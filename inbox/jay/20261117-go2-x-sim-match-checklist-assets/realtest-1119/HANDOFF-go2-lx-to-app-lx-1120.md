> 분류: 인수인계 · go2-lx → app-lx (실기 Go2 X 측정 · Jetson)
> 작성: Claude 세션 (오흥재 지시, go2-lx) · 2026-11-20 19:4x
> 근거: 팀장 19:37 「내용 다 정리해서 app-lx 에서 진행하게 인수인계」 · go2-lx 11/19 10:5x~11/20 19:3x 작업 · lab PR #880 · #881 · #883 · #897 · foothold-go2 가지 feature/go2-policy-bundle-jay
> 요지: 학원 실기 측정을 바로 할 수 있게 Jetson 에 도구 둘 (각도 창 · 기록 관문) 을 놓아 두었다. 아래 1 절 순서대로 하면 된다. 2 절은 남은 확인 · 결정
> 상태: 넘김. go2-lx 의 20 분 원자료 확인 예약은 끔

# go2-lx → app-lx 인수인계 (11/20)

먼저 읽기: foothold-go2 `AGENTS.md` 5 · 5a (로봇 명령은 팀장 동의 · 조이스틱) · lab PR #881 가지 `docs/go2-realtest-1119` 의 `inbox/jay/20261117-go2-x-sim-match-checklist-assets/realtest-1119/ACADEMY-1120.md` (측정 한 장).

Jetson 접속: ai-lx01 에서 `nvidia@<tailnet 주소>` (주소는 ai-lx01 의 `~/.mai/jetson-storage/hosts.env` 의 `JETSON=` · 저장소에 두지 않음) · `-o StrictHostKeyChecking=yes` 로 붙음 (기기 이름으로는 호스트 키 미등록이라 안 붙음).

## 1. 바로 할 실험 (학원 · Jetson 터미널 · 로봇은 팀장 조이스틱)

| 순서 | 무엇 | Jetson 명령 | 확인됨 / 미확인 |
|---|---|---|---|
| 1 | **카메라 각도 창** (서서 가만히 · 큰 창 · 몸통 기준 상대각 목표 35 ± 0.15° 초록 · 바닥 기준 절대각 · 몸통 pitch/roll · 끝은 창에서 q) | `bash ~/go2_diag/pitch/pitch_abs.sh enP8p1s0` | Jetson 빌드 · 원격 9 번 띄움 정상 (19:38 상대각 35.37 · 절대 35.26 · 몸통 -0.10 · **RAISE CAMERA 0.37° 벗어남**). 19:3x 팀장 첫 실행은 시작 직후 `free(): invalid next size` 로 한 번 죽음 → 19:38 고침 (5 초 안에 죽으면 세 번까지 다시 띄움 · 끝날 때 SDK 정리 건너뜀). 창이 눈에 보이는지는 원격이라 미확인 |
| 2 | 자로 잰 높이 · 사진 (바닥→몸 중심 · 바닥→D435i 깊이 렌즈) | 줄자 | `realtest-1119/02-ruler-height.md` 비교표의 「자로 잰 값」 칸이 비어 있음 |
| 3 | **기록 540 초** (각도 창 끈 뒤 · 관문 9 개 통과해야 시작 · 통과하면 Enter · 앉아 30 초 → 서서 60 초 → 한 바퀴 돌아 처음 자리 → 서서 60 초 → 앉기) | `bash ~/go2_diag/jetson_storage/academy_1120.sh` | 08:55 읽기만 관문 시험: L2 원래 점 15.5 Hz · IMU 251 · odom 146 · SDK sport · lowstate 들어옴. 깊이 · RGB · `/tf_static` 관문과 실제 기록은 미확인 |
| 3a | 기록 중 끊김 감시 (다른 터미널) | `bash <lab>/realtest-1119/tools/watch_record.sh <기록 폴더> enP8p1s0 540` (Jetson 에 아직 안 놓음 · 놓을지 결정) | ai-lx01 시험만 통과 |
| 4 | 회수 · 대조 | ai-lx01 `tools/jetson_storage/jetson_sync.py sync` (lab 가지 `feat/jetson-storage-1119`) | |

도구 자리 (Jetson): `~/go2_diag/pitch/` (원본 lab `realtest-1119/tools/pitch/`) · 빌드 결과 `~/go2_diag/sim_match_measure/build_imu/relative_pitch_abs` (11/18 `relative_pitch_live` 는 그대로 · `CMakeLists.txt.bak-1120` 백업) · `~/go2_diag/jetson_storage/academy_1120.sh` (lab 가지 `feat/jetson-storage-1119` 의 `academy_1119.sh` 0cbf6b810 사본 + `/utlidar/cloud` · color compressed · `/tf_static` 관문 · SDK 감시 관문 · DDS enP8p1s0 고정. 원래 가지는 안 고침).

주의:
- 각도 창은 D435i 를 직접 열어 기록과 같이 못 씀 (기록 스크립트가 막음).
- `/sportmodestate` 는 Jetson ROS 에 `unitree_go` 메시지 정의가 없어 ros2 bag 에 안 담김 → SDK 감시 `go2_readonly_monitor` 의 `monitor.csv` 로 받음.
- SDK 감시 프로그램은 끝날 때 `free(): invalid next size` 로 죽는다 (각도 창과 같은 오류 · CSV 는 다 쓴 뒤). 앞 보고에서 「11/18 부터 있던 것」 이라고 했으나 **그 시점은 확인하지 않았다 (정정 · 미확인)**. Unitree SDK 쪽으로 보이나 까닭 미확인.

