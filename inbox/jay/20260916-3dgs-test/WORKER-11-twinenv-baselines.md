# 작업서 11 · `twin_env` 설치와 지면 복원 대조군 B · C 실행 가능성 검증

> 분류: 작업서
> 작성: 오흥재 · 2026-09-18 10:55
> 근거: `DESIGN-real-to-sim.md` 5절(지면 복원 방법 비교) · 8절(환경 설치 규격 `twin_env`) · 팀장 승인(conda 환경 생성 실행 승인 · Windows 시스템 설치는 보류) · 1차 산출물 `_out/splat/splat.ply` · `_out/colmap/undistorted/`
> 요지: 복원 전용 conda 환경 `twin_env` 를 팀원이 그대로 따라 할 수 있는 형태로 만들고, 그 안에서 대조군 **B(Poisson)** 와 **C(COLMAP dense)** 를 1차 자료로 실제로 돌려 본다. 이 작업의 목적은 **도구가 설치되고 돌아가는지와 비용이 얼마인지**를 아는 것이지 어느 방법이 낫다고 판정하는 것이 아니다
> 상태: 검토중
> 판: v1.0
> 이슈: #430
>
> 작업 폴더는 이 파일이 있는 폴더(한글 경로 · 모든 경로 따옴표). 결과는 전부 `_out/baselines/` 아래.

## 0. 전제와 경계

| 항목 | 내용 |
|---|---|
| 승인된 것 | **conda 환경 `twin_env` 생성과 그 안의 패키지 설치**(팀장 승인) |
| 보류된 것 | **Windows 시스템 설치**(VS Build Tools · CUDA Toolkit). 하지 않는다 |
| 건드리면 안 되는 것 | **`isaac311` 환경.** 정책 학습 · 평가 환경이다. 여기에 아무것도 설치하지 않는다 |
| 이번 범위 밖 | WSL2 CUDA Toolkit 설치와 D 후보(2DGS · PGSR 등) 빌드. 다른 세션 몫이다 |
| 자료 | **1차 자료로 돌린다.** 2차 자료는 작업서 10 이 만드는 중이고 나오면 같은 스크립트로 다시 돌린다 |

**팀장 조건이 하나 붙어 있다.** 「추후에 팀원이 따라할 수 있게 설치를 너무 내 로컬라이징에 맞춰서 하지 말고 공식 배포를 할 수 있을 정도로 생각해서 파이프라인 만들기」. 그러므로 **내 머신 경로가 박힌 설치는 실패**다. 아래 3 절을 반드시 지켜라.

## 1. `twin_env` 만들기

1. `conda create -n twin_env python=3.11 -y`
2. 다음을 넣는다. **버전을 고정하고 실제 설치된 버전을 기록한다.** open3d 는 Poisson 에, trimesh 는 메시 입출력에 쓴다.

   `numpy` · `scipy` · `open3d` · `trimesh` · `plyfile` · `opencv-python` · `matplotlib` · `pillow`

   conda 로 되는 것은 conda-forge 로, 안 되는 것만 pip 로 넣고 어느 쪽으로 넣었는지 적는다.
3. 검증: 새 셸에서 다음이 모두 통과해야 한다. 명령과 출력을 로그로 남긴다.

   ```
   python -c "import numpy, scipy, cv2, trimesh, plyfile, matplotlib; print('ok')"
   python -c "import open3d as o3d; print(o3d.__version__); print(o3d.geometry.TriangleMesh.create_sphere().is_watertight())"
   ```

4. 산출: `_out/baselines/env/environment.yml` (`conda env export --from-history` 와 전체 export 둘 다) · `install_twin_env.ps1` (아래 3 절 규칙대로) · `verify_twin_env.ps1` · `pip_freeze.txt` · 설치 로그.

**`isaac311` 에는 아무것도 설치하지 않는다.** 확인을 위해 작업 전후로 `conda list -n isaac311 --explicit` 을 떠서 해시가 같은지 비교하고 결과를 적는다.

## 2. 대조군 실행

### B · Poisson (open3d)

입력은 `_out/splat/splat.ply` (1차 · 가우시안 2,270,126 개).

1. 불투명도 0.1 이상만 남기고(1차와 같은 문턱) 중심점을 뽑는다. 색은 SH 0 차.
2. 법선을 추정한다(`estimate_normals` · 반경은 점 간 평균 거리의 배수로 잡고 값을 기록 · `orient_normals_towards_camera_location` 으로 카메라 쪽을 향하게 한다. 카메라 중심은 `_out/mesh/ground_stats.json` 의 `cameras.centers_units` 를 쓴다).
3. `create_from_point_cloud_poisson` 을 **depth 를 8 · 9 · 10 세 가지**로 돌린다. 각각 벽시계 · 정점 · 삼각형 · 워터타이트 여부 · 파일 크기를 기록한다.
4. 밀도 하위 백분위(예: 1 · 5 %) 정점을 잘라낸 판도 같이 만들고 비교한다.
5. 산출: `_out/baselines/poisson/mesh_d{8,9,10}.ply` 와 통계 JSON.

메모리가 모자라면 점을 균일하게 솎아내고(비율 기록) 그 사실을 적는다. **돌다가 죽으면 죽었다고 적는다.**

### C · COLMAP dense

입력은 `_out/colmap/undistorted/` (1차 · PINHOLE 287 장).

