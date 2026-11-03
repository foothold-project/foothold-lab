> 분류: B/앱 · 앱 개발 준수 사항 (정책 모드 넷 · start-demo · ame2-demo 적용)
> 작성: 오흥재 · lead 세션 · 2026-11-03 16:3x v0.1 · 19:1x v0.2 · 21:5x v0.3 (단일 문서로 정리 · 최종 결정만 · 모드별 명령 표)
> 근거: 앱용 묶음 `inbox/jay/20261103-policy-handoff/start-demo-app/` (lab PR #571) · `inbox/jay/20261103-policy-handoff/ame2-demo-app/` (석헌 님 PR #574 묶음 + lead 보완 #576) · m6000 조건표 `start-demo-app/CONTRACT.md` §3.5 (명령 범위 · D108) · foothold-app dev `1fbe6f6c`(2026-11-03 12:38Z) 를 받아 줄 번호를 다시 잼
> 요지: 현민 님이 이 문서 하나만 보고 start-demo · ame2-demo 를 앱에 붙인다. 파일 자리 · sha · 입출력 · 상태 되먹임 · 시험 벡터 확인법 · 앱 파일별 할 일 · 모드마다 명령이 학습 범위대로 정책에 들어가는지 · JS f32 되돌림 규칙 · 끝 확인 목록을 모두 여기에 둔다. 최종 결정만 적고, 재지 않은 것은 「미확인」 으로만 적는다
> 상태: v0.3 · 두 묶음 lab main 에 있음 · 앱 작업 이슈 foothold-app#259

# 앱 개발 준수 사항 · 정책 모드 넷

이 문서 하나로 일한다. 다른 문서(CONTRACT.md 등)는 값의 근거를 보고 싶을 때만 연다. 이 문서와 다른 문서가 다르면 이 문서가 맞다. `ame2-demo-app/CONTRACT.md` §7 「추가 확인 · 남은 한계」 는 참고이고, 결정은 이 문서다. 앱은 폴더 `start-demo-app/` · `ame2-demo-app/` 둘만 본다. 원본 제출: `inbox/lim/20261103-policy-handoff/ame2-demo/` (석헌 님 PR #574, 참고).

## 0. 결정된 것 (다시 묻지 않는다)

- **모드 넷과 이름(D170).** 코드 키 `nvidia` · `start` · `ame2` · `go2`. 지금 id `nvidia-demo`(앱의 `foothold-v2` 를 이름만 바꿈) · `start-demo`(저장본 m6000) · `ame2-demo`(저장본 m14999) · `go2-oh2l2`(정책 없음, 실기 Sport 모드 상태를 그리기만). 최종 모델이 오면 id 만 `nvidia-foothold-v2` · `start-oh2l2` · `ame2-oh2l2` 로 바꾸고 키는 그대로 둔다. 나중 판 이름: 학습 완료 판은 `start-oh2l2-app/` · `ame2-oh2l2-app/` 로 같은 꼴의 폴더를 새로 만든다(D170 최종 이름 + `-app`).
- **ONNX 가 기본 계산이다.** 같은 ONNX 하나를 웹 시뮬과 실기가 함께 쓴다. ONNX 파일은 앱 저장소에 커밋하지 않고 lab 묶음 폴더에서 복사해 sha256 이 맞을 때만 쓴다.
- **JS f32 되돌림은 ONNX 가 안 될 때의 대비로 남겨도 된다**(팀장 11/03 21:4x). 단 ① 기본은 ONNX ② 되돌림이 켜지면 화면에 늘 보이게 표시(§2-6). start 는 f32 가 없으므로 되돌림 없이 ONNX 만 쓴다.
- **ONNX 실행기는 상태 출력(start 의 GRU 둘)을 다음 호출 입력으로 되먹이고, 입력 자료형(bool 포함)을 계약대로 만든다.**
- **모드별 값은 통째로 갈아 끼운다.** 한 모드 값을 다른 모드의 기본값으로 쓰지 않는다(예: 토크 23.5). 지도 함수도 모드마다 따로.
- **명령은 모드마다 학습 범위 안으로 정책에 들어가야 한다**(팀장 11/03 21:4x). 모드 상한과 앱 · 조직 설정이 그 범위를 깎지 않게 한다(§1.5). 예외는 nvidia 하나: 옆 막대 0.5 를 그대로 두어 학습하지 않은 동작이 잘 안 되는 것을 보여 준다.
- **가속 제한(D108):** 미확인: 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음). 학습도 명령을 계단식으로 바꿨다.
- **서버 쪽 범위 표 `policy_ranges.py` 는 이번 일에서 손대지 않는다.** 브라우저 MuJoCo 시뮬만 고친다(그 파일은 런타임에서 읽는 곳이 없다).

## 1. 파일 · sha · 입출력

### 1.1 받을 파일 (lab 저장소 main)

| 모드 | 자리 | 파일 | sha256 |
|---|---|---|---|
| start | `inbox/jay/20261103-policy-handoff/start-demo-app/` | `start-demo_map_on.onnx`(정답 · 복원) | `81c7e079516058ee6243f6edd11efa8f0da239c6cc86fbca791bda5bcd82f110` |
| | | `start-demo_map_off.onnx`(끔) | `5d1b7bf39aa0d9fb8ae33bf33dad82902165d53679ccd7ec5df727a0b70fe037` |
| | | 시험 벡터 `test_vectors_flat20_reconstruction.json` · `_gt.json` · `_off.json` | `215ac522…` · `9f39abe1…` · `6cdb87af…` (전부 폴더 `SHA256SUMS`) |
| | | 앱 계약 꼴: `contract.json` 의 `app_onnx` 칸 | contract.json `427ccdb3…` |
| ame2 | `inbox/jay/20261103-policy-handoff/ame2-demo-app/` | `ame2-demo.onnx` | `830595df1e78072c0606b5193d1ba787720ff6777edc7cabe496b8c1a9d25de6` |
| | | 시험 벡터 `test_vectors_flat20.json` (같은 내용 `.npz`) | `95bb7ab1be2d7414b495a4e79df8a3a311b703123c4588355621397fb74c7077` |
| | | 앱 계약 꼴: `app_onnx.json` · 조건표 `CONTRACT.md` · `contract.json` · `parity.json` | 폴더 `SHA256SUMS` |

받은 뒤 각 폴더에서 `sha256sum -c SHA256SUMS` 가 전부 OK 여야 쓴다. 폴더마다 `.gitattributes` 가 `* -text` 라 Windows 에서 받아도 sha 가 같다.

### 1.2 세 정책 공통

| 값 | 숫자 |
|---|---|
| 제어 | 50 Hz = 물리 dt 0.005 s × decimation 4 |
| 관절 순서(정책 입출력) | `FL_hip FR_hip RL_hip RR_hip FL_thigh FR_thigh RL_thigh RR_thigh FL_calf FR_calf RL_calf RR_calf`. 앱 MuJoCo 내부 순서와는 이름으로 재배열 |
| 기본 관절각(위 순서) | `[0.1, -0.1, 0.1, -0.1, 0.8, 0.8, 1.0, 1.0, -1.5, -1.5, -1.5, -1.5]` |
| PD | Kp 25 · Kd 0.5 (12 관절) |
| 목표각 | 기본 관절각 + 0.25 × a (a 를 먼저 모드별로 자름) · 목표 속도 0 · 앞먹임 토크 0 |
| 관측 정규화 | 없음 |

### 1.3 start 와 ame2

| 칸 | `start` (start-demo) | `ame2` (ame2-demo) |
|---|---|---|
| 정책이 받는 명령 | 몸 속도 (vx, vy, wz) · `obs45[6:9]` | 목표 [x, y, sin e, cos e] · `prop[45:49]` (§1.5) |
| 몸감각 관측 | 45 = 각속도 3 · 중력 3 · 명령 3 · 관절각 − 기본 12 · 관절 속도 12 · 직전 a 12 (배율 1 · 자르기 없음) | 49 = 몸 속도 3 · 각속도 3 · 중력 3 · 관절각 − 기본 12 · 관절 속도 12 · 직전 raw a 12(±50 자름) · 목표 4 |
| 이력 · 상태 | 이력 10 × 45 (오래된 것이 앞, 리셋 뒤 첫 관측으로 채움) · GRU `h_prop` · `h_terr` 각 128 (리셋 때 0, 출력을 다음 입력에) | 없음 (매 스텝 독립) |
| 지도 | 32 × 16 · 5 cm · 높이 1 채널. 몸 앞 +0.3 m 중심, x −0.475~+1.075 · y −0.375~+0.375, yaw 만 정렬, 값 = 바닥 높이 − 몸 높이(±1 m 자름), 못 맞힌 칸 −1, 배열 순서 yx | 29 × 13 × 3 (x, y, z) · 6 cm. x −0.42~1.26 · y ±0.36, yaw 정렬, x 가 바깥 축, z = 바닥 높이 − 센서 높이 + 0.27 (±1.5 자름) (앱 `ame2-adapter.js` 에 이미 있음) |
| 지도 모드 | 정답 · 복원 · 끔 셋 (시뮬은 셋 다, 실기는 복원 · 끔) | 정답 하나 |
| 깊이 | 60 × 60 · 10 Hz(5 스텝마다) · 정책에는 1 프레임 늦은 최근 2 장 · (d − 0.2)/2.8 을 [0,1] 로 · 미검출 1.0 · 카메라 몸 기준 (0.25, 0, 0.12) m · 아래로 35° · fx 55.9 fy 54.1 cx cy 30 | 없음 |
| 토크 곡선 | DCMotor: hip · thigh 한계 23.5 · 포화 23.5 · 속도 30.0 / calf 45.43 · 45.43 · 15.70. 상한 = min(한계, 포화 × (1 − q̇/v)), 하한 = max(−한계, 포화 × (−1 − q̇/v)) | Go2HV 곡선 (앱 `ame2-adapter.js:14-22` 그대로) |
| a 자르기 | ±17 | ±100 (목표각 쪽 `targetClip`) |
| 행동 지연 | 0 | 0 (§3-4) |

### 1.4 ONNX 입출력 (앱 계약에 그대로 넣는다)

**start** (`start-demo-app/contract.json` 의 `app_onnx` 칸을 그대로 쓴다. 입력 순서 = ONNX `session.inputNames` 실측 순서)

| 입력 | 모양 | 자료형 | 넣는 값 |
|---|---|---|---|
| `obs45` | [1,45] | float32 | §1.3 몸감각 45 |
| `hist` | [1,10,45] | float32 | 직전 10 스텝 obs45 (오래된 것이 앞) |
| `depth2` | [1,2,60,60] | float32 | 1 프레임(0.1 s) 늦게 전달된 최근 깊이 두 장 |
| `h_prop` · `h_terr` | [1,128] 씩 | float32 | 앞 호출의 `h_prop_next` · `h_terr_next` (리셋 뒤 0) |
| `depth_tick` | [1] | **bool** | 새 깊이 프레임이 들어온 스텝(5 스텝마다)만 true |
| `first_after_reset` | [1] | **bool** | 리셋 뒤 첫 호출만 true |
| `use_gt` | [1] | **bool** | 정답 지도 모드면 true, 복원이면 false (끔 모드는 `_map_off` 파일) |
| `gt_map` | [1,32,16] | float32 | 정답 지도(정답 모드), 다른 모드는 0 |

| 출력 | 모양 | 쓰는 곳 |
|---|---|---|
| `action` | [1,12] | ±17 자르기 → 목표각 |
| `h_prop_next` · `h_terr_next` | [1,128] 씩 | 다음 호출의 `h_prop` · `h_terr` |
| `recon_map` | [1,32,16] | 화면 표시용(복원 지도) |

지도 모드 셋: **정답** = `_map_on` + `use_gt` true + `gt_map` · **복원** = `_map_on` + `use_gt` false · **끔** = `_map_off`. 지도 모드를 바꾸면 세션을 바꾸고 상태 0, `first_after_reset` true 로.

**ame2** (`ame2-demo-app/app_onnx.json` 을 그대로 쓴다)

| 입력 | 모양 | 자료형 |
|---|---|---|
| `prop` | [1,49] | float32 |
| `mapping` | [1,29,13,3] | float32 |

| 출력 | 모양 | 쓰는 곳 |
|---|---|---|
| `action` | [1,12] | 목표각 = 기본 + 0.25 × action. 다음 스텝 `prop[33:45]` = clip(action, −50, 50) |
| `gaze_r` | [1,2] float32 | 진단(화면 표시). crop 모서리 ox = clamp(round(r0 × 17), 0, 17) · oy = clamp(round(r1 × 3), 0, 3), 29 × 13 지도 안의 12 × 10 창 |

ame2 는 상태가 없다(되먹임 없음).

### 1.5 모드마다 명령: 학습 범위 · 정책 입력 칸 · 앱이 깎는 곳

**지금 앱의 명령 흐름(dev 1fbe6f6c).** 손 조종은 막대 값(−1~1)에 축 상한을 곱해 만든다(`manual-settings.js:17-21` `manualAxis`). 축 상한 = min(모드 `joystickScale`, 조직 설정 `sim_max_vx` · `sim_max_vy` · `sim_max_wz`)(`manual-settings.js:14`). 조직 설정은 웹에서 연 시뮬(`?from=web`)에서만 읽고(`settings.js:25`), 허용 범위가 `sim_max_vy` 0~0.3 · `sim_max_wz` 0~0.5 이며 기본값도 0.3 · 0.5 다(`manual-settings.js:3` · `apps/contracts/models.py:424-425` · `apps/web/src/phone.ts:125` · `apps/web/src/screens/settings.tsx:93-94`). 키보드는 막대를 끝까지 민 값과 같다(`main.js:127-131`). 찍은 점 가기는 `scenario.js` runner 가 `sim.cmd` 에 직접 쓴다(`main.js:660-662`). 학습 밖 값은 자르지 않고 테두리 색으로만 알린다(`main.js:709`, 10-31 앱 결정 그대로).

| 모드 | 정책 입력 칸 | 학습 범위 (근거) | 모드 상한 (이 안에서 정책에 넣는다) | 사람 입력 → 정책 입력 | 지금 앱에서 깎이는 곳 | 고칠 것 |
|---|---|---|---|---|---|---|
| **start · 정답** | `obs45[6:9]` = (vx, vy, wz) 몸 틀 m/s · rad/s. 이력 `hist` 10 스텝에도 들어가 명령을 바꾸면 10 스텝 동안 섞인다 | m6000 학습 표집(`ex40.yaml:116-123`): 전진 0.1~1.5 · 후진 −1.0~−0.2 · 옆 abs 0.2~0.6 · 제자리 회전 abs 0.3~1.5 · 걸으며 회전 abs wz 0.2~1.0 와 vx 0.3~0.8 · 대각 abs vx 0.3~0.6 와 abs vy 0.2~0.5 | 전진 **1.5** · 후진 **1.0** · 옆 **0.5** · 제자리 회전 **1.2** · 걸으며 회전 **1.0** (D108 상한과 학습 범위 중 작은 쪽, `start-demo-app/CONTRACT.md` §3.5) | 손 조종: 막대 × 모드 상한을 (vx, vy, wz) 로 그대로. 찍은 점 가기: runner 가 `[vx, 0, wz]` (vx = `sim_runner_vx`, wz = clamp(1.5 × 방향 오차, ±runner 상한), 방향 오차 0.4 rad 이상이면 vx 0 으로 제자리 회전, `scenario.js:72-93`) | ① 앞뒤가 한 축이라 후진도 전진 상한까지 나감(`manual-settings.js:14,20`) ② 조직 설정이 옆 0.3 · 회전 0.5 로 깎음 ③ `settings.js:16` 이 회전 상한을 0~1 범위로 검사해 1.2 를 기본 0.6 으로 갈아 끼움(runner 상한) ④ `scenario.js:50-51` runner 상한 vx 0.1~1.5 · wz 0.1~1 | ① 모드 상한을 방향별 다섯 칸(전진 · 후진 · 옆 · 제자리 회전 · 걸으며 회전)으로 두고 `manualAxis` 가 방향에 맞는 상한을 곱한다 ② 조직 설정 범위를 `sim_max_vy` 0~0.5 · `sim_max_wz` 0~1.2 로 넓히고 기본값도 0.5 · 1.2 로(`models.py:424-425,450-451` · `manual-settings.js:3` · `phone.ts:125` · `settings.tsx:93-94` · `apps/contracts/ts/index.ts:922-923,940` 함께) ③ `settings.js:16` 회전 상한 검사를 모드 상한 기준으로(1.2 가 0.6 으로 바뀌지 않게) ④ start 의 runner 명령은 학습 표집 그대로 두 경우로: 회전이 작을 때(|wz| < 0.2) vx 0.1~1.5, 걸으며 회전일 때(|wz| 0.2~1.0) vx 0.3~0.8 (`ex40.yaml:117-118` 학습 칸 · 이 조합 밖은 학습 안 한 명령). 목표 근처 감속은 앱 몫 |
| **start · 복원** | 같음 | 같음 (지도 모드는 명령 범위를 바꾸지 않는다) | 같음 | 같음 | 같음 | 같음 |
| **start · 끔** | 같음 (`_map_off` 파일도 obs45 칸 같음) | 같음 | 같음 | 같음 | 같음 | 같음 |
| **ame2** | `prop[45:49]` = [x, y, sin e, cos e]. (x, y) = 목표 위치 − 몸 위치를 몸 yaw 로만 돌린 것(x 앞 · y 왼쪽), e = 목표 방향 − 몸 방향. 2 m 넘으면 2 m 로 줄이고 e 를 U(−π, π) 로 매 스텝 다시 뽑음(`ame2-adapter.js:26-31`) | 학습 목표: 거리 2 m 안 · 재표집 16.01 s · 목표 방향(월드) ±π/3 · 몸 시작 yaw ±π · 목표 원뿔 45° (`ame2-demo-app/contract.json` command 칸) · 이동 보상 속도 상한 1.2 m/s(`--move2goal_vmax 1.2`) | 목표 거리 2 m 안. 속도는 정책이 정함(1 m 앞 목표를 매 스텝 다시 주면 평지 평균 1.08 m/s · Isaac 실측, PR #574) | 손 조종: 왼 막대 앞 · 옆을 길이 1 이하로 맞춘 몸 틀 목표(1 m 안쪽), 오른 막대는 방향을 rad/s 로 적분하고 오차를 ±π/3 로 자름(`ame2-adapter.js:55-62` · `main.js:663-665`). 찍은 점 가기: 월드 목표 · 경유점을 매 스텝 몸 틀로 다시 바꾸고 2 m 바로 아래로 자름, 방향은 지정 yaw 또는 경로 방향(`ame2-adapter.js:67-79` `ame2WorldGoal` · `scenario.js:86-92`) | 조직 속도 상한이 ame2 의 막대 비율에도 곱해져 옆 목표가 0.3 m, 방향 변화가 0.5 rad/s 로 깎임(`manual-settings.js:14`, ame2 `joystickScale [1,1,1]` `ame2-adapter.js:90`). 뒤쪽 · 옆쪽 목표는 학습 원뿔 밖이지만 자르지 않고 테두리 색만(`ame2-adapter.js:53,90`) | ame2 모드에는 조직 속도 상한을 곱하지 않는다(ame2 막대 값은 속도가 아니라 「1 m 목표의 비율 · 방향 변화 rad/s」). `manualSettings` 를 `command.kind === 'nearby_goal'` 일 때 조직 상한 없이 부른다 |
| **nvidia** | `obs[9:12]` = (vx, vy, wz) (`policy-adapters.js:53`) | vx 0.4~1.5 · vy 0 · wz ±1 (`policy-adapters.js:28` `trainingRanges`) | 학습 범위 그대로 | 막대 × `joystickScale [1.5, 0.5, 1]` (`policy-adapters.js:29`) | 옆 축 상한 0.5 로 학습에 없던 옆걸음 명령이 들어감 | 그대로 둔다(옆 0.5 · start 와 같은 설정). 학습하지 않은 동작은 잘 안 된다는 것을 보여 주는 것이 목적이다 |
| **go2** | 정책 없음 | 해당 없음 | 실기 Sport 명령 표 vx 0~1.5 · vy 0 · wz ±0.5 (`apps/agent/foothold_agent/phone/protocol.py:121-124` `LIMITS`) | 기존 서버 실기 경로 그대로 | 해당 없음 | 없음 |

## 2. 만들 것

### 2-1. 모드 등록부 하나

```js
// mobile/sim/policy-modes.js (새 파일)
export const POLICY_MODES = Object.freeze({
  nvidia: nvidiaDemoMode,   // 지금 foothold-v2 adapter (id 'nvidia-demo')
  start:  startDemoMode,    // 새로 (id 'start-demo', 저장본 m6000)
  ame2:   ame2DemoMode,     // 지금 ame2-demo adapter 를 옮김 (id 'ame2-demo', 저장본 m14999)
  go2:    go2ReplayMode,    // 새로 (id 'go2-oh2l2', 정책 없음 · SDK 상태를 그림)
});
// 고르기: URL ?policy= (값만 새 id 로) · 메뉴. 모르는 키면 오류(조용히 기본값으로 가지 않음)
```

모드 하나는 아래 칸을 **모두** 가진다. 빠진 칸이 있으면 등록 때 오류를 낸다.

| 칸 | 뜻 |
|---|---|
| `id` · `label` | §0 이름 |
| `onnx` | `{files: {...}, sha256: {...}, inputs: [{name, dims, type}], outputs: [{name, dims, type}], action: 'action', state: [{out: 'h_prop_next', in: 'h_prop'}, ...]}` (§1.4) |
| `observe(sim, cmd, mem)` | 그 모드의 관측 배열들(§1.3) |
| `map(sim)` | 그 모드 전용 지도 함수. 바닥을 묻는 저수준 함수(`makeTerrainSampler`)만 같이 쓴다 |
| `depth(sim)` | start 만. 다른 모드는 null |
| `command` | `kind`(`body_velocity` · `nearby_goal`) · 방향별 모드 상한(§1.5) · `inRange` |
| `act(a)` | a 자르기 → 목표각 |
| `torque(tau, dq, i)` | 그 모드 토크 곡선 |
| `timing` · `delay` · `stop` · `reset(mem)` | 리셋 때 이력 · 상태 · 깊이 버퍼 채우기 |
| `fallback` | JS f32 되돌림 파일(ame2 · nvidia) 또는 null(start) |

### 2-2. 명령

- 사람 명령은 막대 · 키 · 찍은 점 가기 셋이고, 정책에 넣기 직전에 모드가 바꾼다(§1.5 「사람 입력 → 정책 입력」 열).
- 정책에 들어가는 값 = 사람 입력을 모드 상한 안으로. 조직 설정은 모드 상한보다 낮게 줄일 수만 있고, 기본값은 모드 상한을 깎지 않는다(§1.5 「고칠 것」).
- 화면에 「이 모드 상한」 을 보여 준다(start 전진 1.5 · 후진 1.0 · 옆 0.5 · 회전 1.2, ame2 목표 2 m · 속도는 정책이 1.2 m/s 안에서 정함).
- 찍은 점 가기는 지금 구조(`astar.planRoute` → `scenario.js` runner 가 `sim.cmd` 에 씀)를 그대로 쓴다. start 는 `[vx, 0, wz]`, ame2 는 `ame2WorldGoal`.

### 2-3. ONNX 실행기 넓히기 (`policy-onnx.js`)

- 출력을 이름으로 여러 개 돌려준다(`action` 만이 아니라).
- `onnx.state` 짝대로 출력을 다음 호출 입력으로 되먹인다(start). 리셋 때 0.
- 입력은 계약 `type` 대로 만든다. start 의 `depth_tick` · `first_after_reset` · `use_gt` 는 **bool [1]** (ORT Web `new ort.Tensor('bool', [true], [1])`). 지금처럼 모두 float32 로 만들면 start 는 첫 호출에서 형식 오류가 난다.
- start 는 지도 모드에 맞는 파일을 연다(정답 · 복원 = `_map_on`, 끔 = `_map_off`). 지도 모드를 바꾸면 세션을 바꾸고 상태를 0 으로.
- 상태 · 이력 · 깊이 버퍼는 **행동이 실제로 적용될 때(`applyAction`)만 확정**한다(늦은 Worker 결과를 버리고 같은 스텝을 다시 부르기 때문, §3-2).

### 2-4. 시험 벡터로 같은 출력 확인 (답을 아는 입력으로 먼저)

시험 벡터 json 꼴(두 묶음 같음):

```json
{
  "format": "<id>-test-vectors/1", "model": "<id>", "checkpoint_sha256": "...",
  "onnx": {"<파일 이름>": "<sha256>"},
  "map_mode": "reconstruction | gt | off",
  "steps": 20, "tolerance": 0.0001, "state_feedback": true,
  "inputs":   [ {"<입력 이름>": [펼친 float32 ...], ...}, ... 20 개 ],
  "expected": [ {"action": [...], ...}, ... 20 개 ],
  "input_shapes": {"<입력 이름>": [..]}, "input_types": {"<입력 이름>": "tensor(float) | tensor(bool)"}
}
```

| 묶음 | 파일 | map_mode | state_feedback | expected 칸 |
|---|---|---|---|---|
| start | `start-demo-app/test_vectors_flat20_reconstruction.json` (`test_vectors_flat20.json` 과 같은 파일) | reconstruction | true | `action` · `h_prop_next` · `h_terr_next` · `recon_map` |
| start | `start-demo-app/test_vectors_flat20_gt.json` | gt | true | 같음 |
| start | `start-demo-app/test_vectors_flat20_off.json` | off (`_map_off` 파일) | true | 같음 |
| ame2 | `ame2-demo-app/test_vectors_flat20.json` | gt | false | `action` · `gaze_r` |

앱 시험(새 파일 `mobile/scripts/policy-vector-selftest.mjs`, Node ORT 와 브라우저 ORT 둘 다, 네 파일 모두):

```js
const tv = JSON.parse(await readFile(path));
let state = null;
for (let k = 0; k < tv.steps; k++) {
  const feed = { ...tv.inputs[k] };
  if (tv.state_feedback && k > 0) Object.assign(feed, state);   // 기록된 h 가 아니라 앱이 앞 스텝에서 받은 h
  const out = await infer(feed);                                 // 앱 실행기 그대로 (bool 입력은 input_types 대로)
  const err = maxAbs(out.action, tv.expected[k].action);
  if (err > tv.tolerance) throw new Error(`step ${k} action ${err}`);
  if (tv.state_feedback) state = { h_prop: out.h_prop_next, h_terr: out.h_terr_next };
}
```

- 시험 벡터의 `onnx` sha 와 앱이 연 ONNX 의 sha 가 다르면 시험하지 않는다.
- 첫 스텝 실패 = 입력 이름 · 순서 · 모양 · 자료형 문제, 둘째부터 실패 = 상태 되먹임 문제.
- lab 실측(onnxruntime CPU): start 최대 차 3.46e-6(PR #571), ame2 최대 차 1.6e-6(onnxruntime 1.31.0). 미확인: 앱 Node · 브라우저에서의 최대 차 · 정해질 때까지 이 시험을 통과해야 그 모드를 켠다.

### 2-5. 그 밖의 확인

1. 순서: 기본 자세로 세우면 `관절각 − 기본` 12 가 전부 |값| < 0.05. a 에 0 을 넣으면 목표각 = §1.2 벡터.
2. 정지: 명령 0 으로 30 초 서 있기(세 정책).
3. 토크: start 모드에서 calf 토크가 23.5 에서 잘리지 않는지(로그).
4. 지도: 서 있는 평지에서 start 지도 값은 모든 칸이 약 −0.3, ame2 z 채널은 0 근처(+0.27 상수).
5. 명령: 막대 · 키를 끝까지 밀었을 때 정책에 들어간 값이 start 전진 1.5 · 후진 −1.0 · 옆 ±0.5 · 제자리 회전 ±1.2 이고, 조직 설정을 기본값으로 둔 웹 시뮬(`?from=web`)에서도 같다. ame2 는 옆 끝까지 밀면 `prop[46]` 이 ±1 근처(0.3 아님). nvidia 는 옆 0.5(학습 밖이라 테두리 색).

### 2-6. JS f32 되돌림 규칙

| 모드 | 기본 계산 | 되돌림 | 규칙 |
|---|---|---|---|
| start | ONNX | 없음 | ONNX 실패 = 정책 잠금 + 사유를 화면에 표시 |
| ame2 | ONNX (`ame2-demo.onnx`) | 유지: `ame2_actor.f32`(sha `28edbc05…`, 같은 저장본 m14999 의 actor 를 다시 짠 JS 계산, 앱 `docs/AME2-PROVENANCE.md`) | 되돌림으로 돌면 화면에 늘 「AME-2 · JS f32 되돌림 중 · 사유」 를 보이게. 지금 `policy-onnx.js:53` 은 알림만 낸다 |
| nvidia | ONNX (`policy_v2.onnx`) | 유지: `policy_v2.f32` | 같음 |

- 엔진 기본값을 ONNX 로 바꾼다: 지금 `main.js:233` 기본이 `'f32'`(11-03 발표용으로 되돌린 것, spec 11:351).
- 미확인: ame2 f32 와 새 ONNX 의 출력 차이 · 정해질 때까지 f32 는 되돌림으로만 쓰고 화면에 표시한다. 앱 시험에서 ame2 시험 벡터를 f32 로도 돌려 최대 차를 적는다.

### 2-7. 하지 않는 것

- start 의 f32 JS 신경망은 만들지 않는다.
- ONNX 파일을 앱 저장소에 커밋하지 않는다(`FH_POLICY_ONNX_SRC` · `FH_AME2_SRC`, spec 11:321,387,422-423).
- 한 모드 값을 다른 모드 기본값으로 쓰지 않는다.

## 3. 앱 실제 구조와 파일별 할 일 (foothold-app dev `1fbe6f6c` · 줄 번호는 이 커밋)

20f3d066 뒤 세 커밋(#264)은 `ame2-adapter.js` · `main.js` · `scenario.js` · spec 11 만 바꿨다. 아래 줄 번호는 1fbe6f6c 에서 다시 잰 것이다.

### 3-1. 지금 정책이 고르고 도는 흐름

1. 고르기: `main.js:19-21` 이 `?policy=` (없으면 `'foothold-v2'`) · 메뉴 `index.html:88` option 둘 · 바꾸면 `main.js:164-167` 이 다시 연다.
2. AME-2 사용 가능 판정: `main.js:170-177` 이 `options[1]` 고정, f32 파일 존재로 판정(`:171-172`), 실패 시 `main.js:158` 이 끔.
3. 가중치는 늘 f32 를 받는다(`main.js:204-205` · `:228`). 엔진 기본 `'f32'`(`main.js:233`).
4. ONNX 경로: `policy-onnx.js:73-78` 파일 하나 · sha 확인 → Worker(`:79-88`, 기한 20 ms) → 늦으면 화면 쪽 ONNX → 실패 시 f32(`:90-111`, 알림 `:53`).
5. 물리 한 번: `sim.js:98-113` `adapter.observe` 뒤 `policy(obs, s.mapping)` · 행동 `sim.js:114-123` · 토크 `sim.js:124-131`.
6. 명령: §1.5 첫 문단.
7. 자산: `sync-web.mjs:15-17`(`FH_SIM_SRC` 필수) · ame2 는 `FH_AME2_SRC`(id 고정 `:33,35,46`) · 나머지 `FH_POLICY_ONNX_SRC` · ORT `:55-63`. 서버 배포는 `deploy/prepare_sim.py:11-27 · 115-160` 의 sha 허용 목록.

### 3-2. 모드 공통으로 고칠 곳

| 자리 | 지금 | 고칠 것 |
|---|---|---|
| `sim.js:105,111` | `policy(obs, mapping)` 인자 둘 고정 | `mode.inputs(s)` 가 계약 순서의 배열 묶음을 돌려주게 |
| 상태 · 이력 · 깊이 버퍼 확정 | Worker 늦은 결과는 버림(`policy-worker-client.js:42-43`) → `frame-clock.js:15` 가 같은 스텝을 다시 부름 | `applyAction` 때만 확정. `observe` 에서 이력을 밀면 두 번 밀린다 |
| 리셋 | `sim.js:71-82` 에 모드 리셋 고리 없음 · `main.js:45` 는 ame2 만 상태 지움 · `spawnOn`(`main.js:384-387`)은 리셋 뒤 자세를 다시 옮김 | 모드 `reset(mem)` · 이력은 리셋 뒤 첫 관측으로 · GRU 0 · `first_after_reset` true |
| ame2 판별 | `main.js:45,118,120,129,158,178,233,662-663,675` · `scenario.js:35` · `sync-web.mjs:35,46` · `policy-onnx.js:52` · `ame2-onnx.js:4-7` 가 `stop.pause` 나 `'ame2-demo'` 로 가림 | `mode.command.kind`(`body_velocity` · `nearby_goal`) 로 |
| 이름 foothold-v2 → nvidia-demo | `policy-adapters.js:173` · `sim.js:14,23` · `main.js:20` · 시험 `ame2-worker-selftest.mjs:112,137,165,198,215,287` · `settings-sim-selftest.mjs:8-10` · `sim-goal-selftest.mjs:283-284` | 모두 함께. URL `?policy=` 는 두고 값만 바꾼다 |
| `policy-onnx.js:23,25` | 입력 전부 float32 · `every(Number.isFinite)` | 입력마다 계약 `type`(bool 은 `Uint8Array` · `new ort.Tensor('bool', …)`) |
| `policy-onnx.js:34-35` | `action` 하나만 · `offsets` 특례 | 출력 이름별 묶음을 돌려줌 · `offsets` 특례를 지움(ame2 진단은 `gaze_r`) |
| `policy-onnx.js:64` · `policy-worker.js:12` | 예열 입력이 float32 0 | 자료형별 예열 |
| `policy-worker.js:15-16` · `policy-worker-client.js:45,67` | `{action}` 만 보냄 | `{outputs}` + 버퍼 전송 목록 |
| `policy-onnx.js:53` | 되돌림 알림만 | 되돌림 중 화면 표시를 늘 켜 둠(§2-6) |
| `main.js:233` | 엔진 기본 `'f32'` | 모드 기본 ONNX(`'wasm'`) |
| 명령 상한 | §1.5 「지금 앱에서 깎이는 곳」 열 | §1.5 「고칠 것」 열 |

### 3-3. start 모드

| 할 일 | 자리 · 이유 |
|---|---|
| adapter 새로 · `action.torque(tau, dq, i)` 에 관절별 DCMotor | `sim.js:17-21` `dcmotor` 는 12 관절 공통 한계 하나. torque 를 두면 MuJoCo 제한이 꺼진다(`sim.js:42-50`, `:46` 오류 문구 「AME-2」 도 고침) |
| a ±17 자르기 | 지금은 목표각 자르기(`sim.js:115-117`)만 |
| f32 없이 도는 길 | `main.js:204-205,228` 과 `policy-onnx.js:54,94,111` 이 f32 를 전제 → 「ONNX 실패 = 잠금 + 사유 표시」 |
| ONNX 파일 둘 · 지도 모드 고르는 UI · 바꿀 때 세션 교체 + 상태 0 | `onnx.file` 하나만 받음(`policy-onnx.js:73` · `sync-web.mjs:47`) |
| 자산 복사 | `sync-web.mjs:45` 는 f32 가 없으면 ONNX 를 건너뜀 → f32 없는 모드 허용 · `deploy/prepare_sim.py:17-21` `ONNX_SHA` 에 두 파일 sha(§1.1) · `deploy/tests/test_prepare_sim.py` 함께 |
| 높이 지도 32 × 16 | `makeTerrainSampler(mj, m, d, {grid, rayOffset})`(`policy-adapters.js:74-165`) 재사용 · 배열 순서 yx. 광선 시작은 ame2 와 같은 「몸에서 위로 쏘는 탐침」 방식(`ame2-adapter.js:104-135`). 몸 위 20 m 고정이면 앱 장면 천장을 맞힌다 |
| 깊이 60 × 60 | 앱에 오프스크린 깊이 그리기 없음(three 렌더러 하나 `main.js:275-291`). `mj_multiRay`(원점 하나 공유, `lidar.js:15`)로 3600 광선 핀홀 카메라(§1.3 카메라 자리 · 각도 · fx fy cx cy) · geom group 지형 필터 `[1,1,0,0,1,0]` + 로봇 제외(`policy-adapters.js:75-84`) · 10 Hz · 몸 전체 자세 기준 · 1 프레임 늦은 두 장 |
| 시험 | `policy-vector-selftest.mjs`(§2-4 start 세 파일) · 깊이 · 지도 단언(평지 값, 천장 무시) · Worker 출력 여러 개 · bool 입력 · `prepare_sim` 시험. `start-selftest.mjs` · `mobile/start/` 는 「시작 화면」 이라 새 파일 이름은 `start-demo-*` |
| 용량 · 시간 | 파일 둘 각 5.8 MB · Worker 초기화 때 사본 하나 더(`policy-worker-client.js:61`, 초기화 기한 15 초). 미확인: 브라우저 추론이 20 ms 안인지 · 정해질 때까지 지금 Worker 구조(늦으면 화면 쪽 계산) 그대로 |

### 3-4. ame2 모드

| 할 일 | 자리 |
|---|---|
| ONNX 계약 바꾸기 (꼭) | `policy-adapters.js:168-171` 계약이 출력 `offsets`(int64) · `gaze_logits` 를 요구하고 `policy-onnx.js:10-12` 가 없으면 「ONNX 입출력 이름 불일치」 로 거절한다. outputs 를 `[{name:'action',dims:[1,12]},{name:'gaze_r',dims:[1,2]}]` 로(`ame2-demo-app/app_onnx.json` 그대로) · 진단 표시는 `gaze_r` 에서 ox = clamp(round(r0 × 17), 0, 17) · oy = clamp(round(r1 × 3), 0, 3) |
| 파일 · sha 바꾸기 (꼭) | `policy-adapters.js:168` `ame2_actor.onnx`(sha `398acb0c…`) → `ame2-demo.onnx`(sha `830595df…`). `ame2-onnx.js:4` 가 이 sha 를 읽고 `policy-onnx.js:78` 이 받은 파일 sha 를 대조 · `sync-web.mjs:33,35,46` 파일 이름 · `deploy/prepare_sim.py:12-21` `AME2_SHA` · `ONNX_SHA`. 파일은 `ame2-demo-app/` 에서 복사 |
| 시험 벡터 | §2-4 ame2 파일 · action 최대 차 1e-4 이하 |
| f32 되돌림 | 유지(§2-6). 사용 판정 `main.js:170-177` 을 ONNX 파일 존재로 바꾸고, f32 는 되돌림 준비 여부로만 |
| 행동 지연 0 | 앱은 리셋마다 0~4 를 무작위로 뽑는다(`ame2-adapter.js:41`, `main.js:242` 가 `ame2DelaySteps` 를 안 넘김) → `ame2DelaySteps: 0` |
| 조직 속도 상한 빼기 | §1.5 ame2 줄 |

### 3-5. nvidia 모드

id · 메뉴 이름을 `nvidia-demo` 로 바꾼다. 명령 설정(`joystickScale [1.5, 0.5, 1]`)은 그대로 둔다(§1.5). f32 와 원본 대조는 spec 11:98 「130 입력 최대 차 0」 으로 이미 통과했으니 spec 11:209 P2 「진행 중」 상태를 닫는다.

### 3-6. go2 모드

- 상태 원본이 없다: agent 가 `rt/lowstate` · `rt/sportmodestate` 를 구독은 하지만(`go2_readonly/sdk.py:28-29`) 내보내는 것은 배터리 · roll/pitch · mode · error 뿐(`go2_readonly/state.py:68-71,110-118`). 관절각 12 · 쿼터니언 · 위치는 안 나간다.
- 전달 경로가 없다: 앱 안 시뮬은 서버와 끊긴 묶음(`main.js:1`) · CSP `connect-src 'self'`(`index.html:7`) · 서버에 묻는 것은 `?from=web` 때뿐(`settings.js:25`).
- 할 일: agent 가 q · 쿼터니언 · 위치를 내보냄 → 서버 API → 앱이 받아 `qpos` 넣고 `mj_forward`(`spawnOn` `main.js:384-387` · `draw` `:368-374` 재사용) · SDK 모터 순서 FR FL RR RL → 이름으로 재배열.
- 명령은 기존 서버 실기 표(§1.5 go2 줄)로 Sport 모드에 보낸다.

## 4. 끝 확인 목록

- [ ] §1.1 파일을 받아 두 폴더 `sha256sum -c SHA256SUMS` 전부 OK
- [ ] 모드 넷 등록 · 빠진 칸 오류 · 모르는 키 오류
- [ ] start 시험 벡터 세 파일(reconstruction · gt · off) 20 스텝 상태 되먹임 통과 (Node · 브라우저)
- [ ] ame2 시험 벡터 20 스텝 통과 (Node · 브라우저) · f32 로도 돌려 최대 차 기록
- [ ] ame2 계약 출력 `action` · `gaze_r`, 파일 · sha `ame2-demo.onnx` · `830595df…`
- [ ] 엔진 기본 ONNX · 되돌림이 켜지면 화면에 늘 표시 · start 는 ONNX 실패 때 잠금 + 사유
- [ ] §1.5 명령 표대로: start 끝 값 전진 1.5 · 후진 −1.0 · 옆 ±0.5 · 회전 ±1.2 가 `?from=web` 에서도 그대로, ame2 옆 목표가 0.3 으로 깎이지 않음, nvidia 옆 0.5 그대로
- [ ] §2-5 순서 · 정지 30 초 · start calf 토크 · 지도 평지 값
- [ ] ame2 `ame2DelaySteps: 0`
- [ ] `deploy/prepare_sim.py` 허용 목록 · `sync-web.mjs` 자산 복사 · 시험 함께

## 5. 미확인

- 미확인: 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음).
- 미확인: 앱 MuJoCo 에서 ame2 의 1 m 목표 실제 속도 · 정해질 때까지 화면 상한 표시는 1.2 m/s (Isaac 실측 평지 평균 1.08 m/s).
- 미확인: 브라우저 ONNX 추론 시간(20 ms 기한 안인지) · 정해질 때까지 지금 Worker 구조 그대로.
- 미확인: ame2 f32 되돌림과 새 ONNX 의 출력 차이 · 정해질 때까지 f32 는 되돌림으로만, 화면 표시.
