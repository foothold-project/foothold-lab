> 분류: A/정책학습 · 구현 명세 (AME-2 teacher · student · neural mapping 을 Unitree Go2 에 논문 충실하게)
> 작성: Fable 명세 세션 · 2026-10-18
> 근거: 논문 `C:/Users/AI-WS01/s2_lab/_papers/2601.08485v3.txt` (arXiv 2601.08485v3, 행 번호 P:n) · 공식 코드 `C:/Users/AI-WS01/s2_lab/_research_repos/ame2_minimal` @8beb9a68 (G1 전용 · Isaac Lab 2.3.2) · Go2 URDF `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf` · Isaac Lab 2.3.2 `C:/isaac/IsaacLab` (`isaaclab_assets/robots/unitree.py` UNITREE_GO2_CFG · `velocity/config/go2/rough_env_cfg.py` · `sensors/ray_caster/ray_caster.py` · `managers/reward_manager.py`) · 선행 검토 VERIFY-fable-19a · VERIFY-astra-18h (맥락만)
> 요지: 논문과 공식 코드를 기준으로 삼고 로봇 고유 항목(관절 수 · 링크 이름 · PD · 행동 배율 · 키 오프셋 · 지도 폭 · 지형 축척) 만 Go2 로 바꾼다. 공식 코드는 teacher · LSIO student · PPO_IL · 융합 코드까지 들어 있고, 빠진 것은 지도 모델 가중치와 지도 모델 학습 코드다. 16 GB 에서는 attention 역전파 활성 메모리가 미니배치를 제약하므로 gradient accumulation 으로 Table IV 를 지키거나, 바꾼 값을 영수증에 적는다
> 상태: 정적 명세 · GPU · Isaac · 학습 미실행 · 다른 파일 수정 없음 · Go2 실측값(관절 순서 · 질량 · 서 있는 높이 · 처리량 · VRAM) 은 전부 「측정 필요」 로 표기

AME-2 를 Go2 에 옮기는 일은 논문 전 구성(teacher 전체 정책 · MoE critic · LSIO student · 증류 손실 · 불확실도 지도 · 보상 체계 · 지형 · DR · PPO) 을 그대로 두고 로봇 고유 상수만 Go2 값으로 바꾸는 일이며, 공식 코드가 G1 용으로 이미 Isaac Lab 2.3.2 에 구현한 부분(모델 · 알고리즘 · 환경 함수 · 융합) 은 복제해서 쓰고, 공개되지 않은 지도 모델 가중치와 그 학습 코드는 논문 V 절대로 우리가 만든다.

# SPEC · AME-2 → Go2 (논문 · 공식 코드 충실 재현)

## 0. 읽는 법 · 약칭 · 전제

- 팀장 결정(인용): 「우리 기준에 논문을 끼워 맞추려고 하는 것 같다. 이러면 안될 것 같다」 · 「추정기, ReLU 이런게 재현, 구현이 안되면 완전 의미 없거든 … 그걸 축소하면 별로 안좋은 것 같아」. 그러므로 이 문서는 **옛 기준 정책(MoE-CTS E1 · 187 점 · 속도 명령) 에 맞추지 않는다**. 처음부터(from scratch) 논문 방식으로 Go2 를 학습한다.
- 값의 출처를 세 가지로 구분한다: **논문** (P:행) · **공식 코드** (파일:행) · **Go2 로컬 자료** (URDF · Isaac Lab). 세 곳에 없는 값은 지어내지 않고 「측정 필요」 또는 「팀장 결정」 으로 적는다.
- 공식 코드가 Isaac Lab 2.3.2 용이고 우리 설치본도 2.3.2 (`C:/isaac/IsaacLab/VERSION`) 이므로, 환경 함수(mdp) · 모델 · 알고리즘은 **옮겨 쓰는 것이 아니라 그대로 쓰는 것** 이 기본이다. 바꾸는 것은 cfg 의 로봇 상수와 Go2 용 대칭 함수, 그리고 지형 축척이다.
- 공식 코드의 라이선스는 `ame2/` GPL-3.0-only (`ame2/setup.py:35`), `rsl_rl/` 는 수정된 rsl_rl (BSD-3, `README.md:72`). 우리가 파생 패키지를 배포하면 GPL 이 따라온다. 팀장 확인 사항.

| 약칭 | 파일 (저장소 루트 기준) |
|---|---|
| P | `_papers/2601.08485v3.txt` (행 번호) |
| AM | `rsl_rl/rsl_rl/models/AME2_models.py` |
| MD | `rsl_rl/rsl_rl/modules/ame2_modules.py` |
| PPO | `rsl_rl/rsl_rl/algorithms/ppo.py` |
| IL | `rsl_rl/rsl_rl/algorithms/ppo_il.py` |
| RN | `rsl_rl/rsl_rl/runners/on_policy_runner.py` |
| CF | `ame2/ame2/tasks/agents/rsl_rl_ppo_cfg.py` |
| EC | `ame2/ame2/tasks/ame2_env_cfg.py` |
| OB · RW · TM · CM · CU · EV · AC · ACC · SY | `ame2/ame2/tasks/mdp/` 의 `observations.py` · `rewards.py` · `terminations.py` · `commands.py` · `curriculums.py` · `events.py` · `actions.py` · `acceleration.py` · `symmetry.py` |
| TR · CT | `ame2/ame2/tasks/terrains.py` · `custom_terrains.py` |
| AS | `ame2/ame2/assets/unitree.py` (G1_CFG) |
| NM · NU · LD | `ame2/ame2/sensors/livox_neural_map_sensor.py` · `neural_mapping_utils.py` · `mid360_lidar.py` |
| PL · TN | `ame2/scripts/rsl_rl/play.py` · `train.py` |
| RM · MZ | `README.md` · `modelzoo/g1_gaze_64000env_10h/params/{agent,env}.yaml` |
| U | `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf` |
| LAB-GO2 | `C:/isaac/IsaacLab/source/isaaclab_assets/isaaclab_assets/robots/unitree.py` (UNITREE_GO2_CFG, 140~181) |
| LAB-GO2-ENV | `C:/isaac/IsaacLab/source/isaaclab_tasks/.../locomotion/velocity/config/go2/rough_env_cfg.py` |
| LAB-RC · LAB-RM | `C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/ray_caster.py` · `managers/reward_manager.py` |

전제 하나를 먼저 확정한다. Isaac Lab RewardManager 는 `term * weight * dt` 로 보상을 더한다(LAB-RM:150). 논문 Table I 의 가중치 열은 「Weight (×dτ)」 이고 dτ = 0.02 s (P:217~239) 이므로, **공식 코드의 weight 숫자(100 · 50 · 5 · 5 · -500 …) 가 곧 논문 표의 숫자** 다. 조기 종료만 논문 -10/dτ → 코드 -500 (×0.02 = -10 /회) 로 같다(EC:439~443). 두 번 곱하지 않는다.

Go2 로컬 수치(계산 근거를 적는다 · 시뮬 실측과 다를 수 있음):
- 관절 12 (U: `{FL,FR,RL,RR}_{hip,thigh,calf}_joint`). URDF 순서는 FL → FR → RL → RR, 각 hip · thigh · calf. **Isaac Lab articulation 순서는 PhysX 가 정하며 URDF 순서와 다를 수 있다** (공식 코드도 sensor 와 articulation 의 body 순서 차이를 처리한다, RW:441~454). → 측정 필요 (U0).
- 링크: `base`, `{FL,FR,RL,RR}_{hip,thigh,calf,foot}`, `Head_upper`, `Head_lower` (각 0.001 kg · 충돌체 있음), `*_rotor` (고정 관절 · 질량 0.089 · 충돌체 없음 → import 시 병합될 수 있음), `imu` · `radar` · `front_camera` (질량 0). → Isaac Lab USD 의 실제 body 목록은 측정 필요.
- 질량 합(U): base 6.921 + 다리 4 × (0.678 + 1.152 + 0.154 + 0.04) = 8.096 + rotor 12 × 0.089 = 1.068 + head 0.002 → **16.087 kg · 체중 ≈ 157.8 N**. Isaac Lab USD 값은 `asset.data.default_mass.sum()` 으로 측정.
- 기본 관절각(LAB-GO2:159~165): hip ±0.1, 앞 thigh 0.8, 뒤 thigh 1.0, calf -1.5. 다리 길이 thigh 0.213 · calf 0.213 (U:118~161), 발 반지름 0.022 (U:217). 서 있는 base 높이(기구학 추정): 앞 0.213·cos(0.8) + 0.213·cos(-0.7) + 0.022 ≈ 0.333 m, 뒤 0.213·cos(1.0) + 0.213·cos(-0.5) + 0.022 ≈ 0.324 m → **≈ 0.33 m**. LAB-GO2 init z 0.4 는 낙하 시작 높이다. 실측 필요(U0).
- 관절 한계(U): hip ±1.0472, 앞 thigh [-1.5708, 3.4907], 뒤 thigh [-0.5236, 4.5379], calf [-2.7227, -0.83776]; effort hip · thigh 23.7 / calf 45.43, velocity 30.1 / 15.70. Isaac Lab actuator 는 effort 23.5 · saturation 23.5 · velocity 30 을 전 관절 공통으로 둔다(LAB-GO2:170~178). 공식 보상 `joint_torque_limits` · `joint_vel_limits` 는 actuator 의 effort_limit · velocity_limit 을 읽으므로(RW:523~582) **Isaac Lab cfg 값이 한계가 된다**.
- 몸통 충돌 상자 0.3762 × 0.0935 × 0.114 (U:18), hip 관절 위치 x ±0.1934 · y ±0.0465 (U:80 등).

---

## 1. 구성 요소 목록

표 열: 구성 요소 · 논문 값 (P:행) · 공식 코드 값 (파일:행) · Go2 적응(로봇 고유 항목만, 근거) · 미확인.

