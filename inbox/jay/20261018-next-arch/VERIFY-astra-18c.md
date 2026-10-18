> 분류: A/정책학습 · 구현 검증
> 작성: 오흥재 요청 · ASTRA 검증 · 2026-10-18
> 근거: b1 고정 묶음 116개 SHA 대조 · 18a/18b 계약 · 지정 보고서 · 설치 Isaac Lab 소스 · 독립 CPU 반례
> 요지: 지도·PPO 연결은 구현됐다. b1 시작 import는 실패하며 감독기 예외 격리·저장본 추적·종료 처리는 장기 실행 전에 고쳐야 한다.
> 상태: 검토 완료 · GPU/Kit 미실행 · 실제 장기 학습·재개·물리 보행 성능은 미확인

# ASTRA 18c · Step1 b1 고정 코드 검증

**판정: b1 그대로의 기동은 권고하지 않는다. M1/M2 학습 구조는 CPU에서 확인됐지만 시작 import가 실패하고, 장기 실행 감독기는 상태 기록 오류로 두 작업을 함께 끝내거나 저장본 추적을 놓칠 수 있다. 아래 지정 결함을 수정해 기존 위임으로 진행하면 된다. 별도의 팀장 동의나 ASTRA 재승인 절차를 추가하지 않는다.**

## 1. 대상과 확인 수준

고정 대상 F는 `C:/Users/AI-WS01/s2_lab/step1_18b_b1_frozen/`이다. `STEP1-18B-B1-SHA256SUMS.txt`의 **116개 항목을 직접 해시 대조했고 모두 일치**했다. 목록 자체 SHA256은 `3cbeb9f6b8894c8647936633a4f215148b8840ebaecf41db69ec2531c433f43b`이다. 부모 `fixtures/model_20000.pt`는 `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`이며 CPU로 읽었다.

`VERIFY-astra-18a.md`·`18b.md`, 작업 사본의 `REPORT-step1-18b-a.md`·`REPORT-step1-18b-b1.md`·`HANDOFF-step1-18b.md`를 대조했다. 이번 판정은 **b1의 바이트**에만 적용한다. 검토 도중 가변 HANDOFF에 15:23 b2 수정과 실제 smoke 실패 보고가 추가됐다. 그 보고를 b2 검증 완료로 옮기지 않는다. 아래 import 결함은 그 보고와 별개로 b1에서 직접 재현했다. b2의 수정 여부는 이번 범위에서 독립 확인하지 않았다.

행 번호 약칭:

| 약칭 | F 아래 실제 경로 |
|---|---|
| actor | `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py` |
| PPO | `source/rsl_rl/rsl_rl/algorithms/moe_cts.py` |
| runner / proxy | `source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py` / `step1_proxy.py` |
| train | `scripts_rsl_rl/train_step1.py` |
| setup / resume / env | `source/robot_lab/robot_lab/tasks/go2/step1_setup.py` / `step1_resume.py` / `env_cfg.py` |
| terrain / foot / rewards | 같은 Go2 폴더의 `mdp/step1_terrain.py` / `foot_train_step1.py` / `rewards.py` |
| queue / launch / approval / watch | F 루트의 `step1_queue.py` / `launch_step1.py` / `step1_approval.py` / `step1_watch_status.py` |
| tests | F 루트의 `test_step1_cpu.py` |
| Lab | `C:/isaac/IsaacLab/source/isaaclab/isaaclab/` |

