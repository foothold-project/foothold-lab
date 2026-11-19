> 분류: 실사 기록 · FOOTHOLD 앱 (웹 + 폰) 지금 상태
> 작성: Claude 세션 app-design-lx (오흥재 지시) · 2026-11-19 22:5x
> 근거: foothold-app `origin/dev` `2b19f592` (11/19 21:35) 코드 읽기 · 같은 커밋을 로컬에 띄워 찍은 화면 18 장 (`shots/`) · 앱 흐름 그림 v0.6 (`../20261101-app/APP-FLOW-DIAGRAM.html`) · 결정 기록 `../20261101-app/APP-ROBOT-DIRECTION-1119.md` v1.1
> 요지: 지금 앱은 「PC 관제 웹 (로봇 · 지도 · 시뮬 · 기록 · 설정)」 과 「폰 조종 (로봇 연결 → 조종)」 두 틀이고, 실기와 시뮬이 다른 화면 · 다른 길로 나뉘어 있다. 팀장 원칙 일곱 가운데 「늘 보이는 STOP」 과 「값의 나이」 는 꽤 있고, 「모드 이름 · 무드 구분 · 웹과 앱 하나 · 3D 고급감 · 음성 · Jetson 저장」 은 없거나 일부다
> 상태: 초안 · 팀장 확인 전. 고칠 안은 쓰지 않는다 (사실만)

# 앱 실사 (2026-11-19 · dev `2b19f592`)

## 0. 무엇을 기준으로 봤나

- **코드 기준은 `dev` 다.** `main` 은 10/21 `6f16be74` 에서 멈춰 있고 `dev` 가 1154 커밋 앞서 있다. 팀원 작업과 팀장이 보는 화면은 `dev` 라서 `dev` 를 실사했다 (lead-lx 22:4x 확인).
- **띄운 법.** 저장소에 있는 개발 도구 `apps/web/tools/dev_stack.py` 로 내 기기 안에서만 띄웠다: 임시 PostgreSQL · 관제 서버 (uvicorn) · 가짜 로봇 (받은 명령을 메모리에만 두는 가짜 agent · 실제 로봇 명령 0) · 웹 개발 서버 (Vite). 계정 셋 (총괄 1 · 운영 관리자 2) · 로봇 1 대 (`Go2-7`) 가 자동으로 만들어진다. 이 도구는 Docker 를 쓰지 않는다.
- **찍은 법.** 헤드리스 Chrome 으로 PC 폭 1440 x 900 · 폰 세로 390 x 844 · 폰 가로 844 x 390 에서 찍었다. 실기 「조종 시작」 은 누르지 않았다.
- **못 띄운 것 (아래 그림 없음 · 코드로만 적음).**
  - 브라우저 MuJoCo 시뮬 (`/sim/`): 정책 · MuJoCo wasm · onnxruntime 묶음이 저장소 밖 비공개 자산 (`deploy/README.md` 「브라우저 MuJoCo 묶음」) 이라 이 기기에 없다. 그래서 「시뮬 열기」 는 「시뮬을 열지 못했습니다」 로 끝났다 (`shots/07`).
  - PC 세 칸 조종 화면 (`pcdrive.tsx` · Go2 3D 포함): 서버 설정 · 기체번호 · 현장 승인 (agent 쪽) 세 조건이 맞아야 열린다 (`apps/server/fh_server/robots.py:111`). 가짜 로봇으로는 현장 승인이 없어 못 열었다.
  - 실기 영상 · 라이다 · 뎁스 · 배터리 · 관절 값: 가짜 로봇이 이 값을 보내지 않아 빈칸으로 찍혔다. 「빈칸일 때 화면이 무엇을 말하는가」 만 사실이다.
- 그림 파일 이름 앞 번호는 이 문서의 읽는 순서다.

## 1. 화면 지도

### 1.1 틀 두 개 (PC · 폰)

