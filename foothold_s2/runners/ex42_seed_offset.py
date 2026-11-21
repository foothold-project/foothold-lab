"""EX-42 seed offset for a different-seed pair of a stage run (lead 2026-11-22 08:35 ledger 30d8e881d). Off by default (EX42_SEED_OFFSET unset
or 0 = the same bytes as before: no reseed, the parent's seed).

Why: an EX-42 stage start takes the parent checkpoint's env_seed (train_start: agent_cfg.seed = parent env_seed, then + local rank) and
restores the parent's RNG state, so --seed / EX42_SEED changed nothing (rx2qcmd2 08:24 printed the same Environment seed as a 42 run).

On (offset N > 0): train_start adds N to the parent env_seed (so the env seed, and through it the env's own draws, differ), and at the start of
learn() the runner reseeds, after every restore, torch (CPU and CUDA), numpy, python random and the command generator with that seed
(env_seed + N + rank, the value Isaac prints as Environment seed). Start line: EX42_SEED_OFFSET where=start.
"""
from __future__ import annotations

import os
import random

ENV = "EX42_SEED_OFFSET"


def offset() -> int:
    raw = os.environ.get(ENV, "")
    if raw == "":
        return 0
    if not raw.isdigit() or not 0 <= int(raw) <= 1000:
        raise ValueError(f"{ENV} must be a whole number 0..1000 (got {raw!r})")
    return int(raw)


def reseed(seed: int, command_term=None) -> dict:
    """Reseed every RNG the rollout draws from. Returns what was reseeded (for the start line)."""
    import numpy as np
    import torch
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed % (2 ** 32))
    random.seed(seed)
    done = ["torch", "cuda" if torch.cuda.is_available() else "no_cuda", "numpy", "python"]
    gen = getattr(command_term, "gen", None)
    if gen is not None:
        gen.manual_seed(seed)
        done.append("command_gen")
    return {"seed": int(seed), "reseeded": done}
