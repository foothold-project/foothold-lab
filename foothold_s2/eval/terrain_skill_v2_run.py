"""EX-41 W78 v2 terrain skill measurement. Imported after Kit initialization."""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

from foothold_s2.eval import axis_v2_cells as cells
from foothold_s2.eval import map_mode_cells
from foothold_s2.eval.ex41_map_modes import REQUIRED_MODES, require_all_modes
from foothold_s2.eval.terrain_skill_run import CASES, HEADING_CASES, case_steps
from foothold_s2.eval.axis_v2_run import _atomic_json, foot_ids, yaw_from_quat
from foothold_s2.runners.manifest import sha256_file

LEVELS = (2, 5)
ANGLES_DEG = (0, 30, 60, 90)
STOP_BACK_CASE = "stairs_fwd_stop_back"
EX41_TABLE = Path(__file__).resolve().parents[1] / "curriculum" / "ex41-fixed5000.yaml"
V2_CASES = {**CASES, STOP_BACK_CASE: (
    [((0.5, 0.0, 0.0), 3.0), ((0.0, 0.0, 0.0), 2.0),
     ((-0.5, 0.0, 0.0), 3.0), ((0.0, 0.0, 0.0), 2.0)],
    ("pyramid_stairs", "pyramid_stairs_inv"))}


def _write_result_json(path, record, *, attempts=8, retry_delay_s=0.25):
    """Retry transient Windows sharing violations while publishing W78 receipts."""
    for attempt in range(attempts):
        try:
            _atomic_json(path, record)
            return
        except PermissionError:
            if attempt + 1 == attempts:
                raise
            time.sleep(retry_delay_s * (attempt + 1))


def prepare_ex41_environment(env_cfg, *, table=EX41_TABLE):
    """Apply the fixed EX-41 observation/config contract before gym.make."""
    from foothold_s2.scripts.ex41_startup import load_fixed_plan, prepare_ex41_env_cfg

    plan = load_fixed_plan(table)
    receipt = prepare_ex41_env_cfg(env_cfg, plan)
    return plan, receipt


def attach_ex41_w86_runtime(env, plan, out_dir: str | Path):
    """Attach the EX-41 diagnostic runtime to a W78 evaluation environment."""
    from foothold_s2.rewards.w86_runtime import attach_runtime

    raw = getattr(env, "unwrapped", env)
    runtime = attach_runtime(raw, plan, Path(out_dir) / "ex41_w86")
    if getattr(raw, "_ex41_w86", None) is not runtime:
        raise RuntimeError("W78 v2 EX-41 W86 runtime attachment did not stick")
    return {"attached": True, "runtime": type(runtime).__name__,
            "log_dir": str(runtime.log_dir)}


def attach_ex41_eval_runtime(env, plan, out_dir: str | Path):
    """Install the EX-40 stand evidence and EX-41 W86 consumers before evaluation steps."""
    from foothold_s2.scripts.ex41_startup import attach_ex41_stand_runtime_data

    stand = attach_ex41_stand_runtime_data(env)
    w86 = attach_ex41_w86_runtime(env, plan, out_dir)
    return {"stand": stand, "w86": w86}


def _int_set(value, *, label: str, required: tuple[int, ...]) -> tuple[int, ...]:
    try:
        numbers = tuple(int(part) for part in value.split(","))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"W78 v2 {label} must be {required}") from exc
    if len(numbers) != len(required) or set(numbers) != set(required):
        raise ValueError(f"W78 v2 {label} must be {required}; got {numbers}")
    return required


