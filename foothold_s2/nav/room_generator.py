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
OUTER_WALL_M = 0.2
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
    max_tries: int = 50


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
    """시드 -> 방 명세 (yaml 로 적을 수 있음). grade_table: `{kind: {max_passed_level: int}}` (없으면 패치를 넣지 않음)."""
    cfg = cfg or RoomConfig()
    rng = np.random.default_rng(seed)
    tiles = wfc_tiles(rng, cfg.weights)
    prims: list = []
    taken = np.zeros((NT, NT), dtype=bool)
    kinds = [k for k in PATCH_KINDS if grade_table and grade_table.get(k, {}).get("max_passed_level", -1) >= 0]
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
    k = int(round(OUTER_WALL_M / RES))
    for sl in ((slice(0, k), slice(None)), (slice(N - k, N), slice(None)), (slice(None), slice(0, k)), (slice(None), slice(N - k, N))):
        room.cell[sl] = CELL_WALL
    for x0, x1, y0, y1 in ((0, OUTER_WALL_M, 0, ROOM_M), (ROOM_M - OUTER_WALL_M, ROOM_M, 0, ROOM_M),
                           (0, ROOM_M, 0, OUTER_WALL_M), (0, ROOM_M, ROOM_M - OUTER_WALL_M, ROOM_M)):
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


def write_room(room: Room, out_dir) -> dict:
    """`terrain_mesh.npz` (vertices · faces · origins · column_family) + `room_manifest.json`. manifest 를 돌려준다."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    v, f = room_mesh(room)
    origins = np.array([[[ROOM_M / 2, ROOM_M / 2, 0.0]]])
    npz = out / "terrain_mesh.npz"
    np.savez_compressed(npz, vertices=v, faces=f, origins=origins, column_family=np.array(["room"]))
    sha = mesh_sha256(v, f)
    manifest = {"format": "hipan-room/1", "seed": room.spec.get("seed"), "mesh_sha256": sha,
                "vertices": int(len(v)), "faces": int(len(f)), "size_m": ROOM_M, "res_m": RES,
                "tiles": room.spec.get("tiles"), "patches": [o for o in room.objects if o["kind"] == "patch"],
                "primitives": room.spec["primitives"]}
    (out / "room_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return manifest


def make_room(seed: int, cfg: RoomConfig | None = None, grade_table: dict | None = None):
    """연결 크기 조건을 만족할 때까지 시드 흐름에서 다시 뽑음. 돌려주는 값: (spec, room)."""
    cfg = cfg or RoomConfig()
    rng = np.random.default_rng(seed)
    for tries in range(1, cfg.max_tries + 1):
        spec = generate_spec(int(rng.integers(0, 2**31)) if tries > 1 else seed, cfg, grade_table)
        spec["seed"], spec["tries"] = int(seed), tries
        room = build_room(spec)
        passable = room.cell != CELL_WALL
        if _largest_component(passable) / passable.size >= cfg.min_free_fraction:
            return spec, room
    raise RuntimeError("no room met min_free_fraction")


def _largest_component(mask: np.ndarray) -> int:
    from scipy import ndimage

    lab, n = ndimage.label(mask)
    return int(np.bincount(lab.ravel())[1:].max()) if n else 0
