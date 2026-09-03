
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
