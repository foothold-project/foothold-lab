"""EX-42 E1 D44 landing cells on 64 independent copies of the pinned tile.

This Kit child is launched only after the prep plan contains a D44 case and
timing contract. It writes per-step NPZ and per-case JSON, then a combined
receipt. No cell is inferred from map64 or from another checkpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401
import yaml
from isaaclab.app import AppLauncher

from foothold_s2.eval.ex42_d44_cells import contract, summarize
from foothold_s2.eval.ex42_eval_tile_mesh import preflight_replicas, source_tile


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--task", default="FootholdS2-Go2-S2-SB-v0")
parser.add_argument("--checkpoint", type=Path, required=True)
parser.add_argument("--plan", type=Path, required=True)
parser.add_argument("--mesh-dir", type=Path, required=True)
parser.add_argument("--replica-dir", type=Path, required=True)
parser.add_argument("--expected-replica-sha256", required=True)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--out", type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.envs != 64 or args.seed < 0 or not args.checkpoint.is_file() or args.out.exists():
    parser.error("D44 requires a fresh output, pinned checkpoint, seed and 64 envs")
plan_bytes = args.plan.read_bytes()
plan = yaml.safe_load(plan_bytes.decode("utf-8-sig"))
settings = contract(plan)
# prep pins /home/jay/data/... while the evaluator passes the resolved /mnt/win-d/... path (11/11 m250); compare both resolved
if (not settings["source_mesh_dir"] or Path(settings["source_mesh_dir"]).resolve() != args.mesh_dir.resolve()
        or not settings["source_mesh_sha256"]):
    parser.error("D44 prep must pin the one-tile source directory and mesh SHA")
source, tile = source_tile(args.mesh_dir)
if source["mesh_sha256"] != settings["source_mesh_sha256"]:
    parser.error("D44 source tile SHA differs from prep")
replica = preflight_replicas(args.mesh_dir, args.replica_dir, anchor="landing_center",
                             expected_mesh_sha256=args.expected_replica_sha256)
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import isaaclab_tasks  # noqa: E402,F401
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import foothold_s2.sb_tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, ex41_eval_loader, map_mode_cells, run_identity  # noqa: E402
from foothold_s2.eval.ex42_eval_tile_mesh import assign_independent_env_origins  # noqa: E402
from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg  # noqa: E402


FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")


def _indices(robot, sensor):
    body, sensing = list(robot.body_names), list(sensor.body_names)
    if any(body.count(name) != 1 or sensing.count(name) != 1 for name in FEET):
        raise RuntimeError("D44 requires four uniquely named robot and sensor feet")
    return [body.index(name) for name in FEET], [sensing.index(name) for name in FEET]


def _configure():
    env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
    agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
    env_cfg.scene.num_envs = args.envs
    env_cfg.seed = agent_cfg.seed = args.seed
    env_cfg.sim.device = agent_cfg.device = args.device
    env_cfg.scene.terrain.terrain_type = "generator"
    env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(
        args.replica_dir / "terrain_mesh.npz", replica["mesh_sha256"])
    env_cfg.scene.terrain.max_init_terrain_level = 7
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
    command_cfg = env_cfg.commands.base_velocity
    command_cfg.resampling_time_range = (1.0e9, 1.0e9)
    command_cfg.dynamic_flags = False
    command_cfg.flag_stride = 0
    if hasattr(env_cfg.actions.joint_pos, "max_delay_s"):
        env_cfg.actions.joint_pos.max_delay_s = 0.0
    return env_cfg, agent_cfg, disabled


def _steps(seconds, dt):
    value = round(seconds / dt)
    if value < 1 or abs(value * dt - seconds) > dt / 2:
        raise ValueError("D44 timing does not align with policy dt")
    return value


def _run_cell(env, raw, robot, sensor, body_ids, sensor_ids, term, runner, case_id, spec, dt):
    n = args.envs
    env.reset()
    terrain = raw.scene.terrain
    expected = torch.arange(n, device=raw.device)
    if (not torch.equal(terrain.terrain_levels, expected.div(8, rounding_mode="floor"))
            or not torch.equal(terrain.terrain_types, expected.remainder(8))):
        raise RuntimeError("D44 terrain assignment changed during reset")
    state = robot.data.root_state_w.clone()
    local_anchor = tile["anchors_local_m"]["landing_center"]
    if spec["task"] == "stop_restart":
        approach = tile["anchors_local_m"]["approach"]
        shift = torch.tensor([approach[i] - local_anchor[i] for i in range(3)], device=raw.device)
        state[:, :3] += shift
    state[:, 7:] = 0
    robot.write_root_pose_to_sim(state[:, :7])
    robot.write_root_velocity_to_sim(state[:, 7:])
    obs = env.get_observations()
    if checkpoint_preparation["checkpoint_pose_commands"]:
        ex41_eval_loader.verify_ex41_pose_observation(obs)
    map_mode_cells.disable_heading_for_fixed_eval(term)
    policy = adapters.S2Policy(runner, n, z_mode="mean", act_mode="mean", map_mode=spec["map_mode"])
    policy.reset(torch.ones(n, dtype=torch.bool, device=raw.device))
    if bool(policy.pstate.use_gt.any()) != (spec["map_mode"] == "eval_gt"):
        raise RuntimeError("D44 requested map mode differs from policy input")
    t = settings["timing"]
    settle = _steps(t["settle_s"], dt)
    approach = _steps(t["approach_limit_s"], dt)
    stop = _steps(t["stop_s"], dt)
    restart = _steps(t["restart_limit_s"], dt)
    turn = _steps(settings["turn_seconds"], dt)
    total = settle + (turn if spec["task"].startswith("turn_") else approach + stop + restart)
    rows = {key: [] for key in ("root_pos_w", "root_quat_w", "foot_pos_w", "contact",
                                "body_vel_b", "alive", "phase_id", "cmd_post")}
    alive = torch.ones(n, dtype=torch.bool, device=raw.device)
    entered = torch.zeros(n, dtype=torch.bool, device=raw.device)
    offset = (raw.scene.env_origins - torch.tensor(local_anchor, device=raw.device)).detach().cpu().numpy()
    for k in range(total):
        phase = 0 if k < settle else (1 if spec["task"].startswith("turn_") else
                1 if k < settle + approach else 2 if k < settle + approach + stop else 3)
        term.vel_command_b[:, :3] = 0.0
        if phase == 1 and spec["task"].startswith("turn_"):
            term.vel_command_b[:, 2] = settings["turn_rate_radps"] * (1 if spec["task"] == "turn_left" else -1)
        elif phase == 1:
            term.vel_command_b[~entered, 0] = settings["approach_vx_mps"]
        elif phase == 3:
            term.vel_command_b[:, 0] = settings["restart_vx_mps"]
        term.stand.copy_(torch.linalg.norm(term.vel_command_b[:, :3], dim=1) == 0)
        map_mode_cells.assert_heading_off_for_fixed_eval(term)
        if bool(term.is_flag_env.any()):
            raise RuntimeError("D44 fixed command evaluation contains a flag environment")
        requested = term.vel_command_b[:, :3].clone()
        action = policy(obs)
        obs, _reward, done, _extras = env.step(action)
        active = alive & ~done.bool()
        if bool(active.any()) and not torch.allclose(
                term.vel_command_b[active, :3], requested[active], atol=1e-5, rtol=0):
            raise RuntimeError("D44 command changed during the policy step")
        policy.reset(done)
        alive &= ~done.bool()
        if checkpoint_preparation["checkpoint_pose_commands"]:
            ex41_eval_loader.verify_ex41_pose_observation(obs)
        if phase == 1 and spec["task"] == "stop_restart":
            local_x = robot.data.root_pos_w[:, 0] - torch.as_tensor(offset[:, 0], device=raw.device)
            band = tile["anchors_local_m"]["stop_band_x"]
            entered |= (local_x >= band[0]) & (local_x <= band[1]) & alive
        force = torch.linalg.vector_norm(sensor.data.net_forces_w[:, sensor_ids], dim=-1)
        data = robot.data
        rows["root_pos_w"].append(data.root_pos_w.detach().cpu().numpy().copy())
        rows["root_quat_w"].append(data.root_quat_w.detach().cpu().numpy().copy())
        rows["foot_pos_w"].append(data.body_pos_w[:, body_ids].detach().cpu().numpy().copy())
        rows["contact"].append((force > 1.0).detach().cpu().numpy().copy())
        rows["body_vel_b"].append(data.root_lin_vel_b.detach().cpu().numpy().copy())
        rows["alive"].append(alive.detach().cpu().numpy().copy())
        rows["phase_id"].append(np.full(n, phase, dtype=np.int16))
        rows["cmd_post"].append(term.vel_command_b[:, :3].detach().cpu().numpy().copy())
    trace = {key: np.stack(value) for key, value in rows.items()}
    trace.update(tile_offset_w=offset, approach_entered=entered.detach().cpu().numpy(), dt=np.asarray(dt),
                 case_id=np.asarray(case_id), map_mode=np.asarray(spec["map_mode"]))
    return trace


def main():
    env = None
    try:
        env_cfg, agent_cfg, disabled = _configure()
        checkpoint_state, checkpoint_preparation = ex41_eval_loader.load_checkpoint_for_eval(
            env_cfg, args.checkpoint)
        env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
        raw = env.unwrapped
        assign_independent_env_origins(raw)
        robot, sensor = raw.scene["robot"], raw.scene["contact_forces"]
        body_ids, sensor_ids = _indices(robot, sensor)
        term = raw.command_manager.get_term("base_velocity")
        dt = float(raw.step_dt)
        runner, _saved = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint,
                                                 args.device, checkpoint_state=checkpoint_state)
        checkpoint_sha = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        args.out.mkdir(parents=True, exist_ok=False)
        cases = {}
        for case_id in (*settings["judge_cases"], *settings["record_cases"]):
            spec = settings["case_specs"][case_id]
            trace = _run_cell(env, raw, robot, sensor, body_ids, sensor_ids, term, runner,
                              case_id, spec, dt)
            raw_file = args.out / f"{case_id}.npz"
            np.savez_compressed(raw_file, **trace)
            scored = summarize(trace, spec=spec, anchors=tile["anchors_local_m"], settings=settings, dt=dt)
            row = {"case_id": case_id, "task": spec["task"], "map_mode": spec["map_mode"],
                   "role": spec["role"], **scored,
                   "trace_file": str(raw_file),
                   "trace_sha256": hashlib.sha256(raw_file.read_bytes()).hexdigest()}
            case_file = args.out / f"{case_id}.json"
            case_file.write_text(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
            cases[case_id] = {key: row[key] for key in ("case_id", "task", "map_mode", "role",
                "envs", "valid_count", "success_count", "survival_count", "trace_file", "trace_sha256")}
            cases[case_id].update(raw_file=str(case_file), raw_sha256=hashlib.sha256(case_file.read_bytes()).hexdigest())
            print("D44_CASE_DONE", case_id, scored["valid_count"], scored["success_count"],
                  scored["survival_count"], flush=True)
        result = {"format": "foothold-ex42-d44-eval/1", "state": "done",
                  "checkpoint": str(args.checkpoint.resolve()), "checkpoint_sha256": checkpoint_sha,
                  "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(), "source_mesh_sha256": source["mesh_sha256"],
                  "replica_mesh_sha256": replica["mesh_sha256"], "seed": args.seed, "envs": args.envs,
                  "dt": dt, "dr_disabled": disabled,
                  "run_identity": run_identity.safe_collect(args.device, checkpoint_sha, eval_seed=args.seed),
                  "checkpoint_preparation": checkpoint_preparation, "cases": cases}
        (args.out / "d44_cells.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print("D44_EVAL_DONE", args.out, flush=True)
    finally:
        if env is not None:
            env.close()
        app.close()


if __name__ == "__main__":
    main()
