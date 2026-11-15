> 분류: A/평가 · 1043 평가 후보 17s CPU 고침 보고
> 작성: Codex Worker · 2026-10-14
> 근거: TASK-codex-worker-1043-eval-fix2.md · VERIFY-astra-17s.md · run_20261014_230924_117964/summary.json · CAND-17S-SHA256SUMS.txt
> 요지: 17s 지적 7항목을 CPU 후보에서 고치고 실제 원본 메타·소유 자식 종료·승인 단회 사용·코드 변이를 재검했다
> 상태: CPU 후보 검증 완료 · 실제 GPU 진단 보류 · 운영 반영 없음

# 1043 평가 후보 17s 고침

## 격리와 판정

- 수정 전 `cand/` 154개 파일, 31,745,441바이트를 `cand_17s_base/`에 복사하고 SHA256 전수 대조 불일치 0. 보존 목록은 `CAND-17S-BASE-SHA256SUMS.txt`.
- 최종 후보 `cand/` 159개 파일의 SHA256 전부는 `CAND-17S-SHA256SUMS.txt`에 있다. 목록 파일 SHA256은 `ac97c2a1a2068dfbfb8e8fa1fbb883cde207b59fb575ab7ce71ab54a57849db9`. 모든 후보 파일을 다시 읽어 목록과 일치했다. 17r 기준과 다른 파일 12개, 그중 신규 5개. 변경 대응표는 아래와 `CAND-17S-CHANGES.json`에 있다.
- `manifest_s1043.json` 계약 SHA256은 `1824228d42e24c23cd7c8781e09926aeba881199d8315320bb7b238322f40d02`. 실행 결정값은 `UNDECIDED`다. 실제 `_eval` 등록 상위 원본 11개 해시 불일치 0, `_eval` 최상위 `*s1043*` 파일 0개. `_eval`은 읽기만 했고 CPU 시험에서 `CUDA_VISIBLE_DEVICES=-1`을 사용했다. GPU와 Isaac은 실행하지 않았다. 저장소 사본·커밋·댓글 게시도 하지 않았다.
- 새 승인 파일은 만들지 않았다. fixture의 승인 값과 2초 시간 한도는 CPU 시험 전용이며 팀장 결정이 아니다.

## 수정 항목과 지정 반례

아래 로그의 `normal`이 같은 시험에서 먼저 통과했다. `mutant`는 지정 검사를 바꾼 별도 Python 사본이다. `failed [...] want [...]`가 동일한 경우에만 CAUGHT로 셌다. 로그는 모두 `evidence_17s/run_20261014_230924_117964/` 아래에 있다.

