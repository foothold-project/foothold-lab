# 3DGS 지형 레퍼런스 · 스마트폰 영상에서 지면 메시를 복원해 Go2 를 올리기까지

> 분류: 리서치
> 작성: 오흥재 · 2026-09-16 13:35
> 근거: 공식 문서(NVIDIA Isaac Sim 5.1 · NuRec · 3DGRUT · Isaac Lab v2.3.2 소스 · nerfstudio · COLMAP · Postshot) · 논문(3DGS · SuGaR · 2DGS · GOF · MILo · BAD-Gaussians · GaussGym) · 이 워크스테이션 실측(입력 영상 · 설치 상태 · Isaac Lab 소스) · codex 검증 1 ~ 4회차(2026-09-16) 반영
> 요지: 3DGS 에서 렌즈 왜곡은 보통 SfM 이 추정하고, 그 뒤 처리는 학습 도구마다 다르다(nerfstudio 는 안에서 펴고, 3DGUT 는 안 펴며, 이번에 고른 Brush 는 펴진 입력이 필요하다). 사람이 SfM 전에 영상을 펴 둘 필요는 없다. 스플랫 자체는 충돌체가 아니라서 지면 메시는 따로 복원해야 하고, 이 머신에는 CUDA 컴파일러가 없어 소스 빌드 없는 경로로 시작한다
> 상태: 검토중
> 판: v1.4
> 이슈: #430
>
> 초안은 Claude 세션이 팀장 지시(`HANDOFF.md`)로 썼다. 기술 허브(hub-tech) 4쪽과 같은 «장 · 절» 구성이고, 3DGS 는 #71 에서 `A/트윈렌더` 짝으로 예정된 자리다. 팀장이 허브에 얹을 때 머리글만 손보면 된다. 검증 결과 원문은 이 폴더의 `_out/verify/verify-result-r1.md` · `-r2.md` · `-r3.md` · `-r4.md` · `-r5.md` 에 있다 (gitignore 대상).

## 0. 이 문서를 읽는 법 · 표기 규칙

이 문서는 「3DGS 로 실제 바닥을 복원해 시뮬 지형으로 쓰려면 무엇을 어떤 순서로 하나」에 답한다. 교과서를 옮기지 않고 **우리 PoC 에 실제로 닿는 범위**만 담는다.

읽는 차례는 셋이다. 급하면 1절만 읽어도 된다.

| 절 | 무엇 | 누가 읽나 |
|---|---|---|
| 1 | 팀장 사전 이해 4항의 검증 답변과 한 줄 결론 | 팀장 |
| G1 ~ G6 | 단계별 레퍼런스 (촬영 · SfM 과 왜곡 · 학습 도구 · 메시 추출 · Isaac 적재 · NVIDIA 공식 지원) | 실제로 돌리는 사람 |
| 2 ~ 3 | 이 머신에서의 실행 계획과 위험 · 출처 | 실제로 돌리는 사람 · 검증자 |

증거 표기는 `AGENTS.md` 4-2 그대로다. `확인됨` 은 공식 문서나 소스를 직접 열어 대조했거나 이 머신에서 잰 것, `추측` 은 그럴듯하지만 안 잰 것, `미확인` 은 확인이 필요한 것, `미측정` 은 재보지 않은 수치다. 문서에 «있다» 고 확인한 것과 이 머신에서 «돌아간다» 고 확인한 것은 다르다. 후자는 실행 검증 전이면 `미확인` 이다. 링크는 3절 출처 목록에 번호로 모았다.

## 1. 팀장 사전 이해 4항 · 검증 답변

| # | 팀장 이해 | 판정 | 실제 관행과 다른 점 |
|---|---|---|---|
| 1 | 사진이 더 좋다(모션블러 없음). 이번은 영상으로 어디까지 되는지 본다 | **대체로 맞다** | 사진은 노출 · 초점 · 화질을 관리하기 좋은 선택이다. 다만 «사진이면 블러가 없다» 는 아니다. NVIDIA NuRec 촬영 지침은 사진에서도 빠른 움직임과 블러를 피하고 노출 시간을 1/100 초 이하로 짧게 잡고, 초점 · 노출 · 화이트밸런스를 고정하라고 적는다 [4]. 영상은 Postshot · nerfstudio · Instant-NGP 전부 «프레임을 뽑아» 쓴다. Postshot 은 «Use Best Images» 로 선명한 프레임을 고르고 [8], nerfstudio 와 Instant-NGP 는 추출 설정과 블러 선별 여부를 따로 확인해야 한다 [11][13]. 이번 PoC 는 자체 선명도 선별을 쓴다 (G1-4). 이번 입력은 상대 선명도 기준으로 두드러지게 흐린 프레임이 적다 (G1-2). 복원 적합성은 SfM 결과로 더 봐야 한다 |
| 2 | VFX 처럼 undistort 한 뒤 선형 3D 공간에서 작업해야 한다. 3DGS 도 그런가 | **반은 맞고 반은 다르다** | 원본 3DGS 경로에서는 «펴진 핀홀 공간에서 최적화한다» 는 점이 같다. 원본 3DGS 래스터라이저는 SIMPLE_PINHOLE 또는 PINHOLE 카메라만 받고 `convert.py` 가 COLMAP `image_undistorter` 로 펴서 넣는다 [9]. 다른 점은 «누가 펴나» 다. 렌즈 보정값이 없으면 SfM(COLMAP) 이 왜곡 계수를 자기보정으로 추정하고, nerfstudio 는 계수를 `transforms.json` 에 적어 두고 **학습 데이터 로더가 그 자리에서 편다** [10][11]. NVIDIA 3DGUT 는 왜곡 카메라 모델로 직접 투영할 수 있어 사전 보정이 필수가 아니다 [5]. 반대로 이번에 고른 Brush v0.3.0 은 COLMAP 로더가 왜곡 계수를 카메라에 넘기지 않아 **SfM 뒤에 펴 준 PINHOLE 입력이 필요하다** [39]. 이미 정확히 보정된 이미지도 쓸 수 있는데, 그때는 COLMAP 에 PINHOLE 계열 모델과 그 이미지에 맞는 내부 파라미터를 지정한다 [7] |
| 3 | 왜곡을 편 영상에서 프레임을 추출해 데이터화하는 것이 맞나 | **이번 자료에서는 순서가 다르다** | 렌즈 보정값이 없는 폰 영상이면 «프레임 추출 → SfM(왜곡 추정 포함) → 도구가 요구하면 undistort» 다. 이번 Brush 경로는 요구한다 (G2-1). 프레임 수는 nerfstudio 기본값이 영상당 300 장 [11], Instant-NGP 권고는 50~150 장 [13], Postshot 은 «Use Best Images» 가 선명하고 고르게 퍼진 프레임을 고른다 [8]. 보정값이 있는 카메라라면 먼저 펴서 PINHOLE 로 넣는 길도 정식이다 [7] |
| 4 | NVIDIA 공식 페이지에 «스마트폰 영상 → 메시» 방법이 있다 | **문서가 둘로 갈린다** | ① «스마트폰 → Isaac Sim»: 2025-10-23 NVIDIA 기술 블로그 「Reconstruct a Scene in Isaac Sim Using Only a Smartphone」. 아이폰 **사진** → COLMAP(PINHOLE) → 3DGUT → USDZ → Isaac Sim 5.0+. **메시가 아니라 스플랫**이고, 본문이 «복원물은 시각 형상뿐이라 충돌 속성이 없다» 고 적으며 이 예제는 바닥으로 별도 Ground Plane 을 추가한다 [3][4]. ② «영상 → 메시»: Instant-NGP(2022). **영상** → ffmpeg 프레임 → COLMAP → NeRF → GUI 의 NeRF→Mesh 변환. **3DGS 가 아니라 NeRF** 이고 RTX 5000 용 Windows 바이너리가 있다 [13][14]. 팀장이 기억하는 «영상 → 메시» 는 ②에 가깝고 «스마트폰 → Isaac Sim» 은 ①이다 |

