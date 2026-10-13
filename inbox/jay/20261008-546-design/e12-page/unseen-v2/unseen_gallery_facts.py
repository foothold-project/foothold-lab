# -*- coding: utf-8 -*-
"""판 하나의 결과를 원자료에서 다시 잰다 (unseen_gallery.py 1판의 ep_facts 를 그대로 옮김 · 2판이 import)."""
import csv
import json
import os

import numpy as np

OUT = "C:/isaac/ext/go2_rl_robotlab/_eval/out"
cache = {}


def ep_facts(tag, ep):
    if tag not in cache:
        d = os.path.join(OUT, tag)
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        fam = meta["args"]["families"]
        cache[tag] = (meta["obstacle_zone_m"][fam][1], np.load(os.path.join(d, "traj.npz"))["traj"],
                      np.load(os.path.join(d, "env_origins.npy")),
                      {int(r["episode"]): r for r in csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8"))})
    ze, tr, org, eps = cache[tag]
    r = eps[ep]
    e = int(r["env"])
    s = r["survived"] == "True"
    j = tr.shape[0] - 1 if s else max(0, int(round(float(r["fall_t"]) / 0.02)) - 1)
    x = tr[: j + 1, e, 0] - org[e, 0]
    return {"surv": s, "fall_t": None if s else float(r["fall_t"]), "fall_reason": r["fall_reason"],
            "cross": bool(np.nanmax(x) >= ze), "x_end": float(x[-1]), "x_max": float(np.nanmax(x)), "zone": ze}
