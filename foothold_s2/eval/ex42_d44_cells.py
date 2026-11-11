"""CPU contract and trace scorer for the EX-42 D44 landing evaluation.

The case list, time windows, and thresholds come from the pinned prep plan.
This module does not launch Isaac. An absent contract cannot produce a PASS.
"""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
import re

import numpy as np


TASKS = ("turn_left", "turn_right", "stop_restart")
MODES = ("eval_gt", "eval_pred", "probe_prop_only")
TRACE_FORMAT = "foothold-ex42-d44-trace/2"
RECEIPT_FORMAT = "foothold-ex42-d44-eval/2"


def top_latch_mask(root_xy, foot_x, alive, bounds):
    """Post-step entry into the landing with every foot past its front edge."""
    root_xy, foot_x, alive = np.asarray(root_xy), np.asarray(foot_x), np.asarray(alive)
    xmin, xmax, ymin, ymax = bounds
    if (root_xy.ndim != 2 or root_xy.shape[1] != 2 or foot_x.shape != (len(root_xy), 4)
            or alive.shape != (len(root_xy),) or alive.dtype != bool
            or not np.isfinite(root_xy).all() or not np.isfinite(foot_x).all()):
        raise ValueError("D44 top latch geometry shape or finite values differ")
    return (alive & (root_xy[:, 0] >= xmin) & (root_xy[:, 0] <= xmax)
            & (root_xy[:, 1] >= ymin) & (root_xy[:, 1] <= ymax)
            & (foot_x >= xmin).all(axis=1))


def restart_command(latched, speed):
    """Per-env phase 3 becomes phase 4 with a zero command after latching."""
    latched = np.asarray(latched)
    if (latched.ndim != 1 or latched.dtype != bool or type(speed) not in (int, float)
            or not math.isfinite(speed) or speed <= 0):
        raise ValueError("D44 restart command contract invalid")
    return np.where(latched, 4, 3).astype(np.int16), np.where(latched, 0.0, speed)


