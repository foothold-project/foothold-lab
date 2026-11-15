> 분류: A/정책학습 · 이식 등가 시험 설계
> 작성: 오흥재 (ASTRA 검토) · 2026-10-18
> 근거: ame2_minimal @8beb9a688d67882828019583f7d5a78e3517f233 직접 열람 · 이번 대화의 2단계 방향 · mai-code 설계 문서
> 요지: 같은 차원·가중치·입력에서 출력뿐 아니라 gradient와 optimizer 갱신을 대조하고, Go2 물리 계약은 별도로 측정한다.
> 상태: 시험 계획 제안 · 코드 열람 확인됨 · 아래 시험 미실행 · 오차 기준 미보정 · GPU/Isaac 미실행

# ASTRA 19a · AME-2 Go2 이식의 등가 시험과 mai-code 단위

**판정: 공식 알고리즘의 수치 등가성과 Go2 신체·센서 계약을 분리해 구현할 수 있으며, teacher에 필요한 시험부터 끝내고 LSIO·mapper는 해당 단계에서 검증하는 구성을 권고한다.**

## 1. 이번에 보존할 것과 등가의 의미

MARG와 E1 이어학습은 이번 기준이 아니다. Go2를 처음부터 학습하고 목표 위치 명령을 사용한다. 순서는 정답 지도 teacher, LSIO student, Linux 이후 mapper이며 Nav2 연결은 이후다. START는 별도 학습 체계로 두고, AME-2의 증류나 PPO 계약을 이름만 바꿔 공유하지 않는다. 석헌 님 Go2 자료는 이번 검토에서 읽지 않았다. Fable의 확정 명세와 이식 코드는 아직 이 보고서의 검증 대상이 아니다.

**G1의 23차원 행동과 Go2의 12차원 행동이 같아야 한다는 요구는 성립하지 않는다.** 같은 입력이라는 말에는 입력 차원, 관절 순서, 가중치, 활성화, 정규화 상태, 난수, loss 계수와 optimizer 상태까지 포함해야 한다. 아래 두 프로파일 각각에서 공식 클래스와 이식 클래스를 비교한다.

| 프로파일 | 시험의 의미 |
|---|---|
| G1 기준 | 고정한 공식 설정의 입력과 출력 차원으로 원본 동작을 보존했는지 확인한다. |
| Go2 차원 | 공식의 로봇 무관 클래스에도 Go2와 같은 차원·설정을 주고 동일한 시험 가중치를 복사한다. 이식본과 함수·gradient·갱신을 비교한다. G1 정책을 Go2로 전이하는 시험이 아니다. |
| 경계 입력 | 작은 배치, 비정사각 지도, 비대칭 지형, 종료·시간 초과, 역사 reset, PPO 전환 직전·직후를 넣는다. 정상 입력 하나만 맞는 구현을 걸러낸다. |

공식 관측 구성을 그대로 옮길 경우 Go2 teacher의 몸 상태+명령은 `9+3×12+4=49`, student 역사는 `6+3×12=42`개씩 20 step이고 명령 4개는 별도다. 대응하는 G1 차원은 82, 75다. 이는 코드 정의로 계산한 값이며 실제 Go2 manager가 내는 텐서와 이름별로 다시 대조해야 한다. critic은 접촉 body 수와 height scan이 더해지므로 actor 차원을 복사하면 안 된다. 근거: Env:184–220,242–310.

지도 크기를 과거 E1의 17×11로 자동 확정하지 않는다. 공식 설정과 새 Go2 명세를 각각 기록한다. 17×11은 축 전치를 찾는 시험 입력으로도 쓸 수 있지만, 그것만으로 새 학습 설정이 정해지는 것은 아니다.

## 2. 기준 소스와 시험 구성

이 문서의 행 번호는 아래 깨끗한 체크아웃의 위 커밋 기준이다. 다른 버전에 그대로 인용하지 않는다.

`R = C:/Users/AI-WS01/s2_lab/_research_repos/ame2_minimal/`