| 항목 | 고침과 시험 | 정상 로그 | 반례가 걸린 위치 · 변이 want |
|---|---|---|---|
| 1 · 원본 q | `validate`는 q 원본의 누락된 `loaded_iter`만 허용하고 명시된 잘못된 값, checkpoint SHA, cmdr 누락은 거절한다. 진단 원본과 반복 원본 호출에만 `need_iter=False`. 실제 원본 meta SHA256 `4c4bed8364cf6cc1c873585dc895ec1fee99ab1bc699cf71bed9c19a834bb093`을 읽기 전용으로 확인하고 byte copy도 대조했다. `test_17s_original.py`. | `test_17s_original.log`, `code_mutants/original_field.normal.log` | `validate`의 iter 조건. `original_field.mutant.log`: failed [original q meta accepted] want [original q meta accepted], CAUGHT. |
| 3 · 승인 예산 | 승인 B에 ID·실제 attempt·log·restart scope를 묶었다. driver는 승인 attempt를 사용한다. `write_root/approval_ledger/<approval_id>/claim.json`을 디렉터리 원자 생성으로 단회 예약한다. 충돌·중단 후에는 같은 승인을 재사용할 수 없다. `test_17s_runtime.py`에서 정상 승인, attempt만 변경, 두 번째 시작, 동시 시작을 검사했다. | `test_17s_runtime.log`, `code_mutants/approval_ledger.normal.log` | `approval_binding`, `claim_approval`. `approval_ledger.mutant.log`: failed [second start refused] want [second start refused], CAUGHT. |
| 2 · 활성 시간·STOP | `deadline_epoch`는 시작 금지, `max_wall_s`는 실행 중 소유 자식 트리의 벽시계 상한으로 분리했다. STOP도 같은 감시기에서 처리한다. PID 생성 시각이 맞는 관찰 자식만 종료하고 전체 종료 확인 전 실행 lease를 풀지 않는다. rc 124/125 및 `held` 부분 결과. 2초 한도·4초 실제 CPU 자식의 `guarded` rc124, 정상 자식, 손자, STOP, OS lease를 검사했다. | `test_17s_runtime.log`, `code_mutants/wall_enforcement.normal.log` | `wait_child_tree`, `guarded`. `wall_enforcement.mutant.log`: failed [guarded wall returns nonzero held result] want [guarded wall returns nonzero held result], CAUGHT. |
| 4 · retry 0 | launch·wall은 양의 정수, retry는 0 이상 정수로 나누어 검사한다. bool·문자열·음수 거절. 승인 retry 0에서 실제 `guarded` launch가 한 번뿐임을 검사했다. | `test_17s_runtime.log`, `code_mutants/retry_zero.normal.log` | `launch_errors`의 risk 검증과 `guarded`의 `min(retries+1)`. `retry_zero.mutant.log`: failed [retry zero approved] want [retry zero approved], CAUGHT. |
| 5 · byte-only 차이 | `semantic_equal`, `json_sha_equal`, `traj_sha_equal`을 별도 기록하고 JSON byte-only에는 `byte_only_json` 원인 코드를 준다. 세 값 모두 일치해야 완료인 현재 보수 규칙은 유지했다. 통과 기준 최종 결정은 UNDECIDED. | `test_17s_diagnostic.log`, `code_mutants/byte_only_reason.normal.log` | `diagnostic_compare_pair`. `byte_only_reason.mutant.log`: failed [byte-only JSON reason] want [byte-only JSON reason], CAUGHT. |
| 6 · 보고 동등성 | 기본·반복·실패 run을 `diagnostic_record` 공통 필드로 기록한다. 시간, tries·try_records, preflight, 장치 전체 peak/여유, fingerprint, buffer, 입력 해시, reset을 같은 키로 남긴다. 없는 자료는 null. not_run, held_runs, failed_runs를 분리한다. | `test_17s_diagnostic.log`, `test_17r_d.log` | 반복과 실패의 필드 집합 대조, held와 failed 상태 구분. 이 항목은 작업서의 코드 변이 필수 6종에 포함되지 않는다. |
| 7 · 공통 경로 | 기본은 write_root 내부만 허용한다. `deployment.common_write_allowlist`의 명시적 key+exact path에 한해 registry·convert_lock·run_lease의 source_eval 경로를 예외로 허용한다. 실제 경로 선택은 UNDECIDED. | `test_17s_diagnostic.log`, `code_mutants/common_allowlist.normal.log` | `assert_isolated`. 무허용 `_eval/slot`, 미등록, 부분 문자열, 대소문자 별칭 거절. `common_allowlist.mutant.log`: failed [_eval slot without allowlist rejected] want [_eval slot without allowlist rejected], CAUGHT. |

**종료 정책 한계:** 생성 시각 확인이 불가능하거나 접근이 막힌 관찰 자식은 신호를 보내지 않고 lease를 계속 보유한다. 이미 부모가 사라진 뒤 처음 관찰되는 자식이나 PID 재사용 전체에 대한 보증은 아니다. CPU fixture의 종료 유예 0.2~0.5초와 `held` 처리는 승인 결정값이 아니다.

## 승인 B 스키마와 장부

승인 JSON 외형은 `{approved:true, by, approved_at, reviewed:B}` 그대로다. B는 이제 정확히 22개 키다:

`experiment`, `train_seed`, `contract_sha256`, `stage`, `approval_id`, `attempt`, `log_name`, `restart_scope`, `termination_policy`, `comparison_pass_rule`, `candidate_hashes`, `comparison_report_sha256`, `gpu_index`, `gpu_uuid`, `CUDA_VISIBLE_DEVICES`, `diagnostic_repeat_original`, `deadline_epoch`, `risk_limit`, `convert_lock`, `run_lease`, `registry`, `python`.

17r B 대비 추가된 정확한 키는 `approval_id`, `attempt`, `log_name`, `restart_scope`, `termination_policy`, `comparison_pass_rule`다. `candidate_hashes`는 다음 5개 Python 파일이다:

