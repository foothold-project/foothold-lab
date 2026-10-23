"""듬성한 발판 지형 생성기 (15 §4 · §8 · §8.1, 16 §2). 순수 계산(numpy)과 Isaac 얇은 껍질로 나뉜다.

START 시험지(`eval/start_sheet.py`, 8 x 4 m)의 치수를 학습 칸 8 x 8 m 의 가운데 띠(y 2~6)에 놓는다 (**가정**: 8 x 8 는 15 §2).
띠 밖은 구덩이 바닥 높이로 이어 붙여 «옆으로 돌아가기» 가 없게 하고, 출발 · 도착 단은 칸 폭 전체다.

계약 (15 §8.1):
  - Isaac 생성기 함수는 `(meshes, origin)` 두 값만 돌려준다. 깃발 · 가장자리 마스크 · 종류는 side table(`SideTable`) 에 둔다.
  - 모든 좌표는 «칸 좌표»(0..8) 로 저장하고, 월드 좌표는 Isaac 과 같은 변환 `tile_xy + (row * size_x, col * size_y)` 로 옮긴다
    (Isaac: 칸 중심으로 -size/2 옮긴 뒤 (row+0.5, col+0.5) * size 만큼 이동 = 합치면 위 식).
  - 칸은 (종류, 난이도) 만으로 결정된다 (시드를 둘의 해시에서 뽑는다). 캐시가 mesh · origin 만 복원해도 side table 을 같은 값으로 다시 만들 수 있다.
난이도 → 레벨 `floor(10 x 난이도)` 는 **가정**. 징검돌 무작위 정도 r: 저무작위 열 0 고정, 고무작위 열 L / 9(레벨 9 = START 최대 돌 ±0.5 · 열 ±0.45 x 틈, 선행 0.0 → 0.48 꼴, 20s lead 채택 · 가정).
"""

import hashlib
from dataclasses import dataclass

import numpy as np

from foothold_s2.eval import start_sheet as ss

TILE = (8.0, 8.0)
STRIP = (2.0, 6.0)                 # 시험지가 놓이는 y 범위
SPAWN_XY = (0.5, 4.0)
FLAG_COUNT = 4
FLAG_X = tuple(SPAWN_XY[0] + (ss.GOAL_X - SPAWN_XY[0]) * (k + 1) / FLAG_COUNT for k in range(FLAG_COUNT))
MASK_RES = 0.025                   # 2.5 cm 띠를 한 칸으로 (16 §2). 칸 하나가 320 x 320
EDGE_DROP_M = 0.2                  # 모서리 문턱 (16 §2 가정)
KINDS = {                          # 학습 이름 -> (START 종류, 징검돌 무작위 정도 r(None = 레벨 비례 L/9), 집단 태그)
    "stepping_stones_low": ("stepping_stones", 0.0, "sparse"),
    "stepping_stones_high": ("stepping_stones", None, "sparse"),   # r = L / 9 (레벨 9 가 START 최대값, fable 20s · lead)
    "balance_beams": ("balance_beams", None, "sparse"),
    "stepping_beams": ("stepping_beams", None, "sparse"),
    "gaps": ("gaps", None, "gap"),
    "flat": (None, None, "sparse"),
}


@dataclass
class TileData:
    kind: str
    group: str
    level: int
    boxes: np.ndarray            # (N, 6) 칸 좌표 x0 x1 y0 y1 z0 z1 (윗면 z1)
    origin: np.ndarray           # (3,) 칸 좌표
    flags: np.ndarray            # (K, 2) 칸 좌표
    inner: np.ndarray            # (H, W) bool, 2.5 cm 띠
    outer: np.ndarray            # (H, W) bool, 5 cm 띠 (안쪽 띠와 겹치는 곳 뺌)


def level_of(difficulty):
    return min(ss.LEVELS - 1, int(difficulty * ss.LEVELS + 1.0e-9))


def seed_of(kind, difficulty):
    h = hashlib.sha256(("%s|%.12f" % (kind, difficulty)).encode()).digest()

    return int.from_bytes(h[:8], "little")


def _frame(depth, platform_z=0.0):
    floor_top = platform_z - depth
    bottom = floor_top - ss.FLOOR_THICKNESS
    x0, x1 = ss.ZONE_X

    return [(0.0, x0, 0.0, TILE[1], bottom, platform_z), (x1, TILE[0], 0.0, TILE[1], bottom, platform_z),
            (x0, x1, 0.0, TILE[1], bottom, floor_top)]


