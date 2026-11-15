> 분류: 조사 (사실 수집 · 설계 판단 없음)
> 작성: 오흥재 (lead 하위 조사 · Claude 작성) · 2026-10-13 00:01
> 근거: arXiv HTML 전문 · AME-2 2601.08485v3 (+ PDF v3 의 Fig. 3 · 7 · 16 · 18) · MARG 2509.20036v2 (+ 원본 그림 Fig. 2 · 4 · 7 · 8) · START 2512.13153v1 (+ Fig. 3 · 6) · JEPLO 2609.15770v1 · MoE-CTS 2602.00678v4 (+ PDF p.1~2) · HiPAN 2604.26504v1 (+ Fig. 3) · README: ASIG-X/JEPLO @460e2272 · wertyuilife2/go2_rl_robotlab @28b4516d · HiPAN 프로젝트 페이지 (2026-10-12 조회)
> 요지: 여섯 편 중 관절 목표를 내는 배포 정책이 외부 센서로 지형을 보는 것은 넷(AME-2 · MARG · START · JEPLO)이고, gap · 디딤돌 성공률 숫자를 낸 것은 셋(MARG 시뮬 · START 실기 5회 · AME-2 시뮬 묶음값)이다. 논문만으로 재구현할 때 빠진 숫자는 13개 점검 항목 중 1~6개가 「없음」이고, 층 폭과 PPO 설정이 가장 자주 빠진다.
> 상태: 초안 · 팀장 · lead · ASTRA 논의 전

# 논문 여섯 편의 구조: 논문만 보고 무엇을 만들 수 있는가

이 문서는 사실만 모은다. 어느 방법이 낫다는 판단과 권고는 적지 않는다(lead 몫).
코드 사실은 [SURVEY-star-code.md](../20261008-546-design/SURVEY-star-code.md) 에 있다. 여기서는 되풀이하지 않고 절 번호로만 가리킨다.

## 읽는 법

- 근거 등급은 세 가지다. `논문 확인 (절 · 표 · 그림)` · `README 주장` · `미확인`.
  - 그림 안에 **인쇄된 숫자**는 `논문 확인 (Fig. N)` 으로 적는다.
  - 그림에 숫자가 없어 눈금으로 읽어야 하는 값은 적지 않는다. `미확인` 으로 둔다.
- `lead 제공` 은 이 조사가 직접 재지 않은 우리 쪽 값이다(lead 가 의뢰문에 적어 준 것).
- 읽은 방식: arXiv HTML 을 내려받아 로컬에서 텍스트로 바꿔 **전문을 읽었다**. HTML 에서 그림이 빠진 경우(AME-2 Fig. 3 · 7 · 16 · 18, MoE-CTS Fig. 1)는 PDF 를 열었고, 숫자가 그림에만 있는 경우(MARG Fig. 2 · 4 · 7 · 8, START Fig. 3 · 6, HiPAN Fig. 3)는 원본 그림 파일을 열었다. WebFetch 요약은 쓰지 않았다.
- 「지형을 본다」의 뜻: **관절 목표를 내는 정책**의 입력에 외부 센서(depth · LiDAR)에서 온 지형 정보(지도 · depth · latent)가 들어가는가. 학습 중 teacher · critic 만 보는 경우는 「보지 않는다」로 센다.
- 숫자 표기: 음수는 `-`, 범위는 `~` 또는 `[a, b]`.

---

## 요약 (논의에 걸리는 사실 열 줄)

1. 배포되는 관절 정책이 지형을 보는 것: **AME-2(depth → 학습형 고도 지도) · MARG(Mid-360 LiDAR → 고도 지도) · START(D435i depth → 재구성 고도 지도) · JEPLO(Mid-360 → 구면 depth → JEPA latent)**. 보지 않는 것: MoE-CTS(proprio 만) · HiPAN 의 low-level(proprio 만, depth 는 high-level 명령 정책만 본다).
2. gap 을 학습 지형에 넣은 논문은 AME-2(0.1 → 1.1 m, ANYmal-D) · MARG(10 → 60 cm, Go1) · START(최대 0.7 m, Lite3) 셋이다. JEPLO 논문 · MoE-CTS 논문에는 gap 지형이 없다(JEPLO 코드는 gap 이 켜져 있다: SURVEY §5.11).
3. gap · 디딤돌 숫자: MARG 시뮬 level 6 Single-Gap 20/20 · 돌 계열 16~20/20 (Fig. 8). START 실기 각 5회 디딤돌(76.3 %) 1.0 · gap 0.7 m 1.0 · 평균대 0.2 m 0.8 (Table II). AME-2 시뮬 student Sparse 묶음 91.8 % · 불규칙 디딤돌(Test 1) 90.0 % (Fig. 16), gap 단독 숫자는 없다.
4. 학습 단계: 단일 단계가 넷(MARG · START · JEPLO · MoE-CTS), teacher 뒤 student 가 둘(AME-2 는 지도 모델까지 3단계, HiPAN 은 4단계).
5. MARG 는 **학습 시뮬에 센서를 렌더하지 않는다**(Table III). 시뮬 높이 표본 187개로 학습하고 실기에서만 LiDAR 지도(TMG)로 바꾼다. START · AME-2 student · JEPLO 는 학습 중 env 마다 depth 또는 LiDAR 를 만든다.
6. 실기 센서가 D435i 인 논문은 START · HiPAN 둘이다. MARG · JEPLO 는 Mid-360 LiDAR, AME-2 는 기종 미기재 depth camera + LiDAR-inertial odometry.
7. 명시적 높이 지도를 정책 앞에 두는 것은 셋(MARG · START · AME-2), latent 로만 넘기는 것은 셋(JEPLO · MoE-CTS · HiPAN).
8. 발 디딤 자리 보상은 MARG(feet center) · START(feet edge) 둘. AME-2 는 의도적으로 두지 않았고(IV-D1) JEPLO 도 없다.
9. 빠진 숫자(13개 점검 항목 중 「없음」): AME-2 3 · MARG 3 · START 6 · JEPLO 4 · MoE-CTS 5 · HiPAN 5. 정책 층 크기를 주는 것은 MARG(전부) · JEPLO(encoder 만) 둘이고, PPO 설정을 주는 것은 AME-2 하나다.
10. 공개 코드: AME-2(G1 전용 재구현) · JEPLO(Go2 · Isaac Lab) · MoE-CTS(Go2 두 판)는 있다. MARG 는 「coming soon」, START 는 공식 없음, HiPAN 은 프로젝트 페이지에 코드 링크 없음.

---

## 0. 비교 기준: 우리 MoE-CTS 구현 (lead 제공)

| 항목 | 값 | 근거 |
|---|---|---|
| 저장소 | wertyuilife2/go2_rl_robotlab @28b4516d (Isaac Lab) | lead 제공 · SURVEY §3.2 |
| teacher encoder | privileged 275차원(그중 height scan 187) → latent 32 (L2 정규화) | lead 제공 |
| student encoder | MoE, proprio 이력 45 × 10 = 450 → expert 8 → latent 32 | lead 제공 |
| actor | 77 = latent 32 + 현재 proprio 45 → 관절 목표 12 | lead 제공 |
| critic | 307 | lead 제공 |
| 배포 정책 | student 만. 지형을 보지 않는다 | lead 제공 |
| 잰 약점 | gap 고리에서 E1 model_20499: 생존 46/100, 0.5 m/s 추종 통과 0/100 · 디딤돌 · 저속 · 정지 명령 | lead 제공 (이 문서는 재지 않음) |

논문 쪽 MoE-CTS 사실은 5절에 따로 적었다(논문은 Isaac Gym · 이력 5 다).

---

## 1. AME-2 · arXiv 2601.08485 v3 (2026-09-07, T-RO 조건부 채택)

제목 「Agile and Generalized Legged Locomotion via Attention-Based Neural Map Encoding」. DIRECTION.md 는 v2 를 인용했다. 이 문서는 v3 를 읽었고 v2 와의 차이는 대조하지 않았다(`미확인`).

