> 분류: 실사 기록 · FOOTHOLD 앱 「실기 Go2 X 가 붙었을 때」 끝에서 끝까지 동작 (코드 읽기)
> 작성: Claude 세션 app-design-lx (오흥재 지시) · 2026-11-20 00:4x · 하위 조사가 쓰고 app-design-lx 가 코드 행을 대조 (fleet.tsx:146-151 · drive_media.py:71-74 · realtime.py:2235 · models.py:165-167 · phone.ts:47)
> 근거: foothold-app `origin/dev` `2b19f592` 의 코드 · 문서 / foothold-lab `app-design-1119` 의 11/17~11/19 현장 기록 (`inbox/jay/...`) · 실행한 것 없음 (로봇 · 서버 · Jetson 접속 0, 시험 실행 0)
> 요지: 실기 화면은 「Jetson 위 setup 프로그램 → 서버 WS → 화면 WS」 한 줄로 값이 붙는다. 서버가 조종을 허용 (server_drive_allowed) 해야 카메라 · 라이다 · 뎁스 · 관절 그림 · 온도가 열린다. 지금 Jetson agent 는 돌고 있지 않다는 기록 (11/18 · 11/19) 만 있고, Go2 X 가 앱 화면까지 간 기록은 찾지 못했다.
> 상태: v1.0 · 코드 읽기만. 아래 「미확인」 은 재지 않은 것. 팀장 11/20 00:29 지시 「로봇이 앱에 연결되지 않았는데 전체를 제대로 파악했나」 에 대한 답

# 실기 Go2 X 연결 · 끝에서 끝까지

이 글의 파일 경로는 모두 `apps/...` = foothold-app 사본 기준이다. 행 번호는 `2b19f592` 기준.

## 0. 한 줄 그림 (말로)

Go2 본체 (DDS 토픽 `rt/lowstate` · `rt/sportmodestate` 등) → 랜선 `enP8p1s0` → Jetson 의 `foothold_agent.setup` (headless · onboard) → 인터넷 wss `/api/v1/agent/ws` → NaverCloud 서버 (`fh_server/realtime.py`) → 브라우저 wss `/api/v1/ws` (state 구독 10 Hz) → 웹 「로봇」 탭 (`screens/fleet.tsx`) · 세 칸 조종 화면 (`pcdrive.tsx`).
영상 · 점은 따로: agent → HTTP POST `/api/v1/agent/drive-media/{rgb|lidar|depth}` → 서버 → 브라우저 WS `/api/v1/robots/{id}/drive-media/{ch}`.

폰 직결 (nearby → 출입증 → 직접 hello) 은 **Jetson 설치판에는 없다**. 그 길은 손으로 켜는 `python -m foothold_agent.go2_direct` (폰 포트 리스너) 에만 있다 (4 절).

---

## 1. 연결 사슬과 단계별 실패 화면

### 1.1 Jetson 에 설치 · 기동

| 단계 | 무엇이 · 어디서 | 근거 |
|---|---|---|
| 설치 | 준비 PC 에서 `build_jetson_bundle.py --build` 로 한 파일을 만들고, Jetson 에서 `sh ./install.sh --server <https 원점> --nic enP8p1s0 --port 9539 --install`. 설치 위치는 `~/foothold-robot` 하나. 다 끝나야 `launch.py` 가 생기고 `INCOMPLETE` 가 지워진다 | `apps/agent/JETSON-ONBOARD.md:46-116` |
| 설정 파일 | `~/foothold-robot/connection.json` (server · nic · port) 를 `launch.py` 가 읽는다 | `apps/agent/installer/install_jetson_bundle.py:27-43` |
| 실제 명령 | `launch.py` 가 `venv/bin/python -I -m foothold_agent.setup --headless --onboard --config ~/foothold-robot/private/agent.json --wheel-dir bundle/wheels --server <server> --nic <nic> --port <port>` 로 바뀌어 실행. 이때 `FH_RECORD=0` (기록 저장 끔) · 캐시 폴더 지정 | `install_jetson_bundle.py:36-42` |
| 자동 시작 | `enable-autostart.sh` 가 `~/.config/systemd/user/foothold-robot.service` 를 만들고 `enable --now`. `Restart=on-failure` · `RestartSec=20` · `StartLimitBurst=5`/600 s · 기록은 `~/foothold-robot-run.log` | `installer/jetson_autostart.py:20-31` · `JETSON-ONBOARD.md:170-186` |
| 토큰 | 처음에는 없음. 짝짓기 (1.2) 로 받은 토큰을 `private/agent.json` (0600) 에 저장해 다음 실행에 다시 쓴다. 환경 변수 · 명령 인자로 토큰을 받지 않는다 | `setup/__main__.py:34-39,105` · `setup/storage.py:109-163` |
| 서버 주소 | `--server` (https 만, http 는 127.0.0.1 만) 또는 저장된 `agent_ws_url` 에서 복원. 저장된 것과 다른 서버면 거부 | `setup/pairing.py:25-36` · `setup/__main__.py:35-39` |
| 상태 화면 | 로봇 컴퓨터 안 `http://127.0.0.1:<port>` 만 (loopback). 6 자리 코드 · QR 은 이 화면에만 뜬다. 원격으로 보려면 승인된 화면 접근 수단 (NoMachine 등) 이 따로 필요 | `setup/__main__.py:232-236` · `JETSON-ONBOARD.md:147-155` |

### 1.2 Go2 와 DDS 연결 → 기체 확인 → 짝짓기

