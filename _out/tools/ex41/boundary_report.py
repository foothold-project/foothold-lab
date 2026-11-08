"""EX-41 per-boundary checklist numbers (EX41-250-LOG rule): vs m6000 and previous boundary.

Usage: python boundary_report.py <run_root> <local_iter>
  run_root = the s2_lab/ex41_main_<stamp> folder (holds eval/ and main/<run>/).
Prints the 10-item table plus the boundary application row (DR scale · stage · reason) so the
report always shows whether DR moved as planned (11/04: DR sat at 0.575 for 750 updates unread).
"""
import glob, json, statistics as st, sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops_machine_profile import load_linux_profile, require_linux_profile

OPS_PROFILE = load_linux_profile()
require_linux_profile(OPS_PROFILE)

RUN = Path(sys.argv[1]).as_posix().rstrip('/')
M6000 = r'C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json'
if OPS_PROFILE:
    M6000 = OPS_PROFILE["paths"]["baseline_m6000"]
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
    mm = glob.glob(f'{RUN}/eval/score-watch/model_{n}_*/evaluation/map64/map_modes.json')
    return json.load(open(sc, encoding='utf-8')), cells(mm[0])


def w78(score):
    s = score['metrics']['w78_v2_periodic_sides']['cells']['eval_gt']; o = {}
    for cell, v in s.items():
        num = den = alive = envs = 0
        for r in v['by_terrain_kind'].values():
            num += r['drag_num']; den += r['drag_den']; alive += r['alive_at_end']; envs += r['env_count']
        o[cell] = (num / den, alive, envs)
    return o


n = int(sys.argv[2]); prev = n - 250
try:
    sc, cur = boundary(n)
except IndexError:
    # No score or no map64 for this boundary: a measurement gap, never a result (11/04 1000 · 1250).
    print(f'== EX-41 {n}: 점수 또는 map64 없음 · 측정 실패 · 결과로 쓰지 않음 · 재측정 영수증을 볼 것')
    raise SystemExit(2)
base = cells(M6000)
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
# 지도 셋(정답 eval_gt · 복원 eval_pred · 끔 probe_prop_only) 비교 · 팀장 11/06 17:2x 「지도 켬 · 끔 · 복원은 EX-41 핵심」
cmds = sorted({c for (m, c) in cur if m == 'eval_gt'})
for other, name in (('eval_pred', '복원'), ('probe_prop_only', '끔')):
    d = [(cur[(other, c)]['err'] - cur[('eval_gt', c)]['err'], c) for c in cmds
         if (other, c) in cur and cur[(other, c)]['err'] is not None and cur[('eval_gt', c)]['err'] is not None]
    if d:
        big = max(d, key=lambda x: abs(x[0]))
        alive = sum(cur[(other, c)]['alive'] for c in cmds if (other, c) in cur) - sum(cur[('eval_gt', c)]['alive'] for c in cmds)
        print(f'M 지도 {name} - 정답: 오차 차 평균 {sum(x[0] for x in d)/len(d):+.3f} · 가장 큰 차 {big[1]} {big[0]:+.3f} · 생존 합 차 {alive:+d}')
for m in ('eval_gt', 'eval_pred', 'probe_prop_only'):
    over = [c for c in cmds if (m, c) in cur and cur[(m, c)]['err'] and cur[(m, c)]['err'] > 0.15]
    print(f'M {m:15s} 판정선 넘은 명령 {len(over)} {over} · 생존 최저 {min(cur[(m, c)]["alive"] for c in cmds if (m, c) in cur)}/64')
print('5 회전 앞뒤 흔들림 vx(정답)', [f"{c} {f(base[('eval_gt',c)]['vx'])}→{f(pc.get(('eval_gt',c),{}).get('vx'))}→{f(cur[('eval_gt',c)]['vx'])}" for c in ('spin+1.2', 'spin-1.2')])
sym = sc['metrics'].get('critic_mirror_symmetry', {}).get('modes', {})
for m, rows in sym.items():
    vals = [r['symmetry'] for r in rows.values() if r.get('valid')]
    if vals: print(f'6 대칭 S {m}: 평균 {sum(vals)/len(vals):.3f} 최저 {min(vals):.3f} <0.8 {sum(v<0.8 for v in vals)}')
try:
    w = w78(sc)
except KeyError:
    w = None
