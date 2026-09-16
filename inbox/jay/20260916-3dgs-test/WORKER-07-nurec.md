# 작업서 07 · 3DGS 스플랫을 Isaac Sim 5.1 안에 배경으로 띄우고 지면 메시 충돌체 · Go2 와 한 화면에 (NuRec)

> 분류: 작업서
> 작성: 오흥재 · 2026-09-16 21:20
> 근거: 코디네이터 세션의 프로브(`_out/nurec/probe_nurec.json` 로 복사 예정) · 3DGRUT 저장소 소스(`_out/tools/3dgrut/` · 커밋 a37ef72 · 2026-07-08) · Isaac Sim 5.1 NuRec 문서 · NVIDIA 포럼 · 조사 문서 `RESEARCH-3dgs-terrain.md` v1.4 G5
> 요지: 3DGRUT 의 `transcode` 는 CUDA 빌드 없이 PLY → NuRec USDZ 로 변환된다(서드파티 휠 전부 Windows 에 있음). 변환한 USDZ 가 Windows Isaac Sim 5.1 에서 실제로 렌더되는지가 첫 관문이고, 되면 `ground.usd` 충돌체 위의 Go2 와 한 화면에 12 초 영상을 만든다
> 상태: 검토중
> 판: v1.0
> 이슈: #430
>
> 작업 폴더는 이 파일이 있는 폴더(한글 경로 · 모든 경로 따옴표). 결과는 전부 `_out/nurec/` 아래. 팀장이 원하는 그림은 «스플랫 배경 + 메시 충돌체 + Go2 한 화면» 이다.

## 0. 확인된 사실 (이 작업서를 쓰기 전에 잰 것)

| 항목 | 값 | 어디서 |
|---|---|---|
| Isaac Sim | 5.1.0 · Kit 107.3.3 · win32 · isaac311 파이썬 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe` | 헤드리스 프로브 |
| 렌더 설정 기본값 | `/rtx/rendermode` = RaytracedLighting · `/app/useFabricSceneDelegate` = true | 프로브 |
| 켜진 확장 | `omni.hydra.rtx-1.0.0` · `omni.volume-0.5.2` · `omni.fabric.commands` | 프로브 |
| NuRec 스키마 | pxr 스키마 레지스트리에 `OmniNuRecVolumeAPI` · `ParticleField*` 없음. 3DGRUT 는 codeless 속성으로 쓰므로 등록이 필요 없을 수 있다 (`미확인`) | 프로브 |
| 렌더러 DLL | `omni.hydra.rtx` 의 `rtx.hydra.dll` · `rtx.scenedb.plugin.dll` 에 «nurec» 문자열 있음 | grep |
| Windows 에서 NuRec 렌더 | **미확인**. 문서는 Isaac Sim 5.0 이상 · Kit 107.3 이상이라고만 적는다 | 문서 |
| 3DGRUT transcode | `python -m threedgrut.export.scripts.transcode <ply> -o <usdz> --format nurec` · PLYImporter → AttributesExportAdapter(torch CPU) → NuRecExporter(pxr · msgpack · numpy). MixtureOfGaussians · CUDA 커널 불필요 | 소스 |
| 필요한 서드파티 | numpy · torch(CPU 로 충분) · plyfile · msgpack · rich · usd-core(26.8 · cp311 win_amd64 휠 있음) · nvidia-ncore(19.8.0 · 순수 파이썬 휠) · hydra-core · omegaconf. `torchmetrics` · `torchvision` · `PIL` · `tqdm` · `ppisp` 는 export 패키지 다른 모듈이 import 하므로 필요할 수 있다 | 소스 · pip index |
| 알려진 함정 | 3DGRUT 저장소의 `pyproject.toml` 은 usd-core 를 Linux 에서만 설치한다 → Windows 에서는 손으로 설치. `threedgrut/__init__.py` 가 `.gui` 를 import 한다(최상위 import 는 logging 뿐) | 소스 |
| 포럼 | 5.1 에서 원점에서 300 m 이상 떨어진 스플랫은 float16 정밀도로 층이 진다(NVIDIA 답변). 우리 장면은 ±15 m 안이라 해당 없음 | 포럼 |
| 좌표 | PLY 는 COLMAP 월드(장면 유닛). `ground.usd` 는 메시 프레임(Z 업 · 미터) = `ground_stats.json` 의 `transform.world_to_mesh_4x4` (균일 축척 0.0787 · 회전 행렬식 +1 · 열벡터 규약 p' = M p) | 04 산출물 |

## 1. 순서

### 1) 변환용 venv

`_out/tools/3dgrut/.venv` 에 Python 3.11 venv 를 만든다(isaac311 의 python.exe 로 `python -m venv` 또는 uv). **isaac311 에는 아무것도 설치하지 않는다.** 설치 순서와 실제 성공한 버전을 `_out/nurec/venv_packages.txt` 에 남긴다(`pip freeze`). torch 는 CPU 휠(`--index-url https://download.pytorch.org/whl/cpu`)로 충분하다. 설치 후 다음이 돼야 다음 단계로 간다.

