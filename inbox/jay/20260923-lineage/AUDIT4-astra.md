# 4차 감사 · 실패 진단과 구현 전 진행 방향

> 분류: 리서치
> 작성: Codex 감사 세션 · 2026-09-23 17:35
> 근거: tfevents 전량 재집계, 실행 로그·저장 설정, 설치된 PPO·PyTorch 코드, 운영 코드와 로컬 App Server 스키마
> 요지: 행동 정상이라는 진단은 보상 이상치와 모순된다. 원장 전환 절차와 프로세스 수명 관리 없이 SQLite 표만 도입하면 P0가 남는다.
> 상태: 로컬 감사 완료 · 별도 발행 전 검증 미완료
> 판: v1.0

## 먼저 고쳐야 할 판단

**판단: 제안된 설계를 그대로 구현 완료로 간주하고 무인 운영을 켜면 안 된다.** 막는 이유는 다음과 같다.

- **실측:** v2b-s의 보상은 마지막까지 27~30이 아니었다. step 1667·1668의 `Train/mean_reward`는 **−2.7019048726833884×10²²**다. critic만 망가지고 행동은 정상이었다는 설명을 철회해야 한다.
- **판단:** 같은 seed 재시도 한 번의 성공·실패로 seed 고유 성질과 무작위 사건을 양분할 수 없다. 재현성 탐색으로는 타당하지만 원인 식별 실험으로는 부족하다.
- **확인됨:** 현재 감시는 `halt_reason`과 별개로 phase가 학습 중이면 평가를 띄운다. `_out/loop/watchdog.py:383-385`, `eval_runner.py:248-267`에는 재시도·중단 정책을 집행하는 관문이 없다. 새 원장을 만들기 전에 구 실행 경로와 실제 작업을 정리하는 전환 절차가 필요하다.
- **판단:** SQLite 표와 원자적 claim만으로 worker 예외 은폐, 산출물 결손, 만료된 소유자의 뒤늦은 완료를 막지 못한다. 아래의 상태 전이·복구 계약과 실패 시험이 함께 있어야 한다.

이번 감사는 새 진단·재시도·설계안을 점검했다. 3차 감사의 수치·결함 주입 결과 전체를 재검산한 전면 감사가 아니다. **확인됨**은 파일과 행, **실측**은 이번 원자료 재집계·시험, **판단**은 해석·권고, **미확인**은 증거가 없는 부분을 뜻한다. 바이너리 tfevents는 행 번호 대신 정확한 파일·tag·step을 제시한다.

## 1. 원자료 재집계와 실패 진단

### 자료 위치와 집계 방식

이하 `L`은 `C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia`, `G`는 `C:/isaac/IsaacLab/logs/gap_run_logs`, `P`는 `C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages`다.

| 약칭 | L 아래 실행 폴더 | tfevents 파일 |
|---|---|---|
| 부모 | `2026-09-21_11-03-28_20260921_v2b_seed42_iter3000` | `events.out.tfevents.1789956223.AI-WS01.75852.0` |
| r | `2026-09-23_14-42-33_20260923_v2b-r_seed42_iter3000` | `events.out.tfevents.1790142170.AI-WS01.69380.0` |
| s | `2026-09-23_14-42-37_20260923_v2b-s_seed43_iter3000` | `events.out.tfevents.1790142176.AI-WS01.74392.0` |
| s2 | `2026-09-23_17-08-57_20260923_v2b-s2_seed43_iter3000` | `events.out.tfevents.1790150950.AI-WS01.76292.0` |

**실측:** isaac311 Python의 TensorBoard `EventAccumulator(..., size_guidance={'scalars': 0})`로 각 실행을 Reload하여 전체 scalar를 읽었다. 기본 reservoir 표본 추출을 사용하지 않았다. 조사 기준은 2026-09-23 17:27 KST에 읽힌 event다. 실행 중 파일의 뒤쪽은 계속 늘어나므로 이후 현재값과 구분한다.

### s에서 실제로 기록된 값

