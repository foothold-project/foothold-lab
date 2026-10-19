> 분류: A/정책학습 · 설계 (10 보행층 · 학습 설정과 GPU 예산)
> 작성: 오흥재 (lead 세션 작성)
> 근거: START 2512.13153v1.txt 221 행 · HiPAN 2604.26504.txt 534~535 · 632~635 행 · legged_gym@8fa29ac · DeepRoboticsLab/rl_training@3d05d3b · `docs/research/training-benchmarks.md` 19 행 · evidence/seokheon-sept-iteration-timing.txt · REPORT-seokheon-ame2.md 5 절 · Isaac Lab multi-GPU 문서 · ASTRA 19f Q6 · fable 20e Q6 · vfxpedia/mai-os#34
> 요지: PPO 값은 논문에 없어 legged_gym · Deep Robotics 공식 값을 가정으로 쓴다. GPU 시간은 병목이 아니지만 16 GB 메모리가 병목이 될 수 있어, Linux 다중 GPU 를 검증 절차로 넣는다. 날짜 예산은 「반복 수」 가 아니라 「벽시계 시간 · 달성 비율」 로 적는다
> 상태: 초안 · 팀장 검토 전 · 수치는 출처 등급(논문 · 선행 · 코드 · 실측 · 가정)을 붙임

# 18 · 학습 설정과 GPU 예산

## 1. PPO 값 (START 원문에 없음)

START · 선행 · PIE 어디에도 PPO 하이퍼파라미터가 없다(evidence/deep-research-start-missing-values.json (1), deep-research-start-chinese-sources.json). 아래는 **가정**이며 출처를 적는다.

