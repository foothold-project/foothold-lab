분류: 실기 측정 · SLAM PoC (로봇 없이 녹화 재생)
작성: Claude 세션 (오흥재 지시, go2-lx) · 2026-11-20 00:3x
근거: lead-lx 11/19 23:3x 의뢰 (팀장 지시) · 앱 흐름 v0.6 「다음 측정할 것 · 제원 부담」 표 (`../../20261101-app/APP-FLOW-DIAGRAM.html#measure-slam`) · ai-lx01 녹화 05:20 · 04:59 · 22:29 · 이 폴더의 `results/*.json` · `tools/`
요지: Point-LIO (ROS2) 와 GLIM 을 sudo 없이 ai-lx01 에 세워 05:20 녹화로 돌렸다. L2 기본 설정으로는 둘 다 실패했는데, 까닭은 Go2 의 L2 가 거꾸로 달려 점구름 축과 IMU 축이 달라서다. 회전을 녹화에서 구해 넣으니 가만히 있을 때는 수 cm 안으로 멈추지만 걷는 동안은 Go2 odom 보다 2.5 배쯤 길게 잡혀 아직 쓸 수 있는 지도가 아니다
상태: PoC 1 차 · 05:20 만 유효 (22:29 녹화에 L2 없음 · 04:59 는 원래 점구름 없음) · 걷기 흐름 · Jetson 부담 미해결

# SLAM PoC (11/19 밤 · 녹화 재생)

## 0. 한눈에 (앱 흐름 v0.6 측정 표 칸으로)

| 측정 표의 칸 | 이번에 잰 값 (05:20 녹화 · 141 초 · 앉음 0~63 · 섬 63~99 · 걷기 99~141 초) | 등급 |
|---|---|---|
| 알고리즘별 흐름 · 시작 끝 자리 차 | 고리가 아닌 녹화라 「같은 자리로 돌아옴」 으로 잴 수 없다. 대신 Go2 odom 의 순 이동 1.15 m 와 견줌: Point-LIO (회전 고침 · x 뒤) 2.05 m · (x 앞) 5.06 m · GLIM (IMU · NAIVE 시작 · x 앞) 1.17 m · (x 뒤) 0.90 m | 녹화 재생 실측 |
| 걷기 대 서기의 흐름 차 | 가만히 앉음 58 초 순 이동: Point-LIO 0.005~0.018 m · GLIM 0.015~0.065 m. 가만히 섬 33 초: Point-LIO 0.03~0.06 m · GLIM 0.02~1.0 m. 걷기 42 초 경로 (1 Hz 로 셈): Go2 odom 4.47 m 대 Point-LIO 11.2~12.9 m · GLIM 12.1~13.1 m (2.5~2.9 배) | 녹화 재생 실측 |
| Point-LIO 부담 (CPU 코어 몫 · 메모리 · 처리 시간) | ai-lx01 (Threadripper 7970X) 에서 141 초 녹화에 CPU 23.7~26.6 초 = 한 코어의 약 17~19 % · 최대 메모리 245~302 MB · 실시간 재생 따라감. **Jetson Orin NX 는 미측정** | ai-lx01 실측 · Jetson 미확인 |
| GLIM 처리 시간 · GPU 메모리 | 05:20 141 초 녹화: 벽시계 77~79 초 (bag 7 GB 를 처음부터 읽는 시간 포함) · CPU 101 초 · GPU 메모리 약 340~470 MiB (RTX 5080 · 학습 작업과 같이 씀) · 라이다만 CT 판은 8.8 초 · 04:59 493 초 (라이다만) 70 초 | ai-lx01 실측 |
| L2 · IMU Hz | 05:20 녹화: `/utlidar/cloud` 2169 장 / 141 초 = 15.4 Hz · `/utlidar/imu` 35191 / 147.8 초 = 238 Hz | 녹화 셈 |
| 지도 그림 | `fig/` 넷 · 방 모양이 또렷하지 않음 (걷는 구간 흐름 탓) | 아래 3 절 |

## 1. 쓴 녹화 (22:29 숙소 기록은 못 씀)

