# Go2 X · Jetson · D435i 현장 인수 기록

> 분류: 현장
> 작성: 오흥재 · 2026-11-17 17:24
> 근거: 업체 제공 「Unitree Go2 + Intel RealSense D435i 제어기 사용자 매뉴얼」 · 2026-11-17 현장 터미널 출력 · NoMachine 접속 실측 · 정본 3 전달 문서
> 요지: 교체받은 Go2 X 계통의 현재 연결과 원격 접속을 확정값 · 업체 문서값 · 미확인값으로 나누고, 저수준 정책 시험 전 점검 순서를 고정한다
> 상태: 현장 기록 v0.16 · D435i↔Go2 상대각 35° 유지성 통과 · NVIDIA custom EDID headless 1080p 실제 적용과 HDMI 없는 재부팅 1회 통과 · 11/20 새 젠더에서도 걷기 시작 때 D435i USB 끊김 45 초 (8 절) · 11/21 흔들기 시험으로 Jetson 쪽 젠더 자리에서 재현, 카메라 쪽은 0 회 · USB 2 로는 23 분 끊김 0 (8.7)
> 판: v0.17

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
| D435i와 Jetson USB | `Intel RealSense D435i` `확인됨` | USB ID `8086:0b3a`, firmware `5.17.0.10`을 확인했다. 2026-11-17 재부팅 뒤 현재 장착 경로는 USB `3.20`, `5000M`으로 열거됐고 영상 스트림도 수신했다. 과거 `480M` 및 젠더 반복 disconnect와 결과가 달라 장시간 재검증이 남았다. |
| 키보드 | Logitech K855 F2 Bluetooth `확인됨` | K855를 Jetson에 Bluetooth로 연결해 조작했다. F1은 ai-lt01에 배정돼 있다. |
| 원격 데스크톱 | NoMachine 접속 성공 `확인됨` | ai-lt01에서 Jetson Wi-Fi 주소와 NX TCP 4000을 사용해 실제 데스크톱 접속에 성공했다. |
| HDMI 없는 현재 세션 | 정상 `확인됨` | NoMachine 연결 중 HDMI를 분리한 뒤에도 원격 데스크톱이 정상 작동했다. |
| HDMI 없는 재부팅 | `640×480 fallback 확인됨` | HDMI를 뺀 상태로 재부팅하면 Xorg가 `640×480`만 만들고 NoMachine에는 NVIDIA 배경 일부가 확대돼 보였다. 같은 HDMI 모니터를 다시 연결하자 즉시 `1920×1080@60`으로 복구됐다. |
| USB 마우스 | 분리 가능 `판단` | NoMachine에서 포인터를 제어할 수 있으므로 로컬 USB 마우스는 운용에 필수적이지 않다. 분리 뒤 원격 포인터가 유지되는지만 바로 확인한다. |

외부 모니터와 USB 마우스는 분리해도 현재 원격 운용에는 지장이 없을 것으로 판단한다. 복구용 HDMI 케이블과 K855는 가까이에 둔다. Go2 내부 LAN과 D435i USB는 분리하지 않는다.

## 2. 업체 매뉴얼에서 받은 값

업체 제공 PDF의 SHA-256은 `5733b99ff3fa065cbcab91bff9107f6791fb19ce4c08c9230578b574f6cc1b92`다. 원본 PDF는 저장소에 넣지 않는다.

| 항목 | 업체 문서값 | 현장 재확인 상태 |
|---|---|---|
| Jetson OS | Ubuntu 22.04 LTS · JetPack 6 · L4T R36.4 · aarch64 | Ubuntu `22.04.5`, L4T `R36.4.7`, aarch64 `확인됨`. `nvidia-jetpack` metapackage는 미설치이고 apt candidate는 `6.2.1+b38`이다. |
| ROS | ROS 2 Humble Desktop · `/opt/ros/humble` | `ROS_DISTRO=humble`, `/opt/ros/humble` `확인됨` |
| 작업공간 | `~/wego_ws` | `/home/nvidia/wego_ws` 존재 `확인됨` |
| Go2 SDK | Unitree SDK2 · CycloneDDS 포함 · `/usr/local` | `/opt/unitree_sdk2`와 `/usr/local` 설치 `확인됨`. SDK 저장소 HEAD는 `aaf69cb56c9d5ed63d8b284008ec3a8ab999bec1`이다. |
| Go2 연결 인터페이스 | `enP8p1s0` | 인터페이스 UP · `192.168.123.99/24` `확인됨` |
| Jetson의 Go2 내부망 주소 | `192.168.123.99/24` 고정 | `enP8p1s0` 귀속과 route `192.168.123.0/24` `확인됨` |
| Go2 주소 | `192.168.123.161` | Jetson `enP8p1s0`에서 3/3 ping, 0% loss, 약 0.22 ms 및 ARP neighbor 수신 `확인됨` |
| D435i USB ID | `8086:0b3a` | 제품명 Intel RealSense Depth Camera 435i와 함께 `확인됨` |
| D435i 매뉴얼 설정 | color 640×480 30 fps · depth 640×480 30 fps · aligned depth · gyro 200 Hz · accel 100 Hz | 격리 RSUSB backend에서 depth/color 약 28~30 Hz, gyro 약 200 Hz, accel 약 100 Hz 동시 수신 `확인됨`. 시스템 기본 V4L2 backend의 HID 실패는 남아 있어 운영 wrapper·장시간 검증 필요 |
| 기본 통합 런치 | `ros2 launch wego_teleop wego_teleop.launch.py` | `미실행` |
| 통합 런치 기본 안전값 | `receive_only:=true` | `wego_teleop.launch.py` 기본값과 `go2_driver` 송신 차단 코드를 확인했고, 명시적 receive-only 단독 실행으로 상태만 수신했다 `확인됨` |

매뉴얼의 `enP8p1s0`, `.99`, `.161`은 업체가 구성한 Go2 내부망 값이다. ai-lt01의 USB 랜 인터페이스 이름과 같아야 하는 값이 아니다.

## 3. 현재 네트워크 실측

### 3.1 ai-lt01

| 항목 | 실측값 |
|---|---|
| Wi-Fi | `wlp0s20f3` · `192.168.20.60/23` |
| USB Ethernet | `enx00e04c362511` · RTL8152 10/100 · carrier UP · 100 Mb/s full duplex |
| 직결 연결 프로필 | `go2-lab` · `192.168.50.1/24` · 자동연결 켬 · priority 50 · default route 사용 안 함 · IPv6 끔 |
| Jetson 직결 ping | `192.168.50.2` · 3/3 응답 · 0% loss · RTT 0.891/1.652/2.563 ms |
| 직결 서비스 | `192.168.50.2:22` SSH 성공 · `192.168.50.2:4000` NoMachine 성공 |

초기 `192.168.123.51/24` 설정에서는 업체 내부망의 `.99`와 `.161`까지 L2 이웃을 찾지 못했다. Jetson 외부 NIC와 ai-lt01을 별도 `192.168.50.0/24`로 설정한 뒤 유선 직결 관리 경로가 정상화됐다 `확인됨`. 이 외부 포트는 Go2 내부망의 단순 bridge가 아니다.

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

Wi-Fi NoMachine과 별도로 유선 관리망 `ai-lt01 192.168.50.1 <-> Jetson 192.168.50.2`에서 SSH와 TCP 4000을 확인했다. ai-lt01의 `go2-lab`은 재부팅 뒤에도 주소가 복원되도록 자동연결을 켰고 `ipv4.never-default=yes`를 유지했다. 인터넷 기본 route는 Wi-Fi를 계속 사용한다.

