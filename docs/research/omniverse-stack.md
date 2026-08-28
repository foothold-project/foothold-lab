# NVIDIA 도구 지도: Omniverse · Isaac Sim · SimReady 가 각각 무엇인가

> 분류: 리서치
> 작성: 오흥재 · 2026-08-12 10:41
> 근거: 공식 문서
> 요지: Isaac Sim 과 USD Composer 는 같은 RTX 렌더러다. 화질은 렌더러가 아니라 에셋(룩뎁)에서 갈린다.
> 상태: 확정
> 판: v1.0

> 작성 2026-08-12 · 워크스테이션 세션 · 방법: 공식 문서 + 쇼케이스 1차 출처 + 우리 실측(렌더 벤치마크·Racer 프레임 분석) 연결
> 목적: «이 도구들이 서로 무슨 관계인가»를 한 장으로. 팀장이 VFX 출신이라 **Foundry 라인업에 빗대어** 설명한다.

## 1. 한 장 지도: Foundry 에 빗대면

| Foundry 세계 | 층위 | **NVIDIA 세계** | 정체 |
|---|---|---|---|
| EXR · Alembic | 파일 표준 | **OpenUSD** | 씬·에셋의 공통 파일 형식. Pixar 가 만들었다 |
| - | 협업 플랫폼 | **Omniverse** | 여러 툴이 같은 USD 를 실시간으로 함께 편집하는 판 |
| NDK | 앱 엔진 | **Omniverse Kit** | 아래 앱들이 전부 이 위에 얹혀 있다 |
| **Katana** | 조립·룩뎁·렌더 앱 | **USD Composer** (구 Create) | 모델링 도구가 아니다. 불러와서 조립·라이팅·렌더 |
| - | 로봇 시뮬 앱 | **Isaac Sim** | USD Composer 와 **같은 Kit 위의 형제 앱** |
| - | 그 위의 라이브러리 | **Isaac Lab** | 강화학습 프레임워크. 앱이 아니라 파이썬 라이브러리 |
| Karma · Arnold | 렌더러 | **RTX Renderer** | **Isaac Sim 과 USD Composer 가 이것을 공유한다** |
| - | 물리 엔진 | **PhysX** | 기본 물리. (차세대 Newton 은 험지 미지원이라 우리는 금지) |
| Mari | 3D 텍스처 | (없음 → **Substance 3D Painter** 를 쓴다) | |
| - | 에셋 품질 라벨 | **SimReady** | «물리 속성이 붙어 시뮬에 바로 쓸 수 있는 USD» 인증 표식 |

