# MoE-CTS (go2_rl_robotlab) 연기 시험 기록

> 분류: 실행 기록 (환경 준비 · 연기 시험)
> 작성: 오흥재 · 2026-10-10 (하위 세션 실행 기록)
> 근거: 이 폴더의 로그 01~09 · `C:/isaac/ext/go2_rl_robotlab/_smoke/` 로그 10~17 · 실험 카드 `foothold-lab/inbox/jay/20261008-546-design/EXP-weekend-moects.md` · `SURVEY-star-code.md` 3절
> 요지: 한글 경로에서는 URDF importer 가 Go2 URDF 를 못 읽어 막혔다(1~6절). lead 결정 「가」로 `C:/isaac/ext/go2_rl_robotlab` 에 다시 두고 30 iter 연기 시험을 했다(7절). 16384 env 는 돌지만 VRAM 을 넘쳐 96 s/iter, **8192 env 는 4.60 s/iter 로 통과.** 40시간이면 약 31,000 iter
> 상태: 연기 시험 통과 (8192 env) · 본 학습은 걸지 않음

## 1. 결과 한눈에

| 항목 | 값 |
|---|---|
| env | `isaac311-moects` (`C:/Users/AI-WS01/anaconda3/envs/isaac311-moects`), `conda create --clone isaac311` |
| 저장소 | `wertyuilife2/go2_rl_robotlab` @ `28b4516d22617b11aeaf8ead63cc00b0c0bcd1bd` (원격 main 최신과 같음, 다르지 않음) |
| 연기 시험 | (한글 경로) **미통과.** run1 은 EULA 질문에서, run2 는 URDF 로드 실패로 죽음. ASCII 경로에서의 통과 결과는 7절 |
| iter 당 시간 | 미확인 (iteration 0 도달 전 종료) |
| GPU 메모리 (16384 env) | 미확인. run2 는 15초 만에 죽었고 그동안 GPU 0 최대 757 MiB |
| isaac311 | 안 바뀜 (`conda-meta/history` 7/29 그대로 · rsl_rl_lib 3.1.2 · wrapt 1.16.0 · click 8.1.7 · protobuf 7.35.1 dist-info 그대로) |
| GPU 1 · pid 25916 | 안 건드림. 끝난 뒤에도 살아 있음. run2 동안 2초 간격 표본에서 GPU 1 은 6,966 ~ 6,974 MiB 로 변화 없음 (GPU 0 만 210 → 757 MiB). 이 세션이 띄운 프로세스는 남은 것 없음 |

## 2. 환경 준비

### 2.1 디스크 (clone 전 측정)

| 드라이브 | 여유 |
|---|---|
| C: | 792.1 GB |
| D: 37.0 GB · E: 923.2 GB · G: 679.7 GB · H: 7.4 GB · I: 155.0 GB · N: 12,304 GB | |

isaac311 측정 크기 14.7 GB (89,541 파일). C: 여유가 충분해 clone 가능으로 판단했다.

### 2.2 clone (`01-conda-clone.log`)

- 11:31:09 ~ 11:37:27, 종료 코드 0. conda 표기 `Packages: 20 · Files: 138630`.
- 새 env 측정 크기 **24.85 GB (144,824 파일)**. 원본보다 큰 까닭: isaac311 의 `Lib/site-packages/isaacsim/kit/data/Kit/Isaac-Sim/5.1/exts/3/` 아래 항목 **479개가 junction** (`%LOCALAPPDATA%/ov/data/exts/v2/...` 를 가리킴)이고, conda 가 그 내용을 실제 폴더로 복사했다. 새 env 는 자기 kit data 를 따로 가진다.
- isaaclab 계열(isaaclab 0.54.2 · isaaclab_rl 0.4.7 · isaaclab_tasks 0.11.12 등)은 isaac311 과 마찬가지로 **`C:/isaac/IsaacLab` 소스 editable** 이다. 두 env 가 같은 Isaac Lab 소스를 본다(이 세션은 그 소스를 고치지 않았다).

### 2.3 README 설치 절차와 실제

