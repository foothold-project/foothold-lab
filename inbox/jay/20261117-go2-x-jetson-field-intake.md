# Go2 X · Jetson · D435i 현장 인수 기록

> 분류: 현장
> 작성: 오흥재 · 2026-11-17 17:24
> 근거: 업체 제공 「Unitree Go2 + Intel RealSense D435i 제어기 사용자 매뉴얼」 · 2026-11-17 현장 터미널 출력 · NoMachine 접속 실측 · 정본 3 전달 문서
> 요지: 교체받은 Go2 X 계통의 현재 연결과 원격 접속을 확정값 · 업체 문서값 · 미확인값으로 나누고, 저수준 정책 시험 전 점검 순서를 고정한다
> 상태: 현장 기록 v0.2 · Jetson 모듈과 캐리어 모델 확정
> 판: v0.2

## 0. 이 기록의 범위

이 문서는 2026-11-17 교체받은 Go2 계통에서 직접 확인한 사실을 팀에 전달하기 위한 현장 기록이다. 비밀번호는 기록하지 않는다. 업체 문서에 적힌 값과 현장에서 직접 읽은 값을 섞지 않는다.

근거 표시는 다음과 같다.

- `확인됨`: 사용자가 현장에서 직접 보거나 명령 출력으로 확인한 값
- `업체 문서값`: 업체 제공 매뉴얼에 적혀 있지만 아직 장치에서 다시 읽지 않은 값
- `추정`: 관측 결과에 가장 잘 맞지만 장치에서 아직 확정하지 않은 해석
- `미확인`: 다음 읽기 전용 점검으로 확인할 값

## 1. 현재 확정된 구성

| 항목 | 상태 | 근거와 의미 |
|---|---|---|
| 로봇 명칭 | `Go2 X` `업체 전달값` | 사용자가 업체로부터 전달받은 명칭이다. 본체 라벨과 펌웨어에서는 아직 재확인하지 않았다. |
| Jetson 전원과 부팅 | `확인됨` | NX215 안쪽 HDMI 포트에 모니터를 연결해 Ubuntu 데스크톱이 출력됐다. 보드는 정상적으로 전원 인가와 OS 부팅이 된다. |
| Jetson 모듈과 캐리어 | `NVIDIA Jetson Orin NX 16GB - AVerMedia NX215B` `확인됨` | Jetson에서 `tr -d '\0' </proc/device-tree/model`을 실행해 device tree model 문자열을 직접 확인했다. Orin Nano가 아니다. |
| Jetson 사용자 | `nvidia` `확인됨` | Ubuntu Settings의 사용자와 NoMachine 로그인에서 확인했다. 비밀번호는 저장소에 기록하지 않는다. |
| Go2와 Jetson 내부 LAN | `연결 유지` `확인됨` | Go2와 Jetson 사이의 기존 LAN 케이블은 분리하지 않았다. |
| D435i와 Jetson USB | `연결 유지` `확인됨` | D435i로 추정되는 카메라가 USB A 변환을 거쳐 Jetson에 연결돼 있다. USB 장치 ID와 제품명은 아직 `lsusb`로 재확인하지 않았다. |
| 키보드 | Logitech K855 F2 Bluetooth `확인됨` | K855를 Jetson에 Bluetooth로 연결해 조작했다. F1은 ai-lt01에 배정돼 있다. |
| 원격 데스크톱 | NoMachine 접속 성공 `확인됨` | ai-lt01에서 Jetson Wi-Fi 주소와 NX TCP 4000을 사용해 실제 데스크톱 접속에 성공했다. |
| HDMI 없는 현재 세션 | 정상 `확인됨` | NoMachine 연결 중 HDMI를 분리한 뒤에도 원격 데스크톱이 정상 작동했다. |
| HDMI 없는 재부팅 | `미확인` | 실행 중 HDMI 분리 성공은 콜드부팅이나 재부팅 뒤의 headless 동작까지 증명하지 않는다. 지금은 재부팅 시험을 하지 않는다. |
| USB 마우스 | 분리 가능 `판단` | NoMachine에서 포인터를 제어할 수 있으므로 로컬 USB 마우스는 운용에 필수적이지 않다. 분리 뒤 원격 포인터가 유지되는지만 바로 확인한다. |

