> 분류: A/정책학습 · 반박 검토 (BRIEF-step2-command-lock-review.md Q1~Q7 · 독립 회차 · 심사위원장 관점)
> 작성: 오흥재 (fable 창 · Claude Fable 5.1 작성) · 2026-10-19 08:41
> 근거: START `C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt` · HiPAN `2604.26504.txt` · AME-2 `2601.08485v3.txt` (행 번호는 이 txt 기준, 이 세션이 직접 엶) · Isaac Lab 2.3.2 `C:/isaac/IsaacLab` (`mdp/curriculums.py` · `velocity_env_cfg.py` · `config/go2/rough_env_cfg.py` · `isaaclab_assets/robots/unitree.py` · `terrains/config/rough.py` · `config/anymal_d/agents/rsl_rl_distillation_cfg.py`) · Go2 URDF `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf` · Go1 URDF (unitree_ros GitHub, 아래 URL) · L1 공식 bag `C:/Users/AI-WS01/s2_lab/_external/l1_data/unilidar-2023-09-22-12-42-04.bag` 을 lead 스크립트 재실행 + 독립 검사로 직접 읽음 · legged_gym · Margolis 2205.02824 · JEPLO 2609.15770v1 (세션 임시 폴더 사본) · 저장소 `docs/research/training-benchmarks.md` · `docs/research/20260928-v2-mvp-report.md` · `DECISIONS-step2-lead.md` · `REPORT-astra-10.md` · 웹 URL 은 본문 각주
> 요지: (다) 는 조건부 채택이다. 1 단계(HiPAN 저수준 논문대로) 는 Isaac Lab 2.3.2 에 teacher-student 증류 부품이 이미 있어 11/7 안에 된다. 2 단계는 「1 번과 눈만 다른 대조」 가 아니라 두 논문 어느 쪽도 시험한 적 없는 새 조합이며, 옆 · 뒤 방향 발밑은 START 의 GRU 가 메울 수 없다(한 번도 시야에 든 적이 없는 땅은 기억할 수 없다). 3 단계 고수준 학습 환경에는 계단이 없어 앱 목표만으로는 계단 시연이 보장되지 않는다. 순서를 1 → 3(1 의 저수준 내장) → 2(병렬) 로 바꾸고 저수준 교체는 등록한 관문을 통과할 때만 하라
> 상태: 독립 검토 완료 · ASTRA 19f 미열람 · GPU · Isaac · 학습 · 코드 수정 · 커밋 없음 (L1 bag 읽기는 CPU 전용 venv) · 팀장 결정 전 설계 확정 아님

**판정: (다) 조건부 채택.** 조건은 셋이다. ① 순서를 1 → 2 → 3 이 아니라 **1 → 3 → 2** 로 바꾼다. 3 단계(고수준) 는 1 단계 저수준을 내장해 먼저 끝내 「HiPAN 논문 그대로 한 벌」 을 11/18 전에 확보하고, 2 단계(TR-Net 이식) 는 다른 GPU 에서 병렬로 돌린 뒤 등록한 관문(Q5) 을 통과할 때만 저수준을 바꾸고 고수준 student 를 다시 증류한다(HiPAN 자신이 저수준을 바꾸면 충돌이 는다고 적었다, H:876~880). ② 2 단계를 「1 번과 눈만 다른 대조」 라고 부르지 않는다. 명령 5 칸을 연 채 START 지각을 올리는 것은 두 논문 어느 쪽도 시험하지 않은 새 방법이고, 보상 · 지형 · 커리큘럼 · 학습 틀이 함께 바뀐다(Q3). 「우리 방법」 으로 표시하고 비교 축을 Q5 대로 등록한다. ③ 무대 계단 시연의 구동 경로를 지금 정한다. HiPAN 고수준 환경에는 계단이 없으므로(H:42) 앱 목표만으로 계단을 오르게 하려면 고수준 환경에 계단을 넣는 「우리 추가」 가 필요하고, 아니면 시연은 앱의 수동 vx 명령으로 한다(BRIEF 「손으로 조종」 허용).

## 0. 물음별 한 줄

| 물음 | 답 (첫 문장) |
|---|---|
| Q1 진단 | 반쯤 맞다. 잠근 것은 명령 샘플러 설정 자체(START S:227 · v2 `lin_vel_y (0,0)`)이고, 지형 승급 잣대는 코드상 「출발점에서의 평면 변위」 라 방향을 가리지 않는다. 다만 4 m 폭 패치에 4 m 문턱이면 옆으로는 승급이 불가능해 「앞으로만」 이 합리화됐다. HiPAN 저수준의 지형 승급 규칙은 **논문 미기재**. grid-adaptive 만으로 옆 · 뒤가 열리는지는 vy 가 격자에 들어가는지에 달렸고 그것도 **논문 미기재** |
| Q2 1 단계 | student 입력은 고유수용 이력 50 스텝 + 명령뿐(H:268~272). 눈이 없다. 무대 계단은 **수동 vx 로는 가능성 있음(계단은 저수준 학습 지형, H:632~633)**, 앱 목표(고수준) 로는 **미확인 · 환경에 계단 없음**. Go1 → Go2 에서 깨질 곳은 종아리 속도 한계(URDF 15.70 vs Isaac Lab 모델 30 rad/s) 와 h 상한 0.4 m(무릎 한계에서 기하 최대 0.39 m) |
| Q3 2 단계 | START 의 GRU 는 「지금 가려진 발밑 · 뒤」 를 **본 적이 있을 때만** 복원한다(S:136~138 · S:360). 옆으로 걸을 때 들어오는 땅은 한 번도 시야에 없었으므로 메울 수 없다. L1 이 채워야 하고, 공식 bag 으로 재 보니 URDF 장착 자세에서 0.25 s 에 앞발 · 뒷발 5 cm 칸이 다 채워진다(몸 가림 미반영). 발 가장자리 보상(S:239~257) 은 기하 식이라 방향을 안 가린다. 불안정 위험 7 건은 3 절 |
| Q4 대안 | (다) 조건부 채택. 웹에서 「명령 열림 + 지각 + 코드 + 16 GB」 를 다 만족하는 것은 없다. 가장 가까운 JEPLO 는 센서가 Mid-360(L1 의 약 9 배 점) 이고 GPL + CC BY-NC. AME-2 는 60 · 30 RTX-4090-day → 우리 43 · 21 일(A6) 이라 숫자로 기각 |
| Q5 비교 | 학습 전에 등록할 것: 공통 시험 타일(기존 16 + START 4 종 × 레벨 + 실측 계단), 명령 칸(vx · vy · ωz 격자, 모델별 분포 안 · 밖 표시), 지표 셋으로 나눈 「건넘」(기준선 도달 · 끝까지 생존 · 둘 다) + 주파율 + MEV + 추종률, 판정 규칙(Wilson 구간 · 한 시드) |
| Q6 일정 | GPU 시간은 병목이 아니다. 세 단계 합 약 66~84 GPU·h(추정) 로 두 장 32 일(≈ 1,500 GPU·h) 의 6 % 미만. 병목은 코드 없는 두 논문의 재구현과 디버그 횟수. 11/7 에 1 단계 결과는 된다. 11/25 에 셋 다는 「큰 재작성 0 회」 일 때만 |
| Q7 동결 | 7 절 표 26 행 |

