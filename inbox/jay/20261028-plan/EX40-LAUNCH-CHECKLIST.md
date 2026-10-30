> 분류: 실험 실행 점검표
> 작성: lead · 2026-10-30 21:5x
> 근거: WORKLIST D57 · D59 · D62 · D65 · D66 · D68~D77, FAILURE-LOG R1~R25 · M01~M77, FLOW-experiment-cycle-1029 8 단계
> 요지: EX-40 기동 전에 끝내야 할 일과 학습 중 자동으로 돌 일을 한 장에. 칸이 모두 「끝 + 증거」가 되어야 기동한다.
> 상태: 진행 중 · analyst가 B11~B13 조정 · B14 본 기동 금지(10/30 23:4x 위임)

# EX-40 기동 점검표

갱신 규칙: 상태가 바뀌면 이 표를 고치고 커밋한다. 증거 칸은 커밋 · 경로 · 숫자. 메모리에 의존하지 않는다.

## A. 결정 (모두 닫힘)

| 번호 | 내용 | 결정 |
|---|---|---|
| A1 | 단계 넘김: 회차 + 성과 그림자 기록 | D72 |
| A2 | B0 · B1 · B2 · B3a · B3b · B3c · D · T0, m0~m8000 (8001 갱신) | D72 · D74 |
| A3 | COM·이득·모터·지연·밀기 다섯 항목 확대 0 → B3c 끝0.5 → D1. 관측 잡음은 m0부터 끝까지1배 고정. 지연 상한0 → 7.5 → 15ms(5ms 내림). 마찰·질량 유지 | D74 · D75 |
| A4 | 보상 · 정지 두 항 · heading · 대칭 끔 · 깃발 0 % | D70 · D71 |
| A5 | 연속7종 L0~2 고정(자동 승급 끔) | D71이 채택한 analyst 0111f9d5 §3 · 실행카드96c19539에 출처 명시 |
| A6 | 밀기 임시 준비값: D 수평 각 축Δv±1.0m/s, B 끝±0.5, 간격10~15s. 선행 조사와 실기 강건성 보장은 분리. 관측 잡음 유지 | D76 · analyst 범위표66a6a4f1. 본 기동 승인은 별도 |

## B. 기동 전 (순서대로)

| 번호 | 일 | 담당 | 상태 | 증거 |
|---|---|---|---|---|
| B1 | 규칙 대조: FAILURE-LOG R · M 중 이번 기동에 걸리는 항목 목록과 대응 | verifier | 끝(표 35 행, 확인은 B11 에서) | verifier-w56/_out/reports/RULES-EX40-1030.md |
| B2 | 문서 정합 두 차례: 커리큘럼 정본·FLOW·WORKLIST W칸·단계 문서·실행카드 | analyst(대조·수정) · planner(후속확인) · lead(WORKLIST) | 96c19539 문서 취합본2da3afe5에서 verifier P3 닫힘. planner 후속 확인 대기 | CURRICULUM·CARD·현재 FLOW §1a·AUDIT. verifier VERIFY-EX40-B11-1031 §7.2. planner 확인은 lead00:1x에 따라 기동 뒤 가능. P1 후속 코드가 문서 소비를 바꾸면 해당 변경분을 같은 묶음에서 대조 |
| B3 | DR 범위표·밀기 논문·관측 잡음 근거 | analyst | 범위·출처·W51 결과 완료. 최종 통합본 대조는B11 | analyst-ame2 DR-RANGES-EX40-1030 v0.1f. SLR 영상 직접 확인, 논문·코드 외란은 다름. 문서96c19539 대조 이력 |
| B4 | W51 추가 비교: EX38 m3001·EX39B m4501, 5조건+base재측정, GPU1 직렬 | analyst | 10/31 00:42:15 완료, 12/12 rc0·468칸. 감독기 종료0 및 CPU 원자료 대조 확인 | s2_lab/basic_gait_runs/eval_actuator/w51_followup_20261030/batch_done.json. analyst-ame2/_out/reports/w51-followup-1030/RESULT-W51-followup.md·audit.json. ±0.5 진단값은D76 학습값과 별개 |
| B5 | 코드: 단계 표 v7(지형 L0~2 · 재개 계약) | runner | 끝 | v7 |
| B6 | DR 일정·이벤트·readback·확인기 | runner | 2da3afe5의 H2/H3 지정 반례 닫힘. 실제 Kit 미확인 | verifier §7.1/7.2: 정상 네 이벤트 PASS, COM±99·motor0·NaN·pending 거부. 실제 환경 직렬화·표본은B12에서 |
| B7 | 코드: 그림자 점수기(8 단계 이름 · 원장 · 단계 끝 전체 평가 · 끝난 뒤 잔여 평가) | scripter | CPU 끝 | 1910d2fb (scripter-ex40-score-v8) |
| B8 | 코드: 단계 끝 자동 보고(얻은 점 · 잃은 점 · 앞 단계 대비 칸별 변화 · 발별 정지 · 좌우) → lab 페이지 · 텔레그램 요지 | scripter | CPU 끝 · lab 첫 화면 링크는 갱신기 소유(남음) | 1910d2fb · lab_status/ex40_stage_reports.html · tg_send.py |
| B9 | 코드: 재개 감시기(마지막 온전한 저장본, 3 회 연속 실패 시 멈춤) | runner | P2·최종 완료·학습중 호출 확인. P1 중간 누락 소비 오판1 남음 | verifier r4 정상31개·분리segment consumed, 보고8건 재소비 중복없음. m5550에서 m5250 파일+score 동시누락도 consumed여서 기존P1 같은 묶음 고침 중 |
| B10 | v7·v8·점수기·보고 통합 | runner | 코드3afb0d6b·보고139f0d2d clean 고정 뒤 누락 반례 후속 고침 중 | runner-ex40-b11-all-fixes. 02:07 verifier 변경분 착수, 독립 CPU33통과6.75s·실제 반환published8 확인. 02:14 runner 같은 묶음 후속 착수. 기존 고정본 보존 |
| B11 | verifier 최종 재검증: 문서 · 카드 · 코드 · 설정 · 재개 · 점수기 · 보고, 막음 0 | verifier | H1~H3/P2/P3와final completion 닫힘, P1 누락 막음1 유지 | verifier-w56/_out/ex40-b11-r4/results.json·pytest.txt, analyst P1-RECHECK-1031.md 02:15절. 대상까지 필요한 회차가 파일목록에서 빠져도 검사해야 함. lead00:3x대로 전체0전 Kit 대기. 139f 공식smoke DRY rc0/prestart_pass는 실제Kit 증거가 아님 |
| B12 | 학습 Kit 짧은 확인(GPU0): 단계·실제DR·L0~2·광선·발별기록 | analyst(직접위임) | P1을 포함한 B11 막음0 뒤 한 번 | handoff_analyst_coord.md. 이 위임은 B14를 포함하지 않음 |
| B13 | 점수기 Kit(GPU1): 단계끝 전체평가1회·실제시간 | analyst(직접위임) | CPU 준비 보고 접수. B11/B12 및GPU1 W51 종료 뒤 한 번 | scripter-ex40-b13 29a526b1 · PREP-EX40-B13-1031.md. CPU32는scripter 보고, Kit 미실행. 짧은model17 전체 경로 시험은 T0 성능 판정과 분리. W51과 중복 기동 금지 |
| B14 | 기동: 시작 스크립트 · 고정 사본(detached) · 실제 경로 점검 · END_BY ≥ 예상 끝 + 24 h · GPU0 | lead | D77 조건 충족 후 lead 판단. analyst 본기동 금지 유지 | analyst 위임은B12/B13과명령·ETA준비까지 |
| B15 | 돌았다 확인(팀장 10/31 00:0x 강화): GPU0 compute-apps PID = 학습 PID · 메모리/사용률 지속(여러 번) · run.log 회차가 시각과 함께 증가 · 1 회 속도 · 저장본 · stage_log · train_extra(DR readback · 발별 · 지형 L0~2) 생성 · 영수증 HEAD = 고정 사본 · dirty 0 · 인자 = D68~D77 · 점수기 GPU1 만. 기동 직후와 10 분 뒤 두 번 | lead | 대기 | |

