> 분류: A/정책학습 · 학습 전제 검사 (명령 분포 · resume 충실도)
> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-11
> 근거: `VERIFY-astra-4.md` 115~116 행 · `DESIGN-astra-rl-topdown.md` 「재시작과 curriculum 시계」 단락 · `_eval/Q-E1.md` 11절 · 코드 `go2_rl_robotlab` 28b4516 (`mdp/commands.py` · `mdp/curriculums.py` · `source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py` · `algorithms/moe_cts.py` · `scripts/rsl_rl/train.py`) · Isaac Lab 로컬 소스 · 원자료 `_eval/out/cmd_dist/` · `_eval/out/resume_test/`
> 요지: (A) E1 학습 명령에는 완전 정지 (0, 0, 0) 가 한 번도 없고, 평면 속도 0.2 m/s 미만 (0 제외) 은 시간의 2.9 % (20k 전) · 1.5 % (20k 뒤) 뿐이다. 반면 매 episode 첫 5 s 는 reset 직전 episode 길이를 쓰는 하한 계산 때문에 (+상한, +상한) 대각선 명령이 된다 (시간의 23 % · 21 %). (B) 이 저장소의 resume 은 모델 · optimizer 만 되살리고, env step counter (명령 curriculum · zero 명령 확률 · reward 가중치 schedule 의 시계) · 지형 레벨 · learning rate · RNG 는 처음으로 돌아간다. iteration 번호는 마지막 번호를 한 번 더 쓰고 `--max_iterations` 는 추가로 센다
> 상태: 판 1 · 학습은 resume 시험용 새 run 4 개 (1024 env · 200 iter 이하) 뿐 · E1 · E2 로그와 checkpoint 무수정 · 저장소 원본 무수정 · 커밋 없음

# 학습 명령 분포와 resume 충실도

## 0. 한눈에

| 물음 | 답 | 상태 |
|---|---|---|
| 정지 (0, 0, 0) 명령 | 20k 전 · 뒤 모두 0 % (env-step 614 만 개씩). 코드상으로도 생성 경로가 없다 | 확인됨 |
| 평면 속도 0 < \|v\| < 0.2 | 시간의 2.9 % (20k 전) · 1.5 % (20k 뒤) | 확인됨 |
| Q-E1 fwd01 (vx 0.1 ± 0.05, \|vy\| ≤ 0.05, \|wz\| ≤ 0.1) 근처 | 시간의 0.010 % · 0.014 % | 확인됨 |
| 가장 흔한 명령 | (+상한, +상한) 대각선 정확히: 시간의 23.4 % · 20.5 % | 확인됨 |
| 후진 · 횡 · 회전 | 후진 우세 23 % · 횡 우세 37 % · \|wz\| ≥ 0.5 가 53 % · 67 % | 확인됨 |
| resume 이 되살리는 것 | 모델 가중치 · 두 Adam 상태 (lr 포함) · iteration 번호 | 확인됨 (B 절) |
| resume 이 못 되살리는 것 | env step counter · 명령 curriculum 단계 · zero 명령 확률 · reward 가중치 schedule · 지형 레벨 · 알고리즘의 learning rate · RNG · episode 위상 | 확인됨 (B 절) |
| `--max_iterations` | 추가 (불러온 번호부터 그만큼 더) | 확인됨 (B 절) |

## A. 학습 명령 분포

### A.1 방법

- **env:** 손대지 않은 `Go2EnvCfg` 를 썼다. E1 의 `params/env.yaml` 과 비교하면 commands · events · terminations · curriculum · observations · actions · rewards 는 차이 0 이다. scene/terrain 의 38 칸 차이는 생성기가 실행 중에 채우는 값 (sub-terrain size 9 m · border 0.5 m · slope threshold) 이다.
- **명령 생성:** `Go2RLGymCommand` 의 실제 경로를 그대로 탔다. 학습 rollout 과 같이 `runner.alg.act` 로 teacher 75 % · student 25 % 를 확률적으로 표본 추출했고, update 는 하지 않았다.
- **curriculum 단계:** 코드가 스스로 읽는 env counter 로 정했다 (`commands.py:129` `current_iter = common_step_counter // 24`).
  - 20k 전: counter = 19000 × 24, E1 `model_19500`.
  - 20k 뒤: counter = 20000 × 24. 첫 resample 에서 코드가 범위를 1.0 으로 바꾼다. 정책은 E1 `model_20499`.
  - 두 경우 모두 runner 처럼 episode 위상을 무작위로 놓고 (`init_at_random_ep_len`), 300 step 을 예열한 뒤 1500 step (30 s) 을 기록했다.