## 1. Q1 진단: 무엇이 명령을 잠갔나

**답: 「앞으로 건넌 거리로 재는 지형 승급」 이 잠근 것이 아니라, 명령 샘플러 설정이 직접 잠갔고 지형 배치가 그 설정을 합리화했다.** 근거를 세 층으로 나눈다.

1. **START 는 설계로 잠갔다.** 「Since terrains align along the x axis, we sample forward velocity commands uniformly from [0.0, 1.5] m/s in the robot frame, with the lateral velocity fixed at zero」 (S:225~227). 0.3 m/s 미만은 0 으로 바꾸고 그때만 ω ∈ [−1.2, 1.2] 를 뽑는다 (S:229~231). 「simultaneous forward walking and turning」 (S:233) 은 저자의 주장이고 분포 자체는 전진 또는 제자리 회전 둘이다(BRIEF 의 읽기와 같음). 지형 패치는 8 m × 4 m (S:275). 승급은 「the curriculum in [41]」 (S:261) = legged_gym 규칙이다.
2. **승급 잣대는 코드상 방향을 가리지 않는다.** legged_gym `_update_terrain_curriculum`: `distance = norm(root_states[:, :2] − env_origins[:, :2])`, `move_up = distance > env_length / 2`, `move_down = distance < |commands_xy| × max_episode_length_s × 0.5` [1]. Isaac Lab 2.3.2 `terrain_levels_vel` 도 같다 (`curriculums.py` 47~51: `torch.norm(root_pos_w[:, :2] − env_origins[:, :2])`, `size[0] / 2`). 즉 「평면 변위」 이지 「앞으로 간 거리」 가 아니다. **그런데** START 패치는 폭이 4 m 라 옆으로는 ±2 m 가 끝이고 문턱은 4 m 다. 옆으로 걸어서는 승급이 **기하적으로 불가능** 하다. 저자가 vy = 0 으로 둔 이유가 여기 있다(「지형이 x 축으로 늘어서 있다」). BRIEF 의 진단은 이 뜻에서 맞고, 「승급이 앞 거리를 센다」 는 뜻에서는 틀리다. 고칠 때 이 구분이 중요한 까닭은, 잣대를 바꿔도 지형 폭과 명령 분포를 안 바꾸면 그대로이고, 반대로 타일을 정사각(8 × 8 m) 으로 두고 명령을 열면 잣대는 그대로 두어도 옆 방향 승급이 된다는 점이다.
3. **v2 도 같은 꼴이었다.** `lin_vel_y (0, 0)` 은 우리가 설정으로 잠갔고(v2 보고 435 · 640), 틈 지형이 앞쪽 띠여서 「명령을 넓히면 로봇이 틈을 향해 서지 않아 노출이 안 생기는」 구조였다(v2 보고 485~489). 해법도 지형 쪽(omni_gap) 이었지 승급 잣대가 아니었다(v2 보고 557~583).

**HiPAN 저수준의 지형 승급 규칙: 논문 미기재.** 저수준 지형은 「rough terrain comprising stairs, discrete holes, slopes, and flat surfaces」 (H:632~633) 뿐이고 레벨 · 승급 · 치수가 없다. 명령 쪽만 있다: 「grid-adaptive curriculum [37], which gradually expands P(c) by introducing higher planar velocity commands once postural commands (hc, θxc) are reliably tracked」 (H:164~165). [37] 은 Margolis 「Rapid Locomotion via RL」 (H:945) 이고, 원문은 전진 속도 × yaw 속도 평면을 0.5 m/s · 0.5 rad/s 격자로 나눠 [−1, 1] 에서 시작하고, 뽑힌 명령의 두 추종 보상이 임계 γ 를 넘으면 이웃 칸에 확률을 더하며, **옆 속도는 격자 밖에서 「작은 균등 분포」 로 따로 뽑는다** [2]. 그러므로:

- **옆 방향이 열리는가.** HiPAN 이 vy 를 격자에 넣었는지 Margolis 처럼 따로 뽑았는지는 **논문 미기재**. 격자 밖이면 vy 는 「처음부터 전체 범위 [−1, 1]」 이거나 「영원히 작은 범위」 둘 중 하나이고, 어느 쪽이든 커리큘럼이 「열어 주는」 것은 아니다. 동결 항목(Q7 F3) 으로 올린다. 권고는 3 차원 격자(vx × vy × ωz) 에 넣고 기록하는 것이다.
- **뒤 방향이 열리는가.** 격자가 0 중심이므로 전진이 열리는 만큼 후진도 열린다(Margolis 규칙). 추종 보상 γ 를 못 넘으면 안 열리므로, 열린 정도는 결과이지 전제가 아니다.
- **지형 쪽이 다시 잠글 위험.** legged_gym 식 평면 변위 잣대를 정사각 타일 위에 쓰면 방향 잠금 기제는 없다. 위험은 다른 데 있다. (a) 명령 격자가 [−1, 1] 에서 시작해 속도가 작을 때 20 s 에 4 m 를 못 가면 지형 레벨이 초반에 고이고(강등 문턱도 |cmd| 에 비례해 같이 낮아지므로 강등은 안 되지만 승급도 안 된다. 같은 지적이 `DESIGN-real-to-sim.md` 1212 에 있다), (b) 옆 · 뒤 명령 때의 실패가 「그 로봇」 을 강등시키므로 어려운 지형 레벨에는 전진 명령 표본이 더 많이 남는 **표본 편향** 이 생긴다. 이것은 잠금은 아니지만 「어려운 지형은 전진으로만 배운」 결과를 낳을 수 있다. 재는 법: 승급 이벤트를 명령 방향 칸(전 · 후 · 좌 · 우 · 회전) 별로 세어 로그에 남기고, 레벨 7 이상 표본의 방향 분포가 명령 분포와 10 %p 넘게 벌어지면 경고(Q7 F4).

## 2. Q2 1 단계: HiPAN 저수준 그대로

**답: student 는 눈이 없다.** 「the student policy πLS takes as inputs the observation o = [op50, c], where op50 = {op,t, …, op,t−49} denotes a history of proprioceptive observations and c is the command」 (H:268~269). op 의 내용은 관절 위치 · 속도, 발 위치 4 개 (pF), 접촉 표시 4 개 (I), roll · pitch, 몸 각속도, 직전 행동이다 (H:198~254). 추정기 둘이 op50 → ẑd (domain), op10 → x̂m (속도 · 높이 · roll) 을 낸다 (H:270~272). teacher 만 지형 높이 지도 xd 를 받는다 (H:264). 따라서 1 단계 산출물은 「명령 5 칸이 열린 **맹목(blind)** 보행」 이다. 이 사실이 2 · 3 단계와 시연의 전제를 정한다.

