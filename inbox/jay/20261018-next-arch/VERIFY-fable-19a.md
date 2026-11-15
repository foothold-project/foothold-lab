> 분류: A/정책학습 · 논문 충실도 검증 (M1 MARG · M2 AME-2 대 b6 고정본)
> 작성: Fable 검토 세션 · 2026-10-18
> 근거: MARG v2 원문 `C:/Users/AI-WS01/s2_lab/_papers/2509.20036v2.txt` · AME-2 v3 원문 `_papers/2601.08485v3.txt` · AME-2 공식 코드 `_research_repos/ame2_minimal` @8beb9a68 · b6 고정본 `s2_lab/step1_18b_b6_frozen` · Isaac Lab `managers/observation_manager.py` · `utils/buffers/circular_buffer.py` · DESIGN-v2 · VERIFY-astra-18b·18e·18f·18g · PLAN-sol-m1-marg-estimator
> 요지: 두 판 모두 논문에서 「지형 encoder 층」 하나만 옮겼고, 논문이 의미 있다고 한 나머지 구성은 빠졌다. M1 은 추정기 · ReLU · critic 의 고도 특징 · 특권 상태 · 위험 지형이, M2 는 LSIO · teacher 와 student 두 단계 · MoE critic · 지도 embedding 정렬 · 불확실도 채널 · AME-2 보상 체계가 없다. M1 은 E1 위에서 거의 전부 복원할 수 있다. M2 는 공개 코드에 지도 모델이 없어 「teacher 등가판」 까지만 복원할 수 있고, 그 이상은 이번 공개판으로는 불가능하다
> 상태: 정적 검토 완료 · GPU · Isaac 미실행 · 어느 파일도 수정하지 않음 · 효과는 미확인

**판정: 팀장 원칙(「구성 요소를 축소하면 의미 없다」)으로 재면 b6 의 M1 · M2 는 둘 다 논문을 충실히 구현한 판이 아니라 「E1 + 그 논문의 지형 encoder 층 폭」 이며, M1 은 아래 1 번 사양대로 고치면 E1 을 유지한 채 MARG 의 네 신경망 · 세 보상 · 동시 학습을 전부 살릴 수 있지만, M2 는 공개 코드가 지도 모델과 student 학습을 내놓지 않았으므로 AME-2 의 teacher 단계까지만 살릴 수 있고 그것을 「AME-2 재현」 이라 부르면 틀린다.**

# Fable 19a · M1 · M2 가 원 논문의 구성을 지키는가

## 0. 검토 방식

- 두 논문 전문을 읽고, 논문이 **고유 기여 · ablation · 「essential」** 로 다루는 구성 요소를 전부 추렸다. 값이 논문에 없으면 「논문 미기재」 라고 쓰고, AME-2 는 공식 코드가 쓰는 값을 따로 적었다. 값을 지어내지 않았다.
- 우리 쪽은 b6 고정본을 행 번호까지 읽었다. 약칭은 아래 표와 같다. 행 번호는 모두 그 파일의 실제 행이다.
- 「상태」 열은 다섯 가지다: **같음** · **축소** · **없음** · **E1 이식과 충돌** · **다름(우리 변형)**.
- 「E1 호환」 은 「E1 의 기존 가중치를 전부 복사하고 새 입력 열만 0 으로 시작해 첫 행동이 E1 과 같게 유지할 수 있는가」 를 뜻한다. b6 의 `load_e1_weights` 는 지금 actor 첫 층만 그렇게 넓힌다(A:307~324, `+160`/`+16` 하드코딩). critic · teacher encoder 를 넓히려면 같은 규칙을 그 두 첫 층에도 일반화해야 한다. 이 일반화는 작은 코드 변경이고 수학적으로는 같은 트릭이다.

| 약칭 | 파일 |
|---|---|
| P1 | `_papers/2509.20036v2.txt` (MARG, 행 번호) |
| P2 | `_papers/2601.08485v3.txt` (AME-2, 행 번호) |
| AM / MD / IL / CF | ame2_minimal `rsl_rl/rsl_rl/models/AME2_models.py` / `modules/ame2_modules.py` / `algorithms/ppo_il.py` / `ame2/ame2/tasks/agents/rsl_rl_ppo_cfg.py` |
| AE / AO / AR / RM | ame2_minimal `ame2/ame2/tasks/ame2_env_cfg.py` / `mdp/observations.py` / `mdp/rewards.py` / `README.md` |
| A / G | b6 `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py` / `algorithms/moe_cts.py` |
| E / O / R / S / T / C / CM | b6 `tasks/go2/env_cfg.py` / `mdp/observations.py` / `mdp/rewards.py` / `step1_setup.py` / `mdp/terrains.py` / `rsl_rl_cfg.py` / `mdp/commands.py` |
| FR / FT / HG | b6 `mdp/foot_reward_step1.py` / `mdp/foot_train_step1.py` / `mdp/height_gap_step1.py` |
| L | b6 `scripts_rsl_rl/train_step1.py` |
| Lab | `C:/isaac/IsaacLab/source/isaaclab/isaaclab/` |

공통 전제(E1, 두 판 공통): actor 입력 77 = CTS latent 32 + single_obs 45 (A:151), single_obs = (ω3, g3, v*3, q12, q̇12, a12) (E:121~164, 238), student 이력 10 프레임 × 45 = 450 (E:161), critic 관측 275 (E:167~233; base_lin_vel 0:3 scale 2.0, contact_force 72:88 scale 1e-3 이력 최대 포함, height 88:275 clip ±1 × 2.5, 구멍 = +2.5 via HG:7~16 · O:52~56), 50 Hz (E:501~504), 명령 x · y ±1.0 · yaw ±1.5 (CM:353~360 의 iter 20000 단계, S:120~137 적용).

## 1. MARG (M1) 구성표