## C. 학습 중 (자동)

| 번호 | 일 | 어디서 |
|---|---|---|
| C1 | 저장 50 간격, 그림자 평가 m500부터250 간격(GPU1), m8000까지31개. 단계 끝 저장본(m1500 · 3000 · 4500 · 5000 · 5500 · 6000 · 7500 · 8000) 전체 평가 | 점수기 ex40_score_config.json checkpoint_first=500. analyst의m250·32개 추정을 정정 |
| C2 | 단계 끝 보고: 얻은 점 · 잃은 점 · 다음 단계 주의 → 팀장이 보는 것은 이것 | 보고기 |
| C3 | 학습 죽음 → 재개 감시기 | 재개 감시기 |
| C4 | 매시 :13 점검(GPU · 진행 · 점수 원장) | lead cron |

## D. 끝난 뒤

| 번호 | 일 |
|---|---|
| D1 | 최종 W15 13×3 · W57 · 정지 · 좌우 · DR 비교군과 같은 조건 재측정 |
| D2 | 영상(GPU1, 전 프레임 검사) |
| D3 | RESULT 9 절 문서 · git · 텔레그램 · lab 페이지 |
| D4 | 다른 시드는 모든 과정 끝난 뒤 맨 마지막 |

## 예상 시각 (추정, 갱신)

- 기동 목표: 10/31(토) 오전, B 칸이 모두 끝 + 증거일 때.
- 8001 갱신 × 약 24 s(EX-38 · 39 실측 근사) ≈ 53.3 h. 10:00 기동이면 11/2(월) 15:20 전후 끝. DR 켠 뒤 속도 변화는 Kit 에서 다시 재서 고친다.
- 단계 끝 예상(10:00 기동 기준): B0 20:00(10/31) · B1 06:00(11/1) · B2 16:00 · B3a 19:20 · B3b 22:40 · B3c 02:00(11/2) · D 12:00 · T0 15:20.

## 10/31 00:04 조정 인계

- analyst는 범위 고침 → verifier B11 → B12/B13 순서만 맡는다. B14는 시작하지 않고 명령·ETA·END_BY를 준비해 lead에 보고한다.
- R6 실제 Kit, R25 범위 보존, M02 고정 실행 사본, M76 실제값 대조, M77 마감 여유를 적용한다.
- 20분 재개 알림을 자신의 창에만 걸었다. 00:03:53 시험 문장이 실제 입력으로 도착했다. 자동GPU기동 기능은 없다. 로그: analyst-ame2/_out/reports/ex40-coord-1031/wake-status.log.
