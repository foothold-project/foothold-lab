> 분류: A/정책학습 · 학습 · 검증 · Codex Worker 작업서 (sol) · step29
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-17 20:50
> 근거: A 짧은 학습 `chain.receipt.json` (verdict HOLD, `short_proof:name 'math' is not defined`) · `bundle/s2_train_launch.py` 163~168행 `math.isclose` 와 3~8행 import 목록(math 없음) · `s2_train_contract.py:94` · `s2_eval_full_contract.py:121` · `s2_compare_ab.py:238`
> 요지: A 는 2000 update 를 끝냈으나, 마지막 증명 함수 `verify_short_single_result` 가 `math` 임포트 누락으로 죽어 영수증이 HOLD 다. B 기동 · 최종 평가 · 비교가 모두 A 영수증 verdict `RUN_COMPLETE_UNVERIFIED` 를 요구한다. 임포트 한 줄을 고치고, 이미 끝난 A 를 같은 증명으로 다시 확인하는 재검증 도구를 만들되, 원본 영수증은 건드리지 않고 관문도 약화하지 않는다
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 을 띄우지 않는다 · 지금 GPU 0 은 lead 가 평가기 smoke 로 쓴다)

# sol 작업서: `math` 임포트 누락 수리와 A 영수증 재검증 (step29)

## 0. 지킬 것

step28 과 같다(새 사본 `codexE/s2_step29/`, `-I -B` CPU, 정상 먼저, 변이는 지정 첫 FAIL, 해시 목록 CR 없이 번들 안에 닫기, B 전체 회귀). 컨텍스트가 적으면 `HANDOFF-step29-*.md` 로 진행 상태를 먼저 남겨라. **A 의 실제 실행 폴더 `C:/Users/AI-WS01/s2_lab/s2_step27_run/runs/shortA-20261017-181213-890c5c24/` 는 읽기 전용이다. 그 안에 아무것도 쓰지 마라(영수증 포함).**

## 1. 사실 (lead 가 원자료로 확인한 것)

- A 는 2000/2000 update, 종료 코드 0, 체크포인트 11개 SHA 기록, 부모 SHA 불변, 가족 정리 확인, 임대 해제, 잠금 해제까지 모두 정상이다. 영수증의 `verdict` 만 HOLD, `boundary_ok` False, `reason` 이 `short_proof:name 'math' is not defined` 이다.
- `s2_train_launch.py` 는 `import argparse, hashlib, json, os, time` 과 `from pathlib import Path` 만 있고 `math` 가 없다. 163~168행(첫 10 update 투영 검사)에서 `math.isclose` 를 쓰는 순간 NameError 가 나고, 그 앞의 검사는 모두 통과했다. 이 경로는 `budget_origin_epoch` 가 있는 manifest(step23 이후)에서만 실행되고 실제 완료 뒤에야 닿아서, CPU 시험이 한 번도 실행하지 못했다.
- lead 가 A 실제 자료로 그 네 `isclose` 와 두 부등식을 손으로 다시 계산했더니 모두 맞는다(평균 4.4563 s, 투영 합 8957.81 s, `exceeds_budget` False, 첫 10개 값 일치). 그러나 도구가 한 것이 아니므로 증거로 쓰지 않는다. 이 작업이 같은 계산을 도구로 하게 만든다.
- 같은 NameError 는 step28 `frozen_delivery` 에도 그대로 들어 있다.

## 2. 필요한 것

