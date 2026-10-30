> 분류: A/평가 · EX-40 B11 통합 수정 기록
> 작성: runner · 2026-10-31
> 근거: TASK-B11-all-fixes.md · verifier VERIFY-EX40-B11-1031.md · 고정 사본 bdb32f3d
> 요지: H1~H3/P1~P3 여섯 막음을 한 후속 사본에 통합하고 CPU 결과와 미확인 범위를 기록한다
> 상태: P1 코드와 CPU 확인 기록 갱신 · verifier 변경분 확인 대기 · GPU/Kit/B14 금지

# EX-40 B11 통합 수정 보고

## 범위와 고정점

- 시작 HEAD: bdb32f3df9480af3d530389b162dbed77c0c2bd0
- 작업 사본: C:/mai/wt/foothold-lab/runner-ex40-b11-all-fixes
- 취합 문서: 96c19539efcf912527cc7ab4ee95a681261f420f
- 취합 B13 준비: 29a526b1bad6069d3ccca0138c564e17258e8bbf
- GPU·Kit·학습·B14 본기동은 수행하지 않는다. main/resume launch guard는 닫힌 채 둔다.

## 여섯 막음에 넣은 변경

| 막음 | 구현 |
|---|---|
| H1 | bounded smoke는 공식 CLI에서만 require_smoke_ready로 통과하고 main/resume은 require_launchable 차단을 유지한다. 18 update의 여덟 단계 경계와 DR probe의 생산 일정 매핑을 영수증 계약에 반영했다. |
| H2 | 저장 S-B10 이벤트는 그대로 비교하고, EX-40의 COM·gain·motor·push 네 직렬화 이벤트는 각각 모드·함수·자산·대상·범위를 검사한다. 설치 Isaac Lab events.py의 실제 함수 인자와 reset/interval 사용을 CPU AST 대조한다. |
| H3 | DR readback에 대상 환경 수, target range, 유한성, 배율 범위와 pending 항목 검사를 추가한다. 이득 표본은 설치 함수가 재설정하는 nominal joint gain 대비 비율이며, COM·모터 baseline을 체크포인트에 저장하고 재개한다. 손상 baseline은 재개 검사에서 거절한다. |
| P1 | 실행 사본 run_ex40_b11.sh가 감독기 ex40_supervisor에 연결된다. 감독기는 종료 상태, 저장본과 manifest SHA, 점수기 소비, 공식 resume gate, 연속 실패 세 건 중단을 순서대로 원장에 남긴다. 최종 완료는 전체 점수 원장 소비와 최종 파일·manifest·훈련 영수증이 맞을 때만 허용하며 HOLD는 대기한다. 학습 도중 주기 평가와 단계 보고 연결은 별도 미종결이다. |
| P2 | 재개 부모의 정책·지각망·두 optimizer·PPO LR·RNG·환경·지도·단계·DR baseline 계약을 읽고, 사망 미확인은 대기하며, 손상 최신 후보는 원인을 기록하고 이전 후보를 찾는다. |
| P3 | 문서 96c19539와 B13 29a526b1의 설명을 통합 상태에 맞췄다. bounded smoke와 본 일정, smoke model_17과 T0 실제 학습을 구별한다. |

## CPU 검증

통합 CPU 명령과 결과를 여기에 기록한다. 시험은 사용자가 지정한 기존 73개 묶음과 v4 14개, H1~H3/P1/P2 변이, B13 CPU 계약을 같은 pytest 호출로 한 번 실행한다. 공식 smoke CLI와 shell DRY도 Kit을 열지 않는 별도 절차로 확인한다.

| 검증 | 결과 |
|---|---|
| 기존 73 + v4 14 CPU 묶음, B13 및 B11 회귀 포함 | 최종 변경에서 `127 passed in 31.29s` |
| H1~H3/P1/P2 답 아는 입력 및 반례 | 통합 pytest에서 통과. COM ±99, motor 0, NaN, pending 항목, 중복 실패, final HOLD·SHA mismatch·미완료 점수 원장 반례 거부 확인 |
| 공식 smoke CLI · main/resume | smoke `--print-args` rc 0, main rc 2 거절, resume rc 2 거절 |
| run_ex40_b11.sh smoke DRY | rc 0, `DRY: training not started`; 최종 커밋 뒤 launch receipt와 prestart receipt 생성 확인 |
| 설치 Isaac Lab API 소스 대조 | 통합 CPU pytest에서 통과, Kit callback 실행은 미확인 |

