> 분류: 가이드 · 실기 측정 목록 한 장 (11/20 학원)
> 작성: Claude 세션 (오흥재 지시, go2-lx) · 2026-11-20 08:5x
> 근거: lead-lx 08:49 의뢰 (팀장 지시) · 11/19 기록 셋의 빠짐 (22:29 에 L2 · IMU · odom 0 개 · 05:20 은 141 초에 본체 토픽 끊김 · `/sportmodestate` 는 bag 에 못 들어감) · lab 가지 `feat/jetson-storage-1119` 의 `academy_1119.sh` · `go2_session.sh` (0 Hz 관문) · SLAM PoC (`../slam-poc-1119/README.md`)
> 요지: 학원에서 1) 서 있는 자세로 카메라 각도를 큰 창에 띄워 브라켓을 35° 로 맞추고 2) 모든 토픽이 Hz 를 내는지 관문을 통과한 뒤에만 고리 녹화를 한다
> 상태: 11/20 08:5x Jetson 에 놓음 · 각도 창 Jetson 빌드 통과 (`~/go2_diag/sim_match_measure/build_imu/relative_pitch_abs` · 각 계산 시험 Jetson 에서도 통과) · 창 띄우기 · 기록 실행은 미확인 (카메라 노드 · 로봇 명령 안 냄)

# 11/20 학원 측정 한 장

로봇 명령 (서기 · 걷기 · 앉기) 은 모두 **팀장 조이스틱**. 아래 명령은 모두 받기만 한다.

## 1. 카메라 각도 창 (브라켓 맞추기 · 목표 몸통 기준 35°)

| 순서 | 누가 | 무엇 | 명령 |
|---|---|---|---|
| 1 | (끝남 08:54) | `tools/pitch/` 를 Jetson `~/go2_diag/pitch/` 에 놓고 빌드 | |
| 2 | 팀장 조이스틱 | 평평한 맨바닥에서 서기 · 가만히 | |
| 3 | 학원 세션 (Jetson) | **한 줄**: 카메라 노드를 끄고 창을 빌드 · 띄움 | `bash ~/go2_diag/pitch/pitch_abs.sh enP8p1s0` |
| 4 | 팀장 | 창의 큰 숫자 (상대각) 가 35.00 ± 0.15 가 되도록 브라켓 조임. 초록 = 맞음 | 창에서 `q` 로 끝 |

창에 뜨는 것 (Jetson 화면 · 큰 글씨):

| 줄 | 뜻 | 근거 |
|---|---|---|
| CAMERA / BODY RELATIVE DOWN PITCH **xx.xxx deg** | D435i IMU 와 Go2 몸통 IMU 의 중력 방향으로 맞춘 상대각 (몸통 기준 · 목표 35) · 차이 · LOWER / RAISE CAMERA | 11/18 `relative_pitch_live` 그대로 |
| CAMERA vs FLOOR **xx.xx deg down · roll** | 카메라 광축이 수평에서 아래로 숙인 각 (바닥 · 중력 기준 절대각) · 옆 기울기 | 새로 더함 (`abs_angles.hpp`) |
| BODY (Go2 IMU) pitch · roll | 몸통 앞숙임 (+ = 코가 아래) · 옆 기울기 | 새로 더함 |
| check | 절대각 ≈ 상대각 + 몸통 앞숙임 (어긋나면 축 약속이 틀린 것) | |

- 터미널에도 한 줄로 갱신: `rel 35.02  abs 38.61  body 3.59  err 0.02`. 숫자 파일 `/tmp/go2-relative-pitch-abs.txt`.
- D435i 를 직접 열어서 ROS 카메라 노드 · 녹화와 같이 못 쓴다 (스크립트가 `view_stop.sh` 로 먼저 끈다). 녹화 전에 끈다.
- 11/19 숙소 녹화 계산값 (매트 위): 바닥 기준 38.59° · 몸통 3.6° 숙임 추정 → 상대 35.0°. 맨바닥 · 이 창으로 다시 잰다.
- 확인한 것: 각 계산 시험 (`abs_angles_test.cpp` · 수평 35 · 코 3.6° 숙임 → 절대 38.6 · 상대 35 · 옆 기울기) 통과 · 프로그램 전체 문법 검사 (unitree_sdk2 · librealsense v2.58.4 · OpenCV 헤더) 통과. **Jetson 에서 빌드 · 실행은 미확인.**

## 2. 녹화 전 관문 (0 Hz 면 시작 안 함)

