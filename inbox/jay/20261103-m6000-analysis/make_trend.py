"""EX-40 key-cell trend m500..m6000 (+ EX-41 m6250) from raw map_modes.json files."""
import json, glob, re, statistics as st, sys
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'
RUNS = sorted(glob.glob(r'C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_*/map64/map_modes.json'),
              key=lambda p: int(re.search(r'model_(\d+)_', p).group(1)))
EX41 = [(6250, r'C:/Users/AI-WS01/s2_lab/ex41_main_20261103_195435/eval/score-watch/model_250_b76f9e502167/evaluation/map64/map_modes.json')]
CELLS = [('back1.0','vx','후진 1.0'),('side+0.5','vy','옆 +0.5 (오른쪽)'),('side-0.5','vy','옆 -0.5 (왼쪽)'),('spin+1.2','wz','제자리 회전 +1.2'),('fwd1.0','vx','전진 1.0')]
KEY = {'vx':'vx_abs_error_mean_alive_mps','vy':'vy_abs_error_mean_alive_mps','wz':'wz_abs_error_mean_alive_radps'}
def read(p):
    d = json.load(open(p, encoding='utf-8'))['modes']; o = {}
    for m in ('eval_gt','probe_prop_only'):
        for c, ax, _ in CELLS:
            if c not in d.get(m, {}): continue
            pe = d[m][c]['per_env']; xs = [e[KEY[ax]] for e in pe if e.get(KEY[ax]) is not None]
            o[(m, c)] = (st.median(xs) if xs else None, sum(e['alive_at_end'] for e in pe))
    return o
pts = [(int(re.search(r'model_(\d+)_', p).group(1)), read(p)) for p in RUNS if int(re.search(r'model_(\d+)_', p).group(1)) <= 6000]
pts41 = [(n, read(p)) for n, p in EX41]
fig, axs = plt.subplots(2, 1, figsize=(16, 9), dpi=140, sharex=True)
for ax, (mode, name) in zip(axs, [('eval_gt','정답 지도'),('probe_prop_only','지도 끔')]):
    for c, a, label in CELLS:
        xs = [n for n, o in pts if (mode, c) in o and o[(mode, c)][0] is not None]
        ys = [o[(mode, c)][0] for n, o in pts if (mode, c) in o and o[(mode, c)][0] is not None]
        l, = ax.plot(xs, ys, marker='o', ms=3, label=label)
        x41 = [n for n, o in pts41 if (mode, c) in o]; y41 = [o[(mode, c)][0] for n, o in pts41 if (mode, c) in o]
        ax.plot(([xs[-1]] + x41) if xs else x41, ([ys[-1]] + y41) if ys else y41, ls='--', marker='s', color=l.get_color())
    ax.axhline(0.15, color='red', lw=1.5, ls=':'); ax.text(520, 0.152, '판정선 0.15', color='red', fontsize=10)
    for b, t in [(1500,'B1'),(3000,'B2'),(4500,'B3a'),(5000,'B3b'),(5500,'B3c'),(6000,'EX-41')]:
        ax.axvline(b, color='#999', lw=0.8); ax.text(b+20, ax.get_ylim()[1]*0.95 if ax.get_ylim()[1] < 1 else 0.3, t, fontsize=9, color='#555')
    ax.set_ylabel(f'{name}\n주축 오차 중앙값'); ax.grid(alpha=.3); ax.set_ylim(0, 0.35)
axs[0].legend(ncol=5, fontsize=10, loc='upper right')
axs[1].set_xlabel('누적 회차 (실선 EX-40 실측 · 점선 EX-41 m6250)')
fig.suptitle('계보 1: 약한 칸의 추종 오차가 학습 중 어떻게 바뀌었나 (64 env 고정 평가, 원자료 map_modes.json)', fontsize=13)
fig.tight_layout(); fig.savefig(sys.argv[1]); print('saved')
for n, o in pts:
    print(n, {k[1]: round(v[0], 3) for k, v in o.items() if k[0]=='eval_gt' and v[0] is not None})
