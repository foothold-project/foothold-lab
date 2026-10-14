> 분류: A/평가 · ASTRA 의뢰 17t · 1043 쌍 평가 후보 17s 고침 검증과 진단 단계 승인 조건 재판정
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 23:50
> 근거: VERIFY-astra-17s.md 전문 · 작업자 E 의 고침 보고 `REPORT-17s.md` (사본 `night-tools-20261013/cmdr1043_eval_cand_17s/`) · lead 재실행 (`evidence_17s_run_234848_lead/`, `lead_rerun/`) · #550 댓글
> 요지: 17s 가 찾은 새 결함 넷(원본 q 결과 거절 · 벽시계 상한 미집행 · 승인 예산 결박 · 재시도 0)과 시험 신뢰 범위 지적을 작업자 E 가 CPU 로 고쳤다고 보고한다. 이 고침이 17s 의 반례를 실제로 닫는지, 새 결함은 없는지, 바뀐 승인 스키마(22 키)와 단회 승인 설계가 「진단 한 묶음(Isaac 세 번)」 에 맞는지 판정해 달라. 팀장 결정이 필요한 값과 lead 측정값, 승인 json 발급 조건을 다시 가르는 것까지
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 팀장 결정값 전부 UNDECIDED · 이 의뢰는 기동 허용을 구하지만 값이 채워지기 전에는 승인 json 을 발급하지 말 것)

# ASTRA 17t

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. 작업자 E 의 보고와 lead 요약을 평소보다 더 신중하게 원자료(코드 · 로그 · 반례)로 독립 대조해 주십시오. 17j ~ 17s 의 기준(시험이 실제 기동 경로를 타는지 · 변이는 정상 소스의 같은 시험 통과와 의도한 실패 위치 · 입력 변조와 코드 검사 끈 변이를 섞어 세지 않기 · 문서와 코드의 차이 · 장치 전체 값 vs 몫 · 「X 없음」 은 기록으로)을 적용해 주십시오.