| 약칭 | R 아래 파일 |
|---|---|
| Model | `rsl_rl/rsl_rl/models/AME2_models.py` |
| PPO | `rsl_rl/rsl_rl/algorithms/ppo.py` |
| IL | `rsl_rl/rsl_rl/algorithms/ppo_il.py` |
| Storage | `rsl_rl/rsl_rl/storage/rollout_storage.py` |
| Runner | `rsl_rl/rsl_rl/runners/on_policy_runner.py` |
| Obs / Sym / Curriculum | `ame2/ame2/tasks/mdp/observations.py` / `symmetry.py` / `curriculums.py` |
| Env / Agent | `ame2/ame2/tasks/ame2_env_cfg.py` / `agents/rsl_rl_ppo_cfg.py` |

시험은 세 종류의 증거를 합친다.

1. **차등 시험:** 원본과 이식본의 동일 계산을 비교한다. 원본 경로를 독립 namespace 또는 별도 CPU 프로세스로 불러오고 실제 `__file__`과 해시를 기록한다. 둘 다 같은 이식 모듈을 import하면 시험이 무효다.
2. **독립 정답 시험:** 작은 Gaussian, GAE, reward, 좌표 변환 등을 손으로 계산한 정답과 비교한다. 원본에 있는 결함까지 복사하면 통과하는 문제를 막는다.
3. **Go2 계약 시험:** 관절·센서·기체의 실측 또는 시뮬레이션 측정으로 적합성을 확인한다. G1과 같은 보행 궤적이나 성공률을 요구하지 않는다.

CPU 시험에는 Kit를 올리지 않는다. TensorDict, 실제 신경망·loss·storage를 사용하고 환경의 물리 데이터만 작은 고정 자료로 공급한다. import 때문에 필요한 경계만 대체하며, 검증할 loss나 관측 함수를 가짜 함수로 바꾸면 안 된다. 원본 실행에 필요한 import 경계 변경도 diff와 해시를 남긴다.