| 순서 | 무엇이 일어나나 | 근거 |
|---|---|---|
| ① 자동 점검 | 설치 해시 · ARM ELF · import 경로 검사 (`installation_ready`). 실패해도 계속 가지만 조종 SDK 는 못 만든다 | `setup/__main__.py:32-33` · `setup/runtime.py:157,227` |
| ② NIC 고르기 | 물리 유선 · Go2 내부 망 (`<GO2_SUBNET>`) · 기본 경로 없음 후보 하나 (`--nic`) | `GO2-SERVER-DRIVE.md` 옛 절차 3 항 · `setup/discovery.py` |
| ③ DDS 구독 | `go2_readonly.sdk.Subscriptions` 로 `rt/lowstate` · `rt/sportmodestate` 두 구독만 (명령 writer 없음). 뎁스 토픽 읽기도 같이 시작 | `setup/__main__.py:49-51` · `GO2-READONLY.md:130-133` |
| ④ 기체번호 | LowState `sn[0]-sn[1]` 이 0.2 s 안에 새로 와야 함. 10 s 안에 못 받으면 `PermissionError` 로 끝 | `setup/runtime.py:42-79` · `setup/__main__.py:52-67` |
| ④-b 번호가 `0-0` | `--onboard` 면 로봇 몸 `.161` 의 MAC 으로 신원을 만들고 **사람 확인 없이** 진행 (11/19 `e6192f21`). 저장된 로봇과 MAC 이 다르면 거부 | `setup/identity.py:107-132` |
| ⑤ 짝짓기 시작 | 저장된 인증이 없거나 `--repair` 면 `POST /api/v1/pairing/start {model, robot_serial}` → 6 자리 코드 · poll 비밀 (10 분) | `setup/pairing.py:66-76` · `fh_server/pairing.py:22,117-141` |
| ⑥ 사람이 웹에서 | 담당 운영 관리자 (OPERATOR 만) 가 웹 «+ 로봇 연결하기 → 새 로봇 추가» 에서 6 자리 (또는 QR `foothold-pair:<6자리>`) 를 넣고 (`/pairing/claim`) 이름을 정함 (`/pairing/{id}/confirm`). 이때 `Robot(owner_user_id=그 사람, serial=기체번호, agent_token_hash)` 가 생김 | `fh_server/pairing.py:81-85,143-205` · `apps/web/src/pairing.tsx:13,120-126` |
| ⑦ 토큰 받기 | agent 가 2 s 마다 poll → `paired` 면 `robot_id · agent_token · agent_ws_url` 를 받아 저장 | `setup/pairing.py:78-92` · `setup/__main__.py:82-107` |

### 1.3 서버 WS 연결 · 인증 · 상태 보내기

| 항목 | 값 | 근거 |
|---|---|---|
| 주소 · 인증 | `agent_ws_url` (= `/api/v1/agent/ws`) 에 `Authorization: Bearer <토큰>`, 받는 크기 4096 B, 연결 제한 2 s | `link/client.py:297-303` · `fh_server/realtime.py:2450` |
| 첫 말 | `hello` (`proto: fh-agent/2`, 장치 목록, `latched`, `stop_gen`). 서버는 3 s 안에 hello 가 없으면 끊음 (`HELLO_TIMEOUT`) | `link/session.py:322-340` · `realtime.py:47,2006-2026` |
| 서버가 하는 일 | 토큰 다시 확인 → `peer.server_drive = drive_enabled(rid)` → 이전 현장 승인 지움 → `field_approval(expires_at=None)` 보냄 → 조종권 회수 | `realtime.py:2027-2061` |
| 상태 주기 | agent 는 0.05 s 마다 돌고 0.1 s 마다 `state` 1 개 (10 Hz) | `link/client.py:15,222-230` · `link/session.py:23,306-312` |
| 다시 붙기 | 끊기면 1 s 부터 두 배씩 최대 10 s 간격. 4401 · 4403 은 다시 붙지 않음 (`ReconnectForbidden`) | `link/client.py:16,74-75,389` |
| 서버 쪽 침묵 | agent 에게서 3 s 동안 아무 것도 안 오면 서버가 닫음 (1013) | `realtime.py:2318-2321` |

### 1.4 단계가 실패하면 화면에 무엇이 뜨나

| 실패한 곳 | Jetson (로그 · 9539 화면) | 웹 로봇 탭 (담당 운영 관리자) |
|---|---|---|
| 설치 미완 (`launch.py` 없음) | systemd 가 6 번 안팎 실패 후 `failed` (11/18 · 11/19 실제 기록, 5 절) | 로봇 자체가 없음 (짝짓기 전) 또는 «로봇 연결을 기다리고 있습니다» |
| DDS 못 받음 (10 s) | `SETUP_FAILURE type=PermissionError reason=connection_failed` · «연결을 거부했습니다. 랜선·로봇 상태·서버 연결을 확인하세요» · 종료 코드 2 → 20 s 뒤 재시도 | 서버에 안 붙었으니 «로봇 연결을 기다리고 있습니다» · 조종 준비 2 단계 «노트북 연결 프로그램을 확인하세요» (`fleet.tsx:78,165`) |
| `0-0` 인데 MAC 못 읽음 | «로봇 몸의 연결 주소를 확인하지 못했습니다…» · `identity_unavailable` | 위와 같음 |
| 짝짓기 거절 · 만료 | `pairing request rejected` / `pairing expired` → 종료 2 → 재시작 때 새 코드 | 웹 코드 입력 칸에서 오류 (`pairing.tsx`) |
| 서버가 토큰 거부 (4401/4403) | «로봇 컴퓨터의 연결이 해제되었습니다. 담당자에게 새 등록을 요청하세요» · `reconnect_forbidden` · 종료 2 (systemd 가 다시 띄워도 또 거부 → 시작 한도에서 멈춤, 코드 읽기 추정) | 로봇은 «끊김» 또는 «연결 전» |
| WS 일시 끊김 | agent 는 STOP · 잠금 후 1~10 s 간격으로 다시 붙음 | 한 번 받은 로봇은 빨강 «로봇과의 연결이 끊겼습니다» · 값은 회색 «마지막 수신값» (`fleet.tsx:75,104`) |
| 브라우저 ↔ 서버 끊김 | (무관) | «서버와의 연결이 끊겼습니다» (`fleet.tsx:76`) |

