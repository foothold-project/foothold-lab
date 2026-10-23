"""START 시험지 지형 생성기 (41 §6 · 15 §4). 순수 numpy, Kit 없음.

네 종: 징검돌 · 평균대 · 디딤 빔 · 틈. 8 x 4 m 칸, 레벨 0~9 (10 단).
Kit 쪽은 이 모듈이 돌려주는 상자 목록을 메시로 바꾸기만 한다 (`terrain_sets.py`).

칸 배치 (x 가 진행 방향, 단위 m)

    x 0 ~ 1.0   출발 단 (스폰 x = 0.5)
    x 1.0 ~ 7.0 듬성한 구간 (6 m)
    x 7.0 ~ 8.0 도착 단

논문 수치 (**논문** 41 §6): 레벨 9 에서 징검돌 희소도 76.3 % · 돌 0.2 m · 틈 0.25 x 0.175 m,
평균대 폭 0.175 m, 디딤 빔 희소도 64.7 % · 빔 0.15 m · 틈 0.275 m, 틈 폭 0.7 m. 깊이 U[0.2, 0.7] m,
돌 · 빔 높이 +-5 cm. 레벨 0 쪽 값은 15 §4 의 선행 범위(돌 0.5 m · 틈 0.175 x 0.1 · 틈 폭 0.1 m).

**가정**(논문에 최고 레벨 값만 있고 사이는 선형 보간을 쓴다): 평균대와 디딤 빔의 낮은 레벨 모양.
평균대는 연속 빔 하나의 폭만 0.6 -> 0.175 로, 디딤 빔은 칸 폭 전체를 가로지르는 막대의
폭 0.5 -> 0.15 · 간격 0.1 -> 0.275 로 줄인다 (선행의 「돌 두 줄 -> 한 줄」 「네 줄 돌 -> 빔 열」
이행은 옮기지 않았다). 틈 지형은 틈 셋을 같은 간격으로 둔다.
"""

import math

import numpy as np

SIZE = (8.0, 4.0)
SPAWN_XY = (0.5, 2.0)
ZONE_X = (1.0, 7.0)
GOAL_X = 7.0
REFERENCE_M = GOAL_X - SPAWN_XY[0]

LEVELS = 10
KINDS = ("stepping_stones", "balance_beams", "stepping_beams", "gaps")

DEPTH_RANGE = (0.2, 0.7)
HEIGHT_JITTER = 0.05

# (레벨 0 값, 레벨 9 값). 레벨 9 는 논문, 레벨 0 은 선행 (15 §4).
STONE_SIZE = (0.5, 0.2)
STONE_GAP_X = (0.175, 0.25)
STONE_GAP_Y = (0.1, 0.175)
STONE_JITTER = 0.5
STONE_COLUMN_JITTER = 0.45
BEAM_WIDTH = (0.6, 0.175)
STEP_BEAM_WIDTH = (0.5, 0.15)
STEP_BEAM_GAP = (0.1, 0.275)
GAP_WIDTH = (0.1, 0.7)
N_GAPS = 3

PLATFORM_Z = 0.0
FLOOR_THICKNESS = 0.2


def _lerp(pair, level):
    f = level / (LEVELS - 1)

    return pair[0] + (pair[1] - pair[0]) * f


class SheetGeometry:
    """한 칸. `boxes` 는 (N, 6) = x0 x1 y0 y1 z0 z1. 윗면이 z1."""

    def __init__(self, kind, level, boxes, supports, depth, params):
        self.kind = kind
        self.level = level
        self.boxes = np.asarray(boxes, dtype=float).reshape(-1, 6)
        self.supports = np.asarray(supports, dtype=bool)
        self.depth = float(depth)
        self.params = params

    def __len__(self):
        return len(self.boxes)


def _box(x0, x1, y0, y1, top, bottom):
    return (x0, x1, y0, y1, bottom, top)


