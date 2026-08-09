# 시각 증거 — 우리가 실제로 본 것

> 작성 2026-08-09 · 워크스테이션 세션
> **이 문서의 목적**: 학습 결과를 숫자로만 보지 않고 **눈으로 확인한 기록**을 남긴다.
> 로봇공학을 모르는 사람이 봐도 "무슨 일이 있었는지" 알 수 있게 쓴다.

모든 이미지는 영상에서 **1초 간격으로 프레임을 뽑아 격자로 붙인 것**이다.
왼쪽 위 노란 숫자가 영상 안에서의 시각(초)이다.

---

## 왜 프레임을 뽑았나

학습 결과는 보통 **숫자 두 개**(보상, 에피소드 길이)로만 확인한다.
그런데 숫자만으로는 *"로봇이 실제로 어떻게 움직이는지"*를 모른다.

영상에서 프레임을 뽑아 나란히 놓으면 **로봇이 화면 어디에 있는지**가 보인다.
**위치가 변하면 걷는 것이고, 안 변하면 제자리에 있는 것이다.** 이게 가장 확실한 검증이다.

> 커널 원칙 3 — *사용자가 겪는 층위에서 확인한다.*
> 학습 로그의 숫자는 대리 신호(proxy)다. 영상은 결과 그 자체다.

**추출 방법** (도구 설치 불필요, 이미 있는 것으로 됨):
`imageio_ffmpeg` 패키지에 동봉된 ffmpeg + OpenCV. 스크립트 40줄.

---

## 00. 목표 지점 — Unitree 공식 영상

![reference](../assets/visual/00_reference_unitree_official.png)

| | |
|---|---|
| 출처 | Unitree 공식 Go2 홍보 영상 (`00_reference/unitree-go2-official.mp4`) |
| 사양 | 1920×1080 · 50fps · 5.4초 |

**★ 중요한 사실: 이것은 CG가 아니라 실물 로봇 실사 촬영이다.**

보이는 것: 강가 자갈밭, **역광**, 물보라 입자가 빛을 받아 반짝임, **얕은 심도**로 배경 나무가 흐려짐,
낮은 카메라 앵글, 젖은 돌의 스페큘러, 크기가 제각각인 실제 자갈, 원경의 산.

우리 목표가 *"이 수준으로 렌더한다"*라면, 정확히는
**"실사 촬영물과 구분되지 않는 CG를 만든다"** — VFX에서 가장 어려운 과제다.

---

## 01. A 정책 — 플래그 없음, 300 iteration

![trainA](../assets/visual/01_trainA_noflag_300iter.png)

| 항목 | 값 |
|---|---|
| 실행 | `logs/rsl_rl/unitree_go2_rough/2026-08-09_14-00-20` |
| 조건 | 기본 설정 (추가 플래그 없음), seed 42 |
| 학습 시간 | **22.07분** (300 iteration) |
| 처리량 | 22,867 steps/s |
| **마지막 20회 평균 보상** | **13.94** |
| **마지막 20회 평균 에피소드 길이** | **938.7 step** (최대 1000) |
| 영상 | 1280×720 50fps 10초 · `assets/video/trainA_noflag_300iter.mp4` |

**읽는 법 — 로봇의 화면상 위치를 보라:**

| 시각 | 위치 |
|---|---|
| 1.2초 | 중앙 타일에 2마리 |
| 7.5초 | **화면 왼쪽 끝까지 이동** |
| 10.0초 | 왼쪽 가장자리 |

**→ 로봇이 화면을 가로질러 이동한다. 걷고 있다.**

**화살표 읽는 법**: Isaac Lab은 로봇 위에 화살표 2개를 그린다.
- **초록 = 명령받은 속도** (가라고 시킨 방향·크기)
- **파랑 = 실제 속도** (진짜 가고 있는 방향·크기)

A에서는 **둘 다 뚜렷하다** = 시킨 대로 가고 있다.

---

## 02. B 정책 — 플래그 있음, 300 iteration

![trainB](../assets/visual/02_trainB_flag_300iter.png)

