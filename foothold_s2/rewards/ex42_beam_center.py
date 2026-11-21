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
    lead 07:39 (ledger 2b9bdc33d · planner 07:38): the body must face along the beam: |yaw| <= EX42_BEAM_CENTER_YAW (default 0.3 rad)
             from +x (a robot that starts turned walks off the beam whatever it does, so its |dy| is a penalty it cannot fix). The check
             line adds, per all / gt / recon: candidates before the yaw test (n_cand), the yaw pass share and |dy| median of the passed ones.
    lead 08:28 (ledger 076d0f707 · planner 08:27): the body must be ON the beam: root z - tile origin z > beam top z - 0.10 m and
             |dy| <= beam half width + 0.05 m, both from the training mesh (EX42_MESH_DIR_E2/terrain_mesh.npz: beam-top vertices at tile
             x 0.5~6.5, per level and column). A robot that stepped off sideways, diagonally or backwards and then got a forward command
             gets 0, not an unfixable -0.5. The check line adds the on-beam share of the yaw-passed candidates and, of the scored samples,
             the share with |dy| >= 0.099 (at the clip).
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
        "EX42_BEAM_CENTER_CHECK_STEPS", "EX42_BEAM_CENTER_YAW")
STATE = "_ex42_beam_center_state"
BEAM_KIND = ("A", "balance_beams")
SAMPLE_EVERY = 24
CMD_EPS = 0.1                        # forward only: vx > 0.1 · |vy| <= 0.1 · |wz| <= 0.1 (lead 06:40)
ON_BEAM_Z = 0.10                     # root z above beam top z - 0.10 (lead 08:28)
ON_BEAM_DY = 0.05                    # |dy| <= half width + 0.05
MESH_ENV = "EX42_MESH_DIR_E2"


def beam_geometry(mesh_dir, table) -> tuple[torch.Tensor, torch.Tensor]:
    """(top_z, half_width), each (levels, columns), NaN off the beam columns: beam-top vertices (tile x 0.5~6.5, |y| < 1, z > -0.3 from the
    tile origin) of every A/balance_beams column and level of the training mesh."""
    import numpy as np
    from pathlib import Path
    if not mesh_dir:
        raise ValueError(f"EX-42 beam centre needs the training mesh folder ({MESH_ENV}) for the on-beam test")
    z = np.load(Path(mesh_dir) / "terrain_mesh.npz")
    origins, verts = z["origins"], z["vertices"]
    top = np.full(origins.shape[:2], np.nan); half = np.full(origins.shape[:2], np.nan)
    for col, row in enumerate(table):
        if (row["family"], row["kind"]) != BEAM_KIND:
            continue
        for lv in range(origins.shape[0]):
            loc = verts - origins[lv, col]
            sel = loc[(loc[:, 0] > 0.45) & (loc[:, 0] < 6.55) & (np.abs(loc[:, 1]) < 1.0) & (loc[:, 2] > -0.3)]
            if not len(sel):
                raise ValueError(f"EX-42 beam centre: no beam-top vertex on level {lv} column {col}")
            top[lv, col], half[lv, col] = float(sel[:, 2].max()), float(np.abs(sel[:, 1]).max())
    return torch.tensor(top, dtype=torch.float32), torch.tensor(half, dtype=torch.float32)


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
    yaw = _num("EX42_BEAM_CENTER_YAW", 0.3)
    if not 0 < yaw <= math.pi:
        raise ValueError(f"EX42_BEAM_CENTER_YAW must be in (0, pi] (got {yaw})")
    steps = _num("EX42_BEAM_CENTER_CHECK_STEPS", 1200)
    if steps < SAMPLE_EVERY or steps != int(steps):
        raise ValueError("EX42_BEAM_CENTER_CHECK_STEPS must be a whole number >= 24")
    return {"form": form, "weight": w, "sigma": sigma, "clip": clip, "x": (x0, x1), "yaw": yaw, "check_steps": int(steps)}


def beam_columns(table) -> torch.Tensor:
    return torch.tensor([(row["family"], row["kind"]) == BEAM_KIND for row in table], dtype=torch.bool)


def value(dy_abs: torch.Tensor, on: torch.Tensor, cfg: dict) -> torch.Tensor:
    """Unweighted term value: l1 min(|dy|, clip) · exp exp(-|dy|/sigma) on active envs, 0 elsewhere."""
    v = dy_abs.clamp(max=cfg["clip"]) if cfg["form"] == "l1" else torch.exp(-dy_abs / cfg["sigma"])
    return torch.where(on, v, torch.zeros_like(v))


class _State:
    def __init__(self, cfg, beam_cols, top=None, half=None):
        self.cfg, self.beam_cols, self.calls, self.samples, self.started = cfg, beam_cols, 0, [], False
        self.top, self.half = top, half


