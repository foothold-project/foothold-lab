> 분류: A/평가 · 감독기 진단
> 작성: analyst · 2026-10-31 13:40
> 근거: 실행 고정본2df419b0 · 실제 원장/상태/평가 영수증 · 자식 기동 차단 CPU 재현
> 요지: m1000 HOLD를 pending으로 조기 반환해 m1250 평가 호출에 도달하지 않으며 m1500도 같은 조건이면 막힘
> 상태: 원인 확인 · 코드/실행/원장 수정 없음 · 조치 결정은 lead

# EX-40 m1250 평가 미기동 원인

감독기 ex40_supervisor.py:228~244는 목표 회차까지 500·750·1000·1250을 차례로 검증한다. :308~309는 saved.state=HOLD를 pending으로 반환한다. :243~244가 그 pending을 즉시 상위로 반환하므로 :281~290의 ex40_score_watch --once 실행에 도달하지 않는다.

실제 고정본 함수 _score_until_checkpoint를 실제 run·manifest·원장으로 CPU 호출했다. subprocess.run과 stage_reports는 호출하면 실패하도록 막았다. 결과는 500 verified → 750 verified → 1000 pending, 최종 pending, 자식 기동0회다. [CPU 재현 결과](EX40-HOLD-BLOCK-READONLY-1031.json). 실행 사본/원장에 결과를 쓰는 분기는 차단했다.

m1000은 eval_receipt done이고 네 단계 모두 rc0이다. HOLD 원인은 score.json의 eval_gt/spin-1.2 stage_first_checkpoint_survival_drop다. 최초m500 생존64 대비m1000 생존60으로 4개 감소했다. 절대 생존 최소60은 충족하지만 상대 하락 허용3보다 커 HOLD다. 오류/프로세스 실패가 아니라 이 증거 보류 상태가 후속 평가 생성까지 차단한 것이다.

ex40_score_watch.py:174는 state.done에 있는 회차를 후보에서 제외한다. 즉 점수기를 직접 호출했다면 done=HOLD인1000을 건너뛰고 새1250을 후보로 고를 수 있지만, 이번에는 감독기가 그 점수기를 부르기 전에 반환했다. 직접 호출·재평가는 이번 읽기 과제에서 하지 않았다.

감독기 :420~429는 consumed일 때만 last_consumed를 갱신한다. 따라서 pending이면 15초마다 같은 검증 경로를 다시 타며 똑같은1000에서 반환한다. 새1250의 평가 실패 기록이 없는 이유는 평가가 시작조차 되지 않았기 때문이다. 실패 원자료 위치는 score-watch/model_1000_64f24758990e/score.json, watch_state.json done.1000=HOLD, score_ledger.jsonl1000행, supervisor_score_events.jsonl의1000·1250 pending이다.

**m1500 예상:** 1000 HOLD와 고정 감독기 코드가 그대로면 expected_updates에1000이 계속 들어가므로1500도 평가 호출 전에 pending으로 반환한다. 따라서 m1500 그림자 평가/단계 끝 보고가 저절로 복구되지 않는다. m1500 저장 자체는 별개의 학습 진행이다. 실제 m1500 도착 전의 코드 경로 예상이며 실행 실측으로 표현하지 않는다.

13:37:36 학습1330/running, manifest1301. m1250 SHA728d8517f973692f43459545ae20483cfe5b5c3ce67424094e00c7c0045a4e5e가13:04:03 pending 이벤트와 일치했다. model1250 평가폴더·score1250·원장행·점수기/평가Python은 관찰되지 않았다. 고정2df419b0 tracked변경0. 학습/감독/primary/고정소스 수정이나 새 GPU 실행 없음.

원자료 뿌리: C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313. 고정 소스: C:/mai/wt/foothold-lab/analyst-ex40-main-verified-1031/foothold_s2/. 현재 별도 W57 retry만 남기기로 한 결정과는 별개로, 이 경로는 m1000의 회전 생존 HOLD에서도 동일하게 막힌다. 이번에는 원인과 영향만 보고하며 수정/적용은 하지 않는다.