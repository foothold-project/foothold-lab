> 분류: 현장 실행 순서 · Go2 X + Jetson Orin NX + D435i + L2
> 작성: 오흥재 · 2026-11-18
> 근거: 20261117 현장 인수 기록 · 20261117 sim-match checklist · 정본 3 contract · foothold-app main README
> 목표: 현재 개체의 하드웨어·센서·통신·안전 상태를 증거로 확정하고, Depth/LiDAR/SLAM을 눈과 데이터로 검증한 뒤 정본 3 ONNX 저수준 정책과 `foothold-app` 실기 연결까지 단계적으로 진행한다.
> 상태: 냉각·재부팅 뒤 read-only monitor와 Classic 좌·우 주행에서 열 사건 미재발 · 카메라 35° 유지성 통과 · HDMI 없는 1080p 정상 전원 사이클 2회 통과 · 업체 공식 열 판정과 D435i 1초 reset 원인은 대기 · 11/21 D435i USB 3 끊김은 Jetson 쪽 젠더 자리 흔들림으로 재현, USB 2 로는 23 분 끊김 0 (인수 기록 8.7)
> 판: v1.5

# Go2 X 실기 commissioning 작업목록

과거 순정 Damping→Stand 직후 앞 hip 78/81°C와 전면 적색 점멸이 있었고 업체 공식 판정은 아직 대기 중이다. 이후 냉각·재부팅과 receive-only monitor 아래 순정 Stand/Classic 주행에서는 최고 56°C, `reserve[0]` nonzero 0, errorlist 0으로 재발하지 않았다. 이 결과는 현 운용 표본이지 업체 공식 안전 한계를 대신하지 않는다. **저수준 정책 시험은 P0 공식 관문 전까지 금지한다.**

## 0. 상태 표기

- `[x]`: 현 개체에서 명령 출력·원본 기록·눈 확인 등 직접 증거가 있다.
- `[~]`: 일부는 확인했지만 운영 조건이나 장시간·재부팅·시각 검증이 남았다.
- `[ ]`: 아직 실행하지 않았거나 증거가 없다.
- 각 단계는 바로 위 관문이 통과돼야 다음으로 간다. 시뮬·가짜 데이터·토픽 이름 존재만으로 실기 통과 처리하지 않는다.

## 1. 현재까지의 완료 감사

