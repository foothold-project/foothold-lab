> 분류: A/정책학습 · 평가 · 미경험 지형 · E1 대 E2
> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-13
> 근거: lead 10/12 23:30 의뢰 · 팀장 「자는 동안에도 GPU 가 돌고, ASTRA 검증을 받으며 Top-down 으로 아침까지」 · foothold-lab `models/foothold-v2.json` (evaluation.terrain_sets.unseen10 · scores_difficulty_0_5 · known_limits) · lab `sim/eval/generalization_env_cfg.py` · `sim/eval/terrains.py` (import 해서 씀, 고치지 않음) · 원자료 `_eval/out/un_*` · `_eval/out/full/un_*`
> 요지: E1 · E2 student (20000 · 20499) 를 v2 의 미경험 지형 10 종 (lab 정의를 그대로 import, 난이도 0.5) 에서 100 실행 · 1 만 판 평가했다. gap 은 0.5 m/s 이하에서 거의 못 건넌다 (0~4 %). 기록으로 보면 앞발이 먼저 틈 아래로 빠지고 몸이 앞으로 기울며 멈춘다. student 는 높이 관측이 없다. stepping_stones 는 건넘 0 % 로 v2 도 깨지는 지형이다. floating_ring 은 0.5 m/s 에서 70~88 % 이고 E2 가 E1 보다 일관되게 낫다. 나머지 7 종은 0.5 · 1.0 m/s 에서 92~100 % 다. v2 와는 잣대가 달라 패턴만 견준다. 대표 영상 144 편 (HUD · 웹 사본) 모든 프레임 결함 0 이고, GPU 1 감시 기록을 붙였다
> 상태: 판 1 (2026-10-13 04:22) · 평가 · 기록 · 영상 끝. ASTRA 검증 전

# 미경험 지형 10 종에서 E1 · E2 student 는 어디서 깨지나

표기: **확인됨** = 이번에 재거나 답을 아는 입력으로 시험한 것 · **추정** = 잰 값에서 끌어낸 해석 · **미확인** = 재지 않은 것.
경로는 `C:/isaac/ext/go2_rl_robotlab/_eval/` 기준이다. 학습은 하지 않았다. GPU 1 만 썼다 (GPU 0 은 lead 의 CMD-R 학습 중). 커밋하지 않았다.

## 0. 한눈에

표 0 · 0.5 m/s 전진 (fwd05) 과 1.0 m/s 전진 (fwd10, 20499 만) · 값은 **건넘 % · 생존 %** (100 판씩, 관측 noise 끔, 난이도 0.5). 원표 `out/UNSEEN-tables.md` · `out/UNSEEN-cells.csv`.

| 지형 | E1 · E2 학습 | 장애물 구간 끝 (m) | E1 20000 | E2 20000 | E1 20499 | E2 20499 | E1 20499 1.0 m/s | E2 20499 1.0 m/s | v2 카드 0.5 · 1.0 m/s |
|---|---|---|---|---|---|---|---|---|---|
| discrete_obstacles | 같은 종류 학습 (매개변수 다름) | 4.00 | 96 · 96 | 92 · 98 | 94 · 99 | 95 · 100 | 97 · 96 | 96 · 98 | 100 · 100 |
| wave | 같은 종류 학습 (매개변수 다름) | 4.00 | 99 · 100 | 97 · 100 | 100 · 100 | 98 · 100 | 100 · 100 | 100 · 100 | 100 · 100 |
| stepping_stones | 정의만 (비율 0) | 4.00 | 0 · 25 | 0 · 25 | 0 · 22 | 0 · 29 | 0 · 9 | 0 · 12 | 0 · 24 |
| gap | 정의만 (비율 0) | 1.02 | 4 · 45 | 0 · 31 | 0 · 46 | 0 · 25 | 30 · 35 | 27 · 35 | 100 · 100 |
| pit | 미경험 | 4.00 | 99 · 100 | 97 · 100 | 100 · 100 | 94 · 100 | 95 · 97 | 100 · 100 | 100 · 100 |
| rails | 미경험 | 2.88 | 92 · 99 | 100 · 98 | 97 · 100 | 92 · 99 | 94 · 100 | 99 · 99 | 99 · 100 (v2 학습 지형) |
| star | 미경험 | 4.00 | 98 · 99 | 97 · 100 | 100 · 100 | 97 · 99 | 100 · 100 | 100 · 100 | 100 · 100 |
| floating_ring | 미경험 | 1.18 | 70 · 81 | 88 · 95 | 70 · 83 | 82 · 89 | 69 · 64 | 85 · 83 | 100 · 100 |
| repeated_boxes | 미경험 | 4.00 | 99 · 100 | 97 · 100 | 100 · 100 | 96 · 100 | 100 · 100 | 100 · 100 | 100 · 100 |
| repeated_cylinders | 미경험 | 4.00 | 99 · 100 | 97 · 100 | 100 · 100 | 95 · 100 | 100 · 100 | 100 · 100 | 100 · 100 |

- **v2 카드 값은 잣대가 다르다.** 직접 견주지 않고 「같은 지형에서 어디서 깨지나」 패턴만 본다. 잣대 차이는 4 절에 있다.

## 1. 무엇을 돌렸나 (확인됨)

### 지형

- 10 종은 v2 카드 `evaluation.terrain_sets.unseen10` 이다: discrete_obstacles · wave · stepping_stones · gap · pit · rails · star · floating_ring · repeated_boxes · repeated_cylinders.
- 지형 정의는 lab 의 `GO2_UNSEEN_TERRAINS_CFG` (`sim/eval/generalization_env_cfg.py`) 를 q_eval 이 **직접 import** 한다. 사본이 아니다. 파일 sha256 은 실행 meta 에 남겼다.
  - v2 와 같은 것: 하위 지형 매개변수 · 타일 8 × 8 m · horizontal 0.1 · vertical 0.005 · slope_threshold 0.75 · 테두리 20 m · 난이도 0.5.
  - v2 와 다른 것:
    - 타일 수: 지형마다 10 장 (q_eval 배치, 출발은 0~7 행). v2 는 1 장 (`num_rows=1`).
    - 지형 시드: 1000. v2 는 42. 같은 매개변수의 다른 무작위 배치다.
    - 출발: 타일 중앙에서 xy ±0.5 m, 높이 +0~0.2 m, yaw 0 고정 (학습 reset 범위, q_eval 기본). v2 는 ±0.10 m · yaw ±5°.
- 학습 여부는 E1 · E2 `params/env.yaml` 의 지형 proportion 으로 붙였다.
  - wave (0.05) · discrete_obstacles (학습 지형 `obstacles` 가 같은 HfDiscreteObstacles, 0.20): **같은 종류를 학습함**. 매개변수는 다르다. 학습 wave 는 진폭 0.1~0.28 m 에 잡음이 있고, 학습 obstacles 는 폭 1~2 m · 높이 0.05~0.275 m 다.
  - stepping_stones · gap: 학습 cfg 에 정의는 있으나 proportion 0.0 이라 타일이 없다. 학습하지 않았다.
  - 나머지 6 종: 미경험.
- robot_lab 의 명령 항이 모르는 지형 이름을 거부해서, 명령 범위 칸 (`terrain_max_command_ranges`) 에 10 종을 넣었다.
  - 이 값은 학습 명령을 뽑는 `_resample` 안에서만 읽힌다. q_eval 은 그 함수를 고정 명령으로 바꾸므로 평가에 닿지 않는다 (확인됨: commands.py 사용처를 다 읽음).

