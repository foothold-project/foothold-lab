"""AME-2 app handoff (2026-11-03): walking speed when the goal is re-sent every control step at a fixed body-frame distance,
as the app's joystick does (foothold-app mobile/sim/ame2-adapter.js:54-62: [f/n, l/n, sin e, cos e], at most 1 m).

Training task, 8 robots on the flat tile (rough column, slope / roughness 0, every level flat), observation noise off.
Robots 0-3 get the goal (1.0, 0) m, robots 4-7 (2.0, 0) m, heading error 0, written into prop[45:49] before every
policy call. Reports the base forward speed (root_lin_vel_b x) over seconds 4-12.

  cd <ame2_spd> ; go2/scripts/run.sh py /root/onnx1103/speed_goal.py --headless --checkpoint <model.pt> --out <json> agent.actor.crop_x=12 ...
"""

import argparse
import json
import os
import sys

from isaaclab.app import AppLauncher

sys.path.append(os.path.join(os.getcwd(), "go2", "scripts", "rsl_rl"))
import cli_args  # isort: skip

parser = argparse.ArgumentParser()
parser.add_argument("--task", type=str, default="Ame2-Go2-Gaze-NoGapStones5")
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")
parser.add_argument("--out", type=str, required=True)
parser.add_argument("--steps", type=int, default=600)
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args, hydra_args = parser.parse_known_args()
sys.argv = [sys.argv[0]] + hydra_args
app = AppLauncher(args).app

import gymnasium as gym
import numpy as np
import torch

from rsl_rl.runners import OnPolicyRunner

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
from isaaclab_tasks.utils.hydra import hydra_task_config

import ame2_go2.tasks  # noqa: F401
from ame2_go2.tasks.mdp.events import _go2_column_terrain_names


@hydra_task_config(args.task, args.agent)
def main(env_cfg, agent_cfg):
    agent_cfg = cli_args.update_rsl_rl_cfg(agent_cfg, args)
    env_cfg.seed = agent_cfg.seed
    env_cfg.scene.num_envs = 8
    gen = env_cfg.scene.terrain.terrain_generator
    gen.sub_terrains["rough"].max_slope_deg = 0.0
    gen.sub_terrains["rough"].max_roughness_m = 0.0
    env_cfg.curriculum.terrain_levels = None
    env_cfg.curriculum.teacher_mapping_noise = None
    env_cfg.observations.teacher_mapping.teacher_mapping.params["custom_noise"] = [0.0, 0.0, 0.0]
    env_cfg.observations.teacher_prop.enable_corruption = False
    env_cfg.scene.height_scanner.drift_range = (0.0, 0.0)
    env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
    u = env.unwrapped
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(args.checkpoint)
    policy = runner.get_inference_policy(device=u.device)
    terrain = u.scene.terrain
    names = _go2_column_terrain_names(terrain.cfg.terrain_generator)
    terrain.terrain_types[:] = names.index("rough")
    terrain.terrain_levels[:] = 0
    terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
    env.reset()
    obs = env.get_observations()
    robot = u.scene["robot"]
    dist = torch.tensor([1.0] * 4 + [2.0] * 4, device=u.device)
    cmd = torch.stack([dist, torch.zeros_like(dist), torch.zeros_like(dist), torch.ones_like(dist)], dim=1)
    vx, vy, wz, done = [], [], [], []
    p0 = robot.data.root_pos_w[:, :2].clone()
    with torch.inference_mode():
        for t in range(args.steps):
            obs["teacher_prop"][:, 45:49] = cmd
            act = policy(obs)
            obs, _, dones, _ = env.step(act)
            vx.append(robot.data.root_lin_vel_b[:, 0].cpu().numpy())
            vy.append(robot.data.root_lin_vel_b[:, 1].cpu().numpy())
            wz.append(robot.data.root_ang_vel_b[:, 2].cpu().numpy())
            done.append(dones.cpu().numpy())
        p1 = robot.data.root_pos_w[:, :2].clone()
    vx, vy, wz, done = np.stack(vx), np.stack(vy), np.stack(wz), np.stack(done)
    dt = float(u.step_dt)
    a, b = int(4.0 / dt), args.steps
    res = {"step_dt": dt, "steps": args.steps, "window_s": [4.0, b * dt], "resets": done.sum(0).tolist()}
    for name, sl in (("goal_1m", slice(0, 4)), ("goal_2m", slice(4, 8))):
        w = vx[a:b, sl]
        res[name] = {
            "vx_mean": float(w.mean()), "vx_per_robot": w.mean(0).round(3).tolist(), "vx_p95": float(np.percentile(w, 95)),
            "vx_max": float(w.max()), "vy_abs_mean": float(np.abs(vy[a:b, sl]).mean()), "wz_abs_mean": float(np.abs(wz[a:b, sl]).mean()),
            "distance_m": torch.linalg.norm(p1[sl] - p0[sl], dim=1).cpu().round(decimals=2).tolist(),
            "time_s": b * dt,
        }
    with open(args.out, "w") as f:
        json.dump(res, f, indent=1)
    print("SPEED", json.dumps({k: (v["vx_mean"] if isinstance(v, dict) else v) for k, v in res.items()}), flush=True)
    print("SPEED_DONE", flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