**무대 계단 시연 가능성.**

| 구동 경로 | 판단 | 근거 |
|---|---|---|
| 앱 수동 vx (손 조종) 로 계단에 올림 | 가능성 있음, **미확인** | 계단은 저수준 학습 지형 (H:632~633). 치수는 논문 미기재. 맹목 계단 보행은 접촉으로 더듬어 오르는 방식이라 단 높이에 민감하다. Isaac Lab 기본 계단은 0.05~0.23 m, 폭 0.3 m (`rough.py` 24~25). 무대 계단 치수 미확인 → 치수를 먼저 재서 학습 분포에 넣어야 한다 |
| 앱 목표점 → 고수준 → 저수준 | **보장 안 됨** | 고수준 학습 환경은 flat · rough · obstructed 타일 + 벽 · 탁자 · 떠 있는 상자 (H:42). 계단이 없다. depth student 는 계단을 「넘을 수 있는 지형」 으로 본 적이 없으므로 피하거나 벽처럼 다룰 수 있다. 실험하기 전에는 모른다(미확인) |
| 고수준 환경에 계단을 넣는 「우리 추가」 | 가능하나 논문 밖 | 저수준이 계단을 배웠으므로 고수준이 계단 위로 명령을 내는 것은 모순이 없다. 다만 PGCL 의 A* 부목표(H:535) 가 계단을 통과 가능으로 다루게 비용 지도를 손봐야 한다 |

**Go1 → Go2 에서 깨질 곳 (URDF 두 개와 Isaac Lab 모델을 직접 대조).**

| 항목 | Go1 | Go2 | 영향 |
|---|---|---|---|
| 몸통 질량 (URDF) · 전체 (사양) | trunk 5.204 kg · 12 kg [3][4] | base 6.921 kg (`go2.urdf` 6) · 약 15 kg [5] | +25 %. HiPAN 적재 DR U(0, 3) kg (H:Table I) 은 Go1 의 0~25 %. Go2 에 같은 절대값이면 0~20 %. 원칙 ② (논문 규칙으로 크기 맞춤) 로는 U(0, 3.75). 동결 항목 F12 |
| 다리 길이 | thigh 0.213 · calf 0.213 [3] | 0.213 · 0.213 (`go2.urdf` FL_calf_joint · FL_foot_joint) | 같다. 지형 치수 환산 불필요 |
| hip 간격 x | 0.1881 [3] | 0.1934 | 3 % 차. 무시 가능 |
| 엉덩이 · 허벅지 토크 | 23.7 N·m [3] | 23.7 (`go2.urdf` 84 · 122) | 같다 |
| 종아리 토크 | 35.55 N·m [3] | 45.43 (`go2.urdf` 160) | Go2 여유 +28 %. 깨지지 않는 쪽 |
| **종아리 속도 한계** | 20.06 rad/s [3] | **15.70** (`go2.urdf` 160) | Go2 가 22 % 느리다. **Isaac Lab Go2 모델은 모든 관절 velocity_limit 30 · DCMotor 23.5** (`unitree.py` 170~176). 시뮬이 실제 종아리의 1.9 배 속도를 허용하므로 계단 · 빠른 스윙에서 **sim 에서만 되는 동작** 을 배울 위험. DECISIONS A4 「Isaac Lab Go2 기본 actuator 유지」 는 토크만 보고 정한 것 → 관절별 속도 한계를 URDF 값으로 동결 (F13) |
| 무릎 가동 범위 | [−2.818, −0.888] [3] | [−2.7227, −0.83776] (`go2.urdf` 160) | 최대 수직 reach = 2 × 0.213 × cos(상한/2) → Go1 0.385 · Go2 0.389 m. **HiPAN h 상한 0.4 m 는 두 로봇 모두 기하 한계와 같다.** 높이 추종 보상 exp(−|hc − h| / 0.0025) (H:Table III r3) 은 0.4 명령에서 0 에 붙는다. 논문도 그 범위로 Go1 을 학습했으므로 원칙 ① 로 두되 추종 오차표(SPEC-hipan L1 검증) 로 「0.38 이상은 추종 불가」 를 기록 (F2) |
| 엉덩이 벌림 범위 | ±0.863 rad [3] | ±1.0472 | Go2 가 넓다. roll ±1.0 rad 명령에 유리 |
| Isaac Lab actuator 모델 | ActuatorNetMLP (`unitree_go1.pt`, `unitree.py` 32~42) | DCMotor 이상 모델 (`unitree.py` 170~176) | Go1 은 실측 모터망, Go2 는 이상 모델. 같은 코드라도 sim-to-real 간극의 출처가 다르다. 논문의 Isaac Gym 모터 모델은 미기재 |
| 발 접촉 표시 I · 발 위치 pF | Go1 발 힘 센서 | Go2 EDU 발 힘 센서 있음(사양) · 위치는 FK | 실기 입력 구성 가능. 지연 · 잡음은 미확인 |

## 3. Q3 2 단계: TR-Net 이식

**답 ①: START 의 GRU 는 옆 · 뒤로 걸을 때의 빈자리를 메울 수 없다. 논문 근거로 그렇다.** TR-Net 의 GRU 는 「retain information about terrain currently occluded beneath and behind the robot」 (S:136~138) 이고, 소거 실험에서 「lacking temporal memory, TR-Net w/o GRU … can only reconstruct terrain **visible from the current viewpoint**」 (S:360) 이다. 즉 기억은 **과거 시점에 보였던 것** 을 지금 위치로 옮겨 오는 장치다. 지도 범위는 뒤 0.5 m ~ 앞 1.1 m × 폭 0.8 m (S:127). 카메라가 앞을 보며 **옆으로** 1.0 m/s 로 걸으면 몸 옆 ±0.4 m 띠로 들어오는 땅은 어느 프레임에도 찍힌 적이 없다(SPEC-start 2 절 기준 pitch 35° 에서 지면 가시 구간은 몸 앞 0.47 m 부터). 0.4 s 안에 띠를 가로지르는 동안 10 Hz 로 4 장이 들어오지만 4 장 모두 앞을 보고 있다. **뒤로** 걸을 때 뒤 0.5 m 밖은 앞으로 지나온 길이 아니면 본 적이 없다. 논문은 이 경우를 평가한 적도 없다(명령 분포가 vy = 0, S:227). 그러므로 「GRU 가 메운다」 는 가정은 **논문 범위 밖** 이고, 연속 지형(계단 · 경사) 에서는 맹목 student 로도 되지만 **희소 발판에서 옆 · 뒤 명령을 실제로 실행하려면 다른 센서가 그 띠를 채워야 한다.**

