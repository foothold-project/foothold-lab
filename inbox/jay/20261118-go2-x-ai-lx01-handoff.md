> 분류: 현장 실기 인수인계
> 작성: Codex 세션 (오흥재 지시, Go2 X commissioning) · 2026-11-18
> 근거: Issue #557 · PR #837~#858 · 20261117~18 현장 실측과 Jetson read-only 감사
> 요지: ai-lt01에서 진행한 Go2 X 실기 확인을 ai-lx01의 AI가 같은 안전선과 원자료로 이어 간다.
> 상태: 2026-11-18 배터리 충전 중 중단점. 다음 전원 ON 첫 작업은 기존 원본 회수다.
> 판: v1.0

# Go2 X ai-lt01 → ai-lx01 인수인계

## 1. 이 문서의 역할

대화 기억이 아니라 `foothold-lab main`을 공용 정본으로 쓴다. Jetson의 `/home/nvidia/go2_diag/records/`는 임시 수집·복구 사본이며 팀 공유 정본이 아니다. 각 측정 뒤 원본과 실행 명령을 이 저장소의 assets로 회수하고 SHA-256을 대조한 뒤 PR로 main에 병합한다.

비밀번호, SSH 개인키, 인증 token, 장치 serial은 Git에 넣지 않는다. ai-lt01의 개인키를 ai-lx01로 복사하지 말고 ai-lx01에서 별도 키 쌍을 만들어 공개키만 Jetson에 등록한다.

## 2. ai-lx01에서 먼저 받을 것

저장소가 이미 있으면 로컬 변경을 먼저 확인하고 덮지 않는다.

```bash
cd <foothold-lab의 실제 경로>
git status --short --branch
git switch main
git pull --ff-only origin main
git lfs pull
git rev-parse HEAD
```

저장소가 없으면 접근 권한이 있는 계정으로 아래 저장소를 clone한다.

- https://github.com/foothold-project/foothold-lab
- 연속 작업 Issue: https://github.com/foothold-project/foothold-lab/issues/557

이 인수인계가 처음 main에 들어간 기준 commit은 PR #858 뒤 `1af9b9e8828c582fafa86da2cfebd24f0c5a6498`보다 새 commit이어야 한다. 정확한 최신값은 `origin/main`을 우선한다.

## 3. 현재 확정된 장비와 통신

| 항목 | 확정값 | 주의 |
|---|---|---|
| 로봇 | 업체 전달명 Go2 X, EDU와 같은 SDK 저수준 제어 가능 | 본체/펌웨어 식별값으로 명칭 보강은 남음 |
| Jetson | NVIDIA Jetson Orin NX 16GB, AVerMedia NX215B | Ubuntu 22.04.5, L4T R36.4.7, 15W mode 2 |
| 노트북↔Jetson 직결망 | 노트북 `192.168.50.1/24` ↔ Jetson `192.168.50.2/24` | `.50.1`은 ai-lt01과 ai-lx01 중 한 기기만 사용. 동시 연결 금지 |
| Jetson↔Go2 내부망 | `enP8p1s0=192.168.123.99/24` ↔ Go2 `192.168.123.161` | 현 구성의 고정값이지만 부팅 뒤 매번 읽어 확인 |
| 원격 화면 | NoMachine TCP 4000 | custom EDID 적용 뒤 HDMI 없는 1920×1080 부팅 2회 통과 |
| SSH | Jetson TCP 22 | ai-lx01의 새 공개키를 별도 등록. 비밀번호·개인키 기록 금지 |
| Depth camera | Intel RealSense D435i, `8086:0b3a`, firmware 5.17.0.10 | 현재 조회 `5000M`은 순간 협상값이고 장시간 안정성 통과가 아님 |
| LiDAR | Unitree L2 운용 판정 | cloud 약 62k, 15.35~15.38 Hz, IMU 약 250 Hz, packet loss 0 |

ai-lx01의 유선 인터페이스 이름은 ai-lt01과 다를 수 있으므로 복사하지 말고 먼저 확인한다.

