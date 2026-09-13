# 팀 공통 개발환경 구축 가이드

> **대상**: 팀원 5인 전원. RL·Isaac Sim 경험이 없어도 그대로 따라 하면 됩니다.
> **목표**: NVIDIA가 배포하는 **사전학습 Go2 험지 보행 정책을 각자 PC에서 재생**하는 데까지.
> **검증**: 2026-07-29, 팀 워크스테이션(AI-WS01)에서 **실제로 끝까지 돌려 성공한 절차**입니다. 추측이나 문서 인용이 아닙니다.
### 이 문서의 위치: 관련 문서 3종의 역할 분담

| 문서 | 질문 | 읽는 사람 |
|---|---|---|
| `01_research/mvp-report-readable.md` | **"무슨 일이 있었나"**. 결과 보고 | 팀 전원·멘토 |
| **이 문서 (`SETUP_GUIDE.md`)** | **"내 PC에서 어떻게 따라 하나"**. 실행 절차 | **환경을 설치할 사람** |
| `01_research/mvp-install-log.md` | "정확히 어떤 숫자가 나왔나". 원본 실측 로그 | 검증·재현할 사람 |

> ⚠️ **버전·수치가 바뀌면 세 문서를 함께 고칠 것.** 특히 §1 버전표와 §5 함정 목록은 `mvp-report-readable.md` §5·§6과 같은 사실을 다룹니다.
> **웹페이지(foothold-project.vercel.app)에 올릴 원문은 이 문서입니다.**

---

## 0. 세 줄 요약

1. **우분투 설치 필요 없습니다.** Windows에서 그대로 됩니다.
2. **전체 약 1시간, 디스크 16GB** (회선 89Mbps 기준). "수십 GB" 아닙니다.
3. **함정이 6개 있습니다.** 전부 *"설치는 성공했다고 뜨는데 나중에 터지는"* 종류라, **§4의 검증 체크리스트를 각 단계마다 반드시 실행**하세요.

---

## 1. 확정 버전: 이 조합만 씁니다

**한 명이라도 다른 버전을 쓰면 팀 결과가 갈라집니다.** 프로젝트 종료까지 업그레이드하지 않습니다.

| 항목 | 버전 | 왜 이 버전인가 |
|---|---|---|
| OS | Windows 10/11 | Isaac Sim 5.1 공식 지원 대상 |
| **Python** | **3.11** | ★ Isaac Sim 5.1 wheel이 `cp311` 전용. **3.10·3.12·3.13 전부 안 됨** |
| NVIDIA 드라이버 | **570 이상** (검증 환경 591.86) | RTX 50 시리즈(Blackwell, `sm_120`) 요구치.<br>RTX 40/30 은 더 낮아도 될 수 있으나 **미확인**: §1.5 |
| **PyTorch** | **2.7.0 + cu128** | ★ 기본 wheel은 **CPU 전용**. cu128을 강제해야 GPU가 잡힘 |
| **Isaac Sim** | **5.1.0.0** (pip) | Isaac Lab 2.3.x가 요구하는 짝 |
| **Isaac Lab** | **`v2.3.2` 태그 고정** | ★ **v2.3.2가 최신 안정판입니다.** 그 위는 전부 베타: §1.1 |
| 물리 백엔드 | **PhysX** | Newton 지원 태스크 목록에 **우리가 쓰는 Rough 태스크가 없음**. §1.1 |
| rsl_rl | **3.1.2** | Isaac Lab v2.3.2가 핀으로 고정 |

### 🚫 쓰면 안 되는 것

| 금지 | 이유 |
|---|---|
| `git clone` 후 그냥 쓰기 | **기본 브랜치가 베타**입니다. 반드시 `--branch v2.3.2` |
| Newton 백엔드 / `develop` / `3.0.0-beta*` | **우리 태스크(Rough)가 지원 목록에 없음** (NVIDIA 공식 문서): §1.1 |
| `legged_gym`, Isaac Gym Preview 4 | Blackwell(`sm_120`) 커널 없음 → RTX 50에서 아예 안 돎 |
| `unitree_rl_gym` | **지형 생성 함수가 통째로 삭제된 fork**입니다. 설정만 남아 있어 "바꿨는데 반영 안 됨" 사고가 납니다 |
| `pip install torch` (그냥) | **CPU 전용이 깔립니다** |

---

