# star 저장소 코드 조사: 논문이 안 주는 숫자를 코드가 무엇으로 주는가

> 분류: 조사 (사실 수집 · 설계 판단 없음)
> 작성: 오흥재 · 2026-10-08 (lead 하위 조사 · 핵심 주장 lead 대조)
> 근거: 9개 저장소 얕은 clone (SHA 는 각 절) · arXiv 2601.08485 v3 HTML · foothold-lab `docs/research/20261007-ame2-go2-v1-v6.md` · `docs/research/20260929-locomotion-direction.md` 93~103행
> 요지: 이 9개 중 목표형 명령은 AME-2 하나 · ame2_minimal 은 G1 전용이지만 논문 밖 신경망 · PPO 숫자를 준다 · 속도형 중 배포 정책 입력에 height scan 이 들어가는 것은 legged_gym 기본 · isaac-go2-ros2 뿐 · Go2 실기 배포 코드는 셋 · 요구 판 번호가 우리 env 와 같은 것도 셋(ame2_minimal · go2_rl_robotlab · JEPLO)
> 상태: 초안 · 팀장 · lead 검토 전

## 요약 (아무것도 실행하지 않았다. 「있다」 는 코드가 있다는 뜻이다)

| 저장소 (SHA) | 무엇을 주는가 | 명령 인터페이스 |
|---|---|---|
| leggedrobotics/ame2_minimal (8beb9a68) | AME-2 저자의 Isaac Lab 2.3.2 재구현. **G1 휴머노이드만**(Go2 · ANYmal 없음). 논문에 없는 신경망 폭 · PPO 변형 · 보상 세부 · curriculum 기간 | **목표형** (목표 x, y + 도착 heading, 에피소드당 1개) |
| wty-yy/go2_rl_gym (30e74dc5) | MoE-CTS(RSS 2026) Isaac Gym 판 Go2 학습 · MuJoCo · Python 실기 배포 | 속도형 (vx, vy, wz), heading 없음 |
| wertyuilife2/go2_rl_robotlab (28b4516d) | 같은 MoE-CTS 의 Isaac Lab 2.3.2 판 · MuJoCo · JIT/ONNX. 실기 코드 없음 | 속도형, heading 없음 |
| wty-yy/RoboGauge (add2c7ee) | MuJoCo 3.2.3 Go2 평가기. 45차원 관측 계약 · 지표 8개 · 지형 7개 | 속도형 (정해진 평가 시퀀스) |
| ASIG-X/JEPLO (460e2272) | Mid-360 LiDAR 구면 depth + JEPA + CTS Go2. Isaac Lab DirectRLEnv · MuJoCo · Jetson C++ | 속도형 (waypoint 지형은 방향을 속도로 변환), heading 입력 없음 |
| leggedrobotics/legged_gym (8fa29acc) | Isaac Gym rough 속도 추종의 원형. Go2 없음. 기본 관측 235 = 48 + 187 | 속도형 + heading |
| unitreerobotics/unitree_rl_gym (276801e4) | legged_gym 을 복사한 **평면** 판. Go2 숫자는 A1 과 같음. Go2 배포 코드 없음 | 속도형 + heading |
| unitreerobotics/unitree_rl_lab (4960b847) | Unitree 공식 Isaac Lab Go2 velocity(**평면 · actor 45**) + deploy.yaml · C++ unitree_sdk2 배포 | 속도형, heading 설정 없음(기본값 False) |
| Zhefan-Xu/isaac-go2-ros2 (f201692a) | Isaac Sim 4.5 추론 + ROS2 브리지. 학습 코드 없음 | 속도형: `Twist` 가 가공 없이 정책 명령 3칸 |
| MARG · START | MARG 공식 코드는 「coming soon」 자리만(arclab-hku/Risky_gym). START 공식 코드는 못 찾음(비공식 Go2/Isaac Lab 각색 Gurukul 있음) | 해당 없음 |

우리 기준선(속도형 · heading True · 재추출 10 s · standing 0.1 · push None · 초기 레벨 2 · 관측 235 중 height 187)은 각 절 표의 마지막 열에 있다.

**가장 중요한 발견 다섯**

1. **ame2_minimal 은 논문이 안 준 숫자를 준다.** proprio encoder 82 → 512 → 512 → 128 · query 192 → 512 → 512 → 96 · MHA 96차원 32 head · decoder 288 → 512 → 512 · 셀 FC 3 → 16 · CNN 1 → 8 → 48 · critic MoE 16 expert(각 499 → 512 → 512 → K, K = 보상 항 수 23 의 multi-head value). PPO 는 Muon · bf16 · 5 epoch · 4 mini-batch 로 논문 부록 C(4 · 3 · 4800 env)와 다르다. 팀 v14 teacher 는 지도 27 × 13 · 6 cm · decoder 224 → 512 → 256 → 128 · 물리 400 Hz 로 코드(26 × 15 · 8 cm · 288 → 512 → 512 · 200 Hz)와 다르다 (1 · 2절).
2. **이 9개 저장소 중 명령이 목표형인 것은 AME-2 하나다.** 나머지 8개는 속도형이고 그중 heading 명령을 쓰는 것은 legged_gym · unitree_rl_gym 둘이다(MoE-CTS · JEPLO 는 없음, unitree_rl_lab 은 설정 없이 기본 False). 재추출은 JEPLO 4 s · MoE-CTS 5 s · legged_gym · unitree_rl_lab 10 s 다.
3. **속도형 저장소 중 배포되는 정책의 입력에 height scan 이 그대로 들어가는 것은 legged_gym 기본(ANYmal · A1 rough, actor 235 = 48 + 187)과 isaac-go2-ros2 의 체크포인트(235, 우리와 같은 숫자)뿐이다.** MoE-CTS 두 판은 height 187 을 teacher latent · critic 에만 쓰고 배포 student 는 고유수용감각 45 × 이력이다. JEPLO 는 높이 맵 300 을 teacher encoder 에만 쓰고 배포 student 는 고유수용감각 + LiDAR 구면 depth(JEPA)다. unitree_rl_lab · unitree_rl_gym 은 평면 · 고유수용감각뿐, RoboGauge 의 평가 계약은 45차원(height 없음)이다. (목표형 AME-2 teacher 는 26 × 15 × 3 지도를 attention encoder 로 받는다.) 덧붙여 JEPLO 의 보상 15항은 go2_rl_robotlab 의 15항과 가중치 · schedule 이 같다.
4. **이 9개 중 Go2 실기 배포 코드는 go2_rl_gym(Python unitree_sdk2) · unitree_rl_lab(C++ · ONNX) · JEPLO(C++ · Jetson) 에만 있다.** legged_gym · unitree_rl_gym(G1 · H1 만) · go2_rl_robotlab · ame2_minimal 에는 없다. go2_rl_gym 실기 스크립트의 명령 scale [3.0, 2.0, 0.5] 는 학습 [2.0, 2.0, 0.25] 와 다르다.
5. **요구 판 번호가 우리 env(Python 3.11 · Isaac Lab 2.3.2 · Isaac Sim 5.1 · torch 2.7.0+cu128 · RTX 5080 sm_120)와 같은 것은 ame2_minimal · go2_rl_robotlab · JEPLO 학습 경로다**(ame2_minimal 의 설치 안내는 Docker 뿐). 셋 다 자기 rsl_rl 개조본(5.0.0 · 3.3.0 · 2.3.1)을 깔도록 되어 있고 우리 env 에는 rsl-rl-lib 3.1.2 가 있다. Isaac Gym 셋은 Python 3.6~3.8 · Linux, RoboGauge 는 mujoco 3.2.3 · torch 2.4.1 을 요구한다. ame2_minimal 코드 주석은 torch 2.7.0+cu128 · sm_120 · bf16 attention 오류와 회피책을 적는다.

---

## 공통 표기와 우리 쪽 사실

- 근거 등급: `코드 확인`(파일:행, 저장소 루트 기준 상대경로) · `README 주장` · `미확인` · `계산`(코드 값으로 이 문서가 셈한 것) · `논문 확인`(arXiv 본문에서 읽음). 어떤 저장소도 **우리가 돌려 보지 않았다.** 「있다」는 코드가 있다는 뜻이고 「돌아간다」는 뜻이 아니다.
- clone 위치: `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/star-src/<owner>__<repo>` (모두 `--depth 1`).
- 「우리 기준선」 열의 출처는 `foothold-lab/docs/research/20260929-locomotion-direction.md` 93~103행 표 하나다. 그 표에 있는 값은 `lin_vel_x=(0.4, 1.5)` · `lin_vel_y=(0, 0)` · `ang_vel_z=(-1, 1)` · `heading_command=True` · `rel_heading_envs=1.0` · `rel_standing_envs=0.1` · `resampling_time_range=(10, 10)` · `push_robot=None` · `max_init_terrain_level=2` · 관측 235차원 중 height scan 187차원 뿐이다. 나머지 칸은 「표에 없음」. 신경망 · 보상 · 배포 표처럼 그 표의 어느 행도 기준선 표에 값이 없는 경우에는 열을 생략했다(모든 행이 「표에 없음」). 「붙일 수 있다」 같은 판단은 적지 않았다.
- 우리 기계에서 이 조사 중 잰 것 (설치 · 실행 없이 조회만):

| 항목 | 값 | 어떻게 쟀나 |
|---|---|---|
| GPU | NVIDIA GeForce RTX 5080 × 2 · compute capability 12.0 (sm_120) · 각 16,303 MiB | `nvidia-smi --query-gpu=name,compute_cap,memory.total` |
| conda env isaac311 | Python 3.11.15 · isaacsim 5.1.0.0 · torch 2.7.0+cu128 · rsl-rl-lib 3.1.2 · isaaclab 0.54.2 | `envs/isaac311/python.exe` 로 버전 조회 |
| 로컬 Isaac Lab 소스 | `C:/isaac/IsaacLab` · git tag `v2.3.2` (37ddf626, 2026-01-29) | `git log -1` |
| RewardManager 의 dt 곱 | `value = func(...) * weight * dt` | `C:/isaac/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py:150` |
| 행동 적용 주기 | decimation 반복 안에서 물리 step 마다 `apply_action()` | `.../envs/manager_based_rl_env.py:182-185` · `.../managers/action_manager.py:395-402` |
| Grid pattern 점 수 | `arange(-size/2, size/2 + 1e-9, resolution)` · ordering "yx" 는 `indexing="ij"` | `.../sensors/ray_caster/patterns/patterns.py:42-46` |

---

## 1. leggedrobotics/ame2_minimal

**무엇을 주는가**: AME-2 저자 쪽 Isaac Lab 2.3.2 재구현. **로봇은 Unitree G1 휴머노이드(23관절) 하나뿐**이고 Go2 · ANYmal-D · TRON1 설정은 없다. 논문이 밝히지 않은 신경망 폭 · head 수 · expert 수 · PPO 변형(Muon · bf16 · multi-head critic) · 보상 함수 세부 · 지형 생성 인자 · curriculum 기간을 코드로 준다. student(neural map) 경로는 코드가 있지만 필요한 모델 파일이 빠져 있어 그대로는 못 돈다.

약어: `cfg` = `ame2/ame2/tasks/ame2_env_cfg.py` · `ppo_cfg` = `ame2/ame2/tasks/agents/rsl_rl_ppo_cfg.py` · `models` = `rsl_rl/rsl_rl/models/AME2_models.py` · `mods` = `rsl_rl/rsl_rl/modules/ame2_modules.py` · `mdp/` = `ame2/ame2/tasks/mdp/` · `terr` = `ame2/ame2/tasks/terrains.py` · `zoo/` = `modelzoo/g1_gaze_64000env_10h/`

### 1.1 메타

| 항목 | 값 | 근거 |
|---|---|---|
| SHA · 마지막 커밋 | `8beb9a688d67882828019583f7d5a78e3517f233` · 2026-10-06 11:25 +0200 「update example cpt and readme」 | `git rev-parse HEAD` · `git log -1` |
| 논문 | 「Agile and Generalized Legged Locomotion via Attention-Based Neural Map Encoding」 IEEE T-RO 2026 · arXiv 2601.08485 (v3, 2026-09-07) | `README 주장` README.md:11-16 · `논문 확인` |
| 라이선스 | GPL-3.0. `rsl_rl/` 은 BSD-3 수정본, Isaac Lab 파생 파일 BSD-3, `mid360_raydirs.npy` 는 fratopa/Mid360_simulation_plugin | `README 주장` README.md:65-74 · LICENSE 1-2 |
| 시뮬레이터 | Isaac Lab 2.3.2 (Isaac Sim 5.1). 컨테이너 기반 `nvcr.io/nvidia/isaac-lab:2.3.2` | `README 주장` README.md:28 · `코드 확인` container/Dockerfile:4 |
| 논문의 시뮬레이터 | 논문은 Isaac Gym + RSL-RL 로 학습했다. 이 저장소는 Isaac Lab 재구현이고 README 가 「IsaacLab 과 legged gym 사이 사소한 세부가 다를 수 있다」고 적는다 | `논문 확인` IV-E1 · `README 주장` README.md:61 |
| Python · 의존성 | ame2 `python_requires>=3.10` · 번들 rsl_rl 5.0.0 `requires-python>=3.9`, `torch>=2.6.0`, `tensordict>=0.7.0`. Dockerfile 은 이미지의 `rsl-rl-lib` 를 지우고 번들 rsl_rl 을 editable 로 깐다 | `코드 확인` ame2/setup.py:37 · rsl_rl/pyproject.toml:7,22,28,30 · container/Dockerfile:15-18 |
| OS | 설치 안내는 Docker + NVIDIA Container Toolkit 과 bash 스크립트뿐. Windows 안내 없음 | `README 주장` README.md:30-39 |
| 등록 task | `Ame2-G1` · `Ame2-G1-Play` · `Ame2-G1-Gaze` · `Ame2-G1-Gaze-Play` · `Ame2-G1-Gaze-Student` · `Ame2-G1-Gaze-Student-Play`. README 의 학습 명령은 `Ame2-G1-Gaze`. `Ame2-G1` 과 `Ame2-G1-Gaze` 는 env cfg 가 같고(`Ame2EnvCfg_G1`) actor 만 다르다 | `코드 확인` ame2/ame2/tasks/__init__.py:17-78 · README.md:33 |
| 공개 체크포인트 | `zoo/model_2400.pt` · G1 gaze teacher · 「64000 envs, 2400 iter」 · run_name `g1_gaze_4x16k` (env.yaml `num_envs: 16000`) | `README 주장` modelzoo/models.md:1 · `코드 확인` zoo/params/agent.yaml:4,15 · zoo/params/env.yaml:86 |

### 1.2 명령 인터페이스: **목표형**

| 항목 | ame2_minimal 최종값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 명령 종류 | 목표 위치 + 도착 heading (`SafeTerrainBasedPose2dCommand`). 속도 명령 없음 | `코드 확인` cfg:149-162 · mdp/commands.py:18-80 | 속도 명령 `lin_vel_x=(0.4,1.5)` · `lin_vel_y=(0,0)` · `ang_vel_z=(-1,1)` |
| 목표 위치 표본 | 지형마다 정의된 flat patch(`target`, 30개) 중 env origin 기준 `\|y\| <= x·tan(cone)+0.1` 안의 것을 무작위로. 없으면 아무 patch. patch 범위 예: stones x 1.0~5.8 m · y ±5 m, climb_up x 2.6~5.5 m | `코드 확인` mdp/commands.py:25-58 · terr:211-230, 110-126 | 표에 없음 |
| cone 각 | cfg 45°. curriculum 이 10° → 45° 로 `24*2000` env step(2000 iteration) 동안 선형 증가 | `코드 확인` cfg:158, 632-639 · mdp/curriculums.py:190-204 | 표에 없음 |
| 도착 heading | world yaw `U(-π/3, π/3)` (`simple_heading=False`) | `코드 확인` cfg:156, 159-161 · mdp/commands.py:77-80 | `heading_command=True` · `rel_heading_envs=1.0` (속도형 heading) |
| 재추출 | 16.01 s. 에피소드 16 s 이므로 에피소드당 목표 1개 | `코드 확인` cfg:155, 675 | `resampling_time_range=(10,10)` |
| 정지 명령 | 별도 standing 환경 없음. 목표 도착 뒤 정지는 `standatgoal` 보상이 담당 | `코드 확인` cfg:429-436 | `rel_standing_envs=0.1` |
| actor 가 받는 명령 | `[x, y, sin(yaw_err), cos(yaw_err)]` 4차원. 거리 2 m 로 자르고 2 m 밖이면 yaw 를 무작위로 바꿔 넣음. 남은 시간 없음 | `코드 확인` cfg:259-262 · mdp/observations.py:263-298 · `논문 확인` IV-E3 | 표에 없음 |
| critic 이 받는 명령 | 자르지 않은 4차원 + 남은 시간 비율 1 | `코드 확인` cfg:201-204 · mdp/observations.py:253-255 | 표에 없음 |
| 초기 yaw | cfg 는 ±π/4 이지만 curriculum 이 매 reset 에 `(-p·π, p·π)` 로 덮어쓴다(p 는 0→1, 2000 iteration). Isaac Lab 은 reset 때 curriculum 을 이벤트보다 먼저 계산한다. 논문은 「처음 20 % iteration 동안 목표를 향한 방향 → [-π, π]」 | `코드 확인` cfg:378, 624-631 · mdp/curriculums.py:175-187 · 로컬 Isaac Lab manager_based_rl_env.py:356, 362 · `논문 확인` IV-D3 | 표에 없음 |

### 1.3 관측

| 항목 | 최종값 | 근거 | 우리 기준선 |
|---|---|---|---|
| actor `teacher_prop` | 선속도 3 (잡음 ±0.1) · 각속도 3 (±0.2) · 중력 3 (±0.05) · 관절각 23 (±0.01) · 관절속도 23 (±1.5) · 직전 행동 23 (±50 clip) · 명령 4 = **82** (G1). Go2 12관절이면 같은 구성이 49 (`계산`) | `코드 확인` cfg:242-266 · mdp/observations.py:248-250 · mdp/symmetry.py:168 | 표에 없음 |
| actor `teacher_mapping` | **26 × 15 × 3** (x, y, z). z = 광선 hit 높이 − 센서 높이 + 0.74, clip ±1.5. 빈 셀은 env 최저값 + U(-1.5, -0.65). 잡음 x·y ±0.001, z 는 0 → 0.05 curriculum(2000 iteration). 스캐너 drift ±0.04 m | `코드 확인` cfg:71-81, 229-239, 640-647 · mdp/observations.py:120-196 | 235차원 중 height scan 187 |
| 격자 | GridPattern 해상도 0.08 m · size 2.0 × 1.12 m · offset x +0.5 → base 기준 x ∈ [-0.5, 1.5], y ∈ [-0.56, 0.56], 390점 · yaw 정렬 | `코드 확인` cfg:71-81 · Isaac Lab patterns.py:42-46 | 표에 없음 |
| 논문 격자 | ANYmal-D 36 × 14 · 8 cm · 중심 x 0.6 m. TRON1 18 × 13 · 8 cm · 중심 x 0.32 m | `논문 확인` IV-E1 | |
| critic | base 9 + 관절 3 × 23 + 명령 4 + 남은 시간 1 + 접촉 26(질량 > 0.1 kg 링크, 1 N 문턱) + height scan 390 = **499**. 잡음 끔 | `코드 확인` cfg:183-226, 317-318 · mdp/symmetry.py:206, 222 | 표에 없음 |
| 이력 | teacher 없음. student `student_prop_hist` 20 step(선속도 제외) | `코드 확인` cfg:269-299 | 표에 없음 |
| 정규화 · 스케일 | obs scale 없음. `AME2Model` · `MoEModel` 의 `update_normalization` 은 비어 있고 `empirical_normalization=None` | `코드 확인` models:229-230, 1177-1178 · ppo_cfg:125 | 표에 없음 |

### 1.4 행동 · 제어

| 항목 | 최종값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 행동 | 전 관절 위치 목표, 기본 자세 offset (`use_default_offset=True`) | `코드 확인` cfg:169-176 | 표에 없음 |
| action scale · clip | 0.25 · ±100 (사실상 clip 없음) | `코드 확인` cfg:172, 174 | 표에 없음 |
| 행동 지연 | `delay_range=(0,1)`. 지연 버퍼가 `apply_actions` 안에서 돌고 Isaac Lab 은 이것을 물리 step 마다 부르므로 지연 단위는 물리 step → 0 또는 5 ms (`계산`). 논문 부록 B 는 [0, 0.02] s | `코드 확인` actions.py:44-65 · Isaac Lab manager_based_rl_env.py:182-185 · `논문 확인` 부록 B | 표에 없음 |
| PD (G1) | DCMotor. hip yaw/pitch Kp 88 · Kd 2, hip roll 139 · 3, knee 139 · 3, waist yaw 88 · 2, waist roll/pitch 50 · 1, ankle 35 · 0.8, shoulder pitch 35 · 0.8, shoulder roll/yaw · elbow 40 · 1. saturation = effort × 1.25 | `코드 확인` ame2/ame2/assets/unitree.py:49-176 | 표에 없음 |
| sim dt · decimation | 0.005 s (200 Hz) · 4 → 정책 50 Hz. 논문은 50 Hz, 실기 PD 400 Hz | `코드 확인` cfg:674, 677 · `논문 확인` III-B | 표에 없음 |

### 1.5 신경망

| 부분 | 최종값 (ELU 전부) | 근거 |
|---|---|---|
| `MLP_512` 정의 | in → 512 → 512 → out (ELU 두 번) | `코드 확인` mods:20-33 |
| proprio encoder | `MLP_512(82 → 128)` | `코드 확인` models:73 |
| 셀별 위치 FC | Linear(3 → 16) 1층 | `코드 확인` models:52-55 |
| CNN (z 채널만) | Conv 5×5 (1 → 8) · Conv 5×5 (8 → 48), padding 2 | `코드 확인` models:57-62 |
| 점별 융합 | Linear(16 + 48 → 96) | `코드 확인` models:65-68 |
| 전역 특징 | MLP 96 → 64 → 64 후 셀 방향 max pool → 64 | `코드 확인` models:78, 168-169 · mods:36-44 |
| query | `MLP_512(128 + 64 → 96)` | `코드 확인` models:79, 170-171 |
| MHA | embed 96 · **32 head**(head 차원 3) · key/value = 390 셀. SDPA math kernel 고정(주석: torch 2.7.0+cu128 · bf16 · sm_120 에서 fused kernel 이 죽는다) | `코드 확인` models:80, 172 · mods:7-17 |
| decoder | `MLP_512(96 + 128 + 64 = 288 → 행동 수)` | `코드 확인` models:85 |
| 출력 분포 | Gaussian, log std, 초기 std 1.0 | `코드 확인` ppo_cfg:154-159 |
| **README 대표 task 의 actor** (`Ame2-G1-Gaze`) | `AME2GazeModel`: 전체 지도에 Conv 3×3(3→8) · Conv 3×3 dilation 2 (8→32) → 공간 max → Linear 32 → 64 = 전역. gaze head (64+128 → 64 → 2) sigmoid 로 crop 중심을 내고 **12 × 10 crop** 만 위 FC/CNN/융합 → MHA(120 셀). straight-through crop. 보조 손실 roi_coef 0.01 · roi_margin 0.45 (클래스 기본 0.35 를 cfg 가 덮음). 주석이 TAGA(arXiv 2606.05880)를 인용 | `코드 확인` models:390-634 · ppo_cfg:63-79, 190-194 |
| critic | **MoE 16 expert**, 각 `MLP_512(499 → K)`, router `MLP_512(499 → 16)`, softmax 가중 합 | `코드 확인` models:1046-1120 · ppo_cfg:160-163 |
| critic 출력 K | multi-head critic(GCR-PPO arXiv 2509.14816 인용): 보상 항마다 value head. K = 활성 보상 항 수 = G1 cfg 에서 23 (`계산`, cfg:412-570 의 RewTerm 수) | `코드 확인` rsl_rl/rsl_rl/algorithms/ppo.py:35, 137-140, 650-657 |
| 대칭 증강 | critic 에만 좌우 대칭 데이터 증강 | `코드 확인` ppo_cfg:180-185 · mdp/symmetry.py:35-36 |
| student (`AME2GazeLSIOModel`) | 20 step 이력에 Conv1d(prop → 16, k5) → Linear(16·16 → 64) + 최근 3 step Linear(3·prop → 60) + 명령 → `MLP_512 → 128`. 지도는 neural map 26 × 15 × 4 (x, y, z, 불확실도). 나머지는 gaze teacher 와 같은 구조 | `코드 확인` models:641-834, 296-322 · mdp/observations.py:201-240 |
| distillation | `PPO_IL`: imitation_coef 0.02 · repr_coef 0.2 · rl_switch_point 4001(그 전엔 surrogate 끔, 이후 lr 1e-5) · 20,000 iteration · teacher JIT 경로 `NN_models/g1_gaze_teacher_isaaclab.jit`. 논문은 student 40,000 iteration, 처음 5000 iteration surrogate 끔 | `코드 확인` ppo_cfg:109-117, 197-245 · rsl_rl/rsl_rl/algorithms/ppo_il.py:40-75 · `논문 확인` IV-E1 · 부록 C |
| student 실행 가능 여부 | mapping 모델 `ame2/NN_models/g1LivoxMapping_perframe.pt` 와 teacher JIT 이 저장소에 없다. 없으면 `FileNotFoundError` 를 내도록 짜여 있다. README 도 「다음 논문 공개까지 unavailable」 | `코드 확인` ame2/ame2/sensors/livox_neural_map_sensor.py:51-53, 379 · `README 주장` README.md:46-47 |
| 내보내기 | JIT 만 (`play.py` 에서 `as_jit` → script → freeze). ONNX 는 `NotImplementedError` | `코드 확인` ame2/scripts/rsl_rl/play.py:641-657 · models:225-227 |

