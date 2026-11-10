"""Independent numerical implementation of SPEC-JEPLO-PRESET.md.

Only the seven active execution-preset terrains are supported. No training cfg
imports this module. Geometry uses a local MT19937 stream and millimetre units.
The external GPL implementation is never imported by this production module.
"""
from dataclasses import dataclass
import math
import warnings

import numpy as np
from scipy.interpolate import RectBivariateSpline
from foothold_s2.terrains.sparse_terrains import level_of, seed_of


KINDS = ('gap', 'flat', 'box', 'discrete_obstacles', 'discrete_grid',
         'pyramid_stairs', 'inverted_pyramid_stairs')
WAYPOINT_KINDS = frozenset(('gap', 'box', 'discrete_obstacles'))
# Consumer contract: ex42_column_reset reads this by canonical kind name.
# Missing kinds keep the caller's existing default XY +/-0.5 and yaw +/-3.14.
RESET_RANGES = {kind: {axis: (0., 0.) for axis in ('x', 'y', 'yaw')}
                for kind in sorted(WAYPOINT_KINDS)}
H, V, SIZE, BORDER, INNER = 0.08, 0.005, 9.0, 7, 99


@dataclass(frozen=True)
class HeightTile:
    kind: str
    level: int
    seed: int
    height_units: np.ndarray
    difficulty: float

    @property
    def origin(self):
        """Reference wrapper's geometric centre, NOT a safe robot spawn."""
        return np.array([4.5, 4.5, self.height_units[56, 56] * V])


