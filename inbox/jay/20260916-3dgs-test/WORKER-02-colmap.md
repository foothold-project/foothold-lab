# 작업서 02 · COLMAP SfM (프레임 287장 → 카메라 포즈 · 희소 점군 · undistort)

> 분류: 계획
> 작성: 오흥재 · 2026-09-16 14:20
> 근거: RESEARCH-3dgs-terrain.md G2-4 · G3-1 · 2절 2단계
> 요지: codex 워커가 이 문서만 보고 SfM 을 끝낼 수 있게 입력 · 명령 · 통과 기준 · 금지 사항을 적는다
> 상태: 확정
> 판: v1.1
> 이슈: #430

워커 모델: `gpt-5.6-sol` · reasoning high (정해진 명령을 돌리되 COLMAP CLI 의 실패 지점을 스스로 풀어야 해서 sol)

## 0. 자리와 경로

| 무엇 | 절대 경로 |
|---|---|
| 작업 폴더 (이 문서가 있는 곳) | `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260916-3dgs-test/` |
| 입력 프레임 (287 장 · sdr 톤매핑 판) | 작업 폴더 `_frames/sdr/NNNN.jpg` |
| 프레임 목록 | 작업 폴더 `_frames/frames.csv` (kept=1 인 행이 287) |
| 도구 자리 | 작업 폴더 `_out/tools/colmap/` (gitignore 대상. **저장소 밖에 폴더를 만들지 않는다**) |
| 산출물 자리 | 작업 폴더 `_out/colmap/` |
| 결과 보고 | 작업 폴더 `_out/colmap/REPORT-02.md` |

작업 폴더 이름에 한글이 있다. 모든 경로를 따옴표로 감싸고, 파이썬에서는 `os.fspath` 그대로 쓴다. COLMAP 이 한글 경로를 못 읽으면 그 오류를 그대로 보고하고 멈춘다 (임의로 다른 자리에 복사하지 않는다).

## 1. 목표

1. COLMAP 4.2.0 Windows CUDA 바이너리를 `_out/tools/colmap/` 에 내려받아 푼다.
2. `_frames/sdr/` 287 장으로 SfM 을 돌려 카메라 포즈와 희소 점군을 얻는다.
3. undistort 한 이미지와 PINHOLE 카메라 모델을 만든다 (뒤 단계의 3DGS 도구용).
4. 수치와 산출물 경로를 `REPORT-02.md` 에 적고 `worker_done` 한다.

## 2. 도구 설치

```
gh release download 4.2.0 --repo colmap/colmap --pattern colmap-x64-windows-cuda.zip --dir "<작업 폴더>/_out/tools"
```

`gh` 가 없으면 `https://github.com/colmap/colmap/releases/download/4.2.0/colmap-x64-windows-cuda.zip` 을 curl 로 받는다. 받은 zip 의 SHA-256 을 보고서에 적는다. `_out/tools/colmap/` 에 풀고 `colmap.exe` 의 절대 경로를 찾아 `--version` 또는 `-h` 출력 첫 줄을 보고서에 적는다. **시스템 PATH 나 레지스트리를 건드리지 않는다.** 실행은 절대 경로로만 한다.

## 3. 실행 명령 (이 순서 · 인자 그대로)

**옵션 이름은 COLMAP 4.2.0 기준이다** (`colmap.exe <명령> -h` 로 2026-09-16 실측). 3.x 의 `SiftExtraction.use_gpu` · `SiftMatching.use_gpu` 는 4.2 에서 `FeatureExtraction.*` · `FeatureMatching.*` 로 바뀌었다. 1차 실행(v1.0)이 이 이름 차이로 옵션 파싱에서 멈췄다. 명령이 «unrecognised option» 으로 실패하면 그 명령의 `-h` 출력을 보고서에 붙이고 멈춘다.

GPU 는 두 장이고 다른 세션의 렌더가 돌고 있다. 먼저 `nvidia-smi --query-gpu=index,memory.used --format=csv` 로 사용량이 적은 GPU 번호를 고르고 `--SiftExtraction.gpu_index <n>` · `--SiftMatching.gpu_index <n>` 에 넣는다. 고른 번호와 그때 사용량을 보고서에 적는다.