한 줄 결론. **3DGS 는 «보이는 것»을 주고, 로봇이 «밟는 것»은 우리가 따로 복원해야 한다.** NVIDIA 블로그 예제도 스플랫 위에 별도 평면을 두고 로봇을 올린다. 이번 PoC 의 값은 그 «따로 복원하는 지면 메시»가 얼마나 매끄럽게 나오느냐에 있다. 팀장이 집중점으로 지정한 자리와 같다.

## G1. 촬영과 프레임 · 이번 입력이 어떤 데이터인가

### G1-1. 입력 영상 실측 `확인됨`

`inbox/jay/20260916-3dgs-test/test_20260916_112122728.mp4` 를 이 머신의 ffmpeg 7.1(imageio-ffmpeg 동봉)과 OpenCV 4.11 로 읽었다.

| 항목 | 값 |
|---|---|
| 해상도 · 프레임 | 1920 x 1080 · 861 프레임 · 23.98 fps (OpenCV 원값 23.979947) · 35.91 초 |
| 코덱 · 비트레이트 | HEVC Main · 8 bit yuv420p · 영상 스트림 2,592 kb/s · 컨테이너 전체 2,729 kb/s (AAC 음성 130 kb/s 포함) |
| 색공간 태그 | tv · bt2020nc / bt2020 / arib-std-b67 (**HLG**) |
| 컨테이너 | mp4 · encoder 태그 `Lavf58.45.100`. 컨테이너 작성 프로그램 정보라 영상 스트림이 다시 인코딩됐는지, 촬영 원본인지는 `미확인` |
| 내용 | 도심 인도와 차도. 벽돌 담장 · 보도블록 · 연석 · 노란 차선(「주정차금지」 도색) · 주차 차량 · 보행자 · 가로수. 강한 햇빛과 렌즈 플레어 |

셋이 위험이다. 1080p 치고 낮은 비트레이트는 압축 자국을 텍스처로 학습시킬 수 있다. HLG 태그는 그대로 디코드하면 톤이 밋밋해지고 도구마다 다르게 읽힐 수 있다. 움직이는 것(사람 · 차)은 스플랫에 유령을 만들 수 있다. Postshot 지침도 «움직이는 것은 블러나 고스트 아티팩트가 된다» 고 적는다 [8]. **이번 입력에서 셋의 실제 영향은 `미측정`** 이다.

### G1-2. 블러 분포 실측 `확인됨`

원본 861 프레임 전부를 그레이로 바꿔 라플라시안 분산(널리 쓰는 선명도 지표 [12])을 쟀다. 검증자가 독립 재계산으로 같은 값을 얻었다.

| 통계 | 값 |
|---|---|
| 최소 · 중앙값 · 최대 | 278 · 584 · 1,117 |
| 중앙값의 절반 미만 | 8 / 861 프레임 (약 0.93 %) |
| 초 단위 평균이 가장 낮은 두 구간 | 31~32 초 341.6 · 32~33 초 344.1 (후반 인도 구간) |

**상대 선명도 기준으로 두드러지게 흐린 프레임은 적다.** 이 지표는 장면의 텍스처 · 명암 · 압축에도 영향을 받으므로 모션블러의 심각도나 복원 적합성을 이것만으로 확정하지 않는다. SfM 등록률과 재투영 오차로 더 판단한다. 문턱은 장면마다 달라 고정하지 않고 이웃과 견줘 유독 낮은 것을 버린다 (sharp-frames 도 같은 발상이다 [12]).

### G1-3. 사진이 왜 낫나 · 다음 촬영 때 지킬 것

공식 지침에서 인용한 것과 이번 PoC 의 적용안을 가른다.

| 항목 | 내용 | 구분 |
|---|---|---|
| 형식 | 사진이 기본. 영상이면 «블러가 안 생길 속도로, 그러면서 최대한 빨리» 움직이고 가장 낮은 프레임레이트를 쓴다 | 문서 인용 [4][8] `확인됨` |
| 노출 | 노출 시간 1/100 초 이하. 초점 · 노출 · 화이트밸런스 고정. 플래시 금지 | 문서 인용 [4][8] `확인됨` |
| 겹침 | 60 % (NVIDIA) 또는 30~50 % (Postshot). 부족하면 SfM 이 끊긴다 | 문서 인용 [4][8] `확인됨` |
| 바닥 | «고립된 물체가 아니면 바닥과 천장 컷을 넣어라» | 문서 인용 [8] `확인됨` |
| 바닥 (적용안) | 우리는 바닥이 목적이니 카메라를 낮추고 아래를 보며 지그재그로 덮는다 | 팀 적용안 `추측` |
| 움직이는 것 | 사람 · 차 · 흔들리는 잎을 피한다 | 문서 인용 [8] `확인됨` |
| HDR · 원본 | HDR 영상 모드를 끄고 폰 원본 파일을 그대로 받는다 | 팀 적용안 (G1-1 의 HLG 문제에서) |
| 축척 | 길이를 아는 물건(줄자 · A4 · 마커)을 바닥에 둔다 | 팀 적용안 (G2-3 에서) |

### G1-4. 프레임 추출 규칙 · 실행 결과

| 무엇 | 값 | 근거 |
|---|---|---|
| 목표 프레임 수 | 250~300 장 (이번 PoC 의 선택) | nerfstudio 기본값 300 을 참고했다 [11]. Instant-NGP 는 별도로 50~150 장을 권한다 [13] |
| 고르는 법 | 연속 3 프레임마다 가장 선명한 한 장을 고르고, 앞뒤를 포함한 25 프레임 이동 중앙값의 0.6 배 미만이면 뺀다. 간격은 정확히 균등하지 않다 | `poc_frames.py` |
| 형식 | plain 은 OpenCV JPEG 품질 95, sdr 은 ffmpeg MJPEG `q:v 2` | 같은 스크립트 |
| 색 | HLG 를 bt709 SDR 로 톤매핑한 판(sdr)과 그냥 디코드한 판(plain) 두 벌 | ffmpeg `zscale` + `tonemap`(hable) 필터 [15] |

결과 `확인됨` (검증자 재계산과 일치): 287 창 중 287 장 선택 · 제외 0 · 선택된 최저 선명도 298 · plain 287 장 + sdr 287 장 · `_frames/` 파일 합 338.70 MB (323.01 MiB). 실행 시간은 로그 파일을 남기지 않아 `미측정` 으로 둔다.

같은 프레임을 나란히 놓고 보면 sdr 판의 채도가 더 높게 보인다 (`_out/probe/plain_vs_sdr.jpg`). 색표 기준이 없어 색 정확도와 학습 품질은 `미측정` 이고, SDR 표시용으로 sdr 판을 우선 쓴다.

## G2. SfM 과 카메라 왜곡 · 「펴야 하나」에 대한 정확한 답

### G2-1. 각 도구가 왜곡을 어떻게 다루나 `확인됨`

