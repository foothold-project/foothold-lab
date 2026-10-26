# REPORT-planner 2026-10-26 21:15 · X26u J-T10 · M-T6 구현 대조

> 분류: 대조 보고 (planner, 설계 반박 검토)
> 작성: planner (Claude Fable 5.1) · 2026-10-26 21:15
> 근거: 사양 JUDGE-SPEC v0.7(b44676c9) 7 절 J-T5 · J-T10, DESIGN-MAPRATIO v0.9 3.2 · 7 절 M-T6 · 구현 impl-integ(feature/judge-mapratio-integ-jay) HEAD 58a4af15 + sonnet-code 의 **미커밋 작업 사본**(21:1x 읽음: terrain_levels_mixed.py · test_world_frame.py · test_terrain_mark.py) · Isaac Lab `/c/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_generator.py:235~247`
> 요지: **막음 0 · 고침 2 · 참고 4.** J-T10(세계 좌표 proxy) 와 M-T6(끔 대상 지형) 의 계산 · 뽑기 · 기록은 사양과 맞다. 고침은 (1) `world_frame` 을 설정에서 주는 길과 manifest 기록이 없음, (2) 표식 덮기를 기록용으로 바꾸는 v0.7 전환이 아직 코드에 없음(사양이 21:0x 에 바뀌어 당연, 반영 대기).
> 상태: 읽기만. 시험은 돌리지 않음(sonnet-code 가 통합 회귀 도는 중이라 같은 파일에 손대지 않음) · GPU · 학습 · 코드 수정 없음

## 1. J-T10 세계 좌표 기대 변위 proxy

| 사양(JUDGE-SPEC v0.7 J-T10) | 코드 | 판정 |
|---|---|---|
| `cmd_sum_w (N, 2)` 를 매 스텝 `R(yaw_t) · vel_command_b[:, :2]` 로 누적 | `mixed_command.py:62` 생성, `:221` `self.cmd_sum_w += mc.world_cmd_step(yaw, self.vel_command_b[:, :2])`, `mixed_core.py:193~197` 회전식 `[c·vx − s·vy, s·vx + c·vy]` | 맞음 |
| `_reset_episode_state` 에서 비움 | `mixed_command.py:123` `self.cmd_sum_w[env_ids] = 0.0` | 맞음 |
| 같은 단위 변환(`step_dt / resample_s`) · 같은 식 | `terrain_levels_mixed.py:37` `cmd_sum_w[env_ids] * env.step_dt / resample_s` 를 `rules.judge` 에 그대로 | 맞음 |
| 기본 `world_frame=True`(결정 8), `False` 면 옛 식 비트 동일 | 작업 사본 `terrain_levels_mixed.py:14` 기본 True(HEAD 58a4af15 는 False, 미커밋). `False` 면 `move` 를 바꾸지 않음(`:43~44`) | 맞음(미커밋) |
| 두 판정 모두 계산 · 9 칸 · 표식 유무별 · 갈린 수 | `rules.FrameCompareStats`(`rules.py:76~120`): 칸 `c{옛}w{세계}`, `mismatch` unmarked · marked, update 마다 `train_extra.jsonl` `world_frame_compare`(`start_runner.py:420~422`, `_take_frame_stats` `:531`) | 맞음 |
| `cmd_sum_w` 없는 term 에 켬 → 거절 | `terrain_levels_mixed.py:34~35` ValueError | 맞음 |
| 켜는 것은 설정 인자 + manifest 에 쓰인 값 기록 | **없음.** `world_frame` 은 함수 기본값뿐. S1 cfg `tasks/s1_env_cfg.py:170` `CurrTerm(func=tlm.terrain_levels_mixed)` 는 params 없음, S2 경로 `terrain_levels_s2`(`terrain_levels_mixed.py:140`) 는 `terrain_levels_mixed(env, env_ids, command_name, resample_s)` 로 불러 `world_frame` 을 넘길 수 없음. manifest 에 `world_frame` · 「출발 저장본은 옛 판정으로 학습됨」 키 없음(`start_runner.py` manifest 쓰기는 `map_ratio_events` 뿐). update 마다 `train_extra.jsonl` 의 `world_frame_compare.world_frame` 에 쓰인 값이 남는 것이 유일한 기록 | **고침 1** |
| 표식 덮기는 기록용(`mask_new_task` 인자 기본 False, 5.2 의 3 v0.7) | `terrain_levels_mixed.py:46~49` 는 표식 있으면 무조건 `rules.mask_new_task` 로 덮음. v0.7(21:0x) 전환 미반영 | **고침 2**(반영 대기) |

