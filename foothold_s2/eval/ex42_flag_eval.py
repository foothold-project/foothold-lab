"""E1F flag cell child: one flag count, 64 env, three map modes on pinned A23 mesh.

Run this file twice, once for flag_one and once for flag_four. The parent
evaluation records both receipts before its stage judge can return PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401
import yaml
from isaaclab.app import AppLauncher

from foothold_s2.eval.ex42_flag_cells import COUNTS, MODES, contract, score_trace
from foothold_s2.eval.ex42_mesh_eval import preflight


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--task", default="FootholdS2-Go2-S2-SB-v0")
parser.add_argument("--checkpoint", type=Path, required=True)
parser.add_argument("--plan", type=Path, required=True)
parser.add_argument("--mesh-dir", type=Path, required=True)
parser.add_argument("--expected-mesh-sha256", required=True)
parser.add_argument("--count", choices=tuple(COUNTS), required=True)
parser.add_argument("--seed", type=int, required=True)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--out", type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.envs != 64 or args.seed < 0 or not args.checkpoint.is_file() or args.out.exists():
    parser.error("E1F flag evaluation requires 64 envs, a pinned checkpoint and fresh output")
plan_bytes = args.plan.read_bytes()
plan = yaml.safe_load(plan_bytes.decode("utf-8-sig"))
settings = contract(plan)
mesh = preflight(args.mesh_dir)
if mesh["mesh_sha256"] != args.expected_mesh_sha256:
    parser.error("E1F flag evaluation mesh SHA differs")
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import isaaclab_tasks  # noqa: E402,F401
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import foothold_s2.sb_tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, ex41_eval_loader, fixed_terrain, map_mode_cells, run_identity  # noqa: E402


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _configure():
    env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
    agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
    env_cfg.scene.num_envs = args.envs
    env_cfg.seed = agent_cfg.seed = args.seed
    env_cfg.sim.device = agent_cfg.device = args.device
    from foothold_s2.eval.ex42_mesh_eval import attach
    mounted = attach(env_cfg, args.mesh_dir)
    if mounted["mesh_sha256"] != args.expected_mesh_sha256:
        raise RuntimeError("E1F flag mounted mesh differs from preflight")
    env_cfg.observations.policy.enable_corruption = False
    from foothold_s2.sensors import start_obs
    start_obs.AUG.enabled = False
    disabled = adapters.disable_eval_randomization(env_cfg)
    for name in ("terrain_levels", "command_range"):
        if hasattr(env_cfg.curriculum, name):
            setattr(env_cfg.curriculum, name, None)
    env_cfg.events.reset_base.params["pose_range"] = {
        "x": (0.0, 0.0), "y": (0.0, 0.0), "yaw": (0.0, 0.0)}
    env_cfg.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
    env_cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)
    cmd = env_cfg.commands.base_velocity
    cmd.seed = args.seed
    cmd.flag_stride = 1
    cmd.flag_count = COUNTS[args.count]
    cmd.dynamic_flags = False
    cmd.clock_scatter = False
    cmd.resampling_time_range = (1.0e9, 1.0e9)
    cmd.params = {**dict(cmd.params or {}), "flag_reach_m": settings["reach_radius_m"],
                  "flag_spin_threshold": 0.0, "backoff_prob": 0.0,
                  "flag_vmax": settings["flag_speed_mps"]}
    if hasattr(env_cfg.actions.joint_pos, "max_delay_s"):
        env_cfg.actions.joint_pos.max_delay_s = 0.0
    return env_cfg, agent_cfg, disabled, mounted


def _run_case(env, raw, robot, term, runner, mode, dt):
    n = args.envs
    assignment = fixed_terrain.apply(raw, cols=mesh["eval_cols"])
    env.reset()
    terrain = raw.scene.terrain
    expected_levels, expected_types = fixed_terrain.fixed_assignment(n, assignment["rows"], mesh["eval_cols"])
    if (not np.array_equal(terrain.terrain_levels.detach().cpu().numpy(), expected_levels)
            or not np.array_equal(terrain.terrain_types.detach().cpu().numpy(), expected_types)):
        raise RuntimeError("E1F flag fixed terrain assignment changed during reset")
    if not bool(term.is_flag_env.all()) or len(term.flag_ids) != n or term.flag_state.flags.shape != (n, COUNTS[args.count], 2):
        raise RuntimeError("E1F flag command term did not select every env")
    expected_flags = np.stack([
        np.stack([terrain.env_origins[i, :2].detach().cpu().numpy() + np.array([.5 + j, 0.])
                  for j in range(COUNTS[args.count])]) for i in range(n)])
    actual_flags = term.flag_state.flags.detach().cpu().numpy()
    if not np.allclose(actual_flags, expected_flags, atol=1e-5, rtol=0):
        raise RuntimeError("E1F flag targets differ from approved straight A23 line")
    term.flag_state.v.fill_(settings["flag_speed_mps"])
    term._update_command()
    map_mode_cells.disable_heading_for_fixed_eval(term)
    policy = adapters.S2Policy(runner, n, z_mode="mean", act_mode="mean", map_mode=mode)
    policy.reset(torch.ones(n, dtype=torch.bool, device=raw.device))
    if bool(policy.pstate.use_gt.any()) != (mode == "eval_gt"):
        raise RuntimeError("E1F flag map mode differs from policy input")
    obs = env.get_observations()
    if checkpoint_preparation["checkpoint_pose_commands"]:
        ex41_eval_loader.verify_ex41_pose_observation(obs)
    steps = round(settings["seconds"] / dt)
    if steps < 1 or abs(steps * dt - settings["seconds"]) > dt / 2:
        raise RuntimeError("E1F flag evaluation seconds do not align with policy dt")
    rows = {"root_pos_w": [], "root_vel_w": [], "alive": [],
            "cmd_policy_input": [], "cmd_after_step": []}
    alive = torch.ones(n, dtype=torch.bool, device=raw.device)
    for _ in range(steps):
        if not bool(term.is_flag_env.all()) or not torch.allclose(
                term.flag_state.v[alive],
                torch.full_like(term.flag_state.v[alive], settings["flag_speed_mps"]), atol=1e-6, rtol=0):
            raise RuntimeError("E1F flag command or speed changed during fixed evaluation")
        requested = term.vel_command_b[:, :3].clone()
        if not bool(torch.isfinite(requested[alive]).all()):
            raise RuntimeError("E1F flag policy input command is nonfinite")
        action = policy(obs)
        obs, _reward, done, _extras = env.step(action)
        # Flag commands must change as the robot moves. Record both sides of the
        # step; equality would incorrectly reject correct target tracking.
        if not bool(torch.isfinite(term.vel_command_b[alive & ~done.bool(), :3]).all()):
            raise RuntimeError("E1F flag post-step command is nonfinite")
        policy.reset(done)
        alive &= ~done.bool()
        if checkpoint_preparation["checkpoint_pose_commands"]:
            ex41_eval_loader.verify_ex41_pose_observation(obs)
        rows["root_pos_w"].append(robot.data.root_pos_w.detach().cpu().numpy().copy())
        rows["root_vel_w"].append(robot.data.root_lin_vel_w.detach().cpu().numpy().copy())
        rows["alive"].append(alive.detach().cpu().numpy().copy())
        rows["cmd_policy_input"].append(requested.detach().cpu().numpy().copy())
        rows["cmd_after_step"].append(term.vel_command_b[:, :3].detach().cpu().numpy().copy())
    trace = {name: np.stack(values) for name, values in rows.items()}
    trace.update(flags_w=actual_flags, dt=np.asarray(dt),
                 env_origins_w=terrain.env_origins.detach().cpu().numpy().copy(),
                 terrain_levels=terrain.terrain_levels.detach().cpu().numpy().copy(),
                 terrain_types=terrain.terrain_types.detach().cpu().numpy().copy())
    return trace, assignment


def main():
    global checkpoint_preparation
    env = None
    try:
        env_cfg, agent_cfg, disabled, mounted = _configure()
        checkpoint_state, checkpoint_preparation = ex41_eval_loader.load_checkpoint_for_eval(
            env_cfg, args.checkpoint)
        env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
        raw = env.unwrapped
        robot = raw.scene["robot"]
        term = raw.command_manager.get_term("base_velocity")
        dt = float(raw.step_dt)
        runner, _saved = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint,
                                                 args.device, checkpoint_state=checkpoint_state)
        args.out.mkdir(parents=True, exist_ok=False)
        receipt = {"format": "foothold-ex42-flag-eval/1", "state": "done",
                   "checkpoint": str(args.checkpoint.resolve()), "checkpoint_sha256": _sha(args.checkpoint),
                   "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                   "mesh_sha256": mounted["mesh_sha256"], "seed": args.seed,
                   "envs": args.envs, "count": args.count, "dt": dt,
                   "dr_disabled": disabled, "checkpoint_preparation": checkpoint_preparation,
                   "run_identity": run_identity.safe_collect(args.device, _sha(args.checkpoint), eval_seed=args.seed),
                   "cases": {}}
        for mode in MODES:
            case = f"{args.count}_{mode}"
            trace, assignment = _run_case(env, raw, robot, term, runner, mode, dt)
            path = args.out / f"{case}.npz"
            np.savez_compressed(path, **trace)
            raw_row = {"case_id": case, **settings["case_specs"][case],
                       **score_trace(trace, settings["case_specs"][case], settings),
                       "trace_file": str(path), "trace_sha256": _sha(path),
                       "fixed_terrain": assignment}
            raw_file = args.out / f"{case}.json"
            raw_file.write_text(json.dumps(raw_row, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
            receipt["cases"][case] = {"trace_file": str(path), "trace_sha256": _sha(path),
                                      "raw_file": str(raw_file), "raw_sha256": _sha(raw_file),
                                      **{key: raw_row[key] for key in ("envs", "valid_count", "success_count", "survival_count")}}
            print("E1F_FLAG_CASE_DONE", case, raw_row["success_count"], raw_row["survival_count"], flush=True)
        (args.out / "flag_cells.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print("E1F_FLAG_EVAL_DONE", args.out, flush=True)
    finally:
        if env is not None:
            env.close()
        app.close()


if __name__ == "__main__":
    main()
