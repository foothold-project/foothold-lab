# Isaac Lab Go2 험지 학습: cfg를 읽는 커리큘럼

> 요지: 공식 Go2 rough 환경이 로봇·지형·명령·보상·시간축을 어떻게 묶는지, 요약 다음에 상세로 읽는다.
> 작성 2026-08-25 · 원본: 팀 스터디 필기 `IsaacLab_Go2_험지학습_요약.md` · `IsaacLab_Go2_험지학습_상세.md`. 공식 클래스명으로 재정리.
> 이 문서가 답하는 것: **학습 cfg를 열기 전에 무엇을 어떤 순서로 읽는가.** 커스텀 험지 설계는 [지형 가이드](terrain-guide-isaaclab.md), 숫자 실측은 [학습 성능 실측](training-benchmarks.md).
> 클래스명·기본값·Go2 오버라이드는 Isaac Lab 공식 `UNITREE_GO2_CFG` · `LocomotionVelocityRoughEnvCfg` · `UnitreeGo2RoughEnvCfg` · `ROUGH_TERRAINS_CFG` 기준 `확인됨`. 스터디 때 나온 실험 감각은 팀 실측과 맞춰 표시한다.

## 이 장을 읽는 순서

1. 아래 **요약**만 먼저 읽는다. 흐름·숫자·손대는 축이 한 장이다.
2. 보상·시간축·Go2 오버라이드가 막히면 **상세**로 내려간다.
3. 지형 종류를 더 고르려면 [지형 가이드](terrain-guide-isaaclab.md) (공식 21종).
4. 학습을 돌린 뒤에는 [학습 성능 실측](training-benchmarks.md)과 [일반화 벤치마크](generalization-benchmark-10-terrains.md).
5. 실패한 지형을 이어서 학습할 계획은 [파인튜닝 계획](terrain-finetune-plan.md).

8/19 이후 정본: 우리 학습 정책의 **실기 저수준 이전은 목표에서 빠진다** `확인됨`. 상세의 증류·ONNX·Orin 경로는 Isaac 계열의 일반 실기 배포 그림이지, 지금 트랙 A/B의 필수 단계가 아니다.

---

# 요약

## 흐름

```
로봇 Asset → 지형 Generator → Scene / Sensors
→ Commands · Actions · Observations
→ Events · Rewards · Terminations
→ PPO 학습 → Checkpoint
```

그 다음이 실기 배포라면 증류 → ONNX → Orin NX가 일반 경로다. **지금은 시뮬 안에서 평가·트윈·렌더로 닫는다** ([프로젝트 보고서](../REPORT.md)).

| 역할 | 클래스 / 파일 |
|---|---|
| 로봇 | `UNITREE_GO2_CFG` |
| 공통 Env | `LocomotionVelocityRoughEnvCfg` (`velocity_env_cfg.py`) |
| Go2 특화 | `UnitreeGo2RoughEnvCfg` (`go2/rough_env_cfg.py`) |
| 지형 | `ROUGH_TERRAINS_CFG` / `TerrainGeneratorCfg` |

## 로봇 · 스폰

- 발 접촉 센서 ON, `disable_gravity=False`
- damping · depenetration · self-collision · solver는 **안정성 우선**
- 초기 높이 약 **0.4 m**. 학습에 쓰는 관절 한계는 물리 범위의 일부
- 리셋 때 기지는 같되 `x` · `y` · `yaw`는 조금씩 달라질 수 있다

## 험지 6종 (공식 rough 예제)

Mesh는 계단·박스처럼 각진 형상, Height Field(HF)는 울퉁불퉁·경사. `curriculum=True`이면 잘하면 어려운 행, 못하면 쉬운 행으로 돌아간다.

| Key | 뜻 | 손잡는 파라미터 |
|---|---|---|
| `pyramid_stairs` / `_inv` | 오르막·내리막 계단 | `step_height_range`, `holes` |
| `boxes` | 격자 높이 랜덤 | `grid_height_range` |
| `random_rough` | 유선형 울퉁불퉁 | `noise_range`, `noise_step` |
| `hf_pyramid_slope` / `_inv` | 경사·역경사 | `slope_range` |

`proportion=0.2`이면 그 지형이 약 20%. 경사 두 종은 예제에서 각 10%. 전체 21종은 [지형 가이드](terrain-guide-isaaclab.md).

## Env 핵심

