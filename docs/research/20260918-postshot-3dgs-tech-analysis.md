# Postshot 기술 분석과 3DGS 오픈소스 대체 경로 · 움직이는 피사체를 포함해서

> 분류: 리서치
> 작성: Claude 세션 (오흥재 지시) · 2026-09-18 11:40
> 근거: jawset.com 공식 문서·릴리스노트 13개 버전 전수 · 홈페이지 영상 7편 ffmpeg 프레임 추출 · 논문 arXiv 원문 · 저장소 LICENSE 와 소스 직접 확인 · 우리 `_out/colmap` 원자료 재측정
> 요지: Postshot 이 파는 것의 거의 전부가 Apache-2.0 공개 구현으로 존재한다. 움직이는 사람은 도구가 아니라 동기 멀티카메라가 가르는 문제이고 오픈소스로 바꿔도 같다. 우리 1차 촬영 실패는 COLMAP 의 삼각측량각 임계로 정확히 설명된다.
> 상태: 초안
> 판: v1.0
> 이슈: #430

---

## 0. 이 문서가 «하지 않는» 것

`inbox/jay/20260916-3dgs-test/DESIGN-real-to-sim.md` (작성 오흥재 · v1.3) 가 이미 답한 것은
다시 쓰지 않는다. 아래로 가리키기만 한다.

| 물음 | 어디 |
|---|---|
| 트윈을 충돌 지형과 배경으로 왜 쪼개나 | DESIGN 1-2 |
| 1차 PoC 가 왜 실패했나 (제자리 촬영 실측) | DESIGN 3-2 (가) |
| 지면 복원 후보 A~E 와 측정표 | DESIGN 5-1 · 5-3 |
| 표면 복원 6종의 Windows 미지원과 WSL2 방침 | DESIGN 5-1-1 |
| 재촬영 설계서 · 현장 체크리스트 | DESIGN 7 |
| 축척 확정 절차 | DESIGN 6 |

**이 문서는 그 위에 얹는 것만 다룬다.** 곧 Postshot 이라는 상용 도구의 정체, 그것을 쓰지
않고 같은 결과에 이르는 공개 경로, 그리고 DESIGN 이 다루지 않은 «움직이는 피사체» 다.

---

## 1. 「영상급」은 하나가 아니라 넷이 동시에 맞아야 나온다

1. **용량이 데이터를 따라 자란다** (densification) · 품질의 대부분이 여기서 갈린다
2. **시점 의존 색** (구면조화 SH) · 없으면 하이라이트가 안 미끄러져 죽은 플라스틱처럼 보인다
3. **카메라가 움직일 때 안 깨진다** · 앨리어싱과 팝핑
4. **입력 사진이 서로 모순되지 않는다** · 노출 · 블러 · 롤링셔터 · 그리고 포즈

**3번이 「사진 같다」와 「영상 같다」를 가르는 지점이고, 표준 벤치마크가 이것을 거의 못 잰다.**

| Mip-NeRF360 | 학습 해상도 PSNR | 8배 축소 시점 PSNR |
|---|---|---|
| 3DGS | 29.19 | **19.59** |
| Mip-Splatting | 29.39 | **26.22** |

학습 해상도에서는 0.20 dB 차이인데 카메라가 물러서면 **6.6 dB** 차이다 `확인됨`
(arXiv 2311.16493 Table 3). 로봇이 장면 안을 자유롭게 이동하며 렌더하는 순간 전부 드러난다.
**우리 용도에서 앤티에일리어싱은 선택 사항이 아니다.**

---

## 2. Postshot 의 정체 · 못 하는 것부터

`확인됨` 표시는 공식 문서·릴리스노트 원문 또는 영상 프레임에서 직접 확인한 것이다.

### 2-1. 출력에 메시가 없다

