"""Edge profile relaxation of the M0~M3 file sha check (lead 2026-11-18 15:59): same arrays + edge_masks keys only passes; anything else stops."""
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.tools.ex42_m0_m3 import edge_profile_relaxed


def _make(tmp_path, mutate=None, extra=None, manifest_extra=None):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir(); new.mkdir()
    arrays = {"vertices": np.arange(12, dtype=np.float32).reshape(4, 3), "faces": np.array([[0, 1, 2], [1, 2, 3]], dtype=np.int64),
              "flags": np.zeros((2, 2, 2), np.float32)}
    manifest = {"mesh_sha256": "ab" * 32, "seed": 42, "mesh_file_sha256": "00"}
    np.savez(old / "terrain_mesh.npz", **arrays)
    (old / "mesh_manifest.json").write_text(json.dumps(manifest)); (old / "terrain_manifest.json").write_text("{}")
    new_arrays = dict(arrays)
    if mutate:
        new_arrays["vertices"] = new_arrays["vertices"].copy(); new_arrays["vertices"].view(np.uint8)[0] ^= 1
    new_arrays.update(extra if extra is not None else {"edge_inner_bits": np.zeros(3, np.uint8), "edge_meta": np.array([1])})
    np.savez_compressed(new / "terrain_mesh.npz", **new_arrays)
    nm = dict(manifest, edge_masks={"sha256": "x"}, mesh_file_sha256="11", **(manifest_extra or {}))
    (new / "mesh_manifest.json").write_text(json.dumps(nm)); shutil.copy(old / "terrain_manifest.json", new / "terrain_manifest.json")
    return old, new


def test_same_arrays_plus_masks_passes(tmp_path):
    old, new = _make(tmp_path)
    r = edge_profile_relaxed(old, new)
    assert r["line"].startswith("EDGE_PROFILE_FILE_SHA_RELAXED old_npz_sha256=") and "vertices" in r["same_arrays"] and r["added_arrays"] == ["edge_inner_bits", "edge_meta"]


def test_one_byte_in_vertices_stops(tmp_path):
    with pytest.raises(ValueError, match="array vertices differs"):
        edge_profile_relaxed(*_make(tmp_path, mutate=True))


def test_unknown_array_stops(tmp_path):
    with pytest.raises(ValueError, match="unknown arrays added: surprise"):
        edge_profile_relaxed(*_make(tmp_path, extra={"edge_meta": np.array([1]), "surprise": np.zeros(2)}))


def test_nothing_added_stops(tmp_path):
    with pytest.raises(ValueError, match="none added"):
        edge_profile_relaxed(*_make(tmp_path, extra={}))


def test_other_manifest_key_stops(tmp_path):
    with pytest.raises(ValueError, match="manifest differs beyond"):
        edge_profile_relaxed(*_make(tmp_path, manifest_extra={"seed": 42, "offsets_m": {"A": 1}}))


def test_real_mesh_passes():
    old = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2")
    new = Path("/home/jay/data/foothold/s2_lab/ex42_mesh_1118_edge/seed42_E0_c333_flags_E2_1111_v2_edge")
    if not (old.exists() and new.exists()):
        pytest.skip("real mesh folders absent")
    r = edge_profile_relaxed(old, new)
    assert {"vertices", "faces", "origins", "column_family", "flags"} <= set(r["same_arrays"]) and set(r["added_arrays"]) == {"edge_inner_bits", "edge_outer_bits", "edge_columns", "edge_meta"}
