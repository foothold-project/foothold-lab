"""Read-back verification of a mesh folder made by ex42_stone_gap_test_mesh --training (the easy stone ladder splice).

CPU only. The splice replaces the A stepping_stones_low tiles of rows 0..9 of a measured source mesh and nothing else, so what is
checked is: the source files are the ones the receipt names, every array but vertices / faces / flags / edge masks is byte equal,
the triangles outside the changed tiles are the source's (only triangles on a changed tile's edge line may differ: the outer wall
is triangulated differently), the flags of every other tile are equal, the changed tiles measure what the generator ladder says
(gap x, stone size, gap y, height jitter, read back from the saved triangles), and the edge masks are the masks of this geometry.
It is CPU evidence, never a new Kit measurement: the aggregate file is inherited and new_kit_validation stays False.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from foothold_s2.scripts import ex42_stone_gap_test_mesh as tm
from foothold_s2.terrains import columns
from foothold_s2.terrains import ex42_edge_masks as em
from foothold_s2.terrains import start_go2_v2 as v2

EDGE_TOL = 1e-3


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def is_ladder_splice(folder):
    receipt = json.loads((Path(folder) / "mesh_manifest.json").read_text(encoding="utf-8-sig"))
    return "ladder_splice" in receipt


def expected_row(row):
    """(gap_x, stone_x, stone_y, gap_y, max |height jitter|) of mesh row `row` after the splice, from the generator constants."""
    args = v2.easy_stone_low_args(row)
    level = args["level"]
    gap_x = args["gap_x"] if args["gap_x"] is not None else v2._lerp(v2.STONE_GAP_X, level)
    jitter = args["height_jitter"] if args["height_jitter"] is not None else v2.HEIGHT_JITTER
    return gap_x, v2._lerp(v2.STONE_SIZE_X, level), v2._lerp(v2.STONE_SIZE_Y, level), v2._lerp(v2.STONE_GAP_Y, level), jitter


def _triangles(vertices, faces):
    return np.ascontiguousarray(vertices[faces].astype(np.float32).reshape(-1, 9))


def verify_ladder_splice(destination):
    destination = Path(destination).resolve(strict=True)
    receipt = json.loads((destination / "mesh_manifest.json").read_text(encoding="utf-8-sig"))
    ls = receipt.get("ladder_splice")
    if not isinstance(ls, dict) or ls.get("NOT_FOR_TRAINING") is not False or ls.get("new_kit_validation") is not False:
        raise ValueError("ladder splice: block missing, marked not for training, or claims a Kit validation")
    source = Path(ls["source_mesh_dir"]).resolve(strict=True)
    if source == destination:
        raise ValueError("ladder splice: the source is the destination")
    for key, name in (("source_manifest_sha256", "mesh_manifest.json"), ("source_npz_sha256", "terrain_mesh.npz")):
        if _sha(source / name) != ls[key]:
            raise ValueError(f"ladder splice: source {name} sha differs from the receipt")
    npz = destination / "terrain_mesh.npz"
    file_sha = _sha(npz)
    if file_sha != receipt.get("mesh_file_sha256"):
        raise ValueError("ladder splice: NPZ file sha differs from the receipt")
    aggregate = receipt["aggregate_file"]
    if Path(aggregate).name != aggregate or (Path(ls["aggregate_inherited_from"]) / aggregate).read_bytes() != (destination / aggregate).read_bytes():
        raise ValueError("ladder splice: aggregate is not the inherited one")
    with np.load(source / "terrain_mesh.npz", allow_pickle=False) as a, np.load(npz, allow_pickle=False) as b:
        if set(a.files) != set(b.files):
            raise ValueError("ladder splice: array names differ from the source")
        replaced = {"vertices", "faces", "flags", *em.EDGE_KEYS}
        for key in sorted(set(a.files) - replaced):
            if a[key].dtype != b[key].dtype or a[key].shape != b[key].shape or a[key].tobytes() != b[key].tobytes():
                raise ValueError(f"ladder splice: original array changed: {key}")
        unchanged = sorted(set(a.files) - replaced)
        va, fa, vb, fb = a["vertices"], a["faces"], b["vertices"], b["faces"]
        origins, family = b["origins"], [str(v) for v in b["column_family"]]
        flags_a, flags_b = a["flags"], b["flags"]
        packed = {k: b[k] for k in em.EDGE_KEYS if k in b.files}
    if hashlib.sha256(vb.astype(np.float32).tobytes() + fb.astype(np.int32).tobytes()).hexdigest() != receipt["mesh_sha256"]:
        raise ValueError("ladder splice: geometry sha differs from the receipt")
    if (len(vb), len(fb)) != (receipt["vertex_count"], receipt["face_count"]):
        raise ValueError("ladder splice: vertex or face count differs from the receipt")
    rows_total, cols_total = origins.shape[:2]
    n_a = sum(1 for f in family if f == "A")
    names = columns.column_types(columns.FULL, n_a)
    stone_cols = [c for c in range(n_a) if names[c] == tm.KIND]
    if stone_cols != ls["columns"] or list(ls["rows"]) != list(tm.ROWS_CHANGED):
        raise ValueError("ladder splice: columns or rows differ from the stone columns of this mesh")
    changed = {(r, c) for c in stone_cols for r in tm.ROWS_CHANGED}
    # triangles outside the changed tiles: equal, except the ones on a changed tile's edge line
    ta, tb = _triangles(va, fa), _triangles(vb, fb)
    corners = {rc: tm.tile_corner(rc[0], rc[1], rows_total, n_a) for rc in changed}

    def outside(tri):
        centre = tri.reshape(-1, 3, 3).mean(1)
        keep = np.ones(len(tri), bool)
        for x0, y0 in corners.values():
            keep &= ~((centre[:, 0] >= x0) & (centre[:, 0] < x0 + tm.TILE[0]) & (centre[:, 1] >= y0) & (centre[:, 1] < y0 + tm.TILE[1]))
        return tri[keep]

    oa, ob = outside(ta), outside(tb)
    key = lambda t: t.view(np.dtype((np.void, 36))).ravel()
    only_a, only_b = oa[~np.isin(key(oa), key(ob))], ob[~np.isin(key(ob), key(oa))]
    if len(oa) != len(ob) or len(only_a) != len(only_b):
        raise ValueError("ladder splice: triangle count outside the changed tiles differs")
    for tris in (only_a, only_b):
        centre = tris.reshape(-1, 3, 3).mean(1)
        near = np.zeros(len(centre), bool)
        for x0, y0 in corners.values():
            near |= ((np.abs(centre[:, 0] - x0) < EDGE_TOL) | (np.abs(centre[:, 0] - (x0 + tm.TILE[0])) < EDGE_TOL)
                     | (np.abs(centre[:, 1] - y0) < EDGE_TOL) | (np.abs(centre[:, 1] - (y0 + tm.TILE[1])) < EDGE_TOL))
        if not near.all():
            raise ValueError("ladder splice: a triangle outside the changed tiles differs and is not on a changed tile's edge line")
    # flags: every other tile equal, changed tiles finite
    other = np.ones((rows_total, cols_total), bool)
    for r, c in changed:
        other[r, c] = False
    if not np.array_equal(flags_a[other], flags_b[other], equal_nan=True):
        raise ValueError("ladder splice: a flag outside the changed tiles differs")
    if not all(np.isfinite(flags_b[r, c]).all() for r, c in changed):
        raise ValueError("ladder splice: a changed tile has no finite flags")
    # changed tiles read back from the saved triangles
    labels = tm.components(fb, len(vb))
    measured = tm.tile_boxes_world(vb, fb, labels, rows_total, cols_total, rows_total, n_a, sorted(changed))
    rows_out = []
    for (r, c) in sorted(changed):
        x0, y0 = corners[(r, c)]
        stones = [s for s in measured[(r, c)] if s[4] - s[3] <= tm.TILE[1] - 1e-3]
        got = tm.measure_tile(stones, x0, y0)
        gap_x, sx, sy, gap_y, jitter = expected_row(r)
        if (abs(got["gap_x_m"] - gap_x) > 2e-4 or abs(got["stone_x_m"] - sx) > 2e-4 or abs(got["stone_y_m"] - sy) > 2e-4
                or abs(got["gap_y_m"] - gap_y) > 2e-4 or got["height_jitter_max_abs_m"] > jitter + 1e-6):
            raise ValueError(f"ladder splice: tile row {r} column {c} does not measure the ladder: {got}")
        rows_out.append({"row": r, "column": c, **got})
    # edge masks of this geometry
    built = em.build_edge_masks(vb, fb, origins, family)
    again = em.pack_masks(built)
    if em.masks_sha256(again) != receipt["edge_masks"]["sha256"] or any(again[k].tobytes() != packed[k].tobytes() for k in again):
        raise ValueError("ladder splice: edge masks are not the masks of this geometry")
    return dict(ls, source=str(source), mesh_file_sha256=file_sha, mesh_sha256=receipt["mesh_sha256"],
                original_arrays_unchanged=unchanged, aggregate_sha256=_sha(destination / aggregate),
                flags_shape=list(flags_b.shape), flags_sha256=hashlib.sha256(flags_b.tobytes()).hexdigest(), flags_bytes=int(flags_b.nbytes),
                finite_cells=int(np.isfinite(flags_b).all(axis=(2, 3)).sum()), fallback_cells=int(np.isnan(flags_b).all(axis=(2, 3)).sum()),
                changed_tiles=len(changed), outside_triangles=int(len(oa)), outside_triangles_differing_on_tile_edge=int(len(only_a)),
                measured_changed_tiles=rows_out, edge_masks_sha256=receipt["edge_masks"]["sha256"])
