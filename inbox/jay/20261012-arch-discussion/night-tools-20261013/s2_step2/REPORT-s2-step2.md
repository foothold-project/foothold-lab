> 분류: A/정책학습 · S2 지도 실험 2 단계 CPU 후보 보고
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-step2.md · README-s2-step1.md 3·8절 · DESIGN-s2-ab-v1.md 6절 · VERIFY-astra-17f2.md · PROBE-sparse-terrain.md · CPU run_20261015_024740_59720
> 요지: 학습 루프 후보와 기동 초안을 만들고 가짜 환경에서 시점·재개·고장 관문·동일 규칙을 검증했다. 실제 Isaac 접속과 학습 기동은 미확인이다
> 상태: 후보 · 팀장/ASTRA 결정 전 · GPU 기동 승인 아님

# S2 지도 실험 학습 연결 2 단계 보고

## 격리와 산출물

작업 위치는 `codexE/s2_step2/`다. `night-tools-20261013/s2/`의 1 단계 파일 6개를 `base_step1/`로 복사했고, 원본과 복사본 SHA256 불일치 0개를 다시 확인했다. `_eval`과 `C:/isaac/ext/go2_rl_robotlab/source`의 부모 코드는 읽기만 했고 쓰기 0건이다. 등록된 `_eval` 원본 11개 SHA256도 읽기 전용 검사에서 모두 일치했고, `_eval` 최상위의 `*s1043*` 파일은 0개다. 공유 저장소에도 이 작업 산출물을 복사하거나 커밋하지 않았다. 시험은 `CUDA_VISIBLE_DEVICES=-1`인 CPU 전용이며 GPU와 Isaac은 실행하지 않았다. 기존 프로세스를 종료하지 않았다.

최종 파일 16개 해시는 [S2-STEP2-SHA256SUMS.txt](S2-STEP2-SHA256SUMS.txt)에 있다. 목록 자체 SHA256은 `91737d563dab78778a51b72dcca42a20f6b7358fecf12b97cf20ee21aef8c5e9`이고, 목록 되읽기에서 16/16 일치했다. 부모 `moe_cts.py` SHA256은 `136a1c1082243ae1c6654307ffcf32de2a99cf6c4d6581419ada59f288a058f6`, `on_policy_runner_cts.py`는 `6800c7866edd03f7deb2bf38a00c6683922a96cbd1d7909ea55989a5eed844a9`로 시작·끝이 같다.

## 부모 코드 대응

| 부모 위치 | S2 후보 대응 | 의도한 차이 |
|---|---|---|
| `moe_cts.py:93~101`의 optimizer와 encoder optimizer | `base_step1/s2_policy.py`의 `make_optimizer`, `s2_ppo.py`의 단일 optimizer | 별도 encoder optimizer 제거. step1 `EncoderControl`의 두 군을 같은 부모 LR 변화 규칙에 묶음 |
| `moe_cts.py:124~129`의 teacher/student 분기 | `s2_runner.py`의 단일 A/B 수집 경로 | `teacher_env_ratio 0.75`와 teacher 손실 제거 |
| `moe_cts.py:132~202`의 행동·저장·return | `s2_runner.py`의 관측 시점 지도 복제, bootstrap, GAE와 유효성 검사 | 지도 187 height + 187 mask를 매 시점 저장하고 reset episode 혼합 거절 |
| `moe_cts.py:227~411`의 PPO·재구성 갱신 | `s2_ppo.py`의 PPO 갱신 | 재구성 손실과 두 번째 optimizer step 제거. `begin_update` → epoch × minibatch별 `enforce_groups`와 `trainable_params` clip → `end_update` |
| `moe_cts.py:278~311`의 adaptive LR | `s2_ppo.py:59~68`, 갱신 중 group 재적용 | 부모 KL 문턱과 배율을 따르며 두 군 LR을 동시 변경 |
| `on_policy_runner_cts.py:108~145`의 rollout·update | `s2_runner.py:104~211` | update 전에 `RunValidityGate`, 고정 계획과 실제 step 수 기록, 무효 rollout 폐기 |
| `on_policy_runner_cts.py:167~181,260~278`의 저장·재개 | `s2_runner.py:214~264` | 정책·control·optimizer·환경·torch CPU/CUDA·numpy·python RNG와 환경 해시 저장. 갱신 중 저장 거절, 다른 arm/규칙/설정 재개 거절 |

부모 actor/critic 구현도 읽기만 했다. 부모 학습 진입점을 S2용으로 수정하지 않았다.

## 항목별 구현과 CPU 확인

정상 로그는 [run_20261015_024740_59720](evidence_s2_step2/run_20261015_024740_59720/)의 `step2_known_answers.log`와 `step1_14.log`다. 반례 코드는 `s2_step2/test_s2_step2.py`, 신규 변이 코드와 개별 정상·변이 로그는 `s2_step2/test_s2_step2_mutants.py`와 `step2_code_mutants_v2/`에 있다. 아래의 CAUGHT는 정상 소스가 같은 시험에서 먼저 exit 0이고 변이의 첫 FAIL이 지정 want와 일치할 때만 센다.

