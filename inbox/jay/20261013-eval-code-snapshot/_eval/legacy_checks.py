# Checks over every converted episode (out/legacy/*): reads each parquet back with the lab timeseries.read() and each
# trace with the lab trace.read(); known answer: at row 0 the base is spawned at origin + 0.40 m (GO2_CFG_UNITREE)
# + uniform 0..0.20 m (reset pose_range z), so base_z_m (height above the env origin) must lie in [0.40, 0.60].
# Also: 93 columns, fold-back checks all passed (convert_report.json), sizes. -> out/legacy_checks.json
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/sim/eval")
import timeseries  # noqa: E402
from overlay import trace as trace_mod  # noqa: E402

res = {"tags": 0, "parquet": 0, "trace": 0, "parquet_bytes": 0, "trace_bytes": 0, "columns": set(), "row0_base_z_m": [9, -9],
       "floor_missing": 0, "fold_checks_failed": 0, "outside": []}
for d in sorted(glob.glob(os.path.join(HERE, "out", "legacy", "*"))):
    rep = json.load(open(os.path.join(d, "convert_report.json"), encoding="utf-8"))
    res["tags"] += 1
    for e in rep["episodes"]:
        res["fold_checks_failed"] += sum(1 for c in e["checks"] if not c[4])
    for p in glob.glob(os.path.join(d, "timeseries", "*.parquet")):
        meta, rows = timeseries.read(p)
        res["parquet"] += 1
        res["parquet_bytes"] += os.path.getsize(p)
        res["columns"].add(int(meta["columns"]))
        z = rows[0]["base_z_m"]
        if z is None:
            res["floor_missing"] += 1
            continue
        res["row0_base_z_m"] = [min(res["row0_base_z_m"][0], z), max(res["row0_base_z_m"][1], z)]
        if not (0.40 - 1e-3 <= z <= 0.60 + 1e-3):
            res["outside"].append([os.path.basename(d), os.path.basename(p), z])
    for p in glob.glob(os.path.join(d, "trace", "*.trace.csv")):
        trace_mod.read(p)
        res["trace"] += 1
        res["trace_bytes"] += os.path.getsize(p)
res["columns"] = sorted(res["columns"])
json.dump(res, open(os.path.join(HERE, "out", "legacy_checks.json"), "w"), indent=1)
print(json.dumps(res))
