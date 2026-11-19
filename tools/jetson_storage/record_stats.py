"""Per-topic stats of one rosbag2 sqlite recording, body tilt while standing, L2 rate and field of view, odom drift.
Jetson, ROS 2 sourced:  python3 record_stats.py <bag dir> <stand start s> <stand end s> <out json>
"""
import glob
import json
import math
import sqlite3
import sys

import numpy as np
import rosbag2_py
from nav_msgs.msg import Odometry
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2 as pc2

bag, s0, s1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
db = sqlite3.connect(glob.glob(bag + '/*.db3')[0])
rows = db.execute('select t.name, t.type, count(m.id), sum(length(m.data)), min(m.timestamp), max(m.timestamp) '
                  'from topics t left join messages m on m.topic_id = t.id group by t.id').fetchall()
start = min(r[4] for r in rows if r[4]) * 1e-9
end = max(r[5] for r in rows if r[5]) * 1e-9
topics = []
for name, typ, n, size, a, b in sorted(rows):
    span = (b - a) * 1e-9 if n and n > 1 else 0
    topics.append(dict(name=name, type=typ, messages=n, mb=round((size or 0) / 1e6, 1),
                       hz=round((n - 1) / span, 2) if span else 0, avg_kb=round((size or 0) / max(n, 1) / 1e3, 1)))

r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='sqlite3'), rosbag2_py.ConverterOptions('cdr', 'cdr'))
r.set_filter(rosbag2_py.StorageFilter(topics=['/utlidar/robot_odom', '/utlidar/cloud']))
odom, tilt, pts, k, az, el = [], [], 0, 0, [], []
while r.has_next():
    topic, data, t = r.read_next()
    rel = t * 1e-9 - start
    if topic == '/utlidar/robot_odom':
        m = deserialize_message(data, Odometry)
        p, q = m.pose.pose.position, m.pose.pose.orientation
        odom.append((rel, p.x, p.y, p.z))
        if s0 <= rel <= s1:
            roll = math.atan2(2 * (q.w * q.x + q.y * q.z), 1 - 2 * (q.x * q.x + q.y * q.y))
            pitch = math.asin(max(-1, min(1, 2 * (q.w * q.y - q.z * q.x))))
            tilt.append((math.degrees(roll), math.degrees(pitch), p.z))
    else:
        m = deserialize_message(data, PointCloud2)
        pts += m.width * m.height
        k += 1
        if k % 50 == 0:
            xyz = np.array([(x, y, z) for x, y, z in pc2.read_points(m, field_names=('x', 'y', 'z'), skip_nans=True)])
            if len(xyz):
                az.append(np.degrees(np.arctan2(xyz[:, 1], xyz[:, 0])))
                el.append(np.degrees(np.arctan2(xyz[:, 2], np.hypot(xyz[:, 0], xyz[:, 1]))))
O = np.array(odom)
T = np.array(tilt) if tilt else np.zeros((0, 3))
first, last = O[0], O[-1]
path = float(np.sum(np.hypot(np.diff(O[:, 1]), np.diff(O[:, 2])))) if len(O) > 1 else 0
res = dict(duration_s=round(end - start, 1), topics=topics,
           stand_window_s=[s0, s1],
           body_while_standing=dict(roll_deg=round(float(np.median(T[:, 0])), 2) if len(T) else None,
                                    pitch_deg=round(float(np.median(T[:, 1])), 2) if len(T) else None,
                                    odom_z_m=round(float(np.median(T[:, 2])), 3) if len(T) else None),
           l2=dict(points_per_s=round(pts / (end - start)), frames=k,
                   azimuth_deg=[round(float(np.percentile(np.concatenate(az), q)), 1) for q in (1, 99)] if az else None,
                   elevation_deg=[round(float(np.percentile(np.concatenate(el), q)), 1) for q in (1, 99)] if el else None),
           odom=dict(path_m=round(path, 2), start_xy=[round(first[1], 3), round(first[2], 3)],
                     end_xy=[round(last[1], 3), round(last[2], 3)],
                     end_minus_start_m=round(float(math.hypot(last[1] - first[1], last[2] - first[2])), 3)))
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps(res))