현재 설치된 NoMachine 무료판은 active physical desktop connection 한 개만 허용한다. 팀원 여러 명이 각자 Player를 설치해 번갈아 접속할 수는 있지만 동시에 접속할 수는 없다. 대여 장비의 서버 패키지나 라이선스는 업체 승인 없이 바꾸지 않는다.

### 3.3 Jetson NIC와 SSH

| 역할 | Jetson 장치 | 실측 상태 |
|---|---|---|
| Go2 내부망 | `enP8p1s0` | UP · `192.168.123.99/24` · `192.168.123.0/24` 직접 route |
| Wi-Fi 관리망 | `wlP1p1s0` | UP · `192.168.21.103/23` · default gateway `192.168.20.1` |
| ai-lt01 직결 외부 LAN | `enx00181af2995a` | ASIX AX88179 · USB bus `5000M` · Ethernet link `100Mb/s Full` · `192.168.50.2/24` · 물리 UP |

직결 실패 원인은 Jetson 외부 NIC에 IPv4가 없었던 것이다. Go2 내부망 `192.168.123.0/24`와 겹치지 않는 별도 subnet을 설정해 `ai-lt01 192.168.50.1/24 <-> Jetson 192.168.50.2/24`를 확정했다.

SSH는 이미 설치돼 있다 `확인됨`.

| 항목 | 값 |
|---|---|
| 패키지 | `openssh-server 1:8.9p1-3ubuntu0.18` |
| 서비스 | enabled · active |
| listen | IPv4 `0.0.0.0:22` · IPv6 `[::]:22` |

ai-lt01 전용 ED25519 key를 Jetson `nvidia` 계정에 등록했고 `BatchMode=yes` SSH에 성공했다 `확인됨`. 개인키 경로는 ai-lt01의 `/home/jay/.ssh/id_ed25519_go2`이며 개인키와 비밀번호는 저장소에 기록하지 않는다. 직결 SSH에서 `hostname=tegra-ubuntu`, `whoami=nvidia`, 세 NIC 주소를 다시 확인했다. Wi-Fi가 없어도 유선 SSH와 NoMachine을 사용할 수 있다.

### 3.4 HDMI 없는 재부팅과 NoMachine

HDMI가 빠진 상태로 재부팅한 뒤 Jetson, GDM, GNOME과 NoMachine 서비스는 모두 정상이었지만 Xorg의 현재 화면은 `640×480`이었다. `/var/log/Xorg.0.log`에도 `Virtual screen size determined to be 640 x 480`이 남았다. NoMachine 장애가 아니라 모니터 EDID가 없는 Tegra Xorg의 기본 fallback이다.

HDMI 모니터를 같은 안쪽 포트에 다시 연결하자 재부팅 없이 `HDMI-0 connected primary 1920x1080+0+0`, 60 Hz로 복구됐다. 현재 `/etc/X11/xorg.conf`에는 `AllowEmptyInitialConfiguration=true`만 있고 headless 고정 해상도는 없다. 영구 headless 운용은 HDMI dummy plug 또는 복구 가능한 Xorg 1920×1080 가상 화면 설정을 별도 관문으로 적용한다. 설정 전에는 SSH 복구 경로와 원본 `xorg.conf` 백업을 확보한다.

2026-11-18 다시 확인한 부팅에서는 HDMI가 연결된 시점에 Xorg가 `JRY HDMI (DFP-0)` EDID를 읽어 1920×1080으로 시작했고, 분리 뒤 `DFP-0: disconnected`와 `Setting mode "NULL"`을 기록했지만 그 부팅의 root screen 크기는 1920×1080으로 남았다. 따라서 파일·아이콘 위치는 같아도 HDMI 없는 최초 부팅의 640×480 root screen에서는 같은 NVIDIA 배경이 확대/crop돼 다른 desktop처럼 보인다. NoMachine 계정이나 홈 디렉터리가 바뀐 현상은 아니다.

해당 모니터 EDID 256 bytes를 Jetson `/home/nvidia/go2_diag/display/`에만 보존하고 NVIDIA `CustomEDID`로 DFP-0 1920×1080을 만드는 가역적 bundle을 [`20261118-go2-headless-nvidia/`](20261118-go2-headless-nvidia/README.md)에 작성했다. 기존 `xserver-xorg-video-dummy` 설정은 NVIDIA 물리 X screen을 우회해 RViz/OpenGL 검증에 불리하므로 활성화하지 않는다. 실제 적용과 HDMI 없는 재부팅 2회, NVIDIA renderer 검증 전에는 완료로 판정하지 않는다.

같은 날 bundle을 실제 적용했다. 최초 `/etc/X11/xorg.conf` backup을 보존했고 물리 HDMI가 `disconnected`인 상태로 재부팅했다. 새 Xorg는 `ConnectedMonitor=DFP-0`와 custom EDID를 읽어 1920×1080@60 mode를 설정했고 GDM/GNOME X11, NoMachine 서비스와 사용자 화면이 정상 복귀했다. XRandR의 논리 `HDMI-0 connected`와 kernel DRM의 물리 `disconnected`는 custom EDID 사용 시 서로 다른 의미다. 이 1회는 통과이며 다음 정상 전원 사이클 반복과 실제 RViz/OpenGL 표시가 남았다.

## 4. 시스템 · 센서 · ROS 실측

2026-11-17 NoMachine의 Jetson 터미널에서 읽기 전용 명령으로 확인했다.

### 4.1 Jetson 모듈과 JetPack

| 항목 | 실측값 |
|---|---|
| device tree model | `NVIDIA Jetson Orin NX 16GB - AVerMedia NX215B` |
| OS | Ubuntu `22.04.5 LTS` |
| L4T | release `R36`, revision `4.7`, aarch64 |
| kernel | `5.15.148-tegra` · PREEMPT |
| RAM | total `15 GiB` · 측정 시 available `12 GiB` |
| swap | `7.6 GiB` · 측정 시 사용 `0 B` |
| nvpmodel | mode `2` · `15W` |
| CPU 상태 | 8개 가운데 core 0~3 online · 4~7 offline · online core 상한 `1.4208 GHz` |
| GPU 상한 | `612 MHz` |
| root storage | Samsung `MZVLQ128HBHQ-000` 128 GB NVMe · ext4 116 GB 중 약 100 GB 여유 |
| 온도 | 무부하 측정 시 thermal zone 약 36~38°C · `nvfancontrol` active |

50 Hz ONNX 추론 성능을 측정할 때 현재 `15W` mode를 기준값으로 반드시 함께 기록한다. 전력 mode를 임의로 바꾸지 않는다.

### 4.2 RealSense D435i

| 항목 | 실측값 |
|---|---|
| 장치 | `RealSense D435I` |
| USB ID | `8086:0b3a` |
| firmware | `5.17.0.10` |
| kernel driver | `uvcvideo` · HID는 `usbhid` |
| Jetson 과거 USB 경로 | 업체 장착 상태에서 USB 2.0 root hub와 hub를 거쳐 `480M` · USB `2.10` 확인 |
| Jetson 현재 USB 경로 | 재부팅 뒤 Realtek USB 3 hub port 4에서 USB `3.20`, `5000M`, 동일 devnum 4로 30초 이상 유지 · kernel disconnect/error 없음 |
| ai-lt01 C-to-A 젠더 시험 | SuperSpeed로 열거되지만 1~10초 안에 반복 disconnect |
| ai-lt01 C-to-C 직결 | `5000M` · USB `3.20` · 15회 연속 표본에서 같은 장치 번호로 안정 유지 |
| device serial | `243722073643` |
| ASIC/USB serial | `253243060450` |
| IMU type | `BMI085` |