### 1.1 관측

| 구성 | 논문 | 공식 코드 | Go2 적응 | 미확인 |
|---|---|---|---|---|
| teacher proprio | v_b(teacher 만) · ω_b · g_b · q · q̇ · 직전 행동 · 명령 c (P:91) | 그룹 `teacher_prop` = base_lin_vel 3 · base_ang_vel 3 · projected_gravity 3 · joint_pos_rel · joint_vel_rel · last_action · 명령 4 (x, y, sin, cos; dist_thr 2.0) · 남은 시간 없음 (EC:242~266, OB:263~298). G1: 3+3+3+23+23+23+4 = 82 | Go2: 3+3+3+12+12+12+4 = **49**. 코드는 관측에서 차원을 추론하므로(AM:45~46) 숫자 수정 없음 | 없음 |
| teacher 지도 | 각 격자점 (x, y, z) 3 채널 (P:92) · dmap 3 (P:165) | `ame2_teacher_mapping`: (N, nx, ny, 3). x · y = yaw 정렬 base 좌표(센서 오프셋 0.5 더함), z = hit_z - base_z + offset(0.74), clip ±1.5, 구멍(inf) = 그 env 의 유효 최솟값 - U(0.65, 1.5), 균일 잡음 [0.001, 0.001, z] (OB:120~196, EC:232~235). `_data.pos_w` 는 base 위치(+drift) 이며 cfg 오프셋 20 m 는 ray 시작점에만 들어간다(LAB-RC:218~226, 240~247) | offset 0.74 (G1 서 있는 높이) → **Go2 ≈ 0.33 (측정값으로 교체)**. clip ±1.5 와 구멍 깊이 U(0.65, 1.5) 는 논문 Appendix A 의 가상 바닥 깊이(-1.5 ~ -0.35, 두 로봇 공통) 와 같은 절대값 규약이라 유지 | 코드 구멍 규칙은 논문 미기재(코드 근거) |
| student 지도 | (x, y, z, u) 4 채널, u 는 불확실도 (P:92) · dmap 4 (P:165) | `ame2_neural_map_obs_from_sensor`: z = est + elevation_offset(0.74) clip ±2, u = clip(var, 0.01, 2) → 0.5·log(u) + 0.5 (OB:201~240). 센서 출력은 (est, var) (NM:169) | elevation_offset → Go2 ≈ 0.33 | u 변환식은 논문 미기재(코드 근거) |
| student proprio 이력 | 선속도 · 명령을 뺀 proprio 20 step 을 쌓아 LSIO (P:189~201) | `student_prop_hist` = base_ang_vel · projected_gravity · joint_pos_rel · joint_vel_rel · last_action, 각 history_length 20, flatten False → (N, 20, prop_dim), 오래된 것이 앞 · 최근 3 step = `[:, -3:]` (EC:268~299, AM:346~370). G1 prop_dim 75 | Go2 prop_dim = 3+3+12+12+12 = **42**. 명령 `student_cmds` 4 (EC:301~311) | reset 직후 이력은 첫 관측으로 채워짐(Isaac Lab CircularBuffer) · 논문 미기재 |
| critic 관측 | teacher 입력 + 각 링크 접촉 상태(특권) + 전체 명령(상대 위치 · sin/cos yaw · 남은 시간) + GT 지도 (P:181~187, 404, Fig.3) | `critic` = teacher_prop 항목(잡음 없음) + 명령 4(clip 없음) + time_left 1 + contact_states(질량 > 0.1 kg 링크, 힘 > 1 N, 이력 4 최대) + height_scan(critic scanner, z 1 채널, offset 0.74, 잡음 ±0.1, clip ±1.5) (EC:184~226, OB:306~379) | **mass_threshold 0.1 kg 이면 Go2 발(0.04 kg) 이 빠진다** → 임계 0.03 으로 내리거나 발을 명시 포함(논문 「각 링크」 를 지키는 쪽). Head_* (0.001 kg) 는 제외됨. 예상 링크 수 17 (base 1 + hip 4 + thigh 4 + calf 4 + foot 4) → 측정 필요 | ignore_bodies(G1 센서 링크) 는 Go2 에 없음 |
| 관측 잡음 | v 0.1 m/s · ω 0.2 rad/s · g 0.05 · q 0.01 rad · q̇ 1.5 rad/s · 지도 0.05 m · 지도 질의 drift ±0.03 m (P:1141) | 같음 (EC:189~197, 247~255); 지도 z 잡음은 커리큘럼으로 0 → 0.05 (EC:640~647); teacher scanner drift_range ±0.04 (3 축) (EC:80) ; student query_drift 0.03 (EC:785) | 로봇 무관 | 논문 IV-B 「teacher 는 잡음 없는 proprio」(P:179~181) 와 Appendix B 의 잡음 목록이 서로 어긋남 → §2 |
| 명령 관측(actor) | 목표 거리 2 m 로 clip · 남은 시간 제거 · 2 m 넘으면 yaw 명령 무작위 (P:404) | `dist_thr=2.0` 로 clip, 먼 목표는 yaw ∈ U(-π, π) (OB:277~286) | 로봇 무관 | 없음 |

### 1.2 신경망

| 구성 | 논문 | 공식 코드 | Go2 적응 | 미확인 |
|---|---|---|---|---|
| 지도 점 FC | 점마다 MLP 위치 임베딩 (P:96) | Linear(dmap → 16) + ELU, x · y 포함 전 채널 (AM:52~55) | 없음 | 없음 |
| 지도 CNN | 지역 특징 CNN (P:96) | Conv2d(dmap-2 → 8, k5, p2) ELU → Conv2d(8 → 48, k5, p2) ELU, z(+u) 채널만 (AM:57~62, 157~159) | 없음 | 없음 |
| 지역 특징 융합 | MLP 로 pointwise local feature (P:96) | Linear(16+48 → 96) ELU → (B, L·W, 96) (AM:65~68, 163~164) | 없음 | 없음 |
| 전역 특징 | MLP + max pool (P:96) | MLP_GlobalPool(96 → 64 ELU → 64) 뒤 `torch.max(dim=1)` → 64 (AM:78, 168~169; MD:36~47) | 없음 | 없음 |
| proprio encoder (teacher) | plain MLP (P:181~183) | MLP_512(prop_dim → 128) = Linear 512 ELU 512 ELU → 128 (AM:73; MD:20~33) | prop_dim 82 → 49 (자동) | 없음 |
| query · MHA | 전역 특징 + proprio 임베딩 → MLP → query, MHA 의 K/V = 지역 특징 (P:96) | MLP_512(128+64 → 96), `nn.MultiheadAttention(96, heads=32)` → head_dim 3, query 1 개, K/V = 모든 격자점 (AM:79~80, 170~173). `mha_math` 가 SDPA 를 math 커널로 고정: **sm_120(Blackwell) 에서 bf16 fused 커널 역전파가 batch×heads > 1e5 에서 죽는 문제 회피** (MD:6~17) | 없음. RTX 5080 이 sm_120 이므로 이 회피가 우리에게 그대로 적용된다 | 없음 |
| 행동 decoder | 지도 임베딩 + proprio 임베딩 → MLP → 행동 (P:95~96) | MLP_512(96 + 128 + 64 = 288 → num_actions) (AM:85, 121~123) | num_actions 23 → 12 (자동) | 없음 |
| 행동 분포 | PPO Gaussian (P:86) | `stochastic=True`, `noise_std_type="log"`, init 1.0 (CF:32~37) | 없음 | 없음 |
| MoE critic | GMT [68] 식 MoE (P:171~177) | 16 expert × MLP_512(obs_dim → K), router MLP_512(obs_dim → 16) softmax, 소프트 혼합 (AM:1046~1130; CF:160~163). obs = critic 그룹 concat (AM:1129~1130) | obs_dim: G1 (82+1+26+390) → Go2 (49+1+17+390 = 457, 지도 26×15 일 때) 자동 | expert 수 16 은 논문 미기재(코드 근거) |
| multi-head critic | 없음(단일 가치) | 기본 켜짐: 보상 항 수 K 만큼 value head, 반환 · 어드밴티지는 합 (PPO:35~36, 137~140, 244~270, 650~668) | 로봇 무관 | §2: 논문 밖 기능 → 기본 끔(K=1) 권고 |
| student proprio encoder (LSIO) | 20 step 이력 + Long-Short I/O → 시간 임베딩, 명령과 함께 MLP (P:189~201) | hist: Conv1d(prop_dim → 16, k5) ELU → Flatten(16·(T-4)) → Linear(→ 64) ELU; recent: Linear(3·prop_dim → 60) ELU; cat[64, 60, cmd] → **MLP_512(128 → 128)** (하드코딩 128) (AM:299~317, 364~375) | Go2: 16·16 = 256 → 64, 3·42 = 126 → 60, 64+60+4 = **128** → 하드코딩과 일치, 수정 없음 | LSIO 세부 폭은 논문 미기재(코드 근거) |
| student 지도 encoder | teacher 와 같은 AME-2, dmap 4 (P:165) | AME2Model 과 동일 모듈, dmap 4 (AM:278~292) | 없음 | 없음 |
| JIT twin | 배포는 ONNX Runtime (P:402) | `_TorchAME2Model(prop, map) → (actions, attn96, global64)`, deterministic mean (AM:1197~1252); `as_onnx` 미구현(AM:225~227); 내보내기는 PL:638~660 (`torch.jit.script` + freeze) | 없음 | Go2 온보드 런타임 미확인 |
| 가변 Gaze 모델 | 없음 | AME2GazeModel · AME2GazeLSIOModel (TAGA, AM:390~839) · 모델주 checkpoint 도 Gaze | **쓰지 않는다**(논문 밖) | 없음 |

