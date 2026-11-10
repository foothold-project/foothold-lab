"""Per-column reset ranges for the EX-42 combined mesh (column -> start offset / yaw range).

Lead decision 01:44: C gap / box / discrete_obstacles start exactly on the safe support patch
(xy and yaw jitter 0, as in the JEPLO original); every other kind keeps the EX-41 default
(x, y in +-0.5 m, yaw +-3.14). The kind-level ranges come from the family generator module as

    RESET_RANGES = {kind: {"x": (lo, hi), "y": (lo, hi), "yaw": (lo, hi)}}     # partial keys allowed

(planner / analyst contract; a module without RESET_RANGES, or a kind not listed, uses the default).
This file only turns that into a per-column table and applies it at reset. Nothing here invents a
range: the numbers are the default below or the generator's own declaration.

Pure python + torch (no Isaac import) so it is CPU-testable; Kit is only needed for the EventTerm.
"""
from __future__ import annotations

import importlib
from typing import Any

import numpy as np

AXES = ("x", "y", "z", "roll", "pitch", "yaw")
DEFAULT_RANGES: dict[str, tuple[float, float]] = {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)}
# family -> (module, kind-order attribute). One mesh column per kind for B C D E; A uses columns.py.
FAMILY_KIND_SOURCES = {"B": ("foothold_s2.terrains.ame2_preset", "KINDS"),
                       "C": ("foothold_s2.terrains.jeplo_preset", "KINDS"),
                       "D": ("foothold_s2.terrains.hipan_posture", "KINDS")}


def _clean(ranges: dict[str, Any]) -> dict[str, tuple[float, float]]:
    out = {}
    for axis, pair in ranges.items():
        if axis not in AXES:
            raise ValueError(f"unknown reset axis {axis!r}")
        lo, hi = (float(pair[0]), float(pair[1]))
        if not (np.isfinite(lo) and np.isfinite(hi)) or lo > hi:
            raise ValueError(f"bad reset range for {axis}: {pair}")
        out[axis] = (lo, hi)
    return out


def family_column_kinds(family: str, count: int) -> list[str | None]:
    """Kind name per column inside one family where the code knows it (else None)."""
    try:
        if family == "A":
            from foothold_s2.terrains import columns
            return list(columns.column_types(columns.FULL, columns.FULL_COLS))
        if family in FAMILY_KIND_SOURCES:
            module, attr = FAMILY_KIND_SOURCES[family]
            kinds = list(getattr(importlib.import_module(module), attr))
            if len(kinds) == count:
                return kinds
        if family == "E":
            from foothold_s2.terrains.ex42 import PAPER_EXT_SPECS
            kinds = [spec.kind for spec in PAPER_EXT_SPECS]
            if len(kinds) == count:
                return kinds
    except ImportError:
        pass
    return [None] * count


def kind_ranges_of(family: str) -> dict[str, dict[str, tuple[float, float]]]:
    """The generator module's own RESET_RANGES declaration ({} if it has none)."""
    module = {"A": "foothold_s2.terrains.start_go2_v2", "B": "foothold_s2.terrains.ame2_preset", "C": "foothold_s2.terrains.jeplo_preset",
              "D": "foothold_s2.terrains.hipan_posture", "E": "foothold_s2.terrains.ex42"}.get(family)
    if module is None:
        return {}
    try:
        declared = getattr(importlib.import_module(module), "RESET_RANGES", None)
    except ImportError:
        return {}
    return {} if declared is None else {kind: _clean(r) for kind, r in declared.items()}


def build_column_table(column_family: list[str],
                       kind_ranges: dict[str, dict[str, dict[str, Any]]] | None = None,
                       ) -> list[dict[str, Any]]:
    """One row per mesh column: {family, kind, ranges}. `kind_ranges` = {family: {kind: ranges}};
    default None reads each family module's RESET_RANGES."""
    if not column_family:
        raise ValueError("EX-42 reset table needs the mesh column_family list (no columns given)")
    rows: list[dict[str, Any]] = []
    for family in dict.fromkeys(column_family):
        count = column_family.count(family)
        kinds = family_column_kinds(family, count)
        declared = kind_ranges_of(family) if kind_ranges is None else {
            k: _clean(r) for k, r in (kind_ranges.get(family) or {}).items()}
        for kind in kinds:
            ranges = {**DEFAULT_RANGES, **declared.get(kind, {})} if kind else dict(DEFAULT_RANGES)
            rows.append({"family": family, "kind": kind, "ranges": ranges,
                         "from_declaration": bool(kind and kind in declared)})
    if [r["family"] for r in rows] != list(column_family):
        raise ValueError("columns of one family must be contiguous in the mesh")
    return rows


def table_tensors(table: list[dict[str, Any]], device: Any = "cpu"):
    """(lo, hi) tensors of shape (columns, 6) in AXES order; undeclared axes are 0 (as Isaac does)."""
    import torch

    if not table:
        raise ValueError("EX-42 reset table is empty")
    lo = torch.zeros(len(table), 6, device=device)
    hi = torch.zeros(len(table), 6, device=device)
    for c, row in enumerate(table):
        for a, axis in enumerate(AXES):
            lo[c, a], hi[c, a] = row["ranges"].get(axis, (0.0, 0.0))
    return lo, hi


def sample_pose_offsets(column_index, lo, hi, generator=None):
    """Uniform sample per env from its own column row. column_index: (envs,) long tensor."""
    import torch

    low, high = lo[column_index], hi[column_index]
    u = torch.rand(low.shape, device=low.device, generator=generator)
    return low + (high - low) * u