| 구성 요소 | 논문 값 · 근거 | 우리 현재 값 · 근거 | 상태 | 축소하지 않는 구현 · E1 호환 |
|---|---|---|---|---|
| 고유수용 관측 o_t | (ω, g, v*, q, q̇, a_{t-1}) = 45 (P1:66) | single_obs 45, 같은 항목 순서 (E:121~164, 238) | 같음 | 그대로 |
| 시간 이력 o^H_t | [o_t, …, o_{t−H}], **H = 5** (P1:66) → 6 프레임 | 추정기 자체가 없음. CTS student 는 10 프레임 450 을 MoE encoder 에 넣음 (E:161, A:162~169) | 없음 | 추정기 입력으로 **최근 6 프레임 × 45** 를 쓴다. Isaac Lab 이력은 항별(term-major) 로 평탄화되고 가장 오래된 것이 앞이다 (Lab `observation_manager.py:409~426`, `circular_buffer.py:80~90`). 그러므로 450 열에서 「끝 270 열」 을 자르면 틀리고, 항마다 (B,10,d) 의 마지막 6 프레임을 떠서 다시 이어야 한다. CPU 에서 답을 아는 입력으로 확인할 것. E1 호환: 새 모듈이므로 영향 없음 |
| 지형 입력 h_t | R187, 로봇 중심 1.6 m × 1.0 m, 상대 높이 ẑ = z_base − h (P1:67, 92~97) | 187 광선, 1.6 × 1.0, 0.1 m (E:64~71). 값은 clip(z_sensor − z_hit − 0.5, ±1) × 2.5, 구멍 +2.5 (HG:7~16, E:224~229) | 같음(기하) · 다름(부호 · 구멍 처리) | 기하는 논문과 일치. 구멍 +2.5 는 우리 계약이고 논문에는 구멍 처리 기재 없음. 지도 잡음(아래 DR 행) 은 별도 |
| Elevation net E_θ1 | 입력 ẑ 187 → **[128, 64, 16]**, **ReLU**, 출력 e_h ∈ R16 (P1:90~97, 648) | `MLP(187, 16, [128, 64], activation='elu')` (A:175). 활성화는 cfg 의 `elu` (C:46). 마지막 선형 뒤 활성화 없음 | 축소(활성화 다름) | 숨은 층을 ReLU 로. A:175 에서 모듈별 activation 인자를 `relu` 로 지정(E1 actor · critic · CTS 의 ELU 는 그대로). E1 호환: 영향 없음 |
| Estimator net E_θ2 | o^H_t → **[258, 128, 7]**, ReLU, 출력 (v̂ 3, ĉ 4) (P1:101~112, 648) | **없음** (A 전체, G:376 손실에 회귀 항 없음) | 없음 | 아래 4.1 참조. 논문의 **258 은 자기 정의와 안 맞는다**: 45 × 6 = 270, 45 × 5 = 225 (P1:66). 258 을 만드는 묶음은 논문에 없다. 그러므로 「H = 5 · 45 항목」 이라는 **텍스트 정의**를 지키고 첫 층을 270 으로 두는 것이 논문을 축소하지 않는 길이다. 258 로 맞추려고 열을 자르거나 채우지 않는다. 숨은 128 ReLU, 출력 7 은 선형(음수 속도 필요). E1 호환: 새 모듈 |
| Actor 입력 | (o_t, e_o, e_h) = 45 + 7 + 16 (P1:122~129) | latent32 + single_obs45 + e_h16 = 93 (A:151, 285~292). e_o 없음 | 축소 | 100 열: 77 복사 + [e_h16, e_o7] 0 초기화 (A:294~305 의 분리 GEMM 유지). CTS latent 32 는 논문에 없는 우리 열이지만 E1 유지를 위해 남긴다. E1 호환 |
| Critic 입력 | (o_t, s_t 특권, **e_h**) (P1:131~137) | latent32.detach + critic275 = 307 (A:152, 353~362). 원시 187 은 들어가지만 **e_h 는 안 들어감** | E1 이식과 충돌(경로 없음) | 307 → 323: e_h16 을 critic 첫 층 새 열(0 초기화) 로 붙인다. 가치 손실 gradient 를 elevation net 에 흘릴지는 **논문이 명시하지 않는다**(P1:139~149 는 「정책 손실이 actor 를 거쳐 estimator · elevation 을 갱신, 가치 손실은 critic 을 갱신」). 그림 2 의 공유 net 과 「네 신경망 동시 학습」 을 따르면 흘리는 쪽이 자연스럽다. 어느 쪽이든 선택을 영수증에 적는다. E1 호환 |
| 특권 상태 s_t | v 3, c 4, m 4(몸통 · 허벅지 · 종아리 질량), μ 1, ζ 2(CoM), f 2(외란력 xy), k_pd 26(kp, kd, 모터 강도 12, 모터 오프셋 12) = 42 (P1:69~77) | critic275 에 v(0:3 × 2.0), 접촉 **힘 이력** 16(72:88 × 1e-3), 관절 가속 · 토크(논문에 없음) 는 있고 **m, μ, ζ, f, kp/kd, 모터 강도 · 오프셋은 없음** (E:167~233) | 없음(부분) | 질량 · 마찰 · CoM 오프셋 · 외란(push) 속도 · kp/kd 배율 · 모터 오프셋은 모두 E:245~343 의 DR 로 시뮬에 존재하므로 특권 관측 항으로 내보낼 수 있다. **모터 강도 α 는 우리 DR 에 없어서 상수 1 이 된다**: 넣어도 정보가 없으니 그 사실을 적고 뺀다(값을 지어내지 않음). 추가 열은 critic 275 뒤에 붙이고 **critic 첫 층과 teacher encoder 첫 층(A:155~158) 모두** 0 열로 넓힌다. `load_e1_weights` 일반화 필요(A:317~323 은 actor 만 처리). E1 호환 |
| 추정 정답 | v_t 실제 선속도, c_t 네 발 접촉 bool (P1:73~77, 147) | 정답 term 없음. critic 0:3 은 × 2.0 이고 72:76 은 **이력 최대 힘**이라 현재 시점 접촉이 아님 (E:168~172, 218~223, O:41~49; PLAN-sol 도 같은 지적). `foot_contact_flags` 가 O:59~63 에 있으나 **env_cfg 에 연결되지 않음** | 없음 | 별도 특권 관측 그룹 `estimator_target` 7 열: v_b 3 (m/s, 스케일 없음) + `foot_contact_flags` 4 (FL · FR · RL · RR). 접촉 임계값은 **논문 미기재** · 우리 함수는 1 N. rollout 저장 시 같은 step 에 저장(G 의 Transition 에 열 추가). 정답에 gradient 없음 |
| 회귀 손실 | loss_reg = MSE(v̂, v) + MSE(ĉ, c) (P1:145~149). 계수 **미기재** | 없음 | 없음 | `L = L_PPO + λ (mean((v̂−v)²) + mean((ĉ−c)²))`, 각 평균 뒤 합(7 열 한꺼풀 평균이면 속도 · 접촉 가중이 달라짐). λ 는 논문 미기재 → 1.0 으로 시작하고 성분별 gradient 노름을 기록(18g 와 같음). PPO optimizer 에 estimator 등록(G:97~105 패턴) |
| 동시 학습 | 네 신경망을 PPO 로 함께, 정책 gradient 가 estimator · elevation 까지 (P1:139~149) | elevation 은 PPO optimizer 에 등록 · gradient 흐름 (G:103~104). estimator 없음. CTS 는 별도 Adam 으로 teacher latent 회귀 (G:106, 439~458) | 축소 | estimator 를 PPO optimizer 에 넣고 actor 경유 gradient 허용, 7 출력 detach 금지. CTS 의 별도 optimizer · no_grad 계약은 그대로(E1 유지) |
| 보상: 속도 추종 | e^{−4‖v*−v‖²} 1.0 · e^{−4(ω*−ω)²} 0.5 (P1:175~218) | exp(−err/0.5²) = e^{−4 err} 2.0 · 1.0 (E:350~359, R:56~80) | 같음(커널) · 비율 같음(2:1) · 절대 가중 2배 | 그대로(E1 보존) |
| 보상: feet air time | Σ_f (t_air,f − 0.5), 가중 **1.0** (P1:197~218, 234~260) | `(last_air_time − 0.5)·first_contact`, 명령 >0.1 게이트, **중력 투영 배율** 추가, 가중 1.0 (R:214~234, E:435~439, S:114, L:48) | 다름(우리 변형: 중력 배율) | 중력 배율은 논문에 없다. 지우면 E1 15 항 외의 신규 항이므로 E1 보행 계약에는 영향 없음. 남길 때는 「우리 변형」 으로 기록 |
| 보상: feet stumble | any ‖f_xy‖ > 4 |f_z|, 가중 **−1.0** (P1:197~218, 262~273) | `any(f_xy > 4 f_z)`, 중력 배율 추가, −1.0 (R:302~310, E:440~444) | 다름(우리 변형: 중력 배율) | 위와 같음 |
| 보상: feet center | 9 점, Type1 접촉점(id 5), Type2 d1 = 5 cm, Type3 d2 = √50 cm, n^i = 1 if h_id < −0.2, 보상 c_t (n2 + 2 n3), 가중 **−0.01** (P1:153~163, 197~218, 275~285) | 3 × 3 격자 간격 0.05 m(= 5 cm · √50 cm), 위험 = NO_HIT 또는 높이 < 발 z − 0.022 − 0.20, 비용 (cardinal_any + 2·diagonal_any)·contact, **중심점 위험이면 3 으로 덮어씀**, −0.01 (FR:9~14, 47~55, FT:10~25, E:445~449) | 다름(우리 변형: 중심 덮어쓰기 · 임계 기준) | 기하 · 가중 · 「2 배」 구조는 논문과 같다. 중심 덮어쓰기 3 은 논문 식에 없다(식은 n2 + 2 n3 만). 논문대로 하려면 덮어쓰기를 지운다. 임계 「−0.2」 의 기준 좌표는 논문 미기재 |
| 보상: 그 외 | lin_z −2.0, ang_xy −0.05, torque −1e-5(추출 「−e−5」), action rate −0.01, joint acc −2.5e-7, collisions ×(−n) 1.0, orientation −0.2, joint limit −0.02 (P1:175~218) | E1 15 항(E:350~434): lin_z −2.0→0.0 커리큘럼(S:20), ang_xy −0.05, torque −1e-4, acc −1e-7, action rate −0.01, smoothness −0.01, undesired_contacts −1.0, joint_pos_limits −2.0, base_height, feet_regulation, hip · joint pos penalty 등 | 다름(E1 상속) | 논문이 ablation 한 것은 세 발 보상 · 관측 공간이지 이 항들은 아니다(P1:736~756). E1 보존을 위해 그대로 둔다. 「MARG 보상표 재현」 이라 부르지 않는다 |
| 종료 | 몸통 · 엉덩이 지형 충돌, **발 높이 < −0.2 m**, 20 s 정체 (P1:647) | base 접촉 1 N (E:455~461), 바닥 없는 gap 에서 root < 바닥 −0.30 (E:462~463, step1_terrain), 발이 타일 밖, 광선 무효 (E:464~465) | 다름 | 논문의 「발 < −0.2 m」 를 종료 항으로 추가할 수 있다(작음). 우리 gap_fall 은 root 기준이다 |
| 지형 | Single-Gap, Stones-Everywhere, Stones-2Rows, Stones-Balance, Beams-Balance, Air-Beams-Balance, **8 레벨**, 게임형 커리큘럼 (P1:627, 647) | P1: E1 8 종 70 % + 바닥 없는 gap 30 % (0.10~0.60 m) (S:95~117, T:170~258). stepping_stones proportion 0, 바닥 −10 (T:240~250). 커리큘럼 `terrain_levels_vel_gym` (E:470) | 축소 | 돌 · 평균대 계열이 P2 로 미뤄져 있다. 18b §5 가 확인한 대로 Isaac Lab `HfSteppingStones` 는 바닥이 있고 `rails` 도 바닥 box 를 깐다 → **바닥 없는** 돌 · 평균대 mesh 가 따로 필요. 레벨 8 · 치수는 Fig 4 캡션만 있고 수치표 없음(논문 미기재) |
| DR | kp · kd 배율 [0.9, 1.1], 적재 [−1, 2) kg, 지연 [0, 12] ms, 마찰 [0.2, 1.25), CoM [−0.05, 0.05) m, 모터 강도 [0.9, 1.1], **지도 잡음 [−5, 5) cm** (P1:636~645) | 질량 base ±1 kg · 나머지 × 0.9~1.1, CoM ±0.03, 마찰 **0.0~2.0**, 복원 0~0.5, 게인 0.9~1.1(reset), 모터 오프셋 ±0.035, push 4 s, **지연 없음, 지도 잡음 없음**(critic 그룹 corruption False) (E:245~343, 231) | 다름(E1 상속) · 없음(지연 · 지도 잡음) | 지도 잡음 ±5 cm 는 elevation · estimator 의 강건성에 직접 닿는 항목이라 넣을 가치가 있다. teacher · critic 계약을 건드리지 않으려면 **지형 모듈이 읽는 사본에만** 잡음을 더한다. 액추에이터 지연은 동역학을 바꿔 E1 보행을 흔들 수 있으니 두 판 공통 · 별도 실험으로 |
| 학습 규모 | Go1, Isaac Gym, 4096 env, 20000 「episodes」, PPO 설정은 [47] Rudin (P1:630, 648) | Go2, Isaac Lab, E1 20000 에서 추가 10000, 4096 env(18e 보고) 또는 8192(launch 기본, `launch_step1.py:73`) | 다름(설계상) | 처음부터 재현이 아니라 미세 조정이므로 비교 불가 항목으로 기록 |
| 관측 ablation 결론 | 몸 속도 또는 지형 지도가 없으면 성공률 ≈ 0 (P1:736~740); 세 발 보상 중 stumble > air time > center (P1:742~756) | 해당 없음 | 참고 | 우리 M1 에 v̂ 가 없으면 논문이 가장 중요하다고 한 두 입력 중 하나가 빠진 상태다 |

