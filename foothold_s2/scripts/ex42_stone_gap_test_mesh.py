"""징검돌 낮은 열의 틈 x 를 바꾼 CPU 측정용 시험 메시 (학습 · 평가 메시 아님 · Isaac 없음 · 옛 폴더는 읽기만).

    python -m foothold_s2.scripts.ex42_stone_gap_test_mesh --src <합친 메시 폴더> --dst <새 폴더> [--gaps 0.05,0.10,0.14]

합친 메시의 징검돌 낮은 열 (family A 의 stepping_stones_low 열 전부) 의 줄 0 · 1 · 2 칸을 지우고 같은 자리에 새 칸을 넣는다.
새 칸 = start_go2_v2 의 징검돌 생성기 그대로 (레벨 0 · 무작위 0) 에서 돌 크기 · 틈 y · 구덩이 깊이 (옛 칸의 값을 그대로 읽어 씀) 는 옛 것과 같고
틈 x 만 줄별로 --gaps 의 값 (m, 줄 0 · 1 · 2 순서) 으로 바꾼다. 줄 3 이상 · 다른 열 · 다른 가족은 바이트 그대로 (정점 순서만 바뀜: 바뀐 칸을 맨 뒤로 붙임).
깃발 (flags) 은 새 칸에서 ex42_flag_producer.tile_flags 로 다시 구하고, 가장자리 마스크 (edge_*) 는 합친 메시에서 다시 만든다.
mesh_sha256 은 바뀐다 (학습에 넣는 판이 아님: M0~M3 영수증 · plan 의 프로파일은 이 폴더를 가리키지 않는다).
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
ROWS_CHANGED = (0, 1, 2)
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


def new_tile_boxes(depth: float, gap_x: float, seed_key: str):
    """칸 좌표 (0..8) 상자 (N, 6): 틀 3 개 (옛 칸과 같음) + 새 징검돌. start_go2_v2.build_tile 과 같은 이음 (띠 y + 2)."""
    rng = np.random.default_rng(legacy.seed_of(seed_key, 0.0))
    saved = (v2.DEPTH_RANGE, v2.STONE_GAP_X)
    v2.DEPTH_RANGE, v2.STONE_GAP_X = (depth, depth), (gap_x, gap_x)
    try:
        geom = v2.generate("stepping_stones", 0, rng, randomness=0.0)
    finally:
        v2.DEPTH_RANGE, v2.STONE_GAP_X = saved
    assert abs(geom.depth - depth) < 1e-12
    shifted = [(x0, x1, y0 + legacy.STRIP[0], y1 + legacy.STRIP[0], z0, z1) for x0, x1, y0, y1, z0, z1 in geom.boxes[3:]]
    return np.asarray(legacy._frame(geom.depth) + shifted, dtype=float), geom.params


def build(src: Path, dst: Path, gaps: tuple[float, ...]) -> dict:
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
    if len(gaps) != len(ROWS_CHANGED):
        raise SystemExit("--gaps needs one value per changed row (0 1 2)")
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
        floor = max(frame, key=lambda b: (b[2] - b[1]) if True else 0)       # x 폭이 가장 큰 틀 (구덩이 바닥) = x 1..7
        depth = -float(floor[6])
        # 검증: 옛 돌 위치 = 옛 L0 틈 x 로 다시 만든 돌 위치 (높이 흔들림만 다름)
        chk, _ = new_tile_boxes(depth, v2.STONE_GAP_X[0], f"check|{r}|{c}")
        ck = chk[3:]
        os_ = np.array([[b[1] - x0t, b[2] - x0t, b[3] - y0t, b[4] - y0t] for b in stones]); os_ = os_[np.lexsort((os_[:, 2], os_[:, 0]))]
        nk = ck[:, :4][np.lexsort((ck[:, 2], ck[:, 0]))]
        same = len(os_) == len(nk) and np.abs(os_ - nk).max() < 1e-3
        gx = float(gaps[ROWS_CHANGED.index(r)])
        nb, params = new_tile_boxes(depth, gx, f"{KIND}|gapx|{gx:.4f}|{r}|{c}")
        for b in boxes:
            drop_labels.append(b[0])
        for x0, x1, y0, y1, z0, z1 in nb:
            v, f = _box_mesh(x0 + x0t, x1 + x0t, y0 + y0t, y1 + y0t, z0, z1)
            new_v.append(v); new_f.append(f + base); base += 8
        tri_local = np.concatenate([_box_mesh(*b)[0][_box_mesh(*b)[1]] for b in nb])
        report.append({"row": r, "col": c, "depth_m": round(depth, 4), "old_stones": len(stones), "new_stones": len(nb) - 3, "old_positions_reproduced": bool(same),
                       "gap_x_m": gx, "stone_x_m": params["stone_x"], "stone_y_m": params["stone_y"], "gap_y_m": params["gap_y"], "stone_columns": params["columns"], "stone_rows": params["rows"]})
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
    dst.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst / "terrain_mesh.npz", **new_arrays)
    shutil.copy2(src / "terrain_manifest.json", dst / "terrain_manifest.json")
    manifest = json.loads((src / "mesh_manifest.json").read_text(encoding="utf-8-sig"))
    manifest["mesh_sha256"] = hashlib.sha256(out_v.tobytes() + out_f.tobytes()).hexdigest()
    manifest["vertex_count"], manifest["face_count"] = int(len(out_v)), int(len(out_f))
    manifest["mesh_file_sha256"] = _digest(dst / "terrain_mesh.npz")
    manifest["edge_masks"] = {**manifest.get("edge_masks", {}), "sha256": em.masks_sha256(packed), "inner_cells": int(built["inner"].sum()), "outer_cells": int(built["outer"].sum())}
    manifest["stone_gap_test_mesh"] = {"NOT_FOR_TRAINING": True, "source_mesh_dir": str(src), "source_geometry_sha256": json.loads((src / "mesh_manifest.json").read_text(encoding="utf-8-sig")).get("mesh_sha256"),
                                       "kind": KIND, "columns": stone_cols, "rows": list(ROWS_CHANGED), "gap_x_m_by_row": list(gaps), "tiles": report}
    (dst / "mesh_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (dst / "stone_gap_levels.json").write_text(json.dumps(manifest["stone_gap_test_mesh"], indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest["stone_gap_test_mesh"] | {"mesh_sha256": manifest["mesh_sha256"], "mesh_file_sha256": manifest["mesh_file_sha256"], "vertices": len(out_v), "faces": len(out_f)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--dst", required=True); ap.add_argument("--gaps", default="0.05,0.10,0.14")
    a = ap.parse_args()
    res = build(Path(a.src), Path(a.dst), tuple(float(x) for x in a.gaps.split(",")))
    print(json.dumps({k: v for k, v in res.items() if k != "tiles"}, indent=1)); print("tiles", len(res["tiles"]), "reproduced", sum(t["old_positions_reproduced"] for t in res["tiles"]))
