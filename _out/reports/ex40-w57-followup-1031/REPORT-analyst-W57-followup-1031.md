> 분류: 평가 실행 점검
> 작성: analyst · 2026-10-31 04:46 KST
> 근거: lead 04:3x 의뢰 · 고정본 2df419b0 · 실제 B13/W57 원자료 · 실행 중 상태 파일
> 요지: W57 재시도는 평가 전용 새 사본에서 구현한다. 실행 중 감독기는 고정 경로의 점수기를 호출하므로 새 사본을 만드는 것만으로 교체되지 않는다.
> 상태: 진행 중 · 구현 scripter · 독립 verifier 확인 대기 · 학습/감독기/고정 사본/실행 원장 변경 없음

# EX-40 W57 평가 전용 복구와 m500 관찰

## 현재 확인과 범위

2026-10-31 04:41 CPU 읽기 확인: 학습 PID 26240, 감독기 PID 141272 생존. `train_start_status.json`은 running, iter60, 기록시각 04:40:01, 25.5906초/회다. manifest는 저장 경계에서 갱신되어 completed_updates51과 model_50 SHA를 갖는다. 이 차이를 실행 정지로 읽지 않는다. m500 도착 시각은 아직 추정이며 실제 저장 영수증으로 확인한다.

- 본 실행: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240`.
- 실행 고정본: `C:/mai/wt/foothold-lab/analyst-ex40-main-verified-1031`, HEAD `2df419b0a4278981f6bd26e5eaedecbf7e8458db`. 수정 금지.
- 실측 감독기 명령의 평가 원장 자리: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch`, 점수 폴더 `scores`. 읽기만.
- 평가 코드 담당: scripter의 `C:/mai/wt/foothold-lab/scripter-ex40-w57-retry`. lead에게 직접 배정받아 진행 중임을 Orca 화면에서 확인했다. 중복 구현하지 않는다.
- m500 읽기 관찰 준비 담당: 기존 runner. Task `task_b76c3904493f`, Dispatch `ctx_d66090fcada3`. 준비·CPU 반례·숨김 관찰기·도착 시험을 맡겼다. 아직 설치 확인 전이다.
- M02: 실행 파일 수정 금지. R20: 실제 저장본·원자료와 소비 경로 확인. M13: 감시 장치 기동 뒤 실제 도착 확인. CPU 통과와 Kit 실행 증거를 분리한다.

## 구분해야 하는 실패 셋

| 항목 | 원자료로 확인한 사실 | 아직 확인하지 못한 것 |
|---|---|---|
| 첫 W57 호출 | B13 마지막 axis_v2가 0.312초에 rc1, checkpoint_sha256.txt 0바이트, Kit run.log 없음 | 당시 sha256sum 실패의 실제 원인. 같은 입력을 CPU에서 다시 읽은 해시는 정상이다 |
| W57 단독 재시도 | `ex40_w57_retry_20261031_0353_f1fff17f`는 rc0, 3모드 × 10칸, 30개 원자료 NPZ 해시 일치 | 첫 실패가 재발하지 않는다는 보장 |
| 점수 소비 | m17의 18개 목표 회전 칸은 완료 환경0, 종료 오차 null. 기존 `_finite`는 EvidenceHold를 낸다 | 전체 본학습 성능. m17의 미달을 본학습에 외삽하지 않는다 |

목표에 도달하지 못한 유효 측정과 측정 파일·숫자가 없는 증거 결손을 분리해야 한다. 문턱을 바꾸거나 null을 0 오차로 채우지 않는다. 원 B13 실패와 완료된 첫 다섯 단계는 그대로 보존한다.

## 실제 적용 경로의 제약

고정본 `foothold_s2/ex40_supervisor.py:281~293`은 `sys.executable -m foothold_s2.ex40_score_watch`를 그 고정본 ROOT에서 호출한다. 이미 떠 있는 감독기 환경에 평가 사본 경로를 바꾸는 인자가 없다. 따라서 단순히 새 점수기를 별도 기동했다고 감독기의 다음 호출까지 바뀌었다고 보고할 수 없다.

