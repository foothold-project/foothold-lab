# EX-42 E0 메시 위 m13000 반복 폭 평가 준비

> 분류: A/평가
> 작성: 오흥재 · 2026-11-11
> 근거: EX-42 점수 설정 · ex42_eval_once.py · ex42_mesh_mount.py · 실제 E0 메시 manifest
> 요지: E0 합친 메시와 열별 reset으로 다섯 번 평가해 관리 항목별 반복 폭을 남기는 입구를 만들었다.
> 상태: CPU 사전검사 통과 · Kit 측정 미실행

## 발견과 변경

기존 `ex42_eval_once.py`는 EX-41 작업의 기본 지형을 썼다. `eval_map_modes.py`도 생성기의 `sub_terrains`만 읽으므로 합친 E0 메시 설정은 받을 수 없었다. `--mesh-dir`를 추가해 메시 manifest와 삼각형 SHA, 10행 × 76열, A~E 가족을 확인한다. 지도 모드와 W57 자식은 같은 메시를 장착하고, `ex42_column_reset.build_column_table`의 종류별 reset 범위를 적용한다. 실제 열 이름은 메시의 `column_family`와 종류 표에서 읽어 영수증에 남긴다. 기존 정지 평가는 정의상 **평면 z=0**이며, 영수증에 이 차이를 적는다.

`ex42_calibrate.py`는 시드 `[42, 42, 43, 44, 45]`로 다섯 평가를 별도 폴더에 순차 실행한다. `calibration.json`은 저장본 · 소스 HEAD · 메시 SHA · 시드 · 완료 영수증을 대조한 뒤에만 쓴다. 각 원수치의 같은 시드 두 번 차이와 전체 다섯 번 범위를 기록하고 관리 항목별 폭을 모은다. `parent_cumulative_drop`은 부모 저장본이 없는 단일 m13000 반복 실험에서 측정할 수 없다고 남긴다. 수치 판정 문턱은 만들지 않았다.

## lead 실행 명령

새 통합 코드로 **다시 만든** 10×76 E0 메시의 `mesh_manifest.json`과 `terrain_mesh.npz` 폴더를 `MESH_DIR`로 지정한다. 예전 `seed42_ABCDE_v3`는 CPU 계획 시험에만 썼고 정식 calibration 입력으로 확정하지 않았다. 실제 manifest의 `mesh_sha256`을 `MESH_SHA`로 핀한다. `OUT`은 없는 새 폴더여야 한다.

```bash
cd /home/jay/mai/wt/foothold-lab/<이 PR을 고정한 사본>
MESH_DIR=/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/<새 통합 메시 폴더>
MESH_SHA=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mesh_sha256"])' "$MESH_DIR/mesh_manifest.json")
OUT=/home/jay/mai/tmp/lead/ex42-calibration-e0-m13000
bash foothold_s2/scripts/ex42_calibrate_e0.sh "$MESH_DIR" "$MESH_SHA" "$OUT" cuda:1
# 계획 다섯 명령과 핀 확인 뒤, lead가 같은 줄 끝에 --execute를 붙여 실행
```

`foothold_s2/scripts/ex42_calibrate_e0.sh`는 m13000 실제 저장본 SHA `20365a2c…`를 확인하고 `isaac311` · PCI GPU 순서 · EULA 환경을 전달한다. `--execute` 없이 실행하면 GPU를 쓰지 않고 다섯 명령만 출력한다.

## CPU 검증과 남은 관문

- CPU 시험: `36 passed`, 원출력 `/home/jay/mai/tmp/scripter/ex42-calibration/test-final.log`.
- 실제 보유 중인 `seed42_ABCDE_v3`로 계획을 읽었을 때 5건 · 시드 `42,42,43,44,45`; 틀린 메시 SHA는 실행 전 거절했다. 계획 원출력 `/home/jay/mai/tmp/scripter/ex42-calibration/plan.json`.
- 아이작 자식의 실제 Kit 실행과 m13000의 새 E0 메시 점수는 아직 미측정이다. GPU 실행은 lead가 맡는다.
