> 분류: 리서치 · A/정책학습
> 작성: ASTRA (lead 의뢰 ASTRA-S2R) · 2026-10-21
> 근거: sonnet 5ddead46 코드 · 설치 rsl_rl 3.1.2 · EX-01/09/10 저장 YAML·TensorBoard·체크포인트 · CPU 답 아는 시험
> 요지: 명령 누락·PPO 재계산·KL 혼입은 확인되지 않았다. 환경도 다른 비교이며, 지각 갱신의 정책 변화와 잠재변수 표집 차이는 따로 가려야 한다.
> 상태: CPU 분석 완료 · 정지의 단일 원인 미확정 · GPU·Kit 미실행 · 코드 수정 없음

# S2-G0 runner와 표준 PPO 대조

## 확정

**“같은 env에서 runner만 바꿨는데 멈췄다”는 전제가 저장 설정과 다르다.** EX-09·10은 EX-01보다 actor뿐 아니라 지형·승급·관측·표본 수·종료 여유·clip이 바뀌었다. 두 명령 판 모두 실패했다는 사실은 두 판의 공통 부분을 의심할 근거지만, runner를 원인으로 확정하지 못한다.

**직접 의심한 명령 누락, PPO 갱신 때 est 재계산, 지각 KL의 adaptive scheduler 혼입, GAE·done 배선 오류는 이번 코드 대조와 CPU 시험에서 재현되지 않았다.** 확인한 차이는 다음과 같다.

- 수집 actor 입력의 명령은 `6:9`에 그대로 있다. 저장 입력으로 첫 PPO ratio를 재면 오차가 `0.0`이다. 지각망을 인위적으로 바꿔도 저장 입력의 ratio는 변하지 않는다.
- adaptive KL은 저장 행동 Gaussian과 현재 actor Gaussian 사이의 KL이다. I-E의 표준정규 prior KL과 다른 값이다. 다만 **PPO 뒤 지각 갱신이 다음 수집의 전체 정책을 바꾸는 양은 이 KL에 들어가지 않는다.** 계산 계약의 감시 공백이며 정지 원인이라는 결론은 아직 아니다.
- 평가 `S2_SAMPLE=1`도 잠재변수 z는 평균으로 고정한다. “학습과 같은 표집” 대조가 아니다. 코드 주석의 의미가 실제 동작과 다르다.
- S2 critic은 noise가 들어간 policy의 몸 관측을 재사용한다. EX-01 critic의 몸 관측은 noise가 없다. actor·critic 크기뿐 아니라 입력 품질도 다르다.

동일한 합성 rollout·초기 weight·minibatch RNG로 표준 ActorCritic+PPO와 S2의 PPO 구간을 한 update 비교했다. 갱신 후 weight 최대 차 `0.0`, loss dict와 adaptive learning_rate도 정확히 같았다. 실제 수집 입력을 생산하는 환경·지각의 동등성까지 보장하는 시험은 아니다.

**CPU 검증: 기존 시험 18개와 이번 독립 진단 22개, 합계 40개 통과.** 이는 배선·산술·작은 가짜 환경 시험이다. 실제 지형 위 보행을 CPU로 재현했다는 뜻이 아니다. 새 GPU·Kit·학습·평가·렌더는 실행하지 않았다.

### 근거와 범위

`S`는 `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code`, `W`는 `C:/mai/wt/foothold-lab/astra2-s2r`, `R`은 `C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl`이다. 상대 코드 경로는 W 안의 파일이고, 요청된 다섯 파일은 S와 바이트 해시가 일치했다. W는 sonnet 커밋 `5ddead4684c0c2ea64d0a261fd42b3b543139d7f`에서 만든 `feature/astra2-s2r-jay`다. 공유 체크아웃·sonnet의 미커밋 변경은 건드리지 않았다.

| 약호 | 실제 경로 |
|---|---|
| SR | `foothold_s2/runners/start_runner.py` |
| PR | `foothold_s2/runners/perception_replay.py` |
| SP | `foothold_s2/models/start_policy.py` |
| PE | `foothold_s2/models/start_perception.py` |
| RF | `foothold_s2/models/replay_fast.py` |
| TS | `foothold_s2/scripts/train_start.py` |
| EA | `foothold_s2/eval/adapters.py` |
| A1 / E1 | `S/logs/rsl_rl/foothold_s1a/2026-10-20_16-59-25_s1a_scan/params/agent.yaml` / `env.yaml` |
| A9 / E9 | `S/logs/rsl_rl/foothold_s2_diag/2026-10-21_16-14-13_diag-G0-open/params/agent.yaml` / `env.yaml` |
| A10 / E10 | `S/logs/rsl_rl/foothold_s2_diag/2026-10-21_16-14-13_diag-G0-start/params/agent.yaml` / `env.yaml` |

각 실행 폴더의 `events.out.tfevents.*`와 S2의 `model_1500.pt`를 CPU로 읽었다. TensorBoard는 태그·step, 체크포인트는 키로 식별한다. 저장 YAML은 실행 설정의 근거지만 실행 당시 전체 소스가 현 파일과 바이트 단위로 동일했다는 증거를 대신하지 않는다. 이번에는 실행 당시 전체 source manifest를 확보하지 못했다. 버전은 isaac311의 `importlib.metadata.version('rsl-rl-lib') = 3.1.2`를 직접 확인했다. 아래 “확정”은 이 범위의 코드·저장 자료·CPU 결과이며 현장 동역학 인과를 뜻하지 않는다.