### 1.3 지도 사양

| 구성 | 논문 | 공식 코드 | Go2 적응 | 미확인 |
|---|---|---|---|---|
| teacher 격자 | ANYmal-D 36 × 14 @ 8 cm, 중심 x 0.6 m; TRON1 18 × 13 @ 8 cm, 중심 0.32 m; 「로봇 치수와 지형 크기로 설계」 (P:399~400, 385~389) | G1 26 × 15 @ 8 cm, x ∈ [-0.5, 1.5], y ∈ [-0.56, 0.56] (GridPattern size [2.0, 1.12], offset (0.5, 0, 20), ordering "yx", yaw 정렬) (EC:71~81) | **팀장 결정**. 후보 A: 논문 사족 값 36 × 14, 중심 0.6 (size [2.8, 1.04] → x ∈ [-0.8, 2.0]) = 504 점. 후보 B: 공식 G1 값 26 × 15 = 390 점. 해상도 8 cm 는 두 로봇 공통이라 유지. Go2 몸길이(hip 간 0.387 m) 가 ANYmal-D 보다 작고 Go2 지형 축척도 작아질 것이므로 **B 를 기본 제안**, 비용(attention K/V 수 · §4) 도 B 가 23 % 적다 | 두 후보의 성능 차이 미확인 |
| critic 격자 | GT 지도 (Fig.3 「channel 제거」) | actor 와 같은 격자의 z 1 채널, 잡음 ±0.1, clip ±1.5, drift 없음 (EC:89~96, 217~222) | 격자는 actor 와 동일하게 | 없음 |
| z 기준 | 「egocentric elevation」 (P:92) | hit_z - base_z + offset(서 있는 높이) (OB:134) → 평지에서 ≈ 0 | offset ≈ 0.33 (측정) | 없음 |
| 구멍(void) | 희소 지형 절반은 물리 바닥, 절반은 지도에만 보이는 가상 바닥(-1.5 ~ -0.35 m) (P:1131~1133) | 가상 바닥은 없다. 대신 inf 를 「유효 최솟값 - U(0.65, 1.5)」 로 채움(OB:137~148) · 바닥 자체는 확률 0.5 로 물리 박스(CT:819~824 등) | 로봇 무관 | §2 충돌 항목 |
| 잡음 커리큘럼 | teacher 첫 20 % 반복에서 지도 잡음 0 → 최대 (P:392) | `teacher_mapping_noise` 0 → 0.05 over `24·2000` env step = 2000 반복 (EC:640~647, CU:242~261) | 로봇 무관 | §2: 2000 은 코드의 max_iterations 5000 기준 40 % → 우리 teacher 반복 수의 20 % 로 환산 |
| drift | 질의 시 ±0.03 m (P:1141) | teacher scanner `drift_range` ±0.04 (xyz, ray 시작점 이동 → 높이에도 -drift_z 반영, LAB-RC:245~246, OB:134); student `query_drift_range` 0.03 (EC:785; NM:186~191) | 로봇 무관 | §2: 0.04 vs 0.03 |
| student 지도 DR | 10 % env 는 완전 지도(분산 0.0025 m²); 1 % 점을 무작위 값 + 분산 > 1 m² (P:1142) | `clean_source_ratio` 0.1 · `clean_source_unc` **0.05** (분산 자리) · `clean_source_noise` 0.02; `random_pixel_ratio` 0.01, est ∈ [-0.7, -0.2], unc ∈ **[0.3, 1.3]** (NM:131~167, 427~432; EC:782~788) | 로봇 무관 | §2: 코드 0.05 는 분산 0.0025 의 표준편차로 보임(단위 미끄러짐 추정) · 분산 0.3~1.3 은 「> 1」 아님 |
| 지도 모델 입력 격자 | ANYmal-D 51 × 31 @ 4 cm 중심 x 1.0; TRON1 31 × 31 @ 4 cm 중심 0.6 (P:608~618) | G1 lidar: 201 × 101 @ 3 cm, x ±3 m · y ±1.5 m (NM:382~385) | **팀장 결정 · 센서 결정 뒤**(D435i 깊이 카메라 · 메모리 기록). 논문 깊이 카메라 판은 4 cm 격자이며 전방 치우침 | Go2 카메라 장착 위치(URDF `front_camera` 는 (0.327, 0, 0.043), U:755) 와 D435i 실제 장착은 측정 필요 |
| 전역 지도 | 8 m × 8 m, 경계 접근 시 재중심 (P:621) | depth 판 `BatchedGlobalProbWinnerPipeline` size_m 기본 20, res 0.08, init_var 100, h_bias -0.5(서 있는 높이 prior) (NU:229~241); lidar 판 6 m, 0.03, init_var 10, hole -3 (NM:394~397) | h_bias → -(Go2 서 있는 높이 ≈ 0.33) | 없음 |

### 1.4 명령

| 구성 | 논문 | 공식 코드 | Go2 적응 | 미확인 |
|---|---|---|---|---|
| 목표 | 위치 + heading 목표, 에피소드 끝에 도달 (P:86, 257~281) | `SafeTerrainBasedPose2dCommand`: 지형 flat patch 중 전방 원뿔(|y| ≤ x·tan(cone) + 0.1) 안에서 무작위, heading U(-π/3, π/3), 16.01 s 마다 재표집(= 에피소드 당 1 회) (CM:18~90; EC:150~162) | flat patch 반지름 · max_height_diff 는 지형 cfg 에 있음(TR 각 항) → Go2 지형 축척과 함께 결정 | heading 범위 ±π/3 는 논문 미기재 |
| AOT / EOT 샘플링 | 지형별로 「아무 곳」 또는 「반대편 끝」 (P:1113) | flat_patch_sampling 의 x_range 로 구현(EOT 는 x_range 가 2.6~5.5 등) (TR:36~38, 121~123 등) | 지형 축척과 함께 | 없음 |
| 원뿔 커리큘럼 | 없음 | cone 10° → 45° over 2000 반복 (EC:632~639, CU:190~204) | 로봇 무관 | §2 코드 전용 |
| 초기 heading 커리큘럼 | 첫 20 % 반복에서 목표 방향 → U(-π, π) (P:392) | reset yaw ±π/4 시작, `init_yaw_range` 0 → ±π over 2000 반복 (EC:378, 624~631) | 로봇 무관 | 시작값 ±π/4 는 코드 |
| 성공 판정(커리큘럼) | 목표 도달 + 성공률 EMA > 0.5 승급, 4 m 밖 강등(평균 시작 거리) (P:391) | 성공 = dist < 0.5 ∧ t_left < 4 s, EMA 0.8/0.2, 승급 dist < 0.5 ∧ EMA > 0.5, 강등 dist > 4.0; 지형별 성공률 로그 (CU:292~383) | 로봇 무관 | 없음 |

### 1.5 보상 · 종료

