# EX-41 최종 결정 반영 대조 (D100~D168 · RULES-HUB 영상 절 · R01) · 2026-11-03

- 분류: 점검 자료 · 팀장 15:3x 「최종 결정사항이 제대로 반영 안 된 것 있는지 제대로 체크」 (lead 15:3x 의뢰 · M86 범례 되돌아감 뒤)
- 작성: planner · 2026-11-03 15:4x · `feature/fable-25a-jay`
- 근거(전부 읽기 등급 · 실행 0): WORKLIST 43bd8207 「확정」 D80~D168 · R01-1~10 · RULES-HUB 4 절 · CURRICULUM-GATES 결정 반영 표 ↔ runner HEAD `8ce15afe`(feature/ex41-b6-b7-runner, 작업 사본에 미커밋 6 · 새 파일 4 는 대조 제외) · scripter HEAD `534d1fa5`(D:/mai-wt/foothold-lab/scripter-w78-video) · C층 고정 사본 `5027e4ad` · 시작 스크립트(runner HEAD 의 train_start.py · ex41_startup.py · start_runner.py · ex41_start_preflight.py)
- 요지: 막음 7. 「완료로 적혔는데 최신 판에 없는 것」 은 R01-9(난도 → 레벨 표기, v9 부터 폴백이 「난도 0.50」 으로 되돌아감) 하나. 더 큰 문제는 합성기가 두 갈래로 갈라져 어느 HEAD 도 D165~D168 과 D166 을 함께 갖지 않고(runner 판 v3.3 은 PUSH 상자가 첫 밀기 뒤 영원히 남음), RULES-HUB 영상 절에 v3.4 행이 없으며, C층 고정 사본은 v3.2 라 현재 판 검사에서 거절된다. 학습 결정(D105 · D123 · D124 · D126 · D130 · D133 · D142 · D153~D156 · D166)은 yaml · 코드에 반영되어 있다
- 상태: 목록만 · 고친 것 없음 · 코드 · GPU · Kit 실행 없음

## 0. 대상과 방법

| 대상 | 판 | 비고 |
|---|---|---|
| runner EX-41 | `8ce15afe` 2026-11-03 14:36 「Unify video legend and push panel layout v3.3」 | 작업 사본 미커밋: eval_map_modes.py · ex41_gpu_priority.py · ex41_eval_once.py · ex41_score_watch.py · train_start.py · test_ex41_eval_schedule_cpu.py 수정, ex41_push_ladder.py · ex41_push_ladder_bundle.py · 시험 2 새 파일. HEAD 만 대조 |
| scripter 합성기 | `534d1fa5` 2026-11-03 15:11 | runner HEAD 는 scripter HEAD 의 조상이 아님(`git merge-base --is-ancestor` 거짓). 두 HEAD 사이 foothold_s2 차이 62 파일 +1263 −4162 |
| C층 고정 사본 | `5027e4ad` 2026-11-02 21:28 | `VIDEO_RULE_VERSION = "v3.2-D140"` |
| 시작 스크립트 | runner HEAD 의 네 파일 | |

판정 칸: **반영됨** · **빠짐**(결정은 있는데 코드 · 연결 없음) · **되돌아감**(한 판에 있었는데 최신 판에 없음) · **시험 없음**(코드는 있는데 시험 0) · **부분** · **대상 아님**(코드 결정이 아님). 줄 번호는 그 판의 파일 기준.

## 1. 막음 7

