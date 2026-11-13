# E1 경계 R2·R3·R4·새 R5·R6 읽기 전용 판독기

> 분류: A/평가
> 작성: analyst-lx · 2026-11-13
> 근거: 이슈 #765 · 원장 73abb340 · 04f50b4f R6 정정 · 0a5c1629 R5 정정 · #779 985ce6ab §3~4
> 요지: 실제 점수와 원자료를 읽어 비교표·발동 규칙·다음 구간 처방·조정 JSON 초안을 만든다.
> 상태: 새 승인표 CPU 구현 · m1000 적용 확정 · m250/m500 재계산 완료 · 새 C1 Kit 자료는 미측정
> 판: v1.6

**이 도구는 학습을 시작·중단하거나 설정을 적용하지 않는다.** 입력은 읽기만 하며 결과는 요청한 `/home/jay/mai/tmp/analyst/e1-boundary-rules-1113` 아래에 쓴다. 기본 부모는 P1 예행 v16의 m13250이다. 자료가 없는 상태를 0이나 PASS로 채우지 않는다.

## 실행

첫 경계 점수가 완성된 뒤 다음 한 줄을 실행한다. 이후에는 명령 안의 `m250` 두 곳을 같은 회차로 바꾼다. 직전 경계와 그 앞 경계가 같은 점수 폴더에 있으면 자동으로 읽는다. 따로 있는 경우 `--previous`·`--earlier`로 지정한다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B /home/jay/mai/wt/foothold-lab/analyst-lx-terrain-d/inbox/jay/20261113-analysis/e1-boundary-rules/boundary_read.py --score /home/jay/data/foothold/s2_lab/ex42_main_20261113_174400/main/EX-42-B-E1-again_20261113_174400/eval/scores/m250/ex42_score.json --out /home/jay/mai/tmp/analyst/e1-boundary-rules-1113/m250
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
| 두 경계 되돌림 | GT 또는 PRED의 **같은 모드·명령·레벨·성분**이 처방 직전 고정 기준보다 두 연속 유효 경계 악화 | 가장 최근 처방의 직전 값. checkpoint/optimizer를 되돌리지 않음. 지도 끔 추종은 기록. 생존은 아래 de8 규칙 |
| R6 첫 활성 | GT·PRED × L0/L5 × 전진0.1/0.2 여덟 칸 중 하나라도 R<0.3/0.6 | slow_track 0→0.2. 첫 경계부터 적용 가능 |
| R6 증량 | 0.2 상태에서 여덟 칸 모두 직전보다 비증가. GT·PRED 어느 한 칸이라도 증가하면 그대로. 유지 회귀·결측이면 증량 보류 | 0.2→0.3 최대 한 번 |
| R2 | GT/PRED 각각 전진1.0 Y1 중앙값>0.10 또는 p90>0.20 rad | zero_yaw −1→−1.25. 더 큰 벌점으로 반복 강화하지 않음 |
| R3 | R6와 R2가 겹침 | R6 묶음 하나만 |
| 새 R5 | R6 이후 GT·PRED 두 경계 무회귀, GT·PRED × 전진0.2 × L0/L5 네 칸 모두 R≥0.5, 같은 접촉 정의 발 자료 충족 | 공중 시간 기준 0.04초·가중 0.1 한 묶음. 지도 끔은 이 진입 조건에서도 기록만 |

R1 폭 좁히기와 옛 R5는 73abb340으로 대체됐다. 결측 때 되살리지 않는다. R5보다 R2를 먼저 확인하며, 처방 변경 뒤 두 경계 관찰 중에는 다른 묶음을 추가하지 않는다. 원장의 명시적 예외인 R6의 다음 경계 증량은 따로 판독한다.

반복 폭은 실행 plan의 v2 값과 같은 0.1 R 0.007, 0.2 R 0.026, Y1 중앙값 0.02 rad, p90 0.04 rad를 쓴다. 문턱 근처에서 처방을 새로 제안하려면 seed7·13의 같은 조건도 필요하다. 증량 비교가 0 근처이면 두 저장본의 같은 시드끼리 비교한다. 시드끼리 평균하거나 GT/PRED/끔을 합치지 않는다. 해당 자료가 없으면 `REPEAT_REQUIRED`다.

두 경계 되돌림은 회전 비율 감소>0.05, 옆 각 방향 R 감소>0.05, Y1 중앙값 증가>0.02 rad 또는 p90 증가>0.04 rad, stand 성공 감소≥4 env, stop 몸속도 증가>0.02 m/s 또는 각속도 크기 증가>0.05 rad/s를 그대로 읽는다. 대칭비만 좋아지거나 나빠진 것을 단독 처방 이유로 쓰지 않는다. 부족한 창은 회복이나 연속 악화로 세지 않는다.

