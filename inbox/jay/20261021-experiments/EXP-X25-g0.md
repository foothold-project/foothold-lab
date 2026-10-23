> 분류: 실험
> 작성: 오흥재 (luna 문서 반영) · 2026-10-23
> 근거: #555 6342453922 · LEAD-HANDOFF-20261022.md §§23·25·27 · manifest `logs/rsl_rl/foothold_s2_x23/2026-10-22_23-00-45_ex25-g0/manifest.json` · BASELINE-0811.md
> 요지: START G0에서 지도를 빼고 EX-23 G1과 비교하는 본류 판이다.
> 상태: 23:00 시작 · manifest와 params의 1501 설정 확인 · 1501 update 기록 · 보행 판정 미확인

# EX-25 · START G0 지도 없음

## 가설과 결과 전 등록

> [선행] “EX-25: EX-23 과 같고 지도만 없음(G0).” [#555 6342453922](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6342453922)

START 구조에서 정답 높이 지도를 제거해도 처음부터 학습해 보행 위상이 형성되는지 EX-23과 비교한다. EX-23과 함께 START 본류를 이루는 G0/G1 대조다.

## 설정

| 항목 | 기록 |
|---|---|
| 흐름 | `[lead 결정·handoff §25]` EX-25는 EX-23과 함께 START 본류다. |
| 구조·입력 | `[lead 기록]` START 지각·GRU·추정기·AdaSmpl 구조, `map_input=none`, `force_gt=false`. |
| 공통 설정 | `[lead 기록]` EX-23과 같은 START 보상·S1 지형·START 명령·약한 DR·행동 지연 끔·관절 한계 벌점 없음. 전체 소비 설정 직접 검증은 미완료다. |
| 목표와 실행 | `[lead 기록]` 최초 1001 계획은 #555 6342453922 및 handoff §25. 23:00에 PID 105768 판을 중지하고 1501로 바꿔 시작했다. `[실측·manifest]` `logs/rsl_rl/foothold_s2_x23/2026-10-22_23-00-45_ex25-g0/manifest.json`의 `run.cli_args.max_iterations=1501`, `run.cli_args.run_name=ex25-g0`, `yaml.agent.max_iterations=1501`. 23:00 시작 후 진행 중이며 완료 아님. |
| 로그 식별 | `[실측·경로]` 시작 로그 `logs/s2_x23_ex23-g1_20261022_230033/run.log`의 `ex23-g1` 폴더명은 스크립트 기본값이며 run name은 `ex25-g0`. `2026-10-22_22-49-21_ex25-g0` 1001 판은 중단됐으므로 결과로 쓰지 않는다. |
| 체크포인트 | 처음부터 학습 계획이며 checkpoint 계승 증거는 없다. |

## 판정 · 결과 전 등록

EX-23과 지도 입력만 다른지 manifest와 실제 actor 입력으로 확인한다. 811 동회차 자료를 함께 본다. `[가설]` 300회는 낮은 자세에서 이동을 먼저 학습하는지 보는 경고 후보이며, 낮은 자세 단독 중단선이 아니다. `[실측·BASELINE-0811]` 몸 높이 500회 0.32 m, 1000회 0.40 m와 대각 비율 0.97 trot.

## 결과

[실측·manifest] `2026-10-22_23-00-45_ex25-g0`에서 `max_iterations=1501`, `progress.completed_updates=1501`이다. 완료 시각과 프로세스 종료는 미확인이다. 앞선 1001 목표는 이전 계획, 22:49 run은 중단판으로 결과에서 제외한다. [실측·gait_table_print.txt] 평지 전진 1.0 m/s 기준 몸 높이/대각 비율/vx는 300회 0.141 m/미정/-0.01, 500회 측정 파일 없음, 1000회 0.303 m/0.97/1.01, 1500회 0.343 m/0.97/0.91이다. [실측·가공 그림] 위상·자세·TensorBoard와 영상 접촉 시트는 [RESULT](RESULT-EX23-25.md)에 연결했다. EX-25 영상은 거의 회색조라 공유 검수에서 제외했다. 최종 판정 미정. 공유 가능한 비교 영상 없음 · 미확인.

## 다음

lead_tmp와 Astra가 EX-23 및 811 동회차 기준으로 수치·위상·영상 gate를 대조한다. EX-25 500회 미측정과 1001 목표, 중단된 22:49 판을 계속 분리한다. 최종 보행 판정은 미정으로 보존한다.
