판정: 18g의 「M2 b6 유지」를 철회하며, M1의 명시적 추정·동시 학습과 M2의 LSIO·MoE critic·단계별 증류·불확실성 지도를 복원해야 하지만, E1의 속도 추종·187점·기존 보행 보존과 원 논문 전체의 동일 재현은 양립하지 않는다.
> 분류: A/정책학습 · 설계 검증
> 작성: ASTRA · 2026-10-18
> 근거: MARG 2509.20036v2 · AME-2 2601.08485v3 · ame2_minimal @8beb9a68 · b6 고정본 직접 대조
> 요지: 의미 있는 구성은 복원하고, E1 접목 때문에 바뀌는 입력·목적·학습 단계는 감추지 않는다
> 상태: 독립 정적 검토 완료 · 새 구조 성능·실행 시간·메모리는 미측정 · GPU·프로세스·코드 변경 없음

## 1. 먼저 정정할 판단과 검토 범위

**18g에서 공개 student 구현이 없다고 읽은 것은 제 오류다.** README의 미제공 안내만으로 코드 존재까지 판단했다. 지정 커밋에는 `AME2LSIOModel`과 action/representation distillation이 실제로 있다. 반면 기본 경로의 `g1LivoxMapping_perframe.pt`는 없다. 「student 코드가 없다」와 「기본 설정으로 완전한 student 실행을 할 준비가 되어 있지 않다」는 다른 사실이다. 아래는 실제 코드 기준이다. 기존 18g 파일은 고치지 않았다.

18a의 추정기 생략은 encoder만 분리하는 실험에 대한 제안이었다. 지금 팀장 원칙에는 맞지 않는다. 18g의 추정기 입력 450·회귀 계수 1 제안도 원 논문 값으로 승격하면 안 된다. 18f의 encoder 폭 복원만으로 AME-2 전체를 갖췄다는 결론도 성립하지 않는다.

**추정기를 빠뜨렸다고 과거 실험이 전부 무의미해지는 것은 아니다.** 과거 M1은 고도 MLP 추가 효과, M2는 특정 attention 접목의 실행 비용에 관한 자료다. 다만 이를 MARG 대 AME-2 비교의 결과로 제시하면 틀리다. 보존 체크포인트와 19:08 중단 사실은 이번 사용자 전달이며, 제가 실행 상태를 다시 조사하지 않았다.

이번 직접 확인: b6에서 아래 관련 코드와 fixture를 포함한 manifest 항목 13개를 SHA256으로 대조해 13개 일치·불일치 0. manifest 자체 SHA256은 `3fdc9cfedda05065cdfd82cba4ad2dbe65892f5266a17caf977eb4ef375348f9`. 전체 파일 검증이나 GPU 시험 통과를 뜻하지 않는다. 공식 checkout HEAD는 `8beb9a688d67882828019583f7d5a78e3517f233`, 그 checkout의 git status는 깨끗했다. Fable 결과는 읽지 않았다.

### 근거 약칭

표의 `파일:행`은 아래 루트에 대한 상대 경로다. 행은 이번에 읽은 바이트 기준이다.

| 약칭 | 실제 경로 |
|---|---|
| B | `C:/Users/AI-WS01/s2_lab/step1_18b_b6_frozen/` |
| R | `C:/Users/AI-WS01/s2_lab/_research_repos/ame2_minimal/` |
| Actor | B`source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py` |
| PPO | B`source/rsl_rl/rsl_rl/algorithms/moe_cts.py` |
| Runner | B`source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py` |
| Env · Cfg · Setup | B`source/robot_lab/robot_lab/tasks/go2/` 아래 `env_cfg.py` · `rsl_rl_cfg.py` · `step1_setup.py` |
| Obs · Reward · Foot · FootConst · Terrain | 같은 Go2 폴더의 `mdp/observations.py` · `rewards.py` · `foot_train_step1.py` · `foot_reward_step1.py` · `step1_terrain.py` |
| Train | B`scripts_rsl_rl/train_step1.py` |
| RModel · RHelper · RIL | R`rsl_rl/rsl_rl/models/AME2_models.py` · `modules/ame2_modules.py` · `algorithms/ppo_il.py` |
| REnv · RCfg | R`ame2/ame2/tasks/ame2_env_cfg.py` · `agents/rsl_rl_ppo_cfg.py` |
| RSensor | R`ame2/ame2/sensors/livox_neural_map_sensor.py` |

