# HUD on replay videos with the lab's overlay/render.py (imported, not modified), then a small web copy.
#   source video : out/video_hud_src/<tag>/<key>_kinreplay.mp4 (q_video.py --overlay label: label strip at the bottom)
#   data         : out/legacy/<tag>/timeseries/<key>.parquet (fr_to_legacy.py, 93 columns)
#   HUD          : render.render(..., mode="flat", trace_obj=...) as _out/loop/axis2_hud.py does
#   web copy     : ffmpeg (imageio-ffmpeg binary) H.264, faststart, at most 720p, target < 2 MB
#   frame gate   : every frame of the HUD video and of the web copy through frame_audit.audit; on a defect the file
#                  is moved to out/_rejected/ and no web copy is published (added 2026-10-12 after the 24 defective copies)
# Usage: python hud_make.py --list sel.json [--workers 8] [--stills 0.1,0.4,0.7,0.95] [--only key]
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
LAB_EVAL = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/sim/eval"
sys.path.insert(0, LAB_EVAL)
WEB_MAX = 2_000_000


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def build_trace(parquet_path):
    """Same as _out/loop/axis2_hud.build_trace: parquet rows wrapped as a trace, no row changed."""
    import timeseries
    from overlay import trace as trace_mod
    meta, rows = timeseries.read(parquet_path)
    dt = float(meta["dt_s"])
    out_meta = {"schema": trace_mod.SCHEMA, "fps": 1.0 / dt, "dt_s": dt, "slowmo": 1,
                "command_vx_mps": abs(float(rows[0].get("cmd_vx_mps") or 0.0)), "env_id": meta.get("env_id", ""),
                "terrain": meta.get("family", ""), "fell_at_s": meta.get("fell_at_s", ""),
                "title": meta.get("hud_title", ""),
                # the drift gauge of the HUD draws this as its reference; Q's corridor limit is 0.30 m (q_metrics.CORRIDOR_M)
                "max_lateral_drift_m": 0.30}
    return trace_mod.Trace(out_meta, rows), meta


def stills(video, out_dir, fracs):
    import av
    os.makedirs(out_dir, exist_ok=True)
    with av.open(video) as c:
        frames = [f for f in c.decode(video=0)]
    n = len(frames)
    paths = []
    for fr in fracs:
        i = min(n - 1, int(round(fr * (n - 1))))
        p = os.path.join(out_dir, os.path.basename(video)[:-4] + f"_f{i:04d}.png")
        frames[i].to_image().save(p)
        paths.append(p)
    return paths


def web_copy(src, dst):
    """720p or less, H.264, faststart, no audio. Raise CRF until the file is under 2 MB."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tried = []
    for crf, height in ((28, 720), (31, 720), (33, 720), (31, 540), (34, 540), (36, 540)):
        cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src, "-vf", f"scale=-2:{height}", "-c:v", "libx264",
               "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", dst]
        subprocess.run(cmd, check=True)
        size = os.path.getsize(dst)
        tried.append({"crf": crf, "height": height, "bytes": size})
        if size < WEB_MAX:
            break
    return {"bytes": os.path.getsize(dst), "crf": tried[-1]["crf"], "height": tried[-1]["height"], "tried": tried}


class FrameGateError(RuntimeError):
    """A HUD video or web copy has frames that fail the frame audit; no web copy is published."""


def gate(path, what):
    """Every frame through frame_audit.audit (black / flat / sky criteria of the lead's audit_frames.py).
    On a defect the file is moved to out/_rejected/ and FrameGateError is raised."""
    sys.path.insert(0, HERE)
    import frame_audit
    r = frame_audit.audit(path, fps=0)
    if r["bad"]:
        rej = os.path.join(HERE, "out", "_rejected", os.path.relpath(os.path.abspath(path), os.path.join(HERE, "out")))
        os.makedirs(os.path.dirname(rej), exist_ok=True)
        os.replace(path, rej)
        raise FrameGateError(f"{what} {path}: {r['bad']}/{r['n']} frames fail the frame audit (dark {r['dark']} flat {r['flat']} blue {r['blue']}); moved to {rej}")
    return {"frames": r["n"], "bad": 0, "min_std": r["min_std"], "max_blue": r["max_blue"], "min_mean": r["min_mean"]}


def one(item, fracs, do_web=True):
    from overlay import render as render_mod
    t0 = time.time()
    tr, meta = build_trace(item["parquet"])
    tr.meta["title"] = item["title"]
    out = item["hud"]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    summary = render_mod.render(item["video"], None, out, crf=20, preset="medium", mode="flat", trace_obj=tr, progress_every=0)
    res = {"key": item["key"], "hud": out, "hud_bytes": os.path.getsize(out), "frames": summary["out_frames"],
           "trace_rows": summary["trace_rows"], "video_fps": summary["video_fps"]}
    res["hud_audit"] = gate(out, "HUD")  # gate 1: the HUD video, every frame
    if fracs:
        res["stills"] = stills(out, os.path.join(os.path.dirname(out), "stills"), fracs)
    if do_web:
        res["web"] = item["web"]
        res.update({"web_" + k: v for k, v in web_copy(out, item["web"]).items()})
        res["web_audit"] = gate(item["web"], "web copy")  # gate 2: the web copy, every frame
    res["wall_s"] = round(time.time() - t0, 1)
    return res


def one_safe(item, fracs, do_web=True):
    """one() that reports a failure (frame gate or anything else) instead of stopping the other items."""
    try:
        return one(item, fracs, do_web)
    except Exception as ex:  # the failing item gets no web copy; the others go on
        return {"key": item["key"], "error": f"{type(ex).__name__}: {ex}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True, help="JSON list of {key, video, parquet, hud, web, title}")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--stills", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--no_web", action="store_true")
    ap.add_argument("--report", default=None)
    ap.add_argument("--batch1", action="store_true")
    ap.add_argument("--tags", default="", help="only these tags (whose label renders have finished)")
    a = ap.parse_args()
    items = json.load(open(a.list, encoding="utf-8"))
    if a.only:
        items = [x for x in items if x["key"] in a.only.split(",")]
    items = [x for x in items if (not os.path.exists(x["hud"]) or a.only) and os.path.exists(x["video"]) and os.path.exists(x["parquet"])]
    if a.tags:
        items = [x for x in items if x["tag"] in a.tags.split(",")]
    if a.batch1:
        sys.path.insert(0, HERE)
        import label_runner
        items = [x for x in items if label_runner.batch1(x)]
    fracs = [float(x) for x in a.stills.split(",") if x]
    out = []
    if a.workers <= 1:
        for it in items:
            out.append(one_safe(it, fracs, not a.no_web))
            print(json.dumps(out[-1], ensure_ascii=False), flush=True)
    else:
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            for r in ex.map(one_safe, items, [fracs] * len(items), [not a.no_web] * len(items)):
                out.append(r)
                print(json.dumps(r, ensure_ascii=False), flush=True)
    rep = a.report or (a.list[:-5] + "_report.json")
    prev = json.load(open(rep, encoding="utf-8")) if os.path.exists(rep) else []
    good = [r for r in out if "error" not in r]
    bad = [r for r in out if "error" in r]
    keys = {r["key"] for r in good}
    json.dump([r for r in prev if r["key"] not in keys] + good, open(rep, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if bad:
        json.dump(bad, open(rep[:-5] + "_errors.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"GATE: {len(bad)} item(s) refused, no web copy for them; see {rep[:-5]}_errors.json", flush=True)
        sys.exit(3)


if __name__ == "__main__":
    main()
