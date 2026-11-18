> 분류: Jetson 원격 관리 · 가역적 시스템 설정
> 작성: 오흥재 · 2026-11-18
> 대상: NVIDIA Jetson Orin NX 16GB / AVerMedia NX215B / L4T 36.4.7 / GDM Xorg / NoMachine 9.8.2
> 상태: 원인 진단·EDID 확보·installer 단위시험·실제 적용·HDMI 없는 재부팅 1회 통과 · 다음 정상 전원 사이클 반복 검증과 RViz/OpenGL 확인 대기

# HDMI 없는 NoMachine 1920×1080 물리 데스크톱

## 원인

현재 GDM은 자동 로그인으로 NVIDIA Xorg `:0`을 먼저 시작하고 NoMachine은 그 물리 데스크톱을 공유한다. HDMI가 없는 부팅에서는 NVIDIA Xorg가 `mode "NULL"`로 시작해 640×480 수준의 화면만 생긴다. HDMI를 연결하면 EDID를 읽어 1920×1080이 되고, 같은 부팅에서 HDMI를 다시 빼도 그 root 화면 크기는 유지된다.

기존 `/etc/X11/xorg.conf.headless`는 `dummy` Xorg driver를 사용한다. 이 방식은 NVIDIA 물리 X screen이 아니므로 RViz/OpenGL 검증에 쓰지 않는다. 이 bundle은 실제 모니터의 EDID를 NVIDIA driver에 제공해 HDMI가 없어도 `DFP-0` 1920×1080 screen을 만들며 CUDA나 NVIDIA OpenGL 경로를 dummy driver로 바꾸지 않는다.

공식 참고: [NoMachine Linux headless](https://kb.nomachine.com/AR03P00973) · [NoMachine stuck resolution](https://kb.nomachine.com/AR05S01127) · [NVIDIA X config options](https://download.nvidia.com/XFree86/Linux-aarch64/515.105.01/README/xconfigoptions.html)

## 확보된 현장 증거

- 2026-11-18 부팅은 `JRY HDMI (DFP-0)` EDID를 읽어 `1920 x 1080`으로 시작했다.
- HDMI 분리 뒤 Xorg log는 `DFP-0: disconnected`, `Setting mode "NULL"`을 기록했지만 root screen은 그 부팅 동안 1920×1080으로 남았다.
- EDID 원본은 Jetson `/home/nvidia/go2_diag/display/JRY-HDMI-1920x1080.edid`에만 보관한다: 256 bytes, SHA-256 `ce04c830518cef77cc02c3ed0f44f6eec030ffa8f8376b3f1fb7d72d7a5b68fd`.
- EDID에는 장치 식별 필드가 있을 수 있어 Git에는 넣지 않는다.

## 적용 전 검사

ai-lt01에서 bundle을 Jetson으로 복사한 뒤 검사한다.

```bash
scp -r inbox/jay/20261118-go2-headless-nvidia \
  nvidia@192.168.50.2:/home/nvidia/go2_diag/

ssh nvidia@192.168.50.2
cd /home/nvidia/go2_diag/20261118-go2-headless-nvidia
python3 -m unittest -v test_install_headless.py
python3 install_headless.py check
```

`check`가 EDID 256 bytes와 위 SHA-256, candidate/active config 존재를 보여야 한다.

## 적용

SSH와 HDMI 복구선을 모두 사용할 수 있을 때만 실행한다. 스크립트는 재부팅하지 않는다.

```bash
cd /home/nvidia/go2_diag/20261118-go2-headless-nvidia
sudo python3 install_headless.py apply
```

첫 적용 때 현재 `/etc/X11/xorg.conf`를 `/etc/X11/xorg.conf.pre-go2-headless`로 한 번만 보존한다. 반복 적용은 최초 백업을 덮지 않는다. HDMI를 분리한 상태에서 사람이 옆에 있을 때 Jetson을 정상 재부팅한다.

```bash
sudo reboot
```

## 재부팅 뒤 통과 조건

ai-lt01에서 SSH가 먼저 돌아오는지 확인하고 다음을 실행한다.

```bash
ssh nvidia@192.168.50.2 '
  systemctl is-active gdm
  /etc/NX/nxserver --status
  DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xrandr --current
  grep -E "CustomEDID|Virtual screen size|Setting mode" /var/log/Xorg.0.log
'
```

다음을 모두 만족해야 P1 통과다.

- HDMI가 물리적으로 빠져 있다.
- SSH와 NoMachine TCP 4000이 재접속된다.
- GDM/GNOME 자동 로그인 세션이 `:0`에 있다.
- `xrandr` current가 1920×1080이다.
- Xorg log가 custom EDID를 읽고 1920×1080 mode를 설정한다.
- NoMachine에서 GNOME desktop이 정상 크기로 보인다.
- 가능하면 `glxinfo -B`가 NVIDIA renderer를 표시하고 RViz가 열린다.
- 동일 조건 재부팅 2회가 모두 통과한다.

## 2026-11-18 첫 HDMI 없는 재부팅 결과

- installer `apply`: 최초 backup 생성, active config와 EDID 설치, EDID 256 bytes와 SHA-256 일치.
- 새 boot 시각 `2026-11-18 06:08:33 UTC`.
- kernel DRM physical connector: `/sys/class/drm/card1-HDMI-A-1/status=disconnected`.
- Xorg: NVIDIA driver가 `ConnectedMonitor=DFP-0`, `CustomEDID`를 읽고 `Virtual screen size configured to be 1920 x 1080`, `Setting mode "DFP-0:nvidia-auto-select+0+0"`을 기록했다.
- XRandR: current 1920×1080, 60 Hz. XRandR의 `HDMI-0 connected`는 custom EDID로 만든 논리 연결이고 물리 케이블 상태는 위 kernel DRM 값으로 구분한다.
- GDM, NVIDIA Xorg, GNOME shell과 NoMachine server/node/nxd가 active였고 사용자가 NoMachine에서 정상 Jetson desktop을 확인했다.
- `glxinfo`는 설치돼 있지 않아 별도 package를 추가하지 않았다. NVIDIA Xorg 사용은 log로 확인했고 실제 RViz/OpenGL 표시는 P3에서 재검증한다.

판정: HDMI 없는 1920×1080 재부팅 **1회 통과**. 설정은 `/etc/X11`에 영구 설치돼 이후 Jetson 재부팅과 Go2 전원 사이클에도 적용되는 구조다. 다음 정상 전원 사이클에서 같은 검사를 한 번 더 통과하면 반복성 관문을 닫는다. 이 검증만을 위해 로봇 전원을 다시 순환하지 않는다.

## SSH 복구

NoMachine 화면이 검거나 GDM이 실패하면 Wi-Fi 또는 직결 LAN SSH로 다음을 실행한다. 스크립트는 재부팅하지 않는다.

```bash
cd /home/nvidia/go2_diag/20261118-go2-headless-nvidia
sudo python3 install_headless.py rollback
sudo reboot
```

SSH도 안 되면 HDMI를 연결해 local terminal에서 같은 rollback을 실행한다. `UseDisplayDevice "none"`이나 dummy driver로 임의 전환하지 않는다.