def validate_request(args) -> None:
    """Reject incomplete combinations and reused output before opening Kit."""
    if args.axis_v2 or args.terrain_skill or not args.fixed_terrain or args.fixed_level is not None:
        raise ValueError("W78 v2 needs --fixed-terrain without --fixed-level, --axis-v2 or --terrain-skill")
    if args.terrain_set != "default":
        raise ValueError("W78 v2 needs the default continuous terrain set")
    if args.envs < 1 or args.eval_seed < 0:
        raise ValueError("W78 v2 needs positive envs and nonnegative eval seed")
    _int_set(args.terrain_levels, label="levels", required=LEVELS)
    _int_set(args.stair_start_angles_deg, label="angles", required=ANGLES_DEG)
    require_all_modes(args.modes, where="W78 v2")
    checkpoint = Path(args.checkpoint)
    if not checkpoint.is_file():
        raise ValueError(f"W78 v2 checkpoint absent: {checkpoint}")
    output = Path(args.out)
    if output.exists():
        if not output.is_dir():
            raise ValueError("W78 v2 needs a fresh empty output directory")
        existing = list(output.iterdir())
        attachment = getattr(args, "ex41_w86_attachment", None)
        if existing and (not isinstance(attachment, dict) or attachment.get("attached") is not True
                         or len(existing) != 1 or existing[0].name != "ex41_w86"
                         or not existing[0].is_dir()):
            raise ValueError("W78 v2 needs a fresh empty output directory or an isolated W86 attach receipt")
        if existing:
            runtime_files = list(existing[0].iterdir())
            if (len(runtime_files) != 1 or runtime_files[0].name != "ex41_stair_start.jsonl"
                    or not runtime_files[0].is_file()):
                raise ValueError("W78 v2 output contains stale or unexpected W86 files")


def yaw_quaternion(degrees: int, *, device, dtype) -> torch.Tensor:
    angle = math.radians(degrees) / 2.0
    return torch.tensor((math.cos(angle), 0.0, 0.0, math.sin(angle)), device=device, dtype=dtype)


def set_start_yaw(robot, degrees: int) -> float:
    """Change body world yaw, keep its reset position, and clear reset velocity."""
    state = robot.data.root_state_w.clone()
    state[:, 3:7] = yaw_quaternion(degrees, device=state.device, dtype=state.dtype)
    state[:, 7:] = 0
    robot.write_root_pose_to_sim(state[:, :7])
    robot.write_root_velocity_to_sim(state[:, 7:])
    actual = yaw_from_quat(robot.data.root_quat_w)
    error = torch.atan2(torch.sin(actual - math.radians(degrees)),
                        torch.cos(actual - math.radians(degrees))).abs().max().item()
    if error > 1.0e-3:
        raise RuntimeError(f"W78 v2 start yaw write/read differs by {error:.6f} rad")
    return error


def _foot_body_ids(robot) -> list[int]:
    names = list(robot.body_names)
    if len(set(names)) != len(names) or any(names.count(name) != 1 for name in cells.FOOT_NAMES):
        raise RuntimeError(f"W78 v2 robot foot order missing or duplicated: {names}")
    return [names.index(name) for name in cells.FOOT_NAMES]