공식 Radiance Field Export 는 **HTML · PLY · SPZ 딱 셋** `확인됨`.
**OBJ · FBX · USDZ · GLB · 메시가 전부 없다.** 일부 서드파티 블로그가 「GLB/USDZ 를
내보낸다」고 쓰는데 공식 문서와 정면 배치되는 오정보다.

> **그러므로 Postshot 은 DESIGN 1-2 의 (b) 배경 전용이고 (a) 충돌 지형에는 원리적으로
> 쓸 수 없다.** 이것이 도구 평가의 결론이다.

### 2-2. 정적 장면을 가정한다고 문서가 직접 말한다

Capturing Guidelines 원문 `확인됨`:

> "Postshot's models assume the input images depict strictly static scenes."
> "The moving shadows create holes in the ground of the radiance field."

**움직이는 그림자가 지면에 구멍을 낸다**고 자백한다. 야외 보도 촬영에서 정확히 걸릴 자리다.

### 2-3. 플랫폼과 티어

- **Windows 10 이상 · NVIDIA Compute Capability 7.5 이상 전용** `확인됨`. Linux·macOS 빌드 없음
- 티어별 경계 `확인됨`
  - **Free** · 비상업 전용이고 **radiance field 를 파일로 내보낼 수 없다**
  - **Indie** · PLY·SPZ 내보내기 + 상업 사용
  - **Studio** · CLI 배치 + **AprilTag 정렬** + EXR/RAW + 4K 초과 HDR

**우리가 실제로 필요한 것 둘(CLI 배치 · AprilTag 미터 스케일)이 전부 Studio 에 있다.**
그리고 **무료판으로 파일럿을 잡으면 마지막에 내보내기에서 막힌다.**

### 2-4. 미터 스케일은 AprilTag 하나뿐

Rdnc Field > Edit > **Align to AprilTag** 에 `Tag Size` 를 **밀리미터로** 넣는다 `확인됨`.
그 외에 미터 단위를 보장하는 장치는 없고, 없으면 SfM 관습대로 임의 축척이다.

### 2-5. 조용한 함정 · `Recenter Poses & Points`

원문 `확인됨`: 씬을 원점 근처로 옮긴 오프셋이 **PLY 메타데이터에만** 저장되고,
*"software using these exports must reference the world origin stored in the PLY metadata."*

**우리 로더가 이 값을 안 읽으면 오류 없이 씬 전체가 어긋난 자리에 놓인다.**
커널 2-2 원칙 2 의 조용한 실패에 정확히 해당한다.

### 2-6. 그 외 확인된 제약

- 비디오를 넣어도 **초당 2~3 프레임만 사용** `확인됨`
- 학습 시작 후 이미지 추가·삭제 불가 `확인됨`
- **어안·360 카메라 지원 언급이 문서·릴리스노트 전체에 0건** `미확인` (질의 필요)
- Unreal 패키징 빌드에도 Postshot 앱 설치가 필요 `확인됨`
- Unity 플러그인 없음 · ROS/Isaac Sim 연동 없음 `확인됨`

---

## 3. 알고리즘 계보 · Jawset 은 논문을 한 곳도 인용하지 않는다

Training Configuration 페이지 전문에 학술 인용이 **0건**이다 `확인됨`.
아래는 프로파일 이름·동작 서술·릴리스 시점으로 역산한 것이다.

| 프로파일 | 대응 | 확신도 |
|---|---|---|
| **Splat ADC** (legacy) | 원조 3DGS `arXiv 2308.04079` 의 Adaptive Density Control | 높음 · 논문 Fig.2 블록 이름이 문자 그대로 그것 |
| **Splat MCMC** | 3DGS as MCMC `arXiv 2404.09591` (NeurIPS 2024) | 높음 · 이름 일치 + "more randomized sampling" + splat 수 상한 고정 + 시점 일치 |
| **Splat3** (현재 권장) | **미확인** · Jawset 자체 3세대로 보인다 | 근거 없음 |
| Anti-Aliasing 옵션 | Mip-Splatting `arXiv 2311.16493` | 추론 · 「줌 아웃 시 아티팩트 방지」 + 서드파티 뷰어 비호환 경고가 정확히 일치 |

