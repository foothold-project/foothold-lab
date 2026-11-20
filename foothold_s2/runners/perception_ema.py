"""v28u: the averaged perception weights the actor sees (candidate C). Helpers around weight_ema.WeightEma (taken as is from PR #824).

Why: the speed estimate of the perception module drifts with every perception update (planner 10:38: v28p m1600 0.805 then m1650 0.583,
bias +0.006 then +0.022). With PERCEPTION_EMA_DECAY > 0 the rollout asks an averaged copy of the perception module for est; the
perception loss still updates the online weights. model_N.pt carries both: perception_state_dict (online, what a resume loads) and
perception_ema (the shadow parameters and the decay; what an evaluation reads when it is there).
"""

from __future__ import annotations

import math

import torch

NAME = "perception"          # the key of the module inside WeightEma (modules={"perception": ...}) and inside the saved shadow


def usable_decay(decay) -> bool:
    return isinstance(decay, (int, float)) and not isinstance(decay, bool) and 0.0 < float(decay) < 1.0


def ema_state_dict(online_state: dict, saved) -> tuple[dict | None, str]:
    """The perception state_dict with the averaged parameters put over the online ones (buffers stay the online ones).

    saved is the checkpoint's perception_ema entry. Returns (state, "") when it can be used, else (None, reason): the caller then keeps the
    online weights and says why. Every averaged parameter must exist in the online state with the same shape, none may be non-finite."""
    if not isinstance(saved, dict) or not saved:
        return None, "no perception_ema in the checkpoint"
    shadow = (saved.get("shadow") or {}).get(NAME)
    if not isinstance(shadow, dict) or not shadow:
        return None, "perception_ema has no shadow of the perception module"
    state = dict(online_state)
    for key, value in shadow.items():
        mine = online_state.get(key)
        if mine is None or tuple(mine.shape) != tuple(value.shape):
            return None, "perception_ema parameter %s does not match the online state" % key
        if not bool(torch.isfinite(value).all()):
            return None, "perception_ema parameter %s is not finite" % key
        state[key] = value.detach().clone().to(mine.dtype)
    return state, ""


def decay_of(saved) -> float | None:
    try:
        value = float(saved["decay"])
    except (TypeError, KeyError, ValueError):
        return None
    return value if math.isfinite(value) else None