| # | 결정 | 구현 자리 | 판정 · 근거 |
|---|---|---|---|
| M1 | D165 · D166 · D167 · D168 (영상 · 평가 주기) | runner HEAD `foothold_s2/eval/video25/compose_25e_v2style10.py:41` `v3.3-D167`, `push_event_overlay.py`(v3.3: `events = [... if t_s <= time_s]` 마지막 이벤트를 영원히 그림, 바탕 (20,24,30), 몸통 화살표 없음) · scripter HEAD 같은 파일 `:43` `v3.4-D168`, `active_push_event` 회복 창 안만, `draw_push_scene_arrow`, `a_push_video.py`(335 줄, runner 에 없음) · 반대로 scripter HEAD 에는 runner 의 `ex41_eval_once.py` D166 주기(−223 줄) · `ex41_turn_receipt.py`(−166) · `ex41_ops.py`(−130) · `test_ex41_eval_schedule_cpu.py`(−230) 가 없음 | **두 갈래 · 통합 없음**. 「최신 판」 이 둘이고 어느 쪽도 D165~D168 + D166 을 다 갖지 않는다. runner 판으로 기동하면 영상은 v3.3(D168 빠짐 · PUSH 상자 영구), scripter 판으로 찍으면 평가 주기 D166 코드가 없다. 기동 전 통합 커밋과 그 커밋의 판 값 · 시험 확인이 필요 |
| M2 | D168 영상 v3.4 (RULES-HUB 규칙 「영상 규칙을 바꾸는 결정이 나오면 같은 커밋에서 (1) 이 절 (2) 합성기 판 값 (3) 판 검사 시험」) | `inbox/jay/20261019-design/RULES-HUB.md:83~90` 4 절: v3.3 행이 마지막, 「판 고정 장치 … 지금 `v3.3-D167`」 · lead 커밋 `43bd8207`(D168) 은 FAILURE-LOG · GATES · WORKLIST 만 바꿈 | **빠짐**(문서). v3.4 행 · 지금 판 값 미갱신. lead 의뢰문의 「영상 절(v1~v3.4)」 과 달리 v3.4 는 절에 없다 |
| M3 | D167 · D168 과 「판 고정 장치」(영수증 판이 지금 판과 다르면 거절) | C층 사본 `foothold_s2/eval/video_rule.py:7` `v3.2-D140` · `c_layer_queue.py:102` 자기 판과 합성기 판이 같아야 실행 · scripter HEAD `test_c_layer_queue.py:45` · `test_plan_c_layer.py:36~38` 은 `v3.4-D168` 만 통과, `v3.2-D140` 을 옛 판으로 거절 | **되돌아감(고정 사본)**. C층이 지금 찍는 영상은 범례 끝선(D167) · PUSH(D168) 없는 v3.2 영수증이라 현재 판의 전 프레임 검사 · 재생 목록 · 단계 끝 루프에서 보류된다. 원자료(npz · attention)로 재합성하거나 사본 판을 올리는 결정 필요(D131 「정본 규칙대로」) |
| M4 | D165 밀기 영상이 단계 끝 묶음에서 돈다(D166 「단계 끝 = 축 전부 + 밀기 D165」) | scripter `a_push_video.py` 는 독립 CLI(호출자 0, `git grep a_push_video` 는 자기 파일과 `record_c_layer.py:66 · 73` 뿐) · runner HEAD `ex41_ops.py` · `ex41_eval_once.py` · `ex41_w78_video_request.py` 에 `push` 0 건 | **빠짐(연결)**. 영상 코드와 시험 8 은 scripter 에 있으나 EX-41 단계 끝 사슬에 묶여 있지 않다 |
| M5 | D168 밀기 사다리(0.5~3.0 m/s × 8 방향 × 지도 셋, 첫 기준선 m6000) · 학습 밀기 상한 올림 | runner 작업 사본 미커밋 `foothold_s2/eval/ex41_push_ladder.py:11~19`(MAGNITUDES 0.5~3.0 · DIRECTIONS 8 · MAP_MODES 3 · TERRAIN flat/random_rough/pyramid_stairs · 64 env · PUSH_AT 2.0 s · FOLLOW 5.0 s · 생존 0.90) + 시험 2 · 어느 HEAD 에도 없음 · yaml `ex41-fixed5000.yaml` `push_velocity` x · y ±1.0 그대로 | **빠짐(미커밋)**. 사다리 코드는 커밋 · 실행 · 연결 전. 학습 상한 숫자는 D168 대로 lead 가 m6000 실측 뒤 정함(대기). W 카드 없음(GATES D168 행은 「W94 · runner」 인데 W94 카드 본문은 B층 · scripter) |
| M6 | D136 force_gt 끈 구간마다 use_gt_frac 재서 보고 · D143 P7-4 T0′ use_gt_frac ≤ 0.3 | 학습 기록 `curriculum/continuous.py:374~396` `use_gt_envs` 는 있음 · EX-41 보고기(`ex41_ops.py` · `ex41_score.py` · `curriculum/ex41_fixed.py` · `scripts/ex41_startup.py`) 에 `use_gt` 0 건 | **빠짐(보고)**. T0′(4501~5000, force_gt false) 에서 재서 보고할 코드가 없다 |
| M7 | D143 P7 졸업 판정 G1~G8 · P7-5 복원 모드 오차 칸 기동 전 | runner HEAD `curriculum/ex41_fixed.py:237~238` `graduation_spec_status: separate approved spec and final evidence required` · `test_ex41_p7_cpu.py` 시험 2 는 「끝 저장본 평가 요청 한 번」 만 · `ex41_scoring.py` 에 복원 오차 필드 0 | **빠짐**(앞 감사 M7 그대로). 판정은 사람 몫으로 남아 있고 코드 · 시험 없음 |