| README | 실제 |
|---|---|
| 1단계 `conda create python=3.11` + `pip install isaaclab[isaacsim,all]==2.3.2.post1` + torch 2.7.0 / torchvision 0.22.0 cu128 | **clone 으로 대신함.** 물려받은 판: Python 3.11.15 · isaacsim 5.1.0.0 · Isaac Lab 로컬 소스 tag v2.3.2 (pip `2.3.2.post1` 과 같은 소스인지 미확인) · torch 2.7.0+cu128 · torchvision 0.22.0+cu128 · numpy 1.26.0 · tensordict 0.13.0 · h5py 3.14.0 · gymnasium 1.2.1 |
| 2단계 `python -m pip install -e source/robot_lab` | 실행함. 종료 코드 0 (`04-pip-install.log`) |
| 2단계 `python -m pip install -e source/rsl_rl` | 실행함. 종료 코드 0. rsl-rl-lib 3.1.2 → **3.3.0 editable** |
| 3단계 mujoco · pygame (선택) | 안 함 (sim2sim 용) |

먼저 `--dry-run` 으로 확인했다 (`02-pip-dryrun.log`). torch · numpy 는 바뀌지 않는다.

**설치 전후 freeze 차이** (`05-freeze-diff.txt`, 정확히 이것뿐):

| 패키지 | 전 | 후 | 비고 |
|---|---|---|---|
| rsl-rl-lib | 3.1.2 | 3.3.0 (editable, `source/rsl_rl`) | |
| robot_lab | 없음 | 2.3.0 (editable, `source/robot_lab`) | |
| wrapt | 1.16.0 | 2.5.0 | isaacsim-kernel 이 `wrapt==1.16.0` 고정 |
| click | 8.1.7 | 8.5.0 | isaacsim-kernel 이 `click==8.1.7` 고정 |
| protobuf | 7.35.1 | 6.33.6 | 내려감 |
| tqdm | 4.70.0 | 4.67.3 | 내려감 |

이 밖에 robot_lab 의 `install_requires` (`cusrl[all]` · `pinocchio` · `xacrodoc` · `pandas`)가 새 패키지 40여 개를 깔았다 (cusrl 1.2.2 · pandas 3.0.6 · onnxruntime 1.31.0 · wandb 0.30.0 · swanlab 0.10.2 등, 목록은 `04-pip-install.log`). 저장소 코드 어디에도 pinocchio · cusrl · xacrodoc · pandas import 는 없다. PyPI 의 `pinocchio-0.4.3` 은 판 번호로 보아 로봇 동역학 Pinocchio(PyPI 이름 `pin`)가 아닌 것으로 보인다 (미확인).

**pip check** (`03-pipcheck-before.txt` · `05-pipcheck-after.txt`):
- 설치 전부터 있던 것 4건 (isaac311 에서 물려받음): isaacsim-kernel 의 psutil · typing_extensions 고정, fastapi 의 starlette, wheel 의 packaging.
- 설치로 생긴 것 3건: isaacsim-kernel 의 wrapt · click 고정, aiobotocore 의 `wrapt<2`.
- 이것이 실행을 막는지는 미확인 (run2 는 Kit 기동 · 설정 파싱 · 장면 생성 시작까지 갔다).

import 확인: `rsl_rl` 3.3.0 이 저장소 `source/rsl_rl` 에서 로드되고 `OnPolicyRunnerCTS` · `ActorCriticMoECTS` · `MoECTS` import 가 된다. `CUDA_VISIBLE_DEVICES=0` 에서 torch 가 보는 장치는 1개, RTX 5080 (12, 0).

## 3. 연기 시험

### 3.1 걸기 전 선언 (`06-smoke-declare.txt`)

- cwd `_smoke/` (train.py 는 cwd 기준 `logs/rsl_rl/<experiment_name>` 에 쓴다)
- `CUDA_VISIBLE_DEVICES=0 python ../scripts/rsl_rl/train.py --task=RobotLab-Go2-v0 --headless --max_iterations 10 --run_name smoke10`
- 저장소 기본값에서 바꾼 것: `max_iterations` 300000 → 10 하나. num_envs 16384 · 시드 42 · device cuda:0 · logger tensorboard 는 기본값.

### 3.2 run1 (`07-smoke-run1.log`) 11:42:04 ~ 11:42:09, 종료 1

```
Do you accept the EULA? (Yes/No): Unable to bootstrap inner kit kernel: EOF when reading a line
```

두 env 모두 `isaacsim/kit/EULA_ACCEPTED` 파일이 없다. foothold-lab 의 기존 스크립트는 전부 `export OMNI_KIT_ACCEPT_EULA=YES` 를 프로세스 범위로 준다 (`_out/loop/diag_rails.sh:22` 등). 같은 방식을 따랐다 (파일 · 영구 환경변수는 만들지 않음).