| tag·범위 | 재집계 |
|---|---|
| `Policy/mean_noise_std`, step 0~1670 | 최소 0.53703934, 최대 0.62203652, 마지막 0.55161560 |
| `Loss/value_function`, step 1576 | 0.028482966 |
| 같은 tag, step 1577·1578 | 0.92253572 · 5.5577240 |
| 같은 tag, step 1586 | 12,932,611 |
| 같은 tag, step 1662~1667 | inf |
| 같은 tag, step 1670 | 2.9287643984×10¹⁶ |
| `Loss/learning_rate`, step 1574~1587 및 1658~1660 | 약 1×10⁻⁵ |
| 같은 tag, step 1661 | 0.00129746343 |
| 같은 tag, step 1662~1669 | 약 0.01 |
| 같은 tag, step 1670 | 약 1×10⁻⁵ |
| `Train/mean_reward`, 마지막 100점 | 최소 −2.7019048727×10²², 최대 30.74684143 |
| `Train/mean_episode_length`, 마지막 100점 | 932.75~998.96002 |

**실측:** 보상은 step 1581에서 −29.15369, 1584에서 −427.05408, 1587에서 −11007.80469, 1608에서 −3.27349632×10⁹, 1615에서 −2.2960767658×10¹⁴, 1667·1668에서 −2.7019048727×10²², 1669에서 −3.4966028836×10¹⁶이다. 마지막 step 1670 하나는 27.38309로 돌아온다. 마지막 값만 보거나 일부 점을 뽑으면 실패 양상이 가려진다.

**실측:** `Episode_Reward/action_rate_l2`도 step 1581에서 −2.54651, 1584에서 −23.89104, 1608에서 −227326144, 1667에서 −9.3816158614×10²⁰이다. 행동 관련 보상 항목의 수치 이상까지 확인된다. 다만 실제 로봇 자세·낙상·모든 env의 행동을 이 평균만으로 재구성할 수는 없다.

**확인됨:** `P/rsl_rl/runners/on_policy_runner.py:78-79,130-131,231-232`의 보상·길이는 최근 종료 에피소드 100개의 deque 평균이다. 전체 env의 모든 순간이 정상이라는 증거가 아니다. `G/20260923_144226_20260923_v2b-s_seed43_iter3000.log:53518-53526`의 iteration 1667 블록에서도 보상 이상치를 대조할 수 있다. 텍스트 출력과 tfevents float32 저장의 반올림 차이는 있지만 같은 규모의 이상이다. 오류 stack과 메시지는 같은 로그 `:53647-53663`, 종료코드 1은 `:53698`이다.

### 무엇까지 말할 수 있는가

**판단:** “value loss가 1577부터 급증했다”는 관측은 맞다. 하지만 value loss는 critic 출력과 return target의 오차이므로 이 tag만으로 critic 파라미터 자체가 최초 원인이라고 할 수 없다. 설치 코드도 `(value_batch - returns_batch).pow(2)`를 계산한다(`P/rsl_rl/algorithms/ppo.py:302-311`).

**판단:** “std가 줄어서 터졌다는 가설을 반증했다”는 말은 너무 넓다. 반박한 것은 **기록된 평균 std가 계속 0으로 수렴했다는 설명**이다. 차원별 최솟값, 실패 minibatch의 std, 마지막 로그 뒤 갱신 값은 없다. 평균이 양수여도 개별 성분 음수·NaN을 배제하지 못한다.

**판단:** “0.01이 초기 발산보다 나중에 기록됐다”는 맞지만 “원인이 아니라 결과임을 입증했다”는 아니다. 이 scalar는 iteration 내부 모든 minibatch의 학습률을 저장하지 않는다(`on_policy_runner.py:213`). 적응 학습률은 KL에 반응한다(`ppo.py:258-292`). 최초 상승의 원인을 0.01로 지목할 근거는 없지만, 후기 불안정을 증폭했는지나 어떤 KL이 상승을 촉발했는지는 미확인이다. 1661부터 상한이라는 수치도 1662부터로 고친다.

**미확인:** 최초 원인은 아직 모른다. reward·return·value·observation·action의 env별 이상치, minibatch별 KL·학습률·gradient norm, optimizer 상태와 실패 직전 파라미터가 필요하다. 지금은 “value loss 급증, 행동 관련 보상 이상, 이후 비유한 손실, sampling 시 scale 조건 위반”이라는 관측 순서까지만 확정한다.

### critic에서 std로 가는 경로