### 정책 · 명령 · 판정

- 정책: E1 (시드 42) · E2 (시드 43) × model_20000 · model_20499. student 경로 (`act_inference`), 관측 noise 끔.
- student 관측은 PolicyCfg 의 여섯 항 45 칸 × 이력 10 = 450 이다 (env_cfg.py 124~160 행).
  - 각속도 3 · 중력 방향 3 · 명령 3 · 관절 각도 12 · 관절 속도 12 · 직전 행동 12.
  - **높이 스캔은 student 입력이 아니다.** teacher · critic (CriticCfg) 입력에만 있다.
- 명령 (q_eval cell, 20 s):
  - fwd05 (0.5 m/s), fwd03 (0.3 m/s): 모든 모델.
  - fwd10 (1.0 m/s): model_20499 만. 이번에 q_eval 에 새로 넣은 cell 이고, 이름으로만 고른다. 기존 `--cells all` 은 11 cell 그대로다.
- 실행: 지형 1 × cell 1 × 100 episode = 100 env. 1,100 env 는 GPU 1 에 안 들어간다. 평가 시드는 1000 이고, E1 과 E2 는 같은 시드라 출발 자세 · DR · 지형이 짝이다.
  - 100 실행 모두 끝났다. 건너뛴 실행은 0 이다.
- 판정 (q_post 그대로, Q-E1 임시 조건 · 현행 정의):
  - 생존: 몸통 접촉 · 60도 넘게 0.2 s 기울어짐 · 지지면 아래로 떨어짐이 없음.
  - Q1 (추종): 첫 1 s 를 뺀 창에서 MAE vx · vy ≤ 0.15, wz ≤ 0.20.
  - Q3: 4 m 통과선 + 통로 이탈 ≤ 0.30 m.
- **건넘 (이번에 더함)**: 살아 있는 동안 몸통이 「장애물 구간 끝」을 넘었는가. 타일 중앙에서 +x 로 잰다.
  - 구간 끝은 lab `terrains.obstacle_zone_m` 을 q_eval 안에서 실제 cfg 로 불러 meta 에 남긴 값이다 (`obstacle_zone_m`).
  - gap 1.025 m (플랫폼 절반 0.75 + 틈 0.275) · floating_ring 1.175 m · rails 2.88 m · 나머지는 타일 절반 4.0 m.
  - 타일 중앙 위치는 q_eval 이 남긴 `env_origins.npy` 다.
  - **주의:** 구간 끝이 4.0 m 인 지형에서 0.3 m/s 는 20 s 안에 4 m 를 가는 것 자체가 빠듯하다.
    - 필요 거리 중앙값 4.0 m, 실제 진행 중앙값 4.3~4.9 m, 몸통 속도 중앙값 0.25~0.28 m/s 다 (확인됨).
    - 그래서 fwd03 의 건넘 % 는 막힘과 시간 부족이 섞인다. fwd03 은 생존 · Q1 · move_ratio 로 읽는다.

### GPU 1

- 모든 실행에 `gpu_guard.py --gpu 1 --min_free_mib 4096` (200 ms) 를 걸었다. 감시 기록은 부록 표에 있다.
- 처음 31 실행은 기본 PhysX 버퍼로 돌았다. 최대 사용 12,101 MiB, 여유 최저 4,201 MiB 였다. 화면 바탕이 약 6.3 GB 였다.
- 00:10 에 1 실행 (un_e2_m20000_wave_fwd05) 을 감시가 멈췄다 (여유 4,016 MiB). 5 분 뒤 다시 돌려 끝냈다.
  - 그 실행의 guard.json 은 재시도가 덮어썼다. 멈춤은 `out/unseen_driver.log` 에 남아 있다.
- 그 뒤 69 실행은 PhysX GPU 버퍼를 작게 잡았다 (rigid patch 2^17 · collision stack 64 MiB, unseen10 실행에서만).
  - 바꾸기 전에 이미 끝난 두 실행 (wave · repeated_boxes) 을 작은 버퍼로 다시 돌려 견줬다. traj · term · 명령 10 개 배열이 bitwise 같았다 (확인됨).
  - 100 실행 로그에 PhysX overflow 문구는 0 이다 (확인됨).
  - 최대 사용 10,495 MiB, 여유 최저 5,807 MiB 다.

## 2. 결과 (확인됨)

표 U-1 의 칸은 **생존 / Q1 / Q3 / 건넘** % 이다. 표 U-2 는 낙상 원인과 진행 거리다. 둘 다 `unseen_post.py` 가 원자료에서 만든다.

#### 표 U-1 · 지형별 · 생존 / Q1 추종 / Q3 (4 m 통과선 · 통로 0.30 m) / 건넘 · % (100 판씩, noise 끔, 난이도 0.5)