## 2. AME-2 (M2) 구성표

| 구성 요소 | 논문 값 · 근거 (공식 코드 값) | 우리 현재 값 · 근거 | 상태 | 축소하지 않는 구현 · E1 호환 |
|---|---|---|---|---|
| 지도 표현 | teacher 각 점 (x, y, z) 3 채널, student (x, y, z, u) 4 채널 (P2:92). 공식: z = hit − base + 0.74, clip ±1.5, **구멍 = 유효 최솟값 − U(0.65, 1.5) (낮게)**, 잡음 (0.001, 0.001, 0.05) 커리큘럼 (AO:120~196, AE:232~235, 640~647) | (x, y, h), h = clip(z_sensor − z_hit − 0.5, ±1) × 2.5, **구멍 = +2.5 (높게)**, 잡음 없음 (A:62~71, 80~81; HG:7~16) | 다름(부호 반전 · 구멍 방향 반대) | 같은 187 광선에서 **M2 모듈 전용 사본**을 AME-2 규약으로 만든다: z' = −h/2.5 (방향), 구멍 = 유효 최솟값 − U(0.65, 1.5) 또는 그 비율을 우리 범위로 환산한 값(공식 값 그대로 쓰면 clip 범위 ±1 과 맞지 않으므로 환산 기준을 적는다). critic · teacher 의 +2.5 계약은 유지. E1 호환 |
| 격자 | ANYmal 36 × 14, 8 cm, 중심 x = 0.6 m (P2:400); 공식 G1 26 × 15, 8 cm, 중심 x = 0.5 (AE:71~81) → **전방 편향** | 17 × 11, 10 cm, 중심 0 (x ∈ [−0.8, 0.8]) (E:64~71) | 축소(전방 도달 0.8 m 대 1.5 m 이상) | E1 critic 의 187 계약을 깨지 않으려면 **지형 모듈 전용 두 번째 scanner**(예: 공식 G1 과 같은 2.0 × 1.12, 8 cm, x 오프셋 0.5 → 26 × 15 = 390 점) 를 추가한다. 비용: 광선 390 개 추가, attention K/V 가 187 → 390. M1 과 입력이 달라지지만 팀장 원칙상 허용(결과로 비교). 18b §2.4 의 「P1 은 187 로」 는 일정 판단이었고 충실도 판단은 아니다 |
| 점 FC | Linear(dmap→16) ELU (AM:52~55) | Linear(3→16) ELU (A:51) | 같음 | 그대로 |
| 높이 CNN | Conv2d(dmap−2→8, 5, pad 2) ELU → Conv2d(8→48, 5, pad 2) ELU (AM:57~62) | 동일 (A:49~50) | 같음 | 그대로 |
| 지역 투영 | Linear(64→96) ELU (AM:65~68) | 동일 (A:52) | 같음 | 그대로 |
| 전역 특징 | MLP_GlobalPool(96→64 ELU→64) 뒤 `torch.max(dim=1)` (AM:78, 168~169; MD:36~47) | 동일 폭, `amax` (A:53~54, 83) | 같음(동률 gradient 분배만 다름, 18g §2) | 그대로. 기록만 |
| Prop encoder | teacher: MLP_512(prop→128), prop = v_b, ω, g, q, q̇, a, 명령 4 (P2:91, 183; AM:73; AE:242~266) | MLP_512(77→128), 77 = CTS latent32.detach + single_obs45 (A:55~57, 84) | 다름(설계상 이식) | 입력이 논문의 「순수 몸 상태」 가 아니라 지형이 섞인 CTS latent 를 포함한다(18f §1). 폭은 같다. 그대로 두고 명시 |
| Query · MHA | MLP_512(128 + 64 → 96), MHA d 96, **32 heads**, query 1 · K/V = 모든 점 (P2:96; AM:79~80, 170~172) | 동일 (A:58~61, 85~88) | 같음 | 그대로 |
| 지도 embedding | [attn 96, global 64] = 160 (P2:96; AM:121~123, 129~130) | 동일 160 을 actor 에 붙임 (A:89) | 같음 | 이것이 공식 `return_latent` 의 (attn_out, global_feat) 와 정확히 같은 양이므로 나중에 representation 정렬 손실을 걸 수 있다 |
| 행동 decoder | MLP_512([attn96, **prop128**, global64] = 288 → 행동) (P2:95~96; AM:85, 121~123) | E1 actor [512, 256, 128] 에 [77 원시, 160] = 237 (A:151, 294~305). **prop128 은 query 에만 쓰이고 decoder 에는 안 들어감** | E1 이식과 충돌 | 선택 B(현재): E1 actor 유지 · 명시. 선택 C(논문 정보 경로 유지 + E1 호환): prop128 도 0 초기화 열로 붙여 365 열. 선택 A(논문 그대로): 새 MLP_512(288) decoder → **E1 actor 가중치 폐기** · 첫 행동 보존 불가. 팀장 원칙과 E1 유지가 둘 다 필요하면 C 다 |
| Student prop encoder (LSIO) | 20 step 이력(명령 · 선속도 제외) → Long-Short I/O (P2:189~201, 627). 공식: Conv1d(prop→16, k 5) ELU → Flatten → Linear(16·(T−4)→64) ELU; 최근 3 step → Linear(3·prop→60) ELU; cat[64, 60, cmd] → MLP_512(→128) (AM:268~273, 299~317, 364~375) | **없음**. CTS student MoE(10 step 450, 명령 포함) 가 그 자리 (E:161, A:162~169) | 없음 | 4.2 참조. 우리 prop 42(= 45 − 명령 3) × 20, cmd 3 → cat 127 → MLP_512(127→128). 공식 코드는 차원을 관측에서 추론하므로 127 은 코드상 문제 없음. **공식 README 는 LSIO student 학습을 「다음 공개 때」 라 적어 미공개** (RM:44~47) |
| Teacher 단계 | GT 지도 · 무잡음 proprio, 80000 iter (P2:179~181, 399). 공식 teacher cfg 는 proprio 에 잡음 있음 (AE:242~266; student cfg 에서 제거 AE:806~812) | E1 20000 + 추가 10000, single_obs 잡음 있음 (E:162, L) | 다름(규모 · 설계) | 비교 불가 항목. 기록 |
| Student 단계 손실 | PPO + 행동 증류 + 지도 embedding MSE (P2:250~252). 공식: imit = −log π_S(a_T) × **0.02**, repr = MSE(attn) + MSE(global) × **0.2**, surrogate 는 첫 **5000**(논문 P2:399) / 4001(CF:115) / 5001(IL:42) iter 동안 0, lr 1e-3 → 1e-5 (IL:40~75, 143~145, 205~208; CF:110~117; P2:1157) | **없음**. CTS 는 teacher latent 32 회귀 + gate 균형 (G:439~458) | 없음 | 4.2 참조. 단계 A 의 M2 를 JIT 로 얼려 teacher(행동 · attn96 · global64) 로 쓰고, 단계 B 에서 위 세 손실. E1 호환: CTS student 와 LSIO 가 **두 개의 몸 이력 encoder** 로 공존(아래 6 절 (c)) |
| 불확실도 채널 u | student 지도 4 채널, w/o uncertainty 는 성공률 하락 (P2:92, 958, 1020). 공식: u 클립 [0.01, 2] → 0.5 log u + 0.5 (AO:201~240) | 없음 | 없음(**공개판으로 불가**) | 지도 모델 · neural mapping 이 **미공개** (RM:44~47, 55~58). GT 지도 student 는 논문 Fig 16 의 「w/o uncertainty」 변형에 해당. 그 이상은 지어낼 수 없다 |
| Critic 구조 | **MoE** (GMT [68]), 16 experts × MLP_512, router MLP_512 softmax (P2:171~172; AM:1046~1114; CF:160~163) | MLP [512, 256, 128] (A:196, C:45) | 없음 | 4.2 · 6 절 (b) 참조 |
| Critic 입력 | actor 입력 + **모든 링크 접촉 상태(bool)** + 전체 명령 + 남은 시간 + 높이 scan(잡음 ±0.1, clip ±1.5) (P2:183~187, 404; AE:184~226; AO:306~379) | latent32 + critic275(접촉 **힘** 16, 관절 가속 · 토크, 높이 187) (E:167~233) | 다름 | 링크별 접촉 bool(발 · 종아리 · 허벅지 · base) 추가는 작다. 남은 시간은 속도 추종에서 의미 없음. critic · teacher encoder 첫 층 0 열 확장(E1 호환) |
| Critic 대칭 증강 | 좌우 대칭 데이터 증강을 **critic 에만** (P2:193~199; CF:180~185 `for_critic_only`) | 없음. MoECTS 는 symmetry_cfg 를 무시 (G:88~90) | 없음 | Go2 관절 · 관측 좌우 사상 함수가 필요. 기존 G 가 무시하므로 알고리즘 수정. 중간 비용 |
| Teacher actor 에 접촉 상태 | 주지 않음(student 와 정보 격차 축소) (P2:185~189) | CTS teacher latent 가 critic275(접촉 힘 포함) 에서 나오므로 teacher 경로 actor 에 **간접 유입** | 다름 | E1 구조 자체이므로 바꾸지 않고 기록 |
| 보상: 과제 | 목표 위치 100, 방향 50, 이동 5, 정지 5 (×dτ) (P2:209~301) | 속도 추종 2.0 · 1.0 (E:350~359) | 다름(팀장 결정) | 속도 추종 유지. 「AME-2 식 encoder 를 속도 추종에」 가 우리 물음임을 제목에 쓴다(DESIGN-v2 §1, 18b §2.1) |
| 보상: 바람직하지 않은 사건 | 각 −1: 회전 >2 rad/s, 평지 도약, 비발 접촉 + 접촉 전환, **모든 링크** stumbling(수평 > 수직; 공식 f_xy > 1.1 f_z + 1 N), 미끄러짐, 자가 충돌 (P2:302~371; AR:368~426; AE:445~507) | undesired_contacts 허벅지 · 종아리 −1 (5 N) (E:395~399), feet_stumble **발만** 4 배 규칙 (R:302~310) | 축소 | 6 개 사건 항을 −1 로 추가(공식 함수가 Isaac Lab 용으로 공개돼 있어 이식 가능). stumbling 은 모든 링크 · 공식 규칙으로 |
| 보상: 발 위치 보상 **의도적 배제** | 「발 접촉 위치를 명시적으로 보상 · 벌점하지 않는다」 (P2:372~374), 보행 air time 류도 없음 | M2 에 **MARG 의 feet_center −0.01 · feet_air_time 1.0 · feet_stumble −1.0 이 들어가 있음** (S:114~116, L:48~50 두 판 공통) | **E1 이식과 충돌(논문 의도와 정면 충돌)** | M2 에서 feet_center 와 feet_air_time 을 제거하고 feet_stumble 을 AME-2 전 링크 규칙으로 바꾼다. 팀장 원칙(판마다 설계 달라도 됨) 에 맞고, 비교 제목에 「보상 집합도 다르다」 를 적는다 |
| 보상: 정칙화 · 시뮬 충실도 | roll rate −0.1, joint reg(q̇² + 0.01 τ² + 0.001 q̈²) −0.001, action rate −0.01, 링크 접촉력 −1e-5, 링크 가속 −0.001, 관절 한계 0.95/0.9/0.8 에 −1000/−1/−1, 조기 종료 −10/dτ (P2:209~248; AE:510~549, 439~443) | E1 15 항(E:350~434) | 다름(E1 상속) | E1 보존. 조기 종료 벌점(−10/dτ = −500/step 공식) 과 관절 한계 세 항은 추가 가능하나 E1 보행 변화 위험이 있어 선택 사항으로 둔다 |
| 종료 | 자세(|g_x| > 0.985, |g_y| > 0.7, g_z > 0), base 접촉력 > 체중, 허벅지 가속(개 60 m/s²), 정체 (P2:375~379; AE:576~613) | base 1 N 접촉, gap 추락, 타일 밖, 광선 무효 (E:452~465) | 다름 | 자세 · 가속 종료는 추가 가능. 정체는 목표 도달용 |
| 지형 · 커리큘럼 | 12 종, 성공률 EMA > 0.5 승급 · >4 m 강등, **지도 잡음 커리큘럼(첫 20 %)**, 초기 방향 커리큘럼; 희소 지형 절반은 가상 바닥 (P2:391~392, 1112~1133; AE:620~647) | 8 종 + gap, 속도 기반 승급 (E:470, S:95~117) | 축소(지형) · 없음(지도 잡음 커리큘럼) | 속도 추종에서는 Rudin 식 거리 커리큘럼이 자연스러운 대응. 지도 잡음 0 → 0.05 m 와 drift ±0.03 m 커리큘럼은 **모듈 전용 사본**에 넣을 수 있다(E1 호환) |
| DR | 적재 ±5 kg, 지연 [0, 0.02] s, 마찰 [0.3, 1.0]; 관측 잡음 v 0.1, ω 0.2, g 0.05, q 0.01, q̇ 1.5, 지도 0.05 m, drift ±0.03 m (P2:1139~1142; AE:326~368, 169~176 지연 0~1 step) | 질량 ±1 kg, 지연 없음, 마찰 0~2; ω 0.2, g 0.05, q 0.03, q̇ 2.0, 지도 잡음 없음 (E:123~158, 245~343) | 다름 | 지도 잡음 · drift 는 위 행. 지연 · 마찰 범위는 동역학 변경이라 두 판 공통 · 별도 |
| PPO | value 1.0, clip 0.2, **entropy 0.004 → 0.001 감쇠**, epoch 4 · minibatch 3(논문 P2:1152~1157) / 5 · 4(공식 CF:168~170), 24 step, 4800 env, adaptive lr, γ 0.99, λ 0.95, KL 0.01; 공식은 muon + bf16 (CF:86~89) | 5 · 4, entropy **0.01 고정**, Adam, lr 5e-5 → 1.7e-4 warmup (C:50~69, L:170~173, G:240~248) | 다름(entropy 감쇠 없음) | entropy 0.004 → 0.001 감쇠는 논문에 적힌 설정. 넣을 수 있으나 E1 은 0.01 로 학습됐으므로 두 판 공통으로 바꾸거나 그대로 두고 기록 |
| 제어 주기 · 에피소드 | 50 Hz, 16 s (P2:90; AE:675) | 50 Hz, 25 s (E:501~504) | 같음 · 다름 | 그대로 |
| 명령 관측 | actor 는 거리 2 m 로 clip · 남은 시간 제외, 먼 목표는 yaw 무작위 (P2:404; AO:263~298) | 속도 명령 3 | 해당 없음 | 속도 추종 결정으로 대체 |