| 영역 | 상태 | 현재 증거 | 남은 것 |
|---|---:|---|---|
| 개체/컴퓨팅 보드 | [x] | `NVIDIA Jetson Orin NX 16GB - AVerMedia NX215B`, Ubuntu 22.04.5, L4T R36.4.7 | Go2 X 명칭은 업체 전달값이라 본체/펌웨어 식별값이 나오면 보강 |
| 유선 관리망 | [x] | ai-lt01 `192.168.50.1` ↔ Jetson `192.168.50.2`, SSH key·22/tcp·4000/tcp 성공, 자동연결 manual profile | 재부팅 뒤 Wi-Fi 없이 SSH/NoMachine 1회 재확인 |
| 내부망 | [x] | Jetson `enP8p1s0=192.168.123.99/24` ↔ Go2 `192.168.123.161`, 1 Gb/s full duplex | firmware/network reset 뒤 절대 불변을 뜻하지 않음 |
| NoMachine | [~] | NVIDIA custom EDID 적용 뒤 물리 HDMI disconnected 정상 전원 사이클 2회에서 1920×1080@60, GDM/GNOME, NoMachine 통과 | RViz/OpenGL renderer 확인 뒤 완료 |
| D435i 정체·USB | [~] | D435i, USB ID `8086:0b3a`, firmware 5.17.0.10, 현재 조회에서 5000M와 영상 수신 | `5000M`은 순간 link 상태일 뿐. 새 젠더 A/B/C·장시간 재연결/프레임 reset/CPU·온도 비교 필요 |
| D435i 영상 | [~] | depth 640×480 약 30 fps. 최종 Classic 180초 5,365프레임·평균 29.81 fps·무효/범위 밖 11.18% | 약 10초에 DDS/Depth 공통 1초 정지와 frame number 287→0 reset 1회. color/aligned GUI·계단 앞·30분 안정성 필요 |
| D435i IMU | [~] | 격리 RSUSB에서 gyro 약 200 Hz, accel 약 100 Hz; 상대각 3회 기록 | 시스템 기본 V4L2는 HID 실패. 운영 wrapper·장시간 안정성 필요 |
| 카메라 위치 | [x] | 몸 중심 기준 약 `(x,y,z)=(+0.350,0,+0.070) m`, 시뮬보다 10 cm 앞·5 cm 낮음 | 각도 조정 시 x/z 재확인 |
| 카메라 각 | [x] | 최종 체결 직후 35.068°·표준편차 0.004°, Classic 좌·우 ㅁ자 주행 뒤 35.023°·표준편차 0.023°, 전후 -0.045° | 몸통 기준 35°와 이 주행 범위의 브라켓 단기 유지성 통과. 장기 반복·충격 뒤 재확인 |
| Go2 body IMU/관절/BMS | [x] | native DDS와 receive-only ROS 변환으로 값·수신률 확인, 정지/보행 60초 통계 기록 | 순정 Stand 열 사건 원인과 안전 한계 확정 |
| LiDAR 모델·상태 | [x] | L2 운용 판정: cloud 약 62k, 15.35~15.38 Hz, IMU 약 250 Hz, packet loss 0 | 본체 라벨 식별 보강은 선택; PointCloud/TF 시각 검증은 별도 |
| LiDAR 눈 확인 | [ ] | `/utlidar/cloud`와 변환 publish 존재만 확인 | RViz에서 실제 3D 점군·방향·TF·움직임 확인 |
| SLAM | [ ] | `/uslam/*`, `/lio_sam_ros2/mapping/odometry` 토픽 존재만 확인 | 실제 지도 생성·odom/TF·저장·재로딩·localization 전부 필요 |
| ONNX 정본 | [x] | map_off/map_on, contract, parity, test vectors, 관절 순열 확정 | Jetson aarch64 runtime과 실시간 실행기는 없음 |
| 저수준 정책 | [ ] | 아직 어떤 정책/저수준 명령도 송신하지 않음 | offline parity→read-only shadow→매달기→평지 map_off→map_on |
| `foothold-app` 실기 | [ ] | 현재 앱 README도 실 Go2 연결 미구현이라고 명시 | 실기 adapter·상태/센서/지도 계약·command safety gateway 필요 |

## 2. 전체 실행 순서

### P0. 열 사건 안전 관문 · 다른 모든 작업보다 먼저

- [x] Jetson에서 `sudo shutdown -h now` 실행 후 Go2 전원 종료.
- [x] 충분히 냉각한 뒤 재부팅했다. 냉간 `reserve[0]` 12개 모두 0, 시작 최고 온도 47°C를 확인했다.
- [~] 업체에 아래 원본 사실을 문의했다. 공식 판정과 안전 재개 조건은 아직 받지 못했다.
  - FR/FL hip 최고 78/81°C, 약 10분 뒤 65/68°C.
  - 전면 적색 점멸, FR `motor_state[0].reserve[0]=0x04` 지속.
  - BMS SOC 81%, cell 3942~3950 mV, motor lost 0.
  - 첫 Stand lowcmd `kp=1`, 재진입 뒤 `kp=100`, `kd=5`; 앞 hip PD torque proxy 약 ±9.1 Nm.
  - `SportModeState.error_code=1001`은 공식 SDK의 Damp API ID이며 고장 코드로 보지 않음.
- [x] 냉각 뒤 전원 투입에서 읽기 전용 온도·reserve·LED·lowcmd 감시를 먼저 실행했다.
  - 준비된 source와 실행법: [`20261118-go2-readonly-boot-gate/`](20261118-go2-readonly-boot-gate/README.md). Jetson SDK build와 5초 receive-only smoke run까지 통과했다.
- [~] 순정 Stand와 Classic 좌·우 ㅁ자 주행을 monitor 아래 수행했고 최고 온도 56°C, 배터리 74→72%, `reserve[0]` nonzero 0, errorlist 0이었다. 조이스틱의 정확한 버튼 순서와 업체가 설명하는 고이득 전환 의미는 미확정이다.
- [ ] 아래 중 하나면 즉시 Damping/전원 종료하고 업체 판단 전 중단한다: 적색 점멸, `0x04` 재발, 앞 hip 급상승, 예상하지 않은 고이득 지속, 비정상 자세/소리.

