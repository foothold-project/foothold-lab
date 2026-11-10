"""CPU definitions for EX-42 W57 contact duty, phase and foot-center drag proxy."""

from __future__ import annotations

import math

import numpy as np


FOOT_ORDER = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")


def per_env(valid, contact, foot_xy_speed_mps, dt_s):
    """Use only post-step samples preceding reset; static terrain is the XY reference."""
    valid, contact = np.asarray(valid), np.asarray(contact)
    speed = np.asarray(foot_xy_speed_mps, dtype=np.float64)
    if (valid.ndim != 2 or valid.dtype != np.bool_ or contact.dtype != np.bool_
            or contact.shape != (*valid.shape, 4) or speed.shape != contact.shape
            or type(dt_s) not in (int, float, np.float32, np.float64)
            or not math.isfinite(float(dt_s)) or dt_s <= 0
            or not np.isfinite(speed[valid]).all() or np.any(speed[valid] < 0)):
        raise ValueError("EX-42 foot samples have invalid shape, mask, speed or dt")
    rows = []
    for env in range(valid.shape[1]):
        mask = valid[:, env]
        n = int(mask.sum())
        touches = contact[:, env] & mask[:, None]
        duty = ([float(touches[:, foot].sum() / n) for foot in range(4)] if n else None)
        drag = ([float(np.sum(speed[:, env, foot][touches[:, foot]]) * dt_s)
                 for foot in range(4)] if n else None)
        rising = touches & ~np.vstack([np.zeros((1, 4), dtype=bool), touches[:-1]])
        # A reset gap is never joined into a gait cycle.
        rising[1:] &= mask[:-1, None]
        touchdowns = [int(rising[:, foot].sum()) for foot in range(4)]
        fl = np.flatnonzero(rising[:, 0])
        phases = [0.0, None, None, None] if len(fl) >= 2 else [None] * 4
        for foot in range(1, 4):
            lags = []
            foot_onsets = np.flatnonzero(rising[:, foot])
            for start, end in zip(fl[:-1], fl[1:]):
                if not mask[start:end].all():
                    continue
                candidates = foot_onsets[(foot_onsets >= start) & (foot_onsets < end)]
                if len(candidates):
                    lags.append(float((candidates[0] - start) / (end - start)))
            if lags:
                phases[foot] = float(np.median(lags))
        rows.append({"env": env, "valid_steps": n, "duty_by_foot": duty,
                     "touchdowns_by_foot": touchdowns, "phase_from_FL_cycle": phases,
                     "foot_drag_proxy_m_by_foot": drag})
    return rows
