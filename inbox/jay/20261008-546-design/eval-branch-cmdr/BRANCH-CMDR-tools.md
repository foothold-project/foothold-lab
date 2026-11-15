> 분류: A/정책학습 · 학습 도구 · 분기 실행기와 CMD-R adapter 관문
> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-11
> 근거: `inbox/jay/20261008-546-design/VERIFY-astra-6.md` 2절 표 · 56 행 관문 · 3절 표 첫 행 · 80 행 계측 관문 · 코드 `go2_rl_robotlab` 28b4516d (추적 파일 무수정) · Isaac Lab 로컬 소스 · 원자료 `_eval/out/branch/`
> 요지: 분기 실행기와 CMD-R adapter 를 저장소 밖에 만들었다. 관문 a (가짜 L=99) · b (20k 경계) · c (A/A) 와 CMD-R 계측 관문은 모두 통과했다. 다만 1024 env update 관문 실행 중 GPU 1 여유가 0.6 GB 까지 내려가 4 GB 규칙을 어겼다 (사후 측정)
> 상태: 판 1 · 실험 학습 0 회 · E1 규모 A/A 0 회 · 분기 규약 · CMD-R 순서 · 예산은 팀장 확정 전 · E1 · E2 원본은 읽기만 · 커밋 없음

# 분기 실행기 · CMD-R adapter · 관문

## 0. 한눈에

| 관문 | 판정 | 핵심 수치 | 상태 |
|---|---|---|---|
| 거부 | 통과 | 확정 표시 없이 관문 아님 → 종료 4. 관문이라도 update 4 회 → 종료 4 | 확인됨 |
| CPU 시험 22 개 | 통과 | 저장소 `commands.py` 의 하한 · zero 시간 식을 AST 로 꺼내 실행했다. time-out 나이 1250 → 하한 250, 나이 0 → 0.19984 · adapter 는 command reset 안에서만 나이 0 이고 뒤에 원래 값으로 돌림 | 확인됨 |
| a · 가짜 L=99 | 통과 | 다음 번호 100 · counter 2,400 · 추가 3 회가 100 · 101 · 102. 첫 rollout 전 zero 0.006667 · base_height −1.18 · lin_vel_z −1.8667 이 연속 run model_99 기록과 같음 | 확인됨 |
| b · 20k 경계 | 통과 | 부모 E1 model_20000 → 다음 20001 · counter 480,024. 평면 ±1 · yaw ±1.5 · 남은 단계 [50000] · zero 0.1 · base_height −10 · lin_vel_z 0 · 첫 명령 표본 ±1 범위 · 첫 관측의 명령 칸 = 명령 · update 1 회 | 확인됨 |
| c · A/A (update 2 회) | 통과 | 분기 직전 상태 · 첫 관측 · RNG · 명령 사건 · 2 회 update 뒤 모델 · optimizer hash 까지 두 실행이 bitwise 같음. 이 규모에서 GPU 비결정성은 관측되지 않음 | 확인됨 |
| CMD-R 계측 | 통과 | time-out 뒤 표본기가 본 나이 1250 → 0. (+상한, +상한) 85 % → 5.0 %. 하한 > 상한 사건 3,782 → 0 (time-out reset). 초기 상태는 켬 · 끔이 같음 | 확인됨 |
| 장치 규칙 | **어김** | 1024 env update 관문 (a · a2 · b · c1 · c2 · 측정 1 회) 에서 GPU 1 사용 최고 15,698 MiB, 여유 0.6 GB. 사전 관문 값 6.5 GB 가 틀렸다 | 확인됨 (측정 1 회) · 추정 (나머지 5 회 같은 수준) |

## 1. 분기 실행기 (`_eval/branch/branch_run.py`, `branch_lib.py`)

저장소의 `Go2EnvCfg` · `MoECTSRunnerCfg` · `OnPolicyRunnerCTS.learn` 을 그대로 쓴다. learn 전에 분기 상태만 놓는다. VERIFY-astra-6 2절 표와 대응은 다음과 같다.