## 2. 「완료로 적혔는데 최신 판에 없는 것」 · 되돌아감

| # | 항목 | 완료 근거 | 최신 판 | 판정 |
|---|---|---|---|---|
| R01-9 | 「난도 0.50」 표기를 레벨로 → 「L5 (0.50)」 | WORKLIST `[x] R01-9` · lead 사본 `inbox/jay/20261028-plan/compose_25e_v2style8.py:355` `f"L{min(9, int(float(diff) * 10))} ({float(diff):.2f})"` | v9 `b5d70fe6`(10/28 02:32 「v8 복사본 위에」) 부터 폴백이 `f"난도 {float(diff):.2f}"` · v10 `e7ec13b3` · runner HEAD · scripter HEAD(`compose_25e_v2style10.py:435`) · C층 사본 전부 같음(`f"L{min(9` 0 건) | **되돌아감**. R01-9 는 v9 가 복사된 뒤(03:0x) v8 에 적용되어 v9 · v10 에 넘어가지 않았다. 지금 EX-41 촬영은 `selected_environment.kind` 경로(`:430` 「L5」)라 화면에는 안 보이고, 깃발 · 옛 꼴 영수증에서만 드러남. 영향 낮음, 유형은 M86 과 같음 |
| D167 범례 | 범례 = 계기판 끝선 | scripter 7d82ab77 · runner 8ce15afe | 둘 다 `GAUGE_X0, GAUGE_X1 = 1084, 1272` · `LEGEND_RECT = (GAUGE_X0, 34, 188, 14 + 17·n)` · `GAUGE_Y0 = 끝 + 8` · 시험 `test_push_event_overlay.py:57`(상자 일치 · 겹침 0 · 넓히면 실패 · 화살표를 글줄로 밀면 실패) | **반영됨 · 시험 있음**(M86 복구 확인) |
| D168 v3.4 | PUSH 상자 회복 창만 · 범례 복귀 · 연한 빨강 · 화살표 중점 = 상자 중점 · 몸통 화살표 | scripter 2a5886a1 · e74402b5 | scripter: `active_push_event`(t_s ≤ t ≤ t_s + median, 없으면 1.5 s) · `compose:932~940` 밀기 중엔 범례 대신, 아니면 범례 · `box_arrow_points` 중점 = 상자 중점 · `draw_push_scene_arrow` 몸통 +0.20 m · 시험 `test_v34_receipt_…` · `test_world_push_arrow_…` · `test_legend_fixed_bounds_in_all_map_modes` | **반영됨(scripter) · runner 판엔 없음**(M1). 바탕색은 BGR (85, 90, 165) = 어두운 적갈색: 「연한 빨강」 인지는 정지 화면 미확인 |

## 3. 영상 결정 · R01 대조 (코드 상수 · 판 값 · 시험)