### 비교 조건부터 바로잡기

| 항목 | EX-01 scan | EX-09 open / EX-10 START | 근거 |
|---|---|---|---|
| env 수 × rollout | 4096 × 24 = 98,304 | 3072 × 24 = 73,728 | E1/E9/E10:86, 각 A `num_steps_per_env`. 같은 update 수도 경험량은 S2가 75% |
| 지형 | 23열, 이어진 7종 | 50열, sparse·flat 포함 13종 | E1:108~205, E9/E10:108~259. S1 지형군 비율 합 0.46을 정규화한 것과 S2 혼합은 다른 분포 |
| 승급 | terrain_levels_mixed | terrain_levels_s2, T_start=1000, T_end=8000 | E1:1224, E9/E10:1829~1832. terrain level 숫자의 분포도 같은 과제를 나타내지 않음 |
| 명령 | 정적 flag_stride=5, dynamic_flags=false | open은 dynamic_flags=true·물러나기 포함, START는 flag_stride=0·start_mode=true | E1:1245, E9/E10:1852 및 `/commands/base_velocity/params`; `s2_env_cfg.py:36~44·83~91` |
| actor | o45 + 높이 스캔187 = 232 | o45 + I-E51 = 96, G0 지도 입력 없음 | `s1_env_cfg.py:86~96`, `s2_env_cfg.py:54`, SR:140~146, SP:16~30 |
| critic | 잡음 없는 o45 + v3 + contact4 = 52 | 잡음 있는 o45 + v3 + contact4 + map512 + footmap100 = 664 | `s1_env_cfg.py:101~112`, SR:132·145~146. S2 env의 clean critic 묶음은 있어도 runner가 사용하지 않음 |
| 발 아래 종료 여유 | 0.20 m | 0.25 m | E1:1220, E9/E10:1825 |
| action scale / wrapper clip | 0.25 / 없음 | 0.25 / ±17 | E1:730, E9/E10:1335, A의 `clip_actions` |
| PPO·초기 noise·MLP 폭 | lr .001 adaptive, KL .01, 5 epoch×4 minibatch, std1, 512/256/128 ELU | 같은 값 | A1/A9/A10의 `algorithm`, `policy`. 단 총 batch와 입력 차원·실제 초기 난수는 다름 |

보상 **가중치** 14항은 E1:987~1137과 E9/E10:1592~1742에서 일치한다. 그러나 지형·명령·방문 상태가 다르므로 각 항이 주는 실제 비용·추종 보상은 같지 않다. EX-09·10끼리는 저장 env에서 명령 설정이 핵심 변경이지만, 그 둘의 실패를 EX-01과 연결해 신경망 하나의 효과라고 부를 수 없다.

### (a) 명령 전달과 PPO 입력 고정

| 검사 | 코드 근거 | CPU 결과·판정 |
|---|---|---|
| o_t에 명령이 존재하는가 | `s1_env_cfg.py:86~91`: ang_vel3·gravity3 다음 generated_commands3. `s2_env_cfg.py:54`는 height_scan만 제거. `sensors/start_obs.py:76~105`는 policy를 재배열하지 않음 | command `(0.3,−0.2,0.7)`을 넣어 `_ppo_obs`의 `actor_in[:,6:9]`와 완전 일치. 명령 전용 gating이나 삭제 없음 |
| est를 PPO 때 새로 만드는가 | SR:219~230 수집, `R/algorithms/ppo.py:143~154` 관측 보관, `R/storage/rollout_storage.py:84` copy, `R/algorithms/ppo.py:170~207·248~252` 저장 minibatch 사용 | 초기 ratio 오차 0.0. 지각 heads bias를 +10 바꿔도 같은 저장 입력 ratio 불변. PPO update 동안 perception.step을 오류 함수로 바꿔도 호출하지 않고 완료 |
| 지각·PPO 순서와 optimizer | SR:248~255, 284~303; SP:3~5 | PPO 뒤 지각 갱신. PPO optimizer에 지각 파라미터 없음. 기존 시험과 독립 시험 모두 PPO가 지각 가중치를 바꾸지 않음 |
| rollout 마지막 est=0은 잘못된 bootstrap인가 | SR:248; `_ppo_obs` critic은 est를 안 씀; `R/algorithms/ppo.py:187~191`은 evaluate만 호출 | 같은 raw에서 est=0과 est=999의 value 완전 일치. 현재 구조에서는 bootstrap 오류가 아님 |

actor가 명령을 받는다는 것은 명령을 잘 따른다는 뜻은 아니다. 실제 S2 checkpoint에 정적 합성 몸 관측을 주고 est를 고정한 채 vx만 +0.5→−0.5로 바꾸면 action 평균 RMS 차이는 open `0.158032`, START `0.097617`이었다. **상수 정책이나 명령 배선 완전 단절은 아니다.** 이 입력은 실제 rollout 분포가 아니므로 추종률·충분한 민감도의 증거로 쓰지 않는다.

### (b) KL·학습률: 혼입은 없고 감시하지 않는 변화가 있다

`R/algorithms/ppo.py:258~292`는 다음 식을 minibatch마다 계산한다.

`KL_policy = mean_batch Σ_action [log(σ_new/σ_old + 1e−5) + (σ_old² + (μ_old−μ_new)²)/(2σ_new²) − 1/2]`.

