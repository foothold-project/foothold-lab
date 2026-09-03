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
