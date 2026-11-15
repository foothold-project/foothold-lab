> 분류: 계획
> 작성: Fable 명세 세션 · 2026-10-18
> 근거: START 원문 `C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt` 와 같은 폴더 PDF (그림 2 · 3 · 4 · 5 · 6 · 표 I · II 를 PDF 에서 직접 봄) · PIE 원문 https://arxiv.org/html/2408.13740v3 (표 II) · Zhang et al. 2311.10484v2 (표 I · III) · Intel D435i 사양 페이지 · Isaac Lab 설치 소스 `C:/isaac/IsaacLab` (VERSION 2.3.2, isaaclab 0.54.2) · rpl_parkour Go2 설정 · E1 고정본 `s2_lab/step1_18b_b6_frozen` · Go2 URDF (rpl_parkour) · Lite3 URDF (DeepRoboticsLab/URDF_model) · 선행 mai-code 분석 start-deep · depth-paths-hipan-start-rpl
> 요지: START 의 구성 요소를 논문이 준 값 그대로 전수 목록으로 적고, 논문이 안 준 값은 「논문 미기재」 로 표시한 뒤 출처가 있는 우리 선택을 따로 붙였다. Go2 + D435i 적응은 로봇 고유 항목(장착 자세 · 내부 파라미터 · 60×60 경로 · 지연)에 한정했고, Isaac Lab 에서는 Warp 광선 카메라(RayCasterCamera)로 4096 환경 60×60 깊이를 16 GB 안에서 만드는 길과 위험을 적었다. 마지막에 mai-code 단위 8 개와 sol 의 Isaac Lab 통합 항목, 검증 단계를 적었다
> 상태: 명세 초안 · 정적 작성 · GPU · Isaac · 학습 미실행 · 어느 코드 · 파일도 고치지 않음 · 효과 · 처리량 · 메모리 최고치는 미확인

**한 문장 요지: START 는 「2 장 깊이 + 고유수용 → TR-Net 이 32×16 (0.05 m) 지역 높이 지도를 복원 → I-E Estimator 가 지도와 10 프레임 이력을 transformer 로 섞어 VAE latent 와 명시 추정(속도 · 몸 · 발 지도)을 내고 → actor 가 관절 목표 12 를 내는」 단일 단계 비대칭 PPO 이며, 14 개 보상 · 4 지형 × 10 레벨 · 점진 커리큘럼 · AdaSmpl · PIE 식 DR 이 모두 한 몸이므로 어느 것도 빼지 않고 Go2 에 그대로 올리되, 논문이 안 준 층 크기 · 임계값 · 카메라 자세는 아래 표에서 출처를 달아 우리가 정한다.**

# START → Go2 + D435i 충실 구현 명세

## 0. 읽는 법과 표기 규약

- **논문값** 열의 숫자는 START 원문에서 그대로 옮겼고 절 · 식 · 표 · 그림 번호를 달았다. 텍스트 추출이 깨진 곳(표 I 의 가중치 열, 그림 5 의 막대 높이)은 PDF 를 직접 보고 적었다.
- **「논문 미기재」** 는 START 본문 어디에도 값이 없다는 뜻이다. 그 옆의 **우리 선택** 은 출처를 셋 중 하나로 표시한다: 「인용 저작(PIE 표 II 등)」 · 「표준 관행(Rudin [41] · rsl_rl 기본값 · E1 설정)」 · 「이 명세의 결정(근거 한 줄)」. 우리 선택은 팀장 확인 전까지 제안이다.
- 팀장 결정(10/18 19:09)에 따라 **축소 금지** 가 원칙이다. 「축소」 가 아닌 「추가」 (예: 깊이 잡음 모델) 도 논문에 없는 것은 따로 표시했고 기본은 넣지 않는다.
- 그림 5 · 6 의 수치는 막대 · 선을 눈금으로 읽은 근사값이며 「눈금 읽기」 라고 표시했다. 검증 목표로만 쓰고 논문 수치로 인용하지 않는다.
- 증거 등급: 「논문값」 과 소스 행 번호가 붙은 것은 `확인됨`, 「이 명세의 결정」 은 `추측` (출처가 있는 제안), 「미확인」 은 `미측정` 이다. 갈래: A/정책학습 · 논문 충실 구현 명세 (START → Go2 + D435i, Isaac Lab 2.3.2).
- 기준 코드: 공개 코드가 없으므로 모든 모듈은 논문에서 새로 구현한다. rpl_parkour 와 Isaac Lab 소스는 **공학 패턴(깊이 처리 · 센서 API)** 참고로만 쓴다. 우리 옛 기반(MoE-CTS · 187 점 scan)에는 맞추지 않는다.

약칭: P = START 원문 txt 행 번호 · T1 = 표 I · F2~F8 = 그림 · PIE = https://arxiv.org/html/2408.13740v3 · Z = Zhang et al. 2311.10484v2 · Lab = `C:/isaac/IsaacLab/source/isaaclab/isaaclab/` · Tasks = `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/` · RPL = `C:/Users/AI-WS01/s2_lab/_research_repos/rpl_parkour/legged_gym/legged_gym/` · E1 = `C:/Users/AI-WS01/s2_lab/step1_18b_b6_frozen/source/`.

## 1. 구성 요소 전수 목록

### 1.1 관측 · 행동 · 특권 정보 (§II-A-1, 식 1 · 2, F2)

| 항목 | 논문값 · 근거 | 논문 미기재 → 우리 선택 (출처) |
|---|---|---|
| 고유수용 o_t ∈ R45 | [ω_t 3, g_t 3, cmd_t 3, θ_t 12, θ̇_t 12, a_{t−1} 12] 순서 (식 1, P64~72). 몸 각속도 · 로봇 좌표 중력 · 속도 명령 · 관절각 · 관절각속도 · 이전 행동 | 관측 스케일 · 잡음: 미기재 → Rudin [41] legged_gym 스케일 (ang_vel 0.25 · dof_pos 1.0 · dof_vel 0.05 · cmd 2.0/0.25) · 관측 잡음은 PIE 표 II 에 없으므로 **넣지 않음** (표준 관행). 관절각은 기본 자세 기준 차이 (E1 과 같음) |
| 행동 a_t ∈ R12 | 12 관절 위치 목표 (P60). PD 추종 | action scale · PD 게인: 미기재 → Go2 는 E1 설정 유지: scale 0.25 · kp 25 · kd 0.5 · DCMotor 토크 23.5 N·m (E1 `robot_lab/assets/unitree.py:132~146`, `tasks/go2/env_cfg.py:112`). 로봇 고유 항목 (2 절) |
| 명시 추정 ê_t | [v̂_t 3, ẑ^b_t, ẑ^f_t] (P133). ẑ^b · ẑ^f 는 몸 · 발 중심 높이 지도 descriptor, 각각 Ĥ^b · Ĥ^f 로 디코딩 「(within 0.1 m)」 (P134) | ẑ^b · ẑ^f 차원 미기재 → 각 16 (이 명세의 결정: 512 · 100 짜리 지도를 복원하기에 충분히 작은 병목). 「within 0.1 m」 은 발 중심 지도의 반경으로 읽는다(다른 읽기: 복원 오차 한계 · 본문만으로는 가를 수 없음) |
| 암시 latent z_t | VAE 로 얻음 (식 3, P120~122) | 차원 미기재 → 32 (DreamWaQ [34] 관행 · 이 명세의 결정). 배포 시 z = μ (미기재 → DreamWaQ 관행) |
| actor 입력 | o_t + ê_t + z_t (P56~60) | 45 + (3 + 16 + 16) + 32 = **112** (우리 차원 선택의 결과) |
| critic 입력 s_t | o_t 와 [v_t 실제 몸 속도 3, c_t 발 접촉 상태 4, H^b_t 몸 주변 지도, H^f_t 네 발 주변 지도] (식 2, P74~88) | H^b: 32×16 = 512 (1.3 절 지도 규격) · H^f: 발마다 5×5 (0.05 m, ±0.1 m) = 25 × 4 = 100 (이 명세의 결정: 「within 0.1 m」 과 지도 해상도 0.05 m 를 그대로 씀). critic 입력 45 + 3 + 4 + 512 + 100 = **664** |

### 1.2 I-E Estimator (§II-A-2, 식 3, F2)

