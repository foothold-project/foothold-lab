> 분류: A/정책학습 · EX-41 요구 대장 U18 (16 env 회전 여섯 경우 진단 대 W57)
> 작성: planner (Claude Fable 5.1) · 2026-11-02 20:2x
> 근거: RULES-HUB v1.5 §8.1 194 행 · §8.2 203 · 205 행 · 판 이력 · EX41-REQUIREMENT-REGISTER 0e85c3d7 RH191~192(151 행) · U18(205 행) · WORKLIST D55(81) · D57(83) · D58(84) · W57(237) · W71(251) · CURRICULUM-GATES v0.8 222 · 374 · 394 행 · FLOW-experiment-cycle-1029 §3 · EX40-LAUNCH-CHECKLIST B13 · C1 · 코드 `turn_probe.py` · `turn_probe_plan.py` · `axis_v2_cells.py` · `ex41_fixed.py:20~27` · `ex41_eval_once.py` · `ex41_score_watch.py`(analyst 사본 c6fff190 읽기 전용) · EX-40 run 폴더 · EX-35 평가 사슬 로그(실측)
> 요지: 「16 env 회전 여섯 경우를 W57 로 대체한다」 는 결정 기록은 **없다**(저장소 전체 grep). 10/29 21:1x D55 · D57 · D58 이 기준 축 v2(W57) 와 D57 점수표를 정했고 11/01 W15 연속 칸(38ee51df) 이 좌 ↔ 우 전환을 64 env 로 옮기면서 **사실상** 범위가 옮겨갔지만 RULES-HUB §8.1 · R12 는 v1.5 그대로라 정본 둘이 모순이다. EX-40 은 16 env 진단을 한 번도 안 쟀고(turn16 폴더 0) EX-41 사슬에도 없다(grep 0). 경우별로 보면 좌 · 우 독립 · 좌 ↔ 우 전환 · 후진 · 정지는 64 env 잣대가 받았고, **전진 → 좌 · 전진 → 우 전환 · 걸으며 돌기 · Q/C 16 env 통계**는 어디에도 없다. 복원 안 셋을 적고 (가) 결정 기록 + (나) 단계 끝 7 저장본 복원(저장본당 약 17.5 분 GPU1, EX-35 실측 환산)을 권한다.
> 상태: v0.2 · **팀장 결정 D151 (가)+(나)**(11/02 20:2x) · (나) 는 W91(runner · analyst · 기동 전) 로 등록 · lead U18-2(RULES-HUB 문구) 대기 · 코드 · GPU 없음

# U18 · 16 env 회전 여섯 경우 진단은 W57 로 대체됐나

## 0. 범위 · 가정

- 카드(등록부 U18 · lead 11/02 18:2x): 「창 경계 16 env 회전 여섯 경우 진단(또는 W57 로 대체됐다는 결정 기록)」 · 「대체된 근거(없으면 복원)」.
- 가정 1: 「복원」 은 planner 가 코드를 넣는 것이 아니라 **복원 안(자리 · 비용 · 담당)** 을 적어 lead 가 배정하는 것(RULES-HUB 1 절 planner 는 구현 · GPU 없음).
- 가정 2: RULES-HUB · 등록부는 lead 가지(`feature/verify-v2-mvp-jay`) 정본이라 고치지 않고 고칠 문구를 §5 에 적는다.
- 등급: 결정 · 설계 · 코드 · 실측 · 계산 · 읽기(다른 세션 결과, 미재측).

## 1. 결론