`Splat MCMC` 가 무엇을 사는지는 분명하다. 원논문 Table 2 `확인됨`: 랜덤 초기화 범위를
좁히면 **3DGS 는 27.89 에서 22.72 로 5.2 dB 붕괴**하는데 **MCMC 는 29.72 에서 29.64 로
0.08 만 떨어진다.** 곧 **SfM 점군이 부실해도 살아남는다.** 텍스처 없는 보도·저조도에서
정확히 이 상황이 난다.

---

## 4. Postshot 없이 되는가 · 된다. 하나만 빼고

| Postshot 기능 | 공개 대응 | 라이선스 |
|---|---|---|
| Splat MCMC | `gsplat` `MCMCStrategy` · `ns-train splatfacto-mcmc` | Apache-2.0 |
| Splat ADC | `DefaultStrategy` | Apache-2.0 |
| **Splat3** | **대응 불명** | 미확인 |
| Photometric Compensation | bilateral grid `arXiv 2406.00448` | Apache-2.0 |
| Anti-Aliasing | Mip-Splatting · `rasterize_mode="antialiased"` | Apache-2.0 |
| Max Splat Count | `cap_max` · nerfstudio `max_gs_num` · Brush `--max-splats` | Apache-2.0 |
| Pose Quality | COLMAP · `colmap global_mapper` | BSD-3 |
| Single Lens 제약 | COLMAP `--ImageReader.single_camera 1` | BSD-3 |
| **PLY·SPZ 내보내기** (Indie 이상 유료) | `splat-transform` + `spz` | **MIT · 무료** |
| Create Sky Model | 직접 대응 없음 | 미확인 |

**결론: Postshot 이 파는 것의 거의 전부가 공개 구현으로 있다.** 유일한 미지가 `Splat3` 이다.

### 4-1. Windows 에서 실제로 무엇을 쓰나

| 스택 | 라이선스 | Windows | 비고 |
|---|---|---|---|
| **gsplat** | Apache-2.0 | 네이티브 | 3DGRUT 저장소 자신이 「프로덕션에는 gsplat 권장」이라 적는다 |
| **Brush** | Apache-2.0 | **사전빌드 zip** | CUDA·MSVC·Python 전부 불필요. AMD 에서도 돈다 |
| INRIA 원본 | **비상업** | VS2019 + CUDA 11.8 | 참조 구현용. main 이 2024-10 이후 멈춤 |
| nerfstudio | Apache-2.0 | 공식이 「Linux 권장」 | gsplat 백엔드 |
| 3DGRUT | Apache-2.0 | 공식 지원 | 어안·롤링셔터·LiDAR |

**Brush 주의** · 미해결 이슈 #525 로 **seed 를 고정해도 결과가 재현되지 않는다**
(404k~897k splat · 14.5~17.3 dB) `확인됨`. 재현성이 필요한 파이프라인에는 실질 위험이다.

**3DGRUT 관련 정정** · 한 조사에서 「Windows 는 PLY 만 나오고 NuRec 내보내기는 `usd-core`
가 linux 전용이라 Isaac Sim 연동에 Linux 박스가 필요하다」고 보고됐다. **우리에게는 틀렸다.**
우리 1차 PoC 가 전용 venv 에 `usd-core 26.8` 을 직접 넣어 `transcode` 를 CPU 로 돌렸고,
NuRec USDZ 267.9 MB 를 만들어 **Windows Isaac Sim 5.1 에서 렌더까지 확인**했다
(`RESULTS-3dgs-terrain.md` 7절). pyproject 의 플랫폼 핀은 우회 가능한 제약이었다.

### 4-2. 라이선스 연쇄 · 상용 계획이 있다면 먼저 볼 것

