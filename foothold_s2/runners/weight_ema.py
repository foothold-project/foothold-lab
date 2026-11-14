"""Exponential moving average of the policy and perception weights, kept beside training (candidate, OFF by default).

Why: the mean action at low forward speed swings by 0.2 to 0.6 between two saves (v28c m600 0.98, m650 0.40) while every
training record stays flat. An average of the last ~100 updates (decay 0.99) is a smoother checkpoint to measure and to keep.

Turn on: set POLICY_EMA_DECAY below to a number in (0, 1), e.g. 0.99 (per PPO update). Nothing else changes:
  * training never reads the average (weights, optimizer, rng, rollouts are untouched; off = no object is built);
  * every save (model_N.pt) also writes model_N_ema.pt in the same folder: same format as model_N.pt (loadable by the same
    code), model_state_dict / perception_state_dict hold the averaged parameters, buffers (normalizer statistics) are the live ones;
  * model_N.pt (and latest.pt) then carry a policy_ema entry so a resume continues the average (see restore()).
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn

POLICY_EMA_DECAY = None   # OFF. Lead 11/15 00:25 suggested 0.99 per update.
EMA_FILE_SUFFIX = "_ema"  # model_N.pt -> model_N_ema.pt (never matches the model_(\d+)\.pt patterns of the watchers)


def ema_file_name(iteration: int) -> str:
    return f"model_{int(iteration)}{EMA_FILE_SUFFIX}.pt"


class WeightEma:
    """Shadow copies of the floating parameters of named modules; buffers are not averaged."""

    def __init__(self, modules: dict[str, nn.Module], decay: float):
        if not isinstance(decay, (int, float)) or not 0.0 < decay < 1.0:
            raise ValueError("POLICY_EMA_DECAY must be a number in (0, 1)")
        self.modules, self.decay, self.updates, self.skipped = dict(modules), float(decay), 0, 0
        self.shadow = {name: {k: p.detach().clone() for k, p in m.named_parameters() if p.is_floating_point()}
                       for name, m in self.modules.items()}

    def _pairs(self):
        for name, module in self.modules.items():
            params = dict(module.named_parameters())
            keys = list(self.shadow[name])
            yield [self.shadow[name][k] for k in keys], [params[k].detach() for k in keys]

    @torch.no_grad()
    def update(self) -> bool:
        """shadow += (1 - decay) * (param - shadow). A non-finite parameter skips the whole step (the shadow stays clean)."""
        if not all(bool(torch.isfinite(p).all()) for _, live in self._pairs() for p in live):
            self.skipped += 1
            return False
        for shadow, live in self._pairs():
            if shadow:
                torch._foreach_lerp_(shadow, live, 1.0 - self.decay)
        self.updates += 1
        return True

    def module_state(self, name: str) -> dict:
        """state_dict of the module with the averaged parameters (buffers live), detached copies."""
        state = {k: v.detach().clone() for k, v in self.modules[name].state_dict().items()}
        for key, value in self.shadow[name].items():
            state[key] = value.clone()
        return state

    def save_state(self) -> dict:
        return {"decay": self.decay, "updates": self.updates, "skipped": self.skipped,
                "shadow": {n: {k: v.clone() for k, v in d.items()} for n, d in self.shadow.items()}}

    def restore(self, saved: dict | None) -> str:
        """Continue a saved average. No entry, another decay or another parameter set: start again from the live weights
        (the constructor already did) and say so. Returns the status line for the log."""
        if not saved:
            return "start_from_loaded_weights (checkpoint has no policy_ema)"
        if not math.isclose(float(saved.get("decay", -1.0)), self.decay, rel_tol=0, abs_tol=1e-12):
            return f"start_from_loaded_weights (saved decay {saved.get('decay')} != {self.decay})"
        shadow = saved.get("shadow") or {}
        for name, mine in self.shadow.items():
            theirs = shadow.get(name) or {}
            if set(theirs) != set(mine) or any(tuple(theirs[k].shape) != tuple(mine[k].shape) for k in mine):
                return f"start_from_loaded_weights (saved parameters of {name} differ)"
        for name, mine in self.shadow.items():
            for key in mine:
                mine[key].copy_(shadow[name][key])
        self.updates, self.skipped = int(saved.get("updates", 0)), int(saved.get("skipped", 0))
        return f"continued (updates {self.updates})"
