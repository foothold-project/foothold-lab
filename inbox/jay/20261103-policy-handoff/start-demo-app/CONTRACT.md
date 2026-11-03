> **최신 결정 (2026-11-03 19:3x · 이 문서의 아래 내용보다 우선):** ① 앱 ONNX 실행기는 GRU 상태 출력(h_prop_next · h_terr_next)을 다음 호출의 h_prop · h_terr 로 **되먹이기로 정했다**(현민 님이 넣음 · 앱 문서 §2-3 · §3-2). ② start 는 f32 JS 신경망을 만들지 않는다(ONNX 만). ③ 플래그 셋(depth_tick · first_after_reset · use_gt)은 bool [1] · `gt_map` 은 [1,32,16]. ④ 이 묶음은 전달 완료(lab PR #571 · D144 닫힘). ⑤ 이름은 start-demo(최종 start-oh2l2). ⑥ 미확인: 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음). ⑦ 앱 쪽 파일별 할 일은 `../HANDOFF-APP-DEVELOPER.md` §3. 아래 §6 · §10 의 옛 물음은 이 결정으로 모두 닫혔다. 걸으며 회전 1.0 · 대각은 전진 · 옆 상한을 각각 적용 · 앱이 깎는 곳은 `../HANDOFF-APP-DEVELOPER.md` v0.3 §1.5 가 최종이다(11/03 21:5x).

> 분류: A/정책학습 · 앱 전달 조건표 초안 (W89 · D144 · m6000 기준)
> 작성: planner (Claude Fable 5.1) · 2026-11-02 20:5x v0.1 (lead 20:4x 대기열 (3): 「W89 앱 조건표 초안, m6000 기준 · ONNX 는 scripter 가 뒤에 · 각 값에 m6000 env.yaml/agent.yaml 줄 번호」) · 21:3x v0.2(lead 21:2x 가 전한 팀장 묶음 (A) + lead 20:4x W89-1~3: D108 정본 · m6000 명령 파일 값 · 맨 위 값 표 · 지도 모드 셋 · Unitree 공식 한계 대조표 · 관절 순서 경고 칸 · ONNX 받아 쓰는 법)
> 근거: EX-40 실행 폴더 `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/`(`params/env.yaml` · `params/agent.yaml` · `model_6000.pt` · `training_trace/coordinate_metadata.json`, 전부 직접 읽음) · 코드 `foothold_s2`(analyst c6fff190 사본, 읽기 전용: `models/start_perception.py` · `models/start_policy.py` · `runners/start_runner.py` · `sensors/start_obs.py` · `sensors/depth_cam_cfg.py` · `sensors/depth_aug.py` · `commands/mixed_command.py` · `curriculum/ex40.yaml` · `robots/go2_params.py` · `deploy/{export.py,obs.py,sdk_joints.py,record_isaac.py,params/deploy.yaml}`) · WORKLIST 11fdb8e4 D103(131 행) · D144(172 행) · W89(283 행) · `inbox/jay/20261101-app/APP-INTEGRATION-NOTES.md` §3 · §5 · `QA-EXPLAINERS.md` 「AME-2 앱 대조 확인」
> 요지: 앱(foothold-app) 과 실기 노드가 m6000 정책을 그대로 돌리려면 맞춰야 하는 조건을 한 표로 모았다. 정책은 actor MLP 하나가 아니라 **지각(TR-Net · I-E 추정기, GRU 둘) + actor** 이고 actor 입력 96 = 몸감각 45 + 추정 51(**z 16 · v 3 · zf 16 · zb 16 순서**) 이다. 50 Hz · Kp 25 · Kd 0.5 · 행동 = 기본 자세 + 0.25 × a · 기본 자세 hip ±0.1 / 앞 thigh 0.8 · 뒤 1.0 / calf −1.5 · Isaac 관절 순서 hip 4 → thigh 4 → calf 4(FL FR RL RR, **이 run 의 training_trace 기록으로 확정**) · 토크 한계 hip · thigh 23.5 / calf 45.43 N·m(DCMotor 곡선) · 명령 (vx, vy, wz) 학습 표집 범위는 **B3c 표**(전진 0.1~1.5 · 후진 −1.0~−0.2 · 옆 0.2~0.6 · 제자리 회전 0.3~1.5 · 걸으며 회전 0.2~1.0) · 지도 32 × 16 · 5 cm · 중심 x +0.3 · 깊이 60 × 60 · 10 Hz · 1 프레임 지연 · (d − 0.2)/2.8. 저장소의 `deploy/` 묶음(export.py · deploy.yaml) 은 **S1-blind(495 입력) 용**이라 m6000 에는 못 쓰고, APP-INTEGRATION-NOTES §5 의 명령 범위 표는 B0 값이라 B3c 로 갱신해야 한다(어긋남 둘). 넘기는 것은 D144 대로 팀장 결정 뒤. **v0.2**: 명령 상한의 정본은 **D108**(모델별 명령 범위 파일 · 우리 학습 범위가 기준 · 전진 1.5 · 후진 1.3 · 옆 0.5 · 회전 1.2 · 앱 가속 제한) 이고 m6000 의 파일 값은 학습 범위 안으로 **전진 1.5 · 후진 1.0 · 옆 0.5 · 제자리 회전 1.2**(§3.5). 지도 모드는 인터페이스에 셋 다 두되 실기는 복원 · 끔, 시뮬 트윈은 정답도(§3.6). Kp · Kd · 토크 · 주기 · 행동 배율은 §0a 맨 위 표. Unitree 공식 한계 대조표(§3.2a) 와 관절 순서 경고 칸(§0b), AME-2 실험 팀원용 「ONNX 받아 쓰는 법」(§5a) 을 더했다.
> v0.3 (lead · 2026-11-03 15:3x · 팀장 15:2x 「앱 최신판을 보고 이 문서를 갱신」): 앱 foothold-app dev `d9b6f382`(2026-11-03 05:32Z) 를 gh 로 읽어 대조했다(§10). 고친 것: §0b 관절 순서(앱 두 adapter 모두 우리와 같은 hip4 → thigh4 → calf4 · v0.2 의 「AME-2 adapter 는 다리 단위」 는 틀림) · §0a 명령 상한 행(앱에 m6000 범위 줄 없음 · 앱 1.5 m/s 표는 Unitree Sport Move 용) · §5a 입출력 이름(제안 이름 → scripter 가 실제 내보낸 `w89_export/contract.json` 이름 · ONNX 파일 둘) · 앱 ONNX 실행기는 상태 없는 입력만 다뤄 m6000 은 지금 앱에서 못 돈다(§10).
> 상태: v0.3 · ONNX 는 scripter 가 내보냄(34982e13 · `D:/mai-tmp/scripter/w89_export/`) · 앱 m6000 adapter 없음 · v0.2 당시: 코드 · GPU · ONNX 내보내기 없음(조건표만) · W89-1 · W89-2 닫힘(lead 20:4x · 팀장 11/02 21:1x 요지) · W89-3 공식 값 대조표 들어감(실기 SDK 가 실제로 거는 값은 **미확인**) · W89-4 팀장 대기(뒤에 닫힘 · §6) · 시험 `app_contract_check.py`(기계 블록 §9 대 env.yaml · agent.yaml · ex40.yaml · 기록 파일 대조 + 「m6000 파일 값 = min(D108, B3c)」 규칙)

# m6000 정책을 앱 · 실기에 넘길 때 맞출 조건표 (W89 · D144)

## 0a. 앱 개발자가 맨 먼저 볼 값 (팀장 11/02 21:1x 요지: PD · 토크 · 주기 · 행동 배율을 표 맨 위에)

| 값 | 숫자 | 뜻 한 줄 | 출처 | 등급 |
|---|---|---|---|---|
| **Kp** | **25.0** N·m/rad · 관절 12 모두 | 목표각 − 현재각 에 곱하는 스프링 세기. 실기 LowCmd 의 kp 에 그대로 | `env.yaml:328` · `:343` | 설정 |
| **Kd** | **0.5** N·m·s/rad · 관절 12 모두 | 관절 속도에 곱하는 감쇠. LowCmd 의 kd 에 그대로 | `env.yaml:329` · `:344` | 설정 |
| **토크 한계** | hip · thigh **23.5** N·m / calf **45.43** N·m (속도 한계 30.0 / 15.7 rad/s, DCMotor 곡선: 빠를수록 상한이 내려감) | 학습이 가정한 모터 상한. 공식 값과의 대조는 §3.2a | `env.yaml:324~325` · `:339~340` · `go2_params.py:16~19` | 설정 |
| **제어 주기** | **50 Hz** (20 ms) = 물리 dt 0.005 s × decimation 4. 깊이 카메라는 10 Hz | 정책 한 번 = 관절 목표 한 번. 20 ms 를 넘기면 학습 조건이 아니다 | `env.yaml:21` · `:84` · `depth_cam update_period 0.1` | 설정 |
| **행동 배율** | 관절 목표각(rad, Isaac 순서) = **기본 관절각 + 0.25 × a**, a 는 먼저 ±17 로 자름 | 정책 출력 12 개를 각도로 바꾸는 식. 목표 속도 0 · 앞먹임 토크 0 | `env.yaml:1583`(scale) · `:1586`(use_default_offset) · `agent.yaml:11`(clip 17) | 설정 |
| **기본 관절각** | hip **+0.1**(왼쪽) · **−0.1**(오른쪽) · thigh 앞 **0.8** · 뒤 **1.0** · calf **−1.5** rad | 위 식의 기준 자세. 관측 `joint_pos_rel` 도 여기서 뺀 값 | `env.yaml:306~311` | 설정 |
| **명령 상한(m6000 파일 값)** | 전진 **1.5** · 후진 **1.0** · 옆 **0.5** · 제자리 회전 **1.2** m/s · rad/s (정본 D108 안에서 학습 범위로 자름, §3.5) | 앱이 이 모델에 보낼 수 있는 최대. **v0.3: 앱에는 아직 m6000 줄이 없다.** 앱의 모델별 범위 정본은 `apps/agent/foothold_agent/policy_ranges.py:54~56` `POLICY_RANGES` 이고 지금 `foothold-v2` 한 줄(vx 0.4~1.5 · vy 0 · wz ±1)뿐이며 형식이 전진 전용(`requires_forward_motion=True`)이라 후진 · 옆 · 제자리 회전 칸을 넓혀야 한다. 앱의 ±1.5 m/s 실기 표(`apps/contracts/server_drive.py:2~4`)는 Unitree Sport Move 용이라 이 값과 섞지 않는다 | WORKLIST D108 · `ex40.yaml:116~121` · 앱 @d9b6f382 | 결정 · 설정 · 코드 |
| **관측 45 · 출력 12** | 몸 각속도 3 · 중력 방향 3 · 명령 3 · 관절각 − 기본 12 · 관절 속도 12 · 직전 행동 12. 배율 1 · 자르기 없음 | 순서가 하나라도 밀리면 걷지 못한다(§3.4) | `env.yaml:1247~1323` | 설정 |

## 0b. ⚠ 경고 칸: 관절 순서 (크게 · 팀장 지시로 따로 둠)

**우리 정책의 관절 벡터 12 는 「관절 종류 단위」 다: hip 4 개 → thigh 4 개 → calf 4 개, 다리는 FL FR RL RR 순.** 이것은 이 run 의 `training_trace/coordinate_metadata.json` `joint_names`(source "training") 로 **확정**된 값이다. **v0.3 정정:** 앱의 두 adapter 도 같은 순서다. AME-2 adapter `mobile/sim/ame2-adapter.js:3~9`(@d9b6f382, 저장본 joint_names 로 확인했다고 적힘 · lead 가 analyst 사본 135a8469 같은 줄을 직접 읽음) 와 foothold-v2 `policy-adapters.js:4~5` 모두 hip4 → thigh4 → calf4 · FL FR RL RR 이다. v0.2 의 「AME-2 adapter 는 다리 단위」 는 QA-EXPLAINERS 43 행의 모호한 문장을 잘못 읽은 것이었다. 다리 단위 순서는 앱 MuJoCo 내부 `MJ_J`(`sim.js:9`) 뿐이고 이름으로 다시 맞춘다(`sim.js:31~33`). **순서 위험은 SDK(LowCmd · LowState) 쪽에 남는다: 모터 순서가 FR FL RR RL 다리 단위다.**

| 순서 이름 | 벡터 index 0 → 11 | 기본 관절각을 이 순서로 적으면(시험 벡터) |
|---|---|---|
| **Isaac = 우리 정책 입출력** | FL_hip FR_hip RL_hip RR_hip · FL_thigh FR_thigh RL_thigh RR_thigh · FL_calf FR_calf RL_calf RR_calf | `[0.1, −0.1, 0.1, −0.1, 0.8, 0.8, 1.0, 1.0, −1.5, −1.5, −1.5, −1.5]` |
| 앱 두 adapter (v0.3 확인) | Isaac 과 같음 | 위와 같음 |
| 앱 MuJoCo 내부 `MJ_J`(이름으로 재배열) | FL(hip thigh calf) · FR(…) · RL(…) · RR(…) | `[0.1, 0.8, −1.5, −0.1, 0.8, −1.5, 0.1, 1.0, −1.5, −0.1, 1.0, −1.5]` |
| Unitree SDK 모터 0~11 | FR(hip thigh calf) · FL(…) · RR(…) · RL(…) | `[−0.1, 0.8, −1.5, 0.1, 0.8, −1.5, −0.1, 1.0, −1.5, 0.1, 1.0, −1.5]` |

- Isaac ↔ SDK 순열은 `deploy/sdk_joints.py` 의 `joint_ids_map [1, 5, 9, 0, 4, 8, 3, 7, 11, 2, 6, 10]`(SDK i 번 모터 = Isaac 그 index) 이다(**코드**). 앱 adapter 순서에서 Isaac 으로는 `[0, 3, 6, 9, 1, 4, 7, 10, 2, 5, 8, 11]` 로 모은다(**계산**).
- **확인 절차**(개발자가 1 분에 끝내는 시험): 로봇(또는 시뮬)을 기본 자세로 세우고 관측 `joint_pos_rel` 12 가 전부 |값| < 0.05 인지 본다. 순서가 틀리면 ±0.9 · ±2.3 같은 큰 값이 보인다. 그다음 정책 출력에 0 을 넣고 목표각이 위 Isaac 시험 벡터와 같은지 본다.


## 0. 범위 · 가정

- 카드(lead 20:4x (3) · WORKLIST W89 283 행 · D144 172 행): 「m6000 기준 조건표: 명령 범위 · 관측 순서와 배율 · 행동 배율 · 기본 관절각 · PD · 토크 한계 · 제어 주기 · 지도 입력, 각 값에 m6000 env.yaml/agent.yaml 줄 번호. ONNX 는 scripter 가 뒤에」. 이 문서는 **조건표와 ONNX 에 무엇이 들어가야 하는지**까지만 적고, 내보내기 · 앱 코드 · 실기 노드는 하지 않는다.
- 가정 1: m6000 의 설정 정본은 그 run 폴더의 `params/env.yaml` · `params/agent.yaml`(학습이 실제로 읽은 것) 이다. 코드 줄 번호는 analyst c6fff190 사본에서 읽었고 EX-40 실행 코드(`git/` · `source_dirty.diff`) 와 같은지는 **대조하지 않았다**(§7).
- 가정 2: 「앱이 맞출 조건」 은 ① 실기 노드(정책을 돌리는 쪽) 가 정책에 줄 입력 · 받을 출력의 계약, ② 앱이 보내는 명령의 범위, 둘이다. D103 의 세 지도 모드(정답 · 복원 · 끔) 가운데 실기에서 가능한 것은 복원 · 끔 둘이다(정답 지도는 시뮬 광선).
- 등급: **설정**(env.yaml · agent.yaml 줄) · **코드** · **실측**(run 폴더 기록 · 파일 해시) · **읽기**(다른 문서) · **계산** · **가정**.

## 1. 저장본

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 파일 | `.../EX-40-B-main_20261031_041337_26240/model_6000.pt` · 26,895,071 B | run 폴더 | 실측 |
| sha256 | `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`(점수 파일 이름의 `d5e9ec400f33` 과 같음) | `sha256sum`(11/02 20:4x) | 실측 |
| 자리 | EX-40 B3c 끝(m6000) · 정답 지도 학습(`force_gt: true`) · DR 배율 0.5 · EX-41 부모 · C층 정본(D131) · 앱용 저장본 기준(D144, m8000 아님) | `agent.yaml:67` · WORKLIST D131 · D144 | 설정 · 결정 |
| 지각 설정 | `map_input: reconstruction`(복원 경로 있음) · `est_mode: learned` · `critic_mode: clean52` · `p_map_off: 0.1` · `contract: basic_gait_ex40` | `agent.yaml:58~68` | 설정 |
| 신경망 | actor · critic 은닉 [512, 256, 128] · ELU · 관측 정규화 **없음**(`actor_obs_normalization: false`) · `clip_actions: 17.0` · `init_noise_std 1.0` | `agent.yaml:11 · 23~36` | 설정 |
| 저장본 안의 것 | rsl_rl `model_state_dict`(actor · critic · std) 와 지각 모듈 상태(runner 가 따로 저장, 키 이름은 scripter 가 열어 확인) | `start_policy.py:1~7`(지각 파라미터는 actor 모듈 밖) | 코드 · **미확인**(키 이름) |

## 2. ONNX 에 무엇이 들어가야 하나 (포함 여부 · W89 「지각 · 추정기 · actor 포함 여부 명시」)

actor MLP 만 내보내면 **움직이지 않는다**. actor 입력 96 가운데 51 이 지각 모듈의 출력이기 때문이다.

| 조각 | 안에 있는 것 | 상태(기억) | 포함 |
|---|---|---|---|
| 몸감각 이력 → I-E 추정기 | 이력 10 × 45 = 450 → `prop_mlp` → GRU 128(`h_prop`) → prop 토큰 64 + 지도 토큰 128(32 × 16 → CNN 16 × 8 × 64) → transformer encoder 2 층 → heads → (mu 16, logvar 16, v 3, zb 16, zf 16) | `h_prop` 128 · 이력 버퍼 10 × 45 | **포함**(또는 앱이 이력 · GRU 상태를 들고 ONNX 에 넘김) |
| 깊이 → TR-Net(복원 지도) | 깊이 2 프레임(60 × 60, 1 프레임 지연) → CNN 1024 + prop 64 → GRU 128(`h_terr`) → rough 512 → U-Net refine → 복원 지도 32 × 16 | `h_terr` 128 · 깊이 프레임 버퍼(2 + 지연 1 = 3) · 10 Hz 틱(5 스텝마다) | **포함**(복원 모드) · 끔 모드면 생략 가능 |
| actor | 96 → 512 → 256 → 128 → 12 · ELU | 없음 | 포함 |
| critic · 발 지도 100 · 정답 지도 | 학습 전용(특권 입력) | | **제외** |
| AdaSmpl(정답 · 복원 확률 p) | 학습 장치. 실기는 정답 지도가 없으므로 항상 복원(또는 끔) | | 제외(모드는 플래그로) |

- est 51 의 **순서**: `torch.cat([z, v, zf, zb])` = z 16 · v 3 · zf 16 · zb 16 (`start_perception.py:355`). 배포 추론은 z = mu(`deterministic`, `:352`). 앞서 QA 「지각 추정값 51 개」 절이 「몸 속도 3 · z 16 · zb 16 · zf 16」 순으로 적은 것은 뜻 설명이지 코드 순서가 아니다(§4 ④).
- 지도 끔 모드 = 지도 토큰을 attention 키에서 뺀다(`start_perception.py:166~173`, 평가 `probe_prop_only` 와 같은 방식). 지도를 0 으로 채우는 것과 다르다.
- 저장소에 있는 `deploy/export.py` 는 **S1-blind actor(입력 495 = 11 × 45 이력)** 전용이고(`export.py:1 · :10`), `deploy/params/deploy.yaml` · `deploy/obs.py`(HISTORY 11) 도 그 판이다. m6000 에는 새 내보내기(지각 포함 · 상태 입출력) 가 필요하다 → scripter(W89). GRUCell · TransformerEncoder 의 ONNX 변환은 v0.3 에서 끝남(두 그래프 checker PASS · 실제 입력 최대 차 3.46e-6, §5a 끝).

## 3. 조건표 (앱 · 실기 노드가 맞출 값)

### 3.1 제어 주기 · 관절 순서 · 기본 자세

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 제어 주기 | **50 Hz**(물리 dt 0.005 s × decimation 4 = 0.02 s). 깊이는 10 Hz(5 스텝마다) · 지도 · 추정은 매 스텝 | `env.yaml:21`(dt) · `:84`(decimation) · `:497`(depth_cam update_period 0.1) · `coordinate_metadata.json` control_dt_s 0.02 | 설정 · 실측 |
| 관절 순서(Isaac = 정책 벡터 순서) | `FL_hip FR_hip RL_hip RR_hip FL_thigh FR_thigh RL_thigh RR_thigh FL_calf FR_calf RL_calf RR_calf`(hip 4 → thigh 4 → calf 4, 다리 FL FR RL RR) | **이 run** `training_trace/coordinate_metadata.json` `joint_names`(source "training", 학습 env 의 `asset.data.joint_names` 기록) | **실측**(QA 「학습 실제 순서 미확인」 은 이 기록으로 닫힌다) |
| SDK 모터 순서 | `FR(hip thigh calf) FL RR RL` · Isaac ↔ SDK 순열 `joint_ids_map [1, 5, 9, 0, 4, 8, 3, 7, 11, 2, 6, 10]`(SDK i 번 모터 = Isaac 인덱스) | `deploy/sdk_joints.py:9~14` · `deploy/params/deploy.yaml` joint_ids_map(S1 기록이지만 같은 Go2 USD · 같은 Isaac 순서) | 코드 · 읽기 |
| 기본 관절각(rad) | hip: L +0.1 · R −0.1 / thigh: 앞 0.8 · 뒤 1.0 / calf −1.5 → Isaac 순서로 `[0.1, −0.1, 0.1, −0.1, 0.8, 0.8, 1.0, 1.0, −1.5, −1.5, −1.5, −1.5]` | `env.yaml:306~311`(init_state.joint_pos 정규식) | 설정 |
| 시작 몸 높이 | 0.4 m(리셋 자세, 서 있는 높이는 이보다 낮게 가라앉음) | `env.yaml:289~292` | 설정 |

### 3.2 PD · 토크 한계

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| PD 이득 | 관절 12 모두 **Kp 25.0 N·m/rad · Kd 0.5 N·m·s/rad**. 토크 = Kp(목표 − 현재) − Kd × 관절 속도. 학습 DR 이 ±10 % 흔들었음(`gain_scale 0.9~1.1`) | `env.yaml:328~329`(hip · thigh) · `:343~344`(calf) · `go2_params.py:16~19 · :24` | 설정 · 코드 |
| 토크 한계 | hip · thigh **23.5 N·m** · 속도 한계 30.0 rad/s / calf **45.43 N·m** · 15.7 rad/s. 학습은 DCMotor 곡선(상한 = min(effort, saturation × (1 − q̇/v_lim))) 으로 잘랐다 | `env.yaml:324~325 · :339~340` · `go2_params.py:35~50` | 설정 · 코드 |
| 실기 대응 | 공식 값 대조는 아래 §3.2a. 실기 SDK 가 LowCmd tau · 속도에 거는 실제 한계는 **미확인**(실기 담당이 LowState 로 잰다, W89-3) | §3.2a | 웹 · 미확인 |

#### 3.2a Unitree 공식 값 대조표 (W89-3 · lead 20:4x 「공식 문서 · SDK 값을 출처와 함께, 못 찾으면 미확인」)

출처(전부 11/02 21:2x 읽음): ① Unitree 공식 제품면 [unitree.com/go2](https://www.unitree.com/go2) 사양표 · ② 공식 GitHub `unitreerobotics/unitree_mujoco` `unitree_robots/go2/go2.xml`(커밋 4746f6bc · 2024-04-29 · 받은 파일 sha256 2014a3d7…) · ③ 공식 GitHub `unitreerobotics/unitree_rl_gym` `resources/robots/go2/urdf/go2.urdf`(커밋 25877c7e · 2023-10-11 · sha256 4f306754…) · ④ 이 기기의 학습 자산 `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf`(제3자 저장소 wertyuilife2 · sha256 f130b1d2…, **비공식**). `unitree_ros` 의 `go2_description` 경로는 404 라 못 받았다. 받은 파일은 `D:/mai-tmp/planner/unitree_dl/` 에 두었다.

| 항목 | 학습 설정(m6000) | ① 공식 제품면 | ② unitree_mujoco | ③ unitree_rl_gym URDF | ④ 학습 URDF(비공식) | 판정 |
|---|---|---|---|---|---|---|
| hip 토크 | 23.5 N·m | 없음(피크 「약 45 N·m」 는 가장 큰 모터 = 무릎 기준, 각주 [1]) | ctrlrange ±23.7 | effort 23.7 | 23.7 | 학습이 0.2 작음(보수적) · 같다고 봄 |
| thigh 토크 | 23.5 | 같음 | ±23.7 | 23.7 | 23.7 | 같음 |
| calf 토크 | 45.43 | 약 45 | ±45.43 | **35.55** | 45.43 | **두 공식 파일이 다름**. 실기 SDK 가 거는 값 **미확인** |
| hip · thigh 속도 한계 | 30.0 rad/s | 없음 | (xml 에 없음) | 30.1 | 30.1 | 같다고 봄 |
| calf 속도 한계 | 15.7 | 없음 | (없음) | **20.07** | 15.70 | **두 공식 파일이 다름** · 미확인 |
| hip 각 범위 | 학습은 자산 URDF 한계를 PhysX 가 막음(설정에 별도 clip 없음) | **±48°** | ±1.0472 rad(±60°) | ±1.0472 | ±1.0472 | **제품면과 파일이 다름**(12°). 실기 노드는 보수적인 ±48° 안에서 자르는 것이 안전(**가정**) |
| thigh 각 범위 | 같음 | −200° ~ 90° | 앞 −1.5708 ~ 3.4907 (−90° ~ 200°) · 뒤 −0.5236 ~ 4.5379 (−30° ~ 260°) | 같음 | 같음 | 제품면은 부호가 반대로 적혀 있고 앞 · 뒤 구분이 없다. 기본 자세 0.8 · 1.0 은 어느 쪽이든 안 |
| calf 각 범위 | 같음 | −156° ~ −48° | −2.7227 ~ −0.83776 (−156° ~ −48°) | 같음 | 같음 | **일치**. 기본 −1.5(−86°) 는 안 |
| 질량 | 학습 USD 15.019 kg(EX-42 §4.1) | 「약 15 kg」(배터리 포함) | | | 16.087 | 공식과 학습 USD 같음 |

읽는 법. 토크 · 속도 한계는 학습이 쓴 값이 공식 파일 가운데 하나(②) 와 같고 다른 하나(③) 와 다르다. 어느 쪽이 실기 모터의 실제 한계인지는 공식 문서에 없다(제품면은 피크 하나만 적음). 실기 노드는 **학습 값을 넘지 않게** 자르고, 실제 한계는 실기에서 LowState 의 tau 로 잰다. 관절 각 범위는 세 파일이 같고 제품면 hip 만 좁다. 정책 목표각은 기본 + 0.25 × (±17) 라 식으로는 ±4.25 rad 까지 나올 수 있으므로 **실기 노드가 목표각을 관절 범위 안으로 자른다**(학습에서는 관절 한계가 물리로 막았다).

### 3.3 행동

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 뜻 | 관절 목표각 12(Isaac 순서) = **기본 관절각 + 0.25 × a** | `env.yaml:1583`(scale 0.25) · `:1584`(offset 0.0) · `:1586`(use_default_offset true) | 설정 |
| 자르기 | rsl_rl `clip_actions 17.0`(a 를 ±17 로 자른 뒤 배율) · env 쪽 `clip: null` | `agent.yaml:11` · `env.yaml:1580` | 설정 |
| 지연 | 학습 때 0~15 ms 행동 지연 DR(`max_delay_s 0.015`, DR 배율 연동). 실기는 노드 지연이 그 안에 들어오는지 잰다 | `env.yaml:1577 · :1587~1588` | 설정 |
| 기록 | `coordinate_metadata.json` action = 「wrapper 자르기 · 지연 전의 PPO 표집 행동」 | 실측 기록 | 실측 |

### 3.4 관측(몸감각 45 · 순서 · 배율)

policy 묶음은 항 6 개를 이 순서로 이어 붙인 **45** 이고, 모든 항이 `scale: null` · `clip: null`(배율 1 · 자르기 없음) 이다(`env.yaml:1247~1323`). 이력은 policy 묶음에 없고(`history_length: null`, `:1251`) 지각 모듈이 10 스텝을 쌓는다.

| 순서 | 항 | 차원 | 뜻 · 단위 | 학습 잡음(실기는 없음) | 출처 |
|---|---|---|---|---|---|
| 1 | base_ang_vel | 3 | 몸 틀 각속도 rad/s(IMU gyro) | U(±0.2) | `env.yaml:1253~1265` |
| 2 | projected_gravity | 3 | 몸 틀에서 본 중력 방향(단위벡터), 쿼터니언에서 계산(식은 `deploy/obs.py:16~22`) | U(±0.05) | `:1266~1278` |
| 3 | velocity_commands | 3 | (vx, vy, wz) 몸 틀 m/s · rad/s | 없음 | `:1279~1288` · `mixed_command.py:39 · :90`(3 열) |
| 4 | joint_pos_rel | 12 | 관절각 − 기본 관절각(rad, Isaac 순서) | U(±0.01) | `:1289~1301` |
| 5 | joint_vel_rel | 12 | 관절 속도 rad/s | U(±1.5) | `:1302~1314` |
| 6 | last_action | 12 | 직전 스텝의 a(자르기 · 배율 전) | 없음 | `:1315~1323` |

- actor 입력 96 = 위 45 + est 51(§2 순서). `start_runner.py:235~245`(`_ppo_obs`: `cat([o, est_in])`) · `start_policy.py:1`.
- 지각 모듈이 받는 이력은 같은 45 를 10 스텝(`HIST_LEN 10`, `start_perception.py:33`) · 리셋 때 첫 관측으로 채움(`:296~312 ingest`). 이력 안에 명령 3 이 들어 있으므로 명령을 바꾸면 10 스텝 동안 섞인다.

### 3.5 명령 범위 (정본 = D108 · m6000 파일 값은 학습 범위 안으로)

정본(**D108**, 11/02 팀장 · WORKLIST 136 행): 앱 명령 상한은 **모델마다 「명령 범위 파일」** 로 두고, **우리 학습 범위가 기준**이다(전진 1.5 · 후진 1.3 · 옆 0.5, 학습이 넓어지면 0.8 · 회전 1.2 · 앱 가속 제한). m6000 의 파일 값은 D108 상한과 m6000 이 실제로 배운 B3c 표집 범위(`ex40.yaml:116~123`, 학습 표집기 `env.yaml:2351~2373`) 가운데 **작은 쪽**이다(lead 21:2x 가 전한 팀장 요지 「m6000 은 학습 범위 안으로(후진 1.0 · 옆 0.5 · 회전 1.2)」).

| 축 | D108 상한(정본) | m6000 학습 표집 B3c(`ex40.yaml`) | **m6000 명령 범위 파일 값** = 작은 쪽 | EX-41 저장본이 배우는 범위(`ex41-fixed5000.yaml` start 블록) | 등급 |
|---|---|---|---|---|---|
| 전진 vx | 1.5 | [0.1, 1.5] (`:116`) | **1.5** | [0.1, 1.5] (`:105~107`) | 결정 · 설정 |
| 후진 vx | 1.3 | [−1.0, −0.2] (`:120`) | **1.0** (학습 상한이 D108 보다 작음) | [−1.3, −0.2] (`:117~119` · D105) → EX-41 저장본 파일은 1.3 | 결정 · 설정 |
| 옆 abs(vy) | 0.5 (학습 넓어지면 0.8) | [0.2, 0.6] (`:121`) | **0.5** (D108 이 학습 상한 0.6 보다 작음) | [0.2, 0.6] (`:120~122`) | 결정 · 설정 |
| 제자리 회전 abs(wz) | 1.2 | [0.3, 1.5] (`:119`) | **1.2** (D108 이 학습 상한 1.5 보다 작음) | [0.3, 1.5] (`:114~116`) | 결정 · 설정 |
| 걸으며 회전 abs(wz) · vx | D108 에 칸 없음 | abs(wz) [0.2, 1.0] · vx [0.3, 0.8] (`:117~118`) | **1.0** (학습 상한, 앱 문서 v0.3 §1.5 로 확정 11/03 21:5x) | 같음 (`:108~113`) | 설정 · 결정 |
| 대각 | D108 에 칸 없음 | abs(vx) [0.3, 0.6] · abs(vy) [0.2, 0.5] (`:122~123`) | 전진 · 옆 상한을 각각 적용 (앱 문서 v0.3 §1.5 로 확정) | 같음 | 결정 |
| 정지 | 0 | (0, 0, 0) · 몫 10 % | 0 | 같음 | 설정 |
| 가속 제한 | 「앱 가속 제한」(수치 없음) | 학습 표집은 명령을 계단식으로 바꿈(가속 제한 없음 · 바뀐 명령은 10 스텝 이력에 섞여 들어감) | 미확인: 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음) | | 미확인 |

- 앱 구현 뜻: 모델별 파일(예 `m6000.ranges.json`) 에 위 「파일 값」 열을 적고 UI · 서버 · 에이전트가 **같은 파일**로 자른다(D108). 평가 칸(W15 13 명령: 전진 0.5 · 1.0 · 후진 0.5 · 1.0 · 옆 ±0.5 · 제자리 ±1.0 …) 은 점수표가 있는 값이고, 상한 근처(전진 1.5 · 회전 1.2) 는 학습은 했으나 점수표로 확인된 값이 아니다.
- `deploy/params/deploy.yaml` 의 `lin_vel_x ±1.5 · lin_vel_y ±1.0 · ang_vel_z ±2.0` 과 `command_filter.py` 의 clip 은 **S1 설계값**(14 §4) 이지 m6000 범위가 아니다(그대로 쓰면 옆 1.0 · 회전 2.0 이 들어간다).
- heading 모드(`forward_fraction 0.5 · gain 0.5 · forward_wz_limit 0.5`, `ex40.yaml:10`) 는 학습 표집 장치이고 앱은 wz 를 직접 준다.

### 3.6 지도 · 깊이 입력

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 높이 지도(정책이 보는 H^b) | **32 × 16 칸 · 5 cm** · yaw 정렬(roll · pitch 는 안 따라감) · 중심이 몸 앞 **+0.3 m**(x −0.475~1.075 · y −0.375~0.375) · 값 h = z_hit − z_base, ±1 m 로 자름 · 못 맞힌 칸 −1 · 배열 ordering **yx** | `env.yaml:570~600`(gt_map_scan offset x 0.3 · resolution 0.05 · size 1.55 × 0.75 · ordering yx) · `start_obs.py:33~37 · :84~89` · `coordinate_metadata.json` grid · `start_perception.py:27~29` | 설정 · 코드 · 실측 |
| 실기에서의 출처 | 정답 광선은 없다 → **복원 지도(TR-Net 출력)** 를 그대로 추정기에 넣거나(복원 모드) 지도 토큰을 뺀다(끔 모드). 지도를 앱이 따로 만들어 넣는 경로는 학습에 없다 | `start_perception.py:325~332` | 코드 |
| 깊이 카메라(D435i 모사) | 60 × 60 · `distance_to_image_plane`(m) · **10 Hz** · 정책에는 **1 프레임(0.1 s) 지연** 된 최근 2 프레임 · 장착 base 기준 (0.25, 0, 0.12) m · 아래로 **35°**(쿼터니언 (0.9537, 0, 0.3007, 0)) · 내부 행렬 fx 55.9 · fy 54.1 · cx = cy = 30(가로 반각 atan(30/55.9) = 28.2°, 세로 29.0°, 계산) | `env.yaml:494~523`(update_period 0.1 · offset · focal 24 · aperture 25.76/26.62 · 60 × 60) · `depth_cam_cfg.py:16~24` · `start_perception.py:34~35 · :66~67`(depth_tick 5 · delay 1) | 설정 · 코드 · 계산 |
| 깊이 정규화 | (d − 0.2)/2.8 → [0, 1] 로 자름 · 미검출(inf · nan · 3 m 초과) = **1.0** · 0.3 m 미만은 무효(inf) | `depth_aug.py:16 · :30~33 · :23 · :75` · `coordinate_metadata.json` depth near 0.2 far 3.0 | 코드 · 실측 |
| 학습 전용 증강 | 잡음 σ 5 mm · Perlin 구멍 U[0, 0.4] · 모양 가림. 실기는 끔 | `depth_aug.py:20~24 · :68~80` | 코드 |
| 정책 입력이 아닌 것 | `height_scanner`(0.1 m · 1.6 × 1.0 · xy) 는 종료 조건 `foot_below_ground` 용 · 발 지도 100(`foot_scan_0~3`) · `gt_feet` · `base_vel` · `contacts` 는 critic(664) 전용 | `env.yaml:351~381 · :2259~2296` · `start_runner.py:186~199` | 설정 · 코드 |
| 지도 모드 셋(D103 · 팀장 11/02 21:1x 요지) | **인터페이스는 셋 모두**(정답 · 복원 · 끔) 를 받는다. **실기**는 정답 광선이 없으므로 **복원 · 끔** 둘만 쓴다. **시뮬 트윈**(앱 MuJoCo) 은 **정답 지도도** 넣는다(앱 광선으로 32 × 16 을 만들어 `gt_map` 입력에, §5a 6 단계). 학습은 `p_map_off 0.1` 로 끔을 섞었다 | `agent.yaml:68` · WORKLIST D103 · lead 21:2x | 설정 · 결정 |

### 3.7 좌표계 · 단위 한 줄

몸 틀 x 앞 · y 왼쪽 · z 위(Isaac Lab · `coordinate_metadata.json` root_quaternion "wxyz, world"). 쿼터니언은 (w, x, y, z). 각도 rad · 속도 m/s · rad/s · 거리 m. 미확인: SDK IMU 의 gyro 축 · 쿼터니언 순서가 같은지 · 정해질 때까지 start 는 웹 시뮬 전용(실기 노드가 붙을 때 대조).

## 4. 지금 문서 · 코드와 어긋나는 자리 (lead 가 고칠 것)

| # | 어디 | 지금 | 맞는 값 | 근거 |
|---|---|---|---|---|
| ① | QA-EXPLAINERS 「AME-2 앱 대조 확인」 「관절 순서: 학습 실제 순서는 미확인」 | 미확인 | **확인됨**: hip 4 → thigh 4 → calf 4 · FL FR RL RR(앱 `ame2-adapter.js` 의 FL FR RL RR 「hip → thigh → calf」 가정과 **다르다**: 앱은 다리 단위, 학습은 관절 종류 단위) | 이 run `coordinate_metadata.json` joint_names |
| ② | APP-INTEGRATION-NOTES §5 명령 범위 표(전진 0.3~1.5 · 옆 0.2~0.5 · 제자리 0.5~1.2 · 걸으며 0.2~0.5) | B0 값(`ex40.yaml:43~48`) | **고침(v0.2 이 커밋)**: D108 · B3c · m6000 파일 값 · EX-41 네 열(§3.5 와 같은 값) | `ex40.yaml:116~123` · WORKLIST D108 |
| ③ | `deploy/export.py` · `deploy.yaml` · `obs.py` | S1-blind 495 입력 · actor 만 | m6000 은 96 입력 + 지각 모듈 · GRU 상태 둘 · 깊이 버퍼 → 새 내보내기 | `export.py:10` · `start_policy.py:1` |
| ④ | QA 「지각 추정값 51 개」 의 나열 순서(v · z · zb · zf) | 뜻 설명 | 코드 순서 z · v · zf · zb | `start_perception.py:355` |
| ⑤ | APP-INTEGRATION-NOTES §3 「몸감각 이력 10 × 45 · 첫 걸음은 리셋 때 채움」 | 같음 | 같음(확인) · 추가: 명령 3 이 이력 안에 포함 | `start_perception.py:33 · :296~312` |

## 5. ONNX 분할 안 (scripter 참고 · 결정 아님)

| 안 | 그래프 | 입력 | 출력 | 장단 |
|---|---|---|---|---|
| (가) 한 그래프 | 지각 + actor | o45(1) · hist 10 × 45 · depth2 (2, 60, 60) · h_prop 128 · h_terr 128 · tick(0/1) · map_off(0/1) | a 12 · h_prop′ · h_terr′ · 복원 지도 32 × 16(표시용) · v 3(표시용) | 호출 한 번 · 상태는 앱이 들고 다님. GRUCell · TransformerEncoder · ConvTranspose 변환 시험 필요 |
| (나) 둘 | TR-Net / (추정기 + actor) | 위를 둘로 | | 끔 모드에서 TR-Net 생략 가능 · 10 Hz 와 50 Hz 를 나눠 부름 |

공통: opset 17(기존 `export.py:33`) · 배포 추론은 z = mu · 관측 정규화 없음 · 입력 순서는 §3.4 · est 순서는 §2 · 리셋 때 h 둘 0 · 이력은 첫 관측 복사 · 깊이 버퍼는 첫 프레임 복사(`init_state :272~280` · `reset_envs :285~291` 과 같게). 내보낸 그래프는 **같은 입력에 PyTorch 와 같은 출력**(기록 `training_trace` 의 저장된 입력으로 비교, `coordinate_metadata.json` depth.stored 「실제 정규화된 지각 입력」) 으로 확인한다.

## 5a. ONNX 받아 쓰는 법 (AME-2 실험 팀원도 따라 하게 · 팀장 11/02 21:1x 요지)

(v0.2 때 쓴 절. ONNX 는 v0.3 에 나왔고 실제 입출력 이름은 이 절 끝 「v0.3 · 실제로 내보낸 이름」 칸과 `../HANDOFF-APP-DEVELOPER.md` §1.4 가 최종이다. 아래 1) 표의 이름은 옛 이름이다.) 숫자는 전부 §0a · §3 의 설정값이다.