| 부품 | 논문값 · 근거 | 논문 미기재 → 우리 선택 (출처) |
|---|---|---|
| 고유수용 이력 GRU | o_t^{H1} 을 GRU 가 처리해 z^prop_t (P104). TR-Net 도 같은 z^prop_t 를 받음 (P126) → **공유** | H1 미기재 → **H1 = 10** (PIE §III-B, 인용 저작). GRU 은닉 256 (이 명세의 결정). 호출 방식: 매 step 최근 10 프레임 창을 처음부터 통과(창 방식, 은닉 전달 없음 · PPO 미니배치에서 상태 저장이 불필요) |
| 지도 CNN | 복원 지도 Ĥ^map_t 에서 z^map_t 추출 (P104). 「각 지형 token 이 특정 지역에 대응」 (P131~132) → CNN 특징도를 token 으로 씀 | 구조 미기재 → 1×32×16 → conv(1→32, k3, s1) → conv(32→64, k3, s2) → conv(64→64, k3, s2) → 64×8×4 = **32 token × 64** (이 명세의 결정: 0.2 m × 0.2 m 지역 하나가 token 하나) |
| transformer 융합 | transformer encoder 층들이 z^prop · 지도 token 을 섞어 z_t · ê_t 를 냄 (P104, 129~133, [21]) | 층 수 · head · 폭 미기재 → 2 층 · 4 head · d_model 64 · FFN 128 · z^prop 는 Linear(256→64) 로 token 하나 추가 (33 token) · 출력은 mean pool (이 명세의 결정) |
| VAE | z_t ~ q(z_t | o^{H1}_t, Ĥ^map_t), KL 항 (식 3) | prior p(z) 미기재 → N(0, I) (DreamWaQ 관행). μ · logσ² head 각 32. 학습 시 reparameterization, 배포 시 μ |
| 명시 head | v̂_t · ẑ^b_t · ẑ^f_t (P133) | Linear(64→3) · (64→16) · (64→16) |
| 디코더 | ẑ^b → Ĥ^b, ẑ^f → Ĥ^f (P134); 모든 추정 벡터에서 ô_{t+1} (P122~124) | MLP(16→128→512) · MLP(16→128→100) · MLP(32+3+16+16=67 → 128 → 45) (이 명세의 결정) |
| 손실 L_IE | KL + MSE(ô_{t+1}, o_{t+1}) + MSE(v̂, v) + MSE(Ĥ^f, H^f) + MSE(Ĥ^b, H^b), 계수 모두 1 (식 3 인쇄 그대로) | 계수는 식대로 1. 정답 o_{t+1} 은 rollout 저장의 다음 step 관측 (마지막 step 은 다음 rollout 첫 관측 또는 마스크) |
| gradient 경계 | 「I-E Estimator 는 지도 학습으로 훈련」 (P42: trained via supervised learning) | 이 문장을 따라 **PPO 손실은 I-E 로 흐르지 않음** (actor 입력에서 ê_t · z_t detach). L_IE 가 TR-Net 으로 흐르는지도 미기재 → **흐르지 않음** (Ĥ^map detach · 1.3 절 이유) |

### 1.3 TR-Net (§II-B, 식 4, F3)

| 부품 | 논문값 · 근거 | 논문 미기재 → 우리 선택 (출처) |
|---|---|---|
| 입력 | z^prop_t 와 시간 깊이 영상 d_t^{H2}, **H2 = 2** (P126~127) | 두 프레임 간격 미기재 → 카메라 주기의 연속 두 프레임(0.1 s 간격) 을 채널로 쌓음 2×60×60 (PIE §III-B 「depth frames stacked in channels」, 인용 저작) |
| 지도 규격 | 로봇 지역 좌표, 뒤 0.5 m ~ 앞 1.1 m, 폭 0.8 m, 해상도 5 cm (P127) | 격자 셀 수 미기재(끝점 포함 여부) → **32 × 16 셀, 셀 중심** x = −0.475 … 1.075, y = −0.375 … 0.375 (이 명세의 결정: 2 의 거듭제곱 축소가 되는 U-Net 친화 크기). 좌표계: yaw 정렬 · 중력 수직 광선 (미기재 → Rudin 관행). 값: h = z_hit − z_base, clip ±1 m (미기재 → 이 명세의 결정; 깊이 0.7 m 구덩이가 포화되지 않음) |
| 깊이 CNN | 깊이 영상에서 시각 특징 (P136) | conv(2→32, k5, s2, p2) → conv(32→64, k3, s2, p1) → conv(64→128, k3, s2, p1) → conv(128→128, k3, s2, p1) → 4×4 → FC 256, LeakyReLU (이 명세의 결정; RPL `go2_distill_config.py` 의 [16,32,32]/[5,4,3] 보다 넓게, 60×60 입력) |
| 결합 → GRU | 시각 특징 ⊕ z^prop → GRU 가 「지금 가려진 발밑 · 뒤 지형」 을 기억 (P136~138) | 은닉 512 · **상태 유지형** (에피소드 reset 때 0) · 카메라가 새 프레임을 줄 때(10 Hz) 만 한 tick 진행 (이 명세의 결정: 실기 10 Hz 와 같게) |
| rough 디코더 | MLP 가 Ĥ^rough_t 로 사상 (P138~139) | MLP(512 → 512 → 512) → reshape 1×32×16 |
| 정제 디코더 | U-Net 기반, 고주파 기하 복원 · 잡음 · 흐린 edge 억제 → Ĥ^refined_t (P158~160, [38]) | 입력은 rough 지도만 (미기재; 이 명세의 결정: 순수 정제). encoder 1→32 (32×16) → 64 (16×8) → 128 (8×4), skip 연결로 복원, 출력 1×32×16 직접 (잔차 아님 · 미기재) |
| 손실 L_TR | MSE(Ĥ^rough, H^b) + L1(Ĥ^refined, H^b), 계수 1 (식 4) | L1 의 gradient 가 rough 를 거쳐 GRU · CNN 까지 흐름 (미기재 → detach 안 함, 이 명세의 결정) |
| 정책 입력 지도 | Ĥ^map_t = Ĥ^refined_t (F3 의 AdaSmpl 뒤), 배포 시 복원 지도만 (P215~217) | TR-Net 은 L_TR 로만 학습 (PPO · L_IE 차단). 근거: AdaSmpl 이 같은 자리에 정답 지도를 넣으므로 Ĥ^map 의 의미가 「지도」 로 고정돼야 함 |
| 복원 오차 (검증 목표) | F5 (최고 난이도, MAE cm, 눈금 읽기): START 돌 ≈ 3.6 · 평균대 ≈ 1.8 · 징검 빔 ≈ 4.8 · gap ≈ 1.5; w/o Prop ≈ 5.2 · 3.7 · 7.5 · 2.6; w/o GRU ≈ 7.6 · 5.0 · 8.6 · 4.1; w/o Refine ≈ 5.5 · 4.3 · 7.2 · 2.2 | 우리 수치는 재현 목표가 아니라 보고 항목 (Go2 · 카메라 자세가 다름) |

### 1.4 AdaSmpl (§II-C, 식 5, F3)

| 항목 | 논문값 · 근거 | 논문 미기재 → 우리 선택 (출처) |
|---|---|---|
| 규칙 | 정책 입력 지도를 확률 p_smpl 로 정답 H^b 로 바꿈. p_smpl = tanh(CV(R)), CV = 에피소드 보상 R 의 변동계수 (식 5, P185~199). 학습 안정 → CV ↓ → 복원 지도 비중 ↑. 배포는 복원 지도만 (P215~217) | R 의 창: 미기재 → 직전 iteration 까지 끝난 에피소드 return 의 rsl_rl `rewbuffer` (최근 100 개) (표준 관행). CV = std/mean, mean ≤ 0 이면 p = 1 (이 명세의 결정). 치환 단위: env 마다 TR-Net tick 마다 Bernoulli(p) (미기재 · 이 명세의 결정). 치환돼도 TR-Net 은 그 step 도 L_TR 로 학습 (논문 취지: 치환은 「정책 입력」 에만) |
| 효과 (검증 목표) | F8: START 가 w/o AdaSmpl 보다 r_feetedge 와 총 보상이 빨리 오름 (눈금 읽기: 10000 iter 에서 총 보상 ≈ 17 대 ≈ 14) | p_smpl 궤적을 매 iteration 기록 (시작 ≈ 1 → 하강) |

