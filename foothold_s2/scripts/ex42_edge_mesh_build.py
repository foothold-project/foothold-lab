"""옛 EX-42 합친 메시 폴더에서 발 가장자리 마스크를 더한 새 폴더를 만든다 (CPU · Isaac 없음 · 옛 폴더는 읽기만).

    python -m foothold_s2.scripts.ex42_edge_mesh_build --src <옛 메시 폴더> --dst <새 폴더>

새 폴더: terrain_mesh.npz (옛 배열 그대로 + edge_inner_bits · edge_outer_bits · edge_columns · edge_meta) · mesh_manifest.json (mesh_file_sha256 를
새 npz 로 바꾸고 `edge_masks` 칸 추가) · terrain_manifest.json (그대로 복사). vertices · faces 는 같아 geometry sha (mesh_sha256) 는 옛 것과 같다.
plan 의 training_mesh_profile 은 폴더 경로와 세 파일 sha 를 고정하므로 새 폴더를 쓰려면 plan 의 그 칸이 바뀐다 (plan sha 도 바뀜).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import numpy as np

from foothold_s2.terrains import ex42_edge_masks as em


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build(src: Path, dst: Path) -> dict:
    if dst.exists() and any(dst.iterdir()):
        raise SystemExit(f"destination is not empty: {dst}")
    data = np.load(src / "terrain_mesh.npz", allow_pickle=False)
    if any(k in data.files for k in em.EDGE_KEYS):
        raise SystemExit("source mesh already carries edge masks")
    arrays = {k: data[k] for k in data.files}
    t0 = time.time()
    built = em.build_edge_masks(arrays["vertices"], arrays["faces"], arrays["origins"], [str(v) for v in arrays["column_family"]])
    packed = em.pack_masks(built)
    sha = em.masks_sha256(packed)
    dst.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dst / "terrain_mesh.npz", **arrays, **packed)
    shutil.copy2(src / "terrain_manifest.json", dst / "terrain_manifest.json")
    manifest = json.loads((src / "mesh_manifest.json").read_text(encoding="utf-8-sig"))
    inner, outer = built["inner"], built["outer"]
    manifest["edge_masks"] = {"sha256": sha, "source_mesh_dir": str(src), "source_mesh_file_sha256": manifest.get("mesh_file_sha256"),
                              "columns": [int(c) for c in built["columns"]], "inner_cells": int(inner.sum()), "outer_cells": int(outer.sum()),
                              "build_seconds": round(time.time() - t0, 1), **built["meta"]}
    manifest["mesh_file_sha256"] = _digest(dst / "terrain_mesh.npz")
    (dst / "mesh_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"dst": str(dst), "edge_masks_sha256": sha, "geometry_sha256": manifest.get("mesh_sha256"), "mesh_file_sha256": manifest["mesh_file_sha256"],
            "columns": len(built["columns"]), "inner_cells": int(inner.sum()), "outer_cells": int(outer.sum()), "uncovered_cells": built["meta"]["uncovered_cells"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--dst", required=True)
    a = ap.parse_args()
    print(json.dumps(build(Path(a.src), Path(a.dst)), indent=1))