| 2절 항목 | 구현 |
|---|---|
| 부모 고정 | `--parent` 파일 SHA-256, 불러온 iter 가 파일 이름 번호와 같은지 확인. 저장소 HEAD 와 추적 파일 변경 여부, 관련 소스 6 개 SHA, 실행기 SHA 를 bundle 에 기록 |
| 시계와 번호 | 다음 번호 L+1, `common_step_counter = (L+1)×24`. 24 가 runner `num_steps_per_env` · command `num_steps_per_iter` 와 같은지 실행 중 assert. `curriculums.py` 의 상수 24 (163 · 186 행) 는 CPU 시험이 확인 |
| 첫 rollout 의 schedule | 명령 범위는 `commands.py:128~139` 와 같은 규칙으로 단계를 적용하고 env 별 범위를 갱신한다. zero 확률은 코드 자신의 `get_current_scale` 로 정한다. reward 가중치는 `gradual_reward_weight_modification` 두 항만 직접 호출한다. 그 뒤 새 episode 를 만드는 reset 에서는 terrain curriculum 항을 잠시 무효로 바꿔 지형 level 이 움직이지 않는다 |
| optimizer | 두 Adam 의 step · moment · group lr 를 부모에서 복원. `alg.learning_rate` = 주 optimizer lr. student encoder lr 은 손대지 않음 (E1 부모: 주 0.000171 · 학생 0.001) |
| 지형과 episode | 열마다 slot 순서로 level 0~5 를 돌려 배정 (열 안 개수 차 ≤ 1). terrain origin · scene origin 일치를 검사하고, root 위치는 origin ±0.5 m 안인지 본다. episode 나이 0 에서 시작한다 |
| 난수와 위상 | 선언 시드 (`--seed`, 관문은 1042) 를 env 와 agent 에 준다. `init_at_random_ep_len=False`. torch CPU · CUDA · numpy · python RNG hash 를 기록 |
| 분기 상태 묶음 | `bundle.json` · `bundle.npz`: 번호 · counter · 실효 schedule · level · origins · root · 관절 · 질량 · COM · 재질 · gain · 영점 · 지연 · 명령 · episode 나이 · RNG · 모델 · optimizer hash · 첫 관측 hash. bitwise resume 를 선언하지 않는다 |
| 추가 예산 | `--updates N` 은 추가 update 수 (L+1 … L+N). 실험 모드는 runner 의 `save_interval` 500 을 그대로 둔다. L=20000 이면 22000 · 24000 이 저장되어 0 · 2k · 4k 평가 지점이 나온다 |
| 거부 | `BRANCH_CONTRACT_CONFIRMED` 가 없으면 `--gate` 만 허용한다. 허용 범위는 update ≤ 3 이면서 env ≤ 1024, 또는 update 0 의 rollout 만 env ≤ 4096. 시험에서 둘 다 종료 4 로 거부됐다 |

## 2. 관문 결과 (GPU 1, 시드 1042)

### a · 가짜 L=99 (부모 = resume 시험의 연속 run model_99, env 1024, update 3)

| 칸 | 분기 직전 | 연속 run model_99 기록 |
|---|---|---|
| 다음 번호 · counter | 100 · 2,400 | (연속 run 의 다음 번호 100 · counter 2,400) |
| zero 확률 | 0.0066667 | 0.0066667 |
| base_height_l2 · lin_vel_z_l2 | −1.18 · −1.8667 | −1.18 · −1.8667 |
| 명령 범위 · 남은 단계 | ±0.5 · ±0.5 · ±1.0 · [50000, 20000] | 같음 |
| 주 lr · 학생 lr · Adam step | 0.000296 · 0.001 · 2000 | 같음 |