CPU 실행은 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`, `CUDA_VISIBLE_DEVICES=-1`, torch `2.7.0+cu128`, numpy `1.26.0`으로 했다. GPU·Isaac·실제 승인 도구·실제 Job 자식은 실행하지 않았다. 코드와 원자료를 수정하지 않았다. 반례의 프로세스·영수증·파일 쓰기는 메모리 대역으로 치환했다.

## 2. 띄우기 전 고칠 것

### 2.1 시작 자체를 막는 절대 import

**확인됨.** `resume:13`은 `from step1_setup import ...`이다. 실제 train은 `robot_lab.tasks.go2.step1_resume`를 import하며, launcher의 PYTHONPATH에는 패키지 루트와 `scripts_rsl_rl`만 들어간다. `tasks/go2`는 없다. 재개 옵션을 주지 않은 첫 기동도 이 import를 지난다. [train:121~125; launch:35~36]

실행 경로에 해당하는 sys.path에서 이 파일을 로드하니 `ModuleNotFoundError: No module named 'step1_setup'`이었다. 같은 소스에 시험에서 쓰는 Go2 디렉터리만 추가하면 `step1-resume-v1` 로드가 성공했다. **tests:20이 Go2 디렉터리를 직접 넣어 결함을 가렸다.** `py_compile`·pyflakes·21개 시험 통과는 이 진입 경로 성공의 증거가 아니다.

수정은 패키지 기준 import로 통일하는 것이다. 시험도 실제 진입점 경로를 사용해야 한다. 이는 한 import 수정이며 학습 구조를 다시 설계할 이유가 아니다.

### 2.2 감독기의 상태 기록 오류가 다른 GPU까지 종료한다

**확인됨.** `queue:261~303`의 시작 루프가 `try/finally` 밖에 있다. 첫 작업이 기동된 뒤 두 번째 작업의 `publish()`나 상태 저장이 실패하면 첫 작업의 명시적 정리·finish를 건너뛴다. 감시 루프에서는 반대로 `publish()` 예외가 바깥 `finally`로 올라가 **남아 있는 모든 owner를 종료**한다. 그 `finally`에는 MAI finish가 없다. [queue:304~386; watch:27~37,71~85]

독립 메모리 시험 결과:

| 입력 | 실제 코드의 결과 |
|---|---|
| 상태 기록 정상, 두 가짜 자식 정상 종료 | M1/M2 각각 `finish(ended)`·close, `EVALUATION_PENDING` |
| M1 기동 후 M2의 첫 publish에서 예외 | M1 launch만 기록되고 stop·close·finish 경로 미실행 |
| 두 가짜 자식이 살아 있는 동안 publish에서 예외 | M1/M2 모두 stop·close, **finish 0회** |

실제 Windows 자식 종료를 시험한 것이 아니라, **현재 Python 제어 흐름에서 어떤 호출이 누락되는지** 재현한 결과다. 실제 프로세스가 끝나면 OS의 Job handle 정리로 자식이 종료될 수 있지만, 이는 정상적인 arm별 종료 영수증을 대신하지 않는다.

**최소 수정:** 시작부터 owner 수명 전체를 정리 범위에 포함하고, 각 run_id의 종료 상태를 별도로 보장한다. mai-watch의 스키마·파일 기록 실패는 해당 상태 채널 오류로 기록하며 건강한 학습 둘을 함께 죽이지 않는다. 실험 소유권·절대 마감 같은 핵심 안전 상태와, 표시용 watch 실패를 구별한다. 이미 허용된 GPU 작업의 중단과 재시도 낭비를 막기 위한 수정이다.

### 2.3 metrics가 먼저 도착하면 저장 완료 checkpoint를 영구히 건너뛴다

**확인됨.** runner는 metrics를 먼저 쓰고 checkpoint를 나중에 저장한다. queue는 해당 iteration에서 파일이 없으면 넘어가면서 `last_checkpoint_checked`를 그 iteration까지 올린다. 다음 poll에서는 이미 지난 저장 시점을 다시 보지 않는다. [runner:201~216,245~254; queue:315~326]

고정 소스의 해당 AST 분기를 그대로 실행했다. 20,500 metrics가 먼저 있고 파일은 아직 없는 입력, 다음 poll에서 파일이 생기고 iteration이 20,501인 입력을 주었다. checkpoint 질의는 `[20500]` 한 번뿐이고 `checkpoint_path`가 끝내 없었다. 처음부터 파일이 존재하는 양성 대조는 같은 코드에서 정상 기록됐다.

파일 자체가 사라지는 결함은 아니다. **감독기 영수증과 재개 경로가 저장본을 놓치는 결함**이다. 특히 마감·실패 종료는 최종 목표 iteration만 찾으므로 최신 중간 저장본을 복구하지 않는다. `DEADLINE`의 “Keep committed checkpoint”라는 문구와 실제 state가 어긋날 수 있다. [queue:227~228,349~367]

**최소 수정:** 발견되지 않은 저장 시점은 pending으로 남겨 재검사한다. 또는 실제 완료된 `.pt`를 기준으로 마지막 저장 iteration을 전진시킨다. 마감·실패 시 최신 완료본을 한 번 더 수집하고 경로·SHA·누적 update를 기록한다. `.tmp`는 완료본으로 채택하지 않는다.

### 2.4 STOP·마감·장치·USD 격리 계약은 부분 구현이다

**18b §7에 요구했던 기존 안전 기능의 반영 확인이며 새 승인 관문이 아니다.**

- **STOP:** queue·train·launch에 STOP 파일 처리 경로가 없다. 기존 STOP을 재사용했다고 볼 수 없다.
- **마감:** queue는 deadline/승인 만료를 poll하다 곧바로 `stop_owned()`한다. trainer가 갱신 경계에서 저장하고 끝내는 경로는 없다. 최대 499개 완료 갱신과 진행 중 갱신이 마지막 정기 저장 이후에 남을 수 있다. 현재 구현은 “마감 강제 종료 후 기존 완료본 유지”이지 “경계 저장 후 정상 종료”가 아니다. [queue:329~337; runner:215~223]
- **감독기 정체:** `approval_finish`는 최대 30초를 기다리고, checkpoint CPU load·hash·watch 파일 처리도 같은 감독기 스레드다. 다른 arm의 deadline 점검도 그동안 밀린다. Job Object는 감독기 프로세스가 죽으면 보호하지만 감독기가 살아서 멈춘 경우까지 해결하지 않는다. 묶음 안 독립 hard-deadline watchdog은 없으며 외부 설치·연결 여부는 미확인이다. [approval:38~40; queue:353~380; `s2_job_owner.py`의 소유권 구현]
- **GPU:** receipt와 watch는 고정 UUID를 기록하지만 실행 환경은 `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `CUDA_VISIBLE_DEVICES=0/1`이다. 실제 CUDA 장치와 그 UUID가 일치하는지는 확인하지 않았다. UUID 결박 완료라고 보고하면 과장이다. 승인에 사용하는 UUID를 실제 visible device에도 사용하고 시작 기록에서 대조하는 편이 명확하다. [launch:25~26; approval:12~14,57~59; watch:59]
- **USD:** 이 묶음은 `spawn.usd_dir`를 실행별로 지정하지 않는다. 설치된 Lab converter 기본값은 초 단위 시각과 `random.randrange(10000)`이다. 같은 시드 상태·같은 초이면 같은 폴더가 된다. 이 식의 CPU 반례에서 두 경로 모두 `usd_20261018_153500_1824`였다. 실제 이번 두 Kit가 충돌했는지는 미확인이다. **동시 두 작업에 경로 격리 보장이 없는 것은 확인됨**이다. run_id별 USD 경로를 주면 시작 시차에 기대지 않아도 된다. [F `source/robot_lab/robot_lab/assets/unitree.py:127~130`; train:186~187; Lab `sim/converters/asset_converter_base.py:65~85`, `envs/manager_based_env.py:96`]

