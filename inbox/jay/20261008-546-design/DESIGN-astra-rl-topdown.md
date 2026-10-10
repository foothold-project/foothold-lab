> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · ASTRA 검토 · 2026-10-10
> 근거: TASK-astra-3-rl-design.md · EXP-weekend-moects.md · SURVEY-star-code.md · VERIFY-astra.md · VERIFY-astra-2.md · #546 · 아래 고정 SHA의 코드 직접 열람
> 요지: MoE-CTS의 Isaac Lab 재현은 몸 감각 기반 비교군으로 시작한다. 실행·평가·재시작 조건을 보완하고, 지형 노출과 지형 입력을 분리해 시험한 뒤 AME-2를 판단한다
> 상태: 설계 초안 · 실행하지 않음 · 예산과 수치 기준은 팀장 확정 전 제안

# S3 · 주말 재현 카드 검증과 RL Top-down 실험 설계

## 1. 먼저 확인한 근거

### 검토 범위와 코드 위치

의뢰서의 일곱 문서와 [#546 본문 및 10/8 RL 방향 댓글](https://github.com/foothold-project/foothold-lab/issues/546#issuecomment-6059477202)을 읽었다. 다음 코드의 해당 부분을 직접 열었으며, 앞선 조사 표의 행 번호를 그대로 복사하지 않았다. 이 문서는 원문을 고치거나 학습을 실행한 결과가 아니다.

| 표기 | 실제 위치와 고정 판 |
|---|---|
| `LAB/` | `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/star-src/wertyuilife2__go2_rl_robotlab/` · SHA `28b4516d22617b11aeaf8ead63cc00b0c0bcd1bd` |
| `L/` | 위 저장소의 `source/robot_lab/robot_lab/tasks/go2/` |
| `R/` | 위 저장소의 `source/rsl_rl/rsl_rl/` |
| `AME/` | `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/star-src/leggedrobotics__ame2_minimal/` · SHA `8beb9a688d67882828019583f7d5a78e3517f233` |
| `JEPLO/` | `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/star-src/ASIG-X__JEPLO/` · SHA `460e2272907af053d6e66b57fec71fdbe6ca1774` |
| `IL/` | `C:/isaac/IsaacLab/` · 로컬 소스. 새 실험 환경이 실제 import할 파일과 같은지는 미확인 |
| 프로젝트 상대 경로 | `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/` 기준 · 검토 HEAD `bd6122da0b32b246bf234f91d5480cd8d0ac1929` |

세 외부 clone은 검토 시 `git status --short`가 비어 있었다. `tmp/star-src`는 조사 위치이므로 장기 실험 원본·로그를 그곳에만 두는 것은 피한다. 실제 실행 준비 때 별도 실험 체크아웃과 보존 경로를 정한다. 이번에는 새 폴더를 만들지 않았다.

### 카드 판단에 직접 영향을 주는 사실

| 확인한 사실 | 근거 | 카드에 미치는 영향 |
|---|---|---|
| **확인됨:** 등록 task는 `RobotLab-Go2-v0`, runner는 `MoECTSRunnerCfg` | `L/__init__.py:20`~27 | 대상 식별은 맞다 |
| **확인됨:** README는 공식 Isaac Lab 구현이자 Gym판의 reproduction이라고 소개한다. 동시에 reward·motor·history·DR 차이를 명시한다 | `LAB/README.md:21`, :251~264 | 논문 원 실험과 조건까지 같은 재현이라고 부를 수 없다 |
| **확인됨:** student 입력은 policy history, teacher는 critic 그룹을 받는다. height scan은 critic에만 있다 | `L/env_cfg.py:122`~243, `R/modules/actor_critic_moe_cts.py:210`~234 | 배포 student는 앞으로의 빈 지지면을 직접 보는 정책이 아니다 |
| **확인됨:** 10프레임 history, actor 현재 관측 45차원 구성, height grid 0.1m·1.6×1.0m 설정 | `L/env_cfg.py:65`~71, :124~165, :235~243 | history 450·scan 187은 코드 구성에서 계산한 값. 실행 텐서 shape·순서는 별도 확인 대상 |
| **확인됨:** 기본 16,384 env, 24 step/iteration, 300,000 iterations, 500 간격 저장 | `L/env_cfg.py:469`, `L/rsl_rl_cfg.py:72`~79 | 10 iter smoke 뒤 무제한 본 학습으로 넘길 카드가 아니다 |
| **확인됨:** 명령 확대가 20,000·50,000 iter, 정지 비중 변화는 1,500까지, reward 변화는 1,500·5,000까지다 | `L/mdp/commands.py:365`~379, `L/env_cfg.py:450`~458 | 몇백 iter의 보행이나 reward 증가로 완성 성능을 판정할 수 없다 |
| **확인됨:** `gap`·`stepping_stones` 학습 비중은 0이다 | `L/mdp/terrains.py:240`~256 | 이 코드의 재현만으로 우리 핵심 gap·희소 발판 학습이 끝나지 않는다 |
| **확인됨:** reward와 지형 레벨은 학습 조건 자체가 바뀌는 동안 기록된다 | `L/mdp/curriculums.py:176`~220 | reward와 레벨 상승만으로 기본 명령·험지 성능 개선을 판단하면 안 된다 |
| **확인됨:** `play.py --fix_commands`는 `(1,0,0)`으로 고정하고 지형 curriculum을 끈다 | `LAB/scripts/rsl_rl/play.py:91`~121 | 이 영상 하나가 정지·후퇴·횡이동·회전 평가를 대신하지 않는다 |

[MoE-CTS 논문 v4 초록](https://arxiv.org/abs/2602.00678v4)도 proprioception-only 정책임을 명시한다. 따라서 **추정:** 이 선택의 가치는 우선 “지형을 직접 보지 않는 강한 몸 감각 정책이 어디까지 해내는가”를 측정하는 데 있다. “발 놓을 곳을 미리 안다”는 최종 질문에는 다음 지형 입력 실험이 필요하다. 성공한 보행만 보고 지형 인지를 입증했다고 해석하지 않는다.

### 실행 전에 잡아야 할 두 가지 코드상 위험

**재시작과 curriculum 시계. 확인됨:** `R/runners/on_policy_runner_cts.py:167`~181의 저장 항목은 model, 두 optimizer, iteration, infos다. :260~279의 load는 환경의 `common_step_counter`, 지형 레벨, command curriculum 상태, RNG를 복원하지 않는다. 기본 호출 `LAB/scripts/rsl_rl/train.py:218`은 추가 환경 상태를 전달하지 않는다. 반면 `L/mdp/commands.py:129`와 `L/mdp/curriculums.py:186`은 환경 카운터를 사용한다. `Go2Env`는 기본 `ManagerBasedRLEnv`를 상속하고(`L/env/go2_env.py:6`~12), 검토한 로컬 기본 환경은 `IL/source/isaaclab/isaaclab/envs/manager_based_rl_env.py:74`에서 그 카운터를 0으로 초기화한다.

실제 `gradual_reward_weight_modification` 함수만 AST로 추출해 CPU에서 답을 아는 입력으로 실행했다. base-height weight는 환경 iteration 0에서 -1, 2,500에서 -5.5, 5,000과 20,000에서 -10이었다. **추정:** runner iteration만 20,000으로 되살리고 새 환경 카운터가 0이면 reward schedule은 다시 -1에서 시작한다. 전체 Isaac 실행으로 재시작을 재현한 것은 아니므로 실제 실행 영향은 미확인이다. 또한 runner :108~110은 `start_it + num_learning_iterations`만큼 돈다. resume의 `--max_iterations`를 최종 누적 iteration으로 오해하면 예산이 늘어난다.

**GPU 1 배치. 확인됨:** 비분산 경로에서 `--device`는 env에 적용되고(`LAB/scripts/rsl_rl/train.py:129`), runner는 별도 `agent_cfg.device`를 받는다(:202). 검토한 로컬 `IL/source/isaaclab_rl/isaaclab_rl/rsl_rl/rl_cfg.py:144`의 기본값은 `cuda:0`이다. 따라서 **추정:** `--device cuda:1`만 적으면 시뮬과 학습이 다른 GPU를 쓸 수 있다. 실행 환경에서 env·runner·tensor device를 모두 기록해 같은 물리 GPU를 가리키는지 확인한다. 두 GPU는 독립 프로세스 두 개로 사용하고, 이번 카드에 distributed 학습을 추가하지 않는다.

### 현지 장비와 예산

**확인됨:** 이번 조회에서 RTX 5080 두 장, 각 16,303 MiB였다. `nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader` 결과는 GPU 0: 210 MiB·0%, GPU 1: 7,075 MiB·6%였다. **GPU 1은 이 시점에 빈 장치가 아니다.** 어떤 프로세스인지, 현재 학습 가능 여유가 충분한지는 미확인이다. 기존 프로세스를 종료하지 않았다.

**확인됨:** README :158의 RTX 4090 사례는 500 iter 학습·저장에 약 30분이다. 이를 단순 비례하면 20,000 iter는 20시간, 176,000은 176시간, 300,000은 300시간이다. **추정일 뿐 RTX 5080 실측 예상 시간이 아니다.** 기본 설정의 환경 transition 수는 `N × 24 × I`: 10 iter도 3,932,160, 20,000은 7,864,320,000, 300,000은 117,964,800,000이다. 병렬 환경의 transition을 물리 step 수나 벽시계 시간으로 혼동하지 않는다.

## 2. 카드 판정과 고칠 내용

**판정: 고친 뒤 진행.** 대상은 유지한다. 다만 첫 목표를 **“고정된 Isaac Lab 구현의 제한 예산 재현 및 student 기준선 측정”**으로 바꾼다. 논문 수준 성능의 완전 재현은 주말 완료 조건이 아니다. B-2가 결정되지 않아도 이 비교군과 평가 도구는 유용하지만, 이 결과로 최종 속도형 계약을 확정하지 않는다.

긴 학습을 시작하기 전에 카드에 다음을 반영할 것을 권고한다.

1. **격리와 판 고정:** 기존 `isaac311`을 유지하고 새 env에서 실제 import 경로·패키지 판·asset 해시·코드 SHA와 diff를 기록한다. “버전명이 같음”과 실제 호환은 구분한다. `isaaclab 2.3.2.post1` 요구와 로컬 2.3.2 차이도 기록한다.
2. **상한:** 아래 E0로 정한 env 수 `N*`와 E1 예산을 사용한다. 16,384가 안 들어가면 수만 줄인 별도 조건으로 명명하고 논문 원 조건과 동등하다고 적지 않는다. env 수를 줄이면 같은 iteration에서도 표본 수가 줄지만 curriculum 시점은 그대로라는 차이를 남긴다.
3. **smoke 완료 조건:** crash 없음 외에 finite 입력·행동·loss, 정확한 actor/teacher 분기, 관절 순서, checkpoint load, export history/reset 일치, device 일치를 확인한다. 알고리즘을 바꾼 수리와 설치 호환 수리는 따로 기록한다.
4. **평가:** 우리 기존 235차원 actor에 450차원 데이터를 억지로 넣지 않는다. policy adapter는 다르게 두고, 동일 물리 상태·명령·성공 규칙을 기록하는 평가층을 공유한다. 최소한 student 전용 기본 명령 평가를 이번 범위에 넣는다. reward만 남기는 카드는 부족하다.
5. **재시작:** 우선 한 번의 연속 학습으로 예산을 정한다. resume은 위 시계·optimizer·RNG·지형 상태의 복원 범위를 시험한 뒤 쓴다. 복원하지 않은 부분이 있으면 ‘정확한 연속 재개’가 아니라 ‘동일 부모의 새 단계 실험’으로 표시한다.
6. **결과 상태:** 실행 정상 / 학습 진행 / 공통 평가 통과 / 공개 benchmark 대조 / 논문 성능 재현을 별도 상태로 기록한다. 앞 상태 통과가 뒤 상태 통과를 뜻하지 않는다.

`R/utils/exporter_cts.py:34`~46, :57~91은 45차원 한 프레임과 내부 history를 전제하고 batch size 1만 허용한다. export parity는 시간 순서가 있는 입력과 reset 직후 입력으로 시험한다. 여러 env에 JIT 하나를 공유해 history가 섞이지 않게 한다. RoboGauge는 보조 benchmark로 유지할 수 있으나, adapter의 scale·관절 순서·PD·reset·정책 반환 형태 검증 전 점수는 성능 근거로 채택하지 않는다. 파일명에 든 `0.6984`도 이번 실행의 목표 점수나 재현 완료선으로 쓰지 않는다.

## 3. 목표를 측정 가능한 질문으로 내리기

아래 수치·표본·일정은 전부 **추정 · 제안**이다. 기존 보고서의 승인된 성공 규칙이나 팀장의 결정을 바꾸지 않는다. 사전 등록 후 결과를 보고 문턱을 움직이지 않으며, 미달도 가치 있는 실험 결과로 남긴다.

### 공통 평가 계약 Q

| 묻는 능력 | 관측할 것 | 1차 선별선 |
|---|---|---|
| 기본 명령을 따르는가 | 평지에서 vx=±0.3m/s, vy=±0.3m/s, wz=±0.5rad/s, 전진 후 zero-command. 방향별 독립 에피소드 | 이동 구간 첫 1초 제외 body-frame vx·vy 각 MAE ≤0.15m/s, wz MAE ≤0.20rad/s. 정지 별도 기준. 각 명령 cell 생존 ≥95%, 해당 명령 기준 통과 ≥90% |
| 정지 명령을 실행하는가 | vx=0.3을 5초 준 뒤 0을 5초. 정지 시간·거리와 yaw drift | 1초 안에 평면 속도 <0.05m/s 및 yaw rate <0.10rad/s가 되고 이를 1초 유지. 정지 거리 ≤0.20m. 학습 정책의 zero-command 반응과 시스템 STOP override는 별개 |
| 험지를 통과하면서 명령도 지키는가 | 20초, 동결한 시작점·명령·collision mesh. 4m gate와 경로 corridor. 생존·진척·추종·방향을 별도 기록 | 4m 도달, 낙상 없음, corridor 최대 이탈 ≤0.30m, 위 추종 문턱. 조합별 분모와 실패 축을 보고. 좁은 길은 경계 자체로 corridor를 더 좁혀 사전 고정 |
| 발을 놓는 선택이 지형 정보에 반응하는가 | 발별 swing/touchdown, 충돌 메시 위 지지 면적, 착지 여유, slip, 도달. 관측 제거·위치 뒤섞기 대조 | 정답 지형 입력의 낙상 없는 유효 통과 비율이 대조보다 ≥10 percentage points 개선하고, 위험 touchdown 비율이 상대 ≥20% 감소. 행동이 바뀌었다는 사실만으로는 통과 아님 |
| 새 능력을 얻으면서 무엇을 잃었는가 | 기본 명령 cell별, 기존 험지 family별 변화. 평균과 최악 cell 모두 | 각 기본 명령 통과율 하락 ≤5pp, 각 기존 family 통과율 하락 ≤5pp, 각 명령 MAE 악화 ≤10%. 대조 MAE가 0에 가까우면 상대비 대신 사전 정한 절대선 사용 |

**평가 구현과 원 규칙 보존:** `sim/eval/metrics.py:493`~524의 기존 `overall_success`는 survival·progress·tracking·direction의 AND다. :527~545의 `traversal_success`는 tracking을 뺀 분석값이며 기존 보고서에서 이를 성공률로 바꾸면 안 된다. 위 새 계약은 `Q-v1`처럼 별도 판으로 기록한다. 후퇴·횡이동에는 명령 방향을 따라 좌표를 정의하고, 회전·정지에 전진거리 판정을 적용하지 않는다. `sim/eval/command_response_metrics.py:146`~190은 1초 연속 저속 창을 검사하지만 yaw까지 검사하지 않으므로 Q의 정지 조건을 그대로 모두 구현한 함수는 아니다.

**낙상과 착지의 의미:** base contact >1N 종료만으로 모든 낙상이 잡힌다고 가정하지 않는다. 몸 기울기 >60°가 0.2초 지속, 지지면 아래로 base 추락, base collision 중 하나를 평가용 낙상 기준으로 제안한다. touchdown은 발별 수직 접촉력이 1N을 넘어 2 policy step 유지되는 이벤트로 정의하고, 단위와 sensor period를 확인한다. 위험 touchdown은 발바닥 footprint가 실제 지지면 밖으로 나가거나, 지지면 안쪽 여유가 2cm 미만인 경우로 기록한다. 2cm는 안전 인증값이 아니라 비교용 제안이다. 실제 발 mesh·지지 폭을 먼저 읽고 불가능한 지형을 제외한다. 발은 빈 공간에서 contact 자체가 생기지 않을 수 있으므로 **무접촉 추락도 별도 실패로 세어** 위험 touchdown 분모 밖으로 빠지는 문제를 막는다. 이 착지 계측기는 현재 구현됐다고 확인하지 않았다.

### 지형·표본과 평가 누출

- 학습 지형은 `L/mdp/terrains.py:183`~256의 기본 8개 nonzero 항목을 원명으로 기록한다. 우리 rough6와 이름·난이도가 동일하다고 묶지 않는다. 별도 비교표에 기존 FOOTHOLD 평가 6종·gap·rails 결과를 붙인다.
- validation은 checkpoint 선택과 설계 선별용, holdout은 최종 확인용으로 분리한다. 난수 seed뿐 아니라 mesh 해시·폭·단차·진입 방향·DR 값까지 동결한다. 결과를 보고 고른 대표 영상은 별도 표시한다.
- gap 폭 0.1·0.2·0.3m, 정면·45°·90° 접근을 1차 후보로 둔다. 실제 생성 가능한 기하와 명령 수행 공간을 확인해 목록을 동결한다. rails와 sparse footholds는 발 footprint와 회전 여유 확인 뒤 추가한다. 도랑을 학습한 뒤 같은 계열의 다른 폭을 ‘완전히 미경험 종류’라고 부르지 않는다. `sim/eval/terrain_split.py:286`~340의 기하 계열 분류도 대조한다.
- 선별은 각 cell 100 episodes, 동일 evaluation seed 1000~1099로 짝지어 시행한다. 임계값 부근 또는 채택 후보만 500 episodes로 확대하고 비율의 Wilson 95% 구간과 paired 차이 구간을 남긴다. 학습 seed와 평가 seed를 분리한다. 수백 env가 같은 학습 seed를 썼다는 사실을 학습 반복 수로 세지 않는다.
- 두 training seed는 최소 변동 점검이다. 두 seed에서 개선 방향이 일치하고 Q의 퇴행선을 지켜야 후보를 올린다. 유의한 개선을 주장할 때 차이의 95% 구간이 0을 가로지르면 ‘개선 미확인’으로 둔다. 최종 논문 수준 주장에는 세 번째 이상 독립 학습과 동일 benchmark 조건의 추가 예산을 정한다.

### 관측과 실행 계약

body-frame 명령 vx·vy·wz, rad/s·m/s, 관절 이름 순서, action scale 0.25, physics 0.005s·decimation 4, sensor update·history 순서·reset을 고정한다. 근거는 `L/env_cfg.py:110`~117, :124~243, :483~501이다. obs normalization은 기본 False를 유지하고 teacher 전용 속도·토크·contact·GT height를 student에 몰래 넘기지 않는다.

시뮬의 no-hit는 `sim/eval/gap_observations.py:56`~80의 finite 판별과 `miss_value=+1`을 참고할 수 있다. **+1은 해당 높이 표현에서 no-hit를 표시하기로 한 encoding이며 물리적 바닥의 실측 높이가 아니다.** `L/env_cfg.py:228`~229의 clip·scale을 적용하면 +2.5가 된다. 실제 LiDAR의 미관측·가림을 모두 ‘구멍’으로 단정하지 않는다. 센서 입력 단계에서는 valid mask·관측 시각·지연·frame을 별도 계약으로 둔다. 이 변환을 재현 E1에 조용히 끼워 넣지 않는다.

## 4. 실행 순서와 실험 카드

**공통 예산 규칙:** iteration은 24 policy steps/env를 뜻한다. `N*`는 E0가 정한 동일 env 수다. 모든 쌍은 같은 N*·환경 transition·부모 checkpoint·PPO·reward·command·DR·curriculum·평가 조건을 쓴다. 달리 쓰면 한 변수의 효과로 해석하지 않는다. 시간은 성능 예측이 아니라 **실행 상한**이다. startup·저장·평가 여유 20%를 뺀 뒤 E0의 실측 iteration 시간 p95로 가능한 수를 계산하고 양쪽의 iteration 예산을 함께 줄인다. 벽시계만 같고 transition이 다른 모델을 표본 효율 비교로 쓰지 않는다. 상한 도달은 실패나 수렴의 증거가 아니라 `예산 종료`다.

### B-2 결정 전에 할 수 있는 것

#### E0 · 실행 조건과 계측 검증

- **질문:** 이 고정 구현을 두 GPU에서 조건을 알고 재현할 수 있는가?
- **출발 코드:** `LAB/scripts/rsl_rl/train.py:121`~145, :193~218, `L/rsl_rl_cfg.py:72`~79, `R/utils/exporter_cts.py:34`~91.
- **바꿀 변수 하나:** capacity probe의 `num_envs`만 512 → 2,048 → 4,096 → 8,192 → 16,384로 올린다. 다음 크기는 이전 peak VRAM을 보고 안전하게 들어갈 때만 시도한다. seed 42·24 step·나머지 기본 설정은 같다. 최종 크기는 4의 배수여야 teacher/student 3:1 분할과 맞는다(`R/algorithms/moe_cts.py:123`~130).
- **비교군:** 같은 코드의 작은 env 수. 이 시험은 정책 성능 비교가 아니다.
- **예산:** 각 크기 10 iter, 선택한 N*에서 별도 500 iter timing run. GPU 0, 최대 2시간. GPU 1은 비워진 뒤 같은 N*로 10 iter device 확인, 최대 20분. timing run checkpoint를 E1 초기 정책으로 쓰지 않는다.
- **수치 판정:** NaN/Inf 관측·action·loss 0건, API/PhysX capacity 경고 0건, GPU 메모리 여유 ≥2GiB, tensor shape/관절 12개 순서 fixture 100% 일치. 같은 1,000 step 관측 시퀀스와 episode reset에서 native student 대 export 최대 action 오차 ≤1e-5. 답이 정해진 평지·단차·구멍 fixture에서 높이/좌표 오차 ≤1e-5m인 수학 변환과 충돌·ray의 별도 허용오차를 구분한다. legacy no-hit의 동작은 예상값대로 기록하고 고친 것으로 가장하지 않는다.
- **다음 조건:** 실제 import·두 device·Q 계측 확인과 N* 확정. export만 막히면 native student 평가로 E1은 진행 가능하되 sim2sim 재현은 미완료. native policy의 관절·관측 계약이 틀리면 긴 학습을 시작하지 않는다.

#### E1 · 공개 구현의 제한 예산 기준선

- **질문:** 이 구현의 student가 기본 명령과 기존 험지를 함께 수행하는 기준선을 만드는가?
- **출발 코드:** `L/rsl_rl_cfg.py:72`~79, `L/mdp/commands.py:365`~433, `L/env_cfg.py:347`~458, `R/modules/actor_critic_moe_cts.py:225`~234.
- **바꿀 변수 하나:** 학습 경과 iteration. 무작위 초기화에서 seed 42, 기본 설정으로 500·5,000·10,000·20,000·20,500 checkpoint를 비교한다. N*를 바꿨다면 이미 E0에서 고정한 이식 조건이다.
- **비교군:** 같은 run의 앞 checkpoint. 공개 176k 정책은 별도 참고군이며 예산·학습 조건이 다르므로 동등 비교군이 아니다.
- **예산:** 최대 20,500 iter, GPU 0 한 장, 학습·저장 상한 28시간, 이후 Q 평가 최대 2시간. iteration 50,000의 최종 명령 확대는 아직 거치지 않는다. 주말 결론도 그 범위로 제한한다.
- **수치 판정:** finite·checkpoint·로그 누락 0건. 기본 명령 Q 통과 여부와 모든 기존 family 결과를 기록한다. 5k→20.5k 개선 또는 plateau를 seed별로 보여주고, 특정 방향 실패를 평균으로 숨기지 않는다. Q를 못 넘으면 ‘실행 재현, 능력 미달’이며 정책 채택은 보류한다.
- **다음 조건:** E2와 비교해 학습 변동을 확인하고 D1·G1로 간다. 20.5k에서 명령 능력이 미달이면 뒤 실험을 무조건 쌓지 않는다. 코드 오류와 학습 부족을 먼저 구분하고, 필요 시 같은 조건으로 55k까지 연장하는 별도 예산을 잡는다. 50k 직후 5k 관찰을 포함한 연장 상한은 seed당 추가 40시간이다. 검증되지 않은 resume으로 연결하지 않는다.

#### E2 · GPU 1의 첫 실험: 독립 seed 반복

- **질문:** E1의 성능과 실패 유형이 seed 하나에만 나타나는가?
- **출발 코드:** `LAB/scripts/rsl_rl/cli_args.py:79`~84, `LAB/scripts/rsl_rl/train.py:126`~145, E1과 동일 config.
- **바꿀 변수 하나:** training seed 42 → 43. task·MoE expert 8·N*·예산·평가 목록은 그대로다. 같은 초기 checkpoint를 공유하면 독립 학습 반복이 아니므로 scratch부터 시작한다.
- **비교군:** GPU 0의 E1 seed 42, 동일 iteration checkpoint. GPU 기종은 같지만 실제 병행 시 throughput과 장치 상태 차이도 기록한다.
- **예산:** 최대 20,500 iter, GPU 1 한 장, 최대 28시간 + 평가 2시간. GPU 1이 비고 E0 device 확인을 통과한 뒤 실행한다.
- **수치 판정:** 두 seed가 Q 기본 명령선과 퇴행선을 모두 지켜야 기준선 후보다. cell별 통과율 차이 >10pp 또는 MAE 차이 >20%면 불안정으로 표시하고 세 번째 seed 검증을 먼저 편성한다. 두 번 같다는 이유만으로 일반화가 입증됐다고 쓰지 않는다.
- **다음 조건:** 공통 실패와 seed 특이 실패를 구분한 표를 만든 뒤 G1 또는 P1의 개입을 고른다. 큰 변동이 있으면 architecture 비교를 보류한다.

#### D1 · teacher의 지형 정보 사용 여부 진단

- **질문:** 현재 teacher는 height scan의 올바른 공간 배치로 이득을 얻는가?
- **출발 코드:** `L/env_cfg.py:225`~229, `R/modules/actor_critic_moe_cts.py:210`~234. teacher는 action sample 대신 같은 mean 경로를 사용하는 평가 adapter가 필요하다.
- **바꿀 변수 하나:** 동일 checkpoint teacher의 height block 공간 순서. 정상 대 고정 permutation. 나머지 privileged 입력·실제 지형·초기 상태·명령은 동일하다. body history student는 height를 바꿔도 출력이 같아야 하는 음성 대조다.
- **비교군:** 정상 teacher. teacher 대 student 격차도 함께 기록하되 teacher는 height 외 privileged 정보도 받아 그 차이 전부를 height 효과로 해석하지 않는다.
- **예산:** 학습 0 iter, 두 seed의 E1/E2 checkpoint 평가, GPU 한 장 최대 2시간, validation cell별 100 episodes/조건.
- **수치 판정:** 학생의 동일 body 입력에서 height만 바꾼 action 최대 차이 ≤1e-6. teacher는 지형 정보 교란 시 유효 통과 비율이 ≥10pp 낮아지는지와 위험 착지·낙상을 함께 본다. 차이가 없으면 해당 과제에서 height 이용 증거 없음. permutation은 분포 밖 교란일 수 있으므로 이것만으로 최종 지형 인지를 입증하지 않는다.
- **다음 조건:** teacher까지 gap에 실패하면 G1의 노출·관측 검증을 우선한다. teacher가 낫고 student가 못 따라오면 P1 지형 입력 실험을 우선할 근거가 된다. D1의 선별 결과가 특정 결론을 미리 보장하지 않는다.

#### G0 · no-hit encoding의 계약 검사

- **질문:** 구멍을 높은 장애물로 해석하는 관측 반전이 있는가?
- **출발 코드:** `L/env_cfg.py:225`~229, `IL/source/isaaclab/isaaclab/envs/mdp/observations.py:292`, `sim/eval/gap_observations.py:56`~80.
- **바꿀 변수 하나:** no-hit 처리만 legacy 대 finite 판별 후 +1 대입으로 바꾼다. hit인 높이의 수식·clip·scale은 그대로다.
- **비교군:** 동일 합성 ray hit 입력의 legacy 출력. 평지·단차·no-hit·NaN·전체 invalid를 따로 시험한다.
- **예산:** 학습 0 iter, CPU fixture와 GPU 한 장의 실제 ray/mesh 대조 최대 1시간.
- **수치 판정:** finite hit의 출력 차이 ≤1e-6, no-hit 최종 출력 +2.5, 비유한 출력 0건. 실제 no-hit pixel·ray 위치와 collision mesh의 대응을 전부 기록한다. NaN과 진짜 no-hit의 원인은 별도 count. 이 검사는 능력 향상 측정이 아니다.
- **다음 조건:** G1·P1 양군에 같은 encoding을 적용하고 별도 설계 판을 부여한다. E1 원본과 성능을 단순 이어 붙이지 않는다. 모든 invalid를 실센서의 구멍으로 처리하는 확장은 금지한다.

#### G1 · 지형 노출의 효과

- **질문:** 기본 명령 분포를 유지하면서 gap을 학습에 넣으면 무엇을 얻고 잃는가?
- **출발 코드:** `L/mdp/terrains.py:251`~256, `L/mdp/commands.py:381`~433, `L/env_cfg.py:347`~458, G0 관측 adapter.
- **바꿀 변수 하나:** scalar p_gap = 0 대 0.10. flat 비중은 0.15−p_gap으로 정해 합계를 보존한다. 다른 지형·난이도 범위·reward·명령을 그대로 둔다. 이는 gap을 위해 flat 표본 일부를 배분하는 단일 mixture 개입이며 gap만의 무비용 추가라고 해석하지 않는다.
- **비교군:** 같은 E1 부모를 복제한 p_gap=0 대조. 두 군 모두 G0 처리를 쓴다. 초기 smoke에서 gap 0.9m 등이 물리적으로 과한 경우 범위를 양군 공통 과제 정의로 먼저 동결하고, p 효과 시험 중 같이 바꾸지 않는다.
- **예산:** seed 42 부모에서 군당 추가 8,000 iter·최대 12시간, 두 GPU에 한 군씩. 통과하면 seed 43 부모에서 같은 쌍을 반복, 추가 24 GPU-hours 상한. stage-reset/복원 방식은 두 군이 동일해야 한다.
- **수치 판정:** validation gap의 Q 통과율 ≥10pp 개선, 기존 family·기본 명령은 Q 퇴행선 이내. gap 진입 횟수·실제 노출 비율·episode 종료·teacher/student 결과를 각각 기록한다. gap 전진만 좋아지고 횡·후퇴가 나빠지면 미채택.
- **다음 조건:** 두 seed 방향 일치 시 지형 mixture 후보로 유지한다. gap 노출 자체가 부족하면 다음 단일 변수는 진입 배치/경로 과제이며, 동시에 reward·네트워크를 바꾸지 않는다. 충분히 노출됐는데 student만 실패하면 P1로 간다.

#### P1 · student에 지형 입력이 필요한가

- **질문:** 같은 학습 문제에서 앞으로의 지형 정보를 주는 것이 몸 감각만으로 넘지 못한 한계를 줄이는가?
- **출발 코드:** `L/env_cfg.py:122`~243, `R/modules/actor_critic_moe_cts.py:87`~118, :225~250, `R/algorithms/moe_cts.py:393`~412. 수정 adapter와 입력 분리는 새로 구현해야 하며 현재 기능이라고 주장하지 않는다.
- **바꿀 변수 하나:** student의 지형 정보 제공 여부. 양군 모두 body history 450 + 현재 height 187 + valid mask 187의 같은 824차원 student encoder를 만들고, 대조군의 추가 374칸만 0으로 막는다. single_obs 45와 actor 입력 77은 보존한다. teacher·critic, 네트워크 폭·parameter 수, reward·지형·명령은 같다. `SingleObsCfg`가 `PolicyCfg`를 상속하므로 policy term을 단순 추가하면 actor까지 변한다. 별도 그룹으로 분리해 이를 막는다.
- **비교군:** 같은 부모 weights를 이식하고 새 입력 가중치를 같은 방식으로 초기화한 masked 군. 원래 450차원 E1과의 차이를 전부 입력 효과라고 하지 않는다. feature 순서·scale·valid mask 의미를 tensor fixture로 고정한다.
- **예산:** 군당 추가 8,000 iter·최대 12시간, 두 GPU 한 군씩. seed 42로 선별하고 통과 시 seed 43 쌍 반복, 추가 24 GPU-hours 상한.
- **수치 판정:** Q의 ≥10pp 지형 개선·위험 착지 ≥20% 감소·퇴행 제한을 함께 적용한다. 학습 예산 부족으로 양군이 덜 배웠으면 ‘효과 없음’이 아니라 미확인. 같은 기하에서 height permutation 평가를 보조로 붙여 실제 지형 배치 이용 여부를 확인한다.
- **다음 조건:** 양 seed 통과 시 ‘GT 지형 입력의 효용’까지만 채택한다. GT ray map은 배포 가능한 LiDAR map과 다르다. 실패면 정보 해상도·배치·노출을 먼저 검사하고 AME-2로 즉시 점프하지 않는다. 변경 입력은 기존 `R/utils/exporter_cts.py:34`~44의 계약과 맞지 않으므로 기존 JIT exporter를 그대로 재사용하지 않는다.

#### P2 · 지형 입력 지연 내성

- **질문:** 지형 정보를 쓰는 이득이 작은 지연에도 유지되는가?
- **출발 코드:** `L/env_cfg.py:495`~499와 P1의 새 terrain observation adapter. 센서 특징을 student로 넘기는 참고 코드는 `JEPLO/training/rsl_rl/rsl_rl/modules/actor_critic_teacher_cts.py:133`~160이다.
- **바꿀 변수 하나:** 동일 P1 정책의 terrain observation age만 0 대 40ms. 50Hz 정책에서 두 step 지연이며 height·mask·pose·timestamp를 묶어 지연한다. 좌표 재투영 방법은 두 조건에서 동일하다. noise나 dropout을 함께 넣지 않는다.
- **비교군:** 같은 checkpoint의 무지연 입력. JEPLO 전체 정책과의 비교가 아니다.
- **예산:** 학습 0 iter, GPU 한 장 최대 2시간, 같은 100 episodes/cell.
- **수치 판정:** Q 통과율 저하 ≤5pp와 기본 명령 절대선 유지. 지연의 frame·timestamp 오차 fixture ≤1e-6, stale 입력 발생 count 기록. 못 지키면 perception contract의 허용 지연을 아직 확보하지 못한 것.
- **다음 조건:** 지연에 약하면 시간 정합과 history부터 보완한다. 강하면 다음 별도 실험으로 noise 크기 또는 dropout 비율 하나를 택한다. GT의 40ms 통과를 실제 LiDAR·depth 배포 완료로 부르지 않는다. JEPLO 전체 재현은 이후 별도 환경·예산이 필요한 후보로 둔다.

### B-2 결정 뒤에만 확정할 것

위 실험은 속도형 연구 비교군을 만드는 일이므로 먼저 할 수 있다. **최종 Nav2 연결, 명령 timeout·STOP 우선순위, 상위와 하위의 소유, 목표형 task/reward로의 전환은 B-2/S2 뒤에 확정한다.** AME-2가 목표형이라는 이유로 Track B의 순정 보행을 대체하도록 범위를 넓히지 않는다.

#### C1 · 선택한 명령 계약의 전달 검사

- **질문:** 선택한 상위→하위 연결이 명령의 의미와 시각을 보존하는가?
- **출발 코드:** 속도형이면 `L/env_cfg.py:136`~141와 `L/mdp/commands.py:429`~433. 목표형이면 `AME/ame2/ame2/tasks/mdp/observations.py:263`~297, `AME/ame2/ame2/tasks/mdp/commands.py:51`~80. 실제 프로젝트 gateway adapter는 S2에서 경로와 SHA를 확정해야 한다. 아직 존재하는 파일처럼 적지 않는다.
- **바꿀 변수 하나:** 같은 명령 trace의 주입 경로만 direct 대 새 bridge. 속도형·목표형 정책 둘을 여기서 맞바꾸지 않는다. 목표형은 발행 때 world에 고정한 목표가 이동 중 같은 장소를 가리키는지 본다.
- **비교군:** 선택된 계약의 direct 주입. 목표형 Go2 checkpoint가 검증되지 않았으면 합성 좌표 fixture까지만 하고 로봇 rollout 결과는 미확인으로 둔다.
- **예산:** 학습 0 iter, CPU contract fixture + GPU 한 장 최대 2시간, 1,000 step trace와 평가 100 episodes.
- **수치 판정:** direct/bridge의 같은 시각·frame 명령 최대 오차 ≤1e-6, 50Hz 하위의 반영 지연 ≤1 policy tick을 초기 제안으로 둔다. 실제 비동기 시스템의 허용 latency·timeout은 S2 확정값을 우선한다. expired 명령의 재사용 0건, STOP 뒤 이전 목표 복귀 0건. 모션은 Q 정지와 선택 계약의 도달 조건을 별도로 통과해야 한다.
- **다음 조건:** 계약 시험 통과 후 통합 연구로 진행한다. 위치 목표 도달을 vx·vy·wz 추종으로 환산하지 않는다. `velocity × horizon`의 위치 증분을 AME-2에 넣었다고 속도 계약을 지킨 것은 아니다.

#### A1 · 마지막 후보: AME-2의 map encoder 도입

- **질문:** 정보가 이미 충분한데도 남은 발판 선택 실패를 attention 기반 map encoder가 줄이는가?
- **출발 코드:** `AME/rsl_rl/rsl_rl/models/AME2_models.py:48`~85, `AME/ame2/ame2/tasks/mdp/observations.py:120`~134. 현재 공개 구현의 G1 teacher와 mapper/student 제외 범위는 `AME/README.md:45`~47. 이것을 Go2 완제품으로 실행하는 실험이 아니다.
- **바꿀 변수 하나:** 선택된 Go2 계약 안의 terrain encoder만 MLP 대 AME 방식 FC/CNN·global pooling·attention 모듈로 바꾼다. 동일한 map·valid 처리·command·actor 출력12·critic·reward·PPO를 유지한다. AME encoder의 x,y 채널은 두 군에 똑같이 주고 비교군 MLP의 parameter 수를 ±5% 이내로 맞춘다. 명령·지도 해상도·optimizer까지 바꾸면 이 실험의 결과로 해석하지 않는다.
- **비교군:** 같은 입력과 예산의 MLP encoder. 기존 P1이 CTS distillation 구조면 teacher/student 사이 어디를 바꾸는지 먼저 고정한다. actor·teacher·student를 동시에 AME 전체로 교체하지 않는다.
- **예산:** 구현 fixture와 10 iter smoke 최대 2시간/GPU, 군당 5,000 iter·최대 12시간, 두 GPU 한 군씩의 **pilot**. 판정 불가면 학습을 더 했다는 근거 없이 논문 재현 성공으로 올리지 않는다. seed 반복은 다음 별도 예산.
- **수치 판정:** Q 지형 개선 ≥10pp·위험 착지 감소 ≥20%·기본 명령 퇴행선 준수, inference p95 <20ms와 peak VRAM 여유 ≥2GiB를 제안한다. speed는 연구용 장치에서 실제 측정하며 실기 latency로 대체하지 않는다. attention 그림만으로는 채택하지 않는다.
- **진입 조건:** 아래 AME-2 관문을 모두 충족한 뒤 별도 카드로 확정한다. 다음 주에 자동 실행하도록 예약하지 않는다. 이식·교정 시간이 예산에 들어가지 못하면 이후 주로 넘긴다.

## 5. 주말과 다음 주의 배치

**추정 · 우선순위이며 완료 약속이 아니다.** 10/10~10/11에는 E0 → E1/E2를 가장 먼저 수행한다. GPU 1 해제 시점과 E0 처리량 때문에 E2 시작은 늦어질 수 있다. 주말 결과는 실제 끝난 동일 iteration checkpoint로 보고한다. 20.5k까지 못 갔으면 짧은 예산의 결과로 명시한다.

| 기간 | GPU 0 | GPU 1 | 남길 판단 |
|---|---|---|---|
| 10/10~10/11 | E0, E1 seed 42 | 사용 가능 확인 후 E0, E2 seed 43 | 실행 조건·기본 능력·변동. 논문 수준 재현 완료 선언 없음 |
| 10/12 | D1·G0·Q 검증 | 대조 평가 또는 E2 잔여 | 지형 미노출인지, teacher/student 정보 차이인지 분리 |
| 10/13~10/14 | G1 대조, 이어 P1 masked | G1 gap, 이어 P1 map | 충분한 동일 예산의 한 변수 비교. 앞 관문 미달이면 다음 비교 보류 |
| 10/15~10/16 | 가장 유효했던 비교의 seed 43 대조 | 같은 비교의 seed 43 변경군 | 획득·손실·변동과 채택 여부 |
| 여유와 조건 충족 시 | P2 또는 C1 | baseline 평가·보존 | B-2 증거, 실제 지연 한계. A1 착수 여부만 재논의 |

초기 2개 학습의 시간 상한 합계는 56 GPU-hours다. G1·P1 선별은 각각 24 GPU-hours, 선택한 비교 하나의 seed 반복은 24 GPU-hours다. 학습 합계 **128 GPU-hours**, E0·계측·평가·저장 여유는 최대 20 GPU-hours를 별도로 둔다. 두 비교를 모두 두 seed로 반복하면 24 GPU-hours 추가다. E1/E2를 55k까지 연장할 필요가 생기면 최대 80 GPU-hours가 더 필요하므로 P1/반복 또는 A1을 미룬다. 이 숫자는 할당 상한이며 두 장의 VRAM이 합쳐진다고 계산하지 않는다. CPU·RAM·디스크 병목과 동시 실행 처리량은 E0 이후 실측한다.

**GPU 1이 비면 선택할 하나는 E2다.** 근거는 첫 run의 성능·변동·실제 처리량이 아직 미확인이고, seed 42와 43이면 설치·관측·알고리즘 조건을 유지한 채 그 변동을 볼 수 있기 때문이다. 처음부터 “MoE 없는 CTS”를 붙이면 모델 폭과 parameter 수까지 달라진다. `R/networks/moe.py:125`~162에서 expert 수가 projection 크기와 gate 출력을 동시에 바꾸므로 `expert_num=1`도 MoE routing만의 순수 효과가 아니다. 그 ablation은 기준선과 예산을 확보한 뒤 별도 비교로 남긴다.

## 6. AME-2를 들이는 증거와 B-2의 결정 범위

**확인됨:** 공개 AME 구현은 현재 G1 teacher 중심이며 neural mapping·student training은 README에서 제외돼 있다. 목표 관측은 `[x,y,sin(yaw_error),cos(yaw_error)]`다. [AME-2 논문 v3](https://arxiv.org/abs/2601.08485v3)는 지도 처리와 perception-control 결합을 다루지만, 이 논문 존재가 우리 Go2 이식의 재현을 보증하지 않는다. 석헌 실험의 student·mapper 미완료, 비교 조건의 한계는 `docs/research/20261007-ame2-go2-v1-v6.md:398`~437에 기록되어 있다. 이번에는 원격 모델·로그를 다시 계측하지 않았으므로 그 성능 수치를 새로 확인했다고 하지 않는다.

따라서 **추정 · 권고:** AME-2 진입에는 다음 다섯 근거가 필요하다.

1. 기본 명령·기존 험지·gap/sparse foothold의 동일 평가와 두 seed 기준선이 있다. 잘 되는 영상 하나나 reward 합계만 있는 상태는 아니다.
2. G1로 지형 노출 부족을 점검했고, P1에서 지형 정보의 효용 또는 단순 encoder의 재현 가능한 한계를 확인했다. 0.1m grid가 경계를 놓친다면 먼저 해상도 하나를 바꾸는 비교를 한다. 관측에 없는 구조를 attention이 복원할 것이라고 가정하지 않는다.
3. 실패 장면의 ray 위치·valid mask·발 접촉·command·policy action·collision mesh를 같은 시간으로 기록해 입력 오류와 제어 실패를 구분했다. 지연·frame 오류가 원인이면 P2/S2를 먼저 고친다.
4. B-2에서 속도형 유지인지 목표형 채택인지와 STOP/timeout·소유를 정했다. 속도형이면 A1은 encoder의 제한적 차용이며 ‘AME-2 전체 재현’이라고 부르지 않는다. 목표형이면 task·reward·도달 판정까지 별도 설계를 확정한 뒤 그 안에서 encoder만 비교한다. 목표점 명령을 넣는 일이 보상항 하나 변경과 같은 실험은 아니다.
5. Go2 자산·12관절·센서·mapper/student 계획과 실제 단일 GPU 메모리 예산을 확인했다. 학습 map으로 움직이는 teacher 연구와 센서로 움직이는 student, Track A 트윈 평가와 Track B 순정 보행은 각각 완료 상태가 다르다.

AME-2를 처음부터 모두 이식하는 대안은 현재 최종 인터페이스와 입력 효용이 미정이라 여러 원인을 한 번에 바꾼다. JEPLO 전체부터 시작하는 대안도 LiDAR sensing·JEPA·CTS·reward 구성을 한꺼번에 들여온다. 반면 본안은 몸 감각 기준선 → 노출 → 입력 → 시간 정합 → 필요한 구조의 순서로 **어떤 정보·조건 때문에 좋아졌는지**를 남긴다. 최종 B-2와 일정 채택은 팀장이 결정한다.

## 7. 실험마다 남길 최소 기록과 이번 검토의 한계

각 run에는 run ID·질문·변수 diff 한 개·부모 checkpoint SHA-256·source SHA/dirty diff·실제 import 경로·conda/pip 판·GPU 식별과 device·seed·N*·rollout 길이·누적 transitions·iteration·wall time·VRAM·저장 주기를 남긴다. env/agent YAML은 `LAB/scripts/rsl_rl/train.py:213`~218이 쓰지만 runner에 전달한 dict와 실제 runtime 값까지 같은지는 별도 출력으로 검증한다. 학습 중 변한 command 범위·reward weight·terrain level도 checkpoint와 함께 남긴다.

평가에는 teacher/student 구분·native/export 구분·관측/정규화/결측 계약·joint 순서·PD·mesh hash·command trace·센서 시각·valid mask·각 실패 축·분모·CI·영상을 함께 둔다. “얻은 것 / 잃은 것 / 아직 모르는 것 / 다음 한 변수”를 결과 카드의 필수 칸으로 한다. 총 reward·curriculum level·latent loss·expert 사용률은 진단값이며 채택 점수의 대체물이 아니다. validation 최고값으로 고른 checkpoint와 holdout 결과를 구분한다.

**직접 수행한 확인:** 코드·문서·이슈 읽기, 장치 상태 조회, 예산 산술, 실제 reward curriculum 함수의 알려진 입력 시험 4건, 정지 계측 함수의 알려진 입력 시험 2건. 정지 fixture는 0 명령 후 0.2초에서 1초 저속 창이 시작되는 경우 `(0.2,None)`, 길이가 모자란 경우 `None`을 반환했다. 이는 함수 동작 시험이지 로봇 성능 시험이 아니다.

**미확인:** 새 env 설치 완료·Isaac 실행 가능성·16,384 env 적재·실제 throughput·checkpoint 재시작 동등성·MoE-CTS 성능·RoboGauge 점수·상세 접촉 계측·새 adapter·센서 배포·주말 완료 가능성. 이번 의뢰는 읽기 전용이므로 설치·학습·프로세스 종료·원문 수정·commit·push는 하지 않았다. 과제 설계안과 실행 검증 완료를 혼동하지 않는다.

검토한 주요 입력 SHA-256:

| 파일 | SHA-256 |
|---|---|
| `TASK-astra-3-rl-design.md` | `9c5646fd66d0674206ad02a6b41f3f84aa24026783967856e95c2976f6ec9105` |
| `EXP-weekend-moects.md` | `1cecad453ce17a60ea9469bfd2955d1bf78126b063af415b94bdae5b3c6f5c23` |
| `SURVEY-star-code.md` | `42c70b8bedecddb338900b5dbf0214dd4cef91177290780f4ef78a4d6e53bb7f` |
| `VERIFY-astra.md` | `96aac39f3462b748ba38206a1395d82ed84c3f7e0c88d13a34a86d58f8768b71` |
| `VERIFY-astra-2.md` | `984f9f0e8f626b855f481f982b5bc7a77df70888c76a5f3a9fc89afb1c573b89` |
| `docs/research/20260929-locomotion-direction.md` | `ffdaf54d47c7427409b316ef50acddbb31e2f75f6aef6a6d172674174947bf32` |
| `docs/research/20261007-ame2-go2-v1-v6.md` | `e1e7315abe0e76e5f6a86be9cc6168acf2e87f0ff548f0a5441afaaa87cd5314` |
