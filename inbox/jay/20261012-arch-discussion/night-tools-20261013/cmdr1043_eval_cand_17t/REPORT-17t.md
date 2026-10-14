> 분류: A/평가 · 1043 평가 후보 17t CPU 고침 보고
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-1043-eval-fix3.md · VERIFY-astra-17t.md · evidence_17t/run_20261015_010804_121484/summary.json · CAND-17T-SHA256SUMS.txt
> 요지: 17t 결함 3건과 보강 항목 3건을 후보에서 고치고 CPU 정상·반례·코드 변이·회귀 시험을 수행했다
> 상태: CPU 후보 검증 완료 · 운영 반영 없음 · GPU 진단 보류

# 1043 평가 후보 17t 고침

## 격리와 후보

- 수정 전 `cand/` 159개 파일, 31,780,361바이트를 `cand_17t_base/`에 보존하고 SHA256 전수 대조 불일치 0을 확인했다. 보존 목록은 `CAND-17T-BASE-SHA256SUMS.txt`다.
- 최종 `cand/` 165개 파일의 SHA256 전부는 `CAND-17T-SHA256SUMS.txt`에 있다. 목록 파일 SHA256은 `dfdb76470970d22ce821aeebffe9d640d975d0c9e96979b3ea94f083c8c353e0`이다. 다시 읽은 후보 165개 해시 불일치 0. 17s 시작본 대비 변경 13개, 신규 6개이며 `CAND-17T-CHANGES.json`에 대응표가 있다. 시험 중 다시 생성된 `__pycache__/s1043_manifest.cpython-311.pyc`는 시작본 바이트로 되돌린 뒤 목록을 만들었다.
- `manifest_s1043.json` 자체 SHA256은 `837fbe07b4240b80dcc9bbb269534ed2f076eff0899c325b77eaa00843909413`, 계약 SHA256은 `1824228d42e24c23cd7c8781e09926aeba881199d8315320bb7b238322f40d02`로 17s와 같다. 팀장 결정값은 모두 `UNDECIDED`다. ASTRA의 launch·retry·반복·wall·종료 유예·restart·비교 규칙 권고값을 manifest에 넣지 않았다.
- 등록된 `_eval` 최상위 원본 11개 SHA256 일치, 최상위 `*s1043*` 파일 0개를 읽기 전용으로 확인했다. `_eval` 대상 쓰기 0, GPU·Isaac 실행 0. 모든 실행은 `CUDA_VISIBLE_DEVICES=-1` CPU 시험이다. 공유 저장소에는 쓰거나 커밋하지 않았고 #550 댓글도 게시하지 않았다.

## 17t 항목 1~6

모든 로그 기준은 `evidence_17t/run_20261015_010804_121484/`다. `normal`이 같은 시험에서 먼저 통과했고, 변이의 첫 `FAIL`이 지정한 `want`와 같을 때만 CAUGHT로 셌다.