### 1.5 actor · critic · PPO · 예산 (§II-A, §II-D-1)

| 항목 | 논문값 · 근거 | 논문 미기재 → 우리 선택 (출처) |
|---|---|---|
| 구조 | 비대칭 actor-critic, [34] 를 따름 (P50~54). actor PPO [32] (P42) | actor · critic MLP [512, 256, 128] ELU (Rudin [41] · E1 기본값). critic 은 별도 MLP, 입력 664 |
| 단일 단계 | 모든 신경망을 한 단계에서 함께 최적화 (P40, 두 단계의 정보 간극 회피 P50) | optimizer 셋: PPO Adam(actor+critic) · Adam(I-E) 1e-3 · Adam(TR-Net) 1e-3, 같은 미니배치에서 같은 iteration 에 갱신 (이 명세의 결정) |
| PPO 하이퍼 | 미기재 | Rudin [41] = E1 `rsl_rl_cfg.py:20~31`: epoch 5 · minibatch 4 · lr 1e-3 adaptive(desired KL 0.01) · γ 0.99 · λ 0.95 · clip 0.2 · entropy 0.01 · value coef 1.0 · grad norm 1.0. **steps/env 48** (Z §II-B 의 48, 인용 저작; TR-Net GRU 의 TBPTT 창 0.96 s 확보) |
| 예산 | Isaac Gym · Lite3 3072 env · RTX A6000 1 장 · 약 10000 iteration / 16.6 h (P221) | Go2 · Isaac Lab · **4096 env** (PIE §III-C-1) · RTX 5080 16 GB 1 장 / 판 · 10000 iteration. 시간 · 메모리는 **미확인** (3.4 절) |
| 시간 해상도 | 행동 50 Hz (P528, 실기) | sim dt 0.005 s · decimation 4 = 50 Hz (E1 `env_cfg.py:501~504`). 에피소드 길이 미기재 → 20 s (Rudin 관행) |

### 1.6 보상 14 항 (표 I, §II-D-2, 식 6) · 전부 포함

표 I 을 PDF 에서 읽은 값. Isaac Lab RewardManager 와 legged_gym 모두 가중치에 step dt 를 곱하므로 아래 가중치를 그대로 `weight` 로 쓴다.

| # | 항 | 식 (표 I) | 가중치 | 구현 메모 |
|---|---|---|---|---|
| 1 | Lin. vel. tracking | exp(−‖min(v, v^cmd) − v^cmd‖² / 0.25) | 1.5 | min 은 성분별. v^cmd 는 (v_x, 0) |
| 2 | Ang. vel. tracking | exp(−‖ω_yaw − ω^cmd_yaw‖² / 0.25) | 0.5 | |
| 3 | Lin. vel. (z) | v_z² | −2.0 | |
| 4 | Ang. vel. (xy) | ‖ω_xy‖² | −0.05 | |
| 5 | Orientation | g_x² + g_y² | −1.0 | 로봇 좌표 중력 |
| 6 | Torques | Σ_j |τ_j|² | −1.0e−5 | |
| 7 | Action rate | Σ_j |a_t − a_{t−1}|² | −0.01 | |
| 8 | Smoothness | Σ_j |a_t − 2a_{t−1} + a_{t−2}|² | −0.01 | a_{t−2} 버퍼 필요 |
| 9 | Joint power | Σ_j |τ_j| |q̇_j| | −2.0e−5 | |
| 10 | Joint accelerations | Σ_j |q̈_j|² | −2.5e−7 | |
| 11 | Joint error | Σ_j |q_j − q_j^default|² | −0.01 | |
| 12 | Collision | Σ_{i∈contact} 1{F_i > 0.1} | −10.0 | 대상 몸체 미기재 → thigh · calf · base (RPL `go2_config.py:54` 의 thigh · calf 에 base 추가, 이 명세의 결정). 임계 0.1 N 은 논문값 |
| 13 | Stumble | 1{∃ i, |F_i^xy| > 4 |F_i^z|} | −1.0 | 네 발 접촉력 |
| 14 | Feet edge | Σ_{i∈feet} c_i · Σ_{d∈dist} ω_d E_d[p_i] | −1.0 | 식 6 · dist = [2.5, 5.0] cm · ω_d = [1.0, 0.5] (P255~257). E_d 는 발 위치 p_i 가 edge 에서 d cm 안이면 1. **부호는 한 번만**: 식 6 에 이미 −, 표 I 가중치도 −1 → 구현은 양의 마스크 합에 −1.0 을 곱함. 2.5 cm 안이면 두 마스크가 겹쳐 1.5 (논문 정의 그대로). edge 정의 미기재 → 「인접 셀과 높이차 > 0.1 m 인 셀 경계」 까지의 평면 거리 (이 명세의 결정: ±5 cm 높이 변화는 edge 로 안 셈). 접촉 c_i 임계 미기재 → 1 N (Lab ContactSensor 기본값) |

### 1.7 종료 (§II-D-1)

| 조건 | 논문값 · 근거 | 우리 선택 |
|---|---|---|
| 뒤집힘 | 「predefined angular limits」 를 넘으면 reset (P221) | 한계값 미기재 → |roll| > 1.0 rad 또는 |pitch| > 1.0 rad (이 명세의 결정) |
| 발 추락 | 발 높이가 지면 평면 아래 「specified threshold」 보다 낮으면 reset (P221) | 임계 미기재 → 발 z < −0.10 m (지형 기준면 = 돌 윗면 0, ±5 cm 변화 아래; 이 명세의 결정) |
| 시간 | 미기재 | 20 s (1.5 절) |
| 몸통 접촉 종료 | **없음** (충돌은 보상 −10 으로만, 표 I) | 넣지 않음 (E1 의 illegal_contact 종료는 가져오지 않음) |

### 1.8 명령 (§II-D-1, P225~233)

- v_x ~ U[0.0, 1.5] m/s (로봇 좌표), v_y = 0 고정.
- v_x < 0.3 m/s 이면 v_x = 0 으로 clamp 하고, 그때만 ω_z ~ U[−1.2, 1.2] rad/s. 그 외 ω_z = 0.
- 재표본 주기 미기재 → 10 s (Rudin 관행). 지형이 x 축을 따라 놓이므로 heading 명령은 없음.
- HiPAN 식 항법기와 짝을 맞출 때의 함의: 이 정책의 학습 분포는 「전진만」 또는 「제자리 회전만」 이다. 항법기가 (v_x > 0, ω_z ≠ 0) 를 동시에 내면 분포 밖이다. 논문 그대로가 기본이며, 동시 명령으로 **넓히는** 것은 논문에 없는 추가이므로 팀장 결정 항목으로 남긴다 (HiPAN 분석의 「RPL 대안에서 상위 명령이 하위 분포를 벗어나는 문제」 와 같은 종류).

### 1.9 지형 · 점진 커리큘럼 (§II-D-3, F4, F6 가로축)