`desired_kl=.01`일 때 `KL>.02`면 lr을 `/1.5`, `0<KL<.005`면 `×1.5` 한다. 범위는 `[1e−5,1e−2]`. 이는 actor의 행동분포이며 PE:173~176의 `KL(N(z_mu,z_var)||N(0,I))`가 아니다. 지각 loss는 PPO update가 끝난 뒤 `loss_dict['perception/...']`에 합쳐 **로그만** 남긴다(SR:251~257). optimizer와 lr 필드도 다르다(SR:86~88·157·303).

CPU에서 std=1인 행동 12차원의 old mean을 0.3만 옮긴 대조는 이론 KL `12×0.3²/2=0.54`이고 lr `.001→.000666667`, 동일 분포는 구현 epsilon 때문에 작은 양의 KL이 나와 `.001→.0015`였다. 표준 구현 그대로이며 지각 KL이 scheduler로 전달되는 경로는 없다. 단일 마지막 lr만으로 KL 분포나 손실 원인을 복원할 수 없고, 현재 표준 로그에는 minibatch별 policy KL이 없다.

**감시 공백:** 실제 정책은 `πθ(a | o, fφ(history))`다. PPO는 저장된 `fφ_old`로 θ의 변화만 제한한다. 그 뒤 감독 손실로 φ를 바꾸면 θ를 그대로 두어도 다음 행동분포가 바뀐다. 다음 rollout은 새 분포를 old로 저장하므로 앞 iteration 경계의 변화가 scheduler에 사후로 들어오는 것도 아니다. 이는 “PPO 도중 입력 재계산 버그”와 다른 현상이다.

합성 replay에서 actor를 완전히 고정하고 지각만 한 번 갱신한 뒤, 같은 history·결정론적 z에 대해 행동 Gaussian KL 평균 `0.00636382`를 얻었다. actor state_dict는 완전 동일했다. **변화 가능성과 현재 감시 범위는 CPU로 확정했지만, EX-09·10의 실제 변화 크기 및 정지에 대한 인과는 미측정**이다. 이 수치를 실제 학습의 KL로 인용하면 안 된다.

### (c) log_prob·value·GAE·보상·done·GRU

| 항목 | 대조와 판정 |
|---|---|
| 행동 log_prob | SP는 표준 ActorCritic을 상속. `R/modules/actor_critic.py`의 Normal.log_prob를 행동 차원 합산하며, 저장 action에 대해 갱신 log_prob를 다시 계산한다(`R/algorithms/ppo.py:147~151·250~251·295`). est는 고정, actor 가중치만 갱신한다 |
| value·GAE | 표준 PPO·RolloutStorage 그대로. delta=`r+γ(1−done)V_next−V`, A=`delta+γλ(1−done)A_next` (`R/storage/rollout_storage.py:130~151`). CPU γ=.9, λ=.8, V=[1,2], r=[3,4], 마지막 V=5에서 returns=[9.48,8.5]; 첫 전이 done이면 첫 return=3으로 미래 차단. 모두 일치 |
| 보상 정규화 | 별도 reward normalization 없음. RND와 symmetry는 저장 cfg에서 null. 보상 clone 뒤 timeout bootstrap만 추가. advantage는 rollout 전체 표준화, minibatch 재정규화 false. CPU 원시 보상1 보존·표준화 평균0/std1 확인 |
| timeout | 양쪽 같은 Isaac wrapper가 done=`terminated OR truncated`, 비유한 horizon이면 extras.time_outs 제공. `R/algorithms/ppo.py:177~180`의 현재 transition value bootstrap도 동일. CPU r=1,V=2,γ=.9에서 timeout reward=2.8, 진짜 종료=1. “표준과 같음”이지 정확한 terminal observation의 V를 새로 계산한다는 뜻은 아님 |
| 정규화 통계 시점 | S2는 process_env_step에 현재 ppo_obs, 표준은 다음 obs를 전달(SR:229~230, `R/runners/on_policy_runner.py:104~110`). 차이는 있으나 A1/A9/A10은 actor/critic normalization=false·RND=null이어서 이번 판에는 영향 경로 없음 |
| GRU reset | SR:244가 done마다 PE:273~279 호출, 두 hidden과 steps_since_reset만 해당 env에서 0. 다음 ingest가 first인 env의 history·depth를 새 관측으로 채움(PE:287~298). CPU 선택적 reset·이전 episode 이력 제거 확인 |
| 재생의 episode 경계 | PR:69~74는 done 저장, PE:302~304 및 RF:49~83은 first에서 순환을 절단. o_next 손실은 done 전이를 제외(RF:119~121). 다른 supervised target은 현재 상태이므로 그 전이를 유지 |
| a3 가속 | 같은 G0 replay·같은 epsilon에서 loop/a3의 loss 최대 차 `1.19e−7`, gradient 최대 차 `4.77e−7`. CPU reset 포함. 이번 표본에서 a3 계산 순서가 의미를 바꾼 증거 없음. 모든 GPU 수치 경로에 대한 보증은 아님 |
| iteration 사이 hidden | SR:195는 learn 시작 때만 초기화. φ 갱신 뒤 생존 env hidden은 옛 φ로 만들어진 값을 이어 사용하며 replay 시작값도 그것을 복사(PR:47~50). 일반적인 truncated recurrent 학습에서도 생길 수 있는 상태 불일치다. 매 iteration reset을 바로 처방하면 기억 자체를 바꾸므로 먼저 크기를 측정해야 함 |

### (d) 행동 scale·clip·noise·초기화

