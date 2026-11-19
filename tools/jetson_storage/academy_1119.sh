#!/bin/bash
# 11/19 real Go2 X record (academy 21:4x, moved to lodging) (owner moves the robot by joystick; this only records).
# Runs detached on the Jetson so a wifi drop does not stop it.
# camera up -> topics.txt (hz, bw, sizes, battery) -> jrec full 540 s -> jrec full 60 s zstd -> camera down
N=${1:?marker name}
R=~/go2_diag/records/$N
mkdir -p $R
exec > $R/run.log 2>&1
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
cd ~/go2_diag/jetson_storage
echo "start $(date +%T)"
if ! pgrep -f realsense2_camera_node >/dev/null; then
  setsid nohup ros2 launch realsense2_camera rs_launch.py enable_color:=true enable_depth:=true pointcloud.enable:=false \
    align_depth.enable:=true rgb_camera.color_profile:=640x480x30 depth_module.depth_profile:=640x480x30 \
    > $R/rs.log 2>&1 < /dev/null &
  echo $! > $R/rs.pid
  STARTED_CAM=1
elif [ -e $R/rs.pid ]; then
  STARTED_CAM=1   # rerun of the same marker: the camera was started by this run
fi
sleep 10
low() { timeout -k 3 6 ros2 topic echo --once /lowstate 2>&1 | grep -E -A3 'bms_state|soc|temperature' | head -60 > $R/lowstate-$1.txt; timeout -k 3 6 ros2 topic echo --once /lowstate > $R/lowstate-$1.full.txt 2>&1; }
low start
{
  echo "# topics $(date +%T)"; timeout -k 3 15 ros2 topic list -t
  T="/lowstate /sportmodestate /utlidar/imu /utlidar/cloud /utlidar/cloud_deskewed /utlidar/robot_odom /camera/camera/color/image_raw /camera/camera/color/image_raw/compressed /camera/camera/depth/image_rect_raw /camera/camera/aligned_depth_to_color/image_raw"
  for t in $T; do ( echo "## $t"; timeout -k 3 10 ros2 topic hz $t 2>&1 | tail -3; timeout -k 3 10 ros2 topic bw $t 2>&1 | tail -2 ) > $R/.probe-$(echo $t | tr / _).txt & P="$P $!"; done
  wait $P   # not a bare wait: the camera launch is a background job of this shell too
  # gate (lead 11/19 23:4x): the 22:29 lodging bag had camera only; L2 · imu · odom were "not published yet"
  ZERO=""
  for t in /utlidar/cloud_deskewed /utlidar/imu /utlidar/robot_odom /camera/camera/depth/image_rect_raw; do
    grep -q "average rate" $R/.probe-$(echo $t | tr / _).txt || ZERO="$ZERO $t"
  done
  echo "## gate zero-hz:${ZERO:- none}"
  cat $R/.probe-*.txt; rm -f $R/.probe-*.txt
  echo "## camera_info"; for c in color depth; do timeout -k 3 6 ros2 topic echo --once /camera/camera/$c/camera_info 2>&1 | grep -E '^(width|height):'; done
  echo "## L2 points per message"; timeout -k 3 6 ros2 topic echo --once /utlidar/cloud 2>&1 | grep -E '^(width|height|point_step|row_step):'
} > $R/topics.txt 2>&1
echo "probe done $(date +%T)"
ZERO=$(sed -n 's/^## gate zero-hz://p' $R/topics.txt)
if [ "$ZERO" != " none" ]; then
  echo "gate fail:$ZERO $(date +%T)"
  [ -n "$STARTED_CAM" ] && { pkill -INT -f realsense2_camera_node; sleep 3; pkill -f rs_launch.py; sleep 2; pkill -KILL -f realsense2_camera_node; }
  echo "end $(date +%T)"; exec >/dev/null 2>&1; python3 -c "import jrec; jrec.write_sums('$R')"; exit 0
fi
echo "gate ok $(date +%T)"
# the 540 s record starts only when the owner stands the robot and lead says go (touch $R/GO); 60 min cap
for i in $(seq 1 720); do [ -e $R/GO ] && break; sleep 5; done
if [ ! -e $R/GO ]; then
  echo "no GO in 60 min, camera down $(date +%T)"
  [ -n "$STARTED_CAM" ] && { pkill -INT -f realsense2_camera_node; sleep 3; pkill -f rs_launch.py; sleep 2; pkill -KILL -f realsense2_camera_node; }
  echo "end $(date +%T)"; exec >/dev/null 2>&1; python3 -c "import jrec; jrec.write_sums('$R')"; exit 0
fi
echo "GO $(date +%T)"
vmstat 5 > $R/vmstat-main.txt & V=$!
python3 jrec.py full $N --seconds 540
kill $V
low end
vmstat 5 > $R/vmstat-zstd.txt & V=$!
python3 jrec.py full ${N%-full}-zstdtest --seconds 60 --zstd
kill $V
if [ -n "$STARTED_CAM" ]; then pkill -INT -f realsense2_camera_node; sleep 3; pkill -f "rs_launch.py"; sleep 2; pkill -KILL -f realsense2_camera_node; fi
echo "end $(date +%T)"
exec >/dev/null 2>&1   # run.log is final before the sums, or the copy never verifies (11/19 22:50)
python3 -c "import jrec; jrec.write_sums('$R')"
