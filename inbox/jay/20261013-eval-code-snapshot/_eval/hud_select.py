# Picks the episodes for the HUD / web set (RECORD-HUD.md): E1 and E2 x model_20499 and model_19500,
# 8 families x stop03 fwd01 fwd05 back03 right03 yawL05, band start (stairs_up stairs_down slope_up slope_down)
# x stop03 yawL05; per cell the first success and the first failure of the full record (no failure -> empty slot).
# HUD title: run, model, B: for band start, family, cell, episode (at most 34 characters, the HUD limit).
# Writes out/hud_sel.json (items for hud_make.py), out/hud_sel_files.json (CSV names per tag) and out/hud_sel_slots.csv.
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
MODELS = [("E1", "20499", "fr_m20499"), ("E2", "20499", "e2_m20499"), ("E1", "19500", "fr_m19500"), ("E2", "19500", "e2fr_m19500")]
FAMS = ["flat", "wave", "slope_up", "slope_down", "rough_slope", "stairs_up", "stairs_down", "obstacles"]
CEN = ["stop03", "fwd01", "fwd05", "back03", "right03", "yawL05"]
BANDF = ["stairs_up", "stairs_down", "slope_up", "slope_down"]
BANDC = ["stop03", "yawL05"]
items, files, slots = [], {}, []
for run, it, pre in MODELS:
    for band in (False, True):
        fams = BANDF if band else FAMS
        cells = BANDC if band else CEN
        for fam in fams:
            tag = f"{pre}_offplat" if band else f"{pre}_{fam}"
            sp = os.path.join(OUT, "full", tag, "episodes_summary.csv")
            rows = list(csv.DictReader(open(sp, encoding="utf-8"))) if os.path.exists(sp) else None
            for cell in cells:
                for lab in ("first_success", "first_failure"):
                    hit = None if rows is None else next((r for r in rows if r["family"] == fam and r["cell"] == cell and lab in r["labels"]), None)
                    slots.append({"run": run, "model": it, "start": "band" if band else "centre", "family": fam, "cell": cell,
                                  "pick": lab, "tag": tag, "file": hit["file"] if hit else "", "status": "ok" if hit else ("no record" if rows is None else "none")})
                    if not hit:
                        continue
                    key = hit["file"][:-4]
                    files.setdefault(tag, []).append(hit["file"])
                    items.append({"key": f"{tag}/{key}", "tag": tag, "file": hit["file"], "pick": lab,
                                  "video": os.path.join(OUT, "video_hud_src", tag, key + "_kinreplay.mp4"),
                                  "parquet": os.path.join(OUT, "legacy", tag, "timeseries", key + ".parquet"),
                                  "hud": os.path.join(OUT, "video_hud", tag, key + "_kinreplay_hud.mp4"),
                                  "web": os.path.join(OUT, "web", tag, key + "_kinreplay_hud_web.mp4"),
                                  "title": f"{run} {it} {'B:' if band else ''}{fam} {cell} ep{int(hit['episode'])}"})
json.dump(items, open(os.path.join(OUT, "hud_sel.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({k: sorted(set(v)) for k, v in files.items()}, open(os.path.join(OUT, "hud_sel_files.json"), "w", encoding="utf-8"), indent=1)
with open(os.path.join(OUT, "hud_sel_slots.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(slots[0].keys()))
    w.writeheader()
    w.writerows(slots)
print(json.dumps({"items": len(items), "slots": len(slots), "empty": sum(s["status"] != "ok" for s in slots),
                  "no_record": sum(s["status"] == "no record" for s in slots)}))
