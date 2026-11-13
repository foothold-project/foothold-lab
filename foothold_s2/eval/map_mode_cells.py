"""CPU-only command cells and per-terrain receipts for map-mode evaluation."""

from __future__ import annotations

from collections import defaultdict
import math

import numpy as np

STOP_LINEAR_MPS = 0.05
STOP_YAW_RADPS = 0.1


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
EX40_B3_COMMANDS = {
    "walk+0.5": (0.5, 0.0, 0.5),
    "walk-0.5": (0.5, 0.0, -0.5),
    "walk+1.0": (0.5, 0.0, 1.0),
    "walk-1.0": (0.5, 0.0, -1.0),
    "spin+0.3": (0.0, 0.0, 0.3),
    "spin-0.3": (0.0, 0.0, -0.3),
    "slow0.1": (0.1, 0.0, 0.0),
    "slow0.2": (0.2, 0.0, 0.0),
    "slow0.3": (0.3, 0.0, 0.0),
}
N21_COMMANDS = {
    "fwd0.5": (0.5, 0.0, 0.0),
    "fwd1.0": (1.0, 0.0, 0.0),
    "spin+1.2": (0.0, 0.0, 1.2),
    "spin-1.2": (0.0, 0.0, -1.2),
    "back0.5": (-0.5, 0.0, 0.0),
    "side+0.5": (0.0, 0.5, 0.0),
    "side-0.5": (0.0, -0.5, 0.0),
    "stop": (0.0, 0.0, 0.0),
}
# HiPAN G1 (lead 11/12 · 팀장 12:25): 상위가 낼 수 있는데 EX-42 학습 13 슬롯 (ex42-prep.yaml shares · ranges)
# 밖인 조합과 슬롯 안 기준 몇 개. 학습 아님 · 측정만.
HIPAN_G1_COMMANDS = {
    # 슬롯 안 기준
    "ref_fwd0.5": (0.5, 0.0, 0.0),
    "ref_walk0.5_wz0.5": (0.5, 0.0, 0.5),
    "ref_side0.4": (0.0, 0.4, 0.0),
    "ref_spin0.8": (0.0, 0.0, 0.8),
    # 빠른 전진 + 회전 (walk_vx 상한 0.8 밖)
    "fast1.0_wz+0.5": (1.0, 0.0, 0.5),
    "fast1.0_wz-0.5": (1.0, 0.0, -0.5),
    "fast1.2_wz+0.8": (1.2, 0.0, 0.8),
    # 후진 + 회전
    "back0.5_wz+0.5": (-0.5, 0.0, 0.5),
    "back0.5_wz-0.5": (-0.5, 0.0, -0.5),
    # 옆 · 대각 + 회전
    "side+0.4_wz+0.5": (0.0, 0.4, 0.5),
    "side-0.4_wz-0.5": (0.0, -0.4, -0.5),
    "diag0.5+0.3_wz+0.5": (0.5, 0.3, 0.5),
    "diag0.5-0.3_wz-0.5": (0.5, -0.3, -0.5),
    # 세 축 동시
    "tri0.8_0.3_0.3": (0.8, 0.3, 0.3),
    # 느린 값 (슬롯 하한 밖)
    "side+0.1": (0.0, 0.1, 0.0),
    "walk0.5_wz+0.1": (0.5, 0.0, 0.1),
    "spin+0.15": (0.0, 0.0, 0.15),
    "creep0.05": (0.05, 0.0, 0.0),
    # 범위 밖 크기
    "side+0.8": (0.0, 0.8, 0.0),
    "diag0.8+0.4": (0.8, 0.4, 0.0),
}
# G1 보강 (lead 11/12 13:0x): 배운 범위 안 순수 옆걸음과 느린 값 죽은 구간 기준선 (planner 12:56 제안)
HIPAN_G1B_COMMANDS = {
    "side+0.2": (0.0, 0.2, 0.0),
    "side+0.3": (0.0, 0.3, 0.0),
    "side+0.4": (0.0, 0.4, 0.0),
    "side+0.6": (0.0, 0.6, 0.0),
    "side-0.4": (0.0, -0.4, 0.0),
    "fwd0.1": (0.1, 0.0, 0.0),
    "fwd0.2": (0.2, 0.0, 0.0),
    "spin+0.3": (0.0, 0.0, 0.3),
}
E1_V2_COMMANDS = {
    "fwd0.1": (0.1, 0.0, 0.0), "fwd0.2": (0.2, 0.0, 0.0),
    "side+0.2": (0.0, 0.2, 0.0), "side-0.2": (0.0, -0.2, 0.0),
    "side+0.4": (0.0, 0.4, 0.0), "side-0.4": (0.0, -0.4, 0.0),
}
GAIT_SPEED_COMMANDS = {
    "fwd0.1": (0.1, 0.0, 0.0), "fwd0.2": (0.2, 0.0, 0.0),
    "fwd0.3": (0.3, 0.0, 0.0), "fwd0.5": (0.5, 0.0, 0.0),
    "fwd1.0": (1.0, 0.0, 0.0),
    "side+0.1": (0.0, 0.1, 0.0), "side-0.1": (0.0, -0.1, 0.0),
    "side+0.2": (0.0, 0.2, 0.0), "side-0.2": (0.0, -0.2, 0.0),
    "back0.1": (-0.1, 0.0, 0.0), "back0.2": (-0.2, 0.0, 0.0),
}
SEQUENCES = {
    "spin_left_to_right": ((0.0, 0.0, 1.2), (0.0, 0.0, -1.2)),
    "spin_right_to_left": ((0.0, 0.0, -1.2), (0.0, 0.0, 1.2)),
    "stop_and_restart": ((0.0, 0.0, 0.0), (0.5, 0.0, 0.0),
                         (0.0, 0.0, 0.0), (0.5, 0.0, 0.0)),
}


