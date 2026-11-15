> 분류: 실험
> 작성: 오흥재 (luna 문서 반영) · 2026-10-23
> 근거: #555 6342453922 · LEAD-HANDOFF-20261022.md §§23·25·27 · manifest `logs/rsl_rl/foothold_s2_x23/2026-10-22_23-00-45_ex25-g0/manifest.json` · BASELINE-0811.md
> 요지: START G0에서 지도를 빼고 EX-23 G1과 비교하는 본류 판이다.
> 상태: 기존 결과 분석 반영 · 전진 개선 확인 · 회전·내성 미완성 · 다음 실행 미결정

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
| 목표와 실행 | `[lead 기록]` 최초 1001 계획은 #555 6342453922 및 handoff §25. 23:00에 PID 105768 판을 중지하고 1501로 바꿔 시작했다. `[실측·manifest]` `logs/rsl_rl/foothold_s2_x23/2026-10-22_23-00-45_ex25-g0/manifest.json`의 `run.cli_args.max_iterations=1501`, `run.cli_args.run_name=ex25-g0`, `yaml.agent.max_iterations=1501`. 당시 시작 기록이며 현재 1501 update 기록은 아래 결과를 따른다. |
| 로그 식별 | `[실측·경로]` 시작 로그 `logs/s2_x23_ex23-g1_20261022_230033/run.log`의 `ex23-g1` 폴더명은 스크립트 기본값이며 run name은 `ex25-g0`. `2026-10-22_22-49-21_ex25-g0` 1001 판은 중단됐으므로 결과로 쓰지 않는다. |
| 체크포인트 | 처음부터 학습 계획이며 checkpoint 계승 증거는 없다. |

## 판정 · 결과 전 등록

EX-23과 지도 입력만 다른지 manifest와 실제 actor 입력으로 확인한다. 811 동회차 자료를 함께 본다. `[가설]` 300회는 낮은 자세에서 이동을 먼저 학습하는지 보는 경고 후보이며, 낮은 자세 단독 중단선이 아니다. `[실측·BASELINE-0811]` 몸 높이 500회 0.32 m, 1000회 0.40 m와 대각 비율 0.97 trot.

## 결과

확인됨: manifest 1501 update 기록과 model_1500 기존 영상·NPZ를 대조했다. 평지 전진 1.0의 높이 0.343 m·실제 속도 0.907 m/s와 대각 교대 확인. 평지 양의 회전은 먼저 돌다가 유지하지 못한다. rough 양의 회전은 G1보다 낫다. EX-25 300 reset 64 기록은 손상 영상과 시도가 섞여 정상 보행 표에서 분리하고, 500 flat은 결측이다. 단색 검수 실패라는 옛 판정은 철회했다. 비교 영상: `C:/mai/wt/foothold-lab/luna-23b/inbox/jay/20261021-experiments/figs/ex23-25-luna-23b/ex23-ex25-rough-1500-1x.mp4`. 수치·위상·관절·학습 곡선·한계는 [RESULT](RESULT-EX23-25.md)에 있다. 단일 시드·짧은 시퀀스의 분석이고 반복 성공률은 미측정이다.

## 다음

분석을 팀장과 확인한 뒤 현 조건 안정화 연장과 DR·지연 단계화를 정한다. 현재 DR은 약하게 고정한 판이다. 추가 회차·기준·학습 실행은 미결정이다.
