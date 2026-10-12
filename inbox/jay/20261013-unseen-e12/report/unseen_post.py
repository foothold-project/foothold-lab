# UNSEEN-E12 tables from the raw outputs of the unseen10 runs (out/un_<run>_m<it>_<terrain>_<cell>/).
# Per episode (episodes.csv, q_post): survived, Q1 (tracking, current definition), Q3 (4 m gate + 0.30 m corridor),
# progress_m, fall reason. Added here: «crossed» = while alive the base got past the end of the terrain's obstacle zone
# measured from the tile centre along +x (meta["obstacle_zone_m"], computed in q_eval by the lab's
# sim/eval/terrains.obstacle_zone_m at the run's difficulty and tile size). Writes out/UNSEEN-cells.csv,
# out/UNSEEN-tables.md, out/UNSEEN-summary.json. Usage: python unseen_post.py
import csv
import glob
import json
import math
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
TERRAINS = ["discrete_obstacles", "wave", "stepping_stones", "gap", "pit", "rails", "star", "floating_ring", "repeated_boxes", "repeated_cylinders"]
# MoE-CTS (E1 / E2) training terrains, from the run's params/env.yaml (proportion > 0): wave (0.05) · obstacles =
# HfDiscreteObstacles (0.20) · slope_up / slope_down / rough_slope / stairs_up / stairs_down / flat. stepping_stones and
# gap are defined with proportion 0.0 (no tile). Parameters differ from v2's unseen10 versions.
TRAINED_KIND = {"wave": "학습함 (같은 종류 · 다른 매개변수)", "discrete_obstacles": "학습함 (같은 종류 · 다른 매개변수)",
                "stepping_stones": "정의만 있음 (학습 비율 0)", "gap": "정의만 있음 (학습 비율 0)"}
DT = 0.02
tf = lambda v: str(v) in ("True", "true", "1")  # noqa: E731


def load(tag):
    d = os.path.join(OUT, tag)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    eps = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
    z = np.load(os.path.join(d, "traj.npz"))
    org = np.load(os.path.join(d, "env_origins.npy"))
    return meta, eps, z["traj"], org


rows = []
for d in sorted(glob.glob(os.path.join(OUT, "un_e[12]_m*_*"))):
    tag = os.path.basename(d)
    m = re.match(r"un_(e[12])_m(\d+)_(.+)_(fwd\d\d)$", tag)
    if not m or not os.path.exists(os.path.join(d, "cells.json")):
        continue
    run, it, fam, cell = m.group(1).upper(), m.group(2), m.group(3), m.group(4)
    meta, eps, traj, org = load(tag)
    zone = meta.get("obstacle_zone_m", {}).get(fam)
    zs, ze, basis = (zone if zone else (None, None, "missing"))
    n = len(eps)
    crossed, prog, falls, reasons = 0, [], 0, {}
    for r in eps:
        e = int(r["env"])
        surv = tf(r["survived"])
        j_last = traj.shape[0] - 1 if surv else max(0, int(round(float(r["fall_t"]) / DT)) - 1)
        xrel = traj[: j_last + 1, e, 0] - org[e, 0]
        if ze is not None and np.nanmax(xrel) >= ze:
            crossed += 1
        prog.append(float(r["progress_m"]))
        if not surv:
            falls += 1
            reasons[r["fall_reason"]] = reasons.get(r["fall_reason"], 0) + 1
    rec = {"run": run, "model": it, "terrain": fam, "cell": cell, "cmd_mps": float(meta["cells"][0]["cmd"][0]), "n": n,
           "trained": TRAINED_KIND.get(fam, "미경험"),
           "survival": sum(tf(r["survived"]) for r in eps) / n, "q1": sum(tf(r["q1_pass"]) for r in eps) / n,
           "q3": sum(tf(r["q3_pass"]) for r in eps) / n, "crossed": crossed / n if ze is not None else float("nan"),
           "zone_m": [zs, ze, basis], "progress_median_m": float(np.median(prog)),
           "move_ratio_median": float(np.median([float(r["move_ratio"]) for r in eps if r["move_ratio"] not in ("", "nan")] or [float("nan")])),
           "falls": falls, "fall_reasons": reasons, "tag": tag, "gpu": meta["devices"]["torch_cuda0_uuid"][:8],
           "eval_seed": meta["args"]["eval_seed"], "difficulty": meta["args"]["difficulty"]}
    rows.append(rec)
if not rows:
    raise SystemExit("no unseen runs")
with open(os.path.join(OUT, "UNSEEN-cells.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=[k for k in rows[0] if k not in ("fall_reasons", "zone_m")] + ["zone_end_m", "fall_reasons"])
    w.writeheader()
    for r in rows:
        x = {k: v for k, v in r.items() if k not in ("fall_reasons", "zone_m")}
        x["zone_end_m"] = r["zone_m"][1]
        x["fall_reasons"] = json.dumps(r["fall_reasons"])
        w.writerow(x)


def pct(x):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.0f}"


by = {(r["run"], r["model"], r["terrain"], r["cell"]): r for r in rows}
lines = ["### 표 U-1 · 지형별 · 생존 / Q1 추종 / Q3 (4 m 통과선 · 통로 0.30 m) / 건넘 · % (100 판씩, noise 끔, 난이도 0.5)\n",
         "| 지형 | 학습 여부 | 장애물 구간 끝 (m) | 명령 | E1 20000 | E2 20000 | E1 20499 | E2 20499 |",
         "|---|---|---|---|---|---|---|---|"]
for fam in TERRAINS:
    for cell in ("fwd03", "fwd05", "fwd10"):
        cells_ = []
        anyr = None
        for run, it in (("E1", "20000"), ("E2", "20000"), ("E1", "20499"), ("E2", "20499")):
            r = by.get((run, it, fam, cell))
            anyr = anyr or r
            cells_.append("-" if r is None else f"{pct(r['survival'])} / {pct(r['q1'])} / {pct(r['q3'])} / **{pct(r['crossed'])}**")
        if anyr is None:
            continue
        lines.append(f"| {fam} | {anyr['trained']} | {anyr['zone_m'][1]:.2f} ({anyr['zone_m'][2]}) | {cell} | " + " | ".join(cells_) + " |")
lines.append("")
lines.append("### 표 U-2 · 낙상 원인과 진행 거리 중앙값 (m)\n")
lines.append("| 지형 | 명령 | 실행 | 낙상 수 (원인) | 진행 중앙값 | move_ratio 중앙값 |")
lines.append("|---|---|---|---|---|---|")
for r in sorted(rows, key=lambda r: (TERRAINS.index(r["terrain"]), r["cell"], r["model"], r["run"])):
    lines.append(f"| {r['terrain']} | {r['cell']} | {r['run']} {r['model']} | {r['falls']} {json.dumps(r['fall_reasons'], ensure_ascii=False)} | {r['progress_median_m']:.2f} | {r['move_ratio_median']:.2f} |")
open(os.path.join(OUT, "UNSEEN-tables.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
json.dump(rows, open(os.path.join(OUT, "UNSEEN-summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(rows), "rows")
