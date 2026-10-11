# Training command distribution of RobotLab-Go2-v0 (E1 settings), measured on the real generation path.
#
# The env is built from the unchanged Go2EnvCfg (the E1 env.yaml is diffed against it and the diff is
# written to meta.json). Actions come from the E1 checkpoint through runner.alg.act, i.e. the training
# rollout sampling (75 % teacher envs, 25 % student envs, stochastic). No update, no training.
# The command curriculum is selected by the env counter the code itself reads
# (commands.py:129 current_iter = common_step_counter // 24): --iter 19000 (before the 20k step, range 0.5)
# or --iter 20000 (after, range 1.0). Every call of Go2RLGymCommand._resample is logged (step, env,
# episode_length_buf seen by the sampler, reason, new command); the time-weighted distribution is
# accumulated from ct.commands every step and checked against the event log every step.
# --test: known-answer configuration (fixed ranges, resample 1 s, no dynamic/limit/zero branches).
#
# Usage (GPU 1 only): see run_cmd_dist.sh

import argparse
import json
import math
import os
import sys
import time

import h5py  # noqa: F401
import tensordict  # noqa: F401

from isaaclab.app import AppLauncher

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--checkpoint", required=True)
ap.add_argument("--iter", type=int, required=True, help="training iteration emulated through common_step_counter")
ap.add_argument("--num_envs", type=int, default=4096)
ap.add_argument("--warmup", type=int, default=300)
ap.add_argument("--steps", type=int, default=1500)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--test", action="store_true")
ap.add_argument("--tag", required=True)
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
args.headless = True
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402

from isaaclab.utils.dict import class_to_dict  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from rsl_rl.runners import OnPolicyRunnerCTS  # noqa: E402

import robot_lab.tasks  # noqa: F401,E402
from robot_lab.tasks.go2.env_cfg import Go2EnvCfg  # noqa: E402
from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg  # noqa: E402