원문: [MARG v2](https://arxiv.org/html/2509.20036v2), [AME-2 v3](https://arxiv.org/html/2601.08485v3). 공개 코드의 크기와 논문에 직접 적힌 값을 구분한다. MARG IV-A가 actor·critic 및 PPO 설정을 위임한 [47]은 Rudin 등의 *Learning to Walk in Minutes*다. 그 [공개 기본 설정](https://raw.githubusercontent.com/leggedrobotics/legged_gym/master/legged_gym/envs/base/legged_robot_config.py)의 현재 값은 참고 근거이며, MARG 저자가 사용한 정확한 커밋·override의 증거는 아니다.

## 2. MARG: 구성별 대조

| 구성 | 논문 값·절 | b6 값·파일:행 | 판정 | 줄이지 않는 구현과 E1 양립 |
|---|---|---|---|---|
| 현재 몸 관측·명령 | 45: 각속도3·중력3·명령3·관절12·속도12·직전 행동12. II-A | 동일 항목 45, 항목별 스케일·noise 적용. Env:121–164,235–238 | 항목 같음, 전처리 동일 여부 미확인 | E1 45를 보존하되 추정 target과 단위를 따로 정의. 논문 명령 범위·재표집 주기는 명시되지 않아 E1 범위를 저자 값이라 부르지 않음 |
| 이력 | H=5, 수식은 `[o_t,…,o_(t-H)]`. II-A | 10프레임 450, CTS student용. Env:160–164; Actor:156–169 | 다름·해석 주의 | 수식대로면 현재 포함 6프레임 270. 문장의 5-step 표현과 구분. 권고는 estimator에 별도 6프레임, E1에는 기존 10프레임. 저자 코드로 5/6 확인은 미확인 |
| 명시적 estimator | `[258,128,7]`, 선속도3+접촉4, ReLU. II-B·IV-A | 없음. CTS latent32·8 expert는 다른 목적. Actor:146–169 | 빠짐 | 270→258→128→7, hidden ReLU, signed 속도 출력은 linear를 권고. 258을 임의로 256으로 수정하지 않음. 최종층 activation·접촉 sigmoid는 원문이 구별해 명시하지 않아 구현 선택으로 기록 |
| estimator 학습 | PPO gradient + `MSE(v̂,v)+MSE(ĉ,c)` 동시. II-B3 Eq.6 | teacher latent MSE+MoE balance, 별도 optimizer. PPO:439–458; Cfg:54 | 빠짐 | estimator를 PPO 그래프에 연결하고 회귀를 같은 학습 단계에 추가. 7개 전체 평균 MSE는 3개·4개 각각 평균의 합과 다름. 회귀의 총 손실 계수는 원문 미기재. 1을 채택해도 우리 선택 |
| 고도 encoder | 187→128→64→16, ReLU. 입력 base_z−terrain_z. II-B1·IV-A | 폭 같음, ELU. Actor:172–176; Cfg:46 | activation 다름 | 새 지도 MLP hidden을 ReLU로. 기존 E1 actor 전체를 ReLU로 바꿀 근거는 없음. 그러면 기존 가중치를 복사해도 기존 함수가 깨짐 |
| 지도 범위·값 | 1.6×1.0 m,187점, 상대 높이. II-B1 | 17×11·0.1 m는 맞음. 입력은 offset·clip 후 ×2.5, miss=+2.5. Setup:81–92; Env:221–229 | 공간 규모 같음, 값 표현 다름 | E1의 기존 187열은 보존. 새 MARG 갈래에는 raw 상대 높이를 별도로 전달. +2.5를 실측 2.5 m로 해석하지 말 것. 원문 miss 처리 상수는 미기재 |
| actor | 현재45+추정7+지도16=68. II-B2 Eq.4 | E1 77+지도16=93. Actor:151,172–183 | 추정7 빠짐, E1 추가32 | 최소 수정은77+7+16=100이지만 그것은 E1 확장형. §4 권고는 원문 68 입력의 별도 actor를 E1 prior에 붙여 입력 의미를 보존 |
| critic·특권 정보 | 현재45+특권42+지도16=103. 특권: v3,c4,m4,μ1,COM2,외력2,PD·strength·offset26. II-A Eq.1·II-B Eq.5 | CTS latent32+raw critic275=307. raw에는 map187·토크·가속도·접촉력16이 있으나 위 특권42 묶음과 다름. Actor:152,353–362; Env:168–229; Obs:41–49 | 단순 폭 문제가 아닌 입력·경로 누락 | 실제 randomization 값을 critic에 넣고 지도16도 연결. 토크·qacc가 mass·friction·COM 관측을 대신하지 않음. §4에서는 별도103 critic, E1 critic 자체를 억지로 동일 구조라고 하지 않음 |
| actor·critic 폭/PPO | IV-A는 [47]에 위임. 현재 참고 코드:512·256·128, ELU, epochs5/minibatch4,γ.99/λ.95,clip.2,entropy.01,24step | 위 기본 규모와 다수 값 같음. Cfg:36–79. 실제 시작 lr5e-5·CTS1e-4·fresh optimizer. Setup:60–78 | 원저자 실행 동일은 미확인 | 명시된 새 두 MLP의 ReLU는 복원, E1 학습률은 접목 선택으로 기록. 위임 문헌 기본값을 MARG의 모든 override로 단정하지 않음 |
| air time | threshold.5,weight1. II-C·Table I, V-D ablation | .5·1. 다만 첫 접촉 때 지급·명령norm>.1·중력 계수 추가. Reward:214–234; Env:435–439 | 핵심항 존재, 지급 방식 동일은 미확인 | 착지 시 적산 방식은 합리적이나 원문에 없는 gating까지 재현 사실로 쓰지 않음. reward별 계수·지급 시점 분리 기록 |
| stumble | `any(Fxy>4 abs(Fz))`,weight−1. II-C·Table I | 비율4와−1 일치, 중력 계수 추가. Reward:302–310; Env:440–444 | 핵심식 같음, 부가 gating 다름 | 비율을 고칠 필요 없음. 중력 계수는 E1 추가 처리로 분리 |
| feet center | 9점,축5 cm·대각√50 cm,낮은 높이−.2,`contact*(n2+2n3)`,weight−.01. II-C Eq.7·V-D | any-by-type·no-hit 위험·접촉Fz>1 N·발 반경.022·중심 위험이면3으로 덮기. Foot:10–25; FootConst:12–14 | 주변2그룹은 대응, 중심 override 등은 추가 | 새 paper 모드에서 중심 override 제거. any 집계·접촉 임계·높이 기준·miss 정책은 명시적 구현 선택. 수식에 없는 Type1 벌점을 원문 복원이라고 말하지 않음 |
| 기본 보상 | Table I:선속도1/회전.5,vz−2,각속도−.05,action rate−.01,qacc−2.5e−7,collision·orientation·관절 자세 항 | 추종2/1,vz최종0,토크−1e−4,qacc−1e−7,몸높이최종−10,추가feet regulation 등. Env:350–448; Setup:20,139–142 | 다름 | 발 보상3개만 같아도 전체 목표는 다름. 원문 보상 모드와 E1 모드 혼합을 명시. −10 몸높이를 그대로 두면 큰 턱을 넘는 자세를 제한할 가능성, 효과 미측정 |
| 지형·curriculum | 6종·8난도. Single-Gap,Stones-Everywhere,Stones-2Rows,Stones-Balance,Beams-Balance,Air-Beams-Balance. Fig.4·IV-A | 기존 지형70%+gap30%,폭.10~.60,기존5/6행 재구성·gap0행 시작. Setup:95–174 | 대부분 빠짐 | 6종 생성기·난도 폭을 복원. 30%gap은 원문 비율이 아님. 기존 E1 난도 재구성 그대로의 이어학습과 새 지형 easy-start는 같은 계약이 아님 |
| 종료 | 몸통/hip 충돌,발 높이−.2,20초 갇힘. IV-A | base1 N,root−.30,foot query invalid/outside. Env:451–465; Terrain:96–104 | 다름 | 발별 낙하와 root 낙하를 구별. 기술적 invalid 종료는 별도 원인으로 보존하되 성능 실패와 혼합 금지. 세계z 고정−.2 대신 타일 기준을 구현 선택으로 명시 |
| domain randomization | kp.9~1.1, payload−1~2 kg,delay0~12 ms,friction.2~1.25,COM±.05,motorstrength.9~1.1,mapnoise±.05 m. Table II | mass±1 kg,COM±.03,friction0~2·restitution0~.5,별도push 등. Env:245–343 | 다름 | 원문 항목을 빠뜨리지 않고 Go2 물성에 연결. kd 원문 `[.9,11]`은 오기 가능성이 있으나 자동으로1.1로 고치지 않음. 선택한 범위를 연구자 보정으로 기록 |
| 학습 단계·기체 | 한 단계 concurrent,4096 Go1,20,000 episodes라는 표기. IV-A·Table III |4096 Go2,CTS teacher/student 동시 분할. Cfg:69; Actor:326–351 | 환경 수 같음, 알고리즘 다름 | E1 CTS를 추가 역사 prior로 남길 수 있으나 원문 estimator의 대체물로 주장하지 않음. episodes를 근거 없이 PPO updates로 등치하지 않음 |
| TMG·실기 | contact-aware ESKF + LiDAR/IMU/발 운동학,hash local map·SOR·occupancy log odds·양방향 ray interpolation. III·V-F | 정책 입력은 simulator height scan. Env:221–229 | 실기 mapping 빠짐 | 별도 TMG 경로 구현 필요. 시뮬 학습 자체는 원문도 추가 LiDAR 없이 진행하므로 TMG 완성을 기다리게 할 이유는 없음. TMG 없는 결과는 controller 실험까지 |

**원문에도 빈칸과 표기 문제가 있다.** estimator hidden 258, H=5의 포함 범위, kd 상한11, 토크 계수 `−e^(−5)` 표기를 제가 조용히 통상 값으로 바꾸지 않는다. 토크는 참고 구현의 `−1e−5`와 원문 표기를 함께 남기고 연구자 선택으로 처리해야 한다. ReLU를 모든 출력에 적용하면 음의 선속도 추정이 불가능하므로 hidden ReLU·출력 linear가 합리적 구현이다. 정확한 저자 최종층은 미확인이다.

Fig.4를 직접 읽으면 레벨1→8의 예시는 gap10→60 cm, Everywhere 돌80→30 cm·틈5→40 cm,2Rows 돌80→30·틈10→30, Balance 돌80→30·틈10→40, Beams 폭30→20·틈10→40, Air-Beams 폭30→20·틈10→40이다. 그러나 Stones-Balance의 레벨4 틈은50 cm,레벨8은40 cm로 표시된다. **8개 행의 정확한 난도 함수는 그림만으로 복원할 수 없다.** 단조 보간을 채택하면 우리 구현 선택이다. terrain mix 비율·contact 임계·TMG voxel 크기/확률 상수도 해당 원문에서 수치 확정 불가다.

## 3. AME-2: encoder 이외까지 대조

공식 checkout의 G1/gaze 예제와 ANYmal-D·TRON1 논문 실험도 동일하지 않다. 예를 들어 RCfg:148–185는 PPO5epochs/4minibatches, 논문 Appendix C는4/3이다. RCfg:198–243의 student 전환4001과 RIL 기본5001도 서로 다르다. 논문에 명시된 실험 값을 우선하고, 코드에서 보충한 값은 코드 근거라고 표시해야 한다.

| 구성 | 논문 값·절 또는 지정 공식 코드 | b6 값·파일:행 | 판정 | 줄이지 않는 구현과 E1 양립 |
|---|---|---|---|---|
| teacher 몸 입력 | 실제 v·ω·g·q·qdot·직전행동·명령. III-B·IV-A. MLP→512→512→128, RModel:51–85; RHelper:20–34 | latent32+single45=77→512→512→128. Actor:55–60,75–84 | 폭 같음, 의미 다름 | 새 teacher 몸 입력은 실제 물리 항목으로. CTS latent에 v가 있을 것이라는 추정으로 true v 입력을 생략하지 않음 |
| teacher actor 정보 제한 | contact는critic에만. IV-B | query의teacher latent가 critic275에서 계산되며 contact·토크·지도 정보를 포함할 수 있음. Actor:326–337; Env:168–229 | 원문보다 특권 누출 | teacher의proprio에 CTS privileged latent를 넣지 않음. E1 prior가 필요하면 배포 가능한 student 경로만 사용 |
| teacher map | xyz3, CNN입력z1. III-B·RModel:51–68 | point3→16, CNN1→8→48,k5,pad2,ELU | 폭·kernel 같음 | 이 부분은 새로 축소할 이유 없음. 좌표의 미터 단위·height 부호를 바로잡아 입력 계약 분리 |
| 지역·전역·query·attention | local64→96ELU; global96→64→64,max; query192→512→512→96; MHA d96 h32. RModel:64–80; RHelper:20–46 | 같은 폭. Actor:49–61,81–89 | 크기 대응 | concat 순서는 b6 CNN/FC,공식 FC/CNN. 처음부터 학습하면 재매개화 가능하나 공식 weight 복사 시 순열 필수. `amax`와`max`는 동률 gradient 배분도 다름. 바이트 동일이라 하지 않음 |
| action decoder | `[attn96,prop128,global64]`=288→512→512→action,ELU hidden. IV-A; RModel:82–85 | map160만 E1의77에 추가,237→512→256→128→12. Actor:89,151,178–183 | prop 직결128 빠짐,decoder 축소 | full288→512→512→12를 복원. 160열을 E1에 붙인 것만으로 full architecture가 되지 않음 |
| student LSIO 이력 |20step,base v·command 제외. IV-A; RModel:241–324 | CTS10step450·latent32,LSIO 없음. Actor:156–169 | 빠짐 | Go2는42×20 이력 별도 유지. CTS10step450을 전역20으로 변경하지 말고 각각 buffer. 최근3step 순서·reset 시 이전episode 유입 차단 |
| student LSIO 폭 | Conv1d(prop_dim→16,k5)→flatten256→64,최근3step→60,cmd4 합쳐128→512→512→128. RModel:299–317,365–375 | 없음 | 빠짐·명령 인터페이스 충돌 | Go242항목이면Conv42→16·최근126→60. 속도명령3이면64+60+3=127이므로 fusion 입력127, hidden512·512·출력128 보존. 128 하드코딩 그대로면 shape 오류. 의미 없는 가짜 goal 한 칸을 추가하지 않음 |
| student map |xyz+uncertainty4,point4→16,CNN2→8→48. III-B·RModel:241–292 | teacher/student 모두 동일 height187·3/1채널 경로 | 빠짐 | 별도 student encoder의 채널을 복원. uncertainty=0 고정은 학습된 불확실성을 제공하는 구현이 아님 |
| critic 구조 |MoE,원문 IV-B. 지정 코드16 experts,각512→512→1,router512→512→16 softmax. RModel:1046–1114 | 단일 MLP512→256→128,CTSstudent 쪽만8experts. Actor:152,156–169,183 | 빠짐 | 16expert critic과router 복원. student encoder의MoE를 criticMoE라고 세면 틀림. paper본문의 expert개수 공백은 지정 코드로 보충 |
| critic 입력·symmetry | teacher inputs+각link contact,fullgoal+time; critic만 좌우대칭 augmentation. IV-B·IV-E3 | rawcritic275+latent32,명령3,footforce16,대칭 경로 없음. Env:168–229; PPO:update 경로 | 빠짐·goal 충돌 | Go2 모든 관련link 접촉과critic-only mirror 복원. 속도과제에는 goal/time을 허위 생성하지 않음. 축·관절순서·지도 좌우 반전도 함께 변환 |
| 단계 |teacher완료 후 고정,student RL+증류. IV-C·IV-E1 | CTSteacher/student 동시,teacherenv75%. Cfg:69; PPO:439–458 | 다른 알고리즘 | teacher와student를 명확히 두 단계로. CTS 동시latent학습을 같은 teacher-student라고 치환하지 않음 |
| action·지도표현 증류 | action.02,representation.2. Appendix C. 지정코드 `−log p_student(a_teacher)` + 두 embedding MSE의합. RIL:127–145 |latent32MSE+balance.01 | 빠짐 | actionMSE로 임의 대체 금지. local96/global64의 각각 평균 MSE를 더함. concat160 전체평균은 둘의 가중치를 바꾸므로 동일 손실 아님 |
| student 초기 학습 |처음5000iteration surrogate 끄고 lr.001;이후RL. IV-E1·Appendix C |start5e-5,warmup50·CTSdistillation 동시. Train:51,170–173; Setup:60–78 | 다름 | 단계별 카운터·학습률·optimizer 저장. 공개RIL:185–208은RL/entropy계수와value·distill을 분리. 전체loss를0으로 만들면 안 됨 |
| PPO·학습량 |4800env,24step,4epoch/3batch,γ.99,λ.95,KL.01,value1/clip.2,entropy.004→.001;teacher80k/student40k. Appendix C·IV-E1 |4096env,24,5/4,entropy.01. Cfg:51–79. 현재10k계획 | 다름 |4096은공통자원 적응으로 명시. 모델 크기·단계는 유지하되 조각 누적 가능.10k를원문학습량 재현이라고 하지 않음 |
| 격자·시야 |ANYmal36×14/.08m,앞으로.6m;TRON18×13/.08m,앞으로.32m. IV-E1 |17×11/.1m,중심0. Actor:62–81 | E1고정187점과 충돌 |187점에서 convolution·attention폭 유지 가능하지만 시야·해상도는 원문과 다름. 보간으로504점만 늘리는 것은 관측 정보 복원이 아님 |
| 입력 높이 |base-relative elevation z,physical xyz. III-B·V-A |E1offset.5·clip×2.5 처리 높이를xyz의z로 사용. Actor:78–81; Setup:81–92 | 단위·부호 차이 |미터 단위 `terrain_z−base_z`를 새경로로. MARG의 `base_z−terrain_z`와 부호까지 동일하다고 묶지 않음. 포화 뒤 역변환은 원정보를 복구 못 함 |
| neural mapper 구조 |얕은gated U-Net,Fig.7. 두3×3conv16→pool3/stride3→upsample+skip concat→두3×3conv16;1×1출력3갈래(mean/logvariance/gate) |없음. Env의RayCaster입력 | 빠짐 |폭16·skip·gate·uncertainty모두 구현. upsample 방식·hiddenactivation·학습optimizer의 정확한 값은 Fig.7/본문에 미기재. gate는sigmoid,최종높이는gate로raw추정과입력 혼합 |
| mapper 학습 |β-NLL β=.5,stop-gradientσ가중·TV샘플가중;다양한4mesh·noise/crop/FOV/missing/outlier. V-B Eq.9–10 |없음 | 빠짐 |일반MSE reconstruction으로축소하지 않음. mapper별 학습 데이터·센서시야·loss를 독립 구성. 논문54Mframes/수렴시간은우리측정이 아님 |
| 시간 융합 |pose기반global grid,probabilistic winner-take-all. V-A Eq.6–8 |매step정답height scan만 | 빠짐 |유효분산=max(new,.5prior),valid비교1.5prior/.04,precision확률로교체. 매번평균하는Bayesfusion이나GRU로대체하면다른설계 |
| 지도 코드·weight 제공 |RSensor:37–54는JIT로드,utils는융합 구현. 기본weight경로379 |b6에해당의존없음 | 공개 일부 존재·weight 누락 |지정checkout기본`ame2/ame2/NN_models/g1LivoxMapping_perframe.pt` Test-Path=False. student전체가없다는이전판정은틀림. 반대로sampleG1gaze checkpoint를mapperweight로사용할수는없음 |
| 명령·task reward |goal xy+heading,actor거리clip2m·남은시간제거,criticfullgoal/time. taskweights100/50/5/5. III-A·IV-D1·IV-E3 |vx/vy/yawrate,추종2/1. Setup:15–19; Env:350–359 | 본질적 충돌 |속도추종 유지 시 task4항·goal종료/curriculum은 별도 정의해야 함. 목표=v×dt라는 이름치환만으로goal-reaching장점이 복원되지 않음 |
| 일반보상·whole-body |전link 접촉·가속·미끄럼·selfcollision 등,foothold위치보상은의도적으로없음. IV-D1 Table I |MARG발center−.01 포함,E1feet/hip제약. Env:395–448 | 목적 충돌 |M2에MARGcenter를기계적으로공통적용하지않음. 무릎접촉·edge사용을억제하면논문이의도한기술을실험전제에서제거 |
| 종료·impact |자세한계,baseforce>체중,contact중thigh가속60(사족)/100(이족),5초이동<.5m+goal거리>1. IV-D2 |baseforce>1N·rootfall−.30 등. Env:455–465 | 다름 |실기Go2에60이안전한지미측정. 충격완화구성은유지하되Go2적용을표기. 속도0command에서정체종료시키지않도록goal조건을실제명령조건으로적응 |
| terrain·curriculum |12종,희소·climbing·dense,successEMA>.5승급,goal거리>4강등,teacher첫20%mapnoise/yaw확장. IV-D3·Appendix A |70%기존+30%gap,non-gap5/6행·gap0행. Setup:95–174 | 큰부분빠짐 |종류·noise/headingcurriculum복원. speedtask용완주/진행정의는필수적응. E1의이미끝난curriculum그대로는새teachercurriculum아님 |
| sparse의바닥 |반은물리바닥,반은지도에보이나collision없는virtualfloor,높이−1.5~−.35m. Appendix A |floorlessgap·miss+2.5 | 다른 관측/물리 계약 |virtualfloor는실제로보이는깊이,miss는미관측. 서로같게변환하지않음.지형별ray대상과collision대상을구별 |
| randomization·sensor |payload±5kg,delay0~.02s,friction.3~1;student15%missing·2%artifact,10%complete,var.0025,1%mapcorrupt(var>1). Appendix B |E1randomization,온라인partial/noiseunc지도 없음. Env:245–343 | 다름 |단위·확률복원,Go2물성에따른범위조정은명시.단순정답height에white noise만넣어studentpipeline복원이라하지않음 |
| actuator·control |50Hz정책,실기400HzPD;ANYmalactuatornet/TRONidentifiedDC+torque-velocityclip. III-B·IV-E3 |Go2/IsaacLab,dt.005×decimation4=50Hz. Env:501–504 | 정책주기는같음·동역학다름 |Go2모터계약유지,ANYmalactuatornet억지이식금지. Go2식별/실기접촉성능은별도미확인 |

Fig.7의 크기는 실제 SVG 그림을 열어 확인했다. mapper의 숨은 activation·upsample·optimizer가 미기재인 것과, 공개 policy의 ELU가 확인되는 것은 별개다. 공식 G1 설정의 추가 gaze 기능은 이번 원 논문 재현에 필수라고 확대하지 않는다.

AME-2 Table I의 나머지 계수도 b6와 같지 않다. regularization은 roll−.1, `qdot²+.01 torque²+.001 qddot²`에−.001,action차−.01,체중초과contact force−1e−5,linkacceleration−.001이다. limit은position95%에−1000,velocity90%에−1,torque80%에−1. early termination은−10/dt,모든항의최종가중에는dt가포함된다. IsaacLab manager가dt를곱하는경로에서두번곱하지말것. AME-2의 ablation은 주로encoder/MoE·student RL/representation/uncertainty·mapping이다. MARG처럼발보상3개를각각제거한실험을AME-2도했다고쓰면틀리다.

AME-2 Appendix A의종류별비율은 rough/stair-down/stair-up/boxes/obstacles 각각5%,climbing-up20%/down5%/consecutive5%,gap5%/pallets5%/stones30%/beam5%다. 이것을gap30%로대체하면훈련분포가달라진다. 물리규모는로봇별로도다르므로Go2에도ANYmal1.1m gap·1m벽을그대로주면충실한동일과제라는주장은성립하지않는다. 비율·지형유형을유지하고규모를Go2에맞추면그조정표를별도로남겨야한다.

## 4. 최소 충실 명세: 권고하는 E1 접목 계약

**핵심 모듈을 모두 갖추는 것과 모든 원문 수치를 동일하게 재현하는 것을 구분해야 한다.** 전자는 E1 위에서 가능하다. 후자는 로봇·시뮬레이터·명령·지도 제약 때문에 불가능하다. 다음은 구현 완료 보고가 아니라 sol에게 줄 설계 권고다. 새 승인 절차를 추가하는 제안은 아니다.

### 공통 접목: E1은 고정된 배포 가능 prior, 새 논문 정책은 완전한 residual

권고는 `a = a_E1_student(history10) + Δa_paper`다. 두 판 모두 같은 E1을 시작점으로 사용하고 E1 prior는 freeze한다. E1 teacher의 특권 latent를 prior에 사용하지 않는다. 새 actor의 마지막 linear weight/bias만 0으로 초기화하고 기존 행동 std·action scale·관절 순서·clipping을 유지하면, **초기 행동 함수**를 E1과 같게 만들 수 있다. 이는 내부 구조를 같게 만드는 것이 아니라 공통 시작 행동을 제공하는 접목 방식이다.

이 방법은 E1 actor의 activation을 바꾸지 않고 MARG의 새 ReLU망과 AME-2의 full 288 decoder를 모두 보존한다. 비용은 추가 inference와 E1 prior라는 원문 외 구성이다. 명칭은 **「E1 prior + MARG 구성 이식」, 「E1 prior + AME-2 구성 이식」**가 맞다. residual은 원 논문 기법이 아니므로 그 효과까지 포함한 Go2 시스템 비교다. E1의 기존 CTS 동시 학습을 계속하면서 AME-2의 완료 teacher 고정 단계까지 동일하게 유지했다고 말할 수는 없다.

초기 일치는 학습 후 보행 보장이 아니다. 최종 head가 0이면 첫 PPO 역전파에서 그 이전 encoder의 gradient는 0일 수 있고 head가 변한 뒤 열린다. MARG estimator는 별도 회귀로 첫 step부터 학습 가능하다. hidden까지 모두 0으로 초기화하지 않는다. 새 critic은 각 논문 구조로 학습한다. 바뀐 reward의 가치함수는 다시 맞춰야 한다. full E1 fine-tuning도 가능하지만 별도 방법 선택이며, 위 권고의 단계·보존 계약도 같이 수정해야 한다.

### M1 최소 충실 명세

1. **estimator와 map encoder**: 별도 6프레임 270→258→128→7, 지도 187→128→64→16. hidden ReLU, 출력은 선속도 부호와 latent 표현을 보존하는 linear를 권고한다. H=5 수식 해석과 출력 activation 선택을 명시한다. 접촉 4개는 실제 접촉 label, 선속도 3개는 body frame 물리값을 사용한다. scaling된 critic v와 raw v를 혼합하지 않는다.
2. **actor·critic**: actor `[current45, estimated7, map16]`=68, critic `[current45, privileged42, map16]`=103. hidden 512·256·128 ELU는 [47] 기본 설정에 근거한 선택이며 MARG 저자의 정확한 override는 미확인이다. 모듈을 실제 출력과 loss에 연결하고 critic의 map16 경로도 살린다.
3. **동시 학습**: PPO와 velocity/contact MSE의 합. estimator를 detach하지 않고 중복 optimizer step도 하지 않는다. 회귀 계수 1을 초기 선택한다면 논문 값이라고 하지 말고 실제 loss 규모·gradient·velocity/contact별 오차를 기록한다. CTS latent의 속도 정보 유무는 미확인이므로 명시 estimator를 대체하지 않는다.
4. **환경**: 발 보상 3개 전부, 6종·8난도, 발 낙하 종료, 명시된 randomization 항목. E1의 발·hip·몸높이 제약을 그대로 겹쳐 넣지 말고 논문 모드와 분리한다. 불명확한 식에 대한 구현 선택은 config에 남긴다. 명령은 E1 속도 형식과 양립한다.
5. **배포 범위**: TMG의 contact-aware 상태 추정·LiDAR map·정제를 구현 항목으로 남긴다. 정책 학습은 원문처럼 정답 지형으로 진행 가능하다. 그 결과만으로 실기 TMG 성능을 검증했다고 하지 않는다.

### M2 최소 충실 명세

1. **teacher full policy**: raw 몸 상태→512·512·128, point16/CNN8·48/local96/global64/query512·512·96/MHA96h32/full288→512·512→12. Go2 속도 명령이면 teacher 몸 입력은 현재45+실제 v3=48이다. 지도는 xyz 미터 단위다. 접촉 state는 teacher actor가 아닌 critic에 준다. E1 prior는 teacher·student 양쪽에서 같은 배포 가능한 경로다.
2. **MoE critic**: 16 experts·router 512·512, critic-only 좌우 대칭. 모든 관련 link의 접촉, ground-truth 지도, 실제 명령을 받는다. actor 쪽 CTS 8 experts로 대체하지 않는다.
3. **별도 LSIO student**: 20프레임×42항목, history Conv42→16/k5, flatten256→64, 최근3프레임126→60. 속도 command3과 합친127→512·512·128. 4채널 map encoder와 teacher와 같은 폭의 full action decoder를 갖춘다. 학습한 teacher를 freeze한 뒤 student 학습을 시작한다.
4. **student 손실·단계**: teacher action의 negative log likelihood .02, attention96/global64 각각 MSE의 합 .2, PPO+value. 초기 5000 student iteration의 surrogate off·lr .001을 보존한다. checkpoint에는 단계별 optimizer·scheduler·entropy·teacher hash·진도를 넣는다. E1을 그대로 지형 teacher라고 부르는 것은 불충분하다.
5. **실제 uncertainty mapping**: Fig.7 gated U-Net, β-NLL/TV, partial-map 센서 모형, pose 융합을 구현한다. policy 출력 187점은 고정하되 mapper 내부 해상도와 센서 시야는 별도로 설계한다. 미관측·낮은 지면·virtual floor를 구분한다. mapper를 준비하는 동안 teacher 학습을 진행하는 것은 원 논문 단계에 맞는다. mapper 없이 student까지 완성했다고 표시하는 것이 문제다.
6. **환경·목적**: 12종 및 지형/지도 noise curriculum, whole-body 보상·impact 종료, 학생 관측 randomization을 갖춘다. goal-reaching task 4항과 goal 기준 종료·승급은 E1 속도 명령으로 직접 복원할 수 없다. 속도 추종 adapter를 명시하고 원래 목표 도달 성능이나 고난도 기술을 그대로 약속하지 않는다.

## 5. 충돌의 최선안과 비용

| 충돌 | 권고 | 비용·한계 |
|---|---|---|
| E1 actor 보존 vs 새 activation·decoder | 고정 E1 student prior + full paper residual | 추가 계산·원문 외 prior. 초기 일치만 가능하며 실제 일치는 아직 시험하지 않음 |
| AME-2 goal vs E1 velocity | 지정된 velocity 유지, 종속 reward·termination·curriculum에 명시적 adapter | goal의 경로 선택·속도 자율성 주장은 못 함. 작은 vdt goal로 숨기지 않음 |
| AME-2 map vs 187점 | 토큰187 고정, encoder 폭 유지, xyz/unc 정보 정상화 | 원문 앞쪽 시야·해상도와 다름. 시야 부족을 attention 구조 실패로 단정 불가 |
| MARG ReLU vs E1 ELU | 신설 estimator/elevation에 ReLU, old E1은 그대로 | 두 함수 계통 공존. 전체 activation 스위치를 ReLU로 바꾸지 않음 |
| 동일 보상 vs 각 논문 목적 | M1 발 center를 M2에 강제하지 않고 평가 metric을 공통으로 | encoder 단독 인과 비교는 못 함. 방법 전체 시스템 비교는 가능 |
| 추가10k vs teacher/student80k/40k | 예산과 단계 진도를 별도 표시, teacher부터 학습하고 student 독립 counter 사용 | 10k를 teacher5k+student5k로 나누면 student PPO가 켜지기 전에 끝날 수 있음 |
| full mapper/critic vs 16GB | 모델 폭을 줄이기 전 minibatch·mapper inference의 microbatch와 graph 보관 최적화 | persistent rollout/global map 메모리는 PPO chunk로 해소되지 않음. 실제 속도·메모리 미측정 |

M1도 작은 추정 MLP 하나를 추가하는 범위보다 크다. 누락 특권 정보·6종 지형·보상 계약이 필요하다. 다만 온라인 센서 mapping까지 필요한 M2 student보다 구현·메모리 부담은 작을 것으로 추정된다. **두 판을 오늘 안에 full 재현해 10k까지 끝낼 수 있다는 근거는 없다.** 완료 시각을 약속할 측정도 없다.

AME-2 V-C의 ANYmal 1000환경 수치를 단순 비례하면 mapper 약3GB+global map .3GB+depth 등1.2GB, 4096개에서 약18.4GB다. 기존 16GB 장비에서 정책·시뮬까지 넣기 어려울 수 있다는 경고용 계산이며 Go2 실측 예측은 아니다. 내부 지도·센서·microbatch에 따라 달라진다. b4의35~43s/update를 full LSIO·16-expert critic·mapper 판의 예상 시간으로 재사용하면 안 된다.

계산을 쪼개려면 원 minibatch 평균·advantage 정규화·KL 결정·gradient clipping·optimizer step 단위를 유지해야 한다. MARG 회귀는3/4항 각각의 평균, AME-2 representation은96/64 각각의 평균을 보존한다. MoE의 batch 통계 손실이 있으면 chunk별 통계를 단순 평균해서는 원 함수와 달라질 수 있다. 새 critic에 기존 CTS balance 손실을 자동 추가할 논문 근거도 없다.

## 6. 비교가 무너지는 경로와 결과 표기

1. **구형 checkpoint에서 각자 이어가면 사전 경험량이 달라진다.** 전달된 model_22069/model_20086은 보존 자료로 두고, 새 구조의 주 비교는 같은 원본 E1에서 시작하는 것이 맞다. 파일명만으로 정확한 완료 횟수를 확정하지 말고 저장 counter를 읽어야 한다. 이번에는 그 checkpoint를 읽지 않았다.
2. **업데이트 번호만 맞춰서는 공정하지 않다.** env·rollout·수집 transition, teacher/student 각 단계 진도, 시간·GPU 시간·실패 재시도를 함께 적는다. 4096×24×5000=491,520,000 transition이다. 같은5000이라도 한 판은 teacher, 다른 판은 student warmup이면 같은 학습 상태가 아니다.
3. **E1 파일 번호 오프셋과 완료 횟수를 분리한다.** 기존 Runner:112–113,166,212–233은 it20000부터 학습한 뒤 같은 it로 저장한다. 같은 규칙이면 추가5000 완료는24999,25000은5001,추가10000은29999다. 새 다단계 runner에 `parent_iteration/phase/completed_updates/env_steps`를 명시하면 오해를 줄일 수 있다.
4. **입력 품질을 억지로 같게 만들지는 않는다.** 각 mapping을 쓴다면 그것도 방법 차이다. 다만 「정답 지도 controller 결과」와 「온라인 지도 deployable 결과」를 한 열에 섞지 않는다. MARG 정답 map 대 AME-2 partial map의 차이를 attention 우열로 해석할 수 없다.
5. **방법 전체 비교와 구조 ablation을 구분한다.** 각자 구성·보상·curriculum이 달라도 같은 시험지에서 시스템 성능은 비교할 수 있다. 그 승패로 MLP보다 attention이 우수·열등하다고 단정할 수는 없다. 내부 구조를 억지로 맞추라는 뜻이 아니다.
6. **모듈이 존재해도 실제로 쓰이지 않을 수 있다.** estimator label·prediction 분리, 학습·추론의 동일 추정 입력, actor의 특권 누출 방지, LSIO 시간축, uncertainty 단위, zero-head 뒤 gradient 유입을 구현 시험에서 직접 본다. 새 승인 단계가 아닌 구현 정확성 항목이다.
7. **성능 해석 한계.** 단일 seed·소수 episode 승률은 탐색 결과다. episode/환경 수와 독립 training seed를 구분하고, 기존 목표 칸 판정이 있으면 결과를 보고 완화하지 않는다. 이 보고서는 새 성공 관문을 추가하지 않는다.

**lead에 전달할 판단:** M1의 estimator/ReLU 복원은 옳지만 그 둘만으로 끝나지 않는다. M2는 encoder 폭을 복원한 b6에서도 핵심 학습·critic·student·mapping이 빠져 있어 유지 권고를 철회한다. 두 판 모두 「핵심 구성을 갖춘 E1 이식」으로 설계하고, 충돌하는 원문 goal·지도 시야·기체·예산은 적응 사항으로 남긴다. 원문에 없는 수치나 미제공 코드를 추측으로 채워 「충실 구현 완료」라 하지 않는다.