| 번호 | 요지 | 구현 자리(scripter HEAD 기준, 다르면 표시) | 판정 |
|---|---|---|---|
| R01-1 | 범례 12 px · 계기판 위로 | `compose_25e_v2style10.py:404` `LEGEND_ROW, LEGEND_FONT = 17, 12` · `:870` 12 px 넘치면 ValueError | 반영됨 |
| R01-2 | 지형 · 레벨 줄 | `:424~435` `terrain_text` · `:602~606` | 반영됨 |
| R01-3 | 「옆」 → 「좌우」 | `:612` `("좌우 m/s", …)` | 반영됨 |
| R01-4 | 미니맵 안쪽 여백 | `:681` `INSET = 16` | 반영됨 |
| R01-5 | 에피소드 따라감 · 넘어짐 1 초 · 판 번호 · 횟수 | `:408` `FALL_HOLD_ROWS = 50` · `:566~572` · `:752` | 반영됨 |
| R01-6 | 막대 범위 ±1.5 · ±1.0 · ±2.0 | `:612~613` | 반영됨 |
| R01-7 · 10 | 팀장 확인 · 점검 문구 | 코드 대상 아님 | 대상 아님 |
| R01-8 | v8 사본을 lead 가지에 | `inbox/jay/20261028-plan/compose_25e_v2style8.py` 존재 | 반영됨 |
| R01-9 | 난도 → 레벨 | 2 절 | **되돌아감** |
| D137 (A) | 색 범위 95 백분위 · 최소 ±5 cm · 숫자 | `:56` `MAP_MIN_SPAN_M = 0.05` · `:126` · `:231` percentile 95 · `:260` 「Map colour range …」 | 반영됨 · 시험 `test_video_v31_map_colours.py` |
| D137 (B) | 128 칸 열지도 · 눈금 0~0.3 | `:57` `ATTENTION_MAX = 0.30` · `:151` `attention_heatmap_tile` · `:240` 16×8 | 반영됨 |
| D139 (C′) | 노란 발 스캔 점은 다음 촬영부터 끔 · 정답 지도 색 유지 | `record_c_layer.py:2070`(scripter) · `:1954`(runner HEAD) `scene_foot_scan_visible: False` · `compose:833` 옛 기록만 범례 유지 · 시험 `test_legacy_scene_keeps_foot_scan_legend_but_new_recording_does_not` · `test_future_scene_overlay_cannot_draw_yellow_foot_scan_points` · `test_gt_and_reconstruction_keep_colour_…` | 반영됨 · 시험 있음 |
| D140 | 뜬 발 세 칸 같은 검은 회색 | 영수증 `feet_markers: airborne-hollow-black-gray-all-three-map-panels` · 시험 `test_airborne_foot_uses_same_black_gray_in_all_three_map_panels` · C층 39bdcfa3 | 반영됨 |
| D152 | C층 headless | C층 `record_c_layer.py:1150` `args.headless = True` · `test_c_layer_headless.py` | 반영됨 |
| D157 | C층 칸마다 성공 한 편 · P4 · P1 양보 | C층 `plan_c_layer.py:52 · 95 · 130` `--first-success-only` 옵션 · `c_layer_queue.py:110` P1 표식 `D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1` · `:366~395` 양보 | 반영됨(성공 한 편은 플래그라 실행 명령에 붙여야 함 · 시드 42~45 네 개) |
| D100 · D131 | C층 세 모드 · m6000 정본 | C층 `record_c_layer.py:103` SB 모드 셋 · `plan_c_layer.py:53 · 68` model_6000 · d5e9ec40 | 반영됨 |
| D102 · D98 | 재생 목록 고정 폴더 `s2_lab/_playlists` · EX번호-m단계-all/fail | runner HEAD `scripts/make_ex41_playlists.py:32 · 57`(`C:/Users/AI-WS01/s2_lab/_playlists` · `EX-41-m%05d-{all,fail}.m3u8`) · 호출자 0 | 부분(코드 있음 · 단계 끝 사슬 연결 없음, 앞 감사 M2 중 폴더는 맞음) |
| D88 | done = 영상 수 = 목록 수 · 전 프레임 검사 0 | runner HEAD `ex41_w78_video_request.py` 는 요청 파일만 만듦(검사 · 수 세기 0) · C층은 `c_layer_frame_audit` 로 함 | A층(W78 영상) 쪽 미확인 · 코드 못 찾음 |
| D149 | 학습 GPU0 · 촬영 · 평가 GPU1 | `ex41_eval_once.py:63 · 220` `cuda:1` · `ex41_startup.py:485 · 503 · 514` 예행 · smoke · 재개는 `cuda:0` 강제 · 본 기동은 `ex41_start_preflight.py:174` 「cuda:0 또는 cuda:1」 허용 | 부분(본 기동 cuda:0 은 명령 인자에 달림) |
| D165 | 밀기 영상 · 지도 셋 · 회복 지표 | scripter `a_push_video.py:27` MODES 셋 · `:108~109` push_events 1 건 + dr_recovery.defined 필수 · `:281~294` 세 모드 지형 · 시드 · 저장본 일치 · `record_c_layer.py:1460~1467` DRMode on · `ex41-fixed5000.yaml` 표 · push_seed · 시험 8 | 반영됨(scripter) · 연결 없음(M4) · 「학습과 같은 interval_push」 는 클립 6.0 s 와 학습 간격 10~15 s 가 어떻게 맞춰지는지 미확인 |
| D167 · D168 | 2 절 | | |

