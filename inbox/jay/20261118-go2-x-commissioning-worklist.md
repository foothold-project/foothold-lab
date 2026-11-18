> 분류: 현장 실행 순서 · Go2 X + Jetson Orin NX + D435i + L2
> 작성: 오흥재 · 2026-11-18
> 근거: 20261117 현장 인수 기록 · 20261117 sim-match checklist · 정본 3 contract · foothold-app main README
> 목표: 현재 개체의 하드웨어·센서·통신·안전 상태를 증거로 확정하고, Depth/LiDAR/SLAM을 눈과 데이터로 검증한 뒤 정본 3 ONNX 저수준 정책과 `foothold-app` 실기 연결까지 단계적으로 진행한다.
> 상태: P0 열 안전 관문에서 중단 · Jetson 정상 종료 후 Go2 전원 종료 완료
> 판: v1.0

# Go2 X 실기 commissioning 작업목록

현재 중단점은 순정 Damping→Stand 직후 앞 hip 78/81°C와 전면 적색 점멸이다. **P0 안전 관문 전에는 다시 Stand·카메라 조정·정책 시험을 하지 않는다.**

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
| NoMachine | [~] | Wi-Fi·유선 접속, HDMI를 실행 중 분리해도 정상 | HDMI 없이 부팅하면 640×480. headless 1920×1080 고정 미완료 |
| D435i 정체·USB | [~] | D435i, USB ID `8086:0b3a`, firmware 5.17.0.10, Jetson에서 5000M와 영상 수신 | 새 젠더 비교·장시간 재연결/프레임 drop/CPU·온도 |
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
- [ ] 충분히 냉각한다. 앞 좌·우 hip 외장이 주변 관절과 비슷한 온도가 되기 전에는 재부팅하지 않는다.
- [ ] 업체에 아래 원본 사실을 전달하고 공식 판정을 받는다.
  - FR/FL hip 최고 78/81°C, 약 10분 뒤 65/68°C.
  - 전면 적색 점멸, FR `motor_state[0].reserve[0]=0x04` 지속.
  - BMS SOC 81%, cell 3942~3950 mV, motor lost 0.
  - 첫 Stand lowcmd `kp=1`, 재진입 뒤 `kp=100`, `kd=5`; 앞 hip PD torque proxy 약 ±9.1 Nm.
  - `SportModeState.error_code=1001`은 공식 SDK의 Damp API ID이며 고장 코드로 보지 않음.
- [ ] 다음 전원 투입은 Damping 상태로만 시작하고, 읽기 전용 온도·reserve·LED·lowcmd 감시를 먼저 실행한다.
  - 준비된 source와 실행법: [`20261118-go2-readonly-boot-gate/`](20261118-go2-readonly-boot-gate/README.md). Jetson SDK build와 5초 receive-only smoke run까지 통과했다.
- [ ] 조이스틱의 정확한 Damping→Stand 버튼 순서와 앱/조이스틱 모드 표시를 기록하고 짧은 전환 1회만 수행한다.
- [ ] 아래 중 하나면 즉시 Damping/전원 종료하고 업체 판단 전 중단한다: 적색 점멸, `0x04` 재발, 앞 hip 급상승, 예상하지 않은 고이득 지속, 비정상 자세/소리.

통과 기준: 냉간 부팅에서 fault 표시가 없고, 짧은 순정 Stand 동안 온도가 안정적이며, lowcmd 전환의 의미를 설명할 수 있고, 업체가 계속 사용 가능하다고 확인한다. **단순히 다시 일어섰다는 이유로 통과하지 않는다.**

### P1. 관리 경로와 HDMI 없는 1080p 데스크톱

- [x] SSH key: ai-lt01 → `nvidia@192.168.50.2`, `BatchMode=yes` 성공.
- [x] NoMachine: Wi-Fi와 유선 TCP 4000 연결 성공.
- [ ] Go2/Jetson 재부팅 뒤 Wi-Fi를 끈 ai-lt01에서 `.50.2` SSH와 NoMachine을 다시 확인한다.
- [ ] HDMI 없이 부팅해도 1920×1080 NoMachine이 나오게 한다.
  - 대여 장비의 최소 변경안은 HDMI dummy plug이다.
  - Xorg 가상 화면을 쓸 경우 `/etc/X11/xorg.conf` 원본 백업, SSH rollback 명령, HDMI 복구선을 먼저 준비한다.
  - 적용 뒤 HDMI 분리 상태 재부팅 2회에서 해상도, GDM/GNOME, NoMachine, SSH를 확인한다.
