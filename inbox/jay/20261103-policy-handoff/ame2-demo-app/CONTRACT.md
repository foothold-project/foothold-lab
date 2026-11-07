> 분류: 가이드
> 작성: 임석헌 · 2026-11-03 19:20
> 근거: run 폴더 `params/env.yaml`(sha256 `08b81523…`) · `params/agent.yaml`(sha256 `ec7e4bd0…`) · 저장본 `model_14999.pt` · 코드 사본 `ame2_spd`(code id a78a734258cf, 학습 전 · 끝 · 11-03 의 코드 manifest 가 같음) · Isaac Lab 2.3.2 원본(팟 `/workspace/isaaclab`, 학습과 같은 판 0.54.2)
> 요지: 앱이 ame2-demo 를 원본과 같게 돌리는 데 필요한 값을 모았다. ONNX 는 원본 `AME2GazeModel.forward` 를 그대로 감싸 내보냈고(층 재구성 없음), 학습 env 에서 기록한 실제 입력 400 스텝에서 PyTorch 와의 action 최대 차이는 **3.6e-06**(기준 1e-4, 통과)
> 상태: v0.1 (AME-2 에이전트 세션) · 팀장 검증 대기 · 지시문 [HANDOFF-AME2-WORKER.md](https://github.com/foothold-project/foothold-lab/blob/main/inbox/jay/20261103-policy-handoff/HANDOFF-AME2-WORKER.md) §1

# AME-2 teacher model_14999 를 앱에 넘길 때 맞출 조건표 (ame2-demo)

등급: **설정**(env.yaml · agent.yaml 줄) · **코드**(학습 코드 사본 · Isaac Lab 원본 줄, `코드확인`) · **실측**(이번에 잰 해시 · 기록, `실측`) · **가정**. §7 에 추가 확인 결과와 남은 `미측정` 항목을 적었다. 같은 출력 확인은 `확인됨`(§2). 코드 경로 약칭: `AME2_models.py` = `rsl_rl/rsl_rl/models/AME2_models.py`, `observations.py` = `go2/ame2_go2/tasks/mdp/observations.py`, `actions.py` · `commands.py` · `curriculums.py` · `events.py` = `go2/ame2_go2/tasks/mdp/` 아래, `go2_actuator.py` · `go2_curve.py` = `go2/ame2_go2/assets/` 아래, `virtual_floor.py` = `go2/ame2_go2/sensors/` 아래, `isaaclab/…` = 팟 `/workspace/isaaclab/source/isaaclab/isaaclab/…`.

## 0a. 앱 개발자가 맨 먼저 볼 값

| 값 | 숫자 | 뜻 한 줄 | 출처 | 등급 |
|---|---|---|---|---|
| **Kp** | **25.0** N·m/rad · 관절 12 모두 | 목표각 - 현재각 에 곱함 | `env.yaml:176` · `:194` | 설정 |
| **Kd** | **0.5** N·m·s/rad · 관절 12 모두 | 관절 속도에 곱함(목표 속도 0) | `env.yaml:177` · `:195` · `isaaclab/actuators/actuator_pd.py:190~193` | 설정 · 코드 |
| **토크 한계** | Go2HV 곡선: hip · thigh 구동 **20.2** / 제동 **23.4** N·m, 13.5 rad/s 까지 평탄 → 30.0 rad/s 에서 0. calf 구동 **38.73** / 제동 **44.86** N·m, 7.04 → 15.65 rad/s | 구동(토크와 속도 부호 같음) 과 제동의 상한이 다르고 빠를수록 줄어듦 | `env.yaml:166~203` · `go2_curve.py:6~16` · `go2_actuator.py:29~48` | 설정 · 코드 |
| **제어 주기** | **50 Hz** = 물리 dt 0.005 s × decimation 4 | ONNX 한 번 = 관절 목표 한 번 | `env.yaml:21` · `:84` · 기록 step_dt 0.02 | 설정 · 실측 |
| **행동 식** | 목표각 = **기본 관절각 + 0.25 × a** (a 는 ONNX `action` 그대로, runner 자르기 없음) | env 의 목표각 자르기 ±100 rad 는 실제로 걸리지 않음 | `env.yaml:1588~1597` · `agent.yaml:13` · `isaaclab/envs/mdp/actions/joint_actions.py:169~178 · 194~195` | 설정 · 코드 |
| **기본 관절각** | `[0.1, -0.1, 0.1, -0.1, 0.8, 0.8, 1.0, 1.0, -1.5, -1.5, -1.5, -1.5]` (관절 순서 §0b) | 위 식의 기준, 관측 `joint_pos_rel` 도 여기서 뺌 | `env.yaml:154~159` · 기록 env 의 `default_joint_pos` | 설정 · 실측 |
| **행동 지연** | **물리 스텝 0~4**(0~20 ms), 에피소드마다 로봇별로 뽑음 | 학습은 이 범위의 지연에 견디게 됨. 앱이 넣지 않아도 됨(지연 0 도 학습 범위 안) | `env.yaml:1598~1600` · `actions.py:45~50 · 62~72` · `isaaclab/envs/manager_based_rl_env.py:182~185` | 설정 · 코드 |
| **입력 · 출력** | 입력 `prop` [1,49] · `mapping` [1,29,13,3], 출력 `action` [1,12] · `gaze_r` [1,2] (진단). 모두 float32 · batch 1 · 상태 없음 | 매 스텝 독립, 되먹일 상태는 직전 action 하나(prop 안) | ONNX · `AME2_models.py:24 · 581~634` | 실측 · 코드 |
| **명령** | 목표 위치 `[x, y, sin e, cos e]` · 몸 yaw 틀 · **2 m 넘으면 2 m 로 줄이고 e 를 무작위로 바꿈** | 속도 명령이 아님 | `env.yaml:1400~1410` · `observations.py:296~340` | 설정 · 코드 |
| **지도** | 29 × 13 × 3(x, y, z) · 6 cm · x -0.42~1.26 · y ±0.36 · **x 가 바깥 축** · z = 바닥 - 몸 + 0.27, ±1.5 자름 | 정답 지도(시뮬 광선). START 의 32 × 16 높이 1 채널과 뜻이 다름 | `env.yaml:584~618 · 1283~1313` · `observations.py:160~224` | 설정 · 코드 |
| **이름** | format `ame2-demo-onnx/1` · 파일 `ame2-demo.onnx` · 최종 `ame2-oh2l2` | lab README 이름 규칙 | README(11/03 17:0x) | 결정 |
| **ONNX** | `ame2-demo.onnx` 5,038,171 B · sha256 `830595df1e78072c0606b5193d1ba787720ff6777edc7cabe496b8c1a9d25de6` | 앱은 이 sha 가 contract.json · SHA256SUMS 와 같을 때만 씀 | `sha256sum` | 실측 |

## 0b. ⚠ 경고 칸: 관절 순서

**정책 벡터 12(관측 joint_pos · joint_vel · last_action, 출력 action)는 「관절 종류 단위」 다: hip 4 → thigh 4 → calf 4, 다리 FL FR RL RR.** 저장본 `go2_env_state.critic_contract.joint_names` 를 그대로 꺼낸 값이고, 기록 env 의 `robot.joint_names` 와 행동 항의 관절 순서도 같았다(실측).

| 순서 이름 | 벡터 index 0 → 11 | 기본 관절각 |
|---|---|---|
| **Isaac = 정책 입출력** | FL_hip FR_hip RL_hip RR_hip · FL_thigh FR_thigh RL_thigh RR_thigh · FL_calf FR_calf RL_calf RR_calf | `[0.1, -0.1, 0.1, -0.1, 0.8, 0.8, 1.0, 1.0, -1.5, -1.5, -1.5, -1.5]` |
| Unitree SDK 모터 0~11 (참고, m6000 조건표 §0b) | FR(hip thigh calf) · FL · RR · RL | 이 순서로 바꿔 넣어야 함 |

- **확인 시험(기록 env 에서 실측):** 관절을 기본 자세에 정확히 두면 `joint_pos_rel` 최대 |값| = 0.0e+00, 관측 prop[9:21] 최대 |값| = 0.0e+00 (기준 < 0.05, 통과). action 0 을 넣었을 때 목표각 - 기본 관절각 최대 |값| = 0.0e+00.

## 1. 저장본

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 파일 | RunPod `/network-volume/limseokheon/ame2_spd/logs/rsl_rl/go2_gaze_teacher/2026-10-27_15-57-27_nogapst5_vmax12_to15000/model_14999.pt` · 100,274,078 B (lab 에 올리지 않음) | run 폴더 | 실측 |
| sha256 | `8c3be365eeddd136edda31988df7fed96ad6f9f92713490b2d993037bf978d4d` (앱 `docs/AME2-PROVENANCE.md:17` 의 `8c3be365…` 와 같음) | `sha256sum`(11/03) | 실측 |
| 자리 | 이 run 자체 15,000 회 = 처음부터 누적 25,001 회(NoGap 0~9k → KL fp32 9~10k → 쉬운 돌 5 % 10~20k → 목표 이동 보상 상한 v_max 1.2 m/s 20~25k) · task `Ame2-Go2-Gaze-NoGapStones5` | run 폴더 `README.txt`(ame2_spd) · `agent.yaml:5 · 20~22` | 실측 · 설정 |
| 설정 sha256 | env.yaml `08b815230d30…` · agent.yaml `ec7e4bd09c96…` | `sha256sum` | 실측 |
| 학습 코드 | 사본 폴더 `ame2_spd`(git 저장소 아님) = ame2_st 고정 사본(2026-10-27T15:48:32Z) + `run/patch_spd.py`(train.py 만), code id a78a734258cf. go2/ame2_go2 · go2/scripts · rsl_rl/rsl_rl 의 manifest sha256 `19d459da…` 가 학습 전(10-27 15:48Z) · 학습 끝(10-28 03:36Z) · 11-03 모두 같음 | `out/snapshot_manifest.txt` · `out/q/manifest_now.txt` · 11-03 재계산 | 실측 |
| 판 | Isaac Lab 2.3.2(isaaclab 0.54.2 · isaaclab_rl 0.4.7, 버전 관리 없는 설치) · torch 2.7.0+cu128 · rsl_rl = `leggedrobotics/ame2_minimal@8beb9a68` 의 rsl_rl 5.0.0 그대로(§7) · Isaac Sim 5.1(학습 로그) = 5.1.0-rc.19(같은 이미지, §7) | 학습 시작 `pip_freeze.txt` · 팟 `VERSION` | 실측 |
| 저장본 안의 것 | `actor_state_dict`(41 텐서, log_std 포함) · `critic_state_dict` · optimizer · `go2_env_state`(critic_contract · 지형 단계 등) | 저장본을 열어 확인 | 실측 |

## 2. ONNX 에 든 것

| 조각 | 안에 있는 것 | 상태 | 포함 |
|---|---|---|---|
| actor 전체 | prop 인코더 · 전역 CNN · gaze head · 정수 crop · crop 인코더 · MHA · 출력 MLP (§3.7) | 없음 | **포함** |
| 결정적 출력 | 평균 action(`stochastic_output=False`) | | 포함 · log_std 와 표집은 제외 |
| critic | MoE 16 전문가, critic 관측(time_left · height_scanner_critic 등) | | **제외** |
| 학습 잡음 · 지도 드리프트 | prop 균등 잡음 · 지도 xy ±0.001 / z ±0.05 · 센서 드리프트 ±0.04 m | | **제외**(배포 입력에 넣지 않음) |

- 내보내기: 원본 `AME2GazeModel` 을 학습과 같은 방식(`algorithms/ppo.py:629~645`)으로 agent.yaml actor 설정에서 만들고 `actor_state_dict` 를 strict 로 불러(모든 키 일치) `forward` 를 그대로 감쌌다. 진단 출력 `gaze_r` 는 원본 get_latent 가 저장하는 `_last_gaze_r`(`AME2_models.py:602~603`). torch 2.7.0+cu128 · onnx 1.21.0 · `torch.onnx.export(dynamo=False)` · opset 17 · IR 8 · 노드 236 · `onnx.checker` full_check 통과.
- 학습 forward 의 STE crop 은 `hard + (soft - soft.detach())` 라 앞방향 값이 hard crop 과 같다(`AME2_models.py:577~579`). ONNX 안에 GridSample 경로가 남지만 결과에 더해지는 값은 0 이다. 원본 `as_jit` 쌍둥이(`AME2_models.py:1255~1338`) 와의 차이는 합성 입력 0.0, 기록 입력 0.0e+00.
- 원본에는 `as_onnx` 가 없다(`AME2_models.py:225~227` NotImplementedError). 지도 크기 29 · 13 은 그래프 안에서 상수다(`AME2_models.py:605~606`).

| 방향 | 이름 | 모양 · 형 | 뜻 |
|---|---|---|---|
| 입력 | `prop` | [1, 49] float32 | §3.4 순서의 몸감각 |
| 입력 | `mapping` | [1, 29, 13, 3] float32 | §3.6 지도 |
| 출력 | `action` | [1, 12] float32 | a (Isaac 순서, 배율 · 기본각 더하기 전) |
| 출력(진단) | `gaze_r` | [1, 2] float32 | 시선 위치 r ∈ (0,1)². crop 모서리 ox = clamp(round(17 r0), 0, 17), oy = clamp(round(3 r1), 0, 3), 12 × 10 창(`AME2_models.py:530~536 · 605~606`) |

**같은 출력 확인(3단계, parity.json).** 학습 env(task `Ame2-Go2-Gaze-NoGapStones5`, env.yaml 설정 그대로에서 관측 잡음만 끔 · 로봇 2 대) 에서 평지 칸 1 · 계단(stair_up 단계 5) 칸 1 을 각 200 스텝 기록했다. 같은 입력을 원본 PyTorch(CPU float32, 한 스텝씩) 와 ONNX(onnxruntime 1.26.0 CPU) 에 넣은 action 최대 차이: 평지 1.7e-06 · 계단 3.6e-06 (기준 1e-4, **통과**). 참고로 env 안 GPU 출력과 CPU PyTorch 의 차이는 평지 2.6e-04 · 계단 2.8e-04 (GPU 커널 차이, 기준 대상 아님). 평지 칸은 학습 지형 rough 의 기울기 · 거칠기를 0 으로 둔 칸이다(기록용 변경, `env_record.yaml` 에 기록).

## 3. 조건표

### 3.1 제어 주기 · 관절 · 자세

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 물리 dt · decimation | 0.005 s · 4 → 제어 0.02 s(50 Hz) | `env.yaml:21` · `:84` · 기록 physics_dt 0.005 · step_dt 0.02 | 설정 · 실측 |
| 관절 순서 | §0b | 저장본 critic_contract · 기록 env | 실측 |
| 기본 관절각 | L hip +0.1 · R hip -0.1 · 앞 thigh 0.8 · 뒤 thigh 1.0 · calf -1.5 | `env.yaml:154~159` | 설정 |
| 시작 높이 | 0.4 m | `env.yaml:137~140` | 설정 |
| 에피소드 | 16 s | `env.yaml:1834` | 설정 |

### 3.2 PD · 모터

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 토크 식 | τ = Kp (q목표 - q) + Kd (0 - dq), 물리 스텝마다(200 Hz) | `isaaclab/actuators/actuator_pd.py:186~200` | 코드 |
| 모터 자르기 | 구동(τ·dq > 0) 평탄 y1, 제동 y2; limit = 평탄 × clamp((x2 - |dq|)/(x2 - x1), 0, 1); τ = clamp(τ, ±limit) | `go2_curve.py:6~16` | 코드 |
| hip · thigh | y1 20.2 · y2 23.4 N·m · x1 13.5 · x2 30.0 rad/s · armature 0.01 | `env.yaml:167~185` | 설정 |
| calf | y1 38.727 · y2 44.862 N·m · x1 7.0415 · x2 15.6478 rad/s · armature 0.01 | `env.yaml:186~203` | 설정 |
| 학습 무작위화 | Kp · Kd · armature × U(0.85, 1.15) (시작 때) · 마찰 0.3~1.0 · 몸 질량 -1~+3 kg · 질량 중심 ±2 cm | `env.yaml:1602~1756` | 설정 |

### 3.3 행동

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| scale · offset | 0.25 · use_default_offset true(offset = 기본 관절각) | `env.yaml:1594~1597` · `isaaclab/envs/mdp/actions/joint_actions.py:173 · 194~195` | 설정 · 코드 |
| 자르기(env) | 목표각에 ±100 rad (배율 · 기본각 더한 뒤) → 사실상 없음 | `env.yaml:1588~1591` · `joint_actions.py:175~178` | 설정 · 코드 |
| 자르기(runner) | 없음(clip_actions null) | `agent.yaml:13` | 설정 |
| 직전 행동 관측 | **자르기 · 배율 전 raw a** 를 ±50 으로 자른 값. 리셋 직후 0 | `observations.py:276~283` · `isaaclab/managers/action_manager.py:384~386` | 코드 |
| 기록 대조 | prop[33:45] - clip(직전 a, ±50) 최대 0.0e+00 · 목표각 - (기본 + 0.25 a) 최대 0.0e+00 | 3단계 기록 | 실측 |
| 지연 | 물리 스텝 0~4, 에피소드마다 | `env.yaml:1598~1600` · `actions.py:45~50 · 62~72` | 설정 · 코드 |

### 3.4 관측 prop 49 (순서 · 배율 1 · 자르기는 직전 행동만)

| index | 항 | 뜻 · 틀 | 학습 잡음(배포 제외) | 출처 | 비고 |
|---|---|---|---|---|---|
| 0:3 | base_lin_vel | 몸 COM 선속도, 몸 틀 m/s | U(±0.1) | `env.yaml:1326~1338` · `observations.py:40~43` · `isaaclab/assets/articulation/articulation_data.py:1041~1043` | **특권**(실기 직접 측정 불가, 시뮬 트윈은 시뮬 값) |
| 3:6 | base_ang_vel | 몸 각속도, 몸 틀 rad/s | U(±0.2) | `env.yaml:1339~1351` · `observations.py:46~49` | |
| 6:9 | projected_gravity | 몸 틀 중력 방향(서 있으면 (0, 0, -1)) | U(±0.05) | `env.yaml:1352~1364` · `observations.py:52~55` | |
| 9:21 | joint_pos_rel | q - 기본 관절각 | U(±0.01) | `env.yaml:1365~1377` · `observations.py:69~72` | |
| 21:33 | joint_vel_rel | dq | U(±1.5) | `env.yaml:1378~1390` · `observations.py:78~81` | |
| 33:45 | last_action | clip(직전 raw a, ±50) | 없음 | `env.yaml:1391~1399` · `observations.py:276~283` | |
| 45:49 | pose_command | [x, y, sin e, cos e] (§3.5) | 없음 | `env.yaml:1400~1410` · `observations.py:296~340` | |

- 순서는 env.yaml 항 순서이고, 기록 env 에서 몸 상태와 대조했다(잡음 끔): lin_vel 0.0e+00 · ang_vel 0.0e+00 · gravity 0.0e+00 · joint_pos_rel 0.0e+00 (실측). 잡음은 그룹 `enable_corruption` 이 참일 때만 붙는다(`env.yaml:1323` · `isaaclab/managers/observation_manager.py:400~407 · 546~548`). 이력 없음(history_length 0) · 관측 정규화 없음(`agent.yaml:6`).
- actor 입력 그룹 순서는 agent.yaml `obs_groups.actor = [teacher_mapping, teacher_prop]`(`agent.yaml:7~10`) 이고 ONNX 는 이름으로 받는다.

### 3.5 명령 (목표 위치)

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 종류 | `goal_pose_xy_sincos`: [x, y, sin e, cos e] | `observations.py:296~340` | 코드 |
| x, y | 목표 위치 - 몸 위치를 몸 yaw 로만 돌린 틀(x 앞 · y 왼쪽) | `isaaclab/envs/mdp/commands/pose_2d_command.py:119~122` | 코드 |
| e | wrap(목표 heading(세계) - 몸 heading(세계)) | `pose_2d_command.py:122` | 코드 |
| 2 m 규칙 | ‖(x, y)‖ > 2.0 이면 (x, y) 를 길이 2.0 으로 줄이고 e 를 U(-π, π) 로 바꿈(매 제어 스텝 새로 뽑음) | `env.yaml:1404` · `observations.py:310~328` | 설정 · 코드 |
| 재표집 | 16.01 s(에피소드 16 s 보다 길어 사실상 에피소드마다 한 번) | `env.yaml:2457~2459` · `:1834` | 설정 |
| 목표 heading | 세계 틀 U(±π/3). 시작 yaw 는 ±π(커리큘럼) 라 e 는 모든 각도 | `env.yaml:2464~2466 · 2429~2436` · `commands.py:77~80` | 설정 · 코드 |
| 목표 위치 | 지형 평평한 칸 중 앞쪽 45° 원뿔 안(커리큘럼 10° → 45°) | `env.yaml:2437~2445 · 2504` · `commands.py:43~55` | 설정 · 코드 |
| 속도 | 이 판은 목표 이동 보상 상한 v_max 1.2 m/s 로 학습 | run `README.txt` · `--move2goal_vmax 1.2` | 실측 |

### 3.6 지도 (정답 지도)

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 모양 · 축 | [29, 13, 3] · 칸 [i, j] = (x_i, y_j, z_ij) · **i = x(바깥, 29)** · j = y(안, 13) | `env.yaml:604~614`(ordering yx) · `isaaclab/sensors/ray_caster/patterns/patterns.py:43~53` · `observations.py:195~222` | 설정 · 코드 |
| 간격 · 범위 | 0.06 m · x -0.42~1.26 · y -0.36~0.36 (격자 ±0.84 · ±0.36 에 센서 offset x 0.42) | `env.yaml:592~596 · 606~609` | 설정 |
| x, y 채널 | 상수 격자(학습 잡음 ±0.001 제외). float32 값은 contract.json `map.grid_x_float32` · `grid_y_float32`(기록 env 값) | `observations.py:184~206` · 기록 | 코드 · 실측 |
| 정렬 · 원점 | yaw 정렬(광선 수직, 격자만 몸 yaw 로 회전) · 원점 = 몸(base 링크) 위치 | `env.yaml:586 · 603` · `isaaclab/sensors/ray_caster/ray_caster.py:241~248 · 274~279` | 설정 · 코드 |
| 광선 | 몸 위 **20 m** 에서 아래로(최대 거리 1e6 m), 매 제어 스텝(0.02 s) | `env.yaml:587 · 596 · 615` · `ray_caster.py:218~224` | 설정 · 코드 |
| z | z = 맞은 점 z(세계) - 몸 z(세계) + **0.27**, 빈 칸 채운 뒤 **[-1.5, 1.5]** 로 자름 | `env.yaml:1313` · `observations.py:174~182`(clip_z 기본값 `observations.py:163`) | 설정 · 코드 |
| 미검출(학습 규칙) | 가상 바닥: 빈 공간이 있는 sparse 칸(이 학습에서는 stones) 은 max(지형, 세계 z = d 평면), d ~ U(-1.0, -0.4) 에피소드마다. 그 밖에 맞은 것이 없는 광선은 (같은 스캔의 가장 낮은 유효 높이) - |d| (0.4~1.0 m 아래), 스캔 전체가 비면 평면 높이 | `env.yaml:1793~1802` · `events.py:800~855` · `virtual_floor.py:60~83` · `observations.py:109~140` | 설정 · 코드 |
| 학습 잡음(제외) | x, y U(±0.001) · z U(±0.05) 칸마다 · 센서 드리프트 xyz U(±0.04) 에피소드마다 | `env.yaml:1309~1312 · 616~618 · 2446~2453` · `observations.py:208~216` · `ray_caster.py:129~131 · 246` | 설정 · 코드 |

### 3.7 신경망

| 항목 | 값 | 출처 | 등급 |
|---|---|---|---|
| 클래스 | AME2GazeModel · num_heads 32 · crop 12 × 10 · roi_margin 0.45 · stochastic(log_std) | `agent.yaml:24~33` · `AME2_models.py:390~519` | 설정 · 코드 |
| prop 인코더 | 49 → 512 → 512 → 128 ELU | `AME2_models.py:462` · `rsl_rl/rsl_rl/modules/ame2_modules.py:20~33` | 코드 |
| 전역 문맥 | 지도 전체(x, y 포함 3 채널) Conv 3→8 k3 · Conv 8→32 k3 dilation 2 · 공간 최댓값 → Linear 32→64 ELU | `AME2_models.py:470~480 · 597~599` | 코드 |
| 시선 | [64 + 128] → 64 ELU → 2 → sigmoid → 정수 12 × 10 창(round · clamp) | `AME2_models.py:488~492 · 602~608 · 530~548` | 코드 |
| crop 인코더 | 칸마다 Linear 3→16 · z 채널 Conv 1→8 k5 · 8→48 k5 · 합쳐 Linear 64→96 → 토큰 120 | `AME2_models.py:444~457 · 610~615` | 코드 |
| attention | query MLP 192 → 512 → 512 → 96 · MHA embed 96, 32 heads | `AME2_models.py:497~498 · 617~619` | 코드 |
| 출력 | [96 + 128 + 64] → 512 → 512 → 12 | `AME2_models.py:503` · `:122~123` | 코드 |
| 순환 상태 · 관측 정규화 | 없음 · 없음 | `AME2_models.py:24` · `agent.yaml:6` | 코드 · 설정 |

## 5a. ONNX 받아 쓰는 법

**0) 받을 것.** `ame2-demo.onnx` · `contract.json` · 이 문서 · `test_vectors_flat20.npz` · `parity.json`. 받자마자 ONNX sha256 이 contract.json · SHA256SUMS 와 같은지 본다.