원본 3DGS 라이선스 원문 `확인됨`:
*"THE USER CANNOT USE, EXPLOIT OR DISTRIBUTE THE SOFTWARE FOR COMMERCIAL PURPOSES
WITHOUT PRIOR AND EXPLICIT CONSENT OF LICENSORS."*

파생 저장소 대부분이 `diff-gaussian-rasterization` 포크를 서브모듈로 단다.
**자기 코드가 MIT 라도 래스터라이저에서 막힌다.** 직접 확인한 것만 해도
`graphdeco-inria/gaussian-splatting` · `ubc-vision/3dgs-mcmc` ·
`autonomousvision/mip-splatting` 셋이 같은 비상업 라이선스다 `확인됨`.

학습 기반 포즈 프런트엔드도 같다. **DUSt3R · MASt3R · MASt3R-SfM · VGGSfM 이 전부 비상업**
이고, 상용 가능한 것은 **VGGT 뿐인데 그것도 기본 가중치가 아니다** ·
`facebook/VGGT-1B` 는 CC-BY-NC, 별도의 `facebook/VGGT-1B-Commercial` 만 상업 가능하며
**신청 승인이 필요**하다 `확인됨`. `pip install` 후 기본 가중치를 받으면 모르는 사이에
비상업 의존성이 생긴다.

---

## 5. 움직이는 사람 · 도구가 아니라 촬영이 가른다

### 5-1. 왜 원리적으로 그런가

정적 장면은 3D 점 하나에 광선이 여러 개 생겨 삼각측량이 된다. 그런데
**시각 `t` 에 카메라 1대면 그 점에 광선이 1개**다. 광선 위 깊이가 자유일 뿐 아니라
「깊이가 변한 것」과 「물체가 광선을 따라 움직인 것」이 구분되지 않는다.

폰을 들고 사람 주위를 돌아도 소용없다. 0.5초 뒤 다른 각도에서 본 어깨는
**다른 시각의 다른 위치의 어깨**다. 삼각측량할 두 광선이 영원히 안 생긴다.

Dynamic 3D Gaussians 저자 원문 `확인됨`:
*"Our method also requires a multi-camera setup and does not work off-the-shelf on
monocular video."*

### 5-2. 리그의 본질은 각도가 아니라 「같은 순간」이다

동기 오차 곱하기 사지 속도가 곧 공간 오차다 (계산).

| 사지 속도 | Δt 1 ms | Δt 16.7 ms (60fps 1프레임) | Δt 33.3 ms (30fps 1프레임) |
|---|---|---|---|
| 1 m/s 걷는 손 | 1 mm | 17 mm | 33 mm |
| 3 m/s 보통 제스처 | 3 mm | 50 mm | **100 mm** |

30fps 카메라를 소프트웨어로만 맞추면 뛰는 손이 **10 cm 어긋난 두 광선**으로 삼각측량된다.
그 교점은 어느 프레임에도 없는 점이고 거기 floater 가 생긴다.
**동기 목표는 1 ms 이하, 가능하면 100 µs 이하** (추론).

### 5-3. 해법 세 갈래 · 그리고 결정적 구분

| | 프레임별 독립 | 4D (canonical + 변형장) | 파라메트릭 아바타 |
|---|---|---|---|
| 필수 입력 | 동기 멀티카메라 | 멀티뷰 권장 | **모노큘러 가능** |
| 가진 것 | 시각 `t` | 시각 `t` | **포즈 θ** |
| 산출물 | **재생** | **재생** | **재애니메이션** |
| 대상 | 아무 장면 | 아무 장면 | 사람만 |

**4D 장면 방법은 `t` 만 있어서 타임라인 스크럽만 된다. 아바타는 `θ` 가 있어서 한 번도
안 찍은 동작을 구동할 수 있다.** 로봇 시뮬레이션에 사람을 넣으려면 후자여야 한다.

### 5-4. Postshot 의 「Model Sequence Rendering」은 학습이 아니라 재생이다

