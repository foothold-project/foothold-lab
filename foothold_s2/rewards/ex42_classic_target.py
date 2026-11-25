"""Classic target terms (lead 2026-11-26 00:26, planner 00:25 real gait table). Off by default.

    EX42_CLASSIC_TARGET=1
    EX42_CLASSIC_TARGET_PARAMS="w_hip=-150,w_pitch=-0.9,w_freq=-60,hip_target=0.05,step_hz=1.4,v_max=0.5,cmd_min=0.05,band_max_level=1,min_swing_steps=3"

planner 00:25 found three cells where the candidate differs from the real Go2 Classic gait:
front hip side-to-side range 0.13 vs 0.05 rad, pitch rate rms 0.266 vs 0.138 rad/s, steps per foot 1.6 vs 1.4 per second
(Classic is 1.4 at every speed). Each term below aims at one cell. The policy input, output and network are unchanged
(reward terms only).

Mask (all three): moving (not the stand slot), |v_xy cmd| <= v_max, command not zero (|v_xy| or |wz| >= cmd_min),
continuous column (not ex42_hip_sparse.sparse_envs) at terrain level <= band_max_level: the near-flat low-speed rows.

(1) ex42_classic_hip_range  at a touchdown of a front foot (FL, FR) that ends a swing of >= min_swing_steps steps:
        relu(range - hip_target)^2, range = (max - min) of that leg's hip joint angle over the whole cycle since its
        previous touchdown (same window idea as the judgment table hip range). Only cycles that started after the
        episode reset count.
(2) ex42_classic_pitch      wy^2 (root_ang_vel_b pitch) every step.
(3) ex42_classic_step_freq  at a touchdown of any foot that closes a full cycle: (T - 1/step_hz)^2, T = seconds since the
        previous touchdown of the same foot (policy dt 0.02 s); cycles longer than 2 s are not scored (stops, stumbles).

Default weights, about 3 % each of the E2b mainline tracking reward 2.116 per second (012130 m500), 9 % together; reward
per second = weight x mean value per 0.02 s step:
    pitch: 0.266^2 = 0.0708 per step -> 0.063 / 0.0708 = 0.9.
    hip:   2 front feet x 1.6 touchdowns/s x 0.02 s x (0.13 - 0.05)^2 = 0.00041 per step -> 0.063 / 0.00041 = 154 -> 150.
    freq:  4 feet x 1.6/s x 0.02 s x (0.625 - 0.714)^2 = 0.00101 per step -> 0.063 / 0.00101 = 62 -> 60.
planner sets the final weights. Note: EX42_LOWSPEED_GAIT (a) already penalises wx^2 + wy^2; if both are on, pitch is counted
twice; lead 00:32 decided w_pitch=0 for that case (the pitch term is then not registered; the monitor still
reports pitch_rms on the mask). Monitor line EX42_CLASSIC_MON (rank 0, calls 1 and 50 then every MONITOR_EVERY steps) reports the three
cells with the judgment definitions on the mask; the counts also go to each command_shares record (key classic_target).
No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

ENV_SWITCH = "EX42_CLASSIC_TARGET"
PARAMS_ENV = "EX42_CLASSIC_TARGET_PARAMS"
DEFAULTS = {"w_hip": -150.0, "w_pitch": -0.9, "w_freq": -60.0, "hip_target": 0.05, "step_hz": 1.4, "v_max": 0.5,
            "cmd_min": 0.05, "band_max_level": 1.0, "min_swing_steps": 3.0}
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
LEGS = ("FL", "FR", "RL", "RR")
FRONT = torch.tensor([True, True, False, False])
CONTACT_N = 1.0
DT = 0.02
MAX_CYCLE_S = 2.0
MONITOR_EVERY = 240
_SUMS: dict[str, torch.Tensor] = {}


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    if value != "1" and os.environ.get(PARAMS_ENV, ""):
        raise ValueError(f"{PARAMS_ENV} is set but {ENV_SWITCH} is not 1")
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
    if (any(not math.isfinite(v) for v in out.values()) or out["w_hip"] >= 0 or out["w_pitch"] > 0 or out["w_freq"] >= 0
            or not 0 < out["hip_target"] < 0.5 or not 0.3 <= out["step_hz"] <= 5 or out["v_max"] <= 0
            or out["cmd_min"] < 0 or not 0 <= out["band_max_level"] <= 9 or out["min_swing_steps"] < 1):
        raise ValueError(f"{PARAMS_ENV} needs w_hip, w_freq < 0 and w_pitch <= 0 (0 = pitch term not registered), 0 < hip_target < 0.5, 0.3 <= step_hz <= 5, v_max > 0, cmd_min >= 0")
    return out


def command_mask(command: torch.Tensor, stand: torch.Tensor, v_max: float, cmd_min: float) -> torch.Tensor:
    speed = torch.linalg.vector_norm(command[:, :2], dim=1)
    nonzero = (speed >= cmd_min) | (command[:, 2].abs() >= cmd_min)
    return ~stand & (speed <= v_max) & nonzero


class CycleTracker:
    """Per env and foot: contact, swing length, steps since the previous touchdown and the hip range over that cycle."""

    def __init__(self, num_envs: int, device):
        shape = (num_envs, 4)
        self.contact = torch.ones(shape, dtype=torch.bool, device=device)
        self.swing_steps = torch.zeros(shape, device=device)
        self.cycle_steps = torch.zeros(shape, device=device)
        self.started = torch.zeros(shape, dtype=torch.bool, device=device)   # a touchdown seen since the episode reset
        self.hip_max = torch.zeros(shape, device=device)
        self.hip_min = torch.zeros(shape, device=device)

    def step(self, hip: torch.Tensor, contact: torch.Tensor, fresh: torch.Tensor, min_steps: float):
        """Returns (cycle_done [N, 4] bool: a touchdown that ends a long enough swing and closes a full cycle,
        cycle_s [N, 4] seconds of that cycle, hip_range [N, 4] of that cycle)."""
        if fresh.any():
            self.contact[fresh] = True
            self.swing_steps[fresh] = 0
            self.cycle_steps[fresh] = 0
            self.started[fresh] = False
            self.hip_max[fresh] = hip[fresh]
            self.hip_min[fresh] = hip[fresh]
        self.cycle_steps = self.cycle_steps + 1
        self.hip_max = torch.maximum(self.hip_max, hip)
        self.hip_min = torch.minimum(self.hip_min, hip)
        air = ~contact
        self.swing_steps = torch.where(air, self.swing_steps + 1, self.swing_steps)
        touchdown = ~self.contact & contact & (self.swing_steps >= min_steps)
        done = touchdown & self.started
        cycle_s = self.cycle_steps * DT
        hip_range = self.hip_max - self.hip_min
        self.started = self.started | touchdown
        self.cycle_steps = torch.where(touchdown, torch.zeros_like(self.cycle_steps), self.cycle_steps)
        self.hip_max = torch.where(touchdown, hip, self.hip_max)
        self.hip_min = torch.where(touchdown, hip, self.hip_min)
        self.swing_steps = torch.where(contact, torch.zeros_like(self.swing_steps), self.swing_steps)
        self.contact = contact.clone()
        return done, cycle_s, hip_range


def hip_value(done, hip_range, target):
    front = FRONT.to(done.device)[None, :]
    v = (hip_range - target).clamp_min(0.0).square()
    return torch.where(done & front, v, torch.zeros_like(v)).sum(dim=1)


def freq_value(done, cycle_s, step_hz):
    ok = done & (cycle_s <= MAX_CYCLE_S)
    v = (cycle_s - 1.0 / step_hz).square()
    return torch.where(ok, v, torch.zeros_like(v)).sum(dim=1)


def _add(key: str, value: torch.Tensor) -> None:
    if key not in _SUMS:
        _SUMS[key] = torch.zeros(value.shape[1:] if value.ndim > 1 else (), device=value.device, dtype=torch.float64)
    _SUMS[key] += value.double().sum(dim=0)


def _mask(env, command_name, p):
    from foothold_s2.rewards.ex42_hip_sparse import sparse_envs

    term = env.command_manager.get_term(command_name)
    command = env.command_manager.get_command(command_name)
    cmd = command_mask(command, term.stand.bool(), p["v_max"], p["cmd_min"])
    continuous = ~sparse_envs(env).to(cmd.device)
    low_level = env.scene.terrain.terrain_levels.to(cmd.device) <= p["band_max_level"]
    return cmd & continuous & low_level


def _update(env, asset_cfg, sensor_cfg, command_name, p):
    """Steps the cycle tracker once per env step (the three terms share it); returns the cached result."""
    raw = getattr(env, "unwrapped", env)
    step_id = int(getattr(raw, "common_step_counter", -1))
    cache = getattr(raw, "_ex42_ct_cache", None)
    if cache is not None and cache[0] == step_id:
        return cache[1]
    robot = env.scene[asset_cfg.name]
    ids = getattr(raw, "_ex42_ct_hip_ids", None)
    if ids is None:
        names = list(robot.joint_names)
        ids = raw._ex42_ct_hip_ids = torch.tensor([names.index(f"{leg}_hip_joint") for leg in LEGS])
    hip = robot.data.joint_pos[:, ids.to(robot.data.joint_pos.device)]
    contact = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids, 2] > CONTACT_N
    tracker = getattr(raw, "_ex42_ct_tracker", None)
    if tracker is None:
        tracker = raw._ex42_ct_tracker = CycleTracker(hip.shape[0], hip.device)
    fresh = raw.episode_length_buf.to(hip.device) <= 1
    done, cycle_s, hip_range = tracker.step(hip, contact, fresh, p["min_swing_steps"])
    active = _mask(env, command_name, p)
    done = done & active[:, None]
    w = robot.data.root_ang_vel_b[:, 1]
    out = {"active": active, "done": done, "cycle_s": cycle_s, "hip_range": hip_range, "pitch_sq": w.square()}
    raw._ex42_ct_cache = (step_id, out)
    _monitor(raw, out, p)
    return out


def ex42_classic_hip_range(env, command_name, asset_cfg, sensor_cfg, p):
    r = _update(env, asset_cfg, sensor_cfg, command_name, p)
    return hip_value(r["done"], r["hip_range"], p["hip_target"])


def ex42_classic_pitch(env, command_name, asset_cfg, sensor_cfg, p):
    r = _update(env, asset_cfg, sensor_cfg, command_name, p)
    return torch.where(r["active"], r["pitch_sq"], torch.zeros_like(r["pitch_sq"]))


def ex42_classic_step_freq(env, command_name, asset_cfg, sensor_cfg, p):
    r = _update(env, asset_cfg, sensor_cfg, command_name, p)
    return freq_value(r["done"], r["cycle_s"], p["step_hz"])


def _monitor(raw, r, p):
    active, done = r["active"], r["done"]
    _add("active_steps", active)
    _add("pitch_sq_sum", torch.where(active, r["pitch_sq"], torch.zeros_like(r["pitch_sq"])))
    ok = done & (r["cycle_s"] <= MAX_CYCLE_S)
    _add("cycles", ok.float())
    _add("cycle_s_sum", torch.where(ok, r["cycle_s"], torch.zeros_like(r["cycle_s"])))
    _add("hip_cycles", done.float())
    _add("hip_range_sum", torch.where(done, r["hip_range"], torch.zeros_like(r["hip_range"])))
    raw._ex42_ct_calls = getattr(raw, "_ex42_ct_calls", 0) + 1
    if raw._ex42_ct_calls in (1, 50) or raw._ex42_ct_calls % MONITOR_EVERY == 0:
        row = summary()
        if row is not None and int(os.environ.get("RANK", "0") or 0) == 0:
            print("EX42_CLASSIC_MON calls=%d %s" % (
                raw._ex42_ct_calls, " ".join(f"{k}={v}" for k, v in row.items() if k != "counting")), flush=True)


def register(env_cfg, term_cfg_class=None, entity_cfg_class=None) -> bool:
    if not enabled():
        return False
    p = params()
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    if entity_cfg_class is None:
        from isaaclab.managers import SceneEntityCfg as entity_cfg_class
    rewards = env_cfg.rewards
    terms = (("ex42_classic_hip_range", ex42_classic_hip_range, p["w_hip"]),
             ("ex42_classic_pitch", ex42_classic_pitch, p["w_pitch"]),
             ("ex42_classic_step_freq", ex42_classic_step_freq, p["w_freq"]))
    terms = tuple(t for t in terms if t[2] != 0.0)   # lead 00:32: w_pitch=0 when EX42_LOWSPEED_GAIT already penalises wy^2
    for name, _, _ in terms:
        if getattr(rewards, name, None) is not None:
            raise ValueError(f"{ENV_SWITCH} registered twice ({name})")
    for name, func, weight in terms:
        setattr(rewards, name, term_cfg_class(
            func=func, weight=weight,
            params={"command_name": "base_velocity", "asset_cfg": entity_cfg_class("robot"), "p": dict(p),
                    "sensor_cfg": entity_cfg_class("contact_forces", body_names=list(FEET), preserve_order=True)}))
    print("EX42_CLASSIC_TARGET where=start w_hip=%g w_pitch=%g w_freq=%g hip_target=%g step_hz=%g v_max=%g cmd_min=%g "
          "band_max_level=%g min_swing_steps=%g mask=moving_lowspeed_nonzero_continuous_level_le_band_max_level"
          % (p["w_hip"], p["w_pitch"], p["w_freq"], p["hip_target"], p["step_hz"], p["v_max"], p["cmd_min"],
             p["band_max_level"], p["min_swing_steps"]), flush=True)
    return True


def summary() -> dict | None:
    if not enabled():
        return None
    s = {k: v.detach().cpu() for k, v in _SUMS.items()}
    steps = float(s.get("active_steps", torch.zeros(())).sum())
    out = {"counting": "rank-local cumulative since process start", "active_env_steps": int(steps)}
    out["pitch_rms"] = round(math.sqrt(float(s["pitch_sq_sum"]) / steps), 5) if steps else None
    if "cycles" in s and steps:
        c = s["cycles"]
        out["step_hz_per_foot"] = [round(float(n) / float(t), 4) if float(t) else None for n, t in zip(c, s["cycle_s_sum"])]
        hc = s["hip_cycles"]
        out["hip_range_rad"] = [round(float(r) / float(n), 5) if float(n) else None for r, n in zip(s["hip_range_sum"], hc)]
        out["scored_cycles"] = int(float(hc.sum()))
    return out