**1) 매 20 ms 한 번, 이 순서로.**
1. 상태 읽기(Isaac 관절 순서, §0b): 몸 COM 선속도 · 각속도(몸 틀) · 중력 방향(몸 틀) · 관절각 · 관절 속도. 관절각에서 기본 관절각을 뺀다.
2. 명령: 목표 위치를 몸 yaw 틀로 바꿔 (x, y), e = wrap(목표 heading - 몸 heading). ‖(x, y)‖ > 2 m 면 2 m 로 줄인다(학습은 이때 e 를 무작위로 줬으므로 2 m 밖 목표의 방향은 뜻이 없다). 앱의 조이스틱 → 1 m 안쪽 목표 변환은 이 범위 안이다.
3. `prop` = [lin_vel 3, ang_vel 3, gravity 3, q - q0 12, dq 12, clip(직전 a, ±50) 12, x, y, sin e, cos e].
4. `mapping`: §3.6 대로 29 × 13 칸에 (x_i, y_j, z_ij). z = 바닥 높이 - 몸 높이 + 0.27 → [-1.5, 1.5]. 광선은 몸 위 20 m 에서 수직으로. 맞은 것이 없는 칸은 (같은 스캔의 가장 낮은 유효 높이) - 0.4~1.0 m(앱의 0.7 m 고정값은 이 범위의 가운데).
5. ONNX 실행 → `action`(그리고 시선 표시가 필요하면 `gaze_r`).
6. 목표각 = 기본 관절각 + 0.25 × action, 목표 속도 0, 앞먹임 토크 0, Kp 25 · Kd 0.5. 시뮬은 물리 스텝마다 §3.2 의 Go2HV 곡선으로 토크를 자른다.
7. 다음 스텝의 직전 a 로 action(자르기 전 raw) 을 저장한다. 리셋 직후 직전 a 는 0.

