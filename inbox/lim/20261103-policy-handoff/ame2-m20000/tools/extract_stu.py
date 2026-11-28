"""Extract the two tagged robots of a rec_student.py recording into one small npz (CPU, no simulator).
Tags (fixed before the run): flat = recorded robot of cell (rough, 0) (the rough sub-terrain was made flat for this recording),
stairs = (stair_up, 4). For each: the first 200 policy rows from the explicit reset (policy inputs prop / cmd / nmap, the policy action,
the robot state used for the layout checks), the action rows (raw / processed) and every frame of that robot in the same steps (the
mapper input grid and the mapper outputs mean / logvar computed in the env). The meta of the recording goes along as json.
usage: python extract_stu.py <rec dir> <out npz>"""
import glob
import json
import os
import sys

import numpy as np
import torch

REC, OUT = sys.argv[1:3]
TAGS = {"flat": ("rough", 0), "stairs": ("stair_up", 4)}
N = 200
meta = torch.load(os.path.join(REC, "meta.pt"), map_location="cpu", weights_only=False)
end = torch.load(os.path.join(REC, "end.pt"), map_location="cpu", weights_only=False)
cells = [tuple(c) for c in meta["rec_cells"]]
idx = {t: cells.index(c) for t, c in TAGS.items()}
PK = ("counter", "ep", "ep_len", "prop", "cmd", "nmap", "act", "gaze_r", "win", "ang_vel_b", "root_quat", "q", "q0", "dq", "dq0", "last_action", "cmd_b")
P = {t: {k: [] for k in PK} for t in TAGS}
A = {t: {k: [] for k in ("counter", "raw", "processed")} for t in TAGS}
F = {t: {k: [] for k in ("counter", "grid", "mean", "logvar")} for t in TAGS}
c0 = None
for p in sorted(glob.glob(os.path.join(REC, "part_*.pt"))):
    d = torch.load(p, map_location="cpu", weights_only=False)
    for r in d["policy"]:
        if c0 is None:
            c0 = int(r["counter"])
        if int(r["counter"]) - c0 >= N:
            continue
        for t, i in idx.items():
            for k in PK:
                v = r[k]
                P[t][k].append(v[i].numpy().copy() if torch.is_tensor(v) else v)
    for r in d["action"]:
        if c0 is not None and int(r["counter"]) - c0 < N:
            for t, i in idx.items():
                A[t]["counter"].append(int(r["counter"]))
                A[t]["raw"].append(r["raw"][i].numpy().copy())
                A[t]["processed"].append(r["processed"][i].numpy().copy())
    for f in d["frame"]:
        if c0 is not None and int(f["counter"]) - c0 < N:
            el = f["env"].tolist()
            for t, i in idx.items():
                e = int(meta["rec_ids"][i])
                if e in el:
                    j = el.index(e)
                    F[t]["counter"].append(int(f["counter"]))
                    for k in ("grid", "mean", "logvar"):
                        F[t][k].append(f[k][j].numpy().copy())
    del d
out = {}
info = {}
for t in TAGS:
    for k, v in P[t].items():
        out[f"{t}_{k}"] = np.array(v) if not torch.is_tensor(v[0]) and np.isscalar(v[0]) else np.stack(v)
    for k, v in A[t].items():
        out[f"{t}_act_{k}"] = np.array(v) if k == "counter" else np.stack(v)
    for k, v in F[t].items():
        out[f"{t}_frame_{k}"] = np.array(v) if k == "counter" else np.stack(v)
    info[t] = {"cell": list(TAGS[t]), "recorded_index": idx[t], "env_id": int(meta["rec_ids"][idx[t]]), "policy_rows": len(P[t]["counter"]),
               "frames": len(F[t]["counter"]), "episodes_in_rows": sorted({int(x) for x in P[t]["ep"]})}
m = {k: meta[k] for k in ("rec_cells", "rec_ids", "type_names", "num_envs", "joint_names", "action_joint_names", "action_scale", "delay_range",
                         "step_dt", "physics_dt", "decimation", "term_names", "obs_groups", "noise_none", "torch", "code", "seed", "crop",
                         "roi_margin", "tool_md5", "source_eval_student_md5", "frame_period_steps")}
m["rec_cells"] = [list(c) for c in m["rec_cells"]]
m["default_joint_pos"] = meta["default_joint_pos"][0].tolist()
m["student428"] = meta["student428"]
m["args"] = {k: meta["args"][k] for k in ("task", "num_envs", "seed", "checkpoint", "mapper_jit", "teacher_jit", "rec_levels", "rec_levels_stones", "rec_episodes")}
m["end_complete"] = bool(end.get("complete", False)) if isinstance(end, dict) else None
m["tags"] = info
out["meta_json"] = np.array(json.dumps(m, default=str))
np.savez_compressed(OUT, **out)
print("EXTRACT_INFO", json.dumps(info))
print("EXTRACT_DONE", OUT)
