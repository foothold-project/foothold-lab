"""B 빔 열의 짧고 기울기가 레벨에 맞는 빔으로 바꾼 학습용 합친 메시 (Isaac 없음 · 옛 폴더는 읽기만 · lead 06:3x 배정 A).

    python -m foothold_s2.scripts.ex42_beam_splice_mesh --src <합친 메시 폴더> --dst <새 폴더> --aggregate-from <aggregate 폴더>
        [--beam-length 2.0] [--beam-start-x 2.0] [--rpy-max 0.1] [--rpy-level-div 9] [--rpy-by-level a0,...,a9] [--entry-align]

옛 B/beam 칸 (줄 0~9): 앞 발판 x 0..2 · 빔 x 2..10 (길이 8 m) · 뒤 발판 x 10..12 (높이 +-delta). 빔은 가운데 축으로 roll/pitch/yaw 를
레벨과 무관하게 +-0.1 rad 균등 난수로 돌려서 들머리가 15 / 24 / 39 cm (L0 / L1 / L2) 올라온다 (planner 실측).
새 칸: 빔 길이 --beam-length (기본 2 m) 를 x = --beam-start-x 에서 시작하고, 기울기 한계는 --rpy-max * 레벨 / --rpy-level-div (기본 0.1 * L/9 ·
--rpy-by-level 로 줄마다 직접 줄 수 있음), 앞 발판은 x 0..빔 시작, 뒤 발판은 빔 끝..12 (높이 규칙 · 두께 · y 폭 · 아래 바닥 상자는 옛 칸 그대로).
--entry-align 이면 빔을 z 로 옮겨 들머리 중심선 윗면 높이를 발판 윗면 (0) 에 맞춘다. 값 (길이 · 기울기 · 시작) 은 전부 손잡이다.

상자 하나 = 꼭짓점 8 · 면 12 이므로 면 배열은 바이트 그대로이고 꼭짓점 (칸마다 3 상자 = 24 개, 모두 80 줄 중 10 칸 = 240 개) 만 제자리에서 바뀐다.
다른 열 · 다른 가족 · 가장자리 마스크 (A 가족 전용) · origins 는 바이트 그대로. 깃발은 바뀐 열 10 칸만 ex42_flag_producer.tile_flags 로 다시 구한다.
mesh_sha256 이 바뀐다: 새 plan 핀 (mesh sha) 이 필요하고 학습에 넣는 판은 이 사실을 받아들인 뒤에만.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

from foothold_s2.terrains import ame2_preset as b
from foothold_s2.terrains import ex42_flag_producer as fp

KIND, FAMILY = "beam", "B"
SIZE = b.SIZE                                   # 12 m 칸
ANCHOR = (1.0, 6.0)                             # spawn_origin 의 beam 시작 위치 (칸 좌표): origins - ANCHOR = 칸 모서리
ROWS = tuple(range(10))
THICK = 0.2                                     # 빔 두께 (옛 코드 z0 = -0.2 · z1 = 0)
BLOCK = "beam_splice"
TOL = 1e-4
DEFAULTS = {"beam_length_m": 2.0, "beam_start_x_m": 2.0, "rpy_max_rad": 0.1, "rpy_level_div": 9.0, "rpy_by_level": None, "entry_align": False}


def _digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def knobs_from(**over):
    k = {**DEFAULTS, **{key: val for key, val in over.items() if val is not None or key in ("rpy_by_level",)}}
    if not (0 < k["beam_length_m"] and 1.0 <= k["beam_start_x_m"] and k["beam_start_x_m"] + k["beam_length_m"] <= SIZE - 0.5):
        raise ValueError("beam must start at x >= 1 m (the spawn anchor stays on the first platform) and end >= 0.5 m before the tile end")
    if not (0 <= k["rpy_max_rad"] <= 0.3 and k["rpy_level_div"] > 0):
        raise ValueError("rpy_max_rad 0..0.3 and rpy_level_div > 0 required")
    if k["rpy_by_level"] is not None:
        table = [float(v) for v in k["rpy_by_level"]]
        if len(table) != 10 or min(table) < 0 or max(table) > 0.3:
            raise ValueError("rpy_by_level needs ten values 0..0.3")
        k["rpy_by_level"] = table
    return k


def angle_limit(level: int, k: dict) -> float:
    """기울기 한계 (rad) = 줄 (레벨) 의 값. 표가 있으면 표, 없으면 rpy_max * level / rpy_level_div."""
    if k["rpy_by_level"] is not None:
        return float(k["rpy_by_level"][level])
    return float(k["rpy_max_rad"]) * level / float(k["rpy_level_div"])


def box_vertices(x0, x1, y0, y1, z0, z1, roll=0.0, pitch=0.0, yaw=0.0):
    """ame2_preset.mesh_arrays 와 같은 상자 (trimesh.creation.box · 가운데 축으로 roll/pitch/yaw): (8, 3) 꼭짓점."""
    import trimesh
    tf = trimesh.transformations.euler_matrix(roll, pitch, yaw)
    tf[:3, 3] = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    return np.asarray(trimesh.creation.box(extents=(x1 - x0, y1 - y0, z1 - z0), transform=tf).vertices, dtype=np.float64)


def _top_mask():
    """trimesh 상자의 꼭짓점 8 개 중 윗면 4 개 (돌리기 전 z 가 높은 쪽). 돌려도 꼭짓점 순서는 그대로다."""
    return box_vertices(0.0, 1.0, 0.0, 1.0, -THICK, 0.0)[:, 2] > -THICK / 2


def top_plane(vertices8):
    """윗면 (돌리기 전 윗면 4 꼭짓점) 평면 z = a x + c y + d. 윗면 기울기 (a, c) 와 d. 꼭짓점은 trimesh 상자 순서여야 한다."""
    top = np.asarray(vertices8)[_top_mask()]
    A = np.column_stack([top[:, 0], top[:, 1], np.ones(4)])
    a, c, d = np.linalg.lstsq(A, top[:, 2], rcond=None)[0]
    return float(a), float(c), float(d)


def top_at(vertices8, x, y):
    a, c, d = top_plane(vertices8)
    return a * x + c * y + d


def new_tile_vertices(level, old_end_z, rng, k, width):
    """(앞 발판, 빔, 뒤 발판) 꼭짓점 (8, 3) 셋 · 칸 좌표. 뒤 발판 z0 · z1 은 옛 칸의 값 (높이차 규칙 그대로)."""
    x0, x1 = k["beam_start_x_m"], k["beam_start_x_m"] + k["beam_length_m"]
    lim = angle_limit(level, k)
    roll, pitch, yaw = (float(rng.uniform(-lim, lim)) if lim > 0 else 0.0 for _ in range(3))
    first = box_vertices(0.0, x0, 0.0, SIZE, -THICK, 0.0)
    beam = box_vertices(x0, x1, 6 - width / 2, 6 + width / 2, -THICK, 0.0, roll, pitch, yaw)
    # 기준 (엇갈림) 상자: 가운데 (x0 + x1) / 2 · 6 · -0.1 의 가운데 축 회전. 들머리 윗면 높이는 중심선 x0 + 0.02 에서 잰다.
    entry = top_at(beam, x0 + 0.02, 6.0)
    if k["entry_align"]:
        beam = beam - [0.0, 0.0, entry]
    z0, z1 = old_end_z
    last = box_vertices(x1, SIZE, 0.0, SIZE, z0, z1)
    return first, beam, last, {"roll": roll, "pitch": pitch, "yaw": yaw, "limit": lim, "entry_step_before_align_m": entry}


def _components(faces, n):
    from foothold_s2.scripts.ex42_stone_gap_test_mesh import components
    return components(faces, n)


def locate_tiles(vertices, faces, origins, family, labels, *, col=None, min_len=7.5):
    """B/beam 열 (구조로 찾음: 한 칸에 폭 <= 1.1 m · 길이 >= 7 m 빔이 있는 열 하나) 과 줄별 칸 모서리 · 세 상자의 꼭짓점 인덱스."""
    fam = [str(v) for v in family]
    b_cols = [c for c, f in enumerate(fam) if f == FAMILY] if col is None else [col]
    out = None
    for col in b_cols:
        ox, oy, _ = origins[0, col]
        cx, cy = ox - ANCHOR[0], oy - ANCHOR[1]
        m = (vertices[:, 0] >= cx + 1.9) & (vertices[:, 0] <= cx + 10.1) & (vertices[:, 1] >= cy + 5.2) & (vertices[:, 1] <= cy + 6.8)
        if not m.any():
            continue
        for lab in np.unique(labels[m]):
            p = vertices[labels == lab]
            if len(p) == 8 and np.ptp(p[:, 0]) > min_len and np.ptp(p[:, 1]) <= 2.2 and p[:, 1].min() > cy + 4 and p[:, 1].max() < cy + 8:
                if out is not None and out != col:
                    raise ValueError("more than one B column carries a long thin beam")
                out = col
    if out is None:
        raise ValueError("no B beam column found in this mesh")
    tiles = {}
    for r in ROWS:
        ox, oy, _ = origins[r, out]
        cx, cy = float(ox - ANCHOR[0]), float(oy - ANCHOR[1])
        inside = (vertices[:, 0] >= cx - TOL) & (vertices[:, 0] <= cx + SIZE + TOL) & (vertices[:, 1] >= cy - TOL) & (vertices[:, 1] <= cy + SIZE + TOL)
        boxes = {}
        for lab in np.unique(labels[inside]):
            idx = np.nonzero(labels == lab)[0]
            p = vertices[idx].astype(np.float64) - [cx, cy, 0.0]
            if len(idx) != 8 or p[:, 0].min() < -TOL or p[:, 0].max() > SIZE + TOL or p[:, 1].min() < -TOL or p[:, 1].max() > SIZE + TOL:
                continue                                                           # 옆 칸으로 걸친 성분
            wide = np.ptp(p[:, 1]) > SIZE - 1e-3
            if np.ptp(p[:, 0]) > min_len and np.ptp(p[:, 1]) <= 2.2:
                boxes["beam"] = idx
            elif wide and np.ptp(p[:, 0]) < SIZE - 0.5 and p[:, 0].min() < TOL:
                boxes["first"] = idx                                           # 12 m 전체 폭 상자 (아래 바닥) 는 제외
            elif wide and np.ptp(p[:, 0]) < SIZE - 0.5 and p[:, 0].max() > SIZE - TOL:
                boxes["last"] = idx
        if set(boxes) != {"first", "beam", "last"}:
            raise ValueError(f"tile row {r}: expected first platform, beam and last platform, found {sorted(boxes)}")
        tiles[r] = {"corner": (cx, cy), "idx": boxes}
    return out, tiles


def _same_order(idx, vertices, reference):
    return bool(np.abs(vertices[idx].astype(np.float64) - reference).max() < 1e-4)


def build(src: Path, dst: Path, *, aggregate_from: Path, **knob_args) -> dict:
    if dst.exists() and any(dst.iterdir()):
        raise SystemExit(f"destination is not empty: {dst}")
    k = knobs_from(**knob_args)
    data = np.load(src / "terrain_mesh.npz", allow_pickle=False)
    arrays = {key: data[key] for key in data.files}
    vertices, faces, origins, flags = arrays["vertices"].copy(), arrays["faces"], arrays["origins"], arrays["flags"].copy()
    labels = _components(faces.astype(np.int64), len(vertices))
    col, tiles = locate_tiles(vertices, faces, origins, arrays["column_family"], labels)
    report, tile_tris = [], {}
    for r in ROWS:
        t = tiles[r]
        cx, cy = t["corner"]
        shift = np.array([cx, cy, 0.0])
        idx = t["idx"]
        old = {name: vertices[i].astype(np.float64) - shift for name, i in idx.items()}
        level = r
        width = b.dimensions(KIND, level)["beam_width_m"]
        # 옛 값이 생성기 치수와 맞는지: 앞 · 뒤 발판 = 옛 생성기 상자 (꼭짓점 순서까지), 빔 = 모서리 길이 8 · 폭 · 0.2
        if not _same_order(idx["first"], vertices, box_vertices(0, 2.0, 0, SIZE, -THICK, 0.0) + shift):
            raise ValueError(f"tile row {r}: first platform is not the generator box (vertex order or size differs)")
        ez0, ez1 = float(old["last"][:, 2].min()), float(old["last"][:, 2].max())
        if not _same_order(idx["last"], vertices, box_vertices(10.0, SIZE, 0, SIZE, ez0, ez1) + shift):
            raise ValueError(f"tile row {r}: last platform is not the generator box")
        delta = b.dimensions(KIND, level)["height_difference_m"]
        if abs(ez0 - (-THICK - delta)) > TOL:
            raise ValueError(f"tile row {r}: last platform z0 is not -0.2 - delta")
        if not -delta - TOL <= ez1 <= delta + TOL:
            raise ValueError(f"tile row {r}: last platform top is outside +-delta")
        d = np.linalg.norm(old["beam"][:, None] - old["beam"][None], axis=2)
        edges = np.unique(np.round(d[np.triu_indices(8, 1)], 4))
        want = sorted({round(8.0, 4), round(width, 4), round(THICK, 4)})
        if not all(any(abs(e - w) < 2e-4 for e in edges) for w in want):
            raise ValueError(f"tile row {r}: old beam edges {edges.tolist()} do not contain the generator's 8 / {width} / {THICK}")
        seed = int.from_bytes(hashlib.sha256(f"{BLOCK}|{KIND}|{r}|{col}|{k['beam_start_x_m']}|{k['beam_length_m']}".encode()).digest()[:4], "big")
        first, beam, last, meas = new_tile_vertices(level, (ez0, ez1), np.random.default_rng(seed), k, width)
        for name, new in (("first", first), ("beam", beam), ("last", last)):
            vertices[idx[name]] = (new + shift).astype(vertices.dtype)
        old_a, old_c, old_d = top_plane(old["beam"])
        report.append({"row": r, "column": col, "level": level, "beam_width_m": width, "old_entry_step_m": round(float(top_at(old["beam"], 2.02, 6.0)), 4),
                       "old_beam_slope_xy": [round(old_a, 4), round(old_c, 4)], "new_roll_pitch_yaw_rad": [round(meas[a_], 5) for a_ in ("roll", "pitch", "yaw")],
                       "new_angle_limit_rad": round(meas["limit"], 5), "new_entry_step_before_align_m": round(meas["entry_step_before_align_m"], 4)})
    # 바뀐 열의 깃발 10 칸
    tri_all = vertices.astype(np.float64)[faces]
    cen = tri_all[:, :, :2].mean(1)
    for r in ROWS:
        cx, cy = tiles[r]["corner"]
        pick = (cen[:, 0] >= cx) & (cen[:, 0] < cx + SIZE) & (cen[:, 1] >= cy) & (cen[:, 1] < cy + SIZE)
        off = np.array([cx, cy, 0.0])
        xy, _ = fp.tile_flags(FAMILY, KIND, tri_all[pick] - off, origins[r, col] - off, np.array([SIZE, SIZE]))
        flags[r, col] = xy + off[:2]
    new_arrays = {**arrays, "vertices": vertices, "flags": flags}
    dst.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst / "terrain_mesh.npz", **new_arrays)
    manifest = json.loads((src / "mesh_manifest.json").read_text(encoding="utf-8-sig"))
    manifest["mesh_sha256"] = hashlib.sha256(vertices.astype(np.float32).tobytes() + faces.astype(np.int32).tobytes()).hexdigest()
    manifest["mesh_file_sha256"] = _digest(dst / "terrain_mesh.npz")
    if not (aggregate_from / manifest["aggregate_file"]).is_file():
        raise SystemExit("--aggregate-from must hold the source aggregate file")
    shutil.copy2(aggregate_from / manifest["aggregate_file"], dst / manifest["aggregate_file"])
    manifest["flag_provenance"] = {**manifest["flag_provenance"], "sha256": hashlib.sha256(flags.tobytes()).hexdigest(),
                                   "beam_splice_note": "flags of the 10 B beam tiles were recomputed with ex42_flag_producer.tile_flags; per-cell metadata above is the source's"}
    manifest[BLOCK] = {"NOT_FOR_TRAINING": False, "new_kit_validation": False, "source_mesh_dir": str(src),
                       "source_manifest_sha256": _digest(src / "mesh_manifest.json"), "source_npz_sha256": _digest(src / "terrain_mesh.npz"),
                       "source_geometry_sha256": json.loads((src / "mesh_manifest.json").read_text(encoding="utf-8-sig")).get("mesh_sha256"),
                       "aggregate_inherited_from": str(aggregate_from), "kind": KIND, "family": FAMILY, "column": col, "rows": list(ROWS),
                       "knobs": k, "changed_vertices": int(sum(len(v) for t in tiles.values() for v in t["idx"].values())), "tiles": report}
    (dst / "mesh_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (dst / "beam_rows.json").write_text(json.dumps(manifest[BLOCK], indent=1, ensure_ascii=False), encoding="utf-8")
    return manifest[BLOCK] | {"mesh_sha256": manifest["mesh_sha256"], "mesh_file_sha256": manifest["mesh_file_sha256"]}


def is_beam_splice(folder):
    return BLOCK in json.loads((Path(folder) / "mesh_manifest.json").read_text(encoding="utf-8-sig"))


def verify_beam_splice(destination) -> dict:
    """읽어 되짚는 검증 (CPU): 원본 파일 sha · 면과 다른 배열 바이트 같음 · 꼭짓점은 바뀐 상자 칸에서만 다름 · 바뀐 칸을 저장된 꼭짓점에서 다시 재서 손잡이와 맞음 ·
    깃발은 바뀐 10 칸만 다름 · 원본 (쉬운 사다리 메시) 도 자기 검증을 통과. 새 Kit 측정이 아니다 (aggregate 는 물려받음)."""
    destination = Path(destination).resolve(strict=True)
    receipt = json.loads((destination / "mesh_manifest.json").read_text(encoding="utf-8-sig"))
    blk = receipt.get(BLOCK)
    if not isinstance(blk, dict) or blk.get("NOT_FOR_TRAINING") is not False or blk.get("new_kit_validation") is not False:
        raise ValueError("beam splice: block missing, marked not for training, or claims a Kit validation")
    source = Path(blk["source_mesh_dir"]).resolve(strict=True)
    if source == destination:
        raise ValueError("beam splice: the source is the destination")
    for key, name in (("source_manifest_sha256", "mesh_manifest.json"), ("source_npz_sha256", "terrain_mesh.npz")):
        if _digest(source / name) != blk[key]:
            raise ValueError(f"beam splice: source {name} sha differs from the receipt")
    from foothold_s2.tools.ex42_ladder_splice import is_ladder_splice, verify_ladder_splice
    source_chain = verify_ladder_splice(source) if is_ladder_splice(source) else None
    file_sha = _digest(destination / "terrain_mesh.npz")
    if file_sha != receipt.get("mesh_file_sha256"):
        raise ValueError("beam splice: NPZ file sha differs from the receipt")
    agg = receipt["aggregate_file"]
    if Path(agg).name != agg or (Path(blk["aggregate_inherited_from"]) / agg).read_bytes() != (destination / agg).read_bytes():
        raise ValueError("beam splice: aggregate is not the inherited one")
    k = knobs_from(**blk["knobs"])
    with np.load(source / "terrain_mesh.npz", allow_pickle=False) as a, np.load(destination / "terrain_mesh.npz", allow_pickle=False) as c:
        if set(a.files) != set(c.files):
            raise ValueError("beam splice: array names differ from the source")
        for key in sorted(set(a.files) - {"vertices", "flags"}):
            if a[key].dtype != c[key].dtype or a[key].shape != c[key].shape or a[key].tobytes() != c[key].tobytes():
                raise ValueError(f"beam splice: original array changed: {key}")
        va, vb, faces, origins, family = a["vertices"], c["vertices"], c["faces"], c["origins"], c["column_family"]
        fa, fb = a["flags"], c["flags"]
    if va.shape != vb.shape or va.dtype != vb.dtype:
        raise ValueError("beam splice: vertex array shape or dtype changed")
    if hashlib.sha256(vb.astype(np.float32).tobytes() + faces.astype(np.int32).tobytes()).hexdigest() != receipt["mesh_sha256"]:
        raise ValueError("beam splice: geometry sha differs from the receipt")
    labels = _components(faces.astype(np.int64), len(vb))
    col, tiles = locate_tiles(vb, faces, origins, family, labels, col=blk["column"], min_len=0.9 * k["beam_length_m"])
    if col != blk["column"] or list(blk["rows"]) != list(ROWS):
        raise ValueError("beam splice: column or rows differ from the beam column of this mesh")
    allowed = np.zeros(len(vb), bool)
    for t in tiles.values():
        for i in t["idx"].values():
            allowed[i] = True
    differ = np.any(va != vb, axis=1)
    if (differ & ~allowed).any():
        raise ValueError("beam splice: a vertex outside the beam tiles differs from the source")
    other = np.ones(fa.shape[:2], bool)
    other[:, col] = False
    if not np.array_equal(fa[other], fb[other], equal_nan=True) or not np.isfinite(fb[:, col]).all():
        raise ValueError("beam splice: a flag outside the beam tiles differs or a beam tile has no finite flags")
    rows_out = []
    for r in ROWS:
        cx, cy = tiles[r]["corner"]
        shift = np.array([cx, cy, 0.0])
        p = {n: vb[i].astype(np.float64) - shift for n, i in tiles[r]["idx"].items()}
        q = {n: va[i].astype(np.float64) - shift for n, i in tiles[r]["idx"].items()}
        be = p["beam"]
        axis = np.linalg.svd(be - be.mean(0))[2][0]                        # 8 꼭짓점의 가장 긴 주축 = 빔의 길이 방향
        length = float(np.ptp((be - be.mean(0)) @ axis))
        x0 = float(be[:, 0].min())
        slope = top_plane(be)
        lim = angle_limit(r, k)
        width = b.dimensions(KIND, r)["beam_width_m"]
        if abs(length - k["beam_length_m"]) > 1e-3 or abs(x0 - k["beam_start_x_m"]) > 0.02:
            raise ValueError(f"beam splice: row {r} beam length {length:.4f} / start {x0:.4f} differ from the knobs")
        if max(abs(slope[0]), abs(slope[1])) > 2 * lim + 1e-3:
            raise ValueError(f"beam splice: row {r} beam top slope {slope[:2]} exceeds the angle limit {lim}")
        entry = top_at(be, k["beam_start_x_m"] + 0.02, 6.0)
        if k["entry_align"] and abs(entry) > 1e-3:
            raise ValueError(f"beam splice: row {r} entry step {entry:.4f} after align")
        first, last = p["first"], p["last"]
        if abs(first[:, 0].max() - k["beam_start_x_m"]) > TOL or abs(last[:, 0].min() - (k["beam_start_x_m"] + k["beam_length_m"])) > TOL:
            raise ValueError(f"beam splice: row {r} platforms do not meet the beam ends")
        if abs(last[:, 2].min() - q["last"][:, 2].min()) > TOL or abs(last[:, 2].max() - q["last"][:, 2].max()) > TOL:
            raise ValueError(f"beam splice: row {r} last platform height rule changed")
        rows_out.append({"row": r, "beam_length_m": round(length, 4), "beam_start_x_m": round(x0, 4), "entry_step_m": round(entry, 4),
                         "top_slope_xy": [round(slope[0], 5), round(slope[1], 5)], "angle_limit_rad": round(lim, 5), "beam_width_m": width,
                         "last_platform_top_m": round(float(last[:, 2].max()), 4), "gap_to_first_platform_m": round(float(x0 - first[:, 0].max()), 4)})
    return dict(blk, source=str(source), mesh_file_sha256=file_sha, mesh_sha256=receipt["mesh_sha256"],
                differing_vertices=int(differ.sum()), faces_byte_equal=True, other_arrays_byte_equal=True,
                flags_sha256=hashlib.sha256(fb.tobytes()).hexdigest(), changed_tiles=len(ROWS), measured_changed_tiles=rows_out,
                source_chain_verified=source_chain is not None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--aggregate-from", required=True)
    ap.add_argument("--beam-length", type=float, default=None)
    ap.add_argument("--beam-start-x", type=float, default=None)
    ap.add_argument("--rpy-max", type=float, default=None)
    ap.add_argument("--rpy-level-div", type=float, default=None)
    ap.add_argument("--rpy-by-level", default=None, help="ten comma separated limits (rad), rows 0..9; replaces rpy-max * level / div")
    ap.add_argument("--entry-align", action="store_true")
    a = ap.parse_args()
    table = None if a.rpy_by_level is None else [float(v) for v in a.rpy_by_level.split(",")]
    res = build(Path(a.src), Path(a.dst), aggregate_from=Path(a.aggregate_from), beam_length_m=a.beam_length, beam_start_x_m=a.beam_start_x,
                rpy_max_rad=a.rpy_max, rpy_level_div=a.rpy_level_div, rpy_by_level=table, entry_align=a.entry_align or None)
    proof = verify_beam_splice(Path(a.dst))
    print(json.dumps({k_: v for k_, v in res.items() if k_ != "tiles"}, indent=1))
    print(json.dumps({"verify": {k_: v for k_, v in proof.items() if k_ in ("differing_vertices", "faces_byte_equal", "other_arrays_byte_equal", "source_chain_verified")}}))