**답 ②: L1 은 그 빈자리를 채울 수 있다. 공식 bag 으로 직접 재 봤다.** lead 의 `l1_go2_floor.py` 를 재실행하고(h = 0.32) 독립 검사 스크립트를 추가로 돌렸다(CPU, 세션 임시 폴더의 venv, 첫 300 clouds).

| 항목 | lead (BRIEF) | 이 세션 재측정 | 비고 |
|---|---|---|---|
| cloud 주기 | 10 Hz | 9.89 Hz | 300 clouds / 30.22 s |
| 점/초 | 21,131 | 20,792 (2,094 점/cloud) | 표본 창 차이 2 % |
| 반구 | 센서 위쪽만 | 센서 틀 z < 0 인 점 **0 / 628,326** · 고도각 0.2°~89.7° | 「위쪽 반구」 확정 |
| 0.25 s 앞발 5 cm 칸 | 모두 채움 | 16/15 (100 %) · 668 점 | 스크립트의 floor 경계로 15 를 넘게 셈 |
| 0.25 s 뒷발 5 cm 칸 | 모두 채움, 점은 앞발의 약 1/8 | 16/15 (100 %) · 82 점 = 앞발의 1/8.1 | 몸통 · 다리 가림 미반영 → 상한 |
| 장착 | URDF radar_joint pitch 2.8782 rad | `go2.urdf` 748~749: xyz (0.28945, 0, −0.046825) rpy (0, 2.8782, 0) 확인 | 센서 +z 축이 (0.259, 0, −0.966), 즉 **수직 아래에서 앞으로 15°** |

**여기서 내 20c · 20d 결론 하나를 고친다.** 20d 1.1 절에서 「장착 축이 수평에서 30~45° 아래이면 앞발은 안, 뒷발은 밖」 이라 적었다. URDF 를 열어 보니 축은 수평이 아니라 **거의 수직 아래** 이고, 위쪽 반구가 곧 바닥 전체다. 그래서 뒷발도 들어온다(점은 성기다). 20d 의 「뒷발은 60° 이상이어야」 는 전제(축 각도) 가 틀렸으므로 철회한다. 남는 미확인은 몸통 · 앞다리 가림이다. 센서(x 0.29 · z −0.047) 에서 뒷발 바닥점(x −0.19 · z −0.33) 으로 가는 광선은 수평 아래 약 30° 로 배 밑을 지나며 앞다리 두 개의 thigh · calf 를 스친다. 실제 가림률은 실기 녹화로만 잰다(Q7 F20).

**답 ③: 발 가장자리 보상은 방향을 가리지 않는다.** r_feetedge = −Σ_feet c_i · Σ_d ω_d E_d[p_i], E_d 는 발 위치가 가장자리에서 d cm 안인지의 불리언, dist = [2.5, 5.0] cm, ω = [1.0, 0.5] (S:239~257). 기하 식이라 옆 · 뒤 발디딤에도 그대로 성립한다. 단, 학습에서 이 보상은 특권 정답으로 계산되므로 성립하는 것과 정책이 **그것을 피할 수 있는 것** 은 다르다. 옆 발디딤 0.2~0.3 m 는 지도 폭 ±0.4 m 안에 들지만 그 칸의 **내용이 관측된 적이 없으면** 정책은 보수적으로 걷거나 떨어진다. 이것이 L1 채널이 필요한 두 번째 이유다.

**답 ④: 두 논문을 합칠 때의 학습 불안정 위험 (일곱).** 심사자라면 (다)-2 를 「눈만 다른 대조」 로 받지 않는다. 바뀌는 것이 눈만이 아니기 때문이다.

| # | 위험 | 왜 | 어디서 드러나나 |
|---|---|---|---|
| R1 | 학습 틀이 양립하지 않는다 | HiPAN 저수준은 teacher PPO → student DAgger 두 단계 (H:134~168). START 는 비대칭 actor-critic **단일 단계** 에 TR-Net 지도 손실과 AdaSmpl 을 붙인다 (S:50~52 · S:313~). TR-Net 을 student 에 붙이면 「student 가 teacher 를 흉내내는 DAgger」 와 「reconstruction 을 섞어 쓰는 AdaSmpl」 이 한 손실에 들어간다. 둘 중 하나를 고르면 그것은 더 이상 그 논문이 아니다 | 설계 결정 F15. 권고: START 단일 단계 + 명령 5 칸 (즉 「START 에 HiPAN 명령 공간」) 으로 부르고, HiPAN 의 r3 · r4 보상을 추가 |
| R2 | 지도 틀 정의 | START 지도는 「robot's local frame」 (S:127), HiPAN 명령 roll 은 **세계 틀** ±1.0 rad (H:130 · 635). 몸이 57° 기울면 몸 틀 지도는 바닥을 비스듬히 자른다 | 지도 틀을 중력 정렬 yaw 틀로 명시 (F16). START 의 Lite3 는 roll 명령이 없어 이 문제를 안 겪었다 |
| R3 | 카메라 높이가 변한다 | h 명령 0.1~0.4 m 는 D435i 높이를 0.3 m 범위로 움직인다. START 의 depth 분포는 고정 높이였다 (S:379 머리 장착) | TR-Net 입력 분포가 넓어져 복원 오차 상승. DR 로 카메라 자세를 흔드는 것(SPEC-start 1.10 절 ±10 mm · ±1°) 과 차원이 다르다 |
| R4 | 추종 보상 둘이 충돌 | START: 1.5 · exp(−‖min(v, v_cmd) − v_cmd‖²/0.25) 는 **초과 속도를 벌하지 않는다** (S:151). HiPAN: 0.4 · exp(−‖v_cmd − v‖²/0.25) 는 정확 추종 (H:Table III r1) | 하나만 쓴다. 고수준 내장을 생각하면 HiPAN 식(정확 추종) 이어야 고수준이 배운 명령 → 결과 관계가 유지된다 (F9) |
| R5 | 스케줄러 셋이 겹친다 | START 지형 점진 커리큘럼 p_advance(T) (S:303~313) + 지형 레벨 10 단 (S:259~261) + HiPAN grid-adaptive 명령 (H:164~165) | 셋의 상호작용은 두 논문 어디에도 없다. 뒤 · 옆 명령이 희소 발판에서 대량 실패 → 강등 → 희소 발판을 끝내 못 배우는 경로가 열린다 (1 절 (b)) |
| R6 | 명령 분포와 지형의 어긋남 | 76.3 % 희소 징검돌 (S:267) 에서 후진 1.5 m/s 는 Lite3 도 Go2 도 보지 못하는 발판으로 뛰어드는 명령이다 | 두 선택지: 전부 열고 실패를 결과로 보고(원칙 ①) / START 처럼 희소 지형군에서는 전진 분포(원칙 ① 위반 아님: START 가 그렇게 했다). **팀장 결정 ③** |
| R7 | 메모리 | START 는 3072 env 를 48 GB A6000 에서 돌렸다 (S:221). 우리는 16 GB. SPEC-start 3 절의 RayCasterCamera 버퍼 추정 0.53 GB 는 카메라만이고 TR-Net(GRU 512 · U-Net) 의 3072 배치 활성과 PPO 버퍼는 미측정 | 첫 10 update 측정 전에는 **미확인**. 안 들어가면 env 수를 줄이고 steps/env 를 늘려 반복당 표본을 지킨다(20a S-1 의 논리) |

