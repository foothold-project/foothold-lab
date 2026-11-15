"""EX-42 slow-command forward progress (`ex42_slow_progress`), registered at weight 0 (decisions.tsv 2026-11-14 01:21,
ledger commit 06d4a1ae; a new reward term, so its limits stay [0, 0] until the team lead approves them).

Why: under a 0.1 m/s command the policy has no gait that slow. Walking at its slowest stable speed (about 0.2 m/s)
and standing still are the same distance from the command, so `track_lin_vel` and `ex42_slow_track` pay both the
same and only the motion penalties differ: standing wins (m750: 63 of 64 envs stand under forward 0.1). This term is
one-sided. It pays for speed along the commanded direction up to the commanded speed and nothing beyond it:

    active = the slow_track band (speed_min <= |c_xy| < speed_max), heading envs included, flag envs excluded,
             a free env with a turn command excluded
    value  = clip(v_xy . c_hat, -|c_xy|, |c_xy|) / |c_xy| * taper(|c_xy|)        where active, else 0
    taper  = 1 up to `taper_from` (0.25 m/s), then linear down to 0 at speed_max (0.3 m/s)

Standing still gives 0, walking at the commanded speed or faster gives 1, moving backwards gives a negative value
(down to -1), so rocking back and forth averages to about 0 instead of being paid (lead 2026-11-14 01:27). The taper
removes the jump at the upper edge of the band. Overshoot is not paid here and is still charged by the tracking terms.

No Kit import at module level.
"""
from __future__ import annotations

import torch

from foothold_s2.rewards.ex42_slow_track import DEFAULTS as BAND_DEFAULTS

TERM = "ex42_slow_progress"
DEFAULTS = {"speed_min": BAND_DEFAULTS["speed_min"], "speed_max": BAND_DEFAULTS["speed_max"], "taper_from": 0.25}


def slow_progress_value(vel_xy, cmd_xy, cmd_wz, *, speed_min, speed_max, taper_from=None, excluded=None, turn_exempt=None):
    """(N,) value from body-frame planar velocity (N, 2), planar command (N, 2), turn command (N,), the (N,) mask of the
    envs left out (flag envs) and the (N,) mask of the envs whose turn command does not count (heading envs)."""
    if not 0.0 < speed_min < speed_max:
        raise ValueError("slow progress needs 0 < speed_min < speed_max")
    taper_from = speed_max if taper_from is None else float(taper_from)
    if not speed_min <= taper_from <= speed_max:
        raise ValueError("slow progress needs speed_min <= taper_from <= speed_max")
    if not (torch.isfinite(cmd_xy).all() and torch.isfinite(cmd_wz).all()):
        raise ValueError("slow progress: nonfinite command")
    speed = torch.linalg.vector_norm(cmd_xy, dim=-1)
    straight = cmd_wz.abs() < 1e-6
    if turn_exempt is not None:
        straight = straight | turn_exempt.bool()
    active = (speed >= speed_min) & (speed < speed_max) & straight
    if excluded is not None:
        active &= ~excluded.bool()
    if (active & ~torch.isfinite(vel_xy).all(-1)).any():
        raise ValueError("slow progress: nonfinite active velocity")
    safe_vel = torch.where(active[:, None], vel_xy, torch.zeros_like(vel_xy))
    safe_speed = speed.clamp_min(speed_min)
    along = (safe_vel * cmd_xy).sum(-1) / safe_speed                       # speed along the commanded direction
    value = torch.maximum(torch.minimum(along, safe_speed), -safe_speed) / safe_speed
    if taper_from < speed_max:
        value = value * ((speed_max - speed) / (speed_max - taper_from)).clamp(0.0, 1.0)
    return torch.where(active, value, torch.zeros_like(speed))


def slow_progress_term(env, command_name, speed_min, speed_max, taper_from=None, include_heading=True):
    """Reward manager term. The reward manager does not call it while its weight is 0."""
    command = env.command_manager.get_command(command_name)
    term = env.command_manager.get_term(command_name)
    heading, flag = getattr(term, "heading", None), getattr(term, "is_flag_env", None)
    if heading is None or flag is None:
        raise ValueError("slow progress needs the command term's heading and is_flag_env masks")
    velocity = env.scene["robot"].data.root_lin_vel_b[:, :2]
    return slow_progress_value(velocity, command[:, :2], command[:, 2], speed_min=float(speed_min),
                               speed_max=float(speed_max), taper_from=taper_from,
                               excluded=flag.bool() if include_heading else heading.bool() | flag.bool(),
                               turn_exempt=heading.bool() if include_heading else None)


def register(env_cfg, term_cfg_class=None) -> bool:
    """Before the env is built: add the term at weight 0 unless the config already has it. True when it was added."""
    if hasattr(env_cfg.rewards, TERM):
        return False
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    setattr(env_cfg.rewards, TERM, term_cfg_class(func=slow_progress_term, weight=0.0,
                                                  params={"command_name": "base_velocity", **DEFAULTS,
                                                          "include_heading": True}))
    return True
