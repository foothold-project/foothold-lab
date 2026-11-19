#!/bin/bash
# 녹화 중 끊김 감시 (읽기 전용 · 로봇에 명령 없음).
# full_record.sh · uslam_record.sh 를 켠 뒤 다른 터미널에서 같은 녹화 폴더를 주고 켠다.
#
# 왜: 11/19 05:20 녹화에서 141 초에 Go2 본체 쪽 (L2 · odom · IMU · lowstate) 이 한꺼번에 끊겼는데
#     녹화는 끝까지 「정상」 으로 돌아 아무도 몰랐다. 카메라만 330 초 남았다.
#
# 쓰는 법: bash watch_record.sh <녹화 폴더> <본체 쪽 망 이름> [초 · 기본 480] [간격 · 기본 10]
#   예:    bash watch_record.sh ~/go2_diag/records/20261119-1500-room-walk-full <망 이름> 480
# 남기는 것: <녹화 폴더>/watch.log (간격마다 한 줄) · 끊김을 처음 본 때 <녹화 폴더>/watch_drop_<시각>.txt
# 알림: 터미널에 「!! 끊김」 줄과 종소리 (\a). 녹화는 멈추지 않는다 (판단은 사람).
#
# 확인 하나 (간격마다):
#   lowstate   : 감시 console.log 마지막 줄의 state_age_ms 가 1000 넘으면 본체 쪽 끊김
#   토픽 Hz    : /utlidar/cloud_deskewed · /utlidar/robot_odom · 깊이 camera_info 를 ros2 topic hz 로 3 초 (ros2 가 있을 때)
# 끊김을 처음 보면 한 번: ip -s link (망) · ip neigh · 커널 기록 끝 40 줄 (읽기만 · 권한 없으면 빈 칸)

set -u
DIR=${1:?녹화 폴더}
IFACE=${2:?본체 쪽 망 이름}
SEC=${3:-480}
EVERY=${4:-10}
LOG=$DIR/watch.log
STALE_MS=${STALE_MS:-1000}

HAVE_ROS=0
if [ -f /opt/ros/humble/setup.bash ]; then
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  command -v ros2 >/dev/null && HAVE_ROS=1
fi

hz() {  # $1 토픽 → 평균 Hz 숫자 하나 또는 0
  [ "$HAVE_ROS" = 1 ] || { echo "-"; return; }
  local v
  v=$(timeout 4 ros2 topic hz "$1" 2>/dev/null | awk '/average rate/ {r=$3} END {print r+0}')
  echo "${v:-0}"
}

state_age() {  # console.log 마지막 줄의 state_age_ms (없으면 -1)
  local f=$DIR/console.log
  [ -s "$f" ] || { echo -1; return; }
  tail -n 1 "$f" | tr ' ' '\n' | awk -F= '$1=="state_age_ms" {print int($2); f=1} END {if (!f) print -1}'
}

snapshot() {  # 끊김 순간 망 상태를 남긴다 (읽기만)
  local out=$DIR/watch_drop_$(date +%H%M%S).txt
  {
    echo "# $(date '+%F %T') 끊김 첫 관찰 · 망 $IFACE"
    echo "## ip -s link"; ip -s link show "$IFACE" 2>&1
    echo "## ip neigh"; ip neigh show dev "$IFACE" 2>&1
    echo "## 커널 기록 끝 40 줄"; journalctl -k -n 40 --no-pager 2>&1 || dmesg 2>&1 | tail -40
  } > "$out"
  echo "$out"
}

echo "# 시작 $(date '+%F %T') · 폴더 $DIR · 망 $IFACE · ${SEC} 초 · ${EVERY} 초마다 · ros2=$HAVE_ROS" | tee -a "$LOG"
echo "# 시각 경과초 state_age_ms L2_Hz odom_Hz depth_Hz 판정" | tee -a "$LOG"
START=$(date +%s); DROPPED=0
while :; do
  NOW=$(date +%s); EL=$((NOW - START))
  [ "$EL" -ge "$SEC" ] && break
  AGE=$(state_age)
  L2=$(hz /utlidar/cloud_deskewed); OD=$(hz /utlidar/robot_odom); DP=$(hz /camera/camera/depth/camera_info)
  VERDICT=ok
  if [ "$AGE" -gt "$STALE_MS" ]; then VERDICT="!!_본체_끊김(lowstate_${AGE}ms)"; fi
  if [ "$HAVE_ROS" = 1 ]; then
    awk -v a="$L2" 'BEGIN {exit !(a < 5)}' && VERDICT="${VERDICT/ok/}!!_L2_${L2}Hz"
    awk -v a="$OD" 'BEGIN {exit !(a < 50)}' && VERDICT="${VERDICT/ok/}!!_odom_${OD}Hz"
    awk -v a="$DP" 'BEGIN {exit !(a < 20)}' && VERDICT="${VERDICT/ok/}!!_깊이_${DP}Hz"
  fi
  LINE="$(date +%T) $EL $AGE $L2 $OD $DP $VERDICT"
  echo "$LINE" >> "$LOG"
  if [ "$VERDICT" != ok ]; then
    printf '\a!! 끊김 %s\n' "$LINE"
    if [ "$DROPPED" = 0 ]; then DROPPED=1; echo "   망 상태 저장: $(snapshot)"; fi
  else
    echo "$LINE"
  fi
  sleep "$EVERY"
done
echo "# 끝 $(date '+%F %T') · 끊김 본 적 $DROPPED" | tee -a "$LOG"