| 물음 | 답 | 등급 |
|---|---|---|
| 대체 결정 기록이 있나 | **없다.** WORKLIST D01~D139 · RULES-HUB v1.0~v1.5 · CURRICULUM-GATES v0.8 · FLOW · 등록부 · 감사 · QA 어디에도 「16 env 여섯 경우를 W57(또는 W15) 로 대신한다」 는 문장이 없다 | 실측(`git grep -E '여섯 경우\|turn16\|16 env 회전'` origin/feature/verify-v2-mvp-jay, 11/02 20:0x) |
| 그런데 왜 안 재나 | 10/29 21:1x 에 D55(기준 축 v2 정의) · D57(기본 보행 졸업선 = 13 명령 × 3 모드 점수표) · D58(W57 기준 축 v2 상세) 이 들어오면서 평가 사슬이 「W15 13 명령 + 순서 칸 3 + W57」 로 짜였고(CURRICULUM-GATES B2 행 222), 11/01 00:14 부터 채점기 W15 연속 칸(38ee51df) 이 좌 ↔ 우 전환을 64 env 로 잰다(W71). 16 env `turn_probe` 는 그 사슬에 안 들어갔다 | 결정 · 코드 · 읽기 |
| 정본 상태 | RULES-HUB §8.1(194 행) 「16 env 회전 진단 … 창 경계는 반드시」 와 §8.2 R12(203 행) 「보행 주장은 16 env 여섯 경우 + 영상이 모두 맞을 때만」 · 205 행 「회전 판정 통계는 16 env 평균」 은 v1.5(10/26) 그대로. 실제 사슬과 모순 | 실측(문서) |
| EX-40 에서 쟀나 | 안 쟀다. run 폴더에 turn16 폴더 0 · 31 저장본 score-watch-b 는 map64 · stand 세 모드 · axis_v2(W57) · axis250 16 저장본 W57 | 실측(`find … -iname '*turn16*'` 0) |
| EX-41 사슬에 있나 | 없다. 계약 순서는 map64 → stand → W57 → W78 v2 이고 `ex41_eval_once.py` · `ex41_score_watch.py` 에 turn_probe 0 건 | 코드(c6fff190) · 계약(analyst, 읽기) |
| 마지막 16 env 측정 | EX-35 m2000(10/27 03:17) · `impl-turncases/logs/ex35_eval/m2000/turn16_{eval_gt,probe_prop_only,eval_pred}/` · 10 경우(회전 8 + 전진 걸음 2) · 16 env · 칸 해시 7f49a1e9(레벨 0) | 실측 |

## 2. 사실 표

