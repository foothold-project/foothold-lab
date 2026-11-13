# E1 경계 R2·R3·R4·새 R5·R6 읽기 전용 판독기

> 분류: A/평가
> 작성: analyst-lx · 2026-11-13
> 근거: 이슈 #765 · 원장 73abb340 · 04f50b4f R6 정정 · 0a5c1629 R5 정정 · #779 985ce6ab §3~4
> 요지: 실제 점수와 원자료를 읽어 비교표·발동 규칙·다음 구간 처방·조정 JSON 초안을 만든다.
> 상태: CPU 답 아는 입력 106개 통과 · 요청·소비 경로 돌연변이 12개 검출 · m250 실제 경계는 결과 대기
> 판: v1.4

**이 도구는 학습을 시작·중단하거나 설정을 적용하지 않는다.** 입력은 읽기만 하며 결과는 요청한 `/home/jay/mai/tmp/analyst/e1-boundary-rules-1113` 아래에 쓴다. 기본 부모는 P1 예행 v16의 m13250이다. 자료가 없는 상태를 0이나 PASS로 채우지 않는다.

## 실행

첫 경계 점수가 완성된 뒤 다음 한 줄을 실행한다. 이후에는 명령 안의 `m250` 두 곳을 같은 회차로 바꾼다. 직전 경계와 그 앞 경계가 같은 점수 폴더에 있으면 자동으로 읽는다. 따로 있는 경우 `--previous`·`--earlier`로 지정한다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B /home/jay/mai/tmp/analyst/e1-boundary-rules-1113/boundary_read.py --score /home/jay/data/foothold/s2_lab/ex42_main_20261113_174400/main/EX-42-B-E1-again_20261113_174400/eval/scores/m250/ex42_score.json --out /home/jay/mai/tmp/analyst/e1-boundary-rules-1113/m250
```

| 산출 | 내용 |
|---|---|
| `REPORT.md` | 한 줄 처방·칸별 현재/부모/직전·차이·단위·조건 일치 |
| `cells.csv` | 표의 원 숫자. 반올림 전 계산값 보존 |
| `mode_cells.csv` | GT·PRED 판정 열과 지도 끔 기록 열을 같은 명령·레벨·성분끼리 나란히 배치. 없는 값은 빈 칸 |
| `report.json` | 입력별 SHA·유지/졸업 판정 분리·현재 보상·처방 직전 고정 기준·규칙별 사유 |
| `adjustment.draft.json` | `apply_ready=false` 포장 안의 `payload`. 변경이 없거나 자료가 불완전하면 null |
| `next_segment.txt` | 다음 구간 처방 한 줄 |

종료 코드 0은 **도구 계산 완료**이지 학습 승인이나 유지 PASS가 아니다. `R4`도 보고 생성에 성공하면 rc0이며 `next_segment=DO_NOT_START`를 반드시 읽는다. 입력 부족은 rc2다. 운영 폴더·s2_lab 아래로 결과를 쓰는 호출은 거절한다. 스크립트에는 `--apply` 옵션이 없다.

초안 payload는 실제 `ex42_segment_adjust.resolve`로 형식을 검사한다. 기존 구간의 명령·보상·저속 표본 몫을 영수증에서 보존하며, 이번 경계에 바꿀 보상 묶음만 더한다. 기존 파일에 자동 덮어쓰기하거나 환경변수를 바꾸지 않는다. `DRAFT` 표식을 승인 문구로 바꾸는 일도 이 도구가 하지 않는다.

## 고정 규칙

| 규칙 | 구현한 조건 | 제안 |
|---|---|---|
| R4 | `maintenance_judgement`가 FAIL/HOLD. 전체 졸업 `judgement`와 구별 | 다음 구간 미기동·lead 확인. 최근 보상 처방의 직전 값만 복원 초안 |
| 두 경계 되돌림 | GT 또는 PRED의 **같은 모드·명령·레벨·성분**이 처방 직전 고정 기준보다 두 연속 유효 경계 악화 | 가장 최근 처방의 직전 값. checkpoint/optimizer를 되돌리지 않음. 지도 끔은 기록 |
| R6 첫 활성 | GT·PRED × L0/L5 × 전진0.1/0.2 여덟 칸 중 하나라도 R<0.3/0.6 | slow_track 0→0.2. 첫 경계부터 적용 가능 |
| R6 증량 | 0.2 상태에서 여덟 칸 모두 직전보다 비증가. GT·PRED 어느 한 칸이라도 증가하면 그대로. 유지 회귀·결측이면 증량 보류 | 0.2→0.3 최대 한 번 |
| R2 | GT/PRED 각각 전진1.0 Y1 중앙값>0.10 또는 p90>0.20 rad | zero_yaw −1→−1.25. 더 큰 벌점으로 반복 강화하지 않음 |
| R3 | R6와 R2가 겹침 | R6 묶음 하나만 |
| 새 R5 | R6 이후 GT·PRED 두 경계 무회귀, GT·PRED × 전진0.2 × L0/L5 네 칸 모두 R≥0.5, 같은 접촉 정의 발 자료 충족 | 공중 시간 기준 0.04초·가중 0.1 한 묶음. 지도 끔은 이 진입 조건에서도 기록만 |

R1 폭 좁히기와 옛 R5는 73abb340으로 대체됐다. 결측 때 되살리지 않는다. R5보다 R2를 먼저 확인하며, 처방 변경 뒤 두 경계 관찰 중에는 다른 묶음을 추가하지 않는다. 원장의 명시적 예외인 R6의 다음 경계 증량은 따로 판독한다.

반복 폭은 실행 plan의 v2 값과 같은 0.1 R 0.007, 0.2 R 0.026, Y1 중앙값 0.02 rad, p90 0.04 rad를 쓴다. 문턱 근처에서 처방을 새로 제안하려면 seed7·13의 같은 조건도 필요하다. 증량 비교가 0 근처이면 두 저장본의 같은 시드끼리 비교한다. 시드끼리 평균하거나 GT/PRED/끔을 합치지 않는다. 해당 자료가 없으면 `REPEAT_REQUIRED`다.

두 경계 되돌림은 회전 비율 감소>0.05, 옆 각 방향 R 감소>0.05, Y1 중앙값 증가>0.02 rad 또는 p90 증가>0.04 rad, stand 성공 감소≥4 env, stop 몸속도 증가>0.02 m/s 또는 각속도 크기 증가>0.05 rad/s를 그대로 읽는다. 대칭비만 좋아지거나 나빠진 것을 단독 처방 이유로 쓰지 않는다. 부족한 창은 회복이나 연속 악화로 세지 않는다.

유지 점수는 GT 13칸·PRED 13칸의 명령 이름과 `judge` 역할을 각각 확인한다. 합계가 26이라는 이유만으로 GT·지도 끔을 잘못 받아들이지 않는다. PRED 유지 실패는 전체 요약이 PASS여도 R4이며, 직전 PRED 유지 실패를 증량 근거로 쓰지 않는다. 지도 끔의 수치와 기준 대비 악화는 `regression_record_only`에 남기되 처방을 발동시키지 않는다.

## 수치·현재 설정의 출처

- 전진0.1/0.2 R: NPZ 몸앞 vx를 생존 샘플에 대해 적분, **예정된 전체 6초·시작 64 env**를 분모로 사용. 생존자만 남기지 않는다. R과 추종 오차·정체 수는 별도 열이다.
- Y1: 출발 yaw를 붙이고 각도를 unwrap한 뒤, env별 마지막 유효 시점의 **순 yaw 절댓값** 중앙값·p90. 부호 중앙값의 절댓값이나 누적 절대 회전량과 다르다.
- 옆 R: map JSON의 env별 명령 방향 투영거리 / 명령 거리. 이 NPZ에는 vy 시계열이 없어 옆 거리를 NPZ에서 재계산했다고 쓰지 않는다.
- stand 성공: 기존 `ex40_score._stand_pass`의 접촉·하중·발틈·몸속도·yaw 기준과 `ex40_score_config.json` 값을 사용한다. 생존만으로 성공을 대신하지 않는다.
- 초기 보상: 고정 v19 plan SHA와 실행 manifest의 실제 env 설정을 대조. 첫 구간에는 별도 RewardManager 영수증이 없으므로 `configured_manifest_initial`로 한계를 표시한다.
- 이후 보상: `segment_commands_bN.json`과 두 rank의 `segment_rewards_bN_rank*.json`을 대조한다. 이전 처방 앵커는 적용 직전 m(N×250)이며 비교 때 계속 고정한다.
- 현재와 과거 점수는 실행 manifest의 같은 local 회차 checkpoint SHA·plan과 맞아야 한다. 부모는 startup이 핀한 m13250 SHA와 맞아야 한다. 학습 회차와 누적 회차를 섞지 않는다.

R5는 `--gait`로 동일 checkpoint의 `norm_Fxyz_gt_1N` 발 자료를 받는다. 계약 예시는 `r5-contact-evidence.template.json`에 있다. 현재 Fz만 있는 자료는 이 계약을 충족하지 않는다. **R5 자료 미비는 R5만 보류하며 E1 전체를 중단하는 새 관문이 아니다.** 발별 완전 구간·참여 env·짧은 구간 비율·발 높이·끌림·원자료 SHA가 필요하다. 이 도구는 그 GPU 자료를 생성하지 않는다.

## 답을 아는 실제 자료 재생

`validation.json`과 아래 폴더는 생성기로 다시 만든다. 과거 자료는 당시 실제 설정을 새로 승인하는 용도가 아니다.

| 입력 | 기대한 결과 |
|---|---|
| 부모 P1 예행 자체 | `BASELINE_ONLY`, 부모 대비 수치 차이 모두 0. 전체 졸업 FAIL을 R4로 오인하지 않음 |
| cmd7seg m500 | `EVIDENCE_HOLD`. GT 저속 값은 재계산 가능하지만 PRED 저속 네 칸이 원자료에 없음. 초안 없음 |
| cmd7seg m750 | `EVIDENCE_HOLD`. 동일하게 PRED 저속 네 칸 미확인. GT만으로 처방하지 않음 |

과거 G1b는 `ex42_mesh=null`인 별도 생성 지형이며 GT만 있다. 부모와 메시가 같다고 주장하지 않는다. `--historical`은 이 차이를 경고로 남겨 **규칙의 반사실 재생**만 허용한다. PRED 값을 GT로 복사하거나 지도·지형·시드를 평균해 채우지 않는다. 19:24 정정 전 v1.1의 GT-only R6 재생과 달리 v1.2는 두 과거 저장본 모두 증거 부족으로 남는다. 새 운영 경계에는 `--historical`을 쓰지 않는다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B /home/jay/mai/tmp/analyst/e1-boundary-rules-1113/replay_known.py
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B -m pytest /home/jay/mai/tmp/analyst/e1-boundary-rules-1113 -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst/e1-boundary-rules-1113/pytest-recheck
```

