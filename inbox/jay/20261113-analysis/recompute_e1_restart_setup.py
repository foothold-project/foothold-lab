"""Issue #765: read-only CPU audit of the m13250 restart proposal and parent.

Writes only to --out. No Isaac/Kit, CUDA, live run, reward or plan mutation.
"""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import yaml

FROZEN = Path('/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v11b')
PARENT = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218')
OLD = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150')
G1 = Path('/home/jay/data/foothold/s2_lab/hipan_g1_20261112')
PARENT_SHA = '680c820b73646d9c11f62f184fd35e6cc096ffd04681951d542b2b4b472d779e'


def partial_reward(cmd, vx, vy, wz, std, yaw_weight):
    """Only three weighted terms, before RewardManager multiplies by dt."""
    return (2 * math.exp(-((cmd-vx)**2+vy**2)/std**2)
            + math.exp(-(wz/.5)**2) + yaw_weight*abs(wz))


def net_yaw(yaw, initial, alive):
    counts = alive.sum(0)
    assert np.all(counts > 0)
    assert np.array_equal(alive, np.arange(len(yaw))[:, None] < counts[None])
    unwrapped = np.unwrap(np.concatenate([initial[None], yaw.astype(float)]), axis=0)
    return unwrapped[counts, np.arange(len(initial))] - unwrapped[0]


def self_test():
    assert partial_reward(.1,.1,0,0,.35,-1) == 3
    assert partial_reward(0,0,0,0,.35,-1) == 3
    assert partial_reward(.1,.1,0,.1,.35,-1) < 3
    assert partial_reward(.1,0,0,0,.35,-1) < partial_reward(.1,0,0,0,.5,-.5)
    assert np.allclose(net_yaw(np.deg2rad([[179.],[-179.]]),np.deg2rad([170.]),np.ones((2,1),bool)),np.deg2rad([11.]))
    assert np.median(np.abs([-.3,.3])) == .3
    assert abs(np.median([-.3,.3])) == 0  # A signed median can hide opposite drifts.
    assert np.isclose((.1*1)/(.1*6),1/6)  # Dead after one second is not a six-second success.
    assert np.isclose(.19*.5*(.2-.1)/(.3-.1),.0475)