## 4. Q4 대안

**답: 이 자원과 날짜에서는 (다) 를 조건부로 채택한다.** 「명령이 열려 있으면서 지각을 쓰고, 코드가 있고, 16 GB 두 장에 들어가며, 우리 센서(D435i · L1) 와 맞는」 방법은 웹에서 찾지 못했다. 찾은 것을 네 항목으로 견준다.

| 방법 | 코드 · 가중치 | 명령 범위 | 예산 | 실기 기종 · 센서 | 판단 |
|---|---|---|---|---|---|
| HiPAN (H) | 코드 없음 (lead 확인) | vx ±1.5 · vy ±1.0 · ωz ±1.5 · h 0.1~0.4 · roll ±1.0 (H:635) | 저수준 12 h + 2 h · 고수준 18 h + 6 h, RTX 4090 1 장 (H:534~535 · 632~634) | Go1 + D435i (H:882) | 바탕 |
| START (S) | 코드 없음 (lead 확인) | vx [0, 1.5] · vy 0 (S:225~227) | 3072 env · A6000 1 장 · 16.6 h (S:221) | Lite3 + D435i (S:379) | 지각 부품만 |
| JEPLO | 코드 GPL-3.0 + lejepa CC BY-NC (20d 1.6) · 가중치 미확인 [6] | vx [−1, −0.5] ∪ [0.5, 1] (p_nz 0.9) · vy 같음 (0.75) · ωz [−2, 2] (J:425~433) | 4096 env · RTX 6000 Pro · 약 12 h (J:294) | Go2 + Mid-360 (J:28 · 277) · 계단 15~20 cm 전방향 1 m/s (J:277 · 360~361 · 311) | 명령 · 지각 · Go2 · Isaac Lab 2.3.2 모두 맞는 **유일한 후보**. 그러나 센서가 다르다(L1 점수 ≈ 1/9, 20c 1 절) 와 라이선스. 「L1 로 JEPLO」 는 20c 에서 부적정으로 판정 |
| Extreme Parkour | 코드 있음 [7] · 가중치 미확인 | lin_vel_x [0, 1.5] · lin_vel_y [0, 0] · yaw 0 (기본 설정) [8] | 6144 env | A1 + D435 | 전진 전용. 잠금 문제를 그대로 가짐 |
| RPL (Zhuang) | 코드 있음 · Go2 설정 사본 보유 (`go2_field_config.py` lin_vel_x [−0.6, 2.0]) | 옆 범위 사본에 없음 → 미확인 | 38,000 · 60,000 iteration (설정 파일) | A1 · Go1 (+ Go2 배포 문서) | 전진 위주. 희소 발판 아님 |
| ABS | 코드 CC BY-NC · 체크포인트 없음 [9] | 목표 위치 명령(속도 아님) | Isaac Gym | Go1 + ZED mini | 충돌 회피 · 평지. 계단 아님 |
| WMP | Apache-2.0 · 가중치 없음 [10] | 미기재 | **GPU 메모리 약 23 GB** · ≥ 10k iteration | A1 | **16 GB 에 안 들어감** |
| Open-DiffLoco | 코드 있음 [11] · 라이선스 · 가중치 미확인 | 전방향, 옆이 가장 좁음 · 최고 약 2 m/s | 5080 1 장 20~60 분 · < 6 GB | Go2 EDU + AGX Orin | **맹목**. 「명령 열린 보행」 만 급하면 가장 싼 대체재이나 h · roll · 계단 없음 |
| legged-loco | MIT · 체크포인트 없음 [12] | 미기재 | Isaac Lab 1.1.0 | Go2 · H1 | 외부 지각 종류 미확인. 판 차이 |
| Isaac Lab Go2 rough (우리 NVIDIA 기준선) | BSD-3 · 체크포인트 보유 | vx · vy · ωz ±1 (`velocity_env_cfg.py` 103) | 23,000 steps/s · 1,500 iter ≈ 104 분 (training-benchmarks.md) | height scan 187 점 (특권) | 명령은 열렸고 지각은 있으나 **배포 가능한 센서가 아니다**. 비교 기준선으로만 |
| AME-2 | ame2_minimal GPL-3.0 (G1 이식판, 20a) | 목표 위치 + heading (A:86 · A:404) | **60 RTX-4090-day (ANYmal-D, 8 GPU) · 30 (TRON1)** (A:399 · A:1106) | ANYmal-D · TRON1 | 우리 환산 43 · 21 일 (DECISIONS A6, 4090 ↔ 5080 비 추정 1.4) |

**AME-2 를 다시 고려할 이유가 있는가. 숫자로는 없다.** 10/24~11/25 는 32 일이고 두 장이면 64 GPU·일이다. TRON1 규모(30 RTX-4090-day) 만 해도 환산 21 일 × 1 시드이며, 그 뒤 student 증류 · 지도 모델 · 평가가 남는다. 논문 자신이 「trades compute for stronger capabilities」 (A:1106) 라 적었다. 목표 도달 틀(A:1097) 이 잠금 문제를 가장 깨끗하게 푸는 것은 맞지만, 날짜 안에 한 벌을 끝까지 돌릴 수 없는 방법은 심사 대상이 아니다.

**왜 JEPLO 로 갈아타지 않는가.** 명령 · 지각 · Go2 · Isaac Lab 판 · 공개 코드 · 계단 전방향 결과까지 네 항목을 다 채운다. 걸리는 것은 두 가지뿐이고 둘 다 치명적이다. 센서 Mid-360 은 우리 L1 의 약 9 배 점밀도라 JEPLO 의 2° 구면 영상이 L1 로는 0.25 s 에 셀당 0.67 점(20c 1 절) 이고, 코드 반입은 GPL(공개 저장소) 과 CC BY-NC(lejepa) 를 끌어온다. 「JEPLO 의 구면 영상 대신 D435i depth」 는 또 다른 새 방법이다.

## 5. Q5 비교 설계: 학습 전에 등록할 것

**답: 지형 · 명령 · 지표 · 판정 규칙 넷을 하나의 명세 파일로 등록하고 해시를 남긴다.** 세 모델이 서로 다른 분포에서 학습됐으므로 「공정」 은 「같은 시험지 + 각 칸이 그 모델의 학습 분포 안인지 밖인지를 미리 적는 것」 으로 정의한다.

