> 분류: B/항법 · 앱 · PR 분석 (PR #553 · 오현민 현장 로봇 운영 앱 기획서 · PRD · 문서팩)
> 작성: 오흥재 (lead 세션 · Claude 보조 작업자 작성, lead 가 저장) · 2026-10-19 00:46
> 근거: 로컬 가지 `pr-553` (= PR #553 머리 `9774bbe885e1`, OPEN, 10-14 04:28Z 갱신) 를 `git show` 로 읽음 · 공개 저장소 `foothold-project/foothold-app` README (기본 가지 `feature/two-device` 머리 `2dfc0e958230`) · `inbox/jay/20261008-546-design/pr-analysis-20261013/ANALYSIS-members.md` 3 절 · `inbox/jay/20261012-arch-discussion/CONTRACT-nav2-policy-draft.md` · 같은 폴더 `SPEC-start-go2.md` · `SPEC-hipan-go2.md`
> 요지: 앱은 사람이 보며 조종 · 목표 지시 · STOP · 기록을 하는 웹 + 설치형 앱이고 검증은 전부 시뮬 · 에뮬레이션(실기 Go2 · 실제 휴대폰 0 건)이다. 로봇 쪽으로는 몸 기준 속도(vx, wz)와 Nav2 목표만 보내며 실기 Go2 는 「순정 보행 위에 SportClient.Move · StopMove」 로 가정한다. 우리 최종 계획(자체 정책을 실기에서 · HiPAN 5 칸 명령 · 계단 무대 시연)과는 실기 다리 · 명령 분포 · 자세 명령 · 계단 능력에서 어긋난다
> 상태: 분석 · 읽기만 · 현민 확인 전 · 앱 코드 · 다른 가지(less82/*) 미열람

# PR #553 앱 기획서 · PRD 분석 (우리 최종 계획과의 맞물림)

줄 번호는 `pr-553` 가지 기준. **본문** = `inbox/oh/20261013-app-prd.md`, **P/** = `inbox/oh/20261013-app-prd/`, **app README** = 공개 저장소 README (`2dfc0e9`). 문서 대부분은 10-12 12 시 판 사본이고 10-13 · 10-14 진행은 본문 4 · 5 장에 따로 있다(본문:96, :115).

## 1. 앱이 무엇이고 어디까지 왔나

- 「현장에서 사람이 로봇을 보면서 조종하고, 목적지로 보내고, 멈추고 개입하고, 한 일을 기록하는 앱」. 첫 로봇 Go2 (P/PRODUCT-PLAN.md:13, :22~26). 완성 조건: PC 필수 화면 4 종 · 실제 휴대폰 화면 · 실기 Go2 첫 현장 임무 반복 통과 (P/PRD.md:20~25). 요구 44 개 + U-01~08 (본문:47~58, P/PRD.md:286~321).
- 스택(10-14): React 18 · TypeScript · Vite · Tornado 관문 · ROS 2 Jazzy · SQLite/FastAPI 기록 · Capacitor 8 Android (iOS 는 Mac 없음) (본문:121~131). 공개 저장소 기본 가지 README 는 아직 옛 구성(`web/dc.js`)이라 React 판 가지는 미확인.
- 앱이 두 갈래: 로컬 `control-app`(gateway · 임무 · 지도 · Nav2 · `go2_adapter.py`) 과 공개 `foothold-app`. 정본 문제는 PR 이 풀지 않았다.

| 구분 | 내용 | 전제 | 출처 |
|---|---|---|---|
| PRD 「검증」 4 개 | 로그인 · 조종권 한 명 · 명시 버튼 · 도착 → 확인 → 기록 · 공통 웹 | Gazebo TB3 · 헤드리스 Chrome | 본문:79~83 |
| 가상 Go2 통합 | foothold-v2 Gazebo 에 PC 웹 + 휴대폰 웹, 통합 16/16 (10-13) | Gazebo · 모바일 에뮬 | 본문:98 · :102 |
| STOP 뒤 몸 | 명령 0 · 잠금은 관측, 몸은 STOP 뒤 약 3.6 s · 0.32 m 더 움직임(원인 미확인) | Gazebo | 본문:103 |
| Android 에뮬 통합 | INCOMPLETE 35 PASS / 3 FAIL | 에뮬 · 모의 서버 | 본문:142 |
| Go2 어댑터 | 가짜 SportClient 9/9 · 변이 15 개 검출, SDK import 0 회 | 오프라인 | P/GO2-ADAPTER.md:13 · :62~64 |
| 미착수 | 두 엄지 실기 · PC 뎁스 · 3D 점군 · 후진 · Go2 목표 이동 · 실기 Go2 · 실제 iPhone · iOS | | 본문:87~92 · :144 |

저자 스스로 「실기 Go2 · 실제 휴대폰 · 현장 전제로 검증된 요구는 없다」 고 적었다 (P/PRD.md:13).

## 2. 앱이 로봇 쪽으로 보내는 것

- 화면 토픽은 `/app/cmd` 하나 (P/5-system-design.md:39). op: teleop(속도) · goal/cancel(Nav2 `navigate_to_pose`) · stop(정지 래치 + Nav2 취소 + 임무 PAUSED) · take/release/yield(조종권) · hb · set_pose/reset_pose · mission.* (P/5-system-design.md:54~64, P/4-product-functional-spec.md:76).
- **보내는 것은 몸 기준 속도와 Nav2 목표 둘뿐.** 자세(몸 높이 · roll) · 옆걸음 · 모드 전환 · 자연어는 없다 (P/2-screen-flow.md:143, P/4-product-functional-spec.md:71).

| 항목 | 값 | 출처 |
|---|---|---|
| teleop 재전송 · gateway 출력 | 20 Hz · 20 Hz | P/4-product-functional-spec.md:69 · P/5-system-design.md:45 |
| deadman · hb | 0.3 s → 0 · 1.0 s 끊김 → 정지 래치 | P/5-system-design.md:68 · P/PRD.md:73~76 |
| gateway 한계 | max_vx 0.5 m/s · max_wz 1.0 rad/s · 후진 금지 | P/5-system-design.md:68 |
| Go2 어댑터 감시 | 0.3 s 끊김 → Move(0,0,0)+StopMove · 0 을 1 s 받아야 해제 · vy 항상 0 | P/GO2-ADAPTER.md:42~44 |
| foothold-app 실제 값 | 0 · 앞 0.6 · 앞 0.6 + 회전 ±0.5 만, 후진 · 옆걸음 · 제자리 회전 · 저속 · 자세는 서버가 0 | app README:44 · :107 |

경로: 브라우저 → 관문(HTTPS · 로그인 · HMAC 서명) → `/app/cmd` → `app_gateway` → `/cmd_vel_mux` → Nav2 collision_monitor → `/cmd_vel` → `go2_adapter` → `SportClient.Move` · `StopMove` (P/TRUST-BOUNDARY.md:19~22, P/5-system-design.md:21~24, P/GO2-ADAPTER.md:36~38). WebRTC 는 명령 경로에 없다.

안전 규칙 핵심: 브라우저 불신 · 신원은 관문이 정함 · 서명 명령만 · 같은 PC DDS 는 「믿는 영역」(인증 아님) · gateway 가 죽으면 앱은 못 세우고 어댑터 0.3 s 감시가 세움 · 정지 수단 세 겹(앱 STOP · 로봇 끊김 감시 · 제조사 정지) · 자동 재개 없음 · STOP 은 「명령 0 + 잠금」 이고 몸 정지는 별도 측정 (P/TRUST-BOUNDARY.md:26~57, P/6-field-operations.md:56 · :81, P/PRD.md:76 · :86).

## 3. GO2-ADAPTER: 실기 Go2 와 어떻게 말하나

- `unitree_sdk2_python` 의 `SportClient` 직결 우선, `unitree_ros2` 는 Jazzy 호환 미확정 (P/GO2-ADAPTER.md:19~20 · :78). `Move(vx, vy, vyaw)` 와 `StopMove()` 만 부름 (:28~30).
- **저수준 가정: Unitree sport mode(순정 보행).** 「실기 Go2 는 내장 보행 위에 SDK 고수준 명령만」 (P/PRD.md:55 · :59, P/PRODUCT-PLAN.md:37). `StandUp` · `Damp` · 모드 전환은 사람이 리모컨으로 (P/GO2-ADAPTER.md:47). 10/12 결정(실기 = 순정 보행)과는 맞고 #557 최종 계획(실기에서 자체 정책)과는 다르다.
- 상태: SDK 설치 · 실기 연결 0 회, `transport` 는 `mock` 만 (:49 · :83~84). 실기 첫날 검수표(:73~79)는 우리 실기 첫날에도 쓸 만하다.

## 4. 우리 계획과의 맞물림 · 빈칸

### 4-1. 실기 다리가 sport mode
- 우리 정책은 50 Hz 관절 목표 12 개 → SDK `LowCmd`. 순정 보행과 동시에 못 씀. 꽂는 자리는 **`/cmd_vel` 뒤 어댑터 백엔드**(Move 대신 「우리 정책 노드에 vx · wz 전달」). 축은 CONTRACT 초안 1 칸과 같다.
- 새로 정할 것: STOP 의 뜻(정책 0 명령 / sport mode 복귀 / Damp), 정책 프로세스 · Jetson 이 죽을 때 몸을 세우는 법, LowCmd 모드에서 리모컨 우선권 (모두 미확인).

### 4-2. START 명령 분포와 반대
| 항목 | 앱 | START 학습 분포 (SPEC-start-go2.md:111~114) |
|---|---|---|
| 회전 | 앞 0.6 + 회전 ±0.5 (아크) 만, 제자리 회전 금지 | vx ≥ 0.3 이면 wz = 0, vx < 0.3 이면 vx = 0 · 제자리 회전 U[-1.2, 1.2] |
| 저속 | 금지 | vx < 0.3 은 0 |
| 옆걸음 | vy = 0 | vy = 0 |

앱의 유일한 회전(아크)은 START 분포 밖이고 START 의 유일한 회전(제자리)은 앱이 막는다. 정책별 허용 명령표가 필요하다 (P/4-product-functional-spec.md:112 CAP-4 자리, 추정).

### 4-3. HiPAN
- 5 칸 명령 중 vx · wz 만 있음. h · roll 없음, gateway 가 Twist 만 중재해 h · roll 을 STOP · deadman 중재에 넣을 통로가 없다.
- 앱 목표(지도 틀 x, y, yaw + map_ver)는 그대로 두고 「목표 제공자」 노드가 SLAM 자세로 몸 기준 상대 목표를 만들면 된다. 빠진 것은 Nav2 대신 HiPAN 에 목표를 넘기는 gateway 백엔드와 취소 · 도착 판정 규칙. map_ver 결속은 앱이 우리보다 앞서 있다 (P/4-product-functional-spec.md:160~162).
- pose 원천은 HiPAN 쪽도 미정 (SPEC-hipan-go2.md 갈림길 G5, 11/30 SLAM 트랙과 같은 결정).

### 4-4. Laya · 자연어
- 없다. AI 는 SpatialLM 오프라인 · 목표물 인식 후속뿐 (P/PRD.md:227~228). 끼울 자리는 있다(추정): 임무의 「운영자 확인 카드」(P/4-product-functional-spec.md:97) · U-03 경고 목록(P/PRD.md:290) · 「화면은 바라는 것을 보내고 실행 여부는 서버가 정한다」(P/5-system-design.md:108).

### 4-5. 무대 계단 시연에 필요한데 PRD 에 없는 것
1. 계단은 앱이 「할 수 없음」 으로 둠 (FLR-4, P/4-product-functional-spec.md:171).
2. collision_monitor 가 계단을 장애물로 막을 수 있음 (미확인).
3. 「지금 정책 이름 · 판」 표시와 무대에서 NVIDIA · v2 · final 을 안전하게 바꾸는 절차 없음.
4. foothold-app Gazebo 정책 입력이 평면 가정이라 계단에서 어긋남 (본문:163).
5. D435i 뎁스 · 점군 화면 미구현, 센서 목록의 XT-16 은 빼야 함 (P/PRD.md:149~159).
6. 행사장 Wi-Fi 지연 · hb 1 s 정지 래치 위험 미측정.
7. 실제 iPhone · 실기 정지 거리 · 리모컨 경합 미측정.
8. 무대 비상 정지 담당 · 낙상 대비 · 관객 거리 절차 없음.

### 4-6. 그대로 가져다 쓸 것
STOP 래치와 몸 정지 측정을 따로 적는 규칙, 정지 판정 문턱 규칙 (P/PRD.md:86 · :205~209), 어댑터 계약 10 항 (P/GO2-ADAPTER.md:40~49), 서명 명령 · 조종권 한 명 · 자동 재개 없음 · map_ver 결속.

## 5. 현민에게 물을 것
1. 최종 실기는 우리 정책(LowCmd 50 Hz). 어댑터 백엔드를 「정책 노드에 vx · wz 전달」 로 바꾸는 설계를 같이 할 수 있나. STOP 은 정책 0 · sport mode 복귀 · Damp 중 무엇.
2. 앱 정본은 `control-app` 과 `foothold-app` 중 어느 쪽인가. gateway · 임무 · `go2_adapter.py` 공개 가능한가.
3. 허용 명령을 정책별 표로 바꿀 수 있나 (START 는 아크 없음 · 제자리 회전 · 0.3 m/s 이상 전진만).
4. HiPAN 식 자율을 Nav2 와 나란한 gateway 백엔드로 넣을 때 목표 · 취소 · 도착 · map_ver 규칙, h · roll 중재 통로.
5. 무대 계단 시연용 「계단 능력」 을 어떤 근거로 열지, collision_monitor 를 계단 구간에서 어떻게.
6. 「지금 정책 이름」 표시와 무대 정책 교체 절차.
7. Laya 조언을 「운영자 확인 카드」 나 U-03 「주의」 로 띄우는 것, 자연어 입력 범위.
8. 실제 iPhone · STOP · 행사장 Wi-Fi 측정 시점, XT-16 제외.
