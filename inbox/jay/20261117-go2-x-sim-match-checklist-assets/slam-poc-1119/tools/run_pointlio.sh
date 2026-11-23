#!/bin/bash
# Point-LIO (ROS2) 를 기록 재생으로 돌린다. 쓰는 법: run_pointlio.sh <이름> <bag 폴더> <라이다 토픽> <imu 토픽> <params yaml> [재생 배속 · 기본 1.0]
set +u
NAME=$1; BAG=$2; LID=$3; IMU=$4; PAR=$5; RATE=${6:-1.0}
B=/home/jay/data/slam_poc; OUT=$B/runs/pointlio_$NAME; rm -rf $OUT; mkdir -p $OUT
source /home/jay/miniforge3/etc/profile.d/conda.sh; conda activate $B/env
source $B/ws_pl/install/setup.bash
export ROS_DOMAIN_ID=77 ROS_LOCALHOST_ONLY=1
sed -e "s#lid_topic: .*#lid_topic: \"$LID\"#" -e "s#imu_topic: .*#imu_topic: \"$IMU\"#" $PAR > $OUT/params.yaml
mkdir -p $B/src/point_lio_ros2/PCD; rm -f $B/src/point_lio_ros2/PCD/scans.pcd
T0=$(date +%s.%N)
ros2 run point_lio pointlio_mapping --ros-args --params-file $OUT/params.yaml -p odom_only:=false -p use_imu_as_input:=false -p prop_at_freq_of_imu:=true -p check_satu:=true -p init_map_size:=10 -p point_filter_num:=1 -p space_down_sample:=true -p filter_size_surf:=0.1 -p filter_size_map:=0.1 -p cube_side_length:=1000.0 -p runtime_pos_log_enable:=false -p odom_header_frame_id:=odom -p odom_child_frame_id:=base_link > $OUT/node.log 2>&1 &
NODE=$!
sleep 3
ros2 bag record -o $OUT/out /aft_mapped_to_init > $OUT/rec.log 2>&1 &
REC=$!
sleep 2
BIN=$(pgrep -f 'lib/point_lio/pointlio_mapping' | head -1)
( while kill -0 $BIN 2>/dev/null; do awk -v t=$(date +%s) '{print t, ($14+$15)/100}' /proc/$BIN/stat; grep VmRSS /proc/$BIN/status | awk '{print "rss_kb",$2}'; sleep 1; done ) > $OUT/cpu.txt 2>/dev/null &
CPU=$!
ros2 bag play $BAG --topics $LID $IMU --rate $RATE > $OUT/play.log 2>&1
T1=$(date +%s.%N)
sleep 3
CPU_S=$(awk '{print ($14+$15)/100}' /proc/$BIN/stat)
RSS=$(grep VmHWM /proc/$BIN/status | awk '{print $2}')
kill -INT $REC; sleep 2; kill -INT $BIN; for i in $(seq 1 60); do kill -0 $BIN 2>/dev/null || break; sleep 1; done; kill -INT $NODE 2>/dev/null; kill $CPU 2>/dev/null
cp $B/src/point_lio_ros2/PCD/scans.pcd $OUT/map.pcd 2>/dev/null
echo "play_wall_s $(echo "$T1 - $T0" | bc)" > $OUT/summary.txt
echo "cpu_s_total $CPU_S" >> $OUT/summary.txt
echo "rss_peak_kb $RSS" >> $OUT/summary.txt
cat $OUT/summary.txt
