> 분류: 리서치
> 작성: 오흥재 · 2026-09-21
> 근거: **조사는 codex `gpt-6-astra` 세션(웹검색 live · 자기 재검증 2 회)이 수행했고 본 문서는 그 산출물이다.** 아래 「읽은 원자료」의 프로젝트 페이지 · 논문 PDF · 저자 가이드 · 공개 저장소 및 구현 파일. 우리 수치는 [작업서 0절](BRIEF-codex-astra.md#0-왜-이-조사를-하나)만 사용.
> 요지: MARG와 AME-2는 희소 발판을 직접 다루지만, HiPAN은 주로 항법과 자세 조절 연구다. 우선 관측 노이즈·누락과 학습 난도를 분리해 확인하고, 이후 지형 인코더와 기억을 비교할 것을 제안한다. 세 방법 모두 기존 가중치에 그대로 덧붙여 논문 성능을 얻는 방법은 아니다.
> 상태: 초안
> 판: v1.0

# 지각 논문 정밀 조사 · MARG · HiPAN · AME-2

## 1. 한 장 요약

`확인됨`은 원자료에서 확인했다는 뜻이며, 우리가 재현했다는 뜻이 아니다. 적용 판단은 `추정`, 원문에 없는 사양은 `논문에 없음`, 구현·성능을 확인하지 못한 것은 `미확인`으로 표시한다. 표의 수치는 별도 표시가 없으면 논문의 보고값이다. 논문끼리 로봇·지형·성공 판정이 달라 성공률을 직접 순위로 비교하지 않는다.

| 연구 | 실제로 해결하는 문제 | 핵심 구조 | 현재 문제와의 관계 · 적용 판단 |
|---|---|---|---|
| MARG | 좁은 보·돌·틈에서 발을 놓고 실기 높이맵 드리프트를 줄이는 문제 | 높이맵 MLP, 이력 기반 속도·접촉 추정, 비대칭 actor-critic, 발 보상, LiDAR 지도 | `추정` 직접 관련. 현재도 높이맵을 보는 우리 정책과 비교하려면 보상·특권관측·기억을 분리해야 한다. 어텐션 필요성을 입증하는 논문은 아니다. [M-P §II·III·V](https://arxiv.org/pdf/2509.20036v2) |
| HiPAN | 막다른 길 탈출, 장거리 목표 도달, 낮은 통로에서 몸높이·roll 조절 | 상·하위 정책, 각각 교사-학생, 깊이 CNN·GRU, 경로 기반 커리큘럼 | `추정` 미세 발판 문제에는 직접 관계없음. 저수준 학생은 지형을 직접 보지 않는다. 항법 단계에서 검토할 대상. [H-P §IV·V](https://arxiv.org/pdf/2604.26504v1) |
| AME-2 | 희소 발판과 오르기 동작의 결합, 가림·노이즈 아래 미경험 지형 일반화 | CNN·전역 특징·다중헤드 어텐션, 불확실성 지도와 시간 융합, 교사-학생 RL | `추정` 직접 관련. 인코더 부분 실험은 가능성이 있지만 전체 시스템 재현은 현재 한 판 예산에 맞지 않는다. [A-P §IV·V·VII](https://arxiv.org/pdf/2601.08485v2) |

우리 기준은 입력 **235**, 총 **571,801** 파라미터, `rsl_rl ActorCritic`, 높이 관측 **187**, 격자 간격 **0.1 m**, 균일 노이즈 **±0.1 m**, 기억 없음이다. 이는 작업서의 주어진 조건이며 체크포인트를 새로 측정하지 않았다. GPU **둘**, 한 판 **95~190분**은 작업서 3절의 예산이다. [작업서 0·3절](BRIEF-codex-astra.md)

`추정` 공간 간격, 높이 오차, 누락값 처리, 보상, 탐색 난도가 모두 후보 원인이다. 지형 특징 폭과 높이 오차가 비슷하다는 사실만으로 동일한 물리량의 신호 대 잡음비처럼 취급할 수 없다. 특히 작업서의 stepping_stones 값은 **돌 사이 간격**이므로 돌 윗면 폭으로 바꾸어 읽으면 안 된다. [작업서 0절](BRIEF-codex-astra.md#0-왜-이-조사를-하나)

### 읽은 원자료

아래는 본문 근거로 사용한 원문 URL이다. 검색 결과의 재서술과 비공식 논문 복사본은 근거로 삼지 않았다. 논문 링크의 `#page=`는 PDF 쪽수이며 학술지 쪽수와 다르다.

| 기호 | 직접 연 자료 · 확인 위치 |
|---|---|
| M-W | [MARG 프로젝트](https://astrorix.github.io/MARG/) · Abstract, Extreme Terrain, Success Rate, BibTeX |
| M-P | [MARG PDF v2](https://arxiv.org/pdf/2509.20036v2) · 본문·표·그림·참고문헌. 다운로드 시작 주소는 [버전 없는 PDF](https://arxiv.org/pdf/2509.20036)였고 파일 첫 쪽에서 v2 확인 |
| M-S | [MARG 실기 성공률 표 이미지](https://astrorix.github.io/MARG/static/images/succ_tab.png) · 프로젝트 Success Rate의 표를 직접 열어 판독 |
| M-C | [MARG 저장소](https://github.com/Astrorix/MARG) · [README 원문](https://raw.githubusercontent.com/Astrorix/MARG/master/README.md), [파일 목록 API](https://api.github.com/repos/Astrorix/MARG/git/trees/master?recursive=1), [저장소 메타데이터](https://api.github.com/repos/Astrorix/MARG) |
| H-W | [HiPAN 프로젝트](https://sgvr.kaist.ac.kr/~Jeil/project_page_HiPAN/) · Framework, Simulation Results, Real-World Validation, BibTeX |
| H-P | [HiPAN PDF v1](https://arxiv.org/pdf/2604.26504v1) · 본문·표·그림·참고문헌. [동일 버전 HTML](https://arxiv.org/html/2604.26504v1)도 대조 |
| A-W | [AME-2 프로젝트](https://sites.google.com/leggedrobotics.com/ame-2) · 논문 링크, 방법 도해, Tuning Guide 링크 |
| A-P | [AME-2 PDF v2](https://arxiv.org/pdf/2601.08485v2) · 본문과 부록 A~D. [동일 버전 HTML](https://arxiv.org/html/2601.08485v2)도 확인 |
| A-G | [저자 Chong Zhang의 Practical Tuning Guide](https://github.com/zita-ch/techblogs/blob/main/2026-03-28-AME%20Tuning%20Guide.md) · [원문](https://raw.githubusercontent.com/zita-ch/techblogs/main/2026-03-28-AME%20Tuning%20Guide.md), 코드 공개 계획과 AME 구조·학습 조언 |
| A-C | [독립 재현 AME_Locomotion](https://github.com/SII-FUSC/AME_Locomotion) · [README](https://raw.githubusercontent.com/SII-FUSC/AME_Locomotion/main/README.md), [actor_critic_encoder.py](https://raw.githubusercontent.com/SII-FUSC/AME_Locomotion/main/rsl_rl/rsl_rl/modules/actor_critic_encoder.py), [파일 목록](https://api.github.com/repos/SII-FUSC/AME_Locomotion/git/trees/main?recursive=1), [메타데이터](https://api.github.com/repos/SII-FUSC/AME_Locomotion) |
| S-P | [START 서지](https://arxiv.org/abs/2512.13153) · [PDF v1](https://arxiv.org/pdf/2512.13153v1), 특히 §II·III와 Table II |
| E-P | [AME 선행논문 서지](https://arxiv.org/abs/2506.09588) · [PDF](https://arxiv.org/pdf/2506.09588), Results D와 Materials and Methods, Supplementary Methods |
| R-P | [MetaLoco 서지](https://arxiv.org/abs/2407.17502) · [PDF v2](https://arxiv.org/pdf/2407.17502v2), §IV-B·Table III~V |
| J-P | [Agile Continuous Jumping 서지](https://arxiv.org/abs/2409.10923) · [PDF](https://arxiv.org/pdf/2409.10923), §IV·VII·VIII와 Table I |

## 2. MARG

### 논문에서 확인한 것

| 요구 항목 | 조사 결과 · 출처 |
|---|---|
| 정식 제목 · 저자 · 소속 · 연도 · arXiv | **MARG: MAstering Risky Gap Terrains for Legged Robots with Elevation Mapping**. Yinzhao Dong, Ji Ma, Liu Zhao, Wanyue Li, Peng Lu. HKU 기계공학과 Adaptive Robotic Controls Lab. **2025**, **2509.20036v2**. [PDF 첫 쪽](https://arxiv.org/pdf/2509.20036v2#page=1), [프로젝트 BibTeX](https://astrorix.github.io/MARG/) |
| 한 문장 요지 | 높이맵·자기상태 이력·발 보상을 함께 학습하고 접촉을 이용한 LiDAR 지도로 실기에서 안전한 발판을 찾는다. [§II·III](https://arxiv.org/pdf/2509.20036v2#page=3) |
| 관측 구조 | 본체 각속도·중력·속도명령·관절 위치/속도·이전 행동과 이력, 높이맵 **187차원**, 몸통 중심 **1.6×1.0 m**. actor는 현재 본체 관측과 추정 속도·접촉 **7차원**, 지형 잠재 **16차원**을 받는다. 입력 합계는 독립된 총수로 **논문에 없음**. `식의 차원 직접 합산` 현재 자기관측 **45**, actor MLP 입력 **68**, critic MLP 입력 **103차원**이다. 이 수치는 원문 구성요소 합산이며 공개 구현의 tensor를 확인한 값은 아니다. 시뮬레이션 지형맵과 실기 Mid360 LiDAR 기반 높이맵 사용. 정확한 격자 배열·정책 지도 간격은 **논문에 없음**. [§II-A·B, 식 (1)~(5)](https://arxiv.org/pdf/2509.20036v2#page=3) |
| 갱신률 · 노이즈 | Mid360 **10 Hz**, 정책·추정·elevation mapping network 동기 **50 Hz**라고 §IV-B에 명시. 별도로 Fig. 2(b), Fig. 10과 §V-G의 TMG 지도 갱신은 **100 Hz**로 표시한다. 같은 처리단계라고 단정할 수 없는 서술 차이가 있다. 지형맵 훈련 노이즈 **[-5,5) cm**. [§IV-B·Table II](https://arxiv.org/pdf/2509.20036v2#page=8), [Fig. 10](https://arxiv.org/pdf/2509.20036v2#page=12) |
| 신경망 구조 | actor·critic MLP 은닉 **512·256·128**, 출력 각각 **12·1**. Elevation MLP의 층 폭은 **128·64·16**, Estimator MLP는 원문 그대로 **258·128·7**, 두 보조망 활성화는 ReLU. 전체 파라미터 수는 **논문에 없음**. CNN·어텐션 구조가 아니다. Fig. 2(c)는 두 보조망 폭을 뒤바꿔 표시한 듯하여 Fig. 2(a)와 §IV-A를 기준으로 기록했다. [Fig. 2](https://arxiv.org/pdf/2509.20036v2#page=4), [§IV-A](https://arxiv.org/pdf/2509.20036v2#page=8) |
| 학습 방식 | 비대칭 actor-critic 기반 **단일 단계 PPO 동시 학습**, 별도 교사-학생 증류가 아니다. 추정망에 속도·접촉 MSE 보조 손실. critic 특권관측은 실제 선속도, 접촉, 링크 질량, 마찰, 질량중심, 외력, 제어이득·모터 세기·오프셋. [§II-A·B, 식 (1)·(5)·(6)](https://arxiv.org/pdf/2509.20036v2#page=3) |
| 잠재 표현 | 높이맵을 MLP로 **16차원** 지형 특징으로 압축하고 정책 학습 신호를 받는다. 추정 **7차원**은 선속도와 발 접촉으로 의미가 정해진 값이므로 순수한 비지도 잠재변수와 구분한다. [§II-B](https://arxiv.org/pdf/2509.20036v2#page=3) |
| 기억 | 자기상태 이력에 **H=5** 명시. 다만 `[o_t,…,o_{t-H}]` 식은 현재 포함 시 **6개**를 뜻하므로 실제 스택 길이는 코드 없이 확정 못 한다. 정책 GRU/LSTM은 제시하지 않는다. 실기 지도에는 접촉 기반 Kalman 추정과 누적 지도 상태가 있다. [§II-A·III](https://arxiv.org/pdf/2509.20036v2#page=3) |
| 실기 검증 | Go1·Go2, 실기 보 폭 최소 **9 cm**, 다리 폭 최소 **18 cm**, 틈 최대 **65 cm**. Go1 실험의 다리는 별도로 **20 cm**라고 명시된다. 도메인 무작위화와 TMG로 zero-shot 이전. 논문 본문에 지형별 실기 반복 성공률 표는 **논문에 없음**. 프로젝트 표에는 narrow balance beams **3/5=60%**, outdoor single gap **4/5=80%**, single plank bridge **2/5=40%**가 있다. 이 수치를 논문 표라고 부르지 않는다. [Fig. 1](https://arxiv.org/pdf/2509.20036v2#page=1), [§V-G·H](https://arxiv.org/pdf/2509.20036v2#page=13), [프로젝트 성공률 표](https://astrorix.github.io/MARG/static/images/succ_tab.png) |
| 보고된 정량 이득 | Table IV의 **700 time steps** 속도 추정 평균 제곱오차: MARG **0.229±0.029**, MorAL **0.270±0.074**, DreamWaQ **0.304±0.012**. `직접 계산` 각각 약 **15.2%**, **24.7%** 오차 감소다. 성공률 %p가 아니며, 우리 기준선 대비도 아니다. 관측·보상 성공률 ablation은 Fig. 7·8의 그래프이고 정확한 차이를 숫자로 전사하지 않았다. [Table IV·§V-C·D](https://arxiv.org/pdf/2509.20036v2#page=10) |
| 코드 공개 여부 | 프로젝트 Code는 “Comming Soon”. 공식 [Astrorix/MARG](https://github.com/Astrorix/MARG)의 master에는 README·프로젝트 웹 정적 파일이 있으며 학습 Python 코드는 확인되지 않는다. 저장소 전체 라이선스 파일도 확인 못 함. **Isaac Gym 사용은 논문 확인**, IsaacLab 또는 legged_gym 기반 구현이라고 확정할 공개 코드 없음. [§IV-A](https://arxiv.org/pdf/2509.20036v2#page=7), [공식 파일 목록](https://api.github.com/repos/Astrorix/MARG/git/trees/master?recursive=1) |
| 계산 비용 | **A100 GPU 한 장**, 환경 **4,096**, 훈련 약 **12시간**, GPU 메모리 약 **12 GB**. §IV-A는 **20,000 episodes**, Fig. 5·8은 **6,000 episodes** 비교 실험으로 적는다. 서로 다른 문맥이며 PPO iteration 수와 동일시하지 않는다. 명확한 iteration 수는 **논문에 없음**. [§IV-A·Fig. 5](https://arxiv.org/pdf/2509.20036v2#page=8), [Table III](https://arxiv.org/pdf/2509.20036v2#page=9) |

### 우리에게 붙일 때의 판정

| 기법 | (가) 변경 범위 | (나) 사전학습 가중치 | (다) 예산 | (라) 작은 특징에 닿는가 |
|---|---|---|---|---|
| 발 stumble·air time·center 보상 | `추정` 망·관측을 유지하면서 보상과 학습 지형을 바꿀 수 있다. | 동일 입력·행동 규약이면 기존 가중치에서 추가학습 가능. 성능 유지는 미확인. | 전체 MARG보다 작은 실험이지만 소요시간 미측정. | 직접 관련. 다만 낮은 턱에 원문의 절벽 판정을 그대로 쓰면 작동하지 않을 수 있다. [§II-C](https://arxiv.org/pdf/2509.20036v2#page=5) |
| 지형 MLP·상태 추정 이력 | `추정` 관측 경로와 망 구조, 추정 보조손실·학습 코드를 변경해야 한다. | 원래 첫 층을 완제품에 그대로 로드 불가. 부분 초기화나 증류는 별도 설계. 전부 무작위 초기화만 가능한 것은 아니다. | 원논문 전체 훈련은 예산 초과. 작은 모듈의 추가학습은 미확인. | 직접 관련이나 관측에 없는 지형 정보를 MLP가 되살린다고 보장하지 않는다. [§II-B·IV-A](https://arxiv.org/pdf/2509.20036v2#page=3) |
| critic 특권관측 | `추정` actor는 유지할 수 있지만 critic 입력과 학습 절차가 달라진다. | actor 가중치 보존 가능. critic 첫 층은 별도 확장·초기화 필요. | 단독 ablation 비용 미측정. | 탐색·가치 추정을 돕는 간접 기법. actor 지각 해상도를 올리지는 않는다. [식 (5)](https://arxiv.org/pdf/2509.20036v2#page=4) |
| TMG | `추정` 실기 지도·상태 추정 모듈 변경. 출력 규약을 맞추면 정책 입력 차원을 유지할 여지는 있다. | 차원뿐 아니라 높이 기준·좌표계·정규화 일치가 필요하다. | 지도 구축 개발·실기 비용은 논문 훈련시간으로 산정 불가. | 좁은 보의 지도 품질과 직접 관련. 현재 시뮬레이션 raycast 실패 원인에 대한 검증과는 다른 단계다. [§III](https://arxiv.org/pdf/2509.20036v2#page=5) |

`확인됨` MARG의 feet-center는 발 주변 높이를 **-0.2 m**와 비교한다. 따라서 우리 낮은 rails를 똑같이 절벽으로 검출할 것이라고 기대하면 안 된다. 원논문도 보상 제거 실험에서 stumble의 영향이 가장 크고 center의 영향은 상대적으로 작다고 보고한다. `추정` 보상 하나를 만능 해법으로 고르기보다 관측·보상 기여를 나눠 시험해야 한다. [식 (7)](https://arxiv.org/pdf/2509.20036v2#page=5), [§V-D](https://arxiv.org/pdf/2509.20036v2#page=11)

## 3. HiPAN

### 논문에서 확인한 것

| 요구 항목 | 조사 결과 · 출처 |
|---|---|
| 정식 제목 · 저자 · 소속 · 연도 · arXiv | **HiPAN: Hierarchical Posture-Adaptive Navigation for Quadruped Robots in Unstructured 3D Environments**. Jeil Jeong, Minsung Yoon, Seokryun Choi, Heechan Shin, Taegeun Yang, Sung-eui Yoon. KAIST School of Computing. **2026**, **2604.26504v1**. [PDF 첫 쪽](https://arxiv.org/pdf/2604.26504v1#page=1), [프로젝트](https://sgvr.kaist.ac.kr/~Jeil/project_page_HiPAN/) |
| 한 문장 요지 | 경로 안내를 점차 줄이는 학습으로 깊이 영상 기반 상위 항법을 익히고, 하위 정책이 속도·몸높이·roll 명령을 실행한다. [§IV](https://arxiv.org/pdf/2604.26504v1#page=3) |
| 관측 구조 | 하위 자기관측: 관절 위치·속도, 발 위치·접촉, roll/pitch, 각속도, 이전 행동. 명령은 **5차원**, 속도와 몸높이·roll. 상위 교사는 **14×11×11** 점유지도와 **31×21** 높이지도, 지도 간격 **0.1 m**를 사용한다. 상위 학생은 전방 깊이 **180×320**, 자기상태·이전 명령·추정 운동상태·상대 목표를 사용한다. 지도 물리 범위의 전체 축별 수치는 **논문에 없음**. 하위 교사의 높이맵은 Fig. 3에 x·y **[-2,2] m**. [§IV-B3·C3, Fig. 3](https://arxiv.org/pdf/2604.26504v1#page=3) |
| 입력 총차원 · 갱신률 | 시스템 전체 입력을 한 벡터로 합한 차원은 **논문에 없음**. 하위 **50 Hz**, 상위 **10 Hz**, 깊이 관측은 최대 **4 m**에서 잘라 정규화. 카메라 자체의 독립 촬영률은 **논문에 없음**. [§IV-D](https://arxiv.org/pdf/2604.26504v1#page=5) |
| 신경망 구조 | 하위 backbone MLP, 교사 지도 인코더 2D CNN·MLP, 학생 이력 추정기 MLP. 상위 교사는 3D·2D CNN 지도 인코더, 상위 학생은 깊이 2D CNN·GRU, 이후 MLP backbone. 정확한 은닉 폭·GRU 크기·파라미터 수는 **논문에 없음**. [Fig. 3, §IV-B3·C3](https://arxiv.org/pdf/2604.26504v1#page=3) |
| 학습 방식 | 하위 교사 PPO와 학생 DAgger, 이어 상위 교사 PPO와 학생 DAgger. 구조상 **네 학습 단계**. 하위 특권정보는 높이맵·질량·마찰 등 domain 변수와 실제 운동상태. 상위 교사는 지도·운동상태와 특권 경로의 중간 목표를 사용한다. 학생 손실에는 행동과 교사 잠재·상태 추정 정렬이 포함된다. [§IV-B·C, 식 (3)·(6)](https://arxiv.org/pdf/2604.26504v1#page=3) |
| 잠재 표현 | 하위 domain 잠재 **32차원**, 상위 공간 지각 잠재 **32차원**. 교사 PPO로 표현을 학습하고 학생은 DAgger 회귀 손실로 교사 표현을 맞춘다. [§IV-B3·C3](https://arxiv.org/pdf/2604.26504v1#page=5) |
| 기억 | 하위 domain 추정은 자기관측 **50스텝**, 운동상태 추정은 **10스텝** 이력. 상위 학생은 GRU recurrent memory. GRU 학습 unroll 길이·유효 기억 시간은 **논문에 없음**. [§IV-B3](https://arxiv.org/pdf/2604.26504v1#page=3), [§IV-C3·Fig. 3](https://arxiv.org/pdf/2604.26504v1#page=5) |
| 실기 검증 | Unitree Go1·RealSense D435i·Intel NUC. 실내 장애물, 막다른 복도, 조명 변화, 야외 햇빛과 미경험 장애물. 도메인 무작위화, 깊이 지우기·blur·가산잡음·카메라 위치 변화, 실기 hole filling 사용. 반복 실기 성공률·분모는 **논문에 없음**. [§IV-D·V-D, Fig. 6](https://arxiv.org/pdf/2604.26504v1#page=7) |
| 보고된 정량 이득 | 시뮬레이션 Table IV의 Corridor/Room/Complex-1/Complex-2 성공률은 **98.5/98.4/94.4/94.7%**. Flat-RL은 **82.0/43.8/45.3/43.7%**. `직접 계산` 환경별 **+16.5/+54.6/+49.1/+51.0%p**. 네 환경 단순평균은 **96.5% 대 53.7%, +42.8%p**. 환경별 **300개** 과제, **10 seeds**. 미세 발판 성공률이나 실기 성공률이 아니다. [§V-A·Table IV](https://arxiv.org/pdf/2604.26504v1#page=6) |
| 코드 공개 여부 | 프로젝트와 PDF에 공식 코드 링크가 없고, 제목·저자·GitHub 조합 검색에서도 공식 학습 저장소를 확인하지 못했다. 공개 안 됐다고 단정하지 않는다. URL·라이선스 **미확인**. Isaac Gym은 논문에 명시, IsaacLab/legged_gym 기반인지는 **미확인**. [프로젝트](https://sgvr.kaist.ac.kr/~Jeil/project_page_HiPAN/), [§IV-D](https://arxiv.org/pdf/2604.26504v1#page=5) |
| 계산 비용 | **RTX 4090 한 장**. 하위 교사 **4,096 env·12시간**, 하위 학생 **300 env·2시간**. 상위 교사 **1,024 env·18시간**, 상위 학생 **128 env·6시간**. `직접 계산` 전체 순차 시간 **38시간**. iteration 수는 **논문에 없음**. [§IV-D](https://arxiv.org/pdf/2604.26504v1#page=5) |

### 우리에게 붙일 때의 판정

| 기법 | (가) 변경 범위 | (나) 사전학습 가중치 | (다) 예산 | (라) 작은 특징에 닿는가 |
|---|---|---|---|---|
| 상위 항법·PGCL | `추정` 상위 망·목표 생성·경로 커리큘럼·교사-학생 학습을 추가한다. | 기존 속도 정책을 하위에 둘 수는 있으나 논문의 자세 적응 기능까지 재현하지는 못한다. | 상위만도 보고 시간이 예산을 넘는다. | **직접 관계없음**. 막다른 길과 목표 도달 문제를 푼다. [§IV-C·D](https://arxiv.org/pdf/2604.26504v1#page=4) |
| 하위 자세 적응 | `추정` 명령·자기관측·추정기·보상·증류 절차 변경. | 기존 관측과 명령 의미가 달라 그대로 이어받지 못한다. 부분 이전은 별도 검증 필요. | 전체 하위 훈련도 예산 초과. | **직접 관계없음**. 몸높이·roll 적응이 작은 발판 분해능을 높이지 않는다. [§IV-B](https://arxiv.org/pdf/2604.26504v1#page=3) |
| 이력 추정기·GRU 아이디어 | `추정` 독립적으로 시험할 수 있으나 망 구조·관측 버퍼를 수정해야 한다. | 기존 MLP를 남기는 보조 경로는 가능하지만 HiPAN의 검증 결과가 아니다. | 소규모 실험 비용 미측정. | 간접 관련. 발 아래 가림과 동역학 추정에는 가능성이 있지만, 이 논문은 우리 지형에 대한 개선을 보이지 않았다. [Fig. 3·§IV-B3](https://arxiv.org/pdf/2604.26504v1#page=3) |

`확인됨` 상위 교사가 쓰는 높이맵 간격도 **0.1 m**다. 이를 우리 격자보다 정밀한 발판 감지 연구로 소개하면 잘못이다. 하위 학생이 교사 지형 특징을 자기상태 이력에서 추정한다는 점도, 앞쪽 미세 지형을 센서로 직접 본다는 주장과 다르다. [§IV-B3·C3](https://arxiv.org/pdf/2604.26504v1#page=5)

## 4. AME-2

### 논문에서 확인한 것

| 요구 항목 | 조사 결과 · 출처 |
|---|---|
| 정식 제목 · 저자 · 소속 · 연도 · arXiv | **AME-2: Agile and Generalized Legged Locomotion via Attention-Based Neural Map Encoding**. Chong Zhang, Victor Klemm, Fan Yang, Marco Hutter. ETH Zurich Robotic Systems Lab, Zhang은 Secure, Reliable, and Intelligent Systems Lab 및 ETH AI Center도 표기. **2026**, **2601.08485v2**. [첫 쪽](https://arxiv.org/pdf/2601.08485v2#page=1) |
| 한 문장 요지 | 국소 발판 특징과 전역 지형 문맥을 함께 보는 어텐션 정책에, 깊이로 만든 불확실성 지도를 연결해 희소·혼합 지형을 일반화한다. [§IV-A·V](https://arxiv.org/pdf/2601.08485v2#page=4) |
| 관측 구조 | 교사는 자기상태와 점별 **(x,y,z)**, 학생은 선속도를 제외한 자기상태 이력과 **(x,y,z,u)** 지도를 받는다. ANYmal-D 정책 지도 **36×14**, TRON1 **18×13**, 모두 **8 cm** 간격. 중심은 각각 몸통 x **0.6 m**, **0.32 m**. 전체 평탄화 입력 총차원은 **논문에 없음**. 목표 명령은 위치·방향 계열이며 우리 속도명령과 다르다. [§III-B·IV-A·IV-E](https://arxiv.org/pdf/2601.08485v2#page=8) |
| 지도 해상도 · 물리 크기 | neural mapping 입력은 ANYmal-D **51×31**, TRON1 **31×31**, **4 cm** 간격. 정책의 **8 cm** 지도와 구분해야 한다. 축별 물리 폭의 직접 표기는 **논문에 없음**. `계산` 점 중심 간 범위를 (N-1)Δ로 해석하면 정책 지도 **2.80×1.04 m / 1.36×0.96 m**, mapping 입력 **2.00×1.20 m / 1.20×1.20 m**다. 셀 외곽 폭 NΔ와는 다르다. [§IV-E1·V-B3](https://arxiv.org/pdf/2601.08485v2#page=10) |
| 갱신률 · 센서 | 정책 **50 Hz**, 실기 PD **400 Hz**. ANYmal-D는 전방 깊이 카메라 **둘**, TRON1은 **하나**. mapping CPU 처리 약 **5 ms/frame**, 그중 망 추론 약 **2.5 ms**. 카메라 촬영률은 **논문에 없음**. 처리시간의 역수를 실제 센서 갱신률로 쓰지 않는다. LiDAR는 지도 융합용 odometry에도 사용한다. [§III-B](https://arxiv.org/pdf/2601.08485v2#page=4), [§V-C](https://arxiv.org/pdf/2601.08485v2#page=10) |
| 신경망 구조 | actor는 자기상태 인코더, 지도 CNN·위치 MLP·pointwise MLP, MLP+max-pool 전역 특징, 상태·전역 특징을 query로 하는 MHA, 행동 MLP. critic은 MoE. mapping은 gated residual 얕은 U-Net. 정책 은닉 폭·전체 파라미터 수는 **논문에 없음**. [Fig. 3·8, §IV-A·B](https://arxiv.org/pdf/2601.08485v2#page=5) |
| 논문 밖 구현 보충 | 저자 가이드에서 AME-2 MHA **32 heads·총 96차원**, critic **16 MLP experts**를 확인했다. 논문에 있는 전체 잠재 차원으로 오인하지 않는다. [저자 가이드 AME-2 Policy Learning, Step 3](https://github.com/zita-ch/techblogs/blob/main/2026-03-28-AME%20Tuning%20Guide.md) |
| 학습 방식 | privileged teacher PPO 후 student PPO+행동 증류+지도 표현 MSE. controller는 **두 단계**이며 별도로 mapping 감독학습을 한다. critic은 잡음 없는 자기상태·정답 지도·링크 접촉상태를 받는다. mapping은 합성 지형의 정답 높이·불확실성 학습으로 β-NLL 사용. [§IV-B·C](https://arxiv.org/pdf/2601.08485v2#page=6), [§V-B](https://arxiv.org/pdf/2601.08485v2#page=10) |
| 잠재 표현 | local attention 결과와 global 특징을 합친 지도 embedding이 있다. 전체 embedding 차원은 **논문에 없음**. 교사에서는 RL, 학생에서는 RL·행동 증류 및 교사 지도 embedding MSE로 학습한다. `u`는 점별 불확실성이며 압축 지형 latent가 아니다. [§IV-A·C, Fig. 3](https://arxiv.org/pdf/2601.08485v2#page=5) |
| 기억 | 학생은 선속도·명령을 제외한 자기상태 **20스텝**을 LSIO로 인코딩하고 명령을 결합한다. 추가로 odometry 기반 누적 지도에 공간 기억이 있다. 정책을 GRU/LSTM이라고 서술하지 않는다. SRU는 mapping 비교 기준선에 쓰인 구조다. [§IV-A](https://arxiv.org/pdf/2601.08485v2#page=5), [§V-A·Appendix D](https://arxiv.org/pdf/2601.08485v2#page=18) |
| 실기 검증 | ANYmal-D와 LimX TRON1. ANYmal-D의 **19 cm** 보·돌, 돌 높이차 **10 cm**, 미고정 보와 혼합 지형을 보인다. 도메인 무작위화·액추에이터 모델·시뮬레이션과 같은 지도 파이프라인 사용. 실기 지형별 반복 성공률·분모는 **논문에 없음**. [§IV-E3·VI-B, Fig. 11](https://arxiv.org/pdf/2601.08485v2#page=12) |
| 보고된 정량 이득 | 시뮬레이션 교사 미경험 지형 평균: AME-2 **95.2%**, AME-1 **51.2%**, MoE **45.0%**. `직접 계산` **+44.0/+50.2%p**. 학생 평균: AME-2 **82.4%**, visual recurrent **51.5%**, w/o RL **60.7%**, w/o representation loss **73.6%**. 각각 **+30.9/+21.7/+8.8%p**. 같은 논문의 ANYmal-D 비교이며 우리 MLP 대비 수치가 아니다. [Table II·III](https://arxiv.org/pdf/2601.08485v2#page=14) |
| 코드 공개 여부 | 공식 완성 학습 코드는 확인 못 했다. 저자 가이드는 후속 버전 뒤 archived code 공개 계획을 적는다. [독립 재현 저장소](https://github.com/SII-FUSC/AME_Locomotion)는 IsaacLab·rsl_rl 기반 **AME-1 변형**, 선택적 global 특징을 추가한 구현이다. 공식 AME-2 전체 재현이 아니다. 루트 전체 라이선스는 **미확인**, `rsl_rl/LICENSE` 존재만으로 전체 배포 권한을 추정하지 않는다. 논문 원실험은 **Isaac Gym + RSL-RL**. [§IV-E1](https://arxiv.org/pdf/2601.08485v2#page=8), [저자 가이드](https://github.com/zita-ch/techblogs/blob/main/2026-03-28-AME%20Tuning%20Guide.md) |
| 계산 비용 | 교사 **80,000 iterations**, 학생 **40,000**, 초기 **5,000**은 PPO surrogate 비활성. ANYmal-D는 약 **60 RTX-4090 GPU-days·8 GPU 병렬**, TRON1은 **30 GPU-days·4 GPU 병렬**. Table VI 환경 **4,800**, GPU당인지 전체인지는 명확하지 않다. mapping 모델은 로봇당 **5,400만 frames·1시간 미만**이며 이는 전체 정책 훈련시간이 아니다. [§IV-E1](https://arxiv.org/pdf/2601.08485v2#page=8), [§V-B3](https://arxiv.org/pdf/2601.08485v2#page=10), [Appendix C](https://arxiv.org/pdf/2601.08485v2#page=18) |

### 우리에게 붙일 때의 판정

| 기법 | (가) 변경 범위 | (나) 사전학습 가중치 | (다) 예산 | (라) 작은 특징에 닿는가 |
|---|---|---|---|---|
| AME 지형 인코더 | `추정` 격자·좌표를 분리하고 CNN·어텐션 망을 추가한다. 관측 설정만의 변경은 아니다. | 기존 flattened height 가중치를 attention latent 가중치로 그대로 읽을 수 없다. 뒤쪽 층 부분 이전 또는 기존 망 보존+추가 경로는 별도 설계. | 작은 인코더 실험은 미측정, 원논문 수렴시간 보장 불가. | 직접 관련. 작은 발판의 상태 의존 선택을 돕지만 누락된 샘플 자체를 복구하지는 않는다. [§IV-A](https://arxiv.org/pdf/2601.08485v2#page=4) |
| 불확실성 지도·공간 기억 | `추정` 센서·지도·관측 채널과 mapping 학습, policy 학생 훈련까지 변경한다. | 높이맵 규약과 입력채널이 달라 직접 로드 불가. 기존 정책 보존형 경로는 별도 실험. | mapping 단독 학습시간은 짧아도 센서·융합·학생 통합 비용은 포함하지 않는다. | 직접 관련. 가림과 잘못 채운 높이의 신뢰도를 표현한다. [§V](https://arxiv.org/pdf/2601.08485v2#page=9) |
| LSIO 자기상태 이력 | `추정` 관측 버퍼·인코더·학습 코드 수정. | 기존 MLP의 함수 보존을 별도로 설계할 수 있으나 논문의 직접 이전법은 아니다. | 단독 비용 미측정. | 간접 관련. 동역학·현재 상태 추정은 돕지만 미관측 발판 폭을 알아내는 기능과는 다르다. [§IV-A](https://arxiv.org/pdf/2601.08485v2#page=5) |
| 전체 AME-2 | `추정` 목표 명령·보상·교사/학생·critic·지도까지 새 학습 시스템 필요. | NVIDIA rough 체크포인트를 바로 이어받는 실험을 논문은 보고하지 않는다. | 현재 예산으로 전체 재현은 부적합. GPU 기종·효율도 알 수 없어 두 장이면 시간이 절반이라고 가정하지 않는다. | 직접 관련하나 우리 모든 실패 지형을 해결한다는 증거는 없다. [§IV-E·VIII](https://arxiv.org/pdf/2601.08485v2#page=8) |

`확인됨` sparse Test 1에서 교사 AME-1은 **99.2%**, AME-2는 **96.8%**다. 전역 특징의 전체 평균 개선을 모든 희소 지형의 개선으로 일반화하면 안 된다. 학생 Test 3에서는 visual recurrent가 **99.8%**로, AME-2의 **89.1%**보다 높다. [Table II·III](https://arxiv.org/pdf/2601.08485v2#page=14)

`확인됨` Table V의 depth missing **20%**·artifact **3%** 실험은 원시 포인트 결손·오염 강건성 검사다. 우리 높이값의 균일 잡음과 같은 조건이 아니다. 전방 상부 카메라를 끄면 Test 3 성공률이 **89.1%에서 1.1%**로 떨어진다. 어텐션·지도 불확실성 표현도 시야가 부족하면 한계가 있다. [§VII-D·Table V](https://arxiv.org/pdf/2601.08485v2#page=16)

## 5. 주변 조사 · 추가 네 연구

### AME 선행연구 · 해상도 조건과 노이즈 학습 순서

**Attention-Based Map Encoding for Learning Generalized Legged Locomotion**, Junzhe He, Chong Zhang, Fabian Jenelten, Ruben Grandia, Moritz Bächer, Marco Hutter, **2025**, **arXiv:2506.09588**. [서지](https://arxiv.org/abs/2506.09588)

`확인됨` 본문 Materials and Methods의 Terrains and Curriculum은 **10 cm 지도 간격이면 돌 지지면이 10 cm보다 커야 한다**는 설계 지침을 명시한다. 이는 해상도별 성공률 sweep이나 보편적인 최소 발판 정리가 아니다. ANYmal-D 미세 지형에는 **12 cm** 돌과 **15 cm** 보가 포함된다. [PDF p.14·p.17](https://arxiv.org/pdf/2506.09588#page=14)

`확인됨` Results D.2는 먼저 정확한 관측으로 배우고 나중에 노이즈·드리프트를 넣는 절차를, 처음부터 noisy base terrains로 학습한 C3와 비교한다. C3는 계단·구덩이·rough보다 희소 돌·보에서 약하다. D.3는 점별 CNN+어텐션을 다운샘플 CNN·Transformer·ViT와 비교한다. 제안법의 후반 단계에는 지형도 추가되므로, 노이즈 도입 시점만 분리한 통제 실험은 아니다. 그래프에서 정확한 %p를 추정 전사하지 않았다. [Results D.2·D.3, Fig. 6](https://arxiv.org/pdf/2506.09588#page=9)

`추정` 우리에게 가장 먼저 가져올 것은 복잡한 전체 망보다 **관측 노이즈 도입 시점의 통제 비교**다. 지지면·간격·격자 원점의 관계도 확인해야 한다. 이 논문이 우리 실패의 원인을 이미 증명한 것은 아니다.

### START · 작은 발판과 기억 제거의 직접 비교

**START: Traversing Sparse Footholds with Terrain Reconstruction**, Ruiqi Yu, Qianshi Wang, Hongyi Li, Zheng Jun, Zhicheng Wang, Jun Wu, Qiuguo Zhu, **2025**, **arXiv:2512.13153v1**. [서지](https://arxiv.org/abs/2512.13153)

`확인됨` 깊이 CNN·GRU·U-Net으로 로봇 뒤 **0.5 m**부터 앞 **1.1 m**, 폭 **0.8 m**, 간격 **5 cm**의 지도를 복원한다. 깊이 입력은 **60×60**, temporal depth **2장**. L1 refinement는 MSE 복원에서 흐려지는 경계를 보완한다. Lite3 **3,072 env**, **RTX A6000 한 장·약 10,000 iterations·16.6시간**의 단일 단계 학습이다. [§II-B·D](https://arxiv.org/pdf/2512.13153v1#page=3)

`확인됨` 실기 Table II에서 지형·방법별 **5회**씩 시험했다. stepping stones는 START **100%**, GRU를 MLP로 바꾼 TR-Net w/o GRU **20%**, PIE 변형 **20%**. `직접 계산` 두 비교 모두 **+80%p**다. 폭 **0.2 m** balance beams는 START **80%**, w/o GRU **20%**, 즉 **+60%p**다. 적은 반복 수이며 지형 재구성기의 기억 제거 효과이지, 우리 전체 MLP와 GRU의 공정 비교가 아니다. [§III-C·Table II](https://arxiv.org/pdf/2512.13153v1#page=7)

`추정` 현재 질문과 직접 맞닿은 후속 후보다. 발 아래로 가려진 지형을 기억해야 하는 이유와 경계 보존의 중요성을 시험할 수 있다. 다만 우리 raycast는 카메라 가림과 조건이 다르므로 전체 START를 바로 도입하기보다 동일 관측원에서 기억 유무를 비교해야 한다.

### MetaLoco · 관측 이력 스택이 항상 개선을 주지는 않는 사례

**MetaLoco: Universal Quadrupedal Locomotion with Meta-Reinforcement Learning and Motion Imitation**, Fatemeh Zargarbashi, Fabrizio Di Giuro, Jin Cheng, Dongho Kang, Bhavya Sukhija, Stelian Coros, **2024**, **arXiv:2407.17502v2**. 초기 버전 제목인 Meta-Reinforcement Learning for Universal Quadrupedal Locomotion Control과 구분했다. [서지·버전 이력](https://arxiv.org/abs/2407.17502)

`확인됨` 같은 **32종** 훈련 로봇에 GRU, MLP, **16스텝** MLP+history를 각각 **5 seeds**로 비교한다. 미경험 로봇 **40종**, 평가 **2,000 episodes**. Table III의 속도 **±0.3 m/s** 조건에서 평균 episode reward는 GRU **92.162**, MLP **90.764**, MLP+history **81.708**이다. 성공률 %p가 아니다. [§IV-B·Table III](https://arxiv.org/pdf/2407.17502v2#page=5)

`추정` 관측 이력을 단순히 붙이는 것과 순환 기억 설계는 다르다. 이 결과는 형태·질량 적응에 관한 것으로, rails·stepping_stones 지각 해상도 문제와는 직접 관계없음이다. 따라서 히스토리 추가만으로 해결된다는 근거로 쓰지 않는다.

### Agile Continuous Jumping · stepping stones를 푸는 다른 제어 전략

**Agile Continuous Jumping in Discontinuous Terrains**, Yuxiang Yang, Guanya Shi, Changyi Lin, Xiangyun Meng, Rosario Scalise, Mateo Guaman Castro, Wenhao Yu, Tingnan Zhang, Ding Zhao, Jie Tan, Byron Boots, **2024**, **arXiv:2409.10923**. [서지](https://arxiv.org/abs/2409.10923)

`확인됨` 깊이 **3층 CNN+1층 GRU** 높이맵 예측기, RL 운동계획, 모델 기반 다리 제어를 결합한다. 정책 훈련 때 지도 위치를 수평 **±8 cm**, 수직 **±5 cm** 이동한다. 이는 픽셀마다 독립적으로 더하는 잡음과 다르다. [§IV](https://arxiv.org/pdf/2409.10923#page=3)

`확인됨` Go1에서 Table I의 stepping stones 최대 속도는 **1.4 m/s**, 비교 Egocentric-Vision A1 walking은 **0.36 m/s**다. 서로 다른 로봇·보행 방식이므로 통제된 인코더 개선량으로 읽지 않는다. 모션 정책 **8,000 gradient steps·RTX 4090 약 7시간**, 지각 예측기 **약 1시간**을 별도로 사용한다. [§VIII-A·Table I](https://arxiv.org/pdf/2409.10923#page=5)

`추정` 돌을 디디는 대신 뛰는 전략도 후보라는 증거다. 그러나 행동이 관절 목표 직접 출력이 아니라 운동계획·다리 제어 계층으로 나뉘므로, 현재 ActorCritic의 관측만 고치는 방안은 아니다.

이번 추가 조사에서 **사전학습 MLP의 첫 층 확장·어댑터만으로 관측을 늘리고 희소 지형 성능까지 검증한 해당 기간의 직접 일치 논문은 확인하지 못했다.** 억지로 다른 적응 논문을 이 범주에 넣지 않았다. 격자 해상도와 지지면 크기를 정량 sweep한 직접 증거도 위 AME 설계 지침과 구분해 미확인으로 남긴다.

## 6. 우리에게 붙일 수 있는 것 · 우선순위와 이유

아래는 모두 `추정`인 실험 제안이다. 현재 저장소의 구현·실측을 새로 조사하지 않았고, 학습을 실행하지 않았다.

| 우선순위 | 제안 | 판별할 질문 · 가중치와 비용 |
|---|---|---|
| 가장 먼저 | 동일 망·격자에서 높이 노이즈와 빗나간 광선 처리를 점검하고, 노이즈 적용 순서를 비교 | 관측이 정확할 때도 발판을 못 찾는가? 기존 입력 의미와 차원을 유지하면 기존 가중치를 추가학습할 수 있다. 보상·지형·시드·명령·평가조건을 맞춰 비교한다. 성공률 상승만으로 sim2real 개선을 주장하지 않는다. [AME Results D.2](https://arxiv.org/pdf/2506.09588#page=9) |
| 그다음 | 격자와 실제 지지면·틈의 정렬을 시각화하고, 격자 간격 또는 국소 범위를 통제해 비교 | 얇은 면이 샘플에 잡히는가? 점 수를 그대로 두고 범위만 줄이면 가중치 모양은 유지되지만 미리 보는 거리가 줄고 입력 의미가 바뀐다. 점 수를 늘리면 첫 층 수정이 필요하다. [AME Terrains and Curriculum](https://arxiv.org/pdf/2506.09588#page=14) |
| 이후 | 비대칭 critic, 발 보상, 이력 추정기를 각각 분리해 추가 | 가치 추정·탐색·착지 선택 중 무엇이 병목인가? MARG 전체를 동시에 붙이면 원인 분리가 어렵다. actor 유지형 critic 실험부터는 가능성이 있다. [MARG §II](https://arxiv.org/pdf/2509.20036v2#page=3) |
| 지각 정보가 유효함을 확인한 뒤 | 같은 관측원에서 flatten MLP, 격자 CNN, AME 계열 인코더 비교 | 격자 구조·상태 의존 attention이 도움이 되는가? 망별 튜닝·학습량 차이를 통제하고 parameter 증가 효과와 구분한다. 원논문 전체 비용을 소형 실험 비용으로 쓰지 않는다. [AME Results D.3](https://arxiv.org/pdf/2506.09588#page=9) |
| 실기 센서로 이전할 때 | 불확실성 채널과 누적 지도, 경계 보존 재구성 | 미관측 영역을 평지처럼 확신하고 디디는가? 정확도와 불확실성 보정을 함께 점검한다. AME-2·START는 유력 참고지만 새 지각 파이프라인 비용이 든다. [AME-2 §V](https://arxiv.org/pdf/2601.08485v2#page=9), [START §II-B](https://arxiv.org/pdf/2512.13153v1#page=3) |
| 항법 과제로 넘어갈 때 | HiPAN의 상위 경로 커리큘럼 | 미세 발판을 해결하기 위한 우선 변경이 아니라, 목표 도달·후퇴·낮은 통로 문제를 다룰 때 검토한다. [HiPAN §IV-C](https://arxiv.org/pdf/2604.26504v1#page=4) |

### 첫 층을 못 읽는 것과 모든 가중치를 버리는 것은 다르다

`추정·설계 제안` 작업서의 “입력 차원이 바뀌면 첫 층을 못 이어받는다”는 **기존 tensor를 동일 shape로 그대로 로드할 수 없다**는 뜻으로 해석한다. 관측 확장이 기존 채널에 새 채널을 덧붙이는 경우에는 수학적으로 다음 초기화가 가능하다. 이 방식이 위 논문에서 검증됐다는 주장은 아니다.

기존 첫 affine 층을 `W x + b`, 확장 관측을 `[x; z]`라 두고 새 가중치를 `[W, 0]`, bias를 `b`로 초기화하면 첫 출력은 동일하다. 뒤쪽 층도 유지하면 **정규화와 기존 채널 의미가 같을 때** 초기 정책 함수를 보존할 수 있다. 새 열은 학습 대상이므로 이후 새 관측 활용은 별도 검증한다. 관측 순서·정규화 통계·action 의미·optimizer 상태도 함께 처리해야 한다.

`추정·설계 제안` 기존 높이 벡터를 새 latent로 완전히 교체하면 위 동일성은 자동으로 성립하지 않는다. 기존 경로를 유지한 잔차 어댑터, 기존 정책의 행동을 맞추는 증류, 호환되는 뒤쪽 층만 복사하는 방법을 각각 따로 검토할 수 있다. 어떤 방식도 기존 정책 보존과 새 지형 개선을 동시에 보장하지 않는다.

예산 판정은 **논문 전체 재현은 세 연구 모두 부적합**, **부분 모듈 추가학습은 미측정**이다. GPU가 둘이라는 정보만으로 종류·메모리·통신·렌더링 부하·분산 효율을 정할 수 없다. 소규모 실행에서 처리량과 메모리를 재기 전에는 한 판 안에 수렴한다고 약속할 수 없다. [작업서 3절](BRIEF-codex-astra.md#3-그다음--우리에게-붙일-수-있는가), [MARG §IV-A](https://arxiv.org/pdf/2509.20036v2#page=8), [HiPAN §IV-D](https://arxiv.org/pdf/2604.26504v1#page=5), [AME-2 §IV-E1](https://arxiv.org/pdf/2601.08485v2#page=8)

## 7. 못 읽은 것 · 확인 못 한 것

| 구분 | 확인 범위와 남은 공백 |
|---|---|
| 핵심 페이지·PDF 접근 | 지정한 프로젝트 페이지 모두 열었다. 웹 도구의 PDF 열기는 internal error 또는 파일 크기 제한을 반환했지만, 원본 arXiv PDF를 직접 내려받아 MARG v2·HiPAN v1·AME-2 v2를 읽었다. 따라서 핵심 PDF를 못 읽은 채 요약한 것은 아니다. PDF 표·도해는 원본 렌더 이미지로도 대조했다. |
| 추가 후보 접근 실패 | [Safe Low-Rank Adaptation in Reinforcement Learning for Locomotion의 OpenReview PDF 주소](https://openreview.net/pdf/b0d5b37bac365fde504d50b3f14047941be94d4b.pdf)를 열었으나 브라우저 확인 화면으로 이동해 본문을 읽지 못했다. 검색 결과만으로 관측 확장이나 가중치 보존 성능을 주장하지 않고 주변 연구 본문에서 제외했다. |
| 출판사 최종본 | MARG 프로젝트의 IEEE 출판사 최종본은 별도로 확보·대조하지 못했다. 근거는 arXiv accepted preprint와 프로젝트 페이지다. 다른 버전에서 표·수치가 바뀌었는지는 미확인이다. |
| MARG 공식 학습 코드 | 공식 저장소는 프로젝트 웹 파일이다. 학습·TMG 구현, 실행 환경, 코드 라이선스, 재현 실행을 확인할 수 없었다. 사이트의 공개 예정 표기를 코드 공개 완료로 취급하지 않았다. |
| HiPAN 공식 코드 | 프로젝트·논문·검색에서 공식 학습 저장소를 찾지 못했다. 저장소 URL·라이선스·실제 입력 tensor 차원·은닉 폭·GRU 길이는 미확인이다. |
| AME-2 공식 코드 | 저자 가이드와 독립 재현 구현은 읽었으나 공식 전체 학습·지도 코드 공개는 확인 못 했다. 독립 구현의 `ame2.pt` 이름이나 global 옵션을 논문의 전체 시스템이라고 취급하지 않았다. root 라이선스·실행 재현은 미확인이다. |
| 세 연구의 모델 크기 | 세 논문의 전체 파라미터 수를 확인할 수 없다. HiPAN의 은닉 폭, AME-2 정책의 전체 embedding 크기·각 층 폭도 논문에 없다. 일반적인 rsl_rl 기본값을 끼워 넣어 숫자를 만들지 않았다. |
| MARG 내부 모호성 | 이력 H와 현재 포함 개수, Fig. 2(c)의 보조망 표기, 본문과 도해의 지도 갱신률, 학습 episodes와 iteration의 관계를 코드로 해소하지 못했다. 정확한 격자 간격·배열도 명시값으로 확정하지 않았다. |
| 실기 성공률 | MARG의 반복 성공률은 프로젝트 이미지 출처이고 논문 본문 표가 아니다. HiPAN·AME-2에는 지형별 반복 실기 성공률·분모가 없다. 시뮬레이션 성공률을 실기 성공률로 옮기지 않았다. |
| 도해 수치·영상 | MARG 관측·보상 ablation과 AME 선행논문 그래프의 모든 막대 값을 정밀 디지타이즈하지 않았다. 프로젝트 영상·보충 영상 전체를 재생해 시행 횟수나 성공을 독립 집계하지 않았다. 영상 성공 장면은 반복 성공률 근거로 사용하지 않았다. |
| 주변 조사 공백 | 해상도만 바꾼 미세 지형 통제 실험, 철망·파이프에 정확히 대응하는 실험, 기존 MLP 가중치를 유지한 첫 층 확장·어댑터의 해당 기간 직접 검증 논문은 확인하지 못했다. 추가 논문 네 건의 근거는 읽은 본문·표에 한정했고 모든 부속 저장소·영상까지 재현 검증하지 않았다. |
| 우리 원인·예산 | 작업서 값 외의 저장소 수치나 GPU 사양을 새로 조사하지 않았다. 실패 원인, 우리 조건의 학습시간·메모리·성공률 이득, 부분 가중치 이전의 효과는 미측정이다. 제안은 실행 결과가 아니다. |

### 판 이력

| 판 | 언제 | 변경 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-21 | 핵심 논문 비교, 추가 연구, 적용 판정과 미확인 항목 작성 | [작업서](BRIEF-codex-astra.md), [조사 이슈 #459](https://github.com/foothold-project/foothold-lab/issues/459) |
