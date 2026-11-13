"""Issue #765: CPU-only repeat audit; raw experiments are read-only."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np

RUN = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150')
G1 = Path('/home/jay/data/foothold/s2_lab/hipan_g1_20261112')
CKPT = '3937df92866b79581f7b27e8b8c9fbde1f7733a85fe5179388fcfd78aa83c4bb'
SEEDS = (42, 7, 13)
MODES = ('eval_gt', 'eval_pred')

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def digest(a):
    a = np.asarray(a)
    return hashlib.sha256(str((a.dtype.str, a.shape)).encode() + a.tobytes()).hexdigest()

def symmetry(left, right):
    if min(left, right) <= 0:
        raise ValueError('nonpositive direction is not a successful symmetric pair')
    return min(left, right) / max(left, right), abs(left-right) / ((left+right)/2)

def net_yaw(yaw, start, alive):
    alive = np.asarray(alive, dtype=bool)
    counts = alive.sum(0)
    assert np.all(counts > 0)
    assert np.array_equal(alive, np.arange(alive.shape[0])[:, None] < counts[None])
    angles = np.unwrap(np.concatenate([start[None], yaw.astype(float)]), axis=0)
    return angles[counts, np.arange(len(start))] - angles[0]

def self_test():
    assert symmetry(.8, 1) == (.8, abs(.8-1)/.9)
    assert np.isclose(symmetry(.8, 1)[1], 2/9)
    assert np.isclose(symmetry(.9047619047619, 1)[1], .1)
    try:
        symmetry(0, 0)
    except ValueError:
        pass
    else:
        raise AssertionError('zero/zero silently accepted')
    z = net_yaw(np.deg2rad([[179., 179.], [-179., -179.], [-170., 40.]]),
                np.deg2rad([170., 170.]), np.array([[1,1],[1,1],[1,0]], bool))
    assert np.allclose(z, np.deg2rad([20., 11.]))
    assert abs(np.median([-.3, .3])) == 0 and np.median(np.abs([-.3, .3])) == .3
    # Fixed six-second denominator must not make a one-second survivor a completer.
    assert np.isclose((.2 * 1) / (.2 * 6), 1/6)

def main(out, axis_root, sides_root):
    self_test()
    out.mkdir(parents=True, exist_ok=True)
    evidence, identity, cells, pairs, yaw_rows, complete, arrays = [], [], [], [], [], [], {}
    def read(p):
        p = Path(p)
        evidence.append({'path': str(p), 'sha256': sha(p)})
        return json.loads(p.read_text(encoding='utf-8'))
    def npz(p):
        evidence.append({'path': str(p), 'sha256': sha(p)})
        with np.load(p, allow_pickle=False) as z:
            return {k: z[k] for k in z.files}
    def common(d, seed, level, source):
        assert d['checkpoint_sha256'] == CKPT
        assert (d['envs'], d['steps'], d['eval_seed']) == (64, 300, seed)
        assert d['evaluation_friction']['state'] == 'verified'
        assert (d['evaluation_friction']['static'], d['evaluation_friction']['dynamic']) == (.8, .6)
        assert sorted(d['dr_off']) == ['add_base_mass', 'physics_material']
        if level == 'mixed012':
            assert {k:sum(t['level']==k for t in d['terrain_tiles']) for k in range(3)} == {0:23,1:23,2:18}
            assert d['fixed_terrain']['fixed_level'] is None
        else:
            assert all(t['level'] == level for t in d['terrain_tiles'])
        assert len(d['terrain_tiles']) == 64
        assert d['ex41_checkpoint_preparation']['actor_input_width'] == 98
        assert d['ex41_checkpoint_preparation']['critic_input_width'] == 666
        identity.append({'source': str(source), 'seed': seed, 'level': level,
                         'checkpoint_sha256': d['checkpoint_sha256'],
                         'source_sha256': d['source_sha256'], 'run_identity': d['run_identity'],
                         'terrain_tiles': d['terrain_tiles'], 'ex42_mesh': d.get('ex42_mesh'),
                         'evaluation_friction': d['evaluation_friction']})
    def compare(d, ref, group):
        assert d['source_sha256'] == ref['source_sha256'], (group, 'source changed')
        assert d['terrain_tiles'] == ref['terrain_tiles'], (group, 'assignment changed')
        assert (d.get('ex42_mesh') or {}).get('mesh_sha256') == (ref.get('ex42_mesh') or {}).get('mesh_sha256')
        for k in ('shape','static_min','static_max','dynamic_min','dynamic_max','material_sha256'):
            assert d['evaluation_friction']['robot'][k] == ref['evaluation_friction']['robot'][k]
    def map_cells(p, d, seed, level, group, modes, names):
        duration = d['steps'] * d['policy_dt_s']
        assert duration == 6
        for mode in modes:
            for name in names:
                r = d['modes'][mode][name]
                assert r['env_count'] == len(r['per_env']) == 64
                assert r['policy_steps_x_envs'] == 19200
                assert r['gt_used'] == (19200 if mode == 'eval_gt' else 0)
                v = np.array(r['command']); axis = int(np.argmax(np.abs(v)))
                speed = abs(v[axis])
                errs = np.array([e[['vx_abs_error_mean_alive_mps','vy_abs_error_mean_alive_mps','wz_abs_error_mean_alive_radps'][axis]] for e in r['per_env']])
                assert np.isfinite(errs).all()
                projections = np.array([e['command_xy_projection_integral_m'] for e in r['per_env']]) if axis < 2 else None
                z = npz(p.parent / d['env_arrays'][mode+'/'+name])
                assert z['vx'].shape == z['alive'].shape == (300,64)
                assert int(z['alive_end'].sum()) == r['alive_envs_at_end']
                if axis == 0:
                    raw = (z['vx'] * z['alive']).sum(0) * float(z['dt']) * np.sign(v[0])
                    assert np.allclose(raw, projections, rtol=2e-5, atol=1e-6)
                    raw_mae = (np.abs(z['vx']-v[0])*z['alive']).sum(0) / z['alive'].sum(0)
                    assert np.allclose(raw_mae, errs, rtol=2e-5, atol=1e-6)
                R = projections / (speed * duration) if projections is not None else None
                success = int(np.sum(z['alive_end'] & (R >= .8) & (R <= 1.2) & (errs <= .2*speed))) if R is not None else None
                cells.append({'group':group,'level':level,'mode':mode,'command':name,'seed':seed,
                              'survival':r['alive_envs_at_end'],
                              'projection_m':float(np.median(projections)) if projections is not None else None,
                              'R':float(np.median(R)) if R is not None else None,
                              'speed_mps':float(np.median(projections)/duration) if projections is not None else None,
                              'mae':float(np.median(errs)), 'brief_1_minus_mae_over_cmd':1-float(np.median(errs))/speed,
                              'stalled_envs':round(r['stalled_fraction_2to4s']*64),
                              'hypothetical_v2_success_count':success, 'source':str(p)})
                arrays[group, level, mode, name, seed] = (z['start_xy'], z['vx'])
            if group.startswith('g1b'):
                left, right = 'side+0.4', 'side-0.4'
            else:
                left, right = 'side+0.5', 'side-0.5'
            rows = {r['command']:r for r in cells if (r['group'],r['seed'],r['level'],r['mode']) == (group,seed,level,mode)}
            l, r = rows[left]['R'], rows[right]['R']
            S, gap = symmetry(l, r)
            pairs.append({'group':group,'level':level,'mode':mode,'seed':seed,
                          'R_left':l,'R_right':r,'S_min_max':S,'difference_over_mean':gap,
                          'signed_left_minus_right':l-r,'source':str(p)})
    for level in (0,5):
        ref = None
        for seed in SEEDS:
            sub = 'm2000seg' if seed == 42 else f'm2000rep_s{seed}'
            p = G1/sub/f'hipan_g1b_L{level}'/'map_modes.json'
            d = read(p); common(d, seed, level, p)
            if ref is None: ref = d
            compare(d, ref, 'G1b')
            assert d['command_suite'] == 'hipan_g1b' and set(d['modes']) == {'eval_gt'}
            assert len(d['modes']['eval_gt']) == 8
            map_cells(p,d,seed,level,'g1b',('eval_gt',),tuple(d['commands']))
    ref_axis = read(RUN/'eval/scores/m2000/axis_v2/axis_v2.json')
    axis_shards = [read(RUN/f'eval/scores/m2000/shards/cuda{i}/axis_v2/axis_v2.json') for i in (0,1)]
    for seed in SEEDS:
        p = RUN/'eval/scores/m2000/axis_v2/axis_v2.json' if seed == 42 else axis_root/f'seed{seed}/axis_v2.json'
        d = ref_axis if seed == 42 else read(p)
        common(d,seed,2,p); compare(d,ref_axis,'axis')
        assert d['dt_s'] == .02
        names = tuple(c['name'] for c in d['cases'])
        assert len(names) == len(set(names)) == 10
        assert names == tuple(c['name'] for c in ref_axis['cases'])
        if seed != 42:
            assert set(d['modes']) == set(MODES)
            assert (p.parent/'exit_code.txt').read_text().strip() == '0'
            assert len(list(p.parent.glob('axis_v2_*.npz'))) == 20
        for mode in MODES:
            assert set(d['modes'][mode]) == set(names)
            for name in names:
                r = d['modes'][mode][name]
                raw = p.parent/Path(r['raw_file']).name
                assert sha(raw) == r['raw_sha256']
                z = npz(raw)
                assert z['yaw'].shape == z['alive'].shape == (300,64)
                assert r['policy_steps_x_envs'] == 19200
                assert r['gt_used'] == (19200 if mode == 'eval_gt' else 0)
                assert len(r['per_env']) == 64
                complete.append({'suite':'axis_v2','seed':seed,'mode':mode,'command':name,
                                 'samples':int(z['alive'].size),'survival':int(z['alive'][-1].sum()),'source':str(raw)})
                if not name.startswith('fwd'): continue
                assert not z['heading_pre'].any()
                assert np.allclose(z['cmd_post'][:,:,2][z['alive'].astype(bool)],0)
                signed = net_yaw(z['yaw'],z['start_yaw'],z['alive'])
                expected = np.array([e['yaw_signed_accum_rad'] for e in r['per_env']])
                assert np.allclose(signed,expected,atol=3e-6)
                yaw_rows.append({'seed':seed,'mode':mode,'command':name,'survival':int(z['alive'][-1].sum()),
                                 'signed_median_rad':float(np.median(signed)),
                                 'abs_net_median_rad':float(np.median(np.abs(signed))),
                                 'abs_net_p90_rad':float(np.quantile(np.abs(signed),.9)),
                                 'source':str(raw),'device':(next(s['run_identity']['device'] for s in axis_shards if mode in s['modes']) if seed == 42 else d['run_identity']['device'])})
                arrays['axis',2,mode,name,seed] = (np.c_[z['start_xy'], z['start_yaw']],z['yaw'])
    ref_sides = read(RUN/'eval/scores/m2000/map64/map_modes.json') if sides_root else None
    for seed in (SEEDS if sides_root else ()):
        p = RUN/'eval/scores/m2000/map64/map_modes.json' if seed == 42 else sides_root/f'seed{seed}/map_modes.json'
        d = ref_sides if seed == 42 else read(p)
        common(d,seed,'mixed012',p); compare(d,ref_sides,'sides05')
        if seed != 42:
            assert (p.parent/'exit_code.txt').read_text().strip() == '0'
            assert set(d['modes']) == set(MODES)
            assert len(list(p.parent.glob('env_arrays_*.npz'))) == 4
            assert all(set(v) == {'side+0.5','side-0.5'} for v in d['modes'].values())
        map_cells(p,d,seed,'mixed012','sides05',MODES,('side+0.5','side-0.5'))
    distinct=[]
    groups = sorted({k[:-1] for k in arrays})
    for key in groups:
        for a,b in itertools.combinations(SEEDS,2):
            aa,bb=arrays[key+(a,)],arrays[key+(b,)]
            assert not np.array_equal(aa[0],bb[0]), (key,a,b,'reset samples repeated')
            assert not np.array_equal(aa[1],bb[1]), (key,a,b,'motion samples repeated')
            distinct.append({'group':str(key),'seed_a':a,'seed_b':b,
                             'reset_max_abs_delta':float(np.max(np.abs(aa[0]-bb[0]))),
                             'trace_max_abs_delta':float(np.max(np.abs(aa[1]-bb[1]))),
                             'reset_sha_a':digest(aa[0]),'reset_sha_b':digest(bb[0]),
                             'trace_sha_a':digest(aa[1]),'trace_sha_b':digest(bb[1])})
    def csvout(name,rows):
        assert rows,name
        with (out/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    csvout('cells.csv',cells);csvout('symmetry.csv',pairs);csvout('yaw.csv',yaw_rows)
    csvout('completeness.csv',complete);csvout('seed_array_distinct.csv',distinct)
    for name,rows in [('identity.json',identity),('evidence_sha256.json',evidence)]:
        (out/name).write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    ranges=[]
    for rows,keys,metrics in ((cells,('group','level','mode','command'),('R','mae','stalled_envs','survival','hypothetical_v2_success_count')),
                              (pairs,('group','level','mode'),('S_min_max','difference_over_mean','R_left','R_right')),
                              (yaw_rows,('mode','command'),('signed_median_rad','abs_net_median_rad','abs_net_p90_rad'))):
        for key in sorted({tuple(r[k] for k in keys) for r in rows}):
            subset={r['seed']:r for r in rows if tuple(r[k] for k in keys)==key}
            assert set(subset)==set(SEEDS)
            for metric in metrics:
                vals=[subset[s][metric] for s in SEEDS]
                if any(v is None for v in vals):continue
                ranges.append({'cell':'/'.join(map(str,key)),'metric':metric,
                               **{f'seed{s}':subset[s][metric] for s in SEEDS},
                               'min':min(vals),'max':max(vals),'width':max(vals)-min(vals)})
    csvout('ranges.csv',ranges)
    lines=['# m2000 세 시드 재계산 표', '', '> 분류: A/평가 · 일반화 벤치마크 · 지표',
           '> 작성: analyst-lx · '+dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
           '> 근거: evidence_sha256.json · 답 아는 입력과 원자료 대조 CPU 검사',
           '> 요지: 시작 64 env를 유지한 시드별 통계와 관측된 반복 범위. 신뢰구간 아님.',
           '> 상태: 확인됨 · 숫자는 스크립트가 생성', '',
           '| 칸 | 지표 | seed42 | seed7 | seed13 | 최소 | 최대 | 폭 |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in ranges:
        lines.append('| '+r['cell']+' | '+r['metric']+' | '+' | '.join(f'{r[k]:.6f}' for k in ('seed42','seed7','seed13','min','max','width'))+' |')
    lines += ['',f'axis-v2 확인: {len(complete)}칸(기준 seed42 GT/PRED 포함). 새 두 시드 40칸 전체 NPZ SHA · 300×64 모양 · 모드 소비 수 대조.',
              f'map64/G1b {len(cells)}칸, 대칭 {len(pairs)}쌍, Y1 {len(yaw_rows)}칸. 배열 차이 {len(distinct)}쌍 확인.',
              'side projection은 원 JSON의 env별 속도 투영 적분이다. NPZ에는 vy 시계열이 없어 옆 적분의 독립 재적분은 불가하다. 전진은 NPZ vx와 JSON을 대조했다.']
    if not sides_root:
        lines += ['', 'S2 ±0.5: 미완료. 첫 반복은 L2로 원 배치를 잘못 지정해 최종 JSON 없이 끝남. 수정 명령의 L0~2 혼합 반복 대기. 수치 없음으로 기록.']
    (out/'TABLES.md').write_text('\n'.join(lines)+'\n')
    idx={(r['cell'],r['metric']):r for r in ranges}
    def span(cell,metric,scale=1):
        r=idx[cell,metric]
        return f"{r['min']*scale:.4f}~{r['max']*scale:.4f}"
    summary=lines[:8]+['', '## S1 · 느린 전진, GT, 연속 지형', '',
        '| 레벨 | 명령 m/s | 진행 R 범위 | R 폭 | 정체 env 수 | 제안 성공 수 |',
        '|---|---:|---:|---:|---:|---:|']
    for level in (0,5):
        for name in ('fwd0.1','fwd0.2'):
            key=f'g1b/{level}/eval_gt/{name}'
            summary.append(f"| L{level} | {name[3:]} | {span(key,'R')} | {idx[key,'R']['width']:.4f} | {span(key,'stalled_envs')} | {span(key,'hypothetical_v2_success_count')} |")
    summary+=['', '## S2 · 각 방향의 실제 진행과 대칭', '',
        '| 조건 | 왼쪽 R 범위 | 오른쪽 R 범위 | S=min/max 범위 | 차/평균 % 범위 | S 폭 |',
        '|---|---:|---:|---:|---:|---:|']
    pair_keys=[('g1b/0/eval_gt','±0.4 · L0 · GT'),('g1b/5/eval_gt','±0.4 · L5 · GT')]
    if sides_root:pair_keys += [('sides05/mixed012/eval_gt','±0.5 · L0~2 · GT'),('sides05/mixed012/eval_pred','±0.5 · L0~2 · PRED')]
    for key,label in pair_keys:
        summary.append(f"| {label} | {span(key,'R_left')} | {span(key,'R_right')} | {span(key,'S_min_max')} | {span(key,'difference_over_mean',100)} | {idx[key,'S_min_max']['width']:.4f} |")
    summary+=['', '## Y1 · 6초 순방향 변화 절댓값, L2', '',
        '| 지도 | 명령 m/s | 중앙값 범위 rad | 중앙값 폭 rad | p90 범위 rad | p90 폭 rad |',
        '|---|---:|---:|---:|---:|---:|']
    for mode in MODES:
        for name in ('fwd0.5','fwd1.0'):
            key=f'{mode}/{name}'
            summary.append(f"| {mode} | {name[3:]} | {span(key,'abs_net_median_rad')} | {idx[key,'abs_net_median_rad']['width']:.4f} | {span(key,'abs_net_p90_rad')} | {idx[key,'abs_net_p90_rad']['width']:.4f} |")
    summary+=['', '각 범위는 seed42/7/13에서 얻은 세 개의 집계값의 최솟값~최댓값이다. env를 합쳐 192개 독립 학습으로 보지 않는다.',
              '진행 R은 살아 있는 구간의 명령 방향 속도 적분 / (명령 크기 × 예정 6초). 생존으로 분모를 줄이지 않는다.',
              '제안 성공 수는 생존 AND env별 R 0.8~1.2 AND MAE≤명령의20%를 이 자료에 계산한 값이며 승인된 기존 판정의 변경이 아니다.',
              '첫 옆 L2 오류 실행은 제외했다. 수정 실행은 원래 혼합 배치와 같으며 단계/학습 설정을 바꾸지 않았다.']
    (out/'SUMMARY.md').write_text('\n'.join(summary)+'\n')
    print(json.dumps({'map_cells':len(cells),'axis_cells':len(complete),'yaw_cells':len(yaw_rows),
                      'distinct_pairs':len(distinct),'source_files':len(evidence),'self_test':'PASS',
                      'sides05_status':'complete' if sides_root else 'pending','out':str(out)}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--axis-root',type=Path,default=Path('/home/jay/data/foothold/s2_lab/e1_yaw_repeat_20261113/m2000_20261113_104730'))
    p.add_argument('--sides-root',type=Path,help='Corrected mixed L0/1/2 repeat; omitted means S2 ±0.5 explicitly pending')
    a=p.parse_args();main(a.out,a.axis_root,a.sides_root)