def _frame(depth):
    """출발 · 도착 단과 구덩이 바닥. 모두 «딛는 면» 이다."""
    floor_top = PLATFORM_Z - depth
    out = [
        _box(0.0, ZONE_X[0], 0.0, SIZE[1], PLATFORM_Z, floor_top - FLOOR_THICKNESS),
        _box(ZONE_X[1], SIZE[0], 0.0, SIZE[1], PLATFORM_Z, floor_top - FLOOR_THICKNESS),
        _box(ZONE_X[0], ZONE_X[1], 0.0, SIZE[1], floor_top, floor_top - FLOOR_THICKNESS),
    ]

    return out


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
    params = {"level": int(level), "depth": depth}

    if kind == "stepping_stones":
        s = _lerp(STONE_SIZE, level)
        gx = _lerp(STONE_GAP_X, level)
        gy = _lerp(STONE_GAP_Y, level)
        f = level / (LEVELS - 1)
        r = f if randomness is None else float(randomness)   # None: 레벨 비례 L/9 (시험지 기본 · 학습 고무작위 열). 학습 저무작위 열은 0 을 넘긴다
        jit = STONE_JITTER * r
        col_jit = STONE_COLUMN_JITTER * r
        px, py = s + gx, s + gy
        params.update(stone=s, gap_x=gx, gap_y=gy, jitter=jit, column_jitter=col_jit)

        n_cols = int(math.floor((x_hi - x_lo + gx) / px))
        n_rows = int(math.floor((SIZE[1] + gy) / py))
        x_off = x_lo + ((x_hi - x_lo) - (n_cols * px - gx)) / 2.0
        y_off = ((SIZE[1]) - (n_rows * py - gy)) / 2.0

        for c in range(n_cols):
            shift = float(rng.uniform(-col_jit, col_jit)) * gx

            for r in range(n_rows):
                dx = float(rng.uniform(-jit, jit)) * gx
                dy = float(rng.uniform(-jit, jit)) * gy
                x0 = min(max(x_off + c * px + shift + dx, x_lo), x_hi - s)
                y0 = min(max(y_off + r * py + dy, 0.0), SIZE[1] - s)
                add(x0, x0 + s, y0, y0 + s)

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


# ---------------------------------------------------------------- 측정 (시험 · MEV 용)


def top_height_map(geom, resolution=0.01):
    """듬성한 구간의 «딛는 면 높이» 격자. 없으면 구덩이 바닥 높이."""
    nx = int(round((ZONE_X[1] - ZONE_X[0]) / resolution))
    ny = int(round(SIZE[1] / resolution))
    heights = np.full((nx, ny), PLATFORM_Z - geom.depth)

    for box, sup in zip(geom.boxes, geom.supports):
        if not sup:
            continue

        x0, x1, y0, y1, _z0, z1 = box
        ix0 = max(0, int(round((x0 - ZONE_X[0]) / resolution)))
        ix1 = min(nx, int(round((x1 - ZONE_X[0]) / resolution)))
        iy0 = max(0, int(round(y0 / resolution)))
        iy1 = min(ny, int(round(y1 / resolution)))

        if ix1 > ix0 and iy1 > iy0:
            heights[ix0:ix1, iy0:iy1] = np.maximum(heights[ix0:ix1, iy0:iy1], z1)

    return heights


def sparsity(geom, resolution=0.01):
    """듬성한 구간에서 딛는 면이 없는 넓이 비율 (구덩이 비율)."""
    heights = top_height_map(geom, resolution)
    floor = PLATFORM_Z - geom.depth

    return float(np.mean(heights <= floor + 1.0e-9))


def support_at(geom, x, y, tolerance=0.0):
    """(x, y) 아래 딛는 면 윗면 높이와 그 상자의 번호. 없으면 `(None, None)`."""
    best = (None, None)

    for i, (box, sup) in enumerate(zip(geom.boxes, geom.supports)):
        if not sup:
            continue

        x0, x1, y0, y1, _z0, z1 = box

        if x0 - tolerance <= x <= x1 + tolerance and y0 - tolerance <= y <= y1 + tolerance:
            if best[0] is None or z1 > best[0]:
                best = (z1, i)

    return best


def edge_distance(geom, x, y):
    """(x, y) 를 받치는 상자 윗면 가장자리까지의 거리. 받치는 상자가 없으면 None."""
    _z, i = support_at(geom, x, y)

    if i is None:
        return None

    x0, x1, y0, y1 = geom.boxes[i][:4]

    # 칸 가장자리(출발 · 도착 단의 바깥 둘레)는 가장자리로 세지 않는다.
    dists = []

    if x0 > 0.0:
        dists.append(x - x0)
    if x1 < SIZE[0]:
        dists.append(x1 - x)
    if y0 > 0.0:
        dists.append(y - y0)
    if y1 < SIZE[1]:
        dists.append(y1 - y)

    return min(dists) if dists else float("inf")


def mev(geom, foot_xy, band=0.05):
    """가장자리 디딤 비율(MEV): 발 디딤 지점 중 가장자리 `band` 안에 놓인 비율.

    받치는 면이 없는 지점(허공 · 구덩이)은 분모에서 뺀다. 분모가 0 이면 None.
    """
    hits = 0
    total = 0

    for x, y in foot_xy:
        d = edge_distance(geom, float(x), float(y))

        if d is None:
            continue

        total += 1

        if d < band:
            hits += 1

    return None if total == 0 else hits / total


def crossing_ratio(distance_before_fall_m, reference_m=REFERENCE_M):
    """주파율: 쓰러지기 전에 간 거리 / 전체 거리 (0..1 로 자른다)."""
    return min(max(distance_before_fall_m / reference_m, 0.0), 1.0)
