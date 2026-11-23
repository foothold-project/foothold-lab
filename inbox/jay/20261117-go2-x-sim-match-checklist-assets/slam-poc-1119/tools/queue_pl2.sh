#!/bin/bash
# Point-LIO 05:20 변형: 라이다만 · IMU-라이다 회전 두 후보 (x 앞 · x 뒤) × 이동 두 후보 (L2 기본 · 몸 IMU 기준)
B=/home/jay/data/slam_poc; BAG=/home/jay/data/go2x_raw/jetson_go2_diag/records/20261119-0520-room-walk-full/bag
while pgrep -f 'run_pointlio[.]sh' >/dev/null; do sleep 5; done
for v in v3_noimu A_xfwd_Tl2 A_xfwd_Tbody B_xback_Tl2 B_xback_Tbody; do
  $B/tools/run_pointlio.sh 0520_$v $BAG /utlidar/cloud /utlidar/imu $B/tools/pl_$v.yaml 1.0
done
echo QUEUE_DONE