- **규모:** 4096 env (E1 은 8192, 지형 열 비율은 같다). 각 경우 env-step 6,144,000 이다.
- **기록:** `_resample` 의 모든 호출에서 step · env · 표본기가 본 episode 길이 · 이유 (주기 / time-out reset / 종료 reset) · 새 명령을 남겼다. 시간 가중 분포는 매 step `ct.commands` 로 셌고, 사건 기록으로 복원한 명령과 매 step 차 0 이었다.
- **기록기 시험:** 답을 아는 설정 (명령 (0.3, 0, 0.5) 고정 · resample 1 s · 동적 · limit · zero 경로 끔) 에서 다섯 검사를 모두 통과했다. 모든 step · 사건이 정확히 (0.3, 0, 0.5) 이고 주기 간격은 50~51 step 이다 (`out/cmd_dist/test/summary.json`).

### A.2 결과 (시간 가중, 모든 env-step)

| | 20k 전 (±0.5 · wz ±1.0) | 20k 뒤 (±1.0 · wz ±1.5) |
|---|---:|---:|
| 완전 정지 (0, 0, 0) | 0 | 0 |
| 평면 0 · 회전만 | 6.7 % | 7.9 % |
| 평면 \|v\| (0, 0.1) | 0.41 % | 0.41 % |
| 평면 \|v\| [0.1, 0.2) | 2.44 % | 1.11 % |
| 평면 \|v\| [0.2, 0.3) | 5.70 % | 1.95 % |
| 평면 \|v\| [0.3, 0.5) | 25.5 % | 6.2 % |
| 평면 \|v\| [0.5, 0.75) | 59.2 % | 13.5 % |
| 평면 \|v\| [0.75, 1.0] | 0 | 19.9 % |
| 평면 \|v\| > 1.0 | 0 | 49.1 % |
| \|vx\| < 0.2 (횡 위주 명령 포함) | 20.4 % | 17.5 % |
| 전진 우세 · 후진 우세 · 횡 우세 | 33.0 · 23.0 · 37.3 % | 32.3 · 23.2 · 36.6 % |
| wz = 0 | 5.8 % | 5.5 % |
| \|wz\| ≥ 0.5 | 53.3 % | 67.5 % |
| 정확히 (+상한, +상한) | 23.4 % | 20.5 % |
| 평면 두 성분이 모두 ±상한 | 36.3 % | 33.2 % |

Q-E1 셀 근처 비율 (선속도 ±0.05 · wz ±0.1):

| 셀 | 20k 전 | 20k 뒤 |
|---|---:|---:|
| stand | 0.56 % | 0.43 % |
| fwd01 | 0.010 % | 0.014 % |
| fwd02 | 0.014 % | 0.013 % |
| fwd03 | 0.022 % | 0.004 % |
| fwd05 | 0.012 % | 0.008 % |
| back03 · left03 · right03 | 0.012 · 0.021 · 0.012 % | 0.004 · 0.004 · 0 % |
| yawL05 · yawR05 | 0.58 · 0.59 % | 0.42 · 0.42 % |

지형별로는 거의 같다. 평면 (0, 0.2) 는 지형마다 2.4~3.1 % (20k 전) · 0.9~2.0 % (20k 뒤) 다. 이 범위에서는 지형별 상한 (`terrain_max_command_ranges`) 이 묶이지 않아, 모든 env 의 범위가 같았다.

### A.3 resample 시점과 그 이유

| 사건 (30 s, 4096 env) | 20k 전 | 20k 뒤 | 표본기가 본 episode 시간 | 나온 명령 |
|---|---:|---:|---|---|
| time-out 뒤 reset | 4,911 | 4,878 | 모두 25.0 s | 100 % 평면 두 성분이 ±상한, 85 % 가 정확히 (+상한, +상한), zero 0 % |
| 종료 (넘어짐) 뒤 reset | 22 | 104 | 2.6~23.9 s (20k 전) | 평면 속도 0.5 이상이 91 % (20k 전) · 0.75 이상이 77 % (20k 뒤) |
| 주기 resample | 20,387 | 20,218 | 5.02 s 간격 (251 step) + zero 명령 뒤 짧은 간격 | 아래 |

