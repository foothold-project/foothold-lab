"""EX-42 rx2ps2: wake the two posture-command input columns (lead 2026-11-22 07:41 ledger 8ee347dad · planner 07:41). OUTSIDE START.
Two switches, both off by default (off = no hook, no weight change, the same bytes as before):

  EX42_POSTURE_COL_LR=<x>   the PPO optimizer's update of actor.0.weight columns 96, 97 (posture inputs: height change h - H0, roll) and of
                            critic.0.weight columns 664, 665 is multiplied by x (planner: 20). A step pre-hook keeps those columns, the post-hook
                            sets col = before + x * (after - before): every other column and layer moves as before, and the factor rides on the
                            step the optimizer actually took (Adam's own scaling and the adaptive learning rate change it the same for all).
  EX42_POSTURE_COL_INIT=1   once, on a fresh start from the parent (not on a resume of the same OUT), those columns are set to small random
                            values: N(0, 1) directions scaled to 1/4 of the median norm of the other input columns of the same layer
                            (generator seeded from EX42_SEED so both ranks draw the same; the parent left them 0). With a posture input of 0
                            the layer output is unchanged, so every env without a posture command acts exactly as before.

Why: planner 07:41: the parent (canonical 3) actor.0.weight columns 96, 97 start at 0 and rx2ps m50 has them at 5~8 % of the other columns:
the policy barely reads the posture command, so the posture reward has nothing to climb on.

Lines: EX42_POSTURE_COLS where=start (switches · column norms before / after · median of the others); EX42_POSTURE_COLS_CHECK every 50
updates (column norms, and the mean |action change| on the last rollout batch when the posture input is set to height -0.2, roll 0.5
instead of 0). No Kit import at module level.
"""
from __future__ import annotations

import json
import math
import os

import torch

LR_SWITCH, INIT_SWITCH = "EX42_POSTURE_COL_LR", "EX42_POSTURE_COL_INIT"
ACTOR_COLS, CRITIC_COLS = (96, 97), (664, 665)
INIT_FRACTION = 0.25
PROBE_CMD = (-0.2, 0.5)                    # height change (m) · roll (rad) for the action-change probe
CHECK_EVERY = 50


def settings() -> dict:
    raw = os.environ.get(LR_SWITCH, "")
    lr = None
    if raw != "":
        try:
            lr = float(raw)
        except ValueError:
            raise ValueError(f"{LR_SWITCH} must be a number (got {raw!r})") from None
        if not (math.isfinite(lr) and 1.0 <= lr <= 100.0):
            raise ValueError(f"{LR_SWITCH} must be in [1, 100] (got {raw!r})")
    init = os.environ.get(INIT_SWITCH, "")
    if init not in ("", "0", "1"):
        raise ValueError(f"{INIT_SWITCH} must be 0 or 1 (got {init!r})")
    return {"lr": lr, "init": init == "1"}


def first_layers(policy):
    return policy.actor[0], policy.critic[0]


def col_norms(weight: torch.Tensor, cols) -> list:
    return [round(float(weight[:, c].norm()), 6) for c in cols]


def other_median(weight: torch.Tensor, cols) -> float:
    keep = [c for c in range(weight.shape[1]) if c not in cols]
    return float(weight[:, keep].norm(dim=0).median())


@torch.no_grad()
def init_columns(policy, seed: int) -> dict:
    """Set the posture columns to N(0,1) directions with norm INIT_FRACTION x median(other column norms). Returns the before / after record."""
    gen = torch.Generator(device="cpu").manual_seed(int(seed))
    rec = {}
    for name, layer, cols in (("actor", first_layers(policy)[0], ACTOR_COLS), ("critic", first_layers(policy)[1], CRITIC_COLS)):
        w = layer.weight
        if w.shape[1] <= max(cols):
            raise ValueError(f"EX-42 posture columns: {name}.0.weight has {w.shape[1]} inputs, needs column {max(cols)}")
        med = other_median(w, cols)
        before = col_norms(w, cols)
        for c in cols:
            d = torch.randn(w.shape[0], generator=gen)
            w[:, c] = (d / d.norm() * INIT_FRACTION * med).to(w.device, w.dtype)
        rec[name] = {"median_other": round(med, 6), "before": before, "after": col_norms(w, cols)}
    return rec