**0) 받을 것 셋.** `m6000_perception_actor.onnx`(§5 (가) 한 그래프 안 기준) · `contract.json`(이 문서 §9 기계 블록과 같은 내용 + 입출력 이름) · 이 문서. 받자마자 `sha256` 을 §1 과 대조한다.

**1) 입출력(옛 이름 · 최종 이름은 이 절 끝 v0.3 칸).**

| 방향 | 이름(옛) | 모양 · 형 | 뜻 |
|---|---|---|---|
| 입력 | `obs45` | [1, 45] float32 | §3.4 순서의 몸감각(배율 1 · 자르기 없음) |
| 입력 | `hist` | [1, 10, 45] float32 | 직전 10 스텝의 `obs45`(가장 오래된 것이 앞) |
| 입력 | `depth` | [1, 2, 60, 60] float32 | 10 Hz 깊이 2 프레임, (d − 0.2)/2.8 로 [0, 1], 미검출 1.0, 1 프레임 지연 규칙(§3.6) |
| 입력 | `h_prop` · `h_terr` | [1, 128] float32 둘 | GRU 상태 둘. 처음 0 |
| 입력 | `depth_tick` | [1] (0/1) | 이번 스텝에 새 깊이 프레임이 들어왔나(5 스텝마다 1) |
| 입력 | `map_mode` | [1] (0 복원 · 1 끔 · 2 정답) | 실기는 0 · 1 만. 2 는 시뮬 트윈 전용이고 그때 `gt_map` 을 같이 준다 |
| 입력(선택) | `gt_map` | [1, 512] float32 | 32 × 16 정답 높이 지도(§3.6 격자 · ordering yx · 미검출 −1). `map_mode` 2 일 때만 |
| 출력 | `action` | [1, 12] float32 | a(Isaac 순서 · 아직 자르기 · 배율 전) |
| 출력 | `h_prop_next` · `h_terr_next` | [1, 128] 둘 | 다음 스텝에 그대로 되먹임 |
| 출력(표시용) | `recon_map` | [1, 32, 16] | TR-Net 복원 지도(앱 화면에 그려 보기) |

