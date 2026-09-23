> 분류: 리서치
> 작성: jay · 2026-09-23 23:59
> 근거: 실측 · 실행 로그 · rsl_rl 소스
> 요지: seed 43에서 1577에 critic loss 급증이 기록됐지만 offending env와 최초의 수치 원인은 특정할 수 없으며, checkpoint resume을 통한 짧은 재현은 검증이 필요하다
> 상태: 조사 중
> 판: v1.0

표기: `확인됨`은 파일 또는 checkpoint를 직접 읽어 확인한 사실, `실측`은 원자료에서 직접 계산한 값, `판단`은 위 사실에서의 해석, `미확인`은 현재 자료로 판정할 수 없는 항목이다.

원 출처: [rsl_rl PPO source](https://github.com/leggedrobotics/rsl_rl/blob/master/rsl_rl/algorithms/ppo.py), [rsl_rl runner source](https://github.com/leggedrobotics/rsl_rl/blob/master/rsl_rl/runners/on_policy_runner.py), [Isaac Lab reinforcement learning scripts](https://github.com/isaac-sim/IsaacLab/tree/main/scripts/reinforcement_learning/rsl_rl). 실제 수치의 원자료는 문서에 적은 로컬 `C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_gap_nvidia` 아래 실행 폴더다.

# 시드 43 발산 조사

## 결론

`seed 43`에서 같은 현상이 두 번 관측된다. `s`와 `s2`는 seed, 시뮬레이터 장치, 설정이 같고 checkpoint의 모델 tensor가 `model_0`, `model_1550`, `model_1575`, `model_1600`, `model_1650`에서 모두 비트 동일했다. 이는 `(seed 43, sim cuda:1)` 조건의 반복성을 강하게 지지한다. 다만 저장되지 않은 rollout과 minibatch까지 비트 동일하다는 것은 확인되지 않았다.

다만 현재 자료로 확정할 수 있는 뿌리는 여기까지다. `Train/mean_reward`와 `Train/mean_episode_length`는 최근 100개 완료 episode를 요약하지만, `Loss/value_function`, `Episode_Reward/*`, termination 지표는 각각 별도 방식으로 집계된다. `Loss/value_function`은 5 epoch × 4 minibatch, 즉 20개 minibatch loss의 평균이다. `Episode_Reward/*`는 reset 대상 env의 누적 reward 평균을 최대 episode 시간으로 나눈 뒤 runner에서 다시 평균한다. termination 지표는 전체 env의 마지막 종료 사유를 평균한 값이며, 해당 iteration에서 끝난 episode의 비율로 읽으면 안 된다. env별 reward, rollout transition, minibatch별 return, KL, gradient는 보존하지 않는다. 그러므로 seed 43이 만든 특정 상황이 reward outlier인지, critic target 또는 bootstrap의 outlier인지, critic의 특정 minibatch인지 구분할 수 없다. offending env와 최초의 비정상 tensor는 미확인이다.

현재 자료에서 확인되는 시간 순서와 그에 대한 가설은 다음과 같다.

1. **미확인 가설**: seed 43의 rollout 안에 현재 평균 지표로 드러나지 않는 outlier transition 또는 return이 생겼을 수 있다.
2. **확인됨**: iteration 1577에 기록된 critic value loss가 0.028에서 0.923으로 변한다.
3. **판단**: 이후 value loss가 1578에서 5.558, 1581에서 667.598로 증폭된다. critic update가 원인인지 단순 동반 현상인지는 미확인이다.
4. **확인됨**: 그 뒤 action-rate reward가 1580에서 -0.285, 1581에서 -2.547, 1584에서 -23.891, 1587에서 -328.589로 변하고, mean reward가 1581에서 -29.154로 크게 튄다.

즉 현재 관측으로는 환경 전체가 먼저 무너졌다고 말할 근거가 없다. 추종 reward, episode length, termination 비율은 1577 전후에 정상 범위다. 확인 가능한 것은 critic value loss 기록이 action-rate와 mean reward의 큰 이상보다 먼저 변했다는 시간 순서뿐이다. critic update가 policy 손상의 원인이라는 인과는 미확인이다.

## 원자료 대조

대상 실행은 다음 네 개다.

| 실행 | agent seed | sim device | network device | 결과 |
|---|---:|---|---|---|
| `2026-09-21_11-03-28_20260921_v2b_seed42_iter3000` | 42 | `cuda:1` | `cuda:0` | 완주 |
| `2026-09-23_14-42-33_20260923_v2b-r_seed42_iter3000` | 42 | `cuda:0` | `cuda:0` | 완주 |
| `2026-09-23_14-42-37_20260923_v2b-s_seed43_iter3000` | 43 | `cuda:1` | `cuda:0` | 1670 부근에서 중단 |
| `2026-09-23_17-08-57_20260923_v2b-s2_seed43_iter3000` | 43 | `cuda:1` | `cuda:0` | 1670 부근에서 중단 |

근거 파일은 각 실행의 `params/agent.yaml` 1, 2행과 `params/env.yaml` 20, 83, 86행이다. 네 `agent.yaml`을 seed, device, run_name, log_dir를 변수로 놓고 비교하면 PPO 설정과 network 구조는 같다. `env.yaml`도 log_dir와 seed, sim device를 제외하면 같다. `IsaacLab.diff`의 SHA-256은 네 실행 모두 `a89ba03510cc9add7a65716f65872dc17382fd7017e980e7bacccede066b1917`이며, 저장된 diff 내용도 같다.

이 비교에서 주의할 점은 seed 42의 두 실행은 seed가 같아도 sim device가 `cuda:1`과 `cuda:0`으로 다르다는 것이다. 두 checkpoint는 model_0부터 이미 달라진다. 따라서 두 device에서 model_0부터 차이가 난다는 사실은 device 차이 가능성과 부합하지만, 내부 계산 순서가 원인이라는 것은 확인되지 않았다. seed 43의 발산을 seed 하나의 필연적 원인이라고 분리해서 증명하지도 못한다. seed 43에서 sim device를 고정한 두 실행이 비트 동일하다는 사실은 반복성을 지지한다.

## TensorBoard 실측

로그 경로는 `C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_gap_nvidia`이다. 사용자가 제시한 `C;C:\Program Files\Git\isaac` 표기는 Git Bash의 `/c/isaac`를 가리키는 것으로 해석했으며, 실제 존재하는 원자료는 위 Windows 경로에서 읽었다.

과거 seed 42 12개 실행에서는 `Loss/value_function` 최대가 0.044에서 0.538 사이였고 1 초과 값이 없었다. 이 중 `smoke4096`은 10 iteration, `katB`는 2 iteration뿐이므로 장시간 정상 실행과 같은 검증 근거로 쓰지 않는다. seed 43의 두 실행은 최대가 `inf`이며 1 초과 값이 93개이고, 1 초과의 첫 step은 1578이다. 1577의 값 `0.9225357`도 직전 값 `0.0284830`보다 32.4배 크므로, 1577은 급증이 기록된 update로 적는다.

| step | `Loss/value_function` | `Train/mean_reward` | `Train/mean_episode_length` | `Episode_Reward/action_rate_l2` |
|---:|---:|---:|---:|---:|
| 1575 | 0.025707 | 28.773 | 954.61 | -0.100261 |
| 1576 | 0.028483 | 30.110 | 995.14 | -0.110286 |
| 1577 | 0.922536 | 29.199 | 969.45 | -0.107403 |
| 1578 | 5.557724 | 29.673 | 980.16 | -0.107525 |
| 1580 | 84.066666 | 24.881 | 979.16 | -0.285430 |
| 1581 | 667.598389 | -29.154 | 973.56 | -2.546513 |
| 1584 | 178740.859375 | -427.054 | 977.10 | -23.891041 |
| 1587 | 2016038.625 | -11007.805 | 967.66 | -328.589355 |

1577의 `track_lin_vel_xy_exp`, `track_ang_vel_z_exp`, `error_vel_xy`, `error_vel_yaw`, `time_out`, `base_contact`, `fell_below_terrain`은 각각 약 1.35, 0.63, 0.24, 0.32, 0.958, 0.040, 0.002 수준이다. 이 평균만으로는 전체 episode가 동시에 무너졌다는 설명이 맞지 않는다. 반대로 평균은 소수 transition의 이상값을 숨길 수 있으므로, 특정 env가 정상이라는 증거도 아니다.

발산 시작 구간인 1575-1587의 iteration 종료 기록에서 `Loss/learning_rate`는 `1e-5`였다. 이후 두 실행 모두 1612에서 약 `1.5e-5`, 1614에서 약 `1e-2`로 변한다. `params/agent.yaml`의 adaptive schedule은 `desired_kl: 0.01`, `max_grad_norm: 1.0`이다. 따라서 1577 직전의 종료 기록만으로 learning rate가 원인이 아니라고 배제할 수 없다. KL과 minibatch별 learning rate와 gradient가 기록되지 않아 기여도는 미확인이다.

## checkpoint와 resume 판정

`model_1550.pt`는 단순 policy weight만이 아니다. `torch.load`로 확인한 최상위 key는 `model_state_dict`, `optimizer_state_dict`, `iter`, `infos`이고 `infos`는 `None`이다. Adam optimizer에는 17개 parameter state가 있고 각 state의 key는 `step`, `exp_avg`, `exp_avg_sq`다. `param_groups`는 optimizer state dict에서 `state`와 나란히 있다. seed 43의 model_1550에서 optimizer step은 `61020`, parameter group learning rate는 `1e-5`였다.

현재 설치된 rsl_rl의 `runners/on_policy_runner.py` 291-326행은 저장 시 optimizer state를 함께 저장하고, load 시 309행의 `load_optimizer=True` 기본값과 317-319행으로 optimizer state를 복원하며 323-325행으로 current iteration을 복원한다. 그러므로 이 실행 설정으로 `model_1550.pt`에서 resume하면 Adam moment와 optimizer의 parameter-group learning rate는 복원된다. 그러나 `ppo.py` 122행의 별도 `self.learning_rate` 변수는 checkpoint에 없고 YAML의 `0.0001`로 다시 초기화된다. 다음 adaptive update가 이 값을 사용하므로 원래 실행과 학습률 상태가 완전히 같다고 할 수 없다.

`model_1550.pt`를 읽어 30 iteration을 요청하면 runner의 `range(start_iter, start_iter + 30)` 특성상 번호는 1550부터 1579까지가 대상이며 1577 번호에 도달한다. 이것은 번호상 재현 창을 제공하는 것이지, 저장되지 않은 환경·RNG 상태까지 원래 실행과 동일하게 재현한다는 뜻은 아니다.

resume이 복원하지 않는 것은 checkpoint에 저장되지 않은 simulator 내부 상태와 RNG 상태다. checkpoint key에 env buffer, CUDA RNG, Python RNG, NumPy RNG가 없다. 따라서 model_1550에서 계측판을 시작하는 것은 조사 비용을 낮추는 제안이지만, 같은 crash를 보장하지 않는다. RNG와 rollout 시작 상태를 함께 덤프해야 bit-perfect replay를 시험할 수 있다. 학습을 실행하지 않았으며, 실제 재실행은 제안만 한다.

`s`의 `Perf/collection time`은 1575-1578에서 약 3.75-3.93초, `Perf/learning_time`은 약 0.24-0.29초다. `s2`는 각각 약 3.60-3.63초와 0.134-0.143초다. 기존 비계측 실행 기준으로 30 iteration의 순수 반복 시간은 대략 2분 안팎이며 simulator 시작, checkpoint load, 추가 계측과 snapshot 저장 비용은 포함하지 않았다. 실제 시간은 GPU와 초기화 비용에 따라 미확인이다.

## 다음 계측안

계측은 GPU를 사용하지 않는 정적 제안으로 남긴다. 가장 중요한 위치는 현재 설치된 `rsl_rl/algorithms/ppo.py`의 update loop다.

### update 직전

설치 소스에서 `loss.backward()`는 365행이다. gradient가 clip되기 전인 376행의 `clip_grad_norm_` 호출 직전에 다음을 수집한다. clip 뒤에는 반환값으로 얻은 전체 pre-clip norm만 남으므로 actor·critic별 norm과 parameter별 최대 gradient는 반드시 clip 전에 계산한다.

- update 번호, epoch, minibatch 번호
- `loss`, `surrogate_loss`, `value_loss`, `entropy`의 finite 여부와 값
- `value_batch`, `target_values_batch`, `returns_batch`, `advantages_batch`의 min, max, mean, 표준편차, absolute max, finite count
- `torch.isfinite` 실패 count와 offending tensor의 batch index
- clip 전 전체 gradient norm, actor gradient norm, critic gradient norm, 각 parameter의 max gradient
- Adam의 해당 parameter `exp_avg`, `exp_avg_sq`, `step` 요약
- policy ratio, old/new value의 범위와 `kl_mean`

`clip_grad_norm_`의 반환값은 clip 전 total norm이다. 이를 저장하되, per-module 값은 별도로 clip 전에 계산한다.

### rollout에서 update로 넘어갈 때

`OnPolicyRunner.learn`의 `env.step` 주변과 `compute_returns()` 뒤에는 trigger window에서만 다음을 저장한다. 종료 env는 `manager_based_rl_env.py` 221행에서 reset되므로 runner 바깥의 step 전후만으로는 reset 직전 상태를 보존할 수 없다. 환경 내부의 `record_pre_reset` 또는 `_reset_idx` 직전에 상태를 복사하고, step 호출 전 observation과 종료 직전 observation, reset 후 observation을 구분해 저장한다.

- env id별 reward와 각 reward term, action, pre-reset observation, done, timeout, reset ids
- action-rate term의 env별 min/max와 해당 env id
- value prediction, next value, return, episode length, rollout의 env id와 time index
- rollout tensor의 shape, device, dtype
- Python, NumPy, torch CPU, CUDA RNG state
- `episode_length_buf`, reset ids, terrain level 등 reset과 curriculum 상태
- `rollout_storage.py` 167-186행의 minibatch permutation과 각 minibatch의 원래 env id·time index

minibatch의 `value_loss`, return, gradient가 threshold를 처음 충족하는 시점에 해당 minibatch의 `optimizer.step()` 직전에 `torch.save`로 snapshot을 남긴다. 1577 이전 snapshot이 필요하면 별도의 예정된 checkpoint로 둔다. `Loss/value_function`은 20회의 minibatch update 뒤에 기록되므로 iteration 종료 로그를 보고 그 iteration의 update를 사전에 막을 수는 없다. iteration 전체를 취소하려면 해당 iteration 시작 checkpoint와 optimizer state로 rollback해야 한다. snapshot에는 model, optimizer, rollout transition, reset 전 상태, return 계산 결과, minibatch index, RNG를 함께 넣는다. 그래야 `reward outlier`, `bootstrap outlier`, `critic-only numerical issue`를 구분할 수 있다.

## 발산 관문

현재 rsl_rl에는 이미 `ppo.py` 376행의 `clip_grad_norm_(..., 1.0)`이 있다. 이것은 gradient norm을 제한하지만, update를 적용하기 전에 non-finite gradient를 거부하거나 value target의 이상치를 막지는 않는다. 다음 두 관문을 권한다.

1. **중단 관문**: minibatch의 `value_loss` 또는 `returns_batch`, `value_batch`, gradient norm이 non-finite이거나, 사전 정의한 robust baseline 대비 급증하면 `optimizer.step()` 전에 snapshot을 남기고 중단한다. iteration 종료의 `Loss/value_function`은 사전 관문 입력으로 쓰지 않는다.
2. **갱신 건너뛰기 관문**: `loss.backward()` 뒤, 376행의 clip 전에 gradient norm이 non-finite이거나 정한 상한을 넘으면 `optimizer.step()`을 호출하지 않고 해당 minibatch를 skip한다. 이미 이전 minibatch가 갱신한 모델과 optimizer를 iteration 전체에서 되돌리려면 시작 checkpoint가 필요하다. value target과 return도 같은 finite 검사 대상이다.

`Loss/value_function`만 TensorBoard에서 감시하는 외부 watchdog은 rsl_rl을 고치지 않고 프로세스를 중단할 수 있다. 그러나 특정 update만 건너뛰려면 optimizer.step 직전의 gradient와 return을 검사해야 하므로 알고리즘 hook, subclass 또는 rsl_rl의 국소 수정이 필요하다. YAML만으로 update skip을 구현할 수는 없다.

정상 학습을 잘못 멈추지 않는지 확인하는 방법은 다음과 같다.

- 기존 seed 42의 12개 로그를 shadow mode로 재생해 iteration 단위 관문 발동 step을 센다. 이것만으로 minibatch 관문의 false positive를 검증했다고 말하지 않는다.
- loss, return, gradient에 유한한 정상 범위와 경계값을 넣는 CPU unit test를 만든다. non-finite, 8배 상승, norm 초과, 정상 minibatch를 각각 시험한다.
- 정상 seed 42 한 판은 enforcement 없이 계측만 켜고, 같은 checkpoint와 동일한 최종 metric을 비교한다.
- seed 43 계측판에서는 조건을 처음 충족한 minibatch의 `optimizer.step()` 직전에 snapshot이 생기고 관문 정책대로 중단 또는 skip되는지 확인한다. 1577 이전 저장은 별도 예정 checkpoint로 확인한다.

## 자료만으로 답할 수 없는 것

현재 자료만으로 `seed 43이 특정 terrain, command, env id에서만 실패했다`고 말할 수 없다. 같은 terrain과 command 분포라는 설정은 확인되지만 표집 결과와 env별 상태는 저장되지 않았다. 또한 TensorBoard에는 minibatch KL, pre-clip gradient, optimizer moment의 시계열이 없다. 그러므로 다음 재현 계측 없이는 뿌리 원인을 하나로 확정하면 안 된다.

- offending env id와 transition index
- 그 transition의 observation, action, reward term, done, timeout
- critic return과 bootstrap value
- update epoch와 minibatch 번호
- pre-clip gradient norm 및 critic parameter별 gradient
- RNG와 reset/curriculum 상태

현재의 가장 정확한 판정은 다음이다. **두 seed 43 실행에서 같은 checkpoint tensor와 같은 발산 시계열이 관측된다. 1577에서 기록된 critic loss 급증이 reward 평균의 큰 이상보다 먼저다. 그러나 최초의 비정상 입력은 현재 원자료에 없고 model_1550 resume도 환경·RNG·adaptive learning-rate 상태를 완전히 복원하지 않으므로 root cause와 짧은 replay 성공은 미확인이다.**
