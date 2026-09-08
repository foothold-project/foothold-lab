"""Probe Isaac Lab viewport capture timing without running an RL policy.

The script intentionally keeps the scene small: one Go2, one terrain tile, one
viewport camera, and a short sequence.  It records the brightness of every
``ManagerBasedRLEnv.render`` call so a missing Replicator buffer cannot be
hidden by the video encoder.
"""

import argparse
import json
import os
import sys

# On this Windows installation these imports must happen before Kit starts.
import torch  # noqa: F401,E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

from isaaclab.app import AppLauncher


parser = argparse.ArgumentParser(description="Probe alternating black viewport frames.")
parser.add_argument("--output_dir", required=True)
parser.add_argument("--terrain", choices=("plane", "repeated_boxes"), default="plane")
parser.add_argument("--capture", choices=("single", "pair", "retry"), default="single")
parser.add_argument("--view", choices=("chase", "topdown"), default="chase")
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--record_env", type=int, default=0)
parser.add_argument("--full_generator", action="store_true")
parser.add_argument("--checkpoint", default="")
parser.add_argument("--command_vx", type=float, default=0.0)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--frames", type=int, default=20)
parser.add_argument("--warmup", type=int, default=8)
parser.add_argument("--width", type=int, default=640)
parser.add_argument("--height", type=int, default=360)
AppLauncher.add_app_launcher_args(parser)
args_cli, _ = parser.parse_known_args()
args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import imageio.v2 as imageio  # noqa: E402
import numpy as np  # noqa: E402

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab.utils.assets import retrieve_file_path  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from generalization_env_cfg import UnitreeGo2GeneralizationEnvCfg  # noqa: E402
from render_capture import capture_lit_frame  # noqa: E402


def configure():
    cfg = UnitreeGo2GeneralizationEnvCfg()
    cfg.seed = args_cli.seed
    if args_cli.record_env < 0 or args_cli.record_env >= args_cli.num_envs:
        raise ValueError("--record_env must be inside --num_envs")
    cfg.scene.num_envs = args_cli.num_envs
    cfg.scene.env_spacing = 4.0
    cfg.viewer.resolution = (args_cli.width, args_cli.height)
    cfg.viewer.origin_type = "asset_root"
    cfg.viewer.asset_name = "robot"
    cfg.viewer.env_index = args_cli.record_env
    if args_cli.view == "topdown":
        cfg.viewer.eye = (-1.0, 0.0, 6.0)
        cfg.viewer.lookat = (0.0, 0.0, 0.0)
    else:
        cfg.viewer.eye = (-3.0, 2.0, 1.6)
        cfg.viewer.lookat = (0.5, 0.0, 0.3)
    cfg.observations.policy.enable_corruption = False
    cfg.curriculum.terrain_levels = None
    cfg.events.push_robot = None
    cfg.events.base_external_force_torque = None
    cfg.commands.base_velocity.ranges.lin_vel_x = (args_cli.command_vx, args_cli.command_vx)
    cfg.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)
    cfg.commands.base_velocity.ranges.ang_vel_z = (0.0, 0.0)
    cfg.commands.base_velocity.heading_command = False
    cfg.commands.base_velocity.rel_standing_envs = 1.0

    terrain = cfg.scene.terrain
    if args_cli.terrain == "plane":
        terrain.terrain_type = "plane"
        terrain.terrain_generator = None
    elif not args_cli.full_generator:
        generator = terrain.terrain_generator
        repeated = generator.sub_terrains["repeated_boxes"]
        generator.sub_terrains = {"repeated_boxes": repeated}
        generator.num_cols = 1
        generator.num_rows = 1
        generator.curriculum = False
        generator.difficulty_range = (0.5, 0.5)
        terrain.max_init_terrain_level = 0

    if getattr(args_cli, "device", None):
        cfg.sim.device = args_cli.device

    return cfg


def mean_brightness(frame):
    return float(np.asarray(frame, dtype=np.float32).mean())