| 항목 | 내용 | 근거 |
|---|---|---|
| 무엇을 풀려는가 | 민첩성과 처음 보는 지형 일반화를 정책 하나로. attention 기반 지도 encoder + 학습형 고도 지도(neural mapping) | 논문 확인 (Abstract · I) |
| 로봇 · 실기 | ANYmal-D(사족) · LimX TRON1(이족), 둘 다 실기. Unitree H1 은 시뮬만. Go2 없음 | 논문 확인 (I · VI-A) |
| 제어 주기 | 정책 50 Hz, 관절 PD 목표, 실기 400 Hz 추종 | 논문 확인 (III-B) |
| 실기 센서 | depth camera 점군. ANYmal-D 는 앞쪽 카메라 둘을 합치고 TRON1 은 앞 카메라 하나. 지도 융합용 odometry 는 ANYmal-D CompSLAM + Graph-MSF(LiDAR-inertial), TRON1 DLIO | 논문 확인 (V-C) |
| 카메라 기종 · 해상도 · 주기 | 논문에 없다 | 미확인 |
| proprio (teacher) | 잡음 없는 base 선속도 · 각속도 · 중력 투영 · 관절 위치 · 속도 · 이전 행동 · 명령 → MLP | 논문 확인 (III-B · IV-A) |
| proprio (student) | 선속도 · 명령을 뺀 proprio 를 **20 step** 쌓아 LSIO([66])로 시간 embedding, 명령과 함께 MLP. odometry 속도가 잡음 · 지연이 커서 student 에서 선속도를 뺐다 | 논문 확인 (IV-A · V-C) |
| 정책 입력 지도 | ANYmal-D 36 × 14 · 8 cm · base 기준 x = 0.6 m 중심. TRON1 18 × 13 · 8 cm · x = 0.32 m. 점마다 teacher (x, y, z), student (x, y, z, u), u 는 불확실도 | 논문 확인 (III-B · IV-E1) |
| 지도 생성 (student) | 프레임마다 점군 → 국소 2D 격자(칸당 최대 z, 빈 칸은 고정 최솟값) → CNN 이 base 상대 고도와 log-variance 예측 → odometry 로 전역 격자에 Probabilistic Winner-Take-All 융합(식 6~8) → 로봇 주변 조회 | 논문 확인 (V-A) |
| 국소 격자 | ANYmal-D 51 × 31 · 4 cm · x = 1.0 m 중심. TRON1 31 × 31 · 4 cm · x = 0.6 m | 논문 확인 (V-B3) |
| 지도 모델 구조 | 얕은 U-Net + gated residual. 3×3 conv 16채널 ×2 → MaxPool(3, stride 3) → Upsample · concat → 3×3 conv 16채널 ×2 → 1×1 conv 로 불확실도 · raw 추정 · sigmoid gate | 논문 확인 (Fig. 7) |
| 지도 모델 학습 | β-NLL(β = 0.5) + 표본별 total variation 가중. 학습 지형 + 쌓인 상자 · 무작위 heightfield · 떠 있는 상자 메시에서 Warp raytracing 으로 표본. 잡음 · 테두리 자르기 · 가림 · 누락 · outlier 합성. 로봇당 5400만 프레임, 1시간 미만 수렴 | 논문 확인 (V-B · Fig. 6) |
| encoder (AME-2) | CNN 국소 특징 + MLP 위치 embedding → MLP 로 점별 국소 특징. 별도 MLP + max pooling → global 특징. global + proprio embedding → MLP → query. MHA(key · value = 점별 국소 특징) → 가중 국소 특징. [global, 가중 국소] = map embedding. [proprio embedding, map embedding] → MLP decoder → 행동 | 논문 확인 (IV-A · Fig. 3) |
| encoder 층 폭 · head 수 · embedding 차원 | 본문에도 Fig. 3 에도 숫자가 없다. 저자 재구현의 값은 SURVEY §1.5 | 미확인 (논문) |
| critic | MoE([68] 설계). teacher actor 입력 + 링크별 접촉 상태. 좌우 대칭 augmentation 은 critic 에만. teacher · student 가 같은 critic 설계. expert 수는 논문에 없다 | 논문 확인 (IV-B) |
| 학습 단계 | (0) 지도 모델 단독 지도학습 → (1) teacher PPO **80000 iteration**(GT 지도, 처음 20 % 동안 지도 잡음 0 → 최대 · 초기 heading 을 목표 방향 → 무작위로) → (2) student **40000 iteration**: PPO + action distillation([53]) + teacher · student map embedding MSE. 처음 5000 iteration 은 surrogate 손실을 끄고 LR 0.001 | 논문 확인 (IV-C · IV-D3 · IV-E1 · 부록 C) |
| 손실 계수 | action distillation 0.02 · representation 0.2 | 논문 확인 (Table IV) |
| PPO 설정 | value 계수 1.0 · value clip 0.2 · entropy 0.004 → 0.001 · epoch 4 · mini-batch 3 · iteration 당 24 step · env 4800 · adaptive LR · γ 0.99 · λ 0.95 · KL 0.01 | 논문 확인 (Table IV) |
| 명령 | **목표형**: 목표 위치 + 도착 heading. actor 는 목표 거리를 2 m 로 자르고 남은 시간을 뺀다. 실제 거리가 2 m 를 넘으면 학습 중 관측 yaw 명령을 무작위로. critic 은 상대 위치 · yaw sin · cos · 남은 시간 전부 | 논문 확인 (IV-E3) |
| 목표 표본 | AOT(지형 어디든) · EOT(지형 반대 끝). 평균 시작 거리 4 m | 논문 확인 (IV-D3 · 부록 A) |
| 보상 (Table I) | 과제: position tracking 100 · heading tracking 50 · moving to goal 5 · standing at goal 5. 정규화: early termination -10/dτ · undesired events -1 · roll rate -0.1 · joint regularization -0.001 · action smoothness -0.01 · link contact force -0.00001 · link acceleration -0.001. 시뮬 충실도: joint position limit -1000 · velocity limit -1 · torque limit -1. 가중치는 × dτ(0.02 s) | 논문 확인 (IV-D1 · Table I) |
| 보상 세부 | position: 1/(1 + 0.25 d²) · 마지막 4 s 마스크. heading: 마지막 2 s · 0.5 m 안. moving: v_min 0.3 · v_max 2 m/s. undesired events: yaw rate > 2 rad/s · 평지(고도차 30 cm 미만)에서 네 발 공중 · 발 아닌 접촉 · stumble(수평력 > 수직력) · 미끄러짐 · 자기 충돌. **발 디딤 위치 보상은 의도적으로 두지 않음** | 논문 확인 (IV-D1) |
| 종료 | 자세(\|g_x\| > 0.985 · \|g_y\| > 0.7 · 뒤집힘) · base 접촉력 > 체중 · 발 접지 중 thigh 가속 초과(개 60 · 사람 100 m/s²) · 정체(5 s 동안 0.5 m 미만 이동이면서 목표에서 1 m 넘게) | 논문 확인 (IV-D2) |
| 지형 (희소) | Gap 5 %: 0.1 → 1.1 m(ANYmal-D) · 0.6 m(TRON1), 가장자리 ±10 %, 양쪽 높이차 ±30 %. Pallets 5 %: beam 폭 0.4 → 0.16 m, 틈 0.08 → 0.35 m, 높이차 0 → 0.3 m. Stones 30 %: [26] [15] 의 「Stones-Everywhere」를 따른다(치수 없음). Beam 5 %: 폭 0.9 → 0.18 m. 희소 지형 절반은 실제 바닥, 절반은 지도에만 보이는 가상 바닥(-1.5 ~ -0.35 m) | 논문 확인 (부록 A) |
| 지형 (그 밖) | Rough · Stair Down · Stair Up · Boxes · Obstacles 각 5 %, Climbing Up 20 % · Down 5 % · Consecutive 5 % (치수는 부록 A) | 논문 확인 (부록 A) |
| curriculum | 성공률 EMA > 0.5 이고 목표 도달이면 승급, 목표에서 4 m 넘게 남으면 강등, 최고 수준을 넘으면 무작위 수준. 수준 개수는 논문에 없다 | 논문 확인 (IV-D3) |
| DR | payload ±5 kg · 지연 0~0.02 s · 마찰 0.3~1.0. 관측 잡음(선속도 0.1 · 각속도 0.2 · 중력 0.05 · 관절 0.01 rad · 관절속도 1.5 · 지도 0.05 m) · 지도 drift ±0.03 m. student: depth 점 15 % 누락 · 2 % artifact · env 10 % 는 완전 지도 · 지도 점 1 % 를 분산 > 1 m² 무작위값으로 | 논문 확인 (IV-D4 · 부록 B) |
| 규모 | Isaac Gym · RSL-RL. ANYmal-D 약 60 RTX-4090-day(GPU 8장), TRON1 약 30 RTX-4090-day(GPU 4장) | 논문 확인 (IV-E1 · VIII-F) |
| 시뮬 지도 비용 | ANYmal-D 1000 env 에서 지도 모델 추론 0.3 ms 미만 · 약 3 GB, 8 m × 8 m 전역 지도 0.3 GB, depth 점군 등 1.2 GB 추가. 지도를 켠 학습은 GT 지도 대비 약 절반 속도 · 메모리 더 씀 | 논문 확인 (V-C · IV-C) |
| 결과: gap · 디딤돌 (시뮬) | Fig. 16 (ANYmal-D, 0.95 Wilson CI, 시행 수 미기재): teacher Sparse 학습 지형 95.2 % · Test 1(불규칙 디딤돌) 96.8 %. **student Sparse 91.8 % · Test 1 90.0 % · Test 2(디딤돌 + pallet + 높은 단) 77.7 % · Test 3(gap 포함 parkour) 89.1 % · Test 4(잔해) 72.9 % · 평균 82.4 %**. 시각 recurrent student [48]: Sparse 86.4 % · Test 1 34.5 %. teacher 없이 처음부터 student: Sparse 16.7 % · Test 0.0~0.5 %. recurrent 지도 student: Sparse 75.8 % · Test 평균 15.5 % | 논문 확인 (Fig. 16 · VII-A · VII-B) |
| gap 단독 숫자 | 없다. Sparse 는 Gap · Pallets · Stones · Beam 묶음값 | 미확인 |
| 결과 (실기) | 19 cm 평균대, gap 있는 두 beam, 20 cm 높이차의 19 cm 디딤돌 두 줄 등. 사진 · 영상뿐, 시행 수 없음 | 논문 확인 (VI-B2 · Fig. 10) |
| 한계 | 2.5D 지도 · 심한 지각 저하(풀 · 눈) 미대상 · 동적 환경에서 지도 실패 가능 · 기술 전환 구간에서 실패가 많음 · 목표형은 중간 움직임 제어가 덜 직접적 | 논문 확인 (VIII-C · VIII-E · VIII-G) |

