"""Read-only CPU audit for issue #765; writes only to the selected report folder."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np

RUN = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150')
G1 = Path('/home/jay/data/foothold/s2_lab/hipan_g1_20261112')
D44 = Path('/home/jay/mai/tmp/d44_reeval/20261113_084230')

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()

def yaw(q):
    w,x,y,z = np.moveaxis(q, -1, 0)
    return np.unwrap(np.arctan2(2*(w*z+x*y), 1-2*(y*y+z*z)), axis=0)

def self_test():
    # Known inputs: forward/reverse signed projection, yaw crossing pi, and
    # a symmetric pair whose signed median hides two large heading errors.
    angles = np.deg2rad([170., 179., 181., 190.])
    q = np.stack([np.cos(angles/2), angles*0, angles*0, np.sin(angles/2)], -1)
    assert np.allclose(yaw(q)-yaw(q)[0], angles-angles[0])
    assert np.isclose(np.median([-.2,-.2]) * -1 / .2, 1)
    assert abs(np.median([-.3, .3])) == 0
    assert np.median(np.abs([-.3,.3])) == .3
    assert np.isclose(2 * math.exp(-(.1/.5)**2), 1.9215788783046464)
    assert np.isclose(2*(1-.8)/(1+.8), 2/9)

def main(out):
    self_test()
    out.mkdir(parents=True, exist_ok=True)
    evidence = []
    def read(p):
        p = Path(p); evidence.append({'path':str(p), 'sha256':sha(p)})
        return json.loads(p.read_text(encoding='utf-8'))
    def writecsv(name, rows):
        assert rows, name
        with (out/name).open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n'); w.writeheader(); w.writerows(rows)
    g1, identities = [], []
    for n in range(0,2001,250):
        for level in (0,5):
            b = read(G1/'briefs'/f'm{n}_L{level}.json')
            p = Path(b['g1b']['source']); d = read(p)
            assert d['envs'] == 64 and d['steps'] == 300
            assert set(d['modes']) == {'eval_gt'}
            duration = d['steps'] * d['policy_dt_s']
            identities.append({'iteration':n,'level':level,'path':str(p),
                               'assignment_sha256':d['terrain_hash'],
                               'source_sha256':d['source_sha256'],
                               'seed':d['eval_seed'],'ex42_mesh':d['ex42_mesh']})
            for name, v in d['modes']['eval_gt'].items():
                cmd = np.asarray(v['command']); axis = int(np.argmax(np.abs(cmd)))
                speed = abs(cmd[axis]); errkey = ['vx_abs_error_mean_alive_mps',
                    'vy_abs_error_mean_alive_mps','wz_abs_error_mean_alive_radps'][axis]
                errors = [e[errkey] for e in v['per_env']]
                projections = [e['command_xy_projection_integral_m'] for e in v['per_env']]
                projection = float(np.median(projections)) if axis < 2 else None
                row = {'iteration':n,'level':level,'command':name,
                       'survival':v['alive_envs_at_end'],'error_median':float(np.median(errors)),
                       'one_minus_error_over_cmd':1-float(np.median(errors))/speed,
                       'projection_m':projection,'projection_ratio':projection/(speed*duration) if projection is not None else None,
                       'body_vx_mean_mps':v['body_vx_integral_median_m']/duration,
                       'stalled_fraction_2to4s':v['stalled_fraction_2to4s'],
                       'duration_s':duration,'source':str(p)}
                g1.append(row)
                if axis == 0:
                    npz = p.parent/f'env_arrays_eval_gt_{name}.npz'
                    evidence.append({'path':str(npz),'sha256':sha(npz)})
                    with np.load(npz,allow_pickle=False) as z:
                        assert z['vx'].shape == (300,64)
                        assert np.all(z['alive']) # no survival conditioning in this calculation
                        assert np.isclose(np.median(z['vx'].sum(axis=0)*float(z['dt'])),
                                          v['body_vx_integral_median_m'],rtol=2e-5)
    writecsv('g1.csv',g1)
    (out/'g1_conditions.json').write_text(json.dumps(identities,ensure_ascii=False,indent=2)+'\n')
    d44rows, d44envs = [], []
    for n in (1750,2000):
        replica=read(D44/f'm{n}'/'d44_mesh/replica_receipt.json')
        for p in sorted((D44/f'm{n}'/'d44').glob('*.json')):
            if p.name=='d44_cells.json': continue
            d = read(p)
            if d.get('task') != 'stop_restart': continue
            npz = p.with_suffix('.npz')
            assert sha(npz) == d['trace_sha256']
            evidence.append({'path':str(npz),'sha256':sha(npz)})
            with np.load(npz,allow_pickle=False) as z:
                y=yaw(z['root_quat_w']); local=z['root_pos_w']-z['tile_offset_w'][None]
                phase=z['phase_id']; dt=float(z['dt'])
                rows=[]
                for e in range(64):
                    ap=np.flatnonzero(phase[:,e]==1); st=np.flatnonzero(phase[:,e]==2)
                    re=np.flatnonzero(phase[:,e]==3); last=min(re[0]+round(2/dt)-1, re[-1])
                    footspan=np.max(np.abs(z['foot_pos_w'][ap,e,:,1]-z['root_pos_w'][ap,e,1,None]))
                    er={'iteration':n,'mode':d['map_mode'],'env':e,
                        'approach_yaw_rad':float(y[ap[-1],e]-y[ap[0]-1,e]),
                        'stop_yaw_rad':float(y[st[-1],e]-y[st[0]-1,e]),
                        'restart_2s_yaw_rad':float(y[last,e]-y[re[0]-1,e]),
                        'heading_at_restart_rad':float(y[re[0],e]),
                        'restart_2s_lateral_m':float(local[last,e,1]-local[re[0],e,1]),
                        'restart_2s_vx_mps':float(np.mean(z['body_vel_b'][re[0]:last+1,e,0])),
                        'foot_lateral_radius_max_m':float(footspan),
                        'end_lateral_offset_m':float(local[-1,e,1]-replica['anchors_local_m']['landing_center'][1]),
                        'success':d['per_env'][e]['success'],'stop_ok':d['per_env'][e]['stop_ok'],
                        'reason':d['per_env'][e]['reason']}
                    rows.append(er); d44envs.append(er)
                result={'iteration':n,'mode':d['map_mode'],'valid':d['valid_count'],
                        'survive':d['survival_count'],'success':d['success_count'],
                        'stop_ok':sum(r['stop_ok'] for r in rows),
                        'no_top_latch':sum(r['reason']=='no_top_latch' for r in rows)}
                for k in ['approach_yaw_rad','stop_yaw_rad','restart_2s_yaw_rad',
                          'heading_at_restart_rad','restart_2s_lateral_m','restart_2s_vx_mps',
                          'foot_lateral_radius_max_m','end_lateral_offset_m']:
                    result[k+'_median']=float(np.median([r[k] for r in rows]))
                result['source']=str(p);d44rows.append(result)
    writecsv('d44.csv',d44rows);writecsv('d44_per_env.csv',d44envs)
    maintenance=[]; yaw_rows=[]
    for n in range(250,2001,250):
        d=read(RUN/f'eval/scores/m{n}/ex42_score.json')
        for mode,v in d['map64'].items():
            left=v['side+0.5']['command_projection_median_m'];right=v['side-0.5']['command_projection_median_m']
            row={'iteration':n,'mode':mode,'maintenance':d['maintenance_judgement'],
                 'side_left_m':left,'side_right_m':right,'symmetry_min_over_max':min(left,right)/max(left,right),
                 'side_difference_over_mean':abs(left-right)/((left+right)/2)}
            for c in ['fwd0.5','fwd1.0']:
                row[c+'_yaw_signed_median_rad']=d['axis_v2'][mode][c]['yaw_signed_accum_median_rad']
                raw=Path(d['axis_v2'][mode][c]['raw_file'])
                evidence.append({'path':str(raw),'sha256':sha(raw)})
                with np.load(raw,allow_pickle=False) as z:
                    alive=z['alive'].astype(bool)
                    counts=alive.sum(axis=0)
                    assert np.all(counts>0)
                    assert np.array_equal(alive,np.arange(alive.shape[0])[:,None]<counts[None])
                    assert not np.any(z['heading_pre'])
                    assert np.allclose(z['cmd_post'][:,:,2][alive],0)
                    angles=np.unwrap(np.concatenate([z['start_yaw'][None],z['yaw']],axis=0),axis=0)
                    signed=angles[counts,np.arange(64)]-angles[0]
                    assert np.isclose(np.median(signed),row[c+'_yaw_signed_median_rad'],atol=2e-6)
                    yaw_rows.append({'iteration':n,'mode':mode,'command':c,
                        'survival':int(alive[-1].sum()),
                        'signed_median_rad':float(np.median(signed)),
                        'abs_net_median_rad':float(np.median(np.abs(signed))),
                        'abs_net_p90_rad':float(np.quantile(np.abs(signed),.9)),
                        'total_yaw_variation_median_rad':float(np.median((np.abs(np.diff(angles,axis=0))*alive).sum(axis=0))),
                        'source':str(raw)})
            maintenance.append(row)
    writecsv('maintenance.csv',maintenance)
    writecsv('yaw.csv',yaw_rows)
    # The EX-41 subclass hardcodes the low-speed fraction; do not use the
    # older EX-40 base-class default (zero). Read the actual constructor AST.
    import ast, sys
    from types import SimpleNamespace
    frozen=Path('/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v6')
    source=frozen/'foothold_s2/curriculum/ex41.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    constructors=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Stage' and len(n.args)>=7]
    assert len(constructors)==1
    low=float(ast.literal_eval(constructors[0].args[6]));assert low==.2
    evidence.append({'path':str(source),'sha256':sha(source)})
    sys.path.insert(0,str(frozen))
    import torch
    from foothold_s2.commands.mixed_core import resample_stage,make_generator
    torch.set_num_threads(2)
    late=read(RUN/'segment_commands_b8.json')['commands']
    stage=SimpleNamespace(id='T0_prime',low_forward_fraction=low,heading_arm='B',
        heading_cfg={'forward_fraction':.3,'spin_target_fraction':.3},
        shares=late['shares'],ranges=late['ranges'],turn_overlay=(late['turn_overlay']['fraction'],*late['turn_overlay']['wz_abs']))
    n_draws=1000000
    samples=resample_stage(make_generator(42),n_draws,stage,torch.zeros(n_draws))
    chosen=(samples['slot']==0)&(samples['cmd'][:,0]<.2)
    expected=late['shares']['forward']*low*(.2-.1)/(.3-.1)
    assert abs(float(chosen.float().mean())-expected)<.0005
    sampler={'draws':n_draws,'seed':42,'low_forward_fraction':low,
             'forward_01_02_expected_fraction_all_commands':expected,
             'forward_01_02_draw_fraction_all_commands':float(chosen.float().mean()),
             'forward_01_02_free_wz_draw_fraction_all_commands':float((chosen & ~samples['heading']).float().mean()),
             'note':'CPU sampler draws, not measured rollout exposure. Stage heading fraction from frozen config.'}
    (out/'sampler.json').write_text(json.dumps(sampler,indent=2)+'\n')
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    tags=['Loss/learning_rate','Loss/kl_probe/ppo_mean','Policy/mean_noise_std','Loss/value_function',
          'Train/mean_reward','Train/mean_episode_length','Curriculum/terrain_levels',
          'Episode_Reward/track_lin_vel','Episode_Reward/track_ang_vel','Episode_Reward/ex41_zero_yaw',
          'Episode_Reward/ex41_foot_slip','Episode_Termination/bad_orientation']
    vals={};duplicates=[]
    for p in sorted(RUN.glob('events.out.tfevents.*')):
        ea=EventAccumulator(str(p),size_guidance={'scalars':0}).Reload()
        for t in tags:
            for e in ea.Scalars(t):
                if not 1<=e.step<=2000: continue
                key=(e.step,t)
                if key in vals and vals[key] != e.value: duplicates.append([e.step,t,vals[key],e.value])
                vals[key]=e.value
        evidence.append({'path':str(p),'sha256':sha(p)})
    assert not duplicates, duplicates[:5]
    curves=[{'iteration':n,**{t:vals[(n,t)] for t in tags}} for n in range(1,2001)]
    writecsv('curves.csv',curves)
    curve_windows=[]
    for n in range(250,2001,250):
        curve_windows.append({'iteration':n,**{t:float(np.mean([vals[(i,t)] for i in range(n-49,n+1)])) for t in tags}})
    writecsv('curve_windows_last50.csv',curve_windows)
    (out/'evidence_sha256.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    colors=['#15616D','#E07A5F','#614051','#317B22']
    for j,name in enumerate(['fwd0.1','fwd0.2','side+0.2','side-0.4']):
        r=[x for x in g1 if x['command']==name and x['level']==0]
        axs[0,0].plot([x['iteration'] for x in r],[x['projection_ratio'] for x in r],marker='o',color=colors[j],label=name)
    axs[0,0].set(title='L0, GT: signed command-axis travel / requested travel',ylabel='ratio');axs[0,0].legend()
    for j,name in enumerate(['fwd0.1','fwd0.2']):
        r=[x for x in g1 if x['command']==name and x['level']==0]
        axs[0,1].plot([x['iteration'] for x in r],[x['stalled_fraction_2to4s'] for x in r],marker='o',color=colors[j],label=name)
    axs[0,1].set(title='2 to 4 seconds: existing stalled fraction',ylabel='fraction');axs[0,1].legend()
    axs[1,0].plot(range(1,2001),[x['Loss/learning_rate'] for x in curves],color=colors[0]);axs[1,0].set(title='Adaptive learning rate',ylabel='learning rate')
    axs[1,1].plot(range(1,2001),[x['Policy/mean_noise_std'] for x in curves],color=colors[2]);axs[1,1].set(title='Action distribution standard deviation',ylabel='mean std')
    for ax in axs.flat:
        ax.set_xlabel('E1 local update (parent cumulative 13250)');ax.grid(alpha=.2)
        ax.axvline(500,color='black',ls=':',alpha=.4)
    fig.savefig(out/'e1-evidence.png',dpi=160);plt.close(fig)
    lines=['# E1 원자료 재계산 표', '', '> 분류: A/평가', '> 작성: analyst-lx · 2026-11-13',
           '> 근거: evidence_sha256.json의 원자료', '> 요지: 본문 의견과 분리한 CPU 재계산 수치',
           '> 상태: 확인됨 · 단일 학습 seed · 학습 및 GPU 실행 없음', '',
           '## 저속과 옆걸음', '',
           'GT · 64 env · 6초. R은 몸 좌표 명령 방향 속도의 적분 ÷ 명령 거리다. R=1이 명령대로, R=0은 명령 방향 진행 0이다. 월드 경로 직진성은 별도다. parent0은 누적 m13250, 그 뒤 번호는 E1 local이다.', '',
           '| local | level | 전진 0.1 R | 전진 0.2 R | 옆 +0.2 R | 옆 +0.4 R | 옆 −0.4 R | 전진 0.1 정체/64 | 전진 0.2 정체/64 |',
           '|---|---|---|---|---|---|---|---|---|']
    for n in range(0,2001,250):
        for level in (0,5):
            r={x['command']:x for x in g1 if x['iteration']==n and x['level']==level}
            fields=[str(n),str(level)]+[f"{r[c]['projection_ratio']:.4f}" for c in ['fwd0.1','fwd0.2','side+0.2','side+0.4','side-0.4']]
            fields += [str(round(r[c]['stalled_fraction_2to4s']*64)) for c in ['fwd0.1','fwd0.2']]
            lines.append('| '+' | '.join(fields)+' |')
    lines += ['', '## D44 /3 정지·재출발', '',
              '각 구간 바로 앞 샘플부터 변화량. 재출발은 첫 2초. yaw는 WXYZ quaternion에서 시간축 unwrap. 표의 yaw 중앙값 분모는 시작 64 env 전체이며, off m2000 유효 판정 분모는 51이다. 생존은 유효 표본 안의 수다.', '',
              '| local | 모드 | 유효 | 생존(유효 중) | 성공 | 정지 통과 | 꼭대기 latch 없음 | 접근 yaw rad | 정지 yaw rad | 재출발 yaw rad | 재출발 옆 이동 m |',
              '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in d44rows:
        fields=[str(r[k]) for k in ['iteration','mode','valid','survive','success','stop_ok','no_top_latch']]
        fields += [f'{r[k+"_median"]:.4f}' for k in ['approach_yaw_rad','stop_yaw_rad','restart_2s_yaw_rad','restart_2s_lateral_m']]
        lines.append('| '+' | '.join(fields)+' |')
    lines += ['', '## 일반 전진 방향 누적', '',
              '6초 끝 순방향 변화량의 절댓값이다. 절대 각속도의 시간 적분(흔들림 총량)과 다르다. 전진 0.5·1.0, GT만 아래에 보이고 세 모드 전부는 yaw.csv에 있다.', '',
              '| local | cmd | signed 중앙값 rad | env별 절댓값 중앙값 rad | env별 절댓값 p90 rad | 생존/64 |',
              '|---|---|---|---|---|---|']
    for r in yaw_rows:
        if r['mode']=='eval_gt':
            lines.append(f"| {r['iteration']} | {r['command']} | {r['signed_median_rad']:.4f} | {r['abs_net_median_rad']:.4f} | {r['abs_net_p90_rad']:.4f} | {r['survival']} |")
    lines += ['', '## 경계 직전 50회 학습 평균', '',
              '보상은 같은 학습 과제 분포가 아니다. 레벨이 변했고 구간 시작 직후 에피소드 합계 버퍼도 다시 쌓인다. 처음 몇 회의 합계 급락을 보행 붕괴로 판정하지 않는다.', '',
              '| local | lr | KL probe | action std | value loss | 평균 보상 | 에피소드 길이 | 지형 평균 레벨 |',
              '|---|---|---|---|---|---|---|---|']
    for r in curve_windows:
        fields=[str(r['iteration']),f"{r['Loss/learning_rate']:.7f}"]+[f'{r[k]:.4f}' for k in ['Loss/kl_probe/ppo_mean','Policy/mean_noise_std','Loss/value_function','Train/mean_reward','Train/mean_episode_length','Curriculum/terrain_levels']]
        lines.append('| '+' | '.join(fields)+' |')
    lines += ['', '## 서 있을 때의 추종 한 항', '',
              '계산: 2×exp(−v²/std²), vy 오차 0. dt를 곱하기 전 보상률이며 실제 step 보상은 여기에 0.02초를 곱한다. 총 보상 우열은 이 식만으로 알 수 없다.', '',
              '| vx 명령 m/s | std | 서 있기 보상률 | 완전 추종 대비 비율 | 완전 추종으로 더 얻는 보상률 |',
              '|---|---|---|---|---|']
    for v in [.1,.2,.5]:
        for std in [.5,.4,.25]:
            value=2*math.exp(-(v/std)**2)
            lines.append(f'| {v} | {std} | {value:.5f} | {value/2:.5f} | {2-value:.5f} |')
    (out/'EVIDENCE-TABLES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'g1_rows':len(g1),'d44_rows':len(d44rows),'curve_rows':len(curves),'source_files':len(evidence),'out':str(out)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)
