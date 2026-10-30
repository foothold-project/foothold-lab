> 분류: A/평가 · EX-40 B11 통합 수정 기록
> 작성: runner · 2026-10-31
> 근거: TASK-B11-all-fixes.md · verifier VERIFY-EX40-B11-1031.md · 고정 사본 bdb32f3d
> 요지: H1~H3/P1~P3 여섯 막음을 한 후속 사본에 통합하고 CPU 결과와 미확인 범위를 기록한다
> 상태: 코드와 CPU 검증 완료 · P1 운영 연결 1건 잔여 · GPU/Kit/B14 금지

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