- update 3 회는 `model_100` · `model_101` · `model_102` 로 저장됐다. counter 는 2,424 · 2,448 · 2,472, Adam step 은 2,020 · 2,040 · 2,060 이다.
- 학생 encoder lr 은 0.001 그대로다.
- level 은 0~5 에 180 · 180 · 180 · 164 · 160 · 160 (열마다 차 ≤ 1) 이다. origin 차는 0, root 는 origin 에서 0.49998 m 안이다.
- 실행기의 마지막 한 줄 (실험 모드 저장 간격) 을 고친 뒤 a 를 다시 돌렸다 (a2). bundle 과 저장 상태가 a 와 bitwise 같았다.
- 지난 resume 시험의 counter 만 고친 후보 (fix2) 는 같은 칸이 zero 0 · base_height −1 · lin_vel_z −2 였다. 이 관문은 그 실패를 잡는 시험이다.

### b · 20k 경계 (부모 E1 model_20000, SHA c8951b79…, env 1024, update 1)

- 분기 직전 값:
  - 다음 번호 20001, counter 480,024
  - 평면 ±1 · yaw ±1.5 (env 별 범위 모두 같음), 남은 단계 [50000]
  - zero 0.1 · base_height −10 · lin_vel_z 0
- 첫 명령 표본 (1,024 개): vx · vy 가 ±1 범위에 있고, 평면 성분이 0.5 를 넘는 비율이 80 % 다. 첫 관측의 명령 칸과 명령의 차는 0 이다.
- 첫 24-step 수집 동안 resample 은 없었다. episode 가 모두 나이 0 에서 시작했기 때문이다.
- update 1 회 뒤:
  - `model_20001`, counter 480,048, schedule 그대로
  - Adam step 400,020 → 400,040
  - 주 lr 0.000171 → 0.0000506 (adaptive 규칙이 첫 update 에서 내림. 원인은 미확인)
  - 학생 lr 0.001

### c · A/A (같은 분기 설정 두 번, env 1024, update 2)

- 분기 직전 상태 칸 전부가 두 실행에서 같았다 (level · origins · root · 관절 · 질량 · COM · 재질 · gain · 영점 · 지연 · 명령 · RNG · 모델 hash, 첫 관측 세 묶음 hash).
- 명령 사건 1,025 건도 같았다.
- `model_20001` · `model_20002` 의 모델 · optimizer hash · lr 도 bitwise 같았다.
- b 의 분기 직전 상태도 c 와 같았다 (같은 설정이면 프로세스가 달라도 같은 상태).
- GPU 비결정성은 이 규모 (env 1024 · update 2) 에서 관측되지 않았다. E1 규모 (8192 env) 와 긴 학습에서는 미확인이다.

## 3. CMD-R adapter

**구현 (`branch_lib.ResetAgeAdapter`, `--cmdr on`):**
- command term 의 reset 호출 동안만 그 env 들의 `episode_length_buf` 를 0 으로 보이게 하고, 호출이 끝나면 원래 값으로 되돌린다.
- 표본기의 하한 (`commands.py:147`) 과 zero 처리의 남은 시간 (:238) 은 같은 나이 0 을 쓴다.
- periodic resample (실제 나이) 은 그대로다.
- Isaac Lab reset 순서도 그대로다. terrain curriculum 은 :356 에서 command reset (:381) 보다 먼저 불리고, episode 길이는 :394 에서 0 이 된다.
- 종료 통계는 termination manager 가 자기 종료 표시로 계산한다 (`termination_manager.py:144~147`).

**CPU 시험 (확인됨):**
- 저장소 `commands.py` 에서 `remaining_dist` · `vel_low_bound` · `next_time_left` 식을 AST 로 꺼냈다. 실제 `sample_disjoint_intervals` 는 `utils.py` 에서 읽었다.
- 나이 1250 (time-out): 하한 250. 표본 10,000 개 전부 [+1, +1 + 1e-6]. zero 남은 시간 0.
- 나이 0: 하한 0.19984. 양 · 음이 모두 나오고 음수 비율 0.50. zero 남은 시간 5 s.
- 나이 1240: 하한 22.7 로 상한을 넘는다. reset 문제와 따로 episode 끝 무렵 하한 > 상한이 남는다.
- adapter: 표본기가 본 나이 0, 뒤 버퍼 원래 값, 제거 뒤 원래 나이.

