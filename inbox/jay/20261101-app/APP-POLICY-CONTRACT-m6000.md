> 분류: A/정책학습 · 앱 전달 조건표 초안 (W89 · D144 · m6000 기준)
> 작성: planner (Claude Fable 5.1) · 2026-11-02 20:5x v0.1 (lead 20:4x 대기열 (3): 「W89 앱 조건표 초안, m6000 기준 · ONNX 는 scripter 가 뒤에 · 각 값에 m6000 env.yaml/agent.yaml 줄 번호」)
> 근거: EX-40 실행 폴더 `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/`(`params/env.yaml` · `params/agent.yaml` · `model_6000.pt` · `training_trace/coordinate_metadata.json`, 전부 직접 읽음) · 코드 `foothold_s2`(analyst c6fff190 사본, 읽기 전용: `models/start_perception.py` · `models/start_policy.py` · `runners/start_runner.py` · `sensors/start_obs.py` · `sensors/depth_cam_cfg.py` · `sensors/depth_aug.py` · `commands/mixed_command.py` · `curriculum/ex40.yaml` · `robots/go2_params.py` · `deploy/{export.py,obs.py,sdk_joints.py,record_isaac.py,params/deploy.yaml}`) · WORKLIST 11fdb8e4 D103(131 행) · D144(172 행) · W89(283 행) · `inbox/jay/20261101-app/APP-INTEGRATION-NOTES.md` §3 · §5 · `QA-EXPLAINERS.md` 「AME-2 앱 대조 확인」
> 요지: 앱(foothold-app) 과 실기 노드가 m6000 정책을 그대로 돌리려면 맞춰야 하는 조건을 한 표로 모았다. 정책은 actor MLP 하나가 아니라 **지각(TR-Net · I-E 추정기, GRU 둘) + actor** 이고 actor 입력 96 = 몸감각 45 + 추정 51(**z 16 · v 3 · zf 16 · zb 16 순서**) 이다. 50 Hz · Kp 25 · Kd 0.5 · 행동 = 기본 자세 + 0.25 × a · 기본 자세 hip ±0.1 / 앞 thigh 0.8 · 뒤 1.0 / calf −1.5 · Isaac 관절 순서 hip 4 → thigh 4 → calf 4(FL FR RL RR, **이 run 의 training_trace 기록으로 확정**) · 토크 한계 hip · thigh 23.5 / calf 45.43 N·m(DCMotor 곡선) · 명령 (vx, vy, wz) 학습 표집 범위는 **B3c 표**(전진 0.1~1.5 · 후진 −1.0~−0.2 · 옆 0.2~0.6 · 제자리 회전 0.3~1.5 · 걸으며 회전 0.2~1.0) · 지도 32 × 16 · 5 cm · 중심 x +0.3 · 깊이 60 × 60 · 10 Hz · 1 프레임 지연 · (d − 0.2)/2.8. 저장소의 `deploy/` 묶음(export.py · deploy.yaml) 은 **S1-blind(495 입력) 용**이라 m6000 에는 못 쓰고, APP-INTEGRATION-NOTES §5 의 명령 범위 표는 B0 값이라 B3c 로 갱신해야 한다(어긋남 둘). 넘기는 것은 D144 대로 팀장 결정 뒤.
> 상태: v0.1 · 코드 · GPU · ONNX 내보내기 없음(조건표만) · lead W89-1 · W89-2 대기 · 시험 `app_contract_check.py`(기계 블록 §9 대 env.yaml · agent.yaml · ex40.yaml · 기록 파일 대조)

# m6000 정책을 앱 · 실기에 넘길 때 맞출 조건표 (W89 · D144)

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
- 저장소에 있는 `deploy/export.py` 는 **S1-blind actor(입력 495 = 11 × 45 이력)** 전용이고(`export.py:1 · :10`), `deploy/params/deploy.yaml` · `deploy/obs.py`(HISTORY 11) 도 그 판이다. m6000 에는 새 내보내기(지각 포함 · 상태 입출력) 가 필요하다 → scripter(W89). GRUCell · TransformerEncoder 의 ONNX 변환 가능 여부는 **미확인**(scripter 시험).

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
| 실기 대응 | 실기 모터의 실제 토크 · 속도 한계가 위와 같은지, SDK LowCmd 의 tau 한계를 어디서 거는지는 **미확인**(공식 사양 확인은 lead · 실기 담당) | | 미확인 |

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