1. **임포트 수리.** `s2_train_launch.py` 에 `import math`. 이 파일의 다른 변경은 하지 않는다. step28 `frozen_delivery` 와 바이트 비교해서 이 파일 외 달라진 학습 · 입력 · 환경 코드(`s2_train_entry_17v.py`, `s2_env_config_17v.py`, `s2_sensor_tracker_17v.py`, `s2_plumbing.py` 등)가 없음을 보고서에 파일별 SHA 표로 적어라. 새로 더하는 파일(재검증 도구, 시험)은 별도로 구분한다.
2. **회귀 시험이 실제 함수를 실행하게.** `verify_short_single_result` 를 `budget_origin_epoch` 가 있는 manifest 와 실제 모양의 `first_ten_projection.json`, `updates.jsonl`(2000줄), `result.json` 로 끝까지 부른다. (a) 정상 입력 PASS, (b) `math` import 를 지운 사본에서 이전 FAIL(이름 오류)이 재현됨, (c) 투영 값을 1 ULP 넘게 바꾸면 지정 `TrainHold("short_first_ten_projection_invalid")`, `projected_total_wall_s` 가 `max_wall_s` 를 넘으면 같은 FAIL. 가짜 손으로 만든 값만 쓰지 말고, A 실제 폴더의 파일을 읽어(쓰지 않고) 같은 함수를 부르는 시험도 하나 둔다.
3. **재검증 도구** `s2_reverify_short_receipt.py` (이름은 정해도 된다). 입력은 A 의 claim 폴더 경로. 동작:
   - 원본 `chain.receipt.json` 과 `chain.receipt.sha256` 의 SHA 를 먼저 잰다. 원본은 어떤 경우에도 수정하지 않는다.
   - **허용 조건이 정확히 이 사고 하나다**: `verdict == "HOLD"`, `reason == "short_proof:name 'math' is not defined"`, `exit_code == 0`, `family_cleanup_confirmed`, `family_active_count == 0`, `gpu_lease_released`, `usd_lock_released`, `parent_sha256_before == parent_sha256_after == PARENT_SHA`, `executed_updates == 2000`, 체크포인트 SHA 가 디스크의 파일과 모두 일치, `result_sha256` 일치. 하나라도 다르면 거절(다른 사고를 덮지 않는다).
   - 위가 맞으면 **수리된** `verify_short_single_result` 를 같은 manifest · result · out_root 로 다시 부른다. 통과하면 새 파일 `chain.receipt.reverified.json` 을 **원본 옆이 아니라 새 폴더** (예: `<claim>/../reverified/…`)에 쓴다. 내용은 원본 영수증의 모든 필드 + `verdict: "RUN_COMPLETE_UNVERIFIED"`, `boundary_ok: true`, `reason: null` + 출처 필드 (`reverified_from_sha256`, `original_verdict`, `original_reason`, `reverifier_bundle_sha256`, `reverified_epoch`, 사용한 도구 파일 SHA). 출처 필드가 없으면 B 의 기동기가 받지 않게 하라.
   - **관문은 약화하지 않는다.** `s2_train_contract.py:94`, `s2_eval_full_contract.py:121`, `s2_compare_ab.py:238` 의 검사 줄은 바꾸지 마라. 재검증 영수증이 그대로 통과할 수 있는 모양이어야 하고, 출처 필드가 없는 위조 파일 · 원본 SHA 와 어긋난 파일 · 본문을 바꾼 파일은 거절돼야 한다(변이 시험).
