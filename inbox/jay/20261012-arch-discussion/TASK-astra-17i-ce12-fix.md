> 분류: A/평가 · ASTRA 의뢰 17i · 같은 시험지 (CE12) 승인 관문 고침 검증
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 01:12
> 근거: VERIFY-astra-17f.md §4.2 ~ §4.5 · 하위 작업 보고 (01:02) · `night-tools-20261013/ce12/` (이번에 다시 고정) · lead 재실행 job tmp `ce12fix/`
> 요지: 17f 가 APPROVED 채택 전에 고치라고 한 세 결함 (대상 대조 · 실행 당시 출처 · 마지막 관측 전환) 과 실제 기록에서 난 dims 오류를 고친 판이 그 결함을 실제로 막는지, 그리고 이 관문으로 CTS r2 기록을 승인해도 되는지 판정해 달라
> 상태: 의뢰 (17g 다음 차례)

# ASTRA 17i · CE12 승인 관문 고침

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. 하위 작업과 lead 의 보고를 맞다고 가정하지 마십시오. 17h 의 기준 (시험은 예정 대비 실행 · skip · hold · 환경 · 기대값의 근거까지) 을 이 판정에도 적용해 주십시오.

## 1. 대상

- 코드: `night-tools-20261013/ce12/` (SHA256SUMS.txt 를 lead 가 01:15 에 다시 만듦 · 실행본 `C:/isaac/ext/go2_rl_robotlab/_eval/ce12/` 와 바이트가 같음 · r2 승인용 묶음 `CODE_BUNDLE_r2.txt` 는 ce12 일곱 파일과 slot v3 · isolate v3 · gpu_guard). 바뀐 파일: compare_native.py · validate_dump.py · run_dump.py · cells.py · dump_native_cts.py · dump_native_v2.py · test_adapters.py · test_run_dump.py · mutate_adapters.py · mutate_run_dump.py · README.
- 하위 작업 보고 요지 (원문은 lead 가 받은 보고 · 아래는 lead 가 옮긴 것):
  - 실제 기록 (`out_ce12/native/cts_e1_m20000/` · 00:25) 의 대조: 관측 policy 329,400 칸 · single_obs 32,940 칸 · joint target 8,640 칸 · last action 8,784 칸 최대 차 0 · CPU 재계산 action 최대 2.15e-6 (step 2 · env 6 · RR_calf_joint) · reset 뒤 env 1 · 6 action 1.91e-6 · 1.67e-6 · 전환 뒤 env 0 action 1.43e-6 (20 step). 보고서 `compare_report_20261014-005010.json`.
  - dims 오류 원인: 기록기가 numpy 정수를 `json.dump(default=str)` 로 적어 policy · single_obs dims 가 문자열. 대조기는 숫자 문자열을 읽게, 기록기는 int 로 적게 고침. 실제 기록 사본 시험 T23 · VA-real.
  - 17f 4.2: stamp 에 승인 대상 (which · tag · attempt · 정규화 체크포인트 경로와 sha256 · model) · 재확인은 모두 같아야 유효 (VA-ck-target).
  - 17f 4.3: run.json `provenance` · `provenance_end` (기록기 · adapter · cells · 실행기 · slot · isolate · guard) · 실행 중 변경이면 87 (RT13) · 승인 A9 는 실행 당시 해시가 모두 있고 옛 칸과 모순 없고 실행 중 불변이고 승인 대상 코드 (`--code_bundle` 또는 지금 파일) 와 같아야 통과.
  - 17f 4.4: switch_step 1..T-1 (실행기 · 기록기 · 승인 A2 같은 규칙) · reset 뒤 · 전환 뒤 action step 수 · 0 이면 A7 · A8 보류 · miss None 은 미측정.
  - 이 기록의 승인: 수집 22 · A1 ~ A8 통과 · **A9 실패 → REJECTED** (guard 해시 미기록 · 기록 뒤 run_dump · cells · dump_native_cts 수정).
  - 설계와 다른 곳: 출처 연결을 「승인 시점 파일 해시」 에서 「실행 당시 해시 = 승인 대상 코드」 로 바꿈.

## 2. lead 가 다시 잰 것 (01:03 ~ 01:15 · isaac311-moects · CUDA_VISIBLE_DEVICES=-1)

| 항목 | 결과 |
|---|---|
| test_adapters.py | 23/23 PASS · exit 0 · PASS 가 아닌 줄 없음 |
| test_run_dump.py | 132/132 PASS · exit 0 · PASS 가 아닌 줄 없음 (skip · hold 문자열은 시험 이름 VA-pending 뿐) |
| mutate_adapters.py | 24/24 CAUGHT · exit 0 |
| mutate_run_dump.py | 65/65 CAUGHT · exit 0 |
| 시험 전후 | ce12 12 파일 해시 그대로 · 변이 사본 남지 않음 |

## 3. lead 가 하려는 것

- 위 판으로 해시를 고정하고 GPU 1 에서 CTS 짧은 기록을 새 tag `cts_e1_m20000_r2` 로 다시 받는다 (README 「lead 가 돌릴 명령」 · reset 1,6@30 · 전환 0@40 fwd03 · dry-run 먼저). 기동 안전에 걸린 부분 (v3 registry · 같은 변환 잠금 · slot v3 · isolate v3) 은 17f 가 본 판 그대로라서 17f §4.5 의 「짧은 진단 기록」 범위로 본다. **r2 결과의 APPROVED 채택은 이 17i 판정 뒤에만 한다.**
- 17i 가 허용하면: r2 승인 → v2 같은 규격 기록 (expect 0) → 양쪽 native 정합성 뒤 공통 세계 비교 (17f §4.5 의 5).

## 4. 물음

1. 4.2 · 4.3 · 4.4 의 각 반례 (17f 가 쓴 그대로) 를 고친 판이 실제로 막는가. 시험 · 변이가 그 반례를 잡는가, 구현을 복제한 시험인가.
2. 「실행 당시 해시 = 승인 대상 코드」 로 바꾼 설계가 맞나. 기록 뒤 무해한 수정 (예: 시험 파일) 까지 REJECTED 가 되는 범위는 적절한가. `--code_bundle` 의 신뢰 근거.
3. dims 같은 형식 차이가 다시 숨지 않게 한 T23 · VA-real 이 충분한가 (실제 기록 하나에 묶인 시험의 한계 포함).
4. r2 를 위 3 절대로 띄우는 것과, r2 를 이 관문으로 승인하는 것이 각각 허용되는가. v2 로 넘어가는 조건.
5. 허용 오차 1e-6 · 1e-4 와 「미확인」 목록 (v2 기록 0 · 자연 종료 reset 0 · 경계 clip · height miss · guard 의 실제 여유 검사 · 17f §3 의 v2 registry 읽기 전용 대조) 이 결과 보고에서 빠지지 않는가.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17i.md` 한 파일. 첫 줄은 한 문장 판정.
- 표기: 확인됨 · 추정 · 미확인. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out*` · `handover_*` · `handover-1635` · `slot/` 에는 쓰지 마십시오. em dash 를 쓰지 마십시오.
