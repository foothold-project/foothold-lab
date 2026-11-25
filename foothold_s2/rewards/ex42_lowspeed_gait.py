"""F1 / F2 common base (lead 2026-11-25 21:03 / 21:04, planner M136): walking low-speed stability. Off by default.

    EX42_LOWSPEED_GAIT=1
    EX42_LOWSPEED_GAIT_BAND="0.05,0.07"   (lo,hi only; may not be combined with lo/hi cells in _PARAMS)
    EX42_LOWSPEED_GAIT_PARAMS="w_ang=-1.1,w_band=-40,v_max=0.5,side_turn_wz=0.5,lo=0.05,hi=0.07,min_swing_steps=3,band_max_level=1"

(a) ex42_lowspeed_angvel   value = wx^2 + wy^2 (root_ang_vel_b roll, pitch)
    active: moving (not the stand slot) and (|v_xy cmd| <= v_max or side command |vy| > |vx| or turn |wz| >= side_turn_wz)
            and a continuous or flat column (not ex42_hip_sparse.sparse_envs, the basic_hip_pos_penalty_l1 column split).
    Weight -1.1: the target is 5 % of the tracking reward at the candidate's low-speed roll rms 0.31 rad/s.
            E2b mainline (012130) m500 per-second Episode_Reward: track_lin_vel 1.394 + track_ang_vel 0.722 = 2.116;
            5 % = 0.106; 0.106 / 0.31^2 = 1.10. Pitch rate adds on top, so the realized share is at least 5 %.
(b) ex42_lowspeed_lift_band  value = sum over the four feet, at a touchdown that ends a swing of >= min_swing_steps steps,
            of relu(lo - lift) + relu(lift - hi); 0 inside the band (not a reward for height).
    lift = (max - min) over the swing of zf = -(0.213 cos(thigh) + 0.213 cos(thigh + calf)), the same forward kinematics as the
            judgment table (planner night_table4.py [2], thigh and calf 0.213 m; hip roll ignored as there). Swing = foot contact
            force z <= 1 N. Same command mask as (a) on continuous columns (not sparse) at terrain level <= band_max_level (1):
            nearly flat ground. lead 21:39: the F plan opens no flat column (flat exposure 0: A/flat 48 49 and C/flat 63), so the
            first form (flat columns only) scored 0 touchdowns; levels 0~1 of the continuous columns hold 382 of 3072 envs.
    Weight -40: touchdown steps are sparse. Assumed 2 touchdowns / s per foot and a 0.03 m excess on the two front feet
            (candidate 0.095 / 0.085 m): mean value per 0.02 s step 2 x 2 x 0.03 x 0.02 = 0.0024; 0.106 / 0.0024 = 44 -> 40.
            The touchdown rate is logged (gait_period_s) to check the assumption.
Monitor line EX42_GAIT_MONITOR (rank 0, first call then every MONITOR_EVERY steps; lead 21:04 item 4): per-swing lift and the
judgment-style window (max - min) lift per foot, roll / pitch rms, foot slip (foot xy speed in contact), action rate, joint power,
gait period, on the (a) mask; the counts also go to each command_shares record (key lowspeed_gait). No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

ENV_SWITCH = "EX42_LOWSPEED_GAIT"
PARAMS_ENV = "EX42_LOWSPEED_GAIT_PARAMS"
BAND_ENV = "EX42_LOWSPEED_GAIT_BAND"   # "lo,hi" in m (lead 21:41: the band is set after planner measures the per-swing lift)
DEFAULTS = {"w_ang": -1.1, "w_band": -40.0, "v_max": 0.5, "side_turn_wz": 0.5, "lo": 0.05, "hi": 0.07,
            "min_swing_steps": 3.0, "band_max_level": 1.0}
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
LEGS = ("FL", "FR", "RL", "RR")
LINK = 0.213
CONTACT_N = 1.0
MONITOR_EVERY = 2400
_SUMS: dict[str, torch.Tensor] = {}


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    if value != "1" and (os.environ.get(PARAMS_ENV, "") or os.environ.get(BAND_ENV, "")):
        raise ValueError(f"{PARAMS_ENV} or {BAND_ENV} is set but {ENV_SWITCH} is not 1")
    return value == "1"


def params() -> dict:
    out = dict(DEFAULTS)
    for item in filter(None, (part.strip() for part in os.environ.get(PARAMS_ENV, "").split(","))):
        key, sep, raw = item.partition("=")
        key = key.strip()
        if not sep or key not in out:
            raise ValueError(f"{PARAMS_ENV} unknown or malformed cell {item!r}")
        try:
            out[key] = float(raw)
        except ValueError:
            raise ValueError(f"{PARAMS_ENV} invalid number {item!r}") from None
    band = os.environ.get(BAND_ENV, "").strip()
    if band:
        cells = [c.strip() for c in band.split(",")]
        if len(cells) != 2 or any(f"{k}=" in os.environ.get(PARAMS_ENV, "") for k in ("lo", "hi")):
            raise ValueError(f"{BAND_ENV} needs exactly 'lo,hi' and no lo/hi cell in {PARAMS_ENV}")
        try:
            out["lo"], out["hi"] = float(cells[0]), float(cells[1])
        except ValueError:
            raise ValueError(f"{BAND_ENV} invalid number {band!r}") from None
    if (any(not math.isfinite(v) for v in out.values()) or out["w_ang"] >= 0 or out["w_band"] >= 0
            or out["v_max"] <= 0 or out["side_turn_wz"] <= 0 or not 0 < out["lo"] < out["hi"] < 0.3
            or out["min_swing_steps"] < 1 or not 0 <= out["band_max_level"] <= 9):
        raise ValueError(f"{PARAMS_ENV} needs weights < 0, v_max and side_turn_wz > 0, 0 < lo < hi < 0.3, min_swing_steps >= 1")
    return out


def foot_z(thigh: torch.Tensor, calf: torch.Tensor) -> torch.Tensor:
    """Judgment-table forward kinematics: foot height below the hip in the leg plane (m, negative)."""
    return -(LINK * torch.cos(thigh) + LINK * torch.cos(thigh + calf))


def command_mask(command: torch.Tensor, stand: torch.Tensor, v_max: float, side_turn_wz: float) -> torch.Tensor:
    vx, vy, wz = command[:, 0], command[:, 1], command[:, 2]
    low = torch.linalg.vector_norm(command[:, :2], dim=1) <= v_max
    side = vy.abs() > vx.abs()
    turn = wz.abs() >= side_turn_wz
    return ~stand & (low | side | turn)


def band_value(lift: torch.Tensor, lo: float, hi: float) -> torch.Tensor:
    return (lo - lift).clamp_min(0.0) + (lift - hi).clamp_min(0.0)


class SwingTracker:
    """Per env and foot: contact, swing length and the zf range of the current swing; window range for the monitor."""

    def __init__(self, num_envs: int, device):
        shape = (num_envs, 4)
        self.contact = torch.ones(shape, dtype=torch.bool, device=device)
        self.swing_steps = torch.zeros(shape, device=device)
        self.swing_max = torch.zeros(shape, device=device)
        self.swing_min = torch.zeros(shape, device=device)
        self.window_max = torch.full(shape, -1e9, device=device)
        self.window_min = torch.full(shape, 1e9, device=device)

    def step(self, zf: torch.Tensor, contact: torch.Tensor, fresh: torch.Tensor, min_steps: float):
        """Returns (touchdown [N, 4] bool that ends a long enough swing, lift [N, 4] of that swing)."""
        if fresh.any():
            self.contact[fresh] = True
            self.swing_steps[fresh] = 0
            self.window_max[fresh] = -1e9
            self.window_min[fresh] = 1e9
        liftoff = self.contact & ~contact
        self.swing_max = torch.where(liftoff, zf, self.swing_max)
        self.swing_min = torch.where(liftoff, zf, self.swing_min)
        air = ~contact
        self.swing_max = torch.where(air, torch.maximum(self.swing_max, zf), self.swing_max)
        self.swing_min = torch.where(air, torch.minimum(self.swing_min, zf), self.swing_min)
        self.swing_steps = torch.where(air, self.swing_steps + 1, self.swing_steps)
        touchdown = ~self.contact & contact & (self.swing_steps >= min_steps)
        lift = self.swing_max - self.swing_min
        self.swing_steps = torch.where(contact, torch.zeros_like(self.swing_steps), self.swing_steps)
        self.contact = contact.clone()
        self.window_max = torch.maximum(self.window_max, zf)
        self.window_min = torch.minimum(self.window_min, zf)
        return touchdown, lift


def _add(key: str, value: torch.Tensor) -> None:
    if key not in _SUMS:
        _SUMS[key] = torch.zeros(value.shape[1:] if value.ndim > 1 else (), device=value.device, dtype=torch.float64)
    _SUMS[key] += value.double().sum(dim=0)


def _masks(env, command_name, p):
    from foothold_s2.rewards.ex42_hip_sparse import sparse_envs

    raw = getattr(env, "unwrapped", env)
    term = env.command_manager.get_term(command_name)
    command = env.command_manager.get_command(command_name)
    cmd = command_mask(command, term.stand.bool(), p["v_max"], p["side_turn_wz"])
    continuous = ~sparse_envs(env).to(cmd.device)
    low_level = env.scene.terrain.terrain_levels.to(cmd.device) <= p["band_max_level"]
    return cmd & continuous, cmd & continuous & low_level


def ex42_lowspeed_angvel(env, command_name, asset_cfg, p):
    active, _ = _masks(env, command_name, p)
    w = env.scene[asset_cfg.name].data.root_ang_vel_b[:, :2]
    value = w.square().sum(dim=1)
    out = torch.where(active, value, torch.zeros_like(value))
    _add("ang_active_steps", active)
    _add("roll_sq_sum", torch.where(active, w[:, 0].square(), torch.zeros_like(value)))
    _add("pitch_sq_sum", torch.where(active, w[:, 1].square(), torch.zeros_like(value)))
    return out


def ex42_lowspeed_lift_band(env, command_name, asset_cfg, sensor_cfg, p):
    raw = getattr(env, "unwrapped", env)
    robot = env.scene[asset_cfg.name]
    active, flat_active = _masks(env, command_name, p)
    ids = getattr(raw, "_ex42_lowspeed_joint_ids", None)
    if ids is None:
        names = list(robot.joint_names)
        ids = (torch.tensor([names.index(f"{leg}_thigh_joint") for leg in LEGS]),
               torch.tensor([names.index(f"{leg}_calf_joint") for leg in LEGS]))
        raw._ex42_lowspeed_joint_ids = ids
    q = robot.data.joint_pos
    zf = foot_z(q[:, ids[0]], q[:, ids[1]])
    contact = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids, 2] > CONTACT_N
    tracker = getattr(raw, "_ex42_swing_tracker", None)
    if tracker is None:
        tracker = raw._ex42_swing_tracker = SwingTracker(zf.shape[0], zf.device)
    fresh = raw.episode_length_buf.to(zf.device) <= 1
    touchdown, lift = tracker.step(zf, contact, fresh, p["min_swing_steps"])
    scored = touchdown & flat_active[:, None]
    value = torch.where(scored, band_value(lift, p["lo"], p["hi"]), torch.zeros_like(lift)).sum(dim=1)
    _monitor(env, robot, sensor_cfg, contact, touchdown, lift, active, flat_active, tracker)
    return value


def _monitor(env, robot, sensor_cfg, contact, touchdown, lift, active, flat_active, tracker):
    raw = getattr(env, "unwrapped", env)
    td = touchdown & active[:, None]
    _add("touchdowns", td.float())
    _add("lift_sum", torch.where(td, lift, torch.zeros_like(lift)))
    _add("band_scored", (touchdown & flat_active[:, None]).float())
    _add("band_env_steps", flat_active)
    _add("mon_steps", active)
    a = active.float()
    feet = getattr(raw, "_ex42_lowspeed_feet", None)
    if feet is None:
        names = list(robot.body_names)
        feet = raw._ex42_lowspeed_feet = [names.index(n) for n in FEET]
    slip = robot.data.body_lin_vel_w[:, feet, :2].norm(dim=-1) * contact.float()
    _add("slip_sum", slip.sum(dim=1) * a)
    _add("contact_sum", contact.float().sum(dim=1) * a)
    manager = getattr(raw, "action_manager", None)
    if manager is not None and hasattr(manager, "prev_action"):
        _add("action_rate_sum", (manager.action - manager.prev_action).square().sum(dim=1) * a)
    if hasattr(robot.data, "applied_torque"):
        _add("power_sum", (robot.data.applied_torque * robot.data.joint_vel).abs().sum(dim=1) * a)
    raw._ex42_lowspeed_calls = getattr(raw, "_ex42_lowspeed_calls", 0) + 1
    if raw._ex42_lowspeed_calls in (1, 50) or raw._ex42_lowspeed_calls % MONITOR_EVERY == 0:
        window = (tracker.window_max - tracker.window_min)[active & (tracker.window_max > -1e8).all(dim=1)]
        row = summary()
        if row is not None and int(os.environ.get("RANK", "0") or 0) == 0:
            print("EX42_GAIT_MONITOR calls=%d %s window_lift_m=%s" % (
                raw._ex42_lowspeed_calls, " ".join(f"{k}={v}" for k, v in row.items() if k != "counting"),
                ",".join("%.4f" % float(x) for x in window.mean(dim=0)) if window.numel() else "none"), flush=True)


def register(env_cfg, term_cfg_class=None, entity_cfg_class=None) -> bool:
    if not enabled():
        return False
    p = params()
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    if entity_cfg_class is None:
        from isaaclab.managers import SceneEntityCfg as entity_cfg_class
    rewards = env_cfg.rewards
    for name in ("ex42_lowspeed_angvel", "ex42_lowspeed_lift_band"):
        if getattr(rewards, name, None) is not None:
            raise ValueError(f"{ENV_SWITCH} registered twice ({name})")
    robot = entity_cfg_class("robot")
    rewards.ex42_lowspeed_angvel = term_cfg_class(
        func=ex42_lowspeed_angvel, weight=p["w_ang"],
        params={"command_name": "base_velocity", "asset_cfg": robot, "p": dict(p)})
    rewards.ex42_lowspeed_lift_band = term_cfg_class(
        func=ex42_lowspeed_lift_band, weight=p["w_band"],
        params={"command_name": "base_velocity", "asset_cfg": robot, "p": dict(p),
                "sensor_cfg": entity_cfg_class("contact_forces", body_names=list(FEET), preserve_order=True)})
    print("EX42_LOWSPEED_GAIT where=start w_ang=%g w_band=%g v_max=%g side_turn_wz=%g band=[%g,%g] min_swing_steps=%g "
          "ang_mask=moving_lowspeed_or_side_or_turn_and_not_sparse band_mask=same_and_continuous_level_le_%g lift=fk_thigh_calf_0.213_swing_range"
          % (p["w_ang"], p["w_band"], p["v_max"], p["side_turn_wz"], p["lo"], p["hi"], p["min_swing_steps"], p["band_max_level"]), flush=True)
    return True


def summary() -> dict | None:
    if not enabled():
        return None
    s = {k: v.detach().cpu() for k, v in _SUMS.items()}
    steps = float(s.get("mon_steps", torch.zeros(())).sum())
    ang = float(s.get("ang_active_steps", torch.zeros(())).sum())
    td = s.get("touchdowns")
    out = {"counting": "rank-local cumulative since process start", "active_env_steps": int(steps)}
    out["roll_rms"] = round(math.sqrt(float(s["roll_sq_sum"]) / ang), 5) if ang else None
    out["pitch_rms"] = round(math.sqrt(float(s["pitch_sq_sum"]) / ang), 5) if ang else None
    if td is not None and steps:
        out["swing_lift_m"] = [round(float(l / max(float(t), 1.0)), 5) for l, t in zip(s["lift_sum"], td)]
        rate = float(td.sum()) / 4.0 / steps / 0.02          # touchdowns per foot per second (policy dt 0.02 s)
        out["touchdowns_per_foot_s"] = round(rate, 4)
        out["gait_period_s"] = round(1.0 / rate, 4) if rate else None
        out["band_scored_touchdowns"] = int(float(s["band_scored"].sum()))
        out["band_env_steps"] = int(float(s.get("band_env_steps", torch.zeros(())).sum()))
        contact = float(s.get("contact_sum", torch.zeros(())))
        out["foot_slip_mps"] = round(float(s["slip_sum"]) / contact, 5) if contact else None
        if "action_rate_sum" in s:
            out["action_rate"] = round(float(s["action_rate_sum"]) / steps, 5)
        if "power_sum" in s:
            out["joint_power_w"] = round(float(s["power_sum"]) / steps, 3)
    return out