업체 매뉴얼은 D435i의 color 640×480 30 fps, aligned depth 640×480 30 fps, gyro 200 Hz, accel 100 Hz를 제시한다. D435i와 C-to-C 케이블은 USB 3에서 정상 동작한다 `확인됨`. 업체 제공 C-to-A 젠더를 거친 ai-lt01 본체 USB-A 직결에서는 `new SuperSpeed USB device`와 D435i serial까지 인식한 뒤 반복 disconnect가 발생했다. 따라서 젠더가 USB 3 신호를 전혀 지원하지 않는 것은 아니지만 SuperSpeed 경로가 안정적이지 않다 `확인됨`. Jetson에서 `480M`으로 내려간 현상도 이 경로 문제와 일치한다.

현재 Jetson에서 ROS 2 RealSense node를 depth Z16 640×480×30과 color RGB8 640×480×30으로 짧게 실행했다. depth는 약 28~30 Hz, color는 약 27~30 Hz로 발행됐다. 시작 직후 `Depth stream start failure` hardware notification이 한 번 있었지만 이후 프레임은 계속 수신됐다. 장시간 drop 검사는 아직 하지 않았다.

D435i gyro/accel은 실패했다. librealsense 로그는 `No HID info provided`, `HID Motion Sensor Failure (bad optional access)`를 기록했고 IMU 토픽은 생성되지 않았다. `nvidia` 사용자는 `video`, `plugdev` 그룹에 있고 `/dev/hidraw0`과 video node 권한, 공식 2.58.4 D435i udev rule 세 줄은 확인돼 단순 파일 권한 문제로 확정할 수 없다. Jetson kernel에서는 interface 5가 `hid-generic`으로 붙었다. 영상 경로 성공과 IMU 성공을 분리해 다룬다.

`rs-enumerate-devices --debug`와 library symbol을 추가 확인했다. 현재 `/opt/ros/humble`의 librealsense 2.58.4는 Linux `v4l_backend`를 사용하고 UVC video0~5는 찾지만 HID device info를 backend device group에 넣지 못한다. RealSense 공식 이슈의 JetPack 6 + D435i IMU 실패 양상과 일치하며, 공식 제시 우회 후보는 librealsense를 `FORCE_RSUSB_BACKEND=TRUE`로 별도 빌드하는 것이다. 이는 아직 적용하지 않았다.

카메라 firmware `5.17.0.10`도 호환 관문이다. RealSense 2.58.4 release 표는 D435/D435i 계열에 `5.17.3.10 이상`을 제시한다. firmware update는 장치를 영구 변경하고 실패 위험이 있으므로 업체 확인, 현재 firmware backup/복구 방법과 전원 안정성을 확보하기 전에는 실행하지 않는다.

시스템 패키지를 바꾸지 않고 Jetson `/home/nvidia/go2_diag/librealsense-rsusb-v2.58.4/`에 tag v2.58.4 commit `34d6c778e1134d8505adcd56bb57acbe7598a459`을 `FORCE_RSUSB_BACKEND=TRUE`로 빌드했다. install prefix도 같은 폴더 아래로 격리했고 `/opt/ros/humble`, `/usr/local`, linker cache와 firmware는 변경하지 않았다.

격리 RSUSB 도구는 BMI085를 HID 오류 없이 식별했다. 최소 진단 프로그램은 5초 동안 gyro 976 frame, accel 502 frame을 받아 각각 195.2 Hz와 100.4 Hz를 기록했다. 이어 기존 ROS `realsense2_camera_node` binary에 실행 시에만 격리 library path를 주입해 다음을 동시에 수신했다.

| RSUSB ROS topic | 약 10초 실측 |
|---|---|
| depth 640×480×30 | 28.41 Hz |
| color 640×480×30 | 28.67 Hz |
| gyro 목표 200 Hz | 200.27 Hz |
| accel 목표 100 Hz | 101.50 Hz |
| united IMU | 200.21 Hz |

따라서 D435i IMU hardware와 현재 firmware는 동작하며, 기존 IMU 실패 원인은 JetPack 6의 V4L2 backend 조합으로 확정한다. 다만 RSUSB 동시 스트림 시작 시 `control_transfer ... Resource temporarily unavailable`, UVC streamer watchdog과 depth start failure notification이 있었고 이후 frame은 계속 나왔다. 장시간 rate/drop, 재시작, USB 재연결과 CPU load를 통과하기 전에는 운영 기본값으로 승격하지 않는다. 재현용 최소 소스는 [`rsusb_imu_probe.cpp`](20261117-go2-x-jetson-field-intake-assets/rsusb_imu_probe.cpp)에 보관한다.

