> 분류: 실행 검증 · EX-40 조정
> 작성: analyst · 2026-10-31 02:38 KST
> 근거: b5bca3b5 · verifier §10/r5 results.json 및 split-trace.json · CPU34 원출력
> 요지: 누락 슬롯 반례는 닫혔고 정상 재개의 이전 segment 출처 연결1건을 같은 묶음에서 고친다.
> 상태: B11 막음1 · runner 후속 착수 · B12/B13 미기동 · B14 본 기동 금지

# EX-40 B11 P1 후속 대조

## 02:38 갱신

verifier §10과 `_out/ex40-b11-r5/pytest.txt`, `results.json`, `split-trace.json`을 직접 읽었다. 독립 CPU는 **34 passed in 10.05s**. m5250 checkpoint/state/ledger 동시누락은pending으로 바뀌어 이 반례는 닫혔다. 정상 단일segment31개와m5550은consumed, 이전segment의5250도consumed이며 반복 추가발송0이다.

남은 **P1 막음1은 정상 재개 출처 미연결**이다. 두 소비 자리가 같은 원인이다. 이전segment m1500 평가가 유효해도 새segment m1550/1600 종료는 target SHA를 현segment에서만 찾아pending이다. 31개를 두segment로 나눈 정상 입력도 슬롯31개verified, 보고8개done 뒤 과거 단계 m1500의 보고SHA를 현segment에서 찾아None이 되어pending이다. 실제 completion은done/evaluated31이다. 코드193~195행·236~239행, r5 trace의digest=null과 일치한다.

이를 `TASK-P1-segment-source.md`에 묶어02:36:26 runner에게 전달, request `775fb1d9-f96d-4874-8d8e-b6d9a552903d`의turn_started를 확인했다. b5b를 보존하고 목표·보고 두 자리의 검증된 출처만 연결한다. 정상 재개 두 경우, 누락·SHA충돌·HOLD 및 중복발송 없음은 같은 CPU 묶음에서 확인한다. 고침 뒤 verifier는 이 지적분만 확인한다.

**앞선 표현 정정:** 이 문서02:15절과 체크리스트B9에서 분리segment도supervisor consumed라고 합쳐 썼으나 r4는 분리자료의report/completion을 확인한 것이다. 분리31개supervisor consumed는 확인되지 않았다. r5에서pending이 재현됐으므로 그 표현을 좁혀 바로잡았다. 원자료와 과거 보고 파일은 보존했다.

## 02:33 갱신

runner 후속 `b5bca3b561293dded80e0209fb84eeae0fc5b807`의 clean 상태와 `_out/reports/CPU-P1-missing-slot-1031.txt`의 **34 passed in 9.52s**를 읽었다. 필요한 회차를 존재 파일이 아니라 config의 first/stride로 열거하고, 검증된 이전 segment 원장을 사용할 수 있게 바뀌었다. 아직 독립 검증 완료를 뜻하지 않는다.

verifier에게02:31:39 `TASK-B11-P1-slot-recheck.md`를 전달했고 request `b912d5fb-312b-4d47-9874-e3370dbf986c`의 turn_started를 확인했다. r4에서 닫힌 범위는 보존한다. 누락 반례와 함께, 이전 segment m1500 평가 뒤 새 segment가 첫 stride1750 전 m1550/1600에서 끝나는 정상 재개도 확인한다. `target_digest`가 현재 segment만 찾으면 정상 재개가 막힐 수 있으므로 그 결과를 받기 전 B11을 닫지 않는다.

02:25:36 깨우기 입력 수신. 02:29:37 W51 완료 원자료와 GPU 총계를 다시 읽었다. W51은12건 모두rc0,468칸, GPU0은0MiB/0%, GPU1은3132MiB/1%였다. GPU1 장치 총계는 학습 프로세스의 점유량으로 해석하지 않는다. B12/B13은 아직 미기동이며139f의DRY는 과거 준비 증거로만 보존한다.

다음은 지적분 verifier 결과 확인, B11전체0일 때 검증된 SHA의 별도 실행 사본과 fresh 출력 폴더에서 공식 B12 한 번, 통과 뒤 B13 한 번이다. B14는 기동하지 않는다. 아래 시각별 기록은 고침 이력이다.