| # | 사실 | 출처 | 등급 |
|---|---|---|---|
| F1 | 16 env 회전 진단 = `foothold_s2/eval/turn_probe.py` (`--envs 16 --cases all --forward-gaits --fixed-terrain`). 경우 표 `turn_probe_plan.PROTOCOLS`: indep_right · indep_left · fwd_then_right · left_then_right · right_then_left · fwd_then_left · walk_turn_left · walk_turn_right(앞 4 s + 기록 8 s · wz 1.2 · 걸으며 돌기 0.5 + ±0.5) + 전진 걸음 fwd0.5 · fwd1.0. 기본 다섯(`DEFAULT_CASES`) 은 전진 → 좌 · 걸으며 돌기 둘이 빠짐 | 코드 `turn_probe_plan.py:24~34` | 코드 |
| F2 | 판정 통계: 요 추종비 Q(16 env 평균) · 네 발 동시 접촉 C · kept(끝까지 선 env) ≥ 14 · 좌우 비대칭(`side_asymmetry_independent`) · 순서 짝 넷(`ORDER_PAIRS`, 독립 대 연속) | 코드 `turn_probe_plan.py:51~56 · 100` · CURRICULUM-GATES 394 행(C2a: Q ≥ 0.6 · C ≤ 0.6 · kept ≥ 14) | 코드 · 설계 |
| F3 | W57 기준 축 v2 = `axis_v2_run.py` + `axis_v2_cells.py`: 64 env · 레벨 2 고정 · 시드 42 · 10 칸(fwd0.5 · fwd1.0 · goal_left_delta000 · goal_right_delta000 · goal_left_delta030 · goal_right_delta030 · goal_left_delta060 · goal_right_delta060 · goal_left_delta090 · goal_right_delta090) × 3 모드 = 30 칸 · 목표까지 wz 1.0 회전 뒤 정지 · 칸 값 `yaw_final_minus_start_median_rad` · `goal_reached_envs` · `stop_end_error_median_rad` · `contact_left_right_gap_median` · `contact_diagonal_gap_median` · `alive_at_end` | 코드 · 실측 `axis250/model_6250/axis_v2.json`(schema foothold-axis-v2/1 · suite W57-v2 · envs 64 · steps 300 · fixed_level 2) | 코드 · 실측 |
| F4 | W15 64 env 13 명령 + 연속 칸 3: `map_modes.json` 의 `sequences` = spin_left_to_right · spin_right_to_left · stop_and_restart(세 모드 모두) | 실측 `score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json` | 실측 |
| F5 | EX-41 유지 판정 칸은 13 명령 × 3 모드 = 39 기록 · 26 판정(`CELLS`). 연속 칸 3 과 W57 은 판정 칸 밖(기록) | 코드 `ex41_fixed.py:20~27` · analyst 계약 「W57/W78 은 기록」 | 코드 |
| F6 | EX-40 score-watch-b 는 m500~m8000 31 저장본. `axis_v2/` 폴더가 있으나 m1000~m2750 등 9 저장본은 sha · head 두 파일뿐(W57 사슬 rc1, WL104 D78 알려진 결함) · 250 간격 W57 은 `axis250/model_<N>/`(16 저장본, 단계 끝 제외) | 실측 ls | 실측 |
| F7 | 16 env 진단 시간(EX-35 m2000, GPU1, Kit 기동 포함): eval_gt 02:56:25 → 03:02:08 ≈ 343 s · probe_prop_only → 03:08:02 ≈ 354 s · eval_pred 03:11:19 → 03:17:08 ≈ 349 s → **모드당 ≈ 350 s · 세 모드 ≈ 17.5 분** | `impl-turncases/logs/ex35_eval/m2000/timing.txt` · `turn16_*/run.log` mtime | 실측 · 계산 |
| F8 | 규칙 R12 는 FAILURE-LOG 117 행에도 있다(10/25 「측정 하나로 보행을 단정」 → 「64 env 평가 + 16 env 여섯 경우 + 영상이 모두 맞을 때만」) | FAILURE-LOG :117 | 결정 |
| F9 | 10/25 22시 실측(16 env): 전진 → 좌는 좌 독립과 같았고 약한 곳은 우회전과 좌 → 우 전환이었다 | AGENDA-LEAD :111 · QA-EXPLAINERS :71 | 읽기(당시 lead 실측) |

## 3. 경우별 대조 (여섯 경우 + 단계 추가 셋 → 지금 잣대)

