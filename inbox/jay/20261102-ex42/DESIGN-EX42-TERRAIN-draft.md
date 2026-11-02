> 분류: A/정책학습 · 설계 초안 (EX-42 지형 구간 · 지형 미리 넣기 · 종류별 승급 · 평가 칸 · 시작 전 측정)
> 작성: planner · 2026-11-02 17:4x v0.1 (lead 17:1x 의뢰: 「이후 실험도 잘 준비하고 있나」 · 근거를 열고 쓸 것 · 정할 것은 표로) · 19:5x **v0.2**(lead 18:2x: analyst `D:/mai-tmp/analyst/OPINION-EX42-Q-1102.md` 반영. Q6 유지 판정 26 · 기록 39 로 정정, Q7 발 들기 「새로 켬」 삭제, Q1 · Q2 · Q4 · Q9 · Q11 · Q13 의 의견을 §13b 에 나란히. Q11 은 P7 졸업 판정 정본(`inbox/jay/20261101-ex41/P7-GRADUATION-SPEC.md` 53fda76c) 에 연결)
> 근거: WORKLIST 122a6435 D106 · D113 · D114 · D115 · D117 · D124 · D126 · D130 · D133 · D136 · D138 · W55 · W59 · W72 · W86 / analyst `inbox/jay/20261102-analysis/PLAN-EX42-TERRAIN-GATES.md`(fb9cda8d) · `SPEC-JEPLO-PRESET.md`(f2ca807c) · `foothold_s2/terrains/jeplo_preset.py` / `inbox/jay/20261019-design/15-TERRAIN-CURRICULUM.md` v1.4 §2~8 · `14-COMMAND-GENERATOR.md` §3 · §5 / `inbox/jay/20261018-next-arch/SPEC-ame2-go2.md` §1.6 / `inbox/jay/20261012-arch-discussion/PAPERS-architecture.md` START 표(II-D3 · Fig. 6 · Table II) · AME-2 부록 A / `inbox/jay/20261026-experiments/CURRICULUM-GATES.md` v0.6c T0~T7 · 1b.6 · 1b.7 / `inbox/jay/20261101-ex41/DESIGN-EX41-STAGE2-draft.md` v0.7.3 §4 · §11 / 코드(ceadc326 · d5c14948): `terrains/columns.py` · `rough_go2_cfg.py` · `s2_layout.py` · `s2_runtime.py` · `progression.py` · `sparse_terrains.py` · `tasks/s2_env_cfg.py` · `eval/fixed_terrain.py` · `eval/map_mode_cells.py` · `eval/axis_v2_run.py:180~200` · `curriculum/ex41-fixed5000.yaml` · `curriculum/ex41.py` · `curriculum/rules.py` · `runners/start_runner.py:86~146` · `runners/map_stats.py` · `eval/eval_dr_mode.py` / Isaac Lab 2.3.2 `terrain_generator.py:240~262` / EX-40 실행 `main/EX-40-B-main_20261031_041337_26240/params/env.yaml`(num_envs 3072 · 23 열 · 8 × 8 m · use_cache false · max_init 2 · height_scanner 0.1 m × [1.6, 1.0] · depth_cam 60 × 60 · 0.1 s) / Go2 URDF `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf`(sha256 f130b1d2…) · Lite3 URDF `…/MGDP/…/all_dog/lite3/urdf/lite3.urdf`(f5e5003d…) 실측 / 웹 제원(Lite3 610 × 370 mm · Go2 700 × 310 × 400 mm, 아래 §4)
> 요지: EX-42 는 EX-41 T0′ 졸업 저장본에서 시작하는 「지형 구간」 이다. 시작 경계에서 지형 네 묶음(15-TERRAIN 13 종 50 열 · AME-2 12 종 · JEPLO 7 종 · 지형 2 판 3 종 = 35 종) 을 **한 번에 열로 만들고** 노출은 env 재배정으로만 올린다(D114 · W86 · Isaac 은 비율 0 이면 열이 안 생김). 승급은 두 층(env 레벨 = 종류별 완료 정의 · 종류 노출 확대 = 종류별 성과 창), 평가 칸은 env 번호가 아니라 `(묶음, 종류, 레벨)` 로 찾고, 시작 전에 메모리 · 생성 시간 · 광선 비용을 새 프로세스로 잰다. START 치수의 Go2 축척은 15-TERRAIN v1.4 의 「절대 치수 재현」 결정과 부딪히므로 두 안을 숫자로 나란히 두고 팀장 결정으로 올린다(Q1). 숫자는 전부 출처 등급을 달았고, 가정값은 §13 표에 모았다.
> 상태: v0.2.1(D146 · D148 · D151 반영, 11/02 20:5x) · 코드 · GPU 없음 · analyst 의견 1 차 반영(§13b) · 두 겹 검토 전 · 정할 것 Q1~Q13 열림(Q14 는 v0.2 에서 닫힘 후보) · analyst PLAN v0.1 과 겹치는 자리는 「같음 · 다름」 으로 표시

# EX-42 지형 구간 설계 초안

## 0. 범위 (지시를 다시 적음 · 가정)

lead 17:1x 의뢰를 내 말로: 「EX-42 지형 구간의 설계 초안 v0.1 을 fable-25a 에 쓴다. D114(종류별 문턱 · 지형 종류로 평가 칸 찾기 · 열 배치 manifest · 시작 전 메모리 · 생성 시간 · 광선 측정) · D113(JEPLO 는 실행 preset 기준 새로 짬) · AME-2 12 종 · START Fig. 4 지형을 Go2 몸 크기 실측값에 맞춰 축척 · D115(p_map_off 는 이어진 지형 조건) · D136(복원 소비 측정) · G18(밀기 칸) · EX-41 → EX-42 이어짐(부모 선택 · 단계 경계 · 무인 사슬) 을 근거를 열고 적는다. 정할 것은 표. 코드 · GPU 금지, 산출 · 임시는 D:.」

| 가정 | 내용 |
|---|---|
| 가정 0-1 | 「START Fig. 4 지형」 = START II-D3 의 네 종류(징검돌 · 평균대 · 디딤 빔 · 틈) 와 그 치수. 우리 저장소의 원문 요약은 PAPERS-architecture 표(II-D3 · Fig. 6 · Table II) 와 15-TERRAIN §4 이고, 이번에 논문 PDF 를 다시 열지는 않았다(**읽기** 등급은 그 두 문서) |
| 가정 0-2 | 「Go2 몸 크기 실측값」 = 이 기기 URDF 에서 직접 읽은 관절 원점 · 마디 길이 · 발 반지름 · 몸통 충돌 상자(§4 **실측**). 실물 줄자 측정은 없다 |
| 가정 0-3 | 「축척」 은 결정이 아니라 **후보 계산** 이다. 15-TERRAIN v1.4 §4 는 「Go2 와 Lite3 몸 크기 차이로 치수를 바꾸지 않는다(ASTRA R1-2 · 20t)」 로 닫혀 있어, 바꾸려면 팀장 결정이 필요하다(Q1) |
| 가정 0-4 | EX-42 의 시작 저장본은 EX-41 T0′ 졸업 저장본(DESIGN-EX41 §11). EX-41 은 아직 기동 전(D135 전수 점검 먼저) 이므로 여기의 회차 · 저장본 번호는 자리표시다 |
| 가정 0-5 | analyst 의 PLAN-EX42-TERRAIN-GATES v0.1(fb9cda8d, 11/02) 이 먼저 있다. 이 문서는 그것을 대체하지 않고, 겹치는 자리는 「같음 / 다름」 을 적고 다른 곳만 근거를 댄다 |

## 1. 그림 (EX-41 에서 EX-42 로)

```
EX-41 (m6000 부모 · 5,000 회 · 23 열 연속 7 종 · L0~5)
  S2a → S2b → S2c → S2d(L5) → S2e(DR 1.0) → T0′(복원 지도)
                                               │ 졸업 관문 = P7-GRADUATION-SPEC(측정 셋 n4750 · n5000 · 끝 평가 · 문턱 G1~G8 · graduation.json)
                                               ▼
EX-42 (T0′ 졸업 저장본 · 새 지형 메시 = 네 묶음 35 종을 한 번에 열로 · 노출은 env 재배정)
  S3-0 설정 경계 ─ T1 L3(연속) ─ T2 L6(연속 + 평균대 노출) ─ F1 깃발 10 % ─ T3 L9(연속 + 틈 0.3→0.6→0.8 노출)
             ─ F2 깃발 15 % ─ T4 AME-2 · JEPLO 노출 5 % ─ F3 깃발 20 % ─ T5 듬성 레벨 ─ T6 p_map_off 0.3(이어진 지형만) ─ 지형 2 판(높은 턱 · 벽 · 기어가기, h · roll 명령)
```