**확인됨:** s의 `params/agent.yaml:18-24,34-50`은 ActorCritic, scalar std, state-dependent std false, max_grad_norm 1.0, symmetry/RND 없음이다. `P/rsl_rl/modules/actor_critic.py:92-104,139-152`는 std를 직접 학습 파라미터로 두고 scalar 분기에서 양수 변환 없이 사용한다. `Normal`의 기본 인자 검증도 꺼져 있다. 이번 로그의 거부 지점은 `Normal()` 생성자가 아니라 **`distribution.sample()`이 호출한 `torch.normal()`**이다.

**확인됨:** `ppo.py:104`의 Adam 하나, `:313`의 합산 loss, `:364-377`의 backward·전체 파라미터 gradient clipping·step은 존재한다. 다만 Adam 하나나 loss 합산 자체가 분리된 actor·critic의 gradient를 자동으로 섞는다는 설명은 틀리다. 중요한 결합점은 `:376`의 **전체 파라미터에 대한 공통 gradient norm**이다. `P/torch/nn/utils/clip_grad.py:101-112,159-176,184,219-220`은 기본적으로 비유한 norm에서 예외를 내지 않고 공통 계수로 gradient들을 곱한다.

**실측:** CPU의 독립 scalar 파라미터 두 개로 gradient를 `(1, inf)`로 만들고 설치된 `clip_grad_norm_(..., 1)`을 호출하니 norm은 inf, gradient는 `(0, NaN)`이었다. `(1, NaN)`에서는 둘 다 NaN이 됐다. 즉 비유한 critic gradient가 공통 clipping을 통해 actor·std에 영향을 줄 수 있는 경로는 있다.

**판단:** 이것은 가능한 전파 경로의 재현이지 실제 사고의 역추적 완료가 아니다. 손실 inf는 제곱 overflow만으로도 생길 수 있고 gradient NaN을 자동으로 뜻하지 않는다. “critic inf가 std NaN을 만들었다”는 **미확인 가설**로 남겨야 한다.

## 2. 같은 seed 재시도의 의미와 관측 항목

**확인됨:** s와 s2의 실행 로그 `:2,32-33,170`은 seed 43, 시뮬 cuda:1, 같은 `nvidia_pretrained_source/nvidia_pretrained.pt` 경로를 가리킨다. s2는 실패한 model_1650에서 이어가기보다 명시된 pretrained 경로에서 다시 시작한 실행이다. 두 실행의 `params/agent.yaml`은 `:10` run_name만 다르고, `params/env.yaml`은 `:851` log_dir만 다르다. 두 agent 설정의 신경망 장치는 `:2` cuda:0이다.

**미확인:** 같은 경로를 읽었다고 같은 시점의 checkpoint bytes가 보증되지는 않는다. 당시 입력 SHA가 없으면 나중 해시 하나로 소급 입증할 수 없다. 실행 코드·라이브러리·driver·동시 부하까지 같았다는 증거도 위 YAML 비교에 포함되지 않는다.

**판단:** 같은 seed로 재발 여부를 탐색하는 재시도는 타당하다. 그러나 재실패는 “이 조건에서 재발”이며 seed 고유 성질의 증명이 아니다. 성공은 “이번에는 재발하지 않음”이며 단순 무작위 사건 확정이나 더 큰 발견의 증명이 아니다. GPU 비결정성, 초기 상태·외부 조건·부하 차이와 잠복 결함이 모두 남는다. 필요하면 여러 seed와 seed별 반복으로 실패 빈도·조건을 따로 비교하되, 이번 감사가 추가 학습 실행을 승인하거나 시작하지는 않는다.

### 관측 시점의 실행 상태

**실측:** 17:27 KST에 읽은 값은 아래와 같다. s2는 아직 1577 부근을 지나지 않았다.

| 실행 | 마지막 event step·시각 | value loss 마지막 | value loss 전 구간 최대 |
|---|---|---:|---:|
| 부모 | 3000 · 9/21 14:34:22 | 0.01171703 | 0.09186173 |
| r | 2633 · 9/23 17:27:36 | 0.01053299 | 0.08671035 |
| s2 | 263 · 9/23 17:27:35 | 0.02638683 | 0.08452634 |