첫 통합 pytest 결과는 `119 passed, 2 failed`였다. 감독기 시험에서 같은 run의 실패 저장본을 score pending과 consumed 단계에서 중복 실패로 셌고, fake launcher fixture에 잘못된 `SimpleNamespace` 참조가 있었다. 이를 idempotent하게 고치고 fixture를 수정한 뒤 121개 통과했다. 독립 verifier는 직전 SHA에서 final-only PASS/HOLD, 잘못된 SHA, 평가 30개 누락에도 감독기가 complete를 반환하는 반례를 발견했다. `_score_until_checkpoint`가 최종 `completion()`의 전체 점수·영수증·SHA 검사를 통과해야 소비 완료를 반환하도록 보완하고, 해당 회귀시험과 원래 통합 묶음을 다시 실행해 `127 passed`를 얻었다. 세 차례 실패 중단 시험은 별도 run 세 개를 사용한다. 공식 셸 DRY 첫 실행은 수정 중인 소스의 git-clean 관문에 걸렸고 이전 고정 커밋 뒤 통과했다. 이번 final completion 보완을 포함한 최종 커밋 뒤에도 DRY를 재실행할 예정이다.

## 미확인과 경계

Kit에서 실제 event callback이 적용된 물성, 학습 중 train_extra 표본과 reset 대상 분포, 실제 저장본 재개와 장기 감시 동작은 미확인이다. CPU의 fake child는 supervisor 전이와 공식 gate 호출 연결만 확인하며 GPU 프로세스를 만들지 않는다. smoke model_17은 18 update 완료본이며 T0 진입 설정을 밟는 데까지다. B13 Kit 평가와 본 학습은 이 커밋에서 실행하지 않는다. verifier는 최종 complete 오판 수정과 CPU 경계시험을 확인했으나, 학습 중 주기 평가 및 단계 보고 연결을 별도 P1 미종결로 남겼다.

## 최종 verifier 재확인

최종 코드 SHA `2647f43b8f66ecf1eb01c79a92d670979c69f317`의 수정 구간을 독립 확인했다. 정상 31개 점수의 완료, 점수 누락, HOLD, 파일 또는 manifest SHA 불일치, 평가 영수증 누락 반례가 의도대로 분기했고 독립 CPU 묶음은 `127 passed in 31.05s`였다. verifier 보고서 `C:/mai/wt/foothold-lab/verifier-w56/_out/reports/VERIFY-EX40-B11-1031.md` §8에 결과가 기록됐다.

그 검토는 감독기가 child 종료 뒤 점수기를 호출하며, 학습 중 평가와 단계 보고 소비가 연결되지 않은 점을 남은 P1으로 유지했다. 본 보고서의 P1도 이 한계를 그대로 둔다. 따라서 H1~H3/P2/P3와 final completion 오판 수정은 검증됐지만, 여섯 막음 전체를 닫았다고 표시하지 않는다.

## 수정 파일

foothold_s2/의 smoke·DR·resume·supervisor 구현과 CPU 시험, run_ex40_b11.sh, 문서 96c19539의 네 파일, B13 준비 보고서와 두 파일, 이 보고서를 수정했다. 원래 run_ex40.sh, s2_lab 자료와 verifier 원자료는 수정하지 않았다.


## P1 온라인 평가와 segment 소비 후속 · 2026-10-31

> 분류: A/평가 · EX-40 B11 P1
> 작성: runner · 2026-10-31
> 근거: TASK-B11-all-fixes.md §마지막 · VERIFY-EX40-B11-1031.md §8 · score_watch 소비 코드
> 요지: 학습 중 저장본 평가, 단계보고 영수증, 재개 segment 원장을 기존 score_watch 경로에 연결
> 상태: CPU fake child 확인 · 독립 P1 변경분 확인 대기 · 실제 Kit/GPU 미확인

### 시작 전 규칙과 범위

RULES-HUB와 FAILURE-LOG를 다시 읽었다. R6은 가짜 입력만으로 실제 실행을 확인했다고 하지 말고, Kit 확인을 못 하면 그 사실을 적으라는 규칙이다. 이번 요청은 Kit와 GPU를 금하므로 실제 Kit 실행은 생략했고 미확인으로 남긴다. R25에 따라 범위를 P1 잔여로 제한했다. M02 때문에 실행 중 shell 사본은 건드리지 않았다. M76에 따라 저장본 경로와 회차별 SHA를 score_watch 원장에 연결했다. M77에 따라 실행 마감과 학습 횟수 설정은 바꾸지 않았다.