통과 기준: 냉간 부팅에서 fault 표시가 없고, 짧은 순정 Stand 동안 온도가 안정적이며, lowcmd 전환의 의미를 설명할 수 있고, 업체가 계속 사용 가능하다고 확인한다. **단순히 다시 일어섰다는 이유로 통과하지 않는다.**

### P1. 관리 경로와 HDMI 없는 1080p 데스크톱

- [x] SSH key: ai-lt01 → `nvidia@192.168.50.2`, `BatchMode=yes` 성공.
- [x] NoMachine: Wi-Fi와 유선 TCP 4000 연결 성공.
- [ ] Go2/Jetson 재부팅 뒤 Wi-Fi를 끈 ai-lt01에서 `.50.2` SSH와 NoMachine을 다시 확인한다.
- [x] HDMI 없이 부팅해도 1920×1080 NoMachine이 나오게 한다.
  - 원인은 HDMI 없는 부팅에서 NVIDIA Xorg가 `mode "NULL"`/640×480으로 시작하고, NoMachine이 그 물리 desktop을 공유하는 것이다. HDMI 연결 부팅 뒤 분리하면 같은 부팅의 1920×1080은 유지된다.
  - NVIDIA custom EDID 방식의 설치기·최초 백업 보존·rollback·단위시험을 [`20261118-go2-headless-nvidia/`](20261118-go2-headless-nvidia/README.md)에 준비했다. 기존 dummy driver 설정은 RViz/OpenGL 경로 때문에 활성화하지 않는다.
  - 적용 뒤 HDMI 분리 상태 재부팅 2회에서 해상도, GDM/GNOME, NoMachine, SSH를 확인한다.
  - [x] 2026-11-18 첫 재부팅: physical DRM HDMI `disconnected`, Xorg custom EDID 1920×1080@60, GDM/GNOME X11, NoMachine service와 사용자 화면 통과.
  - [x] 2026-11-18 두 번째 정상 전원 사이클: physical HDMI `disconnected`, XRandR 1920×1080@60, GDM과 NoMachine active. CustomEDID를 다시 읽고 NVIDIA Xorg mode를 설정했다.
- [ ] NoMachine 무료판 동시 1 physical desktop 제약을 팀 운용 규칙에 남긴다.

통과 기준: HDMI·Wi-Fi 없이 유선 하나로 SSH와 1920×1080 NoMachine에 재접속할 수 있고, 실패 시 SSH/HDMI로 복구할 수 있다.

### P2. D435i 운영 경로 · 눈 확인과 데이터 확인을 같이

- [ ] 기존 젠더와 새 젠더 2개를 A/B/C로 표시하고 동일 USB-A 포트·동일 C-to-C 케이블에서 각각 시험한다.
  - 각 후보를 5회 재연결하고 매회 `lsusb -t`의 `5000M`과 동일 device identity를 확인한다.
  - 후보당 5분 depth+color+IMU를 수신하면서 kernel USB disconnect/reset, librealsense notification, frame reset을 센다.
  - 한 번이라도 `480M`, disconnect 또는 reset이 재현되면 운영 젠더에서 제외한다. 브라켓 나사는 건드리지 않는다.
  - [x] 2026-11-21 새 젠더 (모비큐 EM-ATCP2P) · Jetson 쪽 흔들기 두 번 모두 `-71` · 45 ~ 55 초 끊김 · `480M` 재현 → USB 3 운영에서 제외. 카메라 쪽 흔들기는 0 회. [인수 기록 8.7](20261117-go2-x-jetson-field-intake.md)
