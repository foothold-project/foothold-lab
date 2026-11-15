> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (scripter) · 2026-10-28
> 근거: DISCUSS-next-training-1028.md §2·§4, EX-35 실행 코드 41c053ab
> 요지: 다음 학습용 기본 보행 명령 모드와 기동 자료를 CPU에서 준비한다
> 상태: 준비 중 · 학습 승인 아님 · GPU/Kit 미실행

# 기본 보행 준비판

## 1. 명령 표집기

`basic_gait`를 새 선택값으로 추가했다. 기존 `start`와 `s2a` 기본값, 슬롯, 계약은 그대로다. `--basic-new-share` 기본 0.30, 대안 0.15를 받는다. 새 몫은 정지·후진·옆걸음에 균등 배분하고, 줄인 몫은 전진에 더한다. 걸으며 돌기 0.05+0.05와 제자리 회전 0.10+0.10은 고정한다.

| 새 몫 | 전진 | 걸으며 좌/우 | 제자리 좌/우 | 정지 | 후진 | 옆 좌/우 |
|---|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.40 | 0.05/0.05 | 0.10/0.10 | 0.10 | 0.10 | 0.05/0.05 |
| 0.15 | 0.55 | 0.05/0.05 | 0.10/0.10 | 0.05 | 0.05 | 0.025/0.025 |

CPU 100,000개 실제 표본, seed 42:

| 새 몫 | 전진 | 걸으며 좌/우 | 제자리 좌/우 | 정지 | 후진 | 옆 좌/우 |
|---|---:|---:|---:|---:|---:|---:|
| 0.30 | 39,988 | 4,936/4,931 | 9,949/10,144 | 9,937 | 9,906 | 5,061/5,148 |
| 0.15 | 54,857 | 4,947/5,075 | 10,080/9,803 | 5,029 | 5,061 | 2,531/2,617 |

`test_basic_gait_cpu.py` 4 PASS, 각 비율 허용오차 0.5%p, 음의 vx·양/음 vy·정지·계약 반례 확인. `ruff check --select F` 0건, `git diff --check` 0건. 기존 `test_ex35_command.py`와 함께 실행할 때 21 PASS · 3 FAIL이었다. 실패 3건은 이 작업의 명령 코드가 아니라 설치된 로컬 `rsl_rl.utils`에 `store_code_state`가 없어 `StartRunner` import가 막힌 것이다. 해당 결합 시험은 환경 경로를 맞춘 뒤 재확인해야 한다.

## 2. 추종 보상과 관측 경로 감사

| 경로 | 원 코드 | 판단 |
|---|---|---|
| 선속도 보상 | `foothold_s2/rewards/start_rewards.py:114~115`가 Isaac `mdp.track_lin_vel_xy_exp`를 지정한다. 설치 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/rewards.py:304~315`는 명령 `[:, :2]`에서 몸 속도 `[:, :2]`를 빼서 제곱한다 | vy와 음의 vx를 부호 그대로 쓴다 |
| 회전 보상 | 같은 `start_rewards.py:116~117`, 설치 `rewards.py:318~326` | 요속도 부호 그대로 쓴다 |
| 보상식 선택 | `foothold_s2/tasks/s1_env_cfg.py:185,200~203`의 기본은 `track_lin_form="B"`, A일 때만 min 식으로 교체한다. SB cfg는 B 환경을 상속하며 선택값을 덮지 않는다 (`s2_sb_cfg.py:7~13`, `s2_23f_b_cfg.py:12~25`) | 기본 보행판은 정확 추종 B식 |
| 관측 | `s1_env_cfg.py:88,103`의 `mdp.generated_commands`, 설치 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/observations.py:675~677`은 command manager 값을 그대로 반환 | 관측 명령에 vx 하한 자르기 없음 |
| 명령 term | `mixed_command.py:192~207`가 실제 sampler 결과 세 칸을 버퍼에 복사, `:224~235`가 heading/stand 표시만 적용, `:252~255`가 `[:, :2]` 전체 오차를 기록 | basic 모드의 후진·옆걸음 보존 |
| START 식 격리 | `mixed_core.py`의 `resample_free_modes`는 basic 모드를 먼저 분기하고 `resample_start`는 START 분기에서만 호출한다. 깃발도 `flag_stride=0` 상속값 (`s2_env_cfg.py:87~95`) | basic의 음의 vx·낮은 양의 vx가 START의 0.3 문턱으로 들어가지 않음 |

