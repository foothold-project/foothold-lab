분류: 실기 설치 기록 (Go2 X Jetson)
작성: Claude 세션 (오흥재 지시, lead-lx)
근거: 팀장 11/19 00:50~04:57 채팅 · Jetson 에서 lead 가 SSH 로 잰 값 · 원장 decisions.tsv 11/19 03:51 · 04:35 줄 · 이슈 #861
요지: 11/19 새벽 Jetson 에 무엇을 누가 설치 · 설정했고, 무엇을 어떻게 확인했는지. 다음 사람 (사람 · agent) 이 같은 상태를 다시 확인하고 이어 가는 데 쓴다
상태: 2026-11-19 05:0x 기준 · 설치 셋 확인 끝 · 방 지도 녹화 중

# Go2 X Jetson 설치 · 확인 기록 (11/19)

이 문서는 「누가 무엇을 했나」 와 「어떻게 확인했나」 를 같이 적는다. 다시 확인하는 명령은 각 절 끝에 둔다. 주소 · 기기 번호 · 비밀번호는 적지 않는다 (공개 저장소 규칙과 같음).

## 0. 한눈에

| 항목 | 누가 | 상태 | 확인 방법 |
|---|---|---|---|
| 직결 랜선 (ai-lx01 ↔ Jetson) | 팀장 (11/19 00:50) | 됨 | `ssh` 직결 주소 · ping |
| SSH 키 (기기마다 따로) | 팀장 · lead | 됨 | 공개키만 Jetson 에 더함 |
| Wi-Fi (집 Trust_YourSelf · 아이폰 핫스팟 · 학원 둘) | 팀장 | 저장됨 · 집 Wi-Fi 에 붙음 | `nmcli -t -f NAME,TYPE con show` |
| 시간대 Asia/Seoul | 팀장 (03:58) | 됨 | `timedatectl` |
| Wi-Fi 무선 다시 켬 | 팀장 (04:2x) | 됨 | `nmcli radio` |
| CycloneDDS (ROS 2 통신 플러그인) | 팀장 sudo · lead 가 패키지 받음 | 됨 | 2 절 |
| Tailscale | 팀장 sudo · 인증 · 키 만료 끔 · 이름 바꿈 | 됨 · tailnet 이름 `go2x-jetson` | 3 절 |
| 표시 화면 (카메라 색 · 정렬 깊이 · L2 점구름 · RViz) | lead | 됨 | 4 절 |
| 방 지도 녹화 (L2 + odom) | lead 가 기록만 켬 · 걷기는 팀장 조이스틱 | 녹화 중 (05:00~05:25) | 5 절 |

## 1. 하지 말 것: `apt --fix-broken install` · `apt upgrade`

- 이 Jetson 은 L4T 커널 · 부트로더 · 도구 다섯이 고정 (hold) 돼 있다: `nvidia-l4t-bootloader` · `nvidia-l4t-kernel` · `nvidia-l4t-kernel-dtbs` · `nvidia-l4t-kernel-headers` · `nvidia-l4t-tools`.
- 버전이 섞여 있다 (커널 · 부트로더 36.4.0 · 나머지 L4T 36.4.7). 그래서 apt 는 「unmet dependencies」 를 띄우며 **어떤 설치도 거부**한다.
- fix-broken 은 이 묶음을 맞추려고 커널 · 부트로더를 건드릴 수 있다 (로봇 컴퓨터가 안 뜰 위험). Unitree 이미지가 일부러 묶어 둔 것으로 보인다 (추정).
- 새 패키지는 **받아서 직접 넣는다**: `apt-get download <패키지>` (sudo 없이) → `sudo dpkg -i <파일>.deb`. 의존 패키지가 빠지면 그것도 같은 방법으로 받는다. 설정은 `sudo dpkg --configure <패키지 이름들>` 로 이름을 적어서 (`-a` 는 쓰지 않는다).

확인: `apt-mark showhold` · `dpkg -l 'nvidia-l4t-*' | awk '/^[a-z]/{print $1,$2,$3}'`

## 2. CycloneDDS (L2 점구름을 받으려고)

- 까닭: Go2 는 ROS 2 통신을 CycloneDDS 로 한다. Jetson 기본 통신 (FastDDS) 으로는 L2 (`/utlidar/cloud`) 가 안 보였다.
- 한 일 (팀장 sudo):
  ```
  mkdir -p ~/debs && cd ~/debs
  apt-get download ros-humble-iceoryx-hoofs ros-humble-iceoryx-posh ros-humble-iceoryx-binding-c ros-humble-cyclonedds ros-humble-rmw-cyclonedds-cpp libacl1-dev libattr1-dev
  sudo dpkg -i libattr1-dev_*.deb libacl1-dev_*.deb ros-humble-iceoryx-*.deb ros-humble-cyclonedds_*.deb ros-humble-rmw-cyclonedds-cpp_*.deb
  ```
  처음에는 `libacl1-dev` 가 빠져 네 개가 「설정 안 됨」 으로 남았고, 둘을 더 받아 넣어 끝났다.
- 쓰는 법: ROS 2 명령 전에 `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`.
- 확인 (lead 04:3x): `ros-humble-cyclonedds 0.10.5` · `ros-humble-rmw-cyclonedds-cpp 1.3.6` 설치됨 · `/utlidar/cloud` 15.4 Hz (좌표틀 `utlidar_lidar`).