**논문에 없는 숫자**: encoder · decoder · critic 층 폭, MHA head 수 · 차원, MoE critic expert 수, LSIO 세부([66] 참조), 에피소드 길이, curriculum 수준 수, Stones 치수, depth camera 시뮬 사양(해상도 · FoV · 주기). 지도 잡음 curriculum 의 「maximum level」이 부록 B 의 지도 잡음 0.05 m 와 같은 값인지는 본문이 잇지 않는다. 저자 재구현(ame2_minimal)이 준 값과 논문 대조는 SURVEY §1.12.

**우리 Go2 · Isaac Lab 에 옮길 때 걸리는 사실**

- 배포 student 가 지형을 본다(neural map). 지도 융합에 odometry 가 필요하고, 논문은 LiDAR-inertial odometry(ANYmal-D) · DLIO(TRON1)를 썼다. depth 카메라만으로 odometry 를 만든 판은 논문에 없다. `논문 확인 (V-C)`
- student 학습에서는 env 마다 시뮬 depth 점군과 지도 모델을 돌린다(위 비용). teacher 학습은 GT 지도만 쓴다. `논문 확인 (IV-C · V-C)`
- 명령이 목표형이다. 저자는 두 명령 체계 결합을 향후 과제로 적었다. `논문 확인 (VIII-C)`
- Go2 설정은 없다. 지도 크기는 「로봇 치수와 지형 크기에 맞춰」 정했다고만 적는다. `논문 확인 (IV-E1)`
- 학습 비용이 GPU 일 단위로 크다(위 규모). 우리 RTX 5080 두 장에서의 비용은 `미확인`.
- 공개 코드 ame2_minimal 은 G1 휴머노이드 전용(SURVEY §1).

---

## 2. MARG · arXiv 2509.20036 v2 (2025-09-27, 각주 DOI 표기 ras.tro.25-0713)

제목 「MARG: MAstering Risky Gap Terrains for Legged Robots with Elevation Mapping」.

| 항목 | 내용 | 근거 |
|---|---|---|
| 무엇을 풀려는가 | 위험한 gap 지형(gap · 외나무다리 · 평균대)을 LiDAR 하나로 건너기. 다중 센서 · 모션캡처 없이 | 논문 확인 (Abstract · I) |
| 로봇 · 실기 | 학습은 Go1 모델(IV-A). 실기는 Go1 과 Go2. Go2 용 정책을 따로 학습했는지는 적혀 있지 않다 | 논문 확인 (IV-A · IV-B) · 미확인 (Go2 재학습 여부) |
| 실기 센서 · 주기 | Livox Mid-360 10 Hz. 정책 · state estimator · 지도 네트워크 50 Hz 동기. TMG 지도는 100 Hz 갱신(Fig. 10) | 논문 확인 (IV-B · V-G) |
| 실기 연산 · gain | Go1: 탑재 NUC, kp 30 · kd 0.8. Go2: 유선 외부 노트북(i7-12700H), kp 40 · kd 1.2 | 논문 확인 (IV-B) |
| proprio | ω(3) · 중력 투영(3) · 선속도 명령 v*(R³ 로 적힘) · 관절 위치(12) · 속도(12) · 이전 행동(12). 이력 H = 5 (식은 o_t, …, o_{t-H}) | 논문 확인 (II-A1) |
| 지형 입력 | h_t ∈ R¹⁸⁷, 로봇 중심 1.6 m × 1.0 m. 정책에는 상대 높이 z_t - h_t 를 넣는다. 점 배치 · 해상도는 적혀 있지 않다 | 논문 확인 (II-A1 · II-B1) · 미확인 (배치 · 해상도) |
| privileged s̃ (critic) | 실제 선속도 3 · 발 접촉 4 · 링크 질량 4 · 마찰 1 · CoM 2 · 외란력 2 · k_pd 26(kp 1 · kd 1 · 모터 강도 12 · 영점 12) | 논문 확인 (식 1) |
| elevation net | MLP [128, 64, 16], ReLU → e^h ∈ R¹⁶ | 논문 확인 (IV-A) |
| estimator net | MLP [258, 128, 7], ReLU → v̂(3) + ĉ(4) | 논문 확인 (IV-A) |
| actor · critic | actor 512 × 256 × 128 × 12, critic 512 × 256 × 128 × 1 | 논문 확인 (Fig. 2) |
| actor 입력 | [현재 proprio õ_t, e^o(7), e^h(16)] | 논문 확인 (식 4) |
| critic 입력 | [õ_t, s̃_t, e^h] | 논문 확인 (식 5) |
| 숫자 불일치 | 본문은 Estimator [258,128,7] · Elevation [128,64,16]. Fig. 2 (a) 는 같고, (c) 배포 그림은 두 이름이 서로 바뀌어 붙어 있다. estimator 입력 258 은 적힌 proprio 차원 합(45)의 5배(225)와도 6배(270)와도 맞지 않는다 | 논문 확인 (IV-A · Fig. 2) · 미확인 (258 의 구성) |
| 학습 단계 | **단일 단계**. 네 네트워크를 PPO 로 함께. 정책 gradient 가 estimator · elevation net 까지 흐른다. estimator 는 회귀 손실 MSE(v̂, v) + MSE(ĉ, c) 도 받는다. elevation net 에는 재구성 손실이 없다 | 논문 확인 (II-B3 · 식 6) |
| 학습 시뮬 센서 | 학습 시뮬에 외부 센서 없음(Table III 「Extra sensors during simulation ×」). 시뮬 높이 표본으로 학습하고 실기에서만 TMG 지도로 바꾼다 | 논문 확인 (Table III · V-A) |
| PPO 설정 | 「[47](legged_gym 논문)에 적힌 것」이라고만 함 | 미확인 (논문 안) |
| 명령 | 속도 추종(선속도 · yaw rate 보상). **학습 명령 범위는 논문에 없다.** 평가 명령 0.9 m/s | 논문 확인 (Table I · V-C) · 미확인 (범위) |
| 보상 (Table I) | 선속도 추종 exp(-4 ‖·‖²) 1.0 · 각속도 0.5 · v_z² -2.0 · ‖ω_xy‖² -0.05 · torque -e⁻⁵(원문 표기) · action rate -0.01 · 관절 가속 -2.5e-7 · collision -n 에 가중 1.0 · orientation -0.2 · joint motion limit -0.02 · feet air time Σ(t_air - 0.5) 1.0 · feet stumble(‖f_xy‖ > 4\|f_z\|) -1.0 · feet center c_t(n² + 2n³) -0.01 | 논문 확인 (Table I) |
| feet center 정의 | 발 주변 9점. 접촉점 Type 1, 5 cm 안 Type 2, √50 cm 안 Type 3. 점 높이 < -0.2 면 가장자리로 센다 | 논문 확인 (II-C · 식 7 · Fig. 3) |
| 종료 | trunk · hip 충돌, 발 높이 -0.2 m 아래, 20 s 갇힘 | 논문 확인 (IV-A) |
| 지형 · curriculum | Single-Gap · Stones-Everywhere · Stones-2Rows · Stones-Balance · Beams-Balance · Air-Beams-Balance 6종 × **8 수준**, game-inspired curriculum([46]). 승급 규칙 · 지형 비율은 없다 | 논문 확인 (IV-A) · 미확인 (규칙 · 비율) |
| 수준 1 · 4 · 8 치수 | Single-Gap 10 / 40 / **60 cm**. Stones-Everywhere 틈 5/15/40 cm · 돌 80/60/30 cm · 높이 0~8/0~24/0~36 cm. Stones-2Rows 틈 10/15/30 · 돌 80/55/30 · 높이 0~8/0~24/0~44. Stones-Balance 틈 10/50/40 · 돌 80/55/30 · 높이 같은 값. Beams-Balance 틈 10/20/40 · 폭 30/25/20 cm. Air-Beams-Balance 틈 10/20/40 · 돌 30/30/20 · 높이 0~4/0~24/0~44. 나머지 수준 값은 없다 | 논문 확인 (Fig. 4) |
| DR (Table II) | Kp 배율 [0.9, 1.1] · Kd 배율 [0.9, 11](원문 그대로) · payload [-1.0, 2.0) kg · 지연 [0, 12] ms · 마찰 [0.2, 1.25) · CoM [-0.05, 0.05) m · 모터 강도 [0.9, 1.1] · 지형 지도 잡음 [-5, 5) cm | 논문 확인 (Table II) |
| 규모 | Isaac Gym · Go1 4096 env · **20000 「episodes」**(단위 원문 그대로, iteration 인지 미확인) · A100 1장 · 약 12시간 · GPU 메모리 약 12 GB | 논문 확인 (IV-A · Table III) |
| 결과: 지형별 (시뮬) | Fig. 8, level 6, 지형별 20회, 발 보상 전부 켠 MARG: Single-Gap **20/20** · Stones-Everywhere 20/20 · Stones-2Rows 18/20 · Stones-Balance 17/20 · Beams-Balance 20/20 · Air-Beams-Balance 16/20. 발 보상 모두 뺀 판: 11/20 · 10/20 · 0/20 · 0/20 · 0/20 · 0/20. level 6 의 치수는 그림에 없다 | 논문 확인 (Fig. 8 · V-D) |
| 결과: 관측 ablation | Fig. 7, gap · 돌 · 평균대 혼합 코스, 0.9 m/s, 50회 성공률: ① [õ, v̂, ĉ, e^h] 0.96 · ② [õ, v̂, ĉ, 지도 직접 ĥ] 0.84 · ③ [õ, v̂, e^h] 0.72 · ④ [õ, ĉ, e^h] 0.1 · ⑤ [õ, e^h] 0.0 · ⑥ [õ, v̂, ĉ](지형 없음) 0.0. 같은 그림 (c)(d) 범례 숫자는 부채꼴 크기와 맞지 않아 옮기지 않았다 | 논문 확인 (Fig. 7 · V-C) |
| 결과 (실기) | Go1: 65 cm gap(trot), 20 cm 외나무다리, 기울기 약 10~15° 평균대. Go2: 9 cm 평균대 · 18 cm 외나무다리 · 여러 gap · 야외. 시행 수 · 성공률 없음 | 논문 확인 (V-G · V-H · Fig. 12 · 14) |
| 한계 | trot 하나뿐 · LiDAR 점군 품질에 의존 | 논문 확인 (V-I) |

