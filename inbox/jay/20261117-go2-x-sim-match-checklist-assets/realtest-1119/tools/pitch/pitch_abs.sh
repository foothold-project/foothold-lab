#!/bin/bash
# D435i 각도 큰 창 (읽기 전용 · 로봇 명령 없음): 카메라 IMU 대 몸통 IMU 상대각 (목표 35°) + 바닥 기준 절대각 + 몸통 기울기.
# 11/18 의 relative_pitch_live 를 그대로 두고 옆에 relative_pitch_abs 를 하나 더 만든다.
# 쓰는 법 (Jetson): bash ~/go2_diag/pitch/pitch_abs.sh <본체 쪽 망 이름>
#   먼저 이 폴더 (tools/pitch) 를 Jetson ~/go2_diag/pitch/ 로 복사해 둔다.
# 주의: D435i 를 직접 여므로 ROS 카메라 노드 (view_start.sh · 녹화) 와 같이 못 쓴다. 이 스크립트가 view_stop.sh 로 먼저 끈다.
#       녹화 중에는 켜지 말 것.
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
# 11/21 app-lx: 팀장 터미널에서 세 번 모두 시작 직후 free() 로 죽음 · 원격 (ssh · ROS 안 켬) 에서는 띄움 정상.
#   짐작 (미확인): ROS 를 source 한 터미널은 LD_LIBRARY_PATH 앞에 /opt/ros/humble/lib 이 들어가
#   Unitree SDK 가 자기 libddsc 대신 ROS 쪽 libddsc 를 잡는다. 그래서 빌드 · 실행을 ROS 를 뺀 환경으로 한다.
RS=~/go2_diag/librealsense-rsusb-v2.58.4/build-rsusb/Release
CLEAN=(env -u LD_LIBRARY_PATH -u CYCLONEDDS_URI -u AMENT_PREFIX_PATH -u CMAKE_PREFIX_PATH -u ROS_DISTRO)
case ":${LD_LIBRARY_PATH:-}:${AMENT_PREFIX_PATH:-}:" in *ros*) echo "(이 터미널은 ROS 가 켜져 있음 · 각도 창은 ROS 를 뺀 환경으로 띄움)";; esac
"${CLEAN[@]}" cmake -S $M -B $M/build_imu >/dev/null && "${CLEAN[@]}" cmake --build $M/build_imu --target relative_pitch_abs -j4
echo "창: Jetson 화면 · 숫자 파일: /tmp/go2-relative-pitch-abs.txt · 끝내기: 창에서 q"
# 11/20 19:3x: 시작 직후 free() 오류로 가끔 죽음 (원격 6 번 중 0 번 · 팀장 첫 실행 1 번). 5 초 안에 죽으면 세 번까지 다시 띄운다
for TRY in 1 2 3; do
  T0=$(date +%s)
  "${CLEAN[@]}" DISPLAY=${DISPLAY:-:0} LD_LIBRARY_PATH=$RS:/usr/local/lib $M/build_imu/relative_pitch_abs "$IFACE"; RC=$?
  [ $RC -eq 0 ] && break
  if [ $(( $(date +%s) - T0 )) -lt 5 ]; then
    echo "(시작 중 죽음 rc=$RC · 다시 띄움 $TRY/3)"
    # 처음 한 번만: 실제로 잡힌 라이브러리 (이 줄을 보고에 붙여 주세요)
    [ $TRY = 1 ] && "${CLEAN[@]}" LD_LIBRARY_PATH=$RS:/usr/local/lib ldd $M/build_imu/relative_pitch_abs | grep -E 'ddsc|ddscxx|realsense|unitree' | sed 's/^/   잡힌 lib: /'
    sleep 1; continue
  fi
  echo "(끝남 rc=$RC)"; break
done
