> 분류: 평가 실행 점검
> 작성: analyst · 2026-10-31 05:40 KST
> 근거: lead 04:3x 의뢰 · 고정본 2df419b0 · 실제 B13/W57 원자료 · 실행 중 상태 파일
> 요지: 평가 전용 5c160641의 CPU 확인을 끝냈다. lead 05:3x 결정으로 live 전환은 하지 않고 별도 retry 결과만 남긴다.
> 상태: 이 구현 단위 종료 · 실행 명령만 준비 · 추가 구현·GPU 실행 없음 · W57 보고 칸은 보류 · retry 원장 참조 · m500 관찰은 유지

# EX-40 W57 평가 전용 복구와 m500 관찰

## 현재 확인과 범위

2026-10-31 04:41 CPU 읽기 확인: 학습 PID 26240, 감독기 PID 141272 생존. `train_start_status.json`은 running, iter60, 기록시각 04:40:01, 25.5906초/회다. manifest는 저장 경계에서 갱신되어 completed_updates51과 model_50 SHA를 갖는다. 이 차이를 실행 정지로 읽지 않는다. m500 도착 시각은 아직 추정이며 실제 저장 영수증으로 확인한다.

- 본 실행: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240`.
- 실행 고정본: `C:/mai/wt/foothold-lab/analyst-ex40-main-verified-1031`, HEAD `2df419b0a4278981f6bd26e5eaedecbf7e8458db`. 수정 금지.
- 실측 감독기 명령의 평가 원장 자리: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch`, 점수 폴더 `scores`. 읽기만.
- 평가 코드 담당: scripter의 `C:/mai/wt/foothold-lab/scripter-ex40-w57-retry`. lead에게 직접 배정받아 진행 중임을 Orca 화면에서 확인했다. 중복 구현하지 않는다.
- m500 읽기 관찰 담당: 기존 runner. Task `task_b76c3904493f`, Dispatch `ctx_d66090fcada3`. 05:00 준비 보고와 CPU 13건을 독립 대조했다. 실제 m500 확인은 아직 대기 중이다.
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

## 05:11 후속 확인

- scripter 새 평가 전용 사본의 HEAD는 `258394c32069ed738bc04778576bca561641cc42`, tracked 변경0이다. 원 고정본 `2df419b0` 대비 8파일 변경이다. 생산 코드에서는 W57 사전 해시, 별도 재시도 실행기, 완료0/null의 점수 처리만 바뀌었다. 새 학습이나 기존 원장 변경은 없다.
- scripter 보고의 CPU 64 PASS는 담당자의 시험 결과다. analyst는 diff와 실제 원자료의 완료0/null 생산 경로를 읽었으며, 독립 실행 검증은 verifier에 1회 묶음으로 맡겼다. Task `task_dacd56d217bd`, Dispatch `ctx_7910301b1531`, 05:06:55 `turnStart=observed`. 산출 예정 `C:/mai/wt/foothold-lab/verifier-w56/_out/reports/VERIFY-EX40-W57-RETRY-1031.md`.
- runner 관찰기 PID21272, 04:56:52 시작, 읽기 전용이다. CPU 13/13을 analyst가 다시 실행해 확인했다. 05:09:43 관찰은 completed_updates101, m500 없음, score-watch 없음이다. 학습 상태 파일은 05:10:19 iter130, 25.9522초/회, running이다. 서로 저장 주기가 다른 두 기록을 혼동하지 않는다.
- 자체 깨우기 v1은 05:02:05 실제 도착했지만 한글이 깨졌다. M64의 PowerShell 5.1 BOM 없는 UTF-8 해석 문제다. 자기 알림의 제어 파일로 PID38132가 05:08:41 정상 종료한 것을 확인하고, 실행 파일을 덮어쓰지 않은 ASCII v2로 교체했다. 학습·감독 프로세스는 건드리지 않았다.
- ASCII v2 PID42372, 05:09:33 시작. 05:10:25 시험이 사용자 입력으로 온 것을 확인했다. 07:20부터 20분 간격, 13:00까지 읽기 점검 알림이다. 소스 파싱 오류0, 비ASCII 바이트0. 시험용 임시 `M500-REPORTED` 제어 파일은 이전 자기 helper 종료 후 제거했고, 실제 m500 완료 표식은 아직 없다.
- live 적용 제약은 lead Run에 `msg_caa7d38e0742`로 전달했다. enqueue 증거이며 lead가 읽었는지는 미확인이다.

