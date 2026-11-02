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


class PhysicalSource:
    def __init__(self,env):
        self.env=env; self.robot=env.scene['robot']; self.sensor=env.scene.sensors['contact_forces']
        self.feet=_indices(self.robot.find_bodies,FEET)
        self.force_ids=_indices(self.sensor.find_bodies,FEET)
        self.knees=_indices(self.robot.find_joints,KNEES)
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
        physical_valid=torch.ones(env.num_envs,device=env.device,dtype=torch.bool)
        for x in (d.root_state_w,d.body_state_w,d.joint_pos,d.joint_vel,d.applied_torque,
                  self.sensor.data.net_forces_w,env.action_manager.action,command):
            physical_valid &= torch.isfinite(x).flatten(1).all(-1)
        return dict(sole_z=sole,velocity_xy=d.body_lin_vel_w[:,f,:2],ground_z=ground,
            forces=forces,command=command,heading=term.heading,yaw=d.root_ang_vel_b[:,2],
            joint_pos=d.joint_pos,torque=d.applied_torque,effort_limits=d.joint_effort_limits,
            joint_limits=d.soft_joint_pos_limits,physical_valid=physical_valid,knee_ids=self.knees)


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
        knee_ids=d.get('knee_ids',list(range(d['torque'].shape[1])))
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
             'feet_order':list(FEET),'knee_order':list(KNEES),'feet':{},'terms':{},'quarantine_env_count':self.quarantine_count}
        for name,value in self.sums.items():
            if name.startswith('term/'):
                row['terms'][name[5:]]={'sum':float(value.cpu()),'denominator':self.count,
                                       'mean':float(value.cpu())/self.count if self.count else None}
            else: row['feet'][name]=value.cpu().tolist()
        self.log_dir.mkdir(parents=True,exist_ok=True)
        with (self.log_dir/'ex41_w86.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,allow_nan=False)+'\n')
        self.count=0; self.sums={}; self.quarantine_count=0
        return row

    def state_dict(self):
        return dict(format='ex41-w86/1',count=self.count,quarantine_count=self.quarantine_count,
                    sums={k:v.cpu().clone() for k,v in self.sums.items()},
                    physical_episode_reset_on_resume=True)

    def load_state_dict(self,state):
        if state.get('format')!='ex41-w86/1': raise ValueError('W86 resume schema differs')
        self.count=int(state['count']); self.quarantine_count=int(state['quarantine_count'])
        self.sums={k:v.to(self.pending.device).clone() for k,v in state['sums'].items()}
        if self.count<0 or any(not torch.isfinite(x).all() for x in self.sums.values()):
            raise ValueError('W86 saved counts nonfinite')
        self.on_reset(slice(None)); self.pending[:]=False; self.key=None; self.cache=None


def attach_runtime(env,plan,log_dir):
    if not getattr(plan,'is_ex41',False) or hasattr(env,'_ex41_w86'):
        raise ValueError('W86 attach requires EX41 and must happen once')
    adapter=W86Runtime(env,log_dir); env._ex41_w86=adapter
    return adapter


def reward_term(env,name):
    return env._ex41_w86.refresh()['terms'][name]


def invalid_env(env):
    a=env._ex41_w86; a.refresh()
    return a.pending.clone()


def reset_runtime(env,env_ids):
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
    bad=_bad_rows(actions,len(a.pending),a.pending.device)
    transition=getattr(runner.alg,'transition',None)
    if transition is not None:
        for value in vars(transition).values(): bad |=_bad_rows(value,len(bad),bad.device)
    if bad.any():
        policy=getattr(runner.alg,'policy',None)
        if policy is not None and any(not torch.isfinite(p).all() for p in policy.parameters()):
            raise ValueError('W86 cannot quarantine globally nonfinite policy parameters')
    a.mark(bad,'nonfinite_action_or_pending_transition')
    result=actions.clone(); result[bad.to(actions.device)]=0.
    return result


def quarantine_step(runner,observations,rewards,dones,extras):
    env=runner.env.unwrapped; a=env._ex41_w86; n=len(a.pending)
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
        env._reset_idx(reset_ids); env.scene.write_data_to_sim(); env.sim.forward()
        fresh=env.observation_manager.compute(update_history=False)
        for key in observations.keys():
            observations[key][reset_ids.to(observations[key].device)]=fresh[key][reset_ids].to(observations[key].device)
    remaining=_bad_rows(observations,n,bad.device)
    if remaining.any():
        a.mark(remaining,'post_reset_still_invalid')
        raise ValueError('W86 env reset failed to restore finite observations; simulator repair required')
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