**논문에 없는 숫자**: PPO 설정([47] 참조로 미룸), 학습 명령 범위, 에피소드 길이, 수준 2 · 3 · 5 · 6 · 7 치수와 지형 비율, curriculum 승급 규칙, 높이 표본 배치 · 해상도, estimator 입력 258 의 구성, TMG 파라미터(격자 해상도 r · 크기 L · p_hit · p_miss · T_low · T_high · d_near · d_far).

**우리 Go2 · Isaac Lab 에 옮길 때 걸리는 사실**

- 학습 쪽은 시뮬 높이 표본 187개만 있으면 되고 센서 렌더가 없다. `논문 확인 (Table III)` 우리 teacher 입력에도 height scan 187 이 있다 `lead 제공`. 점 배치 · 범위 · 상대 높이 정의가 같은지는 `미확인`.
- 배포에는 Mid-360 LiDAR + TMG(다리 기구학을 넣은 ESKF + 해시 기반 자기중심 지도 + 광선 보간)가 필요하다. depth camera 로 TMG 를 돌린 결과는 논문에 없다. `논문 확인 (III · V-G)`
- 정책은 지형을 보지만 지형 정보는 16차원으로 압축되어 actor 에 들어간다. `논문 확인 (II-B1)`
- 공개 코드 없음: arclab-hku/Risky_gym 은 README 와 gif 뿐(SURVEY §8.1).

---

## 3. START · arXiv 2512.13153 v1 (2025-12-15, 각주에 채택 표기 · 게재지 이름 없음)

제목 「START: Traversing Sparse Footholds with Terrain Reconstruction」.

| 항목 | 내용 | 근거 |
|---|---|---|
| 무엇을 풀려는가 | 희소 발판(디딤돌 · 평균대 · stepping beams · gap)을 단일 시점 depth + proprio 로. 단일 단계 학습 | 논문 확인 (Abstract · I) |
| 로봇 · 실기 | DEEP Robotics Lite3. 실기 실내 · 야외 | 논문 확인 (I · III-C · III-D) |
| 실기 센서 | 머리에 **RealSense D435i**, raw depth 10 Hz → librealsense decimation · temporal · hole-filling 필터 → 60 × 60. Jetson Orin NX · TensorRT, 행동 50 Hz | 논문 확인 (III-C) |
| 시뮬 센서 | depth 60 × 60 을 기본 카메라 대신 NVIDIA Warp 로 렌더. 카메라 위치 · FoV 는 적혀 있지 않다 | 논문 확인 (II-D1) · 미확인 (위치 · FoV) |
| proprio | o_t ∈ R⁴⁵ = ω 3 · 중력 3 · 속도 명령 3 · 관절 위치 12 · 속도 12 · 이전 행동 12. GRU 에 들어가는 이력 길이 H1 은 적혀 있지 않다 | 논문 확인 (II-A1 · II-A2) · 미확인 (H1) |
| depth 이력 | H2 = 2 | 논문 확인 (II-B) |
| 재구성 지도 범위 | 로봇 뒤 0.5 m 부터 앞 1.1 m, 폭 0.8 m, 5 cm 해상도(셀 수 미기재) | 논문 확인 (II-B) |
| critic privileged | 실제 base 속도 · 발 접촉 · body 주변 heightmap H^b · 네 발 주변 heightmap H^f | 논문 확인 (II-A1) |
| TR-Net | depth 이력 → CNN → proprio 특징 z^prop 와 concat → GRU(가려진 뒤 · 아래 기억) → MLP rough decoder → U-Net refine decoder. 손실 MSE(rough, H^b) + L1(refined, H^b). 층 크기는 본문 · Fig. 3 어디에도 없다 | 논문 확인 (II-B · Fig. 3) · 미확인 (층 크기) |
| I-E Estimator | GRU(proprio 이력) → z^prop, CNN(재구성 지도) → z^map, transformer encoder 층으로 융합 → implicit z(VAE) + explicit ê = [v̂, ẑ^b, ẑ^f]. ẑ 는 H^b · H^f 로 decode(「within 0.1 m」). 손실 KL + MSE(다음 proprio) + MSE(v) + MSE(H^f) + MSE(H^b). transformer 층 수 · latent 차원 없음 | 논문 확인 (II-A2 · 식 3) |
| actor · critic | actor [o_t, ê, z] → 관절 목표 12. critic o_t + s_t. asymmetric actor-critic 은 [34](DreamWaQ)를 따름. PPO | 논문 확인 (II-A) |
| 학습 단계 | **단일 단계**. AdaSmpl: 정책 입력 지도를 확률 p = tanh(CV(R)) 로 GT 지도로 바꿔 넣는다(CV 는 에피소드 보상의 변동계수). 배포는 재구성 지도만 | 논문 확인 (II-C) |
| 명령 | 전진 [0.0, 1.5] m/s, **횡속도 0 고정**, 0.3 m/s 미만 전진 명령은 0 으로, 0 일 때 yaw [-1.2, 1.2] rad/s. 후진 없음 | 논문 확인 (II-D1) |
| 보상 (Table I) | 선속도 추종 exp(-‖min(v, v_cmd) - v_cmd‖²/0.25) 1.5 · 각속도 0.5 · v_z² -2.0 · ‖ω_xy‖² -0.05 · orientation -1.0 · torque -1e-5 · action rate -0.01 · smoothness -0.01 · joint power -2e-5 · 관절 가속 -2.5e-7 · joint error -0.01 · collision -10 · stumble(\|F_xy\| > 4\|F_z\|) -1.0 · feet edge -1.0 | 논문 확인 (Table I) |
| feet edge 정의 | 접지 발이 가장자리 2.5 cm · 5 cm 안이면 가중 1.0 · 0.5 | 논문 확인 (II-D2) |
| 지형 | 4종 × 10 수준, [41] curriculum. 디딤돌 최대 sparsity 76.3 %(돌 0.2 m, 틈 x 0.25 · y 0.175 m) · 평균대 최소 0.175 m · stepping beams 최대 64.7 %(폭 0.15 m · 틈 0.275 m) · **gap 최대 0.7 m**. patch 8 m × 4 m, 지형 깊이 [0.2, 0.7] m, 돌 · beam 높이 ±5 cm | 논문 확인 (II-D3) |
| 수준 값 (그림 가로축) | 디딤돌 38.3 / 46.4 / 53.2 / 62.5 / 76.3 %, 평균대 0.4 / 0.3 / 0.25 / 0.2 / 0.175 m, stepping beams 40.0 / 44.4 / 50.0 / 58.8 / 64.7 %, gap 0.3 / 0.4 / 0.5 / 0.6 / 0.7 m. 열 수준 중 이 다섯 점만 보인다 | 논문 확인 (Fig. 6) |
| progressive curriculum | 처음엔 저무작위 디딤돌 + 평지, 이후 확률적으로 고무작위 디딤돌 · 평균대 · stepping beams 로. p_advance 선형식, p_max · T_start · T_end 값은 없다. **gap 은 이 진행에서 제외**. 돌 위치 무작위: 각 돌 틈의 0.5배까지, 열 단위 x 0.45배까지 | 논문 확인 (II-D3) · 미확인 (상수) |
| 종료 | 각도 한계 초과 · 발 높이가 지면 아래 문턱 이하(값 미기재) | 논문 확인 (II-D1) |
| DR | 「[31](PIE)를 따른다」고만 함 | 미확인 (논문 안) |
| 규모 | Isaac Gym · Lite3 3072 env · RTX A6000 1장 · 약 **10000 iteration / 16.6 시간** | 논문 확인 (II-D1) |
| 결과 (실기, Table II, 각 5회) | START: 디딤돌 76.3 % 성공 1.0(traverse 1.00) · 평균대 0.2 m 0.8(0.99) · stepping beams 58.8 % 1.0(1.00) · **gap 0.7 m 1.0**. PIE(TR-Net 없이 implicit): 0.2 · 0.6 · 0.4 · 0.8. TR-Net w/o GRU: 0.2 · 0.2 · 0.2 · 0.4. w/o AdaSmpl: 0.8 · 0.6 · 0.8 · 0.8. w/o FtEdge: 0.6 · 0.4 · 0.4 · gap 0.0. w/o TerProg: 0.2 · 0.4 · 0.6 · 0.4 | 논문 확인 (Table II) |
| 결과 (시뮬) | 500회 · 6 m · 무작위 지형 10개. 수준별 성공률 · traverse · MEV 는 그림(Fig. 6)뿐이고 점마다 숫자가 인쇄되어 있지 않다 | 미확인 (숫자) |
| 실기 속도 | 희소 발판을 최대 1.5 m/s 로 | 논문 확인 (III-C) |