| 항목 | 값 / 의미 |
|---|---|
| `terrain_type` | `"generator"` (코드로 생성) |
| `num_envs` | 4096 |
| height_scanner | **base**에 붙이고 지형만 측정. 격자·오프셋을 실기와 맞추는 일이 sim-to-real의 핵심이었으나, 지금은 시뮬 평가 정합에 쓴다 |
| commands | `base_velocity`. 주기적 재샘플. 일부 env는 서 있으라는 명령 |
| actions | `목표 = default + action × scale` |
| events | startup(질량·마찰·CoM) / reset(pose·joint) / interval(`push_robot`) |

**Go2 오버라이드 요점**

- 소형 로봇이라 boxes · rough **높이를 낮춘다**. 실무 감각: 단차 약 16 cm 이상은 넘기 어렵다 `추측`
- `push_robot = None`, 관절 리셋 `(1.0, 1.0)`
- `feet_air_time`의 body는 `.*_foot`

## 시간축

| 개념 | 값 |
|---|---|
| physics `dt` | 0.005 s (200 Hz) |
| `decimation` | 4 |
| 정책 주기 | **0.02 s (50 Hz)** |
| episode | 최대 20 s |
| 병렬 | 4096 envs |

물리 4틱마다 정책 1회. 1,500 iteration 벽시계는 스터디 메모 약 104분, 팀 완주 실측은 **133분** (2026-08-12) `확인됨`.

## 보상 · 종료 · 실험 규칙

| Term | 역할 |
|---|---|
| `track_lin_vel_xy_exp` / `track_ang_vel_z_exp` | 명령 추종 |
| `lin_vel_z_l2` 등 | 튀김·흔들림 벌점 |
| `feet_air_time` | 착지 때 정산. 잔발·발끌기 억제 |
| `dof_torques_l2` / `dof_acc_l2` | 과토크·급가속 억제 |
| `base_contact` | 몸통 접촉이면 에피소드 종료 |

**한 번에 가중치 1개만 바꾼다.** mean reward는 에피소드 총점 평균이지 통과율이 아니다.

충돌 근사 플래그(`collisionApproximateCylinders`)는 **쓰지 않는다**. 봉인 `확인됨` ([학습 실측 §2](training-benchmarks.md)).

시각화: 초록 화살 = 명령(command), 파랑 = 실제 속도.

실패는 낙상과 **20초 안에 목표 거리를 못 가서 timeout**을 가른다. 난이도 곡선에서 실패의 주원인은 넘어짐이 아니라 느림이었다 `확인됨`.

---

# 상세

## 1. 전체 그림

Isaac Sim / Isaac Lab에서 Unitree Go2 보행 정책을 학습하는 조립 순서다.

```
[로봇 Asset 설정] → [지형 Generator] → [Scene / Sensors]
        ↓
[Commands · Actions · Observations]
        ↓
[Events(Domain Randomization) · Rewards · Terminations]
        ↓
[LocomotionVelocityRoughEnvCfg] → PPO → Checkpoint
```

Isaac Lab 안에는 Unitree 계열 모델이 여러 대 있다. 이 장의 대상은 **Go2**다.

저장소 안 위치 (Isaac Lab):

```
isaaclab_assets/robots/unitree.py
    → UNITREE_GO2_CFG

isaaclab_tasks/.../locomotion/velocity/velocity_env_cfg.py
    → LocomotionVelocityRoughEnvCfg
    → scene, commands, actions, rewards, events, curriculum

isaaclab_tasks/.../locomotion/velocity/config/go2/rough_env_cfg.py
    → UnitreeGo2RoughEnvCfg
    → UnitreeGo2RoughEnvCfg_PLAY
```

PLAY cfg는 env 수를 줄이고, curriculum·랜덤 푸시를 끄고, 관측 노이즈(`enable_corruption`)를 끈다. 학습이 아니라 **재생·확인**용이다 `확인됨`.

## 2. 로봇 모델 (`UNITREE_GO2_CFG`)

모델 생성 단계에서 물리 엔진이 얼마나 현실적으로, 얼마나 안정적으로 움직일지가 갈린다.

