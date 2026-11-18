# Go2 X Jetson APP 설치 뒤 기준선 감사

> 측정: Claude 세션 (오흥재 지시, go2-x-sim-match-field-1117) · 2026-11-18
> 범위: 읽기·기록만. 패키지 설치, 로봇 명령 송신, 네트워크·카메라·전원 설정 변경 없음.
> 보안: 비밀번호, SSH 공개키 본문, 서버 주소, 인증 JSON, D435i serial은 기록하지 않았다.

오현민 팀원의 `foothold-app` Jetson 연결 작업 뒤, 기존 실기 기준선이 바뀌었는지 확인했다. 감사 중 Go2 X는 사용자가 순정 앉기 상태로 두었고 APP 프로세스는 실행하지 않았다.

## 확정된 변경

- `/home/nvidia/foothold-robot-r4/`: 완성된 r4 설치본. Python package `foothold-agent 0.2.0`, CycloneDDS `0.10.2`, NumPy `1.26.4`, OpenCV `4.10.0.84`가 사용자 전용 venv에 있다.
- `/home/nvidia/foothold-robot/`: r5 설치 도중 중단된 폴더. `INCOMPLETE`가 있고 `launch.py`, `connection.json`이 없다. 설치 로그는 wheel 설치 도중 끝난다.
- `/home/nvidia/.config/systemd/user/foothold-robot.service`: 사용자 부팅 자동실행 서비스가 추가·enable됐다. 현재 r5의 없는 `launch.py`를 실행하려다 부팅 뒤 6회 실패했고 `failed`, `ExecMainStatus=2`다.
- `/home/nvidia/foothold-robot-run.log`: 과거 r3/r4 실행 기록. 고수준 Unitree Sport SDK `StopMove`가 실제 호출됐고 성공 code 0과 실패 code 3104가 모두 있다. `StandUp`, `BalanceStand`, `StandDown`, 저수준 `LowCmd` 호출 문자열은 없다.
- `authorized_keys`에 팀원 접속용 공개키 한 줄이 추가됐다. 키 본문은 저장소에 기록하지 않는다.

## 바뀌지 않은 기준선

| 항목 | 재확인값 |
|---|---|
| Jetson | NVIDIA Jetson Orin NX 16GB - AVerMedia NX215B |
| OS | Ubuntu 22.04.5 · L4T R36.4.7 · kernel 5.15.148-tegra · 15W mode 2 |
| Jetson↔Go2 | `enP8p1s0=192.168.123.99/24`; Go2 `192.168.123.161` 내부망 |
| Wi-Fi | `wlP1p1s0=192.168.21.103/23` (DHCP이므로 주소 영구 고정으로 보지 않음) |
| NoMachine | 9.8.2, TCP 4000 listener 정상 |
| headless Xorg | physical HDMI disconnected, 1920×1080. 기존 CustomEDID와 xorg.conf hash 유지 |
| D435i | `8086:0b3a`, Jetson USB tree `5000M` |
| system packages | 당일 apt/dpkg 설치 기록 없음. Docker 없음 |

`5000M`은 이 조회 시점에 D435i와 Jetson 사이 USB link가 5,000 Mbit/s SuperSpeed로 협상됐다는 뜻이다. 기존 업체 젠더가 항상 이 속도를 유지한다거나 장시간 reset이 없다는 뜻은 아니다. 과거에는 같은 실기 구성 점검 중 `480M` fallback과 SuperSpeed disconnect가 있었고, 180초 기록에는 D435i frame number `287→0` reset과 약 1초 공통 정지가 있었다. 따라서 사용자가 새로 구입한 C-to-A 젠더는 불필요해진 것이 아니다. 기존 젠더와 신규 젠더를 A/B/C로 구분해 재연결·5분·30분 안정성을 비교해야 운영 부품을 확정할 수 있다.

APP의 설치본에는 ONNX, PT, `contract.json`, 배포 YAML이 없다. 따라서 정본 3 보행 정책은 설치·실행되지 않았다. APP의 depth 코드는 ROS metric depth를 사람이 보는 색상 JPEG로 축소하는 경로이며, 정책의 640×480→60×60·10 Hz 전처리가 아니다. 현재 APP 경로를 정책 입력 parity의 근거로 쓰면 안 된다.

현재 `/lowcmd`에는 bare DDS publisher 1개와 subscriber 1개가 보인다. APP 프로세스와 TCP 9539 listener는 없으며, APP 로그에도 `LowCmd` 송신 증거가 없다. 이 publisher는 순정 로봇 내부 명령 스트림으로 취급하되, 저수준 실험 전에는 source ownership을 별도로 검증한다.