## 3. 답 1: M1 (MARG) 의 E1 위 최소 충실 사양

**결론: M1 은 E1 을 유지한 채 MARG 의 네 신경망 · 비대칭 actor-critic · 동시 학습 · 세 발 보상을 전부 넣을 수 있다. 바꿀 곳은 모두 「새 모듈 추가 + 첫 층 0 열 확장」 이고 E1 가중치는 하나도 버리지 않는다.**

1. **Estimator 입력 묶음**: 논문 정의 o^H_t = [o_t … o_{t−5}], H = 5 (P1:66) 를 지킨다 → 6 프레임 × 45 = **270**. 논문의 258 은 45 × 6 도 45 × 5 도 아니어서 그 묶음을 복원할 수 없다(논문 미기재). 258 에 맞추려 열을 깎지 않는다. 450 열 student 이력에서 항별 (B, 10, d) 블록의 마지막 6 프레임을 떠서 잇는다(Lab 이력은 항별 평탄화 · 오래된 것이 앞: `observation_manager.py:423~424`, `circular_buffer.py:80~90`). 450 의 끝 270 열을 자르는 구현은 **틀린다**. reset 직후 이력은 첫 관측으로 채워진다(`circular_buffer.py:136~139`); 논문은 reset 처리 미기재.
2. **Estimator 망**: 270 → 128 **ReLU** → 7 **선형**. (v̂ 3 은 음수 가능.) 18g 의 「450 → 258 → 128 → 7」 제안은 258 을 숨은 층 폭으로 읽은 것이다. 논문은 [258, 128, 7] 을 입력 · 숨은 · 출력으로 읽히게 썼고(elevation 의 [128, 64, 16] 과 같은 표기 형식, P1:648) 우리는 입력이 270 이므로 숨은 층은 128 하나다. 두 해석 중 어느 쪽을 택했는지 영수증에 적는다.
3. **ReLU**: elevation [128, 64] 와 estimator 숨은 층을 ReLU 로. A:175 의 `activation=activation` 을 모듈별 인자 `relu` 로 바꾼다. E1 actor · critic · CTS 의 ELU 는 그대로(바꾸면 E1 보존 계약이 깨짐).
4. **Actor 입력 100**: [latent32, single_obs45 | e_h16, e_o7]. 77 열 복사 · 23 열 0, 분리 GEMM 유지(A:294~305). teacher · student · inference 모두 **예측값** e_o 를 쓴다(teacher 에 정답을 주지 않음: 논문 actor 는 ê 만 받음, P1:122~129).
5. **Critic 입력**: e_h16 을 붙여 307 → 323 (P1:131~137). 가치 gradient 를 elevation 에 흘리는지는 논문 미기재 → 한 가지를 택해 적는다. 특권 상태 s_t 중 우리 시뮬에 **실제로 존재하는** 것(질량 배율 · 마찰 · CoM 오프셋 · push 속도 · kp/kd 배율 · 모터 오프셋 12) 을 특권 관측 항으로 추가하고 critic · teacher encoder 첫 층을 0 열로 넓힌다. 모터 강도는 DR 에 없으니 뺀다고 적는다. `load_e1_weights` 를 세 첫 층 공통 규칙으로 일반화(A:317~323).
6. **정답 7 열**: 새 특권 그룹 `estimator_target` = v_b 3 (m/s) + `foot_contact_flags` 4 (O:59~63, 임계 1 N 은 우리 값 · 논문 미기재). 같은 step 에 rollout 저장. critic 0:3 (× 2.0) 과 72:76 (이력 최대 힘) 을 잘라 쓰지 않는다.
7. **손실 · optimizer**: L = L_PPO + λ·(mean((v̂−v)²) + mean((ĉ−c)²)), λ 논문 미기재 → 1.0 시작, 성분별 gradient 노름 기록. estimator · elevation 은 PPO Adam 에 등록, 7 출력 detach 금지, CTS 별도 Adam · no_grad 는 그대로.
8. **세 발 보상**: 가중 1.0 · −1.0 · −0.01 은 논문과 같다. 논문에 없는 우리 추가(중력 배율, 중심 덮어쓰기 3) 를 지울지 정한다. 지우는 쪽이 「축소 없음」 에 더 가깝다. 어느 쪽이든 「우리 변형」 표기.
9. **지형**: Single-Gap 은 있다. Stones-Everywhere · Beams 계열은 **바닥 없는** mesh 로 만들어야 하며(Isaac Lab 기본 생성기는 바닥을 깐다, 18b §5) 레벨 8 치수는 논문 미기재. P1 안에 못 넣으면 「M1 은 MARG 지형 6 종 중 1 종에서만 학습」 이라고 적는다.
10. **지도 잡음 ±5 cm**: 지형 모듈이 읽는 187 사본에만 더한다(critic · teacher 계약 보존).
11. **종료**: 「발 높이 < −0.2 m」 를 추가할 수 있다(작음).

