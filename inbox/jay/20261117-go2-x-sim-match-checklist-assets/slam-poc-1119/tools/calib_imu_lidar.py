"""Go2 /utlidar/imu 틀과 /utlidar/cloud (utlidar_lidar) 틀 사이 회전 R_imu_lidar 를 녹화로 추정한다.
1) 선 자세 가만히 구간: IMU 중력 (위) 과 라이다 틀 바닥 법선을 맞춘다 (roll · pitch).
2) 앞으로 걷는 구간: 라이다 스캔 두 묶음 사이 ICP 이동 방향 (라이다 틀) 을 Go2 odom 이동 방향 (몸 틀 · IMU 틀과 거의 같다고 둠) 과 맞춘다 (yaw).
쓰는 법: python -I calib_imu_lidar.py <bag 폴더>
"""
import sys, sqlite3, numpy as np
from rosbags.typesys import Stores, get_typestore
ts = get_typestore(Stores.ROS2_HUMBLE)
db = sqlite3.connect(f'file:{sys.argv[1]}/bag_0.db3?mode=ro', uri=True)
t0 = db.execute('select min(timestamp) from messages').fetchone()[0]
tid = {r[1]: r[0] for r in db.execute('select id,name from topics')}
def rows(topic, a, b): return db.execute('select data from messages where topic_id=? and timestamp between ? and ? order by timestamp', (tid[topic], t0 + a * 1e9, t0 + b * 1e9))
def cloud(a, b):
    P = []
    for d, in rows('/utlidar/cloud', a, b):
        m = ts.deserialize_cdr(d, 'sensor_msgs/msg/PointCloud2')
        x = np.frombuffer(bytes(m.data), dtype=np.dtype({'names': ['x', 'y', 'z'], 'formats': ['<f4'] * 3, 'offsets': [0, 4, 8], 'itemsize': m.point_step}))
        P.append(np.stack([x['x'], x['y'], x['z']], 1))
    P = np.concatenate(P).astype(float); P = P[np.isfinite(P).all(1)]; r = np.linalg.norm(P, axis=1)
    return P[(r > 0.6) & (r < 6)]
def rot_a2b(a, b):
    v = np.cross(a, b); s = np.linalg.norm(v); c = a @ b
    if s < 1e-9: return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]); return np.eye(3) + K + K @ K * ((1 - c) / s ** 2)
# 1) roll · pitch
A = np.array([(m.linear_acceleration.x, m.linear_acceleration.y, m.linear_acceleration.z) for m in (ts.deserialize_cdr(d, 'sensor_msgs/msg/Imu') for d, in rows('/utlidar/imu', 70, 95))])
up = A.mean(0) / np.linalg.norm(A.mean(0))
P = cloud(70, 95); rng = np.random.default_rng(2); best = None
for _ in range(3000):
    s = P[rng.choice(len(P), 3, replace=False)]; n = np.cross(s[1] - s[0], s[2] - s[0]); nn = np.linalg.norm(n)
    if nn < 1e-9: continue
    n /= nn; d = -n @ s[0]
    if d < 0: n, d = -n, -d
    c = (np.abs(P @ n + d) < 0.02).sum()
    if best is None or c > best[0]: best = (c, n, d)
_, nup, h = best
R1 = rot_a2b(nup, up)            # 라이다 위 → IMU 위
# 2) yaw: 걷는 구간 두 묶음 ICP
V = 0.05
def make_index(B):
    k = np.floor(B / V).astype(np.int64); hsh = (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)
    o = np.argsort(hsh); return hsh[o], B[o]