| 번호·파일 | 정상 로그의 시험 이름 | 반례와 변이 want |
|---|---|---|
| 1 `s2_ppo.py` | `fixed step count and PPO-only loss`, `adaptive LR parent thresholds`, `A and B same update plan and control rule` | step 수·LR 문턱 반례. `adaptive_lr` 코드 변이의 첫 FAIL = want `adaptive LR parent thresholds`, CAUGHT |
| 2 `s2_runner.py` | `rollout map snapshot and bootstrap time`, `reset uses new episode map`, `all minibatches use saved map`, `sensor NaN holds both-arm gate`, `critic NaN holds before update`, `reward NaN gate blocks update`, `resume bit identical policy optimizer env and RNG`, `checkpoint during update refused` | 이전 episode 지도, NaN 지도·critic·reward, 다른 arm/encoder 규칙, 갱신 중 저장 반례. `map_snapshot`와 `validity_gate` 코드 변이의 첫 FAIL이 각각 같은 이름의 want와 일치, 2/2 CAUGHT |
| 3 `s2_env_adapter.py` | `ray index x-fast and no 20m re-add`, `yaw 90 ray geometry`, `ray order mismatch rejected`, `A terrain information blocked`, `B terrain information changes` | x-fast 순서 변경·20m 재가산·yaw 변형·A/B 지도 차단 반례. `training_map`은 `strict=True`로 호출한다. `ray_order` 첫 FAIL = want `ray order mismatch rejected`, CAUGHT |
| 4 `s2_terrain_overlay.py` | `terrain geometry from CPU probe and parent untouched`, `allocation distinct from encounter and outcome`, `outcome without approach rejected`, `runner logs assigned and encountered separately` | 부모 지형 불변, gap·stones 생성 수치, 접근 없는 통과 거절. `terrain_geometry` 첫 FAIL = want `terrain geometry from CPU probe and parent untouched`, CAUGHT |
| 5 `S2-SMOKE-PREREG-draft.md` | 초안 표를 되읽어 README 8.2의 실행 무결성·측정 일정·표현·행동·공동 규칙·전환과 재시작·평가 분리 7행, 결과 전 결정 별표와 책임자를 확인 | 문서 초안이라 코드 변이 대상이 아니다. 값 확정·실행 결과는 미확인 |
| 6 `night_s2_smoke_draft.sh`, `s2_launch_gate.py` | 초안 첫 줄 `STOP` 뒤 exit 99, `bash -n` exit 0. `approval draft gate known answer`, `approval plan mutation rejected`, `unapproved launch denied` | 승인·plan·환경·코드·마감 결박 반례. `approval_gate` 첫 FAIL = want `unapproved launch denied`, CAUGHT. 초안은 실행하지 않음 |

`RunValidityGate`는 매 rollout에서 지도·critic 입력·value·return·advantage의 유한성과 센서 고장을 갱신 전에 검사한다. 유효·무효 양쪽 arm 기록에 고장 횟수, 폐기 transition 수, 중단 이유와 지형 사건 수가 담긴다. 갱신 예외는 `held_update`로 기록하고 이전 체크포인트부터 재시작해야 한다. `WORLD_SIZE != 1`은 현재 후보에서 거절한다. CUDA RNG는 초기화된 경우 저장하도록 작성했으나 이 CPU 시험에서 CUDA 경로는 미측정이다.

희소 지형은 원본 설정을 deep copy한다. gap 길이 0.10~0.25m, platform 1.5m와 stones 폭 0.50~0.70m, 간격 0.10m, 높이 최대 0.06m, 구멍 깊이 −1m, platform 1.5m, 8×8 크기는 probe의 생성 후보값이다. 최종 지형 비율은 인자 필수이며 기본값이 없다. 사건 필드는 `assigned`, `approach`, `pass`, `avoid`, `fall`, `stall`이다. 배정과 실제 접근은 따로 센다.

## 묶음 시험과 변이 증거

새 run-id [summary.json](evidence_s2_step2/run_20261015_024740_59720/summary.json)에서 네 실행 모두 exit 0이다. 1 단계 정상 `14/14 PASS`와 통과 칸 292개, 1 단계 기존 변이 `ALL CAUGHT 69/69`, 2 단계 알려진 답 26개 PASS, 최초 2 단계 코드 변이 4/4를 기록했다. 69개는 **소스 코드 변이 68개 + 입력 해시 관문 변조 1개**이며 한 종류로 합산해 주장하지 않는다.

같은 run-id의 확장 [step2_code_mutants_v2/summary.json](evidence_s2_step2/run_20261015_024740_59720/step2_code_mutants_v2/summary.json)에서 신규 **코드 변이 6/6 CAUGHT**다. `adaptive_lr`, `ray_order`, `map_snapshot`, `validity_gate`, `terrain_geometry`, `approval_gate` 각각 정상 exit 0, 변이 exit 1, 첫 FAIL과 want 동일, `AssertionError` 확인이다. 최초 네 변이는 확장 여섯에 포함되므로 10개로 더하지 않는다. `bash -n`을 마지막 스크립트 수정 뒤 재확인해 exit 0이었다. 실제 기동 스크립트 실행은 0회다.