순서의 출처: CURRICULUM-GATES v0.6c T1 → T2 → F1 → T3 → F2 → T4 → F3 → T5 → T6 → T7 과 DESIGN-EX41 §11 의 D81 순서(L3 → L6 평균대 → L9 틈 0.3 → 0.6 → 0.8 → 지형 2 판). 둘은 「평균대 · 틈을 어디에 두나」 에서 다르다(GATES 는 T4 에 듬성 노출을 모으고, D81 은 T2 · T3 에 평균대 · 틈을 끼운다). 위 그림은 둘을 **병합한 안**이고 어느 쪽을 정본으로 할지는 Q7. **v0.2(analyst Q7)**: 순서는 제안이고 정본은 **성과 의존관계**(부모 조건 유지 확인 → 연속 지형 확대 → 넓은 평균대 · 작은 틈 노출 → 종류별 확대) 다. T1 · T2 · T3 의 L3 · L6 · L9 는 **평가 지점**이지 「부모 L0~5 학습을 L3 부터 다시 시작」 이 아니다(학습 레벨은 부모의 성과 레벨 분포를 잇는다). 틈 0.8 은 Q1 안 A 의 상한 0.7 과 **별도 승인**이다. 깃발(F1~F3) 과 어려운 지형 노출을 **같은 경계에서 함께** 늘리지 않는다(한 경계에 축 하나).

## 2. 근거 원문 (요지 · 등급 「읽기」)

| 번호 | 원문 요지 | 이 문서에서 받는 자리 |
|---|---|---|
| D113 (11/02 05:0x 팀장) | JEPLO 지형은 원본 코드를 옮기지 않고 명세를 뽑아 우리 코드로 새로 짜되 똑같이 구현 · 검증. 기준은 실행 preset | §3.3 JEPLO 7 종은 analyst SPEC-JEPLO-PRESET(CPU 420/420 일치) 의 수치를 그대로 쓴다. **Go2 축척 대상이 아니다**(JEPLO 는 Go2 코드라 치수가 이미 Go2 것) |
| D114 (11/02 팀장) | 지형 미리 넣기는 EX-42 시작 때. 종류별 승급 문턱 · 평가 칸은 지형 종류로 찾기 · 열 배치 manifest · 시작 전 메모리 · 생성 시간 · 광선 계산 측정 | §5 열 배치 · §6 승급 · §7 평가 칸 · §8 시작 전 측정 |
| D115 (11/02 팀장) | p_map_off 0.1 고정. 지도 끔 걷기는 이어진 지형에 한정해 기대(징검돌 · 틈은 아님). 레벨 관문에서 끔 생존이 정답보다 처지면 이어진 지형에서만 올림(T6 조건부) | §9 |
| D136 (11/02 15시 팀장) | 모든 실험의 학습 기록에서 복원 지도 실제 소비(use_gt_frac · 복원 스텝 > 0) 를 force_gt 끈 구간마다 재서 보고. EX-40 T0 평균 0.151 | §10 |
| W86 (논의 중) | 지형은 15-TERRAIN 50 열 + AME-2 12 종 + JEPLO 지형 + 지형 2 판(높은 턱 · 벽 · 기어가기) 를 처음부터 열로 만들고 노출은 env 재배정으로(Isaac 은 비율 0 이면 열이 안 생김 `terrain_generator.py:244~246`). 지형 판 기록 필수: 시작 때 열 배치 manifest(열 → 종류 · 레벨 식 · 해시) · 경계마다 종류별 env 수 · 레벨 분포 · 평가 칸은 env 번호가 아니라 지형 종류로(W57 terrain_tiles 방식) | §3 · §5 · §7 |
| D106 · D117 (11/02) | W86 미리 등록(보상 항 0 가중 · 명령 · 지형 열 · DR · PPO 일부 · 경고 칸) 잠정 동의. 새 미리 등록 보상: 무릎 토크 한계 근접 · 관절 한계 근접 · 발 체공 · 발 미끄럼 · 지형 따라 발 들기 | §11 EX-42 에서 가중을 여는 항은 「지형 따라 발 들기」 뿐(가정) |
| G18 (lead 16:0x · 16:30) | DR 켠 평가 칸에 밀기(명령 시작 2.0 s · 시드 고정 · Δv 기록) 와 회복 지표 넷, 지도 셋 모두, 기록 전용 | §7.4 지형 칸에도 같은 칸을 둔다(기록 전용) |
| DESIGN-EX41 §11 | 지형 판은 같은 메시(10 줄 × 23 열) 위에서 레벨 상한만 5 → 9 (가정 · 상한 올림 방식). 평균대 · 틈은 지금 메시에 없어 메시 교체 = 판 시작 경계에서만 | **다름**: D114 · W86 이 「시작 때 미리 넣기」 로 정했으므로 EX-42 시작 경계는 **메시 교체**다(§5). §11 의 「같은 메시 위 상한 올림」 은 철회 대상(Q8) |
| analyst PLAN v0.1 | 종류별 완료 정의 표(35 행) · 노출 확대 문턱 52/64 · 60/64(가정) · lookup 키 `(family, kind, level, geometry_seed, layout_sha)` · GPU1 측정 계획 | §3 **같음**(완료 정의는 그 표를 가리킴) · §6 **다름**(문턱 후보가 둘) · §5 **같음**(키) · §8 **보강**(기준 수치 · 산출 파일) |
| 15-TERRAIN v1.4 §2 · §4 | 칸 8 × 8 m · 10 레벨 · 50 열 고정 배치 · START 절대 치수 재현(치수 안 바꿈) · Go2/Lite3 축별 비율 표 | §3.1 · §4 (비율은 오늘 URDF 로 다시 쟀다) |
| SPEC-ame2-go2 §1.6 | 공식 G1 코드 지형 12 종 · 12 × 12 m · 비율 · Go2 축척 원칙(최댓값 하나만 Go2 로 · 팀장 결정) | §3.2 · §4.3 |

## 3. 지형 목록 (네 묶음 · 35 종)

### 3.1 묶음 A · 15-TERRAIN 13 종 (50 열 · 8 × 8 m · 코드에 있음)

| 종류 | 열 | 레벨 0 → 9 | 출처 |
|---|---|---|---|
| pyramid_stairs · pyramid_stairs_inv | 5 · 5 | 단 0.05 → 0.23 m · 폭 0.3 | **코드** `rough_go2_cfg.py:20~25` |
| boxes | 4 | 격자 0.45 · 높이 0.025 → 0.1 | **코드** :26~27 |
| random_rough | 4 | 잡음 0.01 → 0.06 | **코드** :28~29 |
| hf_pyramid_slope · _inv | 2 · 2 | 경사 0 → 0.4 | **코드** :30~33 |
| stage_stairs | 1 | 단 0.15 · 폭 0.3 고정 | **코드** :34~36 (STAGE_STEP_HEIGHT 0.15) |
| stepping_stones_low · high | 7 · 5 | 돌 0.5 → 0.2 · 틈 x 0.175 → 0.25 · y 0.1 → 0.175, high 는 무작위 r = L/9 | **논문**(최고값) · **선행**(범위) · 15 §4 |
| balance_beams | 5 | 두 줄 → 한 줄 폭 0.175 | **논문** · 15 §4 |
| stepping_beams | 5 | 빔 0.15 · 틈 0.275 | **논문** · 15 §4 |
| gaps | 3 | 0.1 → 0.7 m | **논문** · 15 §4 |
| flat | 2 | 보조 평지 | 15 §5 |

열 수는 `columns.FULL`(비율 × 50) 과 `terrain_generator.py:244~246` 의 누적 비율 식으로 **계산**(15 §5 와 같음). EX-40 · EX-41 은 이 가운데 이어진 7 종 23 열만 쓴다(**실측** EX-40 env.yaml num_cols 23).