4. **B 가 같은 코드로 가는지.** 수리 번들이 만든 새 `short_conditions_sha256` 가 A 영수증의 값(`d4cead87…`)과 같은지 확인한다(plan 의 `SHORT_MATCH` 키에 번들 해시가 들어 있는지 읽어서 보고). 다르면 B 기동기가 거절할 것이므로 어디가 달라지는지와 해법을 보고서 맨 위에 적어라.
5. **기동기 핀.** `s2_attended_launch_short.py`, `s2_attended_launch_eval0.py`, `s2_attended_launch_evalfull.py` 의 번들 목록 SHA 핀을 새 번들에 맞추고(step27/28 과 같은 방식), 원본 번들 바이트 변이 3 곳 거절 시험을 유지한다.
6. **(20:55 수정) 평가기 Kit 첫 실제 시험 결과가 나왔다. 이 작업을 둘로 나눈다.** 29a = 위 1~5 (math 수리 + 재검증 도구 + 핀). **먼저 끝내고 바로 알려라** (B 학습 2.5 시간을 GPU 에 걸어야 한다). 29b = 아래 7번 (평가기 수리). 29b 는 B 학습이 도는 동안 하며 늦어도 23:00. 29a 를 29b 때문에 늦추지 마라. 평가기 코드에 비슷한 누락이 있는지는 `pyflakes` 계열 정적 검사(정의되지 않은 이름)로 보고서에 목록으로 적어라.
7. **(29b) 평가기 첫 실제 Kit 결과 (lead 가 20:46 에 돌린 smoke).** 근거 폴더(읽기 전용): `C:/Users/AI-WS01/s2_lab/s2_step28_run/frozen_delivery/runs/eval0-live-20261017-204625-93c781ae/` . 사실: 첫 case-arm `gap-000-s3101` A 는 실제 Kit 에서 **정상 실행됐다**(Kit 시작 포함 자식 25.5 s, 에피소드 125 step, 종료 코드 0, `missing_reason` null, 건당 새 프로세스 경로가 동작). 그런데 부모의 `_verify_fragment`(`s2_eval_case_orchestrator.py` 75행)가 `ast.literal_eval(binding["torch_uuid_raw"])` 에서 SyntaxError 로 `case_child_device_binding` HOLD 를 내고 전체가 멈췄다. 실제 `device_binding.json` 의 값은 `"<torch._C._CUuuid object at 0x000001CEC04008B0>"` (`s2_device_binding_a2.py:33` 의 `repr(raw)`)라 파이썬 리터럴이 아니다. 이 torch 2.7 에서 `str(props.uuid)` 는 UUID 문자열이지만 `repr` 은 객체 표기다. CPU 시험은 리터럴 문자열로 가정해서 이 경로를 못 잡았다. 같은 `ast.literal_eval(...["torch_uuid_raw"])` 가 `s2_eval_supervisor.py:121` 에도 있다. 수리 방향: 파일의 `torch_uuid_raw` 는 UUID 비교의 근거가 될 수 없음을 인정하고(파일에 UUID 문자열이 없다), 자식 보고(`runtime.device_binding.torch_uuid_normalized`, 실제로 `c08e23b062b6a4f28eb211151c6a8c7b` 로 맞다)와 파일의 `kit_observed` · `torch_device_name` 의 일치로 판정하되, 파일에 UUID 가 있었다면(리터럴인 경우) 기존 비교도 유지한다. 관문을 없애지 말고 무엇을 근거로 바꿨는지 보고서에 적어라. **실제 캡처 자료 재생 시험**: 위 폴더를 읽기만 해서(복사본 사용) `_verify_fragment` 와 그 뒤 부모 경로(`usd_evidence`, 조각 합치기, 영수증)를 실제 값으로 끝까지 돌리는 시험을 둬서, 첫 arm 이후의 숨은 오류를 GPU 없이 최대한 먼저 찾아라. 120건 시간 추정은 이 실측(건당 약 25 s, 120건 약 50분)을 가정으로 갱신하라.

## 3. 끝나면

`REPORT-s2-step29.md` (사실 · 수리 줄 · 변경 파일 SHA 표 · 시험 결과 첫 FAIL 과 변이 · 재검증 도구가 A 실제 자료에서 낸 결과(원본 읽기 전용, 도구 출력 원문) · 정적 검사 결과 · 미확인 · lead 실행 명령 한 줄 · B 기동 명령), `S2-STEP29-SHA256SUMS.txt`, #550 댓글 초안(미게시). **A 의 GPU 0 이 놀고 있으므로 가능한 한 빨리**(목표 60~90 분). 막히면 막힌 줄과 필요한 값을 적어라. 컨텍스트가 11 % 이하이면 먼저 `/compact` 하거나 새 세션을 요청하라.