```
.venv\Scripts\python.exe -c "import threedgrut.export.scripts.transcode as t; print(t.__file__)"
```

`threedgrut` 패키지는 `pip install -e` 없이 `PYTHONPATH=_out/tools/3dgrut` 로 잡아도 된다. import 가 `.gui` 에서 막히면 저장소 사본의 `threedgrut/__init__.py` 에서 `from . import gui` 를 try/except 로 감싸고, 바꾼 줄을 보고서에 diff 로 적는다(사본은 gitignore 대상이라 저장소에는 안 들어간다).

### 2) PLY 를 메시 프레임으로 (`poc_ply_to_mesh_frame.py` · 작업 폴더에 새로)

`_out/splat/splat.ply` (2,270,126 개 · 59 속성) 를 `M = world_to_mesh_4x4` 로 옮겨 `_out/nurec/splat_mesh_frame.ply` 로 쓴다. 같은 헤더 · 같은 속성 순서.

| 속성 | 변환 |
|---|---|
| x y z | p' = M[:3,:3] p + M[:3,3] |
| rot_0..3 (w x y z) | q' = q_R ⊗ q · q_R 은 R = M[:3,:3] / s 에서 (s = 0.0787 · `scale.meters_per_scene_unit`) |
| scale_0..2 (log) | + ln(s) |
| f_dc_0..2 | 그대로 |
| f_rest_0..44 | R 로 회전. `_out/tools/3dgrut/threedgrut/export/sh_rotation.py` 의 `rotate_specular(specular, R, max_degree=3)` 를 쓴다. PLY 의 f_rest 는 채널 우선(3 x 15) 이므로 `importers/ply.py` 가 하는 대로 feature 우선(15 x 3) 으로 바꿔 넣고 되돌려 쓴다 |
| opacity · nx ny nz | 그대로 (nx ny nz 는 0) |

검증(보고서에 수치로): (a) `_out/mesh/plane_audit.npz` 의 인라이어 후보 xyz 를 같은 M 으로 옮긴 z 의 중앙값과 RMS (기대: 중앙값 |z| < 0.02 m · RMS ≈ 0.0127 m). (b) COLMAP 카메라 중심 287 개(`C = -R^T t`)를 옮긴 값과 `ground_stats.json` 의 `cameras.centers_m` 의 최대 절대 차이 (기대 < 1e-3 m). (c) 변환 전후 가우시안 수 · 속성 수 동일.

### 3) transcode

```
set PYTHONPATH=<작업폴더>\_out\tools\3dgrut
.venv\Scripts\python.exe -m threedgrut.export.scripts.transcode "<작업폴더>\_out\nurec\splat_mesh_frame.ply" -o "<작업폴더>\_out\nurec\splat.usdz" --format nurec --max-sh-degree 3 -v
```

`--apply-coordinate-transform` 은 **쓰지 않는다** (좌표를 이미 메시 프레임으로 맞췄다). stdout · stderr · 벽시계를 `_out/nurec/transcode.log` 에. 끝나면 zip 목록(`default.usda` · `gauss.usda` · `*.nurec` · 그 밖)과 각 파일 크기, `gauss.usda` 와 `default.usda` 의 전문을 `_out/nurec/usdz_listing.md` 에 붙인다. 특히 prim 타입 · `omni:nurec:` 로 시작하는 속성 이름 · extent · xformOp · `upAxis` 메타데이터 · `metersPerUnit` 를 표로 뽑는다. `upAxis` 가 Y 이거나 xformOp 가 항등이 아니면 4) 에서 정렬에 영향을 주므로 그대로 적고 4) 에서 실측으로 판단한다.

### 4) Isaac Sim 5.1 (Windows) 렌더 시험 (`poc_nurec_render.py` · 작업 폴더에 새로 · isaac311)

