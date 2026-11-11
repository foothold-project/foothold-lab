"""E0 column exposure: which mesh columns get envs at all, and how high their levels may go.

Lead-lx decision 04:58: columns whose exposure is 0 receive no env, at the first assignment and at every
curriculum re-assignment (including the random redraw when an env passes the top level); levels are cut
at the column's own cap. The numbers come from the plan (stages E0 terrain.exposure_at_E0), never typed here:

    exposure_at_E0:
      default: {exposure: 0.0, level_cap: 0}
      positive: [{family: A, kinds_of: continuous, exposure: 1.0, level_cap: 5}]   # kinds_of -> kind_task[<name>]

A rule carries either `exposure` (a relative weight) or `share` (the fraction of ALL envs its columns hold together,
0 < share < 1, split evenly over its columns; K boundary: CG "terrain.exposure.<family>.<kind>.share"). The weight
rules take the rest, 1 - sum(share), in proportion to their weights (the derived continuous share). `kinds_of` names a
kind_task list, `kind` names one kind. Shares and weights are turned into one weight per column, so the env counts
(`env_counts`, largest remainder) hit the shares exactly up to one env.

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
    rules = []                                    # (family, kinds, weight, share, level cap)
    for rule in spec.get("positive") or []:
        if ("kinds_of" in rule) == ("kind" in rule):
            raise ValueError("EX-42 exposure rule names exactly one of kinds_of or kind")
        if "kinds_of" in rule:
            if rule["kinds_of"] not in kind_task:
                raise ValueError(f"EX-42 exposure rule names kind list {rule['kinds_of']!r} that kind_task lacks")
            kinds = set(kind_task[rule["kinds_of"]])
        else:
            kinds = {rule["kind"]}
        if ("exposure" in rule) == ("share" in rule):
            raise ValueError("EX-42 exposure rule carries exactly one of exposure or share")
        weight = _number(rule["exposure"], "positive.exposure") if "exposure" in rule else None
        share = _share(rule["share"]) if "share" in rule else None
        rules.append((rule.get("family"), kinds, weight, share, _cap(rule.get("level_cap"), "positive.level_cap")))
    exposure, caps, share_of = [], [], []
    for row in table:
        hit = [(w, sh, c) for fam, kinds, w, sh, c in rules if row["family"] == fam and row["kind"] in kinds]
        if len(hit) > 1:
            raise ValueError(f"EX-42 exposure rules overlap on column {row['family']}/{row['kind']}")
        w, sh, c = hit[0] if hit else (default[0], None, default[1])
        exposure.append(w)
        share_of.append(sh)
        caps.append(c)
    shares = [(fam, kinds, sh) for fam, kinds, w, sh, c in rules if sh is not None]
    if shares:
        total_share = sum(sh for _, _, sh in shares)
        weight_total = sum(w for w, sh in zip(exposure, share_of) if sh is None)
        if total_share >= 1.0 or weight_total <= 0:
            raise ValueError("EX-42 exposure shares must leave a positive remainder for the weight rules")
        for fam, kinds, sh in shares:
            ids = [i for i, row in enumerate(table) if row["family"] == fam and row["kind"] in kinds]
            if not ids:
                raise ValueError(f"EX-42 exposure share rule {fam}/{sorted(kinds)} matches no mesh column")
            for i in ids:               # normalized weight of these columns = sh / len(ids) of all envs
                exposure[i] = sh / len(ids) * weight_total / (1.0 - total_share)
    if not any(w > 0 for w in exposure):
        raise ValueError(f"EX-42 {stage_id} exposure leaves no column with positive exposure")
    return exposure, caps


def column_shares(plan_terrain: dict[str, Any], table: list[dict[str, Any]], stage_id: str) -> list[float | None]:
    """Per mesh column: its fraction of ALL envs when a `share` rule names it, else None (a weight column)."""
    spec = plan_terrain.get(f"exposure_at_{stage_id}") or {}
    kind_task = plan_terrain.get("kind_task") or {}
    out: list[float | None] = [None] * len(table)
    for rule in spec.get("positive") or []:
        if "share" not in rule:
            continue
        kinds = set(kind_task[rule["kinds_of"]]) if "kinds_of" in rule else {rule["kind"]}
        ids = [i for i, row in enumerate(table) if row["family"] == rule.get("family") and row["kind"] in kinds]
        for i in ids:
            out[i] = float(rule["share"]) / len(ids)
    return out


def low_level_floor(plan_terrain: dict[str, Any], table: list[dict[str, Any]], stage_id: str):
    """The stage's CG:380 floor (continuous envs kept at levels lo..hi: at least `fraction` of the continuous envs),
    or None when the stage row has none (E0 / E1 run without it). Continuous = the family A columns."""
    spec = (plan_terrain.get("floors") or {}).get("continuous_low_level_floor")
    if spec is None:
        return None
    levels, fraction = spec.get("levels"), spec.get("fraction_of_continuous")
    if (not isinstance(levels, list) or len(levels) != 2 or any(type(v) is not int for v in levels)
            or not 0 <= levels[0] <= levels[1] or not isinstance(fraction, (int, float)) or isinstance(fraction, bool)
            or not 0.0 < float(fraction) < 1.0):
        raise ValueError(f"EX-42 {stage_id} continuous low-level floor is malformed")
    continuous = [row["family"] == "A" for row in table]
    if not any(continuous):
        raise ValueError(f"EX-42 {stage_id} continuous low-level floor needs continuous (family A) columns")
    return {"levels": [int(levels[0]), int(levels[1])], "fraction": float(fraction), "continuous": continuous}


def rebalance_to_shares(types, levels, exposure, shares, generator=None):
    """Inherited placement at a K boundary: make the share columns hold their share of the envs.

    The parent's (column, level) per env is kept wherever it is still right. Envs on exposure-0 columns and the
    surplus on over-full share columns go to weight columns; the deficit of the share columns is taken, at random,
    from envs on weight columns and restarts at level 0. Returns (types, levels, receipt)."""
    import torch

    types, levels = types.clone(), levels.clone()
    n, ncol = len(types), len(exposure)
    w = torch.as_tensor(exposure, dtype=torch.float64)
    share_cols = [c for c, s in enumerate(shares) if s]
    weight_cols = [c for c in range(ncol) if w[c] > 0 and not shares[c]]
    if not weight_cols:
        raise ValueError("EX-42 rebalance needs at least one weight column")
    eligible, counts = env_counts(n, exposure)
    target = {int(c): int(k) for c, k in zip(eligible.tolist(), counts.tolist())}
    on = lambda c: torch.nonzero(types == c).flatten()  # noqa: E731
    homeless = [on(c) for c in range(ncol) if w[c] <= 0]
    for c in share_cols:
        ids = on(c)
        extra = len(ids) - target.get(c, 0)
        if extra > 0:
            homeless.append(ids[torch.randperm(len(ids), generator=generator)[:extra]])
    pool = torch.cat(homeless) if homeless else torch.zeros(0, dtype=torch.long)
    moved_out = int(len(pool))
    if moved_out:
        pick = torch.multinomial(w[weight_cols], moved_out, replacement=True, generator=generator)
        types[pool] = torch.as_tensor(weight_cols)[pick]
    taken = 0
    for c in share_cols:
        deficit = target.get(c, 0) - len(on(c))
        if deficit <= 0:
            continue
        donors = torch.nonzero(torch.isin(types, torch.as_tensor(weight_cols))).flatten()
        chosen = donors[torch.randperm(len(donors), generator=generator)[:deficit]]
        types[chosen], levels[chosen] = c, 0
        taken += len(chosen)
    return types, levels, {"moved_to_weight_columns": moved_out, "moved_to_share_columns": taken}


def _share(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1:
        raise ValueError("EX-42 exposure share must be a number with 0 < share < 1")
    return float(value)


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value != value:
        raise ValueError(f"EX-42 exposure {name} must be a number >= 0")
    return float(value)


def _cap(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"EX-42 exposure {name} must be an integer >= 0")
    return value


def env_counts(num_envs: int, exposure):
    """(eligible column ids, envs per eligible column): proportional to exposure, largest remainder."""
    import torch

    w = torch.as_tensor(exposure, dtype=torch.float64)
    eligible = torch.nonzero(w > 0).flatten()
    share = w[eligible] / w[eligible].sum() * num_envs
    counts = share.floor().to(torch.long)
    left = num_envs - int(counts.sum())
    if left > 0:
        counts[torch.argsort(share - counts, descending=True)[:left]] += 1
    return eligible, counts


def assign_exposed_columns(num_envs: int, exposure, generator=None, device="cpu"):
    """Column per env: only exposure > 0 columns, counts proportional to exposure (largest remainder)."""
    import torch

    eligible, counts = env_counts(num_envs, exposure)
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


class LowLevelFloor:
    """CG:380: at least `fraction` of the continuous envs stand on levels lo..hi (forgetting guard).

    Level promotion alone pushes every env to the cap (E1 window 451~700: 33 of 18,608 episodes on L0~2). After each
    level update the envs that are being reset right now (their new origin is applied at this reset, so nothing is
    moved mid-episode) are sent back to a random level in lo..hi until the count reaches ceil(fraction x continuous)
    or there are no more such envs; the shortfall stays visible in the receipt and closes at the next resets."""

    def __init__(self, terrain, spec, refresh, generator=None):
        import torch

        self.terrain, self.refresh, self.generator = terrain, refresh, generator
        self.lo, self.hi, self.fraction = spec["levels"][0], spec["levels"][1], spec["fraction"]
        device = terrain.terrain_levels.device
        self.continuous = torch.as_tensor(spec["continuous"], dtype=torch.bool, device=device)
        self.reassigned = 0
        self.checks = 0
        self.last_deficit = 0

    def counts(self) -> dict[str, int]:
        import math

        cont = self.continuous[self.terrain.terrain_types]
        total = int(cont.sum())
        low = int((cont & (self.terrain.terrain_levels <= self.hi)).sum())
        return {"continuous_envs": total, "low_level_envs": low, "required": math.ceil(self.fraction * total)}

    def enforce(self, env_ids) -> int:
        import torch

        have = self.counts()
        deficit = have["required"] - have["low_level_envs"]
        self.checks += 1
        self.last_deficit = max(deficit, 0)
        if deficit <= 0:
            return 0
        levels, types = self.terrain.terrain_levels, self.terrain.terrain_types
        ids = env_ids[self.continuous[types[env_ids]] & (levels[env_ids] > self.hi)]
        if not ids.numel():
            return 0
        order = torch.randperm(int(ids.numel()), generator=self.generator)[:deficit].to(ids.device)
        picked = ids[order]
        span = self.hi - self.lo + 1
        draw = torch.randint(0, span, (int(picked.numel()),), generator=self.generator).to(picked.device)
        levels[picked] = self.lo + draw
        self.refresh(picked)
        self.reassigned += int(picked.numel())
        self.last_deficit = max(deficit - int(picked.numel()), 0)
        return int(picked.numel())

    def receipt(self) -> dict[str, Any]:
        return {"format": "foothold-ex42-low-level-floor/1", "source": "CG:380", "levels": [self.lo, self.hi],
                "fraction_of_continuous": self.fraction, **self.counts(), "reassigned_total": self.reassigned,
                "checks": self.checks, "last_deficit": self.last_deficit}


def apply_exposure(terrain, exposure, caps, generator=None, parent_env_state=None, table=None,
                   parent_same_mesh: bool = False, shares=None, low_floor=None) -> dict[str, Any]:
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
        rebalance = None
        if shares is not None and any(shares):
            types, levels, rebalance = rebalance_to_shares(types, levels, exposure, shares, generator)
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
    floor = None
    if low_floor is not None:
        floor = LowLevelFloor(terrain, low_floor, refresh, generator)
        floor.enforce(everyone)             # before the first reset every env may be placed
    terrain.low_level_floor = floor

    def capped_update(env_ids, move_up, move_down):
        original(env_ids, move_up, move_down)
        refresh(env_ids)
        if floor is not None:
            floor.enforce(torch.as_tensor(env_ids, device=device, dtype=torch.long))

    terrain.update_env_origins = capped_update
    terrain.exposure_wrapped = True
    return {"exposed_columns": [c for c, w in enumerate(exposure) if w > 0],
            "level_caps": [int(c) for c in cap.tolist()], "envs": num_envs,
            "start": "parent_env_state" if inherited else "assigned",
            **({"low_level_floor": floor.receipt()} if floor is not None else {}),
            **({"rebalance": rebalance} if inherited and rebalance else {})}


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
