"""EX-42 hip L1 (`basic_hip_pos_penalty_l1`) at a lower weight on sparse-column envs only (lead 2026-11-21 21:35 (1), ledger 29f368ce8 (2)).
Off by default: only with EX42_HIP_SPARSE=1. Off, the env config is the same bytes (the term keeps its own function).

Why: the hip L1 term is not in START (the paper's joint error term is a different form); on narrow beams it holds the hips near the
default stance, which may keep the hind feet wide. The cut goes on sparse columns only so the continuous terrain keeps the canon 3 term.

    sparse env  = its terrain column is not family A with a continuous kind or flat (A sparse kinds and every B..E column)
    weight      = EX42_HIP_SPARSE_WEIGHT on sparse envs (<= 0, default 0, e.g. -0.01), the term's own weight elsewhere

The live adjustment cells change whole-term weights only (ex42_segment_adjust.apply_reward_params, ENV_WEIGHT_CELLS), and the hip
weight comes from the stage reward table (ex41 _sync_rewards may set it), so the mask lives in the term function: on sparse envs the
value is scaled by sparse_weight / current term weight (read from the reward manager at each call, so a stage table change keeps the
sparse weight exact). No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

TERM = "basic_hip_pos_penalty_l1"
ENV_SWITCH = "EX42_HIP_SPARSE"
WEIGHT_ENV = "EX42_HIP_SPARSE_WEIGHT"
STATE = "_ex42_hip_sparse_mask"


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    if value != "1" and os.environ.get(WEIGHT_ENV, "") != "":
        raise ValueError(f"{WEIGHT_ENV} is set but {ENV_SWITCH} is not 1")
    return value == "1"


def sparse_weight() -> float:
    raw = os.environ.get(WEIGHT_ENV, "")
    try:
        w = float(raw) if raw != "" else 0.0
    except ValueError:
        raise ValueError(f"{WEIGHT_ENV} must be a number (got {raw!r})") from None
    if not math.isfinite(w) or w > 0.0:
        raise ValueError(f"{WEIGHT_ENV} must be finite and <= 0 (a penalty weight, got {raw!r})")
    return w


def sparse_columns(table) -> torch.Tensor:
    from foothold_s2.terrains import columns as cols
    continuous = set(cols.CONTINUOUS) | {"flat"}
    return torch.tensor([not (row["family"] == "A" and row["kind"] in continuous) for row in table], dtype=torch.bool)


def sparse_envs(env) -> torch.Tensor:
    raw = getattr(env, "unwrapped", env)
    mask = getattr(raw, STATE, None)
    if mask is None:
        table = getattr(raw, "_ex42_column_table", None)
        if table is None:
            raise ValueError("EX-42 hip sparse needs the column table (raw._ex42_column_table) on the environment")
        mask = sparse_columns(table).to(env.device)
        setattr(raw, STATE, mask)
    columns = env.scene.terrain.terrain_types.long().to(mask.device)
    if bool(((columns < 0) | (columns >= len(mask))).any()):
        raise ValueError("EX-42 hip sparse: a terrain column is outside the column table")
    return mask[columns]


def scale(term_weight: float, w_sparse: float, sparse: torch.Tensor) -> torch.Tensor:
    """(N,) factor on the term value: w_sparse / term_weight on sparse envs, 1 elsewhere (weight 0: the term is off anyway)."""
    factor = 0.0 if term_weight == 0.0 else w_sparse / term_weight
    one = torch.ones(sparse.shape, dtype=torch.float32, device=sparse.device)
    return torch.where(sparse, one * factor, one)


def wrap(func, w_sparse: float):
    def hip_sparse_term(env, **params):
        value = func(env, **params)
        weight = float(getattr(env, "unwrapped", env).reward_manager.get_term_cfg(TERM).weight)
        return value * scale(weight, w_sparse, sparse_envs(env)).to(value.device)
    hip_sparse_term.ex42_hip_sparse = w_sparse
    hip_sparse_term.__wrapped__ = func
    return hip_sparse_term


def register(env_cfg) -> bool:
    """Before the env is built: wrap the hip term's function when the switch is on. True when wrapped (one start line)."""
    if not enabled():
        return False
    term = getattr(env_cfg.rewards, TERM, None)
    if term is None:
        raise ValueError(f"{ENV_SWITCH}=1 but the env config has no {TERM} term")
    if getattr(term.func, "ex42_hip_sparse", None) is not None:
        return False
    w = sparse_weight()
    if term.weight < 0 and w < term.weight:
        raise ValueError(f"{WEIGHT_ENV} {w} is stronger than the term weight {term.weight} (this cell only lowers the penalty)")
    term.func = wrap(term.func, w)
    print(f"EX42_HIP_SPARSE where=start term={TERM} weight={term.weight} sparse_weight={w} sparse=not(A continuous or flat)", flush=True)
    return True