원인 (코드 · 확인됨):

- reset 에서 명령은 episode 길이를 0 으로 되돌리기 **전에** 다시 뽑힌다. `manager_based_rl_env.py:381` 에서 command manager 가 reset 되고, :394 에서야 `episode_length_buf` 가 0 이 된다.
- `commands.py:147` 의 하한은 `남은 거리 / ((max_episode_length − episode_length_buf + 1) × dt)` 다.
  - time-out 직후에는 남은 시간이 1 step (0.02 s) 으로 계산된다. 하한은 5 m / 0.02 s = 250 m/s 가 된다.
  - 그러면 `sample_disjoint_intervals` (`utils.py:110`~123) 의 두 구간 폭이 0 이 되어 표본이 상한값 (+0.5 또는 +1.0) 에 붙는다.
- 같은 이유로 zero 명령 경로의 `next_time_left` (:238) 가 0 이 되어, time-out 뒤 첫 명령은 zero 가 될 수 없다.
- 이 명령이 다음 resample 까지 5.02 s 를 간다. episode 대부분이 time-out 으로 끝나므로 학습 시간의 약 1/5 이 이 대각선 최고속 명령이다.

주기 resample 의 \|vx\| (20k 전): episode 5~10 s 에 \|vx\| < 0.2 가 32 %, 20~25 s 에 21 % 다. 중앙값은 0.30 → 0.44 로 커진다. 20k 뒤에는 24 % → 21 %, 중앙값 0.55 → 0.66 이다. 시간이 갈수록 하한이 다시 커지는 방향이다.

정지 (0, 0, 0) 이 없는 이유 (코드 · 확인됨, 측정과 일치):

- 동적 경로의 wz 는 연속 균등이라 0 이 될 확률이 0 이다.
- `limit_vel` (:367) 의 vx · vy 는 {−1, +1} 끝값만 있어 평면 0 을 만들지 않는다.
- zero 경로 (:234~258) 는 평면만 0 으로 하고 wz 는 앞서 뽑은 연속값이나 ±상한으로 둔다.

### A.4 해석

- **확인됨:** E1 은 정지 명령을 한 번도 받지 않았다. 0.1 m/s 근처의 순수 전진 명령은 시간의 0.01 % 수준이다. Q-E1 의 stand · stop · fwd01 셀은 학습 분포 밖이거나 극히 드문 영역을 잰다.
- **추정:** Q-E1 11절의 「0.1 m/s 에서 서 있음」 과 「정지 유지 실패」 는 이 분포 공백과 맞는 방향이다. 다만 분포를 바꿔 학습한 대조가 없으므로 원인으로 확정하지 않는다.
- **추정:** 20499 의 하락이 20k 뒤 범위 확대 직후라는 앞선 추정에 보탤 사실이 있다. 범위가 1.0 이 되면 매 episode 첫 5 s 의 명령은 (1.0, 1.0), 즉 1.41 m/s 대각선이 된다.
- **미확인:** E1 학습 중 실제 지형 레벨 (로그 평균 5.67) 은 이번 측정 (2.4~2.8) 보다 높다. 넘어짐이 더 잦으면 종료 reset 비중이 조금 커진다. 정책은 checkpoint 하나로 고정했다.

## B. resume 충실도

### B.1 방법

새 학습 run 네 개를 GPU 1 에서 돌렸다. 모두 1024 env · 시드 42 · `save_interval` 33 이다. 저장소의 `scripts/rsl_rl/train.py` 를 고치지 않고 `resume_probe.py` 로 감싸 실행했다. 감싼 부분은 runner 의 save · load · learn 에 상태 기록만 더한다. 작업 디렉터리를 `_eval/out/resume_test/` 로 두어 로그가 그 아래 `logs/` 에만 생겼다. E1 · E2 폴더는 건드리지 않았다.

