"""CPU-only command cells and per-terrain receipts for map-mode evaluation."""

from __future__ import annotations

from collections import defaultdict
import math

import numpy as np


CORE_COMMANDS = {
    "fwd0.5": (0.5, 0.0, 0.0),
    "fwd1.0": (1.0, 0.0, 0.0),
    "spin+1.2": (0.0, 0.0, 1.2),
    "spin-1.2": (0.0, 0.0, -1.2),
}
EXTRA_COMMANDS = {
    "back0.5": (-0.5, 0.0, 0.0),
    "back1.0": (-1.0, 0.0, 0.0),
    "side+0.5": (0.0, 0.5, 0.0),
    "side-0.5": (0.0, -0.5, 0.0),
    "diag-fwd+side+": (0.5, 0.5, 0.0),
    "diag-fwd+side-": (0.5, -0.5, 0.0),
    "diag-back+side+": (-0.5, 0.5, 0.0),
    "diag-back+side-": (-0.5, -0.5, 0.0),
    "stop": (0.0, 0.0, 0.0),
}
SEQUENCES = {
    "spin_left_to_right": ((0.0, 0.0, 1.2), (0.0, 0.0, -1.2)),
    "spin_right_to_left": ((0.0, 0.0, -1.2), (0.0, 0.0, 1.2)),
    "stop_and_restart": ((0.0, 0.0, 0.0), (0.5, 0.0, 0.0),
                         (0.0, 0.0, 0.0), (0.5, 0.0, 0.0)),
}


def commands(suite: str) -> dict[str, tuple[float, float, float]]:
    if suite == "core":
        return dict(CORE_COMMANDS)
    if suite == "extended":
        return {**CORE_COMMANDS, **EXTRA_COMMANDS}
    raise ValueError("command suite must be core or extended")


def terrain_rows(levels, types, names: list[str]) -> list[dict]:
    levels = np.asarray(levels)
    types = np.asarray(types)
    if levels.shape != types.shape or levels.ndim != 1:
        raise ValueError("terrain levels/types shape mismatch")
    if np.any(types < 0) or np.any(types >= len(names)):
        raise ValueError("terrain type is outside column names")
    return [{"env": i, "kind": names[int(types[i])], "level": int(levels[i]),
             "column": int(types[i])} for i in range(len(levels))]


def phase_steps(total: int, phases: int) -> list[int]:
    if total < phases or phases < 1:
        raise ValueError("one or more steps required per phase")
    base, remainder = divmod(total, phases)
    return [base + (i < remainder) for i in range(phases)]


def response_times(command, vx, vy, wz, alive, dt: float) -> list[dict]:
    """Descriptive first half-speed and yaw-sign response, without a pass gate."""
    vx, vy, wz, alive = (np.asarray(a) for a in (vx, vy, wz, alive))
    cx, cy, cz = map(float, command)
    norm = math.hypot(cx, cy)
    projected = (vx * cx + vy * cy) / norm if norm else None
    out = []
    for i in range(vx.shape[1]):
        hit = np.flatnonzero(alive[:, i] & (projected[:, i] >= norm * 0.5)) if norm else []
        sign = np.flatnonzero(alive[:, i] & (wz[:, i] * cz > 0)) if cz else []
        out.append({"half_speed_response_s": float(hit[0] * dt) if len(hit) else None,
                    "yaw_sign_response_s": float(sign[0] * dt) if len(sign) else None})
    return out