비용 추정(PLAN-sol 과 18g 와 같은 범위): CPU 구현 · 회귀 시험 6~9 시간 + Kit 1 update 대조 1~2 시간. 이것은 그 문서들의 추정이며 이번에 재지 않았다. 새 입력 폭(100 · 323+) 은 새 모델 판이라 저장 · 재개 · 평가 loader 가 옛 M1 을 거절하게 한다(b6 의 `m2_variant` 패턴).

## 4. 답 2: M2 (AME-2) 의 E1 위 최소 충실 사양

**결론: 공개 코드로 할 수 있는 최대치는 「AME-2 teacher 등가판 + GT 지도 student」 다. 불확실도 지도와 neural mapping 은 README 가 미공개라 밝혔으므로(RM:44~47, 55~58) 논문 전체 재현은 이번 공개판으로 불가능하고, 그 사실을 보고서 제목에 써야 한다.**

### 4.1 단계 A · teacher 등가판 (지금 b6 에 더할 것)

1. **지도 입력 규약**: M2 전용 사본으로 부호 · 구멍 방향을 AME-2 쪽으로(구멍 = 낮은 값, 공식 AO:136~148). 지금 +2.5(높음) 는 attention 이 「절벽을 솟은 벽」 으로 읽게 하는 반대 규약이다.
2. **격자**: 전방 편향 격자(공식 G1: 2.0 × 1.12 m, 8 cm, x 오프셋 0.5 → 26 × 15) 를 모듈 전용 scanner 로 추가. 187 중심 격자는 critic · teacher 용으로 유지. 못 하면 「전방 0.8 m 까지만 본다」 를 제한으로 적는다.
3. **decoder**: 선택 C(prop128 을 0 열로 추가, 365 열) 또는 B(현재) 를 정하고 적는다. 공식 288 → MLP_512 decoder(선택 A) 는 E1 actor 폐기라 E1 유지와 양립하지 않는다.
4. **MoE critic**: 16 experts + router. E1 critic 을 보존하려면 각 expert 를 E1 critic 모양 [512, 256, 128] 로 두고 **16 개 모두 E1 가중치를 복사**, router 마지막 층을 0 으로 두어 균일 gating → 초기 가치가 E1 과 같다. 이는 공식 expert 폭(MLP_512) 과 다르므로 「MoE 구조는 살리고 폭은 E1」 로 기록. 공식 폭을 고집하면 가치 함수를 새로 배워야 하고 PPO 미세 조정이 초반에 흔들린다(완화: 공식 student 처럼 surrogate 를 몇 iteration 끈 가치 전용 warmup).
5. **critic 입력**: 링크별 접촉 bool 추가(공식 `ame2_contact_states`), critic · teacher encoder 첫 층 0 열 확장.
6. **보상**: M2 에서 feet_center · feet_air_time 제거, stumbling 을 전 링크 공식 규칙(f_xy > 1.1 f_z + 1 N) 으로 교체, 비발 접촉 + 전환 · 미끄러짐 · 평지 도약 · 과회전 · 자가 충돌 각 −1 추가. 과제 보상은 속도 추종 유지(팀장 결정). 「목표 도달의 정신」 은 (가) 발 위치 보상 없음 (나) 전신 접촉 허용 + 사건 벌점 (다) 지도 encoder 를 정책과 함께만 학습(지도 감독 없음) (라) 명령 조건부 query(single_obs 에 명령 포함, 이미 그렇다) 네 가지로 옮긴다.
7. **지도 잡음 · drift 커리큘럼**: 0 → 0.05 m, drift ±0.03 m, 첫 20 % iteration(P2:392). 모듈 전용 사본에.
8. **critic 대칭 증강**: Go2 좌우 사상 함수 + G 수정. 중간 비용. 못 하면 「없음」 으로 적는다.
9. **entropy 0.004 → 0.001 감쇠**: 두 판 공통으로 바꾸거나, 바꾸지 않고 적는다.

