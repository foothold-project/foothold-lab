"""EX42_AMP (plan AMP-PLAN-1126 step 3; team lead 11/26 00:20 · 00:25, lead 02:05 · 03:04, planner 00:26 conditions). Off by default.

A style reward from a discriminator trained against real Go2 reference motion (ex42_amp_reference, Classic + Sport walk, stop,
stand). The reward is only added to the reward sum: observations, actions, actor, critic and the ONNX export stay as they are
(ex42_policy_signature_gate must stay "same"; the discriminator is saved under its own checkpoint key amp_disc).

    state s (30)   q - default joint pose (policy order hip x4 · thigh x4 · calf x4, legs FL FR RL RR) · joint vel · body ang vel ·
                   projected gravity, read from the sim WITHOUT action delay or observation noise (the real log is raw lowstate)
    input          (s_t-1, s_t) + one-hot [walk, still]: still = the command is zero, matched against the stop + stand reference;
                   walk = a command, with straight_only=1 only straight commands (|vy| <= straight_vy, |wz| <= straight_wz; other
                   command rows get no style) matched against the forward-stick-only reference (lead 03:17 (3)). With center=1
                   grav_z is dropped and q, grav_x, grav_y are minus the mean of the same condition on the same side (reference:
                   that class mean; policy: its own moving mean), so the discriminator sees the gait motion, not the posture
                   (lead 03:17 (2): the sim policy walks pitched, grav_x -0.116 vs +0.003, and grav_z normalised 21 x)
    reward         rel_style=1: clip((D - lo) / (mean D_ref - lo), 0, 1), lo = mean - floor_sigma * sd of D over this step's policy
                   rows of that condition (relative_style; lead 03:17 (1)); rel_style=0: max(0, 1 - 0.25 (D - 1)^2). Mask rows
                   only, x ramp (0 -> 1 over ramp_steps env steps, planner 00:27 (5))
    mask           continuous columns (not the sparse beam kinds), terrain level <= band_max_level, and with flatlike_only=1 family A
                   flat-like kinds only (the Classic mask); 0 elsewhere (no style on stairs, beams, gaps)
    discriminator  ex42_amp_disc (MLP 512-256 ELU, LSGAN, GP on the normalised input), trained in place every disc_every env steps
                   for disc_steps steps on the latest policy transitions of the mask rows (ring buffer) against the reference

Switch EX42_AMP=1, weight EX42_AMP_W (> 0), reference EX42_AMP_REF (amp_ref.npz), EX42_AMP_PARAMS "key=value,..." over DEFAULTS.
Lines: EX42_AMP where=start (weight, params, reference sha, input form) · EX42_AMP_MON every MONITOR_EVERY steps (last disc step
d_loss gp D_ref D_pol; style_mean dead_frac D_pol_now D_pol_std D_ref_now on mask rows; row fractions; pol_grav_x_walk; ramp). No Kit import at module level.
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
REF_STICK_EPS = 0.05     # ex42_amp_reference STICK_EPS: a stick column is "on" above this
STICK_FORWARD = 1        # reference stick columns: 0 lateral · 1 forward · 2 yaw (planner 03:16: hip q rms 0.150 · 0.040 · gyro_z 1.58)
CENTER_COLS = tuple(range(12)) + (27, 28)   # q and grav_x, grav_y: minus the walk / still mean of that side (lead 03:17 (2))
GRAV_Z = 29              # dropped from the input when center=1 (set by grav_x, grav_y; its reference std is tiny, lead 03:17 (2))
DEFAULTS = {"lr": 1e-4, "disc_every": 24.0, "disc_steps": 2.0, "batch": 4096.0, "gp": 10.0, "ramp_steps": 1200.0,
            "band_max_level": 1.0, "flatlike_only": 1.0, "buffer": 200000.0, "pol_dq_noise": 0.0,
            # lead 03:17 fixes, each on by default (planner 03:16 msg_e33006228c44)
            "rel_style": 1.0, "floor_sigma": 2.0,            # (1) style relative to the policy batch, floor mu_pol - floor_sigma * sd_pol
            "center": 1.0, "center_momentum": 0.01,          # (2) drop grav_z, minus the per-condition mean (policy: moving average)
            "straight_only": 1.0, "straight_vy": 0.1, "straight_wz": 0.1,   # (3) walk = straight command rows vs straight reference only
            "ref_probe": 1024.0}
_STATE: dict = {}
MON_SUMS = ("rows", "style", "dead", "walk", "still", "tot", "d_std", "d_mean", "d_ref", "batches")


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
            or out["flatlike_only"] not in (0.0, 1.0) or out["buffer"] < out["batch"] or out["pol_dq_noise"] < 0
            or any(out[k] not in (0.0, 1.0) for k in ("rel_style", "center", "straight_only")) or out["floor_sigma"] < 0
            or not 0 < out["center_momentum"] <= 1 or out["straight_vy"] < 0 or out["straight_wz"] < 0 or out["ref_probe"] < 16):
        raise ValueError(f"{PARAMS_ENV} out of range: {out}")
    return out


def ref_path() -> Path:
    p = Path(os.environ.get(REF_ENV, ""))
    if not p.is_file():
        raise ValueError(f"{REF_ENV} is not a file: {p}")
    return p


def input_cols(p: dict) -> list[int]:
    return [c for c in range(30) if not (p["center"] and c == GRAV_Z)]


def reference_transitions(npz: dict, p: dict | None = None) -> tuple[torch.Tensor, torch.Tensor]:
    """([N, 2 * len(input_cols) + 2] reference transitions (s_t, s_t+1, walk, still), [2, 30] subtracted means (walk, still)).

    walk = kind 0 rows (with straight_only=1 only the rows where the forward stick alone is on); still = stop and stand rows.
    A transition needs both rows in the same segment and the same class. With center=1 the q and grav_x, grav_y columns of each
    class are minus that class mean and grav_z is dropped."""
    p = dict(DEFAULTS) if p is None else p
    s, seg, kind = (np.asarray(npz[k]) for k in ("s", "seg", "kind"))
    walk = kind == 0
    if p["straight_only"]:
        stick = np.abs(np.asarray(npz["stick"]))
        others = [c for c in range(stick.shape[1]) if c != STICK_FORWARD]
        walk = walk & (stick[:, STICK_FORWARD] > REF_STICK_EPS) & (stick[:, others].max(axis=1) <= REF_STICK_EPS)
    cols = input_cols(p)
    centers = np.zeros((2, 30), dtype=np.float32)
    parts = []
    for c, sel in enumerate((walk, kind != 0)):
        if not sel.any():
            raise ValueError(f"EX42_AMP reference has no {'walk' if c == 0 else 'still'} rows")
        if p["center"]:
            centers[c, list(CENTER_COLS)] = s[sel][:, list(CENTER_COLS)].mean(axis=0)
        i = np.flatnonzero((seg[1:] == seg[:-1]) & sel[:-1] & sel[1:])
        a, b = (s[i] - centers[c])[:, cols], (s[i + 1] - centers[c])[:, cols]
        hot = np.zeros((len(i), 2), dtype=np.float32)
        hot[:, c] = 1.0
        parts.append(np.concatenate([a, b, hot], axis=1))
    return torch.as_tensor(np.concatenate(parts), dtype=torch.float32), torch.as_tensor(centers)


def classes(command: torch.Tensor, p: dict) -> tuple[torch.Tensor, torch.Tensor]:
    """(walk, still) bool rows: still = vx, vy and wz all zero; walk = a command (straight_only=1: |vy|, |wz| small too)."""
    c = command[:, :3]
    still = (c.abs() <= STILL_EPS).all(dim=1)
    walk = ~still
    if p["straight_only"]:
        walk = walk & (c[:, 1].abs() <= p["straight_vy"]) & (c[:, 2].abs() <= p["straight_wz"])
    return walk, still


def relative_style(d: torch.Tensor, d_ref_mean: torch.Tensor, floor_sigma: float) -> torch.Tensor:
    """clip((D - lo) / (mean D_ref - lo), 0, 1), lo = mean D_pol - floor_sigma * sd D_pol over these policy rows.

    The clipped LSGAN form max(0, 1 - 0.25 (D - 1)^2) is exactly 0 (no gradient) for D <= -1, which planner measured on 41 to 66 %
    of the policy rows once the discriminator wins. Relative to the batch, the ranking among policy rows survives a winning
    discriminator; the floor keeps rows below the batch mean alive (with lo = mean only, about half would be 0 again), and the [0, 1]
    range keeps EX42_AMP_W an upper bound (planner (4))."""
    if d.numel() < 2:
        return torch.zeros_like(d)
    lo = d.mean() - floor_sigma * d.std()
    return ((d - lo) / (d_ref_mean - lo).clamp_min(1e-3)).clamp(0.0, 1.0)


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

    ref, ref_centers = reference_transitions(npz if npz is not None else np.load(ref_path()), p)
    ref = ref.to(device)
    disc = amp.AmpDiscriminator(ref.shape[1], amp.HIDDEN, ref.mean(0), ref.std(0)).to(device)
    opt = torch.optim.Adam(disc.parameters(), lr=p["lr"])
    st = {"disc": disc, "opt": opt, "ref": ref, "ref_centers": ref_centers.to(device),
          "ref_idx": [torch.nonzero(ref[:, -1] == c).squeeze(1) for c in (0.0, 1.0)],
          "pol_center": torch.zeros(2, 30, device=device), "pol_center_init": torch.zeros(2, dtype=torch.bool, device=device),
          "buf": Buffer(int(p["buffer"]), ref.shape[1], device), "p": p, "updates": 0,
          "last": {}, "sums": torch.zeros(len(MON_SUMS), dtype=torch.float64, device=device), "calls": 0}
    pending = _STATE.pop("pending", None)
    if pending is not None:
        disc.load_state_dict(pending["disc"])
        opt.load_state_dict(pending["opt"])
        st["updates"] = int(pending.get("updates", 0))
        if "pol_center" in pending:
            st["pol_center"].copy_(pending["pol_center"].to(device))
            st["pol_center_init"].copy_(pending["pol_center_init"].to(device))
    _STATE.update(st)
    return _STATE


def ref_like(st: dict, xp: torch.Tensor) -> torch.Tensor:
    """Reference row indices with the same walk / still count as the policy batch xp (the reference is about 1 walk : 3 still,
    the policy mask rows are mostly walk: a uniform draw would train the walk side on a quarter of the batch)."""
    n_still = int(xp[:, -1].sum())
    out = []
    for c, k in ((0, len(xp) - n_still), (1, n_still)):
        idx = st["ref_idx"][c]
        if k > 0 and len(idx) > 0:
            out.append(idx[torch.randint(len(idx), (k,), device=idx.device)])
    return torch.cat(out) if out else torch.randint(len(st["ref"]), (len(xp),), device=st["ref"].device)


def train_disc(st: dict) -> None:
    from foothold_s2.runners import ex42_amp_disc as amp

    p = st["p"]
    if st["buf"].n < p["batch"]:
        return
    b = int(p["batch"])
    with torch.inference_mode(False), torch.enable_grad():
        for _ in range(int(p["disc_steps"])):
            xp = st["buf"].sample(b).clone()
            xr = st["ref"][ref_like(st, xp)]
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


def update_center(st: dict, s: torch.Tensor, sel: torch.Tensor, c: int) -> None:
    """Moving mean (center_momentum) of the policy's own q, grav_x, grav_y on mask rows of condition c (0 walk, 1 still)."""
    if not bool(sel.any()):
        return
    cols = list(CENTER_COLS)
    m = s[sel][:, cols].mean(dim=0)
    with torch.inference_mode(False):
        m = m.detach().clone()
        if bool(st["pol_center_init"][c]):
            st["pol_center"][c, cols] = st["pol_center"][c, cols].lerp(m, st["p"]["center_momentum"])
        else:
            st["pol_center"][c, cols] = m
            st["pol_center_init"][c] = True


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
    walk, still = classes(env.command_manager.get_command(command_name).to(s.device), p)
    rows = mask(env, p).to(s.device) & ~fresh & (walk | still)
    cls = still.long()
    for c, sel in enumerate((rows & walk, rows & still)):
        update_center(st, s, sel, c)
    center = st["pol_center"][cls] if p["center"] else torch.zeros_like(s)
    cols = input_cols(p)
    cond = torch.stack([(~still).float(), still.float()], dim=1)
    x = torch.cat([(prev - center)[:, cols], (s - center)[:, cols], cond], dim=1)
    from foothold_s2.runners.ex42_amp_disc import style_reward

    d_ref_sum, n_cls = 0.0, 0
    with torch.no_grad():
        d = st["disc"](x)
        if p["rel_style"]:
            style = torch.zeros_like(d)
            for c, sel in enumerate((rows & walk, rows & still)):
                idx = st["ref_idx"][c]
                if int(sel.sum()) < 2 or len(idx) == 0:
                    continue
                pick = idx[torch.randint(len(idx), (int(p["ref_probe"]),), device=idx.device)]
                d_ref = st["disc"](st["ref"][pick]).mean()
                style[sel] = relative_style(d[sel], d_ref, p["floor_sigma"])
                d_ref_sum, n_cls = d_ref_sum + float(d_ref), n_cls + 1
        else:
            style = style_reward(d)
    step = int(getattr(raw, "common_step_counter", 0))
    out = torch.where(rows, style, torch.zeros_like(style)) * ramp(step, p["ramp_steps"])
    with torch.inference_mode(False):
        st["buf"].add(x[rows].detach().clone())
    dr = d[rows]
    one = torch.ones((), dtype=torch.float64, device=s.device)
    with torch.inference_mode(False):
        st["sums"] += torch.stack([rows.sum().double(), style[rows].sum().double(), (style[rows] == 0).sum().double(),
                                   (rows & walk).sum().double(), (rows & still).sum().double(), float(len(rows)) * one,
                                   (dr.std().double() if len(dr) > 1 else 0 * one), dr.double().sum(),
                                   (d_ref_sum / n_cls if n_cls else 0.0) * one, (one if n_cls else 0 * one)]).detach().clone()
    st["calls"] += 1
    if st["calls"] % int(p["disc_every"]) == 0:
        train_disc(st)
    if st["calls"] in (1, 50) or st["calls"] % MONITOR_EVERY == 0:
        v = dict(zip(MON_SUMS, st["sums"].tolist()))
        k = st["calls"] - st.get("mon_calls", 0)
        st["mon_calls"] = st["calls"]
        with torch.inference_mode(False):
            st["sums"].zero_()
        if int(os.environ.get("RANK", "0") or 0) == 0:
            n, nb = v["rows"], v["batches"]
            last = " ".join(f"{key}={val:.4g}" for key, val in st["last"].items()) or "d_loss=none"
            nan = float("nan")
            print(f"EX42_AMP_MON calls={st['calls']} {last} style_mean={v['style'] / n if n else nan:.4f} "
                  f"dead_frac={v['dead'] / n if n else nan:.4f} D_pol_now={v['d_mean'] / n if n else nan:.4f} "
                  f"D_pol_std={v['d_std'] / k if k else nan:.4f} D_ref_now={v['d_ref'] / nb if nb else nan:.4f} "
                  f"mask_row_frac={n / v['tot'] if v['tot'] else 0:.4f} walk_row_frac={v['walk'] / v['tot'] if v['tot'] else 0:.4f} "
                  f"still_row_frac={v['still'] / v['tot'] if v['tot'] else 0:.4f} "
                  f"pol_grav_x_walk={float(st['pol_center'][0, 27]):.4f} ramp={ramp(step, p['ramp_steps']):.3f} "
                  f"disc_updates={st['updates']} buffer={st['buf'].n}", flush=True)
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
          + f" input=s_prev,s,walk,still dims={2 * len(input_cols(p)) + 2}" + (" minus_grav_z centered_per_condition" if p["center"] else "")
          + (" walk=straight_cmd_vs_forward_stick_ref" if p["straight_only"] else " walk=any_cmd_vs_all_walk_ref")
          + (" style=relative_batch_floor" if p["rel_style"] else " style=lsgan_clipped")
          + " mask=continuous_level_le_band_max_level" + ("_flatlike_kinds" if p["flatlike_only"] else ""),
          flush=True)
    return True


def checkpoint_entry() -> dict:
    """{'amp_disc': ...} for the runner checkpoint when the discriminator exists, else {} (the policy keys never change)."""
    if "disc" not in _STATE:
        return {}
    return {"amp_disc": {"disc": {k: v.detach().cpu() for k, v in _STATE["disc"].state_dict().items()},
                         "opt": _STATE["opt"].state_dict(), "updates": _STATE["updates"],
                         "pol_center": _STATE["pol_center"].detach().cpu(), "pol_center_init": _STATE["pol_center_init"].detach().cpu()}}


def load_checkpoint_entry(saved: dict | None) -> None:
    """Resume: the discriminator is built at the first reward call, so the saved state waits until then."""
    if saved is not None and enabled():
        if "disc" in _STATE:
            _STATE["disc"].load_state_dict(saved["disc"])
            _STATE["opt"].load_state_dict(saved["opt"])
            _STATE["updates"] = int(saved.get("updates", 0))
            if "pol_center" in saved:
                _STATE["pol_center"].copy_(saved["pol_center"].to(_STATE["pol_center"].device))
                _STATE["pol_center_init"].copy_(saved["pol_center_init"].to(_STATE["pol_center_init"].device))
        else:
            _STATE["pending"] = saved