`foothold-robot.service`의 문제는 “현재 백그라운드에서 움직이고 있다”가 아니다. 현재는 r5 `launch.py`가 없어 failed 상태이고 start-limit 뒤 저절로 다시 실행되지 않으므로, 재부팅·service 수동 시작·r5 복구가 없다면 지금의 읽기 전용 측정을 방해하지 않는다. 문제는 서비스가 여전히 enabled라서 r5 파일이 완성된 뒤 다음 로그인/부팅에는 사용자 확인 없이 APP가 시작될 수 있다는 점이다. APP는 시작·연결 끊김·output stall 때 안전 동작으로 고수준 `StopMove`를 호출하므로 순정 조이스틱, 측정 자세, 장래 저수준 정책과 command ownership이 겹칠 수 있고 실험 원인 분리를 깨뜨린다. 비활성화는 APP 파일이나 수동 실행 기능을 지우지 않지만, 팀원의 자동접속 검증에는 영향을 주므로 사용자와 팀원의 운용 의도를 확인한 뒤 적용한다.

## D435i 내부값 재확인

앉은 자세에서 내부값 확인용으로 640×480×30 depth를 150프레임 읽었다. 자세 때문에 무효 depth 비율은 평지 Stand 정본으로 쓰지 않는다. 내부값은 이전 실측과 일치했다.

| 항목 | 값 |
|---|---:|
| width × height | 640 × 480 |
| measured fps | 29.9770 |
| fx, fy | 387.124359, 387.124359 |
| cx(ppx), cy(ppy) | 319.636017, 242.064362 |
| distortion | model 4 = Brown-Conrady, coeffs `[0,0,0,0,0]` |
| depth scale | 0.001 m / raw unit |

앉은 상태의 D435i accel↔Go2 projected-gravity 상대각을 한 번 읽었을 때 35.225°였다. 기존 최종 Stand 주행 후 35.023°와 자세가 다르므로 장착 drift 판정에 쓰지 않는다. 같은 순정 Stand 자세에서 독립 3회 재측정한 뒤에만 전후 차이를 판정한다.

## 재현 명령

아래 명령은 모두 receive-only 또는 로컬 상태 조회다. `<jetson>`은 `nvidia@192.168.21.103` SSH 접속을 뜻한다.

```bash
# 서비스와 실행 상태
systemctl --user is-enabled foothold-robot.service
systemctl --user show foothold-robot.service \
  -p ActiveState -p SubState -p Result -p ExecMainStatus -p NRestarts
ss -lntp | grep -E ':(22|4000|9539)([[:space:]]|$)'

# 장치·망·D435i USB 속도
tr -d '\0' </proc/device-tree/model; echo
ip -4 -br addr
ip route
lsusb -t
lsusb | grep -Ei 'Intel|RealSense|8086'

# DDS endpoint 메타데이터만 조회
source /opt/ros/humble/setup.bash
source /home/nvidia/wego_ws/install/setup.bash
ros2 topic info /lowcmd -v

# 기존 receive-only D435i 내부값 측정기
export LD_LIBRARY_PATH=/home/nvidia/go2_diag/librealsense-rsusb-v2.58.4/build-rsusb/Release:/usr/local/lib:${LD_LIBRARY_PATH:-}
/home/nvidia/go2_diag/sim_match_measure/build_imu/depth_capture /tmp/go2-intrinsics-audit.npy

# 기존 receive-only 상대각 도구. 사용자는 순정 자세만 바꾸며 프로그램은 명령을 만들지 않는다.
DISPLAY=:0 XAUTHORITY=/home/nvidia/.Xauthority \
  /home/nvidia/go2_diag/sim_match_measure/build_imu/relative_pitch_live enP8p1s0
```

## 다음 안전 관문

1. 자동실행 서비스는 사용자 승인 뒤 `systemctl --user disable --now foothold-robot.service`로 비활성화하고 상태를 다시 기록한다. 삭제하지 않는다.
2. 같은 순정 Stand에서 상대각을 독립 5초씩 3회 재확인한다. 측정기는 publisher나 motion client를 만들지 않는다.
3. APP 재설치·재실행은 r5 설치 실패 원인과 고수준 command ownership을 팀원이 설명하고, 조이스틱·APP·저수준 정책의 단일 소유권 규칙을 확정한 뒤 별도 관문에서 한다.
4. 시뮬 lead의 추가 측정은 정책 전처리와 APP 영상 전처리를 구분해 새 원시 폴더에 저장한다.
