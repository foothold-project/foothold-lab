"""EX41 n0 registration, cached terrain cost and per-env fault quarantine.

Isaac/Warp imports stay inside the physical source. CPU tests inject measured
arrays. RewardManager alone multiplies cost by weight and dt.
"""
from collections.abc import Mapping
from pathlib import Path
import copy
import json
import torch
from foothold_s2.rewards import w86

FEET=('FL_foot','FR_foot','RL_foot','RR_foot')
KNEES=('FL_calf_joint','FR_calf_joint','RL_calf_joint','RR_calf_joint')
# Corruption guards, not learning thresholds or clipped reward targets.
# Terrain-relative distances keep valid high world elevations unaffected.
MAX_FOOT_HEIGHT_ERROR_M=5.
MAX_SWING_COST_M2=4*MAX_FOOT_HEIGHT_ERROR_M**2
MAX_BODY_YAW_RATE_RAD_S=100.  # Corruption guard, far above commanded 1.5 rad/s.


class FatalTrainingFault(ValueError):
    """U6: abort the current rollout; never serialize corrupt state as resumable.

    The runner owns the stop/checkpoint boundary and notification transport. It
    must preserve the last verified checkpoint, publish this receipt, and stop
    before another optimizer update. This exception is not env quarantine.
    """
    def __init__(self, record, receipt_path):
        self.record=record
        self.receipt_path=str(receipt_path)
        super().__init__('EX41 fatal: '+record['reason'])


def fatal_fault(adapter, reason, *, env_ids=None, error_type=None):
    """Persist the notification source before unwinding; no checkpoint writes."""
    record={'format':'ex41-fatal/1','event':'fatal_training_fault','reason':reason,
            'step':int(adapter.env.common_step_counter),'stop_requested':True,
            'resumable_checkpoint_written':False,
            'required_action':'preserve_last_verified_checkpoint_and_stop_before_update'}
    if env_ids is not None: record['env_ids']=env_ids.detach().cpu().tolist()
    if error_type is not None: record['error_type']=error_type
    path=adapter.log_dir/'ex41_fatal.jsonl'
    try:
        adapter.log_dir.mkdir(parents=True,exist_ok=True)
        with path.open('a',encoding='utf-8') as out:
            out.write(json.dumps(record,allow_nan=False)+'\n')
    except OSError as exc:
        record['receipt_write_error']=type(exc).__name__
    raise FatalTrainingFault(record,path)


def rotate(q,v):
    """Hamilton wxyz quaternion rotation, all arguments broadcast together."""
    qv=q[...,1:].expand_as(v)
    t=2*torch.cross(qv,v,dim=-1)
    return v+q[...,:1]*t+torch.cross(qv,t,dim=-1)


def prepare_env_cfg(env_cfg,plan):
    """Register once before gym.make, after existing EX40 setup."""
    from isaaclab.managers import RewardTermCfg, TerminationTermCfg, EventTermCfg
    if not getattr(plan,'is_ex41',False): raise ValueError('W86 requires EX41 plan')
    if hasattr(env_cfg.rewards,'ex41_swing'): raise ValueError('W86 already registered')
    for name,value in {'collision':-10.,'action_smoothness':-.01,'joint_power':-2e-5}.items():
        if getattr(getattr(env_cfg.rewards,name,None),'weight',None)!=value:
            raise ValueError('W86 maintained term differs: '+name)
    if getattr(getattr(env_cfg.rewards,'stumble',None),'weight',None)!=-1.:
        raise ValueError('W86 expected one existing stumble -1')
    weights=plan.stages[0].rewards
    for name in ('zero_yaw','swing',*w86.PREREGISTERED):
        setattr(env_cfg.rewards,'ex41_'+name,RewardTermCfg(func=reward_term,
            weight=weights.get(name,0.),params={'name':name}))
    env_cfg.rewards.stumble.weight=weights['stumble']
    env_cfg.terminations.ex41_invalid=TerminationTermCfg(func=invalid_env,time_out=False)
    env_cfg.events.ex41_record_reset=EventTermCfg(func=reset_runtime,mode='reset')
    return {'format':'ex41-w86-registration/1','stumble_single_weight':weights['stumble'],
            'weights':{name:weights.get(name,0.) for name in ('zero_yaw','swing',*w86.PREREGISTERED)},
            'zero_weight_recorder_required':True,'feet':list(FEET),'sample_m':[0.,.05,.10],
            'clearance_m':.08,'moving_command_norm':.1,'contact_n':1.}


