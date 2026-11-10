from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.terrains import ex42_mesh_mount as mm

REAL = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42")


def _step_mesh():
    # two flat tiles at z=0 (x<0) and z=0.2 (x>=0), 4 vertices each, no shared vertices
    v = np.array([[-4, -2, 0], [0, -2, 0], [0, 2, 0], [-4, 2, 0],
                  [0, -2, .2], [4, -2, .2], [4, 2, .2], [0, 2, .2]], np.float32)
    f = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]], np.int32)
    return v, f


def _save(tmp_path, v, f, origins, families):
    p = tmp_path / "m.npz"
    np.savez_compressed(p, vertices=v, faces=f, origins=origins, column_family=np.array(families))
    return p


def test_modules_called_exist():
    for name in ("foothold_s2.terrains.ex42_mesh_mount", "foothold_s2.scripts.ex42_mesh_mount_check"):
        assert importlib.util.find_spec(name) is not None


def test_load_verifies_shapes_and_sha(tmp_path):
    v, f = _step_mesh()
    origins = np.array([[[-2, 0, 0.0], [2, 0, 0.2]]])
    p = _save(tmp_path, v, f, origins, ["A", "C"])
    sha = hashlib.sha256(v.astype(np.float32).tobytes() + f.astype(np.int32).tobytes()).hexdigest()
    assert mm.load_combined_mesh(p, sha)["mesh_sha256"] == sha
    with pytest.raises(ValueError, match="differs"):
        mm.load_combined_mesh(p, "0" * 64)
    with pytest.raises(ValueError, match="one family name per column"):
        mm.load_combined_mesh(_save(tmp_path, v, f, origins, ["A"]))
    bad = f.copy(); bad[0, 0] = 99
    with pytest.raises(ValueError, match="missing vertices"):
        mm.load_combined_mesh(_save(tmp_path, v, bad, origins, ["A", "C"]))


def test_local_heights_are_the_surface_under_each_point_and_nan_outside():
    v, f = _step_mesh()
    h = mm.local_mesh_heights(v, f, np.array([[-2.0, 0.0], [2.0, 0.5], [10.0, 0.0]]), radius=6.0)
    assert h[0] == pytest.approx(0.0) and h[1] == pytest.approx(0.2) and np.isnan(h[2])


@pytest.mark.skipif(not (REAL / "terrain_mesh.npz").exists(), reason="mesh batch 1 output not on this machine")
def test_real_mesh_origins_sit_on_the_mesh_for_every_family_cpu():
    """Part A of the Kit check, run on the real 61-column mesh (CPU)."""
    from foothold_s2.scripts.ex42_mesh_mount_check import part_a
    data = mm.load_combined_mesh(REAL / "terrain_mesh.npz", mm.expected_sha_from_manifest(REAL / "mesh_manifest.json"))
    assert data["origins"].shape == (10, 61, 3)
    out = part_a(data)
    print(out)
    assert out["no_hit"] == 0 and out["passed"], out
    assert set(out["max_abs_by_family_m"]) == {"A", "C", "E"}


def test_a_large_face_whose_centroid_is_far_is_still_found():
    v = np.array([[-50, -50, 0.3], [50, -50, 0.3], [50, 50, 0.3], [-50, 50, 0.3]], np.float32)
    f = np.array([[0, 1, 2], [0, 2, 3]], np.int32)
    h = mm.local_mesh_heights(v, f, np.array([[0.0, 0.0]]), radius=2.0)
    assert h[0] == pytest.approx(0.3)
