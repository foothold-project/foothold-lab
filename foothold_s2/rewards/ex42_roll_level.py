"""EX-42 body roll level reward without a posture command (`ex42_roll_level`, lead 2026-11-22 00:40, ledger 411b51789 H-roll).
Off by default: registered only with EX42_ROLL_LEVEL=1, at weight EX42_ROLL_LEVEL_WEIGHT (default 0.2 = HiPAN Table III w4L).

Why: in rx2pz the posture roll tracking term (exp(-|roll - cmd| / 0.05), w 0.2, cmd near 0) kept all four straight-walk yaw cells within
0.015 by +100. This is that term with the command fixed at 0: no posture command, the pose_cmd observation (actor 96:98) stays the zero
producer, no height term.

    value = exp(-|roll| / 0.05)          roll = body roll from root_quat_w (w x y z), rad;  1 when level, exp(-1) = 0.37 at 0.05 rad

Against `flat_orientation` (flat_orientation_l2, weight -1.0, already on): that is an L2 penalty on the gravity xy components (roll and
pitch together, about -(roll^2 + pitch^2)); near level its slope is 2 x roll (0.1 per rad at 0.05 rad), so small roll costs almost nothing.
This term is roll only and sharp at 0: weight x slope = 0.2 / 0.05 = 4 per rad at any small roll, about 40 times the L2 slope at 0.05 rad.
No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

TERM = "ex42_roll_level"
ENV_SWITCH = "EX42_ROLL_LEVEL"
WEIGHT_ENV = "EX42_ROLL_LEVEL_WEIGHT"
SIGMA = 0.05                         # HiPAN Table III roll tracking scale (2604.26504.txt:605)
DEFAULT_WEIGHT = 0.2                 # HiPAN Table III w4L (2604.26504.txt:627)


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    if value != "1" and os.environ.get(WEIGHT_ENV, "") != "":
        raise ValueError(f"{WEIGHT_ENV} is set but {ENV_SWITCH} is not 1")
    return value == "1"


def weight() -> float:
    raw = os.environ.get(WEIGHT_ENV, "")
    try:
        w = float(raw) if raw != "" else DEFAULT_WEIGHT
    except ValueError:
        raise ValueError(f"{WEIGHT_ENV} must be a number (got {raw!r})") from None
    if not math.isfinite(w) or w < 0.0:
        raise ValueError(f"{WEIGHT_ENV} must be finite and >= 0 (a reward weight, got {raw!r})")
    return w


def body_roll(quat_wxyz: torch.Tensor) -> torch.Tensor:
    w, x, y, z = quat_wxyz.unbind(-1)
    return torch.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))


def roll_level(env, asset_name: str = "robot"):
    """(N,) exp(-|roll| / SIGMA)."""
    return torch.exp(-body_roll(env.scene[asset_name].data.root_quat_w).abs() / SIGMA)


def register(env_cfg, term_cfg_class=None) -> bool:
    """Before the env is built: add the term when the switch is on and the config does not have it yet. True when added (one start line)."""
    if not enabled() or hasattr(env_cfg.rewards, TERM):
        return False
    w = weight()
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    setattr(env_cfg.rewards, TERM, term_cfg_class(func=roll_level, weight=w, params={"asset_name": "robot"}))
    print(f"EX42_ROLL_LEVEL where=start weight={w} sigma={SIGMA} roll_cmd=0 pose_cmd=zero height_term=none", flush=True)
    return True