**2) 코드 뼈대.** 브라우저: `const out = await s.run({prop: new ort.Tensor('float32', p, [1,49]), mapping: new ort.Tensor('float32', m, [1,29,13,3])})`. 파이썬: `sess.run(["action"], {"prop": p[None].astype(np.float32), "mapping": m[None].astype(np.float32)})`. mapping 의 메모리 순서는 [i(x)][j(y)][채널 x, y, z].

**3) 맞는지 확인.**
- `test_vectors_flat20.npz`: `prop[t]` · `mapping[t]` 를 한 스텝씩 넣어 `action[t]` 와 최대 차이 1e-4 이하.
- 기본 자세 시험(§0b): 기본 자세에서 joint_pos_rel 전부 |값| < 0.05, action 0 이면 목표각 = 기본 관절각.
- 평지 정지 상태의 mapping z 는 0 근처(몸 높이 약 0.27 m), x, y 채널은 contract.json 격자와 같아야 한다.

**4) 하지 말 것.** START(m6000) 의 지도 함수(32 × 16 · 높이 1 채널) 를 쓰지 않는다. 속도 명령을 그대로 넣지 않는다. 학습 잡음을 배포 입력에 넣지 않는다.

## 7. 추가 확인 (11-03 저녁) · 남은 한계

지시문 HANDOFF §4 의 물음과 v0.1 에서 비워 둔 칸을 재거나 기록으로 확인했다.