def summarize(command, tiles: list[dict], vx, vy, wz, alive, alive_final, dt: float,
              world_xy_start=None, world_xy_end=None, world_xy_samples=None) -> dict:
    vx, vy, wz, alive = (np.asarray(a) for a in (vx, vy, wz, alive))
    alive_final = np.asarray(alive_final, dtype=bool)
    if vx.shape != vy.shape or vx.shape != wz.shape or vx.shape != alive.shape or vx.ndim != 2:
        raise ValueError("sample matrix shape mismatch")
    steps, envs = vx.shape
    if alive_final.shape != (envs,) or len(tiles) != envs or sorted(t["env"] for t in tiles) != list(range(envs)):
        raise ValueError("terrain receipt must name each env exactly once")
    if steps < 1 or not math.isfinite(dt) or dt <= 0 or not np.isfinite(vx).all() or not np.isfinite(vy).all() or not np.isfinite(wz).all():
        raise ValueError("invalid samples or dt")
    if len(command) != 3 or not all(math.isfinite(float(x)) for x in command):
        raise ValueError("invalid command")
    cx, cy, cz = map(float, command)
    if (world_xy_start is None) != (world_xy_end is None):
        raise ValueError("world XY start and end must be paired")
    if world_xy_start is not None:
        world_xy_start, world_xy_end = np.asarray(world_xy_start), np.asarray(world_xy_end)
        if world_xy_start.shape != (envs, 2) or world_xy_end.shape != (envs, 2):
            raise ValueError("world XY shape mismatch")
    if world_xy_samples is not None:
        world_xy_samples = np.asarray(world_xy_samples)
        if world_xy_start is None or world_xy_samples.shape != (steps, envs, 2):
            raise ValueError("world XY samples shape mismatch")
    norm = math.hypot(cx, cy)
    projected = (vx * cx + vy * cy) / norm if norm else np.zeros_like(vx)
    per_env = []
    for tile in sorted(tiles, key=lambda t: t["env"]):
        i = tile["env"]
        mask = alive[:, i].astype(bool)
        count = int(mask.sum())
        row = {**tile, "samples_alive": count, "alive_at_end": bool(alive_final[i]),
               "command_xy_projection_integral_m": float((projected[:, i] * mask).sum() * dt) if norm else None,
               "body_xy_speed_mean_alive_mps": float(np.hypot(vx[:, i], vy[:, i])[mask].mean()) if count else None,
               "yaw_follow_mean_alive": float(wz[:, i][mask].mean() / cz) if cz and count else None,
               "vx_abs_error_mean_alive_mps": float(np.abs(vx[:, i][mask] - cx).mean()) if count else None,
               "vy_abs_error_mean_alive_mps": float(np.abs(vy[:, i][mask] - cy).mean()) if count else None,
               "wz_abs_error_mean_alive_radps": float(np.abs(wz[:, i][mask] - cz).mean()) if count else None,
               "world_xy_displacement_m": float(np.linalg.norm(world_xy_end[i] - world_xy_start[i]))
               if world_xy_start is not None and alive_final[i] else None}
        if world_xy_samples is not None:
            previous = np.vstack((world_xy_start[i], world_xy_samples[:-1, i]))
            row["world_xy_path_m"] = float((np.linalg.norm(world_xy_samples[:, i] - previous, axis=1) * mask).sum())
        per_env.append(row)
    groups = defaultdict(list)
    kind_levels = defaultdict(list)
    for row in per_env:
        groups[row["kind"]].append(row)
        kind_levels[(row["kind"], row["level"])].append(row)
    by_kind = {}
    for kind, rows in sorted(groups.items()):
        progress = [r["command_xy_projection_integral_m"] for r in rows if r["command_xy_projection_integral_m"] is not None]
        by_kind[kind] = {"env_count": len(rows), "alive_at_end": sum(r["alive_at_end"] for r in rows),
                         "command_xy_projection_median_m": float(np.median(progress)) if progress else None,
                         "vx_abs_error_median_mps": float(np.median([r["vx_abs_error_mean_alive_mps"] for r in rows if r["vx_abs_error_mean_alive_mps"] is not None])) if any(r["vx_abs_error_mean_alive_mps"] is not None for r in rows) else None,
                         "vy_abs_error_median_mps": float(np.median([r["vy_abs_error_mean_alive_mps"] for r in rows if r["vy_abs_error_mean_alive_mps"] is not None])) if any(r["vy_abs_error_mean_alive_mps"] is not None for r in rows) else None,
                         "levels": sorted(set(r["level"] for r in rows))}
    by_kind_level = {}
    for (kind, level), rows in sorted(kind_levels.items()):
        progress = [r["command_xy_projection_integral_m"] for r in rows if r["command_xy_projection_integral_m"] is not None]
        by_kind_level[f"{kind}/L{level}"] = {
            "env_count": len(rows), "alive_at_end": sum(r["alive_at_end"] for r in rows),
            "command_xy_projection_median_m": float(np.median(progress)) if progress else None}
    return {"command": [cx, cy, cz], "env_count": envs, "per_env": per_env,
            "by_kind": by_kind, "by_kind_level": by_kind_level}
