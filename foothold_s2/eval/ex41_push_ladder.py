"""Fixed-velocity EX-41 push ladder and CPU aggregation helpers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from typing import Any

MAGNITUDES_MPS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
PUSH250_MAGNITUDES_MPS = (1.0, 1.5, 2.0)
DIRECTIONS_DEG = (0, 45, 90, 135, 180, 225, 270, 315)
MAP_MODES = ("eval_gt", "eval_pred", "probe_prop_only")
TERRAIN_CASES = ("flat", "random_rough", "pyramid_stairs")
ENVS_PER_CASE = 64
PUSH_AT_S = 2.0
FOLLOW_S = 5.0
SURVIVAL_THRESHOLD = 0.90
CARDINAL_DIRECTIONS_DEG = (0, 90, 180, 270)
COMMANDS = {"walk_0.5": (0.5, 0.0, 0.0), "walk_1.0": (1.0, 0.0, 0.0),
            "walk_1.5": (1.5, 0.0, 0.0), "stand_turn_1.2": (0.0, 0.0, 1.2),
            "stand": (0.0, 0.0, 0.0)}


def build_case_grid(*, terrain: str | None = None, map_mode: str | None = None,
                    command: str = "walk_0.5", directions: tuple[int, ...] = DIRECTIONS_DEG) -> list[dict[str, Any]]:
    if terrain is not None and terrain not in TERRAIN_CASES:
        raise ValueError(f"unsupported terrain: {terrain}")
    if map_mode is not None and map_mode not in MAP_MODES:
        raise ValueError(f"unsupported map mode: {map_mode}")
    if command not in COMMANDS or not directions or not set(directions) <= set(DIRECTIONS_DEG):
        raise ValueError("unsupported command or direction set")
    terrains = (terrain,) if terrain else TERRAIN_CASES
    modes = (map_mode,) if map_mode else MAP_MODES
    return [{"terrain": name, "level": 0, "map_mode": mode, "command": command,
             "magnitude_mps": magnitude, "direction_deg": angle, "envs": ENVS_PER_CASE}
            for name in terrains for mode in modes for magnitude in MAGNITUDES_MPS
            for angle in directions]


def build_push250_case_grid(*, terrain: str | None = None) -> list[dict[str, Any]]:
    """Return the D171 250-update GT walking push cells, 64 envs per cell."""
    if terrain is not None and terrain not in TERRAIN_CASES:
        raise ValueError(f"unsupported terrain: {terrain}")
    terrains = (terrain,) if terrain else TERRAIN_CASES
    return [{"terrain": name, "level": 0, "map_mode": "eval_gt", "command": "walk_1.0",
             "magnitude_mps": magnitude, "direction_deg": angle, "envs": ENVS_PER_CASE}
            for name in terrains for magnitude in PUSH250_MAGNITUDES_MPS
            for angle in DIRECTIONS_DEG]


def fixed_target_range(magnitude_mps: float, direction_deg: int, *,
                       magnitudes: tuple[float, ...] = MAGNITUDES_MPS) -> dict[str, tuple[float, float]]:
    magnitude = float(magnitude_mps)
    angle = int(direction_deg)
    if not math.isfinite(magnitude) or magnitude not in magnitudes:
        raise ValueError("magnitude is not registered for this push profile")
    if angle not in DIRECTIONS_DEG:
        raise ValueError("direction must be one of the eight registered 45-degree headings")
    radians = math.radians(angle)
    x = round(magnitude * math.cos(radians), 12)
    y = round(magnitude * math.sin(radians), 12)
    return {"x": (x, x), "y": (y, y), "z": (0.0, 0.0),
            "roll": (0.0, 0.0), "pitch": (0.0, 0.0), "yaw": (0.0, 0.0)}


def summarize_ladder(rows: list[dict[str, Any]], *, terrain: str, map_mode: str,
                     command: str = "walk_0.5", directions: tuple[int, ...] = DIRECTIONS_DEG,
                     magnitudes: tuple[float, ...] = MAGNITUDES_MPS) -> dict[str, Any]:
    if terrain not in TERRAIN_CASES or map_mode not in MAP_MODES:
        raise ValueError("summary identity has an unsupported terrain or map mode")
    if command not in COMMANDS or not directions or not set(directions) <= set(DIRECTIONS_DEG):
        raise ValueError("summary command or direction selection is invalid")
    expected = {(m, d) for m in magnitudes for d in directions}
    found: dict[tuple[float, int], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("magnitude_mps"), row.get("direction_deg"))
        if key in found or key not in expected:
            raise ValueError(f"ladder must contain {len(expected)} unique cells")
        if row.get("terrain") != terrain or row.get("map_mode") != map_mode:
            raise ValueError("cell identity differs from summary identity")
        if row.get("command") != command:
            raise ValueError("cell command differs from summary command")
        if row.get("envs") != ENVS_PER_CASE:
            raise ValueError("each push cell requires 64 envs")
        survivors = row.get("survivors_after_5s")
        if type(survivors) is not int or not 0 <= survivors <= ENVS_PER_CASE:
            raise ValueError("survivors_after_5s must be an integer in [0,64]")
        tilt = row.get("max_tilt_rad")
        if not isinstance(tilt, (int, float)) or not math.isfinite(float(tilt)) or tilt < 0:
            raise ValueError("max_tilt_rad must be finite and nonnegative")
        recovery = row.get("recovery_times_s")
        if not isinstance(recovery, list) or any(
                value is not None and (not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0)
                for value in recovery):
            raise ValueError("recovery_times_s must contain finite nonnegative values or null")
        found[key] = row
    if set(found) != expected:
        raise ValueError(f"ladder must contain {len(expected)} unique cells")

    def recovered_median(values):
        samples = [float(value) for value in values if value is not None]
        return median(samples) if samples else None

    by_magnitude = {}
    for magnitude in magnitudes:
        cell_rows = [found[(magnitude, angle)] for angle in directions]
        survivors = sum(row["survivors_after_5s"] for row in cell_rows)
        samples = len(directions) * ENVS_PER_CASE
        recovery = [float(v) for row in cell_rows for v in row["recovery_times_s"] if v is not None]
        direction_rows = {
            str(angle): {
                "survivors": found[(magnitude, angle)]["survivors_after_5s"],
                "envs": ENVS_PER_CASE,
                "survival_fraction": found[(magnitude, angle)]["survivors_after_5s"] / ENVS_PER_CASE,
                "max_tilt_rad": float(found[(magnitude, angle)]["max_tilt_rad"]),
                "recovery_time_s_median": recovered_median(
                    found[(magnitude, angle)]["recovery_times_s"]),
            }
            for angle in directions
        }
        worst_direction = min(row["survivors_after_5s"] / ENVS_PER_CASE for row in cell_rows)
        by_magnitude[f"{magnitude:.1f}"] = {
            "survivors": survivors,
            "envs": samples,
            "survival_fraction": survivors / samples,
            "worst_direction_survival_fraction": worst_direction,
            "fall_fraction": (samples - survivors) / samples,
            "recovery_time_s_median": median(recovery) if recovery else None,
            "recovery_time_definition": f"median of recovered per-env recovery times across {len(directions)} registered directions",
            "max_tilt_rad": max(float(row["max_tilt_rad"]) for row in cell_rows),
            "directions": direction_rows,
        }
    tolerated = [m for m in magnitudes
                 if by_magnitude[f"{m:.1f}"]["survival_fraction"] >= SURVIVAL_THRESHOLD]
    return {
        "terrain": terrain,
        "level": 0,
        "map_mode": map_mode,
        "survival_threshold": SURVIVAL_THRESHOLD,
        "threshold_fraction": SURVIVAL_THRESHOLD,
        "maximum_tolerated_mps": max(tolerated) if tolerated else None,
        "maximum_tolerated_definition": f"highest registered magnitude with pooled {len(directions)}-direction survival fraction >= 0.90",
        "maximum_tolerated_worst_direction_mps": max(
            (m for m in magnitudes
             if by_magnitude[f"{m:.1f}"]["worst_direction_survival_fraction"] >= SURVIVAL_THRESHOLD),
            default=None),
        "worst_direction_definition": "minimum survival fraction among the registered push directions",
        "magnitudes": by_magnitude,
    }


def summarize_push250(rows: list[dict[str, Any]], *, terrain: str,
                      directions: tuple[int, ...] = DIRECTIONS_DEG) -> dict[str, Any]:
    """Summarize D171: 1.5 m/s uses the worst direction; 1.0 and 2.0 are record-only."""
    base = summarize_ladder(rows, terrain=terrain, map_mode="eval_gt", command="walk_1.0",
                            directions=directions, magnitudes=PUSH250_MAGNITUDES_MPS)
    criterion = base["magnitudes"]["1.5"]
    return {
        "profile": "D171_push250",
        "terrain": terrain,
        "level": 0,
        "map_mode": "eval_gt",
        "command": "walk_1.0",
        "directions_deg": list(directions),
        "envs_per_magnitude_direction": ENVS_PER_CASE,
        "d171_1_5_worst_direction": {
            "survival_fraction": criterion["worst_direction_survival_fraction"],
            "threshold_fraction": SURVIVAL_THRESHOLD,
            "passed": criterion["worst_direction_survival_fraction"] >= SURVIVAL_THRESHOLD,
            "direction_survival": {key: value["survival_fraction"]
                                   for key, value in criterion["directions"].items()},
        },
        "record_only_magnitudes": {
            key: {
                "survival_fraction": value["survival_fraction"],
                "worst_direction_survival_fraction": value["worst_direction_survival_fraction"],
                "directions": value["directions"],
                "recovery_time_s_median": value["recovery_time_s_median"],
                "max_tilt_rad": value["max_tilt_rad"],
            }
            for key, value in base["magnitudes"].items() if key in ("1.0", "2.0")
        },
        "measured_magnitudes": base["magnitudes"],
        "survival_threshold": SURVIVAL_THRESHOLD,
    }


def configure_single_terrain(env_cfg: Any, terrain: str, *, seed: int = 42) -> None:
    """Make a one-column fixed-kind generator for the requested terrain kind."""
    if terrain not in TERRAIN_CASES:
        raise ValueError(f"unsupported terrain: {terrain}")
    from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains
    from foothold_s2.terrains import sparse_terrains

    available = {**continuous_subterrains(), **sparse_terrains.sparse_subterrains()}
    chosen = available[terrain]
    chosen.proportion = 1.0
    env_cfg.scene.terrain.terrain_generator = build_generator({terrain: chosen}, 1, seed=int(seed))


def run_isaac_cell(args, env, raw, robot, term, agent_cfg, adapters, fixed_terrain,
                   terrain_names, checkpoint_state) -> dict[str, Any]:
    """Run one terrain/map-mode matrix with 3072 envs on an initialized Kit env."""
    import numpy as np
    import torch
    from isaaclab.managers import SceneEntityCfg

    from foothold_s2.eval.ex41_eval_loader import verify_ex41_pose_observation
    from foothold_s2.eval.ex41_eval_loader import load_checkpoint_for_eval
    from foothold_s2.eval.eval_dr_mode import recovery_metrics
    from foothold_s2.curriculum.ex40_dr_runtime import interval_push

    if args.push_ladder_terrain not in TERRAIN_CASES or args.push_ladder_map_mode not in MAP_MODES:
        raise ValueError("push ladder terrain/map mode is invalid")
    mode = args.push_ladder_map_mode
    terrain = args.push_ladder_terrain
    command_name = args.push_ladder_command
    profile = getattr(args, "push_ladder_profile", "full")
    magnitudes = PUSH250_MAGNITUDES_MPS if profile == "push250" else MAGNITUDES_MPS
    if profile not in ("full", "push250"):
        raise ValueError("unsupported push ladder profile")
    if profile == "push250" and (mode != "eval_gt" or command_name != "walk_1.0"
                                  or args.push_ladder_directions != "full"):
        raise ValueError("push250 requires eval_gt, walk_1.0 and the full eight-direction circle")
    directions = (CARDINAL_DIRECTIONS_DEG if args.push_ladder_directions == "cardinal"
                  else DIRECTIONS_DEG)
    expected_envs = len(magnitudes) * len(directions) * ENVS_PER_CASE
    if args.envs != expected_envs:
        raise ValueError(f"push ladder requires {expected_envs} envs for {len(directions)} directions x 64 envs")
    terrain_record = fixed_terrain.apply(raw, 0)
    env.reset()
    level = raw.scene.terrain.terrain_levels.detach().cpu().numpy()
    kind_ids = raw.scene.terrain.terrain_types.detach().cpu().numpy()
    if not np.all(level == 0) or not np.all(kind_ids == 0) or terrain_names != [terrain]:
        raise RuntimeError("push ladder requires all envs on the selected terrain at fixed L0")

    checkpoint_cfg, checkpoint_preparation = load_checkpoint_for_eval(
        raw.cfg, args.checkpoint) if checkpoint_state is None else (checkpoint_state, args.ex41_checkpoint_preparation)
    runner, state = adapters.load_s2_runner(
        env, agent_cfg.to_dict(), args.checkpoint, args.device,
        checkpoint_state=checkpoint_cfg)
    policy = adapters.S2Policy(runner, env.num_envs, z_mode="mean", act_mode="mean", map_mode=mode)
    obs = env.get_observations()
    if checkpoint_preparation and checkpoint_preparation.get("checkpoint_pose_commands"):
        verify_ex41_pose_observation(obs)

    command = COMMANDS[command_name]
    target_command = torch.tensor(command, dtype=torch.float32, device=raw.device)
    term.vel_command_b[:, :3] = target_command
    term.heading.fill_(False)
    term.psi_star.zero_()
    if bool(term.heading.any()):
        raise RuntimeError("push ladder fixed-command heading guard failed")

    counts = {"gt": 0, "total": 0}
    original_advance = runner.perception._advance

    def tapped(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map):
        counts["gt"] += int(use_gt.sum().item())
        counts["total"] += int(use_gt.numel())
        return original_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)

    runner.perception._advance = tapped
    dt = float(raw.step_dt)
    push_step = int(round(PUSH_AT_S / dt))
    total_steps = int(round((PUSH_AT_S + FOLLOW_S) / dt))
    if not math.isclose(push_step * dt, PUSH_AT_S, abs_tol=1e-9) or not math.isclose(total_steps * dt, PUSH_AT_S + FOLLOW_S, abs_tol=1e-9):
        raise RuntimeError("push ladder control timestep cannot represent exact 2s + 5s")
    alive = torch.ones(env.num_envs, dtype=torch.bool, device=raw.device)
    vx = torch.zeros((total_steps, env.num_envs), dtype=torch.float32, device=raw.device)
    vy = torch.zeros_like(vx)
    wz = torch.zeros_like(vx)
    tilt = torch.zeros_like(vx)
    xy = torch.zeros((total_steps, env.num_envs, 2), dtype=torch.float32, device=raw.device)
    dones_all = torch.zeros((total_steps, env.num_envs), dtype=torch.bool, device=raw.device)
    alive_all = torch.zeros_like(dones_all)
    event_receipts = []
    raw._ex40_dr_scale = 1.0
    raw._ex40_dr_samples = {}
    asset_cfg = SceneEntityCfg("robot")
    asset_cfg.resolve(raw.scene)
    asset = raw.scene["robot"]
    root_velocity = asset.root_physx_view.get_root_velocities()
    env_groups = []
    group_id = 0
    for magnitude in magnitudes:
        for angle in directions:
            env_ids = torch.arange(group_id * ENVS_PER_CASE, (group_id + 1) * ENVS_PER_CASE,
                                   dtype=torch.long, device=raw.device)
            env_groups.append((magnitude, angle, env_ids))
            group_id += 1

    for step in range(total_steps):
        term.vel_command_b[:, :3] = target_command
        action = policy(obs)
        if step == push_step:
            for magnitude, angle, env_ids in env_groups:
                target_range = fixed_target_range(magnitude, angle, magnitudes=magnitudes)
                before = root_velocity[env_ids].clone()
                interval_push(raw, env_ids, asset_cfg, target_range)
                after = root_velocity[env_ids].clone()
                event_receipts.append({
                    "magnitude_mps": magnitude, "direction_deg": angle,
                    "target_velocity_world_mps": [target_range["x"][0], target_range["y"][0]],
                    "applied_velocity_delta_world_mps_median": float(torch.linalg.vector_norm(after[:, :2] - before[:, :2], dim=1).median().item()),
                    "env_ids": [int(env_ids[0].item()), int(env_ids[-1].item())],
                })
        obs, _reward, dones, _extra = env.step(action)
        policy.reset(dones)
        dones = dones.bool()
        alive_all[step] = alive & ~dones
        vx[step] = robot.data.root_lin_vel_b[:, 0]
        vy[step] = robot.data.root_lin_vel_b[:, 1]
        wz[step] = robot.data.root_ang_vel_b[:, 2]
        gravity = robot.data.projected_gravity_b
        tilt[step] = torch.atan2(gravity[:, :2].norm(dim=1), -gravity[:, 2]).abs()
        xy[step] = robot.data.root_pos_w[:, :2]
        dones_all[step] = dones
        alive &= ~dones

    if mode == "eval_gt" and counts["gt"] != counts["total"]:
        raise RuntimeError("eval_gt push ladder did not use GT for every policy sample")
    if mode != "eval_gt" and counts["gt"]:
        raise RuntimeError(f"{mode} push ladder used GT unexpectedly")
    if counts["total"] != total_steps * env.num_envs:
        raise RuntimeError("push ladder policy sample count differs from rollout")

    vx_np, vy_np, wz_np = vx.cpu().numpy(), vy.cpu().numpy(), wz.cpu().numpy()
    alive_np, dones_np = alive_all.cpu().numpy(), dones_all.cpu().numpy()
    xy_np, tilt_np = xy.cpu().numpy(), tilt.cpu().numpy()
    cells = []
    from foothold_s2.eval.eval_dr_mode import RECOVERY_BAND_MPS, RECOVERY_BAND_RADPS, RECOVERY_HOLD_S
    hold_steps = max(1, int(round(RECOVERY_HOLD_S / dt)))
    for magnitude, angle, env_ids in env_groups:
        start, stop = int(env_ids[0].item()), int(env_ids[-1].item()) + 1
        recovery = recovery_metrics(alive_np[:, start:stop], dones_np[:, start:stop],
                                    vx_np[:, start:stop], vy_np[:, start:stop],
                                    xy_np[:, start:stop], dt, push_step,
                                    wz=wz_np[:, start:stop], tilt=tilt_np[:, start:stop], cmd=command)
        post_push_alive = alive_np[-1, start:stop]
        post_alive = alive_np[push_step:, start:stop]
        err = np.hypot(vx_np[push_step:, start:stop] - command[0],
                       vy_np[push_step:, start:stop] - command[1])
        inside = ((err <= RECOVERY_BAND_MPS) & post_alive
                  & (np.abs(wz_np[push_step:, start:stop] - command[2]) <= RECOVERY_BAND_RADPS))
        recovery_times = []
        for env_index in range(ENVS_PER_CASE):
            run_length = 0
            found_at = None
            for sample_index in range(inside.shape[0]):
                run_length = run_length + 1 if bool(inside[sample_index, env_index]) else 0
                if run_length >= hold_steps:
                    found_at = (sample_index - hold_steps + 2) * dt
                    break
            recovery_times.append(found_at)
        alive_tilt = np.where(post_alive, tilt_np[push_step:, start:stop], 0.0)
        cells.append({
            "terrain": terrain, "map_mode": mode, "level": 0,
            "command": command_name,
            "magnitude_mps": magnitude, "direction_deg": angle,
            "envs": ENVS_PER_CASE,
            "survivors_after_5s": int(post_push_alive.sum()),
            "pre_push_alive_envs": int(alive_np[push_step - 1, start:stop].sum()),
            "pre_push_fallen_envs": int(dones_np[:push_step, start:stop].any(axis=0).sum()),
            "pre_push_command_error_median_mps": float(np.median(np.hypot(
                vx_np[:push_step, start:stop] - command[0], vy_np[:push_step, start:stop] - command[1]))),
            "post_push_fallen_envs": int(dones_np[push_step:, start:stop].any(axis=0).sum()),
            "recovery_times_s": recovery_times,
            "max_tilt_rad": float(alive_tilt.max()),
            "recovery_metrics": recovery,
        })

    digest = __import__("hashlib").sha256(Path(args.checkpoint).read_bytes()).hexdigest()
    result = {
        "format": "foothold-ex41-push-ladder-cell/1",
        "task": args.task, "checkpoint": str(Path(args.checkpoint).resolve()),
        "checkpoint_sha256": digest, "checkpoint_iteration": int(state.get("iter", -1)),
        "terrain": terrain, "terrain_kind": terrain, "level": 0,
        "terrain_assignment": terrain_record,
        "map_mode": mode, "map_mode_label": {"eval_gt": "정답", "eval_pred": "복원", "probe_prop_only": "끔"}[mode],
        "command": {"name": command_name, "value_mps_radps": list(command)},
        "envs": env.num_envs, "envs_per_cell": ENVS_PER_CASE,
        "control_dt_s": dt, "physics_dt_s": float(raw.physics_dt),
        "decimation": int(round(dt / float(raw.physics_dt))),
        "push_at_s": PUSH_AT_S, "push_step": push_step,
        "follow_after_push_s": FOLLOW_S, "total_steps": total_steps,
        "directions_deg": list(directions), "magnitudes_mps": list(magnitudes),
        "profile": profile,
        "recovery_definition": {"linear_band_mps": RECOVERY_BAND_MPS,
                                "yaw_band_radps": RECOVERY_BAND_RADPS,
                                "hold_s": RECOVERY_HOLD_S,
                                "command_is_held_for_pre_and_post_push": True},
        "push_consumer": "foothold_s2.curriculum.ex40_dr_runtime.interval_push",
        "push_events": event_receipts,
        "policy_gt_samples": counts,
        "cells": cells,
    }
    result["summary"] = (summarize_push250(cells, terrain=terrain, directions=directions)
                         if profile == "push250" else summarize_ladder(
                             cells, terrain=terrain, map_mode=mode, command=command_name,
                             directions=directions, magnitudes=magnitudes))
    out = Path(args.push_ladder_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out.with_suffix(".npz"), vx=vx_np, vy=vy_np, wz=wz_np,
                        tilt_rad=tilt_np, xy_world_m=xy_np,
                        alive=alive_np, dones=dones_np,
                        env_group=np.repeat(np.arange(len(env_groups)), ENVS_PER_CASE),
                        magnitude_mps=np.repeat(np.asarray(magnitudes, dtype=np.float32),
                                                len(directions) * ENVS_PER_CASE),
        direction_deg=np.repeat(np.tile(np.asarray(directions, dtype=np.int16),
                                                       len(magnitudes)), ENVS_PER_CASE))
    result["arrays"] = {"path": str(out.with_suffix(".npz")),
                         "sha256": __import__("hashlib").sha256(out.with_suffix(".npz").read_bytes()).hexdigest()}
    out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    raise SystemExit("Use eval_map_modes.py --push-ladder for an initialized Isaac environment")