def disable_heading_for_fixed_eval(term) -> None:
    """Fixed W15 commands must not be rewritten by EX-39 heading on the next step."""
    term.params.ex39_arm = None
    term.heading.fill_(False)
    term.psi_star.zero_()


def assert_heading_off_for_fixed_eval(term) -> None:
    if bool(term.heading.any()):
        raise RuntimeError("fixed evaluation command was overwritten by heading")


def commands(suite: str) -> dict[str, tuple[float, float, float]]:
    if suite == "core":
        return dict(CORE_COMMANDS)
    if suite == "extended":
        return {**CORE_COMMANDS, **EXTRA_COMMANDS}
    if suite == "ex40_b3":
        return {**CORE_COMMANDS, **EXTRA_COMMANDS, **EX40_B3_COMMANDS}
    if suite == "n21":
        return dict(N21_COMMANDS)
    if suite == "hipan_g1":
        return dict(HIPAN_G1_COMMANDS)
    if suite == "hipan_g1b":
        return dict(HIPAN_G1B_COMMANDS)
    if suite == "e1_v2":
        return dict(E1_V2_COMMANDS)
    if suite == "gait_speeds":
        return dict(GAIT_SPEED_COMMANDS)
    raise ValueError("command suite must be core, extended, ex40_b3, n21, hipan_g1, or gait_speeds")


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


def stationary_fraction(mean_xy_speed, mean_abs_yaw_rate, used) -> float:
    """Descriptive stop statistic across both commanded-zero motion axes."""
    mean_xy_speed = np.asarray(mean_xy_speed)
    mean_abs_yaw_rate = np.asarray(mean_abs_yaw_rate)
    used = np.asarray(used, dtype=bool)
    if mean_xy_speed.shape != mean_abs_yaw_rate.shape or used.shape != mean_xy_speed.shape or not used.any():
        raise ValueError("stop window needs matching nonempty samples")
    return float(np.mean((mean_xy_speed[used] < STOP_LINEAR_MPS) &
                         (mean_abs_yaw_rate[used] < STOP_YAW_RADPS)))


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
        out.append({"half_speed_response_s": float((hit[0] + 1) * dt) if len(hit) else None,
                    "yaw_sign_response_s": float((sign[0] + 1) * dt) if len(sign) else None})
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