| 파일 | 17s SHA256 |
|---|---|
| `s1043_manifest.py` | `58bf719ae8817d7417784249aa288a83b2e9a038ddea70336c7e7927ef5a2a24` |
| `cmdr_bundle_compare_s1043.py` | `77c5e5dd0798f7030b1259072c973d1bca38d9df9e58bcdce1a859887c906980` |
| `cmdr_eval_driver_s1043.py` | `236e79b26f883454feb08496a3d841b8ed76c71fdf7078a2a81b359ff0b1a303` |
| `cmdr_post_s1043.py` | `9b2565c48946640aab3238cc1ed968f3a922eb758a93654a502b5571c2b22d59` |
| `frozen_exec_s1043.py` | `eaee9668015d36ef2bde9ef52c4f3a419c38187e0a923c069ec755ba53daaa8e` |

`risk_limit`의 필드는 `max_child_launches`, `max_retries_per_run`, `max_wall_s` 그대로다. 단회 claim은 하나의 승인 ID에서 재기동을 거절하므로 소비된 launch·retry 수를 새 프로세스로 이월할 필요가 없다. 이 기제는 `restart_scope=single_start_no_reuse`를 실제로 승인받은 fixture에서만 작동한다. 현재 manifest의 ID·attempt·log·scope·종료 정책은 UNDECIDED이고 `launch_errors`가 기동을 막는다. `comparison_pass_rule`도 UNDECIDED로 B에 묶되, 진단 보고에는 적용 중인 엄격 규칙을 명시한다.

## CPU 묶음과 첫 실패

새 run-id: `evidence_17s/run_20261014_230924_117964/summary.json`. 10/10 종료 코드 0, 합계 시험 실행 벽시계 81.67초. 이 시간은 CPU 시험 시간이지 운영 진단 소요가 아니다.

| 시험 | rc | 초 | 로그 |
|---|---:|---:|---|
| `test_17r_b.py` | 0 | 3.80 | `evidence_17s/run_20261014_230924_117964/test_17r_b.log` |
| `test_17r_c.py` | 0 | 1.20 | `evidence_17s/run_20261014_230924_117964/test_17r_c.log` |
| `test_17r_d.py` | 0 | 0.42 | `evidence_17s/run_20261014_230924_117964/test_17r_d.log` |
| `test_17r_e.py` | 0 | 28.80 | `evidence_17s/run_20261014_230924_117964/test_17r_e.log` |
| `test_17r_post_cli.py` | 0 | 3.05 | `evidence_17s/run_20261014_230924_117964/test_17r_post_cli.log` |
| `test_17r_mutants.py` | 0 | 0.30 | `evidence_17s/run_20261014_230924_117964/test_17r_mutants.log` |
| `test_17s_original.py` | 0 | 0.30 | `evidence_17s/run_20261014_230924_117964/test_17s_original.log` |
| `test_17s_runtime.py` | 0 | 8.34 | `evidence_17s/run_20261014_230924_117964/test_17s_runtime.log` |
| `test_17s_diagnostic.py` | 0 | 0.38 | `evidence_17s/run_20261014_230924_117964/test_17s_diagnostic.log` |
| `test_17s_code_mutants.py` | 0 | 35.08 | `evidence_17s/run_20261014_230924_117964/test_17s_code_mutants.log` |

17r 입력 변조는 **12종**, 17s 코드 검사 비활성 변이는 **6종**이다. `code_mutants/code_mutants.json`에 각 변이 소스 SHA256, 정상·변이 종료 코드, 시간, `failed`·`want`가 있다. 입력 변조 12종을 코드 변이 수에 합산하지 않았다.

첫 실패는 최종 분모에서 제외했다. 실제 원본 meta 시험의 첫 시도는 원본 폴더에 slot 기록 파일이 없어 검증 전에 FileNotFoundError였고, 시험의 slot 경계만 CPU fixture로 대체한 뒤 실제 meta와 결과 파일을 검증했다. 변이 예비 실행에서 retry 0 변이는 별도 복사 모듈의 `__file__`·ROOT 위치 때문에 `normal approval binding`에서 먼저 실패해 NOT_CAUGHT였다. 복사 모듈의 배치 정보만 실제 후보로 맞춘 뒤 예비 실행과 최종 묶음에서 지정 위치 `retry zero approved`를 확인했다. 이전 17r 연결 시험의 ready·validate·fingerprint는 성공 함수로 교체되어 있으므로 그 시험을 실제 진단 결과 검증으로 세지 않았다.

