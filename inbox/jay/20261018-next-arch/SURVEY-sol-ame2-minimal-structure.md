# AME-2 minimal 실행 구조와 G1에서 Go2로 옮길 항목 조사

> 분류: 리서치
> 작성: sol · 2026-10-18
> 근거: 로컬 `ame2_minimal` 커밋 `8beb9a688d67882828019583f7d5a78e3517f233` · 설치된 Isaac Lab Go2 설정 · robot_lab Go2 URDF · conda import 탐침
> 요지: 공식 사본의 실행 사슬과 G1 결박점을 파일:행으로 표시하고 Go2 대체값의 출처와 미측정값을 나눈다
> 상태: 정적 조사 완료 · 일반 Python import 부분 확인 · Kit와 GPU 미실행

## 읽기 범위와 표기

`확인됨`: 아래 파일:행과 import 결과는 [AME-2 minimal 원본 저장소의 `8beb9a68` 커밋](https://github.com/leggedrobotics/ame2_minimal/tree/8beb9a688d67882828019583f7d5a78e3517f233) 로컬 사본 및 설치된 Go2 소스에서 직접 확인했다. `미측정`: Go2 Kit 안의 body ID·ray·접촉·성능이다.

아래 `A/`는 `C:/Users/AI-WS01/s2_lab/_research_repos/ame2_minimal/ame2/`, `R/`는 같은 저장소의 `rsl_rl/`, `I/`는 `C:/isaac/IsaacLab/source/`, `G/`는 `C:/isaac/ext/go2_rl_robotlab/`이다. `A/ame2/...`는 설치용 확장 루트 아래 Python 패키지를 뜻한다. `G/resources/go2/urdf/go2.urdf`는 Go2 URDF다. 이 조사에서 석헌 님 보고서와 RunPod 자료는 읽지 않았다. 값의 채택은 이 문서가 결정하지 않는다.

## 실행 구조 지도

| 연결 | 파일:행 · 확인한 동작 |
|---|---|
| 진입과 Kit 생성 | `A/scripts/rsl_rl/train.py:13-50`은 `AppLauncher` 인자를 받아 앱을 연다. `:83`, `:165-211`은 runner import, `gym.make`, `RslRlVecEnvWrapper`, `OnPolicyRunner` 또는 `DistillationRunner`, checkpoint load, `runner.learn`, `env.close`의 순서다. 참고 README의 기본 명령은 `README.md:28-35`의 `Ame2-G1-Gaze`다. |
| task 등록 | `A/ame2/__init__.py:9-12`가 task와 UI 확장을 import한다. `A/ame2/tasks/__init__.py:18-76`은 `Ame2-G1`, `-Play`, `-Gaze`, `-Gaze-Play`, `-Gaze-Student`, `-Gaze-Student-Play` 여섯 gym ID를 환경 cfg와 runner cfg에 결선한다. `-Gaze`는 기본 G1 환경에 gaze actor runner를 붙이고, student는 별도 센서·관측 cfg를 쓴다. |
| 환경과 행동 | `A/ame2/tasks/ame2_env_cfg.py:43-140`은 지형·G1·광선·접촉·가속도 센서 장면, `:150-176`은 목표 위치·방향 명령과 지연 관절 위치 행동, `:656-711`은 4096 env, decimation 4, 물리 dt 0.005초, episode 16초, G1 asset와 센서 주기를 설정한다. |
| 관측과 정책 | `A/ame2/tasks/ame2_env_cfg.py:183-318`은 teacher 지형 지도·현재 몸 관측과 critic, 20-step student 몸 이력·명령 그룹이다. `R/rsl_rl/models/AME2_models.py:17-85,137-181`은 지도 점 FC·CNN, 전역 max, 32-head MHA, 행동 MLP다. `A/ame2/tasks/agents/rsl_rl_ppo_cfg.py:148-199`는 24 step, 5000 iteration, AME2 또는 Gaze actor, 16-expert MoE critic, PPO를 결선한다. `:81-115`의 알고리즘 기본값은 Muon optimizer와 mixed precision이며 설정별 유효값 확인이 필요하다. |
| 명령과 사건 | `A/ame2/tasks/mdp/commands.py:18-90`은 지형 flat patch에서 전방 원뿔 안 목표를 고른다. 환경 cfg `:153-162`는 16.01초 재표본, heading ±π/3, cone 45도를 둔다. `ame2_env_cfg.py:322-405`는 마찰·질량·COM·actuator gain 시작 무작위화와 root·joint reset·보조 힘 사건을 묶는다. |
| 보상·종료 | `A/ame2/tasks/ame2_env_cfg.py:409-569`가 목표 위치·heading·정지, 조기 종료, 회전·도약·접촉·미끄럼·자가 충돌, 관절·가속도·힘·상체·발 형상 항을 등록한다. 함수는 `A/ame2/tasks/mdp/rewards.py:35-674`에 있다. `ame2_env_cfg.py:573-613`는 시간·중력·hip 가속도·불법 접촉·정체 종료를 등록하고 구현은 `mdp/terminations.py:31-180`이다. |
| 난도와 지형 | `A/ame2/tasks/ame2_env_cfg.py:617-647`은 terrain level, 시작 yaw, 목표 원뿔, teacher 지도 잡음 curriculum이다. 함수는 `mdp/curriculums.py:165-329`에 있다. `A/ame2/tasks/terrains.py:14-279`는 12×12 m, 10행×60열의 rough·stairs·boxes·obstacles·climb·gap·beam·stones 등을 등록한다. 형상 생성은 `custom_terrains.py:105-1261`에 있다. |
| 센서 분기 | teacher 광선은 `ame2_env_cfg.py:70-96`의 yaw 정렬 26×15 격자와 `mdp/observations.py:89-199`의 높이·점 지도다. student는 `ame2_env_cfg.py:761-818`에서 Mid360 10 Hz와 신경 지도 10 Hz를 더한다. 구동은 `A/ame2/sensors/mid360_lidar.py:32,96-124,197`, `livox_neural_map_sensor.py:16-401`이며 지도 관측 변환은 `mdp/observations.py:201-228`이다. |
| runner와 저장 | `R/rsl_rl/runners/on_policy_runner.py:26-56,77-143`가 rollout와 update를 돌리고 `save_interval`에 `model_<it>.pt`, 종료 때 최신 모델을 저장한다. `:146-170`은 모델·optimizer·iteration을 `torch.save`하고 복원한다. 설정은 `A/ame2/tasks/agents/rsl_rl_ppo_cfg.py:148-153`의 2000회 간격이다. 학생 `PPO_IL`과 frozen teacher 경로는 `:200-246`, `R/rsl_rl/algorithms/ppo_il.py:62-326`이다. |

`ame2_minimal`은 기본 teacher, gaze teacher, lidar student를 한 진입점 아래에 두지만 동일한 입력이나 학습 단계를 뜻하지 않는다. 특히 student의 지도는 teacher ray 지도 대신 별도 추정 경로다.

## G1 결박점과 Go2 출처

| G1 코드와 교체 대상 | Go2에서 확인한 출처 · 아직 잴 것 |
|---|---|
| asset·몸 형상: `A/ame2/assets/unitree.py:12-48`은 `g1_lidar.usd`, 몸 높이 0.78 m, hip·knee·ankle·waist·arm 기본 자세다. 장면은 `ame2_env_cfg.py:690`에서 이 asset을 넣는다. | `I/isaaclab_assets/isaaclab_assets/robots/unitree.py:140-181`의 `UNITREE_GO2_CFG`는 Go2 USD, 높이 0.4 m, 12 leg joint와 DC motor를 준다. 이 프로젝트의 URDF 경로와 높이 0.42 m 후보는 `G/source/robot_lab/robot_lab/assets/unitree.py:73-155`의 `GO2_CFG_ROBOTLAB`이다. 두 asset은 생성 방식과 자기 충돌 설정이 달라 하나를 정해야 한다. URDF의 base 질량 6.921 kg은 `G/resources/go2/urdf/go2.urdf:3-6`, 앞·뒤 hip의 x ±0.1934 m, y ±0.0465 m는 `:79-84,246-251,413-418,580-585`; thigh 옆 offset과 calf 0.213 m, foot 고정 offset 0.213 m는 `:117-160,221-224` 등이다. 전체 충돌체·발 지지 폭과 scanner 장착 높이는 **잴 것**. |
| 관절·순서·대칭: `A/ame2/assets/unitree.py:31-45,49-175`는 G1 hip yaw/roll/pitch, knee, ankle pitch/roll, waist, shoulder, elbow를 제어한다. `A/ame2/tasks/mdp/symmetry.py:22-115`는 23개 G1 action index와 좌우 부호·관측 순서를 고정한다. `ame2_env_cfg.py:169-175`의 `joint_names=[".*"]`는 G1 모든 관절을 행동으로 쓴다. | Go2 URDF는 `FL/FR/RL/RR × hip/thigh/calf`의 revolute 12개다 (`G/resources/go2/urdf/go2.urdf:79-160,246-327,413-494,580-661`). Go2 프로젝트의 순서는 `G/source/robot_lab/robot_lab/assets/unitree.py:148-171`의 `joint_sdk_names`와 기존 cfg의 `JOINT_NAMES`를 참조한다. 23-index 대칭·팔·허리 관측은 재사용 불가. 실제 PhysX joint 이름과 순서는 **잴 것**. |
| 링크·발·자가 충돌: G1은 `base`, `torso_link`, `head_link`, `pelvis_contour_link`, `.*hip_pitch_link`, `.*ankle_roll_link`, 좌우 knee·ankle·어깨·팔꿈치·손목, `d435_link`, `mid360_link`, IMU dummy를 참조한다 (`ame2_env_cfg.py:74-130,205-214,426-568,580-603`). knee·ankle·torso 상호 접촉 센서 3개도 G1 링크에 묶인다 (`:99-128`). | Go2 URDF는 `base`, `FL_foot`, `FR_foot`, `RL_foot`, `RR_foot`과 네 다리의 hip·thigh·calf 링크를 제공한다 (`G/resources/go2/urdf/go2.urdf:3,60-224,227-391,394-558,561-725`). Go2 cfg는 foot 정규식 `.*_foot`, 전신 contact sensor `Robot/.*`를 쓴다 (`G/source/robot_lab/robot_lab/tasks/go2/env_cfg.py:30-32,81-85`). G1 torso/head/ankle/arm 정규식이 Go2에서 몇 body ID와 매칭되는지, 자기 충돌 센서 쌍을 유지할지, foot ID 순서는 **잴 것**. |
| PD·토크·행동: G1 asset은 hip 88/139 stiffness, knee 139, ankle 35 등 DC motor 그룹과 effort 88/139 등을 지정한다 (`A/ame2/assets/unitree.py:49-175`). 행동은 0.25 rad scale, 기본 자세 offset, 0~1 step delay다 (`ame2_env_cfg.py:169-175`). | Isaac Lab `UNITREE_GO2_CFG`는 effort/saturation 23.5, velocity 30, stiffness 25, damping 0.5의 12-leg motor다 (`I/isaaclab_assets/isaaclab_assets/robots/unitree.py:161-181`). robot_lab URDF cfg에는 stiffness 20, damping 0.5 후보가 있다 (`G/source/robot_lab/robot_lab/assets/unitree.py:134-155`); 현재 Go2 task action 0.25와 delay가 있는 actuator 후보는 `G/source/robot_lab/robot_lab/tasks/go2/env_cfg.py:108-115` 및 `G/source/robot_lab/robot_lab/assets/unitree.py:157-171`이다. URDF 관절별 한계는 위 URDF revolute `limit` 행에 있다. 어느 motor 모델과 delay가 실제 Go2 실행에 맞는지는 **잴 것**. G1 gain·armature 무작위화(`ame2_env_cfg.py:357-367`)도 그대로 옮기지 않는다. |
| 지도·광선·몸 높이: G1 teacher는 base 부착, x offset 0.5 m·z 20 m, 0.08 m, 2.0×1.12 m, 26×15 grid, yaw 정렬, drift ±0.04 m다 (`ame2_env_cfg.py:70-96`). 지도 높이 offset 0.74 m, 무효 hit 처리는 `:217-234`, `mdp/observations.py:89-199`. student mapping 범위는 ±3.0×±1.5 m에 0.03 m 소스 격자, 출력 26×15/0.08 m (`A/ame2/sensors/livox_neural_map_sensor.py:371-402`). | Go2 scene의 base 부착 scanner는 `G/source/robot_lab/robot_lab/tasks/go2/env_cfg.py:65-80`; Go2의 0.4/0.42 m 몸 높이 후보와 URDF 다리 길이를 출발 근거로 쓰되 **실제 스캔 x/y 범위, offset, 지도 높이 기준, 무효 hit 빈도, ray 순서, 축 방향, 26×15 유지 가능성은 잴 것**. 원문의 G1 0.74 m offset을 Go2에 복사하지 않는다. |
| 접촉·보상·종료: G1 contact history 4, air time, 모든 body sensor(`ame2_env_cfg.py:83-85`), 접촉 상태에서 질량 >0.1 kg·1 N (`:205-214`), `torso_link` 질량·COM 랜덤화와 보조 힘(`:338-355,399-404`), torso/head/ankle/hip·팔 정규식이 보상·종료에 박혀 있다 (`:413-613`). `link_contact_forces`의 `robot_weight=400`도 G1 값이다 (`:524-530`). | Go2는 `base`와 `.*_foot` 및 contact sensor `Robot/.*`가 기본 대체 이름 출처다 (`G/source/robot_lab/robot_lab/tasks/go2/env_cfg.py:30-32,81-85`). URDF base 질량은 6.921 kg, 각 발 link 질량은 0.04 kg이다 (`G/resources/go2/urdf/go2.urdf:3-6,202-206,369-373,536-540,703-707`). G1의 `mass_threshold=0.1`을 그대로 쓰면 Go2 발 접촉 상태가 빠질 수 있으므로 threshold와 의도한 body 집합은 **잴 것**. Go2 전체 중량, 1 N 발 접촉 판정, torso 질량 편차, 링크별 힘 정규화 기준, 도약·미끄럼·상체·발 yaw 항의 적용 여부와 종료 임계값도 **잴 것**. G1 reward의 torso·ankle·shoulder 대상 이름을 Go2에 그대로 두면 빈 매치나 잘못된 매치가 난다. |
| 목표·지형·curriculum: G1 목표는 flat patch와 전방 cone을 쓰고 tile은 12×12 m (`ame2_env_cfg.py:153-162`, `commands.py:18-90`, `terrains.py:14-279`). gap은 0.18~1.2 m, stones는 box 0.41~0.71 m·간격 0.08~0.12 m (`terrains.py:162-223`). 난도는 목표 거리와 진도에 따라 옮긴다 (`ame2_env_cfg.py:620-647`, `mdp/curriculums.py:292-329`). | Go2 URDF hip 간격과 다리 길이는 위 URDF 출처다. Go2에 가능한 gap·stone·beam 폭과 성공 판정, 목표의 안전 flat patch 크기, tile 크기, 16초 episode에서의 도달률은 **잴 것**. G1 난도 범위를 성능 근거 없이 Go2에 복사하지 않는다. |
| 학생 센서·외부 가중치: G1 `mid360_link`의 10 Hz lidar와 신경 지도(`ame2_env_cfg.py:774-818`), `Mid360` ray 방향 파일(`A/ame2/sensors/mid360_lidar.py:110-116`), `g1LivoxMapping_perframe.pt` 및 `g1_gaze_teacher_isaaclab.jit`가 필요하다 (`livox_neural_map_sensor.py:49-54,379`, `agents/rsl_rl_ppo_cfg.py:200-220`). | Go2 URDF에 `mid360_link`가 없다. 장착 위치·시야·스캔 주기·mapping 모델의 Go2 재사용성은 **잴 것**. 로컬 이 커밋에는 `mid360_raydirs.npy`는 있으나 위 두 NN 모델 파일은 없다. 학생 학습 진입은 경로만 바꿔도 성립하지 않는다. |

## 설치 없는 conda import 탐침

`isaac311-moects/python.exe -B`, `CUDA_VISIBLE_DEVICES=-1`, `PYTHONDONTWRITEBYTECODE=1`로 경로만 `sys.path`에 넣어 확인했다. 설치 명령은 실행하지 않았다. `find_spec` 기준 `ame2/ame2`와 번들 `rsl_rl/rsl_rl`의 위치가 잡힌다. `from rsl_rl.models.AME2_models import AME2Model`은 **PASS**했다. `import ame2`는 **FAIL: `ModuleNotFoundError: No module named 'omni'`**이며 traceback은 `A/ame2/__init__.py:12` → `A/ame2/ui_extension_example.py:6`의 `import omni.ext`다. 일반 conda Python에서 Isaac Lab 패키지 이름은 보여도 Kit의 `omni`, `carb`, `pxr`는 `find_spec`에서 없었다. 따라서 이 환경의 **Kit 없는 완전한 AME-2 extension import는 불가**다. Kit 안 import는 미확인이다.

의존성 선언은 `A/setup.py:23-27`의 `psutil`, `A/config/extension.toml:17-22`의 `isaaclab`, `isaaclab_assets`, `isaaclab_mimic`, `isaaclab_rl`, `isaaclab_tasks`, `R/pyproject.toml:27-35`의 `torch>=2.6`, `torchvision`, `tensordict`, `numpy`, `GitPython`, `onnx`, `onnxscript`다. 정적 import에는 `gymnasium`, `toml`, `trimesh`, `scipy`, Kit의 `omni`·`carb`·`pxr`도 보인다. 탐침에서 `torch`, `torchvision`, `tensordict`, `numpy`, `git`, `onnx`, `onnxscript`, `gymnasium`, `psutil`, `toml`, `trimesh`, `scipy`는 발견됐다. 발견은 버전 적합성이나 Kit import 성공을 증명하지 않는다. 이 사본의 G1 student가 요구하는 외부 두 NN 파일도 부재하므로 student 실행 가능 판정은 **미확인**이다.

## lead가 합칠 때 남는 결정

Go2 asset은 Isaac Lab USD와 robot_lab URDF 가운데 하나를 고정하고, 실제 Kit에서 joint·body ID와 충돌·발 센서 대응을 확인해야 한다. 그 결과에 따라 G1의 23-index 대칭, contact·보상·종료 link regex, 몸 높이·지도 격자·목표·지형 폭, student lidar 장착 및 외부 가중치 계약을 Go2 값으로 확정한다. 이 조사에는 코드 수정, 설치, Kit/GPU 실측과 Go2 학습 결과가 없다.
