# 5판 미경험 지형 영상 8 편: 판별 정보를 원자료에서 읽는다
import csv, json, os
import numpy as np
OUT = "C:/isaac/ext/go2_rl_robotlab/_eval/out"
SEL = [("e1_m20000", "gap", "fwd05", 0), ("e1_m20000", "gap", "fwd05", 57), ("e1_m20499", "gap", "fwd10", 13), ("e1_m20499", "gap", "fwd10", 0),
       ("e1_m20000", "stepping_stones", "fwd05", 0), ("e1_m20000", "floating_ring", "fwd05", 0), ("e2_m20000", "floating_ring", "fwd05", 0),
       ("e1_m20000", "rails", "fwd05", 0)]
wl = {r["web"].split("/")[-2] + "/" + r["web"].split("/")[-1]: r for r in csv.DictReader(open(os.path.join(OUT, "unseen_web_list.csv"), encoding="utf-8"))}
res = []
for m, fam, cell, ep in SEL:
    tag = f"un_{m}_{fam}_{cell}"
    d = os.path.join(OUT, tag)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    ze = meta["obstacle_zone_m"][fam][1]
    tr = np.load(os.path.join(d, "traj.npz"))["traj"]
    org = np.load(os.path.join(d, "env_origins.npy"))
    r = [x for x in csv.DictReader(open(os.path.join(d, "episodes.csv"), encoding="utf-8")) if int(x["episode"]) == ep][0]
    e = int(r["env"]); s = r["survived"] == "True"
    j = tr.shape[0] - 1 if s else max(0, int(round(float(r["fall_t"]) / 0.02)) - 1)
    x = tr[: j + 1, e, 0] - org[e, 0]
    key = f"{tag}/{fam}_{cell}_ep{ep:03d}_kinreplay_hud_web.mp4"
    w = wl.get(key)
    res.append({"tag": tag, "ep": ep, "survived": s, "fall_reason": r["fall_reason"], "fall_t": r["fall_t"], "x0": round(float(x[0]), 2),
                "xmax": round(float(np.nanmax(x)), 2), "zone_end": ze, "crossed": bool(np.nanmax(x) >= ze), "q_line": w and w["q_line"],
                "web": w and w["web"], "bytes": w and int(w["web_bytes"])})
for x in res:
    print(json.dumps(x, ensure_ascii=False))
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "unseen_vsel.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