| 항목 | 논문값 · 근거 | 논문 미기재 → 우리 선택 |
|---|---|---|
| 종류 · 레벨 | 4 종 × 10 난이도, 난이도 상승 규칙은 [41] (P259~261). 패치 8 m × 4 m (P275). 돌 · 빔 높이 변화 ±5 cm, 지형 깊이 U[0.2, 0.7] m (P275~277) | 깊이는 패치(sub-terrain)마다 1 값 (이 명세의 읽기). [41] 규칙 = Lab `terrain_levels_vel` (Tasks `.../velocity/mdp/curriculums.py:27~56`): 걸은 거리 > 패치 길이 / 2 (= 4 m) 면 승급, < 0.5 × ‖cmd‖ × 에피소드 길이면 강등 |
| 징검돌 | 돌 폭 0.2 m, 간격 x 0.25 m · y 0.175 m, 최고 희소도 76.3 % (P267~269). 희소도 = 디딜 수 없는 면적 / 전체 (각주 1, [16]) | 레벨별 간격표 미기재. F6 가로축 희소도 38.3 · 46.4 · 53.2 · 62.5 · 76.3 % 는 간격 배율 0.26 · 0.35 · 0.44 · 0.60 · 1.00 에 해당 (계산: 1 − 0.04 / ((0.2 + 0.25k)(0.2 + 0.175k))). 우리 선택: 10 레벨에서 k 를 0.2 → 1.0 선형, 최고 레벨은 논문값과 같음. 검증: 생성 지형의 희소도 76.3 % ± 0.5 |
| 돌 무작위 (높은 그룹) | 돌마다 두 축으로 ±0.5 × 간격 이동, 열 전체를 x 로 ±0.45 × 간격 이동 (P335~343, F4b) | 낮은 그룹의 이동량 미기재 → 돌 ±0.1 × 간격 · 열 0 (이 명세의 결정) |
| 평균대 | 폭 0.175 m 까지 좁아짐 (P269). F6 가로축 0.4 · 0.3 · 0.25 · 0.2 · 0.175 m | 10 레벨 폭 0.4 → 0.175 선형. 길이 = 패치 길이, x 축 정렬 |
| 징검 빔 | 빔 폭 0.15 m, 간격 0.275 m, 최고 희소도 64.7 % (P271~273). F6 가로축 40.0 · 44.4 · 50.0 · 58.8 · 64.7 % = 간격 0.100 · 0.120 · 0.150 · 0.214 · 0.275 m | 간격 0.10 → 0.275 선형 (y 축 가로 빔) |
| gap | 최대 0.7 m (「2× robot length」) (P273~274). F6 가로축 0.3 · 0.4 · 0.5 · 0.6 · 0.7 m | gap 폭 0.3 → 0.7 선형. gap 개수 미기재 → 패치당 2 개 (이 명세의 결정). Lite3 hip 간 거리 0.349 m (Lite3 URDF `FL_HipX_joint` x 0.1745) 의 2 배 = 0.698 m 가 논문의 「2× 로봇 길이」 와 맞음. Go2 는 0.3868 m (Go2 URDF `FL_hip_joint` x 0.1934) 의 2 배 0.774 m → **논문값 0.7 m 를 그대로 둔다**(축소 아님). 0.774 m 로 넓히는 것은 추가 옵션 |
| 점진 커리큘럼 | 처음엔 낮은 무작위 징검돌 + 보조 평지, 이후 p_advance = max(min(p_max (T − T_start)/(T_end − T_start), 0), p_max) 로 높은 무작위 돌 · 평균대 · 징검 빔에 확률 배정. gap 은 이 진행에서 제외 (P303~333, F4a). [16] 에서 착안 | 인쇄된 max/min 순서는 증가 램프와 모순 → clip(p_max (T − T_start)/(T_end − T_start), 0, p_max) 로 읽음 (선행 분석과 같음). p_max · T_start · T_end · 평지 비율 · 목적지 비율 미기재 → p_max 0.9 · T_start 500 · T_end 4000 iteration · 평지 10 % · 세 목적지 균등 (이 명세의 결정). gap 은 처음부터 고정 비율(20 %)로 배정 |
| 배치 비율 | 미기재 | 열(column) = 지형 종류, 행 = 레벨 (Lab TerrainGenerator curriculum). 비율은 p_advance 로 reset 때 열을 다시 뽑음 (3.2 절) |
| 평가 (검증 목표) | 500 회 × 6 m 주행 × 무작위 지형 10 개, 레벨마다 성공률 · 주파율, 최고 레벨 MEV (P354). F6 눈금 읽기: START 성공률 모든 표시 레벨에서 ≈ 100 %, PIE 는 최고 레벨에서 돌 ≈ 70 % · 평균대 ≈ 60 % · 징검 빔 ≈ 25 % · gap ≈ 60 % | 같은 규약으로 측정하되 Go2 결과를 논문 수치와 「같다」 고 쓰지 않음 |

### 1.10 도메인 무작위화 (§II-D-1 「[31] 을 따름」) · 전부 인용 저작 (PIE 표 II)

| 항목 | PIE 표 II 범위 | Isaac Lab 대응 |
|---|---|---|
| 적재 질량 | [−1, 2] kg | `randomize_rigid_body_mass` (base, add) (Lab `envs/mdp/events.py:286`) |
| Kp · Kd 배율 | [0.9, 1.1] | `randomize_actuator_gains` (:541) |
| 모터 강도 배율 | [0.9, 1.1] | 기본 이벤트 없음 → 토크 출력에 env 별 배율 곱하는 **새 이벤트** |
| 질량중심 이동 | [−50, 50] mm | `randomize_rigid_body_com` (:400) |
| 마찰 | [0.2, 1.2] | `randomize_rigid_body_material` (:155) |
| 초기 관절 위치 배율 | [0.5, 1.5] | `reset_joints_by_scale` (:1238) |
| 시스템 지연 | [0, 15] ms | 행동 지연 버퍼 (E1 에 없음 · `isaaclab.utils.buffers.DelayBuffer` 로 새로 붙임) |
| 카메라 위치 | x · y · z 각 [−10, 10] mm | reset 때 `RayCasterCamera.set_world_poses` 로 env 별 offset 재설정 (Lab `ray_caster_camera.py:163`) |
| 카메라 pitch | [−1, 1]° | 같은 이벤트 |
| 카메라 수평 FOV | [86, 88]° | `set_intrinsic_matrices` (:125). 60×60 crop 에서는 FOV 비례로 환산 (2 절) |
| 몸 질량 | 본문에 언급, 범위 없음 | 적재 질량 항으로 대신 (추가하지 않음) |

PIE 에 없고 START 에도 없는 것(외란 push · 관측 잡음 · 깊이 잡음)은 기본 설정에 **넣지 않는다**. 깊이 잡음은 2.4 절의 선택 항목.

### 1.11 깊이 시뮬레이션 (§II-D-1, P221)

| 항목 | 논문값 · 근거 | 우리 선택 |
|---|---|---|
| 해상도 · 렌더러 | 60 × 60, NVIDIA Warp 로 렌더 (Isaac Gym 기본 카메라 대신) (P221) | Lab `RayCasterCamera` = Warp 광선 투사 (`ray_caster_camera.py:18, 293`) → 논문과 같은 종류. 3 절 |
| 주기 | 실기 10 Hz (P379) | `update_period = 0.1` s |
| FOV · 내부 파라미터 · 장착 | 미기재 | 2 절 (D435i 사양에서 유도) |
| 깊이 범위 · 정규화 | 미기재 | near 0.2 m · far 3.0 m, (d − 0.2)/2.8 을 [0, 1] 로 clip, 미검출(inf · nan) 은 1.0 (RPL `go2_distill_config.py` depth_range [0, 3] 과 PIE 의 D435i MinZ 를 합친 이 명세의 결정) |
| 다리 자기 가림 | 미기재 | 정적 지형 mesh 만 투사 (다리 미렌더). 필요하면 `MultiMeshRayCasterCamera` 로 다리 mesh 추가 가능 (추가 옵션, 비용 미확인) |
| 잡음 | 미기재 (PIE 는 카메라 자세 · FOV 무작위화만) | 1.10 절의 카메라 DR 만. 그 이상은 2.4 절 선택 |

### 1.12 실기 배포 (§III-C, P379, P528)

| 항목 | 논문값 | 우리 (Go2) |
|---|---|---|
| 카메라 | 머리의 Intel RealSense D435i, raw 깊이 10 Hz | 같음 (장착 자세는 2 절) |
| 필터 | librealsense decimation · temporal · hole-filling → 60×60 | 계수 미기재 → 2.3 절 |
| 연산 | Jetson Orin NX + TensorRT, 행동 50 Hz | Go2 EDU Plus 는 Orin NX 16 GB (100 TOPS) (판매 사양; 우리 기체가 Plus 인지 **미확인**) |
| 속도 | 최대 1.5 m/s 로 주파 (P529) | 명령 범위와 같음 |
| TR-Net tick | 미기재 | 새 프레임마다 10 Hz, 정책 50 Hz 는 마지막 지도를 유지 |

### 1.13 ablation 8 종 (§III-A) · 검증 설계의 기준

HMap GT · PIE (START w/o TR-Net, 2D-GRU 암시 encoder) · TR-Net w/o Prop · w/o GRU (MLP 대체) · w/o Refine · START w/o AdaSmpl · w/o FtEdge · w/o TerProg. 실기 표 II (5 회): START 성공률 돌 1.0 · 평균대 0.8 · 징검 빔 1.0 · gap 1.0. 우리 최소 재현 세트: START · HMap GT · w/o AdaSmpl (4.4 절).