| 항 | 논문 식 · 가중(×dτ) | 공식 코드 (weight · 함수) | Go2 적응 | 미확인 |
|---|---|---|---|---|
| 위치 추종 | 1/(1 + 0.25 d²)·t_mask(4), 100 (P:261~276) | 100, `std=2.0` → 1/(1+(d/2)²), T 4.0 (RW:219~236; EC:413~415) | 없음 | 없음 |
| heading 추종 | 1/(1 + d_yaw²)·t_mask(2)·1(d < 0.5), 50 (P:279) | 50 (RW:239~259; EC:416~418) | 없음 | 없음 |
| 이동 | 1(d < 0.5 ∨ (cos θ > 0.5 ∧ 0.3 ≤ v ≤ 2)), 5 (P:284~288) | 5, v_min 0.3 · v_max 2.0 · 몸통 속도(body_names) (RW:180~216; EC:419~428) | body `torso_link` → **`base`** | 없음 |
| 서기 | 1(d<0.5 ∧ d_yaw<0.5)·exp(-(d_foot+d_g+d_q+d_xy)/4), 5 (P:292~300) | 5, 발 센서 `.*ankle_roll_link` (RW:262~304; EC:429~436) | 발 → **`.*_foot`** (4) | 없음 |
| 조기 종료 | -10/dτ (P:219) | -500 (×dt = -10), `term_keys="early_.*"` (RW:35~59; EC:439~443) | 없음 | 없음 |
| 과회전 | |ω_z| > 2.0 rad/s, -1 (P:303) | -1, **yaw_rate_thr 3.0**, head_link 세계 yaw 속도 (RW:352~365; EC:445~449) | 몸 → `base` | §2: 2.0(논문) 택 |
| 평지 도약 | 전 발 공중 ∧ 지도 고도차 < 30 cm, -1 (P:368) | -1, elevation_thr 0.3, start 0.2 s, critic scanner (RW:368~396; EC:450~460) | 발 → `.*_foot` | 없음 |
| 비발 접촉 + 전환 | 비발 링크 접촉 수 + 새 접촉 수, -1 (P:369) | -1, 센서 body `^(?!.*ankle…).*_link`, first_contact 포함 (RW:399~412; EC:461~468) | body → **발을 뺀 전 링크** (`^(?!.*_foot).*`) | Head_* 포함 여부: 포함(논문 「비발」) |
| 스텀블 | 수평 접촉력 > 수직, -1 (P:370) | -1, f_xy > 1.1·f_z + 1 N, 전 링크 (RW:415~426; EC:469~473) | body → 전 링크 `.*` | 1.1 · +1 N 은 코드 근거 |
| 미끄러짐 | 접촉 중 이동, -1 (P:371) | -1, slip_vel_thr 0.3, contact_time > 0.025 s, 수평 속도 (RW:429~463; EC:474~483) | body → 전 링크 | 임계는 코드 근거 |
| 자가 충돌 | 링크 간 충돌, -1 (P:371) | -1 × 3 센서(knee · ankle · torso 필터 쌍), force_matrix (RW:466~482; EC:98~128, 484~507) | **Go2 자가 충돌 센서 신설**: 필터 쌍 예 (FL_calf↔FR_calf, RL_calf↔RR_calf, FL_foot↔FR_foot, RL_foot↔RR_foot, 앞뒤 calf 교차). **LAB-GO2 는 `enabled_self_collisions=False`** (LAB-GO2:154) → True 로 바꿔야 센서가 잡는다 | 쌍 선택은 설계 선택 |
| roll 속도 | [ω_b]_x², -0.1 (P:215, 219) | -0.1 (RW:307~318; EC:510~514) | body → `base` | 없음 |
| 관절 정칙화 | ‖q̇‖² + 0.01‖τ‖² + 0.001‖q̈‖², -0.001 (P:215, 219) | -0.001 (RW:321~335; EC:515~519) | 없음 | 없음 |
| 행동 평활 | ‖a_t - a_{t-1}‖², -0.01 (P:215, 219) | -0.01 (RW:174~176; EC:520~523) | 없음 | 없음 |
| 링크 접촉력 | ‖max(F - G, 0)‖², -1e-5, G = 체중 (P:215, 219, 245~246) | -1e-5, `robot_weight=400.0` (G1), 이력 평균, 2G 로 cap (RW:338~350; EC:524~531) | **robot_weight → Go2 체중 ≈ 158 N (측정값)** | 없음 |
| 링크 가속 | Σ‖v̇_l‖, -0.001 (P:221~223, 241) | -0.001, 유한차분 센서 `BodyAccelerationSensor`, 0.1 kg 미만 링크 무시 (RW:65~97; ACC; EC:532~536) | 0.1 kg 마스크면 Go2 발(0.04) 제외 → 논문 「전 링크」 면 임계 조정 | 없음 |
| 관절 한계 | 위치 0.95 · 속도 0.9 · 토크 0.8 초과분, -1000 · -1 · -1 (P:227~242) | 같음, 속도 · 토크 한계는 actuator cfg 에서 (RW:505~582; EC:538~549) | Go2 actuator: 23.5 N·m · 30 rad/s 전 관절(LAB-GO2) | URDF calf 45.43 과 다름 → 팀장 확인 |
| G1 상체 · 발 yaw 정형 | 없음 | `ame2_optional_uppershaping` -1, `ame2_optional_foot_yaw` -1 (EC:551~570) | **삭제**(사족 · 논문 밖) | 없음 |
| 종료: 자세 | |g_x| > 0.985 ∨ |g_y| > 0.7 ∨ g_z > 0 (P:376) | 같음, body `base`, start 0.2 s (TM:37~76; EC:577~586) | body `base` | 없음 |
| 종료: 몸통 충돌 | base 접촉력 > 체중 (P:377) | threshold **400 N**, body torso_link · pelvis_contour_link, 이력 평균, start 1.0 s (TM:81~107; EC:597~604) | body → `base` (+ Head_upper · Head_lower 포함 여부는 설계 선택), threshold → **체중 ≈ 158 N** | 없음 |
| 종료: 허벅지 가속 | 발 접촉 중 허벅지 가속 > 임계, 개 60 m/s² · 사람 100 (P:378) | threshold 100 (G1), body `.*hip_pitch_link` ↔ 발 `.*ankle_roll_link` 수 일치 assert · 인덱스 순서로 짝 (TM:111~177; EC:587~596) | **60 m/s²** (논문 사족), body `.*_thigh` ↔ `.*_foot`. 짝 순서(FL · FR · RL · RR) 가 asset 과 sensor 에서 같은지 TM:156~161 출력으로 확인 | 60 이 Go2 실기에 안전한지 미측정 |
| 종료: 정체 | 5 s 동안 0.5 m 미만 이동 ∧ 목표 > 1 m (P:379) | 같음 (TM:180~230; EC:605~613) | 없음 | 없음 |
| 종료: 시간 | 에피소드 길이 (P:277 t_left) | 16 s, `time_out=True` (EC:576, 675) | 없음 | 에피소드 길이는 논문 미기재(코드 근거) |

### 1.6 지형 · 커리큘럼

공식 코드 지형 cfg(TR:14~289): 타일 12 × 12 m, 10 행(난이도) × 60 열, horizontal_scale 0.1, vertical_scale 0.005, border 10 m, `max_init_terrain_level` 5(teacher) · 9(student) (EC:51, 772). 비율은 논문 Appendix A 와 같다: rough 5 · stair_down 5 · stair_up 5 · boxes 5 · obstacles 5 · climb_up 20 · climb_down 5 · consecutive 5 · gap 5 · pallets 5 · stones 30 · beam 5 (%). pit · peak · test_1 · test_2 는 proportion 0.

| 지형 | 논문 ANYmal-D (P:1114~1130) | 논문 TRON1 | 공식 G1 코드 (TR) | Go2 |
|---|---|---|---|---|
| Rough | 잡음 ±0 → ±0.2 m | ±0.15 | 거칠기 0 → 0.16 m + 경사 0 → 20° (undulation 3 m) (TR:24~40; CT:105~156) | **팀장 결정**. Isaac Lab Go2 rough cfg 는 「로봇이 작아서」 잡음 (0.01, 0.06) 으로 축소한 전례(LAB-GO2-ENV:24~26) |
| Stair up/down | 경사 5° → 45° | 같음 | step 0.05 → 0.27 m, 폭 0.27~0.35, 통로 0.8~1.8, 벽 확률 0.35, 바닥 -1.5~0 (TR:41~70; CT:159~357) | 팀장 결정 |
| Boxes | 최대 높이 0.05 → 0.4 | 0.05 → 0.3 | 0.05 → 0.3, 20 상자 0.8~2.0 m (TR:71~89) | 팀장 결정 |
| Obstacles | 밀도 0 → 0.5 m⁻² | 같음 | 0 → 0.5, 높이 0.2~2.0, 크기 0.3~0.8 (TR:90~109) | 밀도는 로봇 무관 · 크기는 결정 |
| Climb up | 0.1 → 1.0 m | 0.1 → 0.48 | 0.1 → 0.65, 4~5 상자 벽, yaw ±45°·난이도 (TR:110~126; CT:28~103) | 팀장 결정 |
| Climb down | 0.2 → 1.0 | 0.2 → 0.88 | 0.2 → 0.88 (TR:127~143) | 팀장 결정 |
| Consecutive | 1 층 0.05 → 0.5, 2 층 0.05 → 0.4 | 0.05 → 0.3 · 0.3 | 0.05 → 0.35 · 0.35, up-up-down-down 벽 4 개 (TR:144~161; CT:687~785) | 팀장 결정 |
| Gap | 0.1 → 1.1 m, 양쪽 높이차 ±30 % | 0.1 → 0.6 | **0.18 → 1.2**, 높이차 ±25 %, 바닥 확률 0.5 (TR:162~178; CT:787~828) | 팀장 결정 |
| Pallets | 폭 0.4 → 0.16, 틈 0.08 → 0.35, 높이차 0 → 0.3 | 틈 0.08 → 0.2, 높이차 0 → 0.2 | 폭 0.4 → 0.16, 틈 0.16 → 0.24, 높이 0 → 0.2 (TR:179~196; CT:882~962) | 팀장 결정 |
| Stones | 「StonesEverywhere」 [26][15] | 같음 | 상자 0.71 → 0.41, 틈 0.08 → 0.12, 높이 0.06, 가라앉음 6 % · 솟음 4 % (TR:211~231; CT:964~1090) | 팀장 결정 |
| Beam | 폭 0.9 → 0.18, rpy ±0.1 rad, 높이차 ±0.2 | 같음 | 폭 0.5 → 0.17, max_rpy 0.087, 높이차 ±0.05·난이도 (TR:197~210; CT:830~880) | 팀장 결정 |

Go2 축척 원칙(값은 결정 사항): 커리큘럼 시작값(0.05~0.2 m) 은 두 로봇에서 거의 같으므로 유지하고, **각 지형의 최댓값 하나** 만 Go2 로 정한다. 논문은 로봇마다 다른 최댓값을 썼으므로 「Go2 열」 은 논문 재현이 아니라 로봇 적응이며, 선택한 값과 이유를 표로 남긴다. 희소 지형 바닥(물리 0.5 확률, -1.5~-0.65 m) 과 가상 바닥 문제는 §2.

### 1.7 도메인 랜덤화

| 항 | 논문 (P:1140) | 공식 코드 | Go2 |
|---|---|---|---|
| 적재 | ±5 kg (두 로봇) | base 질량 add (-1.0, 3.0) kg, torso_link (EC:338~346) | body → `base`. 범위는 **팀장 결정**: 논문 ±5 는 base 6.9 kg 대비 과대할 수 있음(코드 `min_mass` 1e-6 클램프, EV:232). 후보 ±5(논문) · (-1, 3)(코드) |
| 마찰 | [0.3, 1.0] | static · dynamic (0.3, 1.0), restitution 0, 64 bucket (EC:326~336) | 없음 |
| 액추에이터 지연 | [0, 0.02] s | `delay_range (0, 1)` step = 0 또는 20 ms (AC:20~73; EC:169~176) | 없음 |
| PD · armature | TRON1 만 ±15 % (ANYmal 은 actuator net) | stiffness · damping · armature scale (0.85, 1.15) (EC:357~368; EV:531~591) | Go2 는 actuator net 없이 DCMotor PD 이므로 TRON1 쪽(±15 %) 을 따르는 것이 자연스러움 · 기록 |
| CoM | 없음 | torso ±0.02 · ±0.02 · ±0.04 m (EC:348~355) | 코드 전용 → §2 |
| reset | heading 커리큘럼 외 미기재 | pose ±0.2 m · yaw 커리큘럼, 속도 ±0.5, 관절 기본값 × (0.5, 1.5) (EC:374~397) | 없음 |
| student 깊이 손상 | 점 15 % 결손 · 2 % artifact (P:1142) | lidar `add_noise` 는 **항등 함수 placeholder** (LD:65~81) → 미구현 | 깊이 카메라 판에 구현(§5 U13) |
| 보조 상승력 | 없음 | `assistive_force` 이벤트는 있으나 그 커리큘럼이 CurriculumCfg 에 없어 **무동작** (EC:399~405; EV:668~690; CU:385~443) | 삭제 |