| 도구 | 왜곡 처리 | 출처 |
|---|---|---|
| 원본 3DGS (INRIA) | «래스터화에는 SIMPLE_PINHOLE 또는 PINHOLE 카메라여야 한다». `convert.py` 가 COLMAP 으로 SfM 하고 `image_undistorter` 로 펴서 넣는다 | [9] |
| nerfstudio · splatfacto | `ns-process-data` 가 COLMAP 왜곡 계수(k1 k2 k3 k4 p1 p2, OPENCV 또는 OPENCV_FISHEYE)를 `transforms.json` 에 적는다. 검토한 main 소스의 데이터 로더는 계수가 0 이 아니면 그 자리에서 편다. pip 배포판 1.1.5 의 동작은 별도 대조 전 | [10][11] |
| NVIDIA 3DGRUT / 3DGUT | «왜곡 카메라와 롤링 셔터 같은 시간 의존 효과를 지원». 3D 장면을 왜곡 카메라 모델로 투영할 수 있어 이미지의 사전 보정이 필수가 아니다. 다만 NVIDIA 의 스마트폰 가이드는 «3DGUT 호환을 위해 PINHOLE 또는 SIMPLE_PINHOLE 을 고르라» 고 적어 단순한 경로를 택했다 | [3][4][5] |
| Postshot | 자체 카메라 트래킹이 포즈와 왜곡을 추정한다. 외부 포즈를 들여오면 «왜곡 계수가 이미지와 맞아야» 하고, Bundler 포즈는 «항상 undistorted 라 이미지도 펴서 넣어야» 한다 | [8] |
| Brush v0.3.0 | COLMAP 로더가 카메라에 fx fy cx cy 와 포즈만 넘기고 왜곡 계수를 버린다 (태그 소스 `colmap.rs` 119~143행 · 138행에서 Camera 를, 142~143행에서 LoadImage 를 만들며 두 생성자에 왜곡 계수를 넘기지 않는다 · `camera.rs` 3~26행 · `scene.rs` 115~158행). OPENCV 로 추정한 미보정 이미지를 그대로 넣으면 왜곡 모델이 유지되지 않는다. **`image_undistorter` 결과(보정 이미지 + PINHOLE 카메라)를 넣는다.** 실행해서 품질 차이를 잰 것은 아니다 | [39] |
| COLMAP | 기본 SIMPLE_RADIAL, 광각은 OPENCV 권장. 같은 카메라 · 같은 촬영 설정이면 `--ImageReader.single_camera 1` 로 내부 파라미터를 공유한다. 외부 캘리브레이션값을 넣어 고정하는 길과, 이미 보정된 이미지에 PINHOLE 계열을 쓰는 길도 있다. 펴는 것은 `image_undistorter` 가 따로 한다 | [7] |

### G2-2. VFX 관행과 무엇이 같고 무엇이 다른가

| | VFX 매치무브 | 3DGS (이번 PoC 의 경로) |
|---|---|---|
| 왜곡 계수의 출처 | 렌즈 그리드 촬영 · 체커보드 캘리브레이션 | SfM 자기보정이 기본. 외부 캘리브레이션값을 넣어 고정할 수도 있다 |
| 펴는 시점 | 트래킹 전에 플레이트를 펴고 오버스캔 | SfM 은 원본으로 하고, 그 뒤는 도구별이다. nerfstudio 는 로더가 편다. 3DGUT 는 왜곡 카메라 모델로 투영하므로 안 편다. Brush v0.3.0 은 COLMAP `image_undistorter` 로 펴서 넣는다 |
| 최적화 공간 | 펴진 선형 핀홀 공간 | 원본 3DGS 도 같다 (PINHOLE 계열 전제) |
| 사람이 할 일 | 렌즈 데이터 확보 · 펴기 · 되감기 | 카메라 모델 선택(SIMPLE_RADIAL / OPENCV / PINHOLE) · 프레임 선별 · 포즈와 재투영 오차 검토 · 축척과 좌표 정렬 |

결론. **«선형 3D 공간에서 작업한다» 는 직관은 맞다.** 다만 3DGS 에서는 그 공간을 사람이 먼저 만들지 않고 SfM 과 학습 도구가 만든다. 이번 PoC 는 원본 추출 프레임으로 COLMAP OPENCV SfM 을 하고, **Brush 학습 전에 `image_undistorter` 로 보정 이미지와 그에 맞는 PINHOLE 카메라를 만들어 그것을 Brush 에 넘긴다.** 원본 OPENCV 데이터와 보정 데이터를 섞지 않는다. 메시 추출 도구도 같은 보정 데이터를 쓴다.

### G2-3. 축척(스케일)은 따로 잡아야 한다 `확인됨`

COLMAP 복원의 크기는 임의다. FAQ 는 카메라 중심의 실좌표를 주고 `model_aligner` 로 닮음 변환(회전 · 이동 · **크기**)을 구하는 길을 적는다 [7]. NVIDIA 의 USDZ 내보내기도 «원점 근처로 정규화할 뿐 바닥이 z=0 이라는 보장은 없다» 고 명시한다 [3][4]. GaussGym 공개 코드는 Polycam(ARKit 포즈)에서 미터 단위 축척을 받고 [16], Postshot Studio 는 AprilTag 로 맞춘다 [8].

이번 영상에는 기준물이 없다. **다음 촬영에는 길이를 아는 물건을 바닥에 둔다.** 이번은 벽돌 한 장 높이나 노면 도색 폭처럼 규격이 있는 것으로 어림잡되, 그 값은 `추측` 이고 실측 대비 오차는 `미측정` 으로 적는다.

### G2-4. 영상용 COLMAP 설정 (적용안)

| 무엇 | 값 | 왜 |
|---|---|---|
| 카메라 모델 | OPENCV, `single_camera 1` | 렌즈 · 초점거리 · 크롭 같은 내부 파라미터가 영상 동안 일정하다고 가정하고 시작한다. 렌즈 전환 · 줌 · 전자식 보정 크롭의 변화와 재투영 오차를 점검하고 필요하면 카메라 그룹을 나눈다 [7] |
| 매칭 | sequential + loop detection | 영상은 이웃 프레임이 곧 이웃 뷰다. Instant-NGP 도 영상엔 sequential 을 준다 [13] |
| 실행 파일 | COLMAP 4.2.0 Windows CUDA 바이너리 (2026-09-01 릴리스 · `colmap-x64-windows-cuda.zip` · 380.97 MB · 363.32 MiB) 를 내려받아 압축을 풀어 실행. 대안은 pycolmap 4.2.0 (cp311 win_amd64 wheel 이 PyPI 에 있음) 을 파이썬 환경에 설치 | 배포 파일 존재 `확인됨` [17][18]. 이 머신에서의 실행은 `미확인` |

## G3. 3DGS 학습 도구 · Windows 11 + RTX 5080 에서의 실행 후보와 남은 검증

### G3-1. 이 머신의 제약 `확인됨` (조사 범위 내)

| 있음 | 발견 못 함 |
|---|---|
| RTX 5080 x2 (장당 16 GB) · 드라이버 591.86 · torch 2.7.0+cu128 (isaac311) · Isaac Sim 5.1.0 · Isaac Lab 소스 v2.3.2 (파이썬 패키지 isaaclab 0.54.2) · Blender 4.5.10 / 5.2.0 · ffmpeg 7.1(파이썬 동봉) · trimesh · scipy · OpenCV | **CUDA 툴킷(nvcc)** · **Visual Studio / MSVC** · COLMAP · nerfstudio · gsplat · open3d · pymeshlab |

PATH · 표준 설치 위치 · Windows 설치 등록 정보 · conda 환경 넷(base · final_env · isaac311 · moss)을 봤고 임의 경로의 포터블 설치까지 전 디스크를 뒤진 것은 아니다. **CUDA 확장을 소스에서 빌드하는 도구(원본 3DGS · SuGaR · 2DGS · GOF · MILo · gsplat 소스 빌드)를 바로 돌릴 환경은 확인되지 않았다.** 그런 도구를 쓰려면 Visual Studio Build Tools 와 CUDA 12.8 툴킷을 «설치»해야 하고, 설치는 시스템 변경이라 팀장 결정 사항으로 둔다.

