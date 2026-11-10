"""EX-42 family D: box meshes for ledge, wall bypass and overhead clearance.

Task types follow HiPAN IV-A/Figs. 2, 5, 6; numeric ledge/clearance limits come
from our CURRICULUM-GATES E6b, not from HiPAN. The wall preset is a project
inference from Go2 dimensions and paper images, not a published HiPAN value.
No training registration, camera routing or policy modification happens here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import warnings

import numpy as np

KINDS = ('high_ledge', 'wall', 'crawl')
PRESET_ID = 'posture_go2_v1'
PRESET_SOURCE = 'project_inference_20261111'
LEVEL_COUNTS = {'high_ledge': 3, 'wall': 1, 'crawl': 10}
LEDGE_HEIGHTS_M = (.30, .45, .60)
CRAWL_CLEARANCE_M = (.30, .25)
WALL_HEIGHT_M = 1.20  # project choice: 3 x Go2 0.40 m standing height
CORRIDOR_WIDTH_M = .80  # project choice: Go2 0.31 m width + 0.245 m each side
# Carrier/layout choices, not paper terrain dimensions. All are caller-visible.
TILE_SIZE = (8., 8.)  # same carrier size as rough_go2_cfg
DEFAULT_THICKNESS_M = .10


@dataclass(frozen=True)
class BoxTile:
    kind: str
    level: int
    seed: int
    size: tuple[float, float]
    boxes: np.ndarray  # each row: x0,x1,y0,y1,z0,z1 in local metres
    origin: np.ndarray
    dimensions: dict[str, float]


def _positive(name, value):
    if (isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, float, np.integer, np.floating))
            or not math.isfinite(float(value)) or value <= 0):
        raise ValueError(f'{name} must be explicit, finite and positive')
    return float(value)


def _identity(kind, level, seed):
    if kind not in KINDS:
        raise ValueError(f'unknown family-D kind: {kind!r}')
    if (isinstance(level, (bool, np.bool_)) or not isinstance(level, (int, np.integer))
            or not 0 <= level < LEVEL_COUNTS[kind]):
        raise ValueError(f'{kind} level must be an integer in [0,{LEVEL_COUNTS[kind]-1}]')
    if (isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer))
            or not 0 <= seed < 2**32):
        raise ValueError('seed must be an explicit uint32 integer')


def build_tile(kind, level, *, seed, size=TILE_SIZE,
               wall_height_m=None, corridor_width_m=None,
               wall_thickness_m=DEFAULT_THICKNESS_M,
               floor_thickness_m=DEFAULT_THICKNESS_M,
               roof_thickness_m=DEFAULT_THICKNESS_M):
    """Pure CPU geometry, with no invented wall preset and no global RNG use.

    Ledge rises over the rear half of the carrier. Crawl places a floating slab
    over its middle half, keeping the space below empty. Wall leaves a +y bypass
    while blocking the centreline. Seed identifies this deterministic layout;
    changing seed alone does not create an independent geometry sample.
    """
    _identity(kind, level, seed)
    if not isinstance(size, (tuple, list)) or len(size) != 2:
        raise ValueError('size must contain two positive lengths')
    sx, sy = (_positive('size', v) for v in size)
    floor = _positive('floor_thickness_m', floor_thickness_m)
    boxes = [(0., sx, 0., sy, -floor, 0.)]
    dimensions = {'tile_x_m': sx, 'tile_y_m': sy, 'floor_thickness_m': floor}
    if kind == 'high_ledge':
        height = LEDGE_HEIGHTS_M[level]
        boxes.append((sx / 2, sx, 0., sy, 0., height))
        dimensions['ledge_height_m'] = height
    elif kind == 'crawl':
        # Ten explicit samples including both canonical endpoints. Interpolation
        # is our layout convention, not a published HiPAN curriculum.
        clearance = float(np.linspace(*CRAWL_CLEARANCE_M, LEVEL_COUNTS[kind])[level])
        roof = _positive('roof_thickness_m', roof_thickness_m)
        boxes.append((sx / 4, 3 * sx / 4, 0., sy, clearance, clearance + roof))
        dimensions.update(ceiling_clearance_m=clearance, roof_thickness_m=roof)
    else:
        height = _positive('wall_height_m', wall_height_m)
        width = _positive('corridor_width_m', corridor_width_m)
        thick = _positive('wall_thickness_m', wall_thickness_m)
        if width >= sy / 2:
            raise ValueError('corridor_width_m must be below half tile width to block the centreline')
        if thick >= sx / 2:
            raise ValueError('wall_thickness_m must be below half tile length to retain approach/exit')
        boxes.append((sx / 2 - thick / 2, sx / 2 + thick / 2, 0., sy - width, 0., height))
        dimensions.update(wall_height_m=height, corridor_width_m=width, wall_thickness_m=thick)
    return BoxTile(kind, int(level), int(seed), (sx, sy), np.asarray(boxes, dtype=float),
                   np.asarray((sx / 8, sy / 2, 0.)), dimensions)


def meshes_for(tile):
    """Independent closed box surfaces preserve the crawl void and underside."""
    import trimesh
    meshes = []
    for x0, x1, y0, y1, z0, z1 in tile.boxes:
        transform = trimesh.transformations.translation_matrix(
            ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        meshes.append(trimesh.creation.box((x1-x0, y1-y0, z1-z0), transform=transform))
    return meshes


def tile_function(difficulty, cfg):
    """Isaac subterrain callback -> (meshes, origin); no Q12 sensor gate."""
    if (isinstance(difficulty, (bool, np.bool_))
            or not isinstance(difficulty, (int, float, np.integer, np.floating))
            or not math.isfinite(float(difficulty)) or not 0 <= difficulty <= 1):
        raise ValueError('difficulty must be finite in [0,1]')
    if cfg.kind not in KINDS:
        raise ValueError(f'unknown family-D kind: {cfg.kind!r}')
    level = getattr(cfg, 'posture_level', None)
    if level is None:
        # Family assembly uses ten storage rows, with duplicate max-level tiles
        # after a kind's last physical level. This is not a new promotion rule.
        count = getattr(cfg, 'layout_rows', None)
        if count is None:
            count = LEVEL_COUNTS[cfg.kind]
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError('layout_rows must be a positive integer or None')
        level = min(LEVEL_COUNTS[cfg.kind]-1, int(float(difficulty)*count + 1e-9))
    else:
        warnings.warn('explicit posture_level overrides row difficulty', RuntimeWarning, stacklevel=2)
    tile = build_tile(cfg.kind, level, seed=cfg.seed, size=cfg.size,
                      wall_height_m=cfg.wall_height_m, corridor_width_m=cfg.corridor_width_m,
                      wall_thickness_m=cfg.wall_thickness_m, floor_thickness_m=cfg.floor_thickness_m,
                      roof_thickness_m=cfg.roof_thickness_m)
    return meshes_for(tile), tile.origin.copy()


def build_generator(*, kind, seed, num_cols=1, size=TILE_SIZE,
                    wall_height_m=WALL_HEIGHT_M, corridor_width_m=CORRIDOR_WIDTH_M,
                    wall_thickness_m=DEFAULT_THICKNESS_M,
                    floor_thickness_m=DEFAULT_THICKNESS_M,
                    roof_thickness_m=DEFAULT_THICKNESS_M):
    """Opt-in per-kind generator, preserving 3 ledge / 1 wall / 10 crawl levels.

    Terrain families with different row counts need an explicit layout assembler;
    this factory never expands the three approved ledge heights into new heights.
    """
    # Validate geometry before optional Isaac imports.
    tile = build_tile(kind, 0, seed=seed, size=size, wall_height_m=wall_height_m,
                      corridor_width_m=corridor_width_m, wall_thickness_m=wall_thickness_m,
                      floor_thickness_m=floor_thickness_m, roof_thickness_m=roof_thickness_m)
    if isinstance(num_cols, bool) or not isinstance(num_cols, int) or num_cols <= 0:
        raise ValueError('num_cols must be a positive integer')
    from isaaclab.terrains import SubTerrainBaseCfg, TerrainGeneratorCfg
    from isaaclab.utils import configclass

    @configclass
    class PostureTerrainCfg(SubTerrainBaseCfg):
        function = tile_function
        kind: str = 'crawl'
        seed: int = 42
        preset_id: str = PRESET_ID
        dimension_source: str = PRESET_SOURCE
        posture_level: int | None = None
        layout_rows: int | None = None
        wall_height_m: float | None = None
        corridor_width_m: float | None = None
        wall_thickness_m: float = DEFAULT_THICKNESS_M
        floor_thickness_m: float = DEFAULT_THICKNESS_M
        roof_thickness_m: float = DEFAULT_THICKNESS_M

    sub = PostureTerrainCfg(kind=kind, seed=int(seed), size=tile.size, proportion=1.,
                            wall_height_m=wall_height_m, corridor_width_m=corridor_width_m,
                            wall_thickness_m=wall_thickness_m, floor_thickness_m=floor_thickness_m,
                            roof_thickness_m=roof_thickness_m)
    return TerrainGeneratorCfg(seed=int(seed), size=tile.size, num_rows=LEVEL_COUNTS[kind],
                               num_cols=num_cols, border_width=0., use_cache=False, curriculum=True,
                               difficulty_range=(0., 1.), sub_terrains={kind: sub})


def measurement_generator(kind, *, seed=42, **dimensions):
    """PR #597-style pair using the documented posture_go2_v1 dimensions.

    measure_kind_with_kit replaces row/column count with one on its private copy.
    The result samples one level, not all levels; it cannot certify a full layout.
    """
    generator = build_generator(kind=kind, seed=seed, **dimensions)
    return generator, generator.sub_terrains[kind]


def build_family_generator(*, seed, wall_height_m=WALL_HEIGHT_M,
                           corridor_width_m=CORRIDOR_WIDTH_M, **dimensions):
    """Full D grid for ex42_mesh_build: 10 rows x 3 kinds, zero border.

    Defaults are our inferred preset, not HiPAN dimensions. Row r uses min(r,Lmax):
    ledge [0,1,2,2,2,2,2,2,2,2], wall [0]*10, crawl [0..9]. Thus ten aligned
    rows introduce no extra ledge height or wall curriculum. Callers must keep
    the kind's physical level cap (2/0/9), not claim ten independent difficulties.
    """
    # Validate mandatory values first, before importing Isaac.
    wall = build_generator(kind='wall', seed=seed, wall_height_m=wall_height_m,
                           corridor_width_m=corridor_width_m, **dimensions)
    subs = {}
    for kind in KINDS:
        g = wall if kind == 'wall' else build_generator(kind=kind, seed=seed, **dimensions)
        sub = g.sub_terrains[kind]
        sub.layout_rows = 10
        sub.proportion = 1. / len(KINDS)
        subs[kind] = sub
    wall.sub_terrains = subs
    wall.num_rows, wall.num_cols = 10, len(KINDS)
    return wall
