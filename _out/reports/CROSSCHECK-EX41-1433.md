# EX-41 기동 전 교차 검증: 결정 · 설계 v0.7 대 작업자 코드 (읽기 전용)

> 분류: A/검증
> 작성: planner (Claude Fable 5.1) · 2026-11-02 14:33 · lead 14:3x 의뢰(팀장 지시 · 읽기 전용 · 코드 수정 · GPU 금지)
> 근거: WORKLIST 4691a13c D80~D132 · W56~W86 · FAILURE-LOG 4691a13c M79~M82(M83 은 D132 가 인용하나 원격 파일에 없음) · 설계 v0.7 ba44f45d · 작업자 worktree 다섯(아래 §0) · 실측 파일 `score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json`
> 요지: 통합 브랜치(runner-ex41-b6-b7 ea51caab) 의 시작 경로는 부모 m6000 · DR 0.5 · 5,000 회 6 단계 · 250 경계 W72 재읽기 · 서 있기 복원 · 거울 소비자까지 이어져 있다. 그러나 **점수 파일 생산자가 시작 경로 어디에도 없어** 기동하면 첫 램프 경계(n751)부터 「증거 없음 유지」 가 걸리고 1,000 회 뒤 DR 이 0.5 에 동결된 채 5,000 회를 다 돈다(코드 읽기, 아래 §2 Q2 · §5 막음 1). 그 밖에 w71_ready false 로 기동 자체 거절(막음 2) · 설계 v0.7 과 코드가 네 자리에서 어긋남(연장 대상 · Δ 문턱 · 몫 2 차 자리 · 서 있기 복원 서술) · W78 v2 · W75 영상 코드 부재 · 거울 관절 블록 시험이 기본값에서 skip.
> 상태: 보고. 코드 · 설정 · GPU 손대지 않음. 숫자는 코드 읽기 · 실측 파일 하나(위) · 계산만. 다른 세션 보고는 「상황판 읽기」 로 표시.

## 0. 대조 기준과 범위

| 쪽 | 기준 | 비고 |
|---|---|---|
| 결정 | WORKLIST `inbox/jay/20261019-design/WORKLIST.md` @ origin/feature/verify-v2-mvp-jay 4691a13c, D80~D132(107~160 행) · W56~W86(228~258 행) | 사본 `scratchpad/wl4691.md` |
| 실패 기록 | FAILURE-LOG 같은 커밋 M01~M82 | M83 본문은 원격에 없음(D132 인용만) |
| 설계 | DESIGN-EX41-STAGE2-draft.md v0.7 ba44f45d (feature/fable-25a-jay) | planner 자기 문서 · 가정 Q26 · Q27 포함 |
| 코드 (통합) | `C:/mai/wt/foothold-lab/runner-ex41-b6-b7` ea51caab (feature/ex41-b6-b7-runner) | analyst fdf1ce33 · scripter 36f6cddf 까지 머지 |
| 코드 (미머지) | analyst-ex41-b12-1102 ced6c43a(더티: tests 수정 1 · 보고 6 미추적) · scripter-ex41-b345 aba6c6e8 · scripter-ex41-ppo 8cab09f2(68cffa0f 포함) · scripter-w75-w76 4f718ae6(더티: c_layer_queue.py · 시험 · 설계 수정 · record_c_layer.py 1,870 행 미추적) | runner 는 ced6c43a · 68cffa0f 를 안 가짐. ced6c43a 의 fdf1ce33 대비 차이는 ex41_fixed.py 신설 · continuous.py 3 행 · ex41.py 19 행 · w86_runtime.py 20 행(_sanitize 사본 반환) · yaml 셋 · 시험 셋. runner 에도 같은 이름 파일이 있고 내용 동일 여부는 ex41_critic_mirror.py 만 diff 로 확인(동일), 나머지는 미대조 |
| 저장소 밖 | `C:/Users/AI-WS01/s2_lab/tools/shadow_loop.sh` · `ex40_main_20261031_041313/*.sh` · `ex40_w78_terrain_skill/` | EX-40 의 그림자 · 축 · 영상 루프. 정본이 저장소 밖에 있음 |