def height_grid(boxes, res=MASK_RES, floor=-10.0):
    """칸 윗면 높이 격자 (H, W) = (x 칸 수, y 칸 수). 겹치면 높은 쪽."""
    nx, ny = int(round(TILE[0] / res)), int(round(TILE[1] / res))
    grid = np.full((nx, ny), floor)

    for x0, x1, y0, y1, _, z1 in boxes:
        i0, i1 = int(round(x0 / res)), int(round(x1 / res))
        j0, j1 = int(round(y0 / res)), int(round(y1 / res))
        grid[i0:i1, j0:j1] = np.maximum(grid[i0:i1, j0:j1], z1)

    return grid


def _dilate(mask, n):
    out = mask.copy()

    for _ in range(n):
        p = np.pad(out, 1)
        out = out | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]

    return out


def edge_masks(grid, drop=EDGE_DROP_M):
    """낙하 높이 `drop` 이상인 세로 모서리 -> (안쪽 2.5 cm 띠, 바깥 5 cm 띠). 경계 양쪽 한 칸(2.5 cm)이 안쪽 띠, 그 바깥 한 칸이 바깥 띠."""
    edge = np.zeros(grid.shape, dtype=bool)

    for axis in (0, 1):
        d = np.abs(np.diff(grid, axis=axis))
        hit = d >= drop

        if axis == 0:
            edge[:-1, :] |= hit
            edge[1:, :] |= hit
        else:
            edge[:, :-1] |= hit
            edge[:, 1:] |= hit

    inner = edge                                  # 경계에서 2.5 cm 안 (양쪽 한 칸)
    outer = _dilate(edge, 1) & ~inner             # 2.5~5 cm

    return inner, outer


def _snap_to_support(boxes, target_x, y0, platform_floor_top):
    """깃발을 발판 윗면 위로 옮긴다: 목표 (x, 4.0) 에서 가까운 순으로 y · x 를 훑어 구덩이 바닥이 아닌 윗면을 찾는다."""
    res = 0.05
    grid = height_grid(boxes, res=res)
    best = None

    for dx in np.arange(0.0, 0.6, res):
        for sx in (1.0, -1.0):
            for dy in np.arange(0.0, 0.4, res):
                for sy in (1.0, -1.0):
                    x, y = target_x + sx * dx, y0 + sy * dy
                    i, j = int(x / res), int(y / res)

                    if 0 <= i < grid.shape[0] and 0 <= j < grid.shape[1] and grid[i, j] > platform_floor_top + 0.1:
                        d = dx * dx + dy * dy

                        if best is None or d < best[0]:
                            best = (d, x, y)

        if best is not None:
            break

    return (best[1], best[2]) if best else (target_x, y0)


def build_tile(kind, difficulty):
    """(종류, 난이도) -> TileData. 결정적이다."""
    start_kind, randomness, group = KINDS[kind]
    level = level_of(difficulty)
    rng = np.random.default_rng(seed_of(kind, difficulty))

    if start_kind is None:
        boxes = [(0.0, TILE[0], 0.0, TILE[1], -ss.FLOOR_THICKNESS, 0.0)]
        depth = 0.0
    else:
        geom = ss.generate(start_kind, level, rng, randomness=randomness) if randomness is not None \
            else ss.generate(start_kind, level, rng)
        depth = geom.depth
        shifted = [(x0, x1, y0 + STRIP[0], y1 + STRIP[0], z0, z1) for x0, x1, y0, y1, z0, z1 in geom.boxes[3:]]
        boxes = _frame(depth) + shifted

    boxes = np.asarray(boxes, dtype=float)
    grid = height_grid(boxes)
    inner, outer = edge_masks(grid)
    mid_y = TILE[1] / 2.0
    flags = np.array([_snap_to_support(boxes, fx, mid_y, -depth) if start_kind else (fx, mid_y) for fx in FLAG_X])

    return TileData(kind, group, level, boxes, np.array([SPAWN_XY[0], SPAWN_XY[1], 0.0]), flags, inner, outer)


def tile_to_world(xy, row, col, size=TILE):
    """칸 좌표 -> 월드 좌표 (Isaac `terrain_generator.py` 335 · 383~388 행과 같은 변환)."""
    xy = np.asarray(xy, dtype=float)

    return xy - 0.5 * np.asarray(size) + np.array([(row + 0.5) * size[0], (col + 0.5) * size[1]])


# ---------------------------------------------------------------- side table


