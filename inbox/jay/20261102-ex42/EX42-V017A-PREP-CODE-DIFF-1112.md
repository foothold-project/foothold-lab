# 정본 v0.17a 대 prep · 통합 코드 값 대조 (EX-42 · 단계별)

> 분류: 검토 (정본 대 실행 설정 대조)
> 작성: planner-lx · 2026-11-12 00:1x
> 근거: lead 11/12 00:06 의뢰 · 정본 `inbox/jay/20261026-experiments/CURRICULUM-GATES.md` v0.17a (이 커밋) · 통합 가지 `lead/linux-integration-1109` 7d93df13 (#720 병합 뒤) 의 `foothold_s2/curriculum/ex42-prep.yaml` · `ex42-approvals.yaml` · 코드 줄 (**실측**: 파일을 직접 열어 yaml 로 읽음) · 원장 `decisions.tsv` d9d533e9 411~425 행 (**읽기**)
> 요지: 단계 상한 · 연장 · 예산 · env 수 · 경계 간격 · 승급 문턱 · D44 여섯 칸과 시간 · 평가 마찰 · 쉬운 등급 하한 · M 규칙 · E1 연장 계약은 정본과 prep 이 같다. 다른 곳은 열 가지다. 큰 것 셋: E1 `foot_slip −0.25` 가 통합 prep · 코드에 없음, E2~E6b · M 의 출구 판정기가 없음, 렌더 「최종 정본 때 지도 없음 연속 지형」 칸이 코드에 없음.
> 상태: 완료 · 코드 · prep 은 고치지 않음 · Kit 실행 0 · 11/12 00:2x 덧붙임 §2.1 (lead 00:16 배정과 처리 · 열한째 항) · §4 (단계 시작 연속 상한 정리안) · 정본은 v0.17b

## 1. 단계별 표

「정본」 은 v0.17a 의 §E.1 · §E.2 값, 「prep」 은 7d93df13 의 `stages[]` 값이다. 줄 번호는 7d93df13 의 `ex42-prep.yaml`.

| 단계 | 최대 회차 정본 · prep | 연장 정본 · prep | 입구 어댑터 (prep) | 출구 판정기 prep `exit_judge` · 코드 등록 | 같음 / 다름 |
|---|---|---|---|---|---|
| E0 | 250 · 250 (:190) | 없음 · 0 (:191) | `map39` (:177) | 없음 · `map39_e0` 등록 (`ex42_stage_judges.py:90`) | 같음 |
| E1 | 1,000 · 1,000 (:296) | +500 × 2 (HOLD 로 상한에 닿을 때만) · 500 × 2 (:297) · 승인 `extension_contract {judgment HOLD · after 1000 · increment 500 · max_count 2 · maximum 2000}` | `map39` (:281) | 없음 · `map39_e1_two_window` 등록 (:107) | 회차 · 연장 같음. **`foot_slip −0.25` 재학습은 다름** (§2-1) |
| E1F | 750 · 750 (:392) | +500 × 1 (가정 · 승인 문구는 「연장 별도」) · 500 × 1 (:393) · 승인 `extension_authorized: false` | `flag_two_window` (:322) | `flag_two_window` (:317) · 등록 (`ex42_e1f_judge.py:161`) | 회차 같음. **연장 세 곳이 다름** (§2-4) |
| E2 | 1,500 · 1,500 (:442) | +500 × 2 · 500 × 2 (:443) | `flag_two_window` (:423) | 없음 · 등록 없음 | 회차 · 연장 같음. **출구 판정기 없음** (§2-2) |
| E3 | 4,000 · 4,000 (:498) | +1,000 × 2 · 1000 × 2 (:499) | `kind_two_window_e2` (:482) | 없음 · 등록 없음 | 같음 + §2-2 |
| E4 | 3,000 · 3,000 (:571) | +1,000 × 2 · 1000 × 2 (:572) | `kind_two_window_e3` (:556) | 없음 · 등록 없음 | 같음 + §2-2. 쉬운 등급 `kind_floor 0.015` (:650) 같음 |
| E5 | 1,500 · 1,500 (:703) | +500 × 2 · 500 × 2 (:704) | `kind_two_window_e4` (:688) | 없음 · 등록 없음 | 같음 + §2-2 |
| M | 500 · 500 (:885) | +500 × 1 · 500 × 1 (:886) | `stage_exit_v1` (:847) · `enabled: false` | 없음 · 등록 없음 | 회차 같음. 규칙 같음 (아래 공통 표). 실행 연결은 §2-5 |
| E6a | 1,000 · 1,000 (:1045) | +500 × 1 · 500 × 1 (:1046) | `kind_two_window_e5` (:1029) | 없음 · 등록 없음 | 같음 + §2-2 |
| E6b | 3,000 · 3,000 (:1206) | +1,000 × 2 · 1000 × 2 (:1207) | `posture_two_window_e6a` (:1190) | 없음 · 등록 없음 | 같음 + §2-2. `kind_floor 0.015` (:1344) 같음. **wall 치수 다름** (§2-6) |
| J0~J4 | 정본 행 없음 | 정본 행 없음 | `pending` · `enabled: false` · 승인 `approved: false` | 없음 | **prep 에만 있음** (§2-7) |

### 1.1 단계 공통 값

| 항목 | 정본 v0.17a | prep · 승인 · 코드 (7d93df13) | 같음 / 다름 |
|---|---|---|---|
| 예산 | EX-42 자체 회차 20,000 · 누적 아님 · 연장은 남은 예산 안 | `training_budget {basis ex42_new_updates · maximum_updates 20000 · count_m_updates true · extensions_within_remaining_budget true}` (:42~) · 승인 `plan_amendment_1938` | 같음 |
| env 수 | 6144 (두 장 · 3072 × 2) | `environment.num_envs: 6144` (:59) | 같음 |
| E0 입구 | 팀장 채택 (m12000 · m13000) 으로 갈음 | `launch.require_ex41_graduation: false` (:36) · `parent_adoption {decision 285348de · checkpoints [m12000_20261107, m13000_20261108]}` | 같음. 정본 §E.4 표에 옛 키 `parent.graduation_json` 줄이 남음 (§2-9) |
| 자동 기동 | 승인된 단계 칸 안에서 관문 PASS 면 자동 기동 + 알림 | `launch.automatic: approved_stage_only` (:35) · 승인 `automatic_launch_allowed {mode approved_stage_only · require_gate_pass true · notify true}` | 같음 (설정). 실제로 이어지는 범위는 §2-2 |
| 경계 | 250 마다 멈춤 → 두 장 분배 평가 → 이어 학습 | `evaluation.interval_updates: 250` (:2341) · 승인 E1F `boundary_mode: stop_evaluate_resume` · 각 단계 `boundary_evaluation_interval_updates` | 같음 |
| 승급 문턱 | 창 64 · 두 창 · 성공 ≥ 52 · 생존 ≥ 60 | `evaluation.promotion {window_episodes 64 · windows 2 · success_min 52 · survival_min 60 · hold_if_invalid true}` | 같음 |
| D44 판정 칸 | 세 과제 × {gt, pred} 여섯 칸 · off 세 칸 기록 | `judge_cases` 여섯 · `record_cases` 셋 | 같음 |
| D44 시간 | settle 1.0 · 접근 4.0 · 정지 2 · 재출발 6.0 s · 정지 속도 ≤ 0.05 m/s 1.0 s · 접촉 발 z ≥ top − 0.08 | `timing {settle_s 1.0 · approach_limit_s 4.0 · stop_s 2.0 · restart_limit_s 6.0 · stop_hold_s 1.0 · stop_speed_mps 0.05 · foot_below_top_m 0.08 · top_hold_s 0.5}` · `valid_min 48` | 같음 |
| D44 꼭대기 도달 | 들어선 뒤 명령 0 · 0.5 s 머무름 · 네 발 동시 접촉 삭제 | `eval/ex42_d44_cells.py:23~42` `top_latch_mask` (모든 발이 앞 모서리를 넘음) · `restart_command` (래치 뒤 명령 0 · 상 4) | 같음 (**읽기** · Kit 재실행은 lead 가 함) |
| 평가 마찰 | 정지 0.8 · 운동 0.6 | `assumptions_pending_lead.evaluation_friction {static 0.8 · dynamic 0.6 · approved}` (:2527) · 소비 `eval/eval_map_modes.py:740` · `axis_v2_run.py:335` · `ex40_stand_eval.py:225` · `ex42_d44_eval.py:270` | 같음 (**읽기** · 재료 실측값은 미확인) |
| 쉬운 등급 하한 | E4 · E6b `kind_floor` 1.5 % | E4 (:650) · E6b (:1344) `kind_floor: 0.015` · 승인 `easy_kind_floor: 0.015` | 같음 |
| M 규칙 | 돌아가는 곳 = 들어간 단계 · M 회차는 원 단계 최대에 안 셈 · 20,000 에는 셈 · 1,000 회에 못 나가면 알림 + 원 단계 이어 가기 · p_map_off 0.3 유지 · 두 창 새로 | `branch_contract {return_to source_stage · maximum_updates_including_extension 1000 · m_updates_count_toward_source_maximum false · m_updates_count_toward_ex42_budget true · on_exhausted notify_and_return_to_source_stage · p_map_off_after_return 0.3 · required_new_windows_after_return 2}` | 같음 (계약). 실행은 §2-5 |
| E1F 명령 몫 | 깃발 0 → 0.10 · 전진 0.23 → 0.17 · 제자리 회전 0.09 → 0.07 둘 | `shares {flag 0.1 · forward 0.17 · spin_left 0.07 · spin_right 0.07 · stand 0.1 · reverse 0.14 …}` · 승인 `shares_delta` | 같음 |
| E1F 깃발 도달 | 목표 0.3 m 안 · 정지 0.5 s (가정) · 문턱은 W09 기준선 뒤 고정 | `flag_cells {reach_radius_m 0.3 · stop_hold_s 0.5 · stop_speed_mps 0.05 · judge 넷 · record 둘}` · 승인 `thresholds: null` | 같음 (문턱은 둘 다 비어 있음) |
| E2 새 종류 | `stepping_stones_low` L0 · 5 % | `exposure_at_E2`: `stepping_stones_low share 0.05 · level_cap 0` · `kind_choice start_stones_l0` | 같음 |
| 연속 L0~2 하한 | 연속 몫의 30 % (가정) | 각 단계 `continuous_low_level_floor {levels [0, 2] · fraction 0.30 · class assumption}` (E1F 부터) | 같음 |
| 렌더 식 | 배운 종 {현재 상한, L9} · 안 배운 종 L0 · 지도 eval_gt · eval_pred · 최종 정본 때만 probe_prop_only 연속 지형 | `eval/ex42_render_plan.py:15` `MAP_MODES (eval_gt, eval_pred)` · `:114` 배운 종 `{current_cap, L9}` · 아니면 `[0]` | 앞 셋 같음. **마지막 항 다름** (§2-3) |
| critic 대칭 | 정본 EX-42 절에 줄 없음 | E1 `critic_mirror: true` · 승인 `fields.critic_mirror` D174 | 정본에 없음 (§2-10) |

## 2. 다른 곳 목록

| # | 무엇이 다른가 | 정본 | prep · 코드 (7d93df13) | 고칠 쪽 (planner 의견) |
|---|---|---|---|---|
| 1 | E1 `foot_slip −0.25` 재학습 | §E.2 E1 「보상 가중」 행 (원장 11/11 23:49) | `ex42-prep.yaml` · `ex42-approvals.yaml` · `scripts/ex42*` 에 `foot_slip` 0 건 (grep). #719 는 이 머리에 없다 | prep · 승인 (#719 병합 뒤 다시 대조) |
| 2 | E2~E6b · M 출구 판정기 | 단계마다 「나가는 조건」 문장이 있다 | prep `exit_judge` 는 E1F 한 줄뿐 · 등록된 판정기는 `map39_e0` · `map39_e1_two_window` · `flag_two_window` 셋. 뒤 단계 입구 어댑터 이름 (`kind_two_window_e2` 등) 은 prep 에 적혀 있으나 같은 이름의 판정기 등록은 없다 | 코드 (scripter). 자동 기동은 지금 E1 → E1F 까지만 이어진다 |
| 3 | 렌더 「최종 정본 때만 지도 없음 연속 지형」 | §E.3 「영상」 행 (원장 12:02) | `ex42_render_plan.py` 에 `probe_prop_only` 0 건 | 코드 |
| 4 | E1F 연장 | 「+500 × 1 (가정) · 승인 문구는 연장 별도」 | prep `extension_updates 500 · max_count 1` · 승인 `extension_authorized: false` | 팀장 한 줄 (연장을 둘지) 뒤 정본 · prep 을 같이 |
| 5 | M 복귀의 실행 연결 | 규칙 문장 | 계약은 prep 에 있으나 승인 `return_stage_id: null` · `source_stage_contract_status: decided_source_stage_return_runtime_pending` · `stage_judgment_policy: pending` | 코드 (복귀 런타임) |
| 6 | D 묶음 wall 치수 | §E.2 E6b 「치수」 행: wall 1.20 / 0.80 등 확정 (원장 12:02) | prep 주석 「wall 은 치수 미정이라 0」 (:1215) · 「열지 않음」 (:1341) | prep (노출 표 · 주석) |
| 7 | 점프 J0~J4 단계 | 정본 행 없음 (원장 13:07: 범위 밖 · 01:5x: 착수 시점만 결정) | prep `stages` 에 J0~J4 다섯 행 (`enabled: false` · `assumption`) · 승인 `stage_j0~j4_authorization approved: false` | 정본 쪽에 「prep 에 꺼진 초안 행이 있다」 한 줄을 둘지 lead 결정 |
| 8 | 단계 시작 때 연속 상한 | E1 「5 → 6 (L5 창 통과 뒤)」 · E1F 「E1 끝 상한 그대로」 · E3 「L6 → L9」 | `exposure_at_E2` 연속 `level_cap 5` · E3 6 · E4 부터 9 · E1F `null` (E1 끝 값) | E1 이 6 으로 끝나면 E2 의 5 와 어긋난다. 값은 planner 노출 표의 가정이다. lead 결정 뒤 prep |
| 9 | 정본 안에 남은 옛 줄 | §E.4 표 `parent.graduation_json` 키 줄 · 단계별 「영상」 행 (성공 1 · 실패 1 꼴) · §E.4 `video.*` 키 줄 | prep 은 `require_ex41_graduation: false` · 렌더는 2 절 식 | 정본 (다음 판에서 정리 · 이번엔 원장 행만 옮김) |
| 10 | 정본에 줄이 없는 실행 설정 | 없음 | critic 대칭 (E1 부터 · D174) · 밀기 끔 종 목록 (`push_mask.off_kinds`) | 정본에 넣을지 lead 결정 (11/11 원장 행에는 없음) |

## 2.1 lead 11/12 00:16 배정과 처리 (정본 v0.17b 기준)

| # | 처리 |
|---|---|
| 1 | 다름이 아니다 (lead 정정): `foot_slip −0.25` 는 실험 가지에만 있고 통합에 없는 것이 맞다. 재학습 결과 뒤 통합 여부를 정한다 |
| 2 | scripter 진행 중 (lead 배정) |
| 3 | runner (lead 배정) |
| 4 · 5 · 6 | verifier (lead 배정) |
| 7 | 정본에 「꺼짐 · 미승인」 표시만 넣음: §E.1 표 아래 J0~J4 문단 · §E.4 `stages[].id` 행 |
| 8 | 정리안 §4 (lead · 팀장 결정 필요) |
| 9 | 정리함: §E.4 `parent.graduation_json` 행 (쓰지 않음 표시) · 단계별 「영상」 행 열 개와 `video.*` 행 (§E.3 식이 우선) · §E.1 읽는 법의 env 수 문장 |
| 10 | 정본 행 추가: §E.2 E1 「critic 대칭」 (D174 · 원장 11/09 00:4x) · §E.3 「DR · 밀기 끔 종」 (DR 1.0 은 원장 11/06 17:3x · 밀기 끔은 원장 행 없음) |
| 11 (새로) | E1 연속 상한. 정본 v0.17b (원장 11/06 22:3x · 23:2x): 「L5 → L9 · 경계마다 +1 · 성과 승급」. prep 7d93df13: `exposure_at_E1` 연속 `level_cap 5` 고정이고 주석이 「5 → 6 올림은 따로 L+ 경계」 라고 적음. 끝난 E1 실행은 상한 5 로 끝남 (**실측**: 로그 `EX42_E0_EXPOSURE` cap 5 · 451~700 회 창 L6~9 시작 0). 즉 원장의 올림이 실행 경로에 없다. 고칠 쪽: §4 결정 뒤 prep · 실행기 |

## 3. 안 한 것

- 단계별 노출 몫 전부 (E3~E6b 의 종류 × 몫 × 상한 수십 행) 는 값마다 대조하지 않았다. 정본은 문장 (「각 5 %」 「10 / 70 / 20」) 이고 prep 은 planner 노출 표의 가정값이라 E2 · 쉬운 등급 · 연속 상한만 봤다.
- 코드는 줄을 읽기만 했다. Kit 실행 · CPU 시험은 돌리지 않았다. #719 는 통합 머리에 없어 대조하지 못했다.
- prep · 승인 · 코드는 고치지 않았다.

## 4. 단계 시작 연속 상한 정리안 (lead 00:16 ⑧)

### 4.1 원장이 정한 것 (읽기)

| 원장 행 | 요지 |
|---|---|
| 11/06 22:3x | E1 첫 변경 = 같은 지형 종류에서 상한 L5 → L9 · 성과 승급 |
| 11/06 23:2x | 경계마다 +1 (L5 → L9) · 어려운 단계 미달로 진도가 멈추지 않게 |
| 11/07 16:3x · 17:2x | 상한 멈춤: 새 어려운 칸 미달로는 멈추지 않고 이미 배운 유지 칸이 크게 떨어질 때만 잠시 · 유지 미회복이면 재상승 없음 · 학습 계속 |
| 11/08 19:0x · 22:5x | E1 부터 L5 → L9 · 한 단계씩 (재확인) |
| 11/11 13:07 | 승인 칸 실측 값 (부모 sha · 상한 · 메시 sha · 기준선) 은 앞 단계 증거로 채우고 재고정 |
| 11/11 23:49 | E1 재학습은 `foot_slip −0.25` 하나만 바꾸고 250 회마다 끝난 E1 과 비교 |

### 4.2 원장이 정하지 않은 것

- E1 이 L9 전에 끝났을 때 (나가는 조건은 유지표 + D44 이고 L9 도달은 조건이 아니다) 나머지 올림을 어디서 하는가. 11/06 23:2x 행은 analyst v5 의뢰 (「미달 시 마지막 통과 레벨 고정하고 다음 단계 · 뒤 블록 재도전 1 회」) 까지이고 결정 행이 없다.
- 한 경계에서 「성과」 를 통과로 보는 창 수 (v0.16 은 두 창 · 원장은 경계마다).

### 4.3 정리안 (planner · 가정 표시)

1. **단계 시작 상한 = 앞 단계 끝 영수증의 상한** (원장 11/11 13:07). prep 의 `exposure_at_E2` 5 · `E3` 6 · `E4` 부터 9 같은 고정 숫자를 E1F 처럼 `null` (앞 단계 끝 값) 로 바꾼다. 그러면 「E1 끝 6 대 E2 5」 같은 어긋남이 생길 자리가 없다.
2. **올림은 경계마다 +1, 그 경계의 유일한 축 변경으로** (원장 11/06 23:2x + 정본의 한 경계 한 축). 한 경계 통과 기준은 현재 상한 칸 전진 1.0 × 3 모드 성공 ≥ 52/64 · 생존 ≥ 60/64 한 창 (**가정** · v0.16 의 두 창을 원장 「경계마다」 에 맞춰 한 창으로).
3. **E1 이 L9 전에 끝나면 뒤 단계에서 이어 올린다** (**가정**). 다른 축 변경이 없는 경계에 +1 을 넣고, K · D · C 변경이 있는 경계에서는 올리지 않는다. 근거는 11/06 23:2x 「미달로 진도가 멈추지 않게」 이다. 반대 안은 「E1 을 L9 까지 붙잡는다」 인데 같은 행과 어긋난다.
4. **E1 재학습에는 올림을 넣지 않는다** (planner 의견). 원장 11/11 23:49 가 「`foot_slip` 하나만 바꿈 · 끝난 E1 과 비교」 이고 끝난 E1 은 상한 5 로 돌았으므로, 재학습도 상한 5 로 두어야 대조가 깨끗하다. 올림은 재학습이 끝난 뒤의 첫 「다른 축 변경 없는 경계」 부터 시작한다.

### 4.4 결정이 필요한 한 줄

「연속 상한 L5 → L9 올림은 E1 재학습이 끝난 뒤부터 경계마다 +1 로 뒤 단계에 이어 간다 (단계 시작값은 앞 단계 끝 값) / E1 안에서 L9 까지 올린 뒤에 나간다」.