### 1.6 학습

| 항목 | 최종값 | 근거 | 논문 부록 C |
|---|---|---|---|
| num_envs | 4096 (cfg 기본) · 공개 run 은 GPU 4장 × 16,000 = 64,000 | `코드 확인` cfg:660 · zoo/params/env.yaml:86 · `README 주장` models.md:1 | 4800 |
| num_steps_per_env | 24 | `코드 확인` ppo_cfg:149 | 24 |
| epochs · mini-batch | **5 · 4** | `코드 확인` ppo_cfg:169-170 | 4 · 3 |
| lr · schedule | 1e-3 · adaptive (desired_kl 0.01, KL > 2×목표면 /1.5, < 목표/2 면 ×1.5, 범위 [1e-5, 1e-3]) | `코드 확인` ppo_cfg:171-175 · ppo.py:385-409 | adaptive · 0.01 |
| entropy | 0.004 시작, 매 iteration ×0.9999, 하한 0.001 | `코드 확인` ppo_cfg:168, 177-178 · ppo.py:538-541 | 0.004 → 0.001 감소 |
| clip · gamma · lambda | 0.2 · 0.99 · 0.95 | `코드 확인` ppo_cfg:167, 173-174 | 0.2 · 0.99 · 0.95 |
| value loss | coef 1.0 · clipped · value loss 가 100 을 넘으면 100 으로 재정규화 | `코드 확인` ppo_cfg:165-166, 179 · ppo.py:429-430 | coef 1.0 · clip 0.2 |
| max_grad_norm | 1.0 | `코드 확인` ppo_cfg:176 | 미기재 |
| optimizer · 정밀도 | **Muon**(2차원 이상 가중치, Newton-Schulz 5회, momentum 0.95, lr 을 `0.2·√max(행,열)` 로 맞춤) + AdamW(나머지) · **bf16 autocast**(forward · loss 만) | `코드 확인` ppo_cfg:84-89 · rsl_rl/rsl_rl/utils/muon.py:39-130 · ppo.py:341-345 | 미기재 |
| max_iterations | 5000 (cfg) · 공개 run 설정 3000, 체크포인트 2400 | `코드 확인` ppo_cfg:150 · zoo/params/agent.yaml:4 · `README 주장` models.md:1 | teacher 80,000 · student 40,000 |
| 시드 | 42 (+ GPU local_rank) | `코드 확인` ppo_cfg:121 · ame2/scripts/rsl_rl/train.py:133-138 | |
| multi-GPU | torchrun `--distributed` | `README 주장` README.md:34 · `코드 확인` train.py:29-31, 133-138 | |
| 학습 시간 · GPU | 체크포인트 폴더 이름 `64000env_10h` 만 있음(GPU 종류 미기재) | `README 주장` models.md:1 | ANYmal-D 약 60 RTX-4090-days(8 GPU), TRON1 약 30(4 GPU) |

### 1.7 보상 (Isaac Lab RewardManager 가 weight × dt(0.02 s) 를 곱한다. 논문 Table I 의 가중치 열도 「× dτ, dτ = 0.02 s」)

| 항 | weight | 핵심 인자 · 식 | 근거 (`코드 확인`) | 논문 Table I |
|---|---:|---|---|---|
| position_tracking | 100 | `1/(1+(d/2)²) · 1(t_left<4)/4` | cfg:413-415 · mdp/rewards.py:219-236 | 100 · 같은 식 |
| heading_tracking | 50 | `1/(1+dyaw²) · 1(t_left<2)/2 · 1(d<0.5)` | cfg:416-418 · rewards.py:239-259 | 50 · 같은 식 |
| move2goal | 5 | d < 0.5 이거나 (cos > 0.5 그리고 0.3 ≤ v ≤ 2.0 m/s) 면 1. v 범위는 함수 기본값 | cfg:419-428 · rewards.py:180-216 | 5 (Eq.4 의 계수는 대조 안 함) |
| standatgoal | 5 | d < 0.5 · \|yaw\| < 0.5 일 때 `exp(-(d_foot + d_g + d_q + d)/4)` | cfg:429-436 · rewards.py:262-304 | 5 |
| early_termination_penalty | -500 | `early_.*` 종료 수 | cfg:439-443 · rewards.py:35-59 | `-10/dτ` = -500 (`계산`) |
| undesired_spinning | -1 | head_link yaw rate > **3.0** rad/s (함수 기본값 2.0) | cfg:445-449 · rewards.py:352-365 | -1 · 2.0 rad/s |
| undesired_leaping | -1 | 모든 발 비접촉 그리고 scan 고저차 < 0.3 m, 0.2 s 이후 | cfg:450-460 · rewards.py:368-396 | -1 · 30 cm |
| undesired_non_foot_contacts | -1 | 발 외 링크 접촉 수 + 새 접촉 수 | cfg:461-468 · rewards.py:399-412 | -1 |
| undesired_stumbling | -1 | 수평력 > 1.1 × 수직력 + 1 N 인 링크 수 | cfg:469-473 · rewards.py:415-426 | -1 · 「수평 > 수직」 |
| undesired_slippage | -1 | 접촉 0.025 s 이상 그리고 수평 속도 > 0.3 m/s (함수 기본 0.25) | cfg:474-483 · rewards.py:429-463 | -1 |
| undesired_self_col (knee · torso · ankle) | -1 × 3 | 필터 접촉 센서 | cfg:484-507 · rewards.py:466-482 | -1 (self-collision) |
| base_roll_rate | -0.1 | torso roll rate² | cfg:510-514 | -0.1 |
| joint_regularization | -0.001 | `‖q̇‖² + 0.01‖τ‖² + 0.001‖q̈‖²` | cfg:515-519 · rewards.py:321-335 | -0.001 · 같은 식 |
| action_smoothness | -0.01 | `‖a_t − a_{t−1}‖²` | cfg:520-523 | -0.01 |
| link_contact_forces | -1e-5 | `max(F − 400 N, 0)²`, F 는 2G 로 상한 | cfg:524-531 · rewards.py:338-350 | -0.00001 |
| body_lin_acc_l1 | -0.001 | 0.1 kg 이상 링크 가속도 노름 합(유한차분 센서) | cfg:532-536 · rewards.py:65-97 | -0.001 |
| joint_pos_limits | -1000 | 0.95 × 한계 초과분 | cfg:538-541 · rewards.py:505-520 | -1000 |
| joint_vel_limits | -1 | 0.9 × 한계 초과분 | cfg:542-545 · rewards.py:523-551 | -1 |
| joint_torque_limits | -1 | 0.8 × 한계 초과분 | cfg:546-549 · rewards.py:554-582 | -1 |
| optional_uppershaping | -1 | 팔 관절 편차², 험지에선 ×0.1 | cfg:552-560 · rewards.py:584-607 | 없음 (README.md:50 「휴머노이드용 · 튜닝 안 함」) |
| optional_foot_shaping | -1 | 발 yaw | cfg:562-570 · rewards.py:610 | 없음 |

### 1.8 종료

| 항 | 코드 | 근거 | 논문 IV-D2 |
|---|---|---|---|
| 기울기 | \|g_x\| > 0.985 · \|g_y\| > 0.7 · g_z > 0, 0.2 s 이후 | `코드 확인` cfg:577-586 · mdp/terminations.py:37-79 | 같음 |
| 허벅지(hip_pitch) 급가속 | > 100 m/s², 발 접촉 중, 1 s 이후 | `코드 확인` cfg:587-596 | 60 (사족) · 100 (휴머노이드) |
| 몸통 충돌 | torso · pelvis 접촉력 > 400 N, 1 s 이후 | `코드 확인` cfg:597-604 | > 로봇 전체 무게 |
| 정체 | 5 s 동안 0.5 m 미만 이동 그리고 목표까지 > 1 m | `코드 확인` cfg:605-613 · terminations.py:180-230 | 같음 |
| 시간 | 16 s | `코드 확인` cfg:675 | 미기재 |

### 1.9 지형 · curriculum

| 항목 | 최종값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 격자 | 12 × 12 m, 10행 × 60열, border 10 m, horizontal 0.1 · vertical 0.005 | `코드 확인` terr:14-22 | 표에 없음 |
| 지형 비율 | rough 5 · stair_down 5 · stair_up 5 · boxes 5 · obstacles 5 · climb_up 20 · climb_down 5 · consecutive 5 · gap 5 · pallets 5 · beam 5 · stones 30 (%) = 12종. pit · peak · test_1 · test_2 는 0 %. **논문 부록 A 의 12종 · 비율과 같다** | `코드 확인` terr:23-288 · `논문 확인` 부록 A | 표에 없음 |
| 난이도 상한 (G1) | stair 계단 0.27 m · boxes 0.05~0.3 m · obstacles 0.2~2.0 m · climb_up 0.1~0.65 m · climb_down 0.2~0.88 m · consecutive 0.05~0.35 m · gap 0.18~1.2 m · stones 0.41~0.71 m 상자. 논문 ANYmal-D 는 climb_up 1.0 m · gap 1.1 m · boxes 0.4 m, TRON1 은 climb_up 0.48 m · climb_down 0.88 m | `코드 확인` terr:44, 75-77, 96, 113-114, 130-131, 147-149, 165-166, 215-216 · `논문 확인` 부록 A | 표에 없음 |
| 초기 레벨 | teacher `max_init_terrain_level=5`, student 9 | `코드 확인` cfg:51, 772 | `max_init_terrain_level=2` |
| 승급 · 강등 | 에피소드 끝 목표 거리 < 0.5 m 그리고 성공 EMA > 0.5 면 승급, > 4.0 m 면 강등. EMA = 0.8·EMA + 0.2·성공, 성공 = 거리 < 0.5 m 그리고 남은 시간 < 4 s | `코드 확인` cfg:620-623 · mdp/curriculums.py:292-327 · `논문 확인` IV-D3 (같은 규칙, EMA 계수는 미기재) | 표에 없음 |
| 그 밖의 curriculum | 초기 yaw 0 → ±π · goal cone 10° → 45° · 지도 z 잡음 0 → 0.05 m, 모두 2000 iteration(`24*2000` step) 선형. 논문은 「처음 20 % iteration」 | `코드 확인` cfg:624-647 · `논문 확인` IV-D3 | 표에 없음 |
| PLAY | 2 × 2 지형, stones 하나 · 난이도 0.93 고정, 무작위화 끔 | `코드 확인` cfg:712-754 | |

### 1.10 Domain randomization

| 항목 | 코드 최종값 | 근거 | 논문 부록 B | 우리 기준선 |
|---|---|---|---|---|
| 마찰 | static · dynamic 0.3~1.0, 64 bucket, restitution 0 | `코드 확인` cfg:326-336 | [0.3, 1.0] | 표에 없음 |
| 질량 | torso 에 -1~+3 kg 더함 | `코드 확인` cfg:338-346 | payload [-5, 5] kg | 표에 없음 |
| 질량중심 | torso x · y ±0.02 m, z ±0.04 m | `코드 확인` cfg:348-355 | 대조한 범위에서 못 찾음 | 표에 없음 |
| 모터 | Kp · Kd · armature × 0.85~1.15 | `코드 확인` cfg:357-368 | TRON1 PD · armature ±15 % | 표에 없음 |
| 지연 | 0~1 물리 step (0~5 ms, `계산`) | `코드 확인` cfg:175 · mdp/actions.py:44-65 | [0, 0.02] s | 표에 없음 |
| 관측 잡음 | 선속도 0.1 · 각속도 0.2 · 중력 0.05 · 관절각 0.01 · 관절속도 1.5 | `코드 확인` cfg:247-255 | 같음 | 표에 없음 |
| 지도 잡음 · drift | z 0→0.05 m · x·y 0.001 · drift ±0.04 m | `코드 확인` cfg:80, 234, 640-647 | 0.05 m · drift [-0.03, 0.03] m | 표에 없음 |
| push | **없음** (EventCfg 에 push 항이 없다. PLAY 의 `push_robot=None` 은 빈 속성) | `코드 확인` cfg:321-405, 746 | 대조한 범위에서 못 찾음 | `push_robot=None` |
| reset | 위치 ±0.2 m · 속도 ±0.5 · 관절 ×0.5~1.5 | `코드 확인` cfg:374-397 | | 표에 없음 |
| assistive force | 이벤트는 등록돼 있지만 힘을 정하는 curriculum(`ame2_optional_assistive_force`)이 CurriculumCfg 에 없어서 `env.assistive_force` 가 생기지 않고 이벤트는 바로 return 한다 | `코드 확인` cfg:399-405, 616-647 · mdp/events.py:668-675 · mdp/curriculums.py:385-405 | 없음 | |

### 1.11 배포 경로

- sim-to-sim(MuJoCo) 코드 없음. sim-to-real(unitree_sdk2 등) 코드 없음. 파일 목록 166개에 deploy · mujoco · sdk 관련 파일이 없다. `코드 확인` (`git ls-files`)
- 내보내기는 JIT 뿐 (1.5절 표).

### 1.12 논문에 없고 코드에만 있는 것 (논문 대조함: arXiv 2601.08485v3 HTML 본문 · 부록 A~D)

1. **모든 신경망 폭과 층 수**: proprio MLP 512-512-128, query MLP 512-512-96, decoder 512-512, 셀 FC 16, CNN 8 · 48, 융합 96, 전역 64, MHA 32 head. 논문은 구성 요소 이름(CNN · positional MLP · max pool · MHA)만 적고 숫자가 없다(본문에서 head 수 · 폭을 찾지 못함).
2. **critic expert 수 16 과 각 expert 폭**: 논문은 「[68] 의 MoE 설계」만 적는다.
3. **PPO 변형 셋**: Muon optimizer · bf16 autocast · multi-head critic(보상 항마다 value head). 셋 다 논문 부록 C 에 없다. 부록 C 와 다른 값도 있다: epoch 5 (논문 4) · mini-batch 4 (논문 3) · env 4096 (논문 4800).
4. **gaze crop actor** (`Ame2-G1-Gaze`, README 대표 task): TAGA(arXiv 2606.05880)를 인용하는 추가 구조로 AME-2 논문 본문에 없다.
5. 보상 세부: spinning 문턱 3.0 rad/s (논문 2.0), slippage 0.3 m/s · 접촉 0.025 s, stumbling 의 1.1 배 + 1 N, move2goal 속도창 0.3~2.0 m/s, link contact 의 400 N 기준과 2G 상한.
6. curriculum 길이: 2000 iteration 고정(논문은 「처음 20 %」, 80,000 의 20 % 는 16,000), 성공 EMA 계수 0.8/0.2, 성공 판정 「남은 시간 < 4 s」, goal cone 10° → 45°.
7. 지도 전처리: 높이 offset 0.74, clip ±1.5, 빈 셀 채움 규칙(최저값 + U(-1.5, -0.65)).
8. DR 범위 중 논문과 다른 것: 질량 -1~+3 kg (논문 ±5), 지연 0~5 ms (논문 0~20 ms), drift ±0.04 (논문 ±0.03). 이 차이가 G1 용 조정인지 Isaac Lab 이식 과정의 차이인지는 저장소가 밝히지 않는다. `미확인`
9. 논문과 같은 것(확인): 보상 가중치 Table I 전부(humanoid optional 2개 제외) · position/heading 식 · 종료 4종 문턱(허벅지는 휴머노이드 값) · 지형 12종 비율 · 승급(성공률 > 0.5) · 강등(> 4 m) · 관측 잡음 · 명령 2 m 자르기.

### 1.13 우리 기계에서 돌릴 수 있는가 (요구 vs 우리 환경 · 판단 없음)

| 요구 | 저장소 | 우리 환경 |
|---|---|---|
| Isaac Lab · Isaac Sim | 2.3.2 · 5.1 | 로컬 Isaac Lab tag v2.3.2 · isaacsim 5.1.0.0 |
| Python | ≥ 3.10 (Isaac Sim 5.1 컨테이너) | 3.11.15 |
| rsl_rl | 번들 rsl_rl 5.0.0 이 `rsl-rl-lib` 를 대체 (Dockerfile) | env 에 rsl-rl-lib 3.1.2 |
| torch | ≥ 2.6.0. 주석이 torch 2.7.0+cu128 · sm_120 조합의 bf16 attention 오류와 회피책을 적음 | torch 2.7.0+cu128 · RTX 5080 sm_120 |
| 설치 방식 | Docker + NVIDIA Container Toolkit · bash | Windows 11 네이티브 conda. Docker 사용 여부는 이 조사에서 안 봄 `미확인` |
| 컴파일 | `.cu` · `.cpp` 파일 없음 (`git ls-files`) | nvcc · MSVC 없음 |
| GPU 메모리 | 공개 run 은 GPU 당 16,000 env. 팀 v15 는 Go2 이식에서 4096 · 2048 env 가 OOM 이었다고 적음(GPU 종류는 보고서에 없음) | 16,303 MiB × 2 |
| 로봇 | G1 만. Go2 로 쓰려면 자산 · 관절 수 · 대칭 함수(23관절 가정, symmetry.py:149) · 접촉 링크 이름이 G1 고정 | |

---

## 2. 팀 보고서(임석헌 v1~v6) 설정 vs ame2_minimal 코드

- 보고서: `foothold-lab/docs/research/20261007-ame2-go2-v1-v6.md` (커밋 b9c97356, 2026-10-07 21:56). 행 번호는 이 파일 기준. 보고서의 설정은 RunPod 볼륨의 v14 candidate `bootstrap` 코드를 읽어 옮긴 것이고(보고서 60행), 이 조사는 그 볼륨을 직접 보지 않았다. 보고서 값은 「보고서가 적은 값」이다.
- 「v14 teacher」 열 = 서사 v1~v6 계열(내부 v7~v14)의 자체 구현. 「v15」 열 = 보고서 5절 300행이 적은 「공개 ame2_minimal 8beb9a6 의 G1 teacher 를 Go2 로 이식」한 판(결과 없음, 학습 중). 코드 열 = ame2_minimal (G1) 최종값.
- 보고서에 없는 칸은 「보고서에 없음」.

