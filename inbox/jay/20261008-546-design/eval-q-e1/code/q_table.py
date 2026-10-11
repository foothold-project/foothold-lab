# Build the Q-E1 comparison (both checkpoints in one table) from out/m<it>_<family>/.
# Writes out/Q-E1-cells.csv (one row per family x cell, both checkpoints side by side,
# paired counts, Newcombe interval, exact McNemar), out/Q-E1-pooled.csv (7 rough
# families pooled per cell), out/Q-E1-pairing.json, and prints markdown tables.

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import q_metrics as Q  # noqa: E402

OUT = os.path.join(HERE, "out")
FAMS = ["flat", "wave", "slope_up", "slope_down", "rough_slope", "stairs_up", "stairs_down", "obstacles"]
ROUGH = FAMS[1:]
ITS = ["20000", "20499"]


def tf(v):
    return str(v) in ("True", "true", "1")


def fnum(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return x


def load(it, fam):
    d = os.path.join(OUT, f"m{it}_{fam}")
    if not os.path.exists(os.path.join(d, "cells.json")):
        return None
    with open(os.path.join(d, "episodes.csv"), encoding="utf-8") as f:
        eps = list(csv.DictReader(f))
    with open(os.path.join(d, "cells.json"), encoding="utf-8") as f:
        cells = json.load(f)
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    return eps, cells, meta


data = {(it, fam): load(it, fam) for it in ITS for fam in FAMS}
missing = [k for k, v in data.items() if v is None]
pairing = {}
for fam in FAMS:
    a, b = data[(ITS[0], fam)], data[(ITS[1], fam)]
    if a is None or b is None:
        continue
    ma, mb = a[2], b[2]
    pairing[fam] = {
        "pairing_sha256_equal": all(ma["pairing_sha256"][k] == mb["pairing_sha256"][k] for k in ma["pairing_sha256"]),
        "terrain_mesh_equal": ma["terrain_mesh"] == mb["terrain_mesh"],
        "terrain_mesh_sha256": ma["terrain_mesh"][0][2] if isinstance(ma["terrain_mesh"], list) else ma["terrain_mesh"],
        "checks_pre": [ma["checks_pre"], mb["checks_pre"]],
        "checks_run": [ma["checks_run"], mb["checks_run"]],
        "devices": [ma["devices"], mb["devices"]],
        "smi_after_env": [ma["smi_after_env"], mb["smi_after_env"]],
        "checkpoint_sha256": [ma.get("checkpoint_sha256"), mb.get("checkpoint_sha256")],
        "rollout_wall_s": [ma["rollout_wall_s"], mb["rollout_wall_s"]],
    }
with open(os.path.join(OUT, "Q-E1-pairing.json"), "w", encoding="utf-8") as f:
    json.dump({"missing": missing, "pairing": pairing}, f, indent=1)

METRICS = ["survival", "pass_rate", "pass_ci", "cell_pass", "q1m_pass_rate", "q1m_cell_pass", "q3_pass_rate",
           "mae_vx_mean", "mae_vy_mean", "mae_wz_mean", "mae_vx_p90", "mae_vy_p90", "mae_wz_p90",
           "mean_vx_mean", "mean_vy_mean", "mean_wz_mean", "move_ratio_mean", "abs_heading_err_rad_mean",
           "corridor_max_m_mean", "gate_reached", "stop_t_mean", "stop_t_p90", "stop_t_n", "stop_dist_m_mean",
           "stop_dist_m_p90", "yaw_drift_rad_mean", "post_stop_drift_m_mean", "still_frac_mean", "disp_m_mean",
           "q2_stop_only_pass", "moving_phase_q1_pass", "fall_reasons", "survived", "pass"]
rows = []
for fam in FAMS:
    a, b = data[(ITS[0], fam)], data[(ITS[1], fam)]
    if a is None or b is None:
        continue
    for sa in a[1]:
        sb = next(s for s in b[1] if s["cell"] == sa["cell"])
        rule = sa["rule"]
        ea = {int(r["episode"]): r for r in a[0] if r["cell"] == sa["cell"]}
        eb = {int(r["episode"]): r for r in b[0] if r["cell"] == sa["cell"]}
        cnt = {}
        for name, key in (("rule", rule), ("q1m", "q1m_pass"), ("surv", "survived")):
            aa = bb = cc = dd = 0
            for k in ea:
                pa, pb = tf(ea[k][key]), tf(eb[k][key])
                aa += pa and pb
                bb += pa and not pb
                cc += (not pa) and pb
                dd += (not pa) and (not pb)
            diff, lo, hi = Q.newcombe_paired(aa, bb, cc, dd)
            cnt[name] = dict(both=aa, only_20000=bb, only_20499=cc, neither=dd, diff=diff, lo=lo, hi=hi,
                             mcnemar_p=Q.mcnemar_exact(bb, cc))
        row = {"family": fam, "cell": sa["cell"], "cmd": sa["cmd"], "src": sa["src"], "rule": rule, "n": sa["n"]}
        for it, s in ((ITS[0], sa), (ITS[1], sb)):
            for m in METRICS:
                row[f"{it}_{m}"] = s.get(m)
        for name in cnt:
            for k, v in cnt[name].items():
                row[f"paired_{name}_{k}"] = v
        rows.append(row)

if rows:
    with open(os.path.join(OUT, "Q-E1-cells.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)

# pooled over rough families (episode level)
pooled = []
cells = [r["cell"] for r in rows if r["family"] == "flat"]
for cell in cells:
    out = {"cell": cell}
    for it in ITS:
        eps = []
        for fam in ROUGH:
            d = data[(it, fam)]
            if d is not None:
                eps += [r for r in d[0] if r["cell"] == cell]
        if not eps:
            continue
        rule = "q2_pass" if cell == "stop03" else "q1_pass"
        n = len(eps)
        ns = sum(tf(r["survived"]) for r in eps)
        npass = sum(tf(r[rule]) for r in eps)
        nm = sum(tf(r["q1m_pass"]) for r in eps)
        out[f"{it}_n"] = n
        out[f"{it}_survival"] = ns / n
        out[f"{it}_survival_ci"] = Q.wilson(ns, n)
        out[f"{it}_pass_rate"] = npass / n
        out[f"{it}_pass_ci"] = Q.wilson(npass, n)
        out[f"{it}_q1m_rate"] = nm / n
        for m in ("mae_vx", "mae_vy", "mae_wz", "move_ratio", "stop_t", "stop_dist_m"):
            v = np.array([fnum(r[m]) for r in eps])
            v = v[np.isfinite(v)]
            out[f"{it}_{m}_mean"] = float(v.mean()) if v.size else float("nan")
    pooled.append(out)
if pooled:
    with open(os.path.join(OUT, "Q-E1-pooled.csv"), "w", newline="", encoding="utf-8") as f:
        keys = []
        for p in pooled:
            for k in p:
                if k not in keys:
                    keys.append(k)
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for p in pooled:
            w.writerow(p)

print("missing:", missing)
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("pairing_sha256_equal", "terrain_mesh_equal")}
                  for k, v in pairing.items()}))


