"""D435i floor-plane fit and media export from the Go2 X rosbag (sqlite3).

Usage (CPU only):
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 taskset -c 0-7 \
    /home/jay/data/go2x_raw/.venv-rosbags/bin/python go2x_cam_derive.py floor
  ... go2x_cam_derive.py media

Record dir defaults to the parent of this script's folder; outputs go to this script's folder.
Times are bag-relative seconds: (message timestamp - min(timestamp)) * 1e-9 (receive time, not header stamp).

Optical frame: x right, y down, z forward. Floor plane n.X + c = 0 with n oriented toward the camera
(c > 0, c = camera height above the plane). pitch_down = asin(-n_z) (positive = looking down),
roll = atan2(n_x, -n_y) (positive = image right edge higher than left edge).

Note on the earlier hang (cam_floor_local.py): np.linalg.svd(Q - c0) with the default
full_matrices=True on an N x 3 inlier matrix builds an N x N U matrix (N ~ 40000 -> 12.8 GB per
frame). Here the plane normal comes from the 3 x 3 covariance (np.linalg.eigh) instead.
"""
import csv
import json
import os
import sqlite3
import subprocess
import sys
import time

import numpy as np
import cv2
from rosbags.typesys import Stores, get_typestore

cv2.setNumThreads(1)
TS = get_typestore(Stores.ROS2_HUMBLE)
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
DB = os.path.join(REC, "bag", "bag_0.db3")
MON = os.path.join(REC, "monitor.csv")
FFMPEG = "/home/jay/miniforge3/envs/isaac311/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
T0 = time.time()

DMIN, DMAX = 0.15, 4.0          # valid depth range used for the fit (m)
THR = 0.02                      # plane inlier distance (m)
N_SAMPLE = 20000                # points sampled per frame for RANSAC scoring
N_HYP = 400                     # RANSAC hypotheses per frame
NY_MAX = -0.5                   # floor candidate: normal (toward camera) must have n_y < -0.5 (tilt < 60 deg)


def log(*a):
    print(f"[{time.time() - T0:8.2f}s]", *a, flush=True)


def open_db():
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    topics = {n: (i, ty) for i, n, ty in db.execute("select id,name,type from topics")}
    start = db.execute("select min(timestamp) from messages").fetchone()[0]
    end = db.execute("select max(timestamp) from messages").fetchone()[0]
    return db, topics, start, end


def first_msg(db, topics, name):
    i, ty = topics[name]
    raw = db.execute("select data from messages where topic_id=? order by timestamp limit 1", (i,)).fetchone()[0]
    return TS.deserialize_cdr(raw, ty)


def iter_topic(db, topics, name, t0_ns=None, t1_ns=None):
    """Stream (timestamp, msg) in time order without fetchall (keeps memory flat)."""
    i, ty = topics[name]
    if t0_ns is None:
        cur = db.execute("select timestamp,data from messages where topic_id=? order by timestamp", (i,))
    else:
        cur = db.execute("select timestamp,data from messages where topic_id=? and timestamp between ? and ? "
                         "order by timestamp", (i, t0_ns, t1_ns))
    for ts, raw in cur:
        yield ts, TS.deserialize_cdr(raw, ty)


def depth_m(msg):
    assert msg.encoding == "16UC1" and not msg.is_bigendian, (msg.encoding, msg.is_bigendian)
    return np.frombuffer(msg.data, np.uint16).reshape(msg.height, msg.width).astype(np.float32) * 1e-3


