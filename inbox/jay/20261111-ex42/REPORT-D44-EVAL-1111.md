# EX-42 E1 D44 계단참 평가 준비

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: CURRICULUM-GATES v0.16:187,229,231 · planner REVIEW-EX42-D44-CELLS-1111.md §2 · analyst CONTRACT-D44-ANCHORS-1111.md · 원본 landing_seed42_v2/mesh_manifest.json · [평가기 원본](https://github.com/foothold-project/foothold-lab/blob/feature/ex42-d44-eval-scripter/foothold_s2/eval/ex42_d44_eval.py)
> 요지: D44 칸 수와 시간을 prep 에서 읽는 평가기, 64개 독립 타일, 두 창 AND 판독의 CPU 경로를 준비했다.
> 상태: 코드 CPU 확인 · Kit 미실행 · 판정 칸과 시간은 팀장 승인 대기
> 판: v0.1

## 적용 범위와 현재 보류

- `ex42_e1_judge.py` 는 `evaluation.paper_cells.stairs_landing.judge_cases` 목록을 읽는다. 칸 수를 4나 6으로 박지 않았다. 목록이나 한 칸이 빠지면 HOLD, 유효 분모 64 중 하나라도 무판정이면 HOLD, 유효한 칸이 하한 미만이면 FAIL이다. 각 칸의 raw JSON과 trace NPZ SHA를 검사한다.
- `ex42_eval_once.py` 는 E1 P1에서 prep에 승인된 칸 목록이 있을 때만 D44 Kit 자식을 추가한다. 현 prep에는 목록이 없으므로 D44 자식을 시작하지 않고 HOLD 이유를 영수증에 남긴다. E0 실행 경로는 그대로다.
- `ex42_eval_tile_mesh.py` 는 승인된 단일 타일을 8×8로 복제해 64 env가 서로 다른 원점에서 시작하게 한다. 고정 원본 `/home/jay/data/foothold/s2_lab/ex42_eval_mesh_1111/landing_seed42_v2`의 기하 SHA는 `baa59af3347c53c2cdeae674ddc873f26d4b9e38cffdbce4a4dc73cf94febb82`; 복제 기하 SHA는 `7a9479506c876f75ad8b63b98c97d3cd2c946d75779634f2a615915017f9ab61`이다.
- `ex42_d44_eval.py` 는 같은 checkpoint와 seed로 각 설정 칸을 순차 실행한다. 각 칸의 64 env post-step 위치, quaternion, 발 위치·접촉, 명령, 생존을 NPZ에 쓰고, 판정 성분을 JSON에 쓴다. `ex42_score.py`는 NPZ에서 다시 집계하여 영수증 숫자와 대조한다.

## prep 에 필요한 칸, 승인 전 제안

현재 planner 권고 (가)는 `turn_left`, `turn_right`, `stop_restart` × `eval_gt`, `eval_pred` 6 판정 칸과 같은 세 과제 × `probe_prop_only` 3 기록 칸이다. `judge_cases` 와 `record_cases`는 문자열 ID 목록, `case_specs`는 ID마다 `{task, map_mode, role}`이며 역할은 각각 `judge`, `record_only`다. 세 과제와 세 모드는 코드가 지원하지만 목록과 칸 수는 prep 이 정한다.

`stairs_landing` 에 원본 디렉터리와 위 SHA를 `source_mesh_dir`, `source_mesh_sha256`로 고정해야 한다. `timing`에는 `settle_s`, `approach_limit_s`, `stop_s`, `restart_limit_s`, `stop_hold_s`, `top_hold_s`, `stop_speed_mps`, `foot_below_top_m`, `foot_stop_z_tolerance_m`을 넣어야 한다. `approach_vx_mps`, `restart_vx_mps`, `stop_surface_z_m`도 prep 값이어야 한다. planner 제안치는 순서대로 1, 4, 2, 6, 1, 0.5초, 0.05 m/s, 0.08, 0.08 m와 1.0, 1.0 m/s, 0.32 m다. 전부 승인 전 가정이다. 기존 `turn_seconds 6`, `turn_rate_radps 1.2`, `success_turn_fraction 0.8`은 그대로 읽는다.

진행 조건: 팀장이 6+3 칸과 시간·판 위 정의를 승인하고 prep/approval 해시를 해당 주인이 고정해야 한다. 그 뒤 lead가 한 번 Kit 예행을 실행해 실제 env 원점, 지도 선택, reset과 영수증을 확인해야 한다. 이 보고서의 CPU 통과를 Kit 통과로 쓰지 않는다.

## CPU 근거

`확인됨`: 실행 환경은 `/home/jay/miniforge3/envs/isaac311/bin/python`, `CUDA_VISIBLE_DEVICES=`이다. 관련 시험 69개 통과 (`test_ex42_score_cpu.py`, `test_ex42_split_eval_cpu.py`, E1 entry/approval/judge, D44 cells/tile). 새 Kit 자식의 실제 AppLauncher 인자 해석에 device=cuda:0, headless=true, kit_args를 넣어 envs=63 사전 거절을 확인했다. Kit 앱은 띄우지 않았다. 고정 원본 타일 재생성과 64 복제 preflight도 CPU 통과했다. 출력: `/home/jay/mai/tmp/scripter/d44-replica-latest-1111/replica_receipt.json`.

## 남은 위험

실제 Isaac rollout은 미실행이다. 특히 `env.reset()` 뒤 고정 타일 배정과 새 root 위치, 감지된 발 접촉, 각 지도 모드, stop-band 진입을 Kit에서 확인해야 한다. CPU 시험은 계산과 입력 계약만 확인한다. 현재 E1 P1이 D44 증거 없이 HOLD를 유지하는 것이 의도된 안전 상태다.

## 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-11-11 | CPU 평가 경로와 승인 전 계약 제안 |
