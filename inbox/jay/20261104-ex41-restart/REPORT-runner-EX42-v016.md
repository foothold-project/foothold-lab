> 분류: C/운영
> 작성: 오흥재 · 2026-11-05
> 근거: EX-41 운영 원장 · 잠긴 EX-41 코드 · CURRICULUM-GATES v0.16 §E · D182 · EX42-V015-RUNNER-DIFF.md
> 요지: EX-41 1251 경계 동작을 원자료와 코드로 설명하고 EX-42 정본 계약 1단계를 CPU 시험으로 고정한다
> 상태: EX-41 분석 확인 · EX-42 계약·CPU 지형 계약 시험 통과 · P4 import/mesh 및 P2 environment/step probe 통과

# EX-41 경계 분석 및 EX-42 v0.16 계약 1단계

## 1. EX-41 1251 경계

운영 run `C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522`의 `ex41_application.jsonl`에서 m1001은 `schedule_continue`, DR 0.5000 → 0.5375였다. m1251은 `dr_hold_missing_evidence`, DR 0.5375 → 0.5750, `score_sha256` 없음이었다. 같은 run의 `stage_log.jsonl`은 m1251에서 `expected_score_iteration=1000`, `selected_score_iteration=null`, `state=missing_evidence`를 기록한다.

실행 코드 SHA는 원장에 기록된 `2b01df9a60ce41a51882dbd3fc78db8c8e05e8aa`다. 해당 잠긴 사본 `D:/mai-wt/foothold-lab/ex41-launch-2b01df9a`는 읽기만 했다. `foothold_s2/curriculum/ex41_fixed.py:178-213`에서 경계 clock은 먼저 직전 경계 이후의 elapsed를 반영하고, 그 뒤 증거 부재를 `paused`로 처리한다. 그래서 m1251에 적용된 0.5750은 m1001~1250 완료 구간의 시간 증가를 포함한 경계값이며, 누락된 m1000 점수 때문에 증가한 값은 아니다. 그 경계부터 이후 상승이 정지되는 의미의 hold다. 이 코드 의미에 따르면 현재 동작은 의도된 동작이며, 직전 m1001 값 0.5375로 소급 복원하는 것은 아니다.

`ex41_fixed.py:446-489`는 다음 update `n`의 증거를 `n - 1 - interval`로 선택한다. 따라서 m1501의 기대 점수는 m1250이다. m1000 점수가 늦게 도착해도 m1501에서 재사용하지 않는다. m1250이 유효한 첫 통과 점수면 회복 연속 횟수가 1/2가 되고, 다음 인접 경계에서 m1500이 통과해야 회복 조건을 채운다. m1250이 없거나 무효면 missing-evidence hold가 계속된다. `ex41_score_watch.py:1202-1236`도 측정 공백을 `result_eligible=false` 및 다음 checkpoint 진행으로 남긴다. 운영 프로세스와 파일은 변경하지 않았다.

## 2. EX-42 정본 대조

기준은 `origin/feature/fable-25a-jay`의 CURRICULUM-GATES v0.16 §E, 고정 정본 커밋 `69e5ac6bb5a5e16f8b5c419e8674237f3f597dd8`, runner diff의 23개 변경 항목, lead WORKLIST D182다. D182는 analyst 승인 D176-4/8/6/7, `consecutive_hold`를 노출 확대만 보류하고 학습 계속, 발 끌림 기준값의 가정 0.25와 반복 폭 2배 중 큰 값, 물리 표시 칸의 평가 기록 전용 처리, 확장 E 경사 35°와 계단 0.30 m, pallets 틈 0.35 m와 높이차 0.30 m를 한 축씩 올리는 규칙으로 정한다. 남은 팀장 결정은 다음 점프·높은 턱·넓은 틈 실험의 착수 시점이다.

## 3. 계약 1단계 산출

작업 사본은 `D:/mai-wt/foothold-lab/runner-ex42-v016`, 브랜치는 `runner/ex42-v016`이다. 이 단계에서는 준비표를 v0.16/D182로 갱신하고, v0.15 diff의 데이터 계약을 일부 연결했다.

