> 분류: A/정책학습 · 설계 (10 보행층 · 학습 설정 · GPU 예산 · 구현 주체)
> 작성: 오흥재 (lead 세션 초안 · fable 20f 가 v1 으로 고쳐 씀)
> 근거: START 2512.13153v1 221 행 · HiPAN 2604.26504 534~535 · 632~635 행 · Isaac Lab 2.3.2 `config/go2/agents/rsl_rl_ppo_cfg.py` 13~32 · `config/anymal_d/agents/rsl_rl_ppo_cfg.py` 31~34 · `isaaclab_rl/rsl_rl/rl_cfg.py` 54 · `distillation_cfg.py` 21~106 · `docs/research/training-benchmarks.md` 19 행 · evidence/seokheon-sept-iteration-timing.txt · REPORT-seokheon-ame2.md 128 행 · Isaac Lab multi-GPU 문서(이 세션 10/19 열람) · fable 20e Q6(118~140 행) · DECISIONS S 행 · fable 20a S-1 · S-2 · APPROVED F-D3 · H(팀장 승인 10/19) · vfxpedia/mai-os#34 · VERIFY-fable-20f P10~P14 · P21 · P23 · APPROVED K-H · K-I · **L(S2 20,000 회, 팀장 승인 10/20 00:4x)**
> 요지: PPO 값은 논문에 없어 Isaac Lab Go2 공식 cfg 값을 가정으로 쓴다(legged_gym · Deep Robotics 와 같은 값). S1 은 Isaac Lab 기본 4096 env, S2 는 START 3072 · 24 를 지키고 16 GB 가 모자라면 1 순위 Linux 다중 GPU(1536 × 2), 2 순위 env 축소 + steps 증가(팀장 승인). S2 는 반복 20,000 회(L, 논문의 2 배)라 GPU 시간은 전체의 10~15 %(재학습 포함 12~17 %)이고, 그래도 병목은 코드다. 구현 주체와 코드 자리를 여기에 둔다
> 상태: v1.1 · 팀장 검토 전 · K-H · K-I · L 반영 · 수치는 출처 등급(논문 · 선행 · 코드 · 실측 · 가정)

# 18 · 학습 설정 · GPU 예산 · 구현 주체

## 0. 쉬운 요약

강화학습은 로봇 수천 대를 시뮬에서 동시에 뛰게 하며 「한 번 모아서 한 번 고치기」(1 iteration, 반복) 를 수천 번 되풀이한다. 그때 쓰는 숫자(한 번에 몇 걸음, 몇 번 고치나 등)는 START 논문에 없어서 Isaac Lab 의 Go2 기본값을 쓴다. 우리 GPU(RTX 5080 16 GB 두 장)로 전체 단계를 다 돌려도 10/24~11/25 동안 쓸 수 있는 시간의 10~15 % 다(눈 달기 S2 를 논문의 2 배인 20,000 번 반복하기로 해서, L). 즉 시간이 부족한 것이 아니라 **코드를 만드는 손**이 부족하다. 그래서 이 문서에 누가 어떤 파일을 만드는지도 적는다. 메모리(16 GB)가 모자라면 Linux 에서 GPU 두 장을 한 학습에 묶는다(그 동안 다른 학습은 쉰다).

## 1. PPO 값 (START 원문에 없음)

START · 선행 · PIE 어디에도 PPO 하이퍼파라미터가 없다(evidence/deep-research-start-missing-values.json · deep-research-start-chinese-sources.json, 「없음 · 신뢰 high」). 아래는 **가정**이며 출처를 적는다.

| 값 | 채택 | 출처 |
|---|---|---|
| steps / env | 24 | **코드** Isaac Lab 2.3.2 `config/go2/agents/rsl_rl_ppo_cfg.py` 13 행. legged_gym@8fa29ac `legged_robot_config.py` 202~234 · Deep Robotics rl_training@3d05d3b Lite3 cfg 도 같은 값(이 두 URL 은 이번 회차 미열람, 20a 때 확인) |
| epochs · minibatches | 5 · 4 | **코드** 같은 파일 30~31 행 |
| 학습률 | 1e-3, adaptive (KL 0.01) | **코드** 32 행 |
| γ · λ | 0.99 · 0.95 | **코드** 같은 파일 |
| clip · entropy | 0.2 · 0.01 | **코드** 29 행 (Isaac Lab ANYmal 예제는 entropy 0.005, `anymal_d/agents/rsl_rl_ppo_cfg.py` 31 행) |
| max grad norm · value 계수 | 1.0 · 1.0 | **코드** 같은 파일 |
| actor · critic | [512, 256, 128] ELU | **선행(START 미기재)** 2409.15692v2 Table V 353 행 · **코드** Go2 cfg 21 행도 같은 값 |

