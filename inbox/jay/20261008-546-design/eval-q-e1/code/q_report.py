# Combine two checkpoint runs (same families, cells, seed) into one comparison.
# Usage: python q_report.py --a out/<tagA> [out/<tagA2> ...] --b out/<tagB> [...] --out out/compare_<name>
# Writes compare_cells.csv (one row per family x cell, both checkpoints side by side,
# paired McNemar / Newcombe on the cell rule) and compare_meta.json (pairing checks).

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import q_metrics as Q  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--a", nargs="+", required=True)
ap.add_argument("--b", nargs="+", required=True)
ap.add_argument("--label_a", default="20000")
ap.add_argument("--label_b", default="20499")
ap.add_argument("--out", required=True)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)


def load(dirs):
    eps, cells, metas = [], [], []
    for d in dirs:
        with open(os.path.join(d, "episodes.csv"), encoding="utf-8") as f:
            eps += list(csv.DictReader(f))
        with open(os.path.join(d, "cells.json"), encoding="utf-8") as f:
            cells += json.load(f)
        with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
            metas.append(json.load(f))
    return eps, cells, metas


ea, ca, ma = load(args.a)
eb, cb, mb = load(args.b)

pair = []
for x, y in zip(ma, mb):
    pair.append({
        "families": [x["families"], y["families"]],
        "pairing_sha256_equal": {k: x["pairing_sha256"][k] == y["pairing_sha256"][k] for k in x["pairing_sha256"]},
        "terrain_mesh_equal": x["terrain_mesh"] == y["terrain_mesh"],
        "terrain_origins_equal": x["terrain_origins_sha256"] == y["terrain_origins_sha256"],
        "checkpoint_sha256": [x.get("checkpoint_sha256"), y.get("checkpoint_sha256")],
    })


def key(r):
    return (r["family"], r["cell"], int(r["episode"]))


def tf(v):
    return v in ("True", "true", "1", True)


ia = {key(r): r for r in ea}
ib = {key(r): r for r in eb}
out = []
for sa in ca:
    sb = next(s for s in cb if s["family"] == sa["family"] and s["cell"] == sa["cell"])
    rule = sa["rule"]
    ks = [k for k in ia if k[0] == sa["family"] and k[1] == sa["cell"]]
    a = b = c = d = 0
    for k in ks:
        pa, pb = tf(ia[k][rule]), tf(ib[k][rule])
        a += pa and pb
        b += pa and not pb
        c += (not pa) and pb
        d += (not pa) and (not pb)
    diff, lo, hi = Q.newcombe_paired(a, b, c, d)
    row = {
        "family": sa["family"], "cell": sa["cell"], "cmd": sa["cmd"], "src": sa["src"], "rule": rule, "n": sa["n"],
    }
    for lab, s in ((args.label_a, sa), (args.label_b, sb)):
        row[f"{lab}_survival"] = s["survival"]
        row[f"{lab}_pass_rate"] = s["pass_rate"]
        row[f"{lab}_pass_ci"] = s["pass_ci"]
        row[f"{lab}_cell_pass"] = s["cell_pass"]
        for m in ("mae_vx_mean", "mae_vy_mean", "mae_wz_mean", "mean_vx_mean", "mean_vy_mean", "mean_wz_mean",
                  "stop_t_mean", "stop_t_n", "stop_dist_m_mean", "yaw_drift_rad_mean", "corridor_max_m_mean",
                  "progress_m_mean", "heading_err_rad_mean", "disp_m_mean", "still_frac_mean", "gate_reached",
                  "move_ratio_mean", "q1m_pass_rate", "q1m_cell_pass", "survived", "pass"):
            row[f"{lab}_{m}"] = s.get(m)
        row[f"{lab}_q3_pass_rate"] = s.get("q3_pass_rate")
        row[f"{lab}_q2_stop_only_pass"] = s.get("q2_stop_only_pass")
        row[f"{lab}_moving_phase_q1_pass"] = s.get("moving_phase_q1_pass")
        row[f"{lab}_fall_reasons"] = s["fall_reasons"]
    row["paired_a_both"], row["paired_b_only_A"], row["paired_c_only_B"], row["paired_d_neither"] = a, b, c, d
    row["diff_A_minus_B"], row["diff_ci_lo"], row["diff_ci_hi"] = diff, lo, hi
    row["mcnemar_p"] = Q.mcnemar_exact(b, c)
    out.append(row)

with open(os.path.join(args.out, "compare_cells.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    for r in out:
        w.writerow(r)
with open(os.path.join(args.out, "compare_meta.json"), "w", encoding="utf-8") as f:
    json.dump({"a": args.a, "b": args.b, "pairing": pair}, f, indent=1)
print(json.dumps(pair, indent=1))
for r in out:
    la, lb = args.label_a, args.label_b
    print(f'{r["family"]:12s} {r["cell"]:8s} {r["rule"]}  {la}: surv {r[la + "_survival"]:.2f} pass {r[la + "_pass_rate"]:.2f}'
          f'  {lb}: surv {r[lb + "_survival"]:.2f} pass {r[lb + "_pass_rate"]:.2f}  diff {r["diff_A_minus_B"]:+.2f}'
          f' [{r["diff_ci_lo"]:+.2f},{r["diff_ci_hi"]:+.2f}] p={r["mcnemar_p"]:.3g}')