기존 상시 승인을 유지한 채 STOP·남은 시간 신호를 trainer에 전달하고, 짧은 종료 유예 안에 저장을 마친 뒤 종료하도록 연결한다. 넘으면 해당 Job 가족만 강제 종료한다. 이미 운용하는 독립 마감 장치가 있다면 그것을 연결하면 된다. 이 수정에 별도 사람 참석이나 실험마다 새 동의를 요구할 이유는 없다.

### 2.5 발 광선 invalid 종료는 한 control step 늦은 값을 읽는다

**소스 순서와 CPU 반례로 확인됨.** Lab은 termination을 먼저 계산하고 reward를 뒤에 계산한다. 그런데 `_step1_foot_invalid_env`는 발 reward 질의에서 새로 쓰고 termination은 그 캐시를 그대로 반환한다. timestamp 검사나 reset 시 캐시 해제도 없다. [Lab `envs/manager_based_rl_env.py:203~221`; foot:69~88; env:465]

따라서 t에서 발생한 invalid가 t의 종료에 반영되지 않고 t+1에 반영된다. t에서 다른 이유로 reset됐으면 새 episode를 이전 invalid로 종료시킬 수도 있다. CPU 호출 순서 시험도 `termination(t)=False`, reward에서 invalid 설정, `termination(t+1)=True`였다. 실제 invalid 발생률은 미확인이다.