class SideTable:
    """(row, col) -> 깃발 (월드) · 마스크 · 집단 태그. 생성기 함수가 호출될 때 (종류, 난이도) 키로 적고, `bind` 가 (row, col) 로 옮긴다."""

    def __init__(self):
        self.by_key = {}
        self.by_cell = {}
        self.calls = []        # 생성기 함수가 불린 순서대로 (종류, 난이도)

    @staticmethod
    def key(kind, difficulty):
        return (kind, round(float(difficulty), 12))

    def record(self, kind, difficulty, tile):
        self.by_key[self.key(kind, difficulty)] = tile
        self.calls.append((kind, float(difficulty)))

    def bind_all(self, names_by_col, num_rows, size=TILE):
        """Isaac 커리큘럼 생성은 열 우선 · 줄 순서로 칸을 만든다 (`terrain_generator.py` 258~262 행). 불린 순서대로 (줄, 열) 에 묶는다.

        불린 횟수가 듬성한 열 수 x 줄 수와 다르거나, 난이도의 레벨이 줄 번호와 다르면 오류 (순서 가정이 깨진 것).
        """
        queue = {}

        for kind, d in self.calls:
            queue.setdefault(kind, []).append(d)

        taken = {k: 0 for k in queue}

        for col, kind in enumerate(names_by_col):
            if kind not in KINDS:
                continue

            for row in range(num_rows):
                i = taken.get(kind, 0)
                seq = queue.get(kind, [])

                if i >= len(seq):
                    raise RuntimeError("%s 가 %d 번만 불렸는데 (줄 %d, 열 %d) 칸이 더 있다" % (kind, len(seq), row, col))

                d = seq[i]
                taken[kind] = i + 1

                if level_of(d) != row:
                    raise RuntimeError("호출 순서 가정이 깨졌다: %s 난이도 %.3f 는 레벨 %d, 칸 줄 %d" % (kind, d, level_of(d), row))

                self.bind(row, col, kind, d, size)

    def bind(self, row, col, kind, difficulty, size=TILE):
        tile = self.by_key.get(self.key(kind, difficulty)) or build_tile(kind, difficulty)
        self.by_cell[(row, col)] = {
            "kind": tile.kind, "group": tile.group, "level": tile.level,
            "flags_world": tile_to_world(tile.flags, row, col, size),
            "origin_world": tile_to_world(tile.origin[:2], row, col, size),
            "inner": tile.inner, "outer": tile.outer,
        }

    def save(self, path):
        arrays = {}

        for (r, c), v in self.by_cell.items():
            p = "%d_%d_" % (r, c)
            arrays[p + "flags"] = v["flags_world"]
            arrays[p + "origin"] = v["origin_world"]
            arrays[p + "inner"] = np.packbits(v["inner"])
            arrays[p + "outer"] = np.packbits(v["outer"])
            arrays[p + "meta"] = np.array([v["kind"], v["group"], str(v["level"])])

        np.savez_compressed(path, **arrays)

    @classmethod
    def load(cls, path, shape=None):
        shape = shape or (int(round(TILE[0] / MASK_RES)), int(round(TILE[1] / MASK_RES)))
        data = np.load(path)
        table = cls()
        cells = {tuple(int(x) for x in k.split("_")[:2]) for k in data.files}

        for r, c in cells:
            p = "%d_%d_" % (r, c)
            n = shape[0] * shape[1]
            meta = data[p + "meta"]
            table.by_cell[(r, c)] = {
                "kind": str(meta[0]), "group": str(meta[1]), "level": int(meta[2]),
                "flags_world": data[p + "flags"], "origin_world": data[p + "origin"],
                "inner": np.unpackbits(data[p + "inner"])[:n].astype(bool).reshape(shape),
                "outer": np.unpackbits(data[p + "outer"])[:n].astype(bool).reshape(shape),
            }

        return table


SIDE_TABLE = SideTable()


# ---------------------------------------------------------------- Isaac 껍질 (Kit 안에서만)


def _tile_function(difficulty, cfg):
    import trimesh

    tile = build_tile(cfg.kind, difficulty)
    SIDE_TABLE.record(cfg.kind, difficulty, tile)
    meshes = []

    for x0, x1, y0, y1, z0, z1 in tile.boxes:
        meshes.append(trimesh.creation.box((x1 - x0, y1 - y0, z1 - z0),
                                           trimesh.transformations.translation_matrix(
                                               ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0))))

    return meshes, tile.origin.copy()


def sparse_subterrains(proportions=None):
    """Isaac `sub_terrains` 항목. 비율은 `columns.SPARSE` (15 §3)."""
    import isaaclab.terrains as terrain_gen
    from isaaclab.utils import configclass

    from foothold_s2.terrains import columns

    @configclass
    class SparseTileCfg(terrain_gen.SubTerrainBaseCfg):
        function = _tile_function
        kind: str = "gaps"

    proportions = proportions or columns.SPARSE

    return {name: SparseTileCfg(proportion=p, size=TILE, kind=name) for name, p in proportions.items()}