- canonical SHA/version과 D182 고정값, 6개 판단의 상태를 YAML에 기록했다.
- terrain family E의 네 종류, A 평균대 L9 폭 0.09 m, B climb_up L9 0.53 m, 확장 E 경사 0.70/35°와 계단 0.30 m를 표에 추가했다.
- evaluation-only paper cells, 경사·지지면 축별 scale, 평가 마찰 기록 항목과 manifest의 논문 출처·physical flag·방향별 치수 확인을 명시했다.
- D176 command floors와 연속 환경 분모를 표에 기록했다. 모든 stage의 `terrain.floors.global_command_floor`에도 reverse 0.05, side_left/right 0.03을 명시하고, validator와 반례 시험이 누락·변조된 stage를 거절한다. `validate_command_shares()`는 0.40 × 0.14 = 0.056을 통과시키며 0.35 × 0.14 = 0.049를 거절한다.
- 유지 항 11개, E2부터 발 끌림 judge, D182의 노출 전용 HOLD, 조건부 명령 완결 정의 및 계단 평가값을 설정 계약에 넣었다.
- 실제 런타임의 지형 생성·점수 산출 연결은 아직 구현되지 않았다. `preparation_only`, lead 승인·EX-41 졸업·측정된 terrain manifest 요구를 계속 fail-closed로 유지한다.

## 4. 검증

테스트는 `isaac311` CPU 환경에서 실행했다.

```text
pytest -p no:cacheprovider --basetemp=D:/mai-tmp/runner/ex42-v016-stage1c -q foothold_s2/tests/test_ex42_prep_cpu.py foothold_s2/tests/test_ex42_v016_contract_cpu.py
12 passed in 3.61s
```

답이 알려진 share 경계 0.056 통과와 0.049 거절, 평가 축의 감소 방향, v0.16/D182 값, 준비-only 차단을 포함한다. Kit, GPU, 실제 terrain 생성, 실제 점수 생산은 수행하지 않았다.

## 5. 출발 관문 2단계

새 CPU 전용 `foothold_s2.scripts.ex42_ops`와 `foothold_s2/run_ex42.ps1`을 추가했다. 세 모드(`ops-check`, `rehearsal`, `production`) 모두 공통으로 EX42Plan 및 AST import 경계를 점검하며, Git source 검사 옵션은 정확한 HEAD · detached · clean 상태를 요구한다. rehearsal은 현재 plan-only이며 실제 simulator를 띄우지 않고, production은 승인 플래그가 있어도 runtime integration 미구현으로 거절되고, 고정 source root와 expected HEAD가 없으면 추가 차단된다. PowerShell wrapper에서 ops-check 실행을 확인했고, 실제 출력은 `state=blocked`, `production_launch_allowed=false`, blocker 6개였다.

```text
pytest -p no:cacheprovider --basetemp=D:/mai-tmp/runner/ex42-v016-stage2b -q foothold_s2/tests/test_ex42_prep_cpu.py foothold_s2/tests/test_ex42_v016_contract_cpu.py foothold_s2/tests/test_ex42_ops_cpu.py
16 passed in 4.60s
py_compile ex42_ops.py, ex42_prep.py: passed
PowerShell run_ex42.ps1 -Mode ops-check: expected blocked result, wrapper rejected
```

## 6. 실제 parser 및 환경 import 관문 3단계

`ex42_ops`는 EX-41에서 쓰는 parser builder로 `train_start.py` 선언과 설치된 RSL-RL CLI를 실제 조합해 알려진 인자를 파싱한다. `--task`, `--agent`, `--num_envs`, `--seed`, `--max_iterations`, `--resume_from` 및 AppLauncher의 `--headless --device cuda:0` 분리를 확인했다. 학습은 시작하지 않았다. 실제 등록 task의 env cfg import도 시도했으나 `isaac311`에 `pxr` 모듈이 없어 `ModuleNotFoundError`로 막혔다. 따라서 env class import는 미확인/미통과이며, ops-check는 이를 blocker로 보고한다. Kit/GPU는 기동하지 않았다.

```text
pytest -p no:cacheprovider --basetemp=D:/mai-tmp/runner/ex42-v016-stage3 -q foothold_s2/tests/test_ex42_prep_cpu.py foothold_s2/tests/test_ex42_v016_contract_cpu.py foothold_s2/tests/test_ex42_ops_cpu.py
17 passed in 5.81s
py_compile ex42_ops.py: passed
```

## 7. 지도 모드 계약 정정 4단계