### 3.2 묶음 B · AME-2 12 종 (공식 G1 preset · 12 × 12 m · 코드 없음)

| 종류 | 공식 G1 코드 최댓값 | 논문 TRON1(작은 로봇) 열 | Go2 열 |
|---|---|---|---|
| rough | 거칠기 0 → 0.16 + 경사 0 → 20° | ±0.15 | Q2 |
| stair_up · stair_down | 단 0.05 → 0.27 · 폭 0.27~0.35 | 경사 5 → 45° | Q2 |
| boxes | 0.05 → 0.3 | 0.05 → 0.3 | Q2 |
| obstacles | 밀도 0 → 0.5 · 높이 0.2~2.0 | 같음 | 밀도는 로봇 무관 |
| climb_up | 0.1 → 0.65 | 0.1 → 0.48 | Q2 |
| climb_down | 0.2 → 0.88 | 0.2 → 0.88 | Q2 |
| consecutive | 0.05 → 0.35 · 0.35 | 0.05 → 0.3 · 0.3 | Q2 |
| gap | 0.18 → 1.2 | 0.1 → 0.6 | Q2 |
| pallets | 폭 0.4 → 0.16 · 틈 0.16 → 0.24 · 높이 0 → 0.2 | 틈 0.08 → 0.2 · 높이 0 → 0.2 | Q2 |
| stones | 0.71 → 0.41 · 틈 0.08 → 0.12 | 「StonesEverywhere」 | Q2 |
| beam | 폭 0.5 → 0.17 | 폭 0.9 → 0.18 | Q2 |

출처 전부 **선행**(SPEC-ame2-go2 §1.6 표 · 그 문서가 공식 `terrains.py:14~252` 를 읽음). 비율(논문 부록 A = 코드): rough 5 · stair_down 5 · stair_up 5 · boxes 5 · obstacles 5 · climb_up 20 · climb_down 5 · consecutive 5 · gap 5 · pallets 5 · stones 30 · beam 5 %. SPEC-ame2 의 Go2 축척 원칙은 「커리큘럼 시작값은 두 로봇에서 거의 같으니 유지하고 **각 지형의 최댓값 하나** 만 Go2 로 정한다 · 논문 재현이 아니라 로봇 적응 · 선택값과 이유를 표로」 다. 값은 전부 **팀장 결정** 칸이고 이 문서는 §4.3 에 후보만 둔다.

### 3.3 묶음 C · JEPLO 7 종 (실행 preset · 9 × 9 m · CPU 코드 있음 f2ca807c)

| 종류 | 레벨 0 → 9 (d = L/9) | 출처 |
|---|---|---|
| gap | 너비 0.1 + 0.54d(0.1 → 0.64) · 깊이 U(1, 2) · 최대 6 개 | **선행** SPEC-JEPLO §2 · **코드** `jeplo_preset.py` |
| flat | 장애물 0 · 비대칭 roughness | 같음 |
| box | 단 0.1 + 0.4d 에 1 · 2 · 3 · 2 · 1 단(중앙 0.3 → 1.5 m) · 길이 U(0.8, 1.5) | 같음 |
| discrete_obstacles | 0.5 m 격자 0 … 0.1d · 회전 상자 0.4d · 크기 U(0.8, 1.25) | 같음 |
| discrete_grid | 0.5 m 격자 0 … 0.2d | 같음 |
| pyramid_stairs · inverted | 단 0.04 + 0.16d(0.04 → 0.2) · 폭 U(0.25, 0.35) · 중앙 2 m | 같음 |

9 × 9 m · 수평 0.08 · 수직 0.005 · 8 m cfg 에 연결하면 예외(**코드**). 타일 시드는 (generator seed, kind, 양자화 전 difficulty) 해시(11/02 독립 검토 반영). JEPLO 는 Go2 용 코드(ASIG-X/JEPLO `go2_parkour`) 라 **Go2 축척을 하지 않는다**(가정 · D113 「똑같이」). box 중앙 1.5 m 는 Go2 가 「넘는」 지형이 아니라 「돌아가거나 오르다 실패하는」 지형일 수 있다. 완료 정의는 analyst 표(「중앙 최고점 통과 뒤 끝」) 를 따르되 우회 경로 분리 기록.

### 3.4 묶음 D · 지형 2 판 3 종 (코드 없음 · D82 h · roll 명령과 짝)

| 종류 | 난이도 축 | 메모 |
|---|---|---|
| high_ledge(높은 턱) | 턱 높이 · 착지면 폭 | Δh 명령 [−0.22, +0.08] · roll [−1, 1](DESIGN-EX41 §11 h · roll 칸 · SPEC :111~112) 과 같은 경계에서 연다 |
| wall(벽) | 높이 · 폭 · 우회 통로 | 넘을 수 없는 벽을 등반 목표로 주지 않는다(analyst 표 같음) |
| crawl(기어가기) | 천장 여유 · 길이 | 천장이 있는 칸은 위에서 내려 쏘는 height_scanner 가 천장을 지면으로 읽는다(**코드** height_scanner 원점 z 20 m · 방향 −z, EX-40 env.yaml :351~380). 지형 2 판 전에 센서 처리(마스크 · 두 번째 히트) 가 필요 → Q12 |

치수는 이번에 정하지 않는다(지형 2 판은 EX-42 마지막 단계이고 h · roll 명령 설계와 함께). 열은 시작 때 만들되 노출 0.

## 4. Go2 몸 크기 실측과 START 치수의 축척 후보

### 4.1 실측 (URDF · 오늘 11/02 읽음)

| 항목 | Go2 (`go2_rl_robotlab/resources/go2/urdf/go2.urdf`, sha256 f130b1d2…) | Lite3 (`MGDP/…/all_dog/lite3/urdf/lite3.urdf`, f5e5003d…) | 비 Go2/Lite3 | 등급 |
|---|---|---|---|---|
| hip 관절 원점 x · y | ±0.1934 · ±0.0465 | ±0.1745 · ±0.062 | 앞뒤 간격 0.3868 / 0.349 = **1.108** | **실측** |
| thigh 관절 y 오프셋 | 0.0955 | 0.0985 | 좌우 thigh 축 간격 0.284 / 0.321 = **0.885** | **실측** |
| thigh · calf 길이 | 0.213 · 0.213 (합 0.426) | 0.20 · 0.20 (합 0.40) | **1.065** | **실측** |
| 발 충돌 구 반지름 | 0.022 (지름 0.044) | 0.04 (지름 0.08) | **0.55** | **실측** |
| 몸통 충돌 상자 | 0.3762 × 0.0935 × 0.114 | (상자 0.234 × 0.184 × 0.08, 몸통 분할 모델) | 비교 불가(모델 꼴 다름) | **실측** |
| URDF 질량 합 | 16.087 kg (15-TERRAIN 이 쓴 MGDP go2 자산은 16.142 · 학습 USD 15.019) | 9.038 kg | **1.78** | **실측**(합) · **선행**(괄호) |
| 서 있는 전체 크기(제원) | 700 × 310 × 400 mm · 15 kg | 610 × 370 × 406 mm(Basic) · 12 kg | 길이 **1.148** · 폭 **0.838** | **웹**(아래 출처) |

