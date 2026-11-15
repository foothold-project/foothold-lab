> 분류: 조사 (사실 수집 · 설계 판단 없음)
> 작성: 오흥재 (lead 하위 조사 · Claude 작성) · 2026-10-13 01:45
> 근거: 팀장 GitHub star 249개 (2026-10-13 01:15 `gh api user/starred` 조회) · 저장소 README 110개 (링크는 전부 추출, 본문은 보행 관련만 읽음) · 프로젝트 · 문서 페이지 42개 · arXiv PDF 19편 (판은 표마다) · 코드 파일 9개 (REAL · Extreme Parkour · Robot Parkour · InstinctLab 설정, `gh api` 파일 단위 조회, clone 없음)
> 요지: star 에서 출발한 저장소 그래프는 hop 4 에서 지형을 보는 parkour 계열(Robot Parkour Learning · Hiking in the Wild 등)에 닿았고, 덮은 문서가 가리킨 Gurukul 을 보조 출발점으로 삼으면 REAL · Extreme Parkour · AME(v1) 까지 닿는다. 새로 기록한 보행 방법 23개 중 「배포 관절 정책이 지형을 본다 · gap 숫자를 낸다 · 코드가 있다」 셋을 다 갖춘 것은 넷(REAL · Extreme Parkour · Robot Parkour Learning · Hiking in the Wild)이고, Go2 와 Isaac Lab 을 함께 쓰는 것은 그중 없다.
> 상태: 초안 · 팀장 · lead · ASTRA 논의 전

# star 저장소 그래프 조사: 별에서 README · 프로젝트 페이지를 따라 hop 별로 찾은 보행 방법

이 문서는 사실만 모은다. 어느 방법을 쓰자는 판단과 권고는 적지 않는다(lead 몫).
이미 덮은 것은 되풀이하지 않고 가리키기만 한다.

- 논문 여섯 편(AME-2 · MARG · START · JEPLO · MoE-CTS · HiPAN): [PAPERS-architecture.md](PAPERS-architecture.md)
- 저장소 아홉 개(ame2_minimal · go2_rl_gym · go2_rl_robotlab · RoboGauge · JEPLO · legged_gym · unitree_rl_gym · unitree_rl_lab · isaac-go2-ros2)와 MARG · START 코드 공개 여부: [SURVEY-star-code.md](../20261008-546-design/SURVEY-star-code.md)
- 논문 인용 그래프는 다른 하위 조사가 맡는다. 여기서는 논문 링크를 **방법을 알아보는 데만** 썼고 인용 목록은 따라가지 않았다.

## 읽는 법

- **근거 등급** 셋.
  - `확인됨 (출처)`: 이 조사가 직접 연 1차 자료. 논문은 `PDF 절 · 표 · 그림`, 코드는 `파일:행` 또는 `gh api` 조회.
  - `README 주장`: README · 프로젝트 페이지 · 문서 사이트에 저자가 적은 말. 어느 쪽인지 괄호에 적는다.
  - `미확인`: 찾지 못했거나 읽지 않았다. 무엇을 해 봤는지 같이 적는다.
- 그림에 **인쇄된 숫자**만 옮긴다. 선 · 막대 높이를 눈으로 읽어야 하는 값은 `미확인` 으로 둔다(PAPERS 와 같은 규칙).
- 「지형을 본다」: **관절 목표를 내는 배포 정책**의 입력에 외부 센서(depth · LiDAR · RGB · 지도)에서 온 지형 정보가 들어가는가. 학습 중 teacher · critic 만 보는 것은 「보지 않는다」로 센다.
- **관련 등급** (그래프를 언제 멈출지 정하려고 이 조사가 정한 구분):
  - 1등급: 배포 관절 정책이 지형을 보고, gap · 디딤돌 · 희소 발판을 학습하거나 그 숫자를 낸다.
  - 2등급: 외부 센서로 지형 · 주변을 보지만 (a) 관절 정책이 아닌 상위 층만 보거나 (b) gap · 디딤돌을 다루지 않는다.
  - 3등급: 지형을 보지 않는(blind) 거친 지형 보행 정책.
  - 범위 밖: 휴머노이드 motion tracking · 텔레오퍼레이션 · 조작 · 드론 · SDK · 하드웨어 · 생성 모델.
- **hop**: star 목록이 hop 0. 한 노드는 한 프로젝트다. 저장소 README 와, 같은 프로젝트의 프로젝트 페이지 · 문서 페이지 · 코드 저장소는 한 노드로 묶는다(예: Risky_gym 과 MARG 페이지, RPL 페이지와 그 코드 저장소). 노드에 걸린 **다른 프로젝트**의 저장소 · 페이지 · 논문이 다음 hop 이다. 한 노드가 여러 길로 닿으면 가장 작은 hop 을 적었다. 「찾은 hop」은 그 방법이 처음 나온 hop.
- **멈춤 규칙**: 1·2등급 새 방법이 두 hop 연속 나오지 않으면 멈췄다. 범위 밖 노드는 기록만 하고 펼치지 않았다(가지치기). 가지친 노드는 hop 기록과 「못 본 것」에 적었다.
- **보조 출발점**: 이미 덮은 문서가 가리켰지만 star 그래프에서는 닿지 않는 노드(Gurukul · HiPAN 페이지). hop 을 따로 세고 `hop′` 로 적었다.
- 아무것도 설치 · 실행 · 학습하지 않았다. GPU 를 쓰지 않았다. clone 하지 않았다.

---

## 요약 (사실 열 줄)

1. star 249개 중 보행 · 시뮬 · 지각 관련으로 **유지 20**, 열어 보고 가지친 것 6, 뺀 것 223 (부록). 유지 20 중 10개는 이미 덮었다(SURVEY 9개 + Risky_gym).
2. 저장소 그래프에서 새로 기록한 보행 방법은 **23개**: 1등급 7 · 2등급 5 · 3등급 11 (덮은 6편 · 9저장소 제외). 범위 밖으로 이름만 적은 것 36개(2.5절).
3. **「배포 관절 정책이 지형을 본다 + gap · 디딤돌 숫자 + 코드」를 다 갖춘 것은 넷**: REAL(Go2 · Isaac Gym · MIT) · Extreme Parkour(A1 · Isaac Gym · CC BY-NC 4.0) · Robot Parkour Learning(논문 A1 · Go1, 저장소에 Go2 예시 · Isaac Gym · MIT) · Hiking in the Wild(G1 휴머노이드 · Isaac Lab · CC BY-NC 4.0). 넷 다 저장소에 학습된 체크포인트가 없다(파일 트리 확인).
4. 넷 중 Go2 실기 결과가 있는 것은 **REAL 하나**. Go2 학습 설정이 있는 것은 REAL · Robot Parkour Learning 저장소. Isaac Lab 으로 학습하는 것은 **Hiking 하나**(휴머노이드). **Go2 + Isaac Lab + 지형을 보는 희소 발판 과제**를 한데 둔 것은 Gurukul 의 START · REAL(teacher 만) · AME 적응 판뿐이고, 저자가 「수렴 · 논문 재현 증거 없음」이라 적었다 `README 주장 (문서 사이트)`.
5. **명령 인터페이스**: 넷 중 임의 속도 명령(정지 · 저속 · 횡 · 후진)을 학습한 것은 없다. REAL · Extreme Parkour 는 waypoint 방향 + 전진 속도(코드 `lin_vel_x = [0, 1.5]`, 횡 0), Robot Parkour Learning 논문은 skill 별 고정 전진 속도(증류 정책 입력에 명령 없음), Hiking 은 위치 기반 속도 명령(`vy = 0`, 평지 일부 env 만 제자리 회전). 지형을 보는 방법 중 **정지 명령**을 학습 분포에 명시한 것은 Egocentric Vision(평지에서만) 하나다.
6. gap 숫자는 서로 비교하기 어렵다. REAL Table I 의 Gaps SR 0.28 은 같은 표의 SoloParkour 0.36 보다 낮고, SR 은 저자 자체 정의다. Extreme Parkour 원문은 SR 대신 MXD(Gap 0.96)를 낸다.
7. REAL 의 지형 생성 코드는 Extreme Parkour 와 거의 같다(`terrain.py` diff 3줄). 둘 다 gap 폭 `0.1 + 0.7 × difficulty` m(0.1 ~ 0.8 m) `확인됨 (코드)`. InstinctLab parkour 설정은 square gap `0.1 ~ 0.7` m `확인됨 (코드)`.
8. star 그래프에서 1·2등급 방법은 **hop 4 에서 처음이자 마지막으로** 나왔다(Robot Parkour Learning · Humanoid Parkour Learning · Hiking · Deep Whole-body Parkour · DIC). hop 5 · 6 은 3등급만(RMA · LCP · HugWBC) → 멈춤. 보조 출발점(Gurukul) 그래프는 hop′4(CMS · VP-Nav)가 마지막, hop′5 · 6 은 없음.
9. 덮은 MARG 에 붙는 새 사실: 프로젝트 페이지 그림 `succ_tab.png` 에 논문에 없는 **Go2 실기 표**가 있다(지형별 5회, 실외 single gap 4/5 · 실내 single gap 5/5 등). gap 폭은 표에 없다.
10. star 목록의 보행 관련 저장소는 대부분 SDK · 시뮬레이터 · 드라이버라서 README 링크가 기반 도구로만 이어진다. star 그래프에서 1등급 방법에 닿는 길은 `ame2_minimal · legged_gym → rsl_rl → mjlab (문서의 Research 페이지) → InstinctMJ (Project Instinct 사이트) → RPL · Hiking · Humanoid Parkour` 하나뿐이었다.

---

## 1. 방법 요약표 (한 줄에 하나)

「지형」은 배포 관절 정책이 지형을 보는가. 「Go2 · IL」은 Go2 판 유무 · Isaac Lab 사용 여부. 근거는 2절 각 표에 있다.

