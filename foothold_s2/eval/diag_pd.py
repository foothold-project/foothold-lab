"""시작 자세 진단 (lead 10/21, astra2 N1f 선택 A): 정책 없이 «행동 0 = 기본 관절 자세 PD 유지» 로 4 s.

    python -m foothold_s2.eval.diag_pd --terrain stepping_stones_start --cmd=0,-0.2,0 --checkpoint <s1scan pt> --out <폴더> --headless --device cuda:0

기록: reset 직후(step 전) 발 구 바닥과 칸 메시 지면(칸 상자 윗면)의 차, 발별 접촉(스텝마다), 몸 높이 · roll · pitch 시간열, s1scan 정책의 첫 action 크기(정책은 계산만 하고 env 에는 0 을 넣는다).
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
parser.add_argument("--terrain", required=True)
parser.add_argument("--cmd", default="0,-0.2,0")
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--envs", type=int, default=16)
parser.add_argument("--seconds", type=float, default=4.0)
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
built = adapter.make_env(generator=generator, num_envs=args.envs, duration_s=args.seconds, seed=42, difficulty=0.5, base_cmd=[cmd] * args.envs, device=args.device)
raw = built["raw"]
pin = runtime.CommandPin(args.envs, raw.device, [cmd] * args.envs)
term = adapter.pin_command(raw, pin)
env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)
terrain_sets.sparse_starts.install_fixed_reset(raw, list(generator.sub_terrains), generator.axis3_starts)
raw.reset()
runtime.EpisodeRunner._write_command(term, pin.want)
obs = env.get_observations()
robot = raw.scene["robot"]
sensor = raw.scene["contact_forces"]
foot_r, _ = robot.find_bodies(".*_foot")
foot_s, _ = sensor.find_bodies(".*_foot")
n, dt = raw.num_envs, raw.step_dt
kind = terrain_sets.START_AXIS3_KINDS.get(args.terrain)
boxes = sparse_terrains.build_tile(kind, 0.5).boxes if kind else None
origin_local = np.array(plan["origin"][:2])
env_origin = raw.scene.terrain.env_origins[:, :2].cpu().numpy()


def ground_below(feet_xy_world):
    out = np.full(feet_xy_world.shape[:2], np.nan)

    if boxes is None:
        return out

    local = feet_xy_world - env_origin[:, None, :] + origin_local

    for e in range(local.shape[0]):
        for f in range(4):
            x, y = local[e, f]
            inside = (boxes[:, 0] <= x) & (x <= boxes[:, 1]) & (boxes[:, 2] <= y) & (y <= boxes[:, 3])
            out[e, f] = boxes[inside, 5].max() if inside.any() else np.nan

    return out


feet0 = robot.data.body_pos_w[:, foot_r, :].cpu().numpy()
g0 = ground_below(feet0[..., :2])
sole0 = feet0[..., 2] - 0.022 - g0                 # 발 구 바닥 - 지면 (reset 직후, step 전)
with torch.inference_mode():
    a0 = policy(obs)
first_action = {"mean_abs": float(a0.abs().mean()), "max_abs": float(a0.abs().max()), "per_env0": [round(float(x), 3) for x in a0[0]]}
zero = torch.zeros(n, 12, device=raw.device)
steps = int(round(args.seconds / dt))
contact = np.zeros((steps, n, 4), dtype=bool)
height = np.zeros((steps, n))
rollpitch = np.zeros((steps, n, 2))
alive = np.ones((steps, n), dtype=bool)
alive_now = np.ones(n, dtype=bool)

for k in range(steps):
    raw.step(zero)
    force = sensor.data.net_forces_w[:, foot_s, :].norm(dim=-1)
    contact[k] = (force > 1.0).cpu().numpy()
    feet = robot.data.body_pos_w[:, foot_r, :2].cpu().numpy()
    gz = ground_below(feet)
    stance = np.where(contact[k], robot.data.body_pos_w[:, foot_r, 2].cpu().numpy(), np.nan)
    height[k] = robot.data.root_pos_w[:, 2].cpu().numpy() - np.nanmean(stance, axis=1)
    g = robot.data.projected_gravity_b.cpu().numpy()
    rollpitch[k] = np.column_stack((np.arctan2(g[:, 1], -g[:, 2]), np.arctan2(-g[:, 0], np.sqrt(g[:, 1] ** 2 + g[:, 2] ** 2))))
    alive[k] = alive_now
    alive_now &= ~(raw.reset_terminated | raw.reset_time_outs).cpu().numpy()


def at(k_):
    m = alive[k_]

    return {"contact_mean": float(contact[k_][m].sum(axis=1).mean()) if m.any() else None,
            "contact_min": int(contact[k_][m].sum(axis=1).min()) if m.any() else None,
            "contact_per_foot_rate": [round(float(x), 2) for x in contact[k_][m].mean(axis=0)] if m.any() else None,
            "body_height_over_stance_m": float(np.nanmean(height[k_][m])) if m.any() else None,
            "roll_deg": float(np.degrees(rollpitch[k_][m][:, 0]).mean()) if m.any() else None,
            "pitch_deg": float(np.degrees(rollpitch[k_][m][:, 1]).mean()) if m.any() else None,
            "alive": int(m.sum())}


res = {"terrain": args.terrain, "cmd": cmd, "plan": {k: v for k, v in plan.items() if k in ("status", "origin", "yaw_rad", "support_heights_m", "sole_air_gaps_m", "foot_edge_clearances_m", "root_z_offset_m", "spawn_root_z_m")},
       "reset_sole_minus_ground_m_env0": [round(float(x), 4) for x in sole0[0]], "reset_sole_minus_ground_m_mean": [round(float(x), 4) for x in np.nanmean(sole0, axis=0)],
       "reset_foot_z_env0": [round(float(x), 4) for x in feet0[0, :, 2]],
       "policy_first_action": first_action,
       "by_step": {str(k_): at(k_) for k_ in (0, 2, 5, 10, 15, 30, 60, 100, steps - 1) if k_ < steps},
       "contact_timeseries_env0": contact[:, 0, :].astype(int).tolist()[::2],
       "body_height_timeseries_mean": [round(float(np.nanmean(height[k_][alive[k_]])), 4) if alive[k_].any() else None for k_ in range(0, steps, 5)]}
os.makedirs(args.out, exist_ok=True)
json.dump(res, open(os.path.join(args.out, "pd.json"), "w"), indent=1)
print("PD", json.dumps({k_: res["by_step"][k_] for k_ in ("30",) if k_ in res["by_step"]}), flush=True)
sys.stdout.flush()
os._exit(0)