`StartActorCritic`은 constructor에서 입력 크기만 검사하고 표준 ActorCritic에 위임한다(SP:22~31). 같은 입력 shape와 같은 직전 RNG로 생성한 표준/START 클래스 state_dict는 CPU에서 완전 일치했다. 출력층에 S2 전용 zero init·작은 gain·tanh 제한을 넣은 코드는 없다. 설치 `R/networks/mlp.py:54~69`의 nn.Linear 기본 초기화이며, 별도 `init_weights()` 함수가 있다는 사실이 호출됐다는 뜻은 아니다.

양쪽 init_noise_std=1이고 state_dependent_std=false다. 다만 S2는 먼저 지각망을 생성하여 RNG를 소비하고(SR:82~95), actor 입력도 다르므로 같은 seed=42여도 S1과 동일한 정책 가중치로 시작하지 않는다. 초기화 **규칙** 일치와 실제 초기 weight 일치를 구별한다.

action scale=.25와 DelayedJointPositionAction, default offset·최대 delay .015 s는 저장 YAML에서 같다. wrapper는 S2만 raw action을 ±17로 자른다(`IsaacLab/source/isaaclab_rl/isaaclab_rl/rsl_rl/vecenv_wrapper.py:153~164`). PPO는 clipping 이전 sample/log_prob를 저장하고 env는 clipped action을 받는 표준 wrapper 방식이다. 포화가 빈번하면 목적과 실행 행동의 관계가 달라질 수 있으나 **실제 rollout 포화율은 이번에 미측정**이다. 합성 checkpoint probe의 평균 행동 최대치는 open 4.386·START 3.766으로, 이것만으로 실학습에서 clip이 무관하다고 결론내릴 수 없다.

### (e) 놓치기 쉬운 차이: 학습·평가의 잠재변수

PE:324~328에서 학습은 `z=mu+epsilon×exp(logvar/2)`, 평가 deterministic=True이면 mu다. EA:421은 항상 deterministic=True이며 `S2_SAMPLE=1`은 EA:425~426에서 **action Gaussian 표집만** 바꾼다. CPU spy로 flag=1이어도 지각 step에 deterministic=True가 전달됨을 확인했다. 따라서 그 flag를 켠 영상이 멈췄다고 “학습과 같은 표집에서도 멈춘다”로 판정하면 안 된다.

현재 checkpoint의 동일 합성 관측 128개에서 행동 noise를 끄고 **z 표집만** 켜면, action mean의 관절별 표준편차 평균이 open `0.088347`, START `0.087577`이었다. z 표집은 실제 actor 출력에 영향이 있다. 다만 이것은 상태 분포 밖 정적 probe이므로 학습·평가 차이가 정지의 원인이라는 증거는 아니다.

G0는 `map_input=none`이라 TR-Net을 만들지 않는다(PE:257). 이 실험의 실패 원인을 depth CNN·TR-Net U-Net 오류로 바로 지목할 수 없다. I-E의 prop GRU·attention·velocity·latent와 supervised map decoder는 남는다(PE:132~170, RF:110~121). actor의 보행 목적이 이 모듈에 역전파되지 않는 것은 설계된 경계다. 지도 없음 G0에서 지도 복원 목표가 도움이 되는지, 정지 상태의 좋은 예측이 보행에 도움이 되는지는 별도 문제다.

### 학습 곡선 원자료 재확인

아래는 각 TensorBoard **step=1500** 값을 직접 읽은 것이다. 종료 값은 해당 로그의 episode 집계 지표이며 모든 시작 episode를 다시 센 성공률로 해석하지 않는다.

| 태그 | EX-01 scan | EX-09 open | EX-10 START |
|---|---:|---:|---:|
| Loss/learning_rate | 0.000384434 | 0.000170859 | 0.000113906 |
| Policy/mean_noise_std | 0.537583 | 0.793098 | 0.757483 |
| Curriculum/terrain_levels | 3.877350 | 0.001302 | 0 |
| Episode_Reward/track_lin_vel | 0.890281 | 0.365049 | 0.338359 |
| Episode_Termination/bad_orientation | 0.216156 | 0.689209 | 0.391290 |
| Episode_Termination/time_out | 0.774363 | 0.306641 | 0.605401 |
| Loss/perception/kl | 해당 없음 | 0.000009662 | 0.000006586 |
| Loss/perception/o_next | 해당 없음 | 0.785723 | 0.612663 |
| Loss/perception/l_ie | 해당 없음 | 0.792468 | 0.618503 |

lead의 중간 lr 약 7.6e−5는 EX-10 step750의 `0.0000759375`와 일치한다. 하지만 EX-09와 EX-10의 끝 lr/noise는 각각 다르다. 둘 다 step0부터 lr이 하한 `1e−5`에 도달했으며, 이는 초기 PPO update 내 큰 행동분포 이동을 조사할 이유다. 그 최초 PPO update 이전에는 아직 지각 update를 하지 않았으므로 **최초 lr 하락을 지각 갱신 후 변화만으로 설명할 수 없다.**

EX-09·10의 학습 중 bad_orientation 지표가 높다. 평가의 서 있기 장면을 “학습 중에도 안정적으로 서서 보상만 챙김”으로 확대하면 틀린 진단이 된다. 초기 탐색·표본 분포·critic 적합·gradient도 봐야 한다. terrain_levels가 바닥에 있다는 것은 그 별도 승급 규칙 아래의 실패 결과이며 신경망 배선 오류의 식별자가 아니다.

