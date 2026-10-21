"""S2 어댑터 대조: 학습 env 설정 그대로(지형 · 이벤트 · 명령 모드 · 잡음 전부 학습 그대로, env 수만 줄임)에서 같은 정책 코드(S2Policy)를 돌려
명령 대비 속도를 본다. 평가 설정(S2Adapter.make_env)에서만 서 있다면 평가 설정 문제, 여기서도 서 있다면 정책이 실제로 서 있는 것이다.

    python -m foothold_s2.eval.diag_s2_faithful --task FootholdS2-Go2-S2-diag-G0-start-v0 --checkpoint <pt> --out <폴더> --headless --device cuda:1
"""

import argparse
import json
import os
import sys

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--task", required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--steps", type=int, default=400)
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters  # noqa: E402

env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
env_cfg.scene.num_envs = args.envs
env_cfg.sim.device = args.device
agent_cfg.device = args.device
env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
raw = env.unwrapped
runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)
policy = adapters.S2Policy(runner, env.num_envs)
obs = env.get_observations()
robot = raw.scene["robot"]
term = raw.command_manager.get_term("base_velocity")
rows = []
for k in range(args.steps):
    with torch.inference_mode():
        a = policy(obs)
        obs, _r, dones, _x = env.step(a)
        policy.reset(dones)
    cmd = term.vel_command_b[:, :3]
    if k % 20 == 0:
        moving = (cmd[:, 0].abs() > 0.3)
        rows.append({"k": k, "act_abs_mean": float(a.abs().mean()), "vx_mean": float(robot.data.root_lin_vel_b[:, 0].mean()),
                     "cmd_vx_mean": float(cmd[:, 0].mean()), "frac_cmd_moving": float(moving.float().mean()),
                     "vx_when_moving": float(robot.data.root_lin_vel_b[moving, 0].mean()) if bool(moving.any()) else None,
                     "wz_abs_mean": float(robot.data.root_ang_vel_b[:, 2].abs().mean()), "cmd_wz_abs_mean": float(cmd[:, 2].abs().mean())})
os.makedirs(args.out, exist_ok=True)
json.dump(rows, open(os.path.join(args.out, "faithful.json"), "w", encoding="utf-8"), indent=1)
print("FAITHFUL", json.dumps(rows[-6:]), flush=True)
os._exit(0)
