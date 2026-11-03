# EX-42 정본 v0.15 가 바꾼 칸 → runner 구현(feature/ex42-prep-runner e9e8502e) 에 넘길 diff 목록

> 분류: A/정책학습 · 설계 → 구현 인계 목록
> 작성: planner · 2026-11-04 01:xx · 정본 `inbox/jay/20261026-experiments/CURRICULUM-GATES.md` EX-42 절 v0.15(같은 커밋) · 검사기 `ex42_canon_check.py` 어긋남 0
> 근거: lead 00:4x · 01:0x 지시 · WORKLIST D176(lead 가지 1ffc9cd1 203 행) · analyst `D:/mai-tmp/analyst/ADVICE-EX42-1103.md` · runner e9e8502e `foothold_s2/curriculum/ex42-prep.yaml` · `ex42_prep.py` · `ex42_preflight.py` · `tests/test_ex42_prep_cpu.py`(읽기 · 돌리지 않음)
> 요지: D176 ①~⑨ 로 닫힌 미결 칸 아홉과 analyst 공여 규칙 · 평가 확대, 그리고 팀장 원칙(논문이 넘은 과제가 기준) 에 따른 확장 묶음 E · 평가 열 · preset 변경을 runner 표 · 파서 · preflight 의 어느 키에 반영해야 하는지 23 항목으로. 코드는 안 고쳤고 값은 정본 절이 정본이다
> 상태: 목록만 · runner 가 e9e8502e 위에 반영 · 구현 · 시험 · Kit 은 전부 미검증

## 읽는 법

「runner 자리」 는 e9e8502e 의 파일 · 키(읽기). 「바꿀 것」 은 정본 v0.15 의 값. 「등급」 은 정본 절의 등급을 그대로. 파서 거절 규칙(「거절」) 은 시작을 막는 검사이지 학습 중 자동 조정이 아니다. 이 목록 밖의 runner 파일은 손대지 않는다.

## 1. 미결 칸 닫힘 (ex42-prep.yaml `assumptions_pending_lead` · D176)

