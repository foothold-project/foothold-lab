> 분류: B/앱 · 앱 개발 준수 사항 (정책 모드 셋)
> 작성: 오흥재 (lead 세션) · 2026-11-03 16:3x v0.1
> 근거: m6000 조건표 정본 `inbox/jay/20261101-app/APP-POLICY-CONTRACT-m6000.md` v0.3.1 (lead 가지 dc81513c) · AME-2 학습 설정 `ame2_spd/.../params/env.yaml` · `agent.yaml` · foothold-app dev `6740de88` (`mobile/sim/policy-adapters.js` · `ame2-adapter.js` · `policy-onnx.js` · `docs/spec/11-POLICY-ADAPTER.md`)
> 요지: 앱에 「모드」 넷(nvidia · start · ame2 · go2)을 두고, 모드를 고르면 그 정책의 값 전부(관측 · 명령 · 지도 · 토크 · 자르기 · 상태 · ONNX)가 함께 바뀌게 한다. 사람이 주는 명령과 화면 상한은 하나로 통일하고, 정책에 넣기 직전에 모드가 바꾼다. 아래 §1 이 답(값)이고 §2 가 만들 것이다
> 상태: v0.1 · start 모드 값은 m6000 묶음 기준(아직 앱에 넘기지 않음) · ame2 모드는 앱에 이미 있는 값을 정본 값과 맞춰 적음 · 명령 가속 제한 값은 미정

# 앱 개발 준수 사항 · 정책 모드 넷

이 문서 하나만 보고 앱 코드를 짤 수 있게 썼다. 이름 규칙과 저장소 배치는 같은 폴더 `README.md`.

## 0. 지금 앱 상태와 바뀌는 점

| | 지금(dev 6740de88) | 이 문서 뒤 |
|---|---|---|
| 정책 | `foothold-v2`(기본) · `ame2-demo`, 선택은 `?policy=` | 모드 키 넷 `nvidia` · `start` · `ame2` · `go2`. 이름은 `nvidia-demo` · `start-demo` · `ame2-demo` · `go2-oh2l2`(앱 `foothold-v2` 는 `nvidia-demo` 로 이름만 바꿈). 최종은 `nvidia-foothold-v2` · `start-oh2l2` · `ame2-oh2l2` · `go2-oh2l2` |
| 추론 | ONNX(ORT Web WASM · Worker), 실패하면 f32 JS 로 되돌림 | 그대로. **start 는 f32 JS 판을 만들지 않는다**(아래 §2-6) |
| ONNX 실행기 | 출력 하나(`contract.action`)만 돌려줌 · 입력 모두 float32 | 출력 여러 개 + **상태 되먹임**(start 에 필요) |
| 모델별 명령 범위 | `policy_ranges.py` 에 foothold-v2 한 줄 · 전진 전용 형식 | 모드마다 한 줄 · 후진 · 옆 · 제자리 회전 칸 |
| 토크 | adapter 에 `action.torque` 가 없으면 12 관절 모두 23.5 · 30 | **모드마다 반드시** 토크 곡선 |

## 1. 답 · 모드별 값 (그대로 옮겨 적는다)

### 1.1 세 모드 공통

| 값 | 숫자 |
|---|---|
| 제어 | 50 Hz = 물리 dt 0.005 s × decimation 4 |
| 관절 순서(정책 입출력) | `FL_hip FR_hip RL_hip RR_hip FL_thigh FR_thigh RL_thigh RR_thigh FL_calf FR_calf RL_calf RR_calf` (세 모드 같음, 앱 MuJoCo 내부 `MJ_J` 순서와는 이름으로 재배열) |
| 기본 관절각(위 순서) | `[0.1, -0.1, 0.1, -0.1, 0.8, 0.8, 1.0, 1.0, -1.5, -1.5, -1.5, -1.5]` |
| PD | Kp 25 · Kd 0.5 (12 관절) |
| 목표각 | 기본 관절각 + 0.25 × a (a 를 먼저 모드별 범위로 자름) · 목표 속도 0 · 앞먹임 토크 0 |
| 관측 정규화 | 없음 |

### 1.2 모드별

