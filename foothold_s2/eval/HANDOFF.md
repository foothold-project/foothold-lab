> 분류: A/정책학습 · 구현 인계 (SC-1 새 평가 도구)
> 작성: sonnet-code 세션 (10/20 00:51, 한도 93 % 로 멈춤)
> 근거: inbox/jay/20261019-design/41-EVAL-AXES.md · 51-S0-BASELINES.md (feature/verify-v2-mvp-jay efab7ed9 를 이 사본에 병합함)
> 요지: foothold_s2/eval/ 새 평가 도구. L0 50 통과, L1 축 1 예행 8 판이 옛 하네스와 판 단위로 일치. 축 3 · 축 2 예행은 GPU 0 에서 chain_l1.sh 가 돌리는 중
> 상태: 진행 중 (lead 보고 전)

# HANDOFF

## 한 것
- 코드: foothold_s2/eval/ (stats cells judge rsj axis2_metrics start_sheet manifest compare runtime adapters terrain_sets axis2_run run_eval run_kit.sh, tests 3 파일).
- L0: pytest 50 통과, pyflakes 0, AST import 검사 통과.
- L1 축 1: `C:/Users/AI-WS01/s2_lab/eval_new/l1_axis1_smoke1` (rough6 · 0.5 m/s · pyramid_stairs · 8 판). 판 8 개의 전진 거리 · 통과선 이탈 · 속도 오차 · overall 이 옛 `eval_e1_v2axes/axis1/rough6/d0.5/v0.5` 같은 (env, 판) 줄과 전부 같음(옛 값 반올림 자리까지). 종료 코드 0, Traceback 0, CSV 8 줄.
- 돌고 있는 것(건드리지 말 것): `eval_new/chain_l1.sh` 가 l1_axis3_left, l1_axis3_spin, l1_axis2 를 차례로 돌린다. 끝나면 `eval_new/chain_l1.done`. 각 폴더 rc.txt 와 run.log 의 Traceback 수로 판정.

## 멈춘 곳 (00:55 갱신)
- chain_l1 끝남. 축 3 좌(0,0.5,0, pyramid_stairs · wave 각 8 판): rc 0, Traceback 0, R/S/J 전부 1.0, 명령 방향 진행 1.00, 방향 이탈(요 30도 초과) 비율 0.375 · 0.25. 표본 8 판이라 구간이 넓음. degenerate 표시(전부 1)는 이 표본 크기 탓일 수 있음(미확인).
- 축 3 제자리 회전 1.2 (gap · stepping_stones 각 8 판): rc 0, S 1.0, 요 추종비 0.984 · 1.004.
- 축 2: 첫 실행이 시나리오 둘째 reset 에서 RuntimeError (inference tensor). 원인은 env.step 을 inference_mode 안에서 부른 것. axis2_run.py 에서 step 을 밖으로 빼서 고침(재실행 안 함, 미확인). 재실행: `bash foothold_s2/eval/run_kit.sh <out> axis2 --policy e1 --checkpoint C:/Users/AI-WS01/s2_lab/step1_run_b2/fixtures/model_20000.pt`, 약 5 분, 그 뒤 axis2_cells.csv 를 evidence/E1-vs-v2-axis2.csv 와 대조(E1 9/9, 요 추종 0.84~0.98 기대).

## 다음 한 걸음
1. chain_l1.done 확인 후 세 폴더를 `manifest.check_run_dir` 로 점검(종료 코드를 믿지 말 것), axis2_cells.csv 를 evidence 와 대조.
2. 축 3 행의 R/S/J · 방향 이탈 열이 의미 있게 찼는지 본다(좌 명령에서 yaw_dev_flag, cmd_progress_ratio).
3. lead 창(term_2580fc05)에 보고: 바꾼 파일 · 시험 · 예행 표 · 옛 하네스 대조 · 41 과 다르게 한 곳 · 남은 질문.

