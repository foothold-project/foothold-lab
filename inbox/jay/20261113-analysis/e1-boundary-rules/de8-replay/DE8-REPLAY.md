# E1 m250·m500 새 승인표 재계산
> 분류: A/평가
> 작성: analyst-lx · 2026-11-13 23:39
> 근거: 원장 de8a3b7f · 5f2e7c3b · 7ba9f2be · P1 JSON/NPZ · tfevents 바이트 사본
> 요지: 과거 경계는 기록용 재계산, 운영 결과와 처방은 변경하지 않음
> 상태: CPU 실측 · C1 추가 Kit 칸 미측정

| 경계 | 기존 규칙 | 끔 생존 | 64 미만 칸 | lr 바닥/창 | 진단 KL >0.02/창 |
|---|---|---|---|---|---|
| m250 | KEEP | PASS (21칸) | 없음 | 193/250 (77.2%) | 67/250 |
| m500 | KEEP | PASS (21칸) | map64/back1.0 63/64 | 195/250 (78.0%) | 88/250 |

| 경계·레벨·속도 | GT R | PRED R | 끔 R (기록) |
|---|---|---|---|
| m250 L0 0.1 | 0.446703 | 0.407424 | 0.371471 |
| m250 L0 0.2 | 0.821468 | 0.814927 | 0.786532 |
| m250 L5 0.1 | 0.422422 | 0.408622 | 0.388723 |
| m250 L5 0.2 | 0.782957 | 0.809524 | 0.782877 |
| m500 L0 0.1 | 0.311974 | 0.333607 | 0.252084 |
| m500 L0 0.2 | 0.841593 | 0.856888 | 0.821001 |
| m500 L5 0.1 | 0.311124 | 0.344467 | 0.246257 |
| m500 L5 0.2 | 0.825911 | 0.827397 | 0.810177 |

확인됨: source reader가 checkpoint·seed·P1 SHA·원자료 값을 대조했다. 지도 끔의 R은 생존 조건에 쓰지 않는다.
미측정: C1의 고정 L3/L6/L9와 끝점 새 Kit 칸. 이를 기존 저속 칸으로 대체하지 않는다.
진단 KL은 scheduler의 실제 미니배치 KL이 아니다. 곡선 숫자는 경고·기록이며 설정 변경이 아니다.
GT 통과·PRED 미달은 지각 경로 점검 후보, GT 미달은 정책·과제 점검 후보. 원인 확정이 아니다.

기존 규칙의 m500 KEEP과 실제 다음 처방은 별개다. lead는 23:07 원장의 한 경계 큰 하락 예외로 b2 slow_track 0→0.2를 적용했다. 도구는 이 결정을 취소하거나 소급 바꾸지 않는다.

m250: /home/jay/mai/tmp/analyst/de8-approved-replay-v2/m250/report.json · SHA `b93ca3a939e4e8646855aefecb512fe7e8a5fe928d5d9c72bc2697373a379657`
원자료 오류: []. C1: ['C1 consumer code unavailable; use --c1-code-root with a fixed reviewed copy'].
진단 분류: {'둘 다 통과': 19, '정책·과제 점검': 17}.

m500: /home/jay/mai/tmp/analyst/de8-approved-replay-v2/m500/report.json · SHA `6b99c7c252c03d4bb2fbc2073a6353146fb950ff015ac14a31dc869eb3dc2fb0`
원자료 오류: []. C1: ['C1 consumer code unavailable; use --c1-code-root with a fixed reviewed copy'].
진단 분류: {'둘 다 통과': 20, '정책·과제 점검': 16}.