### 1.8 PPO · 학습 일정

| 항 | 논문 Table IV (P:1152~1157) | 공식 코드 (CF:148~186 · MZ agent.yaml) | 따를 값 |
|---|---|---|---|
| value loss coef · clip | 1.0 · 0.2 | 1.0 · 0.2 | 1.0 · 0.2 |
| entropy | 0.004 → 0.001 감쇠 | 0.004, 매 반복 ×0.9999, 하한 0.001 (PPO:538~541) | 논문 값 · 감쇠 방식은 코드(논문 미기재) |
| epoch · minibatch | 4 · 3 | 5 · 4 | **논문 4 · 3** (§4 메모리 제약은 accumulation 으로) |
| steps/iter | 24 | 24 | 24 |
| env 수 | 4800 | 4096 기본, 모델주 64000 (4 GPU × 16000) | 예산 사항(§4) |
| lr · 스케줄 | adaptive | 1e-3 adaptive KL 0.01, [1e-5, 1e-3] | 같음 |
| γ · λ | 0.99 · 0.95 | 0.99 · 0.95 | 같음 |
| optimizer | 미기재(RSL-RL 관례 Adam) | **muon**(hybrid Muon/AdamW) (CF:86) | 논문 쪽 Adam 기본, muon 은 스위치(§2) |
| 정밀도 | 미기재 | bf16 autocast(update 순전파만) (CF:89; PPO:341~346) | 메모리상 필요하면 켬 · 기록(§4) |
| max_grad_norm | 미기재 | 1.0 | 1.0 |
| 대칭 증강 | critic 에만 (P:193~199) | `for_critic_only: True`, G1 함수 (CF:180~185; SY) | **Go2 대칭 함수 신설**(§3) |
| teacher 반복 | 80000 (P:399) | 5000(cfg) · 모델주 2400 | 논문 80000 이 기준 · 예산은 §4 |
| student 반복 · surrogate off | 40000 · 첫 5000 (P:399) | max 20000, `rl_switch_point` 4001 (CF:115, 222) / 클래스 기본 5001 (IL:42) | **논문 5000** |
| student 증류 손실 | 행동 증류 0.02 · 표현 MSE 0.2 · surrogate off 때 lr 0.001 (P:1157) | imit = -log π_S(a_T) × 0.02; repr = MSE(attn96) + MSE(global64) × 0.2; 전환 때 lr → 1e-5 뒤 adaptive (IL:34~75, 139~145, 205~208) | 코드 그대로(논문 계수와 일치) |
| student 기타 | 미기재 | min_ent 0.0005, renorm_max_value_loss 20 (CF:236~237) | 코드 |
| 체크포인트 | 미기재 | save_interval 2000 | 운영 선택 |

### 1.9 Neural mapping (논문 V 절) · 공개 여부

| 구성 | 논문 | 공식 코드에 있는 것 | 없는 것 |
|---|---|---|---|
| 투영 | 셀마다 최대 z, 빈 셀 고정 최솟값 (P:408) | lidar 판 `_build_em_from_lidar`: amax scatter, 빈 셀 -3, clamp [-3, 2] (NM:205~258) | 깊이 카메라 판 투영(ANYmal 2 대 · TRON1 1 대, P:622~625) |
| 모델 | 얕은 gated U-Net: 2×conv16 k3 p1 → maxpool k3 s3 → upsample → concat → 2×conv16 → 1×1 세 갈래(불확실도 log-var · raw 추정 · gate sigmoid), 출력 = gate 혼합 (Fig.7, P:531~563, 596~606) | JIT 로드만 (NM:50~58) | **가중치 `ame2/NN_models/g1LivoxMapping_perframe.pt` 없음(디렉터리 자체 없음 · 확인)** · 모델 정의 · 학습 코드 없음 (RM:46~47, 55~58) |
| 학습 | 54 M 프레임, 1 시간 미만/모델; Warp raytracing 으로 메시 위 임의 자세 샘플; 증강(셀 잡음 · 테두리 크롭 · 센서 자세 · FOV 가림 · 거리 clip · 결손 · 이상치); β-NLL β 0.5 (Eq.9); TV 샘플 가중(Eq.10); 메시 4 종(보행 지형 · 쌓은 상자 · 임의 heightfield · 떠 있는 상자) (P:489~619, Fig.6) | 가림 보조 함수 `add_occlusion_straight(_batched)` (NU:827~915) | 데이터 파이프라인 · 손실 · 학습 루프 |
| 융합 | σ̂² = max(σ², 0.5σ²_prior) (Eq.6); 유효 조건 σ̂² < 1.5σ²_prior 또는 σ̂² < 0.2² (P:454, 「0.22」 는 0.2² 의 추출 오류로 읽음 · 코드 0.04 와 일치); p_win = 정밀도 비 (Eq.7); 확률적 덮어쓰기 (Eq.8) | **`BatchedGlobalProbWinnerPipeline.step` 이 Eq.6~8 그대로**: tau_min 0.5, `R_eff < P·(1+0.5)` or `< 0.04`, p = prec/(prec+prec_prior), rand 비교 (NU:358~379). lidar 판은 1.25 · hole -3 · anti-erase (NU:681~710) | 없음 |
| 전역 지도 초기화 | 서 있는 높이의 평지 + 큰 불확실도 (P:409) | h_bias(-0.5) + z, init_var 100 (NU:46~65, 265~266) | Go2: h_bias = -서 있는 높이 |
| 질의 | 최신 전역 지도에서 egocentric 격자 (P:482) | depth 판: 평균 bilinear · 분산 nearest · clamp ±2 (NU:381~418); lidar 판: nearest · OOB = 미관측 (NU:717~748) | 없음 |
| 시뮬 비용 | ANYmal 1000 env: 추론 < 0.3 ms · 3 GB, 전역 지도 8×8 m 0.3 GB, 깊이 구름 등 1.2 GB (P:621) | inference_chunk 2048 (NM:287~299), 10 Hz 갱신 (EC:779~788) | Go2 실측 없음 |
| 실기 | 프레임당 ~5 ms CPU(ONNX 2.5 ms), 정책 2 ms (P:402, 622); odometry CompSLAM+GraphMSF · DLIO; student 에서 선속도 관측 제거 (P:626~627) | 없음 | Go2 온보드 계산기 · odometry 선택 미확인 |

### 1.10 제어 · 배포 주기

- 정책 50 Hz (P:90; 코드 dt 0.005 × decimation 4, EC:674~677). 실기 PD 400 Hz (P:90). 접촉 센서는 물리 step(0.005) 마다 이력 4 (EC:83~85, 687). teacher scanner 는 정책 step 마다(EC:684~685). student 지도 센서 10 Hz 갱신 + 매 정책 step 질의 (EC:776~788; NM:118~170).
- 배포: 논문 ONNX Runtime · i7 CPU 2 ms (P:402); 코드는 JIT 만(ONNX 미구현). Go2 EDU 온보드 계산기 · D435i 프레임률은 로컬 자료에 없음 → 측정 필요.

---

## 2. 논문과 공식 코드의 차이 · 따를 쪽

### 2.1 코드에 있고 논문에 없는 것

| 항목 | 위치 | 판단 |
|---|---|---|
| Gaze(TAGA) 모델 · 모델주 checkpoint 가 Gaze | AM:390~839; MZ agent.yaml `AME2GazeModel` | 쓰지 않음. 논문 모델은 `AME2Model`(dense) |
| multi-head critic(보상 항마다 value head) 기본 켜짐 | PPO:35~36, 650~668 | **끔(K=1)**. 논문 critic 은 단일 MoE 가치. 코드 cfg 에 `multi_head_critic: False` 를 명시 |
| muon optimizer | CF:86; `rsl_rl/utils/muon.py` | Adam 기본(RSL-RL 관례 · 논문 Table IV 「RSL-RL conventions」). muon 은 재현 비교용 스위치로 남김 |
| bf16 autocast | CF:89 | 메모리상 필요하면 켬(§4) · 켠 사실을 영수증에 |
| 전방 원뿔 goal 커리큘럼 10° → 45° | EC:632~639 | 유지 가능(논문 「AOT/EOT」 샘플링의 Isaac Lab 구현 보조). 기록 |
| CoM 랜덤화, reset 속도 ±0.5, 관절 × (0.5, 1.5) | EC:348~355, 374~397 | 유지 · 기록 |
| G1 상체 · 발 yaw 정형 보상 | EC:551~570 | 삭제(사족) |
| assistive force(무동작) · PLAY 의 `push_robot = None` | EC:399~405, 746 | 삭제 |
| 스텀블 1.1·f_z + 1 N, 미끄러짐 0.3 m/s · 0.025 s, 구멍 채움 U(0.65, 1.5), 접촉 1 N 임계, u 변환식 | RW · OB | 코드 값 채택(논문은 정성 서술 · 미기재) |
| 자가 충돌 센서 3 개(쌍 필터) | EC:98~128 | Go2 용 쌍으로 재구성 |
| 지도 xy 잡음 1 mm | EC:234 | 유지(무시 가능) |
| Mid360 lidar 경로 전체 | NM · LD | **Go2 는 깊이 카메라(D435i) → 논문 Fig.5 깊이 판을 따름**. lidar 판 융합(1.25 · hole -3) 대신 `BatchedGlobalProbWinnerPipeline`(Eq.6~8) |