1. **지형 (시험 타일).** (a) 기존 평가 16 종 (v2 평가 규약: 험지 6 + 미경험 10, `20260911-eval-protocol-v2.md` 3 절) 을 그대로 두어 v2 · NVIDIA 와의 연속성을 지킨다. (b) START 4 종(징검돌 · 평균대 · 징검 빔 · 틈) × 레벨 10, 논문 치수 그대로 (S:263~277). (c) 계단: Isaac Lab 기본 0.05~0.23 m (`rough.py` 24) 와 **무대 계단 실측 치수** 한 칸. (d) HiPAN 항법 환경은 별도(Corridor · Room · Complex, H:727~737) 이고 저수준 비교에는 넣지 않는다. 타일 모양은 시드로 안 바뀌므로(eval-protocol 181~192) 지형 시드와 타일 수를 함께 등록한다.
2. **명령.** 격자 vx ∈ {−1.0, −0.5, 0, 0.5, 1.0, 1.5} × vy ∈ {−0.5, 0, 0.5} × ωz ∈ {−0.5, 0, 0.5}, h · roll 은 공통 비교에서 공칭값 고정(NVIDIA · v2 에 그 칸이 없다). 칸마다 모델별 「분포 안 · 밖」 을 미리 적는다: NVIDIA vx ±1 (`velocity_env_cfg.py` 103) 이라 1.5 는 밖 (v2 보고 214~215 가 이미 지적), v2 는 vy = 0 이라 옆 칸 전부 밖, 1 단계는 전부 안. 밖 칸은 「외삽」 으로 따로 표시하고 종합 점수에 섞지 않는다.
3. **지표.** 「건넘」 을 셋으로 나눠 **세 열 다** 남긴다. ① 기준선 도달: 출발점에서 등록한 거리(START 식 전체 거리 6 m, S:354 / 기존 3 m 선) 를 제한 시간 안에 지났는가. ② 끝까지 생존: 제한 시간까지 몸통 접촉 없이 섰는가. ③ 둘 다. 여기에 주파율(쓰러지기 전 간 거리 / 전체, S:354) · MEV(가장자리 디딤 비율, S:354) · 속도 추종률 · 방향 유지를 더한다. 기존 네 축 AND(생존 · 전진 · 속도추종 · 방향, `20260908-success-criteria-anatomy.md` 19) 는 그대로 두되 종합 판정 열로만 쓴다(느려서 떨어지는 판이 51 건 있었다, 같은 문서 33). 항법(3 단계) 은 HiPAN 지표 SR(0.2 m) · SPL (H:737).
4. **판정 규칙.** 칸마다 100 에피소드 · 한 시드 · Wilson 95 % 구간을 적고, 모델 간 차이는 구간이 겹치지 않을 때만 「다르다」 로 쓴다. 시드가 하나이므로 「시드 운」 은 분리하지 못한다고 명세에 적는다. 쌍 비교(같은 타일 · 같은 출발 · 같은 명령) 를 쓰면 S2-RESULT-PLAN 3 절의 Tango 짝 구간으로 통일한다.
5. **등록 시점.** 1 단계 학습 시작 전에 평가기가 실제로 끝까지 도는 것을 한 번 보인다. 지난번에는 학습이 끝나고 평가기가 `raycaster_cache_not_released` 로 멈췄다 (S2-RESULT-PLAN 1 절). 결과는 체크포인트 평가에서만 나온다.

## 6. Q6 일정과 예산

**답: GPU 시간은 병목이 아니고 코드가 병목이다.** 환산식은 t_ours = t_paper × (논문 GPU 처리량 / 우리 처리량) 인데, 우리가 잰 처리량은 **맹목 Go2 험지 4096 env 23,000 steps/s (5080 1 장)** 하나뿐이다 (`training-benchmarks.md` 0 절). depth 렌더 · TR-Net · 180 × 320 카메라가 붙은 처리량은 **미확인** 이다. 아래 숫자는 전부 추정이고, 첫 10 update 에서 재서 갈아 끼운다.

| 단계 | 논문 예산 | 환산 | 우리 추정 | 미확인 |
|---|---|---|---|---|
| 1 HiPAN 저수준 teacher | 4096 로봇 · 12 h · 4090 (H:632) | 반복 수 미기재 → steps/s 못 구함. GPU 비(4090/5080) 로만: 게임 벤치 1.25~1.4 배 [13], Isaac Lab 실측 없음 | 15~17 h | 비율 |
| 1 student DAgger | 300 로봇 · 2 h (H:634) | 같은 비 | 2.5~3 h | |
| 2 START 식 단일 단계 | 3072 env · 10,000 iter · 16.6 h · A6000 (S:221) | steps/env 미기재. 24 가정 → 737 M env-step / 59,760 s = 12,300 steps/s (depth 포함). 우리 맹목 23,000 에서 depth + TR-Net 으로 50 % 라 가정 → 11,500 | 18 h (30 % 라면 30 h) | depth 처리량 · VRAM |
| 3 고수준 teacher | 1024 로봇 · 18 h (H:535), 저수준 내장 50 Hz · 3D 14×11×11 + 2.5D 31×21 지도 (H:486) | GPU 비 | 22~25 h | 지도 표본화 비용 |
| 3 고수준 student | 128 로봇 · 6 h · 180 × 320 depth (H:526~535) | GPU 비 | 7.5~8.5 h | TiledCamera 128 대 |
| (조건부) 2 를 내장한 고수준 재증류 | student 6 h | | 8 h | |
| 합 | | | **66~84 GPU·h** (재증류 포함 74~92) | |

32 일 × 2 장 = 1,536 GPU·h 이므로 한 번 돌리는 데는 5~6 % 다. 디버그로 단계마다 2~3 번 돌려도 20 % 다. **그래서 일정 판단은 코드 준비일로 한다.**

| 단계 | 코드 준비 (추정) | 왜 그 날인가 | 11/7 | 11/25 |
|---|---|---|---|---|
| 1 | 10/22 | Isaac Lab Go2 velocity env + 명령 2 칸(h · roll) + Table III 보상 + Table I DR + 증류 러너. **teacher-student 증류 부품은 Isaac Lab 2.3.2 에 이미 있다** (`anymal_d/agents/rsl_rl_distillation_cfg.py`: RslRlDistillationRunnerCfg · StudentTeacherCfg) | **된다** (10/24 학습 → 10/27 첫 결과, 재실행 1 회 포함) | 된다 |
| 3 (1 의 저수준 내장) | 11/3 | WFC 타일 + 벽 · 탁자 · 상자 환경, A* over GVD 부목표 (H:535), 3D · 2.5D 특권 지도, PGCL 레벨 (H:368), 상태 방문 내적 보상 (H:339), 180 × 320 depth student + GRU. 가장 큰 재구현 | 첫 결과 아님 | **11/12 teacher · 11/14 student, 재실행 1 회면 11/18**. 1 → 2 → 3 순서면 2 의 디버그가 앞을 막아 11/25 를 넘길 위험이 크다 |
| 2 | 10/30 | TR-Net(CNN · GRU · MLP · U-Net) + I-E 추정기(VAE · transformer) + AdaSmpl + 4 지형 × 10 레벨 + p_advance 커리큘럼 + 60 × 60 Warp 카메라 + 발 가장자리 보상. 코드 없음 | 11/7 에 **첫 run 결과** 는 가능 | 두 번째 GPU 에서 11/1~11/20 사이 2~3 run. 관문 통과 시 재증류 11/22 |

