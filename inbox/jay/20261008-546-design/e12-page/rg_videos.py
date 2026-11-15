# -*- coding: utf-8 -*-
"""MuJoCo (RoboGauge) clips for page 6판 (lead 10/13 16:45): web copies + an every-frame check of source and copy.

Every frame is decoded (no sampling: 4 fps once missed a black frame, memory a-narrow-net). Per frame, at 160x90 gray:
  dark   mean < 20 · flat   std < 6 · frozen  identical to the previous frame (counted, not a failure by itself)
Known answers first: audit_selftest/known_2black.mp4 must give dark 2, known_clean.mp4 dark 0.
Web copy: 854x480, h264 yuv420p, CRF 26, faststart, no audio. Frame count of copy must equal source.
Output: rg_videos.json (per clip: frames, dark, flat, frozen, sizes, sha256 of the copy)."""
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

SRC = "C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/videos"
SELF = "C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge/audit_selftest"
SP = "C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/09bbf294-fda0-4c7b-81c5-e23f793f2be2/scratchpad/e12page"
OUT = os.path.join(SP, "v")
W, H = 160, 90


def frames(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    return a.reshape(-1, H, W) if a.size % (W * H) == 0 else None


def audit(path):
    f = frames(path)
    if f is None or len(f) == 0:
        return {"error": "decode"}
    m, s = f.reshape(len(f), -1).mean(1), f.reshape(len(f), -1).std(1)
    frozen = int(sum(1 for i in range(1, len(f)) if np.array_equal(f[i], f[i - 1])))
    return {"frames": int(len(f)), "dark": int((m < 20).sum()), "flat": int((s < 6).sum()), "frozen": frozen,
            "dark_idx": [int(i) for i in np.where(m < 20)[0][:10]], "min_mean": round(float(m.min()), 1), "min_std": round(float(s.min()), 1)}


res = {"selftest": {n: audit(os.path.join(SELF, n)) for n in ("known_2black.mp4", "known_clean.mp4")}}
ok_self = res["selftest"]["known_2black.mp4"].get("dark") == 2 and res["selftest"]["known_clean.mp4"].get("dark") == 0
res["selftest_ok"] = ok_self
if not ok_self:
    print(json.dumps(res, indent=1))
    sys.exit("SELFTEST FAILED")
os.makedirs(OUT, exist_ok=True)
res["clips"] = {}
for n in sorted(os.listdir(SRC)):
    if not n.endswith(".mp4"):
        continue
    src = os.path.join(SRC, n)
    dst = os.path.join(OUT, "rg_" + n.replace("model_20000", "20000").replace("ref_sym_v5.1", "ref"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", "scale=854:480", "-c:v", "libx264", "-crf", "26", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", dst], check=True)
    a, b = audit(src), audit(dst)
    res["clips"][n] = {"web": os.path.basename(dst), "src": a, "web_audit": b, "src_MB": round(os.path.getsize(src) / 1e6, 2),
                       "web_MB": round(os.path.getsize(dst) / 1e6, 2), "web_sha256": hashlib.sha256(open(dst, "rb").read()).hexdigest(),
                       "same_frame_count": a.get("frames") == b.get("frames"),
                       "bad": a.get("dark", 1) + a.get("flat", 1) + b.get("dark", 1) + b.get("flat", 1)}
    print(n, a.get("frames"), b.get("frames"), "dark/flat", a.get("dark"), a.get("flat"), b.get("dark"), b.get("flat"), "frozen", a.get("frozen"), b.get("frozen"), res["clips"][n]["web_MB"], "MB")
res["all_ok"] = all(c["bad"] == 0 and c["same_frame_count"] for c in res["clips"].values())
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rg_videos.json"), "w", encoding="utf-8"), indent=1)
print("selftest", ok_self, "clips", len(res["clips"]), "all_ok", res["all_ok"], "web MB", round(sum(c["web_MB"] for c in res["clips"].values()), 1))
