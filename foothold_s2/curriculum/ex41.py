"""EX-41 local-update state machine and boundary-only W72 application."""
from pathlib import Path
import copy
import hashlib
import json
import math
import re
import yaml
import torch
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Callable
from foothold_s2.curriculum import w72
from foothold_s2.curriculum.continuous import Plan, Runtime, Stage, RANGES, FIRST_REWARDS, sha256
from foothold_s2.commands.mixed_core import EX39_SLOTS

STAGE_IDS = ('S2-0', 'S2a', 'S2b', 'S2c', 'T0_prime')
NEW_REWARDS = {'zero_yaw','swing','stumble','knee_effort_margin','joint_limit_margin','feet_air_time','foot_slip'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def validate_metrics(metrics):
    """Reject malformed scorer input before automatic arithmetic or promotion."""
    for name in ('gait_sync','knee_limit_delta','forward_error_delta','w78_min_lr_ratio'):
        if name in metrics and (type(metrics[name]) not in (int,float) or not math.isfinite(metrics[name])):
            raise ValueError('EX41 invalid automatic metric: '+name)
    for name in ('gait_sync','w78_min_lr_ratio'):
        if name in metrics and not 0<=metrics[name]<=1: raise ValueError('EX41 ratio outside [0,1]: '+name)
    if 'stand_min_passed' in metrics and (type(metrics['stand_min_passed']) is not int or not 0<=metrics['stand_min_passed']<=64):
        raise ValueError('EX41 stand count outside 64 env contract')
    if 'pairs' in metrics:
        if not isinstance(metrics['pairs'],dict): raise ValueError('EX41 pairs mapping required')
        for name,pair in metrics['pairs'].items():
            if name not in ('side','diag_fwd','diag_back') or not isinstance(pair,dict) or set(pair)!={'left','right'}:
                raise ValueError('EX41 automatic pair shape differs')
            for sample in pair.values():
                if not isinstance(sample,list) or len(sample)!=2 or type(sample[0]) is not int or not 0<=sample[0]<=64 or type(sample[1]) not in (int,float) or not math.isfinite(sample[1]) or sample[1]<0:
                    raise ValueError('EX41 automatic pair must be [survivors/64, absolute_error]')


def validate_shares(shares):
    if set(shares) != set(EX39_SLOTS) or any(type(v) not in (int,float) or not math.isfinite(v) or v <= 0 for v in shares.values()):
        raise ValueError('EX41 requires all finite positive command slots')
    if not math.isclose(sum(shares.values()), 1., abs_tol=1e-9):
        raise ValueError('EX41 command shares must sum to 100 percent')


def validate_ranges(ranges, old=None):
    if set(ranges) != set(RANGES):
        raise ValueError('EX41 range keys differ')
    for k,v in ranges.items():
        if len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) or v[0]>=v[1]:
            raise ValueError('EX41 invalid range')
        if old and (v[0]>old[k][0] or v[1]<old[k][1]):
            raise ValueError('EX41 range narrows')


