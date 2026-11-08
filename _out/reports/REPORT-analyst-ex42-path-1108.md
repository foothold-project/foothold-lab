> 분류: 독립 코드 점검
> 작성: analyst · 2026-11-08
> 근거: 고정본 7916a52fa07c6774eb59db2b69f4b7a5068cea63 · isaac311 설치 소스 · 실제 EX-41 m6000 저장본 · CPU 반례
> 요지: I46 외 신규 실행 막음 3건 · 부모 조건 불일치 2건 · model_50 완료 회차 기록 오류
> 상태: 읽기 전용 점검 완료 · 수정 및 Kit 첫 update/50회 실행은 하지 않음

# EX-42 0 단계 첫 갱신과 model_50 경로 점검

**고정본 기준 막음 5건: 첫 갱신 전 실행 오류 3건과 부모 조건 불일치 2건이다.** 이미 알려진 I46은 별도로 적었다. runner가 알려 온 수정 완료 주장은 후속 고정 HEAD를 받기 전에는 닫힘으로 세지 않았다. 이 문서는 고정본의 목록이며 runner 작업 사본을 고치지 않았다.

점검 뿌리 `R = D:/mai-wt/foothold-lab/runner-ex42-w65-7916a52`. 아래 소스 경로는 R 기준이다. R의 `?? outputs/2026-11-08/`는 다른 작업자의 산출물이므로 건드리지 않았다. 자기 분석 사본에만 이 문서와 CPU 근거를 썼다. R14·R15는 원자료 직접 읽기로, R20은 실제 부모 파일과 설치 API 대조로 막았다. M76에 따라 코드로 예상되는 새 실행 조건과 이미 실행된 부모의 실측을 구별했다.

## 1. 실행 순서대로 발견한 것

| 번호 · 영향 | 고정본에서 확인한 경로 | 근거와 재현 | 필요한 닫힘 증거 |
|---|---|---|---|
| I46 · 기존 막음 | `scripts/ex42_training_entry.py:173`에서 unwrapped를 구하고도 178에서 `env.num_envs`를 읽음. 이때는 Gym OrderEnforcing이고 Rsl wrapper는 아직 아님 | 실제 stderr의 AttributeError. `scripts/train_start.py:841` 호출 뒤 862에서야 Rsl wrapper를 만듦 | raw의 num_envs·device를 쓰는 후속 HEAD 및 실제 Gym wrapper 반례 |
| H1 · 신규 실행 막음 | EX-42는 13개 명령 슬롯을 뽑지만 기존 5개 슬롯 카운터를 늘리지 않고 첫 reset. `scripts/train_start.py:834`~842 | `commands/mixed_command.py:73`~75, 209~235. 실제 T0′ 설정·seed 42·3072개 CPU 추출에서 슬롯 0~12가 나옴. 길이 5 += 길이 13은 RuntimeError. EX-41은 `scripts/ex41_startup.py:68`~91의 `configure_ex41_command_slots`를 `train_start.py:977`~982에서 먼저 호출 | 같은 실제 명령 객체에 13개 이름·카운터를 먼저 적용하고 reset 이후 집계가 3072인지 |
| H2 · 신규 실행 막음 | `attach_runtime` 반환 W86Runtime 객체를 `w86` 영수증 칸에 넣고 json.dumps. `scripts/train_start.py:832`~859 | `rewards/w86_runtime.py:363`~373은 dict가 아닌 adapter를 반환. 실제 W86Runtime 타입을 json.dumps하면 TypeError. 물리 생성은 생략한 타입 직렬화 반례 | adapter와 JSON-safe 등록 영수증을 분리하고 첫 reset 영수증 전체를 실제 serialize |
| H3 · 신규 실행 막음 | EX42StageZeroRuntime에 `record_pre_step`·`record_post_step` 메서드가 없음 | 실제 클래스 인스턴스에서 두 속성 조회 모두 AttributeError. `runners/start_runner.py:635`~647은 continuous가 있으면 무조건 호출. 첫 env.step 직전에 먼저 실패. EX-41의 기반 `curriculum/continuous.py:415`, 467에는 두 메서드가 있음 | 필요한 기록을 구현하거나 해당 런타임의 명시적 계약에 맞게 연결. 첫 update에서 pre/step/post 호출 순서까지 시험 |
| H4 · 부모 조건 불일치 | 부모에서 꺼 둔 lin_vel_z 벌점이 새 cfg에서는 −2로 남는 경로 | `rewards/core.py:13`, `start_rewards.py:118` 기본 −2. `scripts/ex41_startup.py:1116`~1122는 다른 네 가중·EX39·서기만 적용. EX-41 `curriculum/ex41.py:378`~393은 runtime에서 lin_vel_z=0으로 바꾸지만 EX-42는 그 runtime을 쓰지 않음. **코드상 예상**이며 새 Kit의 실제 RewardManager 값은 아직 미측정 | 첫 reset 뒤 실제 reward manager의 lin_vel_z=0 및 기존 유지 항 전체 가중 대조. 부모 T0′와 다르게 할 결정은 찾지 못함 |
| H5 · 부모 조건 불일치 | EX-42가 RuntimeReadback을 만들지만 runner와 EX41DRReadback에 붙이지 않음. `_ex41_push_vmax_mps`도 설정하지 않아 legacy 밀기 분기로 감 | `train_start.py:825`~830 및 976(EX41 분기만 attach), `ex41.py:740`~758, `ex40_dr_runtime.py:223`~238. 부모 실제 m6000 기록은 방사형 크기 U[0,2.0] m/s. 새 경로는 YAML 68~74의 x,y 각각 U[−1,1] m/s. 크기 상한 √2와 분포가 다름 | 부모의 방사형 밀기 및 상수 DR=1 소비·기록이 함께 유지되는지 확인. 옛 RuntimeReadback만 그대로 붙이면 EX40 회차 램프를 다시 탈 수 있으므로 단순 연결만으로 완료 처리하지 않음 |

