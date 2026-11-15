"""EX-42 task evidence, independent of Kit and of training promotion.

CG 368d03e2:299,316,387,394. Cross-direction statistic: lead 11/11 15:05,
explicit assumption. A policy fall stays in the denominator. Reset-invalid
rows alone may be excluded from count thresholds, never from the 64-row
projected-distance statistic. No task is inferred from another map mode.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

MODES = ('eval_gt', 'eval_pred', 'probe_prop_only')
TASKS = ('tile_end_reach', 'box_center_pass', 'surface_hold',
         'cross_dir_half_flat', 'push_record', 'tunnel_exit_no_contact')


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def held(mask, steps):
    """A contiguous interval, not total samples spread across the episode."""
    run=np.zeros(mask.shape[1],int); passed=np.zeros(mask.shape[1],bool)
    for row in mask:
        run=np.where(row,run+1,0);passed |= run>=steps
    return passed


def _trace(trace, spec):
    arrays={key:np.asarray(trace[key]) for key in ('root_pos_w','foot_pos_w','contact',
        'alive','reset_valid','tile_offset_w','initial_root_pos_w','initial_yaw_rad',
        'body_vel_b','command_b','forbidden_contact')}
    t,n=arrays['alive'].shape
    shapes={'root_pos_w':(t,n,3),'foot_pos_w':(t,n,4,3),'contact':(t,n,4),
        'alive':(t,n),'reset_valid':(n,),'tile_offset_w':(n,3),
        'initial_root_pos_w':(n,3),'initial_yaw_rad':(n,),
        'body_vel_b':(t,n,3),'command_b':(t,n,3),'forbidden_contact':(t,n)}
    if n!=64 or t!=spec['steps'] or t<2: raise ValueError('task requires 64 envs and exact steps')
    for key,a in arrays.items():
        if a.shape!=shapes[key] or not np.isfinite(a).all():
            raise ValueError(f'{key} shape or finite values invalid')
    for key in ('alive','contact','reset_valid','forbidden_contact'):
        if arrays[key].dtype!=bool: raise ValueError(f'{key} must be boolean')
    if np.any(arrays['alive'][1:] & ~arrays['alive'][:-1]):
        raise ValueError('alive resurrected: a reset cannot start a second trial')
    if spec['task'] not in TASKS or spec['map_mode'] not in MODES:
        raise ValueError('unknown task or map mode')
    if spec['role'] not in ('judge','record_only'): raise ValueError('unknown role')
    if spec['task']=='push_record' and spec['role']!='record_only':
        raise ValueError('DR push cannot enter a judgment cell')
    dt=spec['dt']
    if not math.isfinite(dt) or dt<=0: raise ValueError('invalid policy dt')
    command=np.asarray(spec['command_b'],float)
    if command.shape!=(3,) or not np.isfinite(command).all(): raise ValueError('invalid command')
    expected=np.broadcast_to(command,(t,n,3)).copy()
    if spec.get('stop_at_goal'):
        stopped=np.asarray(trace.get('command_stopped',np.zeros((t,n),bool)))
        if stopped.shape!=(t,n) or stopped.dtype!=bool or np.any(stopped[:-1]&~stopped[1:]):
            raise ValueError('invalid completion stop phase')
        expected[stopped]=0
        arrays['command_stopped']=stopped
    if not np.allclose(arrays['command_b'],expected,atol=1e-6,rtol=0):
        raise ValueError('actual command differs from requested command')
    return arrays


def summarize(trace, *, spec, anchors):
    """Recompute one case from per-step data; no acceptance of caller's counts."""
    a=_trace(trace,spec); alive=a['alive']; valid=a['reset_valid'];n=64
    root=a['root_pos_w']-a['tile_offset_w'][None]
    feet=a['foot_pos_w']-a['tile_offset_w'][None,:,None]
    survives=alive[-1]
    # Freeze at last pre-reset sample. Never measure the teleported new episode.
    final=a['initial_root_pos_w'].copy()
    for step in range(len(alive)): final=np.where(alive[step,:,None],a['root_pos_w'][step],final)
    vx,vy=spec['command_b'][:2]; speed=math.hypot(vx,vy)
    yaw=a['initial_yaw_rad']
    direction=np.stack((np.cos(yaw)*vx-np.sin(yaw)*vy,np.sin(yaw)*vx+np.cos(yaw)*vy),axis=-1)
    projection=np.sum((final[:,:2]-a['initial_root_pos_w'][:,:2])*direction,axis=-1)/speed if speed>0 else np.zeros(n)
    passed=np.zeros(n,bool); center=np.zeros(n,bool);bypass=np.zeros(n,bool)
    hold=math.ceil(float(spec.get('hold_s',.5))/spec['dt'])
    if hold<1: raise ValueError('hold duration must be positive')
    task=spec['task']
    if task not in ('cross_dir_half_flat','push_record'):
        x=anchors['exit_x'];lo,hi=anchors['exit_bounds_y']
        if not (math.isfinite(x) and math.isfinite(lo) and math.isfinite(hi) and hi>lo):
            raise ValueError('invalid exit geometry')
        inside=(root[...,0]>=x)&(root[...,0]<=anchors.get('tile_end_x',x+2.))&(root[...,1]>=lo)&(root[...,1]<=hi)
        if spec.get('stop_at_goal'):
            stops=a['command_stopped'];new=stops & ~np.vstack((np.zeros((1,n),bool),stops[:-1]))
            previous_inside=np.vstack((np.zeros((1,n),bool),inside[:-1]))
            if np.any(new&~previous_inside):raise ValueError('stop command before geometry goal')
        support=a['contact'].any(-1)
        exit_ok=inside&support&alive
        if task=='surface_hold':
            tolerance=spec['foot_height_tolerance_m']
            if not 0<tolerance<.2: raise ValueError('support height tolerance invalid')
            top=anchors.get('support_floor_m',anchors.get('center_top_m'))
            exit_ok &= np.any(a['contact'] & (np.abs(feet[...,2]-top)<=tolerance),axis=-1)
        if task=='box_center_pass':
            x0,x1,y0,y1=anchors['center_bounds_xy']
            within=(root[...,0]>=x0)&(root[...,0]<=x1)&(root[...,1]>=y0)&(root[...,1]<=y1)
            foot_top=(a['contact']&(feet[...,0]>=x0)&(feet[...,0]<=x1)&(feet[...,1]>=y0)&(feet[...,1]<=y1)&
                      (np.abs(feet[...,2]-anchors['center_top_m'])<=spec['foot_height_tolerance_m'])).any(-1)
            visit=within&foot_top&alive
            center=visit.any(0)
            # Must have physically visited top before exiting, not airborne over it.
            seen=np.maximum.accumulate(visit,axis=0)
            passed=held(exit_ok&seen,hold)
            bypass=held((root[...,0]>=x)&alive&support,hold)&~center
        else:
            passed=held(exit_ok,hold)
        if task=='tunnel_exit_no_contact': passed &= ~a['forbidden_contact'].any(0)
    passed &= survives&valid
    rows=[{'env':i,'valid':bool(valid[i]),'survival':bool(survives[i]),'success':bool(passed[i]),
           'center_pass':bool(center[i]),'bypass':bool(bypass[i]),
           'projected_distance_m':float(projection[i])} for i in range(n)]
    result={'envs':n,'valid_count':int(valid.sum()),'survival_count':int((survives&valid).sum()),
        'success_count':int(passed.sum()),'per_env':rows,'projected_distance_m':projection.tolist(),
        'projection_statistic':'median of signed world projection, all 64 initial trials; freeze at first done',
        'command_b':list(spec['command_b']),'steps':spec['steps'],'dt':spec['dt'],
        'role':spec['role'],'map_mode':spec['map_mode']}
    return result


