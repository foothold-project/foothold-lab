# EX-42 깃발 좌표와 평가 방향 계약

> 분류: A/지형씬제작
> 작성: 오흥재 · 2026-11-11 (analyst-lx 구현)
> 근거: #665 · CG 368d03e2:241,393,394,601 · 실제 E0 메시 88197b3a · CPU 시험
> 요지: 실제 지지면에서 깃발을 만들고, 같은 평가 계단을 옆·대각으로 통과하는 계약을 추가했다.
> 상태: CPU 확인됨 · GPU/Kit 및 평가 실행기 전체 연결은 별도 확인
> 판: v0.1

## 1. 바뀐 것과 경계

R11 · M30 · M38 적용: 정본의 지형 치수와 이미 측정한 메시를 보존하고, 재지 않은 Kit 결과를 PASS로 쓰지 않는다.

`ex42_mesh_build.py:192`의 생산자는 실제 생성된 삼각형에서 `(줄,열,4,2)` 세계 좌표를 계산한다. #657 `MeshFlagProvider`의 입력과 일치한다. 난수를 다시 뽑지 않는다. 미래 빌드는 같은 함수로 flags를 함께 저장한다. 기존 메시에는 `tools/ex42_mesh_flags.py:29`로 **새 폴더**에만 추가할 수 있다. 원본 NPZ·승인·학습 프로세스를 바꾸지 않았다.

현재 E0 실제 메시: 10행 × 76열. A 연속 230칸은 전체 NaN으로 기존 직선 경로를 유지한다. A 듬성·보조 평지 및 B~E 530칸에 좌표 4개씩, 총 2,120개가 있다. 일부 좌표만 NaN인 칸이나 지지면을 찾지 못한 칸은 오류로 중단한다. B~E가 조용히 직선으로 바뀌는 길은 없다.

| 묶음 · 종류 | 깃발 규칙 | 등급 · 근거 |
|---|---|---|
| A 연속 7종 | 기존 직선 fallback 그대로 | 코드 · CG:241, columns.CONTINUOUS |
| A stepping_stones_low/high · balance_beams · stepping_beams · gaps · flat | 기존 FLAG_X를 실제 지지면으로 투영. 구덩이 바닥 제외 | 코드 + 배치 가정 · sparse_terrains.py:25, start_go2_v2.py:129 |
| B stair_up/down · rough · boxes · climb_up/down · consecutive | 시작점 이후 x 증가 목표 4개를 실제 표면에 투영 | 배치 가정 · AME-2가 발표한 경유점이라고 주장하지 않음 |
| B gap · pallets · stones · beam | 같은 목표, 전체 타일을 덮는 물리 구덩이 바닥이 있으면 제외. 가상 구덩이는 실재 받침만 | 코드 + 배치 가정 · ame2_preset.mesh_arrays |
| B obstacles | 실제 장애물 아래의 가려진 바닥을 제외하고 노출된 바닥을 선택 | 배치 가정 · 완전한 충돌 회피 경로는 아님 |
| C gap | 실제 높이가 −0.15 m보다 높은 표면에서만 선택. 원본 깊이 −1~−2 m 바닥 제외 | 코드 + 배치 가정 · jeplo_preset._gaps |
| C flat · box · discrete_obstacles · discrete_grid · pyramid_stairs · inverted_pyramid_stairs | 안전 시작점 이후의 실제 표면에 x 증가 목표 4개 | 배치 가정 |
| D high_ledge | 낮은 바닥에서 높은 받침으로 이어지는 실제 표면 | 배치 가정 |
| D wall | 실제 벽 끝에서 +y 우회 통로 중앙을 통과한 뒤 중심선으로 돌아옴 | 배치 가정 · hipan_posture의 기존 벽/통로 치수를 읽음 |
| D crawl | 지붕 윗면이 아니라 시작점과 같은 높이의 바닥 | 코드 + 배치 가정 · 기존 천장 여유 0.30→0.25 m 보존 |
| E slope_steep/ inv · stairs_high/ inv | 시작점에서 +x로 진행하는 실제 표면 4곳 | 배치 가정 · 지형 치수는 ex42.PAPER_EXT_SPECS 그대로 |

공통 배치 가정: B~E의 기본 목표는 시작점 x+0.5부터 타일 끝−0.75 m까지 4개다. 가까운 실제 표면을 고르고 삼각형 중심 쪽으로 1% 옮겨 정확한 모서리를 피한다. 이는 발 전체가 놓일 여유, 장애물 없는 연속 경로, 도약 가능성을 보증하지 않는다. 실제 경로 완주는 종류별 평가와 영상으로 확인해야 한다. A 듬성의 지지점 투영도 이전 SideTable의 좌표와 비트 동일하다는 주장은 하지 않는다.