## 2. 남은 확인 (문서에 「Jetson 에서 확인」 으로 적어 둔 것)

| 무엇 | 왜 | 어떻게 | 문서 |
|---|---|---|---|
| 11/19 05:20 · 22:29 본체 토픽이 끊긴 까닭 | 05:20 은 141 초에 L2 · odom · IMU · lowstate 가 한꺼번에 끊김 (로봇은 계속 걸음) · 22:29 는 처음부터 없음 | Jetson `journalctl -k` 의 그 시각 망 줄 (읽기만) · 22:14 USB 랜 연결이 원인 후보 (lab 0cbf6b810 커밋 설명) · enP8p1s0 고정 뒤 3 번 기록에서 재발 여부 | lab `20261119-0520-room-walk-full/map/README.md` |
| IMU-라이다 회전 앞뒤 (A x 앞 · B x 뒤) | SLAM 의 IMU 축 · L2 는 거꾸로 달림 (170°) | Go2 의 `/tf_static` 에 `utlidar_lidar` · `utlidar_imu` 가 나오는지 (`ros2 topic echo --once --qos-durability transient_local /tf_static`) · 또는 제자리 앞으로 몇 걸음 | lab `slam-poc-1119/README.md` 4 절 (PR #897) |
| 같은 자리로 돌아오는 L2 기록으로 SLAM 다시 | 시작 · 끝 자리 차 (11/19 녹화는 고리가 아님) | 1 절 3 번 기록으로 `slam-poc-1119/tools/run_pointlio.sh` · `run_glim.sh` (ai-lx01 `/home/jay/data/slam_poc` 에 환경 있음) | 같은 문서 |
| Point-LIO 를 Jetson 에서 돌려 CPU 몫 | 걷는 중 실시간 자리 | Jetson 에 설치 = 시스템 변경이라 **팀장 동의 뒤** | 같은 문서 |
| 정책 깊이 입력 (정렬 대 원본) | 정렬 깊이는 시뮬 시야의 70 % 만 덮음 (계산) | 30 초 기록 (`realtest-1119/05-depth-input.md` 2 번 줄) | 05 |
| 깊이 안정성 (젠더 A/B/C) | 1 초 정지 · 4 초 끊김 | `realtest-1119/06-depth-stability.md` | 06 |
| Go2 자체 SLAM (`/uslam`) | 앱 지도 | 팀장이 Unitree 앱으로 켬 · `03-uslam.md` | 03 |

## 3. 팀장이 정할 것 (열린 것)

| 무엇 | 지금 |
|---|---|
| foothold-go2 정책 묶음 push · dev PR | 가지 `feature/go2-policy-bundle-jay` (go2 작업 사본 `/home/jay/mai/wt/foothold-go2/go2-lx-1119`) 커밋 c611520 · 5f36956 · **push 안 함** (공개 저장소 정책 올림인데 「진행」 이 lead 전달로만 옴 → 팀장이 직접 「진행」 하면 push). m15500 = 실기 후보 걸음 정책 · AME-2 m27001 = 앱 시뮬용 teacher (실기 아님) · ame2 contract.json 의 Runpod 버킷 경로 칸 뺌 |
| 석헌 PR #905 (ame2-m27001 공개 파일에서 팟 호스트 이름 지움) | **19:3x 기준 OPEN (병합 안 됨)**. 병합되면 위 go2 묶음의 AME-2 사본 · lab PR #883 (앱용 사본) 을 새 원본으로 다시 맞춰야 함 |
| lab PR 병합 | #880 (05:20 지도 · 3D 점) · #881 (측정 절차 · 각도 창 · academy_1120 · 이 인수인계와 같은 가지) · #883 (ame2 앱용 묶음 · #878 은 병합됨) · #897 (SLAM PoC) |
| 상태 번호 2010 | 고장 아님 (보행 상태 번호 · 기록 8 개 대조) · 앱 로봇 탭 경보에서 빼기 (앱 몫) · `/home/jay/mai/tmp/go2-lx/SPORT-STATE-2010-1120.md` |
| 자로 잰 높이 원자료 | ai-lt01 Codex 원자료 PR 은 11/19 11:01~11/20 19:28 동안 오지 않음 |

## 4. 자리 모음

| 것 | 자리 |
|---|---|
| lab 작업 사본 (측정 절차 · 도구) | `/home/jay/mai/wt/foothold-lab/go2-realtest-move-1119` (PR #881) |
| lab 작업 사본 (SLAM PoC) | `/home/jay/mai/wt/foothold-lab/go2-slam-poc-1119` (PR #897) |
| lab 작업 사본 (지도 · 3D) | `/home/jay/mai/wt/foothold-lab/go2-map3d-1119` (PR #880) |
| lab 작업 사본 (ame2 앱용) | `/home/jay/mai/wt/foothold-lab/ame2-m27001-app-1119` (PR #883) |
| SLAM 환경 · 결과 | ai-lx01 `/home/jay/data/slam_poc/` (env · ws_pl · ws_glim · runs) |
| 조사 기록 | `/home/jay/mai/tmp/go2-lx/` (POLICY-BUNDLE-1119 · CHECK-PR878-1119 · SPORT-STATE-2010-1120 · 이 문서) |
| 기록 원본 (ai-lx01) | `/home/jay/data/go2x_raw/` · `/mnt/win-d/mai/data/go2x_raw/` |