**논문에 없는 숫자**: 모든 층 크기, transformer 층 수, VAE latent 차원, proprio 이력 H1, PPO 설정, DR 값, 지도 셀 수, 카메라 위치 · FoV, p_max · T_start · T_end, AdaSmpl 의 CV 계산 창, 에피소드 길이, 종료 문턱, 수준별 지형 값(최대값과 Fig. 6 다섯 점 외).

**우리 Go2 · Isaac Lab 에 옮길 때 걸리는 사실**

- 배포 정책이 지형을 본다(D435i depth → 재구성 지도). 실기 센서가 lead 가 전한 우리 실기 조건(D435i)과 같은 기종이다. `논문 확인 (III-C)` · `lead 제공`
- 학습 시뮬에서 env 마다 60 × 60 depth 를 렌더해야 하고 논문은 Warp 를 썼다. 우리 기계에서의 렌더 비용은 `미확인`.
- GT heightmap(body · foot)이 critic · TR-Net 감독 · AdaSmpl 세 곳에 필요하다. `논문 확인 (II-A1 · II-B · II-C)`
- 명령이 전진 + 제자리 회전뿐이다(횡 0 · 후진 없음). `논문 확인 (II-D1)`
- Lite3 · Isaac Gym. 공식 코드 없음, 비공식 Go2 · Isaac Lab 각색 Gurukul 은 「논문 결과를 재현하지 않는다」고 스스로 적는다(SURVEY §8.2, `README 주장`).

---

## 4. JEPLO · arXiv 2609.15770 v1 (2026-09-14, 8쪽, 학회 표기 없음)

제목 「JEPLO: Joint-Embedding Predictive Learning for LiDAR-Based Legged Locomotion」. 논문 링크는 ASIG-X/JEPLO README(HEAD 460e2272)의 arXiv 배지에서 확인 `README 주장`.

| 항목 | 내용 | 근거 |
|---|---|---|
| 무엇을 풀려는가 | 지도 · odometry 없는 LiDAR 지각 보행. 가림 · 희소 · 잡음에 강건 | 논문 확인 (Abstract · I) |
| 로봇 · 실기 | **Unitree Go2**, Mid-360 을 앞쪽에 거꾸로 장착, Jetson AGX Orin 64 GB. 실기 실내 · 야외 · 어둠 | 논문 확인 (II · V) |
| 센서 처리 | 수평 FoV 앞 120° · 수직 50° 만. 최근 raw scan 5개 누적(왜곡 보정 없음) → 구면 격자 2° → **60 × 25 depth**(칸별 최소 거리). scan 약 20 Hz. JEPA 10 Hz · 정책 50 Hz | 논문 확인 (II) |
| proprio | o_t ∈ R⁴⁵: roll-pitch rate · yaw rate · 중력 · v_cmd_xy · ω_cmd_z · 관절 위치 · 속도 · 이전 행동. 이력 H_o = 10 · depth H_d = 2 · 행동 H_a = 5 | 논문 확인 (II · III-A) |
| PE-JEPA | MLP(O_t) → z_o ∈ R³² · ViT(D_t) → z_d ∈ R⁶⁴(patch 8 × 4, 6층, head 4, embedding 128) · GRU h ∈ R⁵¹² · 예측 head MLP(h, A) → 다음 step z_o · z_d | 논문 확인 (II · III-A) |
| JEPA 손실 | 한 step latent 예측 MSE + λ(SIGReg(Z_o) + SIGReg(Z_d)), λ = 0.1, 방향 M = 512, Epps-Pulley 통계 | 논문 확인 (식 1 · 2) |
| teacher · student | teacher encoder MLP(O, m, s) → 192차원. student encoder MLP(O, sg(h)) → 192차원, teacher embedding 을 MSE 로 모방. actor π(o_t, z): teacher env 는 teacher z, student env 는 sg(student z). critic V(O, m, s). JEPA · teacher-student MLP 는 모두 3층 hidden 512, 256 | 논문 확인 (II · III-B) |
| teacher 지형 | m_t ∈ R³⁰⁰, 로봇 중심 2.0 m × 1.5 m · 0.1 m. privileged s_t ∈ R⁵⁰(속도 · 발 높이 · 접촉 · 지형 종류 · 몸 접촉력 · 토크 · 모터 gain · 마찰 · 반발 · payload) | 논문 확인 (III-C) |
| gradient 경로 | PPO: actor · critic · teacher encoder. student encoder 는 MSE 만(actor 입력에서 detach). JEPA 는 L_JEPA 만(student 입력에서 detach). 배포는 student encoder 만, 지형 정보는 전부 h_t 로 | 논문 확인 (III-B) |
| 학습 단계 | **단일 단계(CJTS)**. env: student 1024 · teacher 3072. iteration < 5000 은 전부 teacher, 5000 → 10000 에 student env 0 → 1024 와 student surrogate 가중 0 → 1 을 선형으로 | 논문 확인 (III-C) |
| 명령 (Table III) | 재추출 0.25 Hz. Direct(Rough · Discrete · Pyramid · InvPyramid): v_x [-1, -0.5] ∪ [0.5, 1] 확률 0.9 · v_y 같은 범위 0.75 · ω_z [-2, 2] 0.5, 나머지 확률은 0. Waypoint(Boxes · Steps): 속력 [0.5, 1] 확률 0.95 · yaw rate [-1, 1] 로 자름 · 거리 문턱 0.5 m. Rotation(iteration 1000 이후 확률 0.2): v = 0 · ω_z [-2, 2]. heading 명령 입력 없음 | 논문 확인 (Table III · III-C) |
| 보상 (Table I) | 선속도 exp(-4‖·‖²) 2.0 · 각속도 1.0 · v_z² -2(1 - min(k/1500, 1)) · ω_xy -0.05 · 관절 가속 -1e-7 · power -2e-5 · torque -1e-4 · base height -1 - 9 min(k/5000, 1)(목표 0.38 m) · action rate -0.01 · smoothness -0.01 · 원치 않는 접촉(> 5 N) -1.0 · 관절 한계 -2.0 · hip -0.05 · thigh/calf -0.01 · feet regulation -0.05. 지형별 발 위치 항 없음 | 논문 확인 (Table I · III-B) |
| 지형 | Rough · Discrete · Boxes(최대 0.4 m) · Steps(0.1 ~ 0.5 m 증분) · Pyramid · InvPyramid(계단 rise 0.04 ~ 0.20 m · run 0.25 ~ 0.35 m). **gap · 디딤돌 없음**. 지형 curriculum 서술 없음 | 논문 확인 (Fig. 3 · III-C) |
| DR (Table IV) | base 질량 [-2, 5] kg · CoM ±0.03 m · 마찰 [0, 2] · 반발 [0, 0.5] · 초기 관절 배율 [0.5, 1.5] · push 0.25 Hz · Kp [21, 39] · Kd [0.7, 1.3] · 영점 ±0.035 rad · 행동 지연 0~20 ms · proprio 잡음 · LiDAR 원점 drift ±0.03 m · range 잡음 N(0, 0.005²) · depth 지연 0.1 s. 가림 마스크(원 · 사각) 0~2개 | 논문 확인 (Table IV · III-C) |
| 규모 | **Isaac Lab** · RSL-RL PPO · RTX 6000 Pro 1장 · 약 12시간. 비교 실험은 방법마다 15000 iteration. 시뮬 Mid-360 은 [29]를 따름 | 논문 확인 (III-C · IV-A) |
| 결과 | MuJoCo 500회(Table II): 계단(rise 0.2 · run 0.3 m) 59.2 ± 8.3 % · 상자 0.5 m 100 %. gap · 디딤돌 숫자 없음. 실기: 계단 약 1 m/s · 53 cm 상자 · 어둠 · 가림 테이프 | 논문 확인 (Table II · V) |
| 실기 연산 | Jetson CPU 12.4 %(한 코어 기준) · 메모리 1.84 GB · GPU 7.35 % | 논문 확인 (V) |