**2) 매 20 ms 한 번, 이 순서로.**
1. 센서 읽기: IMU 각속도 3(몸 틀 rad/s) · 몸 쿼터니언(w, x, y, z) → 중력 방향 3(`deploy/obs.py:16~22` 식) · 명령 3(vx, vy, wz, §3.5 파일 값 안으로 자른 뒤) · 관절각 12 · 관절 속도 12 를 **SDK 순서에서 Isaac 순서로 재배열**(§0b) · 관절각에서 기본 관절각을 뺌.
2. `obs45` = [각속도 3, 중력 3, 명령 3, 관절각 − 기본 12, 관절 속도 12, 직전 `action` 12].
3. `hist` 를 한 칸 밀고 맨 뒤에 `obs45` 를 넣는다(10 개 유지).
4. 깊이: 카메라가 10 Hz 이므로 5 스텝에 한 번 새 프레임. 정책에는 **한 프레임 늦은** 최근 두 장을 준다(§3.6). 새 프레임이 든 스텝만 `depth_tick` 1.
5. ONNX 실행 → `action` · `h_*_next` · `recon_map`.
6. `a = clip(action, −17, 17)` · 목표각(Isaac 순서) = 기본 관절각 + 0.25 × a · 관절 범위 안으로 자름(§3.2a) · **Isaac 순서에서 SDK 순서로 재배열** · LowCmd: q = 목표각, dq = 0, kp = 25, kd = 0.5, tau = 0.
7. 다음 스텝을 위해 직전 `action` 에 자르기 전 `action` 을 저장(§3.3 기록 행: 학습 관측의 `last_action` 은 자르기 · 배율 전 값), `h_*` 되먹임.

