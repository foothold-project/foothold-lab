> 분류: 기존 EX-40 B11 P1 고침 묶음
> 작성: analyst · 2026-10-31 02:36
> 근거: b5bca3b5 · verifier r5 results.json · split-trace.json · 실제 소비 코드
> 요지: 필요한 슬롯 검사는 통과하지만 목표와 보고 영수증의 이전 segment 출처 연결이 남았다.
> 상태: P1 잔여1 · B12/B13 대기 · B14 금지

# P1 정상 segment 출처 마무리

R6/R15/R19/M14/M24/M02 적용. 새로운 범위가 아니라 TASK-P1-missing-slot.md의 정상 재개 항목이다. 기존 b5bca3b561293dded80e0209fb84eeae0fc5b807을 보존하고 runner-ex40-b11-all-fixes의 후속 커밋 하나에서 아래 두 소비 자리를 함께 고친다. 코드·시험·보고만, GPU/Kit/실제 외부 발신 금지.

analyst가 verifier의 `_out/ex40-b11-r5/results.json`, `split-trace.json`과 코드190~242행을 읽었다. 누락5250은pending, 정상5550/정상31은consumed, 이전segment5250도consumed이며 중복발송0이다. 이 닫힘은 보존한다. 남은 것은 다음 정상 입력들이다.

| 정상 입력 | 현재 결과 | 실패 자리 |
|---|---|---|
| 앞segment m500~1500 실제 checkpoint/score/receipt가 모두 verified, 새segment m1550 또는m1600에서 멈춤 | 둘 다pending | target_update1500의 `_manifest_digest(run,1500)`가 현재segment만 읽어None. 과거1500 SHA는 실제 존재 |
| m500~3000은 이전segment, m3250~8000은현재segment에 둔31개 정상 입력 | `_score_until_checkpoint`는pending, completion은done/evaluated31 | 슬롯31개verified와 stage_reports8개done 뒤 `_stage_report_delivery_ok` 인자의 SHA를 `_manifest_digest(run,n)`로 얻어 이전segment의1500/3000을None로 줌 |

요구: 목표 회차와 각 단계 보고의 SHA·source run도 이미 검증한 슬롯/ledger의 **실제 원자료 출처**를 따라야 한다. 현재segment에 없다는 이유만으로 정상 과거자료를 거부하지 않는다. 반대로 실제 파일·manifest·score·receipt가 없거나 바이트가 충돌하면 계속pending/unknown이다. 보고 JSON·배송 영수증·lab feed의 SHA 결박은 유지하고 검사 자체를 빼지 않는다. 새segment의 같은 회차가 다른 SHA인 충돌도 기존대로 거부한다.

한 CPU 묶음에서 실제 stage_reports/실제 소비 함수를 쓰고 child·sender만 가짜로 둔다. 위 두 정상 입력은consumed이고 재소비 때 재평가·재발송0, 이전target 누락/충돌은거부, m5250 파일+state+ledger 동시누락거부, 정상31개·HOLD·SHA회귀는 보존한다. r5 원자료는 읽기만 하고 수정하지 않는다. 검토를 쉽게 하도록 새 정상 재개 두 입력을 회귀시험에 넣는다.

보고에 정확한 새HEAD·clean·CPU원출력·바뀐 파일만 적는다. 동일P1 지적분 재확인 뒤에만 B11전체0을 판단한다. 기존 다른 닫힘은 다시 열지 않는다.
