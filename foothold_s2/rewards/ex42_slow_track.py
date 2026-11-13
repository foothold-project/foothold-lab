"""EX-42 slow-command relative tracking (`ex42_slow_track`), registered at weight 0 (decisions.tsv 2026-11-13 15:30).

Why: the tracking reward `track_lin_vel` is 2.0 * exp(-|v - c|^2 / std^2). Under a 0.1 m/s command standing still loses
0.078 at std 0.5 and 0.157 at std 0.35, less than the motion penalties a walking robot pays, so the policy stands
(forward 0.1 progress ratio at or below 0.084 at every E1 boundary, 0.112 at the parent m13250). This term measures the
error relative to the commanded speed, so that walking as told is worth the same under 0.1 m/s as under 0.25 m/s:

    active = speed_min <= |c_xy| < speed_max  and  the turn command is zero
             and the env is neither a heading env nor a flag env
    value  = exp(-(|v_xy - c_xy| / |c_xy|)^2 / sigma^2)      where active, else 0

Standing still gives exp(-1 / sigma^2) (0.018 at sigma 0.5), walking exactly as told gives 1.

Contract (lead 2026-11-13 15:41):
* `c_xy` is the planar command vector, so slow side, back and diagonal commands count like slow forward ones.
* The lower edge is inside the band (a command of exactly 0.1 m/s is active), the upper edge is outside it.
* A heading env (the command term's `heading` mask: its turn command comes from the heading controller) and a flag env
  (`is_flag_env`: its command comes from the flag state machine) are excluded whatever their command is, and so is every
  env whose turn command is not zero.

Draft formula of planner-lx; the constants are reward cells (plan row and segment adjustment), to be set from
analyst-lx's measurements. No Kit import at module level.
"""
from __future__ import annotations

import torch

DEFAULTS = {"speed_min": 0.1, "speed_max": 0.3, "sigma": 0.5}
TERM = "ex42_slow_track"


def slow_track_value(vel_xy, cmd_xy, cmd_wz, *, speed_min, speed_max, sigma, excluded=None):
    """(N,) value of the term from body-frame planar velocity (N, 2), planar command (N, 2), turn command (N,) and the
    (N,) mask of the envs the contract leaves out (heading envs, flag envs)."""
    if not (0.0 < speed_min < speed_max and sigma > 0.0):
        raise ValueError("slow track needs 0 < speed_min < speed_max and sigma > 0")
    if not (torch.isfinite(cmd_xy).all() and torch.isfinite(cmd_wz).all()):
        raise ValueError("slow track: nonfinite command")
    speed = torch.linalg.vector_norm(cmd_xy, dim=-1)
    active = (speed >= speed_min) & (speed < speed_max) & (cmd_wz.abs() < 1e-6)
    if excluded is not None:
        active &= ~excluded.bool()
    if (active & ~torch.isfinite(vel_xy).all(-1)).any():
        raise ValueError("slow track: nonfinite active velocity")
    safe_vel = torch.where(active[:, None], vel_xy, torch.zeros_like(vel_xy))
    relative = torch.linalg.vector_norm(safe_vel - cmd_xy, dim=-1) / speed.clamp_min(speed_min)
    return torch.where(active, torch.exp(-(relative / sigma) ** 2), torch.zeros_like(speed))


def slow_track_term(env, command_name, speed_min, speed_max, sigma):
    """Reward manager term. The reward manager does not call it while its weight is 0."""
    command = env.command_manager.get_command(command_name)
    term = env.command_manager.get_term(command_name)
    heading, flag = getattr(term, "heading", None), getattr(term, "is_flag_env", None)
    if heading is None or flag is None:
        raise ValueError("slow track needs the command term's heading and is_flag_env masks")
    velocity = env.scene["robot"].data.root_lin_vel_b[:, :2]
    return slow_track_value(velocity, command[:, :2], command[:, 2], speed_min=float(speed_min),
                            speed_max=float(speed_max), sigma=float(sigma), excluded=heading.bool() | flag.bool())


def register(env_cfg, term_cfg_class=None) -> bool:
    """Before the env is built: add the term at weight 0 unless the config already has it. True when it was added."""
    if hasattr(env_cfg.rewards, TERM):
        return False
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    setattr(env_cfg.rewards, TERM, term_cfg_class(func=slow_track_term, weight=0.0,
                                                  params={"command_name": "base_velocity", **DEFAULTS}))
    return True