| 토픽 | 무엇 | 기대 Hz (11/19 실측) | 관문 방법 | 지금 `academy_1119.sh` |
|---|---|---|---|---|
| `/utlidar/cloud` | L2 원래 점 (점마다 시각 · SLAM 입력) | 15.4 | `ros2 topic hz` 평균이 나와야 | **빠짐 · 더할 것** |
| `/utlidar/cloud_deskewed` | L2 odom 틀 점 (방 지도) | 13.6 | 같음 | 있음 |
| `/utlidar/imu` | L2 IMU | 238 | 같음 | 있음 |
| `/utlidar/robot_odom` | Go2 odom | 146 | 같음 | 있음 |
| `/camera/camera/depth/image_rect_raw` | 깊이 원본 | 30 | 같음 | 있음 |
| `/camera/camera/color/image_raw/compressed` | RGB | 30 | 같음 | **빠짐 · 더할 것** |
| `/tf_static` | 카메라 틀 (한 번만 나오는 토픽이라 hz 로는 0) | 없음 | `ros2 topic echo --once /tf_static` 가 메시지를 내야 | 없음 · 더할 것 |
| `/sportmodestate` | 몸 상태 (상태 번호 · 몸 높이) | 약 300 | **ros2 bag 은 못 담음** (Jetson ROS 에 `unitree_go` 메시지 정의 없음 · 05:20 `bag.log` 경고 1520 줄). SDK 감시 `go2_readonly_monitor` 의 `sport_callbacks` 가 늘어야 | 녹화 목록에는 있으나 실제로는 0 |
| `/lowstate` (SDK) | 관절 온도 · 배터리 · reserve | 500 | SDK 감시 `state_callbacks` 가 늘어야 | 녹화 시작 · 끝에 한 번씩 |

관문 통과 기준: 위 9 줄 모두. **Jetson 에 놓은 사본: `~/go2_diag/jetson_storage/academy_1120.sh`** (`academy_1119.sh` 0cbf6b810 사본 + 세 토픽 · SDK 감시 관문 · DDS enP8p1s0 고정 · 팀장이 직접 치고 관문 뒤 Enter). 08:55 읽기만 시험: L2 원래 점 15.5 Hz · IMU 251 Hz · odom 146 Hz · SDK sport 3 초 892 · lowstate 1511 (카메라는 안 켜서 깊이 · RGB · tf_static 은 안 잼). SDK 감시 프로그램은 끝날 때 `free(): invalid next size` 로 죽지만 CSV 는 다 쓴 뒤라 관문 · 기록에 지장 없음 (11/18 부터 있던 것 · 고치지 않음). 하나라도 0 이면 녹화하지 않고 run 받은편지함에 토픽 이름을 보낸다 (`go2_session.sh` 꼴). 녹화가 도는 동안에는 `tools/watch_record.sh` 로 10 초마다 같은 것을 다시 본다 (05:20 처럼 중간에 끊기면 알림).

## 3. 녹화 순서 (한 번 · 약 9 분)

| 시각 (녹화 시작 기준) | 로봇 (팀장 조이스틱) | 왜 |
|---|---|---|
| 관문 전 | 앉음 | 관문 · 각도 창 |
| 0~30 초 | 앉은 채 가만히 | IMU 초기화 (SLAM 이 가만히 시작해야 함) · 앉은 자세 카메라 각 |
| 30~90 초 | 서서 가만히 (맨바닥) | 선 자세 카메라 높이 · 각 · 몸통 기울기 |
| 90~450 초 | 방 한 바퀴 이상 · **처음 선 자리로 돌아오기** · 마지막에 가만히 10 초 | SLAM 시작 · 끝 자리 차 (11/19 녹화는 고리가 아니라 못 잼) |
| 450~510 초 | 서서 가만히 | 걷기 대 서기 흐름 차 |
| 510~540 초 | 앉기 | |

녹화 토픽 (`jrec.py full` 과 같음): 위 표의 ROS 토픽 7 개 + `/tf`. 같은 때 SDK 감시 `go2_readonly_monitor <망> 540 monitor.csv` (상태 번호 · 몸 높이 · 온도 · 배터리) 를 같이 켠다. 깊이 원본 포함 약 18 MB/초 · 540 초 ≈ 10 GB (Jetson 남은 공간을 `jrec.py` 가 먼저 본다).

## 4. 끝나고

- 회수 · sha256 대조: `go2_session.sh` 의 `jetson_sync.py sync` (D · NAS 두 곳).
- 읽기: `record_offline.py` (토픽 표 · 바닥 평면 · 몸 기울기 · 지도) · SLAM 은 `../slam-poc-1119/tools/run_pointlio.sh` · `run_glim.sh` (IMU-라이다 회전은 `../slam-poc-1119/config/` 값).