## 2. Go2 + D435i 적응 (로봇 고유 항목만)

### 2.1 Go2 와 Lite3 의 기하 (URDF 에서 직접 읽음)

| 항목 | Lite3 (논문 로봇) | Go2 (우리) | 비고 |
|---|---|---|---|
| hip 간 거리 (앞뒤) | 0.349 m (HipX x ±0.1745) | 0.3868 m (hip x ±0.1934) | 논문 「2× 로봇 길이 = 0.7 m」 의 로봇 길이는 이 값 |
| 좌우 발 간격 | 0.319 m (0.062 + 0.09735) × 2 | 0.284 m (0.0465 + 0.0955) × 2 | Go2 가 더 좁음 → 0.175 m 평균대 · 0.175 m y 간격 돌에서 불리하지 않음 |
| 다리 길이 (thigh + calf) | 0.200 + 0.210 = 0.410 m | 0.213 + 0.213 = 0.426 m | |
| 발 반지름 | 미확인 | 0.022 m (URDF sphere) | edge 거리는 발 중심 기준 |
| 기본 서기 높이 | 미확인 | ≈ 0.333 m (thigh 0.8 · calf −1.5 · 발 반지름 포함, 계산값) | 카메라 높이 계산에 씀 |

지형 치수는 **논문값 그대로** (축소 금지). Go2 기준으로 넓히는 것(gap 0.774 m)은 팀장 결정 항목.

### 2.2 D435i 깊이 사양과 60×60 경로

