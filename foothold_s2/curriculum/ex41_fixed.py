"""Approved 5000-update EX41 schedule, with bounded DR safety pauses.

Local n is the next rollout index (1 based). Nominal time is completed updates.
No gate grants early promotion. A pause delays the remaining schedule and keeps
the current DR slope after recovery; exhaustion freezes DR, not learning.
"""
import copy
import json
import math
from pathlib import Path
import yaml
from foothold_s2.curriculum import w72
from foothold_s2.curriculum.continuous import sha256
from foothold_s2.curriculum.ex41 import EX41Runtime

DURATIONS=(750,1000,1000,1250,500,500)
STARTS=(0,750,1750,2750,4000,4500)
POINTS=((0,.5),(750,.5),(1750,.65),(2750,.8),(4000,1.),(5000,1.))
CASES=('fwd0.5','fwd1.0','spin+1.2','spin-1.2','back0.5','back1.0',
       'side+0.5','side-0.5','diag-fwd+side+','diag-fwd+side-',
       'diag-back+side+','diag-back+side-','stop')
CELLS=tuple(f'{mode}/{case}'+('_record_only' if mode=='eval_pred' else '')
            for mode in ('eval_gt','probe_prop_only','eval_pred') for case in CASES)


def maintenance_cells(include_record_only=True):
    """Exact producer/consumer contract. Default 39; 26 needs a new plan decision."""
    if type(include_record_only) is not bool: raise ValueError('record_only selection must be bool')
    return CELLS if include_record_only else CELLS[:26]


def build_maintenance_counts(score, baseline, *, total_envs):
    """Runner adapter for native score.cells. passed means alive_envs_at_end.

    This is survival, not tracking success or flat_stand.passed_envs. The caller
    must verify the evaluated batch contains 64 envs and attach the normal score
    envelope (parent, checkpoint/evidence hashes, iteration and schedule SHA).
    """
    if type(total_envs) is not int or total_envs!=64:
        raise ValueError('maintenance counts require exactly 64 evaluated envs')
    if not isinstance(baseline,dict) or set(baseline) not in (set(CELLS),set(CELLS[:26])):
        raise ValueError('maintenance baseline must select exact 39 or 26 cells')
    if not isinstance(score,dict) or not isinstance(score.get('cells'),dict):
        raise ValueError('native score.cells mapping required')
    out={}
    for key,b in baseline.items():
        row=score['cells'].get(key)
        value=row.get('alive_envs_at_end') if isinstance(row,dict) else None
        if any(type(v) is not int or not 0<=v<=64 for v in (value,b)):
            raise ValueError('invalid or missing alive_envs_at_end: '+key)
        out[key]={'passed':value,'baseline_passed':b,'total':64}
    return out


def validate_plan(plan,doc):
    cfg=plan.fixed_schedule
    expected={'duration_updates':5000,'pause_limit_updates':1000,'recovery_boundaries':2,
              'extension_updates':500,'maximum_extensions':1,'maintenance_drop_count':3,
              'interval_updates':250}
    if set(cfg)!=set(expected)|{'maintenance_baseline','include_record_only'} or any(cfg[k]!=v for k,v in expected.items()):
        raise ValueError('EX41 fixed5000 decision parameters differ')
    maintenance_cells(cfg['include_record_only'])
    if type(plan.automatic['stand_min_passed']) is not int or plan.automatic['stand_min_passed']!=61:
        raise ValueError('EX41 approved stand_min_passed is 61')
    if (tuple(r['duration']['maximum_updates'] for r in doc['stages'])!=DURATIONS
        or tuple(r['duration']['minimum_updates'] for r in doc['stages'])!=DURATIONS
        or tuple(r['start']['fixed_update'] for r in doc['stages'])!=(0,751,1751,2751,4001,4501)):
        raise ValueError('EX41 fixed stage lengths/start points differ')
    b=cfg['maintenance_baseline']
    if not isinstance(b,dict) or set(b)!={'path','sha256'} or not isinstance(b['path'],str) or len(b['sha256'])!=64:
        raise ValueError('EX41 pinned maintenance baseline required')
    if plan.initial_dr_scale!=.5: raise ValueError('EX41 fixed schedule starts at .5')