| 틀 | 언제 | 모양 | 코드 |
|---|---|---|---|
| PC 관제 웹 | 폭 768 px 이상 | 머리줄 (로고 · 화면 이름 · 연결 점 · 알림 종 · 사용자 · 로그아웃 · STOP) + 왼쪽 세로 메뉴 + 본문 | `apps/web/src/App.tsx:1` · 메뉴 정의 `apps/web/src/menu.tsx:24-33` |
| 폰 | 폭 768 px 미만 (또는 눕힌 폰) | 머리줄 (화면 이름 · 연결 점 · `⋯` · STOP) + 본문. 아래 탭 줄 없음 | `App.tsx:2` · `menu.tsx:37-45` |

- PC 메뉴 (보이는 것): **로봇 · 지도 · 시뮬 · 기록** + 아래 **어두움/밝음 · 설정**. 숨은 탭 (주소로만 열림): 결재 · 지형 만들기 · 휴지통 (`menu.tsx:24-33`).
- 폰에는 탭이 없다. 「로봇 연결」 → 「조종」 → 「끝내기」 한 줄이고, 기록 · 전체화면 · 로그아웃 · 테마는 `⋯` 안에 있다 (`shots/12`).
- 같은 웹 코드 (`apps/web`) 가 폭에 따라 두 틀을 고른다. 폰 앱 (Capacitor Android 1.2.3) 은 서버 주소를 열어 이 웹을 보여 주는 껍데기 + 앱 안 오프라인 시뮬이다 (`mobile/package.json` description).

### 1.2 PC 관제 웹

| 그림 | 화면 | 목적 (코드 머리말 기준) | 보이는 것 (찍힌 사실) | 코드 |
|---|---|---|---|---|
| `shots/01-pc-login.jpg` | 로그인 | 계정 로그인 | 계정 · 비밀번호 · 로그인 | `apps/web/src/session.tsx:100-103` |
| `shots/02-pc-admin-robot.jpg` | 로봇 (총괄) | 전 로봇 요약 → 지도 → 경보 → 표 | 숫자 줄 (전체 · 연결 · 임무 중 · 주의 필요 · 결재 대기) · 「지도 · 전 로봇 위치」 · 경보 · 로봇 표 (담당 · 연결 · 배터리 · 임무 · 마지막 보고) · 운영 관리자 목록. **머리줄에 STOP 이 없다** (총괄은 실기를 조종 · STOP 하지 않는다 · `fake.ts` `ADMIN_REAL`) | `apps/web/src/screens/fleet.tsx:1-5` |
| `shots/03-pc-op-robot.jpg` | 로봇 (운영 관리자 · 내 로봇 한 대) | 상태 한 줄 → 관측 → 위치 → 상세 | 「로봇이 연결되었습니다」 칸 (서버 · 로봇 · 조종 중인 사람 · 정지 잠금 · **마지막 보고 0초 전**) · 「로봇 관측」 [지도 · 카메라 · 라이다 · 뎁스] · 「로봇 상태」 (배터리 · 본체 자세 · 현재 위치) · 「조종 준비」 세 단계 · 「현재 임무」 · 「실기 보기」 (지도 고르고 열기 · 조종 안 됨) · 머리줄 **STOP 정지 요청** | 같은 파일 · `pcdrive.tsx:1-4` |
| `shots/04-pc-op-robot-lidar.jpg` | 로봇 관측 · 라이다 | 영상 · 점구름 보기 | 「라이다 신호 없음 · 서버 경유 조종이 허용되면 조종 화면에서 받습니다」 | `quad.tsx` · `lidar3d.tsx:1-4` (11/19 3D 점구름 · three.js) |
| `shots/05-pc-map.jpg` | 지도 | 장소 · 건물 · 층 고르고 구역 · 벽 고치기 | 「어느 지도에서 일할까요?」 · 찾기 · 「+ 파일 올리기」 · 「+ 지형 만들기」 · 휴지통. 「시나리오는 «시뮬» 탭에서」 안내 | `apps/web/src/screens/maps.tsx:1-4` |
| `shots/06-pc-terrain-top.jpg` | 지형 만들기 (위에서) | 시뮬용 지형을 손으로 놓기 | 도구 [고르기 · 상자 · 계단 · 경사 · 틈 · 시작] · 가로 · 세로 m · [위에서 · 3D] · 저장 · 「시뮬로 열기」 · 오른쪽 물체 목록 (0/60) | `apps/web/src/screens/terrain.tsx` |
| `shots/07-pc-terrain-3d-simwin.jpg` | 지형 만들기 (3D) + 시뮬 작은 창 | 3D 로 끌어 놓기 · 브라우저 시뮬을 앱 안 창으로 | 청록 단색 상자 · 계단 · 경사가 격자 위에 놓임 · 왼쪽 아래 작은 창 「시뮬을 열지 못했습니다」 (이 기기에 시뮬 자산 없음 · 0 절). 작은 창은 다른 탭으로 옮겨도 남는다 (`shots/10` 에도 보임) | `screens/terrain3d.tsx:1-3` · `simwin.tsx:1-4` |
| `shots/08-pc-sim.jpg` | 시뮬 | 지도 고르기 → 시뮬 열기 → 시나리오 만들고 「시뮬에서 실행」 | 「어느 지도로 시뮬할까요?」 · 찾기 · 「서버 시뮬 지도가 없습니다」. 실기 지도의 시나리오도 여기서 고친다고 적혀 있다 | `apps/web/src/screens/sim.tsx:1-4` |
| `shots/09-pc-history.jpg` | 기록 | 사건 목록 · 거르기 · 내보내기 | [전체 · 임무 · 이탈 · 연결 · 조종권 · 결재 · 안전 · 계정] · 로봇 · 기간 · 표 (시각 · 종류 · 상태 · 내용 · 로봇·사람) | `screens/history.tsx:1-4` |
| `shots/10-pc-settings.jpg` | 설정 | 조직 기준값 · 실기 · 시뮬 · 계정 | [공통 · 실기 · 시뮬 · 계정] · 배터리 부족 기준 20 % · 실행 시작 최소 배터리 30 % · 경로 이탈 거리 1.5 m · 「총괄만 고침」 | `screens/settings.tsx:1-3` |