수정 전 `foothold_s2/runners/reward_split.py`는 학습에 쓰지 않는 정체 진단에서 `vx`만 보고 전진/회전을 분류했다. CPU 답 아는 입력에서 명령 vx=-0.5, 실제 vx=-0.5는 `stalled=True`, 명령 vy=0.5는 `nomove=True`였다. 보상 자체와 PPO 입력을 바꾸는 결함은 아니다. 8 env Kit에서 실제 env cfg·관측·보상 소비는 미확인이다.

### 2.1 기록 전용 오분류 수정

lead 후속 지시로 `basic_gait_v1`일 때만 `RewardSplit`이 보상 직후 몸 좌우 속도까지 잡고, 전진 · 걸으며 돌기 · 제자리 회전 · 정지 · 후진 · 옆걸음 여섯 묶음의 env-step 수, 추종 env-step 수, 항별 보상 평균을 `train_extra.jsonl`의 `reward_split.by_basic_group`에 기록하게 했다. 후진은 몸 vx 부호를 뒤집어, 옆걸음은 몸 vy와 명령 vy의 부호를 맞춰 추종을 판별한다. 기존 모드의 보상 계산과 기록 분류는 그대로다. 앞의 오분류 반례 여섯 env를 보상 직후에 찍고 reset 뒤 속도·명령을 지운 CPU 시험에서 후진·옆걸음 각각 추종 1, 여섯 묶음 각각 1, 전체 추종 5/6이었다. `test_basic_gait_cpu.py` 6 PASS, `ruff check --select F` 0건.

## 3. 부모와 처음부터 기동 준비

`foothold_s2/basic_gait_launch.py`가 부모와 처음부터의 인자를 만든다. 부모 저장본은 `C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main/model_1500.pt`이며 CPU 실해시 `4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d`와 고정값이 같았다. 부모는 저장본의 가중치·두 optimizer·lr을 기존 `runner.load`로 이어받고, 누적 회차 1501~3000을 돈다. 처음부터는 누적 0~1500을 돈다. 관례상 둘 다 m1500 끝점을 갖게 한 것이며 실제 실행 update 수는 부모 1500, 처음부터 1501이다. 이 한 회 차이는 영수증에 드러낸다. 두 판 모두 시드 42, 3072 env, rollout 24, 지도 끔 확률 0.1, 기본 보행 명령, 시작 시각 분산을 쓴다. `save_interval=250`은 저장 빈도만 바꾼다.

부모 저장본의 활성 지형 레벨은 CPU로 직접 읽어 0~9, L3 이상 2791/3072였다. 논의 초안의 L0~2 조건은 그대로 재개하면 성립하지 않는다. lead 답을 반영해 부모와 처음부터 모두 원래 10행 지형 기하는 유지하고 활성 env 레벨을 `old_level % 3`으로 L0~2에 배치하며, `terrain_levels`·`command_range` 커리큘럼을 끈다. 부모 레벨과 원점은 `runner.load` 뒤 다시 배치하고 물리 reset으로 원점 무결성을 확인한다. 이 지형 상태 변경은 명령 분포 외의 설정 차이로 `resume_parent.json`·manifest·env.yaml·기동 영수증에 기록한다. 팀장 승인 전의 제안이며 실제 Kit 검증은 아직 없다.

