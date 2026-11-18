# Go2 X · Jetson · D435i 현장 인수 기록

> 분류: 현장
> 작성: 오흥재 · 2026-11-17 17:24
> 근거: 업체 제공 「Unitree Go2 + Intel RealSense D435i 제어기 사용자 매뉴얼」 · 2026-11-17 현장 터미널 출력 · NoMachine 접속 실측 · 정본 3 전달 문서
> 요지: 교체받은 Go2 X 계통의 현재 연결과 원격 접속을 확정값 · 업체 문서값 · 미확인값으로 나누고, 저수준 정책 시험 전 점검 순서를 고정한다
> 상태: 현장 기록 v0.13 · D435i↔Go2 상대각 35° 최종 체결 · Classic 좌·우 ㅁ자 주행 전후 유지성 통과 · 약 1초 stream/DDS 정지 별도 관문
> 판: v0.13

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

출처: [Unitree Go2 사용자 매뉴얼](https://marketing.unitree.com/article/en/Go2/User_Manual.html) · [Unitree Go2 배터리와 BMS 보호](https://www.unitree.com/go2/battery/)

## 7. 팀원이 이어서 볼 위치

- 전체 실행 순서: [`20261118-go2-x-commissioning-worklist.md`](20261118-go2-x-commissioning-worklist.md)
- 정본 3 전달: [`HANDOFF-START-m15500-CANON3.md`](20261103-policy-handoff/HANDOFF-START-m15500-CANON3.md)
- 앱 전달과 남은 실기 경로: [`APP-HANDOFF-1117.md`](20261103-policy-handoff/APP-HANDOFF-1117.md)
- 시뮬 대 실기 제원: [`docs/research/20260908-go2-spec-sim-vs-real.md`](../../docs/research/20260908-go2-spec-sim-vs-real.md)
- 연속 작업 이슈: [foothold-lab #557](https://github.com/foothold-project/foothold-lab/issues/557)
- NX215 공식 제품 페이지: [AVerMedia NX215](https://www.avermedia.com/professional/product-detail/NX215)
- NoMachine 제품별 연결 제한: [NoMachine FAQ](https://www.nomachine.com/support/faq)

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
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
