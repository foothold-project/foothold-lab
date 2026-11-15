# Frame gate for the randomization scene videos (no Isaac import; tested on CPU by test_rand_scenes.py).
# Criteria are the lead's audit_frames.py ones, as in _eval/frame_audit.py and _eval/q_video.py (RECORD-HUD.md 5-1):
#   3D area of a 1280 x 720 frame (y 224..616, between the top text box and the bottom strip) is bad when
#   mean luminance < 20 (black) · luminance std < 6 (flat) · share of blue-dominant pixels (b > r + 25 and b > g + 10) > 0.35
#   (sky only). Plus, in the render loop, the projected base must be on screen and the window around it not black.
# Two places:
#   1. render loop (q_rand.py): capture_with_gate() re-renders a failing frame up to max_rerender times, then raises
#      FrameGateError (the run stops, no video). The driver retries the scene in a new process.
#   2. publish: every frame of the master video and of the web copy through _eval/frame_audit.audit(fps=0) (imported,
#      not copied, so the gate is the same one the HUD videos passed). On a defect the file goes to <attempt>/rejected/
#      and no web copy is left in place.
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(HERE)
Y0, Y1 = 224, 616  # 3D area rows at 720p
DARK, FLAT, BLUE = 20.0, 6.0, 0.35
WEB_LADDER = (28, 31, 33)  # crf at 720p; never below 720p (the lead's 720p · 30 fps request)
WEB_TARGET = 2_000_000  # bytes, a target (smallest crf that reaches it), not a gate


class FrameGateError(RuntimeError):
    """A frame or a video failed the frame gate."""


def frame_check(a):
    """One RGB frame (H, W, 3) uint8 at 720p. Returns (ok, reason, stats)."""
    h = a.shape[0]
    y0, y1 = int(round(Y0 * h / 720)), int(round(Y1 * h / 720))
    reg = a[y0:y1:4, ::4, :3].astype(np.float32)
    lum = reg.mean(axis=2)
    r_, g_, b_ = reg[..., 0], reg[..., 1], reg[..., 2]
    blue = float(((b_ > r_ + 25) & (b_ > g_ + 10)).mean())
    st = {"mean": float(lum.mean()), "std": float(lum.std()), "blue": blue}
    if st["mean"] < DARK:
        return False, "dark", st
    if st["std"] < FLAT:
        return False, "flat", st
    if blue > BLUE:
        return False, "blue", st
    return True, "", st


def robot_window_check(a, uv):
    """Projected base inside the frame and the 120 px window around it not black (no colour test: the shaded underside of a
    fallen robot reads blue-dominant, q_video.py note)."""
    h_px, w_px = a.shape[:2]
    if uv is None:
        return True, ""
    u0, v0 = int(round(uv[0])), int(round(uv[1]))
    if not (0 <= u0 < w_px and 0 <= v0 < h_px):
        return False, "robot_off_frame"
    win = a[max(0, v0 - 60):v0 + 60:2, max(0, u0 - 60):u0 + 60:2, :3].astype(np.float32)
    if win.mean() < DARK:
        return False, "robot_window_dark"
    return True, ""


def project(eye, target, pt, w_px, h_px, hfov):
    """Pixel of a world point for a camera at eye looking at target (world z up, square pixels). Same as q_video.py."""
    e, t_, q_ = np.asarray(eye, float), np.asarray(target, float), np.asarray(pt, float)
    f = (t_ - e) / np.linalg.norm(t_ - e)
    rgt = np.cross(f, [0.0, 0.0, 1.0])
    rgt /= np.linalg.norm(rgt)
    up = np.cross(rgt, f)
    d = q_ - e
    zc = d @ f
    fx = w_px / (2.0 * np.tan(hfov / 2.0))
    return w_px / 2.0 + (d @ rgt) / zc * fx, h_px / 2.0 - (d @ up) / zc * fx, zc


