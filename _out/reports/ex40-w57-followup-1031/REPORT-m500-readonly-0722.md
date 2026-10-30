> 분류: A/평가 · 실행 상태 점검
> 작성: analyst · 2026-10-31 07:22
> 근거: runner 관찰 원자료 · 실제 저장 폴더 · train_start_status.json · PID · nvidia-smi
> 요지: m500 미도착, 평가 시작 전이며 GPU1 평가 실행은 아직 미확인
> 상태: 읽기 점검 완료 · m500 실제 도착 후 장치 대조 대기

# EX-40 m500 읽기 점검

적용: R1·R10·R20은 실제 저장본·평가 자식·Kit 장치·결과 영수증으로 확인한다. M02에 따라 실행 중 코드·감독기·원장을 고치지 않는다.

| 항목 | 이번 실측 |
|---|---|
| 점검 시각 | 2026-10-31T07:21:59.9472114+09:00 |
| 관찰기 원자료 시각 | 2026-10-31T07:21:57+09:00 |
| 학습 상태 | running, iter 440, 기록 2026-10-31T07:21:45, 25.4007초/회 |
| manifest | completed_updates 401, 기록 2026-10-31T07:04:51+09:00 |
| model_500.pt | False |
| score-watch 폴더 | False |
| m500 평가 자식 | 관찰 없음. PID/Kit 장치와 대응할 평가 산출물 없음 |
| m500 도착 추정 | 07:47:09, 최신 기록 이후 같은 속도 유지 가정 |
| 프로세스 생존 | 학습26240 · 감독141272 · 관찰21272 · 깨우기42372 |
| 고정 ROOT | 2df419b0a4278981f6bd26e5eaedecbf7e8458db, tracked 변경 0개 |

manifest는 저장 경계에서 갱신되고 학습 상태 파일은 별도 주기로 갱신된다. 두 회차 차이를 학습 정지로 읽지 않는다. GPU1에 학습 PID의 CUDA 컨텍스트가 나타나는 것만으로 평가 기동을 주장하지 않는다. 이번에는 아직 평가 자체가 시작되지 않아 GPU1 평가를 확인할 수 없다.

원자료: [READBACK-0722.json](READBACK-0722.json). 관찰 원본: C:/mai/wt/foothold-lab/runner-ex40-b11-all-fixes/_out/reports/ex40-m500-watch-1031/observations.jsonl. 학습 원본: C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/train_start_status.json.

다음 점검은 이미 걸린 읽기 관찰로 실제 model_500 SHA와 평가 자식 PID, Kit cuda:1, GPU1 UUID GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f, 평가 영수증을 대조한다. 새 GPU 실행·학습·종료·원장 수정은 하지 않았다.

W57은 lead 05:3x 결정대로 최종 평가 사본5c160641와 별도 retry 명령만 준비한 상태다. 추가 verifier 의뢰·scorer-only 전환은 하지 않는다. 단계 끝 W57은 「보류 · retry 원장 참조」로 두며 실행은 lead 결정이다.
## 07:41 재확인

2026-10-31T07:41:22.5378045+09:00 실측: 학습은 2026-10-31T07:38:35 iter480, 25.1679초/회, running. manifest 451, 원자료 2026-10-31T07:25:58+09:00. model500 존재 False, score-watch 존재 False, 평가 자식은 관찰되지 않았다. 현재 속도 유지 가정 m500 도착 07:46:58 추정. GPU1 평가 확인은 여전히 대기다. 고정 ROOT 2df419b0a4278981f6bd26e5eaedecbf7e8458db, tracked 변경 0개. 관찰21272·깨우기42372 생존. [이번 원자료](READBACK-0741.json). W57 추가 작업 없음.