### 1.3 폰

| 그림 | 화면 | 보이는 것 (찍힌 사실) | 코드 |
|---|---|---|---|
| `shots/11-ph-connect.jpg` | 로봇 연결 | 「내 로봇」 카드 (이름 · 정지 잠금 · 조종하는 사람 · [연결] · [관리]) · 「+ 로봇 연결하기」 · 아래 「시뮬」 지도 카드 7 장 (창고 · AME-2 학습 지형 · 큰 공장 · 큰 공장 심화 · 2층 공장 · 요소 코스 · 붕괴 주택, 창고 말고는 「초안」) | `drive.tsx` · `simstart.tsx:1-2` · 지도 목록 `mobile/sim/maps.json` |
| `shots/12-ph-more-menu.jpg` | `⋯` 메뉴 | 전체화면 · 기록 · 로그아웃 · 테마 | `App.tsx` |
| `shots/13-ph-add-robot.jpg` | 새 로봇 추가 | 노트북 (Ubuntu · Windows) 에 연결 프로그램 설치 → 랜선 → QR 스캔 또는 6 자리 코드. **로봇 쪽 컴퓨터가 「노트북」 으로 적혀 있다** (Jetson 은 다른 설치 묶음 `apps/agent/installer/install_jetson_bundle.py`) | `pairing.tsx:1-3` |
| `shots/14-ph-drive.jpg` | 조종 (세로) | 로봇 이름 · 조종하는 사람 · **지연 0.8 ms** · 정지 잠금 · [조종 시작] · [RGB · 뎁스 · 지도] · 영상 자리 「실기 영상 준비 중 (미연결)」 · 작은 지도 「지도 없음」 · 아래 [자세 · 시나리오 · 지도·목표 · 정책] | `realdrive.tsx:1-4` · `drive.tsx` |
| `shots/15-ph-drive-pose.jpg` | 조종 · 자세 시트 | [서기 · 앉기 · 일으키기] 모두 꺼짐 · 「다음 단계에서 열립니다」 | `drive.tsx` |
| `shots/16-ph-drive-map-scenario.jpg` | 조종 · 지도 보기 + 시나리오 시트 | 「지도 · 라이다 자료 없음 · 기능 준비 중」 · 시나리오 고르기 · 「실행 (준비 중) · 실기 시나리오 실행은 준비 중입니다」 | `drive.tsx` · `screens/missions.tsx:3` |
| `shots/17-phl-drive.jpg` | 조종 (가로) | 세로와 같은 내용을 가로로 | `realdrive.tsx` |
| `shots/18-phl-sim-cards.jpg` | 시뮬 지도 카드 (가로) | 지도 카드를 누르면 고른 표시만 바뀌고, 아래에 위에서 본 사진 · 「시뮬 열기」 가 나온다 (이 기기에서는 열리지 않음 · 0 절) | `simstart.tsx:1-2` |
| (그림 없음) | 정책 시트 | 코드 문구 「지금 보행 정책 표시와 바꾸기는 다음 단계에서 열립니다.」 | `apps/web/src/drive.tsx:143` |