| 항목 | 값 |
|---|---|
| 실행 | `logs/rsl_rl/unitree_go2_rough/2026-08-09_14-22-51` |
| 조건 | `--kit_args="--/physics/collisionApproximateCylinders=true"`, seed 42 |
| 학습 시간 | **9.48분** (300 iteration) — A의 **2.3배 빠름** |
| 처리량 | 54,898 steps/s |
| **마지막 20회 평균 보상** | **3.54** — A의 **25%** |
| **마지막 20회 평균 에피소드 길이** | **551.1 step** |
| 영상 | `assets/video/trainB_flag_300iter.mp4` |

**읽는 법:**

| 시각 | 위치 |
|---|---|
| 1.2초 | 중앙 타일 |
| 10.0초 | **거의 같은 자리** |

**→ 10초 동안 화면상 위치가 거의 변하지 않는다. 제자리에서 주저앉아 있다.**

화살표: **초록(명령)만 크고 파랑(실제)이 거의 없다** = 시켰는데 못 간다.

### 그 플래그가 무엇이었나

`collisionApproximateCylinders=true` — Go2의 정강이는 **원통(cylinder) 충돌체**다.
원통은 충돌 계산이 비싸다. 이 스위치는 그 원통을 **더 단순한 모양으로 근사**하게 만든다.

**계산은 2.4배 빨라졌지만, 발이 땅에 닿는 방식이 부정확해져서 로봇이 제대로 못 배웠다.**

> 비유: 달리기 연습을 하는데 **신발 밑창의 요철을 뭉갠 것**. 계산은 편해지지만
> 실제로 어떻게 미끄러지는지를 못 배운다.

### 공정성 검증 — 같은 시간을 줘도 못 따라잡는다

*"B가 2.3배 빠르니 그만큼 더 돌리면 되지 않나?"* 를 실측했다.

| | A (300회) | B (700회) |
|---|---|---|
| 벽시계 시간 | 22.07분 | **24.02분** (9% 더 씀) |
| 보상 | **13.94** | 4.80 |
| 에피소드 길이 | **938.7** | 605.4 |

**→ B는 2.33배 더 돌리고 9% 더 써도 A의 34%에 머문다. 정체됐다. 플래그 봉인 확정.**

### 학습 곡선 (A)

| iteration | 보상 | 에피소드 길이 |
|---|---|---|
| 1 | −0.47 | 11.87 |
| 30 | −2.32 | 425.53 |
| 193 | +10.78 | 983.82 |
| 277 | +13.32 | 898.35 |
| 300 | **+13.94** | 938.7 |

**에피소드 길이가 193→277에서 줄어든 것은 나빠진 게 아니다.**
지형 커리큘럼이 **로봇을 더 어려운 지형으로 승급**시켰기 때문이다
(잘하면 위 행으로, 못하면 아래 행으로. 함수: `terrain_levels_vel`).
보상은 그 구간에도 계속 올랐다.

---

## 03. ★ 학습 씬 ≠ 렌더 씬 — 분리 실증 (성공)

![warehouse](../assets/visual/03_usdscene_warehouse.png)

| 항목 | 값 |
|---|---|
| 정책 | **A 정책** (회색 절차생성 험지에서 학습한 것) |
| 씬 | `Environments/Simple_Warehouse/warehouse.usd` — **학습에 쓴 적 없는 씬** |
| 스크립트 | `C:\isaac\IsaacLab\play_go2_in_usd.py` (NVIDIA 공식 튜토리얼의 Go2판) |
| 소요 | 1.78분 (400 스텝 = 8초) |
| 영상 | `assets/video/usdscene_warehouse.mp4` |

**이것이 증명한 것:**

> **회색 무텍스처 지형에서 학습한 정책을, 정책 파일만 들고 나와서,
> 텍스처와 조명이 있는 완전히 다른 씬에서 걷게 할 수 있다.**

바닥에 타일 텍스처와 반사가 있고, 배경에 선반과 팔레트가 보인다.
01·02의 회색 지형과 비교하면 시각적 차이가 명백하다.