| run | 명령 | 시간 |
|---|---|---:|
| cont | 0 → 200 (`--max_iterations 200`) | 640 s |
| split1 | 0 → 100 (`--max_iterations 100`) | 336 s |
| split2 | split1 `model_99.pt` 에서 `--resume`, `--max_iterations 100` | 333 s |
| fix2 | split2 와 같고, 후보 수정 (B.4) 을 probe 안에서만 적용 | 331 s |

저장마다 기록한 것: runner iteration · env `common_step_counter` · 명령 범위와 남은 curriculum 단계 · zero 명령 확률 · 지형 레벨 분포 · reward 가중치 전부 · episode 위상 · 알고리즘 `learning_rate` 와 optimizer 그룹 lr · Adam step · RNG (torch CPU · CUDA · numpy · python) hash · 모델 · optimizer hash.

### B.2 결과

**같은 시드 두 run 의 재현:** cont 와 split1 은 100 iter 저장 시점에서 기록한 모든 칸이 같다 (모델 · optimizer · RNG · 지형 레벨 · schedule). 이 설정의 학습은 프로세스 간 bitwise 재현된다 (확인됨). 그래서 아래 차이는 resume 이 만든 것이다.

**resume 직후 (split2, load 뒤) 와 연속 run 의 같은 시점 (cont, 100 update 뒤) 비교:**

| 항목 | 연속 (cont) | resume (split2) | 되살아남 |
|---|---|---|---|
| 모델 가중치 hash | 0286631e… | 0286631e… | 예 |
| 두 Adam 상태 (lr 그룹 2.96e-4 · step 2000) | 같음 | 같음 | 예 |
| 다음 iteration 번호 | 100 | 99 (마지막 번호를 한 번 더 씀) | 아니오 |
| env `common_step_counter` | 2400 (iter 100) | 0 | 아니오 |
| zero 명령 확률 | 0.0067 | 0 | 아니오 |
| reward 가중치 base_height_l2 · lin_vel_z_l2 | −1.18 · −1.867 | −1.0 · −2.0 | 아니오 |
| 지형 레벨 평균 | 0.77 | 2.53 (run 시작과 같은 분포) | 아니오 |
| 알고리즘 `learning_rate` | 2.96e-4 | 1.0e-3 (cfg 초기값) | 아니오 |
| CUDA RNG | 진행된 상태 | run 시작 때와 같은 상태 | 아니오 (처음으로 되감김) |
| episode 위상 · sim step counter | 진행 | 0 에서 다시 | 아니오 |

갈라지는 첫 지점과 원인 코드:

- **runner (확인됨):** `on_policy_runner_cts.py:167`~181 의 save 는 모델 · 두 optimizer · iter 만 담는다. :260~279 의 load 는 그것만 되살린다.
- **env counter (확인됨):** env counter 는 새 env 에서 0 으로 시작한다 (`manager_based_rl_env.py` 초기화). 이 counter 를 시계로 읽는 곳은 셋이다.
  - 명령 범위 · zero 확률: `commands.py:129` · :301
  - reward 가중치 schedule: `curriculums.py:186`
  - (이 env 에서는 쓰지 않는 다른 curriculum 함수)
- **learning rate (확인됨):** `moe_cts.py:120` 이 `learning_rate` 를 cfg 값으로 두고 :278~311 의 adaptive 규칙이 그 값에서 출발해 optimizer lr 을 덮어쓴다. resume 후 첫 update 의 lr 은 연속 run 의 약 3 배에서 시작했다. split2 는 반복된 iteration 99 하나를 마친 뒤 lr 3.9e-5 까지 내려갔다. 큰 KL 로 여러 번 깎인 값이라는 해석은 추정이다.
- **iteration 번호 (확인됨):** `learn` (:108~110) 은 불러온 번호 L 에서 L + `max_iterations` − 1 까지 돈다. split2 의 로그는 「99/199」 로 시작해 「198/199」 로 끝났다. 번호 99 가 두 번 쓰이고, 200 update 를 마친 모델 이름이 연속 run 은 `model_199`, resume run 은 `model_198` 이다. `--max_iterations` 는 누적이 아니라 추가다.
- **RNG · 지형 레벨 (확인됨):** 같은 시드로 env 를 새로 만들기 때문에 run 시작 때 값으로 돌아간다 (hash · 분포 일치).

