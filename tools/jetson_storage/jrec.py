#!/usr/bin/env python3
"""Go2 X Jetson recording with a disk space gate (owner 11/19 16:35).

Runs on the Jetson. Refuses to start below START_MIN_GB free, stops the bag
with SIGINT (the bag closes cleanly) when free space drops below STOP_MIN_GB,
and writes SHA256SUMS when it ends so jetson_sync.py can copy and verify it.

  python3 jrec.py full room-walk --seconds 330
  python3 jrec.py camera cam-angle            # capped at 30 s
  python3 jrec.py map lidar-only --seconds 600 --zstd
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.expanduser('~/go2_diag/records')
START_MIN_GB = 20
STOP_MIN_GB = 5
RATE_MB_S = 22.5   # measured 11/19 05:20 full profile, 7.43 GB in 330 s, no compression
SUMS = 'SHA256SUMS'
MARK = '.backup.json'

CAM = ['/camera/camera/depth/image_rect_raw', '/camera/camera/depth/camera_info',
       '/camera/camera/color/image_raw/compressed', '/camera/camera/color/camera_info',
       '/camera/camera/extrinsics/depth_to_color']
LIDAR = ['/utlidar/cloud', '/utlidar/cloud_deskewed', '/utlidar/robot_odom', '/utlidar/imu', '/sportmodestate']
TF = ['/tf', '/tf_static']
PROFILES = {'map': (LIDAR + TF, None), 'camera': (CAM + TF, 30), 'full': (CAM + LIDAR + TF, None)}
ROS = 'source /opt/ros/humble/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; exec ros2 bag record "$@"'


def free_gb(path):
    return shutil.disk_usage(path).free / 1e9


def start_refusal(free, need=START_MIN_GB):
    if free < need:
        return 'refused: %.1f GB free, needs %d GB before recording' % (free, need)
    return None


def write_sums(folder):
    """sha256 of every file under folder except SHA256SUMS and the backup mark, sorted."""
    lines = []
    for base, dirs, files in os.walk(folder):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            rel = './' + os.path.relpath(path, folder)
            if rel in ('./' + SUMS, './' + MARK) or rel.endswith('.tmp'):
                continue
            h = hashlib.sha256()
            with open(path, 'rb') as f:
                for block in iter(lambda: f.read(1 << 20), b''):
                    h.update(block)
            lines.append('%s  %s\n' % (h.hexdigest(), rel))
    tmp = os.path.join(folder, SUMS + '.tmp')
    with open(tmp, 'w') as f:
        f.writelines(sorted(lines, key=lambda s: s[66:]))
    os.replace(tmp, os.path.join(folder, SUMS))
    return len(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('profile', choices=sorted(PROFILES))
    ap.add_argument('name')
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--zstd', action='store_true', help='rosbag2 --compression-mode file --compression-format zstd')
    ap.add_argument('--root', default=ROOT)
    a = ap.parse_args(argv)
    topics, cap = PROFILES[a.profile]
    seconds = min(a.seconds, cap) if cap else a.seconds
    os.makedirs(a.root, exist_ok=True)
    free0 = free_gb(a.root)
    refusal = start_refusal(free0)
    if refusal:
        print(refusal)
        return 2
    print('free %.1f GB · about %d min of full-profile recording before the %d GB stop'
          % (free0, (free0 - STOP_MIN_GB) * 1000 / RATE_MB_S / 60, STOP_MIN_GB))
    stamp = '' if re.match(r'^\d{8}-\d{4}-', a.name) else dt.datetime.now().strftime('%Y%m%d-%H%M') + '-'
    out = os.path.join(a.root, stamp + a.name)   # a name that already starts with YYYYMMDD-HHMM- is used as is
    os.makedirs(out, exist_ok=True)
    if os.path.exists(os.path.join(out, 'bag')):
        print('refused: %s/bag already exists' % out)
        return 2
    args = ['-o', os.path.join(out, 'bag')]
    if a.zstd:
        args += ['--compression-mode', 'file', '--compression-format', 'zstd']
    log = open(os.path.join(out, 'bag.log'), 'w')
    p = subprocess.Popen(['bash', '-c', ROS, 'ros2'] + args + topics, stdout=log, stderr=subprocess.STDOUT,
                         start_new_session=True)
    t0, stopped, low = time.time(), None, free0
    while p.poll() is None:
        free = free_gb(a.root)
        low = min(low, free)
        if stopped is None and free < STOP_MIN_GB:
            stopped = 'low_space'
        elif stopped is None and time.time() - t0 >= seconds:
            stopped = 'time'
        if stopped:
            p.send_signal(signal.SIGINT)
            try:
                p.wait(60)
            except subprocess.TimeoutExpired:
                p.terminate()
                p.wait(30)
            break
        time.sleep(2)
    rc = p.wait()
    log.close()
    record = dict(profile=a.profile, topics=topics, seconds_asked=seconds, seconds_ran=round(time.time() - t0, 1),
                  stopped=stopped or 'exited', rc=rc, zstd=a.zstd, free_start_gb=round(free0, 1),
                  free_low_gb=round(low, 1), free_end_gb=round(free_gb(a.root), 1))
    with open(os.path.join(out, 'record.json'), 'w') as f:
        json.dump(record, f, indent=1)
    n = write_sums(out)
    print(out)
    print(json.dumps(dict(record, files=n)))
    return 3 if stopped == 'low_space' else 0


if __name__ == '__main__':
    sys.exit(main())
