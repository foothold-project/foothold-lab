"""EX-42 E2 balance-beam centre keeping (lead 2026-11-22 06:41, ledger 309cefc1b · planner 06:36). OUTSIDE START (not a paper term).
Off by default: only with EX42_BEAM_CENTER=1. Off, the env config is the same bytes (no term is added).

Why: planner 06:36 split the A/balance_beams L3 failures: 84~96 % are "the body drifts about 5 cm off the beam centre and the outer
hind foot drops", unrelated to the gait width or the hip term. Today's median drift 2.2~2.9 cm gives no reward signal.

    dy     = body root y - the env's terrain tile origin y   (the beam runs along the tile x axis, centred on tile y = 0; the same
             yardstick as planner beam_fail_cause.py root_y_local_m). Reward only: uses the true terrain, the policy observation is
             unchanged (it still sees the map).
    active = the env's terrain column is A/balance_beams (env._ex42_column_table) and the body is on the beam, tile x in [x0, x1]
             (EX42_BEAM_CENTER_X, default 0.5,6.5 m · planner 06:38) and the env's map is not switched off (the runner publishes the
             per-env map-off flag as env._ex42_map_off every step; map-off envs are left out, reconstructed-map envs stay in). Elsewhere 0.
             The centre line is tile y = 0: checked on the real mesh (b2m_rpy_lv, columns 35~39, every level: top y mid 0.0000 m).
    planner 06:38 · lead 06:39 (ledger e617fe49f): r_center = -5.0 x min(|dy|, 0.10) (l1, EX42_BEAM_CENTER_W=-5.0).
    lead 06:40 (ledger b148fd9b2): forward-command envs only (vx > 0.1, |vy| <= 0.1, |wz| <= 0.1: side, turn and stand commands left out);
             the check line splits ground-truth-map and reconstructed-map envs (the runner publishes env._ex42_use_gt beside map-off).
    form   EX42_BEAM_CENTER_FORM = l1  : value = min(|dy|, EX42_BEAM_CENTER_CLIP)      weight must be < 0 (a penalty)
                                 exp : value = exp(-|dy| / EX42_BEAM_CENTER_SIGMA)  weight must be > 0
    weight EX42_BEAM_CENTER_W (no default: the value is chosen with planner and written in the env).

Lines: EX42_BEAM_CENTER where=start (weight · form · width · x range · "outside START"), EX42_BEAM_CENTER where=first_call
(beam envs of all envs), EX42_BEAM_CENTER_CHECK every EX42_BEAM_CENTER_CHECK_STEPS term calls (default 1200 = 50 updates x 24):
on-beam sample count, median |dy|, mean term value (unweighted and weighted). No Kit import at module level.
"""
from __future__ import annotations

import json
import math
import os

import torch

TERM = "ex42_beam_center"
ENV_SWITCH = "EX42_BEAM_CENTER"
KEYS = ("EX42_BEAM_CENTER_FORM", "EX42_BEAM_CENTER_W", "EX42_BEAM_CENTER_SIGMA", "EX42_BEAM_CENTER_CLIP", "EX42_BEAM_CENTER_X",
        "EX42_BEAM_CENTER_CHECK_STEPS")
STATE = "_ex42_beam_center_state"
BEAM_KIND = ("A", "balance_beams")
SAMPLE_EVERY = 24
CMD_EPS = 0.1                        # forward only: vx > 0.1 · |vy| <= 0.1 · |wz| <= 0.1 (lead 06:40)


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    loose = [k for k in KEYS if os.environ.get(k, "") != ""]
    if value != "1" and loose:
        raise ValueError(f"{', '.join(loose)} set but {ENV_SWITCH} is not 1")
    return value == "1"


def _num(name, default=None):
    raw = os.environ.get(name, "")
    if raw == "":
        if default is None:
            raise ValueError(f"{name} is required when {ENV_SWITCH}=1")
        return float(default)
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number (got {raw!r})") from None
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite (got {raw!r})")
    return v


def settings() -> dict:
    form = os.environ.get("EX42_BEAM_CENTER_FORM", "")
    if form not in ("l1", "exp"):
        raise ValueError(f"EX42_BEAM_CENTER_FORM must be l1 or exp (got {form!r})")
    w = _num("EX42_BEAM_CENTER_W")
    if form == "l1" and not w < 0:
        raise ValueError(f"l1 form is a penalty: EX42_BEAM_CENTER_W must be < 0 (got {w})")
    if form == "exp" and not w > 0:
        raise ValueError(f"exp form is a reward: EX42_BEAM_CENTER_W must be > 0 (got {w})")
    sigma, clip = _num("EX42_BEAM_CENTER_SIGMA", 0.03), _num("EX42_BEAM_CENTER_CLIP", 0.10)
    if not (sigma > 0 and clip > 0):
        raise ValueError("EX42_BEAM_CENTER_SIGMA and EX42_BEAM_CENTER_CLIP must be > 0")
    raw_x = os.environ.get("EX42_BEAM_CENTER_X", "0.5,6.5")
    try:
        x0, x1 = (float(v) for v in raw_x.split(","))
    except ValueError:
        raise ValueError(f"EX42_BEAM_CENTER_X must be 'x0,x1' (got {raw_x!r})") from None
    if not x0 < x1:
        raise ValueError(f"EX42_BEAM_CENTER_X must have x0 < x1 (got {raw_x!r})")
    steps = _num("EX42_BEAM_CENTER_CHECK_STEPS", 1200)
    if steps < SAMPLE_EVERY or steps != int(steps):
        raise ValueError("EX42_BEAM_CENTER_CHECK_STEPS must be a whole number >= 24")
    return {"form": form, "weight": w, "sigma": sigma, "clip": clip, "x": (x0, x1), "check_steps": int(steps)}