새 프로세스 · `SimulationApp({"headless": True, "renderer": "RaytracedLighting", "width": 1280, "height": 720})`. 환경 변수 `OMNI_KIT_ACCEPT_EULA=YES` · `KMP_DUPLICATE_LIB_OK=TRUE` 는 그 프로세스에만. `--device` 는 nvidia-smi 로 사용량 적은 GPU.

1. 빈 스테이지(Z 업 · metersPerUnit 1) 에 `isaacsim.core.utils.stage.add_reference_to_stage(usd_path=<splat.usdz>, prim_path="/World/nurec")`. 참조 뒤 `/World/nurec` 아래 prim 경로 · 타입 목록을 로그에.
2. 카메라 하나. 포즈는 COLMAP `images.txt` 의 한 장(가운데쯤 · 예 143번째)을 메시 프레임으로 옮긴 것: 중심 C' = M C · 회전 R_cam→mesh = R · R_wc^T · COLMAP 카메라(+z 앞 · +y 아래) 를 USD 카메라(-z 앞 · +y 위) 로 바꾸려면 오른쪽에 diag(1, -1, -1) 을 곱한다. 초점거리는 PINHOLE fx 835.17 · 폭 1916 → 수평 FOV 로 환산해 `focalLength` / `horizontalAperture` 에 넣는다. 어느 이미지를 골랐는지 · 계산한 4x4 를 로그와 보고서에.
3. `app.update()` 를 60 번 돌려 로딩을 기다린 뒤 `isaacsim.sensors.camera.Camera` (또는 `omni.replicator.core` 의 render product + rgb annotator) 로 RGB 를 받아 `_out/nurec/render_a_nurec.png` 로 저장. 같은 카메라로 `/World/nurec` 을 `UsdGeom.Imageable.MakeInvisible()` 한 뒤 다시 60 프레임 돌려 `_out/nurec/render_b_hidden.png`.
4. 지표(보고서 표): 두 그림의 |a - b| 평균과 «5/255 초과 픽셀 비율» · a 의 그레이 표준편차 · 원본 undistorted 프레임(`_out/colmap/undistorted/images/<그 이미지>`) 을 1280x720 으로 맞춘 것과 a 의 128 px 축소 그레이 정규화 상호상관 계수. 셋을 가로로 이어 붙인 `_out/nurec/compare_cam<idx>.png` (왼쪽 원본 · 가운데 렌더 · 오른쪽 hidden). 판정 규칙: «렌더 됨» = 5/255 초과 픽셀 비율 ≥ 30 %. 상호상관 계수는 적기만 하고 좋고 나쁨을 판정하지 않는다.
5. 아무것도 안 그려지면 다음을 차례로 시도하고 시도마다 같은 지표를 적는다: (i) `/app/useFabricSceneDelegate` false 로 기동 · (ii) `/rtx/rendermode` = PathTracing (spp 16) · (iii) `default.usda` 대신 zip 안의 `gauss.usda` 를 직접 참조 · (iv) `SimulationApp` 대신 Isaac Lab `AppLauncher(headless=True, enable_cameras=True)`. 네 가지 다 안 되면 마지막 로그 50 줄(경고 · 오류 원문)을 `_out/nurec/render_fail.log` 에 적고 «Windows 5.1 NuRec 렌더 실패» 로 보고하고 5) 는 «미수행».
6. 시도 하나가 10 분 동안 진전 없으면 본인 PID 하나만 `taskkill /PID` 로 끝내고 마지막 로그 줄과 함께 «무응답» 으로 적는다.

### 5) 한 화면 (`poc_go2_nurec.py` · 작업 폴더에 새로 · isaac311)

`poc_go2_on_usd.py` 의 환경 구성 · 정책 로드 · 측정 · 영상 코드를 import 하거나 복사해 쓴다. `poc_go2_on_usd.py` 자체는 고치지 않는다 (고쳐야만 하면 기본 동작이 그대로인 추가 인자만 · 보고서에 diff).