### 구현

- supervisor는 child가 살아 있는 동안 주기적으로 PID manifest와 progress를 읽는다. score_watch가 정한 평가 stride 저장본이 새로 보이면 기존 `python -m foothold_s2.ex40_score_watch --once --no-telegram` 경로를 순서대로 호출한다.
- stride가 아닌 저장본으로 segment가 끝나도 직전 stride 저장본을 목표로 계산하고, 해당 run 폴더에 남아 있는 stride 후보 중 미소비 항목을 오래된 회차부터 소비한다. 예를 들어 model_751 저장은 model_500과 model_750 잔여를 지나치지 않는다.
- stage boundary가 평가되면 score_watch의 `stage_reports`가 로컬 `score_out/stage_reports/`에 JSON과 Markdown을 쓴다. supervisor는 현재 저장본 회차의 보고 영수증이 생기기 전에는 그 저장본을 소비 완료로 취급하지 않는다. `--lab-feed`도 같은 score_out 아래로 지정하고 Telegram 및 Git 게시 인자는 주지 않는다.
- score ledger 행에 segment `run_dir`와 checkpoint 전체 경로를 함께 기록한다. 최종 완료 검사는 각 회차의 원래 segment manifest, 파일 SHA, stage_log, score receipt를 대조한다. 단계 비교 보고서도 현재 회차와 직전 단계 회차의 각각의 train_extra 경로를 읽는다.
- supervisor event 원장 `supervisor_score_events.jsonl`은 PID, segment index, checkpoint 회차와 SHA, 상태, 소비된 회차, 단계보고 JSON 경로와 SHA를 기록한다. 같은 상태의 연속 관측은 중복 기록하지 않는다. 실패, HOLD, SHA 충돌, 점수 누락은 소비 완료로 바꾸지 않는다.
- 기존 resume 흐름은 보존한다. 점수 소비 완료 뒤 기존 official launcher gate를 거쳐 다음 segment argv를 준비한다. supervisor는 child나 다른 프로세스를 종료하지 않는다.

### CPU 확인과 원출력

실측 실행 명령:

```text
CUDA_VISIBLE_DEVICES=''
PYTHONDONTWRITEBYTECODE='1'
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest C:/mai/wt/foothold-lab/runner-ex40-b11-all-fixes/foothold_s2/tests/test_ex40_b11_all_fixes_cpu.py C:/mai/wt/foothold-lab/runner-ex40-b11-all-fixes/foothold_s2/tests/test_ex40_scorer_cpu.py -q
```

마지막 출력 원문:

```text
..............................                                           [100%]
30 passed in 6.74s
```

확인 입력에는 살아 있는 fake child, update 751 비stride 저장, model_500/model_750 미소비 행, stage boundary 보고, 두 개의 분리된 segment checkpoint, 같은 회차의 SHA 충돌, 누락된 점수 행이 포함된다. 비stride 저장은 두 기존 stride 저장을 모두 소비한 뒤에만 통과했고, 미소비 충돌과 누락 입력은 각각 unknown 또는 pending으로 남았다. `git diff --check` 출력은 비어 있었다. 이 시험은 CPU 계약 확인이며 실 run과 Kit 평가가 통과했다는 증거가 아니다.

초기 시험 실행 중 fixture에 잘못된 임시 table 경로와 stage_report 입력이 있어 실패했다. fixture를 실제 TABLE과 분리 segment receipt에 맞춘 뒤 영향 시험 묶음을 다시 실행했다. 최종 원출력은 위 30 passed이며 초기 실패를 성공으로 합산하지 않았다.

### 상태와 잔여