### G3-2. 도구 비교

배포 파일이 «있다» 와 이 머신에서 «돈다» 를 가른다. 아래 표의 실행 판정은 전부 실행 검증 전이다.

| 도구 | Windows · RTX 50 (문서 기준) | 입력 | 출력 | 이 머신에서 | 근거 |
|---|---|---|---|---|---|
| **Postshot** (Jawset) | Windows 전용 · compute 7.5 이상 | 영상 그대로(MP4 · MOV · MKV) · 자동 프레임 추출 · **자체 카메라 트래킹** · COLMAP 포즈 import 도 됨 | PLY · SPZ · HTML. **메시 없음** | 후보. 내려받기 · 설치 · 실행 검증 남음. PLY 내보내기가 유료 티어라는 제3자 정리가 있고 공식 문서엔 티어 표기가 없다 `미확인` | [8][19] |
| **Brush** (Rust · wgpu) | Windows · Mac · Linux · **CUDA 불필요** | COLMAP 또는 nerfstudio 데이터(포즈 필요). **v0.3.0 은 왜곡 계수를 안 받으므로 undistort 된 PINHOLE 데이터를 넣는다** (G2-1) | PLY | 후보. 최신 릴리스 v0.3.0 (2025-09-14 · Windows zip 158.79 MB · 151.44 MiB) `확인됨`. 실행은 `미확인` | [20] |
| **gsplat** (nerfstudio 팀) | CI 빌드 매트릭스는 Windows(windows-2022) 에 python 3.10, torch 2.8.0 은 cu128 · cu129, torch 2.9.1 과 2.10.0 은 cu128 · cu130 이다 (cu126 은 Windows 에서 제외). 공개 wheel 목록에는 구버전을 포함한 Windows wheel 이 41 개 있고 v1.5.3 은 `gsplat-1.5.3+pt24cu124-cp310-cp310-win_amd64.whl` 하나다. 조사한 목록에 isaac311(py 3.11 · torch 2.7)용 Windows wheel 은 없다. CI 의 Windows 아키텍처 목록은 7.5 · 8.0 · 8.6 · 9.0 이라 **sm_120(RTX 50) 지원은 `미확인`** | COLMAP 데이터 | PLY · 3DGUT · 왜곡 카메라 연산자 | 후보. 원하는 torch · CUDA 조합의 Windows wheel URL 과 GPU 아키텍처 지원을 확인하고 실제 CUDA 연산을 돌려 본 뒤에야 «컴파일 없는 경로» 로 확정한다 | [21][22] |
| nerfstudio (splatfacto) | pip 배포판 1.1.5 (2024-11) 는 gsplat 1.4.0 고정 | 영상 → `ns-process-data video` (ffmpeg + COLMAP) | PLY · 카메라 | gsplat 1.4.0 Windows wheel 도 목록에 있으나 조사한 파일은 python 3.10 · torch 2.0~2.4 조합이라 isaac311 과 RTX 5080 호환은 `미확인`. 우선순위 낮음 | [10][11] |
| **NVIDIA 3DGRUT** (3DGUT) | 2025-07 부터 Windows 지원 표기. CUDA 11.8 / 12.4 / 12.6 / **12.8(기본 · Blackwell)** / 13.0(실험). Windows 는 **CUDA 툴킷 · Visual Studio Build Tools 2019+ 의 C++ 워크로드 · uv** 가 있어야 `install_env_uv.ps1` 이 실행된다 | COLMAP (PINHOLE 권장) | PLY · **USDZ(NuRec)** · USD | 툴킷 설치 뒤에만 시도 가능. Isaac Sim 렌더용 NVIDIA 공식 경로 | [5][6] |
| 원본 3DGS (INRIA) | README 기준 CUDA 11.8 · VS 2019 로 빌드. 24 GB VRAM 권장 | COLMAP(PINHOLE 계열) | PLY | 툴킷 설치 뒤에도 Blackwell 빌드는 `미확인` | [9] |
| Polycam (앱 · 웹) | 폰 또는 웹 업로드 · 클라우드 처리 | 앱 촬영 · **기존 영상 파일 업로드**(웹 · iOS · 사진측량과 Gaussian Splat 모드 · 공식 안내 2026-09-16 확인) | PLY 스플랫 · GLB / OBJ **메시**(대부분 유료) | 클라우드 후보. 이번 파일의 코덱 · HDR 처리 · 요금 · 지형 품질은 실행 전 `미확인`. 다음 촬영 때 «앱으로 찍기» 도 선택지 | [23][37] |
| KIRI Engine (앱 · 웹) | 클라우드 처리 | 앱 촬영 · **기존 영상 · 사진 업로드** (v3.13 부터) | PLY 스플랫 · 메시(OBJ · FBX · GLTF) | 클라우드 후보. 요금 · 이번 파일 처리는 `미확인` | [38] |
| Luma | 클라우드 | 현행 입력 경로 `미확인` | | 별도 조사 | |
| Instant-NGP | RTX 5000 용 Windows 바이너리 | 영상 → `colmap2nerf.py --video_in` | NeRF · **NeRF→Mesh** (GUI) | NeRF 계열이라 이번 목적(스플랫)과 다르다 | [13][14] |

### G3-3. 고른 것

1. **1차 (CUDA · MSVC 소스 빌드를 피하는 후보 경로)**: COLMAP 4.2.0 바이너리로 SfM → `image_undistorter` (PINHOLE) → **Brush** 로 학습 → PLY. 병행으로 **Postshot** 무료판에 영상을 그대로 넣어 «지면 형상이 복원되는가» 를 시각 점검한다 (내보내기가 막혀도 판단에는 쓸 수 있다). 두 앱 다 내려받기 · 실행 검증이 남아 있다.
2. **gsplat wheel 경로**: 호환 wheel 을 찾고 RTX 5080 에서 CUDA 연산이 실제로 도는지 본 뒤에 결정한다. 툴킷 설치와는 별개의 문제다.
3. **2차 (툴킷 설치 뒤)**: **3DGRUT** 로 USDZ 를 내 Isaac Sim 5.1 에서 렌더가 되는지 본다. NVIDIA 공식 경로다.

## G4. 스플랫 → 지면 메시 · «어떻게 매끄럽게 메시화하는가»

### G4-1. 연구 방법 (스플랫에서 직접 표면을 복원하는 것)

| 방법 | 원리 | 산출 | 이 머신에서 | 근거 |
|---|---|---|---|---|
| SuGaR (CVPR 2024) | 가우시안을 표면에 붙도록 정규화한 뒤 Poisson 으로 메시. README 는 메시 추출 단계를 단일 GPU 평균 30 분으로 적고 뒤의 refinement 는 별도다 | OBJ + 텍스처, Blender 애드온 | CUDA 11.8 안내. README 가 경로 처리 때문에 현재 코드의 Windows 호환 수정이 필요하다고 밝힌다. 뷰어도 Windows 미지원 | [24] |
| 2DGS (SIGGRAPH 2024) | 2D 원반 가우시안. 렌더한 깊이를 TSDF 로 융합해 메시. 야외는 `depth_ratio 0`(평균 깊이) 권장 | PLY 메시 (Open3D TSDF) | CUDA 확장 빌드 필요 | [25] |
| GOF (2024) | 불투명도 필드 + 사면체 격자 marching. 개방된 야외 장면(unbounded) 대상 | PLY 메시 | README 기준 CUDA 11.3 계열 · CGAL 의존. 빌드 무거움 | [26] |
| MILo (SIGGRAPH Asia 2025) | 학습 중 매 반복 메시를 미분 가능하게 추출해 정점 수를 줄인다. 저자들은 bicycle 사례에서 정점 수가 거의 1/10 이라고 보고하고, 표 1 의 Tanks and Temples 평균은 MILo base 4.36 M · GOF 16.49 M · RaDe-GS 14.75 M 이다 (arXiv v2) | 메시 | CUDA 11.8 만 시험됨. Linux 경로 | [27] |
| NVIDIA 3DGRUT | 메시 «주입»(playground)은 있으나 **메시 추출은 없다** | 없음 | 해당 없음 | [6] |

