# Q-v1 basic command evaluation of the deployed MoE-CTS student (E1).
#
# Runs the trained student path exactly as scripts/rsl_rl/play.py does
# (OnPolicyRunnerCTS.get_inference_policy -> ActorCriticMoECTS.act_inference:
# policy history 450 + single_obs 45, no critic/teacher input), with the
# command generator replaced by a fixed per-env schedule.
#
# Repository files are not modified. Everything that differs from training
# is set here and written to meta.json.
#
# Usage (GPU 1 only):
#   set CUDA_DEVICE_ORDER=PCI_BUS_ID, CUDA_VISIBLE_DEVICES=1, OMNI_KIT_ACCEPT_EULA=YES
#   python q_eval.py --checkpoint <model_N.pt> --families flat,stairs_up --tag <name>

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time

import h5py  # noqa: F401  (Windows DLL preload, same as scripts/rsl_rl/play.py)
import tensordict  # noqa: F401

from isaaclab.app import AppLauncher

HERE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint", default=None)
parser.add_argument("--policy", choices=["student", "zero"], default="student")
parser.add_argument("--families", default="flat")
parser.add_argument("--cells", default="all")
parser.add_argument("--episodes", type=int, default=100)
parser.add_argument("--difficulty", type=float, default=0.5)
parser.add_argument("--eval_seed", type=int, default=1000)
parser.add_argument("--obs_noise", action="store_true", help="keep training observation noise (default off)")
parser.add_argument("--tag", required=True)
parser.add_argument("--outdir", default=os.path.join(HERE, "out"))
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.headless = True
app_launcher = AppLauncher(args)
simulation_app = app_launcher.app

import copy  # noqa: E402

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402
from tensordict import TensorDict  # noqa: E402

import isaaclab.utils.math as math_utils  # noqa: E402
from isaaclab.managers import EventTermCfg as EventTerm  # noqa: E402
from isaaclab.managers import SceneEntityCfg  # noqa: E402
from isaaclab.utils.dict import class_to_dict  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from rsl_rl.runners import OnPolicyRunnerCTS  # noqa: E402

import robot_lab.tasks  # noqa: F401,E402  (registers RobotLab-Go2-v0)
from robot_lab.tasks.go2.env_cfg import Go2EnvCfg  # noqa: E402
from robot_lab.tasks.go2.mdp.terrains import TERRAIN_CFG  # noqa: E402
from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg  # noqa: E402

sys.path.insert(0, HERE)
import q_metrics as Q  # noqa: E402

# --- cells ------------------------------------------------------------------
# src "Q": value from the Q contract. "LEAD_TEMP": not in Q, set for this run.
ALL_CELLS = [
    dict(name="stand", kind="stand", cmd=(0.0, 0.0, 0.0), duration_s=10.0, switch_s=None, src="LEAD_TEMP"),
    dict(name="stop03", kind="stop", cmd=(0.3, 0.0, 0.0), duration_s=10.0, switch_s=5.0, src="Q"),
    dict(name="fwd01", kind="lin", cmd=(0.1, 0.0, 0.0), duration_s=20.0, switch_s=None, src="LEAD_TEMP"),
    dict(name="fwd02", kind="lin", cmd=(0.2, 0.0, 0.0), duration_s=20.0, switch_s=None, src="LEAD_TEMP"),
    dict(name="fwd03", kind="lin", cmd=(0.3, 0.0, 0.0), duration_s=20.0, switch_s=None, src="Q"),
    dict(name="fwd05", kind="lin", cmd=(0.5, 0.0, 0.0), duration_s=20.0, switch_s=None, src="LEAD_TEMP"),
    dict(name="back03", kind="lin", cmd=(-0.3, 0.0, 0.0), duration_s=20.0, switch_s=None, src="Q"),
    dict(name="left03", kind="lin", cmd=(0.0, 0.3, 0.0), duration_s=20.0, switch_s=None, src="Q"),
    dict(name="right03", kind="lin", cmd=(0.0, -0.3, 0.0), duration_s=20.0, switch_s=None, src="Q"),
    dict(name="yawL05", kind="yaw", cmd=(0.0, 0.0, 0.5), duration_s=20.0, switch_s=None, src="Q"),
    dict(name="yawR05", kind="yaw", cmd=(0.0, 0.0, -0.5), duration_s=20.0, switch_s=None, src="Q"),
]
CELLS = ALL_CELLS if args.cells == "all" else [c for c in ALL_CELLS if c["name"] in args.cells.split(",")]
FAMILIES = args.families.split(",")
C, E, F = len(CELLS), args.episodes, len(FAMILIES)
N = F * C * E
DT = Q.DT
T = int(round(max(c["duration_s"] for c in CELLS) / DT))  # policy steps
SPAWN_ROWS = 8  # keep equal to q_post.SPAWN_ROWS; rows 0..7 used as start tiles; +x travel stays in the same family column
OUT = os.path.join(args.outdir, args.tag)
os.makedirs(OUT, exist_ok=True)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha256_arr(*arrs):
    h = hashlib.sha256()
    for a in arrs:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def smi():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,uuid,memory.used,utilization.gpu", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20)
        return r.stdout.strip().splitlines()
    except Exception as e:  # pragma: no cover
        return [f"nvidia-smi failed: {e}"]