| 경우(16 env, turn_probe) | 지금 잣대에 있는 자리 | 통계가 같은가 | EX-41 에서 판정에 쓰나 | 상태 |
|---|---|---|---|---|
| 좌 독립 `indep_left` · 우 독립 `indep_right`(wz ±1.2 · 8 s) | W15 `spin+1.2` · `spin-1.2`(64 env · 6 s · 생존 · 추종 오차) + W57 goal 30 · 60 · 90°(wz 1.0 · 목표 정지 · 접촉 좌우 · 대각 간격) | 아니다(Q · C 16 env 평균 → 생존 · 오차 · 정지 오차 · 접촉 간격 중앙값) | W15 는 판정(26 칸, 복원 13 칸은 늘 기록 · D160) · W57 은 기록 | **대체됨**(정의는 다름) |
| 좌 → 우 `left_then_right` · 우 → 좌 `right_then_left` | W15 연속 칸 `spin_left_to_right` · `spin_right_to_left`(64 env · 38ee51df · 11/01 00:14 부터) | 아니다 | **기록만**(`CELLS` 13 × 3 밖) | 부분(측정 있음 · 판정 없음) |
| 전진 → 좌 `fwd_then_left` · 전진 → 우 `fwd_then_right` | 없음. W57 fwd0.5 · fwd1.0 은 전진 중 yaw 누적(heading 끔) 이고 회전 전환이 없다. `sequences` 에도 없다 | - | - | **빠짐** |
| 걸으며 돌기 `walk_turn_left` · `walk_turn_right`(0.5 + ±0.5) | 없음. W15 13 명령에 vx + wz 동시 칸 없음. CURRICULUM-GATES 374 행 「16 env 걸으며 돌기 기준선 미측(A5)」 그대로 | - | - | **빠짐** |
| 후진(단계 추가) | W15 `back0.5` · `back1.0` 세 모드(판정) | - | 판정 | 대체됨 |
| 정지(단계 추가) | W15 `stop` + stand 세 모드(`stand_min_passed 61`) + `stop_and_restart` 연속 칸 + D128 정지 진입 뒤 각속도(계획) | - | 판정(stand) · 기록 | 대체됨 |
| Q(요 추종비) · C(네 발 동시 접촉) · kept ≥ 14 · 좌우 비대칭 | W57 `contact_left_right_gap_median` · `contact_diagonal_gap_median` · P3 대칭비 S(이동비, lead 19:3x 해석) | 환산 불가(다른 정의) | 기록 · P3 는 `critic_mirror_candidate` 만 | 정의 바뀜 |
| 200 Hz 관절 q · 토크 · 접촉 힘 · 미끄럼 기록 | U10 `knee_effort` · U15 `all_link_contact` · U16 foot_slip(학습 중 계측, 평가 아님) | 아니다(학습 분포 대 고정 칸) | 기록 | 부분 |

빠진 둘은 EX-41 처치가 가장 먼저 보일 자리다: 회전 L1 −0.5(정지 때 몸 돌기) · heading 0.5 → 0.3 · 스윙 비용은 「전진하다 돌기」 와 「걸으며 돌기」 에서 걸음새가 바뀌는지로 드러난다(설계 §5.1 · §5.2 · 팀장 관찰 D128). 지금 잣대에는 그 둘이 없고, R12 는 보행 주장에 16 env 여섯 경우를 요구한다.

## 4. 왜 「대체됐다」 고 적을 수 없나

- 대체라면 ① 결정 번호 ② 같은 물음에 답하는 칸의 대응 ③ 옛 잣대의 마지막 값과 새 잣대의 첫 값이 같은 저장본에서 나란히 있어야 한다(FLOW §3 「묶음 판이 바뀌면 판 번호를 올리고 옛 판 결과와 섞지 않는다」). 셋 다 없다.
- 있는 것은 「새 잣대를 만들었다」(D55 · D58 · 38ee51df) 와 「새 잣대만 사슬에 넣었다」(EX-40 점수기 B7 · C1) 뿐이다. 「옛 잣대를 뺀다」 는 없다.
- 그래서 등록부 151 행 「W57 로 대체됐다는 문서 근거 못 찾음」 은 맞다. planner 가 더 찾아도 없었다.

## 5. 복원 안

