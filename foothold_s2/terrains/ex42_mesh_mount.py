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


def column_tile_sizes(origins) -> tuple[np.ndarray, float]:
    """(tile_x per column, tile_y) of the joined grid, from the origin spacing (rows run along x).

    Row pitch of one column = that family's tile length along x; it must be one positive number per
    column. The y value is the median positive spacing between neighbouring columns of the same
    kind of tile (borders between families are larger and are ignored by the median).
    """
    o = np.asarray(origins, dtype=np.float64)
    if o.ndim != 3 or o.shape[0] < 2 or o.shape[1] < 1:
        raise ValueError("tile sizes need origins of shape (rows >= 2, columns, 3)")
    pitch = np.diff(o[:, :, 0], axis=0)                       # (rows-1, cols)
    tile_x = pitch.mean(axis=0)
    if not np.isfinite(tile_x).all() or (tile_x <= 0).any() or not np.allclose(pitch, tile_x[None], atol=1e-4):
        raise ValueError("origin row spacing must be one positive tile length per column")
    dy = np.diff(o[0, :, 1]) if o.shape[1] > 1 else np.array([tile_x.mean()])
    dy = dy[dy > 0]
    return tile_x, float(np.median(dy)) if len(dy) else float(tile_x.mean())


def mesh_file_generator_cfg(npz_path: str | Path, mesh_sha256: str | None = None):
    """Isaac-side cfg whose class_type loads the saved mesh. Kit python only."""
    from isaaclab.utils import configclass

    loaded = load_combined_mesh(npz_path, mesh_sha256)
    tile_x, tile_y = column_tile_sizes(loaded["origins"])

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
        # Tiles differ per family. `size` must NOT be (0, 0): the free-velocity promotion rule compares
        # max distance with size[0] / 2, so 0 promotes every moving env. The scalar below is the median
        # tile; the promotion rule reads the per-column table (rules.promotion_size_x).
        size: tuple = (float(np.median(tile_x)), tile_y)
        tile_x_by_column: tuple = tuple(float(v) for v in tile_x)
        seed: int = 0
        curriculum: bool = True
        use_cache: bool = False

    return CombinedMeshGeneratorCfg()