```bash
ip -br link
ip -br addr
nmcli device status
```

직결 profile을 만들 때는 실제 인터페이스 이름을 사용한다. 기존 profile이 있으면 중복 생성하지 않는다. ai-lt01과 ai-lx01을 동시에 `.50.1`로 연결하지 않는다.

## 4. 현재 물리·센서 기준선

### 카메라

- D435i optical center 위치의 현재 근사: 몸 중심 기준 `(x,y,z)=(+0.350, 0, +0.070) m`.
- 시뮬 기준 `(x,z)=(+0.250,+0.120) m`보다 약 10 cm 앞, 약 5 cm 낮다.
- 최종 브라켓 체결 직후 몸통 기준 상대 pitch: `35.068°`, 표준편차 `0.004°`.
- Classic 좌회전 한 바퀴와 우회전 한 바퀴 뒤: `35.023°`, 표준편차 `0.023°`, 변화 `-0.045°`.
- 앉은 자세에서 읽은 `35.225°`는 자세가 달라 drift 판정에 쓰지 않는다.
- depth intrinsics: 640×480, 약 29.977 fps, `fx=fy=387.124359`, `cx=319.636017`, `cy=242.064362`, Brown-Conrady 계수 전부 0, depth scale 0.001 m/raw unit.
- 기존 Classic 180초 기록: 5,365 frame, 평균 29.81 fps, 무효/범위 밖 11.18%. frame number `287→0` reset과 약 1초 공통 정지가 1회 있었다.

### 안전 사건

- 과거 순정 Damping→Stand 직후 앞 hip가 78/81°C까지 올라가고 전면 LED가 적색 점멸했다.
- 당시 FR `reserve[0]=0x04`, motor lost 0, BMS SOC 81%였다.
- 냉각·재부팅 뒤 순정 Stand와 Classic 주행에서는 최고 56°C, reserve nonzero 0, errorlist 0으로 재발하지 않았다.
- 이 후속 표본은 업체 공식 안전 판정이 아니다. 업체 답변 전에는 저수준 정책이나 새 APP 제어 명령을 보내지 않는다.
- `SportModeState.error_code=1001`은 설치 SDK에서 Damp API ID이므로 그 값 하나를 fault code라 부르지 않는다.

## 5. 팀원 APP 감사 결과

- `/home/nvidia/foothold-robot-r4`: 완성된 r4 설치본. `foothold-agent 0.2.0`과 사용자 venv가 있다.
- `/home/nvidia/foothold-robot`: 중단된 r5 설치본. `INCOMPLETE`가 있고 `launch.py`, `connection.json`이 없다.
- user service `foothold-robot.service`는 enabled지만 r5의 없는 `launch.py` 때문에 부팅 뒤 6회 실패하고 현재 failed다.
- 과거 APP는 고수준 Sport SDK `StopMove`를 호출했다. 성공 code 0과 실패 code 3104 기록이 있다.
- 정본 3 ONNX/PT/contract는 APP에 설치되지 않았고 저수준 정책 실행 증거도 없다.
- 현재 APP process와 TCP 9539 listener는 없었다. service를 임의 disable하거나 r5를 복구하지 않았다.
- 위험은 현재 APP가 몰래 움직이는 것이 아니라, r5가 완성된 뒤 enabled service가 자동 시작되어 조이스틱·향후 저수준 정책과 command ownership이 겹칠 가능성이다. 팀원의 자동실행 의도를 먼저 확인한다.
- 현재 APP의 D435i 경로는 화면용 색상 JPEG다. 정책용 640×480→60×60·10 Hz depth 전처리가 아니다.

## 6. 지금 중단된 정확한 상태