`run_basic_gait.sh`는 기본값이 영수증 생성만 하는 DRY이다. 실제 시작은 lead의 별도 승인과 `LIVE=1`이 필요하다. CPU에서 scratch DRY는 `receipt=.../launch_receipt.json`, `DRY: training not started`, 종료 0으로 끝났다. 부모 영수증도 실제 모델 SHA를 대조하며 CPU에서 종료 0이었다. 실행 예시는 이 작업 사본을 고정하고 승인한 뒤 `END_BY=<시각+시간대> SHARE=0.30 bash foothold_s2/run_basic_gait.sh parent cuda:0 <부모>`와 `... scratch cuda:1`이다. 이 작업에서는 LIVE를 실행하지 않았다.

## 4. W15 평가와 250회 사슬

W15 커밋 `f1631c10`·`45d2d6f3`의 기본 명령 13칸, 이어진 반전·정지 재출발 3칸, 지형별 64 env 기록을 최신 `eval_map_modes.py`의 복원 오차·env arrays 증거와 합쳤다. 정지 판독은 몸 XY 선속도와 요속도를 함께 쓴다. `run_sb_eval.sh`는 세 지도 모드(`eval_gt`, `eval_pred`, `probe_prop_only`)와 `COMMAND_SUITE=extended`를 전달한다.

W28 대기열의 P1 평가 작업을 저장본당 한 건씩 만드는 `basic_gait_chain_plan.py`를 추가했다. 부모 m1750, 2000, 2250, 2500, 2750, 3000과 처음부터 m250, 500, 750, 1000, 1250, 1500을 `ready_file=model_N.pt`로 기다린다. 작업 단위는 `basic_gait_eval_once.py`의 W15 평가이며 checkpoint SHA·회차·명령 13칸·이어진 3칸·64 env·세 모드·turn16 완료 줄과 자식 종료 코드를 확인한다. 승인 출처, GPU UUID, 실제 학습 출력 폴더를 받아 JSON 제안만 쓴다. **대기열 등록이나 serve 기동은 하지 않았다.** 기존 W28 serve는 옛 renderer의 공통 claim과 P1 사슬 전환이 끝나기 전까지 보류 상태다. 두 GPU 모두 학습 중이면 평가 job은 GPU가 빌 때까지 기다리므로, 250회 저장 직후 즉시 결과가 나온다고 보장하지 않는다.

승인 뒤 JSON 제안 생성 명령은 `python -m foothold_s2.basic_gait_chain_plan parent --run-dir <실제 학습 로그 폴더> --out-root <평가 출력 폴더> --spec-dir <새 빈 폴더> --gpu 1 --gpu-uuid <GPU1 UUID> --authorization-ref <승인 근거>`이다. 처음부터 판은 `parent`를 `scratch`로 바꾼다. 생성된 JSON은 각 저장본의 `ready_file`을 기다리는 W28 `judge` 작업이며, 등록과 소비 시작은 운영 전환 승인 뒤 lead가 한다. `authorization_ref`는 출처 추적 칸이지 승인 검증 장치가 아니다.

CPU 검증: 새 기본 보행·기동·사슬 시험 20 PASS, W15·복원 오차·기존 사슬 관련 시험 26 PASS. `test_course_map_modes.py`는 앞서 적은 로컬 `store_code_state` import 결손으로 수집 전에 멈췄다. `ruff check --select F` 0건, Git Bash 구문 검사 0건. 실제 GPU·Kit 8 env 예행과 W28 소비기는 미실행이다.

## 5. 남은 승인과 확인

팀장은 기본 보행 새 몫 0.30 또는 0.15, 두 판 동시 기동, L0~2 고정, W28 평가용 GPU·승인 출처·마감을 정해야 한다. 8 env Kit 예행은 lead가 GPU 여유 때 수행한다. 부모 optimizer 재개와 지형 원점 재배치가 실제 Kit에서 함께 통과하는지 아직 미확인이다.

`SHA256SUMS-basic-gait.txt`는 이번 준비의 코드·CPU 시험 20개 파일을 고정한다. DRY가 만든 `logs_gate/`는 산출 목록과 커밋에서 제외했다.
