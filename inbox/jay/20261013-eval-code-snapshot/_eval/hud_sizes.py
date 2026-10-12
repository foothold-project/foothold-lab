# Sizes of the RECORD-HUD outputs: label-strip sources, HUD videos, web copies, legacy parquet / trace.
# Also checks every HUD report row (frames = trace rows, 50 fps) and every web copy (< 2 MB, H.264, faststart).
# Usage: python hud_sizes.py -> out/hud_sizes.json
import glob
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def tot(pattern):
    fs = glob.glob(os.path.join(OUT, pattern), recursive=True)
    return {"files": len(fs), "bytes": sum(os.path.getsize(f) for f in fs)}


res = {"label_src_mp4": tot("video_hud_src/*/*_kinreplay.mp4"), "hud_mp4": tot("video_hud/*/*_kinreplay_hud.mp4"),
       "web_mp4": tot("web/*/*_kinreplay_hud_web.mp4"), "legacy_parquet": tot("legacy/*/timeseries/*.parquet"),
       "legacy_trace": tot("legacy/*/trace/*.trace.csv")}
rep = json.load(open(os.path.join(OUT, "hud_report.json"), encoding="utf-8"))
res["hud_rows"] = len(rep)
res["hud_frames_equal_trace_rows"] = sum(r["frames"] == r["trace_rows"] for r in rep)
res["hud_fps"] = sorted({r["video_fps"] for r in rep})
webs = glob.glob(os.path.join(OUT, "web", "*", "*.mp4"))
res["web_over_2MB"] = [os.path.relpath(w, OUT) for w in webs if os.path.getsize(w) >= 2_000_000]
res["web_max_bytes"] = max((os.path.getsize(w) for w in webs), default=0)
# codec and faststart (moov before mdat) on every web copy
import imageio_ffmpeg  # noqa: E402
ff = imageio_ffmpeg.get_ffmpeg_exe()
bad_fast, codecs, heights = [], set(), set()
for w in webs:
    head = open(w, "rb").read(4096)
    if head.find(b"moov") < 0 or (head.find(b"mdat") >= 0 and head.find(b"mdat") < head.find(b"moov")):
        bad_fast.append(os.path.relpath(w, OUT))
    r = subprocess.run([ff, "-i", w], capture_output=True, text=True)
    line = next((l for l in r.stderr.splitlines() if "Video:" in l), "")
    codecs.add(line.split("Video:")[1].split()[0] if line else "?")
    for tok in line.replace(",", " ").split():
        if "x" in tok and tok.split("x")[0].isdigit() and tok.split("x")[1].isdigit():
            heights.add(int(tok.split("x")[1]))
            break
res["web_not_faststart"] = bad_fast
res["web_codecs"] = sorted(codecs)
res["web_heights"] = sorted(heights)
json.dump(res, open(os.path.join(OUT, "hud_sizes.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
