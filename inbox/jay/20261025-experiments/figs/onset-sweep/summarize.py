"""Onset sweep table: B 1000~1500, EX-30/31 1550~2000, 64 env fixed terrain (c3884d68).

Sources: this folder's <tag>/map_modes.json, plus existing evals for B1500 / m1750 (impl-w2/logs_gate/eval)
and m2000 (impl-t5/logs/w3p2_ex-3*_m2000_*/eval64). Writes onset_table.csv, onset_table.md, onset_turn.png.
"""
import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXISTING = {
    "b_m1500": "C:/mai/wt/foothold-lab/impl-w2/logs_gate/eval/parent_b1500/map_modes.json",
    "ex30_m1750": "C:/mai/wt/foothold-lab/impl-w2/logs_gate/eval/ex30_1750/map_modes.json",
    "ex31_m1750": "C:/mai/wt/foothold-lab/impl-w2/logs_gate/eval/ex31_1750/map_modes.json",
}
for n in ("30", "31"):
    hits = glob.glob(f"C:/mai/wt/foothold-lab/impl-t5/logs/w3p2_ex-{n}_m2000_*/eval64/map_modes.json")
    if hits:
        EXISTING[f"ex{n}_m2000"] = hits[0]

TERRAIN = "c3884d686592596ee6ac7b2cdfc94e0b1d3f6d84dbca66c52ad20a0400e2"


def load(tag, path):
    d = json.load(open(path, encoding="utf-8"))
    assert d["fixed_terrain"]["assignment_sha256"].startswith(TERRAIN[:12]), (tag, path)
    run, it = tag.split("_m")
    row = {"run": run, "iter": int(it), "source": path}
    for mode in ("eval_gt", "eval_pred"):
        m = d["modes"].get(mode)
        if m is None:
            continue
        k = "gt" if mode == "eval_gt" else "pred"
        row[f"{k}_left"] = m["spin+1.2"]["yaw_follow_median"]
        row[f"{k}_right"] = m["spin-1.2"]["yaw_follow_median"]
        row[f"{k}_left_alive"] = m["spin+1.2"]["alive_envs_at_end"]
        row[f"{k}_right_alive"] = m["spin-1.2"]["alive_envs_at_end"]
        row[f"{k}_fwd1_m"] = m["fwd1.0"]["body_vx_integral_median_m"]
        row[f"{k}_fwd1_alive"] = m["fwd1.0"]["alive_envs_at_end"]
    return row


rows = []
for p in glob.glob(os.path.join(HERE, "*", "map_modes.json")):
    rows.append(load(os.path.basename(os.path.dirname(p)), p))
have = {(r["run"], r["iter"]) for r in rows}
for tag, p in EXISTING.items():
    run, it = tag.split("_m")
    if (run, int(it)) not in have:
        rows.append(load(tag, p))
rows.sort(key=lambda r: (r["run"], r["iter"]))

cols = ["run", "iter", "gt_left", "gt_right", "pred_left", "pred_right", "gt_left_alive", "gt_right_alive",
        "gt_fwd1_m", "gt_fwd1_alive", "pred_fwd1_m", "source"]
with open(os.path.join(HERE, "onset_table.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

fmt = lambda v: "" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
with open(os.path.join(HERE, "onset_table.md"), "w", encoding="utf-8") as f:
    f.write("| 판 | 회차 | 정답 좌 | 정답 우 | 복원 좌 | 복원 우 | 좌 생존 | 우 생존 | 전진 1.0 m (정답) |\n|---|---|---|---|---|---|---|---|---|\n")
    for r in rows:
        f.write("| " + " | ".join(fmt(r.get(c)) for c in ["run", "iter", "gt_left", "gt_right", "pred_left", "pred_right",
                                                       "gt_left_alive", "gt_right_alive", "gt_fwd1_m"]) + " |\n")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    color = {"b": "#666666", "ex30": "#0f7f78", "ex31": "#d2691e"}
    b1500 = [r for r in rows if r["run"] == "b" and r["iter"] == 1500]
    for ax, side in zip(axes, ("left", "right")):
        for run in ("b", "ex30", "ex31"):
            rr = [r for r in rows if r["run"] == run and r.get(f"gt_{side}") is not None]
            if run != "b":
                rr = b1500 + rr
            ax.plot([r["iter"] for r in rr], [r[f"gt_{side}"] for r in rr], "o-", color=color[run],
                    label={"b": "B (EX-28)", "ex30": "EX-30", "ex31": "EX-31"}[run])
        ax.axvline(1500, ls="--", c="k", lw=0.8)
        ax.set_title(f"spin {'+' if side == 'left' else '-'}1.2 yaw follow (median, 64 env, GT map eval)")
        ax.set_xlabel("checkpoint iteration")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("yaw follow (1.0 = as commanded)")
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "onset_turn.png"), dpi=130)
except ImportError:
    pass
print(open(os.path.join(HERE, "onset_table.md"), encoding="utf-8").read())