| 항목 | 보고서 v14 teacher (행) | 보고서 v15 공개 코드 이식 (행) | ame2_minimal 코드 (파일:행) |
|---|---|---|---|
| 로봇 · 관절 수 | Go2 · 12 (68) | Go2 (300) | G1 · 23 (mdp/symmetry.py:149, 168) |
| 명령 (actor) | `[dx, dy (2 m 로 자름), sin, cos]`, 2 m 밖 yaw 무작위 가림 (69) | 보고서에 없음 | 같음 (cfg:259-262 · mdp/observations.py:263-298) |
| 명령 (critic) | 자르지 않은 x · y · sin · cos · 남은 시간 = 5 (81) | 보고서에 없음 | 같음, 4 + 1 (cfg:201-204) |
| 과제 · 목표 표본 | move · pose · turn · stand 과제 비율 3:3:2:2 → 49:49:2:0 (112, 195), 거리 0.6~1.5 m (155) · 1~1.5 m 고정 (223) · 거리 단계 [1,1.5] → [1,2.5] → [1.5,4] m (196), v14 candidate 는 정면 ±15° 30 % (253) | 공개 12종 지형 (300) | 과제 구분 없음. 지형 flat patch 에서 에피소드당 목표 1개, cone 10° → 45° (mdp/commands.py:25-58 · cfg:632-639) |
| 에피소드 | 8 s (155) → 20 s (222) | 16 s (300) | 16 s (cfg:675) |
| 초기 방향 | 360° 무작위 (155) | 보고서에 없음 | curriculum 0 → ±π, 2000 iteration (cfg:624-631) |
| actor 관측 차원 | 상태 45 + 명령 4 = 49 (64, 68-69) | 보고서에 없음 | 82 (G1). 항목 구성은 같다 (cfg:242-266). Go2 12관절이면 49 (`계산`) |
| 지도 격자 | 27 × 13, 6 cm, 중심 x 0.36 m, 351점 × (x, y, z) (70, 75) | 26 × 15 (300) | 26 × 15, 8 cm, 중심 x 0.5 m, 390점 × (x, y, z) (cfg:71-81) |
| 상태 encoder | MLP 49 → 128 → 64 (74) | 보고서에 없음 | `MLP_512`: 82 → 512 → 512 → 128 (models:73 · mods:20-30) |
| 셀 위치 MLP | 3 → 32 → 16 (75) | 보고서에 없음 | Linear 3 → 16 한 층 (models:52-55) |
| 높이 CNN | 5×5 두 층 → 48채널 (75) | 보고서에 없음 | 같음: 1 → 8 → 48, 5×5 (models:57-62) |
| 점별 MLP | 64 → 96 → 96 (75) | 보고서에 없음 | Linear 64 → 96 한 층 (models:65-68) |
| 전역 MLP | 96 → 128 → 64 + max pool (75) | 보고서에 없음 | 96 → 64 → 64 + max pool (models:78 · mods:36-44) |
| query | 상태 64 + 전역 64 → 96 (75) | 보고서에 없음 | `MLP_512`: 128 + 64 → 512 → 512 → 96 (models:79) |
| MHA | 96차원 · 32 head · 351점 (75) | 보고서에 없음 | 96차원 · 32 head · 390점(`Ame2-G1`) 또는 gaze crop 120점(`Ame2-G1-Gaze`) (models:80, 497-498) |
| decoder | 224 → 512 → 256 → 128 → 12 (76) | 보고서에 없음 | 288 → 512 → 512 → 행동 수 (models:85) |
| 활성 | ELU (76) | 보고서에 없음 | ELU (mods:22) |
| 은닉 크기의 출처 | 「논문 미공개라 구현 선택」 (77) | 보고서에 없음 | 코드가 값을 준다 (1.5절) |
| gaze crop | 보고서에 없음 | 보고서에 없음 (어느 actor 를 옮겼는지 안 적음) | README 대표 task 는 gaze crop 12 × 10 (ppo_cfg:63-79, 190-194) |
| critic 입력 | 45 + 5 + 351 + 링크 접촉 19 = 420 (79) | 453 (300) | 9 + 69 + 4 + 1 + 26 + 390 = 499 (cfg:183-226 · mdp/symmetry.py:206, 222). 같은 식에 Go2 12관절을 넣으면 440 + 접촉 링크 수, 453 이면 접촉 13 (`계산`, 이식본 코드는 안 봄) |
| critic 구조 | MoE 16 expert, 각 420 → 256 → 256 → 128 → 1, gate 420 → 128 → 128 → 16 (82) | MoE critic (300) | MoE 16 expert, 각 499 → 512 → 512 → K, router 499 → 512 → 512 → 16 (models:1069-1075) |
| critic 출력 | 1 (82) | 보고서에 없음 | K = 보상 항 수, G1 cfg 23 (ppo.py:650-657, `계산`) |
| 대칭 증강 | critic 에만 (82) | 보고서에 없음 | critic 에만 (ppo_cfg:180-185) |
| 물리 · 정책 주기 | 400 Hz · 50 Hz · decimation 8 (86) | 물리 200 Hz (300) | 200 Hz · 50 Hz · decimation 4 (cfg:674, 677) |
| action scale | 0.25 (86) | 보고서에 없음 | 0.25 (cfg:172) |
| Go2 보호 장치 | 목표각 기본 자세 ±0.5 rad, 4 rad/s, 출력 배율 0.8 · 목표 근처 0.4 (87) | 보고서에 없음 | 없음. clip ±100 (cfg:174) |
| 행동 지연 | PD 지연 0~20 ms (96) | 보고서에 없음 | 0~1 물리 step = 0~5 ms (cfg:175 · mdp/actions.py:44-65, `계산`) |
| num_envs | 4096 (논문 4800) (88) | 1024 (4096 · 2048 OOM) (300) | 4096 (cfg:660) · 공개 run 64,000 (env.yaml:86 · models.md:1) |
| PPO epoch · mini-batch | 4 · 3 (88) | 5 · 4 (300) | 5 · 4 (ppo_cfg:169-170) |
| rollout · entropy | 24 · 0.004 → 0.001 (88) | 보고서에 없음 | 24 · 0.004 × 0.9999/iter, 하한 0.001 (ppo_cfg:149, 168, 177-178) |
| optimizer · 정밀도 | 보고서에 없음 (microbatch 512 는 적음, 88) | Muon · bf16 (300) | Muon · bf16 (ppo_cfg:84-89) |
| 학습 길이 | 500 ~ 2000 iteration (154, 222, 250) | 5000 목표, 21:18 기준 2466 (19, 300) | 5000 (ppo_cfg:150) · 공개 run 3000 설정 · 2400 체크포인트 (agent.yaml:4 · models.md:1) |
| 보상 | Table I 복원 뒤 Go2 보조 항: 진척 20 점/m, yaw 진척 4 점/rad, 근처 기울기 -500, approach_overspeed -2, 도착 보너스 5, 유지 보너스 10, 위치 · 방향 보상을 전 구간 연속 초당 5 · 2.5 (181, 225-229). 보고서 스스로 「논문 Table I 이 아니다」 (383) | 21개 보상 (300) | 23항 = Table I 21항 + humanoid optional 2 (cfg:412-570). 21 은 optional 2개를 뺀 수와 같다 (`계산`, 이식본 코드는 안 봄) |
| 위치 보상 진단 | 「마지막 4초에 거리와 무관하게 양수라 1 m 떨어져 서 있어도 약 80점」 (170) | | 코드 식 `100 × 1/(1+(d/2)²)` 를 4 s 적분하면 d = 1 m 에서 80 (rewards.py:219-236, `계산`). 보고서 진단과 같은 식 |
| 지형 | 부록 A 12종을 Go2 크기로, 40열, 오르기 · 내리기 상한 0.40 m (95). v7~v14 는 평지 (103, 365) | 공개 12종 (300) | 12종 · 10행 × 60열 · 12 m · climb_up 0.65 m · climb_down 0.88 m (G1) (terr:14-288) |
| 지형 curriculum | 평지 판은 거리 단계, 승급 조건 move ≥ 0.8 · pose ≥ 0.8 · turn ≥ 0.6 · 물리 실패 ≤ 2 % 두 번 연속 (196) | 보고서에 없음 | 목표 < 0.5 m 그리고 성공 EMA > 0.5 승급, > 4 m 강등 (mdp/curriculums.py:292-327) |
| DR | payload ±5 kg · 마찰 0.3~1.0 · PD 지연 0~20 ms · 지도 잡음 ±0.05 m · drift ±0.03 m (96). 평지 판은 `robustness=0` (103) | 보고서에 없음 | 마찰 0.3~1.0 · torso -1~+3 kg · CoM · Kp/Kd/armature ×0.85~1.15 · 지연 0~5 ms · 지도 z 잡음 0 → 0.05 · drift ±0.04 · push 없음 (1.10절) |
| 링크 접촉 | 19개 링크 접촉 센서 (97) | 보고서에 없음 | 질량 > 0.1 kg 링크 (G1 26개) (cfg:206-215 · mdp/symmetry.py:195) |
| 조기 종료 | 기울기 · 몸통 충돌 · 허벅지 급가속 · 정체 (313) | 「native early termination」 유지 (385) | 같은 4종, 문턱은 1.8절 (cfg:577-613) |
| 평가 | 1040판 평지 · 성공 = 0.2 m · 15° · 5 s 유지 (310-312) | 같은 1040판에 넣을 계획 (300) | 저장소에 평가 하네스 없음. 학습 중 로그는 성공 EMA · 지형별 레벨 (mdp/curriculums.py:329-380) |
| student · Mapper | 착수 전 (99-101) | 「학생 · 실센서 neural mapping 은 구현 아님」 (101) | student task · LSIO · PPO_IL 코드 있음. mapping 모델 · teacher JIT 이 빠져 있어 그대로는 못 돈다 (livox_neural_map_sensor.py:51-53, 379) |

---

## 3. wty-yy/go2_rl_gym · wertyuilife2/go2_rl_robotlab (MoE-CTS)

> 하위 조사 세션이 읽은 결과를 옮겼다. 이 조사 세션이 다시 연 것: go2_rl_gym `legged_gym/envs/__init__.py:1-15`(등록 · 어느 config 파일을 import 하는지) · `go2_config.py:33-36, 100-110, 140-145, 275-283` · robotlab `env_cfg.py:160-163, 468-470` · `rsl_rl_cfg.py:74-77` · `mdp/commands.py:19-22`. 「밖 코드」 는 우리 로컬 Isaac Lab v2.3.2 소스(`C:/isaac/IsaacLab`)로 읽은 Isaac Lab 동작이고, robotlab 이 요구하는 pip 2.3.2.post1 과 같은 소스인지는 `미확인`.

### 3.1 무엇을 주는가

- **go2_rl_gym** (Isaac Gym 판): unitree_rl_gym 위에 쌓은 Go2 학습 코드. CTS 변종 일곱 개(`go2` · `go2_cts` · `go2_moe_cts` · `go2_moe_ng_cts` · `go2_mcp_cts` · `go2_ac_moe_cts` · `go2_dual_moe_cts`), MuJoCo sim2sim, unitree_sdk2_python 실기 배포 스크립트. README 가 **`go2_moe_cts` 를 「the paper's final version」** 이라고 적는다 (`README 주장` README.md:35). 등록은 `go2_config.py` 의 클래스를 쓴다(같은 폴더의 `go2_config_vanilla*.py` · `go2_config_fast_flat_move.py` 는 등록되지 않음) (`코드 확인` legged_gym/envs/__init__.py:4, 9-15).
- **go2_rl_robotlab** (Isaac Lab 판): 같은 MoE-CTS 를 Isaac Lab 2.3.2 + robot_lab + 수정 rsl_rl 3.3.0 으로 옮긴 「reproduction」 (`README 주장` README.md:21). 학습 · play · JIT/ONNX 내보내기 · MuJoCo sim2sim. 실기 배포 코드는 없다.

### 3.2 메타

| 항목 | go2_rl_gym | go2_rl_robotlab |
|---|---|---|
| SHA · 마지막 커밋 | `30e74dc507bec7a642a8c98be26081f2c6f0822d` · 2026-07-06 | `28b4516d22617b11aeaf8ead63cc00b0c0bcd1bd` · 2026-06-29 |
| 논문 | 「Toward Reliable Sim-to-Real Predictability for MoE-based Robust Quadrupedal Locomotion」 arXiv 2602.00678 · RSS 2026 (README.md:4, 191-196 · arXiv v4 2026-05-10) | 같은 논문 (README.md:6-11) |
| 라이선스 | 새 기여분 MIT, 원 unitree_rl_gym 부분 BSD-3 | 루트 Apache-2.0, 동봉 rsl_rl 헤더 BSD-3 |
| 시뮬레이터 | Isaac Gym (판 표기 없음) (doc/setup_en.md:59-74) | `isaaclab[isaacsim,all]==2.3.2.post1` (`README 주장` README.md:98) |
| Python · torch | 3.8 · 2.3.1 cu12.1 (doc/setup_en.md:38, 56) | 3.11 · 2.7.0 cu128 (README.md:95, 99) |
| OS | Ubuntu 18.04+ 권장 (doc/setup_en.md:5) | 표기 없음. train.py 주석이 「Windows DLL loader conflicts」 회피로 h5py · tensordict 를 먼저 import 한다고 적음 (scripts/rsl_rl/train.py:17-20). 주석일 뿐 |
| 대표 task | `go2_moe_cts` = Go2Robot + GO2Cfg + GO2CfgMoECTS (legged_gym/envs/__init__.py:11) | `RobotLab-Go2-v0` = Go2Env + Go2EnvCfg + MoECTSRunnerCfg (source/robot_lab/robot_lab/tasks/go2/__init__.py:44-53) |
| 동봉 RL 라이브러리 | rsl_rl 1.0.2 수정판 (rsl_rl/setup.py:4) | rsl-rl-lib 3.3.0 수정판 (source/rsl_rl/pyproject.toml:7) · robot_lab 2.3.0 |

약어: gym 쪽 `gcfg` = `legged_gym/envs/go2/go2_config.py` · `genv` = `legged_gym/envs/go2/go2_env.py` · `gbase` = `legged_gym/envs/base/legged_robot_config.py` · `grob` = `legged_gym/envs/base/legged_robot.py` · `gmoe` = `rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py`. robotlab 쪽 `L/` = `source/robot_lab/robot_lab/tasks/go2/` · `lmoe` = `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py`.

### 3.3 명령: **속도형 (heading 없음)**

| 항목 | go2_rl_gym | go2_rl_robotlab | 우리 기준선 |
|---|---|---|---|
| 형식 | (vx, vy, wz), 버퍼 4칸 중 관측엔 3칸 (gcfg:100 · genv:28) | (vx, vy, wz) (L/mdp/commands.py:57) | 속도 명령 |
| heading | **끔** `heading_command=False` (gcfg:102, 이 조사 세션 재확인) | 「Remove heading command」 (L/mdp/commands.py:21, 재확인) | `heading_command=True` · `rel_heading_envs=1.0` |
| 시작 범위 | vx [-0.5, 0.5] · vy [-0.5, 0.5] · wz [-1.0, 1.0] (gcfg:142-144, 재확인) | 같음 (L/mdp/commands.py:429-433) | (0.4, 1.5) · (0, 0) · (-1, 1) |
| iteration 기반 범위 curriculum | iter 20,000 부터 vx ±1.0 · vy ±1.0 · wz ±1.5, iter 50,000 부터 vx ±2.0 · vy ±1.0 · wz ±2.0 (gcfg:111-123 · grob:423-436) | 같음 (L/mdp/commands.py:369-379, 128-140) | 표에 없음 |
| 지형별 상한 | wave · slope · rough: vx ±1.5 · vy ±1.0 · wz ±1.5 / stairs · obstacles · stones · gap: vx ±1.0 / flat: vx ±2.0 · wz ±2.0. 현재 범위와 교집합 (gcfg:129-139 · grob:859-886) | 같은 값 (L/mdp/commands.py:381-416) | 표에 없음 |
| 재추출 | **5 s** (gcfg:101, 재확인) | 5 s (L/mdp/commands.py:417-418) | (10, 10) s |
| 정지 | 확률을 iter 0 ~ 1500 동안 0 → 0.1. 정지 env 의 20 % 는 wz 를 범위 끝값으로 (gcfg:104-105 · grob:546-573) | 같음 | `rel_standing_envs=0.1` |
| 극값 명령 | 20 % 확률로 {min, max} 조합, 연속 두 번이면 부호 반전 (gcfg:106-108 · grob:502-543) | 같음 | 표에 없음 |
| 하한 동적 추출 | `dynamic_resample_commands=True`: 남은 거리(5 m)를 남은 시간에 채울 속도를 하한으로 [min, -하한] ∪ [하한, max] 에서 추출 (gcfg:110 · grob:437-467) | 같음 | 표에 없음 |
| iteration 계산 | `common_step_counter // 24` (24 고정) (grob:58, 162, 424) | `// num_steps_per_iter(24)` | 표에 없음 |

### 3.4 관측

| 항목 | go2_rl_gym | go2_rl_robotlab | 우리 기준선 |
|---|---|---|---|
| actor 한 프레임 | 각속도 × 0.25 (3) · 중력 (3) · 명령 × [2, 2, 0.25] (3) · 관절각 (12) · 관절속도 × 0.05 (12) · 직전 행동 (12) = **45** (genv:26-32 · gcfg:34) | 같은 6항목 = 45, 명령 scale **1.0** (L/env_cfg.py:122-160) | 235 |
| 이력 | **5** 프레임, 프레임 순 225 (gbase:310 · rsl_rl/rsl_rl/runners/on_policy_runner_cts.py:98-157) | **10** 프레임, 항목 순 450 (L/env_cfg.py:162, 재확인) | 표에 없음 |
| actor MLP 입력 | latent 32 + 현재 관측 45 = 77 (gmoe:46) | 같음 (lmoe:89-92) | 표에 없음 |
| critic · privileged | **263** = 선속도 × 2 (3) + actor 45 + 발 접촉력 노름 (4) + τ / τ_limit (12) + 관절속도 차분 / dt × 1e-4 (12) + height 187. 코드 주석의 263 과 맞음 (genv:36-47 · gcfg:36) | **275** (`계산`) = 선속도 3 + 각속도 3 + 중력 3 + 명령 3 + 관절각 12 + 관절속도 12 + 행동 12 + 관절 가속도 12 + 토크 12 + 발 접촉력 16 + height 187 (L/env_cfg.py:168-230). 총 차원 상수가 코드에 없어 대조값 없음 | 235 |
| height scan | x -0.8 ~ 0.8 · y -0.5 ~ 0.5 · 0.1 m → 17 × 11 = **187**, yaw 정렬, `clip(base_z − 0.5 − h, -1, 1) × 2.5` (gbase:26-27 · grob:1160-1197 · genv:34) | GridPattern 0.1 · [1.6, 1.0] → 187 (밖 코드 patterns.py:45-46 로 `계산`), clip ±1 · × 2.5 | 187 |
| height 를 받는 쪽 | **teacher encoder 와 critic 만. actor 관측에는 없다** (genv:26-47) | critic 그룹에만 (L/env_cfg.py:225) | 표에 없음 |
| 잡음 (actor 만) | 각속도 원값 ±0.2 · 중력 ±0.05 · 관절각 ±0.01 · 관절속도 원값 ±1.5 (genv:9-21) | 각속도 ±0.2 · 중력 ±0.05 · 관절각 **±0.03** · 관절속도 **±2.0** (L/env_cfg.py:124-160) | 표에 없음 |
| 정규화 · clip | 고정 scale · ±100 | `actor/critic_obs_normalization=False` · 항목마다 ±100, height ±1 | 표에 없음 |

### 3.5 행동 · 제어

| 항목 | go2_rl_gym | go2_rl_robotlab | 우리 기준선 |
|---|---|---|---|
| 형식 · scale | 관절 위치 목표 P 제어 τ = Kp(0.25a + q_default − q + zero_offset) − Kd·q̇ · 0.25 (gcfg:79-83 · grob:607-612) | JointPositionAction · 0.25 (L/env_cfg.py:110-117) | 표에 없음 |
| Kp / Kd | **20.0 / 0.5** (gcfg:80-81) | **25.0 / 0.5**, 관절 friction 0.01. `GO2_CFG_UNITREE` 사용 (Kp 20 인 `GO2_CFG_ROBOTLAB` 은 정의만) (L/env_cfg.py:63 · source/robot_lab/robot_lab/assets/unitree.py:72-150) | 표에 없음 |
| 토크 한계 | URDF clip: hip · thigh 23.7, calf 35.55 N·m (resources/robots/go2/urdf/go2.urdf:170-174, 280-284) | Unitree T-N 곡선: 같은 방향 20.2 · 반대 23.4 N·m, 13.5 rad/s 넘으면 선형 감소 30 rad/s 에서 0 (source/robot_lab/robot_lab/assets/unitree_actuator.py:238-289) | 표에 없음 |
| dt · decimation | 0.005 · 4 → 50 Hz | 0.005 · 4 → 50 Hz (L/env_cfg.py:483-486) | 표에 없음 |
| 기본 자세 · 초기 높이 | hip ±0.1 · thigh 0.8 / 1.0 · calf -1.5 · z 0.42 | 같은 자세 · z 0.40 + reset 때 0 ~ 0.2 | 표에 없음 |
| 에피소드 · 종료 | 25 s · base 접촉 > 1 N 또는 시간 초과 | 25 s · base illegal_contact 또는 time_out | 표에 없음 |

### 3.6 신경망 (RNN · CNN · attention 없음, MLP 와 MoE 만)

| 항목 | go2_rl_gym | go2_rl_robotlab |
|---|---|---|
| teacher encoder | MLP 263 → 512 → 256 → **32**, ELU, L2Norm (gmoe:44, 53-56 · gbase:315-319) | 275 → 512 → 256 → 32, ELU, L2Norm (lmoe:96-99) |
| student encoder (MoE) | **전문가 8** (gcfg:277, 재확인). 입력 225, 공유 trunk 225 → 512 → 256, 이어 256 → 2048 (= 8 × 256) + ELU, groups=8 Conv1d 로 전문가마다 256 → 32. 「공유 2층 + 전문가별 256 → 256 → 32」 와 같다 (rsl_rl/rsl_rl/modules/utils.py:69-151) | 같은 구조, 입력 450 (source/rsl_rl/rsl_rl/networks/moe.py:112-137) |
| gating | top-k 없는 dense softmax, MLP 225 → 512 → 256 → 8 (rsl_rl/rsl_rl/modules/utils.py:116-120) | dense softmax, 450 → 512 → 256 → **256** → 8 (moe.py:159-163) |
| actor | 77 → 512 → 256 → 128 → 12, ELU (gmoe:69) | 같음 (lmoe:118) |
| critic | (32 + 263) → 512 → 256 → 128 → 1, latent detach (gmoe:47, 72, 139) | (32 + 275) → 512 → 256 → 128 → 1 (lmoe:131, 245) |
| action std | 상태 무관 파라미터, 초기 1.0 | scalar 초기 1.0 |
| teacher-student | **CTS 동시 학습 한 단계.** env 의 75 % teacher (index mod 4 ≠ 0), 25 % student. 같은 actor 가 teacher env 에서는 teacher latent, student env 에서는 student latent(no_grad)로 움직인다. surrogate = teacher 평균 + student 평균 (rsl_rl/rsl_rl/algorithms/moe_cts.py:96-100, 166-168 · gmoe:114-122) | 같음 (source/rsl_rl/rsl_rl/algorithms/moe_cts.py:124-130, 320-322) |
| distillation loss | student env 표본에서 MSE(teacher latent no_grad, student latent) + 0.01 × load balance (= mean((평균 gating − 1/8)²)). student 전용 Adam lr 1e-3 고정, PPO minibatch 재사용 (moe_cts.py:82, 197-221) | 같음 (moe_cts.py:101, 393-412) |

### 3.7 학습

| 항목 | go2_rl_gym | go2_rl_robotlab | 우리 기준선 |
|---|---|---|---|
| PPO | lr 1e-3 adaptive (1e-5 ~ 1e-2, ×/÷ 1.5) · desired_kl 0.01 · entropy 0.01 · clip 0.2 · γ 0.99 · λ 0.95 · 24 step · 4 mini-batch · 5 epoch · max_grad_norm 1.0 · value coef 1.0 · clipped value loss (gbase:323-342) | 같음 (L/rsl_rl_cfg.py:53-75) | 표에 없음 |
| num_envs | **8192** (gcfg:33, 재확인). cmd.md:10 학습 명령은 `--num_envs 8096` | **16384** (L/env_cfg.py:469, 재확인) | 표에 없음 |
| max_iterations | **150,000** (gcfg:282, 재확인). UPDATE.md 에 120k · 150k 둘 다 나옴 | **300,000** (L/rsl_rl_cfg.py:76, 재확인) | 표에 없음 |
| 공개 체크포인트 | 137k · 164k (README.md:63, 71 · deploy/pre_train/go2/) | 176k (deploy/pre_train/go2/go2_moe_cts_176k_0.6984.pt · .onnx) | 표에 없음 |
| 시드 | 0 (gbase:308) | runner cfg 에 없음 → isaaclab_rl 기본 42 (밖 코드) | 표에 없음 |
| 학습 시간 · GPU | MoE-CTS 표기 없음. 초기 PPO 계단 학습 7h13min (UPDATE.md:176) | 「AMD EPYC 7763 and RTX 4090」 에서 500 iteration 학습 · 저장 약 30분 (`README 주장` README.md:158) | 표에 없음 |
| 다중 GPU | horovod 인자 정의만 | `--distributed`, torch.distributed **nccl** | 표에 없음 |

### 3.8 보상

gym: 0 이 아닌 scale 에 dt 0.02 를 곱하고 curriculum 배수는 그 뒤에 곱한다 (grob:902-909, 261-262). `only_positive_rewards=False` (gcfg:158). gym 의 `class scales:` 는 부모 없이 새로 정의돼 base scale 을 물려받지 않는다 (gcfg:177). lab: RewardManager `func × weight × dt` (밖 코드 reward_manager.py:150), curriculum 은 weight 자체를 바꾼다.

| 항목 | go2_rl_gym | go2_rl_robotlab |
|---|---|---|
| 선속도 추적 | 1.0, exp(-err/σ), σ 0.25 에 **dynamic sigma** (gcfg:166-178 · grob:1288-1322) | **2.0**, std 0.5 고정 |
| 각속도 추적 | 0.5 | **1.0**, std 0.5 |
| lin_vel_z | -2.0, 배수 1 → 0 (iter 0 ~ 1500) | 같음 |
| ang_vel_xy | -0.05 | -0.05 |
| 관절 가속도 | -2.5e-7 | **-1.0e-7** |
| 관절 power · torque | -2e-5 · -1e-4 | 같음 |
| base 높이 | -1.0, 배수 1 → 10 (iter 0 ~ 5000), 목표 0.38 m, 지면 = 0.4 × 0.3 m scan 평균 | -1.0 → -10.0, 목표 0.38 |
| action_rate · smoothness | -0.01 · -0.01 (aₜ − 2aₜ₋₁ + aₜ₋₂) | 같음 |
| 충돌 | -1.0, thigh · calf > 0.1 N | -1.0, **5.0 N** |
| 관절 한계 | -2.0, soft 0.9 | 같음 |
| feet_regulation | -0.05, Σ‖v_xy‖² · exp(-h_foot / (0.025 × 0.38)) | 같음 |
| hip 기본자세 | -0.05 | -0.05 |
| thigh · calf 기본자세 | 없음 | **-0.01** |
| 없는 항 | termination · feet_air_time · orientation · dof_vel · stand_still 은 scales 에 없음 | feet_air_time · termination · flat_orientation 없음 |

