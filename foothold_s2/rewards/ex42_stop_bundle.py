"""EX-42 stop-slot bundle (EX42_STOP_BUNDLE): three penalties on the stand command and a delay on the four-foot gain (lead 2026-11-23).
Off by default: only with EX42_STOP_BUNDLE=1. Off, nothing is registered, `ex39_four_foot_stop` keeps its own function, the command
term is not touched and the generator draws nothing more (this module has no draw at all).

Why: under the stand command the policy re-steps or stands with the feet staggered fore-aft / spread sideways; `ex39_four_foot_stop`
pays +0.1 for any four-foot contact, so a quick re-step that lands four feet again loses almost nothing.

Format (both optional except the switch):
    EX42_STOP_BUNDLE=1
    EX42_STOP_BUNDLE_PARAMS="stagger=-0.3,lateral=-0.3,load=-0.05,ff_delay=1.0"   (any subset; the rest keep DEFAULTS)
Weights are reward-manager weights (<= 0; reward = weight x value x dt), ff_delay in seconds (>= 0).

Active envs (all three penalties): the stand command of the stage runtime (`term.stand`, the stop slot: vx = vy = wz = 0 exactly, the
command is also checked to be exactly zero; never a 0.1 threshold) and not a sparse column (`ex42_hip_sparse.sparse_columns`: every column
that is not family A with a continuous kind or flat). Walking, turning, spinning, flag and sparse-column envs get exactly 0.

    ex42_stop_stagger  value = |x_FL - x_FR| + |x_RL - x_RR|                      (m)
    ex42_stop_lateral  value = sum over the four feet |y_foot - y_ref_foot|        (m)
    ex42_stop_load     value = 1 - min(Fz) / mean(Fz) over the four feet           (0 = equal load, 1 = a foot carries nothing)
    foot x, y: foot body origin minus root origin in the yaw frame (rotated by -heading_w; roll / pitch not removed, they move the
    four feet alike and cancel in the stagger difference). Fz: contact sensor net force z, clipped at 0; mean below 1e-6 N gives 1.
    y_ref: the foot y of the env's default joint pose (robot.data.default_joint_pos, the live config's pose), by the Go2 URDF hip / thigh
    offsets (hip at (+-0.1934, +-0.0465), thigh at +-0.0955 from the hip, thigh and calf 0.213 each); not the episode's first frame,
    because reset_joints_by_scale spreads the start pose (0.5 ~ 1.5 x default). Isaac Lab Go2 default (hip +-0.1, thigh 0.8 / 1.0,
    calf -1.5): |y_ref| = 0.1726 front, 0.1717 rear.
    ex39_four_foot_stop: its value x (stop_elapsed_s >= ff_delay - 1e-4). stop_elapsed_s is the command term's own record (a walk -> stand
    transition starts it at 0, it grows by dt every step under stand); the k-th reward step under stand sees k x dt, so with 1.0 s the gain
    starts at the 50th step (1e-4 absorbs the float32 sum of 0.02).

Lines: EX42_STOP_BUNDLE where=start (weights, delay, reference y), and rank-local counts since the start in every command_shares record
(key stop_bundle): stop-slot env-steps seen, steps where each penalty was nonzero, four-foot steps withheld / paid, stand starts and env
steps (stand starts per env per 20 s = stand_starts / (env_steps x dt / 20)), and the record-only front hip torque in the stop slot
(front_hip_abs_torque_mean_nm: mean over active stop env-steps of (|tau_FL_hip| + |tau_FR_hip|) / 2 from robot.data.applied_torque; no
reward weight, lead 13:11). Isaac Lab also logs each new term as Episode_Reward/ex42_stop_stagger, .../ex42_stop_lateral,
.../ex42_stop_load (RewardTermCfg terms of the reward manager). A term whose weight is 0 is not called by the reward
manager and counts nothing. Counts stay on the device until summary(). No Kit import at module level.

Weight table: `python -m foothold_s2.rewards.ex42_stop_bundle` (weight_table()).
"""
from __future__ import annotations

import math
import os

import torch