**3) 시작 때.** `hist` 10 칸을 첫 `obs45` 로 채운다(학습 리셋과 같음, `start_perception.py:296~312`). `h_prop` · `h_terr` 0. 깊이 두 장은 첫 프레임 복제. 명령 (0, 0, 0) 으로 2~3 초 서 있게 한 뒤 명령을 올린다(미확인: 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음)).

**4) 코드 뼈대.** 브라우저(onnxruntime-web, D107): `const s = await ort.InferenceSession.create(url); const out = await s.run({obs45: new ort.Tensor('float32', o, [1,45]), hist: …, depth: …, h_prop: …, h_terr: …, depth_tick: …, map_mode: …});` 파이썬(로봇 쪽 컴퓨터, onnxruntime): `sess = ort.InferenceSession(path); out = sess.run(None, {"obs45": o[None].astype(np.float32), …})`. 두 곳 모두 입력 이름은 `contract.json` 에서 읽고 코드에 박지 않는다.

**5) 맞는지 확인(답을 아는 입력으로 먼저).**
- 순서 시험: §0b 의 기본 자세 시험 벡터. 기본 자세에서 `joint_pos_rel` 전부 |값| < 0.05.
- 같은 입력 같은 출력: scripter 가 ONNX 와 함께 주는 「Isaac 기록 한 토막」(`deploy/record_isaac.py` 꼴: obs45 · hist · depth · h · action 몇 스텝) 을 넣어 `action` 차이 최대 1e−4 이하(**가정** 허용치 · float32).
- 정지 시험: 명령 0 · 평지에서 30 초 서 있고 몸 높이가 0.25 m 아래로 안 내려감(종료 조건 `foot_below_ground 0.25` 에서 가져온 **가정** 문턱).
- 모드 시험: `map_mode` 0 과 1 에서 둘 다 유한한 출력 · 1 일 때 `depth` 를 0 으로 바꿔도 출력이 같음(끔 모드는 지도 토큰을 쓰지 않는다).