### 3.9 지형 · curriculum

| 항목 | go2_rl_gym | go2_rl_robotlab | 우리 기준선 |
|---|---|---|---|
| 비율 | wave 0.05 · slope 0.20 (절반 음의 경사) · rough_slope 0.05 · stairs_up 0.25 · stairs_down 0.10 · obstacles 0.20 · stones 0 · gap 0 · flat 0.15 (gcfg:91 · legged_gym/utils/terrain.py:111-153) | wave 0.05 · slope_up 0.10 · slope_down 0.10 · rough 0.05 · stairs_up 0.25 · stairs_down 0.10 · obstacles 0.20 · flat 0.15 (L/mdp/terrains.py:183-257) | 표에 없음 |
| 크기 | 10행 × 20열, 8 × 8 m, border 25 m, trimesh | 10 × 20, 실제 8 m | 표에 없음 |
| 난이도 | 행/10 이산 0 ~ 0.9. slope 0.1 + 0.52d (최대 29.6°) · 계단 0.05 + 0.23d (0.257 m), 폭 0.31 · 장애물 0.05 + 0.25d (0.275 m) | 연속 0 ~ 1.0, 상한이 gym 의 d = 0.9 값과 같음 (`계산`) | 표에 없음 |
| 초기 레벨 | `max_init_terrain_level=5` (gcfg:88) | 5 (L/env_cfg.py:46) | **2** |
| 승급 · 강등 | 에피소드 중 원점에서 **최대** 거리 > 4 m 면 승급, < ‖Σ명령 xy‖ × 5 s × (1 − 정지 확률) × 0.5 면 강등, 최고 레벨 너머는 무작위 (grob:125, 1142-1155) | 같음 (L/mdp/curriculums.py:199-217) | 표에 없음 |

### 3.10 Domain randomization

| 항목 | go2_rl_gym | go2_rl_robotlab | 우리 기준선 |
|---|---|---|---|
| 마찰 · 반발 | [0.0, 2.0] · [0.0, 0.5], 64 bucket (gcfg:43-56) | 같음 (L/env_cfg.py:318-329) | 표에 없음 |
| 질량 | base +[-1, 1] kg · 링크 ×[0.9, 1.1] | 같음 | 표에 없음 |
| CoM | ±0.03 m | 같음 | 표에 없음 |
| Kp · Kd | ×[0.9, 1.1], reset | 같음 | 표에 없음 |
| 모터 영점 | ±0.035 rad | 같음 | 표에 없음 |
| 모터 강도 | 토크 ×[0.8, 1.2] | **없음** (README.md:262) | 표에 없음 |
| 지연 | step 마다 0 ~ 4 sim step (0 ~ 20 ms) (gcfg:75 · grob:71-77) | actuator 0 ~ 4 physics step | 표에 없음 |
| push | 4 s 마다 xy 선속도 U(±0.4), 각속도 U(±0.6) 로 **덮어씀** (gcfg:70-73 · grob:710-725) | 4 s · 같은 범위, Isaac Lab 함수는 현재 속도에 **더함** (밖 코드 envs/mdp/events.py:1065-1071) | `push_robot=None` |

### 3.11 배포

| 항목 | go2_rl_gym | go2_rl_robotlab |
|---|---|---|
| sim-to-sim | MuJoCo `deploy/deploy_mujoco/deploy_go2.py`, 0.002 × 10 = 50 Hz, Kp 20 / Kd 0.5, cmd_scale [2, 2, 0.25] (configs/go2.yaml:14-29) | MuJoCo `deploy/deploy_mujoco/deploy_go2.py`, Kp 20 / Kd 0.5 (학습은 25), cmd_scale [1, 1, 1], history 는 JIT 안 |
| sim-to-real | unitree_sdk2_python `deploy/deploy_real/deploy_real_go2.py`, rt/lowcmd, Kp 20 / Kd 0.5 하드코딩. **명령 scale [3.0, 2.0, 0.5] 로 학습의 [2.0, 2.0, 0.25] 와 다름** (deploy/deploy_real/configs/go2.yaml:22). yaml 이 가리키는 policy 파일은 저장소에 없음. C++ 은 외부 unitree_cpp_deploy | 실기 배포 코드 없음 (실기 영상은 `README 주장`) |
| 내보내기 | JIT (내부 history, 출력 `(action, (weights, latent))`) · ONNX opset 11 (입력 history 225) | JIT (입력 한 프레임 45, 내부 history 450) · ONNX opset 18 |
| 평가 연동 | RoboGauge 비동기, 500 iteration 마다 JIT 제출, task "go2_moe" | 같은 방식, task "go2_lab" |

### 3.12 두 판의 차이 (요약)

| 항목 | go2_rl_gym | go2_rl_robotlab |
|---|---|---|
| num_envs · max_iterations | 8192 · 150,000 | 16384 · 300,000 |
| 이력 | 5 · 프레임 순 225 | 10 · 항목 순 450 |
| actor 명령 scale | [2.0, 2.0, 0.25] | [1, 1, 1] |
| critic 차원 | 263 | 275 (`계산`) |
| actor 잡음 관절각 · 관절속도 | ±0.01 · ±1.5 | ±0.03 · ±2.0 |
| gating MLP | 512-256 | 512-256-256 |
| 모터 · Kp | 단순 PD · URDF clip · 20 | T-N 곡선 + friction · 25 |
| 모터 강도 DR | [0.8, 1.2] | 없음 |
| push | 덮어씀 | 더함 |
| 추적 보상 | 1.0 / 0.5, dynamic sigma | 2.0 / 1.0, std 0.5 |
| 충돌 문턱 | 0.1 N | 5.0 N |
| 지형 난이도 | 이산 0 ~ 0.9 | 연속 0 ~ 1.0 |
| 실기 배포 | 있음 (Python) | 없음 |

### 3.13 논문에 없고 코드에만 있는 것 (논문 대조함: arXiv 2602.00678 abs · HTML v4, WebFetch 요약을 거침)

맞는 것: Isaac Gym · 8192 agents · 50 / 200 Hz · kp 20 / kd 0.5 · MoE 입력 이력 5 · base 높이 0.38 m · σ 초기 0.25 · 보상 Table IX 다중 지형 가중치 · Table X 지형별 명령 상한 · Table XI 명령 curriculum (0 · 2×10⁴ · 5×10⁴) · DR Table I 대부분 (질량 · CoM · 반발 · Kp/Kd · 모터 강도 · 영점 · 지연 0~20 ms) · 정지 10 % · 극값 20 % · 승급 4 m · 계단 5~25.7 cm · 장애물 5~27.5 cm · 경사 5.7°~29.6°.

다른 것: **마찰** 논문 [0.5, 1.5] 대 코드 두 판 모두 [0.0, 2.0] · **승급 거리** 논문 「final horizontal distance」 대 코드 에피소드 중 최대 거리 · hip symmetry 가중치 논문 -1 대 코드는 등록되지 않은 `go2_config_fast_flat_move.py:228` 에만 -0.5 · robotlab 의 이력 10 · Kp 25 · 모터 강도 DR 없음 · Isaac Lab 사용 · 추적 보상 식 표기(변환 문제일 수 있어 `미확인`).

논문 본문(요약)에서 찾지 못하고 코드에만 있는 것: 전문가 수 8 · latent 32 와 L2Norm · 모든 층 폭 · 공유 trunk + groups Conv1d 구조 · gating 깊이 · teacher env 비율 0.75 · student 전용 Adam 1e-3 · latent MSE · load balance 0.01 · PPO 하이퍼파라미터 전부 · 24 step · 150k iteration · 지형 비율과 20열 · slope_threshold · push · 관측 잡음 · scale · dynamic sigma 보간식 · 보상 curriculum · 동적 하한 명령 · 극값 연속 반전 · 에피소드 25 s · 재추출 5 s.

문서와 코드가 어긋나는 곳: UPDATE.md:97 은 지연 {0, 5, 10, 15} ms, 코드는 0 ~ 20 ms (grob:72). README 표 체크포인트(0.6713)는 「self-collision disabled」 로 학습됐다고 적지만 현재 코드는 self-collision 을 켰고 slope_threshold 도 2026-04-19 에 0.75 → 1.5 로 바뀌었다 (UPDATE.md:1-3). 현재 코드 설정은 README 표 체크포인트의 학습 조건과 같지 않다(문서 기준).

### 3.14 우리 기계 요구사항 대조

| 요구 | go2_rl_gym | go2_rl_robotlab | 우리 환경 |
|---|---|---|---|
| OS | Ubuntu 18.04+ | 표기 없음 (Windows DLL 주석만) | Windows 11 |
| 시뮬레이터 | Isaac Gym | isaaclab 2.3.2.post1 + isaacsim | Isaac Lab 로컬 2.3.2 · isaacsim 5.1.0.0 |
| Python · torch | 3.8 · 2.3.1 cu12.1 | 3.11 · 2.7.0 cu128 | 3.11.15 · 2.7.0+cu128 |
| RL 라이브러리 | 동봉 rsl_rl 1.0.2 | 동봉 rsl-rl-lib 3.3.0 (최소 3.0.1 검사) | rsl-rl-lib 3.1.2 |
| 그 밖 | numpy==1.20 · tensorboard==2.14.0 · mujoco==3.2.3 · onnx==1.17.0 | pinocchio · cusrl[all] · xacrodoc · pandas · tensordict ≥ 0.7 · onnxscript ≥ 0.5.4 | numpy 1.26.0 · tensordict 0.13.0 · onnx 1.22.0 · onnxscript 0.7.1. mujoco · pinocchio · cusrl 없음 (하위 세션이 dist-info 로 확인) |
| 컴파일 | 저장소에 .c · .cpp · .cu · CMake 없음 | 같음 | nvcc · MSVC 없음 |
| 다중 GPU | 미확인 | nccl | GPU 2장. Windows 의 nccl 가능 여부 `미확인` |

### 3.15 못 본 것 (이 절)

- 실행 · 설치 · 학습 없음. 동봉 체크포인트(.pt · .onnx) 미열람(현재 코드 설정으로 학습됐는지 `미확인`).
- robotlab critic 275 · 이력 450 의 실제 텐서 차원(상수가 코드에 없음). robotlab `obs_groups` 의 실제 해석 경로.
- Isaac Lab 쪽 동작은 로컬 2.3.2 사본으로만 봄. pinocchio · cusrl 의 Windows wheel. VRAM 요구량. gym 판 MoE-CTS 학습 시간.
- 논문 PDF 원문 직접 대조(WebFetch 요약이 「없음」 이라 한 항목은 놓쳤을 수 있다). 외부 저장소(unitree_cpp_deploy · Hugging Face 체크포인트).
- gym 변종 moe_ng · mcp · ac_moe · dual_moe 모듈 전체.

### 3.16 이 절의 가장 중요한 사실 다섯

1. 두 판의 구조는 같다: **CTS 동시 학습**(env 75 % teacher · 25 % student), teacher 는 privileged → 32차원 L2 정규화 latent, student 는 **8 전문가 dense softmax MoE**, actor 는 「latent + 현재 45」 → 512-256-128. student 는 latent MSE + 0.01 load balance 로 별도 Adam(1e-3). 이 숫자들은 논문 본문(요약)에서 찾지 못했다.
2. **actor 관측은 45차원 고유수용감각뿐**이다. height scan 187 (17 × 11) 은 teacher 와 critic 에만 들어간다.
3. 명령은 **heading 없는 (vx, vy, wz)**, 재추출 5 s, 시작 ±0.5 / ±0.5 / ±1.0 에서 iteration 20k · 50k 단계 curriculum, 지형별 상한, 정지 0 → 0.1, 극값 20 %, 남은 거리 기반 속도 하한.
4. gym 은 8192 env · 상한 150k iteration(공개 137k · 164k), robotlab 은 16384 env · 300k(공개 176k). PPO 값은 두 판이 같고 legged_gym 기본과도 같다(entropy 0.01 · 5 epoch · 4 mini-batch).
5. 같은 논문의 두 구현이지만 이력 5 대 10 · Kp 20 대 25 · 명령 scale · critic 263 대 275 · 추적 가중치 · 모터 강도 DR 이 다르고, **마찰 DR 은 두 판 모두 [0, 2] 로 논문 [0.5, 1.5] 와 다르다.**

---

## 4. wty-yy/RoboGauge

> 하위 조사 세션이 읽은 결과를 옮겼다. 이 조사 세션이 다시 연 것: `robogauge/tasks/robots/go2/go2.py:38-74`(관측 · 행동) · `go2_config.py` 의 `control_dt` · `num_observations` · `mj2model_dof_indices` · `mujoco_simulator.py:33-39`(MuJoCo 판 상한).

**무엇을 주는가**: MuJoCo 3.2.3 으로 Unitree Go2 보행 정책(TorchScript)을 평가하는 도구. 7개 지형(평지 + 난이도 1~10 지형 6종)에서 정해진 속도 명령 시퀀스를 주고, 0.1 s 마다 정규화 지표 8개를 재서 가중 기하평균으로 점수를 낸다. **평가기가 정책에 주는 관측은 45차원 고유수용감각뿐이고 height scan · base 선속도는 없다.** 학습 코드는 없다.

### 4.1 메타

| 항목 | 값 | 근거 |
|---|---|---|
| SHA · 마지막 커밋 | `add2c7ee0185ea8fd93d242f86e1c8cac6e9913b` · 2026-10-05 「v1.1.9」 | `git log` |
| 라이선스 | MIT | `코드 확인` LICENSE:1 · pyproject.toml:11 |
| 논문 | 「Toward Reliable Sim-to-Real Predictability for MoE-based Robust Quadrupedal Locomotion」 RSS 2026 · arXiv 2602.00678 (go2_rl_gym 과 같은 논문). 프로젝트 페이지 robogauge.github.io/complete/ | `README 주장` README.md:255-264 · arXiv abs |
| 지원 로봇 | Go2 하나 | `코드 확인` robogauge/tasks/__init__.py:22-67 |
| 시뮬레이터 | MuJoCo + dm_control mjcf 로 지형 · 로봇 XML 합성. **`mujoco==3.2.3`, 3.3.0 이상이면 RuntimeError** (접촉 동역학 차이) | `코드 확인` pyproject.toml:31 · mujoco_simulator.py:33-51 |
| Python · 의존성 | 런타임 ≥ 3.8, < 3.12 · 래퍼는 uv 의 3.11 · dm-control==1.0.23 · torch==2.4.1+cu124 · numpy<2 · pillow<10 · matplotlib==3.6.3 · fastapi · uvicorn 등 | `코드 확인` pyproject.toml:10, 25-59 · robogauge.sh:18-22 |
| GPU | 정책 추론은 CPU (`torch.jit.load(...).to('cpu')`). README 시험 환경은 CPU 64 프로세스 | `코드 확인` go2_config.py:23 · base_robot.py:30 · `README 주장` README.md:248 |
| OS | 명시 없음. bash 래퍼, `$ENV/bin/python` 검사. server.py 는 MUJOCO_GL=glfw 고정 | `코드 확인` robogauge.sh:51 · robogauge/scripts/server.py:18 |

### 4.2 지표 (metric_dt 0.1 s 마다, sim 50 step 마다 한 번: base_gauge.py:139-148)

| 지표 | 정의 | 근거 (`코드 확인`) |
|---|---|---|
| lin_vel_err | 1 − ‖v_base − [vx*, vy*, 0]‖ / ‖[max\|vx\|, max\|vy\|]‖ (Go2 는 √2) | vel_metrics.py:23-43 |
| ang_vel_err | 1 − ‖ω_base − [0, 0, wz*]‖ / max\|wz\| (평지 2.0, 지형 1.5) | vel_metrics.py:49-69 · go2_config.py:57, 64 |
| dof_limits | soft 한계(r = 0.4, hip · thigh 만) 초과량 / range 의 RMS 를 1 에서 뺌 | dof_metrics.py:32-67 · go2_flat_task.py:15-18 |
| dof_power | 1 − RMS_j(\|τ·q̇\|) / 100 W | dof_metrics.py:81-93 |
| orientation_stability | 1 − \|g_y\| (roll 만) | stable_metric.py:29-34 |
| torque_smoothness | 1 − RMS(τ_t − τ_prev) / 30 N·m (간격 0.1 s) | stable_metric.py:52-62 |
| friction_margin | 발마다 1 − ΣF_t / Σ(μF_n), F_n > 5 N 발만, F_n 가중평균 | stable_metric.py:92-173 |
| zmp_margin | 다물체 ZMP 와 지지 접촉점 평균 거리로 max(0, 1 − ‖zmp‖/d) | stable_metric.py:302-378 |
| step 품질 | 가중 기하평균, 가중치 lin · ang 각 2, 나머지 6개 각 1 | base_goal.py:49-61 · base_gauge_config.py:12-21 |
| goal 집계 | mean · mean@25 · mean@50 (하위 25 % · 50 % 평균) | base_goal.py:70-83 |
| 지형 점수 | 평지 q, 레벨 지형 0.09 · (L − 1) + 0.19 · q | base_gauge.py:154-173 |
| 최종 점수 | 지형마다 마찰 × 질량 조건별 지형 점수 mean@50 의 평균, `benchmark_score` 는 지형 7개 평균 | stress_pipeline.py:219-243 |

판정: 기울기 > 2.5 rad 면 낙상(그 goal 의 남은 sub-goal 건너뜀, run 은 'error') (mujoco_simulator.py:455-459). 관통(dist < -0.035 m)은 goal 재시작 · 경고, run 당 1회 (mujoco_config.py:49-55). 레벨 통과는 목표 0.1 m 안 도달, 탐색 시드 0~4 의 성공 평균 ≥ 0.8, 1~10 이진 탐색 (level_pipeline.py:38-50, 74-75). README.md:233 의 「세 시드 모두 통과」 와 다르다.

### 4.3 평가 시나리오

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 지형 | flat · slope_fd · slope_bd · wave · stairs_fd · stairs_bd · obstacle (`_bd` 는 초기 yaw 180°, 후진 등반) | `코드 확인` terrain_levels_config.py:12-21 | 표에 없음 |
| 경사 L1~L10 | 8.36° ~ 29.68° | `코드 확인` resources/terrains/slope/slope_N.xml:2 | 표에 없음 |
| 계단 L1~L10 | 단 높이 0.08 ~ 0.23 m, 디딤 0.31 m | `코드 확인` stairs_N.xml:2 | 표에 없음 |
| wave · obstacle | 진폭 0.02 ~ 0.20 m · 높이 0.073 ~ 0.28 m | `코드 확인` wave_N.xml:2 · obstacle_N.xml:2 | 표에 없음 |
| 명령 (평가) | max_velocity: sub-goal 6개 [vx −1, vx +1, vy −1, vy +1, wz −, wz +], 각각 5 s + 정지 2 s. diagonal: (vx, vy) ∈ {−1, 0, 1}² 8개, 각 6 s 중 뒤 3 s 부호 반전 | `코드 확인` velocity_goals.py:46-53, 85, 96-163 | 학습 분포 vx (0.4, 1.5) · vy (0, 0) |
| wz | 평지 ±2.0 rad/s, 지형 ±1.5 rad/s | `코드 확인` go2_config.py:57, 61-64 | (-1, 1) · heading |
| 명령 (레벨 탐색) | 목표 위치를 속도로 변환: wz = sign(Δψ)·min(2\|Δψ\|, 1.5), vx 1.0 또는 0.8, 제한 시간 20~30 s | `코드 확인` velocity_goals.py:206-223 | 표에 없음 |
| push | 코드에서 못 찾음 | `코드 확인`(검색) | `push_robot=None` |
| 마찰 | 모든 geom friction[0] 덮어씀. 서버 stress 0.2 ~ 1.0 (9단계) | `코드 확인` mujoco_simulator.py:170-178 · server.py:48 | 표에 없음 |
| 질량 | base 추가 기본 [0], 서버도 0 (README 는 -1~3 kg) | `코드 확인` helpers.py:85 · `README 주장` README.md:129 | 표에 없음 |
| 지연 · 잡음 | action 을 sub-step 0~9 중 무작위 시점에 적용(0~18 ms) · gyro ±0.8 · q ±0.01 · q̇ ±3.0 | `코드 확인` mujoco_config.py:35, 41-47 · base_pipeline.py:102-159 | 표에 없음 |
| 반복 | 서버 stress = 7 지형 × 마찰 9 = 63 조건, 평가 시드 0 · 1 · 2, 탐색 시드 0~4 | `코드 확인` server.py:41-51 | 표에 없음 |

### 4.4 정책 입력 계약

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 관측 | **45** = gyro × 0.25 (3) · 중력 (3) · 명령 × [2, 2, 0.25] (3) · 관절각 (12) · 관절속도 × 0.05 (12) · 직전 행동 (12) | `코드 확인` go2.py:38-63 · go2_config.py:34, 49 | 235 (height scan 187) |
| height scan · base 선속도 | 없음 | `코드 확인`(검색) · go2.py:55-60 | 187 |
| 명령 처리 | 명령 범위로 clip 후 scale. `go2_lab` 계열은 scale [1, 1, 1] (Go2Lab131 은 [0.5, 1, 1]) · `go2_lab_pose` 는 1 s SE(2) 증분으로 변환 | `코드 확인` go2.py:47-53 · go2_lab_config.py:20, 33, 46 · go2_lab_pose.py:29-103 | 표에 없음 |
| 이력 | 평가기는 한 프레임만 준다. 리셋 때 `model.reset()` 을 부르므로 JIT 에 reset() 이 있어야 함 | `코드 확인` go2.py:65-67 | 표에 없음 |
| 행동 | MuJoCo 순서로 재배열 후 target = a × 0.25 + default, clip 없음 | `코드 확인` go2.py:69-74 | 표에 없음 |
| PD · 주기 | kp 20 (go2) · 25 (go2_lab), kd 0.5, 토크는 500 Hz 마다 · 정책 50 Hz · decimation 10. 토크 한계 hip · thigh ±23.7, calf ±45.43 | `코드 확인` go2_config.py:26, 31-32 · go2_lab_config.py:17 · mujoco_config.py:15-16 · go2.xml:10, 26 | 표에 없음 |
| 관절 순서 | MuJoCo: FL · FR · RL · RR × hip · thigh · calf (다리별). 변환 장치 `mj2model_dof_indices` 는 있지만 모든 설정에서 항등 [0..11] | `코드 확인` go2.xml:226-254 · go2_config.py:40 · go2_lab_config.py:13-51 | 표에 없음 |
| 정책 파일 | TorchScript 만 (ONNX 못 찾음). go2_moe 는 `(action, tuple)` 반환 가정 | `코드 확인` base_robot.py:30 · go2_moe.py:23-46 | 표에 없음 |