### 3.3 run2 (`07-smoke-run2.log`) 11:44:54 ~ 11:45:09, 종료 1

`OMNI_KIT_ACCEPT_EULA=YES` 만 더했다. 진행: Kit 기동 → `Using device: cuda:0` → 설정 파싱 (`Go2EnvCfg` · `MoECTSRunnerCfg`) → `Environment seed : 42` → 장면 생성 중 로봇 spawn 에서 죽음.

첫 오류 (원인):
```
[Error] [isaacsim.asset.importer.urdf] *** Failed to load 'C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\ext\go2_rl_robotlab\resources\go2\urdf/go2.urdf'
[Error] [isaacsim.asset.importer.urdf] Failed to parse URDF file 'go2.urdf'
[Warning] [isaacsim.asset.importer.urdf] Cannot add robot to stage, number of links is zero
```

Python 이 보고한 오류 (결과):
```
isaaclab/sim/schemas/schemas.py:571 activate_contact_sensors
ValueError: No contact sensors added to the prim: '/World/envs/env_0/Robot'. This means that no rigid bodies are present under this prim.
```

로봇은 USD 가 아니라 저장소 안 URDF (`resources/go2/urdf/go2.urdf`)를 실행 중에 변환해 쓴다 (`robot_lab/assets/unitree.py:77` · `robot_lab/assets/__init__.py` 의 `ISAACLAB_ASSETS_DATA_DIR`). 그래서 저장소 위치가 곧 URDF 경로다.

### 3.4 원인 가르기: 같은 URDF 를 경로만 바꿔 변환 (`09-diag-urdf-A.log` · `09-diag-urdf-B.log`)

Isaac Lab 표준 도구 `C:/isaac/IsaacLab/scripts/tools/convert_urdf.py --headless` 로 변환만 했다. 같은 env · 같은 환경변수 · 같은 cwd. B 의 입력은 `resources/go2` 를 통째로 복사한 것이고 `cmp` 로 URDF 가 바이트 단위로 같음을 확인했다 (CRLF 그대로).

| | 입력 경로 | URDF importer | 결과 USD |
|---|---|---|---|
| A | `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf` | `Failed to load` · `number of links is zero` | `go2_base.usd` **492 B** (빈 껍데기) |
| B | `C:/Users/AI-WS01/AppData/Local/Temp/moects_diag_1146/go2/urdf/go2.urdf` | 실패 줄 없음 (material 이름의 중국어를 USD 이름으로 바꾼다는 경고만) | `go2_base.usd` **18,808,111 B** |

- 원인 후보 셋 중 둘이 배제됐다: 파일 내용의 비ASCII (중국어 material 이름) · Windows checkout 의 CRLF (`core.autocrlf=true`, 저장소 안은 LF). B 가 같은 바이트로 통과했다.
- 남은 것: **디렉터리 경로의 한글.** 그 안쪽 기전(importer 가 Windows ANSI 코드페이지 경로 API 로 여는지 등)은 미확인.
- 덧붙여 `convert_urdf.py` 는 A 에서도 **종료 코드 0** 이었다. 실패가 조용히 지나간다.

### 3.5 그 밖에 본 것 (실행을 막지는 않음)

- `CUDA_VISIBLE_DEVICES` 를 두면 Kit 가 경고한다: `CUDA device enumeration and Omniverse device enumeration are different` · `Skipping NVIDIA GPU due CUDA being in bad state` (2회) · `Aftermath Error 0xbad00009`. 그래도 Kit 의 Active GPU 는 bus 41 = UUID `c08e23b0` = nvidia-smi 의 **GPU 0** 이었고, run2 동안 GPU 1 메모리는 표본상 변화가 없었다 (`08-gpu-samples-run2.csv`). 메모리에 적힌 「`CUDA_VISIBLE_DEVICES` 로 창 생성에서 멈춤」은 headless 인 이번에는 나오지 않았다 (장면 생성 전까지만 본 것이라 그 뒤는 미확인).
- 연기 시험 부산물: `_smoke/outputs/` (hydra) · `C:/tmp/IsaacLab/usd_20261010_114508_1824/` (Isaac Lab URDF 변환 출력 자리) · `C:/Users/AI-WS01/AppData/Local/Temp/moects_diag_1146/` (진단 사본). 지우지 않았다.