- Intel 사양 페이지 (https://www.intel.com/content/www/us/en/products/sku/190004/intel-realsense-depth-camera-d435i/specifications.html): 깊이 FOV **H 87° · V 58°**, 깊이 출력 1280×720 30 fps, 능동 스테레오, 동작 범위 약 0.3 ~ 3 m. Intel 지원 문서는 렌즈 공차로 FOV ±3° 변동이라고 적음 (PIE 가 HFOV 를 [86, 88]° 로 흔드는 이유와 맞음).
- MinZ: Intel BKM 튜닝 자료는 D435 848×480 에서 MinZ 17 cm, 해상도에 비례. 우리 near clip 0.2 m 는 이 값 위.
- 논문은 「decimation · temporal · hole-filling 뒤 60×60」 만 적었다 (P379). 16:9 스트림을 decimation 만으로 정사각형으로 만들 수 없으므로 crop 이 끼어 있다고 읽는다. **우리 경로 (이 명세의 결정)**: 848×480 → decimation 배율 8 → 106×60 → 가운데 60 열 crop → 60×60. 결과 FOV ≈ **56.5° × 58°** (계산: 2·atan(tan(43.5°)·60/106)). 대안(전체 87° 를 60 열로 비등방 축소, FOV 87°×58°)은 픽셀 각이 가로세로 1.75 배 달라 CNN 에 불리 → 채택 안 함.
- 60×60 내부 파라미터 (유도값): f_x ≈ **55.9 px**, f_y ≈ **54.1 px**, c_x = c_y = 30. Isaac Lab `PinholeCameraPatternCfg(width=60, height=60, focal_length=24.0, horizontal_aperture=25.78, vertical_aperture=26.61)` 이 같은 값을 준다 (Lab `ray_caster_camera.py:395~398`: f = width × focal / aperture). 또는 `PinholeCameraPatternCfg.from_intrinsic_matrix([55.9, 0, 30, 0, 54.1, 30, 0, 0, 1], 60, 60)`.
- **실측 관문**: 실제 기체에서 `rs-enumerate-devices -c` 로 848×480 깊이 스트림의 fx · fy · ppx · ppy 를 읽어 위 유도값과 대조한다. 어긋나면 실측값으로 시뮬 내부 파라미터를 바꾼다 (유도값은 ±3° 공차 안의 추정).

### 2.3 librealsense 필터 계수 (논문 미기재 · 우리 선택)

이번 세션은 dev.intelrealsense.com 접속이 실패해 문서 기본값을 **기억으로** 적는다. 실기 코드 작성 전에 문서로 재확인할 것.
- decimation: magnitude 8 (범위 2~8, 2×2 · 3×3 은 non-zero median, 그 이상은 non-zero mean).
- temporal: smooth_alpha 0.4 · smooth_delta 20 · persistency 3 (문서 기본값).
- hole_filling: mode 1 (farest_from_around, 문서 기본값).
- 순서: decimation → temporal → hole_filling (논문이 적은 순서 그대로).
- 시뮬에서는 이 필터를 돌리지 않는다. 광선 카메라는 구멍이 없으므로 hole-filling 의 효과(먼 값으로 채움)는 「미검출 = far」 규칙으로 대신한다. temporal 필터의 시간 평활은 시뮬에 없음 → 차이는 실기 전에 기록된 실제 깊이와 시뮬 깊이를 같은 계단에서 비교해 잰다 (4.5 절).

### 2.4 장착 자세 · 지연 · 선택 잡음

| 항목 | 참고값 | 우리 선택 |
|---|---|---|
| 위치 (base 기준) | RPL Go2 D435i: (0.24, −0.0175, 0.12) m, std (0.01, 0.0025, 0.03) (`go2_distill_config.py` sensor.forward_camera) · HiPAN Go1: (0.25, 0, 0.12) · Go2 머리 윗면 joint 원점 (0.285, 0, 0.01) (Go2 URDF `Head_upper_joint`) | **(0.25, 0.0, 0.12) m** (두 선행 구현의 합의값). 실제 브래킷을 단 뒤 자로 재서 고친다 (미확인) |
| pitch (아래로) | RPL: 0.37 ~ 0.43 rad (21 ~ 25°) · HiPAN: 0 · START: 미기재 | **35°** (이 명세의 결정). 근거: 카메라 높이 ≈ 0.45 m, V FOV 58° 에서 지면이 보이는 구간은 pitch 25° → base 앞 0.58 m 부터 지평선, 35° → 0.47 m ~ 4.6 m, 45° → 0.38 m ~ 1.8 m. 지도가 앞 1.1 m 까지이고 1.5 m/s 에서 0.1 s 에 0.15 m 가므로, 발 앞을 더 보는 35° 가 START 의 「발밑 · 뒤는 GRU 기억」 구조에 맞고 항법용 전방 시야(4 m 이상)도 남긴다. 25 · 45° 는 비교 후보 |
| 자세 무작위 | PIE 표 II: 위치 ±10 mm, pitch ±1° | 그대로 (1.10 절) |
| 지연 | START 미기재 · PIE 시스템 지연 [0, 15] ms · RPL 카메라 지연 [0.08, 0.142] s (5 s 마다 재표본) | 기본은 PIE 의 시스템 지연만. 카메라 지연 [0.08, 0.14] s 는 **추가 옵션** (논문에 없음; 실기 측정값으로 정함) |
| 깊이 잡음 | START · PIE 학습 시 없음 · RPL 은 스테레오 잡음 · 블록 아티팩트 모델 | 기본은 없음. 실기 비교(4.5 절)에서 차이가 크면 가우시안 잡음부터 추가 옵션으로 |
| 쿼터니언 (Lab offset, convention "world") | pitch +35° 는 +y 축 회전 | (w, x, y, z) = (cos 17.5°, 0, sin 17.5°, 0) = (0.9537, 0, 0.3007, 0). 부호는 CPU 시험으로 확정 (4.1 U3) |

## 3. Isaac Lab 2.3.2 구현 지도

### 3.1 센서 선택: 수천 env 60×60 깊이를 16 GB 안에서

| 길 | 근거 | 판정 |
|---|---|---|
| **RayCasterCamera** (Warp 광선) | Lab `sensors/ray_caster/ray_caster_camera.py`: `distance_to_image_plane` 지원, `depth_clipping_behavior="max"` 로 미검출을 `max_distance` 로 치환 (:304~319), 정적 mesh 하나 (:47, `ray_caster.py:164`). 지형은 TerrainImporter 가 `/World/ground` 하나로 만들므로 충족 | **채택**. 논문이 Warp 로 렌더한 것과 같은 종류. 비용: 4096 env × 3600 광선 = 14.7 M 광선 / 카메라 tick, 10 Hz 이므로 정책 step 당 환산 2.9 M. E1 의 187 점 × 16384 env = 3.1 M / step 과 같은 급 (E1 은 이 비용으로 돌았음). 버퍼: ray_starts · directions · hits 각 (4096, 3600, 3) float32 = 177 MB × 3 ≈ 0.53 GB, 출력 59 MB |
| TiledCamera (RTX) | Lab 문서: 「RTX 4090 에서 512 카메라 권장」, 「tiled rendering + 영상 네트워크는 큰 메모리」, `--enable_cameras` 필요 (Lab 카메라 문서) | 4096 카메라는 권장의 8 배. 다리 가림 · 재질 효과를 주지만 논문도 그것을 쓰지 않았다. 채택 안 함 (선택 가능성만 기록) |
| MultiMeshRayCasterCamera | Lab `multi_mesh_ray_caster_camera.py` (동적 mesh 가능) | 다리 자기 가림을 넣고 싶을 때만 (1.11 절 추가 옵션) |

카메라 설정 (제안): `RayCasterCameraCfg(prim_path="{ENV_REGEX_NS}/Robot/base", offset=OffsetCfg(pos=(0.25, 0.0, 0.12), rot=(0.9537, 0, 0.3007, 0), convention="world"), pattern_cfg=PinholeCameraPatternCfg(width=60, height=60, focal_length=24.0, horizontal_aperture=25.78, vertical_aperture=26.61), data_types=["distance_to_image_plane"], max_distance=3.0, depth_clipping_behavior="max", update_period=0.1, mesh_prim_paths=["/World/ground"])`. `ray_alignment` 는 카메라 클래스가 "base" 로 강제 (`ray_caster_camera_cfg.py:62~64`) → 머리에 붙은 카메라처럼 roll · pitch 를 따라간다.

### 3.2 정답 지도 · 지형 · 커리큘럼

- **H^b (32×16)**: `RayCasterCfg(prim_path=".../Robot/base", offset=OffsetCfg(pos=(0.3, 0.0, 20.0)), ray_alignment="yaw", pattern_cfg=GridPatternCfg(resolution=0.05, size=[1.55, 0.75], ordering="xy"), mesh_prim_paths=["/World/ground"])`. `grid_pattern` 은 −size/2 … +size/2 를 끝점 포함으로 뽑으므로 (Lab `patterns.py:45~47`) 1.55/0.05 + 1 = 32 · 0.75/0.05 + 1 = 16 점, offset x 0.3 을 더하면 −0.475 … 1.075 (1.3 절과 일치). 값 h = ray_hits_z − base_z. `data.pos_w` 는 base 위치이고 cfg offset 은 광선 시작점에만 들어간다 (`ray_caster.py:220~224, 240~247`) → Lab `height_scan` (pos_w z − hit z − 0.5) 과 같은 꼴로 써도 됨. 평탄화 순서("xy" 의 meshgrid 방향)는 CPU 시험으로 확정.
- **H^f (4 × 5×5)**: 발 링크마다 `RayCasterCfg(prim_path=".../Robot/FL_foot" …, offset pos (0, 0, 20), ray_alignment="yaw", GridPatternCfg(resolution=0.05, size=[0.2, 0.2]))` 4 개. 값 h = hit_z − foot_z. Go2 USD 의 발이 추적 가능한 rigid body 인지는 Kit 에서 확인 (E1 의 ContactSensor 가 `.*_foot` 을 쓰므로 body 는 존재).
- **지형**: `TerrainGeneratorCfg(size=(8.0, 4.0), num_rows=10, curriculum=True, sub_terrains={flat, stones_low, stones_high, balance_beam, stepping_beam, gap})`. 난이도는 행마다 (row_id + η)/num_rows 로 선형 (Lab `terrain_generator.py:50~57`) → 10 레벨. 네 종류는 Lab 기본 함수로 안 된다: `HfSteppingStonesTerrainCfg` 는 돌 폭 · 간격을 난이도로 보간하지만 START 의 열 오프셋 · 두 단계 무작위 · 패치별 깊이가 없고, 평균대 · 징검 빔 · x 축 정렬 gap 은 없다 (`hf_terrains.py:354~`, `mesh_terrains_cfg.py:141~`). → **우리 height-field 함수** (수평 0.025 m · 수직 0.005 m; 0.175 m 폭과 2.5 cm edge 띠를 격자로 표현하려면 0.05 m 로는 부족). 같은 함수가 **edge 거리 래스터** 와 **희소도** 를 함께 내보내면 보상 14 와 검증이 CPU 에서 닫힌다.
- **레벨 커리큘럼**: Lab `terrain_levels_vel` 규칙 그대로 (1.9 절).
- **점진 배정 (TerProg)**: reset 때 env 의 열(지형 종류)을 p_advance 로 다시 뽑는 **새 curriculum 항** (TerrainImporter 의 `terrain_types` · `terrain_origins[levels, types]` 를 직접 갱신). gap 열은 고정 비율.

### 3.3 보상 · 종료 · 명령 · DR · 관측 그룹

- 보상 14 항은 Isaac Lab `RewTerm` 으로. 6 · 9 · 10 은 `asset.data.applied_torque` · `joint_vel` · `joint_acc`, 12 · 13 은 `ContactSensor.data.net_forces_w` (`history_length` 는 1 로 충분; 13 은 현재 step 힘), 14 는 edge 래스터 조회 (발 xy → 패치 지역 좌표 → 이중선형). 8 은 a_{t−2} 버퍼를 action manager 밖에 둔다.
- 종료: `flip` (roll · pitch 1.0 rad) · `foot_below_plane` (발 z < 패치 기준면 − 0.10) · time_out.
- 명령: 1.8 절 샘플러를 `CommandTerm` 으로 새로 (Lab `UniformVelocityCommand` 는 y · yaw 를 독립으로 뽑아 못 씀).
- DR: 1.10 절 표의 대응 함수 + 새 이벤트 둘(모터 강도 · 카메라 자세/FOV) + 행동 지연 버퍼.
- 관측 그룹: `policy` (o_t 45) · `depth` (2×60×60, 카메라 tick 에만 갱신 · 이력 2) · `critic` (s_t 664) · `labels` (v 3 · c 4 · H^b 512 · H^f 100; o_{t+1} 은 저장소에서 다음 step 으로) · `prop_hist` (10 × 45, Lab history_length=10 은 항별 평탄화 · 오래된 것이 앞 (Fable 19a 1 절 확인) → 모듈 안에서 (B, 10, 45) 로 재배열).

### 3.4 rsl_rl 쪽과 메모리 · 처리량 (미확인 항목 포함)

- 새 모듈: `TRNet` · `IEEstimator` · `ActorCriticSTART` · `PPOSTART` (optimizer 셋 · AdaSmpl · 은닉 저장) · `OnPolicyRunnerSTART`. 패턴 참고: E1 `rsl_rl/rsl_rl/modules/actor_critic_recurrent.py` (은닉 상태 rollout 저장) · `runners/on_policy_runner_cts.py` (보조 optimizer 와 rewbuffer).
- 저장소: 깊이를 **카메라 tick 에만 · float16** 으로 저장하면 4096 env × 48 step / 5 × 2 × 3600 × 2 B ≈ 0.57 GB (매 step float32 면 5.7 GB → 안 됨). TR-Net GRU 은닉 (4096 × 512) 과 tick 색인을 함께 저장해 TBPTT.
- VRAM 추정 (**미확인**, 실측 전): 물리 4096 Go2 ≈ E1 과 같은 급(E1 은 16384 env 까지 돌렸음) · 광선 버퍼 0.6 GB · 저장소 0.6 GB + PPO 미니배치(664 × 4096 × 48 float32 ≈ 0.5 GB) · 신경망 활성 (TR-Net 4096 × 2×60×60 forward ≈ 수백 MB) → 10 GB 안쪽으로 보지만 **잰 뒤에 정한다**. 방법을 줄이지 않는 조정 순서: (1) 깊이 float16 · tick 저장 (2) 미니배치 수 4 → 8 (3) env 4096 → 3072 (논문과 같은 수) (4) 두 GPU 는 두 판(시드 또는 ablation) 으로 나눠 씀, 한 판을 두 GPU 로 쪼개지 않음.
- 처리량 (**미확인**): 카메라 tick 비용은 E1 의 scan 과 같은 급이지만 TR-Net · transformer forward 가 매 step 추가된다. 1024 → 2048 → 4096 순으로 step 시간 · 최고 VRAM 을 재고 기록한다 (4.3 절 관문).

### 3.5 위험 목록

1. `distance_to_image_plane` 의 미검출을 `max` 로 치환하면 하늘 · 먼 구덩이가 3.0 m 로 들어온다. 실기 hole-filling 이 먼 값으로 채우는 것과 방향은 같지만 값은 다를 수 있다 (4.5 절 비교).
2. RayCasterCamera 는 지형 mesh 만 본다. 실기에서 다리가 화면 아래쪽을 가리면 분포 차이. 논문도 Warp 렌더였으므로 같은 한계일 가능성이 크지만 **미기재**.
3. 발 RayCaster 4 개 + 몸 RayCaster 1 개 + 카메라 1 개 = 센서 6 개. `update_period` 를 정책 주기에 맞추고 발 scanner 는 yaw 정렬이라 발 링크 roll · pitch 와 무관.
4. 카메라 offset 의 convention · 쿼터니언 부호 오류는 조용히 틀린다 → U3 의 평면 깊이 known-answer 를 Kit 에서도 반복.
5. 고도 field 해상도 0.025 m 로 8 × 4 m 패치 = 320 × 160 셀 × 열 수 × 10 행 → mesh 삼각형 수가 커진다 (E1 의 0.1 m 보다 16 배). Warp BVH 는 감당하지만 생성 시간 · 메모리 **미확인** → `use_cache` 와 실측.
6. TR-Net 이 10 Hz tick 이고 PPO 가 50 Hz 면 한 rollout 48 step 에 tick 9~10 개뿐 → TBPTT 가 짧다. 48 로도 부족하면 steps/env 를 더 올리는 것이 방법 변경 없는 조정.

## 4. 단계별 구축 계획

### 4.1 mai-code 단위 (CPU · 고정 오라클 · 각 단위에 negative control 하나)

| 단위 id | 모듈 범위 | 입력 | 출력 | CPU 오라클 (답을 아는 입력) |
|---|---|---|---|---|
| U1 `start-terrains` | 평지 · 징검돌(저 · 고 무작위) · 평균대 · 징검 빔 · gap 의 height-field 생성 + edge 거리 래스터 + 희소도 계산 (numpy) | 난이도 ∈ [0,1], 시드, 패치 8×4, 수평 0.025 · 수직 0.005 | hf (320×160 int) · edge_dist (m) · sparsity · 패치 깊이 | 최고 난이도 희소도 76.3 ± 0.5 (돌) · 64.7 ± 0.5 (빔); 평균대 폭 0.175 ± 0.025; gap 0.7 ± 0.025; 돌 하나짜리 합성 field 에서 edge_dist 의 해석값(중심 0.1, 모서리 0) 일치; 높이 변화 |Δ| ≤ 0.05; 깊이 ∈ [0.2, 0.7]. negative: 돌 폭을 0.3 으로 바꾸면 희소도 검사가 실패해야 함 |
| U2 `start-gt-maps` | 몸 32×16 · 발 5×5 정답 지도를 hf 에서 CPU 로 뽑는 샘플러 (yaw 정렬 · 셀 중심 좌표 · 평탄화 순서) | hf, base pose (x y z yaw), 발 위치 | H^b 512 · H^f 100 | 계단 하나짜리 해석 지형에서 지도값이 해석값과 ≤ 수직 0.005 차; yaw 90° 회전 시 축 교환; Lab `patterns.grid_pattern` (순수 torch) 을 import 해 같은 (x, y) 순서로 평탄화되는지 대조 (import 안 되면 미확인으로 표기) |
| U3 `start-depth-sim` | 60×60 pinhole 광선 패턴 (2.2 절 내부 파라미터) · 평면 깊이 해석 투사 · crop/정규화/이력 2/지연 버퍼 · 카메라 DR 샘플러 | 내부 파라미터, 자세 (pos · pitch), 평면 높이 | 광선 방향 (3600×3) · 정규화 깊이 2×60×60 | 모서리 광선 각이 ±28.25° · ±29° 와 ≤ 0.05° 차; pitch 35°, 높이 0.45 m 평면에서 각 행의 깊이가 h / sin(각) 해석값과 ≤ 1e−4; 미검출 → 1.0; 쿼터니언 (0.9537, 0, 0.3007, 0) 이 +x 를 35° 아래로 돌림; 이력이 tick 마다 밀림 |
| U4 `start-rewards-cmd` | 보상 14 항 · 종료 2 항 · 명령 샘플러를 순수 torch 함수로 | 가짜 상태 텐서 (fixture) | 항별 값 | 표 I 식과 가중치를 손계산 fixture 와 대조 (각 항 1 건 이상); feet edge: 발이 edge 1 cm 안 → 1.5, 4 cm → 0.5, 6 cm → 0, 비접촉 → 0; stumble 4 배 경계; 명령: 1e5 표본에서 P(v_x = 0) = 0.2 ± 0.01, v_x > 0 이면 ω_z = 0, v_x = 0 이면 ω_z ~ U[−1.2, 1.2] |
| U5 `start-nets` | TRNet · IEEstimator · actor · critic · 세 손실 | 무작위 텐서 | 형상 · 손실 값 · gradient 흐름 표 | 형상 (B, 32, 16) · (B, 112) · (B, 664); KL 폐형식이 수식과 일치; **gradient 경계**: L_PPO 의 backward 뒤 TR-Net · I-E 파라미터 grad 가 None, L_IE 뒤 TR-Net grad None, L_TR 뒤 I-E grad None; 배포 모드 z = μ 로 두 번 호출이 같은 출력; GRU 은닉이 reset 마스크로 0 |
| U6 `start-adasmpl-curriculum` | p_smpl · 치환 마스크 · p_advance · 레벨 규칙 · 열 재배정 | 보상 버퍼, iteration, 거리 | p, 마스크, 새 (level, type) | CV = 0 → p = 0; mean ≤ 0 → p = 1; CV 단조; p_advance 가 T_start 전 0 · T_end 뒤 p_max · 중간 선형; 레벨 규칙: 거리 4.1 m → 승급, 0.5·cmd·T 미만 → 강등, 둘 다면 승급 우선 (Lab 코드 :49~52 와 같음) |
| U7 `start-ppo-runner` | PPOSTART (optimizer 셋 · AdaSmpl · 은닉 · tick 저장) + 아주 작은 가짜 env (CPU) | 가짜 env (지도 8×4 · 깊이 12×12 로 축소한 **시험용** 차원) | 한 iteration 완료 · 체크포인트 왕복 | 합성 선형 정답에서 L_TR · L_IE 가 20 iteration 안에 단조 감소; 저장 → 로드 → 같은 출력; depth 저장이 tick 에만 쓰임 (크기 = steps/5); 옛 E1 체크포인트를 거절 |
| U8 `start-eval` | 평가 집계기 (성공률 · 주파율 · MEV · 복원 MAE cm) | 가짜 궤적 로그 | 표 (레벨 × 지형) | fixture 로그에서 손계산과 일치; MEV 의 「edge 위」 정의는 U1 의 edge_dist ≤ 0 (돌 밖) 또는 ≤ 2.5 cm 중 하나로 **고정해 문서화** (논문 미기재) |

각 단위는 `mai-code-unit-v1` 패킷 형식(unit_id · contract.module · inputs sha256 · outputs · test_argv unittest · negative_control) 으로 발행한다. 시험 차원 축소는 U7 의 가짜 env 에만 허용하고 실제 모듈 기본값은 1~2 절 값이다 (fake-cfg 교훈: 실제 이름 · 차원으로 한 번 더 import 검사).

### 4.2 sol 이 Isaac Lab 에서 통합할 것 (GPU · Kit 실행은 lead)

1. 새 번들 `start_go2` (E1 번들 구조 `source/robot_lab` · `source/rsl_rl` 를 틀로, E1 코드 의존은 로봇 자산 · 환경 뼈대만).
2. `env_cfg.py`: 3.1 센서 1 개 + 3.2 scanner 5 개 + ContactSensor; U1 함수를 `SubTerrainBaseCfg.function` 으로 등록한 TerrainGeneratorCfg; 관측 그룹 5 개; 보상 14 · 종료 3 · 명령 · DR · 커리큘럼 항 등록.
3. 새 이벤트 둘 (모터 강도 · 카메라 자세/FOV) · 행동 지연 버퍼 · a_{t−2} 버퍼.
4. edge 래스터를 지형 생성 결과와 함께 GPU 텐서로 올리고 env 의 패치 index 로 조회하는 조회기.
5. TerProg 열 재배정 항 (TerrainImporter 내부 텐서 갱신).
6. rsl_rl 쪽 네 클래스 등록 · 학습 스크립트 · 체크포인트 · 로그 (p_smpl · 성분 손실 · 복원 MAE · 레벨 분포 · 열 분포).
7. smoke: 16 env 헤드리스 1 iteration → AST import 검사 · 실제 cfg 이름 대조 (가짜 cfg 시험 금지 교훈) → 1024 · 2048 · 4096 env 처리량 · VRAM 실측.

### 4.3 관문 (순서대로 · 앞 관문이 깨지면 다음으로 안 감)

| 관문 | 방법 | 통과 기준 |
|---|---|---|
| G1 CPU 단위 전부 | U1~U8 unittest + negative control | 전부 통과 · negative 전부 실패 |
| G2 Kit 카메라 known-answer | 평지 위 Go2 를 고정 자세로 두고 60×60 깊이 1 장 → U3 해석값과 비교 | 전 픽셀 상대 오차 ≤ 1 % · 미검출 없음 |
| G3 Kit 정답 지도 대조 | 같은 장면에서 RayCaster H^b · H^f 와 U2 CPU 샘플러 | ≤ 0.01 m (수직 0.005 + 보간) · 순서 일치 |
| G4 feet edge 대조 | 발을 edge 에서 1 · 4 · 6 cm 에 놓은 장면 | 1.5 · 0.5 · 0 |
| G5 처리량 · VRAM | 1024 → 4096 env, 각 20 iteration | 4096 에서 최고 VRAM < 14 GB · step 시간 기록 (기준 없음 · 보고) |
| G6 TR-Net 단독 복원 (진단) | E1 또는 무작위 행동으로 모은 (깊이 · 이력 · H^b) 로 TR-Net 만 지도 학습 | 평균 높이 예측 기준선보다 MAE 가 낮고, 최고 레벨 MAE 를 cm 로 보고 (논문 눈금 3.6 · 1.8 · 4.8 · 1.5 와 나란히, 「같다」 금지). 이 단계는 방법의 일부가 아니라 배선 진단 |
| G7 AdaSmpl 거동 | 본 학습 첫 500 iteration | p_smpl 이 1 근처에서 시작해 CV 하강과 함께 내려감 · 치환 비율 로그가 p 와 일치 |
| G8 본 학습 | START 4096 env 10000 iteration, 두 번째 GPU 에 HMap GT | 레벨 분포 · 열 분포 · r_feetedge 상승 (F8 모양) |
| G9 평가 | U8 규약 (500 × 6 m × 10 지형 × 레벨) | 표 (레벨 × 지형 × 지표) · MEV · 복원 MAE |

### 4.4 ablation 최소 세트와 두 GPU

- 1 차: START (GPU 0) · HMap GT (GPU 1). HMap GT 는 상한이자 「TR-Net 외 전부가 제대로 배선됐는가」 의 검사.
- 2 차: START w/o AdaSmpl · START w/o FtEdge (논문 F6 에서 차이가 가장 큰 두 항). 나머지 네 TR-Net 변형은 시간이 남을 때.
- 시드는 판당 1 → 「경향」 으로만 쓴다 (Fable 19a 6 절 11 번과 같음).

### 4.5 실기 전 비교

- 실제 D435i 를 Go2 에 단 자세로 알려진 계단(높이 0.1 m) 앞 0.5 · 1.0 m 에서 필터 뒤 60×60 을 기록하고, 같은 자세의 시뮬 깊이와 픽셀별 차이 분포를 낸다. 차이가 정규화 0.05 를 넘는 영역이 10 % 이상이면 2.4 절 선택 잡음 · 지연을 켠다 (팀장 결정).
- rs-enumerate-devices 내부 파라미터 실측 (2.2 절).
- TensorRT 변환 전에 PyTorch CPU 로 1 step 지연을 재고 10 Hz · 50 Hz 예산 안인지 본다.

## 5. 논문 미기재 · 미확인 요약

- **논문 미기재 (우리가 정함, 1~2 절에 출처)**: H1 · 모든 층 폭 · GRU 은닉 · transformer 층 수 · latent 차원 · 디코더 · 지도 격자 셀 수와 좌표 · 높이 기준 · 깊이 범위 · 정규화 · 카메라 FOV · 내부 파라미터 · 장착 자세 · 필터 계수 · 종료 임계 둘 · 에피소드 길이 · 명령 재표본 주기 · PPO 하이퍼 · steps/env · 레벨별 지형 치수 · 낮은 무작위 그룹 이동량 · p_max · T_start · T_end · 평지 비율 · gap 개수 · 충돌 몸체 · 접촉 임계 · edge 정의 · MEV 의 「edge 위」 정의 · AdaSmpl 창 · 치환 단위 · gradient 경계 · TR-Net tick 주기 · H2 프레임 간격 · 다리 렌더 여부 · 그림 5 · 6 의 정확한 수치.
- **미확인 (실행 · 실측 전)**: 4096 env 처리량 · VRAM · 학습 시간 · 복원 MAE · 성공률 · Go2 EDU 의 Orin 종류 · 실제 장착 좌표 · D435i 실측 내부 파라미터 · librealsense 기본값(기억) · Go2 USD 발 prim 추적 가능 여부 · GridPattern 평탄화 순서 · 0.025 m 고도 field 의 mesh 비용.
- 이 문서는 어떤 코드 · 파일도 고치지 않았고 GPU · Isaac 을 실행하지 않았다.

## 6. 출처

- START: Yu et al., RA-L 2025, arXiv 2512.13153v1 (`C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt` · `.pdf`).
- PIE: Luo et al., RA-L 2024, https://arxiv.org/html/2408.13740v3 (표 II DR · §III-B H1 = 10 · §III-C-1 4096 env).
- Zhang et al., Learning Agile Locomotion on Risky Terrains, https://arxiv.org/html/2311.10484v2 (희소도 정의 · 48 steps · 표 I).
- Intel D435i 사양: https://www.intel.com/content/www/us/en/products/sku/190004/intel-realsense-depth-camera-d435i/specifications.html · Intel D400 FOV 지원 문서 (렌즈 공차 ±3°) · Intel BKM 튜닝 자료 (D435 848×480 MinZ 17 cm).
- Go2 EDU Plus 사양 (Orin NX 16 GB 100 TOPS): https://robostore.com/products/go2-edu-plus-100-tops-computing-quadruped-robot-dog (판매 사양).
- Lite3 URDF: https://github.com/DeepRoboticsLab/URDF_model (`Lite3/urdf/Lite3.urdf`, 이번 세션 내려받아 읽음).
- Go2 URDF: `C:/Users/AI-WS01/s2_lab/_research_repos/rpl_parkour/legged_gym/resources/robots/go2/urdf/go2.urdf`.
- rpl_parkour Go2 설정: `C:/Users/AI-WS01/s2_lab/_research_repos/rpl_parkour/legged_gym/legged_gym/envs/go2/go2_distill_config.py` · `go2_config.py` · `envs/base/legged_robot_noisy.py`.
- Isaac Lab 2.3.2: `C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/{ray_caster.py, ray_caster_camera.py, ray_caster_camera_cfg.py, multi_mesh_ray_caster_camera.py, patterns/patterns.py, patterns/patterns_cfg.py}` · `terrains/{terrain_generator.py, height_field/hf_terrains.py, trimesh/mesh_terrains_cfg.py}` · `envs/mdp/{events.py, observations.py}` · `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/mdp/curriculums.py` · Isaac Lab 카메라 문서 (512 카메라 권장).
- E1 고정본: `C:/Users/AI-WS01/s2_lab/step1_18b_b6_frozen/source/robot_lab/robot_lab/{tasks/go2/env_cfg.py, tasks/go2/rsl_rl_cfg.py, assets/unitree.py}` · `source/rsl_rl/rsl_rl/`.
- 선행 분석: mai-code `start-deep` · `depth-paths-hipan-start-rpl` final.json · `VERIFY-fable-19a.md` · `VERIFY-astra-18h.md` (이 폴더).