| # | 항목 | 의미 | 메모 |
|---|---|---|---|
| 1 | USD / mesh path | 3D 모델 경로 | Unitree Go2 USD |
| 2 | Contact sensors (feet) | 발바닥 접촉 | `True`. 착지·공중 시간 보상, 종료 판정에 필요 |
| 3 | `disable_gravity` | 중력 끄기 | `False`: 중력을 받는다 |
| 4 | Damping (`linear` / `angular`) | 선·각속도 감쇠 | 시뮬이 덜 흔들리게 넣는 경우가 많다 |
| 5 | max linear / angular velocity | 속도 상한 | 예: `1000.0` (사실상 넉넉한 천장) |
| 6 | Depenetration velocity | 겹침을 밀어내는 속도 | 크면 튀고, 작으면 침투가 남는다 |
| 7 | Self-collision | 로봇 자신끼리 충돌 | 끄면 빠르고, 켜면 현실적이지만 불안정해질 수 있다 |
| 8 | Solver position iterations | 위치 오차 재계산 횟수 | 늘리면 안정, 줄이면 비용 감소 |

시뮬에서 «물리적으로 가능한 것»과 «학습에 안정적인 것»은 다를 수 있다. 댐핑·충돌·솔버는 **안정성 우선**으로 둔다.

관절 한계는 물리 범위의 **일부만** 학습에 쓰는 경우가 있다. 끝까지 열면 불안정해지기 쉽다. 액추에이터는 최대 출력(effort / torque)과 `stiffness` / `damping`으로 실기 모터에 가깝게 맞춘다.

## 3. 스폰 (에피소드 시작 자세)

| 항목 | 영문 | 설명 |
|---|---|---|
| 초기 위치 | `init_state.pos` | 기본 높이 예: 약 0.4 m |
| 관절 각도 | `joint_pos` | 기본 스탠스 |
| 관절 속도 | `joint_vel` | 보통 0 |
| Soft / hard limit | joint limit | 물리는 더 열려도 학습 안정성 때문에 조인다 |
| Actuator effort | max effort | 모터 최대 출력에 대응 |

리셋은 «같은 기지, 다른 좌표»가 기본 감각이다. `reset_base`의 `pose_range`에서 `x`, `y`, `yaw`를 랜덤 샘플링한다.

## 4. 험지 설정

### Mesh vs Height Field

| 방식 | 특징 | 대표 |
|---|---|---|
| Mesh | 각진 장애물 (계단, 박스 그리드) | `pyramid_stairs`, `boxes` |
| Height Field | 연속 굴곡·경사 | `random_rough`, `hf_pyramid_slope` |

둘을 섞어 하나의 그리드 맵을 만든다. `ROUGH_TERRAINS_CFG`는 공식 21종 전체가 아니라 **예제 혼합**이다 `확인됨`.

### Terrain Generator 공통

| 항목 | 영문 | 설명 |
|---|---|---|
| 서브 지형 크기 | `size` | 각 sub-terrain의 가로·세로 (m) |
| 테두리 | `border_width` | 지형 간·외곽 경계 |
| 경사 임계 | `slope_threshold` | 너무 가파르면 수직벽처럼 다루거나 그 방향으로 가지 않게 |
| Curriculum | `curriculum=True` | 성능이 오르면 더 어려운 난이도 행으로 |

승급 규칙의 팀 정본: 에피소드 동안 타일의 절반 이상을 이동하면 한 행 위로, 못 가면 아래로 (`terrain_levels_vel`) `확인됨` ([흐름 §2](../FLOW.md)).

### 6종 sub-terrain (ROUGH 예제)

각 타입 `proportion`의 합이 정규화되어 비율이 된다.

| Key | 클래스 예 | 설명 | 주요 파라미터 |
|---|---|---|---|
| `pyramid_stairs` | `MeshPyramidStairsTerrainCfg` | 올라가는 피라미드 계단 | `step_height_range`, `holes` |
| `pyramid_stairs_inv` | `MeshInvertedPyramidStairsTerrainCfg` | 내려가는 계단 | 동일 |
| `boxes` | `MeshRandomGridTerrainCfg` | 격자 박스 높이 랜덤 | `grid_height_range` |
| `random_rough` | `HfRandomUniformTerrainCfg` | 유선형 울퉁불퉁 | `noise_range`, `noise_step` |
| `hf_pyramid_slope` | `HfPyramidSlopedTerrainCfg` | 사다리꼴 경사 | `slope_range` |
| `hf_pyramid_slope_inv` | `HfInvertedPyramidSlopedTerrainCfg` | 역경사 | `slope_range` |