def beam_columns(table) -> torch.Tensor:
    return torch.tensor([(row["family"], row["kind"]) == BEAM_KIND for row in table], dtype=torch.bool)


def value(dy_abs: torch.Tensor, on: torch.Tensor, cfg: dict) -> torch.Tensor:
    """Unweighted term value: l1 min(|dy|, clip) · exp exp(-|dy|/sigma) on active envs, 0 elsewhere."""
    v = dy_abs.clamp(max=cfg["clip"]) if cfg["form"] == "l1" else torch.exp(-dy_abs / cfg["sigma"])
    return torch.where(on, v, torch.zeros_like(v))


class _State:
    def __init__(self, cfg, beam_cols):
        self.cfg, self.beam_cols, self.calls, self.samples, self.started = cfg, beam_cols, 0, [], False


def _rank() -> int:
    for k in ("RANK", "LOCAL_RANK"):
        if os.environ.get(k, "").isdigit():
            return int(os.environ[k])
    return 0


def beam_center_term(env):
    raw = getattr(env, "unwrapped", env)
    st = getattr(raw, STATE, None)
    if st is None:
        table = getattr(raw, "_ex42_column_table", None)
        if table is None:
            raise ValueError("EX-42 beam centre needs the column table (raw._ex42_column_table) on the environment")
        st = _State(settings(), beam_columns(table).to(env.device))
        setattr(raw, STATE, st)
    terrain = env.scene.terrain
    cols = terrain.terrain_types.long().to(st.beam_cols.device)
    if bool(((cols < 0) | (cols >= len(st.beam_cols))).any()):
        raise ValueError("EX-42 beam centre: a terrain column is outside the column table")
    beam_env = st.beam_cols[cols]
    local = env.scene["robot"].data.root_pos_w[:, :2] - terrain.env_origins[:, :2]
    x0, x1 = st.cfg["x"]
    if not hasattr(raw, "_ex42_map_off"):
        raise ValueError("EX-42 beam centre needs the runner's per-env map-off flag (raw._ex42_map_off) to leave map-off envs out")
    map_off = raw._ex42_map_off
    if map_off is None:                                   # the runner has no map switch-off (PerceptionState.map_off None): every env keeps its map
        map_off = torch.zeros(env.num_envs, dtype=torch.bool)
    cmd = env.command_manager.get_command("base_velocity").to(beam_env.device)
    forward = (cmd[:, 0] > CMD_EPS) & (cmd[:, 1].abs() <= CMD_EPS) & (cmd[:, 2].abs() <= CMD_EPS)
    on = beam_env & forward & (local[:, 0] >= x0) & (local[:, 0] <= x1) & ~map_off.to(beam_env.device).bool()
    use_gt = getattr(raw, "_ex42_use_gt", None)
    gt = torch.ones_like(on) if use_gt is None else use_gt.to(on.device).bool()
    dy = local[:, 1].abs()
    v = value(dy, on, st.cfg)
    if not st.started:
        st.started = True
        print(f"EX42_BEAM_CENTER where=first_call beam_envs={int(beam_env.sum())} beam_envs_map_on={int((beam_env & ~map_off.to(beam_env.device).bool()).sum())}"
              f" of={int(beam_env.numel())} rank={_rank()}", flush=True)
    st.calls += 1
    if st.calls % SAMPLE_EVERY == 0 and bool(on.any()):
        st.samples.append(torch.stack([dy[on], v[on], gt[on].float()], 1).detach().float().cpu())
    if st.calls % st.cfg["check_steps"] == 0:
        line = {"step": st.calls, "rank": _rank()}
        s = torch.cat(st.samples) if st.samples else torch.zeros((0, 3)); st.samples = []
        for name, sel in (("all", torch.ones(len(s), dtype=torch.bool)), ("gt", s[:, 2] > 0.5), ("recon", s[:, 2] <= 0.5)):
            t = s[sel]
            line[name] = ({"n": int(len(t)), "median_abs_dy_m": round(float(t[:, 0].median()), 5), "term_mean": round(float(t[:, 1].mean()), 6),
                           "term_mean_weighted": round(float(t[:, 1].mean()) * st.cfg["weight"], 6)} if len(t) else {"n": 0})
        print("EX42_BEAM_CENTER_CHECK " + json.dumps(line), flush=True)
    return v


def register(env_cfg, term_cfg_class=None) -> bool:
    """Before the env is built: add the term when the switch is on and the config does not have it. True when added (one start line)."""
    if not enabled() or hasattr(env_cfg.rewards, TERM):
        return False
    cfg = settings()
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    setattr(env_cfg.rewards, TERM, term_cfg_class(func=beam_center_term, weight=cfg["weight"], params={}))
    width = f"clip={cfg['clip']}" if cfg["form"] == "l1" else f"sigma={cfg['sigma']}"
    print(f"EX42_BEAM_CENTER where=start weight={cfg['weight']} form={cfg['form']} {width} x={list(cfg['x'])} kind=A/balance_beams "
          f"dy=root_y-tile_origin_y check_steps={cfg['check_steps']} outside_START=1", flush=True)
    return True