### 4.2 단계 B · GT 지도 student (선택, 공개판 한계 안)

1. 단계 A 의 M2 를 JIT 로 얼려 teacher 로 쓴다(공식 `_TorchAME2Model` 은 행동 · attn96 · global64 를 돌려줌, AM:1197~1252).
2. student actor: LSIO (20 step × 42, 최근 3 step, 명령 3 → MLP_512 → 128) 가 prop embedding 을 만들고 query 와 decoder 에 들어간다. E1 actor 를 유지하려면 LSIO128 도 0 열로 붙인다(선택 C 의 student 판). CTS student MoE latent 는 E1 유지를 위해 남는다 → 몸 이력 encoder 둘이 공존(6 절 (c)).
3. 손실: PPO + 0.02 × (−log π_S(a_T)) + 0.2 × (MSE(attn_S, attn_T) + MSE(global_S, global_T)), surrogate 는 첫 5000 iter(논문) 끔, lr 1e-3 → 1e-5 (IL:40~75, 143~145). 이 계수들은 공식 코드 · 논문 Table IV 값이다.
4. 지도: GT 187(또는 전방 격자) 에 공식 student 손상(점 1 % 무작위 값, 10 % env 깨끗한 지도, drift) 을 흉내낼 수 있으나 **불확실도 채널은 없다**. 논문 Fig 16 의 「Ours w/o Uncertainty」 가 이 변형의 상한이다.
5. 이 단계는 E1 CTS 와 개념이 겹치고(둘 다 teacher → student 증류) 구현 · 학습 비용이 크다. 이번 일정 안에 넣을지는 팀장 판단이며, 넣지 않으면 M2 는 「teacher 등가판」 이다.