### 1.4 그림 없이 코드로만 확인한 화면

| 화면 | 사실 | 코드 |
|---|---|---|
| PC 세 칸 조종 (11/19) | 맨 위 STOP · 조종 시작/끝 · 잠금 해제. 왼쪽 = 상태 글자 + **Go2 3D** (Unitree 공개 메시 `public/go2/go2.glb` · 받은 관절각대로 돌림 · 관절 12 개 온도 색 점 · 움직임 화살표) + 자세 단추. 가운데 = 4 칸 (지도 · 카메라 · 라이다 · 뎁스). 오른쪽 = 지도 만들기 · 속도 · 시나리오 · 목표 | `pcdrive.tsx:1-4` · `go2model.tsx:1-4` |
| Go2 3D 온도 색 | 관절 온도를 청록 한 색의 연함→진함으로. 「범위 표시용일 뿐 위험 기준 아님」 (50 · 60 · 70 °C 문턱 없음). 온도 보고가 오래되면 온도 칸을 빈 줄표로 비움 | `go2model.tsx:21-25` · `pcdrive.tsx:34` |
| 브라우저 시뮬 (MuJoCo) | `apps/web` 과 따로 된 페이지 `mobile/sim/index.html` (`main.js`). 브랜드 토큰 CSS 를 읽지만 색 값 25 곳을 직접 씀. 「시뮬 정책」 고르기: `nvidia-demo` (기본) · `start(시연)` · `AME-2(시연)` · `Go2 실기 보기` | `mobile/sim/index.html:9,132-136` · `policy-modes.js:73-78` · 라벨 `start-demo-adapter.js:54` · `ame2-adapter.js:86` · `go2-replay.js:7` · `policy-adapters.js:17` |
| 시뮬 작은 창 | PC 「시뮬 열기」 는 페이지를 떠나지 않고 시뮬을 앱 안 창으로 띄운다 (처음 화면 가득 → 작은 창 → 크게 보기 · 닫기) | `simwin.tsx:1-4` |
| PC 서버 경유 시험 조종 | 서버가 켠 시험 로봇만 · PC 웹만 · 명령 9 개 값만 · **키보드 입력 있음** (`keydown`) | `serverdrive.tsx:1-4,268` |
| 주변 로봇 찾기 · 상태만 보기 | 폰 앱이 Wi-Fi (mDNS) · 블루투스로 찾고, 실기 직결 또는 「상태만 보기」 (배터리 · 자세 · 상태 번호 · 넘어짐 추정) | `nearby.tsx:1-4` · `go2status.tsx:1-3` |
| 3D 지도 · 점 지도 | 라이다 점을 three.js 로 그림 (높이 색 · 로봇 화살표 · 끌어 돌리기). 서버 지도 칸 0.1 m 상자 3D (InstancedMesh) | `lidar3d.tsx:1-4` · `lidarmap.tsx:1-3` · `screens/voxel3d.tsx:1-3` |