class EX41Plan(Plan):
    """Plan-compatible stages S2-0/S2a/S2b/S2c/T0_prime.

    Public attributes: is_ex41=True, parent_update, parent_sha256, initial_dr_scale,
    path/sha256/effective_sha256, stages:list[Stage], heading_cfg/stand_cfg,
    domain_randomization, terrain_curriculum, gate_cfg, promotion/shadow_gate,
    boundary_path, approvals_path, stage_meta. load_plan is the public entry.
    stage_meta[id] includes minimum_updates, maximum_updates, terrain policy.
    """
    def __init__(self, path: str | Path, *, arm: str | None = None,
                 smoke_boundaries: tuple[int, ...] | None = None):
        self.path=Path(path).resolve(strict=True)
        self.sha256=sha256(self.path)
        d=yaml.safe_load(self.path.read_text(encoding='utf-8-sig'))
        allowed={'format','start','parent_update','parent_sha256','baseline_env_yaml_sha256','baseline_agent_yaml_sha256',
                 'promotion','shadow_gate','terrain_curriculum','boundary_file','approval_file','gate','stand_penalty',
                 'heading','domain_randomization','first_rewards','ranges','stages','automatic'}
        self.fixed_schedule=d.get('fixed_schedule') if isinstance(d,dict) else None
        if self.fixed_schedule is not None: allowed.add('fixed_schedule')
        if not isinstance(d,dict) or set(d)!=allowed or d['format']!='foothold-ex41-curriculum/1':
            raise ValueError('EX41 unknown/missing schema field')
        if d['start']!='transfer' or type(d['parent_update']) is not int or d['parent_update'] not in (6000,7500) or arm!='B':
            raise ValueError('EX41 requires registered m6000/m7500 transfer and arm B')
        for k in ('parent_sha256','baseline_env_yaml_sha256','baseline_agent_yaml_sha256'):
            if not re.fullmatch('[0-9a-f]{64}',d[k]): raise ValueError('EX41 missing SHA pin')
            setattr(self,k,d[k])
        self.parent_update=d['parent_update']; self.arm=arm; self.is_ex41=True
        self.promotion=d['promotion']; self.shadow_gate=d['shadow_gate']
        if self.fixed_schedule is None:
            if self.promotion!='gate' or self.shadow_gate is not False: raise ValueError('EX41 requires active performance gates')
        elif self.promotion!='fixed' or self.shadow_gate is not True or self.parent_update!=6000:
            raise ValueError('EX41 fixed5000 requires fixed stages, shadow performance and m6000')
        self.terrain_curriculum=d['terrain_curriculum']
        self.heading_cfg=copy.deepcopy(d['heading']); self.stand_cfg=copy.deepcopy(d['stand_penalty'])
        self.gate_cfg=d['gate']; self.automatic=d['automatic']; self.domain_randomization=d['domain_randomization']
        w72.validate_pair_bounds(self.automatic['pair_step'],self.automatic['pair_limit'])
        if self.automatic['interval_updates']!=250: raise ValueError('EX41 approved boundary interval is 250')
        dr=self.domain_randomization
        if (not isinstance(dr,dict) or dr.get('mode') not in ('constant','boundary_ramp')
            or type(dr.get('scale')) not in (int,float) or not math.isfinite(dr['scale'])
            or not 0<=dr['scale']<=1 or dr.get('observation_noise')!={'mode':'fixed','multiplier':1.}):
            raise ValueError('EX41 initial DR scale/noise invalid')
        self.initial_dr_scale=float(dr['scale'])
        if self.initial_dr_scale!={6000:.5,7500:1.}[self.parent_update]:
            raise ValueError('EX41 parent initial DR scale differs: m6000=.5, m7500=1')
        self.boundary_path=self.path.with_name(d['boundary_file']); self.approvals_path=self.path.with_name(d['approval_file'])
        self.effective_sha256=digest({'table':self.sha256,'arm':arm,'smoke':smoke_boundaries})
        rewards=d['first_rewards']
        if set(rewards)!=FIRST_REWARDS|NEW_REWARDS or any(type(v) not in (float,int) or not math.isfinite(v) for v in rewards.values()):
            raise ValueError('EX41 FIRST_REWARDS set incomplete or nonfinite')
        if rewards['zero_yaw']!=-.5 or not -20<=rewards['swing']<=-2 or not -3<=rewards['stumble']<=-1:
            raise ValueError('EX41 initial weights outside lead decision')
        if any(rewards[k]!=0 for k in ('knee_effort_margin','joint_limit_margin','feet_air_time','foot_slip')):
            raise ValueError('EX41 preregistered terms must start at zero')
        expected=('S2a','S2b','S2c','S2d','S2e','T0_prime') if self.fixed_schedule else STAGE_IDS
        if [r.get('id') for r in d['stages']]!=list(expected): raise ValueError('EX41 stage order differs')
        if smoke_boundaries is not None and (len(smoke_boundaries)!=len(expected)-1 or list(smoke_boundaries)!=sorted(set(smoke_boundaries)) or smoke_boundaries[0]<1):
            raise ValueError('EX41 smoke needs one increasing boundary per stage transition')
        self.stages=[]; self.stage_meta={}; prev=None
        for i,row in enumerate(d['stages']):
            if set(row)!={'id','start','duration','shares','ranges','force_gt','terrain'}: raise ValueError('EX41 stage unknown/missing field')
            validate_shares(row['shares']); validate_ranges(row['ranges'],prev)
            prev=row['ranges']; sid=row['id']; is_t0=sid=='T0_prime'
            if row['force_gt'] is not (not is_t0): raise ValueError('EX41 map switch differs')
            n=int(row['start']['fixed_update']) if smoke_boundaries is None or i==0 else smoke_boundaries[i-1]
            duration=copy.deepcopy(row['duration'])
            if smoke_boundaries is not None and i>0:
                span=(smoke_boundaries[i]-n) if i<len(expected)-1 else 2
                duration.update(minimum_updates=span,maximum_updates=span)
            self.stage_meta[sid]={**duration,'terrain':copy.deepcopy(row['terrain'])}
            adds={'rewards':rewards,'command_slots':list(EX39_SLOTS)} if i==0 else ({'map_source':'reconstruction'} if is_t0 else {})
            self.stages.append(Stage(sid,n,copy.deepcopy(row['shares']),{k:tuple(v) for k,v in row['ranges'].items()},
                                     dict(rewards),row['force_gt'],.20,arm,dict(self.heading_cfg),adds))
        self.smoke_boundaries=smoke_boundaries
        if self.fixed_schedule:
            from foothold_s2.curriculum.ex41_fixed import validate_plan
            validate_plan(self,d)


