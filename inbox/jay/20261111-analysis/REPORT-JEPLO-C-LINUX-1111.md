> 분류: A/지형씬제작 · Linux 이식 검증
> 작성: 오흥재(analyst-lx) · 2026-11-11
> 근거: lead-lx 00:04 의뢰 · f2ca807c · JEPLO 460e2272 실행 preset · PR #597 0cb55619
> 요지: 기존 7종 수치 구현을 그대로 옮기고, 묶음 C 측정용 cfg 반환 함수를 더했다. CPU 37건과 원본 대조 420건 통과.
> 상태: CPU 확인됨 · PR 검토용 · 병합 안 함 · Kit 영수증 미확인

# JEPLO 묶음 C Linux 이식과 측정 호출 계약

## 이식한 범위

출발은 `origin/lead/linux-integration-1109`의 `75293ad567bbdaef63e32b163c95b3fd480b14b8`이다. `f2ca807c`에서 생성기, 기존 CPU 시험, 원본 대조 도구, 수치 명세, 당시 대조 JSON만 옮겼다. 같은 가지의 W86 보상 변경은 가져오지 않았다. **기존 생성기 240줄은 바이트까지 동일**하며 뒤에 `measurement_generator`만 더했다. 명세와 과거 결과 JSON은 당시 기록으로 보존했다. 이번 Linux 측정 요약과 해시는 [JEPLO-C-LINUX-evidence.json](JEPLO-C-LINUX-evidence.json)에 있다.

7종은 `gap`, `flat`, `box`, `discrete_obstacles`, `discrete_grid`, `pyramid_stairs`, `inverted_pyramid_stairs`다. 치수·양자화·레벨 식은 [원 수치 계약](../20261102-analysis/SPEC-JEPLO-PRESET.md) 그대로다. 9×9 m, 수평 0.08 m, 수직 0.005 m, 10레벨이다. 8 m 타일에 맞추려고 늘이거나 줄이지 않았다. GPL 원본 구현은 저장소에 추가하지 않았고, 기존 독립 구현만 이식했다.

## PR #597이 부를 계약

```python
from foothold_s2.terrains import jeplo_preset

# CPU inventory. 이름은 jeplo_ 접두어 없이 사용한다.
kinds = list(jeplo_preset.KINDS)

# Kit 초기화 뒤 cfg 생성. 반환 순서는 PR #597 _generator_for와 같다.
generator_cfg, subterrain_cfg = jeplo_preset.measurement_generator("gap", seed=42)
```

| 반환 값 | 계약 |
|---|---|
| `generator_cfg` | `TerrainGeneratorCfg`, size=(9,9), 10행×1열, 원 preset 격자·경사 문턱, cache 끔 |
| `subterrain_cfg` | 요청한 한 종류, 비중 1, kind는 접두어 없는 원 이름, seed 명시 |
| `generator_cfg.sub_terrains` | 요청 종류 하나만. 다른 종류나 8 m 생성기로 바꾸지 않음 |
| 잘못된 종류·seed | Isaac import 전에 ValueError. None·음수·bool·uint32 범위 밖 seed 거절 |

PR #597의 호출자 소유는 sonnet-code다. 그 파일을 이 PR에 복제하거나 몰래 고치지 않았다. 연결 위치는 다음 두 곳이다. 이 PR만 병합하면 #597의 C=0 목록이 자동으로 바뀌지는 않는다.

1. `buildable_kinds()`에 `"C": list(jeplo_preset.KINDS)`를 추가한다.
2. `_generator_for(family, kind)`의 C 분기에서 `return jeplo_preset.measurement_generator(kind, seed=DEFAULT_SEED)`를 반환한다. 기존 공통 8 m `rough_go2_cfg.build_generator`로 돌아가면 안 된다.

종별 치수 선언과 `physical_flag`는 #597의 기존 null 규칙을 유지한다. **원본 치수와 평가용 확대 치수는 같다고 가정해 채우지 않았다.** 생성기 확보와 선언·실측 완료는 서로 다르다.

`measure_kind_with_kit`은 cfg를 복사한 뒤 1행×1열로 만든다(`ex42_manifest.py:62`). 따라서 이 경로의 영수증은 seed에 따라 선택한 **한 타일**의 형상 해시다. 원본 10레벨 전체나 300타일 배치, 7종 통과 성능의 증거가 아니다. JEPLO의 10레벨 전체 높이장 동등성은 아래 별도 CPU oracle이 확인했다. PR #597은 그대로도 전체 manifest에 집계 실측 부족을 남기는 구조다.

## 직접 확인한 것

| 검사 | 결과 · 범위 |
|---|---|
| 이식 전 답 아는 시험 | 생성기 없는 기반에서 기존 시험 수집 실패(ModuleNotFoundError). 구현 이식 뒤 15 PASS |
| 새 호출 함수 시험 | 추가 전 14 FAIL·1 PASS(AttributeError), 함수 추가 뒤 기존 포함 37 PASS(실제 측정 소비 함수 CPU 대역 시험 7건 포함) |
| 원본 수치 대조 | 7종×10레벨×3seed×roughness 2상태 = 420건, 높이장·정점·원점 최대 차이 0 m, 삼각형 동일 |
| 실제 Isaac cfg 클래스 | 설치된 `configclass`, `SubTerrainBaseCfg`, `TerrainGeneratorCfg`를 CPU에서 읽어 7종 생성·validate·copy·to_dict·실제 trimesh 호출 통과. `class_type`만 실행하지 않는 대역으로 두었음 |
| 부작용 방지 | 전역 numpy RNG 불변, 잘못된 크기·레벨·seed 거절, 원 cfg를 유지한 채 측정 사본 변경 |
| 미실행 | Kit·PhysX·GPU 광선·메모리·실제 #597 측정 영수증·학습 환경 등록·8/9/12 m 합친 배치 |

새 pytest는 Isaac cfg 자료 껍질만 대역으로 쓴다. 실제 `configclass`와 일반 dataclass의 상속 처리 차이 때문에 첫 대역 시험 7건이 실패했고, 대역을 고친 뒤 실제 설치 클래스도 별도로 대조했다. 이를 지형 결함이나 Kit 통과로 세지 않는다.

Linux 재현 명령(작업 사본 루트, GPU 사용 없음):

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -m pytest \
  foothold_s2/tests/test_jeplo_preset.py foothold_s2/tests/test_jeplo_measurement_cpu.py \
  -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst-lx/jeplo-c-tests/recheck
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python \
  tools/verify_jeplo_cpu.py \
  --source /mnt/win-d/mai/data/foothold/s2_lab/_research_repos/JEPLO \
  --output /home/jay/mai/tmp/analyst-lx/jeplo-c-tests/oracle-recheck.json
```

원본 HEAD와 파일 바이트를 oracle이 먼저 대조한다. Python·NumPy·SciPy·trimesh 버전, 시험 로그, 설치 클래스 대조 스크립트는 `/home/jay/mai/tmp/analyst-lx/jeplo-c-tests/`에 보존한다. 사용한 공식 원본 위치는 원 수치 계약 끝의 링크다. 확인된 것은 수치 기하이며, 목표점·가장자리 마스크·JEPLO 전체 환경을 재현했다는 주장은 하지 않는다.
