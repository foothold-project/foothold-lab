#!/bin/bash
# D435i 각도 큰 창 (읽기 전용 · 로봇 명령 없음): 카메라 IMU 대 몸통 IMU 상대각 (목표 35°) + 바닥 기준 절대각 + 몸통 기울기.
# 11/18 의 relative_pitch_live 를 그대로 두고 옆에 relative_pitch_abs 를 하나 더 만든다.
# 쓰는 법 (Jetson): bash ~/go2_diag/pitch/pitch_abs.sh <본체 쪽 망 이름>
#   먼저 이 폴더 (tools/pitch) 를 Jetson ~/go2_diag/pitch/ 로 복사해 둔다.
# 주의: D435i 를 직접 여므로 ROS 카메라 노드 (view_start.sh · 녹화) 와 같이 못 쓴다. 이 스크립트가 view_stop.sh 로 먼저 끈다.
#       녹화 중에는 켜지 말 것.
set -e
IFACE=${1:?본체 쪽 망 이름}
P=~/go2_diag/pitch
M=~/go2_diag/sim_match_measure
bash ~/go2_diag/viewer/view_stop.sh >/dev/null 2>&1 || true
cp $P/relative_pitch_abs.cpp $P/abs_angles.hpp $M/
grep -q 'relative_pitch_abs' $M/CMakeLists.txt || cat >> $M/CMakeLists.txt <<'CM'

# 11/20 go2-lx: 상대각 + 절대각 창 (relative_pitch_live 는 그대로)
add_executable(relative_pitch_abs relative_pitch_abs.cpp)
target_include_directories(relative_pitch_abs PRIVATE "${RSUSB_ROOT}/include")
target_link_libraries(relative_pitch_abs PRIVATE
  unitree_sdk2
  "${RSUSB_ROOT}/build-rsusb/Release/librealsense2.so"
  ${OpenCV_LIBS})
CM
cmake --build $M/build_imu --target relative_pitch_abs -j4
echo "창: Jetson 화면 · 숫자 파일: /tmp/go2-relative-pitch-abs.txt · 끝내기: 창에서 q"
DISPLAY=${DISPLAY:-:0} $M/build_imu/relative_pitch_abs "$IFACE"