## 후보 변경 해시 대응

| 파일 | 17r SHA256 | 17s SHA256 |
|---|---|---|
| `build_manifest_s1043.py` | `f0e4163cacee8b470f7e53623a39ac03e89c0c13ce45fb2b134356593f03046d` | `fc2bf8a108da7c5f3517c9bcf3410da58cc208b288a3897bddc2a2c41c1cb7c8` |
| `cmdr_eval_driver_s1043.py` | `69008ba41b52c31cdef420e27171d88d8ff5d433172656fcfdfdb1cfbe445460` | `236e79b26f883454feb08496a3d841b8ed76c71fdf7078a2a81b359ff0b1a303` |
| `manifest_s1043.json` | `79929490f5f271f50ca7794297fdce54f5c5edf144d78ce521a34971ecf1e4e3` | `837fbe07b4240b80dcc9bbb269534ed2f076eff0899c325b77eaa00843909413` |
| `run_all_17s.py` | `NEW` | `7daa9ab0f960a65687f20d268d9ad199d20db699973b0b5c2aaffbc31bbea38f` |
| `s1043_manifest.py` | `ce1ad4930c5f1e3f42932b037a9c5cf49f537e93a3be7148ae41c3fcc3feda09` | `58bf719ae8817d7417784249aa288a83b2e9a038ddea70336c7e7927ef5a2a24` |
| `test_17r_b.py` | `2540ebf3303b179d5dd031bb82d91c8193dabc500a7f5aec13f491ae4532b1fb` | `8b6ee6a1b0c7e56c4ed103a7774c89d1c7c39ce0f4f029ea06ad25d2955782b8` |
| `test_17r_d.py` | `98856d39b2a60dcbebe02849c581712c70d39d4523561b5c79a0835ddee7869c` | `9d4225953c633098e7bc0383970c579511d3a97e1bb76b97fb7e799d6bb6b26e` |
| `test_17r_e.py` | `cded0b516feb71a48590cc57915f5e8fdaf05fe6a2eaa040e2669483830015d5` | `c743eb607c8db5140736ab2d2d39aad18b7878855cda173ca0e912920309c760` |
| `test_17s_code_mutants.py` | `NEW` | `834ffe630c2432a698569c5bcc0ed2272b08e40290446114013aa92a622969cc` |
| `test_17s_diagnostic.py` | `NEW` | `6bb36658f05ca4a00c35db8c6c6a6aad48f9ff068bb46110c1a2b6cffa87dc8d` |
| `test_17s_original.py` | `NEW` | `34fc45137c6e350f5cfcb303b4eefa74754acf7b32c771a7ad994c25d70c676d` |
| `test_17s_runtime.py` | `NEW` | `71f40d712b43574cffab87c172e68c9c8569ed4988cdafaa405bfeb373a7bab0` |

## 미확인과 팀장 결정

실제 GPU 진단, 물리 UUID·free/peak, 실제 slot v3·guard·isolate·Kit 연쇄, 공통 lease를 다른 모든 실행기가 쓰는지, 운영 경로의 common allowlist 또는 write_root 적용은 **미확인**이다. CPU의 손자 시험은 관찰된 트리에 한한다. 장치 peak는 장치 전체 값이며 이 작업 전용 사용량이 아니다. 세 진단 실행과 A 45회는 실행하지 않았다. GPU 진단 기술 승인은 이 보고로 성립하지 않는다.

팀장 결정은 계속 **UNDECIDED**: GPU 배정, 독점 시간창과 참가 실행기 범위, `deadline_epoch` 시작 금지 시각, launch·retry·wall 상한값, 강제 종료 유예·부분 결과 처리, 원본 반복 예산, 승인 재기동 범위, 진단의 의미/바이트 통과선, 공통 경로 배치다. 현재 구현은 단회 승인 재사용 거절과 보수적 3중 비교를 제공한다. 다른 정책 선택에는 코드와 승인 B 재검이 필요하다.