정본 평가 모드는 문자열 `gt`, `pred`, `off` 세 개다. YAML bare `off`는 Python YAML parser에서 boolean `False`로 읽혀 CPU known-input 시험이 실패했다(고치기 전 1 failed, 3 passed). `'off'`로 인용하고 EX42Plan에서 정확한 세 문자열을 검증하도록 수정했다. 전체 관련 CPU 묶음은 17 passed in 5.95s다.

## 8. 명령 몫 stage consumer 5단계

새 `EX42Plan.validate_stage_command_shares()`가 stage ID의 `terrain.floors.global_command_floor`를 읽어 전체 3072 env 분모에서 조건부 명령 몫을 검증한다. E1 답을 아는 입력 0.40 × 0.14 = 0.056은 통과하고 0.35 × 0.14 = 0.049는 거절한다. 현재는 CPU preparation consumer이며 W72 runtime hook은 아직 연결하지 않았다. 전체 EX42 CPU 파일 4개는 25 passed in 6.45s다.

## 9. 확인된 lint 정리 6단계

`pyflakes`가 `ex42_prep.py`의 미사용 `json` import 1건을 찾았다. import를 제거하고 재검했다. EX42 전체 CPU 시험 25 passed in 6.50s, pyflakes 0 diagnostics, `git diff --check` 통과다.

## 10. 예행 사양 관문 7단계

`run_ex42.ps1 -Mode rehearsal` 입력에 출력 폴더와 10개 stage update 수를 받도록 했다. CPU plan-only 검사는 새 D:/mai-tmp/runner/ex42_rehearsal_YYYYMMDD_HHMMSS 경로, 양수 stage 길이 10개, detached · clean · 고정 HEAD를 요구하고 결과에 `kit_started=false`, `training_started=false`를 기록한다. 실제 예행 런타임은 아직 미연결이라 언제나 실행을 거절한다. EX42 CPU 시험은 26 passed in 7.45s, pyflakes 0, diff check 통과다.

## 11. 남은 일

- v0.15 diff 23개 중 runtime consumer까지 연결되지 않은 항목을 계속 구현한다. 특히 terrain preset 생성·manifest 측정·실제 평가기 연결은 현재 미구현이다.
- EX-41과 같은 출발 관문으로 ops_check, 예행 계획, 실제 parser 및 환경 import, 시작 스크립트를 단계별 커밋과 CPU 시험으로 추가한다.
- CPU preflight 및 AST import 확인은 준비 경로일 뿐이며, Kit/GPU 예행 승인이나 본 학습 허가가 아니다.

## 12. 지형 스펙 및 Kit 확인 요청 준비

R6/M02/M13에 따라 확장 E 코드는 지형 cfg import를 모듈 import 시점에 하지 않는다. 새 `terrains/ex42.py`는 정본 치수의 네 종류를 선언하고, D182 평가 축척은 `gap_m × 1.15`, `support_m`·`width_m × 0.85`로 이름이 명시된 축에만 적용한다. 그 외 값은 보존한다. E 종류별 내부 비율은 정본에 없어서 함수 입력으로 필수화했고 균등 배분을 학습 설정 기본값으로 두지 않았다.

`scripts/ex42_kit_probe.py`는 GPU/Kit을 직접 실행하지 않는 CLI 준비물이다. 승인 대기열에서만 GPU1로 실행하도록 장치 검사를 두고, 등록 env cfg를 로드·인스턴스화한 뒤 환경 자체는 만들지 않고, 네 확장 E 메시를 작은 진단 전용 구성으로 생성한다. 이 임시 0.25 비율은 네 생성기를 모두 호출하기 위한 probe 전용이며 계획이나 학습 비율에 기록하지 않는다. 타이머는 810초에서 timeout receipt를 쓰고 rc 124로 끝내며, 성공 시에만 done-file을 만든다. 이 경로는 아직 Kit에서 실행되지 않았으므로 실제 env import/메시 생성 증거가 아니다.

CPU 시험: `isaac311`에서 EX-42 준비·운영·guard·지형 계약 시험 32 passed(8.35s). 신규 테스트는 preset 목록·치수·축척 방향·잘못된 수치·Kit 바깥 lazy-import 차단·probe GPU 및 시간 제한 선언·env 생성/학습 호출 부재를 확인한다. pyflakes 0 diagnostics, `git diff --check` 통과. EX-41 운영 파일·프로세스 및 GPU는 건드리지 않았다.

