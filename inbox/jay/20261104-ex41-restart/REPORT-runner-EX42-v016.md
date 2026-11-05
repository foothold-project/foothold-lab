> 분류: C/운영
> 작성: 오흥재 · 2026-11-05
> 근거: EX-41 운영 원장 · 잠긴 EX-41 코드 · CURRICULUM-GATES v0.16 §E · D182 · EX42-V015-RUNNER-DIFF.md
> 요지: EX-41 1251 경계 동작을 원자료와 코드로 설명하고 EX-42 정본 계약 1단계를 CPU 시험으로 고정한다
> 상태: EX-41 분석 확인 · EX-42 계약 1단계 및 CPU 출발 관문 통과 · 런타임 미연결

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

새 CPU 전용 `foothold_s2.scripts.ex42_ops`와 `foothold_s2/run_ex42.ps1`을 추가했다. 세 모드(`ops-check`, `rehearsal`, `production`) 모두 공통으로 EX42Plan 및 AST import 경계를 점검하며, Git source 검사 옵션은 정확한 HEAD · detached · clean 상태를 요구한다. rehearsal은 현재 plan-only이며 실제 simulator를 띄우지 않고, production은 승인 플래그가 있어도 runtime integration 미구현으로 거절된다. PowerShell wrapper에서 ops-check 실행을 확인했고, 실제 출력은 `state=blocked`, `production_launch_allowed=false`, blocker 5개였다.

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

## 10. 남은 일

- v0.15 diff 23개 중 runtime consumer까지 연결되지 않은 항목을 계속 구현한다. 특히 terrain preset 생성·manifest 측정·실제 평가기 연결은 현재 미구현이다.
- EX-41과 같은 출발 관문으로 ops_check, 예행 계획, 실제 parser 및 환경 import, 시작 스크립트를 단계별 커밋과 CPU 시험으로 추가한다.
- CPU preflight 및 AST import 확인은 준비 경로일 뿐이며, Kit/GPU 예행 승인이나 본 학습 허가가 아니다.