I-E loss 대부분은 o_next이고 prior KL은 매우 작다. 이는 기록된 분포에서 z posterior가 prior에 가까운 신호지만 v·zf·zb까지 쓸모없다는 뜻은 아니다. 정지하거나 넘어지는 분포를 잘 예측하는 것이 좋은 보행 표현이라는 보장도 없다. 낮은 추정 MSE만으로 I-E가 충분히 학습됐다고 판정하지 않는다.

## 가설

| 우선 조사할 가설 | 현재 지지·반증 | 아직 필요한 구분 |
|---|---|---|
| S2 지형·관측·표본량 결합이 초기 학습을 막음 | 저장 cfg에서 차이 확정, 두 S2 모두 낮은 단계·기울기 종료 많음. EX-01은 height scan actor였음 | 환경·경험량·actor 정보까지 맞춘 대조가 없으므로 runner 단독 인과 미확정 |
| 지각 표현의 이동과 stochastic z가 정책 학습을 어렵게 함 | CPU에서 지각만 바꿔 전체 정책 이동, 실제 checkpoint에서 z noise가 action mean을 바꿈 | 실제 rollout에서 φ 갱신 전후 KL·hidden 재계산 차이·명령별 민감도를 측정해야 함. 최초 lr 하락의 단독 설명은 불가 |
| 지각 감독 목표가 보행에 필요한 정보를 충분히 만들지 못함 | 매우 작은 latent prior KL, o_next 중심 손실, actor의 reward gradient 차단 | 같은 분포의 고정 표현·velocity oracle·감독 오류와 성공을 대조. 손실 감소만으로 성능 증명 불가 |
| noisy·큰 critic과 표준 PPO의 결합이 actor update를 불안정하게 함 | critic o에 noise가 들어가고 입력 52→664. 초기 lr 즉시 하한. actor와 critic gradient clipping은 표준 공유 norm | actor/critic gradient norm·value residual·minibatch KL을 같이 재야 함. critic 크기만으로 lr 원인 확정 불가 |
| 평가의 deterministic latent 전환이 움직임을 없앰 | `S2_SAMPLE`이 학습 표집을 완전히 재현하지 않음은 확정 | 아래 표집 네 조합 대조 필요. 평가 차이로 설명돼도 낮은 학습 추종·승급 문제는 별도로 남음 |
| 명령이 입력에서 사라짐 / estimator KL이 scheduler에 섞임 / a3 reset 계산 오류 | 이번 CPU 시험에서 반증 | 실행 당시 source 미확인 범위와 GPU 수치 차이는 남지만, 증거 없이 이 항목부터 고치는 것은 비효율적 |

## 다음에 가를 시험

**지금 PPO 학습률을 고정하거나 새 보상을 넣을 근거는 없다.** 먼저 이미 있는 자료를 활용해 아래 순서로 가른다. GPU 시험은 제안이며 실행하지 않았다. 코드 수정은 담당자 검토 뒤 별도 판으로 해야 한다.

| 순서 | 구체적 시험 | 어떤 결과면 무엇을 말할 수 있나 |
|---|---|---|
| CPU·기록 우선 | EX-01/09/10의 env·명령·관측·clip·경험량 manifest를 이번 차이표대로 고정. 기존 실제 rollout tensor가 있으면 동일 source로 재생 | 차이가 남으면 “runner만의 대조”라는 명칭을 쓰지 않는다. 자료가 없으면 미확인으로 남기며 합성 probe를 실측 rollout으로 대체하지 않음 |
| CPU 재생 자료 확보 뒤 | 같은 저장 history와 같은 epsilon을 고정하고 θ update 전후, φ update 전후, hidden을 재계산한 경우의 행동 KL을 따로 기록. mean/p95/max와 명령별 action 민감도·추정 v 오차를 함께 보고 | φ 변화만 큰 경우 표현 이동 가설 지지. θ 초기 update부터 크면 optimizer/critic/입력 크기·분포 쪽 먼저. prior KL을 policy KL 대신 쓰지 않음 |
| 평가 코드 보완 후 승인된 짧은 대조 | 같은 checkpoint·같은 초기 상태에서 `z=mu / z sample` × `action mean / action sample` 네 조합. 현재 S2_SAMPLE은 그중 z=mu 두 조합만 가능 | z sample에서만 이동하면 잠재변수 배포 전환 후보. action sample에서만 이동하면 평균 정책의 실패 후보. 모두 멈추면 이 두 평가 차이만으로 설명 불가. 한 조합의 우연한 이동은 성공으로 세지 않음 |
| runner 배선의 더 강한 대조 | 동일한 입력 차원·동일 초기 weight·같은 저장 actor_in/critic_in·reward·done·minibatch RNG로 표준 PPO와 S2의 PPO 구간을 한 update 비교. 이번 합성 rollout에서는 weight·loss·lr 완전 일치까지 확인했으며, 다음에는 실제 저장 rollout에 같은 검사를 적용 | 동일 update면 runner 수학보다 입력을 생산하는 지각·환경 차이를 우선. 어긋나면 최초 차이 tensor부터 고친다. 시뮬 없이 가능 |
| 그 뒤 승인할 최소 학습 대조 | 하나의 쉬운 이어진 지형 env·같은 명령·같은 N×T·critic·초기 state_dict·clip에서 actor 입력을 공통 `o45+est51`로 맞춤. 한 판은 est를 고정 영으로, 다른 판은 현재 G0의 학습 지각으로 제공 | 이 비교는 “지각 입력·공동 학습의 효과”를 가른다. actor 구조와 환경을 동시에 바꾸지 않음. 고정 입력에서도 실패하면 지각 탓으로 확정 못 함. S1 scan의 눈187을 빼면 그것은 새 기준이며 EX-01 재사용 불가 |
| 후속 분해 | 위 비교가 지각 쪽을 지목할 때만 같은 학습된 지각을 고정한 판과 계속 갱신한 판, 또는 속도 oracle을 한 축씩 비교 | 고정판만 성공하면 이동 가설, 둘 다 실패하면 표현·관측 정보 가설을 더 본다. 처음부터 모든 축을 큰 격자로 늘리지 않음 |