**실측:** s2의 마지막 100점 value loss는 0.01672080~0.03674759다. 프로세스 조회에서도 PID 76292와 69380이 존재했고 시작 시각은 각각 17:08:48, 14:42:19였다. Win32_Process 명령행 조회는 접근 거부라 프로세스 신원의 모든 필드까지 확인하지 못했다. 살아 있음과 향후 완주는 구분한다.

**판단:** 1577만 찍어 보는 방식보다 그 이전부터 1670 이후까지 연속 구간을 본다. 기존 로그에서는 value loss, reward 전량, action_rate_l2, std 평균, episode length, 학습률의 이상치·비유한수·변화 속도를 확인한다. 향후 승인된 계측에는 차원별 std 최솟값·유한성, action·observation·return·value의 범위와 env ID, actor/critic별 clipping 전 gradient norm, 실제 minibatch KL·학습률을 추가한다. 계측 변경은 별도 실행 조건으로 기록한다. 비유한수·지속적 폭증의 중단 규칙과 덤프 위치를 사전에 정하고, 문제를 감추는 std clamp나 자동 재시도로 실패를 덮지 않는다.

## 3. 구현 순서에 빠진 단계

**판단:** 실패 보존 → 입력 고정 → 원장 → 완전성 검사라는 큰 순서는 유지할 수 있다. 다만 **1과 2 사이에 기존 실행계의 전환·실제 상태 조정 단계**가 반드시 필요하다.

**확인됨:** `_out/loop/state.json:11-52`에는 r·s만 있고 s2가 없다. `:54-60`은 여전히 재시도 판단 대기·train_runs 2다. `:79`의 r이 이후 혼자라는 서술도 s2가 시작된 뒤의 부하를 담지 못한다. `watchdog.py:383-385`는 이 상태에서도 평가 실행을 호출하며, `eval_runner.py:248-267,284-288`은 준비된 실행을 평가 큐에 넣고 양 GPU 작업을 시작한다. s2가 사용하는 자원과 충돌할 수 있다.

전환 절차의 수용 조건은 다음과 같다. 이는 운영자에게 제안하는 절차이며 이번 감사에서 수행하지 않았다.

1. 기존 scheduler·watchdog·수동 launcher의 **새 작업 생성 경로**를 식별하고 전환 중 중복 기동을 막는다. 기존 학습은 임의로 종료하지 않는다. 새 DB만 띄우고 구 launcher가 계속 돌게 두지 않는다.
2. 살아 있는 r·s2와 실패한 s를 각각 실행 신원·확정 경로·PID 생성시각·진행·실패 증거와 함께 원장에 등록한다. 소급 입증 못 하는 입력 해시는 UNKNOWN으로 남기고 새 실행의 preflight 면제 근거로 쓰지 않는다.
3. 시뮬·정책·렌더 장치와 동시 부하를 예약·조정하고, 기존 학습이 끝나기 전에 평가가 끼어들지 않는 정책을 확정한다. 코드 사본 변경도 진행 중 프로세스와 분리한다.
4. 새 감독기는 처음에 관측만 하여 구 상태와 대조한다. 실행권을 넘기는 지점과 되돌리는 조건을 정한 뒤 단일 경로로 전환한다.

**판단:** 1단계의 SHA 네 항목도 보강한다. 실제 `env+agent` 설정·CLI override, 시작 checkpoint의 역할과 SHA, 평가 config SHA·기대 집합·규격 판, 실행 코드의 dirty diff와 저장소 밖 파일·라이브러리 판, 확정된 출력 경로가 필요하다. 커밋 하나는 설치된 rsl_rl이나 미커밋 파일을 고정하지 못한다. 실행에 필요한 하네스와 의존 파일을 preflight에서 실제 확인해야 한다.

**판단:** 2단계에는 원장 외에 worker 예외 전달, 자식 프로세스 식별, heartbeat·진행 정체·최대시간 제한, 재기동 후 reconciliation, GPU 예약이 포함돼야 한다. 이를 3단계 뒤로 미루면 원장이 거짓 성공을 영구 기록한다.

**판단:** 3단계의 “반례 넷 전부 거부”는 시험별로 뜻을 나눈다. 결손·잘못된 키·빈 marker는 INVALID, 동시 claim은 하나만 허용, worker 예외는 FAILED와 부모 비정상 종료가 기대 결과다. 단순한 입력 거부 시험 네 개로 줄이지 않는다. 수치 회귀 외에 null·범위·성공 수/분모 모순·원자료와 요약 불일치·기준선 누락·평가 SHA 불일치도 막아야 한다. `base_gates_met` 변경은 tg 소비자까지 같이 적용한다.

