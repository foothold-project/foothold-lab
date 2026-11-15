> 분류: A/평가 · ASTRA 의뢰 17l · 미경험 v6 (17g 의 A 고침) 검증과 full 승인 여부
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 05:18
> 근거: VERIFY-astra-17g.md 2 · 4 절 · night-tools-20261013/uncr_v6/ (사본 · SHA256SUMS · 작업자 보고 lead_rerun/REPORT.md · 새 manifest · 새 옛 묶음 재검 보고) · lead 재실행 job tmp codexw/leadA/
> 요지: 17g 가 지적한 P1 (GPU 대기 뒤 코드 재검사 공백 · 잠금 대기 뒤 동결) · 환경 지문 · 새 manifest 를 고친 v6 가 그 반례를 실제로 막는지, 그리고 full 75 실행을 승인해도 되는지 (승인이면 승인 json) 판정해 달라
> 상태: 의뢰 (17k 다음)

# ASTRA 17l · 미경험 v6

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. lead 와 작업자의 보고 · 재실행 숫자 · 조건 해석을 평소보다 더 신중하게 원자료로 독립 대조해 주십시오. 17h · 17j 의 기준 (변이는 정상 소스에서 같은 시험이 통과함과 의도한 실패 위치까지 · 엉뚱한 실패를 검출로 세지 않기) 을 적용해 주십시오.

## 1. 대상 (해시 고정 · `night-tools-20261013/uncr_v6/SHA256SUMS.txt`)

| 파일 | sha256 앞 16 자 |
|---|---|
| `unseen_driver_cmdr_v6.py` | c0114134210475a8 |
| `uncr_revalidate_v3.py` | 3bd8ae4dc6453527 |
| `test_uncr_v6.py` | a87d84a4e195266e |
| `mutate_uncr_v6.py` | e9cf763965f47029 |
| `frozen_exec.py` | df111075449485c3 |
| 새 manifest 파일 `manifest_v6-20261014-051705.json` | 7d48a74261481bb1 |
| 새 옛 묶음 재검 보고 `revalidate-v6-20261014-051704.json` | ec69b80978b708fe |

(실행본은 `C:/isaac/ext/go2_rl_robotlab/_eval/` 와 바이트가 같음을 lead 가 5 개 파일 모두 대조.) 17g 가 검증한 v5 (`unseen_driver_cmdr_v5.py` df0cf1e0a1df · `uncr_revalidate_v2.py` 089574adfa10 · `test_uncr_v5.py` 983d7b434634 · `mutate_uncr_v5.py` ff1ef3fdac09) 는 고치지 않았고 해시가 그대로다 (lead 가 재확인).

작성자는 **Codex Worker (gpt-6-sol)** 이고 검증자가 아닙니다. 작업서 `TASK-codex-worker-17g-fix.md` 의 A 부분. 작업자 보고 `uncr_v6/lead_rerun/REPORT.md` (02:44 사고 기록 + 재개 뒤 갱신본).

## 2. 먼저 알려야 할 일 (사고)

작업자는 처음 (02:42) 합성 시험을 돌리다 복사한 v6 의 출력 루트가 실제 `_eval/out_uncr_v5` 를 가리켜 가짜 시험이 거기에 4 개 파일을 썼다 (`driver_v5.json` 은 lead 의 00:43 manifest 단계 기록이 덮임 · `HALT_v5.json` · `uncr_par_gap_fwd05.slot.json` · `.guard.json` 추가). `manifest_v5.json` 은 그대로. lead 가 보호 기준선 대조로 확인했고 지우지 않고 뒀다 (증거). 작업자는 즉시 멈춰 보고했고 03:57 에 격리 조건을 달아 재개했다. 재개 뒤에는 `out_uncr_v5` 에 쓰지 않았다 (lead 대조). v5 는 17g 가 승인하지 않았고 v6 (새 루트 `out_uncr_v6`) 로 대체된다.

## 3. 작업자 보고 요지와 lead 재실행

