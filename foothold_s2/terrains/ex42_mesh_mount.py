"""Mount the joined EX-42 terrain mesh (terrain_mesh.npz from scripts/ex42_mesh_build.py) in a training env.

Isaac Lab's TerrainImporter (terrain_type="generator") only calls
`cfg.class_type(cfg=cfg, device=device)` and then reads `.terrain_mesh`, `.terrain_origins`
and `.flat_patches` (terrain_importer.py:84-99). `CombinedMeshGenerator` provides exactly those
three from the saved npz, so no importer subclass is needed: assign `mesh_file_generator_cfg(...)`
to `env_cfg.scene.terrain.terrain_generator`.

The numpy helpers (load_combined_mesh, local_mesh_heights) import no Isaac and are CPU-tested.
Nothing here decides which columns are exposed to training (exposure shares stay with the
curriculum); it only supplies the mesh and the (rows, columns, 3) origins.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def load_combined_mesh(npz_path: str | Path, expected_mesh_sha256: str | None = None) -> dict[str, Any]:
    """Load vertices / faces / origins / column_family; verify shapes and the optional sha256."""
    data = np.load(Path(npz_path), allow_pickle=False)
    vertices = np.asarray(data["vertices"])
    faces = np.asarray(data["faces"])
    origins = np.asarray(data["origins"], dtype=np.float64)
    column_family = [str(v) for v in data["column_family"]]
    if vertices.ndim != 2 or vertices.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError("combined mesh vertices/faces must be (N,3) and (M,3)")
    if len(vertices) == 0 or len(faces) == 0:
        raise ValueError("combined mesh is empty")
    if int(faces.max()) >= len(vertices) or int(faces.min()) < 0:
        raise ValueError("combined mesh faces reference missing vertices")
    if origins.ndim != 3 or origins.shape[2] != 3 or origins.shape[1] != len(column_family):
        raise ValueError("terrain_origins must be (rows, columns, 3) with one family name per column")
    if not np.isfinite(origins).all() or not np.isfinite(vertices).all():
        raise ValueError("combined mesh contains non-finite values")
    sha = hashlib.sha256(vertices.astype(np.float32).tobytes() + faces.astype(np.int32).tobytes()).hexdigest()
    if expected_mesh_sha256 is not None and sha != expected_mesh_sha256:
        raise ValueError(f"combined mesh sha256 {sha[:8]} differs from the expected {expected_mesh_sha256[:8]}")
    return {"vertices": vertices, "faces": faces, "origins": origins,
            "column_family": column_family, "mesh_sha256": sha}


def expected_sha_from_manifest(mesh_manifest_path: str | Path) -> str:
    doc = json.loads(Path(mesh_manifest_path).read_text(encoding="utf-8"))
    sha = doc.get("mesh_sha256")
    if not isinstance(sha, str) or len(sha) != 64:
        raise ValueError("mesh_manifest.json has no mesh_sha256")
    return sha


class MeshHeights:
    """Top-surface height under xy points, by trimesh ray casting on a local patch.

    Independent of warp. Per-face xy bounds are computed once, so many small queries (one per
    env) stay cheap. A downward ray starts at z = max + 10 and the highest hit counts, so a
    point over a gap reads the pit floor, which is the mesh under that xy and nothing else.
    """

    def __init__(self, vertices: np.ndarray, faces: np.ndarray):
        self.vertices, self.faces = vertices, faces
        corners = vertices[faces][:, :, :2]
        self.lo, self.hi = corners.min(axis=1), corners.max(axis=1)   # large faces count
        self.top = float(vertices[:, 2].max()) + 10.0

    def at(self, points_xy: np.ndarray, radius: float = 3.0) -> np.ndarray:
        import trimesh

        pts = np.asarray(points_xy, dtype=np.float64).reshape(-1, 2)
        out = np.full(len(pts), np.nan)
        if not len(pts):
            return out
        center = pts.mean(axis=0)
        reach = float(np.abs(pts - center).max()) + radius
        near = ((self.hi[:, 0] >= center[0] - reach) & (self.lo[:, 0] <= center[0] + reach)
                & (self.hi[:, 1] >= center[1] - reach) & (self.lo[:, 1] <= center[1] + reach))
        if not near.any():
            return out
        local = trimesh.Trimesh(vertices=self.vertices, faces=self.faces[near], process=False)
        origins = np.column_stack([pts, np.full(len(pts), self.top)])
        directions = np.tile([0.0, 0.0, -1.0], (len(pts), 1))
        locations, ray_index, _tri = local.ray.intersects_location(origins, directions, multiple_hits=True)
        for i in np.unique(ray_index):
            out[i] = locations[ray_index == i][:, 2].max()
        return out


def local_mesh_heights(vertices: np.ndarray, faces: np.ndarray, points_xy: np.ndarray,
                       radius: float = 3.0) -> np.ndarray:
    """One-shot form of MeshHeights.at."""
    return MeshHeights(vertices, faces).at(points_xy, radius)


TILE_PITCH_TOLERANCE_M = 0.10      # row spacing that differs from the column's median by more is reported
TILE_PITCH_LIMIT_FRACTION = 0.25   # ... and one that differs by more than this share of the tile is an error


def column_tile_sizes(origins) -> tuple[np.ndarray, float, list[dict[str, float]]]:
    """(tile_x per column, tile_y, irregular columns) of the joined grid, from the origin spacing.

    Rows run along x. The tile length of a column is the MEDIAN spacing between its origins: a
    family generator may move the origin inside its tile to the safe support patch (real C meshes
    show 8.92 / 9.08 m next to 9 m), so the spacing is not exactly equal to the tile length.
    Columns whose spacing strays from the median by more than TILE_PITCH_TOLERANCE_M are returned in
    the third value ({column, median, max_deviation}); a deviation over a quarter tile means the
    origins are not one row per tile and raises. tile_y is the median positive spacing between
    neighbouring columns (borders between families are larger and are ignored by the median).
    """
    o = np.asarray(origins, dtype=np.float64)
    if o.ndim != 3 or o.shape[0] < 2 or o.shape[1] < 1:
        raise ValueError("tile sizes need origins of shape (rows >= 2, columns, 3)")
    if not np.isfinite(o).all():
        raise ValueError("origins must be finite")
    pitch = np.diff(o[:, :, 0], axis=0)                       # (rows-1, cols)
    tile_x = np.median(pitch, axis=0)
    if (tile_x <= 0).any():
        raise ValueError("origin row spacing must be positive: the rows of a column are not ordered along x")
    deviation = np.abs(pitch - tile_x[None]).max(axis=0)
    if (deviation > TILE_PITCH_LIMIT_FRACTION * tile_x).any():
        raise ValueError("origin row spacing varies by more than a quarter tile: not one origin per tile row")
    irregular = [{"column": int(c), "median": float(tile_x[c]), "max_deviation": float(deviation[c])}
                 for c in np.nonzero(deviation > TILE_PITCH_TOLERANCE_M)[0]]
    dy = np.diff(o[0, :, 1]) if o.shape[1] > 1 else np.array([tile_x.mean()])
    dy = dy[dy > 0]
    return tile_x, (float(np.median(dy)) if len(dy) else float(tile_x.mean())), irregular


# CPU-only evaluation aid: the joined mesh has millions of triangles and a single PhysX contact pair can spend minutes in
# BV4 overlap tests over them (2026-11-19). `crop_to_cells` keeps only the triangles around the evaluated (level, column)
# cells. World coordinates, origins and column families are untouched. Never used by training or GPU evaluation.
CROP_MARGIN_DEFAULT_M = 8.0
LAST_CROP_RECORD: dict[str, Any] = {}      # set by the cropped generator when it runs (same process as the evaluator)


def crop_to_cells(vertices: np.ndarray, faces: np.ndarray, origins, tile_x, tile_y: float,
                  cells, margin: float) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Faces whose centroid lies within tile/2 + margin (x and y) of any cell origin; vertices renumbered, coordinates kept.

    `cells` is a list of (row, column) into `origins` (rows, columns, 3); `tile_x` is the per-column tile length, `tile_y`
    the column pitch (column_tile_sizes). Raises when a cell is outside the grid, the margin is negative or nothing is kept.
    """
    o = np.asarray(origins, dtype=np.float64)
    tx = np.asarray(tile_x, dtype=np.float64)
    if not cells or margin < 0 or not np.isfinite(margin):
        raise ValueError("crop needs at least one cell and a finite non-negative margin")
    centroid = np.asarray(vertices, dtype=np.float64)[np.asarray(faces)].mean(axis=1)
    keep = np.zeros(len(faces), dtype=bool)
    clean = []
    for row, col in cells:
        if not (0 <= int(row) < o.shape[0] and 0 <= int(col) < o.shape[1]):
            raise ValueError(f"crop cell ({row}, {col}) is outside the {o.shape[0]}x{o.shape[1]} grid")
        ox, oy = o[int(row), int(col), 0], o[int(row), int(col), 1]
        keep |= (np.abs(centroid[:, 0] - ox) <= tx[int(col)] / 2 + margin) & (np.abs(centroid[:, 1] - oy) <= tile_y / 2 + margin)
        clean.append([int(row), int(col)])
    kept = np.asarray(faces)[keep]
    if len(kept) == 0:
        raise ValueError("crop kept no triangle")
    used = np.unique(kept)
    renumber = np.full(len(vertices), -1, dtype=np.int64)
    renumber[used] = np.arange(len(used))
    new_vertices, new_faces = np.asarray(vertices)[used], renumber[kept]
    sha = hashlib.sha256(new_vertices.astype(np.float32).tobytes() + new_faces.astype(np.int32).tobytes()).hexdigest()
    return new_vertices, new_faces, {"cropped": True, "margin_m": float(margin), "cells": clean, "faces_before": int(len(faces)),
                                     "faces_after": int(len(new_faces)), "cropped_mesh_sha256": sha}