- [ ] NoMachine 무료판 동시 1 physical desktop 제약을 팀 운용 규칙에 남긴다.

통과 기준: HDMI·Wi-Fi 없이 유선 하나로 SSH와 1920×1080 NoMachine에 재접속할 수 있고, 실패 시 SSH/HDMI로 복구할 수 있다.

### P2. D435i 운영 경로 · 눈 확인과 데이터 확인을 같이

- [ ] 기존 젠더와 새 젠더를 동일 포트·케이블에서 각각 시험해 `lsusb -t` 5000M, disconnect 0인 것을 선별한다.
- [ ] 격리 RSUSB build를 재현 가능한 wrapper/service 후보로 정리한다. 시스템 `/opt/ros/humble` librealsense와 firmware는 업체 승인 없이 교체하지 않는다.
- [ ] GUI에서 동시에 눈으로 확인한다.
  - RGB 영상 방향/좌우, depth colormap, aligned depth overlay.
  - 중앙 주점 `(320,242)`과 35° 목표 바닥점 표시.
  - 카메라를 가리거나 가까운 물체를 움직였을 때 depth가 즉시 변하는지.
- [ ] 데이터로 30분 이상 기록한다.
  - depth/color 실제 fps, frame-number gap, 40/100 ms 초과 간격, USB reset/disconnect.
  - gyro/accel rate, NaN/정지 구간, CPU·메모리·Jetson 온도.
  - 원본과 정책용 60×60·10 Hz·0.2~3.0 m clip·무효=max 전처리 결과를 함께 저장.
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
- [ ] 기존 `contracts/v1`을 읽고 실기 adapter가 제공할 최소 계약을 별도 버전으로 정의한다.
  - robot identity/mode, battery, joint/IMU/temperature/fault.
  - RGB/depth, LiDAR cloud, odom/TF, map/pose.
  - command lease, heartbeat, STOP latch, ownership, stale timeout.
  - sim/real source 표시와 절대 혼동 방지.
- [ ] 처음에는 상태·영상·지도 receive-only adapter만 연결한다.
- [ ] 앱 STOP은 UI 응답이 아니라 Jetson gateway의 명령 0/잠금과 로봇의 실제 정지까지 각각 검증한다.
- [ ] 실기 수동 고수준 조종과 저수준 ONNX 제어를 별도 mode로 분리하고 동시에 활성화하지 않는다.
- [ ] SLAM 지도 저장/목록/재열기부터 연결하고 Nav2 자동 이동은 마지막 별도 관문으로 둔다.

통과 기준: 앱 화면이 실기 원본 상태·Depth/LiDAR/지도와 일치하고, 연결 단절/STOP/소유권 시험을 통과하며, sim/real과 고수준/저수준 제어가 명확히 격리된다.

## 3. 다음 전원 투입 때 실제로 할 한 묶음

P0 업체 답변 또는 안전 재개 조건이 충족됐다는 전제에서 다음 한 묶음만 수행한다.

1. Go2를 Damping으로 부팅하고 Stand시키지 않는다.
2. 유선 `.50.2` SSH 접속 후 BMS·12개 모터 온도·reserve·lowcmd 읽기 전용 monitor를 시작한다.
3. 냉간 기준값과 전면 LED를 기록한다. fault가 남으면 종료한다.
4. Wi-Fi를 끈 ai-lt01에서 SSH·NoMachine 직결 재접속을 확인한다.
5. D435i `lsusb -t`와 RSUSB depth/color/IMU를 켜고 GUI로 RGB/depth/alignment를 확인한다.
6. LiDAR receive-only cloud를 RViz에 띄워 교실 형상과 TF를 확인한다.
7. 이때까지 로봇은 Damping이며 어떤 motion command도 보내지 않는다.
8. 모든 read-only 항목이 정상이고 업체가 허용했을 때만, 온도 monitor를 유지한 채 순정 Stand 전환 1회를 별도 시험한다.

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
| v1.0 | 2026-11-18 | 완료·부분 완료·미완료 감사, P0 열 안전부터 P7 foothold-app 실기 연결까지 단계별 관문, 다음 전원 투입 read-only 묶음 작성 |
