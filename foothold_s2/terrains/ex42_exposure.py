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


def exposure_by_column(plan_terrain: dict[str, Any], table: list[dict[str, Any]],
                       stage_id: str = "E0") -> tuple[list[float], list[int]]:
    """(exposure, level_cap) per mesh column from the plan's terrain section of `stage_id` and the column table."""
    spec = plan_terrain.get(f"exposure_at_{stage_id}")
    if not isinstance(spec, dict) or not isinstance(spec.get("default"), dict):
        raise ValueError(f"EX-42 {stage_id} stage lacks terrain.exposure_at_{stage_id}.default")
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
        raise ValueError(f"EX-42 {stage_id} exposure leaves no column with positive exposure")
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


def parent_column_kinds() -> list[str]:
    """Kind of each column of the parent's mesh (EX-41 / stage zero: the 23 continuous columns)."""
    from foothold_s2.terrains import columns

    return list(columns.column_types(columns.CONTINUOUS, columns.CONTINUOUS_COLS))


def restore_parent_placement(parent_env_state: dict[str, Any], table: list[dict[str, Any]], num_envs: int,
                             same_mesh: bool = False):
    """(terrain_types, terrain_levels) of the parent's envs, checked against the new mesh by kind name.

    Parent column c must be the same kind as new-mesh column c (family A); a mismatch raises. Every rank
    gets the same parent distribution (3072 envs each), so two ranks hold 6144 envs of that distribution.
    `same_mesh` (E1: the parent is an E0 run on this very mesh): columns are the table's own columns,
    so the only check is that every parent column exists in the table.
    """
    import torch

    types = torch.as_tensor(parent_env_state["terrain_types"]).to(torch.long).clone()
    levels = torch.as_tensor(parent_env_state["terrain_levels"]).to(torch.long).clone()
    if types.shape != levels.shape or types.ndim != 1 or len(types) != num_envs:
        raise ValueError(f"EX-42 parent env_state has {tuple(types.shape)} envs, this process has {num_envs}")
    kinds = [r["kind"] for r in table] if same_mesh else parent_column_kinds()
    if int(types.min()) < 0 or int(types.max()) >= len(kinds):
        raise ValueError("EX-42 parent env_state names a column outside the parent mesh")
    for c, kind in enumerate(kinds if not same_mesh else []):
        row = table[c] if c < len(table) else None
        if row is None or row["family"] != "A" or row["kind"] != kind:
            raise ValueError(f"EX-42 parent column {c} is {kind!r} but the new mesh column is "
                             f"{None if row is None else (row['family'], row['kind'])}")
    return types, levels


def apply_exposure(terrain, exposure, caps, generator=None, parent_env_state=None, table=None,
                   parent_same_mesh: bool = False) -> dict[str, Any]:
    """Runtime step on the TerrainImporter (call once after the env exists, before the first reset):
    start from the parent's (column, level) per env when given (else assign only to exposed columns),
    cut levels at the caps, and wrap update_env_origins so every later level change is cut the same
    way. A parent column with exposure 0 raises. Returns a receipt."""
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
    cap = cap.clamp(max=terrain.terrain_origins.shape[0] - 1)
    inherited = parent_env_state is not None
    if inherited:
        if table is None:
            raise ValueError("EX-42 parent placement needs the column table")
        types, levels = restore_parent_placement(parent_env_state, table, num_envs, same_mesh=parent_same_mesh)
        if int(levels.min()) < 0 or int(levels.max()) >= terrain.terrain_origins.shape[0]:
            raise ValueError("EX-42 parent env_state level is outside the mesh rows")
        if not torch.as_tensor([w > 0 for w in exposure])[types].all():
            raise ValueError("EX-42 parent env sits on a column with exposure 0")
        terrain.terrain_types = types.to(device)
        terrain.terrain_levels = levels.to(device)
    else:
        terrain.terrain_types = assign_exposed_columns(num_envs, exposure, generator, device)

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
            "level_caps": [int(c) for c in cap.tolist()], "envs": num_envs,
            "start": "parent_env_state" if inherited else "assigned"}


def level_counts(terrain) -> dict[str, Any]:
    """Receipt of the live placement: envs per level, and the (column, level) cells that hold envs."""
    import torch

    levels = terrain.terrain_levels.detach().cpu().to(torch.long)
    types = terrain.terrain_types.detach().cpu().to(torch.long)
    rows = int(terrain.terrain_origins.shape[0])
    cells: dict[str, int] = {}
    for c, l in zip(types.tolist(), levels.tolist()):
        cells[f"{c}:{l}"] = cells.get(f"{c}:{l}", 0) + 1
    return {"envs": int(levels.numel()),
            "per_level": torch.bincount(levels, minlength=rows).tolist(),
            "columns_used": sorted(set(types.tolist())),
            "per_column_level": dict(sorted(cells.items(), key=lambda kv: tuple(map(int, kv[0].split(":"))))),
            "levels_max": int(levels.max()) if levels.numel() else None}