v0.5 릴리스 노트 원문 `확인됨`:
*"Import (drag&drop) multiple .PSHT or .PLY files. Each file will correspond to one frame."*

**이것이 전부다.** Postshot 에 4DGS·Deformable·Spacetime 같은 시변 표현은 없다.
독립적인 정적 3DGS 를 N개 각각 학습해 N개 파일로 재생하는 것이고, 학습 시간과 용량이
프레임 수만큼 선형으로 늘어난다.

**쇼케이스 영상을 프레임 추출해 확인한 것** `확인됨`:
타임라인 전체 길이 **737**, 워터마크 **© Infinite-Realities**. 이 스튜디오는
동기화된 6K 머신비전 어레이 · 글로벌 셔터 · 30 FPS · 디스크 초당 3.4 GB 로 스트리밍한다.
**737 프레임이면 모델 파일이 737개다.**

헤더 영상 78초에서 움직이는 인물이 나오는 4편도 전부 동기 어레이 스튜디오 작품이다
(**© New World Designs** · 동기 Z CAM E2 4K **50대**, 많게는 Canon DSLR **240대** ·
**© Electric Lens Co**) `확인됨`.

> **그 영상들은 「Postshot 이 움직이는 것을 찍을 수 있다」는 증거가 아니라
> 「한 순간을 수십 대가 동시에 찍으면 그 정지된 순간을 3DGS 로 만들 수 있다」는 증거다.**

### 5-5. 「모노큘러」라는 단어에 속지 말 것

논문들이 모노큘러라 부르는 데이터 대부분이 사실상 멀티뷰다 `확인됨`.

- **PeopleSnapshot** · 카메라 고정, **피사체가 A-포즈로 제자리 회전** (사람 기준계에서 턴테이블)
- **ZJU-MoCap** · 애초에 **21대 동기 리그**이고 「모노」 실험은 거기서 한 대만 뽑은 것
- **D-NeRF 합성** · 카메라가 프레임마다 순간이동

정량화한 논문이 있다 (EMF · `arXiv 2210.13445` · NeurIPS 2022) `확인됨`:
멀티뷰 단서가 없으면 **masked PSNR 이 1~2 dB 하락, 복잡한 모션에서는 4~5 dB 하락.**
4~5 dB 는 「약간 나쁨」이 아니라 다른 물건이다.

**사람 전용 아바타만이 예외**다. SMPL-X 사전지식이 뒷면을 채우므로 360도가 보이기는 한다.
다만 **그 뒷면은 측정값이 아니라 추정값**이고 로보틱스 평가 자료로 쓰면 안 된다.

---

## 6. 촬영 기하 · 인용 가능한 수치

DESIGN 7절의 재촬영 설계서를 뒷받침하는 «왜» 에 해당한다.

### 6-1. 한 줄로 쓰면 이것이다

```
σ_Z / Z  ≈  σ_d / (f · α)
```

**상대 깊이 오차는 삼각측량각 α 에 반비례하고 거리와는 무관하다.**
기반식 `z = f·B/d`, `|ε_z| = z²/(f·B)·|ε_d|` 는 `arXiv 1705.05548` §2.1 `확인됨`.
위 정리는 거기에 `b = αZ` 를 대입한 것이다 (본 문서의 대수).

f = 1000 px, σ_d = 0.5 px 기준:

| 삼각측량각 | 상대 깊이 오차 |
|---|---|
| 16° · COLMAP 초기쌍 임계 | 0.18 % |
| 6° · local BA | 0.5 % |
| 1.5° · 점 필터 하한 (이 아래는 삭제) | 1.9 % |
| 0.5° | 5.7 % |
| 0.1° · 10 m 거리에서 몇 cm 우발 이동 | **29 %** |

### 6-2. COLMAP 이 「한 자리 촬영」을 거부하는 정확한 경로 `확인됨`

