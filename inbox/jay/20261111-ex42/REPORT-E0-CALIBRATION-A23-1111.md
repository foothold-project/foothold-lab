# EX-42 E0 calibration 고정 평가 칸

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (lead · scripter-lx 반영) · 2026-11-11
> 근거: EX-41 m12000 부모 map64 영수증 · E0 c333 메시 · lead-lx 05:35 결정
> 요지: 물리 메시 76열 가운데 A 연속 23열만 평가 칸에 배정하여 부모의 64 env 배정과 일치시켰다.
> 상태: CPU 확인됨 · Kit 미실행

## 원자료 대조

- 부모: `/mnt/win-d/mai/data/foothold/s2_lab/ex41_main_20261104_235522/eval/linux-baseline-1110/m12000/evaluation/map64/map_modes.json`. `terrain_set=default`, `fixed_terrain.cols=23`, 64 env. Planner가 읽은 50열은 이 영수증의 배정이 아니다.
- 메시: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333/terrain_mesh.npz`. 전체 76열, SHA256 `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95`.
- 실측: 부모와 새 배정의 `(kind, level, column)` 64/64 일치. 배정 SHA256 양쪽 모두 `c3884d686592596ee6ac7b2cdfc94e0b1d3f6d84dbca66c52ad20a0400e2358f`. 레벨별 env 수는 L0 23 · L1 23 · L2 18.

## 변경과 관문

- `ex42_mesh_eval` 영수증에 평가 열 23과 이름 배열을 분리했다. 실제 메시 76열과 각 열의 reset 설정은 유지한다.
- map64 독립 명령 · sequence · W57 axis가 모두 같은 23열 배정을 쓴다. 기존 기본 평가 경로는 물리 열 수를 그대로 쓴다.
- 점수기는 메시 평가의 열 수 · 배정 SHA · env별 타일을 확인한다. 76열 참고 판은 calibration으로 받지 않는다. 다섯 반복 집계도 영수증의 23열 표식을 요구한다.
- `isaac311` CPU 시험 39 passed. 실제 c333 메시와 부모 영수증을 직접 읽는 시험을 포함했다. GPU · Kit 재평가는 하지 않았다.

## 한계

같은 `(kind, level, column)` 배정은 확인했지만 새 메시의 기하가 부모와 같다는 주장은 아니다. E0 기준 수치는 이 판으로 다시 측정해야 한다. 현재 도는 76열 판은 참고용이다.