def body_yaw(quat_wxyz: torch.Tensor) -> torch.Tensor:
    """Yaw (rad, -pi..pi) of Isaac (w, x, y, z) root quaternions."""
    w, x, y, z = quat_wxyz.unbind(-1)
    return torch.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


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
        top, half = beam_geometry(os.environ.get(MESH_ENV, ""), table)
        st = _State(settings(), beam_columns(table).to(env.device), top.to(env.device), half.to(env.device))
        setattr(raw, STATE, st)
    terrain = env.scene.terrain
    cols = terrain.terrain_types.long().to(st.beam_cols.device)
    if bool(((cols < 0) | (cols >= len(st.beam_cols))).any()):
        raise ValueError("EX-42 beam centre: a terrain column is outside the column table")
    beam_env = st.beam_cols[cols]
    robot = env.scene["robot"].data
    local = robot.root_pos_w[:, :2] - terrain.env_origins[:, :2]
    x0, x1 = st.cfg["x"]
    if not hasattr(raw, "_ex42_map_off"):
        raise ValueError("EX-42 beam centre needs the runner's per-env map-off flag (raw._ex42_map_off) to leave map-off envs out")
    map_off = raw._ex42_map_off
    if map_off is None:                                   # the runner has no map switch-off (PerceptionState.map_off None): every env keeps its map
        map_off = torch.zeros(env.num_envs, dtype=torch.bool)
    cmd = env.command_manager.get_command("base_velocity").to(beam_env.device)
    forward = (cmd[:, 0] > CMD_EPS) & (cmd[:, 1].abs() <= CMD_EPS) & (cmd[:, 2].abs() <= CMD_EPS)
    cand = beam_env & forward & (local[:, 0] >= x0) & (local[:, 0] <= x1) & ~map_off.to(beam_env.device).bool()
    yaw_ok = body_yaw(robot.root_quat_w.to(cand.device)).abs() <= st.cfg["yaw"]
    lv = terrain.terrain_levels.long().to(cand.device)
    top, half = st.top[lv, cols], st.half[lv, cols]
    rz = robot.root_pos_w[:, 2].to(cand.device) - terrain.env_origins[:, 2].to(cand.device)
    on_beam = (rz > top - ON_BEAM_Z) & (local[:, 1].abs() <= half + ON_BEAM_DY)      # NaN off the beam columns -> False
    on = cand & yaw_ok & on_beam
    use_gt = getattr(raw, "_ex42_use_gt", None)
    gt = torch.ones_like(on) if use_gt is None else use_gt.to(on.device).bool()
    dy = local[:, 1].abs()
    v = value(dy, on, st.cfg)
    if not st.started:
        st.started = True
        print(f"EX42_BEAM_CENTER where=first_call beam_envs={int(beam_env.sum())} beam_envs_map_on={int((beam_env & ~map_off.to(beam_env.device).bool()).sum())}"
              f" of={int(beam_env.numel())} rank={_rank()}", flush=True)
    st.calls += 1
    if st.calls % SAMPLE_EVERY == 0 and bool(cand.any()):
        st.samples.append(torch.stack([dy[cand], value(dy, cand, st.cfg)[cand], gt[cand].float(), yaw_ok[cand].float(), on_beam[cand].float()], 1).detach().float().cpu())
    if st.calls % st.cfg["check_steps"] == 0:
        line = {"step": st.calls, "rank": _rank()}
        s = torch.cat(st.samples) if st.samples else torch.zeros((0, 5)); st.samples = []
        for name, sel in (("all", torch.ones(len(s), dtype=torch.bool)), ("gt", s[:, 2] > 0.5), ("recon", s[:, 2] <= 0.5)):
            c = s[sel]; y = c[c[:, 3] > 0.5]; t = y[y[:, 4] > 0.5]           # c: candidates · y: yaw passed · t: also on the beam (the term's samples)
            g = {"n_cand": int(len(c)), "yaw_pass": round(float(len(y)) / len(c), 4) if len(c) else None,
                 "on_beam_of_yaw_pass": round(float(len(t)) / len(y), 4) if len(y) else None,
                 "median_abs_dy_m_cand": round(float(c[:, 0].median()), 5) if len(c) else None, "n": int(len(t)),
                 "at_clip_share": round(float((t[:, 0] >= 0.099).float().mean()), 4) if len(t) else None}
            if len(t):
                g.update({"median_abs_dy_m": round(float(t[:, 0].median()), 5), "term_mean": round(float(t[:, 1].mean()), 6),
                          "term_mean_weighted": round(float(t[:, 1].mean()) * st.cfg["weight"], 6)})
            line[name] = g
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
    print(f"EX42_BEAM_CENTER where=start weight={cfg['weight']} form={cfg['form']} {width} x={list(cfg['x'])} yaw_max={cfg['yaw']} kind=A/balance_beams "
          f"dy=root_y-tile_origin_y check_steps={cfg['check_steps']} outside_START=1", flush=True)
    return True