- `holes=True`: 위에서 보면 십자만 남기고 모서리를 뺀다. 좁은 영역으로 올라가게 유도한다.
- `noise_step`: HF rough를 샘플할 때의 해상도.
- 난이도 행이 오르면 `step_height_range` 같은 (min, max) 구간을 보간한다.

예제 스케치:

```python
sub_terrains={
    "pyramid_stairs": terrain_gen.MeshPyramidStairsTerrainCfg(
        proportion=0.2,
        step_height_range=(0.05, 0.23),
        holes=False,
    ),
    "pyramid_stairs_inv": ...,
    "boxes": terrain_gen.MeshRandomGridTerrainCfg(
        proportion=0.2,
        grid_height_range=(0.05, 0.2),
    ),
    "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
        proportion=0.2,
        noise_range=(0.02, 0.10),
        noise_step=0.02,
    ),
    "hf_pyramid_slope": terrain_gen.HfPyramidSlopedTerrainCfg(
        proportion=0.1,
        slope_range=(0.0, 0.4),
    ),
    "hf_pyramid_slope_inv": ...,
}
```

공통 cfg의 난이도 0→9 감각 ([흐름 §2](../FLOW.md) `확인됨`):

| 지형 | 비율 | 난이도 0 → 9 |
|---|---|---|
| 계단 오름 · 내림 | 각 20% | 단 높이 0.05 → 0.23 m |
| 랜덤 박스 | 20% | 0.05 → 0.20 m |
| 무작위 요철 | 20% | 0.02 → 0.10 m |
| 경사 오름 · 내림 | 각 10% | 기울기 0 → 0.4 (약 22도) |

Go2 전용 cfg는 아래 §6처럼 박스·요철 높이를 이보다 **낮춘다**.

## 5. 공통 환경 (`LocomotionVelocityRoughEnvCfg`)

### Scene · Ground

| 항목 | 설명 |
|---|---|
| `terrain_type="generator"` | 고정 맵 파일이 아니라 코드로 생성 |
| `max_init_terrain_level` | 초기 난이도 상한. 예: 5 |
| `collision_group=-1` | 병렬 로봇이 ground collision을 같이 쓰는 패턴 |
| Physics material | 마찰·반발. combine mode 예: `"multiply"` |

정지 마찰과 동적 마찰, restitution(반발)을 여기서 준다.

### Height scanner · 접촉

| 항목 | 설명 |
|---|---|
| Robot | 공통 cfg에서는 `MISSING`. 로봇별 cfg가 주입 |
| Scanner offset | 보통 **base(몸통)** |
| Mesh prim filter | 몸·다리는 통과하고 **지형만** 높이 측정 |
| Contact forces | 몸통이 바닥에 닿으면 실패 판정 |
| `track_air_time` | 부위가 공중에 떠 있는 시간 추적. `True` |

height scan의 단위·오프셋·격자(예: 10 cm)가 점수에 영향을 준다. 187점(앞뒤 1.6 m × 좌우 1.0 m, 10 cm 격자)의 풀이는 [흐름 §3](../FLOW.md).

### Commands

로봇에게 «몸통이 따라가야 할 목표 속도»를 내린다.

| 항목 | 설명 |
|---|---|
| `base_velocity` | 선속도·각속도 명령 |
| `resampling_time_range` | 몇 초마다 새 명령을 뽑을지 |
| `rel_standing_envs` | 일부 env는 «서 있어라». 예: 약 2% |
| `heading_command` | 끄면 지정 속도만 추종. 켜면 방향만 주고 정책이 요를 맞춘다 |
| `ranges` | 명령 범위 = 난이도 |

### Actions · Observations

정책 출력은 절대 각도가 아니라 **기본 자세 기준 오프셋**이다.

`목표 = default + (action × scale)`

관측 대표: `base_lin_vel`, `base_ang_vel`, `projected_gravity`(기울기), joint pos/vel, height scan, last action. 학습 전에 `ObservationsCfg`를 한 번 읽는다. 노이즈는 센서 오차 모사(강건성)용이다.

### Events (domain randomization)

같은 설정인데 어제와 오늘이 달라지는 이유 중 하나이자, 특정 시뮬 세팅에만 특화되지 않게 넣는 외란이다.

| 시점 | 예 |
|---|---|
| startup | 마찰·반발, `add_base_mass`, CoM(`base_com`) |
| reset | 스폰 pose/vel, joint 위치 |
| interval | `push_robot` (학습 중 밀어내기) |

