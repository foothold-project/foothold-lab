"""In-memory targeted mutants. Run only after the normal CPU suite passes."""
from __future__ import annotations

from pathlib import Path
import sys
import types
import torch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from test_s2_step15_foot import fixture


def mutated(filename,old,new,name):
    source=(HERE/filename).read_text(encoding='utf-8')
    if source.count(old)!=1:raise RuntimeError('mutation anchor: '+name)
    module=types.ModuleType('mutant_'+name)
    sys.modules[module.__name__]=module
    exec(compile(source.replace(old,new),str(HERE/filename),'exec'),module.__dict__)
    return module


def fails_value(actual,expected,label):
    assert actual==expected, f'{label}: expected {expected}, got {actual}'


def mutants():
    checks=[]
    m=mutated('s2_foot_reward.py','DROP_M = 0.20','DROP_M = 0.19','drop_boundary')
    p,h,s,f=fixture();h[0,0,1]=-.195
    checks.append(('drop_boundary','20cm_strict',lambda m=m,p=p,h=h,s=s,f=f: fails_value(m.feet_center_any9_v1(p,h,s,f).cost.tolist(),[0.],'20cm_strict')))

    m=mutated('s2_foot_reward.py','CONTACT_N = 1.0','CONTACT_N = 0.999','force_boundary')
    p,h,s,f=fixture();h[0,0,1]=-.3;f[0,0,2]=1.
    checks.append(('force_boundary','1N_strict',lambda m=m,p=p,h=h,s=s,f=f: fails_value(m.feet_center_any9_v1(p,h,s,f).cost.tolist(),[0.],'1N_strict')))

    m=mutated('s2_foot_reward.py','cardinal.to(p_f.dtype) + 2 * diagonal.to(p_f.dtype)',
              '2 * cardinal.to(p_f.dtype) + 2 * diagonal.to(p_f.dtype)','cardinal_weight')
    p,h,s,f=fixture();h[0,0,1]=-.3
    checks.append(('cardinal_weight','cardinal_one',lambda m=m,p=p,h=h,s=s,f=f: fails_value(m.feet_center_any9_v1(p,h,s,f).cost.tolist(),[1.],'cardinal_one')))

    m=mutated('s2_foot_reward.py','cardinal.to(p_f.dtype) + 2 * diagonal.to(p_f.dtype)',
              'cardinal.to(p_f.dtype) + diagonal.to(p_f.dtype)','diagonal_weight')
    p,h,s,f=fixture();h[0,0,0]=-.3
    checks.append(('diagonal_weight','diagonal_two',lambda m=m,p=p,h=h,s=s,f=f: fails_value(m.feet_center_any9_v1(p,h,s,f).cost.tolist(),[2.],'diagonal_two')))

    m=mutated('s2_foot_reward.py','per_foot = torch.where(central, torch.full_like(per_foot, 3), per_foot)',
              'per_foot = per_foot','central_override')
    p,h,s,f=fixture();h[0,0,4]=-.3
    checks.append(('central_override','center_three',lambda m=m,p=p,h=h,s=s,f=f: fails_value(m.feet_center_any9_v1(p,h,s,f).cost.tolist(),[3.],'center_three')))

    m=mutated('s2_foot_reward.py','danger = (status == NO_HIT) | ((status == HIT) & (heights < threshold))',
              'danger = (status == HIT) & (heights < threshold)','no_hit_void')
    p,h,s,f=fixture();s[0,0,1]=m.NO_HIT;h[0,0,1]=float('inf')
    checks.append(('no_hit_void','valid_no_hit_cost',lambda m=m,p=p,h=h,s=s,f=f: fails_value(m.feet_center_any9_v1(p,h,s,f).cost.tolist(),[1.],'valid_no_hit_cost')))

    m=mutated('s2_foot_reward.py','threshold = p_f[..., 2].unsqueeze(-1) - RADIUS_M - DROP_M',
              'threshold = torch.full_like(heights, -RADIUS_M-DROP_M)','world_zero_threshold')
    p,h,s,f=fixture();p[...,2]+=10;h+=10;h[0,0,1]=9.7
    checks.append(('world_zero_threshold','translated_height',lambda m=m,p=p,h=h,s=s,f=f: fails_value(m.feet_center_any9_v1(p,h,s,f).cost.tolist(),[1.],'translated_height')))

    m=mutated('s2_foot_query.py','starts[..., 2] += RAY_START_ABOVE_FOOT_M',
              'starts[..., 2] += 2*RAY_START_ABOVE_FOOT_M','double_ray_offset')
    p,_,_,_=fixture()
    checks.append(('double_ray_offset','ray_start_20m',lambda m=m,p=p: fails_value(round(float(m.make_ray_starts(p,.05)[0,0,4,2]),3),20.022,'ray_start_20m')))

    m=mutated('s2_foot_query.py','if not bool((frame_id > self.frame_id).all()):',
              'if False:','stale_frame')
    p,_,_,f=fixture();hits=m.make_ray_starts(p,.05);hits[...,2]=0
    tracker=m.FootQueryTracker(1,.05)
    kw=dict(centers=p,forces=f,hits=hits,frame_id=torch.tensor([0]),episode_id=torch.tensor([0]),
            tile_origin=torch.zeros(1,3),tile_size_xy=(4.,4.),mesh_path=m.MESH_PATH)
    tracker.capture(**kw)
    def stale(tracker=tracker,kw=kw):
        try:tracker.capture(**kw)
        except ValueError as ex:
            if 'foot_frame_stale' in str(ex):return
        raise AssertionError('stale_frame_rejected: expected foot_frame_stale')
    checks.append(('stale_frame','stale_frame_rejected',stale))

    m=mutated('s2_foot_query.py','if not bool((finite | no_hit).all()):',
              'if False:','partial_inf')
    p,_,_,f=fixture();hits=m.make_ray_starts(p,.05);hits[...,2]=0;hits[0,0,1,2]=float('inf')
    tracker=m.FootQueryTracker(1,.05)
    def partial(tracker=tracker,p=p,f=f,hits=hits,m=m):
        try:tracker.capture(centers=p,forces=f,hits=hits,frame_id=torch.tensor([0]),
            episode_id=torch.tensor([0]),tile_origin=torch.zeros(1,3),
            tile_size_xy=(4.,4.),mesh_path=m.MESH_PATH)
        except ValueError as ex:
            if 'foot_hit_invalid' in str(ex):return
        raise AssertionError('partial_inf_rejected: expected foot_hit_invalid')
    checks.append(('partial_inf','partial_inf_rejected',partial))
    return checks


if __name__=='__main__':
    caught=0
    checks=mutants()
    for name,want,check in checks:
        try:check()
        except AssertionError as ex:
            if str(ex).split(':',1)[0]!=want:raise
            print(f'CAUGHT {name} first_FAIL={want} want={want} detail={ex}')
            caught+=1
        else:raise RuntimeError('SURVIVED '+name)
    print(f'MUTANTS {caught}/{len(checks)} CAUGHT')