15-TERRAIN §4 의 비율 표(1.108 · 1.065 · 0.885 · 0.55 · 1.79) 와 오늘 실측이 같다(질량만 자산 차이). 웹 제원 출처: Lite3 [deeprobotics.cn 제품면](https://deeprobotics.cn/en/wap/product1.html) · [Wellbots Lite 3 Venture](https://www.wellbots.com/products/deep-robotics-lite-3-venture) · [RobotShop Lite3 Basic](https://ca.robotshop.com/products/deep-robotics-lite3-basic-quadruped-robot); Go2 [iFixit Go2](https://www.ifixit.com/Device/Unitree_Go2) · [RobotLAB Go2](https://www.robotlab.com/?p=14223) · [Elektor Go2 Pro](https://elektor.fr/products/unitree-go2-pro-quadruped-robot). 판매처마다 높이 · 무게가 조금 다르다(Lite3 높이 406~496 mm 변종별 · Go2 Air 18 kg 표기 한 곳).

### 4.2 START Fig. 4 네 지형: 두 안

| 치수 (START 최고 난이도) | 안 A · START 절대 치수 그대로(15-TERRAIN v1.4 결정) | 안 B · Go2 축척(**계산**: 길이 축 × 1.108 · 폭 축 × 0.885 · 높이 그대로) | 축 근거 |
|---|---|---|---|
| 징검돌 변 0.2 m | 0.2 | 0.18(폭 축) 또는 0.22(길이 축) | 돌은 발 디딤 면이라 발 지름 비 0.55 로 줄이면 0.11(너무 과격 · Go2 발이 작아 상대 여유는 이미 큼) |
| 틈 x 0.25 · y 0.175 | 0.25 · 0.175 | 0.28 · 0.155 | 틈 x 는 보폭(hip 간격) · y 는 좌우 발 간격 |
| 평균대 0.175 | 0.175 | 0.155 | 좌우 thigh 축 간격 비 0.885 |
| 디딤 빔 폭 0.15 · 틈 0.275 | 0.15 · 0.275 | 0.133 · 0.305 | 폭은 좌우 · 틈은 보폭 |
| 틈(gap) 0.7 | 0.7 | 0.78(hip 간격) ~ 0.80(전체 길이) | START 실기 Table II: 0.7 m 성공 1.0(5 회) |
| 깊이 U[0.2, 0.7] · 돌 높이 ±5 cm | 그대로 | 그대로(다리 길이 비 1.065 는 10 % 안) | |
| 무작위 ±0.5 · ±0.45 × 틈 | 그대로(틈에 비례) | 그대로 | |

읽는 법. 안 A 는 「같은 치수가 두 로봇에 같은 상대 난이도」 라고 주장하지 않고(15 §4 판단 보류), 결과를 축별 비율로 읽는다. 안 B 는 Go2 의 걸음 기하에 맞춘 **로봇 적응** 이라 START 수치와의 대조는 끊긴다. 두 안의 차이는 틈 길이 10 % · 폭 12~15 % 이고, 발 지름 비(0.55) 만 크게 다른데 그것은 축척에 쓰지 않았다(돌 0.11 m 는 START 수준 밖). **planner 의견**: 안 A 를 학습 열로 유지하고(결정 번복 없음 · 50 열 코드 그대로), 안 B 의 틈 0.78 · 평균대 0.155 · 빔 0.133 세 종류를 **평가 전용 칸**(노출 0 열) 으로 더해 「Go2 에 맞춘 치수에서의 성과」 를 따로 적는다. 결정은 Q1. **v0.2(analyst Q1 조건부 동의)**: 축척판은 **별도 이름의 민감도 평가**로 두고 「Go2 적정 치수」 라고 확정하지 않는다(몸 길이 비율이 같은 상대 난이도를 보증하지 않음). 평가 전용은 학습 노출 0 과 분리 평가 배치를 manifest 로 증명하고, A 0.7 m 와 B 0.78~0.80 m 의 성과를 한 칸에 합치지 않는다.

### 4.3 AME-2 12 종 Go2 열 후보 (SPEC-ame2 원칙 「최댓값 하나만」)

| 후보 | 내용 | 장점 | 단점 |
|---|---|---|---|
| B-1 TRON1 열 | 논문의 작은 로봇 열 그대로(climb_up 0.48 · gap 0.6 · boxes 0.3 · consecutive 0.3 · pallets 틈 0.2) | 논문 안의 값 · 한 번에 정해짐 | TRON1 은 이족 · 키가 Go2 보다 큼 → climb_up 0.48 은 Go2 서 있는 높이 0.40 보다 높다 |
| B-2 Go2 **임시 시험 범위**(v0.2 이름 바꿈, 옛 「기하 상한」) | climb_up · consecutive 를 0.40(제원) × 0.8 = 0.32 · climb_down 0.6 · gap START 0.7(또는 안 B 0.78) 부터 **낮은 레벨에서 점검할 후보** · 나머지 TRON1 | 시작 범위가 좁아 낮은 레벨부터 실측으로 넓힐 수 있음 | 0.8 배는 **가정**. 정적 몸높이만으로 동적 통과 가능 · 불가능을 보증하지 못하므로 「못 넘을 값을 안 넣음」 이라고 주장하지 않는다(analyst Q2). 실기 Go2 의 최대 단 높이는 제원에 없다(미확인) |
| B-3 G1 코드 열 | 공식 preset 그대로 | 코드 재현 · 원본 보존 | G1 은 키 1.3 m 급이라 Go2 와 체급이 다르다(값의 뜻은 실측 전에 단정하지 않음) |

planner 의견: B-2 로 시작하고 최댓값을 **표로 원장에**(SPEC-ame2 원칙). 결정은 Q2. **v0.2(analyst Q2)**: TRON1 값을 일괄 채택하지 않고 **12 종 각각** 「원본 preset 값 · Go2 후보 · 레벨별 실측」 세 칸으로 나눠 적는다. 원본 preset 이름과 변경판 이름을 manifest `families[].kind_variant` 로 보존한다.

## 5. 열 배치 manifest 와 칸 크기 (D114 · W86)

### 5.1 세 묶음의 칸 크기가 다르다

| 묶음 | 칸 | 생성기 |
|---|---|---|
| A 15-TERRAIN | 8 × 8 m · 수평 0.1 · 수직 0.005 · 10 줄 | `rough_go2_cfg.build_generator` (use_cache False) |
| B AME-2 | 12 × 12 m · 수평 0.1 · 수직 0.005 · 10 줄 × 60 열(공식) | 없음(새로) |
| C JEPLO | 9 × 9 m · 수평 0.08 · 수직 0.005 · 10 줄 | `jeplo_preset`(9 m 아니면 거절) |
| D 지형 2 판 | 미정 | 없음 |

Isaac `TerrainGeneratorCfg.size` 는 생성기 하나에 하나다(**코드**). 그래서 세 안:

| 안 | 내용 | 장단점 |
|---|---|---|
| (가) 모두 8 m 로 다시 맞춤 | AME-2 · JEPLO 를 8 m 칸에 다시 그림 | 생성기 하나 · 코드 작음 / **치수가 바뀐다**(analyst: 「12 m 를 8 m 로 축소하면 같은 치수가 아님」 · JEPLO adapter 는 8 m 를 거절) → D113 「똑같이」 위반 |
| (나) 공통 12 m 껍질에 작은 칸을 넣음 | 8 · 9 m 무늬를 12 m 칸 가운데 두고 둘레를 그 묶음의 바닥으로 채움 | 생성기 하나 / 둘레 평지 · 목표 거리 · 승급 거리(4 m) 의 뜻이 바뀜(analyst 도 「별도 결정 없이 하지 않음」) |
| (다) 묶음별 독립 생성기를 한 메시로 합침(**추천**) | 생성기 셋(8 · 12 · 9 m) 을 따로 돌려 메시를 x 방향으로 이어 붙이고, `terrain_origins` 를 (10 줄, 전체 열) 로 **연결**(열마다 폭이 달라도 원점 텐서는 명시값이라 `update_env_origins` · `terrain_origins[level, type]` 가 그대로 동작) | 치수 보존 · 묶음별 캐시 · manifest 가 자연스러움 / Isaac `TerrainImporter` 가 생성기 하나만 받으므로 **우리 importer 어댑터**가 필요(W86 코드 · CPU 로 원점 · 경계 · 겹침 없음을 먼저 증명) |

(다) 가 analyst 의 「family 별 독립 layout 우선」 과 같다. 결정은 Q3.

### 5.2 manifest 꼴 (시작 때 한 번 · 경계마다 분포 덧붙임)

이미 있는 키를 넓힌다(**코드** 실측 m6000 map_modes.json 의 `terrain_columns` · `terrain_hash` · `terrain_tiles[{env, kind, level, col}]` · `fixed_terrain.assignment_sha256`):

| 칸 | 내용 |
|---|---|
| `format` | `foothold-terrain-manifest/1` |
| `families[]` | 묶음마다 `{name, tile_size_m, h_scale, v_scale, rows, cols, generator_sha(코드 파일 sha256), seed, origin_offset_xy}` |
| `columns[]` | 전역 열마다 `{col, family, kind, level_formula(d = L/9 또는 (L+U)/10), physical_dims_by_level{L0, L5, L9}, mesh_sha256, cache_hit, flags(깃발 열 좌표), goal_surfaces(출발 · 마지막 지지면)}` |
| `sensors` | 접촉 메시 · height_scanner · depth_cam 이 읽는 mesh prim 경로가 **같은** 메시인지(불일치면 거절) |
| `exposure_schedule` | 단계마다 묶음 · 종류별 env 몫(§6) |
| `boundary_log[]` | 경계마다 `{iteration, env_count_by_kind, level_hist_by_kind, success/fail/invalid by (family, kind, level, dir, map_mode), use_gt_frac_by_family}` |
| `receipts` | §8 의 생성 시간 · 메모리 · 광선 영수증 파일 경로와 sha |

lookup 키는 analyst 와 같게 `(family, kind, level, geometry_seed, layout_sha)` 이고 `env_id` 는 그 순간의 배정 결과일 뿐이다. reset 뒤 `env → (kind, level, row, col)` 이 실제 `terrain_origins` 와 일치하는지 매 경계 확인(W57 이 이미 `terrain_tiles` 대조를 한다, `axis_v2_run.py:180~200`).

## 6. 종류별 승급 문턱 (D114) · 두 층

| 층 | 무엇 | 지금 코드 | EX-42 안 |
|---|---|---|---|
| ① env 레벨 승급 · 강등 | env 하나가 에피소드 끝에 L±1 | 자유 속도: `rules.judge_free`(이동 > 4 m 승급 · < 0.5 × ‖Σcmd‖ × 4 s × 0.9 강등) · 깃발: `judge_flag`(깃발 전부 / 절반 미만) · 정지 · 회전 제외(14 §5) · EX-41 S2d 부터 켬(상한 L5) | 그대로 두되 **종류별 완료 정의**(analyst §2 표 35 행: 끝 구간 도달 + 마지막 지지면 0.5 s 생존, 0.5 s · 목표 오차 0.3 m 는 가정) 로 「이동 거리」 를 바꾼다. 평면 변위 4 m 는 12 m 칸(AME-2) 에서 뜻이 다르므로 **칸 길이의 절반** 으로 식을 둔다(Isaac 기본 `size[0]/2` 와 같은 꼴, **코드** `curriculums.py:47~51`) |
| ② 종류 노출 확대 | 어떤 종류 · 다음 레벨을 env 몇 % 에 줄지 | 듬성 재배정은 `progression.p_advance(T)` = **회차 기반**(1b.7 · T_start 1,000 · T_end 8,000 · p_max 0.9) · EX-41 은 `terrain.policy fixed_l02 · level_cap` 만 | p_advance 의 입력을 회차가 아니라 **그 종류의 성과 창** 으로(W55 · 1b.7 결론). 창 = 같은 `(family, kind, level, dir, map_mode)` 의 독립 종료 에피소드 ≥ 64 |

노출 확대 문턱의 후보(둘 다 문서에 이미 있음):

| 후보 | 값 | 출처 |
|---|---|---|
| T4 행(CURRICULUM-GATES v0.6c) | 고정 칸 과제 ≥ 48/64 · 생존 ≥ 54/64 · 종류별 추세(D12) | **읽기**(가정 표시됨) |
| analyst PLAN §1 | 성공 ≥ 52/64(81.25 %) · 생존 ≥ 60/64 · 같은 조건 두 창 연속 · 노출 새 10 % / 현재 70 % / 쉬움 20 %, 통과 뒤 새 20 %, 실패 시 5 % | **읽기**(가정 표시됨) |

planner 의견: 문턱은 **반복 폭 실측 뒤** 결과 전에 고정(둘 다 가정). 단계 안에서는 analyst 의 노출 비율(10 / 70 / 20) 을 쓰고, 묶음을 **여는** 순간(T2 평균대 · T3 틈 · T4 AME-2 · JEPLO) 은 CURRICULUM-GATES 의 「지형 열 듬성 0 → 5 %(연속 ≥ 20 % 유지)」 대로 5 % 부터. 결정은 Q4 · Q5. 성과 창의 분모에서 정지 · 회전 명령과 `invalid`(목표 없음 · 기록 누락) 는 빼고 수를 남긴다(analyst 같음). **v0.2(analyst Q4)**: 창마다 종료 에피소드 ID · 지형 seed · 방향 · 지도 모드를 기록하고, `invalid` 때문에 분모가 64 에 모자라면 그 창으로는 노출을 **확대하지 않는다**. 「칸 길이의 절반 이동」 만으로 계단 · 틈의 완료를 대신하지 않는다(마지막 지지면 도달 · 장애물 통과를 먼저 확인, analyst 완료 정의 표). 문턱은 반복 폭 실측 뒤 결과 전에 고정.

## 7. 평가 칸은 지형 종류로 (D114)

### 7.1 지금 있는 것(**코드**)

- `eval_map_modes --terrain-set sparse50`: 50 열 생성기로 바꾸고 `fixed_terrain.apply_sparse(raw, level)` 가 **종류 이름** 으로 열을 골라 env 를 배정하고 `terrain_tiles[{env, kind, level, col}]` · `assignment_sha256` 을 적는다. 기본 `fixed_assignment` 는 `env 번호 % 열 수` 라 EX-42 에서 쓰면 안 된다(analyst 같음).
- `map_mode_cells.terrain_rows(levels, types, names)` 가 점수 행에 `by_kind` · `by_kind_level` 을 만든다(실측 m6000 점수 행 키에 있음).
- W57 `axis_v2_run.py:180~200`: reset 뒤 `terrain_tiles` 수 = env 수, 시작 위치가 자기 원점 0.5 m 안, 다음 명령에서 tiles 가 바뀌면 오류.

### 7.2 EX-42 평가 사다리(가정 · 칸 수는 analyst 와 lead 가 정함)

| 칸 | 내용 | 자리 |
|---|---|---|
| 기준 축 | W15 13 명령 L0~2 · 64 env · 지도 3 모드(그대로) | 모든 정본(FLOW §3) |
| 고정 레벨 | W78 v2 고정 L3(T1) · L6(T2) · L9(T3) · 네 방향 | §11 그대로 |
| D44 칸 | 계단참 제자리 회전 좌 · 우 · 계단 중간 정지 → 재출발(W48 이 치수 정함) | T1 부터(1b.6) |
| 종류별 칸 | 묶음 · 종류마다 대표 레벨(L0 · L5 · L9 가운데 노출된 것) × 전진 1.0 · 지도 3 모드 → `(family, kind, level)` 로 찾음 · 열 배치가 바뀌어도 같은 물리 지형 | 새 `--terrain-set ex42 --kinds …`(W86) |
| DR 켠 · 밀기 칸(G18) | d5c14948 의 `--dr-mode on --dr-scale 1.0`: 지형 칸에서도 밀기 2.0 s · 지표 넷 · `push_cells` · 기록 전용 | 유지 판정 소비자는 `require_dr_off_document` 로 켠 문서를 거절(B2) |
| 깃발 도달 | F1 부터 W09 기준선 뒤 고정 | W60 |
| 회전 전환 · 걸으며 돌기(**D151**) | EX-41 에서 16 env 진단(W91, 기록 전용) 으로만 잰 「전진 → 회전 전환 · 걸으며 돌기」 를 EX-42 **시작 경계**에서 W57 `case_specs` 64 env 칸으로 넣는다(W57 묶음 판 번호가 올라가므로 판 안에서는 불가, `U18-TURN-SIX-CASES-VS-W57.md` §5 「옮기기」) | S3-0 시작 경계 · W57 |

유지 판정은 **정답 · 끔 26 칸**이고 복원 13 칸은 기록이며 39 숫자를 모두 남긴다(D133 · **코드** `ex41-fixed5000.yaml` `include_record_only: false` · `ex41_fixed.CELLS[:26]`; v0.1 의 「39 칸 판정」 은 틀림, analyst Q6 정정). EX-42 에서도 그 26 칸은 연속 7 종 L0~2 기준 축 그대로 둔다. 종류별 칸은 **처음엔 기록**(추세 D12) 이되, 그 종류의 **노출을 확대하는 순간에는 필수 성과 관문**이다(§6 ②). EX-42 시작 때 새 부모(EX-41 졸업본)의 **같은 평가 배치 · 기준표 SHA** 를 먼저 고정한다(유지 기준선 = 졸업본 점수, EX-41 의 `maintenance_baseline` 꼴). 결정은 Q6.

## 8. 시작 전 측정 (D114: 메모리 · 생성 시간 · 광선) · 승인 뒤 새 프로세스

기준값(**실측** EX-40 env.yaml · 코드): env 3,072 · 23 열 × 10 줄 × 8 m(14,720 m²) · use_cache False(시작마다 생성) · height_scanner 격자 0.1 m × [1.6, 1.0] = 17 × 11 = **187 광선/env**, 주기 0.02 s · depth_cam 60 × 60 = **3,600 광선/env**, 주기 0.1 s → 초당 광선 ≈ 3,072 × (187 × 50 + 3,600 × 10) ≈ **1.39 × 10⁸ /s**(**계산**). EX-42 메시 넓이(열 수 가정 §5: A 50 열 8 m + B 12 열 12 m + C 7 열 9 m + D 3 열 8 m, 10 줄) = 32,000 + 17,280 + 5,670 + 1,920 = **56,870 m²** ≈ EX-40 의 3.9 배(**계산**). EX-40 의 GPU 메모리 · 생성 시간은 저장소 문서에서 숫자를 찾지 못했다(**미확인** · 사슬 로그에 있으면 lead 가 지정).

| 단계 | 재는 것 | 조건 | 산출 |
|---|---|---|---|
| M0 CPU | 묶음 · 종류 · L0/L5/L9 의 치수 · 삼각형 수 · 높이장 · metadata · 전역 열 표 | GPU 없음 | `terrain_manifest.json`(§5.2) · 알려진 답 시험(JEPLO 420 경우는 이미 있음) |
| M1 생성 시간 | 묶음별 생성기 벽시계 · CPU RSS · use_cache True/False 두 번(캐시 적중) | GPU1 · env 0(생성만) | `receipt_terrain_gen.json` |
| M2 업로드 · 메모리 | 접촉 메시 · 광선 메시 업로드 뒤 GPU allocated · reserved · 최대, 128 → 512 → 3,072 env(앞 크기에서 여유 확인 뒤만) · 4,096 은 별도 요청 | GPU1 · 학습 없음 · PPO update 없음 | `receipt_terrain_mem.json` |
| M3 광선 | height_scanner · depth_cam 따로 · 합쳐서, warmup 20 뒤 100 회, CUDA event 동기화, 평균 · p50 · p95 · 최대, reset 포함 / 제외, cold / warm | 같음 | `receipt_rays.json` |
| 중단선 | 여유 < 2 GiB 면 그 크기에서 멈추고 다음 크기를 안 띄움(analyst 2 GiB · **가정** · lead 승인 전 고정 안 함) | | |

GPU1 이 비었다는 관측만으로 실행 권한이 생기지 않는다(analyst 같음 · 이 문서도 GPU 금지). 결정은 Q9(범위 · 예산). **v0.2(analyst Q9)**: 위 기준값 1.39 × 10⁸ /s 는 height_scanner 187 + depth_cam 3,600 만 센 것이고, analyst 읽기로는 `sensors/start_obs.py:84~99` 의 정답 지도 512 · 발 100 광선이 더 있다(**미재측** · M3 에서 센서마다 실제 활성 여부 · 주기 · lazy 호출을 같이 잰다). 측정은 기존 lead 조건(GPU1 그림자 · axis250 · stage_loop2 · 미채점 저장본)에 양보하고 **한 번 10 분 이내**를 예산에 명시한다. 총예산은 생성 실측 전 미확정. 2 GiB 는 보장값이 아니라 **후보 중단선**이다.

## 9. D115 · p_map_off 는 이어진 지형 조건

지금 코드: `start_runner.py:86` `p_map_off` 는 **env 공통 스칼라**로, reset 때 env 마다 그 확률로 「지도 끔」 을 뽑아 에피소드 끝까지 유지한다(:146). 평가는 `adapters.py:495` 가 0 으로 둔다. D115 는 「지도 끔 걷기는 이어진 지형에 한정」 이므로 EX-42 는:

| 항목 | 안 |
|---|---|
| 적용 집단 | 끔 추첨은 **이어진 묶음(A 의 연속 7 종) env 만**. 듬성(START 4 종 · AME-2 희소 4 종 gap · pallets · stones · beam · JEPLO gap) · 지형 2 판 env 는 p_off 0(가정: 「징검돌 · 틈은 아님」 을 묶음 태그로 적용 · `s2_layout.group_of` 꼴의 집단 태그로 판정, 열 이름 역산 금지) |
| 구현 자리 | `p_map_off` 를 env 별 마스크로(집단 태그 × 스칼라) → W86 미리 등록 · EX-42 시작 경계(막는 칸 아님 · 「열되 경고」) |
| T6 조건부 | 레벨 관문에서 끔 생존이 정답보다 처지면 **이어진 지형에서만** 0.1 → 0.3. 판정 칸 = 연속 7 종 고정 레벨 칸의 끔 생존(§7.2) |
| 기록 | 경계마다 집단별 실제 끔 비율(추첨 결과) · 끔 env 의 생존 · 오차 |

## 10. D136 · 복원 지도 실제 소비

EX-42 는 T0′ 뒤라 **전 구간 force_gt False**(`map_input reconstruction`, EX-41 T0_prime 행과 같음). 소비 기록은 이미 있다(**코드** `runners/map_stats.py`: 회차마다 `map_stats.jsonl` 에 `use_gt_frac` · `gt_missed_frac` 등). EX-40 T0 의 0.151(7501~8000 평균, EX41-LAUNCH-GAPS :71) 이 기준점이다. EX-42 에서 더할 것:

| 항목 | 안 |
|---|---|
| 묶음별 분리 | `use_gt_frac` 를 전체 평균만이 아니라 **집단 태그별**(이어진 · 듬성 · AME-2 · JEPLO) 로(복원이 어려운 지형에서 AdaSmpl 이 정답 지도로 더 자주 바꿔 넣는지가 물음) |
| 경계 보고 | 경계마다 집단별 평균 · 복원 스텝 수 > 0 확인 · 0.151 과 나란히 |
| 판정 | 기록 전용(D133 의 뜻과 같음). 집단 평균이 0.3 을 넘으면 **경고**(가정 · 「약 85 % 복원」 이 70 % 아래로 떨어진 신호) → Q10 |

## 11. G18 밀기 · DR · 보상 (EX-42 에서 바뀌지 않는 것과 바뀌는 것)

| 항목 | EX-42 |
|---|---|
| DR | **부모의 실제 배율을 인계**(EX-41 끝값은 1.0 이 목표지만 `ex41_fixed.py` 의 유지 상한 소진 경로에서는 1.0 미만으로 끝날 수 있음 · analyst Q11). 1.0 미만이면 추가 상승은 EX-42 안에서 따로 결정 · 유지 판정 26 칸 · 기록 39(D130 · D133) · 밀기 간격 10~15 s 학습 그대로 |
| 평가 밀기 칸 | §7.2 의 DR 켠 칸을 지형 칸에도(기록 전용 · `push_cells`) |
| 보상 | 기존 유지 항 그대로(D117 정정: stumble · collision · smoothness · joint_power 는 이미 켜짐). **v0.2**: v0.1 의 「시작 경계에서 지형 따라 발 들기를 새로 켬」 은 **삭제**. 발 높이 비용 `swing` 은 EX-41 S2-0 부터 이미 켜져 있고(**코드** `ex41-fixed5000.yaml:98` swing −10 · D123) 서 있기 복원으로 한 번 반감될 수 있으므로(D130), EX-42 는 **부모의 실제 가중(반감 이력 포함)을 계승**하고 S3-0 에서 보상 가중을 바꾸지 않는다. D117 의 미리 등록 항은 0 가중 등록만 |
| 명령 | 13 슬롯 몫 고정(§11 「T1 은 명령 몫을 바꾸지 않음」) · 깃발 슬롯 14 는 시작 경계에서 몫 0 으로 등록, F1 에서 10 %(D52 · W60) · h · roll 0 고정, 지형 2 판 경계에서 염 |

## 12. EX-41 → EX-42 이어짐

| 항목 | 규칙 | 출처 |
|---|---|---|
| 부모 선택 | EX-41 **T0′ 졸업 저장본** = `P7-GRADUATION-SPEC.md`(53fda76c) 의 판정기가 `graduation.json` 에 `graduated True` 로 적은 끝 저장본(측정 셋 n4750 · n5000 경계 · 끝 평가, 문턱 G1~G8). v0.1 의 「연속 3 저장본」 은 yaw(G5) 에만 남는다. sha256 · update 번호를 EX-42 표(yaml) 의 `parent_sha256` · `parent_update` 에 박고 preflight 가 `graduation.json` 의 `spec_sha256` 과 함께 대조(EX-41 `ex41_start_preflight.verify_parent_checkpoint` 꼴) | P7 정본 · DESIGN-EX41 §4 · §11 · D124 · D135 |
| T0′ 미달이면 | EX-42 를 시작하지 않는다(**기본안 · analyst Q11 동의**). 먼저 같은 평가 파일에서 미달이 생존 · 추종 · yaw · 서 있기 · 복원 소비 가운데 어느 줄인지 분리한다. 보완이 필요하면 기존 지형에서 **별도 승인한** 복원 보완 구간을 둔다. S2e +500 연장은 T0′ 앞 구간이라 T0′ 미달의 자동 재시도 규칙이 아니다. DR 배율 < 1.0 으로 끝났으면 졸업이 아니라 「DR 미완 보고」 (P7 G8) | P7 §5 · Q11 |
| 설정 표 | `foothold-ex42-curriculum/1`(EX-41 표 꼴 그대로: `start: transfer` · `promotion: fixed` · `boundary_file` · `approval_file` · `fixed_schedule`) + 단계 행에 `terrain: {policy: ex42, level_cap, exposure: {family: {kind: share}}}` 와 `terrain_manifest_sha256`. 파서(`ex41.py:121` 는 `terrain` 키 안의 꼴을 안 본다) 는 W86 에서 `exposure` 를 받게 넓힘 | **코드** `ex41-fixed5000.yaml` · `ex41.py` |
| 단계 경계 | W72 방식(끊지 않고 경계에서만 설정 다시 읽음 · 막는 칸 목록 · 승인 줄 대조). **지형 메시는 막는 칸**(판 시작 경계 S3-0 에서만 교체 · 판 안에서는 노출 몫 · 레벨 상한만 바뀜) → §11 Q17 의 답을 「막는 칸」 으로 | W72 · DESIGN-EX41 Q17 |
| 무인 사슬 | EX-41 과 같은 셋: `ex41_start_preflight`(읽기 전용 · 부모 sha · 인자 · 소스) → 감독기(`ex40_supervisor` 꼴: 저장본 확인 · 구간 평가 소비 · 결정 영수증 · 프로세스 안 죽임) → 점수기(`ex41_score` 꼴 · 39 칸 + 종류별 칸). 더할 것: **지형 manifest 검사**(§5.2 sha · 센서 메시 일치 · §8 영수증 존재) 를 preflight 에, 경계마다 manifest `boundary_log` 덧붙임 | **코드** 세 파일 · D135 |
| 자동 기동 | **없다**(**D146**, 11/02 20:2x 팀장). EX-41 졸업 판정(P7 · D143) 이 나오면 그때 묻는다 · 결과가 매우 유의미하면 텔레그램. 진입 목표는 **11/5 06:00 이전**(**D148**) · END_BY 는 M77 그대로. 위 「T0′ 미달이면」 과 같이 사람이 여는 경계이고, 기동 전 전수 점검(D135) · 사본 · 산출 D:(D138) 규칙은 EX-41 과 같다 | WORKLIST 11fdb8e4 174 · 176 행 · D135 · D138 |
| 회차 | 미정. EX-41 과 같은 「250 점검 시각 · 단계별 최대 예산 · 연장 횟수를 **사전 고정**」 꼴을 추천 → Q13. **v0.2(analyst Q13)**: 회차가 찼다는 이유로 새 지형 · 레벨 노출을 **확대하지 않는다**(노출 확대는 §6 ② 성과로만). 기준 미달이면 같은 조건 유지 · 등록된 연장 · 보고로 남기고 졸업과 구분한다. 「500~1,000 × 7~9 = 3,500~9,000 회」 는 산술 범위일 뿐 학습량의 근거가 아니다. 전환 입력 · 결정 · 설정 SHA 를 경계마다 남겨 재현 | D126 꼴 · analyst Q13 |
| 앞 일 관문 | `worklist_gate.py W59`(11/02 17:44 실행, lead_tmp e187590b): 앞 일 W55 「끝」 이나 증거 경로 `v7/v8` 가 MISSING_PATH 라 **막음** 표시. EX-42 카드를 쓰기 전에 WORKLIST W55 상태 칸의 증거 경로를 고쳐야 한다(lead) | **실측**(도구 출력) |

## 13. 정할 것 (표)

| 번호 | 물음 | 후보 | planner 의견 | 정하는 사람 |
|---|---|---|---|---|
| Q1 | START 네 지형 치수: 절대 치수(15 v1.4) 대 Go2 축척(§4.2) | A 그대로 / B 축척 / A 학습 + B 평가 전용 3 종 | A + B 평가 전용(결정 번복 없이 Go2 수치도 얻음) | 팀장 |
| Q2 | AME-2 12 종 Go2 최댓값 | B-1 TRON1 / B-2 Go2 기하 상한(0.32 · 0.6 · 0.7) / B-3 G1 코드 | B-2, 값은 원장 표로 | 팀장 |
| Q3 | 칸 크기 다른 세 묶음의 배치 | (가) 8 m 재맞춤 / (나) 12 m 껍질 / (다) 독립 생성기 합침 | (다) · CPU 증명 먼저 | lead |
| Q4 | 종류 노출 확대 문턱 | 48/64 · 54/64(T4 행) / 52/64 · 60/64 두 창(analyst) | 반복 폭 실측 뒤 고정 · 그 전엔 analyst 값을 가정으로 | lead → 팀장 |
| Q5 | 노출 비율 | 10 / 70 / 20 → 20 / 60 / 20(analyst) / 묶음 여는 순간 5 % | 여는 순간 5 %(GATES T4) · 그 뒤 analyst 비율 | lead |
| Q6 | 유지 판정 26 칸(정답 · 끔, 복원 13 은 기록 · 39 숫자 보존) 을 EX-42 에서도 연속 7 종 L0~2 로 둘지 | 그대로 / 종류별 칸 일부 편입 | 그대로 · 종류별 칸은 기록이되 노출 확대 순간엔 필수 관문 · 새 부모 기준표 SHA 먼저 고정(analyst Q6 반영) | 팀장 |
| Q7 | 단계 순서의 정본 | GATES v0.6c T 행 / D81(§11) / 병합(§1 그림) | 병합안은 제안, 정본은 성과 의존관계(§1 v0.2) · L3/6/9 는 평가 지점 · 틈 0.8 별도 승인 · 깃발과 지형을 같은 경계에 안 묶음 | 팀장 |
| Q8 | DESIGN-EX41 §11 의 「같은 메시 위 상한 올림」 철회 | 철회(시작 경계 메시 교체) / 유지 | 철회(D114 · W86 이 뒤에 정해짐) | lead |
| Q9 | §8 측정 범위 · GPU1 예산 | M0 만 / M0~M3 / 4,096 포함 | M0~M3, 4,096 은 별도 | lead → 팀장 |
| Q10 | 복원 소비 경고선 | 없음 / 0.3 / 묶음별 다르게 | 0.3 경고(기록 전용) | lead |
| Q11 | T0′ 미달 때 | 시작 안 함 / 복원 구간을 EX-42 첫 단계로 | 시작 안 함(기본, analyst 동의) · 미달 줄 분리 · 보완은 별도 승인 카드 · 판정은 P7 정본(P7-1~P7-7 은 그쪽 표) | 팀장 |
| Q12 | crawl(천장) 의 센서 처리 | 두 번째 히트 / 마스크 / 지형 2 판까지 보류 | 보류 · 지형 2 판 카드에서 | lead |
| Q13 | EX-42 회차 · 단계 길이 | 점검 시각 · 예산 · 연장 수 사전 고정 / 성과 승급 | 사전 고정(D126 꼴) + 노출 확대는 성과로만(회차 찼다고 안 넓힘, analyst Q13) | 팀장 |
| Q14 | ~~지형 따라 발 들기 보상의 가중 여는 시점~~ | (v0.2 닫힘 후보) | swing 은 이미 켜져 있어(YAML :98 −10) 「새로 켬」 이 없다. 부모의 실제 가중(반감 이력 포함) 계승. lead 확인만 | lead |

### 13b. analyst OPINION-EX42-Q-1102(11/02 18:05) 반영 표 (v0.2)

| Q | analyst 의견 요지 | 반영 자리 | 남은 차이 |
|---|---|---|---|
| Q1 | 조건부 동의: A 학습 + B 평가 전용. 축척판은 별도 이름의 민감도 평가 · 「Go2 적정 치수」 확정 금지 · 학습 노출 0 과 분리 배치 검증 · A 0.7 과 B 0.78~0.80 성과 안 합침 | §4.2 끝 | 없음(팀장 결정 대기) |
| Q2 | B-2 는 임시 시험 범위이지 기하 상한이 아님. 「못 넘을 값을 안 넣음」 · 「1.2 m 는 뜻 없음」 삭제. 12 종 각각 원본 · Go2 후보 · 레벨별 실측 분리 · 이름 보존 | §4.3 표 · 문단 | 없음 |
| Q4 | 52/64 · 60/64 두 창은 가정 유지. 창마다 ID · seed · 방향 · 모드 기록 · invalid 로 분모 모자라면 확대 안 함 · 절반 이동으로 완료 대체 금지 | §6 끝 | 없음 |
| Q6 | 유지 26 판정 · 복원 13 기록 · 39 보존(D133). v0.1 §7.2 · §11 · Q6 의 「39 칸 판정」 은 오기. 종류별 칸은 노출 확대 때 필수 관문. 새 부모 평가 배치 · 기준표 SHA 고정 | §7.2 · §11 DR 행 · Q6 | 없음 |
| Q7 | 병합 순서는 제안, 성과 의존관계가 정본 · L3/6/9 는 평가 지점 · 틈 0.8 별도 승인 · 깃발과 지형 같은 경계 금지 · 발 들기 「새로 켬」 삭제(YAML :98 이미 켜짐 · 반감 이력 계승) | §1 · §11 보상 행 · Q7 · Q14 | 없음 |
| Q9 | M0~M3 크기별 순차 동의. 187 만으로는 누락(정답 지도 512 · 발 100, `start_obs.py:84~99`) · 실제 활성 · 주기 · lazy 호출 함께 · 10 분 이내 · 기존 lead 조건에 양보 · 2 GiB 는 후보 중단선 | §8 끝 | 512 · 100 은 planner 미재측(analyst 읽기) |
| Q11 | 기본안 동의(자동 기동 없음). 미달 줄 분리 · 보완 구간 별도 승인 · S2e +500 은 재시도 아님 · DR 끝값 1.0 전제 금지(실제 배율 인계) | §11 DR 행 · §12 두 행 · Q11 · P7 정본 §5 | 없음 |
| Q13 | 점검 시각 · 예산 고정 동의. 회차로 노출 확대 금지 · 미달이면 유지 · 등록된 연장 · 보고 · 3,500~9,000 은 산술 범위 · 전환 SHA 기록 | §12 회차 행 · Q13 | 없음 |

analyst 가 의견을 내지 않은 Q3 · Q5 · Q8 · Q10 · Q12 는 v0.1 그대로다.

## 14. 안 한 것 · 손대지 않은 것

- 코드 · GPU · Kit · 학습 없음. 지형 2 판 치수 · 깃발 배치 코드(W60) · W86 파서 확장은 설계만 적고 만들지 않았다.
- START 논문 PDF · AME-2 부록 A 원문을 다시 열지 않았다(저장소 요약 문서 두 개에 의존 · 등급 「읽기」). 숫자가 갈리면 원문이 이긴다.
- EX-40 의 GPU 메모리 · 지형 생성 시간 실측값을 찾지 못했다(미확인 · §8).
- analyst PLAN 의 35 행 완료 정의는 검토하지 않고 가리키기만 했다(겹침 방지). 반박 검토는 lead 가 걸면 따로.
- v0.2: analyst 의견이 가리킨 `start_obs.py:84~99`(광선 512 · 100) · `ex41_fixed.py:142~160`(DR 상한 소진) 은 다시 열지 않았다(analyst 읽기 그대로, §13b). 의견 Q3 · Q5 · Q8 · Q10 · Q12 는 없었다.
- W59 카드(T1 L3 첫 판) 는 이 문서가 아니다. worklist_gate 가 W55 증거 경로로 막혀 있다(§12).

## 15. 근거 경로

- WORKLIST: `origin/feature/verify-v2-mvp-jay:inbox/jay/20261028-plan/WORKLIST.md`(122a6435) :134 D106 · :141 D113 · :142 D114 · :143 D115 · :145 D117 · :152 D124 · :154 D126 · :158 D130 · :161 D133 · :164 D136 · :166 D138 · :233 W55 · :237 W59 · :250 W72 · :264 W86
- analyst: `origin/feature/analyst-terrain-w86-1102-jay:inbox/jay/20261102-analysis/PLAN-EX42-TERRAIN-GATES.md` · `SPEC-JEPLO-PRESET.md` · `foothold_s2/terrains/jeplo_preset.py`(f2ca807c) · 의견 `D:/mai-tmp/analyst/OPINION-EX42-Q-1102.md`(11/02 18:05 · 저장소 밖 · 요지는 §13b 에 옮김) · 그 의견이 가리킨 코드 `c63fe7d7 foothold_s2/curriculum/ex41-fixed5000.yaml:98 · 441~443` · `ex41_scoring.py:84~92` · `ex41_fixed.py:142~160` · `sensors/start_obs.py:84~99`(planner 는 YAML 441~452 · `ex41_fixed.CELLS[:26]` 만 다시 읽음, 나머지는 analyst 읽기)
- P7 졸업 판정 정본: `inbox/jay/20261101-ex41/P7-GRADUATION-SPEC.md` · `p7_spec_check.py`(feature/fable-25a-jay 53fda76c)
- 설계 정본: `inbox/jay/20261019-design/15-TERRAIN-CURRICULUM.md` :36~147 · `14-COMMAND-GENERATOR.md` :61~79 · :135~145 · `inbox/jay/20261018-next-arch/SPEC-ame2-go2.md` :138~156 · `inbox/jay/20261012-arch-discussion/PAPERS-architecture.md` :155~190(START) · :55~110(AME-2) · `inbox/jay/20261026-experiments/CURRICULUM-GATES.md` :60~71 · :140~147 · `inbox/jay/20261101-ex41/DESIGN-EX41-STAGE2-draft.md` :140~150 · :428~446
- 코드(D:/mai-wt/planner-d125 d5c14948 = runner e1615b0e + D125): `foothold_s2/terrains/columns.py:11~34` · `rough_go2_cfg.py:11~43` · `s2_layout.py:1~30` · `s2_runtime.py:46` · `progression.py:13~17` · `tasks/s2_env_cfg.py:39~70` · `eval/fixed_terrain.py:13~130` · `eval/map_mode_cells.py:72` · `eval/axis_v2_run.py:180~200` · `curriculum/ex41-fixed5000.yaml:1~40 · 130~178 · 424~455` · `curriculum/ex41.py:121~130` · `curriculum/rules.py:14~29` · `runners/start_runner.py:86~146` · `runners/map_stats.py:20~105` · `ex41_start_preflight.py:18~77` · `ex40_supervisor.py:1~6` · `sensors/depth_cam_cfg.py:15~22`
- Isaac Lab 2.3.2: `C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_generator.py:240~262`
- 실행 기록: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/params/env.yaml` :86 · :100~108 · :220 · :242 · :351~380 · :494~520, `agent.yaml` :58 · :67~68
- 로봇: `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf` :18 · :79~80 · :117~118 · :155~156 · :217 · :221~222 · `C:/Users/AI-WS01/s2_lab/_research_repos/MGDP/legged_gym/resources/robots/all_dog/lite3/urdf/lite3.urdf` :198 · :202~203 · :242~243 · :268~269 · :295