| 칸 | `start` (start-demo) | `ame2` (ame2-demo) |
|---|---|---|
| 정책이 받는 명령 | 몸 속도 (vx, vy, wz) | 목표 위치 [x, y, sin, cos] (몸 틀, 2 m 넘으면 2 m 로 자르고 yaw 다시 뽑음) |
| 사람 명령 → 정책 명령 | 그대로(모드 범위로 자름) | 속도를 매 tick 1 m 안쪽 목표로 바꿈(앱 `ame2-adapter.js:54~62` 그대로) |
| 모드 속도 상한 | 전진 1.5 · 후진 1.0 · 옆 0.5 · 제자리 회전 1.2 · 걸으며 회전 1.0 (m/s · rad/s) | 학습 속도 상한 **1.2 m/s** (`--move2goal_vmax 1.2`, 팀장 확인) · 후진 · 옆은 목표 방향으로 |
| 관측 | 45 = 각속도 3 · 중력 3 · 명령 3 · 관절각−기본 12 · 관절 속도 12 · 직전 a 12 (배율 1 · 자르기 없음) | 49 = 몸 속도 3 · 각속도 3 · 중력 3 · 관절각−기본 12 · 관절 속도 12 · 직전 raw a 12(±50 자름) · 목표 4 |
| 이력 · 상태 | 이력 10 × 45(가장 오래된 것 앞, 시작 때 첫 관측으로 채움) · GRU 상태 `h_prop` · `h_terr` 각 128(처음 0, 출력을 다음 입력에) | 없음 |
| 지도 | **32 × 16 · 5 cm · 높이 1 채널**: 몸 앞 +0.3 m 중심, x −0.475~+1.075 · y −0.375~+0.375, yaw 만 정렬, 값 = 바닥 높이 − 몸 높이(±1 m 자름), 못 맞힌 칸 −1, 배열 순서 yx · 광선은 몸 위 20 m 에서 아래로 | **29 × 13 × 3 (x, y, z) · 6 cm**: x −0.42~1.26 · y ±0.36, yaw 정렬, x 가 바깥 축, z = 바닥 높이 − 센서 높이 + 0.27(±1.5 자름) · 광선 +20 m (앱 `ame2-adapter.js` 에 이미 있음) |
| 지도 모드 | 정답 · 복원 · 끔 셋: 시뮬은 정답도, 실기는 복원 · 끔 | 정답만 |
| 깊이 | 60 × 60 · 10 Hz(5 스텝마다) · 정책에는 1 프레임 늦은 최근 2 장 · (d − 0.2)/2.8 을 [0,1] 로 · 미검출 1.0 · 카메라 몸 기준 (0.25, 0, 0.12) m · 아래로 35° · fx 55.9 fy 54.1 cx cy 30 | 없음 |
| 토크 곡선 | DCMotor: hip · thigh 한계 23.5 · 포화 23.5 · 속도 30.0 / calf 45.43 · 45.43 · 15.70. 상한 = min(한계, 포화 × (1 − q̇/v)), 하한 = max(−한계, 포화 × (−1 − q̇/v)) | Go2HV 곡선(앱 `ame2-adapter.js:15~21` 그대로) |
| a 자르기 | ±17 | ±100(목표각 쪽 `targetClip`) |
| 지연 | 배포 0 | 배포 0 |
| ONNX | 파일 둘 `start-demo_map_on.onnx`(sha 81c7e079…) · `_map_off.onnx`(sha 5d1b7bf3…). 입력 9 `obs45[1,45] · hist[1,10,45] · depth2[1,2,60,60] · h_prop[1,128] · h_terr[1,128] · depth_tick[1] · first_after_reset[1] · use_gt[1] · gt_map[1,512]` · 출력 4 `action[1,12] · h_prop_next · h_terr_next · recon_map[1,32,16]`. 지도 끔 = `_map_off` 파일, 복원 = `_map_on` + use_gt 0, 정답 = `_map_on` + use_gt 1 + gt_map | 파일 하나 `ame2-demo.onnx`(석헌 님 새 묶음, 지금 앱의 `ame2_actor.onnx` 398acb0c… 는 재구성 actor 라 바꿔 끼움). 입력 `prop[1,49] · mapping[1,29,13,3]` · 출력 `action[1,12]`(+ 진단 offsets · gaze_logits) |
| 묶음 자리 (ONNX 포함) | `inbox/jay/20261103-policy-handoff/start-demo/` (팀장 검증 뒤) | `inbox/lim/20261103-policy-handoff/ame2-demo/` (석헌 님 PR → 팀장 검증 뒤) |