**200 update 뒤:** split2 의 schedule 시계는 iter 100 에 머물러 있다. zero 확률 0.0067 (연속 0.0133), base_height −1.178 (연속 −1.36), lin_vel_z −1.868 (연속 −1.733) 이다. 차이가 100 iter 만큼 계속 밀려 간다.

### B.3 E1 부모 (iter 20000 근처) 에 그대로 resume 하면

코드 식으로 계산한 값이다. 작은 run 에서 같은 기전을 확인했다 (확인됨: 기전 · 추정: E1 규모의 학습 영향).

| 항목 | E1 연속 (iter ≥ 20000) | 그대로 resume 직후 |
|---|---|---|
| 명령 범위 vx · vy · wz | ±1.0 · ±1.0 · ±1.5 | ±0.5 · ±0.5 · ±1.0 (iter 20000 이 다시 올 때까지) |
| zero 명령 확률 | 0.1 | 0 에서 1500 iter 동안 0.1 로 |
| lin_vel_z_l2 가중치 | 0 | −2.0 에서 1500 iter 동안 0 으로 |
| base_height_l2 가중치 | −10 | −1.0 에서 5000 iter 동안 −10 으로 |
| 지형 레벨 | 평균 5.67 (로그) | 0~5 무작위 (평균 약 2.5) |
| 알고리즘 lr | 그 시점 adaptive 값 | 1e-3 에서 다시 |

즉 그대로 resume 하면 G1 · P1 의 양군은 E1 의 이어진 학습이 아니라 「다른 reward · 좁은 명령 범위의 새 단계」 에서 갈라진다. 이 차이가 gap 노출 효과와 섞인다.

### B.4 후보 수정과 그 시험 (저장소 밖, probe 안에서만)

resume 한 run 의 learn 직전에 다음을 넣었다 (fix2).

1. 다음 번호 = L + 1
2. `common_step_counter` = (L + 1) × 24
3. 알고리즘 `learning_rate` = optimizer lr
4. 지형 레벨과 RNG 를 checkpoint 옆에 저장해 둔 sidecar 에서 복원

결과:

- 번호는 100 에서 199 로 이어졌고, 연속 run 과 이름 · update 수가 같다.
- 시계 칸 (counter · zero 확률 · reward 가중치) 은 저장 시점 132 · 165 · 198 · 199 에서 연속 run 과 같다. 132 의 가중치만 −1.2394 대 −1.2376 이다. 가중치는 reset 때 갱신되는데 reset 시각이 달라서다.
- 모델 · optimizer · 지형 레벨의 이후 값은 다르다. 로봇의 물리 상태와 episode 위상이 이어지지 않으므로 bitwise 연속은 기대하지 않는다.
- env 의 `_sim_step_counter` 는 0 에서 다시 시작한다. 이 env 설정의 event 는 이 값을 쓰지 않는다 (cfg 확인 · 영향은 미확인).

## C. G1 을 E1 부모에서 가르려면

1. **꼭 고칠 것 (확인됨):**
   - resume 직후 env `common_step_counter` 를 (L + 1) × 24 로 둔다. 이것 없이는 명령 범위 · zero 확률 · reward 가중치 schedule 이 처음으로 돌아간다.
   - 알고리즘 `learning_rate` 를 optimizer lr 로 맞춘다.
   - 다음 iteration 번호를 L + 1 로 둔다.
   - 셋 모두 저장소 밖 실행기에서 할 수 있고, fix2 로 시험했다.
2. **정해야 할 것:**
   - E1 은 지형 레벨과 RNG 를 저장하지 않았다. 레벨은 로그 평균 5.67 만 남아 있다. G1 양군에 같은 규칙 (예: 새 curriculum 으로 다시 시작) 을 정하고 동결한다.
   - RNG 는 양군마다 선언한 시드로 새로 시작한다. 이것은 「E1 의 이어짐」 이 아니라 「같은 부모 가중치에서 새 시드로 갈라짐」 이라고 부른다.
