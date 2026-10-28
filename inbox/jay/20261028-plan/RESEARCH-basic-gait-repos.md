> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: verifier · 2026-10-28
> 근거: 저자 공식 저장소의 고정 SHA·소스 행 · 공개 가중치 CPU 확인 · RESEARCH-basic-gait-list · PROVENANCE-START-vs-OURS
> 요지: Go2 공개 가중치 출발점은 SLR와 MoE-CTS가 구체적이다. START로 가중치를 바로 이어 읽는 길은 없으며, 보상·명령 이식은 가능하지만 공개 정책의 성능까지 따라오지는 않는다
> 상태: 제한 조사 완료 · 적용안은 미확정 · GPU·Kit·학습·실기 실행 없음 · 커밋/push 없음

# 기본 보행 공개 저장소와 START 이식 경로

**바로 사용할 수 있는 START 대체 저장본은 찾지 못했다.** SLR는 Go2용 encoder·actor 가중치가 실제로 내려받아지고 CPU에서 호출된다. MoE-CTS/RoboGauge는 Go2 학습·MuJoCo 평가·ONNX 배포물을 함께 공개한다. 둘은 기본 보행 teacher 후보이지만 START checkpoint와 호환되는 부모는 아니다. HIM은 공식 학습 코드가 명료하나 이 조사 SHA에는 Go2 설정과 가중치가 없다. Open-DiffLoco는 Go2 코드가 있지만 학습기와 물리 엔진까지 달라 우리 PPO에 보상만 가져오는 비용과 불확실성이 크다.

**요청한 두 쓰임 중 구현 거리가 짧은 것은 (b) START를 유지하고 보상·명령의 명세를 옮기는 길이다.** 다만 지금 포복·정지 문제가 그 보상으로 해결된다는 근거는 없다. (a)는 검증된 teacher를 확보한 다음 별도의 증류와 START 공동학습 연결이 필요한 새 학습 절차다. 이것을 기존 START 이어 학습과 동일하게 기록하면 안 된다.

## 1. 조사 범위와 고정 출처

2026-10-28 조회. 논문 저자 페이지가 연결한 저장소를 우선했다. 2023 DreamWaQ·Walk These Ways는 기간 밖 계보이고, 논문과 연결되지 않는 개인 Go2 포크는 공식 재현 후보로 늘리지 않았다. MOVE는 고유감각 전용이 아니라 깊이 카메라를 쓰는 지각 보행이다. 논문 공개, 학습 코드 공개, 추론 가중치 공개, 학습 재개용 checkpoint 공개를 구분한다. 공개 코드가 있다는 이유로 이 Windows/RTX 5080 환경에서 실행 검증됐다고 쓰지 않는다.

아래 H/S/D/R은 이 SHA의 파일을 뜻한다. 표의 행 번호는 웹 렌더 행이 아닌 실제 소스 행이다.

