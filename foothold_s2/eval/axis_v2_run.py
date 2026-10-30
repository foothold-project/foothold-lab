"""W57 axis v2 Kit loop. Imported by eval_map_modes after its existing app setup."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import torch

from foothold_s2.commands import mixed_core
from foothold_s2.eval import axis_v2_cells as cells
from foothold_s2.eval import map_mode_cells
from foothold_s2.runners.manifest import sha256_file


def yaw_from_quat(q):
    return torch.atan2(2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]),
                       1.0 - 2.0 * (q[:, 2].square() + q[:, 3].square()))


def target_from_reset(root_quat_w, spec):
    """Change only the target; keep the body's actual reset world yaw."""
    start = yaw_from_quat(root_quat_w).clone()
    delta = spec["goal_delta_deg"]
    target = mixed_core.wrap_to_pi(start + math.radians(delta)) if delta is not None else start.clone()
    return start, target


def foot_ids(raw):
    sensor = raw.scene.sensors["contact_forces"]
    names = list(sensor.body_names)
    if len(set(names)) != len(names) or any(names.count(name) != 1 for name in cells.FOOT_NAMES):
        raise RuntimeError(f"W57 foot names missing or duplicated: {names}")
    ids = [names.index(name) for name in cells.FOOT_NAMES]
    return sensor, ids


def _finite(value):
    value = float(value)
    return value if math.isfinite(value) else None


def _atomic_json(path: Path, record):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def directional_slope_kinds(tiles, require: bool):
    kinds = sorted({t["kind"] for t in tiles if "slope" in t["kind"]})
    if require and not kinds:
        raise RuntimeError("W57 formal terrain assignment lacks directional slope cells")
    return kinds


def execute_case_loop(env, raw, robot, term, policy, sensor, feet, spec, target, steps):
    """Execute the real per-step command boundary; also exercised with a CPU env."""
    n = env.num_envs
    goal_turn = spec["kind"] == "goal_turn_stop"
    stop_steps = steps // 2
    alive = torch.ones(n, dtype=torch.bool, device=raw.device)
    reached = torch.full((n,), -1, dtype=torch.int64, device=raw.device)
    yaw = torch.zeros(steps, n, device=raw.device)
    vx, vy, wz = torch.zeros_like(yaw), torch.zeros_like(yaw), torch.zeros_like(yaw)
    valid = torch.zeros(steps, n, dtype=torch.bool, device=raw.device)
    contact = torch.zeros(steps, n, 4, dtype=torch.bool, device=raw.device)
    done_rows = torch.zeros_like(valid)
    cmd_pre = torch.zeros(steps, n, 3, device=raw.device)
    cmd_post = torch.zeros_like(cmd_pre)
    heading_pre = torch.zeros_like(valid)
    stand_pre = torch.zeros_like(valid)
    obs = None
    for step in range(steps):
        if goal_turn:
            error = mixed_core.wrap_to_pi(target - yaw_from_quat(robot.data.root_quat_w)).abs()
            arrived = alive & (reached < 0) & (error <= cells.GOAL_TOLERANCE_RAD)
            reached[arrived] = step
            turning = alive & (reached < 0)
            stopping = alive & (reached >= 0)
            measured = turning | (stopping & (step - reached < stop_steps))
            term.vel_command_b[:, :3] = 0.0
            term.vel_command_b[turning, 2] = torch.sign(mixed_core.wrap_to_pi(
                target[turning] - yaw_from_quat(robot.data.root_quat_w)[turning])) * cells.TURN_WZ_RADPS
            term.stand.copy_(stopping)
        else:
            measured = alive.clone()
            term.vel_command_b[:, :3] = torch.tensor(spec["command"], device=raw.device)
            term.stand.fill_(False)
        term.heading.fill_(False)
        term.psi_star.zero_()
        cmd_pre[step] = term.vel_command_b[:, :3]
        heading_pre[step] = term.heading
        stand_pre[step] = term.stand
        if goal_turn or step == 0:
            obs = env.get_observations()
        action = policy(obs)
        obs, _reward, done, _extras = env.step(action)
        cmd_post[step] = term.vel_command_b[:, :3]
        policy.reset(done)
        done_rows[step] = done.bool()
        valid[step] = measured & alive & ~done.bool()
        alive &= ~done.bool()
        data = robot.data
        yaw[step] = yaw_from_quat(data.root_quat_w)
        vx[step] = data.root_lin_vel_b[:, 0]
        vy[step] = data.root_lin_vel_b[:, 1]
        wz[step] = data.root_ang_vel_b[:, 2]
        contact[step] = torch.linalg.vector_norm(sensor.data.net_forces_w[:, feet], dim=-1) > cells.CONTACT_N
    return {"yaw": yaw, "vx": vx, "vy": vy, "wz": wz, "valid": valid,
            "contact": contact, "done": done_rows, "cmd_pre": cmd_pre, "cmd_post": cmd_post,
            "heading_pre": heading_pre, "stand_pre": stand_pre, "reached_step": reached,
            "stop_steps": stop_steps}


