"""CPU preflight and Kit attachment for EX-42 calibration on one fixed mesh."""
from __future__ import annotations

import json
from pathlib import Path

from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh
from foothold_s2.terrains.ex42_column_reset import build_column_table


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
    return {"mesh_npz": str(npz_path), "manifest": str(manifest_path),
            "mesh_sha256": loaded["mesh_sha256"], "columns": [row["kind"] for row in table],
            "column_family": loaded["column_family"]}


def attach(env_cfg, mesh_dir):
    """Before gym.make: mount exact mesh and its declared per-column reset."""
    from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg
    from foothold_s2.terrains.ex42_column_reset import apply_column_reset

    record = preflight(mesh_dir)
    env_cfg.scene.terrain.terrain_type = "generator"
    env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(
        record["mesh_npz"], record["mesh_sha256"])
    env_cfg.scene.terrain.max_init_terrain_level = 2
    apply_column_reset(env_cfg, build_column_table(record["column_family"]))
    return record