**논문에 없는 숫자**: PPO 설정, actor · critic 층 폭, 지형 수준 · curriculum, Rough · Discrete 치수, 에피소드 길이, JEPA rollout 길이 T_JEPA, student 최적화 설정. 코드 값과 논문 대조는 SURVEY §5.11.

**우리 Go2 · Isaac Lab 에 옮길 때 걸리는 사실**

- 여섯 편 중 실기 로봇(Go2)과 학습 시뮬레이터(Isaac Lab)가 둘 다 우리와 같은 논문은 이것 하나다. 요구 판도 우리 env 와 같다(SURVEY §5.1 · 요약 5).
- 배포 student 가 LiDAR 로 지형을 본다. 우리 실기 센서가 D435i 라면(lead 제공) 그 조합의 결과는 논문에 없다. `논문 확인 (II · V)`
- teacher-student 구조(CTS)와 proprio 45 · 이력 10 이 우리 구현과 같은 꼴이고, 보상 15항은 go2_rl_robotlab 과 가중치 · schedule 이 같다는 것이 코드 조사 결과다(SURVEY 요약 3).
- 학습 지형에 gap 이 없다(논문). 코드는 gap 을 켜 둔다(SURVEY §5.11).
- 공개 코드 · 체크포인트 있음(SURVEY §5).

---

## 5. MoE-CTS · arXiv 2602.00678 v4 (2026-05-10, RSS 2026)

제목 「Toward Reliable Sim-to-Real Predictability for MoE-based Robust Quadrupedal Locomotion」. 논문 링크는 go2_rl_robotlab README(HEAD 28b4516d)의 배지에서 확인 `README 주장`.

| 항목 | 내용 | 근거 |
|---|---|---|
| 무엇을 풀려는가 | proprio 만으로 강건한 다지형 보행 + RoboGauge(MuJoCo sim-to-sim 지표로 sim-to-real 예측) | 논문 확인 (Abstract · I) |
| 로봇 · 실기 | **Unitree Go2**, 실기 | 논문 확인 (III-D · VI) |
| 센서 | IMU + 관절 encoder 만. 카메라 · LiDAR · 발 접촉 센서 없음 | 논문 확인 (I · III-A) |
| 관측 o_t | ω · 중력 투영 · 관절 위치 · 속도 · v_x · v_y · ω_z 명령 · 이전 행동 | 논문 확인 (III-A) |
| privileged s_t | 선속도 · 높이 표본(로봇 중심 1 m × 1.6 m · 0.1 m 간격) · 발 접촉력 · 관절 토크 · 관절 가속 | 논문 확인 (III-A) |
| 구조 | CTS([49])의 student encoder 를 MoE 로 바꿈. expert K 개 · gating softmax(g(o_{t-H:t})) · z_s = Σ ω_k E_k. load balance 손실 Σ(ω̄_k - 1/K)². MoE 입력 이력 H = 5 | 논문 확인 (III-B · 식 2 · 3 · III-D) |
| K · 층 폭 · latent 차원 | 논문 본문 · Fig. 1 에 없다. 코드 값(expert 8 · latent 32 · L2 정규화)은 SURVEY §3.13 | 미확인 (논문) |
| 학습 단계 | **단일 단계** CTS(teacher · student 동시). 알고리즘 설정은 「CTS[49]를 따른다」 | 논문 확인 (III-B · III-D) |
| 명령 (Table X · XI) | 지형별 상한: Flat v_x ±2.0 · v_y ±1.0 · ω_z ±2.0, Wave · Slope ±1.5 · ±1.0 · ±1.5, Stairs · Obstacle ±1.0 · ±1.0 · ±1.5. 명령 curriculum: 0 ~ 2×10⁴ step ±0.5 · ±0.5 · ±1.0 → 2×10⁴ ~ 5×10⁴ ±1.0 · ±1.0 · ±1.5 → 그 뒤 ±2.0 · ±1.0 · ±2.0 | 논문 확인 (Table X · XI) |
| 명령 표본 | 정지 10 % · 세 축 최대값 조합 20 % · 선속도 0 일 때 최대 각속도 20 %. 누적 명령 길이가 승급 거리를 넘도록 다음 명령 하한을 정하는 dynamic sampling(식 17 · 18) | 논문 확인 (부록 B-B) |
| 보상 (Table IX) | 선속도 exp(-σ‖·‖²) 1.0 · 각속도 0.5 · v_z -2.0(안정되면 0 으로 감쇠) · ω_xy -0.05 · 관절 가속 -2.5e-7 · power -2e-5 · torque -1e-4 · base height -1.0(0.38 m) · action rate -0.01 · smoothness -0.01 · collision -1.0 · joint limit -2.0 · foot regulation -0.05 · hip regulation -0.05 (hip symmetry -1 은 평지 고속 모델만). σ 초기 0.25, 지형 · 난이도 · 명령 크기로 조정(식 15 · 16) | 논문 확인 (III-C · Table IX · 부록 B-A) |
| 지형 | flat · wave · slope(5.7° ~ 29.6°) · rough slope(±5 cm) · stairs up · down(5 ~ 25.7 cm, 디딤면 31 cm) · obstacle(5 ~ 27.5 cm, 폭 1 ~ 2 m). **gap · 디딤돌 없음**. 승급: 최종 수평 거리 4 m 초과 | 논문 확인 (III-D · 부록 B-B) |
| DR (Table I) | 마찰 [0.5, 1.5] · payload ±1 kg · 링크 질량 ×[0.9, 1.1] · CoM ±3 cm · 반발 [0, 0.5] · kp · kd ×[0.9, 1.1] · 모터 강도 ×[0.8, 1.2] · 영점 ±0.035 rad · 지연 0 ~ 20 ms | 논문 확인 (Table I) |
| 규모 | Isaac Gym · 8192 agent · kp 20 · kd 0.5 · 50 Hz / 200 Hz. 총 iteration · GPU · 시간은 없다 | 논문 확인 (III-D) · 미확인 (총량) |
| 결과 (실기, Table VI) | 측면 충격 80 ~ 100 N 18/20 · 타일 계단 15.5 cm 85/85 · 30 cm 장애물 17/20. 평지 4.01 m/s. gap · 디딤돌 숫자 없음 | 논문 확인 (Table VI · VI) |
| 저자가 적은 향후 과제 | exteroceptive 지각을 MoE 표현에 결합해 구조물 장애물 횡단 개선 | 논문 확인 (VII) |