def baseline_counts(plan):
    cfg=plan.fixed_schedule['maintenance_baseline']; p=Path(cfg['path']).resolve(strict=True)
    if sha256(p)!=cfg['sha256']: raise ValueError('EX41 maintenance baseline SHA differs')
    data=json.loads(p.read_text(encoding='utf-8-sig'))
    if data['checkpoint_iteration']!=6000 or data['checkpoint_sha256']!=plan.parent_sha256:
        raise ValueError('EX41 maintenance baseline parent differs')
    out={key:data['cells'][key]['alive_envs_at_end']
         for key in maintenance_cells(plan.fixed_schedule['include_record_only'])}
    if any(type(v) is not int or not 0<=v<=64 for v in out.values()):
        raise ValueError('EX41 maintenance baseline requires selected counts out of 64')
    return out


def maintenance(counts,baseline):
    """None means missing evidence. No missing mode/cell can count as recovery."""
    if not isinstance(counts,dict) or set(counts)!=set(baseline): return None
    failed=[]
    for key,b in baseline.items():
        row=counts[key]
        if (not isinstance(row,dict) or set(row)!={'passed','baseline_passed','total'}
            or type(row['passed']) is not int or not 0<=row['passed']<=64
            or type(row['baseline_passed']) is not int or row['baseline_passed']!=b
            or type(row['total']) is not int or row['total']!=64): return None
        if row['passed']<b-3: failed.append(key)
    return failed


class Clock:
    """Serializable elapsed-time clock, even when a consumer rejects a setting."""
    def __init__(self):
        self.anchor=1; self.elapsed=0; self.paused=False; self.pause_used=0
        self.recovered=0; self.last_score_iteration=None; self.frozen_scale=None
        self.extension=0; self.extension_decided=False

    def time(self,n): return self.elapsed+(0 if self.paused else max(0,n-self.anchor))

    def scale(self,n):
        if self.frozen_scale is not None: return self.frozen_scale
        t=self.time(n)
        for (a,x),(b,y) in zip(POINTS,POINTS[1:]):
            if t<=b: return x+(y-x)*max(0,min(1,(t-a)/(b-a)))
        return 1.

    def boundary(self,n,failed,score_iteration):
        if n<self.anchor: raise ValueError('EX41 schedule clock cannot go backwards')
        delta=n-self.anchor
        old_scale=self.scale(n)
        event='schedule_continue'
        if self.paused:
            held=min(delta,max(0,1000-self.pause_used))
            self.pause_used+=held
            if held<delta:
                # A skipped/rejected boundary cannot spend an extra 250 hold.
                self.elapsed+=delta-held
                self.paused=False; self.frozen_scale=old_scale; self.recovered=0
                event='dr_pause_budget_exhausted_frozen_report'
        else: self.elapsed+=delta
        self.anchor=n
        # Only a rising DR segment needs a pause. Initial adaptation still gets
        # its full 750 updates, even when evidence is absent in an early window.
        can_rise=750<=self.elapsed<4000 and self.frozen_scale is None
        if can_rise:
            if failed is None or failed:
                self.paused=True; self.recovered=0; self.last_score_iteration=None
                event='dr_hold_missing_evidence' if failed is None else 'dr_hold_maintenance'
            elif self.paused:
                if score_iteration!=self.last_score_iteration:
                    self.recovered=(self.recovered+1 if self.last_score_iteration is not None
                                    and score_iteration-self.last_score_iteration==250 else 1)
                    self.last_score_iteration=score_iteration
                if self.recovered>=2:
                    self.paused=False; self.recovered=0; event='dr_resume_same_slope'
                else: event='dr_hold_recovery_1_of_2'
        # Recovery at the exact cap has priority. Freeze only while unrecovered.
        if self.paused and self.pause_used>=1000:
            self.paused=False; self.frozen_scale=old_scale; self.recovered=0
            event='dr_pause_budget_exhausted_frozen_report'
        return event

    def position(self,n):
        t=self.time(n)
        starts=(*STARTS[:-1],STARTS[-1]+self.extension)
        return max(i for i,start in enumerate(starts) if t>=start)