**6) 시뮬 트윈에서 정답 지도 모드(`map_mode` 2).** 앱 MuJoCo 에서 몸 중심 앞 +0.3 m 를 중심으로 x −0.475 ~ +1.075 · y ±0.375 의 32 × 16 격자(5 cm) 에 **yaw 만 정렬**한 수직 광선을 **몸 위 20 m 에서 아래로** 쏴 높이를 구하고, 몸 높이 기준 상대값으로 `gt_map` 512 를 만든다(ordering yx · 미검출 −1, `env.yaml:570~600`). 광선 시작 높이가 낮으면 높은 단이 빠진다(APP-INTEGRATION-NOTES §4 12 항).

**v0.3 · 실제로 내보낸 이름(위 1)의 옛 이름을 대신함 · 최종).** scripter 34982e13 이 내보낸 묶음 `D:/mai-tmp/scripter/w89_export/`: 파일 둘 `ex40_m6000_map_on.onnx`(sha 81c7e079…) · `ex40_m6000_map_off.onnx`(sha 5d1b7bf3…), 입력 9 = `obs45 · hist · depth2 · h_prop · h_terr · depth_tick · first_after_reset · use_gt · gt_map`, 출력 4 = `action · h_prop_next · h_terr_next · recon_map`. 지도 모드는 입력 `map_mode` 가 아니라 **파일 선택(on/off) + `use_gt`**(on 에서 false = 복원, true = 진단용 정답). 행동 자르기 ±17 과 기본 + 0.25 × a 는 ONNX 밖. 앱 실행기(`mobile/sim/policy-onnx.js:21~35` @d9b6f382)는 모든 입력을 float32 로 만들고 `contract.action` 출력 하나만 돌려준다: **상태 출력(h_*_next)을 되먹이는 경로가 없어 m6000 은 지금 앱에서 못 돈다.** 플래그 입력도 float32 [1] 로 맞춰야 한다.

