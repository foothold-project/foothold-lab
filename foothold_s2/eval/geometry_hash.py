"""듬성 칸 기하 재현 확인 (SONNET-X26n). 같은 칸 해시(레벨, 열)여도 징검돌 위치 · 빔 폭은 생성기 seed 와 줄 안 난이도 무작위에 달렸다.

Isaac `terrain_generator.py` 는 seed 가 None 이면 numpy 전역 상태에서 seed 를 뽑고(144 행), 줄 안 난이도 = (줄 + np_rng.uniform()) / 줄 수(261 행),
듬성 칸 기하는 (종류, 난이도) 해시로 정해진다(sparse_terrains.seed_of). 그래서 평가는 생성기 seed 를 SPARSE_GEOMETRY_SEED 로 고정하고,
실제 만들어진 칸의 상자 배열(메시의 입력 = 높이장의 원천)을 sha256 으로 남겨 모델끼리 같은 기하에서 비교했는지 확인한다.
순수 numpy. Kit 이 만든 SIDE_TABLE(모듈 전역)을 읽는다.
"""

from __future__ import annotations

import hashlib

import numpy as np

from foothold_s2.terrains import sparse_terrains as sp

SPARSE_GEOMETRY_SEED = 20261026


def tiles_by_cell(side_table, names_by_col, num_rows) -> dict:
    """SIDE_TABLE 에 생성기가 호출된 순서대로 쌓인 (종류, 난이도) 를 Isaac 열 우선 · 줄 순서로 (줄, 열) 칸에 묶고 TileData 를 돌려준다(SideTable.bind_all 과 같은 규칙, 모자라거나 레벨이 어긋나면 오류)."""
    queue = {}

    for kind, d in side_table.calls:
        queue.setdefault(kind, []).append(d)
    taken = {k: 0 for k in queue}
    out = {}

    for col, kind in enumerate(names_by_col):
        if kind not in sp.KINDS:
            continue

        for row in range(num_rows):
            i, seq = taken.get(kind, 0), queue.get(kind, [])

            if i >= len(seq):
                raise RuntimeError("%s 가 %d 번만 불렸는데 (줄 %d, 열 %d) 칸이 더 있다" % (kind, len(seq), row, col))
            d = seq[i]
            taken[kind] = i + 1

            if sp.level_of(d) != row:
                raise RuntimeError("호출 순서 가정이 깨졌다: %s 난이도 %.3f 는 레벨 %d, 칸 줄 %d" % (kind, d, sp.level_of(d), row))
            tile = side_table.by_key.get(side_table.key(kind, d))

            if tile is None:
                raise RuntimeError("%s 난이도 %.6f 의 칸이 기록에 없다" % (kind, d))
            out[(row, col)] = tile

    return out


def tile_sha256(tile, kind: str, level: int, col: int) -> str:
    h = hashlib.sha256()
    h.update(("%s|%d|%d|" % (kind, level, col)).encode())
    h.update(np.ascontiguousarray(tile.boxes, dtype=np.float64).tobytes())
    h.update(np.ascontiguousarray(tile.origin, dtype=np.float64).tobytes())

    return h.hexdigest()


SUPPORT_TOL_M = 0.05                 # 시작 점의 칸 윗면 높이가 출발 단 윗면에서 이 안이면 «발판 위»


def start_support(side_table, names_by_col, num_rows, tiles, start_xy_rel) -> np.ndarray:
    """env 별 시작 위치(칸 원점 기준 xy, spawn 은 칸 좌표 SPAWN_XY)가 칸의 발판 위(윗면 높이 >= 출발 단 윗면 - SUPPORT_TOL_M)인지 (n,) bool. 빔 밖 · 구덩이 위 시작은 False. 칸 기하는 SIDE_TABLE 에서 읽는다."""
    cells = tiles_by_cell(side_table, names_by_col, num_rows)
    top = float(sp._frame.__defaults__[0])
    out, grids = [], {}

    for t, rel in zip(tiles, np.asarray(start_xy_rel, dtype=float)):
        key = (int(t["level"]), int(t["col"]))

        if key not in grids:
            grids[key] = sp.height_grid(cells[key].boxes)
        x, y = sp.SPAWN_XY[0] + rel[0], sp.SPAWN_XY[1] + rel[1]
        i, j = int(np.clip(x / sp.MASK_RES, 0, grids[key].shape[0] - 1)), int(np.clip(y / sp.MASK_RES, 0, grids[key].shape[1] - 1))
        out.append(grids[key][i, j] >= top - SUPPORT_TOL_M)

    return np.asarray(out, dtype=bool)


def geometry_record(side_table, names_by_col, num_rows, used_cells, seed=SPARSE_GEOMETRY_SEED) -> dict:
    """used_cells: [(레벨, 열)] 평가가 쓰는 칸. 열별(칸별) 해시와 전체 해시."""
    cells = tiles_by_cell(side_table, names_by_col, num_rows)
    per = {}

    for lv, col in sorted(set(used_cells)):
        tile = cells[(lv, col)]
        per["L%dc%d" % (lv, col)] = tile_sha256(tile, names_by_col[col], lv, col)
    total = hashlib.sha256("|".join("%s=%s" % kv for kv in sorted(per.items())).encode()).hexdigest()

    return {"seed": seed, "basis": "칸 상자 배열(메시 입력) + 원점 sha256, 칸별 L<레벨>c<열>", "per_cell": per, "total": total}