시작 경로(코드 읽기): `foothold_s2/scripts/train_start.py --ex41_table ... --ex41_parent_checkpoint ...` → `ex41_startup.load_fixed_plan` · `require_production_authorization` · `verify_m6000_parent` → AppLauncher → `prepare_ex41_env_cfg`(보상 등록 · DR 0.5 · 지형 · W86) → gym.make → `set_live_initial_dr_scale` · W86 `attach_runtime` → `configure_ex41_train_cfg` → StartRunner → `load_ex41_parent` → `continuous.make_runtime` :62~65 → **EX41FixedRuntime** → `attach` · `set_stage_changed_hook(apply_runtime_fields)` · `start(parent_sha)`. 학습 루프에서 `start_runner.py:461 continuous.on_update_start(it)` · `:464 ex40_dr_runtime.update_start(it)`(EX41DRReadback, `ex41.py:213 · 660~672`) · `:653 · 667 on_checkpoint`. **그림자 평가 · 점수 생산 · 영상 루프를 띄우는 줄은 train_start · ex41_startup 어디에도 없다**(grep shadow · score_watch · subprocess · Popen 0 건).

## 1. 상태 표: 결정 → 코드 위치 → 시작 경로 연결 → 시험 종류 → 상태

시험 종류 표기: **끝점** = 답을 결정 · 실측에서 미리 알고 거는 시험, **복제** = 구현이 낸 값 · 모양을 그대로 기대값으로 쓴 시험, **가짜 입력** = 코드가 요구하는 모양대로 시험이 지어낸 입력(M79 · M80 꼴).

