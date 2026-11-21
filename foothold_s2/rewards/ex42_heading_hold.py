"""EX-42 integrated heading error while the turn command is zero (`ex42_heading_hold`). Off by default: the term is
registered only when EX42_HEADING_HOLD=1 (lead 2026-11-21 17:21, ledger b4037bbbc, literature note
LIT-FORGETTING-HEADING-1121.md section 3 and 5 row 4), at the start weight EX42_HEADING_HOLD_WEIGHT (unset = 0, and the
reward manager does not call a weight 0 term). Lead 17:24: no live adjustment cell yet (the fence file and the plan SHA
stay as they are); that is a second step. Isaac Lab logs the term mean as Episode_Reward/ex42_heading_hold.

Why: `ex41_zero_yaw` charges the instantaneous |yaw rate|. Inside one step cycle the yaw wobble is larger than the mean
drift, so most of that charge goes to the wobble and little to the drift that turns the robot off a beam. This term
charges the drift itself: the body heading against the heading the robot had when it received the command.

    psi0   = body yaw when the command last changed (any of vx, vy, wz) or the episode started
    active = |wz command| < 1e-6, not a flag env (the flag gives wz), not a heading env (already closed loop)
    value  = -|wrap(psi - psi0)|  [rad]                                          where active, else 0

The value is a negative L1 (the ANYmal form 1 - 0.5|e| adds a constant the weight would carry; the negative form is 0
when the heading is held). psi0 is kept on the term's own state, the command term is not changed. A new command or a new
episode takes psi0 again, so a flag env that becomes a free env (or the other way) starts from where it stands.

No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

TERM = "ex42_heading_hold"
ENV_SWITCH = "EX42_HEADING_HOLD"
WEIGHT_ENV = "EX42_HEADING_HOLD_WEIGHT"
TURN_EPS = 1e-6
STATE = "_ex42_heading_hold_state"


def wrap(angle):
    return torch.remainder(angle + math.pi, 2.0 * math.pi) - math.pi


def heading_hold_value(yaw, command, psi0, *, excluded=None):
    """(N,) value from body yaw (N,), the command (N, 3) and the held heading (N,). `excluded` (N,) bool: flag or heading envs."""
    if not (torch.isfinite(command).all() and torch.isfinite(psi0).all()):
        raise ValueError("heading hold: nonfinite command or held heading")
    active = command[:, 2].abs() < TURN_EPS
    if excluded is not None:
        active = active & ~excluded.bool()
    if (active & ~torch.isfinite(yaw)).any():
        raise ValueError("heading hold: nonfinite active yaw")
    err = wrap(torch.where(active, yaw, psi0) - psi0).abs()
    return torch.where(active, -err, torch.zeros_like(err))


class HeadingHoldState:
    """psi0 and the command it was taken under, per env."""

    def __init__(self, num_envs, device):
        self.psi0 = torch.zeros(num_envs, device=device)
        self.command = torch.full((num_envs, 3), float("nan"), device=device)     # nan: the first call takes psi0

    def update(self, yaw, command, new_episode):
        """Take psi0 again where the command changed or the episode is new. Returns the (N,) mask of envs that took it."""
        changed = ~(command == self.command).all(-1) | new_episode.bool()
        self.psi0 = torch.where(changed, yaw, self.psi0)
        self.command = torch.where(changed[:, None], command, self.command)
        return changed


def heading_hold_term(env, command_name, include_stand=True):
    """Reward manager term. The reward manager does not call it while its weight is 0, so the state is not built then."""
    command = env.command_manager.get_command(command_name)
    term = env.command_manager.get_term(command_name)
    heading, flag = getattr(term, "heading", None), getattr(term, "is_flag_env", None)
    if heading is None or flag is None:
        raise ValueError("heading hold needs the command term's heading and is_flag_env masks")
    yaw = env.scene["robot"].data.heading_w
    state = getattr(env, STATE, None)
    if state is None:
        state = HeadingHoldState(env.num_envs, command.device)
        setattr(env, STATE, state)
    state.update(yaw, command[:, :3], env.episode_length_buf <= 1)       # the step after a reset counts 1
    excluded = heading.bool() | flag.bool()
    if not include_stand and getattr(term, "stand", None) is not None:
        excluded = excluded | term.stand.bool()
    return heading_hold_value(yaw, command[:, :3], state.psi0, excluded=excluded)


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    if value != "1" and os.environ.get(WEIGHT_ENV, "") != "":
        raise ValueError(f"{WEIGHT_ENV} is set but {ENV_SWITCH} is not 1")
    return value == "1"


def start_weight() -> float:
    """The stage-start weight (lead 17:24: an env value for now, the live adjustment cell is a second step). Unset = 0.
    The term value is <= 0, so a weight >= 0 charges the drift; a negative weight would pay it and is refused."""
    raw = os.environ.get(WEIGHT_ENV, "")
    try:
        weight = float(raw) if raw != "" else 0.0
    except ValueError:
        raise ValueError(f"{WEIGHT_ENV} must be a number (got {raw!r})") from None
    if not math.isfinite(weight) or weight < 0.0:
        raise ValueError(f"{WEIGHT_ENV} must be finite and >= 0 (got {raw!r})")
    return weight


def register(env_cfg, term_cfg_class=None) -> bool:
    """Before the env is built: add the term at the start weight when the switch is on and the config does not have it
    yet. True when it was added (one EX42_HEADING_HOLD start line). With the switch off nothing changes (the env config
    is the same bytes)."""
    if not enabled() or hasattr(env_cfg.rewards, TERM):
        return False
    weight = start_weight()
    if term_cfg_class is None:
        from isaaclab.managers import RewardTermCfg as term_cfg_class
    setattr(env_cfg.rewards, TERM, term_cfg_class(func=heading_hold_term, weight=weight,
                                                  params={"command_name": "base_velocity", "include_stand": True}))
    print(f"EX42_HEADING_HOLD where=start weight={weight} turn_eps={TURN_EPS} excluded=flag,heading", flush=True)
    return True