## 4. SQLite 설계가 아직 막지 못하는 것

**판단:** 표 구조는 출발점이다. DDL·트랜잭션·복구 구현이 없으므로 P0가 해소됐다고 판정할 수 없다.

| 기존 P0와 직접 확인한 코드 | 제안 설계에서 남는 구멍 | 최소 수용 조건 |
|---|---|---|
| 결손 자료 후보 통과. `verdict.py:89-94,177-197,249-264` | 표에 state만 넣어도 같은 채점기가 잘못된 PASS를 쓴다 | 기대 키·원자료·해시 검증이 완료돼야 검증 결과를 확정. INVALID는 분기 차단 |
| 중복 실행. `eval_runner.py:213-225,259-281` | owner가 NULL인 행 하나의 claim만 보호한다. 중복 job 행, 만료 후 옛 worker, 구 launcher는 별개 | 유일 제약, 상태 조건부 claim, fencing과 소유권 재확인, 구 경로 차단 |
| worker 예외 뒤 성공. `eval_runner.py:203-205,287-297` | jobs 행이 있어도 예외를 기록·전파하지 않으면 RUNNING 누락 또는 거짓 집계가 남는다 | 예정 job 집합 보존, 예외→FAILED, 부모 전파, 예정 집합 전체 terminal 확인 |

### 필드와 제약

**판단:** 다음 계약이 필요하다. 표를 반드시 이 이름으로 더 만들라는 뜻은 아니다.

- **실행 신원:** `run_id`, `attempt_id`, `job_id`의 PK·FK, `UNIQUE(run_id,n)`, 의미가 고정된 idempotency key의 UNIQUE, attempt 출력 경로 중복 금지. SQLite 연결마다 foreign key 집행을 보장한다. idempotency key는 checkpoint·평가 설정·지형·속도·seed 등 실제 작업 입력을 구분해야 한다.
- **job 범위:** runs.ckpt_sha 하나로 시작 checkpoint와 네 평가 checkpoint를 모두 나타내지 못한다. job마다 입력 checkpoint 경로·SHA, 평가 규격·config SHA·기대 산출물을 고정한다. 학습을 다시 돌리지 않고 axis1 한 칸만 재시도할 수 있도록 논리 job과 job 실행 attempt를 구별한다.
- **재시도 계보:** s의 FAILED 기록을 s2로 덮지 않는다. 같은 논리 실행의 attempt이든 별도 run이든 `retry_of`, 승인 근거, 원래 실패, 재시도 횟수·예산을 연결한다.
- **상태 의미:** 실행 상태와 검증 상태, 채점 FAIL/PASS를 분리한다. exit 0인 학습과 기준 미달 정책은 다른 차원이다. 대기·취소·검증 대기·계획 밖 입력을 표현할 상태도 필요하다. UNKNOWN은 실패 확정이나 재시도 허가가 아니다. outbox는 PENDING/SENDING/SENT/RETRY 등 별도 전이를 사용한다.
- **과정 기록:** job별 PID·생성시각·명령/실행 ID, 부모·자식 관계, heartbeat, 마지막 진행 시각, 종료코드·오류·stderr 경로·시간 제한·자원 예약. 현재 attempts.pid 한 개로 병렬 axis 작업을 식별할 수 없다.

### claim·lease·완료 확정

**판단:** `UPDATE ... WHERE owner IS NULL`의 영향 행 수 확인은 단일 claim의 좋은 출발점이지만 충분하지 않다. 제안된 컬럼 이름 `owner_token`과 실제 SQL 이름도 통일해야 한다. claim은 실행 가능한 state를 함께 조건으로 걸고 commit 이후 외부 작업을 시작한다. owner만 비교하면 완료 후 owner를 비운 job을 재실행할 수 있다.

lease 만료는 프로세스 사망 증명이 아니다. 만료를 보고 새 worker를 띄우면 옛 worker가 계속 GPU 작업을 할 수 있다. takeover 전 실제 프로세스·자원을 조정하고 소유권 세대 번호를 올린다. heartbeat·완료 UPDATE는 job ID, owner token, 세대, 기대 state를 모두 확인해야 한다. 오래된 worker는 completion 발행·상태 확정·잠금 해제를 못 해야 한다. DB fencing만으로 이미 실행 중인 외부 프로세스가 멈추지는 않는다.