def reset_root_q(env, env_ids, pose_range, asset_cfg=SceneEntityCfg("robot")):
    """Training reset_root_state_uniform with yaw fixed per env (env._q_yaw) and zero velocity."""
    asset = env.scene[asset_cfg.name]
    root = asset.data.default_root_state[env_ids].clone()
    r = torch.tensor([pose_range.get(k, (0.0, 0.0)) for k in ("x", "y", "z")], device=asset.device)
    s = math_utils.sample_uniform(r[:, 0], r[:, 1], (len(env_ids), 3), device=asset.device)
    pos = root[:, :3] + env.scene.env_origins[env_ids] + s
    yaw_all = getattr(env, "_q_yaw", None)
    yaw = torch.zeros(len(env_ids), device=asset.device) if yaw_all is None else yaw_all[env_ids]
    z = torch.zeros_like(yaw)
    quat = math_utils.quat_mul(root[:, 3:7], math_utils.quat_from_euler_xyz(z, z, yaw))
    asset.write_root_pose_to_sim(torch.cat([pos, quat], dim=-1), env_ids=env_ids)
    asset.write_root_velocity_to_sim(torch.zeros(len(env_ids), 6, device=asset.device), env_ids=env_ids)


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


meta = {"args": vars(args), "cells": CELLS, "families": FAMILIES, "N": N, "T_steps": T,
        "env_vars": {k: os.environ.get(k) for k in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "OMNI_KIT_ACCEPT_EULA")},
        "smi_start": smi(), "t_start": time.strftime("%Y-%m-%d %H:%M:%S")}

# --- env config ----------------------------------------------------------------
env_cfg = Go2EnvCfg()
train_view = class_to_dict(env_cfg)  # untouched default config (what train.py used)

# compare with the E1 run's dumped config
ckpt = args.checkpoint
if ckpt:
    yml = os.path.join(os.path.dirname(ckpt), "params", "env.yaml")
    with open(yml, "r", encoding="utf-8") as f:
        train_yaml = yaml.load(f, Loader=yaml.UnsafeLoader)
    keys = ["observations", "actions", "decimation", "sim", "events", "terminations"]
    diffs = {}
    for k in keys:
        diffs[k] = dict_diff(train_yaml.get(k), train_view.get(k), k)
    rob = dict_diff(train_yaml["scene"]["robot"], train_view["scene"]["robot"], "scene/robot")
    diffs["scene/robot"] = rob
    meta["default_cfg_vs_train_yaml"] = {k: v[:20] for k, v in diffs.items()}
    meta["default_cfg_vs_train_yaml_counts"] = {k: len(v) for k, v in diffs.items()}

# evaluation changes (all recorded)
changes = []
env_cfg.scene.num_envs = N
env_cfg.seed = args.eval_seed
env_cfg.sim.device = "cuda:0"
if not args.obs_noise:
    env_cfg.observations.policy.enable_corruption = False
    env_cfg.observations.single_obs.enable_corruption = False
    changes.append("observation noise off for policy and single_obs (LEAD_TEMP)")