H1 CPU 추출 카운트: `[702,199,200,272,259,321,437,205,205,65,54,75,78]`, 합 3072. H1~H3은 실제 런타임 전체를 돌렸다는 뜻이 아니라 각각의 실패 연산·메서드 계약을 CPU로 재현한 것이다.

H5에서 설치 Isaac의 `push_by_setting_velocity`는 이름·설명만 보면 대입처럼 보이지만, 실제 `C:/isaac/isaaclab/source/isaaclab/isaaclab/envs/mdp/events.py:1065`~1071은 기존 속도에 표본을 **더한다**. 따라서 이번 차이는 더하기 대 대입이 아니라 표본 분포·최댓값·기록 연결이다. 부모 `train_extra.jsonl:6000`의 실제 방사형 크기 최댓값은 1.9838616848 m/s, 해당 갱신 표본은 60개다.

## 2. 첫 50회 저장에서의 기록·이어받기 빈칸

| 항목 | 확인 결과 | 범위·영향 |
|---|---|---|
| model_50 완료 회차 | `start_runner.py:964`~970의 원래 함수에 it=50을 넣으면 completed_updates=51, 경험 수 3,760,128로 기록. 실제 50×24×3072는 3,686,400 | **CPU 재현**. EX42 runtime은 1부터 세지만 generic manifest는 0부터 세는 식. EX41 보정 hook(`scripts/ex41_resume.py:564`~570)은 `train_start.py:1158`의 EX41 분기만 설치. 체크포인트 내용 iter=50과 원장51이 갈림 |
| 모델·optimizer·RNG 저장 키 | `start_runner.py:1181`~1225에 policy, critic, 두 optimizer, adaptive lr, perception, AdaSmpl, map-switch, RNG, env_state, curriculum 저장 경로 있음 | **코드 확인**. 실제 model_50 파일의 완성·해시·재로드는 이번 읽기 전용 범위에서 미실행 |
| EX42 curriculum 저장 | `scripts/ex42_training_entry.py:224`~250에 iteration, 부모·계획 SHA, 상수 DR, 지형 정책, 명령·지도 집계가 있음 | 이전 EX41 fixed clock을 가져오지 않는 새 구간. 부모의 물리 상태·기존 curriculum을 복원하지 않는 것은 `load_ex42_stage_zero_parent:1493`~1545에 명시됨 |
| 다시 시작 경로 | EX42 전용 CLI는 `scripts/ex42_training_entry.py:39`~40에서 resume_from을 거절 | 저장 키가 있다고 같은 CLI로 model_50부터 이어 갈 수 있는 것은 아님. 향후 이어받기 계약 미연결. 첫 50회 실행 오류와는 구별 |
| 실제 가중·지도 비율 | EX42 effective에는 reward_weights가 없어 저장본 `ex41_w86_reward_weights`가 None. `_last_use_gt_frac` 갱신도 EX41 조건문 안(`start_runner.py:725`~728)이라 부모 값이 남음 | 학습 자체의 AdaSmpl 갱신은 별도 실행됨(747,751~752). 기록의 최신성 문제이며 지도 선택이 고정됐다는 뜻은 아님 |
| 초기 설정 snapshot | `ex42_chain.py:101`~110은 iteration=0에서만 snapshot, 실제 EX42 호출은 1부터 | 초기 snapshot이 생기지 않는 경로. 첫 저장본까지 설정 실제 소비 증거가 빠짐 |
| 50회 평가 호출 | `ex42_chain`의 P1 간격은 250회 | model_50에서 새 평가를 안 거는 것은 이 간격과 맞음. 250회 이후 실제 평가 사슬은 이번 범위 밖 |