## 4. 학습 결정 대조 (yaml · 코드 줄, runner HEAD)

| 번호 | 요지 | 자리 | 판정 |
|---|---|---|---|
| D96 · D105 · D108 | 전진 0.23 · zero_yaw −0.5 · heading 0.3 · 후진 [−1.3, −0.2] | `ex41-fixed5000.yaml` shares forward 0.23 · reverse 0.14 · ranges reverse_vx [−1.3, −0.2] · side_vy_abs [0.2, 0.6] · heading forward_fraction 0.3 · first_rewards zero_yaw −0.5 | 반영됨. 단 D108 「옆 0.5」 와 yaml 옆 0.6 은 문서끼리 다름(낮음) |
| D110 · D130 | 서 있기 10 · 61/64 · 스윙 반감 한 번 · +500 한 번 · +1000 상한 · 2 경계 회복 · 3/64 | yaml stand 0.1 · automatic.stand_min_passed 61 · fixed_schedule pause_limit 1000 · recovery_boundaries 2 · extension 500 × 1 · maintenance_drop_count 3 · approvals automatic.stand_restore · extension · `ex41_fixed.py:64~65`(61 강제) · `:465~485`(반감 max(−20, min(−2, old/2)) 한 번 · D110 연장 한 번) | 반영됨 · 시험 `test_ex41_fixed_cpu.py` |
| D115 | p_map_off 0.1 | `ex41_startup.py:679~681` 부모 p_map_off 검사 | 반영됨 |
| D116 | Kp 25 · Kd 0.5 막음 · PPO 엔트로피 · KL 만 | `ex41_startup.py:941~948` stiffness · damping 이름 검사 · 값은 `baseline_env_yaml_sha256` 고정(`:739`) · boundary ppo entropy 0.01 · desired_kl 0.01 · `w72.py:13` 범위 | 부분(값 25 · 0.5 를 직접 비교하는 줄은 없고 sha 로 묶음) |
| D117 | 미리 등록 항 0 가중 · 걸림 −2 · 기존 항 유지 | yaml first_rewards knee_effort_margin · joint_limit_margin · feet_air_time · foot_slip 0.0 · stumble −2.0 · `rewards/w86-preparation.yaml` existing_terms | 반영됨. 단 그 yaml 머리 `execution_connected: false` · zero_yaw `approved_value_unwired` 는 `start_runner.py:129~131 · 549~581` · `ex41_startup.py:688 · 718`(`ex41_w86_required = True`) 와 어긋나는 낡은 메타(낮음) |
| D121 | 종료 조건 · 에피소드 길이 열되 바꾸면 기록 | boundary `episode_length_s: 20.0` · `w72.py:13` (1, 120) 범위 | 부분(「과제 변경 기록 + 전후 같은 평가」 자동 장치는 못 찾음) |
| D123 | 걸림 −2 [−3, −1] · 스윙 −10 [−20, −2] | yaml · approvals bounds | 반영됨 |
| D124 · D135 | 부모 m6000 d5e9ec40 · 전수 점검 먼저 | yaml parent_update 6000 · parent_sha256 · `ex41_start_preflight.py:33~88`(detached · clean · HEAD 일치 · 부모 이름 · SHA · manifest) · `train_start.py:116~118` | 반영됨 |
| D126 | 750 · 1000 · 1000 · 1250 · 500 · T0′ 500 · DR 0.5→0.65→0.8→1.0 · L5 상한 | yaml stages fixed_update 0 · 751 · 1751 · 2751 · 4001 · 4501 · dr_stage_end_scales [0.5, 0.65, 0.8, 1, 1, 1] · level_cap 2 → 5 · `ex41_fixed.py:60~69` 값 고정 검사 | 반영됨 |
| D132 | 지도 모드 셋 강제 | `eval/ex41_map_modes.py:6~23` REQUIRED_MODES · 빠지면 ValueError | 반영됨 |
| D133 · D160 | 판정 26 · 기록 13 · 39 보존 | yaml include_record_only false · `ex41_scoring.py:87` total_envs 64 | 반영됨 |
| D141 | lin_vel_z 0 유지 | EX-41 yaml · 코드에 항 없음(부모 env.yaml sha 고정) | 부분(명시 검사 없음) |
| D142 · D155 · D101 | S = min/max · 0.8 · 연속 2 · 자동 켬 없음 · 승인은 W72 | `curriculum/ex41_symmetry.py:26~34 · 80` · yaml critic_both_fail_fraction 0.8 · required_consecutive 2 · boundary `critic_mirror: false` · approvals 에 critic_mirror 없음 · `start_runner.py:132~138 · 334~365` APPROVED 영수증 · `ex41_fixed.py:267~` 사이드카 비교 | 반영됨 · 시험 `test_ex41_p3_cpu.py` · `test_ex41_symmetry_cpu.py` |
| D153 · D154 | 직전 경계 점수(n−1−250) · W78 없으면 26 칸 유효 | `ex41_fixed.py:214~215` `expected = n-1-interval` · `:302` `sidecar_missing` 은 P3 만 결측 | 반영됨 |
| D156 | END_BY = 예상 끝 + 최대 연장 + 24 h · 경보만 | `ex41_startup.py:44 · 589~662` `EX41_END_BY_BUFFER_SECONDS = 86400` · `action: warning_only` · `ex41_ops.py:214~218` | 반영됨 |
| D166 | 250 마다 26 + 13 + 계단 옆 좌우 쌍 · 단계 끝 전부 · 60 분 조건 | `ex41_eval_once.py:24~30` PERIODIC `stairs_side_left,stairs_side_right` · FULL 10 경우 · `:51 · 55` 각도 0/30/60/90 · 시험 `test_scope_commands_use_side_w78_every_250_and_full_w78_at_stage_end` · `test_measured_periodic_side_cost_fits_one_250_update_training_interval` · `test_core_score_is_published_before_stage_end_auxiliary_dispatch` | 반영됨(runner 에만 · M1) |
| D128 | 정지 뒤 각속도 · heading · 후진 횡 이탈 지표 | `eval/axis_v2_cells.py:82 · 203` stop_end_error_rad · stop_yaw_drift_rad · W78 FULL `stairs_fwd_stop_back` · 영상 머리줄 `Heading from start … lateral drift` | 반영됨(부분: 「정지 뒤 후진 횡 이탈」 은 영상 머리줄과 W78 경우로만) |
| D151 | 단계 끝 7 저장본 16 env 진단 | `eval/ex41_turn_receipt.py:1~5` 「W91 CPU 영수증 · 관문 아님 · GPU1 사슬은 runner」 · 호출자 미확인 | 부분(앞 감사 L7 그대로) |
| D136 · D143 | 1 절 M6 · M7 | | 빠짐 |
| D168 학습 상한 | 1 절 M5 | | 대기 · 미커밋 |
| D164 (가) C: 자리 | 되읽기 D: 강제(앞 감사 M1) | runner HEAD `ex41_startup.py:249~262` `_require_ex41_run_path` 가 C: smoke · main/<run> 허용, 되읽기 `:757 · 812` 가 이것을 씀. `_require_d_drive` 는 예행 `:482 · 516` 만 | **반영됨 · 앞 감사 M1 닫힘**(dfa0bd58). W97 카드 「`:730 · 783` D: 강제」 문구는 낡음 |

