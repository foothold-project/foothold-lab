# W58 500회 판단 사전 알림 도구

> 분류: C/운영 · 자동화
> 작성: runner · 2026-11-07
> 근거: lead 카드 W58(msg_81a704086e71), EX-41 저장본 및 완료 점수 산출물
> 요지: 저장본 시각과 완료 점수 소요시간의 중앙값으로 다음 500회 판단 시각과 30분 전 알림 문장을 계산한다
> 상태: CPU 확인 · 실제 발송 미실행

## 구현

foothold_s2/scripts/ex42_judgment_notice.py가 번호가 붙은 체크포인트의 수정 시각에서 최근 구간 회당 시간을 계산하고, iteration 및 체크포인트 경로가 맞는 완료 점수 JSON의 created_at에서 점수 소요시간을 계산한다. 두 시간 모두 최근 5개 표본 중앙값을 사용하며, 역사 재현용 --as-of-iteration은 미래 체크포인트와 점수 자료를 제외한다. 완료 점수 표본이 하나도 없으면 임의 기본값을 쓰지 않고 실패한다.

알림 시각은 예측 경계 30분 전이다. 출력 문장의 HH:MM은 점수 완료 예상 시각이며, 메시지 발송 또는 점수 평가 실행은 하지 않는다. 실제 EX-42에서는 실행 폴더의 main/ 체크포인트와 eval/scores/ 완료 점수를 지정하고, lead가 출력 문장을 발송 경로에 연결해야 한다.

## CPU 확인

실제 원자료:
- 학습: C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522
- 점수: C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/eval/scores
- 재현 기준: m5000 시각, 목표 m5500

예측은 회당 중앙값 27.108초, m5500 도착 2026-11-06 18:01:39 KST, 점수 중앙값 2690.8초, 판단 예정 18:46:30, 경계 30분 전 알림 예정 17:31:39였다. 저장본 실제 도착은 18:09:25로 예측보다 7분 46초 늦었고 score_5500 JSON created_at은 18:57:28.910 UTC, 즉 18:57:28.910 KST로 판단 예측보다 약 10분 59초 늦었다. 예측치는 일정 보장이 아니라 최근 중앙값에 기반한 안내값이다.

시험 명령:
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/test_ex42_judgment_notice_cpu.py -q --basetemp=D:/mai-tmp/runner/ex42-w58/pytest -p no:cacheprovider

결과: 3 passed. 포함 항목은 500회 다음 경계, 관측된 점수 시간 중앙값, 과거 컷오프의 미래자료 제외, 점수 자료 누락 시 실패, 알림 문장 형식이다. GPU, Kit, 학습 및 실제 발송은 실행하지 않았다.

운영 예시:
python -m foothold_s2.scripts.ex42_judgment_notice --checkpoint-dir <run>/main/<run-name> --score-dir <run>/eval/scores