def _boxes(rng, d):
    lengths = rng.randint(10, 19, size=5)
    edges = np.r_[0, np.cumsum(lengths)] + max(0, (INNER - lengths.sum()) // 2)
    result = np.zeros((INNER, INNER), dtype=np.int16)
    centre = INNER // 2
    for i, multiplier in enumerate((1, 2, 3, 2, 1)):
        radius = rng.randint(10, 19)
        centre = int(np.clip(centre + rng.randint(-2, 3), 18, INNER - 18))
        result[edges[i]:edges[i + 1], centre-radius:centre+radius] = multiplier * round((0.1 + 0.4*d) / V)
    return result


def _pyramid(rng, d, inverted):
    width = int(rng.uniform(0.25, 0.35) / H)
    height = int((0.04 + d*(0.2 - 0.04)) * (-1 if inverted else 1) / V)
    x, y = np.indices((INNER, INNER))
    distance = np.minimum.reduce([x, y, INNER-1-x, INNER-1-y])
    rings = np.minimum(distance // width, (INNER - 25) // (2*width))
    return (rings * height).astype(np.int16)


def _discrete(rng, d, add_boxes):
    limit = round((0.1 if add_boxes else 0.2) * d / V)
    cells = rng.randint(0, limit + 1, size=(17, 17))
    result = np.repeat(np.repeat(cells, 6, axis=0), 6, axis=1)[:INNER, :INNER].astype(np.int16)
    spread = round(rng.uniform(0.8 if add_boxes else 0.6, 1.2) / H)
    if add_boxes:
        x, y = np.indices(result.shape)
        for row in (24, 49, 74):
            for sign in (-1, 1):
                cy = np.clip(49 + sign*spread, 9, 90)
                radius = rng.uniform(0.8, 1.25) / (2*H)
                angle = math.radians(rng.uniform(0, 90))
                dx, dy = x-row, y-cy
                square = ((np.abs(dx*np.cos(angle) + dy*np.sin(angle)) <= radius)
                          & (np.abs(-dx*np.sin(angle) + dy*np.cos(angle)) <= radius))
                result[square] = round(0.4*d/V)
        result[94:99, 43:55] = 0
    return result


def _gaps(rng, d):
    depth = -round(rng.uniform(1, 2) / V)
    radius = round(rng.uniform(0.6, 1.2) / H)
    lead_length = round(rng.uniform(1, 2) / H)
    opening = max(1, round((0.1 + 0.54*d) / H))
    platform = round(1/H)
    available = INNER - 2*platform
    count = max(n for n in range(1, 7) if lead_length+n*opening+(n-1)*10+5 <= available)
    extra = available - lead_length - count*opening - (count-1)*10 - 5
    lengths = [lead_length]
    for _ in range(count-1):
        allowance = min(2, extra)
        add = int(rng.randint(allowance+1)) if allowance else 0
        lengths.append(10+add)
        extra -= add
    lengths.append(available - count*opening - sum(lengths))
    centres = 49 + rng.randint(-5, 5, size=count+1)
    result = np.zeros((INNER, INNER), dtype=np.int16)
    # First carve one continuous pit, then restore disjoint safe corridors.
    result[platform:INNER-platform] = depth
    position = platform
    for length, cy in zip(lengths, centres):
        result[position:position+length, cy-radius:cy+radius] = 0
        position += length + opening
    return result


def _flat(rng):
    # Flat preset still samples unused hurdle waypoints before roughness.
    rng.uniform(0.4, 0.8)
    for _ in range(6):
        rng.randint(round(1.2/H), round(2.2/H))
        rng.randint(-5, 5)
    rng.randint(round(1.2/H), round(2.2/H))
    return np.zeros((INNER, INNER), dtype=np.int16)


def _roughen(field, rng, d, noise_range):
    lo, hi = noise_range
    size = INNER * H
    n = int(size / 0.075)
    values = np.arange(int(-lo/V), int((lo + (hi-lo)*d)/V) + 1)
    samples = rng.choice(values, size=(n, n))
    domain = np.linspace(0, size*H, n)
    query = np.linspace(0, size*H, INNER)
    noise = RectBivariateSpline(domain, domain, samples)(query, query)
    return field + np.rint(noise).astype(np.int16)


def build_heightfield(kind, level, seed, *, roughness=True):
    """Return the full 113x113 field, where one integer means 5 mm."""
    if kind not in KINDS or isinstance(level, bool) or not isinstance(level, (int, np.integer)) or not 0 <= level <= 9:
        raise ValueError('expected an execution-preset kind and integer level 0..9')
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or not 0 <= seed < 2**32:
        raise ValueError('seed must be an explicit uint32 integer')
    rng = np.random.RandomState(seed)
    d = level / 9
    noise = (0.02, 0.06)
    if kind == 'gap':
        field = _gaps(rng, d)
    elif kind == 'flat':
        field = _flat(rng)
    elif kind == 'box':
        field, noise = _boxes(rng, d), (0.01, 0.03)
    elif kind.startswith('discrete_'):
        field, noise = _discrete(rng, d, kind == 'discrete_obstacles'), (0.01, 0.03)
    else:
        field, noise = _pyramid(rng, d, kind.startswith('inverted_')), (0.01, 0.02)
    field[[0, -1], :] = 0
    field[:, [0, -1]] = 0
    if roughness:
        field = _roughen(field, rng, d, noise)
    full = np.pad(field, BORDER).astype(np.int16)
    return HeightTile(kind, int(level), int(seed), full, d)


def mesh_arrays(tile, slope_threshold=0.5):
    """Triangulate with vertical cliff snapping; extend the last border to 9 m."""
    heights = tile.height_units.astype(np.float64)
    n = heights.shape[0]
    axes = np.arange(n, dtype=np.float64)*H
    axes[-1] = SIZE
    xy = np.stack(np.meshgrid(axes, axes, indexing='ij'), axis=-1)
    if slope_threshold is not None:
        limit = slope_threshold*H/V
        shifts = np.zeros_like(xy)
        for axis in (0, 1):
            a = [slice(None), slice(None)]
            b = a.copy()
            a[axis], b[axis] = slice(None, -1), slice(1, None)
            rise = heights[tuple(b)]-heights[tuple(a)]
            shifts[tuple(a) + (axis,)] += rise > limit
            shifts[tuple(b) + (axis,)] -= rise < -limit
        diagonal = heights[1:, 1:]-heights[:-1, :-1]
        corner = np.zeros_like(heights)
        corner[:-1, :-1] += diagonal > limit
        corner[1:, 1:] -= diagonal < -limit
        xy += H*(shifts + (shifts == 0)*corner[..., None])
    vertices = np.concatenate([xy, (heights*V)[..., None]], axis=-1).reshape(-1, 3).astype(np.float32)
    base = (np.arange(n-1)[:, None]*n + np.arange(n-1)).ravel()
    triangles = np.stack([base, base+n+1, base+1, base, base+n, base+n+1], axis=-1).reshape(-1, 3).astype(np.uint32)
    return vertices, triangles


def validate_layout(size, num_rows, difficulty_range, seed):
    if tuple(size) != (SIZE, SIZE):
        raise ValueError('JEPLO execution preset requires a separate 9x9 m tile layout')
    if num_rows != 10 or tuple(difficulty_range) != (0, 1):
        raise ValueError('JEPLO adapter requires 10 rows and difficulty_range=(0,1)')
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or not 0 <= seed < 2**32:
        raise ValueError('generator seed must be an explicit uint32 integer, never None')


def adapter_seed(kind, difficulty, generator_seed):
    """Use the seed actually assigned by Isaac, plus unquantized tile identity."""
    return seed_of(f'jeplo/{generator_seed}/{kind}', difficulty) % 2**32


def reset_ranges_by_column(column_kinds):
    """Global C column -> reset pose ranges, consumed BEFORE the first reset.

    Input is an explicit mapping of actual global column numbers to KINDS.
    Never infer columns from env IDs or assume C starts at column 50. Columns
    outside C are omitted by the caller and retain its normal reset settings.
    Decision 2026-11-11 01:44: three waypoint kinds have no XY/yaw jitter;
    the other four retain the existing ranges. This does not alter joints,
    initial velocity, commands or the terrain curriculum.
    """
    result = {}
    for column, kind in column_kinds.items():
        if (isinstance(column, bool) or not isinstance(column, (int, np.integer))
                or column < 0 or kind not in KINDS):
            raise ValueError('expected nonnegative integer C column and canonical kind')
        result[int(column)] = dict(RESET_RANGES.get(kind, {
            'x': (-.5, .5), 'y': (-.5, .5), 'yaw': (-3.14, 3.14)}))
    return result


def spawn_origin(tile, *, vertices=None, faces=None):
    """Return a support-checked entry anchor without changing any geometry.

    The three waypoint kinds require reset_ranges_by_column's zero XY/yaw.
    Inspect the actual snapped triangles over a 0.70 x 0.50 m rectangle, not
    just the height under the body centre. Prefer the entry near (1,4.48),
    constrain it to x<=1.6 and within 0.4 m of the route centreline. Accept
    at most 0.15 m relief and only ground in [-0.10,0.15] m; pit floors and
    box tops above 0.15 m are not fallback starts. These bounds are our reset
    contract, not a published JEPLO success threshold. No candidate -> error.
    Direct-command kinds retain the reference origin and their reset ranges.
    """
    if tile.kind not in WAYPOINT_KINDS:
        return tile.origin.copy()
    if (vertices is None) != (faces is None):
        raise ValueError('vertices and faces must be supplied together')
    if vertices is None:
        vertices, faces = mesh_arrays(tile)
    triangles = np.asarray(vertices, dtype=np.float64)[faces]
    if not np.isfinite(triangles).all():
        raise ValueError('nonfinite spawn support mesh')
    lower, upper = triangles[:, :, :2].min(1), triangles[:, :, :2].max(1)
    candidates = np.array([(x*H, y*H) for x in range(5, 21) for y in range(51, 62)])
    distance = ((candidates - (1., 4.48))**2).sum(1)
    for centre in candidates[np.argsort(distance, kind='stable')]:
        intersects = (np.all(upper >= centre-(.35, .25), axis=1)
                      & np.all(lower <= centre+(.35, .25), axis=1))
        patch = triangles[intersects]
        if not len(patch):
            continue
        z = patch[:, :, 2]
        if z.min() < -.1-1e-7 or z.max() > .15+1e-7 or np.ptp(z) > .15+1e-7:
            continue
        # Interpolate the true surface at the anchor; cliffs can displace the
        # nominal heightfield sample XY by one cell during triangulation.
        a = patch[:, 0]
        u, v = patch[:, 1, :2]-a[:, :2], patch[:, 2, :2]-a[:, :2]
        det = u[:, 0]*v[:, 1]-u[:, 1]*v[:, 0]
        nonvertical = abs(det) > 1e-12
        a, u, v, det, patch = (item[nonvertical] for item in (a, u, v, det, patch))
        delta = centre-a[:, :2]
        s = (delta[:, 0]*v[:, 1]-delta[:, 1]*v[:, 0])/det
        t = (u[:, 0]*delta[:, 1]-u[:, 1]*delta[:, 0])/det
        hit = (s >= -1e-7) & (t >= -1e-7) & (s+t <= 1+1e-7)
        if hit.any():
            height = a[:, 2]+s*(patch[:, 1, 2]-a[:, 2])+t*(patch[:, 2, 2]-a[:, 2])
            return np.r_[centre, height[hit].max()]
    raise ValueError(f'no safe entry support: kind={tile.kind} level={tile.level} seed={tile.seed}')


def tile_function(difficulty, cfg):
    """Isaac SubTerrainBaseCfg interface. Standard row bins map to JEPLO L/9.

    A caller building an exact level uses cfg.jeplo_level. This function does
    not register itself in an environment or alter any current terrain mix.
    """
    validate_layout(cfg.size, getattr(cfg, 'jeplo_num_rows', 10),
                    getattr(cfg, 'jeplo_difficulty_range', (0, 1)), cfg.seed)
    if not np.isfinite(difficulty) or not 0 <= difficulty <= 1:
        raise ValueError('difficulty must be in [0,1]')
    level = getattr(cfg, 'jeplo_level', None)
    if level is None:
        level = level_of(difficulty)
    else:
        warnings.warn('explicit jeplo_level overrides row difficulty', RuntimeWarning, stacklevel=2)
    tile = build_heightfield(cfg.kind, level, adapter_seed(cfg.kind, difficulty, cfg.seed))
    vertices, faces = mesh_arrays(tile)
    origin = spawn_origin(tile, vertices=vertices, faces=faces)
    import trimesh
    return [trimesh.Trimesh(vertices=vertices, faces=faces, process=True)], origin


def jeplo_subterrains(seed=42):
    """Opt-in factory matching our existing sparse_subterrains API. Never auto-register."""
    validate_layout((SIZE, SIZE), 10, (0, 1), seed)
    from isaaclab.terrains import SubTerrainBaseCfg
    from isaaclab.utils import configclass

    @configclass
    class ExecutionPresetCfg(SubTerrainBaseCfg):
        function = tile_function
        kind: str = 'flat'
        seed: int = 42
        jeplo_level: int | None = None
        jeplo_num_rows: int = 10
        jeplo_difficulty_range: tuple[float, float] = (0.0, 1.0)

    return {'jeplo_'+kind: ExecutionPresetCfg(kind=kind, seed=seed, size=(SIZE, SIZE), proportion=1/7)
            for kind in KINDS}


def build_generator(*, seed, num_cols=30, num_rows=10, size=(SIZE, SIZE), difficulty_range=(0, 1)):
    """Dedicated opt-in layout, preventing the existing 8 m/seed=None default."""
    validate_layout(size, num_rows, difficulty_range, seed)
    from isaaclab.terrains import TerrainGeneratorCfg
    return TerrainGeneratorCfg(seed=seed, size=size, num_rows=num_rows, num_cols=num_cols,
                               horizontal_scale=H, vertical_scale=V, slope_threshold=0.5,
                               difficulty_range=difficulty_range, border_width=20.0,
                               use_cache=False, curriculum=True, sub_terrains=jeplo_subterrains(seed))


def measurement_generator(kind, *, seed=42):
    """Return (generator cfg, subterrain cfg) for EX-42 measure family C.

    Accept canonical KINDS names, without the training factory's jeplo_ prefix.
    The returned layout retains the 9 m tile and ten level bins. The caller
    measure_kind_with_kit isolates one tile by copying this cfg and replacing
    num_rows/num_cols with 1. That is one sampled level, not a ten-level audit.
    No environment, curriculum, dimensions declaration or receipt is modified.
    """
    if kind not in KINDS:
        raise ValueError(f'unknown JEPLO measurement kind: {kind!r}')
    generator = build_generator(seed=seed, num_cols=1)
    subterrain = generator.sub_terrains['jeplo_' + kind]
    subterrain.proportion = 1.0
    generator.sub_terrains = {kind: subterrain}
    return generator, subterrain
