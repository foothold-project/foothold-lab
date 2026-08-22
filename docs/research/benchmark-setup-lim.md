# Unitree Go2 Isaac Lab 2.3.2 베이스라인·미경험 험지 벤치마크

> 작성 2026-08-22 · **임석헌** · 원본: inbox/lim (승격 2026-08-22) · Runpod 재현의 실행 정본
> 요지: NVIDIA 공식 checkpoint 모델의 미경험 험지에 대한 간단한 지표 측정

- 기준 환경: RunPod Ubuntu 컨테이너
- Isaac Lab 루트: `/workspace/isaaclab`
- 공식 체크포인트: `/workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt`
- 미경험 험지 태스크: `Isaac-Velocity-Unseen-Unitree-Go2-v0`
- 평가 규모: 10개 험지 × 험지별 50개 에피소드
- 공통 명령: `vx=0.5 m/s`, `vy=0.0 m/s`, `wz=0.0 rad/s`
- 공통 seed: `42`

## 1. NVIDIA pretrained Go2 checkpoint 로드

### 작업 경로와 버전 확인
```bash
cd /workspace/isaaclab
git describe --tags --always
./isaaclab.sh -p -c "import isaaclab; print(isaaclab.__version__)"
cat source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/rough_env_cfg.py
```

- 기대 버전 : `v2.3.2` 또는 `2.3.2`

### 공식 체크포인트 자동 다운로드와 실행

```bash
cd /workspace/isaaclab
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/play.py \
  --task Isaac-Velocity-Rough-Unitree-Go2-v0 \
  --num_envs 1 \
  --use_pretrained_checkpoint \
  --headless
```

- 최초 실행 결과 : 공식 pretrained checkpoint 다운로드
- 실행 종료 방식 : `Ctrl+C`

## 2. `generalization_env_cfg.py` 미경험 험지 구성

### 목적

- 기본 Go2 로봇·관측·행동·보상 구조 재사용
- 기본 학습 지형과 다른 10개 지형 타입의 평가 전용 구성
- `env 0`부터 `env 9`까지의 고정 지형 배치
- 에피소드별 작은 초기조건 변화와 전체 실행 재현성 확보

### 파일 경로

```text
/workspace/isaaclab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/generalization_env_cfg.py
```

### 파일 전체 작성

```bash
cd /workspace/isaaclab
cat > source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/generalization_env_cfg.py <<'PY'
import isaaclab.terrains as terrain_gen
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg

GO2_UNSEEN_TERRAINS_CFG = terrain_gen.TerrainGeneratorCfg(
    seed=42,
    size=(8.0, 8.0),
    border_width=10.0,
    num_rows=1,
    num_cols=10,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    curriculum=True,
    difficulty_range=(0.5, 0.5),
    color_scheme="height",
    use_cache=False,

    sub_terrains={
        "discrete_obstacles": terrain_gen.HfDiscreteObstaclesTerrainCfg(
            proportion=0.1,
            obstacle_width_range=(0.4, 1.0),
            obstacle_height_range=(0.05, 0.16),
            num_obstacles=35,
            platform_width=1.5,
            border_width=0.25,
        ),

        "wave": terrain_gen.HfWaveTerrainCfg(
            proportion=0.1,
            amplitude_range=(0.03, 0.12),
            num_waves=4,
            border_width=0.25,
        ),

        "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
            proportion=0.1,
            stone_height_max=0.12,
            stone_width_range=(0.35, 0.65),
            stone_distance_range=(0.08, 0.20),
            holes_depth=-1.0,
            platform_width=1.5,
            border_width=0.25,
        ),

        "gap": terrain_gen.MeshGapTerrainCfg(
            proportion=0.1,
            gap_width_range=(0.15, 0.40),
            platform_width=1.5,
        ),

        "pit": terrain_gen.MeshPitTerrainCfg(
            proportion=0.1,
            pit_depth_range=(0.10, 0.30),
            platform_width=1.5,
            double_pit=False,
        ),

        "rails": terrain_gen.MeshRailsTerrainCfg(
            proportion=0.1,
            rail_thickness_range=(0.08, 0.18),
            rail_height_range=(0.05, 0.18),
            platform_width=1.5,
        ),

        "star": terrain_gen.MeshStarTerrainCfg(
            proportion=0.1,
            num_bars=5,
            bar_width_range=(0.30, 0.70),
            bar_height_range=(0.05, 0.16),
            platform_width=1.5,
        ),

        "floating_ring": terrain_gen.MeshFloatingRingTerrainCfg(
            proportion=0.1,
            ring_width_range=(0.25, 0.60),
            ring_height_range=(0.05, 0.16),
            ring_thickness=0.12,
            platform_width=1.5,
        ),

        "repeated_boxes": terrain_gen.MeshRepeatedBoxesTerrainCfg(
            proportion=0.1,

            object_params_start=terrain_gen.MeshRepeatedBoxesTerrainCfg.ObjectCfg(
                num_objects=25,
                height=0.08,
                size=(0.35, 0.35),
                max_yx_angle=0.0,
                degrees=True,
            ),

            object_params_end=terrain_gen.MeshRepeatedBoxesTerrainCfg.ObjectCfg(
                num_objects=45,
                height=0.16,
                size=(0.50, 0.50),
                max_yx_angle=15.0,
                degrees=True,
            ),

            platform_width=1.5,
        ),

        "repeated_cylinders": terrain_gen.MeshRepeatedCylindersTerrainCfg(
            proportion=0.1,

            object_params_start=terrain_gen.MeshRepeatedCylindersTerrainCfg.ObjectCfg(
                num_objects=25,
                height=0.08,
                radius=0.12,
                max_yx_angle=0.0,
                degrees=True,
            ),

            object_params_end=terrain_gen.MeshRepeatedCylindersTerrainCfg.ObjectCfg(
                num_objects=45,
                height=0.16,
                radius=0.20,
                max_yx_angle=15.0,
                degrees=True,
            ),

            platform_width=1.5,
        ),
    },
)

@configclass
class UnitreeGo2GeneralizationEnvCfg(UnitreeGo2RoughEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 10
        self.scene.terrain.terrain_generator = GO2_UNSEEN_TERRAINS_CFG
        self.scene.terrain.max_init_terrain_level = 0
        self.curriculum.terrain_levels = None
        self.observations.policy.enable_corruption = False
        self.events.push_robot = None
        self.events.base_external_force_torque = None
        self.commands.base_velocity.ranges.lin_vel_x = (0.5, 0.5)
        self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)
        self.commands.base_velocity.ranges.ang_vel_z = (0.0, 0.0)
        self.commands.base_velocity.heading_command = False
        self.commands.base_velocity.rel_standing_envs = 0.0
        self.viewer.origin_type = "asset_root"
        self.viewer.asset_name = "robot"
        self.viewer.env_index = 0
        self.viewer.eye = (-3.0, 2.0, 1.5)
        self.viewer.lookat = (0.0, 0.0, 0.4)
PY
```