- 사용자가 Go2와 Jetson을 끄고 배터리를 충전하러 갔다.
- 끄기 전 앉은/Damping 상태에서 15초 receive-only monitor를 실행했다.
  - SOC 21→20%.
  - FR/FL hip 32/31°C, 전체 최고 37°C(RR hip).
  - reserve nonzero 0, lost 0, errorlist 0.
  - kp max 0, kd max 3, sport marker 1001.
  - state age 최대 약 3.19 ms, cmd age 최대 약 6.76 ms, sport age 약 5.35 ms.
- 원본은 아직 Jetson에만 있다.
  - `/home/nvidia/go2_diag/records/20261118-priority-readonly-prestand/monitor.csv`
  - `/home/nvidia/go2_diag/records/20261118-priority-readonly-prestand/console.log`
  - `/home/nvidia/go2_diag/records/20261118-priority-readonly-prestand/summary.json`
- 당시 기록한 SHA-256 앞부분은 각각 `c41328d7…`, `1b039cfe…`, `6c7d1a1a…`다. 다음 부팅 때 Jetson에서 전체 해시를 다시 읽어 사본과 대조한다.
- ai-lt01의 assets 목적 폴더는 만들었지만 전원 OFF가 먼저여서 파일을 회수하지 못했다. 빈 폴더를 측정 완료로 보지 않는다.

## 7. 다음 전원 ON 직후 순서

아래 1~6은 설치·설정 변경과 로봇 명령 없이 먼저 한다.

1. Jetson SSH 접속 후 `foothold-robot.service`가 여전히 failed인지, APP process와 TCP 9539가 없는지 읽는다.
2. SOC, 모터 온도, reserve, DDS age를 15초 receive-only로 읽는다. 배터리가 충분하지 않거나 이상 징후가 있으면 Stand로 가지 않는다.
3. 가장 먼저 위 prestand 원본 세 파일을 작업 노트북의 assets로 `scp`하고 Jetson 원본과 사본의 전체 SHA-256을 대조한다.
4. 비밀번호·token·개인키·장치 serial이 없는지 검사하고 README에 실행 명령과 조건을 기록한 뒤 PR/main에 반영한다. Jetson 원본은 삭제하지 않는다.
5. main의 보강된 `summarize_monitor.py`를 Jetson 측정 kit에 복사한다. 패키지 설치나 service 변경은 하지 않는다.
6. 장기 receive-only monitor를 먼저 시작하고 화면과 CSV callback age가 갱신되는지 확인한다.

위 조건이 정상일 때만 사용자가 순정 조이스틱으로 Stand 1회를 한다.

7. 같은 Stand에서 D435i↔Go2 상대각을 5초씩 독립 3회 기록한다.
8. 같은 기록에서 SDK `body_height` 평균·모집단 표준편차·최소·최대를 구한다.
9. 사용자가 바닥→몸 중심, 바닥→D435i optical center 높이를 자로 재고 기준점을 사진과 함께 기록한다.
10. 사용자가 다시 안전한 앉기/Damping으로 전환한다. 모든 원본을 즉시 Git assets로 회수한다.
11. 그다음에만 기존 젠더와 새 젠더를 A/B/C로 표시해 동일 포트·케이블에서 재연결 5회와 후보당 5분 depth/color/IMU 안정성을 비교한다.

## 8. 금지선

- AI나 진단 프로그램이 Stand, Damp, StopMove, Sport command, LowCmd를 보내지 않는다. 순정 자세 변경은 사용자 조이스틱만 사용한다.
- 업체 열 사건 공식 판정, 조이스틱 E-stop 확인, 2인 매달기 관문 전에는 저수준 정책을 송신하지 않는다.
- 사용자와 팀원의 합의 전에는 `foothold-robot.service`를 disable/start하거나 r5를 복구하지 않는다.
- 시스템 librealsense, JetPack, ROS package, firmware를 진단 편의를 위해 임의 변경하지 않는다.
- 새 젠더를 샀다는 사실이나 한 번의 `5000M`만으로 USB 경로를 통과 처리하지 않는다.
- Jetson 원본을 Git 회수·해시 검증 전에 지우지 않는다. 검증 뒤에도 사용자 승인 없이 지우지 않는다.
- repo의 다른 사용자 untracked/dirty 파일을 stage하거나 수정하지 않는다.