def _quat_from_euler_wxyz(roll, pitch, yaw):
    import torch

    cr, sr, cp, sp, cy, sy = (torch.cos(roll / 2), torch.sin(roll / 2), torch.cos(pitch / 2),
                              torch.sin(pitch / 2), torch.cos(yaw / 2), torch.sin(yaw / 2))
    return torch.stack([cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy,
                        cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy], dim=-1)   # w x y z


def _quat_mul(a, b):
    import torch

    aw, ax, ay, az = a.unbind(-1)
    bw, bx, by, bz = b.unbind(-1)
    return torch.stack([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                        aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], dim=-1)


def reset_root_state_by_column(env, env_ids, lo, hi, velocity_range, asset_cfg=None):
    """Drop-in for isaaclab mdp.reset_root_state_uniform whose pose range depends on the env's
    terrain column (terrain.terrain_types). Same maths: default root + env origin + sample."""
    import torch

    asset = env.scene[asset_cfg.name if asset_cfg is not None else "robot"]
    root_states = asset.data.default_root_state[env_ids].clone()
    columns = env.scene.terrain.terrain_types[env_ids].long()
    lo_d, hi_d = lo.to(asset.device), hi.to(asset.device)
    samples = sample_pose_offsets(columns, lo_d, hi_d)
    positions = root_states[:, 0:3] + env.scene.env_origins[env_ids] + samples[:, 0:3]
    orientations = _quat_mul(root_states[:, 3:7],
                             _quat_from_euler_wxyz(samples[:, 3], samples[:, 4], samples[:, 5]))
    rng = torch.tensor([velocity_range.get(k, (0.0, 0.0)) for k in AXES], device=asset.device)
    velocities = root_states[:, 7:13] + rng[:, 0] + (rng[:, 1] - rng[:, 0]) * torch.rand(
        len(env_ids), 6, device=asset.device)
    asset.write_root_pose_to_sim(torch.cat([positions, orientations], dim=-1), env_ids=env_ids)
    asset.write_root_velocity_to_sim(velocities, env_ids=env_ids)


def apply_column_reset(env_cfg, table: list[dict[str, Any]]) -> None:
    """Swap env_cfg.events.reset_base for the per-column version (Kit python)."""
    if not table:
        raise ValueError("EX-42 reset table missing: refusing to fall back to the default range silently")
    from isaaclab.managers import EventTermCfg

    lo, hi = table_tensors(table)
    old = env_cfg.events.reset_base.params
    env_cfg.events.reset_base = EventTermCfg(
        func=reset_root_state_by_column, mode="reset",
        params={"lo": lo, "hi": hi, "velocity_range": old["velocity_range"]})


# ---- push gate: no interval push on narrow-support (sparse) columns -----------------------------
# Team-lead decision 01:54: pushes stay on for continuous / flat columns, off on narrow-support
# terrain. The kind list is planner's; until it lands the caller passes the table:
#     narrow_support = {"A": {"stones", ...}, "C": {"gap", ...}, ...}      # family -> kind names
# A column whose kind name is unknown to the code (None) keeps the push and is listed in the report.

def push_gate_mask(table: list[dict[str, Any]], narrow_support: dict[str, Any]) -> list[bool]:
    """Per mesh column: True = push disabled. `narrow_support` = {family: iterable of kind names}."""
    sets = {family: set(kinds) for family, kinds in narrow_support.items()}
    known = {(row["family"], row["kind"]) for row in table if row["kind"]}
    unknown_names = [(f, k) for f, ks in sets.items() for k in ks if (f, k) not in known]
    if unknown_names:
        raise ValueError(f"narrow-support kinds not present in the mesh columns: {sorted(unknown_names)}")
    return [bool(row["kind"] and row["kind"] in sets.get(row["family"], ())) for row in table]


def push_gate_report(table: list[dict[str, Any]], mask: list[bool]) -> dict[str, Any]:
    return {"push_off_columns": [c for c, off in enumerate(mask) if off],
            "push_off_kinds": [f"{table[c]['family']}/{table[c]['kind']}" for c, off in enumerate(mask) if off],
            "columns_with_unknown_kind_push_kept": [c for c, r in enumerate(table) if r["kind"] is None],
            "columns": len(mask)}


def push_gated_by_column(env, env_ids, inner, push_off, **params):
    """EventTerm func: run the wrapped interval push only for envs whose column is not push-off.
    `push_off` is a bool tensor of shape (columns,)."""
    import torch

    device = env.scene.terrain.terrain_types.device
    rows = torch.arange(env.scene.num_envs, device=device) if env_ids is None else torch.as_tensor(
        env_ids, dtype=torch.long, device=device).flatten()
    keep = ~push_off.to(device)[env.scene.terrain.terrain_types[rows].long()]
    rows = rows[keep]
    if len(rows) == 0:
        return
    inner(env, rows, **params)


def apply_column_push_gate(env_cfg, mask: list[bool], term_names=("ex40_push", "push_robot")) -> list[str]:
    """Wrap the existing interval push term(s) of env_cfg.events (Kit python). Returns wrapped names.
    Raises if no push term is installed, so a missing gate cannot pass silently."""
    import torch

    wrapped = []
    for name in term_names:
        term = getattr(env_cfg.events, name, None)
        if term is None:
            continue
        term.params = {"inner": term.func, "push_off": torch.tensor(mask, dtype=torch.bool), **term.params}
        term.func = push_gated_by_column
        wrapped.append(name)
    if not wrapped:
        raise ValueError(f"no push event term found among {term_names}")
    return wrapped