다시 확인: `source /opt/ros/humble/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; ros2 topic hz /utlidar/cloud`

## 3. Tailscale (집 ↔ 학원 · 랜선 없이 접속)

- 한 일 (팀장): 설치 스크립트로 저장소 등록 (마지막 apt 설치 단계는 1 절 까닭으로 실패) → `apt-get download tailscale` → `sudo dpkg -i tailscale_*.deb` → `sudo systemctl enable --now tailscaled` → `sudo tailscale up` 이 낸 링크를 ai-lx01 브라우저에서 열어 인증 → 관리 화면에서 키 만료 끔 → tailnet 이름만 `go2x-jetson` 으로 바꿈 (시스템 이름 `tegra-ubuntu` 는 그대로).
- Jetson 에 브라우저는 필요 없다 (인증 링크는 아무 기기에서 연다).
- 확인 (lead 04:3x): `tailscale 1.104.7` · `tailscaled` enabled · active · tailnet 에 ai-lx01 · ai-lt01 · NAS 와 같이 보임 · ai-lx01 에서 tailnet 주소로 SSH 됨 (호스트 키가 직결 주소의 키와 같은 것을 확인한 뒤 등록).

다시 확인: Jetson 에서 `tailscale status` · 다른 기기에서 `ssh nvidia@go2x-jetson` (MagicDNS 를 켠 경우) 또는 tailnet 주소.

## 4. 표시 화면 (Jetson 모니터 · NoMachine)

- 무엇이 뜨나: RViz 한 창에 카메라 색 영상 · 색에 맞춘 깊이 (align_depth) · L2 점구름 (높이 색) · L2 좌표축. 따로 터미널 한 창에 관절 온도 · 배터리 (읽기 전용 감시 출력).
- 시작 · 끄기: `bash ~/go2_diag/viewer/view_start.sh` · `bash ~/go2_diag/viewer/view_stop.sh` (둘 다 CycloneDDS 로 띄움). 설정 `~/go2_diag/viewer/cam.rviz` (옛 판 `cam.rviz.bak-0347` · `cam.rviz.bak-0433`).
- 확인 (lead 04:33 Jetson 화면 캡처): 색 25 Hz · 정렬 깊이 24 Hz · L2 15.4 Hz · RViz 3D 칸에 점구름.
- 깊이 왼쪽 검은 띠는 고장이 아니다 (스테레오 카메라는 왼쪽 끝을 두 눈이 같이 못 봐서 깊이가 원래 비어 있다).
- 정책 입력 깊이를 정렬할지 여부는 따로 정한다 (시뮬 카메라 정의와 맞출 것 · 미확인).

## 5. 방 지도 (L2 로 위에서 본 지도)

- Go2 가 이미 내보내는 것 (CycloneDDS · 04:5x 잼): `/utlidar/cloud_deskewed` 13.6 Hz (좌표틀 `odom` = 움직여도 고정된 바닥 기준) · `/utlidar/robot_odom` 146 Hz. 그래서 걸으면서 녹화만 하면 점구름을 그대로 쌓아 위에서 본 지도가 된다 (SLAM 을 따로 안 깔아도 1 차 지도).
- Unitree 자체 SLAM (`/uslam/*` · `/api/slam_operate`) 도 있으나 켜는 것은 로봇 API 요청이라 팀장 동의 뒤. 지금은 안 켰다 (토픽 0 Hz).
- 녹화 (lead · 읽기 전용 · 로봇에 명령 없음): `bash ~/go2_diag/viewer/walk_record.sh <초>` → `~/go2_diag/records/<시각>-room-walk/` 에 `monitor.csv` (온도 · 배터리) · `bag/` (cloud_deskewed · robot_odom · imu · tf). 약 4.7 MB/초.
- 11/19 05:00 녹화 시작 시 배터리 27 % · 가장 뜨거운 관절 54 °C (RR calf · 서 있는 상태) · reserve 0.
- 지도 만들기 (다음): 녹화를 ai-lx01 로 옮겨 점을 쌓고 높이로 잘라 위에서 본 그림 (바닥 · 벽 · 가구) 으로 그린다.

## 6. 망 바꾸기 (랜선 뺄 때)

- 랜선을 빼도 Jetson 은 Wi-Fi + Tailscale 로 SSH 된다 (04:3x 확인). 로봇 안쪽 망 (Jetson ↔ Go2 본체) 은 다른 선이라 영향 없다.
- NoMachine 은 직결 주소 대신 tailnet 이름 · 주소로 다시 붙는다.
- `Go2_<번호>` Wi-Fi 는 Go2 본체가 내보내는 것 (휴대폰 Unitree 앱용). Jetson 은 붙이지 않는다.
- 아이폰 핫스팟 이름의 따옴표는 굽은 따옴표 (’) 라 명령으로 치면 「없는 이름」 이 된다. 아이콘으로 고르거나 `nmcli dev wifi list` 에서 복사.

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-11-19 | 처음 작성 (CycloneDDS · Tailscale · 표시 화면 · 방 지도 녹화 · 하지 말 것) |