3DGRUT 을 뺀 넷은 표면 복원 방법이다. 그 메시를 보행 충돌체로 쓰려면 축척 · 구멍 · 표면 오차 · 삼각화 · 충돌 설정을 따로 검증해야 한다. 그리고 툴킷 설치 전에는 어느 것도 이 머신에서 못 돌린다.

### G4-2. 실용 경로 (툴킷 없이 되는 것)

| 경로 | 무엇 | 장점 | 한계 |
|---|---|---|---|
| **A. 2.5D 높이 격자** (실험안) | 스플랫 중심점(불투명도 · 크기로 거른 것)을 바닥 평면에 정렬하고, 격자마다 높이 중앙값을 취해 삼각화 | Go2 높이 스캔이 원래 2.5D 다 (광선이 아래로만 간다 [30]). 삼각형 수를 마음대로 정한다. trimesh · scipy 로 된다 | 가우시안 중심을 지표면 표본으로 취급하는 정확도, 뜬 점 제거 효과, 지면 오차가 전부 `미측정`. 한 칸에 가짜 점이 우세하면 중앙값도 틀린다. 보간은 실제 구멍과 단차를 지울 수 있어 관측 누락과 실제 구멍을 갈라 보간 범위를 정한다. 연석 옆면 같은 수직면이 계단 모양이 된다 |
| B. Poisson 표면 복원 | 중심점에 법선을 추정해 Open3D `create_from_point_cloud_poisson(depth)`. 저밀도 정점을 잘라 낸다 | 곡면이 자연스럽다 | 법선 추정이 흔들리면 물결이 생긴다. 경계가 부풀어 오르는 것을 밀도로 잘라야 한다 [28]. open3d 는 wheel 설치가 먼저다 |
| C. COLMAP dense MVS | `patch_match_stereo` → `stereo_fusion` → `poisson_mesher`. 스플랫과 무관한 대조군 | 사진측량 표준. 3DGS 를 쓴 대규모 지형 연구도 충돌 메시는 사진측량 메시로 만들어 «하이브리드» 로 썼다 [29] | 시간이 길고 하늘 · 무텍스처 면에 구멍 |
| D. 폰 앱의 LiDAR 메시 | Polycam 이 GLB 메시를 같이 준다. GaussGym 공개 코드는 Polycam 의 Raw Data 와 GLTF 내보내기에서 출발한다 [16][23] | 미터 단위 축척이 따라온다 | 이번 영상엔 해당 없음. 다음 촬영 선택지 |

**이번 PoC 는 A 를 주요 경로로, B 와 C 를 대조군으로 둔다.** «매끄럽게» 의 뜻을 우리 기준으로 적으면 아래와 같다. **전부 팀이 제안한 목표값이고 검증 전이다.**

| 지표 | 목표 (제안) | 재는 법 |
|---|---|---|
| 관측 범위 | 보행 구간에서 실제 관측된 칸 비율과 보간한 칸 비율을 둘 다 기록 | 격자 통계. 보간 뒤 빈 칸 0 만으로 성공을 판정하지 않는다 |
| 뜬 점 · 가짜 턱 | 인도 평면에서 ±3 cm 밖의 칸이 보행 구간의 1 % 미만 | 평면 적합 잔차 |
| 연석 높이 | 실측과 ±2 cm | 이번 자료엔 실측 길이가 없어 `미측정`. 규격 추정치와의 비교는 실측 오차라고 부르지 않는다 |
| 삼각형 수 | 10 만 이하 | 정적 삼각 메시 충돌체에 상한 규정은 없지만 [31] 높이 스캔 warp 메시가 매 스텝 광선을 쏘므로 작게 |

### G4-3. 후처리와 충돌 메시 `확인됨` (문서 기준)

- 평활화 · 데시메이션은 trimesh(설치됨) 또는 Blender 4.5(설치됨) 의 Smooth · Decimate 로 한다. pymeshlab 2025.7 도 win cp311 wheel 이 있다 [18]
- **정적 지형은 삼각 메시 충돌체를 그대로 쓴다.** Isaac Sim 물리 문서: «삼각 메시와 메시 단순화는 rigid body 에서 지원되지 않아 convex hull 로 되돌아간다». 정적 형상은 삼각 메시를 직접 쓸 수 있다 [31]. 지형은 rigid body 가 아니므로 `UsdPhysics.CollisionAPI` 를 켜고 `MeshCollisionAPI` 의 approximation 을 `none` 으로 둔다 (두 API 는 다른 것이다)
- 다만 **Isaac Lab 높이 스캔은 USD 의 `faceVertexIndices` 를 그대로 삼각형으로 읽는다.** 사각형 면이 섞이면 광선 결과가 깨진다. **삼각화 필수** (G5-2)

## G5. Isaac Sim 5.1 · Isaac Lab 에 지형을 올리기

### G5-1. NuRec(3DGS) 는 «보이는 것» 만 준다 `확인됨` (문서 기준)

- Isaac Sim 5.0 부터 «Neural Volume Rendering(NuRec)» 으로 3DGUT 기반 USDZ 를 USD 에셋처럼 불러 렌더한다. 5.1 문서도 같다 [1][2]
- NVIDIA 스마트폰 가이드: «복원 장면은 시각 형상뿐이고 충돌 속성이 없다. Create > Physics > Ground Plane 으로 바닥을 만든다». 그림자는 프록시 메시를 NuRec prim 에 연결해 받는다 [3][4]
- **Isaac Lab 의 terrain importer 는 그 USDZ 를 지형으로 쓰기 어렵다.** 2025-08 이슈에 프로젝트 협업자가 «terrain importer 는 표준 메시 형상만 지원하는 것으로 보인다. 확장 볼륨 스키마(UsdVolVolume 계열)는 지형으로 시각화되지 않는다. 표준 메시로 변환해야 할 수 있다» 고 답했다 [32]. 모든 로딩 경로가 불가능하다는 일반화는 하지 않는다
- Isaac Sim **6.0** 릴리스 노트에 Fabric Scene Delegate 를 통한 3DGS 렌더, 스플랫과 메시의 조명 상호작용, 멀티 GPU 가 있다 [33]. 우리 `omniverse-stack.md` 의 «5.1 은 조명 상호작용 약함 · 6.0 개선» 이 이것이다. 우리는 5.1 에 머문다
- 이 머신의 Isaac Sim 5.1 pip 설치본과 kit 캐시의 파일명에서 nurec 이름을 찾지 못했다 `확인됨` (검색 범위 내 · 기능 부재의 증명은 아니다). 5.1 Windows 에서 NuRec USDZ 가 실제로 렌더되는지는 **NVIDIA 샘플 USDZ(HF `nvidia/PhysicalAI-Robotics-NuRec`)를 열어 봐야 안다** `미확인` [34]. 문서에 OS 제한 표기가 없다 [1][2]

