"""Place basic-gait envs on L0..2 while retaining the generated ten-row geometry."""

from __future__ import annotations

import hashlib

import torch


def place_l02(raw_env) -> dict:
    """Rebase active labels and both origin tables without touching terrain types."""
    terrain = raw_env.scene.terrain
    old = terrain.terrain_levels.clone()
    types = terrain.terrain_types
    if old.ndim != 1 or old.shape != types.shape or len(old) == 0:
        raise ValueError("terrain level/type labels must be matching nonempty vectors")
    if (old < 0).any() or (old >= terrain.terrain_origins.shape[0]).any():
        raise ValueError("old terrain level is outside generated rows")
    if (types < 0).any() or (types >= terrain.terrain_origins.shape[1]).any():
        raise ValueError("terrain type is outside generated columns")
    if terrain.terrain_origins.shape[0] < 3:
        raise ValueError("basic gait needs generated rows L0..2")
    new = old.remainder(3)
    terrain.terrain_levels.copy_(new)
    origins = terrain.terrain_origins[new, types]
    terrain.env_origins.copy_(origins)
    raw_env.scene.env_origins.copy_(origins)
    if not torch.equal(terrain.env_origins, raw_env.scene.env_origins):
        raise RuntimeError("terrain and scene origins differ after L0..2 placement")
    return {
        "policy": "fixed_l02",
        "generated_rows_unchanged": True,
        "placement": "old_level modulo 3, terrain type unchanged",
        "old_above_l2": int((old > 2).sum().item()),
        "new_counts": [int((new == level).sum().item()) for level in range(3)],
        "labels_sha256": hashlib.sha256(new.detach().cpu().contiguous().numpy().tobytes() +
                                        types.detach().cpu().contiguous().numpy().tobytes()).hexdigest(),
    }