def judge_counts(row, *, valid_min=48, success_min=52, survival_min=60):
    n=row['valid_count']
    if n<valid_min: return {'judgement':'HOLD','reason':'valid_below_floor'}
    success=math.ceil(success_min*n/64);survival=math.ceil(survival_min*n/64)
    return {'judgement':'PASS' if row['success_count']>=success and row['survival_count']>=survival else 'FAIL',
            'success_threshold':success,'survival_threshold':survival}


def compare_cross_direction(row, flat, *, window_index, settings=None):
    """Lead 11/11 15:05: all-start median and D44 proportional survival count."""
    cfg=settings or {'valid_min':48,'survival_min':60,'ratio_min':.5,'judge_from_window':2}
    for key in ('checkpoint_sha256','seed','map_mode','command_b','steps','dt','envs'):
        if row.get(key)!=flat.get(key) or key not in row: raise ValueError(f'cross pair differs: {key}')
    if row['envs']!=64 or type(window_index) is not int or window_index<1: raise ValueError('invalid cross pair/window')
    for item in (row,flat):
        d=np.asarray(item['projected_distance_m'])
        if d.shape!=(64,) or not np.isfinite(d).all(): raise ValueError('64 finite cross distances required')
        if not 0<=item['survival_count']<=item['valid_count']<=64: raise ValueError('invalid cross counts')
    role='record_only' if window_index<cfg['judge_from_window'] else 'judge'
    terrain_med=float(np.median(row['projected_distance_m']));flat_med=float(np.median(flat['projected_distance_m']))
    result={'role':role,'terrain_median_m':terrain_med,'flat_median_m':flat_med,
        'ratio':terrain_med/flat_med if flat_med>0 else None,'window_index':window_index,
        'assumption':'lead 2026-11-11 15:05, signed 64-start median; proportional valid survival'}
    if min(row['valid_count'],flat['valid_count'])<cfg['valid_min'] or flat_med<=0:
        return {**result,'judgement':'HOLD','reason':'invalid_denominator_or_flat_nonpositive'}
    threshold=math.ceil(cfg['survival_min']*row['valid_count']/64)
    passed=terrain_med/flat_med>=cfg['ratio_min'] and row['survival_count']>=threshold
    return {**result,'judgement':('PASS' if passed else 'FAIL') if role=='judge' else 'RECORD',
            'survival_threshold':threshold,'criteria_met':passed}


def expanded_e_exit(rows):
    """CG:299 separate level and completed-skill evidence. Missing never PASS."""
    requirements={'slope_steep':6,'slope_steep_inv':6,'stairs_high':3,'stairs_high_inv':3}
    items={kind:('PASS' if rows.get(kind,{}).get('level',-1)>=level and
                  rows[kind].get('judgement')=='PASS' else 'HOLD') for kind,level in requirements.items()}
    return {'judgement':'PASS' if all(v=='PASS' for v in items.values()) else 'HOLD','items':items}
