"""징검돌 낮은 열의 쉬운 사다리 (줄 0~9) 시험 메시 (학습 · 평가 메시 아님 · Isaac 없음 · 옛 폴더는 읽기만).

    python -m foothold_s2.scripts.ex42_stone_gap_test_mesh --src <합친 메시 폴더> --dst <새 폴더>

합친 메시의 징검돌 낮은 열 (family A 의 stepping_stones_low 열 전부) 의 줄 0~9 칸을 지우고 같은 자리에 새 칸을 넣는다.
새 칸 = start_go2_v2.build_tile 그대로 (set_easy_stone_low(True): 틈 x 표 EASY_STONE_LOW_GAP_X · 돌 높이 흔들림 +-2 cm).
줄 0~4 는 레벨 0 돌 크기 · 틈 y 로 틈 x 만 커진다. 줄 5 = 옛 L0, 줄 6~9 = 옛 L1~L4 (옛 L5~L9 는 이 열에서 빠짐).
같은 생성기를 꺼 둔 채 (옛 값) 다시 만든 칸이 옛 메시의 칸과 일치하는지 (돌 위치 xy) 줄마다 확인해 보고한다.
다른 열 · 다른 가족은 바이트 그대로 (정점 순서만 바뀜: 바뀐 칸을 맨 뒤로 붙임).
깃발은 새 칸에서 ex42_flag_producer.tile_flags 로 다시 구하고, 가장자리 마스크는 합친 메시에서 다시 만든다.
줄별 실측 (틈 x · 돌 크기 · 높이 흔들림) 은 만든 메시를 다시 읽어 잰다 (stone_gap_levels.json).
mesh_sha256 은 바뀐다 (학습에 넣는 판이 아님: M0~M3 영수증은 이 폴더를 가리키지 않는다).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

from foothold_s2.terrains import columns
from foothold_s2.terrains import ex42_edge_masks as em
from foothold_s2.terrains import ex42_flag_producer as fp
from foothold_s2.terrains import sparse_terrains as legacy
from foothold_s2.terrains import start_go2_v2 as v2

TILE = legacy.TILE
ROWS_CHANGED = tuple(range(10))
KIND = "stepping_stones_low"
TOL = 1e-4


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _box_mesh(x0, x1, y0, y1, z0, z1):
    """trimesh.creation.box 와 같은 8 정점 · 12 면 (정점 순서는 달라도 됨: 면 법선 바깥)."""
    v = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)], dtype=np.float64)
    f = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]], dtype=np.int64)
    return v, f


def components(faces: np.ndarray, n: int):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    a = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]]); b = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]])
    return connected_components(coo_matrix((np.ones(len(a), np.int8), (a, b)), shape=(n, n)), directed=False)[1]


def tile_boxes_world(vertices, faces, labels, rows, cols, rows_total, cols_total, wanted):
    """wanted = [(row, col)] 칸의 상자 (연결 성분 하나 = 상자 하나): {(row, col): [(label, x0, x1, y0, y1, z0, z1), ...]}."""
    lo = np.array([tile_corner(r, c, rows_total, cols_total) for r, c in wanted])
    xmin, ymin = lo.min(0); xmax, ymax = lo[:, 0].max() + TILE[0], lo[:, 1].max() + TILE[1]
    inreg = (vertices[:, 0] >= xmin - TOL) & (vertices[:, 0] <= xmax + TOL) & (vertices[:, 1] >= ymin - TOL) & (vertices[:, 1] <= ymax + TOL)
    cand = np.unique(labels[inreg])
    out = {w: [] for w in wanted}
    order = np.argsort(labels, kind="stable"); sl = labels[order]
    for lab in cand:
        a, b = np.searchsorted(sl, [lab, lab + 1]); pts = vertices[order[a:b]].astype(np.float64)
        mn, mx = pts.min(0), pts.max(0)
        if mn[0] < xmin - TOL or mx[0] > xmax + TOL or mn[1] < ymin - TOL or mx[1] > ymax + TOL:
            continue                                                        # 영역 밖으로 걸친 성분 (옆 칸 · 다른 형태) 은 건드리지 않음
        cx, cy = (mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2
        for (r, c), (x0, y0) in zip(wanted, lo):
            if x0 <= cx < x0 + TILE[0] and y0 <= cy < y0 + TILE[1]:
                out[(r, c)].append((int(lab), mn[0], mx[0], mn[1], mx[1], mn[2], mx[2]))
    return out


def tile_corner(row, col, rows, cols):
    return em.tile_corner(row, col, rows, cols)


def new_tile_boxes(row: int, easy: bool, depth: float, seed_key: str):
    """칸 좌표 (0..8) 상자 (N, 6): 틀 3 개 + 돌. start_go2_v2.generate (옛 메시를 만든 같은 생성기) 를 레벨 = 줄 · 무작위 0 으로 부르고
    build_tile 과 같은 이음 (띠 y + STRIP) 을 붙인다. 구덩이 깊이는 옛 칸의 값으로 고정 (옛 메시는 칸마다 깊이 · 높이 난수가 다르다).
    easy=True 는 생성기의 쉬운 사다리 인자 (v2.easy_stone_low_args: 줄 0~4 틈 x 표 · 줄 5 = 옛 L0 · 줄 6~9 = 옛 L1~L4) 를 넘긴다. easy=False 는 옛 값 (레벨 = 줄)."""
    rng = np.random.default_rng(legacy.seed_of(seed_key, 0.0))
    saved = v2.DEPTH_RANGE
    v2.DEPTH_RANGE = (depth, depth)
    try:
        geom = v2.generate("stepping_stones", **(v2.easy_stone_low_args(row) if easy else {"level": row}), rng=rng, randomness=0.0)
    finally:
        v2.DEPTH_RANGE = saved
    assert abs(geom.depth - depth) < 1e-12
    shifted = [(x0, x1, y0 + legacy.STRIP[0], y1 + legacy.STRIP[0], z0, z1) for x0, x1, y0, y1, z0, z1 in geom.boxes[3:]]
    return np.asarray(legacy._frame(geom.depth) + shifted, dtype=float)


def measure_tile(stones, x0t, y0t):
    """메시에서 읽은 돌 상자 [(label, x0, x1, y0, y1, z0, z1)] 로 틈 x · 돌 크기 · 높이 흔들림 (윗면 z - PLATFORM_Z) 을 잰다."""
    b = np.array([[s[1] - x0t, s[2] - x0t, s[3] - y0t, s[4] - y0t, s[6]] for s in stones])
    xs = np.unique(np.round(b[:, 0], 4)); ys = np.unique(np.round(b[:, 2], 4))
    sx, sy = float(np.median(b[:, 1] - b[:, 0])), float(np.median(b[:, 3] - b[:, 2]))
    tops = b[:, 4] - v2.PLATFORM_Z
    return {"stones": int(len(b)), "stone_x_m": round(sx, 4), "stone_y_m": round(sy, 4),
            "gap_x_m": round(float(np.median(np.diff(xs) - sx)), 4), "gap_y_m": round(float(np.median(np.diff(ys) - sy)), 4),
            "height_jitter_max_abs_m": round(float(np.abs(tops).max()), 4), "height_jitter_std_m": round(float(tops.std()), 4)}


def build(src: Path, dst: Path) -> dict:
    if dst.exists() and any(dst.iterdir()):
        raise SystemExit(f"destination is not empty: {dst}")
    data = np.load(src / "terrain_mesh.npz", allow_pickle=False)
    arrays = {k: data[k] for k in data.files}
    vertices, faces, origins = arrays["vertices"], arrays["faces"], arrays["origins"]
    rows_total, cols_total = origins.shape[:2]
    fam = [str(v) for v in arrays["column_family"]]
    nA = sum(1 for f in fam if f == "A")
    names = columns.column_types(columns.FULL, nA)
    stone_cols = [c for c in range(nA) if names[c] == KIND]
    if len(v2.EASY_STONE_LOW_GAP_X) + 5 != len(ROWS_CHANGED):
        raise SystemExit("the generator's ladder (%d easy rows + old L0..L4) does not fill rows %s" % (len(v2.EASY_STONE_LOW_GAP_X), ROWS_CHANGED))
    wanted = [(r, c) for c in stone_cols for r in ROWS_CHANGED]
    labels = components(faces, len(vertices))
    old = tile_boxes_world(vertices, faces, labels, rows_total, cols_total, rows_total, nA, wanted)
    # 옛 칸 상자: 틀 3 개 (칸 폭 전체) + 돌. 옛 값 읽기: 구덩이 깊이 · 돌 위치 (검증)
    drop_labels, new_v, new_f, report, flag_edit = [], [], [], [], {}
    base = 0
    for (r, c) in wanted:
        boxes = old[(r, c)]
        x0t, y0t = tile_corner(r, c, rows_total, nA)
        frame = [b for b in boxes if b[4] - b[3] > TILE[1] - 1e-3]          # y 폭 8 m = 틀 상자
        stones = [b for b in boxes if b[4] - b[3] <= TILE[1] - 1e-3]
        if len(frame) != 3 or not stones:
            raise SystemExit(f"tile ({r},{c}): unexpected box layout frame={len(frame)} stones={len(stones)}")
        floor = max(frame, key=lambda b: (b[2] - b[1]))                     # x 폭이 가장 큰 틀 (구덩이 바닥) = x 1..7
        depth = -float(floor[6])
        # 검증: 쉬운 줄을 끈 같은 생성기로 다시 만든 칸의 돌 위치 (xy) = 옛 메시의 칸 (높이 난수만 다름)
        ck = new_tile_boxes(r, False, depth, f"check|{r}|{c}")[3:]
        os_ = np.array([[b[1] - x0t, b[2] - x0t, b[3] - y0t, b[4] - y0t] for b in stones]); os_ = os_[np.lexsort((os_[:, 2], os_[:, 0]))]
        nk = ck[:, :4][np.lexsort((ck[:, 2], ck[:, 0]))]
        same = len(os_) == len(nk) and bool(np.abs(os_ - nk).max() < 1e-3)
        nb = new_tile_boxes(r, True, depth, f"{KIND}|easy|{r}|{c}")
        for b in boxes:
            drop_labels.append(b[0])
        for x0, x1, y0, y1, z0, z1 in nb:
            v, f = _box_mesh(x0 + x0t, x1 + x0t, y0 + y0t, y1 + y0t, z0, z1)
            new_v.append(v); new_f.append(f + base); base += 8
        tri_local = np.concatenate([_box_mesh(*b)[0][_box_mesh(*b)[1]] for b in nb])
        report.append({"row": r, "col": c, "depth_m": round(depth, 4), "old_stones": len(stones), "new_stones": len(nb) - 3,
                       "old_xy_reproduced_with_easy_off": same, "old_measured": measure_tile(stones, x0t, y0t)})
        flag_edit[(r, c)] = (nb, depth)
    drop = np.isin(labels, np.array(drop_labels))
    keep_v = ~drop
    remap = np.cumsum(keep_v) - 1
    keep_f = keep_v[faces].all(axis=1)
    if (keep_v[faces].any(axis=1) & ~keep_f).any():
        raise SystemExit("a removed box shares a face with a kept one")
    out_v = np.concatenate([vertices[keep_v], np.concatenate(new_v).astype(np.float32)])
    nkeep = int(keep_v.sum())
    out_f = np.concatenate([remap[faces[keep_f]], np.concatenate(new_f) + nkeep]).astype(np.int32)
    # 깃발: 바뀐 칸만 tile_flags 로 다시
    flags = arrays["flags"].copy()
    size = np.asarray(TILE)
    tri_all = out_v.astype(np.float64)[out_f]
    cen = tri_all[:, :, :2].mean(1)
    for (r, c) in wanted:
        x0t, y0t = tile_corner(r, c, rows_total, nA)
        pick = (cen[:, 0] >= x0t) & (cen[:, 0] < x0t + TILE[0]) & (cen[:, 1] >= y0t) & (cen[:, 1] < y0t + TILE[1])
        off = np.array([x0t, y0t, 0.0])
        xy, _meta = fp.tile_flags("A", KIND, tri_all[pick] - off, origins[r, c] - off, size)
        flags[r, c] = xy + off[:2]
    built = em.build_edge_masks(out_v, out_f, origins, fam)
    packed = em.pack_masks(built)
    new_arrays = {**arrays, "vertices": out_v, "faces": out_f, "flags": flags, **packed}
    # 줄별 실측: 만든 메시를 다시 읽어 (옛 값 = 같은 칸의 옛 메시에서 잰 값)
    labels2 = components(out_f, len(out_v))
    new_meas = tile_boxes_world(out_v, out_f, labels2, rows_total, cols_total, rows_total, nA, wanted)
    for t in report:
        x0t, y0t = tile_corner(t["row"], t["col"], rows_total, nA)
        st = [b for b in new_meas[(t["row"], t["col"])] if b[4] - b[3] <= TILE[1] - 1e-3]
        t["new_measured"] = measure_tile(st, x0t, y0t)
    dst.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst / "terrain_mesh.npz", **new_arrays)
    shutil.copy2(src / "terrain_manifest.json", dst / "terrain_manifest.json")
    manifest = json.loads((src / "mesh_manifest.json").read_text(encoding="utf-8-sig"))
    manifest["mesh_sha256"] = hashlib.sha256(out_v.tobytes() + out_f.tobytes()).hexdigest()
    manifest["vertex_count"], manifest["face_count"] = int(len(out_v)), int(len(out_f))
    manifest["mesh_file_sha256"] = _digest(dst / "terrain_mesh.npz")
    manifest["edge_masks"] = {**manifest.get("edge_masks", {}), "sha256": em.masks_sha256(packed), "inner_cells": int(built["inner"].sum()), "outer_cells": int(built["outer"].sum())}
    manifest["stone_gap_test_mesh"] = {"NOT_FOR_TRAINING": True, "source_mesh_dir": str(src), "source_geometry_sha256": json.loads((src / "mesh_manifest.json").read_text(encoding="utf-8-sig")).get("mesh_sha256"),
                                       "kind": KIND, "columns": stone_cols, "rows": list(ROWS_CHANGED),
                                       "easy_gap_x_m_by_row": {str(k): v for k, v in v2.EASY_STONE_LOW_GAP_X.items()},
                                       "row_map": {str(r): ("easy" if r in v2.EASY_STONE_LOW_GAP_X else "old level %d" % (r - v2.EASY_STONE_LOW_SHIFT)) for r in ROWS_CHANGED},
                                       "easy_height_jitter_m": v2.EASY_STONE_LOW_HEIGHT_JITTER, "tiles": report}
    (dst / "mesh_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (dst / "stone_gap_levels.json").write_text(json.dumps(manifest["stone_gap_test_mesh"], indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest["stone_gap_test_mesh"] | {"mesh_sha256": manifest["mesh_sha256"], "mesh_file_sha256": manifest["mesh_file_sha256"], "vertices": len(out_v), "faces": len(out_f)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--dst", required=True)
    a = ap.parse_args()
    res = build(Path(a.src), Path(a.dst))
    print(json.dumps({k: v for k, v in res.items() if k != "tiles"}, indent=1))
    print("tiles", len(res["tiles"]), "old xy reproduced with easy off", sum(t["old_xy_reproduced_with_easy_off"] for t in res["tiles"]))
