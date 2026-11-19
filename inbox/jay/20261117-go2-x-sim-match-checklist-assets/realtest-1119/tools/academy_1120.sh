#!/bin/bash
# 11/20 학원 Go2 X 기록 (Jetson 에서 팀장이 직접 친다 · 받기만 · 로봇 명령 없음 · 로봇은 팀장 조이스틱).
# academy_1119.sh (lab 가지 feat/jetson-storage-1119 · 0cbf6b810) 의 사본에 관문 셋을 더했다:
#   /utlidar/cloud (SLAM 원래 점) · /camera/camera/color/image_raw/compressed · /tf_static (한 번만 오는 토픽 · echo 로 확인)
#   /sportmodestate · /lowstate 는 Jetson ROS 에 unitree_go 정의가 없어 bag 에 못 담으므로 SDK 감시 (go2_readonly_monitor) 로 관문 · 기록
# 하나라도 0 이면 기록을 시작하지 않고 카메라를 끈다.
#   쓰는 법: bash ~/go2_diag/jetson_storage/academy_1120.sh [초 · 기본 540]
#   관문 통과 뒤 「Enter」 를 누르면 기록 시작 (그 전에 팀장이 로봇을 앉힌 채 둔다 · 녹화 순서는 ACADEMY-1120.md 3 절)
SEC=${1:-540}
N=$(date +%Y%m%d-%H%M)-academy-full
R=~/go2_diag/records/$N
mkdir -p $R
exec 3>&1 4>&2
exec > >(tee -a $R/run.log) 2>&1
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
GO2_IFACE=${GO2_IFACE:-enP8p1s0}
export CYCLONEDDS_URI=${CYCLONEDDS_URI:-"<CycloneDDS><Domain><General><Interfaces><NetworkInterface name=\"$GO2_IFACE\" priority=\"default\" multicast=\"default\"/></Interfaces></General></Domain></CycloneDDS>"}
MON=~/go2_diag/20261118-go2-readonly-boot-gate/build/go2_readonly_monitor
cd ~/go2_diag/jetson_storage
echo "== $N · cyclonedds $GO2_IFACE · start $(date +%T)"
cam_down() { [ -n "$STARTED_CAM" ] && { pkill -INT -f realsense2_camera_node; sleep 3; pkill -f rs_launch.py; sleep 2; pkill -KILL -f realsense2_camera_node; } ; true; }
if pgrep -f relative_pitch_ >/dev/null; then echo "!! 각도 창이 D435i 를 쥐고 있음 · 창에서 q 로 끄고 다시"; exit 2; fi
if ! pgrep -f realsense2_camera_node >/dev/null; then
  setsid nohup ros2 launch realsense2_camera rs_launch.py enable_color:=true enable_depth:=true pointcloud.enable:=false \
    align_depth.enable:=true rgb_camera.color_profile:=640x480x30 depth_module.depth_profile:=640x480x30 \
    > $R/rs.log 2>&1 < /dev/null &
  STARTED_CAM=1
fi
echo "카메라 켬 · 토픽 Hz 재는 중 (약 1 분)"; sleep 10
T="/utlidar/cloud /utlidar/cloud_deskewed /utlidar/imu /utlidar/robot_odom /camera/camera/depth/image_rect_raw /camera/camera/color/image_raw/compressed"
P=""
for t in $T; do ( echo "## $t"; timeout -k 3 10 ros2 topic hz $t 2>&1 | tail -3 ) > $R/.probe-$(echo $t | tr / _).txt & P="$P $!"; done
timeout -k 3 12 ros2 topic echo --once --qos-durability transient_local /tf_static > $R/.probe-tf_static.txt 2>&1 & P="$P $!"
$MON $GO2_IFACE 5 $R/gate_monitor.csv > $R/gate_monitor.log 2>&1 & P="$P $!"
wait $P
ZERO=""
for t in $T; do grep -q "average rate" $R/.probe-$(echo $t | tr / _).txt || ZERO="$ZERO $t"; done
grep -q "child_frame_id" $R/.probe-tf_static.txt || ZERO="$ZERO /tf_static"
SPORT=$(tail -1 $R/gate_monitor.csv 2>/dev/null | cut -d, -f5); STATE=$(tail -1 $R/gate_monitor.csv 2>/dev/null | cut -d, -f3)
[ "${SPORT:-0}" -gt 0 ] 2>/dev/null || ZERO="$ZERO /sportmodestate(SDK)"
[ "${STATE:-0}" -gt 0 ] 2>/dev/null || ZERO="$ZERO /lowstate(SDK)"
{ cat $R/.probe-*.txt; echo "## SDK sport_callbacks=$SPORT state_callbacks=$STATE (5 s)"; } > $R/topics.txt; rm -f $R/.probe-*.txt
grep -A2 '^## ' $R/topics.txt | grep -E '^## |average rate' | paste - - 2>/dev/null | sed 's/  */ /g'
if [ -n "$ZERO" ]; then
  echo; echo "!!!!! 관문 실패 · 0 Hz:$ZERO · 기록 안 함 · 카메라 끔 ($(date +%T))"
  cam_down; exec 1>&3 2>&4; exit 2
fi
echo; echo "===== 관문 통과 (9 개 모두 들어옴) · 로봇은 앉은 채 · 준비되면 Enter (끝내려면 Ctrl+C) ====="
read -r _
echo "== 기록 시작 $(date +%T) · ${SEC} 초 · 순서: 앉아 30 초 → 서서 60 초 → 한 바퀴 돌아 같은 자리 → 서서 60 초 → 앉기"
$MON $GO2_IFACE $SEC $R/monitor.csv > $R/console.log 2>&1 & M=$!
vmstat 5 > $R/vmstat-main.txt & V=$!
python3 jrec.py full $N --seconds $SEC
kill $V 2>/dev/null; wait $M 2>/dev/null
cam_down
echo "== 끝 $(date +%T) · $R"
exec 1>&3 2>&4; sleep 1   # run.log 를 닫은 뒤 sha256 (1119 와 같은 까닭)
python3 -c "import jrec; jrec.write_sums('$R')"
echo "sha256 적음 · 받기는 ai-lx01 jetson_sync.py"