| 결정 | 코드 위치 (runner ea51caab) | 시작 경로 연결 | 시험 | 상태 |
|---|---|---|---|---|
| D124 부모 m6000 (SHA d5e9ec40…) · B3c 끝 | `curriculum/ex41-fixed5000.yaml` parent_update 6000 · parent_sha256 · baseline env/agent yaml SHA; `ex41_startup.verify_m6000_parent`; `start_runner.load_ex41_parent`(ex41_transfer) | 연결(train_start → verify → load_ex41_parent) | `test_ex41_startup_integration_cpu:44` 실제 yaml 끝점 · `test_ex41_b345:121` 0 열 비트 동일(끝점) | **있음 · 연결** |
| D125 DR 켠 평가 칸 배율 1.0 | 평가기(eval_map_modes · axis_v2_run) 의 DR 배율 인자는 이 검토에서 안 봄 | 미확인 | 미확인 | **미확인** |
| D126 5,000 회 · 6 단계 회차 고정 · 램프 0.5 → 0.65 → 0.8 → 1.0 | yaml stages S2a(0,750) S2b(751,1000) S2c(1751,1000) S2d(2751,1250) S2e(4001,500) T0_prime(4501,500); `ex41_fixed.py` POINTS ((0,.5),(750,.5),(1750,.65),(2750,.8),(4000,1),(5000,1)) · `Clock.scale` 선형 보간 · `on_update_start` :148~153 경계 n≥1 · (n−1)%250==0 | 연결(continuous :62~65 · start_runner :461 매 회차 · :464 EX41DRReadback 가 `runtime.dr_scale(update)` 를 회차마다 읽음 → 램프는 회차마다 선형, 250 계단 아님) | `test_ex41_fixed_cpu:56` 끝점(1.5e−4 · 1.6e−4 는 결정값) · `:99` 단계 이름 끝점 · `:128` smoke | **있음 · 연결** |
| D126 DR 유지(유지 칸 < 기준 − 3/64) · 연속 2 경계 회복 재개 · 상한 +1,000 | `ex41_fixed.maintenance()` (passed < baseline − 3 → 실패 목록 · 증거 결손 → None); `Clock.boundary` :85~111 (소진 → 동결; can_rise 750≤elapsed<4000; **failed None(증거 없음) 도 유지** `dr_hold_missing_evidence`; 회복은 score_iteration 간격 250 일 때만 세어 2 회면 재개) | 연결(on_update_start :176~178) | `:64` 끝점(−3 경계 · 결손 None) · `:73` · `:84` · `:91` 끝점(500 회 재개 · 1,000 소진 · 동결 0.5) | **있음 · 연결 · 결정보다 넓음**: 팀장 확정은 「성적이 떨어지면」 인데 코드는 **증거가 없어도 유지** 한다. 생산자가 없는 지금(§2 Q2) 이 분기가 기동 즉시 걸린다 |
| D126 자동 조정 셋(서 있기 복원 · +500 연장 · 보고) 만 | `on_update_start` :185~192 서 있기(61 미만 → 스윙 반감 한 번, approvals `automatic.stand_restore`) · :194~201 연장 · `_write` 보고. `EX41Runtime._automatic`(ex41.py:533~577, 좌우 ±1 %p · 낮춤 · 거울 자동) 은 **FixedRuntime 이 부르지 않음**(호출 ex41.py:512 만) | 연결 | `test_ex41_fixed_cpu:109` 끝점(−10 → −5 · 좌우 · 거울 없음) | **있음 · 연결** · 설계 v0.7 §5.11 :296 이 「서 있기 복원(D110 +2)」 로 적혀 있어 **설계 쪽이 틀림**(D130 · 코드가 맞음) → v0.7.1 수정 몫(planner) |
| D130 유지 +1,000 다 써도 미회복 → 현재 배율 계속 + 보고 · +500 연장 한 번 | `Clock.boundary` :96~98 동결 이벤트 `dr_pause_budget_exhausted_frozen_report` · 일정은 5,000 + 연장까지 진행 · 끝 `fixed_schedule_finished requires_review` :213~216 | 연결 | `:91` · `:154` 끝점 | **있음 · 연결** |
| D130 「maintenance_counts 가 점수 파일에 실제로 찍히는지 확인 뒤 기동」 | 판독기 `ex41_startup.maintenance_counts_from_map_modes` :139~165(envs 64 · 세 모드 집합 일치 · 13 사례 · env_count 64 · per_env 64 · alive_envs_at_end) · CLI `foothold_s2/ex41_score.py`(22 행, `--score-draft --map-modes --out`) | **미연결**: CLI 를 부르는 곳 없음(저장소 .py · .sh 전수 grep, s2_lab/tools 와 ex40_main 루프에도 ex41 0 건). `_read_scores` ex41.py:388~421 이 요구하는 `foothold-ex41-score/1` · stage_id · schedule_sha256 · parent_sha256 · evidence SHA · baseline_checkpoint_sha256 을 만드는 생산자 없음(ex40_score 는 `foothold-ex40-score/2`) | `test_ex41_startup_integration_cpu:93 · 104 · 117` 가짜 입력 `_map_modes()`. **실측 대조(planner, 이 검토)**: m6000 실제 map_modes.json 의 사례 행 키에 env_count · per_env · alive_envs_at_end 가 있고 envs 64 · 세 모드 이름 일치 → 판독기 모양은 실제와 맞음 | **판독기 있음 · 생산자 없음 · 시작 경로 미연결** = D130 조건 미충족 |
| D131 C층 정본 저장본 m6000 | scripter-w75-w76 `eval/c_layer_queue.py:53 validate_plan` 이 `approved_canon`(경로 · SHA) 요구 | 미연결(plan 미작성 · DESIGN-W75-W76 「정본 저장본 미결정」) | `test_c_layer_queue.py` 더티 | **설정 미입력** |
| D132 그림자 · yaw 기록은 지도 모드 셋 강제 | 강제는 **판독기 한 곳** :144~145 만. `eval_map_modes.py:30` `--modes` 기본 셋이지만 :223 부분집합 허용 · `axis_v2_run.py:158` 같음 · `ex40_score_watch.py:311` 은 stand 세 모드 + map64 phase 만 요구(map64 안의 모드 수는 안 봄) | 판독기는 시작 경로 밖(생산자 없음) | 끝점 `:104`(모드 결손 거절) | **부분**: EX-41 점수 판독기만 강제 · 평가기 CLI · W57 · W78 v2 기록은 강제 없음 · W78 v2 코드 없음 |
| D128 정지 yaw 지표 셋(정지 진입 각속도 · heading 흐름 · 후진 횡 이탈, 벌점 없음) | 코드 없음. W78 v2 는 계약 문서 `inbox/jay/20261102-analysis/EX41-W78-V2-CLI-OUTPUT-CONTRACT.md` 만 · W57 axis_v2_run 의 정지 구간 각속도 기록 여부 미확인 | 없음 | 없음 | **없음** |
| D123 걸림 −2 [−3,−1] · 스윙 5~10 % 규칙 · 막히면 −10 [−20,−2] | boundary yaml first_rewards stumble −2 · swing −10 · zero_yaw −0.5; approvals bounds swing [−20,−2] stumble [−3,−1] zero_yaw [−0.5,−0.25]; `w72.BOUNDS` 같은 값 · `w86_runtime.prepare_env_cfg` 가 기존 stumble 가중을 계획값으로 | 연결(prepare_ex41_env_cfg · `_sync_rewards` ex41.py:365~378) | `test_ex41_review_regressions:46` yaml 이 범위를 못 넓힘(끝점) · w86 시험(계산 끝점) | **있음 · 연결** · 스윙 −10 은 analyst 계산값(상황판 읽기 · 설계 Q 열림) |
| D110 상한 → 다음 단계 전환 + 보고 · 연장 한 번 | `on_update_start` :194~201 · `_level_delta` ex41.py:579~585(50 회 표본 · 첫 250 창 대 마지막 250 창) · yaml automatic.extension_level_delta **0.5** | 연결 | `:169` 끝점(연장 500 · S2e · T0′ 뒤 끝) | **있음 · 연결 · 설계와 어긋남** (§3 ①②) |
| D109 · D116 · D121 과제 변경 기록 | 설계 §2 · §8 기록만 | 해당 없음 | 해당 없음 | 기록 |
| D117 m6000 영상 관찰 · D96 · D97 · D101 · D105 | 보상 항 등록 `w86_runtime.prepare_env_cfg`(ex41_zero_yaw · ex41_swing · preregistered 0) · D97 zero_yaw 한 번 낮춤 범위 approvals | 연결 | `test_w86_runtime_cpu` 11 개(계산 끝점 · 격리) · `test_w86_preparation` | **있음 · 연결** |
| W71 지형 성과 소비자 검증 | boundary yaml `w71_ready: false`; `ex41_startup.require_production_authorization` 가 True 요구; `apply_runtime_fields` ex41.py:753 performance 면 w71_ready 필수; `on_update_start` :202~204 S2d 진입 경계 거절 | 연결 | `test_ex41_startup_integration_cpu:53` 끝점(false 면 거절) · fixed 시험은 fixture 가 True 로 바꿔 돎 | **기동 관문 열림**: 지금 yaml 로는 train_start 가 시작을 거절한다. W71 소비자 검증(실제 Kit) 뒤 True 커밋 필요 |
| W72 250 경계 재읽기 · 승인 범위 | `w72.read_committed_pair`(추적 파일 깨끗 · HEAD) · `validate_change`(:80~83 필드 추가 · 삭제 금지 · 승인 없는 변경 거절) · `on_update_start` :157~168 | 연결(start_runner :461) | `test_w72_cpu` 3 개 끝점(더티 거절) · `test_ex41_fixed_cpu:135 · 144` 끝점(잘못된 설정이 유지 · 멈춤을 못 가림) | **있음 · 연결** |
| W86 보상 런타임 · 격리 | `rewards/w86_runtime.py` · `start_runner.py:495~535 quarantine` · `ex41_valid_storage` | 연결(attach_runtime · `_ex41_w86` 필수) | `test_ex41_ppo_valid` 10 개(설치 PPO 와 비트 동일 끝점) · `test_ex41_ppo_bridge` | **있음 · 연결** · analyst ced6c43a 의 `_sanitize` 사본 반환 수정(std 별칭 보호) 이 runner 에 머지됐는지 **미대조** |
| D93 · D101 critic 거울 | `runners/ex41_critic_mirror.py`(mirror_critic 666 · CriticMirrorPPO) · `start_runner._construct_algorithm` :290~310 자세 명령이면 항상 CriticMirrorPPO(거울 off 기본) · `set_ex41_critic_mirror` :351~368 · `apply_runtime_fields` ex41.py:757~763 | 연결(클래스는 루프 안; **거울 손실 on 은 길 없음**, §2 Q4) | `test_ex41_b345:214` 끝점(인볼루션 · 고정 인덱스 쌍) **단 관절 블록은 `EX41_COORDINATE_METADATA` 없으면 skip** · `:253` 복제(combined = 평균) · `:273` 끝점(actor 기울기 불변) | **있음 · 연결 · 꺼짐** |
| W77 그림자 루프 EX-41 | `s2_lab/tools/shadow_loop.sh` 는 `ex40_score_watch` 만(ex41 0 건) | 없음 | 없음 | **없음** |
| W78 v2 지형 기술 평가 · W83 | 계약 문서만 | 없음 | 없음 | **없음** |
| W57 축 평가(회전 목표 0/30/60/90°) | `eval/axis_v2_cells.py:15 GOAL_DELTA_DEG=(0,30,60,90)` · `case_specs` 전진 + 좌우 회전 목표 | EX-41 시작 경로에 없음(EX-40 은 `axis250_loop.sh` 가 저장소 밖에서 돌림) | `test_axis_v2_run_cpu` 6 개(끝점) | **코드 있음 · EX-41 미연결** |
| W75 영상 코드 정리 `foothold_s2/video/{shoot,record,compose}.py` | runner · scripter-w75-w76 모두 **없음** | 없음 | 없음 | **없음** |
| W76 B · C층 영상 자동화 | scripter-w75-w76 `eval/c_layer_queue.py`(322 행, 더티) · `eval/video25/record_c_layer.py`(1,870 행, 미추적) | 없음(정본 · recorder 미결) | `test_c_layer_queue.py` 더티 | **미커밋** |
| W80 A층 4 방향 영상 규칙 | scripter-w75-w76 fc1ef1d5 stairs_inv_L1 포착 규칙(커밋 제목 읽기 · 본문 미검토) | 없음 | 미확인 | **미확인** |
| D102 재생목록 폴더 · 이름 | runner `scripts/make_ex41_playlists.py`(70 행) `EX-41-m{update:05d}-{all|fail}.m3u8` · 출력 폴더 인자 | 부르는 곳 없음 | 없음 | **있음 · 미연결** · 이름은 D102 와 0 채움만 다름 |
| M79 · M80(가짜 자료 · 가짜 폴더 통과) · M81(촬영 실패에도 done) · M82(WORKLIST 사본 stale) | §4 위험 셋이 같은 꼴 | | | 재발 위험 |
| (결정 못 찾음) `lin_vel_z` 가중 0 | `_sync_rewards` ex41.py:376~377 이 경계마다 lin_vel_z 를 0 으로 · `basic_lin_vel_z_schedule=False`. EX-40 env.yaml:1901~1904 는 −2.0 | 연결 | 미확인 | **근거 결정 미확인** → lead 확인(EX-40 끝값이 0 이면 정상) |

