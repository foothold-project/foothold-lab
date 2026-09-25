# 작업서 03 · Brush 로 3DGS 학습 (COLMAP 포즈 → 스플랫 PLY)

> 분류: 계획
> 작성: 오흥재 · 2026-09-16 14:40
> 근거: RESEARCH-3dgs-terrain.md G3-2 · G3-3 · 2절 3단계 · 작업서 02 산출물
> 요지: CUDA 컴파일 없이 도는 Brush 로 첫 스플랫을 만들고, 지면이 복원되는지 판단할 재료(PLY · 렌더 몇 장 · 수치)를 남긴다
> 상태: 확정
> 판: v1.1
> 이슈: #430

워커 모델: `gpt-5.6-sol` · reasoning high (CLI 옵션을 `--help` 로 스스로 찾아야 하고, 실패 지점을 갈라 보고해야 한다)

선행 조건: 작업서 02 가 통과해 `_out/colmap/undistorted/` (images/ + sparse/ · PINHOLE 카메라) 가 있어야 한다. 없으면 시작하지 말고 «선행 조건 없음» 으로 보고한다. `undistorted/sparse/cameras.bin` 의 모델이 PINHOLE 인지 `colmap model_converter --output_type TXT` 로 확인해 보고서에 적는다.

## 0. 자리와 경로

| 무엇 | 절대 경로 |
|---|---|
| 작업 폴더 | `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260916-3dgs-test/` |
| 입력 (1순위) | 작업 폴더 `_out/colmap/undistorted/` (COLMAP 형식 · PINHOLE 카메라 · images/ 와 sparse/) |
| 입력 (2순위 · 1순위 폴더 구조를 Brush 가 못 읽으면) | `_out/colmap/undistorted/images/` 와 `_out/colmap/undistorted/sparse/` 를 Brush 가 기대하는 구조(예 `images/` · `sparse/0/`)로 **복사가 아니라 정션(junction)** 으로 묶은 `_out/brush_in/`. **`_frames/sdr/` + OPENCV `sparse/0/` 를 직접 넣지 않는다.** Brush v0.3.0 로더는 왜곡 계수를 버리므로 보정 안 된 이미지와 OPENCV 모델을 넣으면 왜곡이 무시된다 (RESEARCH G2-1 · 출처 39) |
| 도구 자리 | 작업 폴더 `_out/tools/brush/` (gitignore 대상) |
| 산출물 자리 | 작업 폴더 `_out/splat/` |
| 결과 보고 | 작업 폴더 `_out/splat/REPORT-03.md` |

한글 경로다. 모든 경로를 따옴표로 감싼다. Brush 가 한글 경로를 못 읽으면 그 오류를 그대로 보고하고 멈춘다.

## 1. 목표

1. Brush v0.3.0 Windows 배포 파일(`brush-app-x86_64-pc-windows-msvc.zip` · 158.79 MB · 151.44 MiB)을 `_out/tools/brush/` 에 받아 푼다. zip 의 SHA-256 을 적는다.
2. `brush --help` (실행 파일 이름은 zip 안의 것을 확인) 출력을 **전부** `_out/splat/brush_help.txt` 에 저장하고, 학습 스텝 수 · PLY 내보내기 · 해상도 · 뷰어 없이 돌리기에 해당하는 옵션 이름을 보고서에 적는다.
3. **짧은 판**: 총 스텝 3,000 (또는 가장 가까운 옵션)으로 한 번 돌려 파이프라인이 끝까지 가는지 본다. PLY 를 `_out/splat/short.ply` 로.
4. **본 판**: 총 스텝 30,000 (옵션이 허용하는 범위에서) 으로 돌려 `_out/splat/splat.ply` 를 만든다. 학습 중 GPU 메모리와 벽시계 시간을 적는다.
5. 두 PLY 의 가우시안 수 · 파일 크기 · 학습 시간을 표로 적고 `worker_done`.

## 2. 실행 규칙

- GPU 는 두 장이고 다른 세션의 렌더가 돌고 있다. Brush 는 wgpu 라 `nvidia-smi` 로 어느 GPU 를 잡았는지 학습 중에 확인해 적는다. 특정 GPU 를 고르는 옵션이 `--help` 에 있으면 사용량이 적은 쪽을 고른다. 없으면 그대로 두고 적는다.
- 뷰어(GUI)를 띄우지 않는 옵션이 있으면 그것을 쓴다. GUI 만 되는 도구라면 창이 뜨더라도 명령줄 인자로 학습과 내보내기가 끝나는지 확인하고, 안 되면 «헤드리스 불가» 로 보고하고 멈춘다.
- 학습 해상도는 기본값으로 시작한다. 메모리가 모자라면 이미지 긴 변 1,280 으로 낮추는 옵션을 쓰고 적는다.
- 단계마다 시작 · 끝 시각을 적는다.

## 3. 통과 기준 (관문)

| 항목 | 기준 |
|---|---|
| 짧은 판 | `_out/splat/short.ply` 존재 · PLY 헤더의 vertex 수(= 가우시안 수) 보고 |
| 본 판 | `_out/splat/splat.ply` 존재 · vertex 수 · 파일 크기 · 학습 시간 · 최대 GPU 메모리 |
| 손실 | 학습 로그에 나온 마지막 손실 값(있으면) 과 PSNR(있으면) |
| 좌표계 | PLY 의 좌표계가 COLMAP 과 같은지(카메라 원점 기준으로 스플랫이 어느 축으로 퍼지는지) 한 줄 기록. 바닥이 어느 축의 어느 방향인지 `추측` 표기로 적는다 |

## 4. 하지 말 것

- 다른 프로세스를 죽이지 않는다. `CUDA_VISIBLE_DEVICES` 설정 금지. 시스템 설치 · PATH · 환경변수 · pip 전역 설치 금지.
- 다른 학습 도구(gsplat · nerfstudio · Postshot)로 갈아타지 않는다. 막히면 오류 원문을 적고 멈춘다.
- `_out/tools/brush/` · `_out/splat/` · `_out/brush_in/` 밖의 저장소 파일을 만들거나 고치지 않는다. git 커밋 · 스테이징 금지.
- em dash(U+2014) 금지.

## 5. 보고서 형식 (`_out/splat/REPORT-03.md`)

```
# REPORT-03 · Brush 3DGS 학습
## 환경   Brush 버전 · zip SHA-256 · 실행 파일 이름 · 잡은 GPU · 시작/끝 시각
## 명령   실제로 친 명령 전부 (경로 포함 · 순서대로)
## 결과   짧은 판 / 본 판 표 (vertex 수 · 파일 크기 · 시간 · 최대 GPU 메모리 · 손실/PSNR)
## 좌표계 관찰
## 산출물 경로 목록과 크기
## 문제   오류 원문 · 우회한 것 · 못 한 것
## 판정   3절 관문 항목별 통과/실패
```

`worker_done` 의 세 문장 요약에 본 판 vertex 수 · 학습 시간 · 통과/실패를 넣고 `--report-path` 에 이 보고서 경로를 준다.