### 3.5 명령 범위 (m6000 이 배운 표집 범위 · B3c)

학습 표집기(MixedVelocityCommand, `env.yaml:2351~2373`) 는 단계마다 아래 범위에서 뽑았다. m6000 은 B0~B3c 를 지나왔고 마지막 단계 B3c 의 범위가 가장 넓다.

| 슬롯 | B3c 범위 | 앱 상한 권고(= 학습 상한) | 출처 |
|---|---|---|---|
| 전진 vx | [0.1, 1.5] m/s | 1.5 | `ex40.yaml:116` |
| 걸으며 돌기 vx · abs(wz) | [0.3, 0.8] · [0.2, 1.0] | 이동 중 abs(wz) ≤ 1.0 | `:117~118` |
| 제자리 회전 abs(wz) | [0.3, 1.5] rad/s | 1.5(vx · vy = 0 일 때) | `:119` |
| 후진 vx | [−1.0, −0.2] | −1.0(EX-41 은 −1.3 으로 넓힘, D105 · 그 저장본부터) | `:120` |
| 옆 abs(vy) | [0.2, 0.6] | 0.6 | `:121` |
| 대각 abs(vx) · abs(vy) | [0.3, 0.6] · [0.2, 0.5] | | `:122~123` |
| 정지 | (0, 0, 0) · 몫 10 % | 0 | 설계 §4(읽기) |
| heading 모드 | 학습 표집 장치(`forward_fraction 0.5 · gain 0.5 · forward_wz_limit 0.5`). 앱은 wz 를 직접 준다 | 해당 없음 | `ex40.yaml:10` |

- 평가 칸(W15 13 명령) 은 전진 0.5 · 1.0 · 후진 0.5 · 1.0 · 옆 ±0.5 · 제자리 ±1.0 · 걸으며 … 이라 **평가된 값 ≠ 표집 상한**이다. 상한 근처(전진 1.5 · 회전 1.5) 는 학습은 했으나 점수표로 확인된 값이 아니다(가정: 앱 기본 상한은 평가 칸 값 1.0 · 옆 0.5, 「최대」 는 표집 상한).
- `deploy/params/deploy.yaml` 의 `lin_vel_x ±1.5 · lin_vel_y ±1.0 · ang_vel_z ±2.0` 과 `command_filter.py` 의 clip 은 **S1 설계값**(14 §4) 이지 m6000 표집 범위가 아니다.

### 3.6 지도 · 깊이 입력

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 높이 지도(정책이 보는 H^b) | **32 × 16 칸 · 5 cm** · yaw 정렬(roll · pitch 는 안 따라감) · 중심이 몸 앞 **+0.3 m**(x −0.475~1.075 · y −0.375~0.375) · 값 h = z_hit − z_base, ±1 m 로 자름 · 못 맞힌 칸 −1 · 배열 ordering **yx** | `env.yaml:570~600`(gt_map_scan offset x 0.3 · resolution 0.05 · size 1.55 × 0.75 · ordering yx) · `start_obs.py:33~37 · :84~89` · `coordinate_metadata.json` grid · `start_perception.py:27~29` | 설정 · 코드 · 실측 |
| 실기에서의 출처 | 정답 광선은 없다 → **복원 지도(TR-Net 출력)** 를 그대로 추정기에 넣거나(복원 모드) 지도 토큰을 뺀다(끔 모드). 지도를 앱이 따로 만들어 넣는 경로는 학습에 없다 | `start_perception.py:325~332` | 코드 |
| 깊이 카메라(D435i 모사) | 60 × 60 · `distance_to_image_plane`(m) · **10 Hz** · 정책에는 **1 프레임(0.1 s) 지연** 된 최근 2 프레임 · 장착 base 기준 (0.25, 0, 0.12) m · 아래로 **35°**(쿼터니언 (0.9537, 0, 0.3007, 0)) · 내부 행렬 fx 55.9 · fy 54.1 · cx = cy = 30(가로 반각 atan(30/55.9) = 28.2°, 세로 29.0°, 계산) | `env.yaml:494~523`(update_period 0.1 · offset · focal 24 · aperture 25.76/26.62 · 60 × 60) · `depth_cam_cfg.py:16~24` · `start_perception.py:34~35 · :66~67`(depth_tick 5 · delay 1) | 설정 · 코드 · 계산 |
| 깊이 정규화 | (d − 0.2)/2.8 → [0, 1] 로 자름 · 미검출(inf · nan · 3 m 초과) = **1.0** · 0.3 m 미만은 무효(inf) | `depth_aug.py:16 · :30~33 · :23 · :75` · `coordinate_metadata.json` depth near 0.2 far 3.0 | 코드 · 실측 |
| 학습 전용 증강 | 잡음 σ 5 mm · Perlin 구멍 U[0, 0.4] · 모양 가림. 실기는 끔 | `depth_aug.py:20~24 · :68~80` | 코드 |
| 정책 입력이 아닌 것 | `height_scanner`(0.1 m · 1.6 × 1.0 · xy) 는 종료 조건 `foot_below_ground` 용 · 발 지도 100(`foot_scan_0~3`) · `gt_feet` · `base_vel` · `contacts` 는 critic(664) 전용 | `env.yaml:351~381 · :2259~2296` · `start_runner.py:186~199` | 설정 · 코드 |
| 지도 모드 셋(D103) | 정답(시뮬 전용) · 복원 · 끔(학습 `p_map_off 0.1`). 앱 UI 의 세 모드 가운데 실기는 둘 | `agent.yaml:68` · WORKLIST D103 | 설정 · 결정 |