### 2.2 논문에 있고 코드에 없는 것

| 항목 | 논문 | 판단 |
|---|---|---|
| 지도 모델 가중치 · 정의 · 학습 코드 | P:489~619 | **우리가 구현**(§5 Stage 3). README 가 「다음 공개 때」 라 적음(RM:55~58) |
| 깊이 구름 15 % 결손 · 2 % artifact | P:1142 | 구현(코드 `add_noise` 는 항등) |
| 가상 바닥(지도에 보이나 충돌 없음) | P:1131~1133 | 코드는 「바닥 없음 + 구멍을 유효 최솟값 - U(0.65, 1.5) 로 채움」 으로 근사. 논문대로 하려면 raycast 대상 메시와 충돌 메시를 분리해야 한다(Isaac Lab TerrainImporter 는 단일 `/World/ground`). **1 차는 코드 근사 유지 · 2 차 과제로 기록** |
| ANYmal actuator net · TRON1 DC 모터 식별 · 토크-속도 clip [77] | P:403 | Go2 는 Isaac Lab DCMotorCfg(saturation 23.5 · velocity 30) → 토크-속도 제한은 DCMotor 모델이 담당. 실기 식별값은 미확인 |
| 깊이 카메라 2 대 병합(ANYmal) | P:622~625 | Go2 는 1 대(D435i) · TRON1 쪽과 같음 |
| ONNX 배포 | P:402 | 코드 미구현 → 배포 단계 과제 |

### 2.3 서로 어긋나는 값 · 따를 쪽과 이유

| 항목 | 논문 | 코드 | 따를 쪽 · 이유 |
|---|---|---|---|
| PPO epoch · minibatch | 4 · 3 (Table IV) | 5 · 4 | **논문**. Table IV 가 실험값이고 코드는 G1 예제 기본값. 단, 16 GB 에서 minibatch 3 은 활성 메모리가 넘친다 → gradient accumulation 으로 「유효 minibatch 3」 을 지킨다(§4). 못 지키면 바꾼 값 · 이유를 영수증에 |
| surrogate off 반복 | 5000 | 4001 (cfg) · 5001 (기본) | **논문 5000** |
| 과회전 임계 | 2.0 rad/s (odometry 드리프트 근거) | 3.0 | **논문 2.0** (근거가 적혀 있음) |
| 지도 질의 drift | ±0.03 | teacher ±0.04 (xyz) · student 0.03 | **논문 0.03**. teacher scanner `drift_range (-0.03, 0.03)` |
| 지도 잡음 · heading 커리큘럼 길이 | 첫 20 % 반복 | 2000 반복(5000 의 40 %) | **논문 규칙(20 %)**: `max_steps = 24 × (teacher 반복 수 × 0.2)` |
| 완전 지도 env 의 분산 | 0.0025 m² | `clean_source_unc` 0.05(분산 자리) | **논문 0.0025**. 코드 0.05 는 표준편차를 분산 자리에 넣은 것으로 보임(u 변환이 log 분산을 쓰므로 차이가 남, OB:237~238). 기록 |
| 손상 점 분산 | > 1 m² | unc U(0.3, 1.3) | **논문**: 분산 하한 1.0 (예 U(1.0, 2.0); 상한은 u clip 2.0 과 맞춤) |
| teacher proprio 잡음 | IV-B 「잡음 없는 proprio」 (P:179~181) vs Appendix B 잡음 목록 (P:1141) | teacher 그룹 잡음 켜짐(EC:265), student 단계에서는 teacher 관측 잡음 제거(EC:806~812) | **코드(잡음 켬)**. Appendix B 가 수치까지 적은 명시 사양이고 같은 저자의 코드가 그렇게 구현했다. 논문 내부 모순을 기록 |
| 허벅지 가속 임계 | 사족 60 · 이족 100 | G1 100 | **60**(사족) |
| 몸통 충돌 임계 | 체중 | 400 N(G1) | **체중(Go2 ≈ 158 N, 측정값)** |
| 적재 | ±5 kg | (-1, 3) kg | 팀장 결정(§1.7) |
| 융합 유효 조건 | 1.5 σ²_prior | depth 판 1.5 · lidar 판 1.25 | **depth 판(= 논문)** |
| 전역 지도 크기 | 8 × 8 m | depth 판 기본 20 m · lidar 6 m | 논문 8 m(메모리 §4) |
| 지도 모델 입력 격자 해상도 | 4 cm | lidar 3 cm | 논문 4 cm(깊이 판) |

---

## 3. G1 → Go2 이식 목록

공식 task 패키지에서 G1 에 묶인 항목 전부와 Go2 대체물. 「측정」 은 U0 프로브로 채운다.

| # | G1 항목 (위치) | Go2 대체 | 근거 |
|---|---|---|---|
| 1 | `G1_CFG` (AS:12~177; EC:698) | `UNITREE_GO2_CFG` (LAB-GO2:140~181) 를 복제해 `enabled_self_collisions=True` 로 바꾼 `GO2_AME2_CFG`. solver 반복 4/0 유지 여부는 측정 뒤 결정(G1 은 6/1) | LAB-GO2; 자가 충돌 보상(P:371) |
| 2 | 관절 23 · `.*` 액션 (EC:169~176) | 관절 12 · `.*`, scale 0.25, use_default_offset, delay (0, 1) 그대로 | LAB-GO2-ENV:29 도 0.25 |
| 3 | 기본 관절각 (AS:29~47) | LAB-GO2:157~166 (hip ±0.1, thigh 0.8/1.0, calf -1.5) → `joint_pos_rel` 기준 · `d_q` 서기 기준 | LAB-GO2 |
| 4 | 액추에이터 DCMotor 11 그룹 (AS:49~176) | `base_legs` DCMotor 1 그룹: effort 23.5 · saturation 23.5 · velocity 30 · kp 25 · kd 0.5 · armature 미지정 | LAB-GO2:169~179. URDF calf effort 45.43 · velocity 15.7 과 다름 → 팀장 확인 |
| 5 | `torso_link` (move2goal · roll rate · 질량 · CoM · assistive) | `base` | U:3 |
| 6 | `base`(자세 종료 body) (EC:580) | `base` | 같음 |
| 7 | 발 `.*ankle_roll_link` (서기 · 도약 · 허벅지 가속 짝) | `.*_foot` | U:202~226 |
| 8 | 허벅지 `.*hip_pitch_link` (EC:591) | `.*_thigh` | U:98~123 |
| 9 | 비발 접촉 body `^(?!.*ankle\|d435_link\|mid360_link).*_link` (EC:465) | `^(?!.*_foot).*` (base · hip · thigh · calf · Head_*) | 논문 「비발」 |
| 10 | 스텀블 · 미끄러짐 · 접촉력 · 가속 body `^(?!d435_link\|mid360_link).*_link` | `.*` | 논문 「전 링크」 |
| 11 | 몸통 충돌 종료 `torso_link` · `pelvis_contour_link` 400 N (EC:597~604) | `base` (Head_upper · Head_lower 포함은 설계 선택), threshold = 측정 체중 | P:377 |
| 12 | `robot_weight=400.0` (EC:530) | 측정 체중(URDF 추정 157.8 N) | P:245~246 |
| 13 | `offset`/`elevation_offset` 0.74 (EC:219, 234, 795, 850) | 측정 서 있는 높이(추정 0.33) | OB:134 |
| 14 | `contact_states` mass_threshold 0.1 · ignore_bodies 4 개 (EC:206~215) | 임계 0.03(발 0.04 kg 포함) · ignore 없음(또는 `imu` 류 질량 0 은 자동 제외) | 논문 「각 링크」 |
| 15 | 자가 충돌 센서 knee · ankle · torso (EC:98~128) | Go2 쌍 센서(§1.5) | 설계 선택 |
| 16 | `add_base_mass` (-1, 3) torso (EC:338~346) | `base`, 범위 결정 | §1.7 |
| 17 | `base_com` torso (EC:348~355) | `base` | 코드 전용 항 |
| 18 | `undesired_spinning` head_link 3.0 (EC:445~449) | `base`, 2.0 | P:303 |
| 19 | `early_hip_acc` 100 (EC:587~596) | 60 | P:378 |
| 20 | 격자 size [2.0, 1.12] offset 0.5 (EC:71~96) | 후보 B 그대로 또는 A([2.8, 1.04], 0.6) | §1.3 |
| 21 | `AME2_TERRAINS_CFG_G1` (TR) | `AME2_TERRAINS_CFG_GO2`: 비율 · 종류 · 커리큘럼 시작값 유지, 최댓값 결정 | §1.6 |
| 22 | `ame2_g1_symmetry_augmentation` (SY:16~224, 관절 23 · 접촉 26 · 격자) | `ame2_go2_symmetry_augmentation`: 관절 12 짝(FL↔FR, RL↔RR; hip 부호 반전, thigh · calf 부호 유지), critic 레이아웃 9 + 3×12 + 4 + 1 + C + L·W, 접촉 C 의 좌우 짝, height scan y 뒤집기 | 측정 관절 · body 순서 필요(U0) |
| 23 | student 센서 Mid360 (`mid360_link`, 20k ray) + Livox 지도 (EC:774~788) | D435i 깊이 패턴(NU:936~967 `realsense_grid_pattern` 48×27 · 80° · 4 m) + 깊이 판 융합 센서(신설) · 장착 자세 측정 | §5 U13 |
| 24 | gym id `Ame2-G1*` (tasks/__init__.py) | `Ame2-Go2`, `Ame2-Go2-Play`, `Ame2-Go2-Student`, `Ame2-Go2-Student-Play` | 운영 |
| 25 | viewer eye (EC:704) | Go2 크기에 맞게 | 운영 |
| 26 | `rsl-rl-lib` 5.0.0 번들(`rsl_rl/pyproject.toml:6~7`) 이 설치본의 stock rsl-rl-lib 를 대체(`container/Dockerfile:15~19`) | 우리 Isaac Lab python 환경의 rsl_rl 교체는 **다른 프로젝트(go2_rl_robotlab 의 rsl_rl) 와 충돌** 가능 → 전용 venv 또는 되돌림 절차 | 운영 위험 |

