# 클라우드 GPU에서 Isaac Sim 돌리기 — 가능성 조사

> 작성 2026-08-08 · 방법: NVIDIA 공식 문서·포럼·NGC 카탈로그·GitHub 이슈 직접 확인 · 상태: **코덱스 교차검증 대기**
> 배경: 팀원 4명 노트북에 RTX 없음(GTX 1650 Ti / RTX 30 구형) → 로컬 실행 불가. **RunPod 시도했으나 실패** 보고를 받아 원인 조사.
> 연결: [[SETUP_GUIDE]] · [[TEAM_ACCESS]] · [[mvp-install-log]]

---

## 🔴 결론 3줄

1. **RunPod 실패의 최유력 원인 = A100/H100 선택.** NVIDIA 공식 문서에 *"GPUs without RT Cores (A100, H100) are not supported"* 명시. `확인됨`
2. **★ 우리 버전과 정확히 일치하는 공식 컨테이너가 NGC에 이미 있다** — `nvcr.io/nvidia/isaac-lab:2.3.2`, `nvcr.io/nvidia/isaac-sim:5.1.0`. **직접 빌드 불필요.** `확인됨`
3. **가장 검증된 경로 = AWS `g6e`(L40S) + 공식 AMI 또는 위 컨테이너.** NVIDIA가 직접 문서화한 배포 가이드가 있다. `확인됨`

---

## 1. GPU 요구사항 — RT 코어가 관문이다

**NVIDIA 공식 원문** (https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html):
> **"GPUs without RT Cores (A100, H100) are not supported."**

- 최소 **GeForce RTX 4080 (16GB)** / 권장 RTX 5080 / 이상적 RTX PRO 6000 Blackwell(48GB)
- NVIDIA 직원 확인: *"An H100 is for compute ONLY. **It is not suitable for anything Isaac Sim**"* — 대안으로 A5000·A6000·L40/L40s 권장
  https://forums.developer.nvidia.com/t/isaac-sim-newton-physics-on-h100-gpu/370921
- A100에 대해서도: *"The A100 is not supported. Isaac Sim requires a GPU with RT cores for rendering. **NVENC is also required for live-streaming**"*
  https://forums.developer.nvidia.com/t/isaac-sim-a100-apptainer-singularity-support/285273

| GPU | RT 코어 | Isaac Sim | 근거 |
|---|---|---|---|
| **A100 / H100 / H200 / B200** | **없음** | 🔴 **공식 미지원** | 요구사양 문서 명시 |
| **L40S** | 있음 (3세대 142개) | ✅ NVIDIA 직원 권장 · AWS 공식 경로 | nvidia.com/data-center/l40s |
| L4 | 있음 | ✅ (Isaac Automator g6 지원) | — |
| A10G | 있음 (GPU당 80개) | ✅ (Automator g5 지원) | AWS g5 페이지 원문에 *"80 ray tracing cores"* |
| RTX 4090 / A6000 / 6000 Ada | 있음 | ✅ | 요구사양 + 포럼 권장 |
| T4 | 있음(Turing) | △ 구버전 최소선, **5.1 권장사양 미달** | 포럼 232237 |
| V100 | 없음 | 🔴 미지원 | 헤드리스 시도 실패 사례 |

### ⚠️ "헤드리스면 RT 코어 없어도 되지 않나" — **공식적으로 부정됨** `부분확인`
- NVIDIA 직원들이 헤드리스 우회 가능성을 **일관되게 부정**(스레드 232237, 370921)
- 단 커뮤니티 사례: A100 + Docker에서 Isaac Sim **4.0.0**이 *"오류가 좀 있지만 시뮬레이터는 작동"* 보고 있음
- **5.1에서의 A100 성공 사례는 미확인.** → **팀 프로젝트 기반으로 삼지 말 것**

---

## 2. RunPod에서 왜 실패했나