| 항목 | 후보 고침과 정상 시험 | 반례와 변이 결과 |
|---|---|---|
| 1 · PID 소유권 | `wait_child_tree`는 관찰된 부모의 `(pid, create_time)`이 현재도 같고 실행 중일 때만 새 자식을 등록한다. 부모 불일치·소멸, 자식 접근 거부, 생성 시각 오류는 `unowned_unknown`으로 두고 신호를 보내지 않으며 lease를 유지한다. 불명 PID가 자연 종료하거나 사라진 뒤에는 보류 목록에서 해제한다. `test_17t_ownership.log`의 가짜 psutil 표에서 100→110 정상 손자 정리, 110 PID 재사용 뒤 300 미등록·무신호·보류, 접근 거부와 부모 소멸 보류가 통과했다. 실제 PID에는 신호를 보내지 않았다. 기존 STOP, 2초 wall/4초 자식, 실제 CPU 고아 자식의 자연 종료와 lease는 `test_17s_runtime.log`, `test_17r_e.log`에서 재검했다. | `test_17t_code_mutants/parent_identity.normal.log` 통과. 부모 식별 조건을 제거한 변이는 `parent_identity.mutant.log`에서 `failed [PID reuse child never signalled] want [PID reuse child never signalled]`, CAUGHT. |
| 2 · 승인 B 값 | `comparison_pass_rule` 허용 집합은 `semantic_and_json_bytes_and_traj_bytes` 하나다. launch 검증과 driver 판정이 같은 승인 값을 사용한다. `approval_id`, `attempt`는 1~64자, `log_name`은 1~50자의 영문·숫자·밑줄·하이픈만 허용하고 예약어를 대소문자 무관하게 거절한다. `restart_scope=single_start_no_reuse`만, `termination_policy`의 키 집합·양의 유한 종료 유예·`partial_result=held`만 검증한다. `test_17t_approval.log`에서 실제 `require_files=True` 정상 승인과 30개 반례, 두 개의 양의 유예 fixture, driver의 비교 규칙 적용, UNDECIDED 차단이 통과했다. | `comparison_rule_gate.normal.log` 통과. 지원 규칙 검사 제거 변이는 `comparison_rule_gate.mutant.log`에서 `failed [comparison_pass_rule 0 rejected] want [comparison_pass_rule 0 rejected]`, CAUGHT. |
| 3 · 필수 지문 | `diagnostic_record`는 `valid` 이전에 필수 지문·배치와 cells/traj SHA를 확인하고 계산 예외를 `held`와 `why`로 기록한다. 기본 원본과 반복 원본 모두 적용하고 필수 지문 없는 완료를 막는다. 실제 원본 q 결과의 `meta.json` SHA256 `4c4bed8364cf6cc1c873585dc895ec1fee99ab1bc699cf71bed9c19a834bb093`을 codexE 안에 바이트 복사한 `test_17t_fingerprint.log`에서 정상 valid, 복사본 `env_origins.npy` 제거 뒤 validate 통과이지만 record held, 반복 record held, 복원 뒤 valid를 확인했다. | `fingerprint_hold.normal.log` 통과. 필수 지문 보류 조건 제거 변이는 `fingerprint_hold.mutant.log`에서 `failed [missing fingerprint held] want [missing fingerprint held]`, CAUGHT. 실패 run의 없는 증거는 null로 남는다. |
| 4 · 공통 지문 | pairing 2종, terrain mesh/origins, env origins, N/T/cells, obs shapes, UUID, layout, traj0를 orig와 small/default/repeat 사이에서 비교한다. evaluator source, PhysX small buffer, eval changes는 의도한 차이 목록으로 별도 표시한다. 공통 지문 불일치는 항목명을 보고하고 `held_common_fingerprint`가 된다. 의미/JSON 바이트/traj 바이트 비교는 승인 규칙의 독립 판정으로 남는다. | `test_17t_diagnostic_contract.log`에서 제외 항목 차이는 통과, env_origins 차이는 `orig_vs_small` 키로 보류, 반복 승인 뒤에도 불일치 보류, 필수 지문 누락은 `held_incomplete`가 통과했다. |
| 5 · 비용과 반복 사유 | `wall_s`는 마지막 try의 이전 필드로 유지하고 `wall_s_scope=last_try_only`를 명시했다. `try_wall_s_sum`, `startup_allocated_s`, `non_try_wall_s`, 준비·모든 try·대기·검증을 합친 `total_wall_s`와 report `startup_wall_s`, `attempt_total_wall_s`를 추가했다. | 같은 진단 계약 로그에서 전체 시간이 startup과 tries 이상임을 확인했다. `repeat_not_needed`, `repeat_not_approved`, `repeat_ran` 및 이유가 정상·불일치·승인 반복에서 구분되었다. CPU fixture 시간이며 GPU 비용은 미측정이다. |
| 6 · 공통 allowlist | `registry`, `convert_lock`, `run_lease`에 한해 source_eval 내부의 정확한 key+path만 예외로 허용한다. 와일드카드, 디렉터리, 잘못된 확장자, 등록되지 않은 경로를 거절한다. 실제 공통 경로는 UNDECIDED다. | `test_17s_diagnostic.log`에서 정상 exact path와 비공통 키·디렉터리·와일드카드·별칭 반례가 통과했다. |

## 승인 B 검증 범위

