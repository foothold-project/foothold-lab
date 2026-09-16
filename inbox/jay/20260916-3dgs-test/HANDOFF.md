# 3DGS 지형 PoC · 세션 핸드오프 (2026-09-16)

> 작성: lead 세션(브랜드 영상 담당)이 팀장 오흥재 지시로 작성. 이 파일이 새 세션의 출발점이다.
> 상태: 착수 전. 이 문서의 "질문" 항목은 새 세션이 조사로 답한다.

## 0. 먼저 읽을 것 (순서대로)

1. `AGENTS.md` (저장소 규칙 전부. CLAUDE.md는 포인터일 뿐이다)
2. `README.md`, `sim/README.md`, `sim/twin/README.md`
3. `docs/` 의 프로젝트 정본 (특히 `docs/decisions/`, `docs/notices/`). 프로젝트 사이트: https://foothold-project.vercel.app (기술 허브: /hub-tech)
4. 이 문서

가장 자주 어기는 규칙 셋: **작업 전 `git pull origin main`** · **`docs/`를 직접 고치지 않는다(제출은 `inbox/jay/` 아래에만)** · **em dash(U+2014) 금지(빌드가 배포를 막는다)**. `sim/` 아래에 넣을 것이 생기면 브랜치를 파고 PR로 올린다(inbox를 거치지 않는다). PoC 단계의 산출물·리포트는 이 폴더(`inbox/jay/20260916-3dgs-test/`)에 둔다. 새 폴더 트리를 임의로 만들지 않는다. 대용량 산출물(프레임·포인트클라우드·메시)은 저장소에 커밋하지 않고 `.gitignore` 대상 하위 폴더에 두며 경로만 기록한다.

## 1. 프로젝트가 무엇인가

FOOTHOLD = **Unitree Go2 사족보행 로봇의 "미경험 험지 적응" 시뮬레이션 및 실기 자율주행 프로젝트**. 슬로건 FIND THE NEXT STEP. 정체성은 "불확실한 지형에서도 다음 걸음을 이어간다".

- 트랙 A(시뮬레이션): Isaac Sim 5.1 + Isaac Lab, RSL-RL PPO로 Go2 보행 정책 학습·평가. 학습 환경 `Isaac-Velocity-Rough-Unitree-Go2-v0`. 환경: conda `isaac311` (`C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe`). NVIDIA 사전학습 체크포인트: `C:\isaac\IsaacLab\.pretrained_checkpoints\rsl_rl\Isaac-Velocity-Rough-Unitree-Go2-v0\checkpoint.pt` (우리 자체 학습 pt는 `sim/policy/`·`models/` 및 docs 정본을 확인).
- `sim/twin/` = "A/트윈렌더 · 실공간 복원 · 3DGS · RTX 렌더 · 합성데이터, 담당 맹라현". **이번 PoC는 이 영역과 겹친다.** 담당자 자료가 있으면 먼저 읽고 중복하지 않는다.
- 최종 그림: 우리가 학습한 정책(.pt)을 Go2에 입혀, **실제 지형을 디지털 트윈으로 재현한 시뮬 공간**에서 보행시키고, 이후 실기로 간다.

## 2. 이번 PoC 목표 (팀장 원문 요지)

"Gaussian Splatting으로 바닥을 Mesh화하고, 그 지형 위에 Go2를 올려서 우리가 학습시킨 모델이 실제 지형에서도 보행하는 데 문제가 없음을 MVP로 보여준다."

**핵심 집중점(팀장 지정)**: 바닥이 **메시로 잘 뜨는가**, 포인트 클라우드가 잘 뜨는가, 그것을 **어떻게 매끄럽게 메시화**하는가. 보이는 품질(렌더 룩)은 나중 단계.

입력 자료: `inbox/jay/20260916-3dgs-test/test_20260916_112122728.mp4` (스마트폰 영상, HEVC, 23.976fps, 35.9초). 모션블러가 있을 수 있음을 감안한 "가능성 파악용" 테스트.

## 3. 팀장의 사전 이해 (맞는지 검증해서 답할 것)