## 2. 원자료 확인

- CPU 시험 **95 PASS**: flags 생산/소비, world offset 한 번, 기존 필드 보존, 잘못된 지형 거절, pit 제외, crawl 바닥, wall 우회, B/C/D 전 종류 L0·L5·L9, 실제 Isaac 난수 커널, 평가 기하/방향/판정 역할.
- 실제 E0 메시 전체: 독립 `trimesh` ray/triangle 교차로 2,120개 좌표의 지지 높이를 다시 읽음. 아래 차이는 좌표를 float32로 저장한 뒤의 높이 차이이며 허용 0.0001 m로 시험했다.
- 이 검사는 Kit 장착 검사나 로봇 보행 성공 시험이 아니다.

| 묶음 | 검사 좌표 수 | 불일치 수 | 최대 높이 차 m |
|---|---:|---:|---:|
| A | 1080 | 0 | 0.000000000 |
| B | 480 | 0 | 0.000089307 |
| C | 280 | 0 | 0.000009621 |
| D | 120 | 0 | 0.000000000 |
| E | 160 | 0 | 0.000013215 |

원자료: `/home/jay/mai/tmp/analyst-lx/flag-rays-final-1111.json`.
재계산 코드: `inbox/jay/20261111-analysis/verify_flag_rays.py`.
시험 로그: `/home/jay/mai/tmp/analyst-lx/flag-eval-suite-1111.log`.

| 산출 | 값 |
|---|---|
| 깃발 추가 사본 | `/home/jay/mai/tmp/analyst-lx/seed42_E0_c333_flags_1111` |
| 기하 SHA, 원본과 동일 | `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95` |
| 새 NPZ SHA | `59b0bf3e3023f40da828b86eebff4513222e13452c70fc49b8951d7e8d42d771` |
| 깃발 배열 SHA | `f58819fcc9a109ad05dcf6581624dfaf0a3dc5986faab93a4f053a76368d7207` |
| 메시 manifest SHA | `6ca62db95b94564d70178fc7017c226d4c4eba9d345e80bca7ef6759572e2ad2` |
| 깃발 계산 실측 | 8.481초 CPU |

기존 aggregate는 원본에서 물려받은 측정임을 `flag_annotation_source.measurements_inherited=true`, `new_kit_validation=false`로 남겼다. 기존 형상·원점 필드의 동일성은 시험으로 확인했다. 새 파일에는 새 SHA가 있으므로 실행 승인/부모 핀을 몰래 기존 값으로 통과시킬 수 없다. 실행용 `terrain_manifest.json`은 #620 도구로 새로 생성한다. 통합 plan이 바뀌면 그 plan으로 다시 고정해야 한다.

같은 새 폴더의 실행 manifest도 현재 가지 prep과 선언 `083e6e70`으로 생성했다. `status=measured`, 46행, 누락 0, `validate_terrain_manifest` 통과. SHA는 `3bb8a05516080fcc34a42755760ab650036a59f595163f4a6d7bc0126eb6122e`다. 학습 승인 변경은 하지 않았다.

## 3. E2~E5 평가 전용 열

기존 32개 고정 기하를 재사용한다. START 변형 12개는 틈 ×1.15, 지지면 ×0.85, 둘 다의 3변형 ×4종이다. 각 종류의 terrain seed는 변형끼리 같다. 평가용 계단 높이·경사 각·기록 상한은 바꾸지 않았다.

`ex42_eval_records.py:23`에 계단 0.15·0.20·0.25 m 각각 옆 ±, 전진 대각 ±, 후진 대각 ±의 6개를 추가했다. 18개 모두 **record**다. CG:394와601이 근거이며, 시작 yaw 회전은 같은 코스를 비교하기 위한 배치 가정이다.

- `body_command_xy_unit`는 몸 기준 단위 방향, `approach_yaw_rad`와 곱하면 세계 +x로 간다.
- 시작은 `approach`, 끝은 `course_exit=[7.5,4,0]`. 같은 오르막·내리막 기하를 통과한다.
- 속도 크기와 시간 한도는 평가 실행기가 정본 명령 계약으로 공급해야 한다. 생성기가 숫자를 지어내지 않았다.
- 기존 32기하 + 후진 별칭 2 + 새 방향 18 = 52개 case metadata. 역할을 바꿔도 되는 새 승인은 아니다.
- E4 judge는 기존 경사 30/35°, 계단 0.15/0.20/0.25 전진, 0.10 후진 그대로다. D44는 E1 judge 그대로다.