| 물음 | 답 | 근거 | 등급 |
|---|---|---|---|
| ORT Web 에서 같은 출력인가 | onnxruntime-web 1.31.1 WASM 1 thread(Node v24.15.0) 로 기록 400 스텝: action 최대 차이 **2.6e-06**(평지 1.5e-06 · 계단 2.6e-06, 기준 1e-4 통과) | `parity.json` `ort_web` | `실측` |
| 시선 창 반올림이 실행기마다 뒤집히나 | 기록 400 스텝에서 반올림 경계(.5)까지 가장 가까운 거리: x 0.0005 칸(r0 로 3.0e-05) · y 0.0098 칸. 실행기 사이 gaze_r 차이는 최대 2.4e-07 라 여유가 약 127 배. 이 400 스텝에서는 뒤집힘 없음. 다른 입력에서 경계에 더 가까우면 생길 수 있음 | 기록 `gaze_r` | `실측` |
| 1 m 목표에서 실제 속도 | 앱 조이스틱처럼 매 스텝 몸 틀 (1.0, 0) m · e = 0 목표를 다시 넣으면 평지에서 4~12 s 평균 전진 **1.08 m/s**(로봇 4 대 1.06, 1.08, 1.09, 1.09, 95 백분위 1.14). 같은 방식 2 m 목표는 0.96 m/s. 8 대 모두 넘어짐 · 리셋 없음. 이동 보상 상한 v_max 1.2 m/s 보다 낮다 | `speed_goal.py`(학습 task, 관측 잡음 끔, 8 대) | `실측` |
| 계단 영상이 같은 모델 · 조건인가 | 우리 model_14999 영상 두 묶음(`…Vmax1.2_20-25k__yaw180` 난이도 0.35 · `…__yaw180_d0.8` 난이도 0.8) 의 기록 로그 체크포인트는 `ame2_spd/…/model_14999.pt` md5 2fc79f9a…(이 저장본) 이다. 계단 단 높이 = 0.03 + 0.14 × 난이도 → 0.079 m · 0.142 m, 단 너비 U(0.22, 0.30) m. 목표는 env 의 목표 생성기(앞 45° 원뿔 안 평평한 칸), 첫 방향 ±180°, Play 설정(무작위화 · 잡음 · 지연 끔). 팀 문서가 어느 영상을 가리키는지는 문서에 없어 이 두 묶음으로 답한다 | 영상 기록 `traj_stair_*.log` · `custom_terrains.py:296~299` · `env.yaml:298~330` | `실측` |
| 앱의 빈 칸 0.7 m 고정값 | 앱 규칙(빈 칸 = 같은 스캔의 가장 낮은 유효 높이 - 0.7 m, 가상 평면 없음; 앱 `mobile/sim/ame2-adapter.js:94~125` @20f3d066) 은 학습 규칙(같은 식에 U(0.4, 1.0) m) 의 가운데 값이다. 같은 벤치마크(평가 seed 1001 · 12지형 · 로봇 2,400 대 · 5 에피소드, `eval_gaze.py`) 를 깊이만 0.7 고정으로 다시 돌린 결과: 전체 71.71 % → **71.49 %**, 계단 오르기 97.90 → 98.10 %, 계단 내려가기 99.10 → 98.90 %, 지형별 차이 최대 -1.70 %p(gap). 지형별 표는 `parity.json` `void_depth_0p7`. 같은 seed 로 두 번 잰 측정끼리도 지형별 최대 3.3 %p 까지 차이가 났던 적이 있어(우리 REQ299 측정), 이 차이는 그 흔들림 안이다 | `cmp_depth07.py` | `실측` |
| 학습 코드 출처 · 커밋 | rsl_rl = `leggedrobotics/ame2_minimal` 커밋 `8beb9a688d67882828019583f7d5a78e3517f233`(2026-10-06, rsl_rl 5.0.0) 의 `rsl_rl/rsl_rl` .py 33 개와 바이트 단위로 같음(수정 없음). go2 코드 83 개는 저장소 밖 우리 코드라 커밋이 없고 code id a78a734258cf · manifest sha256 `19d459da…` 로 식별 | 팟 원본 트리 git 과 대조 | `실측` |
| 학습 호스트의 Isaac Sim 판 | 5.1: 학습 로그의 Kit 경로가 `Isaac-Sim/5.1`. 학습 시작 때 pip 목록과 팟 1 pip 목록이 같아(출력 머리줄 하나만 다름) 같은 이미지로 보고 **5.1.0-rc.19** | `out/q/smoke.log:1` · `pip_freeze.txt` | `실측` · 추론 |