| 값 | 채택 | 출처 |
|---|---|---|
| steps / env | 24 | [legged_gym@8fa29ac `legged_robot_config.py` 202~234](https://github.com/leggedrobotics/legged_gym/blob/8fa29acc6fd1910c3d9659eef6310bdd301cde0a/legged_gym/envs/base/legged_robot_config.py#L202) · [Deep Robotics rl_training@3d05d3b Lite3 PPO cfg](https://github.com/DeepRoboticsLab/rl_training/blob/3d05d3b97f7a2390f003547f23a02b3b42eea195/source/rl_training/rl_training/tasks/manager_based/locomotion/velocity/config/quadruped/deeprobotics_lite3/agents/rsl_rl_ppo_cfg.py) |
| epochs · minibatches | 5 · 4 | 같음 |
| 학습률 | 1e-3, adaptive (KL 0.01) | 같음 |
| γ · λ | 0.99 · 0.95 | 같음 |
| clip · entropy | 0.2 · 0.01 | 같음 (Isaac Lab ANYmal 예제는 entropy 0.005, deep-research 주의) |
| max grad norm · value 계수 | 1.0 · 1.0 | 같음 |
| actor · critic | [512, 256, 128] ELU | **선행** 2409.15692v2 Table V · 같은 값이 위 두 코드에도 있음 |

Deep Robotics 파일은 Lite3(START 실기 로봇) 제조사 공식 설정이지만 robot_lab 에서 파생된 범용 속도 추종 설정이라 START 값의 정황 근거일 뿐이다(deep-research 1 항).

## 2. env 수와 반복 수

| 항목 | START | 우리 1 차 | 등급 |
|---|---|---|---|
| env 수 | 3072 | 3072 (16 GB 에 안 들어가면 줄이고 steps 를 늘려 반복당 표본 73,728 유지) | **논문** 221 행 · 줄이는 규칙은 **가정** (20a S-1) |
| 반복 수 | 약 10,000 | 목표 10,000, 날짜 예산으로 자름 | **논문** |
| 시간 | 16.6 h · RTX A6000 1 장 | 4 절 표 | **논문** |
| depth | Warp 60 × 60, 10 Hz, 2 프레임 | 같음 | **논문** 221 · 379 행 |

## 3. 우리 처리량 실측 (지금까지 잰 것만)

| 무엇 | 장비 | env | 1 회 시간 · 처리량 | 출처 |
|---|---|---|---|---|
| NVIDIA Go2 rough, 눈 없음 | 5080 1 장 (Windows) | 4096 | 4.17 s · 약 23,000 steps/s | **실측** `training-benchmarks.md` 19 행 |
| 석헌 NVIDIA 이어학습 5 판 | RunPod (기종 미확인) | 4096 | 수집 2.50~3.60 s + 학습 0.08~0.22 s · 25,736~37,691 steps/s | **실측** evidence/seokheon-sept-iteration-timing.txt (tfevents 직접 해석) |
| 석헌 AME-2 Go2 teacher | RTX 4090 1 장 | 4096 | 7.9~8.8 s · 최대 메모리 17.3~17.8 GiB | **실측** REPORT-seokheon-ame2.md 5 절 |
| depth 렌더 + TR-Net | | | **미측정** | 첫 10 회에서 잰다 |

## 4. 갈래별 GPU 시간 (추정)

환산식(ASTRA 19f Q6): 우리 시간 T = 논문 시간 H × 학습량 배율 r / 처리량 비 q + 추가 작업. q 는 「같은 env 수 · 같은 렌더에서 수집과 갱신 전체 처리량의 비」 이고 아직 재지 않았다.

| 갈래 | 논문 기준 | 우리 추정 (q 가정 0.5 ~ 1.0, r = 1) | 근거 |
|---|---|---|---|
| G0 눈 없음 기준선(열린 명령) | 해당 없음 | 3 ~ 6 h (눈 없는 처리량 실측으로 10,000 회 × 73,728 표본 ÷ 23,000 ~ 37,000 steps/s) | **실측** 처리량 + 계산 |
| G1 지도만 · G3 지도 + 가장자리 | START 16.6 h · A6000 | 17 ~ 33 h | **논문** + **가정** q |
| 주행층 teacher · student | HiPAN 18 h + 6 h · 4090 | 24 ~ 48 h | **논문** HiPAN 534~535 행 + **가정** q |
| (참고) HiPAN 저수준 | 12 h + 2 h · 4090 | 사용 안 함(우리 보행으로 대체) | **논문** 632~634 행 |

합계 약 44 ~ 87 GPU·h 로, 두 장 기준 날짜 예산(5 절)의 10 % 안팎이다. fable 20e 의 「GPU 시간은 병목이 아니고 코드가 병목」 과 같은 결론. 단, 재시도 · 디버그 횟수는 넣지 않았다.

## 5. 날짜 예산

| 구간 | 기간 (Linux 학습 시작 10/23 00:00 을 가정) | 두 장 GPU·h |
|---|---|---|
| ~ 11/7 | 15 일 | 720 |
| ~ 11/25 | 33 일 | 1,584 |

Linux 시작일은 정해지지 않았다(ASTRA 19f 「예시」 와 같은 가정). 반복 수를 다 못 채운 판은 「목표 10,000 회 중 n %」 로 적는다(타협 원칙 ③).

## 6. 16 GB 대책

- 사실: AME-2 Go2 teacher 가 4096 env 에서 17.3~17.8 GiB 를 썼다(**실측**). START 는 48 GB A6000 에서 3072 env 를 돌렸다(**논문**). 우리 depth + TR-Net 메모리는 미측정.
- 대책 1 (순서대로):
  1. 첫 10 회에서 장당 메모리를 잰다.
  2. 넘치면 env 를 줄이고 steps 를 늘려 반복당 표본을 지킨다.
  3. Linux 다중 GPU: Isaac Lab 은 PyTorch DDP 로 GPU 마다 env 를 나눠 가진다. 메모리를 합치는 것이 아니라 env 를 반으로 나눠 장당 메모리를 줄인다. **Linux 전용**(NCCL). 실행: `python -m torch.distributed.run --nnodes=1 --nproc_per_node=2 scripts/reinforcement_learning/rsl_rl/train.py --task=<task> --headless --distributed` ([Isaac Lab Multi-GPU 문서](https://isaac-sim.github.io/IsaacLab/main/source/features/multi_gpu.html)).
- 대가: 두 장을 한 판에 묶으면 G0 · G1 · G3 를 나란히 못 돌린다. 판마다 「빠른 하나」 와 「나란히 둘」 을 고른다.
- 검증 절차(super2 런북 7 절, vfxpedia/mai-os#34 에 숫자로): 두 장 인식 · NCCL all-reduce · Go2 10 회 두 장 / 한 장 대조 · depth 카메라 두 장 렌더 · 문제 시 `NCCL_SHM_DISABLE=1`.

## 7. 구현 방법

- `RslRlOnPolicyRunnerCfg` 에 1 절 값. 순환 신경망(GRU)이 있으므로 `RslRlPpoActorCriticRecurrentCfg` 계열 또는 우리 actor-critic 클래스(13 문서)를 쓰고, 순환 상태 리셋 · minibatch 분할 규칙을 13 문서에 고정한다(ASTRA 19g 3 절 「순환 상태 재사용이 층 크기보다 위험」).
- 판마다 첫 10 회에서 `Perf/collection time` · `Perf/learning_time` · `Perf/total_fps` · 장당 최대 메모리를 기록해 q 를 구하고 4 절 표를 실측으로 바꾼다(석헌 tfevents 해석 스크립트 evidence/tfevents_perf.py 재사용).

## 8. 검증할 가설

| # | 가설 | 어떻게 보나 |
|---|---|---|
| H18-1 | 3072 env 의 depth + TR-Net 이 5080 16 GB 한 장에 들어간다 | 첫 10 회 메모리 |
| H18-2 | 두 장 DDP 가 한 장 대비 처리량 1.6 배 이상 | super2 #34 실측 |
| H18-3 | legged_gym PPO 값으로 학습이 무너지지 않는다(KL · NaN) | 첫 500 회 |

## 9. 열린 항목

- Linux 학습 시작일.
- q(처리량 비) 실측.
- 판별 「한 장 둘」 대 「두 장 하나」 배정 규칙(70 문서 일정과 함께).