## 41 과 다르게 한 곳 · 남은 질문 (보고에 넣을 것)
- R 은 「몸통 통과」(진행 3 m 도달)만 구현. 「네 발이 유효 지지면 위」 조건은 미구현.
- 「이어진 지형」 을 글자대로 rough6 전체 + wave + discrete_obstacles 로 둬서 계단 둘이 계단 행과 겹침.
- 축 3 진행 비율의 분모는 기준 거리 3 m(41 가정의 「3 m 기준 거리」), 도달 뒤 명령 0 으로 T 까지 서 있음(41 §5).
- 듬성한 행 좌 · 우는 vy_obs 가 있어야 잼(--vy_obs 연결은 cells.axis3_table 까지, run_eval 에는 아직 칸 풀어쓰기 드라이버 없음).
- START 시험지: 생성기 + L0 치수 시험만. Kit 실행 (`do_start`) 과 mesh L1 미연결. 평균대 · 디딤 빔 · 징검돌의 낮은 레벨 모양은 가정(논문은 최고 레벨만). START 4 종은 8x4 m 칸이라 축 3 의 옆 · 뒤 명령 기준 거리가 칸을 벗어나 축 3 지형군에서 뺌.
- IsaacLabAdapter(NVIDIA · v2 체크포인트)는 Kit 미시험, run_eval 에 연결 안 됨(E1 만).
- 무대 계단 칸: terrain_sets.stage_stairs_cfg 만 있고 Kit 에서 안 띄워 봄.
- GPU 는 CUDA_VISIBLE_DEVICES 대신 --device cuda:0 + PCI_BUS_ID (렌더 장치 규칙). lead 지시 문구와 다름.
- 남은 구현: S0 전체 칸을 도는 드라이버(축 1 6 묶음 + 축 2 + 축 3 칸 풀기), 옛 값 전체 대조(축 1 48 칸 · 0.4479, 범위 안 32 칸 · 0.6719), 판 비교 CSV.

## 미커밋 파일
- 없음(이 문서까지 한 커밋으로 묶음). 브랜치 vfxpedia/sonnet-code, push 안 함.

## 03:20 갱신
- 축 2 재실행 완료(eval_new/l1_axis2, 종료 0, Traceback 0): 아홉 칸 판정 옛 값과 동일. 요 추종비 차이 최대 0.012. hold 잔류 속도 0.00272(옛 0.00088), hold 관절 목표 변화 0.00859(옛 0.00265), 원인 미확인.
- lead 에 최종 보고를 보냄(SendMessage, 03:20). 답을 기다림: hold 차이 파기 여부, vy_obs 값, R 의 발 조건, START 4종 범위.

## SC-2 진행 (10/20 03:50)
- (a) hold 원인 해결: reset 난수 순서(래퍼 먼저 -> reset -> 명령 항 교체). 축 2 아홉 칸이 evidence 와 비트 일치. hold 관절 칸은 reset 난수만으로 0.00185~0.01117 로 문턱 0.01 을 넘나듦(lead 가 최종 점검에 올림).
- (b) E1 축 1 48칸 새 도구 = 옛 값, 어긋난 칸 0, 4,800 판 판정 일치. 표 eval_new/axis1_e1_vs_old.csv.
- (c) v2 · NVIDIA 어댑터 예행 8 판 통과, 경로 · sha256 은 보고와 manifest 에 있음.
- (d) S0 연쇄: `python -m foothold_s2.eval.s0_chain --root C:/Users/AI-WS01/s2_lab/eval_new/s0 --policies e1,v2,nvidia --gpus 0,1 --e1_axis1_dir C:/Users/AI-WS01/s2_lab/eval_new/axis1_e1` 03:48:58 시작. 로그 s0/s0_chain.log, 상태 s0/s0_status.jsonl. 이어 돌리기 가능(같은 명령 다시). 하트비트 Cron c70eb341 이 21 분마다 확인.
- 남은 일: 연쇄 끝나면 (1) 41 형식 표 (축 1 세 판 x 48칸, 축 2 시드 셋 표 compare.axis2_seed_table, 축 3 21칸 표) (2) 판 비교 CSV (3) NVIDIA · v2 축 1 을 옛 sweep_long.csv 와 칸 단위 대조(compare.axis1_report 는 옛 summary 형식이라 sweep_long 용 변환 필요) (4) lead 보고. START 시험지 Kit 실행은 미연결.

## SC-2 끝 (10/20 09:00)
- S0 96 일 전부 통과 + v2 · NVIDIA 축 2 재측정(어댑터 수정 d8437c05). 표 inbox/jay/20261019-design/evidence/baselines/ (README 에 읽는 법). 원자료 C:/Users/AI-WS01/s2_lab/eval_new/s0/. stale 축 2 는 eval_new/s0_stale_axis2/.
- 반복성: v2 stepping_stones · random_rough 0.5 m/s 각 2회 + 연쇄 결과 모두 100판 비트 일치(GPU 0 · 1). 수정 전 후: 축 1 0.5 m/s 4묶음 3200판 · 축 3 대표 8일 4200판 비트 일치.
- 남은 일: START 시험지 Kit 실행 미연결, 0.5 m/s 옛 sweep 어긋남의 옛 실행 조건 미확인, 41 의 R 정의 공백(lead 목록).
