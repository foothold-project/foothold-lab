"""EX42_AMP (plan AMP-PLAN-1126 step 3; team lead 11/26 00:20 · 00:25, lead 02:05 · 03:04, planner 00:26 conditions). Off by default.

A style reward from a discriminator trained against real Go2 reference motion (ex42_amp_reference, Classic + Sport walk, stop,
stand). The reward is only added to the reward sum: observations, actions, actor, critic and the ONNX export stay as they are
(ex42_policy_signature_gate must stay "same"; the discriminator is saved under its own checkpoint key amp_disc).

    state s (30)   q - default joint pose (policy order hip x4 · thigh x4 · calf x4, legs FL FR RL RR) · joint vel · body ang vel ·
                   projected gravity, read from the sim WITHOUT action delay or observation noise (the real log is raw lowstate)
    input          (s_t-1, s_t) + one-hot [walk, still]: still = the command is zero (stand / stop rows are matched against the stop +
                   stand reference only, command rows against walk only; planner 00:27 (3))
    reward         style = max(0, 1 - 0.25 (D - 1)^2) on mask rows, x ramp (0 -> 1 over ramp_steps env steps, planner 00:27 (5))
    mask           continuous columns (not the sparse beam kinds), terrain level <= band_max_level, and with flatlike_only=1 family A
                   flat-like kinds only (the Classic mask); 0 elsewhere (no style on stairs, beams, gaps)
    discriminator  ex42_amp_disc (MLP 512-256 ELU, LSGAN, GP on the normalised input), trained in place every disc_every env steps
                   for disc_steps steps on the latest policy transitions of the mask rows (ring buffer) against the reference

Switch EX42_AMP=1, weight EX42_AMP_W (> 0), reference EX42_AMP_REF (amp_ref.npz), EX42_AMP_PARAMS "key=value,..." over DEFAULTS.
Lines: EX42_AMP where=start (weight, params, reference sha) · EX42_AMP_MON every MONITOR_EVERY steps (d_loss gp D_ref D_pol
style_mean on mask rows, mask_row_frac, ramp, disc_updates). No Kit import at module level.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import numpy as np
import torch

ENV_SWITCH = "EX42_AMP"
WEIGHT_ENV = "EX42_AMP_W"
REF_ENV = "EX42_AMP_REF"
PARAMS_ENV = "EX42_AMP_PARAMS"
TERM = "ex42_amp_style"
LEGS = ("FL", "FR", "RL", "RR")
JOINTS = tuple(f"{leg}_{j}_joint" for j in ("hip", "thigh", "calf") for leg in LEGS)
STILL_EPS = 1e-6
MONITOR_EVERY = 240
DEFAULTS = {"lr": 1e-4, "disc_every": 24.0, "disc_steps": 2.0, "batch": 4096.0, "gp": 10.0, "ramp_steps": 1200.0,
            "band_max_level": 1.0, "flatlike_only": 1.0, "buffer": 200000.0, "pol_dq_noise": 0.0}
_STATE: dict = {}


def enabled() -> bool:
    raw = os.environ.get(ENV_SWITCH, "")
    if raw not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 1, 0 or unset (got {raw!r})")
    if raw != "1":
        if os.environ.get(WEIGHT_ENV) or os.environ.get(REF_ENV) or os.environ.get(PARAMS_ENV):
            raise ValueError(f"{WEIGHT_ENV} / {REF_ENV} / {PARAMS_ENV} set while {ENV_SWITCH} is off")
        return False
    return True


def weight() -> float:
    raw = os.environ.get(WEIGHT_ENV, "")
    try:
        w = float(raw)
    except ValueError:
        raise ValueError(f"{WEIGHT_ENV} must be a number > 0 (got {raw!r})") from None
    if not math.isfinite(w) or w <= 0:
        raise ValueError(f"{WEIGHT_ENV} must be a number > 0 (got {raw!r})")
    return w


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
    if (any(not math.isfinite(v) for v in out.values()) or not 0 < out["lr"] < 1e-2 or out["disc_every"] < 1 or out["disc_steps"] < 0
            or out["batch"] < 16 or out["gp"] < 0 or out["ramp_steps"] < 0 or not 0 <= out["band_max_level"] <= 9
            or out["flatlike_only"] not in (0.0, 1.0) or out["buffer"] < out["batch"] or out["pol_dq_noise"] < 0):
        raise ValueError(f"{PARAMS_ENV} out of range: {out}")
    return out


def ref_path() -> Path:
    p = Path(os.environ.get(REF_ENV, ""))
    if not p.is_file():
        raise ValueError(f"{REF_ENV} is not a file: {p}")
    return p


def reference_transitions(npz: dict) -> torch.Tensor:
    """[N, 62] reference transitions (s_t, s_t+1, walk, still) inside segments; stop and stand rows are 'still'."""
    s, seg, kind = (np.asarray(npz[k]) for k in ("s", "seg", "kind"))
    i = np.flatnonzero(seg[1:] == seg[:-1])
    still = (kind[i] != 0).astype(np.float32)[:, None]
    return torch.as_tensor(np.concatenate([s[i], s[i + 1], 1.0 - still, still], axis=1), dtype=torch.float32)


def condition(command: torch.Tensor) -> torch.Tensor:
    """[num_envs, 2] one-hot [walk, still]; still = vx, vy and wz all zero."""
    still = (command[:, :3].abs() <= STILL_EPS).all(dim=1).float()
    return torch.stack([1.0 - still, still], dim=1)


def ramp(step: int, ramp_steps: float) -> float:
    return 1.0 if ramp_steps <= 0 else min(1.0, max(0.0, step / ramp_steps))


class Buffer:
    """Ring buffer of the latest policy transitions (normal tensors, not inference tensors)."""

    def __init__(self, size: int, dim: int, device):
        self.x = torch.zeros(size, dim, device=device)
        self.n, self.pos = 0, 0

    def add(self, x: torch.Tensor) -> None:
        k = min(len(x), len(self.x))
        if k == 0:
            return
        x = x[-k:]
        end = self.pos + k
        if end <= len(self.x):
            self.x[self.pos:end] = x
        else:
            cut = len(self.x) - self.pos
            self.x[self.pos:] = x[:cut]
            self.x[:end - len(self.x)] = x[cut:]
        self.pos = end % len(self.x)
        self.n = min(self.n + k, len(self.x))

    def sample(self, k: int, gen: torch.Generator | None = None) -> torch.Tensor:
        return self.x[torch.randint(self.n, (k,), device=self.x.device, generator=gen)]


def build(device, p: dict, npz: dict | None = None) -> dict:
    from foothold_s2.runners import ex42_amp_disc as amp

    ref = reference_transitions(npz if npz is not None else np.load(ref_path())).to(device)
    disc = amp.AmpDiscriminator(ref.shape[1], amp.HIDDEN, ref.mean(0), ref.std(0)).to(device)
    opt = torch.optim.Adam(disc.parameters(), lr=p["lr"])
    st = {"disc": disc, "opt": opt, "ref": ref, "buf": Buffer(int(p["buffer"]), ref.shape[1], device), "p": p, "updates": 0,
          "last": {}, "sums": torch.zeros(3, dtype=torch.float64, device=device), "calls": 0}
    pending = _STATE.pop("pending", None)
    if pending is not None:
        disc.load_state_dict(pending["disc"])
        opt.load_state_dict(pending["opt"])
        st["updates"] = int(pending.get("updates", 0))
    _STATE.update(st)
    return _STATE


def train_disc(st: dict) -> None:
    from foothold_s2.runners import ex42_amp_disc as amp

    p = st["p"]
    if st["buf"].n < p["batch"]:
        return
    b = int(p["batch"])
    with torch.inference_mode(False), torch.enable_grad():
        for _ in range(int(p["disc_steps"])):
            xr = st["ref"][torch.randint(len(st["ref"]), (b,), device=st["ref"].device)]
            xp = st["buf"].sample(b).clone()
            st["last"] = amp.disc_step(st["disc"], st["opt"], xr, xp, p["gp"])
            st["updates"] += 1


def state_vector(env, robot) -> torch.Tensor:
    raw = getattr(env, "unwrapped", env)
    ids = getattr(raw, "_ex42_amp_ids", None)
    if ids is None:
        names = list(robot.joint_names)
        ids = raw._ex42_amp_ids = torch.tensor([names.index(n) for n in JOINTS], device=robot.data.joint_pos.device)
    d = robot.data
    q = d.joint_pos[:, ids] - d.default_joint_pos[:, ids]
    return torch.cat([q, d.joint_vel[:, ids], d.root_ang_vel_b, d.projected_gravity_b], dim=1)


def mask(env, p) -> torch.Tensor:
    from foothold_s2.rewards.ex42_classic_target import flatlike_columns
    from foothold_s2.rewards.ex42_hip_sparse import sparse_envs

    raw = getattr(env, "unwrapped", env)
    terrain = env.scene.terrain
    dev = terrain.terrain_levels.device
    out = ~sparse_envs(env).to(dev) & (terrain.terrain_levels <= p["band_max_level"])
    if p["flatlike_only"]:
        table = getattr(raw, "_ex42_column_table", None)
        if table is None:
            raise ValueError("EX42_AMP flatlike_only needs the column table (raw._ex42_column_table)")
        out = out & flatlike_columns(table).to(dev)[terrain.terrain_types.long()]
    return out


def ex42_amp_style(env, command_name: str, asset_cfg, p: dict) -> torch.Tensor:
    raw = getattr(env, "unwrapped", env)
    robot = env.scene[asset_cfg.name]
    s = state_vector(env, robot)
    if "disc" not in _STATE:
        with torch.inference_mode(False):      # the rollout runs in inference mode: parameters built there could not be trained
            build(s.device, p)
    st = _STATE
    prev = getattr(raw, "_ex42_amp_prev", None)
    fresh = raw.episode_length_buf.to(s.device) <= 1
    if p["pol_dq_noise"] > 0:
        s = s.clone()
        s[:, 12:24] += torch.randn_like(s[:, 12:24]) * p["pol_dq_noise"]
    with torch.inference_mode(False):
        raw._ex42_amp_prev = s.detach().clone()
    if prev is None:
        return torch.zeros(s.shape[0], device=s.device)
    cond = condition(env.command_manager.get_command(command_name).to(s.device))
    x = torch.cat([prev, s, cond], dim=1)
    rows = mask(env, p).to(s.device) & ~fresh
    with torch.no_grad():
        d = st["disc"](x)
    from foothold_s2.runners.ex42_amp_disc import style_reward

    style = style_reward(d)
    step = int(getattr(raw, "common_step_counter", 0))
    out = torch.where(rows, style, torch.zeros_like(style)) * ramp(step, p["ramp_steps"])
    with torch.inference_mode(False):
        st["buf"].add(x[rows].detach().clone())
    st["sums"] += torch.stack([rows.sum().double(), torch.where(rows, style, torch.zeros_like(style)).sum().double(),
                               torch.tensor(float(len(rows)), dtype=torch.float64, device=s.device)])
    st["calls"] += 1
    if st["calls"] % int(p["disc_every"]) == 0:
        train_disc(st)
    if st["calls"] in (1, 50) or st["calls"] % MONITOR_EVERY == 0:
        n, ssum, tot = st["sums"].tolist()
        st["sums"].zero_()
        if int(os.environ.get("RANK", "0") or 0) == 0:
            last = " ".join(f"{k}={v:.4g}" for k, v in st["last"].items()) or "d_loss=none"
            print(f"EX42_AMP_MON calls={st['calls']} {last} style_mean={ssum / n if n else float('nan'):.4f} "
                  f"mask_row_frac={n / tot if tot else 0:.4f} ramp={ramp(step, p['ramp_steps']):.3f} disc_updates={st['updates']} "
                  f"buffer={st['buf'].n}", flush=True)
    return out


def register(env_cfg, term_cfg_class=None, entity_cfg_class=None) -> bool:
    if not enabled():
        return False
    w, p, ref = weight(), params(), ref_path()
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    if entity_cfg_class is None:
        from isaaclab.managers import SceneEntityCfg as entity_cfg_class
    if getattr(env_cfg.rewards, TERM, None) is not None:
        raise ValueError(f"{ENV_SWITCH} registered twice")
    setattr(env_cfg.rewards, TERM, term_cfg_class(func=ex42_amp_style, weight=w,
                                                  params={"command_name": "base_velocity", "asset_cfg": entity_cfg_class("robot"), "p": dict(p)}))
    sha = hashlib.sha256(ref.read_bytes()).hexdigest()
    print(f"EX42_AMP where=start weight={w:g} ref={ref} sha256={sha[:12]} " + " ".join(f"{k}={v:g}" for k, v in p.items())
          + " input=s_prev,s,walk,still mask=continuous_level_le_band_max_level" + ("_flatlike_kinds" if p["flatlike_only"] else ""),
          flush=True)
    return True


def checkpoint_entry() -> dict:
    """{'amp_disc': ...} for the runner checkpoint when the discriminator exists, else {} (the policy keys never change)."""
    if "disc" not in _STATE:
        return {}
    return {"amp_disc": {"disc": {k: v.detach().cpu() for k, v in _STATE["disc"].state_dict().items()},
                         "opt": _STATE["opt"].state_dict(), "updates": _STATE["updates"]}}


def load_checkpoint_entry(saved: dict | None) -> None:
    """Resume: the discriminator is built at the first reward call, so the saved state waits until then."""
    if saved is not None and enabled():
        if "disc" in _STATE:
            _STATE["disc"].load_state_dict(saved["disc"])
            _STATE["opt"].load_state_dict(saved["opt"])
            _STATE["updates"] = int(saved.get("updates", 0))
        else:
            _STATE["pending"] = saved