def mesh_file_generator_cfg(npz_path: str | Path, mesh_sha256: str | None = None, *, crop_cells=None, crop_margin: float | None = None):
    """Isaac-side cfg whose class_type loads the saved mesh. Kit python only.

    `crop_cells` (CPU evaluation only, default None) returns a cfg whose generator keeps just the triangles around those
    (row, column) cells (`crop_to_cells`); with None the cfg is the very same one as before.
    """
    from isaaclab.utils import configclass

    loaded = load_combined_mesh(npz_path, mesh_sha256)
    tile_x, tile_y, irregular = column_tile_sizes(loaded["origins"])

    class CombinedMeshGenerator:
        def __init__(self, cfg, device="cpu"):
            import trimesh

            data = load_combined_mesh(cfg.mesh_npz, cfg.mesh_sha256)
            self.terrain_mesh = trimesh.Trimesh(vertices=data["vertices"].astype(np.float64),
                                                faces=data["faces"].astype(np.int64), process=False)
            self.terrain_origins = data["origins"]
            self.flat_patches = {}

    @configclass
    class CombinedMeshGeneratorCfg:
        class_type: type = CombinedMeshGenerator
        mesh_npz: str = str(Path(npz_path).resolve())
        mesh_sha256: str = loaded["mesh_sha256"]
        # fields other code may read from a generator cfg; they describe the joined grid
        num_rows: int = int(loaded["origins"].shape[0])
        num_cols: int = int(loaded["origins"].shape[1])
        column_family: tuple = tuple(loaded["column_family"])      # family letter per joined column
        # Tiles differ per family. `size` must NOT be (0, 0): the free-velocity promotion rule compares
        # max distance with size[0] / 2, so 0 promotes every moving env. The scalar below is the median
        # tile; the promotion rule reads the per-column table (rules.promotion_size_x).
        size: tuple = (float(np.median(tile_x)), tile_y)
        tile_x_by_column: tuple = tuple(float(v) for v in tile_x)
        tile_x_irregular_columns: tuple = tuple((r["column"], r["max_deviation"]) for r in irregular)
        seed: int = 0
        curriculum: bool = True
        use_cache: bool = False

    if crop_cells is None:
        return CombinedMeshGeneratorCfg()

    cells = tuple((int(r), int(c)) for r, c in crop_cells)
    margin = CROP_MARGIN_DEFAULT_M if crop_margin is None else float(crop_margin)

    class CroppedMeshGenerator(CombinedMeshGenerator):
        def __init__(self, cfg, device="cpu"):
            import trimesh

            data = load_combined_mesh(cfg.mesh_npz, cfg.mesh_sha256)
            vertices, faces, record = crop_to_cells(data["vertices"], data["faces"], data["origins"], tile_x, tile_y,
                                                    cfg.crop_cells, cfg.crop_margin)
            record["source_mesh_sha256"] = data["mesh_sha256"]
            LAST_CROP_RECORD.clear()
            LAST_CROP_RECORD.update(record)
            self.terrain_mesh = trimesh.Trimesh(vertices=vertices.astype(np.float64), faces=faces.astype(np.int64), process=False)
            self.terrain_origins = data["origins"]
            self.flat_patches = {}

    @configclass
    class CroppedMeshGeneratorCfg(CombinedMeshGeneratorCfg):
        class_type: type = CroppedMeshGenerator
        crop_cells: tuple = cells
        crop_margin: float = margin

    return CroppedMeshGeneratorCfg()