## 02:15 갱신

runner의 코드 `3afb0d6b37317c6e3a8caef7737150e68c1f3432`, 보고 포함 고정 HEAD `139f0d2dd9089c25d660a7f4d2e0052c5552c15e`를 clean 상태로 확인했다. verifier에게02:07:54 동일 P1 변경분을 전달했고 request `9a213f0a-e223-40cf-b0d4-33f41239bf61`의 turn_started를 확인했다.

`verifier-w56/_out/ex40-b11-r4/pytest.txt`의 **33 passed in6.75s**와 `results.json`을 직접 읽었다. 실제 보고 함수는 published8(int), fake sender8회이고 재소비해도8회였다. 정상 단일segment31개는consumed, 분리segment는report/completion만 확인했다(02:38 표현 정정). HOLD·SHA불일치·평가영수증 누락은 거부됐다. 살아 있는 가짜 자식의 wait 이전 점수 호출도 기록됐다. 실제 Kit·실제 Telegram 수신은 이 CPU 결과에 포함되지 않는다.

**남은 한 반례:** 비stride m5550에서 m5250 checkpoint 파일과 score 행을 함께 제거하면 `missing_checkpoint_and_score5250=consumed`. 정상 m5550도 consumed였다. `ex40_supervisor.py:190~209`는 현재 존재하는 파일 집합만 순회하여 이 누락 회차를 세지 못한다. 해당 원출력과 코드로 판단했으며 analyst가 verifier 원자료를 다시 실행하거나 수정하지는 않았다.

이 지적을 `TASK-P1-missing-slot.md`에 한 묶음으로 적어 runner에게02:14:16 전달, request `f56a12b1-17ba-4246-9271-65bad9946063`의 turn_started를 확인했다. 누락 집합 검사와 정상 segment 출처 보존만 고치며 기존 닫힘을 다시 열지 않는다. verifier 최종 보고와 후속 고침 확인은 남아 있다.

B12 준비 DRY는139f0d2d 공식 `run_ex40_b11.sh`에서 rc0, `prestart_pass`, source_git_clean=true, B scratch18회, 단계0/2/4/6/8/10/12/14를 확인했다. 영수증은 `C:/Users/AI-WS01/s2_lab/ex40_preflight_20261031_b11_139f/receipts/ex40_b11/B_smoke_20261031_020942_1121058/`. **LIVE=0이므로 GPU/Kit 학습은 시작하지 않았다.** 실제 기동은 후속 고정본 B11 막음0 뒤다.

02:08:39 GPU 장치총계0번0MiB/1번3109MiB, W51·EX40 학습/평가 python 프로세스 없음. W51은12개 rc0,468칸 완료 기록을 다시 읽었다. 02:05:20 깨우기 입력 수신. B14 금지는 유지한다. 아래01:55 기록은 당시 결함과 처리의 이력이다.

## 현재 사실

검토 대상은 `C:/mai/wt/foothold-lab/runner-ex40-b11-all-fixes`의 구현 `84ce82a6a8eae245f1cfd16ba0071d530581bc58`, 보고 기록 `de2510e764b44dfe23c98c6fe8e702e01b6c656d`다. runner의 좁은 CPU 결과는 보고에 30 passed in 6.74s로 기록되어 있다. 이 수를 전체 P1 통과로 간주하지 않았다. 코드는 child 생존 중 평가 호출과 segment별 출처를 추가했으나 아래 문제가 남았다.

| 항목 | 직접 확인 | 판정 |
|---|---|---|
| 실제 보고 반환형 | `ex40_supervisor.py:222~225`는 `reports['published']`의 원소를 순회한다. 실제 `ex40_score_watch.stage_reports`의 마지막 반환은 `published: len(published)`로 정수다. | 정상 보고가 있는 분기에서도 TypeError 위험. 기존 P1의 코드 오류 |
| 운영 전달 연결 | 감독기223행은 telegram_sender=None, 237~238행은 --no-telegram 및 score_out 안 lab_feed를 고정한다. 공식 셸에는 운영 publish-worktree·실제 lab-feed·sender 전달 인자가 없다. | 로컬 보고 생성과 B8의 lab·요지 전달은 별개. 기존 P1/B8 연결 미완료 |
| 이전 닫힘 | verifier §8 및 `_out/ex40-b11-r3/pytest.txt`, `results.json`을 읽어 127 passed in31.05s와 final-only/누락/HOLD/SHA/영수증 반례를 확인했다. | 기존 final completion 수정의 한정 닫힘은 보존. 신규 후속 코드는 아직 verifier 판정 전 |