**RunPod GPU 목록 및 시작가** (https://www.runpod.io/gpu-models, 2026-08-08 조회)

| RT 코어 **있음** (Isaac Sim 가능) | 시작가/hr |
|---|---|
| **RTX A5000** | **$0.16** |
| **RTX A6000** | **$0.33** |
| **RTX 4090** | **$0.34** |
| A40 | $0.35 |
| L4 | $0.44 |
| L40 | $0.69 |
| RTX 5090 | $0.69 |
| RTX 6000 Ada | $0.74 |
| **L40S** | **$0.79** |
| RTX Pro 6000 | $1.69 |

| RT 코어 **없음** (🔴 불가) | |
|---|---|
| A100 | $1.19~1.39 |
| H100 | $1.99~2.69 |
| H200 · B200 | — |

### 실패 원인 후보 (근거 순)

**① A100/H100 선택** — 가장 유력. RunPod에서 "AI 학습"으로 흔히 고르는 게 이 둘이고, 공식 미지원이다. RTX 렌더러 생성 실패로 초기화 단계에서 죽는다.
→ **팀원에게 "어떤 GPU를 골랐는지" 확인이 1순위.**

**② RunPod 데이터센터의 UDP 차단** `확인됨` — RT 코어 GPU를 골랐어도 실패하는 **문서화된 RunPod 고유 이슈**가 있다.
공식 Isaac Lab 컨테이너가 **UDP가 비활성화된 RunPod 데이터센터에서 `/workspace/isaaclab/`이 빈 채로 실패**한다. RunPod 지원팀이 수일 조사 끝에 UDP를 원인으로 지목했고 **이슈는 미해결로 열려 있다.**
https://github.com/isaac-sim/IsaacLab/issues/2271

**③ 파드 안에서 Docker 재실행 불가** (추정, `미확인`) — RunPod 파드 자체가 컨테이너라 Isaac Lab의 표준 `docker/container.py` 워크플로가 안 통한다. **이미지를 파드 템플릿으로 직접 지정**해야 한다.

> RunPod에서의 명시적 **성공 사례**(GPU·이미지·설정 명기)는 찾지 못했다 — `미확인`

---

## 3. AWS — 가장 문서화된 경로 `확인됨`

| 인스턴스 | GPU | RT 코어 | Isaac Sim |
|---|---|---|---|
| **g6e** | **L40S 48GB** | ✅ | **NVIDIA 공식 권장** (`g6e.2xlarge`) |
| g7e | RTX Pro 6000 | ✅ | 공식 가이드에 `g7e.8xlarge` 명시 |
| g6 | L4 24GB | ✅ | 가능 (Automator 지원) |
| g5 | A10G 24GB | ✅ | 가능 (Automator 지원) |
| g4dn | T4 16GB | ✅ | 구버전 최소선, 5.1 권장 미달 |
| **p4 (A100) / p5 (H100)** | — | ❌ | 🔴 **불가** |

- **NVIDIA 공식 AWS 배포 가이드** (인스턴스·AMI·드라이버·컨테이너 절차 전부):
  https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_advanced_cloud_setup_aws.html
- **AWS Marketplace 공식 AMI**: *"NVIDIA Isaac Sim™ Development Workstation"* — Isaac Sim·VS Code·Docker·인증 드라이버 사전 설치. **AMI 자체는 무료**(인프라 비용만)
- **Isaac Automator** (AWS/GCP/Azure 자동 배포, 기본 `g6e.2xlarge`): https://github.com/isaac-sim/IsaacAutomator
- **요금** (2026-08-08, instances.vantage.sh): `g6e.xlarge`(L40S 48GB, 4vCPU/32GB) **온디맨드 $1.861/hr · 스팟 $1.798/hr**
  ⚠️ 다른 사이즈·리전은 `미확인` — 직접 조회할 것

---

## 4. ★★ Docker — 공식 이미지가 우리 버전과 정확히 일치한다 `확인됨`

```
nvcr.io/nvidia/isaac-sim:5.1.0      ← 우리가 쓰는 버전
nvcr.io/nvidia/isaac-lab:2.3.2      ← 우리가 고정한 태그와 동일
```
- Isaac Sim 컨테이너: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/isaac-sim
- **Isaac Lab 컨테이너도 별도로 존재하며 `2.3.2` 태그가 있다**: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/isaac-lab

> ### 이게 이 조사에서 가장 중요한 발견이다
> **직접 빌드가 필요 없다.** 우분투에서 Docker로 전환할 때도, 클라우드로 확장할 때도
> **NVIDIA가 만들어둔 이미지를 그대로** 쓰면 된다.
> 지금 Windows에서 겪은 **함정 6개(Python 버전·torch CPU판·conda·flatdict·tensordict·h5py)를 전부 우회**한다.

**요구사항**: Docker + **NVIDIA Container Toolkit ≥ 1.17.0** + Ubuntu 22.04/24.04

**Docker가 필수는 아니다**: AWS 공식 AMI는 네이티브 설치형이고, VM에 직접 설치도 가능하다.
- 네이티브 장점: 디버깅 단순 / 단점: 환경 재현·팀 공유가 번거로움
- **클라우드에서는 버전 고정·재현성 때문에 컨테이너 경로가 일반적**

---

## 5. 대안 — NVIDIA Brev / Isaac Launchable `확인됨`

**브라우저만으로 VS Code + Isaac Sim/Lab 스트리밍**이 되는 사전 구성 환경. NVIDIA의 현재 공식 클라우드 경로.
- https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_advanced_cloud_setup_launchable.html
- 저장소: https://github.com/isaac-sim/isaac-launchable
- L40S 1장 예시로 문서화됨
- **비용 `미확인`** (배후 클라우드 인스턴스 요금 과금)

> ★ **팀원 노트북(GTX 1650 Ti)에서 브라우저만으로 접근 가능하다면, 이게 가장 현실적인 팀 확장 경로일 수 있다.**

**Omniverse Cloud**: Launcher가 2025-10-01 폐기되고 배포가 GitHub/NGC로 이동 — 단일 "클라우드 제품" 형태는 사실상 소멸 `부분확인`
**Vast.ai / Lambda / Paperspace**: 문서화된 Isaac Sim 성공 사례 못 찾음 `미확인`

---

## 6. ★ 권고

1. **팀원에게 즉시 확인**: RunPod에서 **어떤 GPU를 골랐는지**. A100/H100이면 원인 확정. RTX 계열이었다면 **IsaacLab #2271 UDP 차단** 이슈를 의심하라.
2. **가장 검증된 경로 = AWS `g6e`(L40S) + 공식 AMI 또는 `nvcr.io/nvidia/isaac-lab:2.3.2`.** 우리 버전과 일치하는 공식 이미지가 있어 직접 빌드 불필요. g6e.xlarge 약 **$1.86/hr**.
3. **RunPod을 다시 쓴다면 RTX 4090($0.34) 또는 L40S($0.79)를 선택**하고 isaac-lab 이미지를 파드 템플릿으로 지정. 단 **UDP 가능한 데이터센터인지 먼저 확인**해야 하고, 문서화된 성공 보증이 없다.
4. **설정 부담을 없애려면 NVIDIA Brev의 Isaac Launchable**이 공식 대안이다. 팀원 노트북 사양을 고려하면 검토 가치가 높다.
5. **A100/H100에서 "헤드리스면 되지 않을까"는 공식적으로 부정됐다.** 커뮤니티 부분 성공 사례만 있다. **기반으로 삼지 말 것.**

## 7. 미확인 (판단 근거로 쓰지 말 것)
- RunPod에서 Isaac Sim 성공한 구체 사례(GPU·이미지·설정)
- 5.1에서 A100 헤드리스 동작 여부
- Brev / Isaac Launchable 실제 비용
- AWS g6e 외 사이즈·리전 요금
- Vast.ai · Lambda · Paperspace 사례
- Isaac Sim 5.1의 Vulkan 세부 요구사항

## 변경 이력
- 2026-08-08 v1: RunPod 실패 원인 조사. **RT 코어 요구가 관문임을 공식 문서로 확정.**
  **★ `nvcr.io/nvidia/isaac-lab:2.3.2` 공식 이미지 발견 — 우리 버전과 정확히 일치.**