## 2. 팀장 특별 질문 여섯

**Q1 계단 0/30/60/90° 가 EX-41 평가 · 학습에 들어가는가.** 「계단 0/30/60/90°」 를 두 가지로 읽을 수 있어 둘 다 답한다(가정). (ㄱ) W57 의 회전 목표각 0/30/60/90°(`axis_v2_cells.py:15`): 코드는 있고 EX-40 에서는 저장소 밖 `axis250_loop.sh` 가 250 회마다 돌렸다. EX-41 시작 경로(train_start · ex41_startup) 와 fixed5000 yaml 어디에도 이 루프를 띄우는 줄이 없다 → **평가 미연결**. (ㄴ) 계단 지형 접근 방향 0/30/60/90°(W80 A층 4 방향 · W78 v2): 학습 쪽은 지형 정책이 `fixed_l02` · `performance`(레벨 상한 5) 둘뿐이고 방향 커리큘럼은 없다(yaml · `prepare_terrain_cfg`). 평가 쪽 W78 v2 는 코드가 없고 계약 문서만 있다 → **학습 · 평가 모두 없음**. 어느 뜻이든 「들어가지 않는다」.

**Q2 250 경계 W72 설정 재읽기가 시작 경로에 연결됐는가.** 연결됐다. `start_runner.py:461` 이 매 회차 `continuous.on_update_start(it)` 를 부르고, `EX41FixedRuntime.on_update_start` :148~153 이 (n−1)%250==0 에서 `w72.read_committed_pair` 로 커밋된 boundary · approvals 를 다시 읽어 `validate_change` 뒤 `_apply` → `apply_runtime_fields`(지형 · PPO · 거울 · 에피소드 길이) · `_sync_rewards` · `_sync_map` 으로 반영한다. 더티 · 미추적 파일이 있으면 그 경계는 거절되고 지난 유효 스냅샷을 쓴다(:161~165). **단 같은 경계에서 점수 파일을 읽는 `_read_scores` 가 소비할 파일을 만드는 생산자가 없다.** 그 결과(코드 읽기, 시험 `:154` 의 전제와 같음): n751 부터 `failed is None` → `dr_hold_missing_evidence` 로 DR 유지 → 1,000 회 뒤 소진 → 0.5 동결 → 5,000 회 끝까지 DR 0.5. 처방 · 몫 · 지형 경계는 회차대로 진행된다. 즉 **생산자 없이 기동하면 EX-41 은 「DR 램프 없는 5,000 회」 가 된다**. 이것이 D130 이 「확인 뒤 기동」 이라 적은 그 조건이다.

