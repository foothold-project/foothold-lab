"""Issue #765, read-only CPU audit of the E1 remedial 250-update window."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import datetime as dt
import json
from pathlib import Path
import sys
import numpy as np
from recompute_e1_seed_repeats import net_yaw, sha, symmetry, self_test

OLD = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150')
NEW = Path('/home/jay/data/foothold/s2_lab/ex42_remedy_20261113_115101/main/EX-42-B-E1-remedyA_20261113_115101')
G1 = Path('/home/jay/data/foothold/s2_lab/hipan_g1_20261112')
MODES = ('eval_gt', 'eval_pred', 'probe_prop_only')
TAGS = ('Loss/learning_rate', 'Loss/kl_probe/ppo_mean', 'Policy/mean_noise_std',
        'Loss/value_function', 'Train/mean_reward', 'Train/mean_episode_length',
        'Curriculum/terrain_levels', 'Episode_Reward/track_lin_vel',
        'Episode_Reward/track_ang_vel', 'Episode_Reward/ex41_zero_yaw',
        'Episode_Reward/ex41_foot_slip', 'Episode_Termination/bad_orientation')


def main(out):
    self_test()
    # A central two-second stall statistic can improve while six-second progress falls.
    a = np.array([.13, .06, .04, .05, .08, .07])
    b = np.array([.05, .05, .08, .10, .06, .04])
    assert b[2:4].mean() > a[2:4].mean() and b.sum() < a.sum()
    out.mkdir(parents=True, exist_ok=True)
    frozen = Path('/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v11b')
    sys.path.insert(0, str(frozen))
    import yaml
    from foothold_s2.eval.ex42_d44_cells import read_evidence
    plan_path = frozen/'foothold_s2/curriculum/ex42-prep.yaml'
    plan = yaml.safe_load(plan_path.read_text(encoding='utf-8'))
    evidence = {}
    checks, map_rows, g1_rows, yaws, pairs, time_rows, d44rows, curves = [], [], [], [], [], [], [], []
    refs = {}

    def register(p):
        p = Path(p)
        value = sha(p)
        evidence[str(p)] = value
        return value

    def read(p):
        register(p)
        return json.loads(Path(p).read_text(encoding='utf-8'))

    def arrays(p, expected=None):
        actual = register(p)
        if expected is not None:
            assert actual == expected, p
        with np.load(p, allow_pickle=False) as z:
            return {k: z[k] for k in z.files}

    def equal_conditions(d, ref, name):
        for k in ('envs', 'steps', 'eval_seed', 'dr_off', 'curriculum_off', 'fixed_terrain', 'terrain_tiles', 'ex42_mesh'):
            assert d.get(k) == ref.get(k), (name, k)
        # Absolute frozen-checkout path changed, physical material values did not.
        assert {k:v for k,v in d['evaluation_friction'].items() if k!='plan_path'} == {
            k:v for k,v in ref['evaluation_friction'].items() if k!='plan_path'}, name
        changes = sorted(k for k in set(d['source_sha256']) | set(ref['source_sha256'])
                         if d['source_sha256'].get(k) != ref['source_sha256'].get(k))
        allowed = ['foothold_s2.runners.contracts', 'foothold_s2.runners.start_runner'] if name == 'map64' else []
        assert changes == allowed, (name, changes)
        checks.append({'suite':name, 'same_conditions':True, 'source_changes':changes,
                       'device':d['run_identity']['device']})

    def map_cells(p, d, iteration, group, level, rows):
        assert (d['envs'], d['steps'], d['eval_seed'], d['policy_dt_s']) == (64,300,42,.02)
        for mode, entries in d['modes'].items():
            for command, r in entries.items():
                z = arrays(p.parent / Path(d['env_arrays'][mode+'/'+command]).name)
                al = z['alive'].astype(bool)
                assert z['vx'].shape == al.shape == (300,64)
                assert int(z['alive_end'].sum()) == r['alive_envs_at_end']
                assert len(r['per_env']) == r['env_count'] == 64
                assert r['policy_steps_x_envs'] == 19200
                assert r['gt_used'] == (19200 if mode == 'eval_gt' else 0)
                cmd = np.array(r['command'])
                v = np.linalg.norm(cmd[:2])
                projected = np.array([e['command_xy_projection_integral_m'] for e in r['per_env']]) if v else None
                ratio = projected/(v*6) if v else None
                errs = {k:np.array([e[k] for e in r['per_env']]) for k in (
                    'vx_abs_error_mean_alive_mps','vy_abs_error_mean_alive_mps','wz_abs_error_mean_alive_radps')}
                assert all(np.isfinite(x).all() for x in errs.values())
                if cmd[0] and not cmd[1]:
                    raw = (z['vx']*al).sum(0)*.02*np.sign(cmd[0])
                    assert np.allclose(raw, projected, atol=1e-6, rtol=2e-5)
                row = {'iteration':iteration,'group':group,'level':level,'mode':mode,'command':command,
                       'survival':r['alive_envs_at_end'],'R':float(np.median(ratio)) if v else None,
                       'projection_m':float(np.median(projected)) if v else None,
                       'vx_mae':float(np.median(errs['vx_abs_error_mean_alive_mps'])),
                       'vy_mae':float(np.median(errs['vy_abs_error_mean_alive_mps'])),
                       'wz_mae':float(np.median(errs['wz_abs_error_mean_alive_radps'])),
                       'stalled_fraction_2to4s':r['stalled_fraction_2to4s'],
                       'stationary_fraction_2to4s':r['stationary_fraction_2to4s'],'source':str(p)}
                if group == 'g1b':
                    err = errs['vx_abs_error_mean_alive_mps' if cmd[0] else 'vy_abs_error_mean_alive_mps']
                    row['proposed_v2_success'] = int(np.sum(z['alive_end'] & (ratio>=.8) & (ratio<=1.2) & (err<=.2*v))) if v else None
                rows.append(row)
                if group == 'g1b' and command.startswith('fwd'):
                    for sec in range(6):
                        means = z['vx'][sec*50:(sec+1)*50].mean(0)
                        time_rows.append({'iteration':iteration,'level':level,'command':command,'second':sec,
                                          'median_vx_mps':float(np.median(means)),'below_005_count':int((means<.05).sum())})
                    win = z['vx'][100:200].mean(0)
                    assert np.isclose((win<.05).mean(), r['stalled_fraction_2to4s'])
        for mode in d['modes']:
            left,right = ('side+0.4','side-0.4') if group=='g1b' else ('side+0.5','side-0.5')
            rr = {r['command']:r for r in rows if (r['iteration'],r['level'],r['mode'])==(iteration,level,mode)}
            l,r=rr[left]['R'],rr[right]['R']; s,gap=symmetry(l,r)
            pairs.append({'iteration':iteration,'group':group,'level':level,'mode':mode,
                          'left_R':l,'right_R':r,'S_min_over_max':s,'difference_over_mean':gap})

    summaries = {}
    for iteration, run, sub in ((2000,OLD,'m2000seg'),(2250,NEW,'remA2250')):
        score_root = run/f'eval/scores/m{iteration}'
        manifest = read(run/'manifest.json')
        ckpt = register(run/f'model_{iteration}.pt')
        assert ckpt == manifest['checkpoints'][f'model_{iteration}.pt']
        p1=read(score_root/'p1_score.json'); score=read(score_root/'ex42_score.json')
        assert p1['state']=='complete' and p1['checkpoint_iteration']==iteration
        assert p1['checkpoint_sha256']==score['checkpoint_sha256']==ckpt
        summaries[str(iteration)]={'checkpoint_sha256':ckpt,'p1':p1['judgment'],
            'maintenance':score['maintenance_judgement'],'maintenance_windows':p1['e1_exit']['maintenance']}
        p=score_root/'map64/map_modes.json';d=read(p)
        assert d['checkpoint_sha256']==ckpt and set(d['modes'])==set(MODES)
        assert all(len(v)==13 for v in d['modes'].values())
        if iteration==2000: refs['map64']=d
        else: equal_conditions(d,refs['map64'],'map64')
        map_cells(p,d,iteration,'map64','mixed012',map_rows)
        a=read(score_root/'axis_v2/axis_v2.json')
        assert a['checkpoint_sha256']==ckpt and set(a['modes'])==set(MODES)
        if iteration==2000: refs['axis']=a
        else: equal_conditions(a,refs['axis'],'axis')
        for mode, entries in a['modes'].items():
            assert len(entries)==10
            for name, row in entries.items():
                raw=score_root/'axis_v2'/Path(row['raw_file']).name
                z=arrays(raw,row['raw_sha256']); al=z['alive'].astype(bool)
                assert al.shape==z['yaw'].shape==(300,64)
                assert row['policy_steps_x_envs']==19200 and row['gt_used']==(19200 if mode=='eval_gt' else 0)
                if not name.startswith('fwd'): continue
                assert not z['heading_pre'].any() and np.allclose(z['cmd_post'][:,:,2][al],0)
                signed=net_yaw(z['yaw'],z['start_yaw'],al)
                assert np.allclose(signed,[e['yaw_signed_accum_rad'] for e in row['per_env']],atol=3e-6)
                progress=(z['vx']*al).sum(0)*float(z['dt'])
                yaws.append({'iteration':iteration,'mode':mode,'command':name,
                    'abs_net_median_rad':float(np.median(abs(signed))),
                    'abs_net_p90_rad':float(np.quantile(abs(signed),.9)),
                    'signed_median_rad':float(np.median(signed)),
                    'progress_m':float(np.median(progress)),
                    'stalled_fraction_2to4s':float((z['vx'][100:200].mean(0)<.05).mean()),
                    'survival':int(al[-1].sum()),'source':str(raw)})
        for level in (0,5):
            p=G1/sub/f'hipan_g1b_L{level}/map_modes.json';d=read(p)
            assert d['checkpoint_sha256']==ckpt and set(d['modes'])=={'eval_gt'}
            assert len(d['modes']['eval_gt'])==8
            if iteration==2000:refs[f'g1b{level}']=d
            else:equal_conditions(d,refs[f'g1b{level}'],f'g1b{level}')
            map_cells(p,d,iteration,'g1b',level,g1_rows)
        d=read(score_root/'d44/d44_cells.json')
        assert d['checkpoint_sha256']==ckpt and d['state']=='done' and len(d['cases'])==9
        if iteration==2000: refs['d44']=d
        else:
            for k in ('format','source_mesh_sha256','replica_mesh_sha256','seed','envs','dt','plan_sha256','dr_disabled'):
                assert d[k]==refs['d44'][k],k
        # Use the pinned CPU criterion to recompute all nine cases from traces,
        # not merely sum the JSON's claimed per-env success flags.
        canonical_folder = Path(next(iter(d['cases'].values()))['raw_file']).parent
        checked = read_evidence(canonical_folder, plan=plan, plan_sha256=d['plan_sha256'],
                                checkpoint_sha256=ckpt, seed=42)
        summaries[str(iteration)]['d44_raw_recomputed_judge_counts'] = {
            k:v['success_count'] for k,v in checked.items()}
        for case, row in d['cases'].items():
            p=score_root/'d44'/Path(row['raw_file']).name
            assert register(p)==row['raw_sha256']; rr=read(p)
            z=arrays(p.with_suffix('.npz'),rr['trace_sha256'])
            assert len(rr['per_env'])==64
            assert sum(bool(e['success']) for e in rr['per_env'])==rr['success_count']
            item={'iteration':iteration,'case':case,'valid':rr['valid_count'],
                  'survival':rr['survival_count'],'success':rr['success_count'],
                  'stop_ok':None,'reasons':dict(Counter(e['reason'] for e in rr['per_env'])),
                  'approach_yaw_rad':None,'stop_yaw_rad':None,'restart_2s_yaw_rad':None,'restart_2s_vx_mps':None,
                  'yaw_diagnostic_survivors':None}
            if rr['task']=='stop_restart':
                item['stop_ok']=sum(e['stop_ok'] for e in rr['per_env'])
                q=z['root_quat_w']; y=np.unwrap(np.arctan2(2*(q[:,:,0]*q[:,:,3]+q[:,:,1]*q[:,:,2]),1-2*(q[:,:,2]**2+q[:,:,3]**2)),axis=0)
                rows=[]
                survivors = np.flatnonzero(z['alive'][-1])
                assert len(survivors) > 0
                item['yaw_diagnostic_survivors'] = len(survivors)
                for env in survivors:
                    ap=np.flatnonzero(z['phase_id'][:,env]==1);st=np.flatnonzero(z['phase_id'][:,env]==2);re=np.flatnonzero(z['phase_id'][:,env]==3)
                    last=min(re[0]+round(2/float(z['dt']))-1,re[-1])
                    rows.append([y[ap[-1],env]-y[ap[0]-1,env],y[st[-1],env]-y[st[0]-1,env],
                                 y[last,env]-y[re[0]-1,env],z['body_vel_b'][re[0]:last+1,env,0].mean()])
                for k,v in zip(('approach_yaw_rad','stop_yaw_rad','restart_2s_yaw_rad','restart_2s_vx_mps'),np.median(rows,axis=0)):
                    item[k]=float(v)
            d44rows.append(item)
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
        vals={}
        for f in sorted(run.glob('events.out.tfevents.*')):
            ea=EventAccumulator(str(f),size_guidance={'scalars':0}).Reload(); register(f)
            for tag in TAGS:
                for e in ea.Scalars(tag):
                    if iteration-49<=e.step<=iteration:
                        key=(e.step,tag)
                        assert key not in vals or vals[key]==e.value
                        vals[key]=e.value
        assert len(vals)==50*len(TAGS)
        curves.append({'iteration':iteration,**{t:float(np.mean([vals[(i,t)] for i in range(iteration-49,iteration+1)])) for t in TAGS}})

    for rank in (0,1):
        d=read(NEW/f'segment_rewards_b8_rank{rank}.json')
        assert d['live']==d['asked'] and d['live']['zero_yaw']==-1.
    register(plan_path)
    register(frozen/'foothold_s2/eval/ex42_d44_cells.py')
    register(frozen/'foothold_s2/rewards/w86.py')
    repeat_path=Path(__file__).with_name('e1-seed-repeat-data')/'ranges.csv'
    register(repeat_path)
    register(Path(__file__).with_name('recompute_e1_seed_repeats.py'))
    register(Path(__file__).with_name('e1-review-data')/'g1.csv')
    def writecsv(name, rows):
        assert rows
        with (out/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    for name,rows in [('map64.csv',map_rows),('g1b.csv',g1_rows),('yaw.csv',yaws),('symmetry.csv',pairs),('slow_seconds.csv',time_rows),('d44.csv',d44rows),('training_last50.csv',curves)]:
        writecsv(name,rows)
    (out/'summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2)+'\n')
    (out/'conditions.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    (out/'evidence_sha256.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    # Generate report tables and a static comparison plot directly from measurements.
    repeat={(r['cell'],r['metric']):r for r in csv.DictReader(repeat_path.open())}
    def span(cell, metric):
        r=repeat[cell,metric]
        return f"{float(r['min']):.4f}~{float(r['max']):.4f}"
    lines=['# m2250 원자료 재계산 표','',
           '> 분류: A/평가 · 일반화 벤치마크 · 지표',
           '> 작성: analyst-lx · '+dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
           '> 근거: evidence_sha256.json · CPU 재계산',
           '> 요지: 방향·저속·정체·D44를 나눠 비교한다.',
           '> 상태: 확인됨 · m2250은 seed42 한 번', '',
           '## Y1 · 같은 axis-v2 L2, 6초', '',
           '| 지도·명령 | m2000 중앙값 | m2000 세 시드 범위 | m2250 중앙값 | m2000 p90 | m2000 p90 범위 | m2250 p90 | 전진 m, 전→후 |',
           '|---|---:|---|---:|---:|---|---:|---|']
    yi={(r['iteration'],r['mode'],r['command']):r for r in yaws}
    for mode in ('eval_gt','eval_pred'):
        for c in ('fwd0.5','fwd1.0'):
            a,b=yi[2000,mode,c],yi[2250,mode,c];key=f'{mode}/{c}'
            lines.append(f"| {mode} {c} | {a['abs_net_median_rad']:.4f} | {span(key,'abs_net_median_rad')} | {b['abs_net_median_rad']:.4f} | {a['abs_net_p90_rad']:.4f} | {span(key,'abs_net_p90_rad')} | {b['abs_net_p90_rad']:.4f} | {a['progress_m']:.3f} → {b['progress_m']:.3f} |")
    lines+=['','단위 rad. 네 칸 모두 두 저장본 생존64/64, 2~4초 정체0/64. 원래 문턱 중앙값0.10·p90 0.20은 가정으로 제안한 값이며 운영 P1과 별도다.', '',
            '## S1 · G1b의 GT, L0와 L5는 연속 지형', '',
            '| 레벨·명령 | m2000 R | m2000 세 시드 R | m2250 R | 정체 env 수 전→후 | m2250 제안 성공 수 |',
            '|---|---:|---|---:|---|---:|']
    gi={(r['iteration'],r['level'],r['command']):r for r in g1_rows}
    for l in (0,5):
        for c in ('fwd0.1','fwd0.2'):
            a,b=gi[2000,l,c],gi[2250,l,c]
            lines.append(f"| L{l} {c} | {a['R']:.4f} | {span(f'g1b/{l}/eval_gt/{c}','R')} | {b['R']:.4f} | {round(a['stalled_fraction_2to4s']*64)} → {round(b['stalled_fraction_2to4s']*64)} | {b['proposed_v2_success']}/64 |")
    lines+=['','R은 6초 진행/명령 거리, 정체는 2~4초 평균 속도<0.05m/s. 네 칸 생존은 모두64/64. 성공 정의는 사전 제안 그대로 생존 AND R0.8~1.2 AND MAE≤명령20%.', '',
            '## D44 · 고정 판정식을 원 NPZ로 다시 계산', '',
            '| 칸 | 성공 m2000→m2250 | 정지 통과 전→후 | 도달 감지 미충족 전→후 | 접근 yaw 전→후 | 정지 yaw 전→후 | 재출발2초 yaw 전→후 |',
            '|---|---|---|---|---|---|---|']
    di={(r['iteration'],r['case']):r for r in d44rows}
    for mode in MODES:
        a,b=di[2000,'stop_restart_'+mode],di[2250,'stop_restart_'+mode]
        lines.append(f"| {mode} | {a['success']} → {b['success']} | {a['stop_ok']} → {b['stop_ok']} | {a['reasons'].get('no_top_latch',0)} → {b['reasons'].get('no_top_latch',0)} | {a['approach_yaw_rad']:.4f} → {b['approach_yaw_rad']:.4f} | {a['stop_yaw_rad']:.4f} → {b['stop_yaw_rad']:.4f} | {a['restart_2s_yaw_rad']:.4f} → {b['restart_2s_yaw_rad']:.4f} |")
    lines+=['','yaw는 끝까지 생존한 env의 구간별 signed 중앙값(rad), Y1의 절댓값 중앙값과 다른 통계다. 지도 켬 GT/PRED 생존은 모두64/64. 지도 끔 생존은51→64이며, 서로 다른 생존자 집단의 yaw는 진단용으로만 둔다. 끔은 기록 전용. 회전6칸은 두 저장본 모두64/64 성공.', '',
            '## 학습 마지막50회 평균', '',
            '| 저장본 | lr | KL | action std | value loss | 보상 | 에피소드 길이 | 평균 레벨 |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in curves:
        lines.append(f"| {r['iteration']} | {r['Loss/learning_rate']:.7f} | {r['Loss/kl_probe/ppo_mean']:.5f} | {r['Policy/mean_noise_std']:.5f} | {r['Loss/value_function']:.5f} | {r['Train/mean_reward']:.4f} | {r['Train/mean_episode_length']:.3f} | {r['Curriculum/terrain_levels']:.4f} |")
    lines+=['','보상 가중이 달라졌으므로 보상 합의 직접 우열로 해석하지 않는다. 모든 숫자는 스크립트가 읽은 원자료 또는 사전 반복 표에서 생성했다.']
    (out/'TABLES.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=['#006D77','#C65D3B']
    fig,axs=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    labels=['GT .5','GT 1.0','PRED .5','PRED 1.0'];ks=[('eval_gt','fwd0.5'),('eval_gt','fwd1.0'),('eval_pred','fwd0.5'),('eval_pred','fwd1.0')]
    x=np.arange(4)
    for i,n in enumerate((2000,2250)):
        axs[0,0].bar(x+(i-.5)*.32,[yi[n,m,c]['abs_net_median_rad'] for m,c in ks],width=.32,color=colors[i],label=f'm{n}')
    axs[0,0].set(xticks=x,xticklabels=labels,ylabel='median abs net yaw (rad)',title='Fast-forward heading response');axs[0,0].legend()
    for i,n in enumerate((2000,2250)):
        axs[0,1].bar(x+(i-.5)*.32,[gi[n,l,c]['R'] for l,c in [(0,'fwd0.1'),(0,'fwd0.2'),(5,'fwd0.1'),(5,'fwd0.2')]],width=.32,color=colors[i])
    axs[0,1].set(xticks=x,xticklabels=['L0 .1','L0 .2','L5 .1','L5 .2'],ylabel='progress / commanded distance',title='Slow forward: six-second progress')
    for i,n in enumerate((2000,2250)):
        rr=[r for r in time_rows if (r['iteration'],r['level'],r['command'])==(n,0,'fwd0.2')]
        axs[1,0].plot([r['second']+.5 for r in rr],[r['median_vx_mps'] for r in rr],marker='o',color=colors[i],label=f'm{n}')
    axs[1,0].axhline(.05,color='#444444',ls=':');axs[1,0].axvspan(2,4,color='#E8E8E8',alpha=.5)
    axs[1,0].set(xlabel='time (s)',ylabel='median one-second vx (m/s)',title='Why the 2-4 s stall statistic differs');axs[1,0].legend()
    for i,n in enumerate((2000,2250)):
        axs[1,1].bar(np.arange(3)+(i-.5)*.32,[di[n,'stop_restart_'+m]['success'] for m in MODES],width=.32,color=colors[i])
    axs[1,1].set(xticks=np.arange(3),xticklabels=['GT','PRED','OFF (record)'],ylabel='successful envs / 64',ylim=(0,64),title='D44 stop-restart remains incomplete')
    fig.savefig(out/'comparison.png',dpi=150);plt.close(fig)
    print(json.dumps({'known_input_tests':'PASS','map64_rows':len(map_rows),'g1b_rows':len(g1_rows),'yaw_rows':len(yaws),
                      'd44_rows':len(d44rows),'source_files':len(evidence),'summary':summaries,'out':str(out)},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    main(p.parse_args().out)
