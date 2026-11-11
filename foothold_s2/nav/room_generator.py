"""HiPAN 주행층 방 생성기 (22-NAV-ENV §2 · §3 · §6). numpy 만 쓴다 (Kit 없이).

20 x 20 m 방 · 0.1 m 격자 (200 x 200) · 2 m 타일 10 x 10. 타일 종류를 WFC (엔트로피 최소 칸부터 정하고 인접 규칙으로 전파,
모순이면 같은 시드 흐름에서 다시) 로 깐 뒤 타일마다 높이와 등급을 그린다.
등급 (22 §3): FREE 0 · CONNECTED_ROUGH 1 · SPARSE 2 · BLOCKED 3 · OVERHEAD 4 (머리 위 장애물이 있으나 몸 높이보다 높아 통과 가능).
가정 (22 가 가정으로 적은 것): 타일 확률 · 패치 모양 (우리 지형 생성기 실제 치수가 아님, 대표값) · 몸 높이 0.4 m.
이 파일이 아직 하지 않는 것: 막다른 길 · 반쯤 닫힌 방, 우리 지형 생성기 (15 §8) 의 실제 치수 연결, 방 메시 (Kit).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

ROOM_M = 20.0
RES = 0.1
N = int(round(ROOM_M / RES))          # 200
TILE_M = 2.0
TILE = int(round(TILE_M / RES))       # 20
NT = N // TILE                        # 10

FREE, ROUGH_CONNECTED, SPARSE, BLOCKED, OVERHEAD = 0, 1, 2, 3, 4
FLAT, ROUGH, OBST, STAIRS, GAP, STONES, BEAM, LOG = range(8)
PATCHES = (STAIRS, GAP, STONES, BEAM, LOG)
TILE_NAMES = ("flat", "rough", "obstacle", "stairs", "gap", "stones", "beam", "log")
FLOOR_DROP = -1.0


@dataclass(frozen=True)
class RoomConfig:
    weights: tuple = (4.0, 2.0, 2.0, 0.5, 0.4, 0.4, 0.3, 0.3)   # 타일 종류별 WFC 가중 (가정)
    max_gap_cross_m: float = 0.7        # 하위가 넘는 최대 틈 폭 (S1/S2 레벨표가 정함 · 가정)
    gap_width_m: float = 0.5
    stair_step_m: float = 0.15
    beam_width_m: float = 0.4
    log_width_m: float = 0.15
    stone_m: float = 0.3
    stone_pitch_m: float = 0.5
    body_height_m: float = 0.4
    p_wall: float = 0.2                 # 22 §6.2 가정
    p_table: float = 0.1
    p_box: float = 0.1
    min_free_fraction: float = 0.35     # 가장 큰 통과 가능 덩어리 / 방 면적 (아니면 새 시드 흐름)
    max_tries: int = 50


@dataclass
class Room:
    seed: int
    tiles: np.ndarray                   # (10, 10) 타일 종류
    height: np.ndarray                  # (200, 200) 바닥 높이 m
    grade: np.ndarray                   # (200, 200) uint8 등급
    clearance: np.ndarray               # (200, 200) 머리 위 장애물 아래면 높이 m (없으면 inf)
    objects: list = field(default_factory=list)   # dict(kind, x0, y0, x1, y1 (m), z0, z1)
    tries: int = 1


def _cells(m: float) -> int:
    """미터 -> 격자 칸 (올림, 부동소수 오차 허용: 0.15 m 는 2 칸)."""
    return max(1, int(np.ceil(m / RES - 1e-6)))


def _allowed(a: int, b: int, axis: int) -> bool:
    """타일 a 옆에 b 가 올 수 있나. axis 0 = x 방향 이웃 (건너는 방향) · 1 = y 방향 이웃."""
    for p, q in ((a, b), (b, a)):
        if p in PATCHES:
            if axis == 0:
                if q != FLAT:                    # 패치 앞뒤는 평지 (22 §6.1)
                    return False
            elif q not in (FLAT, ROUGH, p):      # 옆은 평지 · 거친 면 · 같은 패치
                return False
    return True


_ALLOW = np.array([[[_allowed(a, b, ax) for b in range(8)] for a in range(8)] for ax in (0, 1)])


def wfc_tiles(rng: np.random.Generator, weights, max_restarts: int = 200) -> np.ndarray:
    w = np.asarray(weights, dtype=np.float64)
    for _ in range(max_restarts):
        dom = np.ones((NT, NT, 8), dtype=bool)
        ok = True
        while True:
            cnt = dom.sum(-1)
            if (cnt == 0).any():
                ok = False
                break
            open_ = cnt > 1
            if not open_.any():
                break
            ent = np.where(open_, cnt + rng.random(cnt.shape) * 0.1, np.inf)
            i, j = np.unravel_index(np.argmin(ent), ent.shape)
            p = dom[i, j] * w
            k = rng.choice(8, p=p / p.sum())
            dom[i, j] = False
            dom[i, j, k] = True
            stack = [(i, j)]
            while stack and ok:
                ci, cj = stack.pop()
                for di, dj, ax in ((1, 0, 0), (-1, 0, 0), (0, 1, 1), (0, -1, 1)):
                    ni, nj = ci + di, cj + dj
                    if not (0 <= ni < NT and 0 <= nj < NT):
                        continue
                    sup = _ALLOW[ax][dom[ci, cj]].any(0)
                    new = dom[ni, nj] & sup
                    if (new != dom[ni, nj]).any():
                        dom[ni, nj] = new
                        if not new.any():
                            ok = False
                            break
                        stack.append((ni, nj))
            if not ok:
                break
        if ok:
            return dom.argmax(-1).astype(np.int8)
    raise RuntimeError("WFC did not converge")


def _paint_tile(kind, cfg, rng, h, g, clr, objs, ti, tj):
    xs, ys = slice(ti * TILE, (ti + 1) * TILE), slice(tj * TILE, (tj + 1) * TILE)
    H, G = h[xs, ys], g[xs, ys]
    x0m, y0m = ti * TILE_M, tj * TILE_M
    if kind == FLAT:
        return
    if kind == ROUGH:
        H[:] = rng.uniform(-0.03, 0.03, H.shape)
        G[:] = FREE
    elif kind == STAIRS:
        # 올라갔다 내려오는 계단 (양 끝은 0 높이로 평지와 이어짐). x 방향 5 단 폭 0.4 m
        steps = np.interp(np.arange(TILE), [0, 4, 8, 11, 15, 19], [0, 1, 2, 2, 1, 0]).round()
        H[:] = (steps * cfg.stair_step_m)[:, None]
        G[:] = ROUGH_CONNECTED
    elif kind == GAP:
        wc = _cells(cfg.gap_width_m)
        a = (TILE - wc) // 2
        H[a:a + wc, :] = FLOOR_DROP
        G[a:a + wc, :] = SPARSE if cfg.gap_width_m <= cfg.max_gap_cross_m else BLOCKED
    elif kind == STONES:
        sc = _cells(cfg.stone_m)
        pc = max(sc + 1, _cells(cfg.stone_pitch_m))
        H[:] = FLOOR_DROP
        G[:] = BLOCKED
        for a in range(2, TILE - sc + 1, pc):
            for b in range(1, TILE - sc + 1, pc):
                H[a:a + sc, b:b + sc] = 0.0
                G[a:a + sc, b:b + sc] = SPARSE
    elif kind in (BEAM, LOG):
        wm = cfg.beam_width_m if kind == BEAM else cfg.log_width_m
        wc = _cells(wm)
        a = (TILE - wc) // 2
        H[:] = FLOOR_DROP
        G[:] = BLOCKED
        H[:, a:a + wc] = 0.0
        G[:, a:a + wc] = SPARSE
    elif kind == OBST:
        if rng.random() < cfg.p_wall:
            horiz = rng.random() < 0.5
            L, t = int(1.6 / RES), 2
            a, b = int(0.2 / RES), (TILE - t) // 2
            if horiz:
                sl = (slice(a, a + L), slice(b, b + t))
                box = (x0m + a * RES, y0m + b * RES, x0m + (a + L) * RES, y0m + (b + t) * RES)
            else:
                sl = (slice(b, b + t), slice(a, a + L))
                box = (x0m + b * RES, y0m + a * RES, x0m + (b + t) * RES, y0m + (a + L) * RES)
            G[sl] = BLOCKED
            objs.append(dict(kind="wall", x0=box[0], y0=box[1], x1=box[2], y1=box[3], z0=0.0, z1=2.0))
        if rng.random() < cfg.p_table:
            s = int(0.8 / RES)
            a, b = rng.integers(2, TILE - s - 1, 2)
            z = 0.7
            _overhead(G, clr[xs, ys], (slice(a, a + s), slice(b, b + s)), z, cfg)
            for da in (0, s - 1):          # 다리 4 개 (한 칸)
                for db in (0, s - 1):
                    G[a + da, b + db] = BLOCKED
            objs.append(dict(kind="table", x0=x0m + a * RES, y0=y0m + b * RES, x1=x0m + (a + s) * RES, y1=y0m + (b + s) * RES, z0=z - 0.05, z1=z))
        if rng.random() < cfg.p_box:
            s = int(0.6 / RES)
            a, b = rng.integers(2, TILE - s - 1, 2)
            z0 = float(rng.uniform(0.2, 1.0))
            _overhead(G, clr[xs, ys], (slice(a, a + s), slice(b, b + s)), z0, cfg)
            objs.append(dict(kind="box", x0=x0m + a * RES, y0=y0m + b * RES, x1=x0m + (a + s) * RES, y1=y0m + (b + s) * RES, z0=z0, z1=z0 + 0.5))


def _overhead(G, C, sl, bottom, cfg):
    C[sl] = np.minimum(C[sl], bottom)
    if bottom <= cfg.body_height_m:
        G[sl] = BLOCKED
    else:
        cur = G[sl]
        G[sl] = np.where(cur == BLOCKED, BLOCKED, OVERHEAD)


def passable(grade: np.ndarray) -> np.ndarray:
    return grade != BLOCKED


def largest_component(mask: np.ndarray) -> int:
    seen = np.zeros_like(mask, dtype=bool)
    best = 0
    for s in zip(*np.nonzero(mask)):
        if seen[s]:
            continue
        stack, n = [s], 0
        seen[s] = True
        while stack:
            x, y = stack.pop()
            n += 1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = x + dx, y + dy
                if 0 <= a < mask.shape[0] and 0 <= b < mask.shape[1] and mask[a, b] and not seen[a, b]:
                    seen[a, b] = True
                    stack.append((a, b))
        best = max(best, n)
    return best


def make_room(seed: int, cfg: RoomConfig | None = None) -> Room:
    cfg = cfg or RoomConfig()
    rng = np.random.default_rng(seed)
    for tries in range(1, cfg.max_tries + 1):
        tiles = wfc_tiles(rng, cfg.weights)
        h = np.zeros((N, N))
        g = np.full((N, N), FREE, dtype=np.uint8)
        clr = np.full((N, N), np.inf)
        objs: list = []
        for ti in range(NT):
            for tj in range(NT):
                _paint_tile(int(tiles[ti, tj]), cfg, rng, h, g, clr, objs, ti, tj)
        g[:2, :] = g[-2:, :] = BLOCKED          # 바깥 벽 0.2 m
        g[:, :2] = g[:, -2:] = BLOCKED
        if largest_component(passable(g)) / g.size >= cfg.min_free_fraction:
            return Room(seed, tiles, h, g, clr, objs, tries)
    raise RuntimeError("no room met min_free_fraction")


def sample_free_points(room: Room, rng: np.random.Generator, n: int, margin_m: float = 0.3) -> np.ndarray:
    """무충돌 위치 균등 표본 (22 §6.6): 가장 큰 통과 가능 덩어리 안에서 BLOCKED 와 margin 이상 떨어진 평지 · 이어진 험지 · 거친 면 셀 (미터, 방 모서리 기준 xy)."""
    blocked = room.grade == BLOCKED
    m = int(round(margin_m / RES))
    bad = blocked.copy()
    for dx in range(-m, m + 1):
        for dy in range(-m, m + 1):
            bad |= np.roll(np.roll(blocked, dx, 0), dy, 1)
    ok = (~bad) & np.isin(room.grade, (FREE, ROUGH_CONNECTED))
    comp = _component_mask(passable(room.grade))
    cells = np.argwhere(ok & comp)
    if len(cells) == 0:
        raise ValueError("no free cell")
    pick = cells[rng.integers(0, len(cells), n)]
    return (pick + 0.5) * RES


def _component_mask(mask: np.ndarray) -> np.ndarray:
    seen = np.zeros_like(mask, dtype=bool)
    best, best_cells = 0, None
    for s in zip(*np.nonzero(mask)):
        if seen[s]:
            continue
        stack, cells = [s], []
        seen[s] = True
        while stack:
            x, y = stack.pop()
            cells.append((x, y))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a, b = x + dx, y + dy
                if 0 <= a < mask.shape[0] and 0 <= b < mask.shape[1] and mask[a, b] and not seen[a, b]:
                    seen[a, b] = True
                    stack.append((a, b))
        if len(cells) > best:
            best, best_cells = len(cells), cells
    out = np.zeros_like(mask, dtype=bool)
    if best_cells:
        idx = np.array(best_cells)
        out[idx[:, 0], idx[:, 1]] = True
    return out