후속 등록은 2026-11-05에 완료했다. dispatcher queue ID 467이 priority 4, GPU1, done-file 지정으로 대기 중이고, 실행은 dispatcher가 담당한다. 결과의 `environment_import`와 `family_e_generation`에서 두 증거가 모두 나와야 다음 연결을 판단할 수 있다. 실패/timeout이면 manifest는 만들지 않고 blocker로 보존한다.

## 13. EX-42 E 지형 CPU 단계 및 Kit 대기 등록

커밋 `4407fd360b6e758ab69b7ffa11bce26028023d92`에 네 파일을 추가했다. `foothold_s2/terrains/ex42.py`는 E 계열 네 지형의 승인된 범위와 평가 크기 배율을 CPU에서 선언하고, Isaac import는 Kit 함수 호출 시점까지 미룬다. 지형 종류별 학습 비율은 정본에서 정해지지 않아 임의 배분하지 않는다.

`scripts/ex42_kit_probe.py`는 승인 대기열 전용이며 CUDA 1만 허용한다. 등록 task의 환경 설정을 불러오고 네 종류 mesh 생성 결과를 측정하되 `gym.make`, 학습, 평가를 시작하지 않는다. 균등 비율은 네 생성기를 한 번씩 확인하기 위한 probe 전용 입력이며 학습 계획 비율로 저장하지 않는다. Kit 종료가 810초를 넘으면 timeout 영수증을 남기도록 했다.

재검증 결과:

```text
pytest -p no:cacheprovider --basetemp=D:/mai-tmp/runner/ex42-terrain-stage2-full -q test_ex42_correct_guards_cpu.py test_ex42_ops_cpu.py test_ex42_prep_cpu.py test_ex42_terrain_cpu.py test_ex42_v016_contract_cpu.py
32 passed in 7.66s
py_compile: passed
pyflakes: 0 diagnostics
git diff --check: passed
```

Kit 확인은 2026-11-05에 완료됐다. Dispatcher item 467의 rc 0, 수행 시간 9.56초이며 receipt `D:/mai-tmp/runner/ex42_kit_probe_20261105_1120.json`은 `passed`다. `FootholdS2SBEnvCfg`를 import·인스턴스화했고 네 E 지형을 생성해 합계 13,618 vertices, 26,304 faces, mesh SHA `c28e622ad8d27fd34e77eb617e3c0c8635ff740751ba04767b4e3668b922150d`를 기록했다. 단 이 P4 probe는 `environment_created=false`라 `gym.make`, reset, simulation step은 확인하지 않았다. 현재 queue readback에는 item 467의 priority가 2로 표시된다. 등록 요청은 P4였으며 변경 주체/시각은 확인 가능한 dispatcher log에 남아 있지 않다.

## 14. EX-42 environment create + step smoke

P4 receipt에서 task env cfg import와 mesh 생성은 통과했지만 환경 생성 및 step은 수행하지 않았으므로, 별도 probe를 추가했다. `foothold_s2/scripts/ex42_env_probe.py`는 1 env, family-E 4종의 probe-only terrain mix, zero action 3 step으로 제한한다. policy 평가·학습은 하지 않고, 810초 timeout과 success-only done-file을 사용한다. 실제 Kit은 dispatcher로만 실행하도록 `cuda:1` 외 장치를 거절한다.

CPU 시험은 먼저 새 모듈 부재로 collection error가 나는 것을 확인한 뒤 구현했다. 이후 EX-42 CPU 묶음 35 passed(7.03s), py_compile 통과, pyflakes 0 diagnostics, `git diff --check` 통과. 코드/test는 `e25ab650f93c865269e05a95e852ff8513e75ccf`에 커밋했다.

이 절 작성 시점에는 P2 dispatcher item 468이 GPU1, `--device cuda:1`, 3 step, 최대 810초로 대기 중이었다. done-file은 `D:/mai-tmp/runner/ex42_env_probe_20261105_1325.done`, receipt는 `D:/mai-tmp/runner/ex42_env_probe_20261105_1325.json`이다. 이후 receipt 결과는 §15에 기록한다. EX-42 curriculum runtime 소비자와 measured terrain manifest 연결은 별도 미완료다.

## 15. EX-42 environment create + step 결과