| 안 | 내용 | 비용 | 얻는 것 · 잃는 것 | 등급 |
|---|---|---|---|---|
| (가) 결정 기록만 | WORKLIST 에 D 번호 하나: 「16 env 회전 여섯 경우 진단은 W15 13 명령 + 연속 칸 3 + W57 기준 축 v2 로 대신한다. 전진 → 회전 전환 · 걸으며 돌기 · Q/C 통계는 EX-41 에서 재지 않는다(EX-42 시작 경계에서 W57 칸으로 다시 정함)」. RULES-HUB §8.1 194 행을 그 문장으로, §8.2 203 행 R12 를 「W15 연속 칸 · W57 · 영상」 으로, 205 행 「16 env 평균」 을 「64 env 중앙값 · 생존」 으로 고침(lead 가지) | 0 | 정본 모순 해소. 빠진 둘은 EX-41 동안 못 봄(팀장이 명시적으로 버리는 결정) | 계획 |
| (나) 단계 끝 복원 | EX-41 단계 끝 저장본 7 개(n0 · n750 · n1750 · n2750 · n4000 · n4500 또는 n5000 · T0′ 끝) 에서 `turn_probe --envs 16 --cases all --forward-gaits --fixed-terrain` × 세 모드(D132 지도 셋 강제) 를 GPU1 사슬 끝(W78 v2 뒤) 또는 W70 꼴 단계 끝 루프에 추가. 판정 칸에 넣지 않고 기록 + R12 보행 주장용 + `side_asymmetry_independent` 추적. 영수증: 저장본 sha · rc · `TURNPROBE_DONE` 줄 · 칸 해시 7f49a1e9 | 저장본당 ≈ 17.5 분(F7) × 7 ≈ **2 h GPU1**(계산) · 코드: 호출 + 영수증 + 시험(runner · analyst) | 빠진 둘과 Q/C 를 단계마다 봄. 250 경계는 안 봄(RULES-HUB 「창 경계는 반드시」 의 창 = 단계 끝으로 읽음, 가정) | 계획 · 실측 환산 |
| (다) 250 마다 | 20 저장본 × 17.5 분 ≈ 5.8 h GPU1. HO33(점수기 전체 1 회가 250 회 간격 안에 끝나는지, 창 = 250 × 25.72 s ≈ 107 분) 에 W15 + stand + W57 + W78 v2 240 조합 + axis250 뒤로 17.5 분이 더 붙음 | 5.8 h · 창 초과 위험 | U4 시간 측정 전에는 권하지 않음 | 계획 |
| 옮기기(뒤) | 전진 → 회전 전환 · 걸으며 돌기를 W57 `case_specs` 에 64 env 칸으로 추가(같은 영수증 · 같은 레벨 2). W57 묶음 판 번호가 올라가므로(FLOW §3) **EX-41 도중 불가 · EX-42 시작 경계**에서 | 코드 · 판 번호 | 16 env 와 64 env 를 섞지 않고 빠진 둘을 기준 축에 넣음 | 계획 |

**planner 추천: (가) + (나) → 팀장 결정 D151 로 채택(11/02 20:2x).** 까닭 셋. ① R12 는 살아 있는 규칙이고 EX-41 보고는 「정지 뒤 안 돈다 · 뒷발을 든다 · 전환이 매끄럽다」 같은 보행 주장을 하게 된다. ② 빠진 둘(전진 → 회전 · 걸으며 돌기) 이 바로 이번 처치가 보일 자리다(§3). ③ 2 h 는 EX-41 35.7 h 의 5.6 %(계산) 이고 GPU1 은 학습을 막지 않는다. 다만 (나) 의 Q · C 값은 **판정선이 아니라 기록**이다(결과를 보고 문턱을 만들지 않음 · EX-35 C2a 문턱 Q ≥ 0.6 · C ≤ 0.6 · kept ≥ 14 는 그 판의 가정값이지 EX-41 의 선이 아님).

주의: `turn_probe` 기본 칸 해시 7f49a1e9 는 레벨 0 이고 `--fixed-level` 을 주면 해시가 바뀐다(코드 `turn_probe.py` 인자 도움말). EX-41 L0~2 와 맞추려면 레벨 0 그대로 두고 옛 판(EX-32~35) 과 같은 칸으로 잰다. 지형 메시가 EX-40 과 같은지(10 줄 × 23 열) 는 runner 가 `terrain_hash` 로 확인한다(미확인).

## 6. 결정 물음

