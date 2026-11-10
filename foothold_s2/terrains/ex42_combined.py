"""Join independent family terrain generators into ONE mesh with one origins tensor.

DESIGN-EX42-TERRAIN draft 5.1 option (da): every family keeps its own generator (own tile
size, own scales), their meshes are placed next to each other and `terrain_origins` is
concatenated to (rows, total_columns, 3), so `terrain_origins[level, column]` keeps working.

Axis note (checked in Isaac Lab terrain_generator.py:183): the generator centres its mesh with
x = -size[0] * num_rows / 2 and y = -size[1] * num_cols / 2, so ROWS run along x and COLUMNS run
along y. Joining columns therefore means translating along y (default `axis=1`). The task text
said "x direction"; pass axis=0 only if the rows were meant.

Pure numpy / trimesh. No Isaac import, so it is CPU-testable. Nothing here invents a dimension:
offsets come from the measured mesh bounds of each part.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def combine_family_parts(parts: list[dict[str, Any]], *, axis: int = 1,
                         tolerance: float = 1e-6) -> dict[str, Any]:
    """parts: [{name, mesh (trimesh-like: vertices, faces, bounds), origins (rows, cols, 3)}].

    Each part is shifted along `axis` so its minimum touches the previous part's maximum.
    Returns {vertices, faces, origins, column_family, offsets, bounds}. Raises on mismatched
    rows, origins outside their own mesh, or any overlap of parts after placement.
    """
    if axis not in (0, 1):
        raise ValueError("axis must be 0 (x) or 1 (y)")
    if not parts:
        raise ValueError("no family parts to combine")
    rows = {np.asarray(p["origins"]).shape[0] for p in parts}
    if len(rows) != 1:
        raise ValueError(f"family parts have different row counts: {sorted(rows)}")
    other = 1 - axis
    all_vertices, all_faces, all_origins = [], [], []
    column_family: list[str] = []
    offsets: dict[str, float] = {}
    intervals: list[tuple[str, float, float]] = []
    vertex_base = 0
    cursor = None
    for part in parts:
        name = part["name"]
        origins = np.asarray(part["origins"], dtype=np.float64)
        if origins.ndim != 3 or origins.shape[2] != 3 or origins.shape[1] < 1:
            raise ValueError(f"origins of {name} must have shape (rows, cols, 3)")
        vertices = np.asarray(part["mesh"].vertices, dtype=np.float64)
        faces = np.asarray(part["mesh"].faces, dtype=np.int64)
        if len(vertices) == 0 or len(faces) == 0:
            raise ValueError(f"empty mesh for family {name}")
        low, high = float(vertices[:, axis].min()), float(vertices[:, axis].max())
        shift = 0.0 if cursor is None else cursor - low
        # origins must sit inside the part's own mesh bounds, on both horizontal axes
        for ax in (axis, other):
            lo, hi = float(vertices[:, ax].min()), float(vertices[:, ax].max())
            if origins[..., ax].min() < lo - tolerance or origins[..., ax].max() > hi + tolerance:
                raise ValueError(f"origins of {name} lie outside its mesh on axis {ax}")
        moved = vertices.copy()
        moved[:, axis] += shift
        moved_origins = origins.copy()
        moved_origins[..., axis] += shift
        offsets[name] = shift
        intervals.append((name, low + shift, high + shift))
        cursor = high + shift
        all_vertices.append(moved)
        all_faces.append(faces + vertex_base)
        vertex_base += len(vertices)
        all_origins.append(moved_origins)
        column_family.extend([name] * origins.shape[1])
    for (a, a0, a1), (b, b0, b1) in zip(intervals, intervals[1:]):
        if b0 < a1 - tolerance:
            raise ValueError(f"families {a} and {b} overlap along axis {axis}")
    vertices = np.concatenate(all_vertices)
    faces = np.concatenate(all_faces)
    origins = np.concatenate(all_origins, axis=1)
    return {
        "vertices": vertices, "faces": faces, "origins": origins,
        "column_family": column_family, "offsets": offsets,
        "bounds": [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()],
        "axis": axis,
    }


def family_column_summary(column_family: list[str]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for name in column_family:
        summary[name] = summary.get(name, 0) + 1
    return summary