프로세스 spawn과 DB commit, 파일 rename과 DB commit은 하나의 SQLite 트랜잭션이 아니다. “STARTING 기록 뒤 spawn 전”, “spawn 뒤 PID 기록 전”, “파일 확정 뒤 DB 완료 전” 장애를 복구할 규칙이 필요하다. completion에는 job/attempt/소유권 세대·입력 해시·검증 결과·실제 산출물 해시를 넣고, 재시작 시 파일과 원장을 대조한다. 파일이 있다는 이유만으로 SUCCEEDED로 올리지 않는다.

**판단:** 상태 변경·events 추가·outbox 추가는 같은 트랜잭션으로 확정한다. 상태 version 조건과 append-only 집행이 필요하다. `events`에는 attempt/job 연결을 명시적으로 남긴다. outbox에는 `(event_seq, channel)` 등의 유일 제약, claim·재시도 시각·오류·전송 식별자를 둔다. 외부 전송 성공 직후 DB 기록 전에 죽는 구간 때문에 DB만으로 정확히 한 번 배달을 약속할 수 없다. 중복 가능성을 수신자가 식별할 event ID를 본문에도 넣는다.

**판단:** 승인 시험은 동시 claim뿐 아니라 worker 예외·부모 종료·lease 만료 후 옛 완료·spawn 중간 장애·파일/DB 확정 사이 장애·디스크 쓰기 실패·재기동을 포함한다. 모두 예정 job 누락, 중복 실행, 원자료 덮어쓰기, 거짓 성공이 없어야 한다. 정상 처리 한 번으로 이 조건을 대체하지 않는다.

## 5. 새 tg.py에서 같이 막아야 할 것

**확인됨:** `_out/loop/tg.py:74-84`는 직접 HTTP 전송하며 durable outbox·중복 억제·재시도 상태가 없다. `:105`는 아직 `candidate`를 “배포 후보”로 표시한다. `:87-89,108-109`는 branch 링크와 별도 commit 문자열을 만들 뿐 해당 commit의 문서 존재·접근을 검증하지 않는다. `:78`은 본문을 4000자로 잘라 뒤쪽 링크를 잃을 수도 있다. `:134-136`은 API 응답 ok가 false여도 정상 반환 0이다. 네트워크 예외는 따로 처리하지 않는다.

**판단:** 채점 이름 변경을 이 소비자에도 반영하고 INVALID·미검증을 “미달”과 분리한다. 검증된 보고가 원격에서 읽히는 상태를 확인한 뒤 해당 commit의 고정 링크로 알린다. 운영 실패 알림과 검증 완료 보고를 별개 이벤트로 둔다. 원시 예외에는 토큰이 포함된 URL이 섞일 수 있으므로 로그에 안전한 오류 필드만 남긴다. 이번 감사는 자격증명 파일을 열거나 텔레그램을 보내지 않았다. 실제 배달·폰 링크 접근은 미확인이다.

## 6. App Server 읽기 전용 조회

### 이번 환경에서 확인한 경계

**실측:** `codex --version`은 0.155.0이다. 직접 stdio 프로세스에 initialize를 보내고 stdout·stderr를 각각 읽었지만 초기화 응답을 받기 전에 exit 1로 끝났다. stderr는 **`failed to initialize sqlite state runtime under .../orca/codex-runtime-home/home`**였다. PATH 임시 디렉터리에도 접근 거부 os error 5가 있었다. 따라서 이번 환경의 실패를 핸드셰이크 순서 문제라고 단정할 수 없다. 사용자 세션에서 initialize가 성공했다는 말은 이번 재현 결과와 구별한다.

계정 조회 요청은 initialize 성공 시에만 보내도록 했다. 이번에는 그 조건을 통과하지 못해 rateLimits·usage의 실응답을 받지 못했다. **실제 계정 필드 구조·값은 미확인**이다. 리셋 소비 메서드는 호출하지 않았다. 인증정보 복사·권한 우회도 하지 않았다.