코드 대상이 아닌 결정(대조 안 함): D103 · D104 · D106 · D107 · D111~D114 · D118~D120 · D122 · D127 · D129 · D134 · D138 · D144~D148 · D150 · D158 · D159 · D161~D164(폴더 · 앱 · 역할 · 일정 · EX-42 설계). D109 · D117 「성과에 따라 가중 가변」 은 D130 이 「반감 한 번」 으로 좁혀 D130 기준으로 봄. D94 · D125 「DR 켠 평가 칸 하나 · 배율 1.0」 은 W57 칸 코드를 열지 않아 미확인(a_push 의 dr_scale 1.0 만 확인).

## 5. 낮음 (문서 · 카드)

- L1 W94 카드(`WORKLIST.md:302`) 「영상 v3.2(D140)」 → 지금 판 v3.4. GATES D165 · D167 · D168 행이 W94 를 가리키나 W94 본문은 B층 규칙 ①~⑦ 뿐이고 밀기 영상 · 사다리 · v3.4 언급 0. D165~D168 을 본문에 적은 W 카드 0.
- L2 W97 카드 「ex41_startup.py:730 · 783 D: 강제 충돌」 은 runner HEAD 에서 닫힘(4 절 끝 행). 카드 문구 갱신 필요.
- L3 GATES D166 행 「W93 · W97」: D166 코드는 runner HEAD 에 있으나(반영됨) 카드 W93 은 P3 승인 절차만. 평가 주기 카드 없음.
- L4 `rewards/w86-preparation.yaml` 머리 `execution_connected: false` · `approved_value_unwired` 낡음(4 절 D117).
- L5 D108 「옆 0.5」 vs yaml side_vy_abs 0.6 (4 절).
- L6 D149 본 기동 cuda:0 코드 강제 없음(예행 · smoke 만).
- L7 D157 「성공 한 편」 은 `--first-success-only` 플래그(기본 아님).
- L8 D102 재생 목록 스크립트 호출자 0 · D88 A층 영상 수 검사 못 찾음.
- L9 runner 작업 사본 미커밋 10 파일(0 절). HEAD 대조라 이 변경(D168 사다리 · eval 주기 수정)은 보지 않음.
- L10 D168 PUSH 바탕 (85, 90, 165) BGR 이 「연한 빨강」 인지 정지 화면 미확인.

