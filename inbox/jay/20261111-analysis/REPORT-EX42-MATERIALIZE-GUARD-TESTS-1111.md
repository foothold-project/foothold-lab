# materialize 승인 · 범위 거절 시험 보강

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: verifier-lx · 2026-11-11
> 근거: reviewer REVIEW-a5d2ed35.md v0.2 · lead 15:58 후속 의뢰
> 요지: 미승인/비활성 단계와 범위 확대를 직접 겨누는 8개 CPU 시험
> 상태: 확인됨. 구현 코드 변경 없음, GPU·Kit 미사용

통합 `4efda640` 위에 시험 파일 하나와 이 기록만 더했다. 회차 정정 PR #684와 별도 PR이다. reviewer의 생존8종 가운데 지정된 승인 여부와 범위 확대 두 검사를 대상으로 했다. 나머지6종을 닫았다는 뜻은 아니다.

기존 반례는 승인 템플릿과 source plan이 같은 파일이었다. 승인 값을 바꾸고 plan 해시를 다시 고정해도 두 rank 노출 로그의 승인 SHA가 이전 값으로 남아, 겨누려던 거절문을 없애도 다른 SHA 검사에서 먼저 거절할 수 있었다. 새 입력은 실제 런타임 계약처럼 원 단계 source plan과 다음 단계 template을 분리한다. 원 gate·원 plan·두 rank 로그를 그대로 맞추고 template의 승인 값과 pin만 바꾼다. 정상 대조가 실제 materialize 발행에 성공하는지도 확인한다.

| 입력 | 정상 코드 | 지정 guard 제거본 |
|---|---|---|
| 분리한 source/template의 정상 승인 | materialized | 정상 대조 |
| approved=false · enabled=false · approved 문자열 true · 정수1 | target 승인 거절, out/lock 없음 | 네 시험 FAIL |
| scope 최대1250 · 1500 · 20000, 등록된 범위750 | scope 확대 거절, out/lock 없음 | 세 시험 FAIL |

CPU 원출력: `/home/jay/mai/tmp/verifier-lx/materialize-guard-tests-1111/control.log`, `41 passed in 17.55s`(기존33 + 새8). 제거본 스크립트 `mutate.py`, 결과 `mutations.json`, 개별 로그 `approval.log` · `scope.log`. 제거본은 자기 scratch 사본에서만 실행했고 원 구현은 그대로다.

정확한 거절 단계와 이유까지 대조한다. guard 제거 후 후단 승인 검사도 일부 입력을 거절할 수 있으므로 제거본에서 실제 무승인 학습이 시작됐다는 주장이 아니다. 해당 선행 거절문이 조용히 사라지는 것을 새 시험이 잡는다는 뜻이다.

회차 정정 #684 `529f753b`의 변경 코드·설정과 합친 scratch에서도 새8개 `8 passed in 2.86s`(`with684.log`). pyflakes 0, diff-check 0.

Refs #555.