## 4. 결정이 필요한 것

저장소를 ASCII 경로로 옮기지 않으면 이 코드는 이 기계에서 로봇을 만들지 못한다. 지시가 「우회하지 말고 보고」라서 멈췄다. 갈림길:

| 안 | 할 일 | 알려진 것 |
|---|---|---|
| 가. ASCII 경로에 다시 clone | 예: `C:/isaac/ext/go2_rl_robotlab` 에 clone · `28b4516d` 고정 → isaac311-moects 에서 그 자리로 `python -m pip install -e source/robot_lab` · `python -m pip install -e source/rsl_rl` 다시 (의존성은 이미 있어 editable 위치만 바뀔 것, dry-run 으로 먼저 확인) → 같은 연기 시험 | 진단 B 로 URDF 변환은 됨. 학습 단계는 미확인 |
| 나. ASCII 경로 junction 을 한글 폴더에 걸기 | `mklink /J` | robot_lab 은 `os.path.abspath(__file__)` 로 자원 경로를 만든다. editable 설치가 junction 경로를 기록할지 실제 경로로 풀지 미확인. 시험 안 함 |
| 다. 한글 경로 유지 | 저장소 코드나 Isaac Sim 쪽을 고쳐야 함 | 재현 충실도가 떨어진다. 권하지 않음 |

## 5. 본 학습 명령 (연기 시험 통과 뒤에 쓸 것)

```
OMNI_KIT_ACCEPT_EULA=YES CUDA_VISIBLE_DEVICES=0 python scripts/rsl_rl/train.py --task=RobotLab-Go2-v0 --headless
```

- 기본값: num_envs 16384 · `max_iterations` 300,000 · save_interval 500 · 시드 42 · experiment `go2_moe_cts`. cwd 기준 `logs/rsl_rl/go2_moe_cts/` 에 쓴다.
- 예상 시간: **우리 측정 없음.** README 의 「RTX 4090 에서 500 iteration 학습 · 저장 약 30분」(`README 주장`, README.md:158)을 그대로 쓰면 3.6 s/iter 이고 300,000 iter 는 약 300 시간(12.5일), 공개 체크포인트 176k 까지는 약 176 시간(7.3일)이다 (`계산`). RTX 5080 · Windows 에서의 값은 연기 시험으로 재야 한다.

## 6. 로그 목록

| 파일 | 내용 |
|---|---|
| `01-conda-clone.log` | conda clone 출력 · 시작/종료 시각 · 종료 코드 |
| `02-pip-dryrun.log` | README 2단계 dry-run |
| `03-freeze-before.txt` · `03-pipcheck-before.txt` | 설치 전 |
| `04-pip-install.log` | README 2단계 실제 설치 |
| `05-freeze-after.txt` · `05-freeze-diff.txt` · `05-pipcheck-after.txt` | 설치 후 |
| `06-smoke-declare.txt` | 걸기 전 선언 · run2 변경 |
| `07-smoke-run1.log` · `07-smoke-run2.log` | 연기 시험 두 판 |
| `08-gpu-samples-run1.csv` · `08-gpu-samples-run2.csv` | 2초 간격 GPU 메모리 표본 |
| `09-diag-urdf-A.log` · `09-diag-urdf-B.log` | 경로 A/B 진단 |

## 7. 가안 실행: ASCII 경로에서 30 iter 연기 시험 (2026-10-10 11:50 ~ 12:45)

새 로그는 모두 `C:/isaac/ext/go2_rl_robotlab/_smoke/` 에 있다 (번호 10~17). 한글 경로 clone 은 지우지 않았다.

### 7.1 재설치

- `C:/isaac/ext/go2_rl_robotlab` 에 clone, `28b4516d22617b11aeaf8ead63cc00b0c0bcd1bd` 고정, 작업 트리 변경 0.
- isaac311-moects 에서 README 2단계 두 줄을 새 경로에서 다시 실행, 둘 다 종료 0 (`10-pip-reinstall-ascii.log`). dry-run 은 `robot_lab-2.3.0` · `rsl-rl-lib-3.3.0` 만 다시 깔겠다고 했고 실제도 그랬다. 앞뒤 freeze 차이 없음 (`10-freeze-before.txt` · `10-freeze-after.txt`).
- `pip show -f` (`10-pip-show-f.txt`): robot_lab 과 rsl-rl-lib 의 `Editable project location` 이 `C:\isaac\ext\go2_rl_robotlab\source\robot_lab` · `...\source\rsl_rl`. finder 의 MAPPING 도 같은 경로. `import rsl_rl` 이 새 경로에서 로드된다.

