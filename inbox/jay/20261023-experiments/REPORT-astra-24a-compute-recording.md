> 분류: A/정책학습 · 계산 자원 및 원학습 기록 점검
> 작성: ASTRA · 2026-10-24
> 근거: ea664f1e 고정 소스 · 설치 rsl_rl · 논문 원문 · NVIDIA와 Runpod 공식 공개 문서 · CPU 답 아는 입력
> 요지: Linux 분산 기반은 있으나 현 SOL23f 실행기는 분산을 거부한다. A100/H100은 Isaac Sim 지원 대상이 아니며, 현재 학습 요약으로 원학습 발 궤적과 지각 입력을 복원할 수 없다.
> 상태: 제한 조사 완료 · GPU 성능과 실제 분산 실행은 미확인 · 실행 승인 아님

# ASTRA-24a 계산 자원과 기록 점검

## 1. 먼저 결론

1. **두 RTX5080으로 한 학습: 고쳐야 가능.** 일반 START runner에는 PPO와 지각망의 gradient 동기화가 이미 있다. 그러나 현재 B/TopDown 실행 계약은 `--distributed`를 거부한다. Linux로 옮기는 것만으로 현재 실행기가 두 GPU를 쓰지는 않는다. GRU가 원천 장애라는 주장도 틀리다.
2. **Runpod 후보: RT 코어가 있는 RTX 계열부터.** A100/H100의 큰 메모리와 CUDA 성능은 현재 Isaac Sim 전체 실행의 적합성 근거가 아니다. 더 빠르고 더 싸다는 결론은 같은 코드와 경험량에서 실측하기 전에는 미확인이다.
3. **보존 우선순위: 원학습 발 궤적, 지각 입력 묶음, 실제 환경 조건의 연결.** 현재 `step_evidence.jsonl`과 `map_stats.jsonl`은 요약이다. `record_sol23f.py`의 상세 NPZ는 체크포인트로 새 평가를 수행한 자료이며 원학습 재생 기록이 아니다.

범위: `C:/mai/wt/foothold-lab/lead-tmp-start-b`의 **ea664f1e92c3fa7223e0d372816c6ca752966690**을 `git show`로 읽었다. 아래 `foothold_s2/` 경로는 모두 이 커밋 기준이다. 설치 RSL 경로의 접두사는 `C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/`이다. 실행 중인 두 GPU 작업에는 접근하거나 변경하지 않았다. 실제 새 실행의 파일 생성 여부와 성능을 이 보고서에서 측정했다고 주장하지 않는다.

## 2. 공식 다중 GPU 지원과 우리 실행기의 차이

[Isaac Lab 2.3.2 공식 Multi-GPU 문서](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/features/multi_gpu.html)는 RSL-RL 등의 분산 학습을 지원하고, NCCL 제약 때문에 Linux만 지원한다고 명시한다. GPU마다 프로세스와 환경을 만들고 gradient를 공유하는 방식이다. 공식 예제의 구조는 아래와 같다. **우리 SOL23f의 실행 명령으로 검증한 것이 아니다.**

```text
python -m torch.distributed.run --nnodes=1 --nproc_per_node=2 scripts/reinforcement_learning/rsl_rl/train.py --task=Isaac-Cartpole-v0 --headless --distributed
```