def main():
    os.makedirs(args_cli.output_dir, exist_ok=True)
    cfg = configure()
    raw_env = ManagerBasedRLEnv(cfg=cfg, render_mode="rgb_array")
    raw_env.reset()
    actions = torch.zeros(
        (raw_env.num_envs, raw_env.action_manager.total_action_dim),
        dtype=torch.float32,
        device=raw_env.device,
    )

    policy = None
    policy_nn = None
    obs = None
    step_env = raw_env
    checkpoint_path = ""
    if args_cli.checkpoint:
        agent_cfg = load_cfg_from_registry(
            "Isaac-Velocity-Rough-Unitree-Go2-v0", "rsl_rl_cfg_entry_point"
        )
        agent_cfg.seed = args_cli.seed
        agent_cfg.device = raw_env.device
        step_env = RslRlVecEnvWrapper(raw_env, clip_actions=agent_cfg.clip_actions)
        checkpoint_path = retrieve_file_path(args_cli.checkpoint)
        runner = OnPolicyRunner(
            step_env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device
        )
        runner.load(checkpoint_path)
        policy = runner.get_inference_policy(device=raw_env.device)
        policy_nn = runner.alg.policy
        obs = step_env.get_observations()

    warmup_brightness = []
    for _ in range(args_cli.warmup):
        warmup_brightness.append(mean_brightness(raw_env.render()))

    startup_attempts = 0
    startup_means = []
    if args_cli.capture == "retry":
        _, startup_attempts, startup_means = capture_lit_frame(
            raw_env, minimum_mean=10.0, max_attempts=120
        )

    kept_frames = []
    calls = []
    for frame_index in range(args_cli.frames):
        if policy is None:
            raw_env.step(actions)
        else:
            with torch.inference_mode():
                actions = policy(obs)
                obs, _, dones, _ = step_env.step(actions)
                policy_nn.reset(dones)
        first = np.ascontiguousarray(raw_env.render())
        first_mean = mean_brightness(first)
        call = {"frame": frame_index, "first": first_mean}
        if first_mean < 10.0 and hasattr(raw_env, "_rgb_annotator"):
            annotator_data = raw_env._rgb_annotator.get_data()
            call["annotator_size_after_black"] = int(np.asarray(annotator_data).size)

        if args_cli.capture == "retry":
            if first_mean >= 10.0:
                kept = first
                call["attempts"] = 1
                call["attempt_means"] = [first_mean]
            else:
                kept, extra_attempts, extra_means = capture_lit_frame(
                    raw_env, minimum_mean=10.0, max_attempts=2
                )
                call["attempts"] = 1 + extra_attempts
                call["attempt_means"] = [first_mean] + extra_means
        elif args_cli.capture == "pair":
            second = np.ascontiguousarray(raw_env.render())
            second_mean = mean_brightness(second)
            call["second"] = second_mean
            # This selection is diagnostic. It makes no claim that a dark scene
            # is invalid; it exposes which of the two renderer updates carried
            # the completed buffer in this controlled, lit scene.
            kept = first if first_mean >= second_mean else second
            call["selected"] = "first" if first_mean >= second_mean else "second"
        else:
            kept = first

        call["kept"] = mean_brightness(kept)
        calls.append(call)
        kept_frames.append(kept)
        print(json.dumps(call), flush=True)

    video_path = os.path.join(
        args_cli.output_dir, f"{args_cli.terrain}_{args_cli.capture}.mp4"
    )
    writer = imageio.get_writer(
        video_path, fps=50, codec="libx264", quality=None,
        macro_block_size=8, pixelformat="yuv420p",
        output_params=["-crf", "20", "-preset", "fast"],
    )
    for frame in kept_frames:
        writer.append_data(frame)
    writer.close()

    imageio.imwrite(os.path.join(args_cli.output_dir, "frame_000.png"), kept_frames[0])
    imageio.imwrite(os.path.join(args_cli.output_dir, "frame_001.png"), kept_frames[1])

    kept_means = [call["kept"] for call in calls]
    result = {
        "terrain": args_cli.terrain,
        "capture": args_cli.capture,
        "view": args_cli.view,
        "device": str(raw_env.device),
        "num_envs": raw_env.num_envs,
        "record_env": args_cli.record_env,
        "resolution": [args_cli.width, args_cli.height],
        "frames": args_cli.frames,
        "warmup_calls": args_cli.warmup,
        "warmup_brightness": warmup_brightness,
        "startup_ready_attempts": startup_attempts,
        "startup_ready_means": startup_means,
        "render_calls": calls,
        "black_frames": sum(value < 10.0 for value in kept_means),
        "alternating_black": all(
            (kept_means[index] < 10.0) != (kept_means[index + 1] < 10.0)
            for index in range(len(kept_means) - 1)
        ) if len(kept_means) > 1 else False,
        "checkpoint": checkpoint_path,
        "command_vx": args_cli.command_vx,
        "sim_dt": raw_env.cfg.sim.dt,
        "decimation": raw_env.cfg.decimation,
        "render_interval": raw_env.cfg.sim.render_interval,
        "sim_has_gui": raw_env.sim.has_gui(),
        "sim_has_rtx_sensors": raw_env.sim.has_rtx_sensors(),
        "sim_render_mode": raw_env.sim.render_mode.name,
        "video": os.path.basename(video_path),
    }
    with open(os.path.join(args_cli.output_dir, "result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2), flush=True)
    step_env.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