### 7.2 걸기 전 선언 (`11-smoke-declare.txt`)

- cwd `C:/isaac/ext/go2_rl_robotlab/_smoke`, 환경변수 `OMNI_KIT_ACCEPT_EULA=YES CUDA_VISIBLE_DEVICES=0`
- `python ../scripts/rsl_rl/train.py --task=RobotLab-Go2-v0 --headless --max_iterations 30 --run_name <이름> agent.save_interval=10`
- train.py 에 `--save_interval` 인자가 없어 hydra override `agent.save_interval=10` 으로 줬다.
- 저장소 기본값에서 바꾼 것: max_iterations 300000 → 30, save_interval 500 → 10, (두 번째 판만) num_envs 16384 → 8192. 시드 42 · device cuda:0 · logger tensorboard 는 기본값.
- 건 뒤 `params/agent.yaml` · `params/env.yaml` 을 되읽어 선언과 맞음을 확인했다 (max_iterations 30 · save_interval 10 · 시드 42 · resume false · num_envs 16384 / 8192).

### 7.3 결과

| 항목 | num_envs 16384 (기본) | num_envs 8192 |
|---|---|---|
| 로그 | `12-smoke-n16384.log` | `15-smoke-n8192.log` |
| 실행 | 11:51:53 ~ 12:41:15, 종료 0 | 12:41:51 ~ 12:44:48, 종료 0 (16384 판이 끝난 뒤 시작, GPU 0 동시 사용 없음) |
| iter 당 시간 (iter 5~29 평균, n=25) | **96.01 s** | **4.596 s** (최소 4.52 · 최대 4.83) |
| 수집 / 학습 시간 (iter 29) | 22.6 s / 72.7 s | 4.14 s / 0.46 s |
| 초당 step (tensorboard `Perf/total_fps`, iter 29) | 4,126 | 42,725 |
| GPU 0 최대 (nvidia-smi 2초 표본) | 15,945 MiB / 16,303 | 14,597 MiB / 16,303 |
| 프로세스 GPU 메모리 (Windows 카운터 최대) | 전용 15,897 MiB + **공유 10,178 MiB** | 전용 14,535 MiB + 공유 2,284 MiB |
| GPU 1 (표본 최소 ~ 최대) | 6,960 ~ 7,061 MiB | 6,975 ~ 7,060 MiB |
| 지형 레벨 `Curriculum/terrain_levels` (iter 0 → 29) | 2.496 → 1.545 | 2.503 → 1.537 |
| teacher / student 평균 보상 (iter 29) | -3.85 / -4.15 | -3.92 / -4.51 |
| 체크포인트 | model_0 · 10 · 20 · 29 (각 26.4 MB) | model_0 · 10 · 20 · 29 |

- **16384 는 메모리 부족이다.** OOM 오류는 없고 종료 0 이지만, Windows WDDM 이 넘친 약 10 GB 를 시스템 RAM(공유 GPU 메모리)으로 넘겨 학습 시간이 데이터 2배에 약 155배(0.47 s → 72.7 s) 늘었다. 그래서 지시대로 8192 로 낮췄다. 프로세스 종료가 금지라 16384 판은 30 iter 를 끝까지 돌렸다(약 50분).
- 8192 의 공유 2,284 MiB 가 넘침인지 정상 공유 버퍼인지는 미확인. 학습 시간 0.46 s 로 보아 큰 넘침은 아니다. 전용 메모리 여유는 약 1.7 GB.
- **보상 로그:** 콘솔과 tensorboard 둘 다 찍힌다. tensorboard 이벤트 파일을 읽어 scalar 37종이 각 30 step 있음을 확인했다 (teacher · student 보상과 에피소드 길이, `Episode_Reward/*` 15항, `Curriculum/terrain_levels`, `Loss/mean_latent_loss` · `Loss/mean_load_balance_loss`, `Perf/*` 등).
- **체크포인트:** 두 판 모두 `model_29.pt` 를 `torch.load` 로 열었다. 키 `model_state_dict` · `optimizer_state_dict` · `optimizer_stu_enc_state_dict` · `iter`(29) · `infos`, 파라미터 2,193,089 개.
- 지형 레벨이 2.5 → 1.5 로 내려간 것은 두 판 모두 같고, 초기 레벨이 0~5 균등(`max_init_terrain_level=5`)이라 평균 2.5 에서 시작해 무작위 정책이 강등되는 초기 구간이다. 30 iter 로 학습이 되는지는 판단할 수 없다.
- 경고: 모든 env 에서 `Head_upper/visuals` · `Head_lower/visuals` 의 USD 참조가 안 풀린다 (env 당 2줄). 시각 prim 에만 걸린다. `CUDA_VISIBLE_DEVICES` 관련 Kit 경고(3.5절)도 그대로 나오지만 실행은 막지 않았다.
- 이 세션이 띄운 프로세스는 남은 것이 없다. pid 25916 살아 있음.

