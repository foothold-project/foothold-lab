> 분류: 실험
> 작성: 오흥재 (luna 초안 · lead_tmp 대조) · 2026-10-21
> 근거: [#555 진단·결정 댓글](https://github.com/foothold-project/foothold-lab/issues/555) · `inbox/jay/20261019-design/NIGHT-REPORT-1021.md` · 코드·실행 로그
> 요지: S1-a 실패에서 D1·D2·D2-s43·D3 진단과 세 변경 처방까지의 근거 관계와 미확인 범위를 연결한다.
> 상태: 기록 · S1a-Rx1 명명 병합 완료 · 옛 실행 이름 병기 · 실험 승인 문서 아님

# 밤 실험 관계표

검사 계약 `exp-sync-v1`: 아래 「관계」 표의 첫 칸은 카드 파일 `EXP-<식별자>.md`로 연결한다. 각 카드에는 내용이 있는 `## 가설`, `## 설정`, `## 결과`, `## 다음` 절이 필요하다. `## 결과` 절에는 `영상 없음 · 미확인` 또는 `.mp4`·`.mov`·`.mkv`·`.webm` 영상 경로를 적는다. 「사슬 작업 이름」 표는 `chain_state.json`의 `running`·`done` 이름을 기록한다. 실험 작업은 카드 식별자에, 실험이 아닌 보조 작업은 `운영`에 연결한다. 이름 없는 실행은 검사 실패로 남기고 임의로 실험에 귀속하지 않는다.

> 원자료 재집계: `미측정`. 수치 표는 원보고와 실행 기록을 출처로 하며 이 초안에서 다시 계산하지 않았다.
실험 식별자와 경로의 숫자는 이름이다. 결과 수치에는 등급을 붙였다. `[실측]`은 지정 보고서·로그에 기록된 측정값이며, 이 초안 작성 중 원자료를 다시 집계하지 않았다. `[코드]`는 설정 또는 커밋에서 읽은 값이다. `[가정]`은 계획·해석이다. 영상은 lead 확인상 밤 보행 영상이 없다.

## 관계

**S1a-Rx1**은 커널 lin·ang 0.25 · fbg 0.25 · clip 17의 회복 처방이다. #555 댓글 6304758796, 코드 `690dd194`, 학습 폴더 `foothold_s1a_v11/*s1a_v11_*`에서는 과거 이름 `S1a-v1.1`로 불렸다. 설계 §52의 `S1a-v1.1`은 heading 30% → 50% 처방으로, lead 명명 인계상 미실행인 별개 판이다. 새 이름은 기록을 식별하기 위한 것이며 실행 폴더·코드·봉인 파일을 바꾸지 않는다.

<!-- exp-sync:experiments:v1 -->
| 카드 | 역할 | 부모 설정·체크포인트 | 주요 차이와 결과 | 설계 정본 관계 |
|---|---|---|---|---|
| [S1-a](EXP-S1-a.md) | 본 학습 기준과 실패 관찰 | S1-a 설정. 두 run의 저장 agent 설정은 `resume: false`(luna 대조). model_5999는 결과 참조이며 부모 체크포인트라는 뜻이 아님 | 거친 바닥에서 정지·전진·회전 실패. blind도 실패했으나 진단 경로는 scan 중심 | `16-REWARDS.md`와 `52-S1-OPEN-COMMAND.md`에 S1 계획이 있음. 이번 실패 진단은 #555 기록 |
| [D1](EXP-D1.md) | 발 들기 항 가설 | S1-a 설정 파생. `resume: false`, max_iterations=1501, model_1500 비교. S1-a의 학습 체크포인트에서 이어 학습하지 않음 | `feet_air_time` 가중치 `[코드] +0.1`. 등록된 개선 기준 미달, 가설 기각 | D1은 설계 정본에서 찾지 못함. #555의 진단용 신설 |
| [D2](EXP-D2.md) | 추종 커널의 정지 효과 | S1-a 설정 파생. `resume: false`, max_iterations=1501, model_1500 비교 | 선속도·회전 추종 std를 `[코드] 0.5 → 0.25`로 함께 변경. seed 42의 1,500회 결과와 두 시드 1,100회 비교는 별개 | D2는 설계 정본에서 찾지 못함. #555의 진단용 신설 |
| [D2-s43](EXP-D2-s43.md) | D2 두 번째 시드 확인 및 발산 진단 | seed 43 초기 판은 D2 설정 파생. 이후 발산 판을 `model_1100`에서 재개한 clip 시험은 별도 단계 | 등록 목표 model_1500를 채우지 못해 `[실측] 1,100회` 비교로 제한. 별도 clip17 단기 확인은 장시간 안정성 증거가 아님 | D2-s43은 설계 정본에서 찾지 못함. #555의 진단용 신설 |
| [D3](EXP-D3.md) | 회전 커널 분리 진단 | S1-a 설정 파생. `resume: false`, max_iterations=1501, model_1500 비교 | D2 대비 선속도 std만 `[코드] 0.25` 유지, 회전 std는 `[코드] 0.25 → 0.5`로 되돌림. 세 판정선 모두 통과하지 못함 | D3은 설계 정본에서 찾지 못함. #555의 진단용 신설 |
| [S1a-Rx1 3변경 처방](EXP-S1a-Rx1.md) | 회복용 본 학습 묶음 처방. #555에서는 처음 `S1a-v1.1`로 기록 | S1-a 설정 계보, `resume: false`의 새 학습. S1-a 체크포인트에서 이어받았다고 보지 않음 | 추종 커널 lin·ang `[코드] 0.25`, `foot_below_ground` `[코드] 0.25 m`, `clip_actions` `[코드] 17.0`의 세 변경 묶음 | lead가 이 카드의 정식 이름을 `S1a-Rx1`로 정함. §52의 기존 `S1a-v1.1`은 heading `[코드] 30% → 50%` 처방으로 별도 보존(lead 명명 인계상 미실행) |

## 사슬 작업 이름

이 표는 현재 지도에 연결된 이름만 기록한다. 새 작업의 결과를 확인해 카드 또는 운영으로 분류하기 전에는 이름을 추가하지 않는다.

<!-- exp-sync:chain:v1 -->
| 사슬 작업 | 카드 또는 분류 |
|---|---|
| `scan_train` | S1-a |
| `blind_train` | S1-a |
| `repro_s0` | 운영 |
| `scan_eval` | S1-a |
| `v2_base_gate200` | S1-a |
| `blind_eval` | S1-a |
| `agenda_J1` | 운영 |
| `snapshot_bf16` | 운영 |

## 설계 정본에 있는 것과 진단용 신설

| 항목 | 분류 | 기준 커밋에서 확인한 내용 |
|---|---|---|
| S1 보상·env 기준 | 설계 정본에 있음 | `16-REWARDS.md`의 S1 보상 계약과 `17-GO2-MODEL.md`의 로봇 모델 계약 |
| S1-a와 기존 실패 처방 경로 | 설계 정본에 있음 | `52-S1-OPEN-COMMAND.md`의 S1-a 계획 및 heading 증가 처방. §52의 `S1a-v1.1`은 heading `[코드] 30% → 50%` 의미이며 lead 명명 인계상 미실행인 별개 판 |
| D1·D2·D2-s43·D3 실험과 관측 결과 | 진단용 신설 | #555 사전 등록·후속 판정 댓글. 기준 설계 문서에 있는 정식 실험 카드로 간주하지 않음 |
| #555의 세 변경 회복 처방 | 이 초안에서 별도 표기 | #555 댓글과 코드 `[코드] 690dd194`에 처음 `S1a-v1.1`로 기록. lead의 명명 답에 따라 카드 정식 이름은 `S1a-Rx1`. §52의 기존 heading 처방은 변경하지 않으며 lead 명명 인계상 미실행인 별개 판 |

## 공통 해석 경계

- D2 `[실측]` 1,500회 seed 42 결과 `[실측]` 정지 비율 `0.766 → 0.078`은 D2-s43 두 시드 `[실측]` 1,100회 결과 `[실측]` 기준 `0.921`, seed 42 `[실측]` `0.203`, seed 43 `[실측]` `0.203`과 다른 회차·분모다. 하나의 반복 결과처럼 합치지 않는다.
- blind 처방은 scan 진단에서 외삽한 조합이다. blind에서 별도 원인 진단을 완료했다는 근거가 없다.
- lead 확인: 밤 보행 영상 없음. 수치 진단을 영상 관찰로 바꾸어 말하지 않는다.
- S1a-Rx1 세 변경 묶음의 결과와 항별 효과를 분리한다. blind 성능, 전체 평가 통과, 다음 단계 승격은 미확인이다.
- 명명 갈림길은 lead 답변으로 해결: 세 변경 카드 이름은 `S1a-Rx1`. `S1a-v1.1`은 #555 실행 기록의 과거 이름으로 남기고, 설계 §52의 heading 처방 이름은 그대로 둔다.
- `inbox/jay/20261019-design/NIGHT-REPORT-1021.md`와 #555는 기록 근거다. 이 표는 lead의 DECISION-SYNC 또는 Astra 검증을 대신하지 않는다.

## 다음 가설

D1에서 실패한 보상 항 가설을 D2의 커널 비교로 좁혔고, D2-s43과 D3에서 재현·축 분리를 시도했다. 다음 검증은 세 변경 묶음의 사전 중간 기준을 scan과 blind 각각에서 확인하는 일이다. 완료 로그·최종 gate가 없으면 결과는 미확인으로 남긴다.

## 근거 경로

- `inbox/jay/20261019-design/16-REWARDS.md`, `17-GO2-MODEL.md`, `52-S1-OPEN-COMMAND.md` at base `[코드] bc9d4b25`.
- `inbox/jay/20261019-design/NIGHT-REPORT-1021.md`.
- #555 댓글: [D1 등록 6298590512](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6298590512), [D1 판정 6301263269](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6301263269), [D2·후속 등록 6302009721](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302009721), [D2-s43 6304255937](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304255937), [발산·clip17 6304310458](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304310458), [D3·처방 6304758796](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796).
- 코드 변경: `[코드] 690dd194`, `[코드] e6efed92`, `[코드] 21fd5e2d`.

## 대조 범위와 읽는 순서

- 부모 화살표는 **설정 관계**다: S1-a → D1·D2·D3·회복 처방, D2 → D2-s43(시드 변경)·D3(회전 커널 복원). 같은 체크포인트를 이어받았다는 뜻은 아니다. D1·D2·D3는 iteration 0~1500, max_iterations=1501이며 통상 「1500회 판」은 model_1500을 뜻한다.
- 원자료 수치는 각 카드의 「lead_tmp 직접 대조」가 우선한다. 초안의 `[실측]` 중 그 절에서 대조하지 않은 값은 **다른 세션의 보고값**이다. GPU 평가 재실행은 하지 않았다.
- 보상·종료·행동 clip·시작점·처방의 문서 반영과 미완료 담당은 [DECISION-SYNC](../20261019-design/DECISION-SYNC.md)에 있다. 이 지도는 새 실험을 승인하지 않는다.
- 파일 경로 약칭: `sonnet-code` = `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/`, `eval_new` = `C:/Users/AI-WS01/s2_lab/eval_new/`. 상대 로그 경로는 전자, 평가 경로는 후자에서 찾는다.

명명 병합 근거: lead의 이 창 요청과 luna `a974cf8d`. `e3d5da42`의 원자료 대조·사전 기준 정정은 보존하고, 카드명·옛 이름 대응·링크만 병합했다.