B의 외형은 `{approved:true, by, approved_at, reviewed:B}`이고, 22개 키는 `experiment`, `train_seed`, `contract_sha256`, `stage`, `approval_id`, `attempt`, `log_name`, `restart_scope`, `termination_policy`, `comparison_pass_rule`, `candidate_hashes`, `comparison_report_sha256`, `gpu_index`, `gpu_uuid`, `CUDA_VISIBLE_DEVICES`, `diagnostic_repeat_original`, `deadline_epoch`, `risk_limit`, `convert_lock`, `run_lease`, `registry`, `python`이다. 17t는 B 키 수를 바꾸지 않고 각 필드의 형식·지원 집합을 강화했다. 이름 예약어는 `undecided`, `none`, `null`, `true`, `false`, `unknown`, `nan`이다. 유예 시간에 운영 숫자를 지정하지 않았다. 0.25와 12.7초는 양의 유한수 형식 확인용 CPU fixture다. 승인된 비교 규칙은 driver가 그대로 적용한다. manifest의 `UNDECIDED`는 여전히 launch gate에서 거절된다.

## 전체 CPU 묶음과 변이

새 run-id `evidence_17t/run_20261015_010804_121484/summary.json`: 15/15 종료 코드 0, 시험별 벽시계 합계 109.77초. 17r 6개, 17s 4개, 17t 5개를 모두 포함한다. 각 시험의 종료 코드·시간·로그 경로는 summary에 있다. `test_17r_e.py`는 실제 OS lock, registry, CPU 자식·손자 lease를 확인했고, 실제 GPU 또는 Isaac 시험은 아니다.

| 종류 | 수 | 증거 |
|---|---:|---|
| 17r 입력 변조 | 12 | `test_17r_mutants.log` |
| 17s 코드 변이 | 6/6 CAUGHT | `test_17s_code_mutants/code_mutants.json` · 정상/변이 개별 로그 |
| 17t 신규 코드 변이 | 3/3 CAUGHT | `test_17t_code_mutants/code_mutants.json` · 정상/변이 개별 로그 |

17s 6종의 실제 변이는 원본 `loaded_iter` 조건, wall 집행, 승인 claim 충돌, retry 0 허용, byte-only 원인 코드, 공통 allowlist 조건이다. 모두 안전 기능 비활성화 변이라고 부르지 않는다. 17r 입력 변조 12종은 코드 변이 9종에 합산하지 않았다.

첫 묶음 `evidence_17t/run_20261015_010221_176804`는 17r 연결 시험의 고아 자식 구간에서 멈춰 최종 분모에 넣지 않았다. 소유권 불명 자식이 자연 종료한 뒤에도 보류 PID 기록이 남는 문제가 원인이었다. 진행 중이던 직접 띄운 시험을 중단하고 보류 PID의 소멸/zombie 확인 때만 해제하도록 수정했다. 이후 단독 `test_17r_e.py`와 위 최종 묶음이 통과했다. 시험 출력의 `UNOWNED UNKNOWN`은 관찰 시점의 보수적 보류이며, 자식 자연 종료 확인 뒤 lease가 풀린다.

## 후보 변경 해시

아래 해시는 17t 시작본과 최종 후보의 바이트 SHA256이다. 빈 시작본은 신규 파일이다.