`ex40_score_watch.py:100~109`는 `score_ledger.jsonl`에서 checkpoint_iteration 중복을 거절한다. 같은 파일에 같은 회차의 재시도 행을 덧붙이는 방식은 구 소비기를 깨뜨린다. 기존 done/HOLD도 다음 process_once 후보에서 제외된다. 수정·삭제 없는 별도 retry 이력 및 기존 소비기 호환성을 CPU로 검증해야 한다.

새 평가 사본에서 복구 결과를 생성하는 것, 실행 중 원장이 그 결과를 채택하는 것, 감독기가 그 결과를 소비하는 것은 각각 다른 단계다. 이번 구현과 검증 중에는 실행 중인 원장에 적용하지 않는다. 실제 적용에 현재 지시 범위를 넘는 조치가 필요하면 구체적인 변경 자리와 대안을 lead에게 보고한다.

## 인계할 완료 증거

1. 평가 전용 고정 HEAD와 diff. 학습·감독기·설정 문턱 변경 없음.
2. 유한한 전처리 재시도, stderr/명령/비밀값 없는 환경 기록, 실패 시 원자료 보존.
3. 새 출력 폴더와 retry ID, 부모 실패 영수증·checkpoint SHA 연결, 기존 다섯 단계 재사용 검증.
4. 0완료/null 정상 입력, 실제 결손·NaN·SHA 불일치·중복 시도·부분 실패·동시 쓰기 반례.
5. verifier 한 번의 변경분 확인. 이후 GPU 평가가 없으면 Kit 미실행으로 표기.
6. m500 실제 평가 PID/물리 GPU UUID/명령/영수증의 대조. cuda:1 설정만으로 실행 장치 확인을 갈음하지 않는다.

## 04:53 중간 대조

- 고정본의 실제 함수를 CPU에서 호출했다. 단일 HOLD 행은 읽고, 같은 회차 retry 행을 같은 원장에 추가하면 `score ledger has a malformed or duplicate checkpoint iteration`으로 거절한다. `_verified_score_slot`은 저장 상태 HOLD에서 `pending`을 반환한다. `_finite(None)`는 `EvidenceHold`다. 결과 [CPU-OLD-CONSUMER.json](CPU-OLD-CONSUMER.json). 임시 폴더 입력만 만들었고 실행 원장은 쓰지 않았다.
- 원 B13 failed 영수증 SHA `9a34371ff8d9db8ef5de52400dbc61e85b0939e735902726fda47ffcc730b84c`, W57 단독 JSON SHA `e5cb7f3b7f08f551bc29396918a57668ee31a00080c896c8ede3c78188a23ac9` 재확인. 실행 사본 HEAD 2df419b0, tracked 변경0. [READBACK-0448.json](READBACK-0448.json).
- `axis_v2_cells.py`의 goal 통계는 완료하지 못한 stop 구간의 오차를 null로 내보낸다. raw JSON의 완료0/null은 실제 생산자 경로와 일치한다. 그 null을 정상0오차로 바꾸어서는 안 된다.
- scripter 첫 묶음 `dec2e4ee`가 생성됐다. 평가 사전 해시의 유한 재시도와 별도 재시도 이력을 구현했으나, 기존 score 소비와 null 구분까지 닫혔다는 증거는 아직 없다. 최종 묶음 및 verifier 검토 전이다.
- runner 자체 알림 `msg_0d79ea00a665`를 04:46:24에 실제 수신해 ACK했다. 관찰기 기동·CPU 반례의 최종 보고는 대기 중이다. m500 평가가 이미 돌았다는 뜻이 아니다.
- 04:47 `nvidia-smi`에서 학습 PID26240은 두 GPU UUID 모두에 나타났지만 Kit 로그는 AppLauncher와 Environment device 모두 cuda:0이다. 컨텍스트 존재만으로 계산 장치나 새 평가 시작을 단정하지 않는다. m500의 평가 자식 PID와 Kit 장치 로그를 따로 확인한다.

## 이력

| 시각 | 내용 |
|---|---|
| 04:46 | 작업 범위·실제 실행 상태·고정 감독기 교체 제약 기록. 새 평가 사본의 구현과 관찰기 준비 진행 |
| 04:53 | 기존 소비기 CPU 반례·원본 해시 보존·알림 도착 확인. scripter 첫 묶음 및 남은 소비 경로 기록 |