새 manifest: `/home/jay/mai/tmp/analyst-lx/eval32_directions_seed42_1111/mesh_manifest.json`.
기하 SHA `057b6a292681f95bf669e8c1213d51f4e1e74bdacee02a05d07aca73a7ffc01a`, NPZ SHA `d5e8a2956ee8c7f6e96ba26b41ffb19b415aeb6a17c969379f26b03fdedfee0b`: 이전 all32 산출과 동일하다. 새 시작점 CPU 검사 32/32 통과. manifest만 방향·앵커 정보가 추가됐다. GPU 장착은 lead 슬롯에서 확인한다.

## 4. D44 여섯 칸에 쓰는 앵커

scripter 전달 자료: `/home/jay/mai/tmp/analyst-lx/D44-SIX-ANCHORS-1111.json`.
run 전달: `msg_111e1a9d143f` · 정지 높이 재확인 `msg_04978d44dd9b`.

| 과제 | 시작 앵커 | 실제 표면 m | 주의 |
|---|---|---:|---|
| 계단참 좌회전 | landing_center [4,4,1.44] | 1.44 | 참 경계 x/y 3.4~4.6 |
| 계단참 우회전 | 같은 앵커 | 1.44 | 좌우가 같은 기하 |
| 계단에서 정지 후 재출발 | approach [0.5,4,0]에서 걸어서 stop_band x1.6~1.9로 | **0.48** | x1.61/1.75/1.89의 실제 NPZ 광선 높이 모두 0.4799999893 |

각 과제를 pinned prep의 승인된 지도 두 모드에 재사용한다. 모드를 생성기에서 다시 정하지 않는다. 좌표 z는 지면 높이이며 몸통 초기 높이를 한 번만 더한다. 새 manifest는 `stop_band_interior_surface_z_m`도 제공한다. 0.32 m는 직전 디딤면 높이이므로 정지 band 내부와 혼동하면 안 된다.

## 5. 이어받을 소비자 확인

| 항목 | 준비 | 다음 확인 주인 |
|---|---|---|
| flags를 NPZ에서 명령까지 | #657과 CPU roundtrip 확인 | sonnet/runner: 실제 E1F 환경에서 선택된 열·행·세계좌표 영수증 |
| 새 NPZ 승인 핀 | 새 SHA와 원본 기하 보존 증거 준비 | lead/verifier: 통합 실행 plan·manifest·승인 핀 고정 |
| 평가 방향 metadata | 52 case 준비, 방향 변환 CPU 확인 | scripter: 해당 yaw·몸 기준 방향·속도·시간 소비 및 완료 기준 |
| D44 | 실제 앵커·정지 높이 전달 | scripter: 6 case 설정·지면 z·root offset 소비 |
| Kit 장착 및 실제 학습 | 이번 작업에서 미실행 | lead가 E1 종료 뒤 슬롯에서 확인 |

연속 학습 전체가 준비됐다고 판정하는 문서가 아니다. 맡은 생성기·원자료 계약의 검증 범위와 소비자의 남은 확인을 구분했다.

## 6. 재현 명령

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m pytest -q -p no:cacheprovider foothold_s2/tests/test_ex42_flag_producer_cpu.py foothold_s2/tests/test_ex42_flags_cpu.py foothold_s2/tests/test_ex42_combined_mesh_cpu.py foothold_s2/tests/test_ex42_mesh_rng_cpu.py foothold_s2/tests/test_ex42_eval_records_cpu.py foothold_s2/tests/test_ex42_eval_terrains_cpu.py
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.tools.ex42_mesh_flags --source /mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333 --out /home/jay/mai/tmp/analyst-lx/NEW_UNIQUE_FLAGS_FOLDER
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /home/jay/miniforge3/envs/isaac311/bin/python inbox/jay/20261111-analysis/verify_flag_rays.py /home/jay/mai/tmp/analyst-lx/seed42_E0_c333_flags_1111 --out /home/jay/mai/tmp/analyst-lx/NEW_RAY_REPORT.json
```

정본 링크: [CURRICULUM-GATES 고정판](https://github.com/foothold-project/foothold-lab/blob/368d03e2061b505fc72ad73e9cd2527a766e7738/inbox/jay/20261026-experiments/CURRICULUM-GATES.md#L392). 작업 [#665](https://github.com/foothold-project/foothold-lab/issues/665).

| 판 | 변경 |
|---|---|
| v0.1 | 실제 메시 깃발 생산·원자료 ray 교차·방향별 평가 metadata·D44 앵커 인계 |