class EX41Runtime(Runtime):
    """Runtime-compatible local-n state machine plus committed W72 config.

    Public inherited methods: attach/start/on_reset/on_update_start,
    record_pre_step/record_post_step/flush_consumption/on_checkpoint,
    state_dict/load_state_dict/on_resume_checkpoint/after_physical_resume_reset.
    start(parent_sha256) verifies the transfer parent; it is not EX40 scratch.
    Properties: finished:bool, stop_requested:bool, max_updates:int|None,
    effective:dict, stage_meta and pending evaluation are in checkpoint state.
    Externally supported stage ids: S2-0, S2a, S2b, S2c, T0_prime.
    """
    def __init__(self, plan, env_count: int, device: str, log_dir: str | Path,
                 score_dir: str | Path | None = None,
                 terrain_policy: dict | None = None, segment_index: int = 0):
        super().__init__(plan,env_count,device,log_dir,score_dir,terrain_policy,segment_index)
        self.templates=copy.deepcopy(plan.stages)
        self.stage_pos=0
        self.stage_meta=plan.stage_meta
        self.finished=False; self.stop_requested=False; self.graduated=False
        self.max_updates=None  # S2a/S2b performance hold has no invented n cap.
        self.effective={}; self._hook=None; self._receipt=None; self._applied_ids=set()
        self._snapshot=None; self._config_values=None
        self._last_boundary=-1; self._iteration=0; self._extensions=0
        self._pair_bias={}; self._halved=set(); self._auto_disabled=False
        self._mirror_pending=False; self._auto_seen=set(); self._history=[]
        self._level_history=[]; self._s2c_pass=False
        self._ramp=(0,plan.initial_dr_scale,plan.initial_dr_scale,0)
        self._stage_baseline_sha=plan.parent_sha256

    def set_stage_changed_hook(self, callback: Callable[[Stage, dict], dict]) -> None:
        """Install before attach/start; called at initial application and boundary.

        callback(stage, effective) MUST apply approved terrain/mirror/PPO fields
        and return JSON-serializable actual readback. effective contains:
          iteration:int, stage_id:str, terrain:{policy,level_cap},
          critic_mirror:bool, ppo:{entropy_coef,desired_kl},
          dr:{scale,target_scale,ramp_updates},
          reward_weights:dict, heading:dict, shares:dict, ranges:dict.
        On invalid config callback is never invoked. Callback failure must not
        be reported applied. Rollback requires callback(previous_stage, previous
        effective). An invalid mirror authorization during rollback stays OFF,
        is recorded rejected and continues. Other unconfirmed rollback errors
        propagate; they cannot be reported as an applied configuration.
        Commands change per env on reset; global reward/PPO/map fields change at
        update boundary. Effective map usage remains separately logged per env.
        """
        if not callable(callback): raise TypeError('EX41 callback must be callable')
        self._hook=callback

    def boundary_receipt(self) -> dict | None:
        """Last foothold-ex41-application/1 record, or None before first apply.

        Keys: event_id, status(applied/rejected), iteration, stage_before,
        stage_after, config_commit, config_sha256, approval_sha256,
        score_sha256, checkpoint_sha256, decisions, before, after, readback,
        reason. Persisted in one append-only ex41_application.jsonl in NEW run.
        event_id is deterministic and checkpointed for idempotent resume.
        Rejected config retains before; after never pretends unconsumed values.
        """
        return copy.deepcopy(self._receipt)

    def _initial_values(self):
        return {'ppo':{'entropy_coef':.01,'desired_kl':.01},
                'dr':{'target_scale':self.plan.initial_dr_scale,'ramp_updates':0},
                'reward_weights':{'zero_yaw':-.5,'swing':-10.,'stumble':-2.},
                'heading_forward_fraction':.3,'critic_mirror':False,
                'terrain_level_cap':5,'w71_ready':False,'episode_length_s':20.}

    def attach(self, runner, command_term):
        self.runner=runner; command_term.stage_runtime=self
        runner.continuous_curriculum=self
        old=getattr(runner,'ex40_dr_runtime',None)
        if old is not None:
            wrapper=EX41DRReadback(old,self)
            self.dr_runtime=wrapper; runner.ex40_dr_runtime=wrapper
        # start() applies n0 exactly once, after parent transfer. Do not call
        # legacy _sync_rewards: it would reset the lin_vel_z schedule origin.

    def start(self,parent_sha256=None):
        if parent_sha256!=self.plan.parent_sha256: raise ValueError('EX41 configured parent SHA differs')
        if self._started: return
        self._snapshot=w72.read_committed_pair(self.plan.boundary_path,self.plan.approvals_path)
        values=self._snapshot['config'].get('values')
        self._check_values(values)
        if values['dr']!={'target_scale':self.plan.initial_dr_scale,'ramp_updates':0}:
            raise ValueError('EX41 initial DR boundary must match configured parent scale; ramp begins at an approved boundary')
        w72.validate_change(self._initial_values(),values,self._snapshot['approvals'])
        self._config_values=copy.deepcopy(values)
        if not self._apply(0,0,values,[],None,f'configured m{self.plan.parent_update} n0 transfer'):
            raise ValueError('EX41 initial application failed before first rollout')
        self._started=True

    def _check_values(self,values):
        if not isinstance(values,dict) or set(values)!=set(self._initial_values()):
            raise ValueError('EX41 unknown/missing boundary values')
        leaves=w72._leaves(values); expected=w72._leaves(self._initial_values())
        if set(leaves)!=set(expected): raise ValueError('EX41 boundary shape differs')
        for key,value in leaves.items():
            if key in w72.BOOLS:
                if type(value) is not bool: raise ValueError('EX41 boolean field differs')
            elif type(value) not in (int,float) or not math.isfinite(value) or not w72.BOUNDS[key][0]<=value<=w72.BOUNDS[key][1]:
                raise ValueError(f'EX41 boundary invalid: {key}')
        for k in ('dr.ramp_updates','terrain_level_cap'):
            if type(leaves[k]) is not int: raise ValueError('EX41 integer required')

    def _effective(self,pos,n,values):
        s=self.templates[pos]; meta=self.stage_meta[s.id]
        shares=dict(s.shares)
        for pair,bias in self._pair_bias.items():
            left,right=pair.split('|'); shares[left]+=bias; shares[right]-=bias
        validate_shares(shares)
        reward=dict(s.rewards); reward.update(values['reward_weights'])
        heading=dict(s.heading_cfg); heading['forward_fraction']=values['heading_forward_fraction']
        return dict(iteration=n,stage_id=s.id,shares=shares,ranges={k:list(v) for k,v in s.ranges.items()},
            heading=heading,reward_weights=reward,force_gt=s.force_gt,
            terrain={'policy':meta['terrain']['policy'],'level_cap':min(meta['terrain']['level_cap'],values['terrain_level_cap'])},
            critic_mirror=values['critic_mirror'],ppo=copy.deepcopy(values['ppo']),
            dr={'scale':self.dr_scale(n),'target_scale':values['dr']['target_scale'],'ramp_updates':values['dr']['ramp_updates']},
            w71_ready=values['w71_ready'],episode_length_s=values['episode_length_s'])

    def dr_scale(self,n):
        start,initial,target,length=self._ramp
        frac=1. if not length else max(0.,min(1.,(n-start)/length))
        return initial+(target-initial)*frac

    def _grow_counts(self):
        for name in ('_step_counts','_done_counts','_contact_counts','_side_counts','_side_contact_counts'):
            x=getattr(self,name); missing=len(self.plan.stages)-x.shape[0]
            if missing>0: setattr(self,name,torch.cat([x,torch.zeros((missing,*x.shape[1:]),device=x.device,dtype=x.dtype)]))

    def _record_receipt(self,row):
        self.log_dir.mkdir(parents=True,exist_ok=True)
        with (self.log_dir/'ex41_application.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n'); f.flush()
        self._receipt=copy.deepcopy(row)

    def _apply(self,pos,n,values,decisions,score,reason):
        before=copy.deepcopy(self.effective)
        try:
            self._check_values(values)
            after=self._effective(pos,n,values)
            if before and after['dr']['target_scale']!=self.dr_scale(n) and after['dr']['ramp_updates']<=0:
                raise ValueError('EX41 DR target change requires positive ramp_updates')
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            self._reject_boundary(n,exc)
            return False
        snap=self._snapshot or {}
        after['authorization']={'gate':'W72','status':'APPROVED','approval_id':snap.get('approval_sha256'),
            'decision_ids':sorted(set([d['decision_id'] for d in decisions]+([reason] if reason!='boundary_config' else []))),
            'config_commit':snap.get('commit'),'config_sha256':snap.get('config_sha256'),
            'approval_sha256':snap.get('approval_sha256'),
            'boundary_file':str(self.plan.boundary_path.resolve()),
            'approval_file':str(self.plan.approvals_path.resolve())}
        score_sha=(score or {}).get('_sha256')
        event_id=digest([n,before,after,snap.get('config_sha256'),score_sha])
        if event_id in self._applied_ids: return True
        row=dict(format='foothold-ex41-application/1',event_id=event_id,status='rejected',iteration=n,
            parent_update=self.plan.parent_update,stage_before=before.get('stage_id'),stage_after=after['stage_id'],
            config_commit=snap.get('commit'),config_sha256=snap.get('config_sha256'),
            approval_sha256=snap.get('approval_sha256'),score_sha256=score_sha,
            checkpoint_sha256=(score or {}).get('checkpoint_sha256',(self.last_checkpoint or {}).get('sha256',self.plan.parent_sha256)),
            decisions=decisions,before=before,after=before,readback={},reason=reason)
        old_active=self.active; old_pos=self.stage_pos; old_ramp=self._ramp
        s=replace(self.templates[pos],shares=after['shares'],ranges={k:tuple(v) for k,v in after['ranges'].items()},
                  heading_cfg=after['heading'],rewards=after['reward_weights'])
        try:
            if self._hook is None: raise ValueError('EX41 stage_changed consumer missing')
            readback=self._hook(s,copy.deepcopy(after))
            if not isinstance(readback,dict) or not readback: raise ValueError('EX41 consumer readback must be a nonempty mapping')
            json.dumps(readback,allow_nan=False)
            for key in ('terrain','ppo','critic_mirror','episode_length_s','authorization'):
                if key not in readback or digest(readback[key])!=digest(after[key]):
                    raise ValueError('EX41 consumer readback differs: '+key)
            self.effective=after
            self._sync_map(); self._sync_rewards()
            old_dr=before.get('dr',{})
            if (old_dr.get('target_scale'),old_dr.get('ramp_updates'))!=(after['dr']['target_scale'],after['dr']['ramp_updates']):
                self._ramp=(n,after['dr']['scale'],after['dr']['target_scale'],after['dr']['ramp_updates'])
            row.update(status='applied',after=after,readback=readback)
            self._record_receipt(row)
        except Exception as exc:
            self.effective=before; self._ramp=old_ramp
            rollback_error=None
            if before:
                try:
                    self._hook(self.plan.stages[old_active],copy.deepcopy(before))
                except ValueError as restore_exc:
                    if not before.get('critic_mirror'):
                        raise
                    # The setter turns mirror OFF before rejecting changed
                    # authorization bytes. Never resurrect an invalid grant.
                    # A false setter call does not need the old approval.
                    rollback_error=f'{type(restore_exc).__name__}: {restore_exc}'
                    self.effective=copy.deepcopy(before)
                    self.effective['critic_mirror']=False
                    row['readback']=self._hook(self.plan.stages[old_active],copy.deepcopy(self.effective))
                    self._mirror_pending=False
                    self._write({'event':'mirror_rollback_rejected_off','iteration':n,
                                 'error':rollback_error,'critic_mirror':False})
                self._sync_map(); self._sync_rewards()
            row.update(status='rejected',after=copy.deepcopy(self.effective),
                       reason=f'{reason}: {type(exc).__name__}: {exc}',rollback_error=rollback_error)
            self._record_receipt(row)
            return False
        # An immutable version protects old episodes at command resampling.
        if not before:
            self.plan.stages[0]=s; self.active=0
        else:
            self.plan.stages.append(s); self.active=len(self.plan.stages)-1; self._grow_counts()
        self.stage_pos=pos
        if old_pos!=pos:
            self.stage_entry_iteration=n; self._history=[]; self._level_history=[]
            self._stage_baseline_sha=(self.last_checkpoint or {}).get('sha256',self.plan.parent_sha256)
            self._write({'event':'stage_enter','iteration':n,'from':before.get('stage_id'),'to':s.id,
                         'reason':reason,'graduated':reason=='performance_pass','receipt_id':event_id})
        self._applied_ids.add(event_id)
        return True

    def _sync_map(self):
        if self.runner is not None and self.effective:
            value=self.effective['force_gt']
            self.runner.adasmpl.force_gt=value
            self.runner.pcfg['force_gt']=value
            self.runner.perception.cfg.force_gt=value

    def _sync_rewards(self):
        if self.runner is None or not self.effective: return
        manager=self.runner.env.unwrapped.reward_manager
        mapping={'hip_pos_penalty':'basic_hip_pos_penalty_l1','thigh_calf_pos_l1':'ex39_thigh_calf_pos_l1',
                 'four_foot_contact_at_stop':'ex39_four_foot_stop','stand_gap':'ex40_stand_gap','stand_load':'ex40_stand_load',
                 'zero_yaw':'ex41_zero_yaw','swing':'ex41_swing'}
        for name,value in self.effective['reward_weights'].items():
            if name in ('knee_effort_margin','joint_limit_margin','feet_air_time','foot_slip'):
                if value!=0: raise ValueError('EX41 preregistered zero cannot activate mid-run')
                continue
            key=mapping.get(name,name); cfg=copy.deepcopy(manager.get_term_cfg(key))
            cfg.weight=value; manager.set_term_cfg(key,cfg)
        self.runner.basic_lin_vel_z_schedule=False
        cfg=copy.deepcopy(manager.get_term_cfg('lin_vel_z')); cfg.weight=0.; manager.set_term_cfg('lin_vel_z',cfg)

    def _reject_boundary(self,n,exc):
        self._record_receipt(dict(format='foothold-ex41-application/1',event_id=digest([n,str(exc)]),status='rejected',
            iteration=n,stage_before=self.effective.get('stage_id'),stage_after=self.effective.get('stage_id'),
            config_commit=None,config_sha256=None,approval_sha256=None,score_sha256=None,checkpoint_sha256=None,
            decisions=[],before=copy.deepcopy(self.effective),after=copy.deepcopy(self.effective),readback={},reason=str(exc)))

    def _read_scores(self,n):
        if self.score_dir is None: return []
        rows=[]
        for p in sorted(self.score_dir.glob('*.json')):
            h=None
            try:
                h=sha256(p)
                if h in self.seen_scores: continue
                d=json.loads(p.read_text(encoding='utf-8-sig')); json.dumps(d,allow_nan=False)
                if not isinstance(d,dict): raise ValueError('EX41 score must be an object')
                it=d.get('iteration')
                if type(it) is not int or it>n: continue  # not yet consumable
                if d.get('format')!='foothold-ex41-score/1': raise ValueError('EX41 score format differs')
                if d.get('stage_id')!=self.effective['stage_id']: raise ValueError('EX41 score stage differs')
                if d.get('schedule_sha256')!=self.plan.effective_sha256 or d.get('parent_sha256')!=self.plan.parent_sha256:
                    raise ValueError('EX41 score run differs')
                if it<self.stage_entry_iteration or n-it>self.plan.gate_cfg['maximum_score_age']:
                    raise ValueError('EX41 stale score')
                cp=Path(d['checkpoint_path']).resolve(strict=True)
                if cp.name!=f'model_{it}.pt' or sha256(cp)!=d['checkpoint_sha256']: raise ValueError('EX41 score checkpoint differs')
                stamp=datetime.fromisoformat(d['created_at'])
                if stamp.tzinfo is None or stamp>datetime.now(timezone.utc): raise ValueError('EX41 score time invalid')
                if any(type(d.get(k)) is not bool for k in ('maintenance_pass','stage_pass','safety_stop')):
                    raise ValueError('EX41 score decisions missing')
                if not isinstance(d.get('metrics'),dict) or not isinstance(d.get('evidence'),list) or not d['evidence']:
                    raise ValueError('EX41 score measured evidence missing')
                validate_metrics(d['metrics'])
                for e in d['evidence']:
                    if not isinstance(e,dict): raise ValueError('EX41 evidence must be an object')
                    if sha256(Path(e['path']).resolve(strict=True))!=e['sha256']: raise ValueError('EX41 raw evidence SHA differs')
                if d.get('baseline_checkpoint_sha256')!=self._stage_baseline_sha: raise ValueError('EX41 stage baseline differs')
                if d['safety_stop']:
                    self.stop_requested=True
                    self._write({'event':'registered_safety_stop','score_sha256':h,'iteration':n})
                d['_sha256']=h; rows.append(d)
            except (ValueError,KeyError,OSError,TypeError) as exc:
                self._write({'event':'score_rejected','path':str(p),'sha256':h,'reason':str(exc)})
                if h is not None: self.seen_scores.add(h)
        # A conflict at the same checkpoint invalidates all versions, not just
        # whichever file happened to sort last.
        out=[]
        for it in sorted({r['iteration'] for r in rows}):
            group=[r for r in rows if r['iteration']==it]
            existing=[r for r in self._history if r['iteration']==it]
            if len(group)+len(existing)>1:
                self._history=[r for r in self._history if r['iteration']!=it]
                self._write({'event':'score_conflict','iteration':it,'hashes':[r['_sha256'] for r in group+existing]})
            else: out.extend(group)
            self.seen_scores.update(r['_sha256'] for r in group)
        return out

    def on_update_start(self,iteration):
        if not self._started: raise ValueError('EX41 start/load required before rollout')
        if type(iteration) is not int or iteration<0: raise ValueError('EX41 local n invalid')
        self._iteration=iteration
        smoke=self.plan.smoke_boundaries
        boundary=(iteration in (*smoke,smoke[-1]+2)) if smoke else (iteration-1)%250==0
        if iteration<=self._last_boundary or not boundary: return
        self._last_boundary=iteration
        # Safety is independent of a broken or dirty W72 configuration. Valid
        # stop evidence is consumed even when configuration is rejected below.
        score_rows=self._read_scores(iteration)
        self._history=sorted(self._history+score_rows,key=lambda r:r['iteration'])[-8:]
        try:
            snap=w72.read_committed_pair(self.plan.boundary_path,self.plan.approvals_path)
            manual=snap['config'].get('values'); self._check_values(manual)
            decisions=w72.validate_change(self._config_values,manual,snap['approvals'])
        except (ValueError,TypeError,KeyError,OSError,yaml.YAMLError) as exc:
            self._reject_boundary(iteration,exc); return
        self._snapshot=snap
        # Preserve prior automatic changes unless this exact manual field changed.
        values=copy.deepcopy(self._config_values)
        if self.effective:
            values['reward_weights']={k:self.effective['reward_weights'][k] for k in values['reward_weights']}
            values['critic_mirror']=self.effective['critic_mirror']
        for d in decisions:
            dst=values; parts=d['path'].split('.')
            for part in parts[:-1]: dst=dst[part]
            dst[parts[-1]]=d['after']
        if self.stop_requested:
            return
        latest=self._history[-1] if self._history else None
        fresh=[r for r in self._history if iteration-r['iteration']<=self.plan.gate_cfg['maximum_score_age']]
        elapsed=iteration-self.stage_entry_iteration
        transition_state=(self._extensions,self._s2c_pass,self.finished,self.graduated)
        next_pos=self.stage_pos; reason='boundary_config'
        if smoke:
            if iteration==smoke[-1]+2:
                self.finished=self.stage_pos==4; self.graduated=False
                self._write({'event':'smoke_finished','iteration':iteration,'finished':self.finished,'graduated':False})
            else:
                requested=smoke.index(iteration)+1
                if requested!=self.stage_pos+1:
                    reason='smoke_previous_boundary_not_applied'
                elif requested>=3 and not values['w71_ready']:
                    reason='w71_not_ready'
                else:
                    next_pos=requested; reason='smoke_boundary_only_NOT_graduated'
        elif self.stage_pos==0: next_pos=1; reason='first_rollout'
        elif not self.stop_requested:
            meta=self.stage_meta[self.templates[self.stage_pos].id]
            pair=fresh[-2:]
            passed=(len(pair)==2 and pair[1]['iteration']-pair[0]['iteration']>=self.plan.gate_cfg['separated_checkpoints']
                    and all(r['maintenance_pass'] and r['stage_pass'] for r in pair)
                    and elapsed>=meta['minimum_updates'])
            if passed and self.stage_pos<4:
                if self.stage_pos!=2 or values['w71_ready']:
                    next_pos+=1; reason='performance_pass'
                    if self.stage_pos==3: self._s2c_pass=True
                else: reason='w71_not_ready'
            elif self.stage_pos==3 and elapsed>=meta['maximum_updates']+self._extensions*meta['extension_updates']:
                delta=self._level_delta()
                if snap['approvals'].get('automatic',{}).get('extension') and self._extensions<meta['maximum_extensions'] and delta is not None and delta>=self.plan.automatic['extension_level_delta'] and latest and latest in fresh and latest['maintenance_pass'] and latest['metrics'].get('stand_min_passed',0)>=self.plan.automatic['stand_min_passed']:
                    self._extensions+=1; reason='D110 extension once'
                else: next_pos=4; reason='D110 cap transition; S2c NOT graduated'
            elif self.stage_pos==4 and elapsed>=meta['maximum_updates']:
                self.finished=True; self.graduated=passed and self._s2c_pass
                self._write({'event':'T0_prime_finished','iteration':iteration,'graduated':self.graduated,'requires_lead_terrain_decision':not self.graduated})
        auto_state=(copy.deepcopy(self._pair_bias),set(self._halved),self._auto_disabled,self._mirror_pending,set(self._auto_seen))
        # At most one command adjustment per boundary, even if several delayed
        # score files arrived together. They still all inform consecutive tests.
        # A valid score read at a rejected configuration boundary stays in
        # history. Consume it once after repair while it remains fresh.
        pending_auto=[r for r in fresh if r['_sha256'] not in self._auto_seen]
        if pending_auto:
            score=pending_auto[-1]
            decisions+=self._automatic(values,score,next_pos!=self.stage_pos,next_pos=next_pos)
            self._auto_seen.update(r['_sha256'] for r in pending_auto)
        if next_pos!=self.stage_pos and self._mirror_pending:
            values['critic_mirror']=True
            if not any(d['path']=='critic_mirror' for d in decisions):
                decisions.append(dict(path='critic_mirror',before=self.effective['critic_mirror'],after=True,
                                      decision_id=snap['approvals']['automatic']['critic_mirror'],automatic=True))
        changed=bool(decisions) or next_pos!=self.stage_pos or reason.startswith('D110')
        if changed:
            ok=self._apply(next_pos,iteration,values,decisions,latest,reason)
            if ok: self._config_values=copy.deepcopy(manual)
            else:
                self._pair_bias,self._halved,self._auto_disabled,self._mirror_pending,self._auto_seen=auto_state
                self._extensions,self._s2c_pass,self.finished,self.graduated=transition_state
                if self._receipt.get('rollback_error'):
                    self._mirror_pending=False
        else:
            self._config_values=copy.deepcopy(manual)
            self._write({'event':'boundary_keep','iteration':iteration,'stage':self.effective['stage_id'],
                         'reason':reason if reason!='boundary_config' else 'missing_or_insufficient_performance; training continues'})

    def _automatic(self,values,score,stage_boundary,*,next_pos=None):
        if score['_sha256'] in self._auto_seen: return []
        self._auto_seen.add(score['_sha256'])
        metrics=score['metrics']; rules=self._snapshot['approvals'].get('automatic',{}); changes=[]
        latest=self._history[-2:]
        cfg=self.plan.automatic
        def twice(key,pred):
            return len(latest)==2 and latest[1]['iteration']-latest[0]['iteration']>=self.plan.gate_cfg['separated_checkpoints'] and all(key in r['metrics'] and pred(r['metrics'][key]) for r in latest)
        lower=set()
        if twice('gait_sync',lambda x:x<cfg['gait_sync_floor']): lower.add('zero_yaw')
        if twice('knee_limit_delta',lambda x:x>cfg['knee_limit_increase']): lower.add('swing')
        if twice('forward_error_delta',lambda x:x>cfg['forward_error_increase']): lower.update(('swing','zero_yaw'))
        if metrics.get('stand_min_passed',64)<cfg['stand_min_passed']:
            lower.add('swing'); self._auto_disabled=True
        if rules.get('reward_halving'):
            for name in sorted(lower-self._halved):
                old=values['reward_weights'][name]; value=max(w72.BOUNDS['reward_weights.'+name][0],min(w72.BOUNDS['reward_weights.'+name][1],old/2))
                values['reward_weights'][name]=value; self._halved.add(name)
                changes.append(dict(path='reward_weights.'+name,before=old,after=value,decision_id=rules['reward_halving'],automatic=True))
        if rules.get('pair_bias') and not self._auto_disabled:
            for name in ('side','diag_fwd','diag_back'):
                pair=metrics.get('pairs',{}).get(name)
                if not isinstance(pair,dict) or set(pair)!={'left','right'}: continue
                key=name+'_left|'+name+'_right'; old=self._pair_bias.get(key,0.)
                try: new=w72.adjust_pair(old,pair['left'],pair['right'],step=cfg['pair_step'],limit=cfg['pair_limit'],
                                        survival_noise=cfg['pair_survival_noise'],error_noise=cfg['pair_error_noise'])
                except (ValueError,TypeError): continue
                base=self.templates[self.stage_pos if next_pos is None else next_pos].shares
                if base[name+'_left']+new<=0 or base[name+'_right']-new<=0:
                    self._write({'event':'automatic_pair_kept','pair':name,'reason':'would_remove_existing_command','requested_bias':new})
                    continue
                if new!=old:
                    self._pair_bias[key]=new
                    changes.append(dict(path='pair_bias.'+name,before=old,after=new,decision_id=rules['pair_bias'],automatic=True))
        if rules.get('critic_mirror') and score['iteration']<=1000 and twice('w78_min_lr_ratio',lambda x:x<cfg['critic_both_fail_fraction']):
            self._mirror_pending=True
            if stage_boundary:
                values['critic_mirror']=True
                changes.append(dict(path='critic_mirror',before=False,after=True,decision_id=rules['critic_mirror'],automatic=True))
        return changes

    def _level_delta(self):
        # 50-update snapshots, five samples in each complete 250-update window.
        samples=dict(self._level_history); start=self.stage_entry_iteration-1
        first=[samples.get(start+k) for k in range(50,251,50)]
        last=[samples.get(start+k) for k in range(300,501,50)]
        if any(x is None or not math.isfinite(x) for x in first+last): return None
        return sum(last)/5-sum(first)/5

    def on_checkpoint(self,iteration,checkpoint):
        p=Path(checkpoint).resolve(strict=True)
        if p.name!=f'model_{iteration}.pt': raise ValueError('EX41 checkpoint name differs')
        self.last_checkpoint={'iteration':iteration,'path':str(p),'sha256':sha256(p)}

    def flush_consumption(self,iteration):
        super().flush_consumption(iteration)
        if self.runner is not None and iteration%50==0:
            row=terrain_distribution(self.runner.env.unwrapped)
            self._level_history.append((iteration,row['mean_level']))
            self._write({'event':'terrain_distribution','iteration':iteration,**row})

    def state_dict(self):
        state=super().state_dict()
        state.update(format='foothold-ex41-state/1',stages=[asdict(s) for s in self.plan.stages],stage_pos=self.stage_pos,
            effective=copy.deepcopy(self.effective),config_values=copy.deepcopy(self._config_values),snapshot=copy.deepcopy(self._snapshot),
            last_boundary=self._last_boundary,iteration=self._iteration,extensions=self._extensions,
            pair_bias=dict(self._pair_bias),halved=sorted(self._halved),auto_disabled=self._auto_disabled,
            mirror_pending=self._mirror_pending,auto_seen=sorted(self._auto_seen),history=copy.deepcopy(self._history),
            level_history=list(self._level_history),s2c_pass=self._s2c_pass,ramp=self._ramp,
            stage_baseline_sha=self._stage_baseline_sha,receipt=copy.deepcopy(self._receipt),applied_ids=sorted(self._applied_ids),
            finished=self.finished,stop_requested=self.stop_requested,graduated=self.graduated)
        return state

    def load_state_dict(self,state):
        if state.get('format')!='foothold-ex41-state/1' or state.get('plan_sha256')!=self.plan.sha256 or state.get('effective_sha256')!=self.plan.effective_sha256:
            raise ValueError('EX41 self-resume state/plan differs; parent transfer is a separate path')
        if self.segment_index!=state['segment_index']+1: raise ValueError('EX41 resume segment differs')
        saved_terrain=state.get('terrain_receipt')
        env=getattr(getattr(self.runner,'env',None),'unwrapped',None)
        terrain=getattr(getattr(env,'scene',None),'terrain',None)
        if terrain is not None:
            labels=hashlib.sha256(terrain.terrain_levels.detach().cpu().long().contiguous().numpy().tobytes()+
                                  terrain.terrain_types.detach().cpu().long().contiguous().numpy().tobytes()).hexdigest()
            if not saved_terrain or labels!=saved_terrain.get('terrain_labels_sha256'):
                raise ValueError('EX41 restored terrain labels differ from saved checkpoint')
        elif saved_terrain is not None:
            raise ValueError('EX41 saved terrain requires actual restored simulator labels')
        self.plan.stages=[Stage(**s) for s in state['stages']]; self._grow_counts()
        self.active=state['active']; self.stage_pos=state['stage_pos']
        env_stage=state['env_stage'].to(self.env_stage.device)
        if env_stage.shape!=self.env_stage.shape or (env_stage<0).any() or (env_stage>=len(self.plan.stages)).any():
            raise ValueError('EX41 invalid saved episode versions')
        self.env_stage.copy_(env_stage)
        for attr,key in (('effective','effective'),('_config_values','config_values'),('_snapshot','snapshot'),
                         ('_last_boundary','last_boundary'),('_iteration','iteration'),('_extensions','extensions'),
                         ('_pair_bias','pair_bias'),('_auto_disabled','auto_disabled'),('_mirror_pending','mirror_pending'),
                         ('_history','history'),('_level_history','level_history'),('_s2c_pass','s2c_pass'),('_ramp','ramp'),
                         ('_stage_baseline_sha','stage_baseline_sha'),('_receipt','receipt'),('stage_entry_iteration','stage_entry_iteration'),
                         ('last_checkpoint','last_checkpoint'),('finished','finished'),('stop_requested','stop_requested'),('graduated','graduated')):
            setattr(self,attr,copy.deepcopy(state[key]))
        self._halved=set(state['halved']); self._auto_seen=set(state['auto_seen']); self._applied_ids=set(state['applied_ids'])
        self.seen_scores=set(state['seen_scores']); self._started=True
        if self._hook is None: raise ValueError('EX41 restore hook missing')
        before=copy.deepcopy(self.effective)
        try:
            self._hook(self.plan.stages[self.active],copy.deepcopy(before))
        except ValueError as exc:
            if not before.get('critic_mirror'): raise
            # A saved ON value is not a permanent authorization. The setter
            # already disabled it; restore the other fields with mirror OFF.
            after=copy.deepcopy(before); after['critic_mirror']=False
            readback=self._hook(self.plan.stages[self.active],copy.deepcopy(after))
            self.effective=after; self._mirror_pending=False
            row=copy.deepcopy(self._receipt or {})
            row.update(format='foothold-ex41-application/1',
                event_id=digest(['resume_mirror_rejected_off',self.segment_index,before]),
                status='rejected',iteration=self._iteration,before=before,after=after,
                readback=readback,reason=f'resume_mirror_rejected_off: {exc}')
            self._record_receipt(row)
            self._write({'event':'resume_mirror_rejected_off','iteration':self._iteration,
                         'error':str(exc),'critic_mirror':False})
        self._sync_map(); self._sync_rewards()
        if state.get('domain_randomization') is not None:
            if self.dr_runtime is None: raise ValueError('EX41 saved DR consumer missing')
            self.dr_runtime.load_state_dict(state['domain_randomization'],self._iteration+1)