시험(`test_world_frame.py` 작업 사본) 대 사양 시험 줄:

| 사양 시험 | 시험 함수 | 판정 |
|---|---|---|
| analyst 반례 인자 없이 0 · `False` −1 | `test_decision_8_default_is_on_and_old_behavior_stays_behind_the_argument`(기본값 True 확인 포함) · `test_row_analyst_counterexample_…` | 있음 |
| 원운동 0 · 직진 10 m 둘 다 +1 | `test_row_circle_…` · `test_row_straight_…` | 있음 |
| `False` 비트 동등성 | `test_switch_off_is_bit_identical_…`(300 env 무작위, `cmd_sum_w` 없는 term 과 비교) | 있음(S1 1000 스텝 Kit 동등성은 아님, CPU 대용) |
| 갈린 수 > 0 이고 모두 한 방향 칸 | `test_perfect_following_simulation_…`(시드 0 · 2000 에피소드: 켬 강등 0, 끔 강등 > 0 이고 < 3 %, 켬 승급 > 90 %) | **부분**: 강등 수만 보고 「c-1w0 · c0w1 칸 외 0」 은 안 봄 → 참고 2 |
| 깃발 env 는 두 판정이 같은 규칙 | `test_both_judgements_are_recorded_…`: 깃발 env 는 표에서 **뺀다**(`select=~is_flag_env`) | 사양에 없던 선택, 타당 → 참고 1(사양에 적음) |

## 2. M-T6 끔 대상 지형

| 사양(DESIGN-MAPRATIO v0.9 M-T6) | 코드 | 판정 |
|---|---|---|
| 지형 이름으로만(연속 7 종 + flat 참, 듬성 거짓, 레벨 무시) | `map_switch.py:15~16` `ELIGIBLE_NAMES = CONTINUOUS ∪ {flat}`, `SPARSE_NAMES = SPARSE − {flat}`; `eligible_map_off(terrain_types, terrain_levels, names)` `:30~34` 는 levels 를 받고 안 씀 | 맞음 |
| n 개 전부 뽑은 뒤 `& eligible`(난수열 소비 동일) | `start_runner.py:291, 380` `_restrict_map_off(draw_map_off(n, …), reset)` → `:866~874` `off & eligible`; 시험 `test_the_draw_still_consumes_the_generator_…` · 23 열 생성기 상태 동일 시험 | 맞음 |
| 읽는 때 = env.step 뒤 새 에피소드 값 | `:380` 은 `env.step` 과 done 집계 뒤 `perception.reset_envs` 인자 자리(`dones > 0`); 시험 `test_the_cell_is_read_after_the_step_…` | 맞음 |
| 열 → 이름은 Isaac 고정 배치 식 | `columns.column_types(proportions, num_cols)` `:52~58` `names[min(where(i/num_cols + 0.001 < cumsum))]` = Isaac `_generate_curriculum_terrains` `terrain_generator.py:244~246` 과 같은 식(내가 열어 대조) | 맞음(사양의 `column_assignment` 라는 이름만 다름) |
| 이름 모르는 열 → 기동 거절 | `check_column_names` `:19~27` ValueError, `_off_column_names` 가 기동 때 부름(`:856~860`) · 시험 `test_unknown_column_name_is_refused` | 맞음 |
| 기록: 이름 · 레벨별 끔 시작 수 · 허용 env 수 · 듬성 진입 수 · manifest 허용 집합 | `OffEligibilityStats`(`:45~91`): starts · eligible_starts · sparse_starts · off_starts · off_starts_by_level · by_name[이름][by_level] · off_ended · `off_ended_on_sparse_prev_step`(마지막 step 이전 위치 근사, 주석 명시) → `map_switch.jsonl` `off_eligibility`; manifest `map_ratio_events` 에 `{"kind": "off_eligibility", "eligible", "sparse", "num_cols", "column_counts"}` | 맞음(진입 수는 「끝난 끔 에피소드 중 듬성 칸 위」 로 정의, 사양의 「이동해 들어간 수」 와 같은 뜻) |
| 23 열(S1-a) 비트 동일 · FULL 50 듬성 끔 0 · 허용 realized p ± 0.03 | 시험 23 열 대 지형 도구 없는 env(같은 map_off · 같은 생성기 상태) · 50 열 듬성 0 · 허용 비율 0.3 ± **0.04**(사양 0.03) | 맞음(허용 폭만 0.01 넓음 → 참고 3) |
| 전체 비율 자동 조정 없음 · 레벨 조건 없음 · 에피소드 중 바꾸지 않음 | 확률을 올리는 코드 없음 · levels 미사용 · `map_off` 는 reset 자리에서만 바뀜 | 맞음 |