**최소 수정:** 현재 step의 발 질의를 termination 이전 또는 그 term 내부에서 한 번 계산하고 reward가 같은 캐시를 재사용한다. 캐시는 step과 env별 episode/reset에 귀속한다. tile 밖·invalid인 env만 종료하고 나머지는 계속 학습한다는 18a 계약은 유지한다. `foot_outside_tile`에는 이미 현재 step 확인이 있지만 invalid term에는 없다. [terrain:133~152]

## 3. 돌리면서 보완할 수 있는 것

아래는 첫 학습을 기다리게 할 사유로 쓰지 않는다. 다만 **실행 중 Python 파일을 바꾸면 이미 import된 프로세스에도 반영된다고 생각하면 안 된다.** 별도 분석·평가기·다음 실행판을 준비하고, 해당 데이터를 해석하거나 재개하기 전까지 적용한다. 감독기 수정은 그 감독기 기동 전에 반영하는 것이 맞다.

### 3.1 1,000 update 대용 지표의 시간창과 terminal 프레임

분기는 있고 JSON도 작성된다. 독립 평가가 아니라는 `training_rollout_proxy_not_independent_eval` 표기도 올바르다. 그러나 proxy는 매 1,000회 구간이 아니라 **해당 프로세스 시작 이후 누적**이다. 재개하면 새로 0에서 시작한다. gap·base-height 카운터도 resume metadata에 보존하지 않는다. 서로 다른 길이의 누적치를 단순 비교하면 최근 퇴행을 가릴 수 있다. [runner:117,203~212; proxy:27~58; resume:40~74]

또한 proxy 입력은 `env.step()` 뒤의 raw 상태이다. done env는 이미 reset돼 새로운 접촉·속도·명령·관측을 갖는다. 마지막 action은 이전 episode의 것이다. 현재 done/timeout 개수는 셀 수 있지만 terminal 순간의 flight/stall/nonfinite 해석에는 reset 혼합이 있다. [runner:133~146; Lab `envs/manager_based_rl_env.py:215~241`]

수정: 구간 시작/끝 update·segment_id·누적/구간 구분을 기록하고, reset 전 값으로 집계하거나 done 프레임을 운동 지표 분모에서 제외한다. moving_steps를 따로 둬 정지 명령 비중과 flight 비율을 분리한다. 종료 이유별 수와 단순 timeout을 구분한다. **timeout_success_proxy는 틈 통과 성공률이 아니다.** 지금 자료는 학습 중 조기 이상 탐지용으로만 쓴다.

### 3.2 post-distill KL과 NaN 기록은 자동 대응과 다르다

teacher/student KL이 PPO 안의 lr·조기 중단을 제어하는 것은 확인했다. student 증류 뒤 KL은 최대 1,024개 student 표본으로 한 번 기록하며 그 값으로 증류 lr을 낮추거나 이후 update를 중단하지 않는다. 이를 “증류 후 KL도 자동 제어한다”라고 쓰면 틀린다. [PPO:300~345,420~452,467~485]

이는 18b의 “학습 중 KL 기록”을 막는 결함은 아니다. 큰 post-distill KL이 관측되면 증류 갱신 원인부터 확인하며, 측정 전 새 threshold나 중단 규칙을 임의로 늘리지 않는다. 1,000회 proxy의 nonfinite count 역시 자동 복구를 의미하지 않는다.

### 3.3 최종 checkpoint 검사기는 NaN을 받아들인다

**확인됨.** `queue.verify_checkpoint()`는 iteration·사전 키·actor 열 수·map prefix·resume 일부 키를 검사한다. 모델과 Adam tensor의 finite 여부 및 전체 state 적재 가능성은 확인하지 않는다. [queue:194~223]