| 지형 | 학습 여부 | 장애물 구간 끝 (m) | 명령 | E1 20000 | E2 20000 | E1 20499 | E2 20499 |
|---|---|---|---|---|---|---|---|
| discrete_obstacles | 학습함 (같은 종류 · 다른 매개변수) | 4.00 (tile_half:HfDiscreteObstaclesTerrainCfg) | fwd03 | 100 / 93 / 14 / **70** | 98 / 96 / 22 / **71** | 98 / 91 / 17 / **64** | 100 / 94 / 6 / **61** |
| discrete_obstacles | 학습함 (같은 종류 · 다른 매개변수) | 4.00 (tile_half:HfDiscreteObstaclesTerrainCfg) | fwd05 | 96 / 93 / 33 / **96** | 98 / 93 / 31 / **92** | 99 / 90 / 30 / **94** | 100 / 95 / 11 / **95** |
| discrete_obstacles | 학습함 (같은 종류 · 다른 매개변수) | 4.00 (tile_half:HfDiscreteObstaclesTerrainCfg) | fwd10 | - | - | 96 / 90 / 41 / **97** | 98 / 90 / 42 / **96** |
| wave | 학습함 (같은 종류 · 다른 매개변수) | 4.00 (tile_half:HfWaveTerrainCfg) | fwd03 | 100 / 100 / 22 / **84** | 100 / 100 / 17 / **79** | 100 / 100 / 15 / **83** | 100 / 100 / 8 / **70** |
| wave | 학습함 (같은 종류 · 다른 매개변수) | 4.00 (tile_half:HfWaveTerrainCfg) | fwd05 | 100 / 100 / 29 / **99** | 100 / 100 / 37 / **97** | 100 / 100 / 28 / **100** | 100 / 100 / 19 / **98** |
| wave | 학습함 (같은 종류 · 다른 매개변수) | 4.00 (tile_half:HfWaveTerrainCfg) | fwd10 | - | - | 100 / 100 / 42 / **100** | 100 / 100 / 43 / **100** |
| stepping_stones | 정의만 있음 (학습 비율 0) | 4.00 (tile_half:HfSteppingStonesTerrainCfg) | fwd03 | 39 / 0 / 0 / **0** | 50 / 0 / 0 / **0** | 29 / 0 / 0 / **0** | 34 / 0 / 0 / **0** |
| stepping_stones | 정의만 있음 (학습 비율 0) | 4.00 (tile_half:HfSteppingStonesTerrainCfg) | fwd05 | 25 / 0 / 0 / **0** | 25 / 0 / 0 / **0** | 22 / 0 / 0 / **0** | 29 / 0 / 0 / **0** |
| stepping_stones | 정의만 있음 (학습 비율 0) | 4.00 (tile_half:HfSteppingStonesTerrainCfg) | fwd10 | - | - | 9 / 0 / 0 / **0** | 12 / 0 / 0 / **0** |
| gap | 정의만 있음 (학습 비율 0) | 1.02 (gap_width_range) | fwd03 | 37 / 0 / 0 / **0** | 32 / 0 / 0 / **0** | 46 / 0 / 0 / **0** | 14 / 0 / 0 / **0** |
| gap | 정의만 있음 (학습 비율 0) | 1.02 (gap_width_range) | fwd05 | 45 / 1 / 0 / **4** | 31 / 0 / 0 / **0** | 46 / 0 / 0 / **0** | 25 / 0 / 0 / **0** |
| gap | 정의만 있음 (학습 비율 0) | 1.02 (gap_width_range) | fwd10 | - | - | 35 / 10 / 0 / **30** | 35 / 7 / 1 / **27** |
| pit | 미경험 | 4.00 (tile_half:MeshPitTerrainCfg) | fwd03 | 100 / 100 / 15 / **80** | 100 / 100 / 19 / **74** | 100 / 76 / 13 / **58** | 100 / 96 / 3 / **58** |
| pit | 미경험 | 4.00 (tile_half:MeshPitTerrainCfg) | fwd05 | 100 / 100 / 27 / **99** | 100 / 100 / 32 / **97** | 100 / 100 / 32 / **100** | 100 / 100 / 15 / **94** |
| pit | 미경험 | 4.00 (tile_half:MeshPitTerrainCfg) | fwd10 | - | - | 97 / 97 / 33 / **95** | 100 / 100 / 30 / **100** |
| rails | 미경험 | 2.88 (rail_2_outer_edge) | fwd03 | 100 / 82 / 3 / **67** | 100 / 100 / 12 / **87** | 100 / 82 / 12 / **76** | 100 / 64 / 6 / **57** |
| rails | 미경험 | 2.88 (rail_2_outer_edge) | fwd05 | 99 / 89 / 8 / **92** | 98 / 98 / 20 / **100** | 100 / 85 / 19 / **97** | 99 / 85 / 7 / **92** |
| rails | 미경험 | 2.88 (rail_2_outer_edge) | fwd10 | - | - | 100 / 84 / 23 / **94** | 99 / 83 / 22 / **99** |
| star | 미경험 | 4.00 (tile_half:MeshStarTerrainCfg) | fwd03 | 100 / 100 / 17 / **70** | 100 / 100 / 19 / **72** | 100 / 100 / 26 / **79** | 100 / 96 / 14 / **68** |
| star | 미경험 | 4.00 (tile_half:MeshStarTerrainCfg) | fwd05 | 99 / 99 / 33 / **98** | 100 / 100 / 39 / **97** | 100 / 100 / 37 / **100** | 99 / 99 / 21 / **97** |
| star | 미경험 | 4.00 (tile_half:MeshStarTerrainCfg) | fwd10 | - | - | 100 / 99 / 46 / **100** | 100 / 100 / 41 / **100** |
| floating_ring | 미경험 | 1.18 (ring_width_range) | fwd03 | 86 / 66 / 5 / **59** | 95 / 81 / 12 / **80** | 93 / 55 / 2 / **55** | 93 / 68 / 4 / **71** |
| floating_ring | 미경험 | 1.18 (ring_width_range) | fwd05 | 81 / 69 / 6 / **70** | 95 / 84 / 11 / **88** | 83 / 65 / 8 / **70** | 89 / 79 / 8 / **82** |
| floating_ring | 미경험 | 1.18 (ring_width_range) | fwd10 | - | - | 64 / 55 / 2 / **69** | 83 / 67 / 7 / **85** |
| repeated_boxes | 미경험 | 4.00 (tile_half:MeshRepeatedBoxesTerrainCfg) | fwd03 | 100 / 100 / 17 / **79** | 100 / 100 / 22 / **74** | 100 / 97 / 27 / **76** | 100 / 96 / 7 / **65** |
| repeated_boxes | 미경험 | 4.00 (tile_half:MeshRepeatedBoxesTerrainCfg) | fwd05 | 100 / 99 / 30 / **99** | 100 / 100 / 41 / **97** | 100 / 100 / 41 / **100** | 100 / 100 / 20 / **96** |
| repeated_boxes | 미경험 | 4.00 (tile_half:MeshRepeatedBoxesTerrainCfg) | fwd10 | - | - | 100 / 100 / 50 / **100** | 100 / 100 / 46 / **100** |
| repeated_cylinders | 미경험 | 4.00 (tile_half:MeshRepeatedCylindersTerrainCfg) | fwd03 | 100 / 100 / 22 / **82** | 100 / 100 / 23 / **73** | 100 / 99 / 25 / **80** | 100 / 97 / 5 / **64** |
| repeated_cylinders | 미경험 | 4.00 (tile_half:MeshRepeatedCylindersTerrainCfg) | fwd05 | 100 / 100 / 29 / **99** | 100 / 100 / 35 / **97** | 100 / 100 / 33 / **100** | 100 / 100 / 18 / **95** |
| repeated_cylinders | 미경험 | 4.00 (tile_half:MeshRepeatedCylindersTerrainCfg) | fwd10 | - | - | 100 / 100 / 47 / **100** | 100 / 100 / 43 / **100** |

#### 표 U-2 · 낙상 원인과 진행 거리 중앙값 (m)