**Q3 그림자 · W57 · W78 v2 yaw 기록이 지도 셋을 코드로 강제하는가(D132).** 셋 가운데 **하나도 강제하지 않는다**. 강제 코드는 EX-41 점수 판독기 `maintenance_counts_from_map_modes` :144~145 한 곳이고, 그 판독기는 시작 경로에 연결되지 않았다(Q2). `eval_map_modes.py:30` 기본값은 세 모드지만 `--modes eval_gt` 한 모드만 줘도 돈다(:223 부분집합 허용). `axis_v2_run.py:158` 도 같다. EX-40 그림자 감시 `ex40_score_watch.py:311` 은 stand 세 모드와 map64 단계 존재만 본다. W78 v2 는 코드가 없다. M83 재발을 막는 장치는 **판독기 한 곳 + 생산자 없음** 이라 지금은 사실상 없다.

**Q4 critic 거울 증강이 답 아는 시험으로 검증되고 학습 루프에서 실제 불리는가.** 시험: `test_ex41_b345:214` 는 인볼루션(두 번 거울 = 원본)과 인덱스 쌍(0 음 · 1 양 · 7 · 8 음 · 48↔49 · 50↔51 · 52↔67 · 564↔593 · 664 유지 · 665 음)을 **답을 미리 적어** 건다(끝점). 그러나 **관절 블록(9 · 21 · 33 시작 12 열 셋) 의 좌우 바꿈 · hip 부호는 `EX41_COORDINATE_METADATA` 환경 변수에 실제 EX-40 관절 이름 파일이 있을 때만 검사하고 없으면 `pytest.skip`** 한다. CPU 23 PASS 류 보고가 이 skip 을 포함했는지는 미확인(상황판 숫자만). `:253` 은 `value_combined == (orig + mirror)/2` 를 거는 복제 시험. `:273` 은 거울이 actor 기울기를 바꾸지 않음을 거는 끝점. 루프: 자세 명령이면 `_construct_algorithm` 이 항상 CriticMirrorPPO 를 쓰므로 **클래스는 루프 안에 있고 유효 마스크 경로는 실제 돈다**. 거울 손실은 `effective['critic_mirror']` 가 True 일 때만 켜지는데, (가) boundary yaml 기본 false, (나) approvals yaml 에 critic_mirror 필드 승인이 없어 수동 변경은 `validate_change` 에서 거절, (다) 자동 켜기(`EX41Runtime._automatic` ex41.py:573~577) 는 FixedRuntime 이 부르지 않는다. 따라서 **현재 설정의 fixed5000 에서 거울 증강이 켜질 경로는 없다**. 팀장 확정 「자동 조정 셋」 과는 맞다. 켜고 싶으면 approvals 에 필드 승인 + boundary 커밋이 필요하고, 그 전에 관절 블록 시험을 skip 없이 돌려야 한다.

