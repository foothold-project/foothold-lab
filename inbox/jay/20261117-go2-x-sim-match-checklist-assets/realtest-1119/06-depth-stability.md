> 분류: 가이드 · 실기 측정 절차 (8 절 6 번)
> 작성: Claude 세션 (오흥재 지시, go2-lx) · 2026-11-19
> 근거: [`20261118-go2-x-ai-lx01-handoff.md`](../../20261118-go2-x-ai-lx01-handoff.md) 4 절 (180 초 기록: 무효 11.18 % · 프레임 번호 287→0 · 약 1 초 정지 1 회) · 7 절 11 · 11/19 05:20 녹화 (깊이 3.88 초 · 색 4.34 초 끊김 1 회) · 03:1x 카메라 시작 때 `Depth stream start failure (Hardware Error)` 1 회
> 요지: USB 젠더 후보 A/B/C 를 같은 포트 · 같은 선에서 재연결 5 회 + 5 분 깊이 · 색 · IMU 연속 녹화로 비교해, 깊이가 끊기지 않는 연결을 고른다
> 상태: 초안 · 측정 안 함 · 11/19 14:5x foothold-go2 PR #14 에서 옮김 (팀장 14:46: 측정 절차 · 시험 도구는 lab)

# 6. 깊이 안정성 (젠더 A/B/C)

## 무엇을 · 왜

- 무엇: D435i 를 Jetson 에 잇는 젠더 (어댑터) 후보마다 (1) 재연결 5 회에서 USB 3 으로 잡히는지 (2) 5 분 동안 깊이 · 색 · IMU 가 끊기지 않는지 잰다.
- 왜: 실기 정책은 깊이가 0.1 초마다 들어와야 한다. 지금까지 기록에 1 초 정지 (11/18) · 4 초 끊김 (11/19) · 시작 실패 1 회가 있었다. 원인이 젠더 · 선 · 전원 · 노드 중 어디인지 모른다.
- 로봇은 앉은 채 (Damping). 서기 · 걷기 없음 → 로봇 명령 없음. 젠더를 꽂고 빼는 것은 사람 손 (팀장 또는 현장 사람).

후보 표시: 기존 젠더 = A · 새 젠더 = B · 젠더 없이 직결 또는 다른 후보 = C (현장에서 정해 `06_candidates.csv` 에 적는다). 포트와 선은 셋 다 같게.

## 명령

후보마다 아래를 한 번씩. 순서는 A → B → C.

| 순서 | 누가 | 할 것 | 명령 (Jetson) |
|---|---|---|---|
| 1 | 사람 | 카메라 노드를 끈 상태에서 후보 젠더로 꽂기 | `bash ~/go2_diag/viewer/view_stop.sh` (출력 `0`) |
| 2 | AI 또는 사람 | USB 속도 · 장치 확인 (재연결 1 회째) | `lsusb -t \| grep -B1 -i video` (`5000M` 또는 그 위면 USB 3) |
| 3 | 사람 + AI | 뽑았다 다시 꽂기 4 번 더, 매번 2 번 명령 | 결과를 `06_replug.csv` 에 |
| 4 | AI 또는 사람 | 카메라 켜기 (IMU 포함 · `view_start.sh` 는 IMU 를 안 켜서 이 줄만 따로) | `source /opt/ros/humble/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; R=~/go2_diag/records/$(date +%Y%m%d-%H%M)-depth-stab-<A\|B\|C>; mkdir -p $R; setsid nohup ros2 launch realsense2_camera rs_launch.py enable_color:=true enable_depth:=true align_depth.enable:=false enable_gyro:=true enable_accel:=true unite_imu_method:=2 rgb_camera.color_profile:=640x480x30 depth_module.depth_profile:=640x480x30 > $R/rs.log 2>&1 < /dev/null &` |
| 5 | AI 또는 사람 | 시작 오류 확인 (10 초 뒤) | `grep -cE "ERROR\|Hardware Error" $R/rs.log` · `grep "USB type" $R/rs.log` (일련번호 줄은 옮기지 않는다) |
| 6 | AI 또는 사람 | 300 초 녹화 (4 번과 같은 셸 · 영상 본체 대신 camera_info 로 도착 시각만 · 작다) | `timeout -s INT 300 ros2 bag record -o $R/bag /camera/camera/depth/camera_info /camera/camera/color/camera_info /camera/camera/imu` |
| 7 | AI 또는 사람 | 노드 끄기 | `bash ~/go2_diag/viewer/view_stop.sh` |

camera_info 는 영상 한 장마다 같이 나가므로 도착 간격이 곧 영상 간격이다 (05:20 녹화: 깊이 camera_info 9783 · 깊이 영상 9150 이라 완전히 같지는 않다. 확인이 필요하면 6 번에 `/camera/camera/depth/image_rect_raw` 를 더하되 약 18 MB/초).

IMU 토픽 이름은 드라이버 판에 따라 다를 수 있다. 4 번 뒤 `ros2 topic list | grep -i imu` 로 보고 6 번을 맞춘다.

## 합격 줄

후보 하나가 아래를 모두 넘으면 합격.

| 항목 | 합격 |
|---|---|
| 재연결 | 5 / 5 번 USB 3 (`5000M` 이상) 으로 잡힘 |
| 시작 | 5 번에서 `Hardware Error` 0 |
| 깊이 | 300 초에 평균 29 Hz 이상 · 간격 0.2 초 넘는 끊김 0 회 |
| 색 | 같음 |
| IMU | 끊김 (간격 0.1 초 넘음) 0 회 |
| 1 초 정지 | 세 흐름이 같은 때 함께 멈춘 일 0 회 (11/18 에 1 회 있었던 꼴) |

여럿 합격이면 끊김이 가장 적은 것. 모두 불합격이면 가장 나은 것과 실패 꼴을 적고 팀장이 정한다 (선 · 전원 · 포트 바꾸기는 그다음 일).

분석 (회수 뒤 ai-lx01 · `.venv-rosbags`): 각 토픽 header 시각 간격으로 평균 Hz · 최대 간격 · 0.2 초 넘는 횟수 · 세 흐름 공통 정지 시각.

## 기록 파일 이름

| 파일 | 어디 |
|---|---|
| 녹화 | Jetson `~/go2_diag/records/<YYYYMMDD-HHMM>-depth-stab-A` (B · C 같음) → 이 폴더 아래 `06-depth-stability/` |
| 후보 | `06_candidates.csv`: `후보,무엇 (젠더 모양 · 산 곳 없이),포트,선` |
| 재연결 | `06_replug.csv`: `후보,회차,시각,속도(lsusb),잡힘` |
| 결과 | `06_summary.json`: 후보마다 흐름별 평균 Hz · 최대 간격 · 끊김 횟수 · 공통 정지 |