Isaac Lab 쪽 흔적(판단 없이): `go2_lab*` task 가 7 지형씩 등록돼 있고 (`코드 확인` robogauge/tasks/__init__.py:42-67), Go2LabConfig docstring 은 「aligned with RobotLab observation scaling」 (go2_lab_config.py:13-20), 스크립트가 `go2_rl_robotlab/logs/rsl_rl/.../exported/policy.pt` 를 `go2_lab` 로 평가한다 (scripts/run_models.sh:5-15). Isaac Lab 의 관절 순서로 바꾸는 설정은 코드에서 못 찾았다. 로컬 Isaac Lab exporter 는 `reset()` 을 `@torch.jit.export` 로 두고 forward 가 텐서를 돌려준다 (하위 세션이 우리 기계 `C:/isaac/IsaacLab/source/isaaclab_rl/isaaclab_rl/rsl_rl/exporter.py:100-105` 에서 읽음).

go2_rl_gym 과의 연결: 학습 쪽 `RoboGaugeClient.submit_task` 가 POST /submit_eval 로 서버에 넘기고 서버가 StressPipeline(7 지형 · 시드 0~2 · 마찰 0.2~1.0 · 30 프로세스 · 127.0.0.1:9973)을 돈다 (`코드 확인` client.py:39-134 · server.py:41-51, 100-185).

### 4.5 우리 기계 요구사항 대조

| 항목 | RoboGauge 요구 | 우리 환경 (하위 세션이 우리 기계에서 읽음) |
|---|---|---|
| OS | 명시 없음, bash · 리눅스 경로 | Windows 11 |
| Python | < 3.12, 래퍼 3.11 | isaac311 = 3.11 |
| MuJoCo · dm-control | ==3.2.3 · ==1.0.23 | isaac311 에 둘 다 없음 |
| torch | ==2.4.1+cu124 | 2.7.0+cu128 |
| numpy · pillow · matplotlib | <2 · <10 · ==3.6.3 | 1.26.0 · 11.3.0 · 3.10.3 |
| uv | 래퍼가 필요 | Git Bash PATH 에 없음 |
| GPU | 추론은 CPU | RTX 5080 × 2 |
| CPU 병렬 | 서버 기본 30 프로세스 | 논리 프로세서 64 |
| 렌더 | server.py glfw 고정 | Windows 에서 headless glfw 동작 `미확인` |
| 컴파일 | 저장소 안 빌드 단계 못 찾음 | nvcc · MSVC 없음. 하위 의존성 Windows wheel 유무 `미확인` |

### 4.6 못 본 것 (이 절)

- 아무것도 실행하지 않았다. 점수 · 통과 레벨 · Windows 동작 · glfw/EGL 동작 `미확인`.
- go2_rl_gym 의 `update_robogauge` 본문, 번들 .pt 의 data.pkl (텐서 모양 · 이력 길이).
- 논문 PDF 본문(지표 식이 논문과 같은지 대조 안 함). assets/docs/friction_margin.md · zmp_margin.md 본문.
- joystick_goal.py · visualization.py · logger.py 세부. dm-control · glfw 의 Windows · 3.11 wheel 유무.

### 4.7 이 절의 가장 중요한 사실 다섯

1. 평가기가 주는 관측은 **45차원 고유수용감각**(height scan · base 선속도 없음)이다. 이력은 JIT 안에 있어야 하고 `reset()` 이 필요하다 (go2.py:38-67).
2. Isaac Lab(RobotLab) 정책용 `go2_lab*` task 가 있지만 관절 순서 매핑은 모든 설정에서 항등이다. 매핑 장치는 있다.
3. 평가 명령은 vx · vy ±1 m/s, wz ±2.0 (평지) / ±1.5 (지형) rad/s, 5 s 이동 + 2 s 정지, 대각 3 s 반전이다.
4. 점수는 0.1 s 마다 8지표 가중 기하평균(속도 오차 가중 2) → 하위 50 % 평균 → 지형 7개 평균이다. push 는 없고 서버 DR 은 마찰 9단계 · action 지연 · 관측 잡음이다.
5. 실행 요구는 mujoco==3.2.3 (3.3.0 이상 거부) · torch 2.4.1+cu124 · Python < 3.12 · uv · bash 다. 정책 추론은 CPU 다.

---

## 5. ASIG-X/JEPLO

> 하위 조사 세션이 읽은 결과를 옮겼다. 이 조사 세션이 다시 연 것: README.md:1-46 (논문 · 설치 판) · `training/go2_parkour/go2_parkour/tasks/go2_loco_env_cfg.py:181-186, 246-262` (재추출 4 s · 관측 845 구성) · `go2_loco_env.py:150-158` (direct 명령 범위 · 0 확률) · `go2_loco_ppo_cfg.py` 의 epoch 10 · mini-batch 4 · entropy 0.01 · max_iterations 1500. 약어: `env` = `training/go2_parkour/go2_parkour/tasks/go2_loco_env.py` · `cfg` = 같은 폴더 `go2_loco_env_cfg.py` · `ppo` = 같은 폴더 `go2_loco_ppo_cfg.py` · `R/` = `training/rsl_rl/rsl_rl/`.

**무엇을 주는가**: Livox Mid-360 하나를 **뒤집어 단** Go2 의 perceptive locomotion 전체(학습 · MuJoCo sim-to-sim · Jetson 실기 C++). Isaac Lab **DirectRLEnv** 와 개조 RSL-RL. PPO(teacher-student 동시 학습, CTS)와 JEPA world model(LeJEPA SIGReg)이 **같은 iteration 안에서 따로 최적화**된다. LiDAR 입력은 point cloud 도 height map 도 아닌 **구면 depth(range) image**.

### 5.1 메타

| 항목 | 값 | 근거 |
|---|---|---|
| SHA · 마지막 커밋 | `460e2272907af053d6e66b57fec71fdbe6ca1774` · 2026-09-17 「Export ONNX models and test cases whenever checkpoints are saved」 | git log |
| 논문 | 「JEPLO: Joint-Embedding Predictive Learning for LiDAR-Based Legged Locomotion」 arXiv 2609.15770 (2026-09-14 제출, 8 pages, 학회 표기 없음) | `README 주장` README.md:1, 6, 15-20 |
| 라이선스 | GPLv3 (상업 이용 별도 문의). training/rsl_rl BSD-3, training/lejepa MIT. 군사 이용 반대 문구 | README.md:345 · LICENSE:1-2 · DISCLAIMER:14 |
| 시뮬레이터 | Isaac Lab DirectRLEnv, `isaaclab[isaacsim,all]==2.3.2.post1` | `README 주장` README.md:31 (재확인) · cfg:22, 159 |
| Python · torch | 3.11 (`>=3.10,<3.12`) · torch 2.7.0 / torchvision 0.22.0 cu128 | README.md:28, 32 (재확인) · training/go2_parkour/pyproject.toml:8 |
| 필수 의존 | 저장소 안 lejepa · rsl_rl 사본 `pip -e`. **wandb 필수** (`wandb_project` 없으면 ValueError) | README.md:38-46 · R/runners/on_policy_runner_teacher_cts.py:219-222 |
| OS · 하드웨어 | 학습 OS 명시 없음. sim-to-sim 은 Ubuntu 22.04. 실기 Jetson AGX Orin + Mid-360 + 3D 프린트 케이지. 학습 RTX 6000 Pro 1장 약 12시간 (논문 요약) | README.md:73, 95, 244 |
| 공개물 | model_15000.pt (64.7 MB) · policy.onnx · sensor_estimator.onnx · ONNX 검증 표본 | training/logs/rsl_rl/go2_loco/pretrained/ |
| 학습 경로 | `scripts/train.py` → task `Unitree-Go2-Locomotion` (등록 task 하나) → `Go2LocoEnv` · `Go2LocoEnvCfg` · `Go2LocoPPOCfg` → runner `OnPolicyRunnerTeacherCTS` → `TeacherCTS` · `ActorCriticTeacherCTS` · `JepaEstimatorSensorSS` | training/scripts/train.py:71, 93, 185 · tasks/__init__.py:6-14 |

### 5.2 명령: **속도형** (지형에 따라 waypoint 쪽으로 속도를 만드는 모드가 섞임)

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 형식 | body frame (vx, vy, wz). 지형에 따라 direct 모드와 waypoint 모드 | env:150-151, 687-692 | 속도 명령 |
| direct 모드 지형 | parkour_flat(거친 평지) · pyramid_stairs · inverted_pyramid_stairs · discrete_grid | env:55-60 | 표에 없음 |
| direct vx · vy | 크기 U(0.5, 1.0), 부호 ±50 %, 0 일 확률 vx 10 % · vy 25 % | env:154-156 (재확인), 1050-1064 | (0.4, 1.5) · (0, 0) |
| direct wz | U(-2, 2), 0 일 확률 50 % | 같음 | (-1, 1) |
| waypoint 모드 | gap · box · discrete_obstacles 지형. 다음 waypoint 방향, 속력 U(0.5, 1.0) (5 % 확률 0), wz = clip(yaw 오차, ±1), 0.5 m 안이면 다음 waypoint, 8개 | env:427-459, 997-1045 | 표에 없음 |
| heading | 별도 heading 입력 없음. `_cmd_heading_offset` 은 env:1103 에서 항상 0 으로 덮임 | env:1093-1103 | `heading_command=True` · `rel_heading_envs=1.0` |
| 정지 | direct 에서 세 성분이 모두 0 일 확률 0.1 × 0.25 × 0.5 = 1.25 % (`계산`). waypoint 는 속력 0 이 5 % | env:156, 1042-1045 | `rel_standing_envs=0.1` |
| 제자리 회전 | iteration ≥ 1000 부터 direct 재추출 때 20 % 확률로 lin 0 · wz U(-2, 2) | env:1068-1083 | 표에 없음 |
| 재추출 | **4.0 s** 고정 | cfg:183 (재확인) | (10, 10) s |
| 명령 curriculum | 명령 범위 curriculum 없음. `command_curriculum.py` 는 이름과 달리 direct 지형 레벨 승강 규칙 | tasks/command_curriculum.py:31-46 | 표에 없음 |

### 5.3 관측

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 벡터 구조 | 하나의 "policy" 벡터 **845** = proprio 이력 450 + 높이 맵 300 + privileged 50 + 잡음 없는 현재 proprio 45. depth 는 별도 키 (2, 25, 60) | cfg:248-262 (재확인) · env:642-671 | 235 |
| proprio 45 | 각속도 × 0.25 (3) · 중력 (3) · 명령 lin × 2.0 (2) · ang × 0.25 (1) · 관절각 (12) · 관절속도 × 0.05 (12) · 직전 행동 × 0.1 (12) | env:611-623 | 표에 없음 |
| 이력 | 10 step (0.2 s), newest first | cfg:248 · env:637-640 | 표에 없음 |
| teacher 높이 맵 | 0.1 m 격자 2.0 × 1.5 m → 20 × 15 = **300** (로컬 Isaac Lab 2.3.2 GridPattern 식으로 `계산`), base 앞 0.4 m offset, yaw 정렬, (hit z − base z) clip ±2 × 0.5, 잡음 없음 | cfg:212-219, 254 · env:579-582 | 187 |
| privileged 50 | 선속도 3 · 발 clearance 4 · 발 접촉 4 · 평지 one-hot 2 · 링크 19개 접촉력 크기 19 · 토크 12 · Kp 1 · Kd 1 · 마찰 · 반발 3 · base 질량 변화 1 | env:573-592, 649-658 | 표에 없음 |
| critic | 845 전체 | R/modules/actor_critic_teacher.py:73-76, 154-166 | 표에 없음 |
| actor | teacher: 현재 proprio 45 + encoder 64 × 3 = 237. student: 현재 proprio 45 + student encoder 192 = 237 (actor 공유) | actor_critic_teacher.py:68-72 · actor_critic_teacher_cts.py:151-161 | 표에 없음 |
| JEPA 입력 | proprio 이력 450 + depth (2, 25, 60) + GRU hidden 512, 5 step 마다 (10 Hz). metadata.json 기재값과 일치 | on_policy_runner_teacher_cts.py:153-160, 282-301 · pretrained/exported/test_cases/metadata.json:35-47 | 표에 없음 |
| LiDAR 표현 | **구면 depth image**: 고각 -4.5° ~ 45.5° 25 bin × 방위 ±60° 60 bin, 2° 간격, bin 당 최소 거리, 0.1 ~ 2.0 m → ÷2 로 [0, 1] | sensor/lidar_pattern.py:85-88 · spherical_depth_generator.py:195-302 | 표에 없음 |
| 센서 장착 · 패턴 | base 기준 (0.275, 0, 0.148) m, x축 180° (뒤집어 장착), 지면 mesh 만. **Mid-360 실제 스캔 패턴 파일(mid360.npy)을 env 별로 잘라 씀**, 갱신당 3000 표본 × FOV 비율, 갱신 50 Hz | cfg:232-241, 297 · livox_scan_generator.py:54-125 | 표에 없음 |
| LiDAR 잡음 · 결손 | 거리 σ 0.005 m · 아래 2행 dropout · 도형 가림 0~2개 · env 별 Perlin occlusion U(0, 0.4) · 원점 drift ±0.03 m | spherical_depth_generator.py:139-316 · env:209, 946-947 | 표에 없음 |
| 정규화 | empirical normalization 을 runner 가 강제로 끔 | on_policy_runner_teacher_cts.py:129-138 | 표에 없음 |

하위 세션이 코드 읽기로 찾은 이상 동작(실행으로 재지 않음): `_get_dones` 가 `_get_observations(pure=True)` 를 부르는데 `pure` 가 depth 갱신을 막지 않아(env:851, 595-598) 한 step 에 depth 갱신이 두 번 일어난다. 그 결과 10칸 ring 에 갱신 5개가 독립 잡음으로 두 번씩 들어가고, 명목 `depth_delay=1` 이 중복 push 로 소모돼 관측 2채널이 [직전 tick, 현재 tick] 이 된다. 호출 순서는 로컬 Isaac Lab v2.3.2 `direct_rl_env.py:389-410` 에서 확인. `SphericalDepthGenerator.reset()` 은 env 에서 호출되지 않는다.

### 5.4 행동 · 제어

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 행동 | 관절 위치 목표 = a × **0.25** + default + motor zero offset, clamp ±100 | env:469-474 · cfg:178-180 | 표에 없음 |
| 관절 순서 | FL · FR · RL · RR 순서로 hip → thigh → calf, 다르면 assert | env:62-88 | 표에 없음 |
| actuator | DelayedPDActuator 상속 「GO2HV」: Kp 25 · Kd 0.5 · friction 0.01, 지연 0~4 physics step (0~20 ms), T-N 곡선 X1 13.5 · X2 30 rad/s · Y1 20.2 · Y2 23.4 N·m | assets/unitree.py:142-150 · assets/unitree_actuator.py:14-129 | 표에 없음 |
| PD gain curriculum | reset 마다 덮어씀: iteration 5000 → 10000 동안 Kp 중심 25 → 30, Kd 0.5 → 1.0, 배율 ±10 % → ±30 %. 최종 Kp [21, 39], Kd [0.7, 1.3] | env:916-936 | 표에 없음 |
| 주기 | sim dt 0.005 · decimation 4 · 50 Hz | cfg:162, 165, 289 | 표에 없음 |
| 에피소드 · 종료 | 25 s. \|roll\| 또는 \|pitch\| > 1.5 rad, base z < -5 m. waypoint 8개 모두 도달도 time-out | cfg:161 · env:835-853 | 표에 없음 |

### 5.5 신경망

| 항목 | 값 | 근거 |
|---|---|---|
| actor | 237 → 512 → 256 → 128 → 12, ELU. 관절별 scalar std 초기 1.0 | ppo:33-38 · R/modules/actor_critic.py:38-75 |
| critic | 845 → 512 → 256 → 128 → 1, ELU | 같음 |
| teacher encoder | 이력 450 · 높이 300 · priv 50 각각 → 256 → 128 → 64, ELU, 출력 Tanh, 합 192. PPO 로 학습 | actor_critic_teacher.py:64-109 |
| student encoder | JEPA feature 512 → 512 → 256 → 128 (SiLU) · 이력 450 → 512 → 256 → 128 (SiLU) · fusion 256 → 512 → 256 · head 3개 Linear(256, 64) + Tanh → 192 | actor_critic_teacher_cts.py:20-92 |
| JEPA depth encoder | SmallViT: (2, 25, 60) 을 (2, 32, 64) 로 pad, patch (4, 8) → 64 token + CLS, embed 128 · block 6 · head 4 · MLP 비 2 (GELU) · pre-norm · QK-norm · 2D sin-cos 위치 → z_d 64 | R/modules/jepa_estimator_sensor_ss.py:25-270 |
| JEPA 나머지 | proprio encoder 450 → 512 → 256 → 32 · action 이력 60 → 256 → 128 → 32 · GRUCell(96 → 512) · predictor 544 → 512 → 256 → 64 (z_d), 544 → 512 → 256 → 32 (z_o) | jepa_estimator_sensor_ss.py:207-243 |
| target · EMA · masking | **없다.** target 은 같은 online encoder 의 z(t+1), detach 없음. collapse 방지는 SIGReg | jepa_estimator_sensor_ss.py:368-382 |
| JEPA loss | MSE(ẑ_d, z_d) + MSE(ẑ_o, z_o) + 0.1·SIGReg(z_d) + 0.1·SIGReg(z_o), SIGReg = EppsPulley 512 slice | jepa_estimator_sensor_ss.py:245-247, 345-382 |
| sensor_estimator 출력 | 높이 맵 · 속도 같은 물리량이 아니라 **GRU hidden 512 를 detach 해 정책 feature 로** | jepa_estimator_sensor_ss.py:256-296 |
| teacher-student | CTS: actor · critic 공유, student encoder 만 따로. student encoder 는 teacher latent (3 × 64, detach) 를 MSE 로 모방, PPO gradient 는 student encoder 로 안 감 | R/algorithms/teacher_cts.py:295-329 |
| 순서 | 단일 단계 동시: 매 iteration rollout → PPO → student encoder → JEPA. RL loss 는 JEPA 에 안 닿음 | on_policy_runner_teacher_cts.py:264-356 |
| student 비율 | warmup (A, B): A 전엔 teacher 만, A~B 동안 student env 0 → round(N × ratio), surrogate 가중 0 → 1. CLI 기본 (0, 0), **README 명령은 ratio 0.25, (5000, 10000)** | teacher_cts.py:110-127 · train.py:39-49 · README.md:54 |

### 5.6 학습

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| PPO | clip 0.2 · value coef 1.0 · clipped value loss · entropy 0.01 · **epoch 10** · mini-batch 4 · lr 1e-3 adaptive (KL > 0.02 ÷1.5, < 0.005 ×1.5, 1e-5 ~ 1e-2) · desired_kl 0.01 · γ 0.99 (TeacherCTS 기본 0.998 을 덮음) · λ 0.95 · max_grad_norm 1.0 · 24 step | ppo:27-52 (재확인) · teacher_cts.py:33, 369-396 | 표에 없음 |
| student encoder · JEPA 최적화 | student Adam 2e-4 · JEPA Adam 5e-4, grad clip 10, iteration 마다 5 epoch × env ≤ 256 · 시간 ≤ 5 | train.py:50-52 · jepa_estimator_sensor_ss.py:178, 249-251 · storage/rollout_storage_jepa_ss.py:89-107 | 표에 없음 |
| num_envs | env cfg 4096 → train.py 인자 기본 **1024** 가 덮음 → README 명령 4096 | cfg:185 · train.py:34, 103-115 · README.md:54 | 표에 없음 |
| max_iterations | ppo cfg 1500 → train.py 기본 10000 이 항상 덮음 → README 20000. 논문 비교 15000, 공개 체크포인트 15000 | ppo:28 · train.py:36, 117-120 · README.md:54 | 표에 없음 |
| 시드 | `--seed` 기본 None → agent cfg 기본 42 (로컬 Isaac Lab rl_cfg.py:141) | train.py:35, 123 | 표에 없음 |
| 시간 · 안정성 | 약 12 h, RTX 6000 Pro (논문 요약). README: 「학습이 가끔 불안정하다, 15k 이후 체크포인트를 MuJoCo 로 골라라」 | README.md:56 | 표에 없음 |
| 다중 GPU | `WORLD_SIZE` > 1 이면 NCCL | R/runners/on_policy_runner_teacher.py:543-585 | 표에 없음 |

### 5.7 보상 (RewardManager 를 쓰지 않고 DirectRLEnv 안에서 `rate × weight × step_dt(0.02)` 로 합산: env:753-760)

| 항목 | 식 | 가중치 (dt 곱하기 전) | 근거 |
|---|---|---|---|
| track_lin_vel_xy_exp | exp(-‖cmd_xy − v_xy‖² / 0.25) | 2.0 | cfg:134 · go2_loco_rewards.py:36-39 |
| track_ang_vel_z_exp | exp(-(cmd_wz − wz)² / 0.25) | 1.0 | cfg:135 |
| lin_vel_z_l2 | vz² | -2.0 → 0.0 (iteration 0 ~ 1500) | cfg:136-139 · env:767-773 |
| ang_vel_xy_l2 | ‖ω_xy‖² | -0.05 | cfg:140 |
| joint_acc_l2 | ‖q̈‖² | -1e-7 | cfg:141 |
| joint_power | Σ\|q̇·τ\| | -2e-5 | cfg:142 |
| joint_torques_l2 | ‖τ‖² | -1e-4 | cfg:143 |
| base_height_l2 | (h − 0.38)², h 는 0.4 × 0.3 m 소형 scanner 평균, gap 지형에선 0 | -1.0 → -10.0 (iteration 0 ~ 5000) | cfg:144-147 · env:774-780 |
| action_rate_l2 · action_smoothness_l2 | 1차 · 2차 차분 | -0.01 · -0.01 | cfg:148-149 |
| undesired_contacts | thigh · calf 접촉력 > 5 N 개수 | -1.0 | cfg:150-151 |
| joint_pos_limits | soft 0.9 초과량 | -2.0 | cfg:152 |
| feet_regulation | Σ‖v_xy^foot‖² · exp(-h_f / (0.025 · 0.38)) | -0.05 | cfg:153 |
| hip_pos_penalty_l1 · joint_pos_penalty_l1 | hip · thigh/calf 기본자세 편차 | -0.05 · -0.01 | cfg:154-155 |

feet air time · 종료 penalty · 생존 보너스 · flat orientation 항은 없다. 이 15항의 가중치 · schedule 은 go2_rl_robotlab 판 MoE-CTS (3.8절) 의 15항과 항목마다 같다(추적 2.0 / 1.0 · lin_vel_z -2 → 0 · 관절 가속도 -1e-7 · power · torque · base 높이 -1 → -10 과 목표 0.38 · 충돌 5 N · 관절 한계 -2 · feet_regulation · hip -0.05 · thigh/calf -0.01). DR 도 마찰 [0, 2] · 반발 [0, 0.5] · CoM ±0.03 · 영점 ±0.035 · push 4 s ±0.4 / ±0.6 이 같고 base 질량(-2 ~ +5 대 -1 ~ +1)과 Kp/Kd 처리가 다르다. (보상은 이 조사 세션이 두 저장소 cfg 를 직접 대조: JEPLO cfg:130-155 · robotlab `L/env_cfg.py:347-435`. JEPLO `RewardCfg` 의 docstring 이 「RobotLab Go2 reward weights and schedules」 다, cfg:131. DR 비교는 두 하위 세션 표를 나란히 본 것. JEPLO 는 Go2 자산 · actuator 를 unitree_rl_lab · robot_lab 에서 가져왔다고 적는다: assets/unitree.py:71, 126)

