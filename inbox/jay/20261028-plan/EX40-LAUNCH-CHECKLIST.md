> 분류: 실험 실행 점검표
> 작성: lead · 2026-10-30 21:5x
> 근거: WORKLIST D57 · D59 · D62 · D65 · D66 · D68~D77, FAILURE-LOG R1~R25 · M01~M77, FLOW-experiment-cycle-1029 8 단계
> 요지: EX-40 기동 전에 끝내야 할 일과 학습 중 자동으로 돌 일을 한 장에. 칸이 모두 「끝 + 증거」가 되어야 기동한다.
> 상태: B12 PASS · B13 map64/B3/정지 PASS·W57 기록 완료/점수 미결1 · 최종2df419b0 main DRY PASS · B14 LIVE=1은lead

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
| B6 | DR 일정·이벤트·readback·확인기 | runner · scripter(실제 Kit 결함) | 합친 f1fff17f 실제 Kit PASS | 최초 gain 폭8/4 기록 결함 고침 보존. B12 18개 train_extra, reset probe0/6000/6001/7501의 배율0/0.5/1/1, 관측 잡음1×고정, 실제gain·COM·밀기·지연 readback 대조. B12-INDEPENDENT.json |
| B7 | 코드: 그림자 점수기(8 단계 이름 · 원장 · 단계 끝 전체 평가 · 끝난 뒤 잔여 평가) | scripter | CPU 끝 | 1910d2fb (scripter-ex40-score-v8) |
| B8 | 코드: 단계 끝 자동 보고(얻은 점 · 잃은 점 · 앞 단계 대비 칸별 변화 · 발별 정지 · 좌우) → lab 페이지 · 텔레그램 요지 | scripter | CPU 끝 · lab 첫 화면 링크는 갱신기 소유(남음) | 1910d2fb · lab_status/ex40_stage_reports.html · tg_send.py |
| B9 | 코드: 재개 감시기(마지막 온전한 저장본, 3 회 연속 실패 시 멈춤) | runner | P1 source 고침68161fc7 독립 확인 끝 | verifier §11/r6: 정상1550/1600·분리31개 consumed, target 누락/HOLD/SHA충돌 및 현재 같은 회차 다른SHA 거부. 반복재평가/추가발신0. 실제 장기 재개는 미확인 |
| B10 | v7·v8·점수기·보고 통합 | runner · analyst(승인된 합침만) | Kit 고정f1fff17f와 표식만 바꾼 최종2df419b0 구분 | 68161fc7 + e53f63de 전체tree 정확합·CPU40건. 새 analyst-ex40-main-verified-1031은 runtime_adapter_status 1줄+증거문서만 변경, detached·clean·원격HEAD일치 |
| B11 | verifier 최종 재검증: 문서 · 카드 · 코드 · 설정 · 재개 · 점수기 · 보고, 막음 0 | verifier | §11 P1 닫힘 유지, §12 표식 변경분 main DRY 준비 막음0 | 2df419b0 부모f1fff17f exact diff2파일·원자료SHA10/10. 새HEAD의 실제 main DRY는prestart_pass. W57 점수소비 한계는B13으로 분리 |
| B12 | 학습 Kit 짧은 확인(GPU0): 단계·실제DR·L0~2·광선·발별기록 | analyst(직접위임) | 03:11:46 실제18갱신 done, rc0·검사PASS. 첫 실패 보존 | f1fff17f·env3072·seed42, 8단계0/2/4/6/8/10/12/14 일치. model17 SHA b7232f73…92ced8 재해시·status·manifest 일치, 발별127616 유효 표본, hit1.0. L0/1/2=1034/1025/1013. 평균27.374s/갱신. 보고 analyst-ame2/_out/reports/ex40-coord-1031/B12-B13-KIT-1031.md |
| B13 | 점수기 Kit(GPU1): 단계끝 전체평가1회·실제시간 | analyst(직접위임) | map64·B3·정지 PASS, W57 단독rc0·원자료완료. 전체점수 미결1 | 첫 전체시도31분42.484초·rc5·원실패보존. 승인된W57만 새폴더1회11분38.685초·30칸×64env·원자료SHA30개일치. m17 목표정지18칸오차null → 점수기EvidenceHold. 전체PASS영수증·최종표·5PNG미생성. analyst-ame2 451dc72b B12-B13-KIT-1031.md |
| B14 | 기동: 시작 스크립트 · 고정 사본(detached) · 실제 경로 점검 · END_BY ≥ 예상 끝 + 24 h · GPU0 | lead | 2df419b0 LIVE=0 main DRY rc0·prestart_pass. 실제 LIVE=1 안 함 | s2_lab/ex40_main_dry_20261031_040426/receipts/ex40_b11/B_main_20261031_040427_1129247. 명령·ETA·점수기미결은 analyst-ame2 451dc72b B14-PREP-1031.md. 03:5x 지시로W57미결과기동준비 병행 |
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