새 스키마 생성도 임시 디렉터리 파일 쓰기의 os error 5로 실패했다. 대신 기존 로컬 생성 산출물 `C:/Users/AI-WS01/AppData/Local/Temp/foothold-audit3-evidence/schema/`를 직접 읽었다. 아래 `S`는 이 경로다. 이는 3차 감사의 문장을 근거로 삼은 것이 아니라 남아 있는 인터페이스 JSON 자체를 확인한 것이다. 새로 생성한 파일이나 실계정 응답으로 오인하면 안 된다.

### 호출 순서와 파라미터

**확인됨:** `S/v1/InitializeParams.json:4-31,64-81`에는 clientInfo.name·version, capabilities.experimentalApi가 있다. `S/ClientNotification.json:4-18`에는 initialized 알림이 있다. 두 조회 메서드의 요청 정의는 `S/ClientRequest.json:10938-10966,10992-11020`이다.

**판단:** 인증된 동일 사용자 환경에서 `codex app-server --stdio`를 유지하고 한 줄당 JSON 하나와 개행을 써서 flush한다. 첫 응답의 같은 id를 확인한 다음 initialized 알림을 보내고 조회한다. stdout은 응답·알림을 계속 읽고 stderr도 별도로 비워야 한다. 여러 PowerShell 단발 파이프로 프로세스를 새로 만들거나 첫 송신 뒤 stdin을 닫지 않는다. 응답은 순서가 아니라 id로 연결하며 timeout·프로세스 종료·JSON-RPC error를 구분한다.

```json
{"id":1,"method":"initialize","params":{"clientInfo":{"name":"lineage_usage_reader","version":"1.0"},"capabilities":{"experimentalApi":true}}}
```

id 1의 성공 응답을 받은 뒤 다음 줄을 순서대로 보낸다. initialized에는 id가 없다.

```json
{"method":"initialized"}
{"id":2,"method":"account/rateLimits/read","params":{"excludeResetCreditDetails":true}}
{"id":3,"method":"account/usage/read","params":{}}
```

**확인됨:** `S/v2/NullableGetAccountRateLimitsParams.json:12-24`에서 `excludeResetCreditDetails`는 별도 리셋권 상세 조회 생략 옵션이다. 생략/false는 상세 조회를 유지하며 조회 자체는 소비가 아니다. `supportsLunaReserve`도 존재하지만 자동 fallback 지원을 선언하는 값이므로 이 읽기 전용 파서는 보내지 않는다. `S/v2/NullableGetAccountTokenUsageParams.json:12-22`의 threadId는 선택 필드다. `{}`는 계정 범위, 특정 threadId는 해당 thread의 추정 usage 조회다. 별도 thread 생성이나 turn 시작은 필요하지 않다.

### 실응답 대신 확인한 스키마 구조

**확인됨:** 아래는 계정값을 제거한 응답 복사본이 아니라 **스키마 기반 형식 요약**이다. 선택 필드 생략·null과 알 수 없는 새 필드를 허용해야 한다.

`account/rateLimits/read`의 result (`S/v2/GetAccountRateLimitsResponse.json:143-258,286-337`):

```text
rateLimits: RateLimitSnapshot                 필수
rateLimitsByLimitId?: { [limitId]: RateLimitSnapshot } | null
accountId?: string | null
ordinaryUsageAllowed?: boolean | null
rateLimitResetCredits?: { availableCount: integer, credits?: ResetCredit[] | null } | null
rateLimitUpsell?: 임의 JSON

RateLimitSnapshot:
  limitId?, limitName?, normalModelSlug?: string | null
  planType?: string enum | null
  primary?, secondary?: RateLimitWindow | null
  credits?: { hasCredits: boolean, unlimited: boolean, balance?: string | null } | null
  individualLimit?: { limit: string, used: string, remainingPercent: integer, resetsAt: integer } | null
  spendControlReached?: boolean | null
  rateLimitReachedType?: string enum | null

RateLimitWindow:
  usedPercent: integer
  windowDurationMins?: integer | null
  resetsAt?: integer | null
```

리셋권 상세 스키마는 같은 파일 `:57-134`에 있다. `ResetCredit`은 `id, grantedAt, resetType, status`가 필수이고 `title, description, expiresAt`은 nullable 선택 필드다. 상세 `credits=null`과 빈 배열은 다르며 배열 길이가 availableCount보다 작을 수 있다. 상세 id를 로그에 기록하거나 소비 요청에 연결할 필요는 없다.