### 1.3 `nvidia` 모드 (nvidia-demo)

앱에 있는 `foothold-v2` 값 그대로(관측 235 · 높이 187 칸 · 명령 범위 vx 0.4~1.5 · vy 0 · wz ±1 · `policy_v2.onnx` sha c9f3c5c0…). 바꾸지 않는다. 할 일은 하나: 앱의 f32 JS MLP 계산이 원본 actor(npz `a162d3bf…`)와 같은 출력인지 확인(spec 11 P2 「진행 중」 을 닫기).

### 1.4 `go2` 모드 (go2-oh2l2)

정책을 돌리지 않는다. 실기 Go2 는 순정 Sport 모드로 움직이고, 앱은 SDK 로 받은 상태(관절각 12 · 몸 자세 쿼터니언 · 몸 위치 또는 속도)를 시뮬 화면의 로봇에 그대로 그린다. 주의: SDK 모터 순서는 FR FL RR RL 다리 단위라 화면 관절 이름으로 재배열한다(START 조건표 §0b 표). ONNX · 지도 · 토크 칸은 없음(null)으로 등록하고, 명령은 Sport 모드 쪽(앱 기존 서버 실기 표)으로 보낸다.

## 2. 만들 것

### 2-1. 모드 등록부 하나

```js
// mobile/sim/policy-modes.js (새 파일, 이름 제안)
export const POLICY_MODES = Object.freeze({
  nvidia: nvidiaDemoMode,   // 지금 foothold-v2 adapter (id 'nvidia-demo')
  start:  startDemoMode,    // 새로 (id 'start-demo', 저장본 m6000)
  ame2:   ame2DemoMode,     // 지금 ame2-demo adapter 를 옮김 (id 'ame2-demo', 저장본 m14999)
  go2:    go2ReplayMode,    // 새로 (id 'go2-oh2l2', 정책 없음 · SDK 상태를 그림)
});
// 고르기: 코드 const MODE = 'start'; 또는 URL ?mode=start · 메뉴. 모르는 키면 오류(조용히 기본값으로 가지 않음)
// 최종 모델이 오면 id 만 nvidia-foothold-v2 · start-oh2l2 · ame2-oh2l2 로 바꾸고 키는 그대로
```

모드 하나는 아래 칸을 **모두** 가진다. 빠진 칸이 있으면 등록 때 오류를 낸다(공통 기본값으로 채우지 않는다).

| 칸 | 뜻 |
|---|---|
| `id` · `label` | 이름 규칙(README) 그대로 |
| `onnx` | `{files: {...}, sha256: {...}, inputs: [{name, dims}], outputs: [{name, dims, type}], action: 'action', state: [{out: 'h_prop_next', in: 'h_prop'}, ...]}` |
| `observe(sim, cmd, mem)` | 그 모드의 관측 배열들을 만든다(§1.2) |
| `map(sim)` | **그 모드 전용 지도 함수.** start 는 32 × 16 × 1, ame2 는 29 × 13 × 3. 두 모드가 같은 함수를 쓰지 않는다. 바닥을 묻는 저수준 함수(`makeTerrainSampler`)만 같이 쓴다 |
| `depth(sim)` | start 만. 없으면 null |
| `command(human)` | 사람 명령(vx, vy, wz) → 정책 명령. start 는 범위로 자름, ame2 는 1 m 목표로 바꿈 |
| `ranges` | 모드 속도 상한(§1.2) |
| `act(a)` | a 자르기 → 목표각 |
| `torque(tau, dq, i)` | 그 모드 토크 곡선 |
| `timing` · `delay` · `stop` · `reset(mem)` | 시작 · 리셋 때 이력 · 상태 · 깊이 버퍼 채우기 |

### 2-2. 명령 통일