### 문법·내용 확인

```bash
cd /workspace/isaaclab
./isaaclab.sh -p -m py_compile source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/generalization_env_cfg.py
cat source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/generalization_env_cfg.py
```

- 정상 문법 확인: `py_compile` 무출력

## 3. Go2 `__init__.py`에 `gym.register()` 추가

### 목적

- 문자열 태스크 ID와 환경 설정 클래스의 연결
- `gym.make()`와 Hydra 태스크 설정 로더의 새 태스크 탐색 지원
- 기존 Go2 Rough PPO runner 설정의 재사용

### 파일 경로

```text
/workspace/isaaclab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/__init__.py
```

```bash
cd /workspace/isaaclab
cp source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/__init__.py /workspace/isaaclab/go2_init_backup.py
```

### 파일 끝에 추가할 코드

```python
gym.register(
    id="Isaac-Velocity-Unseen-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.generalization_env_cfg:UnitreeGo2GeneralizationEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:UnitreeGo2RoughPPORunnerCfg",
    },
)
```

### `cat` 기반 추가 방식

```bash
cd /workspace/isaaclab
cat >> source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/__init__.py <<'PY'

gym.register(
    id="Isaac-Velocity-Unseen-Unitree-Go2-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.generalization_env_cfg:UnitreeGo2GeneralizationEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:UnitreeGo2RoughPPORunnerCfg",
    },
)
PY
```

### 등록 확인

```bash
cd /workspace/isaaclab
grep -n "Isaac-Velocity-Unseen-Unitree-Go2-v0" source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/__init__.py
./isaaclab.sh -p -m py_compile source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/__init__.py
./isaaclab.sh -p -c "import gymnasium as gym; import isaaclab_tasks; print(gym.spec('Isaac-Velocity-Unseen-Unitree-Go2-v0'))"
```

- 기대 검색 결과: 단일 `id` 행
- 기대 Gym 출력: 새 태스크의 `EnvSpec`

## 4. 미경험 태스크와 공식 체크포인트 연결 실행

### 목적

- 학습된 policy 파라미터의 변경 없는 재사용
- 미경험 험지 환경만 교체한 zero-shot 실행
- 관측 차원·행동 차원·checkpoint 호환성 확인

### 체크포인트 경로 확인

```bash
cd /workspace/isaaclab
cat <<'TXT'
/workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt
TXT
test -s /workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt
echo $?
```

### 미경험 태스크 실행

```bash
cd /workspace/isaaclab
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/play.py \
  --task Isaac-Velocity-Unseen-Unitree-Go2-v0 \
  --num_envs 10 \
  --checkpoint /workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt \
  --headless
```

### 정상 실행 기준

- 환경 개수 `10` 확인
- 공식 `checkpoint.pt` 로드 로그 확인
- 관측·행동 차원 불일치 오류 부재
- terrain 생성 오류 부재
- 실행 종료 방식: `Ctrl+C`

## 5. `eval_generalization.py` 정량평가 코드 작성

### 목적

- 10개 지형의 병렬 평가
- 지형별 50개 에피소드 수집
- 동일 지형의 50개 에피소드마다 서로 다른 초기 위치·방향·관절 자세 적용
- 생존·전진·속도 추종·방향 유지 평가
- raw CSV와 summary CSV 자동 생성
- 동일 evaluator 기반 checkpoint 공정 비교

### 파일 경로

```text
/workspace/isaaclab/scripts/reinforcement_learning/rsl_rl/eval_generalization.py
```

### 파일 전체 작성

