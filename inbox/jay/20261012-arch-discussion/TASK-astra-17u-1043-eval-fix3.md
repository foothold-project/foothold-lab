> 분류: A/평가 · ASTRA 의뢰 17u · 1043 쌍 평가 후보 17t 고침 검증과 진단 단계 승인 조건 재판정
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 01:50
> 근거: VERIFY-astra-17t.md 전문 · 작업자 E 의 고침 보고 `REPORT-17t.md` (사본 `night-tools-20261013/cmdr1043_eval_cand_17t/`) · lead 재실행 (`evidence_17t_run_014830_lead/`, `lead_rerun/`) · #550 댓글
> 요지: 17t 가 찾은 기동 차단 결함 셋(PID 재사용 때 무관한 자식 종료 · 승인 필드 값 검사 부재 · 필수 지문 누락을 valid 로 남김)과 보강 항목을 작업자 E 가 CPU 로 고쳤다고 보고한다. 이 고침이 17t 의 반례를 실제로 닫는지, 새 결함은 없는지, 지금 상태에서 「제한된 진단 기술 승인」 을 발급할 수 있는지(없다면 정확히 무엇이 남았는지)를 판정해 달라. 팀장 결정값과 lead 측정값의 마지막 구분, 승인 발급 순서까지
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 팀장 결정값 전부 UNDECIDED · 팀장은 이 값들에 아직 답하지 않았음 · 이 의뢰는 기동 허용을 구하지만 값이 채워지기 전에는 승인 json 을 발급하지 말 것)

# ASTRA 17u

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. 작업자 E 의 보고와 lead 요약을 평소보다 더 신중하게 원자료(코드 · 로그 · 반례)로 독립 대조해 주십시오. 17j ~ 17t 의 기준(시험이 실제 기동 경로를 타는지 · 변이는 정상 소스의 같은 시험 통과와 의도한 실패 위치 · 입력 변조와 코드 변이를 섞어 세지 않기 · 변이의 «실제로 바뀐 의미» 를 정확히 쓰기 · 문서와 코드의 차이 · 장치 전체 값 vs 몫 · 「X 없음」 은 기록으로)을 적용해 주십시오.