측정 필요(U0 산출): articulation 관절 순서 · body 순서, contact sensor body 순서, `default_mass` 와 합, 기본 자세로 1 s 정착 뒤 base 높이, 발 접촉 임계 1 N 에서 네 발 접촉 플래그, D435i 장착 좌표.

---

## 4. 16 GB 메모리 · 처리량 위험

전부 추정이며 실측 전이다. 정책 = 「방법을 줄이지 않는 선택」 을 먼저 쓰고, 안 되면 예산(env 수 · minibatch 수) 을 바꾼 사실을 적는다. 논문 사용값: 4800 env · 24 step · 3 minibatch(P:1156), ANYmal-D 전체 60 RTX-4090-일 / 8 GPU, TRON1 30 / 4 GPU (P:399, 1106). 모델주 참고: 64000 env(4 GPU × 16000) · 2400 반복 · 10 h, Gaze 모델(120 셀) · GPU 종류 미기재(MZ).

### 4.1 PPO update 의 attention 활성 메모리(가장 큰 위험)

- 미니배치 표본 수 S = N·24/M. N 4096 · M 3 → 32768; M 4 → 24576.
- AME-2 지도 경로가 역전파용으로 저장하는 활성 폭(셀당 float 수, 추정): fc 16 + conv 8 + conv 48 + concat 64 + local 96 + pool 은닉 64 + pool 출력 64 + K 96 + V 96 ≈ 552, ELU 입력 저장을 더해 **≈ 600 float/셀** 로 잡는다.
- 메모리 ≈ 600 × 셀 × S × 4 B(fp32). 셀 390 (후보 B): S 32768 → **30.7 GB**, S 24576 → 23 GB. 셀 504 (후보 A): ×1.29. bf16 autocast 는 약 절반.
- 그러므로 4096 env · M 3 은 16 GB 에 들어가지 않는다(추정). 선택지:
  1. **gradient accumulation(방법 보존)**: 미니배치 하나를 micro-batch k 개로 나눠 순전파 · 역전파를 누적하고 optimizer step 은 미니배치마다 1 회. 손실 평균(micro 평균 × 표본 수 가중), KL 적응(inference_mode 로 micro 마다 계산 뒤 평균해 lr 갱신), value renorm, clip 은 미니배치 단위를 유지한다. S 32768 / k 8 → 4096 표본 → 3.8 GB(fp32, 셀 390). PPO 클래스에 `micro_batches` 인자를 더하는 코드 변경이며 Table IV 는 그대로다.
  2. M 을 12~16 으로 올림(하이퍼파라미터 변경 · epoch 당 optimizer step 4~5 배) → 영수증 기록.
  3. bf16 autocast(코드 제공) · 켠 사실 기록.
  4. env 수 축소(예산 변경 · 논문 4800 대비) → 기록.
- `mha_math`(MD:6~17) 가 math 커널을 강제하므로 bf16 fused 커널 결함과 무관하지만, math 커널은 attention 점수 (S × 32 head × 1 × 셀) 텐서를 그대로 만든다(S 32768 · 셀 390 → 1.6 GB fp32). 위 추정에 포함.

### 4.2 롤아웃 저장 · 물리 · 센서

- teacher 저장(N 4096 · 24): env-step 당 float ≈ 지도 390×3 + prop 49 + critic 457 = 1676 → 6.7 KB → **0.66 GB**(후보 A 0.84 GB). student: 지도 390×4 + 이력 20×42 + cmd 4 + critic 457 + teacher 관측(증류용 49 + 1170) = 4360 → **1.7 GB**.
- Go2 4096 env 물리는 이 기기에서 전례가 있다(E1 4096 env, 메모리 기록). height scanner 2 개 × 390 ray × 4096 = 3.2 M ray/step. 지형 메시(10 × 60 타일, 돌 지형 180 타일 × ~576 상자) 는 수백만 삼각형 → 코드가 `gpu_collision_stack_size 2^27`, `gpu_max_rigid_patch_count 20·2^15` 로 올림(EC:680~682). Go2 축척에서 상자 수가 늘면(돌 상자 0.41 m → 더 작게) 더 는다 → 측정.
- MoE critic 16 expert × MLP_512(457) 는 미미(≈ 16 × 0.5 M 파라미터).
- 디스플레이 GPU: GPU 0 이 화면을 구동하면 가용 VRAM 이 1~2 GB 줄고(메모리 기록 「GPU 메모리는 장치 전체 값」), headless 학습은 GPU 1 이 안전. 두 GPU 를 함께 쓰려면 코드의 `--distributed`(torchrun, TN:132~140; RN:231~273) 로 env 를 나눌 수 있다(모델주가 4 GPU 로 그렇게 함).

### 4.3 student 단계의 지도 모델

- 논문 ANYmal 1000 env 기준 추론 3 GB + 전역 지도 0.3 GB + 깊이 구름 등 1.2 GB = 4.5 GB/1000 env (P:621) → 4096 env 단순 비례 **≈ 18 GB** → 정책 · 물리를 빼고도 16 GB 초과. 선택지(방법 보존 순): (가) Go2 입력 격자가 ANYmal 51×31 보다 작으면 비례 축소(격자 결정 뒤 재추정); (나) 추론 chunk(코드 inference_chunk 2048, NM:287~299) 로 일시 활성 축소(전역 지도 상주분은 줄지 않음); (다) **지도 모델 · 융합을 GPU 1 에 두고 시뮬 · 정책을 GPU 0 에**(10 Hz 마다 4096 × 1296 ray × 3 float ≈ 64 MB 전송) → 구현 과제; (라) student env 수 축소(예산 변경) → 기록. 논문도 student 단계가 teacher 의 절반 속도 · 더 많은 메모리라고 적었다(P:251).

### 4.4 반복 수와 벽시계

- teacher 80000 반복: 반복 시간 T 를 측정해 80000·T. 예: T 5 s → 4.6 일, 10 s → 9.3 일, 20 s → 18.5 일(GPU 1 장). 논문은 8 GPU 로 ANYmal 전체 7.5 일 벽시계. 2 GPU 분산이면 약 절반. **T 는 미측정 · U5 에서 1024 · 2048 · 4096 env 로 잰다.**
- student 40000 반복 + 지도 모델 학습(논문 54 M 프레임 · 1 시간 미만/모델, 4090 1 장).
- 「반복 수를 줄이는 것」 은 예산 변경이지 방법 변경이 아니다. 줄이면 논문의 80000/40000 과 함께 적는다.

---

## 5. 단계별 구축 계획 (mai-code 단위 · CPU 오라클 · sol 통합)

원칙: 공식 코드 함수 · 모델 · 알고리즘은 **복사해서 그대로** 쓴다(`official-vs-port` 등가성은 「같은 함수」 라서 자명하고, 바뀐 것은 cfg 와 Go2 전용 함수만). CPU 오라클은 Kit 없이 돌 수 있는 순수 torch 조각에만 건다. `isaaclab.*` 를 import 하는 조각(mdp 함수 · cfg · 지형) 은 **가짜 모듈로 시험하지 않는다**(메모리 기록: 가짜 cfg 시험 328 PASS 뒤 실제 Kit 6 초 실패). 그 조각은 sol 이 Kit headless 스모크로 잰다. 순서는 팀장 지시대로 teacher(GT 지도) → LSIO student → mapper.

### Stage 0 · 자산 · 환경 준비

| 단위 | 범위 | 산출 | 오라클 · 확인 | 담당 |
|---|---|---|---|---|
| U0-A Go2 프로브 | Kit headless, 1 env, `GO2_AME2_CFG` 로 스폰 · 1 s 정착 | `go2_asset_facts.json`: joint_names 순서, body_names, contact sensor body 순서, default_mass(링크별 · 합), base 높이, 네 발 접촉(1 N), joint_pos_limits · actuator effort/velocity | 관절 이름 집합 = URDF 12 개; 질량 합이 URDF 16.087 kg 과 1 % 안(아니면 차이 기록); base 높이가 0.30~0.36 안(아니면 기록) | sol |
| U0-B 환경 | 전용 python 환경(venv 또는 별도 Isaac Lab python) 에 번들 `rsl-rl-lib` 5.0.0 과 `ame2_go2` 를 `--no-deps -e` 설치, 되돌림 절차 문서화 | 설치 영수증(`importlib.metadata.version`) | `python -c "import rsl_rl.models.AME2_models"` 성공 · 기존 go2_rl_robotlab 환경 무변경 확인 | sol |
| U0-C D435i 장착 | 실기 장착 좌표 · 각도 측정(없으면 URDF `front_camera` (0.327, 0, 0.043) 임시 · 「임시」 표기) | `go2_sensor_pose.json` | 팀장 확인 | 팀장 · sol |

### Stage 1 · teacher (GT 지도)