### 3.7 좌표계 · 단위 한 줄

몸 틀 x 앞 · y 왼쪽 · z 위(Isaac Lab · `coordinate_metadata.json` root_quaternion "wxyz, world"). 쿼터니언은 (w, x, y, z). 각도 rad · 속도 m/s · rad/s · 거리 m. SDK IMU 의 gyro 축 · 쿼터니언 순서가 같은지는 실기 노드가 대조한다(**미확인**).

## 4. 지금 문서 · 코드와 어긋나는 자리 (lead 가 고칠 것)

| # | 어디 | 지금 | 맞는 값 | 근거 |
|---|---|---|---|---|
| ① | QA-EXPLAINERS 「AME-2 앱 대조 확인」 「관절 순서: 학습 실제 순서는 미확인」 | 미확인 | **확인됨**: hip 4 → thigh 4 → calf 4 · FL FR RL RR(앱 `ame2-adapter.js` 의 FL FR RL RR 「hip → thigh → calf」 가정과 **다르다**: 앱은 다리 단위, 학습은 관절 종류 단위) | 이 run `coordinate_metadata.json` joint_names |
| ② | APP-INTEGRATION-NOTES §5 명령 범위 표(전진 0.3~1.5 · 옆 0.2~0.5 · 제자리 0.5~1.2 · 걸으며 0.2~0.5) | B0 값 | m6000 은 B3c: 전진 0.1~1.5 · 옆 0.2~0.6 · 제자리 0.3~1.5 · 걸으며 0.2~1.0 · 후진 −1.0~−0.2 | `ex40.yaml:43~48`(B0) 대 `:116~123`(B3c) |
| ③ | `deploy/export.py` · `deploy.yaml` · `obs.py` | S1-blind 495 입력 · actor 만 | m6000 은 96 입력 + 지각 모듈 · GRU 상태 둘 · 깊이 버퍼 → 새 내보내기 | `export.py:10` · `start_policy.py:1` |
| ④ | QA 「지각 추정값 51 개」 의 나열 순서(v · z · zb · zf) | 뜻 설명 | 코드 순서 z · v · zf · zb | `start_perception.py:355` |
| ⑤ | APP-INTEGRATION-NOTES §3 「몸감각 이력 10 × 45 · 첫 걸음은 리셋 때 채움」 | 같음 | 같음(확인) · 추가: 명령 3 이 이력 안에 포함 | `start_perception.py:33 · :296~312` |

## 5. ONNX 분할 안 (scripter 참고 · 결정 아님)

