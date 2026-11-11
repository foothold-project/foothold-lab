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


def test_capture_spec_uses_matching_eval_cell_and_pins_frame_audit_inputs(tmp_path):
    from foothold_s2.eval.ex42_render_capture import capture_spec_from_evaluation, validate_capture_spec

    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/rough"}, current_cap=9)
    request = next(row for row in plan["requests"]
                   if row["terrain_key"] == "A/rough" and row["map_mode"] == "eval_gt")

    n = 64
    kinds = np.asarray(["rough"] * 32 + ["stones"] * 32)
    cols = np.asarray([0] * 32 + [50] * 32, dtype=np.int64)
    levels = np.asarray([9] * 32 + [0] * 32, dtype=np.int64)
    alive = np.ones(n, dtype=np.bool_)
    alive[1] = False
    distance = np.full(n, 4.0, dtype=np.float32)
    arrays = tmp_path / "env_arrays_eval_gt_fwd1.0.npz"
    np.savez(arrays, kind=kinds, terrain_col=cols, terrain_level=levels,
             alive_end=alive, body_vx_integral_m=distance)
    evaluation = tmp_path / "map_modes.json"
    evaluation.write_text(json.dumps({
        "checkpoint_sha256": plan["checkpoint_sha256"], "eval_seed": 42,
        "ex42_mesh": {"mesh_sha256": plan["mesh_sha256"]},
        "env_arrays": {"eval_gt/fwd1.0": arrays.name},
    }), encoding="utf-8")

    selected = capture_spec_from_evaluation(
        plan, request["request_id"], evaluation, command_name="fwd1.0",
        role="success", source_root=tmp_path, source_head="a" * 40,
        recorder_sha256="b" * 64,
    )
    assert selected["env_id"] == 0
    assert selected["terrain_key"] == "A/rough"
    assert selected["fixed_level"] == 9
    assert selected["map_mode"] == "eval_gt"
    assert selected["evaluation_arrays_sha256"]
    assert selected["frame_audit_required"] is True
    assert validate_capture_spec(selected)["state"] == "verified"


def test_capture_spec_rejects_wrong_checkpoint_or_empty_role(tmp_path):
    from foothold_s2.eval.ex42_render_capture import capture_spec_from_evaluation

    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/rough"}, current_cap=9)
    request = next(row for row in plan["requests"] if row["terrain_key"] == "A/rough")
    arrays = tmp_path / "env_arrays_eval_gt_fwd1.0.npz"
    np.savez(arrays, kind=np.asarray(["rough"]), terrain_col=np.asarray([0]),
             terrain_level=np.asarray([9]), alive_end=np.asarray([True]),
             body_vx_integral_m=np.asarray([4.0]))
    evaluation = tmp_path / "map_modes.json"
    evaluation.write_text(json.dumps({"checkpoint_sha256": "0" * 64, "eval_seed": 42,
        "ex42_mesh": {"mesh_sha256": plan["mesh_sha256"]},
        "env_arrays": {"eval_gt/fwd1.0": arrays.name}}), encoding="utf-8")
    kwargs = dict(command_name="fwd1.0", role="success", source_root=tmp_path,
                  source_head="a" * 40, recorder_sha256="b" * 64)
    with pytest.raises(ValueError, match="checkpoint SHA"):
        capture_spec_from_evaluation(plan, request["request_id"], evaluation, **kwargs)


def test_plan_includes_current_cap_and_l9_for_trained_kind(tmp_path):
    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/rough"}, current_cap=5)
    trained_levels = {row["terrain_level"] for row in plan["requests"]
                      if row["terrain_key"] == "A/rough"}
    untrained_levels = {row["terrain_level"] for row in plan["requests"]
                        if row["terrain_key"] == "B/stones"}
    assert trained_levels == {5, 9}
    assert untrained_levels == {0}
    assert len(plan["requests"]) == 18