| # | runner 자리 | 바꿀 것 | 정본 자리 · 등급 |
|---|---|---|---|
| 1 | `assumptions_pending_lead.minimum_valid_envs` {48, assumption, approved false} | `approved: true` · class `decision` · decision_id D176-1 | §E.3.1 머리 · E.4 `maintenance.min_valid_envs` · 결정 D176 ① |
| 2 | `error_rise_vx_vy_mps` 0.03 · `error_rise_wz_radps` 0.05 approved false | 둘 다 `approved: true`(시작값) + 새 키 `maintenance.threshold_rule: max_assumption_2x_repeat`(첫 calibration 뒤 문턱 = max(가정값, 반복 폭 × 2) 로 결과 전 고정 · 옛 「반복 폭 1 배」 · 「2 배 넘으면 올리지 않음」 은 버림) · 생존 −3/64 도 같은 식 | §E.3 유지 칸 행 · §E.3.1 머리 · E.4 · 결정 D176 ② |
| 3 | `record_to_judge_promotions` {[], undecided} | `[projection_distance, foot_drag]` · 새 키 `maintenance.judge_from_stage: {projection_distance: E2, foot_drag: E2}` · E0 · E1 은 record + 텔레그램 경보 · E2 경계부터 judge(HOLD + 되돌림) · 발 끌림은 §E.3.1 새 행(발마다 접촉 중 수평 이동 거리 합 · 64 env 중앙값 · comparator ≤ 기준 + max(가정 미정, 반복 폭 × 2)) → `maintenance.items[]` 에 항 추가(11 항) · 점수 생산자에 발별 `foot_drag_m` 필드 필요 | §E.3.1 투영 · 발 끌림 행 · 결정 D176 ③ · 발 끌림 가정값 **미정** |
| 4 | `conditional_command_share_denominator` {null, assumption} | 조건부(연속 env 안 비율 · 정본 안) 로 고정 + 전체(3,072) 하한 `stages[].terrain.floors.global_command_floor: {reverse: 0.05, side_left: 0.03, side_right: 0.03}` · 파서: 연속 몫 × 조건부 몫 < 전체 하한이면 그 K 경계 거절 · `boundary_log` 에 분모 둘(조건부 · 전체 소비) 기록 · 실효 `continuous_share_min` 0.20 → **0.43**(max(5/14, 3/7) · 계산) · E3 듬성 합 ≤ 50 % 그대로 · E4 듬성 합 ≤ 57.1 % | §E.3 명령 몫 · 지형 망각 행 · E3 · E4 env 몫 행 · E.4 floors · 결정 D176 ④ · 계산 |
| 5 | (공여 규칙 · runner 표에 없음) | 새 블록 `maintenance.donation: {window_boundaries: 4, survival_min: 60, main_axis_error_max: 0.15, delta_s_max: 3, delta_e_max_vxvy: 0.03, delta_e_max_wz: 0.05, max_fraction: 0.25, e0_floor_frac: 0.50, wait_boundaries: 2, pair_equal: true}` · 공여원 = 전진 · 제자리 회전 · 대각 묶음 가운데 「잘함 + 안정」 자격 칸(§E.3 몫 공여 행의 식 전부) · 가장 약한 칸 금지 · 정지 · 후진 · 옆 금지 · 파서: `boundary.donor` 벡터가 묶음당 현재 몫 25 % 초과 · 누적 잔여 < E0 몫 50 % · 좌우 짝 다른 양 · 유효 env < 48 이면 거절 · 공여 뒤 2 경계 안 다른 축 확대 거절 · 회귀면 공여 전 벡터로 되돌림(감독기) | §E.3 몫 공여 행 · E.4 donation · 결정 D176 ④ · analyst 가정 승인(4 · 750 · 0.15 · 25 % · 50 % · 2) |
| 6 | `sparse_reverse_completion` · `side_completion` {null, undecided} | 둘 다 `cross_dir_half_flat`: 생존 ≥ 60/64 + 명령 방향 투영 이동 ≥ 같은 명령 평지 값의 50 % · 첫 창은 기록만 · 둘째 창부터 판정(가정) · `promotion.completion` enum 에 이름 추가 | §E.3 완료 정의 행 · E5 승급 행 · E.4 · 결정 D176 ⑤ |
| 7 | `stairs_dimensions_w48` {null, undecided} | 단 0.16 m · 계단참 깊이 1.2 m · 회전 6 s · ±1.2 rad/s · 성공 = 생존 + 판 위 + 돈 각도 ≥ 명령의 80 % · 정지 재출발 = 중간 단 2 s 정지 뒤 전진 1.0 꼭대기 도달 → 평가 전용 열 `eval_stairs_landing_016`(학습 `stage_stairs` `STAGE_STEP_HEIGHT 0.15` 는 **안 바꿈**) | E1 유지 칸 · 승급 행 · E.4 `eval.paper_cells.landing` · 결정 D176 ⑥ · 80 % · 2 s 가정 |
| 8 | (부모 누적 하락 · `maintenance.parent_alarm.survival_drop` 6 만 있음) | `maintenance.parent_alarm.consecutive_hold: 2` · 두 경계 연속 경보면 노출 확대 HOLD + 팀장 보고(학습 프로세스는 D156 대로 안 끊음 · 가정) | §E.3 유지 칸 행 · §E.3.1 부모 행 · E.4 · 결정 D176 ⑦ |
| 9 | `evaluation_scale_multiplier` {null, calibration} · `environment.evaluation.scale_multiplier` null · `status unresolved_calibration` | 틈 × 1.15 · 지지면 × 0.85 를 **따로**(종류별 적용 자리는 §E.3 평가 전용 열 행) · preset 넷 `eval.start_variants: [start_go2_v2, start_go2_eval_gap115, start_go2_eval_sup085, start_go2_eval_both]` · 명목 L9 값 gap 0.8919 · 징검돌 틈 0.3186 · 지지 폭 0.1505 · 평균대 0.1316 · 빔 두께 0.1413 · 틈 0.3504 · status `fixed_before_results`(결과 뒤 변경 금지 · 바꾸면 새 판 ID) · manifest 에 `source_preset → go2_train → eval_variant` · `terrain_manifest_contract.evaluation_must_be_larger` 는 「축마다 어려운 쪽」 으로(지지면은 작아지므로 「크다」 검사가 틀림 · 비교 방향을 축별로) | §E.3 평가 전용 열(D158 · D176 ⑧) 행 · E.4 · 결정 D176 ⑧ · 계산 |
| 10 | `q4_two_window_range` {null, calibration} | 변경 없음(D159 · E0 calibration 뒤 #2 식으로 고정) | 그대로 |
| 11 | (종류별 분기 · 표에 없음) | 한 종류가 막혀도 다른 종류의 K · D 경계를 열 수 있음(경계마다 축 하나는 그대로) · 단계 파서가 「종류 일렬」 을 강제하면 풀기 | E.1 E4 행 · 결정 D176 ⑨ |

## 2. 팀장 원칙(논문이 넘은 과제가 기준 · 목표는 그 이상) 으로 바뀐 치수 · 열 (§E.8)

| # | runner 자리 | 바꿀 것 | 정본 자리 · 등급 |
|---|---|---|---|
| 12 | `environment.training_presets.A: start_go2_v1` · `terrain_manifest_contract` preset ID | `start_go2_v2` = v1 에서 balance_beams L9 폭 0.155 → **0.09** 만 다름(L5 0.286) · 생성기는 `start_sheet.py` 선형식 그대로 범위만 | §E.2 머리 · E3 치수 행 · §E.8 평균대 행 · D176 ⑥ ⑦ 원칙 · 계산 |
| 13 | `training_presets` 에 E 없음 · `kind_count_by_family {A 13, B 12, C 7, D 3, continuous 7}` | 새 묶음 **E** `paper_ext_v1` 4 종: `slope_steep` · `slope_steep_inv`(hf pyramid slope 기울기 0.40 → 0.70 · 비(높이/거리) 단위 · 21.8° → 35.0°) · `stairs_high` · `stairs_high_inv`(단 0.23 → 0.30 · run 0.30) · 연속 생성기 꼴(`rough_go2_cfg.py:20~33` 의 Cfg 종류) 그대로 범위만 · `kind_count_by_family.E: 4`(39 종) · `rough_go2_cfg` 는 **안 바꿈**(E0 부모 diff 0) · E0 사전 등록 share 0 · level_cap 0 · 과제 묶음 `[forward_1.0, flag]` · 완료 `tile_end_reach` · E3 연속 L9 통과 직후 K 로 열 수 있음 · E4 exit 경사 L6 · 계단 L3 | §E.8 머리 · E.1 E4 · E4 행 셋 · E.4 preset · D176 ⑥ ⑦ 원칙 · 계산 |
| 14 | `ame2_go2_mix_v1` climb_up 0.32(D159) | climb_up L9 0.32 → **0.53**(JEPLO Go2 실기 상자 증거까지) · preset ID 는 B-2 표의 Go2 후보 열 값 갱신(원본 · Go2 후보 · 실측 세 칸 구조 그대로) | E4 치수 행 · §E.8 턱 오르기 행 · 결정 D159 → D176 ⑦ 원칙 |
| 15 | `evaluation` 블록(26 + 13 · kind_cells · fixed_levels) | 평가 전용 열(노출 0 · 레벨 하나) 추가 `eval.paper_cells`: 경사 `eval_slope_30` · `_35`(판정 목표 · E4 부터) · `_45`(기록) · 계단 `eval_stairs_015 · 020 · 025`(전진 판정 목표 0.25 · 옆 · 대각 기록) · `eval_stairs_010`(후진 판정 목표 · 0.15 · 0.20 후진 기록) · `eval_stairs_landing_016`(#7) · `eval_stair_surface_spin`(JEPLO rise 0.15/run 0.25 · 기록 · 가정) · `judge_from_stage: E4` · 39 칸 판정 · 기록 수는 그대로(이 열은 별도 묶음) | §E.3 평가 칸 · 평가 전용 열(논문 과제) 행 · E.4 · §E.8 · D176 ⑥ ⑦ |
| 16 | `TerrainGeneratorCfg slope_threshold=0.75`(`rough_go2_cfg.py:43`) | `eval_slope_45`(기울기 1.0) 는 임계 0.75 를 넘어 수직면으로 변환됨 → 그 열만 평면 메시(`MeshPlaneTerrainCfg` 기울기) 또는 임계 ≥ 1.0 으로 생성 · 학습 열은 임계 그대로 | §E.3 평가 전용 열(논문 과제) 행 · §E.8 경사 행 · 코드 읽기 |
| 17 | 평가기 마찰(점수 평가기 `eval_map_modes.py` 값 **미확인** · 녹화 0.8 · 0.6) | 경사 칸 기록에 평가 마찰(정지 · 동적) 을 같이 적는 필드 `eval.friction_record: true` · 45° 는 정지 마찰 ≥ 1.0 이 필요해 0.8 로는 기록 0 이 정상 · 학습 DR [0.2, 1.2] 라 학습 중 경사 성공은 마찰 표본 조건부 | §E.8 경사 행 · 코드 · 미확인 |
| 18 | `terrain_manifest_contract.each_kind_fields` | 칸 둘 추가: `paper_reference`(논문 · 로봇 · 최대 치수 · 성공률 · §E.8 행) · `physical_flag`(정적 기하 밖 여부 · 근거 한 줄) | §E.8 · D176 ⑥ ⑦ |
| 19 | E6b high_ledge 0.3 → 0.45 → 0.6 · crawl 0.25 · AME climb_down 0.6 · consecutive 0.3 · START gaps 0.7756 | **안 바꿈**(물리 표시 칸 · 팀장 판단 전) · 평가 기록 열만: high_ledge 0.75 · gap 0.90 · 1.00 · climb_down 0.75 · 0.88 · consecutive 0.40 · crawl 0.20 · 평균대 0.09 · 0.0765 · 계단 0.27 · 0.30 → `eval.paper_cells` 기록 묶음에 | §E.8 물리 표시 행 · §E.9 · 팀장 판단 |

## 3. 표 머리 · 문서 참조

| # | runner 자리 | 바꿀 것 |
|---|---|---|
| 20 | `design.canonical_commit: a7407329` · `canonical_version: v0.14` | 이 커밋 해시 · `v0.15` · `design_draft_version` 은 그대로(초안은 안 고침) |
| 21 | `launch.require_resolved_assumptions: true` | 그대로 · #1~#9 가 approved 로 바뀌어도 발 끌림 가정값 · 평가기 마찰 · 물리 표시 칸 · analyst 승인 D 번호가 남아 있으므로 `assumptions_pending_lead` 에 그 넷을 새 항목으로 적고 시작은 계속 막힘 |
| 22 | `ex42_preflight.py` blockers | `design_assumptions_pending` 사유 목록을 #21 의 넷으로 갱신 · `terrain_manifest_missing` 에 묶음 E · 평가 열 · preset 넷 포함 |
| 23 | `tests/test_ex42_prep_cpu.py` | 새 거절 규칙 시험 넷(전체 하한 · 공여 상한 · 2 경계 대기 · 종류 분기 허용) · 발 끌림 항 11 · paper_cells 파싱 · 답 아는 입력: 연속 0.40 × 후진 0.14 = 0.056 ≥ 0.05 통과 · 0.35 × 0.14 = 0.049 거절 |

## 안 한 것 · 손대지 않은 것

- runner 파일은 읽기만 했고 고치지 않았다. 시험 · preflight · Kit 을 돌리지 않았다.
- `DESIGN-EX42-TERRAIN-draft.md` §13 표(Q 물음) 는 lead 지시 범위(정본 절) 밖이라 안 고쳤다(§13 표 닫힘 표시는 남은 일).
- 점수 평가기(`eval_map_modes.py`) 의 마찰 값 · 고정 레벨 칸의 종류 배정은 확인하지 않았다(미확인).
- analyst 조언 승인의 D 번호는 WORKLIST 에 없어 「가정」 으로 적었다. lead 가 번호를 붙이면 정본 · 이 목록의 「D176 ④ · ⑧ 범위」 표기를 그 번호로 바꾼다.