def contract(plan: dict) -> dict:
    landing = plan["evaluation"]["paper_cells"]["stairs_landing"]
    judges = landing.get("judge_cases")
    records = landing.get("record_cases")
    cases = landing.get("case_specs")
    timing = landing.get("timing")
    if (not isinstance(judges, list) or not judges or not isinstance(records, list)
            or not isinstance(cases, dict) or not isinstance(timing, dict)
            or any(not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_-]+", name) is None
                   for name in judges + records)
            or len(set(judges + records)) != len(judges + records)
            or set(cases) != set(judges + records)):
        raise ValueError("D44 prep case list or timing contract missing")
    for name, spec in cases.items():
        if (not isinstance(spec, dict) or spec.get("task") not in TASKS
                or spec.get("map_mode") not in MODES
                or name != f"{spec.get('task')}_{spec.get('map_mode')}"
                or spec.get("role") != ("judge" if name in judges else "record_only")):
            raise ValueError(f"D44 prep case {name} has invalid task, mode or role")
        if (name in judges) != (spec["map_mode"] in ("eval_gt", "eval_pred")):
            raise ValueError(f"D44 prep case {name} map mode and judgment role differ")
    for key in ("settle_s", "approach_limit_s", "stop_s", "restart_limit_s",
                "stop_hold_s", "top_hold_s", "stop_speed_mps", "foot_below_top_m",
                "foot_stop_z_tolerance_m"):
        value = timing.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"D44 prep timing {key} missing or invalid")
    if timing["stop_hold_s"] > timing["stop_s"]:
        raise ValueError("D44 stop hold exceeds stop window")
    valid_min = landing.get("valid_min")
    if type(valid_min) is not int or not 0 < valid_min <= 64:
        raise ValueError("D44 valid denominator floor missing or invalid")
    for key in ("turn_rate_radps", "turn_seconds", "success_turn_fraction", "stop_surface_z_m"):
        value = landing.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"D44 prep {key} missing or invalid")
    if not 0 < landing["success_turn_fraction"] <= 1:
        raise ValueError("D44 turn success fraction outside (0,1]")
    for key in ("approach_vx_mps", "restart_vx_mps"):
        value = landing.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"D44 prep {key} missing or invalid")
    if (not isinstance(landing.get("source_mesh_dir"), str) or not landing["source_mesh_dir"]
            or not isinstance(landing.get("source_mesh_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", landing["source_mesh_sha256"]) is None):
        raise ValueError("D44 prep source mesh path or SHA missing")
    return {"judge_cases": tuple(judges), "record_cases": tuple(records),
            "case_specs": cases, "timing": timing, "turn_rate_radps": landing["turn_rate_radps"],
            "turn_seconds": landing["turn_seconds"],
            "turn_success_fraction": landing["success_turn_fraction"],
            "approach_vx_mps": landing["approach_vx_mps"],
            "restart_vx_mps": landing["restart_vx_mps"],
            "stop_surface_z_m": landing.get("stop_surface_z_m"),
            "source_mesh_dir": landing.get("source_mesh_dir"),
            "source_mesh_sha256": landing.get("source_mesh_sha256")}


def _yaw(quat: np.ndarray) -> np.ndarray:
    w, x, y, z = np.moveaxis(quat, -1, 0)
    return np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def _continuous_true(mask: np.ndarray, steps: int) -> bool:
    run = 0
    for value in mask:
        run = run + 1 if bool(value) else 0
        if run >= steps:
            return True
    return False


def _longest_true(mask: np.ndarray) -> int:
    longest = run = 0
    for value in mask:
        run = run + 1 if bool(value) else 0
        longest = max(longest, run)
    return longest


def summarize(trace: dict, *, spec: dict, anchors: dict, settings: dict, dt: float) -> dict:
    """Score one 64-env case from post-step raw arrays; retain every env reason."""
    if spec.get("task") not in TASKS or not math.isfinite(dt) or dt <= 0:
        raise ValueError("D44 case task or dt invalid")
    if str(np.asarray(trace.get("trace_format", ""))) != TRACE_FORMAT:
        raise ValueError("D44 old trace format cannot prove the arrival stop")
    root = np.asarray(trace["root_pos_w"], dtype=np.float64)
    quat = np.asarray(trace["root_quat_w"], dtype=np.float64)
    feet = np.asarray(trace["foot_pos_w"], dtype=np.float64)
    contact = np.asarray(trace["contact"], dtype=bool)
    alive = np.asarray(trace["alive"], dtype=bool)
    body_vel = np.asarray(trace["body_vel_b"], dtype=np.float64)
    phases = np.asarray(trace["phase_id"], dtype=np.int16)
    commands = np.asarray(trace["cmd_post"], dtype=np.float64)
    latched_at = np.asarray(trace["top_latched_at"])
    origin = np.asarray(trace["tile_offset_w"], dtype=np.float64)
    steps, envs = alive.shape
    approached = np.asarray(trace.get("approach_entered", np.ones(envs, dtype=bool)), dtype=bool)
    if (root.shape != (steps, envs, 3) or quat.shape != (steps, envs, 4)
            or feet.shape != (steps, envs, 4, 3) or contact.shape != (steps, envs, 4)
            or body_vel.shape != (steps, envs, 3) or phases.shape != (steps, envs)
            or origin.shape != (envs, 3) or approached.shape != (envs,) or envs != 64
            or commands.shape != (steps, envs, 3) or latched_at.shape != (envs,)
            or latched_at.dtype.kind not in "iu" or contact.dtype != bool or alive.dtype != bool
            or np.any(alive[1:] & ~alive[:-1])
            or not all(np.isfinite(array).all() for array in (root, quat, feet, body_vel, origin, commands))):
        raise ValueError("D44 trace shape, finiteness or 64-env denominator differs")
    if not np.isin(phases, (0, 1, 2, 3, 4)).all():
        raise ValueError("D44 unknown phase id")
    timing = settings["timing"]
    counts = {name: round(timing[name] / dt) for name in
              ("settle_s", "approach_limit_s", "stop_s", "restart_limit_s")}
    turn_count = round(settings["turn_seconds"] / dt)
    if any(abs(counts[name] * dt - timing[name]) > dt / 2 for name in counts):
        raise ValueError("D44 trace timing does not align with policy dt")
    if (spec["task"].startswith("turn_") and
            (steps != counts["settle_s"] + turn_count or
             not np.all(phases[:counts["settle_s"]] == 0) or
             not np.all(phases[counts["settle_s"]:] == 1))):
        raise ValueError("D44 turn phase schedule differs")
    if spec["task"] == "stop_restart":
        a = counts["settle_s"]
        b = a + counts["approach_limit_s"]
        c = b + counts["stop_s"]
        if (steps != c + counts["restart_limit_s"] or
                not np.all(phases[:a] == 0) or not np.all(phases[a:b] == 1) or
                not np.all(phases[b:c] == 2) or not np.isin(phases[c:], (3, 4)).all()):
            raise ValueError("D44 stop and arrival phase schedule differs")
    local_root = root - origin[None]
    local_feet = feet - origin[None, :, None]
    xmin, xmax, ymin, ymax = anchors["landing_bounds_xy"]
    top = anchors["landing_center"][2]
    foot_floor = top - settings["timing"]["foot_below_top_m"]
    platform = ((local_root[:, :, 0] >= xmin) & (local_root[:, :, 0] <= xmax)
                & (local_root[:, :, 1] >= ymin) & (local_root[:, :, 1] <= ymax)
                & contact.any(axis=-1)
                & np.all(~contact | (local_feet[:, :, :, 2] >= foot_floor), axis=-1))
    yaw = np.unwrap(_yaw(quat), axis=0)
    rows = []
    for env in range(envs):
        survives = bool(alive[-1, env])
        valid, success, reason = True, False, ""
        if spec["task"].startswith("turn_"):
            if latched_at[env] != -1 or np.any(phases[:, env] == 4):
                raise ValueError("D44 turn trace contains an arrival latch")
            turn = phases[:, env] == 1
            sign = 1 if spec["task"] == "turn_left" else -1
            signed_yaw = sign * float(yaw[turn, env][-1] - yaw[turn, env][0]) if turn.any() else 0.0
            on_platform = bool(turn.any() and np.all(platform[turn, env]))
            success = bool(survives and on_platform and signed_yaw >=
                           settings["turn_seconds"] * settings["turn_rate_radps"]
                           * settings["turn_success_fraction"])
            reason = "turn_pass" if success else "turn_angle_or_platform_or_survival"
            rows.append({"env": env, "valid": valid, "survival": survives, "success": success,
                         "reason": reason, "signed_yaw_rad": signed_yaw,
                         "on_platform": on_platform})
            continue
        approach = phases[:, env] == 1
        stop = phases[:, env] == 2
        restart = phases[:, env] == 3
        top_stop = phases[:, env] == 4
        candidate = top_latch_mask(local_root[:, env, :2], local_feet[:, env, :, 0],
                                   alive[:, env], anchors["landing_bounds_xy"])
        first = np.flatnonzero(restart & candidate)
        expected_latch = int(first[0]) if len(first) else -1
        if int(latched_at[env]) != expected_latch or not np.array_equal(
                top_stop, (np.arange(steps) > expected_latch) & (phases[:, env] >= 3)
                if expected_latch >= 0 else np.zeros(steps, dtype=bool)):
            raise ValueError("D44 top latch or phase 4 differs from post-step geometry")
        # cmd_post is read after env.step. A terminal reset may resample the
        # command on that very step, so it is a policy-command witness only
        # while the env is still alive in the post-step trace.
        post_live = alive[:, env]
        if (np.any(np.abs(commands[restart & post_live, env, 0] - settings["restart_vx_mps"]) > 1e-5)
                or np.any(np.abs(commands[top_stop & post_live, env]) > 1e-5)
                or np.any(np.abs(commands[stop & post_live, env]) > 1e-5)):
            raise ValueError("D44 recorded command differs from restart and arrival stop")
        if not approached[env]:
            valid, reason = False, "approach_timeout"
        stop_floor = settings["stop_surface_z_m"]
        if stop_floor is None:
            raise ValueError("D44 prep stop surface height missing")
        stop_band = anchors["stop_band_x"]
        within_band = ((local_root[:, env, 0] >= stop_band[0])
                       & (local_root[:, env, 0] <= stop_band[1]))
        stopped = (np.linalg.norm(body_vel[:, env, :2], axis=-1) <= timing["stop_speed_mps"])
        stop_feet = (contact[:, env].any(axis=-1) & np.all(
                        ~contact[:, env] | (np.abs(local_feet[:, env, :, 2] - stop_floor)
                                              <= timing["foot_stop_z_tolerance_m"]), axis=-1))
        # Foot height is diagnostic. The approved stop is root x and horizontal speed.
        stop_ok = _continuous_true((stop & within_band & stopped),
                                   math.ceil(timing["stop_hold_s"] / dt))
        top_ok = top_stop & platform[:, env] & stopped
        reached = _continuous_true(top_ok, math.ceil(timing["top_hold_s"] / dt))
        success = bool(valid and survives and stop_ok and reached)
        on_landing = ((local_root[:, env, 0] >= xmin) & (local_root[:, env, 0] <= xmax)
                      & (local_root[:, env, 1] >= ymin) & (local_root[:, env, 1] <= ymax))
        feet_inside = ((local_feet[:, env, :, 0] >= xmin) & (local_feet[:, env, :, 0] <= xmax)
                       & (local_feet[:, env, :, 1] >= ymin) & (local_feet[:, env, :, 1] <= ymax)).all(axis=1)
        four_foot_xy_ticks = _longest_true(top_stop & feet_inside)
        if not valid:
            reason = "approach_timeout"
        elif success:
            reason = "stop_restart_pass"
        elif expected_latch < 0:
            reason = "no_top_latch"
        elif not stop_ok or not np.any(top_stop & stopped):
            reason = "not_still"
        elif np.any(top_stop & on_landing & contact[:, env].any(axis=1)
                    & ~np.all(~contact[:, env] | (local_feet[:, env, :, 2] >= foot_floor), axis=1)):
            reason = "foot_below_landing"
        elif np.any(top_stop & ~on_landing):
            reason = "left_landing"
        else:
            reason = "landing_hold_or_survival"
        rows.append({"env": env, "valid": valid, "survival": survives, "success": success,
                     "reason": reason,
                     "approach_steps": int(approach.sum()), "stop_ok": stop_ok,
                     "stop_feet_height_ok": bool(np.any(stop & stop_feet)),
                     "landing_0_5s": reached, "top_latched_at": expected_latch,
                     "lateral_offset_at_latch_m": (float(abs(local_root[expected_latch, env, 1] - (ymin + ymax) / 2))
                                                   if expected_latch >= 0 else None),
                     "max_foot_lateral_offset_m": (float(np.max(np.abs(
                         local_feet[top_stop, env, :, 1] - (ymin + ymax) / 2))) if top_stop.any() else None),
                     "four_foot_xy_inside_ticks": four_foot_xy_ticks})
    return {"envs": envs, "valid_count": sum(row["valid"] for row in rows),
            "survival_count": sum(row["survival"] for row in rows if row["valid"]),
            "success_count": sum(row["success"] for row in rows), "per_env": rows}


def _sha(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def read_evidence(folder: Path, *, plan: dict, plan_sha256: str,
                  checkpoint_sha256: str, seed: int) -> dict:
    """Bind each scored row to the Kit receipt, source JSON and per-step NPZ bytes."""
    settings = contract(plan)
    from foothold_s2.eval.ex42_eval_tile_mesh import source_tile

    source_manifest, source_column = source_tile(Path(settings["source_mesh_dir"]))
    if source_manifest["mesh_sha256"] != settings["source_mesh_sha256"]:
        raise ValueError("D44 source mesh SHA differs from prep")
    folder = Path(folder)
    receipt = json.loads((folder / "d44_cells.json").read_text(encoding="utf-8-sig"))
    expected = set(settings["judge_cases"] + settings["record_cases"])
    if (receipt.get("format") != RECEIPT_FORMAT or receipt.get("state") != "done"
            or receipt.get("plan_sha256") != plan_sha256
            or receipt.get("checkpoint_sha256") != checkpoint_sha256
            or receipt.get("source_mesh_sha256") != settings["source_mesh_sha256"]
            or receipt.get("seed") != seed or receipt.get("envs") != 64
            or set(receipt.get("cases", {})) != expected):
        raise ValueError("D44 Kit receipt conditions or coverage differ")
    output = {}
    for case_id in settings["judge_cases"] + settings["record_cases"]:
        indexed = receipt["cases"][case_id]
        spec = settings["case_specs"][case_id]
        source = folder / f"{case_id}.json"
        trace = folder / f"{case_id}.npz"
        if (indexed.get("raw_file") != str(source)
                or indexed.get("trace_file") != str(trace)
                or indexed.get("raw_sha256") != _sha(source)
                or indexed.get("trace_sha256") != _sha(trace)):
            raise ValueError(f"D44 {case_id} evidence path or SHA differs")
        row = json.loads(source.read_text(encoding="utf-8-sig"))
        if (row.get("case_id") != case_id or row.get("task") != spec["task"]
                or row.get("map_mode") != spec["map_mode"] or row.get("role") != spec["role"]
                or row.get("trace_sha256") != indexed["trace_sha256"]
                or any(row.get(key) != indexed.get(key) for key in
                       ("envs", "valid_count", "success_count", "survival_count"))):
            raise ValueError(f"D44 {case_id} score differs from indexed Kit evidence")
        with np.load(trace, allow_pickle=False) as arrays:
            recomputed = summarize({key: arrays[key] for key in arrays.files}, spec=spec,
                                   anchors=source_column["anchors_local_m"], settings=settings,
                                   dt=float(arrays["dt"]))
        if any(row.get(key) != recomputed[key] for key in
               ("envs", "valid_count", "success_count", "survival_count", "per_env")):
            raise ValueError(f"D44 {case_id} summary differs from raw trace")
        if case_id in settings["judge_cases"]:
            output[case_id] = {key: indexed[key] for key in
                               ("case_id", "envs", "valid_count", "success_count",
                                "survival_count", "raw_file", "raw_sha256")}
    return output