Python·PyTorch·NumPy·TensorDict 버전, CPU thread 수, dtype, 학습/eval 모드, 난수 상태를 고정한다. 같은 seed만 주는 것으로 부족하다. 각 실행 전에 Python·NumPy·torch RNG 상태를 복원하고, Gaussian 계산 단위 시험에는 같은 epsilon을 직접 공급한다. 실제 경로에서는 난수 소비 횟수와 실행 뒤 상태도 비교한다. PyTorch도 버전·장치 간 완전한 재현을 보장하지 않는다. [공식 재현성 문서](https://docs.pytorch.org/docs/2.14/notes/randomness.html)

### 제안 허용 오차

아래는 논문 수치가 아니라 **CPU 같은 환경에서 시작할 시험 기준**이다. 아직 원본 A/A 반복 실측으로 보정하지 않았다. 실제 결과를 보기 전에 기준을 파일에 기록한다. 실패를 통과시키려고 오차만 늘리지 말고 최초로 갈라지는 연산을 찾는다.

| 대상 | 절대 오차 atol | 상대 오차 rtol | 추가 조건 |
|---|---:|---:|---|
| shape·dtype·키/관절 순서·mask·배치 인덱스·분기·step 수 | 0 | 0 | 완전 일치 |
| float64 작은 해석 정답, forward·loss | 1e-10 | 1e-8 | 비매끄러운 경계는 별도 사례 |
| float64 gradient 대조 | 1e-9 | 1e-7 | 선택 모듈은 finite difference도 병행 |
| float32 forward·각 loss·KL | 1e-6 | 1e-5 | 중간 텐서도 비교 |
| float32 gradient·단일 Adam 갱신 | 1e-6 | 1e-4 | None/0 차이, 모멘트·step도 확인 |
| 동일 CPU의 고정 rollout 3회 갱신·저장 후 재개 | 1e-5 | 1e-4 | 각 회차 비교, 분기·카운터는 정확 일치 |

판정식은 원소별 `abs(actual-reference) <= atol + rtol*abs(reference)`다. NaN/Inf는 먼저 검사하고 두 쪽이 같이 NaN이어도 통과시키지 않는다. maximum absolute error, 가장 큰 오차의 이름·인덱스, 기준 대비 오차를 출력한다. 수치 비교 방식의 근거는 [torch.testing.assert_close](https://docs.pytorch.org/docs/2.14/testing.html#torch.testing.assert_close)이며, 위 수치는 그 문서의 기본값을 그대로 가져온 것이 아니다.

가중치 자체만 비교하면 작은 갱신 누락이 묻힌다. `Δθ`, gradient norm, Adam의 1·2차 모멘트와 step을 함께 본다. optimizer에서 빠진 파라미터를 찾도록 의도적으로 gradient가 발생하는 자료를 사용한다. 초기 0·작은 gradient를 무조건 불합격시키지는 않으며, 해당 경로의 수학적 기대와 대조한다. AMP, GPU fused 연산, Windows→Linux 동등성은 이 CPU 통과로 인증되지 않는다.

## 3. CPU 등가 시험 목록

표의 번호는 시험 ID다. 각각 정상 사례와 의도한 결함 사례를 함께 가진다. 변이는 별도 시험 사본에만 적용하고 정상 소스가 같은 시험을 먼저 통과해야 한다. 예외가 났다는 사실만으로 변이 검출로 세지 않는다. 기대한 assertion 위치와 이유가 맞아야 한다.

| ID · 대상 | 답을 아는 입력과 확인할 것 | 반드시 잡을 반례 · 근거 |
|---|---|---|
| E01 · 구성·초기화 | 두 프로파일에 동일 명시 가중치. 이름·shape·활성화·head·parameter 수와 optimizer 등록을 대조. 같은 seed의 초기화도 별도 대조 | 폭 축소, ELU 변경, 누락 모듈, 두 원본 경로가 같은 파일인 경우. Model:51–85,278–329,1046–1114 |
| E02 · 지도 전처리 | 평면·x/y 경사·한 칸 턱·구멍·전부 miss. 좌표마다 고유 값을 넣은 비정사각 지도. noise를 고정해 invalid 대체→clip→noise 순서를 대조 | x/y 전치, sensor 높이 부호 오류, 전부 miss가 유효 지면으로 오인됨. Obs:120–196. 유한 출력만으로 정답 지도라고 하지 않음 |
| E03 · 지도 encoder | point FC16, CNN8→48, local96, global64를 각각 비교. 가장자리 padding, max가 서로 다른 칸에 있는 입력, 동률 입력 분리 | flatten 순서·padding·max 축 변경. Model:51–66,145–167. 동률에서는 원본의 선택 index와 gradient 규칙도 기록 |
| E04 · query·attention·actor | 몸 상태 embedding128, query96, 32 heads, attention96, 결합288, 행동 출력을 순서대로 비교. 지도와 몸 상태를 각각 교란 | query 입력 detach/연결 오류, head 수 축소, global 또는 몸 상태 누락. Model:67–85,145–182. 입력 detach와 encoder 파라미터 gradient는 구분 |
| E05 · 분포 | 알려진 mean/std와 action으로 log probability·entropy·old||new KL·동일 epsilon sample 계산. action 축 합산 확인 | mean/sum 혼동, KL 방향 반전, std와 log_std 혼동. Model:193–239. deterministic forward 뒤 과거 distribution을 읽는 오류도 검사 |
| E06 · MoE critic | 16개 expert를 상수로 만들어 uniform gate의 산술 평균, 알려진 비균등 가중합을 검증. 실제 MLP도 수치 대조. K=1과 K>1 | top-1 전환, router detach, head 순서 변경. Model:1046–1114. 모든 expert·gate의 gradient를 확인 |
| E07 · storage·sampling | 작은 env×time 배열에 식별자 부여. flatten, old logprob/value 복사, mini-batch 순서, epoch 재사용, clear 확인 | 참조 공유로 old 값 변함, env/time 뒤집힘, remainder 은폐. Storage:231–266은 한 번 만든 permutation을 epoch마다 재사용하고 나머지를 제외하므로 그 동작을 명시 |
| E08 · GAE·timeout | 2 env×3 step의 reward/value로 terminal, timeout, 끝 bootstrap, K개 보상 성분을 손계산. advantage 정규화의 std 정의와 epsilon 확인 | terminal과 timeout 혼동, head 평균/합 혼동, 다음 episode value 누수. PPO:165–185,200–270. singleton 정규화의 비유한 결과도 보고 |
| E09 · PPO 각 항 | 양/음 advantage, ratio가 clip 안/밖, value clip 안/밖, entropy, loss cap 안/밖을 각각 계산 | clip 부호, reduction 변경, value cap을 일반 clamp로 바꿔 gradient 소멸. PPO:412–432의 detached 분모까지 보존 |
| E10 · KL·대칭·gradient clip | KL이 기준의 0.5·2배 전후인 사례, actor/critic norm이 다른 사례. critic-only augmentation 시 actor batch 불변 확인 | KL을 조기 종료로 바꾸기, actor·critic을 묶어 norm clip하기, actor까지 대칭 두 배. PPO:310–321,384–410,499–501 |
| E11 · 한 번/세 번 갱신 | 같은 고정 rollout, optimizer 상태, sampler로 loss→gradient→clip→Adam→entropy decay 전부 대조. 실제 factory도 호출 | critic K fallback, 누락 parameter, optimizer 중복 step, entropy decay 시점 차이. PPO:538–541,640–671; Runner:40 |
| E12 · LSIO 시간 축 | 20 step에 시간·관절별 식별자. 전체 역사 Conv1d, 최근 3 step, 명령4, embedding128 비교. 일부 env만 reset | 시간 역순, 최근 window 한 칸 밀림, episode 이전 값 누수, 현재 action을 previous action으로 사용. Model:264–329; Env:269–310 |
| E13 · LSIO 지도·특권 누수 | 같은 history/cmd/map의 forward·gradient. teacher 전용 선속도·정답 자료만 바꿔 student 출력 불변 확인. 지도·history를 바꾸면 해당 경로 반응 | teacher 관측이 student 입력으로 섞임, 학생 encoder가 no_grad 안에 있음. Model:241–387. GT 지도 공급 중인 단계는 지도 특권 제거 완료로 부르지 않음 |
| E14 · 증류 항 | frozen teacher의 행동·local96·global64. 행동 NLL과 두 표현 MSE를 독립 계산해 계수별 gradient 확인 | 행동 MSE로 대체, latent 순서 반전, teacher 업데이트, detach된 student. IL:127–145,267–288 |
| E15 · 학습 단계 | switch-1, switch, switch+1에 counter·lr·RL/증류/value/entropy 항을 확인. switch를 시험용 작은 수로도 설정 | 전환 한 번 밀림, 전환 전 PPO가 켜짐, 전환 후 teacher loss 삭제. IL:64–75,149–208. teacher PPO와 student PPO의 logratio clamp 차이도 보존 |
| E16 · export·재로딩 | teacher의 실제 stochastic act 이후 export, CPU reload, 세 출력 대조. LSIO는 history+cmd+map 입력으로 별도 export 대조 | 학습 전 빈 distribution에서만 export 통과, LSIO가 teacher wrapper를 상속해 history 소실. Model:221–227,1197–1252 |
| E17 · 저장·재개 | 같은 고정 rollout에서 연속 3회와 1회 저장+새 객체 2회 비교. optimizer, schedule, RNG, normalizer, stage counter 확인 | 모델만 복구, 증류 switch 초기화, entropy/lr 재설정, iteration 중복. PPO:573–607; Runner:77,121,146–171; IL:58,64–75 |
| E18 · microbatch를 쓸 경우 | 비균등한 마지막 chunk까지 weighted reduction, KL 집계, gradient norm, optimizer step을 unchunked와 대조 | chunk마다 mean을 단순 합산, chunk별 clip/step, 배치 통계의 비선형 손실을 분할 평균. 사용하지 않으면 해당 사유로 미적용, 전체 실패가 아님 |

모든 경우를 큰 학습 배치로 돌릴 필요는 없다. batch 1·2·7, 작은 rollout, 정사각/비정사각 지도, 세 개의 고정 seed와 경계 입력으로 먼저 충분히 구별한다. CPU 시간과 메모리는 미측정이다. 명세가 확정되면 실제 사용 클래스에 필요한 사례만 선택하되, 선택하지 않은 것과 이유를 결과에 남긴다.

### 원본을 그대로 정답으로 삼으면 놓치는 지점

아래는 이번에 직접 읽은 **정적 근거**다. 재현 시험 결과가 아니다. 각각 작은 CPU 반례로 확정하고, 공식 결함과 이식 결함을 따로 표시해야 한다.

- **teacher/student critic 구성 차이:** PPO factory는 active reward term 수에 따라 다중 value head를 만든다(PPO:640–671). 반면 PPO_IL factory는 critic 출력 1, 기본 storage를 만든다(IL:310–313). Runner:40은 해당 class의 factory를 부른다. “공식은 모두 단일 value”나 “student도 teacher와 같은 다중 value”라고 일괄 명세하면 틀린다. factory를 실제로 호출하는 E11이 필요하다.
- **teacher export 결함 후보:** Model:239에서 distribution은 torch Normal인데, 학습 뒤 wrapper 생성은 그 객체의 `as_deterministic_output_module()`을 호출한다(Model:1214–1217). 실제 호출 시 지원 여부를 E16에서 확인해야 한다. 빈 distribution인 초기 모델만 export하면 이 경로를 놓친다.
- **기본 LSIO export 경계:** LSIO는 별도 history/recent encoder를 가지지만 상속한 teacher wrapper는 그것들을 복사하지 않고 prop+map을 받는다(Model:241–387,1197–1252). 확정 명세가 기본 LSIO를 선택하면 전용 export가 필요하다. 다른 LSIO 변형을 고르면 그 클래스의 wrapper를 따로 확인한다.
- **정확한 이어학습 상태:** PPO.save/load에는 모델·optimizer만 있고 entropy 계수, IL update_cnt, RNG 상태 복구가 보이지 않는다(PPO:573–607). Runner는 iter/infos를 추가한다(Runner:146–171). IL의 loss_dict에 update_cnt를 출력하는 것(IL:251–263)은 checkpoint 저장이 아니다. E17에서는 원본의 재개 한계를 재현하고, 이식본은 연속 실행과 동등한 재개를 목표로 별도 수정 계약을 둔다.
- **attention 그림의 의미:** Model:177 부근의 혼합 시각화 값에는 attention과 global max 선택 정보가 합쳐진다. 이 값을 순수 attention 확률로 보고 합이 1인지 시험하거나 “다음 발 위치”의 증거로 해석하면 안 된다. 순수 MHA weights와 시각화 값은 분리해서 보관한다.

원본과 다른 수정이 필요하면 `원본 재현 → 결함 반례 → 수정 규칙 → 영향받은 시험`만 남긴다. 실행 경로에 필요한 결함부터 수정하며 전체 알고리즘을 재설계할 이유로 확대하지 않는다. 코드 충실성은 논문 전체 재현이나 Go2 성능의 증거가 아니다.

## 4. 로봇 의존 부분: 무엇을 실제로 재야 하는가

여기서 G1의 숫자를 무조건 복사하는 것은 충실한 이식이 아니다. 기하·질량·관절·접촉의 차이를 숨긴다. 아래는 CPU 계약 시험과 이후 기존 GPU 실행 안에서 수집할 측정 항목이다. 별도 참석·재승인 절차를 추가하자는 뜻이 아니다.

| 경계 | CPU에서 확인 | Go2에서 기록할 측정과 판정 방식 |
|---|---|---|
| 관절·행동·구동기 | 12개 joint name의 전단사, 순서·부호, default pose+scale×action, 제한·delay buffer. 한 축씩 unit pulse | 요청/실제 q·dq·torque, 포화율, limit 위반, PD 오차. 질량·inertia·gear·effort limit를 asset 원본과 대조. G1 action scale 0.25나 gains를 근거 없이 유지하지 않음. Env:169–175 |
| 좌표·명령 | 알려진 yaw 0/±90°와 평행이동으로 body/world 변환. actor의 거리 2m 제한 전후, heading sin/cos, critic의 원거리 정보 | goal world/body·거리·heading error·time-left를 함께 기록. 현재 API는 속도 명령이 아님. 향후 Nav2는 pose 목표의 좌표계·시간·취소/갱신 계약으로 연결. Obs:263–298 |
| 지도·센서 | 비정사각 좌표표, sensor offset, body yaw, 유효성, 높이 offset·clip·noise 순서 | 평면·경사·턱의 광선 위치와 실제 표면 높이 비교. 평면 내부 오차 1mm 이내를 초기 진단 목표로 제안하되 mesh/단위/PhysX 조건 확인 후 고정. 경계와 miss는 별도 mask로 계산. 센서와 root 높이를 혼동하지 않음. Obs:120–196 |
| 대칭 | joint/body 대응·부호표가 두 번 적용하면 원복. 관측·goal·action 동시 반사, 기준 자세 FK를 반사한 결과와 비교 | 좌우 unit action에서 실제 발 이동 방향 대조. 기존 함수는 23관절 하드코딩이므로 Go2 전용 adapter 필요. 신경망 자체가 학습 전 좌우 대칭이라는 assertion은 하지 않음. Sym:85–218 |
| 접촉·종료 | body mask·임계값 전후, 정상/추락/timeout·reset을 손계산. 접촉을 2발로 가정한 인덱스 탐지 | 4발별 force·접촉 mask, 몸통 충돌·넘어짐 사유, 정상 지지 pose의 오종료. critic contact 수를 실제 body 목록에서 계산. Env:205–220,573–614 |
| 시간·역사 | sim dt×decimation, policy·센서 update 주기, 20개 history의 시간표, 일부 env reset | 20-step buffer가 담는 실제 시간, 최신 샘플 시점, sensor age, action delay 분포. 공식 G1은 0.005×4=0.02s 정책 주기(Env:674–685). Go2에서 주기를 바꾸면 LSIO 시간 의미도 달라짐 |
| 보상·curriculum | 알려진 동일 상태에서 각 항을 독립 계산. weight·dt 적용, reward component 순서, progress·EMA·level 갱신 | 항별 reward/분산, 접촉 대상, goal 도달/실패 비율, terrain level 분포. 몸 높이·발 간격·관절/충돌 비용은 Go2 명세 값으로 판정. G1과 총 reward가 같다는 기준은 부적절. Env:409–654; Curriculum:322–331 |
| terrain·goal sampler | seed별 배치·경계·도달 가능 영역, 지정 난이도, goal이 공중/구멍에 놓이는 반례 | 실제 초기 발 지지·goal 지지면·불가능 목표 비율, 지형 종류별 도달/추락/정체. 처음부터 학습하므로 E1에서 쉬웠다는 이유만으로 초기 curriculum을 정하지 않음. Env:153–161,617–654 |

물리 성능 오차와 성공률 기준은 아직 미확인이다. 실측 없이 “G1 대비 ±5%면 등가” 같은 숫자를 만들지 않는다. 힘 단위·mass threshold·충돌 body의 정확성이 먼저이고, 이후 성능은 여러 seed와 동일 Go2 시험 조건에서 비교한다. 시작 상태의 지면 충돌이나 센서 좌표 오류를 학습으로 해결하려 하지 않는다.

mapper를 미루는 동안 LSIO에 공급하는 `neural_map`의 네 번째 채널 의미와 생성법은 명세에 고정해야 한다. 정답 높이에 임의의 불확실성 숫자를 붙여 실제 mapper 성능으로 보고하지 않는다. GT 지도 기반 student 단계는 역사·증류의 작동을 확인할 수 있지만, 지각 오차 내성이나 D435i 실기 배포를 입증하지 않는다. 기본 student의 채널 경계는 Model:264–285, 실제 map 공급 함수는 Obs:201부터 확인한다.

## 5. mai-code 작업 단위의 권고 경계

**파일별로 잘게 나누기보다 한 단위가 하나의 수치 계약을 끝까지 책임지도록 나눈다.** 공통 파일을 여러 작업자가 동시에 고치지 않는다. 아래 산출명은 제안이고 실제 경로는 확정 명세의 작업 폴더에 매핑한다. 이번에 새 코드나 unit 파일을 만들지는 않았다.

| 단위 | 소유 범위·입출력 계약 | 연결·완료 증거 |
|---|---|---|
| U0 · 기준과 독립 정답 | 공식 소스/설정 해시, class 선택, tensor schema, 정상 fixture·해석 정답·tolerance. 구현 코드의 expected 출력을 복사하지 않음 | 모든 단위 입력. 원본 A/A와 정상 fixture 검증. 구현자가 expected나 허용 오차를 바꾸지 못하게 출력 범위 분리 |
| U1 · teacher networks | map encoder·prop/query·MHA·actor distribution·MoE critic. TensorDict→행동/분포/latent/value | E01, E03–E06. Go2/G1 동일 shape 프로파일 각각의 forward와 backward |
| U2 · PPO와 storage | rollout 입력→GAE·batch·PPO update·optimizer/schedule 상태. storage와 sampler를 함께 소유 | U1 후 E07–E11. reward head 수와 순서까지 계약. U4와 checkpoint 필드 합의 |
| U3 · Go2 MDP adapter | 관절·관측·대칭·행동·센서·reward·goal·curriculum. 물리 상태→정의된 관측과 reward | U0로 시작 가능. E02와 4절 CPU 계약. 실제 Kit 자료는 해당 실행에서 별도 기록 |
| U4 · teacher 실행·저장·export | U1/U2/U3 조립, factory 선택, 재개 상태, teacher JIT의 세 출력, 실행 영수증 | E11 실제 구성, E16 teacher, E17. 알고리즘 자체를 여기서 다시 구현하지 않음 |
| U5 · LSIO networks·history | history/cmd/map→학생 행동·latent. reset·시간 축·전용 export | U0/U1 계약 재사용, E12–E13 및 E16 student. 지도는 공급원과 독립된 schema로 받음 |
| U6 · 증류와 student 실행 | frozen teacher 출력+student rollout→IL/PPO update·단계 상태. student factory와 checkpoint 확장 | U4 teacher artifact·U5 뒤 E14–E17. U2 PPO 변경이 필요하면 U2 소유자에게 한 수정 묶음으로 귀속 |
| U7 · mapper, Linux 이후 | 센서 입력→정의된 neural_map. map timestamp·frame·valid/uncertainty 의미 | 지금은 schema만 합의. Linux 이후 별도 원본 대조·센서 실측. U1–U4 teacher 준비를 기다리게 하지 않음 |
| U8 · 평가와 자료 집계 | 고정 Go2 조건의 목표 도달·추락·시간·지형별 결과 및 소스/설정 출처 | 정책 구현과 독립. 학습 로그의 reward 상승을 성공률로 대체하지 않음 |

U0의 입력 계약을 먼저 작게 고정하고 U1/U2와 U3를 겹쳐 진행할 수 있다. teacher는 U1–U4와 관련 시험이 준비되면 진행한다. LSIO 시험 미완료를 teacher의 대기 이유로 만들지 않는다. 반대로 teacher 시험 통과를 LSIO·mapper의 통과로 확장하지 않는다. 작업자 수와 GPU 배정은 lead의 실행 계획 영역이다.

START는 별도 U0/U1/U2에 해당하는 논문 추출·모델·동시 학습 단위로 구성한다. 공통으로 쓸 것은 Go2 asset의 출처, 좌표/관절 schema, 평가 자료 형식 정도다. 같은 로봇이어도 보상·관측·역사·학습 단계가 같다고 강제하지 않는다. D435i adapter와 이후 HiPAN의 interface도 각각의 명세에 귀속한다.

mai-code 단위에는 다음을 남긴다. 근거는 `C:/Users/AI-WS01/Desktop/jay/Claude/docs/superpowers/specs/2026-10-18-mai-code-design.md:74–85`다. 실제 실행기 지원 여부는 이번에 실행해 확인하지 않았다.

- issue #555 연결, 작업 ID, 전용 worktree, 입력 소스·명세·fixture의 경로와 SHA, 허용 출력 경로.
- 입력/출력 shape와 단위, 변경 가능한 기체 설정, 보존할 연산, 명세에 없는 항목의 처리. 원문과 코드가 다른 항목은 별도 차이표.
- Analyze→Plan→Implement→Verify가 읽는 동일 고정 자료와 미리 정한 시험 argv 배열. 검증기는 작업자의 “PASS” 문장 대신 실제 구현과 원자료를 읽는다.
- 예정·실행·PASS·FAIL·SKIP·미적용 개수, 각 skip 이유, 환경, exit code, assertion 위치, 최대 오차, 원본/이식 해시, 정상 시험과 변이 결과. 0개 실행을 PASS로 쓰지 않는다.
- 명세나 입력 해시가 바뀌면 영향받는 단위의 증거만 다시 만든다. 무관한 단위 전체를 반복 검증하거나 새로운 사람 승인 대기를 추가하지 않는다.

## 6. 명세가 오면 바로 대조할 항목

Fable 명세에서 먼저 확인할 것은 실제 actor/critic/algorithm class, teacher·student 관측 키와 역사, 지도 크기·채널, 보상 head 구성, 증류 계수·전환 시점, Go2 신체별 상수, mapper 전 임시 지도 공급 계약이다. 그 값이 확정되면 U0와 시험 profile을 연결하고, 논문·공식 코드·Go2 변경을 세 열로 분리한다.

이번 결론은 **시험 설계가 가능하다는 판단**이다. 공식 코드와 Go2 이식의 등가 PASS, 실제 Go2 안정 보행, CPU 시험 소요 시간, GPU 처리량은 아직 미확인이다. 지금 필요한 후속 작업은 별도 승인 문서를 늘리는 것이 아니라, 이 기준으로 구현과 독립 시험이 서로 다른 결함을 잡도록 작업 경계를 정하는 것이다.