**분량:** `VERIFY-astra-17u.md` 한 파일. 첫 줄 한 문장 판정, 질문마다 「판정 · 근거 · 남길 미확인」. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out/` 은 읽기만 · `slot/` · `handover_*` · `handover-1635` 에는 쓰지 마십시오. em dash 금지.

## 1. 대상과 보고

작업자 E (Codex Worker · gpt-6-sol · 검증자 아님) 의 17t 고침 후보. 바이트 고정은 `night-tools-20261013/cmdr1043_eval_cand_17t/SHA256SUMS.txt` (37 줄) 이고 작업자 쪽 전체 목록은 `CAND-17T-SHA256SUMS.txt` (165 줄 · 목록 파일 SHA256 `dfdb76470970d22ce821aeebffe9d640d975d0c9e96979b3ea94f083c8c353e0` · `__pycache__` 의 pyc 한 개와 `mutant_*` · `work/` 포함이라 저장소 사본에는 넣지 않았다). 17t 가 본 판은 `cmdr1043_eval_cand_17s/` 이고 작업자가 고치기 전에 `codexE/cand_17t_base/` 로 159 개 파일을 보존했다.

6 개 핵심 파일 해시(17t): `s1043_manifest.py` `4f6cfc485e708c5995e9a2b431f204321292e772f7d0be3cdb51424c5e2f76d4` · `cmdr_eval_driver_s1043.py` `553740512e026abf1a81b21049a644a68a28e5540bac60708ca68809ee041cc3` · `manifest_s1043.json` `837fbe07b4240b80dcc9bbb269534ed2f076eff0899c325b77eaa00843909413`(17s 와 동일) · `cmdr_bundle_compare_s1043.py` `77c5e5dd…`(동일) · `cmdr_post_s1043.py` `9b2565c4…`(동일) · `frozen_exec_s1043.py` `eaee9668…`(동일). 17s 대비 바뀐 기존 파일 일곱(driver · `s1043_manifest.py` · `test_17r_b` · `test_17r_d` · `test_17r_e` · `test_17s_diagnostic` · `test_17s_original`), 새 파일 여섯(`run_all_17t.py` · `test_17t_approval.py` · `test_17t_code_mutants.py` · `test_17t_diagnostic_contract.py` · `test_17t_fingerprint.py` · `test_17t_ownership.py`).

작업자 주장(`REPORT-17t.md`):
1. **PID 소유권:** `wait_child_tree` 는 관찰된 부모의 `(pid, create_time)` 이 현재도 같고 실행 중일 때만 새 자식을 등록. 부모 불일치 · 소멸 · 자식 접근 거부 · 생성 시각 오류는 `unowned_unknown` 으로 두고 신호 없이 lease 유지. 불명 PID 가 자연 종료하거나 사라진 뒤에는 보류 목록에서 해제(소멸 / zombie 확인 때만). 가짜 psutil 표 시험에서 100→110 정상 손자 정리 · 110 PID 재사용 뒤 300 미등록 · 무신호 · 보류 · 접근 거부와 부모 소멸 보류가 통과. **작업자 한계:** 관찰되기 전에 재부모화된 자식은 발견하지 못할 수 있음, Windows Job Object 같은 더 강한 소유 경계는 구현하지 않음(검토 의견만).
2. **승인 B 값 검사:** `comparison_pass_rule` 허용 집합은 `semantic_and_json_bytes_and_traj_bytes` 하나, launch 검증과 driver 판정이 같은 승인값 사용. `approval_id` · `attempt` 1~64자, `log_name` 1~50자 영문 · 숫자 · 밑줄 · 하이픈, 예약어(`undecided` · `none` · `null` · `true` · `false` · `unknown` · `nan`) 대소문자 무관 거절. `restart_scope=single_start_no_reuse` 만. `termination_policy` 는 키 집합 · 양의 유한 종료 유예 · `partial_result=held` 만. 실제 `require_files=True` 정상 승인과 30 개 반례 통과.
3. **필수 지문:** `diagnostic_record` 가 `valid` 이전에 필수 지문 · 배치와 cells / traj SHA 를 확인하고 계산 예외는 `held` + `why`. 기본 원본 · 반복 원본 모두. 실제 원본 q 결과 meta(SHA256 `4c4bed83…bb093`)의 바이트 복사본으로 정상 valid → `env_origins.npy` 제거 후 validate 통과 · record held → 복원 후 valid.
4. **공통 지문 대조(P2):** pairing 2종 · terrain mesh/origins · env origins · N/T/cells · obs shapes · UUID · layout · traj0 를 orig 와 small / default / repeat 사이에서 비교, evaluator source · PhysX small buffer · eval changes 는 의도한 차이 목록. 불일치는 `held_common_fingerprint`.
5. **비용 · 반복 사유:** `wall_s_scope=last_try_only`, `try_wall_s_sum` · `startup_allocated_s` · `non_try_wall_s` · `total_wall_s` · `startup_wall_s` · `attempt_total_wall_s`. 반복은 `repeat_not_needed` / `repeat_not_approved` / `repeat_ran`.
6. **allowlist:** `registry` · `convert_lock` · `run_lease` 세 키에 한해 source_eval 내부 정확한 key+path 만 허용, 와일드카드 · 디렉터리 · 잘못된 확장자 · 미등록 경로 거절.

작업자 시험: 15 개 스크립트 모두 exit 0 (`evidence_17t_run_010804_worker/summary.json` · 합계 109.77 초 · 17r 6 + 17s 4 + 17t 5). **입력 변조 12 종(17r) · 17s 코드 변이 6 종 · 17t 신규 코드 변이 3 종을 따로 센다**고 보고(`code_mutants.json`). 17s 6 종의 실제 변이 의미는 원본 `loaded_iter` 조건 · wall 집행 · 승인 claim 충돌 · retry 0 허용 · byte-only 원인 코드 · 공통 allowlist 조건이며 모두 「안전 기능 비활성화」 라고 부르지 않는다고 적었다. 17t 신규 3 종: 부모 식별 조건 제거 · 지원 비교 규칙 검사 제거 · 필수 지문 보류 조건 제거. 첫 묶음(`run_20261015_010221_176804`)은 17r 연결 시험의 고아 자식 구간에서 멈춰 분모에서 뺐다고 적었다(원인: 소유권 불명 자식이 자연 종료한 뒤에도 보류 PID 기록이 남음 → 소멸 / zombie 확인 때만 해제하도록 수정).
**작업자가 적은 한계(그대로 인용):** `test_17s_original` 은 실제 q 원본 meta 와 결과를 읽되 slot · `log_done` · `usd_check` · `py_traceback` 을 가상화 / `test_17t_fingerprint` 도 같은 주변 관문을 가상화하되 실제 원본 결과의 바이트 복사본 사용 / `test_17r_e` 의 진단 `validate` · `fingerprint` 는 성공 함수로 교체 / `test_17s_runtime` 의 guarded 실행 일부는 gate · preflight 를 CPU fixture 로 대체. 실제 GPU 진단 · A 45 회 · 물리 UUID · free / peak · 실제 slot v3 · guard · isolate · Kit 연쇄 · 다른 모든 실행기의 공통 lease 참여 · 공통 경로 배치 · 실제 PID 재사용 경주는 미확인.

## 2. lead 재실행

**실행(10/15 01:48:30 ~ 01:50:19 · lead):** 작업자의 `run_all_17t.py` 를 새 run-id `run_20261015_014830_16564` 로 한 번 돌렸다(`CUDA_VISIBLE_DEVICES=-1` · 해석기 `isaac311-moects` · `-B -u`). 열다섯 시험 모두 종료 0(`test_17r_b` 3.81 s · `c` 1.20 · `d` 0.42 · `e` 25.94 · `post_cli` 3.62 · `mutants` 0.31 · `test_17s_original` 0.34 · `runtime` 8.22 · `diagnostic` 0.42 · `code_mutants` 34.94 · `test_17t_ownership` 0.31 · `fingerprint` 0.41 · `approval` 12.69 · `diagnostic_contract` 0.80 · `code_mutants` 15.09). 로그는 `evidence_17t_run_014830_lead/`(저장소 사본) · 스크립트와 출력은 `lead_rerun/`. 실행 전과 후에 작업자 `cand/` 165 파일을 작업자 목록(CR 제거 후)과 `sha256sum -c` 로 대조해 165/165 일치했고 재실행이 후보를 바꾸지 않았다.
**코드 변이:** `code_mutants.json` 의 17s 6 건과 17t 3 건 모두 `caught: true`, 정상 종료 0, 변이 종료 1, `failed` 와 `want` 문구 일치. 17t 3 건의 변이 로그 끝에서 `AssertionError: PID reuse child never signalled`(`test_17t_ownership.py` 16 행 `check`) · `comparison_pass_rule 0 rejected`(`test_17t_approval.py` 27 행) · `missing fingerprint held`(`test_17t_fingerprint.py` 26 행) 이 해당 시험 소스의 `check(...)` 에서 난 것을 눈으로 확인했다. 변이가 정확히 그 검사만 바꾼 것인지는 코드 대조하지 않았다.
**사본:** 저장소 `night-tools-20261013/cmdr1043_eval_cand_17t/` 는 작업자 `cand/` 에서 코드 · 시험 · 가짜 slot · manifest · 패치 · 보고서를 복사한 것이고(파일 단위 `cmp` 불일치 0) `SHA256SUMS.txt` 37 줄을 새로 만들었다.
**lead 가 하지 않은 것:** 고침 코드의 줄 단위 검토 · PID 재사용 반례를 ASTRA 방식으로 직접 재현 · 변이가 의도한 검사만 바꿨는지 코드 대조 · 새 공통 지문 대조가 정상 실행을 오탐하지 않는지(의도한 차이 목록의 완전성) · 소유 경계 방안(Job Object 등)의 평가 · 실제 slot v3 / guard / isolate 연쇄 · 승인 JSON 발급 · 어떤 UNDECIDED 값도 채우지 않음.

## 3. 물음

1. **17t 의 기동 차단 결함 셋이 닫혔는가.** (a) PID 재사용: ASTRA 반례(루트 100 · 중간 110 종료 후 PID 재사용 · 새 자식 300)가 막히는지, `(pid, create_time)` 부모 식별이 충분한지, 불명 PID 의 「자연 종료 / 소멸 시 보류 해제」가 새 경주(해제 직후 PID 재사용 · zombie)를 만들지 않는지, lease 가 영영 안 풀리거나 너무 일찍 풀리는 경우, 접근 거부 · 부모 소멸 · 관찰 전 재부모화 경계, 그리고 작업자가 말한 「관찰 전 재부모화는 못 찾음」이 진단 승인의 수용 가능한 잔여 위험인지 아니면 Job Object 같은 OS 소유 경계가 필수인지. (b) 값 검사: 허용 규칙과 적용 규칙이 같은지(driver 가 승인값을 읽어 쓰는지), 예약어 · 길이 · 문자 집합 · `termination_policy` 구조 검사에 우회가 있는지, 승인 digest 에 새 필드가 들어가는 구조가 그대로인지. (c) 지문: 정상 대조군 valid · 지문 파일 누락 held · 복원 valid 가 실제 코드 경로를 타는지, 기본과 반복에 같은 조건인지, 최종 완료 조건이 누락을 보는지. 새로 생긴 결함이 있는지.
2. **시험 신뢰 범위(17t 2 절 재판정).** 새 코드 변이 3 종과 17s 6 종이 실제로 어떤 의미를 바꾸는지(「안전 기능 비활성화」 라고 부를 수 있는 것은 어느 것인지) · 입력 변조 12 종과 섞지 않고 센 것이 맞는지 · 정상 소스가 같은 시험을 통과하는지 · 가상화된 주변 관문(`log_done` · `usd_check` · `py_traceback` · slot · gate · preflight · `validate` / `fingerprint` 교체)이 아직 어디에 남아 있는지 · 시험이 못 보는 것(실제 GPU 의 slot · guard · isolate · Kit 연쇄 · 물리 버퍼 · peak · 모든 운영 실행기의 공통 lease 사용).
3. **진단 계약 재판정.** 공통 지문 대조의 항목 목록과 「의도한 차이」 목록이 맞는지(오탐 · 누락), `held_common_fingerprint` 와 의미 / JSON / traj 비교가 독립 판정으로 남는지, 비용 · 반복 사유 보고가 정직한지, 세 실행 분리와 A 자동 진행 금지가 유지되는지.
4. **UNDECIDED 와 승인 json 발급 조건(최종).** 이번 후보 바이트가 ASTRA 가 보기에 「제한된 진단 기술 승인」 의 **대상으로 충분한지**(충분하다면 어떤 조건에서 발급 가능하다고 말할 수 있는지, 남은 결함이 있다면 정확히 무엇인지). 22 키 승인 B 의 필드별 책임(lead 측정 / 팀장 결정 / ASTRA 판단)과 각 값의 허용 범위. **팀장은 17t 4 절의 권고값을 그대로 쓸 수 있는가**(launch 3 · retry 0 · 원본 반복 false · `max_wall_s` 1200~1800 · `terminate_grace_s` 5~10 · `single_start_no_reuse` · 통과선 하나 · 20~30 분 작업창 · GPU 0 또는 1 중 하나)와 팀장이 실제로 정해야 하는 마지막 항목 목록. lead 가 측정해야 하는 것(물리 UUID / index · 여유 · 판 · 경로 · 고정 코드 해시 · 입력 38 개 · SAME 번들 · 참가 실행기의 canonical lock / lease / registry)을 **순서대로** 적어 달라. 그리고 ASTRA 가 승인 json 을 발급하는 정확한 순서(팀장 값 → lead 측정 → contract 동결 → 비교 보고 동결 → 코드 다섯 해시 → B 검토 → 승인 파일 + 외부 digest).
5. **배치와 공통 경로.** 17t 권고(기존 검증 경로를 정확한 allowlist 로 재사용)를 구체화해 달라: `_eval` 의 슬롯 코드(`slot/isaac_slot_v3.py` 등)를 읽고 registry · convert_lock · run_lease 의 canonical 경로 후보와 참가 실행기(Isaac 실행 도구들)가 실제로 그 경로를 쓰는지를 가를 수 있는지. 반영 직후 CPU 재검 · 기동 직전 확인 목록 · 중단 조건 · 보고 문구. 진단 한 묶음(Isaac 세 번)의 예상 소요와 A 45 회 별도 승인 전에 필요한 것(launch 53 · 54).
6. **견적 갱신.** 17t 6 절의 1.5 ~ 3.5 시간을 이번 진행(작업자 E 가 00:50 ~ 01:14 에 고침, lead 재실행 01:50)으로 갱신. 지금부터 GPU 진단 시작까지의 현실적인 단계와 병목. 특히 **팀장 결정 · lead 측정 · 배치를 수정 검증과 병행할 수 있는 부분**과 순서를 지켜야 하는 부분.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17u.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