class EX41DRReadback:
    """Keep the existing physical DR events/readback; replace its n-based ramp."""
    def __init__(self,base,runtime):
        self.base=base; self.runtime=runtime
        base.scale=runtime.plan.initial_dr_scale; base.env._ex40_dr_scale=base.scale

    def update_start(self,update):
        b=self.base; b.update=int(update); b.schedule_update=None; b.smoke=False
        b.scale=self.runtime.dr_scale(update); b.env._ex40_dr_scale=b.scale
        if not b._first_update:
            b.env._ex40_dr_samples={}
            action=b.env.action_manager.get_term('joint_pos')
            if hasattr(action,'_ex40_sample_counts'): action._ex40_sample_counts=None
        b._first_update=False

    def summary(self):
        row=self.base.summary(); row['schedule']='EX41 constant or approved boundary ramp'
        return row

    def state_dict(self):
        row=self.base.state_dict(); row['format']='ex41-dr-runtime/1'; return row

    def load_state_dict(self,state,next_update):
        if state.get('format')!='ex41-dr-runtime/1' or state.get('config_sha256')!=self.base.config_sha256:
            raise ValueError('EX41 DR state differs')
        b=self.base; b.update=state['last_update']; b.scale=state['scale']; b.env._ex40_dr_scale=b.scale
        device=getattr(b.env,'device','cpu')
        if state.get('com_baseline') is not None: b.env._ex40_dr_com_baseline=torch.as_tensor(state['com_baseline']).to(device).clone()
        if state.get('motor_baselines') is not None:
            b.env._ex40_dr_motor_baselines={k:{n:torch.as_tensor(v).to(device).clone() for n,v in vs.items()} for k,vs in state['motor_baselines'].items()}