**분량:** `VERIFY-astra-17t.md` 한 파일. 첫 줄 한 문장 판정, 질문마다 「판정 · 근거 · 남길 미확인」. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out/` 은 읽기만 · `slot/` · `handover_*` · `handover-1635` 에는 쓰지 마십시오. em dash 금지.

## 1. 대상과 보고

작업자 E (Codex Worker · gpt-6-sol · 검증자 아님) 의 17s 고침 후보. 바이트 고정은 `night-tools-20261013/cmdr1043_eval_cand_17s/SHA256SUMS.txt` (31 줄) 이고 작업자 쪽 전체 목록은 `CAND-17S-SHA256SUMS.txt` (159 줄 · 목록 파일 SHA256 `ac97c2a1a2068dfbfb8e8fa1fbb883cde207b59fb575ab7ce71ab54a57849db9` · 이 안에는 `__pycache__` 의 pyc 한 개와 `mutant_*` 18 개 · `work/` 가 포함돼 저장소 사본에는 넣지 않았다). 17s 가 본 판은 `cmdr1043_eval_cand_17r/` 이고 작업자가 고치기 전에 `codexE/cand_17s_base/` 로 154 개 파일을 보존했다(대조 불일치 0 이라고 보고).

6 개 핵심 파일 해시(17s): `s1043_manifest.py` `58bf719ae8817d7417784249aa288a83b2e9a038ddea70336c7e7927ef5a2a24` · `cmdr_bundle_compare_s1043.py` `77c5e5dd0798f7030b1259072c973d1bca38d9df9e58bcdce1a859887c906980`(17r 과 동일) · `cmdr_eval_driver_s1043.py` `236e79b26f883454feb08496a3d841b8ed76c71fdf7078a2a81b359ff0b1a303` · `cmdr_post_s1043.py` `9b2565c48946640aab3238cc1ed968f3a922eb758a93654a502b5571c2b22d59`(동일) · `frozen_exec_s1043.py` `eaee9668015d36ef2bde9ef52c4f3a419c38187e0a923c069ec755ba53daaa8e`(동일) · `manifest_s1043.json` `837fbe07b4240b80dcc9bbb269534ed2f076eff0899c325b77eaa00843909413`. 17r 대비 바뀐 기존 파일은 `build_manifest_s1043.py` · `cmdr_eval_driver_s1043.py` · `manifest_s1043.json` · `s1043_manifest.py` · `test_17r_b.py` · `test_17r_d.py` · `test_17r_e.py` 일곱, 새 파일은 `run_all_17s.py` · `test_17s_code_mutants.py` · `test_17s_diagnostic.py` · `test_17s_original.py` · `test_17s_runtime.py` 다섯 (보고 표에 해시).

작업자 주장(`REPORT-17s.md`): 17s 의 7 항목을 각각 고침.
1. 원본 q: `validate` 가 q 원본의 누락된 `loaded_iter` 만 허용, 명시된 잘못된 값 · checkpoint SHA · cmdr 누락은 거절. 진단 원본과 반복 원본에만 `need_iter=False`. 실제 원본 meta(SHA256 `4c4bed83…bb093`) 를 읽기 전용으로 확인.
2. 벽시계: `deadline_epoch` 는 시작 금지, `max_wall_s` 는 소유한 자식 트리의 실행 중 상한, STOP 도 같은 감시기. PID 생성 시각이 맞는 관찰 자식만 종료, 전체 종료 확인 전 lease 유지, rc 124/125 와 `held` 부분 결과.
3. 승인 예산: 승인 B 에 승인 ID · 실제 attempt · log · restart scope 를 묶음. `write_root/approval_ledger/<approval_id>/claim.json` 을 디렉터리 원자 생성으로 **단회 예약**. 충돌 · 중단 뒤에도 같은 승인을 재사용 못 함(`restart_scope=single_start_no_reuse`).
4. retry 0: launch · wall 은 양의 정수, retry 는 0 이상 정수. 승인 retry 0 에서 실제 `guarded` launch 가 한 번.
5. byte-only: `semantic_equal` · `json_sha_equal` · `traj_sha_equal` 별도 기록, JSON byte-only 는 `byte_only_json` 원인 코드. 세 값 모두 일치해야 완료인 보수 규칙 유지, 통과선은 UNDECIDED.
6. 보고 동등성: 기본 · 반복 · 실패 run 이 `diagnostic_record` 공통 필드(시간 · tries · preflight · 장치 전체 peak/여유 · fingerprint · buffer · 입력 해시 · reset). 없는 자료는 null, not_run / held_runs / failed_runs 분리.
7. 공통 경로: 기본은 `write_root` 내부만 허용, `deployment.common_write_allowlist` 의 key+exact path 에 한해 registry · convert_lock · run_lease 의 source_eval 경로 예외.

승인 B 스키마: 17r 의 키에 `approval_id` · `attempt` · `log_name` · `restart_scope` · `termination_policy` · `comparison_pass_rule` 6 개를 더해 정확히 22 키(보고 36 행). 그 값들(ID · attempt · log · scope · 종료 정책 · 통과선)은 manifest 에서 UNDECIDED 이고 `launch_errors` 가 기동을 막는다고 보고.

작업자 시험: 10 개 스크립트 모두 exit 0 (`evidence_17s_run_230924_worker/summary.json` · 시험 실행 합계 81.67 초). **입력 변조 12 종과 코드 검사를 끈 변이 6 종을 따로 센다**고 보고(`code_mutants.json` · 변이 소스 SHA256 · 정상 · 변이 종료 코드 · `failed` · `want`). 첫 실패(실제 원본 meta 시험의 slot 기록 파일 없음 · retry 0 변이의 복사 모듈 ROOT 위치로 NOT_CAUGHT)는 분모에서 빼고 보고서에 적었다고 함.
**작업자가 적은 한계(그대로 인용):** 실제 GPU 진단 · 물리 UUID · free/peak · 실제 slot v3 · guard · isolate · Kit 연쇄 · 공통 lease 를 다른 모든 실행기가 쓰는지 · 운영 경로의 allowlist 또는 write_root 적용은 미확인. 생성 시각 확인이 불가능하거나 접근이 막힌 관찰 자식은 신호를 보내지 않고 lease 를 계속 보유. 이미 부모가 사라진 뒤 처음 관찰된 자식 · PID 재사용 전체에 대한 보증은 아님. CPU fixture 의 종료 유예 0.2 ~ 0.5 초와 `held` 처리는 승인 결정값이 아님. 작업자가 띄운 옛 CPU 시험 프로세스(PID 175820)는 팀장 종료 확인 대기 중.

## 2. lead 재실행

**실행(10/14 23:48:48 ~ 23:50:07 · lead):** 작업자의 `run_all_17s.py` 를 새 run-id `run_20261014_234848_102912` 로 한 번 돌렸다(`CUDA_VISIBLE_DEVICES=-1` · 해석기 `isaac311-moects` · `-B -u`). 열 시험 모두 종료 0(`test_17r_b` 3.78 s · `c` 1.19 · `d` 0.44 · `e` 25.84 · `post_cli` 3.03 · `mutants` 0.30 · `test_17s_original` 0.36 · `runtime` 8.22 · `diagnostic` 0.39 · `code_mutants` 35.08). 로그는 `evidence_17s_run_234848_lead/`(저장소 사본) · 스크립트와 출력은 `lead_rerun/`. 실행 전과 후에 작업자 `cand/` 159 파일을 작업자 목록(CR 제거 후)과 `sha256sum -c` 로 대조해 159/159 일치했고 재실행이 후보를 바꾸지 않았다.
**코드 변이:** `code_mutants.json` 의 `records` 6 건 모두 `caught: true`, 정상 종료 0, 변이 종료 1, `failed` 와 `want` 문구 일치(`original q meta accepted` · `guarded wall returns nonzero held result` · `second start refused` · `retry zero approved` · `byte-only JSON reason` · `_eval slot without allowlist rejected`). lead 는 변이 로그 세 건(approval_ledger · retry_zero · common_allowlist)의 끝에서 `AssertionError: <label>` 이 시험 소스의 해당 `check(...)` 줄에서 난 것을 눈으로 확인했다. 입력 변조 12 종은 17r 시험 그대로이며 코드 변이 6 종과 합산하지 않는다.
**사본:** 저장소 `night-tools-20261013/cmdr1043_eval_cand_17s/` 는 작업자 `cand/` 에서 코드 · 시험 · 가짜 slot · manifest · 패치 · 보고서를 복사한 것이고(파일 단위 `cmp` 불일치 0) `SHA256SUMS.txt` 31 줄을 새로 만들었다. `mutant_*.py` 18 개 · `work/`(fixture 30 MB) · `reports/` · `__pycache__` 는 넣지 않았다(원본은 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/cand/` 에 그대로).
**lead 가 하지 않은 것:** 고침 코드의 줄 단위 검토 · 6 개 변이가 의도한 검사만 끈 것인지 코드 대조 · 17s 의 반례를 ASTRA 방식으로 직접 재현 · 소유 자식 트리 종료 로직의 PID 재사용 · 접근 거부 경계 시험 · 승인 장부의 동시 시작 경쟁을 독립 재현 · 실제 slot v3 / guard / isolate 연쇄 · 승인 JSON 발급 · 어떤 UNDECIDED 값도 채우지 않음.