| 지형 | 명령 | 실행 | 낙상 수 (원인) | 진행 중앙값 | move_ratio 중앙값 |
|---|---|---|---|---|---|
| discrete_obstacles | fwd03 | E1 20000 | 0 {} | 4.77 | 0.90 |
| discrete_obstacles | fwd03 | E2 20000 | 2 {"base_contact": 2} | 4.63 | 0.88 |
| discrete_obstacles | fwd03 | E1 20499 | 2 {"tilt60": 2} | 4.52 | 0.83 |
| discrete_obstacles | fwd03 | E2 20499 | 0 {} | 4.32 | 0.90 |
| discrete_obstacles | fwd05 | E1 20000 | 4 {"tilt60": 3, "base_contact": 1} | 8.43 | 0.93 |
| discrete_obstacles | fwd05 | E2 20000 | 2 {"tilt60": 1, "base_contact": 1} | 8.35 | 0.92 |
| discrete_obstacles | fwd05 | E1 20499 | 1 {"base_contact": 1} | 8.27 | 0.95 |
| discrete_obstacles | fwd05 | E2 20499 | 0 {} | 7.94 | 0.97 |
| discrete_obstacles | fwd10 | E1 20499 | 4 {"base_contact": 3, "tilt60": 1} | 16.82 | 0.97 |
| discrete_obstacles | fwd10 | E2 20499 | 2 {"base_contact": 2} | 16.42 | 0.97 |
| wave | fwd03 | E1 20000 | 0 {} | 4.92 | 0.93 |
| wave | fwd03 | E2 20000 | 0 {} | 4.72 | 0.90 |
| wave | fwd03 | E1 20499 | 0 {} | 4.95 | 0.90 |
| wave | fwd03 | E2 20499 | 0 {} | 4.69 | 0.94 |
| wave | fwd05 | E1 20000 | 0 {} | 8.67 | 0.95 |
| wave | fwd05 | E2 20000 | 0 {} | 8.73 | 0.95 |
| wave | fwd05 | E1 20499 | 0 {} | 8.85 | 0.98 |
| wave | fwd05 | E2 20499 | 0 {} | 8.56 | 0.98 |
| wave | fwd10 | E1 20499 | 0 {} | 17.30 | 0.98 |
| wave | fwd10 | E2 20499 | 0 {} | 17.79 | 0.98 |
| stepping_stones | fwd03 | E1 20000 | 61 {"base_contact": 51, "tilt60": 10} | 0.87 | 0.40 |
| stepping_stones | fwd03 | E2 20000 | 50 {"base_contact": 47, "tilt60": 3} | 0.82 | 0.18 |
| stepping_stones | fwd03 | E1 20499 | 71 {"base_contact": 64, "tilt60": 7} | 0.90 | 0.38 |
| stepping_stones | fwd03 | E2 20499 | 66 {"base_contact": 65, "tilt60": 1} | 0.87 | 0.42 |
| stepping_stones | fwd05 | E1 20000 | 75 {"base_contact": 70, "tilt60": 5} | 0.93 | 0.47 |
| stepping_stones | fwd05 | E2 20000 | 75 {"base_contact": 72, "tilt60": 3} | 0.94 | 0.46 |
| stepping_stones | fwd05 | E1 20499 | 78 {"base_contact": 76, "tilt60": 2} | 0.96 | 0.50 |
| stepping_stones | fwd05 | E2 20499 | 71 {"base_contact": 65, "tilt60": 6} | 0.89 | 0.37 |
| stepping_stones | fwd10 | E1 20499 | 91 {"base_contact": 87, "tilt60": 4} | 1.11 | 0.42 |
| stepping_stones | fwd10 | E2 20499 | 88 {"base_contact": 85, "tilt60": 3} | 1.05 | 0.40 |
| gap | fwd03 | E1 20000 | 63 {"base_contact": 50, "tilt60": 13} | 0.72 | 0.38 |
| gap | fwd03 | E2 20000 | 68 {"base_contact": 68} | 0.72 | 0.81 |
| gap | fwd03 | E1 20499 | 54 {"base_contact": 53, "tilt60": 1} | 0.74 | 0.17 |
| gap | fwd03 | E2 20499 | 86 {"base_contact": 85, "below_support": 1} | 0.70 | 0.95 |
| gap | fwd05 | E1 20000 | 55 {"base_contact": 51, "tilt60": 4} | 0.71 | 0.08 |
| gap | fwd05 | E2 20000 | 69 {"base_contact": 69} | 0.72 | 0.40 |
| gap | fwd05 | E1 20499 | 54 {"base_contact": 53, "tilt60": 1} | 0.72 | 0.08 |
| gap | fwd05 | E2 20499 | 75 {"base_contact": 72, "below_support": 1, "tilt60": 2} | 0.71 | 0.59 |
| gap | fwd10 | E1 20499 | 65 {"base_contact": 58, "tilt60": 6, "below_support": 1} | 0.93 | 0.05 |
| gap | fwd10 | E2 20499 | 65 {"base_contact": 60, "tilt60": 5} | 0.84 | 0.03 |
| pit | fwd03 | E1 20000 | 0 {} | 4.71 | 0.90 |
| pit | fwd03 | E2 20000 | 0 {} | 4.73 | 0.89 |
| pit | fwd03 | E1 20499 | 0 {} | 4.50 | 0.82 |
| pit | fwd03 | E2 20499 | 0 {} | 4.28 | 0.93 |
| pit | fwd05 | E1 20000 | 0 {} | 8.64 | 0.94 |
| pit | fwd05 | E2 20000 | 0 {} | 8.68 | 0.94 |
| pit | fwd05 | E1 20499 | 0 {} | 8.81 | 0.97 |
| pit | fwd05 | E2 20499 | 0 {} | 7.97 | 0.97 |
| pit | fwd10 | E1 20499 | 3 {"base_contact": 3} | 16.08 | 0.97 |
| pit | fwd10 | E2 20499 | 0 {} | 17.13 | 0.97 |
| rails | fwd03 | E1 20000 | 0 {} | 3.29 | 0.67 |
| rails | fwd03 | E2 20000 | 0 {} | 4.52 | 0.85 |
| rails | fwd03 | E1 20499 | 0 {} | 3.95 | 0.72 |
| rails | fwd03 | E2 20499 | 0 {} | 2.88 | 0.64 |
| rails | fwd05 | E1 20000 | 1 {"tilt60": 1} | 6.91 | 0.84 |
| rails | fwd05 | E2 20000 | 2 {"tilt60": 1, "base_contact": 1} | 8.24 | 0.90 |
| rails | fwd05 | E1 20499 | 0 {} | 7.53 | 0.84 |
| rails | fwd05 | E2 20499 | 1 {"base_contact": 1} | 6.72 | 0.86 |
| rails | fwd10 | E1 20499 | 0 {} | 15.64 | 0.92 |
| rails | fwd10 | E2 20499 | 1 {"base_contact": 1} | 15.40 | 0.92 |
| star | fwd03 | E1 20000 | 0 {} | 4.55 | 0.87 |
| star | fwd03 | E2 20000 | 0 {} | 4.66 | 0.87 |
| star | fwd03 | E1 20499 | 0 {} | 4.72 | 0.86 |
| star | fwd03 | E2 20499 | 0 {} | 4.58 | 0.90 |
| star | fwd05 | E1 20000 | 1 {"base_contact": 1} | 8.12 | 0.92 |
| star | fwd05 | E2 20000 | 0 {} | 8.45 | 0.92 |
| star | fwd05 | E1 20499 | 0 {} | 8.65 | 0.94 |
| star | fwd05 | E2 20499 | 1 {"base_contact": 1} | 8.13 | 0.95 |
| star | fwd10 | E1 20499 | 0 {} | 17.18 | 0.96 |
| star | fwd10 | E2 20499 | 0 {} | 16.74 | 0.96 |
| floating_ring | fwd03 | E1 20000 | 14 {"base_contact": 14} | 1.75 | 0.70 |
| floating_ring | fwd03 | E2 20000 | 5 {"base_contact": 5} | 4.02 | 0.82 |
| floating_ring | fwd03 | E1 20499 | 7 {"base_contact": 7} | 2.38 | 0.67 |
| floating_ring | fwd03 | E2 20499 | 7 {"base_contact": 7} | 3.35 | 0.79 |
| floating_ring | fwd05 | E1 20000 | 19 {"base_contact": 18, "tilt60": 1} | 6.69 | 0.82 |
| floating_ring | fwd05 | E2 20000 | 5 {"base_contact": 5} | 7.75 | 0.89 |
| floating_ring | fwd05 | E1 20499 | 17 {"base_contact": 17} | 6.36 | 0.84 |
| floating_ring | fwd05 | E2 20499 | 11 {"base_contact": 11} | 6.53 | 0.91 |
| floating_ring | fwd10 | E1 20499 | 36 {"base_contact": 32, "tilt60": 4} | 9.75 | 0.92 |
| floating_ring | fwd10 | E2 20499 | 17 {"base_contact": 17} | 13.01 | 0.93 |
| repeated_boxes | fwd03 | E1 20000 | 0 {} | 4.76 | 0.90 |
| repeated_boxes | fwd03 | E2 20000 | 0 {} | 4.77 | 0.89 |
| repeated_boxes | fwd03 | E1 20499 | 0 {} | 4.68 | 0.85 |
| repeated_boxes | fwd03 | E2 20499 | 0 {} | 4.53 | 0.90 |
| repeated_boxes | fwd05 | E1 20000 | 0 {} | 8.61 | 0.93 |
| repeated_boxes | fwd05 | E2 20000 | 0 {} | 8.72 | 0.93 |
| repeated_boxes | fwd05 | E1 20499 | 0 {} | 8.75 | 0.96 |
| repeated_boxes | fwd05 | E2 20499 | 0 {} | 8.05 | 0.96 |
| repeated_boxes | fwd10 | E1 20499 | 0 {} | 17.64 | 0.97 |
| repeated_boxes | fwd10 | E2 20499 | 0 {} | 17.47 | 0.97 |
| repeated_cylinders | fwd03 | E1 20000 | 0 {} | 4.77 | 0.89 |
| repeated_cylinders | fwd03 | E2 20000 | 0 {} | 4.79 | 0.90 |
| repeated_cylinders | fwd03 | E1 20499 | 0 {} | 4.77 | 0.86 |
| repeated_cylinders | fwd03 | E2 20499 | 0 {} | 4.52 | 0.93 |
| repeated_cylinders | fwd05 | E1 20000 | 0 {} | 8.69 | 0.93 |
| repeated_cylinders | fwd05 | E2 20000 | 0 {} | 8.70 | 0.94 |
| repeated_cylinders | fwd05 | E1 20499 | 0 {} | 8.91 | 0.96 |
| repeated_cylinders | fwd05 | E2 20499 | 0 {} | 8.16 | 0.97 |
| repeated_cylinders | fwd10 | E1 20499 | 0 {} | 17.54 | 0.97 |
| repeated_cylinders | fwd10 | E2 20499 | 0 {} | 17.61 | 0.98 |


