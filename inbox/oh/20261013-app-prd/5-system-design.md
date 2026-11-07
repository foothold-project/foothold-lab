# ⑤ 시스템 설계 - 지금 구조와 목표 구조 (2026-10-07 mentor)

> 분류: 계획
> 작성: 오현민 · 2026-10-13
> 근거: `확인됨` 작성자 로컬 문서팩 2026-10-12 12시 판과 대조한 사본. 실기 Go2·실제 휴대폰·현장 검증은 0건.
> 요지: 시스템 설계. 지금 구조와 목표 구조, 둘 사이의 차이.
> 상태: 검토중
>
> 안내: 작성자 로컬 문서팩(2026-10-12 12시 판)의 사본이다. 내용·수치·확정/제안/미정 구분·상태는 그 시점 그대로다. 문자 도식은 표·목록으로 바꾸고 내부 경로·해시·계정은 지웠다. 10-12 이후 구현 기록은 상위 문서 [`../20261013-app-prd.md`](../20261013-app-prd.md) 「작성 시점 이후 진행」에 따로 적었다. 10-14 채택 요구는 이 문서 끝의 날짜 붙은 추가 절로 구분한다.

원 출처: 기능 참고로 든 공식 자료 목록은 [기획서 11장](PRODUCT-PLAN.md). 예: [Foxglove 3D 패널](https://docs.foxglove.dev/docs/visualization/panels/3d) (우리 구현의 증거 아님)

> 기능 ID는 `4-product-functional-spec.md`. 이 문서의 표는 두 종류다: **[현재]** = 코드에서 직접 확인한 실제 인터페이스(파일·행 기준), **[설계 예시]** = 아직 없는 목표 구조. 둘을 섞어 읽지 않는다.

## 1. 한눈에

**현재**: S1 loopback / Gazebo(TB3 대역) 관문 경유 / Go2 어댑터는 오프라인 mock만. S2 Isaac 진단은 보류.

| 순서 | 구간 | 내용 |
|---|---|---|
| 1 | 브라우저(노트북·휴대폰) → phone_gate | wss. 관문이 TLS·로그인·서명·허용 op 를 맡는다 |
| 2 | phone_gate → rosbridge | 같은 PC 안(loopback)에만 열림. 허용 토픽만 |
| 3 | `/app/cmd` → app_gateway → `/cmd_vel_mux` → collision_monitor → `/cmd_vel` → 로봇 | 로봇은 loopback·Gazebo·Go2 어댑터 mock |
| 4 | Nav2 `navigate_to_pose` / `compute_path_to_pose` ↔ app_gateway | `/app/mission_nav` 요청. Nav2 출력 `/cmd_vel_smoothed` 는 NAV 일 때만 통과 |
| 5 | app_gateway → `/app/state` | 상태 |
| 6 | `/app/cmd` → mission_executor → `/app/mission` | SQLite 사건 기록 = 임무 정본 |

**목표(추가되는 것)**: 실기 Go2 SDK 연결(어댑터 실기 검증), 실제 카메라 영상 중계, 장비 어댑터, 층 관리(floor_manager). 로그인 세션·서버 영상 차단·오프라인 로봇 쪽 끊김 감시는 10-07 에 구현했다(④ 참조).

- **화면은 믿지 않는 층이다.** 안전 판단(제어권·heartbeat·STOP 래치·Nav2 취소)은 gateway가, 임무 판단은 mission_executor가 한다.
- **`/cmd_vel_mux`를 쓰는 것은 gateway 하나뿐이다.** 임무 서버도 목표를 gateway를 거쳐서만 보낸다(`/app/mission_nav`).
- 화면은 안전 장치가 아니다. gateway·PC·통신이 죽으면 화면도 서버도 로봇을 세울 수 없다. 그래서 **앱 경로가 사라져도 동작하는 로봇 쪽 명령 끊김 감시**(STP-5)와, 그와 별도로 **제조사 정지 수단·물리 정지 절차**(`6-field-operations.md` §3-4)가 필요하다.

## 2. 실제 인터페이스 [현재]

### 2-1. 토픽
| 토픽 | 타입 | 쓰는 쪽 → 읽는 쪽 | 비고 |
|---|---|---|---|
| `/app/cmd` | `std_msgs/String`(JSON) | 화면 → gateway·mission_executor | 화면이 쓸 수 있는 유일한 토픽(rosbridge `topics_pub_glob`, 관문 `PUB`) |
| `/app/state` | `std_msgs/String`(JSON) | gateway → 화면·mission_executor | 10 Hz |
| `/app/mission` | `std_msgs/String`(JSON) | mission_executor → 화면 | 2 Hz + 바뀔 때 |
| `/app/mission_nav` | `std_msgs/String`(JSON) | mission_executor → gateway | **내부 전용.** 화면·관문 허용 목록에 없다 |
| `/map` | `nav_msgs/OccupancyGrid` | Gazebo 기본: map_server(저장 지도 tb3_sandbox) + AMCL · `S1_SLAM=1`: slam_toolbox · loopback: map_server · (보류) Isaac S2: slam_toolbox → gateway·화면. 한 런에 정본 하나 | transient_local |
| `/cmd_vel_smoothed` | `geometry_msgs/Twist` | Nav2 → gateway | NAV 모드일 때만 통과 |
| `/cmd_vel_mux` | `geometry_msgs/Twist` | **gateway만** → collision_monitor | steady 20 Hz |
| `/cmd_vel` | `geometry_msgs/Twist` | collision_monitor → 로봇 | 입력이 끊기면 아무것도 안 냄(반례 R2에서 확인) |
| `/clock` | `rosgraph_msgs/Clock` | 시뮬 → gateway | use_sim_time일 때만 감시 |

Nav2 액션: `navigate_to_pose`(이동), `compute_path_to_pose`(사전 경로 검사). 서비스: costmap 비우기 2개, `navigate_to_pose/_action/cancel_goal`(gateway 기동 정리).

### 2-2. `/app/cmd` 명령(op)
| op | 받는 쪽 | 조건 | 결과 |
|---|---|---|---|
| `take` | gateway | 누구나 | 제어권 받음 + 정지 래치(take) |
| `release` | gateway | 제어권자 | **정지 해제**(취소 확인 전이면 거절). 이름과 달리 제어권을 놓지 않는다 - owner 유지 |
| `yield` | gateway | 제어권자 | 조종권 내려놓기(CTL-5, 10-07): 출력 0 + 정지 래치(yield) + owner 비움 |
| `hb` | gateway | 제어권자 | heartbeat. 1.0 s 끊기면 정지(link) |
| `teleop` | gateway | 제어권자 | 누르는 동안 속도. 0.3 s 끊기면 0(deadman) |
| `goal` / `cancel` | gateway | 제어권자 | 목표·취소 |
| `stop` | gateway | **누구나** | 정지 래치(stop) |
| `reset_pose` | gateway | 제어권자, 멈춤(IDLE·STOPPED)·목표 없음, `loopback` 매개변수가 참일 때만(Nav2 loopback 시뮬). Gazebo·Isaac·실기는 거부 | **몸을** 시작 위치로 되돌림 → 정지 래치(reset) |
| `set_pose` | gateway | 제어권자, 저장 지도 위치 추정(AMCL) 런 | **위치 추정만** 다시 맞춤(`/initialpose`) - 몸은 그대로. 먼저 멈추고 옛 목표 취소 → 정지 래치(loc_set). SLAM 런에선 화면이 숨김 |
| `mission.start` | mission_executor | 제어권자 | `template_id`, `target`(필요 시) |
| `mission.pause` / `resume` / `answer` / `abort` | mission_executor | 제어권자 | `answer`, `reason` |

- 모든 메시지에 `sid`(화면 탭 ID). `mission.*`에는 `command_id`·`expect_rev`도 붙는다.
- [10-07 해소] 아래 한계는 관문 로그인·서명(`intake()`·`Auth`)으로 막았다 - 현재 동작은 [신뢰 경계](TRUST-BOUNDARY.md). 기록용 옛 서술: **`sid`는 화면이 정해 보내는 값이고 아무도 검증하지 않았다.** 휴대폰 관문(`phone_gate.py` 132~138행)은 허용 토픽·op인지만 보고 메시지를 그대로 rosbridge로 넘긴다. gateway·임무 서버는 메시지의 `sid`를 `owner`와 비교만 한다(`mission_executor.py` 193행). `owner` sid는 `/app/state`로 모든 화면에 보이므로, 관문 토큰을 가진 화면은 그 값을 써서 제어권자 행세를 할 수 있다. «보기 전용 화면 거절» 시험(K3·A11)은 **정직하게 다른 sid를 쓴 화면**만 확인했다. 목표 구조는 §5.
- gateway 기본값(`app_gateway.py` Core): max_vx 0.5 · max_wz 1.0 · 후진 금지 · deadman 0.3 s · hb_timeout 1.0 s · nav_stale 0.5 s · cancel_timeout 2.0 s · plan_timeout 5.0 s · clock_stale 0.5 s(출력만 0) · clock_latch 2.0 s(정지 래치).

### 2-3. 상태 JSON
**`/app/state`** (gateway): `mode`(IDLE·MANUAL·PLANNING·NAV·CANCELING·STOPPED) · `owner`(sid) · `msg` · `stop`(정지 코드: stop·link·take·clock·cancel_timeout·reset) · `gen`(목표 번호) · `res`({gen, status, why}) · `pose`([x, y, yaw, TF 나이]) · `delay` · `out` · `vel` · `nav` · `goal` · `limits` · `sim`.

**`/app/mission`** (mission_executor): `active`(진행 중 임무) · `last`(마지막 끝난 임무) · `templates`(id·title·summary·steps·`why_not`·`needs_target`) · `history`(최근 10개) · `events`(최근 40개, 문장 포함) · `seq` · `acks`(최근 20개) · `identity`(지금 «sid (사람 신원 미확인)»).

- **[현재 한계] snapshot은 최근 것만 담는다**(`mission_executor.py` 393~399행: 사건 최근 40개·이력 최근 10개·ack 최근 20개). 끊긴 동안 40개보다 많이 쌓이면 화면의 «끊긴 동안 있었던 일»에서 빠지고, 빠졌다는 표시도 없다. 목표: seq 범위 요청 + 빠진 번호 표시 + DB 보존·내보내기 기준(REC-6).

임무 상태: `RUNNING` · `PAUSED` · `SUCCEEDED` · `FAILED` · `ABORTED`. 계약 문서의 READY는 **화면 쪽 선택 단계**이고 서버 상태로는 없다. 멈춤 이유(`pause.reason`): `await_operator` · `operator` · `stop` · `link` · `take` · `clock` · `cancel_timeout` · `manual` · `gateway` · `server_restart` · `failed` · `interrupted`.

### 2-4. 저장 [현재]
`.mission/<스택>-d<도메인>.db` (SQLite)
```
events(seq INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, mission_id TEXT, type TEXT, by TEXT, command_id TEXT, data TEXT)
acks(command_id TEXT PRIMARY KEY, ack TEXT)
```
- 사건 종류: `created` · `step_started` · `step_done` · `paused` · `resumed` · `answered` · `ended` · `command`(명령 감사 - rev를 올리지 않음).
- 상태는 기록을 처음부터 다시 적용해 만든다(`apply()`). 앱 코드는 덧붙이기만 한다.
- **한계**: 파일 권한만으로 보호한다. 해시 사슬·서명 같은 변조 방지는 없다. 디스크가 망가지면 기록도 잃는다 → 백업(REC-5).
- 한 기록 파일에 서버 하나: `<db>.lock` 파일 잠금(flock).
- [현재, 10-07] **기록은 한 트랜잭션.** `on_cmd` 는 ack·`command` 감사 사건·상태 사건을 `store.tx()` 하나로 commit 하고, commit 뒤에만 ack 와 이동 명령을 낸다. commit 전에 죽으면 아무것도 남지 않고(같은 `command_id` 로 다시 보내면 처음처럼 실행), commit 뒤·이동 전달 전에 죽으면 재시작 때 PAUSED(server_restart)·자동 재개 없음. 같은 `command_id` 를 다른 주체·내용이 쓰면 거절. 실패 주입 반례는 selftest(`atomic_selftest`).
- 🔴 **[현재 한계]** 이동이 바깥 세계(Nav2·장비)에 닿은 뒤의 «정확히 한 번 실행»은 보장·검증하지 않았다. 목표는 §4 7·8번.

## 3. 데이터 사전

| 이름 | 누가 만드나 | 뜻 | 쓰임 |
|---|---|---|---|
| `sid` | **관문**(연결마다, 화면이 보낸 값은 지움) | 화면 연결 ID. 사람 신원이 아니다 | 제어권 주인 |
| `actor` | 관문(로그인 계정 + 서버가 정한 기기 id) | 사람·기기 | 기록 주체·표시(IDN-2) |
| `command_id` | 화면 | 버튼 한 번 = ID 하나 | 같은 ID 재전송 → 실행 없이 처음 답 반환 |
| `expect_rev` / `rev` | 화면이 보고 있던 rev / 서버 | 임무가 바뀔 때마다 +1 | 다르면 «이미 바뀌었습니다» 거절(옛 화면 방지) |
| `ack` | 서버 | {command_id, ok, why, op} | **«받았다»일 뿐 «끝났다»가 아니다.** 끝은 사건으로 알린다 |
| `attempt_id` | 서버 | 한 단계의 한 번 실행(다시 하면 새 ID) | 결과·근거를 시도별로 기록 |
| `gen` | gateway | gateway 목표 번호 | 단계가 «자기 목표»의 결과만 보도록(옛 응답 무시) |
| `seq` | 기록 | 사건 순번 | «끊긴 동안 있었던 일» 기준 |
| `building_id`·`floor_id`·`map_version` [설계 예시] | 지도 관리 | 층별 지도 식별 | FLR-2 |

## 4. 서버 정본과 명령 처리 규칙

1. 화면은 «바라는 것»을 보낸다. 실행 여부는 서버가 정하고, 거절하면 쉬운 말 이유를 돌려준다.
2. [현재] 명령 처리 순서(`mission_executor.on_cmd`): 같은 `command_id`가 있으면 주체·내용이 같을 때만 처음 답(다르면 거절) → 검사(gateway 상태 → 제어권자 sid → 위치 추정 → 지도 버전 → op별 조건) → **ack·감사·상태 사건을 한 트랜잭션으로 commit** → commit 뒤에만 ack·이동(§2-4). [목표]는 아래 7·8번.
3. **수락과 완료를 섞지 않는다.** ack는 즉시 오고, 단계 성공은 도착 판정(Nav2 성공 + 위치 오차) 뒤 사건으로 온다.
4. 단계는 보내기 직전 gateway의 `gen`(gen0)을 기억하고, 그보다 큰 gen의 결과만 자기 것으로 본다. 다른 목표가 끼어들면 «중간에 끊김»(interrupted)으로 멈춘다.
5. 재시작: 진행 중 임무 → PAUSED(server_restart). gateway에 남은 옛 목표는 **처음 본 그 gen만** 5 s 안에 취소한다(다른 화면의 새 목표는 건드리지 않는다).
6. gateway 재기동: 자기가 목표를 하나도 안 보냈을 때만 «지금 이전 Nav2 목표 전부» 취소(반례 R4). 전제는 이 스택에서 Nav2에 목표를 보내는 것이 gateway 하나뿐이라는 것이다 - RViz·다른 API로 보낸 목표도 같이 취소된다. **시스템 제약으로 둔다**: 운용 중 Nav2 목표 송신자는 gateway 하나. 다른 송신자가 있는 구성은 검수 R9로 따로 확인.
7. [기록 원자성은 현재 구현, 나머지 목표] **원자 처리**: 명령 접수 기록·ack·상태 전이 사건을 한 트랜잭션으로 commit 한다(구현). 실행이 바깥 세계(Nav2·장비)에 닿는 부분은 «보냄 → 결과 확인» 두 사건으로 나눠, 재시작 때 «보냈는데 결과 모름» 지점을 찾을 수 있게 한다(MIS-13).
8. [목표] **불분명한 결과는 자동 재시도하지 않는다.** 재시작·끊김 뒤 결과를 모르는 명령은 PAUSED + «결과 확인 필요»로 두고 운영자가 확인한다. 장비 명령에는 장비 쪽 중복 키(idempotency key)와 결과 조회를 요구한다 - 장비가 지원하지 않으면 그 장비 능력은 «검증 안 됨»으로 둔다.

## 5. 제어권·신원

- [현재] 제어권 주인 = 관문이 정한 `sid`(+ 표시용 계정·기기). 누구나 `take` 가능(받는 순간 정지 래치), 주인은 `yield` 로 내려놓음, STOP은 누구나.
- [현재, 10-07] 관문 계정 로그인(scrypt, IP별 300 s 안 5회 실패 잠금, 세션 8 h) → 관문이 sid·actor{account, device}를 정해 명령에 서명해 붙인다. 화면이 보낸 sid·actor 는 지운다.
- [10-07 이전 기록] sid 는 화면이 만든 값이라 권한 증거가 아니었고(보기 전용 거절은 정직한 화면에만 통함), 기록 주체도 탭 sid 였으며 로그인 세션이 없었다 - 10-07 관문 로그인·서명으로 해소(CTL-4·IDN-1·2, Gazebo fin-auth 13/13).
- [설계 예시 - 대부분 10-07 구현, 아래 «현재» 줄 참조] 로그인 세션 → 관문이 검증된 세션에서 `actor`(operator_id)·`device_id`·제어권 `lease`를 꺼내 메시지에 붙여 rosbridge로 넘긴다. 서버는 화면이 보낸 sid·신원 필드를 권한 근거로 쓰지 않는다. owner = (operator_id, device_id, lease). lease는 take 때 서버가 발급하고 화면은 그 값을 볼 수 없게 한다(지금처럼 `/app/state`에 공개하지 않는다)(CTL-4·IDN-2).
- **결정: 신원 계약을 이력·보고 화면(F4)보다 먼저 고정한다.** 기록 형식이 sid로 굳은 뒤 바꾸면 옛 기록을 옮겨야 한다(`7-roadmap-decisions.md` D-3).

## 6. 네트워크와 배치

- **로컬 서버 + 현장망이 기본이다.** PC(또는 로봇 탑재 컴퓨터) 하나에 gateway·임무 서버·관문·웹 파일을 두고, 현장 Wi-Fi/LAN으로 화면이 붙는다. 인터넷·클라우드는 필수가 아니다.
- 클라우드는 선택이다: 원격 관제·기록 보관용. 제어 경로는 현장 안에 둔다.
- 보호 없는 제어 포트를 열지 않는다: rosbridge는 127.0.0.1에만, 바깥은 관문(TLS + 로그인 + 서명 + 허용 목록)으로만.
- 시뮬 연결(S2, 보류): RunPod Isaac ↔ zenoh 터널 ↔ PC. 공개 포트를 열지 않는다.
- [현재, 10-07] 앱 스택의 DDS 는 `run_s1.sh` 가 `ros/fastdds_local.xml` 을 지정한다: 127.0.0.1 UDP 만(공유 메모리 없음), SUBNET 범위 + 주소 화이트리스트, 정적 피어 없음. **인증·암호화가 아니다** - 같은 PC 의 다른 프로세스는 붙을 수 있다. Gazebo 의 발견 포트(0.0.0.0:10317/10318)는 DDS 가 아니며 그대로 열린다(시뮬 한정). 범위는 [신뢰 경계](TRUST-BOUNDARY.md).

## 7. 화면 기술 - 웹앱, 선택 PWA, 네이티브 조건

- **웹앱이 기본이다.** 노트북·휴대폰 공용, 설치 없음, 공용 기기·관제 화면에 바로 쓸 수 있다.
- **설치형 PWA는 선택이다**(SYS-6, 미검증). 단말이 믿는 HTTPS 인증서가 전제다([MDN - PWA 설치 조건](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)).
- **PWA 캐시 규칙**(목표): 캐시하는 것은 화면 파일(HTML·JS·CSS·아이콘)뿐이다. 상태·지도·영상·명령은 캐시하지 않는다. 연결 전·끊긴 동안은 «연결 안 됨»만 보이고 옛 상태를 현재처럼 보이지 않는다. 끊긴 동안 누른 버튼을 모아 두었다가 다시 붙은 뒤 보내지 않는다 - 다시 붙으면 서버 상태부터 받고 사람이 새로 누른다. 서버 버전과 화면 버전이 다르면 조작을 막고 새로고침을 안내한다.
- 화면이 가려지거나 앱이 백그라운드로 가는 것은 [Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)로 알 수 있지만, 백그라운드 탭은 타이머가 늦춰질 수 있어 heartbeat가 끊긴다 - 이것이 정지로 이어지는 것은 의도된 동작이다(CTL-3).
- **설치형 앱(apk/exe)이 생겼다**(10-08 오후, `clients/README.md`, `7-roadmap-decisions.md` D-1). 웹앱은 그대로이고, 앱은 관문 https 주소를 그대로 여는 껍데기다(Android 시스템 WebView · Windows Electron). 그래서 /api·ws·로그인 쿠키가 같은 출처로 남아 gateway·관문·CORS 는 바꾸지 않았다(옛 걱정 ①②는 이 방식으로 해당 없음). ③ 인증서는 우회하지 않는다 - 기기에 사설 CA 를 설치(Android 사용자 CA·Windows 현재 사용자 루트), 믿지 않으면 화면을 열지 않고 설치 안내. ⑤ 앱이 백그라운드로 가면 입력을 놓고 JS 타이머를 멈춘다 → heartbeat 끊김 → 서버 정지(link)·자동 재개 없음(에뮬레이터 1.0 s 실측). 앱이 죽어도 같은 감시로 정지. 관문 밖 주소는 앱 안에서 열지 않는다. ⑥ 검증: 에뮬레이터(Android 14) 14/14 · 같은 데스크톱 코드 Linux Electron 10/10 - **실폰·Windows 실기·iOS 는 미검증**, ④ iOS 로컬 네트워크 권한과 ipa 는 Mac·Xcode·Apple 계정이 있어야 해서 **ipa 미생성**. exe 는 코드 서명이 없어 SmartScreen 경고가 뜬다. apk 서명 키(`clients/android/keystore/`)를 잃으면 업데이트 설치가 안 된다.
- 어느 쪽도 화면 꺼짐·앱 백그라운드·통신 끊김에서 안전을 보장하지 않는다 → heartbeat 정지(CTL-3) + 로봇 쪽 감시(STP-5) + 자동 재개 없음.
- 장갑·우천 조작은 소프트웨어 종류보다 단말과 물리 조종기의 영향이 크다(브라우저 Gamepad API는 후보, 미검증).

## 8. 센서·영상 - 확정 근거를 따로 둔다

- 이번 로봇(Go2)의 센서 모델·영상 소스·전송 방식은 **미확정**이다. 다른 곳(예: 수업 실기)의 Go2 구성을 이 로봇의 구성으로 가정하지 않는다.
- 확정 방법: 실물 확인(모델명) → 드라이버·SDK 문서 → PC에서 데이터 수신(녹화) → 지연·주기 실측. 이 네 가지가 기록되기 전에는 화면·능력 등록에 쓰지 않는다.
- 영상 설계 [설계 예시]: 로봇/PC에서 WebRTC 등으로 중계 → 화면. 프레임에 «촬영 시각»이 있으면 촬영 나이를, 없으면 «마지막 프레임 수신 n 초 전 · 촬영 시각 미확인»을 표시한다(VID-2). 수신 나이는 «최근에 받았나»일 뿐이다 - 네트워크·인코더 버퍼에 묵은 프레임이 방금 도착하면 수신 나이는 0이지만 영상은 오래된 것이다(검수 V2 반례). 촬영→화면 지연은 화면에 시계를 띄워 카메라로 다시 찍는 방식 등으로 따로 잰다(V3). [현재, 10-07] 시뮬은 Gazebo 카메라 → `gz_video`(JPEG) → 화면, 서버 VideoGate 가 촬영 나이·끊김을 본다. (옛 진단: Isaac `/camera/rgb`, zenoh 2 Hz 제한)

## 9. 지도·위치 - `/map`과 TF의 정본은 하나

- [현재 S1] loopback: map_server가 `/map`, loopback 시뮬이 `map→odom` TF.
- [현재 S2] rko_lio가 `odom→base_link`, slam_toolbox가 `/map`과 `map→odom`(매핑 모드). 2D 스캔은 3D 점군을 로봇 몸 높이 기준(`base_stabilized`)으로 잘라 만든다.
- **규칙: `/map`과 `map→odom`을 내는 노드는 한 번에 하나.** SLAM과 map_server+AMCL을 같이 띄우면 TF가 두 곳에서 나와 위치가 튄다. 운용 모드(매핑 / 저장 지도 위치추정)를 바꿀 때는 한쪽을 내리고 다른 쪽을 올린다.
- 운용 위치추정 방식(slam_toolbox 저장 그래프 위치추정 vs map_server+AMCL)은 미정이다(D-6).

## 10. 다층 설계 [설계 예시]

- **층별 2D 지도 + 위 계층(임무 서버 옆 `floor_manager`)에서 층 관리.** Nav2 본체를 고치지 않는다 - Nav2는 «지금 활성 층 안의 목표»만 받는다. Nav2 `map_server`의 `load_map` 서비스로 런타임 지도 교체가 가능하다([nav2_map_server README](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_map_server/README.md)).
- 목표·기록은 `(building_id, floor_id, map_version, x, y, yaw)`로 저장한다. 층마다 지도 원점이 다르니 같은 (x, y)가 층마다 다른 곳이다. map_version이 다른 옛 목표는 실행하지 않는다.
- **층 전환 단계**(FLR-3): ① 이동 정지 + 옛 Nav2 목표 취소 ② 사람이 층 이동을 확인(자동 계단·엘리베이터는 검증된 능력이 없다) ③ 지도와 위치추정을 함께 교체 ④ 위치가 튀는 동안 출력 0, 비용지도·경로 비움 ⑤ 위치 수렴 확인(기준 TBD) ⑥ 새 목표.
- 화면은 **로봇의 실제 층**과 **운영자가 보고 있는 층**을 구별해 표시한다(FLR-5).
- 함정: 계단·아트리움으로 다른 층이 2D 스캔에 섞일 수 있다 → 층별 진입 금지 구역(Nav2 keepout 필터). 계단 위에서는 이 2D 구조가 맞지 않는다(기울기·높이 변화) → 계단 보행은 Nav2 밖 별도 능력. rko_lio 오도메트리가 층 사이에 끊기지 않는지는 실측 전.

## 11. 안전 계층 (위에서 놓쳐도 아래가 잡는다)

| 층 | 무엇 | 지금 |
|---|---|---|
| 화면 | 누르는 동안만 보내기, 두 번 눌러 중단 | 구현 (안전 장치로 치지 않음) |
| gateway | 제어권·heartbeat·deadman·STOP 래치·시계 감시·취소 확인·영상 차단 | 검증(S1 loopback·Gazebo fin-auth) |
| 임무 서버 | 자동 재개 없음, 멈춘 이유가 풀려야 계속. 죽으면 임무 목표 정지 래치 | 검증(loopback·Gazebo fin-kill 4/4) |
| collision_monitor | 장애물 앞 감속·정지 | 검증(loopback 가짜 레이저). 실기 정지거리 미측정 |
| **로봇 쪽 명령 끊김 감시** | 명령이 0.3 s 안 오면 Move(0)+StopMove·래치 | **오프라인 mock 만 9/9 - 실기 검증 전 필수**(STP-5, [GO2-ADAPTER](GO2-ADAPTER.md)) |
| 장비 인터록 | 장비 측 하드웨어 차단 | 장비 미정 |

- **지금 «전체 정지»(STOP)는 이동만 멈춘다.** 장비 정지 경로는 없다(STP-3·4 미구현).
- gateway가 정상 종료(Ctrl-C)하면 마지막 출력 0을 낸다(반례 R6). 하지만 그 시험에서 시뮬도 함께 내려가 **몸이 실제로 섰는지는 측정하지 않았다.** 시험 로그 끝의 `WebSocketClosedError`는 시험 도구가 스택이 내려갈 때 낸 종료 예외다.
- gateway가 죽으면(KILL·크래시) 앱은 0을 낼 수 없다. 반례 R2에서 몸이 선 것은 loopback 시뮬 자체의 1 s 감시 덕이다(`/opt/ros/jazzy/lib/python3.12/site-packages/nav2_loopback_sim/loopback_simulator.py` 237행). 실기는 로봇 쪽 감시(STP-5, 어댑터는 오프라인만 검증) **그리고** 제조사 정지 수단·물리 정지 절차가 필요하다.

## 12. 참고 구조
- 상용 로봇 운영 플랫폼의 구성 예: [Boston Dynamics Orbit 개요](https://dev.bostondynamics.com/docs/concepts/orbit/about_orbit.html) - 임무·기록·원격 운영을 한 서버에 모으는 구조의 참고일 뿐이며, Go2 지원이나 이 앱의 기능 근거가 아니다.

## 바뀐 이력
- 2026-10-07 처음 작성.
- 2026-10-07 Codex 2차 검수 반영: §1 정지 수단 표현, §4 실제 ack 선커밋 순서, §7 네이티브 조건(잠긴 화면 알림만으로는 아님), §8 촬영 나이/수신 나이.
- 2026-10-07 Codex 문서 검수 반영: sid 위조 한계·commit 분리 crash 창·snapshot 제한을 [현재 한계]로, 원자 처리·불분명 결과 무재시도·lease를 [목표]로. PWA 캐시 규칙, 영상 «받은 뒤 n 초»와 지연 구분, 종료 시험 범위, 공식 링크.
- 2026-10-07 최종 정리: 현재 그림(Gazebo·Go2 mock, Isaac 보류), `yield` op, 기록 한 트랜잭션, 관문이 정하는 sid·actor, DDS 로컬 프로필·Gazebo 발견 포트, 안전 계층 근거 갱신.
- 2026-10-07 Codex 중간 검수(msg_9bb45af9ae25): `/map` 행 런별 정본, `reset_pose`(몸 되돌리기, loopback 만)와 `set_pose`(위치 추정만) 구분.
- 2026-10-08 §7 설치형 앱: 조건부 후보 → 추가 방향(사용자 선호), 패키지 전 고칠 것 6가지. apk/ipa 파일은 아직 없음.
- 2026-10-08 오후 §7: apk(서명)·exe(코드 서명 없음) 생성, 관문 주소를 그대로 여는 방식이라 서버 변경 없음. 에뮬레이터·Linux 시험 통과, 실기·iOS 미검증.

## 2026-10-14 추가: 개선 채택·구현 중

이 문서에 영향 있는 새 범위는 **웹과 네이티브 전송 분리·제한된 probe/QR 계약·상태 데이터 출처·지도 결속**이다. [PRD 추가 요구 U-01~06](PRD.md#2026-10-14-추가-요구-unitree-비교-개선-채택)의 수락 기준을 따른다. 10-12 당시 상태·수치는 유지한다. 현재 웹·APK `eb46259`는 개선 전이며 새 요구 완료·실폰/실Gazebo 검증을 뜻하지 않는다. 구현·모의·실환경 판정을 별도 갱신한다.
