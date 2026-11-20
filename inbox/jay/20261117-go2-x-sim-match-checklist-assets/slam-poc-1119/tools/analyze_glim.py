"""GLIM dump 정리: traj_lidar.txt (TUM) 궤적 · Go2 odom 비교 · 부분 지도 점을 모아 위에서 본 그림.
쓰는 법: python -I analyze_glim.py <run 폴더> <원본 bag 폴더 (robot_odom 비교용)>
"""
import sys, os, json, glob, numpy as np
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
ts = get_typestore(Stores.ROS2_HUMBLE)
run, src = sys.argv[1], sys.argv[2]; D = os.path.join(run, 'dump')
tr = np.loadtxt(os.path.join(D, 'traj_lidar.txt')); T, P = tr[:, 0], tr[:, 1:4]
def plen(P): return float(np.sum(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1)))
res = {'slam_samples': int(len(T)), 'slam_duration_s': round(float(T[-1] - T[0]), 1), 'slam_start': np.round(P[0], 3).tolist(), 'slam_end': np.round(P[-1], 3).tolist(),
       'slam_start_end_xy_m': round(float(np.linalg.norm(P[-1, :2] - P[0, :2])), 3), 'slam_start_end_z_m': round(float(P[-1, 2] - P[0, 2]), 3), 'slam_path_len_m': round(plen(P), 2)}
Tg, Pg = [], []
with AnyReader([Path(src)], default_typestore=ts) as r:
    c = [c for c in r.connections if c.topic == '/utlidar/robot_odom']
    for k, (cc, t, raw) in enumerate(r.messages(connections=c)):
        if k % 3: continue
        m = r.deserialize(raw, cc.msgtype); p = m.pose.pose.position
        Tg.append(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9); Pg.append((p.x, p.y, p.z))
Tg, Pg = np.array(Tg), np.array(Pg); w = (Tg >= T[0]) & (Tg <= T[-1])
if w.sum() > 2:
    G = Pg[w]; res.update({'go2odom_start_end_xy_m': round(float(np.linalg.norm(G[-1, :2] - G[0, :2])), 3), 'go2odom_path_len_m': round(plen(G), 2)})
M = []
for sd in sorted(glob.glob(os.path.join(D, '[0-9]' * 6))):
    txt = open(os.path.join(sd, 'data.txt')).read().split('\n')
    i = txt.index('T_world_origin: '); Tw = np.array([list(map(float, txt[i + 1 + k].split())) for k in range(4)])
    pts = np.fromfile(os.path.join(sd, 'points_compact.bin'), dtype='<f4').reshape(-1, 3).astype(float)
    M.append(pts @ Tw[:3, :3].T + Tw[:3, 3])
M = np.concatenate(M); res['map_points'] = int(len(M)); res['submaps'] = len(glob.glob(os.path.join(D, '[0-9]' * 6)))
np.savetxt(os.path.join(run, 'traj.csv'), np.c_[T, P], delimiter=',', header='t,x,y,z', fmt='%.4f')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(9, 9), dpi=110); z0 = np.percentile(M[:, 2], 2)
sc = ax.scatter(M[:, 0], M[:, 1], c=np.clip(M[:, 2] - z0, 0, 2), s=0.3, cmap='viridis'); fig.colorbar(sc, ax=ax, fraction=0.046, label='height above lowest 2% (m)')
ax.plot(P[:, 0], P[:, 1], 'r-', lw=1, label='GLIM path'); ax.plot(P[0, 0], P[0, 1], 'go', ms=8, label='start'); ax.plot(P[-1, 0], P[-1, 1], 'kx', ms=10, mew=2, label='end')
ax.set_aspect('equal'); ax.legend(loc='upper right'); ax.set_title(os.path.basename(run.rstrip('/')) + f"  start-end {res['slam_start_end_xy_m']} m")
fig.tight_layout(); fig.savefig(os.path.join(run, 'topview.png'))
json.dump(res, open(os.path.join(run, 'result.json'), 'w'), indent=1); print(json.dumps(res))