## 3. 어디서 깨지나

### 3-1. gap: 앞발이 틈으로 빠지며 앞으로 고꾸라진다 (확인됨: 기록 · 추정: 해석)

- 건넘은 0.3 · 0.5 m/s 에서 0~4 %, 1.0 m/s 에서 27~30 % 다. 생존은 14~46 % 이고, 낙상 대부분이 몸통 접촉이다 (실행마다 50~85 판).
- 100 판 전체의 「가장 멀리 간 몸통 위치」 (타일 중앙 기준, 살아 있는 동안):
  - 중앙값은 0.73~0.85 m 다. 플랫폼 끝이 0.75 m 다.
  - 0.5 m/s 이하에서 먼 쪽 끝 (1.025 m) 을 넘은 판은 0~4 개다. 1.0 m/s 에서는 27~30 개다.
  - 원표: `out/UNSEEN-gap-failure.json`.
- 대표판 기록 (첫 성공 · 첫 실패 · MAE 중앙값, 10 실행에서 멈칫이 잡힌 17 판):
  - 「멈칫」은 0.5 s 평균 몸통 vx 가 명령의 30 % 아래로 떨어진 첫 시각이다 (첫 1 s 이후).
  - 17 판 가운데 16 판에서 **앞발 하나가 먼저 플랫폼 윗면보다 5 cm 넘게 내려갔다.** 그 뒤 0.34~1.08 s 안에 멈칫이 왔다.
  - 멈칫 때 몸통은 x 0.62~0.97 m (대부분 0.71~0.76 m) 로 플랫폼 끝에 있었다. 몸 앞쪽이 아래로 14~40° 기울어 있었다.
- 해석 (추정): student 는 틈을 볼 수 없다. 높이 스캔이 입력이 아니기 때문이다 (1 절).
  - 앞발이 허공을 딛고 빠진 뒤에야 몸 감각 (관절 · 중력 방향) 으로 넘어짐을 겪는다.
  - 1.0 m/s 에서 일부가 건너는 것은 보폭과 운동량이 0.275 m 틈을 넘기기 때문으로 보인다. 재지 않았다 (미확인).
- 출발 위치 탓 낙상: 1 s 안에 넘어진 판이 gap 실행마다 0~8 개다.
  - 출발 ±0.5 m 가 1.5 m 플랫폼에서 발을 틈 위에 놓을 수 있다. v2 의 ±0.10 m 에는 없는 조건이다.
- teacher 관측의 사실 (따로 적는다, D1 · G0 진단 맥락): Isaac Lab `height_scan` 에서 빗나간 광선은 −inf 이다.
  - clip (−1) 을 거쳐 scale 2.5 가 곱해져 **−2.5** 가 된다 (observation_manager.py 404~407 행: clip 다음 scale · ray_caster 의 miss = inf).
  - 바닥 없는 틈은 teacher · critic 입력에서 「몸통보다 1 m 넘게 솟은 것」과 같은 값이 된다. student 와는 관계없다.

### 3-2. stepping_stones: 플랫폼을 벗어나자마자 발이 구멍에 빠진다 (확인됨: 기록)

- 건넘은 모든 칸에서 0 % 다. 생존은 22~50 % (0.3 · 0.5 m/s), 9~12 % (1.0 m/s) 다. 낙상 시각 중앙값은 2.1~5.2 s 다.
- 대표판 기록:
  - 발 하나가 구멍 (타일 원점보다 0.2 m 넘게 아래) 으로 내려간 뒤 넘어졌다.
  - 몸통이 가장 멀리 간 위치는 0.7~1.6 m 로, 플랫폼 끝 (0.75 m) 을 막 벗어난 자리다.
  - 일부는 출발 0.3 s 안에 발이 이미 구멍 위에 있었다 (출발 ±0.5 m).
- v2 도 이 지형은 0.5 m/s 0 %, 1.0 m/s 24 % (시드에 따라 0~24 %) 였다 (카드 known_limits).

### 3-3. floating_ring: 몸통 접촉으로 넘어진다 · 시드 차가 가장 크다

- 건넘 55~88 %, 생존 64~95 % 다. 낙상은 모두 몸통 접촉이다.
  - 고리 아래면이 지면 위 0.105 m, 두께 0.12 m 다 (d = 0.5, mesh_terrains.py floating_ring_terrain).
- E2 가 E1 보다 일관되게 낫다: 건넘 +12~21 pp (다섯 칸 모두), 생존 +14~19 pp (20000 fwd05 · 20499 fwd10).
- 어디서 · 어떻게 닿는지는 재지 않았다 (원인 미확인). 대표판 영상에 실패판이 있다.

### 3-4. 나머지

- rails: 0.5 · 1.0 m/s 에서 건넘 92~100 %, 생존 98~100 % 다. 0.3 m/s 에서는 move_ratio 0.64~0.85 로 느려진다.
- wave · pit · star · repeated_boxes · repeated_cylinders · discrete_obstacles: 0.5 · 1.0 m/s 에서 건넘 92~100 %, 생존 96~100 % 다.

### 3-5. E1 대 E2 (같은 시드 1000, 짝)

10 pp 넘게 갈리는 칸을 셌다. 시간 부족이 섞이는 fwd03 · 타일 절반 지형의 건넘은 뺐다.

