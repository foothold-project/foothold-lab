"""EX-42 slow-command overspeed penalty (`ex42_slow_overspeed`), candidate C of the E2 m1100 overspeed incident
(lead 2026-11-19 23:03, planner OVERSPEED-M1100-1119). Registered at weight 0, so nothing changes until the team lead approves
a weight (limits [-1.0, 0]; the weight is negative: this is a penalty). It is the mirror of `ex42_slow_progress`:

    active = the slow_track band (speed_min <= |c_xy| < speed_max), straight command (heading envs count), and not
             a flag env, not a gap / sparse column env
    value  = -clip(v_xy . c_hat - |c_xy|, 0, |c_xy|) / |c_xy|        where active, else 0

Speed along the commanded direction at or below the command gives 0, an overshoot of |c| (twice the command) gives -1, more
is clipped at -1, being too slow gives 0 (slow_progress already charges that). One side only, so the two terms together push the
speed to the command from both sides. There is no taper at the upper band edge (the lead's formula has none).

Gap / sparse columns: the project's `is_sparse_name` rule (A: stepping stones, balance and stepping beams, gaps; every column of
the B, C, D, E families), read from the column table the entry puts on the env (`_ex42_column_table`). A missing table is an error,
never a silent "no column excluded".

No Kit import at module level.
"""
from __future__ import annotations

import torch

from foothold_s2.rewards.ex42_slow_track import DEFAULTS as BAND_DEFAULTS

TERM = "ex42_slow_overspeed"
DEFAULTS = {"speed_min": BAND_DEFAULTS["speed_min"], "speed_max": BAND_DEFAULTS["speed_max"]}


def slow_overspeed_value(vel_xy, cmd_xy, cmd_wz, *, speed_min, speed_max, excluded=None, turn_exempt=None):
    """(N,) value (<= 0) from body-frame planar velocity (N, 2), planar command (N, 2), turn command (N,), the (N,) mask of the
    envs left out (flag envs, gap / sparse columns) and the (N,) mask of the envs whose turn command does not count (heading envs)."""
    if not 0.0 < speed_min < speed_max:
        raise ValueError("slow overspeed needs 0 < speed_min < speed_max")
    if not (torch.isfinite(cmd_xy).all() and torch.isfinite(cmd_wz).all()):
        raise ValueError("slow overspeed: nonfinite command")
    speed = torch.linalg.vector_norm(cmd_xy, dim=-1)
    straight = cmd_wz.abs() < 1e-6
    if turn_exempt is not None:
        straight = straight | turn_exempt.bool()
    active = (speed >= speed_min) & (speed < speed_max) & straight
    if excluded is not None:
        active &= ~excluded.bool()
    if (active & ~torch.isfinite(vel_xy).all(-1)).any():
        raise ValueError("slow overspeed: nonfinite active velocity")
    safe_vel = torch.where(active[:, None], vel_xy, torch.zeros_like(vel_xy))
    safe_speed = speed.clamp_min(speed_min)
    along = (safe_vel * cmd_xy).sum(-1) / safe_speed
    value = -(along - safe_speed).clamp_min(0.0).minimum(safe_speed) / safe_speed
    return torch.where(active, value, torch.zeros_like(speed))


def sparse_env_mask(env):
    """(N,) bool: the env's terrain column is a gap / sparse column (`is_sparse_name` on the entry's column table)."""
    from foothold_s2.runners.map_switch import is_sparse_name

    table = getattr(env, "_ex42_column_table", None)
    if table is None:
        raise ValueError("slow overspeed needs the column table (env._ex42_column_table) to leave gap / sparse columns out")
    names = [r["kind"] if r["family"] == "A" else "%s/%s" % (r["family"], r["kind"]) for r in table]
    types = env.scene.terrain.terrain_types.long()
    if bool(((types < 0) | (types >= len(names))).any()):
        raise ValueError("slow overspeed: a terrain column is outside the column table")
    lut = torch.tensor([is_sparse_name(n) for n in names], dtype=torch.bool, device=types.device)
    return lut[types]


def slow_overspeed_term(env, command_name, speed_min, speed_max, include_heading=True):
    """Reward manager term. The reward manager does not call it while its weight is 0."""
    command = env.command_manager.get_command(command_name)
    term = env.command_manager.get_term(command_name)
    heading, flag = getattr(term, "heading", None), getattr(term, "is_flag_env", None)
    if heading is None or flag is None:
        raise ValueError("slow overspeed needs the command term's heading and is_flag_env masks")
    velocity = env.scene["robot"].data.root_lin_vel_b[:, :2]
    out = flag.bool() | sparse_env_mask(env)
    return slow_overspeed_value(velocity, command[:, :2], command[:, 2], speed_min=float(speed_min), speed_max=float(speed_max),
                                excluded=out if include_heading else out | heading.bool(),
                                turn_exempt=heading.bool() if include_heading else None)


def register(env_cfg, term_cfg_class=None) -> bool:
    """Before the env is built: add the term at weight 0 unless the config already has it. True when it was added."""
    if hasattr(env_cfg.rewards, TERM):
        return False
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    setattr(env_cfg.rewards, TERM, term_cfg_class(func=slow_overspeed_term, weight=0.0,
                                                  params={"command_name": "base_velocity", **DEFAULTS, "include_heading": True}))
    return True