## 3. 물음

1. **17s 의 새 결함 4 건이 닫혔는가.** (a) 원본 q 결과 검증: 실제 원본 meta 사본을 정상 입력으로 쓰는 시험이 `validate` 의 실제 경로를 타는지, 필드 유무 처리가 「원본 q 에 한정」 인지(iteration 검사를 통째로 끈 해결이 아닌지), checkpoint 해시 · 원본 소스 · cmdr 검사가 유지되는지. (b) 벽시계: 17s 의 반례(한도 2 초 · 4 초 자식)가 막히는지, 시작 금지와 강제 종료 구분, 종료 확인 전 lease 유지, 손자 · STOP, 그리고 「PID 생성 시각이 맞는 관찰 자식만 종료」 설계가 PID 재사용 · 접근 거부 · 관찰 전 사라진 자식에서 안전한지, 잘못된 프로세스를 죽일 위험은 없는지. (c) 승인 예산: attempt 만 바꾼 재사용 · 두 번째 시작 · 동시 시작이 막히는지, **단회 claim 이 「진단 한 묶음(Isaac 세 번 + 조건부 원본 반복)」 한 번의 승인에 맞는 설계인지**(한 승인 ID 로 세 번의 q 실행이 모두 한 프로세스에서 이어지는 것이 claim 하나로 충분한지, 중간 실패 · 재시도 · 원본 반복이 같은 claim 안에서 처리되는지), 충돌 · 중단 뒤 재사용 금지가 현실적인지(승인 한 번이 소진되면 재발급이 필요한 흐름). (d) retry 0. 새로 생긴 결함(예: 승인 digest 에 새 6 키가 실제로 들어가는지, 장부 경로가 write_root 밖으로 샐 수 있는지, allowlist 의 새 우회, 감시기가 정상 종료 자식을 오판)이 있는지.
2. **시험 신뢰 범위(17s 2 절 재판정).** 코드 검사를 끈 변이 6 종이 실제로 그 검사만 끈 것인지(변이 소스 차이를 보고 판정) · 입력 변조 12 종과 섞지 않고 센 것이 맞는지 · 정상 소스가 같은 시험을 통과하는지 · 실제 원본 meta 시험이 `validate` 의 실제 코드를 타는지(작업자가 slot 경계만 fixture 로 대체했다고 적음) · 그래도 `test_17r_e` 의 연결 시험이 validate · fingerprint 를 성공 함수로 교체한 한계는 여전한지 · 시험이 못 보는 것(GPU 의 slot · guard · isolate · Kit 연쇄 · 물리 버퍼 · peak · 모든 운영 실행기의 공통 lease 사용).
3. **진단 계약 재판정.** 세 별도 실행 · 단계 분리 · A 자동 진행 없음이 유지되는지. 정상 원본 결과가 이제 거절되지 않는지 · 비교 결과가 `semantic_equal` / `json_sha_equal` / `traj_sha_equal` 로 분리되고 byte-only 가 물리 비결정성으로 읽히지 않는지 · 반복 원본 · 실패 run 의 보고 항목이 기본 세 run 과 같은 수준인지. 통과선(`comparison_pass_rule`)을 UNDECIDED 로 승인 B 에 묶은 방식이 「성능을 본 뒤 판정선을 바꾸면 안 된다」 는 규칙을 지키는지.
4. **UNDECIDED 와 승인 json 발급 조건(갱신).** 22 키 승인 B 의 정확한 구조와 해시 대상을 다시 확정해 달라. 6 개 새 키(`approval_id` · `attempt` · `log_name` · `restart_scope` · `termination_policy` · `comparison_pass_rule`) 가운데 **누가(lead 측정 / 팀장 결정 / ASTRA 판단) 어떤 값을 채우는지** · 값 범위와 허용 후보. 팀장 결정값(GPU 배정 · 독점 시간창 · `deadline_epoch` 의미 · launch · retry · wall 상한 · 강제 종료 유예 · 부분 결과 처리 · 원본 반복 예산 · 재기동 범위 · 통과선 · 공통 경로 배치)에 대해 ASTRA 가 **권고하는 구체 값 범위**(팀장이 고를 수 있게). ASTRA 가 진단 승인 json 을 발급하는 조건과 순서(어떤 값이 채워지고 어떤 CPU · 측정이 통과한 뒤인지).
5. **배치와 첫 GPU 진단 순서(17s 5 절 갱신).** 17s 가 제안한 `candidate_dir=_eval/cmdr1043_eval_17s_fixed/` · `source_eval=_eval` · `write_root=_audit_cmdr1043/` 배치가 이번 후보(allowlist 포함)로 구체적으로 어떻게 되는지. 공통 lock · lease · registry 를 write_root 안에 둘지 기존 경로 allowlist 로 허용할지 ASTRA 의 권고. 반영 직후 CPU 재검 · 기동 직전 확인 목록 · 중단 조건 · 보고 문구. 진단 한 묶음의 예상 소요(Isaac 세 번)와 A 45 회 별도 승인 전에 필요한 것. A 의 launch 예산에 시작 시험 8 회 + 조건부 원본 반복 1 회 + A 45 회를 어떻게 넣을지.
6. **견적 갱신.** 17s 6 절의 1.75 ~ 4.5 시간(수정 1 ~ 3 + 재검 0.5 ~ 1 + 배치 · 측정 0.25 ~ 0.5)을 이번 진행(작업자 E 가 22:50 ~ 23:15 에 고침, lead 재실행 23:50)으로 갱신. 지금부터 GPU 진단 시작까지의 현실적인 단계와 각 병목(ASTRA 검증 · 팀장 결정 · lead 측정 · 배치).

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17t.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