1. 사진이 더 좋다(모션블러 없음). 하지만 이번은 영상으로 어디까지 되는지 본다.
2. VFX 관행처럼 **카메라 왜곡을 편 뒤(undistort) 선형 3D 공간에서 작업**해야 한다. 3DGS(사진·영상 모두)에도 이 과정이 필요한가?
3. 왜곡을 편 영상에서 **프레임을 추출해 데이터화**해서 쓰는 게 맞는가? (프레임 간격, 블러 프레임 제거 기준 등)
4. NVIDIA 공식 페이지에 "스마트폰 영상 → 메시" 방법이 제시되어 있다고 안다. 정확히 어떤 도구·문서인지 확인.

새 세션이 답할 것: 위 이해가 실제 3DGS→메시 워크플로와 같은지, 다른 점은 무엇인지.

## 4. 조사 (deep-research 스킬 사용)

주제: **스마트폰 영상 → (COLMAP/undistort) → 3D Gaussian Splatting → 지면 메시 추출 → Isaac Sim 5.1 지형(충돌체 포함) → Go2 정책 보행 검증** 의 실제 파이프라인. 근거 있는 출처로:
- 도구 후보 비교: nerfstudio/gsplat, 원본 3DGS, PostShot, Polycam 등 (Windows 11 + RTX 환경에서 실제 되는 것 위주)
- 메시 추출: SuGaR, 2DGS, GOF 등 "splat → mesh" 방법과 지면 평활화(hole filling, decimation, 충돌 메시 생성)
- NVIDIA 쪽: Isaac Sim 5.x의 Neural Reconstruction / 3DGS(USDZ) 지원 여부, 3DGRUT, Instant-NGP 계열, "스마트폰 영상 → 메시" 공식 가이드의 정확한 출처
- 카메라 왜곡·프레임 추출·블러 처리 관행
- Isaac Lab에서 커스텀 지형 메시(USD) 위에 Go2 + RSL-RL 정책 올리는 방법(height scan 등 관측 호환)

산출: 리포트 1편(한국어, 출처 링크 포함, em dash 금지)을 이 폴더에 `RESEARCH-3dgs-terrain.md` 로 저장. 팀장이 기술 허브(hub-tech)에 올리길 원하므로 허브 형식(4쪽: ROS 2 · RL · SLAM · CV 중 해당 쪽)을 `docs/decisions/20260912-research-hub-redesign.md` 에서 확인하고 그 형식에 맞춘다. **docs/ 직접 수정 금지, 이 폴더에 제출본을 두고 팀장이 반영.**

## 5. 실행 단계 (제안, 조사 후 확정)

1. 영상 프레임 추출(블러 프레임 제거 기준 포함) → COLMAP SfM + undistort → 3DGS 학습(작은 규모부터)
2. 스플랫 → 지면 메시 추출 → 평활화·구멍 메움·데시메이션 → 충돌 메시(USD) 저장
3. Isaac Sim 5.1에 지형 USD 로드 → Go2 + 체크포인트로 보행 시험(우선 NVIDIA 사전학습 pt, 다음 우리 pt) → 짧은 영상·수치(낙상 여부, 발 관통, height scan 정상 여부) 기록
4. 각 단계 결과·한계·다음 단계를 이 폴더에 기록

## 6. 경계 (지키지 않으면 남의 작업이 망가진다)

- **남의 GPU 작업을 절대 죽이지 않는다.** 지금 이 머신에서 `sim/eval/record_terrain_demo.py` 렌더가 다른 세션에서 돌고 있을 수 있다. 프로세스를 정리할 때 자기 것만.
- **브랜드 영상 작업(lead 세션)과 분리**: `C:\Users\AI-WS01\AppData\Local\Temp\claude\...\scratchpad\launch_render\` 및 `render_brand.py`, `inbox/jay/20260904-launch/` 는 건드리지 않는다. `sim/eval` 도 수정하지 않는다.
- `CUDA_VISIBLE_DEVICES` 를 설정하지 않는다(과거 검은 프레임 원인).
- 크리덴셜·API 키를 다루지 않는다. 필요한 로그인은 팀장이 직접.
- 보고는 사실대로: 실패했으면 실패, 미확인은 미확인.

## 7. 관리자 세션

이 저장소의 최종 관리자 세션은 Orca 터미널 "super" (`term_166c0261-0e0e-47ff-b8a0-82af6dbb1d30`) 이다. 핸드오프 사실은 lead 세션이 super에 통지했다. 진행 보고·질문은 팀장에게 직접 하고, 저장소 전체에 영향 있는 결정은 super의 확인을 받는다.
