# 작업서 05 · 지면 메시 → Isaac Lab 용 충돌체 USD (저장 뒤 다시 열어 검증)

> 분류: 계획
> 작성: 오흥재 · 2026-09-16 15:00
> 근거: RESEARCH-3dgs-terrain.md G4-3 · G5-2 (Isaac Lab v2.3.2 소스 실측 10개 조건) · 작업서 04 산출물
> 요지: OBJ 를 Isaac Lab 의 `create_prim_from_mesh` 경로로 USD 에 넣어 충돌 · 재질 · 삼각화를 붙이고, 저장한 파일을 새 스테이지에서 다시 열어 G5-2 의 조건을 하나씩 확인한다
> 상태: 확정
> 판: v1.0
> 이슈: #430

워커 모델: `gpt-6-astra` · reasoning high (Isaac Sim 파이썬 · USD 스키마 · 검증 논리)

선행 조건: `_out/mesh/ground.obj` 와 `_out/mesh/ground_stats.json` (작업서 04). 없으면 «선행 조건 없음» 으로 보고하고 멈춘다.

## 0. 자리와 경로

| 무엇 | 절대 경로 |
|---|---|
| 작업 폴더 | `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260916-3dgs-test/` |
| 스크립트 (새로 만든다) | 작업 폴더 `poc_mesh_to_usd.py` |
| 입력 | `_out/mesh/ground.obj` (Z 업 · 미터 · 삼각형) |
| 산출물 | `_out/mesh/ground.usd` · `_out/mesh/ground_usd_check.json` · `_out/mesh/REPORT-05.md` |
| 파이썬 | `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe` · Isaac Sim 5.1 · Isaac Lab v2.3.2 (`C:/isaac/IsaacLab`) |
| 참고 코드 (읽기만) | `C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/utils.py` (`create_prim_from_mesh`) · `terrains/terrain_importer.py` · `sim/eval/record_terrain_demo.py` 의 AppLauncher 기동 순서 |

환경 변수 `OMNI_KIT_ACCEPT_EULA=YES` · `KMP_DUPLICATE_LIB_OK=TRUE` 를 **그 프로세스에만** 준다 (`sim/eval/render_gallery.py` 머리의 «쓰는 법» 과 같다). `CUDA_VISIBLE_DEVICES` 는 만지지 않는다. 헤드리스로 띄운다.

## 1. 해야 할 것

1. `AppLauncher(headless=True)` 로 Isaac Sim 을 띄우고 `trimesh.load("ground.obj")` 로 메시를 읽는다. 면이 전부 삼각형인지, 정점 · 면 수, 경계 상자를 적는다.
2. `isaaclab.terrains.utils.create_prim_from_mesh("/World/ground", mesh, visual_material=PreviewSurfaceCfg(diffuse_color=(0.5,0.5,0.5)), physics_material=RigidBodyMaterialCfg(static_friction=1.0, dynamic_friction=1.0, restitution=0.0))` 로 prim 을 만든다. 이 함수가 만드는 prim 경로(예 `/World/ground/mesh`)를 그대로 적는다.
3. 스테이지 메타데이터를 확인해 `metersPerUnit=1.0` · `upAxis=Z` 로 맞추고 `_out/mesh/ground.usd` 로 저장한다 (`omni.usd.get_context().save_as_stage` 또는 `stage.GetRootLayer().Export`. 어느 것을 썼는지 적는다).
4. **새 프로세스**(같은 스크립트의 `--verify` 모드)로 저장한 USD 를 열어 `ground_usd_check.json` 에 아래를 적는다.

| 검사 | 기대 |
|---|---|
| `/World/ground` 아래 `Mesh` 타입 prim 이 **정확히 하나** · `Plane` 타입 prim 없음 | G5-2 1 · 5 |
| `faceVertexCounts` 가 전부 3 | G5-2 4 |
| 정점 수 · 면 수가 OBJ 와 같다 | 1번과 대조 |
| `UsdPhysics.CollisionAPI` 적용됨 · `PhysxCollisionAPI` 유무 · `MeshCollisionAPI` 의 approximation 값 (기대 `none`) | G5-2 2 · G4-3 |
| 물리 재질이 바인딩됨 (`physicsMaterial` prim 존재 · 마찰값) | G5-2 2 |
| `metersPerUnit` 1.0 · `upAxis` Z | G5-2 8 |
| 월드 변환이 항등 (스케일 1 · 회전 0) | RayCaster 가 world transform 을 곱하므로 항등이 아니면 값도 적는다 |
| 원점 (0, 0) 주변 반지름 1 m 의 정점 z 최소 · 최대 · 중앙값 | G5-2 7 (바닥이 z=0 근처인가) |
| 파일 크기 | |

5. 한 번 더, Isaac Lab 의 `TerrainImporterCfg(terrain_type="usd", usd_path=..., prim_path="/World/ground", env_spacing=2.0, num_envs=1)` 로 `TerrainImporter` 를 만들어 예외 없이 뜨는지, `env_origins` 가 (0,0,0) 인지 적는다. 그 뒤 `RayCasterCfg(prim_path=..., mesh_prim_paths=["/World/ground"], pattern_cfg=GridPatternCfg(resolution=0.1, size=(1.6, 1.0)))` 를 z=1.0 의 고정 prim 에 붙여 한 스텝 업데이트하고 **187 광선 중 유한값 개수** 와 hit z 의 최소 · 최대 · 중앙값을 적는다 (Isaac Lab 의 height scan 이 우리 USD 를 읽는지 직접 보는 것이다). 이 부분이 어려우면 «5번 미수행» 으로 적고 4번까지로 보고한다.

## 2. 통과 기준 (관문)

| 항목 | 기준 |
|---|---|
| USD | `_out/mesh/ground.usd` 존재 · 4번 표의 검사 전부 기대와 일치 |
| 스캔 | 5번을 했다면 유한값 187/187, 못 했다면 «미수행» 명시 |
| 스크립트 | `poc_mesh_to_usd.py` 가 `--obj` `--usd` `--verify` 인자로 처음부터 끝까지 돈다. 머리에 분류 · 작성 · 근거 · 요지 도크스트링 |

## 3. 하지 말 것

- 다른 프로세스를 죽이지 않는다 (다른 세션의 Isaac 렌더가 돌고 있다). `CUDA_VISIBLE_DEVICES` 설정 금지. 시스템 설치 · pip 설치 금지.
- `sim/` · `docs/` · `.github/` · `C:/isaac/IsaacLab` 을 고치지 않는다 (읽기만).
- `poc_mesh_to_usd.py` · `_out/mesh/` 밖의 저장소 파일을 만들거나 고치지 않는다. git 커밋 · 스테이징 금지.
- em dash(U+2014) 금지.

## 4. 보고서 형식 (`_out/mesh/REPORT-05.md`)

```
# REPORT-05 · 지면 메시 USD 충돌체
## 환경   Isaac Sim · Isaac Lab 버전 · 시작/끝 시각 · 기동 시간
## 명령   실제로 친 명령
## 결과   1절 1~5번의 수치와 4번 검사표 (기대 · 실측 · 판정)
## 산출물 경로 목록과 크기
## 문제   오류 원문 · 우회한 것 · 못 한 것
## 판정   2절 관문 항목별 통과/실패
```

`worker_done` 의 세 문장 요약에 검사표 통과 개수 · 스캔 유한값 개수(또는 미수행) · 통과/실패를 넣고 `--report-path` 에 이 보고서 경로를 준다.