def nn(X, hs, Bs):
    best = np.full(len(X), np.inf); idx = np.full(len(X), -1); k = np.floor(X / V).astype(np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                kk = k + [dx, dy, dz]; hh = (kk[:, 0] * 73856093) ^ (kk[:, 1] * 19349663) ^ (kk[:, 2] * 83492791)
                lo = np.searchsorted(hs, hh, 'left'); hi = np.searchsorted(hs, hh, 'right')
                for j in range(4):
                    sel = lo + j < hi; ii = (lo + j)[sel]; dd = np.linalg.norm(Bs[ii] - X[sel], axis=1); bt = dd < best[sel]
                    s2 = np.where(sel)[0][bt]; best[s2] = dd[bt]; idx[s2] = ii[bt]
    return best, idx
def icp(Psrc, Pdst):
    hs, Bs = make_index(Pdst); R = np.eye(3); t = np.zeros(3)
    S = Psrc[rng.choice(len(Psrc), min(30000, len(Psrc)), replace=False)]
    for k in range(50):
        X = S @ R.T + t; dist, idx = nn(X, hs, Bs); s = (idx >= 0) & (dist < (0.2 if k < 20 else 0.06))
        a, b = S[s], Bs[idx[s]]; ma, mb = a.mean(0), b.mean(0)
        U, _, Vt = np.linalg.svd((a - ma).T @ (b - mb)); D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
        R = Vt.T @ D @ U.T; t = mb - R @ ma
    return R, t, s.mean()
odo = []
for d, in rows('/utlidar/robot_odom', 0, 150):
    m = ts.deserialize_cdr(d, 'nav_msgs/msg/Odometry'); p = m.pose.pose.position; q = m.pose.pose.orientation
    odo.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
odo = np.array(odo); stamp0 = odo[0, 0]
def q2R(x, y, z, w): return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
out = []
for a in (114.0, 117.0, 120.0, 123.0):
    b = a + 1.5
    C1 = cloud(a, a + 0.4); C2 = cloud(b, b + 0.4)
    R, t, fr = icp(C2, C1)           # C2 점을 C1 틀로: t = 라이다가 a→b 사이 움직인 것 (라이다 틀 · a 시점)
    i1 = np.argmin(np.abs(odo[:, 0] - (odo[0, 0] + a + 0.2))); i2 = np.argmin(np.abs(odo[:, 0] - (odo[0, 0] + b + 0.2)))
    Rb = q2R(*odo[i1, 4:]); dbase = Rb.T @ (odo[i2, 1:4] - odo[i1, 1:4])   # 몸 틀 이동
    out.append((a, t, dbase, fr))
    print('t', a, 'lidar move', np.round(t, 3), '|', round(np.linalg.norm(t), 3), ' base move', np.round(dbase, 3), '|', round(np.linalg.norm(dbase), 3), 'inl', round(fr, 2))
# yaw: R1 로 라이다 이동을 IMU 틀로 옮긴 뒤 수평 성분 각을 몸 이동 수평 각과 맞춤
ang = []
for a, t, dbase, fr in out:
    ti = R1 @ t
    if np.linalg.norm(dbase[:2]) > 0.1 and np.linalg.norm(ti[:2]) > 0.1:
        ang.append(np.arctan2(dbase[1], dbase[0]) - np.arctan2(ti[1], ti[0]))
yaw = float(np.angle(np.mean(np.exp(1j * np.array(ang))))) if ang else 0.0
c, s = np.cos(yaw), np.sin(yaw); Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
up_axis = up; K = np.array([[0, -up_axis[2], up_axis[1]], [up_axis[2], 0, -up_axis[0]], [-up_axis[1], up_axis[0], 0]])
Rup = np.eye(3) + np.sin(yaw) * K + (1 - np.cos(yaw)) * K @ K     # IMU 위 축 둘레 yaw
R = Rup @ R1
from math import atan2, asin, degrees
print('yaw samples deg', np.round(np.degrees(ang), 1), 'mean', round(degrees(yaw), 1))
print('R_imu_lidar=\n', np.round(R, 5)); print('rpy deg', round(degrees(atan2(R[2, 1], R[2, 2])), 2), round(degrees(asin(-R[2, 0])), 2), round(degrees(atan2(R[1, 0], R[0, 0])), 2))
print('lidar height above floor (standing, mat)', round(h, 3))
np.save('/home/jay/data/slam_poc/tools/R_imu_lidar.npy', R)
