"""EX-41 per-boundary checklist numbers (EX41-250-LOG rule): vs m6000 and previous boundary.

Usage: python ex41_boundary_report.py <local_iter>
"""
import glob, json, statistics as st, sys

RUN = r'C:/Users/AI-WS01/s2_lab/ex41_main_20261103_195435'
M6000 = r'C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json'
KEY = {'vx': 'vx_abs_error_mean_alive_mps', 'vy': 'vy_abs_error_mean_alive_mps', 'wz': 'wz_abs_error_mean_alive_radps'}


def axis(cmd):
    return 'wz' if cmd.startswith('spin') else ('vy' if cmd.startswith('side') else 'vx')


def cells(path):
    d = json.load(open(path, encoding='utf-8'))['modes']; out = {}
    for m, cs in d.items():
        for c, v in cs.items():
            pe = v['per_env']
            def med(k):
                xs = [e[k] for e in pe if e.get(k) is not None]
                return st.median(xs) if xs else None
            out[(m, c)] = dict(alive=sum(e['alive_at_end'] for e in pe), err=med(KEY[axis(c)]), vx=med(KEY['vx']))
    return out


def boundary(n):
    sc = glob.glob(f'{RUN}/eval/scores/score_{n}_*.json')[0]
    mm = glob.glob(f'{RUN}/eval/score-watch/model_{n}_*/evaluation/map64/map_modes.json')[0]
    return json.load(open(sc, encoding='utf-8')), cells(mm)


def w78(score):
    s = score['metrics']['w78_v2_periodic_sides']['cells']['eval_gt']; o = {}
    for cell, v in s.items():
        num = den = alive = envs = 0
        for r in v['by_terrain_kind'].values():
            num += r['drag_num']; den += r['drag_den']; alive += r['alive_at_end']; envs += r['env_count']
        o[cell] = (num / den, alive, envs)
    return o


n = int(sys.argv[1]); prev = n - 250
sc, cur = boundary(n); base = cells(M6000)
try:
    _, pc = boundary(prev)
except IndexError:
    pc = {}
f = lambda x: '  -  ' if x is None else f'{x:.3f}'
print(f'== EX-41 {n} (누적 m{6000+n}) · maintenance_pass {sc.get("maintenance_pass")} · safety_stop {sc.get("safety_stop")}')
worst = min(cur.items(), key=lambda kv: kv[1]['alive'])
print('1 생존 최저', worst[0], worst[1]['alive'], '/64 · m6000 대비 -2 넘게 나빠진 칸:',
      [k for k in cur if k in base and cur[k]['alive'] < base[k]['alive'] - 2])
print('2 판정선 0.15 넘은 칸:', [(k, round(v['err'], 3)) for k, v in cur.items() if v['err'] and v['err'] > 0.15])
for c in ('back0.5', 'back1.0', 'side+0.5', 'side-0.5', 'spin+1.2', 'spin-1.2', 'fwd1.0'):
    row = [f"{m[:8]} {f(base.get((m,c),{}).get('err'))}→{f(pc.get((m,c),{}).get('err'))}→{f(cur[(m,c)]['err'])} ({cur[(m,c)]['alive']})"
           for m in ('eval_gt', 'eval_pred', 'probe_prop_only')]
    print(f'  {c:9s}', ' | '.join(row))
print('5 회전 앞뒤 흔들림 vx(정답)', [f"{c} {f(base[('eval_gt',c)]['vx'])}→{f(pc.get(('eval_gt',c),{}).get('vx'))}→{f(cur[('eval_gt',c)]['vx'])}" for c in ('spin+1.2', 'spin-1.2')])
sym = sc['metrics'].get('critic_mirror_symmetry', {}).get('modes', {})
for m, rows in sym.items():
    vals = [r['symmetry'] for r in rows.values() if r.get('valid')]
    if vals: print(f'6 대칭 S {m}: 평균 {sum(vals)/len(vals):.3f} 최저 {min(vals):.3f} <0.8 {sum(v<0.8 for v in vals)}')
w = w78(sc)
L = [v[0] for k, v in w.items() if 'left' in k]; R = [v[0] for k, v in w.items() if 'right' in k]
print(f'7 계단 옆 발 끌림 왼 {min(L):.3f}~{max(L):.3f} 오른 {min(R):.3f}~{max(R):.3f} · 생존 최저', min((v[1], k) for k, v in w.items()))
print('9 서기', sc['metrics'].get('stand_counts'), '· 무릎', [round(j['ratio'] * 100, 2) for j in sc['metrics']['training_knee_effort']['joints'].values()], '%')
st_ = json.load(open(f'{RUN}/main/EX-41-B-main_20261103_195435/train_start_status.json'))
print('10 학습', st_['iter'], round(st_['iter_s'], 1), 's · 보상', round(st_['mean_reward'], 1), '· 길이', round(st_['mean_episode_length'], 1))