```bash
cd /workspace/isaaclab
cat > scripts/reinforcement_learning/rsl_rl/eval_generalization.py <<'PY'

import argparse
import csv
import math
import os
import sys
import math
from collections import defaultdict
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Evaluate Go2 zero-shot generalization on unseen terrains.")
parser.add_argument("--task", type=str, default="Isaac-Velocity-Unseen-Unitree-Go2-v0")
parser.add_argument("--episodes_per_terrain", type=int, default=50)
parser.add_argument("--eval_duration", type=float, default=6.0)
parser.add_argument("--command_vx", type=float, default=0.5)
parser.add_argument("--min_progress_ratio", type=float, default=0.70)
parser.add_argument("--max_velocity_mae", type=float, default=0.25)
parser.add_argument("--max_lateral_drift", type=float, default=0.75)
parser.add_argument("--output_dir", type=str, default="/workspace/isaaclab/generalization_results")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--spawn_xy_range", type=float, default=0.10, help="Random initial x/y offset in meters.")
parser.add_argument("--yaw_range_deg", type=float, default=5.0, help="Random initial yaw range in degrees.")
parser.add_argument("--joint_pos_scale", type=float, default=0.05, help="Random joint position scale around default pose.")

import cli_args

cli_args.add_rsl_rl_args(parser)

AppLauncher.add_app_launcher_args(parser)

args_cli, hydra_args = parser.parse_known_args()

sys.argv = [sys.argv[0]] + hydra_args

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

from rsl_rl.runners import OnPolicyRunner
from isaaclab.utils.assets import retrieve_file_path
from isaaclab.utils.math import quat_apply
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
import isaaclab_tasks
from isaaclab_tasks.utils.hydra import hydra_task_config

TERRAIN_NAMES = [
    "discrete_obstacles",
    "wave",
    "stepping_stones",
    "gap",
    "pit",
    "rails",
    "star",
    "floating_ring",
    "repeated_boxes",
    "repeated_cylinders",
]

def configure_evaluation(env_cfg, agent_cfg):
    env_cfg.seed = args_cli.seed
    agent_cfg.seed = args_cli.seed
    env_cfg.scene.num_envs = len(TERRAIN_NAMES)

    terrain_gen = env_cfg.scene.terrain.terrain_generator

    if terrain_gen is None:
        raise RuntimeError("Benchmark task does not use a TerrainGenerator.")

    terrain_gen.seed = args_cli.seed

    terrain_gen.curriculum = True

    if terrain_gen.num_cols != len(TERRAIN_NAMES):
        raise RuntimeError(
            f"Expected {len(TERRAIN_NAMES)} terrain columns, "
            f"but config has {terrain_gen.num_cols}."
        )

    env_cfg.scene.terrain.max_init_terrain_level = 0

    if hasattr(env_cfg.curriculum, "terrain_levels"):
        env_cfg.curriculum.terrain_levels = None
    env_cfg.episode_length_s = args_cli.eval_duration

    cmd = env_cfg.commands.base_velocity

    cmd.ranges.lin_vel_x = (args_cli.command_vx, args_cli.command_vx)
    cmd.ranges.lin_vel_y = (0.0, 0.0)
    cmd.ranges.ang_vel_z = (0.0, 0.0)

    cmd.heading_command = False
    cmd.rel_heading_envs = 0.0
    cmd.rel_standing_envs = 0.0

    env_cfg.observations.policy.enable_corruption = False

    if hasattr(env_cfg.events, "push_robot"):
        env_cfg.events.push_robot = None

    if hasattr(env_cfg.events, "base_external_force_torque"):
        env_cfg.events.base_external_force_torque = None

    if hasattr(env_cfg.events, "add_base_mass"):
        env_cfg.events.add_base_mass = None

    if hasattr(env_cfg.events, "base_com"):
        env_cfg.events.base_com = None

    spawn_range = args_cli.spawn_xy_range

    yaw_range_rad = math.radians(args_cli.yaw_range_deg)

    joint_scale = args_cli.joint_pos_scale

    if getattr(env_cfg.events, "reset_base", None) is not None:
        env_cfg.events.reset_base.params["pose_range"] = {
            "x": (-spawn_range, spawn_range),
            "y": (-spawn_range, spawn_range),
            "yaw": (-yaw_range_rad, yaw_range_rad),
        }

        env_cfg.events.reset_base.params["velocity_range"] = {
            "x": (0.0, 0.0),
            "y": (0.0, 0.0),
            "z": (0.0, 0.0),
            "roll": (0.0, 0.0),
            "pitch": (0.0, 0.0),
            "yaw": (0.0, 0.0),
        }

    if getattr(env_cfg.events, "reset_robot_joints", None) is not None:
        env_cfg.events.reset_robot_joints.params["position_range"] = (
            1.0 - joint_scale,
            1.0 + joint_scale,
        )

        env_cfg.events.reset_robot_joints.params["velocity_range"] = (
            0.0,
            0.0,
        )


def initial_forward_vectors(robot, num_envs, device):
    local_x = torch.zeros((num_envs, 3), device=device)
    local_x[:, 0] = 1.0

    forward_w = quat_apply(robot.data.root_quat_w, local_x)
    forward_xy = forward_w[:, :2]

    forward_xy = forward_xy / torch.linalg.vector_norm(
        forward_xy, dim=1, keepdim=True
    ).clamp_min(1.0e-8)

    return forward_xy


def print_and_verify_mapping(raw_env):
    terrain = raw_env.scene.terrain
    terrain_gen_cfg = raw_env.cfg.scene.terrain.terrain_generator

    cfg_names = list(terrain_gen_cfg.sub_terrains.keys())

    print("\n" + "=" * 80)
    print("ENV -> TERRAIN MAPPING")
    print("=" * 80)

    if cfg_names != TERRAIN_NAMES:
        print("Configured terrain order:")
        print(cfg_names)
        print("Expected terrain order:")
        print(TERRAIN_NAMES)
        raise RuntimeError(
            "sub_terrains dictionary order does not match benchmark definition."
        )

    types = terrain.terrain_types.detach().cpu().tolist()
    levels = terrain.terrain_levels.detach().cpu().tolist()
    origins = terrain.env_origins.detach().cpu().tolist()

    for env_id in range(raw_env.num_envs):
        terrain_type = int(types[env_id])

        if terrain_type < 0 or terrain_type >= len(TERRAIN_NAMES):
            raise RuntimeError(
                f"env {env_id} has invalid terrain_type={terrain_type}"
            )

        terrain_name = TERRAIN_NAMES[terrain_type]

        print(
            f"env {env_id:02d}"
            f" | terrain_type={terrain_type}"
            f" | level={int(levels[env_id])}"
            f" | terrain={terrain_name:<22}"
            f" | origin=({origins[env_id][0]:7.2f},"
            f" {origins[env_id][1]:7.2f},"
            f" {origins[env_id][2]:6.2f})"
        )

        if terrain_type != env_id:
            raise RuntimeError(
                f"Mapping mismatch: env {env_id} -> terrain_type {terrain_type}"
            )

    print("\n[PASS] env-to-terrain mapping is deterministic and correct.")


def verify_commands(raw_env, command_vx):
    command = raw_env.command_manager.get_command("base_velocity")

    expected = torch.zeros_like(command)
    expected[:, 0] = command_vx

    max_error = torch.max(torch.abs(command - expected)).item()

    print("\n" + "=" * 80)
    print("COMMAND VERIFICATION")
    print("=" * 80)

    for env_id in range(raw_env.num_envs):
        values = command[env_id].detach().cpu().tolist()
        print(
            f"env {env_id:02d}"
            f" | vx={values[0]: .3f}"
            f" | vy={values[1]: .3f}"
            f" | wz={values[2]: .3f}"
        )

    if max_error > 1.0e-6:
        raise RuntimeError(
            f"Commands are not fixed as expected. max error={max_error}"
        )

    print("\n[PASS] all robots receive the same velocity command.")


def summarize_results(rows):
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["terrain"]].append(row)

    summary_rows = []

    for terrain_name in TERRAIN_NAMES:
        episodes = grouped[terrain_name]

        n = len(episodes)

        overall_rate = sum(int(r["overall_success"]) for r in episodes) / n
        survival_rate = sum(int(r["survival_success"]) for r in episodes) / n
        progress_rate = sum(int(r["progress_success"]) for r in episodes) / n
        tracking_rate = sum(int(r["tracking_success"]) for r in episodes) / n
        direction_rate = sum(int(r["direction_success"]) for r in episodes) / n

        mean_forward = sum(float(r["forward_progress_m"]) for r in episodes) / n
        mean_lateral = sum(float(r["lateral_drift_m"]) for r in episodes) / n
        mean_vel_mae = sum(float(r["velocity_mae_mps"]) for r in episodes) / n
        mean_duration = sum(float(r["duration_s"]) for r in episodes) / n
        mean_reward = sum(float(r["mean_reward_per_step"]) for r in episodes) / n

        failed = [r for r in episodes if not bool(r["survival_success"])]

        if failed:
            mean_fall_time = sum(float(r["duration_s"]) for r in failed) / len(failed)
        else:
            mean_fall_time = ""

        summary_rows.append(
            {
                "terrain": terrain_name,
                "episodes": n,
                "overall_success_rate": overall_rate,
                "survival_rate": survival_rate,
                "progress_success_rate": progress_rate,
                "tracking_success_rate": tracking_rate,
                "direction_success_rate": direction_rate,
                "mean_forward_progress_m": mean_forward,
                "mean_lateral_drift_m": mean_lateral,
                "mean_velocity_mae_mps": mean_vel_mae,
                "mean_episode_duration_s": mean_duration,
                "mean_fall_time_s": mean_fall_time,
                "mean_reward_per_step": mean_reward,
            }
        )

    return summary_rows


def save_csv(rows, summary_rows, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    raw_path = os.path.join(output_dir, "generalization_raw.csv")
    summary_path = os.path.join(output_dir, "generalization_summary.csv")

    with open(raw_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\n" + "=" * 80)
    print("RESULT FILES")
    print("=" * 80)
    print(raw_path)
    print(summary_path)


@hydra_task_config(args_cli.task, "rsl_rl_cfg_entry_point")
def main(env_cfg, agent_cfg):

    if args_cli.checkpoint is None:
        raise ValueError(
            "--checkpoint is required. "
            "Use the NVIDIA Go2 Rough pretrained checkpoint."
        )

    configure_evaluation(env_cfg, agent_cfg)

    if getattr(args_cli, "device", None) is not None:
        env_cfg.sim.device = args_cli.device

    gym_env = gym.make(args_cli.task, cfg=env_cfg)

    raw_env = gym_env.unwrapped

    print_and_verify_mapping(raw_env)

    gym_env.reset()

    verify_commands(raw_env, args_cli.command_vx)

    env = RslRlVecEnvWrapper(
        gym_env,
        clip_actions=agent_cfg.clip_actions,
    )

    resume_path = retrieve_file_path(args_cli.checkpoint)

    print("\n[INFO] Loading checkpoint:")
    print(resume_path)

    runner = OnPolicyRunner(
        env,
        agent_cfg.to_dict(),
        log_dir=None,
        device=agent_cfg.device,
    )

    runner.load(resume_path)

    policy = runner.get_inference_policy(device=raw_env.device)
    policy_nn = runner.alg.policy

    obs = env.get_observations()


    verify_commands(raw_env, args_cli.command_vx)

    num_envs = raw_env.num_envs
    device = raw_env.device
    dt = raw_env.step_dt

    target_episodes = args_cli.episodes_per_terrain

    ideal_distance = args_cli.command_vx * args_cli.eval_duration
    min_progress = args_cli.min_progress_ratio * ideal_distance

    episode_counts = torch.zeros(
        num_envs, dtype=torch.long, device=device
    )

    elapsed = torch.zeros(num_envs, device=device)
    velocity_error_sum = torch.zeros(num_envs, device=device)
    reward_sum = torch.zeros(num_envs, device=device)
    sample_count = torch.zeros(num_envs, dtype=torch.long, device=device)

    robot = raw_env.scene["robot"]

    start_pos = robot.data.root_pos_w[:, :2].clone()
    forward_dir = initial_forward_vectors(robot, num_envs, device)

    terrain_origins = raw_env.scene.terrain.env_origins[:, :2].clone()

    start_offset = start_pos - terrain_origins

    start_yaw = torch.atan2(
        forward_dir[:, 1],
        forward_dir[:, 0],
    )

    results = []

    print("\n" + "=" * 80)
    print("GENERALIZATION EVALUATION")
    print("=" * 80)
    print(f"terrains               : {num_envs}")
    print(f"episodes / terrain     : {target_episodes}")
    print(f"total target episodes  : {num_envs * target_episodes}")
    print(f"evaluation duration    : {args_cli.eval_duration:.2f} s")
    print(f"command vx             : {args_cli.command_vx:.2f} m/s")
    print(f"ideal distance         : {ideal_distance:.2f} m")
    print(f"minimum progress       : {min_progress:.2f} m")
    print(f"max velocity MAE       : {args_cli.max_velocity_mae:.2f} m/s")
    print(f"max lateral drift      : {args_cli.max_lateral_drift:.2f} m")
    print("=" * 80)

    while simulation_app.is_running():

        if torch.all(episode_counts >= target_episodes):
            break

        active = episode_counts < target_episodes

        pre_step_pos = robot.data.root_pos_w[:, :2].clone()

        command = raw_env.command_manager.get_command("base_velocity").clone()

        expected = torch.zeros_like(command)
        expected[:, 0] = args_cli.command_vx

        command_error = torch.max(torch.abs(command - expected)).item()

        if command_error > 1.0e-5:
            raise RuntimeError(
                f"Command changed during evaluation. "
                f"max deviation={command_error}"
            )

        actual_vel_b = robot.data.root_lin_vel_b[:, :2].clone()

        planar_vel_error = torch.linalg.vector_norm(
            actual_vel_b - command[:, :2],
            dim=1,
        )

        elapsed[active] += dt
        velocity_error_sum[active] += planar_vel_error[active]
        sample_count[active] += 1

        with torch.inference_mode():
            actions = policy(obs)
            obs, reward, dones, extras = env.step(actions)
            policy_nn.reset(dones)

        reward_sum[active] += reward[active]

        terminated = raw_env.reset_terminated.clone()
        timed_out = raw_env.reset_time_outs.clone()

        done_ids = torch.nonzero(
            (terminated | timed_out) & active,
            as_tuple=False,
        ).squeeze(-1)

        if done_ids.numel() == 0:
            continue

        for env_id_tensor in done_ids:
            env_id = int(env_id_tensor.item())

            terrain_type = int(
                raw_env.scene.terrain.terrain_types[env_id].item()
            )
            terrain_name = TERRAIN_NAMES[terrain_type]

            displacement = pre_step_pos[env_id] - start_pos[env_id]

            forward = torch.dot(
                displacement,
                forward_dir[env_id],
            ).item()

            lateral_axis = torch.stack(
                (
                    -forward_dir[env_id, 1],
                    forward_dir[env_id, 0],
                )
            )

            lateral = abs(
                torch.dot(displacement, lateral_axis).item()
            )

            steps = max(int(sample_count[env_id].item()), 1)

            vel_mae = (
                velocity_error_sum[env_id].item() / steps
            )

            mean_reward = (
                reward_sum[env_id].item() / steps
            )

            duration = elapsed[env_id].item()

            survival_success = bool(
                timed_out[env_id].item()
                and not terminated[env_id].item()
            )

            progress_success = bool(
                forward >= min_progress
            )

            tracking_success = bool(
                vel_mae <= args_cli.max_velocity_mae
            )

            direction_success = bool(
                lateral <= args_cli.max_lateral_drift
            )

            overall_success = bool(
                survival_success
                and progress_success
                and tracking_success
                and direction_success
            )

            episode_number = int(
                episode_counts[env_id].item()
            ) + 1

            progress_ratio = (
                forward / ideal_distance
                if ideal_distance > 0.0
                else 0.0
            )

            termination_reason = (
                "timeout"
                if timed_out[env_id].item()
                else "base_contact"
            )

            row = {
                "terrain": terrain_name,
                "env_id": env_id,
                "episode": episode_number,
                "start_x_offset_m": round(
                    start_offset[env_id, 0].item(),
                    4,
                ),

                "start_y_offset_m": round(
                    start_offset[env_id, 1].item(),
                    4,
                ),

                "start_yaw_deg": round(
                    math.degrees(start_yaw[env_id].item()),
                    3,
                ),
                "overall_success": overall_success,
                "survival_success": survival_success,
                "progress_success": progress_success,
                "tracking_success": tracking_success,
                "direction_success": direction_success,
                "termination_reason": termination_reason,
                "duration_s": round(duration, 4),
                "forward_progress_m": round(forward, 4),
                "ideal_distance_m": round(ideal_distance, 4),
                "progress_ratio": round(progress_ratio, 4),
                "lateral_drift_m": round(lateral, 4),
                "velocity_mae_mps": round(vel_mae, 4),
                "mean_reward_per_step": round(mean_reward, 6),
            }

            results.append(row)

            episode_counts[env_id] += 1

            print(
                f"[{terrain_name:<22}] "
                f"episode {episode_number:02d}/{target_episodes} "
                f"| success={int(overall_success)} "
                f"| survival={int(survival_success)} "
                f"| forward={forward:5.2f}m "
                f"| lateral={lateral:4.2f}m "
                f"| vel_MAE={vel_mae:4.2f}"
            )

            start_pos[env_id] = robot.data.root_pos_w[env_id, :2]

            local_x = torch.tensor(
                [[1.0, 0.0, 0.0]],
                device=device,
            )

            new_forward = quat_apply(
                robot.data.root_quat_w[env_id : env_id + 1],
                local_x,
            )[0, :2]

            new_forward = new_forward / torch.linalg.vector_norm(
                new_forward
            ).clamp_min(1.0e-8)

            forward_dir[env_id] = new_forward

            start_offset[env_id] = (
                start_pos[env_id]
                - terrain_origins[env_id]
            )

            start_yaw[env_id] = torch.atan2(
                new_forward[1],
                new_forward[0],
            )

            elapsed[env_id] = 0.0
            velocity_error_sum[env_id] = 0.0
            reward_sum[env_id] = 0.0
            sample_count[env_id] = 0

    if len(results) == 0:
        raise RuntimeError("No evaluation episodes were recorded.")

    summary_rows = summarize_results(results)

    save_csv(
        results,
        summary_rows,
        args_cli.output_dir,
    )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for row in summary_rows:
        print(
            f"{row['terrain']:<22}"
            f" | overall={100 * row['overall_success_rate']:6.1f}%"
            f" | survival={100 * row['survival_rate']:6.1f}%"
            f" | forward={row['mean_forward_progress_m']:5.2f}m"
            f" | vel_MAE={row['mean_velocity_mae_mps']:5.2f}m/s"
        )

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
PY
```