def dict_diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'train' if k in a else 'eval'}")
            else:
                out += dict_diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} vs {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += dict_diff(x, y, f"{path}[{i}]")
    else:
        if isinstance(a, float) and isinstance(b, float):
            if not (a == b or (math.isnan(a) and math.isnan(b))):
                out.append(f"{path}: {a} vs {b}")
        elif a != b:
            out.append(f"{path}: {a!r} vs {b!r}")
    return out


OUT = os.path.join(HERE, "out", "cmd_dist", args.tag)
os.makedirs(OUT, exist_ok=True)
meta = {"args": vars(args), "t_start": time.strftime("%Y-%m-%d %H:%M:%S"),
        "env_vars": {k: os.environ.get(k) for k in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER")}}

cfg = Go2EnvCfg()
default_view = class_to_dict(cfg)
yml = os.path.join(os.path.dirname(args.checkpoint), "params", "env.yaml")
with open(yml, "r", encoding="utf-8") as f:
    train_yaml = yaml.load(f, Loader=yaml.UnsafeLoader)
diffs = {k: dict_diff(train_yaml.get(k), default_view.get(k), k) for k in ("commands", "events", "terminations", "curriculum", "observations", "actions", "rewards")}
diffs["scene/terrain"] = dict_diff(train_yaml["scene"]["terrain"], default_view["scene"]["terrain"], "scene/terrain")
meta["default_cfg_vs_E1_env_yaml"] = {k: v[:20] for k, v in diffs.items()}
meta["default_cfg_vs_E1_env_yaml_counts"] = {k: len(v) for k, v in diffs.items()}
cfg.scene.num_envs = args.num_envs
cfg.seed = args.seed
cfg.sim.device = "cuda:0"
changes = [f"num_envs {args.num_envs} (E1: 8192)"]
cc = cfg.commands.base_velocity
if args.test:
    cc.dynamic_resample_commands = False
    cc.limit_vel_prob = 0.0
    cc.zero_command_curriculum = None
    cc.command_range_curriculum = []
    cc.ranges.lin_vel_x = (0.3, 0.3)
    cc.ranges.lin_vel_y = (0.0, 0.0)
    cc.ranges.ang_vel_yaw = (0.5, 0.5)
    cc.resampling_time = 1.0
    changes.append("TEST: fixed command (0.3, 0, 0.5), resampling 1 s, dynamic/limit/zero branches off, no range curriculum")
meta["changes"] = changes

env = gym.make("RobotLab-Go2-v0", cfg=cfg)
env = RslRlVecEnvWrapper(env, clip_actions=None)
u = env.unwrapped
dev = u.device
N = u.num_envs
agent_cfg = MoECTSRunnerCfg()
agent_cfg.device = "cuda:0"
runner = OnPolicyRunnerCTS(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
runner.load(args.checkpoint)
runner.train_mode()
_IM = torch.inference_mode()
_IM.__enter__()

ct = u.command_manager.get_term("base_velocity")
TERR = list(ct.terrain_types)
meta["terrain_types"] = TERR
meta["envs_per_terrain"] = {t: int((ct.terrain_idxs == i).sum()) for i, t in enumerate(TERR)}
meta["episode"] = {"max_episode_length": int(u.max_episode_length), "step_dt": u.step_dt, "max_episode_length_s": u.max_episode_length_s}

# --- event log around the real sampler -----------------------------------------------------------
EV = []          # rows: step, env, buf_seen, reason, vx, vy, wz, time_left_after
STATE = {"k": -1, "in_reset": False, "active": False}
_orig_resample = ct._resample
_orig_reset = ct.reset


def _wrapped_resample(env_ids):
    if len(env_ids) == 0:
        return _orig_resample(env_ids)
    buf = u.episode_length_buf[env_ids].clone()
    if STATE["in_reset"]:
        reason = torch.where(u.reset_time_outs[env_ids], 1, 2)  # 1 reset after time-out, 2 reset after termination
    else:
        reason = torch.zeros_like(buf)  # 0 periodic (time_left <= 0)
    _orig_resample(env_ids)
    if STATE["active"]:
        c = ct.commands[env_ids]
        EV.append(torch.stack([torch.full_like(buf, STATE["k"]).float(), env_ids.float(), buf.float(), reason.float(),
                               c[:, 0], c[:, 1], c[:, 2], ct.time_left[env_ids]], 1).cpu())


def _wrapped_reset(env_ids=None):
    STATE["in_reset"] = True
    try:
        return _orig_reset(env_ids)
    finally:
        STATE["in_reset"] = False


ct._resample = _wrapped_resample
ct.reset = _wrapped_reset

# --- emulate the training iteration and the runner's random episode phases ----------------------------
u.common_step_counter = args.iter * 24
u.episode_length_buf = torch.randint_like(u.episode_length_buf, high=int(u.max_episode_length))  # learn(init_at_random_ep_len=True)
obs = env.get_observations()
meta["counter_set"] = u.common_step_counter
for k in range(args.warmup):
    obs, _, _, _ = env.step(runner.alg.act(obs))
meta["after_warmup"] = {"command_ranges": ct.command_ranges, "zero_command_prob": float(ct.zero_command_prob),
                        "remaining_range_curriculum": len(ct.cfg.command_range_curriculum), "max_lin_vel": ct.max_lin_vel,
                        "env_range_vx_unique": torch.unique(ct.env_command_ranges["lin_vel_x"], dim=0).cpu().tolist(),
                        "env_range_vy_unique": torch.unique(ct.env_command_ranges["lin_vel_y"], dim=0).cpu().tolist(),
                        "env_range_wz_unique": torch.unique(ct.env_command_ranges["ang_vel_yaw"], dim=0).cpu().tolist(),
                        "terrain_level_mean": float(u.scene.terrain.terrain_levels.float().mean())}

# --- record ------------------------------------------------------------------------------------------
STATE["active"] = True
track = ct.commands.clone()
cmd_steps = np.zeros((args.steps, N, 3), np.float32)
check_max = 0.0
eplen_at_done = []
t0 = time.time()
for k in range(args.steps):
    STATE["k"] = k
    n_ev = len(EV)
    obs, _, dones, _ = env.step(runner.alg.act(obs))
    for e in EV[n_ev:]:
        track[e[:, 1].long().to(dev)] = e[:, 4:7].to(dev)
    check_max = max(check_max, float((track - ct.commands).abs().max()))
    cmd_steps[k] = ct.commands.cpu().numpy()
meta["record_wall_s"] = time.time() - t0
meta["event_log_vs_commands_every_step_max_abs"] = check_max
meta["end"] = {"command_ranges": ct.command_ranges, "zero_command_prob": float(ct.zero_command_prob),
               "terrain_level_mean": float(u.scene.terrain.terrain_levels.float().mean()), "counter": int(u.common_step_counter)}
ev = torch.cat(EV).numpy() if EV else np.zeros((0, 8), np.float32)
np.savez_compressed(os.path.join(OUT, "events.npz"), ev=ev, terrain_idx=ct.terrain_idxs.cpu().numpy(), terrain_names=np.array(TERR))
np.save(os.path.join(OUT, "cmd_steps.npy"), cmd_steps)
meta["n_events"] = int(len(ev))
meta["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
meta["torch_max_mem_alloc_MiB"] = torch.cuda.max_memory_allocated() / 2 ** 20
with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=1, default=str)
print("[CMD] done", args.tag, "events", len(ev), "check", check_max, flush=True)
env.close()
app.close()