남은 한계:
- 기록 조건: 관측 잡음 · 지도 잡음 · 센서 드리프트를 끄고, 평지 칸은 rough 칸의 기울기 · 거칠기를 0 으로 바꾼 칸이다(학습 지형 그대로가 아님). 나머지(도메인 무작위화 · 지연 · 가상 바닥) 는 env.yaml 그대로. 기록 설정(`env_record.yaml`) 과 env.yaml 을 비교하면 그 밖에 두 곳이 다르다: 보상 매개변수 `ame2_move2goal.v_max 1.2`(학습은 train.py 인자로 넣음, 보상에만 쓰여 관측 · 행동과 무관) 와 시작 yaw · 목표 원뿔 커리큘럼의 `max_steps`(학습 기록 24, 기록 env 는 task 기본값 48000 이라 기록 중 시작 yaw 와 목표 원뿔이 좁았다; 리셋 분포만 바뀜). 지형 칸 크기 · prim 경로 · env_spacing 차이는 학습이 env 를 만든 뒤 덤프해서 생긴 표기 차이다(`go2/scripts/rsl_rl/train.py:289`).
- 1 m 목표 속도는 평지 · 앞쪽 목표만 쟀다(옆 · 뒤 목표, 계단 위 속도는 재지 않음, `미측정`).
- 실기(SDK 순서 · IMU · 안전 제어) 는 이 문서 범위 밖이다. lin_vel 이 특권이라 실기에는 이 teacher 를 쓰지 않는다(팀장 11/03 16:0x: student 는 따로).