### 평가 지표와 기준

| 지표 | 의미 | 판정 기준 |
|---|---|---|
| `overall_success` | 최종 성공 | 아래 4개 조건의 동시 만족 |
| `survival_success` | 평가 종료까지 생존 | 6초 timeout 도달 |
| `progress_success` | 충분한 전진 | 3.0 m의 70%인 2.1 m 이상 |
| `tracking_success` | 명령 속도 추종 | planar velocity MAE 0.25 m/s 이하 |
| `direction_success` | 방향 유지 | 측면 누적 이동 0.75 m 이하 |
| `duration_s` | 실제 지속 시간 | 최대 6초 |
| `forward_progress_m` | 초기 전방축 누적 전진거리 | 월드 속도의 전방축 투영 적분 |
| `ideal_distance_m` | 명령 완전 추종 거리 | 0.5 m/s × 6초인 3.0 m |
| `progress_ratio` | 이상적 거리 대비 비율 | 실제 거리 ÷ 이상적 거리 |
| `lateral_drift_m` | 초기 측면축 누적 이탈 | 측면축 투영 적분 절댓값 |
| `velocity_mae_mps` | 목표 planar velocity 오차 | 작을수록 우수 |
| `mean_reward_per_step` | timestep별 평균 reward | 학습 목적 관점의 보조 지표 |