class ColumnLR:
    """Optimizer step hooks: the update of the posture columns times `mult` (see module doc)."""

    def __init__(self, optimizer, policy, mult: float):
        self.mult, self.saved = float(mult), None
        a, c = first_layers(policy)
        self.targets = [(a.weight, list(ACTOR_COLS)), (c.weight, list(CRITIC_COLS))]
        owned = {id(p) for g in optimizer.param_groups for p in g["params"]}
        if any(id(w) not in owned for w, _ in self.targets):
            raise ValueError("EX-42 posture column LR: the first actor / critic layer is not in the PPO optimizer")
        self.handles = [optimizer.register_step_pre_hook(self._pre), optimizer.register_step_post_hook(self._post)]

    def _pre(self, optimizer, args, kwargs):
        self.saved = [w.detach()[:, cols].clone() for w, cols in self.targets]

    @torch.no_grad()
    def _post(self, optimizer, args, kwargs):
        for (w, cols), before in zip(self.targets, self.saved):
            w[:, cols] = before + self.mult * (w[:, cols] - before)
        self.saved = None

    def remove(self):
        for h in self.handles:
            h.remove()


class PostureCols:
    """Runner glue: attach(), maybe_init() at the start of learn(), after_update(it) after every PPO update."""

    def __init__(self, alg, policy, cfg: dict):
        self.alg, self.policy, self.cfg = alg, policy, cfg
        self.lr = ColumnLR(alg.optimizer, policy, cfg["lr"]) if cfg["lr"] is not None else None
        self.last_x = None
        self._hook = policy.actor.register_forward_pre_hook(self._keep_input)
        self.init_record = None

    def _keep_input(self, module, args):
        x = args[0]
        if x.dim() == 2 and x.shape[1] > max(ACTOR_COLS):
            self.last_x = x.detach()[:512].clone()

    def maybe_init(self, fresh_from_parent: bool, seed: int) -> None:
        a, c = first_layers(self.policy)
        rec = None
        if self.cfg["init"] and fresh_from_parent:
            rec = init_columns(self.policy, seed)
        self.init_record = rec
        print("EX42_POSTURE_COLS where=start " + json.dumps({
            "lr_mult": self.cfg["lr"], "init": self.cfg["init"], "init_done": rec is not None, "fresh_from_parent": bool(fresh_from_parent),
            "actor_cols": list(ACTOR_COLS), "critic_cols": list(CRITIC_COLS), "init_fraction": INIT_FRACTION, "init": rec,
            "actor_norms": col_norms(a.weight, ACTOR_COLS), "actor_median_other": round(other_median(a.weight, ACTOR_COLS), 6),
            "critic_norms": col_norms(c.weight, CRITIC_COLS), "critic_median_other": round(other_median(c.weight, CRITIC_COLS), 6),
            "outside_START": 1}), flush=True)

    @torch.no_grad()
    def action_change(self) -> float | None:
        if self.last_x is None:
            return None
        x0 = self.last_x.clone(); x0[:, list(ACTOR_COLS)] = 0.0
        x1 = x0.clone(); x1[:, ACTOR_COLS[0]], x1[:, ACTOR_COLS[1]] = PROBE_CMD
        return round(float((self.policy.actor(x1) - self.policy.actor(x0)).abs().mean()), 6)

    def after_update(self, it: int) -> None:
        if (it + 1) % CHECK_EVERY:
            return
        a, c = first_layers(self.policy)
        print("EX42_POSTURE_COLS_CHECK " + json.dumps({
            "it": it + 1, "actor_norms": col_norms(a.weight, ACTOR_COLS), "actor_median_other": round(other_median(a.weight, ACTOR_COLS), 6),
            "critic_norms": col_norms(c.weight, CRITIC_COLS), "critic_median_other": round(other_median(c.weight, CRITIC_COLS), 6),
            "probe_cmd": list(PROBE_CMD), "mean_abs_action_change": self.action_change(),
            "rank": int(os.environ.get("RANK", "0"))}), flush=True)


def attach(alg, policy) -> PostureCols | None:
    cfg = settings()
    if cfg["lr"] is None and not cfg["init"]:
        return None
    return PostureCols(alg, policy, cfg)