외부 모니터와 USB 마우스는 분리해도 현재 원격 운용에는 지장이 없을 것으로 판단한다. 복구용 HDMI 케이블과 K855는 가까이에 둔다. Go2 내부 LAN과 D435i USB는 분리하지 않는다.

## 2. 업체 매뉴얼에서 받은 값

업체 제공 PDF의 SHA-256은 `5733b99ff3fa065cbcab91bff9107f6791fb19ce4c08c9230578b574f6cc1b92`다. 원본 PDF는 저장소에 넣지 않는다.

| 항목 | 업체 문서값 | 현장 재확인 상태 |
|---|---|---|
| Jetson OS | Ubuntu 22.04 LTS · JetPack 6 · L4T R36.4 · aarch64 | `미확인` |
| ROS | ROS 2 Humble Desktop · `/opt/ros/humble` | `미확인` |
| 작업공간 | `~/wego_ws` | `미확인` |
| Go2 SDK | Unitree SDK2 · CycloneDDS 포함 · `/usr/local` | `미확인` |
| Go2 연결 인터페이스 | `enP8p1s0` | `미확인` |
| Jetson의 Go2 내부망 주소 | `192.168.123.99/24` 고정 | Jetson `hostname -I`에서 `.99`가 보인 사실만 `확인됨`. 어느 NIC에 붙었는지는 `미확인` |
| Go2 주소 | `192.168.123.161` | `미확인` |
| D435i USB ID | `8086:0b3a` | `미확인` |
| D435i 매뉴얼 설정 | color 640×480 30 fps · depth 640×480 30 fps · aligned depth · gyro 200 Hz · accel 100 Hz | 설정 파일과 실행 토픽에서 `미확인` |
| 기본 통합 런치 | `ros2 launch wego_teleop wego_teleop.launch.py` | `미실행` |
| 통합 런치 기본 안전값 | `receive_only:=true` | 코드와 실제 런치 인자에서 `미확인` |

매뉴얼의 `enP8p1s0`, `.99`, `.161`은 업체가 구성한 Go2 내부망 값이다. ai-lt01의 USB 랜 인터페이스 이름과 같아야 하는 값이 아니다.

## 3. 현재 네트워크 실측

### 3.1 ai-lt01

| 항목 | 실측값 |
|---|---|
| Wi-Fi | `wlp0s20f3` · `192.168.20.60/23` |
| USB Ethernet | `enx00e04c362511` · RTL8152 10/100 · carrier UP · 100 Mb/s full duplex |
| 시험용 연결 프로필 | `go2-lab` · `192.168.123.51/24` · default route 사용 안 함 · IPv6 끔 |
| `.99`와 `.161` ping | 둘 다 3회 송신, 응답 0 |
| ARP neighbor | `.99 FAILED` · `.161 FAILED` |

물리 링크는 살아 있지만 ai-lt01이 연결된 NX215 외부 Ethernet 포트에서 업체 내부망의 `.99`와 `.161`까지 L2 이웃을 찾지 못했다. 따라서 그 외부 포트가 Go2 내부망에 단순 bridge된 포트는 아니라는 해석이 현재 관측과 맞는다 `추정`. Jetson의 두 NIC 이름과 주소를 읽기 전에는 포트 역할을 확정하지 않는다.

### 3.2 Jetson Wi-Fi와 NoMachine

| 항목 | 실측값 |
|---|---|
| `hostname -I` | `192.168.123.99 192.168.21.103` |
| Wi-Fi 접근 주소 | `192.168.21.103` `확인됨` |
| ai-lt01에서 Wi-Fi ping | 3/3 응답 · 0% loss · RTT 14.762/37.128/59.749 ms |
| NX 서비스 | `nxserver` · `nxnode` · `nxd` enabled · 새 연결 enabled |
| NX 포트 | ai-lt01에서 `192.168.21.103:4000` TCP 연결 성공 |
| Jetson NoMachine | `nomachine 9.8.2-1 arm64` |
| ai-lt01 Player | `nomachine-player 10.2.3-1 amd64` |
| 실제 접속 | `nvidia` 계정으로 physical desktop 접속 성공 |