ENV_SWITCH = "EX42_STOP_BUNDLE"
PARAMS_ENV = "EX42_STOP_BUNDLE_PARAMS"
DEFAULTS = {"stagger": -0.3, "lateral": -0.3, "load": -0.05, "ff_delay": 1.0}
WEIGHT_KEYS = ("stagger", "lateral", "load")
TERMS = {"stagger": "ex42_stop_stagger", "lateral": "ex42_stop_lateral", "load": "ex42_stop_load"}
FOUR_FOOT = "ex39_four_foot_stop"
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
# Go2 URDF (go2_robot_sdk go2.urdf): FL_hip_joint origin (0.1934, 0.0465, 0), FL_thigh_joint (0, 0.0955, 0), calf and foot (0, 0, -0.213).
HIP_Y, THIGH_Y, LINK = 0.0465, 0.0955, 0.213
FF_EPS = 1e-4
_COUNT_KEYS = ("stop_steps", "stagger_nonzero", "lateral_nonzero", "load_nonzero", "ff_withheld", "ff_paid",
               "stand_starts", "env_steps")
_COUNTS: dict = {}
_SUMS: dict = {}
_STARTED = {"done": False}


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    if value != "1" and os.environ.get(PARAMS_ENV, "") != "":
        raise ValueError(f"{PARAMS_ENV} is set but {ENV_SWITCH} is not 1")
    return value == "1"


def params() -> dict:
    """DEFAULTS overridden by EX42_STOP_BUNDLE_PARAMS (comma list of key=value)."""
    out = dict(DEFAULTS)
    raw = os.environ.get(PARAMS_ENV, "")
    for item in (p.strip() for p in raw.split(",") if p.strip()):
        key, sep, val = item.partition("=")
        key = key.strip()
        if not sep or key not in DEFAULTS:
            raise ValueError(f"{PARAMS_ENV}: expected key=value with key in {sorted(DEFAULTS)} (got {item!r})")
        try:
            out[key] = float(val)
        except ValueError:
            raise ValueError(f"{PARAMS_ENV}: {key} must be a number (got {val!r})") from None
    for key in WEIGHT_KEYS:
        if not math.isfinite(out[key]) or out[key] > 0.0:
            raise ValueError(f"{PARAMS_ENV}: {key} is a penalty weight, finite and <= 0 (got {out[key]})")
    if not math.isfinite(out["ff_delay"]) or out["ff_delay"] < 0.0:
        raise ValueError(f"{PARAMS_ENV}: ff_delay must be finite and >= 0 (got {out['ff_delay']})")
    return out


# ------------------------------------------------------------------ values (pure tensors)

def stagger_value(x: torch.Tensor) -> torch.Tensor:
    """(N,) from (N, 4) yaw-frame foot x in FEET order."""
    return (x[:, 0] - x[:, 1]).abs() + (x[:, 2] - x[:, 3]).abs()


def lateral_value(y: torch.Tensor, y_ref: torch.Tensor) -> torch.Tensor:
    return (y - y_ref).abs().sum(dim=1)


def load_value(fz: torch.Tensor) -> torch.Tensor:
    f = fz.clamp_min(0.0)
    return 1.0 - f.min(dim=1).values / f.mean(dim=1).clamp_min(1e-6)


def reference_y(joint_names, default_joint_pos: torch.Tensor) -> torch.Tensor:
    """(N, 4) foot y of the default joint pose in the base frame (FEET order), from the Go2 URDF offsets."""
    names = list(joint_names)
    cols = []
    for leg in ("FL", "FR", "RL", "RR"):
        q = [default_joint_pos[:, names.index(f"{leg}_{j}_joint")] for j in ("hip", "thigh", "calf")]
        side = 1.0 if leg[1] == "L" else -1.0
        height = LINK * (torch.cos(q[1]) + torch.cos(q[1] + q[2]))          # foot below the thigh joint, in the hip frame
        cols.append(side * HIP_Y + side * THIGH_Y * torch.cos(q[0]) + height * torch.sin(q[0]))
    return torch.stack(cols, dim=1)


# ------------------------------------------------------------------ env access

def _count(key: str, value: torch.Tensor) -> None:
    if key not in _COUNTS:
        _COUNTS[key] = torch.zeros((), dtype=torch.long, device=value.device)
    _COUNTS[key] += value.sum().long() if value.dtype == torch.bool else value.long()


def _add(key: str, value: torch.Tensor) -> None:
    if key not in _SUMS:
        _SUMS[key] = torch.zeros((), dtype=torch.float64, device=value.device)
    _SUMS[key] += value.sum().double()