## 9. 정본 읽기 순서

1. [전체 commissioning 작업목록](https://github.com/foothold-project/foothold-lab/blob/main/inbox/jay/20261118-go2-x-commissioning-worklist.md)
2. [시뮬 대 실기 실측 체크리스트](https://github.com/foothold-project/foothold-lab/blob/main/inbox/jay/20261117-go2-x-sim-match-checklist.md)
3. [팀원 APP 설치 뒤 read-only 감사](https://github.com/foothold-project/foothold-lab/blob/main/inbox/jay/20261117-go2-x-sim-match-checklist-assets/20261118-app-baseline-audit/README.md)
4. [receive-only boot gate 도구](https://github.com/foothold-project/foothold-lab/tree/main/inbox/jay/20261118-go2-readonly-boot-gate)
5. [현장 인수 기록](https://github.com/foothold-project/foothold-lab/blob/main/inbox/jay/20261117-go2-x-jetson-field-intake.md)
6. [Go2 제원·시뮬 대 실기](https://github.com/foothold-project/foothold-lab/blob/main/docs/research/20260908-go2-spec-sim-vs-real.md)
7. [정본 3 정책 bundle](https://github.com/foothold-project/foothold-lab/tree/main/inbox/jay/20261103-policy-handoff/start-m15500-app)
8. [연속 작업 Issue #557](https://github.com/foothold-project/foothold-lab/issues/557)

## 10. ai-lx01 AI 시작 프롬프트

아래 문장을 그대로 전달한다.

```text
foothold-lab main을 git pull하고 `inbox/jay/20261118-go2-x-ai-lx01-handoff.md`를 처음부터 끝까지 읽어라. 이어서 그 문서 9절의 정본을 순서대로 읽고 Issue #557의 최신 댓글을 확인하라.

너의 역할은 Go2 X + Jetson Orin NX 16GB + D435i + L2의 실기 commissioning을 이어 가는 read-only 진단·기록 담당이다. 사용자 명시 승인 전에는 설치·설정 변경·서비스 변경·로봇 명령을 하지 마라. 특히 APP의 StopMove/Sport command/LowCmd, 저수준 ONNX 송신은 금지한다. 순정 자세 변경은 사용자가 조이스틱으로만 한다.

현재 로봇은 배터리 충전을 위해 꺼져 있다. 다음 전원 ON 첫 작업은 새로운 측정이 아니라 Jetson `/home/nvidia/go2_diag/records/20261118-priority-readonly-prestand/`의 세 원본을 작업 노트북으로 회수하고 전체 SHA-256을 대조하는 것이다. 그 뒤 service/process/port 9539와 SOC·온도·reserve를 receive-only로 확인하고, 안전할 때만 사용자 순정 Stand 아래 상대각 3회와 SDK/자 몸높이를 측정한다.

모든 숫자는 그 턴에 읽은 원자료와 경로를 붙여라. Jetson은 임시 원본 보관소이고 팀 공유 정본은 foothold-lab main이다. 측정마다 assets 폴더, 실행 명령, SHA-256, 확정/미확정을 기록하고 PR로 main에 병합하라. 비밀번호·개인키·token·장치 serial은 Git에 쓰지 마라. 다른 사람의 dirty/untracked 파일은 건드리지 마라.

시작 보고에는 현재 main commit, 읽은 문서 목록, 확정된 안전 금지선, 다음 한 단계만 적어라. 아직 로봇이 꺼져 있으면 실행하지 말고 회수·측정 명령만 점검해서 준비하라.
```

## 변경 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-11-18 | ai-lt01 실측·APP 감사·안전 사건·카메라/USB/L2 기준선, Jetson 미회수 원본, ai-lx01 네트워크·SSH 주의, 다음 전원 ON 순서와 AI 시작 프롬프트 통합 |