### 5.8 지형 · curriculum

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 생성기 | ParkourTerrainGenerator, curriculum True. 열마다 종류, 행마다 d = row/9 (10단계, 0~1) | terrain/parkour_terrains_cfg.py:15-26 | 표에 없음 |
| 크기 | 부지형 9 × 9 m, **10행 × 30열**, border 20 m, horizontal 0.08 | parkour_terrains_cfg.py:16-23 | 표에 없음 |
| 비율 | 활성 7종, cfg 의 0.25 를 `__post_init__` 이 모두 1/7 로 덮음: gap · flat · box · discrete_obstacles · discrete_grid · pyramid · inverted | cfg:299-302 · env:352-371 | 표에 없음 |
| 난이도 | gap 폭 0.1 + 0.54d m · flat 거칠기 0.02 + 0.04d · box 높이 0.1 + 0.4d · discrete_obstacles 0.4d · grid 0.2d · 계단 0.04 + 0.16d (폭 0.25~0.35 m) | parkour_terrains_cfg.py:28-165 | 표에 없음 |
| 초기 레벨 | `max_init_terrain_level=0`, 모든 env 를 0 레벨에 | cfg:195 · env:375 | **2** |
| 승강 (waypoint) | 8개 모두 도달 +1, 4개 미만 -1 | env:869-872 | 표에 없음 |
| 승강 (direct) | spawn 에서 최대 이동거리 > 4 m 면 +1, < 0.5 × \|Σ명령 xy\| × 4 s × 0.9 면 -1 | env:873-887 | 표에 없음 |

### 5.9 Domain randomization

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 질량 · 링크 · CoM | base +U(-2, 5) kg · 링크 ×U(0.9, 1.1) · base CoM ±0.03 m | cfg:45-72 | 표에 없음 |
| 마찰 · 반발 | U(0, 2) · U(0, 0.5), 64 bucket, 지면 1.0 average | cfg:100-111, 197-203 | 표에 없음 |
| 영점 · 초기 관절 | ±0.035 rad · 위치 ×U(0.5, 1.5) | cfg:73-85 | 표에 없음 |
| push | 4 s 마다 x · y ±0.4 m/s, roll · pitch · yaw ±0.6 rad/s (play 에서 끔) | cfg:86-99 · play.py:107 | `push_robot=None` |
| Kp/Kd | 5.4절 gain curriculum | env:916-936 | 표에 없음 |
| 모터 강도 | 없음 (RandomDCMotor 는 정의만) | motor/random_dc_motor.py:20-55 | 표에 없음 |
| 지연 | 0~20 ms (actuator) | assets/unitree.py:148-149 | 표에 없음 |

### 5.10 배포

| 항목 | 값 | 근거 |
|---|---|---|
| sim-to-sim | unitree_mujoco 개조본(C++): Mid-360 패턴으로 mj_multiRay (20 Hz, 프레임당 24000 광선), ZMQ 5590 → lidar_depth_pub `--sim` → deploy 가 DDS 로 제어. 터미널 5개 | deployment/unitree_mujoco/simulate/src/param.h:29-33 · README.md:207-240 |
| sim-to-real | `deploy.cpp` (C++17 · Eigen · fmt · onnxruntime · unitree_sdk2 · ZMQ). rt/lowstate → rt/lowcmd 로 q · kp · kd. TensorRT EP, 시작 때 저장 표본으로 출력 검증 | deployment/go2_deploy/deploy/CMakeLists.txt:12-32 · deploy.cpp:1083-1161 |
| 주기 | 제어 50 Hz · estimator 10 Hz | deploy.cpp:598-599, 826-838 |
| **명령 입력** | (a) ZMQ SUB 5562 로 float32 × 3 (vx, vy, wz), pygame 키보드 스크립트가 50 Hz 로 보냄 (slow 0.75/0.3/1.0, fast 1.0/1.0/2.0). (b) Unitree 게임패드: joystick 모드 vx = ly × 0.75, vy = -lx × 0.75, wz = -rx × 1.0. B 는 비상정지 | deploy.cpp:943-950, 1564-1594, 1843-1931 · scripts/pygame_wm_control.py:41-47 |
| 명령 clip | config.json 전진 1.5 · 횡 1.5 · 회전 3.0 | deploy/config.json:4-6 |
| 행동 후처리 · gain | 기본: 0.8·new + 0.2·prev 평활, hip ×0.5. README 명령은 `--raw-actions` 로 둘 다 끔. config.json Kp 28 · Kd 1.1 | deploy.cpp:752-760, 2017-2066 · config.json:2-3 |
| 안전장치 | τ_proxy > 30 N·m 또는 \|dq\| > 25 rad/s 가 연속 N회면 damping | deploy.cpp:671-674, 2098-2150 |
| 빌드 이상 | lidar_depth_pub/CMakeLists.txt:20 이 이 SHA 에 없는 `lidar_depth_pub_occ.cpp` 를 참조. rclcpp · livox_ros_driver2 를 무조건 찾으므로 sim 모드도 빌드에 ROS2 필요 | CMakeLists.txt:8-10, 20 |

### 5.11 논문에 없고 코드에만 있는 것 (논문 대조함: arXiv 2609.15770 abs · HTML, WebFetch 요약을 거침)

일치: 이력 Ho 10 · Hd 2 · Ha 5 · proprio 45 · 높이 맵 300 · privileged 50 · depth 60 × 25 · 2° · ViT 6층 · head 4 · embed 128 · z_o 32 · z_d 64 · GRU 512 · SIGReg M 512 · λ 0.1 · student schedule (5000 ~ 10000, 1024 env) · 보상 15항 가중치와 schedule · 명령 표 · DR 표 대부분 · 50 / 10 Hz.

다른 곳: (1) 코드는 **gap 지형을 활성(1/7)** 으로 둔다(논문 요약에는 gap 이 없음, 이름 대응은 추정). (2) 논문은 Kp [21, 39] · Kd [0.7, 1.3] 범위만, 코드는 그 범위로 넓혀 가는 **PD gain curriculum**. (3) 논문 요약은 「모든 MLP hidden 512, 256」, 코드의 teacher encoder 3개와 JEPA action encoder 는 256, 128. (4) critic 에 잡음 없는 현재 proprio 45 가 더해져 845. (5) LiDAR 누적: 논문 「최신 raw scan 5개, 20 Hz」, 코드는 50 Hz RayCaster 와 위의 이중 갱신. (6) 가림 augmentation 에 정사각형 · 사다리꼴 · Perlin · 아래 2행 dropout 추가. (7) privileged 접촉력은 벡터가 아니라 크기 19개. (8) 높이 맵 중심이 base 앞 0.4 m. (9) iteration 수: 논문 15000 · README 20000 · train.py 기본 10000 · ppo cfg 1500. (10) patch 크기 표기 8 × 4 대 (4, 8).

코드에만: PPO 하이퍼파라미터 전부 · JEPA · student 최적화 값 · action scale · dt · decimation · 에피소드 25 s · 종료 조건 · 지형 크기 · 승강 규칙 · T-N 곡선 · 링크 질량 scale · Mid-360 갱신당 3000 표본 · 배포 평활 · hip ×0.5 · Kp 28 / Kd 1.1 · OOD 임계 · TensorRT 허용오차.

### 5.12 우리 기계 요구사항 대조

| 항목 | JEPLO 요구 | 우리 환경 |
|---|---|---|
| 학습 OS | 명시 없음, 학습 경로에서 Linux 전용 호출은 grep 범위에서 못 찾음 | Windows 11 |
| Python · Isaac Lab | 3.11 · pip `isaaclab[isaacsim,all]==2.3.2.post1` | 3.11.15 · 로컬 v2.3.2 소스 + isaaclab 0.54.2 (pip 2.3.2.post1 과 같은지 `미확인`) |
| torch | 2.7.0 cu128 | 2.7.0+cu128 |
| rsl_rl | 저장소 안 개조본(패키지명 rsl-rl-lib 2.3.1)을 `pip -e` | rsl-rl-lib 3.1.2 |
| 기타 | lejepa (`pip -e`) · wandb 필수 | `미확인` |
| 컴파일 (학습) | 확인 범위에서 C++/CUDA 확장 빌드 없음 | nvcc · MSVC 없음 |
| GPU | RTX 6000 Pro 1장 약 12 h (논문 요약) | RTX 5080 × 2 (16 GB 씩) |
| 다중 GPU | NCCL | Windows 의 NCCL 가능 여부 `미확인` |
| sim-to-sim · 실기 | Ubuntu 22.04 · unitree_sdk2 · unitree_mujoco C++ 빌드 · ROS2 Humble + Livox driver2 · ONNX Runtime GPU 1.22.0 linux · TensorRT 10.9 · CUDA 12.8 · Jetson AGX Orin | Windows, 컴파일러 없음, Linux 이전은 계획만 |

### 5.13 못 본 것 (이 절)

- 바이너리(pt · onnx · npz · mid360.npy) 미열람: Mid-360 갱신당 실제 광선 수, 공개 체크포인트가 지금 코드 값으로 학습됐는지(logs 에 params/env.yaml · agent.yaml 없음) `미확인`.
- 논문 원문 PDF · 부록 직접 대조 안 함(gap 언급 · gain curriculum 언급 여부는 최종 확인 아님).
- 다 읽지 않은 파일: go2_loco_env_window.py · parkour_sub_terrians.py 대부분 · parkour_terrain_importer.py · depth_noise.py · deploy.cpp 기립 시퀀스 · unitree_mujoco 나머지 · lidar_depth_pub.cpp 의 sim 모드.
- 실행 없음: 845 · 20 × 15 · depth 이중 갱신은 모두 코드 읽기 결과.

### 5.14 이 절의 가장 중요한 사실 다섯

1. **JEPA 는 사전학습이 아니다.** PPO 와 같은 iteration 안에서 따로 최적화되고, target encoder · EMA · masking 이 없으며 collapse 는 SIGReg(λ 0.1, 512 slice)로 막는다. 정책은 GRU hidden 512 를 detach 해서 받는다.
2. 정책 경로: proprio 45 × 10 + JEPA hidden 512 → student encoder (teacher 의 이력 · 높이 맵 300 · privileged 50 latent 3 × 64 를 MSE 모방) → teacher 와 공유하는 actor 237 → 512 → 256 → 128 → 12. JEPA 는 2 × 25 × 60 구면 depth (≤ 2 m)를 10 Hz 로 본다.
3. 명령은 지형별로 두 모드(direct: vx · vy 크기 0.5~1.0 양방향 · wz ±2 / waypoint: 속력 0.5~1.0 · yaw rate ±1), 제자리 회전 20 % (iteration ≥ 1000), 재추출 4 s.
4. 보상 15항은 RewardManager 없이 weight × 0.02 로 합산되고, 코드에는 논문 요약에 없는 PD gain curriculum 과 gap 지형이 있다. push 는 4 s 마다 켜져 있다.
5. **학습 요구(Python 3.11 · Isaac Lab 2.3.2.post1 · torch 2.7.0 cu128)는 우리 env 의 판 번호와 같다.** 배포 두 경로(MuJoCo · Jetson)는 Linux 전용 의존과 C++ 빌드를 요구한다.

---

## 6. leggedrobotics/legged_gym · unitreerobotics/unitree_rl_gym

> 이 절은 하위 조사 세션이 읽은 결과를 이 조사 세션이 옮겼다. 이 조사 세션이 직접 다시 연 것: unitree_rl_gym `legged_gym/envs/go2/go2_config.py` 전체 · 두 저장소 base cfg 의 핵심 값(grep) · unitree_rl_gym `legged_robot.py:198-204`(항상 평면) · go2_config 와 a1_config 의 diff · legged_gym 논문 HTML 의 「108 measurements」 · 「pushes happen every 10 s」 · 「kept constant for the duration of an episode」 · Table 2 · Table 4 문장. 나머지 행 번호는 하위 세션이 연 행이다.

**경로 약칭.** legged_gym(LG): `LGc` = `legged_gym/envs/base/legged_robot_config.py` · `LGe` = `legged_gym/envs/base/legged_robot.py` · `LGt` = `legged_gym/utils/terrain.py`. unitree_rl_gym(UR): `URc` = `legged_gym/envs/base/legged_robot_config.py` · `URe` = `legged_gym/envs/base/legged_robot.py` · `go2` = `legged_gym/envs/go2/go2_config.py`. 그 밖은 `LG:경로:행` · `UR:경로:행`.

### 6.1 무엇을 주는가

- **legged_gym**: Isaac Gym 의 rough terrain 속도 추종 환경(ANYmal B/C · A1 · Cassie). game-inspired terrain curriculum 구현. PPO 는 저장소 밖 rsl_rl(v1.0.2). **Go2 설정 없음.** 실기 배포 코드 없음, actor JIT 내보내기까지만.
- **unitree_rl_gym**: legged_gym 을 복사한 뒤 env 코드에서 지형 생성 · height scan · terrain curriculum 을 지운 **평면 판**. Go2 는 legged_gym A1 설정을 그대로 복사해 등록했다. MuJoCo sim-to-sim 과 실기 배포 코드는 **G1 · H1 · H1_2 용만** 있다.

### 6.2 메타

| 저장소 | SHA · 마지막 커밋 | 논문 | 라이선스 | 시뮬레이터 | Python | OS |
|---|---|---|---|---|---|---|
| legged_gym | `8fa29acc6fd1910c3d9659eef6310bdd301cde0a` · 2025-05-29 | 「Learning to Walk in Minutes Using Massively Parallel Deep Reinforcement Learning」 CoRL 2021 · arXiv 2109.11978 (`README 주장` LG:README.md:22) | BSD-3-Clause (`코드 확인` LG:LICENSE:1-3) | Isaac Gym **Preview 3**, 「Preview 2 will not work」 (`README 주장` LG:README.md:29) | 3.6 · 3.7 · 3.8, 3.8 권장 (`README 주장` LG:README.md:25) | 명시 없음. 문제 해결 절이 apt · `LD_LIBRARY_PATH` · `libpython3.8m.so` (LG:README.md:82) |
| unitree_rl_gym | `276801e46c5d433564f24658bac64f254b7d2d4b` · 2025-07-25 | 논문 없음 | BSD-3-Clause (UR:LICENSE:1). `legged_gym/LICENSE` 에 ETH · NVIDIA 표기 | Isaac Gym (판 명시 없음, UR:doc/setup_en.md:65) · MuJoCo 3.2.3 (UR:setup.py:11) | 3.8 (UR:doc/setup_en.md:38) | Ubuntu 18.04 이상 권장 (UR:doc/setup_en.md:5) |

legged_gym README 에 「Isaac Lab 으로 옮겼고 이 저장소는 limited updates」 공지가 있다 (`README 주장` LG:README.md:11-15).

설정 경로: LG 는 기본 cfg → robot cfg → `LG:legged_gym/envs/__init__.py:47-51` 등록 → `LG:legged_gym/utils/helpers.py:154` (`--task` 기본 `anymal_c_flat`). UR 은 기본 cfg → `go2` → `UR:legged_gym/envs/__init__.py:14` 의 `register("go2", LeggedRobot, GO2RoughCfg(), GO2RoughCfgPPO())` → `UR:legged_gym/utils/helpers.py:124` (`--task` 기본 `go2`). `--num_envs` · `--seed` · `--max_iterations` 를 주면 cfg 를 덮는다 (LG:helpers.py:127-150).

### 6.3 명령: **속도형**

| 항목 | legged_gym 기본 | unitree_rl_gym go2 최종 | 우리 기준선 |
|---|---|---|---|
| 형식 | (vx, vy, wz) + heading, `num_commands=4`, 관측엔 앞 3칸 (`코드 확인` LGc:71 · LGe:215) | 같음 (URc:42 · URe:188) | 속도 명령 |
| lin_vel_x | [-1.0, 1.0] (LGc:75) | [-1.0, 1.0] 상속 (URc:46) | (0.4, 1.5) |
| lin_vel_y | [-1.0, 1.0] (LGc:76) | [-1.0, 1.0] (URc:47) | (0, 0) |
| ang_vel_yaw | [-1, 1], heading 모드에선 이 범위로 안 뽑음 (LGc:77 · LGe:345-348) | 같음 (URc:48 · URe:300-303) | (-1, 1) |
| heading | `heading_command=True`, 범위 ±3.14. yaw 명령 = `clip(0.5 × wrap_to_pi(목표 − 현재), -1, 1)` 를 매 step 계산, 이득 0.5 · clip ±1 은 코드에 박힘 (LGc:73, 78 · LGe:327-330) | 같음 (URc:44, 49 · URe:287-290) | `heading_command=True` · `rel_heading_envs=1.0` |
| 정지 | 정지 env 비율 설정 없음. xy 명령 노름 ≤ 0.2 면 xy 를 0 으로(heading 은 유지) (LGe:351) | 같음 (URe:306) | `rel_standing_envs=0.1` |
| 재추출 | 10 s (500 step) 와 리셋 때. 에피소드 20 s (LGc:72, 41 · LGe:325-326, 168) | 같음 (URc:43 · URe:285-286, 143) | (10, 10) s |
| 명령 curriculum | 기본 꺼짐 (`curriculum=False`, `max_curriculum=1.`). 켜면 tracking_lin_vel 평균이 0.8 × scale 을 넘을 때 lin_vel_x 를 ±0.5 씩 넓힘 (LGc:69-70 · LGe:443-452, 161-162) | 함수는 남았으나 reset_idx 에서 부르지 않음 (URe:386-395, 126-161) | 표에 없음 |

### 6.4 관측

| 항목 | legged_gym 기본 | unitree_rl_gym go2 최종 | 우리 기준선 |
|---|---|---|---|
| actor | 선속도 3 · 각속도 3 · 중력 3 · 명령 3 · 관절각 12 · 관절속도 12 · 직전 행동 12 · height 187 = **235** (`num_observations=235`) (`코드 확인` LGc:36 · LGe:212-223). 187 = 17 × 11 (`계산`) | 앞 7항목 = **48** (`num_observations=48`). height 항은 코드에서 지워짐 (`코드 확인` URc:6 · URe:185-194) | 235, 그중 height scan 187 |
| critic | `num_privileged_obs=None`, 비대칭 critic 없음 (LGc:37 · LG:legged_gym/envs/base/base_task.py:75-78) | 같음 (URc:7). UR 의 G1 · H1 · H1_2 는 privileged 50 · 44 · 50 | 표에 없음 |
| height 격자 | x -0.8 ~ 0.8 (0.1 간격, 17점) · y -0.5 ~ 0.5 (11점), yaw 만 따라 회전, 인접 3 표본 최솟값, 관측값 `clip(base_z − 0.5 − h, -1, 1) × 5.0` (LGc:54-55 · LGe:796-811, 222) | cfg 값은 남았지만 env 가 읽지 않음 (URc:24-26. URe 에서 terrain cfg 참조는 515-517 마찰뿐) | 187 (격자는 표에 없음) |
| 이력 | 없음 (직전 행동 1 step) (LGe:218) | 같음 (URe:191) | 표에 없음 |
| obs scale | lin_vel 2.0 · ang_vel 0.25 · dof_pos 1.0 · dof_vel 0.05 · height 5.0 · 명령 [2, 2, 0.25] (LGc:157-162 · LGe:515) | 같음 (URc:128-133 · URe:458) | 표에 없음 |
| 잡음 | lin_vel 0.1 · ang_vel 0.2 · gravity 0.05 · dof_pos 0.01 · dof_vel 1.5 · height 0.1 (× obs scale), 균등 (LGc:167-175 · LGe:226, 469-477) | 같음 (URc:138-146) | 표에 없음 |
| clip_observations | 100 (LGc:163) | 100 (URc:134) | 표에 없음 |

### 6.5 행동 · 제어

| 항목 | legged_gym 기본 | unitree_rl_gym go2 최종 | 우리 기준선 |
|---|---|---|---|
| 행동 | 관절 위치 목표 `control_type='P'`. torque = Kp(목표 − q) − Kd·q̇ 를 Python 에서 sim step 마다 계산해 effort 로 (LGc:90, 108 · LGe:365-375, 89-92) | 같음 (go2:25) | 표에 없음 |
| action_scale | 0.5 (a1 0.25, anymal_c 0.5) (LGc:95) | **0.25** (go2:29) | 표에 없음 |
| PD | 기본은 자리표시 값. a1 20 / 0.5. anymal_c 는 LSTM actuator net (LGc:92-93 · LG:legged_gym/envs/anymal_c/mixed_terrains/anymal_c_rough_config.py:62-69) | **Kp 20 · Kd 0.5** (go2:26-27) | 표에 없음 |
| 기본 관절각 · 초기 높이 | 자리표시 | hip ±0.1 · thigh 앞 0.8 / 뒤 1.0 · calf -1.5 · z 0.42 (go2:5-21) | 표에 없음 |
| torque · 속도 한계 | URDF | Go2 URDF: hip · thigh 23.7, calf 35.55 N·m · 30.1 · 30.1 · 20.07 rad/s (UR:resources/robots/go2/urdf/go2.urdf:170-174, 225-229, 280-284) | 표에 없음 |
| decimation · dt | 4 · 0.005 → 정책 50 Hz · 물리 200 Hz (LGc:97, 184) | 같음 (go2:31 · URc:155) | 표에 없음 |
| clip_actions | 100 (LGc:164) | 100 (URc:135) | 표에 없음 |
| 종료 | `terminate_after_contacts_on` 접촉 > 1 N 또는 time-out (LGe:141-143) | 위 + \|pitch\| > 1.0 · \|roll\| > 0.8 rad (URe:122), 대상 `["base"]` | 표에 없음 |

### 6.6 신경망 · 학습

| 항목 | legged_gym 기본 | unitree_rl_gym go2 최종 | 우리 기준선 |
|---|---|---|---|
| 정책 | `ActorCritic`, actor · critic [512, 256, 128] ELU, init_noise_std 1.0. RNN 설정은 주석(lstm 512 1층). anymal_c_flat 은 [128, 64, 32] (LGc:206-213, 231) | 같음 (URc:177-180, 202). UR 의 G1 · H1 은 `ActorCriticRecurrent` lstm 64 | 표에 없음 |
| PPO | lr 1e-3 adaptive · desired_kl 0.01 · entropy 0.01 · clip 0.2 · clipped value loss · γ 0.99 · λ 0.95 · 24 step · 4 mini-batch · 5 epoch · max_grad_norm 1.0 · value_loss_coef 1.0 (LGc:217-228, 233) | 같음 (URc:188-204 · go2:50) | 표에 없음 |
| num_envs · max_iterations · 시드 | 4096 · 1500 · 1 (LGc:35, 234, 203) | 4096 · 1500 · 1 (URc:5, 205, 174) | 표에 없음 |
| 다중 GPU | rl_device 하나. `--horovod` 는 선언만 (LG:helpers.py:162-163) | 같음 | 표에 없음 |
| 학습 시간 | README 에 없음. 논문: RTX A6000 에서 1500 update 를 20분 안에 (`논문`, 하위 세션이 읽음) | README 에 없음 | 표에 없음 |

### 6.7 보상 (scale 0 인 항은 지우고 나머지에 dt 0.02 를 곱한다: LGe:549-554 · URe:490-495. `only_positive_rewards=True`, `tracking_sigma=0.25`: LGc:148-149)