1. `patch_match_stereo` · 2. `stereo_fusion` → `fused.ply`
2. GPU 를 쓴다. **`nvidia-smi` 로 가장 한가한 GPU 를 골라 지정하고 사용량을 기록한다.** 작업서 09 · 10 워커가 다른 GPU 를 쓰고 있을 수 있다.
3. **이것이 가장 오래 걸린다.** 287 장이면 patch_match 만 수십 분일 수 있다. **60 분 진전이 없으면 본인 PID 하나만 종료하고 「무응답」으로 적는다.** 시간이 모자라면 `--PatchMatchStereo.max_image_size` 를 낮춰(예 1600) 다시 돌리고 그 설정을 적는다.
4. 산출: `_out/baselines/dense/fused.ply` 와 단계별 벽시계 · 점 수 · 파일 크기.

### A 와 나란히 놓기

A(우리 2.5D 격자)는 이미 `_out/mesh/` 에 있다. 새로 돌리지 않는다.

**B 와 C 의 산출물을 A 와 같은 잣대로 재려면 같은 2.5D 격자에 얹어야 한다.** 그래서 B 의 메시 정점과 C 의 융합 점군을 각각 `poc_mesh_grid.py` 와 같은 방식(같은 `world_to_mesh_4x4` · 같은 0.05 m 격자 · 같은 보행 관심 영역)으로 내려 다음을 계산한다. 이때 **평활화와 구멍 메움은 끄고** 원자료의 차이만 본다.

| 지표 | 의미 |
|---|---|
| 보행 관심 영역 관측 칸 비율 | 실제 자료가 있는 칸이 몇 퍼센트인가 |
| 관측 칸의 높이 표준편차 | 거칠기 |
| 평면 잔차 RMS | 도로면 평면에 얼마나 붙는가 |
| 빈 칸 · 구멍 | 메우지 않았을 때의 결손 |
| 처리 벽시계 · 최대 메모리 · 산출물 바이트 | 비용 |

## 3. 팀원이 따라 할 수 있게 (팀장 조건)

설치 스크립트와 문서는 다음을 지킨다. 어기면 이 작업은 실패다.

1. **절대 경로를 박지 않는다.** 저장소 루트는 스크립트 위치에서 상대로 구한다. 사용자 이름(`AI-WS01`)이 스크립트에 들어가면 안 된다.
2. **환경 이름을 인자로 받는다.** 기본값 `twin_env`, `-EnvName` 으로 바꿀 수 있게.
3. **재실행해도 안전해야 한다.** 이미 있으면 만들지 않고 알린다.
4. **검증 명령이 따로 있다.** 설치가 됐는지 사람이 한 줄로 확인할 수 있어야 한다.
5. **버전을 고정한다.** `environment.yml` 에 실제 설치된 버전이 들어간다.
6. GPU 가 없는 팀원 머신에서도 B 는 돌아야 한다(open3d Poisson 은 CPU). C 는 CUDA 가 필요하다고 명시한다.

## 4. 보고서 · `_out/baselines/REPORT-11.md`

0 한눈에(설치 성공 여부 · B · C 실행 결과 · 비용 한 표) · 1 `twin_env` (넣은 것 · 버전 · 검증 출력 · isaac311 불변 확인) · 2 B Poisson (depth 별 결과) · 3 C dense (설정과 결과 · 못 끝냈으면 그 사실) · 4 A · B · C 나란히 표 · 5 한계와 미확인 · 6 팀원용 설치 절차(스크립트 경로와 명령) · 7 재현 명령.

**4 절 표에서 어느 방법이 낫다고 판정하지 마라.** 1차 자료는 카메라가 제자리에서 찍힌 것이라 「누가 없는 자료를 더 그럴듯하게 메우나」를 비교하게 된다. 그 한계를 5 절 첫 줄에 적는다. 이 작업의 결론은 **「B 와 C 가 이 환경에서 돌아가고 비용은 얼마다」** 까지다.

## 5. 통과 기준

| 관문 | 통과 |
|---|---|
| G1 환경 | `twin_env` 생성 · 검증 명령 통과 · `environment.yml` 과 설치 스크립트 존재 · 3 절 여섯 규칙 충족 · `isaac311` 불변 확인 |
| G2 B | depth 세 가지 결과와 통계. 실패했으면 오류 원문 |
| G3 C | `fused.ply` 또는 「무응답 · 미완」과 그때까지의 기록 |
| G4 비교 | A · B · C 를 같은 격자 잣대로 나란히 놓은 표 |

worker_done 요약 세 문장에 `twin_env` 설치 성공 여부와 open3d 버전 · B 의 depth 9 정점 수와 벽시계 · C 의 완료 여부를 넣고 `--report-path` 에 REPORT-11.md 절대 경로를 준다.

## 6. 제약

- **`isaac311` 에 설치 금지.** 시스템 설치(VS Build Tools · Windows CUDA Toolkit) 금지. WSL 은 건드리지 않는다.
- 다른 프로세스를 절대 죽이지 않는다(작업서 09 · 10 워커와 다른 세션 GPU 작업이 돌고 있다). 종료는 본인 PID 하나만. `CUDA_VISIBLE_DEVICES` 설정 금지.
- `sim/` · `docs/` · `.github/` · `C:/isaac/IsaacLab` · `models/` 와 기존 `_out/` 산출물은 **읽기만** 한다. `_out/baselines/` 에만 쓴다.
- 새로 만드는 저장소 파일은 `_out/baselines/` 안의 것뿐. git 커밋 · 스테이징 금지. em dash(U+2014) 금지.
- 막히면 오류 원문을 적고 멈춘다. **되는 것과 안 되는 것을 있는 그대로 적는다.**

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-18 | 처음 씀 | 설계안 5절 · 8절 · 팀장 승인 |
