"""The 11:38 shared-USD run vs its v3.7 re-collection (lead 10/13, TASK-astra-16h step 7, VERIFY-astra-16h 4.4). Read only.
Compares bytes AND contents: cells.json as parsed values, every traj.npz array by dtype / shape / values, episodes.csv
rows, and the meta fields that describe the input and the checks (meta also carries times and paths).
Wording (16h 4.4): equal -> "no difference found in the recorded outputs compared" (not "the asset was intact");
different -> "recorded outputs differ, cause unknown; isolate" (not "contaminated by the collision")."""
import csv
import glob
import hashlib
import io
import json
import os
import sys

import numpy as np

OUT = "C:/isaac/ext/go2_rl_robotlab/_eval/out"
TAG = sys.argv[1] if len(sys.argv) > 1 else "cq_on24000_flat_stand_on_s1000"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


old = sorted(glob.glob(os.path.join(OUT, "attempts", f"{TAG}.dir.*")))
new = os.path.join(OUT, TAG)
if not old or not os.path.isdir(new) or not os.path.exists(os.path.join(new, "traj.npz")):
    print(json.dumps({"tag": TAG, "old_folders": old, "new_ready": os.path.exists(os.path.join(new, "traj.npz")), "result": "not ready"}))
    sys.exit(2)
o = old[0]
res = {"tag": TAG, "old": os.path.relpath(o, OUT), "new": os.path.relpath(new, OUT), "bytes": {}, "content": {}}
for f in ("cells.json", "traj.npz", "episodes.csv", "env_origins.npy"):
    a, b = sha(os.path.join(o, f)), sha(os.path.join(new, f))
    res["bytes"][f] = a is not None and a == b
res["content"]["cells.json"] = json.load(open(os.path.join(o, "cells.json"))) == json.load(open(os.path.join(new, "cells.json")))
zo, zn = np.load(os.path.join(o, "traj.npz")), np.load(os.path.join(new, "traj.npz"))
arr = {}
for k in sorted(set(zo.files) | set(zn.files)):
    if k not in zo.files or k not in zn.files:
        arr[k] = "missing on one side"
        continue
    x, y = zo[k], zn[k]
    if x.dtype != y.dtype or x.shape != y.shape:
        arr[k] = f"dtype/shape {x.dtype}{x.shape} vs {y.dtype}{y.shape}"
    elif np.array_equal(x, y, equal_nan=x.dtype.kind == "f"):
        arr[k] = "equal"
    else:
        d = np.nanmax(np.abs(x.astype(np.float64) - y.astype(np.float64))) if x.dtype.kind in "fiu" else None
        arr[k] = f"values differ (max abs {d})"
res["content"]["traj.npz"] = arr
ro = list(csv.DictReader(io.StringIO(open(os.path.join(o, "episodes.csv"), encoding="utf-8").read())))
rn = list(csv.DictReader(io.StringIO(open(os.path.join(new, "episodes.csv"), encoding="utf-8").read())))
res["content"]["episodes.csv"] = ro == rn
mo = json.load(open(os.path.join(o, "meta.json"), encoding="utf-8"))
mn = json.load(open(os.path.join(new, "meta.json"), encoding="utf-8"))
keys = ["args", "checks_pre", "checks_run", "N", "T_steps", "checkpoint_sha256", "loaded_iter", "pairing_sha256", "pairing_sha256_ext", "terrain_mesh"]
res["content"]["meta (input / checks)"] = {k: mo.get(k) == mn.get(k) for k in keys}
lo = open(os.path.join(OUT, f"{TAG}.log"), encoding="utf-8", errors="replace").read()
res["new_log_root_ref"] = "</World/envs/env_0/Robot>: Unresolved reference" in lo
same = res["content"]["cells.json"] and res["content"]["episodes.csv"] and all(v == "equal" for v in arr.values())
res["result"] = ("no difference found in the recorded outputs compared" if same
                 else "recorded outputs differ, cause unknown: isolate, re-collect again under the same conditions, then compare inputs / fingerprints / logs")
print(json.dumps(res, ensure_ascii=False, indent=1))
sys.exit(0 if same else 1)
