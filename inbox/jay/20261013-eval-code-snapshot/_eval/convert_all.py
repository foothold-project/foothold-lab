# 1. Checks that every org_<tag> fingerprint run has the same pairing fingerprints, terrain mesh and arguments as
#    <tag> (so its env_origins.npy belongs to that run). 2. Converts every full-record tag with fr_to_legacy.py
#    (93-column parquet + 17-column trace), origins from out/<tag>/env_origins.npy or out/org_<tag>/env_origins.npy.
# Usage: python convert_all.py  -> out/convert_all.json
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
res = {"origin_pairs": {}, "converted": {}}
tags = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(OUT, "full", "*", "episodes_summary.csv")))
tags = [t for t in tags if not t.startswith("frt")]
for t in tags:
    org = os.path.join(OUT, "org_" + t)
    if os.path.exists(os.path.join(OUT, t, "env_origins.npy")):
        res["origin_pairs"][t] = "own run"
        continue
    a = json.load(open(os.path.join(OUT, t, "meta.json"), encoding="utf-8"))
    b = json.load(open(os.path.join(org, "meta.json"), encoding="utf-8"))
    skip = ("tag", "fingerprint_only", "full_record")
    dflt = {"heading_hold": 0.0, "heading_clip": 0.5, "spawn_offset": "", "height_perm_seed": -1}
    args_eq = all(a["args"].get(k, dflt.get(k)) == b["args"].get(k, dflt.get(k)) for k in set(a["args"]) | set(b["args"]) if k not in skip)
    ok = a["pairing_sha256"] == b["pairing_sha256"] and a["terrain_mesh"] == b["terrain_mesh"] and args_eq \
        and a.get("terrain_origins_sha256") == b.get("terrain_origins_sha256")
    res["origin_pairs"][t] = {"pairing_equal": a["pairing_sha256"] == b["pairing_sha256"], "mesh_equal": a["terrain_mesh"] == b["terrain_mesh"],
                              "args_equal": args_eq, "terrain_origins_sha_equal": a.get("terrain_origins_sha256") == b.get("terrain_origins_sha256"), "ok": ok}
    if not ok:
        print("ORIGIN MISMATCH", t, res["origin_pairs"][t], flush=True)
bad = [t for t, v in res["origin_pairs"].items() if isinstance(v, dict) and not v["ok"]]
if bad:
    json.dump(res, open(os.path.join(OUT, "convert_all.json"), "w"), indent=1)
    sys.exit(f"STOP: origin runs do not match {bad}")
for t in tags:
    r = subprocess.run([sys.executable, os.path.join(HERE, "fr_to_legacy.py"), "--tag", t], capture_output=True, text=True)
    res["converted"][t] = r.stdout.strip().splitlines()[-1] if r.returncode == 0 else f"FAILED {r.stderr[-400:]}"
    print(t, res["converted"][t][:120], flush=True)
json.dump(res, open(os.path.join(OUT, "convert_all.json"), "w"), indent=1)
print("CONVERT DONE", sum(1 for v in res["converted"].values() if not v.startswith("FAILED")), "/", len(tags), flush=True)