**rollout 시험 (부모 E1 model_20000, 시드 1042, env 4096, 1,500 step = 30 s, update 없음):**

| 사건 | adapter 끔 | adapter 켬 |
|---|---|---|
| 분기 직후 reset (4,096) | 나이 0 · (+1, +1) 5.2 % · zero 10.1 % | 같음 (초기 상태 hash 끔 = 켬) |
| time-out reset | 3,782 건 · 표본기 나이 1250 · 하한 250 · **하한 > 상한 3,782** · (+1, +1) **84.6 %** · zero 0 % · vx < 0 9.9 % | 3,803 건 · 나이 0 · 하한 0.1998 · **하한 > 상한 0** · (+1, +1) **5.0 %** · zero 9.7 % · vx < 0 46.0 % |
| 넘어짐 reset | 443 건 · 하한 > 상한 90 | 361 건 · 0 |
| periodic | 20,438 건 · 하한 > 상한 1 | 20,506 건 · 2 |
| 30 s 시간 가중 (+1, +1) | 16.6 % | 4.3 % |
| 완전 정지 (0, 0, 0) | 0 | 0 |
| terrain level 평균 (매 5 s) | 2.49 → 2.487 → time-out 뒤 2.939 | 2.49 → 2.486 → 2.952 |

- time-out 직후 +상한 치우침은 adapter 로 사라진다. 남은 5 % 는 `limit_vel` 경로 몫이다.
- 하한 > 상한은 time-out · 넘어짐 reset 에서 0 이 되지만, periodic 에서는 1~2 건이 남는다 (episode 끝 무렵). VERIFY-astra-6 80 행대로 별도 카운터로 남기고 고치지 않았다.
- 완전 정지는 여전히 0 이다. CMD-R 은 정지 명령을 만들지 않는다 (CMD-S 의 몫).
- episode 의 의미 보존:
  - 확인됨 (코드 + CPU): adapter 는 command reset 밖의 나이를 바꾸지 않는다.
  - 측정: time-out reset 수는 끔 3,782 · 켬 3,803 으로 같은 규모다. level 평균은 time-out 전까지 같은 경로이고, time-out 의 curriculum 결과는 2.939 · 2.952 로 같은 규칙의 결과다.
  - 차이는 명령이 바뀌어 움직임이 달라진 결과다 (추정).
- 이번 기록은 `Episode_Termination/*` 값을 step 마다 합산했다. 이 값은 「마지막 episode 종료 비율」 이라 합이 해석되지 않는다. 그래서 종료 통계 보존은 코드로만 확인됨이다.

## 4. 장치 규칙 위반 (사후 측정)

- 1024 env update 관문 (a · a2 · b · c1 · c2) 은 실행 전에 「여유 − 6.5 GB ≥ 4 GB」 만 확인했다.
- 뒤늦게 같은 설정 (b 와 같은 명령) 을 한 번 더 돌리며 200 ms 마다 쟀다. GPU 1 사용 최고 15,698 MiB, 여유 0.6 GB 였다. torch 할당 최고는 8.4 GB 다 (PPO update 단계).
- 다섯 관문도 같은 설정이므로 매번 수십 초 동안 여유가 4 GB 아래로 내려갔을 것이다 (추정). 지난 resume 시험 (같은 1024 env 학습) 도 같았을 수 있다 (미확인).
- pid 25916 과 E2 는 살아 있다.
- 앞으로 GPU 1 에서 update 관문은 env 256 이하로 줄이거나, 4 GB 규칙을 지킬 수 있는 다른 시간에 돌려야 한다.
- **남은 프로세스:** 측정에 쓴 `nvidia-smi -lms 200` (pid 145356, 출력 `_eval/out/branch/memprobe.csv`) 가 아직 돈다. 종료는 계기판이 막았고, 팀장 확인이 필요하다.

