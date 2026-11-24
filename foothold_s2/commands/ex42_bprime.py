"""Experimental B-prime first-flag bearing input and turn-in-place command.

The three inputs are [valid, body-frame unit x, body-frame unit y].  Only the
first unpassed flag is exposed.  All three entries are exactly zero when the
sample is not on its first flag, including ordinary velocity-command envs.
This module has no Isaac dependency so the command and transfer contracts can
be checked on the CPU before any simulation is launched.
"""

from __future__ import annotations

import math
import os

import torch


DEFAULT_TURN_RAD = 0.25
ENV_ENABLE = "EX42_BPRIME"
ENV_TURN_RAD = "EX42_BPRIME_TURN_RAD"
ENV_WEIGHT = "EX42_BPRIME_HEADING_WEIGHT"


def read_config(environ=None) -> dict[str, float] | None:
    env = os.environ if environ is None else environ
    enabled = env.get(ENV_ENABLE)
    if enabled in (None, "0"):
        if ENV_TURN_RAD in env or ENV_WEIGHT in env:
            raise ValueError("B-prime parameters require EX42_BPRIME=1")
        return None
    if enabled != "1":
        raise ValueError("EX42_BPRIME must be 0 or 1")
    threshold = validate_turn_rad(env.get(ENV_TURN_RAD, DEFAULT_TURN_RAD))
    weight = float(env.get(ENV_WEIGHT, "1.0"))
    if not math.isfinite(weight) or weight <= 0.0:
        raise ValueError("B-prime heading reward weight must be positive and finite")
    return {"turn_rad": threshold, "heading_weight": weight}


def validate_turn_rad(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or not 0.1 <= value <= 3.0:
        raise ValueError("B-prime turn threshold must be in [0.1, 3.0] rad")
    return value


def first_flag_bearing(flags: torch.Tensor, index: torch.Tensor, count: torch.Tensor,
                       position: torch.Tensor, yaw: torch.Tensor,
                       is_flag: torch.Tensor) -> torch.Tensor:
    """Return N x 3 features, masking invalid and already-passed first flags."""
    n = position.shape[0]
    if (flags.ndim != 3 or flags.shape[0] != n or flags.shape[-1] != 2
            or position.shape != (n, 2) or yaw.shape != (n,)
            or index.shape != (n,) or count.shape != (n,) or is_flag.shape != (n,)):
        raise ValueError("B-prime bearing shapes differ")
    if flags.shape[1] == 0:
        return position.new_zeros((n, 3))
    valid = is_flag.bool() & (index == 0) & (count > 0)
    delta = flags[:, 0] - position
    c, s = yaw.cos(), yaw.sin()
    x = c * delta[:, 0] + s * delta[:, 1]
    y = -s * delta[:, 0] + c * delta[:, 1]
    length = torch.clamp(torch.sqrt(x.square() + y.square()), min=1.0e-9)
    unit = torch.stack((x / length, y / length), -1)
    feature = torch.cat((valid.to(position.dtype)[:, None], unit), -1)
    return torch.where(valid[:, None], feature, torch.zeros_like(feature))


def turn_mask(bearing: torch.Tensor, threshold_rad: float) -> torch.Tensor:
    if bearing.ndim != 2 or bearing.shape[1] != 3:
        raise ValueError("B-prime bearing needs N x 3")
    threshold_rad = validate_turn_rad(threshold_rad)
    angle = torch.atan2(bearing[:, 2], bearing[:, 1])
    return (bearing[:, 0] == 1) & (angle.abs() > threshold_rad)


def command_for_learned_turn(command: torch.Tensor, bearing: torch.Tensor,
                             threshold_rad: float) -> tuple[torch.Tensor, torch.Tensor]:
    """A large initial bearing asks the actor to turn using the bearing reward.

    Linear and angular tracking targets are zero there.  The angular tracking
    reward is separately masked for these rows so that its zero target cannot
    punish the turn.  No scripted angular velocity is supplied to the actor.
    """
    if command.shape != bearing.shape:
        raise ValueError("B-prime command needs N x 3")
    mask = turn_mask(bearing, threshold_rad)
    return torch.where(mask[:, None], torch.zeros_like(command), command), mask


def heading_alignment_reward(bearing: torch.Tensor) -> torch.Tensor:
    """Dense 0..1 first-flag heading score; masked rows are exactly zero."""
    if bearing.ndim != 2 or bearing.shape[1] != 3:
        raise ValueError("B-prime bearing needs N x 3")
    return torch.where(bearing[:, 0] == 1, (bearing[:, 1] + 1.0) * 0.5,
                       torch.zeros_like(bearing[:, 0]))


def turn_exposure_counts(index: torch.Tensor, turning: torch.Tensor,
                         selected: torch.Tensor) -> tuple[float, float, float, float, float, float]:
    """Record-only turn counts, split by first versus later flag."""
    first = (index == 0)[selected]
    active = turning[selected]
    return (float(active.sum().item()), float(selected.sum().item()),
            float((active & first).sum().item()), float(first.sum().item()),
            float((active & ~first).sum().item()), float((~first).sum().item()))
