"""SOL-23f START-TopDown 학습 지형. 8x4 m 원문 시험지와 별도 작업가정 비율."""

from __future__ import annotations

import hashlib

import numpy as np

from foothold_s2.eval import start_sheet as sheet
from foothold_s2.terrains import sparse_terrains


SIZE = sheet.SIZE
RESOLUTION = 0.025
NUM_ROWS = 10
NUM_COLS = 30
WORLD_CENTER_SHIFT = np.array([NUM_ROWS * SIZE[0] / 2, NUM_COLS * SIZE[1] / 2])
# 작업가정: gap 10% 고정, 비-gap 90%. 쉬운 low:flat=1:1, 어려운 세 종류=1:1:1.
# 최초 배정의 어려운 열은 환경 생성 뒤 쉬운 열로 옮긴다. 이후 p_advance가 재배정한다.
PROPORTIONS = {
    "stepping_stones_low": 0.15,
    "flat": 0.15,
    "stepping_stones_high": 0.20,
    "balance_beams": 0.20,
    "stepping_beams": 0.20,
    "gaps": 0.10,
}
KIND_MAP = {
    "stepping_stones_low": ("stepping_stones", 0.0),
    "stepping_stones_high": ("stepping_stones", None),
    "balance_beams": ("balance_beams", None),
    "stepping_beams": ("stepping_beams", None),
    "gaps": ("gaps", None),
}
SIDE_TABLE = None


def _seed(kind: str, difficulty: float) -> int:
    return int.from_bytes(hashlib.sha256(f"{kind}|{difficulty:.12f}".encode()).digest()[:8], "little")


def _height_grid(boxes: np.ndarray, resolution: float = RESOLUTION) -> np.ndarray:
    grid = np.full((int(SIZE[0] / resolution), int(SIZE[1] / resolution)), -10.0)
    for x0, x1, y0, y1, _z0, top in boxes:
        i0, i1 = int(round(x0 / resolution)), int(round(x1 / resolution))
        j0, j1 = int(round(y0 / resolution)), int(round(y1 / resolution))
        grid[i0:i1, j0:j1] = np.maximum(grid[i0:i1, j0:j1], top)
    return grid


def make_tile(kind: str, difficulty: float):
    if kind not in PROPORTIONS:
        raise ValueError(f"unknown terrain: {kind}")
    level = min(NUM_ROWS - 1, int(NUM_ROWS * float(difficulty) + 1e-9))
    if kind == "flat":
        boxes = np.array([[0.0, 8.0, 0.0, 4.0, -0.2, 0.0]])
    else:
        source, randomness = KIND_MAP[kind]
        boxes = sheet.generate(source, level, np.random.default_rng(_seed(kind, difficulty)), randomness).boxes
    inner, outer = sparse_terrains.edge_masks(_height_grid(boxes), drop=0.2)
    # START Eq. 6 uses nested masks: <=2.5 cm receives both 1 and 0.5.
    outer = outer | inner
    flags = np.array([[x, 2.0] for x in (2.0, 3.5, 5.0, 6.5)], dtype=float)
    return sparse_terrains.TileData(
        kind=kind, group="gap" if kind == "gaps" else "sparse", level=level,
        boxes=boxes, origin=np.array([sheet.SPAWN_XY[0], sheet.SPAWN_XY[1], 0.0]),
        flags=flags, inner=inner, outer=outer,
    )


class TopDownSideTable(sparse_terrains.SideTable):
    def bind_all(self, names_by_col, num_rows, size=SIZE):
        # The inherited binder skips names outside its older KINDS table.
        # TopDown includes flat and two distinct stepping-stone columns.
        queue = {}
        for kind, difficulty in self.calls:
            queue.setdefault(kind, []).append(difficulty)
        consumed = {kind: 0 for kind in queue}
        for col, kind in enumerate(names_by_col):
            for row in range(num_rows):
                i = consumed.get(kind, 0)
                seq = queue.get(kind, [])
                if i >= len(seq):
                    raise RuntimeError(f"missing TopDown tile {kind} row={row} col={col}")
                difficulty = seq[i]
                consumed[kind] = i + 1
                if min(NUM_ROWS - 1, int(NUM_ROWS * difficulty + 1e-9)) != row:
                    raise RuntimeError(f"TopDown tile order mismatch {kind} row={row} difficulty={difficulty}")
                self.bind(row, col, kind, difficulty, size=size)

    def bind(self, row, col, kind, difficulty, size=SIZE):
        if self.key(kind, difficulty) not in self.by_key:
            raise RuntimeError(f"terrain side table missing generated tile: {kind} row={row} col={col}")
        super().bind(row, col, kind, difficulty, size=size)
        # TerrainGenerator centers the concatenated mesh and terrain_origins.
        # The inherited side table uses the pre-centering row/column coordinates.
        cell = self.by_cell[(row, col)]
        cell["flags_world"] -= WORLD_CENTER_SHIFT
        cell["origin_world"] -= WORLD_CENTER_SHIFT


SIDE_TABLE = TopDownSideTable()


def _tile_function(difficulty, cfg):
    import trimesh

    tile = make_tile(cfg.kind, difficulty)
    SIDE_TABLE.record(cfg.kind, difficulty, tile)
    meshes = []
    for x0, x1, y0, y1, z0, z1 in tile.boxes:
        meshes.append(trimesh.creation.box(
            (x1 - x0, y1 - y0, z1 - z0),
            trimesh.transformations.translation_matrix(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)),
        ))
    return meshes, tile.origin.copy()


def generator_cfg():
    """Kit 안에서만 호출하는 10행×30열 지형 생성기."""
    import isaaclab.terrains as terrain_gen
    from isaaclab.terrains.terrain_generator_cfg import TerrainGeneratorCfg
    from isaaclab.utils import configclass

    @configclass
    class TopDownTileCfg(terrain_gen.SubTerrainBaseCfg):
        function = _tile_function
        kind: str = "flat"

    subs = {name: TopDownTileCfg(proportion=p, size=SIZE, kind=name) for name, p in PROPORTIONS.items()}
    return TerrainGeneratorCfg(
        size=SIZE, border_width=20.0, num_rows=NUM_ROWS, num_cols=NUM_COLS,
        horizontal_scale=0.1, vertical_scale=0.005, slope_threshold=0.75,
        use_cache=False, curriculum=True, sub_terrains=subs,
    )