def fit_floor(d, rays, rng):
    """Return dict with plane and stats, or None. d: HxW meters, rays: (H*W,2) normalized x,y."""
    flat = d.reshape(-1)
    valid = np.flatnonzero((flat >= DMIN) & (flat <= DMAX))
    if len(valid) < 1000:
        return None
    z = flat[valid].astype(np.float64)
    P = np.empty((len(valid), 3))
    P[:, 0] = rays[valid, 0] * z
    P[:, 1] = rays[valid, 1] * z
    P[:, 2] = z
    S = P[rng.choice(len(P), size=min(len(P), N_SAMPLE), replace=False)]
    idx = rng.integers(0, len(S), size=(N_HYP, 3))
    a, b, c = S[idx[:, 0]], S[idx[:, 1]], S[idx[:, 2]]
    n = np.cross(b - a, c - a)
    nn = np.linalg.norm(n, axis=1)
    ok = nn > 1e-9
    n, a = n[ok] / nn[ok, None], a[ok]
    off = -np.einsum("ij,ij->i", n, a)              # plane n.X + off = 0
    flip = off < 0                                   # orient normal toward camera (off = camera distance > 0)
    n[flip] *= -1
    off[flip] *= -1
    keep = n[:, 1] < NY_MAX                          # roughly horizontal, facing up toward camera
    if not keep.any():
        return None
    n, off = n[keep], off[keep]
    score = (np.abs(S @ n.T + off) < THR).sum(0)
    k = int(np.argmax(score))
    nb, cb = n[k], off[k]
    for _ in range(3):                               # least-squares refit on all valid pixels
        inl = np.abs(P @ nb + cb) < THR
        Q = P[inl]
        if len(Q) < 500:
            return None
        cen = Q.mean(0)
        w, V = np.linalg.eigh(np.cov((Q - cen).T))
        nb = V[:, 0]
        cb = -nb @ cen
        if cb < 0:
            nb, cb = -nb, -cb
    inl = np.abs(P @ nb + cb) < THR
    res = P[inl] @ nb + cb
    mask = np.zeros(flat.shape, bool)
    mask[valid[inl]] = True
    return {
        "n": nb, "height_m": float(cb),
        "pitch_down_deg": float(np.degrees(np.arcsin(-nb[2]))),
        "roll_deg": float(np.degrees(np.arctan2(nb[0], -nb[1]))),
        "inlier_frac": float(inl.mean()), "n_valid": int(len(P)), "n_inlier": int(inl.sum()),
        "rms_resid_m": float(np.sqrt(np.mean(res ** 2))),
        "inlier_depth_med_m": float(np.median(P[inl, 2])),
        "mask": mask.reshape(d.shape),
    }


def colorize_depth(d):
    """0-4 m turbo, invalid (0) black. Returns BGR uint8."""
    u8 = np.clip(d / 4.0 * 255.0, 0, 255).astype(np.uint8)
    img = cv2.applyColorMap(u8, cv2.COLORMAP_TURBO)
    img[d <= 0] = 0
    return img


def decode_jpeg(msg):
    return cv2.imdecode(np.asarray(msg.data, dtype=np.uint8), cv2.IMREAD_COLOR)


def monitor_body_height():
    with open(MON) as f:
        r = csv.reader(f)
        h = next(r)
        i, j = h.index("t_s"), h.index("body_height")
        a = np.array([(float(x[i]), float(x[j])) for x in r])
    return a


def pct(x):
    x = np.asarray(x)
    return {"median": float(np.median(x)), "p10": float(np.percentile(x, 10)), "p90": float(np.percentile(x, 90)),
            "min": float(x.min()), "max": float(x.max())}


def nearest_color(db, topics, start, t_ns):
    i, ty = topics["/camera/camera/color/image_raw/compressed"]
    row = db.execute("select timestamp,data from messages where topic_id=? and timestamp between ? and ? "
                     "order by abs(timestamp-?) limit 1", (i, t_ns - int(2e8), t_ns + int(2e8), t_ns)).fetchone()
    if row is None:
        return None, None
    return (row[0] - start) * 1e-9, decode_jpeg(TS.deserialize_cdr(row[1], ty))