Dispatcher item 468 receipt를 읽었다. `state=passed`, `kit_started=true`, `training_started=false`, `environment_created=true`다. 실제 `ManagerBasedRLEnv`는 `FootholdS2SBEnvCfg`에서 `num_envs=1`, `device=cuda:1`, `action_dim=12`로 생성되었고 reset 뒤 zero action 3 step 모두 finite reward를 반환했으며 done 수는 0이었다. probe 비율은 네 family E 메시를 호출하기 위한 진단 전용 0.25씩이며 학습 일정으로 쓰지 않았다. 확인은 해당 네 지형의 환경 생성과 3 step까지이며, production curriculum runtime, 점수 생산, measured terrain manifest 연결은 아직 미구현이다.


## 후속: per-kind manifest 경로와 runtime 입구

- `foothold_s2/curriculum/ex42_manifest.py`는 Kit가 실제 생성한 한 terrain kind의 mesh 정점·면 SHA, bounds, 개수, 생성 시간을 측정하고 queued Kit receipt로 봉인하는 API를 추가한다. `assemble_manifest`는 family receipt의 출처, 중복, 축별 치수 방향과 family별 개수를 검사하며, 완전한 A/B/C/D/E/continuous inventory와 필수 aggregate 측정이 모두 갖춰진 경우에만 기존 `EX42Plan.validate_terrain_manifest`를 통과시켜 `measured`로 만든다. 부분 입력은 `partial`로 남는다.
- `foothold_s2/scripts/ex42_manifest_build.py`는 receipt들을 CPU에서 조립하는 CLI다. 부분 결과는 exit 2로 끝나며 launch gate 입력으로 사용될 수 없다.
- `continuous.make_runtime`은 이제 EX-42를 EX-40 runtime에 흘려보내지 않고 `EX42Runtime` 전용 입구로 보낸다. 이 입구는 3072 env와 명시적 CUDA device, 승인·졸업·완전 측정 manifest를 확인한다. 현재 v0.16 table은 `preparation_only`, 승인/측정 가정도 미결이고 active stage transition consumer는 아직 구현되지 않았으므로 본 학습은 계속 fail-closed다. 이 변경은 curriculum progression 구현 완료를 뜻하지 않는다.
- 실제 Kit 측정은 실행하지 않았다. 기존 receipt 467/468은 각각 E mesh probe와 1-env/3-step env smoke 범위다. 현재 worktree에는 A/B/C/D/continuous 각 preset builder/명시 kind inventory가 없어 39종 전체 manifest는 생성할 수 없다. 필요한 후속은 각 family의 명시 cfg 공급자와 실제 queued Kit kind receipt, family별 required aggregate measurements이며, 그 결과가 들어오기 전에는 미측정으로 유지한다.


## 후속: EX-42 점수 누락 경계와 DR 일정

- 팀장 지시대로 해당 경계 점수가 없거나 예상 회차가 아닌 늦은 점수만 있으면 `measurement_gap` 결정 payload를 반환하고 `applied_scale=planned_scale`을 유지하는 CPU 정책 함수를 추가했다. 이 payload는 학습 지속과 공백 이유를 기록하며, 누락 점수 때문에 DR scale을 보류하지 않는다. 코드 위치: `foothold_s2/curriculum/ex42_runtime.py`의 `resolve_missing_score_dr_boundary`.
- CPU 회귀는 경계 1001에서 m1000 점수 누락 시 planned DR 0.65, 경계 1501에서 m1250만 관측 시 planned DR 0.8을 확인한다. 두 경우 모두 gap reason과 회차를 기록하고 학습 지속을 표시한다.
- **팀장 확인 질문:** 점수가 도착했고 maintenance가 성능 미달일 때 기존 `hold_exposure_continue_training`만 적용하고 DR은 예정대로 올릴지, 아니면 maintenance 미달이면 DR scale도 유지할지 결정이 필요하다. 이번 수정은 이 경우를 바꾸지 않는다.
- EX-42 고정 table은 여전히 `preparation_only`이며 실제 runtime transition consumer는 아직 준비 gate 뒤에 연결되지 않았다. v0.16 table에는 단계별 DR scale 일정 항목도 없다. 따라서 0.65/0.8은 함수 전달값을 확인하는 CPU 입력일 뿐 공식 단계표 값이 아니며, 일정 값을 새로 만들지 않았다. 후속 caller는 승인된 일정에서 `planned_scale`을 전달해야 한다.