## 5. 답 3: 충실도와 E1 이식이 부딪히는 곳

| 충돌 | 내용 | 논문 의미를 가장 살리는 선택 | 비용 |
|---|---|---|---|
| (a) actor decoder | 두 논문 모두 지도 · 몸 embedding 을 받는 **새** decoder. E1 은 actor [512, 256, 128] 가중치 보존이 목적 | E1 actor 유지 + 논문이 actor 에 넣는 입력을 **전부** 0 열로 추가(M1: e_h16 + e_o7, M2: attn96 + global64 + prop128). decoder 폭은 재현 안 됨을 적음 | 첫 층 열 증가만. 첫 행동 = E1 유지 |
| (b) critic | MARG: e_h + 특권 42 를 받는 critic. AME-2: MoE critic. E1 critic 은 MLP 307 | MARG: 0 열 확장. AME-2: 16 expert 모두 E1 복사 + 0 router(초기 가치 = E1). 공식 MLP_512 폭은 포기 | `load_e1_weights` 일반화 · critic 재구성. MoE 는 critic 연산 16 배 |
| (c) 몸 이력 encoder 셋 | E1 CTS(10 step MoE latent), MARG estimator(6 step), AME-2 LSIO(20 step) | CTS 는 E1 유지 조건이라 남기고, 논문 encoder 를 **병렬 갈래**로 추가. 중복은 결과로 판정(18g §1 과 같은 입장) | 입력 중복 · 파라미터 증가 · 해석 복잡 |
| (d) 지도 규약 | E1 critic 계약(구멍 +2.5, 부호) 과 AME-2(구멍 낮음, z 위가 양수) | 같은 광선의 **모듈 전용 사본**을 논문 규약으로 | 작음. M1 · M2 입력이 「같은 187」 이 아니게 됨(팀장 원칙상 허용, 제목에 적음) |
| (e) 격자 | 187 중심 격자 대 전방 편향 격자 | 모듈 전용 두 번째 scanner | 광선 · attention 비용 증가, teacher · critic 무변경 |
| (f) 학습 체계 | CTS 동시 증류 대 AME-2 두 단계 | 단계 A 뒤 단계 B 를 별 실행으로. 불확실도는 불가 | 큼. 일정과 충돌 |
| (g) 보상 집합 | MARG 세 발 보상이 지금 두 판 공통. AME-2 는 발 위치 보상을 명시적으로 거부 | 판별 보상 집합(M1: MARG 세 항, M2: AME-2 사건 벌점). 비교 제목에 「encoder 와 보상 집합이 함께 다르다」 | 「encoder 하나만 다르다」 는 해석을 포기. 팀장 원칙과 일치 |
| (h) 활성화 | MARG ReLU 대 E1 ELU | 새 모듈만 ReLU | 없음 |
| (i) DR 동역학 | 두 논문의 액추에이터 지연 · 마찰 범위 대 E1 DR | 관측 쪽(지도 잡음 · drift) 만 지금, 동역학 쪽은 두 판 공통 별도 | 지연 추가 시 E1 보행 변화 위험 |
| (j) 명령 | AME-2 목표 도달 대 속도 추종 | 팀장 결정대로 속도 추종. 「속도 추종에서 AME-2 encoder」 가 물음 | 논문 성적 재현 주장 불가 |