유지 점수는 GT 13칸·PRED 13칸의 명령 이름과 `judge` 역할을 각각 확인한다. 합계가 26이라는 이유만으로 GT·지도 끔을 잘못 받아들이지 않는다. PRED 유지 실패는 전체 요약이 PASS여도 R4이며, 직전 PRED 유지 실패를 증량 근거로 쓰지 않는다. 지도 끔 추종의 기준 대비 악화는 `regression_record_only`에만 남긴다. 생존은 아래 de8 절의 별도 60/64 규칙을 적용한다.

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
| v1.4 | 0a5c1629: R5 진입 전진0.2 바닥값도 GT·PRED 네 칸 모두 적용. 누락은 보류, 지도 끔 추종은 기록. 생존은 아래 de8 규칙 |
| v1.5 | H2: 임의 바이트 증거 거절, NPZ 접촉·발별 통계 재계산, 생성 체크포인트 대조 |
| v1.6 | de8a3b7f · 5f2e7c3b · 7ba9f2be: 지도 끔 21칸 생존, GT/PRED 진단, 곡선, m1750 분기, C1 기록. m1000부터 적용 |

## H2 접촉 원자료 계약 보강 (2026-11-13)

`--gait`의 `analyst-r5-contact-evidence/1` 요약과 SHA만으로는 R5를 열지 않는다.
각 `sources[]`는 아래 NPZ 원자료의 경로와 SHA256이어야 한다. 요약의 발별 숫자는 이 원자료에서 다시 센 값과 같아야 한다. 텍스트, Fz 전용 자료, 다른 저장본, 불완전 자료는 `valid=false`이며 R5만 대기한다. 이 도구는 학습 설정을 적용하지 않는다.

| NPZ 키 | 계약 |
|---|---|
| `format`, `producer` | `foothold-r5-contact-raw/1`, `foothold_s2.eval.ex42_gait_contact` |
| `run_identity` | JSON 문자열: 생성 체크포인트 `checkpoint_sha256`, `eval_seed=42`, `mode=eval_gt/eval_pred`, 실제 생성 코드 `code_head` |
| `contact_definition`, `foot_names` | `norm_Fxyz_gt_1N`, FL·FR·RL·RR 순서 |
| `dt`, `window_seconds`, `command` | 0.02 s, [1,6], 실제 느린 평행이동 명령 벡터. 속도 크기 0.1~0.3 m/s, wz=0 |
| `force_xyz_n` | 300×64×4×3, 월드 좌표 힘 N |
| `contact` | 300×64×4 bool. 원시 힘의 유클리드 크기 >1 N과 모든 표본이 같아야 함 |
| `foot_height_m` | 300×64×4, 발 아래 지지면 기준 발 높이 m |
| `foot_xy_speed_mps` | 300×64×4, 발 월드 수평 속력 m/s |
| `alive` | 300×64 bool, 첫 종료 이후 false 유지 |

집계는 1≤t<6 s의 생존 표본이다. 접지→공중→접지로 양 끝이 관측된 공중 구간만 세며, 창 경계에 걸린 구간은 제외한다. 발별로 공중 구간 수, 기여 env 수, 1표본 구간 비율, 공중 발 높이 중앙값, 끌림 비율(접지·높이<0.02 m·수평 속력>0.05 m), 공중 시간<0.5 s 비율을 다시 센다. 기존 R5의 최소 20구간·16env·짧은 구간 과반 조건은 바꾸지 않았다.

현재 runner m250 CSV는 원시 Fx/Fy/Fz와 접촉을 담지만 발 높이·속력은 없다. 따라서 위 NPZ를 이미 생산했다고 주장하지 않는다. 그 CSV로 요약의 높이·끌림을 채워 넣거나, 형식 이름만 바꿔 R5를 열 수 없다. 생산자 연결과 완전한 실측은 별도 필요하다.


## 23:04 승인표 추가 (de8a3b7f)

`boundary_approved.py`는 기존 R2/R4/R5/R6 결과 위에 읽기 전용 표를 얹는다. `original_rule_decision`은 기존 판독이고, 적용 전 경계의 `de8_counterfactual`은 새 규칙으로 보면 어떠한지를 기록한 것이다. 과거 결정을 바꾸지 않는다.