| 기호 | 공식 저장소·고정 SHA | 확인 범위 |
|---|---|---|
| H | [InternRobotics/HIMLoco](https://github.com/InternRobotics/HIMLoco/tree/ef289acaa62795009363b7b819c9186690630441), `ef289acaa62795009363b7b819c9186690630441` | README, Aliengo 설정·공통 환경, HIM actor·estimator, LICENSE, tree·release 목록 |
| S | [11chens/SLR-master](https://github.com/11chens/SLR-master/tree/8b454a142401ebcf87c33f26bb7b7dba7c0f7e6e), `8b454a142401ebcf87c33f26bb7b7dba7c0f7e6e` | Go2 설정·환경·모듈·play, encoder.jit·policy.jit, README 라이선스 |
| D | [MartinOpat/open-diffloco](https://github.com/MartinOpat/open-diffloco/tree/35256b6c8e243d658d6379ff8d17cde8e01d8211), `35256b6c8e243d658d6379ff8d17cde8e01d8211` | blind_nolinvel_nokinref 변형, network·config·배포 문서·LICENSE. 다른 변형과 보상을 섞지 않음 |
| R | [robogauge/code](https://github.com/robogauge/code/tree/f116b00a934262348f41cbfd0d07cc4cb6fbf8d8), `f116b00a934262348f41cbfd0d07cc4cb6fbf8d8` | go2_rl_gym MoE-CTS, RoboGauge·unitree_cpp_deploy, ONNX 파일 목록. 프로젝트는 RSS2026 표기의 익명 원고를 소개하며 채택 여부는 확인하지 않음 |

원자료 사본과 GitHub tree·release JSON: `C:/mai/wt/foothold-lab/verifier-27c-window/_out/gait_repos_1028/`. 선택 소스 98개와 추가 network·license 원문을 저장했다. 저장소 전체를 실행하거나 의존성을 설치하지 않았다.

## 2. 공개 코드와 가중치 비교

| 연구·연도 | 로봇·시뮬 | 실제 명령 계약·정지 | 신경망·공개 가중치 | 라이선스 원문·우리 로컬 실현성 |
|---|---|---|---|---|
| **HIM, ICLR 2024** | 공식 env는 A1·Aliengo·Go1. **Go2 없음**. Isaac Gym Preview 4 | 기본 vx·vy 각각 ±1, yaw 범위 ±3.14지만 `heading_command=True`라 yaw 직접 균등 표집과 다름. 10 s 재표집. 작은 xy 명령을 0으로 만드는 것과 yaw까지 0인 정지는 별개. H `legged_robot_config.py:70~80` | 비순환 actor MLP 512/256/128 + 6×45 history를 받는 HIM MLP. 속도 3 + latent 16, successor contrastive 학습. H `aliengo_config.py:34~40`, `him_actor_critic.py:74~110`, `him_estimator.py:15~68`. tree·release에서 공식 추론 가중치 미발견 | H 루트 LICENSE:1 CC BY-NC-SA 4.0, 하위 의존성 별도. README는 Ubuntu20.04·Python3.7·Torch1.10·Gym Preview4. 현재 Windows Isaac Lab에 바로 실행 불가. Linux 별도 환경 및 Go2 이식 필요. 옛 Torch의 RTX5080 지원은 미확인 |
| **SLR, CoRL 2024 / PMLR 2025** | **Go2 자산 포함**, Isaac Gym Preview4 | 초기 vx·vy ±0.5, heading 제어 yaw clip ±1. 명령 curriculum 최대 forward1.5/back1.0/lateral1.0. 10 s 재표집. xy norm≤0.2이면 xy 0, yaw는 heading 오차에서 생성. S `configs/go2_config.py:107~122`, `envs/legged_robot.py:553~556,1151`. 정지 전용 확률 계약은 없음 | 10×45 history → MLP256/128/64 → latent20, 현재45+latent20 → actor512/256/128 →12. transition model 포함, GRU 없음. **encoder.jit·policy.jit 실제 다운로드·CPU 호출 확인**. critic·optimizer 포함 재개 저장본은 tree에 없음 | S README:9 CC BY-NC4.0 선언, 일부 파일은 상속 BSD 헤더. 코드/자산별 고지 유지 필요. CPU 추론 가능 확인. Gym 학습은 별도 Linux 환경. `play.py:64`가 저장소에 없는 logs/.../model_10000.pt를 읽어 기본 예제를 그대로 실행할 수는 없음 |
| **Open-DiffLoco, 2026 preprint** | **Go2**, MuJoCo MJX/JAX. Isaac 계열 아님 | vx ±1.5, vy ±1, wz ±1.5. 각 성분 0 확률 0.1이 **독립**이므로 완전 정지는 계산상 0.001, 정지10%가 아님. D `.../blind_nolinvel_nokinref/environment.py:34~38,348` | 10-frame history, actor512/256/128 + LayerNorm/ELU, tanh12. SHAC/JAVE의 미분 시뮬 학습. `src/core/networks.py:9~28`. 해당 tree·release에서 checkpoint 미발견. export 경로는 있지만 가중치 제공과 다름 | D LICENSE.md:25~48,65~87은 자체 비상업·동일조건·소스 제공 조건. 현재 isaac311에 그대로 훈련 불가. JAX/MJX 환경 별도. CPU/Windows 성능과 RTX5080 학습은 미확인 |
| **MoE-CTS / RoboGauge, 2026 프로젝트 원고** | **Go2**, Isaac Gym 학습·MuJoCo 평가·C++/ONNX 배포 | heading=False, 초기 vx·vy ±0.5, wz±1.0, 5 s 재표집. zero-command 비율 0→0.1, 일부 zero 표집에 yaw 극값 부여. 이후 범위·지형별 상한. R `go2_rl_gym/.../go2_config.py:93~141`. zero 분류 전체가 완전 정지는 아님 | privileged teacher encoder + history student MoE(8 experts, latent32) + actor512/256/128. R `actor_critic_moe_cts.py:10~62,104~122`. **unitree_cpp_deploy/logs 안 policy.onnx 두 개 존재**. 이 조사에서 ONNX 추론·보행은 미실행. 학습 재개 checkpoint는 별도 확인 필요 | 학습/배포 각각 LICENSE:1 MIT, 하위 의존성 별도. Go2 추론 후보이나 Gym·MuJoCo wrapper와 관측 history가 필요. Isaac Lab로 직접 import해 실행하는 구조 아님. 실기 Orin 배포 소스 제공은 우리 실기 검증을 대신하지 않음 |
| **MOVE, 2024 preprint / ICRA2025** | 깊이+고유감각, Isaac Gym. 공개 코드 기준 Go2 여부 **미확인** | 앞·뒤·옆 기술의 논문 평가는 확인. 실행 표집기·정지 분모 미확인 | PS-Net pseudo-siamese·지각 기반 단일 정책. 논문·영상은 확인했으나 저자 공식 코드/가중치 링크를 찾지 못함 | 코드 라이선스·로컬 실행성 미확인. 재현 가능한 공개 출발점으로 추천하지 않음. [원문 §III·IV](https://arxiv.org/html/2412.03353v1) |
| **HAC-LOCO, 2025** | Go1, Isaac Gym | 논문 최대 vx±2,vy±1,wz±2; 정지 실기 사례는 있음. 실제 표집기·전용 정지 비중 미확인 | history AE+속도/힘 estimator+PPO 저수준, 이를 얼린 뒤 상위 compliance 학습. 공식 코드·가중치 미발견 | 논문 라이선스가 소프트웨어 사용 허가를 뜻하지 않음. 재현 코드를 자체 작성해야 하는 후보. [원문 §III·Table I](https://arxiv.org/html/2507.02447v1#S3) |
| **Proprioceptive Force Estimation, 2026 preprint** | Go1, Isaac Gym | 논문 planar curriculum vx±0.75→±1.5,vy±0.5→±1.0, 정지·적재·leash 구별. 실제 코드의 wz/정지 계약 미확인 | history에서 force·velocity·latent 추정과 정책 공동학습. 공식 코드·가중치 미발견 | 로컬 실행성·코드 라이선스 미확인. [원문 §III-B~F·IV-A](https://arxiv.org/html/2609.34222v1#S3) |

「미발견」은 저자 페이지·논문 링크, 해당 공식 tree·releases와 이름 검색 범위의 결과다. 인터넷 어디에도 존재하지 않는다고 단정하지 않는다. 특히 동명 GitHub 프로젝트를 논문 공식 구현으로 취급하지 않았다.

## 3. 실제 보상 항목과 원문 행

다음은 **학습 설정의 계수**다. episode 합계나 step 보상 실측이 아니다. H/S의 dt 곱·S의 양수 clip과 같은 소비 단계도 함께 봐야 한다. 단순 항목 존재가 아니라 활성 계수를 확인했다.

| 후보 | 활성 항목·설정값 | 식·가중치 원문 |
|---|---|---|
| H Aliengo 설정 | xy 추종1, yaw추종0.5, vz²−2, ωxy²−0.05, 자세−0.2, 관절가속−2.5e−7, 절대 기계전력−2e−5, 몸높이−1, foot_clearance−0.01, action변화−0.01, 2차변화−0.01. air_time·stand_still·torque² 등은 0. target높이0.30, 발의 몸기준 z target−0.20 | [aliengo_config.py:85~116](https://github.com/InternRobotics/HIMLoco/blob/ef289acaa62795009363b7b819c9186690630441/legged_gym/legged_gym/envs/aliengo/aliengo_config.py#L85). [legged_robot.py:1111~1165](https://github.com/InternRobotics/HIMLoco/blob/ef289acaa62795009363b7b819c9186690630441/legged_gym/legged_gym/envs/base/legged_robot.py#L1111): clearance는 몸기준 발 높이 제곱오차×몸기준 발 xy속력 합 |
| S Go2 설정 | H와 같은 xy1/yaw0.5,vz−2,ωxy−0.05,acc−2.5e−7,power−2e−5,action변화·2차변화 각−0.01. 몸높이−10(target0.32), clearance−0.5(target−0.22), 자세−0.2. torque²·air_time·collision·stand_still은0. 총보상 양수 clip 켬 | [go2_config.py:135~158](https://github.com/11chens/SLR-master/blob/8b454a142401ebcf87c33f26bb7b7dba7c0f7e6e/configs/go2_config.py#L135), base cfg:165~181 상속 대조. [legged_robot.py:1239~1332](https://github.com/11chens/SLR-master/blob/8b454a142401ebcf87c33f26bb7b7dba7c0f7e6e/envs/legged_robot.py#L1239); :914~919는 가중치 dt 곱. power=Σ|τ||qdot|, torque²와 다름 |
| D blind_nolinvel_nokinref | vx/vy/wz 각각 **음의 제곱오차**, 높이 exp(−10(h−0.3)²), vz²−0.5, upright 0.5(−gz), 기본관절오차²−0.3, action변화²−0.02, action²−0.05, ωxy²−0.05 | [environment.py:739~787](https://github.com/MartinOpat/open-diffloco/blob/35256b6c8e243d658d6379ff8d17cde8e01d8211/src/envs/go2/variants/blind_nolinvel_nokinref/environment.py#L739). START의 exponential 추종 보상과 형상부터 다르며, actor tanh와 미분 학습을 빼고 계수만 옮기는 것은 원 구현 재현이 아님 |
| R Go2 기본 설정 | xy1,yaw0.5,vz−2,ωxy−0.05,acc−2.5e−7,power−2e−5,torque²−1e−4,높이−1(target0.38),action변화·2차변화 각−0.01,collision−1,관절한계−2,feet_regulation−0.05,hip_to_default−0.05. 높이 배율1→10·vz배율1→0 curriculum 별도 | [go2_config.py:151~192](https://github.com/robogauge/code/blob/f116b00a934262348f41cbfd0d07cc4cb6fbf8d8/go2_rl_gym/legged_gym/envs/go2/go2_config.py#L151), [legged_robot.py:1381~1412](https://github.com/robogauge/code/blob/f116b00a934262348f41cbfd0d07cc4cb6fbf8d8/go2_rl_gym/legged_gym/envs/base/legged_robot.py#L1381). feet_regulation은 발 속도²와 높이 지수 결합. 지형·속도별 tracking_sigma도 변함 |

공개 구현을 찾지 못한 세 논문의 보상은 **코드 원문 행을 제시할 수 없다.** MOVE §III-A4, HAC-LOCO Table I, Force Estimation Table II·§III-F가 문헌 출처다. 이를 공개 실행 보상표로 바꿔 적지 않는다. HAC-LOCO의 상위 compliance 보상은 속도 명령 자체를 바꾸는 역할이므로 우리 저수준 정상 보행 보상에 그대로 추가할 항이 아니다.

## 4. (a) 공개 모델로 걷고 START로 옮기는 길

**구현 가능성: 조건부 가능. 직접 checkpoint resume는 불가.** SLR는 actor 입력65·출력12이고, HIM·MoE도 자기 history encoder의 latent 의미를 전제로 한다. START TR-Net·I-E·지도 토큰/선택·순환 상태와 같은 표현이 아니다. 출력12가 같거나 MLP 폭이 같다는 이유로 중간 가중치를 부분 복사해도 의미 호환은 생기지 않는다.

| 경로 | 얻는 것 | 막히는 곳·위험 |
|---|---|---|
| 공개 actor를 별도 기본 보행 정책으로 먼저 소비 | 학습 없이 teacher의 실제 Go2 동작을 점검할 수 있는 가능성. SLR 공개 JIT는 CPU 입력이 확인돼 가장 구체적 | 물리·관절 순서·기본 자세·PD·action_scale·history 순서·정규화·필터·시간간격 계약을 이식해야 함. SLR의 hip scale0.5·filter=True·Kp40/Kd1과 우리 actuator가 다르면 같은 action도 다른 동작. CPU 유한 출력은 정상 보행 증거가 아님 |
| teacher action을 START student에 증류 | 신경망 구조가 달라도 행동 target을 전달 가능. teacher와 student의 latent를 동일시할 필요 없음 | student rollout 상태에서 teacher를 질의하는 데이터 집계 등이 필요. teacher 궤적만 모사하면 오차 누적·넘어짐 회복 공백. 양쪽 raw action이 아닌 실제 관절 목표 계약을 먼저 맞춰야 함. 새 명령·지형에서 teacher가 못 걷는 영역은 증류로 해결되지 않음 |
| 증류 후 START의 TR/I-E/PPO/AdaSmpl 공동학습 | 본류 구조로 다시 연결할 수 있는 제안 | blind teacher의 행동만 맞추면 TR 지도 사용을 무시하는 해가 쉬움. reconstruction·I-E의 감독 목표와 AdaSmpl 보상분포가 바뀐다. teacher 사용을 끝내고 PRED-only에서 지도 필요 지형을 통과하는지는 별도 미확인. teacher critic·optimizer state를 START에 이어 읽을 수 없음 |

증류로 기본 보행을 얻는 길은 과학적으로 타당한 후보이나, START 논문의 처음부터 공동학습을 그대로 재현하는 경로는 아니다. 별도 출처·부모 계보로 기록해야 한다. teacher-student를 이미 사용하는 MoE-CTS도 **자기 privileged encoder에서 자기 history encoder로 옮기는 코드**이지, START로 옮기는 범용 converter가 아니다.

## 5. (b) START 신경망을 유지하고 보상·명령만 대입

**구현 가능성: 가능. 현재 목적과의 연결은 이쪽이 더 직접적이다.** 환경의 reward·command는 actor 구조와 별개로 정의할 수 있다. SLR/HIM의 정확 추종·몸높이·foot_clearance·전력·action 2차변화는 검토 가능한 명세다. 그러나 이름이 같은 함수를 선택하는 수준으로 끝내면 다른 실험이 된다.

- **명령:** HIM/SLR는 기본 heading controller다. 우리 yaw-rate 직접 명령·독립 회전·반전·정지재출발을 유지하려면 heading→yaw 소비를 그대로 복사할지 별도 결정이 필요하다. 범위에 0이 포함돼도 완전 정지 episode 비중과 같지 않다. R의 회차 기반 범위 확대는 우리 성과 기반 확대를 대체하지 않는다.
- **물리·좌표:** SLR foot_clearance의 음수 target은 지면 위 발 높이가 아니라 몸기준 z다. 몸높이 target0.32를 우리 reset root_z와 같은 값으로 읽으면 안 된다. PD·hip scale·필터·action clip까지 포함한 조건표가 있어야 기존 결과와 비교할 수 있다.
- **보상 크기:** τ²와 Σ|τqdot|는 물리량이 다르다. dt 곱, 합산 축, positive clipping, tracking_sigma 분모를 고정해야 한다. λ 이름·값만 가져오면 실효 균형이 달라진다. SLR에서 torque²=0이라는 사실은 우리 토크 벌점이 불필요하다는 근거가 아니다.
- **학습 결합:** START AdaSmpl은 episode reward 변동계수를 소비한다. 보상 상수·clip·합산 구조를 바꾸면 정책 gradient뿐 아니라 GT/PRED 표집도 바뀐다. 따라서 보상 교체는 학습 환경의 한 항만 독립적으로 바뀐 처치라고 단정할 수 없다.
- **보존할 본류:** 이식은 기본 보행 부분에 대한 대안이다. 연속7종 이후 sparse·foot_edge, 제한된 뒤/옆·정지·회전, TR/I-E/PPO/AdaSmpl 공동학습, 실기 PRED-only, 성과 기반 확대를 조용히 폐기할 근거가 아니다.

우리 대조 정본은 [PROVENANCE-START-vs-OURS.md](../20261025-experiments/PROVENANCE-START-vs-OURS.md) §1~3이다. 정확 추종은 이미 우리 설계이며 새로 SLR에서 발견한 차이로 세지 않는다. START 원문 보상·명령을 그대로 유지했다는 주장과 공개 보상 대입안은 분리해야 한다. 이 문서 §1의 JEPLO 「360°로 뒤를 직접 봄」은 이전 조사에서 지적했듯 정책 입력 FoV와 다르며 이번 추천 근거로 사용하지 않았다.

## 6. 직접 확인한 가중치와 실행 한계

S `encoder.jit` 645,345 bytes, SHA256 `6288e9967168be5b2ee6486a3a0cbd2997f861f4e77e9a01bbc108bc877174bf`; `policy.jit` 812,222 bytes, SHA256 `26b96650c969ad13fb07c11049e359e853822ba55879bac68536d63388fb382d`. ZIP 안 TorchScript 코드를 먼저 확인하고 isaac311·Torch2.7.0+cu128에서 **map_location=cpu**, CUDA 숨김으로 로드했다. encoder zero(1,450)→(1,20), actor zero(1,65)→(1,12), 모두 유한. 영수증 `.../_out/gait_repos_1028/slr_cpu_receipt.json`. 합성 0입력은 관측 차원·런타임 호환 시험이지 물리 상태나 보행 평가가 아니다.

R의 공개 ONNX는 `unitree_cpp_deploy/logs/rsl_rl/go2_moe_cts_expert_goal_137000_0.6745/exported/policy.onnx`와 `go2_moe_cts_fast_flat_v4_fz_54k/exported/policy.onnx`다. 파일 이름의 회차·성능 표기를 독립 실측으로 받아들이지 않았다. H·D는 tree 및 release에서 배포 가중치를 확인하지 못했으므로 「코드만으로 바로 기존 모델을 실행」 후보가 아니다.

**남은 미확인:** 공개 정책의 우리 Go2 물리에서의 보행, RTX5080에서 옛 Gym 학습 지원·처리량, 각 가중치의 정확한 학습 설정·seed·원자료 대응, START로 증류한 성능, 라이선스가 적용되는 배포 산출물의 구체적 범위. 이 조사로 새 학습·설치·실기 실행을 승인하지 않는다.