### 평가 사본 채택과 live 적용을 구분할 것

| 단계 | 지금 준비한 것 | 남은 것 |
|---|---|---|
| 실패 원인 확보 | 사전 해시 stderr, 유한 재시도, 원자 해시 영수증 | 과거 0.312초 실패의 정확한 OS 원인은 복구할 수 없어 미확인 |
| 실패 회차 재평가 | 동일 checkpoint·설정·단계표 SHA 확인, W57만 새 폴더 실행, 별도 attempt 원장 | 새 코드의 Kit 실행은 이번 CPU 검증에서 하지 않음 |
| 점수 의미 | 완료0/null과 증거 결측을 분리, 기존 수치 문턱 보존 | verifier 반례·원자료 독립 확인 진행 중 |
| 실행 중 감독기 소비 | 옛 소비기의 중복행 거절·HOLD pending을 CPU로 확인 | 옛 ROOT는 새 코드를 읽지 않는다. 별도 원장만으로 자동 채택 완료라고 할 수 없음 |

기존 감독기만 종료하거나 재기동하는 방법은 이 과제의 권한 밖이며 학습 자식 생존도 보장하지 못한다. 고정 사본 덮어쓰기, Python 경로 우회, 기존 HOLD 행 수정으로 이 제한을 피하지 않는다. lead가 적용 범위를 정하기 전에는 새 평가 사본의 구현·CPU 증거·독립 검토를 전달하고 현재 학습을 보존한다.

## 05:20 평가 전용 고침 확인

**평가용 최종 HEAD `5c1606412e9876b7c3105756f378b4a5a629e73c`. 코드 고침과 CPU 확인은 끝났고, live 적용과 실제 새 코드 Kit 실행은 미완료다.**

verifier는 `258394c3` 전체 변경분을 1회 검토해 기존 CPU 64건을 직접 통과시켰으나 H1을 발견했다. 완료0에서 오차 키 자체를 지우면 B0 PASS, B2 FAIL로 소비되는 결함이다. scripter는 한 지점에 키 존재 검사 두 줄을 더했고, 전후 반례와 관련24건 시험을 기록했다. analyst는 같은 반례를 독립 입력으로 다시 구성해 고침 전후를 직접 대조했다.

| 확인 | 대상 | 결과 | 근거 |
|---|---|---|---|
| 변경분 독립 검토 | 258394c3 | 기존64건 통과, 누락 반례 H1 발견 | `C:/mai/wt/foothold-lab/verifier-w56/_out/reports/VERIFY-EX40-W57-RETRY-1031.md` |
| H1 수정 전 | 258394c3 고정 archive | 14입력 중12개 일치, 키 누락2개 불일치 | [H1-BEFORE.json](H1-BEFORE.json) |
| H1 수정 후 | 5c160641 | 14/14 일치, 프로세스 종료값0 | [H1-AFTER.json](H1-AFTER.json) · [같은 시험 코드](check_h1.py) |
| 문턱·기타 생산 코드 변경 | 258394c3 → 5c160641 | 오차 키 검사 두 줄뿐. 그 밖은 시험·보고·원출력 | git diff |
| 실행 원본 보존 | 05:19:29 | 2df419b0 tracked 변경0, 학습·감독 생존, 원 B13/W57 SHA 동일 | [READBACK-0520.json](READBACK-0520.json) |