- 지도 끔: 연속 지형의 시작 64개를 분모로 생존 ≥60. 같은 칸이 직전 250 경계에서도 <60이면 최근 처방 직전 값으로 되돌림 초안. 첫 미달은 기록. 추종 오차는 처방에 사용하지 않는다. 자료가 63개뿐인 경우와 64개 중 63개 생존을 혼동하지 않는다.
- GT/PRED: 같은 과제의 GT 통과·PRED 미달은 지각 경로부터 점검, GT 미달은 정책·과제부터 점검. 원인을 확정한 인과 분석은 아니다.
- 곡선: 마지막 250회와 직전 250회의 lr 바닥 비율·진단 KL >2×desired_kl 횟수·noise std·에피소드 길이·보상 항을 기록. 바닥은 코드의 1e-5, desired_kl은 실행 agent.yaml. 진단 KL은 scheduler 미니배치 KL이 아니며 임의의 std 붕괴 문턱을 만들지 않는다. 경고는 설정 변경이 아니다. 이어받기 직후 에피소드 버퍼 초기화도 별도로 고려한다.
- m1750: m1500·m1750의 모든 판정 칸·지도 끔 생존과 같은 처방·평가 plan을 확인해 E1F 초안. 미달이면 `--extension-code-root <v26 고정 사본>`으로 실제 확장 증거를 읽은 뒤 미달 성분 **전부**가 두 번 기준 쪽인지 추가 검사한다. 기준까지 부족분(gap)이 줄어드는지를 쓰며, 다른 성분의 부족분이 새로 생기거나 커지면 거절한다. v26 자체는 한 성분만 개선돼도 통과할 수 있어 그대로 받아들이지 않는다. +250은 m1750에서 한 번만 가능하다. 근거 없으면 `HOLD_DIAGNOSE`, 걸음·곡선·시드 진단 목록을 남긴다. 이 도구는 진단 GPU도 띄우지 않는다.
- L9: C1 소비자의 원자료 재계산값과 도달 레벨을 기록한다. L9 실패는 E1F를 막지 않는다. C1 필수 판정 칸이 없으면 PASS를 만들지 않는다.

입력 P1 영수증의 evaluation plan 경로·SHA를 확인한다. C1은 그 plan이 있는 고정 사본의 `ex42_e1_wide.py`를 사용한다. 별도 사본은 `--c1-code-root`로 지정한다. 평가 plan이 사본 밖에 있을 때에는 이 옵션이 필요하다. C1 code SHA를 결과에 남긴다. 기본 source 검증기는 이 저장소 코드이므로 스크립트 몇 개를 scratch로 따로 복사해서 실행하지 말고 위 저장소 경로로 호출한다.

**적용 경계 확정:** lead 답 `msg_cc11370b2af9`와 원장 `7ba9f2be`에 따라 기본값은 **m1000**이다. m750은 기존 경계 규칙, m250·m500·m750 새 표는 CPU 기록만이다. `--effective-from 750`은 이전 의뢰의 반사실 재생용이며 운영 적용값이 아니다. C1 평가가 없다는 이유로 원래 m750 결정을 소급 중단시키지 않는다.

**지도 끔 범위 확정:** 원장 `5f2e7c3b`와 같은 lead 답에 따라 생존 판정은 정확히 **21칸**, 유지13 + L0 여섯 + L5 전진0.1·0.2 둘이다. L1~2는 유지 mixed012가 덮는다. L5 옆 네 칸·L2 yaw 둘·고정 L3/L6/L9·명령 끝점 OFF는 기록이며 되돌림·졸업에 쓰지 않는다. 먼저 27칸으로 센 중간 기록은 이 범위 정정 전이므로 최종판과 구분한다.

`curve_snapshots/`에는 읽은 tfevents 바이트와 SHA가 남는다. 파일은 운영 run이 아닌 지정한 `--out` 아래에만 쓴다. L3/L6/끝점의 기존 m250·m500 원자료는 없으므로 C1은 미측정이다. 새 Kit를 실행한 것처럼 채우지 않는다.

실제 m500에서 도구 기존 문턱은 KEEP이지만 lead는 23:07 원장의 큰 하락 대응으로 slow_track 0→0.2를 b2에 적용했다. 그 승인 예외를 이 재생 도구가 취소하지 않는다. 다음 경계의 실제 처방은 b2 영수증으로 읽는다.

### 검증과 재현 (v1.6)

[구현·검증 보고](REPORT-DE8-1113.md)와 [m250/m500 재계산](de8-replay/DE8-REPLAY.md)을 함께 읽는다.
새 규칙의 첫 두 판정 창은 m1000·m1250이다. m750 기록을 m1000의 첫 연속 악화 창으로 세지 않는다.
C1의 기록 전용 칸(L9·고정 지형 OFF 등)의 결측은 경고만 남긴다. 필요한 GT/PRED 판정 칸은 결측·기록 전용 강등·유효63이면 HOLD다.
C1 문턱까지의 차이에는 옆0.8의 R·MAE·성공·생존을 모두 넣는다. 성공 수만 좋아져서 연장되는 길을 막는다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261113-analysis/e1-boundary-rules/replay_de8.py --out /home/jay/mai/tmp/analyst/de8-replay-user
```

m1750에서 연장 증거를 읽으려면 `boundary_read.py`에 `--extension-code-root /home/jay/mai/wt/foothold-lab/ex42-launch-e1-v26`을 준다.
C1 자료가 생기면 `--c1-code-root`에는 **검토를 마친 실제 평가 코드의 고정 사본**을 준다. 이 옵션은 해당 폴더의 평가기를 CPU로 읽을 뿐 Kit을 기동하지 않는다.
별도 평가 plan은 기존 P1 영수증에 고정된 파일을 읽는다. 경로 옵션으로 학습 plan이나 P1 영수증을 바꾸지 않는다.