## 2. 데이터가 흐르는 길 (지금)

| 길 | 무엇이 오가나 | 근거 |
|---|---|---|
| 화면 ↔ 관제 서버 (HTTP `/api/v1`) | 로그인 · 로봇 목록 · 지도 · 시나리오 · 사건 · 설정 | `apps/web/src/api.ts` · `apps/server/README.md` |
| 화면 ↔ 서버 실시간 (`/api/v1/ws`) | 로봇 상태 · 조종권 · STOP · 명령 (50 ms 마다) | `apps/web/src/rt.ts` · 그림 v0.6 숫자 표 |
| 서버 ↔ 로봇 agent (`/api/v1/agent/ws`) | agent 가 서버로 먼저 연결 (그래서 Jetson 이 인터넷만 있으면 바깥에서 조종) | 그림 v0.6 「읽는 순서」 |
| 폰 ↔ 로봇 agent 직결 | 시뮬 · 실기 직결 조종 (출입증 · 조종권 · 잠금 · STOP 판정은 agent) | `realdrive.tsx:1-2` · `phone.ts` |
| 브라우저 안 시뮬 | MuJoCo + onnxruntime-web 정책이 **사용자 기기 안에서** 돈다 (서버 GPU 0) | 결정 기록 6 절 · `deploy/README.md` |
| agent → Go2 | Sport 경로 `SportClient.Move` 하나. 저수준 LowCmd · 모드 관리자 · 안전 정지 (Damp) 없음 | 그림 v0.6 숫자 표 (`go2_direct/sink.py:567`) |

## 3. 실행 구조 (사실)

- **로컬 개발**: `dev_stack.py` 로 서버 + 임시 DB + 가짜 로봇은 Docker 없이 내 기기에서 뜬다 (이번 실사에서 실제로 띄움). 그러나 (1) 브라우저 시뮬은 비공개 자산이 따로 있어야 하고, (2) 실기 기록 재생 (예: 11/19 숙소 기록) 을 화면에 흘려보내는 길은 이 도구에 없고, (3) 웹 개발 서버는 `.env` 가 아닌 `FH_API` 등 환경 변수로 주소를 받는다 (`apps/web/vite.config.ts`).
- **`docker compose` 파일은 `origin/dev` 에 없다.** 예시 환경 파일은 `deploy/server.env.example` · `deploy/foothold-sim-manager.env.example` · `deploy/rootfs-manager.env.example` 셋이 있다.
- **운영**: NaverCloud 서버 하나에 Caddy 443 → 정적 웹 + uvicorn + PostgreSQL 16 (`deploy/README.md` · 결정 기록 6 절). 웹 빌드는 PC 에서 해서 보낸다. 지금 앱 흐름은 「서버에 로그인 → 서버 경유 또는 폰 직결로 로봇」 이 기본이다 (서버 먼저).
- **로봇 연결 패널**: 새 로봇은 로봇 쪽 컴퓨터에 연결 프로그램을 깔고 화면의 QR · 6 자리 코드로 서버에 등록한다 (`pairing.tsx:1-3` · `shots/13`). 연결 키는 화면에 오지 않는다.
- **Jetson 자동 시작**: 설치 묶음이 `enable-autostart.sh` · `disable-autostart.sh` 를 만들고 `foothold-robot.service` (systemd user) 를 켜고 끈다 (`apps/agent/installer/install_jetson_bundle.py:210-215` · `jetson_autostart.py:9`). 11/19 22:16 이 서비스가 부팅 때 떠서 로봇 명령 (SportClient) 을 낼 수 있었던 것이 확인됐고 팀장이 껐다 (시작 프롬프트 3 절).

## 4. 팀장 원칙 대비 모자란 점 (사실만 · 고칠 안 없음)