질량·CoM을 충분히 흔드는 편이 시뮬 특화를 줄인다. 난이도 손잡이로도 쓴다.

### 한 클래스로 묶는 숫자

| 항목 | 전형값 |
|---|---|
| `scene.num_envs` | 4096 |
| `env_spacing` | 2.5 |
| `decimation` | 4 |
| `episode_length_s` | 20.0 |
| `sim.dt` | 0.005 |

센서 업데이트 주기는 decimation·dt에 맞춘다. height scanner가 있으면 주기를 넣고, 없으면 건너뛴다. `terrain_levels`가 있으면 curriculum이 켜진다.

## 6. Go2 전용 오버라이드 (`UnitreeGo2RoughEnvCfg`)

공식 cfg에서 강조되는 점:

1. 로봇은 `UNITREE_GO2_CFG`
2. height scanner는 `{ENV_REGEX_NS}/Robot/base`
3. Go2는 작아서 **지형 높이를 낮춘다**
4. `push_robot = None`
5. `add_base_mass` 분포를 작게, 음수도 포함. 예: `(-1.0, 3.0)`
6. 관절 리셋 `position_range = (1.0, 1.0)` (default 배율에 가깝게)
7. `feet_air_time` body = `.*_foot`

개념 코드:

```python
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    LocomotionVelocityRoughEnvCfg,
)
from isaaclab_assets.robots.unitree import UNITREE_GO2_CFG


@configclass
class UnitreeGo2RoughEnvCfg(LocomotionVelocityRoughEnvCfg):
    def __post_init__(self):
        super().__post_init__()

        self.scene.robot = UNITREE_GO2_CFG.replace(
            prim_path="{ENV_REGEX_NS}/Robot"
        )
        self.scene.height_scanner.prim_path = "{ENV_REGEX_NS}/Robot/base"

        # Go2는 작아서 지형 난이도(높이)를 낮춤
        self.scene.terrain.terrain_generator.sub_terrains["boxes"].grid_height_range = (0.025, 0.1)
        self.scene.terrain.terrain_generator.sub_terrains["random_rough"].noise_range = (0.01, 0.06)
        self.scene.terrain.terrain_generator.sub_terrains["random_rough"].noise_step = 0.01

        self.actions.joint_pos.scale = 0.25
        self.events.push_robot = None
        self.events.add_base_mass.params["mass_distribution_params"] = (-1.0, 3.0)
        self.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
        self.events.base_com = None

        self.rewards.feet_air_time.params["sensor_cfg"].body_names = ".*_foot"
        self.rewards.feet_air_time.weight = 0.01
        self.rewards.track_lin_vel_xy_exp.weight = 1.5
        self.rewards.track_ang_vel_z_exp.weight = 0.75
        self.rewards.dof_torques_l2.weight = -0.0002
        self.rewards.dof_acc_l2.weight = -2.5e-7

        self.terminations.base_contact.params["sensor_cfg"].body_names = "base"
```

공통 `RewardsCfg`의 기본 가중치(예: `track_lin_vel_xy_exp = +1.0`)와 **Go2 표의 숫자가 다르다**. 학습에 실제로 들어가는 쪽은 이 오버라이드다. 공통 9항목의 쉬운 말은 [흐름 §2](../FLOW.md).

## 7. 시간축: physics tick · decimation · policy step

물리 시계와 정책 시계는 둘이다. 정책이 로봇의 판단이다.

| 개념 | 값 | 의미 |
|---|---|---|
| Physics `dt` | 0.005 s | 1 physics tick (200 Hz) |
| `decimation` | 4 | 물리 4틱마다 정책 1회 |
| Policy period | 0.02 s | **50 Hz** |
| Episode | 최대 20 s | 시간 초과 시 timeout 가능 |
| 병렬 | 4096 envs | 한 iteration에 대량 경험 |

직관:

1. 0.005초마다 물리 엔진이 한 번 계산한다 (physics tick).
2. tick이 4번 쌓이면 정책이 새 관절 목표를 낸다 (policy step).
3. 발 하나를 들고 내려놓는 시간은 대략 수십~100 policy step 스케일로 쌓일 수 있다.

