> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: verifier-lx · 2026-11-11
> 근거: 팀장 19:38 원장 `7121e0188cf1cbe558704764227e306e6097149f` · lead 의뢰 · Refs #555
> 요지: EX-42 자체 20,000회 예산 선언·단계 상한·쉬운 종류 하한·M 복귀 계약·E1 연장 승인을 반영하고 승인 SHA를 재고정한다.
> 상태: 승인·prep 및 E1 승인 소비 검사 변경 · CPU 검증 · 실제 실행 파일 변경 없음

# 19:38 결정 반영

| 결정 | 반영 | 소비 범위 |
|---|---|---|
| EX-42 자체 20,000회 | prep `training_budget.basis=ex42_new_updates`, `maximum_updates=20000`, M 포함·연장은 남은 예산 안 | 전체 예산의 선언. 기존 materialize는 호출자가 전달한 `budget_limit/used/basis`를 사용하므로 runner가 이 계약에 맞춰 입력해야 한다 |
| E3·E4·E6b 상한 | prep와 해당 승인 `scope.maximum_updates`를 각각 4000·3000·3000으로 대조 | 기존 단계 표 소비자가 읽는 값. 각 `scope_amendment`에 새 원장 신원을 별도로 남겨 원 승인 13:07 신원도 보존 |
| E4·E6b 쉬운 종류 1.5% | `terrain.k_ladder.kind_floor=0.015`와 결정 SHA. 기존 숫자는 이미 0.015라 미결 주석을 확정 근거로 교체 | 기존 K 사다리 소비자 경로. 다른 종류 비율은 변경하지 않음 |
| E1 연장 +500 × 2 | `extension_authorized=true`, HOLD·1000 이후·500씩 2회·총 상한 2000의 `extension_contract` | E1 validator가 새 원장 SHA와 정확한 계약일 때만 허용. 기본 scope는 1000 유지. L+ 승인이나 다음 단계 승인을 추가하지 않음 |
| M은 들어간 단계로 복귀 | prep `branch_contract.return_to=source_stage`, 승인 `exit.return_to` 유지 | 실제 `branch_origin_stage_id`·`return_stage_id`·부모 SHA는 null 유지 |
| M 회차 계산 | `m_updates_count_toward_source_maximum=false`, `m_updates_count_toward_ex42_budget=true` | 원 단계 최대에는 제외·전체 예산에는 포함하는 계약 |
| M 1000회 소진 | `on_exhausted=notify_and_return_to_source_stage`, 지도 끔 0.3 유지, `source_window_counter_after_return=restart_two_windows`, 새 창 2개 | M의 `enabled=false`, `consumer_status=pending`은 유지. 아직 없는 실제 분기·복귀 소비자를 완료로 표시하지 않음 |

E1F부터 뒤 단계의 첫 점검 최소 250회와 HOLD 연장 간격·횟수는 그대로다. 다른 상한을 20,000에 맞추려고 임의로 늘리지 않았다. 수정 뒤 E0~E6b 기본 상한 합은 M 제외 16,000회, M 기본 500회를 한 번 넣으면 16,500회다. 이는 단계 표 합산이며 EX-41 T0-prime bridge는 이 합에서 제외했다. 20,000은 공유 예산 상한으로 기록했고 모든 단계 연장을 무조건 더해도 된다는 뜻이 아니다.

## 승인 SHA와 과거 실행 보존

- 원 승인 SHA: `7e9f72da0e708a36f3b44c3560414f5d77fc33fedb1129ccc4ac99c76473c98d`.
- 새 승인 SHA: `e00f2a564c39fabd9de260ae9594455e2d5b0f44503fd020e213cb96b6dad483`. prep `stage_zero.approval_sha256`를 이 바이트 해시로 재고정했다.
- E1 최초 진입 결정 `7ef023f5`와 전체 단계 결정 `2b94ea58`는 보존했다. 이번 변경 신원은 `teamlead-2026-11-11-1938-ex42-budget-m-floor-e1-extension`이다.
- 옛 고정 E1 plan/approvals를 수정하지 않았다. 옛 `extension_authorized=false`는 여전히 검사를 통과하며 그 칸으로 연장이 열리지는 않는다. 실제 재개에 새 승인 쌍을 사용하는 절차와 원 plan SHA 계보 연결은 runner가 확인해야 한다.
- D44 도달 정의는 미결이므로 D44 설정·판정 코드는 수정하지 않았다. M 실제 복귀·전체 회차 누적·남은 예산 소진 소비자는 이 PR의 구현 범위가 아니다.