| 녹화 | L2 · IMU | 이번에 쓴 것 |
|---|---|---|
| `20261119-2229-lodging-full` (540 초) | **없음.** bag 토픽은 카메라 여섯뿐. 녹화 시작 때 `topics.txt` 에 `/utlidar/cloud` · `cloud_deskewed` · `imu` · `robot_odom` 모두 「does not appear to be published yet」. 같은 때 lowstate (SDK) 는 들어옴 (SOC 68 %) · 05:20 의 본체 쪽 ROS 끊김과 같은 꼴로 보임 (까닭 미확인) | 못 씀 |
| `20261119-0520-room-walk-full` | 원래 점구름 `/utlidar/cloud` (x y z intensity ring time · 점마다 시각) + IMU · 0~141 초 (141 초에 본체 토픽 끊김) | 주 입력 |
| `20261119-0459-room-walk` | `cloud_deskewed` (이미 odom 틀 · 점마다 시각 없음) + IMU · 493 초 · Go2 odom 기준 시작 끝 0.2 m | 보조. odom 자세 역으로 몸 틀 점으로 되돌린 bag (`tools/make_0459_base_bag.py`) 을 라이다만으로 넣음 → Point-LIO · GLIM 둘 다 발산 (`results/pointlio_0459.json` · `glim_0459_ct.json`) |

## 2. 무엇을 세웠나 (sudo 없음 · 모두 ai-lx01 사용자 공간)

| 것 | 판 | 자리 |
|---|---|---|
| ROS 2 Humble (RoboStack conda) · PCL 1.13 · CUDA 12.9 (nvcc) · OpenCV · spdlog | conda-forge · robostack-staging | `/home/jay/data/slam_poc/env` |
| Point-LIO ROS2 판 | `dfloreaa/point_lio_ros2` a8e2d0d (L2 설정 `config/unilidar_l2.yaml` 있음) | `/home/jay/data/slam_poc/ws_pl` |
| GTSAM | `borglab/gtsam` 4.3a1 (2f3e56c0d) · 소스 빌드 | `/home/jay/data/slam_poc/local` |
| gtsam_points (CUDA · sm_120) | `koide3/gtsam_points` 8e94654 | 같은 곳 |
| GLIM · glim_ros2 (보기 창 끔) | `koide3/glim` 1a197c9 · `koide3/glim_ros2` 4d4ec52 | `/home/jay/data/slam_poc/ws_glim` |

ROS2 길: L2 공식 예시는 ROS1 이지만 Point-LIO 의 ROS2 판이 L2 설정과 함께 있고 Humble 에서 빌드 · 실행됨 (확인됨). GLIM 은 처음부터 ROS2 를 지원. 같은 길이 Jetson (Humble) 에서도 되는지는 미확인.

## 3. 결과

### 3a. 기본 설정은 실패: L2 점구름 축과 IMU 축이 다르다

- Point-LIO L2 기본 설정 (IMU-라이다 회전 = 단위 행렬): 120 초까지 버티다 걷기에서 발산 · 끝 44 m (`fig/pointlio_0520_default_diverged.png`).
- 라이다만 (IMU 끔): Point-LIO 는 앉아 있는 동안에도 34 m 흐름 · GLIM CT 는 경로 772 m. 선 자세에서 L2 점의 60 % 가 0.5 m 안 (바로 아래 바닥 · 로봇 몸), 81 % 가 0.8 m 안이라 남는 점도 대부분 바닥이어서 수평 이동을 잡기 어렵다 (측정 · `tools/calib_imu_lidar.py` 와 같은 녹화).
- 까닭: 가만히 선 25 초에 IMU 중력 방향 (위) 은 IMU 틀 (0.03, 0.00, 1.00) 인데, L2 점구름에서 찾은 바닥 법선 (바닥 → 센서) 은 라이다 틀 (0.13, -0.16, -0.98) 이다. 둘이 170° 어긋난다 = L2 가 거꾸로 달려 있다. Unitree 공식 Go2 URDF 의 라이다 장착 (`radar_joint` · rpy 0 2.8782 0 = y 축 164.9°) 으로 바꿔 보아도 26° 어긋나 맞지 않는다 (Go2 X 의 실제 장착 · 토픽 틀이 URDF 와 다른 것으로 보임 · 미확인).
- 고친 것: 바닥 법선을 IMU 위로 돌리는 회전 (roll · pitch) 을 녹화에서 구함. 앞뒤 (yaw 180°) 는 녹화만으로 가르지 못해 두 후보를 다 돌림: A = 라이다 x 가 앞 · B = 라이다 x 가 뒤. 이동 (lever arm) 은 L2 기본 (수 mm) 과 몸 IMU 기준 (0.33 m) 두 가지를 돌렸고 결과 차이가 작아 L2 기본을 씀. 값은 `config/pl_*.yaml` 의 `extrinsic_R` · `config/glim_*/config_sensors.json` 의 `T_lidar_imu`.

### 3b. 회전을 고친 뒤 (05:20)

