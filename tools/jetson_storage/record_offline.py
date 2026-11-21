"""Read a Go2 X rosbag2 sqlite recording on ai-lx01 (no ROS here): topic table, camera floor plane while standing,
body tilt from sportmodestate, L2 rate and field of view, odom return error, top-view map like room_map.py.
Minimal CDR (XCDR1 little endian) reader for the few message types used. numpy + matplotlib only.

  python record_offline.py <record folder> <stand start s> <stand end s> <out dir>
"""
import glob
import json
import math
import os
import sqlite3
import struct
import sys

import numpy as np


class Cdr:
    def __init__(self, b):
        self.b, self.o = b, 4                                   # 4-byte encapsulation header

    def al(self, n):
        r = (self.o - 4) % n
        if r:
            self.o += n - r

    def p(self, fmt, n):
        self.al(n)
        v = struct.unpack_from('<' + fmt, self.b, self.o)
        self.o += struct.calcsize('<' + fmt)
        return v if len(v) != 1 else v[0]

    def u8(self): return self.p('B', 1)
    def u32(self): return self.p('I', 4)
    def i16(self): return self.p('h', 2)
    def f32(self, k=1): return self.p('%df' % k, 4)
    def f64(self, k=1): return self.p('%dd' % k, 8)

    def s(self):
        n = self.u32()
        v = self.b[self.o:self.o + n - 1].decode('utf-8', 'replace')
        self.o += n
        return v

    def header(self):
        sec, nsec = self.p('iI', 4)
        return sec + nsec * 1e-9, self.s()

    def blob(self):
        n = self.u32()
        v = self.b[self.o:self.o + n]
        self.o += n
        return v


def odometry(b):
    c = Cdr(b); c.header(); c.s()
    pos = c.f64(3); q = c.f64(4)
    return pos, q


def sportmode(b):
    c = Cdr(b)
    c.p('iI', 4); c.u32()                                       # stamp, error_code
    quat = c.f32(4); c.f32(3); c.f32(3); rpy = c.f32(3); c.u8()  # imu_state
    c.u8(); c.f32(); c.u8(); c.f32()                            # mode, progress, gait, foot_raise
    pos = c.f32(3); body_h = c.f32()
    return rpy, body_h, pos


def cloud(b):
    c = Cdr(b); c.header()
    h, w = c.u32(), c.u32()
    fields = {}
    for _ in range(c.u32()):
        name = c.s(); off = c.u32(); c.u8(); c.u32()
        fields[name] = off
    c.u8(); step = c.u32(); c.u32()
    data = c.blob()
    n = h * w
    a = np.frombuffer(data, np.uint8)[:n * step].reshape(n, step)
    xyz = np.stack([a[:, fields[k]:fields[k] + 4].copy().view('<f4')[:, 0] for k in 'xyz'], 1)
    return xyz[np.isfinite(xyz).all(1)]


def image16(b):
    c = Cdr(b); c.header()
    h, w = c.u32(), c.u32(); enc = c.s(); c.u8(); c.u32()
    return np.frombuffer(c.blob(), '<u2').reshape(h, w), enc


def caminfo(b):
    c = Cdr(b); c.header()
    h, w = c.u32(), c.u32(); model = c.s()
    d = c.f64(c.u32())
    k = c.f64(9)
    return dict(width=w, height=h, model=model, d=list(d) if isinstance(d, tuple) else [d], fx=k[0], fy=k[4], cx=k[2], cy=k[5])


