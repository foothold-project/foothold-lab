#!/bin/bash
# GLIM (glim_rosbag · 기록을 최대 속도로 후처리). 쓰는 법: run_glim.sh <이름> <bag 폴더> <config 폴더>
NAME=$1; BAG=$2; CFG=$3
B=/home/jay/data/slam_poc; OUT=$B/runs/glim_$NAME; rm -rf $OUT; mkdir -p $OUT
source /home/jay/miniforge3/etc/profile.d/conda.sh; conda activate $B/env
export LD_LIBRARY_PATH=$B/local/lib:$LD_LIBRARY_PATH
source $B/ws_glim/install/setup.bash
export ROS_DOMAIN_ID=78 ROS_LOCALHOST_ONLY=1
( while true; do nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null | awk -v t=$(date +%s) '{print t,$0}'; sleep 1; done ) > $OUT/gpu_apps.txt &
GPU=$!
T0=$(date +%s.%N)
/usr/bin/time -v ros2 run glim_ros glim_rosbag $BAG --ros-args -p config_path:=$CFG -p dump_path:=$OUT/dump -p auto_quit:=true > $OUT/glim.log 2> $OUT/time.txt
RC=$?
T1=$(date +%s.%N)
kill $GPU
echo "rc $RC" > $OUT/summary.txt
echo "wall_s $(echo "$T1 - $T0" | bc)" >> $OUT/summary.txt
grep -E 'User time|System time|Maximum resident|Percent of CPU' $OUT/time.txt >> $OUT/summary.txt
cat $OUT/summary.txt
