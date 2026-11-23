"""Optional E2 stand-transition shaping, independent of the existing stop bundle.

The foot-x reference is the per-env default joint pose through the Go2 URDF FK, rather than
the random reset joint pose. This is the brief's ``reset default-pose FK`` alternative.
Only continuous-column, moving-to-stand transitions enter the window. No RNG is used here.
"""
from __future__ import annotations

import math
import os

import torch

from foothold_s2.rewards.ex42_stop_bundle import FEET, foot_xy, stop_mask
from foothold_s2.rewards.ex42_hip_sparse import sparse_envs

ENV_SWITCH = "EX42_STOP_WINDOW_SHAPE"
PARAMS_ENV = "EX42_STOP_WINDOW_SHAPE_PARAMS"
DEFAULTS = {"window": 1.0, "x_weight": 0.1, "x_width": 0.08, "stand_share": 0.15}
PENALTIES = ("ex39_four_foot_stop", "ex40_stand_gap", "ex40_stand_load")
HIP_X, LINK, FOOT_X = 0.1934, 0.213, -0.002
_COUNTS: dict[str, torch.Tensor] = {}


def enabled() -> bool:
    switch = os.environ.get(ENV_SWITCH, "")
    if switch not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1")
    if switch != "1" and os.environ.get(PARAMS_ENV, ""):
        raise ValueError(f"{PARAMS_ENV} needs {ENV_SWITCH}=1")
    return switch == "1"


def params() -> dict:
    out = dict(DEFAULTS)
    for item in filter(None, (part.strip() for part in os.environ.get(PARAMS_ENV, "").split(","))):
        key, sep, raw = item.partition("=")
        if not sep or key not in out:
            raise ValueError(f"{PARAMS_ENV} unknown or malformed cell {item!r}")
        try:
            out[key] = float(raw)
        except ValueError:
            raise ValueError(f"{PARAMS_ENV} invalid number {item!r}") from None
    if (any(not math.isfinite(v) for v in out.values()) or out["window"] <= 0 or out["x_weight"] <= 0
            or out["x_width"] <= 0 or not 0 < out["stand_share"] < 0.9):
        raise ValueError(f"{PARAMS_ENV} needs finite window/width/weight > 0, share in (0, 0.9)")
    return out


def window_mask(env, command_name: str, window_s: float) -> torch.Tensor:
    term = env.command_manager.get_term(command_name)
    if not hasattr(term, "stop_from_move") or not hasattr(term, "stop_elapsed_s"):
        raise ValueError("EX42_STOP_WINDOW_SHAPE needs the command transition clock")
    return stop_mask(env, command_name) & term.stop_from_move & (term.stop_elapsed_s < window_s)


def default_foot_x(joint_names, default_joint_pos: torch.Tensor) -> torch.Tensor:
    """Go2 URDF foot collision center x, in FL FR RL RR order, for each env's default pose."""
    names = list(joint_names)
    cols = []
    for leg in ("FL", "FR", "RL", "RR"):
        thigh = default_joint_pos[:, names.index(f"{leg}_thigh_joint")]
        calf = default_joint_pos[:, names.index(f"{leg}_calf_joint")]
        front = 1.0 if leg[0] == "F" else -1.0
        cols.append(front * HIP_X - LINK * torch.sin(thigh) - LINK * torch.sin(thigh + calf)
                    + FOOT_X * torch.cos(thigh + calf))
    return torch.stack(cols, dim=1)


def x_reward(x: torch.Tensor, reference: torch.Tensor, width: float) -> torch.Tensor:
    return torch.exp(-(x - reference).abs().mean(dim=1) / width)


def _add(key: str, value: torch.Tensor) -> None:
    if key not in _COUNTS:
        _COUNTS[key] = torch.zeros((), device=value.device, dtype=torch.float64)
    _COUNTS[key] += value.double().sum()


