# EX-42 B 묶음 시작 지지면 보완

> 분류: A/지형씬제작
> 작성: 오흥재 (scripter-lx 반영) · 2026-11-11
> 근거: mount_check_ABCDE_v3_cuda0.json · ame2_preset.py · CPU 메시 시험
> 요지: B 실패 다섯 종의 시작 지지면과 열별 reset 범위를 보완했다.
> 상태: CPU 확인됨 · Kit 재측정 대기

## 원자료와 변경

`/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/mount_check_ABCDE_v3_cuda0.json`의 `per_column.failed`에서 B 실패는 10줄이다. 열 50 stair_up L6, 51 stair_down L6·L9, 57 pallets L6·L9, 58 stones L0·L3·L9, 59 beam L6·L9이다. 이 줄들의 `zero_xy_range`는 모두 false이고 발 높이·지지 실패가 기록되어 있다.

`ame2_preset.py`는 위 다섯 종의 안전 원점을 반환하며 `RESET_RANGES`에 x·y·yaw 0을 선언한다. 결합 메시 reset 소비기 `ex42_column_reset.kind_ranges_of()`는 이 선언을 실제 전역 열의 종류에 연결한다. 계단은 마지막 진입 평탄부, beam은 기존 진입 플랫폼을 쓴다. pallets와 stones에는 x=0~0.95 m 진입 landing을 하나씩 추가했다. 좁은 발판의 폭·간격과 뒤쪽 장애물은 그대로지만 **메시 자체는 바뀌므로** 기존 v3 메시 SHA를 재사용하면 안 된다.

## CPU 확인과 남은 관문

`isaac311`에서 `test_ame2_spawn_cpu.py`와 기존 `test_ame2_preset_cpu.py` 합계 86 passed. 다섯 종의 L0·L3·L6·L9, seed 42·43 및 실제 adapter seed에 대해 0.70×0.50 m 발 지지 직사각형을 생성된 삼각형과 독립 교차해 확인했다. landing을 지운 변형은 예외로 잡혔고, 50·51·57·58·59 열만 x·y·yaw 0인 표를 확인했다.

CPU 확인은 reset 직후 실제 로봇 발 위치·몸 높이를 대신하지 않는다. 결합 메시를 이 코드에서 다시 만들고 SHA를 고정한 뒤, 열별 reset 소비기를 적용한 Kit 장착 검사를 다시 해야 한다. 위 10줄의 통과 여부는 그 전까지 미확인이다.