**7) 하지 말 것.** AME-2 adapter 의 관측 49 열 · 목표 입력 · 지도(29×13×3)를 재사용하지 않는다(관절 순서는 같다, §0b v0.3)(우리 모델은 45 + 지각이고 명령은 속도 3). S1 `deploy/export.py`(495 입력) 로 내보낸 파일을 이 문서의 입력으로 부르지 않는다(§4 ③).

## 6. 결정 물음 (모두 닫힘)

| 번호 | 물음 | 답 | 누가 |
|---|---|---|---|
| W89-1 | APP-INTEGRATION-NOTES §5 명령 범위 갱신 | **닫힘**(lead 20:4x: B0 → B3c 실제 값 · 팀장 D108 정본): §5 표를 D108 · B3c · m6000 파일 값 · EX-41 네 열로 바꿈(이 커밋) | lead · 팀장 |
| W89-2 | 넘기는 지도 모드 | **닫힘**(팀장 11/02 21:1x 요지): 인터페이스는 셋, 실기는 복원 · 끔, 시뮬 트윈은 정답도(§3.6) | 팀장 |
| W89-3 | 실기 한계(관절 각 · 토크 · 속도) 공식 값 · IMU 축 · 카메라 장착 | **닫힘(물음)** · 공식 제품면 · 공식 GitHub 두 파일로 대조표 §3.2a. 미확인: 실기 SDK 가 거는 calf 토크 · 속도 한계와 IMU 축 · 카메라 장착 · 정해질 때까지 학습 값(45.43 N·m · 15.7 rad/s)을 넘지 않게 실기 노드가 자른다(실기 담당이 11/9 전후 LowState 로 잼) | lead → 실기 담당 |
| W89-4 | 넘기는 시점 | **닫힘**: 11/03 lab PR #571 로 전달 | 팀장 |