---

## 2. 로봇 탭 화면 상태표

웹은 서버 목록 (`RobotSummary`) 위에 화면 WS 의 `ScreenState` 를 얹어 판정한다 (`rt.ts:514-528` `withLive`). 서버는 agent 소켓이 있으면 `connection=ONLINE`, 마지막 state 가 3 s 넘으면 state 를 빈 것으로 본다 (`fh_server/robots.py:44-64`). 화면의 갈래는 `fleet.tsx:52-53` `kindOf`.

### 2.1 상태별로 보이는 것 · 열리는 것

| 상태 | 판정 근거 | 운영 관리자 (담당, PC) | 총괄 (PC) | 폰 (운영 관리자) |
|---|---|---|---|---|
| 연결 전 (agent 가 한 번도 안 붙음) | `connection=OFFLINE` · `status=null` | 회색 «로봇 연결을 기다리고 있습니다 · 서버는 연결됐지만 로봇에서 받은 정보가 없습니다» · 조종 준비 «연결 대기» · 서버가 주는 막힘 이유 (아래 2.2) · «조종 화면 열기» 꺼짐 (`fleet.tsx:78,95,157-168`) | 표 한 줄 «연결 전» · 지도에 점 없음 (`fake.ts:48`) | 로봇 목록 «연결 전» (`fake.ts:48`) |
| 서버 연결만 (화면 WS 열림, 첫 state 전) | `unknown='wait'` | «로봇 상태를 확인하는 중입니다» (`fleet.tsx:77`) | «상태 확인 중» | 같음 |
| 로봇 상태 받는 중 | `connection=ONLINE` · state 10 Hz | 초록 «로봇이 연결되었습니다» · 상태 한 줄 (서버 · 로봇 «연결» · 조종 중인 사람 · 정지 잠금 · 마지막 보고 n 초 전) · 로봇 상태 칸 (배터리 · 본체 자세 · 상태 번호 · 넘어짐 · 현재 위치) · 로봇 관측 칸은 «카메라 신호 없음» 류 문구만 (`fleet.tsx:64-144`) | 표 · 경보 · 서랍 상세 (장치 목록 · 자세 · 상태 번호, 읽기만) · «실기 보기» 링크 (`fleet.tsx:365-405,286-300`) | 목록에 배터리 · 넘어짐 칩 |
| 기체 확인 (사람 확인 대기) | Jetson `--onboard` 는 **없음** (11/19 코드에서 자동). 노트북판은 `0-0` 일 때 «이 로봇 맞음» 을 누를 때까지 서버 등록 · 연결을 시작하지 않음 | 서버에 안 붙었으니 «연결 전» 과 같음 | 같음 | 같음 |
| 현장 승인 (field approval) | 아래 2.3. 사람이 주지 않는다 | 화면에 따로 보이지 않음. 결과가 `server_drive_allowed=true` 로만 나타남 | 같음 | 같음 |
| 서버 경유 조종 허용 | `server_drive_allowed=true` (`robots.py:111-114`) · 화면은 `canDrive` = 허용 AND PC AND 앱 밖 AND 총괄 아님 AND 내 로봇 (`serverdrive.tsx:162`) | 로봇을 고르면 본문이 곧 세 칸 조종 화면 `PcDrive` (STOP · 조종 시작 · 잠금 해제 · 자세 · 관절 3D · 온도 · 카메라 · 라이다 · 뎁스 · 지도 만들기) (`fleet.tsx:335-338` · `pcdrive.tsx:116-180`) | 조종 · STOP 없음 (서버도 403 `ADMIN_NO_REAL_CONTROL`, `fh_server/api.py:75,88`) | `drive.tsx` 조종 화면 (서버 경유, 명령표 9 개 값 · 반 넘게 밀면 정해진 속도). 카메라 · 라이다 칸은 없음 (`drive.tsx:2-3,152`) |
| 조종 중 | 서버 lease 의 holder | 맨 위 줄 «조종하는 사람» · 보내는 속도 · 수평 속도 (`pcdrive.tsx:159-161`) | 표 «사람 조종» | 같음 |
| STOP 잠금 | state `latched=true` | 상태 한 줄 «정지 잠금 · 잠김», STOP 단계 문구 (정지 요청 접수 → «로봇 정지 확인 · 잠금·출력 0·수평 속도 0») · «잠긴 까닭» (`serverdrive.tsx:70-78` · `pcdrive.tsx:127,163`) | 빨강 «정지 잠금» | 같음 |
| 끊김 | 한 번 받은 뒤 OFFLINE | 빨강 «로봇과의 연결이 끊겼습니다» · 값은 «마지막 수신값», 현재 위치 · 정지 상태는 모름. 조종 화면은 남기되 «조종 시작» 꺼짐 (`fleet.tsx:75,104` · `pcdrive.tsx:141,146` · `serverdrive.tsx:171-176`) | 경보 목록 위로 | 같음 |
| 오래됨 | 서버: state 3 s 넘으면 빈 state (`robots.py:47`). 세 칸 화면: 1 s 넘으면 «로봇 보고 없음» · 관절 그림 멈춤 (`pcdrive.tsx:23,121,168`) · 온도 3 s 넘으면 «-(빈 값 표시)» (`pcdrive.tsx:35,43`) · 영상 1 s 넘으면 «신호 없음» (`drive_media.py:216-226`) | «마지막 보고 n 초 전» 이 커짐 (`fleet.tsx:30-45`) | 같음 | 같음 |
| 남의 로봇 | 운영 관리자에게 남의 로봇 | «○○님 담당 로봇입니다 · 요약만» · 관측 · 상태 · 조종 준비 칸 없음 (`fleet.tsx:79,345-348`) | (총괄은 전부 봄) | 목록에 안 나옴 (`fake.ts:77`) |