def overlay_png(path, title, d, fit, color, t_d, t_c):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dep = colorize_depth(d)[:, :, ::-1]
    gray = np.clip(d / 4.0, 0, 1)
    ov = np.dstack([gray, gray, gray])
    ov[d <= 0] = 0
    m = fit["mask"]
    ov[m] = 0.35 * ov[m] + 0.65 * np.array([0.1, 0.9, 0.2])
    fig, ax = plt.subplots(1, 3, figsize=(18, 5.4), dpi=100)
    if color is not None:
        ax[0].imshow(color[:, :, ::-1])
        ax[0].set_title(f"color (nearest frame, bag t={t_c:.2f} s)")
    ax[1].imshow(dep)
    ax[1].set_title(f"depth 0-4 m turbo, black = no data (t={t_d:.2f} s)")
    ax[2].imshow(ov)
    ax[2].set_title(f"floor inliers (green, |dist|<{THR*100:.0f} cm)")
    for a in ax:
        a.axis("off")
    fig.suptitle(f"{title}: height {fit['height_m']:.3f} m, pitch down {fit['pitch_down_deg']:.2f} deg, "
                 f"roll {fit['roll_deg']:.2f} deg, inlier frac {fit['inlier_frac']:.2f}, "
                 f"rms {fit['rms_resid_m']*1000:.1f} mm")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def cmd_floor():
    db, topics, start, end = open_db()
    ci = first_msg(db, topics, "/camera/camera/depth/camera_info")
    K = np.array(ci.k).reshape(3, 3)
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    H, W = ci.height, ci.width
    vv, uu = np.mgrid[0:H, 0:W]
    rays = np.c_[((uu - cx) / fx).reshape(-1), ((vv - cy) / fy).reshape(-1)]
    log("bag start", start, "duration", (end - start) * 1e-9, "K", fx, fy, cx, cy, "D", list(ci.d))
    mon = monitor_body_height()
    summary = {"bag_start_ns": start, "depth_intrinsics": {"fx": fx, "fy": fy, "cx": cx, "cy": cy,
               "width": W, "height": H, "distortion_model": ci.distortion_model, "D": [float(x) for x in ci.d]},
               "params": {"depth_range_m": [DMIN, DMAX], "inlier_thr_m": THR, "ransac_sample": N_SAMPLE,
                          "ransac_hypotheses": N_HYP, "floor_candidate_ny_max": NY_MAX}, "windows": {}}
    for name, (w0, w1) in {"standing": (68.0, 98.0), "sitting": (10.0, 55.0)}.items():
        rng = np.random.default_rng(0)
        rows, fails, mid_pick = [], [], None
        tmid = 0.5 * (w0 + w1)
        n_frames = 0
        for ts, msg in iter_topic(db, topics, "/camera/camera/depth/image_rect_raw",
                                  start + int(w0 * 1e9), start + int(w1 * 1e9)):
            n_frames += 1
            t = (ts - start) * 1e-9
            d = depth_m(msg)
            fit = fit_floor(d, rays, rng)
            if fit is None:
                fails.append(round(t, 3))
                continue
            rows.append({"t_s": round(t, 4), "height_m": fit["height_m"], "pitch_down_deg": fit["pitch_down_deg"],
                         "roll_deg": fit["roll_deg"], "inlier_frac": fit["inlier_frac"], "n_valid": fit["n_valid"],
                         "n_inlier": fit["n_inlier"], "rms_resid_m": fit["rms_resid_m"],
                         "inlier_depth_med_m": fit["inlier_depth_med_m"],
                         "nx": float(fit["n"][0]), "ny": float(fit["n"][1]), "nz": float(fit["n"][2])})
            if mid_pick is None or abs(t - tmid) < abs(mid_pick[0] - tmid):
                mid_pick = (t, d, fit)
            if n_frames % 100 == 0:
                log(name, "frames", n_frames, "last", {k: round(v, 3) for k, v in rows[-1].items() if k in
                                                       ("t_s", "height_m", "pitch_down_deg", "roll_deg", "inlier_frac")})
        csv_path = os.path.join(HERE, f"floor_{name}_{int(w0)}-{int(w1)}s.csv")
        with open(csv_path, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
        sel = (mon[:, 0] >= w0) & (mon[:, 0] <= w1)
        bh = float(np.median(mon[sel, 1]))
        hs = [r["height_m"] for r in rows]
        summary["windows"][name] = {
            "window_s": [w0, w1], "depth_frames_in_window": n_frames, "frames_fitted": len(rows),
            "frames_failed_t_s": fails,
            "height_m": pct(hs), "pitch_down_deg": pct([r["pitch_down_deg"] for r in rows]),
            "roll_deg": pct([r["roll_deg"] for r in rows]), "inlier_frac": pct([r["inlier_frac"] for r in rows]),
            "rms_resid_m": pct([r["rms_resid_m"] for r in rows]),
            "monitor_body_height_median_m": bh, "monitor_samples": int(sel.sum()),
            "camera_height_minus_body_height_m": float(np.median(hs)) - bh,
            "per_frame_csv": os.path.basename(csv_path),
        }
        t, d, fit = mid_pick
        t_c, color = nearest_color(db, topics, start, start + int(t * 1e9))
        png = os.path.join(HERE, f"floor_overlay_{name}_t{t:06.2f}s.png")
        overlay_png(png, f"{name} t={t:.2f} s", d, fit, color, t, t_c)
        summary["windows"][name]["overlay_png"] = os.path.basename(png)
        log(name, json.dumps({k: v for k, v in summary["windows"][name].items() if k != "frames_failed_t_s"}))
    with open(os.path.join(HERE, "floor_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    log("done floor")


class FFWriter:
    def __init__(self, path, w, h, fps):
        self.p = subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                                   "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                                   "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
                                   "-threads", "4", "-movflags", "+faststart", path], stdin=subprocess.PIPE)

    def write(self, img):
        self.p.stdin.write(np.ascontiguousarray(img).tobytes())

    def close(self):
        self.p.stdin.close()
        rc = self.p.wait()
        assert rc == 0, rc


def put_text(img, s, y, color=(255, 255, 255)):
    cv2.putText(img, s, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, s, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)


def make_video(db, topics, start, end, topic, render, label, path, fps=30):
    """Constant-fps output; slot k (t=k/fps) shows the latest frame with bag t <= slot t (timing preserved)."""
    dur = (end - start) * 1e-9
    nslots = int(np.floor(dur * fps)) + 1
    it = iter_topic(db, topics, topic)
    cur_img, cur_t, nxt = None, None, next(it, None)
    writer, n_in, n_out, max_gap, prev_t = None, 0, 0, 0.0, None
    for k in range(nslots):
        ts_slot = k / fps
        while nxt is not None and (nxt[0] - start) * 1e-9 <= ts_slot:
            cur_t = (nxt[0] - start) * 1e-9
            cur_img = render(nxt[1])
            if prev_t is not None:
                max_gap = max(max_gap, cur_t - prev_t)
            prev_t = cur_t
            n_in += 1
            nxt = next(it, None)
        if writer is None:
            if cur_img is None and nxt is not None:
                h, w = render(nxt[1]).shape[:2]
            else:
                h, w = cur_img.shape[:2]
            writer = FFWriter(path, w, h, fps)
            blank = np.zeros((h, w, 3), np.uint8)
        frame = blank.copy() if cur_img is None else cur_img.copy()
        if cur_img is None:
            put_text(frame, f"{label}  bag t={ts_slot:7.2f} s  (no frame yet)", 22)
        else:
            age = ts_slot - cur_t
            put_text(frame, f"{label}  bag t={cur_t:7.2f} s", 22, (255, 255, 255) if age < 0.2 else (0, 0, 255))
            if age >= 0.2:
                put_text(frame, f"stale {age:.2f} s (no newer frame)", 44, (0, 0, 255))
        writer.write(frame)
        n_out += 1
        if k % 1500 == 0:
            log(path, "slot", k, "/", nslots, "frames in", n_in)
    writer.close()
    return {"slots": n_out, "fps": fps, "input_frames": n_in, "max_input_gap_s": round(max_gap, 3),
            "duration_s": round(nslots / fps, 2)}


def depth_render_with_bar(msg):
    d = depth_m(msg)
    img = colorize_depth(d)
    h, w = img.shape[:2]
    bar = cv2.applyColorMap(np.tile(np.linspace(0, 255, w).astype(np.uint8), (12, 1)), cv2.COLORMAP_TURBO)
    img[h - 30:h - 18] = bar
    for m in range(0, 5):
        x = min(int(m / 4 * (w - 1)) + 2, w - 34)
        cv2.putText(img, f"{m} m", (x, h - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def cmd_media():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    db, topics, start, end = open_db()
    info = {}
    # stills
    for tt in (80.0, 150.0, 250.0):
        t_c, color = nearest_color(db, topics, start, start + int(tt * 1e9))
        p = os.path.join(HERE, f"still_color_t{tt:03.0f}s.png")
        cv2.imwrite(p, color)
        i, ty = topics["/camera/camera/depth/image_rect_raw"]
        ts, raw = db.execute("select timestamp,data from messages where topic_id=? and timestamp between ? and ? "
                             "order by abs(timestamp-?) limit 1",
                             (i, start + int((tt - 0.5) * 1e9), start + int((tt + 0.5) * 1e9),
                              start + int(tt * 1e9))).fetchone()
        t_d = (ts - start) * 1e-9
        d = depth_m(TS.deserialize_cdr(raw, ty))
        dm = np.ma.masked_less_equal(d, 0)
        cmap = plt.get_cmap("turbo").copy()
        cmap.set_bad("black")
        fig, ax = plt.subplots(figsize=(8, 6.4), dpi=100)
        im = ax.imshow(dm, cmap=cmap, vmin=0, vmax=4)
        ax.set_title(f"depth bag t={t_d:.2f} s (0-4 m, black = no data, valid {np.mean(d > 0)*100:.0f} %)")
        ax.axis("off")
        fig.colorbar(im, ax=ax, fraction=0.035, label="m")
        fig.tight_layout()
        pd = os.path.join(HERE, f"still_depth_t{tt:03.0f}s.png")
        fig.savefig(pd)
        plt.close(fig)
        info[f"still_{tt:.0f}"] = {"color_t_s": round(t_c, 3), "depth_t_s": round(t_d, 3)}
        log("still", tt, info[f"still_{tt:.0f}"])
    info["color_mp4"] = make_video(db, topics, start, end, "/camera/camera/color/image_raw/compressed",
                                   decode_jpeg, "color", os.path.join(HERE, "color_full.mp4"))
    log("color", info["color_mp4"])
    info["depth_mp4"] = make_video(db, topics, start, end, "/camera/camera/depth/image_rect_raw",
                                   depth_render_with_bar, "depth 0-4 m", os.path.join(HERE, "depth_full.mp4"))
    log("depth", info["depth_mp4"])
    with open(os.path.join(HERE, "media_info.json"), "w") as f:
        json.dump(info, f, indent=1)
    log("done media")


if __name__ == "__main__":
    {"floor": cmd_floor, "media": cmd_media}[sys.argv[1]]()
