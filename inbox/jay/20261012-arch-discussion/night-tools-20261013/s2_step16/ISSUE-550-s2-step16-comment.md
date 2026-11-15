# #550 댓글 초안 · S2 step16
> 분류: A/정책학습
> 작성: sol · 2026-10-16
> 근거: `REPORT-s2-step16.md` · `evidence_s2_step9/step16_release/summary.json` · `S2-STEP16-SHA256SUMS.txt`
> 요지: ASTRA 17ai 평가·발 광선 결함 수정본과 CPU 증거를 lead 재실행용으로 전달한다.
> 상태: 미게시 초안

step16 사본 `codexE/s2_step16`을 인도합니다. 평가 첫 reset 전 `_q_yaw` 설정과 생성 실패 close 1회, 체크포인트 update·plan·encoder·parent 신원, 8회 USD 생성자 진입 상한, 환경/cache 잔존 HOLD, case별 USD/ray/pre-reset 영수증을 보강했습니다. 발 광선은 실제 reset ID 세대 연결, 정답표 직선 비용 3·대각 비용 2·좁은 cardinal 비용 1, RewardManager 실출력 대조, 학습 0 전용 단회 Kit 드라이버·감독 계약을 추가했습니다.

CPU 직접 시험은 정상 29/29, 반례·변이 13/13 지정 첫 FAIL입니다. B 전체 깨끗한 복사본 회귀는 52/52 파일 통과, 정상 파일 PASS 라벨 356, 변이 파일 CAUGHT 라벨 84이며 교차 라벨은 별도입니다. 상세 증거는 `REPORT-s2-step16.md`와 `evidence_s2_step9/step16_release/summary.json`에 있습니다. GPU/Isaac은 실행하지 않았고 `_eval`은 읽기만 했습니다. 실제 Kit 물리·USD·RewardManager 결과는 미확인입니다. 기존 평가 요청의 신원 핀과 기존 훈련 manifest의 새 USD 래퍼 SHA는 lead가 재봉인해야 합니다. 팀장 결정값과 승인 JSON은 만들지 않았습니다.