## 5. CMD-R 쌍을 바로 띄울 수 있는가

**도구는 준비됐다.** 팀장이 확정하면 다음 명령 두 줄로 띄운다.

```
BRANCH_CONTRACT_CONFIRMED=<근거> CUDA_VISIBLE_DEVICES=0 python branch_run.py --parent <E1>/model_20000.pt --seed 1042 --num_envs 8192 --updates 4000 --cmdr off --tag cmdr_s42_off
BRANCH_CONTRACT_CONFIRMED=<근거> CUDA_VISIBLE_DEVICES=1 python branch_run.py --parent <E1>/model_20000.pt --seed 1042 --num_envs 8192 --updates 4000 --cmdr on  --tag cmdr_s42_on
```

**남은 것 (미확인 · 미구현):**
1. 8192 env 실측이 없다 (지시대로 안 돌림). 1024 env update 에서 이미 GPU 1 여유가 0.6 GB 였다. 8192 env 학습은 GPU 1 의 4 GB 규칙 (pid 25916 7 GB) 과 함께 갈 수 없을 가능성이 높다 (추정). E1 은 GPU 0 에서 8192 env 로 학습했다. GPU 0 은 E2 가 끝난 뒤에야 쓸 수 있다.
2. 6 GPU-hours 상한은 실행기 안에 없다. 외부 시간 제한과 「공통으로 완료한 저장 지점끼리 비교」 규칙으로 처리해야 한다.
3. 두 GPU 의 군이 같은 시드여도 GPU 기종 · 부하가 다르면 수치 경로가 달라질 수 있다. 같은 GPU 짝 A/A 는 확인했지만 GPU 0 대 1 짝은 미확인이다.
4. 높이 인코딩: 실행기는 저장소 legacy 를 쓴다. 학습 8 지형에서는 no-hit 이 0 이라 G0 와 입력이 같다 (G0.md). gap 을 넣는 G1 에는 G0 연결이 따로 필요하다.
5. 계약 확정 대상: 부모 20000 고정, level 0~5 층화, 시드 1042 · 1043, CMD-R 판, 예산, Q 평가 지점 (0 · 2k · 4k) 과 목표 · 퇴행 cell.

## 6. 재현

```
cd C:/isaac/ext/go2_rl_robotlab/_eval/branch
python test_branch_lib.py                 # 22 checks
bash run_gates.sh refuse                  # exit 4 twice, no GPU
bash run_gates.sh a; bash run_gates.sh b; bash run_gates.sh c; bash run_gates.sh cmdr
python cmdr_analyze.py
```

원자료는 `_eval/out/branch/{gate_a,gate_a2,gate_b,gate_b_mem,gate_c1,gate_c2,cmdr_off,cmdr_on}/` (bundle · saves · events · result) 와 `cmdr_summary.json` · `cpu_tests.json` · `memprobe.csv` 다. GPU 1 실행 합계는 약 11 분이다.

## lead 재검 (10/11)

- `out/branch/cmdr_summary.json` 을 직접 읽었다: 끈 판 time-out reset 3,782 건 모두 하한 > 상한 · (+상한, +상한) 84.6 % · 완전 평면 정지 0. 문서 값과 같다.
- **장치 규칙 위반 (하위 작업 보고 · lead 확인):** 1024 env update 관문 다섯이 GPU 1 여유 4 GB 규칙을 어겼다 (사후 측정 최고 15,698 MiB · 여유 0.6 GB). 실행 전 예상만 확인하고 실행 중에는 재지 않았다. E2 (GPU 0) 와 pid 25916 은 살아 있다. 다음 GPU 1 작업은 실행 중 200 ms 측정과 자동 중단을 붙인다.
- 측정용 `nvidia-smi -lms 200` (pid 145356 · 10/11 20:51 시작) 이 남아 있다. 프로세스 종료는 팀장 확인 뒤라 lead 가 끄지 않았다.
- 이 폴더는 `C:/isaac/ext/go2_rl_robotlab/_eval/` 의 사본이다.