| 단위 | 범위 | CPU 오라클 | 담당 |
|---|---|---|---|
| U1 task 패키지 `ame2_go2` | 공식 `ame2` 복제 → `Ame2EnvCfg_Go2`(§3 표 전부) · `AME2_TERRAINS_CFG_GO2`(팀장 결정값) · gym id · PLAY cfg · `multi_head_critic False` · PPO 4·3 · 커리큘럼 20 % · drift 0.03 · 과회전 2.0 · 허벅지 60 · 체중 · offset | Kit 전 CPU 오라클 없음(isaaclab import). **정적 검사**: cfg 파일의 모든 `body_names`/`joint_names` 정규식이 U0-A 의 body/joint 목록에 1 개 이상 매칭(정규식 × 목록 CPU 검사, 가짜 모듈 아님 · 문자열만) | mai-code |
| U2 모델 등가 · 치수 | `AME2Model`(dmap 3, prop 49, out 12), `_TorchAME2Model` JIT(script) 동일 입력 → actions · attn · global **정확히 같음**(deepcopy, 허용 오차 0); `AME2LSIOModel`((B,20,42),(B,L,W,4),(B,4)) → (B,12), latent 96 · 64, hist Linear 입력 256; `MoEModel`(457 → 1) 16 expert; 파라미터 수 보고; 격자 후보 A · B 둘 다 | 위 등식 · 형상 | mai-code |
| U3 Go2 대칭 함수 | `ame2_go2_symmetry_augmentation`(critic 전용) | mirror∘mirror = identity(정확); 임의 관측에 대해 손으로 쓴 사상과 일치; 접촉 C 짝 교환; height scan `(nx, ny)` y 뒤집기; 행동 12 짝; critic 길이 = 9 + 36 + 4 + 1 + C + L·W | mai-code (U0-A 순서 입력) |
| U4 PPO CPU 회귀 | rsl_rl `tests/` 패턴의 더미 VecEnv(TensorDict 관측 teacher_mapping (B,L,W,3) 등) 로 AME2Model + MoE critic + 대칭 증강 2 반복 | NaN 없음; K=1; save → load 재개 동일 손실; `micro_batches` 누적 구현 시 **k=1 과 k=4 의 gradient 가 fp32 에서 1e-5 안**(누적 정확성) | mai-code |
| U5 Kit 스모크 | `Ame2-Go2` 16 env: 관측 형상 출력(teacher_mapping (16, L, W, 3) · prop (16, 49) · critic (16, 457±)), contact 링크 목록에 발 4 개 포함, 허벅지↔발 짝 출력(TM:156~161) FL·FR·RL·RR 일치, 보상 항 수, PPO update 1 회 완료, **update 순간 VRAM**(nvidia-smi 0.5 s 샘플 · 메모리 기록 「실행 전만 재면 틀린다」); 이어서 1024 · 2048 · 4096 env 반복 시간 · VRAM 표 → §4 결정(micro-batch k · bf16 · env 수) | 산출: 표 · 선택 영수증 | sol |
| U6 teacher 학습 | 결정된 N · k 로 80000 반복(또는 예산 반복 수 · 기록), heartbeat(CronCreate) · 체크포인트 2000 · 지형별 성공률 로그(CU:373~375) · 두 GPU 분산 여부 | 평가: play 로 지형별 성공률 · 조기 종료 원인 분포 | sol |

### Stage 2 · LSIO student

| 단위 | 범위 | CPU 오라클 | 담당 |
|---|---|---|---|
| U7 teacher JIT 내보내기 | `play.py --export` (PL:638~660) → `go2_teacher.jit` | CPU 로드 → 학습 checkpoint 모델과 같은 입력에서 actions(mean) · attn · global 정확히 같음 | mai-code + sol |
| U8 student env cfg | `Ame2EnvCfg_Go2_Student`: obs 그룹 neural_map · student_prop_hist(20) · student_cmds, teacher 관측 무잡음, scanner drift 0, 지도 DR(질의 drift 0.03 · 완전 지도 10 % **분산 0.0025** · 손상 1 % **분산 ≥ 1**), 초기 레벨 0..9 | Kit 스모크(sol): `student_prop_hist` (16, 20, 42) 가 오래된→새로운 순서인지 **알려진 신호 주입**(예: 한 step 만 행동을 1.0 으로) 으로 확인 | mai-code · sol |
| U8-interim GT 지도 stand-in | 지도 모델이 없을 때 증류 기계 시험용: 공식 `clean_source_ratio=1.0` 경로(critic scanner z + 잡음 0.02, 분산 0.0025) 로 `neural_map` 4 채널 생성. 주의: 공식 센서는 초기화 때 JIT 지도 모델 파일이 없으면 `FileNotFoundError` 를 낸다(NM:50~54) → clean 비율 1.0 일 때 모델 로드를 건너뛰는 센서 변형이 필요(작은 코드 변경 · 기록) | **라벨: 「논문 student 가 아니라 Fig.16 「w/o uncertainty」 유사 중간판」**. 결과 보고 제목에 그렇게 쓴다 | sol · mai-code |
| U9 PPO_IL CPU 회귀 | 더미 env + 더미 JIT teacher(고정 선형) | 전환 전 `rl_coef` 0 · surrogate 0 · loss = 0.02·imit + 0.2·repr + value; student 분포 평균 = teacher 행동이면 imit = -log π(mean) · repr = 0; 전환 반복(5000) 에 lr 1e-5; 전환 뒤 surrogate 활성; checkpoint 에 `update_cnt` 저장 확인(IL 은 저장 안 함 → 재개 시 전환 시점 틀어짐 **위험**: `save()` 확장 필요) | mai-code |
| U10 student 학습 | 40000 반복(또는 예산 · 기록), 첫 5000 surrogate off | 평가 teacher 대비 성공률 | sol |

### Stage 3 · neural mapping (논문 V)

| 단위 | 범위 | CPU 오라클 | 담당 |
|---|---|---|---|
| U11 지도 모델 | Fig.7 gated U-Net(2×conv16 k3 p1 → maxpool k3 s3 → upsample → concat → 2×conv16 → 1×1 × 3: log-var · raw · gate sigmoid; out = gate·raw + (1-gate)·입력), β-NLL β 0.5 (Eq.9, σ 에 stop-grad), TV 가중 (Eq.10) | 격자 (1, H, W) → (mean, logvar) 같은 형상; gate 0 이면 출력 = 입력; β-NLL 을 손 계산 값과 1e-6 안; TV 가중 합 1; 합성 계단 데이터 200 step 학습에 손실 감소 · 가린 셀 σ 증가 | mai-code |
| U12 데이터 합성 | 메시 4 종(보행 지형 · 쌓은 상자 · heightfield · 떠 있는 상자) 위 임의 자세 raycast(학습은 Warp GPU · 시험은 trimesh CPU 소량), 증강 7 종(P:493~495), 가림은 `add_occlusion_straight_batched`(NU:857~915) | 계단 heightfield 에서 가림 함수가 계단 뒤 셀을 -2 로 만드는지; 결손 · 이상치 비율이 지정값 ±1 % | mai-code |
| U13 깊이 센서 · 융합 센서 | D435i 패턴(NU:936~967) RayCaster + 15 % 결손 · 2 % artifact + 투영(셀 max z · 빈 셀 최솟값) + 지도 모델 추론(chunk) + `BatchedGlobalProbWinnerPipeline`(Eq.6~8, h_bias -0.33, 8 m) + egocentric 질의 → (est, var) | 융합 CPU 오라클: (prior 100, meas 0.01) 에서 p_win ≈ 0.9999; meas ≫ prior 는 절대 미채택; 재중심 roll 뒤 세계 좌표 질의 불변; 결정적 시드 재현. 센서는 Kit 스모크(sol): 평지에서 est ≈ 0 · var 감소 | mai-code · sol |
| U14 지도 모델 학습 | 54 M 프레임(또는 예산 · 기록), 1 GPU | 보류 지형 L_0.5(Table III 식) 보고 | sol |
| U15 student(지도 모델 포함) | U8 cfg + U13 센서, 40000 반복 | 논문 student 에 해당하는 결과 | sol |

### 교차 사항

- 영수증: 각 단계 시작 때 「논문 값 · 코드 값 · 우리 값 · 이유」 표를 고정하고, 학습 뒤 바꾸지 않는다(메모리 기록: 결과를 보고 보상을 바꾸면 새 실험).
- 재개 안전: student 전환 카운터 `update_cnt` 는 IL 이 저장하지 않는다(IL:62~75; PPO:573~583) → U9 에서 저장 · 로드 확장. 미확인 상태로 재개하면 전환이 다시 5000 뒤로 밀린다.
- GPU 두 장: teacher 분산(torchrun) 또는 teacher(GPU 1) + 지도 모델 데이터 합성 · 학습(GPU 0) 병행 → 「GPU 줄과 판단 줄을 나눈다」(메모리 기록).
- 라이선스: `ame2` GPL-3.0 파생 패키지 공개 범위는 팀장 결정.

---

## 6. 미확인 · 미기재 목록

- 논문 미기재(코드로 보충): 구멍 채움, 스텀블 1.1·f_z + 1 N, 미끄러짐 임계, 접촉 1 N, u 변환식, LSIO 층 폭, MoE 16, 에피소드 16 s, heading 범위 ±π/3, reset 분포, 전역 지도 재중심 비율 0.3, 지도 모델 은닉 활성화 · upsample 방식 · optimizer.
- 코드 미기재(논문으로 보충): 깊이 손상, 가상 바닥, 지도 모델 전체, ONNX.
- 측정 필요: Go2 관절 · body 순서, 질량 합, 서 있는 높이, 자가 충돌 쌍 효과, update VRAM(N · k · bf16), 반복 시간, 지도 모델 메모리(Go2 격자), D435i 장착 · 프레임률, Go2 온보드 계산기 · odometry.
- 팀장 결정: teacher 격자 후보 A/B, 지형 최댓값 11 개, 적재 범위, URDF calf 토크 45.43 대 Isaac Lab 23.5, Head_* 를 몸통 충돌 종료에 포함할지, GPL 범위, 예산(env 수 · 반복 수) 과 그 기록 방식.
- 이 문서는 정적 명세다. 어느 코드도 실행 · 수정하지 않았고, 선행 검토 두 편의 수치는 다시 재지 않은 채 참고만 했다.