```
colmap feature_extractor --database_path "<작업 폴더>/_out/colmap/database.db" --image_path "<작업 폴더>/_frames/sdr" --ImageReader.camera_model OPENCV --ImageReader.single_camera 1 --FeatureExtraction.use_gpu 1 --FeatureExtraction.gpu_index <n>

colmap sequential_matcher --database_path "<작업 폴더>/_out/colmap/database.db" --SequentialMatching.overlap 15 --FeatureMatching.use_gpu 1 --FeatureMatching.gpu_index <n>

colmap mapper --database_path "<작업 폴더>/_out/colmap/database.db" --image_path "<작업 폴더>/_frames/sdr" --output_path "<작업 폴더>/_out/colmap/sparse"

colmap model_analyzer --path "<작업 폴더>/_out/colmap/sparse/0"

colmap model_converter --input_path "<작업 폴더>/_out/colmap/sparse/0" --output_path "<작업 폴더>/_out/colmap/sparse/0_txt" --output_type TXT
colmap model_converter --input_path "<작업 폴더>/_out/colmap/sparse/0" --output_path "<작업 폴더>/_out/colmap/sparse_points.ply" --output_type PLY

colmap image_undistorter --image_path "<작업 폴더>/_frames/sdr" --input_path "<작업 폴더>/_out/colmap/sparse/0" --output_path "<작업 폴더>/_out/colmap/undistorted" --output_type COLMAP
```

- 루프 검출(`--SequentialMatching.loop_detection 1`)은 1차 실행에서는 **끈 채로** 간다. 위 순서가 끝나면 두 번째 판을 `_out/colmap_loop/` 에 `--SequentialMatching.loop_detection 1` 만 더해 따로 돌리고 둘의 수치를 나란히 적는다. 4.2 의 `-h` 에는 vocab tree 경로 옵션이 보이지 않았다. 추가 파일을 요구하는 오류가 나면 오류 원문을 적고 두 번째 판은 접는다.
- mapper 가 모델을 여러 개 만들면(`sparse/0`, `sparse/1` ...) 등록 이미지 수가 가장 많은 것을 «주 모델» 로 쓰고 나머지 개수와 크기를 보고한다.
- 단계마다 벽시계 시간을 잰다 (시작 · 끝 시각을 기록).

## 4. 통과 기준 (관문)

| 항목 | 기준 |
|---|---|
| 등록 이미지 | 주 모델에 287 장 중 **90 % 이상**. 미만이면 실패로 보고하되 산출물은 남긴다 |
| 카메라 | 카메라가 **1 개**(single_camera). OPENCV 파라미터 fx fy cx cy k1 k2 p1 p2 를 보고서에 그대로 적는다 |
| 통계 | `model_analyzer` 출력 그대로 (등록 이미지 · 점 수 · 관측 수 · 평균 트랙 길이 · 평균 재투영 오차) |
| undistort | `_out/colmap/undistorted/images/` 에 등록 이미지 수만큼 파일 · `sparse/cameras.bin` 의 모델이 PINHOLE |
| 점군 | `sparse_points.ply` 존재 · 점 수 |

## 5. 하지 말 것

- 다른 프로세스를 죽이지 않는다. 특히 `python.exe` (다른 세션의 Isaac 렌더). 자기 것도 `taskkill /IM` 같은 이름 단위 명령을 쓰지 않는다.
- `CUDA_VISIBLE_DEVICES` 를 설정하지 않는다.
- `_out/` 와 이 보고서 밖의 저장소 파일을 만들거나 고치지 않는다. `docs/` · `sim/` · `.github/` 금지. 새 폴더 트리를 저장소 안팎에 만들지 않는다 (`_out/tools/` · `_out/colmap/` · `_out/colmap_loop/` 만).
- 시스템 설치(인스톨러 · PATH · 환경변수 · pip 전역 설치)를 하지 않는다.
- 다른 도구(pycolmap · GLOMAP · hloc)로 갈아타지 않는다. 막히면 오류 원문을 적고 멈춘다.
- em dash(U+2014)를 쓰지 않는다. 가운뎃점(·)이나 마침표.

## 6. 보고서 형식 (`_out/colmap/REPORT-02.md`)

```
# REPORT-02 · COLMAP SfM
## 환경   colmap 버전 · zip SHA-256 · GPU 번호와 그때 사용량 · 시작/끝 시각
## 명령   실제로 친 명령 전부 (경로 포함 · 순서대로)
## 결과   model_analyzer 출력 원문 · 카메라 파라미터 · 모델 개수 · 등록률 · undistort 파일 수 · 점군 점 수
## 산출물 경로 목록과 크기
## 문제   오류 원문 · 우회한 것 · 못 한 것
## 판정   4절 관문 항목별 통과/실패
```

`worker_done` 의 세 문장 요약에 등록률 · 평균 재투영 오차 · 실패 여부를 넣고 `--report-path` 에 이 보고서 경로를 준다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.1 | 2026-09-16 | COLMAP 4.2.0 옵션 이름으로 정정 (FeatureExtraction · FeatureMatching) · 루프 검출 2차 판 지시 정정 · 용량 단위 | 1차 워커 실패 보고 REPORT-02.md · `colmap.exe -h` 실측 |
| v1.0 | 2026-09-16 | 처음 씀 | RESEARCH G2-4 |