def front_hip_abs_torque(robot) -> torch.Tensor:
    """(N,) (|tau_FL_hip| + |tau_FR_hip|) / 2 from robot.data.applied_torque (record only)."""
    names = list(robot.joint_names)
    ids = [names.index("FL_hip_joint"), names.index("FR_hip_joint")]
    return robot.data.applied_torque[:, ids].abs().mean(dim=1)


def stop_mask(env, command_name: str) -> torch.Tensor:
    from foothold_s2.rewards.ex42_hip_sparse import sparse_envs

    term = env.command_manager.get_term(command_name)
    if getattr(term, "stage_runtime", None) is None:
        raise ValueError("EX42_STOP_BUNDLE needs the stage runtime's stand mask (term.stage_runtime)")
    command = env.command_manager.get_command(command_name)
    stop = term.stand.bool() & (command == 0).all(dim=1)
    return stop & ~sparse_envs(env).to(stop.device)


def foot_xy(env, asset_cfg):
    robot = env.scene[asset_cfg.name]
    rel = robot.data.body_pos_w[:, asset_cfg.body_ids, :2] - robot.data.root_pos_w[:, None, :2]
    if rel.shape[1] != 4:
        raise ValueError("EX42_STOP_BUNDLE needs the four foot bodies")
    yaw = robot.data.heading_w[:, None]
    c, s = torch.cos(yaw), torch.sin(yaw)
    return c * rel[..., 0] + s * rel[..., 1], -s * rel[..., 0] + c * rel[..., 1]


def ex42_stop_stagger(env, command_name, asset_cfg):
    stop = stop_mask(env, command_name)
    x, _ = foot_xy(env, asset_cfg)
    value = torch.where(stop, stagger_value(x), torch.zeros_like(x[:, 0]))
    term = env.command_manager.get_term(command_name)
    dt = float(getattr(getattr(env, "unwrapped", env), "step_dt", 0.02))
    elapsed = term.stop_elapsed_s
    _count("stop_steps", stop)
    _count("stagger_nonzero", value != 0)
    _count("stand_starts", term.stand.bool() & (elapsed > 0) & (elapsed < 1.5 * dt))
    _count("env_steps", torch.tensor(stop.shape[0], device=stop.device))
    tau = front_hip_abs_torque(env.scene[asset_cfg.name]).to(stop.device)
    _add("front_hip_abs_torque_nm", torch.where(stop, tau, torch.zeros_like(tau)))
    return value


def ex42_stop_lateral(env, command_name, asset_cfg):
    stop = stop_mask(env, command_name)
    raw = getattr(env, "unwrapped", env)
    ref = getattr(raw, "_ex42_stop_ref_y", None)
    robot = env.scene[asset_cfg.name]
    if ref is None:
        ref = reference_y(robot.joint_names, robot.data.default_joint_pos).to(stop.device)
        setattr(raw, "_ex42_stop_ref_y", ref)
    _, y = foot_xy(env, asset_cfg)
    value = torch.where(stop, lateral_value(y, ref), torch.zeros_like(y[:, 0]))
    _count("lateral_nonzero", value != 0)
    return value


def ex42_stop_load(env, command_name, sensor_cfg):
    stop = stop_mask(env, command_name)
    fz = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids, 2]
    if fz.shape[1] != 4:
        raise ValueError("EX42_STOP_BUNDLE load needs four foot bodies")
    value = torch.where(stop, load_value(fz), torch.zeros_like(fz[:, 0]))
    _count("load_nonzero", value != 0)
    return value


def wrap_four_foot(func, delay_s: float):
    """`ex39_four_foot_stop` pays only from ff_delay seconds after the walk -> stand transition (term.stop_elapsed_s)."""
    def four_foot_after_delay(env, command_name, **kwargs):
        value = func(env, command_name, **kwargs)
        term = env.command_manager.get_term(command_name)
        late = term.stop_elapsed_s.to(value.device) >= delay_s - FF_EPS
        out = value * late.to(value.dtype)
        _count("ff_withheld", (value != 0) & ~late)
        _count("ff_paid", out != 0)
        return out
    four_foot_after_delay.ex42_stop_bundle_delay = delay_s
    four_foot_after_delay.__wrapped__ = func
    return four_foot_after_delay