def ex42_stop_window_x(env, command_name, asset_cfg, window_s: float, width: float):
    active = window_mask(env, command_name, window_s)
    robot = env.scene[asset_cfg.name]
    raw = getattr(env, "unwrapped", env)
    ref = getattr(raw, "_ex42_stop_window_ref_x", None)
    if ref is None:
        ref = default_foot_x(robot.joint_names, robot.data.default_joint_pos).to(active.device)
        raw._ex42_stop_window_ref_x = ref
    x, _ = foot_xy(env, asset_cfg)
    value = torch.where(active, x_reward(x, ref, width), torch.zeros_like(x[:, 0]))
    term = env.command_manager.get_term(command_name)
    dt = float(raw.step_dt)
    first = active & (term.stop_elapsed_s > 0) & (term.stop_elapsed_s < 1.5 * dt)
    _add("window_env_steps", active)
    _add("x_reward_sum", value)
    _add("moving_to_stop", first)
    _add("continuous_env_steps", ~sparse_envs(env))
    _add("continuous_env_seconds", (~sparse_envs(env)).to(torch.float64) * dt)
    return value


def _without_window(func, window_s: float):
    def reward(env, **kwargs):
        value = func(env, **kwargs)
        return torch.where(window_mask(env, kwargs["command_name"], window_s), torch.zeros_like(value), value)
    reward.__wrapped__ = func
    reward.ex42_stop_window_shape = True
    return reward


def register(env_cfg, term_cfg_class=None, entity_cfg_class=None, *, stage_id=None) -> bool:
    if not enabled():
        return False
    if stage_id != "E2":
        raise ValueError(f"{ENV_SWITCH}=1 is scoped to E2 (got {stage_id!r})")
    p = params()
    try:
        noise_window = float(os.environ.get("EX42_STOP_NOISE_WINDOW_S", ""))
    except ValueError:
        noise_window = float("nan")
    if not math.isfinite(noise_window) or not math.isclose(noise_window, p["window"], abs_tol=1e-9):
        raise ValueError(f"{ENV_SWITCH}=1 needs EX42_STOP_NOISE_WINDOW_S equal to window")
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    if entity_cfg_class is None:
        from isaaclab.managers import SceneEntityCfg as entity_cfg_class
    rewards = env_cfg.rewards
    for name in PENALTIES:
        term = getattr(rewards, name, None)
        if term is None:
            raise ValueError(f"{ENV_SWITCH}=1 needs {name}")
        if getattr(term.func, "ex42_stop_window_shape", False):
            raise ValueError(f"{ENV_SWITCH} registered twice on {name}")
        term.func = _without_window(term.func, p["window"])
    entity = entity_cfg_class("robot", body_names=list(FEET), preserve_order=True)
    rewards.ex42_stop_window_x = term_cfg_class(
        func=ex42_stop_window_x, weight=p["x_weight"],
        params={"command_name": "base_velocity", "asset_cfg": entity,
                "window_s": p["window"], "width": p["x_width"]})
    print("EX42_STOP_WINDOW_SHAPE where=start window_s=%g x_weight=%g x_width=%g stand_share=%g" % (
        p["window"], p["x_weight"], p["x_width"], p["stand_share"]), flush=True)
    return True


def override_shares(shares: dict, target_stand: float) -> dict:
    old = shares["stand"]
    flag = shares["flag"]
    if target_stand >= 1 - flag or old >= 1 - flag:
        raise ValueError("EX42_STOP_WINDOW_SHAPE stand share leaves no free moving slots")
    factor = (1 - flag - target_stand) / (1 - flag - old)
    return {key: (value if key == "flag" else target_stand if key == "stand" else value * factor)
            for key, value in shares.items()}


def summary() -> dict | None:
    if not enabled():
        return None
    values = {key: float(value.item()) for key, value in _COUNTS.items()}
    steps = values.get("window_env_steps", 0.0)
    continuous = values.get("continuous_env_steps", 0.0)
    seconds = values.get("continuous_env_seconds", 0.0)
    return {"window_env_steps": int(steps), "x_reward_mean": values.get("x_reward_sum", 0.0) / steps if steps else None,
            "moving_to_stop": int(values.get("moving_to_stop", 0.0)),
            "moving_to_stop_per_env_20s": values.get("moving_to_stop", 0.0) * 20 / seconds if seconds else None,
            "continuous_env_steps": int(continuous), "counting": "rank-local cumulative since process start"}