정리. **렌더링 외관은 NuRec, 밟는 바닥은 우리 메시.** 이 둘을 같은 좌표계에 놓는 것이 트윈 렌더의 최종 그림이고, 이번 PoC 는 뒤쪽(메시)만 한다.

### G5-2. 우리 지형 USD 가 지켜야 할 것 (Isaac Lab v2.3.2 소스 실측) `확인됨`

`C:\isaac\IsaacLab`(v2.3.2 · 커밋 37ddf62 · 2026-01-29) 소스를 직접 읽었다. 경로는 `source/isaaclab/isaaclab/` 아래다 [30][35]. 소스에서 확인한 계약이지 실행으로 확인한 결과는 아니다.

| # | 조건 | 어디서 나온 조건인가 |
|---|---|---|
| 1 | `TerrainImporterCfg(terrain_type="usd", usd_path=...)`. `import_usd` docstring 은 «여러 메시가 있으면 첫 것만» 이라 적지만 구현은 USD 파일을 참조로 불러온다. 실제로 «하나를 고르는» 것은 높이 스캔(5번)이다. 그래서 충돌 지면을 **단일 삼각 Mesh 로 통합**해 물리와 스캔 형상을 일치시킨다 | `terrains/terrain_importer.py` 255~263행 · 284~285행 |
| 2 | **충돌과 재질을 USD 안에 미리 넣는다.** importer 는 «재질 속성을 적용하지 않는다» 고 적혀 있고, 실제로 `UsdFileCfg(usd_path)` 만 부르며 `collision_props` 를 안 준다 | 같은 파일 262~263 · 284행 · `sim/spawners/from_files/from_files.py` 333~334행 |
| 3 | 대안. `import_mesh(trimesh)` 는 `create_prim_from_mesh` 로 모든 면을 삼각형으로 쓰고 충돌(collision_enabled=True)과 재질을 붙인다. OBJ 를 trimesh 로 읽어 이 함수로 넣고 USD 로 저장한 뒤, **저장한 USD 를 다시 열어 충돌 · 재질 · 변환이 유지되는지 확인**한다 | `terrain_importer.py` 251~253행 · `terrains/utils.py` 89~103행(삼각화 · 충돌) · 119~130행(재질) |
| 4 | **삼각형만.** 높이 스캔이 `faceVertexIndices` 를 flatten 해 `wp.Mesh` 에 넣고 `faceVertexCounts` 를 보지 않는다 | `sensors/ray_caster/ray_caster.py` 192~197행 · `utils/warp/ops.py` 394~396행 |
| 5 | 높이 스캔 `mesh_prim_paths` 는 **정확히 하나**. 그 경로 아래에 `Plane` 이 있으면 그것을 우선 써서 거대한 평면을 만들고, 없을 때 첫 `Mesh` 를 쓴다. **실제 지형과 함께 보조 Plane 을 같은 경로 아래 두지 않는다.** foothold-v1 은 `/World/ground` | `ray_caster.py` 164~167 · 177~185 · 203행 · `models/foothold-v1.env.yaml` 343~344행 |
| 6 | 정적 메시만. «USD 기본값에서 안 바뀌는 메시» | RayCaster 문서 [30] |
| 7 | env 원점은 **z=0 격자**. usd 지형은 `env_spacing` 이 없으면 ValueError, 커리큘럼 없음. 복원 지면이 자동으로 정렬되지 않으므로 걸을 자리를 원점에, 바닥을 z=0 근처에 «우리가» 놓는다 | `configure_env_origins` 309~310행(env_spacing 없으면 ValueError) · `_compute_env_origins_grid` 359~368행 |
| 8 | 단위 미터 · Z 업 | Isaac Sim 스테이지 규약. 축척은 G2-3 |
| 9 | 광선이 빗나가면 inf. 규격 2 함수(`height_scan_with_gap`)가 연결된 경우에만 그 자리가 +1.0(깊은 낭떠러지)이 된다. 기본 Go2 Rough 관측 함수는 -inf 를 -1 로 자른다. **메시 구멍 = 낭떠러지 또는 벽 관측** | `sim/eval/gap_observations.py` · Isaac Lab `mdp.height_scan` |
| 10 | `visual-evidence.md` 04 의 교훈. 씬을 바꾸면 스폰과 카메라를 맞춰야 «조용한 실패» 가 없다 | 저장소 정본 |

### G5-3. 정책을 올리는 법 (적용안)

`sim/eval` 은 수정 금지이므로 PoC 스크립트는 이 폴더에 둔다. 뼈대는 `record_terrain_demo.py` 와 같다. `UnitreeGo2RoughEnvCfg` 를 받아 `scene.terrain` 을 usd 로 바꾸고, `curriculum.terrain_levels = None`, `observations.policy.enable_corruption = False`, `num_envs` 1~4, `env_spacing` 을 준다. 체크포인트는 `OnPolicyRunner.load` 뒤 `get_inference_policy`.

**체크포인트마다 관측 설정을 맞춘다.** 지형만 바꾸면 안 된다. 기본 Go2 Rough 소스는 `mdp.height_scan` 을 쓴다 (`velocity_env_cfg.py` 134~138행). NVIDIA 사전학습 pt 는 이 기본 관측을 적용하는 후보이고, 그 파일의 학습 설정은 체크포인트 폴더에 env.yaml 이 없어 추가 확인한다. foothold-v1 의 저장된 학습 설정은 `height_scan_with_gap`(offset 0.5 · miss_value 1.0)이다 (`models/foothold-v1.env.yaml` 614행 · 639~640행). 평가 하네스의 `apply_gap_aware_scan` 과 같은 방식으로 foothold-v1 에는 규격 2 관측을 명시적으로 걸고, 정책 입력 순서 · 크기 · 정규화도 대조한다. NVIDIA pt 파일은 존재를 확인했고(`C:\isaac\IsaacLab\.pretrained_checkpoints\...\checkpoint.pt` · 6,881,762 바이트) 로드와 호환은 실행 검증 전이다.

기록할 것은 팀장 지정 셋이다.

| 항목 | 정의 (적용안) |
|---|---|
| 낙상 | base contact 종료 여부와 시각 (`metrics.py` 방식) |
| 발 관통 | 발 충돌 형상과 지면 사이의 침투량. 링크 원점 높이에서 지면 높이를 뺀 값은 대리 지표이고, 허용 오차(예 1 cm)와 집계 단위(스텝 수 · 최대 침투)를 함께 적는다 |
| 높이 스캔 정상 여부 | 187 광선(1.6 x 1.0 m · 0.1 m 격자 · 17 x 11) 중 유한값 비율과 값 분포 (`probe_height_scan.py` 방식) |

## G6. NVIDIA 공식 지원 · 정확한 문서 지도