def floor_plane(d, K, rng):
    fx, fy, cx, cy = K
    v, u = np.nonzero((d > 0.3) & (d < 4.0))
    if len(u) < 1000:
        return None
    sel = rng.choice(len(u), size=min(len(u), 40000), replace=False)
    u, v = u[sel], v[sel]
    z = d[v, u]
    P = np.c_[(u - cx) / fx * z, (v - cy) / fy * z, z]
    best = None
    for _ in range(300):                                        # same RANSAC as Jetson cam_floor.py
        a, b_, c_ = P[rng.choice(len(P), 3, replace=False)]
        n = np.cross(b_ - a, c_ - a); nn = np.linalg.norm(n)
        if nn < 1e-6:
            continue
        n /= nn
        if n[1] > 0:
            n = -n
        if n[1] > -0.5:
            continue
        inl = np.abs(P @ n - np.dot(n, a)) < 0.015
        if best is None or inl.sum() > best[1].sum():
            best = (n, inl)
    if best is None:
        return None
    Q = P[best[1]]; c0 = Q.mean(0)
    n = np.linalg.svd(Q - c0)[2][-1]
    if n[1] > 0:
        n = -n
    return dict(height_m=float(abs(np.dot(n, c0))), pitch_deg=float(np.degrees(np.arcsin(-n[2]))),
                roll_deg=float(np.degrees(np.arctan2(n[0], -n[1]))), inlier_frac=float(best[1].mean()))


def med(xs):
    return round(float(np.median(xs)), 3) if len(xs) else None