Deep Robotics 파일은 Lite3(START 실기 로봇) 제조사 공식 설정이지만 robot_lab 에서 파생된 범용 속도 추종 설정이라 START 값의 정황 근거일 뿐이다(deep-research 1 항).

## 2. env 수와 반복 수 (단계별)

| 단계 | env | steps/env | 반복당 표본 | 반복 목표 | 등급 |
|---|---|---|---|---|---|
| S1-a · S1-b (Isaac Lab Go2 velocity env 바탕) | 4096 | 24 | 98,304 | 6,000 (S1-a) · +3,000 (S1-b 이어 학습) | **코드** Isaac Lab Go2 기본 4096(training-benchmarks 19 행 실측 조건) · 반복 수는 **가정**(1,500 회 완주 104 분 실측에서 명령 개방으로 2~4 배) |
| S2-G0 · G1 · G3 (START 틀) | **3072** | **24** | 73,728 | **20,000** | env 는 **논문** 221 행(3072 · 약 10,000 회 · 16.6 h · A6000) · steps 24 는 **팀장 승인** (DECISIONS S · fable 20a S-1 · S-2 · APPROVED F-D3 · H). **반복 수는 우리 변경**(논문 10,000 의 2 배, **팀장 승인 L** 10/20 00:4x): 이어진 지형군 0.46 을 더한 만큼 듬성한 지형 노출이 START 의 약 0.5 배로 줄어 G3 실패 때 「방법 탓 대 연습 부족」 을 못 가르므로, 지형 비율은 그대로 두고 반복만 2 배(0.50 × 20,000 ≈ START 10,000 의 1.0 배, **가정**, 15 §5). START 가 4096 이 아니라 3072 인 까닭은 논문에 없다 |
| S3 teacher · student | 1024 · 128 | 논문 미기재 | | 벽시계 18 h · 6 h 의 n % | **논문** HiPAN 535 행 |
| S4 (S2 이어 학습) | 3072 | 24 | 73,728 | 5,000 | **가정** |

S2 에서 16 GB 가 모자랄 때(**팀장 승인** F-D3): 1 순위 Linux 다중 GPU(프로세스당 1536 env × 2, 합계 3072, 6 절), 2 순위 env 를 줄이고 steps 를 늘려 반복당 표본 73,728 을 유지(예: 2048 × 36). 2 순위로 내려가면 기록한다(원칙 ③).

## 3. 우리 처리량 실측 (지금까지 잰 것만)

| 무엇 | 장비 | env | 1 회 시간 · 처리량 | 출처 |
|---|---|---|---|---|
| NVIDIA Go2 rough, 눈 없음 | 5080 1 장 (Windows) | 4096 | 4.17 s · 약 23,000 steps/s · 1,500 회 104 분 | **실측** `training-benchmarks.md` 19 행 |
| 석헌 NVIDIA 이어학습 5 판 | RunPod (기종 미확인) | 4096 | 수집 2.50~3.60 s + 학습 0.08~0.22 s (합 2.6~3.8 s) · 25,736~37,691 steps/s (중앙값) | **실측** evidence/seokheon-sept-iteration-timing.txt (tfevents 직접 해석) |
| 석헌 AME-2 Go2 teacher | RTX 4090 1 장 | 4096 | 7.9~8.8 s · 최대 메모리 17.3~17.8 GiB | **실측** REPORT-seokheon-ame2.md 128 행 |
| depth 렌더 + TR-Net · 180×320 카메라 128 대 | | | **미측정** | 첫 10 회에서 잰다 |

## 4. 단계별 GPU 시간 (이 표가 정본 · 52~55 · 70 은 여기를 가리킨다)

환산식(ASTRA 19f Q6 · fable 20e Q6): 우리 시간 T = 논문 시간 H × 학습량 배율 r / 처리량 비 q + 추가 작업. q 는 「같은 env 수 · 같은 렌더에서 수집과 갱신 전체 처리량의 비」 이고 아직 재지 않았다(q 0.5~1.0 가정, r = 1).