3. **예산:** `--max_iterations` 는 추가다. 「총 N iter 까지」 로 적으면 예산이 그만큼 늘어난다.
4. **명령 분포 (A 절):** 매 episode 첫 5 s 의 (+상한, +상한) 대각선과 정지 명령 부재는 G1 의 gap 노출과 별개로 학습 분포를 정한다. 명령 생성을 바꾸려면 양군 공통으로 바꾸고 별도 대조로 둔다. 이번에는 아무것도 바꾸지 않았다.

## D. 재현과 자원

```
cd C:/isaac/ext/go2_rl_robotlab/_eval
bash run_cmd_dist.sh test && python cmd_analyze.py test --expect_test
bash run_cmd_dist.sh runs && python cmd_analyze.py pre20k && python cmd_analyze.py post20k
bash run_resume_test.sh all && python resume_compare.py
```

- 원자료: `out/cmd_dist/{test,pre20k,post20k}/` (사건 기록 · 매 step 명령 · summary), `out/resume_test/logs/rsl_rl/go2_moe_cts/*_rt_*` (checkpoint · `*.state.json` · sidecar · train.log), `out/resume_test/compare.json`.
- GPU 1 만 썼다. A 약 11 분 · B 약 27 분이다. 기록한 최대 사용은 11.2 GB (A 4096 env 중, 여유 5.1 GB) 이다.
- GPU 0 (E2) 와 pid 25916 은 건드리지 않았다.
- resume 시험 로그는 약 0.5 GB 다.
- 처음 짠 resume 명령은 checkpoint 이름 정규식 `model_99.pt` 가 옆의 `.state.json` 까지 잡을 수 있었다 (`parse_cfg.py:210`~217 은 match 후 정렬해 마지막을 고름). 실행 전에 `model_99.pt$` 로 고정했다. 이 저장소에서 checkpoint 옆에 다른 파일을 두면 같은 함정이 있다.

## E. 못 잰 것

- 명령 분포를 바꿔 학습했을 때 정지 · 저속 능력이 나아지는지 (대조 학습 없음).
- E1 학습 중 실제 지형 레벨 · 넘어짐 비율에서의 분포 (이번 레벨 평균 2.4~2.8).
- 8192 env 에서의 값 (지형 열 비율은 같게 둠).
- 수정한 resume 으로 E1 규모 (iter 20000) 에서 이어 학습한 결과. 이번 시험은 iter 100 → 200 의 작은 run 이다.

## lead 재검 (10/11)

- 코드에서 직접 확인했다: Isaac Lab `envs/manager_based_rl_env.py` 의 `_reset_idx` 는 `command_manager.reset` (381 행 부근) 을 부른 **뒤에** `episode_length_buf[env_ids] = 0` (394 행 부근) 을 한다. robot_lab `tasks/go2/mdp/commands.py:141`~160 의 하한은 `remaining_dist / ((max_episode_length - episode_length_buf + 1) * step_dt)` 라 time-out 직후에는 분모가 1 step 이 된다. `mdp/utils.py:110` `sample_disjoint_intervals` 는 하한이 상한보다 크면 두 폭이 0 이라 `cfg_max` 를 낸다. 그래서 vx · vy 가 모두 +상한에 붙는다. 문서 결론과 같다.
- 정지 · 저속 약점의 원인이라는 것은 추정이다 (분포를 바꾼 대조 학습 없음). 공개 MoE-CTS 결과도 이 코드로 학습됐을 것이므로, 재현은 그대로 두고 고친 분포는 별도 개입 실험으로 다룬다.
- **정정 (ASTRA 6 · `VERIFY-astra-6.md` 1절):** 「매 episode 첫 5.02 s 가 (+상한, +상한)」 은 과하다. time-out reset 4,911 · 4,878 건 중 최종 명령이 +상한 근처인 것은 85.4 % · 84.8 % 다 (뒤 단계 limit_vel 이 일부를 바꿈). 「time-out 직후 sampler 가 +상한으로 치우치고 대개 약 5 s 유지」로 읽는다. 23.4 % · 20.5 % 는 4096 env · env 당 30 s 의 별도 rollout 측정이며 E1 학습 전체 시간 비율이 아니다. 「정지 0 %」 는 설정상 완전 정지를 할당하는 경로가 없다는 뜻이다 (zero 처리는 vx · vy 만 0 으로 하고 wz 는 유지).