`account/usage/read`의 result (`S/v2/GetAccountTokenUsageResponse.json:4-187`):

```text
summary: {
  currentStreakDays?, lifetimeTokens?, longestRunningTurnSec?,
  longestStreakDays?, peakDailyTokens?: integer | null
}
dailyUsageBuckets?: [{ startDate: string, tokens: integer }] | null
threadUsage?: {
  threadId: string,
  estimatedUsageCreditsMicros: integer,
  estimatedUsageUsdMicros?: integer | null,
  groups: [{
    estimatedUsageCreditsMicros: integer,
    model?, reasoningEffort?, speed?: string | null,
    inputTokens?, cachedInputTokens?, netNewInputTokens?,
    outputTokens?, totalTokens?: integer | null
  }]
} | null
```

**판단:** primary/secondary 위치로 주간 창을 가정하지 말고 windowDurationMins와 limitId를 읽는다. 조회 실패·null을 0%로 바꾸지 않는다. ordinaryUsageAllowed가 없을 때 퍼센트만으로 사용 허가 회복을 추론하지 않는다. usage의 토큰 누계·추정 credits와 rateLimits의 포함 사용량 한도를 동일 지표로 합치지 않는다. 실제 응답 확보 전에는 이 구조를 테스트 fixture로 쓸 수 있을 뿐 실연동 완료라고 보고할 수 없다.

## 7. 감사 범위·산출·검증 상태

**확인됨:** 코드 판은 HEAD `f6097623885dec33836ed51ccde928f13740ab68`에서 조사했다. 직접 읽은 파일의 SHA-256은 다음과 같다.

| 파일 | SHA-256 |
|---|---|
| `_out/loop/watchdog.py` | `db600e5e3e2ce1ba39954180cf0554e4c75c95ac626f89b127ac3eb5bb6595b5` |
| `_out/loop/eval_runner.py` | `5b9d715351b09bf61757aba31184e9df7282ad9a8f997169e01d2459f50e5d8e` |
| `_out/loop/verdict.py` | `60bdaef7f2c6dd9bb9b0d079296e11fa5b6c658828ae524a5f316bf51f65d855` |
| `_out/loop/tg.py` | `66d2566e757ed8ea0f1f0fa66dfcd4eea9afcbd5ee8834b5e80ca3e24d15cc3d` |

`git pull origin main`은 Already up to date였다. 문서 작성 전에 분류 두 절을 넣어 감사 이슈 생성을 시도했으나 GitHub API 프록시 `127.0.0.1:9` 연결 거부로 실패했다. 이슈 생성·새 브랜치·PR·발행을 완료했다고 보고하지 않는다. 기존 작업 브랜치와 사용자 변경을 유지하고 요청된 이 파일만 작성했다.

코드·상태·학습 파일을 고치지 않았고 학습·평가·텔레그램 전송·리셋권 소비를 실행하지 않았다. CPU 집계와 작은 gradient 시험만 했다. SQLite 운영 설계는 정적 검토이며 새 구현의 동시성·복구 통과 판정이 아니다.

**실측:** 저장소 규칙의 별도 검증을 `codex exec --model gpt-6-astra -c model_reasoning_effort=high -s read-only --skip-git-repo-check`로 시도했다. 감사문을 믿지 말고 tfevents를 직접 다시 세며 한국어·근거·오해·과장을 검증하도록 요청했다. 그러나 모델 실행 전에 `failed to initialize in-process app-server client: 액세스가 거부되었습니다. (os error 5)`로 exit 1이었다. 내용 검증의 통과·실패 판정이 아니며 별도 발행 전 검증은 미완료다. 검증 가능한 환경에서 재검증한 뒤 공식 발행해야 한다. 권한 우회나 리셋 소비로 해결하지 않았다.

자체 형식 확인에서는 머리 여섯 항목과 em dash 0개를 확인했다. 이는 독립 내용 검증을 대체하지 않는다.

## 판 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-09-23 | 4차 방향 감사. 전체 scalar 재집계, 실패 전파 경로 한정, 전환 절차·SQLite 계약·읽기 전용 조회 구조 점검 |