| 번호 | 물음 | planner 안 | 누가 |
|---|---|---|---|
| U18-1 | (가) 만 · (가)+(나) · (가)+(다) 가운데 | (가)+(나) | 팀장 → **닫힘 D151**(11/02 20:2x): (가)+(나). 빠진 「전진 → 회전 전환 · 걸으며 돌기 · Q/C」 는 단계 끝 저장본 7 개에서 16 env 진단(지도 셋 D132 · 기록 전용) · EX-42 시작 때 W57 칸에 넣는다 |
| U18-2 | RULES-HUB 194 · 203 · 205 행 문구와 D 번호 | §5 (가) 문장 그대로 · 「대체」 가 아니라 「대신 잰다 · 빠진 둘은 EX-42 경계에서」 로 적음 | lead |
| U18-3 | (나) 의 담당 · 자리(사슬 끝 대 단계 끝 루프) · 시점 | runner(사슬) · analyst(영수증 · 시험) · U4 시간 측정 뒤 n750 전 | lead → **W91** 로 등록(runner · analyst · 기동 전, WORKLIST 11fdb8e4 285 행: 「단계 끝 저장본 7 개에서 turn_probe 16 env 여섯 경우 + 전진→회전 · 걸으며 돌기 × 지도 셋, GPU1 사슬, 기록 전용 영수증」). 자리는 「GPU1 사슬」 로 정해졌고 시점 n750 전은 그대로 제안 |

## 7. 안 한 것 · 미재측

- 코드 · 사슬 · RULES-HUB · 등록부를 고치지 않았다. GPU 를 쓰지 않았다.
- F7 시간은 EX-35 10/27 로그의 파일 시각 차(Kit 기동 포함) 로 계산한 값이다. EX-41 환경(3,072 env 학습이 GPU0 에서 도는 동안 GPU1) 에서 다시 재야 한다(U4).
- 10/25 실측 F9 와 analyst 계약 · W71 상태는 읽기다. W57 의 각 칸이 실제로 어떤 판정 문턱에 걸리는지는 EX-41 에서 「기록」 이라는 계약 문장만 확인했다.
- `turn_probe` 가 지금 analyst 사본에서 EX-41 task 이름(자세 명령 2 칸 추가 · 지각 450) 으로 그대로 도는지는 미확인이다(관측 차원이 바뀌면 loader 가 거부할 수 있음, 가정).

## 8. 근거 경로

- 규칙: `inbox/jay/20261019-design/RULES-HUB.md` v1.5 §8.1 194 · §8.2 202~205 · 판 이력 297 / `FAILURE-LOG.md` 117 / `inbox/jay/20261028-plan/FLOW-experiment-cycle-1029.md` §3
- 결정: `inbox/jay/20261028-plan/WORKLIST.md` D55(81) · D57(83) · D58(84) · W57(237) · W71(251) / `inbox/jay/20261026-experiments/CURRICULUM-GATES.md` 222 · 374 · 394 / `inbox/jay/20261028-plan/EX40-LAUNCH-CHECKLIST.md` B7 · B13 · C1
- 등록부: `inbox/jay/20261101-ex41/EX41-REQUIREMENT-REGISTER.md` 0e85c3d7 151 · 205 / `QA-EXPLAINERS.md` 56 · 69~79 / `inbox/jay/20261019-design/AGENDA-LEAD.md` 111
- 코드(analyst 사본 c6fff190 읽기 전용): `foothold_s2/eval/turn_probe.py` · `turn_probe_plan.py:20~56 · 100` · `axis_v2_cells.py:1~30` · `axis_v2_run.py:130~160` · `curriculum/ex41_fixed.py:20~27` · `ex41_eval_once.py` · `ex41_score_watch.py` · `eval/ex35_eval_chain2.sh:82`
- 실측: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/{score-watch-b,axis250}` · `score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json` · `axis250/model_6250/axis_v2.json` / `C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval/m2000/{timing.txt,rc.txt,turn16_*/run.log}`
- 시험: `u18_cases_check.py`(이 문서가 코드의 경우 이름을 빠짐없이 적었는지 대조)