| 항목 | legged_gym 기본 | go2 최종 | ×dt 후 (`계산`) |
|---|---|---|---|
| tracking_lin_vel | 1.0 (LGc:133) | 1.0 | 0.02 |
| tracking_ang_vel | 0.5 (LGc:134) | 0.5 | 0.01 |
| lin_vel_z | -2.0 (LGc:135) | -2.0 | -0.04 |
| ang_vel_xy | -0.05 (LGc:136) | -0.05 | -0.001 |
| torques | -0.00001 (LGc:138), a1 -0.0002 | **-0.0002** (go2:45) | -4e-6 |
| dof_acc | -2.5e-7 (LGc:140) | -2.5e-7 | -5e-9 |
| feet_air_time | 1.0 (LGc:142), anymal_c_flat 2.0. 첫 접지 때 Σ(t_air − 0.5), 명령 ≤ 0.1 이면 0 (LGe:882-893) | 1.0 | 0.02 |
| collision | -1 (LGc:143), 0.1 N 초과 접촉 수 | -1, 대상 thigh · calf (go2:37) | -0.02 |
| action_rate | -0.01 (LGc:145) | -0.01 | -0.0002 |
| dof_pos_limits | 기본 없음, a1 -10 | **-10.0** (go2:46) | -0.2 |
| 꺼진 항 (0) | termination · orientation(anymal_c_flat 은 -5) · dof_vel · base_height · feet_stumble · stand_still (LGc:132-146) | 같음 | |
| soft_dof_pos_limit · base_height_target · max_contact_force | 1.0 · 1.0 · 100 (LGc:150-154) | 0.9 · 0.25 · 100 (go2:42-43). base_height 보상이 꺼져 있어 0.25 는 안 쓰인다 | |

`feet_stumble` 은 함수 이름이 `_reward_stumble` 이라 scale 을 0 이 아닌 값으로 바꾸면 getattr 가 실패한다 (LGe:895, 563, 하위 세션 확인).

### 6.8 지형 · curriculum

| 항목 | legged_gym 기본 | unitree_rl_gym go2 최종 | 우리 기준선 |
|---|---|---|---|
| mesh | `trimesh` (LGc:44) | `plane` (URc:15). env 는 이 값을 읽지 않고 **항상 ground plane** (`코드 확인` URe:198-204) | 표에 없음 |
| 크기 · 행 · 열 | 8 × 8 m · 10행 · 20열 · border 25 m (LGc:45-47, 59-62) | cfg 에만 남음 | 표에 없음 |
| 비율 | `[0.1, 0.1, 0.35, 0.25, 0.2]` = smooth slope · rough slope · stairs up · stairs down · discrete (LGc:63-64). 열 수 2 · 2 · 7 · 5 · 4 (`계산`) | 지형 없음 | 표에 없음 |
| 난이도 | 행 i 의 d = i/10 (0~0.9). slope 0.4d · 계단 0.05 + 0.18d (최대 0.212 m), 폭 0.31 m · 장애물 0.05 + 0.2d · rough ±0.05 m (LGt:88, 115-137) | 해당 없음 | 표에 없음 |
| max_init_terrain_level | 5 (LGc:58) | 5 가 남았지만 읽히지 않음 (URc:29) | **2** |
| 승급 · 강등 | 리셋 때. 이동 거리 > 4 m 면 승급, < \|cmd_xy\| × 20 s × 0.5 면 강등, 최고 레벨을 넘으면 무작위 레벨 (LGe:428-440) | 함수 삭제 | 표에 없음 |

### 6.9 Domain randomization

| 항목 | legged_gym 기본 | unitree_rl_gym go2 최종 | 우리 기준선 |
|---|---|---|---|
| 마찰 | [0.5, 1.25], 64 bucket (LGc:122-123 · LGe:266-277). anymal_c_flat [0, 1.5] | 같음 (URc:93-94) | 표에 없음 |
| 질량 | 기본 꺼짐, [-1, 1] (LGc:124-125). anymal_c_rough 는 켬, [-5, 5] kg | 꺼짐 (URc:95-96) | 표에 없음 |
| push | 켬 · 15 s · 1.0 m/s. 전역 step 기준으로 모든 env 를 한꺼번에 (LGc:126-128 · LGe:334-335, 414-419) | 값은 같고 env 별 `episode_length_buf % 750 == 0` 일 때 (URe:372-382) | `push_robot=None` |
| 리셋 | 관절 default × U(0.5, 1.5), base 속도 6축 U(-0.5, 0.5) (LGe:385-386, 408) | 같음 | 표에 없음 |
| actuator | anymal_c 는 LSTM actuator net (LG:resources/actuator_nets/anydrive_v3_lstm.pt) | 없음 (Python PD) | 표에 없음 |

### 6.10 배포

| 항목 | legged_gym | unitree_rl_gym |
|---|---|---|
| 내보내기 | `play.py` 가 actor 를 `torch.jit.script` 로 `exported/policies/policy_1.pt` (LG:legged_gym/utils/helpers.py:180-190) | 같음 (UR:legged_gym/utils/helpers.py:150-160) |
| sim-to-sim | 없음 | `deploy/deploy_mujoco/deploy_mujoco.py` 있음. configs 는 g1 · h1 · h1_2 뿐, go2 MuJoCo xml 없음. 관측 배열이 go2 학습 관측과 다름(base_lin_vel 없음, phase 2칸 있음) (deploy_mujoco.py:111-117) |
| sim-to-real | 없음 | Python `deploy/deploy_real/deploy_real.py`(unitree_sdk2py) · C++ `deploy/deploy_real/cpp_g1` 모두 G1 · H1 · H1_2 용. 「Currently supported robots include Unitree G1, H1, H1_2」 (`README 주장` UR:deploy/deploy_real/README.md:3). **Go2 설정 없음** |
| 사전 학습 정책 | 없음 | `deploy/pre_train/{g1,h1,h1_2}/motion.pt` 뿐 |

### 6.11 unitree_rl_gym go2 가 legged_gym 기본에서 바꾼 값

| 층 | 항목 | legged_gym 기본 | go2 최종 | 근거 |
|---|---|---|---|---|
| 기본 cfg | num_observations · mesh_type | 235 · trimesh | 48 · plane | LGc:36, 44 / URc:6, 15 |
| go2 cfg | init z · 기본 관절각 · PD · action_scale | 1.0 · 자리표시 · 자리표시 · 0.5 | 0.42 · hip ±0.1 / thigh 0.8·1.0 / calf -1.5 · 20 / 0.5 · 0.25 | go2:5-31 |
| go2 cfg | asset | "" | go2.urdf · foot · penalize thigh·calf · terminate base · self_collisions 1 | go2:34-39 |
| go2 cfg | soft_dof_pos_limit · base_height_target · torques · dof_pos_limits | 1.0 · 1.0 · -1e-5 · 없음 | 0.9 · 0.25 · -2e-4 · -10 | go2:42-46 |
| env 코드 | 지형 · height scan · terrain curriculum | 있음 | 삭제 (항상 평면) | URe:198-204 |
| env 코드 | 종료 · push · 명령 curriculum 호출 | 접촉 · 전역 push · 호출 | roll/pitch 문턱 추가 · env 별 push · 호출 안 함 | URe:122, 369-382, 126-161 |

**A1 과의 관계** (`코드 확인`, 이 조사 세션이 diff 로 다시 확인): CR 을 지우고 `go2_config.py` 와 `LG:legged_gym/envs/a1/a1_config.py` 를 비교하면 다른 곳은 라이선스 머리말 · 클래스 이름 · URDF 경로 · asset 이름 · experiment_name 뿐이다. Kp 20 / Kd 0.5, action_scale 0.25, 기본 관절각, torques -0.0002, dof_pos_limits -10, base_height_target 0.25 는 모두 A1 의 숫자다.

### 6.12 논문에 없고 코드에만 있는 것 (legged_gym 논문 대조함: arXiv 2109.11978v3 HTML)

이 조사 세션이 HTML 에서 직접 다시 읽은 문장: 「108 measurements of the terrain」, 「The pushes happen every 10 s」, 명령은 「kept constant for the duration of an episode」, Table 2 가중치 표기는 「1 dt」 「4 dt」 「0.00002 dt」 「0.25 dt」 「0.001 dt」 「2 dt」 (값 × dt), Table 4 base linear velocity 잡음 「0.01 m/s」, 실기에서 선속도 명령 상한을 0.6 m/s 로 낮췄다는 문장. 논문 HTML 에서 「512」 · 「neurons」 · 「ELU」 를 찾지 못했다.

| 항목 | 논문 | 코드 |
|---|---|---|
| height 점 수 | 108 | 17 × 11 = 187 (LGc:54-55) |
| push 주기 | 10 s | 15 s (LGc:127) |
| 명령 유지 | 에피소드 동안 고정 | 10 s 마다 재추출, 에피소드 20 s (LGc:72, 41) |
| lin_vel_z · torques · action rate · collision · air time | 4 · 0.00002 · 0.25 · 0.001 · 2 (× dt) | 2 · 0.00001 · 0.01 · 1 · 1 (LGc:135-145) |
| joint motion | 0.001 × (‖q̈‖² + ‖q̇‖²) | dof_acc 2.5e-7 · dof_vel 0 |
| 선속도 잡음 | 0.01 m/s | 0.1 (LGc:172) |
| 계단 · 경사 | 5~20 cm · 0~25° | 최대 0.212 m · slope 0.4d (단위 `미확인`) |

코드에만 있는 숫자: 신경망 [512, 256, 128] ELU · init_noise_std 1.0 · `only_positive_rewards` · 명령 범위 ±1 m/s · heading ±3.14 와 P 이득 0.5 · 작은 명령 0 처리 문턱 0.2 · obs scale · height offset 0.5 · clip ±1 · ×5 · num_rows 10 · num_cols 20 · 지형 비율 · max_init_terrain_level 5 · 마찰 bucket 64 · 리셋 범위 · action_scale 0.5 · clip 100 · anymal_c_rough 질량 ±5 kg.

README 와 코드가 다른 곳: LG:README.md:69 「기본 cfg 에 reward scale 이 없다」, 실제로는 있다 (LGc:131-146). UR:README.md:9 는 Go2 지원을 적지만 Sim2Sim · Sim2Real 절은 G1 · H1 · H1_2 만 다룬다.

### 6.13 우리 기계 요구사항 대조

| 항목 | legged_gym | unitree_rl_gym | 우리 환경 |
|---|---|---|---|
| 시뮬레이터 | Isaac Gym Preview 3 | Isaac Gym (판 명시 없음) | Isaac Lab 2.3.2 + Isaac Sim 5.1. Isaac Gym 설치 여부는 안 봄 `미확인` |
| Python | 3.6~3.8 | 3.8 | 3.11.15 |
| torch | 1.10.0+cu113 (LG:README.md:27) | 2.3.1 · pytorch-cuda 12.1 (UR:doc/setup_en.md:56) | 2.7.0+cu128 |
| rsl_rl | v1.0.2 checkout | v1.0.2 | rsl-rl-lib 3.1.2 |
| 기타 고정 | matplotlib | numpy==1.20 · mujoco==3.2.3 | `미확인` |
| OS | 명시 없음, Linux 명령만 | Ubuntu 18.04+ · Linux Miniconda | Windows 11 (Linux 이전은 계획만) |
| Windows 언급 | 없음 (grep) | 없음 (grep) | Isaac Gym 의 Windows 지원은 두 저장소 문서에 근거 없음 `미확인` |
| GPU | 명시 없음 | 드라이버 525+ 권장 | RTX 5080 × 2 (sm_120). Isaac Gym 과 sm_120 의 호환은 `미확인` |
| 컴파일 | Python 경로에 빌드 없음 | C++ 배포는 cmake · LibTorch · unitree_sdk2 · CycloneDDS, `/usr/local/include` 고정 | nvcc · MSVC 없음 |

### 6.14 못 본 것 (이 절)

- rsl_rl v1.0.2 소스(저장소 밖): ActorCritic 층 구성 · adaptive LR 구현 · time-out bootstrapping · `init_at_random_ep_len` · critic 입력 · 관측 정규화.
- isaacgym 패키지: `terrain_utils` 의 slope 단위와 계단 부호, `gymutil` 기본값.
- 논문 PDF 원본(HTML 만 읽음).
- 실행 결과 전부. UR 의 G1 · H1 세부, `deploy_real/common/*.py`, `cpp_g1` 본문, Go2 URDF 질량 · 관성. git 이력(얕은 clone).

### 6.15 이 절의 가장 중요한 사실 다섯

1. unitree_rl_gym 의 `go2` task 는 **평면 · 48차원 관측(height scan 없음)** 이다 (URc:6, 15 · URe:198-204). 클래스 이름은 `GO2RoughCfg`, experiment 이름은 `rough_go2` 지만 지형이 없다.
2. `go2_config.py` 의 숫자는 legged_gym `a1_config.py` 와 전부 같다 (Kp 20 · Kd 0.5 · action_scale 0.25 · 기본 관절각 · 보상 덮어쓰기).
3. 두 저장소 어디에도 **Go2 배포 코드가 없다.** MuJoCo · 실기 config · 사전 학습 정책은 G1 · H1 · H1_2 뿐.
4. legged_gym 기본 rough 관측은 **235 = 48 + 187 (17 × 11)** 로 우리 기준선 숫자와 같다. 명령 · push · 초기 레벨은 다르다: lin_vel_x ±1 · lin_vel_y ±1 · push 15 s 1 m/s · max_init_terrain_level 5 (우리: (0.4, 1.5) · (0, 0) · None · 2).
5. legged_gym 논문 Table 2 의 보상 가중치와 코드 기본값은 여러 칸이 다르고(lin_vel_z 4 대 2, action rate 0.25 대 0.01, collision 0.001 대 1, air time 2 대 1), push 주기(10 s 대 15 s) · height 점 수(108 대 187) · 명령 재추출(에피소드 고정 대 10 s)도 다르다. 신경망 크기는 논문에 없고 코드에만 있다.

---

## 7. unitreerobotics/unitree_rl_lab · Zhefan-Xu/isaac-go2-ros2

> 하위 조사 세션이 읽은 결과를 옮겼다. 이 조사 세션이 다시 연 것: unitree_rl_lab `velocity_env_cfg.py` 의 명령(189-203) · 지형 생성기(24-37) · policy 관측(220-238), isaac-go2-ros2 의 cmd_vel 콜백(`ros2/go2_ros2_bridge.py:320-323`) · 전역 명령 텐서(`go2/go2_ctrl.py:11-22`) · `cfg/sim.yaml` · decimation 덮어쓰기(`isaac_go2_ros2.py:38-46`). 하위 세션이 「Isaac Lab 본체 · 미확인」 으로 둔 칸 일부는 이 조사 세션이 **우리 로컬 Isaac Lab v2.3.2 소스**로 채웠다(「로컬 v2.3.2」 표시). unitree_rl_lab 이 적은 판은 2.3.0 이라 판 차이에 따른 값 차이는 `미확인` 이다.

경로 약칭 (unitree_rl_lab): `P/` = `source/unitree_rl_lab/unitree_rl_lab/` · `go2cfg` = `P/tasks/locomotion/robots/go2/velocity_env_cfg.py` · `go2reg` = `P/tasks/locomotion/robots/go2/__init__.py` · `ppo` = `P/tasks/locomotion/agents/rsl_rl_ppo_cfg.py` · `cmd` = `P/tasks/locomotion/mdp/commands/velocity_command.py` · `curr` = `P/tasks/locomotion/mdp/curriculums.py` · `rew` = `P/tasks/locomotion/mdp/rewards.py` · `asset` = `P/assets/robots/unitree.py` · `act` = `P/assets/robots/unitree_actuators.py` · `export` = `P/utils/export_deploy_cfg.py` · `D/` = `deploy/include/`.

### 7.1 무엇을 주는가

- **unitree_rl_lab**: Unitree 공식 Isaac Lab 확장. Go2 속도 추종 task(`Unitree-Go2-Velocity`)의 학습 설정 전부와, 학습 때 기록하는 `deploy.yaml` · play 에서 내보내는 `policy.onnx` 를 읽어 unitree_sdk2(DDS)로 실기나 MuJoCo 에 거는 C++ 컨트롤러가 있다. **Go2 task 는 평면 하나 · 고유수용감각 관측(height scan 관측 없음)** 이다. Go2 정책 파일은 저장소에 없다.
- **isaac-go2-ros2**: 학습 코드가 없는 추론 · ROS2 브리지. 외부에서 학습된 Isaac Lab Go2 rough 체크포인트(입력 235)를 Isaac Sim 4.5 에서 돌린다. **ROS2 `geometry_msgs/Twist` cmd_vel 이 clip · scale · timeout 없이 정책 관측의 명령 3칸으로 들어간다.**

### 7.2 메타

| 항목 | unitree_rl_lab | isaac-go2-ros2 |
|---|---|---|
| SHA · 커밋 | `4960b84732b0c2ec593dccbfe963fda1bcd7b1e3` · 2025-11-19 | `f201692a5519e6e6ed058637ce93a2f603f016f2` · 2025-09-23 |
| 라이선스 | Apache-2.0 (`코드 확인` LICENCE:1-2 · source/unitree_rl_lab/pyproject.toml:13) | **라이선스 파일 없음** (`git ls-files`) |
| Isaac Sim · Isaac Lab | 5.1.0 · 2.3.0 (`README 주장` README.md:3-4). setup.py classifier 엔 4.5.0 이 남음 (setup.py:36) | 4.5.0 · 2.1.0 (`README 주장` README.md:4-8, 26-28). 4.2 판은 `isaacsim-4.2` 브랜치 |
| Python | ≥ 3.10 (pyproject.toml:12) | 3.10 (`README 주장` README.md:2) |
| OS | classifier `POSIX :: Linux`. 배포 C++ 은 `/proc/self/exe` · onnxruntime-linux-x64 · apt | Ubuntu 22.04 (`README 주장` README.md:6) · ROS2 Humble |
| 등록 task | `Unitree-Go2-Velocity` · `Unitree-G1-29dof-Velocity` · `Unitree-H1-Velocity` · G1 mimic 2종 (go2reg:3-12) | 없음. Isaac Lab 의 `Isaac-Velocity-Rough-Unitree-Go2-v0` 를 `gym.make` (go2/go2_ctrl.py:81) |
| 학습 코드 | 있음 (train.py · play.py) | 없음 (추론 루프만, isaac_go2_ros2.py:80-101) |
| 논문 | 없음 | 없음. 컨트롤러가 `abizovnuralem/go2_omniverse` 기반이라고 적음 (README.md:112) |

설정 경로: `gym.register` (go2reg:3-12) → `RobotEnvCfg` (go2cfg:366-405, `__post_init__` 382-405) → `BasePPORunnerCfg` (ppo:10-36) → train.py CLI 덮어쓰기 (scripts/rsl_rl/train.py:124-133).

### 7.3 unitree_rl_lab 명령: **속도형**

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 종류 | (vx, vy, wz). `UniformLevelVelocityCommandCfg` = Isaac Lab `UniformVelocityCommandCfg` + `limit_ranges` | `코드 확인` cmd:9-11 · go2cfg:191-202 | 속도 명령 |
| lin_vel_x | 초기 (-0.1, 0.1) → limit (-1.0, 1.0) | `코드 확인` go2cfg:197, 200 | (0.4, 1.5) |
| lin_vel_y | 초기 (-0.1, 0.1) → limit (-0.4, 0.4) | `코드 확인` go2cfg:197, 200 | (0, 0) |
| ang_vel_z | (-1, 1), limit 도 같음 | `코드 확인` go2cfg:197, 200 | (-1, 1) |
| 재추출 | (10.0, 10.0) s | `코드 확인` go2cfg:193 | (10, 10) |
| rel_standing_envs | 0.1 | `코드 확인` go2cfg:194 | 0.1 |
| heading_command · rel_heading_envs | Go2 cfg 에 설정 없음 → 기본값 **False · 1.0** (로컬 v2.3.2 `isaaclab/envs/mdp/commands/commands_cfg.py:41, 55`). G1 · H1 cfg 는 `heading_command=False` 를 명시 | `코드 확인`(설정 없음) · 기본값은 로컬 v2.3.2 | True · 1.0 |
| 명령 curriculum | `lin_vel_cmd_levels` 만 등록. `common_step_counter % max_episode_length == 0` 일 때 리셋 env 의 `track_lin_vel_xy` 에피소드 합 / 20 s 가 weight × 0.8 (= 1.2) 를 넘으면 lin_vel_x · y 범위를 ±0.1 넓히고 limit 로 clamp. lin_vel_x 9번, y 3번이면 limit (`계산`). `ang_vel_cmd_levels` 는 정의만 있고 등록 안 됨 | `코드 확인` go2cfg:363 · curr:11-61 | 표에 없음 |
| 배포 | 조이스틱 `ly` · `-lx` · `-rx` 를 deploy.yaml 의 범위(= limit_ranges)로 clamp | `코드 확인` D/isaaclab/envs/mdp/observations/observations.h:111-123 · export:40-48 | 표에 없음 |

### 7.4 unitree_rl_lab 관측 · 행동

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| policy | 각속도 × 0.2 (3, ±0.2) · 중력 (3, ±0.05) · 명령 (3) · 관절각 (12, ±0.01) · 관절속도 × 0.05 (12, ±1.5) · 직전 행동 (12). 모두 clip ±100. **합 45**, history 없음(`history_length=5` 는 주석) | `코드 확인` go2cfg:222-237 | 235 |
| critic | 선속도 3 · 각속도 3 · 중력 3 · 명령 3 · 관절각 12 · 관절속도 12 · 관절 토크 × 0.01 (12) · 직전 행동 12 = **60**, 잡음 없음 (비대칭) | `코드 확인` go2cfg:242-265 | 표에 없음 |
| height scan | **관측에 없음.** 센서는 scene 에 있음 (GridPattern 0.1 · [1.6, 1.0], yaw 정렬). critic 의 height 항은 주석. 점 수는 로컬 v2.3.2 GridPattern 식으로 17 × 11 = 187 (`계산`) | `코드 확인` go2cfg:96-103, 256-259 · 로컬 patterns.py:45-46 | 187 |
| 행동 | 관절 위치 목표 12, scale 0.25, default offset, clip ±100 | `코드 확인` go2cfg:209-211 | 표에 없음 |
| 기본 자세 | hip ∓0.1 · thigh 앞 0.8 / 뒤 1.0 · calf -1.5 · 초기 높이 0.4 m | `코드 확인` asset:102-110 | 표에 없음 |
| actuator | `UnitreeActuatorCfg_Go2HV` (DelayedPDActuator 상속), **stiffness 25.0 · damping 0.5** · friction 0.01. torque-speed 곡선 Y1 20.2 · Y2 23.4 N·m, X1 13.5 · X2 30 rad/s. 지연 · armature 설정 없음 | `코드 확인` asset:113-120 · act:56-146 | 표에 없음 |
| dt · decimation · 에피소드 | 0.005 s · 4 → 50 Hz · 20 s | `코드 확인` go2cfg:385-388 | 표에 없음 |
| 종료 | time_out · base 접촉 (1.0) · bad_orientation 0.8 rad | `코드 확인` go2cfg:350-355 | 표에 없음 |

### 7.5 unitree_rl_lab 신경망 · 학습

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| actor · critic | [512, 256, 128] ELU (45 → 12, 60 → 1), init_noise_std 1.0, `empirical_normalization=False` | `코드 확인` ppo:16-22 | 표에 없음 |
| PPO | 24 step · 5 epoch · 4 mini-batch · lr 1e-3 adaptive · desired_kl 0.01 · γ 0.99 · λ 0.95 · clip 0.2 · value_loss_coef 1.0 · clipped value loss · **entropy 0.01** · max_grad_norm 1.0 | `코드 확인` ppo:12, 23-36 | 표에 없음 |
| max_iterations · save · num_envs | **50,000** · 100 · 4096 | `코드 확인` ppo:13-14 · go2cfg:371 | 표에 없음 |
| 기타 | `init_at_random_ep_len=True` · TF32 켬 · 시드는 BasePPORunnerCfg 에 없음(본체 기본값) · `--distributed` 면 rank 별 시드 | `코드 확인` train.py:43-45, 114-115, 132-143, 204 | 표에 없음 |
| 학습 시간 · GPU | README 에 없음 | | 표에 없음 |