## 8. 근거 경로

- run: `/network-volume/limseokheon/ame2_spd/logs/rsl_rl/go2_gaze_teacher/2026-10-27_15-57-27_nogapst5_vmax12_to15000/`(params/env.yaml 2,504 행 · params/agent.yaml 65 행 · model_14999.pt)
- 코드 사본: `/network-volume/limseokheon/ame2_spd/`(rsl_rl/rsl_rl · go2/ame2_go2 · go2/scripts) · Isaac Lab 원본 `/workspace/isaaclab/source/isaaclab/isaaclab/`
- 내보내기 · 기록 도구(이 폴더에 올리지 않음, 석헌 PC 와 팟 `/root/onnx1103/`): `export_ame2_onnx.py` · `rec_onnx_vectors.py` · `parity_ref.py` · `parity_ort.py`

## 9. 기계 블록 (contract.json 의 요약)

```json
{"format": "ame2-demo-onnx/1", "checkpoint_sha256": "8c3be365eeddd136edda31988df7fed96ad6f9f92713490b2d993037bf978d4d", "command_type": "goal_pose_xy_sincos", "state": "stateless", "joint_names": ["FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint", "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint", "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint"], "default_joint_pos": [0.1, -0.1, 0.1, -0.1, 0.8, 0.8, 1.0, 1.0, -1.5, -1.5, -1.5, -1.5], "kp": [25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0], "kd": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5], "control_hz": 50, "sim_dt": 0.005, "decimation": 4, "action_delay": {"unit": "physics_step", "range_inclusive": [0, 4], "physics_dt_s": 0.005, "seconds": [0.0, 0.02], "sampled": "once per episode at reset, per robot", "applied": "FIFO over physics steps (4 per control step)"}}
{"inputs": [["prop", [1, 49]], ["mapping", [1, 29, 13, 3]]], "outputs": [["action", [1, 12]], ["gaze_r", [1, 2]]], "action": "target_q = default_joint_pos + 0.25 * action (Isaac order); target velocity 0; feed-forward torque 0", "map": {"shape": [29, 13, 3], "resolution_m": 0.06, "x_range_m": [-0.42, 1.26], "y_range_m": [-0.36, 0.36], "z_offset": 0.27, "z_clip": [-1.5, 1.5], "sensor_offset_m": [0.42, 0.0, 20.0]}, "onnx_sha256": "830595df1e78072c0606b5193d1ba787720ff6777edc7cabe496b8c1a9d25de6", "parity_max_abs": 3.5762786865234375e-06}
```
