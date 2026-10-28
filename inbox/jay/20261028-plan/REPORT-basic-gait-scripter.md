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

주의: 기존 `foothold_s2/runners/reward_split.py:46~51`은 학습에 쓰지 않는 정체 진단에서 `vx`만 보고 전진/회전을 분류한다. CPU 답 아는 입력에서 명령 vx=-0.5, 실제 vx=-0.5는 `stalled=True`, 명령 vy=0.5는 `nomove=True`였다. 이 진단의 basic 모드 결과는 새 기술의 성과로 해석하지 않는다. 보상 자체와 PPO 입력을 바꾸는 결함은 아니다. 8 env Kit에서 실제 env cfg·관측·보상 소비는 미확인이다.

## 3. 남은 준비

부모 SHA와 scratch 기동 인자, W15 평가 사슬 연결은 다음 커밋에서 기록한다. 8 env Kit 예행은 lead가 GPU 여유 때 실행한다.