| 판 | 앉음 58 초 순 이동 m | 섬 33 초 순 이동 m | 걷기 42 초 순 이동 m · 경로 m (1 Hz) · 높이 폭 m | 141 초 시작 끝 m | CPU 초 · 메모리 |
|---|---|---|---|---|---|
| Go2 odom (비교) | 0.000 | 0.003 | 1.14 · 4.47 · 0.03 | 1.15 | (로봇 안) |
| Point-LIO B (x 뒤) | 0.005 | 0.034 | 2.09 · 11.2 · 0.79 | 2.05 | 26.0 · 256 MB |
| Point-LIO A (x 앞) | 0.014 | 0.061 | 4.91 · 12.1 · 0.21 | 5.06 | 26.0 · 259 MB |
| Point-LIO B · 근거리 0.8 m 버림 | 0.008 | 0.041 | 2.44 · 11.7 · 0.95 | 2.47 | 23.7 · 245 MB |
| GLIM B (x 뒤 · NAIVE 시작) | 0.065 | 0.024 | 0.86 · 12.1 · 0.23 | 0.90 | 101 · GPU 약 0.4 GB |
| GLIM A (x 앞 · NAIVE 시작) | 0.015 | 1.009 | 2.22 · 13.1 · 0.19 | 1.17 | 101 · GPU 약 0.4 GB |

- GLIM 은 처음 시작 추정 (ROBUST) 이 앉아 있는데도 속도 3~4 m/s 로 잡혀 깨졌다 (segfault). 로봇이 가만히 시작하므로 NAIVE 로 바꿔 돌았다.
- 걷는 동안 둘 다 경로를 Go2 odom 의 2.5~2.9 배로 잡는다. 걸음 충격 · 다리가 라이다에 들어오는 것 · 바닥만 보이는 시야가 후보 (미확인). 높이도 걷는 중 0.2~0.9 m 흔들린다 (바닥은 평평).
- 고리가 아닌 녹화라 「시작 끝 자리 차」 는 흐름을 직접 재지 못한다. 진짜 흐름은 같은 자리로 돌아오는 L2 포함 녹화가 있어야 잰다.

### 3c. 지도 그림

| 그림 | 무엇 |
|---|---|
| `fig/pointlio_0520_B_xback_Tl2.png` · `fig/pointlio_0520_A_xfwd_Tl2.png` | Point-LIO 지도 (5 cm 아래로 줄이지 않은 저장 점) · 빨강 = 궤적 |
| `fig/glim_0520_imuB_naive.png` · `fig/glim_0520_imuA_naive.png` | GLIM 부분 지도 점 모음 · 빨강 = 궤적 |
| `fig/pointlio_0520_default_diverged.png` | L2 기본 설정 (발산) |

방의 벽 · 가구 모양이 또렷하지 않다. 04:59 의 odom 쌓기 지도 (`../20261119-0459-room-walk/room_topview.png`) 보다 못하다. 원본 지도 (`map.pcd` 수십 MB) 와 궤적은 ai-lx01 `/home/jay/data/slam_poc/runs/` 에만 둔다.

## 4. 다음 (제안 · 팀장 결정)

1. **L2 포함 고리 녹화 하나** (같은 자리로 돌아오기 · 3 분 남짓 · 첫 30 초 가만히). 22:29 처럼 L2 가 안 들어오면 녹화 전에 `ros2 topic hz /utlidar/cloud` 로 먼저 확인 (`../realtest-1119/tools/watch_record.sh`).
2. IMU-라이다 앞뒤 (A · B) 를 가르는 녹화: 서서 제자리 앞으로 몇 걸음 (Go2 odom 과 라이다 이동 방향 대조) 또는 Unitree 의 Go2 X 실제 `utlidar_lidar` · `utlidar_imu` 틀 정보 (Jetson 의 `/tf_static` 녹화).
3. 걷는 중 흐름: 근거리 버림 · 다리 점 걸러내기 · IMU 잡음 값 · Point-LIO `use_imu_as_input` 을 같은 녹화로 비교.
4. Jetson Orin NX 에서 같은 Point-LIO 를 녹화 재생으로 돌려 CPU 몫 재기 (설치는 Jetson 시스템 변경이라 팀장 동의 뒤).

## 5. 다시 돌리는 법

```
# Point-LIO (실시간 재생 · CPU 초 · 최대 메모리 기록)
tools/run_pointlio.sh <이름> <bag 폴더> /utlidar/cloud /utlidar/imu config/pl_B_xback_Tl2.yaml 1.0
# GLIM (최대 속도 재생 · auto_quit)
tools/run_glim.sh <이름> <bag 폴더> config/glim_0520_imuB_naive   # 나머지 config 파일은 glim 기본 config 폴더에서 복사
# 정리 (궤적 · Go2 odom 비교 · 위에서 본 그림)
python -I tools/analyze_run.py <run> <bag> /aft_mapped_to_init
python -I tools/analyze_glim.py <run> <bag>
```

스크립트의 경로는 ai-lx01 기준이다.
