# Branch runner (outside the repository) for controlled branches from a parent checkpoint (VERIFY-astra-6 2)
# and the CMD-R adapter (VERIFY-astra-6 3, first row). Repository training code is used unchanged
# (Go2EnvCfg, MoECTSRunnerCfg, OnPolicyRunnerCTS.learn); this file only sets the branch state before learn().
#
#   parent      : --parent <model_L.pt>, file SHA recorded, loaded iter must equal L in the file name
#   clock       : next label L+1, env.common_step_counter = (L+1) x 24 (24 checked against runner and command cfg)
#   schedule    : before the first rollout the command ranges (stage rule of commands.py:128-139), env ranges,
#                 remaining stages, zero probability (get_current_scale) and the reward weights (the two
#                 gradual_reward_weight_modification terms only) are set explicitly; terrain curriculum is not called
#   optimizer   : both Adam states from the parent; alg.learning_rate = main optimizer lr; student encoder lr untouched
#   terrain     : levels 0..5 stratified per column by slot index (branch_lib.stratified_levels), origins updated
#   seed        : declared branch seed (env and agent), init_at_random_ep_len = False, new episodes (age 0)
#   bundle      : state before the first rollout -> <out>/bundle.json + bundle.npz
#   CMD-R       : --cmdr on wraps only the command term reset so the sampler sees age 0 (branch_lib.ResetAgeAdapter)
#   guard       : without BRANCH_CONTRACT_CONFIRMED only --gate runs are allowed (<= 3 updates and <= 1024 envs,
#                 or rollout only with <= 4096 envs)
import argparse
import json
import os
import pickle
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import branch_lib as B  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--parent", required=True)
ap.add_argument("--seed", type=int, required=True)
ap.add_argument("--num_envs", type=int, default=1024)
ap.add_argument("--updates", type=int, default=0)
ap.add_argument("--rollout_steps", type=int, default=0, help="rollout only (no update), record command events")
ap.add_argument("--cmdr", choices=["off", "on"], default="off")
ap.add_argument("--gate", action="store_true")
ap.add_argument("--tag", required=True)
args0, _ = ap.parse_known_args()
ok, why = B.gate_allowed(args0.gate, args0.num_envs, args0.updates, bool(os.environ.get("BRANCH_CONTRACT_CONFIRMED")))
if not ok:
    print("[BRANCH]", why)
    sys.exit(4)

import h5py  # noqa: F401,E402
import tensordict  # noqa: F401,E402
from isaaclab.app import AppLauncher  # noqa: E402

AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
args.headless = True
app = AppLauncher(args).app

import hashlib  # noqa: E402

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from rsl_rl.runners import OnPolicyRunnerCTS  # noqa: E402

import robot_lab.tasks  # noqa: F401,E402
from robot_lab.tasks.go2.env_cfg import Go2EnvCfg  # noqa: E402
from robot_lab.tasks.go2.mdp.curriculums import gradual_reward_weight_modification  # noqa: E402
from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg  # noqa: E402

REPO = "C:/isaac/ext/go2_rl_robotlab"
OUT = os.path.join(os.environ.get("BRANCH_OUT") or os.path.join(HERE, "..", "out", "branch"), args.tag)  # BRANCH_OUT: 10/13 새 실행은 _eval/out 밖 (ASTRA 17 §4)
os.makedirs(OUT, exist_ok=True)
T0 = time.time()


def fsha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dump(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), "w", encoding="utf-8"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


meta = {"args": {k: v for k, v in vars(args).items()}, "gate_decision": why, "t_start": time.strftime("%Y-%m-%d %H:%M:%S"),
        "env_vars": {k: os.environ.get(k) for k in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "BRANCH_CONTRACT_CONFIRMED")}}
meta["parent_sha256"] = fsha(args.parent)
meta["code"] = {"repo_head": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
                "repo_tracked_changes": subprocess.run(["git", "-C", REPO, "status", "--short", "--untracked-files=no"], capture_output=True, text=True).stdout.strip(),
                "files_sha256": {p: fsha(os.path.join(REPO, p)) for p in (
                    "source/robot_lab/robot_lab/tasks/go2/mdp/commands.py", "source/robot_lab/robot_lab/tasks/go2/mdp/curriculums.py",
                    "source/robot_lab/robot_lab/tasks/go2/mdp/utils.py", "source/robot_lab/robot_lab/tasks/go2/env_cfg.py",
                    "source/rsl_rl/rsl_rl/runners/on_policy_runner_cts.py", "source/rsl_rl/rsl_rl/algorithms/moe_cts.py")},
                "branch_files_sha256": {f: fsha(os.path.join(HERE, f)) for f in ("branch_run.py", "branch_lib.py")}}