- 코드 변경 출발점: c1cefb1ab537bd5a2468dd0b9bcd1ec8133c9518. 변경 전 보존 refs: `refs/backup/ex40-b11-pre-p1/c1cefb1a`, `refs/backup/ex40-b11-pre-p1/2da3afe5`, `refs/backup/ex40-b11-pre-p1/2647f43b`.
- 수정 파일은 `foothold_s2/ex40_supervisor.py`, `foothold_s2/ex40_score_watch.py`, `foothold_s2/ex40_stage_report.py`, `foothold_s2/tests/test_ex40_b11_all_fixes_cpu.py`, `foothold_s2/tests/test_ex40_scorer_cpu.py`이다.
- 실제 학습 child, 실제 score evaluator, Kit, CUDA, Telegram/Git 보고 게시, 남의 프로세스 조작은 수행하지 않았다. 학습 중 실제 checkpoint가 정해진 시간 간격으로 도착하는지, GPU 자원 경계, Kit 출력, 실제 결과 도달은 미확인이다.
- P1 변경분 독립 확인은 analyst가 verifier에 한 차례 요청한다. 그 확인 전에는 B11 P1 전체를 닫거나 B12/B13 준비가 허용됐다고 말하지 않는다.


구현 커밋(위 CPU 시험이 직접 대상으로 한 HEAD): `84ce82a6a8eae245f1cfd16ba0071d530581bc58` · 부모 `c1cefb1ab537bd5a2468dd0b9bcd1ec8133c9518`. 다음 보고 기록 커밋은 이 구현 파일을 바꾸지 않는다.

## 01:54 P1 실제 반환값과 운영 발신 인자 후속 · 2026-10-31

### 확인 및 변경

- 기존 감독기는 `stage_reports()`의 `published`를 목록으로 순회했다. 실제 함수는 성공 건수 정수 `0` 또는 양의 정수를 반환한다. 실제 빈 경계 입력에서 반환값 `0`, 형식 `int`를 관측했고, 이전 순회식은 `TypeError: 'int' object is not iterable`가 되는 계약 오류였다.
- supervisor는 이제 정수 건수를 형식 검사하고, 요구 경계별 JSON/Markdown 보고서, checkpoint 회차와 SHA, 공유 lab feed JSON/HTML, 설정된 경우 요약 `.delivery.json` 및 본문 SHA를 확인한다. 건수가 부족하거나 배송 영수증이 없으면 pending, 형식이 계약과 다르면 unknown으로 둔다.
- 성공 경계 시험은 실제 `stage_reports()`와 실제 score ledger, 체크포인트 SHA, 보고서 파일 및 fake sender를 거쳤다. sender는 실제 발신 대신 수락 응답만 돌려주며, 생성된 lab feed와 배송 영수증을 확인한다. 완료된 영수증 재소비 때 중복 발신을 하지 않는 것도 확인한다.
- `run_ex40_b11.sh`에서 supervisor에 기존 `tg_send.py`와 `lab_status/ex40_stage_reports.json` 기본 경로를 전달한다. 운영자가 `EX40_TELEGRAM_SENDER`, `EX40_LAB_FEED`로 경로를 덮을 수 있다. supervisor는 이를 기존 `ex40_score_watch --telegram-sender --lab-feed` 인자로 전달하며, sender가 없을 때만 `--no-telegram`을 쓴다. score_watch가 lab feed 부모 디렉터리를 만들도록 했다.

### CPU 확인

명령:

```text
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest C:/mai/wt/foothold-lab/runner-ex40-b11-all-fixes/foothold_s2/tests/test_ex40_b11_all_fixes_cpu.py C:/mai/wt/foothold-lab/runner-ex40-b11-all-fixes/foothold_s2/tests/test_ex40_scorer_cpu.py -q
```

원출력:

```text
.................................                                        [100%]
33 passed in 6.63s
```

실제 성공 stage-report 함수 경로, 실제 `published=0` 정수 반환의 pending 처리, fake sender, 배송/요약 SHA 및 공유 lab JSON/HTML, 공식 supervisor 인자 전달, 셸 기본 경로를 시험했다. 외부 Telegram 발신은 없었다.

### 상태와 잔여

- 이 후속은 기존 P1/B8 범위다. 이전 보고의 P1 전면 완료 표시는 없으며 analyst의 P1 변경분 verifier 확인이 여전히 필요하다.
- GPU, Kit, 학습 child, 실제 score evaluator 및 외부 발신/게시를 실행하지 않았다. 실제 lab 서비스가 파일을 읽고 실제 Telegram 수신자가 받는지는 미확인이다.
- 관련 변경은 `foothold_s2/ex40_supervisor.py`, `foothold_s2/ex40_score_watch.py`, `foothold_s2/run_ex40_b11.sh`, 두 CPU 시험 파일 및 이 보고서다. push하지 않았다.