- [ ] 2026-11-21 학원 · 업체 USB 2 젠더로 바꿔 다시 잰다 (팀장 02:12 승인).
  - 흔들기 시험: Jetson 쪽 젠더 30 초 · 카메라 쪽 30 초 · 커널 `-71` · disconnect · 0 장 구간을 센다.
  - `rs.log` 에 `Device USB type: 2.1` 과 깊이 · 색 `640x480 · 30` 이 열렸는지 확인한다.
  - 걷기 녹화 (ros2 bag) 로 깊이 · 색 실제 Hz · 0.2 초 넘는 빈틈을 센다. 비교 기준은 11/20 USB 2 구간 깊이 29.1 Hz · 색 30.0 Hz.
  - 지연: 카메라 하드웨어 시각과 Jetson 받은 시각의 차이를 USB 2 · USB 3 각각 잰다.
  - 카메라 IMU 를 깊이 · 색과 함께 켜서 gyro · accel Hz 와 깊이 Hz 가 함께 버티는지 본다 (격리 RSUSB 경로).
  - 정책 입력 명세 (해상도 · 주기 · 허용 지연 · 끊김 견딤 · IMU 사용 여부) 를 lead 답과 대조한다 (11/21 02:16 질문).
  - USB 2 가 모자라면 소프트웨어로 USB 3 만 막는 길을 sudo 로 시험한다 (이 커널은 포트별 `disable` 없음 · 같은 허브에 외부 LAN).
- [ ] 격리 RSUSB build를 재현 가능한 wrapper/service 후보로 정리한다. 시스템 `/opt/ros/humble` librealsense와 firmware는 업체 승인 없이 교체하지 않는다.
- [ ] GUI에서 동시에 눈으로 확인한다.
  - RGB 영상 방향/좌우, depth colormap, aligned depth overlay.
  - 중앙 주점 `(320,242)`과 35° 목표 바닥점 표시.
  - 카메라를 가리거나 가까운 물체를 움직였을 때 depth가 즉시 변하는지.
- [ ] 데이터로 30분 이상 기록한다.
  - depth/color 실제 fps, forward frame gap뿐 아니라 frame number 감소/reset, 40/100/500 ms 초과 간격, USB reset/disconnect.
  - gyro/accel rate, NaN/정지 구간, CPU·메모리·Jetson 온도.
  - 원본과 정책용 60×60·10 Hz·0.2~3.0 m clip·무효=max 전처리 결과를 함께 저장.
- [ ] 정책용 전처리를 별도 정본 구현으로 만든다. 현재 Jetson APP의 depth JPEG 변환은 이 전처리가 아니다.
  - 실측 640×480 intrinsics에서 시뮬 60×60 `fx=55.9`, `fy=54.1`에 맞도록 약 0.1444배 축소한 뒤 가운데 60×60 crop하는 후보를 정확한 반올림·보간법까지 고정한다.
  - 30 Hz 원본에서 device timestamp를 기준으로 10 Hz frame을 선택하고, 0.1초 관측 지연·0.2~3.0 m clip·0/무효=max 규칙을 contract와 함께 검증한다.
  - 원본, resize 중간판, crop 60×60, 정규화 입력을 같은 frame number/timestamp로 저장해 시뮬 재투영과 픽셀 단위 대조한다.
- [ ] 평지뿐 아니라 계단 앞에서 zero/범위 밖 비율과 가까운 단차 표현을 저장한다.
- [x] D435i↔Go2 상대각 실시간 도구로 몸통 기준 35°를 맞추고 브라켓을 재체결했다.
  - [x] 최종 체결 직후 독립 3회 평균 35.068°·표준편차 0.004°.
  - [x] Classic 좌·우 ㅁ자 주행 뒤 3회 평균 35.023°·표준편차 0.023°, 전후 변화 -0.045°.
  - [ ] 장기 반복·충격 뒤 witness mark와 상대각을 재확인하고 몸 기준 x/y/z 정밀값을 갱신한다.

통과 기준: 선택한 물리 연결과 wrapper에서 영상+IMU가 장시간 안정적이고, 사람이 보는 GUI와 저장 통계가 일치하며, 실측 extrinsic/intrinsics/preprocess가 정본 문서에 고정된다.

### P3. L2 LiDAR PointCloud 시각 검증

- [x] native SDK2 receive-only `LidarState`에서 error 0, 약 62k cloud, packet loss 0으로 L2 운용 판정.
- [ ] publisher를 추가하지 않는 receive-only 경로로 PointCloud2를 만든다. 기존 업체 driver를 쓸 때 `receive_only=true`, command gate off를 명시한다.
- [ ] RViz에서 `/utlidar/cloud` 또는 검증된 변환 cloud를 표시한다.
- [ ] 아래를 눈과 수치로 확인한다.
  - 로봇 정면/좌우/바닥/벽 방향이 실제와 같은지.
  - fixed frame과 LiDAR TF가 뒤집히거나 90/180° 틀어지지 않았는지.
  - 사람이 로봇 주변을 걸을 때 점군이 맞는 방향으로 움직이는지.
  - 10분간 cloud rate, point count, packet loss, timestamp 단조성.