> ### 핵심 한 줄
> **Isaac Sim 과 USD Composer 는 같은 RTX 렌더러를 쓴다.** `확인됨` ([공식 문서](https://docs.isaacsim.omniverse.nvidia.com/latest/reference_material/rendering_modes.html))
> 그래서 «시뮬은 Isaac, 시연 영상은 Omniverse 에서» 라고 따로 갈 필요가 없다. 이미 같은 렌더러다.
> **화질 차이는 렌더러가 아니라 에셋(룩뎁)에서 갈린다.**

## 2. 렌더 품질의 상한: 눈으로 확인할 수 있는 사례

전부 클릭해서 직접 볼 수 있는 1차 출처다.

| 사례 | 무엇 | 품질 판정 | 도구 조합 |
|---|---|---|---|
| [Ramen Shop](https://www.behance.net/gallery/146438613/Ramen-Shop-NVIDIA-Omniverse) ([제작기](https://80.lv/articles/photorealistic-ramen-shop-made-in-nvidia-omniverse)) | 도쿄 라멘집 인테리어 | **실사와 구분이 어려운 수준에 가장 근접한 공개 사례** | ZBrush·Blender 모델링 + Substance 텍스처 + Omniverse 렌더. 4K 텍스처 3,000장 · 레퍼런스 사진 2,000장 |
| [Marbles at Night](https://www.youtube.com/watch?v=NgcYLIvlp_k) ([비하인드](https://blogs.nvidia.com/blog/omniverse-marbles-rtx-playable-sample/)) | 물리 기반 구슬 게임 | 실시간 기준 최상급. RTX 3090 한 장 1440p | 수작업 에셋 165개 · 텍스처 500GB |
| [Racer RTX](https://www.youtube.com/watch?v=AsykNkUMoNU) | RC카 질주 | 실사급 재질. **단 모래·먼지는 물리가 아니라 대부분 모션블러다**: 우리가 프레임 단위로 확인했다 → [render-benchmarks.md](render-benchmarks.md) §4-2 | ZBrush·Maya·Blender + Substance |
| [BMW 가상 공장](https://www.youtube.com/watch?v=g78YHYXXils) | 산업 디지털 트윈 | 시각화로는 훌륭. VFX 기준으로는 «클린한 CG» 티가 남 | 커스텀 CAD 룩뎁 |

> ### 정직한 단서
> 위 쇼케이스는 전부 **외부 DCC 로 수개월 수작업한 에셋**을 Omniverse 로 렌더한 것이다.
> Omniverse 는 «렌더러 + 조립 도구»다. **에셋을 좋게 만들어 주는 도구가 아니다.**
> Isaac Sim 기본 콘텐츠(창고·오피스)는 로봇 테스트용이라 룩뎁 기준으로 만든 것이 아니다.
> 우리 실측에서도 창고 씬은 Path Tracing 을 켜도 차이가 작았다 → [render-benchmarks.md](render-benchmarks.md) §4.

## 3. 지금 받아서 쓸 수 있는 에셋 (전부 근거 링크)

| # | 무엇 | 규모 | 라이선스 | 난이도 |
|---|---|---|---|---|
| 1 | [NVIDIA 공식 USD 팩](https://docs.omniverse.nvidia.com/usd/latest/usd_content_samples/downloadable_packs.html): SimReady Warehouse 01/02 · Containers · Residential · **Sample Scenes(441개, 26GB: Marbles·Old Attic 쇼케이스 원본 포함)** · Skies | 팩당 9~26GB | 프로젝트 사용 무료 | 최하 (드래그) |
| 2 | [PhysicalAI SimReady Warehouse](https://huggingface.co/datasets/nvidia/PhysicalAI-SimReady-Warehouse-01) | USD 753개 · 15GB | **CC-BY-4.0** | 최하 |
| 3 | [vMaterials 2](https://developer.nvidia.com/vmaterials) | 측정 기반 물리 재질 **1,854종** · 5.5GB | 무료 | 하: 재질만 갈아끼움 |
| 4 | [Poly Haven](https://polyhaven.com) · [AmbientCG](https://ambientcg.com) | HDRI 16K · 텍스처 · 모델 | **CC0** | 하 |
| 5 | [Unitree 공식 Go2 USD](https://github.com/unitreerobotics/unitree_model) · [CAD](https://github.com/unitreerobotics/unitree_cad) | 로봇 모델 | BSD-3 | 하 |

- **가장 싸게 룩이 올라가는 순서: HDRI 하나 → vMaterials → 스캔 에셋.**
  돔 라이트에 실사 HDRI 를 거는 것 하나로 «회색 디퓨즈» 인상이 가장 크게 바뀐다.
- 위험지역(잔해·터널) 계열은 Sketchfab 포토그래메트리 스캔이 실사에 가장 유리하다.
  ⚠️ **UE 전용 팩은 피할 것**: Unreal 재질·블루프린트 의존이라 USD 변환 시 셰이더가 깨진다.
- 워크스테이션 보유 현황(2026-08-12): Poly Haven HDRI 1장 수령(`C:\isaac\assets\hdri\`) · vMaterials·Sample Scenes 는 미수령.

### Go2 모델에 대한 정직한 답

**«영화용 히어로 에셋» 수준의 Go2 는 시판되지 않는다.** `미확인` (부재 증명 불가)
실사급 클로즈업이 필요하면 공식 CAD + 직접 룩뎁(Substance)이 현실적 경로다. 이건 팀장의 본업 영역이다.

## 4. 우리 프로젝트에서의 결론

| 컷 성격 | 도구 |
|---|---|
| 로봇 클로즈업 · 핵심 컷 | **Blender** (설치 완료 · 제어권 최상) |
| 넓은 씬 · 다수 컷 | **Isaac Sim Path Tracing** (실측 1.75초/프레임 @1080p 128spp) |
| 원경 실사 배경 | NuRec/3DGS (5.1 은 조명 상호작용 약함 · 6.0 에서 개선) |

컷마다 섞어 쓰는 것: VFX 에서 늘 하던 방식이고, 팀장이 확정한 방향이다(2026-08-12).

## 연결

- 렌더 실측·Racer 프레임 판정 → [render-benchmarks.md](render-benchmarks.md)
- 시각 증거 → [visual-evidence.md](visual-evidence.md)
- 아키텍처(버전·EOL) → [architecture-decision.md](architecture-decision.md)

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-08-12 | 처음 씀 | 이전 이력은 git 에 |
