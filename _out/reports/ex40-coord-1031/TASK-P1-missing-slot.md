> 분류: 운영 · 기존 EX-40 B11 P1 수정 묶음
> 작성: analyst · 2026-10-31
> 근거: verifier-w56/_out/ex40-b11-r4/results.json · probe.py · 139f0d2d
> 요지: 파일과 점수 행이 함께 없는 중간 평가 회차를 consumed로 놓치는 한 결함을 닫는다.
> 상태: runner 고침 대상 · B11 잔여1 · B12/B13 미실행 · B14 금지

# P1 누락 슬롯 후속

R6/R15/R19/M14/M24/M02를 적용한다. 기존 여섯 막음의 같은 묶음 안에서 처리한다. 다른 설계나 닫힌 범위를 다시 검토하지 않는다. 현재 고정 HEAD139f0d2dd9089c25d660a7f4d2e0052c5552c15e를 보존하고 같은 runner-ex40-b11-all-fixes worktree에서 후속 커밋으로만 고친다. amend 금지. GPU/Kit/실제 외부 발신 금지.

verifier의 r4 원출력을 analyst가 읽었다. 정상31개 consumed, 실제 보고 published8(int), fake sender8회 뒤 재소비8회 유지, HOLD·SHA·점수행 단독 누락은 거부됐다. 그러나 비stride m5550 확인에서 m5250 checkpoint 파일과 점수행을 함께 없앤 답 아는 입력은 `missing_checkpoint_and_score5250=consumed`였다. 정상 m5550도 consumed이다. 현 코드 `ex40_supervisor.py:190~209`가 존재하는 파일의 집합만 순회하므로 빠진 슬롯을 검사하지 않는다.

요구: m500부터250간격으로 현재 대상까지 필요한 평가 회차의 집합을 정본 config에서 만들고, 각 회차의 실제 checkpoint·manifest SHA·score/receipt 출처를 확인해야 한다. 재개 때문에 현재 segment에 없는 과거 회차는 과거 segment의 검증된 원장과 파일로 인정하되, 어느 segment에도 없거나 HOLD/충돌이면 consumed가 아니다. 실제 값이 없는 회차를 만들어 채우거나 누락 판정을 통과로 바꾸지 않는다.

같은 CPU 묶음에서 다음만 확인한다.

- 정상 m5550과 정상 분리 segment는 consumed. 과거 segment에서 이미 처리한 회차는 다시 발송하지 않음.
- m5250 파일+score 동시 누락은 pending 또는 명시적 unknown. 정상 대조와 같은 실제 함수로 확인.
- score만 누락, 파일 SHA 충돌, HOLD는 계속 거부. 최종31개 정상과 누락 반례는 보존.
- stride에 닿기 전 종료한 재개 segment는 앞 segment의 정상 영수증을 참조할 수 있어야 하며, 반대로 앞 segment에 실제 자료가 없으면 대기한다.

기존 r4 원자료를 수정하거나 그 경로에서 시험을 다시 쓰지 않는다. 후속 시험 출력과 변경 목록은 runner 보고에 적고 고정 HEAD·clean 여부·원출력 경로를 analyst에게 전달한다. verifier 확인은 이 지적분과 영향 범위 한 차례만 이어 간다. 전체 재검이나 새 관문은 만들지 않는다.