### 2.2 «조종 가능» 이 안 될 때 서버가 주는 이유 (표시만)

`server_drive_blocked` 값과 화면 문구 (`robots.py:149-162` · `fleet.tsx:146-151`):

| 값 | 뜻 | 화면 문구 |
|---|---|---|
| `SWITCH_OFF` | 서버 env `FH_SERVER_DRIVE_ENABLED` 가 1 이 아니고 `FH_SERVER_DRIVE_ROBOTS` 목록에도 없음 | 서버에서 실기 조종이 꺼져 있습니다 (관리자만 켤 수 있음) |
| `NO_OWNER` | 담당 없음 | 담당자가 없습니다 |
| `NO_SERIAL` | 짝짓기 기체번호 없음 | 로봇 기체번호가 등록되지 않았습니다 |
| `AGENT_OFFLINE` | 위 셋은 맞는데 `field_approved` 가 거짓 | 로봇 쪽 노트북 프로그램이 연결되지 않았습니다 (Jetson 이어도 «노트북» 이라고 씀) |

스위치 규칙: `FH_SERVER_DRIVE_ENABLED` 가 있으면 그 값 (1/0) 이 이기고, 없을 때만 `FH_SERVER_DRIVE_ROBOTS` UUID 목록을 본다 (`fh_server/api.py:46-62`). 저장소의 `deploy/` 에는 이 env 를 켜는 줄이 없다 (`grep` 0 건). 운영 서버에서 켜져 있는지는 **미확인**.

### 2.3 현장 승인: 무엇이 · 누가 · 어떻게

- **누가**: 사람 아님. 2026-11-11 `8f08d0d0` 부터 폰의 «현장 안전 확인 3 체크» 는 없어졌고, 옛 API `POST/DELETE /robots/{id}/field-approval` 는 410 `FIELD_APPROVAL_RETIRED` (`fh_server/pairing.py:232-244` · `GO2-SERVER-DRIVE.md` «현재 7번에 해당하는 승인 동작»).
- **서버 조건** `field_approved` (`realtime.py:859-865`): 실기 · 소켓 살아 있음 · 담당 변경 중 아님 · 스위치 켜짐 · 토큰 재확인 0.5 s 이내 · 마지막 수신 3 s 이내 · 그리고 DB 에 담당자와 기체번호가 있음 (`realtime.py:1714-1720,1802-1804`).
- **어떻게**: 서버가 보낼 때마다 `field_approval{expires_at: 지금+30 분}` 을 만들고 (`realtime.py:1311-1317`), 승인 중이면 60 s 마다 다시 보냄 (`realtime.py:2314-2315`). 조건이 깨지면 `expires_at=null` 로 회수하고 조종권도 거둠 (`realtime.py:882-898`).
- **agent 쪽 검사** (`setup/runtime.py:143-180`): 같은 NIC · 지금 실측 기체번호 · 자동 점검 통과 · 연결 살아 있음 · 30 분 이내 · 이전보다 새 만료. 통과하면 그때 처음 `SportClient` 두 개를 만들고 **잠긴 채** 시작 (`runtime.py:248-293`). 쓴 만료 시각은 0600 파일에 남겨, 프로그램을 다시 켜면 서버의 새 승인이 또 필요 (`runtime.py:258-261`).
- **조종까지 남은 관문**: STOP → 조종권 (lease) → 신선한 실측 정지 → 명시적 잠금 해제 → 새 중립 입력 (`GO2-SERVER-DRIVE.md` 옛 절차 7 항). 운동 상태 번호는 0 과 100 (Agile) 만 이동 허용 (`setup/runtime.py:323-327`).

---

## 3. 로봇 탭에 붙는 값 하나하나

공통: Go2 토픽 → `go2_readonly/state.py` (토픽별 2 s 신선도) + `go2_direct/feedback.py` (조종 감시용 0.2 s 창) → `go2_direct/reporting.py` `project` · `devices` → `DriveSession._state` (`go2_direct/server.py:130-145`) → `AgentState` → 서버 `accept_state` (`realtime.py:2223-2273`) → `RobotSummary` (`robots.py:197-213`) · `ScreenState` (`realtime.py:1606-1618`, 화면에 0.1 s 마다, `realtime.py:1700-1704`).