| 무엇 | 칸 | 방향 |
|---|---|---|
| floating_ring 건넘 · Q1 · 생존 | 12 | 모두 E2 가 높음 (건넘 +12~21 · Q1 +12~15 · 생존 +14~19 pp) |
| gap 생존 | 3 | 모두 E2 가 낮음 (−14~−32 pp) |
| Q3 (통로 0.30 m) | 12 | 20499 의 10 칸은 E2 가 낮음 (−11~−21 pp). 20000 의 2 칸은 E2 가 높음 |
| rails 0.3 m/s | 4 | 20000 은 E2 높음, 20499 는 E2 낮음 |
| pit 0.3 m/s Q1 | 1 | E2 높음 (+20) |
| stepping_stones 0.3 m/s 생존 | 1 | E2 높음 (+11) |

- 추정: E2 20499 의 Q3 하락은 옆으로 새는 쪽이다. E2-and-records.md 의 E2 20499 좌우 회전 비대칭 (yawR05 덜 돎) 과 같은 방향일 수 있다. 재지 않았다.


## 4. v2 의 같은 지형 성적과 잣대 차이

| | v2 카드 (`scores_difficulty_0_5`) | 이 평가 |
|---|---|---|
| 성공 정의 | 생존 · 진행 ≥ 3 m · 추종 MAE ≤ 0.25 · 방향 (3 m 지점 좌우 ≤ 0.75 m) 넷의 AND | 생존 · Q1 (MAE vx · vy ≤ 0.15, wz ≤ 0.20) · Q3 (4 m · 통로 0.30 m) · 건넘을 따로 |
| 판 길이 | ideal 6 m 를 속도로 나눈 시간 (0.5 m/s 12 s · 1.0 m/s 6 s, 카드 eval_duration_s 4 · 6 · 12) | 20 s |
| 타일 | 지형마다 1 장 · 시드 42 | 지형마다 10 장 · 시드 1000 |
| 출발 | ±0.10 m · yaw ±5° | ±0.5 m · yaw 0 |
| 높이 관측 | v2 정책의 입력. 빗나간 광선 +1 (규격 2) | student 는 높이 관측 없음 |
| rails | v2 는 학습 지형 (proportion 0.1) | E1 · E2 미경험 |

- 같은 지형에서 깨지는 곳의 패턴:
  - stepping_stones 는 둘 다 깨진다 (v2 0~24 %, E1 · E2 건넘 0 %).
  - gap 은 v2 는 100 % 이고, E1 · E2 는 0~4 % (0.5 m/s 이하) 다.
  - 나머지 8 종은 둘 다 대부분 지난다. floating_ring 은 v2 100 %, E1 · E2 70~88 % 다.
- 추정: gap 의 차이는 「틈을 보는 관측이 있느냐」와 맞아떨어진다. v2 는 높이 관측이 있고, student 는 없다.
  - 정책 · 학습 · 잣대가 함께 다르므로 원인으로 확정할 수 없다.


## 5. 기록 · 영상 (확인됨)

- **전체 기록 CSV**: 100 실행 모두 `--full_record`. 칸마다 첫 성공 · 첫 실패 · MAE 중앙값을 남겼다.
  - 243 편 · 234.1 MB, 115 열 (`out/full/un_*/`). 열 정의는 각 폴더의 `SCHEMA.md` 에 있다.
- **lab 규격 사본**: `fr_to_legacy.py` 로 93 열 parquet 243 편 (65.5 MB) 과 HUD trace 17 열 243 편 (53.1 MB) 을 만들었다 (`out/legacy/un_*/`).
  - 바닥 기준점은 실행이 남긴 `env_origins.npy` 다.
  - 판정값 (MAE · 행 수) 되접기 대조는 243/243 통과했다.
- **영상** (`out/unseen_sel.json`): 칸마다 첫 성공 · 첫 실패.
  - 200 칸 가운데 144 편이 나왔다. 빈 칸은 그 칸에 성공이나 실패 판이 없던 자리다 (예: stepping_stones 는 성공이 없음).
  - 실행별 편 수: E1 20499 45 · E2 20499 45 · E1 20000 29 · E2 20000 25.

| 산출물 | 경로 | 편 | 크기 |
|---|---|---|---|
| 아래 띠 기록 재생 (운동학, 물리 재계산 아님, Q 판정 줄) | `out/video_hud_src/un_*/` | 144 | 2,591.6 MB |
| HUD (lab render.py flat 모드) | `out/video_hud/un_*/` | 144 | 605.1 MB |
| 웹 사본 (720p · H.264 · faststart · < 2 MB) | `out/web/un_*/` | 144 | 199.4 MB (가장 큰 것 1,998,576 B) |

- **관문 둘 (오늘 넣은 것) 을 그대로 썼다.**
  - 렌더 관문: un_e1_m20499_stepping_stones_fwd10 ep0 은 첫 프로세스에서 frame 22 가 12 번 다시 렌더해도 「하늘」이라 거부됐다. 새 프로세스의 두 번째 시도에서 재렌더 0 으로 통과했다. 렌더러 프로세스 탈 (어제와 같은 증상) 로 보인다 (추정).
  - 발행 관문: HUD · 웹 사본 모든 프레임 검사에서 거절 0.
- **모든 프레임 검사**: 아래 띠 원본 · HUD · 웹 사본 432 파일, 결함 0 (`out/unseen_frame_audit.json`).
- 목록: `out/unseen_web_list.csv` (실행 · model · 지형 · cell · 고른 이유 · Q 판정 줄 · 웹 경로 · 크기).
- 처리 중 생긴 일 (확인됨):
  - 첫 tag (E1 20499 discrete_obstacles fwd05) 영상 2 편이 렌더 스크립트의 지형 이름 문제로 빠졌다. 고친 뒤 04:10 에 GPU 1 이 빌 때 다시 찍었다.
  - 실행기의 마지막 검사 단계가 Windows process pool 의 재import 로 깨졌다 (04:13).
    - 자식 프로세스가 실행기를 다시 읽어 변환을 동시에 돌렸다. 그 사이에 만든 parquet 이 깨졌을 수 있어 100 tag 를 모두 다시 변환했다 (실패 0, 되접기 대조 통과).
    - 그 뒤 검사만 다시 돌렸다. 실행기는 `if __name__ == "__main__"` 으로 고쳤다.
    - GPU 일은 03:55 에 이미 끝나 있었다. 04:13 부터 GPU 1 은 lead 의 CMD-R 평가가 쓴다. 그 뒤 제 일은 CPU 만 썼다.


## 부록 · GPU 1 감시 기록 (확인됨)

- 전체 표 (평가 100 · 영상 101): `out/UNSEEN-guards.csv` · `out/UNSEEN-guards.md`. 감시 간격 200 ms, 바닥 4,096 MiB.
- 평가 100 실행: 감시가 멈춘 실행 0 (최종 기록 기준).
  - 단, 00:10 의 1 회 멈춤 (un_e2_m20000_wave_fwd05, 여유 4,016 MiB) 은 재시도 기록이 덮어써 이 표에 없다. `out/unseen_driver.log` 에 있다.
  - 기본 버퍼 31 실행: 여유 최저 4,201 MiB · 최대 사용 12,101 MiB.
  - 작은 버퍼 69 실행: 여유 최저 5,807 MiB · 최대 사용 10,495 MiB.
