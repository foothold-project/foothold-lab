"""방 걷기 녹화 (rosbag2 sqlite) 에서 위에서 본 지도를 만든다. ROS 2 없이 rosbags 로 읽는다.
04:59 판 room_map.py (Jetson ROS 2 환경) 와 같은 방법 · 같은 수치를 rosbags 로 옮긴 것.
/utlidar/cloud_deskewed 는 이미 odom 틀이라 점을 그대로 쌓는다. /utlidar/robot_odom 은 걸은 길.
쓰는 법: <rosbags venv>/bin/python -I room_map_rosbags.py <bag 폴더> <출력 폴더> [시작 초] [끝 초]
덧붙임: 5 cm 칸마다 점 하나 (칸 평균) 를 room_points_5cm.npy 로 남긴다 (3D 보기용 · 원래 z).
"""
import sys, os, json
import numpy as np
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from pathlib import Path

bag, out = sys.argv[1], sys.argv[2]
t0 = float(sys.argv[3]) if len(sys.argv) > 3 else None
t1 = float(sys.argv[4]) if len(sys.argv) > 4 else None
os.makedirs(out, exist_ok=True)

DT = {1: "i1", 2: "u1", 3: "i2", 4: "u2", 5: "i4", 6: "u4", 7: "f4", 8: "f8"}


def xyz(msg):
    f = {x.name: x for x in msg.fields}
    dt = np.dtype({"names": ["x", "y", "z"], "formats": [DT[f[k].datatype] for k in "xyz"],
                   "offsets": [f[k].offset for k in "xyz"], "itemsize": msg.point_step})
    n = msg.width * msg.height
    a = np.frombuffer(bytes(msg.data[: n * msg.point_step]), dtype=dt)
    a = np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float32)
    return a[np.isfinite(a).all(1)]


pts, path, frames, n_odom = [], [], 0, 0
last_xy = None
with AnyReader([Path(bag)], default_typestore=get_typestore(Stores.ROS2_HUMBLE)) as r:
    conns = [c for c in r.connections if c.topic in ("/utlidar/cloud_deskewed", "/utlidar/robot_odom")]
    tstart = r.start_time
    for c, t, raw in r.messages(connections=conns):
        rel = (t - tstart) * 1e-9
        if (t0 is not None and rel < t0) or (t1 is not None and rel > t1):
            continue
        if c.topic == "/utlidar/cloud_deskewed":
            frames += 1
            a = xyz(r.deserialize(raw, c.msgtype))
            if a.size and last_xy is not None:
                # 로봇 몸 · 다리에 맞은 점을 뺀다 (몸 중심에서 수평 0.6 m 안)
                d = np.hypot(a[:, 0] - last_xy[0], a[:, 1] - last_xy[1])
                pts.append(a[d > 0.6][::2])
        else:
            n_odom += 1
            if n_odom % 5 == 0:
                p = r.deserialize(raw, c.msgtype).pose.pose.position
                last_xy = (p.x, p.y)
                if n_odom % 15 == 0:
                    path.append((t * 1e-9, p.x, p.y, p.z))
P = np.concatenate(pts) if pts else np.zeros((0, 3), np.float32)
path = np.array(path)
floor = float(np.percentile(P[:, 2], 2)) if len(P) else 0.0
res = 0.05
xmin, xmax = path[:, 1].min() - 5, path[:, 1].max() + 5
ymin, ymax = path[:, 2].min() - 5, path[:, 2].max() + 5
keep = (P[:, 0] > xmin) & (P[:, 0] < xmax) & (P[:, 1] > ymin) & (P[:, 1] < ymax)
P = P[keep]; z = P[:, 2] - floor
W, H = int((xmax - xmin) / res) + 1, int((ymax - ymin) / res) + 1
ix = ((P[:, 0] - xmin) / res).astype(int); iy = ((P[:, 1] - ymin) / res).astype(int)
cnt = np.zeros((H, W), np.int32); np.add.at(cnt, (iy, ix), 1)
top = np.full((H, W), np.nan, np.float32)
order = np.argsort(z)
top[iy[order], ix[order]] = z[order]
obs_mask = (z > 0.15) & (z < 1.8)
occ = np.zeros((H, W), np.int32); np.add.at(occ, (iy[obs_mask], ix[obs_mask]), 1)
floor_mask = (z <= 0.08)
flr = np.zeros((H, W), np.int32); np.add.at(flr, (iy[floor_mask], ix[floor_mask]), 1)

# 5 cm 3D 칸마다 점 하나 (칸 안 점의 평균)
v = np.floor(P / res).astype(np.int64)
_, inv, vc = np.unique(v, axis=0, return_inverse=True, return_counts=True)
inv = inv.ravel()
vox = np.zeros((len(vc), 3), np.float64); np.add.at(vox, inv, P)
vox = (vox / vc[:, None]).astype(np.float32)
np.save(os.path.join(out, "room_points_5cm.npy"), vox)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ext = [xmin, xmax, ymin, ymax]
fig, axs = plt.subplots(1, 2, figsize=(16, 8), dpi=110)
im = axs[0].imshow(np.where(cnt > 0, top, np.nan), origin="lower", extent=ext, cmap="viridis", vmin=0, vmax=2.0)
axs[0].set_title("Top view: highest point per 5 cm cell (m above floor)")
fig.colorbar(im, ax=axs[0], fraction=0.046)
grid = np.full((H, W, 3), 0.55)
grid[flr > 5] = (1.0, 1.0, 1.0)
grid[(occ > 20) & (occ > 0.3 * cnt)] = (0.1, 0.1, 0.1)
axs[1].imshow(grid, origin="lower", extent=ext)
axs[1].set_title("Occupancy: white floor / black obstacle 0.15-1.8 m / grey unknown")
for ax in axs:
    if len(path):
        ax.plot(path[:, 1], path[:, 2], "r-", lw=1.5, label="robot path (odom)")
        ax.plot(path[0, 1], path[0, 2], "go", ms=8, label="start")
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.set_aspect("equal"); ax.legend(loc="upper right")
fig.tight_layout(); fig.savefig(os.path.join(out, "room_topview.png"))
np.savez_compressed(os.path.join(out, "room_grid.npz"), top=top, cnt=cnt, occ=occ, flr=flr,
                    origin=np.array([xmin, ymin]), res=res, floor=floor, path=path)
dur = float(path[-1, 0] - path[0, 0]) if len(path) > 1 else 0.0
walk = float(np.sum(np.linalg.norm(np.diff(path[:, 1:3], axis=0), axis=1))) if len(path) > 1 else 0.0
info = {"cloud_frames": frames, "points_kept": int(len(P)), "floor_z": floor, "extent_m": [round(xmax - xmin, 2), round(ymax - ymin, 2)],
        "obstacle_cells": int(((occ > 20) & (occ > 0.3 * cnt)).sum()), "floor_cells": int((flr > 5).sum()), "path_s": round(dur, 1), "path_len_m": round(walk, 2),
        "voxels_5cm": int(len(vox))}
json.dump(info, open(os.path.join(out, "room_map_info.json"), "w"), indent=1)
print(json.dumps(info))
