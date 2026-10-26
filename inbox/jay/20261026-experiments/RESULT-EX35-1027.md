> 분류: 실험
> 작성: 오흥재 (lead · scripter 원자료 생성) · 2026-10-27
> 근거: EX-35 고정 학습 영수증·run.log·m1750/m1950/m2000 판정 JSON · 결과 전 EX-35 카드 §4b.6
> 요지: 최종 두 저장본은 MAINTAIN_FAIL이다. 필수 칸과 A11 미판독으로 창 판정은 HOLD, 연장 없음이다.
> 상태: 학습 종료·정답 지도 저장본 판정 확인됨 · 창 판정 보류 · 영상·보행 위상·저장본 추세 해석 대기
> 판: v1.1

# EX-35 결과 · 명령 S2a 창 판정

## 1. 같은 조건의 영상부터 보기

영상 분석 대기. analyst · runner가 영상과 보행 위상을 분석 중이다. 공개 링크와 영상 길이·프레임 수는 미확인이다.

## 2. 무엇이 같고 무엇이 다른가

부모는 S-B10 m1500 (`sha256 4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d`), EX-35는 그 저장본에서 m1501부터 m2000까지 500회 갱신했다. 실행 인자는 GPU `cuda:0`, 3072 env, seed 42, `max_iterations=2001`이다. 명령 과정 S2a와 판정 규칙은 결과 전 [EX-35 카드](../20261021-experiments/EXP-EX35-SB10-cmd-S2a.md)에 등록됐다. 영상·물리 상세 조건의 독립 재확인은 미완료다.

## 3. 저장본별 판정

| 저장본 | 지도 모드 | 단계 안 갱신 | 최소 체류 | 상태 | 사유 수 |
|---|---|---:|---:|---|---:|
| m1750 | eval_gt | 250 | 500 | NEW_TASK_PENDING | 1 |
| m1950 | eval_gt | 450 | 500 | MAINTAIN_FAIL | 3 |
| m2000 | eval_gt | 500 | 500 | MAINTAIN_FAIL | 3 |

m1750의 `NEW_TASK_PENDING`은 최종 유지 판정이 아니다. 최종 판단에는 m1950과 m2000의 상태를 쓴다.

## 4. 유지 실패가 난 칸

| 저장본 | 사례 | 조건 | 측정값 | 등록 한계 |
|---|---|---|---:|---:|
| m1950 | right_then_left | drop_Q | 0.4955872241479847 | 0.5837163634983495 |
| m1950 | right_then_left | rise_C | 0.6950000000000001 | 0.6673828125 |
| m1950 | fwd_then_left | drop_Q | 0.4757363248932633 | 0.5628077151095658 |
| m2000 | left_then_right | survival_16 | 13 | 14 |
| m2000 | right_then_left | drop_Q | 0.5586886471922285 | 0.5837163634983495 |
| m2000 | fwd_then_left | survival_16 | 13 | 14 |

이 표는 `ex35_verdict.json.reasons`를 그대로 펼친 것이다. 원인이나 보행 기전을 뜻하지 않는다.

## 5. 회전 사례의 Q · C · 생존 표본

| 사례 | m1950 Q | m2000 Q | m1950 C | m2000 C | m1950 kept | m2000 kept |
|---|---:|---:|---:|---:|---:|---:|
| fwd_then_left | 0.4757 | 0.5714 | 0.6412 | 0.5558 | 15 | 13 |
| fwd_then_right | 0.8108 | 1.0993 | 0.4083 | 0.4422 | 15 | 16 |
| indep_left | 0.4276 | 0.5401 | 0.6546 | 0.4855 | 14 | 15 |
| indep_right | 0.8341 | 1.1090 | 0.4087 | 0.4366 | 16 | 15 |
| left_then_right | 0.8294 | 1.1200 | 0.4339 | 0.4317 | 15 | 13 |
| right_then_left | 0.4956 | 0.5587 | 0.6950 | 0.5513 | 14 | 14 |
| walk_turn_left | 0.4705 | 0.4820 | 0.1345 | 0.0943 | 16 | 16 |
| walk_turn_right | 0.4746 | 0.4953 | 0.0530 | 0.0469 | 16 | 16 |

Q·C의 정의와 문턱은 등록 카드와 판정기 계약을 따른다. 여기서는 원자료 표시만 한다.

부모와 비교할 때는 같은 사례끼리 본다. 부모 S-B10 m1500은 `startline_table.json`의 `eval_gt`이고 아래 m2000 열은 EX-35 판정 JSON이다.

| 사례 | 부모 Q | m2000 Q | 차이 |
|---|---:|---:|---:|
| fwd_then_left | 0.7628 | 0.5714 | -0.1914 |
| right_then_left | 0.7837 | 0.5587 | -0.2250 |
| indep_left | 0.4266 | 0.5401 | +0.1135 |

