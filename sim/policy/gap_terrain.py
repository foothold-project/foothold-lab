"""Procedural forward-facing gap terrain for Go2 training."""

from __future__ import annotations

import numpy as np
import trimesh

from isaaclab.terrains import SubTerrainBaseCfg
from isaaclab.utils import configclass


def forward_gap_terrain(
    difficulty: float,
    cfg: "ForwardGapTerrainCfg",
) -> tuple[list[trimesh.Trimesh], np.ndarray]:
    """Create a run-up platform, a bottomless gap, and a landing platform."""

    difficulty = float(np.clip(difficulty, 0.0, 1.0))
    gap_width = cfg.gap_width_range[0] + difficulty * (
        cfg.gap_width_range[1] - cfg.gap_width_range[0]
    )

    size_x, size_y = cfg.size
    gap_center_x = size_x * cfg.gap_center_ratio
    gap_start_x = gap_center_x - 0.5 * gap_width
    gap_end_x = gap_center_x + 0.5 * gap_width

    if gap_start_x <= 0.0 or gap_end_x >= size_x:
        raise ValueError(f"Gap is outside terrain bounds: size={cfg.size}, width={gap_width:.3f}")

    meshes: list[trimesh.Trimesh] = []

    # The two slabs have no connecting floor, so falling into the gap is a real failure.
    run_up_size = (gap_start_x, size_y, cfg.slab_thickness)
    run_up_pos = (0.5 * gap_start_x, 0.5 * size_y, -0.5 * cfg.slab_thickness)
    meshes.append(trimesh.creation.box(run_up_size, trimesh.transformations.translation_matrix(run_up_pos)))

    landing_length = size_x - gap_end_x
    landing_size = (landing_length, size_y, cfg.slab_thickness)
    landing_pos = (gap_end_x + 0.5 * landing_length, 0.5 * size_y, -0.5 * cfg.slab_thickness)
    meshes.append(trimesh.creation.box(landing_size, trimesh.transformations.translation_matrix(landing_pos)))

    # The returned origin becomes the robot spawn reference for this tile.
    spawn_x = gap_start_x - cfg.approach_distance
    if spawn_x < cfg.minimum_spawn_x:
        raise ValueError("approach_distance leaves insufficient space before the terrain boundary")

    origin = np.array([spawn_x, 0.5 * size_y, 0.0], dtype=np.float64)
    return meshes, origin


@configclass
class ForwardGapTerrainCfg(SubTerrainBaseCfg):
    """Configuration for a bottomless gap perpendicular to the +x direction."""

    function = forward_gap_terrain

    gap_width_range: tuple[float, float] = (0.05, 0.20)
    gap_center_ratio: float = 0.50
    approach_distance: float = 1.50
    slab_thickness: float = 1.00
    minimum_spawn_x: float = 0.75