| 팀장 원칙 | 지금 있는 것 | 없는 것 · 다른 것 |
|---|---|---|
| 1. 탭마다 그 목적의 기능이 한곳에 | PC 는 로봇 · 지도 · 시뮬 · 기록 · 설정으로 나뉨 | 같은 일이 여러 탭에 흩어짐: 시나리오는 지도 탭에서 「시뮬 탭에서 만든다」 고 안내하고 (`shots/05`), 지형 만들기는 지도 탭 입구인데 결과는 시뮬 탭에 뜬다 (`menu.tsx:29` 주석). 실기 조종은 폰 (또는 서버가 허용한 PC 세 칸 화면) · 시뮬 조종은 PC 시뮬 탭과 폰 로봇 연결 화면 두 곳 |
| 2. 늘 보이는 안전 띠 | 머리줄 STOP (운영 관리자 · 폰) · 「정지 잠금」 알약 · 끊김 문구 (`App.tsx:33-50`) | 총괄 화면에는 STOP 이 없다 (`shots/02`). 배터리 · 관절 온도 · 통신 · 모드를 한 줄로 늘 보이는 띠는 없다 (PC 「상태 띠」 는 끊김 · 알림 한 줄용 · `App.tsx:104`) |
| 3. 한눈에 · 필요할 때 깊이 | 총괄 숫자 줄 → 표 → 서랍 · 운영 관리자 상태 한 줄 → 관측 → 상세 · 접힌 「최근 사건」 「장치·위치」 | 폰 조종 화면의 자세 · 정책 · 실기 시나리오가 「다음 단계」 로 비어 있다 (`shots/15` · `shots/16` · `drive.tsx:143`) |
| 4. 값이 얼마나 오래됐는지 | 「마지막 보고 0초 전」 · 「마지막 수신 22:44:33」 · 지연 ms · 온도 오래되면 빈 줄표 (`seenAt` 등 37 곳) | 화면마다 모양이 다름 (초 전 · 시각 · ms). 영상 · 지도 칸마다 나이 표시는 이번에 확인 못 함 (자료 없음) |
| 5. 로봇 연결 → 시뮬 탭에서 Map → 임무 시뮬 → 「실기도 똑같이」 알림 · 조이스틱 또는 키보드 하나 직결 · 웹 · 앱 하나로 | 같은 웹 코드가 PC · 폰을 다 그림 · 시뮬은 브라우저 안 · 시나리오를 시뮬에서 실행 (`run.tsx:1-3`) | (가) 실기 시나리오 실행 없음 (「준비 중」 · `shots/16`). (나) 「시뮬에서 한 것이 실기에도 똑같이」 를 알리는 화면 없음. (다) **ADR-003: 실기 조종은 폰만 · 키보드는 시뮬 화면에만** (`screens/sim.tsx:3`) 인데 서버 경유 시험 조종은 PC 키보드가 있다 (`serverdrive.tsx:268`) · 팀장 원칙 「조이스틱 또는 키보드 하나 직결」 과 부딪침 (요구 원장에 「갈림」 으로). (라) 시뮬 페이지 (`mobile/sim/index.html`) 는 `apps/web` 과 다른 별도 화면이다. (마) 조이스틱 (`wireless_remote`) 읽기 없음 |
| 6. 모드 표시 「AME-2 Mode」 · 「START Mode」 · 무드톤 · 시뮬과 실기를 단번에 구분 | 시뮬 페이지 안 정책 고르기 (`nvidia-demo` · `start(시연)` · `AME-2(시연)` · `Go2 실기 보기`) · 실기 알약 「실기 · 미검증」 (`realdrive.tsx:74`) · 표의 「실기」 글자 | 「AME-2 Mode: 목표 기반 험지 주행 특화」 「START Mode: 기본 명령 수행 특화」 같은 모드 이름 · 설명 없음. 기본 정책이 네 모드 설계에 없는 `nvidia-demo`. 앱 화면 (`apps/web`) 의 정책 시트는 비어 있음. 모드 · 시뮬 · 실기에 따라 바뀌는 무드 (주사선 · 색 · 바탕) 를 찾지 못함 (`scanline` · `mood` 검색 0). 실기 공간의 Depth · RGB · LiDAR 창은 있으나 시뮬과 같은 틀 |
| 7. 고급스러운 3D · AI Slop 금지 | three.js 3D: Go2 공개 메시 · 라이다 점 · 지형 3D · 지도 칸 3D | 지형 3D 는 청록 단색 상자 · 평평한 그림자 (`shots/07`). 화면 대부분은 평면 카드 · 표 · 테두리 단추 (`shots/02` ~ `shots/10`). 브랜드 토큰은 foothold-brand 1.1.0 과 같은 바이트 (`apps/web/public/brand/SOURCE.md` · 비교 `cmp` 같음) |
| 음성 (명령 · 경고) | 없음 | 앱 · 시뮬 · agent 코드에 음성 기능 0 (`voice · speech · tts · wake` 검색은 agent 의 다른 뜻 3 곳뿐) |
| 관절 온도 · 배터리 경고 (팀장 03:14 값) | 관절 12 온도 색 (범위 표시용 · 위험 기준 아님) · 배터리 잔량 · 20 % 아래 「배터리 낮음」 · 설정의 배터리 부족 기준 | 50 · 60 · 70 °C 문턱 · 이상 체크 · 10 % 단계 · 되풀이 알림 없음 (`go2model.tsx:21`). 같은 일을 하던 PR #389 는 팀장이 폐기 |
| Jetson 저장 남은 GB + [지금 백업] | 없음 (`GB · 백업 · disk` 검색 0) | |
| 실행 구조: 로컬 먼저 · `docker compose` 한 번 · `.env` | Docker 없이 뜨는 개발 도구 (`dev_stack.py`) · 예시 env 셋 | compose 파일 없음 · 실기 기록 재생 길 없음 · 시뮬 자산은 비공개 따로 · 서버 먼저 구조 |
| Jetson agent 자동 시작 금지 · 명시적으로 켤 때만 | 자동 시작 켜기 · 끄기 스크립트 | 설치 묶음이 자동 시작을 켤 수 있는 구조 (`install_jetson_bundle.py:210-215`) · 앱 화면에서 「실기 연결 켜기」 같은 명시적 단추는 찾지 못함 |
| 실시간 3D 지도 (react-three-fiber · 지연 p50 · p95) | three.js 직접 (`three` 0.186) · react-three-fiber 없음 (`apps/web/package.json`) | 지연을 숫자로 재는 장치 없음 (폰 조종의 「지연 ms」 는 링크 왕복 값 · 무엇을 재는지 이번에 확인 안 함) |