- A1: `run_one()` 이 GPU 대기와 시도 폴더 보존 뒤 STOP · 마감 · 해시를 다시 보고 자식을 호출. 대조군 자식 1 회 `ok` · 대기 중 해시 변경 자식 0 회 `frozen` (ASTRA 17g 2.1 재현을 실제 `run_one` 으로).
- A2: slot 의 첫 자식이 `frozen_exec.py`: 잠금 획득 뒤 등록 manifest 의 코드 · 입력을 재해시, 변경이면 자식 0 회 · **종료 92** · 같으면 아래 자식 종료 코드를 그대로 전달 (대조군은 7 전달). v6 은 92 를 보호 오류로 HALT (재시도 없음). 92 는 기존 코드에서 안 보임 (`rg`).
- A3: 환경 지문 (executable · python 전체 버전 · numpy 버전과 경로 · BLAS 이름과 버전 · OpenBLAS 커널 · `OPENBLAS_CORETYPE` · `MKL_CBWR` · `MKL_ENABLE_INSTRUCTIONS` · CPU 이름 · 판정 코드 해시) 를 재검 보고 · stamp · manifest 에 기록하고 full · post 의 재계산 대조 전에 검증된 지문 (python 3.11.15 · numpy 1.26.0 · OpenBLAS 0.3.23.dev · 커널 Cooperlake) 과 비교해 다르면 `[post-env]` 한 줄과 **종료 3**. 실제 `out_uncr` 읽기 전용 재검 valid 23 · `OPENBLAS_CORETYPE=Nehalem` 하위 프로세스는 hold 15 가 아니라 `[post-env] 다른 칸: openblas_kernel, OPENBLAS_CORETYPE` 와 종료 3 · 비교 필드 13 개 각각 변조 거절.
- A4: 새 manifest `code_manifest_sha256 = 91d35be9c6a7f65bba573d414b76aa359f58567924bb4bbf501e7c04c83c8e52` · 등록 일치 · 새 실행 75 · 옛 `ac09c264...` 재사용 안 함. **설계 한계 (작업자 스스로 밝힘):** 자기 파일의 최종 해시를 자기 소스 상수에 넣을 수 없어 v6 새 코드 다섯 파일은 모듈 적재 때 해시를 등록하는 동적 방식이다 (full 의 승인 파일은 이 해시를 포함한 manifest 해시에 묶임 · `frozen_exec` 가 잠금 뒤 다시 읽음).
- A5: 합성 시험 72 (기존 50 + 새 22) · 변이 44 (기존 38 + 새 6). 작업자는 처음 시험이 D02 에서 중단 (사고) · 재개 뒤 D05b 1 건 실패 (주입 호출 수 2 → 3 바로잡음) · P03 의도한 실패 (`revalidate_v5_*` → `revalidate_v6_*`) 를 남겼다.
- **lead 재실행 (04:58 ~ 05:16 · isaac311-moects · `UNCR_TEST_SKIP_REAL=1` · `CUDA_VISIBLE_DEVICES=-1`):** 합성 시험 72 PASS · `FAILS []` · 종료 0 · 변이 44/44 CAUGHT (각 줄이 `failed [...] want [...]` 로 의도한 시험 이름과 일치) · 종료 0. 원로그 `uncr_v6/lead_rerun/test.txt` · `mut.txt`. **실제 `out_uncr` 의 v3 재검기 재검 (lead 가 05:17 에 직접):** runs valid 23 · diag valid 21 · diag 칸 valid 7 · 묶음 해시 `e55975172405901a0178a8e2bd3541ce7e13b118d0a9ab723fb6028d69ef2b58` (17e 가 검토한 값과 같음) · frozen_ok True · 새 보고 `out_uncr_v6/reval/20261014-051704/revalidate.json`. **새 manifest (lead 가 05:17 에 실제 루트로):** 등록 일치 · 새 실행 75 · `code_manifest_sha256` 91d35be9... (작업자 폴더 결과와 같음) · 파일 `out_uncr_v6/manifest_v6.json` 7d48a742...
- 보호 대조: v5 4 개 원본 해시 그대로 · 작업자 재개 뒤 `out_uncr_v5` 변화 없음 · `out_uncr` · `out_ce12` · branch · s2 · handover 변화 없음.
- **lead 가 안 한 것:** full 실행 · 실제 Isaac · 실제 slot 잠금 경계 · 실제 GPU 대기.

## 4. 물음

1. **A1 · A2 가 17g 2.1 의 반례를 실제로 막나.** `frozen_exec.py` 가 slot 이 잠금을 얻은 직후 첫 자식으로 실제로 들어가는 명령 구성인가 (코드로), 그 사이에 바뀐 파일을 실제로 거절하나. 대기 중 변경 반례 · 잠금 대기 뒤 변경 반례를 실제 `run_one()` 과 `frozen_exec.py` 로.
2. **A3 환경 지문.** 검증된 지문 상수의 근거 (한 해석기에서의 로컬 조회) 가 충분한가. CPU 이름 · 커널이 지문에 들어 있어 다른 기계 · Ubuntu 이전 뒤에는 어떻게 되나. 「바이트 검사를 느슨하게 하지 않고 환경을 막는」 설계가 맞나. 17g 4 절의 요구 (실제 `sys.executable` · python 전체 버전 · numpy 판과 경로 · 판정 코드 해시를 기록하고 검증 환경과 다르면 보류) 를 충족하나.
3. **A4 동적 등록의 한계.** 작업자가 밝힌 설계 (모듈 적재 때 해시 등록) 가 「동결」 의 의미를 해치나. 승인 JSON 이 묶는 것이 무엇이고 무엇이 안 묶이나.
4. **full 75 실행 승인 여부.** 승인이면 아래 형식의 승인 JSON 을 `inbox/jay/20261012-arch-discussion/night-tools-20261013/uncr_v6/approval-astra-17l.json` 한 파일로 써 주십시오 (승인하지 않으면 만들지 마십시오): `kind` `uncr_v6_full_approval` · `decision` `approve` · `by` `ASTRA 17l` · `t` 시각 · `reval_sha256` `ec69b80978b708fed73d6a8a4025e5693cde21dfd9aaf9debf9f46fb5bf2cd82` (위 새 재검 보고 파일의 전체 해시) · `old_bundle_sha256` `e55975172405901a0178a8e2bd3541ce7e13b118d0a9ab723fb6028d69ef2b58` · `code_manifest_sha256` `91d35be9c6a7f65bba573d414b76aa359f58567924bb4bbf501e7c04c83c8e52` · `reuse_partial` `no` · `new_runs` 75 (manifest 의 `approval_template` 과 같은 칸). 허용이면 lead 가 돌릴 명령 · deadline · 사전 확인 (17j 처럼 GPU 1 의 실제 UUID · 여유 · 다른 Isaac 과 겹치지 않기 · 상대 로그 직접 읽기) · 중단 조건 · 한 번에 하나의 Isaac 으로 RAND smoke 와의 순서를 적어 주십시오.
5. 결과 보고에 남길 범위 문장과 지표 구분 (17g 5 절) 이 v6 표에 들어가나.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17l.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
- 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out*` · `handover_*` · `handover-1635` · `slot/` 에는 쓰지 마십시오. em dash 를 쓰지 마십시오.