학습 알고리즘은 **PPO**. hidden dim · actor-critic 크기는 에이전트 cfg에 있다. 네트워크는 rough 기준 512·256·128 `확인됨` ([공개 정책 조사](go2-pretrained-policies.md)).

iteration 감각: 4096 envs × 24 steps가 한 단위로 도는 설정이 팀에 공유되어 있다 `확인됨` (`num_steps_per_env = 24`).

벽시계: 스터디 메모는 ckpt 1500 ≈ 104분, 하루 약 4회. 팀 완주 실측은 1,500 iteration **133분** (보상 22.88) `확인됨`. GPU·헤드리스 여부에 따라 출렁인다.

**규칙: 정책/보상은 한 번에 하나만 바꾸고, 변경 단위를 팀에 공유한다.**

## 8. 보상 · 종료

보상 채점표는 사람이 쓴다. 정책은 그 점수에 맞춰 최적화된다.

| 목적 | 대표 term | 설명 |
|---|---|---|
| 명령 추종 | `track_lin_vel_xy_exp`, `track_ang_vel_z_exp` | 준 선속도·요를 따라가는가 |
| 안정성 | `lin_vel_z_l2`, `ang_vel_xy_l2` | 위아래로 튀거나 옆으로 흔들리지 않는가 |
| 보행 품질 | `feet_air_time` | 공중 시간과 착지 패턴 |
| 에너지 | `dof_torques_l2`, `dof_acc_l2` | 과토크·급가속 억제. 약하게 두는 경우가 많다 |

선속도 계열이 많아 보이는 이유: 몸통을 기준축으로 움직이기 때문이다. 가중치를 보면 위아래 튀김(`lin_vel_z_l2`)이 큰 벌점인 경우가 많다.

`feet_air_time`은 발이 **착지하는 순간**에 정산하는 형태가 흔하다. «마지막으로 얼마나 떠 있었는가»를 보는 이유: 잔발질·발 끌기·치팅을 막고 한 발씩 들게 하기 위해서다.

손대기 좋은 축 (한 번에 하나):

1. `track_lin_vel_*`
2. `track_ang_vel_*`
3. `feet_air_time`
4. `lin_vel_z_l2`

팀 난이도 곡선에서 실패의 주원인은 넘어짐이 아니라 **느림**이었다. 그래서 손댈 후보는 안정 벌보다 **속도 추종 상과 지형별 속도 커리큘럼** 쪽이다 `확인됨`.

TensorBoard **mean reward** ≈ 에피소드 총점 평균. 우상향이면 학습이 살아 있다는 신호일 뿐이다. 보상 13.94 정책의 통과율이 0%였던 사례가 있다 `확인됨` ([시각 증거](visual-evidence.md)). **통과율은 평가 파이프라인으로 잰다.**

종료:

| 항목 | 설명 |
|---|---|
| `base_contact` | 몸통 접촉이 임계를 넘으면 끝 |
| timeout | `episode_length_s` (20초) |
| 기타 | bad orientation 등 |

## 9. 팀 실험에서 이미 고정된 것

이 절은 스터디 메모와 팀 실측을 맞춘 것이다. 숫자를 인용할 때는 실측 문서를 연다.

### 설치 · 실행

학습은 Isaac Sim / Isaac Lab이 도는 GPU에서. 노트북에 Isaac을 올리지 않는다 `확인됨` ([8/18 험지RL](../meetings/20260818-rough-terrain-study.md)). Python·ROS가 충돌하면 컨테이너를 나누고 통신만 맞추는 구성이 [아키텍처 결정](architecture-decision.md)의 정본이다.

셋업 후 **실제로 한 걸음 도는지**부터 확인한다. PLAY cfg, 소량 env가 먼저다.

### 플래그

다리를 원통으로 단순화하는 collision 근사 플래그는 속도를 올려 주지만 물리가 바뀌어 도달 상한이 낮아진다. **플래그 없이 기본 상태로 학습**이 봉인이다 `확인됨`.

랜덤 시드·도메인 랜덤 때문에 같은 설정이라도 하루하루가 달라질 수 있다. 그래도 평균은 좋아야 한다. **seed · headless · collision flag · iteration · 벽시계**를 실험 로그에 남긴다.

### 난이도 · KPI