**논문에 없는 숫자**: expert 수 K, 층 폭, latent 차원, PPO 설정, 총 학습 길이, 에피소드 길이(T_ep 기호만), 학습 지형 수준 수, wave 치수. 코드에만 있는 값 목록은 SURVEY §3.13.

**우리 Go2 · Isaac Lab 에 옮길 때 걸리는 사실**

- 우리 현재 방법이다(0절). 논문 판은 Isaac Gym · 이력 5 · kp 20, Isaac Lab 판 코드는 이력 10 · Kp 25(SURVEY §3.13).
- 배포 정책이 지형을 보지 않고, 학습 지형에 gap · 디딤돌이 없다. `논문 확인 (I · III-D)`

---

## 6. HiPAN · arXiv 2604.26504 v1 (2026-04-29, RA-L 2026 채택)

제목 「HiPAN: Hierarchical Posture-Adaptive Navigation for Quadruped Robots in Unstructured 3D Environments」 (KAIST).

**식별**: WebSearch 두 번(「HiPAN quadruped navigation depth camera arXiv」 · 「"HiPAN" robot locomotion OR navigation paper」)에서 이름이 맞는 논문은 이것 하나였다. 사족 · RealSense D435i 실기라는 점도 맞는다. 팀장이 말한 「HiPAN 같은 주행」이 이 논문을 뜻하는지는 팀장 확인 전 `미확인`.

| 항목 | 내용 | 근거 |
|---|---|---|
| 무엇을 풀려는가 | 비정형 3D 환경에서 **목표 지점 내비게이션**: 막다른 길 탈출 · 낮은 통로 아래로 자세 낮추기. 지형 횡단(gap · 디딤돌) 논문이 아니다 | 논문 확인 (Abstract · I · IV-A) |
| 로봇 · 실기 | 학습 · 실기 모두 **Unitree Go1**, 실기에 **RealSense D435i** · Intel NUC · ROS | 논문 확인 (IV-D · V-D) |
| 구조 | 두 층. high-level(10 Hz)이 명령 c = [v_x, v_y, ω_z, 몸 높이 h, roll θ_x] 를 내고, low-level(50 Hz)이 c 를 관절 12개로 | 논문 확인 (IV-B1 · IV-D) |
| low-level teacher | 입력: proprio o_p(관절 위치 · 속도 · 발 위치 · 발 접촉 · roll pitch · ω · 이전 행동) · c · privileged motion(선속도 · 몸 높이 · roll) · privileged domain(heightmap x [-2, 2] · y [-2, 2] m + DR 변수) → domain encoder(2D CNN + MLP) → z_d ∈ R³² | 논문 확인 (IV-B3 · Fig. 3) |
| low-level student | proprio 이력 **50** → domain estimator → ẑ_d, proprio 이력 10 → motion estimator → x̂_m, 현재 o_p · c 와 함께 MLP. **지형을 보지 않는다** | 논문 확인 (IV-B3 · Fig. 3) |
| high-level teacher | privileged 3D occupancy 14 × 11 × 11 + 2.5D 고도 31 × 21(0.1 m) → 3D CNN · 2D CNN → z_s ∈ R³² · proprio · 이전 명령 · motion · 부목표 상대 위치 | 논문 확인 (IV-C3) |
| high-level student | 앞 카메라 depth **180 × 320** → 2D CNN + GRU → ẑ_s · proprio · 추정 motion · 목표 상대 위치 → 명령 | 논문 확인 (IV-C3 · Fig. 3) |
| 학습 단계 | 층마다 teacher PPO → student DAgger(행동 MSE + latent MSE (+ motion MSE)). low-level 먼저, high-level 학습 전이에 low-level student 를 넣는다. 모두 4단계 | 논문 확인 (IV-B2 · IV-C1 · 식 3 · 6) |
| curriculum | low-level: grid-adaptive([37]), 자세 명령을 따라가면 평면 속도 범위 확대. high-level: Path-Guided Curriculum(부목표 간격 1 m 부터 1 m 씩, 지도 · 부목표는 teacher 만) + state count 내적 보상 | 논문 확인 (IV-B2 · IV-C2) |
| 명령 범위 (low-level) | v_x [-1.5, 1.5] · v_y [-1.0, 1.0] · ω_z [-1.5, 1.5] · h [0.1, 0.4] m · θ_x [-1.0, 1.0] rad | 논문 확인 (IV-D) |
| 보상 | high-level Table II(goal arrival 5.0 · state count 0.5 · desired speed 0.25 · 정규화 7항) · low-level Table III(속도 0.4 · yaw 0.2 · 높이 0.2 · roll 0.2 · 정규화 8항) | 논문 확인 (Table II · III) |
| 지형 | low-level: stairs · discrete holes · slopes · flat(치수 없음). high-level: WFC 로 만든 20 × 20 m 환경 6개(평평 · 거친 · 막힌 타일 + 벽 · 탁자 · 떠 있는 상자) | 논문 확인 (IV-A · IV-D) |
| DR (Table I) | payload [0, 3] kg · CoM ±0.1 m · 마찰 [0.7, 1.2] · 반발 [0, 0.1] · 모터 토크 ×[0.9, 1.1], 10 s 마다 충격 | 논문 확인 (Table I · IV-D) |
| depth 시뮬 · 실기 처리 | 시뮬: random erasing · Gaussian blur · 잡음, 카메라 [0.25, 0, 0.12] m 기준 ±0.05 m · pitch ±2.5°, 4 m 에서 자르고 [0, 1] 정규화. 실기: 자르기 · 정규화 · hole-filling | 논문 확인 (IV-D · V-D) |
| 규모 | Isaac Gym · i7-13700 + RTX 4090 1장. high teacher 18 h(1024 로봇) · student 6 h(128). low teacher 12 h(4096) · student 2 h(300). iteration 수 없음 | 논문 확인 (IV-D) |
| 결과 | 내비게이션 성공률 · SPL(Table IV, 예: Complex-2 SR 94.7 %). gap · 디딤돌 숫자 없음. 실기는 그림 · 영상 | 논문 확인 (Table IV · V-D) |
| 한계 | 투명 · 반사면(유리)을 depth 가 못 봐 통과 가능으로 오인할 수 있음 | 논문 확인 (VI) |
| 코드 | 프로젝트 페이지(sgvr.kaist.ac.kr/~Jeil/project_page_HiPAN/)에 코드 링크 없음(2026-10-12 조회). SURVEY 대상 밖 | 미확인 (공개 여부) |

**논문에 없는 숫자**: 모든 층 크기(latent 32 외), PPO 설정, iteration 수, low-level 지형 치수, 에피소드 길이, 카메라 FoV, grid-adaptive curriculum 세부.

**우리 Go2 · Isaac Lab 에 옮길 때 걸리는 사실**

- 실기 센서(D435i)는 lead 가 전한 우리 실기 조건과 같은 기종이다. `논문 확인 (V-D)` · `lead 제공`
- 관절 정책(low-level)은 지형을 보지 않는다. depth 는 high-level 이 명령을 고르는 데만 쓴다. 지형 횡단 능력은 low-level 정책의 몫이다. `논문 확인 (IV-B3 · IV-C3)`
- high-level student 학습에 180 × 320 depth 렌더가 필요하다(128 로봇 · 6 h). 우리 기계 비용은 `미확인`.
- Go1 · Isaac Gym.

---

## 7. 비교표