def run_suite(args, env, raw, robot, term, agent_cfg, adapters, fixed_terrain,
              terrain_names, dr_off, curriculum_off, run_identity):
    """Run independent starts on one fixed terrain assignment, preserving raw receipts."""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / "axis_v2.json"
    partial = out_dir / "axis_v2.partial.json"
    if final.exists() or partial.exists() or (out_dir / "map_modes.json").exists():
        raise RuntimeError("W57 requires a fresh output directory, separate from W15")
    n, steps, dt = env.num_envs, args.steps, float(raw.step_dt)
    if steps < 4 or n < 1 or not math.isfinite(dt) or dt <= 0:
        raise ValueError("W57 needs at least four control steps and one environment")
    if not args.fixed_terrain or args.fixed_level is None:
        raise ValueError("W57 requires a fixed terrain level")
    sensor, feet = foot_ids(raw)
    if bool(term.is_flag_env.any()):
        raise RuntimeError("W57 fixed command suite requires no flag environments")
    source_paths = (Path(__file__), Path(cells.__file__), Path(sys.modules["__main__"].__file__),
                    Path(adapters.__file__), Path(fixed_terrain.__file__))
    source = {p.name: sha256_file(str(p)) for p in source_paths}
    result = {"schema": "foothold-axis-v2/1", "suite": "W57-v2", "not_w15": True,
              "checkpoint": args.checkpoint, "checkpoint_sha256": sha256_file(args.checkpoint),
              "source_sha256": source, "run_identity": run_identity, "envs": n, "steps": steps,
              "dt_s": dt, "eval_seed": args.eval_seed, "terrain_set": args.terrain_set,
              "fixed_level": args.fixed_level, "dr_off": dr_off, "curriculum_off": curriculum_off,
              "foot_order": cells.FOOT_NAMES, "foot_contact_threshold_n": cells.CONTACT_N,
              "cases": cells.case_specs(), "modes": {}, "terrain_tiles": None,
              "measurement_note": "alive samples exclude post-reset state; goal offsets use reset body yaw; complete stop windows only; no pass threshold"}

    for mode in args.modes.split(","):
        if mode not in ("eval_gt", "eval_pred", "probe_prop_only", "none"):
            raise ValueError(f"unknown W57 map mode {mode!r}")
        runner, sd = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device)
        saved_map_input = runner.pcfg.get("map_input")
        if (saved_map_input == "none") != (mode == "none"):
            raise RuntimeError(f"W57 map_input={saved_map_input!r} disagrees with mode={mode!r}")
        result.setdefault("checkpoint_iter", int(sd.get("iter", -1)))
        result.setdefault("saved_map_input", saved_map_input)
        result["modes"][mode] = {}
        counts = {"gt": 0, "total": 0}
        original_advance = runner.perception._advance

        def tapped(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, _orig=original_advance):
            counts["gt"] += int(use_gt.sum())
            counts["total"] += int(use_gt.numel())
            return _orig(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)

        runner.perception._advance = tapped
        for spec in cells.case_specs():
            counts["gt"] = counts["total"] = 0
            torch.manual_seed(args.eval_seed)
            env.reset()
            terrain_record = (fixed_terrain.apply_sparse(raw, args.fixed_level) if args.terrain_set == "sparse50"
                              else fixed_terrain.apply(raw, args.fixed_level))
            env.reset()
            if bool(term.is_flag_env.any()):
                raise RuntimeError("W57 reset produced flag environments")
            start_offset = (robot.data.root_pos_w[:, :2] - raw.scene.env_origins[:, :2]).abs().max().item()
            if start_offset > 0.501:
                raise RuntimeError(f"W57 reset root is outside its fixed terrain origin: {start_offset:.3f} m")
            terrain = raw.scene.terrain
            tiles = map_mode_cells.terrain_rows(terrain.terrain_levels.cpu().numpy(),
                                                terrain.terrain_types.cpu().numpy(), terrain_names)
            if len(tiles) != n:
                raise RuntimeError("W57 terrain tile count differs from env count")
            directional = directional_slope_kinds(
                tiles, args.terrain_set == "default" and n >= len(terrain_names))
            if result["terrain_tiles"] is None:
                result["terrain_tiles"] = tiles
                result["fixed_terrain"] = terrain_record
                result["directional_slope_kinds"] = directional
            elif tiles != result["terrain_tiles"]:
                raise RuntimeError("W57 terrain assignment changed between cases")
            start_yaw, target = target_from_reset(robot.data.root_quat_w, spec)
            start_xy = robot.data.root_pos_w[:, :2].clone()
            policy = adapters.S2Policy(runner, n, z_mode="mean", act_mode="mean",
                                       map_mode="eval_pred" if mode == "none" else mode)
            policy.reset(torch.ones(n, dtype=torch.bool, device=raw.device))
            map_mode_cells.disable_heading_for_fixed_eval(term)
            samples = execute_case_loop(env, raw, robot, term, policy, sensor, feet, spec, target, steps)
            if counts["total"] != n * steps:
                raise RuntimeError(f"W57 policy perception step count invalid: {counts}")
            if (mode == "eval_gt" and counts["gt"] != counts["total"]) or (mode != "eval_gt" and counts["gt"] != 0):
                raise RuntimeError(f"W57 {mode} map source count invalid: {counts}")

            y, x, side, turn, al, feet_on = (samples[k].cpu().numpy() for k in
                                            ("yaw", "vx", "vy", "wz", "valid", "contact"))
            starts, targets = start_yaw.cpu().numpy(), target.cpu().numpy()
            reached = samples["reached_step"].cpu().numpy()
            yaw_stats = cells.yaw_accumulation(starts, y, al)
            symmetry = cells.contact_symmetry(feet_on, al)
            goal_stats = (cells.goal_stop_dynamic(starts, targets, y, al, reached,
                                                  samples["stop_steps"], dt, vx=x, vy=side, wz=turn)
                          if spec["kind"] == "goal_turn_stop" else None)
            alive_window_end = cells.alive_at_window_end(
                al, goal_stats["stop_complete"] if goal_stats else None)
            rows = []
            for i, tile in enumerate(tiles):
                row = {**tile, "alive_end": bool(alive_window_end[i]), "alive_steps": int(al[:, i].sum()),
                       "start_yaw_rad": float(starts[i]),
                       "yaw_final_minus_start_rad": _finite(yaw_stats["final_minus_start_wrapped_rad"][i]),
                       "yaw_signed_accum_rad": _finite(yaw_stats["signed_rad"][i]),
                       "yaw_absolute_accum_rad": _finite(yaw_stats["absolute_rad"][i]),
                       "contact_fraction_by_foot": [_finite(v) for v in symmetry["fraction_by_foot"][i]],
                       "contact_left_right_gap": _finite(symmetry["left_right_gap"][i]),
                       "contact_diagonal_gap": _finite(symmetry["diagonal_gap"][i])}
                if goal_stats is not None:
                    row.update({key: _finite(goal_stats[key][i]) for key in
                                ("stop_end_error_rad", "stop_yaw_drift_rad", "stop_alive_duration_s",
                                 "stop_stationary_duration_s")})
                    row["goal_reached_step"] = int(reached[i]) if reached[i] >= 0 else None
                    row["stop_complete"] = bool(goal_stats["stop_complete"][i])
                    row["fall_before_goal"] = bool(not al[-1, i] and reached[i] < 0)
                rows.append(row)
            by_kind = {}
            for kind in sorted({t["kind"] for t in tiles}):
                selected = [r for r in rows if r["kind"] == kind]
                by_kind[kind] = {"env_count": len(selected),
                                 "alive_at_end": sum(r["alive_end"] for r in selected),
                                 "yaw_signed_accum_median_rad": cells.finite_median(
                                     [r["yaw_signed_accum_rad"] for r in selected]),
                                 "yaw_absolute_accum_median_rad": cells.finite_median(
                                     [r["yaw_absolute_accum_rad"] for r in selected])}
            filename = f"axis_v2_{mode}_{spec['name']}.npz"
            np.savez_compressed(out_dir / filename, yaw=y, vx=x, vy=side, wz=turn, alive=al,
                                contact=feet_on, done=samples["done"].cpu().numpy(),
                                cmd_pre=samples["cmd_pre"].cpu().numpy(),
                                cmd_post=samples["cmd_post"].cpu().numpy(),
                                heading_pre=samples["heading_pre"].cpu().numpy(),
                                stand_pre=samples["stand_pre"].cpu().numpy(),
                                reached_step=reached, stop_steps=samples["stop_steps"],
                                start_yaw=starts, target_yaw=targets, start_xy=start_xy.cpu().numpy(),
                                terrain_level=np.array([r["level"] for r in tiles]),
                                terrain_kind=np.array([r["kind"] for r in tiles]), dt=dt)
            result["modes"][mode][spec["name"]] = {
                "kind": spec["kind"], "goal_delta_deg": spec["goal_delta_deg"],
                "start_offset_max_m": start_offset,
                "command": list(spec["command"]), "stop_steps": samples["stop_steps"] if goal_stats is not None else None,
                "gt_used": counts["gt"], "policy_steps_x_envs": counts["total"],
                "alive_at_end": int(alive_window_end.sum()),
                "yaw_final_minus_start_median_rad": cells.finite_median(yaw_stats["final_minus_start_wrapped_rad"]),
                "stop_end_error_median_rad": cells.finite_median(goal_stats["stop_end_error_rad"]) if goal_stats else None,
                "goal_reached_envs": int((reached >= 0).sum()) if goal_stats else None,
                "stop_complete_envs": int(goal_stats["stop_complete"].sum()) if goal_stats else None,
                "stop_stationary_duration_median_s": cells.finite_median(goal_stats["stop_stationary_duration_s"]) if goal_stats else None,
                "contact_left_right_gap_median": cells.finite_median(symmetry["left_right_gap"]),
                "contact_diagonal_gap_median": cells.finite_median(symmetry["diagonal_gap"]),
                "by_terrain_kind": by_kind,
                "raw_file": filename, "raw_sha256": sha256_file(str(out_dir / filename)), "per_env": rows}
            _atomic_json(partial, result)
            print("AXIS_V2_CASE", mode, spec["name"], result["modes"][mode][spec["name"]]["alive_at_end"], flush=True)
        runner.perception.ie.mask_map_tokens = False
    _atomic_json(final, result)
    partial.unlink()
    print("AXIS_V2_DONE", final, flush=True)
    return result