| # | 방법 | 등급 | arXiv (본 판) | 로봇 | 지형 (센서) | 명령 | 시뮬 | 학습 gap · 디딤돌 | gap · 디딤돌 숫자 | 코드 (라이선스 · ckpt) | Go2 · IL | 찾은 hop |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | REAL | 1 | 2603.17653 v1 | Go2 | 예 (D435i depth) | waypoint 방향 + 전진 속도 | Isaac Gym | gap 0.1 ~ 0.8 m (코드) | 시뮬 Gaps SR 0.28 (Table I) | 있음 (MIT · 없음) | Go2 실기 · IL 아님 | hop′1 |
| A2 | Extreme Parkour | 1 | 2309.14341 v1 | A1 | 예 (D435 depth, heading 도 예측) | waypoint 방향 + 속력 | Isaac Gym | gap 0.1 ~ 0.8 m (코드) | 시뮬 Gap MXD 0.96 (Table 2) · 실기 0.8 m | 있음 (CC BY-NC 4.0 · 없음) | 없음 · 아님 | hop′2 |
| A3 | Robot Parkour Learning | 1 | 2309.05665 v2 | A1 · Go1 (저장소 Go2) | 예 (D435 depth) | 논문: skill 별 고정 속도 · 저장소 Go2: goal-based | Isaac Gym | leap 0.2 ~ 0.8 m (Table 1) | 시뮬 Leap 80 % · 실기 0.6 m 80 % | 있음 (MIT · 없음) | Go2 설정 · 배포 예시 · 아님 | hop 4 |
| A4 | Egocentric Vision (Agarwal 외) | 1 | 2211.07638 v1 | A1 | 예 (D435 depth) | 속도 + heading, 평지 정지 · 회전 포함 | Isaac Gym | gap · 디딤돌 지형 (치수 없음) | 실기 gap 26 cm 100 % · 디딤돌 94 % | 링크 없음 | 없음 · 아님 | hop′3 |
| A5 | AME (v1) | 1 | 2506.09588 v1 | ANYmal-D · GR-1 | 예 (elevation map) | 속도 (전방향) | 미확인 | gap · grid stones (치수 없음) | 그림만 (Fig. 6) | 공식 못 찾음 · 재현 둘 | Gurukul Go2 적응 · 재현은 IL | hop′1 |
| A6 | Hiking in the Wild | 1 | 2601.07718 v1 | G1 (휴머노이드) | 예 (D435i depth) | 위치 기반 속도 (vy 0) | Isaac Lab | square gap 0.1 ~ 0.7 m (코드) | 시뮬 Deep Gap 100.0 % · 실기 50 cm | 있음 (CC BY-NC 4.0 · 없음) | 없음 · IL | hop 4 |
| A7 | Humanoid Parkour Learning | 1 | 2406.10759 v2 | H1 (휴머노이드) | 예 (D435i depth) | 평면 x · y · yaw + 트랙 자동 yaw | Isaac Gym | leap 0.2 ~ 1.2 m | 시뮬 Leap 80 % (Table 2) | 링크 없음 | 없음 · 아님 | hop 4 |
| B1 | DIC (Learning to Jump from Pixels) | 2 | 2110.15344 v1 | Mini Cheetah | 상위 층만 (D435 depth), 관절은 MPC + WBIC | 상위 정책이 몸 속도 · gait 출력 | PyBullet | gap (치수는 그림) | 시뮬 그림만 | Google Sites 링크 (미확인) | 없음 · 아님 | hop 4 |
| B2 | Omni-Perception | 2 | 2505.19214 v2 | Go2 (그림 2) | 예 (LiDAR 원시 점군), 충돌 회피용 | 속도 명령 + 회피 | Isaac Gym | 없음 | 없음 (장애물 회피 30회 표) | 일부 (LiDAR 시뮬만, 학습 코드 진행 중) | Go2 · 아님 | hop′1 |
| B3 | CMS (Cross-Modal Supervision) | 2 | 2211.03785 v1 | A1 | 예 (단안 RGB) | 미확인 | RaiSim | 미확인 | 없음 | 있음 (학습 GPL-3.0 · 배포 라이선스 없음) | 없음 · 아님 | hop′4 |
| B4 | VP-Nav | 2 | 2112.02094 v2 | A1 | 아니오 (depth 는 계획 층) | 계획 층이 속도 명령 생성 | RaiSim | 없음 | 없음 | 있음 (Apache-2.0) | 없음 · 아님 | hop′4 |
| B5 | Deep Whole-body Parkour | 2 | 2601.07701 v1 | G1 (휴머노이드) | 예 (D435i depth) | 참조 동작 (motion tracking) | Isaac Lab | 없음 | 없음 | InstinctLab shadowing (CC BY-NC 4.0) | 없음 · IL | hop 4 |
| C1 | CTS | 3 | 2405.10830 v2 | A1 · Aliengo · P1 | 아니오 | 속도 [-1, 1] m/s | Isaac Gym | 없음 | 없음 | 공식 링크 못 봄 (go2_rl_gym 에 재구현 ckpt) | go2_rl_gym 판 · 아님 | hop 1 |
| C2 | DreamWaQ | 3 | 2301.10602 v2 | A1 | 아니오 | 속도 | Isaac Gym | 없음 | 없음 | 링크 못 봄 (go2_rl_gym 재구현 ckpt) | go2_rl_gym 판 · 아님 | hop 1 |
| C3 | HIMLoco | 3 | 2312.11460 v3 | Aliengo · A1 · Go1 | 아니오 | 속도 (평가 표에 [-1, 1] · [-2, 2] m/s) | Isaac Gym | 없음 | 없음 | 있음 (CC BY-NC-SA 4.0 · 없음) | 없음 · 아님 | hop 1 |
| C4 | H-Infinity Locomotion | 3 | 2404.14405 v2 | Aliengo · A1 | 아니오 | 속도 | Isaac Gym | 없음 | 없음 | 학습 코드 미공개 (README TODO) | 없음 · 아님 | hop 2 |
| C5 | RMA | 3 | 2107.04034 v1 | A1 | 아니오 | 미확인 | RaiSim | 없음 | 없음 | antonilo/rl_locomotion (GPL-3.0) | 없음 · 아님 | hop 5 · hop′3 |
| C6 | Rapid Locomotion | 3 | 2205.02824 v1 | Mini Cheetah | 아니오 | 속도 (최대 6.0 m/s 명령 시험) | Isaac Gym | 없음 | 없음 | 있음 (NOASSERTION) | 없음 · 아님 | hop 4 |
| C7 | Walk These Ways | 3 | 2212.03238 v1 | Go1 | 아니오 | 속도 3 + gait 파라미터 | Isaac Gym | 없음 (평지 gap 흉내만) | 없음 | 있음 (MIT · 있음) | 없음 · 아님 | hop 3 |
| C8 | Energy gaits | 3 | 2111.01674 v1 | A1 | 아니오 | 미확인 | 미확인 | 미확인 | 없음 | 링크 못 봄 | 없음 · 아님 | hop′4 |
| C9 | Humanoid-Gym | 3 | 2404.05695 v2 | 휴머노이드 | 아니오 | 미확인 | 미확인 | 미확인 | 없음 | 있음 (라이선스 표기 없음) | 없음 · 미확인 | hop 4 |
| C10 | LCP (Lipschitz-Constrained Policies) | 3 | 2410.11825 v3 | 휴머노이드 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 | 있음 (NOASSERTION) | 없음 · 미확인 | hop 6 |
| C11 | HugWBC | 3 | 2502.03206 v3 | 휴머노이드 | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 | 있음 (라이선스 표기 없음) | 없음 · 미확인 | hop 6 |

C10 · C11 은 README 머리만 읽었다(hop 6, 멈춤 직전). 칸 대부분이 `미확인` 인 까닭이다.

---

## 2. 방법별 세부

### 2.1 1등급: 배포 관절 정책이 지형을 보고 gap · 디딤돌을 다룬다

#### A1. REAL (Robust Extreme Agility Learning)