기준은 지속 진행·명령 추종·생존·방향을 함께 보며, 학습 episode 집계와 평가 평균 정책의 행동을 나누어 기록한다. `1500회` 한 지점이나 단일 seed만으로 S2 구조 또는 START 전체를 기각하지 않는다. 반대로 CPU 배선 시험 통과만으로 현 구조가 학습 가능하다고 승인하지 않는다.

## CPU 검증과 재현 기록

- 실행 Python: `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`. `CUDA_VISIBLE_DEVICES=-1`, OMP/MKL 스레드 1, 테스트 tensor와 checkpoint map_location 모두 CPU. 독립 시험 시작에서 CUDA unavailable을 assert했다.
- 기존 `foothold_s2/tests/test_start_runner.py`와 `test_start_perception.py`: **18 passed, 46.28 s**. CPU 가짜 env이며 Kit import 없음.
- 독립 스크립트: `C:/Users/AI-WS01/AppData/Local/Temp/astra_s2r_cpu.py`, **22개 pass**. 스크립트 sha256 `505791bb84e0962605b31a5cbaa00fd75eb0612553460307ad92de243b944503`. 결과 JSON 같은 폴더 `astra_s2r_cpu_result.json`, sha256 `d0fa3ac9dd54746f1d3bfebd3b923cb10a0be3c6e7d236741067075cce5476b2`. 최초 진단 스크립트의 중단용 generator가 Python StopIteration 변환에 걸려 시험 자체를 고친 뒤 재실행했다. 제품 코드는 변경하지 않았다.
- 곡선 재독 결과는 같은 임시 폴더 `astra_s2r_curves.json`; 보고 표는 실제 TensorBoard 태그의 step1500과 대조했다.
- 현재 요청된 코드와 sonnet 사본의 바이트 일치를 확인했다. SR sha256 `19f0bae20445348c5f90c4d8ea01d026e75858136c84730cf331444d58650d6f`, PR `07e32c1330ddc3d7cc596e78e28550c07dffb7f4a6ad821c788b1f4a836dc63e`, SP `15caf9de285833243e5987f0ccb119304aa4e0b29ee15879f748594f4e3b0590`, PE `1469a37f39984a6229cb56bfd6ea4c5797323b9cd78371b3d2f0bfc6c3c4efa4`, TS `4f0b6eb859d01b92d89d64a6991e1ec9c5ae88936d87f26873af0d03317a6c3e`.

아래 부록에 독립 시험 소스를 그대로 보존한다. 임시 파일이 사라져도 같은 고정 checkout에서 재실행할 수 있다. checkpoint·로그 경로는 이 기기의 원자료를 가리킨다.

<details>
<summary>독립 CPU 시험 소스</summary>