## 7. 안 한 것 · 미확인

- 하지 않은 것: ONNX 내보내기 · 앱(foothold-app) 코드 열기 · 실기 노드 · 저장본 키 이름 열기 · GPU.
- 미확인: 저장본 안 지각 모듈 키 이름 · 실기 모터 한계 · SDK IMU 축 · 카메라 실제 장착 · 정해질 때까지 start 는 웹 시뮬 전용이고 실기 노드는 학습 값을 넘지 않게 자른다 · EX-40 실행 코드와 c6fff190 사본의 줄 번호 일치(`git/` · `source_dirty.diff` 대조 안 함).
- 등급 주의: §3 의 값은 설정 파일 줄을 그대로 옮긴 것이고 m6000 이 그 값으로 **잘 걷는지**는 이 문서의 물음이 아니다(점수표 · 영상은 C층 · EX-41 보고).
- v0.2 에서 안 한 것: 앱 코드(`ame2-adapter.js` · `policy-adapters.js`) 를 열지 않았다(관절 순서 가정은 QA-EXPLAINERS 43 행 · lead 메모 48 행 **읽기**). `unitree_ros` `go2_description` 은 404 로 못 받았다. 두 공식 파일의 calf 토크 · 속도 불일치(45.43/15.7 대 35.55/20.07) 는 어느 쪽이 실기인지 **미확인**으로 남긴다. 걸으며 회전 상한 · 대각 상한은 11/03 앱 문서 v0.3 §1.5 로 확정했고, 가속 제한은 미확인: 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음). ONNX 입출력 이름은 v0.3 에서 실제 이름으로 바뀌었다(§5a 끝).

## 8. 근거 경로