원장 원문: [73abb340](https://github.com/foothold-project/foothold-lab/commit/73abb340a6175fc4316f08d87d66f8d51ee5bc5a), [19:24 정정 04f50b4f](https://github.com/foothold-project/foothold-lab/commit/04f50b4faca0b2b351d6bb089c868ddf3eae4cf7), [19:45 R5 정정 0a5c1629](https://github.com/foothold-project/foothold-lab/commit/0a5c1629). R5·되돌림 근거: [#779 문서 §3~4](https://github.com/foothold-project/foothold-lab/blob/985ce6ab/inbox/jay/20261113-analysis/DESIGN-SLOW-TRACK-R5-R6-1113.md). 18:42의 GT 네 칸 결합은 19:24 원장 정정과 lead 19:28 지시로 GT·PRED 여덟 칸으로 대체됐다. 19:45 결정은 R5의 전진0.2 바닥값에도 PRED를 포함했다.

## #784 문턱 시험 보강

확인됨: 정상 코드 106개 통과. 아래 고침을 **각각 격리 사본**에 넣으면 해당 행의 시험이 실패한다. v1.3은 시험 보강만, v1.4는 새 결정에 따라 R5의 전진0.2 바닥값을 GT·PRED 네 칸에 적용했다. `mutation_validation.json`에 실패한 시험 이름과 로그 경로를 남겼다.

| 잘못 바꾼 값 | 답을 아는 입력과 정상 결과 | 검출 |
|---|---|---|
| R6 전진 0.2 문턱 0.60 → 0.50 | 다른 칸은 양호, GT·PRED 중 L0 또는 L5의 R=0.55이면 R6. R=0.60에서는 비발동 | 4개 실패 |
| R2 중앙값 0.10 → 0.15 | p90=0.19, GT 또는 PRED 중앙값=0.13이면 R2. 0.10에서는 비발동 | 2개 실패 |
| R5 관찰 기간 500 → 250 | 활성 뒤 250·499회는 관찰 미완료, 500회부터 완료 | 2개 실패 |
| 서 있기 하락 4개 이상 → 4개 초과 | GT 또는 PRED 고정 기준 64, 두 창 모두 60이면 되돌림. 61이면 비발동 | 4개 실패 |
| 되돌림 기본 인자 GT·PRED → GT만 | 기본 반환 계약에 PRED 회전·stand 축을 포함하고 지도 끔은 제외 | 1개 실패 |
| 되돌림 실제 소비 경로 GT·PRED → GT만 | PRED 회전·옆·Y1·stand·stop 중 같은 성분이 두 창 악화하면 실제 처방 되돌림 | 7개 실패 |
| 직전 경계 PRED 유효 판정 삭제 | PRED FAIL/HOLD/누락인 창은 두 번째 악화 창으로 세지 않음 | 3개 실패 |
| 증량 직전 PRED PASS 검사 삭제 | 여덟 칸이 모두 내려가도 직전 PRED FAIL/HOLD/누락이면 증량 초안 없음 | 3개 실패 |
| 현재 GT·PRED 유지 판정 누락 검사 삭제 | 전체 PASS라도 GT·PRED 어느 판정이 없으면 `EVIDENCE_HOLD` | 3개 실패 |
| 13칸 이름 대조 삭제 | 실제 부모 점수의 stop 이름만 바꿔 13칸을 유지하거나 한 칸 삭제하면 거절 | 6개 실패 |
| R5 전진0.2 바닥값 GT·PRED → GT만 | PRED L0 또는 L5의 R=0.4999, 나머지는 양호해도 R5 비발동 | 2개 실패 |
| R5 바닥값 0.5 이상 → 0.5 초과 | GT·PRED 각 L0/L5 한 칸이 정확히 0.5이고 나머지가 양호하면 R5 발동 | 4개 실패 |

R5 시간 조건은 기존의 두 경계 확인 조건과 겹친다. 정상 250회 경계 이력에서는 시간 조건만 잘못 바꿔도 다른 조건이 조기 R5를 막으므로, 시간 조건을 실제 `decide()`가 호출하는 `r5_observation_complete()`로 분리했다. **시간 조건의 단위 시험**과 **+250회 비발동·+500회 발동의 전체 판정 시험**을 함께 둔다. 이 차이를 숨기거나 불가능한 처방 이력으로 전체 판정 반례를 만들지 않았다.

19:36 reviewer의 첫 변형은 `rollback_limits()` 기본 인자만 GT로 바꿨다. 실제 `regression()` 호출은 모드를 명시하므로 그 변형만으로 실행 판정이 달라지지 않는다. 기본 계약 시험과 실제 소비 경로를 GT만으로 바꾼 시험을 구별해 적었다. 직전 PRED 검사도 증량 전에 한 번 더 있으므로, reviewer 변형은 두 번째 악화 창 채택 경로에서, 별도 변형은 실제 증량 경로에서 검출했다. 예외가 우연히 나거나 모듈을 못 불러온 것은 검출로 세지 않는다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B /home/jay/mai/tmp/analyst/e1-boundary-rules-1113/check_mutations.py --out /home/jay/mai/tmp/analyst/e1-boundary-rules-1113/mutation-check
```

| 판 | 변경 |
|---|---|
| v1.0 | 확정 규칙·원자료 판독·초안·기존 구간 보존·25개 CPU 시험 |
| v1.1 | 요청 문턱 네 곳을 겨냥한 24개 시험 추가, 네 돌연변이 실행 검증, R5 시간 조건만 같은 식으로 분리 |
| v1.2 | 19:24 결정: GT·PRED 여덟 칸 R6, 두 지도 유지·되돌림, 지도 끔 기록, 나란한 표, PRED 없는 과거 재생 보류 |
| v1.3 | 19:38 재검 지적 네 곳의 실패 시험, 실제 소비 경로 두 변형 추가. 판정 코드는 v1.2 그대로 |
| v1.4 | 0a5c1629: R5 진입 전진0.2 바닥값도 GT·PRED 네 칸 모두 적용. 누락은 보류, 지도 끔은 기록 |