| 항목 | 내용 | 근거 |
|---|---|---|
| 논문 | arXiv 2603.17653 v1 (2026-03-18). v1 본문에 게재지 없음 | 확인됨 (arXiv API · PDF 1쪽) |
| 게재 | IROS 2026 채택 | README 주장 (README 머리) |
| 로봇 | Unitree Go2 (시뮬 · 실기) | 확인됨 (PDF IV-A · Fig. 3) |
| 배포 센서 | 앞쪽 Intel RealSense D435i depth + 관절 · IMU. 추론은 탑재 NVIDIA Jetson, 13.1 ms | 확인됨 (Abstract · IV-A) |
| 지형을 보나 | 예. student 가 depth → FiLM-CNN(proprio 로 변조) → Mamba → 행동 | 확인됨 (III-A · 식 2 · 3) |
| 지형 표현 | teacher: terrain scan dots(코드 `n_scan = 132`)를 key · value 로, proprio 를 query 로 cross-modal attention. student: depth `87 × 58`(코드 `resized`), depth 이력 2 | 확인됨 (III-A · 코드 `legged_robot_config.py:43, 48, 95-96`) |
| 상태 추정 | 1D ResNet(proprio 10 frame) 이 속도 · 불확실도 예측 → EKF 로 IMU 적분과 융합 | 확인됨 (III-B · 식 4~10) |
| 학습 단계 | 2단계. (1) privileged teacher PPO (scan dots + 속도 · 마찰 · 모터) → (2) student 증류: `L = λ L_RL + (1 - λ) L_BC`, λ 는 teacher-student 행동 거리로 정하는 gating | 확인됨 (III · 식 11 · 12) |
| 명령 | 「path waypoint 로 안내」. 코드 기본: `lin_vel_x = [0, 1.5]` · `lin_vel_y = [0, 0]` · `heading_command = True` · `num_goals = 8` · 재추출 6 s (Extreme Parkour 코드와 같은 값). student 가 heading 을 스스로 예측하는지는 본문 · README 에서 못 찾음 | 확인됨 (III-A · 코드 `legged_robot_config.py:223-251`) · 미확인 (heading 예측) |
| 시뮬 · 비용 | Isaac Gym. 정책 50 Hz · PD 1 kHz. RTX 4080 1장 약 30 시간 | 확인됨 (IV · IV-A) |
| 학습 지형 | 「Extreme Parkour [4] 의 지형 설정과 난이도 그대로」. 코드: parkour · hurdle · flat · step · gap 다섯 종이 각 0.2. gap 폭 `0.1 + 0.7 × difficulty` m (0.1 ~ 0.8 m), 깊이 0.2 ~ 1 m | 확인됨 (IV-B · 코드 `terrain.py:310-318` · `legged_robot_config.py:196-216`) |
| 보고 숫자 | Table I (시뮬, 시행 수 미기재): **Gaps SR 0.28 · MXD 0.39**. 같은 표 Extreme Parkour 0.10 · RPL 0.03 · SoloParkour 0.36. 전체 SR 0.78. Table IV (장애물 1 m 앞부터 시야 가림): 전체 SR 0.55. SR 은 「custom definition」 | 확인됨 (Table I · IV · IV-A) |
| 실기 숫자 | 없음 (그림 · 영상) | 확인됨 (IV) |
| 코드 | [JIAlonglong/REAL](https://github.com/JIAlonglong/REAL) @c439814a · MIT (LICENSE 파일. GitHub API 는 NOASSERTION) · push 2026-07-07 · Isaac Gym Preview 4 · Python 3.8 · torch 1.10.0+cu113 · **체크포인트 없음** (트리 89개 파일 중 `.pt` 없음) · 배포는 README 의 C++ 예시 조각뿐 | 확인됨 (`gh api` 트리 · LICENSE) · README 주장 (요구 판) |
| Go2 | 예 (`go2_config.py`, 실기) | 확인됨 |
| 재구현에 빠진 것 | 체크포인트. 실기 배포 코드. Isaac Lab 판. README 표의 `--num_envs` 기본 2048 과 코드 `env.num_envs = 4096` 중 어느 쪽이 쓰이는지. SR 정의 | 확인됨 (트리 · 코드) · 미확인 (정의) |

#### A2. Extreme Parkour with Legged Robots

| 항목 | 내용 | 근거 |
|---|---|---|
| 논문 | arXiv 2309.14341 v1 (2023-09-25). v1 에 게재지 없음. AME(v1) 참고문헌 [10] 은 ICRA 2024 로 적는다 | 확인됨 (arXiv API) · 확인됨 (2506.09588v1 참고문헌, 표기만) |
| 로봇 | Unitree A1 | 확인됨 (4.1) |
| 배포 센서 | 머리 안 RealSense D435, 10 ± 2 Hz, `58 × 87` 로 줄임, depth 지연 0.08 s 고정. Jetson NX | 확인됨 (4.1) |
| 지형을 보나 | 예. depth → convnet-GRU 가 scandots 자리를 대신하고, heading 도 depth 로 예측 | 확인됨 (3.3 · Fig. 2) |
| 지형 표현 | Phase 1 scandots + ROA(환경 추정). Phase 2 depth | 확인됨 (3.2 · 3.3) |
| 학습 단계 | 2단계. Phase 1 RL (scandots, waypoint 로 준 oracle heading) → Phase 2 DAgger 증류 (depth, heading 예측, teacher · student heading 섞기 MTS) | 확인됨 (3.2 · 3.3) |
| 명령 | 속력 `v_cmd` + waypoint 방향 `d̂` + walking flag `W`. 보상은 `min(<v, d̂>, v_cmd)`. 코드 `lin_vel_x = [0, 1.5]` | 확인됨 (식 2 · 3.2 · 코드 `legged_robot_config.py:206-212`) |
| 시뮬 · 비용 | Isaac Gym (README: Preview 3 으로 학습, Preview 4 도 문제 없음). 3090 1장 20 시간 미만 | 확인됨 (4.1) · README 주장 |
| 학습 지형 | tilted ramp · gap · hurdle · high step. 논문 본문에 gap 치수 없음. 코드 gap 폭 `0.1 + 0.7 × difficulty` m | 확인됨 (3.2 · 코드 `terrain.py:310-311`) · 미확인 (논문 치수) |
| 보고 숫자 | Table 2 (시뮬, 256 로봇 · 30 s): **Gap MXD 0.96 ± 0.14 · MEV 0.02 ± 0.14** (NoClear 0.96 · Noisy 0.87). 실기: 0.8 m gap 횡단 (Fig. 5, 몸길이 2배). Fig. 7 실기 gap 0.3 ~ 0.8 m 각 5회는 선 그림이라 값 미확인 | 확인됨 (Table 2 · Fig. 5, PDF 9쪽 그림으로 행 대응 확인) · 미확인 (Fig. 7 값) |
| 코드 | [chengxuxin/extreme-parkour](https://github.com/chengxuxin/extreme-parkour) @d2ffe27b · CC BY-NC 4.0 (LICENSE) · push 2023-11-28 · 체크포인트 없음 (actuator net 만) · 로봇 설정 a1 · go1 · anymal · cassie (go2 없음) | 확인됨 (`gh api` 트리 · LICENSE) |
| Go2 | 없음. 같은 지형 코드를 쓴 REAL 이 Go2 판 | 확인됨 (트리 · diff) |
| 재구현에 빠진 것 | 체크포인트. 논문 쪽 gap 치수 (코드에만). 비상업 라이선스 | 확인됨 |

#### A3. Robot Parkour Learning (RPL)

| 항목 | 내용 | 근거 |
|---|---|---|
| 논문 | arXiv 2309.05665 v2 (2023-09-12) · CoRL 2023 Oral | 확인됨 (arXiv API comment) |
| 로봇 | 논문: Unitree A1 · Go1. 저장소: Go2 학습 설정 · 배포 예시 추가, 「성능 보장 안 함」 | 확인됨 (4 Robot Setup) · README 주장 |
| 배포 센서 | RealSense D435, depth `48 × 64` · 10 Hz, Jetson NX. 정책 50 Hz, PD Kp 50 · Kd 1, 토크 25 Nm 로 자름 | 확인됨 (3.3) |
| 지형을 보나 | 예. depth → 작은 CNN → GRU (proprio · 이전 행동과 함께) | 확인됨 (3.2) |
| 지형 표현 | skill teacher: privileged 시각 정보(장애물까지 거리 · 높이 · 폭 · 종류 one-hot 4). 증류 student: depth. Go2 저장소 teacher 는 `height_measurements (1, 21, 11)` | 확인됨 (3.1 · 코드 `go2_distill_config.py:25-33, 168`) |
| 학습 단계 | skill 다섯(climb · leap · crawl · tilt · run) 각각 RL 2단계 (soft dynamics 로 장애물 관통 허용한 사전학습 → hard dynamics 미세조정) → DAgger 로 하나의 parkour 정책 증류 | 확인됨 (3.1 · 3.2) |
| 명령 | 논문: skill 별 고정 목표 전진 속도 (leap 1.5 · climb 1.2 · run 0.8 m/s, Table 8). 증류 정책 입력은 proprio 29 · 이전 행동 · depth 뿐, 명령 없음. Go2 저장소: obs 에 `commands` 포함, goal-based 명령, `lin_vel_x = [-0.6, 2.0]` | 확인됨 (Table 8 · 3.2 · 코드 `go2_field_config.py:134-150`, `go2_distill_config.py:14-23`) |
| 시뮬 | Isaac Gym (Preview 4, torch 2.4.1 로 시험). 트랙 40개 × 장애물 20개 | 확인됨 (4) · README 주장 (판) |
| 학습 지형 | **leap gap 길이 학습 [0.2, 0.8] m · 시험 [0.3, 0.9] m** (Table 1). gap 폭 0.8 m · 깊이 0.8 m 고정 (부록). Go2 저장소 `leap length = [0.05, 0.8]` · `depth = [0.5, 0.8]` | 확인됨 (Table 1, PDF 4쪽 그림으로 행 대응 확인 · 부록 · 코드 `go2_field_config.py:46-50`) |
| 보고 숫자 | Table 2 (시뮬, 100회 × 시드 3, 시험 범위): **Leap 성공 80 % · 평균 거리 3.05 m** (최대 3.6 m). Blind 0 %. 실기 A1 (Fig. 6 본문): **0.60 m gap 80 %** (각 10회). 야외 0.6 m 돌 사이 gap | 확인됨 (Table 2 · 4 Indoor) |
| 코드 | [ZiwenZhuang/parkour](https://github.com/ZiwenZhuang/parkour) @5e1f4136 · MIT · push 2025-10-26 · 체크포인트 없음 · Go2 배포 스크립트 `onboard_codes/go2/` (ROS2) | 확인됨 (`gh api` 트리) |
| Go2 | Go2 학습 · 증류 설정과 배포 스크립트 있음. Go2 결과 숫자는 없음 | 확인됨 (트리) · README 주장 (성능 보장 안 함) |
| 재구현에 빠진 것 | 체크포인트. 증류에 렌더 가능한 GPU 2장 · 24 GB (A1 안내). Go2 예시는 crawl skill 제외 | README 주장 (`legged_gym/README.md`) |

#### A4. Legged Locomotion in Challenging Terrains using Egocentric Vision

| 항목 | 내용 | 근거 |
|---|---|---|
| 논문 | arXiv 2211.07638 v1 · CoRL 2022 Oral | 확인됨 (arXiv API) |
| 로봇 | Unitree A1 | 확인됨 (부록 C.2) |
| 배포 센서 | 앞쪽 RealSense D435. 계단용 정책은 내장 카메라, 디딤돌 · gap 용 정책은 위에 단 외부 카메라 (정책 둘) | 확인됨 (Real World Comparisons) |
| 지형을 보나 | 예. depth + proprio → GRU (monolithic) 또는 GRU 로 terrain latent 추정 → MLP (RMA 구조) | 확인됨 (2.2) |
| 학습 단계 | 2단계. Phase 1 RL (scandots + privileged) → Phase 2 지도학습 (DAgger, BPTT 24) | 확인됨 (2.1 · 2.2) |
| 명령 | 전진 속도 + 목표 heading, `ω_cmd = 0.5 × (h_cmd - h)`. 지형 위: `vx = 0.35 m/s`, heading [-10°, 10°]. 평지: curve following (`vx` [0.2, 0.75], heading [-60°, 60°]) · 제자리 회전 · **완전 정지** 중 무작위 | 확인됨 (부록 B) |
| 시뮬 · 비용 | Isaac Gym + legged_gym. 3090, phase 1 4096 env 13 h · phase 2 256 env 6 h | 확인됨 (부록 C) |
| 학습 지형 | 20 × 10 격자 100 sub-terrain, Stairs · Slopes · Rough Flat · Gaps · Stepping Stones · Discrete (Fig. 5). 치수 없음 | 확인됨 (부록 C) |
| 보고 숫자 | 시뮬 Table 1 Stepping Stones 평균 이동 RMA 18.83 m · MLith 20.72 m · Blind 1.02 m (행 대응은 본문 「약 20 m」 서술로 맞춤). 실기 Fig. 4: **gap 26 cm 100 %**, **디딤돌 (30 cm 폭 · 15 cm 간격) 94 %** (평균 9.4 개), Blind 둘 다 0 %. 시행 수 미기재 | 확인됨 (Table 1 · Fig. 4) |
| 코드 | 프로젝트 페이지 · 논문에 코드 링크 없음 | 미확인 (페이지 링크 전수 추출, 2026-10-13) |
| Go2 | 없음 | 확인됨 |

#### A5. AME: Attention-Based Map Encoding (AME-2 의 앞 판)

| 항목 | 내용 | 근거 |
|---|---|---|
| 논문 | arXiv 2506.09588 v1 (2025-06-11). comment 「peer review 전 원고, 출판 뒤 크게 바뀔 예정」, 본문 「Last Revision Dec 16, 2024」 | 확인됨 (arXiv API · PDF 1쪽) |
| 로봇 | ANYmal-D · Fourier GR-1, 둘 다 실기 | 확인됨 (본문 · 부록 Deployment) |
| 배포 센서 | ANYmal-D: elevation mapping [31] 을 탑재 Jetson 에서. GR-1: 모션캡처 자세로 미리 만든 지형 메시를 ray-casting | 확인됨 (Deployment) |
| 지형을 보나 | 예 (높이 지도 scan → CNN → MHA → 정책) | 확인됨 (본문) |
| 지형 표현 | 로봇 중심 높이 지도 ANYmal-D 26 × 16 · GR-1 17 × 11. MHA 차원 64 · head 16 | 확인됨 (Training) |
| 학습 단계 | 2단계 (teacher-student 아님): stage 1 기본 지형 · 완전 지각 → stage 2 지형 추가 · 잡음 · 외란 미세조정. ANYmal stage 1 18000 · stage 2 3600 epoch, 4096 로봇, A100 6일 | 확인됨 (Two-stage · Training) |
| 명령 | 선속도 · 각속도 추적 보상, 전방 · 측방 · 회전 명령 (Fig. 5 · 7B). 범위 미확인 | 확인됨 (Table 2 · Fig. 5) · 미확인 (범위) |
| 시뮬 | 본문에서 이름을 못 찾음 | 미확인 |
| 학습 지형 | stage 1: stairs · pits · rough · pallets · gaps · grid stones. stage 2 추가: pentagon stones · rough hills · rings · beams 등. 치수는 「gap 폭은 로봇 길이 이하, 디딤돌은 10 cm 해상도보다 크게」뿐 | 확인됨 (Supplementary Terrains · Terrains and Curriculum) |
| 보고 숫자 | 시뮬 Fig. 6 (성공 · 정체 · 실패율, DTC 대비) 은 그림만. gap 단독 숫자 없음 | 미확인 (그림 값) |
| 코드 | 공식 코드 링크를 그래프에서 못 찾음 (논문 [44] 는 zenodo 데이터). 재현 둘: [SII-FUSC/AME_Locomotion](https://github.com/SII-FUSC/AME_Locomotion) (G1, Isaac Lab, ckpt `ame1.pt` · `ame2.pt`) · Gurukul (Go2 · G1 적응, 수렴 증거 없음). 2.4 표 참조 | 확인됨 (`gh api` 트리) · README 주장 |
| Go2 | Gurukul 적응 판만 | README 주장 (문서 사이트) |

#### A6. Hiking in the Wild (휴머노이드)

| 항목 | 내용 | 근거 |
|---|---|---|
| 논문 | arXiv 2601.07718 v1 (2026-01-12). 프로젝트 사이트 표기 「In Submission」 | 확인됨 (arXiv API) · README 주장 (project-instinct 사이트) |
| 로봇 | Unitree G1 29-DoF | 확인됨 (IV-A) |
| 배포 센서 | 내장 RealSense D435i, 60 Hz, 480 × 270 → 64 × 36 → 36 × 18. Jetson Orin NX · onnxruntime, 정책 50 Hz | 확인됨 (IV-A) |
| 지형을 보나 | 예. depth 이력 8 frame (strided) + proprio → MoE 정책 | 확인됨 (III · IV-A · Table II) |
| 학습 단계 | 단일 단계 end-to-end RL + AMP style 보상. 고속 달리기 · 일부 지형은 post-train | 확인됨 (I · IV-A) |
| 명령 | 위치 기반 속도 명령: flat patch 를 목표로 골라 `vx` · yaw rate 생성, **`vy = 0`**. 평지 일부 env 는 제자리 회전 명령만 | 확인됨 (III-D) |
| 시뮬 | Isaac Sim + Isaac Lab, RTX 4090. depth 는 Warp ray-caster | 확인됨 (IV-A · III-B) |
| 학습 지형 | 논문 본문에 gap 치수 없음. 공개 코드 `parkour_env_cfg.py`: `square_gaps` 비율 0.10, **`gap_distance_range = (0.1, 0.7)` m**, 깊이 (0.4, 0.6) m. 이 설정이 논문 학습 설정과 같은지는 미확인 | 확인됨 (코드 `parkour_env_cfg.py:91-96`) · 미확인 (논문과 동일 여부) |
| 보고 숫자 | 시뮬 Table I (1000 로봇 × 10000 step): **Deep Gap SR 100.0 %** (edge 벌점 없이 99.94 %), landing 0.96. Table II Gap 100.0 %. 실기: **50 cm gap**, 32 cm 단상. Fig. 8 (각 10회) 막대는 인쇄 숫자 없음 | 확인됨 (Table I · II · IV-B, PDF 7 · 9쪽 그림으로 확인) · 미확인 (Fig. 8 값) |
| 코드 | [project-instinct/InstinctLab](https://github.com/project-instinct/InstinctLab) @de6b92f0 · CC BY-NC 4.0 · push 2026-09-20 · Isaac Sim 5.1.0 · Isaac Lab commit `f73c331738` (v2.3.2 뒤) · task `Instinct-Parkour-Target-Amp-G1-v0` · AMASS 참조 동작 필요 · 체크포인트 없음 | 확인됨 (트리 · LICENSE) · README 주장 (판 · task) |
| Go2 | 없음 | 확인됨 |

#### A7. Humanoid Parkour Learning (휴머노이드)

| 항목 | 내용 | 근거 |
|---|---|---|
| 논문 | arXiv 2406.10759 v2 · CoRL 2024 | 확인됨 (arXiv API) |
| 로봇 | Unitree H1 | 확인됨 (4.1) |
| 배포 센서 | 머리의 RealSense D435i, NUC | 확인됨 (본문 · 부록) |
| 지형을 보나 | 예 (depth 증류 student) | 확인됨 (3 · 3.3) |
| 학습 단계 | 평면 보행 정책 → oracle parkour 정책 (scandots, 지형 10종 auto-curriculum) → depth student 증류 (DAgger, multi-process) | 확인됨 (3) |
| 명령 | 평면 보행: `x [-0.8, 2.0]` · `y [-0.8, 0.8]` m/s · yaw [-1, 1] rad/s (Table 1). parkour 트랙: 목표 방향으로 yaw 자동 명령 | 확인됨 (Table 1 · 3) |
| 시뮬 | Isaac Gym | 확인됨 (4.1) |
| 학습 지형 | **leap 길이 학습 [0.2, 1.2] m** · 시험 같음 (부록 표) | 확인됨 (부록) |
| 보고 숫자 | 시뮬 Table 2 (각 10회): **Leap 80 %** (feet air time 보상 판 50 %). 실기 Fig. 5 (각 10회) 그림. 0.8 m gap (Fig. 1) | 확인됨 (Table 2 · Fig. 1) · 미확인 (Fig. 5 값) |
| 코드 | 프로젝트 페이지에 코드 링크 없음 | 미확인 (페이지 링크 전수 추출) |
| Go2 | 없음 | 확인됨 |

### 2.2 2등급: 지형을 보지만 상위 층만이거나 gap 을 다루지 않는다

| 항목 | B1. DIC (Learning to Jump from Pixels) | B2. Omni-Perception | B3. CMS | B4. VP-Nav | B5. Deep Whole-body Parkour |
|---|---|---|---|---|---|
| 논문 | 2110.15344 v1 · CoRL 2021 (comment) | 2505.19214 v2 (2025-08-28) · CoRL 2025 (README 주장) | 2211.03785 v1 · ICRA 2023 (rl_locomotion README bibtex, README 주장) | 2112.02094 v2 · CVPR 2022 (comment) | 2601.07701 v1 · In Submission (사이트) |
| 로봇 | MIT Mini Cheetah | Go2 (그림 2 설명). LiDAR 시뮬 검증은 G1 | A1 | A1 | G1 29-DoF |
| 배포 센서 | 앞쪽 D435 depth | LiDAR 원시 점군 (Mid-360 등) | 단안 RGB + proprio | D435 depth (점유 지도) | D435i depth 50 Hz |
| 관절 정책이 지형을 보나 | 아니오. depth 는 상위 RL 정책만, 관절은 MPC + WBIC | 예 (PD-RiskNet → 정책) | 예 (실기에서 학습한 visual lookahead) | 아니오 (보행 정책은 proprio + 속도 명령) | 예 (CNN depth + 참조 동작) |
| 학습 단계 | 상위: heightmap expert RL → depth student BC | 단일 (높이 정보로 감독) | sim 에서 blind 정책 → 실기에서 비전 모듈 (CMS) | 보행 정책 sim → safety advisor → 계획 | 단일 단계 |
| 명령 | 상위가 몸 속도 · gait 출력 | 속도 명령 + 회피 보상 | 미확인 | 계획 층이 속도 명령 생성 | 참조 동작 (motion tracking) |
| 시뮬 | PyBullet | Isaac Gym (자체 LiDAR 렌더러) | RaiSim | RaiSim | Isaac Lab (자체 ray-caster) |
| gap · 디딤돌 | gap world (폭 무작위). 시뮬 성공률은 그림만 | 없음. 실기 Table 4 (30회): 정적 30/30 · 공중 21/30 · 작은 25/30 · 사람 27/30 | 없음. 계단 19 cm · 연석 20 cm · 경사 35° | 없음 | 없음 (vault · dive · 점프 동작) |
| 코드 | 논문 각주 Google Sites (따라가지 않음) | [aCodeDog/OmniPerception](https://github.com/aCodeDog/OmniPerception) @a1059ae3 · 라이선스 파일 없음 (README 배지 MIT, Gurukul 은 「license grant 없음」) · LidarSensor 「Released[Half]」 · 학습 코드 「In Progress」 · Isaac Sim ≤ 4.5 | [antonilo/vision_locomotion](https://github.com/antonilo/vision_locomotion) (배포 · 비전, 라이선스 없음) + [antonilo/rl_locomotion](https://github.com/antonilo/rl_locomotion) (RaiSim 학습, GPL-3.0) | [MarkFzp/navigation-locomotion](https://github.com/MarkFzp/navigation-locomotion) · Apache-2.0 · push 2022-06-29 | InstinctLab `tasks/shadowing` (CC BY-NC 4.0) |
| Go2 | 없음 | 예 | 없음 (README: Go1 은 손봐야 함) | 없음 | 없음 |
| 근거 | 확인됨 (PDF 1 · 3 · 4절) | 확인됨 (PDF 3 · 4절 · Table 4) · README 주장 (상태) | 확인됨 (PDF Abstract · Fig. 1) · README 주장 | 확인됨 (PDF Abstract · 3절) | 확인됨 (PDF 1 · 3 · 4절) |

### 2.3 3등급: 지형을 보지 않는 방법

모두 배포 관절 정책이 지형을 보지 않는다. gap · 디딤돌을 학습 지형에 두었다는 서술을 본문에서 찾지 못했다(키워드 `gap` · `stepping stone` 로 PDF 전문 검색, CTS 는 「학습 계단에 gap 이 없었다」는 문장만).

| 방법 | 논문 (판 · 게재) | 로봇 | 명령 | 시뮬 | 코드 | 근거 |
|---|---|---|---|---|---|---|
| C1 CTS | 2405.10830 v2 · RA-L (PDF 머리 「accepted August 2024」) | 학습 비교 A1, 실기 A1 · Aliengo · LimX P1 | 선속도 [-1, 1] m/s 로 시작 | Isaac Gym, 8192 agent (teacher 6144 · student 2048) | 공식 링크 그래프에서 못 봄. go2_rl_gym README 가 「CTS vanilla」 ckpt 를 냄 (SURVEY §3) | 확인됨 (PDF) · README 주장 |
| C2 DreamWaQ | 2301.10602 v2 · ICRA 2023 | A1 | 속도 | Isaac Gym (본문 「[12] 의 공개 구현 기반」) | 링크 못 봄. go2_rl_gym README 에 재구현 ckpt | 확인됨 (PDF) · README 주장 |
| C3 HIMLoco | 2312.11460 v3 · ICLR 2024 (README) | Aliengo · A1 · Go1 | 속도 (평가 표에 [-1, 1] · [-2, 2] m/s, 학습 범위 미확인) | Isaac Gym, 4096 env · 1 시간 | [InternRobotics/HIMLoco](https://github.com/InternRobotics/HIMLoco) @ef289aca (OpenRobotLab 에서 옮김) · CC BY-NC-SA 4.0 · Isaac Gym Preview 4 · Python 3.7 · ckpt 없음 | 확인됨 (PDF · 트리 · LICENSE) |
| C4 H-Infinity | 2404.14405 v2 · CoRL 2024 (페이지) | Aliengo · A1 | 속도 | Isaac Gym, 3090 | 같은 저장소 README TODO 「학습 코드 공개」 미체크 | 확인됨 (PDF) · README 주장 |
| C5 RMA | 2107.04034 v1 · RSS 2021 | A1 | 미확인 | RaiSim | [antonilo/rl_locomotion](https://github.com/antonilo/rl_locomotion) (RMA 코드를 바탕으로 한 CMS 학습 코드, GPL-3.0) | 확인됨 (PDF 키워드) · README 주장 |
| C6 Rapid Locomotion | 2205.02824 v1 · RSS 2022 | Mini Cheetah (저장소는 Go1 도) | 속도 명령, 6.0 m/s 명령 시험 (Table IV) | Isaac Gym Preview 3 | [Improbable-AI/rapid-locomotion-rl](https://github.com/Improbable-AI/rapid-locomotion-rl) @f5143ef9 · NOASSERTION · torch 1.10 | 확인됨 (PDF) · README 주장 |
| C7 Walk These Ways | 2212.03238 v1 · CoRL 2022 Oral | Go1 | `[vx, vy, ωz]` + gait 파라미터 (위상 · 주파수 등), 이력 30 step | Isaac Gym | [Improbable-AI/walk-these-ways](https://github.com/Improbable-AI/walk-these-ways) @0e7236bd · MIT · **사전학습 ckpt 있음** · Go1 배포 | 확인됨 (PDF · 트리 · LICENSE) |
| C8 Energy gaits | 2111.01674 v1 · CoRL 2021 | A1 (페이지) | 미확인 | 미확인 | 링크 못 봄 | 확인됨 (arXiv API) · 미확인 |
| C9 Humanoid-Gym | 2404.05695 v2 · ICRA 2024 workshop | 휴머노이드 | 미확인 | 미확인 (README 링크는 legged_gym · rsl_rl) | [roboterax/humanoid-gym](https://github.com/roboterax/humanoid-gym) @ae46e201 · 라이선스 표기 없음 | 확인됨 (arXiv API · 메타) |
| C10 LCP | 2410.11825 v3 · IROS 2025 (README) | 휴머노이드 | 미확인 | 미확인 | [zixuan417/smooth-humanoid-locomotion](https://github.com/zixuan417/smooth-humanoid-locomotion) @004f6706 · NOASSERTION | README 주장 |
| C11 HugWBC | 2502.03206 v3 · RSS 2025 (arXiv comment) | 휴머노이드 | 미확인 | 미확인 | [InternRobotics/HugWBC](https://github.com/InternRobotics/HugWBC) @eb831af7 (apexrl 에서 옮김) · 라이선스 표기 없음 | README 주장 |

### 2.4 구현 · 재현 · 학습 틀 (새 방법 아님)

| 저장소 (SHA) | 무엇 | Go2 | 판 | 근거 |
|---|---|---|---|---|
| [shivam-sood00/Gurukul](https://github.com/shivam-sood00/Gurukul) (cfde1437, Apache-2.0) | Go2 Isaac Lab 실험 모음. START · REAL(Stage 1 teacher 만) · AME · Contact Trails(저장소 자체 모듈, 발 접촉으로 만든 자기중심 기억 지도) · depth 증류 · LiDAR(OmniPerception 파일은 공개 판에서 뺌) task 등록. **모두 「수렴 · 실행 · 논문 재현 증거 없음」**. START 지도 encoder 는 논문 CNN 대신 MLP + global token 3개. AME 는 stride-2 CNN 에 XYZ, actor · critic encoder 분리, 단일 단계, actor 에 선속도 없음 | 예 | Isaac Sim 5.1.0.0 · Isaac Lab 0.54.3 · rsl-rl-lib 5.3.0 | README 주장 (문서 사이트 task-status · start · real · ame · contact-trails · installation 페이지) |
| [SII-FUSC/AME_Locomotion](https://github.com/SII-FUSC/AME_Locomotion) (1d3519ee, 라이선스 표기 없음) | AME(v1) 재현, G1 29-DoF. CNN 에 XYZ, stride 다운샘플, AME-2 global context 추가(ame2.pt). 2단계 (`FINETUNE`) | 아니오 | README 중국어 단락은 Isaac Sim 5.1.0 + Isaac Lab 2.3.0, 영어 단락은 5.0.0 + 2.3.0 (서로 다름) | README 주장 · 확인됨 (ckpt 파일 트리) |
| [fan-ziqi/robot_lab](https://github.com/fan-ziqi/robot_lab) (500399ed, Apache-2.0) | Isaac Lab 확장. `RobotLab-Isaac-Velocity-Rough-Unitree-Go2-v0` 등 속도 추종 rough task. go2_rl_robotlab · Gurukul 의 바탕 (rl_training 은 「일부 코드 사용」) | 예 | Isaac Lab 2.3.2 · Isaac Sim 5.1 (README 판 표) | README 주장 |
| [DeepRoboticsLab/rl_training](https://github.com/DeepRoboticsLab/rl_training) (3d05d3b9, BSD-3) | Lite3 (START 의 로봇) rough task Isaac Lab | 아니오 | Isaac Sim 5.1.0 · Isaac Lab 2.3.2 · RSL-RL 5.0.1 | README 주장 |
| [unitreerobotics/unitree_rl_mjlab](https://github.com/unitreerobotics/unitree_rl_mjlab) (1425b15f, Apache-2.0) | Unitree 공식 mjlab 환경, `Unitree-Go2-Flat` 속도 추종 | 예 (평지) | mjlab (MuJoCo Warp) | README 주장 |
| [mujocolab/mjlab](https://github.com/mujocolab/mjlab) (371e3b7e) · [google-deepmind/mujoco_playground](https://github.com/google-deepmind/mujoco_playground) (d59156e0) | MuJoCo Warp · MJX 학습 틀. Playground 는 사족 · 이족 보행 환경 있음 (세부 안 읽음) | 미확인 | Apache-2.0 | README 주장 |
| [project-instinct/InstinctLab](https://github.com/project-instinct/InstinctLab) · instinct_rl · [InstinctMJ](https://github.com/project-instinct/InstinctMJ) | Hiking · Deep Whole-body Parkour 의 학습 틀 (Isaac Lab · mjlab 판) | 아니오 (G1) | Isaac Lab commit `f73c331738` | README 주장 |
| [abizovnuralem/go2_omniverse](https://github.com/abizovnuralem/go2_omniverse) (db18970d, BSD-2) | Isaac Sim Go2 · G1 디지털 트윈 + ROS2. isaac-go2-ros2 의 제어기 출처 | 예 | Isaac Sim 5.x · ROS 2 Jazzy 이식 (README) | README 주장 |
| 로봇별 보행 학습 설정 (hop 3 · 4 · hop′1): asimov-mjlab · microduck_rl · mjlab-homierl · mjlab_upkie · booster_gym · booster_train · engineai_rl_lab | 특정 이족 · 휴머노이드 · 바퀴 로봇용 속도 추종 설정. 논문 방법이 아니다. README 에 depth · LiDAR · camera · height scan 언급 없음 (키워드 검색) | 아니오 | 각 README | 확인됨 (README 키워드 검색) |

### 2.5 범위 밖으로 이름만 적은 것 (36)

휴머노이드 motion tracking · 텔레오퍼레이션: BeyondMimic (2508.08241 v4) · ASAP (2502.01143 v3) · HOMIE (2502.13013 v2) · PHC (2305.06456 v3) · ProtoMotions · MimicKit (2510.13794 v4) · TWIST2 (2511.02832 v1) · TWIST · SONIC (2511.07820 v4) · ZEST (2602.00401 v1) · OmniXtreme (2602.23843 v1) · HUSKY (2602.03205 v2) · CLOT (2602.15060 v2) · DynaRetarget (2602.06827 v3) · PAC-MAN (2607.28623 v2) · FRoM-W1 (2601.12799 v1) · Embrace Collisions (2502.01465 v1) · PBHC (KungfuBot) · AMO · GMT · AMP (2104.02180) · DeepMimic (1804.02717) · APEX (2511.09091 v2) · DecAP (2310.05714 v3) · Expressive Humanoid (expressive-humanoid).
조작 · 기타: Deep Whole-Body Control (2210.10044) · Legs as Manipulator (2303.11330) · Visual Whole-Body Control (2403.16967) · Arm-Constrained Curriculum (2403.16535) · SLIM (2509.03859) · ToddlerBot · Locomotion Beyond Feet (2601.03607).
드론 · 비로봇: NavRL (2409.15634, 드론) · OmniDrones (2309.12825) · jev-drone · flybody (awesome-fly 안, 초파리).

판 번호는 arXiv API 로 제목만 확인했다. 본문은 읽지 않았다.

### 2.6 이미 덮은 방법에 붙는 새 사실

| 방법 | 새 사실 | 근거 |
|---|---|---|
| MARG | 프로젝트 페이지 그림 `succ_tab.png`: Go2 실기, 지형별 5회. Narrow balance beams 3/5 · **Outdoor single gap 4/5** · Narrow ditch 5/5 · Soft step 3/5 · Single plank bridge 2/5 · **Indoor single gap 5/5** · Drainage ditch 3/5 · Step 3/5. gap 폭 · 정책 판(Go1 학습 정책인지 Go2 재학습인지)은 표에 없다. 페이지 본문은 「4096 Go2 로 새 parkour 지형 학습」 영상도 적는다 | README 주장 (astrorix.github.io/MARG 페이지 · 그림을 내려받아 확인) |
| START | Gurukul Go2 적응 판의 차이 (2.4 표). SURVEY §8.2 는 코드 내용을 안 읽었다고 적었고, 이 조사도 코드는 안 읽고 문서 사이트만 읽었다 | README 주장 (문서 사이트) |
| AME-2 | 제3자 재현(SII-FUSC)은 AME(v1)에 AME-2 의 global context 만 더한 G1 판이다. AME-2 의 학습형 지도 · student 는 없다 | README 주장 |
| JEPLO | 프로젝트 페이지에 Hugging Face 데이터셋 `ASIG-Lab/JEPLO-Dataset` 과 하드웨어 CAD 페이지 링크가 있다 | 확인됨 (페이지 링크 추출) |

---

## 3. hop 기록

### 3.1 star 에서 출발한 그래프

「방문」은 README 또는 페이지를 내려받아 링크를 뽑은 것. 「적기만」은 이름 · 설명만 보고 펼치지 않은 것.

| hop | 방문한 노드 (주요) | 새 1·2등급 | 새 3등급 | 범위 밖 · 기반 도구 |
|---|---|---|---|---|
| 0 | star 249개 중 31개 README (유지 20 · 가지침 6 · 확인용 5) + 자기 페이지: MARG (Risky_gym) · JEPLO · legged_gym · robogauge (go2_rl_robotlab) · Isaac Lab 문서 | 없음 (덮은 것뿐) | 없음 | 부록 |
| 1 | rsl_rl (+ 문서) · HIMLoco (+ 페이지, OpenRobotLab 이름으로도 받음) · robot_lab · whole_body_tracking · go2_omniverse · NavRL · Mid360_simulation_plugin · mujoco_terrains · unitree_cpp_deploy · unitree_mujoco · unitree_ros · mujoco_menagerie · dm_control · go2-webrtc · livox_ros_driver2 · A-LOAM | 없음 | HIMLoco · CTS · DreamWaQ (go2_rl_gym README 의 논문 링크) | BeyondMimic · NavRL |
| 2 | mjlab (+ Research 문서 페이지) · mujoco_playground · HINF 페이지 · rl_sar · ASAP · humanoid_amp · motion_tracking_controller · OmniDrones · robot_descriptions.py · livox_laser_simulation · unitree_ros2 · unitree_ros_to_real · go2_webrtc_connect · isaacsim_launcher | 없음 | H-Infinity | ASAP · AMP · OmniDrones |
| 3 | InstinctMJ (+ project-instinct 사이트) · unitree_rl_mjlab · mjlab-homierl · asimov-mjlab · microduck_rl · wbc-mjlab · twist2_mjlab · perceptive_cbf_rl · mjlab_upkie · brax · mujoco_warp · walk-these-ways (+ 페이지) · RoboMimic_Deploy · Lite3_MotionSDK · unitree_guide · HumanoidVerse · human2humanoid · PHC · awesome-robot-descriptions · booster_gym · toddlerbot · legged_template_controller | 없음 | Walk These Ways | HOMIE · PHC · TWIST2 · PAC-MAN · SONIC · ZEST · OmniXtreme · HUSKY · CLOT · DynaRetarget |
| 4 | InstinctLab (+ `tasks/parkour/README.md`) · instinct_rl · robot-parkour 페이지 (+ ZiwenZhuang/parkour, `legged_gym/README.md`) · humanoid4parkour · deep-whole-body-parkour · hiking-in-the-wild 페이지 · rapid-locomotion-rl · rl_training · Lite3_rl_deploy · ProtoMotions · humanoid-gym · booster_train · awesome-open-source-robots · locomotion-beyond-feet 페이지 | **Robot Parkour Learning · Humanoid Parkour Learning · Hiking in the Wild · Deep Whole-body Parkour · DIC** | Rapid Locomotion · Humanoid-Gym | Embrace Collisions · ToddlerBot · Locomotion Beyond Feet |
| 5 | manipulation-locomotion 페이지 (+ Deep-Whole-Body-Control) · model-free-agility (404) · MimicKit · Genesis · RoboJuDo | 없음 | RMA (rapid-locomotion-rl README 의 논문 링크) | Deep Whole-Body Control · MimicKit |
| 6 | HugWBC · smooth-humanoid-locomotion (README) / 적기만: PBHC · AMO · TWIST · GMT · FRoM-W1 · GMR | 없음 | LCP · HugWBC | PBHC · AMO · TWIST · GMT · FRoM-W1 |
| 7 | HugWBC · LCP 의 링크: expressive-humanoid (적기만) 외에는 이미 본 노드 | 없음 | 없음 | expressive-humanoid |

**멈춤**: hop 5 · 6 에 1·2등급 새 방법이 없어 멈췄다. hop 7 은 펼친 노드가 둘뿐이라 「없음」은 그 둘의 링크에 한한다.

### 3.2 보조 출발점에서 출발한 그래프

출발점: Gurukul (SURVEY §8.2 가 가리킴, 코드 미독) · HiPAN 페이지 (PAPERS §6). MARG · JEPLO · RoboGauge 페이지는 star 그래프 hop 0 노드(자기 페이지)로 이미 봤다.

| hop′ | 방문한 노드 | 새 1·2등급 | 새 3등급 | 범위 밖 · 기반 도구 |
|---|---|---|---|---|
| 0 | Gurukul README + 문서 사이트 10쪽 (credits · task-status · tasks overview · training-methods · start · real · ame · contact-trails · lidar-based · installation) · HiPAN 페이지 (arXiv 링크뿐) | 없음 | 없음 | |
| 1 | JIAlonglong/REAL (+ REAL 페이지) · SII-FUSC/AME_Locomotion · aCodeDog/OmniPerception · engineai_rl_lab / 논문: AME 2506.09588 · REAL · Omni-Perception · START (덮음) · CTS (봄) | **REAL · AME(v1) · Omni-Perception** | 없음 | APEX · DecAP · BeyondMimic · AMP · DeepMimic · Visual WBC · Arm-Constrained · SLIM · RevoLab |
| 2 | extreme-parkour.github.io (+ chengxuxin/extreme-parkour) · AMP_for_hardware · legged_lab · MimicKit (봄) | **Extreme Parkour** | 없음 | MimicKit · GMR |
| 3 | RMA 페이지 · robot-skills 페이지 · vision-locomotion 페이지 | **Egocentric Vision** | RMA (star 그래프 hop 5 와 같음) | Legs as Manipulator |
| 4 | antonilo/rl_locomotion (+ CMS 페이지 · antonilo/vision_locomotion) · energy-locomotion 페이지 · navigation-locomotion 페이지 (+ MarkFzp/navigation-locomotion) · manipulation-locomotion (봄) | **CMS · VP-Nav** | Energy gaits | Deep Whole-Body Control (봄) · xbpeng 페이지 |
| 5 | 링크: realsense-ros · unitree_legged_sdk · librealsense · hora(손 조작) · worldsheet · noe-eva(무관한 개인 페이지) | 없음 | 없음 | 전부 |
| 6 | 펼칠 범위 안 노드 없음 | 없음 | 없음 | |

**멈춤**: hop′5 · 6 에 새 방법이 없다.

REAL README 표에 SoloParkour 와 RPL 이 이름으로만 나오고 링크는 없다. 이름만 나온 것은 따라가지 않았다(「못 본 것」).

---

## 부록. 팀장 star 전체 (2026-10-13 01:15 조회, 249개)

「유지」는 보행 · 시뮬 · 지각 관련으로 README 를 열고 링크를 hop 1 로 넘긴 것. 「유지 후 가지침」은 열어 봤지만 보행 정책 · 보행 링크가 없어 펼치지 않은 것. 「뺌」은 설명만 보고 뺀 것이고 README 를 열지 않았다(확인용으로 연 5개 제외. 설명 열을 보고 빠뜨린 것이 있는지 확인할 수 있다). 「덮음」은 이미 조사한 저장소.

| # | 저장소 | 마지막 push | GitHub 설명 (앞 80자) | 판정 · 까닭 |
|---|---|---|---|---|
| 1 | abizovnuralem/go2_ros2_sdk | 2026-07-13 | Unofficial ROS2 SDK support for Unitree GO2 AIR/PRO/EDU | 유지 · Go2 ROS2 드라이버 (보행 정책 없음) |
| 2 | legion1581/unitree_webrtc_connect | 2026-08-17 | Unitree Go2 / G1 / R1 WebRTC driver | 유지 · Go2 WebRTC 드라이버 (보행 정책 없음) |
| 3 | manycore-research/SpatialLM | 2026-06-26 | [NeurIPS 2025] SpatialLM: Training Large Language Models for Structured Indoor M… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 4 | microsoft/ResearchStudio | 2026-09-21 | ResearchStudio: Our AI co-author, from research problem to final publication. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 5 | facebookresearch/sam3 | 2026-10-07 | The repository provides code for running inference and finetuning with the Meta … | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 6 | facebookresearch/faiss | 2026-10-12 | A library for efficient similarity search and clustering of dense vectors. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 7 | facebookresearch/segment-anything | 2024-09-18 | The repository provides code for running inference with the SegmentAnything Mode… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 8 | facebookresearch/MUSE | 2022-08-31 | A library for Multilingual Unsupervised or Supervised word Embeddings | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 9 | facebookincubator/muse-gadget-sdk | 2026-10-12 | Open source SDK to build Muse gadgets | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 10 | mvschwarz/openrig | 2026-10-12 | Build your own network of agents from Claude Code, Codex and Pi: persistent team… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 11 | tester-army/e2e | 2026-10-12 | Next generation e2e testing framework for web and mobile apps. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 12 | morluto/rea | 2026-10-12 | Reverse engineer anything with agents, from app behavior down to native binaries… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 13 | cursor/plugins | 2026-10-12 | Cursor plugin specification and official plugins | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 14 | NVIDIA/NemoClaw | 2026-10-12 | Run agents like Hermes, LangChain Deep Agents, and OpenClaw more securely inside… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 15 | NVIDIA/OpenShell | 2026-10-12 | OpenShell is the safe, private runtime for autonomous AI agents. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 16 | VectifyAI/PageIndex | 2026-10-12 | 📑 PageIndex: Document Index for Vectorless, Reasoning-based RAG | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 17 | thedotmack/claude-mem | 2026-10-12 | Persistent Context Across Sessions for Every Agent - Captures everything your ag… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 18 | pablostanley/yoinks | 2026-07-17 | yoink any video from your terminal. no shady ads. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 19 | DuarteSantos8/openGym | 2026-10-12 | Self-hosted gym & body-weight tracker · plan routines, log workouts (supersets, … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 20 | NandhaKishorM/laya | 2026-10-12 | Non-autoregressive System 1 decision engine. Typed choice, score and yes/no deci… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 21 | playcanvas/supersplat | 2026-10-05 | 3D Gaussian Splat Editor | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 22 | leggedrobotics/ame2_minimal | 2026-10-06 | official reimplementation of AME-2 | 유지 · 덮음 (SURVEY §1) · README 링크를 hop 1 로 |
| 23 | RomanSlack/jev-drone | 2026-09-24 | Camera-only autonomous drone in MuJoCo with a small judgment model (TypeSafe Jev… | 유지 후 가지침 · MuJoCo 드론 내비게이션 (다리 없음) |
| 24 | ruvnet/ruflo | 2026-10-12 | 🌊 The original agent harness. Deploy intelligent multi-player swarms, coordinate… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 25 | debpalash/VoiceStudio | 2026-10-12 | VoiceStudio is the open-source, fully-local ElevenLabs alternative · voice cloni… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 26 | shitagaki-lab/see-through | 2026-10-05 | "Single-image Layer Decomposition for Anime Characters" (SIGGRAPH 2026 Conferenc… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 27 | nv-tlabs/lyra | 2026-07-20 | Project Lyra: Open Generative 3D World Models | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 28 | baranowskibrt/onecanvas | 2026-10-02 | [NeurIPS 2026 Spotlight] Official code and checkpoints for OneCanvas: 3D Scene U… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 29 | aigc3d/Glob3R | 2026-07-17 | Official Repo of "Glob3R: Global Structure-from-Motion with 3D Foundation Models… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 30 | hku-mars/loam_livox | 2020-02-24 | A robust LiDAR Odometry and Mapping (LOAM) package for Livox-LiDAR | 유지 · LiDAR odometry · mapping (보행 정책 없음) |
| 31 | ankitdhall/lidar_camera_calibration | 2025-10-16 | ROS package to find a rigid-body transformation between a LiDAR and a camera for… | 유지 · LiDAR-카메라 보정 (보행 정책 없음) |
| 32 | hustvl/4DGaussians | 2024-10-27 | [CVPR 2024] 4D Gaussian Splatting for Real-Time Dynamic Scene Rendering | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 33 | SpatiaOS/Procedura | 2026-08-27 | Agentic 3D Modeling with Procedural Control · turns a text prompt into an editab… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 34 | yanyan-li/4DGS-SLAM | 2025-08-08 | Instead of removing dynamic objects as distractors and reconstructing only stati… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 35 | google-deepmind/tapnet | 2026-09-15 | Tracking Any Point (TAP) | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 36 | 666ghj/MiroFish | 2026-10-01 | A Simple and Universal Swarm Intelligence Engine, Predicting Anything. 简洁通用的群体智能… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 37 | freemocap/freemocap | 2026-10-10 | Free Motion Capture for Everyone 💀✨ | 뺌 · 사람 모션캡처 (로봇 정책 아님) |
| 38 | aipoch/open-science | 2026-10-12 | The open-source AI research workbench for scientific research and agent workflow… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 39 | ahujasid/mcp-for-blender | 2026-10-06 | Community plugin to control Blender 3D with any LLM of your choice. Not affiliat… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 40 | blender/blender | 2026-10-12 | Official mirror of Blender | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 41 | higgsfield-ai/cli | 2026-09-18 | Higgsfield CLI | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 42 | KKKKhazix/AIHOT | 2026-10-12 | 一个自己找热点、自己写日报的网站框架。把信源和精选标准换成你的，它就是你的行业热点站。 | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 43 | unitreerobotics/unitree_rl_gym | 2025-07-25 |  | 유지 · 덮음 (SURVEY §6) |
| 44 | microsoft/onnxruntime | 2026-10-12 | ONNX Runtime: cross-platform, high performance ML inferencing and training accel… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 45 | wty-yy/RoboGauge | 2026-10-05 | Evaluate the performance metrics for different RL locomotion models. | 유지 · 덮음 (SURVEY §4) |
| 46 | google-deepmind/mujoco | 2026-10-12 | Multi-Joint dynamics with Contact. A general purpose physics simulator. | 유지 · 시뮬레이터 (README 링크를 hop 1 로) |
| 47 | unitreerobotics/unitree_sdk2 | 2026-09-21 | Unitree robot sdk version 2. https://support.unitree.com/home/zh/developer | 유지 · Unitree 저수준 SDK (정책 없음 · README 링크 없음) |
| 48 | unitreerobotics/unitree_sdk2_python | 2026-09-21 | Python interface for unitree sdk2 | 유지 · SDK 파이썬 판 (정책 없음) |
| 49 | leggedrobotics/legged_gym | 2025-05-29 | Isaac Gym Environments for Legged Robots | 유지 · 덮음 (SURVEY §6) |
| 50 | wty-yy/go2_rl_gym | 2026-07-06 | [RSS 2026] Toward Reliable Sim-to-Real Predictability for MoE-based Robust Quadr… | 유지 · 덮음 (SURVEY §3) · README 의 CTS · HIM · DreamWaQ 링크를 hop 1 로 |
| 51 | wertyuilife2/go2_rl_robotlab | 2026-07-27 | [RSS 2026] Toward Reliable Sim-to-Real Predictability for MoE-based Robust Quadr… | 유지 · 덮음 (SURVEY §3) |
| 52 | ASIG-X/JEPLO | 2026-09-17 | First JEPA-based learning framework for mapping-free LiDAR-based perceptive loco… | 유지 · 덮음 (SURVEY §5) |
| 53 | K-Dense-AI/scientific-agent-skills | 2026-10-12 | Turn any AI agent into an AI Scientist. The #1 Agent Skills library for science,… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 54 | ai-boost/awesome-harness-engineering | 2026-10-12 | Awesome list for AI agent harness engineering: tools, patterns, evals, memory, M… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 55 | volcengine/OpenViking | 2026-10-12 | Self-evolving Context Database for AI Agents. Unify Agent Memory, Knowledge RAG … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 56 | rohitg00/agentmemory | 2026-10-12 | #1 Persistent memory for AI coding agents based on real-world benchmarks | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 57 | headroomlabs-ai/headroom | 2026-10-11 | Compress tool outputs, logs, files, and RAG chunks before they reach the LLM. 20… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 58 | diegosouzapw/OmniRoute | 2026-10-11 | Never stop coding. Free MIT AI gateway: one endpoint, 359 providers (150+ free),… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 59 | Graphify-Labs/graphify | 2026-10-12 | Turn any codebase, with its docs, SQL schemas, configs, and PDFs, into a queryab… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 60 | amap-cvlab/ABot-Recon | 2026-09-25 | Streaming 3D reconstruction from only video input: Revisiting Local Context for … | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 61 | Maelic/RelateAnything | 2026-10-11 | RelateAnything: Real-Time Open-Vocabulary Relation Prediction From Any Inputs | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 62 | StarTrail-org/LEANN | 2026-10-09 | [MLsys2026 Best Paper]: https://arxiv.org/abs/2506.08276. RAG on Everything with… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 63 | robbietilton/Compositor | 2026-10-12 | The Photoshop alternative for Mac | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 64 | github/spec-kit | 2026-10-12 | 💫 Toolkit to help you get started with SDD or any other process! | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 65 | JustVugg/colibri | 2026-10-11 | Run frontier MoE models on hardware you already own · pure C, zero deps, experts… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 66 | davila7/claude-code-templates | 2026-10-12 | CLI tool for configuring and monitoring Claude Code | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 67 | dreamurl/GPT-Bridge | 2026-09-16 |  | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 68 | uppinote20/claude-dashboard | 2026-10-06 | Comprehensive status line plugin for Claude Code with context usage, API rate li… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 69 | trycua/cua | 2026-10-12 | Scale computer-use 2.0 with open-source drivers, cross-OS fleets, and benchmarks… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 70 | docling-project/docling | 2026-10-12 | Get your documents ready for gen AI | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 71 | arclab-hku/Risky_gym | 2025-05-14 |  | 유지 · 덮음 (SURVEY §8.1) · MARG 페이지를 hop 1 로 |
| 72 | odoo/odoo | 2026-10-12 | Odoo. Open Source Apps To Grow Your Business. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 73 | tamaratran/fast-jev-compaction | 2026-09-18 | Claude Code plugin that replaces the compaction summary with Jev decisions: ever… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 74 | browser-use/jev-ultrafast | 2026-09-30 | Fastest and cheapest web agent | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 75 | google/artemis | 2026-10-01 | ARTEMIS turns natural-language instructions into reliable Android automation. It… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 76 | AprilRobotics/apriltag | 2026-08-07 | AprilTag is a visual fiducial system popular for robotics research. | 유지 후 가지침 · fiducial 마커 (보행 아님) |
| 77 | pacifio/atlas | 2026-10-12 | Source control for agents. Use multiple coding agents, track their changes and q… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 78 | THU-MAIC/OpenMAIC | 2026-10-12 | Open Multi-Agent Interactive Classroom · Get an immersive, multi-agent learning … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 79 | nv-tlabs/3dgrut | 2026-09-22 | Ray tracing and hybrid rasterization of Gaussian particles | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 80 | cobanov/awesome-fly | 2026-10-05 | A curated list of fruit fly connectome projects: MaleCNS, FlyWire, brain simulat… | 뺌 · 초파리 커넥톰 목록. flybody(MuJoCo 초파리 보행 RL) 가 있으나 로봇 아님 |
| 81 | jgraph/drawio | 2026-10-08 | draw.io is a JavaScript, client-side editor for general diagramming. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 82 | jgraph/drawio-desktop | 2026-10-11 | Official electron build of draw.io | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 83 | huawei-bayerlab/marigold-v2 | 2026-10-05 | Marigold V2: Revisiting Diffusion Transformers for Monocular Depth Estimation | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 84 | prs-eth/Marigold | 2026-09-06 | [CVPR 2024 - Oral, Best Paper Award Candidate] Marigold: Repurposing Diffusion-B… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 85 | trailhq/Graft | 2026-10-12 | Turbocharge Claude Code, Cursor, Codex, Gemini & every coding agent: faster, che… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 86 | graykode/abtop | 2026-09-14 | Like htop, but for AI coding agents. Monitor Claude Code & Codex CLI sessions, t… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 87 | tt-a1i/archify | 2026-10-12 | Turn any idea, plan, or codebase into a beautiful interactive diagram. An agent … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 88 | PaddlePaddle/PaddleOCR | 2026-09-16 | Turn any PDF or image document into structured data for your AI. A powerful, lig… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 89 | D4Vinci/Scrapling | 2026-10-11 | 🕷️ An adaptive Web Scraping framework that handles everything from a single requ… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 90 | hugohe3/ppt-master | 2026-10-11 | AI turns documents or topics into real, native PowerPoint decks · with native sh… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 91 | dgtlmoon/changedetection.io | 2026-10-12 | Best and simplest tool for website change detection, web page monitoring, and we… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 92 | every-app/open-seo | 2026-10-08 | Open source alternative to Semrush and Ahrefs | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 93 | trycompai/crm | 2026-09-11 | Comp AI CRM is an open source, CRM designed for AI agents. Agentic-first CRM. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 94 | fabio-sim/Depth-Anything-ONNX | 2024-10-03 | ONNX-compatible Depth Anything: Unleashing the Power of Large-Scale Unlabeled Da… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 95 | DepthAnything/Depth-Anything-V2 | 2026-03-24 | [NeurIPS 2024] Depth Anything V2. A More Capable Foundation Model for Monocular … | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 96 | larashero3-dotcom/lieflat-charts | 2026-09-05 | Data visualization Skill for AI Agents, turning data into polished, interactive … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 97 | abi/screenshot-to-code | 2026-10-09 | Drop in a screenshot and convert it to clean code (HTML/Tailwind/React/Vue) | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 98 | ant-research/4DAnyone | 2026-09-23 | [SIGGRAPH Asia 2026] 4DAnyone: Create Anyone in 4D from a Casual Monocular Video | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 99 | pixel-agents-hq/pixel-agents | 2026-10-09 | Pixel office. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 100 | semantica-agi/semantica | 2026-10-12 | Graph-Native Infrastructure for Context and Accountable AI Systems | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 101 | cactus-compute/needle | 2026-10-11 | Automation foundation model for tiny devices: 2-bit, 8-29 MB, tool calls, ASR, s… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 102 | megadose/holehe | 2024-09-10 | holehe allows you to check if the mail is used on different sites like twitter, … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 103 | omacom/omarchy | 2026-10-12 | Beautiful, Modern & Opinionated Linux | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 104 | macro-inc/macro | 2026-10-12 | Macro is a unified workspace for teams: email, chat, docs, tasks, agents, calls,… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 105 | unslothai/unsloth | 2026-10-12 | Local UI to run and train LLMs and diffusion models. Supports GGUF, MLX, Qwen3.8… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 106 | lightningpixel/modly | 2026-10-04 | Desktop app to generate 3D models from images or prompt using local AI · runs en… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 107 | public-apis/public-apis | 2026-10-11 | A collective list of free APIs | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 108 | 3b1b/manim | 2026-09-09 | Animation engine for explanatory math videos | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 109 | cathrynlavery/diagram-design | 2026-10-12 | Editorial diagram design for Claude Code, Codex, GitHub Copilot, Cursor, Factory… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 110 | PrimeIntellect-ai/prime-agent | 2026-10-12 | A self-improving RLM agent for coding workflows and long-running autonomous task… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 111 | NVIDIA-Omniverse/omniverse-labs | 2026-09-29 | Omniverse Labs is a project housing experimental Omniverse sample content | 유지 후 가지침 · Omniverse 실험 모음 (README 에 보행 없음) |
| 112 | hms-gymnopedie/IsaacSim_Setting | 2026-02-10 | Isaac Sim Setting Dockerfile | 유지 · Isaac Sim Dockerfile (정책 없음 · 링크 없음) |
| 113 | nyrahealth/CrisperWhisper | 2026-09-22 | Controllable Transcription. Verbatim ( every, filler, pause, stutter, vocal soun… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 114 | tensorflow/tensorboard | 2026-10-09 | TensorFlow's Visualization Toolkit | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 115 | Zhefan-Xu/isaac-go2-ros2 | 2025-09-23 | Unitree Go2 simulation platform for testing navigation, decision-making and auto… | 유지 · 덮음 (SURVEY §7) |
| 116 | unitreerobotics/unitree_rl_lab | 2026-05-25 | This is a repository for reinforcement learning implementation for Unitree robot… | 유지 · 덮음 (SURVEY §7) |
| 117 | supabase/supabase | 2026-10-12 | The Postgres development platform. Supabase gives you a dedicated Postgres datab… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 118 | isaac-sim/IsaacSim | 2026-10-02 | NVIDIA Isaac Sim™ is an open-source application on NVIDIA Omniverse for developi… | 유지 · 시뮬레이터 (README 에 외부 저장소 링크 없음) |
| 119 | isaac-sim/IsaacLab | 2026-10-12 | Unified framework for robot learning with multi-physics/renderer support | 유지 · 학습 틀 (README · 환경 목록 페이지 확인, 외부 방법 링크 없음) |
| 120 | GuanYixuan/pyCapCut | 2026-10-01 | A lightweight, flexible, and easy-to-use Python tool for generating and exportin… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 121 | openai/codex | 2026-10-12 | Lightweight coding agent that runs in your terminal | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 122 | OpenCut-app/OpenCut | 2026-09-24 | The open-source CapCut alternative | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 123 | earendil-works/pi | 2026-10-12 | AI agent toolkit: unified LLM API, agent loop, TUI, coding agent CLI | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 124 | openinterpreter/openinterpreter | 2026-10-11 | A coding agent for open models like Kimi K3 and GLM 5.3 | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 125 | HKUDS/LightRAG | 2026-10-12 | [EMNLP2025] LightRAG: Simple and Fast Retrieval-Augmented Generation | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 126 | HKUDS/nanobot | 2026-10-12 | Ultra-lightweight, open-source, self-hosted personal AI agent framework in Pytho… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 127 | HKUDS/DeepTutor | 2026-10-12 | DeepTutor: Lifelong Personalized Tutoring. https://deeptutor.info/. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 128 | HKUDS/Vibe-Trading | 2026-10-12 | "Vibe-Trading: Your Personal Trading Agent" | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 129 | vinta/awesome-python | 2026-10-12 | The definitive list that answers "I want to do X in Python, which tool should I … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 130 | star-history/star-history | 2026-09-12 | The de facto GitHub star history graph. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 131 | citrolabs/ego-lite | 2026-10-12 | The fastest browser for AI agents to run browser automation, built for sharing y… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 132 | microsoft/vscode | 2026-10-12 | Visual Studio Code | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 133 | microsoft/playwright-cli | 2026-09-28 | CLI for common Playwright actions. Record and generate Playwright code, inspect … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 134 | microsoft/playwright-python | 2026-10-09 | Python version of the Playwright testing and automation library. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 135 | microsoft/playwright-mcp | 2026-10-08 | Playwright MCP server | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 136 | microsoft/playwright | 2026-10-12 | Playwright is a framework for Web Testing and Automation. It allows testing Chro… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 137 | mem0ai/mem0 | 2026-10-09 | The Memory Layer for AI Agents - Drop-in memory infrastructure for AI agents and… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 138 | Julian-adv/OpenMMO | 2026-10-10 |  | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 139 | heygen-com/hyperframes | 2026-10-12 | Write HTML. Render video. Built for agents. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 140 | Yeachan-Heo/oh-my-claudecode | 2026-10-12 | Teams-first Multi-agent orchestration for Claude Code | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 141 | tmux/tmux | 2026-10-12 | tmux source code | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 142 | lidge-jun/opencodex | 2026-10-12 | Universal provider proxy for OpenAI Codex & Claude Code · use any LLM (Claude, G… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 143 | Robbyant/lingbot-map | 2026-10-10 | [ECCV 2026 Best Paper Award Candidate] LingBot-Map: Geometric Context Transforme… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 144 | poloclub/transformer-explainer | 2026-06-06 | Transformer Explained Visually: Learn How LLM Transformer Models Work with Inter… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 145 | paperclipai/paperclip | 2026-10-12 | The open-source app everyone uses to manage agents at work | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 146 | Nutlope/hallmark | 2026-08-06 | Anti-AI-slop design skill for Claude Code, Cursor, and Codex. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 147 | TencentCloud/CubeSandbox | 2026-10-12 | Instant, Concurrent, Secure & Lightweight Sandbox for AI Agents. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 148 | bradautomates/claude-video | 2026-09-25 | Give Claude the ability to watch any video. /watch downloads, extracts frames, t… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 149 | techwithanant/saras_ai_robot_v2 | 2026-06-19 |  | 유지 후 가지침 · 바퀴 로봇 차 + Claude MCP (다리 없음) |
| 150 | chatchat-space/Langchain-Chatchat | 2025-11-10 | Langchain-Chatchat（原Langchain-ChatGLM）基于 Langchain 与 ChatGLM, Qwen 与 Llama 等语言模型… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 151 | pollen-robotics/AmazingHand | 2026-04-23 | Code and model to control the AH! | 유지 후 가지침 · 로봇 손 (보행 아님) |
| 152 | huggingface/lerobot | 2026-10-12 | 🤗 LeRobot: Making AI for Robotics more accessible with end-to-end learning | 유지 후 가지침 · 로봇 학습 라이브러리 (조작 중심 · 링크는 leLab 뿐) |
| 153 | koala73/worldmonitor | 2026-10-12 | Real-time global intelligence dashboard. AI-powered news aggregation, geopolitic… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 154 | Panniantong/Agent-Reach | 2026-10-08 | Give your AI agent eyes to see the entire internet. Read & search Twitter, Reddi… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 155 | google-research/timesfm | 2026-09-29 | TimesFM (Time Series Foundation Model) is a pretrained time-series foundation mo… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 156 | NVIDIA/SkillSpector | 2026-10-12 | Security scanner for AI agent skills. Detect vulnerabilities, malicious patterns… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 157 | withastro/flue | 2026-10-12 | The sandbox agent framework. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 158 | Saqoosha/ccusage-menubar | 2025-06-19 |  | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 159 | edwardkim/rhwp | 2026-10-12 | 아래한글 hwp viewer and editor by rust and wasm | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 160 | Leonxlnx/taste-skill | 2026-10-11 | Taste-Skill - gives your AI good taste. stops the AI from generating boring, gen… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 161 | stablyai/orca | 2026-10-12 | Orca is the ADE for working with a fleet of parallel agents. Run any coding agen… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 162 | MengTo/Skills | 2026-10-06 | Agent skills for designers and builders using Codex, Claude, Cursor, and other A… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 163 | MengTo/Spring | 2023-07-03 | A library to simplify iOS animations in Swift. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 164 | agentskills/agentskills | 2026-08-09 | Specification and documentation for Agent Skills | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 165 | elder-plinius/G0DM0D3 | 2026-07-15 | LIBERATED AI CHAT | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 166 | elder-plinius/L1B3RT4S | 2026-02-17 | TOTALLY HARMLESS LIBERATION PROMPTS FOR GOOD LIL AI'S! <NEW_PARADIGM> [DISREGARD… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 167 | elder-plinius/CL4R1T4S | 2026-09-22 | LEAKED SYSTEM PROMPTS FOR CHATGPT, CLAUDE, GEMINI, GROK, PERPLEXITY, CURSOR, LOV… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 168 | alirezarezvani/claude-skills | 2026-08-30 | 380 Claude Code skills & agent skills & plugins (30+ Agents, 70+ custom commands… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 169 | n8n-io/n8n | 2026-10-12 | Fair-code workflow automation platform with native AI capabilities. Combine visu… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 170 | Zackriya-Solutions/meetily | 2026-09-15 | Privacy first, AI meeting assistant with 4x faster Parakeet/Whisper live transcr… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 171 | gronxb/codex-relay | 2026-10-12 | Use Codex from your phone while the real work stays on your computer. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 172 | asgeirtj/system_prompts_leaks | 2026-10-12 | Documented system prompts from Anthropic - Claude Fable 5.1, Opus 5.5, Claude De… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 173 | browser-use/browser-use | 2026-10-09 | Agents that use the browser. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 174 | browser-use/video-use | 2026-10-08 | Edit videos with coding agents | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 175 | fivetaku/insane-search | 2026-10-12 | Auto-bypass for blocked websites in Claude Code · Phase 0→3 adaptive scheduler, … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 176 | usestrix/strix | 2026-10-12 | Open-source AI penetration testing tool to find and fix your app’s vulnerabiliti… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 177 | openai/codex-plugin-cc | 2026-07-08 | Use Codex from Claude Code to review code or delegate tasks. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 178 | microsoft/markitdown | 2026-10-04 | Python tool for converting files and office documents to Markdown. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 179 | MarcSkovMadsen/awesome-streamlit | 2023-05-25 | The purpose of this project is to share knowledge on how awesome Streamlit is an… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 180 | Adam-CAD/CADAM | 2026-10-07 | CADAM is the open source text-to-CAD web application | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 181 | ekimetrics/adaptive-chunking | 2026-07-06 | Adaptive Chunking: automatically select the best chunking method per document fo… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 182 | helloianneo/ian-xiaohei-illustrations | 2026-09-24 | 中文小黑怪诞正文配图生成 Skill / 16:9 白底手绘 / 少量红橙蓝批注 / Codex Skill | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 183 | NatronGitHub/Natron | 2026-07-24 | Open-source video compositing software. Node-graph based. Similar in functionali… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 184 | lsdefine/GenericAgent | 2026-10-11 | Self-evolving agent: grows skill tree from 3.3K-line seed, achieving full system… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 185 | DeusData/codebase-memory-mcp | 2026-10-12 | High-performance code intelligence MCP server. Indexes codebases into a persiste… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 186 | JCodesMore/ai-website-cloner-template | 2026-10-05 | Clone any website with one command using AI coding agents | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 187 | xbtlin/ai-berkshire | 2026-10-12 | AI 时代的伯克希尔：基于 Claude Code / Codex 的价值投资研究框架。巴菲特·芒格·段永平·李录四大师方法论 + 多Agent并行研究。/ A… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 188 | google-labs-code/stitch-skills | 2026-08-17 | A library of Agent Skills designed to work with the Stitch MCP server. Each skil… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 189 | revfactory/harness | 2026-09-28 | A meta-skill that designs domain-specific agent teams, defines specialized agent… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 190 | calesthio/OpenMontage | 2026-10-03 | World's first open-source, agentic video production system. 12 production pipeli… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 191 | mukul975/Anthropic-Cybersecurity-Skills | 2026-08-31 | 817 structured cybersecurity skills for AI agents · Mapped to 6 frameworks: MITR… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 192 | jamiepine/voicebox | 2026-10-07 | The open-source AI voice studio. Clone, dictate, create. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 193 | palmier-io/palmier-pro | 2026-10-05 | macOS video editor built for AI | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 194 | mgth/LittleBigMouse | 2026-09-17 | DPI Aware mouse move across screens | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 195 | penpot/penpot | 2026-10-12 | Penpot: The open-source design platform for Product teams that need scalable col… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 196 | DietrichGebert/ponytail | 2026-10-10 | Makes your AI agent think like the laziest senior dev in the room. The best code… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 197 | JuliusBrussee/caveman | 2026-10-12 | 🪨 why use many token when few token do trick. Viral skill + proxy for coding age… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 198 | theamusing/perfectPixel | 2026-02-01 | Refine and quantize messy AI pixel art into clean, perfect pixels. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 199 | aldegad/sprite-gen | 2026-10-12 | Generate clean 2D game sprites & animation atlases · component-row pipeline: sta… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 200 | nikopueringer/CorridorKey | 2026-05-28 | Perfect Green Screen Keys | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 201 | epoko77-ai/im-not-ai | 2026-10-12 | AI가 쓴 한글을 사람 글처럼 윤문하는 Claude 스킬 · Korean AI-text humanizer: detects and rewrites… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 202 | blader/humanizer | 2026-09-28 | Agent skill that removes signs of AI-generated writing from text | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 203 | SOMJANG/Mecab-ko-for-Google-Colab | 2023-07-15 | Use Mecab Library(NLP Library) in Google Colab | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 204 | tesseract-ocr/tessdata | 2024-03-09 | Trained models with fast variant of the "best" LSTM models + legacy models | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 205 | UB-Mannheim/tesseract | 2026-07-29 | Tesseract Open Source OCR Engine (main repository) | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 206 | smilegate-ai/korean_unsmile_dataset | 2022-04-08 |  | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 207 | ahastudio/til | 2026-10-12 | Today I Learned | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 208 | microsoft/SkillOpt | 2026-10-06 | SkillOpt is a text-space optimizer that trains reusable natural-language skills … | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 209 | VAST-AI-Research/TripoSplat | 2026-08-13 | TripoSplat converts a single 2D image into high-quality and variable number of 3… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 210 | opendataloader-project/opendataloader-pdf | 2026-10-12 | PDF Parser for AI-ready data. Automate PDF accessibility. Open-source. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 211 | nesquena/hermes-webui | 2026-10-12 | Hermes WebUI: The best way to use Hermes Agent from the web or from your phone! | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 212 | underlines/awesome-ml | 2025-04-25 | Curated list of useful LLM / Analytics / Datascience resources | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 213 | mattpocock/skills | 2026-10-12 | Skills for Real Engineers. Straight from my .agents directory. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 214 | eugeniughelbur/obsidian-second-brain | 2026-10-10 | Persistent memory for Claude Code and 6 other CLI agents, stored as plain markdo… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 215 | kepano/obsidian-skills | 2026-09-15 | Agent skills for Obsidian. Teach your agent to use Obsidian CLI and open formats… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 216 | breferrari/obsidian-mind | 2026-10-12 | A self-organizing Obsidian vault that gives AI coding agents persistent memory. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 217 | VoltAgent/awesome-design-md | 2026-10-12 | A collection of DESIGN.md files analysis by popular brand design systems. Drop o… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 218 | EveryInc/compound-engineering-plugin | 2026-10-12 | Official Compound Engineering plugin for Claude Code, Codex, Cursor, and more | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 219 | obra/superpowers | 2026-10-10 | An agentic skills framework & software development methodology that works. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 220 | sykim52/colgraphrag | 2026-07-21 | A query-conditioned multimodal reasoning pipeline that constructs question-speci… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 221 | ZhengPeng7/BiRefNet | 2026-10-11 | [CAAI AIR'24] Bilateral Reference for High-Resolution Dichotomous Image Segmenta… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 222 | Q00/ouroboros | 2026-10-12 | Agent OS: the agent gets smarter on its own. We just hold the line: Interview-ga… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 223 | Yeachan-Heo/oh-my-codex | 2026-10-12 | OmX - Oh My codeX: Your codex is not alone. Add hooks, agent teams, HUDs, and so… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 224 | Anil-matcha/Open-Generative-AI | 2026-10-11 | Unrestricted Open-source alternative to AI video platforms · Free AI image & vid… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 225 | QwenLM/Qwen3-TTS | 2026-03-17 | Qwen3-TTS is an open-source series of TTS models developed by the Qwen team at A… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 226 | msitarzewski/agency-agents | 2026-10-07 | A complete AI agency at your fingertips - From frontend wizards to Reddit commun… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 227 | microsoft/PowerToys | 2026-10-12 | Microsoft PowerToys is a collection of utilities that supercharge productivity a… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 228 | microsoft/ai-agents-for-beginners | 2026-10-12 | 18 Lessons to Get Started Building AI Agents | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 229 | Netflix/void-model | 2026-06-20 |  | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 230 | NousResearch/hermes-agent | 2026-10-12 | The agent that grows with you | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 231 | slopus/happy | 2026-10-11 | Orchestrate Claude, Codex and Grok in one app. Open-source (MIT), reuses the sub… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 232 | fivetaku/cc101 | 2026-09-24 | Claude Code 한국어 입문 가이드 / Korean Beginner Guide for Claude Code | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 233 | humantonylee/free-router | 2026-07-15 | The free AI model router, API for everyday AI work. Find the best option, compar… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 234 | NomaDamas/k-skill | 2026-10-10 | 한국인을 위한 스킬 모음집 - 에이전트를 한국인으로 | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 235 | affaan-m/ECC | 2026-10-12 | The agent harness performance optimization system. Skills, instincts, memory, se… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 236 | ultraworkers/claw-code | 2026-10-11 | An agent-managed museum exhibit, built in Rust with Gajae-Code / LazyCodex · dev… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 237 | garrytan/gstack | 2026-10-12 | Use Garry Tan's exact Claude Code setup: 23 opinionated tools that serve as CEO,… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 238 | bytedance/deer-flow | 2026-10-12 | An open-source long-horizon SuperAgent harness that researches, codes, and creat… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 239 | AlexsJones/llmfit | 2026-10-12 | Hundreds of models & providers. One command to find what runs on your hardware. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 240 | microsoft/VibeVoice | 2026-10-08 | Open-Source Frontier Voice AI | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 241 | SillyTavern/SillyTavern | 2026-10-02 | LLM Frontend for Power Users. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 242 | supertone-oss-archive/supertonic | 2026-09-09 | Lightning-Fast, On-Device, Multilingual TTS · running natively via ONNX. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 243 | openclaw/openclaw | 2026-10-12 | The AI that really does things. Any OS. Any Platform. The lobster way. 🦞 | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 244 | code-yeongyu/oh-my-openagent | 2026-10-12 | OmO: Just type "mass ulw" keyword with your prompt. Now you are the master of gr… | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 245 | codecrafters-io/build-your-own-x | 2026-07-14 | Master programming by recreating your favorite technologies from scratch. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 246 | ultralytics/ultralytics | 2026-10-12 | Ultralytics YOLO27, YOLO26, YOLO11, YOLOv8 · object detection, instance segmenta… | 뺌 · 비전 · 3D 재구성 · 생성 모델 (보행 정책 없음) |
| 247 | SKN19-3rd-4team/zip-fit | 2025-11-27 | 나에게 딱 맞는 집 zip-fit | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 248 | SKNetworks-AI19-250818/.github | 2025-12-09 |  | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |
| 249 | nari-labs/dia | 2025-11-19 | A TTS model capable of generating ultra-realistic dialogue in one pass. | 뺌 · 보행 · 지형 · 로봇 시뮬레이션과 무관 |

---

## 못 본 것

**star 단계**
- 「뺌」 223개는 GitHub 설명만 보고 뺐다. README 는 열지 않았다. 설명이 비었거나 짧은 것(예: `dreamurl/GPT-Bridge`, `Julian-adv/OpenMMO`, `Netflix/void-model`)은 README 를 열어 무관함을 확인했다.
- star 는 `gh api user/starred` 가 돌려준 것만 셌다. 비공개 저장소 star · star 목록(list) 기능은 보지 않았다.

**그래프 단계**
- 가지친 범위 밖 노드(휴머노이드 motion tracking · 조작 · 드론)의 링크는 펼치지 않았다. 그 안에 보행 방법 링크가 있을 수 있다. 펼치지 않은 노드: hop 3 의 pal_mjlab (설명 「PAL Robotics robots and tasks」 만으로는 보행 여부를 모르는데 열지 않았다) · mjlab_myosuite · in-hand-rotation-mjlab · wuji-mjlab · jumper, hop 5 의 pyroki · mink · SOMA-X, hop 6 의 PBHC · AMO · TWIST · GMT · FRoM-W1 · GMR, hop 7 의 expressive-humanoid · hugwbc · lipschitz 페이지.
- 기반 도구 노드(SDK · 드라이버 · 설명 파일 모음)의 링크 중 GitHub 저장소가 아닌 것과, robot_descriptions 류 목록의 개별 설명 저장소 수십 개는 열지 않았다.
- README · 논문에 이름만 있고 저장소 · 페이지 링크가 없는 방법은 따라가지 않았다: SoloParkour (REAL README 표 · 논문 Table I) · ANYmal Parkour · DTC · Learning agile locomotion on risky terrains (AME(v1) 참고문헌, 인용 그래프 몫).
- 프로젝트 페이지 밖 사이트: DIC 의 Google Sites (코드 · 부록이 있다고 각주에 적힘), HOMIE 등 논문 페이지.
- Gurukul 의 코드 파일은 읽지 않았다. 문서 사이트의 서술만 옮겼다.
- 저장소 위키 · 이슈 · 포크 · 「Used by」 는 보지 않았다.

**방법 단계**
- 3등급 C5 는 PDF 키워드 검색만, C8 은 arXiv 메타만, C9 ~ C11 은 README 머리만 봤다. 로봇 · 명령 · 시뮬 칸의 `미확인` 은 읽지 않아서다.
- 그림에만 있는 값: Extreme Parkour Fig. 7, Hiking Fig. 8, Humanoid Parkour Fig. 5, AME Fig. 6, DIC Fig. 4 의 성공률.
- AME(v1) 의 시뮬레이터 이름은 본문 전문 검색(`isaac` 등)으로 못 찾았다. 보충 자료 영상 · zenodo 데이터는 열지 않았다.
- REAL 의 student 가 heading 을 스스로 예측하는지 (`legged_robot.py` 미독), REAL SR 의 정의, 시행 수.
- Hiking 의 학습 gap 치수는 공개 코드 값만 봤다. 논문 학습 판과 같은지 미확인.
- 체크포인트 유무는 저장소 트리의 `.pt · .pth · .onnx · .jit · .ckpt` 파일로만 셌다. Hugging Face 등 외부에 올린 것은 찾지 않았다(README 에 링크가 있는 go2_rl_gym 류 제외).
- 어떤 저장소도 설치 · 실행하지 않았다. Isaac Gym 계열(REAL · Extreme Parkour · RPL · HIMLoco)이 우리 env(RTX 5080 sm_120 · torch 2.7.0+cu128, SURVEY 공통 표기)에서 도는지, Gurukul 의 Isaac Lab 0.54.3 · rsl-rl-lib 5.3.0 요구가 우리 0.54.2 · 3.1.2 와 맞는지는 `미확인`.