소스 주석 원문 (`estimators/two_view_geometry.h`):
*"it is checked whether the geometry describes a planar scene or panoramic view
(pure rotation) described by a homography. This is a degenerate case, since epipolar
geometry is only defined for a moving camera."*

CVPR 2016 논문 원문:
*"we do not triangulate from panoramic image pairs to avoid erroneous triangulation
angles due to inaccurate pose estimates."*

결과: 모든 쌍이 PANORAMIC 으로 태깅되어 삼각측량에서 제외되고
**유효한 초기 쌍을 영원히 못 찾는다.**

### 6-3. 알아야 할 기본값 셋 `확인됨`

| 항목 | 값 | 뜻 |
|---|---|---|
| `init_min_tri_angle` | 16° | 초기 이미지 쌍. `b = 2Z·tan(θ/2)` 이므로 5 m 앞이면 측면 이동 **1.4 m** 필요 |
| `ModifyForVideoData()` | 16° -> **8°** | **비디오 입력이면 절반으로 낮춘다.** 프레임 추출로 넣는 우리에게 해당 |
| `init_max_forward_motion` | 0.95 | **피사체를 향해 일직선으로 다가가는 촬영을 거부한다.** 전진 방향 시차는 삼각측량에 거의 쓸모가 없다 |

세 번째가 중요하다. **로봇 주행 경로를 그대로 따라 찍으면 정확히 이 함정이다.**

### 6-4. 현장 규칙

**인접 촬영 시점 간 15~30°.** COLMAP 의 16° 임계를 정확히 감싼다.
그 밖에 공식 문서가 직접 말하는 것 `확인됨`:
노출·조리개·ISO 수동 고정 · 수동 초점 · 핸드헬드 최소 1/125 s ·
「같은 자리에서 회전만 하지 말고 매 촬영마다 몇 걸음 옮길 것」.

### 6-5. 프런트엔드를 바꿔서 얻을 것은 거의 없다

GLOMAP README 의 「1~2 자릿수 빠름」은 **수천 장 이상 규모에만 해당한다** `확인됨`.
논문 표 실측은 **1.6배에서 28.6배** 범위이고, 물체 중심 촬영(우리와 가장 유사)에서는
**1.56배**에 COLMAP 정확도가 이미 AUC@3° 96.5 로 포화다.

**200~500장 규모 로봇 촬영에서 병목은 프런트엔드가 아니라 촬영이다.**

---

## 7. 우리 자료에서 확인한 것

### 7-1. 1차 촬영이 지탱할 수 있었던 거리

DESIGN 3-2 (가) 의 실측(첫 프레임에서 최대 이동 **0.80 m**)에 6-3 을 적용하면:

| 임계 | 유효 초기 쌍이 성립하는 최대 거리 |
|---|---|
| 16° (사진 기본) | **2.85 m** |
| 8° (비디오 프리셋) | **5.72 m** |

어느 쪽이든 그 너머는 **알고리즘과 무관하게 구조적으로 복원 불가능했다.**
「원경이 흐리고 포인트가 안 잡힌다」의 정량적 원인이고, 상용 도구를 샀어도 같았다.

### 7-2. `sparse/` 가 세 조각으로 갈려 있다

`_out/colmap/sparse/` 를 직접 세었다 `확인됨`:

| 모델 | 등록 이미지 | 3D 점 |
|---|---|---|
| `sparse/0` | **3** | 2,273 |
| `sparse/1` | 12 | 1 |
| **`sparse/2`** | **287** | **32,727** |

COLMAP 기본값이 `multiple_models = true` · `max_num_models = 50` 이라, 촬영이 끊기면
**오류 없이 여러 조각을 뱉는다.** 그리고 **3DGS 로더 기본 경로는 `sparse/0`** 이다.