14입력은 B0와 B2 각각에서 완료0/명시적 null, 완료0/키 누락, 완료1/null, 완료 개수 누락, 완료0/NaN, 완료1/NaN, 완료0/유한 오차다. 명시적 0/null만 B0 기록 PASS 또는 B2 성능 FAIL이며, 나머지 결손·상충은 HOLD다. 전체64건을 최종 수정 뒤 다시 실행했다고 주장하지 않는다. 독립 전체 검토1회 뒤 지적 지점만 재확인했다. 최종 `ex40_score.py` SHA는 `09041dd79bc73463c23548e188759747773ca483d97b1875b3792a84588396d4`다.

verifier Dispatch `ctx_7910301b1531`와 H1 고침 scripter Dispatch `ctx_01e6f51dcab1`는 결과·파일을 확인해 정산하고 기존 창을 retained로 두었다. 새 작업을 남겨 두지 않았다.

### lead에게 넘길 적용 절차와 남은 제약

1. 새 평가 전용 사본과 HEAD는 위 5c160641로 고정한다. 본학습 사본2df419b0는 그대로 둔다.
2. 실패 회차의 `eval_receipt.json`에 맞는 checkpoint·설정·단계표 SHA로 `ex40_w57_retry --check-only`를 먼저 수행한다. 역사적 B13은 f1fff17f 단계표를 써야 하며, 현재 표식만 다른 2df 단계표로 읽으면 거절되는 것이 맞다.
3. W57 재평가 자체는 고유 attempt ID와 새 출력 폴더를 사용한다. 첫 다섯 단계는 SHA가 맞는 원자료만 재사용하고, 원 실패·성공·재시도 이력을 별도 원장으로 연결한다. 새 코드로 Kit를 실행하는 단계는 아직 하지 않았다.
4. 자동 점수기 전환은 별도 미완료다. 감독기는 frozenROOT를 호출하므로 이 사본으로 자동 교체되지 않는다. 재시도 원장도 primary HOLD를 대신 소비하지 않는다. 기존 primary의 HOLD를 지우거나 같은 회차 행을 중복 추가하면 안 된다.
5. lead에게 제안한 추가 구현 범위는 새 평가 기록자가 `watch.lock`으로 하나만 돌면서 **아직 primary에 없는 회차의 정규 결과만** 추가하고 실패 attempt는 별도 보존하는 것이다. 이 방식은 기존 원장에 신규 행을 쓰므로 「원장 건드리지 말 것」 범위 확인이 필요하다. `stage_reports` 동시성과 구 감독의 실제 소비까지 CPU로 검증하기 전에는 적용안 확정이 아니다. 질문 `msg_f12d4b6d9027`, 응답 대기. 프로세스 종료·고정 ROOT 수정 방식은 제안하지 않았다.

따라서 현재 완료 범위는 **평가 전용 수정·재시도 도구·CPU 검토**다. 본학습의 다음 W57 호출에 반영됐다는 보고는 아직 할 수 없다. 코드 오류 H1은 닫혔고 적용 범위 제약1이 남았다.

### m500 관찰 인계

- 05:18:57 학습 상태: running, iter150, 25.5889초/회. 05:19:29 `model_500.pt`와 `score-watch`는 아직 없다.
- runner 관찰기 PID21272가 실제 저장본 SHA, manifest, 평가 PID, 장치 로그를 읽는다. 자기 알림 PID42372의 ASCII 시험은 05:10:25 사용자 입력으로 도착했다.
- m500은 약07:40이라는 추정 대신 실제 도착을 기준으로 한다. 이후 평가 자식의 `cuda:1`/Kit 장치와 GPU1 UUID를 대조해 lead에게 한 줄 보고한다. 학습 PID가 양 GPU의 CUDA 컨텍스트 목록에 뜨는 것은 평가가 GPU1에서 돈다는 증거가 아니다.

## 05:3x 결정 반영 · 여기서 추가 구현 종료

lead 답으로 질문 `msg_f12d4b6d9027`은 닫혔다. **live primary 원장·감독기·고정 ROOT 보존, scorer-only 전환 추가 구현 없음.** 단계 끝 저장본의 별도 W57 실행은 lead가 그때 결정한다. 단계 끝 보고에서 W57 칸은 **「보류 · retry 원장 참조」**로 읽고, 별도 결과가 나와도 primary 채택이나 감독기의 HOLD 해소로 표현하지 않는다. 앞 절의 전환안은 미채택 이력이다.

