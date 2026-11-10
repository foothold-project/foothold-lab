"""EX-40 flat stance receipt, one checkpoint and one map mode per Kit child.

The physical sample follows rr_stance_probe.py in scripter-rr-probe @503ff5fb.
It records all feet before the score thresholds are applied by ex40_score.py.
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
from isaaclab.app import AppLauncher


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--task", default="FootholdS2-Go2-S2-SB-v0")
parser.add_argument("--checkpoint", type=Path, required=True)
parser.add_argument("--mode", choices=("eval_gt", "probe_prop_only", "eval_pred"), required=True)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--seconds", type=float, default=3.0)
parser.add_argument("--skip-seconds", type=float, default=1.0)
parser.add_argument("--contact-n", type=float, default=1.0)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--out", type=Path, required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if (args.envs < 1 or args.seconds <= args.skip_seconds or args.skip_seconds < 0
        or args.seed < 0 or not args.checkpoint.is_file()):
    parser.error("invalid stance duration, environment count, seed, or checkpoint")
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import isaaclab_tasks  # noqa: E402,F401
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import foothold_s2.sb_tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, ex41_eval_loader, map_mode_cells, run_identity  # noqa: E402
from foothold_s2.robots.go2_kinematics import FOOT_RADIUS_M  # noqa: E402

_KIT_PRELOAD = (h5py, tensordict, rsl_rl.runners, isaaclab_tasks,
                foothold_s2.sb_tasks)


FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")


def _cpu(tensor):
    return tensor.detach().cpu().numpy().copy()


def _foot_indices(robot, sensor):
    body, sensing = list(robot.body_names), list(sensor.body_names)
    if len(set(body)) != len(body) or len(set(sensing)) != len(sensing):
        raise RuntimeError("duplicate physical foot names")
    if any(name not in body or name not in sensing for name in FEET):
        raise RuntimeError("four canonical Go2 feet are not all present")
    return [body.index(name) for name in FEET], [sensing.index(name) for name in FEET]


def _configure():
    env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
    agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
    env_cfg.scene.num_envs = args.envs
    env_cfg.seed = args.seed
    env_cfg.scene.env_spacing = 8.0
    env_cfg.scene.terrain.terrain_type = "plane"
    env_cfg.scene.terrain.terrain_generator = None
    env_cfg.scene.terrain.max_init_terrain_level = None
    env_cfg.sim.device = args.device
    agent_cfg.device = args.device
    env_cfg.observations.policy.enable_corruption = False
    from foothold_s2.sensors import start_obs
    start_obs.AUG.enabled = False
    for name in ("actuator_gains", "motor_strength", "physics_material", "add_base_mass",
                 "base_com", "push_robot", "base_external_force_torque"):
        if hasattr(env_cfg.events, name):
            setattr(env_cfg.events, name, None)
    for name in ("terrain_levels", "command_range"):
        if hasattr(env_cfg.curriculum, name):
            setattr(env_cfg.curriculum, name, None)
    if hasattr(env_cfg.actions.joint_pos, "max_delay_s"):
        env_cfg.actions.joint_pos.max_delay_s = 0.0
    env_cfg.events.reset_base.params["pose_range"] = {
        "x": (0.0, 0.0), "y": (0.0, 0.0), "yaw": (0.0, 0.0)}
    env_cfg.events.reset_robot_joints.params["position_range"] = (1.0, 1.0)
    env_cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)
    env_cfg.commands.base_velocity.resampling_time_range = (1.0e9, 1.0e9)
    env_cfg.commands.base_velocity.flag_stride = 0
    env_cfg.commands.base_velocity.dynamic_flags = False
    return env_cfg, agent_cfg


def _summarize(force_z, gap, speed, yaw_speed, alive, mass_kg, skip, contact_n):
    per_env = []
    for env_id in range(force_z.shape[1]):
        mask = alive[skip:, env_id]
        row = {"env": env_id, "alive_at_end": bool(alive[-1, env_id]),
               "valid_samples_after_1s": int(mask.sum()), "feet": {}}
        if not mask.any():
            per_env.append(row)
            continue
        row["body_speed_mean_mps"] = float(speed[skip:, env_id][mask].mean())
        row["abs_yaw_speed_mean_radps"] = float(np.abs(yaw_speed[skip:, env_id][mask]).mean())
        for foot, name in enumerate(FEET):
            f = force_z[skip:, env_id, foot][mask]
            h = gap[skip:, env_id, foot][mask]
            row["feet"][name] = {
                "contact_fraction_gt1n": float(np.mean(f > contact_n)),
                "mean_fz_over_mg": float(np.mean(np.maximum(f, 0.0) /
                                                 (mass_kg[skip:, env_id][mask] * 9.81))),
                "sole_gap_p95_m": float(np.percentile(h, 95))}
        per_env.append(row)
    return per_env


def main():
    env = None
    try:
        env_cfg, agent_cfg = _configure()
        checkpoint_state, checkpoint_preparation = ex41_eval_loader.load_checkpoint_for_eval(
            env_cfg, args.checkpoint)
        env = RslRlVecEnvWrapper(gym.make(args.task, cfg=env_cfg), clip_actions=agent_cfg.clip_actions)
        raw = env.unwrapped
        robot, sensor = raw.scene["robot"], raw.scene["contact_forces"]
        body_ids, sensor_ids = _foot_indices(robot, sensor)
        term = raw.command_manager.get_term("base_velocity")
        dt = float(raw.step_dt)
        steps, skip = round(args.seconds / dt), round(args.skip_seconds / dt)
        if steps < 2 or not 0 < skip < steps or abs(steps * dt - args.seconds) > dt / 2:
            raise RuntimeError("stance duration does not align with policy steps")
        torch.manual_seed(args.seed)
        obs, _ = env.reset()
        if checkpoint_preparation["checkpoint_pose_commands"]:
            ex41_eval_loader.verify_ex41_pose_observation(obs)
        map_mode_cells.disable_heading_for_fixed_eval(term)
        term.vel_command_b[:, :3] = 0.0
        runner, _ = adapters.load_s2_runner(
            env, agent_cfg.to_dict(), args.checkpoint, args.device,
            checkpoint_state=checkpoint_state)
        policy = adapters.S2Policy(runner, args.envs, z_mode="mean", act_mode="mean", map_mode=args.mode)
        if args.mode == "eval_gt" and not bool(policy.pstate.use_gt.all()):
            raise RuntimeError("stance GT map was not selected")
        if args.mode != "eval_gt" and bool(policy.pstate.use_gt.any()):
            raise RuntimeError("stance GT map leaked into non-GT mode")
        from foothold_s2.eval import map_error as map_error_metrics

        map_error_last = {"e": None, "rebuild_maxdiff": 0.0}
        original_advance = runner.perception._advance

        def tapped_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map,
                           *map_off, _original=original_advance):
            result = _original(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map,
                               *map_off)
            try:
                rel = (raw.scene.sensors["gt_map_scan"].data.ray_hits_w[..., 2]
                       - robot.data.root_pos_w[:, 2:3])
            except Exception as exc:  # noqa: BLE001
                rel = None
                map_error_last["rel_error"] = repr(exc)
            map_error_metrics.record(map_error_last, result, gt_map, rel)
            return result

        runner.perception._advance = tapped_advance
        alive = np.ones(args.envs, dtype=bool)
        rows = {key: [] for key in ("force_z", "gap", "speed", "yaw_speed", "alive", "mass_kg")}
        map_error_rows = {name: [] for name in map_error_metrics.SERIES}
        origins = _cpu(raw.scene.env_origins[:, 2])
        if not np.allclose(origins, 0.0, atol=1e-6):
            raise RuntimeError("flat stance terrain is not z=0")
        for _ in range(steps):
            term.vel_command_b[:, :3] = 0.0
            map_mode_cells.assert_heading_off_for_fixed_eval(term)
            map_error_last["e"] = None
            action = policy(obs)
            errors = map_error_last["e"]
            for index, name in enumerate(map_error_metrics.SERIES):
                if errors is None:
                    map_error_rows[name].append(np.full(args.envs, np.nan, dtype=np.float32))
                else:
                    map_error_rows[name].append(_cpu(errors[index]).astype(np.float32, copy=False))
            obs, _, done, _ = env.step(action)
            alive &= ~_cpu(done.bool())
            data = robot.data
            rows["force_z"].append(_cpu(sensor.data.net_forces_w[:, sensor_ids, 2]))
            rows["gap"].append(_cpu(data.body_pos_w[:, body_ids, 2]) - FOOT_RADIUS_M)
            rows["speed"].append(_cpu(data.root_lin_vel_b.norm(dim=-1)))
            rows["yaw_speed"].append(_cpu(data.root_ang_vel_b[:, 2]))
            rows["alive"].append(alive.copy())
            rows["mass_kg"].append(_cpu(robot.root_physx_view.get_masses()).sum(axis=1))
            policy.reset(done)
        arrays = {key: np.stack(value) for key, value in rows.items()}
        map_error_series = {name: np.stack(value) for name, value in map_error_rows.items()}
        valid = arrays["alive"][skip:]
        for key in ("force_z", "gap", "speed", "yaw_speed", "mass_kg"):
            values = arrays[key][skip:]
            masked = np.broadcast_to(valid[(...,) + (None,) * (values.ndim - 2)], values.shape)
            if not np.isfinite(values[masked]).all():
                raise RuntimeError(f"stance {key} contains nonfinite valid samples")
        per_env = _summarize(**arrays, skip=skip, contact_n=args.contact_n)
        map_error_aggregate = map_error_metrics.env_aggregate(map_error_series, arrays["alive"])
        map_error_summary = map_error_metrics.record_only_summary(
            map_error_aggregate["map_err_all_mean_cm"],
            map_error_aggregate["map_err_all_cellmax_cm"],
            source="stand_raw.npz:map_err_all_*_cm",
        )
        args.out.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.out / "stand_raw.npz", **arrays,
                            **{"map_err_series_" + name: values
                               for name, values in map_error_series.items()},
                            **{name: value for name, value in map_error_aggregate.items()})
        checkpoint_sha = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        result = {"format": "foothold-ex40-stand/1", "checkpoint": str(args.checkpoint),
                  "checkpoint_sha256": checkpoint_sha,
                  "run_identity": run_identity.safe_collect(args.device, checkpoint_sha, eval_seed=args.seed),
                  "ex41_checkpoint_preparation": checkpoint_preparation,
                  "mode": args.mode, "envs": args.envs, "seconds": args.seconds,
                  "skip_seconds": args.skip_seconds, "dt": dt, "feet": FEET,
                  "contact_force_n": args.contact_n,
                  "conditions": {"ground": "plane z=0", "command": [0, 0, 0],
                                 "dr": "startup randomization disabled", "delay_s": 0,
                                 "policy_noise": "off", "seed": args.seed,
                                 "gap_definition": "foot center z minus collision radius, not ray hit"},
                  "per_env": per_env,
                  "restoration_error_record_only": map_error_summary,
                  "map_error_rebuild_maxdiff_m": map_error_last.get("rebuild_maxdiff"),
                  "map_error_rel_error": map_error_last.get("rel_error"),
                  "raw_sha256": hashlib.sha256((args.out / "stand_raw.npz").read_bytes()).hexdigest()}
        (args.out / "stand.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print("EX40_STAND_DONE", args.mode, args.envs, flush=True)
    finally:
        if env is not None:
            env.close()
        app.close()


if __name__ == "__main__":
    main()