실제 M1 객체와 두 Adam에서 만든 CPU payload를 메모리로 넘겼다. 정상 payload가 통과한 뒤 **actor 첫 가중치 하나만 NaN으로 바꿔도 같은 SHA 반환 경로로 통과**했다. 따라서 최종 확인서가 모델 수치 건전성까지 검증했다고 표현하면 안 된다.

첫 rollout을 이 검사 수정까지 기다릴 필요는 없다. 최종 채택·평가·재개 전에 모델·optimizer의 floating tensor finite 검사와 해당 arm의 strict state 적재 검사를 보완한다. 이미 고정된 hash·phase·unit 검사는 유지한다. 모델을 다시 학습하거나 새 승인을 받을 문제는 아니다.

### 3.4 재개 상태는 많이 개선됐지만 “정확한 재개” 범위를 좁혀야 한다

두 Adam·lr·상한·warmup·누적 update·지형 level/type/origin·명령 범위·보상·RNG는 실제 capture/restore 경로에 있다. 20,000 저장본을 복원해 다음 iteration 20,001, 완료 update 1로 이어지는 CPU 대조도 통과했다. [resume:28~74,78~134; train:280~313]

다만 물리 episode·명령 timer·관측 이력은 저장하지 않고 reset한다. 이를 보고서가 명시한 것은 옳다. 실제 Kit reset 뒤 난도 검증은 CPU fixture로 대신할 수 없다. saved RNG를 reset **후** 복구하므로 물리 초기화까지 예전 RNG 순서와 연속이라는 주장도 할 수 없다. [train:294~297; resume:137~171]

추가 정리 사항:

- `plan_resume()`이 물려받은 `config.optimizer_policy`는 여전히 `restart_both_from_E1`이다. 실제 경로는 restore이고 train receipt는 맞게 쓴다. 감독기 config도 `restore_both_exact`에 맞춰야 한다. [queue:99,137~154; train:325~326]
- checkpoint는 부모 SHA와 unit을 담지만 **그 checkpoint를 만든 소스·유효 설정 digest**는 담지 않는다. queue의 현재 code/config SHA만으로 과거 저장본의 제작 코드를 복원할 수 없다. 출처 state와 연결하거나 저장 metadata에 넣는다. 출처 식별 추가이며 임의로 모든 코드 변경 재개를 금지하라는 뜻은 아니다. [resume:40~74; queue:101~108,147~154]
- 현재 실행기는 같은 P1 unit의 canary 한 번을 지원한다. 의도된 정기 P1→P2 전환을 모두 canary로 처리할 수 있는 다일 대기열은 아직 아니다. 보고서도 P2·평가기 미완료라고 썼으므로 이를 구현 완료로 올려 적지 않는다.

### 3.5 평가기·P2·메모리는 병행 항목이다

P2는 현재 명시적으로 거절하고, P1 완료는 `EVALUATION_PENDING`으로 남긴다. 이는 없는 평가를 성공으로 꾸미는 것보다 정확하다. **P1 학습을 평가기 완성까지 묶어 둘 필요는 없다.** 별도 작업으로 CTS student 평가 loader와 동일 사례 초기화, P2 공통 예산·지형을 준비한다. M1/M2의 학습 중 지표만으로 화요일 채택을 완료했다고 보고해서는 안 된다. [train:141; queue:363~364; HANDOFF의 남은 작업]

M2의 큰 PPO minibatch 메모리 위험은 여전하다. `data=list(generator)`로 모든 epoch의 minibatch를 잡고, map token의 forward/backward 비용도 더해진다. 첫 update 최고 allocated memory 기록은 있으나 실제 peak·처리량·Kit 메모리는 미확인이다. 원래 CTS에도 있던 list 구조를 이번 M2가 새로 만들었다고 탓해서는 안 된다. M2가 OOM이면 두 arm 공통 env·표본 예산을 함께 조정하고, attention 효과와 batch 변경을 섞어 설명하지 않는다. [PPO:259~261; runner:124~125,192~193; 18b §2.4]

## 4. 18a·18b 계약별 코드 대조