## 3. 고침 · 참고

- **고침 1 (J-T10 설정 · manifest).** 「옛 동작은 인자로 남김」(팀장 결정 8 · lead 21:0x) 이 함수 서명에는 있으나 **실행에서 고를 길이 없다**: S1 cfg 는 params 없음, S2 경로는 인자를 넘기지 않음, CLI · yaml 어디에도 `world_frame` 이 없다. manifest 에도 쓰인 값과 「출발 저장본 S-B10 m1500 은 옛 판정으로 학습됨」 이 없다. 제안: `CurrTerm(func=…, params={"world_frame": <설정값>})`(S1) · `terrain_levels_s2(…, world_frame=True)` 가 그대로 넘기기(S2) · runner 가 manifest 에 `terrain_judge = {"world_frame": …, "mask_new_task": …, "start_checkpoint_judged_with": "body_frame"}`. 기본값은 켬 그대로.
- **고침 2 (표식 덮기 기록용, 반영 대기).** JUDGE-SPEC v0.7 5.2 의 3: 결정 8 뒤 표식 에피소드의 `move` 덮기는 기록용, 옛 덮기는 `mask_new_task=True` 인자(기본 False). 코드는 아직 무조건 덮는다. 켬 + 덮기는 틀린 판정은 아니고 보수적(표식 에피소드가 승급을 못 함) 이라 막음이 아니다. 사양이 21:0x 에 바뀐 것이라 sonnet-code 가 못 봤을 수 있다(21:07 창에 전달).
- 참고 1. 9 칸 표에서 깃발 env 를 뺀 것은 타당(같은 규칙이라 늘 대각선). 사양 J-T10 행에 적었다(v0.8).
- 참고 2. 「갈린 에피소드는 모두 한 방향(c-1w0 · c0w1) 칸」 은 모의 시험이 강등 수만 본다. `FrameCompareStats` 로 칸을 세어 그 두 칸 밖이 0 인지 보는 한 줄이 있으면 사양 시험 줄과 맞는다.
- 참고 3. 50 열 realized 끔 비율 허용 폭 0.04(사양 0.03). 6 회차 표본이라 넓힌 듯. 사양 쪽을 ± 0.04 로 맞춘다(v0.8).
- 참고 4. `test_world_frame.py` 머리말 3 행 「스위치 world_frame 기본 끔」 은 결정 8 전 문장(작업 사본). 커밋 전에 고칠 것.

## 4. 재지 않은 것

시험 실행(sonnet-code 통합 회귀 중) · Kit 안 S1 1000 스텝 동등성 · 실제 학습의 갈린 에피소드 빈도(J-T10 기록 뒤) · 끔 에피소드의 듬성 진입 빈도(M-T6 기록 뒤).
