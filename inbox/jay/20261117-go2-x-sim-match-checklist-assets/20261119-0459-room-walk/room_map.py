"""방 걷기 녹화 (rosbag2 sqlite) 에서 위에서 본 지도를 만든다.
/utlidar/cloud_deskewed 는 이미 odom 틀이라 점을 그대로 쌓는다. /utlidar/robot_odom 은 걸은 길.
쓰는 법 (Jetson · ROS 2 환경): python3 room_map.py <bag 폴더> <출력 폴더>
"""
import sys, os, json
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Odometry
from sensor_msgs_py import point_cloud2 as pc2

bag, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
reader = rosbag2_py.SequentialReader()
reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3"),
            rosbag2_py.ConverterOptions("cdr", "cdr"))
reader.set_filter(rosbag2_py.StorageFilter(topics=["/utlidar/cloud_deskewed", "/utlidar/robot_odom"]))
pts, path, frames, n_odom = [], [], 0, 0
last_xy = None
while reader.has_next():
    topic, data, t = reader.read_next()
    if topic == "/utlidar/cloud_deskewed":
        frames += 1
        msg = deserialize_message(data, PointCloud2)
        a = pc2.read_points_numpy(msg, field_names=("x", "y", "z"), skip_nans=True)
        if a.size and last_xy is not None:
            # 로봇 몸 · 다리에 맞은 점을 뺀다 (몸 중심에서 수평 0.6 m 안)
            d = np.hypot(a[:, 0] - last_xy[0], a[:, 1] - last_xy[1])
            pts.append(a[d > 0.6][:: 2].astype(np.float32))
    else:
        n_odom += 1
        if n_odom % 5 == 0:
            m = deserialize_message(data, Odometry)
            p = m.pose.pose.position
            last_xy = (p.x, p.y)
            if n_odom % 15 == 0:
                path.append((t * 1e-9, p.x, p.y, p.z))
P = np.concatenate(pts) if pts else np.zeros((0, 3), np.float32)
path = np.array(path)
# 바닥 높이: 걸은 길 몸 높이 - 약 0.3 m 대신 점 높이 분포의 아래쪽 2 % 로 잡는다
floor = float(np.percentile(P[:, 2], 2)) if len(P) else 0.0
z = P[:, 2] - floor
res = 0.05
# 창 밖 · 반사로 멀리 튄 점을 빼고 걸은 길 둘레 5 m 만 그린다
xmin, xmax = path[:, 1].min() - 5, path[:, 1].max() + 5
ymin, ymax = path[:, 2].min() - 5, path[:, 2].max() + 5
keep = (P[:, 0] > xmin) & (P[:, 0] < xmax) & (P[:, 1] > ymin) & (P[:, 1] < ymax)
P = P[keep]; z = P[:, 2] - floor
W, H = int((xmax - xmin) / res) + 1, int((ymax - ymin) / res) + 1
ix = ((P[:, 0] - xmin) / res).astype(int); iy = ((P[:, 1] - ymin) / res).astype(int)
# 칸마다 점 수 · 가장 높은 점
cnt = np.zeros((H, W), np.int32); np.add.at(cnt, (iy, ix), 1)
top = np.full((H, W), np.nan, np.float32)
order = np.argsort(z)
top[iy[order], ix[order]] = z[order]
# 장애물 칸: 바닥에서 0.15~1.8 m 사이 점이 3 개 넘음
obs_mask = (z > 0.15) & (z < 1.8)
occ = np.zeros((H, W), np.int32); np.add.at(occ, (iy[obs_mask], ix[obs_mask]), 1)
floor_mask = (z <= 0.08)
flr = np.zeros((H, W), np.int32); np.add.at(flr, (iy[floor_mask], ix[floor_mask]), 1)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ext = [xmin, xmax, ymin, ymax]
fig, axs = plt.subplots(1, 2, figsize=(16, 8), dpi=110)
im = axs[0].imshow(np.where(cnt > 0, top, np.nan), origin="lower", extent=ext, cmap="viridis", vmin=0, vmax=2.0)
axs[0].set_title("Top view: highest point per 5 cm cell (m above floor)")
fig.colorbar(im, ax=axs[0], fraction=0.046)
grid = np.full((H, W, 3), 0.55)          # 모름 = 회색
grid[flr > 5] = (1.0, 1.0, 1.0)          # 바닥 = 흰색
grid[(occ > 20) & (occ > 0.3 * cnt)] = (0.1, 0.1, 0.1)   # 장애물 = 검정 (그 칸 점의 30 % 넘게가 0.15~1.8 m)
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
        "obstacle_cells": int(((occ > 20) & (occ > 0.3 * cnt)).sum()), "floor_cells": int((flr > 5).sum()), "path_s": round(dur, 1), "path_len_m": round(walk, 2)}
json.dump(info, open(os.path.join(out, "room_map_info.json"), "w"), indent=1)
print(json.dumps(info))
