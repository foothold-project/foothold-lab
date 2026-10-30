"""W57 descriptive yaw, target-stop and four-foot contact measurements.

This module is CPU testable. It defines measurements, never pass thresholds.
"""

from __future__ import annotations

import math

import numpy as np

from foothold_s2.eval.map_mode_cells import STOP_LINEAR_MPS, STOP_YAW_RADPS


GOAL_DELTA_DEG = (0, 30, 60, 90)
FORWARD = {"fwd0.5": (0.5, 0.0, 0.0), "fwd1.0": (1.0, 0.0, 0.0)}
TURN_WZ_RADPS = 1.0
GOAL_TOLERANCE_RAD = 0.05
FOOT_NAMES = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
CONTACT_N = 1.0


def case_specs():
    """Two forward and eight signed goal offsets, all from the reset body yaw."""
    forward = [{"name": name, "kind": "forward", "command": command, "goal_delta_deg": None}
               for name, command in FORWARD.items()]
    goals = [{"name": f"goal_{side}_delta{degrees:03d}", "kind": "goal_turn_stop",
              "command": (0.0, 0.0, TURN_WZ_RADPS * sign), "goal_delta_deg": sign * degrees}
             for degrees in GOAL_DELTA_DEG for side, sign in (("left", 1), ("right", -1))]
    return forward + goals


def goal_stop_dynamic(start_yaw, target_yaw, yaw, alive, reached_step, stop_steps, dt,
                      vx=None, vy=None, wz=None):
    """Measure a fixed-length stop window starting at each env's actual goal arrival."""
    start_yaw, target_yaw = np.asarray(start_yaw), np.asarray(target_yaw)
    yaw, alive, reached_step = np.asarray(yaw), np.asarray(alive, bool), np.asarray(reached_step)
    if (yaw.ndim != 2 or alive.shape != yaw.shape or start_yaw.shape != (yaw.shape[1],)
            or target_yaw.shape != start_yaw.shape or reached_step.shape != start_yaw.shape
            or stop_steps < 1 or not math.isfinite(dt) or dt <= 0):
        raise ValueError("dynamic goal-stop receipt shapes or duration differ")
    if any(v is not None for v in (vx, vy, wz)) and any(v is None for v in (vx, vy, wz)):
        raise ValueError("dynamic stop velocity axes must be provided together")
    velocities = None if vx is None else tuple(np.asarray(v) for v in (vx, vy, wz))
    if velocities and any(v.shape != yaw.shape for v in velocities):
        raise ValueError("dynamic stop velocity shape differs")
    error = np.full(yaw.shape[1], np.nan)
    drift = error.copy()
    duration = np.zeros(yaw.shape[1])
    stationary = duration.copy() if velocities else None
    complete = np.zeros(yaw.shape[1], bool)
    for i, first in enumerate(reached_step):
        if first < 0 or first >= len(yaw):
            continue
        end = min(int(first) + stop_steps, len(yaw))
        mask = alive[int(first):end, i]
        duration[i] = int(mask.sum()) * dt
        complete[i] = end - int(first) == stop_steps and bool(mask.all())
        if velocities:
            x, y, z = (v[int(first):end, i] for v in velocities)
            stationary[i] = float((mask & (np.hypot(x, y) < STOP_LINEAR_MPS)
                                   & (np.abs(z) < STOP_YAW_RADPS)).sum() * dt)
        if complete[i]:
            error[i] = abs(wrap(target_yaw[i] - yaw[end - 1, i]))
            before = start_yaw[i] if first == 0 else yaw[int(first) - 1, i]
            drift[i] = wrap(yaw[end - 1, i] - before)
    return {"reached_step": reached_step, "stop_complete": complete,
            "stop_end_error_rad": error, "stop_yaw_drift_rad": drift,
            "stop_alive_duration_s": duration, "stop_stationary_duration_s": stationary}


def wrap(angle):
    return np.arctan2(np.sin(angle), np.cos(angle))


def yaw_accumulation(start_yaw, yaw, alive):
    """Signed and absolute yaw accumulated before the first done per env."""
    start_yaw, yaw, alive = np.asarray(start_yaw), np.asarray(yaw), np.asarray(alive, dtype=bool)
    if yaw.ndim != 2 or alive.shape != yaw.shape or start_yaw.shape != (yaw.shape[1],):
        raise ValueError("yaw receipt shapes differ")
    if not np.isfinite(start_yaw).all() or not np.isfinite(yaw).all():
        raise ValueError("yaw receipt has nonfinite values")
    signed = np.full(yaw.shape[1], np.nan)
    absolute = np.full(yaw.shape[1], np.nan)
    last = np.full(yaw.shape[1], np.nan)
    for env in range(yaw.shape[1]):
        indices = np.flatnonzero(alive[:, env])
        if not len(indices):
            continue
        if not np.array_equal(indices, np.arange(len(indices))):
            raise ValueError("alive became true after termination")
        sequence = np.r_[start_yaw[env], yaw[indices, env]]
        delta = wrap(np.diff(sequence))
        signed[env], absolute[env], last[env] = delta.sum(), np.abs(delta).sum(), sequence[-1]
    return {"signed_rad": signed, "absolute_rad": absolute,
            "final_minus_start_wrapped_rad": wrap(last - start_yaw), "last_yaw_rad": last}


