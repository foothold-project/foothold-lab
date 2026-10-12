# crossed-then-fell vs crossed-and-survived (q_post fall_t truncation), and paired E1/E2 discordance on the same env
import os, csv, json
import numpy as np
OUT = r"C:/isaac/ext/go2_rl_robotlab/_eval/out"
def per_ep(tag):
    d = os.path.join(OUT, tag)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    fam = meta["args"]["families"]
    ze = meta["obstacle_zone_m"][fam][1]
    tr = np.load(os.path.join(d, "traj.npz"))["traj"]
    org = np.load(os.path.join(d, "env_origins.npy"))
    res = {}
    for r in csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")):
        e = int(r["env"]); s = r["survived"] == "True"
        j = tr.shape[0] - 1 if s else max(0, int(round(float(r["fall_t"]) / 0.02)) - 1)
        x = tr[: j + 1, e, 0] - org[e, 0]
        res[e] = (s, bool(np.nanmax(x) >= ze), float(x[0]))
    return res
for fam, cell, models in (("gap", "fwd10", ["e1_m20499", "e2_m20499"]), ("gap", "fwd05", ["e1_m20000", "e2_m20000", "e1_m20499", "e2_m20499"]),
                          ("floating_ring", "fwd05", ["e1_m20000", "e2_m20000", "e1_m20499", "e2_m20499"]), ("floating_ring", "fwd10", ["e1_m20499", "e2_m20499"])):
    print(f"== {fam} {cell}")
    R = {}
    for m in models:
        R[m] = per_ep(f"un_{m}_{fam}_{cell}")
        v = R[m].values()
        cs = sum(1 for s, c, _ in v if c and s); cf = sum(1 for s, c, _ in v if c and not s)
        print(f"  {m}: crossed&survived {cs} · crossed then fell {cf} · crossed total {cs+cf}")
    for a, b in (("e1_m20000", "e2_m20000"), ("e1_m20499", "e2_m20499")):
        if a in R and b in R:
            b10 = sum(1 for e in R[a] if R[a][e][1] and not R[b][e][1]); b01 = sum(1 for e in R[a] if not R[a][e][1] and R[b][e][1])
            same_start = all(abs(R[a][e][2] - R[b][e][2]) < 1e-4 for e in R[a])
            print(f"  paired crossing {a} vs {b}: only E1 {b10} · only E2 {b01} · same start x {same_start}")