def register(env_cfg, term_cfg_class=None, entity_cfg_class=None) -> bool:
    """Before the env is built: add the three terms and delay the four-foot gain when the switch is on. True when registered."""
    if not enabled():
        return False
    p = params()
    four = getattr(env_cfg.rewards, FOUR_FOOT, None)
    if four is None:
        raise ValueError(f"{ENV_SWITCH}=1 but the env config has no {FOUR_FOOT} term")
    if getattr(four.func, "ex42_stop_bundle_delay", None) is not None:
        return False
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    if entity_cfg_class is None:
        from isaaclab.managers import SceneEntityCfg as entity_cfg_class

    def robot():
        return entity_cfg_class("robot", body_names=list(FEET), preserve_order=True)

    setattr(env_cfg.rewards, TERMS["stagger"], term_cfg_class(func=ex42_stop_stagger, weight=p["stagger"],
                                                              params={"command_name": "base_velocity", "asset_cfg": robot()}))
    setattr(env_cfg.rewards, TERMS["lateral"], term_cfg_class(func=ex42_stop_lateral, weight=p["lateral"],
                                                              params={"command_name": "base_velocity", "asset_cfg": robot()}))
    setattr(env_cfg.rewards, TERMS["load"], term_cfg_class(
        func=ex42_stop_load, weight=p["load"],
        params={"command_name": "base_velocity",
                "sensor_cfg": entity_cfg_class("contact_forces", body_names=list(FEET), preserve_order=True)}))
    four.func = wrap_four_foot(four.func, p["ff_delay"])
    print(f"EX42_STOP_BUNDLE where=start stagger={p['stagger']} lateral={p['lateral']} load={p['load']} "
          f"ff_delay_s={p['ff_delay']} active=stand_and_not_sparse y_ref=default_joint_pos_urdf", flush=True)
    _STARTED["done"] = True
    return True


def summary() -> dict | None:
    if not enabled():
        return None
    out = {k: int(_COUNTS[k].item()) if k in _COUNTS else 0 for k in _COUNT_KEYS}
    steps = out["stop_steps"]
    total = float(_SUMS["front_hip_abs_torque_nm"].item()) if "front_hip_abs_torque_nm" in _SUMS else 0.0
    out["front_hip_abs_torque_mean_nm"] = total / steps if steps else None
    out["counting"] = "rank-local since process start"
    return out


# ------------------------------------------------------------------ weight table

def weight_table(stagger_m=0.05, lateral_m=0.05, load_imbalance=0.3, window_s=4.0, dt=0.02,
                 ff_weight=0.1, restep_s=0.3, weights=None) -> dict:
    """Weight at which a deviation held for the whole stop window costs as much as the four-foot gain a re-step loses
    (ff_weight x restep_s). Isaac Lab reward = weight x value x dt per step, so the window total is weight x value x window_s."""
    weights = dict(DEFAULTS if weights is None else weights)
    lost = ff_weight * restep_s
    rows = {}
    for key, value in (("stagger", stagger_m), ("lateral", lateral_m), ("load", load_imbalance)):
        threshold = lost / (value * window_s)
        rows[key] = {"value": value, "threshold_abs_weight": threshold,
                     "per_step_at_threshold": threshold * value * dt,
                     "weight": weights[key], "per_step_at_weight": abs(weights[key]) * value * dt,
                     "window_total_at_weight": abs(weights[key]) * value * window_s,
                     "beats_restep": abs(weights[key]) * value * window_s > lost}
    return {"four_foot_lost_by_restep": lost, "window_s": window_s, "dt": dt, "steps": round(window_s / dt), "rows": rows}


if __name__ == "__main__":
    table = weight_table()
    print(f"four_foot gain lost by a re-step = 0.1 x 0.3 s = {table['four_foot_lost_by_restep']:.4f} "
          f"(window {table['window_s']} s, dt {table['dt']} s, {table['steps']} steps)")
    for key, row in table["rows"].items():
        print(f"{key:8s} value {row['value']:.3f}  |w| threshold {row['threshold_abs_weight']:.4f}  "
              f"per-step at threshold {row['per_step_at_threshold']:.2e}  weight {row['weight']}  "
              f"per-step {row['per_step_at_weight']:.2e}  window total {row['window_total_at_weight']:.4f}  beats={row['beats_restep']}")
