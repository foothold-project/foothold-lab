> 분류: CPU 회귀 검증
> 작성: verifier-lx · 2026-11-11
> 근거: REVIEW-5d4dbf33 고침 1 · lead 12:23 의뢰 · PR644 5d4dbf33 원본 CPU 모듈
> 요지: 빈 칸을 채운 정상 사본을 먼저 통과시킨 뒤 네 가드를 각각 깨뜨리는 시험 7개 추가
> 상태: 확인됨 · GPU/Kit 미실행 · 승인 및 운영 코드 변경 없음

# PR644 채운 승인 사본 가드 시험

`test_ex42_filled_approval_guards_cpu.py`만 새 시험으로 넣었다. 부모 · landing 메시 · 깃발 기준선 · M0~M3 · 팀장 식별을 시험용 값으로 채우고 정상 승인 검사 통과를 먼저 확인한다. 그 뒤 한 항목만 바꾸고 승인 파일 pin도 다시 계산하므로, 앞쪽의 빈 칸 또는 SHA 오류가 뒤쪽 결함을 가리지 않는다. 시험용 값은 실제 승인 파일에 쓰지 않는다.

| 반례 | 제거본 결과 |
|---|---|
| F4: 깃발 0.11 · 전진 0.16, 총합 1.0 유지 | 몫 대조 제거 시 `1 failed, 6 passed` |
| F7: approver=worker, E1F/E2 각각 | 신원 대조 제거 시 `2 failed, 5 passed` |
| F8: E2 M0~M3 SHA null 또는 64자리 0 | 영수증 대조 제거 시 `2 failed, 5 passed` |
| F9: 해당 단계 DR=0.8, E1F/E2 각각 | DR 대조 제거 시 `2 failed, 5 passed` |

원본은 `7 passed in 0.44s`. 네 제거본 모두 `DID NOT RAISE`로 실패하여 목표 가드 결함을 잡았다. `git archive 5d4dbf33`의 curriculum 사본에서 CPU Python으로 실행했다. 처음 최소 사본은 EX41 부모 YAML이 없어 실패했으며 curriculum 입력 전체를 포함한 뒤 위 결과를 얻었다. 임시 제거본은 원래 바이트로 복구했다.

원출력과 재현 스크립트: `/home/jay/mai/tmp/verifier-lx/pr644-guards-1111/{cpu.log,mutations.py,mutations.json,F4_shares.log,F7_approver.log,F8_m0_m3.log,F9_dr.log}`. 이번 결과는 승인 파서 회귀 검증이며 E1F 학습·노출 소비 검증은 별도다. Refs #555.