**Q5 영상 규칙(W76 · W80 · D102) 연결.** 연결된 것이 없다. W75 `foothold_s2/video/` 는 어느 worktree 에도 없다. W76 C층 대기열은 scripter-w75-w76 의 **미커밋 수정 + 미추적 recorder 1,870 행** 이고 정본 저장본(D131) · recorder 시드 제약(record_25e_x31 :462 · :496 시드 42 고정) 이 미결이다. W80 은 fc1ef1d5 커밋 제목만 확인했다. D102 재생목록 스크립트는 runner 에 있지만 부르는 곳이 없고 폴더는 인자다. EX-41 시작 경로에는 영상 · 재생목록 · B층 7 규칙 어느 것도 없다. EX-40 처럼 저장소 밖 셸 루프로 돌릴 계획이면 그 루프가 아직 없다.

**Q6 정답 복제 시험이라 통과하는 위험 셋.** §4.

## 3. 설계 v0.7 과 코드의 어긋남 (어느 쪽을 고칠지 lead 가 정할 것)

| # | 자리 | 설계 v0.7 | 코드 | 비고 |
|---|---|---|---|---|
| ① | +500 연장 대상 | §5.12 :323~325 S2d(n2751~4000) 를 n4500 까지 | `ex41_fixed.py:194~201` time ≥ 4500 에서 결정 · **S2e(DR 1.0 유지, pos 4) 를 500 연장**; 시험 `:169` 가 S2e 연장을 끝점으로 검 | 팀장 확정문은 「성과는 +500 연장 한 번」 만. D110 원문은 S2c(옛 이름, 지금 S2d) 상한. 어느 단계를 늘리는지 결정 필요 |
| ② | Δ 문턱 | §5.12 +0.2(planner 재도출 가정 Q26) | yaml `extension_level_delta 0.5` | 설계는 가정 표시 · 코드는 옛 값. 하나로 |
| ③ | 명령 몫 2 차 자리 | §4 S2c n1751(가정 Q26) | yaml shares S2b n751 부터 23·6·6·9·9·10·14·7·7·2·2·2.5·2.5 (S2a 23·7.5·7.5·9·9·10·14·6·6·1.5·1.5·2.5·2.5) | 「한 경계에 한 묶음」 이면 S2b 경계는 램프 시작 + 몫 2 차 둘 |
| ④ | 서 있기 복원 | §5.11 :296 「D110 +2」 | 스윙 반감 한 번(D130 · :187~192) | **설계가 틀림** → planner v0.7.1 |
| ⑤ | DR 유지 조건 | §5.9 「유지 칸 < 기준 − 3/64」 | 같음 + **증거 없음도 유지** | 결정 확장. 생산자가 붙으면 정상 분기, 안 붙으면 Q2 |
| ⑥ | 지표 셋(D128) | §5.8 세 지표 | 없음 | W78 v2 · W57 구현 몫 |