def collect_case(env, raw, robot, term, policy, sensor, sensor_feet, body_feet,
                 phases, steps, *, heading: bool, verify_pose_cmd: bool = False) -> dict[str, np.ndarray]:
    """Capture each scheduled step; valid excludes post-reset values after a done."""
    n, total = env.num_envs, sum(steps)
    device = raw.device
    alive = torch.ones(n, dtype=torch.bool, device=device)
    root_start = robot.data.root_pos_w.clone()
    yaw_start = yaw_from_quat(robot.data.root_quat_w).clone()
    phases_out = torch.empty(total, dtype=torch.int16, device=device)
    cmd = torch.zeros(total, n, 3, device=device)
    root = torch.zeros(total, n, 3, device=device)
    quat = torch.zeros(total, n, 4, device=device)
    body_vel = torch.zeros(total, n, 3, device=device)
    body_wz = torch.zeros(total, n, device=device)
    foot_pos = torch.zeros(total, n, 4, 3, device=device)
    foot_vel_xy = torch.zeros(total, n, 4, 2, device=device)
    contact = torch.zeros(total, n, 4, dtype=torch.bool, device=device)
    contact_force = torch.zeros(total, n, 4, device=device)
    valid = torch.zeros(total, n, dtype=torch.bool, device=device)
    done_out = torch.zeros_like(valid)
    term_names = tuple(raw.termination_manager.active_terms)
    term_bits = torch.zeros(total, n, len(term_names), dtype=torch.bool, device=device)
    obs = env.get_observations()
    if verify_pose_cmd:
        from foothold_s2.eval.ex41_eval_loader import verify_ex41_pose_observation
        verify_ex41_pose_observation(obs)
    tick = 0
    for phase_id, ((command, _seconds), count) in enumerate(zip(phases, steps, strict=True)):
        for _ in range(count):
            if heading:
                term.vel_command_b[:, :2] = torch.as_tensor(command[:2], device=device)
                if tick == 0:
                    term.vel_command_b[:, 2] = 0.0
                term.heading.fill_(True)
                term.psi_star.copy_(yaw_start)
            else:
                term.vel_command_b[:, :3] = torch.as_tensor(command, device=device)
                term.heading.fill_(False)
                term.psi_star.zero_()
            term.stand.fill_(not any(command))
            action = policy(obs)
            obs, _reward, dones, _extras = env.step(action)
            if verify_pose_cmd:
                from foothold_s2.eval.ex41_eval_loader import verify_ex41_pose_observation
                verify_ex41_pose_observation(obs)
            policy.reset(dones)
            valid[tick] = alive & ~dones.bool()
            done_out[tick] = alive & dones.bool()
            for j, name in enumerate(term_names):
                term_bits[tick, :, j] = raw.termination_manager.get_term(name) & alive
            alive &= ~dones.bool()
            data = robot.data
            phases_out[tick] = phase_id
            cmd[tick] = term.vel_command_b[:, :3]
            root[tick] = data.root_pos_w
            quat[tick] = data.root_quat_w
            body_vel[tick] = data.root_lin_vel_b
            body_wz[tick] = data.root_ang_vel_b[:, 2]
            foot_pos[tick] = data.body_pos_w[:, body_feet]
            foot_vel_xy[tick] = data.body_lin_vel_w[:, body_feet, :2]
            force = torch.linalg.vector_norm(sensor.data.net_forces_w[:, sensor_feet], dim=-1)
            contact_force[tick] = force
            contact[tick] = force > cells.CONTACT_N
            tick += 1
    arrays = {"phase_id": phases_out, "cmd_post": cmd, "root_pos_w": root,
              "root_quat_w": quat, "body_vel_b": body_vel, "body_wz": body_wz,
              "foot_pos_w": foot_pos, "foot_vel_xy_w": foot_vel_xy,
              "contact": contact, "contact_force_n": contact_force,
              "alive": valid, "dones": done_out, "termination_bits": term_bits,
              "root_start_w": root_start, "yaw_start_rad": yaw_start}
    result = {key: value.detach().cpu().numpy() for key, value in arrays.items()}
    result["termination_names"] = np.asarray(term_names, dtype="U64")
    return result


def movement_ratio_for_env(data: dict, phases, steps, env_id: int, dt: float) -> list[dict]:
    start, output = 0, []
    for (command, _seconds), count in zip(phases, steps, strict=True):
        vx, vy = command[:2]
        speed = math.hypot(vx, vy)
        sample = slice(start, start + count)
        live = data["alive"][sample, env_id]
        projection = ((data["body_vel_b"][sample, env_id, 0] * vx
                       + data["body_vel_b"][sample, env_id, 1] * vy) / speed
                      if speed else np.zeros(count))
        distance = float(np.sum(projection[live]) * dt) if speed else None
        planned = float(speed * count * dt) if speed else None
        output.append({"movement_ratio": distance / planned if planned else None,
                       "distance_projected_m": distance, "planned_distance_m": planned,
                       "alive_samples": int(live.sum()), "scheduled_samples": count})
        start += count
    return output