## 6. 답 4: 비교를 무너뜨릴 위험

1. **변경 묶음이 너무 커서 아무것에도 귀속되지 않음**: M1 에 추정기 · ReLU · critic 경로 · 특권 상태 · 지형, M2 에 규약 · 격자 · MoE critic · 보상 집합을 한꺼풀에 넣으면 결과 차이를 encoder 에 돌릴 수 없다. 완화: 판마다 **변경 목록을 학습 전에 고정**해 영수증에 적고, E1 과 M0 를 기준선으로 남긴다. 「attention 단독 효과」 라 쓰지 않는다(18e §2, 18f §3).
2. **M2 를 「AME-2 재현」 이라 부름**: 지도 모델 · student · 불확실도 · 목표 도달이 없다. 제목은 「E1 + AME-2 teacher 구조(속도 추종)」.
3. **critic 재시작으로 PPO 붕괴**: 공식 폭 MoE critic 을 새로 배우면 미세 조정 초반 가치 추정이 무너져 「AME-2 가 나쁘다」 로 읽힌다. 완화: E1 복사 expert 또는 가치 전용 warmup.
4. **회귀 gradient 가 clip 노름을 지배**: λ = 1 에서 estimator 손실이 공통 clip(G:410~411) 을 먹으면 PPO 가 약해진다(18g §1). 성분별 노름 기록, λ 는 미확인으로 표기.
5. **258 맞추기**: 270 을 258 로 자르거나 채우면 입력 의미가 깨진다. 450 끝 270 열 자르기도 틀림(항별 평탄화). CPU 에서 답을 아는 입력으로 묶음 검사.
6. **접촉 정답 오염**: critic 72:76(이력 최대 힘) 을 정답으로 쓰면 시점이 어긋난다. 전용 label 그룹만 쓴다.
7. **처리량 차이를 시간으로 비교**: M2 는 느리다(18e). 공통 추가 update 수 · 공통 checkpoint 로 비교하고 wall-clock 은 운영 지표로만.
8. **옛 checkpoint 조용한 재개**: 입력 폭이 바뀐 새 판은 옛 M1 · M2 를 거절해야 한다(b6 `m2_variant` 패턴 유지).
9. **지형 미비로 MARG 주장 미검증**: P1 은 gap 하나다. 돌 · 평균대 없이 「MARG 식이 위험 지형에 좋다」 는 판정은 불가. 바닥 없는 mesh 가 없으면 그 한계를 적는다.
10. **보상 집합 분기의 되돌림**: M2 에서 발 보상을 빼고 결과가 나쁘면 되살리고 싶어진다. 결과를 보고 보상을 바꾸면 새 실험으로 분리한다(18b §6 5 번).
11. **단일 시드**: 두 판 모두 한 시드. 「경향」 으로만 쓴다.

## 7. 미확인 · 미기재 목록

- 논문 미기재: MARG 258 의 묶음, 회귀 손실 계수, 접촉 임계값, 가치 gradient 가 elevation 에 흐르는지, feet center 「−0.2」 의 기준 좌표, 지형 레벨 치수표, 구멍(미스) 값 처리. AME-2 논문 미기재 · 공식 코드만 있음: 지도 구멍 채움 규칙, stumbling 의 1.1 f_z + 1 N, student 손상 비율 세부, rl_switch 4001 대 5000.
- 미확인(이번 세션): b6 의 GPU 처리량 · 메모리, 새 모듈을 넣은 뒤 E1 보행 유지, λ · 0.02 · 0.2 가 우리 조건에서 적절한지, 전방 격자의 raycast 비용. 어느 것도 실행하지 않았다.
- 이 문서는 설계 충실도 판정이다. 코드 · GPU · 프로세스 · 커밋을 건드리지 않았다.
