# Do the full-record re-runs (GPU 0) reproduce the stored E1 runs (GPU 1)? Also aggregate fr_check results and sizes.
# Usage: python fr_repro.py > out/FR-repro.json
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
PY = sys.executable
FAMS = ["flat", "wave", "slope_up", "slope_down", "rough_slope", "stairs_up", "stairs_down", "obstacles", "offplat"]
res = {"pairs": {}, "checks": {}}
for it in ("20000", "20499"):
    for f in FAMS:
        a, b = os.path.join(OUT, f"m{it}_{f}", "traj.npz"), os.path.join(OUT, f"fr_m{it}_{f}", "traj.npz")
        if not (os.path.exists(a) and os.path.exists(b)):
            res["pairs"][f"{it}/{f}"] = "missing"
            continue
        za, zb = np.load(a), np.load(b)
        ma = json.load(open(os.path.join(OUT, f"m{it}_{f}", "meta.json"), encoding="utf-8"))
        mb = json.load(open(os.path.join(OUT, f"fr_m{it}_{f}", "meta.json"), encoding="utf-8"))
        res["pairs"][f"{it}/{f}"] = {
            "traj_bitwise": bool(np.array_equal(za["traj"], zb["traj"])), "term_equal": bool(np.array_equal(za["term"], zb["term"])),
            "traj_max_abs": float(np.nanmax(np.abs(za["traj"].astype(np.float64) - zb["traj"].astype(np.float64)))),
            "gpu_stored": ma["devices"]["torch_cuda0_uuid"][:8], "gpu_rerun": mb["devices"]["torch_cuda0_uuid"][:8],
            "old_hash_equal": ma["pairing_sha256"]["init_root_pose"] == mb["pairing_sha256"]["init_root_pose"]}
        r = subprocess.run([PY, os.path.join(HERE, "fr_check.py"), f"fr_m{it}_{f}"], capture_output=True, text=True)
        try:
            res["checks"][f"{it}/{f}"] = json.load(open(os.path.join(OUT, "full", f"fr_m{it}_{f}", "checks.json")))
        except Exception as ex:  # pragma: no cover
            res["checks"][f"{it}/{f}"] = f"failed: {ex} {r.stderr[-300:]}"
for it in ("20000", "20499"):
    for f in FAMS:
        tag = f"e2_m{it}_{f}"
        if not os.path.exists(os.path.join(OUT, "full", tag, "episodes_summary.csv")):
            res["checks"][f"E2 {it}/{f}"] = "missing"
            continue
        r = subprocess.run([PY, os.path.join(HERE, "fr_check.py"), tag], capture_output=True, text=True)
        try:
            res["checks"][f"E2 {it}/{f}"] = json.load(open(os.path.join(OUT, "full", tag, "checks.json")))
        except Exception as ex:  # pragma: no cover
            res["checks"][f"E2 {it}/{f}"] = f"failed: {ex} {r.stderr[-300:]}"
size = {}
for sub in ("full", "video"):
    tot, n = 0, 0
    for root, _, files in os.walk(os.path.join(OUT, sub)):
        for fn in files:
            if fn.endswith(".csv") or fn.endswith(".mp4"):
                tot += os.path.getsize(os.path.join(root, fn))
                n += 1
    size[sub] = {"files": n, "bytes": tot, "GiB": round(tot / 2 ** 30, 3)}
res["sizes"] = size
print(json.dumps(res, indent=1))