def swing_and_drag(data: dict, env_id: int) -> dict:
    live_count = int(data["alive"][:, env_id].sum())
    contact = data["contact"][:live_count, env_id]
    z = data["foot_pos_w"][:live_count, env_id, :, 2]
    speed = np.linalg.norm(data["foot_vel_xy_w"][:live_count, env_id], axis=-1)
    drag_den = int(contact.sum())
    drag_num = int((contact & (speed > 0.15)).sum())
    heights, open_swings = [], 0
    for foot in range(4):
        k = 0
        while k < live_count:
            if contact[k, foot]:
                k += 1
                continue
            end = k
            while end < live_count and not contact[end, foot]:
                end += 1
            if k > 0 and end < live_count:
                ground = (float(z[k - 1, foot]) + float(z[end, foot])) / 2.0
                heights.append(float(np.max(z[k:end, foot]) - ground))
            else:
                open_swings += 1
            k = end
    return {"drag_num": drag_num, "drag_den": drag_den,
            "drag_ratio_of_contact": drag_num / drag_den if drag_den else None,
            "swing_clearance_m": heights, "closed_swing_count": len(heights),
            "open_swing_count": open_swings}


def stop_back_metrics(data: dict, steps: list[int], env_id: int) -> dict:
    """D128 stop drift and post-stop backward lateral displacement."""
    if len(steps) != 4:
        raise ValueError("D128 case needs four phases")
    a, b, c, d = np.cumsum(steps)
    live = data["alive"][:, env_id]
    yaw = np.arctan2(2 * (data["root_quat_w"][:, env_id, 0] * data["root_quat_w"][:, env_id, 3]
                           + data["root_quat_w"][:, env_id, 1] * data["root_quat_w"][:, env_id, 2]),
                     1 - 2 * (data["root_quat_w"][:, env_id, 2] ** 2
                              + data["root_quat_w"][:, env_id, 3] ** 2))
    if not live[a - 1] or not live[b - 1]:
        return {"stop_yaw_drift_rad": None, "stop_abs_wz_integral_rad": None,
                "post_stop_back_lateral_m": None}
    drift = float(np.angle(np.exp(1j * (yaw[b - 1] - yaw[a - 1]))))
    dt = float(data["dt"])
    integral = float(np.sum(np.abs(data["body_wz"][a:b, env_id][live[a:b]])) * dt)
    reverse_live = np.flatnonzero(live[b:c])
    if len(reverse_live):
        end = b + int(reverse_live[-1])
        delta_xy = data["root_pos_w"][end, env_id, :2] - data["root_pos_w"][b - 1, env_id, :2]
        lateral = float(-math.sin(yaw[b - 1]) * delta_xy[0] + math.cos(yaw[b - 1]) * delta_xy[1])
    else:
        lateral = None
    return {"stop_yaw_drift_rad": drift, "stop_abs_wz_integral_rad": integral,
            "post_stop_back_lateral_m": lateral, "final_stop_alive": bool(live[d - 1])}


def summarize_case(data: dict, tiles: list[dict], phases, steps, dt: float,
                   *, d128: bool) -> dict:
    rows = []
    for env_id, tile in enumerate(tiles):
        movements = movement_ratio_for_env(data, phases, steps, env_id, dt)
        feet = swing_and_drag(data, env_id)
        row = {"env": env_id, "kind": tile["kind"], "level": tile["level"],
               "alive_at_end": bool(data["alive"][-1, env_id]),
               "alive_samples": int(data["alive"][:, env_id].sum()),
               "movement_phases": movements, **feet}
        if d128:
            row.update(stop_back_metrics(data, steps, env_id))
        rows.append(row)
    by_kind = {}
    for kind in sorted({tile["kind"] for tile in tiles}):
        selected = [row for row in rows if row["kind"] == kind]
        phase_ratios = [[row["movement_phases"][phase]["movement_ratio"] for row in selected
                         if row["movement_phases"][phase]["movement_ratio"] is not None]
                        for phase in range(len(steps))]
        drag_num = sum(row["drag_num"] for row in selected)
        drag_den = sum(row["drag_den"] for row in selected)
        clearances = [height for row in selected for height in row["swing_clearance_m"]]
        by_kind[kind] = {"env_count": len(selected), "alive_at_end": sum(row["alive_at_end"] for row in selected),
                         "movement_ratio_median": float(np.median(phase_ratios[0])) if phase_ratios[0] else None,
                         "phase_movement_ratio_median": [float(np.median(values)) if values else None
                                                         for values in phase_ratios],
                         "phase_movement_valid_envs": [len(values) for values in phase_ratios],
                         "drag_num": drag_num, "drag_den": drag_den,
                         "drag_ratio_of_contact": drag_num / drag_den if drag_den else None,
                         "swing_clearance_p50_m": float(np.median(clearances)) if clearances else None,
                         "closed_swing_count": len(clearances),
                         "open_swing_count": sum(row["open_swing_count"] for row in selected)}
    return {"per_env": rows, "by_terrain_kind": by_kind}