## 3. 실제 객체·부모와 맞는 부분

| 점검 | 직접 확인한 근거 | 판단 |
|---|---|---|
| Python·PPO API | `isaac311/python.exe`, rsl-rl-lib 3.1.2, 실제 설치 `Lib/site-packages/rsl_rl/algorithms/ppo.py`의 signature와 init_storage를 import하여 읽음 | 현재 runner의 policy 생성 후 `alg.init_storage` 호출(`start_runner.py:329`~346)과 맞음. isaac311-moects의 다른 PPO API를 근거로 쓰지 않음 |
| wrapper 이후 환경 속성 | 설치 `C:/isaac/isaaclab/source/isaaclab_rl/isaaclab_rl/rsl_rl/vecenv_wrapper.py:52`~66, 106~164 | num_envs, device, unwrapped, episode_length_buf, TensorDict 관측, 4개 step 반환값이 runner와 맞음. wrapper **이전** I46과 구별 |
| 텐서 장치 | `runners/devices.py:7`~18, `train_start.py:683`, `start_runner.py:637`~645 | env.sim과 agent 장치를 함께 지정하고 행동은 env.device, 결과는 runner.device로 옮김. GPU 실제 전송·메모리 사용은 미측정 |
| 부모 actor/critic | 실제 `model_6000.pt`를 CPU 로드: actor 첫 층 512×98, critic 첫 층 512×666, ex41_pose_commands=true, mirror=false | 98/666 확인. 예전 96/664를 가정할 필요 없음 |
| pose_cmd | `scripts/ex41_startup.py:1143`~1168 첫 관측 검사, `start_runner.py:266`~276·320~322 | N×2, 유한값, 두 칸 0 요구. actor는 45+51+2, critic은 52+512+100+2. 실제 Kit 첫 관측은 이번 검사에서 생성하지 않음 |
| optimizer·학습률 | 부모의 PPO lr 및 optimizer group lr 둘 다 0.00038443359375000017. `load_ex42_stage_zero_parent:1521`~1529에 두 optimizer와 adaptive lr 복원 | 저장된 상태와 로드 코드 대응 확인. 첫 PPO update 수치·optimizer tensor CUDA 장치 실증은 미실행 |
| 정규화·지도 | 부모 actor/critic/reward 정규화 모두 false, running buffer 없음. p_map_off=0.1. perception_cfg 전체를 새 train_cfg에 복사 | 정규화 통계를 빠뜨려 이번 부모가 달라진다는 근거는 없음. strict model/perception 로드와 map 확률 일치 검사는 있음 |
| RNG | 부모 rng의 Python·NumPy·torch·CUDA 키 및 저장 경로 확인. `start_runner.py:1172`~1179에서 torch RNG를 CPU로 바꾸어 복원 | 새 물리 환경에서 동일 궤적이라는 보장은 아님. 시뮬레이터 상태 전체 복원과 신경망 RNG 복원은 다름 |

실제 부모: `C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/model_6000.pt` · local 6000, 누적 12000 · SHA256 `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`.

## 4. 재현 자료와 보고 경계

- [CPU 점검 스크립트](ex42-path-1108/audit.py), [부모·슬롯·직렬화 원결과](ex42-path-1108/audit.json), [누락 메서드·manifest·부모 밀기 원결과](ex42-path-1108/supplement.json), [SHA256SUMS](ex42-path-1108/SHA256SUMS).
- `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`, `CUDA_VISIBLE_DEVICES=''`, TMP·TEMP는 `D:/mai-tmp/analyst`. isaac311로 실행. GPU·Kit·학습·프로세스·실행 원장은 변경하지 않음.
- I46 실제 stderr: `D:/mai-tmp/runner/w65_main/stderr_20261108_111922.log:3`~12.
- 부모 밀기 실측: 위 부모 폴더 `train_extra.jsonl:6000`. 기존 EX41 런타임과 설치 Isaac 함수까지 읽어 대조함.
- runner의 후속 수정 회신: `msg_0bfdcc093ef9`에 I46·H1·H2 수정 및 CPU 110 PASS라고 적혀 있다. 후속 HEAD와 그 시험을 이 보고서에서 재측정하지 않았으므로 위 고정본 결과를 소급해서 닫지 않았다.

**다음 확인 대상은 수정된 고정 HEAD 하나다.** 그 판에서 I46·H1~H3 재현이 사라지고 H4·H5 실제 소비값이 부모와 맞아야 한다. model_50의 회차·해시·저장 키도 함께 확인해야 첫 50회 경로가 검증됐다고 말할 수 있다. 이번 점검은 그 실행을 승인하거나 수행하지 않았다.