| 계약 | 판정과 근거 |
|---|---|
| teacher rollout 지도 | `act→update_distribution→_actor_input`, z_T 사용. actor:275~282,316~331. CPU 호출 확인 |
| student rollout 지도 | z_S 계산만 no_grad, map 계산은 블록 밖. actor:322~327. CPU gradient 시험 통과 |
| student inference 지도 | 기존 student 이력·single obs와 같은 map 경로. actor:333~341. CPU 호출·초기 출력 확인 |
| PPO 재계산 지도 | teacher/student 각각 `policy.act`로 같은 경로 재계산. PPO:285~295. M1/M2 CPU update 확인 |
| PPO optimizer 등록 | map encoder 모든 parameters를 PPO에 추가, student Adam에는 넣지 않음. PPO:102~110. 소유권·파라미터 변화 CPU 확인 |
| 기존 77열 복사, 새 16열 0 | actor:297~314. split GEMM 284~295. CPU 초기 행동 동일성 확인. CUDA bit 동일성은 미확인 |
| 구멍 처리 +2.5 | `height_gap_step1.py:7~16`의 raw miss +1, env:224~228 clip/scale, actor:268~273 마지막 187열. 세 관측 wiring·순서/scale 반례 CPU 확인 |
| M2 구조 | CNN 1→8→16, xyz MLP 3→16, local 32→64, global MLP+max, 1-query 4-head attention, 128→16. actor:43~80. 18b 권고 구조 반영 |
| 격자 순서 | actor:59~75, Lab `sensors/ray_caster/patterns/patterns.py:43~53`, `patterns_cfg.py:55`. xy flatten에 맞는 H=11,W=17. yaw 정렬 env:67. CPU 좌표 시험 통과 |
| query detach | z_T/z_S를 query에 넣을 때만 detach. 기존 actor 경로 유지. actor:78,326. latent grad 없음·height/single grad 있음 CPU 확인 |
| 첫 시작 lr·optimizer | train:145~165, setup:60~78. PPO 5e-5, student 1e-4, 부모 PPO lr 상한·50 update ramp ceiling. PPO:237~244. 두 Adam 재시작은 첫 시작에만 적용 |
| E1 curriculum 끝값 | setup:125~142에서 누적 step·명령·zero .1·보상 끝값 반영. 과거 per-env 난도는 원자료가 없어 5/6 분포로 재구성했음을 명시. 정확한 옛 분포 복원이 아님 |
| gap 30%·가장 쉬운 행 | setup:95~116,157~173. 기존 지형 비중 합 .7, gap .3, gap env row 0, 실제 생성 폭 table 기록. row 0과 모든 폭이 정확히 .10 m라는 주장은 다름 |
| 바닥 없는 gap 낙하 종료 | terrain:7~9,96~130; env:462~465. 지면 원점보다 root가 .30 m 낮으면 해당 gap env 종료. 접촉 없는 무한 추락 방지. 실제 궤적 미확인 |
| 발 보상 adapter | foot:11~25,28~83. env×4발×9광선 batched, 고정 크기 cache/counter, any-by-type·중앙 override 유지. CPU 경계·비용 시험 통과. invalid 종료 시점 결함은 §2.5 |
| base-height 무효 광선 | rewards:500~522에서 비율 계수 추가, runner:186~196에서 기록. 이 비율의 실제 값은 미확인. 보상 비활성화 구간을 정상 지형 신호로 해석하지 않음 |
| 저장·재개 metadata | runner:226~254, resume:28~171, train:280~313. 핵심 복원 CPU 확인, 시작 import·실제 Kit reset·과거 코드 출처 한계는 위 본문 |
| 큐 감시·MAI receipt/finish·watch | 정상 경로 연결은 존재. queue:241~386, approval:50~79, watch:40~85. 예외 시 arm 격리·finish 보장·저장본 추적은 미충족. 실제 서비스 가동 미확인 |

## 5. 독립 시험과 한계

**솔이 보고한 21개 전체를 독립 재실행했다고 주장하지 않는다.** 파일 생성·실제 프로세스 시험을 피하고 다음 11개를 선택해 직접 실행했다. 예정 11, 실행 11, PASS 11, 실패 0, 오류 0, skip 0이다. tests의 함수명은 아래와 같다.

