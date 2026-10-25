"""S-B50 · S-B10 중간 학습 곡선 (map_switch.jsonl, 켬 · 끔 따로). lead 10/26 아침. 학습 신호일 뿐 판정이 아니다 (판정은 카드의 평가)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUNS = {
    "S-B50 (p 0.5)": Path("C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-25_23-45-04_sb-main/map_switch.jsonl"),
    "S-B10 (p 0.1)": Path("C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main/map_switch.jsonl"),
}
KEYS = [("ep_reward_mean", "episode reward"), ("ep_length_mean", "episode length (steps)"),
        ("terrain_level_mean", "terrain level"), ("track_lin_vel_per_s", "track_lin_vel per s"),
        ("track_ang_vel_per_s", "track_ang_vel per s")]
W = 50
OUT = Path(__file__).parent


def load(p):
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows


def win(rows, side, key):
    xs, ys = [], []
    for s in range(0, rows[-1]["it"] + 1, W):
        vals = [r[side][key] for r in rows if s <= r["it"] < s + W and r[side].get("episodes_ended", 0) > 0 and r[side].get(key) is not None]
        if vals:
            xs.append(s + W / 2); ys.append(sum(vals) / len(vals))
    return xs, ys


data = {n: load(p) for n, p in RUNS.items()}
fig, axes = plt.subplots(1, len(KEYS), figsize=(22, 4.2))
table = []
for ax, (k, label) in zip(axes, KEYS):
    for (n, rows), c in zip(data.items(), ("tab:blue", "tab:orange")):
        for side, ls in (("on", "-"), ("off", "--")):
            x, y = win(rows, side, k)
            ax.plot(x, y, ls, color=c, label=f"{n} map {side}")
    ax.set_title(label); ax.set_xlabel("iteration"); ax.grid(alpha=.3)
axes[0].legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "sb_mid_curves.png", dpi=110)
for n, rows in data.items():
    last = rows[-1]["it"]
    lo = max(0, last - W + 1)
    seg = [r for r in rows if r["it"] >= lo]
    row = {"run": n, "last_it": last, "window": f"{lo}-{last}",
           "off_frac_steps_mean": sum(r["off_frac_steps"] for r in seg) / len(seg)}
    for side in ("on", "off"):
        for k, _ in KEYS:
            v = [r[side][k] for r in seg if r[side].get("episodes_ended", 0) > 0 and r[side].get(k) is not None]
            row[f"{side}_{k}"] = sum(v) / len(v) if v else None
    table.append(row)
(OUT / "sb_mid_last_window.json").write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
for r in table:
    print(r["run"], r["window"], "off_frac", round(r["off_frac_steps_mean"], 3))
    for k, _ in KEYS:
        print(f"   {k:22s} on {r['on_'+k]:.3f}  off {r['off_'+k]:.3f}")