- run: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/`(`params/env.yaml` 2,400 행 · `params/agent.yaml` 68 행 · `model_6000.pt` · `training_trace/coordinate_metadata.json` · `manifest.json`)
- 코드(analyst c6fff190 사본 `D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102/foothold_s2/`): `models/start_perception.py:27~41 · 66~67 · 155~181 · 272~291 · 296~355` · `models/start_policy.py:1~30` · `runners/start_runner.py:186~245` · `sensors/start_obs.py:1~58 · 84~99` · `sensors/depth_cam_cfg.py:16~24` · `sensors/depth_aug.py:16~33` · `commands/mixed_command.py:39 · 90` · `curriculum/ex40.yaml:10 · 34~124` · `robots/go2_params.py:13~50` · `deploy/export.py` · `deploy/obs.py` · `deploy/sdk_joints.py` · `deploy/record_isaac.py:60~85` · `deploy/params/deploy.yaml`
- 문서: WORKLIST 11fdb8e4 131 · 136(D108) · 172 · 283 행 · `inbox/jay/20261101-app/APP-INTEGRATION-NOTES.md` §3 · §5 · `inbox/jay/20261101-ex41/QA-EXPLAINERS.md`
- 웹 · 공식(11/02 21:2x 읽음): [unitree.com/go2 사양표](https://www.unitree.com/go2) · [unitree_mujoco go2.xml](https://github.com/unitreerobotics/unitree_mujoco/blob/main/unitree_robots/go2/go2.xml)(4746f6bc) · [unitree_rl_gym go2.urdf](https://github.com/unitreerobotics/unitree_rl_gym/blob/main/resources/robots/go2/urdf/go2.urdf)(25877c7e) · 받은 사본 `D:/mai-tmp/planner/unitree_dl/` · 학습 URDF `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf:84 · 122 · 160 · 456`

## 9. 기계 블록 (시험 `app_contract_check.py` 가 env.yaml · agent.yaml · ex40.yaml · 기록 파일과 대조)

```json
{"sim_dt": 0.005, "decimation": 4, "depth_update_period": 0.1,
 "joint_names_isaac": ["FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint", "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint", "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint"],
 "default_joint_pos": {".*L_hip_joint": 0.1, ".*R_hip_joint": -0.1, "F[L,R]_thigh_joint": 0.8, "R[L,R]_thigh_joint": 1.0, ".*_calf_joint": -1.5},
 "init_pos_z": 0.4,
 "stiffness": 25.0, "damping": 0.5,
 "effort_limit_hip_thigh": 23.5, "velocity_limit_hip_thigh": 30.0, "effort_limit_calf": 45.43, "velocity_limit_calf": 15.7,
 "action_scale": 0.25, "action_offset": 0.0, "use_default_offset": true, "max_delay_s": 0.015, "clip_actions": 17.0,
 "actor_hidden_dims": [512, 256, 128], "activation": "elu", "actor_obs_normalization": false,
 "force_gt": true, "p_map_off": 0.1, "map_input": "reconstruction", "est_mode": "learned", "critic_mode": "clean52",
 "policy_terms": ["base_ang_vel", "projected_gravity", "velocity_commands", "joint_pos", "joint_vel", "actions"],
 "depth_cam": {"width": 60, "height": 60, "offset_pos": [0.25, 0.0, 0.12], "focal_length": 24.0},
 "gt_map_scan": {"resolution": 0.05, "size": [1.55, 0.75], "offset_x": 0.3, "ordering": "yx"},
 "b3c_ranges": {"forward_vx": [0.1, 1.5], "walk_vx": [0.3, 0.8], "walk_wz_abs": [0.2, 1.0], "spin_wz_abs": [0.3, 1.5], "reverse_vx": [-1.0, -0.2], "side_vy_abs": [0.2, 0.6], "diag_vx_abs": [0.3, 0.6], "diag_vy_abs": [0.2, 0.5]},
 "d108_caps": {"forward_vx": 1.5, "reverse_vx_abs": 1.3, "side_vy_abs": 0.5, "spin_wz_abs": 1.2},
 "app_caps_m6000": {"forward_vx": 1.5, "reverse_vx_abs": 1.0, "side_vy_abs": 0.5, "spin_wz_abs": 1.2, "walk_wz_abs": 1.0},
 "model_sha256": "d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5"}
```

## 10. 앱 최신판 대조 (v0.3 · foothold-app dev `d9b6f382` 2026-11-03 05:32Z · main `6f16be74` 는 AME-2 · ONNX 이전 판이라 dev 기준)

lead 가 gh 로 직접 다시 본 줄: `policy_ranges.py:40~56` · `policy-onnx.js:8~36` · `ame2-adapter.js:1~12`(analyst 사본 135a8469). 나머지는 lead 하위 조사(gh 읽기)이고 줄 번호는 @d9b6f382.

| 이 문서 자리 | v0.2 값 | 앱 최신 | 판정 | 받는 쪽이 할 일 |
|---|---|---|---|---|
| §0b 관절 순서 | AME-2 adapter 다리 단위 | 두 adapter 모두 hip4 → thigh4 → calf4 (`ame2-adapter.js:3~9` · `policy-adapters.js:4~5` · `docs/spec/11-POLICY-ADAPTER.md:255~277`) | 문서가 틀림 → v0.3 고침 | 없음(SDK 쪽 순열만 주의) |
| §0a · §3.5 · §9 명령 범위 파일(D108) | `m6000.ranges.json` 같은 파일 | `POLICY_RANGES` 에 `foothold-v2` 한 줄(vx 0.4~1.5 · vy 0 · wz ±1), 형식이 전진 전용 | 앱에 없음 | `VelocityRange` 를 후진 하한 · 옆 · 제자리 회전 칸까지 넓히고 m6000 줄(전진 1.5 · 후진 1.0 · 옆 0.5 · 제자리 1.2 · 걸으며 회전 1.0)을 더함 |
| §3.5 앱 실기 표 | (없음) | 서버 실기 ±1.5 m/s · 회전 ±0.5 (`server_drive.py:2~4` · `serverdrive.tsx:19~23`) · 폰 quantize (0,0,0)·(0.6,0,0)·(0.6,0,±0.5) (`safety/core.py:90~103`) | 앱이 바뀜 · Unitree Sport Move 용 | RL 정책 범위와 섞지 않음 |
| §3.5 가속 제한 | 미확인 | `main.js` · `sim.js` · `safety/core.py` 에 시간 가속 제한 없음(그 파일 범위에서만 확인) | 앱에 없음 | 미확인: 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음) |
| 조이스틱 | (없음) | foothold-v2 `joystickScale [1, 0.5, 1]` · `inRange` (`policy-adapters.js:28~29`) | 문서에 없음 | m6000 adapter `command` 에 kind `body_velocity` · axes · trainingRanges · joystickScale · 옆 · 후진 · 회전 허용 inRange 선언 |
| §3.6 지도 모드 셋 | 인터페이스 셋 | 높이 입력은 adapter 마다 고정(foothold-v2 187 칸 · AME-2 29×13×3) · 모드 전환 · 깊이 입력 없음 | 앱에 없음 | 정답 32×16 은 `makeTerrainSampler` 공유로 새로, 복원 · 끔은 깊이 60×60 생성부터 |
| START / m6000 adapter | D144 뒤 | `policy-adapters.js:2` 「START remains undefined」 · 등록 둘(foothold-v2 · ame2-demo) | 아직 없음 | 이 문서가 spec 11 §3 START 열의 입력 |
| §0a 50 Hz | 0.005 × 4 | `timing {physicsDt .005, decimation 4, policyDt .02}` · 20 ms 넘긴 추론은 버리고 물리를 멈춤 | 같음 | 없음 |
| §0a · §3.2 토크 | calf 45.43 / 15.7 | foothold-v2 설정은 12 관절 모두 23.5 / 30 (`policy-adapters.js:26` · `sim.js:17~22`), 관절별 곡선은 `action.torque` 함수가 있을 때만 | 앱이 다름 | m6000 adapter 는 calf 를 `action.torque` 로 따로. foothold-v2 설정을 복사하면 calf 가 23.5 로 잘림 |
| §0a · §3.3 행동 자르기 ±17 | ±17 | 앱 공통에는 목표각 자르기(AME-2 `targetClip`)뿐 | 앱에 없음 | adapter 에서 a 를 ±17 로 자름 |
| §3.3 지연 | 0~15 ms DR | foothold-v2 지연 없음 · AME-2 만 0~4 물리 스텝 | 선택 | 배포 기본 0 |
| §5a ONNX | contract.json · v0.3 실제 이름 | 앱에 contract.json 소비자 없음 · adapter `onnx {file, sha256, inputs[{name,dims}], outputs[{name,dims,type}], action}` 로 받음 · float32 만 · 출력 하나만(`policy-onnx.js:8~36`) · 자산은 `FH_POLICY_ONNX_SRC` 에 두고 커밋 안 함 · parity 1e−4 · f32 JS 되돌림 경로 요구(spec 11:384~416) | 문서가 앱과 안 맞음 · **상태 되먹임 불가** | 앱 실행기에 상태 입출력 되먹임을 더하거나(현민), m6000 을 상태 없는 그래프로 바꿀 수 없으므로 실행기 확장이 먼저. f32 JS 되돌림(GRU · transformer)은 팀장 · 현민 결정 |
| 새 앱 문서 | (없음) | `docs/AME2-PROVENANCE.md` · `mobile/scripts/ame2-training-contract.md` · `docs/POLICY-PROVENANCE.md` · `docs/spec/11-POLICY-ADAPTER.md` v0.9(§9 AME-2 · §10 새 모델 절차) · `docs/spec/DRIVE-MODES-VALIDATION.md` | 앱이 바뀜 | §8 근거에 더함 |

**정한 것(11/03):** (1) 앱 ONNX 실행기에 GRU 상태 되먹임을 **넣는다**(현민 님) (2) spec 11 의 「f32 JS 되돌림 경로」 요건은 start 에 **걸지 않는다**(ONNX 만, parity 로 대신) (3) 미확인: 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음).
