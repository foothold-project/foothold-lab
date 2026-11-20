"""SLAM 결과 정리: 출력 bag 의 Odometry 궤적 · Go2 odom 과 비교 · 지도 PCD 위에서 본 그림.
쓰는 법: python -I analyze_run.py <run 폴더> <원본 bag 폴더> <odom 토픽 이름 (출력 bag)> [map.pcd]
결과: <run>/traj.csv · result.json · topview.png
"""
import sys, json, os, numpy as np
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
ts = get_typestore(Stores.ROS2_HUMBLE)
run, src, topic = sys.argv[1], sys.argv[2], sys.argv[3]
pcd = sys.argv[4] if len(sys.argv) > 4 else os.path.join(run, 'map.pcd')

def read_odom(bag, topic, step=1):
    T, P = [], []
    with AnyReader([Path(bag)], default_typestore=ts) as r:
        c = [c for c in r.connections if c.topic == topic]
        for k, (cc, t, raw) in enumerate(r.messages(connections=c)):
            if k % step: continue
            m = r.deserialize(raw, cc.msgtype); p = m.pose.pose.position
            T.append(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9); P.append((p.x, p.y, p.z))
    return np.array(T), np.array(P)

T, P = read_odom(os.path.join(run, 'out'), topic, step=1)
o = np.argsort(T); T, P = T[o], P[o]
_, keep = np.unique(np.floor(T / 0.02), return_index=True); T, P = T[keep], P[keep]   # 50 Hz 칸마다 첫 값
Tg, Pg = read_odom(src, '/utlidar/robot_odom', step=3)
def plen(P): return float(np.sum(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1)))
res = {'slam_samples': int(len(T)), 'slam_duration_s': round(float(T[-1] - T[0]), 1),
       'slam_start': np.round(P[0], 3).tolist(), 'slam_end': np.round(P[-1], 3).tolist(),
       'slam_start_end_xy_m': round(float(np.linalg.norm(P[-1, :2] - P[0, :2])), 3),
       'slam_start_end_z_m': round(float(P[-1, 2] - P[0, 2]), 3),
       'slam_path_len_m': round(plen(P), 2)}
w = (Tg >= T[0]) & (Tg <= T[-1])
if w.sum() > 2:
    G = Pg[w]
    res.update({'go2odom_start_end_xy_m': round(float(np.linalg.norm(G[-1, :2] - G[0, :2])), 3),
                'go2odom_start_end_z_m': round(float(G[-1, 2] - G[0, 2]), 3),
                'go2odom_path_len_m': round(plen(G), 2)})
np.savetxt(os.path.join(run, 'traj.csv'), np.c_[T, P], delimiter=',', header='t,x,y,z', fmt='%.4f')

M = None
if os.path.exists(pcd):
    with open(pcd, 'rb') as f:
        hdr = {}
        while True:
            line = f.readline().decode().strip(); k, *v = line.split(); hdr[k] = v
            if k == 'DATA': break
        names, sizes, types, counts = hdr['FIELDS'], list(map(int, hdr['SIZE'])), hdr['TYPE'], list(map(int, hdr.get('COUNT', ['1'] * len(hdr['FIELDS']))))
        n = int(hdr['POINTS'][0])
        if hdr['DATA'][0] != 'binary': raise SystemExit('pcd not binary')
        dt = np.dtype([(nm if nm != '_' else f'pad{i}', {'F': 'f', 'U': 'u', 'I': 'i'}[tp] + str(sz), (c,) if c > 1 else ()) for i, (nm, sz, tp, c) in enumerate(zip(names, sizes, types, counts))])
        a = np.frombuffer(f.read(n * dt.itemsize), dtype=dt, count=n)
        M = np.stack([a['x'], a['y'], a['z']], 1).astype(np.float64); M = M[np.isfinite(M).all(1)]
    res['map_points'] = int(len(M))

import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(9, 9), dpi=110)
if M is not None:
    z0 = np.percentile(M[:, 2], 2)
    s = M[::max(1, len(M) // 400000)]
    sc = ax.scatter(s[:, 0], s[:, 1], c=np.clip(s[:, 2] - z0, 0, 2), s=0.2, cmap='viridis')
    fig.colorbar(sc, ax=ax, fraction=0.046, label='height above floor (m)')
ax.plot(P[:, 0], P[:, 1], 'r-', lw=1.5, label='SLAM path')
ax.plot(P[0, 0], P[0, 1], 'go', ms=8, label='start'); ax.plot(P[-1, 0], P[-1, 1], 'kx', ms=10, mew=2, label='end')
ax.set_aspect('equal'); ax.legend(loc='upper right'); ax.set_xlabel('x (m)'); ax.set_ylabel('y (m)')
ax.set_title(os.path.basename(run.rstrip('/')) + f"  start-end {res['slam_start_end_xy_m']} m")
fig.tight_layout(); fig.savefig(os.path.join(run, 'topview.png'))
json.dump(res, open(os.path.join(run, 'result.json'), 'w'), indent=1)
print(json.dumps(res))
