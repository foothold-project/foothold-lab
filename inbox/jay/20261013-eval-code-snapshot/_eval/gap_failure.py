# Where and how the student fails on the unseen «gap» terrain (measured from the records; no assumption about what
# the student sees: its inference path uses proprioception only, height scan is a teacher / critic input).
# Geometry (Isaac Lab gap_terrain, d = 0.5, lab cfg): platform 1.5 m square centred on the tile origin, top at z = 0;
# gap width 0.275 m around it (no floor); far edge at 0.75 + 0.275 = 1.025 m from the centre along +x.
#   all episodes (traj.npz): furthest base reach x_rel = max(base_x - origin_x) while alive, fall reason / time
#   representative episodes (full-record CSV): at the first «stall» (0.5 s mean body vx < 30 % of the command after
#   t = 1 s) the front feet x_rel, foot height above the platform top, contact, base pitch; and whether any foot went
#   below z = -0.05 m (stepped into the gap) before the stall.
# Usage: python gap_failure.py -> out/UNSEEN-gap-failure.json and a printed table
import csv
import glob
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
EDGE, FAR = 0.75, 1.025
DT = 0.02
res = {}
for d in sorted(glob.glob(os.path.join(OUT, "un_e[12]_m*_gap_fwd*"))):
    tag = os.path.basename(d)
    if not os.path.exists(os.path.join(d, "cells.json")):
        continue
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    cmd = float(meta["cells"][0]["cmd"][0])
    eps = list(csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")))
    traj = np.load(os.path.join(d, "traj.npz"))["traj"]
    org = np.load(os.path.join(d, "env_origins.npy"))
    reach, falls = [], {}
    for r in eps:
        e = int(r["env"])
        surv = r["survived"] == "True"
        jl = traj.shape[0] - 1 if surv else max(0, int(round(float(r["fall_t"]) / DT)) - 1)
        reach.append(float(np.nanmax(traj[: jl + 1, e, 0] - org[e, 0])))
        if not surv:
            falls[r["fall_reason"]] = falls.get(r["fall_reason"], 0) + 1
    reach = np.array(reach)
    rec = {"cmd": cmd, "n": len(eps), "survived": sum(r["survived"] == "True" for r in eps), "falls": falls,
           "reach_before_edge (<0.75)": int((reach < EDGE).sum()), "reach_in_gap (0.75..1.025)": int(((reach >= EDGE) & (reach < FAR)).sum()),
           "reach_past_far_edge (>=1.025)": int((reach >= FAR).sum()), "reach_median_m": float(np.median(reach)), "reps": []}
    for p in sorted(glob.glob(os.path.join(OUT, "full", tag, "gap_*_ep*.csv"))):
        D = np.genfromtxt(p, delimiter=",", names=True)
        e = int(json.load(open(os.path.join(OUT, "full", tag, "statics.npz"), "rb")) if False else 0)  # env read below
        summ = {r["file"]: r for r in csv.DictReader(open(os.path.join(OUT, "full", tag, "episodes_summary.csv"), encoding="utf-8"))}
        s = summ[os.path.basename(p)]
        e = int(s["env"])
        ox, oz = float(org[e, 0]), float(org[e, 2])
        vx = D["linvel_body_x_mps"]
        k = max(1, int(round(0.5 / DT)))
        run = np.convolve(vx, np.ones(k) / k, mode="valid")
        idx = [i for i in range(int(1.0 / DT), len(run)) if run[i] < 0.3 * cmd]
        j = idx[0] + k - 1 if idx else None
        feet = {}
        for ft in ("FL_foot", "FR_foot", "RL_foot", "RR_foot"):
            fz = D[f"{ft}_z_m"] - oz
            below = np.nonzero(fz < -0.05)[0]
            feet[ft] = {"x_rel_at_stall": None if j is None else round(float(D[f"{ft}_x_m"][j] - ox), 3),
                        "z_above_top_at_stall": None if j is None else round(float(fz[j]), 3),
                        "contact_at_stall": None if j is None else int(D[f"{ft}_contact"][j]),
                        "first_below_-0.05_t": None if not len(below) else round(float(D["t_s"][below[0]]), 2),
                        "min_z_above_top": round(float(np.nanmin(fz)), 3)}
        g = np.stack([D["gravity_body_x"], D["gravity_body_y"], D["gravity_body_z"]], 1)
        pitch = np.degrees(np.arcsin(np.clip(g[:, 0], -1, 1)))  # nose-down positive for projected gravity x > 0
        rec["reps"].append({"file": os.path.basename(p), "labels": s["labels"], "survived": s["survived"], "fall_reason": s["fall_reason"],
                            "fall_t": s["fall_t"], "stall_t": None if j is None else round(float(D["t_s"][j]), 2),
                            "base_x_rel_at_stall": None if j is None else round(float(D["base_x_m"][j] - ox), 3),
                            "base_x_rel_max": round(float(np.nanmax(D["base_x_m"] - ox)), 3),
                            "pitch_deg_at_stall": None if j is None else round(float(pitch[j]), 1),
                            "pitch_deg_max_abs": round(float(np.nanmax(np.abs(pitch))), 1), "feet": feet})
    res[tag] = rec
json.dump(res, open(os.path.join(OUT, "UNSEEN-gap-failure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for tag, r in res.items():
    print(tag, "surv", r["survived"], "falls", r["falls"], "reach <edge", r["reach_before_edge (<0.75)"], "in gap", r["reach_in_gap (0.75..1.025)"],
          "past", r["reach_past_far_edge (>=1.025)"], "median", round(r["reach_median_m"], 2))
    for x in r["reps"]:
        print("   ", x["file"], x["labels"], "stall_t", x["stall_t"], "base_x", x["base_x_rel_at_stall"], "max", x["base_x_rel_max"], "pitch", x["pitch_deg_at_stall"],
              {k: (v["x_rel_at_stall"], v["z_above_top_at_stall"], v["contact_at_stall"], v["first_below_-0.05_t"]) for k, v in x["feet"].items() if k in ("FL_foot", "FR_foot")})