## 답을 아는 실제 함수 호출

CUDA_VISIBLE_DEVICES를 해당 CPU 프로세스에서만 빈 값, PYTHONDONTWRITEBYTECODE=1, PYTHONPATH를 대상 고정 사본으로 두고 isaac311 python을 사용했다. own worktree의 임시 디렉터리에 빈 run/score 원장을 만들고 실제 `stage_reports(run,out,DEFAULT_CONFIG,TABLE,'B',telegram_sender=None)`를 호출했다. GPU·Kit·외부 전송은 없었다.

출력:

```text
{'state': 'pending', 'published': 0, 'first_pending': 1500, 'first_hold': None}
published_type=int
TypeError: 'int' object is not iterable
```

마지막 오류는 실제 반환값에 감독기225행과 같은 `{item.get('update') for item in value.get('published', [])}`를 적용한 것이다. 빈 원장은 보고서가 없는 정상 pending 입력이며, 반환형은 보고 개수와 무관하게 정수다. 이 검사는 완성된 학습 감독기 전체를 실제로 실행한 시험은 아니다. 코드의 두 실제 함수 계약 불일치를 재현한 CPU 측정이다.

## 처리와 다음 순서

- 기존 의뢰 `_out/reports/ex40-coord-1031/TASK-B11-all-fixes.md`의01:54절에 두 항목을 함께 적었다. runner에게01:54:30 전송, request `95f8139e-a9cc-481c-8c8a-ff47cac152c1`, turn_started 확인. 새 전면 검토를 요청하지 않았다.
- runner는 같은 사본에서 후속 커밋으로 고치며 검토된 HEAD와 원자료를 보존한다. 실제 운영 인자는 연결하되 CPU/B12/B13 기능시험에서 외부 발송은 하지 않는다. 정상 보고 함수와 fake sender 영수증으로 시험한다.
- 고정 후속 HEAD가 오면 `_out/reports/ex40-coord-1031/TASK-B11-P1-remaining.md` 범위로 verifier에게 P1 변경분만 한 번 확인받는다. H1~H3/P2/P3 전면 반복 금지.
- B11 전체 막음0 뒤 B12 GPU0 짧은 확인 한 번, PASS 뒤 B13 GPU1 전체 평가 경로 한 번. B14는 시작하지 않는다.
- lead 체크리스트는 `d28d893ef40c55271e3d6d346d6df25806b46036`에 final completion 닫힘과 학습 중 연결 미종결을 분리했고 원격 HEAD 일치를 확인했다.
- W51은00:42:15에12/12 rc0,468칸 완료. 결과·CPU audit `38aef2e5`, 원자료 `C:/Users/AI-WS01/s2_lab/basic_gait_runs/eval_actuator/w51_followup_20261030/`. 01:37 GPU0 0MiB/GPU1 3107MiB는 장치 총계이고 당시 W51 프로세스는 없었다. B13 기동 직전 재확인한다.
- 20분 깨우기 사용자 입력은01:45:04까지 실제 도착했다. 아직 COORD-DONE을 만들지 않았다.

## 연속성

미완료 목표: EX-40 B11 연결 확인, 승인된 B12/B13, B14 명령·ETA 준비와 lead 보고. 대기: runner P1 고침. B14 기동, 프로세스 종료, 실제 외부 시험 발송은 하지 않는다. 원대화는 `C:/Users/AI-WS01/.codex/sessions/2026/09/28/rollout-2026-09-28T01-46-37-01a0e3c2-ea62-70f0-94a8-3d6e2fdc0f85.jsonl`, 이번 재개 참조 위치6109994858이다. 요약·이슈는 원대화와 원자료를 대신하지 않는다.
