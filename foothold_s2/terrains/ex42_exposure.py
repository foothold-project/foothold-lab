"""E0 column exposure: which mesh columns get envs at all, and how high their levels may go.

Lead-lx decision 04:58: columns whose exposure is 0 receive no env, at the first assignment and at every
curriculum re-assignment (including the random redraw when an env passes the top level); levels are cut
at the column's own cap. The numbers come from the plan (stages E0 terrain.exposure_at_E0), never typed here:

    exposure_at_E0:
      default: {exposure: 0.0, level_cap: 0}
      positive: [{family: A, kinds_of: continuous, exposure: 1.0, level_cap: 5}]   # kinds_of -> kind_task[<name>]

Isaac's TerrainImporter keeps terrain_types fixed after the start and only moves terrain_levels, so
"never reassigned into an exposure-0 column" holds once the start assignment is inside the eligible set.
Pure python + torch; Kit only supplies the terrain object.
"""
from __future__ import annotations

from typing import Any


def exposure_by_column(plan_terrain: dict[str, Any], table: list[dict[str, Any]]) -> tuple[list[float], list[int]]:
    """(exposure, level_cap) per mesh column from the plan's E0 terrain section and the column table."""
    spec = plan_terrain.get("exposure_at_E0")
    if not isinstance(spec, dict) or not isinstance(spec.get("default"), dict):
        raise ValueError("EX-42 E0 stage lacks terrain.exposure_at_E0.default")
    base = spec["default"]
    default = (_number(base.get("exposure"), "default.exposure"), _cap(base.get("level_cap"), "default.level_cap"))
    kind_task = plan_terrain.get("kind_task") or {}
    rules = []
    for rule in spec.get("positive") or []:
        kinds_of = rule.get("kinds_of")
        if kinds_of not in kind_task:
            raise ValueError(f"EX-42 exposure rule names kind list {kinds_of!r} that kind_task lacks")
        rules.append((rule.get("family"), set(kind_task[kinds_of]),
                      _number(rule.get("exposure"), "positive.exposure"), _cap(rule.get("level_cap"), "positive.level_cap")))
    exposure, caps = [], []
    for row in table:
        hit = [(w, c) for fam, kinds, w, c in rules if row["family"] == fam and row["kind"] in kinds]
        if len(hit) > 1:
            raise ValueError(f"EX-42 exposure rules overlap on column {row['family']}/{row['kind']}")
        w, c = hit[0] if hit else default
        exposure.append(w)
        caps.append(c)
    if not any(w > 0 for w in exposure):
        raise ValueError("EX-42 E0 exposure leaves no column with positive exposure")
    return exposure, caps


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value != value:
        raise ValueError(f"EX-42 exposure {name} must be a number >= 0")
    return float(value)


def _cap(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"EX-42 exposure {name} must be an integer >= 0")
    return value


def assign_exposed_columns(num_envs: int, exposure, generator=None, device="cpu"):
    """Column per env: only exposure > 0 columns, counts proportional to exposure (largest remainder)."""
    import torch

    w = torch.as_tensor(exposure, dtype=torch.float64)
    eligible = torch.nonzero(w > 0).flatten()
    share = w[eligible] / w[eligible].sum() * num_envs
    counts = share.floor().to(torch.long)
    left = num_envs - int(counts.sum())
    if left > 0:
        counts[torch.argsort(share - counts, descending=True)[:left]] += 1
    types = torch.repeat_interleave(eligible, counts)
    perm = torch.randperm(num_envs, generator=generator)
    return types[perm].to(device)


def apply_exposure(terrain, exposure, caps, generator=None) -> dict[str, Any]:
    """Runtime step on the TerrainImporter (call once after the env exists, before the first reset):
    assign envs only to exposed columns, cut levels at the caps, and wrap update_env_origins so every
    later level change is cut the same way. Returns a receipt."""
    import torch

    if getattr(terrain, "exposure_wrapped", False):
        raise ValueError("EX-42 exposure is already applied to this terrain")
    if terrain.terrain_origins is None:
        raise ValueError("EX-42 exposure needs a curriculum terrain (terrain_origins missing)")
    if len(exposure) != terrain.terrain_origins.shape[1] or len(caps) != len(exposure):
        raise ValueError("EX-42 exposure table does not match the mesh column count")
    device = terrain.terrain_levels.device
    cap = torch.as_tensor(caps, dtype=torch.long, device=device)
    num_envs = terrain.terrain_levels.shape[0]
    terrain.terrain_types = assign_exposed_columns(num_envs, exposure, generator, device)
    cap = cap.clamp(max=terrain.terrain_origins.shape[0] - 1)

    def refresh(ids):
        terrain.terrain_levels[ids] = torch.minimum(terrain.terrain_levels[ids], cap[terrain.terrain_types[ids]])
        terrain.env_origins[ids] = terrain.terrain_origins[terrain.terrain_levels[ids], terrain.terrain_types[ids]]

    everyone = torch.arange(num_envs, device=device)
    refresh(everyone)
    original = terrain.update_env_origins

    def capped_update(env_ids, move_up, move_down):
        original(env_ids, move_up, move_down)
        refresh(env_ids)

    terrain.update_env_origins = capped_update
    terrain.exposure_wrapped = True
    return {"exposed_columns": [c for c, w in enumerate(exposure) if w > 0],
            "level_caps": [int(c) for c in cap.tolist()], "envs": num_envs}