- [ ] RViz 스크린샷과 rosbag/원본 표본을 보관한다. serial/password는 제외한다.

통과 기준: 실제 교실 형상이 올바른 좌표계의 3D 점군으로 보이고, 수치 rate/point count가 L2 상태값과 일치한다.

### P4. SLAM·지도 생성·재사용

- [ ] `/uslam/*`와 `/lio_sam_ros2/mapping/odometry`의 실제 publisher, rate, QoS, frame_id, TF tree를 기록한다. 토픽 이름만으로 실행 중이라 판정하지 않는다.
- [ ] P0 통과 뒤 순정 Classic 저속으로 작은 폐곡선을 한 바퀴 주행하며 RViz에서 점군·odom·trajectory·map을 동시에 본다.
- [ ] 같은 장소로 돌아왔을 때 loop closure/지도 겹침/높이 drift를 확인한다.
- [ ] 지도를 명시적 파일로 저장하고 SHA-256, frame, 해상도, 원점을 기록한다.
- [ ] 프로세스 재시작 뒤 저장 지도를 다시 열어 localization 또는 이어 매핑이 가능한지 시험한다.
- [ ] 지도 저장/재로딩 실패, TF 끊김, 시간이 역행할 때 로봇 제어와 독립적으로 안전 중단되는지 확인한다.

통과 기준: 한 회의 화면이 아니라 저장된 지도 원물, 재시작 뒤 재사용, pose/TF 연속성까지 재현된다.

### P5. ONNX 실행기를 먼저 움직이지 않는 상태로 검증

