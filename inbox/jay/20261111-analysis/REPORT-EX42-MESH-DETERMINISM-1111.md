# EX-42 메시 생성 결정성 복구
> 분류: A/지형씬제작
> 작성: analyst-lx · 2026-11-11 11:21
> 근거: 팀장 11/11 11:12 지시 · #635 · 실제 A 함수 CPU 반례 · 저장 NPZ 비교
> 요지: 생성 앞 NumPy·PyTorch 전역 seed를 고정하고 소비한 난수 상태와 NPZ 파일 SHA를 영수증에 남겼다.
> 상태: CPU 관련 62 PASS · 전체 39종 Kit/CUDA 반복 생성은 미실행 · PR 검토 대기

## 결정과 범위

E1은 E0 메시 `seed42_E0_c333`을 그대로 쓴다. mesh SHA `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95`, terrain_manifest SHA `39145e734002859dfc384d3e010c6d3115056d8ce01b341d561499b23a7f50bd`. 이번 변경은 E2 전 생성 재현 결함을 고친다. 기존 메시·학습·실행 설정은 고치지 않았다. 기반은 `9e93f3e4cccf6ce102d2859d8e1f575e5a6c3cb8`.

## 원인과 변경

A boxes는 PyTorch 전역 `uniform_`, random_rough는 NumPy 전역 `choice`를 쓰지만 기존 cfg.seed는 TerrainGenerator의 별도 np_rng만 고정했다. 실제 E0/E1 메시에서 A 연속 23열 중 8열이 바뀌었다. boxes 정점 차 최대 0.178410903 m · 전체 평균 0.013791943 m, random_rough 최대 0.049999999 m · 평균 0.016665003 m다. XY와 A 원점은 같았다. B는 A 뒤 생성되고 전용 default_rng를 쓰므로 #617 B 입구 수정의 공용 난수 소비 영향은 아니다.

- `foothold_s2/terrains/mesh_rng.py`: NumPy legacy · Torch CPU · 실제 boxes가 사용하는 **현재 CUDA 장치**를 같은 seed로 고정한다. 다른 GPU를 초기화하거나 다시 seed하지 않는다. 성공·실패 모두 호출자의 난수 상태로 복원한다.
- `foothold_s2/scripts/ex42_mesh_build.py`: 첫 묶음 cfg 생성 전부터 마지막 묶음 생성까지 위 context를 사용한다. 생성 직전·직후 전체 난수 상태를 `rng_provenance`에 기록하고, 저장된 NPZ 전체 파일의 `mesh_file_sha256`도 기록한다.
- NumPy 상태는 MT19937 키·위치·Gaussian 캐시, Torch 상태는 uint8 base64 + SHA256. 복원 가능한 원상태이며 단순 seed 이름만 남기는 기록이 아니다.
- `geometry_rng_device`는 실제 기본 CUDA 장치다. 기존 측정용 `device` 인자와 구분한다. 이 PR은 장치 배정 정책을 바꾸지 않는다.
- `mesh_sha256`은 기존대로 vertices+faces 해시를 유지한다. 새 파일 해시는 origins·column_family·NPZ 포맷까지 포함한다.

## 시험

[기계 판독 증거](evidence/ex42-mesh-determinism-cpu.json).

| 시험 | 결과 |
|---|---|
| 수정 전 답을 아는 회귀 입력 | NPZ 불일치 · 난수 영수증 누락 · 실패 후 상태 복구 누락, 3 FAIL |
| 수정 후 관련 CPU 시험 4파일 | 62 PASS · 0 FAIL · 0 SKIP |
| 같은 seed 42, 바깥 NumPy/Torch 상태만 다르게 | NPZ SHA 동일 |
| seed 43 | 다른 NPZ SHA |
| NumPy seed 고정 제거 돌연변이 | NPZ 동일성 시험 실패 |
| Torch seed 고정 제거 돌연변이 | NPZ 동일성 시험 실패 |
| 상태 기록 JSON 왕복 | NumPy/Torch 다음 난수까지 복원 일치 |
| 생성 중 예외 | 원래 NumPy/Torch 상태 복원 · 성공 영수증 없음 |
| 현재 CUDA 장치 계약 | CPU generator 대역으로 seed·기록·복원 확인, 다른 장치 seed 호출 거절 |

| CPU 생성 판 | seed | NPZ SHA256 |
|---|---:|---|
| first | 42 | `5f877f9b7ce0d28f03ace82fe1c7d994c6e559b211909dbb3a6d3af68ed1efc2` |
| second | 42 | `5f877f9b7ce0d28f03ace82fe1c7d994c6e559b211909dbb3a6d3af68ed1efc2` |
| different | 43 | `50236cf0d627165cd233ab7b14c36106aec5a38f6314e6b66ecceba9c49d9414` |

시험 명령:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m pytest \
  foothold_s2/tests/test_ex42_mesh_rng_cpu.py \
  foothold_s2/tests/test_ex42_combined_mesh_cpu.py \
  foothold_s2/tests/test_ex42_execution_manifest_cpu.py \
  foothold_s2/tests/test_ex42_kit_measure_cpu.py \
  -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst-lx/mesh-determinism-1111/pytest-final
```

**검증 한계:** 일반 CPU Python의 TerrainGenerator import는 `pxr` 누락으로 불가했다. 그래서 설치된 실제 boxes·random_rough 함수 본문을 AST로 실행하고, 운영 `build_and_measure`의 실제 메시 결합·NPZ 저장 경로를 시험했다. Kit 배치기와 GPU 측정만 대체했다. 이는 전체 39종 메시나 실제 CUDA 커널을 두 번 돌린 증거가 아니다. E2 전에 고정 코드·장치에서 전체 메시를 두 번 생성하여 `mesh_file_sha256`와 `mesh_sha256` 일치를 확인해야 한다. CPU와 CUDA, 의존성 판이 다른 실행의 동일 바이트는 보장하지 않는다.

난수 상태가 기록되지 않은 과거 E0의 A 기하는 seed 42를 새로 고정한다고 복원되지 않는다. E0 기하가 필요하면 기존 파일을 사용한다. 영수증의 생성 시간 등은 매번 달라질 수 있으므로 영수증 파일 전체가 아니라 NPZ 파일 및 메시 해시를 비교한다.

## 원자료

- 원인 보고: `/home/jay/mai/tmp/analyst-lx/REPORT-E1-A-GEOMETRY-RNG-1111.md`
- 정점 대조와 실제 함수 반례: `/home/jay/mai/tmp/analyst-lx/e1-a-rng-1111/`
- 이번 red/green/final 및 돌연변이 로그: `/home/jay/mai/tmp/analyst-lx/mesh-determinism-1111/`
- [이슈 #635](https://github.com/foothold-project/foothold-lab/issues/635)