- `test_gap_known_answer_and_old_counterexample`
- `test_three_observation_wires_use_same_function`
- `test_critic_height_contract_catches_reorder_and_scale`
- `test_e1_shared_weights_and_initial_actions`
- `test_m2_grid_query_and_actor_contract`
- `test_m2_ppo_owns_map_and_updates_it`
- `test_m1_cpu_rollout_map_and_optimizer`
- `test_student_kl_above_limit_stops_remaining_update`
- `test_rollout_proxy_known_answer`
- `test_gap_fall_and_tile_reset_only_affected_env`
- `test_foot_training_adapter_boundary_and_bounded_reset_state`

이외 독립 확인은 다음과 같다. 모두 소스 바이트 수정 없이 메모리에서 수행했다.

| 시험 | 관찰과 범위 |
|---|---|
| 실제 sys.path와 시험 sys.path import 대조 | 실제 구성 실패, 시험 전용 Go2 경로를 넣으면 성공. §2.1 |
| checkpoint poll의 늦게 생긴 파일 | 동일 AST에서 늦은 파일 누락, 먼저 존재한 파일 양성 대조 성공. §2.3 |
| 감독기 정상 종료·시작 중 예외·감시 중 예외 | 가짜 owner와 receipt만 사용. 정상 각각 finish, 예외 경로 정리/finish 누락과 양 arm 종료 확인. §2.2 |
| 실제 runner.save·capture·restore | 실제 M1·두 Adam payload, torch.save 목적지와 rename만 메모리 치환. tmp→최종 경로 호출, 두 optimizer state, 다음 iteration 20,001 확인. Windows 실제 디스크 atomic성·Kit 재개 시험은 아님 |
| 마지막 확인서의 NaN 반례 | 정상 payload 통과 뒤 actor 한 값 NaN으로 변이해도 통과. §3.3 |
| update 999/1000와 최종 저장 분기 | runner의 해당 AST·실제 proxy를 실행. 999에는 metrics만, 1000에는 metrics+proxy, 마지막 `model_20999.pt`, `last_model=True` 호출. 파일은 메모리 sink. 해당 분기에 추가 import 누락은 발견하지 못함 |
| invalid 종료의 호출 순서 | 새 invalid가 다음 termination에서 읽힘. 실제 발생 빈도는 미확인. §2.5 |
| USD 기본 경로 이름 | 같은 초·같은 난수 상태에서 동일 이름 산출. 실제 두 Kit 충돌 재현은 하지 않음 |

**GPU 없이 확인할 수 없는 것은 남아 있다:** M2 메모리/처리량, native preload의 실제 DLL 상태, 발 raycast가 현재 mesh와 foot frame에 정확히 닿는지, 재개 뒤 물리 reset과 난도 보존, 실제 UUID 매핑, 장시간 Windows 저장 경쟁, Job Object 가족 종료, mai-watch 수집 서비스와 실제 MAI 승인 범위. CPU 통과를 이 항목들의 통과로 대신하지 않는다.

## 6. 실행 담당자에게 넘길 순서

1. b1의 시작 import를 고친 고정판을 사용한다. HANDOFF에 기재된 b2는 이번 검토에서는 검증 완료로 간주하지 않는다.
2. 긴 P1 감독기를 띄우기 전에 §2.2~2.4의 예외·저장본·STOP/마감·USD/장치 연결을 보완한다. 발 invalid term은 같은 step의 질의를 보게 고친다. 수정자는 지적된 CPU 반례와 실제 진입 경로만 확인하면 되며 전체 심사를 다시 받을 필요는 없다.
3. 기존 계획의 첫 갱신 메모리·gradient·저장 관찰을 같은 기동 안에서 수행하고 공통 예산으로 두 arm을 진행한다. 독립 평가기와 P2는 병행 개발한다.
4. 최종 상태는 학습 완료/평가 대기/마감 중단/실패를 구분하고 최신 검증 checkpoint의 경로·SHA·누적 update·두 optimizer 재개 여부를 남긴다. 평가가 없으면 구조 우열이나 지도 효과 결론은 아직 미확인이다.

이번에 발견한 결함은 새로운 승인 절차를 세울 이유가 아니다. **이미 정한 학습이 시작에서 실패하거나 끝에서 증거와 재개 경로를 잃지 않도록 구현을 바로잡을 사항**이다.