### 임계값 설정 근거

- 70% progress threshold: 생존만 하고 정지하는 rollout 제외
- 0.25 m/s MAE threshold: 0.5 m/s 명령 대비 50% 오차 상한
- 0.75 m lateral threshold: 3.0 m 목표 대비 25% 측면 편차 상한
- 복합 기준: 단일 지표 편향 방지
- 보고서 표기 권장: 프로젝트 내부 operational threshold

### 문법·내용 확인

```bash
cd /workspace/isaaclab
./isaaclab.sh -p -m py_compile scripts/reinforcement_learning/rsl_rl/eval_generalization.py
cat scripts/reinforcement_learning/rsl_rl/eval_generalization.py
```

- 정상 문법 확인: `py_compile` 무출력

## 6. `record_generalization.py` 지형별 영상 녹화 코드 작성

### 목적

- 10개 지형 배치 유지
- 선택한 `record_env`의 Go2 추적 카메라 구성
- V2 정량평가와 분리된 대표 rollout 영상 구성
- 공식 checkpoint 기반 단일 지형 대표 rollout 녹화
- CSV 평가와 동일한 6초·0.5 m/s 조건 구성

### 파일 경로

```text
/workspace/isaaclab/scripts/reinforcement_learning/rsl_rl/record_generalization.py
```