def contact_symmetry(contact, alive):
    """FL,FR,RL,RR contact occupancy and left/right plus diagonal gaps."""
    contact, alive = np.asarray(contact, dtype=bool), np.asarray(alive, dtype=bool)
    if contact.ndim != 3 or contact.shape[:2] != alive.shape or contact.shape[2] != 4:
        raise ValueError("contact receipt must be (step,env,FL/FR/RL/RR)")
    fraction = np.full((contact.shape[1], 4), np.nan)
    for env in range(contact.shape[1]):
        if alive[:, env].any():
            fraction[env] = contact[alive[:, env], env].mean(axis=0)
    lateral = np.abs((fraction[:, 0] + fraction[:, 2] - fraction[:, 1] - fraction[:, 3]) / 2)
    diagonal = np.abs((fraction[:, 0] + fraction[:, 3] - fraction[:, 1] - fraction[:, 2]) / 2)
    return {"fraction_by_foot": fraction, "left_right_gap": lateral, "diagonal_gap": diagonal}


def goal_stop(start_yaw, target_yaw, yaw, alive, turn_steps: int, dt: float,
              vx=None, vy=None, wz=None):
    """Final goal error, time alive in stop phase, and fall in either phase."""
    start_yaw, target_yaw = np.asarray(start_yaw), np.asarray(target_yaw)
    yaw, alive = np.asarray(yaw), np.asarray(alive, dtype=bool)
    if (yaw.ndim != 2 or alive.shape != yaw.shape or start_yaw.shape != (yaw.shape[1],)
            or target_yaw.shape != start_yaw.shape or not 1 <= turn_steps < len(yaw)
            or not math.isfinite(dt) or dt <= 0):
        raise ValueError("goal-stop receipt shapes or phase time differ")
    if not np.isfinite(yaw).all() or not np.isfinite(target_yaw).all() or not np.isfinite(start_yaw).all():
        raise ValueError("goal-stop yaw is nonfinite")
    velocity = (vx, vy, wz)
    if any(v is not None for v in velocity):
        if any(v is None for v in velocity):
            raise ValueError("goal-stop velocity axes must be provided together")
        vx, vy, wz = (np.asarray(v) for v in velocity)
        if any(v.shape != yaw.shape or not np.isfinite(v).all() for v in (vx, vy, wz)):
            raise ValueError("goal-stop velocity receipt is invalid")
        stationary = alive[turn_steps:] & (np.hypot(vx[turn_steps:], vy[turn_steps:]) < STOP_LINEAR_MPS)
        stationary &= np.abs(wz[turn_steps:]) < STOP_YAW_RADPS
        stationary_duration = stationary.sum(axis=0) * dt
    else:
        stationary_duration = None
    error = np.full(yaw.shape[1], np.nan)
    drift = np.full(yaw.shape[1], np.nan)
    for env in range(yaw.shape[1]):
        kept = np.flatnonzero(alive[turn_steps:, env]) + turn_steps
        if not len(kept):
            continue
        error[env] = abs(wrap(target_yaw[env] - yaw[kept[-1], env]))
        drift[env] = wrap(yaw[kept[-1], env] - yaw[turn_steps - 1, env])
    return {"stop_end_error_rad": error, "stop_yaw_drift_rad": drift,
            "stop_alive_duration_s": alive[turn_steps:].sum(axis=0) * dt,
            "stop_stationary_duration_s": stationary_duration,
            "fall_in_turn": ~alive[turn_steps - 1],
            "fall_in_stop": alive[turn_steps - 1] & ~alive[-1],
            "start_yaw_rad": start_yaw, "target_yaw_rad": target_yaw}


def finite_median(values):
    values = np.asarray(values, dtype=float)
    kept = values[np.isfinite(values)]
    return float(np.median(kept)) if len(kept) else None


def alive_at_window_end(valid, stop_complete=None):
    """An early completed stop remains alive at its own fixed window boundary."""
    valid = np.asarray(valid, dtype=bool)
    if valid.ndim != 2 or not valid.shape[0]:
        raise ValueError("valid receipt must be (step,env)")
    if stop_complete is None:
        return valid[-1].copy()
    stop_complete = np.asarray(stop_complete, dtype=bool)
    if stop_complete.shape != (valid.shape[1],):
        raise ValueError("stop completion shape differs from env count")
    return stop_complete.copy()
