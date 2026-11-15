"""foot_below_ground 종료가 학습 지형 어디서 나는가 + 안 A(발 반경 0.15 m 안 스캔 점의 최저 높이 기준)와 비교 (lead 10/21 B-2). 환경 정의는 바꾸지 않는다.

    python -m foothold_s2.eval.diag_fbg2 --checkpoint <pt> --out <폴더> --headless --device cuda:0
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

tm = raw.termination_manager
tcfg = tm.get_term_cfg("foot_below_ground")
orig = tcfg.func
state = {}


def wrapper(env_, **kw):
    cur = orig(env_, **kw)
    asset = env_.scene[kw["asset_cfg"].name]
    scanner = env_.scene.sensors[kw["scanner_cfg"].name]
    feet = asset.data.body_pos_w[:, kw["asset_cfg"].body_ids, :]
    hits = scanner.data.ray_hits_w
    ok = torch.isfinite(hits).all(dim=-1)
    d = torch.linalg.norm(feet[:, :, None, :2] - hits[:, None, :, :2], dim=-1)
    near = ok[:, None, :] & (d < 0.15)
    z = torch.where(near, hits[:, None, :, 2].expand_as(d), torch.full_like(d, 1.0e6))
    low = z.min(dim=-1).values
    has = near.any(dim=-1)
    alt = ((feet[..., 2] < low - kw["margin"]) & has).any(dim=1)
    state["cur"], state["alt"] = cur.clone(), alt
    return cur


tcfg.func = wrapper
tm.set_term_cfg("foot_below_ground", tcfg)
c = cfg.commands.base_velocity
raw.reset()
obs = env.get_observations()
n = raw.num_envs
types = raw.scene.terrain.terrain_types.detach().cpu().numpy()
levels = raw.scene.terrain.terrain_levels.detach().cpu().numpy()
names = columns.column_types(columns.CONTINUOUS, columns.CONTINUOUS_COLS)
steps = int(round(args.seconds / raw.step_dt))
cur_n, alt_n, both_n = defaultdict(int), defaultdict(int), defaultdict(int)
env_steps = defaultdict(int)
resets = defaultdict(int)
other_terms = defaultdict(int)

for k in range(steps):
    with torch.inference_mode():
        obs, _r, dones, _x = env.step(policy_nn.act(obs) if args.sample else policy(obs))
        policy_nn.reset(dones)

    cur, alt = state["cur"].cpu().numpy(), state["alt"].cpu().numpy()
    for e in range(n):
        key = names[types[e]]
        env_steps[key] += 1
        if cur[e]:
            cur_n[key] += 1
        if alt[e]:
            alt_n[key] += 1
        if cur[e] and alt[e]:
            both_n[key] += 1
        if cur[e]:
            lv = int(levels[e])
            cur_n["level%d" % lv] += 1
        if dones[e]:
            resets[key] += 1

res = {"envs": n, "seconds": args.seconds, "per_terrain": {k: {"env_steps": env_steps[k], "episodes_ended": resets[k], "cur_fires": cur_n[k], "alt_fires": alt_n[k], "both": both_n[k]} for k in sorted(env_steps)},
       "cur_fires_by_level": {k: v for k, v in sorted(cur_n.items()) if k.startswith("level")},
       "totals": {"cur": sum(v for k, v in cur_n.items() if not k.startswith("level")), "alt": sum(alt_n.values()), "both": sum(both_n.values()), "episodes_ended": sum(resets.values())}}
os.makedirs(args.out, exist_ok=True)
json.dump(res, open(os.path.join(args.out, "fbg2.json"), "w"), indent=1)
print("FBG2", json.dumps(res["totals"]), flush=True)
sys.stdout.flush()
os._exit(0)