def main():
    rec, s0, s1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    os.makedirs(out, exist_ok=True)
    db = sqlite3.connect(glob.glob(os.path.join(rec, 'bag', '*.db3'))[0])
    tid = {n: (i, t) for i, n, t in db.execute('select id, name, type from topics')}
    rows = db.execute('select t.name, t.type, count(m.id), coalesce(sum(length(m.data)),0), min(m.timestamp), max(m.timestamp) '
                      'from topics t left join messages m on m.topic_id = t.id group by t.id').fetchall()
    t_start = min(r[4] for r in rows if r[4]) * 1e-9
    t_end = max(r[5] for r in rows if r[5]) * 1e-9
    dur = t_end - t_start
    table = []
    for name, typ, n, size, a, b in sorted(rows):
        span = (b - a) * 1e-9 if n > 1 else 0
        table.append(dict(name=name, type=typ, messages=n, mb=round(size / 1e6, 1), hz=round((n - 1) / span, 2) if span else 0,
                          avg_kb=round(size / max(n, 1) / 1e3, 1), first_s=round(a * 1e-9 - t_start, 1) if a else None))

    def msgs(name, every=1):
        if name not in tid:
            return
        for k, (t, data) in enumerate(db.execute('select timestamp, data from messages where topic_id=? order by timestamp',
                                                 (tid[name][0],))):
            if k % every == 0:
                yield t * 1e-9 - t_start, data

    # body while standing
    rpy, bh = [], []
    for rel, b in msgs('/sportmodestate'):
        if s0 <= rel <= s1:
            r_, h_, _ = sportmode(b)
            rpy.append(r_); bh.append(h_)
    rpy = np.degrees(np.array(rpy)) if rpy else np.zeros((0, 3))
    body = dict(roll_deg=med(rpy[:, 0]), pitch_deg=med(rpy[:, 1]), body_height_m=med(bh), samples=len(bh))

    # camera
    info = None
    for _, b in msgs('/camera/camera/depth/camera_info'):
        info = caminfo(b); break
    cinfo = None
    for _, b in msgs('/camera/camera/color/camera_info'):
        cinfo = caminfo(b); break
    rng = np.random.default_rng(0)
    planes, enc, dshape = [], None, None
    if info:
        K = (info['fx'], info['fy'], info['cx'], info['cy'])
        for rel, b in msgs('/camera/camera/depth/image_rect_raw', 6):
            if s0 <= rel <= s1:
                img, enc = image16(b); dshape = img.shape
                f = floor_plane(img.astype(np.float32) * 1e-3, K, rng)
                if f:
                    f['t'] = round(rel, 2); planes.append(f)
    H = [p['height_m'] for p in planes]; Pd = [p['pitch_deg'] for p in planes]; Rd = [p['roll_deg'] for p in planes]
    cam = dict(depth_info=info, color_info=cinfo, depth_encoding=enc, depth_shape=dshape, frames_used=len(planes),
               height_above_floor_m=med(H), pitch_down_deg=med(Pd), roll_deg=med(Rd),
               pitch_p10_p90=[round(float(np.percentile(Pd, q)), 2) for q in (10, 90)] if Pd else None,
               inlier_frac=med([p['inlier_frac'] for p in planes]))
    if Pd and body['pitch_deg'] is not None:
        # sportmodestate rpy: pitch > 0 = nose down (ROS y-axis). camera pitch is measured down from level,
        # so the mount angle relative to the body is camera pitch minus body pitch; same for roll.
        cam['pitch_down_vs_body_deg'] = round(cam['pitch_down_deg'] - body['pitch_deg'], 2)
        cam['roll_vs_body_deg'] = round(cam['roll_deg'] - body['roll_deg'], 2)
    if H and body['body_height_m']:
        cam['height_above_body_m'] = round(cam['height_above_floor_m'] - body['body_height_m'], 3)

    # L2 and odom
    pts, frames, az, el = 0, 0, [], []
    for k, (rel, b) in enumerate(msgs('/utlidar/cloud')):
        c = Cdr(b); c.header(); h, w = c.u32(), c.u32(); pts += h * w; frames += 1
        if k % 50 == 0:
            xyz = cloud(b)
            if len(xyz):
                az.append(np.degrees(np.arctan2(xyz[:, 1], xyz[:, 0])))
                el.append(np.degrees(np.arctan2(xyz[:, 2], np.hypot(xyz[:, 0], xyz[:, 1]))))
    odom = np.array([(rel,) + odometry(b)[0] for rel, b in msgs('/utlidar/robot_odom')])
    if not len(odom) or not frames:
        # 11/19 22:29 lodging: the bag had camera topics only (no L2, odom, imu, sportmodestate)
        missing = [t for t in ('/utlidar/cloud', '/utlidar/cloud_deskewed', '/utlidar/robot_odom', '/utlidar/imu',
                               '/sportmodestate') if t not in tid or not next((1 for r in table if r['name'] == t and r['messages']), 0)]
        res_ = dict(record=os.path.basename(rec.rstrip('/')), duration_s=round(dur, 1), stand_window_s=[s0, s1], topics=table,
                    body_while_standing=body, camera=cam, l2='L2 없음', odom='odom 없음', map='L2 없음 · 지도 못 만듦',
                    missing_topics=missing)
        json.dump(res_, open(os.path.join(out, 'record_summary.json'), 'w'), indent=1, ensure_ascii=False)
        json.dump(planes, open(os.path.join(out, 'floor_planes.json'), 'w'), indent=1)
        print(json.dumps({k: v for k, v in res_.items() if k != 'topics'}, ensure_ascii=False))
        return
    walk =odom[(odom[:, 0] >= s1)] if len(odom) else odom
    path_len = float(np.sum(np.hypot(np.diff(odom[:, 1]), np.diff(odom[:, 2])))) if len(odom) > 1 else 0
    stand_xy = odom[(odom[:, 0] >= s0) & (odom[:, 0] <= s1)][:, 1:3].mean(0) if len(odom) else None
    l2 = dict(frames=frames, hz=round(frames / dur, 2), points_per_s=int(pts / dur), points_per_frame=int(pts / max(frames, 1)),
              azimuth_deg_p1_p99=[round(float(np.percentile(np.concatenate(az), q)), 1) for q in (1, 99)] if az else None,
              elevation_deg_p1_p99=[round(float(np.percentile(np.concatenate(el), q)), 1) for q in (1, 99)] if el else None)

    # map (same rules as room_map.py)
    P, last_xy, oi = [], None, 0
    for rel, b in msgs('/utlidar/cloud_deskewed'):
        while oi < len(odom) - 1 and odom[oi, 0] < rel:
            oi += 1
        last_xy = odom[oi, 1:3] if len(odom) else None
        a = cloud(b)
        if len(a) and last_xy is not None:
            d = np.hypot(a[:, 0] - last_xy[0], a[:, 1] - last_xy[1])
            P.append(a[d > 0.6][::2].astype(np.float32))
    P = np.concatenate(P) if P else np.zeros((0, 3), np.float32)
    floor = float(np.percentile(P[:, 2], 2)) if len(P) else 0.0
    path = odom[::15]
    xmin, xmax = path[:, 1].min() - 5, path[:, 1].max() + 5
    ymin, ymax = path[:, 2].min() - 5, path[:, 2].max() + 5
    keep = (P[:, 0] > xmin) & (P[:, 0] < xmax) & (P[:, 1] > ymin) & (P[:, 1] < ymax)
    P = P[keep]; z = P[:, 2] - floor; res = 0.05
    W, Hh = int((xmax - xmin) / res) + 1, int((ymax - ymin) / res) + 1
    ix = ((P[:, 0] - xmin) / res).astype(int); iy = ((P[:, 1] - ymin) / res).astype(int)
    cnt = np.zeros((Hh, W), np.int32); np.add.at(cnt, (iy, ix), 1)
    top = np.full((Hh, W), np.nan, np.float32); o = np.argsort(z); top[iy[o], ix[o]] = z[o]
    om = (z > 0.15) & (z < 1.8); occ = np.zeros((Hh, W), np.int32); np.add.at(occ, (iy[om], ix[om]), 1)
    fm = z <= 0.08; flr = np.zeros((Hh, W), np.int32); np.add.at(flr, (iy[fm], ix[fm]), 1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ext = [xmin, xmax, ymin, ymax]
    fig, axs = plt.subplots(1, 2, figsize=(16, 8), dpi=110)
    im = axs[0].imshow(np.where(cnt > 0, top, np.nan), origin='lower', extent=ext, cmap='viridis', vmin=0, vmax=2.0)
    axs[0].set_title('Top view: highest point per 5 cm cell (m above floor)')
    fig.colorbar(im, ax=axs[0], fraction=0.046)
    grid = np.full((Hh, W, 3), 0.55); grid[flr > 5] = (1, 1, 1); grid[(occ > 20) & (occ > 0.3 * cnt)] = (0.1, 0.1, 0.1)
    axs[1].imshow(grid, origin='lower', extent=ext)
    axs[1].set_title('Occupancy: white floor / black obstacle 0.15-1.8 m / grey unknown')
    for ax in axs:
        ax.plot(path[:, 1], path[:, 2], 'r-', lw=1.5, label='robot path (odom)')
        ax.plot(path[0, 1], path[0, 2], 'go', ms=8, label='start')
        ax.plot(path[-1, 1], path[-1, 2], 'bs', ms=7, label='end')
        ax.set_xlabel('x (m)'); ax.set_ylabel('y (m)'); ax.set_aspect('equal'); ax.legend(loc='upper right')
    fig.tight_layout(); fig.savefig(os.path.join(out, 'room_topview.png'))
    end_xy = odom[-1, 1:3]
    res_ = dict(record=os.path.basename(rec.rstrip('/')), duration_s=round(dur, 1), stand_window_s=[s0, s1], topics=table,
                body_while_standing=body, camera=cam, l2=l2,
                odom=dict(path_len_m=round(path_len, 2), stand_xy=[round(float(x), 3) for x in stand_xy],
                          end_xy=[round(float(x), 3) for x in end_xy],
                          end_minus_stand_m=round(float(np.hypot(*(end_xy - stand_xy))), 3),
                          walk_samples=len(walk)),
                map=dict(points_kept=int(len(P)), floor_z=round(floor, 3), extent_m=[round(xmax - xmin, 2), round(ymax - ymin, 2)],
                         obstacle_cells=int(((occ > 20) & (occ > 0.3 * cnt)).sum()), floor_cells=int((flr > 5).sum())))
    json.dump(res_, open(os.path.join(out, 'record_summary.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump(planes, open(os.path.join(out, 'floor_planes.json'), 'w'), indent=1)
    print(json.dumps({k: v for k, v in res_.items() if k != 'topics'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