## 검증

새 결정 시험을 먼저 실행해 수정 전 11 실패를 확인했다. 수정 후 새 계약 11개는 통과했다. 옛 승인 false 허용, 원장 SHA·조건·횟수·상한·증분을 다시 해시 고정해도 잘못된 연장은 거절하는 반례를 포함한다. 새 계약 검사를 제거한 사본은 해당 거절 시험 7개가 모두 `DID NOT RAISE`로 실패했다.

기존 회귀시험에서 옛 상한·미승인 기대값을 새 원장 값으로 고쳤다. 과거 고정 source plan 시험은 extension=false였던 당시 승인 바이트를 별도 fixture로 구성해 보존했다. handoff 시험은 1000회 HOLD의 1250 경계 계속, FAIL·결측의 연장 거절, 2000회 소진 알림, 잘못된 연장 증거 거절을 확인한다.

CPU 원출력·제거본은 `/home/jay/mai/tmp/verifier-lx/decision-1938-1111/`에 있다. GPU·Kit·실제 자식 학습 기동은 하지 않았다. 최종 원출력 `final.log`: **202 passed in 59.71s**, 실패·skip 없음. 승인·단계표·회차·E1 진입·materialize·K 사다리·handoff·이어 가기 표적 11개 시험 파일을 실행했다. 제거본 `mutant.log`: 7 failed, 4 deselected (의도한 관문 제거를 모두 검출). `git diff --check` 통과, 수정 생산 코드와 새 시험 pyflakes 0. 기존 handoff 시험 파일의 pytest fixture import 경고는 이번 변경 전부터 있어 손대지 않았다.

최종 prep SHA는 `97735c66968701ff54473fe2fe3e00419f24389f655e1a522280760627893d94`다. 승인·prep 반영 범위는 완료이며, 실제 예산 누적과 M 복귀 소비자는 남은 실행 경계다.

## Reviewer 후속: DR 설치 소비자와 낡은 거절 시험

`ex41_startup._authorized_initial_dr_scale`이 E1 증명에서 `extension_authorized is False`만 받던 경로를 직접 재현했다. 실제 승인 validator가 반환한 새 true 증명으로 수정 전 `test_dr_scale_one_is_authorized_by_the_real_e1_cell_and_only_by_it`가 실패했다. DR 소비자는 과거 false 증명을 계속 받고, true는 기본 상한 1000 및 원장 `7121e018`의 HOLD·1000 이후·500씩 2회·최대 2000 계약이 정확히 일치할 때만 받는다. scope의 기본 상한을 연장 총상한으로 바꾸는 입력도 거절한다. 다른 단계와 EX-41 0.5 경로는 변경하지 않았다.

scoped-auto의 옛 `extension_authorized=True` 거절 시험은 이미 true인 승인 값을 다시 넣는 무효 반례였다. `extension_contract=None`으로 바꿔 계약 없는 true를 거절하는 시험으로 수정했다. DR 소비자 시험에는 과거 false 허용과 계약 결측·원장·조건·증분·횟수·상한 변경 거절을 추가했다.

표적 두 파일은 **57 passed in 10.10s**. 옛 false-only 조건으로 되돌린 제거본과 계약 대조를 삭제한 제거본은 각각 실제 승인 소비 시험에서 1 failed로 검출했다. 파일을 바꾼 채 운영 경로를 실행하지 않고 시험 프로세스 안 함수만 치환했다. CPU 원출력은 같은 scratch의 `reviewer-red.log`, `reviewer-targeted.log`, `reviewer-mutant-old.log`, `reviewer-mutant-unchecked.log`에 보존했다.

전체 EX-42 CPU 파일 `foothold_s2/tests/test_ex42*_cpu.py`를 CUDA 숨김으로 실행한 최종 원출력 `reviewer-full.log`: **1096 passed, 3 skipped in 301.03s (0:05:01)**, rc 0. skipped 세 건을 통과로 세지 않았다. `git diff --check`와 수정 Python 세 파일 pyflakes도 통과했다. 실제 GPU/Kit 재개는 실행하지 않았고, 승인·prep 바이트와 해시는 이번 후속에서 변경하지 않았다.
