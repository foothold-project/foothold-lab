"""F1 stand penalties (lead 2026-11-25 20:20 / 20:23, planner F1F2-DESIGN-1125 section 2): body tilt and per-leg
contact force difference, only in the stand (command 0) slot. Off by default; off registers nothing.

    EX42_STAND_TILT=1          EX42_STAND_TILT_W (reward-manager weight <= 0, default -1.0)
        value = gx^2 + gy^2 of projected_gravity_b (the flat_orientation_l2 quantity), stand slot only
    EX42_LOAD_BALANCE=1        EX42_LOAD_BALANCE_W (weight <= 0, default -0.5)
        value = (|Fz_FL - Fz_FR| + |Fz_RL - Fz_RR|) / (m g), stand slot only
        Fz: contact sensor net force z clipped at 0; m: the env's realized robot mass (_ex40_total_mass_kg).
        Left against right per leg pair: a front load moves weight forward, so front-rear equality is not asked.
    EX42_STAND_PENALTY_DELAY_S (default 1.0): both terms are 0 for the first delay seconds after a stand start
        (the same 1 s as the stop window / four-foot delay, so the transition step is not punished).

Active envs: ex42_stop_bundle.stop_mask (stand slot, command exactly 0, not a sparse column) and stop_elapsed_s >= delay.
Lines: EX42_STAND_TILT where=start / EX42_LOAD_BALANCE where=start at registration, one `first_active` line the first time a
term sees an active env, and rank-local counts in each command_shares record (key stand_tilt_load). No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

TILT, LOAD = "EX42_STAND_TILT", "EX42_LOAD_BALANCE"
DELAY_ENV = "EX42_STAND_PENALTY_DELAY_S"
DEFAULT_W = {TILT: -1.0, LOAD: -0.5}
TERMS = {TILT: "ex42_stand_tilt", LOAD: "ex42_load_balance"}
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
G = 9.81
EPS = 1e-4
_SUMS: dict[str, torch.Tensor] = {}
_FIRST: set[str] = set()


def enabled(switch: str) -> bool:
    value = os.environ.get(switch, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{switch} must be 0 or 1 (got {value!r})")
    if value != "1" and os.environ.get(switch + "_W", ""):
        raise ValueError(f"{switch}_W is set but {switch} is not 1")
    return value == "1"


def weight(switch: str) -> float:
    raw = os.environ.get(switch + "_W", "")
    try:
        value = float(raw) if raw else DEFAULT_W[switch]
    except ValueError:
        raise ValueError(f"{switch}_W must be a number (got {raw!r})") from None
    if not math.isfinite(value) or value >= 0:
        raise ValueError(f"{switch}_W must be finite and < 0 (got {value})")
    return value


def delay_s() -> float:
    raw = os.environ.get(DELAY_ENV, "")
    try:
        value = float(raw) if raw else 1.0
    except ValueError:
        raise ValueError(f"{DELAY_ENV} must be a number (got {raw!r})") from None
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{DELAY_ENV} must be finite and >= 0")
    return value


def tilt_value(projected_gravity_b: torch.Tensor) -> torch.Tensor:
    return projected_gravity_b[:, :2].square().sum(dim=1)


def load_value(fz: torch.Tensor, mass_kg: torch.Tensor) -> torch.Tensor:
    """fz [N, 4] in FL FR RL RR order; mass [N] > 0."""
    if fz.ndim != 2 or fz.shape[1] != 4 or mass_kg.shape != fz.shape[:1]:
        raise ValueError("EX42_LOAD_BALANCE needs four foot forces and one mass per env")
    f = fz.clamp_min(0.0)
    return ((f[:, 0] - f[:, 1]).abs() + (f[:, 2] - f[:, 3]).abs()) / (mass_kg * G)


def active_mask(env, command_name: str, delay: float) -> torch.Tensor:
    from foothold_s2.rewards.ex42_stop_bundle import stop_mask

    term = env.command_manager.get_term(command_name)
    if not hasattr(term, "stop_elapsed_s"):
        raise ValueError("EX-42 stand penalties need the command stop clock (stop_elapsed_s)")
    return stop_mask(env, command_name) & (term.stop_elapsed_s >= delay - EPS)


def _add(key: str, value: torch.Tensor) -> None:
    if key not in _SUMS:
        _SUMS[key] = torch.zeros((), device=value.device, dtype=torch.float64)
    _SUMS[key] += value.double().sum()


def _first_line(name: str, active: torch.Tensor, value: torch.Tensor) -> None:
    if name in _FIRST or int(os.environ.get("RANK", "0") or 0) != 0:
        return
    n = int(active.sum())
    if n:
        _FIRST.add(name)
        print(f"{name.upper()} first_active envs={n} value_mean={float(value[active].mean()):.6g}", flush=True)


def ex42_stand_tilt(env, command_name, asset_cfg, delay):
    active = active_mask(env, command_name, delay)
    value = tilt_value(env.scene[asset_cfg.name].data.projected_gravity_b)
    out = torch.where(active, value, torch.zeros_like(value))
    _add("tilt_active_steps", active)
    _add("tilt_value_sum", out)
    _first_line("ex42_stand_tilt", active, value)
    return out


def ex42_load_balance(env, command_name, sensor_cfg, delay):
    active = active_mask(env, command_name, delay)
    raw = getattr(env, "unwrapped", env)
    mass = getattr(raw, "_ex40_total_mass_kg", None)
    if mass is None:
        raise ValueError("EX42_LOAD_BALANCE needs the realized robot mass (_ex40_total_mass_kg)")
    fz = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids, 2]
    value = load_value(fz, mass.to(fz.device))
    out = torch.where(active, value, torch.zeros_like(value))
    _add("load_active_steps", active)
    _add("load_value_sum", out)
    _first_line("ex42_load_balance", active, value)
    return out


def register(env_cfg, term_cfg_class=None, entity_cfg_class=None) -> list[str]:
    on = [switch for switch in (TILT, LOAD) if enabled(switch)]
    if not on:
        return []
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    if entity_cfg_class is None:
        from isaaclab.managers import SceneEntityCfg as entity_cfg_class
    delay = delay_s()
    rewards = env_cfg.rewards
    for switch in on:
        name = TERMS[switch]
        if getattr(rewards, name, None) is not None:
            raise ValueError(f"{switch} registered twice ({name})")
        if switch == TILT:
            params = {"command_name": "base_velocity", "asset_cfg": entity_cfg_class("robot"), "delay": delay}
            func = ex42_stand_tilt
        else:
            params = {"command_name": "base_velocity", "delay": delay,
                      "sensor_cfg": entity_cfg_class("contact_forces", body_names=list(FEET), preserve_order=True)}
            func = ex42_load_balance
        setattr(rewards, name, term_cfg_class(func=func, weight=weight(switch), params=params))
        print(f"{switch} where=start term={name} w={weight(switch):g} delay_s={delay:g} "
              f"mask=stop_mask_stand_slot_not_sparse", flush=True)
    return on


def summary() -> dict | None:
    if not (enabled(TILT) or enabled(LOAD)):
        return None
    values = {key: float(value.item()) for key, value in _SUMS.items()}
    out = {"counting": "rank-local cumulative since process start"}
    for key in ("tilt", "load"):
        steps = values.get(f"{key}_active_steps", 0.0)
        out[f"{key}_active_env_steps"] = int(steps)
        out[f"{key}_value_mean"] = values.get(f"{key}_value_sum", 0.0) / steps if steps else None
    return out
