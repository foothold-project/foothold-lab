"""EX-42 BC prior loss on slow-command samples (lead 2026-11-21 17:21, ledger b4037bbbc, literature note
LIT-FORGETTING-HEADING-1121.md section 2 PPF eq. 6-7 and section 5 row 5). Off by default.

    L = L_PPO + beta * mean_{s in slow} || mu_theta(s) - mu_prior(s) ||^2

mu_prior is the mean action of a frozen parent actor read from EX42_BC_PRIOR_CKPT (for example rf model_250); beta is
EX42_BC_PRIOR_BETA (lead 17:24: an env value for now, the live adjustment cell is a second step). The slow samples are
the rows whose planar command is in the slow_track band, 0.1 <= |c_xy| < 0.3 m/s (the actor input starts with o45:
ang_vel 0:3, gravity 3:6, command 6:9, the layout the critic mirror uses). Only the EX-41 critic-mirror update loop
(CriticMirrorPPO._update_impl, the E2 path) carries the term; the installed PPO.update path refuses it.

No Kit import at module level.
"""
from __future__ import annotations

import copy
import math
import os
from pathlib import Path

import torch

CKPT_ENV = "EX42_BC_PRIOR_CKPT"
BETA_ENV = "EX42_BC_PRIOR_BETA"
CMD_SLICE = slice(6, 8)          # vx, vy of the command in the actor input (o45 order)
SPEED_MIN, SPEED_MAX = 0.1, 0.3  # the slow_track band (ex42-reward-adjust-limits slow_track_speed_min / _max)
LOG = "EX42_BC_PRIOR"


def settings() -> dict | None:
    """None when off (neither value set). Both or neither: one without the other is a mistake."""
    ckpt, beta = os.environ.get(CKPT_ENV, ""), os.environ.get(BETA_ENV, "")
    if not ckpt and not beta:
        return None
    if not ckpt or not beta:
        raise ValueError(f"{CKPT_ENV} and {BETA_ENV} go together (got ckpt {bool(ckpt)}, beta {bool(beta)})")
    try:
        value = float(beta)
    except ValueError:
        raise ValueError(f"{BETA_ENV} must be a number (got {beta!r})") from None
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{BETA_ENV} must be finite and >= 0 (got {beta!r})")
    path = Path(ckpt)
    if not path.is_file():
        raise ValueError(f"{CKPT_ENV} is not a file: {ckpt}")
    return {"ckpt": str(path), "beta": value}


def load_prior(policy, ckpt: str, device) -> torch.nn.Module:
    """A frozen copy of `policy` with the parent's weights (strict: the same architecture, else refused)."""
    state = torch.load(ckpt, map_location=device, weights_only=False)
    weights = state.get("model_state_dict") if isinstance(state, dict) else None
    if not isinstance(weights, dict):
        raise ValueError(f"{CKPT_ENV} has no model_state_dict: {ckpt}")
    prior = copy.deepcopy(policy)
    prior.load_state_dict(weights, strict=True)
    prior.eval()
    for p in prior.parameters():
        p.requires_grad_(False)
    return prior


def slow_mask(actor_in: torch.Tensor) -> torch.Tensor:
    speed = torch.linalg.vector_norm(actor_in[:, CMD_SLICE], dim=-1)
    return (speed >= SPEED_MIN) & (speed < SPEED_MAX)


def bc_loss(mu: torch.Tensor, prior_mu: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, int]:
    """(loss, samples). With no slow sample the loss is an exact 0 that keeps the graph (no gradient)."""
    n = int(mask.sum())
    if n == 0:
        return (mu * 0.0).sum(), 0
    return (mu[mask] - prior_mu[mask].detach()).square().sum(-1).mean(), n
