> 분류: B/앱 · 앱 개발 준수 사항 (정책 모드 셋)
> 작성: 오흥재 (lead 세션) · 2026-11-03 16:3x v0.1 · 19:1x v0.2 (앱 dev 20f3d066 파일 단위 전수 대조 반영 · §3 새 절)
> 근거: m6000 조건표 정본 `inbox/jay/20261101-app/APP-POLICY-CONTRACT-m6000.md` v0.3.1 (lead 가지 dc81513c) · AME-2 학습 설정 `ame2_spd/.../params/env.yaml` · `agent.yaml` · foothold-app dev `20f3d066`(2026-11-03 09:19Z, mobile/sim 은 6740de88 과 같음) (`mobile/sim/policy-adapters.js` · `ame2-adapter.js` · `policy-onnx.js` · `docs/spec/11-POLICY-ADAPTER.md`)
> 요지: 앱에 「모드」 넷(nvidia · start · ame2 · go2)을 두고, 모드를 고르면 그 정책의 값 전부(관측 · 명령 · 지도 · 토크 · 자르기 · 상태 · ONNX)가 함께 바뀌게 한다. 사람이 주는 명령과 화면 상한은 하나로 통일하고, 정책에 넣기 직전에 모드가 바꾼다. 아래 §1 이 답(값)이고 §2 가 만들 것이다
> 상태: v0.2.1 · start-demo 묶음 전달됨(lab PR #571 · `inbox/jay/20261103-policy-handoff/start-demo/`) · ame2-demo 묶음은 석헌 님 PR 대기(lab #569) · 앱 작업 이슈 foothold-app#259

# 앱 개발 준수 사항 · 정책 모드 넷

이 문서 하나만 보고 앱 코드를 짤 수 있게 썼다. 이름 · 진행 순서 · 묶음 폴더 · 정해진 것은 바로 아래 「공통 규칙」.

## 공통 규칙 (이 문서만 보고 일할 수 있게 같은 내용을 세 문서에 모두 둔다 · 2026-11-03 19:3x 판)

**이름(D170).** 모드 코드 키 `nvidia` · `start` · `ame2` · `go2`. 지금 이름 `nvidia-demo`(앱의 옛 `foothold-v2`) · `start-demo`(저장본 m6000) · `ame2-demo`(저장본 m14999) · `go2-oh2l2`(정책 없음, 실기 Sport 모드 상태를 그리기만). 최종 이름 `nvidia-foothold-v2` · `start-oh2l2` · `ame2-oh2l2` · `go2-oh2l2`. ONNX 파일 = 이름 + `.onnx`(start 는 `_map_on` · `_map_off` 둘). 묶음 format = 이름 + `-onnx/1`, 입출력이 바뀌면 `/1` 을 올린다.

**진행 순서.** ① lead 가 start-demo 묶음 · 석헌 님이 ame2-demo 묶음을 PR ② 팀장이 PR 검증 · 머지 ③ 현민 님이 앱에 적용. 현민 님은 ①을 기다리지 않고 앱 구조부터 만든다(값은 앱 문서에 있다).

**묶음 폴더(ONNX 도 lab 에 올린다).** `inbox/<올린 사람>/20261103-policy-handoff/<이름>/` 에 `<이름>.onnx` · `CONTRACT.md` · `contract.json`(입출력 이름 · dims · type · 실측 순서 · 각 ONNX sha256, 앱 adapter `onnx` 꼴은 `app_onnx` 칸) · `parity.json` · `test_vectors_flat20.json` 과 `.npz` · `SHA256SUMS` · `.gitattributes`(`* -text`, 바이트 그대로). 한 파일 100 MB 아래. 앱 저장소에는 ONNX 를 커밋하지 않고 이 폴더에서 복사해 sha256 을 맞춰 쓴다.

**정해진 것(다시 묻지 않는다).** ONNX 하나를 웹 시뮬과 실기가 함께 쓴다 · **앱 ONNX 실행기는 상태 출력(GRU)을 다음 호출 입력으로 되먹이고 입력 자료형(bool 포함)을 계약대로 만든다**(현민 님 몫, 앱 문서 §2-3 · §3-2) · start 는 f32 JS 신경망을 만들지 않는다 · 모드별 값은 통째로 갈아 끼우고 공통 기본값을 쓰지 않는다 · 지도 함수는 모드마다 따로 · ONNX 는 lab 공개 저장소에 올린다.

**아직 정하지 않은 것.** 명령 가속 제한 값(D108) 하나.

**올리는 법.** main 에서 브랜치 → 자기 `inbox/<이름>/` 아래만 커밋 → PR → 팀장 머지. `docs/` 는 건드리지 않는다. 문장에 em dash(가로로 긴 줄표)를 쓰지 않는다.

## 0. 지금 앱 상태와 바뀌는 점

| | 지금(dev 6740de88) | 이 문서 뒤 |
|---|---|---|
| 정책 | `foothold-v2`(기본) · `ame2-demo`, 선택은 `?policy=` | 모드 키 넷 `nvidia` · `start` · `ame2` · `go2`. 이름은 `nvidia-demo` · `start-demo` · `ame2-demo` · `go2-oh2l2`(앱 `foothold-v2` 는 `nvidia-demo` 로 이름만 바꿈). 최종은 `nvidia-foothold-v2` · `start-oh2l2` · `ame2-oh2l2` · `go2-oh2l2` |
| 추론 | **기본은 f32 JS**(`main.js:233`), ONNX 는 `?policyBackend=wasm` 일 때만 · Worker 기한 20 ms · 5 번 늦으면 화면 쪽 ONNX · 그것도 실패하면 f32 | start 는 f32 가 없으므로 **모드 기본을 ONNX 로**, ONNX 실패 = 잠금 + 사유 표시(§3-3) |
| ONNX 실행기 | 출력 하나(`contract.action`)만 돌려줌 · 입력 모두 float32 · `sim.js:105,111` 이 `policy(obs, mapping)` 인자 둘 고정 | 출력 여러 개 + **상태 되먹임** + bool 입력 · 입력 배열을 계약 순서로(§3-2) |
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
| 지연 | 배포 0 | 배포 0 (지금 앱은 0~4 무작위, §3-4 에서 0 으로) |
| ONNX | 파일 둘 `start-demo_map_on.onnx`(sha 81c7e079…) · `_map_off.onnx`(sha 5d1b7bf3…). 입력 9 `obs45[1,45] · hist[1,10,45] · depth2[1,2,60,60] · h_prop[1,128] · h_terr[1,128] · depth_tick[1] · first_after_reset[1] · use_gt[1] · gt_map[1,512]` · 출력 4 `action[1,12] · h_prop_next · h_terr_next · recon_map[1,32,16]`. 지도 끔 = `_map_off` 파일, 복원 = `_map_on` + use_gt 0, 정답 = `_map_on` + use_gt 1 + gt_map | 파일 하나 `ame2-demo.onnx`(석헌 님 새 묶음, 지금 앱의 `ame2_actor.onnx` 398acb0c… 는 재구성 actor 라 바꿔 끼움). 입력 `prop[1,49] · mapping[1,29,13,3]` · 출력 `action[1,12]`(+ 진단 offsets · gaze_logits) |
| 묶음 자리 (ONNX 포함) | `inbox/jay/20261103-policy-handoff/start-demo/` (팀장 검증 뒤) | `inbox/lim/20261103-policy-handoff/ame2-demo/` (석헌 님 PR → 팀장 검증 뒤) |

### 1.3 `nvidia` 모드 (nvidia-demo)

앱에 있는 `foothold-v2` 값 그대로(관측 235 · 높이 187 칸 · 명령 범위 vx 0.4~1.5 · vy 0 · wz ±1 · `policy_v2.onnx` sha c9f3c5c0…). 바꾸지 않는다. 할 일은 하나: 앱의 f32 JS MLP 계산이 원본 actor(npz `a162d3bf…`)와 같은 출력인지 확인(spec 11 P2 「진행 중」 을 닫기).

### 1.4 `go2` 모드 (go2-oh2l2)

정책을 돌리지 않는다. 실기 Go2 는 순정 Sport 모드로 움직이고, 앱은 실기 상태(관절각 12 · 몸 쿼터니언 · 위치)를 받아 시뮬 화면 로봇에 그린다. **지금 앱에는 이 상태를 내보내고 받는 길이 없다**(§3-6). ONNX · 지도 · 토크 칸은 null 로 등록한다.

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
- 화면 상한은 앱 설정 하나(지금 시뮬 전진 1.5 m/s). **단 지금 앱은 옆 0.3 · 회전 0.5 로 막고 회전 1.2 를 0.6 으로 갈아 끼운다(§3-2)** → 모드 상한을 따로 둔다. 실제로 보내는 값 = **min(화면 상한, 모드 상한)**. 화면에 「이 모드 상한」 을 함께 보여 준다(ame2 는 1.2).
- 가속 제한은 앱 공통 한 곳에 둔다. 값은 팀장 결정 대기(D108).
- **앞으로 목표 걷기도 쓴다.** START 기저 정책 실험(깃발)은 목표를 두고 걷게 하려는 것이다. 앱에서 「목표 지점」 을 찍으면 ame2 는 목표를 그대로, start 는 위 계층(경로 · 판단층)이 목표를 속도 명령으로 바꿔 넣는다(팀 결정: 속도 명령 + 위 계층). 그래서 `command()` 는 사람 속도와 목표 지점 두 입력을 받을 수 있게 열어 둔다.

### 2-3. ONNX 실행기 넓히기 (`policy-onnx.js`)

- 출력을 이름으로 여러 개 돌려준다(`action` 만이 아니라).
- `onnx.state` 에 적힌 짝대로 출력을 다음 호출의 입력으로 되먹인다(start 의 GRU 둘). 리셋 때 0.
- 입력은 contract.json 에 적힌 자료형대로 만든다. **start 의 플래그 셋(depth_tick · first_after_reset · use_gt)은 ONNX 에서 bool [1]** 이고 나머지는 float32 다(묶음 실측 · ORT Web 은 `new ort.Tensor('bool', [true], [1])` 로 받는다). 지금 실행기처럼 모두 float32 로 만들면 start 는 첫 호출에서 형식 오류가 난다.
- start 는 지도 모드에 따라 파일 둘 중 하나를 연다(on/off). 모드 안에서 지도 모드를 바꾸면 세션을 바꾸고 상태를 0 으로.

### 2-4. 모델별 범위 표 (브라우저 시뮬은 §3-2 의 앱 설정 · 서버 쪽 `policy_ranges.py` 는 런타임에서 안 읽힘)

지금 `VelocityRange` 는 전진 전용이다. 후진 하한 · 옆 · 제자리 회전 · 걸으며 회전 칸을 넣고 start · ame2 줄을 더한다. UI · 서버 · 에이전트가 이 표 하나로 자른다(D108).

### 2-5. 확인 (답을 아는 입력으로 먼저)

1. 순서: 기본 자세로 세우면 `관절각 − 기본` 12 가 전부 |값| < 0.05. a 에 0 을 넣으면 목표각 = §1.1 벡터.
2. 같은 출력: 묶음의 시험 벡터(아래 §2-5a)를 앱 실행기에 넣어 `action` 최대 차이 1e-4 이하. start 는 상태 되먹임까지 20 스텝 이어서.
3. 정지: 명령 0 으로 30 초 서 있기.
4. 토크: start 모드에서 calf 토크가 23.5 에서 잘리지 않는지(로그로).
5. 지도: 서 있는 평지에서 start 지도 값은 모든 칸이 약 −0.3(= 바닥 − 몸 높이), ame2 z 채널은 0 근처(+0.27 상수 때문). 두 값이 이렇게 다르게 나오면 지도 함수가 모드별로 맞게 나뉜 것이다.

### 2-5a. 시험 벡터 받는 꼴 (start-demo · ame2-demo 공통)

묶음마다 같은 내용을 두 꼴로 준다: `test_vectors_flat20.json`(앱 · Node · 브라우저용) · `test_vectors_flat20.npz`(파이썬용). 평지에서 실제 학습 환경을 20 스텝 돌리며 기록한 것이다.

```json
{
  "format": "<이름>-test-vectors/1",          // 예 start-demo-test-vectors/1
  "model": "start-demo", "checkpoint_sha256": "d5e9ec40...",
  "onnx": {"start-demo_map_on.onnx": "81c7e079..."},  // 어느 파일 · sha 로 만든 답인지
  "map_mode": "reconstruction",                // start: reconstruction · off · gt 셋을 각각 한 벌씩, ame2: gt
  "steps": 20, "tolerance": 1e-4, "state_feedback": true,   // ame2 는 false
  "inputs":   [ {"obs45": [...], "hist": [...], "...": [...]}, ... 20 개 ],   // ONNX 입력 이름 그대로, 펼친 float32 배열
  "expected": [ {"action": [...], "h_prop_next": [...], "h_terr_next": [...]}, ... 20 개 ]
}
```

앱 시험(이름 제안 `mobile/scripts/policy-vector-selftest.mjs`, Node ORT 와 브라우저 ORT 둘 다):

```js
const tv = JSON.parse(await readFile(path));
let state = null;
for (let k = 0; k < tv.steps; k++) {
  const feed = { ...tv.inputs[k] };
  if (tv.state_feedback && k > 0) Object.assign(feed, state);   // 기록된 h 가 아니라 **앱이 앞 스텝에서 받은 h** 를 넣는다
  const out = await infer(feed);                                 // 앱 실행기 그대로
  const err = maxAbs(out.action, tv.expected[k].action);
  if (err > tv.tolerance) throw new Error(`step ${k} action ${err}`);
  if (tv.state_feedback) state = { h_prop: out.h_prop_next, h_terr: out.h_terr_next };
}
```

- 첫 스텝은 기록된 입력 그대로(상태 0 · first_after_reset 1). 둘째부터 상태를 앱이 되먹여 20 스텝 모두 통과해야 실행기의 상태 되먹임이 맞다.
- 실패하면 몇 번째 스텝 · 어느 출력에서 벗어났는지가 원인을 알려 준다(첫 스텝 실패 = 입력 이름 · 순서 · 모양, 둘째부터 실패 = 상태 되먹임).
- 시험 벡터의 `onnx` sha 와 앱이 연 ONNX 의 sha 가 다르면 시험하지 않는다.

### 2-6. 하지 않는 것

- **start 의 f32 JS 신경망은 만들지 않는다.** 팀 방향은 「같은 ONNX 하나를 웹과 실기가 함께 쓴다」 이다. spec 11 의 「f32 JS 되돌림 경로」 요건은 foothold-v2 · ame2 에만 두고, start 는 parity(원본 대 ONNX 1e-4)로 대신한다(spec 11 고치기).
- 한 모드의 값을 다른 모드 기본값으로 쓰지 않는다(토크 23.5 가 그 예).
- ONNX 파일을 앱 저장소에 커밋하지 않는다(`FH_POLICY_ONNX_SRC`, spec 11:410~416). lab 의 묶음 폴더에서 복사하고, sha256 이 묶음의 contract.json · SHA256SUMS 와 같을 때만 쓴다. 복사 · 배포 자리는 §3-3 (`sync-web.mjs` · `prepare_sim.py`).


## 3. 앱 실제 구조와 파일별 할 일 (foothold-app dev `20f3d066` 전수 대조 · 줄 번호는 이 커밋)

§1 · §2 는 「무엇을」, 이 절은 「어느 파일의 어디를」 이다. 둘이 다르면 이 절이 맞다.

### 3-1. 지금 정책이 고르고 도는 흐름

1. 고르기: `main.js:19-21` 이 `?policy=` (없으면 `'foothold-v2'`) · 메뉴는 `index.html:88` option 둘 · 바꾸면 `main.js:164-167` 이 다시 연다.
2. AME-2 사용 가능 판정은 `main.js:170-177` 이 `options[1]` 고정 · ONNX 가 아니라 f32 파일 존재로 판정 · 실패 시 `main.js:158` 이 끔.
3. 가중치는 늘 f32 를 받는다(`main.js:204-205` · `:228`). 엔진 기본 `'f32'`(`main.js:233`).
4. ONNX 경로: `policy-onnx.js:73-78` 파일 하나 · SHA 확인 → Worker(`:79-88`, 기한 `policyDt`×1000 = 20 ms) → 5 번 늦으면 화면 쪽 ONNX → 실패 시 f32(`:90-111`).
5. 물리 한 번: `sim.js:98-113` `adapter.observe` 뒤 `policy(obs, s.mapping)` · 행동 `sim.js:114-123` · 토크 `sim.js:124-131`.
6. 명령: `main.js:656-665` · 시나리오 · 찍은 점은 `scenario.js:85-95` 의 `runner.tick` 이 `sim.cmd` 에 직접 씀 · ame2 는 `ame2Joystick` 이 목표를 만듦.
7. 자산: `sync-web.mjs:15-17`(`FH_SIM_SRC` 필수) · ame2 는 `FH_AME2_SRC`(id 고정 `:33,35,46`) · 나머지 `FH_POLICY_ONNX_SRC` · ORT `:55-63`. 서버 배포는 `deploy/prepare_sim.py:11-27 · 115-160` 의 SHA 허용 목록, `dev` 머지 = 자동 배포(spec 11:416). GitHub workflow 는 없음.

### 3-2. 모드 공통으로 고칠 곳

| 자리 | 지금 | 고칠 것 |
|---|---|---|
| `sim.js:105,111` | `policy(obs, mapping)` 인자 둘 고정 | `mode.inputs(s)` 가 contract 순서의 배열 묶음을 돌려주게 |
| 상태 · 이력 · 깊이 버퍼 확정 시점 | Worker 늦은 결과는 버림(`policy-worker-client.js:42-43`) → `frame-clock.js:15` 가 같은 스텝을 다시 부름 | **행동이 실제로 적용될 때(`applyAction`)만 확정.** `observe` 에서 이력을 밀면 두 번 밀린다 |
| 리셋 | `sim.js:71-82` 에 모드 리셋 고리 없음 · `main.js:45` 는 ame2 만 상태 지움 · `spawnOn`(`main.js:384-387`)은 리셋 뒤 자세를 다시 옮김 | 모드 `reset(mem)` 고리 · 이력은 「리셋 뒤 첫 관측」 으로 채움 · GRU 0 · first_after_reset true |
| ame2 판별 문자열 | `main.js:118-120,129,660-664,673` · `scenario.js:35` · `sync-web.mjs:35,46` · `policy-onnx.js:52` · `ame2-onnx.js:4-7` 가 `stop.pause` 나 `'ame2-demo'` 로 가림 | `mode.command.kind`(`body_velocity` · `goal_pose`) 같은 필드로 |
| 이름 바꾸기 foothold-v2 → nvidia-demo | `policy-adapters.js:173` · `sim.js:14,23` · `main.js:20` · 시험 `ame2-worker-selftest.mjs:112,137,165,198,215,287` · `settings-sim-selftest.mjs:8-10` · `sim-goal-selftest.mjs:283-284` | 모두 함께. URL `?policy=` 는 그대로 두고 값만 바꿔도 된다(`?mode=` 는 선택) |
| `policy-onnx.js:23,25` | 입력 전부 float32 · `every(Number.isFinite)` | 입력마다 contract `type`(bool 은 `Uint8Array` · `new ort.Tensor('bool', …)`) |
| `policy-onnx.js:35` · `:34` | `action` 하나만 · `offsets` 특례 | 출력 이름별 묶음을 돌려줌 · 특례를 일반화 |
| `policy-onnx.js:64` · `policy-worker.js:12` | 예열 입력이 float32 0 | 자료형별 예열(bool 입력에서 실패함) |
| `policy-worker.js:15-16` · `policy-worker-client.js:45,67` | `{action}` 만 보냄 · `data.action` · `Float32Array.from` | `{outputs}` + 버퍼 전송 목록 |
| 명령 상한 `manual-settings.js:14,20` | 앞뒤 대칭 축 하나 | 모드별 축 상한(후진 1.0 · 걸으며 회전 1.0 따로) |
| `settings.js:16` | `boundedNumber(caps.wz, 0, 1, 0.6)` · 1.2 를 「범위 밖」 으로 보고 **0.6 으로 갈아 끼움** | 모드 상한을 따로 두고 자르기(min)로 |
| `scenario.js:51-52` | 1.5 / 1 고정 | 모드 상한에서 |
| 조직 설정 `models.py:424-425` · `manual-settings.js:3` · `phone.ts:125` | `sim_max_vy ≤ 0.3` · `sim_max_wz ≤ 0.5`(기본도 같음) · `?from=web` 일 때만(`settings.js:25`) | 웹에서 연 start 는 옆 0.5 · 회전 1.2 를 못 낸다. 세 곳 상한을 함께 넓히거나 모드 상한을 조직 설정과 따로 둔다 |
| `policy_ranges.py` | `POLICY_RANGES` 를 런타임에서 읽는 곳 없음 · `:35` 제자리 회전 · 후진 거부 · `:47` 전진 전용 · 실제 서버 시뮬 범위는 `protocol.py:128-132` `SIMULATION_LIMITS`(Gazebo 경로) · `models.py:1821-1828` 후진 칸 없음 | 브라우저 MuJoCo 모드 상한과는 따로 다룬다. 서버 쪽은 이번 범위 밖으로 표시만 |

### 3-3. start 모드

| 할 일 | 자리 · 이유 |
|---|---|
| adapter 새로(`policy-adapters.js`) · `action.torque(tau, dq, i)` 에 관절별 DCMotor | `sim.js:17-21` `dcmotor` 는 12 관절 공통 한계 하나. torque 를 두면 MuJoCo 제한이 꺼진다(`sim.js:42-50`, `:46` 오류 문구가 「AME-2」 라 같이 고침) |
| a ±17 자르기 | 지금은 목표각 자르기(`sim.js:115-117`)만 |
| 모드 기본 엔진 ONNX · f32 없이 도는 길 | `main.js:204-205,228` 과 `policy-onnx.js:54,94,111` 이 f32 를 전제 → 「ONNX 실패 = 잠금 + 사유 표시」 새 경로 |
| ONNX 파일 둘(map_on · map_off) · 지도 모드 고르는 UI · 바꿀 때 세션 교체 + 상태 0 | `onnx.file` 하나만 받음(`policy-onnx.js:73` · `sync-web.mjs:47`) |
| 자산 복사 | `sync-web.mjs:45` 는 f32 가 없으면 그 정책의 ONNX 를 건너뜀 → f32 없는 모드 허용 · `deploy/prepare_sim.py:17-21` `ONNX_SHA` 에 두 파일 SHA(묶음 SHA256SUMS) · `deploy/tests/test_prepare_sim.py` 함께 |
| 높이 지도 32 × 16 | `makeTerrainSampler(mj, m, d, {grid, rayOffset})`(`policy-adapters.js:74-165`) 재사용 · 배열 순서는 yx(§1.2) · **광선 시작을 「몸 위 20 m」 로 하면 앱 장면 천장을 맞힌다** → foothold-v2 의 `rayOffset 0.501`(`:20-23`) 방식 또는 ame2 의 몸에서 위로 쏘는 탐침(`ame2-adapter.js:98-118`) 중 하나 |
| 깊이 60 × 60 | 앱에 오프스크린 깊이 그리기 없음(three 렌더러 하나 `main.js:275-291` · 라이다는 수평 360 줄 `lidar.js:14-15`). 방법: `mj_multiRay`(원점 하나 공유, `lidar.js:15`)로 60 × 60 = 3600 광선 핀홀 카메라(§1.2 카메라 자리 · 각도 · fx fy cx cy) · geom group 은 지형 필터 `[1,1,0,0,1,0]` + 로봇 제외(`policy-adapters.js:75-84`) · 10 Hz · 몸 전체 자세 기준 · 1 프레임 늦은 두 장 |
| 목표 걷기 | 위 계층이 이미 있다: `astar.planRoute` → `scenario.js:64-99` `runner.tick` 이 `[vx, 0, wz]`(기본 `sim_runner_vx` 0.4). start 는 이것을 그대로 쓴다. 옆 · 후진은 만들지 않음(`:95`). §2-2 의 `command(human, goal)` 대신 runner 가 `sim.cmd` 에 쓰는 지금 구조를 따른다 |
| 시험 | `start-demo-vector-selftest.mjs`(Node · 브라우저 ORT, 20 스텝 상태 되먹임) · 깊이 · 지도 단언(평지 값, 천장 무시) · Worker 출력 여러 개 · bool 입력(`ame2-worker-selftest.mjs` 틀) · `prepare_sim` 시험. **이름 주의**: `start-selftest.mjs` · `mobile/start/` 는 「시작 화면」 이다(`package.json` selftest) · 새 파일은 `start-demo-*` |
| 용량 · 시간 | 파일 둘 각 5.8 MB · Worker 초기화 때 사본 하나 더(`policy-worker-client.js:61`, 초기화 기한 15 초). 추론 20 ms 안인지는 아직 안 잼 |

### 3-4. ame2 모드

| 할 일 | 자리 |
|---|---|
| 새 ONNX 계약 | 지금 계약은 `offsets`(int64) · `gaze_logits` 출력이 꼭 있어야 함(`policy-adapters.js:168-171`, 검사 `policy-onnx.js:11`). 새 파일에 없으면 계약도 고침 |
| f32 되돌림 | f32 는 옛 재구성 actor(`policy-adapters.js:69` `28edbc05…`). ONNX 만 바꾸면 되돌릴 때 **다른 정책이 조용히 돈다** → 새 f32 를 받거나 ame2 도 f32 되돌림을 끈다. 사용 판정(`main.js:170-173`)도 f32 기준 |
| 행동 지연 0 | 앱은 리셋마다 0~4 를 무작위로 뽑는다(`ame2-adapter.js:41`, `main.js:242` 가 `ame2DelaySteps` 를 안 넘김) → `ame2DelaySteps: 0` |
| 배포 허용 목록 | `prepare_sim.py:12-21` `AME2_SHA` · `ONNX_SHA` 를 새 파일로 |

### 3-5. nvidia 모드

id · 메뉴 이름만 바꾼다. f32 와 원본 대조는 spec 11:98 에 「130 입력 최대 차 0」 으로 이미 통과했으니 spec 11:209 P2 「진행 중」 표 상태만 닫는다.

### 3-6. go2 모드 (새로 만들 길이 길다)

- 상태 원본이 없다: agent 가 `rt/lowstate` · `rt/sportmodestate` 를 구독은 하지만(`go2_readonly/sdk.py:28-29`) 내보내는 것은 배터리 · roll/pitch · mode · error 뿐(`go2_readonly/state.py:68-71,110-118`). 관절각 q 12 · 쿼터니언 · 위치는 어디에도 안 나간다(`go2_direct/feedback.py:67-69` 는 dq 를 정지 판정에만).
- 전달 경로가 없다: 앱 안 시뮬은 서버와 끊긴 묶음(`main.js:1`) · CSP `connect-src 'self'`(`index.html:7`) · 서버에 묻는 것은 `?from=web` 때뿐(`settings.js:25`).
- 할 일: agent 가 q · 쿼터니언 · 위치를 내보냄 → 서버 API → 앱이 받아 `qpos` 넣고 `mj_forward`(`spawnOn` `main.js:384-387` · `draw` `:368-374` 재사용) · SDK 모터 순서 FR FL RR RL → 이름으로 재배열.
- 명령은 기존 서버 실기 표(`protocol.py:121-124`: vx 0~1.5 단계값 · vy 0 · wz ±0.5, 후진 · 옆 없음)로 Sport 모드에 보낸다.

### 3-7. 묶음과 맞출 것 (start-demo)

- 묶음 `contract.json` 의 `app_onnx` 칸에 앱 adapter `onnx` 꼴 그대로 입력 9 · 출력 4 의 이름 · dims · type 을 넣었다. 입력 순서는 ONNX `session.inputNames` 실측 순서와 같다(앱은 이 순서가 같아야 받는다, `policy-onnx.js:10`).
- `gt_map` 은 `[1,32,16]`(§1.2 표의 `[1,512]` 는 원소 수 표기였음, 모양은 `[1,32,16]` 으로 쓴다).
- 깊이 지연 뜻: 10 Hz 로 새 프레임이 들어온 스텝에만 `depth_tick` true, `depth2` 는 「1 프레임(0.1 s) 늦게 전달된 최근 두 장」.

## 4. 남은 것 · 정할 것

- 가속 제한 값(팀장, D108).
- ame2 1 m 목표에서 실제 속도: 앱 시뮬에서 재서 모드 상한 표에 적기(현민).
- ONNX 추론 속도: 나중에 따로 논의(팀장 16:3x). 그때까지는 지금 Worker 구조 그대로.