### 왜 이것이 프로젝트의 주춧돌인가

```
[학습 단계]  회색 무텍스처 · 로봇 4096마리 · 렌더 끔(headless)
             → 목적: 속도. 예쁠 필요가 0.
             → 산출물: model.pt (6.9MB)

                        ↓  ★정책만 들고 넘어간다 (여기가 03이 증명한 지점)

[렌더 단계]  로봇 1마리 · 실사 지형 · Path Tracing · 시네마틱 카메라
             → 목적: 품질. 느려도 됨.
```

**이는 VFX 파이프라인과 같은 구조다** — 시뮬레이션 캐시를 굽고, 라이팅·렌더를 따로 한다.
시뮬 단계에서 예쁠 필요가 없다.

### 핵심 코드 (한 줄)

```python
env_cfg.scene.terrain = TerrainImporterCfg(
    prim_path="/World/ground",
    terrain_type="usd",              # ← 절차생성 지형 대신
    usd_path="...warehouse.usd",     # ← USD 파일을 통째로 지형으로
)
```

---

## 04. 같은 방법의 실패 사례 — 사무실 씬

![office](../assets/visual/04_usdscene_office_FAILED.png)

| 항목 | 값 |
|---|---|
| 씬 | `Environments/Office/office.usd` |
| 결과 | 스크립트는 **exit=0으로 정상 종료**, mp4도 생성됨. **그러나 화면에 로봇이 없다** |
| 소요 | 5.39분 (warehouse의 3배 — 씬이 무겁다) |

화면 대부분이 흰 벽이다. **카메라가 벽 안쪽에 박혔거나, 로봇이 벽 안에 스폰됐다.**

### 여기서 배운 것 — 두 가지

**① USD 씬을 바꾸는 것은 "한 줄"이지만, 씬마다 스폰 위치와 카메라를 맞춰야 한다.**
warehouse는 원점에 넓은 바닥이 있어 우연히 됐고, office는 원점에 벽이 있다.
실사 지형(3DGS 스캔)을 넣을 때도 같은 작업이 필요하다.

**② 이것이 "조용한 실패"의 교과서적 사례다.**

> 스크립트는 **성공(exit=0)을 보고했고, mp4 파일도 만들었다.**
> 프레임을 눈으로 보지 않았다면 **"사무실 씬도 성공"이라고 보고했을 것이다.**

커널 원칙 2 — *조용한 실패를 소리 나게 만든다.* 그리고 원칙 3 — *사용자가 겪는 층위에서 확인한다.*
**프레임을 뽑아 본 것이 이 실패를 잡았다.**

---

## 부록: 재현 방법

```powershell
conda activate isaac311
cd C:\isaac\IsaacLab
$env:OMNI_KIT_ACCEPT_EULA="YES"

# 학습한 정책을 원래 지형에서 재생 (영상 저장)
#   ⚠️ --checkpoint 는 파일명이 아니라 전체 경로를 받는다 (play.py:109)
python play_go2_win.py --task Isaac-Velocity-Rough-Unitree-Go2-Play-v0 `
  --num_envs 16 --headless --video --video_length 500 `
  --checkpoint "C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_rough\2026-08-09_14-00-20\model_299.pt"

# 학습한 정책을 다른 USD 씬에서 재생
#   ⚠️ 이쪽은 JIT(TorchScript)로 익스포트된 exported/policy.pt 를 받는다
python play_go2_in_usd.py `
  --checkpoint "C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_rough\2026-08-09_14-00-20\exported\policy.pt" `
  --env_usd "Environments/Simple_Warehouse/warehouse.usd" `
  --steps 400 --headless --video --tag warehouse
```

**프레임 추출**: `scratchpad/frames.py` 참조 (OpenCV + `imageio_ffmpeg` 동봉 ffmpeg).

---

## 연결

- 수치 정본 → [training-benchmarks.md](training-benchmarks.md)
- 아키텍처 결정 → [architecture-decision.md](architecture-decision.md)
- 곡선으로 보기 → TensorBoard `logs/rsl_rl/unitree_go2_rough` (LAN: `:6006`)
