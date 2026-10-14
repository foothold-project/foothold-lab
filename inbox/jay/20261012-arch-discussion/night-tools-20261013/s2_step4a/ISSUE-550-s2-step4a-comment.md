> 분류: A/정책학습
> 작성: Codex Worker · 2026-10-15
> 근거: REPORT-s2-step4a.md · evidence_s2_step4a/run_20261015_0500_a1/summary.json
> 요지: 17v A 단계 CPU 중간 보고와 첫 GPU 접속 확인의 남은 보류 사유
> 상태: lead 게시용 초안 · 미게시

# S2 17v A 단계 CPU 중간 보고

17v P1 센서 packet 시점과 yaw 유한성, 8환경×256 step 접속 정답표, 0단계 전용 Job Object 감독기·단회 claim·상태·영수증·마감을 `codexE/s2_step4/` 사본에 구현했습니다. Isaac Lab 설치 소스의 미확인 호출 여섯은 `S2-17V-CONNECT-SOURCE.md`에 줄 번호로 대조했습니다.

새 A 묶음은 정상 7/7 exit 0, A 코드 변이 5/5가 정상 선통과 후 지정 첫 FAIL로 CAUGHT입니다. Windows Job Object의 suspended 배정과 시험용 CPU 자식 자연 종료도 확인했습니다. GPU·Isaac 실행 0, `_eval`·slot·guard·부모 수정 0입니다.

실제 충돌 mesh/숨은 plane, 고정 자세, Kit·driver 판, private sensor hook의 라이브 순서가 미확인이라 0단계 라이브 판정은 아직 HOLD입니다. 감독기의 세션 분리와 독립 hard deadline 감시, 다른 실행기의 UUID lease 참여도 미확인입니다. `REPORT-s2-step4a.md`의 질문을 ASTRA에 A 범위로 전달해 주세요. B 학습 사슬은 계속 작업 중입니다.