최종 평가 사본은 `5c160641`다. 요청에 적힌 `258394c3`은 독립 검토 당시 판이며, 그 검토에서 나온 H1만 고친 최종 판과 구분한다. 추가 verifier 의뢰나 전체 시험을 다시 돌리지 않았다.

### 준비한 실행 명령 한 줄 · 실행하지 않음

PowerShell용이다. 아래 `$n=1500`만 실제 단계 끝 저장 번호로 바꾼다. 저장본 SHA로 원 평가 폴더를 고르고, 날짜·시각이 들어간 새 attempt 폴더와 별도 retry 원장만 만든다. 사본의 고정 설정은 `device=cuda:1`, 64환경, level2, 300스텝이며 실제 Kit 해석기는 wrapper의 `isaac311`이다. 명령을 시작하는 `isaac311-moects` Python은 CPU 재시도 조율용이다.

```powershell
& { $ErrorActionPreference='Stop'; $n=1500; $base='C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313'; $ck="$base/main/EX-40-B-main_20261031_041337_26240/model_${n}.pt"; $digest=(Get-FileHash -LiteralPath $ck -Algorithm SHA256).Hash.ToLower(); Push-Location 'C:/mai/wt/foothold-lab/scripter-ex40-w57-retry'; try { if ((git rev-parse HEAD).Trim() -ne '5c1606412e9876b7c3105756f378b4a5a629e73c') { throw 'evaluation HEAD changed' }; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -m foothold_s2.ex40_w57_retry --prior-eval "$base/score-watch/model_${n}_$($digest.Substring(0,12))" --checkpoint $ck --retry-root 'C:/Users/AI-WS01/s2_lab/ex40_w57_retry_separate_20261031' --attempt-id "m${n}-$(Get-Date -Format yyyyMMdd_HHmmss)"; if ($LASTEXITCODE -ne 0) { throw "W57 retry rc=$LASTEXITCODE" } } finally { Pop-Location } }
```

**현재 도구의 범위:** 원 평가 영수증이 `state=failed`, W57 자식 rc가 0이 아니고, 다른 필요한 단계는 rc0일 때 쓰는 명령이다. W57 실행은 rc0인데 옛 점수기만 HOLD한 경우나, 앞선 HOLD 때문에 다음 회차의 원 평가 폴더가 아직 없는 경우에는 이 도구가 거절한다. 없는 실패 영수증을 만들어 통과시키지 않는다. 이 경우도 W57 칸은 보류로 두고 lead의 단계 끝 결정에 넘긴다. 해당 범위를 넓히는 구현은 이번 결정대로 하지 않는다.

별도 결과 위치는 `C:/Users/AI-WS01/s2_lab/ex40_w57_retry_separate_20261031/w57_retry_model_<N>_m<N>-<시각>/`, 원장은 같은 root의 `w57_retry_ledger.jsonl`이다. `retry_receipt.json`·`score.json`에 원 실패 영수증 SHA와 attempt ID가 연결된다. 새 Kit 실행·실제 retry 결과 생성은 미실행이다.

## 이력

| 시각 | 내용 |
|---|---|
| 04:46 | 작업 범위·실제 실행 상태·고정 감독기 교체 제약 기록. 새 평가 사본의 구현과 관찰기 준비 진행 |
| 04:53 | 기존 소비기 CPU 반례·원본 해시 보존·알림 도착 확인. scripter 첫 묶음 및 남은 소비 경로 기록 |
| 05:11 | 258394c3 보완본, verifier 1회 검토 시작, m500 관찰기 CPU 재확인, ASCII 깨우기 실제 도착 기록 |
| 05:20 | verifier H1 지적→scripter 5c160641→analyst 같은 입력14개 재확인. live 적용 범위 제약과 m500 대기 분리 |
| 05:40 | lead의 별도 retry만 채택 결정 반영. 전환 추가 구현 종료, 명령 한 줄과 기존 도구 적용 조건 기록 |