- [x] 정본: [`start-m15500-app`](https://github.com/foothold-project/foothold-lab/tree/main/inbox/jay/20261103-policy-handoff/start-m15500-app), `CONTRACT.md`, `contract.json`, `parity.json`, test vectors.
- [ ] Jetson aarch64에서 사용할 ONNX Runtime 또는 TensorRT 판을 OS/JetPack 호환성 기준으로 선택한다. JetPack 전체를 임의 설치하지 않는다.
- [ ] 저장된 test vector로 map_off/map_on offline inference를 실행해 정본 출력과 허용오차를 통과한다.
- [ ] 50 Hz observation pipeline을 **read-only shadow mode**로 실행한다.
  - 45칸 관측 순서, SDK→Isaac 관절 순열 `[3,0,9,6,4,1,10,7,5,2,11,8]`.
  - gravity/ang_vel/q/dq/이전 action, 단위·sign·default pose.
  - latency, deadline miss, stale state, NaN/Inf, inference p50/p95/max.
  - map_off 출력은 계산만 하고 `/lowcmd`에는 보내지 않는다.
- [ ] watchdog을 먼저 구현하고 고의로 state/inference/process를 끊어 안전 상태 전이를 검증한다.
- [ ] 순정 고수준 controller와 저수준 publisher가 동시에 동작하지 않도록 단일 소유권/lock과 시작·종료 순서를 만든다.

통과 기준: 동일 test vector parity, 50 Hz deadline, stale/NaN/watchdog fault injection, publisher 0인 shadow log가 모두 통과한다.

### P6. 저수준 정책 · 매달기부터 map_off, 마지막에 map_on

- [ ] P0 열 사건이 공식적으로 해소되고, 조이스틱 E-stop/복구 동작을 실제로 확인한다.
- [ ] 로봇을 안전하게 매달아 네 발이 바닥에 닿지 않게 한다. 2인 운용과 물리 전원 차단 담당을 둔다.
- [ ] 모터별 sign/order/offset을 한 관절씩 작은 범위에서 검증한다.
- [ ] contract의 kp/kd/action scale/rate를 그대로 쓰되, 시작 시 현재 관절에서 부드럽게 blend하고 온도·토크·position·velocity 한계를 둔다.
- [ ] 프로세스 kill, LAN 단절, stale state, inference hang, 조이스틱 STOP 각각에서 명령이 안전하게 해제되는지 시험한다.
- [ ] 매달기 관문 뒤 평지·넓은 공간·`start-m15500_map_off.onnx`로 짧게 시작한다.
- [ ] map_off의 정지·저속 직진·정지 복구를 통과한 뒤에만 실측 depth pipeline을 연결한 map_on을 검토한다.
- [ ] map_on 전에 카메라 위치 `(0.35,0,0.07)`과 상대 pitch, intrinsics/dropout/latency 차이를 시뮬에 반영하거나 검증된 reprojection/fine-tune을 사용한다.

통과 기준: 매달기 fault injection과 평지 map_off 안전 로그가 먼저다. “정책이 한 번 걸었다”는 map_on 또는 앱 연결 통과가 아니다.

### P7. `foothold-app`에서 시뮬·실기 공통 제어

- [x] 현재 [`foothold-app`](https://github.com/foothold-project/foothold-app)은 시뮬 연결 화면/서버가 있지만 README가 실 Go2 연결과 SLAM/Nav2를 미구현으로 명시한다.
- [x] 2026-11-18 팀원 설치 뒤 읽기 전용 감사: 사용자 venv r4, 중단된 r5, enable된 user systemd service를 확인했다. 과거 r4는 고수준 `StopMove`를 호출했지만 정본 3 정책·저수준 ONNX는 설치되지 않았다. [원시 감사](20261117-go2-x-sim-match-checklist-assets/20261118-app-baseline-audit/README.md)
- [ ] 자동실행 service를 측정 기간 비활성화하고, APP의 조이스틱·순정 Sport SDK·향후 저수준 정책 간 command ownership을 확정한다.
- [ ] 기존 `contracts/v1`을 읽고 실기 adapter가 제공할 최소 계약을 별도 버전으로 정의한다.
  - robot identity/mode, battery, joint/IMU/temperature/fault.
  - RGB/depth, LiDAR cloud, odom/TF, map/pose.
  - command lease, heartbeat, STOP latch, ownership, stale timeout.
  - sim/real source 표시와 절대 혼동 방지.
- [ ] 처음에는 상태·영상·지도 receive-only adapter만 연결한다.
- [ ] APP의 D435i 경로에 원본 depth 메타데이터와 검증된 정책 전처리 결과를 추가한다. 화면용 색상 JPEG만으로 map_on 정책 입력을 대신하지 않는다.
- [ ] APP에서 `map_off`/`map_on`, 순정 고수준 Sport, 저수준 정책을 서로 다른 명시적 mode와 ownership lease로 분리하고 현재 owner를 UI와 Jetson log에 모두 표시한다.
- [ ] 앱 STOP은 UI 응답이 아니라 Jetson gateway의 명령 0/잠금과 로봇의 실제 정지까지 각각 검증한다.
- [ ] 실기 수동 고수준 조종과 저수준 ONNX 제어를 별도 mode로 분리하고 동시에 활성화하지 않는다.
- [ ] SLAM 지도 저장/목록/재열기부터 연결하고 Nav2 자동 이동은 마지막 별도 관문으로 둔다.

통과 기준: 앱 화면이 실기 원본 상태·Depth/LiDAR/지도와 일치하고, 연결 단절/STOP/소유권 시험을 통과하며, sim/real과 고수준/저수준 제어가 명확히 격리된다.

## 3. 현재 중단점에서 이어서 할 실제 순서

### 우선순위 0 · 현재 기준선과 command ownership 고정

1. Go2는 사용자가 바꾸기 전까지 순정 앉기 상태를 유지한다. 현재 failed/no process인 APP service와 포트 9539를 재확인한다.
2. 팀원에게 r5 설치 중단 원인, 자동실행 의도, APP가 호출한 `StopMove`, 조이스틱과의 ownership 설계를 확인한다.
3. 읽기 전용 측정 기간에는 service를 비활성화할지 사용자·팀원 합의로 결정한다. 현재 상태에서는 재부팅·수동 start·r5 복구가 없으면 service가 스스로 살아나 측정을 방해하지 않는다.
4. P0 열 사건 업체 판정 전에는 저수준 명령·정책 송신·새 APP 제어 시험을 하지 않는다.

### 원시자료 보존 규칙

1. Jetson `/home/nvidia/go2_diag/records/`는 전원이 켜진 동안의 **임시 수집·복구 사본**이다. 팀 공유 정본이 아니다.
2. 각 측정이 끝나면 같은 작업 단위 안에서 원본 CSV/NPY/NPZ·console log·summary·실행 명령을 ai-lt01의 `inbox/jay/20261117-go2-x-sim-match-checklist-assets/<측정명>/`으로 회수한다.
3. 회수 뒤 Jetson 원본과 ai-lt01 사본의 SHA-256을 대조하고, 비밀번호·token·개인키·장치 serial이 없는지 검사한다. 큰 파일은 Git LFS 여부를 먼저 확인한다.
4. 검증된 파일과 README를 PR로 main에 병합한다. 다른 Ubuntu 장비 ai-lx01은 `git pull`과 필요 시 `git lfs pull`로 받는다.
5. Git 반영 전에는 Jetson 원본을 지우지 않는다. Git 반영 뒤 삭제도 별도 승인 없이는 하지 않는다.

### 우선순위 1 · 시뮬 재투영에 직접 필요한 실측

1. receive-only 온도·reserve·lowcmd 감시를 먼저 실행하고, 사용자가 순정 조이스틱으로 한 번만 Stand한다.
2. 동일 Stand에서 카메라-몸통 상대각을 독립 5초씩 3회 재측정해 기존 35.068°/35.023°와 비교한다. 앉은 자세 35.225°는 drift 판정에 쓰지 않는다.
3. Stand와 Classic에서 `SportModeState.position[2]` 등 SDK base 높이의 평균·표준편차를 기록하고, 바닥→몸 중심 실측 및 `카메라 높이 ≈ 몸 높이+0.07 m`와 대조한다.
4. 카메라 `(x,y,z)≈(0.35,0,0.07)m`의 원점을 1 cm 단위로 재정의한다. 몸 중심이 IMU인지 `base_link`인지, depth optical origin이 렌즈 전면인지 센서 내부 원점인지 명시한다.
5. 640×480 intrinsics와 depth scale은 재확인 완료. 정확한 640×480→약 0.1444배 resize→중앙 60×60 crop 후보를 코드·보간·반올림·무효값 규칙까지 고정하고 시뮬과 픽셀 parity를 본다.

### 우선순위 2 · D435i 물리 연결과 운영 경로 선별

1. 기존 젠더와 가져온 새 C-to-A 젠더를 A/B/C로 표시한다. 동일 Jetson 포트·동일 C-to-C 케이블에서 후보별 5회 재연결과 5분 depth/color/IMU 시험을 한다.
2. 매 연결마다 `5000M`을 확인한다. 한 번이라도 `480M`, disconnect, frame reset이 나오면 운영 후보에서 제외한다.
3. 선택 젠더로 RGB, depth colormap, aligned overlay, 중앙 주점과 영상 방향을 GUI에서 확인한다.
4. 새 젠더를 샀다는 사실이나 한 번의 `5000M`만으로 통과 처리하지 않는다. 아래 우선순위 3의 정본 원시자료는 이 단계에서 선택한 운영 경로로 수집한다.

### 우선순위 3 · 시간·무효 깊이·정적 장면·장시간 원시자료

1. depth frame number, device timestamp, timestamp domain, host 수신 monotonic/realtime timestamp를 함께 기록해 지연·jitter 분포와 30→10 Hz 선택 기준을 정한다.
2. 선택 젠더 경로에서 Depth와 DDS state age를 30분 동시 기록하고 CPU·메모리·Jetson 온도, USB reset/disconnect를 함께 센다. 기존 frame `287→0` 약 1초 사건이 재현되면 전후 30초 원시 구간을 분리한다.
3. 640×480과 정책 후보 60×60에서 무효/0.2~3.0 m 밖 픽셀의 누적 히트맵을 만든다.
4. 순정 Stand로 (a) 평지, (b) 높이를 잰 턱, (c) 계단 첫 단 0.5 m·1.0 m에서 원본 depth를 각각 10초 저장하고 실제 높이·거리를 함께 기록한다.
5. Go2 body IMU 갱신률·callback age와 D435i accel timestamp를 기록해 projected gravity와 카메라 IMU의 시간 어긋남을 추정한다.

### 우선순위 4 · LiDAR·SLAM·APP·정책

1. L2 PointCloud/TF를 RViz에서 실제 교실과 대조하고 10분 rate/point count/packet loss/timestamp를 기록한다.
2. 순정 Classic 저속 폐곡선으로 SLAM 지도·odom·TF·loop closure를 확인하고 저장·재로딩한다.
3. APP receive-only adapter에 body/joint/BMS/fault, RGB/depth, L2 cloud, odom/TF/map을 연결한다. 화면용 JPEG와 정책용 depth tensor를 분리한다.
4. Jetson ONNX runtime을 고른 뒤 정본 test vector offline parity→50 Hz publisher 없는 shadow mode→watchdog fault injection 순서로 진행한다.
5. 업체 열 안전 판정·조이스틱 E-stop·2인 매달기 관문 뒤에만 저수준 관절 확인→평지 `map_off`를 시험한다. 실측 전처리와 재투영/fine-tune이 검증된 뒤에만 `map_on`을 검토한다.

## 4. 정본과 증거 위치

- [현장 인수 기록](https://github.com/foothold-project/foothold-lab/blob/main/inbox/jay/20261117-go2-x-jetson-field-intake.md)
- [시뮬 대 실기 실측 체크리스트](https://github.com/foothold-project/foothold-lab/blob/main/inbox/jay/20261117-go2-x-sim-match-checklist.md)
- [Go2 제원·시뮬 대 실기](https://github.com/foothold-project/foothold-lab/blob/main/docs/research/20260908-go2-spec-sim-vs-real.md)
- [정본 3 정책 bundle](https://github.com/foothold-project/foothold-lab/tree/main/inbox/jay/20261103-policy-handoff/start-m15500-app)
- [정본 3 전달 문서](https://github.com/foothold-project/foothold-lab/blob/main/inbox/jay/20261103-policy-handoff/HANDOFF-START-m15500-CANON3.md)
- [foothold-app](https://github.com/foothold-project/foothold-app)
- [연속 작업 Issue #557](https://github.com/foothold-project/foothold-lab/issues/557)

비밀번호, 개인키, 장치 serial은 이 작업목록에 기록하지 않는다. 각 통과 판정에는 날짜·명령 또는 실행기 판·원본 파일·요약 통계를 함께 남긴다.

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.5 | 2026-11-21 | app-lx: P2 에 새 젠더 흔들기 시험 결과 (USB 3 운영 제외) 와 11/21 학원 USB 2 젠더 재측정 항목 (흔들기 · 걷기 녹화 · 지연 · 카메라 IMU · 정책 입력 대조) 추가 |
| v1.4 | 2026-11-18 | Jetson은 임시 수집·복구 사본으로만 사용하고 매 측정 뒤 ai-lt01 Git assets로 회수·SHA-256/비밀정보 검사·main 병합하는 원시자료 보존 규칙 추가 |
| v1.3 | 2026-11-18 | 짧은 Stand 기하 측정 뒤 젠더 A/B/C 운영 경로를 먼저 선별하고, 30분 timestamp·무효 히트맵·평지/턱/계단 정본 원시자료는 선택 젠더로 수집하도록 현장 순서 수정 |
| v1.2 | 2026-11-18 | 팀원 APP 자동실행의 현재/잠재 영향 분리 · `5000M` 순간 협상과 젠더 안정성 통과 구분 · 시뮬 lead 실측, timestamp/무효 depth/정적 장면, A/B/C, LiDAR/SLAM/APP/정책을 우선순위 0~4로 재정렬 · 정책용 60×60 전처리를 APP 필수 후속으로 명시 |
| v1.1 | 2026-11-18 | 냉각 뒤 Classic 주행 안전 표본과 카메라 35° 유지성 반영 · HDMI 없는 부팅 root cause/custom EDID 적용·rollback·첫 재부팅 통과 · C-to-A A/B/C 선별과 frame reset 계수 · 현재 후속 순서 갱신 |
| v1.0 | 2026-11-18 | 완료·부분 완료·미완료 감사, P0 열 안전부터 P7 foothold-app 실기 연결까지 단계별 관문, 다음 전원 투입 read-only 묶음 작성 |
