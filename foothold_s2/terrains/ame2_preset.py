"""Independent Go2-sized AME-2 terrain family B, opt-in for mesh measurement.

This is our geometry, not the GPL ame2_minimal implementation.  The ranges
come from CURRICULUM-GATES v0.16 E3/E4 and are not an author reproduction.
Isaac imports stay inside the adapter so dimensions and meshes are CPU-testable.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

import numpy as np


PRESET = "ame2_go2_mix_v1"
KINDS = ("stair_up", "stair_down", "rough", "boxes", "climb_up",
         "climb_down", "gap", "pallets", "stones", "beam", "consecutive",
         "obstacles")
PROPORTIONS = {kind: (.20 if kind == "climb_up" else .30 if kind == "stones" else .05)
               for kind in KINDS}
SIZE = 12.0
HORIZONTAL_SCALE = 0.1
VERTICAL_SCALE = 0.005


@dataclass(frozen=True)
class Box:
    # Bottom and top surfaces in tile coordinates. A missing box means a real hole.
    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class Tile:
    kind: str
    level: int
    seed: int
    boxes: tuple[Box, ...]
    dimensions: dict[str, float]
    floor_mode: str
    floor_height_m: float | None
    rough_height_m: np.ndarray | None = None

    @property
    def origin(self):
        if self.rough_height_m is not None:
            return np.array([2., 6., self.rough_height_m[20, 60]], dtype=float)
        supports = [box for box in self.boxes
                    if self.floor_height_m is None or box.z1 > self.floor_height_m + .2]
        if not supports:
            raise ValueError("AME-2 tile has no spawn support")
        def distance(box):
            dx = max(box.x0 - 2., 0., 2. - box.x1)
            dy = max(box.y0 - 6., 0., 6. - box.y1)
            return dx * dx + dy * dy
        nearest = min(supports, key=distance)
        x = min(max(2., nearest.x0 + .01), nearest.x1 - .01)
        y = min(max(6., nearest.y0 + .01), nearest.y1 - .01)
        return np.array([x, y, nearest.z1], dtype=float)


def _lerp(a, b, level):
    return float(a + (b - a) * level / 9)


def dimensions(kind: str, level: int) -> dict[str, float]:
    """Go2 mix v1 canonical L0..9 endpoint dimensions, in metres unless named."""
    if kind not in KINDS or type(level) is not int or not 0 <= level <= 9:
        raise ValueError("AME-2 Go2 kind and integer level 0..9 required")
    table = {
        "stair_up": {"step_height_m": (.05, .27), "tread_m": (.30, .30)},
        "stair_down": {"step_height_m": (.05, .27), "tread_m": (.30, .30)},
        # SPEC's 0..0.16 m is the full U[-a,+a] span, so a_max = 0.08 m.
        "rough": {"noise_amplitude_m": (0, .08), "slope_deg": (0, 20)},
        "boxes": {"box_height_m": (.05, .30)},
        "climb_up": {"ledge_height_m": (.10, .53)},
        "climb_down": {"ledge_height_m": (.20, .60)},
        "gap": {"gap_m": (.18, .70)},
        "pallets": {"beam_width_m": (.40, .16), "gap_m": (.08, .35),
                    "height_difference_m": (0, .30)},
        "stones": {"stone_side_m": (.71, .41), "gap_m": (.08, .12)},
        "beam": {"beam_width_m": (.90, .18), "height_difference_m": (0, .20),
                 "max_rpy_rad": (.10, .10)},
        "consecutive": {"first_ring_height_m": (.05, .30),
                        "second_ring_height_m": (.05, .30)},
        "obstacles": {"density_per_m2": (0, .50),
                      "obstacle_height_min_m": (.20, .20),
                      "obstacle_height_max_m": (2.0, 2.0)},
    }
    return {key: _lerp(*limits, level) for key, limits in table[kind].items()}


def _box(x0, x1, y0, y1, z1, *, z0=-.2, roll=0., pitch=0., yaw=0.):
    if not (0 <= x0 < x1 <= SIZE and 0 <= y0 < y1 <= SIZE and z0 < z1):
        raise ValueError("AME-2 box escapes tile or has no volume")
    return Box(x0, x1, y0, y1, z0, z1, roll, pitch, yaw)


def _sparse_floor(seed, rng):
    # Appendix A: half physical and half virtual. The virtual half has no collider.
    height = float(rng.uniform(-1.5, -.35))
    physical = seed % 2 == 0
    return ("physical" if physical else "virtual", height,
            [_box(0, SIZE, 0, SIZE, height, z0=height - .1)] if physical else [])


def build_tile(kind: str, level: int, seed: int) -> Tile:
    d = dimensions(kind, level)
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("AME-2 tile seed must be an explicit uint32")
    rng = np.random.default_rng(seed)
    boxes: list[Box] = []
    floor_mode, floor_height = "none", None
    rough = None
    if kind in {"gap", "pallets", "stones", "beam"}:
        floor_mode, floor_height, boxes = _sparse_floor(seed, rng)

    if kind in ("stair_up", "stair_down"):
        step, tread = d["step_height_m"], d["tread_m"]
        for i in range(int(SIZE / tread)):
            x0, x1 = i * tread, min(SIZE, (i + 1) * tread)
            h = (min(i, 6) if kind == "stair_up" else -min(i, 6)) * step
            boxes.append(_box(x0, x1, 1., 11., h, z0=min(-.2, h - .2)))
    elif kind == "rough":
        n = int(SIZE / HORIZONTAL_SCALE) + 1
        axis = np.linspace(0, SIZE, n)
        coarse_axis = np.linspace(0, SIZE, 5)
        anchors = rng.uniform(-d["noise_amplitude_m"], d["noise_amplitude_m"], (5, 5))
        x_interp = np.stack([np.interp(axis, coarse_axis, anchors[:, j]) for j in range(5)], axis=1)
        noise = np.stack([np.interp(axis, coarse_axis, row) for row in x_interp], axis=0)
        # The 3 m undulation uses 82% of the tan(slope) derivative budget.
        # The remaining 18% bounds the 3 m-spaced U[-0.08,+0.08] anchors.
        period = 3.
        slope = .82 * math.tan(math.radians(d["slope_deg"]))
        wave = slope * period / (2 * math.pi) * np.sin(2 * math.pi * axis / period)
        rough = noise + wave[:, None]
    elif kind == "boxes":
        boxes.append(_box(0, SIZE, 0, SIZE, 0))
        for _ in range(20):
            side = float(rng.uniform(.8, 2.0))
            x, y = rng.uniform(.3, SIZE - side - .3, 2)
            boxes.append(_box(float(x), float(x + side), float(y), float(y + side),
                              float(rng.uniform(.01, d["box_height_m"]))))
    elif kind == "climb_up":
        h = d["ledge_height_m"]
        boxes.extend((_box(0, 5.5, 0, SIZE, 0), _box(5.5, SIZE, 0, SIZE, h)))
    elif kind == "climb_down":
        h = d["ledge_height_m"]
        boxes.extend((_box(0, 5.5, 0, SIZE, h), _box(5.5, SIZE, 0, SIZE, 0)))
    elif kind == "consecutive":
        a, b = d["first_ring_height_m"], d["second_ring_height_m"]
        edges = (0., 2.4, 4.8, 7.2, 9.6, 12.)
        heights = (0., a, a + b, a, 0.)
        for i, h in enumerate(heights):
            boxes.append(_box(edges[i], edges[i + 1], 0, SIZE, h))
    elif kind == "gap":
        width = d["gap_m"]
        # Split the edges into lanes to give the paper's bounded irregularity.
        for lane in range(4):
            shift = float(rng.uniform(-.1, .1) * width)
            x0 = 6. - width / 2 + shift
            x1 = x0 + width
            dz = float(rng.uniform(-.3, .3) * width)
            y0, y1 = lane * 3., (lane + 1) * 3.
            boxes.extend((_box(0, x0, y0, y1, 0),
                          _box(x1, SIZE, y0, y1, dz, z0=min(-.2, dz - .2))))
    elif kind == "pallets":
        width, gap = d["beam_width_m"], d["gap_m"]
        x = 1.
        while x + width <= SIZE - 1.:
            delta = d["height_difference_m"]
            z = float(rng.uniform(-delta, delta)) if delta else 0.
            boxes.append(_box(x, x + width, 1., 11., z, z0=min(-.2, z - .2),
                              yaw=float(rng.uniform(-.1, .1))))
            x += width + gap
    elif kind == "stones":
        side, gap = d["stone_side_m"], d["gap_m"]
        pitch = side + gap
        for x in np.arange(0, SIZE - side, pitch):
            for y in np.arange(0, SIZE - side, pitch):
                dx, dy = rng.uniform(-gap / 4, gap / 4, 2)
                x0 = float(np.clip(x + dx, 0, SIZE - side))
                y0 = float(np.clip(y + dy, 0, SIZE - side))
                boxes.append(_box(x0, x0 + side, y0, y0 + side, float(rng.uniform(-.06, .06))))
    elif kind == "beam":
        width, delta, angle = d["beam_width_m"], d["height_difference_m"], d["max_rpy_rad"]
        boxes.extend((_box(0, 2., 0, SIZE, 0),
                      _box(2., 10., 6 - width / 2, 6 + width / 2, 0,
                           roll=float(rng.uniform(-angle, angle)),
                           pitch=float(rng.uniform(-angle, angle)),
                           yaw=float(rng.uniform(-angle, angle))),
                      _box(10., SIZE, 0, SIZE, float(rng.uniform(-delta, delta)),
                           z0=-.2 - delta)))
    elif kind == "obstacles":
        count = int(round(d["density_per_m2"] * SIZE * SIZE))
        selected = set(map(int, rng.choice(144, size=count, replace=False)))
        for ix in range(12):
            for iy in range(12):
                x, y = float(ix), float(iy)
                if 12 * ix + iy not in selected:
                    boxes.append(_box(x, x + 1, y, y + 1, 0))
                    continue
                side = float(rng.uniform(.3, .8))
                margin = (1. - side) / 2
                height = float(rng.uniform(d["obstacle_height_min_m"],
                                           d["obstacle_height_max_m"]))
                if rng.integers(2):
                    boxes.extend((_box(x, x + 1, y, y + 1, 0),
                                  _box(x + margin, x + 1 - margin,
                                       y + margin, y + 1 - margin, height)))
                else:
                    # Remove the centre of the cell and put a lower collision
                    # floor inside it; the four surrounding strips form walls.
                    boxes.extend((_box(x, x + margin, y, y + 1, 0),
                                  _box(x + 1 - margin, x + 1, y, y + 1, 0),
                                  _box(x + margin, x + 1 - margin, y, y + margin, 0),
                                  _box(x + margin, x + 1 - margin,
                                       y + 1 - margin, y + 1, 0),
                                  _box(x + margin, x + 1 - margin, y + margin,
                                       y + 1 - margin, -height, z0=-height - .2)))
    else:
        raise AssertionError(kind)
    return Tile(kind, level, seed, tuple(boxes), d, floor_mode, floor_height, rough)


def validate_tile(tile: Tile):
    """Reject silent filled gaps and mismatched physical floor declarations."""
    if tile.kind == "gap":
        if any(box.x0 <= 6 <= box.x1 and box.y0 <= 6 <= box.y1 and box.z1 > -.3
               for box in tile.boxes):
            raise ValueError("AME-2 gap centre was bridged by a collision surface")
    if tile.floor_mode == "physical" and not any(
            box.x0 == 0 and box.x1 == SIZE and box.y0 == 0 and box.y1 == SIZE
            and box.z1 == tile.floor_height_m for box in tile.boxes):
        raise ValueError("AME-2 physical sparse floor missing")


def mesh_arrays(tile: Tile):
    """CPU mesh arrays, with actual holes where no support box exists."""
    import trimesh

    meshes = []
    for box in tile.boxes:
        extents = (box.x1 - box.x0, box.y1 - box.y0, box.z1 - box.z0)
        centre = ((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2, (box.z0 + box.z1) / 2)
        transform = trimesh.transformations.euler_matrix(box.roll, box.pitch, box.yaw)
        transform[:3, 3] = centre
        meshes.append(trimesh.creation.box(extents=extents, transform=transform))
    if tile.rough_height_m is not None:
        z = tile.rough_height_m
        n = z.shape[0]
        x, y = np.meshgrid(np.linspace(0, SIZE, n), np.linspace(0, SIZE, n), indexing="ij")
        vertices = np.stack((x, y, z), axis=-1).reshape(-1, 3)
        starts = (np.arange(n - 1)[:, None] * n + np.arange(n - 1)).ravel()
        faces = np.stack((starts, starts + n, starts + 1,
                          starts + 1, starts + n, starts + n + 1), axis=-1).reshape(-1, 3)
        meshes.append(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))
    if not meshes:
        raise ValueError("AME-2 tile generated no collidable mesh")
    return meshes


def _tile_seed(kind, difficulty, seed):
    payload = f"{PRESET}/{seed}/{kind}/{difficulty:.12f}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def tile_function(difficulty, cfg):
    if tuple(cfg.size) != (SIZE, SIZE) or not 0 <= difficulty <= 1 or not math.isfinite(difficulty):
        raise ValueError("AME-2 measurement tile must be 12x12 m with difficulty 0..1")
    level = cfg.ame2_level if cfg.ame2_level is not None else min(9, int(difficulty * 10))
    tile = build_tile(cfg.kind, level, _tile_seed(cfg.kind, difficulty, cfg.seed))
    validate_tile(tile)
    import trimesh
    # One mesh per tile keeps the 60-column layout from creating hundreds of
    # separate USD mesh prims for every stone tile.
    return [trimesh.util.concatenate(mesh_arrays(tile))], tile.origin


def _subterrains(seed, proportions):
    from isaaclab.terrains import SubTerrainBaseCfg
    from isaaclab.utils import configclass

    @configclass
    class Ame2Go2TileCfg(SubTerrainBaseCfg):
        function = tile_function
        kind: str = "rough"
        seed: int = 42
        ame2_level: int | None = None

    return {kind: Ame2Go2TileCfg(kind=kind, seed=seed, size=(SIZE, SIZE),
                                proportion=proportions[kind]) for kind in proportions}


def build_generator(*, seed: int = 42, num_cols: int = 60, proportions=None):
    """Opt-in 12x12 m, 10-row Isaac cfg; no live training cfg imports it."""
    if type(seed) is not int or not 0 <= seed < 2**32 or type(num_cols) is not int or num_cols < 1:
        raise ValueError("AME-2 generator seed or column count invalid")
    proportions = dict(PROPORTIONS if proportions is None else proportions)
    if not proportions or not set(proportions).issubset(KINDS) or any(
            type(value) not in (float, int) or not math.isfinite(value) or value <= 0
            for value in proportions.values()) or not math.isclose(sum(proportions.values()), 1., abs_tol=1e-9):
        raise ValueError("AME-2 generator proportions must be positive and sum to one")
    from isaaclab.terrains import TerrainGeneratorCfg
    generator = TerrainGeneratorCfg(seed=seed, size=(SIZE, SIZE), num_rows=10, num_cols=num_cols,
                                    horizontal_scale=HORIZONTAL_SCALE, vertical_scale=VERTICAL_SCALE,
                                    border_width=10.0, slope_threshold=0.75, curriculum=True,
                                    difficulty_range=(0., 1.), use_cache=False,
                                    sub_terrains=_subterrains(seed, proportions))
    return generator


def measurement_generator(kind: str, *, seed: int = 42):
    """One-column, ten-level (TerrainGeneratorCfg, SubTerrainCfg) Kit contract."""
    if kind not in KINDS:
        raise ValueError("AME-2 measurement kind invalid")
    generator = build_generator(seed=seed, num_cols=1, proportions={kind: 1.})
    return generator, generator.sub_terrains[kind]