| 무엇 | 문서 | 날짜 | 한 줄 |
|---|---|---|---|
| Isaac Sim 5.1 Neural Volume Rendering | [1] | 5.1.0 | USDZ(3DGUT) 를 USD 에셋처럼 로드 · 렌더. 물리 없음 |
| Isaac Sim 5.0 같은 페이지 | [2] | 5.0.0 | 샘플 3종(Voyager Cafe · Galileo Lab · Wormhole) · 예제 코드가 «충돌 바닥 평면» 을 따로 만든다 |
| 기술 블로그 「스마트폰만으로 Isaac Sim 에 장면 복원」 | [3] | 2025-10-23 | 사진 → COLMAP PINHOLE → 3DGUT MCMC → USDZ → Isaac Sim 5.0+. 학습 환경은 «Linux · CUDA 11.8 · GCC 11 이하». 이 예제는 별도 평면을 추가한다 |
| NuRec 「Mono 카메라 데이터로 장면 복원」 | [4] | 2026-06-24 갱신 | 촬영 지침(사진 · 60 % 겹침 · 노출 1/100 초 이하 · 노출 고정) · «바닥이 z=0 이라는 보장 없음» |
| 3DGRUT 저장소 | [5][6] | v1.1.0 · 2026-06-10 (검증일 main README 와 나눠 인용) | Windows(2025-07) · Blackwell CUDA 12.8 · USD / USDZ / PLY / NuRec 내보내기 · 왜곡 카메라 · 롤링 셔터 |
| Isaac Sim 6.0 릴리스 노트 | [33] | 6.0 | Fabric Scene Delegate 3DGS · 조명 상호작용 · 멀티 GPU. 우리 대상 아님 |
| Instant-NGP | [13][14] | 2022 ~ | 영상 → NeRF → 메시. RTX 5000 Windows 바이너리 |
| GaussGym (연구 · Berkeley) | [16] | 2025-10-17 | 논문은 VGGT 포즈 · 점군 · 법선 → **NKSR 충돌 메시**, 스플랫은 렌더 전용. 공개 코드는 Polycam Space 의 Raw Data + GLTF 에서 출발. Unitree A1 로 실기 검증 |
| 대규모 지형 3DGS (ISPRS 2024) | [29] | 2024 | 스플랫은 보기용, **충돌은 사진측량 메시** 의 하이브리드 |

두 연구 사례 [16][29] 가 같은 결론을 낸다. **스플랫은 렌더에, 충돌은 별도 메시에.** NVIDIA 블로그 예제도 다르지 않다. 우리 `FLOW.md` 의 «스캔은 시험지와 무대» 원칙과 맞물린다.

## 2. 이 머신에서의 실행 계획 (조사 뒤 확정안)

| 단계 | 무엇 | 도구 | 산출물 (이 폴더 · gitignore 대상) | 상태 |
|---|---|---|---|---|
| 1 | 프레임 추출 · 흐린 프레임 제외 · HLG 처리 두 판 | 동봉 ffmpeg 7.1 · OpenCV · `poc_frames.py` | `_frames/plain/` · `_frames/sdr/` 각 287 장 · `_frames/frames.csv` | **완료** (G1-4) |
| 2 | SfM (OPENCV · sequential · loop) · **`image_undistorter` (Brush 입력용 · 필수)** | COLMAP 4.2.0 Windows CUDA 바이너리 | `_out/colmap/` · `_out/colmap/undistorted/` | 워커 실행 중 (작업서 02 v1.1) |
| 3 | 3DGS 학습 (짧은 판 뒤 본 판) · 입력은 2단계의 undistorted 폴더 | Brush (CUDA 불필요) · 병행 Postshot 무료판 시각 점검 | `_out/splat/splat.ply` | 작업서 03 준비됨. 내려받기 · 실행 검증 전 |
| 4 | 지면 메시 A(2.5D 격자) · 대조군 B(Poisson) · C(COLMAP dense) | trimesh · scipy · open3d wheel · Blender 4.5 | `_out/ground.obj` · 지표 표 | 후보 도구 선정. 스크립트와 open3d 설치 전 |
| 5 | USD 충돌체 저장 (삼각화 · CollisionAPI 활성화 · MeshCollisionAPI approximation=none · 물리 재질 · z=0 · 원점) · 다시 열어 확인 | Isaac Lab `create_prim_from_mesh` 경로 | `_out/ground.usd` | 스크립트 작성 전 |
| 6 | Go2 보행 시험 (NVIDIA pt → foothold-v1 · 관측 설정 각각 맞춤) · 영상 · 수치 | isaac311 · PoC 스크립트 | mp4 · trace CSV · 요약 표 | 스크립트 작성 전 · GPU 는 다른 세션 렌더와 나눠 씀 |
| 7 | (2차) VS Build Tools + CUDA 12.8 설치 뒤 3DGRUT USDZ · Isaac Sim 5.1 NuRec 렌더 확인. gsplat 은 wheel 검증 결과에 따라 별도 | | | **팀장 결정** (시스템 설치) |

시간은 1 단계를 포함해 전부 `미측정` 이다. 2 단계 이후의 예상(2 는 300 장 기준 수십 분, 3 은 GPU 를 나눠 쓰는 상태)은 `추측` 이고 잰 뒤 적는다.

### 위험

| 위험 | 왜 | 대응 |
|---|---|---|
| SfM 이 차도 쪽에서 끊길 수 있다 `추측` | 앞으로만 걷는 영상은 옆 시차가 작아 등록이 끊기거나 희소점이 부족할 수 있다. 영역별 등록률 · 점 밀도는 `미측정` | 인도 폭만 목표로 자른다. 다음 촬영은 지그재그 |
| 유령 · 뜬 점 | 보행자 · 차 · 플레어. 이번 입력에서의 영향은 `미측정` | 불투명도 · 크기 필터 + 격자 중앙값. 효과는 실험으로 잰다 |
| 축척 오차 | 기준물이 없다 | 규격 있는 물체로 어림 (`추측` 표기) · 다음 촬영에 줄자 |
| 톤 · 압축 | HLG 태그 · 낮은 비트레이트. 영향은 `미측정` | 두 판 비교 · 다음엔 폰 원본 |
| 높이 스캔이 구멍을 낭떠러지나 벽으로 읽는다 | 관측 함수마다 miss 처리가 다르다 (G5-2 9번) | 관측 함수를 체크포인트에 맞추고, 보행 구간의 관측 칸 비율을 관문으로 |
| Windows 5.1 NuRec 렌더 미확인 | 문서에 OS 표기 없음 | 샘플 USDZ 로 먼저 시험. 2차 범위 |

## 3. 출처

