"""정상 걷는 구간의 원소별 |action| 분포 (lead 10/21 clip_actions 값 결정). 학습 env 그대로(DR 끔), 표집 행동.

    python -m foothold_s2.eval.diag_fbg2 --checkpoint <pt> --out <폴더> [--clip X] --headless --device cuda:0
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
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--envs", type=int, default=256)
parser.add_argument("--sample", action="store_true")
parser.add_argument("--clip", type=float, default=None)
parser.add_argument("--max_level", type=int, default=2)
parser.add_argument("--seconds", type=float, default=20.0)
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402
from collections import defaultdict  # noqa: E402

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
import isaaclab_tasks  # noqa: E402,F401
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters  # noqa: E402
from foothold_s2.terrains import columns  # noqa: E402

adapter = adapters.S1Adapter("scan")
cfg = adapter.env_cfg_class()
cfg.seed = 42
cfg.scene.num_envs = args.envs
cfg.sim.device = args.device
cfg.observations.policy.enable_corruption = False

for name in ("actuator_gains", "motor_strength", "physics_material", "add_base_mass", "base_com", "push_robot", "base_external_force_torque"):
    if hasattr(cfg.events, name):
        setattr(cfg.events, name, None)

cfg.actions.joint_pos.max_delay_s = 0.0
cfg.scene.terrain.max_init_terrain_level = args.max_level

for name in ("terrain_levels", "command_range", "penalty_on"):
    if hasattr(cfg.curriculum, name):
        setattr(cfg.curriculum, name, None)

agent_cfg = load_cfg_from_registry(adapter.task_id, "rsl_rl_cfg_entry_point")
agent_cfg.device = args.device
raw = ManagerBasedRLEnv(cfg=cfg)
built = {"gym_env": raw, "raw": raw, "env_cfg": cfg, "agent_cfg": agent_cfg}
env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)


robot = raw.scene["robot"]
raw.reset()
obs = env.get_observations()
n = raw.num_envs
steps = int(round(args.seconds / raw.step_dt))
walk, allv = [], []
nan_seen = False

for k in range(steps):
    with torch.inference_mode():
        a = policy_nn.act(obs) if args.sample else policy(obs)
        speed = robot.data.root_lin_vel_b[:, :2].norm(dim=1)
        walking = speed > 0.1
        walk.append(a.abs()[walking].flatten().cpu())
        allv.append(a.abs().flatten().cpu())
        obs, _r, dones, _x = env.step(a)
        policy_nn.reset(dones)

def stats(chunks):
    v = torch.cat(chunks).numpy()
    q = np.percentile(v, [50, 99, 99.9, 99.99])

    return {"n": int(v.size), "median": float(q[0]), "p99": float(q[1]), "p99.9": float(q[2]), "p99.99": float(q[3]), "max": float(v.max())}

res = {"checkpoint": args.checkpoint, "envs": n, "seconds": args.seconds, "walking_steps_only(speed>0.1)": stats(walk), "all_steps": stats(allv)}
os.makedirs(args.out, exist_ok=True)
json.dump(res, open(os.path.join(args.out, "actdist.json"), "w"), indent=1)
print("ACTDIST", json.dumps(res), flush=True)
sys.stdout.flush()
os._exit(0)