def prepare_terrain_cfg(env_cfg,plan):
    """Register the term at n0, fixed until the runtime enables S2c."""
    from isaaclab.managers import CurriculumTermCfg
    env_cfg.scene.terrain.max_init_terrain_level=2
    env_cfg.curriculum.terrain_levels=CurriculumTermCfg(func=ex41_terrain_levels,
        params={'command_name':'base_velocity','resample_s':4.,'world_frame':True})
    return {'policy':'fixed_l02','max_init_terrain_level':2,'promotion_enabled':False,
            'registered_performance_term':'ex41_terrain_levels','world_frame':True}


def capped_moves(levels,moves,cap):
    if type(cap) is not int or cap<0: raise ValueError('EX41 level cap invalid')
    return torch.where(((moves>0)&(levels>=cap))|((moves<0)&(levels<=0)),torch.zeros_like(moves),moves)


def ex41_terrain_levels(env,env_ids,command_name='base_velocity',resample_s=4.,world_frame=True):
    """Existing judge_free world displacement, with explicit upper cap.

    Term runs before reset events/command reset. Pure spin/stand have zero
    translation sum and remain at their level. Curriculum changes no mesh.
    """
    from foothold_s2.curriculum import rules
    terrain=env.scene.terrain
    settings=getattr(env,'_ex41_terrain',{'policy':'fixed_l02','level_cap':2})
    if settings['policy']!='performance': return terrain.terrain_levels.float().mean()
    term=env.command_manager.get_term(command_name)
    ids=torch.as_tensor(env_ids,device=env.device,dtype=torch.long)
    if not world_frame or not hasattr(term,'cmd_sum_w'): raise ValueError('EX41 requires world-frame command displacement')
    if term.is_flag_env[ids].any(): raise ValueError('EX41 has no flag slots; new terrain contract required')
    summed=term.cmd_sum_w[ids]*env.step_dt/resample_s
    moves=rules.judge_free(term.max_dist[ids],summed,size_x=terrain.cfg.terrain_generator.size[0],resample_s=resample_s)
    moves=capped_moves(terrain.terrain_levels[ids],moves,settings['level_cap'])
    terrain.update_env_origins(ids,moves>0,moves<0)
    return terrain.terrain_levels.float().mean()