결론: 1 → 3 → 2 로 두면 11/25 에 「HiPAN 논문대로 한 벌 + 2 단계 결과」 가 남고, 1 → 2 → 3 으로 두면 2 가 막힐 때 3 이 없다. 둘의 GPU 비용은 같다.

## 7. Q7 동결 목록

| # | 항목 | 동결값 (권고) | 근거 · 표시 |
|---|---|---|---|
| F1 | 저수준 명령 5 칸 범위 | vx [−1.5, 1.5] · vy [−1.0, 1.0] · ωz [−1.5, 1.5] · h [0.1, 0.4] m · roll [−1.0, 1.0] rad | H:635 · 원칙 ① |
| F2 | h 추종 가능 구간 기록 | 정지 격자 h ∈ {0.10, …, 0.40} × roll ∈ {−1, −0.5, 0, 0.5, 1} 추종 오차표. 0.38 이상은 「기하 한계」 로 표기 | 2 절 무릎 reach 0.389 m · SPEC-hipan L1 검증 |
| F3 | 명령 커리큘럼 | grid-adaptive. 격자 vx × vy × ωz 3 차원, 칸 0.5 m/s · 0.5 m/s · 0.5 rad/s, 시작 [−1, 1]³ 교집합 범위, 확장 조건 「두 추종 보상 ≥ γ」, γ 값 기록. 자세 명령 추종 뒤 평면 속도 확장 | H:164~165 · Margolis [2] · vy 처리는 논문 미기재 → **우리 결정 표시** |
| F4 | 지형 승급 규칙 | Isaac Lab `terrain_levels_vel` (평면 변위 > size/2 승급 · < |cmd|·T·0.5 강등), 타일 8 × 8 m 정사각, 레벨 10 | H 논문 미기재 → 우리 결정. 1 절 |
| F5 | 승급 방향 편향 감시 | 승급 이벤트를 명령 방향 5 칸별로 로그, 레벨 ≥ 7 표본의 방향 분포가 명령 분포와 10 %p 넘게 벌어지면 경고 | 1 절 (b) |
| F6 | 저수준 지형 | stairs · discrete holes · slopes · flat (H:632~633) + 무대 계단 실측 치수. 치수 미기재 → Isaac Lab 기본 + 실측 | 2 절 |
| F7 | teacher 관측 | op (q · q̇ · pF · I · θxy · ω · a_{t−1}) + c + xm + xd(지형 높이 지도 · DR 변수) → zd ∈ R32 | H:198~267 |
| F8 | student 관측 | op50 + c, 추정기 op50 → ẑd · op10 → x̂m. **외부 지각 없음** | H:268~272 |
| F9 | 저수준 보상 | HiPAN Table III 14 항 · 가중치 그대로. 속도 추종은 정확 추종형 | H:587~627 · R4 |
| F10 | 증류 | DAgger, teacher 행동 + zd + xm 회귀 | H:168~189 |
| F11 | 저수준 예산 | 4096 로봇 · 논문 시간을 반복 수로 환산 불가 → **벽시계 12 h 와 2 h 를 n % 로 기록** | H:632~634 · 원칙 ③ |
| F12 | DR | Table I 학습 분포. 적재는 절대값 U(0, 3) / 비율 U(0, 3.75) 중 하나를 **고르고 기록** | H:Table I · 원칙 ② |
| F13 | actuator | Isaac Lab Go2 DCMotor 23.5 유지하되 **관절별 velocity_limit 을 URDF 값(hip · thigh 30.1 · calf 15.70)** 으로 | `unitree.py` 170~176 · `go2.urdf` 84 · 122 · 160 |
| F14 | 2 단계 이름 | 「START 지각(TR-Net · I-E · AdaSmpl · 발 가장자리) 을 HiPAN 명령 공간에 올린 우리 방법」. 「HiPAN 저수준 + 눈」 이라 쓰지 않음 | 3 절 R1 |
| F15 | 2 단계 학습 틀 | 단일 단계 비대칭 PPO(START) + TR-Net 손실(MSE 거친 지도 · L1 정제 지도, S:160~165) + AdaSmpl. DAgger 없음 | S:50~52 · R1 |
| F16 | 지도 틀 | 중력 정렬 yaw 틀, 뒤 0.5 ~ 앞 1.1 m × 0.8 m @ 5 cm | S:127 · R2 |
| F17 | 2 단계 명령 분포 | 팀장 결정 ③ 의 결과를 적는다 (전부 열기 / 지형군별) | R6 |
| F18 | 2 단계 지형 | START 4 종 × 10 레벨 + p_advance 선형 스케줄(p_max · T_start · T_end 값 기록) + 1 단계 지형 | S:259~313 |
| F19 | 2 단계 카메라 | D435i 위치 (0.25, 0, 0.12) · pitch 35° · 60 × 60 · 10 Hz · 2 프레임 (SPEC-start 2 절) + **h 명령에 따른 높이 변화 허용** 표기 | R3 |
| F20 | L1 채널 | 1 차(11/7) 에는 넣지 않음. 넣을 때의 입력 정의(높이 · 마스크 · age · 점수, 0.5 s 누적) 와 가림률 실측 로그를 선행 조건으로 | 3 절 · 20d 3 절 |
| F21 | 고수준 환경 | WFC flat · rough · obstructed + 벽 · 탁자 · 상자, 20 × 20 m × 6. **계단 포함 여부 = 팀장 결정 ②** | H:42 · H:535 |
| F22 | PGCL | d = 1 m 시작, 1 m 씩 증가, 「다음 미도달 부목표」, 전부 도달 시 레벨 상승 | H:368 |
| F23 | 고수준 관측 | teacher: 3D 14×11×11 + 2.5D 31×21 @ 0.1 m · ōp · xm · p_gs. student: depth 180 × 320 · ōp · x̂m · p_g | H:486~491 · 526~531 |
| F24 | 고수준 예산 | 1024 로봇 18 h · 128 로봇 6 h → 벽시계 n % 기록 | H:535 |
| F25 | 평가 등록 | 5 절 1~5 를 파일 하나로, 해시 · 태그 | |
| F26 | 저수준 교체 관문 | 2 단계 저수준이 1 단계 저수준보다 공통 시험지 (5 절 2 의 「안」 칸) 에서 끝까지 생존 ≥ 동일 · START 4 종 기준선 도달 ≥ +10 %p · 고수준 재증류 뒤 SR 하락 ≤ 2 %p. 하나라도 어기면 교체 안 함 | H:876~880 |