- 사람 명령은 한 가지: 몸 속도 (vx, vy, wz). 조이스틱 · 키 · 버튼 모두 이것을 만든다.
- 화면 상한은 앱 설정 하나(지금 시뮬 전진 1.5 m/s). 실제로 보내는 값 = **min(화면 상한, 모드 상한)**. 화면에 「이 모드 상한」 을 함께 보여 준다(ame2 는 1.2).
- 가속 제한은 앱 공통 한 곳에 둔다. 값은 팀장 결정 대기(D108).
- **앞으로 목표 걷기도 쓴다.** START 기저 정책 실험(깃발)은 목표를 두고 걷게 하려는 것이다. 앱에서 「목표 지점」 을 찍으면 ame2 는 목표를 그대로, start 는 위 계층(경로 · 판단층)이 목표를 속도 명령으로 바꿔 넣는다(팀 결정: 속도 명령 + 위 계층). 그래서 `command()` 는 사람 속도와 목표 지점 두 입력을 받을 수 있게 열어 둔다.

### 2-3. ONNX 실행기 넓히기 (`policy-onnx.js`)

- 출력을 이름으로 여러 개 돌려준다(`action` 만이 아니라).
- `onnx.state` 에 적힌 짝대로 출력을 다음 호출의 입력으로 되먹인다(start 의 GRU 둘). 리셋 때 0.
- 플래그 입력(depth_tick · first_after_reset · use_gt)도 float32 [1] 로 만든다.
- start 는 지도 모드에 따라 파일 둘 중 하나를 연다(on/off). 모드 안에서 지도 모드를 바꾸면 세션을 바꾸고 상태를 0 으로.

### 2-4. 모델별 범위 표 (`apps/agent/foothold_agent/policy_ranges.py`)

지금 `VelocityRange` 는 전진 전용이다. 후진 하한 · 옆 · 제자리 회전 · 걸으며 회전 칸을 넣고 start · ame2 줄을 더한다. UI · 서버 · 에이전트가 이 표 하나로 자른다(D108).

### 2-5. 확인 (답을 아는 입력으로 먼저)

1. 순서: 기본 자세로 세우면 `관절각 − 기본` 12 가 전부 |값| < 0.05. a 에 0 을 넣으면 목표각 = §1.1 벡터.
2. 같은 출력: 묶음의 `test_vectors_flat20.npz` 를 앱 실행기에 넣어 `action` 최대 차이 1e-4 이하(start 는 상태 되먹임까지 20 스텝 이어서).
3. 정지: 명령 0 으로 30 초 서 있기.
4. 토크: start 모드에서 calf 토크가 23.5 에서 잘리지 않는지(로그로).
5. 지도: 서 있는 평지에서 start 지도 값은 모든 칸이 약 −0.3(= 바닥 − 몸 높이), ame2 z 채널은 0 근처(+0.27 상수 때문). 두 값이 이렇게 다르게 나오면 지도 함수가 모드별로 맞게 나뉜 것이다.

### 2-6. 하지 않는 것

- **start 의 f32 JS 신경망은 만들지 않는다.** 팀 방향은 「같은 ONNX 하나를 웹과 실기가 함께 쓴다」 이다. spec 11 의 「f32 JS 되돌림 경로」 요건은 foothold-v2 · ame2 에만 두고, start 는 parity(원본 대 ONNX 1e-4)로 대신한다(spec 11 고치기).
- 한 모드의 값을 다른 모드 기본값으로 쓰지 않는다(토크 23.5 가 그 예).
- ONNX 파일을 앱 저장소에 커밋하지 않는다(`FH_POLICY_ONNX_SRC`, spec 11:410~416). lab 의 묶음 폴더에서 복사하고, sha256 이 묶음의 contract.json · SHA256SUMS 와 같을 때만 쓴다.

## 3. 남은 것 · 정할 것

- 가속 제한 값(팀장, D108).
- ame2 1 m 목표에서 실제 속도: 앱 시뮬에서 재서 모드 상한 표에 적기(현민).
- ONNX 추론 속도: 나중에 따로 논의(팀장 16:3x). 그때까지는 지금 Worker 구조 그대로.
- start 묶음 전달 시점: 팀장 결정(D144).