| 값 | Go2 원천 | agent 모듈 · 필드 | 서버 필드 | 화면 위치 | 갱신 · 오래됨 기준 |
|---|---|---|---|---|---|
| 배터리 % | LowState `bms_state.soc` | `state.py:93,103` → `project` `battery.soc` (lowstate 신선할 때만, `reporting.py:40-43`) | `state.battery={soc, updated_at}` (`realtime.py:2235`) | 로봇 상태 칸 «배터리» (`fleet.tsx:138`) · 표 · 세 칸 화면 (`pcdrive.tsx:155`) · 20 % 미만 주황 (`fake.ts:51`) | 10 Hz · 토픽 2 s · 서버 3 s |
| 전압 | LowState `power_v` | `battery.voltage` (`reporting.py:44-45`) | **버림**: 서버 `Battery` 에 칸이 없음 (`contracts/models.py:165-167` · `realtime.py:2235`) | 서버 경유 화면에는 없음. 폰 상태 전용 HTTP 보기에만 «V» (`go2status.tsx:136`) | |
| 자세 roll · pitch | LowState `imu_state.rpy[0:2]` | `robot_info.attitude` (`reporting.py:22-24`) | `state.robot_info` (`realtime.py:2230`) | «본체 자세» 아래 작은 글씨 `roll +1.2° · pitch …` (`fleet.tsx:139`) · 상세 서랍 «자세» (`go2status.tsx:65-74`). 연결 중일 때만 (`go2status.tsx:79`) | 토픽 2 s |
| 상태 번호 | SportModeState `error_code` | `robot_info.error_code` (sport 신선할 때만) | 같음 | «상태 번호 0(정상 범위)» / «상태 번호 N» (`fleet.tsx:133`) | 토픽 2 s |
| 넘어짐 추정 | roll 또는 pitch 절댓값 ≥ 60° | `robot_info.fallen` (`state.py:142-143`) | 같음 | «넘어짐 의심» 칩 (목록 · 상세) (`go2status.tsx:85-88`) · 안전 판단에는 안 씀 | |
| 자세 (서 있음 · 엎드림) | SportModeState `mode` · `body_height` · `progress` | `posture{state, mode}` (`server.py:132-133`) | `ScreenState.posture` 만 (목록 요약에는 없음) | 세 칸 화면 «자세» (`pcdrive.tsx:153`) · 자세 단추 (`serverdrive.tsx:193-205`) | 0.2 s 창, 넘으면 UNKNOWN |
| 관절 12 각도 | LowState `motor_state[0:12].q` | `robot_info.joints{names, positions, age_s}` (`state.py:95-97,148-157`) | 같음 · 서버가 메모리 체류 시간을 `age_s` 에 더함 (`robots.py:51-57`) | 세 칸 화면 Go2 3D 그림 (`pcdrive.tsx:25-32,167`) · `/sim/index.html?...policy=go2-demo&robot=<id>` «실기 보기» (`fleet.tsx:262-300` · `mobile/sim/go2-replay.js`) · **로봇 탭 기본 화면에는 숫자 없음** | 그림은 `age_s ≤ 1 s` 이고 state 1 s 안일 때만 |
| 온도 | 관절 `motor_state.temperature` · 배터리 `bq_ntc`/`mcu_ntc` · IMU · 본체 `temperature_ntc1/2` | `robot_info.temperature` (`state.py:30-47`) | 같음 | 세 칸 화면 «관절 최고 온도 · 배터리 온도 · 몸 안 온도» · 관절 점 색 (20~80 °C 눈금, 위험 기준 아님) (`pcdrive.tsx:41-47,156-158` · `go2model.tsx:21-22`). 팀장 11/19 지시 50 · 60 · 70 °C 알림은 **코드에 없음** | 3 s 넘으면 «-(빈 값 표시)» |
| 위치 | SportModeState `position` | `robot_info.position` (`origin=BOOT_ORIGIN_UNVERIFIED`, 켤 때 기준) · 지도 `pose` 는 전부 null (`reporting.py:39`) | `location` 은 null | 로봇 탭 «현재 위치 · -(빈 값 표시) · 지도 위치 없음» · 지도에 점 없음 (`fleet.tsx:140,227`). `position` 은 «실기 보기» 의 이동량에만 | |
| 수평 속도 | SportModeState `velocity[0:2]` | `speed` (1 s 안, `reporting.py:46-50`) | `state.speed` | 세 칸 화면 «수평 속도» · STOP 확인 문구 (`pcdrive.tsx:159` · `serverdrive.tsx:76`) | 1 s |
| 장치 목록 | 위 토픽 신선도 | `go2-battery` · `go2-imu` · `go2-sport` · `go2-preflight` (자동 점검) · `go2-identity` (`0-0` MAC 일 때) (`reporting.py:54-73` · `setup/runtime.py:446-455`) | `devices` (DB 에도 저장) | 상세 서랍 장치 · ERROR 면 주의 `DEVICE_ERROR` (`robots.py:80-97`) | |
| 카메라 RGB | SDK `VideoClient.GetImageSample` | JPEG 640×360 이하 · 64 KiB · 최대 5 Hz · HTTP POST `/agent/drive-media/rgb` | 최신 1 장 · 1 s 넘으면 `NO_VIDEO` (`drive_media.py:180-226`) | 세 칸 화면 «카메라» 칸만. 로봇 탭 «로봇 관측» 은 늘 «카메라 신호 없음 + 까닭» (`fleet.tsx:111-124`) | **승인 중에만** 보냄 (`setup/runtime.py:404-436`), 서버도 `server_drive_allowed` 일 때만 받고 보여 줌 (`drive_media.py:71-74`) |
| 라이다 점 | `rt/utlidar/cloud_deskewed` (odom 틀) · 3 s 없으면 `rt/utlidar/cloud` | 4000 점 · 48 KiB · 최대 2 Hz | 같은 중계 | 세 칸 화면 «라이다» 3D · «지도 · 라이다로 쌓는 중» (`pcdrive.tsx:119,129-132`) | 1 s · 승인 중만 |
| 뎁스 | 같은 DDS 참가자로 ROS 이름 후보 (`/d435i/depth/image_rect_raw` 등) 를 찾음 | `depth/source.py` · 640×360 · 최대 5 Hz · TURBO 색 | 같은 중계 | 세 칸 화면 «뎁스» · 없으면 «뎁스 카메라 영상이 아직 오지 않습니다…» (`drivemedia.ts:44`) | 1 s. 뎁스 발행은 연결 직후부터 돌지만 서버가 승인 전에는 받지 않음 (`setup/__main__.py:127-129` · `drive_media.py:82-92`) |
| 지도 | 라이다 + odom | `mapping/runtime.py` (웹 «지도 만들기» 의 `slam` 명령에 따름) | 지도 판 저장 | 세 칸 화면 오른쪽 «지도 만들기» (`pcdrive.tsx:80-86`) | 승인 중만 (`setup/runtime.py:417-423`) |