첫 파일 복사 시 PowerShell `-LiteralPath`와 `*` 조합으로 복사가 0건인 것을 확인했다. 파일 열거 방식으로 다시 복사한 뒤 여섯 파일 해시가 모두 맞았다. 이 예비 실패는 최종 시험 통과 수에 넣지 않았다.

## 초안 기동 연쇄와 남은 연결

| 초안 구간 | 기존 도구·검사와 연결 의도 | 현재 상태 |
|---|---|---|
| 승인 JSON과 `s2_launch_gate.py` | 승인 plan·환경·코드 해시·마감 결박 | CPU 구조 검사만 통과. 서명이나 팀장 신원 인증은 없음 |
| STOP·deadline·`_single_run_lease` | `night_20261013_cmdr1043_v3.sh`의 순차 실행과 중단 패턴 | shell 초안만. 공통 실행 lease 참여는 미확인 |
| `isaac_slot_v3.py` | 물리 GPU slot 대기·공유 변환 lock·registry·USD 디렉터리 | 인수 형태만 참조. S2 실행에서 미측정 |
| `gpu_guard.py` | VRAM 바닥·사용량 감시 | 미실행 |
| `usd_isolate_run_v3.py` | Kit/USD 격리 실행 | 미실행 |
| `S2_TRAIN_ENTRY` | S2 실제 Isaac 학습 진입점 | 아직 없음. `branch_run.py`는 1043 평가 전용이므로 S2 지원을 주장하지 않음 |

이 파일은 맨 앞의 무조건 `exit 99` 때문에 현재 실행 불능이다. 1043의 tool chain을 참조한 **검토용 초안**이며 실제 S2 학습 진입점, 종료 후 결과 인증, 승인 진위 확인과 공통 lease 결합을 만들고 ASTRA가 검토한 뒤 새 실행본이 필요하다. 따라서 이 단계가 곧바로 GPU smoke 준비 완료라는 뜻은 아니다.

## 실제 접속 전 확인과 미확인 범위

Isaac 접속 시험에서는 RayCaster 실제 `height_scanner.data.pos_w`와 `ray_hits_w`의 187칸 순서, yaw 프레임, 20m scanner offset 처리, 평지·단차·빈 공간의 collision mesh 높이, no-hit mask와 reset 직후 새 frame token을 대조해야 한다. 이어서 A/B의 부모 체크포인트·초기 공유 가중치·encoder latent/grad/Adam 상태, 같은 env seed·명령·지형·보상·critic, 매 update의 map 시점과 `epoch × minibatch` step 수, 공동 실패·중단 로그를 실제 경로에서 검증해야 한다. 저장·재개 때 실제 GPU RNG, USD 변환 lock·registry·slot·guard, 결과 artifact 해시와 별도 evaluator도 확인해야 한다.

현재 미확인은 실제 Isaac/RayCaster와 collision mesh, GPU·VRAM·시간당 iteration, 실제 학습 안정성과 성능, CUDA RNG 저장·복원, 공유 lease의 다른 작업과의 상호 배제, 스크립트 인수 호환성, smoke 이후 독립 평가다. CPU 가짜 환경의 비트 동일 재개를 실제 Isaac 결정성으로 확대하지 않는다.

## 결정 대기 값과 ASTRA 질문

첫 A/B의 `encoder_mode`, schedule을 택하면 W와 r, 환경 수·iteration 수·rollout 길이·epoch·minibatch·중단 기준, 평가 일정과 표본·seed, gap/stones 최종 배정 비율, 성공·회피·추락·정체 판정, 표현·행동 진단 경계는 팀장/ASTRA 결정 전이다. 코드에 최종값을 박지 않았고 prereg의 숫자도 제안이다. 특히 ASTRA의 encoder 권고를 확정값으로 옮기지 않았다.

lead가 ASTRA에 바로 보낼 질문 다섯 가지:

1. 실제 RayCaster의 yaw·187칸 순서·no-hit·20m offset과 collision mesh 확인에서 어떤 원자료와 불합격 조건을 요구하는가?
2. 첫 A/B에서 encoder_mode를 무엇으로 동결하고, schedule pilot이 필요하다면 W·r·시도 수·재시작 규약을 어떻게 사전 등록할 것인가?
3. A/B 공동 규칙과 실패 관문에서 필요한 부모 동치·gradient·optimizer·group LR·KL·latent 로그의 최소 집합은 무엇인가?
4. 짧은 smoke의 환경 수·update 수·중단 기준을 정하려면 어떤 GPU 메모리·시간당 iteration 실측이 먼저 필요한가?
5. gap/stones의 배정 대비 실제 접근·통과·회피·추락·정체와 최종 독립 평가를 어떤 표본·seed·명령·checkpoint 선택 규칙으로 묶을 것인가?

다음 단계는 실제 S2 진단 전용 접속과 승인 분리, 그 뒤 CPU/Isaac 연결 통합 시험이다. GPU 기동은 별도 결정 사항이다.
