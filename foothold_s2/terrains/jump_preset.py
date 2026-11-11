"""Opt-in EX-42 family F, DESIGN-JUMP v0.2 section 2.2: J2/J3/J4 only.

The approved ladder specifies heights and gap widths, not a compulsory gait.
Carrier, pit depth, floor thickness and goal placement are explicit project
assumptions. Geometry availability is not proof of Go2 jump feasibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import warnings

import numpy as np

KINDS = ('jump_up_low', 'jump_down_low', 'jump_gap', 'jump_up_high')
PRESET_ID = 'jump_go2_v1'
LEVEL_VALUES_M = {
    'jump_up_low': (.10, .20, .30),
    'jump_down_low': (.10, .20, .30),
    'jump_gap': (.15, .30, .45, .60),
    'jump_up_high': (.40, .50, .60, .65, .70, .75),
}
LEVEL_COUNTS = {kind: len(values) for kind, values in LEVEL_VALUES_M.items()}
STAGES = dict(zip(KINDS, ('J2', 'J2', 'J3', 'J4')))
SOURCE_COMMIT = '368d03e2061b505fc72ad73e9cd2527a766e7738'
SOURCE_PATH = 'inbox/jay/20261104-jump/DESIGN-JUMP-draft.md'
SOURCE_SECTION = '2.2'
# Implementation assumptions, not published paper measurements.
TILE_SIZE = (8., 8.)
LAYOUT_ROWS = 10
GAP_DEPTH_M = 1.0
FLOOR_THICKNESS_M = .10
# Keep existing reset defaults; the first support patch accommodates XY +-0.5
# and all yaw angles of the 0.70 x 0.50 m support-test rectangle.
RESET_RANGES = {}


@dataclass(frozen=True)
class JumpTile:
    kind: str
    level: int
    seed: int
    size: tuple[float, float]
    boxes: np.ndarray  # local x0,x1,y0,y1,z0,z1, metres
    origin: np.ndarray
    dimensions: dict[str, float]


def _positive(name, value):
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating))
            or not math.isfinite(float(value)) or value <= 0):
        raise ValueError(f'{name} must be finite and positive')
    return float(value)


def _identity(kind, level, seed):
    if kind not in KINDS:
        raise ValueError(f'unknown family-F kind: {kind!r}')
    if (isinstance(level, (bool, np.bool_)) or not isinstance(level, (int, np.integer))
            or not 0 <= level < LEVEL_COUNTS[kind]):
        raise ValueError(f'{kind} physical level must be in [0,{LEVEL_COUNTS[kind]-1}]')
    if (isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer))
            or not 0 <= seed < 2**32):
        raise ValueError('seed must be an explicit uint32 integer')


def build_tile(kind, level, *, seed, size=TILE_SIZE,
               gap_depth_m=GAP_DEPTH_M, floor_thickness_m=FLOOR_THICKNESS_M):
    """Closed box mesh specification. Only the requested ladder dimension varies.

    Up and down are separate, full-width steps; no side route on the tile.
    Gap has a physical floor (contact with that floor is not successful crossing).
    No RNG is consumed. Seed changes identify runs, not independent geometries.
    """
    _identity(kind, level, seed)
    if not isinstance(size, (tuple, list)) or len(size) != 2:
        raise ValueError('size must contain two lengths')
    sx, sy = (_positive('size', value) for value in size)
    if sx < 8 or sy < 4:
        raise ValueError('family F needs size >= (8,4) m for its approach and safe reset patch')
    depth = _positive('gap_depth_m', gap_depth_m)
    floor = _positive('floor_thickness_m', floor_thickness_m)
    value = LEVEL_VALUES_M[kind][level]
    center = sx / 2
    dimensions = {'tile_x_m': sx, 'tile_y_m': sy, 'floor_thickness_m': floor}
    origin = np.array([1., sy/2, 0.])
    if kind == 'jump_gap':
        lo, hi = center-value/2, center+value/2
        boxes = [(0., sx, 0., sy, -depth-floor, -depth),
                 (0., lo, 0., sy, -depth, 0.), (hi, sx, 0., sy, -depth, 0.)]
        dimensions.update(gap_width_m=value, gap_depth_m=depth)
    else:
        boxes = [(0., sx, 0., sy, -floor, 0.)]
        if kind == 'jump_down_low':
            boxes.append((0., center, 0., sy, 0., value))
            origin[2] = value
        else:
            boxes.append((center, sx, 0., sy, 0., value))
        dimensions['ledge_height_m'] = value
    return JumpTile(kind, int(level), int(seed), (sx, sy),
                    np.asarray(boxes, dtype=np.float64), origin, dimensions)


def meshes_for(tile):
    import trimesh
    meshes = []
    for x0, x1, y0, y1, z0, z1 in tile.boxes:
        transform = trimesh.transformations.translation_matrix(
            ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2))
        meshes.append(trimesh.creation.box((x1-x0, y1-y0, z1-z0), transform=transform))
    return meshes


def desired_flags(size=TILE_SIZE):
    """Two approach goals and two exit goals; not takeoff/landing commands."""
    sx, sy = size
    return np.array([[2., sy/2], [sx/2-1., sy/2], [sx/2+1., sy/2], [sx-.75, sy/2]])


def tile_function(difficulty, cfg):
    if (isinstance(difficulty, (bool, np.bool_)) or not isinstance(difficulty, (int, float, np.integer, np.floating))
            or not math.isfinite(float(difficulty)) or not 0 <= difficulty <= 1):
        raise ValueError('difficulty must be finite in [0,1]')
    if cfg.kind not in KINDS:
        raise ValueError(f'unknown family-F kind: {cfg.kind!r}')
    count = getattr(cfg, 'layout_rows', None)
    if count is None:
        count = LEVEL_COUNTS[cfg.kind]
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError('layout_rows must be a positive integer')
    level = getattr(cfg, 'jump_level', None)
    if level is None:
        level = min(LEVEL_COUNTS[cfg.kind]-1, int(float(difficulty)*count + 1e-9))
    else:
        warnings.warn('explicit jump_level overrides row difficulty', RuntimeWarning, stacklevel=2)
    tile = build_tile(cfg.kind, level, seed=cfg.seed, size=cfg.size,
                      gap_depth_m=cfg.gap_depth_m, floor_thickness_m=cfg.floor_thickness_m)
    return meshes_for(tile), tile.origin.copy()


def build_generator(*, kind, seed, num_cols=1, size=TILE_SIZE,
                    gap_depth_m=GAP_DEPTH_M, floor_thickness_m=FLOOR_THICKNESS_M):
    tile = build_tile(kind, 0, seed=seed, size=size, gap_depth_m=gap_depth_m,
                      floor_thickness_m=floor_thickness_m)
    if isinstance(num_cols, bool) or not isinstance(num_cols, int) or num_cols < 1:
        raise ValueError('num_cols must be a positive integer')
    from isaaclab.terrains import SubTerrainBaseCfg, TerrainGeneratorCfg
    from isaaclab.utils import configclass

    @configclass
    class JumpTerrainCfg(SubTerrainBaseCfg):
        function = tile_function
        kind: str = 'jump_up_low'
        seed: int = 42
        preset_id: str = PRESET_ID
        jump_level: int | None = None
        layout_rows: int | None = None
        gap_depth_m: float = GAP_DEPTH_M
        floor_thickness_m: float = FLOOR_THICKNESS_M

    sub = JumpTerrainCfg(kind=kind, seed=int(seed), size=tile.size, proportion=1.,
                         gap_depth_m=gap_depth_m, floor_thickness_m=floor_thickness_m)
    return TerrainGeneratorCfg(seed=int(seed), size=tile.size, num_rows=LEVEL_COUNTS[kind],
                               num_cols=num_cols, border_width=0., use_cache=False,
                               curriculum=True, difficulty_range=(0.,1.), sub_terrains={kind:sub})


def build_family_generator(*, seed, **dimensions):
    """Ten aligned storage rows, four kinds. Extra rows repeat the last physical level."""
    subs = {}
    for kind in KINDS:
        generator = build_generator(kind=kind, seed=seed, **dimensions)
        sub = generator.sub_terrains[kind]
        sub.layout_rows = LAYOUT_ROWS
        sub.proportion = 1./len(KINDS)
        subs[kind] = sub
    generator.num_rows, generator.num_cols = LAYOUT_ROWS, len(KINDS)
    generator.sub_terrains = subs
    return generator


def measurement_generator(kind, *, seed=42, **dimensions):
    generator = build_generator(kind=kind, seed=seed, **dimensions)
    return generator, generator.sub_terrains[kind]


def build_family_cpu(*, seed, size=TILE_SIZE, gap_depth_m=GAP_DEPTH_M):
    """Same callback geometry and centered grid convention as TerrainGenerator.

    No border, random height perturbation or extra obstacle. This supplies a
    saved-mesh input; it does not measure Isaac/PhysX mounting or GPU memory.
    """
    # Validate before importing optional trimesh.
    build_tile(KINDS[0], 0, seed=seed, size=size, gap_depth_m=gap_depth_m)
    import trimesh
    sx, sy = size
    meshes = []
    origins = np.empty((LAYOUT_ROWS, len(KINDS), 3), dtype=np.float64)
    for col, kind in enumerate(KINDS):
        for row in range(LAYOUT_ROWS):
            tile = build_tile(kind, min(row, LEVEL_COUNTS[kind]-1), seed=seed,
                              size=size, gap_depth_m=gap_depth_m)
            offset = np.array([(row-LAYOUT_ROWS/2)*sx, (col-len(KINDS)/2)*sy, 0.])
            for mesh in meshes_for(tile):
                mesh.apply_translation(offset)
                meshes.append(mesh)
            origins[row,col] = tile.origin + offset
    return dict(name='F', mesh=trimesh.util.concatenate(meshes), origins=origins,
                kinds=list(KINDS), size=tuple(size))