def pct(x):
    return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{100 * x:.0f}"


def f3(x):
    return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.3f}"


print()
for r in rows:
    a, b = ITS
    print(f'{r["family"]:11s} {r["cell"]:8s} surv {pct(r[a + "_survival"])}/{pct(r[b + "_survival"])}'
          f' pass {pct(r[a + "_pass_rate"])}/{pct(r[b + "_pass_rate"])}'
          f' q1m {pct(r[a + "_q1m_pass_rate"])}/{pct(r[b + "_q1m_pass_rate"])}'
          f' mae {f3(r[a + "_mae_vx_mean"])},{f3(r[a + "_mae_vy_mean"])},{f3(r[a + "_mae_wz_mean"])}'
          f' / {f3(r[b + "_mae_vx_mean"])},{f3(r[b + "_mae_vy_mean"])},{f3(r[b + "_mae_wz_mean"])}'
          f' move {f3(r[a + "_move_ratio_mean"])}/{f3(r[b + "_move_ratio_mean"])}'
          f' d={r["paired_rule_diff"]:+.2f} p={r["paired_rule_mcnemar_p"]:.2g}')
print()
for p in pooled:
    a, b = ITS
    print(f'POOLED {p["cell"]:8s} n {p.get(a + "_n")} surv {pct(p.get(a + "_survival"))}/{pct(p.get(b + "_survival"))}'
          f' pass {pct(p.get(a + "_pass_rate"))}/{pct(p.get(b + "_pass_rate"))}'
          f' q1m {pct(p.get(a + "_q1m_rate"))}/{pct(p.get(b + "_q1m_rate"))}')