정리하면 **서버 경유 조종이 꺼져 있으면** 운영 관리자는 로봇 탭에서 배터리 · roll/pitch · 상태 번호 · 넘어짐 추정 · 장치 상태 · 마지막 보고만 본다. 관절 그림 · 온도 · 카메라 · 라이다 · 뎁스 · 지도 만들기는 모두 `server_drive_allowed=true` 뒤의 세 칸 화면에 있다. 관절만은 «실기 보기» 시뮬 창으로 볼 수 있다.

---

## 4. 폰 직결 길과 서버 경유 길

| | 서버 경유 (Jetson 설치판 · 노트북 설치판) | 폰 직결 |
|---|---|---|
| agent 실행 | `foothold_agent.setup` (Jetson 은 `launch.py`) | `python -m foothold_agent.go2_direct` 를 현장 env (`FH_GO2_DIRECT_ENABLED=1` · 0600 승인 JSON · 폰 키링 · 포트 등) 로 손으로 (`GO2-DIRECT-RUNTIME.md:13-27,66-71`) |
| 화면 진입 | PC 로봇 탭 → 세 칸 화면 / 폰 `#/drive/<id>` | 폰 «+ 로봇 연결하기» 주변 찾기 (mDNS `_foothold._tcp` · BLE) → 로봇 ID 를 알린 에이전트 «연결» → 서버가 출입증 발급 → 앱 중계로 에이전트 `/phone/ws` 에 직접 hello → `RealDrive` (`nearby.tsx:1-5` · `realdrive.tsx:1-4`) |
| 명령 길 | 화면 → 서버 중재 (lease) → agent | 폰 → agent 직접. 서버는 출입증만 |
| 상태 길 | agent → 서버 → 화면 | agent → 폰. 서버로는 폰이 LTE 로 올리는 표시 전용 `phone_relay` (`GO2-PHONE-STATE-RELAY.md:1-30`) 또는 `FH_GO2_CLOUD_REPORTING=1` 일 때 agent 직접 보고 |
| 명령 값 | 표 9 개 (전후 ±1.5 · 옆 ±1.0 m/s · 회전 ±0.5 rad/s) | 정지 · 전진 0.3~1.5 m/s · 전진하며 회전 ±0.5 (`GO2-DIRECT-RUNTIME.md:79`) |
| 영상 | RGB · 라이다 · 뎁스 중계 있음 | 폰 직결 카메라 경로는 05 §13.8 (실기 확인 미확인) |
| 상태 전용 길 | (없음) | `go2_readonly --listen --advertise` 의 HTTP `:9610/go2/status` + 8 자리 현장 코드 → 폰 «상태만 보기» (`GO2-READONLY.md:159-205,251-272` · `go2status.tsx`) |

**실기에서 어느 길이 검증됐나 (문서 기준)**

| 길 | 문서 기록 | 판정 |
|---|---|---|
| 폰 직결 조종 | 화면에 «실기 연결은 아직 실제 기체에서 확인하지 않았습니다(미검증)» 를 늘 띄움 (`phone.ts:47`) · «실기 시험 0회» (`GO2-DIRECT-RUNTIME.md:79`) | **미검증** |
| 노트북 → 서버 → 웹 상태 표시 | 10/30 `cc1df955` 문서: «별도 사용자 승인으로 실기 상태 구독→로컬 서버→웹 상태 수신·headless 표시만 읽기 전용으로 확인» (서버가 로컬이었음, 기체 미기재) (`GO2-SERVER-DRIVE.md:133`) | 읽기 전용 1 회 기록 있음 · 원자료 미확인 |
| 노트북 → 서버 경유 조종 | 10/30 서버 시험 코드 `af87977` 의 «실제 성공 실행» 이 비공개 현장 기록에 있다고만 적힘 (`GO2-SERVER-DRIVE.md:313-326`) · 11/13 «현장 담당자는 로봇을 세운 뒤 연결이 됐다고 보고» + 승인 직후 정지 출력 실패 조사 (`GO2-SERVER-DRIVE.md:298-303`) | 보고만 있음 · 원자료 · 기체 (Go2 EDU 인지 X 인지) **미확인** |
| Jetson 설치판 (Go2 X) | `JETSON-ONBOARD.md:221-223` «Jetson 미확인: … 최초 등록 … DDS 상태 수신·STOP …» | **미검증** |

---

## 5. 지금 배치 상태 (문서 · 기록 기준만)

