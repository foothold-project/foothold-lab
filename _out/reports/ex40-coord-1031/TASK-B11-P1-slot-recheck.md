> 분류: 검증 의뢰
> 작성: analyst · 2026-10-31 02:31
> 근거: verifier r4 §9 · runner b5bca3b561293dded80e0209fb84eeae0fc5b807
> 요지: 기존 P1 누락 슬롯 고침과 그 재개 영향만 한 차례 대조한다.
> 상태: B11 지적분 재확인 · B12/B13 대기 · B14 금지

# B11 P1 누락 슬롯 지적분 확인

R6/R15/R19/M14/M24/M02 적용. 기존 여섯 막음의 같은 고침 묶음이다. 새 전체 검토를 하지 않는다. 대상은 C:/mai/wt/foothold-lab/runner-ex40-b11-all-fixes 의 b5bca3b561293dded80e0209fb84eeae0fc5b807, analyst가 clean과 CPU 원출력 34 passed in 9.52s를 읽었다. 변경은 ex40_supervisor.py와 관련 시험 및 보고다.

기존 §9의 실제 stage_reports published=8, 실제 함수 호출, 중복 발신 없음, H1~H3/P2/P3 및 최종31개 완료의 닫힘은 보존한다. 다음만 정상과 반례를 같은 실제 함수로 확인하고 VERIFY-EX40-B11-1031.md에 후속 절을 더한다.

1. r4 m5550 정상은 consumed, m5250 checkpoint+state+ledger 동시 누락은 pending/unknown이어야 한다. score만 누락, HOLD, SHA 충돌도 그대로 거부한다.
2. m5250이 이전 segment의 검증된 checkpoint/manifest/score/eval receipt로 남아 있으면 정상 consumed이고 재평가/재발신이 없어야 한다. 정규31개와 분리 segment 정상도 같은 경로로 유지.
3. 이미 고침 의뢰에 포함된 정상 재개: 앞 segment가 m1500까지 정상 평가, 재개 segment는 m1550 또는 m1600에서 종료해 아직 새 stride m1750 전이다. 앞 segment의 m1500 평가를 인정하여 정상 재개를 허용해야 한다. current run에 m1500 파일이 없다는 이유만으로 막으면 기존 P1 안의 미완료다. b5b의 target_digest가 현 segment만 찾는지 확인. 앞 segment 자료도 없거나 충돌이면 대기.
4. fake children/sender만 대체하고 stage_reports/score/receipt 소비는 실제 함수를 쓴다. old r4 파일은 보존하고 별도 r5 출력에 저장. 실제 GPU, Kit, 외부 발송 금지.

결과는 정상/반례 입력·기대·실제·출처를 짧게. 남은 막음 수를 명시한다. 끝 보고는 기존 orca orchestration status로 analyst와 lead에, 터미널 입력으로 보고하지 않는다. B11 전체0 전에는 Kit를 열지 않는다.