| 판 | 근거 | 우리 추정 | 등급 |
|---|---|---|---|
| S1-a scan (높이 스캔) | 4.17 s/회 × 6,000 회. 4.17 s 는 Windows · NVIDIA 식 env · 눈 없음 조건의 실측이라 우리 조건(Linux · 14 생성기 · 정사각 메시 · 종아리 DCMotor)과 다르다 | 7.0 h | **다른 조건 실측 + 가정**(VERIFY-lead-final 22) |
| S1-a blind (눈 없음) | 같음 | 7.0 h | 같음 |
| S1-b (깃발 지형군 추가 · blind 이어 학습 3,000 회) | 메시 지형 포함, 처리량 미측정 | 3.5~5 h | **가정** |
| **S2-G0 (눈만 끈 판 · 3072 · 20,000 · depth 렌더 없음)** | S2 틀에서 depth 렌더 · TR-Net 이 빠지므로 G1 보다 빠름. 23,000 steps/s 기준 73,728 × 20,000 ÷ 23,000 ≈ 17.8 h, 메시 지형 · 생성기 비용으로 1.5 배 | **18~28 h** (10,000 회 기준 9~14 h 의 2 배, L) | **가정**(J-A · VERIFY-lead-final 1 · 2 · L) |
| S2 G1 (지도만 · 20,000 회) | START 16.6 h(10,000 회), q 0.5~1.0 → 18~30 h, 반복 2 배(r = 2, L) | **36~60 h** | **논문** + **가정** q (20e Q6) · **L** |
| S2 G3 (지도 + 가장자리 · 20,000 회) | 같음 | **36~60 h** | 같음 |
| S3 teacher (하위 지각은 정답 지도로 대체 · J-E) | HiPAN 18 h · 4090, GPU 비 1.25~1.4. 하위가 S2 여도 teacher 단계에는 depth 렌더가 없다(21 §6) | 22~25 h | **논문** 535 행 + **가정** (20e Q6) |
| S3 student (상위 depth 180×320 × 128 env + 하위가 S2 면 60×60 depth × 128 env · TR-Net · GRU) | HiPAN 6 h. 하위 depth · TR-Net 추가 비용은 **미측정**(11/3~11/10 디버그 창에서 S2-G1 중간 체크포인트로 한 번 실행해 잰다, VERIFY-lead-final 5) | 7.5~8.5 h (+ 하위 depth 미측정) | **가정** |
| S3 student 재증류(하위 교체 뒤) | student 만 | 8 h | **가정** |
| S3 teacher 재학습(D34: S1 위에서 배웠고 S2 가 뒤늦게 F26 사전을 넘은 때만) | teacher + student | 30~34 h | **가정** |
| S4 (S2 이어 학습 5,000 회 + L1 광선 2,100 개) | 5,000 회(S2 20,000 의 1/4 · L 전 10,000 기준의 절반, 반복 수는 L 로 바뀌지 않음) + 광선 비용 | 9~15 h | **가정** |
| S1-x 시뮬 간 확인 (K-I) | MuJoCo · Gazebo 는 CPU 위주 · 칸당 50 판 × 16 칸 × 2 시뮬. Isaac 쪽 비교값은 S1-a 평가에서 이미 나옴 | GPU ≈ 0 (합에 더하지 않음) | **가정** |
| (참고) HiPAN 저수준 | 12 h + 2 h · 4090 | 사용 안 함(우리 보행으로 대체) | **논문** 632~634 행 |
| **합** | 행을 그대로 더함: 7 + 7 + 3.5~5 + 18~28 + 36~60 + 36~60 + 22~25 + 7.5~8.5 + 8 + 9~15 | **154~224 GPU·h** (teacher 재학습 30~34 h 포함 184~258) | L 로 S2 세 판이 2 배(L 전 120~175 · 150~210) · S1-x 는 GPU ≈ 0 |

날짜 예산(Linux 학습 시작 10/24 00:00 가정 · 70 문서와 같음): ~11/7 14 일 두 장 672 GPU·h, ~11/25 32 일 1,536 GPU·h. 합은 10~15 %(재학습 포함 12~17 %)다. 디버그로 판마다 2~3 번 돌려도 40 % 안이다. fable 20e 의 「GPU 시간은 병목이 아니고 코드가 병목」 과 같은 결론. 반복 수를 다 못 채운 판은 「목표 n 회 중 m %」 로 적는다(타협 원칙 ③).

## 5. 16 GB 대책