- 장면: `scene.terrain` = usd `_out/mesh/ground.usd` (06 과 같은 설정 · `scene.env_spacing` 과 `terrain.env_spacing` 둘 다 1.0) · `/World/nurec` 에 `splat.usdz` 참조 · xform 항등 · num_envs **1** · 정책 **B** (`foothold-v1.pt` · 규격 2 관측) · 명령 0.5 m/s 직진 · 12 초 · 스폰과 reset 범위는 06 그대로 · **yaw 는 무작위 대신 0 으로 고정** (카메라 구도를 위해 · 06 과 다른 점으로 명시).
- NuRec prim 은 시각 전용이다. 충돌은 `ground.usd` 만. NuRec prim 에 `proxy` 계열 관계(4) 의 속성 표에서 이름 확인 · 문서에 «Proxy field in Raw USD Properties» 로 나옴)가 있으면 `/World/ground/mesh` 를 지정하고 메시에 matte 설정이 있으면 켜 본다. 있고 없고 · 켰을 때 그림이 달라졌는지 스틸로 남긴다.
- 카메라: 로봇 스폰점 (0, 0, 지면) 을 향해 뒤쪽 3.5 m · 높이 1.6 m · 20 도 내려다보는 고정 카메라 · 1280x720 · 30 fps. 
- 두 번 돌린다: (A) 지면 메시 보임(06 의 재질 그대로) · (B) 지면 메시 `MakeInvisible()` (충돌은 유지). 각각 `_out/nurec/go2_B_mesh_visible/run.mp4` · `_out/nurec/go2_B_mesh_hidden/run.mp4` 와 06 형식의 `trace.csv` · `summary.json`. t = 0 · 4 · 8 · 12 초 스틸 PNG 도 저장.
- 06 과 같은 측정(낙상 · 원시 광선 유한값 · 정책 입력 유한값 · progress_x)을 요약에 넣되 좋고 나쁨은 판정하지 않는다. 광선이 NuRec prim 에 맞는지(`height_scanner.mesh_prim_paths` 는 `/World/ground` 로 두므로 안 맞아야 한다) 첫 스텝 187 광선 유한값으로 확인한다.

### 6) 보고서 `_out/nurec/REPORT-07.md`

0 한눈에(관문 셋 결과 표) · 1 환경(venv 패키지 · 실패한 설치 · 저장소 사본 diff) · 2 변환(2) 의 검증 수치 · transcode 벽시계 · zip 구성표) · 3 렌더 시험(시도별 설정 · 지표 · 이미지 경로) · 4 한 화면(영상 · 스틸 경로 · 측정 요약 · proxy 시도 결과) · 5 한계와 오류 원문 · 6 재현 명령(전부 절대 경로 · 환경 변수). em dash 금지. 추측은 `추측`, 못 잰 것은 `미측정` · `미확인` 으로 표시.

## 2. 통과 기준

| 관문 | 통과 |
|---|---|
| G1 변환 | `splat_mesh_frame.ply` 검증 (a)(b)(c) 통과 · `splat.usdz` 존재 · zip 구성과 `gauss.usda` 전문 기록 |
| G2 렌더 | «렌더 됨 / 안 됨» 을 4) 의 지표로 판정 · 비교 이미지 존재. 안 되면 시도 네 가지와 오류 원문 |
| G3 한 화면 | G2 통과 시 영상 두 편 · 스틸 · trace · summary. G2 실패 시 «미수행» 명시 |

worker_done 요약 세 문장에 G1 · G2 · G3 결과와 «렌더 됨» 판정의 픽셀 비율을 넣고 `--report-path` 에 REPORT-07.md 절대 경로를 준다.

## 3. 제약

- 다른 프로세스를 절대 죽이지 않는다(다른 세션의 Isaac 렌더 python.exe 가 돌고 있다). 종료는 본인 PID 하나만. `CUDA_VISIBLE_DEVICES` 설정 금지.
- pip 설치는 `_out/tools/3dgrut/.venv` 안에만. isaac311 · 시스템 파이썬 · 시스템 설치(VS Build Tools · CUDA 툴킷) 금지. CUDA 커널 빌드 시도 금지(필요 없다).
- `sim/` · `docs/` · `.github/` · `C:/isaac/IsaacLab` · `models/` 는 읽기만. 저장소 파일 중 새로 만드는 것은 `poc_ply_to_mesh_frame.py` · `poc_nurec_render.py` · `poc_go2_nurec.py` 세 개와 `_out/nurec/` · `_out/tools/3dgrut/` 안의 것뿐. git 커밋 · 스테이징 금지.
- em dash(U+2014) 금지. 막히면 오류 원문을 적고 멈춘다. 렌더 품질 · 보행 수치의 좋고 나쁨은 판정하지 않는다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-16 | 처음 씀 | 프로브 · 3DGRUT 소스 · 문서 |