def _indices(find,names):
    ids,found=find(list(names),preserve_order=True)
    if list(found)!=list(names) or len(set(ids))!=len(names):
        raise ValueError('W86 explicit name/order differs: '+str(found))
    return ids


def actuator_effort_limits(robot):
    """Read live motor clipping limits in robot joint order, not PhysX's 1e9.

    Isaac Lab ActuatorBase.effort_limit is [env, group_joint]. For explicit
    motors effort_limit_sim/joint_effort_limits may deliberately be 1e9.
    This is the motor's effort ceiling, not its velocity-dependent envelope.
    """
    reference=robot.data.joint_effort_limits
    if reference.ndim!=2: raise ValueError('W86 joint effort shape differs')
    n,j=reference.shape
    result=torch.empty_like(reference); seen=set()
    for actuator in robot.actuators.values():
        indices=actuator.joint_indices
        ids=list(range(j))[indices] if isinstance(indices,slice) else [int(i) for i in indices]
        if not ids or len(set(ids))!=len(ids) or any(i<0 or i>=j or i in seen for i in ids):
            raise ValueError('W86 actuator joint mapping overlaps or is invalid')
        limits=actuator.effort_limit
        if not isinstance(limits,torch.Tensor) or limits.shape!=(n,len(ids)):
            raise ValueError('W86 actuator effort shape differs')
        limits=limits.to(device=reference.device,dtype=reference.dtype)
        if not torch.isfinite(limits).all() or (limits<=0).any():
            raise ValueError('W86 actuator effort limits invalid')
        result[:,ids]=limits; seen.update(ids)
    if seen!=set(range(j)): raise ValueError('W86 actuator effort coverage incomplete')
    return result


class PhysicalSource:
    def __init__(self,env):
        self.env=env; self.robot=env.scene['robot']; self.sensor=env.scene.sensors['contact_forces']
        self.feet=_indices(self.robot.find_bodies,FEET)
        self.force_ids=_indices(self.sensor.find_bodies,FEET)
        self.knees=_indices(self.robot.find_joints,KNEES)
        self.link_names=tuple(self.sensor.body_names)
        if set(self.link_names)!=set(self.robot.body_names):
            raise ValueError('W86 all-link sensor must cover every robot body')
        from isaaclab.sensors import RayCaster
        from isaaclab.utils.warp import raycast_mesh
        if '/World/ground' not in RayCaster.meshes: raise ValueError('W86 actual terrain mesh missing')
        self.mesh=RayCaster.meshes['/World/ground']; self.cast=raycast_mesh

    def __call__(self):
        env=self.env; d=self.robot.data; f=self.feet
        command=env.command_manager.get_command('base_velocity')
        term=env.command_manager.get_term('base_velocity')
        pos=d.body_pos_w[:,f]; quat=d.body_quat_w[:,f]
        center=pos+rotate(quat,torch.tensor([-.002,0.,0.],device=env.device).expand_as(pos))
        sole=center[...,2]-.022
        rootq=d.root_quat_w
        yaw=torch.atan2(2*(rootq[:,0]*rootq[:,3]+rootq[:,1]*rootq[:,2]),
                        1-2*(rootq[:,2].square()+rootq[:,3].square()))
        yawq=torch.zeros_like(rootq); yawq[:,0]=torch.cos(yaw/2); yawq[:,3]=torch.sin(yaw/2)
        inv=yawq.clone(); inv[:,1:]*=-1
        relative=center-d.root_pos_w[:,None,:]
        body=rotate(inv[:,None,:],relative)
        points=w86.ahead_points_body(body[...,:2],torch.nan_to_num(command),
                                    command.new_tensor([0.,.05,.10]))
        starts=torch.cat([points,body[...,2,None,None].expand(-1,-1,3,1)],dim=-1)
        starts=rotate(yawq[:,None,None,:],starts)+d.root_pos_w[:,None,None,:]
        starts[...,2]+=20.
        finite_rays=torch.isfinite(starts).all(-1)
        safe_starts=torch.nan_to_num(starts,nan=0.,posinf=0.,neginf=0.).contiguous()
        directions=torch.zeros_like(safe_starts); directions[...,2]=-1.
        hits=self.cast(safe_starts,directions,self.mesh,max_dist=50.)[0][...,2]
        ground=torch.where(finite_rays,hits,torch.full_like(hits,float('inf')))
        forces=self.sensor.data.net_forces_w[:,self.force_ids]
        command_slot_names=tuple(getattr(term,'slot_names',()))
        command_slot=getattr(term,'slot_current',None)
        command_is_flag=getattr(term,'is_flag_env',None)
        physical_valid=torch.ones(env.num_envs,device=env.device,dtype=torch.bool)
        for x in (d.root_state_w,d.body_state_w,d.joint_pos,d.joint_vel,d.applied_torque,
                  self.sensor.data.net_forces_w,env.action_manager.action,command):
            physical_valid &= torch.isfinite(x).flatten(1).all(-1)
        result=dict(sole_z=sole,velocity_xy=d.body_lin_vel_w[:,f,:2],ground_z=ground,
            forces=forces,command=command,heading=term.heading,yaw=d.root_ang_vel_b[:,2],
            joint_pos=d.joint_pos,torque=d.applied_torque,effort_limits=actuator_effort_limits(self.robot),
            joint_limits=d.soft_joint_pos_limits,physical_valid=physical_valid,knee_ids=self.knees,
            all_link_names=self.link_names,all_forces=self.sensor.data.net_forces_w)
        if command_slot is not None and command_is_flag is not None and command_slot_names:
            result.update(command_slot_names=command_slot_names,command_slot=command_slot,
                          command_is_flag=command_is_flag)
        return result