## 1.1 ★ "왜 최신 버전을 안 쓰나요?": 가장 많이 나오는 질문

> 팀원 질문: *"`--branch v2.3.2`로 고정하던데, 최신을 받으면 학습이 더 진전돼 있는 거 아닌가요?"*

### 먼저, 오해 하나를 풀어야 합니다

**Isaac Lab은 「학습된 결과」가 아니라 「학습시키는 도구」입니다.**
버전이 올라간다고 로봇이 더 잘 걷지 않습니다. 걷게 만드는 건 **우리가 돌리는 학습**입니다.

오히려 반대입니다. 우리가 첫날부터 걷는 로봇을 볼 수 있었던 건
NVIDIA가 배포한 **사전학습 체크포인트** 덕분인데, 그건 `Isaac/5.1/.../Isaac-Velocity-Rough-Unitree-Go2-v0/` 경로로
**Isaac Sim 5.1 · Isaac Lab 2.3.x 짝에 맞춰** 올라와 있습니다.
버전을 올리면 **그 자산이 안 맞게 됩니다.**

### 그리고, "최신"이라는 게 안정판이 아닙니다 (2026-08-05 확인)

| 태그 | 날짜 | 상태 |
|---|---|---|
| `v3.0.0-beta2.patch1` | 2026-07-02 | 🔴 베타 |
| `v3.0.0-beta2` | 2026-06-17 | 🔴 베타 |
| `v3.0.0-beta` | 2026-03-17 | 🔴 베타 |
| **`v2.3.2`** | **2026-02-02** | ✅ **최신 안정판 = 우리가 쓰는 것** |

**v2.3.2 위로는 정식 릴리스가 하나도 없습니다.** 기본 브랜치조차 `release/3.0.0-beta2`(베타)입니다.
그래서 `git clone`만 하면 **베타를 받게 됩니다.**

### 3.0을 받으면 실제로 무슨 일이 나는가: 전부 NVIDIA 공식 문구

| # | 무슨 일 | 근거 (원문) |
|---|---|---|
| ① | **Windows에서 아예 안 됩니다** | v3.0.0-beta Known Limitations: *"**Ubuntu only**: The develop branch is currently available on Ubuntu. Windows support .. will be available soon."* |
| ② | **Isaac Sim부터 다시 깔아야 합니다** | 3.0은 **Isaac Sim 6.0** 기반. 우리가 깐 건 **5.1**입니다 |
| ③ | **Python·PyTorch가 다릅니다** | 3.0 = Python **3.12** / PyTorch **2.10.0**. 우리 = 3.11 / 2.7.0+cu128 |
| ④ | **명령어가 통째로 깨집니다** | beta2 Migration Notes: *"Replace `--headless` usage with `--viz` / `--visualizer`"*. 이 문서의 모든 명령이 못 쓰게 됩니다 |
| ⑤ | **NVIDIA가 직접 경고합니다** | beta2: *"may still receive **breaking changes** before the final Isaac Lab 3.0 release"* |
| ⑥ | **Newton 백엔드에 우리 태스크가 없습니다** | 아래 참조 |
| ⑦ | `unitree_rl_lab`(실기 배포 코드)이 **2.3.x를 요구**합니다 | 나중에 실물에 올릴 때 막힙니다 |

### ⑥번이 결정적입니다. 이름으로 확인 가능합니다

Newton 통합 문서(`docs/source/experimental-features/newton-physics-integration/`)의 **지원 태스크 목록**:

```
Isaac-Velocity-Flat-Unitree-Go2-v0      ← 평지. 목록에 있음
Isaac-Velocity-Rough-Unitree-Go2-v0     ← 험지. 목록에 없음  ★ 우리가 쓰는 것
```

같은 문서 원문:
> *"Many features are not yet supported, and only a limited set of classic RL and **flat terrain** locomotion reinforcement learning examples are included at the moment."*
> *"you are likely to encounter **breaking changes** ... We do not expect to be able to provide support or debugging assistance until the framework has reached an official release."*

**우리 프로젝트 주제가 「험지」입니다.** 험지가 없는 백엔드로는 할 게 없습니다.
그리고 3.0 릴리스 노트는 **material randomization(마찰 랜덤화)이 PhysX 전용**이라고 명시합니다
그건 우리의 **도메인 랜덤화 핵심 기법**입니다.

### 결론

