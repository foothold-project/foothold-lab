"""D44's published one-tile mesh must give every evaluation env its own tile."""
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.eval.ex42_eval_tile_mesh import (
    assign_independent_env_origins, build_replicas, preflight_replicas, source_tile)
from foothold_s2.terrains.ex42_eval_terrains import LANDING, write_mesh
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh


def _source(tmp_path, monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    folder = tmp_path / "source"
    write_mesh(folder, kinds=[LANDING], seed=42)
    return folder


def test_landing_replicas_have_distinct_pinned_anchors_and_mesh(tmp_path, monkeypatch):
    source = _source(tmp_path, monkeypatch)
    manifest, column = source_tile(source)
    assert manifest["seed"] == 42
    for anchor in ("approach", "landing_center"):
        output = tmp_path / anchor
        receipt = build_replicas(source, output, anchor=anchor, grid=2)
        loaded = load_combined_mesh(output / "terrain_mesh.npz", receipt["mesh_sha256"])
        assert loaded["origins"].shape == (2, 2, 3)
        assert len({tuple(pos) for pos in loaded["origins"].reshape(-1, 3)}) == 4
        np.testing.assert_allclose(loaded["origins"][0, 0], column["anchors_local_m"][anchor], atol=0)
        np.testing.assert_allclose(loaded["origins"][1, 0] - loaded["origins"][0, 0], [8, 0, 0], atol=0)
        np.testing.assert_allclose(loaded["origins"][0, 1] - loaded["origins"][0, 0], [0, 8, 0], atol=0)
        assert receipt["envs"] == 4 and receipt["source_mesh_sha256"] == manifest["mesh_sha256"]
        assert preflight_replicas(source, output, anchor=anchor, grid=2) == receipt
        with pytest.raises(FileExistsError):
            build_replicas(source, output, anchor=anchor, grid=2)


def test_landing_replicas_reject_tampered_source_or_anchor(tmp_path, monkeypatch):
    source = _source(tmp_path, monkeypatch)
    with (source / "terrain_mesh.npz").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="file SHA"):
        build_replicas(source, tmp_path / "bad", anchor="approach", grid=2)

    source2 = tmp_path / "source2"
    write_mesh(source2, kinds=[LANDING], seed=42)
    path = source2 / "mesh_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["columns"][0]["anchors_local_m"]["stop_band_x"] = [3.0, 4.0]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="regenerated tile differs"):
        build_replicas(source2, tmp_path / "bad2", anchor="approach", grid=2)


def test_landing_preflight_rejects_changed_replica_origin(tmp_path, monkeypatch):
    source = _source(tmp_path, monkeypatch)
    output = tmp_path / "replicas"
    build_replicas(source, output, anchor="landing_center", grid=2)
    receipt_path = output / "replica_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["anchor"] = "approach"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt"):
        preflight_replicas(source, output, anchor="landing_center", grid=2)


def test_landing_assignment_uses_every_tile_once():
    origins = torch.tensor([[[0., 0., 0.], [0., 8., 0.]],
                            [[8., 0., 0.], [8., 8., 0.]]])
    scene_origins = torch.zeros(4, 3)
    terrain = SimpleNamespace(terrain_origins=origins, terrain_levels=torch.zeros(4, dtype=torch.long),
                              terrain_types=torch.zeros(4, dtype=torch.long), env_origins=scene_origins)
    raw = SimpleNamespace(scene=SimpleNamespace(terrain=terrain, env_origins=scene_origins))
    result = assign_independent_env_origins(raw, grid=2)
    assert result["unique_origins"] == 4
    assert terrain.terrain_levels.tolist() == [0, 0, 1, 1]
    assert terrain.terrain_types.tolist() == [0, 1, 0, 1]
    assert torch.equal(scene_origins, origins.reshape(4, 3))
    with pytest.raises(ValueError, match="one terrain tile"):
        assign_independent_env_origins(raw, grid=3)


def test_landing_replicas_accept_a_manifest_published_before_new_derived_anchors(tmp_path, monkeypatch):
    # 11/11 18:4x: landing_seed42_v2 was published before build_tile reported course_exit and
    # stop_band_interior_surface_z_m; the real post-E1 P1 m250 stopped on that difference although the geometry matched.
    source = _source(tmp_path, monkeypatch)
    path = source / "mesh_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for key in ("course_exit", "stop_band_interior_surface_z_m"):
        manifest["columns"][0]["anchors_local_m"].pop(key, None)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    build_replicas(source, tmp_path / "ok", anchor="approach", grid=2)