| 파일 | 17s 시작본 | 17t 후보 |
|---|---|---|
| `cmdr_eval_driver_s1043.py` | `236e79b26f883454feb08496a3d841b8ed76c71fdf7078a2a81b359ff0b1a303` | `553740512e026abf1a81b21049a644a68a28e5540bac60708ca68809ee041cc3` |
| `s1043_manifest.py` | `58bf719ae8817d7417784249aa288a83b2e9a038ddea70336c7e7927ef5a2a24` | `4f6cfc485e708c5995e9a2b431f204321292e772f7d0be3cdb51424c5e2f76d4` |
| `test_17r_b.py` | `8b6ee6a1b0c7e56c4ed103a7774c89d1c7c39ce0f4f029ea06ad25d2955782b8` | `8deadf04a35064d0ae52f2633604758e4ac3617d189a90bffe3fc45b3cf19419` |
| `test_17r_d.py` | `9d4225953c633098e7bc0383970c579511d3a97e1bb76b97fb7e799d6bb6b26e` | `cbc7bc63625baa57755c691fc0017ea93c8d39d0ba5891615dbbb39828d85172` |
| `test_17r_e.py` | `c743eb607c8db5140736ab2d2d39aad18b7878855cda173ca0e912920309c760` | `d4063ef82adb467fc3425a62bce94e4197d2d5211d289750561fe2a0505829bb` |
| `test_17s_diagnostic.py` | `6bb36658f05ca4a00c35db8c6c6a6aad48f9ff068bb46110c1a2b6cffa87dc8d` | `53ebdf5404a990620918283d53f22140a760ec5649ecab2459b9d08ae9a08969` |
| `test_17s_original.py` | `34fc45137c6e350f5cfcb303b4eefa74754acf7b32c771a7ad994c25d70c676d` | `fd4381849ff2b42a408fcf19c0138a8b19139b6fa5b10e5221b3004187de4995` |
| `run_all_17t.py` | 신규 | `d03d663ed0c8d5916aba22d32b4fb8ede7f5a9bc6422d80293d27e1291158c25` |
| `test_17t_approval.py` | 신규 | `09967e3932b9d1bd7a858ee665c7846e3408404587f6f646e632ff7221ab355e` |
| `test_17t_code_mutants.py` | 신규 | `ea9dab1dd5e44ffb923bfe81c8b99aa019267ce87c964ddf3056566a6ddb33d5` |
| `test_17t_diagnostic_contract.py` | 신규 | `dab4a4ba232e69b83a80003e978a56fcace034f9de2e3409ae4f5a980f63cce2` |
| `test_17t_fingerprint.py` | 신규 | `b70db275aaf29898133c2b6cfb044ca542692b98d0b2573fec894fd2d9b32654` |
| `test_17t_ownership.py` | 신규 | `49a327fd2014a0d9a48aa1e6e8f382722c508bb6ba1e548bd17fde7ec4b08656` |

## 한계와 필요한 결정

`test_17s_original.py`는 실제 q 원본 meta와 결과를 읽되 slot, `log_done`, `usd_check`, `py_traceback`을 가상화했다. 원본 실제 로그·USD·traceback 관문 통과 근거는 아니다. `test_17t_fingerprint.py`도 같은 주변 관문을 가상화하되 실제 원본 결과의 바이트 복사본을 사용한다. `test_17r_e.py`의 진단 `validate`·`fingerprint`는 성공 함수로 교체되고, `test_17s_runtime.py`의 guarded 실행 일부는 gate·preflight를 CPU fixture로 대체한다. 각 시험에서 실제로 검증한 층위만 근거로 삼는다.

PID 소유권은 관찰된 부모의 식별 시각을 다시 확인하는 방식이다. 부모 식별이 불가능한 채 관찰된 자식은 보류하지만, 관찰되기 전에 재부모화된 자식은 발견하지 못할 수 있다. 모든 Windows 프로세스 생성·종료 경주를 폐쇄했다고 주장하지 않는다. 더 강한 소유 경계가 필요하면 Windows Job Object로 자식 생명주기를 묶거나 프로세스 핸들을 직접 보유하는 별도 후보가 있다. Job Object는 Isaac/Kit 손자, 기존 Job 중첩, 종료 정책과 충돌 가능성이 있어 별도 CPU·운영 검증이 필요하다. 이번 후보에는 구현하지 않았다.

실제 GPU 진단과 A 45회, 물리 UUID·메모리 free/peak, 실제 slot v3·guard·isolate·Kit 연쇄, 다른 모든 실행기의 공통 lease 참여, 공통 경로 배치, 실제 PID 재사용 경주는 **미확인**이다. 팀장 결정은 **UNDECIDED**: GPU 배정·독점 시간창, 참가 실행기 범위, 시작 마감, launch·retry·wall 상한, 종료 유예·부분 결과 처리, 원본 반복, 재기동 범위, 비교 통과선, 공통 경로 배치. 현재 CPU fixture의 숫자와 규칙은 승인값이 아니다. GPU 기동 허용으로 해석하지 않는다.