| 항목 | 기록 | 근거 |
|---|---|---|
| NaverCloud 서버 구성 | Ubuntu 24.04 · Caddy 443 → 정적 웹 + uvicorn + PostgreSQL 16 · `<IP>.sslip.io` · dev 배포 (40 자리 커밋 지정, 자동 배포는 선택) | `deploy/README.md:1-30,104-141` · lab `APP-ROBOT-DIRECTION-1119.md:81` |
| 서버에 떠 있는 판 (커밋) | 저장소 · lab 기록에서 찾지 못함 | **미확인** |
| 서버 경유 조종 스위치 | `deploy/` 에 `FH_SERVER_DRIVE_*` 설정 줄 없음 | **미확인** |
| 자동 배포와 실기 | «로봇 연결 시 움직이는 중 재시작을 막는 조건이 … 지금은 미구현» | `deploy/README.md:141` |
| Jetson agent 설치 | 11/18 감사: r4 완성본 `~/foothold-robot-r4` (foothold-agent 0.2.0), r5 `~/foothold-robot` 는 `INCOMPLETE` · `launch.py` · `connection.json` 없음 | lab `inbox/jay/20261118-go2-x-ai-lx01-handoff.md:81-86` · git `66ae5bf0e` 의 `20261118-app-baseline-audit/README.md` |
| Jetson 서비스 | `foothold-robot.service` enabled · 없는 `launch.py` 로 부팅 뒤 6 회 실패 · `failed` · 앱 프로세스 · TCP 9539 없음 (11/18). 11/19 에도 «failed · 9539 · 9611 안 열림 = 앱 agent 가 돌고 있지 않음» | 위 감사 · lab `APP-ROBOT-DIRECTION-1119.md:43` |
| 자동 시작 꺼짐 | 「끄자」 는 제안 · 다음 관문으로만 적힘. 실제로 `disable` 했다는 기록은 이 사본들에서 찾지 못함 | 감사 README «다음 안전 관문 1» · `APP-ROBOT-DIRECTION-1119.md:121` · **미확인** |
| 과거 앱 실행 흔적 | `~/foothold-robot-run.log` 에 r3/r4 실행 때 고수준 `StopMove` 호출 (code 0 · 3104) | 감사 README. 이 코드에서 `StopMove` 는 서버 승인 뒤 만든 SDK 로만 나가므로 그때 서버 승인까지 갔을 가능성이 있다 (**추정**, 로그 원문 미확인) |
| 11/19 Go2 X 작업 | CycloneDDS · Tailscale · RViz 표시 · 방 녹화. FOOTHOLD agent 실행 기록 없음 | lab `20261101-app/GO2X-JETSON-SETUP-1119.md:11-23` |
| Go2 X 가 앱 화면까지 간 기록 | 찾지 못함. 앞선 «실기 연결» 기록은 10/30 · 11/13 노트북 길이며 기체가 Go2 X 인지 미기재 | 4 절 표 · **미확인** |

---

## 6. 로컬에서 「실기가 붙은 화면」 을 재현하는 후보

이미 있는 것: `apps/web/tools/dev_stack.py` (임시 PostgreSQL · uvicorn · 계정 셋 · 로봇 `Go2-7` 하나 · 가짜 agent). 이 가짜 agent 는 평범한 `Session` 이라 `robot_info` · 배터리 · 장치를 안 보내고, 로봇에 `serial` 이 없고 (`dev_stack.py:60`), uvicorn 에 `FH_SERVER_DRIVE_ENABLED` 를 안 준다 (`dev_stack.py:67`). 그래서 앞선 실사가 빈 화면만 찍었다.

| 후보 | 무엇을 흘리나 | 필요한 것 · 명령 | 한계 |
|---|---|---|---|
| A. 상태만 (가장 작음) | 배터리 · roll/pitch · 상태 번호 · 넘어짐 · 관절 · 온도 · 위치 → 로봇 탭 «로봇 상태» · 상세 · «실기 보기» | scratch 스크립트에서 `dev_stack.py agent` 와 같은 `Client` 를 쓰되 `Session` 을 상속해 `_state()` 에 `go2_direct.reporting.project(State.snapshot())` 를 합친다. `State` 에는 `SimpleNamespace` 로 만든 가짜 LowState (`tick` 증가 · `sn` · `bms_state.soc` · `power_v` · `imu_state.rpy/quaternion` · `motor_state[i].q/temperature`) · SportModeState (`stamp.sec/nanosec` 증가 · `mode` · `error_code` · `position`) 를 10 Hz 로 넣는다. 본보기: `apps/agent/tests/test_go2_replay_samples.py:11-20` · 서버 쪽 본보기 `apps/server/tests/test_go2_replay.py:9-27` | 조종 허용 · 세 칸 화면은 안 열림 (serial · 스위치 없음). 실제 setup 경로와는 다른 Session |
| B. 실제 setup 경로 그대로 | A + 장치 목록 · 자세 (posture) · 자동 현장 승인 · `server_drive_allowed=true` · 세 칸 화면 · 잠금 해제 흐름 | ① `dev_stack.py server` 를 쓰되 로봇에 `serial` (예 `1234-5678`) 을 넣고 uvicorn env 에 `FH_SERVER_DRIVE_ENABLED=1` 을 더한 scratch 사본 ② agent 쪽은 `foothold_agent.setup.runtime.run(credentials, nic, inputs, subscriptions, ready=True, check_nic=lambda: True, status=Status(), stop=…, connect=<가짜 SportClient 쌍>, media_factory=<빈 것>, mapping_factory=<빈 것>)` 을 실제 `Client` (로컬 WS) 로 부르고 `Inputs.lowstate/sportmodestate` 에 가짜 표본을 0.01 s 마다 넣는다. 가짜 SDK 를 끼우는 법은 `apps/agent/tests/test_setup_approval_runtime.py:143-200` (`__import__` 바꿔치기 · `FakeSport`) 에 그대로 있다 | 손이 많이 감. 가짜 SDK 로 `Move` 가 메모리에만 감 (실기 명령 0). `0-0` · MAC 길은 `socket.if_nameindex` · 이웃 조회도 가짜로 |
| C. 영상 · 점 | 카메라 · 라이다 · 뎁스 칸 | B 로 `server_drive_allowed=true` 를 만든 뒤, 같은 agent 토큰으로 `POST /api/v1/agent/drive-media/{rgb|lidar|depth}` 에 `{header: media/1, points}` 를 5 Hz 이하로 올린다 (JPEG 크기와 header width/height 일치 · `captured_at` 1 s 안 · `seq` 증가 · 라이다는 base64 xyz float32, `frame` 은 `odom` 또는 `lidar_link`) (`fh_server/drive_media.py:123-178`). 형식 본보기: `apps/server/tests/test_drive_media.py` · `apps/agent/tests/test_go2_drive_media.py` | agent 의 진짜 미디어 모듈은 `type(channel) is Subscriptions` (진짜 SDK 구독) 을 요구해 가짜 구독으로는 안 돈다 (`go2_direct/media.py:476-479`). 그래서 HTTP 로 직접 올려야 함 |
| D. 실기 기록 재생 | 11/19 방 녹화 (L2 `cloud_deskewed` · odom · imu · D435i 깊이) | NAS 의 11/19 rosbag2 (저장소 밖) 를 `.venv-rosbags` 로 읽어 C 의 형식으로 올리고, monitor.csv 의 배터리 · 온도를 A/B 의 가짜 LowState 에 넣기 (`GO2X-JETSON-SETUP-1119.md:80-95`) | 저장소에 이 재생 도구는 없음. 만들어야 함 |
| E. 브라우저만 단위 시험 | «실기 보기» 관절 보간 | `node mobile/scripts/go2-replay-live-selftest.mjs` (가짜 WS · 가짜 GET) | 화면 전체가 아님 |
| F. 폰 상태 전용 | 폰 «상태만 보기» | `go2_readonly` 의 HTTP 계약 (`GO2-READONLY.md:211-272`) 을 흉내 내는 로컬 HTTP + 앱 이벤트 `fh-go2`. 폰 앱 · WebView 필요 | 서버 경유 화면과 무관 |

