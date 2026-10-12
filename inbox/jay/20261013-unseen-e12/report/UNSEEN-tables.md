### 표 U-1 · 지형별 · 생존 / Q1 추종 / Q3 (4 m 통과선 · 통로 0.30 m) / 건넘 · % (100 판씩, noise 끔, 난이도 0.5)

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

### 표 U-2 · 낙상 원인과 진행 거리 중앙값 (m)

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
