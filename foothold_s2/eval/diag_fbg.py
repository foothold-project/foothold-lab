"""foot_below_ground 종료 진단 (lead 10/21 B): 종료 판정이 쓰는 기준 지면 높이(가장 가까운 스캔 점)와 발 아래 실제 지면(칸 상자 윗면)을 첫 스텝들에서 맞댄다.

    python -m foothold_s2.eval.diag_fbg --terrain gaps_start --cmd=-0.3,0,0 --checkpoint <pt> --out <폴더> --headless --device cuda:0
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
parser.add_argument("--terrain", default="gaps_start")
parser.add_argument("--cmd", default="-0.3,0,0")
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--envs", type=int, default=16)
parser.add_argument("--steps", type=int, default=12)
parser.add_argument("--out", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app = AppLauncher(args).app
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402
import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, runtime, terrain_sets  # noqa: E402
from foothold_s2.terrains import sparse_terrains  # noqa: E402

cmd = tuple(float(x) for x in args.cmd.split(","))
adapter = adapters.S1Adapter("scan")
root_h = adapters.sparse_start_root_height(adapter)
generator = terrain_sets.merged_generator([args.terrain], 0.5, 42, start_cmd=cmd, root_height_m=root_h)
plan = generator.axis3_starts[args.terrain]
built = adapter.make_env(generator=generator, num_envs=args.envs, duration_s=4.0, seed=42, difficulty=0.5, base_cmd=[cmd] * args.envs, device=args.device)
raw = built["raw"]
pin = runtime.CommandPin(args.envs, raw.device, [cmd] * args.envs)
term = adapter.pin_command(raw, pin)
env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)
terrain_sets.sparse_starts.install_fixed_reset(raw, list(generator.sub_terrains), generator.axis3_starts)
raw.reset()
runtime.EpisodeRunner._write_command(term, pin.want)
obs = env.get_observations()
robot = raw.scene["robot"]
scanner = raw.scene.sensors["height_scanner"]
feet_ids, _ = robot.find_bodies(".*_foot")
kind = terrain_sets.START_AXIS3_KINDS.get(args.terrain)
boxes = sparse_terrains.build_tile(kind, 0.5).boxes if kind else None
origin_local = np.array(plan["origin"][:2])
rows = []

for k in range(args.steps):
    feet = robot.data.body_pos_w[:, feet_ids, :]
    hits = scanner.data.ray_hits_w
    ok = torch.isfinite(hits).all(dim=-1)
    h2 = torch.where(ok[..., None], hits, torch.zeros_like(hits))
    d = torch.linalg.norm(feet[:, :, None, :2] - h2[:, None, :, :2], dim=-1)
    d = torch.where(ok[:, None, :], d, torch.full_like(d, 1.0e6))
    dmin, nearest = d.min(dim=-1)
    gz = torch.gather(h2[..., 2], 1, nearest)
    env_origin = raw.scene.terrain.env_origins[:, :2]
    local = (feet[..., :2] - env_origin[:, None, :]).cpu().numpy() + origin_local
    true_z = np.full(local.shape[:2], np.nan)

    if boxes is not None:
        for e in range(local.shape[0]):
            for f in range(4):
                x, y = local[e, f]
                inside = (boxes[:, 0] <= x) & (x <= boxes[:, 1]) & (boxes[:, 2] <= y) & (y <= boxes[:, 3])
                true_z[e, f] = boxes[inside, 5].max() if inside.any() else np.nan

    rows.append({"k": k, "foot_z": feet[0, :, 2].tolist(), "scan_nearest_z": gz[0].tolist(), "scan_nearest_dist": dmin[0].tolist(),
                 "true_ground_z_below_foot": true_z[0].tolist(), "foot_xy_tile": local[0].round(3).tolist(),
                 "env_origin_z": float(raw.scene.terrain.env_origins[0, 2]), "scan_z_range": [float(h2[0, :, 2].min()), float(h2[0, :, 2].max())],
                 "foot_minus_scan": (feet[0, :, 2] - gz[0]).tolist(),
                 "would_terminate_scan": bool(((feet[..., 2] < gz - 0.2) & (dmin < 0.15))[0].any()),
                 "would_terminate_true": bool((feet[0, :, 2].cpu().numpy() < true_z[0] - 0.2).any()) if boxes is not None else None,
                 "base_z": float(robot.data.root_pos_w[0, 2])})
    with torch.inference_mode():
        obs, _r, dones, _x = env.step(policy(obs))
        policy_nn.reset(dones)
    rows[-1]["terminated_after_step"] = bool(raw.reset_terminated[0])
    rows[-1]["foot_below_ground_flag"] = bool(raw.termination_manager.get_term("foot_below_ground")[0])

os.makedirs(args.out, exist_ok=True)
json.dump({"plan": {k: v for k, v in plan.items() if k in ("origin", "yaw_rad", "feet_world", "support_heights_m", "foot_air_gaps_m")}, "steps": rows},
          open(os.path.join(args.out, "fbg.json"), "w"), indent=1, default=str)
print("FBG done", flush=True)
sys.stdout.flush()
os._exit(0)