## 5. 확인하지 못한 것

- 브라우저 시뮬 화면 전부 (정책 고르기 · 시나리오 실행 · 키보드 · 조이스틱 그림) · PC 세 칸 조종 화면 · Go2 3D 의 실제 모습: 이 기기에서 띄우지 못했다 (0 절).
- 실기 값이 들어올 때의 화면 (배터리 · 온도 색 · 영상 · 점구름 · 값 나이): 가짜 로봇이 보내지 않았다.
- 실제 폰 · Android WebView · 실제 손가락: 헤드리스 Chrome 의 폰 흉내만 했다.
- 밝음 테마: 찍지 않았다.
- 폰 「지연 0.8 ms」 의 뜻 (무엇에서 무엇까지).
- foothold-app `main` 화면 (10/21) 은 보지 않았다.

## 6. 다시 하는 법

```bash
python3 ~/mai/mai-os/tools/wt.py add foothold-app <이름> --ref origin/dev
cd ~/mai/wt/foothold-app/<이름>
python3 -m venv apps/server/.venv && . apps/server/.venv/bin/activate && pip install -r apps/server/requirements-test.txt
(cd apps/web && npm ci)
python apps/web/tools/dev_stack.py server <짧은 경로 · 유닉스 소켓 107 바이트 제한> 8810 &
PYTHONPATH=apps/agent python apps/web/tools/dev_stack.py agent <같은 경로> &
(cd apps/web && CHOKIDAR_USEPOLLING=1 npx vite) &   # 감시 파일 수 한도에 걸리면 polling
# 브라우저 http://127.0.0.1:5180 · 계정 비밀번호는 <경로>/stack.json (커밋 금지)
```
