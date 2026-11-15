# Guard records of the UNSEEN-E12 runs (out/un_*.guard.json and out/video_hud_src/un_*.guard.json) -> out/UNSEEN-guards.csv
# and a markdown appendix table out/UNSEEN-guards.md. Buffer setting per run from its meta eval_changes.
import csv, glob, json, os, time
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
rows = []
for g in sorted(glob.glob(os.path.join(OUT, "un_e*.guard.json")) + glob.glob(os.path.join(OUT, "video_hud_src", "un_e*.guard.json"))):
    d = json.load(open(g, encoding="utf-8"))
    tag = os.path.basename(g)[: -len(".guard.json")]
    kind = "video" if "video_hud_src" in g else "eval"
    small = ""
    if kind == "eval" and os.path.exists(os.path.join(OUT, tag, "meta.json")):
        m = json.load(open(os.path.join(OUT, tag, "meta.json"), encoding="utf-8"))
        small = "small" if any("physx buffers reduced" in c for c in m.get("eval_changes", [])) else "default"
    rows.append({"kind": kind, "tag": tag, "physx_buffers": small, "gpu_index": d["gpu_index"], "floor_mib": d["min_free_floor_mib"],
                 "min_free_mib": d["min_free_mib"], "max_used_mib": d["max_used_mib"], "samples": d["samples"], "interval_s": d["interval_s"],
                 "stopped_by_guard": d["stopped_by_guard"], "exit_code": d["exit_code"], "wall_s": d["wall_s"],
                 "finished": time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(g)))})
with open(os.path.join(OUT, "UNSEEN-guards.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
lines = ["| 종류 | tag | PhysX 버퍼 | 여유 최저 MiB | 최대 사용 MiB | 표본 (200 ms) | 멈춤 | exit | 끝난 시각 |", "|---|---|---|---|---|---|---|---|---|"]
for r in sorted(rows, key=lambda r: r["finished"]):
    lines.append(f"| {r['kind']} | {r['tag']} | {r['physx_buffers']} | {r['min_free_mib']:,} | {r['max_used_mib']:,} | {r['samples']} | {'예' if r['stopped_by_guard'] else ''} | {r['exit_code']} | {r['finished']} |")
open(os.path.join(OUT, "UNSEEN-guards.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
ev = [r for r in rows if r["kind"] == "eval"]
for b in ("default", "small"):
    x = [r for r in ev if r["physx_buffers"] == b]
    if x:
        print(b, len(x), "min_free min", min(r["min_free_mib"] for r in x), "max_used max", max(r["max_used_mib"] for r in x))
print("eval guard files", len(ev), "video guard files", len(rows) - len(ev), "stopped", [r["tag"] for r in rows if r["stopped_by_guard"]])