**v2.3.2 고정은 보수적인 선택이 아니라, 지금 유일하게 굴러가는 조합입니다.**
프로젝트 종료(11월)까지 올리지 않습니다. 3.0 정식판이 나와도 **그때 검토 대상이지 즉시 적용 대상이 아닙니다.**

> 📌 확인 경로: 직접 보고 싶으면:
> [릴리스 목록](https://github.com/isaac-sim/IsaacLab/releases) ·
> [v2.3.2 태그](https://github.com/isaac-sim/IsaacLab/releases/tag/v2.3.2) ·
> [Newton 지원 태스크 목록](https://github.com/isaac-sim/IsaacLab/blob/v2.3.2/docs/source/experimental-features/newton-physics-integration/training-environments.rst)

---

## 1.5 ★ 내 PC는 어떤가: 팀원마다 다릅니다

> **이 가이드의 검증 환경은 RTX 5080 ×2 입니다. 여러분 PC는 다릅니다.**
> 특히 **§4 체크리스트 3번(`sm_120`)은 RTX 50 시리즈에만 해당**합니다. 그대로 읽으면 멀쩡한 PC가 "실패"로 나옵니다.

### GPU 세대별 아키텍처 코드

| GPU 세대 | 코드명 | arch 코드 |
|---|---|---|
| RTX 50 | Blackwell | `sm_120` ← **검증 환경** |
| RTX 40 | Ada Lovelace | `sm_89` |
| RTX 30 | Ampere | `sm_86` |
| RTX 20 | Turing | `sm_75` |

**§4 체크리스트 3번은 이렇게 읽으세요:**

- ✗ "`sm_120`이 있어야 한다"
- ✅ **"내 GPU의 코드가 목록에 있어야 한다"**

```powershell
# 내 GPU 이름과 arch 목록을 같이 확인
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python -c "import torch; print(torch.cuda.get_device_name(0)); print(torch.cuda.get_arch_list())"
```

### 🔴 Isaac Sim 공식 요구사양: 생각보다 높습니다

| 등급 | GPU | VRAM |
|---|---|---|
| **최소** | **GeForce RTX 4080** | **16 GB** |
| 권장 | GeForce RTX 5080 | 16 GB |
| 이상적 | RTX PRO 6000 Blackwell | 48 GB |
| **미지원** | **RT 코어가 없는 GPU**: GTX 전 계열, A100·H100 포함 | - |

출처: [Isaac Sim 공식 요구사양](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html)
**AI-WS01의 RTX 5080이 정확히 "권장" 등급**입니다.

> ⚠️ **이 문턱은 팀원 대부분이 못 넘습니다.** RTX 3060·4060 급도 **공식 최소 미달**입니다.
> 그래서 **워크스테이션 공유는 선택이 아니라 기본 전제**입니다.

### 내 PC로 어디까지 되나

| 내 환경 | Isaac Sim | 비고 |
|---|---|---|
| **RTX 5080 (AI-WS01)** | **전부 가능** | 실증 완료 · 공식 "권장" 등급 |
| RTX 4080 이상 · 16 GB | 가능 | 공식 최소 충족 |
| RTX 30/40 · VRAM 16 GB 미만 | **공식 최소 미달** | 돌 수도 있으나 **보장 없음** |
| **GTX 계열** (예: GTX 1650 Ti) | **원천적으로 불가** | **RT 코어가 없습니다.** 드라이버·VRAM 문제가 아니라 하드웨어에 그 기능이 없음 |
| GPU 없음 · 내장 그래픽 · 맥 | **불가** | - |

### ★ 그래서 노트북으로는 무엇을 하나. 생각보다 많습니다

Isaac Sim이 안 돌아도 **학습 커리큘럼 A트랙 17절 중 대부분**은 노트북에서 그대로 진행됩니다.
특히 **실습이 있는 A6·A7이 가능**합니다.

| 절 | 노트북 | 왜 |
|---|---|---|
| A1~A5 · A8 · A11 · A12 · A14~A17 | **가능** | 개념 · 설계 · 표 만들기 |
| **A6 MuJoCo에서 Go2 세우기** | **가능** | **MuJoCo는 CPU 물리 엔진**입니다. RT 코어도 큰 VRAM도 필요 없습니다 |
| **A7 규칙으로 걷게 해보고 실패하기** | **가능** | MuJoCo 위에서 합니다. **이 프로젝트에서 물리 감각을 얻는 유일한 절** |
| A13 코드 읽기 | **가능** | 읽고 고치는 데 GPU가 필요 없습니다 |
| A9 첫 학습 · A10 보상 실험 | **워크스테이션 원격** | GPU 2장이라 동시 2인 (⚠️ "2장 묶어 2배"는 아님: §8) |

**노트북 담당자에게**: **A6·A7을 먼저 하세요.**
선행 사례는 이 단계를 건너뛰고 바로 강화학습으로 가서 "발을 왜 안 떼는지"를
물리적 직관 없이 **석 달을 헤맸습니다**. 노트북에서 할 수 있는 이 두 절이
**팀 전체의 진단 속도를 좌우합니다.**

> **미래 방향**: AI-WS01에 **리눅스 멀티부트**를 구성해 팀원이 원격으로 붙는 안을 검토 중입니다.
> 리눅스가 Isaac Sim·Isaac Lab의 1차 지원 플랫폼이고, 다중 사용자 접속도 훨씬 수월합니다.
> ⚠️ 아직 구성 안 함. 결정되면 이 문서에 절차를 추가합니다.

---

## 2. 사전 준비

```powershell
# 1) GPU·드라이버 확인: 570 이상이어야 함
nvidia-smi

# 2) 디스크 여유 20GB 이상 확인
Get-Volume -DriveLetter C

# 3) git 설치 여부
git --version
```

**Anaconda 또는 Miniconda가 필요합니다.** 없으면 Miniconda를 먼저 설치하세요.
※ 관리자 권한은 **필요 없습니다.** 전부 사용자 폴더에 설치됩니다.

---

## 3. 설치 절차 (복붙용)

### STEP 1: Python 3.11 전용 환경 만들기

```powershell
conda create -n isaac311 python=3.11 -y
conda activate isaac311
python --version          # → Python 3.11.x 여야 함
```

> ⚠️ **`conda activate`를 반드시 하세요.** 뒤에 나올 `isaaclab.bat`이 `%CONDA_PREFIX%`로 파이썬을 찾습니다. PATH만 건드리면 **베이스 환경에 잘못 설치**됩니다(함정 ③).

### STEP 2: PyTorch를 **cu128로** 설치 (★ 순서 중요)

```powershell
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 `
    --index-url https://download.pytorch.org/whl/cu128
```

> **왜 먼저 하나**: Isaac Sim이 `torch==2.7.0`을 요구하는데, 그냥 두면 PyPI 기본 wheel(**CPU 전용**)이 깔립니다.
> 먼저 cu128을 깔아두면 `2.7.0+cu128`이 `==2.7.0` 조건을 만족해서 **덮어쓰이지 않습니다.** (실측 확인)

### STEP 3: Isaac Sim 설치

```powershell
pip install "isaacsim[all]==5.1.0.0" --extra-index-url https://pypi.nvidia.com
```
소요 약 4분.

### STEP 4: 첫 실행 (Kit 런타임 자동 수신)

```powershell
$env:OMNI_KIT_ACCEPT_EULA="YES"
python -c "from isaacsim import SimulationApp; app=SimulationApp({'headless':True}); print('OK'); app.close()"
```

> ⏱ **첫 실행만 6~7분 걸립니다.** Kit 런타임 약 5GB를 자동으로 받고 초기화합니다(초기화만 385초).
> 두 번째부터는 20초 내외입니다. **멈춘 게 아니니 기다리세요.**

### STEP 5: Isaac Lab **태그 고정** clone

```powershell
mkdir C:\isaac -Force
cd C:\isaac
git clone --branch v2.3.2 --depth 1 https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab
git describe --tags       # → v2.3.2 여야 함
```

> 경로를 **짧게(`C:\isaac`)** 두세요. Isaac Lab은 경로가 깊어서 Windows 260자 제한에 걸릴 수 있습니다.

### STEP 6: 빌드 도구 문제 선처리

```powershell
pip install "setuptools<81" wheel
pip install "flatdict==4.0.1" --no-build-isolation
```

> 최신 setuptools(83+)에서 `pkg_resources`가 빠졌는데 `flatdict`가 그걸 씁니다(함정 ④).

### STEP 7: Isaac Lab 설치

```powershell
conda activate isaac311       # ★ 다시 한 번 확인
cd C:\isaac\IsaacLab
.\isaaclab.bat --install rsl_rl
pip install -e source/isaaclab
pip install "packaging==23.0"   # isaacsim이 요구하는 핀으로 복구
```

> `rsl_rl`만 설치합니다. 우리 프로젝트는 다른 RL 프레임워크(rl_games·skrl·sb3)를 쓰지 않습니다.

### STEP 8: Windows 우회 스크립트 만들기 (★ 필수)

**재생용** `C:\isaac\IsaacLab\play_go2_win.py` 파일을 만들고 아래를 넣으세요.

```python
# Windows 우회: Isaac Sim Kit 로드 전에 "네이티브 확장을 가진" 패키지를 선점 import
#   - tensordict : access violation 0xC0000005 (헤드리스에서도 발생)
#   - h5py       : entrypoint not found 0xC0000139 (GUI 모드에서 발생)
import torch                       # noqa
from tensordict import TensorDict  # noqa
import rsl_rl.runners              # noqa
import h5py                        # noqa
import runpy, sys, os
SCRIPT = os.path.join("scripts", "reinforcement_learning", "rsl_rl", "play.py")
sys.path.insert(0, os.path.dirname(os.path.abspath(SCRIPT)))   # cli_args 를 찾게
sys.argv = [SCRIPT] + sys.argv[1:]
runpy.run_path(SCRIPT, run_name="__main__")
```

**학습용** `C:\isaac\IsaacLab\train_go2_win.py` 도 같이 만듭니다.
**위와 완전히 같고 `SCRIPT` 한 줄만 `train.py` 로 바꿉니다.**

```python
# Windows 우회: Isaac Sim Kit 로드 전에 "네이티브 확장을 가진" 패키지를 선점 import
#   - tensordict : access violation 0xC0000005 (헤드리스에서도 발생)
#   - h5py       : entrypoint not found 0xC0000139 (GUI 모드에서 발생)
import torch                       # noqa
from tensordict import TensorDict  # noqa
import rsl_rl.runners              # noqa
import h5py                        # noqa
import runpy, sys, os
SCRIPT = os.path.join("scripts", "reinforcement_learning", "rsl_rl", "train.py")
sys.path.insert(0, os.path.dirname(os.path.abspath(SCRIPT)))   # cli_args 를 찾게
sys.argv = [SCRIPT] + sys.argv[1:]
runpy.run_path(SCRIPT, run_name="__main__")
```

### STEP 9: 최종 실행

```powershell
conda activate isaac311
cd C:\isaac\IsaacLab
$env:OMNI_KIT_ACCEPT_EULA="YES"

python play_go2_win.py --task Isaac-Velocity-Rough-Unitree-Go2-Play-v0 `
    --num_envs 32 --use_pretrained_checkpoint --headless --video --video_length 200
```

**성공하면 아래 4개가 생깁니다:**
```
C:\isaac\IsaacLab\.pretrained_checkpoints\rsl_rl\Isaac-Velocity-Rough-Unitree-Go2-v0\
  ├─ checkpoint.pt                     6.56 MB   ← NVIDIA 사전학습 정책
  ├─ exported\policy.onnx              1.10 MB   ← 실물 배포용 포맷
  ├─ exported\policy.pt                1.11 MB
  └─ videos\play\rl-video-step-0.mp4   0.51 MB   ← 재생 영상
```

**여기까지 되면 환경 구축 완료입니다.**

---

## 4. ★ 검증 체크리스트: 각 단계마다 확인하세요

> **"설치 성공 메시지"는 결과가 아닙니다.** 아래를 직접 돌려서 눈으로 확인하세요.

| # | 확인 명령 | 기대 결과 |
|---|---|---|
| 1 | `python --version` | `Python 3.11.x` |
| 2 | `python -c "import torch; print(torch.__version__, torch.version.cuda)"` | `2.7.0+cu128 12.8` |
| 3 | `python -c "import torch; print(torch.cuda.get_arch_list())"` | 목록에 **내 GPU의 arch 코드** 포함<br>RTX 50 → `sm_120` · RTX 40 → `sm_89` · RTX 30 → `sm_86` (§1.5) |
| 4 | `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"` | `True` + GPU 수 |
| 5 | **실제 연산** (아래 스니펫) | `True` |
| 6 | `git describe --tags` (IsaacLab 폴더) | `v2.3.2` |
| 7 | `pip list \| findstr "isaacsim isaaclab rsl"` | isaacsim 5.1.0.0 / rsl-rl-lib 3.1.2 |
| 8 | STEP 9 실행 | mp4 파일 생성 |

**5번: GPU가 정말 계산하는지 (알려진 답 테스트)**
```powershell
python -c "import torch; d='cuda:0'; I=torch.eye(1024,device=d); x=torch.randn(1024,1024,device=d); print(torch.allclose(I@x, x, atol=1e-5))"
```
→ `True` 가 나와야 합니다. `cuda.is_available()`이 True인 것만으로는 부족합니다.

---

## 5. 🔴 함정 6개와 해법

전부 **"성공한 것처럼 보이다가 나중에 터지는"** 종류입니다. 검증 환경에서 실제로 다 겪었습니다.

### ★ 먼저 일반 규칙: 개별 사례보다 이게 중요합니다

> **함정 ⑤·⑥은 같은 부류입니다.**
> **Isaac Sim Kit은 자기 네이티브 DLL을 먼저 올립니다.**
> **네이티브 확장을 가진 파이썬 패키지를 Kit보다 나중에 import하면 충돌합니다.**
>
> | 패키지 | 증상 | 언제 |
> |---|---|---|
> | `tensordict` | access violation `0xC0000005` | 헤드리스에서도 |
> | `h5py` | entrypoint not found `0xC0000139` | GUI 모드에서 |
>
> **앞으로 새 패키지를 추가할 때마다 같은 증상이 날 수 있고, 해법은 항상 「선점 import」입니다.**
> 새 패키지를 넣었는데 알 수 없는 `0xC000....` 로 죽으면, 먼저 이걸 의심하세요.

### ① Isaac Sim 5.1은 Python 3.11 전용
- **증상**: `No matching distribution found for isaacsim`
- **원인**: wheel 태그가 `cp311`. 3.10/3.12/3.13 모두 불가
- **해법**: `conda create -n isaac311 python=3.11`
- ※ Isaac Sim 6.0.x는 `cp312`지만, 우리는 v2.3.2 정책상 **5.1을 씁니다**

### ② ★ `torch 2.7.0` 기본 wheel은 CPU 전용
- **증상**: 설치는 성공. 그런데
  ```
  torch: 2.7.0+cpu / CUDA build: None / arch list: [] / cuda avail: False
  ```
- **왜 위험한가**: 설치 단계에서 아무 에러도 안 납니다. **학습을 돌려서야 GPU를 못 쓴다는 걸 발견**합니다
- **해법**: STEP 2 (cu128 인덱스 강제) → `2.7.0+cu128`, arch list에 `sm_120` 포함

### ③ `isaaclab.bat`은 `%CONDA_PREFIX%`로 파이썬을 찾음
- **증상**: `ERROR: Unknown compiler(s): [['icl'], ['cl'], ['gcc'], ...]`
- **함정**: C 컴파일러가 진짜 원인이 **아닙니다.** conda 환경이 활성화 안 돼 **베이스 파이썬(3.13)**이 쓰였고, `numpy<2`에 cp313 wheel이 없어 소스 빌드로 떨어진 것입니다
- **해법**: `conda activate isaac311`을 **실제로** 실행. PATH 조작만으로는 안 됩니다
- **부작용 확인**: 이미 당했다면 베이스 환경 정리
  ```powershell
  # 베이스에서 실행
  pip uninstall -y isaaclab isaaclab_assets isaaclab_contrib isaaclab_mimic isaaclab_rl isaaclab_tasks
  ```

### ④ `flatdict==4.0.1` 빌드 실패
- **증상**: `ModuleNotFoundError: No module named 'pkg_resources'`
- **해법**: STEP 6
- **후처리**: `packaging`이 26.x로 올라가 isaacsim 핀(23.0)을 깨뜨리므로 `pip install "packaging==23.0"`으로 복구

### ⑤ ★★ Windows에서 `rsl_rl`을 Isaac Sim 뒤에 import하면 크래시
- **증상**: `Windows fatal exception: access violation` (exit code `-1073741819` = `0xC0000005`)
- **크래시 지점**: `rsl_rl/runners/on_policy_runner.py` **line 14** = `from tensordict import TensorDict`
- **왜 찾기 어려운가**: 각 모듈을 **단독으로 import하면 전부 정상**입니다. Isaac Sim Kit이 먼저 로드된 상태에서만 죽습니다
- **해법**: STEP 8의 래퍼 스크립트: `tensordict`/`rsl_rl`을 `AppLauncher`보다 **먼저** import
- ⚠️ **미확인**: 이 크래시가 Windows 전용인지 Linux/WSL에서도 나는지는 확인하지 않았습니다

### ⑥ ★★ GUI 모드에서 `h5py` DLL 로드 실패
- **증상**: GUI로 띄우면 **67초 만에 죽음**
  ```
  ImportError: DLL load failed while importing _errors   (h5py)
  Windows fatal exception: code 0xc0000139               ← 엔트리포인트 불일치
  ```
- **함정**: **`h5py`를 단독 import하면 정상입니다** (`OK 3.16.0`). **Kit이 먼저 로드된 상태에서만** 죽습니다
- **헤드리스에서는 안 나타납니다.** GUI가 확장을 더 올리면서 터집니다
- **해법**: 함정 ⑤와 동일: **선점 import** (STEP 8 래퍼에 `import h5py` 한 줄)

**공통 팁**
- Isaac Sim은 **stdout을 가로챕니다.** 스크립트의 `print()`가 안 보이면 죽은 게 아닙니다. **결과는 파일로 쓰세요**
- 실행 중 `omni.hydra` 메시 primvar 경고가 많이 뜨는데 **정상 동작에 지장 없습니다**

---

## 6. 우리가 어디서 무엇을 가져왔나 (출처)

| 대상 | 출처 | 비고 |
|---|---|---|
| **Isaac Sim 5.1.0.0** | `https://pypi.nvidia.com` (NVIDIA 공식 pip 인덱스) | wheel 태그 `cp311` |
| **Kit 런타임 ~5GB** | `d4i3qtqj3r0z5.cloudfront.net` (첫 실행 시 자동) | `%LOCALAPPDATA%\ov\` 에 캐시 |
| **Isaac Lab v2.3.2** | `github.com/isaac-sim/IsaacLab` · 커밋 `37ddf626871758333d6ed89cf64ad702aef127d0` | ★ 태그 고정 필수 |
| **rsl_rl 3.1.2** | PyPI (`rsl-rl-lib`), Isaac Lab이 핀 고정 | ETH RSL 학습 라이브러리 |
| **PyTorch cu128** | `download.pytorch.org/whl/cu128` | 기본 PyPI 아님 |
| **사전학습 Go2 체크포인트** | `omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/IsaacLab/PretrainedCheckpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt` | 6.56MB, `--use_pretrained_checkpoint`로 자동 수신 |

**사용 가능한 Go2 태스크 4개** (설치 후 확인됨)
```
Isaac-Velocity-Flat-Unitree-Go2-v0        평지 학습용
Isaac-Velocity-Flat-Unitree-Go2-Play-v0   평지 재생용
Isaac-Velocity-Rough-Unitree-Go2-v0       험지 학습용   ← 우리 베이스라인
Isaac-Velocity-Rough-Unitree-Go2-Play-v0  험지 재생용
```

**teacher-student 증류 예제도 포함돼 있습니다** (우리 프로젝트의 핵심 구조)
```
source/isaaclab_rl/isaaclab_rl/rsl_rl/distillation_cfg.py
source/isaaclab_tasks/.../config/anymal_d/agents/rsl_rl_distillation_cfg.py
```

---

## 7. 실측 데이터 (검증 환경 AI-WS01)

| 항목 | 값 |
|---|---|
| GPU | RTX 5080 ×2 (각 15,979 MB), 드라이버 591.86 |
| CPU / RAM | Threadripper 7970X (32C/64T) / 256 GB |
| 회선 실측 | **11.1 MB/s (89 Mbps)**: 544MB를 48.9초에 수신 |
| **총 디스크 사용** | **15.77 GB** (pip 캐시 8GB 포함, 캐시는 삭제 가능) |
| 전체 소요 | 약 1시간 (시행착오 포함) |
| Kit 첫 초기화 | 385초: **두 번째부터 ~20초** |
| GPU 실측 성능 | fp32 4096×4096 matmul **36.4 TFLOPS** |

### 학습 성능 (2026-08-05 측정 · 험지 · 4096 envs · RTX 5080 **1장**)

| 항목 | 값 |
|---|---|
| **학습 처리 속도** | **21,248 ~ 21,385 steps/s** |
| **iteration 1회** | **4.4 ~ 4.6초** (수집 4.5s + 학습 0.12s) |
| 30 iteration | 2.53분 (기동 포함) |
| **표준 1,500 iteration** | **실측 133분 (2시간 13분)**: 2026-08-12 완주 |
| ↳ 위 30 iteration 에서 외삽한 예상 | 113분: **실측이 +18% 더 걸렸다** |
| GUI 모드 자원 | 시스템 RAM 13.5 GB · VRAM 약 9 GB (GPU0 4,143 + GPU1 4,807 MiB) |

> **한 번 학습에 약 2시간 15분이 걸립니다**(1,500 iteration 실측 133분).
> 하루 8시간이면 **3~4회** 실험할 수 있습니다.
> 수집(4.5s)이 학습(0.12s)의 **37배**입니다. 병목은 신경망이 아니라 **시뮬레이션**입니다.
> 이 수치는 **험지(Rough)** 기준이고, 평지(Flat)는 훨씬 빠릅니다.

**설치 위치**
```
C:\Users\<사용자>\anaconda3\envs\isaac311\      7.77 GB   파이썬 환경 전체
C:\Users\<사용자>\AppData\Local\ov\             4.75 GB   Kit 런타임 캐시
C:\isaac\IsaacLab\                              0.08 GB   Isaac Lab 소스
C:\Users\<사용자>\AppData\Local\pip\Cache\      (삭제 가능)
```

---

## 8. ⚠️ 팀에 공유할 주의사항 2개

### ① `CUDA peer access: Not supported`
워크스테이션의 두 GPU가 **서로 직접 통신하지 못합니다.**
- ✅ **"GPU 2장 = 동시에 두 명이 각자 학습"**: 유효합니다 (`--device cuda:0` / `cuda:1`)
- ❌ **"GPU 2장을 묶어 하나의 학습을 가속"**: **측정 완료. Windows 에서는 구조적으로 불가합니다**
  ```
  torch.distributed.is_nccl_available()  →  False
  ```
  NCCL 은 GPU 끼리 직접 데이터를 주고받는 라이브러리이고 DDP 학습에 필수인데,
  **PyTorch Windows 빌드에는 들어가지 않습니다.** gloo 는 CPU 경유라 대체가 안 됩니다.
  → **우분투로 전환한 뒤에 다시 측정**합니다 (2026-08-11 판정)
→ 대외 자료에 *"GPU 2장으로 학습을 2배 빠르게"*라고 쓰지 마세요. *"동시 2인 실험"*이 정확한 표현입니다.

### ② `policy.onnx`가 자동 생성됩니다
재생만 해도 **ONNX 익스포트가 함께 나옵니다**(1.1MB).
Unitree 공식 실물 배포 경로가 ONNX이므로, **sim2real의 첫 단추가 이미 준비돼 있다**는 뜻입니다.

---

## 9. 아직 검증 안 된 것 (정직하게)

| 항목 | 상태 |
|---|---|
| **험지 속도 우회 플래그** | `--kit_args="--/physics/collisionApproximateCylinders=true"` 효과 **여전히 미측정** |
| **teacher-student 증류 실제 실행** | 예제 파일 존재만 확인. 안 돌려봄 |
| **WSL2 / 네이티브 우분투** | 시험 안 함. Windows로 성공했으므로 급하지 않음 |
| **함정 ⑤·⑥이 Linux에서도 나는지** | 미확인 |

> ✅ **해소됨 (2026-08-05)**: 「학습 실행 속도 미측정」과 「GUI 실행 미확인」은 이번 2차 실증으로 측정됐습니다. §7 참조.

---

## 10. 각자 설치 후 보고할 것

팀 채널에 아래를 붙여넣어 주세요. **전원이 같은 환경인지 확인하는 용도**입니다.

```powershell
conda activate isaac311
python -c "import torch,sys; print('py',sys.version.split()[0]); print('torch',torch.__version__,torch.version.cuda); print('sm_120', 'sm_120' in torch.cuda.get_arch_list()); print('gpu',torch.cuda.device_count())"
cd C:\isaac\IsaacLab; git describe --tags
```

**기대 출력**
```
py 3.11.x
torch 2.7.0+cu128 12.8
sm_120 True
gpu <각자 GPU 수>
v2.3.2
```

하나라도 다르면 **§5 함정 목록**을 확인하세요.

---

## 변경 이력
- 2026-08-05 v1: 2026-07-29 AI-WS01 실증 결과를 팀 배포용으로 재구성. 원본 로그 = [[mvp-install-log]]