## 4. 정답 복제 · 가짜 입력이라 통과하는 위험 셋

1. **점수 파일 생산자 부재를 시험이 가린다.** `test_ex41_fixed_cpu` 의 `tick()` 과 `test_ex41_runtime_cpu.score()` 헬퍼가 `foothold-ex41-score/1` 형식 · stage_id · schedule_sha256 · evidence SHA · maintenance_counts 39 칸을 **코드가 요구하는 모양대로 지어** 넣는다. 그래서 유지 · 재개 · 연장이 모두 PASS 지만 실제 기동에서는 그 파일이 하나도 생기지 않는다(M79 「가짜 자료 통과 뒤 실제 HOLD」 와 같은 꼴). 판독기 모양이 실제 map_modes.json 과 맞는 것은 이 검토가 실측 파일 하나로 확인했지만, **실제 평가 산출물 → ex41_score.py → score_dir** 로 가는 사슬을 끝까지 돌린 시험 · 기록이 없다.
2. **거울 관절 블록 검사가 기본값에서 skip.** `test_mirror_known_components_and_involution` 의 관절 36 열 검증은 환경 변수가 없으면 skip 되고 나머지 단언만으로 PASS 가 찍힌다. 런타임 `_assert_ex41_joint_order` 가 Kit 에서 다시 막긴 하지만 그것은 기동 뒤다. CPU 보고의 PASS 수에 skip 이 섞였는지 확인 전에는 「거울 검증됨」 으로 적지 말 것.
3. **기동 관문을 fixture 가 우회.** fixed 시험은 boundary 를 `w71_ready: True` 로 바꾸고 approvals 에 `w71_ready` 승인을 끼워 넣어(`:25~27`) 돈다. 실제 yaml 은 false 라 train_start 가 시작을 거절한다(올바른 동작). 위험은 「CPU 전부 PASS = 기동 가능」 으로 읽히는 것. 같은 결의 낡은 관문: `scripts/ex41_start_preflight.py` 는 아직 **부모 7500** 을 요구하고(`REQUIRED_PARENT_UPDATE = 7500`, max_iterations > 7500) `launch_allowed` 를 항상 False 로 내는데, `test_ex41_start_preflight_cpu` 136 행이 그 낡은 값을 지키고 있다. analyst ced6c43a 는 이 파일을 지웠지만 runner 에는 남아 있다. 기동 스크립트가 어느 preflight 를 부르는지에 따라 기동이 7500 사유로 막히거나, 반대로 아무 preflight 도 안 거친다.

## 5. 기동 전 막음 (순서대로)

1. **점수 생산자 + 그림자 루프 EX-41 판**: 저장본 N 마다 평가(eval_map_modes 세 모드 64 env) → `ex41_score.py --score-draft --map-modes --out score_dir` 를 돌려 `foothold-ex41-score/1` 을 만드는 장치가 시작 경로에 붙어야 한다. 붙인 뒤 **답 아는 끝점**: m6000 실측 map_modes.json 을 넣어 39 칸 passed 가 score_6000 json 과 같은지, 한 모드를 지운 입력이 거절되는지.
2. **W71 소비자 검증 뒤 `w71_ready: true` 커밋**(Kit 실측 필요 · 이 검토 범위 밖).
3. §3 ①②③ 결정 → yaml · 설계 한쪽으로. ④ 는 planner 가 v0.7.1 에서 고침.
4. `ex41_start_preflight.py` 7500 잔재 정리 또는 미사용 확인(기동 스크립트가 무엇을 부르는지).
5. 거울 관절 블록 시험을 `EX41_COORDINATE_METADATA` 로 skip 없이 1 회(기록 남김).
6. D132: 평가기 CLI(`eval_map_modes` · `axis_v2_run`) 에 세 모드 강제가 필요하면 결정으로 올릴 것(지금은 판독기만).
7. 영상 · 재생목록 · W78 v2 는 EX-41 기동과 독립이지만 「기록」 결정(D128 · D132 · W76 · W80 · D102) 이 하나도 연결되지 않았으므로, 기동 전에 어느 것을 첫 250 경계까지 붙일지 lead 가 정할 것.

