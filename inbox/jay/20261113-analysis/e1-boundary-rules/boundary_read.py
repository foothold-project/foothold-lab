"""CPU-only artifact reader and draft writer; no GPU imports or apply command.

Inputs are frozen score/JSON/NPZ receipts. All writes are outside the data tree.
See README.md for the exact ledger, metric definitions, replay limitations.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
from zipfile import BadZipFile
from types import SimpleNamespace
import numpy as np
import yaml
from boundary_rules import MODES, JUDGE_MODES, LOW_KEYS, finite, decide

CODE=Path('/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v19')
PARENT=Path('/home/jay/data/foothold/s2_lab/ex42_p1reh_20261113_144455/m13250/ex42_score.json')
RUN=Path('/home/jay/data/foothold/s2_lab/ex42_main_20261113_174400/main/EX-42-B-E1-again_20261113_174400')
FORMAT='analyst-ex42-e1-boundary-draft/1'
MAINTENANCE_CASES=('fwd0.5','fwd1.0','spin+1.2','spin-1.2','back0.5','back1.0',
                   'side+0.5','side-0.5','diag-fwd+side+','diag-fwd+side-',
                   'diag-back+side+','diag-back+side-','stop')
REWARD_FIELDS={
    'track_lin_vel_std':'rewards.track_lin_vel.params.std',
    'track_ang_vel_std':'rewards.track_ang_vel.params.std',
    'feet_air_time':'rewards.ex41_feet_air_time.weight',
    'foot_slip':'rewards.ex41_foot_slip.weight','zero_yaw':'rewards.ex41_zero_yaw.weight',
    'feet_air_time_threshold':'rewards.ex41_feet_air_time.params.threshold',
    'slow_track':'rewards.ex42_slow_track.weight','slow_track_sigma':'rewards.ex42_slow_track.params.sigma',
    'slow_track_speed_min':'rewards.ex42_slow_track.params.speed_min',
    'slow_track_speed_max':'rewards.ex42_slow_track.params.speed_max'}

class Reader:
    def __init__(self):self.sources={}
    def bytes(self,path,expected=None):
        path=Path(path);raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if expected and digest!=expected:raise ValueError(f'SHA mismatch: {path}')
        if str(path) in self.sources and self.sources[str(path)]!=digest:
            raise ValueError(f'input changed while reading: {path}')
        self.sources[str(path)]=digest
        return raw
    def json(self,path):
        data=json.loads(self.bytes(path).decode('utf-8-sig'),parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON:'+x)))
        if not isinstance(data,dict):raise ValueError('JSON must be an object: '+str(path))
        return data
    def npz(self,path,expected=None):
        with np.load(io.BytesIO(self.bytes(path,expected)),allow_pickle=False) as z:
            return {k:z[k] for k in z.files}

def fingerprint(doc,case,command):
    friction=doc.get('evaluation_friction') or {}
    return dict(envs=doc.get('envs'),steps=doc.get('steps'),seed=doc.get('eval_seed'),
                mesh=(doc.get('ex42_mesh') or {}).get('mesh_sha256'),
                assignment=doc.get('fixed_terrain',{}).get('assignment_sha256'),
                level=doc.get('fixed_terrain',{}).get('fixed_level'),
                dr_off=doc.get('dr_off'),command=command,case=case,
                friction=[friction.get(k) for k in ('static','dynamic','combine_mode')])

def checked_source(doc,checkpoint,seed=42):
    if doc.get('checkpoint_sha256')!=checkpoint or doc.get('envs')!=64:
        raise ValueError('checkpoint/64-env identity mismatch')
    actual=doc.get('eval_seed',doc.get('conditions',{}).get('seed'))
    if actual!=seed:raise ValueError('seed mismatch')
    if 'steps' in doc and doc['steps']!=300:raise ValueError('step denominator mismatch')
    if doc.get('dr_off') is False:raise ValueError('DR-on evidence not allowed')

def _npz_alive(z,checkpoint,seed):
    identity=json.loads(str(z['run_identity'].item()))
    alive=np.asarray(z['alive'])
    if (identity['checkpoint_sha256']!=checkpoint or identity['eval_seed']!=seed or
        alive.shape!=(300,64) or alive.dtype!=bool or not np.array_equal(alive.sum(0),z['alive_steps']) or
        not np.array_equal(alive[-1],z['alive_end']) or not math.isclose(float(z['dt']),.02,abs_tol=1e-8)):
        raise ValueError('NPZ identity or alive denominator mismatch')
    return alive

def maintenance_mode_status(score):
    """Require the named GT/PRED 26-cell contract, not any 26 judged rows."""
    modes=score.get('cell_judgments',{})
    if set(modes)!=set(MODES):raise ValueError('maintenance map modes incomplete')
    status={}
    for mode in MODES:
        rows=modes[mode]
        if set(rows)!=set(MAINTENANCE_CASES):raise ValueError('maintenance command coverage differs: '+mode)
        role='judge' if mode in JUDGE_MODES else 'record_only'
        if any(row.get('role')!=role for row in rows.values()):raise ValueError('maintenance mode role differs: '+mode)
        if mode not in JUDGE_MODES:continue
        judgments=[row.get('judgment') for row in rows.values()]
        if any(x not in ('PASS','FAIL','HOLD') for x in judgments):raise ValueError('invalid maintenance judgment: '+mode)
        status[mode]='FAIL' if 'FAIL' in judgments else 'HOLD' if 'HOLD' in judgments else 'PASS'
    return status

def load_snapshot(score_path,iteration=None,code_root=CODE,legacy_low=None,seed=42,repeat=False):
    score_path=Path(score_path);folder=score_path.parent;r=Reader()
    if iteration is None:
        match=re.fullmatch(r'm([1-9][0-9]*|0)',folder.name)
        iteration=int(match[1]) if match else None
    s=dict(iteration=iteration,score_path=str(score_path),metrics={},fingerprints={},errors=[],warnings=[],
           maintenance=None,maintenance_modes={},overall=None,comparable=True,repeats={},sources=r.sources)
    def add(key,value,fp):
        if not finite(value):raise ValueError('nonfinite metric '+key)
        s['metrics'][key]=value;s['fingerprints'][key]=fp
    def guarded(label,fn):
        try:fn()
        except (OSError,ValueError,KeyError,TypeError,IndexError,EOFError,BadZipFile,AttributeError) as exc:
            s['errors'].append(label+': '+str(exc))
    try:
        score=r.json(score_path)
        cp=score['checkpoint_sha256']
        if not re.fullmatch('[0-9a-f]{64}',cp):raise ValueError('invalid checkpoint SHA')
        if score.get('format')!='foothold-ex42-maintenance-score/1':raise ValueError('score format differs')
        if (score['conditions']['envs']!=64 or score['conditions']['steps']!=300 or
            score['conditions']['eval_seed']!=42 or set(score['conditions']['modes'])!=set(MODES)):
            raise ValueError('score denominator/seed/modes differs')
        s.update(checkpoint_sha256=cp,plan_sha256=score.get('execution_plan_sha256'),
                 maintenance=score.get('maintenance_judgement'),overall=score.get('judgement'),
                 score_config_sha256=score.get('score_config_sha256'))
        s['maintenance_modes']=maintenance_mode_status(score)
        if s['maintenance']=='PASS' and any(x!='PASS' for x in s['maintenance_modes'].values()):
            raise ValueError('maintenance PASS contradicts per-cell verdict')
        if iteration is None:raise ValueError('provide --iteration for non mN folder')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        s['errors'].append('score: '+str(exc));return s

    def map_source(path,suite,level,low=False):
        doc=r.json(path);checked_source(doc,cp,seed)
        if not (doc.get('ex42_mesh') or {}).get('mesh_sha256') and not legacy_low:
            raise ValueError('mesh identity missing')
        if low and doc['fixed_terrain']['fixed_level']!=int(level[1:]):raise ValueError('low level mismatch')
        if not low and set(doc['modes'])!=set(MODES):raise ValueError('map64 three modes required')
        for mode,cases in doc['modes'].items():
            for case,row in cases.items():
                if low and case not in ('fwd0.1','fwd0.2','side+0.2','side-0.2','side+0.4','side-0.4'):continue
                cmd=doc['commands'][case];speed=math.hypot(*cmd[:2]);per=row['per_env']
                if len(per)!=64 or row['env_count']!=64 or [a['env'] for a in per]!=list(range(64)):
                    raise ValueError(f'env IDs/denominator {mode}/{case}')
                fp=fingerprint(doc,case,cmd);prefix=f'{suite}/{level}/{mode}/{case}/'
                add(prefix+'env_count',64,fp);add(prefix+'survival',row['alive_envs_at_end'],fp)
                for axis in ('vx','vy','wz'):
                    vals=np.array([a[f'{axis}_abs_error_mean_alive_'+('radps' if axis=='wz' else 'mps')] for a in per])
                    if not np.isfinite(vals).all():raise ValueError('nonfinite per-env MAE')
                    add(prefix+axis+'_mae',float(np.median(vals)),fp)
                if speed:
                    vals=np.array([a['command_xy_projection_integral_m'] for a in per],dtype=float)/(speed*6)
                    if not np.isfinite(vals).all():raise ValueError('nonfinite progress')
                    if low and case.startswith('fwd'):
                        name=doc['env_arrays'][mode+'/'+case]
                        if Path(name).name!=name:raise ValueError('raw path escapes map folder')
                        z=r.npz(path.parent/name);alive=_npz_alive(z,cp,seed)
                        vx=z['vx'].astype(float)
                        if not np.isfinite(vx).all():raise ValueError('nonfinite body velocity')
                        vals=(vx*alive).sum(0)/300/speed
                        if not np.allclose(vals*speed*6,z['body_vx_integral_m'],atol=1e-5,rtol=0):
                            raise ValueError('body vx integral receipt mismatch')
                        if int(alive[-1].sum())!=row['alive_envs_at_end']:raise ValueError('survival receipt mismatch')
                        samples=alive[100:200].sum(0)
                        stalls=int(np.count_nonzero((vx[100:200]*alive[100:200]).sum(0)/np.maximum(samples,1)<.05))
                        add(prefix+'stalled_2to4s',stalls,fp)
                    add(prefix+'R',float(np.median(vals)),fp)
                if cmd[2]:add(prefix+'yaw_follow',row['yaw_follow_median'],fp)
                if case=='stop':
                    add(prefix+'speed_median_mps',float(np.median([a['body_xy_speed_mean_alive_mps'] for a in per])),fp)
                    add(prefix+'yaw_speed_median_radps',float(np.median([a['wz_abs_error_mean_alive_radps'] for a in per])),fp)
                    if finite(row.get('stationary_fraction_2to4s')):add(prefix+'stationary_fraction_2to4s',row['stationary_fraction_2to4s'],fp)
        # Compare summary score values with their actual raw JSON, not rounded chat text.
        if not low and not repeat:
            for mode,rows in score.get('map64',{}).items():
                for case,row in rows.items():
                    for field,key in [('alive_at_end','survival'),('vx_abs_error_median_mps','vx_mae'),
                                      ('vy_abs_error_median_mps','vy_mae'),('wz_abs_error_median_radps','wz_mae')]:
                        if not math.isclose(row[field],s['metrics'][f'map/mixed012/{mode}/{case}/{key}'],abs_tol=1e-7):
                            raise ValueError('score and map receipt disagree')

    for level in (0,5):
        path=(Path(legacy_low)/f'hipan_g1b_L{level}/map_modes.json' if legacy_low else folder/f'e1_v2/L{level}/map_modes.json')
        guarded('low_L'+str(level),lambda p=path,l=level:map_source(p,'low',f'L{l}',True))
    guarded('map64',lambda:map_source(folder/'map64/map_modes.json','map','mixed012'))

    def yaw_source():
        path=folder/'axis_v2/axis_v2.json';doc=r.json(path);checked_source(doc,cp,seed)
        if doc.get('fixed_level')!=2:raise ValueError('axis L2 required')
        for mode in MODES:
            for case in ('fwd0.5','fwd1.0'):
                row=doc['modes'][mode][case];raw=path.parent/Path(row['raw_file']).name
                z=r.npz(raw,row['raw_sha256']);alive=z['alive'].astype(bool)
                if alive.shape!=(300,64) or not np.array_equal(alive,np.arange(300)[:,None]<alive.sum(0)) or np.any(alive.sum(0)==0):
                    raise ValueError('axis alive denominator')
                if z['heading_pre'].any() or not np.allclose(z['cmd_post'][:,:,2][alive],0):raise ValueError('axis heading/turn command not zero')
                yaw=np.concatenate([z['start_yaw'][None],z['yaw']],axis=0)
                if not np.isfinite(yaw).all():raise ValueError('nonfinite yaw')
                yaw=np.unwrap(yaw,axis=0);net=yaw[alive.sum(0),np.arange(64)]-yaw[0]
                if not np.allclose(net,[p['yaw_signed_accum_rad'] for p in row['per_env']],atol=3e-6):raise ValueError('yaw receipt mismatch')
                fp=fingerprint(doc,case,[float(case[3:]),0.,0.]);prefix=f'yaw/L2/{mode}/{case}/'
                add(prefix+'median_abs_rad',float(np.median(np.abs(net))),fp)
                add(prefix+'p90_abs_rad',float(np.quantile(np.abs(net),.9)),fp)
                add(prefix+'survival',int(alive[-1].sum()),fp)
    guarded('axis_v2',yaw_source)

    def stand_source(mode):
        path=folder/f'stand_{mode}/stand.json';doc=r.json(path);checked_source(doc,cp,seed)
        r.bytes(path.with_name('stand_raw.npz'),doc['raw_sha256'])
        cfg=r.json(Path(code_root)/'foothold_s2/curriculum/ex40_score_config.json')['stand']
        per=doc['per_env']
        if len(per)!=64 or [a['env'] for a in per]!=list(range(64)):raise ValueError('stand IDs')
        passed=0
        for row in per:
            good=row['valid_samples_after_1s']>0 and row['alive_at_end']
            for k,cap in [('body_speed_mean_mps','body_speed_mean_mps_max'),('abs_yaw_speed_mean_radps','abs_yaw_speed_mean_radps_max')]:
                if not finite(row[k]):raise ValueError('nonfinite stand speed')
                good &= row[k]<=cfg[cap]
            if set(row['feet'])!={'FL_foot','FR_foot','RL_foot','RR_foot'}:raise ValueError('stand foot order')
            for foot in row['feet'].values():
                for key,limit,sign in [('contact_fraction_gt1n','contact_fraction_min_by_foot',1),
                                       ('mean_fz_over_mg','mean_fz_over_mg_min_by_foot',1),('sole_gap_p95_m','sole_gap_p95_m_max_by_foot',-1)]:
                    if not finite(foot[key]):raise ValueError('nonfinite stand contact')
                    good &= sign*foot[key]>=sign*cfg[limit]
            passed+=int(good)
        fp=dict(seed=seed,seconds=doc['seconds'],skip=doc['skip_seconds'],conditions=doc['conditions'],contact=doc['contact_force_n'])
        add(f'stand/flat/{mode}/stand/success',passed,fp)
        add(f'stand/flat/{mode}/stand/speed_median_mps',float(np.median([a['body_speed_mean_mps'] for a in per])),fp)
        add(f'stand/flat/{mode}/stand/yaw_speed_median_radps',float(np.median([a['abs_yaw_speed_mean_radps'] for a in per])),fp)
    if not repeat:
        for mode in MODES:guarded('stand/'+mode,lambda m=mode:stand_source(m))
    # Published v2 values have to agree with our recomputation too.
    if 'e1_v2_cells' in score and not repeat:
        for level in (0,5):
            for mode in MODES:
                for case in ('fwd0.1','fwd0.2'):
                    key=f'low/L{level}/{mode}/{case}/R'
                    try:
                        recorded=score['e1_v2_cells']['low'][f'L{level}'][mode][case]['R']
                        if not math.isclose(recorded,s['metrics'][key],abs_tol=1e-7):raise ValueError('recorded low R mismatch')
                    except (KeyError,ValueError,TypeError) as exc:s['errors'].append(key+':'+str(exc))
    if legacy_low:s['warnings'].append('Historical G1b has GT only. PRED low cells remain missing; no GT substitution and no causal treatment claim.')
    return s

def comparison_rows(now,parent,previous):
    rows=[]
    for key in sorted(now['metrics']):
        value=now['metrics'][key];base=parent['metrics'].get(key);prev=(previous or {}).get('metrics',{}).get(key)
        comparable=(key in parent.get('fingerprints',{}) and now['fingerprints'].get(key)==parent['fingerprints'][key])
        metric=key.split('/')[-1]
        unit=('rad' if metric.endswith('_rad') else 'rad/s' if metric.endswith('_radps') or metric=='wz_mae'
              else 'm/s' if metric.endswith('_mps') or metric in ('vx_mae','vy_mae')
              else 'env' if metric in ('env_count','survival','stalled_2to4s','success') else 'ratio')
        rows.append(dict(cell=key,unit=unit,value=value,parent=base,parent_delta=value-base if finite(base) else None,
                         previous=prev,previous_delta=value-prev if finite(prev) else None,
                         parent_conditions_match=comparable))
    return rows

def comparisons_by_mode(rows):
    """Put independent GT/PRED values beside the off-mode record, without pooling."""
    grouped={}
    for row in rows:
        suite,level,mode,case,metric=row['cell'].split('/')
        if mode not in MODES:raise ValueError('unknown comparison mode: '+mode)
        key='/'.join((suite,level,case,metric))
        group=grouped.setdefault(key,dict(cell=key,unit=row['unit'],**{m:None for m in MODES}))
        if group[mode] is not None:raise ValueError('duplicate comparison cell: '+row['cell'])
        group[mode]=row
    return [grouped[k] for k in sorted(grouped)]

def load_treatment(run_root,iteration,code_root=CODE):
    r=Reader();run_root=Path(run_root);code_root=Path(code_root)
    t=dict(current={},initial={},last_change=None,r6_activated_at=None,r6_raised=False,errors=[],history=[],sources=r.sources,
           prior_payload=None,plan_sha256=None,run_root=str(run_root),readback='configured_manifest_initial')
    try:
        startup=r.json(run_root/'startup_receipt.json');manifest=r.json(run_root/'manifest.json')
        planfile=code_root/'foothold_s2/curriculum/ex42-prep.yaml';planraw=r.bytes(planfile)
        if hashlib.sha256(planraw).hexdigest()!=startup['plan_sha256']:raise ValueError('plan SHA differs from run startup')
        plan=yaml.safe_load(planraw);t['plan_sha256']=startup['plan_sha256'];t['plan_path']=str(planfile)
        rewards=next(s['rewards'] for s in plan['stages'] if s['id']=='E1')
        actual={k:float(manifest['yaml']['env'][field]) for k,field in REWARD_FIELDS.items()}
        if set(rewards)!=set(actual):raise ValueError('plan/manifest reward keys mismatch')
        t['initial']=dict(rewards);t['current']=dict(rewards)
        t['checkpoint_hashes']=manifest['checkpoints']
        t['parent_checkpoint_sha256']=startup['parent']['checkpoint_sha256']
        active=(iteration-1)//250 if iteration else 0
        past=dict(schema='ex42-segment-adjust/1',stage_id='E1',plan_sha256=t['plan_sha256'],segments={})
        # First segment b0 has no separate readback; this limitation remains visible.
        for index in range(1,active+1):
            path=run_root/f'segment_commands_b{index}.json';rec=r.json(path)
            if rec['plan_sha256']!=t['plan_sha256'] or rec['boundary_index']!=index or rec['stage_id']!='E1':raise ValueError('segment receipt identity mismatch')
            wanted=rec['rewards']['values']
            for rank in (0,1):
                back=r.json(run_root/f'segment_rewards_b{index}_rank{rank}.json')
                if back['plan_sha256']!=t['plan_sha256'] or back['boundary_index']!=index or back['live']!=wanted:
                    raise ValueError('rank reward readback mismatch')
            changed=[k for k in REWARD_FIELDS if wanted[k]!=t['current'][k]]
            if changed:
                change=dict(iteration=index*250,before=dict(t['current']),after=dict(wanted),fields=changed)
                t['history'].append(change);t['last_change']=change
                if t['current']['slow_track']==0 and wanted['slow_track']>0:t['r6_activated_at']=index*250
                if wanted['slow_track']>=.3:t['r6_raised']=True
            t['current']=dict(wanted);t['readback']='both_rank_reward_manager_receipts'
            # Actual receipts embed effective entries, not the adjustment file path.
            for field,entry in [('commands',rec),('rewards',rec['rewards']),('low_forward_fraction',rec.get('low_forward_fraction') or {})]:
                entry_index=entry.get('entry')
                if entry_index is None:continue
                key=str(entry_index)
                row=past['segments'].setdefault(key,{k:entry.get(k) for k in ('decided_at','reason','evidence')})
                value=rec['commands'] if field=='commands' else entry['values'] if field=='rewards' else entry['value']
                if field in row and row[field]!=value:raise ValueError('past receipt rewrites an applied entry')
                row[field]=value
        t['prior_payload']=past if past['segments'] else None
        if actual not in (t['initial'],t['current']):raise ValueError('manifest reward values match neither initial nor effective segment')
        limits=yaml.safe_load(r.bytes(code_root/'foothold_s2/curriculum/ex42-reward-adjust-limits.yaml'))
        for k,v in t['current'].items():
            if not finite(v) or not limits['cells'][k][0]<=v<=limits['cells'][k][1]:raise ValueError('reward outside limits: '+k)
    except (OSError,KeyError,ValueError,TypeError,StopIteration) as exc:t['errors'].append(str(exc))
    return t

def make_adjustment(decision,treatment,iteration,evidence):
    if not decision['changes'] or iteration<250:return None
    import copy
    d=copy.deepcopy(treatment.get('prior_payload')) or dict(schema='ex42-segment-adjust/1',stage_id='E1',plan_sha256=treatment['plan_sha256'],segments={})
    d['segments'][str(iteration//250)]=dict(decided_at='DRAFT '+datetime.now().astimezone().isoformat(),
       reason=decision['rule']+' · '+' '.join(decision['notes']),evidence=evidence,
       rewards={**treatment['current'],**decision['changes']})
    return d

def load_gait(path,checkpoint):
    if path is None:return None
    r=Reader();out={'valid':False,'valid_conditions':False,'issues':[],'sources':r.sources}
    try:
        d=r.json(path)
        if (d.get('format')!='analyst-r5-contact-evidence/1' or d.get('checkpoint_sha256')!=checkpoint or
            d.get('contact_definition')!='norm_Fxyz_gt_1N' or d.get('window_seconds')!=[1,6] or d.get('dt')!=.02):
            raise ValueError('R5 contact identity or definition differs')
        if set(d['feet'])!={'FL','FR','RL','RR'}:raise ValueError('four feet required')
        for foot in d['feet'].values():
            if foot['complete_intervals']<20 or foot['contributing_envs']<16:raise ValueError('insufficient foot events/envs')
            for field in ('single_sample_fraction','height_median_m','drag_fraction','negative_fraction_at_0p5'):
                if not finite(foot[field]):raise ValueError('R5 metric missing')
            if foot['negative_fraction_at_0p5']<=.5:raise ValueError('short-interval premise unconfirmed')
        if not d['sources']:raise ValueError('R5 raw sources absent')
        for source in d['sources']:r.bytes(source['path'],source['sha256'])
        out.update(valid=True,valid_conditions=True,contact_definition=d['contact_definition'])
    except (OSError,KeyError,ValueError,TypeError) as exc:out['issues'].append(str(exc))
    return out

def run(score,parent,run_root,code_root,out,iteration=None,previous=None,earlier=None,legacy_low=None,gait=None,historical=False):
    out=Path(out).resolve();run_root=Path(run_root).resolve();score=Path(score);parent=Path(parent)
    # Deliberately stronger than rejecting only this run: no writes anywhere in s2_lab.
    if out.is_relative_to(run_root) or any(x in out.parts for x in ('s2_lab','ex42-launch-e1-v19')):
        raise ValueError('output must be outside training/evaluation/frozen-source trees')
    now=load_snapshot(score,iteration,code_root,legacy_low);base=load_snapshot(parent,0,code_root)
    n=now['iteration'] or 0
    if n<0 or (n%250 and not historical):
        now['errors'].append('not_a_250_update_boundary')
    if previous is None and n>250:
        p=score.parent.parent/f'm{n-250}/ex42_score.json'
        if p.is_file():previous=p
    if earlier is None and n>500:
        p=score.parent.parent/f'm{n-500}/ex42_score.json'
        if p.is_file():earlier=p
    def history(path):
        if path is None:return None
        oldn=int(re.fullmatch('m([0-9]+)',Path(path).parent.name)[1])
        low=Path(legacy_low).parent/f'm{oldn}seg' if legacy_low else None
        return load_snapshot(path,oldn,code_root,low)
    prev=history(previous) if previous else base if n==250 else None
    prior=history(earlier)
    t=load_treatment(run_root,250 if historical else n,code_root)
    if not historical and n>0:
        expected=t.get('checkpoint_hashes',{}).get(f'model_{n}.pt')
        if isinstance(expected,dict):expected=expected.get('sha256')
        if expected!=now.get('checkpoint_sha256'):
            now['errors'].append('checkpoint not pinned to this run manifest at requested local iteration')
        if now.get('plan_sha256')!=t['plan_sha256']:
            now['errors'].append('score execution plan differs from this run')
        if t.get('parent_checkpoint_sha256')!=base.get('checkpoint_sha256'):
            now['errors'].append('baseline is not this runs pinned parent')
        for snap in (prev,prior):
            if not snap or snap['iteration']==0:continue
            value=t.get('checkpoint_hashes',{}).get(f'model_{snap["iteration"]}.pt')
            if isinstance(value,dict):value=value.get('sha256')
            if value!=snap.get('checkpoint_sha256') or snap.get('plan_sha256')!=t['plan_sha256']:
                snap['errors'].append('history checkpoint or plan differs from run manifest')
    if t['last_change']:
        anchor_n=t['last_change']['iteration'];p=score.parent.parent/f'm{anchor_n}/ex42_score.json'
        if p.is_file():t['anchor']=load_snapshot(p,anchor_n,code_root)
    for snap in (now,prev):
        if not snap or not snap.get('checkpoint_sha256'):continue
        # Repeat bundles are already produced by the evaluator near thresholds.
        for seed in (7,13):
            root=Path(snap['score_path']).parent/f'e1_v2_repeat_seed{seed}'
            if not root.is_dir():continue
            rep=load_repeat(root,snap['checkpoint_sha256'],seed,code_root)
            snap['sources'].update(rep['sources'])
            if not rep['errors']:snap['repeats'][str(seed)]=rep['metrics']
            else:snap['warnings'].append({'repeat_seed':seed,'errors':rep['errors']})
    comparisons=comparison_rows(now,base,prev)
    mode_comparisons=comparisons_by_mode(comparisons)
    mismatches=[r['cell'] for r in comparisons if r['parent'] is not None and not r['parent_conditions_match']]
    now['comparable']=not mismatches
    if historical:
        # Counterfactual rule replay, explicitly on current approved initial rewards.
        now['comparable']=True
        now['warnings'].append('Historical replay uses current initial treatment, not the treatment actually applied in cmd7seg.')
    decision=decide(now,base,prev,prior,t,load_gait(gait,now.get('checkpoint_sha256')))
    if n==0 and not now['errors']:
        decision.update(rule='BASELINE_ONLY',changes={},next_segment='NOT_A_BOUNDARY')
        decision['notes'].append('부모 자체 대조만. 실제 경계 처방이 아님.')
    draft=make_adjustment(decision,t,n,str(out/'report.json'))
    validation=None
    if draft:
        try:
            sys.path.insert(0,str(code_root))
            from foothold_s2.commands.ex42_segment_adjust import resolve, reward_limits
            plan=SimpleNamespace(sha256=t['plan_sha256'],document=yaml.safe_load(Path(t['plan_path']).read_text()))
            resolve(plan,'E1',draft,n//250,reward_limits(Path(code_root)/'foothold_s2/curriculum/ex42-reward-adjust-limits.yaml'))
            validation='consumer_resolve_pass'
        except (ValueError,KeyError,TypeError) as exc:
            validation='consumer_rejected: '+str(exc);draft=None
    result=dict(format=FORMAT,created_at=datetime.now().astimezone().isoformat(),decision=decision,
                iteration=n,current=now,parent=base,previous=prev,earlier=prior,treatment=t,
                parent_condition_mismatches=mismatches,comparisons=comparisons,
                mode_comparisons=mode_comparisons,
                historical_counterfactual=historical,consumer_validation=validation)
    out.mkdir(parents=True,exist_ok=True)
    write=lambda name,obj:(out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    write('report.json',result)
    write('adjustment.draft.json',dict(format='analyst-adjustment-review-only/1',apply_ready=False,
          historical_counterfactual=historical,consumer_validation=validation,payload=draft))
    with (out/'cells.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['cell','unit','value','parent','parent_delta','previous','previous_delta','parent_conditions_match'],lineterminator='\n')
        writer.writeheader();writer.writerows(comparisons)
    numeric=('value','parent','parent_delta','previous','previous_delta')
    with (out/'mode_cells.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['cell','unit']+[m+'_'+k for m in MODES for k in numeric],lineterminator='\n')
        writer.writeheader()
        for group in mode_comparisons:
            writer.writerow(dict(cell=group['cell'],unit=group['unit'],**{
                m+'_'+k:(group[m] or {}).get(k) for m in MODES for k in numeric}))
    def show(x):return '미확인' if x is None else f'{x:.6f}' if isinstance(x,float) else str(x)
    changes=' · '.join(f'{k} {t["current"].get(k)}→{v}' for k,v in decision['changes'].items()) or '현재 값 유지'
    one=f'm{n}: {decision["rule"]} · {changes} · 다음 구간 {decision["next_segment"]} · 초안만'
    text=['# E1 경계 규칙 판독',f'> 분류: A/평가',f'> 작성: analyst-lx · {datetime.now():%Y-%m-%d %H:%M}',
          '> 근거: 원장 73abb340 · 15:03 R2/R3/R4 · 04f50b4f R6 정정 · 0a5c1629 R5 GT·PRED 정정',
          '> 요지: '+one,'> 상태: CPU 원자료 재계산 · 실행 설정 미적용','',one,'',
          f'기존 유지: {now["maintenance"]}; 전체 졸업: {now["overall"]}. 둘은 별개다.',
          f'지도별 유지: {now["maintenance_modes"]}. GT·PRED 판정, 지도 끔 기록 전용.',
          '되돌림은 처방 직전 고정 기준과 같은 칸 두 경계를 비교한다. parent_delta와 previous_delta는 참고 열이다.',
          f'현재 설정 근거: {t["readback"]}. 초기 manifest는 RewardManager 실시간 재측정이 아니다.',
          f'소비 형식 검사: {validation}. 역사 재생: {historical}.',
          'R1·옛 R5 폐기. R5는 동일 접촉 정의 자료 없으면 보류. 시드·모드·레벨은 합치지 않는다.','',
          '발동: '+', '.join(decision['triggered']),'',*decision['notes'],'',
          '각 지도 열: 현재; 부모(차이); 직전(차이). 없는 지도 값은 미확인으로 남긴다.',
          '| 칸 | 단위 | GT 판정 | PRED 판정 | 지도 끔 기록 |',
          '|---|---|---|---|---|']
    def mode_show(row):
        if row is None:return '미확인'
        return (f'{show(row["value"])}; 부모 {show(row["parent"])} (Δ {show(row["parent_delta"])}); '
                f'직전 {show(row["previous"])} (Δ {show(row["previous_delta"])})')
    for group in mode_comparisons:
        text.append('| '+' | '.join([group['cell'],group['unit'],*(mode_show(group[m]) for m in MODES)])+' |')
    text+=['','입력 오류: '+json.dumps(now['errors']+t['errors'],ensure_ascii=False),
           '주의: '+json.dumps(now['warnings'],ensure_ascii=False),'',
           '원자료별 SHA와 고정 기준의 경계별 악화 항목은 report.json에 있다. 조정 JSON의 payload는 초안이며 이 도구가 적용하지 않는다.']
    (out/'REPORT.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    (out/'next_segment.txt').write_text(one+'\n',encoding='utf-8')
    return result

def load_repeat(root,checkpoint,seed,code_root):
    """Repeat evaluation has no score.json. Use the canonical CPU cell reader."""
    r=Reader();out=dict(metrics={},errors=[],sources=r.sources)
    try:
        sys.path.insert(0,str(code_root))
        from foothold_s2.ex42_e1_v2 import measure_cells
        cells=measure_cells(root,checkpoint,seed)
        for key,item in cells['sources'].items():r.bytes(item['path'],item['sha256'])
        for level in ('L0','L5'):
            for mode,rows in cells['low'][level].items():
                if not isinstance(rows,dict):raise ValueError('repeat low incomplete')
                for case,row in rows.items():
                    if not isinstance(row,dict):raise ValueError('repeat low incomplete')
                    r.bytes(row['raw_file'],row['raw_sha256'])
                    out['metrics'][f'low/{level}/{mode}/{case}/R']=row['R']
        for mode,rows in cells['yaw'].items():
            for case,row in rows.items():
                r.bytes(row['raw_file'],row['raw_sha256'])
                for metric in ('median_abs_rad','p90_abs_rad'):out['metrics'][f'yaw/L2/{mode}/{case}/{metric}']=row[metric]
    except (OSError,ValueError,KeyError,TypeError,BadZipFile,EOFError,AttributeError) as exc:out['errors'].append(str(exc))
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--score',type=Path,required=True);p.add_argument('--parent',type=Path,default=PARENT)
    p.add_argument('--run-root',type=Path,default=RUN);p.add_argument('--code-root',type=Path,default=CODE)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--iteration',type=int)
    p.add_argument('--previous',type=Path);p.add_argument('--earlier',type=Path)
    p.add_argument('--legacy-low',type=Path);p.add_argument('--gait',type=Path)
    p.add_argument('--historical',action='store_true')
    a=p.parse_args();result=run(a.score,a.parent,a.run_root,a.code_root,a.out,a.iteration,a.previous,a.earlier,a.legacy_low,a.gait,a.historical)
    print((a.out/'next_segment.txt').read_text().strip())
    return 2 if result['decision']['rule']=='EVIDENCE_HOLD' else 0

if __name__=='__main__':raise SystemExit(main())