if w is None:
    print('7 계단 옆 발 끌림: score HOLD (재평가 W78 에서 따로)')
else:
    L = [v[0] for k, v in w.items() if 'left' in k]; R = [v[0] for k, v in w.items() if 'right' in k]
    print(f'7 계단 옆 발 끌림 왼 {min(L):.3f}~{max(L):.3f} 오른 {min(R):.3f}~{max(R):.3f} · 생존 최저', min((v[1], k) for k, v in w.items()))
def push_line(k):
    """Item 8 (I30: m7000 · m7750 stairs push misses went unreported because this line was missing)."""
    p = Path(f'{RUN}/eval/push250/{6000 + k}.json')
    if not p.is_file():
        return f'8 밀림 m{6000 + k}: 아직 없음(밀기 감시기 대기 · 다음 점검에서 다시 볼 것)'
    d = json.load(open(p, encoding='utf-8'))
    parts = [f"{c['terrain']} {c['summary']['d171_1_5_worst_direction']['survival_fraction']:.3f}"
             f"{'' if c['summary']['d171_1_5_worst_direction']['passed'] else ' 미달'}" for c in d['children']]
    return f"8 밀림 m{6000 + k} {'통과' if d.get('d171_all_terrains_passed') else '미달'} · 1.5 최악 방향 " + ' · '.join(parts)


print(push_line(n))
if Path(f'{RUN}/eval/push250/{6000 + prev}.json').is_file():
    print('  직전', push_line(prev)[2:])
print('9 서기', sc['metrics'].get('stand_counts'), '· 무릎', [round(j['ratio'] * 100, 2) for j in sc['metrics'].get('training_knee_effort', {}).get('joints', {}).values()], '%')
RUNDIR = Path(glob.glob(f'{RUN}/main/*/train_start_status.json')[0]).parent.as_posix()
st_ = json.load(open(f'{RUNDIR}/train_start_status.json'))
print('10 학습', st_.get('iter'), *(f"{round(st_[k], 1)}{u}" for k, u in (('iter_s', ' s'), ('mean_reward', ' 보상'), ('mean_episode_length', ' 길이')) if isinstance(st_.get(k), (int, float))), '· 상태', st_.get('state', ''))
app = [json.loads(l) for l in open(f'{RUNDIR}/ex41_application.jsonl', encoding='utf-8') if l.strip()]
row = next((r for r in reversed(app) if r.get('iteration') == n + 1), None)
if row is None:
    print('11 경계 적용 기록 없음 · n+1 =', n + 1, '(경계가 아직 적용되지 않았거나 기록이 빠짐)')
else:
    dr = row['after'].get('dr', {})
    print('11 경계 적용', row['iteration'], row['stage_before'], '→', row['stage_after'], '·', row['status'],
          '· 사유', row.get('reason'), '· DR', dr.get('scale'), '→ 목표', dr.get('target_scale'))
# 12 lr · KL over this boundary's 250 updates (11/04: S2a sat at the 1e-5 floor for 233 of its
# first 500 updates with KL probe > 0.05 85 times; nobody saw it because no report showed it).
try:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    lo, hi, floor = n - 250, n, 1e-5
    lr, kl = {}, {}
    for f in sorted(glob.glob(f'{RUNDIR}/events.out.tfevents.*')):
        acc = EventAccumulator(f, size_guidance={'scalars': 0}); acc.Reload()
        tags = acc.Tags()['scalars']
        for tag, dst in (('Loss/learning_rate', lr), ('Loss/kl_probe/ppo_mean', kl)):
            if tag in tags:
                for ev in acc.Scalars(tag):
                    if lo < ev.step <= hi:
                        dst[ev.step] = ev.value  # later files win on resumed (repeated) steps
    if lr:
        at_floor = sum(v <= floor * 1.0001 for v in lr.values())
        big_kl = sum(v > 0.05 for v in kl.values())
        print(f'12 학습률 · KL ({lo + 1}~{hi}, {len(lr)} 회): 바닥(1e-5) {at_floor} 회 · KL probe > 0.05 {big_kl} 회'
              f' · lr 중앙 {st.median(lr.values()):.2e}')
    else:
        print('12 학습률 · KL: TensorBoard 기록 없음(미측)')
except ImportError:
    print('12 학습률 · KL: tensorboard 없음(isaac311 로 돌릴 것)')