def _sha_for_optional(path: Path) -> str | None:
    return sha256_file(str(path)) if path.is_file() else None


def expected_combinations() -> set[tuple[int, int, str, str]]:
    return {(level, angle, mode, name) for level in LEVELS for angle in ANGLES_DEG
            for mode in REQUIRED_MODES for name in V2_CASES}


def require_complete(completed: set[tuple[int, int, str, str]]) -> None:
    expected = expected_combinations()
    if completed != expected:
        missing = expected - completed
        extra = completed - expected
        raise RuntimeError(f"W78 v2 incomplete combinations: {len(completed)}/{len(expected)}; "
                           f"missing={len(missing)} extra={len(extra)}")


def run_suite(args, env, raw, robot, term, agent_cfg, adapters, fixed_terrain,
              terrain_names, dr_off, curriculum_off, run_identity):
    validate_request(args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    final = out / "terrain_skill_v2.json"
    partial = out / "terrain_skill_v2.partial.json"
    error_path = out / "terrain_skill_v2.error.json"
    sensor, sensor_feet = foot_ids(raw)
    body_feet = _foot_body_ids(robot)
    if bool(term.is_flag_env.any()):
        raise RuntimeError("W78 v2 needs no flag environments")
    n, dt = env.num_envs, float(raw.step_dt)
    if not math.isfinite(dt) or dt <= 0 or n != args.envs:
        raise ValueError("W78 v2 env count or control dt differs from request")
    source_paths = (Path(__file__), Path(sys.modules["__main__"].__file__),
                    Path(adapters.__file__), Path(fixed_terrain.__file__))
    manifest = Path(args.checkpoint).parent / "manifest.json"
    result = {"schema": "foothold-terrain-skill-v2/1", "suite": "W78-v2", "state": "running",
              "checkpoint": str(Path(args.checkpoint).resolve()), "checkpoint_sha256": sha256_file(args.checkpoint),
              "checkpoint_manifest_sha256": _sha_for_optional(manifest),
              "source_sha256": {p.name: sha256_file(str(p)) for p in source_paths},
              "run_identity": run_identity, "envs": n, "dt_s": dt, "eval_seed": args.eval_seed,
              "levels": LEVELS, "start_angles_deg": ANGLES_DEG, "modes": {},
              "ex41_environment_preparation": getattr(args, "ex41_env_preparation", None),
              "ex41_checkpoint_preparation": getattr(args, "ex41_checkpoint_preparation", None),
              "ex41_runtime_attachment": getattr(args, "ex41_runtime_attachment", None),
              "dr_off": dr_off, "curriculum_off": curriculum_off,
              "cases": {name: {"phases": [[list(command), seconds] for command, seconds in phases],
                               "focus_kinds": list(kinds)} for name, (phases, kinds) in V2_CASES.items()},
              "measurement_note": "descriptive only; terminated samples excluded; no pass threshold"}
    expected_keys = expected_combinations()
    completed: set[tuple[int, int, str, str]] = set()
    assignment_sha: dict[tuple[int, int], str] = {}
    try:
        for level in LEVELS:
            for angle in ANGLES_DEG:
                for mode in REQUIRED_MODES:
                    runner, saved = adapters.load_s2_runner(
                        env, agent_cfg.to_dict(), args.checkpoint, args.device,
                        checkpoint_state=getattr(args, "ex41_checkpoint_state", None))
                    result.setdefault("checkpoint_iter", int(saved.get("iter", -1)))
                    if runner.pcfg.get("map_input") == "none":
                        raise RuntimeError("W78 v2 cannot use a map_input none checkpoint")
                    mode_rows = result["modes"].setdefault(mode, {})
                    for name, (phases, kinds) in V2_CASES.items():
                        key = (level, angle, mode, name)
                        torch.manual_seed(args.eval_seed)
                        env.reset()
                        fixed = fixed_terrain.apply(raw, level)
                        env.reset()
                        actual = raw.scene.terrain
                        tiles = map_mode_cells.terrain_rows(actual.terrain_levels.cpu().numpy(),
                                                            actual.terrain_types.cpu().numpy(), terrain_names)
                        if len(tiles) != n or any(tile["level"] != level for tile in tiles):
                            raise RuntimeError(f"W78 v2 actual assignment differs at {key}")
                        if not {tile["kind"] for tile in tiles} >= set(kinds):
                            raise RuntimeError(f"W78 v2 focus kinds missing at {key}")
                        pair = (level, angle)
                        sha = fixed["assignment_sha256"]
                        if pair in assignment_sha and assignment_sha[pair] != sha:
                            raise RuntimeError(f"W78 v2 tile SHA differs across modes at {key}")
                        assignment_sha[pair] = sha
                        yaw_error = set_start_yaw(robot, angle)
                        policy = adapters.S2Policy(runner, n, z_mode="mean", act_mode="mean", map_mode=mode)
                        policy.reset(torch.ones(n, dtype=torch.bool, device=raw.device))
                        map_mode_cells.disable_heading_for_fixed_eval(term)
                        steps = case_steps(phases, dt)
                        data = collect_case(
                            env, raw, robot, term, policy, sensor, sensor_feet,
                            body_feet, phases, steps, heading=name in HEADING_CASES,
                            verify_pose_cmd=bool(getattr(args, "ex41_checkpoint_preparation", {}).get(
                                "checkpoint_pose_commands", False)))
                        data["dt"] = np.asarray(dt)
                        data["phase_steps"] = np.asarray(steps)
                        data["t"] = np.arange(sum(steps), dtype=np.float64) * dt
                        filename = f"terrain_skill_v2_L{level}_a{angle:03d}_{mode}_{name}.npz"
                        np.savez_compressed(out / filename, **data)
                        summary = summarize_case(data, tiles, phases, steps, dt, d128=name == STOP_BACK_CASE)
                        mode_rows[f"L{level}_a{angle:03d}_{name}"] = {
                            "level": level, "stair_start_angle_deg": angle, "case": name,
                            "requested_kinds": kinds, "terrain_tiles": tiles,
                            "terrain_assignment_sha256": sha, "start_yaw_readback_error_rad": yaw_error,
                            "phase_steps": steps, "raw_file": filename,
                            "raw_sha256": sha256_file(str(out / filename)), **summary}
                        completed.add(key)
                        _write_result_json(partial, result)
                        print("TERRAIN_SKILL_V2_CASE", *key, flush=True)
        require_complete(completed)
        result["w78_min_lr_ratio"] = {}
        for level in LEVELS:
            for angle in ANGLES_DEG:
                for mode in REQUIRED_MODES:
                    rows = result["modes"][mode]
                    for kind in ("pyramid_stairs", "pyramid_stairs_inv"):
                        left = rows[f"L{level}_a{angle:03d}_stairs_side_left"]["by_terrain_kind"][kind]["movement_ratio_median"]
                        right = rows[f"L{level}_a{angle:03d}_stairs_side_right"]["by_terrain_kind"][kind]["movement_ratio_median"]
                        result["w78_min_lr_ratio"][f"L{level}_a{angle:03d}_{mode}_{kind}"] = {
                            "left": left, "right": right,
                            "min_lr_ratio": min(left, right) if left is not None and right is not None else None,
                            "definition": "minimum of signed left and right movement ratios; no threshold"}
        result["state"] = "done"
        _write_result_json(final, result)
        partial.unlink()
        print("TERRAIN_SKILL_V2_DONE", final, flush=True)
        return result
    except Exception as exc:
        _write_result_json(error_path, {"state": "HOLD", "reason": repr(exc),
                                        "completed": len(completed), "expected": len(expected_keys),
                                        "partial_path": str(partial)})
        raise