위 명령은 **실행하지 않았다**. A~C 가 실제로 화면을 채우는지는 미확인.

---

## 7. 코드에서 본 어긋남 · 위험 (코드 읽기 추정, 실측 아님)

1. **서버는 「소켓 연결」 만으로 ONLINE.** Go2 DDS 가 연결 뒤 끊겨도 agent 소켓이 살아 있으면 로봇 탭은 «연결» 이고 값만 «-(빈 값 표시)» / «모름» 이 된다. 그 사이 서버 `field_approved` 는 참이라 `server_drive_allowed=true` 가 유지되고 60 s 마다 승인을 다시 보내지만, agent 는 기체번호가 0.2 s 안에 새로 오지 않으면 승인을 거부한다 (`realtime.py:859-865` · `setup/runtime.py:157-164,234`). 화면은 «조종 가능» 인데 조종이 안 되는 틈이 생길 수 있다.
2. **sport `stamp` 가 0 이거나 고정인 펌웨어.** 읽기 전용 `State` 는 이를 허용하지만, setup 경로는 `Feedback.sportmodestate` 를 거치며 `marker <= 0` 이거나 증가하지 않으면 버린다 (`feedback.py:112-139`). 그러면 상태 번호 · 자세 · 속도가 계속 비고 조종도 못 연다. Go2 X 의 stamp 동작은 미확인.
3. **전압이 서버에서 버려진다** (`realtime.py:2235`). 웹 서버 경유 화면 어디에도 전압이 없다.
4. **온도 알림 (50 · 60 · 70 °C) · 배터리 20/10 % 반복 알림 (팀장 11/19)** 은 코드에 없다. 온도는 세 칸 화면에서만 보인다.
5. **문서와 코드 차이**: `JETSON-ONBOARD.md:159-163` 은 «기체번호가 없으면 처음 한 번 '이 로봇 맞음' 확인» 이라 적었지만 11/19 `e6192f21` 코드는 onboard 에서 사람 확인을 건너뛴다 (`setup/identity.py:120-132`). `GO2-DIRECT-RUNTIME.md:5` 의 «자동 시작 서비스 … 제공하지 않는다» 도 지금 설치판과 다르다 (그 문서는 `go2_direct` 진입점 이야기).
6. **Jetson 에서 6 자리 코드 보기**: headless 라 코드가 loopback `:9539` 화면에만 있다. 원격 화면 접근 수단 없이는 짝짓기를 못 한다.
7. **화면 문구가 «노트북»**: Jetson 이어도 «로봇 쪽 노트북 프로그램이 연결되지 않았습니다» · «노트북 연결 프로그램을 확인하세요» 로 나온다 (`fleet.tsx:150,165`).
8. **라이다 기종**: 코드 · 문서는 L1 (`rt/utlidar/cloud*`) 기준이고 Go2 X 는 L2. 11/19 기록에 같은 토픽 이름이 보이지만 (`GO2X-JETSON-SETUP-1119.md:45,67`) agent 의 점 해석이 L2 에서 맞는지는 미확인.
9. **뎁스**: D435i 는 Jetson USB 에 붙어 있고 RViz 는 Jetson 위 ROS 로 띄웠다. agent 는 Go2 내부 NIC 에 묶은 DDS 참가자로 ROS 토픽을 찾는데, Jetson 안에서 낸 realsense 토픽이 그 참가자에게 보이는지는 미확인.

## 8. 확인 못 한 것 (미확인 모음)

- NaverCloud 에 떠 있는 커밋 · `FH_SERVER_DRIVE_ENABLED` 값 · 자동 배포 켜짐 여부
- Jetson `foothold-robot.service` 의 11/19 이후 상태 · 실제로 disable 했는지
- Go2 X 로 서버 · 웹 화면까지 간 기록 (날짜 · 근거 모두 없음)
- 10/30 · 11/13 노트북 길 기록의 원자료 · 기체 종류
- Go2 X 의 `sn` (0-0 인지) · sport `stamp` 동작 · L2 점 형식 · D435i 토픽이 agent 에 보이는지
- 6 절 재현 후보의 실제 동작