## 5a. 추가(14:5x lead 의뢰): D125 「DR 켠 평가 칸 배율 1.0」 평가기 확인 (읽기 전용)

- `eval/eval_map_modes.py`(runner ea51caab): DR 배율 인자가 **없다**. :91~100 이 `actuator_gains · motor_strength · physics_material · add_base_mass · base_com · push_robot · base_external_force_torque` 이벤트를 모두 None 으로 지우고 `joint_pos.max_delay_s = 0` 으로 두며, :102~104 가 꺼진 목록이 `["physics_material", "add_base_mass"]` 와 다르면 RuntimeError 로 멈춘다(「DR 켜진 채 끔 평가」 방지 관문). EX-40 의 런타임 DR(`ex40_dr.py` 게인 · 세기 · 질량 · 무게중심 · 밀기 · 지연) 은 평가기에 붙지 않는다(`foothold_s2/eval/*.py` · `ex40_score*.py` 에 ex40_dr · dr_scale 0 건). 즉 **평가는 항상 DR 끔** 이고 「DR 켠 칸」 을 만들 길이 없다.
- `eval/axis_v2_run.py` · `axis_v2_cells.py`: DR 관련 코드 0 건(eval_map_modes 안에서 같은 env 로 돌므로 같이 끔).
- `run_eval_map_modes.sh`: 인자 없음(장치 · 저장본 · 폴더만).
- 결론: D94 「DR 켠 평가 칸 하나」 · D125 「배율 1.0」 은 **코드 없음 · 시작 경로 없음 · 시험 없음**. 설계 v0.7 §5.9 관문 행의 「D94 DR 켠 칸만 그 단계 끝 배율로 켜고 배율을 점수표에 적는다(가정)」 도 구현이 없다. 만들려면 평가기에 (ㄱ) DR 이벤트를 남기는 모드 (ㄴ) ex40_dr 런타임을 배율 1.0 으로 붙이는 길 (ㄷ) 점수표에 배율 기록, 셋이 필요하고 EXPECTED_DR_OFF 관문도 그 모드에서는 달라야 한다. 구현 몫 · 우선순위는 lead 결정.
- 같은 확인에서 발견: 설계 Q26 ② 「DR 유지 때 몫 · 지형 경계는 회차 고정 그대로, DR 일정만 민다」 는 코드와 다르다. `ex41_fixed.Clock` 은 유지 중 elapsed 를 멈추고 단계 위치도 elapsed 로 세므로 **단계 경계까지 같이 밀린다**(`test_ex41_fixed_cpu.py:81` 「Stage end delayed by same 500 updates」). §3 표에 빠졌던 다섯째 어긋남이다. lead 결정(설계를 코드에 맞출지).

## 6. 안 한 것 · 미확인

- 코드 · 설정 · 시험 수정 없음 · GPU · Kit 실행 없음 · 시험 실행 없음(모두 읽기).
- analyst ced6c43a 와 runner ea51caab 의 같은 이름 파일 내용 대조는 `ex41_critic_mirror.py` 만(동일). `w86_runtime.py` `_sanitize` 수정 · `ex41.py` 19 행 차이가 runner 에 들어갔는지 미대조.
- scripter-ex41-b345 aba6c6e8 · scripter-ex41-ppo 8cab09f2 는 runner 가 머지한 범위(36f6cddf) 와 68cffa0f 제목만 확인 · 68cffa0f 본문 미검토.
- D125 평가기 DR 배율 인자 · W80 규칙 본문 · W57 정지 구간 각속도 기록 여부 · `lin_vel_z` 0 의 근거 결정 · CPU PASS 보고에 skip 포함 여부 · EX41DRReadback 의 base(ex40_dr) 가 매 회차 `update_start` 를 실제로 거치는지(start_runner :464 호출은 확인, base 내부 미확인).
- 다른 세션 보고(analyst CPU23 PASS · verifier CPU12 · runner 34 PASS) 는 상황판 읽기이며 재측하지 않았다.
- 이 파일은 `_out/reports/`(미추적) 에만 있고 커밋하지 않았다(의뢰에 커밋 없음).
- 보고 송신 직후 상황판(14:37) 에 analyst 가 ced6c43a 뒤 **a0581766** 을 push 했다고 적혀 있다(「상한회복 · 점수 helper · 시계 보강 · CPU57」). 이 검토는 ced6c43a 와 runner ea51caab 기준이며 a0581766 은 **미대조**. §1 · §3 의 ex41_fixed.py 줄 번호는 그 커밋에서 바뀌었을 수 있다.
