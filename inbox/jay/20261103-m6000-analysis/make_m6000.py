"""m6000 39-cell survival/error heatmap from the raw map_modes.json (no hand numbers)."""
import json, statistics as st, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'
SRC = r'C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json'
OUT = sys.argv[1]
d = json.load(open(SRC, encoding='utf-8'))['modes']
CMDS = ['fwd0.5','fwd1.0','back0.5','back1.0','side+0.5','side-0.5','diag-fwd+side+','diag-fwd+side-','diag-back+side+','diag-back+side-','spin+1.2','spin-1.2','stop']
MODES = [('eval_gt','정답 지도'),('eval_pred','복원 지도'),('probe_prop_only','지도 끔')]
def axis_err(cmd, pe):
    key = 'wz_abs_error_mean_alive_radps' if cmd.startswith('spin') else ('vy_abs_error_mean_alive_mps' if cmd.startswith('side') else 'vx_abs_error_mean_alive_mps')
    xs = [e[key] for e in pe if e.get(key) is not None]
    return st.median(xs) if xs else float('nan')
err = [[axis_err(c, d[m][c]['per_env']) for c in CMDS] for m, _ in MODES]
alive = [[sum(1 for e in d[m][c]['per_env'] if e['alive_at_end']) for c in CMDS] for m, _ in MODES]
fig, ax = plt.subplots(figsize=(18, 4.6), dpi=150)
im = ax.imshow(err, cmap='RdYlGn_r', vmin=0.0, vmax=0.20, aspect='auto')
for i in range(3):
    for j in range(len(CMDS)):
        e = err[i][j]; bad = e > 0.15
        ax.text(j, i, f'{e:.3f}\n{alive[i][j]}/64', ha='center', va='center', fontsize=10,
                fontweight='bold' if bad else 'normal', color='black')
        if bad: ax.add_patch(plt.Rectangle((j-.5, i-.5), 1, 1, fill=False, ec='red', lw=3))
ax.set_xticks(range(len(CMDS)), CMDS, rotation=20); ax.set_yticks(range(3), [n for _, n in MODES])
ax.set_title('m6000 (EX-40 끝 · EX-41 부모) 39 칸: 위 = 주축 추종 오차 중앙값(전후 vx · 옆 vy · 회전 wz), 아래 = 끝까지 생존 / 64 · 빨간 테두리 = 판정선 0.15 초과', fontsize=12)
cb = fig.colorbar(im, ax=ax, fraction=0.02); cb.set_label('오차 m/s · rad/s')
fig.tight_layout(); fig.savefig(OUT); print('saved', OUT)
for (m, n), row, ar in zip(MODES, err, alive):
    print(n, [f'{c}:{e:.3f}/{a}' for c, e, a in zip(CMDS, row, ar)])