| 논문 | 배포 관절 정책이 지형을 보나 (센서) | 지형 표현 | 학습 단계 | gap · 디딤돌 근거 | 공개 코드 | 빠진 숫자 (13 항목 중 없음 · 부분) |
|---|---|---|---|---|---|---|
| AME-2 | 예 (depth camera 점군 → 학습형 고도 지도 + 불확실도, odometry 융합) | 36 × 14 (x, y, z, u) → attention encoder(local + global + MHA) | 3 (지도 모델 · teacher 80k · student 40k) | 시뮬 student Sparse 묶음 91.8 % · Test 1 디딤돌 90.0 % (Fig. 16). gap 단독 없음. 실기는 사진 | ame2_minimal (G1 전용, SURVEY §1) | 3 · 4 |
| MARG | 예 (Mid-360 LiDAR → TMG 지도) | 187 상대 높이 → MLP → 16차원 | 1 (PPO + 추정 회귀 동시) | 시뮬 level 6 Single-Gap 20/20 · 돌 · beam 16~20/20 (Fig. 8) · 혼합 코스 0.96 (Fig. 7). 실기 65 cm gap, 시행 수 없음 | 없음 (「coming soon」, SURVEY §8.1) | 3 · 4 |
| START | 예 (D435i depth 60 × 60 → TR-Net 재구성 지도) | 1.6 m × 0.8 m · 5 cm 지도 → CNN + transformer → implicit + explicit | 1 (AdaSmpl) | 실기 각 5회: 디딤돌 76.3 % 1.0 · 평균대 0.2 m 0.8 · stepping beams 1.0 · gap 0.7 m 1.0 (Table II). 시뮬은 그림만 | 공식 없음 · 비공식 Gurukul (SURVEY §8.2) | 6 · 3 |
| JEPLO | 예 (Mid-360 → 구면 depth 60 × 25 → JEPA GRU h) | latent (h 512 → student 192) | 1 (CJTS, student env 를 5k ~ 10k 에 투입) | 없음 (계단 · 상자만) | 공식 ASIG-X/JEPLO (SURVEY §5) | 4 · 1 |
| MoE-CTS | 아니오 (proprio 만) | height 187 은 학습 중 privileged 만 | 1 (CTS) | 없음 (학습 지형에 gap · 디딤돌 없음) | go2_rl_gym · go2_rl_robotlab (SURVEY §3) | 5 · 2 |
| HiPAN | 아니오 (low-level 은 proprio 만). high-level 이 D435i depth 를 보고 명령만 낸다 | high: depth → CNN + GRU latent 32 | 4 (low T→S, high T→S) | 없음 (내비게이션 논문) | 링크 없음 · SURVEY 밖 | 5 · 3 |

### 빠진 숫자 점검표 (13 항목)

「있음」은 논문 본문 · 표 · 그림에 값이 있다는 뜻, 「부분」은 일부만, 「없음」은 논문 안에 없거나 다른 논문 참조로만 미룬 것.

| 항목 | AME-2 | MARG | START | JEPLO | MoE-CTS | HiPAN |
|---|---|---|---|---|---|---|
| 1 지형 encoder 층 크기 | 없음 | 있음 (입력 258 모순) | 없음 | 있음 | 없음 | 없음 |
| 2 actor · critic 층 크기 | 없음 | 있음 (Fig. 2) | 없음 | 없음 | 없음 | 없음 |
| 3 PPO 설정 | 있음 | 없음 ([47]) | 없음 | 없음 | 없음 ([49]) | 없음 |
| 4 학습 길이 | 있음 | 부분 (「episodes」) | 있음 | 있음 | 없음 | 부분 (시간만) |
| 5 병렬 env 수 | 있음 | 있음 | 있음 | 있음 | 있음 | 있음 |
| 6 명령 범위 | 부분 (목표형) | 없음 | 있음 | 있음 | 있음 | 있음 |
| 7 보상 표 | 있음 | 있음 | 있음 | 있음 | 있음 | 있음 |
| 8 지형 치수 (수준별) | 부분 (Stones 없음) | 부분 (수준 1 · 4 · 8) | 부분 (최대값 + 다섯 점) | 부분 | 부분 | 없음 |
| 9 curriculum 규칙 · 수준 수 | 부분 | 부분 | 부분 (상수 없음) | 없음 | 부분 | 부분 |
| 10 proprio 이력 길이 | 있음 | 있음 | 없음 (H1) | 있음 | 있음 | 있음 |
| 11 DR 표 | 있음 | 있음 | 없음 ([31]) | 있음 | 있음 | 있음 |
| 12 에피소드 길이 | 없음 | 없음 | 없음 | 없음 | 없음 | 없음 |
| 13 센서 시뮬 사양 | 부분 | 부분 | 부분 | 있음 | 있음 | 부분 |
| **없음 개수** | 3 | 3 | 6 | 4 | 5 | 5 |
| **부분 개수** | 4 | 4 | 3 | 1 | 2 | 3 |

---

## 8. 논문끼리 겹치는 생각 (사실만, 여섯 편 기준)

1. **관절 정책이 지형을 본다**: 4/6 (AME-2 · MARG · START · JEPLO). 보지 않는 둘(MoE-CTS · HiPAN low-level)은 proprio 이력만 쓴다.
2. **학습 시뮬에서 센서를 만든다**: 지형을 보는 넷 중 셋(START depth · AME-2 student depth 점군 · JEPLO LiDAR). MARG 하나만 학습 시뮬에 센서 없이 높이 표본으로 학습하고 실기에서 지도로 바꾼다(Table III).
3. **명시적 높이 지도를 정책 앞에 둔다**: 3/6 (MARG 시뮬 표본 또는 TMG · START 재구성 · AME-2 학습형 지도). JEPLO 는 높이 지도를 teacher 입력으로만 쓰고 재구성 손실은 두지 않았으며, 학습 뒤 분석용 decoder 로만 복원했다(III-B · VI).
4. **가려진 지형을 신경망 기억으로 메운다**: 3/6 (START TR-Net GRU · JEPLO GRU 512 · HiPAN high-level GRU). AME-2 는 신경망 기억 대신 odometry 융합 지도를 쓰고, recurrent 지도 기준선은 처음 보는 지형에서 낮았다(Fig. 16 Test 평균 15.5 %, Table III). MARG 는 지도 쪽(TMG)이 기억을 맡는다.
5. **학습 중 privileged 정보**: 6/6 이 쓴다(critic 또는 teacher).
6. **단일 단계 학습**: 4/6 (MARG · START · JEPLO · MoE-CTS). teacher 뒤 student: 2/6 (AME-2 · HiPAN). AME-2 는 student 에 RL 손실을 섞었을 때 처음 보는 지형 성공률이 올랐다고 보고한다(VII-B).
7. **속도 · 접촉을 명시적으로 추정해 감독한다**: 3/6 (MARG v · c, START v · 지도, HiPAN v · 높이 · roll). AME-2 는 student 입력에서 선속도를 아예 뺐다. MARG 관측 ablation 에서 속도 추정을 빼면 성공률 0.1(④), 속도 · 접촉 추정을 모두 빼면 0.0(⑤)이었다(Fig. 7).
8. **발 디딤 자리 보상**: 2/6 (MARG feet center · START feet edge). 둘 다 빼면 성능이 떨어졌다고 보고(MARG Fig. 8 · START Table II w/o FtEdge gap 0.0). AME-2 는 지형 무관하게 정의하기 어렵다며 두지 않았다(IV-D1).
9. **stumble 벌점(수평 접촉력이 수직의 일정 배수 초과)**: 3/6 (MARG 4배 · START 4배 · AME-2 1배).
10. **gap 을 학습 지형에 넣었다**: 3/6 (MARG 최대 60 cm · START 0.7 m · AME-2 1.1 m). **디딤돌**도 같은 셋. HiPAN low-level 에는 「discrete holes」가 있다(치수 없음).
11. **gap · 디딤돌 숫자를 냈다**: 3/6 (MARG 시뮬 · START 실기 · AME-2 시뮬 묶음). 실기 시행 수까지 낸 것은 START 하나(각 5회).
12. **명령 체계**: 속도형 5/6 (MARG · START · JEPLO · MoE-CTS · HiPAN low-level 은 속도 + 자세), 목표형 1/6 (AME-2). 정지(0) 명령을 학습 분포에 명시: START(0.3 m/s 미만 → 0) · JEPLO(p_nz 밖은 0) · MoE-CTS(정지 10 %). AME-2 는 목표에서 서 있기 보상. MARG 는 명령 분포를 적지 않았다.
13. **실기 센서**: D435i 2/6 (START · HiPAN), Mid-360 2/6 (MARG · JEPLO), 기종 미기재 depth camera 1/6 (AME-2), 없음 1/6 (MoE-CTS).
14. **실기 로봇이 Go2**: 3/6 (MARG 일부 · JEPLO · MoE-CTS). **학습 시뮬이 Isaac Lab**: 1/6 (JEPLO). 나머지는 Isaac Gym.

---

## 9. 못 본 것

- AME-2 v2 와 v3 의 차이(DIRECTION.md 는 v2 를 인용). MARG 의 T-RO 출판본.
- 각 논문의 보조 영상.
- 참조로 미룬 값(MARG 의 [47], START 의 [31] · [41], MoE-CTS 의 [49], AME-2 의 [26] · [15] · [66])을 따라가 읽지 않았다.
- START Fig. 6 · MARG Fig. 5 · 6 · AME-2 Fig. 18 의 그림 속 선 · 막대 값(인쇄 숫자가 없는 것).
- HiPAN 코드 공개 여부(프로젝트 페이지 외 검색 안 함), Gurukul 코드 내용.
- 우리 기계에서 depth · LiDAR 시뮬 렌더 비용. 아무것도 실행하지 않았다.