독립 좌회전은 부모보다 높다. 전진 뒤 좌회전과 우회전 뒤 좌회전의 하락을 독립 좌회전의 하락으로 일반화하지 않는다.

## 6. 학습 종료와 학습 곡선의 한계

`run.log`의 마지막 학습 회차는 2000/2001, 표시 경과는 03:22:27, `rc.txt`는 0이다. 아래는 run.log의 각 회차 값을 창 안에서 산술 평균한 것이다.

| 갱신 창 | 로그 수 | 평균 보상 | 에피소드 길이 | 지형 레벨 | 엔트로피 | 가치 손실 | PPO KL | bad_orientation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1501-1550 | 50 | 9.8086 | 560.3838 | 5.8472 | 9.2819 | 0.0236 | 0.0177 | 0.0483 |
| 1701-1750 | 50 | 16.4824 | 951.2884 | 6.0715 | 9.5774 | 0.0260 | 0.0169 | 0.1003 |
| 1901-1950 | 50 | 16.8638 | 962.0696 | 6.1857 | 9.4513 | 0.0243 | 0.0163 | 0.0637 |
| 1951-2000 | 50 | 17.2394 | 962.4546 | 6.2300 | 9.3899 | 0.0236 | 0.0168 | 0.0787 |

이 학습 평균은 같은 명령 분포의 저장본 독립 평가가 아니며, 판정에는 사용하지 않았다.

## 7. 판정과 증거 범위

m1950과 m2000 저장본의 `MAINTAIN_FAIL`은 확인됐다. 카드 §4b.6의 **6행만 조건부로 보면 REVERT**이나, 이 표는 앞에서 맞는 행이 우선이다. 필수 칸 완결 증거가 없고 A11 영상 판독표가 미제출이므로 선행 1·4행에서 현재 창 판정은 **HOLD (판정 보류)**다. 정본은 **S-B10 m1500 유지**, EX-35 연장은 없다. m1950·m2000 JSON은 정답 지도 `eval_gt` 저장본 판정이며, 전체 창 판정 완료나 보행 기전 결론이 아니다.

## 8. 다음 설계에서 무엇을 바꾸는가

이 보고서만으로 원인을 정하지 않는다. analyst와 runner의 영상·위상·저장본 추세 분석 및 필수 칸 완결 확인을 기다린다. 새 학습이나 연장은 별도 팀장 결정이 필요하다.

## 9. 실제 완료와 재현 경로

`python inbox/jay/20261026-experiments/figs/ex35/gen_result.py --out inbox/jay/20261026-experiments/RESULT-EX35-1027.md --json-out inbox/jay/20261026-experiments/figs/ex35/result_data.json`

| 원자료 | 경로 | sha256 |
|---|---|---|
| m1750 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval\m1750\ex35_verdict.json` | `9707eb3cc3aecb208177093d054f86e1d1b501951de8aa0849a8b7c86d3b3e4b` |
| m1950 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval\m1950\ex35_verdict.json` | `ba66346def7fc4a37fcc70bbedd46f7442284af023352894b7c578a26fb9ec58` |
| m2000 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval\m2000\ex35_verdict.json` | `8f1271f8be7196b33c06f350474fd10590d3698a5ab017b679024a544e5c7dc5` |
| receipt | `C:\mai\wt\foothold-lab\impl-ex35-07fc\logs_gate\ex35_main_20261026_232432\launch_receipt.json` | `58707db6fe22b337b3ce4b595f338b2c6afda2dc3f0c12a367c699108430d442` |
| run_log | `C:\mai\wt\foothold-lab\impl-ex35-07fc\logs_gate\ex35_main_20261026_232432\run.log` | `932a5ceddebb412a7efac6b64868151aa38382ee9085a0e804a44d341b285edc` |
| rc | `C:\mai\wt\foothold-lab\impl-ex35-07fc\logs_gate\ex35_main_20261026_232432\rc.txt` | `93ff7811a209e2a8479230bbb9b6bc19f7f311d3af383ec350c1db2a7e7d5494` |
| baseline | `C:\mai\wt\foothold-lab\lead_tmp-20261023\inbox\jay\20261026-experiments\figs\startline\startline_table.json` | `841ce5170e2ec63a952d19c3722ee19cb441020c4b52b8a882295d2605713298` |

검사: `m1750=NEW_TASK_PENDING`, `m1950=m2000=MAINTAIN_FAIL`, 완료 회차와 rc, 부모 sha 일치를 생성기가 요구한다. `HOLD`는 카드 §4b.6 선행 행과 미완 증거 범위의 운영 기록이며 저장본 JSON의 상태가 아니다. 재생성 시 원자료가 달라지면 해시와 문서도 달라진다.