```python
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
import sys, copy, json, contextlib, io
from pathlib import Path
sys.path.insert(0, 'C:/mai/wt/foothold-lab/astra2-s2r')
import torch
from tensordict import TensorDict
from rsl_rl.modules import ActorCritic
from rsl_rl.algorithms import PPO
from foothold_s2.models.start_policy import StartActorCritic, OBS_GROUPS
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg
from foothold_s2.models.start_perception import StartPerception, PerceptionCfg
torch.set_num_threads(1)
assert not torch.cuda.is_available()
out = {'cuda_available': False, 'tests': {}, 'measurements': {}}
def check(name, condition):
    assert bool(condition), name
    out['tests'][name] = 'pass'
def runner():
    torch.manual_seed(123)
    cfg=train_cfg(6, {'map_input':'none','microbatch_envs':2,'num_learning_epochs':1,'num_mini_batches':2})
    with contextlib.redirect_stdout(io.StringIO()):
        return StartRunner(FakeStartEnv(4,episode_len=3), cfg, None, 'cpu')
r=runner()
raw=r.env.get_observations().clone()
raw['policy'][:,6:9]=torch.tensor([.3,-.2,.7])
obs=r._ppo_obs(raw,torch.zeros(4,51))
check('command_slots_6_to_8', torch.equal(obs['actor_in'][:,6:9],raw['policy'][:,6:9]))
check('critic_obeys_same_policy_noise',torch.equal(obs['critic_in'][:,:45],raw['policy']))
with contextlib.redirect_stdout(io.StringIO()):
    kw={'actor_hidden_dims':[512,256,128],'critic_hidden_dims':[512,256,128]}
    torch.manual_seed(7); a=StartActorCritic(obs,OBS_GROUPS,12,**kw)
    torch.manual_seed(7); b=ActorCritic(obs,OBS_GROUPS,12,**kw)
check('same_init_as_standard_at_equal_shape',all(torch.equal(a.state_dict()[k],v) for k,v in b.state_dict().items()))
check('initial_std_one',torch.equal(a.std,torch.ones(12)))
saved={}
def stop():
    saved['obs']=r.alg.storage.observations.clone()
    saved['logp']=r.alg.storage.actions_log_prob.clone()
    saved['actions']=r.alg.storage.actions.clone()
    raise StopIteration
update=r.alg.update;r.alg.update=stop
try:r.learn(1)
except StopIteration:pass
r.alg.update=update
flat=saved['obs'].flatten(0,1)
def ratio():
    r.alg.policy.act(flat)
    return torch.exp(r.alg.policy.get_actions_log_prob(saved['actions'].flatten(0,1))-saved['logp'].flatten())
err=float((ratio()-1).abs().max());out['measurements']['initial_ratio_error']=err
check('first_ppo_ratio_one',err<1e-5)
check('command_saved_exactly',torch.equal(saved['obs']['actor_in'][:,:,:45],r.replay.data['obs']))
with torch.no_grad():
    r.perception.ie.heads.bias.add_(10)
check('changed_estimator_not_recomputed_in_ratio',float((ratio()-1).abs().max())<1e-5)
v0=r.alg.policy.evaluate(r._ppo_obs(raw,torch.zeros(4,51)))
v1=r.alg.policy.evaluate(r._ppo_obs(raw,torch.ones(4,51)*999))
check('bootstrap_est_zero_irrelevant_to_critic',torch.equal(v0,v1))
p_before=copy.deepcopy(r.perception.state_dict())
r.perception.step=lambda *x,**kw: (_ for _ in ()).throw(AssertionError('PPO called perception'))
r.alg.update()
check('ppo_no_perception_call_or_weight_update',all(torch.equal(v,r.perception.state_dict()[k]) for k,v in p_before.items()))

# Adaptive policy KL: known old/new normal distributions, optimizer disabled.
def kl_trial(shift):
    with contextlib.redirect_stdout(io.StringIO()): p=ActorCritic(obs,OBS_GROUPS,12,actor_hidden_dims=[8],critic_hidden_dims=[8])
    alg=PPO(p,num_learning_epochs=1,num_mini_batches=1,learning_rate=.001,desired_kl=.01)
    alg.init_storage('rl',4,1,obs,[12]);alg.act(obs)
    alg.process_env_step(obs,torch.ones(4),torch.ones(4),{})
    alg.compute_returns(obs)
    alg.storage.mu.add_(shift)
    alg.optimizer.step=lambda *x,**kw:None
    alg.update()
    return alg.learning_rate
lo,hi=kl_trial(0),kl_trial(.3)
out['measurements']['policy_kl_lr_low_high']=[lo,hi]
check('adaptive_kl_known_normals',abs(lo-.0015)<1e-12 and abs(hi-.001/1.5)<1e-12)

with contextlib.redirect_stdout(io.StringIO()): p=ActorCritic(obs,OBS_GROUPS,12,actor_hidden_dims=[8],critic_hidden_dims=[8])
alg=PPO(p,gamma=.9);alg.init_storage('rl',4,1,obs,[12]);alg.act(obs)
alg.transition.values.fill_(2)
alg.process_env_step(obs,torch.ones(4),torch.ones(4),{'time_outs':torch.tensor([1,0,1,0])})
check('timeout_bootstrap_known_values',torch.allclose(alg.storage.rewards[:, :, 0],torch.tensor([[2.8,1,2.8,1]])))
check('raw_rewards_no_normalization',float(alg.storage.rewards[0,1,0])==1)
alg.init_storage('rl',2,2,obs[:2],[12]);st=alg.storage
st.values.copy_(torch.tensor([[[1.],[1.]],[[2.],[2.]]]))
st.rewards.copy_(torch.tensor([[[3.],[3.]],[[4.],[4.]]]))
st.dones.zero_();st.dones[0,1]=1
st.compute_returns(torch.ones(2,1)*5,.9,.8,normalize_advantage=False)
check('gae_terminal_known_return',torch.allclose(st.returns[:,:,0],torch.tensor([[9.48,3.],[8.5,8.5]]),atol=1e-6))
st.compute_returns(torch.ones(2,1)*5,.9,.8,normalize_advantage=True)
check('advantage_global_normalization',abs(float(st.advantages.mean()))<1e-6 and abs(float(st.advantages.std())-1)<1e-6)

p=StartPerception(PerceptionCfg(map_input='none'));state=p.init_state(2,'cpu')
state.h_prop.fill_(7);state.h_terr.fill_(8);state.hist.fill_(9);state.steps_since_reset.fill_(4)
p.reset_envs(state,torch.tensor([True,False]),torch.tensor([False,True]))
check('reset_selected_hidden_only',not state.h_prop[0].any() and torch.all(state.h_prop[1]==7) and not state.h_terr[0].any())
new=torch.zeros(2,45);new[0,6]=.6
inp=p.ingest(state,new,torch.zeros(2,60,60))
check('reset_history_replaced_before_use',torch.equal(inp['hist'][0],new[0].expand(10,45)) and inp['first'].tolist()==[True,False])

# Same replay, same epsilon: loop versus a3 losses and gradients.
r=runner();r.alg.update=stop
# Use replay already captured from first r by assigning copied source before overwriting.
r.alg.update=stop
try:r.learn(1)
except StopIteration:pass
batch=r.replay.gather(torch.arange(4));eps=torch.randn(6,4,16)
losses=[];grads=[]
for impl in ['loop','a3']:
    r.perception.zero_grad(set_to_none=True)
    res=r.perception.sequence_loss(batch,eps,impl);res['loss'].backward()
    losses.append({k:float(res[k].detach()) for k in ['loss','kl','o_next','v','hf','hb']})
    grads.append(torch.cat([x.grad.flatten() for x in r.perception.parameters() if x.grad is not None]))
le=max(abs(losses[0][k]-losses[1][k]) for k in losses[0]);ge=float((grads[0]-grads[1]).abs().max())
out['measurements']['loop_a3_loss_gradient_max_error']=[le,ge]
check('g0_loop_a3_loss_and_gradient',le<1e-4 and ge<1e-4)
# Perception updates can change the composite policy even while actor weights are fixed.
def deterministic_est(per):
    hp,ht=batch['h_prop0'],batch['h_terr0'];est=[]
    with torch.no_grad():
        for t in range(6):
            hp,ht,z=per._advance(hp,ht,batch['hist'][t],batch['depth2'][t].float(),batch['tick'][t],batch['first'][t],batch['use_gt'][t],batch['gt_map'][t])
            est.append(torch.cat([z['mu'],z['v'],z['zf'],z['zb']],-1))
    return torch.stack(est)
before=deterministic_est(r.perception);actor_before=copy.deepcopy(r.alg.policy.state_dict())
r.update_perception();after=deterministic_est(r.perception)
with torch.no_grad():
    aa=r.alg.policy.act_inference({'actor_in':torch.cat([batch['obs'],before],-1).flatten(0,1)})
    bb=r.alg.policy.act_inference({'actor_in':torch.cat([batch['obs'],after],-1).flatten(0,1)})
    jump=((aa-bb)**2/(2*r.alg.policy.std**2)).sum(-1)
out['measurements']['synthetic_perception_only_composite_kl_mean']=float(jump.mean())
check('perception_only_changes_composite_policy',float(jump.max())>0 and all(torch.equal(v,r.alg.policy.state_dict()[k]) for k,v in actor_before.items()))

# Trained checkpoints: diagnostic probes, not real robot observations.
root=Path('C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s2_diag')
for label in ['open','start']:
    sd=torch.load(root/f'2026-10-21_16-14-13_diag-G0-{label}/model_1500.pt',map_location='cpu',weights_only=False)
    r=runner();r.alg.policy.load_state_dict(sd['model_state_dict']);r.perception.load_state_dict(sd['perception_state_dict'])
    n=128;o=torch.zeros(n,45);o[:,5]=-1;o[:,6]=.5;dep=torch.zeros(n,60,60);gm=torch.zeros(n,32,16)
    ps=r.perception.init_state(n,'cpu');inp=r.perception.ingest(ps,o,dep)
    with torch.no_grad():
        est=r.perception.step(ps,inp,gm,deterministic=True)
        x=torch.cat([o,est],-1);y=r.alg.policy.act_inference({'actor_in':x})
        xflip=x.clone();xflip[:,6]=-.5;yf=r.alg.policy.act_inference({'actor_in':xflip})
        ps=r.perception.init_state(n,'cpu');inp=r.perception.ingest(ps,o,dep);est_s=r.perception.step(ps,inp,gm)
        ys=r.alg.policy.act_inference({'actor_in':torch.cat([o,est_s],-1)})
    out['measurements'][label]={'iteration':sd['iter'],'lr':sd['ppo_learning_rate'],'std_mean':float(r.alg.policy.std.mean()),'fixed_est_command_flip_action_rms':float((yf-y).square().mean().sqrt()),'latent_only_action_std_mean':float(ys.std(0).mean()),'abs_action_mean_max':float(y.abs().max())}
    check(label+'_command_has_nonzero_effect',float((yf-y).abs().max())>1e-6)
# Evaluation's S2_SAMPLE flag only samples action noise, not latent noise.
from foothold_s2.eval.adapters import S2Policy
r=runner();policy=S2Policy(r,4);called=[]
realstep=r.perception.step
def spy(*args,**kwargs):
    called.append(kwargs.get('deterministic'))
    return realstep(*args,**kwargs)
r.perception.step=spy
os.environ['S2_SAMPLE']='1';policy(r.env.get_observations());os.environ.pop('S2_SAMPLE')
check('s2_sample_still_deterministic_latent',called==[True])
# One complete PPO update: identical stored data and weights versus standard policy.
r=runner();actual_update=r.alg.update;r.alg.update=stop
try:r.learn(1)
except StopIteration:pass
r.alg.update=actual_update
template=r.alg.storage.observations[0].clone()
with contextlib.redirect_stdout(io.StringIO()):
    standard=ActorCritic(template,OBS_GROUPS,12,actor_hidden_dims=[512,256,128],critic_hidden_dims=[512,256,128])
standard.load_state_dict(r.alg.policy.state_dict())
cfg=copy.deepcopy(r.alg_cfg);cfg.pop('class_name',None)
gold=PPO(standard,device='cpu',**cfg)
gold.storage=copy.deepcopy(r.alg.storage)
gold.optimizer.load_state_dict(r.alg.optimizer.state_dict())
torch.manual_seed(999);loss_a=r.alg.update()
torch.manual_seed(999);loss_b=gold.update()
diff=max(float((v-gold.policy.state_dict()[k]).abs().max()) for k,v in r.alg.policy.state_dict().items())
out['measurements']['standard_full_ppo_update_max_weight_diff']=diff
check('standard_full_ppo_update_exact_match',diff==0 and loss_a==loss_b and r.alg.learning_rate==gold.learning_rate)
Path(os.environ['TEMP'],'astra_s2r_cpu_result.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))

```

</details>