1. Isaac Sim 5.1.0 「Neural Volume Rendering」 https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_nurec.html
2. Isaac Sim 5.0.0 「Neural Volume Rendering」 https://docs.isaacsim.omniverse.nvidia.com/5.0.0/assets/usd_assets_nurec.html
3. NVIDIA Technical Blog, 「Reconstruct a Scene in NVIDIA Isaac Sim Using Only a Smartphone」 (2025-10-23) https://developer.nvidia.com/blog/reconstruct-a-scene-in-nvidia-isaac-sim-using-only-a-smartphone/
4. NVIDIA Omniverse NuRec 「Reconstruct Scenes from Mono Camera Data」 https://docs.nvidia.com/nurec/archives/26.04/robotics/neural_reconstruction_mono.html
5. nv-tlabs/3dgrut README (검증일 main) https://github.com/nv-tlabs/3dgrut/blob/main/README.md
6. nv-tlabs/3dgrut v1.1.0 릴리스 노트 (2026-06-10) https://github.com/nv-tlabs/3dgrut/releases/tag/v1.1.0
7. COLMAP FAQ https://colmap.github.io/faq.html · 카메라 모델 문서 https://colmap.github.io/cameras.html
8. Postshot User Guide (Importing Images · Capturing Guidelines · Radiance Field Export) https://www.jawset.com/docs/d/Postshot+User+Guide
9. graphdeco-inria/gaussian-splatting README https://github.com/graphdeco-inria/gaussian-splatting/blob/main/README.md
10. nerfstudio 「Data conventions」 https://docs.nerf.studio/quickstart/data_conventions.html · `full_images_datamanager.py` (main · 로더 undistort) https://github.com/nerfstudio-project/nerfstudio/blob/main/nerfstudio/data/datamanagers/full_images_datamanager.py
11. nerfstudio `video_to_nerfstudio_dataset.py` (num_frames_target=300) · `colmap_converter_to_nerfstudio_dataset.py` (camera_type · matching_method 기본값) https://github.com/nerfstudio-project/nerfstudio/tree/main/nerfstudio/process_data · 「Using custom data」 https://docs.nerf.studio/quickstart/custom_dataset.html · PyPI 1.1.5 메타데이터(gsplat==1.4.0) https://pypi.org/pypi/nerfstudio/1.1.5/json
12. sharp-frames (PyPI · 0.4.0 · 2026-07-18) https://pypi.org/project/sharp-frames/
13. NVlabs/instant-ngp 「NeRF dataset tips」 https://github.com/NVlabs/instant-ngp/blob/master/docs/nerf_dataset_tips.md
14. NVlabs/instant-ngp README (RTX 5000 Windows 바이너리 · NeRF→Mesh) https://github.com/NVlabs/instant-ngp
15. FFmpeg filters 「tonemap」 · 「zscale」 https://ffmpeg.org/ffmpeg-filters.html#tonemap-1
16. GaussGym 논문 (arXiv 2510.15352 · 2025-10-17 · 3.1절 VGGT + NKSR) https://arxiv.org/abs/2510.15352 · 공개 코드 README (Polycam Raw Data + GLTF) https://github.com/escontra/gauss_gym
17. COLMAP 4.2.0 릴리스 (2026-09-01 · `colmap-x64-windows-cuda.zip`) https://github.com/colmap/colmap/releases/tag/4.2.0
18. PyPI 확인 (2026-09-16 실측): pycolmap 4.2.0 · open3d 0.19.0 · pymeshlab 2025.7.post1 에 cp311 win_amd64 wheel 파일이 있다. gsplat 1.5.3 · nerfstudio 1.1.5 는 CUDA 바이너리가 없는 범용(py3-none-any) wheel 과 sdist 뿐이다 https://pypi.org/project/pycolmap/
19. radiancefields.com Postshot 정리 (제3자 · 티어 · 1.1.43) https://radiancefields.com/platforms/postshot
20. ArthurBrussee/brush README https://github.com/ArthurBrussee/brush · v0.3.0 릴리스 https://github.com/ArthurBrussee/brush/releases/tag/v0.3.0
21. gsplat `INSTALL_WIN.md` https://github.com/nerfstudio-project/gsplat/blob/main/docs/INSTALL_WIN.md · 공개 wheel 목록 https://docs.gsplat.studio/whl/gsplat/
22. gsplat wheel 빌드 매트릭스 `.github/workflows/building.yml` https://github.com/nerfstudio-project/gsplat/blob/main/.github/workflows/building.yml
23. Polycam 「What File Types Can Polycam Export」 https://learn.poly.cam/hc/en-us/articles/27756102599572-What-File-Types-Can-Polycam-Export
24. Anttwo/SuGaR README https://github.com/Anttwo/SuGaR
25. hbb1/2d-gaussian-splatting README https://github.com/hbb1/2d-gaussian-splatting
26. autonomousvision/gaussian-opacity-fields README https://github.com/autonomousvision/gaussian-opacity-fields
27. Anttwo/MILo README · arXiv 2506.24096 https://github.com/Anttwo/MILo
28. Open3D 「Surface reconstruction」 https://www.open3d.org/docs/release/tutorial/geometry/surface_reconstruction.html
29. Chen et al., 「Large-Scale 3D Terrain Reconstruction Using 3D Gaussian Splatting for Visualization and Simulation」, ISPRS Archives XLVIII-2-2024 https://isprs-archives.copernicus.org/articles/XLVIII-2-2024/49/2024/
30. Isaac Lab 「Ray Caster」 https://isaac-sim.github.io/IsaacLab/main/source/overview/core-concepts/sensors/ray_caster.html · 소스 `source/isaaclab/isaaclab/sensors/ray_caster/ray_caster.py`
31. Isaac Sim 「Physics Simulation Fundamentals」 (충돌 근사 · 정적 삼각 메시) https://docs.isaacsim.omniverse.nvidia.com/latest/physics/simulation_fundamentals.html
32. isaac-sim/IsaacLab 이슈 #3295 「using the usdz in isaaclab」 (2025-08-28 · 협업자 답변 2025-09-02) https://github.com/isaac-sim/IsaacLab/issues/3295#issuecomment-3245789828
33. Isaac Sim 6.0 릴리스 노트 https://docs.isaacsim.omniverse.nvidia.com/6.0.0/overview/release_notes.html
34. Hugging Face `nvidia/PhysicalAI-Robotics-NuRec` (샘플 USDZ) https://huggingface.co/datasets/nvidia/PhysicalAI-Robotics-NuRec
35. Isaac Lab API 「isaaclab.terrains」 (TerrainImporterCfg · import_usd) https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.terrains.html · 소스 `source/isaaclab/isaaclab/terrains/terrain_importer.py`
36. BAD-Gaussians (ECCV 2024 · 모션블러가 3DGS 품질을 깎는다는 근거) https://github.com/WU-CVGL/BAD-Gaussians
37. Polycam 「How to Create Photogrammetry and Gaussian splats from Existing Images and Videos on Mobile and Web」 https://learn.poly.cam/hc/en-us/articles/30549121659412-How-to-Create-Photogrammetry-and-Gaussian-splats-from-Existing-Images-and-Videos-on-Mobile-and-Web
38. KIRI Engine 「How to capture 3D Gaussian Splats」 https://www.kiriengine.app/blog/how-to-capture-3d-gaussian-splats-kiri-engine
39. Brush v0.3.0 태그 소스 · COLMAP 로더 `crates/brush-dataset/src/formats/colmap.rs` https://github.com/ArthurBrussee/brush/blob/v0.3.0/crates/brush-dataset/src/formats/colmap.rs · 카메라 자료형 `crates/brush-render/src/camera.rs` https://github.com/ArthurBrussee/brush/blob/v0.3.0/crates/brush-render/src/camera.rs · 이미지 로더 `crates/brush-dataset/src/scene.rs` https://github.com/ArthurBrussee/brush/blob/v0.3.0/crates/brush-dataset/src/scene.rs

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| **v1.4** | 2026-09-16 | codex 검증 4회차 반영. Brush `colmap.rs` 인용 범위를 카메라 · 이미지 생성 호출까지 포함하는 119~143행으로 정정 | verify-result-r4 |
| v1.3 | 2026-09-16 | codex 검증 3회차 반영. Brush v0.3.0 이 왜곡 계수를 안 받으므로 «SfM → image_undistorter → Brush» 를 요지 · 1절 · G2 · G3 · 2절에 일관되게 명시 · CollisionAPI 와 MeshCollisionAPI 구분 · Polycam 출처 정정 | verify-result-r3 |
| v1.2 | 2026-09-16 | codex 검증 2회차 반영. gsplat 공개 목록 범위 · MILo 배수의 비교 조건 · NVIDIA pt 관측 설정을 «후보» 로 · Polycam · KIRI 를 클라우드 후보로 복귀 · 다운로드 용량 단위 · single_camera 가정 · 위험표 문장 · 소스 행 번호 보완 | verify-result-r2 |
| v1.1 | 2026-09-16 | codex 검증 1회차 반영. 사진 · 셔터 표현, 왜곡 설명의 일반화, gsplat 실행 가능 단정, MILo 수량, 관측 함수 불일치, 영상 수치(비트레이트 · 0.93 % · 31~33 초 · 338.70 MB), «준비됨» 표기, 문체를 고쳤다 | verify-result-r1 |
| v1.0 | 2026-09-16 | 처음 씀 | #430 · HANDOFF.md |