class EX41FixedRuntime(EX41Runtime):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.clock=Clock(); self.baseline=None
        self._missing_maintenance_boundaries=0
        self.max_updates=6500  # 5000 + bounded DR holds1000 + one extension500.

    def start(self,parent_sha256=None):
        self.baseline=baseline_counts(self.plan)
        super().start(parent_sha256)

    def _check_values(self,values):
        super()._check_values(values)
        if not values['w71_ready']:
            raise ValueError('EX41 fixed schedule requires verified W71 consumer before launch')

    def dr_scale(self,n): return self.clock.scale(n)

    def _effective(self,pos,n,values):
        result=super()._effective(pos,n,values)
        result['dr']={'scale':self.dr_scale(n),'target_scale':self.dr_scale(n),'ramp_updates':0}
        return result

    def _apply(self,*args,**kwargs):
        history=self._history
        ok=super()._apply(*args,**kwargs)
        self._history=history  # Fixed-parent evidence survives stage changes.
        # Fixed maintenance comparison always refers to the selected parent,
        # never a stage-entry checkpoint chosen after seeing new results.
        self._stage_baseline_sha=self.plan.parent_sha256
        return ok

    def on_update_start(self,n):
        if not self._started: raise ValueError('EX41 start/load required before rollout')
        if type(n) is not int or n<0: raise ValueError('EX41 local n invalid')
        self._iteration=n
        smoke=self.plan.smoke_boundaries
        boundary=(n in (*smoke,smoke[-1]+2)) if smoke else n>=1 and (n-1)%250==0
        if not boundary or n<=self._last_boundary: return
        if self.finished: return
        self._last_boundary=n
        rows=self._read_scores(n); self._history=sorted(self._history+rows,key=lambda r:r['iteration'])[-8:]
        if self.stop_requested: return
        try:
            snap=w72.read_committed_pair(self.plan.boundary_path,self.plan.approvals_path)
            manual=snap['config']['values']; self._check_values(manual)
            if manual['dr']!={'target_scale':.5,'ramp_updates':0}:
                raise ValueError('EX41 fixed5000 DR controlled by pinned schedule, not manual target')
            decisions=w72.validate_change(self._config_values,manual,snap['approvals'])
        except (ValueError,TypeError,KeyError,OSError,yaml.YAMLError) as exc:
            # Invalid new settings do not cancel the already approved schedule
            # or hide a maintenance-driven DR hold. Use the last valid snapshot.
            self._reject_boundary(n,exc)
            snap=self._snapshot; manual=copy.deepcopy(self._config_values); decisions=[]
        self._snapshot=snap
        values=copy.deepcopy(manual)
        if self.effective:
            values['reward_weights']={k:self.effective['reward_weights'][k] for k in values['reward_weights']}
            for d in decisions:
                if d['path'].startswith('reward_weights.'):
                    values['reward_weights'][d['path'].split('.')[1]]=d['after']
        # Historical rows may be retained for audit, never reused as a fresh
        # 250-update recovery, stand-restoration or extension observation.
        fresh=[r for r in self._history if n-250<=r['iteration']<n]
        score=fresh[-1] if fresh else None
        failed=maintenance(score['metrics'].get('maintenance_counts'),self.baseline) if score else None
        if n>=251:
            self._missing_maintenance_boundaries=(self._missing_maintenance_boundaries+1 if failed is None else 0)
            if self._missing_maintenance_boundaries>=2:
                self._write({'event':'maintenance_evidence_missing_warning','iteration':n,
                    'consecutive_boundaries':self._missing_maintenance_boundaries,
                    'required_cells':len(self.baseline),'score_iteration':score['iteration'] if score else None})
        before=copy.deepcopy(self.clock.__dict__)
        event=self.clock.boundary(n,failed,score['iteration'] if score else None)
        pos=self.clock.position(n)
        if smoke:
            pos=min(5,smoke.index(n)+1) if n in smoke else 5
        # Only automatic reward change approved at 14:0x is stand restoration.
        halve=False
        stand=score['metrics'].get('stand_min_passed') if score else None
        stand_valid=type(stand) is int and 0<=stand<=64
        stand_floor=self.plan.automatic['stand_min_passed']
        if n>=251 and not stand_valid:
            self._write({'event':'stand_evidence_missing','iteration':n,'action':'no_automatic_stand_change_or_extension'})
        if stand_valid and stand<stand_floor and 'swing' not in self._halved:
            if snap['approvals'].get('automatic',{}).get('stand_restore'):
                old=values['reward_weights']['swing']; new=max(-20.,min(-2.,old/2))
                values['reward_weights']['swing']=new; halve=True
                decisions.append(dict(path='reward_weights.swing',before=old,after=new,
                    decision_id=snap['approvals']['automatic']['stand_restore'],automatic=True))
        # Existing D110 one-time extension, immediately before T0 at full DR.
        if not smoke and self.clock.time(n)>=4500 and not self.clock.extension_decided:
            self.clock.extension_decided=True
            delta=self._level_delta()
            if (self.dr_scale(n)==1. and score and failed==[] and score['maintenance_pass']
                and stand_valid and stand>=stand_floor and delta is not None
                and delta>=self.plan.automatic['extension_level_delta']
                and snap['approvals'].get('automatic',{}).get('extension')):
                self.clock.extension=500; pos=4; event='D110_extension_once'
        if self.templates[pos].id!=self.effective['stage_id'] and self.stage_meta[self.templates[pos].id]['terrain']['policy']=='performance' and not values['w71_ready']:
            self._reject_boundary(n,ValueError('w71_not_ready')); return
        # Reapply even within a stage to retain a single boundary receipt with
        # its physical scale and pinned maintenance evidence.
        if self._apply(pos,n,values,decisions,score,event):
            self._config_values=copy.deepcopy(manual)
            if halve: self._halved.add('swing')
            self._write({'event':event,'iteration':n,'schedule_clock':copy.deepcopy(self.clock.__dict__),
                         'failed_cells':failed,'baseline_sha256':self.plan.fixed_schedule['maintenance_baseline']['sha256'],
                         'dr_scale':self.dr_scale(n),'stage':self.effective['stage_id']})
            ended=n==smoke[-1]+2 if smoke else self.clock.time(n)>=5000+self.clock.extension
            if ended:
                self.finished=True; self.graduated=False
                self._write({'event':'fixed_schedule_finished','iteration':n,'graduated':False,
                             'dr_scale':self.dr_scale(n),'full_dr_reached':self.dr_scale(n)==1.,'requires_review':True})
        else:
            # Elapsed time and DR safety observations happened even if a hook
            # rejected a setting. Only unapplied extension decisions roll back.
            self.clock.extension=before['extension']
            self.clock.extension_decided=before['extension_decided']
            self._write({'event':'schedule_clock_accounted_after_rejection','iteration':n,
                         'schedule_clock':copy.deepcopy(self.clock.__dict__)})

    def state_dict(self):
        state=super().state_dict(); state['fixed_clock']=copy.deepcopy(self.clock.__dict__)
        state['maintenance_baseline_sha256']=self.plan.fixed_schedule['maintenance_baseline']['sha256']
        state['missing_maintenance_boundaries']=self._missing_maintenance_boundaries
        return state

    def load_state_dict(self,state):
        self.baseline=baseline_counts(self.plan)
        if state.get('maintenance_baseline_sha256')!=self.plan.fixed_schedule['maintenance_baseline']['sha256']:
            raise ValueError('EX41 fixed resume baseline differs')
        clock=state.get('fixed_clock')
        if not isinstance(clock,dict) or set(clock)!=set(self.clock.__dict__): raise ValueError('EX41 fixed clock missing')
        for key in ('anchor','elapsed','pause_used','recovered','extension'):
            if type(clock[key]) is not int or clock[key]<0: raise ValueError('EX41 fixed clock count invalid')
        if (clock['pause_used']>1000 or clock['extension'] not in (0,500)
            or type(clock['paused']) is not bool or type(clock['extension_decided']) is not bool
            or clock['recovered']>2 or clock['elapsed']>5500):
            raise ValueError('EX41 fixed clock bounds invalid')
        last=clock['last_score_iteration']; boundary=state.get('last_boundary'); iteration=state.get('iteration')
        initial=boundary==-1 and iteration==0 and clock['anchor']==1
        stopped=state.get('stop_requested') is True
        if (type(boundary) is not int or type(iteration) is not int
            or (not initial and (clock['anchor']>iteration or clock['anchor']<1
                or (clock['anchor']!=boundary and not stopped)))
            or (not self.plan.smoke_boundaries and (clock['anchor']-1)%250!=0)
            or clock['elapsed']+clock['pause_used']!=clock['anchor']-1
            or (last is not None and (type(last) is not int or not 0<=last<clock['anchor']))
            or (clock['recovered'] and (last is None or not clock['paused']))):
            raise ValueError('EX41 fixed clock anchor/last score inconsistent')
        if clock['frozen_scale'] is not None and (type(clock['frozen_scale']) not in (int,float)
            or not math.isfinite(clock['frozen_scale']) or not .5<=clock['frozen_scale']<=1):
            raise ValueError('EX41 fixed clock frozen DR invalid')
        missing=state.get('missing_maintenance_boundaries',0)
        if type(missing) is not int or missing<0: raise ValueError('EX41 fixed clock missing-evidence count invalid')
        self.clock.__dict__.update(copy.deepcopy(clock))
        self._missing_maintenance_boundaries=missing
        super().load_state_dict(state)
