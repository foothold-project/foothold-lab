from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval.ex42_render_plan import build_render_plan, main


def _mesh_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "mesh"
    root.mkdir()
    vertices = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    faces = np.asarray([[0, 1, 2]], dtype=np.int32)
    origins = np.zeros((10, 76, 3), dtype=np.float64)
    families = np.asarray(["A"] * 50 + ["B"] * 12 + ["C"] * 7 + ["D"] * 3 + ["E"] * 4)
    np.savez(root / "terrain_mesh.npz", vertices=vertices, faces=faces,
             origins=origins, column_family=families)
    mesh_sha = hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest()
    mesh_file_sha = hashlib.sha256((root / "terrain_mesh.npz").read_bytes()).hexdigest()
    mesh_manifest = {"format": "foothold-ex42-combined-mesh/1", "seed": 42,
        "families_present": ["A", "B", "C", "D", "E"], "families_missing": [],
        "mesh_sha256": mesh_sha, "mesh_file_sha256": mesh_file_sha,
        "training_started": False,
        "origins_shape": [10, 76, 3],
        "columns_by_family": {"A": 50, "B": 12, "C": 7, "D": 3, "E": 4}}
    (root / "mesh_manifest.json").write_text(json.dumps(mesh_manifest), encoding="utf-8")
    terrain = {"format": "foothold-ex42-terrain-manifest/1", "status": "ready",
        "blockers": [], "kinds": [
            {"family": "continuous", "geometry_family": "A", "kind": "rough",
             "geometry_selection": {"columns": [0]}},
            {"family": "B", "geometry_family": "B", "kind": "stones",
             "geometry_selection": {"columns": [50]}},
        ]}
    (root / "terrain_manifest.json").write_text(json.dumps(terrain), encoding="utf-8")
    return root


def test_plan_uses_mesh_kinds_level_rule_modes_and_three_slots(tmp_path):
    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/rough"}, current_cap=9)

    assert plan["mesh_sha256"]
    assert plan["checkpoint_sha256"]
    assert plan["state"] == "selection_pending"
    assert len(plan["requests"]) == 2 * 2 * 3
    assert {r["terrain_key"]: r["terrain_level"] for r in plan["requests"]} == {
        "A/rough": 9, "B/stones": 0}
    assert {r["map_mode"] for r in plan["requests"]} == {"eval_gt", "eval_pred"}
    assert {r["selection_role"] for r in plan["requests"]} == {
        "success", "failure", "overview"}
    assert all(r["selected_env_id"] is None for r in plan["requests"])
    assert all(r["capture_ready"] is False for r in plan["requests"])


def test_plan_rejects_unknown_or_invalid_trained_kind(tmp_path):
    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    with pytest.raises(ValueError, match="trained kind absent"):
        build_render_plan(mesh, checkpoint, trained_kinds={"C/nope"}, current_cap=9)
    with pytest.raises(ValueError, match="current cap"):
        build_render_plan(mesh, checkpoint, trained_kinds={"A/rough"}, current_cap=10)


def test_plan_only_cli_emits_json_and_keeps_capture_blocked(tmp_path):
    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    output = io.StringIO()
    argv = ["--mesh-dir", str(mesh), "--checkpoint", str(checkpoint),
            "--trained-kind", "A/rough", "--current-cap", "9"]
    with redirect_stdout(output):
        assert main(argv) == 0
    result = json.loads(output.getvalue())
    assert result["state"] == "selection_pending"
    assert result["renderer_backend"]["supported"] is False
    assert len(result["requests"]) == 12
    from foothold_s2.eval.video25.record_c_layer import parse_spec
    with pytest.raises(ValueError, match="experiment must be B, TD, G0B, or SB"):
        parse_spec(json.dumps({"experiment": "EX42", "source_root": str(Path(__file__).resolve().parents[3])}))