def terrain_distribution(env):
    """Read real labels; column assignment matches installed Isaac generator."""
    terrain=env.scene.terrain; cfg=terrain.cfg.terrain_generator
    if cfg.curriculum is not True: raise ValueError('EX41 column names require curriculum generator or actual tile manifest')
    names=list(cfg.sub_terrains); proportions=[float(cfg.sub_terrains[k].proportion) for k in names]
    if sum(proportions)<=0: raise ValueError('EX41 terrain proportions empty')
    cumulative=[]; total=0.
    for p in proportions: total+=p/sum(proportions); cumulative.append(total)
    columns=[names[next(j for j,c in enumerate(cumulative) if i/cfg.num_cols+.001<c)] for i in range(cfg.num_cols)]
    levels=terrain.terrain_levels.detach().cpu().long(); types=terrain.terrain_types.detach().cpu().long()
    if levels.shape!=types.shape or (types<0).any() or (types>=len(columns)).any(): raise ValueError('EX41 terrain label mismatch')
    per_kind={}
    for name in names:
        mask=torch.tensor([columns[i]==name for i in types.tolist()],dtype=torch.bool)
        per_kind[name]={'env_count':int(mask.sum()),'levels':torch.bincount(levels[mask],minlength=cfg.num_rows).tolist()}
    return {'columns':columns,'by_terrain':per_kind,'mean_level':float(levels.float().mean()),
            'labels_sha256':hashlib.sha256(levels.numpy().tobytes()+types.numpy().tobytes()).hexdigest()}