def main(out):
    self_test(); out.mkdir(parents=True, exist_ok=True)
    evidence=[]
    def file(p):
        p=Path(p)
        with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
        evidence.append({'path':str(p),'sha256':h})
        return p
    def js(p): return json.loads(file(p).read_text(encoding='utf-8'))
    def npz(p):
        with np.load(file(p),allow_pickle=False) as z:return {k:z[k] for k in z.files}
    def csvout(name,rows):
        assert rows
        with (out/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    file(PARENT/'model_250.pt')
    assert evidence[-1]['sha256']==PARENT_SHA
    parent=[]
    for level in (0,5):
        p=G1/f'G1b_L{level}'/'map_modes.json'; d=js(p)
        assert d['checkpoint_sha256']==PARENT_SHA
        assert (d['eval_seed'],d['envs'],d['steps'],d['policy_dt_s'])==(42,64,300,.02)
        assert all(t['level']==level for t in d['terrain_tiles'])
        for name,row in d['modes']['eval_gt'].items():
            if not name.startswith(('fwd','side')):continue
            cmd=np.array(row['command']); axis=int(np.argmax(np.abs(cmd))); speed=abs(cmd[axis])
            projections=np.array([e['command_xy_projection_integral_m'] for e in row['per_env']])
            z=npz(p.parent/d['env_arrays']['eval_gt/'+name]); alive=z['alive'].astype(bool)
            assert alive.shape==(300,64) and alive.all()  # Parent rows have no censoring.
            assert row['alive_envs_at_end']==64
            key=('vx_abs_error_mean_alive_mps','vy_abs_error_mean_alive_mps')[axis]
            errors=np.array([e[key] for e in row['per_env']])
            stalled=int(round(row['stalled_fraction_2to4s']*64))
            extra={}
            if axis==0:
                raw=(z['vx']*alive).sum(0)*float(z['dt'])
                assert np.allclose(raw,projections,rtol=2e-5,atol=1e-6)
                assert np.allclose(np.abs(z['vx']-cmd[0]).mean(0),errors,rtol=2e-5,atol=1e-6)
                assert stalled==int((z['vx'][100:200].mean(0)<.05).sum())
                extra={f'R_{a}_{b}s':float(np.median(z['vx'][a*50:b*50].mean(0)/speed)) for a,b in ((0,1),(2,4),(4,6))}
            parent.append({'level':level,'mode':'eval_gt','command':name,'R':float(np.median(projections/(speed*6))),
                'median_projection_m':float(np.median(projections)),'median_mae_mps':float(np.median(errors)),
                'stalled_2to4s':stalled,'stalled_denominator':64,'alive':64,
                **{k:extra.get(k) for k in ('R_0_1s','R_2_4s','R_4_6s')},'source':str(p)})
    csvout('parent_g1b.csv',parent)
    yaw=[];p=PARENT/'eval/scores/m250/axis_v2/axis_v2.json';d=js(p)
    assert d['checkpoint_sha256']==PARENT_SHA
    assert (d['eval_seed'],d['envs'],d['steps'],d['dt_s'],d['fixed_level'])==(42,64,300,.02,2)
    for mode,cases in d['modes'].items():
        for name in ('fwd0.5','fwd1.0'):
            row=cases[name]; raw=p.parent/Path(row['raw_file']).name;z=npz(raw)
            assert evidence[-1]['sha256']==row['raw_sha256']
            assert not z['heading_pre'].any()
            assert np.allclose(z['cmd_post'][:,:,2][z['alive'].astype(bool)],0)
            signed=net_yaw(z['yaw'],z['start_yaw'],z['alive'].astype(bool))
            assert np.allclose(signed,[e['yaw_signed_accum_rad'] for e in row['per_env']],atol=3e-6)
            yaw.append({'mode':mode,'command':name,'survival':int(z['alive'][-1].sum()),
                'signed_median_rad':float(np.median(signed)),
                'abs_net_median_rad':float(np.median(np.abs(signed))),
                'abs_net_p90_rad':float(np.quantile(np.abs(signed),.9)),'source':str(raw)})
    csvout('parent_yaw.csv',yaw)
    (out/'parent_baseline.json').write_text(json.dumps({
        'format':'analyst-e1-parent-baseline/1','checkpoint_sha256':PARENT_SHA,
        'cumulative_update':13250,'local_update':250,'seed':42,'n_envs':64,'steps':300,
        'g1b':parent,'yaw':yaw,
        'note':'Baseline data only. No execution approval or automatic judge modification.'},ensure_ascii=False,indent=2)+'\n')
    env=yaml.load(file(OLD/'params/env.yaml').read_text(),Loader=yaml.BaseLoader)
    rewards=env['rewards'];assert float(rewards['track_lin_vel']['weight'])==2
    assert float(rewards['track_ang_vel']['weight'])==1
    assert float(rewards['track_ang_vel']['params']['std'])==.5
    plan=yaml.safe_load(file(FROZEN/'foothold_s2/curriculum/ex42-prep.yaml').read_text())
    source=file(FROZEN/'foothold_s2/curriculum/ex41.py')
    constructors=[n for n in ast.walk(ast.parse(source.read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Stage' and len(n.args)>=7]
    assert len(constructors)==1
    low=float(ast.literal_eval(constructors[0].args[6]));assert low==.2
    early=js(OLD/'segment_commands_b1.json')['commands'];late=js(OLD/'segment_commands_b8.json')['commands']
    sys.path.insert(0,str(FROZEN))
    import torch
    from foothold_s2.commands.mixed_core import resample_stage, make_generator
    torch.set_num_threads(2)
    # Execute the installed pure reward functions, without importing Isaac or starting Kit.
    library=Path('/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/envs/mdp/rewards.py')
    reward_ast=ast.parse(library.read_text())
    functions=[n for n in reward_ast.body if isinstance(n,ast.FunctionDef) and n.name in ('track_lin_vel_xy_exp','track_ang_vel_z_exp')]
    assert len(functions)==2
    pure=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*functions],type_ignores=[])
    ns={'torch':torch,'SceneEntityCfg':lambda name:SimpleNamespace(name=name)}
    exec(compile(ast.fix_missing_locations(pure),str(library),'exec'),ns)
    for c in (.1,.2):
        for width in (.5,.35):
            cmd=torch.tensor([[c,0.,0.]],dtype=torch.float64)
            data=SimpleNamespace(root_lin_vel_b=torch.tensor([[c,0.,0.]],dtype=torch.float64),root_ang_vel_b=torch.tensor([[0.,0.,.1]],dtype=torch.float64))
            mock=SimpleNamespace(scene={'robot':SimpleNamespace(data=data)},command_manager=SimpleNamespace(get_command=lambda _:cmd))
            direct=2*ns['track_lin_vel_xy_exp'](mock,width,'base_velocity')+ns['track_ang_vel_z_exp'](mock,.5,'base_velocity')-.1
            assert np.isclose(float(direct),partial_reward(c,c,0,.1,width,-1))
    samplers=[]
    for name,commands,low_fraction in [('parent_E0',plan['stage_zero'],low),('E1_initial',early,low),('E1_late',late,low),('proposal',early,.5)]:
        overlay=commands.get('turn_overlay')
        if isinstance(overlay,dict):overlay=(overlay['fraction'],*overlay['wz_abs'])
        stage=SimpleNamespace(id='T0_prime',low_forward_fraction=low_fraction,heading_arm='B',heading_cfg={'forward_fraction':.3,'spin_target_fraction':.3},shares=commands['shares'],ranges=commands['ranges'],turn_overlay=overlay)
        n=1000000;s=resample_stage(make_generator(42),n,stage,torch.zeros(n))
        picked=(s['slot']==0)&(s['cmd'][:,0]>=.1)&(s['cmd'][:,0]<.2)
        expected=commands['shares']['forward']*low_fraction/2
        actual=float(picked.float().mean())
        assert abs(actual-expected)<.001
        samplers.append({'profile':name,'forward_share':commands['shares']['forward'],'within_forward_low_fraction':low_fraction,
            'expected_01_02_all':expected,'expected_01_02_heading_off':expected*.7,'expected_01_03_all':expected*2,
            'expected_03_15_all':commands['shares']['forward']*(1-low_fraction),
            'cpu_draw_01_02_all':actual,'cpu_draw_01_02_heading_off':float((picked&~s['heading']).float().mean()),'draws':n,'seed':42})
    csvout('sampler.csv',samplers)
    math_rows=[]
    for c in (.1,.15,.2):
        for std,yw in ((.5,-.5),(.35,-1.)):
            still=partial_reward(c,0,0,0,std,yw)
            for fraction in (.5,1.):
                for omega in (0.,.05,.1,.15,.2):
                    walking=partial_reward(c,c*fraction,0,omega,std,yw)
                    math_rows.append({'command_mps':c,'linear_std_mps':std,'zero_yaw_weight':yw,'actual_vx_fraction':fraction,'actual_wz_radps':omega,
                        'still_linear_plus_angular':still,'walking_three_terms':walking,'margin_before_other_cost':walking-still,'margin_per_step_dt002':(walking-still)*.02})
    csvout('reward_math.csv',math_rows)
    stages=[s for s in plan['stages'] if s['id'] in ('E0','E1','E1F','E2','E3','E4','E5','M','E6a','E6b')]
    budget={'origin_cumulative':next(s for s in stages if s['id']=='E0')['parent']['cumulative_update'],
            'stage_zero_updates':plan['stage_zero']['maximum_updates'],'budget_limit':plan['training_budget']['maximum_updates'],
            'stage_maxima':{s['id']:s['maximum_updates'] for s in stages},'base_sum':sum(s['maximum_updates'] for s in stages)}
    budget['pre_E2']=sum(budget['stage_maxima'][k] for k in ('E0','E1','E1F'))
    budget['remaining_E2_onward_no_extension']=budget['budget_limit']-budget['pre_E2']
    budget['remaining_E2_onward_E1_plus1000']=budget['remaining_E2_onward_no_extension']-1000
    assert (budget['origin_cumulative'],budget['pre_E2'],budget['base_sum'])==(13000,2750,17250)
    (out/'budget.json').write_text(json.dumps(budget,ensure_ascii=False,indent=2)+'\n')
    for suffix in ('foothold_s2/commands/mixed_core.py','foothold_s2/commands/ex42_command_stats.py','foothold_s2/commands/ex42_shares.py','foothold_s2/rewards/w86.py','foothold_s2/rewards/w86_runtime.py','foothold_s2/rewards/basic_gait_bundle.py','foothold_s2/ex42_stage_handoff.py','foothold_s2/scripts/ex42_remeasure.py'): file(FROZEN/suffix)
    file('/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/envs/mdp/rewards.py')
    file('/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py')
    file(Path(__file__).with_name('e1-seed-repeat-data')/'ranges.csv')
    (out/'evidence_sha256.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    lines=['# m13250 기준값과 보상 계산', '', '> 분류: 리서치', '> 작성: analyst-lx · 2026-11-13', '> 근거: evidence_sha256.json의 원자료와 실행 코드', '> 요지: 모든 숫자는 recompute_e1_restart_setup.py가 생성', '> 상태: `확인됨` · 보상 계산은 세 항만, 전체 보상 아님', '', '대조 코드: [실제 명령 샘플러](https://github.com/foothold-project/foothold-lab/blob/8fdbbe78c96f2c58c653a8d29ff82ce12fa5c56d/foothold_s2/commands/mixed_core.py#L270). 원자료별 경로·해시는 [목록](evidence_sha256.json).', '', '## 부모 G1b', '', '| 레벨 | 명령 | 실제/명령 R | 정체/64 | 생존/64 | 추종 MAE m/s |', '|---|---|---:|---:|---:|---:|']
    lines += [f"| L{r['level']} | {r['command']} | {r['R']:.6f} | {r['stalled_2to4s']} | {r['alive']} | {r['median_mae_mps']:.6f} |" for r in parent]
    lines += ['', '## 부모 Y1 · L2, 6초', '', '| 지도 | 명령 | 부호 중앙값 rad | 순 yaw 절댓값 중앙값 rad | 순 yaw 절댓값 p90 rad | 생존/64 |', '|---|---|---:|---:|---:|---:|']
    lines += [f"| {r['mode']} | {r['command']} | {r['signed_median_rad']:.6f} | {r['abs_net_median_rad']:.6f} | {r['abs_net_p90_rad']:.6f} | {r['survival']} |" for r in yaw]
    lines += ['', '## 명령 비중 · 실행 코드 CPU 표본과 이론 기대값', '', '| 프로필 | 순전진 몫 % | 그 안 저속 몫 % | 0.1~0.2 전체 기대 % | heading 끔 기대 % | CPU 표본 % |', '|---|---:|---:|---:|---:|---:|']
    lines += [f"| {r['profile']} | {100*r['forward_share']:.2f} | {100*r['within_forward_low_fraction']:.1f} | {100*r['expected_01_02_all']:.3f} | {100*r['expected_01_02_heading_off']:.3f} | {100*r['cpu_draw_01_02_all']:.3f} |" for r in samplers]
    lines += ['', '## 완전 속도 추종 대 정지 · 다른 비용 차는 제외, dt 곱 전', '', '| 명령 m/s | 폭 m/s | zero_yaw | 실제 wz rad/s | 정지 세 항 | 걷기 세 항 | 차이 |', '|---|---:|---:|---:|---:|---:|---:|']
    lines += [f"| {r['command_mps']:.2f} | {r['linear_std_mps']:.2f} | {r['zero_yaw_weight']:.1f} | {r['actual_wz_radps']:.2f} | {r['still_linear_plus_angular']:.6f} | {r['walking_three_terms']:.6f} | {r['margin_before_other_cost']:.6f} |" for r in math_rows if r['actual_vx_fraction']==1 and r['command_mps'] in (.1,.2) and r['actual_wz_radps'] in (0,.1,.15)]
    (out/'TABLES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'self_test':'PASS','parent_rows':len(parent),'yaw_rows':len(yaw),'sampler_profiles':len(samplers),'reward_rows':len(math_rows),'raw_evidence_files':len(evidence),'budget':budget},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();main(args.out)