| 대상 | 판정과 실제 구현 | 근거 파일:행 |
|---|---|---|
| 현재 B/TopDown 입구 | **분산 실행 불가로 고정.** `validate_launch`가 즉시 거부한다. B는 env 3072도 고정하여 1536/rank 설정을 그대로 넣을 수 없다. | `foothold_s2/sol23f_contract.py:19`, `:38`; `scripts/train_sol23f_common.py:47` |
| 일반 START 입구 | rank별 device와 seed, per-process env 수를 지원한다. 이 파일을 현재 실행기의 대체품으로 쓰면 SOL23f의 설정·증거·마감·재개 계약까지 같다는 보장이 없다. | `scripts/train_start.py:8`, `:89`, `:92`, `:95`; `scripts/train_sol23f_common.py:129`, `:159`, `:176` |
| 분산 초기화 | StartRunner가 상속한 설정에서 WORLD_SIZE/RANK/LOCAL_RANK를 읽고 NCCL process group을 연다. 실제 설치본은 PyTorch DDP wrapper 대신 수동 collectives를 쓰는 경로다. | `runners/start_runner.py:91`; 설치 `runners/on_policy_runner.py:351`, `:391` |
| PPO actor/critic | 설치 PPO가 gradient를 평균한다. adaptive KL도 rank 평균을 사용하고 rank 0에서 정한 학습률을 broadcast한다. | 설치 `algorithms/ppo.py:265`, `:272`, `:373`, `:432` |
| TR-Net/I-E, GRU | 지각망 Adam 갱신 전 gradient SUM/world_size가 있다. GRU의 **가중치**가 여기에 포함된다. env별 hidden은 해당 rank의 궤적에 붙는 상태이므로 서로 같은 hidden으로 만들 필요가 없다. PPO actor 자체는 MLP이고 지각망의 순환 재생은 별도다. | `runners/start_runner.py:102`, `:107`, `:243`, `:268`, `:311`, `:475`, `:485`, `:507`; `models/start_policy.py:1` |
| optimizer | 각 rank가 optimizer 복제본을 가진다. 초기 모델 broadcast와 같은 평균 gradient·갱신 횟수·optimizer 초기 상태라면 같은 갱신이 가능하다. optimizer를 매번 broadcast하는 구현은 아니다. rank마다 minibatch 수나 grad가 생기는 파라미터 목록이 달라지면 collective 순서도 검증해야 한다. | `runners/start_runner.py:475`, `:508`, `:519`, `:603`, `:606` |
| AdaSmpl | completed-return의 count/sum/sumsq를 전 rank 합산한 뒤 확률을 갱신한다. env별 GT mask는 지역 표집한다. | `runners/start_runner.py:244`, `:311`, `:499` |
| normalizer | **현재 actor/critic 모두 꺼짐.** 켜면 설치 EmpiricalNormalization은 지역 입력만으로 평균·분산을 갱신한다. 지속적인 통계 all_reduce는 없다. 현재 꺼진 기능을 활성 분산 버그로 세지 않는다. | `tasks/agents/s2_ppo_cfg.py:17`; 설치 `algorithms/ppo.py:160`; `networks/normalization.py:48` |
| curriculum | level/type 승급과 환경 재배정은 각 rank의 경험에 따라 지역적으로 진행한다. 이것 자체는 오류가 아니다. 공통 반복수에 따른 스케줄과 지역 성공률·분포를 구분해야 한다. `_s2_rng` 기본 seed=0은 rank별 seed와 별개여서 표집 상관 가능성도 남는다. | `curriculum/terrain_levels_mixed.py:106`, `:116`, `:119`, `:123` |
| 로그와 복원 | 기반 runner는 rank 0 로그/체크포인트만 쓴다. SOL23f의 StepEvidence·MapStats·manifest·재질 파일은 분산용 파일 소유권·전역 집계를 갖춘 실행 경로로 검증되지 않았다. checkpoint 하나의 지역 terrain/RNG는 모든 rank 상태가 아니다. | `runners/start_runner.py:121`, `:361`, `:599`; `runners/sol23f_runner.py:149`, `:235`; `runners/map_stats.py:95`; `scripts/train_sol23f_common.py:129`, `:203` |

**분산 전 필요한 범위:** SOL23f 계약에서 global env와 per-rank env를 명시하고 rank/device를 연결하며, 초기 모델·optimizer 동일성, PPO·지각망·AdaSmpl 동기화, rank별 환경/RNG 저장과 기록 파일 소유권을 확인해야 한다. 현재 기본 지원을 전부 새로 작성해야 한다는 뜻은 아니다. 실제 NCCL 실행과 장시간 수렴 동등성은 이번 CPU 검사로 확인할 수 없다.

1536×2×24 = **73,728 transitions/update**이고 3072×1×24와 같다. 3072를 각 GPU에 넣으면 **147,456/update**로 학습 경험량이 두 배다. 두 설정의 s/update만 비교하면 속도 향상을 과장한다. `num_steps_per_env=24`의 코드 근거는 `tasks/agents/s2_ppo_cfg.py:9`이다. **16 GB 두 장은 하나의 32 GB 메모리 공간이 아니다.** 모델·optimizer·Kit·지형은 복제되고 env·rollout 부분이 분산된다. VRAM 절감량과 PCIe/NCCL 비용, CPU 병목, 두 장의 처리량 향상은 미측정이다.

## 3. 원문에 적힌 GPU와 시간

논문 TXT 접두사: `C:/Users/AI-WS01/s2_lab/_papers/`. 행 번호는 LF 기준이며 PDF의 form-feed를 별도 행으로 세지 않았다.