# ---- env and runner (training configuration unchanged except num_envs and the declared seed) -----------------
env_cfg = Go2EnvCfg()
env_cfg.scene.num_envs = args.num_envs
env_cfg.seed = args.seed
env_cfg.sim.device = "cuda:0"
agent_cfg = MoECTSRunnerCfg()
agent_cfg.seed = args.seed
agent_cfg.device = "cuda:0"
env_cfg.log_dir = OUT
env = gym.make("RobotLab-Go2-v0", cfg=env_cfg)
env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
u = env.unwrapped
dev = u.device
runner = OnPolicyRunnerCTS(env, agent_cfg.to_dict(), log_dir=OUT, device=agent_cfg.device)
ct = u.command_manager.get_term("base_velocity")
ter = u.scene.terrain
robot = u.scene["robot"]
cm = u.curriculum_manager

# ---- parent ----------------------------------------------------------------------------------------------------
runner.load(args.parent)
L = int(runner.current_learning_iteration)
fname_L = int(os.path.basename(args.parent).split("_")[1].split(".")[0])
assert L == fname_L, f"loaded iter {L} != file name {fname_L}"
steps = int(runner.cfg["num_steps_per_env"])
assert steps == B.STEPS_PER_ITER == int(ct.cfg.num_steps_per_iter), (steps, ct.cfg.num_steps_per_iter)
nxt, ctr = B.next_label_and_counter(L, steps)
runner.current_learning_iteration = nxt
u.common_step_counter = ctr
lr_main_loaded = float(runner.alg.optimizer.param_groups[0]["lr"])
lr_stu_loaded = float(runner.alg.optimizer_stu_enc.param_groups[0]["lr"])
runner.alg.learning_rate = lr_main_loaded
meta["clock"] = {"parent_iter": L, "next_label": nxt, "common_step_counter": ctr, "steps_per_iter": steps,
                 "lr_main_loaded": lr_main_loaded, "lr_student_encoder_loaded": lr_stu_loaded, "alg_learning_rate_set": runner.alg.learning_rate}

# ---- terrain levels: stratified 0..5 per column --------------------------------------------------------------------
lv = B.stratified_levels(ter.terrain_types.cpu().numpy(), 6)
ter.terrain_levels[:] = torch.as_tensor(lv, device=ter.terrain_levels.device, dtype=ter.terrain_levels.dtype)
ter.env_origins[:] = ter.terrain_origins[ter.terrain_levels, ter.terrain_types]

# ---- explicit schedule sync -----------------------------------------------------------------------------------------
cur_iter = ctr // int(ct.cfg.num_steps_per_iter)
ranges, rem = B.apply_command_stages(ct.cfg.command_range_curriculum, cur_iter)
if ranges is not None:
    for k in ("lin_vel_x", "lin_vel_y", "ang_vel_yaw"):
        ct.command_ranges[k] = ranges[k]
    ct.max_lin_vel = max(abs(ct.command_ranges["lin_vel_x"][0]), abs(ct.command_ranges["lin_vel_x"][1]),
                         abs(ct.command_ranges["lin_vel_y"][0]), abs(ct.command_ranges["lin_vel_y"][1]))
    ct.cfg.command_range_curriculum[:] = rem
    ct._update_env_command_ranges()
if ct.cfg.zero_command_curriculum is not None:
    ct.zero_command_prob = ct.get_current_scale(ct.cfg.zero_command_curriculum)
all_ids = torch.arange(u.num_envs, device=dev)
synced_terms = []
for name, tc in zip(cm._term_names, cm._term_cfgs):
    if tc.func is gradual_reward_weight_modification:
        tc.func(u, all_ids, **tc.params)
        synced_terms.append(name)

# ---- command event recorder (+ optional CMD-R adapter) ----------------------------------------------------------------
EV = []
FLAG = {"in_reset": False, "branch_reset": False, "k": -1}
_orig_resample = ct._resample


def _rec_resample(env_ids):
    if len(env_ids) == 0:
        return _orig_resample(env_ids)
    age = u.episode_length_buf[env_ids].clone().float()
    acc = ct.commands_xy_accumulation[env_ids].norm(dim=1)
    rd = torch.clip(0.625 * ct.terrain_length - acc * ct.cfg.resampling_time, 0.0)
    lb = torch.clip(rd / ((u.max_episode_length - age + 1 + 1e-9) * u.step_dt), 0.0)
    if FLAG["branch_reset"]:
        reason = torch.full_like(age, 3)
    elif FLAG["in_reset"]:
        reason = torch.where(u.reset_time_outs[env_ids], 1.0, 2.0)
    else:
        reason = torch.zeros_like(age)
    _orig_resample(env_ids)
    c = ct.commands[env_ids]
    hi = ct.env_command_ranges["lin_vel_x"][env_ids, 1]
    EV.append(torch.stack([torch.full_like(age, FLAG["k"]), env_ids.float(), age, reason, lb, (lb > hi).float(),
                           c[:, 0], c[:, 1], c[:, 2], ct.time_left[env_ids]], 1).detach().cpu())