env_cfg.events.randomize_push_robot = None
changes.append("push events off (as play.py)")
env_cfg.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
changes.append("reset joints at default pose, scale (1,1) instead of (0.5,1.5) (LEAD_TEMP)")
env_cfg.events.reset_base = EventTerm(
    func=reset_root_q, mode="reset",
    params={"pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "z": (0.0, 0.2)}})
changes.append("reset_base: xy +-0.5 m, z +0..0.2 m as training; yaw fixed per cell; velocity 0 (LEAD_TEMP)")
env_cfg.curriculum.terrain_levels = None
env_cfg.curriculum.base_linear_velocity = None
env_cfg.curriculum.base_height_l2 = None
changes.append("all curriculum terms off")
env_cfg.episode_length_s = 30.0
changes.append("episode_length_s 25 -> 30 so no time_out inside a 20 s cell")
tg = copy.deepcopy(TERRAIN_CFG)
tg.sub_terrains = {k: copy.deepcopy(TERRAIN_CFG.sub_terrains[k]) for k in FAMILIES}
for v in tg.sub_terrains.values():
    v.proportion = 1.0
tg.num_cols = F
tg.num_rows = 10
tg.difficulty_range = (args.difficulty, args.difficulty)
tg.curriculum = True
tg.seed = args.eval_seed
tg.use_cache = False
env_cfg.scene.terrain.terrain_generator = tg
env_cfg.scene.terrain.max_init_terrain_level = None
changes.append(f"terrain: one column per family {FAMILIES}, 10 rows, difficulty fixed {args.difficulty}, seed {args.eval_seed}")
meta["eval_changes"] = changes
meta["eval_cfg_obs"] = {g: {"enable_corruption": getattr(env_cfg.observations, g).enable_corruption,
                            "history_length": getattr(env_cfg.observations, g).history_length}
                        for g in ("policy", "single_obs", "critic")}

env = gym.make("RobotLab-Go2-v0", cfg=env_cfg)
env = RslRlVecEnvWrapper(env, clip_actions=None)
u = env.unwrapped
dev = u.device
robot = u.scene["robot"]
meta["smi_after_env"] = smi()

# --- policy (student path, same as play.py) -------------------------------------
agent_cfg = MoECTSRunnerCfg()
agent_cfg.device = "cuda:0"
runner = OnPolicyRunnerCTS(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
if ckpt:
    runner.load(ckpt)
    meta["checkpoint_sha256"] = sha256_file(ckpt)
policy = runner.get_inference_policy(device=dev)
pnn = runner.alg.policy
meta["obs_groups"] = runner.cfg["obs_groups"]
meta["policy_class"] = type(pnn).__name__
meta["inference_fn"] = f"{type(pnn).__name__}.{policy.__name__}"
meta["devices"] = {
    "env_device": str(dev), "sim_device": str(u.sim.device), "runner_device": str(runner.device),
    "policy_param_device": str(next(pnn.parameters()).device),
    "torch_cuda0_name": torch.cuda.get_device_properties(0).name,
    "torch_cuda0_uuid": str(getattr(torch.cuda.get_device_properties(0), "uuid", "")),
    "torch_device_count": torch.cuda.device_count(),
}
meta["action_joint_names"] = list(u.action_manager.get_term("joint_pos")._joint_names)

# --- layout: family column, start row, cell, yaw ----------------------------------
ter = u.scene.terrain
e_idx = torch.arange(N, device=dev)
fam = torch.div(e_idx, C * E, rounding_mode="floor")
cel = torch.div(e_idx % (C * E), E, rounding_mode="floor")
epi = e_idx % E
ter.terrain_types[:] = fam
ter.terrain_levels[:] = epi % SPAWN_ROWS
ter.env_origins[:] = ter.terrain_origins[ter.terrain_levels, ter.terrain_types]
meta["terrain_origins_shape"] = list(ter.terrain_origins.shape)
cmd_a = torch.tensor([c["cmd"] for c in CELLS], device=dev, dtype=torch.float)[cel]
cmd_b = cmd_a.clone()
sw = torch.full((N,), 10 ** 9, device=dev, dtype=torch.long)
for ci, c in enumerate(CELLS):
    if c["kind"] == "stop":
        m = cel == ci
        cmd_b[m] = 0.0
        sw[m] = int(round(c["switch_s"] / DT))
yaw0 = torch.zeros(N, device=dev)
lin_mask = torch.tensor([c["kind"] in ("lin", "stop") for c in CELLS], device=dev)[cel]
yaw0[lin_mask] = -torch.atan2(cmd_a[lin_mask, 1], cmd_a[lin_mask, 0])
u._q_yaw = yaw0  # command direction points to world +x (along the rows of one family)

ct = u.command_manager.get_term("base_velocity")
target = cmd_a.clone()


def _fixed_resample(env_ids):
    ct.commands[env_ids] = target[env_ids]
    ct.time_left[env_ids] = 1.0e9


ct._resample = _fixed_resample

# --- reset with the evaluation seed (pairs initial states across checkpoints) -------
obs_buf, _ = u.reset(seed=args.eval_seed)
obs = TensorDict(obs_buf, batch_size=[N])
meta["obs_shapes"] = {k: list(v.shape) for k, v in obs.items()}

# terrain mesh hash (actual USD collision mesh)
try:
    import omni.usd
    from pxr import UsdGeom
    stage = omni.usd.get_context().get_stage()
    hs = []
    for prim in stage.Traverse():
        if str(prim.GetPath()).startswith("/World/ground") and prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            pts = np.array(mesh.GetPointsAttr().Get(), dtype=np.float32)
            idx = np.array(mesh.GetFaceVertexIndicesAttr().Get(), dtype=np.int64)
            hs.append((str(prim.GetPath()), int(pts.shape[0]), sha256_arr(np.round(pts, 5), idx)))
    meta["terrain_mesh"] = hs
except Exception as ex:  # pragma: no cover
    meta["terrain_mesh"] = f"failed: {ex}"
meta["terrain_origins_sha256"] = sha256_arr(np.round(ter.terrain_origins.cpu().numpy(), 5))

# initial-state fingerprint for pairing
init_root = robot.data.root_state_w[:, :7].cpu().numpy()
init_q = robot.data.joint_pos.cpu().numpy()
masses = robot.root_physx_view.get_masses().cpu().numpy()
stiff = robot.data.joint_stiffness.cpu().numpy() if hasattr(robot.data, "joint_stiffness") else np.zeros(1)
meta["pairing_sha256"] = {
    "init_root_pose": sha256_arr(np.round(init_root, 5)),
    "init_joint_pos": sha256_arr(np.round(init_q, 5)),
    "body_masses": sha256_arr(np.round(masses, 5)),
    "joint_stiffness": sha256_arr(np.round(stiff, 5)),
}

# --- checks before the rollout -----------------------------------------------------
g = torch.Generator(device=dev)
g.manual_seed(12345)  # separate generator: does not touch the env RNG
checks = {}
with torch.inference_mode():
    a0 = policy(obs)
    o1 = obs.clone()
    o1["critic"] = torch.randn(o1["critic"].shape, generator=g, device=dev) * 10.0
    checks["teacher_input_randomized_max_abs_action_change"] = float((policy(o1) - a0).abs().max())
    o2 = obs.clone()
    o2["policy"] = o2["policy"] + 0.1 * torch.randn(o2["policy"].shape, generator=g, device=dev)
    checks["policy_history_perturbed_max_abs_action_change"] = float((policy(o2) - a0).abs().max())
    o3 = obs.clone()
    o3["single_obs"] = o3["single_obs"] + 0.1 * torch.randn(o3["single_obs"].shape, generator=g, device=dev)
    checks["single_obs_perturbed_max_abs_action_change"] = float((policy(o3) - a0).abs().max())
    # same numbers through the explicit student modules (no teacher_encoder call)
    lat, _ = pnn.student_moe_encoder(pnn.actor_obs_normalizer(obs["policy"]))
    a_manual = pnn.actor(torch.cat([lat, pnn.single_obs_normalizer(obs["single_obs"])], dim=-1))
    checks["manual_student_path_vs_act_inference_max_abs"] = float((a_manual - a0).abs().max())
meta["checks_pre"] = checks

# --- rollout -------------------------------------------------------------------
hs_small = u.scene["height_scanner_small"]


def ground_z():
    z = hs_small.data.ray_hits_w[..., 2]
    z = torch.where(torch.isfinite(z), z, torch.nan)
    return torch.nanmean(z, dim=1)


def snap():
    d = robot.data
    return np.concatenate([
        d.root_pos_w.cpu().numpy(),                      # 0:3
        d.heading_w.cpu().numpy()[:, None],              # 3
        d.root_lin_vel_b.cpu().numpy(),                  # 4:7
        d.root_ang_vel_b.cpu().numpy(),                  # 7:10
        d.projected_gravity_b[:, 2:3].cpu().numpy(),     # 10
        (d.root_pos_w[:, 2] - ground_z()).cpu().numpy()[:, None],  # 11 height above ground
    ], axis=1).astype(np.float32)


traj = np.zeros((T + 1, N, 12), dtype=np.float32)
term = np.zeros((T + 1, N), dtype=bool)
traj[0] = snap()
cmd_err_single = 0.0
cmd_err_hist = 0.0
nonfinite = 0
act_abs_sum = torch.zeros(N, device=dev)
t0 = time.time()
smi_mid = None
with torch.inference_mode():
    for k in range(T):
        # the command shown to the policy at step k is the current target
        cmd_err_single = max(cmd_err_single, float((obs["single_obs"][:, 6:9] - target).abs().max()))
        cmd_err_hist = max(cmd_err_hist, float((obs["policy"][:, 87:90] - target).abs().max()))
        if args.policy == "student":
            act = policy(obs)
        else:
            act = torch.zeros(N, 12, device=dev)
        nonfinite += int((~torch.isfinite(act)).sum()) + int((~torch.isfinite(obs["policy"])).sum())
        act_abs_sum += act.abs().mean(dim=1)
        # command for the NEXT observation (computed at the end of env.step)
        target[:] = torch.where((k + 1 >= sw)[:, None], cmd_b, cmd_a)
        ct.commands[:] = target
        obs, _, _, _ = env.step(act)
        term[k + 1] = u.reset_terminated.cpu().numpy()
        traj[k + 1] = snap()
        if k == T // 2:
            smi_mid = smi()
torch.cuda.synchronize()
meta["rollout_wall_s"] = time.time() - t0
meta["smi_mid"] = smi_mid
meta["torch_max_mem_alloc_MiB"] = torch.cuda.max_memory_allocated() / 2 ** 20
checks_run = {
    "obs_single_cmd_vs_target_max_abs": cmd_err_single,
    "obs_history_latest_cmd_vs_target_max_abs": cmd_err_hist,
    "nonfinite_action_or_obs_count": nonfinite,
}
meta["checks_run"] = checks_run

# --- save trajectories, then metrics through q_post (same code path as re-runs) ----
np.savez(os.path.join(OUT, "traj.npz"), traj=traj, term=term, cel=cel.cpu().numpy(), fam=fam.cpu().numpy(),
         epi=epi.cpu().numpy(), cmd_a=cmd_a.cpu().numpy(), cmd_b=cmd_b.cpu().numpy(), sw=sw.cpu().numpy(),
         act_abs_mean=(act_abs_sum / T).cpu().numpy())
meta["smi_end"] = smi()
meta["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=1, default=str)
import q_post  # noqa: E402

summary = q_post.postprocess(OUT)

print("[Q-EVAL] done", args.tag, "N", N, "rollout_s", round(meta["rollout_wall_s"], 1))
print("[Q-EVAL] checks_pre", json.dumps(checks))
print("[Q-EVAL] checks_run", json.dumps(checks_run))
q_post.print_summary(args.tag, summary)
env.close()
simulation_app.close()