## 8. 이전 회차와 달라진 내 결론

- **L1 뒷발 가시성 (20d 1.1 절 · 20c 1 절).** 철회. 축 각도를 미확인으로 두고 30~45° 를 가정했는데 URDF 가 165° (수직 아래에서 앞 15°) 를 준다. 바닥 전체가 위쪽 반구 안이고 bag 재측정으로 뒷발 칸도 0.25 s 에 채워짐을 확인했다. 남는 미확인은 몸통 · 앞다리 가림뿐이다.
- **Nav2 planner 부목표 (20d 3 절).** 유지. 이번 물음 밖.
- 20c 의 「① 은 L1 → TR-Net 근거리 채널 꼴로만」 은 유지하되, 이 문서 F20 대로 1 차에는 빼고 2 단계 결과(옆 · 뒤 명령 칸의 실패) 가 그 필요를 숫자로 보인 뒤 넣는 순서가 맞다.

## 9. 팀장이 정할 것 (셋)

1. **순서.** (다) 의 1 → 2 → 3 대신 **1 → 3 → 2(병렬)**, 저수준 교체는 F26 관문 통과 때만. GPU 비용은 같고 11/25 에 남는 것이 달라진다.
2. **계단 시연의 구동.** 고수준 학습 환경에 계단을 넣는 「우리 추가」 (논문 밖 표시) 인가, 시연은 앱 수동 vx 로 하고 고수준은 평지 항법만 보이는가. 전자는 3 단계 코드 범위가 늘고, 후자는 「앱 목표 → 계단」 장면이 없다.
3. **2 단계 명령 분포.** 희소 발판에서도 5 칸 전부 열고 옆 · 뒤 칸의 실패를 결과로 보고하는가(원칙 ① 그대로, R5 · R6 위험 감수), 아니면 START 가 했듯 희소 지형군에서는 전진 분포를 쓰고 연속 지형에서만 다 여는가(논문 둘 다의 선례 안, 표시 필요).

## 10. 출처

- S: `C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt` (START, RA-L 2025). H: `2604.26504.txt` (HiPAN). A: `2601.08485v3.txt` (AME-2). J: JEPLO 2609.15770v1 txt (세션 임시 폴더 사본, 10/18 내려받음).
- Isaac Lab 2.3.2: `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/mdp/curriculums.py` 27~58 · `velocity_env_cfg.py` 96~103 · `config/go2/rough_env_cfg.py` 24~79 · `config/anymal_d/agents/rsl_rl_distillation_cfg.py` · `C:/isaac/IsaacLab/source/isaaclab_assets/isaaclab_assets/robots/unitree.py` 32~42 · 140~176 · `C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/config/rough.py` 22~33.
- Go2 URDF: `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf` 6 · 84 · 122 · 160 · 748~749 (공식 `unitree_ros` go2_description.urdf 와 같은 값, [5]).
- L1: `C:/Users/AI-WS01/s2_lab/_external/l1_go2_floor.py` (lead) 재실행 + 독립 검사 `…/scratchpad/l1check/check_l1.py` (이 세션), bag `C:/Users/AI-WS01/s2_lab/_external/l1_data/unilidar-2023-09-22-12-42-04.bag`.
- 저장소: `docs/research/training-benchmarks.md` (23,000 steps/s) · `docs/research/20260928-v2-mvp-report.md` 435 · 485~489 · 557~583 · 640 · 886 · `docs/research/20260911-eval-protocol-v2.md` · `docs/research/20260908-success-criteria-anatomy.md` · `inbox/jay/20261012-arch-discussion/S2-RESULT-PLAN.md` · `inbox/jay/20261018-next-arch/DECISIONS-step2-lead.md` A4 · A6 · `inbox/jay/20261013-go2-app-study/REPORT-astra-10.md` 65~67 (128 × 128 × 30 bit 복셀, BRIEF 의 「128×128×Z」 와 일치).
- [1] legged_gym `legged_robot.py` `_update_terrain_curriculum`: https://raw.githubusercontent.com/leggedrobotics/legged_gym/master/legged_gym/envs/base/legged_robot.py
- [2] Margolis et al., Rapid Locomotion via RL, §III-D2 Eq. 11: https://ar5iv.arxiv.org/html/2205.02824 (격자 0.5 m · 0.5 rad, 시작 [−1, 1], 임계 γ 값 미기재, 옆 속도는 격자 밖 균등 분포)
- [3] Go1 URDF: https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/go1_description/urdf/go1.urdf (trunk 5.204 · thigh/calf 0.213 · hip x 0.1881 · effort 23.7/23.7/35.55 · velocity 30.1/30.1/20.06 · calf [−2.818, −0.888] · hip ±0.863)
- [4] Go1 사양 12 kg · 0.645 × 0.28 × 0.4 m: https://www.generationrobots.com/media/unitree/Go1%20Datasheet_EN%20v3.0.pdf
- [5] Go2 사양 약 15 kg · 최대 관절 토크 약 45 N·m: https://unitree.com/go2 · https://w-technika.cz/out/media/Go2%20Introductionv1.2-English%202023.7.19.pdf · Go2 URDF https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/go2_description/urdf/go2_description.urdf
- [6] JEPLO 코드: https://github.com/ASIG-X/JEPLO (J:28)
- [7] Extreme Parkour 코드: https://github.com/chengxuxin/extreme-parkour
- [8] 같은 저장소 `legged_robot_config.py` (lin_vel_x [0, 1.5] · lin_vel_y [0, 0] · ang_vel_yaw [0, 0] · heading [0, 0] · num_envs 6144): https://raw.githubusercontent.com/chengxuxin/extreme-parkour/main/legged_gym/legged_gym/envs/base/legged_robot_config.py
- [9] ABS: https://github.com/lecar-lab/abs (CC BY-NC 4.0 · Go1 EDU + ZED mini · 체크포인트 없음)
- [10] WMP: https://gitee.com/ByteDance/WMP (Apache-2.0 · Isaac Gym Preview 3 · 「Training takes about 23G GPU memory」) · 논문 https://arxiv.org/abs/2409.16784
- [11] Open-DiffLoco: https://arxiv.org/html/2608.02069v1 · https://github.com/MartinOpat/open-diffloco (Go2 EDU + AGX Orin · 5080 1 장 20~60 분 · 맹목)
- [12] legged-loco: https://github.com/yang-zj1026/legged-loco (MIT · Isaac Lab 1.1.0 · Go2 · H1)
- [13] RTX 5080 대 4090: Isaac Lab 실측 비교 없음 (https://github.com/isaac-sim/IsaacLab/issues/2761 · https://arxiv.org/pdf/2511.04831 는 L40 · RTX Pro 6000 · 5090 만). 게임 벤치 5080 ≈ 4090 의 70~80 %: https://techtactician.com/?p=46167 (추정 근거로만)
