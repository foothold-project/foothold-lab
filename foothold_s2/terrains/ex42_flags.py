"""Flag coordinates for the combined EX-42 mesh (planner 12:25: the S2 flag table was sized for 50 columns).

The EX-42 task is a plain ManagerBasedRLEnv, so the 50-column `Layout()` of `tasks/s2_env.py` is not on this path:
flags are the default straight line. What did not exist is a table sized by the MESH columns. The mesh builder may
store one in the combined npz as `flags` (rows, columns, K >= 4, 2) in world xy, NaN where a cell has none (continuous
cells, or a kind whose flags are not written yet). This module reads that table and serves it to the command term;
a NaN cell falls back to the straight line, a column the table does not have is an error, never a silent index.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def load_flag_table(npz_path: str | Path, rows: int, columns: int):
    """The npz `flags` array as float32 (rows, columns, K, 2), or None when the mesh carries no flag table."""
    import numpy as np

    data = np.load(Path(npz_path), allow_pickle=False)
    if "flags" not in data.files:
        return None
    flags = np.asarray(data["flags"], dtype=np.float32)
    if flags.ndim != 4 or flags.shape[0] != rows or flags.shape[1] != columns or flags.shape[2] < 4 or flags.shape[3] != 2:
        raise ValueError(f"EX-42 flag table must be ({rows}, {columns}, >=4, 2), got {tuple(flags.shape)}")
    if np.isinf(flags).any():
        raise ValueError("EX-42 flag table holds an infinite value (NaN means no flags for a cell)")
    return flags


class MeshFlagProvider:
    """`flag_provider(terrain, env_ids, count)` for the mixed command term, indexed by (level, column) of the mesh."""

    def __init__(self, flags):
        import torch

        self.flags = torch.as_tensor(flags, dtype=torch.float32)
        self.columns = int(self.flags.shape[1])

    def __call__(self, terrain, env_ids, count):
        import torch
        from foothold_s2.commands import mixed_core as mc

        levels = terrain.terrain_levels[env_ids].long()
        types = terrain.terrain_types[env_ids].long()
        if int(types.max()) >= self.columns:
            raise ValueError(f"EX-42 an env sits on column {int(types.max())} but the flag table has {self.columns}")
        table = self.flags.to(levels.device)
        out = table[levels, types][:, :count]
        straight = torch.stack([mc.straight_flag_line(o, count) for o in terrain.env_origins[env_ids, :2].cpu()]).to(out.device)
        missing = torch.isnan(out).any(dim=(1, 2))
        return torch.where(missing[:, None, None], straight, out)


def attach_mesh_flags(env_cfg: Any, npz_path: str | Path, rows: int, columns: int) -> dict[str, Any] | None:
    """Give the command term the mesh flag table when the mesh has one (None: nothing changes, straight flags)."""
    flags = load_flag_table(npz_path, rows, columns)
    if flags is None:
        return None
    term = getattr(env_cfg.commands, "base_velocity", None)
    if term is None or not hasattr(term, "flag_provider"):
        raise ValueError("EX-42 the command term cannot take a flag provider")
    term.flag_provider = MeshFlagProvider(flags)
    return {"rows": rows, "columns": columns, "k": int(flags.shape[2]), "cells_with_flags": int((~__import__("numpy").isnan(flags).any(axis=(2, 3))).sum())}