| 원문 | 명시된 학습 자원과 시간 | 범위 및 근거 |
|---|---|---|
| START | RTX A6000 **1장**, Lite3 **3072 env**, 약 **10,000회 / 16.6시간** | Isaac Gym, Warp 60×60 depth. [§II-D1 Training Details](https://arxiv.org/html/2512.13153v1#S2.SS4.SSS1), `2512.13153v1.txt:221` |
| AME-2 | ANYmal-D 약 **60 RTX-4090 GPU-days**, **8 GPU 병렬**; TRON1 약 **30 GPU-days**, **4 GPU 병렬** | teacher 80,000회, student 40,000회. [§IV-E1 Training Setup](https://arxiv.org/html/2601.08485v3#S4.SS5.SSS1), `2601.08485v3.txt:399`; §VIII-F `:1106`. 원문은 이 대목에서 벽시계 완료 시간을 별도로 적지 않는다. 60/8 같은 산술을 실제 총 경과시간으로 바꾸지 않았다. |
| JEPLO | NVIDIA **RTX 6000 Pro GPU**, 전체 학습 약 **12시간** | 원문 단수 GPU. student 1024 + teacher 3072의 4096 env 배분, 초기 teacher-only와 점진 전환을 포함한다. [§III-C Training setup](https://arxiv.org/html/2609.15770v1#S3.SS3), `2609.15770v1.txt:246`. 해당 대목의 세부 GPU SKU·VRAM은 미기재. |

RTX **A6000**, RTX **6000 Ada**, RTX **6000 Pro**를 같은 카드로 취급하면 안 된다. 논문 간 로봇·시뮬레이터·입력·손실·반복수가 다르므로 위 시간으로 우리 Go2 실행의 ETA를 환산할 근거가 없다. 특히 START와 AME-2는 Isaac Gym이며 현재 Isaac Sim 요구 조건과 혼동하면 안 된다.

## 4. Runpod 가격과 Isaac Sim 적합성

**공식 공개 조회 2026-10-24.** [Runpod pricing](https://www.runpod.io/pricing)의 Pods 표시값이며 페이지 갱신일은 2026-10-08이다. Cloud 선택 상태, 지역 재고, 계약 할인, 최종 청구 조건은 미확인이다. Serverless 가격은 아래 표에 섞지 않았다.

| GPU | VRAM | 공개 표시 USD/시간 | 현재 Isaac Sim 실행 후보 판정 |
|---|---:|---:|---|
| RTX4090 | 24 GB | 0.89 | RT 있음, 후보. 실제 처리량 미측정 |
| RTX5090 | 32 GB | 1.19 | RT 있음, 후보. 드라이버·컨테이너 확인 필요 |
| L40S | 48 GB | 1.09 | RT 있음, 후보. 메모리 여유가 곧 빠른 PPO라는 뜻은 아님 |
| RTX6000 Ada | 48 GB | 0.99 | RT 있음, 후보 |
| RTX A6000 | 48 GB | 0.59 | START 사용 GPU. 우리 전체 실행 처리량은 미측정 |
| RTX Pro6000 | 96 GB | 2.49 | 공식 Sim 요구표의 Blackwell 계열 후보. 실제 제공 SKU 확인 필요 |
| A100 PCIe / SXM | 80 GB | 각각 1.79 | **RT 코어 없음, Isaac Sim 공식 비지원** |
| H100 PCIe / SXM / NVL | 80 / 80 / 94 GB | 2.89 / 3.99 / 3.19 | **RT 코어 없음, Isaac Sim 공식 비지원** |

[Isaac Sim 5.1 Requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html)는 A100/H100 같은 RT 코어 없는 GPU를 비지원으로 명시한다. headless나 Warp depth 사용이 이 요건을 없앤다는 공식 근거는 확인하지 못했다. A100/H100에서 PyTorch만 별도로 돌리는 문제와 전체 Isaac Lab 환경을 돌리는 문제는 다르다. Linux 컨테이너·드라이버·Vulkan·자산 접근·CPU RAM·VRAM을 포함한 실제 host 적합성은 미확인이다. RTX라는 이름만으로 해당 Runpod Pod를 실행 검증했다고 말하지 않는다. MIG 조각도 일반 GPU와 동등한 그래픽 기능으로 가정하지 않는다.

RT/메모리 근거: [RTX4090 공식 사양](https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4090/), [RTX5090 공식 사양](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/), [L40S 공식 사양](https://www.nvidia.com/en-in/data-center/l40s/), [RTX6000 Ada 공식 사양](https://www.nvidia.com/en-us/products/workstations/rtx-6000/). Sim 버전은 설치 계열에 맞춰 5.1 문서를 인용했다.

**비용 단축의 판단식:** 같은 global batch·코드·정밀도·기록 조건의 완료 update당 벽시계 시간과 비용을 비교한다. GPU 요금은 `장수 × 시간당 가격 × (준비+학습+평가 시간)`이고 저장 등 부대비용은 별도다. 4090 대비 5090이 비용까지 낮추려면 준비비용을 무시해도 처리량이 **1.19/0.89 = 1.337배**를 넘어야 한다. 이는 가격으로 계산한 손익분기점이며 성능 예측이 아니다. 로컬 1장과 2장 실측에서 초기 준비와 안정 구간을 분리하고 global transitions/s, update 시간, peak VRAM을 보아야 한다. 이 보고서는 새 유료 측정을 승인하거나 실행하지 않았다.

## 5. 실제 기록 단위

| 값 | 원학습에서 디스크에 남는 것 | 나중 `record_sol23f.py` 평가에서 남는 것 | 근거 |
|---|---|---|---|
| 발 XY / world XYZ | **없음.** `foot_xy`라는 집계 이름은 좌표가 아니다. | world `body_pos_w`에서 발 XYZ를 읽어 `foot_xy`, `foot_z` 저장 | `runners/sol23f_runner.py:107`, `:128`; `eval/record_sol23f.py:540`, `:602` |
| 접촉 발 속도 | reset 전 control step마다 발 rigid-body 중심 world 선속도 XY norm을 읽어 전체 env·발의 합/접촉 수를 누적. update 끝에 L, T, L/T만 저장 | 직접 속도 벡터 없음. 위치 차분은 일부 구간에서 가능하나 원래 속도나 접촉점 속도와 같지 않음 | `sol23f_runner.py:65`, `:103`, `:119`; `record_sol23f.py:600` |
| 접촉 / 종료 | 힘 norm >1 N 조건. update별 접촉 표본 수와 종료 term별 합계. 한 종료가 여러 term에 중복될 수 있음 | 발별 bool 접촉, done/timeout/종료 이유·term 배열 | `sol23f_runner.py:70`, `:105`, `:126`; `record_sol23f.py:604`, `:608` |
| 몸·관절 | update 끝 joint_pos shape/min/max/mean/SHA. 관절 궤적 없음 | joint_pos, roll/pitch, vx/vy/wz, command. root world XYZ·전체 yaw 궤적은 NPZ 필드에 없음 | `sol23f_runner.py:57`, `:138`; `record_sol23f.py:605` |
| depth | replay RAM에 입력 이력. 학습 원본 이미지 디스크 저장 없음 | 지각 `_advance`가 받은 depth2의 마지막 프레임 저장. 센서 raw 전체 이력이라는 뜻은 아님 | `runners/perception_replay.py:30`; `record_sol23f.py:440`, `:444` |
| GT / rough / refined | GT와 refined/effective의 평균·표준편차 등 update 요약. rough 배열·통계는 이 recorder에 없음 | GT/rough/refined 배열 저장 | `runners/map_stats.py:20`, `:88`, `:95`; `record_sol23f.py:445`, `:614` |
| 실제 useGT | update 평균 사용 비율. env별 mask 이력은 RAM뿐 | 실제 bool mask와 reset-first 표시 저장·pred 모드 검사 | `map_stats.py:26`; `start_runner.py:279`; `record_sol23f.py:448`, `:583`, `:612` |
| DR 실값 | startup robot material 전체 env×shape×3 NPY+SHA는 보존. mass/COM/PD/strength는 요약+SHA. camera/delay도 update 끝 요약+SHA | 새 평가 환경에서 실현한 조건이며 원학습 조건 이력의 대체물이 아님 | `sol23f_runner.py:46`, `:141`; `scripts/train_sol23f_common.py:129`, `:146`, `:153` |

StepEvidence는 `termination_manager.compute` 후, reset 전에 채집하고 `Sol23FRunner.log`에서 flush한다(`sol23f_runner.py:103`, `:235`). **200 Hz의 모든 물리 substep 기록이 아니다.** 종료 순간 표본은 포함하지만 env.step 한 번당 한 표본이다. L/T는 정적 지면에 대한 발 링크 중심 속력의 접촉 가중 평균이며 발바닥 접촉점의 미끄럼 거리 실측과 구분한다.

MapStats는 B/TopDown이 상속한 `log_map_stats=True`로 붙는다(`tasks/agents/s2_x23_ppo_cfg.py:16`, `s2_23f_topdown_ppo_cfg.py:12`, `scripts/train_sol23f_common.py:207`). 평균 지도의 평균·표준편차 요약에서 원래 512칸 배치를 복구할 수 없다.

평가 recorder는 checkpoint를 새 env에 불러와 3초씩 네 명령을 실행한다. latent/action은 mean이다(`record_sol23f.py:255`, `:263`, `:383`, `:421`, `:506`). 위치는 step 전, done은 step 후 기록한다(`:540`, `:554`, `:564`). `step_contract`의 `physics_dt_s` 이름에도 불구하고 실제 입력은 `raw.step_dt`다(`:259`, `:474`). 따라서 정책/control 주기의 배열을 물리 substep 연속 기록이라고 해석하면 안 된다. 지도 출력은 실제 갱신 tick 사이 같은 값을 포함할 수 있다. 이 상세 NPZ가 존재해도 학습 중 sampling action, 지각 hidden, 당시 DR/지형을 재생한 자료는 아니다.

## 6. 원학습 자료 공백 우선 셋

| 우선 | 복구 불가능한 원자료 | 지금 남는 자료로 할 수 없는 판단 |
|---|---|---|
| 1 | env·episode·시각이 연결된 원학습 발 XYZ, 속도 벡터, 접촉 힘, 몸 자세, 명령과 action의 궤적 | 같은 L/T라도 앞 미끄럼, 뒤 미끄럼, 발 하나의 심한 미끄럼을 구분할 수 없다. 종료 직전 관절 자세·발 지지 관계도 update 요약에서 복원 불가 |
| 2 | 같은 궤적의 depth 이력, GT/rough/refined, 실제 env별 useGT, GRU hidden과 지각 tick | 나쁜 지도와 행동 실패가 같은 순간 발생했는지, 어떤 입력으로 어느 추정값과 행동을 냈는지 확인 불가. 평균 useGT가 같다고 같은 env에서 GT를 썼다는 뜻이 아님 |
| 3 | episode별 실제 DR·reset·terrain 배정과 위 두 묶음의 연결, 재개 시 rank별 상태 | 재질 전체 배열은 있으나 다른 DR의 SHA는 원값을 되돌리는 저장 형식이 아니다. checkpoint의 지역 환경/RNG만으로 모든 원학습 상태·순서를 복원할 수 없음 |

`PerceptionReplay`는 RAM 버퍼이며 다음 rollout에서 덮인다(`runners/perception_replay.py:30`, `:47`; `start_runner.py:268`). 체크포인트의 state 목록에는 네트워크·optimizer·AdaSmpl·환경 일부·RNG가 있지만 `pstate`, replay, PhysX 연속 상태는 없다(`start_runner.py:599`). 현재 재개도 `physical_resume_identical=False`를 명시한다(`sol23f_runner.py:195`, `:201`). **새 평가나 재학습은 새로운 자료를 만들 뿐, 저장하지 않은 옛 자료를 되살리지 않는다.** 무작정 모든 env의 영상을 저장해야 한다는 뜻은 아니며, 향후 원인 판정에 필요한 고정 표본과 사건 전후 원자료의 보존 범위를 먼저 정할 사안이다. 이번에는 기록 코드를 바꾸지 않았다.

## 7. CPU 검증과 한계

isaac311 Python으로 CUDA를 숨기고 bytecode 쓰기를 끈 채, 고정 커밋의 함수 AST만 추출하여 다음 **답 아는 입력 5건 통과**를 확인했다. Kit·CUDA·분산 프로세스는 열지 않았다.

| 입력 | 예상과 실제 |
|---|---|
| valid B 인자 + distributed=True | `SOL-23f runs one process per experiment` ValueError |
| 같은 인자 + distributed=False, now=0, max_wall_s=100 | deadline=100 |
| 발 속도 (3,4,0), 접촉 힘 2 N; 다른 발은 비접촉 | 누적 속력=5, 접촉 수=1 |
| 위 속도의 부호를 모두 반전 | 저장될 속력 합·접촉 수가 동일. 방향 복원 불가능성을 확인 |
| 설치 normalizer 두 개에 각각 0과 10 입력 | 지역 평균 각각 0과 10. 지속 전역 통계 동기화는 별도 필요 |

검증은 해당 소스의 계약과 요약 손실성을 확인한 것이다. NCCL collective 완주, multi-rank optimizer 동일성, Linux 복원, 현재 실행 로그 완전성, cloud GPU 실제 속도·총비용은 **미확인**이다. root의 진행 중 측정 결과를 이 문서의 실측으로 가져오지 않았다.
