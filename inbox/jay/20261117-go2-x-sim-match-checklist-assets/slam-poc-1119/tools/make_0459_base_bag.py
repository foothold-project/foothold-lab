"""04:59 녹화: /utlidar/cloud_deskewed (odom 틀) 를 그 순간 robot_odom 자세의 역으로 base_link 틀 점으로 되돌려
새 bag (/slam/points · base_link · L2 와 같은 배치 x y z intensity ring=1 time=0) 과 /utlidar/imu 사본을 쓴다. SLAM 입력용.
주의: 점을 되돌리는 데 Go2 odom 을 쓰므로 한 장 안의 점 배치는 Go2 의 deskew 결과를 따른다 (장끼리 이어 붙이는 것은 SLAM 몫).
쓰는 법: python -I make_0459_base_bag.py <입력 bag 폴더> <출력 bag 폴더>
"""
import sys, numpy as np
from pathlib import Path
from rosbags.highlevel import AnyReader
from rosbags.rosbag2 import Writer
from rosbags.typesys import Stores, get_typestore
ts = get_typestore(Stores.ROS2_HUMBLE)
PC2 = ts.types['sensor_msgs/msg/PointCloud2']; PF = ts.types['sensor_msgs/msg/PointField']
src, dst = sys.argv[1], sys.argv[2]

def q2R(x, y, z, w):
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

odom_t, odom_T = [], []
with AnyReader([Path(src)], default_typestore=ts) as r:
    c = [c for c in r.connections if c.topic == '/utlidar/robot_odom']
    for cc, t, raw in r.messages(connections=c):
        m = r.deserialize(raw, cc.msgtype); p = m.pose.pose.position; q = m.pose.pose.orientation
        st = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        odom_t.append(st); odom_T.append((q2R(q.x, q.y, q.z, q.w), np.array([p.x, p.y, p.z])))
odom_t = np.array(odom_t)
fields = [PF(name='x', offset=0, datatype=7, count=1), PF(name='y', offset=4, datatype=7, count=1),
          PF(name='z', offset=8, datatype=7, count=1), PF(name='intensity', offset=16, datatype=7, count=1),
          PF(name='ring', offset=20, datatype=4, count=1), PF(name='time', offset=24, datatype=7, count=1)]
# L2 /utlidar/cloud 와 같은 배치 (point_step 32 · ring=1 · time=0: 이미 deskew 된 점)
n_out = 0; max_dt = 0
with AnyReader([Path(src)], default_typestore=ts) as r, Writer(Path(dst), version=8) as w:
    cp = w.add_connection('/slam/points', 'sensor_msgs/msg/PointCloud2', typestore=ts)
    ci = w.add_connection('/utlidar/imu', 'sensor_msgs/msg/Imu', typestore=ts)
    conns = [c for c in r.connections if c.topic in ('/utlidar/cloud_deskewed', '/utlidar/imu')]
    for cc, t, raw in r.messages(connections=conns):
        if cc.topic == '/utlidar/imu':
            w.write(ci, t, raw); continue
        m = r.deserialize(raw, cc.msgtype)
        st = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        i = int(np.clip(np.searchsorted(odom_t, st), 1, len(odom_t) - 1))
        if abs(odom_t[i-1] - st) < abs(odom_t[i] - st): i -= 1
        max_dt = max(max_dt, abs(odom_t[i] - st))
        R, p = odom_T[i]
        a = np.frombuffer(bytes(m.data), dtype=np.dtype({'names': ['x', 'y', 'z', 'i'], 'formats': ['<f4'] * 4,
                          'offsets': [0, 4, 8, 16], 'itemsize': m.point_step}), count=m.width * m.height)
        P = np.stack([a['x'], a['y'], a['z']], 1).astype(np.float64)
        ok = np.isfinite(P).all(1); P = P[ok]
        B = (P - p) @ R            # odom → base_link: R^T (P - p)
        out = np.zeros(len(B), dtype=np.dtype({'names': ['x', 'y', 'z', 'intensity', 'ring', 'time'],
                       'formats': ['<f4', '<f4', '<f4', '<f4', '<u2', '<f4'], 'offsets': [0, 4, 8, 16, 20, 24], 'itemsize': 32}))
        out['x'], out['y'], out['z'] = B.T; out['intensity'] = a['i'][ok]; out['ring'] = 1
        hdr = m.header.__class__(stamp=m.header.stamp, frame_id='base_link')
        msg = PC2(header=hdr, height=1, width=len(out), fields=fields, is_bigendian=False, point_step=32,
                  row_step=32 * len(out), data=np.frombuffer(out.tobytes(), np.uint8), is_dense=True)
        w.write(cp, t, ts.serialize_cdr(msg, 'sensor_msgs/msg/PointCloud2')); n_out += 1
print('clouds', n_out, 'max |odom - cloud stamp| s', round(max_dt, 4))
