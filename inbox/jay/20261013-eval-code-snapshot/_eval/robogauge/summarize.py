# Summarize RoboGauge StressPipeline outputs (stress_benchmark_results.yaml) into the
# paper / README table columns.
#
# Definitions (checked against arXiv 2602.00678 v4 Table IV vs Table XIII, rows Ours and CTS):
#   Score    = benchmark_score (mean over 7 terrains of the terrain robust score at mean@50)
#   Tracking = mean(lin_vel_err, ang_vel_err)                                  [summary, mean@50]
#   Safety   = mean(dof_limits, dof_power)                                      [summary, mean@50]
#   Quality  = mean(orientation_stability, torque_smoothness, zmp_margin, friction_margin) [mean@50]
#   Level    = mean of the max passed level L* over the 6 level terrains x 9 frictions (failed = 0).
#              This Level definition is a reconstruction (author script not found) -> marked in doc.
import csv
import glob
import json
import os
import re
import sys

import yaml

OUT = "C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge"
TERRAINS = ["flat", "wave", "slope_fd", "slope_bd", "stairs_fd", "stairs_bd", "obstacle"]
LEVEL_TERRAINS = TERRAINS[1:]
GROUPS = {
    "Tracking": ["lin_vel_err", "ang_vel_err"],
    "Safety": ["dof_limits", "dof_power"],
    "Quality": ["orientation_stability", "torque_smoothness", "zmp_margin", "friction_margin"],
}
KEY_RE = re.compile(r"^(?P<terrain>" + "|".join(sorted(TERRAINS, key=len, reverse=True)) +
                    r")_(?P<level>None|\d+)_baseMass(?P<mass>[-\d.]+)_friction(?P<fric>[\d.]+)$")


def first(v):
    return float(str(v).split(" ")[0])


def load(path):
    # RoboGauge writes this file with open(path, 'w') and no encoding -> Windows ANSI code page (cp949 here).
    raw = open(path, "rb").read()
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        txt = raw.decode("cp949")
    try:
        return yaml.safe_load(txt)
    except yaml.constructor.ConstructorError:
        return yaml.unsafe_load(txt)


def summarize(path):
    d = load(path)
    s = d["summary"]
    row = {"model_path": d.get("model_path"), "Score": float(d["benchmark_score"])}
    for g, ms in GROUPS.items():
        row[g] = sum(first(s[m]["mean@50"]) for m in ms) / len(ms)
    cells = {}
    for k in d:
        m = KEY_RE.match(k)
        if not m:
            continue
        lvl = None if m["level"] == "None" else int(m["level"])
        cells[(m["terrain"], float(m["fric"]))] = lvl
    lv = {t: [cells[(t, f)] for (tt, f) in sorted(cells) if tt == t] for t in LEVEL_TERRAINS}
    n_cells = sum(len(v) for v in lv.values())
    row["Level"] = sum(sum(v) for v in lv.values()) / n_cells if n_cells else float("nan")
    row["n_level_cells"] = n_cells
    row["n_flat_cells"] = sum(1 for (t, _f) in cells if t == "flat")
    row["terrain_score"] = {t: float(d["scores"][t]) for t in TERRAINS if t in d["scores"]}
    row["terrain_level_mean"] = {t: (sum(v) / len(v) if v else None) for t, v in lv.items()}
    row["terrain_level_by_friction"] = {
        t: {f"{f:.1f}": cells[(t, f)] for (tt, f) in sorted(cells) if tt == t} for t in LEVEL_TERRAINS
    }
    row["metrics_mean@50"] = {m: first(s[m]["mean@50"]) for g in GROUPS.values() for m in g}
    return row


def main():
    rows = {}
    for p in sorted(glob.glob(f"{OUT}/stress/go2_lab_stress_*/*/stress_benchmark_results.yaml")):
        label = p.replace("\\", "/").split("/")[-3].replace("go2_lab_stress_", "")
        rows[label] = summarize(p)
        rows[label]["yaml"] = p.replace("\\", "/")
    wall = {}
    wp = f"{OUT}/stress/walltimes.csv"
    if os.path.exists(wp):
        for r in csv.reader(open(wp, encoding="utf-8")):
            if r:
                wall[r[0]] = {"nproc": int(r[2]), "wall_s": int(r[3])}
    for k in rows:
        rows[k]["wall"] = wall.get(k)
    with open(f"{OUT}/summary.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    hdr = f"{'label':28s} {'Score':>7s} {'Track':>7s} {'Safety':>7s} {'Qual':>7s} {'Level':>6s} cells  wall"
    print(hdr)
    for k, r in rows.items():
        w = r["wall"]["wall_s"] if r["wall"] else -1
        print(f"{k:28s} {r['Score']:7.4f} {r['Tracking']:7.4f} {r['Safety']:7.4f} {r['Quality']:7.4f} "
              f"{r['Level']:6.2f} {r['n_level_cells']}+{r['n_flat_cells']}  {w}s")
    print()
    print(f"{'label':28s} " + " ".join(f"{t:>9s}" for t in TERRAINS))
    for k, r in rows.items():
        print(f"{k:28s} " + " ".join(f"{r['terrain_score'].get(t, float('nan')):9.4f}" for t in TERRAINS))
    print()
    print(f"{'label (mean L*)':28s} " + " ".join(f"{t:>9s}" for t in LEVEL_TERRAINS))
    for k, r in rows.items():
        print(f"{k:28s} " + " ".join(f"{r['terrain_level_mean'][t]:9.2f}" for t in LEVEL_TERRAINS))


if __name__ == "__main__":
    sys.exit(main())
