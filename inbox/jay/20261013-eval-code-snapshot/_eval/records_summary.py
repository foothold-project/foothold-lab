# Aggregates the replay-video reports and the GPU guard summaries -> out/records_summary.json (read only)
# Usage: python records_summary.py
import glob
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
res = {"videos": {}, "guards": {}}
allv = []
for rp in sorted(glob.glob(os.path.join(OUT, "video", "*", "videos_report.json"))):
    r = json.load(open(rp, encoding="utf-8"))
    tag = r["full_tag"]
    if not (tag.startswith("fr_") or tag.startswith("e2_")):
        continue
    v = r["videos"]
    fam = tag.split("_", 2)[2]
    med = [x["contact_foot_height_above_terrain_m"]["median"] for x in v]
    within = [x["contact_foot_height_above_terrain_m"]["frac_within_0.018_0.028"] for x in v]
    res["videos"][tag] = {"n": len(v), "mesh_equal": r["terrain_mesh_equal"], "bytes": sum(x["bytes"] for x in v),
                          "seconds": round(sum(x["seconds"] for x in v), 1), "fk_max_m": max(x["replayed_foot_vs_csv_max_abs_m"] for x in v),
                          "contact_height_median_range_m": [round(min(med), 4), round(max(med), 4)],
                          "within_0.018_0.028_min": round(min(w for w in within if w is not None), 3),
                          "within_0.018_0.028_median": round(float(np.median([w for w in within if w is not None])), 3),
                          "wall_s": round(sum(x["wall_s"] for x in v), 0),
                          "sim_device": sorted({x.get("sim_device", "cuda:0") for x in v}), "render_gpu": "GPU 1"}
    for x in v:
        allv.append((tag, fam, x))
fams = {}
for tag, fam, x in allv:
    d = fams.setdefault(fam, {"n": 0, "med": [], "within": []})
    d["n"] += 1
    d["med"].append(x["contact_foot_height_above_terrain_m"]["median"])
    d["within"].append(x["contact_foot_height_above_terrain_m"]["frac_within_0.018_0.028"])
res["by_family"] = {f: {"videos": d["n"], "median_of_medians_m": round(float(np.median(d["med"])), 4),
                        "median_range_m": [round(min(d["med"]), 4), round(max(d["med"]), 4)],
                        "within_band_median": round(float(np.median(d["within"])), 3), "within_band_min": round(min(d["within"]), 3)}
                    for f, d in sorted(fams.items())}
res["videos_sim_device_count"] = {d: sum(1 for _, _, x in allv if x.get("sim_device", "cuda:0") == d) for d in ("cuda:0", "cpu")}
res["videos_total"] = {"tags": len(res["videos"]), "videos": len(allv), "mesh_equal_all": all(v["mesh_equal"] for v in res["videos"].values()),
                       "fk_max_m": max((v["fk_max_m"] for v in res["videos"].values()), default=None),
                       "bytes": sum(v["bytes"] for v in res["videos"].values()),
                       "seconds": round(sum(v["seconds"] for v in res["videos"].values()), 1)}
for gp in sorted(glob.glob(os.path.join(OUT, "*.guard.json")) + glob.glob(os.path.join(OUT, "video", "*.guard.json"))):
    g = json.load(open(gp, encoding="utf-8"))
    res["guards"][os.path.relpath(gp, OUT).replace("\\", "/")] = {k: g.get(k) for k in ("gpu_index", "min_free_mib", "max_used_mib", "samples", "stopped_by_guard", "exit_code", "wall_s")}
by_gpu = {}
for k, g in res["guards"].items():
    b = by_gpu.setdefault(str(g["gpu_index"]), {"runs": 0, "stopped": [], "min_free_mib": 10 ** 9, "samples": 0, "nonzero_exit": []})
    b["runs"] += 1
    b["samples"] += g["samples"] or 0
    b["min_free_mib"] = min(b["min_free_mib"], g["min_free_mib"] if g["min_free_mib"] is not None else 10 ** 9)
    if g["stopped_by_guard"]:
        b["stopped"].append(k)
    if g["exit_code"] not in (0, None) and not g["stopped_by_guard"]:
        b["nonzero_exit"].append(k)
res["guards_by_gpu"] = by_gpu
json.dump(res, open(os.path.join(OUT, "records_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({"videos_total": res["videos_total"], "by_family": res["by_family"], "guards_by_gpu": by_gpu}, ensure_ascii=False, indent=1))
