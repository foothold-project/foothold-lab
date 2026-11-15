"""Replicate one approved evaluation-only tile for independent parallel envs.

The published evaluation tile has one geometry row and one column. Isaac's
terrain importer reuses an origin when envs exceed tiles, so a 64-env D44 cell
must have 64 distinct copies. The source mesh and its anchors remain pinned.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh


FORMAT = "foothold-ex42-evaluation-replica/1"
SOURCE_FORMAT = "foothold-ex42-evaluation-mesh/1"
LANDING = "eval_stairs_landing_016"
ANCHORS = ("approach", "landing_center")


def source_tile(mesh_dir: Path) -> tuple[dict, dict]:
    """Read the one-tile manifest and reject changed bytes or unknown geometry."""
    mesh_dir = Path(mesh_dir)
    manifest_path = mesh_dir / "mesh_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    columns = manifest.get("columns")
    if (manifest.get("format") != SOURCE_FORMAT or manifest.get("training_allowed") is not False
            or manifest.get("origins_shape") != [1, 1, 3] or not isinstance(columns, list)
            or len(columns) != 1 or columns[0].get("kind") != LANDING
            or columns[0].get("column") != 0 or columns[0].get("family") != "V"
            or columns[0].get("tile_size_m") != [8.0, 8.0]
            or type(manifest.get("seed")) is not int):
        raise ValueError("D44 needs the approved single landing evaluation tile")
    npz = mesh_dir / "terrain_mesh.npz"
    if hashlib.sha256(npz.read_bytes()).hexdigest() != manifest.get("mesh_file_sha256"):
        raise ValueError("D44 evaluation tile file SHA differs")
    source = load_combined_mesh(npz, manifest.get("mesh_sha256"))
    if (list(source["origins"].shape) != [1, 1, 3]
            or not np.allclose(source["origins"][0, 0], columns[0]["origin_world_m"], atol=1e-7, rtol=0)):
        raise ValueError("D44 evaluation tile origin differs")
    anchors = columns[0].get("anchors_local_m")
    if (not isinstance(anchors, dict) or set(ANCHORS) - set(anchors)
            or not all(len(anchors[key]) == 3 and np.isfinite(anchors[key]).all() for key in ANCHORS)
            or len(anchors.get("stop_band_x", [])) != 2
            or len(anchors.get("landing_bounds_xy", [])) != 4):
        raise ValueError("D44 evaluation tile anchors missing")
    return manifest, columns[0]


def build_replicas(mesh_dir: Path, output: Path, *, anchor: str, grid: int = 8) -> dict:
    """Write an isolated square grid, one identical tile per env, without overwrites."""
    import trimesh

    if anchor not in ANCHORS or type(grid) is not int or grid < 2:
        raise ValueError("D44 replica anchor or grid invalid")
    manifest, column = source_tile(mesh_dir)
    from foothold_s2.terrains.ex42_eval_terrains import build_tile

    tile = build_tile(LANDING, seed=manifest["seed"])
    # Every anchor pinned in the published manifest must regenerate exactly; anchors the builder learned to
    # report after the tile was published (11/11: course_exit, stop_band_interior_surface_z_m) may be extra,
    # because the geometry itself is pinned by the file SHA above and by dimensions and origin here.
    pinned = column["anchors_local_m"]
    if (any(tile.anchors.get(key) != value for key, value in pinned.items())
            or tile.dimensions != column["dimensions"]
            or list(tile.origin) != column["origin_world_m"]):
        raise ValueError("D44 regenerated tile differs from pinned anchors or dimensions")
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    pitch_x, pitch_y = column["tile_size_m"]
    pieces, origins = [], np.empty((grid, grid, 3), dtype=np.float64)
    for row in range(grid):
        for col in range(grid):
            offset = np.array([row * pitch_x, col * pitch_y, 0.0])
            copy = tile.mesh.copy()
            copy.apply_translation(offset)
            pieces.append(copy)
            origins[row, col] = np.asarray(tile.anchors[anchor], dtype=np.float64) + offset
    # Border is outside the grid, as in the one-tile source. It never covers a pit.
    width, height = grid * pitch_x, grid * pitch_y
    for x0, x1, y0, y1 in ((-20., 0., -20., height + 20.),
                           (width, width + 20., -20., height + 20.),
                           (0., width, -20., 0.), (0., width, height, height + 20.)):
        box = trimesh.creation.box((x1-x0, y1-y0, .2))
        box.apply_translation(((x0+x1)/2, (y0+y1)/2, -.1))
        pieces.append(box)
    joined = trimesh.util.concatenate(pieces)
    vertices = np.asarray(joined.vertices, dtype=np.float32)
    faces = np.asarray(joined.faces, dtype=np.int32)
    mesh_sha = hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    npz = output / "terrain_mesh.npz"
    np.savez_compressed(npz, vertices=vertices, faces=faces, origins=origins,
                        column_family=np.array(["V"] * grid))
    record = {"format": FORMAT, "source_manifest": str(Path(mesh_dir) / "mesh_manifest.json"),
              "source_manifest_sha256": hashlib.sha256((Path(mesh_dir) / "mesh_manifest.json").read_bytes()).hexdigest(),
              "source_mesh_sha256": manifest["mesh_sha256"], "mesh_sha256": mesh_sha,
              "mesh_file_sha256": hashlib.sha256(npz.read_bytes()).hexdigest(),
              "seed": manifest["seed"], "kind": LANDING, "anchor": anchor,
              "anchors_local_m": column["anchors_local_m"], "rows": grid, "cols": grid,
              "envs": grid * grid, "tile_size_m": [pitch_x, pitch_y]}
    (output / "replica_receipt.json").write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return record


def preflight_replicas(mesh_dir: Path, replica_dir: Path, *, anchor: str,
                       expected_mesh_sha256: str | None = None, grid: int = 8) -> dict:
    """Bind the Kit input to both source and expanded mesh bytes before launch."""
    manifest, column = source_tile(mesh_dir)
    receipt_path = Path(replica_dir) / "replica_receipt.json"
    record = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    npz = Path(replica_dir) / "terrain_mesh.npz"
    if (record.get("format") != FORMAT or record.get("source_manifest") != str(Path(mesh_dir) / "mesh_manifest.json")
            or record.get("source_manifest_sha256") != hashlib.sha256(
                (Path(mesh_dir) / "mesh_manifest.json").read_bytes()).hexdigest()
            or record.get("source_mesh_sha256") != manifest["mesh_sha256"]
            or record.get("kind") != LANDING or record.get("anchor") != anchor
            or record.get("rows") != grid or record.get("cols") != grid
            or record.get("envs") != grid * grid
            or record.get("anchors_local_m") != column["anchors_local_m"]
            or record.get("mesh_file_sha256") != hashlib.sha256(npz.read_bytes()).hexdigest()
            or (expected_mesh_sha256 is not None and record.get("mesh_sha256") != expected_mesh_sha256)):
        raise ValueError("D44 replica receipt or mesh bytes differ")
    loaded = load_combined_mesh(npz, record["mesh_sha256"])
    if list(loaded["origins"].shape) != [grid, grid, 3]:
        raise ValueError("D44 replica grid shape differs")
    expected = np.asarray(column["anchors_local_m"][anchor], dtype=np.float64)[None, None, :]
    row = np.arange(grid, dtype=np.float64)[:, None, None] * np.array([column["tile_size_m"][0], 0, 0])
    col = np.arange(grid, dtype=np.float64)[None, :, None] * np.array([0, column["tile_size_m"][1], 0])
    if not np.allclose(loaded["origins"], expected + row + col, atol=1e-7, rtol=0):
        raise ValueError("D44 replica origins differ from pinned anchor")
    return record


def assign_independent_env_origins(raw, *, grid: int = 8) -> dict:
    """Assign each of the 64 environments to one distinct physical tile."""
    import torch

    terrain = raw.scene.terrain
    n = int(terrain.terrain_levels.numel())
    if n != grid * grid or tuple(terrain.terrain_origins.shape) != (grid, grid, 3):
        raise ValueError("D44 needs one terrain tile per evaluation environment")
    ids = torch.arange(n, device=terrain.terrain_levels.device)
    rows, cols = ids.div(grid, rounding_mode="floor"), ids.remainder(grid)
    terrain.terrain_levels.copy_(rows.to(terrain.terrain_levels.dtype))
    terrain.terrain_types.copy_(cols.to(terrain.terrain_types.dtype))
    terrain.env_origins.copy_(terrain.terrain_origins[rows, cols])
    if (not torch.equal(raw.scene.env_origins, terrain.env_origins)
            or torch.unique(terrain.env_origins, dim=0).shape[0] != n):
        raise RuntimeError("D44 environment origins overlap or differ from terrain")
    return {"rows": grid, "cols": grid, "envs": n,
            "assignment": "row=env//grid, column=env%grid", "unique_origins": n}
