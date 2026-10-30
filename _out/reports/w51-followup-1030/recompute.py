"""Read-only CPU W51 audit. Writes analysis artifacts only, never evaluation inputs."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path('C:/Users/AI-WS01/s2_lab/basic_gait_runs/eval_actuator/w51_followup_20261030')
OUT = Path(__file__).resolve().parent
POLICIES = ('ex38', 'ex39b')
VARIANTS = ('w51_base', 'w51_push', 'w51_noise2', 'w51_combo4', 'w51_all6')
MAPS = ('eval_gt', 'eval_pred', 'probe_prop_only')
NOISE = dict(base_ang_vel=.2, projected_gravity=.05, joint_pos=.01, joint_vel=1.5)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def finite_median(values):
    vals = [float(v) for v in values if v is not None and np.isfinite(v)]
    return float(np.median(vals)) if vals else None

def dist_alive(vx, alive, dt):
    return np.sum(vx * alive, axis=0) * dt

def self_check():
    vx = np.array([[1.,2.],[1.,2.],[1.,200.]])
    alive = np.array([[True,True],[True,True],[True,False]])
    np.testing.assert_allclose(dist_alive(vx, alive, .02), [.06,.08])
    assert finite_median([None, 1, 3]) == 2

def read_run(policy, variant, rep):
    path = ROOT/policy/variant/f'rep{rep}'/'map_modes.json'
    d = json.loads(path.read_text(encoding='utf-8'))
    assert d['run_identity']['gpu_index'] == 1
    assert d['run_identity']['code_dirty_files'] == 0
    assert d['run_identity']['checkpoint_sha256'] == d['checkpoint_sha256']
    assert d['envs'] == 64 and d['steps'] == 300
    assert set(d['modes']) == set(MAPS) and len(d['env_arrays']) == 39
    assert len(d['commands']) == 13
    assert d['w51']['config']['option'] == variant
    assert d['fixed_terrain']['levels'] == [1]
    nscale = 2. if variant == 'w51_noise2' else 1.
    rn = d['w51']['runtime_policy_noise']
    assert set(rn) == set(NOISE)
    for k, a in NOISE.items():
        np.testing.assert_allclose([rn[k]['n_min'],rn[k]['n_max']],[-a*nscale,a*nscale])
        assert rn[k]['operation'] == 'add'
    physical = d['w51']['physical_startup']
    push = d['w51']['pushes']
    has_push = variant in ('w51_push','w51_all6')
    assert len(push) == (39 if has_push else 0)
    rows, terrain_rows, inputs = [], [], [dict(path=str(path),sha256=sha(path))]
    for mode in MAPS:
        assert set(d['modes'][mode]) == set(d['commands'])
        for cmd, row in d['modes'][mode].items():
            key = mode+'/'+cmd
            assert row['env_count'] == 64 and len(row['per_env']) == 64
            total = row['policy_steps_x_envs']
            assert total == 64*300 and row['gt_used'] == (total if mode=='eval_gt' else 0)
            assert d['terrain_hash'][key] == d['fixed_terrain']['assignment_sha256']
            ap = path.parent/d['env_arrays'][key]
            inputs.append(dict(path=str(ap),sha256=sha(ap)))
            with np.load(ap,allow_pickle=False) as a:
                assert a['vx'].shape == a['alive'].shape == (300,64)
                assert np.isfinite(a['vx']).all()
                dt = float(a['dt'])
                np.testing.assert_allclose(dt,.02)
                recomputed_dist = dist_alive(a['vx'],a['alive'],dt)
                np.testing.assert_allclose(recomputed_dist,a['body_vx_integral_m'],rtol=1e-6,atol=1e-6)
                np.testing.assert_allclose(np.median(recomputed_dist),row['body_vx_integral_median_m'],rtol=1e-6,atol=1e-6)
                alive_n = int(np.count_nonzero(a['alive'][-1]))
                assert alive_n == row['alive_envs_at_end'] == sum(x['alive_at_end'] for x in row['per_env'])
                assert np.array_equal(a['alive'].sum(0),a['alive_steps'])
                assert np.all(a['terrain_level'] == 1)
                maperr = finite_median(a['map_err_inrange_mean_cm'])
                sat = finite_median(a['map_err_gt_sat_frac_mean'])
            per = row['per_env']
            ratios = [x['yaw_follow_mean_alive'] for x in per]
            if abs(row['command'][2]) > 0:
                # Persisted env means are sufficient for this aggregate, not raw-wz replay.
                ratios = [0 if v is None else v for v in ratios]
                np.testing.assert_allclose(np.median(ratios),row['yaw_follow_median'],rtol=1e-5,atol=1e-6)
            if has_push:
                pp = push[key]
                assert [x['step'] for x in pp] == [100,200]
                for p in pp:
                    b=np.asarray(p['before']);t=np.asarray(p['target']);ac=np.asarray(p['actual']);de=np.asarray(p['delta_xy'])
                    assert p['max_abs_readback_error'] <= 1e-5
                    if len(b):
                        np.testing.assert_allclose(t[:,:2]-b[:,:2],de,atol=2e-7)
                        np.testing.assert_allclose(t[:,2:],b[:,2:],atol=0)
                        np.testing.assert_allclose(t,ac,atol=1e-5)
                        assert np.max(np.abs(de)) <= .5
            rec=dict(policy=policy,variant=variant,rep=rep,map_mode=mode,command=cmd,
                     alive_n=alive_n,env_n=64,body_vx_integral_median_m=row['body_vx_integral_median_m'],
                     cmd_projection_median_m=finite_median(x['command_xy_projection_integral_m'] for x in per),
                     yaw_follow_median=finite_median(ratios) if abs(row['command'][2])>0 else None,
                     vx_mae_env_median_mps=finite_median(x['vx_abs_error_mean_alive_mps'] for x in per),
                     vy_mae_env_median_mps=finite_median(x['vy_abs_error_mean_alive_mps'] for x in per),
                     wz_mae_env_median_radps=finite_median(x['wz_abs_error_mean_alive_radps'] for x in per),
                     xy_speed_env_median_mps=finite_median(x['body_xy_speed_mean_alive_mps'] for x in per),
                     tilt_mean_alive_rad=row['tilt_rad_mean_alive'],stationary_fraction_2to4s=row['stationary_fraction_2to4s'],
                     map_error_env_median_cm=maperr,gt_sat_env_median_fraction=sat,source=str(path))
            rows.append(rec)
            for kind in sorted({x['kind'] for x in per}):
                pp=[x for x in per if x['kind']==kind]
                terrain_rows.append(dict(policy=policy,variant=variant,rep=rep,map_mode=mode,command=cmd,
                    terrain=kind,level=1,env_n=len(pp),alive_n=sum(x['alive_at_end'] for x in pp),
                    cmd_projection_median_m=finite_median(x['command_xy_projection_integral_m'] for x in pp),
                    yaw_follow_median=finite_median(x['yaw_follow_mean_alive'] for x in pp),
                    vx_mae_env_median_mps=finite_median(x['vx_abs_error_mean_alive_mps'] for x in pp),
                    vy_mae_env_median_mps=finite_median(x['vy_abs_error_mean_alive_mps'] for x in pp),
                    wz_mae_env_median_radps=finite_median(x['wz_abs_error_mean_alive_radps'] for x in pp)))
    return d, rows, terrain_rows, inputs

def write_csv(name, rows):
    if rows:
        with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    self_check();OUT.mkdir(exist_ok=True,parents=True)
    jobs=[(p,v,r) for p in POLICIES for v,r in [('w51_base',1),('w51_base',2),('w51_push',1),('w51_noise2',1),('w51_combo4',1),('w51_all6',1)]]
    missing=[];data={};rows=[];terrains=[];inputs=[]
    for key in jobs:
        p,v,r=key
        if not (ROOT/p/v/f'rep{r}'/'map_modes.json').exists():missing.append(key);continue
        d,rr,tt,ii=read_run(*key);data[key]=d;rows+=rr;terrains+=tt;inputs+=ii
    assert args.partial or not missing, f'{len(missing)} unfinished runs'
    matches=[]
    for key,d in data.items():
        parent=data[(key[0],'w51_base',1)]
        fields=dict(materials=d['w51']['physical_startup']['materials']['sha256']==parent['w51']['physical_startup']['materials']['sha256'],
                    masses=d['w51']['physical_startup']['masses']['sha256']==parent['w51']['physical_startup']['masses']['sha256'],
                    terrain_assignment=d['fixed_terrain']['assignment_sha256']==parent['fixed_terrain']['assignment_sha256'],
                    checkpoint=d['checkpoint_sha256']==parent['checkpoint_sha256'],source=d['source_sha256']==parent['source_sha256'])
        matches.append(dict(policy=key[0],variant=key[1],rep=key[2],**fields))
    comparison=[];idx={(x['policy'],x['variant'],x['rep'],x['map_mode'],x['command']):x for x in rows}
    metrics=['alive_n','body_vx_integral_median_m','cmd_projection_median_m','yaw_follow_median','vx_mae_env_median_mps','vy_mae_env_median_mps','wz_mae_env_median_radps','xy_speed_env_median_mps','tilt_mean_alive_rad','map_error_env_median_cm']
    for row in rows:
        p,v,r,mode,c=[row[k] for k in ('policy','variant','rep','map_mode','command')]
        b1=idx[(p,'w51_base',1,mode,c)];b2=idx.get((p,'w51_base',2,mode,c))
        if v=='w51_base' or b2 is None:continue
        for metric in metrics:
            if any(x[metric] is None for x in (row,b1,b2)):continue
            base=(b1[metric]+b2[metric])/2
            diff=row[metric]-base;width=abs(b1[metric]-b2[metric])
            comparison.append(dict(policy=p,variant=v,map_mode=mode,command=c,metric=metric,
                base_rep1=b1[metric],base_rep2=b2[metric],base_midpoint=base,value=row[metric],delta_from_base_midpoint=diff,
                observed_repeat_difference=width,abs_delta_gt_repeat_difference=abs(diff)>width))
    audit=dict(complete=not missing,runs=len(data),expected_runs=12,cells=len(rows),missing=missing,
               condition_matches=matches,all_common_conditions_match=all(all(x[k] for k in ('materials','masses','terrain_assignment','checkpoint','source')) for x in matches),
               data_checks='64env/300steps, maps3x13, first-episode vx/alive recompute, map consumption, noise readback, push readback',
               limits='Yaw uses persisted per-env means, no independent raw-wz replay; tilt is persisted pooled mean. No gait/feet/video. Baseline repeat difference is observed width, not a statistical bound.',inputs=inputs)
    write_csv('cells.csv',rows);write_csv('terrain_cells.csv',terrains);write_csv('differences.csv',comparison)
    (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:audit[k] for k in ('complete','runs','cells','missing','all_common_conditions_match')},ensure_ascii=False))
    if not audit['all_common_conditions_match']:print('CAUTION: paired physical/configuration inputs differ; inspect audit before causal interpretation')

if __name__=='__main__': main()