def apply_runtime_fields(runner,stage,effective):
    """Default stage_changed hook for runner integration. No reward duplication.

    Use functools.partial(apply_runtime_fields, runner). The owning runtime
    applies reward/map and DR. This hook applies terrain/PPO/critic/episode.
    """
    env=runner.env.unwrapped; terrain=effective['terrain']
    if terrain['policy'] not in ('fixed_l02','performance'): raise ValueError('EX41 unknown terrain policy')
    if terrain['policy']=='performance' and not effective['w71_ready']: raise ValueError('EX41 W71 consumer not verified')
    cap=terrain['level_cap']
    if not 0<=cap<env.scene.terrain.terrain_origins.shape[0]: raise ValueError('EX41 terrain cap exceeds generated rows')
    if int(env.scene.terrain.terrain_levels.max())>cap: raise ValueError('EX41 cap cannot silently discard current levels')
    setter=getattr(runner,'set_ex41_critic_mirror',None)
    if not callable(setter): raise ValueError('EX41 critic mirror consumer not installed')
    try:
        setter(effective['critic_mirror'],approval=effective['authorization'] if effective['critic_mirror'] else None)
    except ValueError:
        # The enclosing runtime transaction records rejected and restores
        # other fields. Never leave a failed ON request effective at the hook.
        setter(False,approval=None)
        raise
    runner.alg.entropy_coef=effective['ppo']['entropy_coef']; runner.alg.desired_kl=effective['ppo']['desired_kl']
    env.cfg.episode_length_s=effective['episode_length_s']
    env._ex41_terrain=copy.deepcopy(terrain)
    runner.continuous_curriculum.terrain_policy={'policy':terrain['policy'],'max_init_terrain_level':2,
                                                'promotion_enabled':terrain['policy']=='performance','level_cap':cap}
    return {'terrain':copy.deepcopy(env._ex41_terrain),'ppo':{'entropy_coef':runner.alg.entropy_coef,'desired_kl':runner.alg.desired_kl},
            'critic_mirror':runner.ex41_critic_mirror,'episode_length_s':env.cfg.episode_length_s,
            'authorization':copy.deepcopy(effective['authorization'])}
