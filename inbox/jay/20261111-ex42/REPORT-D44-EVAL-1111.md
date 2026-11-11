# EX-42 E1 D44 계단참 평가 준비

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: CURRICULUM-GATES v0.16:187,229,231 · planner REVIEW-EX42-D44-CELLS-1111.md §2 · analyst CONTRACT-D44-ANCHORS-1111.md · 원본 landing_seed42_v2/mesh_manifest.json · [평가기 원본](https://github.com/foothold-project/foothold-lab/blob/feature/ex42-d44-eval-scripter/foothold_s2/eval/ex42_d44_eval.py)
> 요지: D44 칸 수와 시간을 prep 에서 읽는 평가기, 64개 독립 타일, 두 창 AND 판독의 CPU 경로를 준비했다.
> 상태: 팀장 13:03 승인값 prep 반영 · CPU 확인 · Kit 미실행
> 판: v0.3

## 적용 범위와 현재 보류

- `ex42_e1_judge.py` 는 `evaluation.paper_cells.stairs_landing.judge_cases` 목록을 읽는다. 칸 수를 4나 6으로 박지 않았다. 목록이나 한 칸이 빠지면 HOLD다. 접근하지 못한 env는 분모에서 빼고, 유효 48 미만이면 해당 칸 HOLD, 유효 48 이상이면 성공 ≥ ceil(52/64 × 유효)와 생존 ≥ ceil(60/64 × 유효)를 적용한다. 다른 칸의 FAIL은 HOLD보다 우선한다. 계획 밖 칸과 raw JSON, trace NPZ의 칸 신원과 SHA를 검사한다.
- `ex42_eval_once.py` 는 E1 P1에서 prep에 승인된 칸 목록이 있을 때만 D44 Kit 자식을 추가한다. prep에는 6개 판정 칸과 3개 기록 칸이 있으며, 증거가 없으면 HOLD 이유를 영수증에 남긴다. E0 실행 경로는 그대로다.
- `ex42_eval_tile_mesh.py` 는 승인된 단일 타일을 8×8로 복제해 64 env가 서로 다른 원점에서 시작하게 한다. 고정 원본 `/home/jay/data/foothold/s2_lab/ex42_eval_mesh_1111/landing_seed42_v2`의 기하 SHA는 `baa59af3347c53c2cdeae674ddc873f26d4b9e38cffdbce4a4dc73cf94febb82`; 복제 기하 SHA는 `7a9479506c876f75ad8b63b98c97d3cd2c946d75779634f2a615915017f9ab61`이다.
- `ex42_d44_eval.py` 는 같은 checkpoint와 seed로 각 설정 칸을 순차 실행한다. 각 칸의 64 env post-step 위치, quaternion, 발 위치·접촉, 명령, 생존을 NPZ에 쓰고, 판정 성분을 JSON에 쓴다. `ex42_score.py`는 NPZ에서 다시 집계하여 영수증 숫자와 대조한다.

## prep 에 고정한 승인값

팀장 승인 5fc05cf9는 `turn_left`, `turn_right`, `stop_restart` × `eval_gt`, `eval_pred` 6 판정 칸과 같은 세 과제 × `probe_prop_only` 3 기록 칸이다. `judge_cases` 와 `record_cases`는 문자열 ID 목록, `case_specs`는 ID마다 `{task, map_mode, role}`이며 역할은 각각 `judge`, `record_only`다. 세 과제와 세 모드는 코드가 지원하지만 목록과 칸 수는 prep 이 정한다.

`stairs_landing` 에 원본 디렉터리와 위 SHA를 `source_mesh_dir`, `source_mesh_sha256`로 고정했다. `timing`에는 `settle_s`, `approach_limit_s`, `stop_s`, `restart_limit_s`, `stop_hold_s`, `top_hold_s`, `stop_speed_mps`, `foot_below_top_m`, `foot_stop_z_tolerance_m`이 있다. 시간은 순서대로 1, 4, 2, 6, 1, 0.5초다. 정지는 몸통 root x가 [1.6, 1.9] 안이고 수평 속도 ≤ 0.05 m/s인 상태가 1.0초 이어질 때로 판정한다. 발 높이는 기록만 하며 정지 통과 조건에 쓰지 않는다. analyst의 [앵커 실측](/home/jay/mai/tmp/analyst-lx/D44-SIX-ANCHORS-1111.json)은 정지 띠 내부 디딤면이 0.48 m이고 기존 0.32 m는 직전 디딤면이라고 적는다. prep의 `stop_surface_z_m`을 0.48 m로 고쳤다. `valid_min`은 D176 승인값 48로 기록했다. 꼭대기 판의 발 높이 조건은 그대로다.

진행 조건: 승인된 6+3 칸과 시간·판 위 정의가 prep에 들어갔다. lead가 한 번 Kit 예행을 실행해 실제 env 원점, 지도 선택, reset과 영수증을 확인해야 한다. 이 보고서의 CPU 통과를 Kit 통과로 쓰지 않는다.

## CPU 근거

`확인됨`: 실행 환경은 `/home/jay/miniforge3/envs/isaac311/bin/python`, `CUDA_VISIBLE_DEVICES=`이다. Linux 기기 프로필을 source한 관련 시험 74개 통과 (`test_ex42_score_cpu.py`, `test_ex42_split_eval_cpu.py`, E1 entry/approval/judge, D44 cells/tile). 유효 47 HOLD, 유효 48에서 성공 39·생존 45 PASS, 성공 38 FAIL, FAIL과 HOLD 공존 시 FAIL, 기록 전용 칸의 판정 편입, 칸 신원 변경, 정지 유지 2.1초, 발 높이가 0.48 m와 다른 정지를 답 아는 입력으로 확인했다. 새 Kit 자식의 실제 AppLauncher 인자 해석에 device=cuda:0, headless=true, kit_args를 넣어 envs=63 사전 거절을 확인했다. Kit 앱은 띄우지 않았다. 고정 원본 타일 재생성과 64 복제 preflight도 CPU 통과했다. 출력: `/home/jay/mai/tmp/scripter/d44-replica-latest-1111/replica_receipt.json`.

## 남은 위험

실제 Isaac rollout은 미실행이다. 특히 `env.reset()` 뒤 고정 타일 배정과 새 root 위치, 감지된 발 접촉, 각 지도 모드, stop-band 진입을 Kit에서 확인해야 한다. CPU 시험은 계산과 입력 계약만 확인한다. D44 증거가 없는 E1 P1은 HOLD를 유지하는 것이 의도된 안전 상태다.

## 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v0.3 | 2026-11-11 | D176 유효 표본 하한 48과 비례 문턱 · 정지 root/속도 계약 · 디딤면 0.48 m 실측 · 관련 CPU 74개 통과 |
| v0.2 | 2026-11-11 | 팀장 승인 5fc05cf9의 6+3 칸과 시간, 원본 메시 SHA를 prep에 고정 · CPU 70개 통과 |
| v0.1 | 2026-11-11 | CPU 평가 경로와 승인 전 계약 제안 |