출처: [RealSense Jetson Orin IMU issue #13713](https://github.com/realsenseai/librealsense/issues/13713) · [RealSense D435i Orin NX issue #13958](https://github.com/realsenseai/librealsense/issues/13958) · [librealsense releases](https://github.com/realsenseai/librealsense/releases)

교체용 모비큐 `EM-ATCP2P` USB-A 3.2 to USB-C 10 Gbps 젠더 2개입은 구매 완료됐지만 아직 미수령·미검증이다. 도착 뒤 ai-lt01에서 두 개를 각각 `5000M`과 disconnect 부재로 선별하고, 통과한 젠더만 Jetson 장시간 스트림에 사용한다. 브라켓과 카메라 각도 조절 나사는 이 과정에서 풀지 않는다.

2026-11-20 팀장 정정: 업체 젠더는 D435i 를 USB 3 이 아니라 USB 2.0 으로 잡아 해상도 설정이 낮게 들어왔고, 노트북에서도 같았다. 그래서 USB 3.1 까지 받는 C to A 젠더를 새로 사서 11/19 17 시 이후 D435i 와 Jetson USB 포트 사이에 계속 꽂아 두었다. 이것이 위 모비큐 `EM-ATCP2P` 다 (팀장 11/21 확인). 2개 중 어느 것인지, `5000M` 선별을 했는지는 기록이 없다. 새 젠더로도 11/20 앱에서 D435i 신호가 자주 끊긴다는 팀원 보고가 있었고, 같은 날 기록에서 걷기 시작 때 USB 끊김이 잡혔다 (8 절). 젠더 하나만의 문제는 아니다.

### 4.2.1 정책 실행 환경의 현재 공백

L4T `nvidia-l4t-cuda 36.4.7`은 설치돼 있지만 `/usr/local/cuda/bin/nvcc`는 없고 `nvidia-jetpack` metapackage도 설치되지 않았다. TensorRT와 cuDNN Debian package, Docker, Python `torch`, `onnx`, `onnxruntime`, `pyrealsense2`도 현재 기본 Python 3.10 환경에서 발견되지 않았다. OpenCV 4.5.4와 NumPy 1.21.5는 있다.

따라서 ONNX 파일이 있다고 바로 50 Hz 정책을 실행할 수 있는 상태는 아니다. JetPack 전체를 임의 설치하거나 OS를 바꾸지 말고, 정본 contract에 맞는 aarch64 ONNX Runtime 또는 TensorRT 실행 경로, CUDA 호환성과 watchdog을 별도 배포 관문으로 설계한다.

### 4.3 ROS 2 · Unitree DDS · LiDAR

| 항목 | 실측값 |
|---|---|
| ROS | Humble |
| 설치 | `/opt/ros/humble` |
| 업체 작업공간 | `/home/nvidia/wego_ws` |
| Unitree 상태 | `/lowstate`, `/lf/lowstate`, `/sportmodestate`, `/lf/sportmodestate` 발견 |
| 조이스틱 | `/wirelesscontroller`, `/wirelesscontroller_unprocessed` 발견 |
| 저수준 명령 | `/lowcmd` 토픽 발견 · 읽기만 했으며 publish하지 않음 |
| LiDAR | `/utlidar/cloud`, `/utlidar/imu`, `/utlidar/lidar_state`, `/utlidar/range_info` 등 발견 |
| SLAM | `/uslam/*`, `/lio_sam_ros2/mapping/odometry` 발견 |
| 배터리 경고 | `/lf/battery_alarm` 발견 |

LiDAR DDS endpoint와 type은 다음처럼 확인됐다.

| 토픽 | type | publisher |
|---|---|---|
| `/utlidar/lidar_state` | `unitree_go/msg/LidarState` | bare DDS app 1개 · RELIABLE |
| `/utlidar/range_info` | `geometry_msgs/msg/PointStamped` | bare DDS app 1개 · RELIABLE |
| `/utlidar/cloud` | `sensor_msgs/msg/PointCloud2` | bare DDS app 1개 · RELIABLE |

`ros2 pkg prefix unitree_go`와 `ros2 interface show unitree_go/msg/LidarState`는 package 없음으로 실패했다. ROS message package는 없지만 Unitree SDK2의 C++ type header `/usr/local/include/unitree/idl/go2/LidarState_.hpp`는 설치돼 있다 `확인됨`. 따라서 bare DDS endpoint는 발견되지만 ROS CLI가 custom message를 역직렬화하지 못한다.

`ros2 topic echo --once /utlidar/lidar_state`는 `The message type 'unitree_go/msg/LidarState' is invalid`로 실패했다. BEST_EFFORT로 다시 구독한 `/utlidar/range_info`와 `/utlidar/cloud`도 제한 시간 안에 표본이 없었다. 이는 LiDAR 비활성이 아니라 ROS message package 부재와 CLI 구독 경로 문제였다.

설치된 `libunitree_sdk2.a`, `libddsc.so`, `libddscxx.so`와 CMake package를 사용해 publisher가 없는 읽기 전용 C++ subscriber를 빌드했다. `rt/utlidar/lidar_state`를 Go2 내부망 `enP8p1s0`에서 직접 구독해 실제 상태 수신에 성공했다 `확인됨`. 진단기는 Jetson `/home/nvidia/go2_diag/lidar_state_readonly/`에 두었고 LiDAR work mode, 회전, IP, `/lowcmd`를 변경하는 API는 포함하지 않았다.

5회 반복 실측 범위는 다음과 같다.

| 필드 | 실측값 |
|---|---|
| `software_version` | `1.0.0.38` |
| `error_state` | `0` |
| `dirty_percentage` | `1` |
| `cloud_frequency` | `15.352078`~`15.384279` |
| `cloud_packet_loss_rate` | `0.0` |
| `cloud_size` | `61,986`~`62,027` |
| `cloud_scan_num` | `210` |
| `imu_frequency` | `247.497879`~`250.643814` |
| `imu_packet_loss_rate` | `0.0` |

`firmware_version`과 `sdk_version` 문자열은 이 publisher에서 빈 값이었다. `sys_rotation_speed`와 `com_rotation_speed`도 수신했지만 공개 header에 단위 설명이 없으므로 Hz로 환산하지 않는다.

### 4.3.1 Go2 내부망과 receive-only 상태 실측

Jetson `enP8p1s0`은 Go2와 `1000Mb/s Full Duplex`로 연결돼 있고 `192.168.123.161`에 3/3 ping, 0% loss, 약 0.22 ms로 응답했다. 업체 `go2_driver`의 source를 먼저 검토해 `receive_only=true`가 velocity, orientation, motion service, stop SDK와 body-pose SDK 호출을 모두 차단하는 것을 확인했다. 그 뒤 `receive_only=true`, `control_gate_enabled=false`, `command_passthrough=false`, `enable_body_pose=false`를 명시해 짧게 실행하고 종료했다. patrol, direct SDK motion 및 motion example은 실행하지 않았다.

| 항목 | 실측값 |
|---|---|
| 통신 | `/go2/comm_ok=true` |
| 배터리 | SOC 89% · raw current 약 -1.4 A · cycle 20 · 31/33°C |
| SportModeState | `mode=0`, `gait_type=0`, `error_code=1001` · fresh |
| 관절 | 12개 position/velocity/temperature 수신 · 약 10 Hz |
| 모터 온도 | 약 29~33°C |
| body IMU publish | 약 30.3 Hz |
| raw low state 변환 publish | 20.0 Hz |
| LiDAR PointCloud2 변환 publish | 약 15.37 Hz |

`error_code=1001`은 현재 사용자가 설정한 damping 상태와 Unitree Sport API의 Damp ID 1001이 일치하지만, 공개 `SportModeState` 메시지는 이 필드의 펌웨어별 상태 의미를 정의하지 않는다. 건강 상태나 제어 준비 완료로 해석하지 않고 opaque marker로 보존한다. raw low state의 `foot_force`에는 약 90대 숫자가 들어왔지만, Go2 X에 실사용 가능한 발 접촉 센서가 없다는 전달과 함께 정책은 이 필드를 사용하지 않는다. placeholder인지 추정하지 말고 별도 하드웨어 근거가 생길 때까지 미사용 상태를 유지한다.

### 4.3.2 업체 `wego_ws` 구성 감사

업체 작업공간에는 `go2_base`, `go2_description`, `go2_msgs`, `robot_control_interfaces`, `wego_teleop`이 있다. `wego_teleop.launch.py`는 현재 실제 NIC `enP8p1s0`, `receive_only=true`를 기본값으로 사용하며 Livox/Aurora를 포함하지 않는다. 하지만 다음 불일치 때문에 통합 launch를 아직 실행하지 않는다.

| 항목 | 확인된 불일치 |
|---|---|
| `go2_base/config/d435i.yaml` | 고정 serial `250122076113`; 실제 D435i device serial은 `243722073643` |
| `go2_sensors_launch.py` | 기본 interface `enp88s0`; 현재 장치에 없음 |
| `go2_sensors_launch.py` | MID-360/Livox와 optional Aurora 구성을 포함; 현재 내장 LiDAR는 L2 |
| D435i mount TF | 설정 주석이 robot mount TF는 실측 대기라고 명시; 임의 transform을 추가하지 않음 |
| `go2_description.urdf` | 기존 `utlidar` transform `xyz=0.3 0 -0.03`, `rpy=0.22 -3.00 2.05`가 있으나 현 개체 실측 근거는 아직 없음 |
| `wego_teleop/README.md` | ROS domain 42 운용 문구가 있으나 Unitree native DDS는 domain 0을 사용; 두 계층을 구분해야 함 |

`wego_teleop/config/d435i.yaml`은 고정 serial을 제거하고 color/depth 640×480×30, gyro 200 Hz, accel 100 Hz, receive-only bringup을 의도한다. 하지만 현재 IMU HID 실패와 mount TF 미측정이 남아 있으므로 파일의 의도값을 실측 성공값으로 취급하지 않는다.

### 4.4 LiDAR 모델 판정

현재 개체는 `4D LiDAR L2`로 운용 판정한다 `확인됨`. 근거는 다음 넷이다.

1. Unitree 현재 Go2 제품 페이지는 Go2의 기본 LiDAR를 L2, FOV 360°×96°로 안내한다.
2. 이 Go2 X의 LiDAR 회전은 조선대 Go2 EDU에서 확인한 L1보다 눈에 띄게 느리다 `사용자 비교 관찰`. 공식 수치는 L2의 수평 주사가 5.55 Hz, L1은 11 Hz이므로 방향이 일치한다.
3. `/utlidar/*` DDS와 SDK2 `LidarState_` type이 존재해 Unitree 4D LiDAR 계통임은 확인됐다.
4. 읽기 전용 native DDS subscriber에서 `cloud_size`가 5회 모두 약 62,000으로 안정적으로 수신됐다. 이는 Unitree 공식 L2 유효 주파수 64,000 points/s에 가깝고 L1의 21,600 points/s와 명확히 구분된다. packet loss는 0이었다.

현재 공식 Go2 앱 페이지에는 L1이라는 옛 표기가 남아 있고 `LidarState_`에는 별도 model 문자열이 없다. 따라서 본체 라벨이나 serial 조회에 의한 식별은 아직 없지만, 공식 L1/L2 데이터율 차이와 실제 상태값이 충분히 분리되므로 실기 구성에서는 L2로 다룬다. `/lowcmd`와 LiDAR 제어 명령에는 어떤 값도 publish하지 않았다.

출처: [Unitree 현재 Go2 제품 페이지](https://www.unitree.com/go2/) · [Unitree L2 공식 제원](https://www.unitree.com/L2/) · [Unitree Go2 앱 페이지의 L1 표기](https://www.unitree.com/app/go2/)

부팅 직후 업체 `wego_teleop` bringup은 실행 중이 아니었다 `확인됨`. 진단 중에는 receive-only `go2_driver`를 제한 시간 동안만 띄워 `/go2/odom`, `/go2/imu`, `/joint_states` 등을 측정한 뒤 종료했다. 순정 Unitree DDS 토픽과 업체 ROS driver가 변환해 만드는 ROS 토픽을 구분한다.

## 5. 카메라 실기 정렬 기준

시뮬 정본 [`foothold_s2/sensors/depth_cam_cfg.py`](../../foothold_s2/sensors/depth_cam_cfg.py)의 기준은 다음과 같다.

| 항목 | 시뮬 기준 |
|---|---|
| 장착 위치 | 몸통 base 중심 기준 앞 `0.25 m` · 좌우 `0 m` · 위 `0.12 m` |
| pitch | 아래 `35°` |
| 정책 입력 해상도 | `60×60` |
| 갱신 주기 | `10 Hz` |

실기 카메라는 머리 위 고정 자리에서 각도만 조정할 수 있다. 각도는 35°로 맞추되, 실기 렌즈 중심의 몸통 base 기준 앞·위 거리를 자로 재서 기록해야 한다. 위치가 시뮬과 다르면 깊이 기반 지도가 어긋날 수 있다. 처음 실기 정책 시험은 이 영향을 피하도록 `map_off`를 사용한다.

2026-11-18 냉각·재부팅 뒤 D435i 가속도를 depth 광학좌표로 변환하고 Go2 projected gravity와 직접 비교하는 실시간 상대각 도구를 검증했다. 조정 직후 독립 5초 측정 3회는 35.037°·35.049°·35.039°(평균 35.042°, 모집단 표준편차 0.005°)였다. 최근 광학 중심 높이 실측 0.395 m는 전체 Depth 바닥 평면 역산 0.3954 m와 일치했다. 다만 오른쪽 브라켓 체결부가 헛돈 뒤 3회 평균이 35.252°로 0.210° 이동했다. 따라서 각도 계산·조정법은 확인됐지만, 양쪽 체결 고정과 주행 전후 유지성을 통과하기 전까지 최종 장착값으로 확정하지 않는다.

오른쪽 체결부를 다시 고정한 뒤 최종 3회는 평균 35.068°·표준편차 0.004°였고, 순정 Classic으로 좌·우 ㅁ자 코스를 각각 한 바퀴 주행한 뒤 평균 35.023°·표준편차 0.023°였다. 전후 변화 -0.045°로 이 주행 범위의 브라켓 단기 유지성을 통과한다. 180초 Depth는 평균 29.81 fps, 무효/0.2~3.0 m 밖 평균 11.18%였으나 약 10초에 DDS와 Depth가 함께 약 1초 정지하고 Depth frame number가 287→0으로 reset됐다. 이후는 forward gap 없이 이어졌다. 장기 운영 관문에서는 이 reset을 별도로 재현·해소한다.

## 6. 정본 3 정책과 안전 관문

실기에서 추측해 채우면 안 되는 값은 [`start-m15500-app/CONTRACT.md`](20261103-policy-handoff/start-m15500-app/CONTRACT.md)와 [`contract.json`](20261103-policy-handoff/start-m15500-app/contract.json)을 정본으로 쓴다. 관측 순서, 관절 순서, 행동 배율, PD 값, 주기를 기억으로 옮기지 않는다.

| 항목 | 확정 또는 현재 상태 |
|---|---|
| 첫 실기 ONNX | `start-m15500_map_off.onnx` |
| 정책 주기 | 50 Hz |
| 발 접촉 센서 | 정책 입력에 쓰지 않음. raw DDS 변환에는 `foot_force` 숫자가 보였지만 실사용 가능한 센서값으로 검증하지 않았으므로 정책에는 포함하지 않음 |
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

충전 (2026-11-20 팀장 확인): Go2 X 에는 본체 뒤쪽 충전 단자가 없다 (EDU 에는 있다). 배터리를 빼서 충전한다. 충전기 제원은 `docs/research/20260908-go2-spec-sim-vs-real.md` 의 공식 사양표 값 (33.6 V 3.5 A · 급속 33.6 V 9 A) 이며 이 개체의 충전기에서 다시 읽은 값은 아니다.

지금까지 현장에서는 Jetson 을 먼저 끄지 않고 Go2 전원을 바로 꺼도 문제가 드러나지 않았다 (팀장). 위험한 때는 기록 · 설치처럼 Jetson 이 디스크에 쓰는 중일 때다. 11/20 은 Jetson OS 를 먼저 끄고 Go2 를 껐다.

출처: [Unitree Go2 사용자 매뉴얼](https://marketing.unitree.com/article/en/Go2/User_Manual.html) · [Unitree Go2 배터리와 BMS 보호](https://www.unitree.com/go2/battery/)

## 7. 팀원이 이어서 볼 위치

- 전체 실행 순서: [`20261118-go2-x-commissioning-worklist.md`](20261118-go2-x-commissioning-worklist.md)
- 정본 3 전달: [`HANDOFF-START-m15500-CANON3.md`](20261103-policy-handoff/HANDOFF-START-m15500-CANON3.md)
- 앱 전달과 남은 실기 경로: [`APP-HANDOFF-1117.md`](20261103-policy-handoff/APP-HANDOFF-1117.md)
- 시뮬 대 실기 제원: [`docs/research/20260908-go2-spec-sim-vs-real.md`](../../docs/research/20260908-go2-spec-sim-vs-real.md)
- 연속 작업 이슈: [foothold-lab #557](https://github.com/foothold-project/foothold-lab/issues/557)
- NX215 공식 제품 페이지: [AVerMedia NX215](https://www.avermedia.com/professional/product-detail/NX215)
- NoMachine 제품별 연결 제한: [NoMachine FAQ](https://www.nomachine.com/support/faq)

## 8. 2026-11-20 학원 기록 · D435i 끊김 · 방전 · 회수 (app-lx)

근거: Jetson 기록 `20261120-2145-academy-full` (ai-lx01 D 쪽 회수본 · `bag_0.db3` 42.0 GB) · 그 안의 `rs.log` · `watch_drop_214813.txt` (끊김 순간의 커널 기록 40 줄) · `vmstat-main.txt` · app-lx 분석 스크립트 (`/home/jay/data/app-lx/academy-1120/analysis/`). 로봇 명령은 모두 팀장 조이스틱, 세션은 받기만 했다.

### 8.1 측정 전 값

| 항목 | 값 | 근거 |
|---|---|---|
| D435i↔몸통 상대각 | 35.13° (`ON TARGET`) · 바닥 기준 35.32° · 몸통 +0.20° | 20:44 각도 창 (`relative_pitch_abs`) · 학원 맨바닥 · 서 있음 `확인됨` |
| 높이 | 바닥에서 D435i 두 렌즈 가운데까지 40.5 cm | 팀장 줄자 `확인됨` (11/18 광학 중심 0.395 m 와 1 cm 차) |
| 관문 | 9 개 통과 (L2 원래 점 · deskewed · L2 IMU · odom · 깊이 · 색 · `/tf_static` · SDK sport · lowstate) | 21:45 · 앞선 21:24 실패는 `/tf_static` 확인 명령 문제 (ros2 daemon 고장 · reliable 빠짐) 로 고친 뒤 통과 |

### 8.2 기록

- 21:46:06 시작. 팀장 Ctrl+C 뒤에도 `ros2 bag record` 와 카메라 노드가 따로 떠 있어 22:11 까지 이어졌다. 그래서 학원 고리, 숙소로 오는 길, 계단 (Free Walk 대각선 · 뒤로 4 칸) 이 모두 들어 있다. 길이 1526 초 · 메시지 832,926 개.
- 고칠 것: `academy_1120.sh` 는 기록과 카메라를 `setsid` 로 띄우므로 Ctrl+C 로 같이 멈추지 않는다. 끝낼 때 기록 프로세스에 SIGINT 를 보내는 처리가 필요하다.

| 토픽 | 개수 | 평균 Hz | 0.2 초 넘는 끊김 | 가장 긴 끊김 |
|---|---|---|---|---|
| 깊이 `image_rect_raw` | 43,108 | 28.25 | 4 | 37.6 초 (21:48:00) |
| 깊이 `camera_info` | 44,455 | 29.13 | 4 | 37.6 초 |
| 색 compressed | 44,467 | 29.14 | 2 | 38.1 초 (21:48:00) |
| L2 `cloud` · `cloud_deskewed` | 23,249 · 23,263 | 15.2 | 1 | 11.1 초 (21:57:28 · 숙소 오는 길 · 원인 미확인) |
| L2 IMU | 381,519 | 250.0 | 0 | 0.03 초 |
| odom | 228,388 | 149.7 | 0 | 0.04 초 |

### 8.3 D435i 끊김은 두 가지다

1. **USB 단 끊김 (21:47:49 ~ 21:48:38 · 약 45 초) · 심각.** 깊이와 색이 같은 순간 멈췄다 (4.6 초 · 1.3 초 · 38 초 연달아). 같은 때 L2 · odom 은 정상이었다. 카메라 노드는 `VIDIOC_QBUF … No such device` 를 냈고, 커널에는 `Disable of device-initiated U1/U2 failed`, `error -71`, `Device not responding to setup address`, `USB disconnect` 가 되풀이됐다. 기록 시작 103 초 뒤로, 서 있다가 처음 걷기 시작한 때다. 그 뒤 23 분 (숙소 길 · 계단 포함) 은 0.2 초 넘는 끊김이 0 회였다 `확인됨`.
   - 원인 후보 (둘 다 미확인): 걷기 시작의 흔들림으로 젠더 · 선 · 꽂는 자리가 떨어짐 / USB 3 절전 (U1 · U2 · LPM) 전환 실패.
   - 「물리」 의 뜻: 선이 빠진 것이 아니다. 팀장 사진 (11/20 밤) 으로 모든 연결은 꽂혀 있었다. `error -71` 은 꽂힌 채 접점 신호가 잠깐 흐려질 때 나오고, 5 Gbps 인 USB 3 는 아주 작은 흔들림에도 이렇게 된다. 그래서 다시 꽂지 않아도 저절로 다시 붙었다.
   - 11/21 흔들기 시험 결과 (8.7): ② Jetson 쪽에서 두 번 재현, ① 카메라 쪽은 0 회. 아래 ① 은 원인에서 뺀다.
   - 사진에서 본 두 자리 (11/20 밤의 후보): ① 카메라 쪽, 선이 D435i USB-C 구멍에서 나오자마자 거의 직각으로 꺾여 각도 브라켓 축 바로 옆을 지난다. 몸이 흔들리면 꺾인 자리가 커넥터를 옆으로 당긴다. ② Jetson 쪽, 모비큐 젠더가 캐리어 USB-A 단자에 길게 꽂히고 선은 젠더 끝에서 위로 꺾여 고무 고리를 지난다. 선이 당겨지면 젠더가 지렛대가 되어 USB-A 접점을 비튼다.
   - 다시 붙었을 때 USB 3 인지 2 인지, 첫 끊김 순간의 커널 줄은 Jetson 이 꺼져 아직 못 읽었다 (다음 부팅 때 `journalctl -k` 로 읽음).
2. **노드 단 한 장씩 빠짐 (기록 내내 약 3 %) · 가벼움.** 깊이 `camera_info` 는 나왔는데 영상이 없는 것이 1,342 장이다. 매분 1.6 ~ 4.7 % 로 고르고, 연속은 길어야 3 장 (0.1 초) 이다. 색은 빠지지 않았다. 정렬 깊이 (`align_depth`) 계산이 한 코어를 꽉 채운 것으로 짐작한다 (미확인 · 전체 CPU 는 평균 약 60 % 놀았다 · 15W 모드 4 코어).

정책 (START · HiPAN 의 저수준 `lowcmd` 경로) 에는 1 번이 치명적이다. 다음 순서로 가린다.

1. 카메라를 켜고 Go2 를 세운 채, ① 카메라 쪽 꺾인 자리, ② Jetson 쪽 젠더를 하나씩 손으로 살짝 흔든다 (5 분). app-lx 가 깊이 Hz 와 커널 USB 줄을 1 초마다 본다. 어느 쪽에서 `-71` 이 뜨는지로 자리를 가린다.
2. USB 3 절전 (LPM) 을 끄고 같은 시험을 한다 (sudo · 재부팅 · 팀장).
3. 카메라 쪽은 선이 커넥터에서 곧게 나와 여유 고리 하나를 만든 뒤 브라켓에 묶이게 한다 (타이 · 벨크로). Jetson 쪽은 젠더를 빼고 A-to-C 한 줄짜리 USB 3 선으로 바꿔 접점 하나를 줄인다.
4. 앱에서 보이는 끊김은 Jetson 기록과 같은 때로 맞춰, USB 끊김인지 망 끊김인지 가른다.

### 8.4 방전 (Damping · 엎드림 · LAN 회수와 sha256 대조 중)

| 시각 | 배터리 | 전압 |
|---|---|---|
| 22:18 | 7 % | 27.22 V |
| 22:25 | 5 % | 27.10 V |
| 22:29 | 4 % | 27.03 V |
| 22:33 | 3 % | 26.96 V |
| 22:39 | 2 % | 26.83 V |
| 22:43 | 1 % | 26.58 V |
| 22:44 | 1 % | 26.50 V (마지막 읽음 · 22:45 팀장이 Jetson 을 끈 뒤 Go2 끔) |

- 1 분마다 SDK 읽기 전용 감시 3 초로 읽었다 (`soc_pct` · `power_v`). 7 % 에서 1 % 까지 약 26 분.
- 1 % 에서 정상 종료했으므로 「배터리가 끊길 때 Jetson 이 어떻게 꺼지나」 (6.1 절 3 번) 는 여전히 미확인이다.

### 8.5 회수 속도

| 길 | 크기 | 걸린 시간 | 속도 |
|---|---|---|---|
| 보드 외부 LAN 포트 (CAT6 직결 · 안쪽 칩은 보드 USB 허브에 붙은 AX88179 · `enx…` 1000 Mb/s) · tailnet 직접 경로 · rsync over ssh → ai-lx01 D | 42.0 GB | 22:19 ~ 22:38 (약 19 분) | 평균 약 37 MB/s · 1 분 단위 12 ~ 60 MB/s |
| 숙소 Wi-Fi (2.4 GHz · -67 dBm) | 쓰지 않음 | | 랜이 훨씬 빠르므로 큰 기록은 랜으로 받는다 |

- 받은 뒤 Jetson 의 백업 끝난 15 폴더 (약 20.6 GB) 를 `jetson_sync.py delete` 로 지웠다. 도구가 Jetson · ai-lx01 · NAS 세 곳 sha256 을 다시 맞춘 뒤에만 지운다 (팀장 22:24 · 22:35 확인). Jetson 남은 공간 60 GB.

### 8.6 Wi-Fi 가 늦게 붙는 까닭

- 21:53:17 학원 Wi-Fi 가 `ssid-not-found` 로 끊긴 뒤 21:53:19 supplicant 가 `inactive` 로 찾기를 멈췄다. 22:08:15 까지 15 분 동안 접속 시도 기록이 0 줄이고, 22:08:15 숙소 Wi-Fi 첫 시도에 0.3 초 만에 붙었다. 11/19 21:50 ~ 22:14 와 같은 꼴이다.
- 저장된 Wi-Fi 다섯의 `autoconnect-retries 0` 과 우선순위 (핫스팟 20 · 숙소 10 · 나머지 0) 는 22:13 에 되읽어 들어가 있음을 확인했다. 이 설정은 「시도 뒤 실패」 만 다시 하므로 이 꼴을 막지 못한다. Wi-Fi 절전은 켜져 있었다 (`wifi.powersave 3`).
- 22:2x 팀장 sudo 로 `fh-wifi-keepalive.timer` 를 깔았다: Wi-Fi 절전 끔 (다음 연결부터) · 30 초마다 끊김 상태면 다시 찾고 연결. 켜진 채 Wi-Fi 를 잃었다가 돌아오는 시험 (복도로 나갔다 들어오기) 은 다음 전원 때 한다.

### 8.7 2026-11-21 01 시 흔들기 시험 · USB 2 23 분 장수 · 정리

조건: 숙소 · Go2 엎드림 · 로봇 명령 0 · 카메라 노드는 학원 녹화와 같은 설정 (640x480 · 30 · align_depth) · 1 초마다 깊이 · 색 장수와 USB 속도 · `journalctl -k -f`. 원본은 Jetson `~/go2_diag/wiggle/` (`kern-wiggle-all.log` · `hz-wiggle-all.log`) 에 둔다.

| 흔든 자리 (팀장 손가락 · 세지 않게) | 커널 `-71` | USB 끊김 | 깊이 0 장 | USB 속도 |
|---|---|---|---|---|
| Jetson 쪽 젠더 · 아래 포트 1 회 (01:13:48 ~) | 있음 · 첫 줄 `Non-zero status (-71) in video completion handler` | 3 번 | 약 53 초 | 한때 `480M` (USB 2) 로 붙음 |
| Jetson 쪽 젠더 · 아래 포트 2 회 (01:15:47 ~) | 있음 · 같은 첫 줄 | 있음 | 45 초 | 끊겼다 붙었다 |
| 카메라 쪽 USB-C 꺾인 자리 (01:17 ~ 01:19) | 없음 | 없음 | 0 초 | `5000M` 그대로 |
| Jetson 쪽 젠더 · 위 포트로 옮긴 뒤 (01:21 ~ 01:26) | 있음 | 있음 | 1 분에 40 ~ 55 초 | `5000M` 로 다시 붙기 반복 |

- 첫 줄 · 길이 · USB 2 로 떨어지는 꼴이 11/20 21:47:49 학원 끊김과 같다 `확인됨`. 위 · 아래 포트 (`2-1.2` · `2-1.4`) 는 보드 안 같은 USB 3 허브이고, 같은 허브에 외부 LAN 칩 (AX88179) 도 붙어 있다.
- 지금 가장 그럴듯한 설명 (미확인): USB-A 안쪽 고속 접점 5 개는 짧고 작아서, 길게 꽂힌 젠더가 조금만 기울어도 먼저 떨어진다. 입구 쪽 USB 2 접점 4 개는 길어서 버틴다. 젠더 몸체 탓인지 보드 단자 탓인지는 가르지 못했다 (A-to-C 한 줄 선이 없고, 카메라 쪽 선은 빠지지 않는 구조).
- 11/20 학원 기록 `rs.log`: 21:48:35 무렵부터 `Device USB type: 2.1` 이고, 다시 연 설정은 깊이 `640x480 Z16 30` · 색 `640x480 RGB8 30` 그대로였다.
- 같은 기록 bag 장수 (받은 시각 기준):

| 구간 | 깊이 | 색 | L2 점구름 |
|---|---|---|---|
| USB 3 (21:45 ~ 21:48:35 · 끊김 45 초 포함) | 27.5 Hz | 28.8 Hz | 15.3 Hz |
| USB 2 (21:48:35 ~ 끝 · 약 23 분 · 걷기 · 계단 · Free Walk) | 29.1 Hz (40,038 장) | 30.0 Hz (41,249 장) | 15.2 Hz |

  색은 매분 1,795 ~ 1,799 장 (1,800 이 만점), 깊이는 매분 1,713 ~ 1,769 장이다. USB 2 구간 커널 USB 끊김 0 줄 `확인됨`.
- 시험 중 파이썬 수신기 (`rclpy` · best effort) 가 가만히 있어도 깊이 10 ~ 20 장만 셌다. RViz 를 끄고 CPU 가 76 % 놀아도 같았고, 같은 설정의 bag 은 29 Hz 였으므로 수신기 쪽 문제로 본다. 판정에는 0 장 구간과 커널 줄만 썼다.
- 정리: 지금 구조로 USB 3 를 쓰면 걸을 때 깊이가 45 ~ 55 초씩 끊긴다. USB 2 로 붙이면 이 끊김을 피한다는 기록이 하나 있다. 정책 전처리 후보 (작업목록 P2 · 60x60 · 10 Hz) 에 30 Hz 원본은 넉넉하지만, USB 2 에서의 지연과 카메라 IMU 를 함께 켠 대역은 아직 재지 않았다.
- 소프트웨어로 USB 3 만 막는 길: 이 커널 (5.15 tegra) 에는 포트별 `disable` 스위치가 없다 (읽기만으로 확인). 같은 허브에 외부 LAN 이 있어 허브째 막는 길은 쓰지 않는다. 하드웨어로 USB 2 전용 부품 (업체 젠더 · USB 2.0 연장선 · 허브) 을 끼우는 쪽을 먼저 한다.
- 다음 (11/21 학원 · 작업목록 P2): 업체 USB 2 젠더로 바꿔 흔들기 시험 · 걷기 녹화 · `USB type: 2.1` 확인 · 지연 · 카메라 IMU 를 함께 잰다. 정책 입력 명세 (해상도 · 주기 · 지연 · 끊김 견딤) 는 lead 에 물었다 (11/21 02:16).

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v0.17 | 2026-11-21 | app-lx: 흔들기 시험 (Jetson 쪽 두 번 재현 · 카메라 쪽 0 회 · 위 포트도 같음) · 학원 기록 USB 2 23 분 깊이 29.1 Hz · 색 30.0 Hz · 소프트웨어 USB 3 막기 불가 확인 · 외부 LAN 포트 이름 정정 (8.7) |
| v0.16 | 2026-11-20 | app-lx: 학원 기록 1526 초 분석 (D435i USB 단 끊김 45 초 · 노드 단 3 % 빠짐) · 새 3.1 젠더 정정 · Go2 X 충전 단자 없음 · 방전 7→1 % 곡선 · 42 GB 랜 회수 속도 · Wi-Fi 늦게 붙는 까닭과 다시 찾기 설정 (8 절) · 새 젠더 = 모비큐 EM-ATCP2P (팀장 확인) · 사진으로 본 꺾임 두 자리와 흔들림 시험 순서 (8.3) |
| v0.15 | 2026-11-18 | NVIDIA custom EDID 실제 적용 · 최초 xorg.conf backup 보존 · physical HDMI disconnected 재부팅에서 1920×1080@60/GDM/GNOME/NoMachine 통과 · 다음 정상 전원 사이클 반복과 RViz/OpenGL 확인 대기 |
| v0.14 | 2026-11-18 | HDMI 연결 부팅→분리와 HDMI 없는 부팅의 Xorg mode 차이 확정 · 같은 GNOME desktop의 배경 crop 현상 설명 · NVIDIA custom EDID headless 1080p bundle/최초 백업/SSH rollback 준비 · 실제 적용·재부팅 검증 대기 |
| v0.13 | 2026-11-18 | 브라켓 재체결 직후 상대각 3회 평균 35.068°/표준편차 0.004° · Classic 좌·우 ㅁ자 주행 뒤 35.023°/0.023° · 전후 -0.045°로 단기 유지성 통과 · 180초 Depth에서 DDS/Depth 약 1초 공통 정지와 frame number reset 1회 기록 |
| v0.12 | 2026-11-18 | D435i↔Go2 실시간 상대각 도구 검증 · 재조정 직후 3회 평균 35.042°/표준편차 0.005° · 오른쪽 체결부 헛돎 뒤 평균 35.252°로 0.210° 이동 · 광학 중심 높이 실측 0.395 m와 Depth 평면 0.3954 m 일치 · 기계 고정 미합격으로 최종 extrinsic 보류 |
| v0.11 | 2026-11-18 | D435i↔Go2 상대각 3회 평균 33.262° · 순정 Damping→Stand 뒤 전면 hip 78/81°C와 적색 점멸로 안전 중단 · Jetson 정상 종료 뒤 Go2 종료 · `1001`은 공식 SDK상 Damp API ID로 정정 · 다음 작업을 별도 commissioning worklist로 분리 |
| v0.10 | 2026-11-17 | 격리 librealsense 2.58.4 RSUSB build · gyro 약 195~200 Hz와 accel 약 100~101 Hz 실수신 · ROS depth/color/IMU 동시 발행 확인 · 현재 firmware에서 IMU hardware 정상과 V4L2 backend 원인 확정 · RSUSB 시작 경고와 장시간 관문 기록 |
| v0.9 | 2026-11-17 | D435i IMU failure가 현재 V4L2 backend에서 HID device info를 찾지 못하는 상태임을 debug log로 확인 · JetPack 6 알려진 문제와 RSUSB 별도 build 후보 · firmware 5.17.0.10과 SDK 권장 5.17.3.10 이상 차이 및 firmware update 보류 관문 기록 |
| v0.8 | 2026-11-17 | HDMI 없는 재부팅의 640×480 fallback과 HDMI 연결 즉시 1080p 복구 · 직결 LAN 자동연결 · Jetson 현재 D435i 5000M와 depth/color 30 fps급 실측 · D435i IMU HID 실패 · Go2 배터리/관절/IMU/LiDAR receive-only 수신률 · 업체 `wego_ws`의 stale serial/interface/MID-360 구성 불일치 · ONNX runtime 개발환경 공백 기록 |
| v0.7 | 2026-11-17 | Jetson 기존 D435i 480M 재확인 · ai-lt01 USB-A와 업체 C-to-A 젠더에서 SuperSpeed 반복 disconnect · C-to-C 직결은 USB 3.20 5000M로 안정 유지 · 젠더 경로 불안정 확정과 A-to-C 단일 케이블 교체 관문 기록 |
| v0.6 | 2026-11-17 | ai-lt01과 Jetson 외부 NIC의 `192.168.50.0/24` 직결망 · SSH key와 BatchMode 접속 확인 · native SDK2 읽기 전용 subscriber로 LiDARState 5회 수신 · 약 62k cloud size와 L2 공식 64k 대조로 L2 운용 판정 확정 |
| v0.5 | 2026-11-17 | Unitree ROS message package 부재와 SDK2 LidarState header 확인 · 공식 Go2 L2 제원과 L1 대비 느린 회전 관찰을 근거로 L2 유력 현장 판정 · 장치 식별값 미확인 한계 기록 |
| v0.4 | 2026-11-17 | LiDAR 세 토픽의 type과 bare DDS publisher 확인 · LidarState 로컬 type support 부재와 데이터 표본 미수신 기록 · L1/L2 미확정 유지 |
| v0.3 | 2026-11-17 | Ubuntu · L4T · RAM · 15W mode, 세 NIC 역할, SSH 활성, D435i firmware와 USB 2.0 연결, ROS Humble과 Unitree DDS · LiDAR 토픽 실측 반영 |
| v0.2 | 2026-11-17 | device tree model 출력으로 NVIDIA Jetson Orin NX 16GB와 AVerMedia NX215B 확정 · 배터리 저전압과 종료 안전 절차 추가 |
| v0.1 | 2026-11-17 | 업체 매뉴얼값, ai-lt01과 Jetson 네트워크 실측, NoMachine 접속, 실행 중 HDMI 분리 성공, 다음 읽기 전용 점검과 저수준 안전 관문 기록 |
