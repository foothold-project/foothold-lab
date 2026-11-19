> 분류: 가이드 · 실기 측정 절차 (8 절 3 번)
> 작성: Claude 세션 (오흥재 지시, go2-lx) · 2026-11-19
> 근거: [`GO2X-JETSON-SETUP-1119.md`](../../20261101-app/GO2X-JETSON-SETUP-1119.md) 5 · 7 · 8 절 · Jetson `~/go2_diag/viewer/uslam_record.sh` · 11/19 05:39 시도 (거의 빈 녹화 · 「5 초 안에 lowstate 없음」 · 05:20 녹화 141 초부터 본체 쪽 통신이 끊긴 것이 이어졌을 수 있음, [`../20261119-0520-room-walk-full/map/README.md`](../20261119-0520-room-walk-full/map/README.md))
> 요지: Go2 자체 SLAM 을 팀장이 Unitree 앱으로 켜고, AI 는 받기만 하는 녹화로 지도 · 위치 토픽을 남긴다. 지도 저장 · 다시 불러 위치 찾기까지 한 번
> 상태: 초안 · 측정 안 함 · 11/19 14:5x foothold-go2 PR #14 에서 옮김 (팀장 14:46: 측정 절차 · 시험 도구는 lab)

# 3. Go2 자체 SLAM (`/uslam`)

## 무엇을 · 왜

- 무엇: Go2 본체 SLAM 으로 방 지도를 만들고, 저장하고, 로봇을 다른 곳에 두었다가 다시 불러 위치를 찾는지 본다.
- 왜: 앱 지도 화면 · HiPAN 상위 정책 · Nav2 가 쓸 지도의 바탕. 11/19 새벽 1 차 지도는 Go2 odom 을 그대로 쌓은 것 (고리 닫기 없음 · 벽 두 겹 일부) 이라 SLAM 이 아니다.
- 켜는 길: `/api/slam_operate` 번호를 Jetson 에서 찾지 못했다. 그래서 **팀장이 Unitree 휴대폰 앱의 지도 메뉴로 켠다.** AI 가 API 요청으로 켜지 않는다 (로봇 API 요청 = 팀장 동의 대상).

## 명령

| 순서 | 누가 | 할 것 | 명령 (Jetson) |
|---|---|---|---|
| 1 | AI 또는 사람 | 공통 시작 전 확인 (README) · 배터리 70 % 이상 (05:39 시도는 배터리 바닥에서 실패) | |
| 2 | AI 또는 사람 | 카메라 켜기 (녹화 목록에 카메라 토픽이 있다) | `bash ~/go2_diag/viewer/view_start.sh` |
| 3 | AI 또는 사람 | 지금 `/uslam` 토픽이 0 Hz 인지 (켜기 전 기준) | `source /opt/ros/humble/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; timeout 6 ros2 topic hz /uslam/frontend/odom` |
| 4 | AI 또는 사람 | 감시 + 녹화 켜기 (600 초) | `bash ~/go2_diag/viewer/uslam_record.sh 600` · 출력된 폴더 이름을 적는다 |
| 5 | 팀장 조이스틱 또는 팀장 동의 | 서기 | 조이스틱 Stand |
| 6 | 팀장 | Unitree 앱 지도 메뉴에서 지도 만들기 시작 | 휴대폰 앱 |
| 7 | AI 또는 사람 | SLAM 토픽이 들어오는지 | 3 번 명령을 `/uslam/frontend/odom` · `/uslam/cloud_map` 로 |
| 8 | 팀장 조이스틱 | 방 한 바퀴 → 시작점으로 돌아와 멈춤 (고리 닫기) | 조이스틱 |
| 9 | 팀장 | 앱에서 지도 저장 · 이름 `room-1119` | 휴대폰 앱 |
| 10 | 팀장 조이스틱 | 방 다른 쪽으로 옮겨 멈춤 | 조이스틱 |
| 11 | 팀장 | 앱에서 저장한 지도 불러 위치 찾기 | 휴대폰 앱 |
| 12 | AI 또는 사람 | 위치 토픽이 들어오는지 | 3 번 명령을 `/uslam/localization/odom` 로 |
| 13 | 팀장 조이스틱 또는 팀장 동의 | 앉히기 · 앱에서 SLAM 끄기 | 조이스틱 · 앱 |
| 14 | AI 또는 사람 | 녹화 끝 · 카메라 끄기 · 토픽 표 확인 | `bash ~/go2_diag/viewer/view_stop.sh` · `cat <폴더>/bag/metadata.yaml \| grep -A1 name:` |

녹화가 크다 (깊이 원본 약 18 MB/초 · 600 초면 10 GB 남짓). Jetson 남은 공간을 먼저 `df -h ~` 로 본다. 20 GB 안 되면 `uslam_record.sh` 의 녹화 초를 줄인다 (스크립트는 고치지 않는다).

## 합격 줄

| 항목 | 합격 |
|---|---|
| 켜짐 | `/uslam/frontend/odom` 1 Hz 넘게 들어옴 (켜기 전 0 Hz 와 대비) |
| 지도 | `/uslam/cloud_map` 이 bag 에 1 개 넘게 있음 · 위에서 본 그림에서 벽이 한 겹 (11/19 1 차 지도의 두 겹이 사라짐) |
| 고리 닫기 | 시작점과 돌아온 점의 SLAM 위치 차이 10 cm 안 |
| 다시 위치 찾기 | `/uslam/localization/odom` 이 들어오고, 그 위치를 지도에 찍으면 실제 놓은 자리와 30 cm 안 (팀장 눈 · 사진) |
| 안전 | 감시 기록 내내 관절 60 °C 미만 · reserve nonzero 0 |

불합격이면: 어느 단계에서 멈췄는지 (토픽이 안 나옴 · 지도는 나오나 저장 안 됨 · 위치 못 찾음) 만 적고 8 절 4 번 (녹화로 오프라인 SLAM) 으로 넘긴다.

## 기록 파일 이름

| 파일 | 어디 |
|---|---|
| 녹화 | Jetson `~/go2_diag/records/<YYYYMMDD-HHMM>-room-walk-uslam/` → 이 폴더 아래 `03-uslam/` |
| 앱 화면 | `03_app_map.png` (저장한 지도) · `03_app_reloc.png` (위치 찾은 화면) |
| 메모 | `03_steps.csv`: `순서,시각,한 것,토픽 Hz,메모` |
| 위에서 본 그림 | 회수 뒤 ai-lx01 에서 `/uslam/cloud_map` 마지막 메시지를 그림으로 → `03_uslam_topview.png` |