### 7.4 일요일 밤까지 (약 40시간) 몇 iter 가능한가 (`계산`, 본 학습은 걸지 않음)

| | 8192 env | 16384 env |
|---|---|---|
| s/iter (실측 iter 5~29) | 4.596 | 96.01 |
| 40 h = 144,000 s 에 가능한 iter | **약 31,300** (최소 · 최대 iter 시간으로 29,800 ~ 31,900) | 약 1,500 |
| 그동안의 env step | 약 62억 (31,300 × 24 × 8192) | |

- 기동 약 1분과 500 iter 마다의 저장(26 MB)은 무시할 만하다.
- **주의 1.** s/iter 는 학습 초반 30 iter 의 값이다. 에피소드가 길어지거나 지형 레벨이 바뀌면 달라질 수 있다 (미확인).
- **주의 2.** 8192 는 저장소 기본(16384)과 다르다. iteration 수가 같아도 iter 당 표본이 절반이고 PPO minibatch 도 절반(4개 × 49,152)이 된다. 명령 범위 curriculum 은 iteration 기준이라(20,000 · 50,000) 40시간 안에 20,000 단계(약 25.5시간 지점)는 지나고 50,000 은 못 간다. 공개 체크포인트 176k (16384 env, 약 692억 step)에 견주면 iter 로 18 %, step 로 약 9 % 다.
- README 의 RTX 4090 추정(3.6 s/iter, 16384 env, 약 109,000 step/s)에 견주면 우리 8192 판은 약 42,700 step/s 다.

본 학습을 걸 때의 명령 (cwd `C:/isaac/ext/go2_rl_robotlab`, 로그는 cwd 기준 `logs/rsl_rl/go2_moe_cts/`):

```
OMNI_KIT_ACCEPT_EULA=YES CUDA_VISIBLE_DEVICES=0 python scripts/rsl_rl/train.py --task=RobotLab-Go2-v0 --headless --num_envs 8192
```

기본 max_iterations 300,000 이면 4.596 s/iter 로 약 383시간(16일)이다. 일요일 밤에 끝나게 하려면 `--max_iterations 31000` 을 붙이거나 그 시각에 멈춰야 한다 (어느 쪽인지는 lead 결정).

### 7.5 로그 목록 (`C:/isaac/ext/go2_rl_robotlab/_smoke/`)

| 파일 | 내용 |
|---|---|
| `10-pip-reinstall-ascii.log` · `10-freeze-before.txt` · `10-freeze-after.txt` · `10-pip-show-f.txt` | 새 경로 재설치 |
| `11-smoke-declare.txt` | 두 판의 걸기 전 선언 · 8192 로 바꾼 까닭 |
| `12-smoke-n16384.log` · `12-iter-table-n16384.txt` | 16384 판 · iter 표 (iter · 시간 · 수집 · 학습 · teacher/student 보상 · 지형 레벨) |
| `13-gpu-samples-n16384.csv` · `14-gpu-shared-n16384.csv` | 2초 nvidia-smi 표본 · 30초 전용/공유 카운터 |
| `15-smoke-n8192.log` · `15-iter-table-n8192.txt` | 8192 판 · iter 표 (teacher 에피소드 길이 포함) |
| `16-gpu-samples-n8192.csv` · `17-gpu-shared-n8192.csv` | 2초 nvidia-smi 표본 · 10초 전용/공유 카운터 |
| `logs/rsl_rl/go2_moe_cts/2026-10-10_11-51-53_smoke30_n16384/` · `.../2026-10-10_12-41-51_smoke30_n8192/` | params · tensorboard · train.log · 체크포인트 |
