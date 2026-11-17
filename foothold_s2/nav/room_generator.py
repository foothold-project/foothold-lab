"""HiPAN 주행층 방 생성기 (PLAN-HIPAN-V2 §5.1 · M3 · 22-NAV-ENV §2 · §6). numpy 만 쓴다 (Kit 없이).

흐름: 시드 -> `generate_spec` (WFC 타일 + 지형 패치 + 장애물 = 방 명세) -> `build_room` (격자 · 메시) -> `write_room` (EX-42 메시 꼴).
방 명세는 yaml 로 적을 수 있는 원시 도형 목록이라 손으로 적은 방 (벤치마크 · 답 아는 방, `nav/rooms/*.yaml`) 도 같은 경로로 만든다.
20 x 20 m · 0.1 m 격자 200 x 200 · 바탕 타일 2 m 10 x 10 (가정). 지형 패치는 EX-42 의 듬성한 발판 생성기
(`terrains/sparse_terrains.build_tile`, 8 x 8 m 칸) 를 불러 쓴다 (복사하지 않음). 패치 앞뒤 (건너는 x 방향) 에는 평지 타일 한 줄.
등급 판정은 이 파일이 아니라 `grade_map.py` 몫이다. 여기서는 셀 종류 (CELL_*) 와 높이 · 머리 위 여유 · 틈 폭만 낸다.
이 파일이 아직 하지 않는 것: 막다른 길 · 반쯤 닫힌 방, 연속 7 종 · 묶음 B C D 의 패치 (계단 2 m 타일만 임시), Kit 장착 · 충돌 시험.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

ROOM_M = 20.0
RES = 0.1
N = int(round(ROOM_M / RES))          # 200
TILE_M = 2.0
TILE = int(round(TILE_M / RES))       # 20
NT = N // TILE                        # 10
PATCH_TILES = 4                       # 8 m 패치 = 타일 4 x 4
WALL_H = 1.2                          # 계획 §5.1
OUTER_WALL_M = 0.2                    # 둘레 벽 두께 기본 (손으로 적은 방 · 옛 꼴). maze 명세는 spec["outer_wall_m"] = MAZE_OUTER_WALL_M (설계 3.1)
MAZE_OUTER_WALL_M = 0.3
PIT_DROP = -1.0

# 셀 종류 (grade_map.py 가 등급으로 옮김)
CELL_FLAT, CELL_ROUGH, CELL_STAIRS, CELL_FOOTHOLD, CELL_PIT, CELL_GAP_PIT, CELL_WALL, CELL_LEG, CELL_OVERHEAD = range(9)
TILE_FLAT, TILE_ROUGH, TILE_OBST, TILE_STAIRS = range(4)
TILE_NAMES = ("flat", "rough", "obstacle", "stairs")
PATCH_KINDS = ("stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams", "gaps")


@dataclass(frozen=True)
class RoomConfig:
    weights: tuple = (4.0, 2.0, 2.0, 0.6)      # flat rough obstacle stairs (가정)
    stair_step_m: float = 0.15
    p_wall: float = 0.2                        # 22 §6.2 가정
    p_table: float = 0.1
    p_box: float = 0.1
    n_patches: int = 2                         # 8 x 8 m 둘 = 방 면적의 32 % (30 % 안팎, 가정)
    min_free_fraction: float = 0.35
    max_tries: int = 200
    layout: str = "maze"                       # "maze" = 길과 벽 (막힌 덩어리 + 타일 경계 벽 + 문 · DESIGN-HIPAN-ROOMS-1117 3.1 · 기본) | "old" = 옛 꼴 (막힌 타일에 벽 확률 p_wall)
    block_frac: float = 0.22                   # maze: 막힌 타일 비율 (1~3 타일짜리 덩어리)
    wall_keep: float = 0.55                    # maze: 신장 나무에 없는 타일 경계에 벽을 세울 확률 (0 = 벽 없음 · 1 = 완전 미로). make_room 의 keep_choices 가 시드마다 고름
    door_frac: float = 0.35                    # maze: 세운 벽 가운데 문을 내는 비율
    door_m: float = 1.0
    wall_t_m: float = 0.2
    p_pillar: float = 0.08                     # maze: 자유 타일 가운데 1.2 m 안에 흩는 탁자 · 상자 · 기둥 (p_table · p_box 와 함께)
    keep_choices: tuple = (0.35, 0.55, 0.75)   # make_room 이 시드로 돌려가며 쓰는 wall_keep (설계 3.2 제안: 셋 둘씩). () = wall_keep 그대로
    free_range: tuple = (0.55, 0.80)           # maze 수락: 통과 가능 칸 비율 (설계 3.4)
    min_dead_end_tiles: int = 3                # maze 수락: 막다른 타일 수
    min_connected: float = 0.98                # maze 수락: 통과 가능 칸 중 가장 큰 덩어리 비율
    min_passage_m: float = 0.8                 # maze 수락: 가장 좁은 통과 폭
    sparse_patch_kinds: tuple = PATCH_KINDS    # 듬성한 패치 (징검돌 · 외나무 · 틈) 로 쓸 종류. () = 뺌 (HiPAN 1 차 방: 팀장 11/16 · FIRST_ROUND_CFG)

    def __post_init__(self):
        if self.layout not in ("maze", "old"):
            raise ValueError(f"layout must be maze | old: {self.layout}")
        bad = [k for k in self.sparse_patch_kinds if k not in PATCH_KINDS]
        if bad:
            raise ValueError(f"unknown sparse patch kinds {bad}; allowed {PATCH_KINDS}")


# HiPAN 모드 2 의 1 차 학습 방: 하위 (E1F) 가 안 배운 듬성한 패치를 뺀다. 다시 넣으려면 `replace(FIRST_ROUND_CFG, sparse_patch_kinds=PATCH_KINDS)` 한 줄
FIRST_ROUND_CFG = RoomConfig(sparse_patch_kinds=())


# ---------------------------------------------------------------- WFC


def _allowed(a: int, b: int, axis: int) -> bool:
    """타일 a 옆에 b. axis 0 = x (건너는 방향): 계단 앞뒤는 평지. axis 1 = y: 계단 옆은 평지 · 거친 면 · 계단."""
    for p, q in ((a, b), (b, a)):
        if p == TILE_STAIRS:
            if axis == 0 and q != TILE_FLAT:
                return False
            if axis == 1 and q not in (TILE_FLAT, TILE_ROUGH, TILE_STAIRS):
                return False
    return True


_K = len(TILE_NAMES)
_ALLOW = np.array([[[_allowed(a, b, ax) for b in range(_K)] for a in range(_K)] for ax in (0, 1)])


def wfc_tiles(rng: np.random.Generator, weights, max_restarts: int = 200) -> np.ndarray:
    w = np.asarray(weights, dtype=np.float64)
    if w.shape != (_K,) or (w <= 0).any():
        raise ValueError(f"weights must be {_K} positive values")
    for _ in range(max_restarts):
        dom = np.ones((NT, NT, _K), dtype=bool)
        ok = True
        while ok:
            cnt = dom.sum(-1)
            open_ = cnt > 1
            if not open_.any():
                break
            ent = np.where(open_, cnt + rng.random(cnt.shape) * 0.1, np.inf)
            i, j = np.unravel_index(np.argmin(ent), ent.shape)
            p = dom[i, j] * w
            k = rng.choice(_K, p=p / p.sum())
            dom[i, j] = False
            dom[i, j, k] = True
            stack = [(i, j)]
            while stack and ok:
                ci, cj = stack.pop()
                for di, dj, ax in ((1, 0, 0), (-1, 0, 0), (0, 1, 1), (0, -1, 1)):
                    ni, nj = ci + di, cj + dj
                    if not (0 <= ni < NT and 0 <= nj < NT):
                        continue
                    new = dom[ni, nj] & _ALLOW[ax][dom[ci, cj]].any(0)
                    if (new != dom[ni, nj]).any():
                        dom[ni, nj] = new
                        if not new.any():
                            ok = False
                            break
                        stack.append((ni, nj))
        if ok:
            return dom.argmax(-1).astype(np.int8)
    raise RuntimeError("WFC did not converge")


# ---------------------------------------------------------------- 명세


def generate_spec(seed: int, cfg: RoomConfig | None = None, grade_table: dict | None = None) -> dict:
    """시드 -> 방 명세 (yaml 로 적을 수 있음). grade_table: `{kind: {max_passed_level: int}}` (없으면 패치를 넣지 않음). cfg.layout 이 maze (기본) 면 길과 벽 방."""
    cfg = cfg or RoomConfig()
    if cfg.layout == "maze":
        return _generate_spec_maze(seed, cfg, grade_table)
    return _generate_spec_old(seed, cfg, grade_table)


def _generate_spec_old(seed: int, cfg: RoomConfig, grade_table: dict | None) -> dict:
    rng = np.random.default_rng(seed)
    tiles = wfc_tiles(rng, cfg.weights)
    prims: list = []
    taken = np.zeros((NT, NT), dtype=bool)
    kinds = [k for k in cfg.sparse_patch_kinds if grade_table and grade_table.get(k, {}).get("max_passed_level", -1) >= 0]
    if kinds:
        for _ in range(cfg.n_patches):
            cands = [(r, c) for r in range(1, NT - PATCH_TILES) for c in range(0, NT - PATCH_TILES + 1)
                     if not taken[r - 1:r + PATCH_TILES + 1, c:c + PATCH_TILES].any()]
            if not cands:
                break
            r, c = cands[int(rng.integers(0, len(cands)))]
            kind = kinds[int(rng.integers(0, len(kinds)))]
            level = int(rng.integers(0, int(grade_table[kind]["max_passed_level"]) + 1))
            tiles[r - 1:r + PATCH_TILES + 1, c:c + PATCH_TILES] = TILE_FLAT      # 앞뒤 평지 (x 방향 한 줄)
            taken[r - 1:r + PATCH_TILES + 1, c:c + PATCH_TILES] = True
            prims.append({"type": "patch", "kind": kind, "level": level, "x": r * TILE_M, "y": c * TILE_M})
    for i in range(NT):
        for j in range(NT):
            t = int(tiles[i, j])
            x0, y0 = i * TILE_M, j * TILE_M
            if t == TILE_ROUGH:
                prims.append({"type": "rough", "x0": x0, "y0": y0, "x1": x0 + TILE_M, "y1": y0 + TILE_M, "seed": int(rng.integers(0, 2**31))})
            elif t == TILE_STAIRS:
                prims.append({"type": "stairs", "x": x0, "y": y0, "step_m": cfg.stair_step_m})
            elif t == TILE_OBST:
                if rng.random() < cfg.p_wall:
                    horiz = bool(rng.random() < 0.5)
                    a, L, th = 0.2, 1.6, 0.2
                    b = (TILE_M - th) / 2
                    box = (x0 + a, y0 + b, x0 + a + L, y0 + b + th) if horiz else (x0 + b, y0 + a, x0 + b + th, y0 + a + L)
                    prims.append({"type": "wall", "x0": box[0], "y0": box[1], "x1": box[2], "y1": box[3], "h": WALL_H})
                if rng.random() < cfg.p_table:
                    a, b = rng.uniform(0.2, TILE_M - 1.0, 2)
                    prims.append({"type": "table", "x": round(x0 + float(a), 1), "y": round(y0 + float(b), 1), "w": 0.8, "top": 0.7})
                if rng.random() < cfg.p_box:
                    a, b = rng.uniform(0.2, TILE_M - 0.8, 2)
                    prims.append({"type": "box", "x": round(x0 + float(a), 1), "y": round(y0 + float(b), 1), "w": 0.6,
                                  "z0": round(float(rng.uniform(0.2, 1.0)), 2), "h": 0.5})
    return {"seed": int(seed), "size_m": ROOM_M, "tiles": tiles.tolist(), "primitives": prims}



# ---------------------------------------------------------------- 길과 벽 방 (DESIGN-HIPAN-ROOMS-1117 3.1)

_NB4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _tiles_connected(free: np.ndarray) -> bool:
    cells = np.argwhere(free)
    if not len(cells):
        return False
    seen = np.zeros_like(free)
    stack = [tuple(cells[0])]
    seen[stack[0]] = True
    n = 1
    while stack:
        i, j = stack.pop()
        for a, b in _NB4:
            p, q = i + a, j + b
            if 0 <= p < free.shape[0] and 0 <= q < free.shape[1] and free[p, q] and not seen[p, q]:
                seen[p, q] = True
                n += 1
                stack.append((p, q))
    return n == len(cells)


def _block_tiles(rng: np.random.Generator, frac: float, taken: np.ndarray) -> np.ndarray:
    """타일의 frac 를 1~3 타일짜리 덩어리 (1x1 · 2x2 · 1x3 · 3x1 · 1x2 · 2x1) 로 막는다. 남은 자유 타일은 한 덩어리로 이어진 채로 (taken = 패치 자리 · 막지 않음)."""
    blocked = np.zeros((NT, NT), bool)
    target, tries = int(round(frac * NT * NT)), 0
    while blocked.sum() < target and tries < 500:
        tries += 1
        i, j = rng.integers(0, NT, 2)
        h, w = tuple(int(x) for x in rng.integers(1, 3, 2)) if rng.random() < 0.7 else (1, 1)
        if rng.random() < 0.3:
            h, w = (3, 1) if rng.random() < 0.5 else (1, 3)
        if taken[i:i + h, j:j + w].any() or i + h > NT or j + w > NT:
            continue
        cand = blocked.copy()
        cand[i:i + h, j:j + w] = True
        if _tiles_connected(~cand):
            blocked = cand
    return blocked


def _spanning_tree_edges(rng: np.random.Generator, free: np.ndarray) -> set:
    """자유 타일 위 무작위 신장 나무 (깊이 우선). 돌려주는 값: 가지 (두 타일의 frozenset) 집합. 나무 가지는 늘 열려 있다 = 어디든 갈 수 있음의 보장."""
    cells = [tuple(int(v) for v in c) for c in np.argwhere(free)]
    start = cells[int(rng.integers(len(cells)))]
    seen, stack, edges = {start}, [start], set()
    while stack:
        c = stack[-1]
        nb = [(c[0] + a, c[1] + b) for a, b in _NB4 if 0 <= c[0] + a < NT and 0 <= c[1] + b < NT and free[c[0] + a, c[1] + b] and (c[0] + a, c[1] + b) not in seen]
        if not nb:
            stack.pop()
            continue
        n = nb[int(rng.integers(len(nb)))]
        seen.add(n)
        edges.add(frozenset((c, n)))
        stack.append(n)
    return edges


def _generate_spec_maze(seed: int, cfg: RoomConfig, grade_table: dict | None) -> dict:
    rng = np.random.default_rng(seed)
    prims: list = []
    taken = np.zeros((NT, NT), dtype=bool)
    kinds = [k for k in cfg.sparse_patch_kinds if grade_table and grade_table.get(k, {}).get("max_passed_level", -1) >= 0]
    patch_tiles = np.zeros((NT, NT), dtype=bool)
    if kinds:
        for _ in range(cfg.n_patches):
            cands = [(r, c) for r in range(1, NT - PATCH_TILES) for c in range(0, NT - PATCH_TILES + 1)
                     if not taken[r - 1:r + PATCH_TILES + 1, c:c + PATCH_TILES].any()]
            if not cands:
                break
            r, c = cands[int(rng.integers(0, len(cands)))]
            kind = kinds[int(rng.integers(0, len(kinds)))]
            level = int(rng.integers(0, int(grade_table[kind]["max_passed_level"]) + 1))
            taken[r - 1:r + PATCH_TILES + 1, c:c + PATCH_TILES] = True
            patch_tiles[r - 1:r + PATCH_TILES + 1, c:c + PATCH_TILES] = True
            prims.append({"type": "patch", "kind": kind, "level": level, "x": r * TILE_M, "y": c * TILE_M})
    blocked = _block_tiles(rng, cfg.block_frac, taken)
    free_t = ~blocked
    # 바닥 종류: WFC 로 평지 · 거친 면 · 계단을 깔고, 막힌 타일은 덩어리가 대신한다. WFC 가 낸 「막힌 면」 은 평지로 되돌린다
    tiles = wfc_tiles(rng, cfg.weights)
    tiles[tiles == TILE_OBST] = TILE_FLAT
    tiles[taken] = TILE_FLAT
    tiles[blocked] = TILE_OBST
    for i in range(NT):
        for j in range(NT):
            if tiles[i, j] == TILE_STAIRS and any(0 <= i + a < NT and 0 <= j + b < NT and blocked[i + a, j + b] for a, b in _NB4):
                tiles[i, j] = TILE_FLAT                         # 계단 둘레에 막힌 덩어리가 닿으면 평지로 (앞뒤는 오르내리는 혹이 되고 · 옆은 WFC 이웃 규칙 (_allowed) 을 어긴다)
    for i in range(NT):
        for j in range(NT):
            t, x0, y0 = int(tiles[i, j]), i * TILE_M, j * TILE_M
            if t == TILE_ROUGH:
                prims.append({"type": "rough", "x0": x0, "y0": y0, "x1": x0 + TILE_M, "y1": y0 + TILE_M, "seed": int(rng.integers(0, 2**31))})
            elif t == TILE_STAIRS:
                prims.append({"type": "stairs", "x": x0, "y": y0, "step_m": cfg.stair_step_m})
            elif t == TILE_OBST:
                prims.append({"type": "wall", "x0": x0, "y0": y0, "x1": x0 + TILE_M, "y1": y0 + TILE_M, "h": WALL_H})     # 막힌 덩어리: 못 지나는 타일
    # 얇은 벽: 나무에 없는 경계를 keep 확률로 세운다 (패치 타일에 닿는 경계는 열어 둔다)
    tree = _spanning_tree_edges(rng, free_t & ~patch_tiles) if (free_t & ~patch_tiles).any() else set()
    edges, th, dm = [], cfg.wall_t_m, cfg.door_m
    for i in range(NT):
        for j in range(NT):
            if not free_t[i, j]:
                continue
            for a, b in ((1, 0), (0, 1)):
                p, q = i + a, j + b
                if p >= NT or q >= NT or not free_t[p, q] or patch_tiles[i, j] or patch_tiles[p, q]:
                    continue
                if frozenset(((i, j), (p, q))) in tree or rng.random() >= cfg.wall_keep:
                    continue
                door = bool(rng.random() < cfg.door_frac)
                off = round(float(rng.uniform(0.3, TILE_M - dm - 0.3)), 1) if door else None
                edges.append([i, j, a, b, door])
                pieces = [(0.0, TILE_M)] if not door else [(0.0, off), (off + dm, TILE_M)]
                for lo, hi in pieces:
                    if a == 1:      # x 방향 경계: x = p * TILE_M 에 y 로 뻗은 벽
                        prims.append({"type": "wall", "x0": round(p * TILE_M - th / 2, 2), "y0": round(j * TILE_M + lo, 2), "x1": round(p * TILE_M + th / 2, 2), "y1": round(j * TILE_M + hi, 2), "h": WALL_H})
                    else:
                        prims.append({"type": "wall", "x0": round(i * TILE_M + lo, 2), "y0": round(q * TILE_M - th / 2, 2), "x1": round(i * TILE_M + hi, 2), "y1": round(q * TILE_M + th / 2, 2), "h": WALL_H})
    # 흩는 것: 자유 타일 가운데 1.2 m 안에 탁자 · 상자 · 기둥 (통로를 막지 않게)
    for i in range(NT):
        for j in range(NT):
            if not free_t[i, j] or taken[i, j] or tiles[i, j] == TILE_STAIRS:
                continue
            x0, y0 = i * TILE_M, j * TILE_M
            if rng.random() < cfg.p_table:
                a, b = rng.uniform(0.4, 0.8, 2)
                prims.append({"type": "table", "x": round(x0 + float(a), 1), "y": round(y0 + float(b), 1), "w": 0.8, "top": 0.7})
            elif rng.random() < cfg.p_box:
                a, b = rng.uniform(0.4, 1.0, 2)
                prims.append({"type": "box", "x": round(x0 + float(a), 1), "y": round(y0 + float(b), 1), "w": 0.6, "z0": round(float(rng.uniform(0.2, 1.0)), 2), "h": 0.5})
            elif rng.random() < cfg.p_pillar:
                a, b = rng.uniform(0.5, 1.2, 2)
                prims.append({"type": "wall", "x0": round(x0 + float(a), 2), "y0": round(y0 + float(b), 2), "x1": round(x0 + float(a) + 0.3, 2), "y1": round(y0 + float(b) + 0.3, 2), "h": WALL_H})
    return {"seed": int(seed), "size_m": ROOM_M, "outer_wall_m": MAZE_OUTER_WALL_M, "tiles": tiles.tolist(), "primitives": prims,
            "maze": {"wall_keep": float(cfg.wall_keep), "blocked": [[int(i), int(j)] for i, j in np.argwhere(blocked)], "edges": edges}}


def dead_end_tiles(spec: dict) -> int:
    """막다른 타일 수: 자유 타일 가운데 실제로 드나들 수 있는 (벽이 없거나 문이 있는) 이웃 자유 타일이 하나뿐인 것. maze 명세가 없으면 0."""
    mz = spec.get("maze")
    if not mz:
        return 0
    blocked = {(int(i), int(j)) for i, j in mz["blocked"]}
    closed = {frozenset(((i, j), (i + a, j + b))) for i, j, a, b, door in mz["edges"] if not door}
    n = 0
    for i in range(NT):
        for j in range(NT):
            if (i, j) in blocked:
                continue
            deg = sum(1 for a, b in _NB4 if 0 <= i + a < NT and 0 <= j + b < NT and (i + a, j + b) not in blocked and frozenset(((i, j), (i + a, j + b))) not in closed)
            n += deg == 1
    return n


def load_spec(path) -> dict:
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(d, dict) or "primitives" not in d:
        raise ValueError("room spec needs a primitives list")
    return d


# ---------------------------------------------------------------- 방


@dataclass
class Room:
    spec: dict
    height: np.ndarray                  # (200, 200) 바닥 윗면 높이 m
    cell: np.ndarray                    # (200, 200) uint8 CELL_*
    clearance: np.ndarray               # 머리 위 장애물 아래면 높이 (없으면 inf)
    gap_width: np.ndarray               # 틈 셀의 틈 폭 m (그 밖 0)
    patch_kind: np.ndarray              # (200, 200) int8 패치 종류 번호 (없으면 -1)
    patch_level: np.ndarray             # (200, 200) int8
    boxes: list = field(default_factory=list)       # 메시용 상자 (x0 x1 y0 y1 z0 z1)
    no_floor: np.ndarray | None = None  # 바닥 격자 메시를 뺄 셀
    objects: list = field(default_factory=list)


def _sl(x0, x1, y0, y1):
    a0, a1 = int(round(x0 / RES)), int(round(x1 / RES))
    b0, b1 = int(round(y0 / RES)), int(round(y1 / RES))
    return slice(max(a0, 0), min(a1, N)), slice(max(b0, 0), min(b1, N))


def _patch_cells(room: Room, p: dict, kind_idx: int):
    from foothold_s2.eval import start_sheet as ss
    from foothold_s2.terrains import sparse_terrains as st

    level = int(p["level"])
    t = st.build_tile(p["kind"], level / ss.LEVELS)
    ox, oy = float(p["x"]), float(p["y"])
    sx, sy = _sl(ox, ox + st.TILE[0], oy, oy + st.TILE[1])
    nx, ny = sx.stop - sx.start, sy.stop - sy.start
    xs = ox + (np.arange(nx) + 0.5) * RES
    ys = oy + (np.arange(ny) + 0.5) * RES
    top = np.full((nx, ny), -np.inf)
    for x0, x1, y0, y1, z0, z1 in t.boxes:
        mx = (xs - ox >= x0) & (xs - ox < x1)
        my = (ys - oy >= y0) & (ys - oy < y1)
        blk = np.ix_(mx, my)
        top[blk] = np.maximum(top[blk], z1)
    gx0, gx1 = ss.ZONE_X
    inzone_x = ((xs - ox) >= gx0) & ((xs - ox) < gx1)
    inzone_y = ((ys - oy) >= st.STRIP[0]) & ((ys - oy) < st.STRIP[1])
    zone = inzone_x[:, None] & np.ones(ny, bool)[None]
    foot = top >= -0.1
    cell = np.where(foot, CELL_FLAT, CELL_PIT).astype(np.uint8)
    cell[zone & foot & inzone_y[None]] = CELL_FOOTHOLD
    gapw = np.zeros((nx, ny))
    if p["kind"] == "gaps":
        pit = zone & ~foot & inzone_y[None]
        for j in range(ny):
            run = 0
            for i in range(nx + 1):
                if i < nx and pit[i, j]:
                    run += 1
                elif run:
                    gapw[i - run:i, j] = run * RES
                    run = 0
        cell[pit] = CELL_GAP_PIT
    room.height[sx, sy] = np.where(np.isfinite(top), top, PIT_DROP)
    room.cell[sx, sy] = cell
    room.gap_width[sx, sy] = gapw
    room.patch_kind[sx, sy] = kind_idx
    room.patch_level[sx, sy] = level
    room.no_floor[sx, sy] = True
    for x0, x1, y0, y1, z0, z1 in t.boxes:
        room.boxes.append((ox + x0, ox + x1, oy + y0, oy + y1, z0, z1))
    room.objects.append({"kind": "patch", "patch_kind": p["kind"], "level": level, "x0": ox, "y0": oy, "x1": ox + st.TILE[0], "y1": oy + st.TILE[1]})


def _overhead(room: Room, sl, bottom: float):
    room.clearance[sl] = np.minimum(room.clearance[sl], bottom)
    cur = room.cell[sl]
    room.cell[sl] = np.where((cur == CELL_WALL) | (cur == CELL_LEG), cur, CELL_OVERHEAD)


def build_room(spec: dict) -> Room:
    room = Room(spec, np.zeros((N, N)), np.full((N, N), CELL_FLAT, np.uint8), np.full((N, N), np.inf),
                np.zeros((N, N)), np.full((N, N), -1, np.int8), np.full((N, N), -1, np.int8))
    room.no_floor = np.zeros((N, N), dtype=bool)
    order = {"rough": 0, "stairs": 1, "patch": 2, "gap": 3, "wall": 4, "table": 5, "box": 6}
    bad = [p.get("type") for p in spec["primitives"] if p.get("type") not in order]
    if bad:
        raise ValueError(f"unknown primitive {bad[0]!r}")
    prims = sorted(spec["primitives"], key=lambda p: order[p["type"]])
    for p in prims:
        t = p["type"]
        if t == "rough":
            sl = _sl(p["x0"], p["x1"], p["y0"], p["y1"])
            r = np.random.default_rng(int(p.get("seed", 0)))
            shape = (sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
            room.height[sl] = r.uniform(-0.03, 0.03, shape)
            room.cell[sl] = CELL_ROUGH
        elif t == "stairs":
            sl = _sl(p["x"], p["x"] + TILE_M, p["y"], p["y"] + TILE_M)
            steps = np.interp(np.arange(TILE), [0, 4, 8, 11, 15, 19], [0, 1, 2, 2, 1, 0]).round()
            room.height[sl] = (steps * float(p.get("step_m", 0.15)))[:, None]
            room.cell[sl] = CELL_STAIRS
        elif t == "patch":
            _patch_cells(room, p, PATCH_KINDS.index(p["kind"]))
        elif t == "gap":
            sl = _sl(p["x0"], p["x1"], p["y0"], p["y1"])
            room.height[sl] = PIT_DROP
            room.cell[sl] = CELL_GAP_PIT
            room.gap_width[sl] = float(p["x1"]) - float(p["x0"])
            room.no_floor[sl] = True
            room.boxes.append((p["x0"], p["x1"], p["y0"], p["y1"], PIT_DROP - 0.2, PIT_DROP))
            room.objects.append({"kind": "gap", "x0": p["x0"], "y0": p["y0"], "x1": p["x1"], "y1": p["y1"]})
        elif t == "wall":
            sl = _sl(p["x0"], p["x1"], p["y0"], p["y1"])
            room.cell[sl] = CELL_WALL
            room.boxes.append((p["x0"], p["x1"], p["y0"], p["y1"], 0.0, float(p["h"])))
            room.objects.append({"kind": "wall", "x0": p["x0"], "y0": p["y0"], "x1": p["x1"], "y1": p["y1"], "z0": 0.0, "z1": float(p["h"])})
        elif t == "table":
            x, y, w, top = float(p["x"]), float(p["y"]), float(p["w"]), float(p["top"])
            sl = _sl(x, x + w, y, y + w)
            _overhead(room, sl, top - 0.05)
            for lx in (x, x + w - 0.1):
                for ly in (y, y + w - 0.1):
                    lsl = _sl(lx, lx + 0.1, ly, ly + 0.1)
                    room.cell[lsl] = CELL_LEG
                    room.boxes.append((lx, lx + 0.1, ly, ly + 0.1, 0.0, top - 0.05))
            room.boxes.append((x, x + w, y, y + w, top - 0.05, top))
            room.objects.append({"kind": "table", "x0": x, "y0": y, "x1": x + w, "y1": y + w, "z0": top - 0.05, "z1": top})
        elif t == "box":
            x, y, w, z0, h = float(p["x"]), float(p["y"]), float(p["w"]), float(p["z0"]), float(p["h"])
            _overhead(room, _sl(x, x + w, y, y + w), z0)
            room.boxes.append((x, x + w, y, y + w, z0, z0 + h))
            room.objects.append({"kind": "box", "x0": x, "y0": y, "x1": x + w, "y1": y + w, "z0": z0, "z1": z0 + h})
        else:
            raise ValueError(f"unknown primitive {t!r}")
    ow = float(spec.get("outer_wall_m", OUTER_WALL_M))
    k = int(round(ow / RES))
    for sl in ((slice(0, k), slice(None)), (slice(N - k, N), slice(None)), (slice(None), slice(0, k)), (slice(None), slice(N - k, N))):
        room.cell[sl] = CELL_WALL
    for x0, x1, y0, y1 in ((0, ow, 0, ROOM_M), (ROOM_M - ow, ROOM_M, 0, ROOM_M),
                           (0, ROOM_M, 0, ow), (0, ROOM_M, ROOM_M - ow, ROOM_M)):
        room.boxes.append((x0, x1, y0, y1, 0.0, 2.0))
    return room


# ---------------------------------------------------------------- 메시


def _box_mesh(b):
    x0, x1, y0, y1, z0, z1 = b
    v = np.array([[x, y, z] for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)], dtype=np.float64)
    f = np.array([[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4], [2, 6, 3], [3, 6, 7], [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5]])
    return v, f


def room_mesh(room: Room) -> tuple:
    """(vertices float32 (V,3), faces int32 (F,3)). 바닥 높이 격자 (no_floor 셀 제외) + 상자들."""
    h = room.height
    gx, gy = np.meshgrid(np.arange(N + 1) * RES, np.arange(N + 1) * RES, indexing="ij")
    pad = np.pad(h, ((0, 1), (0, 1)), mode="edge")
    corner_z = pad.copy()
    verts = [np.stack([gx.ravel(), gy.ravel(), corner_z.ravel()], 1)]
    idx = np.arange((N + 1) * (N + 1)).reshape(N + 1, N + 1)
    keep = ~room.no_floor
    a, b, c, d = idx[:-1, :-1][keep], idx[1:, :-1][keep], idx[:-1, 1:][keep], idx[1:, 1:][keep]
    faces = [np.concatenate([np.stack([a, b, c], 1), np.stack([b, d, c], 1)])]
    base = (N + 1) * (N + 1)
    for bx in room.boxes:
        v, f = _box_mesh(bx)
        verts.append(v)
        faces.append(f + base)
        base += len(v)
    return np.concatenate(verts).astype(np.float32), np.concatenate(faces).astype(np.int32)


def mesh_sha256(vertices: np.ndarray, faces: np.ndarray) -> str:
    """`ex42_mesh_mount.load_combined_mesh` 와 같은 정의."""
    return hashlib.sha256(vertices.astype(np.float32).tobytes() + faces.astype(np.int32).tobytes()).hexdigest()


START_MARGIN_M = 0.8                  # 시작점은 평지 셀이고 벽 · 장애물 · 구덩이 · 방 가장자리에서 이만큼 떨어진 곳 (planner F2 · 11/16 23:40: 열 reset 의 xy 흔들기 ±0.5 m 네모의 모서리 0.71 m 도 평지 안에 들어오게 0.5 -> 0.8)
ROOM_GAP_M = 2.0                      # 한 메시의 방 사이 빈 공간. 방 폭 20 m 에 2 m 여유를 둔다.


def start_points(room: Room, k: int, seed: int = 0, margin: float = START_MARGIN_M) -> np.ndarray:
    """방 하나의 시작점 k 개 (방 틀 x y z, z = 바닥 높이). 큰 통과 영역 안의 평지 셀에서 시드 고정으로 겹치지 않게 뽑는다."""
    from scipy import ndimage

    if k < 1:
        raise ValueError("k must be >= 1")
    flat = np.pad(room.cell == CELL_FLAT, 1, constant_values=False)
    clear = (ndimage.distance_transform_edt(flat)[1:-1, 1:-1] * RES) >= margin
    lab, n = ndimage.label(room.cell != CELL_WALL)
    if n == 0:
        raise ValueError("room has no passable cell")
    big = lab == (1 + int(np.argmax(np.bincount(lab.ravel())[1:])))
    ok = np.argwhere(clear & big)
    if len(ok) < k:
        raise ValueError(f"only {len(ok)} start cells have {margin} m of flat clearance, {k} wanted")
    pick = ok[np.random.default_rng(seed).choice(len(ok), size=k, replace=False)]
    return np.array([[(i + 0.5) * RES, (j + 0.5) * RES, float(room.height[i, j])] for i, j in pick])      # 배열은 [x 칸][y 칸] (build_room · room_mesh 와 같다). 옛 판은 x · y 가 뒤바뀌어 있었다 (11/17 22:5x 발견)


def write_room(room: Room, out_dir, n_starts: int = 0, start_seed: int = 0) -> dict:
    """`terrain_mesh.npz` (vertices · faces · origins · column_family) + `room_manifest.json`. manifest 를 돌려준다.
    n_starts = 0: origins (1, 1, 3) 방 가운데 (옛 꼴). n_starts = K: origins (1, K, 3) = `start_points` 의 K 개 (column_family 는 \"room\" K 번)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    v, f = room_mesh(room)
    if n_starts:
        starts = start_points(room, n_starts, start_seed)
        origins = starts[None, :, :]
    else:
        starts = None
        origins = np.array([[[ROOM_M / 2, ROOM_M / 2, 0.0]]])
    npz = out / "terrain_mesh.npz"
    np.savez_compressed(npz, vertices=v, faces=f, origins=origins, column_family=np.array(["room"] * origins.shape[1]))
    sha = mesh_sha256(v, f)
    manifest = {"format": "hipan-room/1", "seed": room.spec.get("seed"), "mesh_sha256": sha,
                "vertices": int(len(v)), "faces": int(len(f)), "size_m": ROOM_M, "res_m": RES,
                "tiles": room.spec.get("tiles"), "patches": [o for o in room.objects if o["kind"] == "patch"],
                "primitives": room.spec["primitives"],
                "starts": None if starts is None else {"seed": int(start_seed), "margin_m": START_MARGIN_M, "xyz": starts.round(4).tolist()}}
    (out / "room_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return manifest


def write_rooms(rooms, out_dir, n_starts: int = 0, start_seed: int = 0,
                room_gap_m: float = ROOM_GAP_M) -> dict:
    """여러 방을 x 방향 한 메시로 저장한다. origins 의 각 행은 한 방, 열은 그 방 시작점이다."""
    rooms = list(rooms)
    if not rooms:
        raise ValueError("at least one room is required")
    gap = float(room_gap_m)
    if not np.isfinite(gap) or gap <= 0:
        raise ValueError("room_gap_m must be finite and positive")
    if n_starts < 0:
        raise ValueError("n_starts must be >= 0")

    pitch = ROOM_M + gap
    vertices, faces, origin_rows, room_rows = [], [], [], []
    vertex_offset = 0
    for row, room in enumerate(rooms):
        x_offset = row * pitch
        v, f = room_mesh(room)
        v[:, 0] += x_offset
        faces.append(f + vertex_offset)
        vertices.append(v)
        vertex_offset += len(v)

        if n_starts:
            starts = start_points(room, n_starts, seed=int(start_seed) + row)
        else:
            starts = np.array([[ROOM_M / 2, ROOM_M / 2, 0.0]], dtype=np.float64)
        starts[:, 0] += x_offset
        origin_rows.append(starts)
        room_rows.append({
            "row": row,
            "seed": room.spec.get("seed"),
            "x_offset_m": x_offset,
            "mesh_vertices": int(len(v)),
            "mesh_faces": int(len(f)),
            "starts_seed": int(start_seed) + row if n_starts else None,
            "starts_local_xyz": (starts - np.array([x_offset, 0.0, 0.0])).round(4).tolist(),
            "patches": [o for o in room.objects if o["kind"] == "patch"],
            "primitives": room.spec["primitives"],
        })

    v = np.concatenate(vertices).astype(np.float32, copy=False)
    f = np.concatenate(faces).astype(np.int32, copy=False)
    origins = np.stack(origin_rows).astype(np.float64, copy=False)
    sha = mesh_sha256(v, f)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "terrain_mesh.npz", vertices=v, faces=f, origins=origins,
                        column_family=np.array(["room"] * origins.shape[1]))
    manifest = {
        "format": "hipan-rooms/1",
        "room_count": len(rooms),
        "size_m": ROOM_M,
        "room_gap_m": gap,
        "room_pitch_m": pitch,
        "origins_shape": list(origins.shape),
        "mesh_sha256": sha,
        "vertices": int(len(v)),
        "faces": int(len(f)),
        "starts": None if not n_starts else {
            "seed": int(start_seed), "margin_m": START_MARGIN_M,
            "points_per_room": int(n_starts),
        },
        "rooms": room_rows,
    }
    (out / "room_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )
    return manifest


STAND_CLEARANCE_M = 0.5               # grade_table_draft.yaml 의 stand_clearance_m (가정 · 몸 높이 + 0.1)


def free_mask(room: Room) -> np.ndarray:
    """생성기가 아는 통과 가능 칸: 벽 · 탁자 다리 · 구덩이 · 틈 · 서서 못 지나는 낮은 머리 위 장애물 아래 (여유 < STAND_CLEARANCE_M) 를 뺀 칸.
    grade_map 의 통과 가능 (자세 스위치 꺼짐) 과 같은 약속이다 (등급표 stand_clearance_m 0.5 와 같은 값 · 다르면 room_check 가 잡는다)."""
    low = (room.cell == CELL_OVERHEAD) & (room.clearance < STAND_CLEARANCE_M)
    return ~(np.isin(room.cell, (CELL_WALL, CELL_LEG, CELL_PIT, CELL_GAP_PIT)) | low)


def passage_width_m(free: np.ndarray, min_cover: float = 0.98, cap_m: float = 1.2) -> float:
    """가장 좁은 통과 폭 m: 반지름 r 인 원이 지나갈 수 있는 길 (벽에서 r 이상 떨어진 칸) 만으로도 통과 가능 칸의 min_cover 이상이 이어져 있는 가장 큰 2r (cap 까지).
    좁은 문틈이 방을 둘로 가르면 r 이 그 틈 반폭 아래에서만 통과한다. 막힌 구석 (막다른 틈) 은 가르지 않으므로 세지 않는다."""
    from scipy import ndimage

    big = _largest_label(free)
    total = int(big.sum())
    if not total:
        return 0.0
    dist = ndimage.distance_transform_edt(big) * RES
    best = 0.0
    for r in np.arange(0.1, cap_m / 2 + 1e-9, 0.05):
        comp = _largest_label(dist >= r)
        if not comp.any():
            break
        covered = (ndimage.distance_transform_edt(~comp) * RES <= r + RES) & big
        if covered.sum() / total >= min_cover:
            best = 2 * float(r)
        else:
            break
    return round(best, 2)


def _largest_label(mask: np.ndarray) -> np.ndarray:
    from scipy import ndimage

    lab, n = ndimage.label(mask)
    return lab == (1 + int(np.argmax(np.bincount(lab.ravel())[1:]))) if n else np.zeros_like(mask)


def room_metrics(room: Room, spec: dict | None = None) -> dict:
    """방 한 개의 수락 값 (maze 설계 3.4 의 방마다 줄): 통과 가능 칸 비율 · 가장 큰 덩어리 비율 · 막다른 타일 · 가장 좁은 통과 폭 · 시작 후보 칸 수."""
    from scipy import ndimage

    spec = spec or room.spec
    free = free_mask(room)
    big = _largest_label(free)
    flat = np.pad(room.cell == CELL_FLAT, 1, constant_values=False)
    clear = (ndimage.distance_transform_edt(flat)[1:-1, 1:-1] * RES) >= START_MARGIN_M
    return {"free_frac": float(free.mean()), "connected_frac": float(big.sum() / max(free.sum(), 1)), "dead_end_tiles": dead_end_tiles(spec),
            "passage_m": passage_width_m(free), "start_cells": int((clear & big).sum())}


MIN_START_CELLS = 200                 # 시작점 64 개를 겹침 없이 뽑을 여유 (수락 조건)


def accepts(m: dict, cfg: RoomConfig) -> bool:
    """방마다 수락 조건 (설계 3.4 의 방마다 줄)."""
    lo, hi = cfg.free_range
    return (lo <= m["free_frac"] <= hi and m["connected_frac"] >= cfg.min_connected and m["dead_end_tiles"] >= cfg.min_dead_end_tiles
            and m["passage_m"] >= cfg.min_passage_m and m["start_cells"] >= MIN_START_CELLS)


def make_room(seed: int, cfg: RoomConfig | None = None, grade_table: dict | None = None):
    """수락 조건을 만족할 때까지 시드 흐름에서 다시 뽑음. 돌려주는 값: (spec, room).
    maze 방: wall_keep 은 시드가 keep_choices 를 돌려가며 고르고 (시드 % 3), 수락은 방마다 줄 (통과 가능 칸 · 이어짐 · 막다른 타일 · 통과 폭 · 시작 후보). spec[\"metrics\"] 에 값을 남긴다.
    old 방 · 패치가 든 maze 방: 가장 큰 덩어리가 min_free_fraction 이상이면 수락 (옛 조건, spec["metrics"] 없음)."""
    import dataclasses

    cfg = cfg or RoomConfig()
    maze = cfg.layout == "maze"
    if maze and cfg.keep_choices:
        cfg = dataclasses.replace(cfg, wall_keep=float(cfg.keep_choices[int(seed) % len(cfg.keep_choices)]))
    rng = np.random.default_rng(seed)
    for tries in range(1, cfg.max_tries + 1):
        spec = generate_spec(int(rng.integers(0, 2**31)) if tries > 1 else seed, cfg, grade_table)
        spec["seed"], spec["tries"] = int(seed), tries
        room = build_room(spec)
        if maze and not any(q.get("type") == "patch" for q in spec["primitives"]):
            m = room_metrics(room, spec)
            if accepts(m, cfg):
                spec["metrics"] = {k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()}
                return spec, room
            continue
        # 옛 꼴 · 듬성한 패치가 든 방 (구덩이 · 징검돌이 통과 가능 칸 · 이어짐 · 통과 폭 줄을 건드린다. 이어짐은 건너뛰기 간선이 잇는다 = 계획기 몫): 옛 조건
        passable = room.cell != CELL_WALL
        if _largest_component(passable) / passable.size >= cfg.min_free_fraction:
            return spec, room
    raise RuntimeError("no room met the acceptance conditions")


def _largest_component(mask: np.ndarray) -> int:
    from scipy import ndimage

    lab, n = ndimage.label(mask)
    return int(np.bincount(lab.ravel())[1:].max()) if n else 0
