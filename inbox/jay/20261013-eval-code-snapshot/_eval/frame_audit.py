# Frame audit of replay / HUD / web videos (lead's audit_frames.py criteria, ffmpeg from imageio-ffmpeg):
# 3D area only (720p y 224..616, between the HUD panel and the bottom strip), a frame is bad when
#   dark: mean luminance < 20 · flat: luminance std < 6 · blue: share of blue-dominant pixels (b > r + 25 and b > g + 10) > 0.35
# Usage: python frame_audit.py [--fps 4 | --fps 0 for every frame] [--workers 16] [--out out/frame_audit.json] <files or globs ...>
import argparse
import glob
import json
import os
import subprocess

import numpy as np

W, H = 160, 90
Y0, Y1 = 28, 77  # 720p y 224..616 at 90 rows


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def frames(path, fps):
    vf = (f"fps={fps}," if fps else "") + f"scale={W}:{H}"
    p = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W, 3)


def audit(path, fps=4):
    fr = frames(path, fps).astype(np.float32)
    reg = fr[:, Y0:Y1]
    lum = reg.mean(axis=3)
    mean, std = lum.mean(axis=(1, 2)), lum.std(axis=(1, 2))
    r, g, b = reg[..., 0], reg[..., 1], reg[..., 2]
    blue = ((b > r + 25) & (b > g + 10)).mean(axis=(1, 2))
    bad = (mean < 20) | (std < 6) | (blue > 0.35)
    idx = np.nonzero(bad)[0]
    step = 1.0 / fps if fps else 0.02
    return {"file": path.replace("\\", "/"), "n": int(len(fr)), "bad": int(len(idx)), "frac": round(len(idx) / max(1, len(fr)), 3),
            "dark": int(((mean < 20)).sum()), "flat": int((std < 6).sum()), "blue": int((blue > 0.35).sum()),
            "first_bad_t": [round(float(k * step), 2) for k in idx[:12]],
            "min_std": round(float(std.min()), 1), "max_blue": round(float(blue.max()), 3), "min_mean": round(float(mean.min()), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=float, default=4)
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    files = sorted({f for g in a.files for f in glob.glob(g)})
    if a.workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.workers) as ex:
            res = list(ex.map(audit, files, [a.fps] * len(files)))
    else:
        res = [audit(f, a.fps) for f in files]
    if a.out:
        json.dump(res, open(a.out, "w", encoding="utf-8"), indent=1)
    flag = [x for x in res if x["bad"]]
    print(json.dumps({"videos": len(res), "flagged": len(flag)}))
    for x in sorted(flag, key=lambda x: -x["frac"])[:60]:
        print(f"{x['frac']:.2f} {x['bad']}/{x['n']} dark{x['dark']} flat{x['flat']} blue{x['blue']} {x['file']} {x['first_bad_t']}")
    return res


if __name__ == "__main__":
    main()