현재 안정적으로 확인된 관리 경로는 `ai-lt01 Wi-Fi -> 192.168.21.103:4000 -> Jetson NoMachine`이다. 외부 유선 관리 포트의 주소는 아직 정하지 않았다.

현재 설치된 NoMachine 무료판은 active physical desktop connection 한 개만 허용한다. 팀원 여러 명이 각자 Player를 설치해 번갈아 접속할 수는 있지만 동시에 접속할 수는 없다. 대여 장비의 서버 패키지나 라이선스는 업체 승인 없이 바꾸지 않는다.

## 4. 다음 읽기 전용 점검

다음 명령은 NoMachine의 Jetson 터미널에서 한 묶음씩 실행하고 출력을 이 문서에 추가한다. 먼저 장비를 움직이지 않는 식별 명령만 사용한다.

### 4.1 Jetson 모듈과 JetPack

device tree model 확인은 끝났다.

```text
NVIDIA Jetson Orin NX 16GB - AVerMedia NX215B
```

남은 OS와 전력 모드 확인:

```bash
tr '\0' '\n' </proc/device-tree/compatible
cat /etc/nv_tegra_release
free -h
sudo nvpmodel -q --verbose
```

통과 결과: device tree로 확정한 Orin NX 16GB와 NX215B에 이어 L4T, 실제 가용 메모리, 전력 모드를 기록한다.

### 4.2 NIC와 경로

```bash
ip -br link
ip -br addr
ip route
nmcli device status
```

통과 결과: `enP8p1s0`의 실제 존재와 `.99/24` 귀속, 다른 Ethernet 포트의 이름과 주소, Wi-Fi 인터페이스와 `.21.103` 귀속을 기록한다.

### 4.3 D435i와 ROS 환경

```bash
lsusb
source /opt/ros/humble/setup.bash
source ~/wego_ws/install/setup.bash
printenv ROS_DISTRO
ros2 pkg prefix wego_teleop
```

통과 결과: `8086:0b3a`, D435i 제품 식별, Humble, `wego_ws` 설치를 확인한다. 아직 런치를 실행하지 않는다.

## 5. 카메라 실기 정렬 기준

시뮬 정본 [`foothold_s2/sensors/depth_cam_cfg.py`](../../foothold_s2/sensors/depth_cam_cfg.py)의 기준은 다음과 같다.

| 항목 | 시뮬 기준 |
|---|---|
| 장착 위치 | 몸통 base 중심 기준 앞 `0.25 m` · 좌우 `0 m` · 위 `0.12 m` |
| pitch | 아래 `35°` |
| 정책 입력 해상도 | `60×60` |
| 갱신 주기 | `10 Hz` |

실기 카메라는 머리 위 고정 자리에서 각도만 조정할 수 있다. 각도는 35°로 맞추되, 실기 렌즈 중심의 몸통 base 기준 앞·위 거리를 자로 재서 기록해야 한다. 위치가 시뮬과 다르면 깊이 기반 지도가 어긋날 수 있다. 처음 실기 정책 시험은 이 영향을 피하도록 `map_off`를 사용한다.

## 6. 정본 3 정책과 안전 관문

실기에서 추측해 채우면 안 되는 값은 [`start-m15500-app/CONTRACT.md`](20261103-policy-handoff/start-m15500-app/CONTRACT.md)와 [`contract.json`](20261103-policy-handoff/start-m15500-app/contract.json)을 정본으로 쓴다. 관측 순서, 관절 순서, 행동 배율, PD 값, 주기를 기억으로 옮기지 않는다.

| 항목 | 확정 또는 현재 상태 |
|---|---|
| 첫 실기 ONNX | `start-m15500_map_off.onnx` |
| 정책 주기 | 50 Hz |
| 발 접촉 센서 | 정책 입력에 쓰지 않으므로 Go2 X에 값이 없어도 문제가 되지 않음 |
| map_on | 실기 카메라 위치와 depth 전처리를 확인한 뒤 |
| 순정 보행 | 현재 조이스틱으로 연결된 상태 · 비교와 비상 복구 경로로 유지 |
| 저수준 제어 | 아직 실행하지 않음 |

실기 순서는 다음 관문을 넘을 때만 진행한다.