## 6. lead 가 정할 것

1. M1 통합: 어느 가지를 기동 판으로 쓸지(runner 에 scripter 의 a_push_video · v3.4 를 얹을지, 반대로 할지), 통합 커밋 뒤 `VIDEO_RULE_VERSION` · 시험 · D166 시험을 한 판에서 돌릴지.
2. M2 RULES-HUB 4 절 v3.4 행 · 「지금 판」 값(lead 몫, 규칙 8).
3. M3 C층: 사본 판을 v3.4 로 올릴지(새 plan SHA · W92) · 이미 찍힌 칸은 npz 재합성인지.
4. M4 · M5 연결과 카드: 밀기 영상 · 사다리를 어느 W 에 두고 누가 단계 끝 사슬에 묶는지(GATES 는 W94 · runner).
5. M6 · M7 use_gt_frac 보고 · P7 판정 코드를 기동 전 둘지 T0′ 전까지 둘지.
6. R01-9 를 v10 에 되살릴지(지금 화면 영향 없음) · 되살리면 v3.5 판 값인지.

## 7. 안 한 것

코드 · 시험 · GPU · Kit 실행 없음(모두 읽기). runner 작업 사본 미커밋 변경 미대조. D01~D79 미대조(의뢰 범위 「특히 D100~D168」, D80~D99 는 영상 · 평가 관련만 봄). W57 칸 코드(D94 · D125) 안 엶. 정지 화면 · 영상 파일 안 봄(색 · 배치는 상수와 시험으로만). scripter 가지의 EX-41 학습 코드(runner 와 다른 −4162 줄)는 「없음」 만 세고 내용 미대조. D166 「좌우 조합 60 분 이하」 는 시험 이름으로만 확인, 실측 수치 안 봄.
