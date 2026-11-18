"""verify_ladder_splice on the real spliced folder and on tampered copies (needs the saved mesh folders; they are on the lab disk)."""
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.tools import ex42_ladder_splice as ls

NEW = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1118_easy10/seed42_E0_c333_flags_E2_1111_v2_edge_easy10")
pytestmark = pytest.mark.skipif(not NEW.is_dir(), reason="spliced mesh folder not on this machine")


def test_expected_rows_follow_the_generator_ladder():
    assert [round(ls.expected_row(r)[0], 4) for r in range(10)] == [0.05, 0.07, 0.09, 0.11, 0.14, 0.1939, 0.2031, 0.2124, 0.2216, 0.2308]
    assert ls.expected_row(0)[4] == 0.02 and ls.expected_row(5)[4] == 0.05
    assert ls.expected_row(3)[1:4] == pytest.approx((0.554, 0.4425, 0.0885))


def test_real_folder_verifies():
    proof = ls.verify_ladder_splice(NEW)
    assert proof["changed_tiles"] == 70 and proof["outside_triangles_differing_on_tile_edge"] < 100
    assert ls.is_ladder_splice(NEW)


def _tampered(tmp_path, edit):
    dst = tmp_path / "t"
    shutil.copytree(NEW, dst)
    with np.load(dst / "terrain_mesh.npz", allow_pickle=False) as z:
        arrays = {k: z[k].copy() for k in z.files}
    edit(arrays)
    np.savez_compressed(dst / "terrain_mesh.npz", **arrays)
    manifest = json.loads((dst / "mesh_manifest.json").read_text(encoding="utf-8"))
    with (dst / "terrain_mesh.npz").open("rb") as f:
        manifest["mesh_file_sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
    manifest["mesh_sha256"] = hashlib.sha256(arrays["vertices"].astype(np.float32).tobytes() + arrays["faces"].astype(np.int32).tobytes()).hexdigest()
    (dst / "mesh_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return dst


def test_a_moved_vertex_outside_the_changed_tiles_is_refused(tmp_path):
    def edit(a):
        a["vertices"][0, 2] += 0.01          # vertex 0 is part of an untouched tile
    with pytest.raises(ValueError, match="outside the changed tiles|array changed|edge masks"):
        ls.verify_ladder_splice(_tampered(tmp_path, edit))


def test_a_changed_tile_that_leaves_the_ladder_is_refused(tmp_path):
    def edit(a):
        v = a["vertices"]
        v[-5000:, 2] += 0.2                  # the last vertices are the spliced stones
    with pytest.raises(ValueError, match="ladder|edge masks|outside"):
        ls.verify_ladder_splice(_tampered(tmp_path, edit))


def test_a_changed_aggregate_is_refused(tmp_path):
    dst = tmp_path / "t"
    shutil.copytree(NEW, dst)
    path = dst / "aggregate_measurements.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="aggregate"):
        ls.verify_ladder_splice(dst)
