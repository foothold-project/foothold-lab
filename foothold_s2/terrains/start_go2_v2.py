"""EX-42 START Go2 training preset, isolated from the absolute START sheet.

D158 / DESIGN-EX42-TERRAIN-draft §4.2: x * 1.108, y * 0.885,
z unchanged. CURRICULUM-GATES v0.16:277,595 overrides only balance-beam
L9 width to 0.09 m; :294 specifies the family-E ranges in ex42.py.
Use exact products, not the rounded three-decimal display in the table.
Tile/frame dimensions stay 8 x 8 m with the original 8 x 4 m strip.
Legacy eval/start_sheet.py and sparse_terrains.py are deliberately untouched.
"""

import math

import numpy as np

from foothold_s2.eval import start_sheet as ss
from foothold_s2.terrains import sparse_terrains as legacy

PRESET_ID = "start_go2_v2"
SCALE_X = 1.108
SCALE_Y = 0.885
STONE_SIZE_X = tuple(v * SCALE_X for v in ss.STONE_SIZE)
STONE_SIZE_Y = tuple(v * SCALE_Y for v in ss.STONE_SIZE)
STONE_GAP_X = tuple(v * SCALE_X for v in ss.STONE_GAP_X)
STONE_GAP_Y = tuple(v * SCALE_Y for v in ss.STONE_GAP_Y)
BEAM_WIDTH = (ss.BEAM_WIDTH[0] * SCALE_Y, 0.09)
STEP_BEAM_WIDTH = tuple(v * SCALE_X for v in ss.STEP_BEAM_WIDTH)
STEP_BEAM_GAP = tuple(v * SCALE_X for v in ss.STEP_BEAM_GAP)
GAP_WIDTH = tuple(v * SCALE_X for v in ss.GAP_WIDTH)

# Shared shape/noise conventions, never mutate the legacy module's constants.
SIZE, ZONE_X, LEVELS, KINDS = ss.SIZE, ss.ZONE_X, ss.LEVELS, ss.KINDS
DEPTH_RANGE, HEIGHT_JITTER = ss.DEPTH_RANGE, ss.HEIGHT_JITTER
STONE_JITTER, STONE_COLUMN_JITTER = ss.STONE_JITTER, ss.STONE_COLUMN_JITTER
PLATFORM_Z, FLOOR_THICKNESS, N_GAPS = ss.PLATFORM_Z, ss.FLOOR_THICKNESS, ss.N_GAPS
_lerp, _frame, _box, SheetGeometry = ss._lerp, ss._frame, ss._box, ss.SheetGeometry


def generate(kind, level, rng, randomness=None):
    """한 칸을 만든다. 레벨은 0~9 정수, 10 이상은 오류 (negative control)."""
    if kind not in KINDS:
        raise ValueError("모르는 종류 %r. 있는 것: %r" % (kind, KINDS))

    if not isinstance(level, (int, np.integer)) or not 0 <= level < LEVELS:
        raise ValueError("레벨은 0..%d 정수여야 합니다: %r" % (LEVELS - 1, level))

    depth = float(rng.uniform(*DEPTH_RANGE))
    boxes = _frame(depth)
    support = [True, True, False]  # 구덩이 바닥은 딛는 면이 아니다 (떨어진 것)
    floor_bottom = PLATFORM_Z - depth - FLOOR_THICKNESS

    def add(x0, x1, y0, y1, jitter=True):
        top = PLATFORM_Z + (float(rng.uniform(-HEIGHT_JITTER, HEIGHT_JITTER)) if jitter else 0.0)
        boxes.append(_box(x0, x1, y0, y1, top, floor_bottom))
        support.append(True)

    x_lo, x_hi = ZONE_X
    params = {"preset_id": PRESET_ID, "level": int(level), "depth": depth}

    if kind == "stepping_stones":
        sx = _lerp(STONE_SIZE_X, level)
        sy = _lerp(STONE_SIZE_Y, level)
        gx = _lerp(STONE_GAP_X, level)
        gy = _lerp(STONE_GAP_Y, level)
        f = level / (LEVELS - 1)
        r = f if randomness is None else float(randomness)   # None: 레벨 비례 L/9 (시험지 기본 · 학습 고무작위 열). 학습 저무작위 열은 0 을 넘긴다
        jit = STONE_JITTER * r
        col_jit = STONE_COLUMN_JITTER * r
        px, py = sx + gx, sy + gy
        params.update(stone_x=sx, stone_y=sy, gap_x=gx, gap_y=gy, jitter=jit, column_jitter=col_jit)

        n_cols = int(math.floor((x_hi - x_lo + gx) / px))
        n_rows = int(math.floor((SIZE[1] + gy) / py))
        x_off = x_lo + ((x_hi - x_lo) - (n_cols * px - gx)) / 2.0
        y_off = ((SIZE[1]) - (n_rows * py - gy)) / 2.0

        for c in range(n_cols):
            shift = float(rng.uniform(-col_jit, col_jit)) * gx

            for r in range(n_rows):
                dx = float(rng.uniform(-jit, jit)) * gx
                dy = float(rng.uniform(-jit, jit)) * gy
                x0 = min(max(x_off + c * px + shift + dx, x_lo), x_hi - sx)
                y0 = min(max(y_off + r * py + dy, 0.0), SIZE[1] - sy)
                add(x0, x0 + sx, y0, y0 + sy)

        params.update(columns=n_cols, rows=n_rows)

    elif kind == "balance_beams":
        w = _lerp(BEAM_WIDTH, level)
        params.update(beam_width=w)
        y0 = SIZE[1] / 2.0 - w / 2.0
        add(x_lo, x_hi, y0, y0 + w)

    elif kind == "stepping_beams":
        w = _lerp(STEP_BEAM_WIDTH, level)
        g = _lerp(STEP_BEAM_GAP, level)
        pitch = w + g
        n = int(math.floor(((x_hi - x_lo) + g) / pitch))
        x_off = x_lo + ((x_hi - x_lo) - (n * pitch - g)) / 2.0
        params.update(beam=w, gap=g, count=n)

        for i in range(n):
            x0 = x_off + i * pitch
            add(x0, x0 + w, 0.0, SIZE[1])

    else:  # gaps
        g = _lerp(GAP_WIDTH, level)
        plat = ((x_hi - x_lo) - N_GAPS * g) / (N_GAPS + 1)
        params.update(gap_width=g, platform_length=plat, count=N_GAPS)

        if plat <= 0.0:
            raise ValueError("틈 폭 %.3f 에 플랫폼 길이가 0 이하입니다" % g)

        x = x_lo

        for _ in range(N_GAPS + 1):
            add(x, x + plat, 0.0, SIZE[1], jitter=False)
            x += plat + g

    return SheetGeometry(kind, int(level), boxes, support, depth, params)