ct._resample = _rec_resample
_orig_reset = ct.reset


def _flag_reset(env_ids=None):
    FLAG["in_reset"] = True
    try:
        return _orig_reset(env_ids)
    finally:
        FLAG["in_reset"] = False


ct.reset = _flag_reset
adapter = B.ResetAgeAdapter(u, ct) if args.cmdr == "on" else None

# ---- branch reset: new episodes at the new origins, terrain curriculum not called -----------------------------------------
tl_idx = cm._term_names.index("terrain_levels")
tl_func = cm._term_cfgs[tl_idx].func
cm._term_cfgs[tl_idx].func = lambda env, env_ids, **kw: torch.mean(ter.terrain_levels.float())
FLAG["branch_reset"] = True
u.reset()
FLAG["branch_reset"] = False
cm._term_cfgs[tl_idx].func = tl_func
obs = env.get_observations()


# ---- state ------------------------------------------------------------------------------------------------------------
def opt_state(o):
    st = [v for v in o.state.values()]
    return {"lr_groups": [g["lr"] for g in o.param_groups], "steps": sorted({float(v["step"]) for v in st if "step" in v})[:3], "n": len(st),
            "sha": B.sha_tensor(*[v[k] for v in st for k in ("exp_avg", "exp_avg_sq") if k in v]) if st else None}


def state(where):
    rm = u.reward_manager
    lvn = ter.terrain_levels.cpu().numpy()
    d = robot.data
    act = list(robot.actuators.values())[0]
    jt = u.action_manager.get_term("joint_pos")
    sd = runner.alg.policy.state_dict()
    root = d.root_link_pose_w
    return {
        "where": where, "label_next": int(runner.current_learning_iteration), "common_step_counter": int(u.common_step_counter),
        "iter_from_counter": int(u.common_step_counter) // 24,
        "command_ranges": {k: list(v) for k, v in ct.command_ranges.items()},
        "env_ranges_unique": {k: torch.unique(ct.env_command_ranges[k], dim=0).cpu().tolist() for k in ("lin_vel_x", "lin_vel_y", "ang_vel_yaw")},
        "remaining_stages": [s["iter"] for s in ct.cfg.command_range_curriculum], "zero_command_prob": float(ct.zero_command_prob),
        "reward_weights": {n: float(rm.get_term_cfg(n).weight) for n in rm.active_terms},
        "terrain_level_hist": np.bincount(lvn, minlength=10).tolist(),
        "terrain_level_per_column_ok": bool(all(np.ptp(np.bincount(lvn[ter.terrain_types.cpu().numpy() == c], minlength=6)[:6]) <= 1
                                                 for c in np.unique(ter.terrain_types.cpu().numpy()))),
        "origins_vs_terrain_origins_max_abs": float((ter.env_origins - ter.terrain_origins[ter.terrain_levels, ter.terrain_types]).abs().max()),
        "scene_env_origins_vs_terrain_max_abs": float((u.scene.env_origins - ter.env_origins).abs().max()),
        "root_xy_minus_origin_max_abs": float((root[:, :2] - ter.env_origins[:, :2]).abs().max()),
        "episode_length_buf": [int(u.episode_length_buf.min()), int(u.episode_length_buf.max())],
        "alg_learning_rate": float(runner.alg.learning_rate), "optimizer": opt_state(runner.alg.optimizer),
        "optimizer_stu_enc": opt_state(runner.alg.optimizer_stu_enc),
        "model_sha": B.sha_tensor(*[sd[k] for k in sorted(sd)]),
        "rng": {"torch_cpu": B.sha_tensor(torch.get_rng_state()), "torch_cuda": B.sha_tensor(torch.cuda.get_rng_state()),
                "numpy": hashlib.sha256(np.random.get_state()[1].tobytes()).hexdigest(), "python": hashlib.sha256(pickle.dumps(random.getstate())).hexdigest()},
        "sha": {"levels": B.sha_tensor(ter.terrain_levels), "origins": B.sha_tensor(ter.env_origins), "root_pose": B.sha_tensor(root),
                "joint_pos": B.sha_tensor(d.joint_pos), "masses": B.sha_tensor(robot.root_physx_view.get_masses()),
                "coms": B.sha_tensor(robot.root_physx_view.get_coms()), "materials": B.sha_tensor(robot.root_physx_view.get_material_properties()),
                "gains": B.sha_tensor(act.stiffness, act.damping), "motor_offset": B.sha_tensor(jt._offset),
                "delay": B.sha_tensor(act.positions_delay_buffer.time_lags), "commands": B.sha_tensor(ct.commands)},
    }