### 파일 전체 작성

```bash
cd /workspace/isaaclab
cat > scripts/reinforcement_learning/rsl_rl/record_generalization.py <<'PY'
import argparse
import os
import sys
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Record one terrain from the Go2 generalization benchmark.")
parser.add_argument("--task", type=str, default="Isaac-Velocity-Unseen-Unitree-Go2-v0")
parser.add_argument("--checkpoint", type=str, required=True)
parser.add_argument("--record_env", type=int, required=True, help="Environment index to follow and record.")
parser.add_argument("--video_length", type=int, default=300, help="Number of environment steps to record.")
parser.add_argument("--output_dir", type=str, default="/workspace/isaaclab/generalization_videos")
parser.add_argument("--command_vx", type=float, default=0.5)
parser.add_argument("--seed", type=int, default=42)

import cli_args
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()
args_cli.enable_cameras = True
sys.argv = [sys.argv[0]] + hydra_args
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch
from rsl_rl.runners import OnPolicyRunner
from isaaclab.utils.assets import retrieve_file_path
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils.hydra import hydra_task_config

TERRAIN_NAMES = [
    "discrete_obstacles",
    "wave",
    "stepping_stones",
    "gap",
    "pit",
    "rails",
    "star",
    "floating_ring",
    "repeated_boxes",
    "repeated_cylinders",
]

def configure_recording(env_cfg, agent_cfg):
    env_id = args_cli.record_env
    if env_id < 0 or env_id >= len(TERRAIN_NAMES):
        raise ValueError(
            f"--record_env must be 0-{len(TERRAIN_NAMES) - 1}"
        )

    env_cfg.seed = args_cli.seed
    agent_cfg.seed = args_cli.seed
    env_cfg.scene.num_envs = len(TERRAIN_NAMES)

    terrain_gen = env_cfg.scene.terrain.terrain_generator
    terrain_gen.seed = args_cli.seed
    terrain_gen.curriculum = True

    env_cfg.scene.terrain.max_init_terrain_level = 0

    if hasattr(env_cfg.curriculum, "terrain_levels"):
        env_cfg.curriculum.terrain_levels = None

    cmd = env_cfg.commands.base_velocity

    cmd.ranges.lin_vel_x = (
        args_cli.command_vx,
        args_cli.command_vx,
    )
    cmd.ranges.lin_vel_y = (0.0, 0.0)
    cmd.ranges.ang_vel_z = (0.0, 0.0)

    cmd.heading_command = False
    cmd.rel_heading_envs = 0.0
    cmd.rel_standing_envs = 0.0

    env_cfg.observations.policy.enable_corruption = False

    if hasattr(env_cfg.events, "push_robot"):
        env_cfg.events.push_robot = None

    if hasattr(env_cfg.events, "base_external_force_torque"):
        env_cfg.events.base_external_force_torque = None

    if hasattr(env_cfg.events, "add_base_mass"):
        env_cfg.events.add_base_mass = None

    if hasattr(env_cfg.events, "base_com"):
        env_cfg.events.base_com = None

    if getattr(env_cfg.events, "reset_base", None) is not None:
        env_cfg.events.reset_base.params["pose_range"] = {
            "x": (0.0, 0.0),
            "y": (0.0, 0.0),
            "yaw": (0.0, 0.0),
        }

        env_cfg.events.reset_base.params["velocity_range"] = {
            "x": (0.0, 0.0),
            "y": (0.0, 0.0),
            "z": (0.0, 0.0),
            "roll": (0.0, 0.0),
            "pitch": (0.0, 0.0),
            "yaw": (0.0, 0.0),
        }

    env_cfg.viewer.origin_type = "asset_root"
    env_cfg.viewer.asset_name = "robot"
    env_cfg.viewer.env_index = env_id

    env_cfg.viewer.eye = (-3.0, 2.0, 1.4)
    env_cfg.viewer.lookat = (0.5, 0.0, 0.35)

    env_cfg.viewer.resolution = (1280, 720)

@hydra_task_config(args_cli.task, "rsl_rl_cfg_entry_point")
def main(env_cfg, agent_cfg):
    configure_recording(env_cfg, agent_cfg)
    env_id = args_cli.record_env
    terrain_name = TERRAIN_NAMES[env_id]

    if getattr(args_cli, "device", None) is not None:
        env_cfg.sim.device = args_cli.device

    output_dir = os.path.join(
        args_cli.output_dir,
        f"{env_id:02d}_{terrain_name}",
    )

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 80)
    print("GENERALIZATION VIDEO RECORDING")
    print("=" * 80)
    print(f"env id       : {env_id}")
    print(f"terrain      : {terrain_name}")
    print(f"video length : {args_cli.video_length} steps")
    print(f"output dir   : {output_dir}")
    print("=" * 80)

    gym_env = gym.make(
        args_cli.task,
        cfg=env_cfg,
        render_mode="rgb_array",
    )

    raw_env = gym_env.unwrapped

    gym_env.reset()

    terrain_type = int(
        raw_env.scene.terrain.terrain_types[env_id].item()
    )

    print(
        f"[VERIFY] env {env_id} -> "
        f"terrain_type {terrain_type} -> "
        f"{TERRAIN_NAMES[terrain_type]}"
    )

    if terrain_type != env_id:
        raise RuntimeError(
            f"Unexpected mapping: env {env_id} -> "
            f"terrain_type {terrain_type}"
        )

    command = raw_env.command_manager.get_command(
        "base_velocity"
    )

    cmd_values = command[env_id].detach().cpu().tolist()

    print(
        f"[VERIFY] command env {env_id}: "
        f"vx={cmd_values[0]:.3f}, "
        f"vy={cmd_values[1]:.3f}, "
        f"wz={cmd_values[2]:.3f}"
    )

    video_kwargs = {
        "video_folder": output_dir,
        "step_trigger": lambda step: step == 0,
        "video_length": args_cli.video_length,
        "disable_logger": True,
        "name_prefix": terrain_name,
    }

    gym_env = gym.wrappers.RecordVideo(
        gym_env,
        **video_kwargs,
    )

    env = RslRlVecEnvWrapper(
        gym_env,
        clip_actions=agent_cfg.clip_actions,
    )

    checkpoint_path = retrieve_file_path(
        args_cli.checkpoint
    )

    print("[INFO] Loading checkpoint:")
    print(checkpoint_path)

    runner = OnPolicyRunner(
        env,
        agent_cfg.to_dict(),
        log_dir=None,
        device=agent_cfg.device,
    )

    runner.load(checkpoint_path)

    policy = runner.get_inference_policy(
        device=raw_env.device
    )

    policy_nn = runner.alg.policy

    obs = env.get_observations()

    step = 0

    while simulation_app.is_running():

        with torch.inference_mode():
            actions = policy(obs)
            obs, _, dones, _ = env.step(actions)
            policy_nn.reset(dones)

        step += 1

        if step >= args_cli.video_length:
            break

    env.close()

    print("\n[DONE]")
    print(f"terrain : {terrain_name}")
    print(f"folder  : {output_dir}")


if __name__ == "__main__":
    main()
    simulation_app.close()
PY
```