def _safe(x):
    return torch.nan_to_num(x,nan=0.,posinf=0.,neginf=0.)


class W86Runtime:
    """Cache one pre-reset physical snapshot per control step, not per reward."""
    def __init__(self,env,log_dir,*,source=None):
        self.env=env; self.log_dir=Path(log_dir); self.source=source if source is not None else PhysicalSource(env)
        n=env.num_envs; dev=env.device
        self.pending=torch.zeros(n,dtype=torch.bool,device=dev)
        self.last_contact=torch.zeros(n,4,dtype=torch.bool,device=dev)
        self.observed=torch.zeros(n,4,dtype=torch.bool,device=dev)
        self.in_swing=torch.zeros_like(self.observed)
        self.air_time=torch.zeros(n,4,device=dev); self.peak=torch.zeros_like(self.air_time)
        self.cache=None; self.key=None; self.count=0; self.sums={}; self.quarantine_count=0
        self.link_names=None; self.link_peak=None
        self.command_slot_names=None

    def mark(self,bad,reason):
        bad=bad.to(self.pending.device).bool()
        if bad.shape!=self.pending.shape: raise ValueError('W86 quarantine shape differs')
        if bad.any():
            new=bad & ~self.pending; self.pending |=bad
            self.quarantine_count+=int(new.sum())
            self.log_dir.mkdir(parents=True,exist_ok=True)
            with (self.log_dir/'ex41_quarantine.jsonl').open('a',encoding='utf-8') as out:
                out.write(json.dumps({'step':int(self.env.common_step_counter),'reason':reason,
                    'env_ids':bad.nonzero().flatten().cpu().tolist()},allow_nan=False)+'\n')

    def _sum(self,name,x):
        value=x.detach().sum(0,dtype=torch.float64 if x.is_floating_point() else torch.int64)
        self.sums[name]=self.sums.get(name,torch.zeros_like(value))+value

    def refresh(self):
        key=int(self.env.common_step_counter)
        if self.key==key: return self.cache
        d=self.source(); n=self.env.num_envs
        bad=~d['physical_valid'].bool()
        for name in ('sole_z','velocity_xy','forces','command','yaw','joint_pos','torque'):
            x=d[name]; bad |= ~torch.isfinite(x).reshape(n,-1).all(-1)
        if 'all_forces' in d:
            names=tuple(d['all_link_names']); forces=d['all_forces']
            if (not names or len(set(names))!=len(names) or any(not isinstance(x,str) or not x for x in names)
                or forces.shape!=(n,len(names),3) or self.link_names not in (None,names)):
                raise ValueError('W86 all-link order/shape differs')
            self.link_names=names
            bad |=~torch.isfinite(forces).flatten(1).all(-1)
        self.mark(bad,'nonfinite_physical_state')
        huge_yaw=d['yaw'].abs()>MAX_BODY_YAW_RATE_RAD_S
        self.mark(huge_yaw,'body_yaw_rate_out_of_bounds')
        bad |=huge_yaw
        # Invalid rays are missing terrain evidence, not a zero-height surface.
        target,ray_valid=w86.swing_target(d['ground_z'][...,0],d['ground_z'])
        huge=((d['sole_z']-target).abs()>MAX_FOOT_HEIGHT_ERROR_M) & ray_valid
        huge |= ((d['sole_z']-d['ground_z'][...,0]).abs()>MAX_FOOT_HEIGHT_ERROR_M) & torch.isfinite(d['ground_z'][...,0])
        huge=huge.any(-1)
        self.mark(huge,'physical_height_out_of_bounds')
        bad |=huge
        ray_valid &= ~bad[:,None]
        cmd=_safe(d['command']); moving=(torch.linalg.vector_norm(cmd,dim=-1)>.1) & ~bad
        contact=torch.linalg.vector_norm(_safe(d['forces']),dim=-1)>1.
        liftoff=self.observed & self.last_contact & ~contact & ~bad[:,None]
        touchdown=self.in_swing & contact & ~bad[:,None]
        self.in_swing |=liftoff
        self.air_time=torch.where(liftoff,torch.zeros_like(self.air_time),self.air_time)
        self.peak=torch.where(liftoff,torch.zeros_like(self.peak),self.peak)
        self.air_time+=(self.in_swing & ~contact).float()*self.env.step_dt
        gap=_safe(d['sole_z']-d['ground_z'][...,0])
        self.peak=torch.where(self.in_swing & ray_valid,torch.maximum(self.peak,gap),self.peak)
        self.in_swing &=ray_valid
        touchdown &=self.in_swing
        complete=touchdown & ray_valid & moving[:,None]
        knee_ids=d['knee_ids']
        if len(knee_ids)!=4 or len(set(knee_ids))!=4:
            raise ValueError('W86 requires four explicitly ordered knee indices')
        effort=d['effort_limits'][:,knee_ids]; limits=d['joint_limits']
        if not torch.isfinite(effort).all() or (effort<=0).any() or not torch.isfinite(limits).all():
            raise ValueError('W86 static actuator/joint limits invalid')
        terms={
          'zero_yaw':w86.zero_yaw_l1(_safe(d['yaw']),cmd[:,2],d['heading']),
          'swing':w86.swing_clearance_cost(_safe(d['sole_z']),target,_safe(d['velocity_xy']),contact,ray_valid,moving),
          'knee_effort_margin':w86.effort_margin_cost(_safe(d['torque'])[:,knee_ids],effort),
          'joint_limit_margin':w86.joint_limit_cost(_safe(d['joint_pos']),limits[...,0],limits[...,1]),
          'feet_air_time':w86.air_time_term(self.air_time,touchdown,moving),
          'foot_slip':w86.slip_cost(_safe(d['velocity_xy']),contact),
          'stumble':w86.stumble_cost(_safe(d['forces'])),
          'stumble_force_floor_1n':w86.stumble_cost(_safe(d['forces']),1.),
        }
        overflow=torch.zeros_like(bad)
        for value in terms.values(): overflow |=~torch.isfinite(value)
        excessive=terms['swing']>MAX_SWING_COST_M2
        self.mark(excessive,'swing_cost_out_of_bounds')
        overflow |=excessive
        self.mark(overflow,'nonfinite_derived_reward')
        bad |=overflow; ray_valid &=~bad[:,None]; complete &=~bad[:,None]
        self._sum('complete_swing_count',complete.long())
        self._sum('complete_swing_peak_sum_m',torch.where(complete,self.peak,torch.zeros_like(self.peak)))
        self._sum('complete_swing_time_sum_s',torch.where(complete,self.air_time,torch.zeros_like(self.air_time)))
        for name,value in terms.items():
            terms[name]=torch.where(bad,torch.zeros_like(value),value)
            self._sum('term/'+name,terms[name])
        fm=w86.foot_metrics(d['sole_z'],d['ground_z'][...,0],d['velocity_xy'],contact,moving & ~bad)
        for name in ('swing_frames','contact_moving_frames','drag_frames','low_swing_frames'):
            self._sum(name,fm[name])
        self._sum('invalid_ray_frames',~torch.isfinite(d['ground_z']).all(-1))
        self._sum('valid_foot_frames',fm['valid'] & ~bad[:,None])
        self._sum('swing_height_sum_m',torch.where(fm['swing_frames'].bool(),fm['height_m'],torch.zeros_like(gap)))
        self._sum('knee_limit_frames',(_safe(d['torque'])[:,knee_ids].abs()/effort>=.9) & ~bad[:,None])
        self._sum('knee_valid_frames',(~bad[:,None]).expand(-1,4))
        self._sum('knee_abs_torque_sum_nm',torch.where(~bad[:,None],_safe(d['torque'])[:,knee_ids].abs(),0.))
        self._sum('knee_effort_limit_sum_nm',torch.where(~bad[:,None],effort,0.))
        self._sum('knee_detail_valid_frames',(~bad[:,None]).expand(-1,4))
        if all(key in d for key in ('command_slot_names','command_slot','command_is_flag')):
            names=tuple(d['command_slot_names'])
            slots=d['command_slot']; flags=d['command_is_flag']
            if (not names or len(set(names))!=len(names) or any(not isinstance(name,str) or not name for name in names)
                    or slots.shape!=(n,) or flags.shape!=(n,)):
                raise ValueError('W86 command slot labels/shape differ')
            if self.command_slot_names not in (None,names):
                raise ValueError('W86 command slot order changed')
            self.command_slot_names=names
            slots=slots.to(device=bad.device,dtype=torch.long)
            flags=flags.to(device=bad.device,dtype=torch.bool)
            valid_slot=(slots>=0)&(slots<len(names))&~flags
            group=torch.where(flags,torch.full_like(slots,len(names)),
                              torch.where(valid_slot,slots,torch.full_like(slots,len(names)+1)))
            contact_valid=contact&~bad[:,None]
            force_n=torch.linalg.vector_norm(_safe(d['forces']).double(),dim=-1)
            for index in range(len(names)+2):
                selected=(group==index)[:,None]
                self._sum(f'command_force_sum/{index}',torch.where(contact_valid&selected,force_n,0.))
                self._sum(f'command_contact_frames/{index}',(contact_valid&selected).long())
        if 'all_forces' in d:
            force=torch.linalg.vector_norm(_safe(d['all_forces']).double(),dim=-1)
            valid=(~bad[:,None]).expand_as(force)
            force=torch.where(valid,force,torch.zeros_like(force))
            self._sum('links/contact_frames',(force>1.) & valid)
            self._sum('links/valid_frames',valid)
            self._sum('links/force_sum_n',force)
            peak=force.max(0).values
            self.link_peak=peak if self.link_peak is None else torch.maximum(self.link_peak,peak)
        self.in_swing &=~contact & ~bad[:,None]
        self.observed[:]=~bad[:,None]; self.last_contact=contact.clone()
        self.count+=n; self.key=key; self.cache={'terms':terms,'bad':bad,'ray_valid':ray_valid}
        return self.cache

    def on_reset(self,ids):
        self.observed[ids]=False; self.in_swing[ids]=False
        self.air_time[ids]=0.; self.peak[ids]=0.
        # Keep pending and this-step cache until quarantine_step consumes them.

    def flush(self,iteration):
        row={'format':'ex41-w86-metrics/1','iteration':int(iteration),'env_frames':self.count,
             'control_dt_s':float(self.env.step_dt),
             'feet_order':list(FEET),'knee_order':list(KNEES),'feet':{},'terms':{},'quarantine_env_count':self.quarantine_count}
        row['foot_contact_force_by_command']={'status':'unavailable',
            'reason':'source_has_no_command_slot_labels'}
        if self.command_slot_names is not None:
            groups=(*self.command_slot_names,'flag','unclassified')
            by_command={}
            for index,name in enumerate(groups):
                force_sum=self.sums.get(f'command_force_sum/{index}',torch.zeros(4,dtype=torch.float64))
                frames=self.sums.get(f'command_contact_frames/{index}',torch.zeros(4,dtype=torch.int64))
                foot_rows={}
                for foot_index,foot in enumerate(FEET):
                    denominator=int(frames[foot_index])
                    total=float(force_sum[foot_index])
                    foot_rows[foot]={'contact_frames':denominator,
                        'contact_time_s':denominator*float(self.env.step_dt),
                        'force_sum_n':total,
                        'mean_force_n':total/denominator if denominator else None}
                by_command[name]={'feet':foot_rows}
            row['foot_contact_force_by_command']={
                'status':'measured','source':'contact_forces.net_forces_w',
                'group_by':'MixedVelocityCommand.slot_current; flag and invalid slots separate',
                'contact_threshold_n':1.0,
                'mean_definition':'vector-norm force averaged only over frames whose same foot exceeds the contact threshold',
                'record_only':True,'feet_order':list(FEET),'commands':by_command}
        for name,value in self.sums.items():
            if name.startswith('links/'):continue
            if name.startswith(('command_force_sum/','command_contact_frames/')):continue
            if name.startswith('term/'):
                row['terms'][name[5:]]={'sum':float(value.cpu()),'denominator':self.count,
                                       'mean':float(value.cpu())/self.count if self.count else None}
            else: row['feet'][name]=value.cpu().tolist()
        near=self.sums.get('knee_limit_frames',torch.zeros(4,dtype=torch.int64))
        valid=self.sums.get('knee_valid_frames',torch.zeros(4,dtype=torch.int64))
        row['knee_effort']={'definition':'abs(applied_torque)/actuator.effort_limit >= threshold_fraction',
                           'limit_source':'actuator.effort_limit; not PhysX effort_limit_sim; not velocity envelope',
                           'threshold_fraction':.9,'record_only':True,'joints':{}}
        for i,name in enumerate(KNEES):
            numerator,denominator=int(near[i]),int(valid[i])
            row['knee_effort']['joints'][name]={'near_limit_frames':numerator,'valid_frames':denominator,
                'ratio':numerator/denominator if denominator else None}
            # Old resumed recorder state can lack these new sums. Do not divide
            # new detail samples by the older accumulated count or invent zero.
            detail=int(self.sums.get('knee_detail_valid_frames',torch.zeros(4,dtype=torch.int64))[i])
            row['knee_effort']['joints'][name].update(detail_valid_frames=detail,
                mean_abs_applied_torque_nm=float(self.sums['knee_abs_torque_sum_nm'][i])/detail if detail else None,
                mean_effort_limit_nm=float(self.sums['knee_effort_limit_sum_nm'][i])/detail if detail else None)
        row['all_link_contact']={'status':'unavailable','reason':'source_has_no_all_link_forces'}
        if self.link_names is not None and 'links/valid_frames' in self.sums:
            links={}
            for i,name in enumerate(self.link_names):
                num=int(self.sums['links/contact_frames'][i]); den=int(self.sums['links/valid_frames'][i])
                group=('foot' if name.endswith('_foot') else 'calf' if name.endswith('_calf')
                       else 'thigh' if name.endswith('_thigh') else 'trunk' if name in ('base','trunk')
                       or name.startswith('Head_') else 'other')
                links[name]={'group':group,'contact_frames':num,'valid_frames':den,'contact_ratio':num/den if den else None,
                    'mean_force_n':float(self.sums['links/force_sum_n'][i])/den if den else None,
                    'force_peak_n':float(self.link_peak[i]) if den else None}
            row['all_link_contact']={'status':'measured','source':'net_forces_w','threshold_n':1.,
                'sample':'control-step pre-reset snapshot; net force may hide opposing contacts',
                'record_only':True,'links':links}
        self.log_dir.mkdir(parents=True,exist_ok=True)
        with (self.log_dir/'ex41_w86.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,allow_nan=False)+'\n')
        self.count=0; self.sums={}; self.quarantine_count=0; self.link_peak=None
        return row

    def state_dict(self):
        return dict(format='ex41-w86/1',count=self.count,quarantine_count=self.quarantine_count,
                    sums={k:v.cpu().clone() for k,v in self.sums.items()},
                    command_slot_names=self.command_slot_names,
                    link_names=self.link_names,link_peak=None if self.link_peak is None else self.link_peak.cpu().clone(),
                    physical_episode_reset_on_resume=True)

    def load_state_dict(self,state):
        if state.get('format')!='ex41-w86/1': raise ValueError('W86 resume schema differs')
        self.count=int(state['count']); self.quarantine_count=int(state['quarantine_count'])
        self.sums={k:v.to(self.pending.device).clone() for k,v in state['sums'].items()}
        saved_commands=state.get('command_slot_names')
        self.command_slot_names=None if saved_commands is None else tuple(saved_commands)
        if self.command_slot_names is not None and (not self.command_slot_names
                or len(set(self.command_slot_names))!=len(self.command_slot_names)):
            raise ValueError('W86 saved command slot names invalid')
        self.link_names=None if state.get('link_names') is None else tuple(state['link_names'])
        self.link_peak=state.get('link_peak')
        if self.link_peak is not None:self.link_peak=self.link_peak.to(self.pending.device).clone()
        if 'links/valid_frames' in self.sums and (not self.link_names or self.link_peak is None
            or self.link_peak.shape!=(len(self.link_names),) or not torch.isfinite(self.link_peak).all()):
            raise ValueError('W86 saved link metadata invalid')
        if self.count<0 or any(not torch.isfinite(x).all() for x in self.sums.values()):
            raise ValueError('W86 saved counts nonfinite')
        self.on_reset(slice(None)); self.pending[:]=False; self.key=None; self.cache=None


def attach_runtime(env,plan,log_dir):
    if not getattr(plan,'is_ex41',False) or hasattr(env,'_ex41_w86'):
        raise ValueError('W86 attach requires EX41 and must happen once')
    adapter=W86Runtime(env,log_dir); env._ex41_w86=adapter
    from foothold_s2.rewards.stair_start_hist import snapshot
    adapter.log_dir.mkdir(parents=True,exist_ok=True)
    with (adapter.log_dir/'ex41_stair_start.jsonl').open('a',encoding='utf-8') as out:
        out.write(json.dumps({'event':'stair_start_angle_hist','initialization_index':0,
            'iteration':None,'iteration_note':'adapter_attach_before_restored_training_iteration_is_known',
            'stair_start_angle_hist':snapshot(env)},allow_nan=False)+'\n')
    return adapter


def reward_term(env,name):
    return env._ex41_w86.refresh()['terms'][name]


def invalid_env(env):
    a=env._ex41_w86; a.refresh()
    return a.pending.clone()


def reset_runtime(env,env_ids):
    from foothold_s2.rewards.stair_start_hist import record_reset
    try:
        record_reset(env,env_ids)
    except (AttributeError, KeyError, ValueError, IndexError) as exc:
        # P4 is record-only. Preserve a visible missing-evidence reason without
        # changing reset/quarantine behavior when diagnostic metadata is absent.
        env._ex41_stair_hist_error=type(exc).__name__+': '+str(exc)
    a=getattr(env,'_ex41_w86',None)
    if a is not None: a.on_reset(env_ids if env_ids is not None else slice(None))


def _leaves(value):
    if isinstance(value,torch.Tensor): yield value
    elif isinstance(value,Mapping) or hasattr(value,'items'):
        for v in value.values(): yield from _leaves(v)


def _bad_rows(value,n,device):
    out=torch.zeros(n,device=device,dtype=torch.bool)
    for tensor in _leaves(value):
        if tensor.is_floating_point() and tensor.ndim and tensor.shape[0]==n:
            out |=~torch.isfinite(tensor).reshape(n,-1).all(-1).to(device)
    return out


def _global_nonfinite(value,n):
    return any(t.is_floating_point() and (not t.ndim or t.shape[0]!=n)
               and not torch.isfinite(t).all() for t in _leaves(value))


def _sanitize(value,bad,fill=0.):
    """Return owned transition storage; rollout tensors can alias policy std.

    In particular action_sigma is an expanded view of the policy parameter.
    Writing even one invalid row in place would modify every environment's std.
    Preserve TensorDict containers and never write into caller-owned leaves.
    """
    if isinstance(value,torch.Tensor):
        if value.ndim and value.shape[0]==len(bad):
            result=value.detach().clone()
            result[bad.to(result.device)]=fill
            return result
    elif isinstance(value,Mapping) or hasattr(value,'items'):
        result=value.clone() if hasattr(value,'clone') else copy.copy(value)
        for key,child in value.items(): result[key]=_sanitize(child,bad,fill)
        return result
    return value


def quarantine_actions(runner,actions):
    a=runner.env.unwrapped._ex41_w86
    if _global_nonfinite(actions,len(a.pending)):
        fatal_fault(a,'global_nonfinite_action')
    bad=_bad_rows(actions,len(a.pending),a.pending.device)
    transition=getattr(runner.alg,'transition',None)
    if transition is not None:
        if _global_nonfinite(vars(transition),len(bad)):
            fatal_fault(a,'global_nonfinite_transition')
        for value in vars(transition).values(): bad |=_bad_rows(value,len(bad),bad.device)
    if bad.any():
        policy=getattr(runner.alg,'policy',None)
        if policy is not None and any(not torch.isfinite(p).all() for p in policy.parameters()):
            fatal_fault(a,'global_nonfinite_policy')
        if bad.all():
            fatal_fault(a,'all_env_actions_invalid')
    a.mark(bad,'nonfinite_action_or_pending_transition')
    result=actions.clone(); result[bad.to(actions.device)]=0.
    return result


def quarantine_step(runner,observations,rewards,dones,extras):
    env=runner.env.unwrapped; a=env._ex41_w86; n=len(a.pending)
    if _global_nonfinite(observations,n) or _global_nonfinite(rewards,n):
        fatal_fault(a,'global_nonfinite_observation')
    bad=a.pending | _bad_rows(observations,n,a.pending.device) | _bad_rows(rewards,n,a.pending.device)
    extras=dict(extras)
    # Snapshot before pending is cleared. Normal termination remains valid.
    # The PPO consumer must apply this to GAE/normalization/loss/KL denominators.
    extras['ex41_ppo_valid']=(~bad).clone()
    if not bad.any(): return observations,rewards,dones,extras
    a.mark(bad,'post_step_quarantine')
    # If the termination manager already reset a bad env, do not reset it twice.
    reset_ids=(bad & ~dones.to(bad.device).bool()).nonzero().flatten()
    # Invalid reset observations need one additional env-local reset.
    obs_bad=_bad_rows(observations,n,bad.device)
    reset_ids=torch.unique(torch.cat([reset_ids,obs_bad.nonzero().flatten()]))
    if reset_ids.numel():
        try:
            env._reset_idx(reset_ids); env.scene.write_data_to_sim(); env.sim.forward()
            fresh=env.observation_manager.compute(update_history=False)
            if _global_nonfinite(fresh,n):
                fatal_fault(a,'global_nonfinite_reset_observation',env_ids=reset_ids)
            for key in observations.keys():
                observations[key][reset_ids.to(observations[key].device)]=fresh[key][reset_ids].to(observations[key].device)
        except FatalTrainingFault:
            raise
        except Exception as exc:
            fatal_fault(a,'env_reset_failed',env_ids=reset_ids,error_type=type(exc).__name__)
    remaining=_bad_rows(observations,n,bad.device)
    if remaining.any():
        a.mark(remaining,'post_reset_still_invalid')
        fatal_fault(a,'post_reset_still_invalid',env_ids=remaining.nonzero().flatten())
    rewards=rewards.clone(); rewards[bad.to(rewards.device)]=0.
    dones=dones.clone(); dones[bad.to(dones.device)]=True
    extras=dict(extras)
    if 'time_outs' in extras:
        extras['time_outs']=extras['time_outs'].clone(); extras['time_outs'][bad.to(extras['time_outs'].device)]=False
    transition=getattr(runner.alg,'transition',None)
    if transition is not None:
        for name,value in vars(transition).items():
            setattr(transition,name,_sanitize(value,bad,1. if name in ('action_sigma','action_std') else 0.))
    # Other episode aggregate log values must not poison training summaries.
    for group in ('episode','log'):
        if group in extras:
            extras[group]=copy.deepcopy(extras[group])
            for x in _leaves(extras[group]):
                if x.is_floating_point(): x.nan_to_num_(nan=0.,posinf=0.,neginf=0.)
    a.on_reset(bad.nonzero().flatten()); a.pending[:]=False
    return observations,rewards,dones,extras