- 영상 101 실행 (CPU PhysX · 렌더 GPU 1): 여유 최저 6,621 MiB · 최대 사용 9,681 MiB.

평가 실행 표 (끝난 시각 순):

| 종류 | tag | PhysX 버퍼 | 여유 최저 MiB | 최대 사용 MiB | 표본 (200 ms) | 멈춤 | exit | 끝난 시각 |
|---|---|---|---|---|---|---|---|---|
| eval | un_e1_m20000_gap_fwd05 | default | 4,805 | 11,497 | 433 |  | 0 | 00:00:28 |
| eval | un_e1_m20000_pit_fwd05 | default | 4,799 | 11,503 | 419 |  | 0 | 00:01:53 |
| eval | un_e1_m20000_rails_fwd05 | default | 4,814 | 11,488 | 440 |  | 0 | 00:03:21 |
| eval | un_e1_m20000_star_fwd05 | default | 4,791 | 11,511 | 422 |  | 0 | 00:04:46 |
| eval | un_e1_m20000_floating_ring_fwd05 | default | 4,821 | 11,481 | 442 |  | 0 | 00:06:15 |
| eval | un_e1_m20000_repeated_boxes_fwd05 | default | 4,779 | 11,523 | 414 |  | 0 | 00:07:38 |
| eval | un_e1_m20000_repeated_cylinders_fwd05 | default | 4,622 | 11,680 | 422 |  | 0 | 00:09:03 |
| eval | un_e2_m20000_discrete_obstacles_fwd05 | default | 4,649 | 11,653 | 429 |  | 0 | 00:10:30 |
| eval | un_e2_m20000_wave_fwd05 | small | 6,027 | 10,275 | 410 |  | 0 | 00:17:14 |
| eval | un_e2_m20000_stepping_stones_fwd05 | small | 6,582 | 9,720 | 560 |  | 0 | 00:19:07 |
| eval | un_e2_m20000_gap_fwd05 | small | 6,242 | 10,060 | 464 |  | 0 | 00:20:40 |
| eval | un_e2_m20000_pit_fwd05 | small | 6,608 | 9,694 | 423 |  | 0 | 00:22:05 |
| eval | un_e2_m20000_rails_fwd05 | small | 6,713 | 9,589 | 448 |  | 0 | 00:23:35 |
| eval | un_e2_m20000_star_fwd05 | small | 6,127 | 10,175 | 419 |  | 0 | 00:25:00 |
| eval | un_e2_m20000_floating_ring_fwd05 | small | 6,687 | 9,615 | 432 |  | 0 | 00:26:27 |
| eval | un_e2_m20000_repeated_boxes_fwd05 | small | 6,724 | 9,578 | 417 |  | 0 | 00:27:51 |
| eval | un_e2_m20000_repeated_cylinders_fwd05 | small | 6,670 | 9,632 | 410 |  | 0 | 00:29:13 |
| eval | un_e1_m20499_discrete_obstacles_fwd03 | small | 6,137 | 10,165 | 423 |  | 0 | 00:30:38 |
| eval | un_e1_m20499_wave_fwd03 | small | 6,672 | 9,630 | 426 |  | 0 | 00:32:04 |
| eval | un_e1_m20499_stepping_stones_fwd03 | small | 6,133 | 10,169 | 519 |  | 0 | 00:33:48 |
| eval | un_e1_m20499_gap_fwd03 | small | 6,719 | 9,583 | 438 |  | 0 | 00:35:16 |
| eval | un_e1_m20499_pit_fwd03 | small | 6,676 | 9,626 | 424 |  | 0 | 00:36:42 |
| eval | un_e1_m20499_rails_fwd03 | small | 6,724 | 9,578 | 458 |  | 0 | 00:38:14 |
| eval | un_e1_m20499_star_fwd03 | small | 6,718 | 9,584 | 411 |  | 0 | 00:39:37 |
| eval | un_e1_m20499_floating_ring_fwd03 | small | 6,504 | 9,798 | 450 |  | 0 | 00:41:07 |
| eval | un_e1_m20499_repeated_boxes_fwd03 | small | 6,044 | 10,258 | 426 |  | 0 | 00:42:33 |
| eval | un_e1_m20499_repeated_cylinders_fwd03 | small | 6,647 | 9,655 | 415 |  | 0 | 00:43:57 |
| eval | un_e2_m20499_discrete_obstacles_fwd03 | small | 6,566 | 9,736 | 430 |  | 0 | 00:45:23 |
| eval | un_e2_m20499_wave_fwd03 | small | 6,444 | 9,858 | 435 |  | 0 | 00:46:51 |
| eval | un_e2_m20499_stepping_stones_fwd03 | small | 6,584 | 9,718 | 542 |  | 0 | 00:48:40 |
| eval | un_e2_m20499_gap_fwd03 | small | 6,573 | 9,729 | 470 |  | 0 | 00:50:14 |
| eval | un_e2_m20499_pit_fwd03 | small | 6,523 | 9,779 | 443 |  | 0 | 00:51:44 |
| eval | un_e2_m20499_rails_fwd03 | small | 6,512 | 9,790 | 451 |  | 0 | 00:53:14 |
| eval | un_e2_m20499_star_fwd03 | small | 5,959 | 10,343 | 423 |  | 0 | 00:54:40 |
| eval | un_e2_m20499_floating_ring_fwd03 | small | 6,640 | 9,662 | 450 |  | 0 | 00:56:10 |
| eval | un_e2_m20499_repeated_boxes_fwd03 | small | 6,661 | 9,641 | 428 |  | 0 | 00:57:36 |
| eval | un_e2_m20499_repeated_cylinders_fwd03 | small | 6,630 | 9,672 | 425 |  | 0 | 00:59:02 |
| eval | un_e1_m20000_discrete_obstacles_fwd03 | small | 6,514 | 9,788 | 435 |  | 0 | 01:00:30 |
| eval | un_e1_m20000_wave_fwd03 | small | 6,477 | 9,825 | 434 |  | 0 | 01:01:57 |
| eval | un_e1_m20000_stepping_stones_fwd03 | small | 6,165 | 10,137 | 533 |  | 0 | 01:03:44 |
| eval | un_e1_m20000_gap_fwd03 | small | 6,573 | 9,729 | 467 |  | 0 | 01:05:18 |
| eval | un_e1_m20000_pit_fwd03 | small | 6,505 | 9,797 | 450 |  | 0 | 01:06:49 |
| eval | un_e1_m20000_rails_fwd03 | small | 6,464 | 9,838 | 480 |  | 0 | 01:08:26 |
| eval | un_e1_m20000_star_fwd03 | small | 6,499 | 9,803 | 447 |  | 0 | 01:09:56 |
| eval | un_e1_m20000_floating_ring_fwd03 | small | 6,353 | 9,949 | 516 |  | 0 | 01:11:39 |
| eval | un_e1_m20000_repeated_boxes_fwd03 | small | 6,471 | 9,831 | 461 |  | 0 | 01:13:12 |
| eval | un_e1_m20000_repeated_cylinders_fwd03 | small | 6,663 | 9,639 | 466 |  | 0 | 01:14:46 |
| eval | un_e2_m20000_discrete_obstacles_fwd03 | small | 6,567 | 9,735 | 487 |  | 0 | 01:16:24 |
| eval | un_e2_m20000_wave_fwd03 | small | 6,527 | 9,775 | 455 |  | 0 | 01:17:56 |
| eval | un_e2_m20000_stepping_stones_fwd03 | small | 6,618 | 9,684 | 550 |  | 0 | 01:19:47 |
| eval | un_e2_m20000_gap_fwd03 | small | 6,568 | 9,734 | 493 |  | 0 | 01:21:26 |
| eval | un_e2_m20000_pit_fwd03 | small | 6,526 | 9,776 | 454 |  | 0 | 01:22:57 |
| eval | un_e2_m20000_rails_fwd03 | small | 6,368 | 9,934 | 482 |  | 0 | 01:24:34 |
| eval | un_e2_m20000_star_fwd03 | small | 6,346 | 9,956 | 474 |  | 0 | 01:26:10 |
| eval | un_e2_m20000_floating_ring_fwd03 | small | 6,418 | 9,884 | 482 |  | 0 | 01:27:47 |
| eval | un_e2_m20000_repeated_boxes_fwd03 | small | 6,668 | 9,634 | 463 |  | 0 | 01:29:20 |
| eval | un_e2_m20000_repeated_cylinders_fwd03 | small | 6,602 | 9,700 | 468 |  | 0 | 01:30:54 |
| eval | un_e1_m20499_discrete_obstacles_fwd10 | small | 6,628 | 9,674 | 459 |  | 0 | 01:32:27 |
| eval | un_e1_m20499_wave_fwd10 | small | 6,124 | 10,178 | 457 |  | 0 | 01:33:59 |
| eval | un_e1_m20499_stepping_stones_fwd10 | small | 6,085 | 10,217 | 584 |  | 0 | 01:35:56 |
| eval | un_e1_m20499_gap_fwd10 | small | 6,513 | 9,789 | 484 |  | 0 | 01:37:34 |
| eval | un_e1_m20499_pit_fwd10 | small | 6,521 | 9,781 | 458 |  | 0 | 01:39:07 |
| eval | un_e1_m20499_rails_fwd10 | small | 6,435 | 9,867 | 484 |  | 0 | 01:40:44 |
| eval | un_e1_m20499_star_fwd10 | small | 6,280 | 10,022 | 453 |  | 0 | 01:42:15 |
| eval | un_e1_m20499_floating_ring_fwd10 | small | 6,325 | 9,977 | 469 |  | 0 | 01:43:50 |
| eval | un_e1_m20499_repeated_boxes_fwd10 | small | 5,921 | 10,381 | 434 |  | 0 | 01:45:17 |
| eval | un_e1_m20499_repeated_cylinders_fwd10 | small | 6,075 | 10,227 | 442 |  | 0 | 01:46:46 |
| eval | un_e2_m20499_discrete_obstacles_fwd10 | small | 5,890 | 10,412 | 486 |  | 0 | 01:48:24 |
| eval | un_e2_m20499_wave_fwd10 | small | 6,159 | 10,143 | 443 |  | 0 | 01:49:53 |
| eval | un_e2_m20499_stepping_stones_fwd10 | small | 6,234 | 10,068 | 592 |  | 0 | 01:51:52 |
| eval | un_e2_m20499_gap_fwd10 | small | 6,356 | 9,946 | 495 |  | 0 | 01:53:32 |
| eval | un_e2_m20499_pit_fwd10 | small | 5,807 | 10,495 | 459 |  | 0 | 01:55:04 |
| eval | un_e2_m20499_rails_fwd10 | small | 6,474 | 9,828 | 479 |  | 0 | 01:56:41 |
| eval | un_e2_m20499_star_fwd10 | small | 6,389 | 9,913 | 457 |  | 0 | 01:58:13 |
| eval | un_e2_m20499_floating_ring_fwd10 | small | 6,324 | 9,978 | 500 |  | 0 | 01:59:54 |
| eval | un_e2_m20499_repeated_boxes_fwd10 | small | 6,039 | 10,263 | 445 |  | 0 | 02:01:23 |
| eval | un_e2_m20499_repeated_cylinders_fwd10 | small | 6,379 | 9,923 | 448 |  | 0 | 02:02:53 |
| eval | un_e1_m20499_discrete_obstacles_fwd05 | default | 4,816 | 11,486 | 476 |  | 0 | 23:25:40 |
| eval | un_e1_m20499_wave_fwd05 | default | 4,261 | 12,041 | 457 |  | 0 | 23:27:21 |
| eval | un_e1_m20499_stepping_stones_fwd05 | default | 4,833 | 11,469 | 547 |  | 0 | 23:29:11 |
| eval | un_e1_m20499_gap_fwd05 | default | 4,715 | 11,587 | 455 |  | 0 | 23:30:43 |
| eval | un_e1_m20499_pit_fwd05 | default | 4,738 | 11,564 | 427 |  | 0 | 23:32:09 |
| eval | un_e1_m20499_rails_fwd05 | default | 4,532 | 11,770 | 457 |  | 0 | 23:33:41 |
| eval | un_e1_m20499_star_fwd05 | default | 4,523 | 11,779 | 425 |  | 0 | 23:35:06 |
| eval | un_e1_m20499_floating_ring_fwd05 | default | 4,227 | 12,075 | 464 |  | 0 | 23:36:40 |
| eval | un_e1_m20499_repeated_boxes_fwd05 | default | 4,812 | 11,490 | 411 |  | 0 | 23:38:03 |
| eval | un_e1_m20499_repeated_cylinders_fwd05 | default | 4,809 | 11,493 | 409 |  | 0 | 23:39:25 |
| eval | un_e2_m20499_discrete_obstacles_fwd05 | default | 4,751 | 11,551 | 421 |  | 0 | 23:40:49 |
| eval | un_e2_m20499_wave_fwd05 | default | 4,782 | 11,520 | 422 |  | 0 | 23:42:14 |
| eval | un_e2_m20499_stepping_stones_fwd05 | default | 4,800 | 11,502 | 541 |  | 0 | 23:44:03 |
| eval | un_e2_m20499_gap_fwd05 | default | 4,695 | 11,607 | 466 |  | 0 | 23:45:37 |
| eval | un_e2_m20499_pit_fwd05 | default | 4,783 | 11,519 | 426 |  | 0 | 23:47:03 |
| eval | un_e2_m20499_rails_fwd05 | default | 4,822 | 11,480 | 452 |  | 0 | 23:48:34 |
| eval | un_e2_m20499_star_fwd05 | default | 4,788 | 11,514 | 420 |  | 0 | 23:49:58 |
| eval | un_e2_m20499_floating_ring_fwd05 | default | 4,426 | 11,876 | 450 |  | 0 | 23:51:29 |
| eval | un_e2_m20499_repeated_boxes_fwd05 | default | 4,246 | 12,056 | 430 |  | 0 | 23:52:55 |
| eval | un_e2_m20499_repeated_cylinders_fwd05 | default | 4,841 | 11,461 | 428 |  | 0 | 23:54:22 |
| eval | un_e1_m20000_discrete_obstacles_fwd05 | default | 4,201 | 12,101 | 422 |  | 0 | 23:55:47 |
| eval | un_e1_m20000_wave_fwd05 | default | 4,263 | 12,039 | 423 |  | 0 | 23:57:12 |
| eval | un_e1_m20000_stepping_stones_fwd05 | default | 4,756 | 11,546 | 545 |  | 0 | 23:59:01 |