def capture_with_gate(render, uv, max_rerender, frame_index, rerender_log):
    """render() -> RGB frame. Re-render while the frame fails, at most max_rerender times. Appends
    (frame_index, reason, tries, ok) to rerender_log for every re-render. Raises FrameGateError when still failing."""
    arr = render(0)
    ok, why, _ = frame_check(arr)
    if ok:
        ok, why = robot_window_check(arr, uv)
    tries = 0
    while not ok and tries < max_rerender:
        tries += 1
        arr = render(tries)
        ok, why2, _ = frame_check(arr)
        if ok:
            ok, why2 = robot_window_check(arr, uv)
        rerender_log.append((frame_index, why, tries, ok))
        if not ok:
            why = why2
    if not ok:
        raise FrameGateError(f"FRAME_GATE frame {frame_index} fails ({why}) after {tries} re-renders")
    return arr


# --- files -------------------------------------------------------------------------------------------------------------
def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def audit(path):
    """Every frame through _eval/frame_audit.audit (fps=0: no sampling, a single black frame counts)."""
    if EVAL not in sys.path:
        sys.path.insert(0, EVAL)
    import frame_audit
    return frame_audit.audit(path, fps=0)


def probe(path):
    """codec, size, average frame rate, frame count (decoded), via PyAV."""
    import av
    with av.open(path) as c:
        s = c.streams.video[0]
        n = sum(1 for _ in c.decode(video=0))
        return {"codec": s.codec_context.name, "width": s.codec_context.width, "height": s.codec_context.height,
                "fps": float(s.average_rate) if s.average_rate else 0.0, "frames": n, "pix_fmt": s.codec_context.pix_fmt,
                "bytes": os.path.getsize(path)}


def web_copy(src, dst, fps=30):
    """H.264 · yuv420p · 30 fps (ffmpeg fps filter) · 720p · +faststart · no audio. Smallest crf on the ladder that
    reaches the size target; the last rung is kept if none does."""
    tried = []
    for crf in WEB_LADDER:
        cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src, "-vf", f"fps={fps},scale=-2:720", "-c:v", "libx264",
               "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", dst]
        subprocess.run(cmd, check=True)
        tried.append({"crf": crf, "bytes": os.path.getsize(dst)})
        if tried[-1]["bytes"] < WEB_TARGET:
            break
    return {"crf": tried[-1]["crf"], "bytes": tried[-1]["bytes"], "tried": tried, "size_target_bytes": WEB_TARGET}


def _reject(path, rejected_dir):
    os.makedirs(rejected_dir, exist_ok=True)
    dst = os.path.join(rejected_dir, os.path.basename(path))
    os.replace(path, dst)
    return dst


def _summ(r):
    return {k: r[k] for k in ("n", "bad", "dark", "flat", "blue", "first_bad_t", "min_std", "max_blue", "min_mean")}


def publish(master, web, rejected_dir, expect_master_frames=None, make_web=web_copy):
    """Gate the master (every frame), make the web copy, gate it (every frame) and check codec / size / rate / faststart.
    Any failure: the failing file goes to rejected_dir and FrameGateError is raised (no web copy left in place)."""
    sys.path.insert(0, HERE)
    import rand_lib as RL
    out = {}
    am = audit(master)
    out["gate_master"] = _summ(am)
    if am["bad"] or (expect_master_frames is not None and am["n"] != expect_master_frames):
        moved = _reject(master, rejected_dir)
        raise FrameGateError(f"FRAME_GATE master {master}: bad {am['bad']}/{am['n']} (expected frames {expect_master_frames}); moved to {moved}")
    out["web_encode"] = make_web(master, web)
    aw = audit(web)
    out["gate_web"] = _summ(aw)
    pr = probe(web)
    out["web_probe"] = pr
    fs = RL.faststart_ok(web)
    out["web_faststart"] = fs
    bad = []
    if aw["bad"]:
        bad.append(f"bad frames {aw['bad']}/{aw['n']}")
    if pr["codec"] != "h264" or pr["height"] != 720 or pr["width"] != 1280 or abs(pr["fps"] - 30.0) > 0.01:
        bad.append(f"format {pr}")
    if not fs:
        bad.append("not faststart")
    if bad:
        moved = _reject(web, rejected_dir)
        raise FrameGateError(f"FRAME_GATE web {web}: {'; '.join(bad)}; moved to {moved}")
    return out
