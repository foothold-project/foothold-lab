"""Per-terrain success of two eval_gaze outputs (same seed, same tool): training no-return depth U(0.4, 1.0) vs fixed 0.7 m.
Success over counted episodes = every played episode except the first of each env (as the queues' EVALCHECK).
  python.sh cmp_depth07.py <reference.pt> <depth07.pt> <out.json>
"""
import json
import sys

import torch


def per_type(path):
    d = torch.load(path, map_location="cpu", weights_only=False)
    F = {k: i for i, k in enumerate(d["fields"])}
    R = d["rows"]
    P = R[R[:, F["played"]] > 0]
    env = P[:, F["env"]].long()
    n = d["num_envs"]
    order = torch.argsort(env, stable=True)
    es = env[order]
    rank = torch.arange(len(es)) - torch.searchsorted(es, torch.arange(n))[es]
    counted = order[rank >= 1]
    ce = env[counted]
    s = P[counted, F["success"]]
    typ = d["env_type"].long()[ce]
    out = {}
    for i, name in enumerate(d["type_names"]):
        m = typ == i
        out[name] = {"episodes": int(m.sum()), "success": float(s[m].mean())}
    out["_all"] = {"episodes": int(len(s)), "success": float(s.mean())}
    meta = {k: d[k] for k in ("task", "seed", "episodes", "num_envs", "checkpoint", "completed_updates", "actor_sha", "code")}
    return out, meta


a, ma = per_type(sys.argv[1])
b, mb = per_type(sys.argv[2])
assert {k: v for k, v in ma.items()} == {k: v for k, v in mb.items()}, (ma, mb)
res = {"meta": ma, "reference_depth_U0.4_1.0": a, "depth_fixed_0.7": b,
       "diff_points": {k: round(100 * (b[k]["success"] - a[k]["success"]), 2) for k in a}}
json.dump(res, open(sys.argv[3], "w"), indent=1)
for k in a:
    print(f"{k:12s} {a[k]['episodes']:6d} ep  ref {100 * a[k]['success']:6.2f} %  depth0.7 {100 * b[k]['success']:6.2f} %  diff {res['diff_points'][k]:+6.2f} %p")
print("CMP_DONE")
