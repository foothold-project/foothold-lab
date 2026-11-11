# EX-42 점프 지형 묶음 F · CPU 생성과 결정성

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: 팀장 19:38 결정 7121e018 · DESIGN-JUMP v0.2 §2.2 · 코드 fa8372d9 · CPU 원자료
> 요지: J2 오르기·내려오기, J3 틈, J4 높은 턱의 메시·깃발·출처 기록을 만들고 두 번 빌드의 파일 해시를 대조했다.
> 상태: CPU 검증 완료 · Kit 장착과 물리 보행 미확인 · 기존 학습 설정 미변경
> 판: v0.1

`확인됨`: 이번 범위의 CPU 막음은 0이다. **생성기를 만든 것과 로봇이 그 장애물을 넘는 것은 다르다.** 학습·GPU·Kit은 실행하지 않았다. F를 기존 학습에 노출하는 비율이나 승급 규칙도 바꾸지 않았다. analyst-lx가 19:55에 정리했다.

## 1. 만든 지형과 치수 출처

[DESIGN-JUMP v0.2 §2.2](https://github.com/foothold-project/foothold-lab/blob/368d03e2061b505fc72ad73e9cd2527a766e7738/inbox/jay/20261104-jump/DESIGN-JUMP-draft.md#L99)의 사다리를 그대로 읽었다. 정본에서 가정으로 제시한 단계 치수이며, 이번 생성 지시의 대상이다. 논문 실측 수치라는 뜻은 아니다.

| 순서·종 이름 | 과제 | 물리 레벨별 높이 또는 폭(m) | 바뀌는 축 | 등급 |
|---|---|---|---|---|
| F 열 0 · `jump_up_low` | J2 낮은 턱 오르기 | 0.10, 0.20, 0.30 | 높이 | 설계·이번 지시 |
| F 열 1 · `jump_down_low` | J2 내려오기 | 0.10, 0.20, 0.30 | 내려갈 높이 | 설계·이번 지시 |
| F 열 2 · `jump_gap` | J3 같은 높이의 틈 건너기 | 0.15, 0.30, 0.45, 0.60 | 틈 폭 | 설계·이번 지시 |
| F 열 3 · `jump_up_high` | J4 높은 턱 오르기 | 0.40, 0.50, 0.60, 0.65, 0.70, 0.75 | 높이 | 설계·이번 지시 |

코드 정본은 `foothold_s2/terrains/jump_preset.py:15`의 `KINDS`, `LEVEL_VALUES_M`이다. 오르기와 내려오기는 서로 다른 종이다. J5의 넓은 틈·J6 연결 과제는 이번 범위에 포함하지 않았다. 걸어 넘거나 기어오르는 전략을 메시가 제한하지 않는다.

다른 묶음과 열로 붙일 수 있도록 **10행×4열**에 담았다. 물리 레벨은 각각 **3·3·4·6개**, 총 16개이다. 그 뒤 행은 최고 레벨의 반복이며 새 난이도가 아니다. 예를 들어 `jump_up_high`의 행→물리 레벨은 `[0,1,2,3,4,5,5,5,5,5]`이다. 소비자는 manifest의 `row_physical_levels`를 사용해야 한다. 같은 높이의 다음 행으로 올라간 것을 새 높이를 배웠다고 세면 안 된다.

## 2. 설계에 없던 배치 값은 구현 가정으로 분리

| 항목 | 값 | 이유·한계 |
|---|---|---|
| 타일 길이×폭 | 8×8 m | 기존 A·D·E 계열의 운반 격자 크기와 맞춘 구현 가정 |
| 장애물 위치 | 타일 x 중앙, 기본 x=4 m | 접근과 착지·회복 공간을 두는 구현 가정 |
| 턱·틈의 y 폭 | 타일 전체 폭 | 같은 타일 안 옆 우회로를 만들지 않음. 타일 밖 우회 판정은 평가기 몫 |
| 틈 바닥 깊이 | 1.0 m, 모든 폭에서 고정 | 유한한 실제 바닥을 두는 구현 가정. 바닥 접촉을 성공으로 세면 안 됨 |
| 바닥 두께 | 0.10 m | 닫힌 상자 메시를 만드는 구현 가정 |
| 시작 XY | (1, 4) m | 장애물 전 넓은 지지면 |
| 시작 z | 내려오기만 해당 턱 높이, 나머지 0 m | 실제 발 아래 받침 높이. 로봇 몸통 높이가 아님 |
| reset 범위 | 기존 x/y ±0.5 m·yaw ±3.14 rad 유지 | 새로운 yaw 제한을 도입하지 않음 |
| 지지면 검사 사각형 | 0.70×0.50 m | 앞선 묶음 장착 검사의 지지면 계약을 재사용. 실제 관절 로봇을 놓은 시험은 아님 |

`layout_assumptions`에 위 값을 출처 등급과 함께 넣었다. `build_tile`은 타일 길이 8 m·폭 4 m 미만, 잘못된 레벨·seed·NaN 치수를 거절한다. 기본 크기에서 reset XY 흔들림과 사각형 회전을 모두 덮는 반경은 `0.5 + hypot(0.35,0.25)` m이다. 이 영역은 시작 지지면 안에 있다.

메시는 높이장 격자 보간 없이 닫힌 상자로 만든다. 저장할 때 정점은 기존 계약대로 float32가 되므로 아주 작은 반올림 오차가 남는다.

## 3. 메시·깃발·원점 소비 계약

| 인터페이스 | 계약 |
|---|---|
| `jump_preset.build_tile(kind, level, seed=...)` | 순수 CPU 치수·상자·원점 |
| `jump_preset.build_generator(kind=..., seed=...)` | 종별 Isaac 설정. Kit에서 사용하는 선택적 factory |
| `jump_preset.build_family_generator(seed=...)` | 10행×4열, 기존 `ex42_mesh_build --family F` 연결 |
| `jump_preset.measurement_generator(kind, seed=...)` | 종별 측정용 `(generator_cfg, subterrain_cfg)` |
| `python -m foothold_s2.tools.ex42_jump_mesh` | GPU 없이 저장 메시·manifest·CPU 지지면 영수증 생성 |
| `terrain_mesh.npz` | `vertices`, `faces`, `origins (10,4,3)`, `column_family`, `flags (10,4,4,2)` |
| `flags` | world XY. 각 타일 로컬 XY는 (2,4), (3,4), (5,4), (7.25,4) m |
| `ex42_column_reset` | F 열을 위 네 종 순서로 찾고 기존 reset 범위를 소비 |

깃발 앞 둘은 접근 지지면, 뒤 둘은 넘어간 뒤 지지면이다. 이륙 시각·발 디딜 위치·도약 궤적을 명령하는 값은 아니다. 실제 삼각형으로 깃발 아래를 검사하며, 틈 바닥이나 지지면이 없는 곳을 목표로 선택하면 오류를 낸다.

기존 `load_combined_mesh`, `load_flag_table`, `MeshFlagProvider`로 F 산출물을 읽는 CPU 시험을 통과했다. A~E 기본 선택은 그대로이며 `--family F`를 명시해야 추가된다. 기존 A~E 메시와 원자료를 수정하지 않았다. 전체 묶음에 붙일 때 F를 마지막에 넣으면 앞 묶음의 위치가 변하지 않는 기존 결합 방식을 따른다.

CPU 격자의 중심 이동 방식은 설치된 Isaac Lab `terrain_generator.py:183`, `:333`, `:383`과 대조했다. **Isaac factory를 Kit에서 실행한 대조는 미확인**이다. 저장 NPZ의 실제 지지면은 아래 CPU 광선 검사로 별도 확인했다.

## 4. 실측과 답을 아는 시험

원자료는 저장소 밖 `/home/jay/mai/tmp/analyst-lx/jump_f_seed42_1111/build1`과 `build2`에 있다. 전달용 메시·manifest는 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_F_jump_fa8372d9`이며, 이 폴더의 네 파일 해시도 두 빌드와 모두 같다. 저장소에는 [해시와 실측 요약](evidence/jump-f-cpu-1111.json)만 넣었다.

| 확인 | 결과 | 등급 |
|---|---|---|
| 독립 프로세스 두 번, seed 42 | NPZ·mesh manifest·terrain manifest·CPU 지지면 영수증 각각 바이트 SHA 일치 | CPU 실측 |
| NPZ SHA256 | `1465a55cb366df7b3821dba427e04a7272b7234c1c063982296a93875db7f6b9` | CPU 실측 |
| 정점·면만의 geometry SHA256 | `eaa6476310d494a3707eee92bdd0a2e4ec3c634768a1eeff4cdc2fdeb1fc58eb` | CPU 실측 |
| 정점·삼각형 | 720·1,080개 | 저장 NPZ 실측 |
| 시작 지지면 | 40칸·360개 광선, 원점 높이와 최대 차 1.1921e-8 m | float32 메시 CPU 실측 |
| 깃발 지지면 | 40칸·160개 광선, 예상 접근·착지 높이와 일치 | CPU 실측 |
| NumPy·Torch 전역 RNG | 생성 전후 상태 동일 | CPU 시험 |
| CPU 회귀 묶음 | 72 PASS·0 FAIL | CPU 시험 |
| Kit 장착·GPU 메모리·깊이 카메라·실제 Go2 동작 | 미실행·미확인 | 측정 없음 |

NPZ ZIP 항목의 시각도 모두 1980-01-01로 고정되어 있다. 같은 초에 빌드해서 우연히 ZIP 시각이 같았다는 비교가 아니다. 재현 범위는 같은 코드·NumPy 1.26.0·trimesh 4.5.1 환경이다. **다른 seed를 주어도 F의 물리 형상은 같다.** 난수 지형 변형을 넣지 않았으므로 이를 독립 지형 표본이라고 부르면 안 된다.

답을 아는 입력으로 실제 높이와 틈 양 모서리를 쟀다. 추가 반례는 내려오기 원점을 0으로 낮춘 경우, 착지면을 없앤 경우, 깃발을 틈 가운데로 옮긴 경우이다. 모두 지지면 검사가 거절했다. 기존 메시·깃발·reset·난수 코드의 회귀 시험도 포함했다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m pytest foothold_s2/tests/test_jump_preset_cpu.py foothold_s2/tests/test_ex42_flag_producer_cpu.py foothold_s2/tests/test_ex42_flags_cpu.py foothold_s2/tests/test_ex42_combined_mesh_cpu.py foothold_s2/tests/test_ex42_column_reset_cpu.py foothold_s2/tests/test_ex42_mesh_mount_cpu.py foothold_s2/tests/test_ex42_mesh_rng_cpu.py -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst-lx/jump-f-review
```

## 5. 재생성과 남은 연결

CPU 재생성 명령이다. 기존 결과를 덮지 않으므로 `--out`에는 새 폴더를 넣는다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.tools.ex42_jump_mesh --seed 42 --out /home/jay/mai/tmp/analyst-lx/jump_f_seed42_reproduce
```

`mesh_manifest.json`과 `terrain_manifest.json`은 `status=cpu_generated`이다. GPU 측정값·학습 승인·실측 receipt를 만들어 넣지 않았다. 기존 `EX42Plan.validate_terrain_manifest`가 이 결과를 `not measured`로 거절하는 시험도 통과했다.

현재 EX-42 실행 prep과 측정 inventory는 A~E를 대상으로 한다. F의 최종 학습 노출·승급 및 정식 measured manifest 계약은 해당 단계 연결에서 확장해야 한다. 이번 PR은 그 규칙이나 승인 파일을 임의로 바꾸지 않는다. 순서는 **F 기하 CPU 준비 → 승인된 슬롯에서 Kit 장착·측정 → F 단계 계약·승인 대조 → 노출**이다. 좁은 의미의 CPU 준비 완료를 학습 시작 가능 판정으로 읽지 않는다.

## 이력

| 판 | 변경 |
|---|---|
| v0.1 | J2·J3·J4 네 종류, 16개 물리 레벨, 40칸 메시·깃발·결정성·CPU 지지면 증거 |
