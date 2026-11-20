"""CPU preflight and Kit attachment for EX-42 calibration on one fixed mesh."""
from __future__ import annotations

import json
from pathlib import Path

from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh
from foothold_s2.terrains.ex42_column_reset import build_column_table


# The parent's default map64 uses the 23 continuous A columns. The physical
# combined mesh has 76 columns; its B-E columns are not part of this cell.
EVAL_COLS = 23


def validate_eval_cell(result, mesh, *, fixed_level=None):
    """Reject a 76-column reference run when scoring the A-only calibration cell."""
    from foothold_s2.eval.fixed_terrain import assignment_sha256, fixed_assignment

    record = result.get("fixed_terrain") or {}
    n = result.get("envs")
    if (n != 64 or record.get("rows") != 10 or record.get("cols") != EVAL_COLS
            or record.get("num_envs") != n or record.get("fixed_level") != fixed_level
            or mesh.get("eval_cols") != EVAL_COLS):
        raise ValueError("EX-42 calibration fixed evaluation cell is not A continuous 23 x 64 env")
    levels, types = fixed_assignment(n, record["rows"], EVAL_COLS, fixed_level)
    if record.get("assignment_sha256") != assignment_sha256(levels, types):
        raise ValueError("EX-42 calibration fixed evaluation assignment SHA differs")
    tiles = result.get("terrain_tiles") or []
    names = mesh.get("eval_columns") or []
    if len(tiles) != n or len(names) != EVAL_COLS or any(
            tile.get("env") != i or tile.get("column") != int(types[i])
            or tile.get("level") != int(levels[i])
            or tile.get("kind") != names[int(types[i])]
            for i, tile in enumerate(tiles)):
        raise ValueError("EX-42 calibration terrain tiles differ from A continuous fixed cell")


def validate_kind_cell(result, mesh, *, family: str, kind: str, level: int, envs: int = 64, start_yaw_zero: bool = False):
    """Verify every env stayed on the selected named kind after the Kit run."""
    from foothold_s2.eval.fixed_terrain import assignment_sha256, kind_assignment

    record = result.get("fixed_terrain") or {}
    n = result.get("envs")
    table = [{"family": f, "kind": k} for f, k in zip(
        mesh.get("column_family", ()), mesh.get("columns", ()))]
    if (n != envs or record.get("rows") != 10 or record.get("cols") != len(table)
            or record.get("num_envs") != n or record.get("fixed_level") != level
            or record.get("family") != family or record.get("kind") != kind):
        raise ValueError("EX-42 named kind evaluation identity differs")
    if result.get("start_yaw_override") != (0.0 if start_yaw_zero else None):      # a +x start must be recorded; a random-yaw cell must not carry one
        raise ValueError("EX-42 named kind evaluation start yaw record differs from the plan")
    levels, types = kind_assignment(n, record["rows"], table, family, kind, level)
    if record.get("assignment_sha256") != assignment_sha256(levels, types):
        raise ValueError("EX-42 named kind evaluation assignment SHA differs")
    tiles = result.get("terrain_tiles") or []
    if len(tiles) != n or any(
            tile.get("env") != i or tile.get("column") != int(types[i])
            or tile.get("level") != level or tile.get("kind") != kind
            for i, tile in enumerate(tiles)):
        raise ValueError("EX-42 named kind evaluation terrain tiles differ")


def preflight(mesh_dir):
    folder = Path(mesh_dir).resolve(strict=True)
    manifest_path = folder / "mesh_manifest.json"
    npz_path = folder / "terrain_mesh.npz"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (manifest.get("format") != "foothold-ex42-combined-mesh/1"
            or manifest.get("families_present") != ["A", "B", "C", "D", "E"]
            or manifest.get("families_missing") != []
            or manifest.get("seed") != 42):
        raise ValueError("EX-42 calibration requires the full seed-42 ABCDE mesh")
    loaded = load_combined_mesh(npz_path, manifest.get("mesh_sha256"))
    if list(loaded["origins"].shape) != manifest.get("origins_shape") or loaded["origins"].shape[:2] != (10, 76):
        raise ValueError("EX-42 calibration mesh shape differs from the 10x76 E0 grid")
    table = build_column_table(loaded["column_family"])
    if any(row["kind"] is None for row in table):
        raise ValueError("EX-42 calibration mesh has an unknown column kind")
    if loaded["column_family"][:EVAL_COLS] != ["A"] * EVAL_COLS:
        raise ValueError("EX-42 calibration requires the first 23 columns to be family A")
    return {"mesh_npz": str(npz_path), "manifest": str(manifest_path),
            "mesh_sha256": loaded["mesh_sha256"], "columns": [row["kind"] for row in table],
            "column_family": loaded["column_family"], "eval_cols": EVAL_COLS,
            "eval_columns": [row["kind"] for row in table[:EVAL_COLS]]}


def crop_cells_for(record, *, level, family=None, kind=None):
    """(row, column) cells a fixed evaluation visits: the named kind's columns, or the A calibration columns, at `level`."""
    if level is None:
        raise ValueError("a cropped mesh needs a fixed level")
    if kind is None:
        return [(int(level), c) for c in range(record["eval_cols"])]
    ids = [i for i, (f, k) in enumerate(zip(record["column_family"], record["columns"])) if f == family and k == kind]
    if not ids:
        raise ValueError(f"crop cells: no column for {family}/{kind}")
    return [(int(level), i) for i in ids]


def attach(env_cfg, mesh_dir, *, crop_margin=None, crop_level=None, crop_family=None, crop_kind=None):
    """Before gym.make: mount exact mesh and its declared per-column reset.

    `crop_margin` (CPU evaluation only, default None = the whole mesh as always) keeps just the triangles around the cells the
    fixed evaluation visits."""
    from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg
    from foothold_s2.terrains.ex42_column_reset import apply_column_reset

    record = preflight(mesh_dir)
    env_cfg.scene.terrain.terrain_type = "generator"
    if crop_margin is None:
        env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(
            record["mesh_npz"], record["mesh_sha256"])
    else:
        env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(
            record["mesh_npz"], record["mesh_sha256"], crop_margin=crop_margin,
            crop_cells=crop_cells_for(record, level=crop_level, family=crop_family, kind=crop_kind))
    env_cfg.scene.terrain.max_init_terrain_level = 2
    record.update(apply_column_reset(env_cfg, build_column_table(record["column_family"])) or {})
    return record