1. 조이스틱 비상 정지와 순정 모드 복구 절차를 먼저 확인한다.
2. 로봇을 매단 상태에서 발이 바닥에 닿지 않게 하고 저수준 관절 목표만 확인한다.
3. 관절 순서, sign, offset, PD, action scale, 50 Hz를 정본 계약과 대조한다.
4. 명령 끊김과 프로세스 종료 때 안전 정지가 되는지 확인한다.
5. 위 관문을 통과한 뒤에만 평지에서 `map_off`를 시험한다.
6. 카메라 위치, 각도, depth 단위와 전처리 parity를 확인한 뒤에만 `map_on`을 검토한다.

업체 매뉴얼의 `/cmd_vel`과 `go2_motion_cmd`는 업체 ROS 드라이버의 순정 고수준 제어 경로다. 정본 3 ONNX가 12개 관절 목표를 내는 저수준 정책 경로와 같은 것이 아니다. 처음 점검에서는 `receive_only:=true`를 유지하고, 두 제어 경로를 동시에 실행하지 않는다.

### 6.1 배터리 저전압과 종료

Unitree Go2 사용자 매뉴얼에는 머리 표시등이 노란색으로 느리게 깜빡이면 저전압 경고이며 10분 안에 자동으로 crouch한다고 적혀 있다. 같은 매뉴얼은 배터리가 한 칸 남으면 운용을 멈추고 로봇을 끈 뒤 충전하라고 안내한다. 전원이 끊길 때 로봇이 서 있으면 크게 넘어져 손상과 안전 위험이 생길 수 있으므로, 전원을 끌 때는 먼저 로봇을 눕히라고 명시한다.

현장 운용 규칙:

1. 자동 crouch를 기다리지 않는다. 배터리가 한 칸이거나 노란색 느린 점멸이면 즉시 시험을 멈춘다.
2. 사람과 물건을 치우고 순정 조이스틱의 익숙한 눕기 또는 damping 동작으로 몸통을 바닥에 안정시킨다. 손과 발을 몸통 아래에 넣지 않는다.
3. Jetson 작업을 저장하고 OS를 정상 종료한 뒤 로봇 전원을 끈다. 로봇 배터리 차단 때 Jetson 전원이 어떻게 종료되는지는 아직 `미확인`이므로 강제 전원 차단에 의존하지 않는다.
4. 완전 방전을 안전 동작 시험으로 사용하지 않는다. BMS에는 과방전 보호가 있지만, 이것이 서 있는 로봇과 Jetson OS의 안전한 종료를 보장한다는 뜻은 아니다.

출처: [Unitree Go2 사용자 매뉴얼](https://marketing.unitree.com/article/en/Go2/User_Manual.html) · [Unitree Go2 배터리와 BMS 보호](https://www.unitree.com/go2/battery/)

## 7. 팀원이 이어서 볼 위치

- 정본 3 전달: [`HANDOFF-START-m15500-CANON3.md`](20261103-policy-handoff/HANDOFF-START-m15500-CANON3.md)
- 앱 전달과 남은 실기 경로: [`APP-HANDOFF-1117.md`](20261103-policy-handoff/APP-HANDOFF-1117.md)
- 시뮬 대 실기 제원: [`docs/research/20260908-go2-spec-sim-vs-real.md`](../../docs/research/20260908-go2-spec-sim-vs-real.md)
- 연속 작업 이슈: [foothold-lab #557](https://github.com/foothold-project/foothold-lab/issues/557)
- NX215 공식 제품 페이지: [AVerMedia NX215](https://www.avermedia.com/professional/product-detail/NX215)
- NoMachine 제품별 연결 제한: [NoMachine FAQ](https://www.nomachine.com/support/faq)

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v0.2 | 2026-11-17 | device tree model 출력으로 NVIDIA Jetson Orin NX 16GB와 AVerMedia NX215B 확정 · 배터리 저전압과 종료 안전 절차 추가 |
| v0.1 | 2026-11-17 | 업체 매뉴얼값, ai-lt01과 Jetson 네트워크 실측, NoMachine 접속, 실행 중 HDMI 분리 성공, 다음 읽기 전용 점검과 저수준 안전 관문 기록 |
