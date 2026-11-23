"""Optional first-flag bearing and the preregistered turn-before-walk trace check."""
from __future__ import annotations

import math

import numpy as np
import torch


def bearing_degrees(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value) or value < -180.0 or value > 180.0:
        raise ValueError("first flag bearing must be finite and within [-180, 180] degrees")
    return float(value)


def rotate_flags(flags: torch.Tensor, start_xy: torch.Tensor, start_yaw: torch.Tensor,
                 bearing_deg: float) -> torch.Tensor:
    """Rigidly turn each whole flag row around its actual robot spawn position."""
    if flags.ndim != 3 or flags.shape[-1] != 2 or flags.shape[1] < 1 or start_xy.shape != (len(flags), 2) or start_yaw.shape != (len(flags),):
        raise ValueError("first flag bearing input shape differs")
    if not bool(torch.isfinite(flags).all() and torch.isfinite(start_xy).all() and torch.isfinite(start_yaw).all()):
        raise ValueError("first flag bearing input is nonfinite")
    vector = flags[:, 0] - start_xy
    if bool((torch.linalg.norm(vector, dim=-1) < 1.0e-6).any()):
        raise ValueError("first flag coincides with robot spawn")
    current = torch.atan2(vector[:, 1], vector[:, 0])
    delta = start_yaw + math.radians(bearing_degrees(bearing_deg)) - current
    cosine, sine = torch.cos(delta), torch.sin(delta)
    offset = flags - start_xy[:, None, :]
    rotated = torch.stack((offset[..., 0] * cosine[:, None] - offset[..., 1] * sine[:, None],
                           offset[..., 0] * sine[:, None] + offset[..., 1] * cosine[:, None]), dim=-1)
    return start_xy[:, None, :] + rotated


def score_turn_before_walk(trace: dict) -> dict:
    """First body-forward speed >0.2 m/s: angle to flag and spawn displacement.

    The 20/35 degree and 0.15 m thresholds were fixed before this measurement
    (lead 2026-11-23 20:24). Missing crossings are counted as failures.
    """
    pos = np.asarray(trace["root_pos_w"], dtype=np.float64)
    vel = np.asarray(trace["root_vel_w"], dtype=np.float64)
    quat = np.asarray(trace["root_quat_w"], dtype=np.float64)
    alive = np.asarray(trace["alive"], dtype=bool)
    first = np.asarray(trace["flags_w"], dtype=np.float64)[:, 0]
    start = np.asarray(trace["start_pos_xy_w"], dtype=np.float64)
    if (pos.ndim != 3 or pos.shape[0] < 1 or pos.shape[1] < 1 or pos.shape[-1] != 3 or vel.shape != pos.shape or
            quat.shape != (*pos.shape[:2], 4) or alive.shape != pos.shape[:2] or
            first.shape != (pos.shape[1], 2) or start.shape != (pos.shape[1], 2) or
            not all(np.isfinite(x).all() for x in (pos, vel, quat, first, start))):
        raise ValueError("first flag bearing trace shape or finiteness differs")
    yaw = np.arctan2(2 * (quat[..., 0] * quat[..., 3] + quat[..., 1] * quat[..., 2]),
                     1 - 2 * (quat[..., 2] ** 2 + quat[..., 3] ** 2))
    body_vx = vel[..., 0] * np.cos(yaw) + vel[..., 1] * np.sin(yaw)
    crossings = alive & (body_vx > 0.2)
    has = crossings.any(axis=0)
    idx = crossings.argmax(axis=0)
    env = np.arange(pos.shape[1])
    at = pos[idx, env, :2]
    heading = yaw[idx, env]
    target = np.arctan2(first[:, 1] - at[:, 1], first[:, 0] - at[:, 0])
    error = np.abs((target - heading + np.pi) % (2 * np.pi) - np.pi) * 180 / np.pi
    distance = np.linalg.norm(at - start, axis=1)
    valid_error = error[has]
    median = float(np.median(valid_error)) if len(valid_error) else None
    p90 = float(np.percentile(valid_error, 90)) if len(valid_error) else None
    return {"format": "ex42-first-flag-bearing/1", "envs": pos.shape[1],
            "forward_crossings": int(has.sum()), "bearing_error_median_deg": median,
            "bearing_error_p90_deg": p90, "start_displacement_max_m": float(distance[has].max()) if has.any() else None,
            "passed": bool(has.all() and median <= 20.0 and p90 <= 35.0 and np.all(distance[has] <= 0.15)),
            "per_env": [{"env": int(j), "first_forward_step": int(idx[j]) if has[j] else None,
                         "bearing_error_deg": float(error[j]) if has[j] else None,
                         "start_displacement_m": float(distance[j]) if has[j] else None}
                        for j in env]}