### 문법·내용 확인

```bash
cd /workspace/isaaclab
./isaaclab.sh -p -m py_compile scripts/reinforcement_learning/rsl_rl/record_generalization.py
cat scripts/reinforcement_learning/rsl_rl/record_generalization.py
```

- 정상 문법 확인: `py_compile` 무출력

## 7. `record_all_generalization.sh` 전체 지형 자동 녹화 스크립트 작성

### 목적

- `record_env=0`부터 `record_env=9`까지 순차 실행
- 프로세스별 카메라 대상 지형 변경
- 지형별 독립 폴더와 MP4 한 개 생성

### 파일 경로

```text
/workspace/isaaclab/record_all_generalization.sh
```

### 파일 전체 작성

```bash
cd /workspace/isaaclab
cat > /workspace/isaaclab/record_all_generalization.sh <<'SH'
#!/bin/bash

set -e

cd /workspace/isaaclab

CHECKPOINT="/workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt"

for ENV_ID in {0..9}
do
    ./isaaclab.sh -p \
    scripts/reinforcement_learning/rsl_rl/record_generalization.py \
      --task Isaac-Velocity-Unseen-Unitree-Go2-v0 \
      --checkpoint "${CHECKPOINT}" \
      --record_env "${ENV_ID}" \
      --video_length 300 \
      --command_vx 0.5 \
      --seed 42 \
      --headless
done

find /workspace/isaaclab/generalization_videos \
  -type f -name "*.mp4" \
  -print
SH
```

### 권한·문법·내용 확인

```bash
cd /workspace/isaaclab
chmod +x /workspace/isaaclab/record_all_generalization.sh
bash -n /workspace/isaaclab/record_all_generalization.sh
cat /workspace/isaaclab/record_all_generalization.sh
```

- 정상 문법 확인: `bash -n` 무출력

## 8. 에피소드 실행과 CSV 저장

### 목적

- 10개 지형의 병렬 rollout
- 지형별 50개 에피소드 수집
- 총 500개 raw 평가 행 생성
- 지형별 summary 10개 행 생성

### 출력 경로 확인

```bash
cd /workspace/isaaclab
mkdir -p /workspace/isaaclab/generalization_results_v2
cat <<'TXT'
/workspace/isaaclab/generalization_results_v2/generalization_raw.csv
/workspace/isaaclab/generalization_results_v2/generalization_summary.csv
TXT
```

### 평가 실행

```bash
cd /workspace/isaaclab
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/eval_generalization.py \
  --task Isaac-Velocity-Unseen-Unitree-Go2-v0 \
  --checkpoint /workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt \
  --episodes_per_terrain 50 \
  --eval_duration 6.0 \
  --command_vx 0.5 \
  --spawn_xy_range 0.10 \
  --yaw_range_deg 5.0 \
  --joint_pos_scale 0.05 \
  --min_progress_ratio 0.70 \
  --max_velocity_mae 0.25 \
  --max_lateral_drift 0.75 \
  --output_dir /workspace/isaaclab/generalization_results_v2 \
  --seed 42 \
  --headless
```