def _support_flag(boxes, x, y, floor):
    """Keep the legacy target unless grid rounding put it outside a support.

    A 5 cm grid can round a thin Go2 beam outward. Project such a candidate
    onto the nearest actual support rectangle, with no new physical margin.
    """
    x, y = legacy._snap_to_support(boxes, x, y, floor)
    supports = boxes[boxes[:, 5] > floor + 0.1]
    if not len(supports):
        raise ValueError("start_go2_v2 flag has no support surface")
    px = np.clip(x, supports[:, 0], supports[:, 1])
    py = np.clip(y, supports[:, 2], supports[:, 3])
    i = np.argmin((px - x) ** 2 + (py - y) ** 2)
    return float(px[i]), float(py[i])


def build_tile(kind, difficulty):
    """Go2 geometry, flags and edge masks; original tile/frame/noise conventions."""
    start_kind, randomness, group = legacy.KINDS[kind]
    level = legacy.level_of(difficulty)
    rng = np.random.default_rng(legacy.seed_of(kind, difficulty))
    if start_kind is None:
        # Flat is identical in both presets.
        return legacy.build_tile(kind, difficulty)
    geom = generate(start_kind, level, rng, randomness=randomness)
    shifted = [(x0, x1, y0 + legacy.STRIP[0], y1 + legacy.STRIP[0], z0, z1)
               for x0, x1, y0, y1, z0, z1 in geom.boxes[3:]]
    boxes = np.asarray(legacy._frame(geom.depth) + shifted, dtype=float)
    inner, outer = legacy.edge_masks(legacy.height_grid(boxes))
    flags = np.array([_support_flag(boxes, x, legacy.TILE[1] / 2, -geom.depth)
                      for x in legacy.FLAG_X])
    return legacy.TileData(kind, group, level, boxes,
                           np.array([*legacy.SPAWN_XY, 0.0]), flags, inner, outer)


class SideTable(legacy.SideTable):
    """Separate preset cache, including reconstruction when Isaac's cache hits."""

    def bind(self, row, col, kind, difficulty, size=legacy.TILE):
        key = self.key(kind, difficulty)
        if key not in self.by_key:
            self.by_key[key] = build_tile(kind, difficulty)
        super().bind(row, col, kind, difficulty, size)


SIDE_TABLE = SideTable()


def _tile_function(difficulty, cfg):
    import trimesh

    tile = build_tile(cfg.kind, difficulty)
    SIDE_TABLE.record(cfg.kind, difficulty, tile)
    meshes = []
    for x0, x1, y0, y1, z0, z1 in tile.boxes:
        meshes.append(trimesh.creation.box(
            (x1 - x0, y1 - y0, z1 - z0),
            trimesh.transformations.translation_matrix(
                ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))))
    return meshes, tile.origin.copy()


def sparse_subterrains(proportions=None):
    """EX-42-only lazy Isaac configs; callers must opt in to this module.

    Existing EX-41/evaluation imports still resolve to sparse_terrains.
    Function identity and preset_id distinguish Isaac geometry cache entries.
    """
    from foothold_s2.terrains import columns

    proportions = proportions if proportions is not None else columns.SPARSE
    if not proportions or set(proportions) - set(legacy.KINDS):
        raise ValueError("start_go2_v2 requires known sparse terrain kinds")
    import isaaclab.terrains as terrain_gen
    from isaaclab.utils import configclass

    @configclass
    class Go2SparseTileCfg(terrain_gen.SubTerrainBaseCfg):
        function = _tile_function
        kind: str = "gaps"
        preset_id: str = PRESET_ID

    return {name: Go2SparseTileCfg(proportion=p, size=legacy.TILE, kind=name)
            for name, p in proportions.items()}