st0 = state("before first rollout")
o0 = obs if isinstance(obs, dict) or hasattr(obs, "keys") else obs
st0["obs_sha"] = {k: B.sha_tensor(o0[k]) for k in o0.keys()}
st0["obs_cmd_vs_commands_max_abs"] = float((o0["single_obs"][:, 6:9] - ct.commands).abs().max())
st0["synced_reward_terms"] = synced_terms
st0["first_commands"] = {"vx_minmax": [float(ct.commands[:, 0].min()), float(ct.commands[:, 0].max())],
                         "vy_minmax": [float(ct.commands[:, 1].min()), float(ct.commands[:, 1].max())],
                         "wz_minmax": [float(ct.commands[:, 2].min()), float(ct.commands[:, 2].max())],
                         "abs_planar_gt_0.5_frac": float((ct.commands[:, :2].abs() > 0.5).any(dim=1).float().mean())}
dump("bundle.json", {"meta": meta, "state": st0})
np.savez_compressed(os.path.join(OUT, "bundle.npz"), levels=ter.terrain_levels.cpu().numpy(), origins=ter.env_origins.cpu().numpy(),
                    root_pose=robot.data.root_link_pose_w.cpu().numpy(), joint_pos=robot.data.joint_pos.cpu().numpy(),
                    commands=ct.commands.cpu().numpy(), episode_length_buf=u.episode_length_buf.cpu().numpy(),
                    torch_cpu_rng=torch.get_rng_state().numpy(), torch_cuda_rng=torch.cuda.get_rng_state().cpu().numpy())
print("[BRANCH] bundle", json.dumps({k: st0[k] for k in ("label_next", "common_step_counter", "command_ranges", "zero_command_prob")}), flush=True)

# ---- updates (gate: <= 3) ---------------------------------------------------------------------------------------------------
saves = []
if args.updates > 0:
    _orig_save = OnPolicyRunnerCTS.save

    def _save(self, path, it, last_model, infos=None):
        _orig_save(self, path, it, last_model, infos)
        s = state(f"save it={it} last={last_model}")
        s["file"] = os.path.basename(path)
        saves.append(s)

    OnPolicyRunnerCTS.save = _save
    if args.gate:
        runner.cfg["save_interval"] = 1  # gate: every update; experiment keeps the runner cfg (500: 0 / 2k / 4k points)
    runner.learn(num_learning_iterations=args.updates, init_at_random_ep_len=False)
    dump("saves.json", saves)

# ---- rollout only (CMD-R test) ------------------------------------------------------------------------------------------------
roll = {}
if args.rollout_steps > 0:
    runner.train_mode()
    logs = {}
    cmd_steps = np.zeros((args.rollout_steps, u.num_envs, 3), np.float32)
    lv_mean = []
    with torch.inference_mode():
        for k in range(args.rollout_steps):
            FLAG["k"] = k
            obs, _, _, extras = env.step(runner.alg.act(obs))
            for key, v in extras.get("log", {}).items():
                if key.startswith("Episode_Termination") or key.startswith("Curriculum"):
                    logs.setdefault(key, []).append(float(v) if not hasattr(v, "item") else float(v.item()))
            cmd_steps[k] = ct.commands.cpu().numpy()
            if k % 50 == 0:
                lv_mean.append(float(ter.terrain_levels.float().mean()))
    np.save(os.path.join(OUT, "cmd_steps.npy"), cmd_steps)
    roll = {"logs_sum_or_last": {k: (sum(v) if "Termination" in k else v[-1]) for k, v in logs.items()}, "logs_n": {k: len(v) for k, v in logs.items()},
            "terrain_level_mean_every_50": lv_mean, "adapter_calls": adapter.calls if adapter else None}
ev = torch.cat(EV).numpy() if EV else np.zeros((0, 10), np.float32)
np.save(os.path.join(OUT, "events.npy"), ev)
meta["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
meta["wall_s"] = time.time() - T0
meta["torch_max_mem_alloc_MiB"] = torch.cuda.max_memory_allocated() / 2 ** 20
dump("result.json", {"meta": meta, "rollout": roll, "n_events": int(len(ev)), "final_state": state("end")})
print("[BRANCH] done", args.tag, flush=True)
env.close()
app.close()