### 결과 확인

```bash
cd /workspace/isaaclab
ls -lh /workspace/isaaclab/generalization_results_v2/generalization_raw.csv
ls -lh /workspace/isaaclab/generalization_results_v2/generalization_summary.csv
wc -l /workspace/isaaclab/generalization_results_v2/generalization_raw.csv
wc -l /workspace/isaaclab/generalization_results_v2/generalization_summary.csv
head -n 3 /workspace/isaaclab/generalization_results_v2/generalization_raw.csv
cat /workspace/isaaclab/generalization_results_v2/generalization_summary.csv
```

- raw CSV 기대 행 수: 헤더 포함 `501`
- summary CSV 기대 행 수: 헤더 포함 `11`
- 지형별 episode 기대값: `50`

### 에피소드 변화 검증

```bash
cd /workspace/isaaclab
./isaaclab.sh -p -c "import pandas as pd; p='/workspace/isaaclab/generalization_results_v2/generalization_raw.csv'; d=pd.read_csv(p); print(d.groupby('terrain').size()); print(d.groupby('terrain')['forward_progress_m'].nunique())"
```

- 지형별 행 개수: 모두 `50`
- randomization 확인: 지형별 `forward_progress_m` 고유값 복수 개

## 9. 지형별 로봇 움직임 영상 저장

### 목적

- 10개 미경험 지형별 MP4 한 개 생성
- 정량 CSV 결과 해석용 행동 근거 확보
- `asset_root` 기준 Go2 추적 카메라 적용
- 1280×720 해상도와 300 environment step 녹화

### 단일 지형 시험 녹화

```bash
cd /workspace/isaaclab
./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/record_generalization.py \
  --task Isaac-Velocity-Unseen-Unitree-Go2-v0 \
  --checkpoint /workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt \
  --record_env 1 \
  --video_length 1000 \
  --output_dir /workspace/isaaclab/generalization_videos \
  --command_vx 0.5 \
  --seed 42 \
  --headless
```

### 전체 지형 자동 녹화

```bash
cd /workspace/isaaclab
/workspace/isaaclab/record_all_generalization.sh
```

### 영상 확인

```bash
cd /workspace/isaaclab
find /workspace/isaaclab/generalization_videos -type f -name "*.mp4" -print
find /workspace/isaaclab/generalization_videos -type f -name "*.mp4" | wc -l
cat <<'TXT'
00_discrete_obstacles
01_wave
02_stepping_stones
03_gap
04_pit
05_rails
06_star
07_floating_ring
08_repeated_boxes
09_repeated_cylinders
TXT
```

- 기대 MP4 개수: `10`
- 영상 길이: `step_dt=0.02 s` 기준 약 6초
- CSV 대응 조건: 동일 command·seed·초기 randomization 범위·평가 길이

## 10. CSV·영상 압축과 8000 포트 다운로드

### 목적

- raw CSV·summary CSV·지형별 MP4의 단일 ZIP 패키징
- RunPod HTTP Service 8000 기반 로컬 다운로드
- Pod 종료 전 결과 반출과 압축 무결성 확인

### 결과 확인과 ZIP 생성

```bash
cd /workspace/isaaclab
ls -lh /workspace/isaaclab/generalization_results_v2
find /workspace/isaaclab/generalization_videos -type f -name "*.mp4" -print
zip -r go2_generalization_benchmark_v2.zip \
  generalization_results_v2 \
  generalization_videos
```

### `zip` 미설치 시 설치

```bash
cd /workspace/isaaclab
apt-get update
apt-get install -y zip unzip
```

### 압축 검증

```bash
cd /workspace/isaaclab
ls -lh /workspace/isaaclab/go2_generalization_benchmark_v2.zip
unzip -t /workspace/isaaclab/go2_generalization_benchmark_v2.zip
unzip -l /workspace/isaaclab/go2_generalization_benchmark_v2.zip
```

- 필수 파일: `generalization_results_v2/generalization_raw.csv`
- 필수 파일: `generalization_results_v2/generalization_summary.csv`
- 필수 파일: `generalization_videos` 하위 MP4 10개
- 정상 무결성 출력: `No errors detected`

### 다운로드 폴더와 8000 포트 서버

```bash
cd /workspace/isaaclab
mkdir -p /workspace/download
cp /workspace/isaaclab/go2_generalization_benchmark_v2.zip /workspace/download/
cat <<'TXT'
/workspace/download/go2_generalization_benchmark_v2.zip
TXT
ls -lh /workspace/download/go2_generalization_benchmark_v2.zip
cd /workspace/download
python3 -m http.server 8000 --bind 0.0.0.0
```

- 정상 출력: `Serving HTTP on 0.0.0.0 port 8000`
- 서버 유지 조건: 현재 터미널 세션 유지
- RunPod 접속 위치: `Pod → Connect → HTTP Service 8000`
- 직접 주소 형식: `https://<POD_ID>-8000.proxy.runpod.net`
- 다운로드 대상: `go2_generalization_benchmark_v2.zip`

### 최종 안전 확인

- 로컬 ZIP 다운로드 완료
- 로컬 ZIP 압축 해제 성공
- CSV 2개 존재 확인
- MP4 10개 존재 확인
- 결과 확인 이후 Pod 종료

### 공식 코드 기준 참조

- Go2 등록 구조: `source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/__init__.py`
- Go2 Rough 환경 구조: `source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/rough_env_cfg.py`
- RSL-RL 실행 구조: `scripts/reinforcement_learning/rsl_rl/play.py`
- terrain 설정 클래스: `source/isaaclab/isaaclab/terrains`

### 체크포인트 검증

```bash
cd /workspace/isaaclab
ls -lh /workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt
test -s /workspace/isaaclab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt
echo $?
```

- 정상 확인값: `0`