- Terrain level 예: 0~9. 난이도별 성능 그래프를 본다.
- 넘어짐 vs **목표 거리(예: 10 m) 미달 timeout**을 가른다.
- 공식 rough에서는 넘어져서 끝나기보다 20초 안에 거리를 못 채우는 경우가 많았다 `확인됨`.
- 지형 하나만 바꿔도 웅크리거나 부들거리는 개체가 나온다. 난이도 0 / 3 / 6 / 9를 눈으로 비교하고, **관절·센서 로그와 함께** 본다. 블로그 렌더만으로 판단하지 않는다.

### 시각화 화살표

| 색 | 의미 |
|---|---|
| 초록 | 명령 (이쪽으로 가라) |
| 파랑 | 실제 속도 (명령을 따랐는가) |

학습 씬과 렌더 씬은 정책 파일만 들고 분리할 수 있다 `확인됨`. 공식 USD는 텍스처가 빈약하면 diffuse만 보인다. 영상용은 머티리얼·텍스처를 입힌다 ([도구 지도](omniverse-stack.md) · [렌더 실측](render-benchmarks.md)).

## 10. 배포 경로: 일반 그림 vs 우리 정본

Isaac 계열의 일반 실기 경로는 아래와 같다.

```
Sim 학습
  (시뮬에는 특권 정보가 있다: 완벽한 상태, height scan)
        ↓
증류 Teacher → Student
  (실기 센서만으로 같은 입력을 못 채울 때)
        ↓
정책 다듬기 · 새 지형 / sim-to-sim / 렌더 테스트
        ↓
ONNX → Orin NX
(실패 시 Sim으로 회귀)
```

실기 제어 계층의 짧은 표:

| 계층 | 내용 |
|---|---|
| 고수준 | Sport mode / MCF 등 내장 모드 |
| 저수준 | 관절 12개 직접 명령 |
| 스위치 | 동시에 켜지지 않음 |
| 주기 | 약 0.02 s (50 Hz). 정책 주기와 맞춤 |

**우리 정본 (8/19):** 학습 정책의 실기 저수준 이전은 하지 않는다 `확인됨`. 트랙 A는 시뮬에서 학습·미학습 지형 평가·트윈·렌더로 닫고, 트랙 B는 순정 보행 위에 SLAM·Nav2다. 특권 관측 증류는 «실기에 우리 정책을 올릴 때»의 장치라, 지금 파인튜닝 계획에서는 필수가 아니다 `확인됨` ([파인튜닝 계획](terrain-finetune-plan.md)).

sim-to-sim · 새 지형 시험 · 렌더 테스트는 그대로 트랙 A의 일이다.

## 11. 용어

| 필기 / 속어 | 정식 |
|---|---|
| 아이작심 / 아이작랩 | Isaac Sim / Isaac Lab |
| 고투 | Unitree Go2 |
| 럼피 / 험지 | rough terrain / `ROUGH_TERRAINS_CFG` |
| 서브 테레인 | sub_terrains |
| 하잇 스캐너 | height_scanner |
| 커멘드 | commands (`base_velocity`) |
| 데피메이션 | decimation |
| 피피오 | PPO |
| 피트 에어타임 | feet_air_time |
| 민 리워드 | mean reward (에피소드 리턴 평균) |
| 오닉스 / 오린 | ONNX / Jetson Orin NX |
| 증류 | distillation (teacher-student) |
| 심투심 / 심투리얼 | sim-to-sim / sim-to-real |
| 옴니버스 | Omniverse (USD 실시간 편집) |

## 부록. 실험 체크리스트

- [ ] 변경은 보상 가중치 1개 또는 지형 파라미터 1개만
- [ ] seed / headless / collision flag / iteration / 벽시계 기록
- [ ] TensorBoard: mean reward, terrain level. timeout vs fall 분리
- [ ] 시각화: command(녹) vs actual(파)
- [ ] Go2용 stairs/boxes 높이가 과하지 않은지 (약 16 cm 감각)
- [ ] PLAY cfg · 소량 env로 먼저, 그다음 4096
- [ ] 난이도 0 / 3 / 6 / 9를 눈으로 보고 관절·센서 로그와 같이 판단
- [ ] 통과율은 평가 파이프라인으로. mean reward만으로 결론 내지 않음

다음에 더 읽을 것: PPO clip/advantage, policy hidden dims, `terrain_levels_vel` 승급 규칙, 커스텀 험지는 [지형 가이드](terrain-guide-isaaclab.md), 실패 지형 이어서 학습은 [파인튜닝 계획](terrain-finetune-plan.md).