- 사실: AME-2 Go2 teacher 가 4096 env 에서 17.3~17.8 GiB 를 썼다(**실측**). START 는 48 GB A6000 에서 3072 env 를 돌렸다(**논문**). 우리 depth + TR-Net 메모리는 미측정.
- 순서(**팀장 승인** F-D3): ① 첫 10 회에서 장당 메모리를 잰다(60 B 신호: 최대 > 14.5 GB 또는 OOM). ② 넘치면 Linux 다중 GPU 로 1536 × 2. ③ 그래도 넘치면 env 를 줄이고 steps 를 늘려 반복당 표본 73,728 유지, 기록.
- 다중 GPU 의 뜻(Isaac Lab multi-GPU 문서, 이 세션 열람): **Linux 전용**(NCCL, Windows 미지원). 검증은 Linux 이전 직후에 하고, 이전 날짜는 설계 동결 시점이다(D32 · 70 §1). 프로세스마다 **완전한 env 인스턴스**(각자 `--num_envs` 개 env · 정책 사본 · 버퍼) 를 띄우고 gradient 갱신 때만 동기화한다. 메모리를 합치는 것이 아니라 `--num_envs` 를 프로세스당 값으로 넣어 장당 env 를 줄이는 것이고, Kit 고정 메모리는 두 번 들므로 절감은 절반 미만이다(미측정). 실행: `python -m torch.distributed.run --nnodes=1 --nproc_per_node=2 scripts/reinforcement_learning/rsl_rl/train.py --task=<task> --headless --distributed`.
- 대가: 두 장을 한 판에 묶으면 S2 와 S3 를 나란히 못 돌린다. 그 경우 70 의 배치에서 S3 는 S2 가 끝난 뒤로 민다(기록).
- 검증 절차(super2 런북 7 절 · vfxpedia/mai-os#34 에 숫자로): 두 장 인식 · NCCL all-reduce · Go2 10 회 두 장 / 한 장 대조 · depth 카메라 두 장 렌더 · 문제 시 `NCCL_SHM_DISABLE=1` · 화면용 GPU 가 렌더에 필요한 점(`isaac-render-needs-display-gpu`).

## 6. 구현 주체와 코드 자리 (팀장 승인 10/20 00:0x · APPROVED I 「역할」 · 70 과 같이)

**구현은 rl 세션 + lead** 가 맡는다. lead: 명령 생성기 · 지형과 승급 · 새 평가 도구 · 학습 실행. rl: 눈 있는 보행 신경망(TR-Net · I-E · AdaSmpl) · 학습 runner. 모듈 코딩은 두 담당이 띄우는 **Sonnet 세션**이 하고, 학습 감시(heartbeat · 로그 · GPU 상태 · 첫 update 확인)는 **Haiku 하위 작업**이 한다. **검증은 fable**(단계 관문마다 · 답을 아는 입력 시험 · 실제 첫 실행 확인). **ASTRA 는 한 회**: 설치된 Isaac Lab 2.3.2 코드로 설계가 실제 API 로 구현 가능한지(RayCasterCamera · 다중 GPU DDP · DCMotor 종아리 분리 · 지형 생성기 · 순환 신경망 runner) + 큰 위험 셋(눈 있는 보행 코드 · 16 GB · 11/10 관문) 반대 의견, 새 창 · 결과 파일 하나. **sol(codex) 은 실행 스크립트만**(한도 약 82 %). O5 는 이것으로 닫힘(90 D41).

| 모듈 | 파일 (Isaac Lab 확장 `foothold_s2/` 가칭) | 담당(코딩 세션) | 검증 | 쓰는 단계 |
|---|---|---|---|---|
| 명령 생성기 · 승급 | `commands/mixed_command.py` · `curriculum/terrain_levels_mixed.py` | lead (Sonnet) | fable L0~L2 | S1~S4 |
| 지형 · 마스크 · 전환 | `terrains/rough_go2_cfg.py` · `terrains/sparse_terrains.py` · `terrains/edge_mask.py` · `terrains/progression.py` | lead (Sonnet) | fable · ASTRA 1 회 | S0 START 시험지 · S1-b · S2 · 22 |
| 보상 | `rewards/start_rewards.py` | lead (Sonnet) | fable | S1~S4 |
| 로봇 · DR | `robots/go2_cfg.py` | lead (Sonnet) | fable · ASTRA 1 회(DCMotor 분리) | 전부 |
| 센서 · 증강 | `sensors/depth_cam_cfg.py` · `sensors/depth_aug.py` · `sensors/l1_raycaster.py`(S4) | rl (Sonnet) | fable · ASTRA 1 회(RayCasterCamera) | S2 · S4 |
| 지각 · 정책 · runner | `models/start_perception.py` · `models/start_policy.py` · `runners/start_runner.py` | rl (Sonnet) | fable · ASTRA 1 회 | S2 · S4 |
| 환경 task | `tasks/s1_env_cfg.py` · `tasks/s2_env_cfg.py` · `tasks/nav_env_cfg.py` | lead (Sonnet) · nav 는 rl 과 같이 | fable | S1 · S2 · S3 |
| 주행층 | `nav/room_generator.py` · `nav/gvd_astar.py` · `nav/pgcl.py`(lead) · `nav/hl_teacher.py` · `nav/hl_student.py` · 하위 내장 어댑터(rl) | lead + rl (Sonnet) | fable · ASTRA 1 회 | S3 |
| 평가 | `eval/axis1.py` · `axis2.py` · `axis3.py` · `rsj.py` · `start_sheet.py` · `metrics.py` · `replay_commands.py`(새 하네스, D30 · 지표 · 명령 열 재생은 시뮬 무관, 41 §10) | lead (Sonnet) · **Windows 에서 10/20~10/22**(K-H) | fable(옛 값 대조 · Linux 재현 확인 10/23) | S0 부터 |
| 시뮬 간 확인 S1-x (K-I) | `sim_x/mujoco_go2.py`(`unitree_mujoco` 위) · `sim_x/gazebo_bridge.py`(ROS 2 Go2 패키지 후보 위) · 정책 ONNX 내보내기 | lead (Sonnet) | fable(Isaac 값 대조 · 41 §9 S1-x 행) | S1-x 10/31~11/2 · 앱 시뮬 연결 |
| ROS 노드 | `ros/flag_follower.py` · `ros/cmd_cleaner.py` · `ros/judge_shadow.py` · `ros/policy_node.py` | lead (Sonnet) · 현민 협의 | fable · 현민 | 23 · 31 · 42 |
| Kit 실행 · 무인 사슬 · GPU 배치 · 학습 감시 | 실행 스크립트(sol) · heartbeat · 로그 감시(Haiku 하위 작업) | lead · sol(스크립트만) | fable 첫 실행 확인 | 전부 |

주행층 · ROS 노드의 lead / rl 배정은 승인문(APPROVED I 역할)에 없어 이 표가 **가정**이다(90 남은 질문).

## 7. 구현 방법 · 검증 사다리

- `RslRlOnPolicyRunnerCfg` 에 1 절 값. 순환 신경망(GRU)이 있으므로 `RslRlPpoActorCriticRecurrentCfg`(`rl_cfg.py` 54) 계열 또는 우리 actor-critic 클래스(13 문서)를 쓰고, 순환 상태 리셋 · minibatch 분할 규칙을 13 · 12 문서에 고정한다(ASTRA 19g 3 절 「순환 상태 재사용이 층 크기보다 위험」). S3 증류는 `RslRlDistillationRunnerCfg`(`distillation_cfg.py` 106) 를 바탕으로.
- 판마다 첫 10 회에서 `Perf/collection time` · `Perf/learning_time` · `Perf/total_fps` · 장당 최대 메모리를 기록해 q 를 구하고 4 절 표를 실측으로 바꾼다(evidence/tfevents_perf.py 재사용).
- 사다리: L0 cfg AST 대조(실제 Kit 등록 이름) → L1 첫 10 update(Traceback 0 · 메모리 · steps/s · 체크포인트 파일) → L2 첫 update 로그 확인 → L3 본 학습(무인 사슬 · heartbeat · GPU 두 장 상태 한 줄 보고) → L4 평가.
- 학습 승인: 2 단계 학습은 설계 동결 뒤 Linux 이전을 마치고 학습을 시작할 때 팀장이 새로 한다(APPROVED H). 다른 세션의 승인은 승인이 아니다.
- 동결은 두 단계다(50 §4): 설계 문서 10/22, 단계별 cfg · 하네스 · 관문 해시는 각 학습 직전.

## 8. 검증할 가설

| # | 가설 | 어떻게 보나 |
|---|---|---|
| H18-1 | 3072 env 의 depth + TR-Net 이 5080 16 GB 한 장에 들어간다 | 첫 10 회 메모리 |
| H18-2 | 두 장 DDP 가 한 장 대비 처리량 1.6 배 이상 | super2 #34 실측 |
| H18-3 | Isaac Lab Go2 PPO 값으로 학습이 무너지지 않는다(KL · NaN) | 첫 500 회 |
| H18-4 | 4 절 추정 q 가 0.5~1.0 안 | 첫 10 회 steps/s |

## 9. 열린 항목

- q(처리량 비) 실측 · depth 메모리 실측 · S3 student 단계의 하위 depth 추가 비용.
- 「한 장 둘」 대 「두 장 하나」 배정의 실제 전환 시점(70 과 함께).
- 주행층 · ROS 노드의 lead / rl 배정(가정) 확인.