**우리 세션은 밟지 않았다.** `RESULTS-3dgs-terrain.md` 가 「루프 검출 없음(채택 ·
`sparse/2`)」 「287 / 287 등록」이라 명시했고 `2_txt` 사본까지 만들어 뒀다.
**다만 3장짜리 조각이 `sparse/0` 에 남아 있으므로 기본 경로를 쓰는 도구나 다음 사람은
조용히 3장으로 학습한다.**

---

## 8. 관문 제안 셋

1. **학습 전 등록 수 대조.** 「등록 이미지 수 = 입력 이미지 수」인가, `sparse/1` 이
   생기지 않았는가를 확인하고 아니면 막는다. 7-2 가 그 실례다
2. **인접 시점 15~30°** 를 현장 규칙으로 고정한다 (6-4)
3. **노출·화이트밸런스·초점 수동 고정.** 못 하면 학습에서 bilateral grid 를 켠다

---

## 9. 확인하지 못한 것

- `Splat3` 의 알고리즘 정체. Jawset 이 어떤 논문도 인용하지 않는다
- Postshot 의 어안·360 카메라 지원 여부. 문서·릴리스노트 전체에 언급 0건
- Postshot 내부 SfM 이 COLMAP/GLOMAP 을 래핑하는지. 구현 비공개
- Free 티어 파일의 유료 티어 호환 방향. 가격 페이지 문구가 모호하다
- `gsplat` 과 `Brush` 가 StopThePop 식 픽셀별 정렬을 구현하는지
- `nvidia/PhysicalAI-Robotics-NuRec` 은 **Gated** 라 접근 승인이 선행 조건이다.
  9개 환경 전부에 메시가 있는 것도 아니다 (공식 설명이 "Some datasets also include
  a mesh and occupancy map")
- RTX 5080 16 GB 에서 Isaac Lab 과 NuRec 동시 구동의 실제 VRAM 여유. **실측 안 함**

---

## 10. 출처

**논문** · 2308.04079 (3DGS) · 2404.09591 (3DGS-MCMC) · 2311.16493 (Mip-Splatting) ·
2404.10484 (AbsGS) · 2403.15530 (Pixel-GS) · 2406.15643 (Taming 3DGS) ·
2403.14166 (Mini-Splatting) · 2402.00525 (StopThePop) · 2412.12507 (3DGUT) ·
2407.07090 (3DGRT) · 2406.00448 (Bilateral Guided) · 2403.13327 (GS on the Move) ·
2403.17888 (2DGS) · 2403.17822 (DN-Splatter) · 2308.09713 (Dynamic 3D Gaussians) ·
2310.08528 (4D-GS) · 2312.16812 (Spacetime Gaussians) · 2210.13445 (EMF) ·
2412.04457 (동적 3DGS 벤치마크) · 2407.21686 (ExAvatar) · 2503.10625 (LHM) ·
2407.20219 (GLOMAP) · 2503.11651 (VGGT) · 2409.19152 (MASt3R-SfM) · 1705.05548 (깊이 오차식)

**공식 문서** · jawset.com/docs (Postshot User Guide 전체 + 릴리스노트 v0.1~v1.1.69) ·
colmap.github.io/tutorial.html · docs.gsplat.studio · nerfbaselines.github.io

**저장소** · nerfstudio-project/gsplat · ArthurBrussee/brush · nv-tlabs/3dgrut ·
playcanvas/supersplat · playcanvas/splat-transform · nianticlabs/spz · colmap/colmap

**우리 원자료** · `inbox/jay/20260916-3dgs-test/_out/colmap/sparse/{0,1,2}` ·
`RESULTS-3dgs-terrain.md` · `DESIGN-real-to-sim.md`

---

## 판 이력

| 판 | 날짜 | 무엇 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-18 | 처음 씀. Postshot 전수 분석, 오픈소스 대응표, 움직이는 피사체 세 갈래, 촬영 기하 수치, 우리 `sparse/` 조각 실측 | 공식 문서·논문 원문·저장소 소스·우리 원자료 |