### 7.6 unitree_rl_lab 보상 (Isaac Lab RewardManager 사용, weight × dt 0.02: 로컬 v2.3.2 reward_manager.py:150)

| 항목 | weight | params · 정의 위치 | 근거 (go2cfg) |
|---|---:|---|---|
| track_lin_vel_xy_exp | 1.5 | std 0.5 · 본체 | 273-275 |
| track_ang_vel_z_exp | 0.75 | std 0.5 · 본체 | 276-278 |
| lin_vel_z_l2 | -2.0 | 본체 | 281 |
| ang_vel_xy_l2 | -0.05 | 본체 | 282 |
| joint_vel_l2 | -0.001 | 본체 | 283 |
| joint_acc_l2 | -2.5e-7 | 본체 | 284 |
| joint_torques_l2 | -2e-4 | 본체 | 285 |
| action_rate_l2 | -0.1 | 본체 | 286 |
| joint_pos_limits | -10.0 | 본체 | 287 |
| energy | -2e-5 | Σ\|q̇\|·\|τ\| · **이 저장소** rew:22-28 | 288 |
| flat_orientation_l2 | -2.5 | 본체 | 291 |
| joint_position_penalty | -0.7 | 기본 자세 L2, 명령 0 · 속도 ≤ 0.3 이면 ×5 · **이 저장소** rew:67-76 | 293-301 |
| feet_air_time | 0.1 | threshold 0.5 · isaaclab_tasks | 304-312 |
| air_time_variance_penalty | -1.0 | 발 사이 air · contact time 분산 (0.5 clip) · **이 저장소** rew:155-166 | 313-317 |
| feet_slide | -0.1 | 본체 | 318-325 |
| undesired_contacts | -1 | threshold 1, Head · hip · thigh · calf | 336-343 |
| feet_contact_forces | (주석) -0.02 | 미사용 | 326-333 |

### 7.7 unitree_rl_lab 지형 · DR · 배포

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| 지형 | 생성기 이름 `COBBLESTONE_ROAD_CFG` 지만 sub_terrains 는 **`flat` (MeshPlaneTerrainCfg) 하나만**. random_rough · 경사 · boxes · 계단은 주석. 8 × 8 m, 10행 × 20열 | `코드 확인` go2cfg:24-64 | 표에 없음 |
| max_init_terrain_level | 1 | `코드 확인` go2cfg:77 | 2 |
| 지형 curriculum | `terrain_levels_vel` 등록 (go2cfg:362). 규칙은 로컬 v2.3.2 isaaclab_tasks 기준: 이동 거리 > 지형 길이/2 면 승급, < \|cmd_xy\| × 에피소드 길이 × 0.5 면 강등 | `코드 확인`(등록) · 규칙은 로컬 v2.3.2 `isaaclab_tasks/.../locomotion/velocity/mdp/curriculums.py:47-54` | 표에 없음 |
| 마찰 | 0.3 ~ 1.2 (static · dynamic), restitution 0 ~ 0.15, 64 bucket | `코드 확인` go2cfg:120-130 | 표에 없음 |
| 질량 | base 에 -1 ~ +3 kg | `코드 확인` go2cfg:132-140 | 표에 없음 |
| 외력 | reset 때 force · torque (0, 0) (범위 0) | `코드 확인` go2cfg:143-151 | 표에 없음 |
| push | 5 ~ 10 s 간격, x · y 속도 ±0.5 m/s | `코드 확인` go2cfg:179-184 | `push_robot=None` |
| CoM · Kp/Kd · 지연 무작위 | EventCfg 에 없음 | `코드 확인` go2cfg:115-184 | 표에 없음 |
| deploy.yaml | train.py 가 학습 시작 때 기록: 관절 매핑 · step_dt · kp · kd · default pos · 명령 limit · 행동 scale/offset/clip · 관측 항 scale/clip/history (noise 제외) | `코드 확인` train.py:196 · export:22-117 | 표에 없음 |
| 내보내기 | play.py 가 `exported/policy.pt` (JIT) · `exported/policy.onnx` | `코드 확인` play.py:142-152 | 표에 없음 |
| Go2 C++ 컨트롤러 | `deploy/robots/go2/` · unitree_sdk2 go2 DDS · ONNX Runtime linux-x64 1.22.0 · 실행 파일 `go2_ctrl`. 정책 스레드 0.02 s, FSM 1 kHz, 기울기 > 1.0 rad 면 Passive (학습 종료는 0.8 rad). FixStand 자세 [0, 0.8, -1.5] 는 학습 기본 자세와 다름 | `코드 확인` deploy/robots/go2/CMakeLists.txt · include/Types.h:3-6 · D/FSM/State_RLBase.h:15-47 · config.yaml:1-30 | 표에 없음 |
| sim2sim · sim2real 안내 | unitree_mujoco (저장소 밖) 연결 · `./g1_ctrl --network eth0` 예시. Go2 절차 문서는 없음 | `README 주장` README.md:88-141 | 표에 없음 |
| Go2 사전학습 정책 | 없음 (deploy/ 의 policy.onnx 는 g1_29dof 용) | `코드 확인`(파일 목록) | 표에 없음 |

### 7.8 isaac-go2-ros2 명령 경로 (ROS2 토픽 → 콜백 → 명령 텐서 → 정책)

| 단계 | 내용 | 근거 |
|---|---|---|
| 0. 퍼블리셔 | 이 저장소에 Nav2 설정 · launch · 파라미터 없음 (`nav2` grep 0건). README 는 NavRL 을 사용 예시로 링크 | `코드 확인`(없음) · README.md:106 |
| 1. 토픽 · 메시지 | 한 대면 `unitree_go2/cmd_vel`, 여러 대면 `unitree_go2_{i}/cmd_vel`. **`geometry_msgs/Twist`** (Stamped 아님), QoS depth 10 | `코드 확인` ros2/go2_ros2_bridge.py:4, 69-71, 88-91 |
| 2. 콜백 | `msg.linear.x` · `msg.linear.y` · `msg.angular.z` 를 `base_vel_cmd_input[env_idx][0..2]` 에 **그대로 대입**. clip · scale · 좌표 변환 · timeout(0 복귀) 없음 | `코드 확인` go2_ros2_bridge.py:320-323 (이 조사 세션 재확인) |
| 3. 명령 텐서 | 전역 `torch.zeros((num_envs, 3))`, CPU | `코드 확인` go2/go2_ctrl.py:11-16 |
| 3'. 키보드 | W/S · A/D · Z/C 가 같은 텐서에 ±1.5. 키를 떼면 텐서 전체 `zero_()` (ROS 값도 지워짐) | `코드 확인` go2_ctrl.py:24-63 |
| 4. 관측 항 | `base_vel_cmd = ObsTerm(func=go2_ctrl.base_vel_cmd)`, scale · clip · noise 없음, `clone().to(env.device)` | `코드 확인` go2/go2_env.py:83 · go2_ctrl.py:19-21 |
| 5. 명령 관리자 | `CommandsCfg.base_vel_cmd` 는 범위 전부 0 의 「dummy settings」. 정책은 4 의 전역 텐서를 읽음 | `코드 확인` go2_env.py:103-113 |
| 6. 순서 | `policy(obs)` → `env.step` → ROS 발행 → `rclpy.spin_once`. 새 명령은 다음 step 관측에 반영 | `코드 확인` isaac_go2_ros2.py:80-91 |
| 7. 주기 | `cfg/sim.yaml` freq 40 → decimation = ceil(1/0.005/40) = 5 (cfg 의 8 을 덮음) → **정책 40 Hz**, 물리 200 Hz | `코드 확인` cfg/sim.yaml:5 · isaac_go2_ros2.py:41-42 (이 조사 세션 재확인) |
| 8. 범위 대조 | 정책이 학습된 명령 범위는 이 저장소에 없음(체크포인트는 외부 학습). Nav2 출력 범위 설정도 없음 | `미확인` |

### 7.9 isaac-go2-ros2 정책 설정

| 항목 | 값 | 근거 | 우리 기준선 |
|---|---|---|---|
| task | `Isaac-Velocity-Rough-Unitree-Go2-v0` (Isaac Lab 기본 task, 저장소 밖), cfg 는 이 저장소 `Go2RSLEnvCfg` 로 넘김 | `코드 확인` isaac_go2_ros2.py:39-45 | 표에 없음 |
| 체크포인트 | `ckpts/unitree_go2/rough_model_7850.pt` (사용) · `flat_model_6800.pt` | `코드 확인` go2_ctrl_cfg.py:75-76 | 표에 없음 |
| 체크포인트 모양 | rough: actor 235 → 512 → 256 → 128 → 12, critic 235 → … → 1, iter 7850, normalizer 없음. flat: 48 → 128 → 128 → 128 → 12 | 정적 검사(하위 세션이 pickle 을 실행하지 않고 디스어셈블) | 235 |
| policy 관측 | 선속도 3 · 각속도 3 · 중력 3 · 명령 3 · 관절각 12 · 관절속도 12 · 직전 행동 12 · height scan (clip ±1). 비-height 48, 235 − 48 = 187 (`계산`). scale 없음, `enable_corruption=False` | `코드 확인` go2_env.py:75-101 | 235 중 187 |
| height scanner | 0.1 · [1.6, 1.0], `mesh_prim_paths=["/World/ground"]`. 장애물(`/World/obstacleTerrain`) · 창고(`/World/Warehouse`) prim 은 raycast 대상에 없음 | `코드 확인` go2_env.py:52-59 · env/sim_env.py:21, 46, 72, 96-99 | 표에 없음 |
| PD · actuator | Isaac Lab `UNITREE_GO2_CFG` (저장소 밖) | `미확인` | 표에 없음 |
| 행동 · sim | scale 0.25 · dt 0.005 · decimation 5 · num_envs 1 | `코드 확인` go2_env.py:64, 164 · sim.yaml:4 | 표에 없음 |
| 센서 퍼블리시 | odom (frame `map` → `base_link`, 50 Hz 목표) · TF `map → unitree_go2/base_link` (odom child 와 이름 다름) · LiDAR PointCloud2 (Hesai_XT32_SD10, 15 Hz 목표) · 전방 카메라 color · depth · semantic 640 × 480 · `/clock` | `코드 확인` go2_ros2_bridge.py:59-140, 209-275, 415-594 | 표에 없음 |

### 7.10 논문에 없고 코드에만 있는 것

두 저장소 모두 **논문 없음**. README 에도 없고 코드에서만 나오는 세부: unitree_rl_lab 의 Go2HV torque-speed 곡선 · 명령 curriculum 승급 조건(weight × 0.8, ±0.1, 1000 step 마다) · 로컬 보상 셋(energy · joint_position_penalty · air_time_variance_penalty) · 생성기 이름은 COBBLESTONE 이지만 평면 하나 · 학습 0.8 rad 대 배포 1.0 rad 종료 각 · deploy.yaml 자동 기록. isaac-go2-ros2 의 cmd_vel 무가공 대입 · 키보드 놓으면 전체 0 · 정책 40 Hz · height scanner 가 `/World/ground` 만 raycast.

### 7.11 우리 기계 요구사항 대조

| 항목 | unitree_rl_lab | isaac-go2-ros2 | 우리 환경 |
|---|---|---|---|
| OS | Linux (classifier · bash 런처 · 배포 C++). train.py 에 Isaac Lab 템플릿의 Windows 분기 문구가 있음 (train.py:75-76) | Ubuntu 22.04 | Windows 11 |
| Isaac Sim · Isaac Lab | 5.1.0 · 2.3.0 | 4.5.0 · 2.1.0 | 5.1.0 · 로컬 2.3.2 |
| Python | ≥ 3.10 | 3.10 | 3.11.15 |
| 런처 · 설치 | `unitree_rl_lab.sh -i` (bash · git lfs · pip -e · conda activate.d 기록) | `python isaac_go2_ros2.py` (hydra), requirements 없음 | PowerShell · Git Bash |
| 자산 | HF dataset `unitreerobotics/unitree_model` USD, `UNITREE_MODEL_DIR` 직접 수정 (asset:20) | Isaac Lab `UNITREE_GO2_CFG` · Nucleus USD | `미확인` |
| ROS2 | 불필요 | Humble · rclpy · cv_bridge · tf2_ros | `미확인` |
| 컴파일 | 학습 쪽 없음. 배포 쪽 CMake · C++ · unitree_sdk2 · yaml-cpp · boost · eigen · spdlog · fmt | 없음 | nvcc · MSVC 없음 |
| API 이름 | `ray_alignment="yaw"` | `attach_yaw_only=True` · `omni.isaac.ros2_bridge` 와 `isaacsim.ros2.bridge` 혼용 | 5.1 호환 `미확인` |

### 7.12 못 본 것 (이 절)

- Isaac Lab 본체 값 중 로컬 v2.3.2 로 채우지 않은 것: ObservationManager 의 noise · clip · scale 순서, 본체 보상 함수 정의, DelayedPDActuator 지연 기본값, RslRlOnPolicyRunnerCfg 의 seed · clip_actions 기본값, `reset_joints_by_scale` 의미, critic 그룹 매핑, ONNX 입력 이름. 그리고 2.3.0 과 로컬 2.3.2 의 차이.
- isaac-go2-ros2 의 PD (`UNITREE_GO2_CFG`), 체크포인트를 학습한 설정(명령 범위 · 관측 순서 · DR).
- 실행 결과 전부. unitree_sdk2 조이스틱 원값 범위. rclpy `spin_once` 동작. 브랜치 `isaacsim-4.2` · `isaacsim-4.5-docker`.

### 7.13 이 절의 가장 중요한 사실 다섯

1. unitree_rl_lab `Unitree-Go2-Velocity` 는 **평면 하나 · actor 45 · critic 60 (비대칭)** 이다. height scanner 는 scene 에만 있다 (go2cfg:24-64, 96-103, 222-265).
2. Go2 명령은 (vx ±0.1, vy ±0.1, wz ±1) 에서 (vx ±1.0, vy ±0.4, wz ±1.0) 까지 **lin_vel 만 curriculum 으로 넓어진다** (curr:11-37). heading_command 는 설정이 없어 로컬 v2.3.2 기본값 False. rel_standing_envs 0.1 · 재추출 10 s 는 우리 기준선과 같은 값이다.
3. 제어는 kp 25 · kd 0.5 · Go2HV torque-speed 곡선 · action scale 0.25 · 50 Hz. PPO 는 entropy 0.01 · 50,000 iteration. 배포 C++ 이 학습 때 자동 기록된 deploy.yaml 에서 관측 · scale · kp/kd · 관절 매핑을 읽는 구조다. Go2 정책 파일은 없다.
4. isaac-go2-ros2 의 cmd_vel 은 `Twist` 의 linear.x · linear.y · angular.z 가 **가공 없이** 정책 관측의 명령 3칸이 된다 (go2_ros2_bridge.py:320-323 · go2_env.py:83). 정책은 40 Hz 로 돈다. Nav2 설정과 학습 명령 범위는 이 저장소에 없다.
5. isaac-go2-ros2 의 `rough_model_7850.pt` 는 입력 235 · [512, 256, 128] · 출력 12 이고 관측 구성상 height scan 187 이다(우리 기준선과 같은 숫자). height scanner 는 `/World/ground` 만 raycast 하고 장애물 · 창고 prim 은 대상에 없다. 라이선스 파일이 없다.

---

## 8. MARG · START 공식 코드 공개 여부

> 하위 조사 세션이 검색했다. 이 조사 세션이 다시 한 것: `gh api repos/arclab-hku/Risky_gym/git/trees/HEAD` (README.md 와 docs/figs/*.gif 3개뿐, pushed_at 2025-05-14) · `gh search repos "Sparse Footholds Terrain Reconstruction"` · `"START sparse foothold"` (둘 다 결과 0).

### 8.1 MARG (arXiv 2509.20036)

| 항목 | 내용 | 근거 |
|---|---|---|
| 제목 | MARG: MAstering Risky Gap Terrains for Legged Robots with Elevation Mapping | arXiv |
| 저자 (표기 그대로) | Yinzhao Dong, Ji Ma, Liu Zhao, Wanyue Li, Peng Lu · ArcLab, The University of Hong Kong | arXiv |
| 게재 | 저장소 설명 「[IEEE T-RO 2025]」, 프로젝트 페이지 Paper 링크 ieeexplore 11196002 | 페이지 · gh api |
| 논문 안 링크 | 보충 영상(youtu.be/NOVmjvWUM8Y)만. 코드 링크 · 공개 문장 없음 | arXiv HTML v2 |
| 프로젝트 페이지 | astrorix.github.io/MARG/ (Astrorix/MARG 는 정적 페이지만) | 페이지 · gh api |
| 공식 코드 | 프로젝트 페이지 Code 버튼 → github.com/arclab-hku/Risky_gym, 버튼 문구 「Code(Comming Soon)」 | 페이지 |
| **상태** | **「coming soon」 자리만 있음.** 커밋 2개(2025-05-06, 2025-05-14), 트리는 README 와 gif 3개, README:25 「### Code Coming Soon」. README 에 Isaac Gym Preview 3 · rsl_rl · `train.py --task=go1` 사용법이 적혀 있지만 그 파일은 없다. 라이선스 없음 | gh api (이 조사 세션이 트리 재확인) |
| 비공식 재구현 | 못 찾음 | 검색 |

### 8.2 START (arXiv 2512.13153)

| 항목 | 내용 | 근거 |
|---|---|---|
| 제목 | START: Traversing Sparse Footholds with Terrain Reconstruction | arXiv |
| 저자 (표기 그대로) | Ruiqi Yu, Qianshi Wang, Hongyi Li, Zheng Jun, Zhicheng Wang, Jun Wu, Qiuguo Zhu · 주로 Zhejiang University | arXiv HTML v1 |
| 논문 안 링크 | 보충 영상(youtu.be/j85qVv_kVyI)만. 코드 · 프로젝트 페이지 링크와 공개 문장 없음 | arXiv |
| 프로젝트 페이지 | 못 찾음 | 검색 |
| **공식 코드** | **못 찾음** (논문이 미공개라고 밝힌 문장도 없으므로 「코드 미공개 확인」 이 아니라 「못 찾음」) | 검색 |
| 기타 | NVIDIA/warp PUBLICATIONS.md:70 에 목록으로만 올라 있음 | gh api |
| **비공식** 재구현 | shivam-sood00/Gurukul (Apache-2.0, 2026-08-10 생성): 「Experimental Go2/Isaac Lab adaptation inspired by START」, 「does not reproduce the paper's Lite3/Isaac Gym results」, 「No bundled checkpoint」, 지도 encoder 를 CNN 대신 MLP 로 단순화. task `Gurukul-Isaac-Velocity-Rough-Unitree-Go2-Start-v0`. 코드 내용은 안 읽음 | gh api (트리 · 문서만) |

쓴 검색어(하위 세션): `gh search repos` 로 "MARG legged" · "MARG gap terrain" · "Risky Gap Terrains" · "Mastering Risky Gap" · "2509.20036" · "MARG elevation mapping" · "MARG quadruped" · "gap terrain elevation mapping legged" · "Risky_gym" · "risky gym legged" · "START sparse footholds" · "Traversing Sparse Footholds" · "sparse footholds terrain reconstruction" · "2512.13153" · "START legged terrain reconstruction" · "sparse foothold quadruped" · "START Lite3" · "sparse footholds" · "sparse foothold" · "terrain reconstruction locomotion" · "sparse terrain quadruped heightmap reconstruction". `gh search code` 로 "2509.20036"(HTTP 408, 재시도 안 함) · "MAstering Risky Gap" · "2512.13153" · "Traversing Sparse Footholds". `gh api` 로 orgs/arclab-hku/repos · Astrorix/MARG · arclab-hku/Risky_gym · Gurukul. WebSearch 2회. 못 본 것: START 저자 개인 GitHub, MARG 의 T-RO 판 본문, Papers with Code · Hugging Face papers 연결, 선행 논문 arXiv 2409.15692 의 코드.

---

## 9. 못 본 것 (전체)

저장소별 세부는 각 절의 「못 본 것」에 있다. 여기에는 전체에 걸린 것과 1 · 2절(이 조사 세션이 직접 읽은 부분)의 것을 적는다.

**전체**
- **어떤 저장소도 설치 · 실행 · 학습하지 않았다.** 학습 시간 · VRAM · 수렴 · 성능 · Windows 동작 · MuJoCo · 실기 동작은 전부 `미확인` 이다.
- 3 · 4 · 5 · 6 · 7 · 8절은 하위 조사 세션 다섯이 읽었다. 이 조사 세션은 각 절 머리 인용문에 적은 행만 다시 열어 맞는지 확인했다. 나머지 행 번호는 하위 세션이 연 행이다.
- 각 저장소에 동봉된 체크포인트 · ONNX · npz 의 가중치와 텐서 모양은 isaac-go2-ros2(하위 세션이 pickle 을 실행하지 않고 정적 검사)를 빼면 열지 않았다. 공개 체크포인트가 현재 코드 설정으로 학습됐는지는 모두 `미확인`.
- 저장소 밖 라이브러리(Isaac Gym · rsl_rl v1.0.2 · unitree_sdk2 · unitree_mujoco · lejepa)의 기본값. Isaac Lab 쪽은 우리 로컬 v2.3.2 소스로 일부만 확인했고, 저장소가 요구하는 판(2.3.0 · 2.3.2.post1 · 2.1.0)과의 차이는 `미확인`.
- 논문 대조는 arXiv HTML(AME-2 · legged_gym 은 이 조사 세션이 직접, MoE-CTS · JEPLO 는 하위 세션이 WebFetch 요약으로)만 했다. PDF 원문은 어느 것도 보지 않았다. 「논문에 없다」 는 그 HTML · 요약에서 찾지 못했다는 뜻이다.
- 우리 쪽 Docker · ROS2 · Isaac Gym 설치 여부, Windows 에서 NCCL 다중 GPU 가 되는지.

**1절 ame2_minimal**
- G1 자산(`ame2/ame2/assets/g1_lidar/*.usd`)의 관절 · 링크 구성은 열지 않았다. 23관절은 `mdp/symmetry.py:149, 168` 의 assert 로만, 접촉 26 은 `symmetry.py:195, 206` 으로만 안다.
- `modelzoo/.../model_2400.pt` 미열람. `env.yaml`(2824행)은 핵심 키만 grep 했고 코드 cfg 와 전 항목 대조는 안 했다(대조한 것: num_envs 16000 · decimation 4 · dt 0.005 · num_rows/cols · max_init_terrain_level 5 · action scale 0.25 · episode 16 s · cone 45°). `agent.yaml` 은 전체를 읽었다.
- `custom_terrains.py`(1286행) 지형 함수 본문, `neural_mapping_utils.py` · `mid360_lidar.py` 본문, `play.py` 대부분, 번들 rsl_rl 의 `distillation.py` · `rnd.py` · storage.
- 논문 Eq. 4 · 5(move2goal · standatgoal)의 계수, 부록 B 의 CoM 범위.
- 「multi-head critic 의 K = 23」 은 cfg 의 RewTerm 수를 센 `계산` 이고, Isaac Lab RewardManager 의 `active_terms` 가 23 을 돌려주는지 실행으로 재지 않았다.

**2절 팀 보고서 대조**
- RunPod 볼륨(`limseokheon/ame2_go2`)의 v14 · v15 코드는 이 조사에서 열지 않았다. 보고서 값은 보고서가 적은 값이다. v15 의 critic 453 · 보상 21 이 코드의 어떤 항목인지는 코드 식에 Go2 를 넣어 셈한 `계산`(추정)이다.
- 보고서가 v15 에 어느 actor(AME2Model · AME2GazeModel)를 옮겼는지 적지 않아 확인하지 못했다.