- B12 18갱신 실측 평균27.374444초. 8001갱신 약60.84시간, 관측속도 범위를 대입하면57.10~65.48시간. 장기·GPU1평가 병행속도는 미측정이며 첫50갱신 뒤 갱신한다.
- 시작 대비 단계 끝 추정: B0 11.41h · B1 22.82h · B2 34.23h · B3a 38.03h · B3b 41.83h · B3c 45.63h · D 57.04h · T0 60.84h.
- lead용 기동명령은 예상끝 시작+67h, END_BY 시작+91h(예상끝+24h), max-wall96h로 준비했다. 실제 시작 때 시간을 다시 계산한다. B12의 짧은 deadline을 복사하지 않는다.
- 250갱신 간격 약114.06분. 첫B13 실패시도31분42.48초(27.80%), 별도W57까지 두 실행의 시간합43분21.17초(38.01%). 시간합을 성공한 단일전체평가 실측으로 쓰지 않는다.

## 10/31 00:04 조정 인계

- analyst는 범위 고침 → verifier B11 → B12/B13 순서만 맡는다. B14는 시작하지 않고 명령·ETA·END_BY를 준비해 lead에 보고한다.
- R6 실제 Kit, R25 범위 보존, M02 고정 실행 사본, M76 실제값 대조, M77 마감 여유를 적용한다.
- 20분 재개 알림을 자신의 창에만 걸었다. 00:03:53 시험 문장이 실제 입력으로 도착했다. 자동GPU기동 기능은 없다. 로그: analyst-ame2/_out/reports/ex40-coord-1031/wake-status.log.

## 10/31 02:53 실제 Kit 실패 갱신

최신 직접 지시는 smoke 미사용 P1과 B12/B13을 병행하도록 바꿨다. 이에 b5bca3b5 고정 사본에서 B12를 한 번 실행했으나 첫 reset에서 실패했다. CPU 통과를 실제 Kit 통과로 쓰지 않는다. 원자료·해시·고침 의뢰는 `C:/mai/wt/foothold-lab/analyst-ame2/_out/reports/ex40-coord-1031/B12-B13-KIT-1031.md`. 02:56 scripter e53f63de의 CPU 고침을 독립 대조했다. verifier P1 확인은 별도로 진행하며 B13은 실제 저장본 대기, B14는 계속 금지다.

## 10/31 03:06 합친 고정본 재시도

lead의 최신 직접 답변으로 두 고침을 한 사본에 합친 뒤 B12 재시도1회, PASS면 동일 HEAD로 B13 한 번을 승인받았다. 최종 `f1fff17fecf82ac77fe843c9a48214f166b154ca`의 원격·로컬 HEAD와 clean, 전체 tree의 두 고침 외 변경0을 확인했다. 코드 diff check0, 보존한 수정 전 pytest 원출력에는 공백6줄 경고만 있다. B12는 실제 첫 reset을 넘어 학습 중이다. B14 본 기동은 하지 않는다.

## 10/31 04:08 W57 재시도와 최종 DRY

lead03:5x에 따라 첫다섯단계 재실행 없이 W57만 새폴더에서1회 확인했고, f1fff17f 기반 새고정본에 표식1줄·증거만 커밋했다. 최종HEAD `2df419b0a4278981f6bd26e5eaedecbf7e8458db`, 원격 feature/ex40-runtime-verified-analyst. verifier§12 변경분 확인 뒤 같은HEAD main LIVE=0 DRY에서 실제prestart_pass를 확인했다. B14 본학습은 시작하지 않았다.

W57의 첫호출은 B2끝m4500이 아니라 B0끝m1500(약11.41h)이다. `axis_goal OR boundary_record`를 실제31슬롯으로 확인했다. 또 실패한 평가가done/HOLD원장에 기록되므로 점수기 단순재시작은 해당회차를 복구하지 않는다. 학습·감독기·기존원장은 보존하고, 평가전용 고침본의 새폴더 측정과 정식재시도 연결이 필요하다. 현재 연결CLI는 없으며 문서만으로 구현됐다고 하지 않는다. W57 단독rc0 이후에도 m17의정지오차null을점수기가HOLD로읽어 최종전체기능PASS는미확인이다. 이둘을 B14판단자료에 분리해전달했다.