| 안 | 그래프 | 입력 | 출력 | 장단 |
|---|---|---|---|---|
| (가) 한 그래프 | 지각 + actor | o45(1) · hist 10 × 45 · depth2 (2, 60, 60) · h_prop 128 · h_terr 128 · tick(0/1) · map_off(0/1) | a 12 · h_prop′ · h_terr′ · 복원 지도 32 × 16(표시용) · v 3(표시용) | 호출 한 번 · 상태는 앱이 들고 다님. GRUCell · TransformerEncoder · ConvTranspose 변환 시험 필요 |
| (나) 둘 | TR-Net / (추정기 + actor) | 위를 둘로 | | 끔 모드에서 TR-Net 생략 가능 · 10 Hz 와 50 Hz 를 나눠 부름 |

공통: opset 17(기존 `export.py:33`) · 배포 추론은 z = mu · 관측 정규화 없음 · 입력 순서는 §3.4 · est 순서는 §2 · 리셋 때 h 둘 0 · 이력은 첫 관측 복사 · 깊이 버퍼는 첫 프레임 복사(`init_state :272~280` · `reset_envs :285~291` 과 같게). 내보낸 그래프는 **같은 입력에 PyTorch 와 같은 출력**(기록 `training_trace` 의 저장된 입력으로 비교, `coordinate_metadata.json` depth.stored 「실제 정규화된 지각 입력」) 으로 확인한다.

## 6. 결정 물음

| 번호 | 물음 | planner 안 | 누가 |
|---|---|---|---|
| W89-1 | APP-INTEGRATION-NOTES §5 명령 범위를 B3c 로 갱신하고, 앱 기본 상한은 평가 칸 값(전진 1.0 · 옆 0.5 · 회전 1.0) · 최대는 표집 상한으로 둘지 | 그렇게(§3.5 가정 줄) | lead |
| W89-2 | 넘기는 모드: 복원만 / 복원 + 끔 | 둘 다(끔은 안전 대비 · D103 세 모드 UI 와 맞음), 정답은 「시뮬 전용」 표시 | lead |
| W89-3 | 실기 모터 한계 · IMU 축 · 카메라 장착(위치 · 35°) 확인 담당 | 실기 담당(11/9 전후) · 카메라는 D435i 구매 뒤 | lead → 팀장 |
| W89-4 | 넘기는 시점 | D144 대로 팀장 결정 뒤(지금 안 넘김) | 팀장 |

## 7. 안 한 것 · 미확인

- 하지 않은 것: ONNX 내보내기 · 앱(foothold-app) 코드 열기 · 실기 노드 · 저장본 키 이름 열기 · GPU.
- 미확인: 저장본 안 지각 모듈 키 이름 · GRU · transformer 의 ONNX 변환 · 실기 모터 한계 · SDK IMU 축 · 카메라 실제 장착 · EX-40 실행 코드와 c6fff190 사본의 줄 번호 일치(`git/` · `source_dirty.diff` 대조 안 함).
- 등급 주의: §3 의 값은 설정 파일 줄을 그대로 옮긴 것이고 m6000 이 그 값으로 **잘 걷는지**는 이 문서의 물음이 아니다(점수표 · 영상은 C층 · EX-41 보고).

## 8. 근거 경로

- run: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/`(`params/env.yaml` 2,400 행 · `params/agent.yaml` 68 행 · `model_6000.pt` · `training_trace/coordinate_metadata.json` · `manifest.json`)
- 코드(analyst c6fff190 사본 `D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102/foothold_s2/`): `models/start_perception.py:27~41 · 66~67 · 155~181 · 272~291 · 296~355` · `models/start_policy.py:1~30` · `runners/start_runner.py:186~245` · `sensors/start_obs.py:1~58 · 84~99` · `sensors/depth_cam_cfg.py:16~24` · `sensors/depth_aug.py:16~33` · `commands/mixed_command.py:39 · 90` · `curriculum/ex40.yaml:10 · 34~124` · `robots/go2_params.py:13~50` · `deploy/export.py` · `deploy/obs.py` · `deploy/sdk_joints.py` · `deploy/record_isaac.py:60~85` · `deploy/params/deploy.yaml`
- 문서: WORKLIST 11fdb8e4 131 · 172 · 283 행 · `inbox/jay/20261101-app/APP-INTEGRATION-NOTES.md` §3 · §5 · `inbox/jay/20261101-ex41/QA-EXPLAINERS.md`

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
 "model_sha256": "d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5"}
```
