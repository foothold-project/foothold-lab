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
            {"family": "continuous", "geometry_family": "A", "kind": "pyramid_stairs",
             "geometry_selection": {"columns": [0]}},
            {"family": "B", "geometry_family": "B", "kind": "stair_up",
             "geometry_selection": {"columns": [50]}},
        ]}
    (root / "terrain_manifest.json").write_text(json.dumps(terrain), encoding="utf-8")
    return root


def _write_evaluation_artifacts(plan, mesh: Path, arrays: Path, *, kinds, cols, levels,
                                alive, distance, evaluation: Path):
    from foothold_s2.eval.ex42_mesh_eval import preflight
    from foothold_s2.eval.fixed_terrain import assignment_sha256

    kinds = np.asarray(kinds)
    cols = np.asarray(cols, dtype=np.int64)
    levels = np.asarray(levels, dtype=np.int64)
    assignment = assignment_sha256(levels, cols)
    np.savez(arrays, kind=kinds, terrain_col=cols, terrain_level=levels,
             alive_end=np.asarray(alive, dtype=bool),
             body_vx_integral_m=np.asarray(distance, dtype=np.float64),
             assignment_sha256=np.asarray(assignment))
    mesh_record = preflight(mesh)
    evaluation.write_text(json.dumps({
        "checkpoint_sha256": plan["checkpoint_sha256"], "eval_seed": 42,
        "envs": 64, "steps": 300, "policy_dt_s": 0.02,
        "commands": {"fwd1.0": [1.0, 0.0, 0.0]},
        "ex42_mesh": {"mesh_sha256": plan["mesh_sha256"],
                      "columns": mesh_record["columns"]},
        "fixed_terrain": {"assignment_sha256": assignment},
        "terrain_hash": {"eval_gt/fwd1.0": assignment},
        "env_arrays": {"eval_gt/fwd1.0": arrays.name},
    }), encoding="utf-8")


def test_plan_uses_mesh_kinds_level_rule_modes_and_three_slots(tmp_path):
    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/pyramid_stairs"}, current_cap=9)

    assert plan["mesh_sha256"]
    assert plan["checkpoint_sha256"]
    assert plan["state"] == "selection_pending"
    assert len(plan["requests"]) == 2 * 2 * 3
    assert {r["terrain_key"]: r["terrain_level"] for r in plan["requests"]} == {
        "A/pyramid_stairs": 9, "B/stair_up": 0}
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
        build_render_plan(mesh, checkpoint, trained_kinds={"A/pyramid_stairs"}, current_cap=10)


def test_plan_only_cli_emits_json_and_capture_consumer_can_prepare_a_spec(tmp_path):
    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    output = io.StringIO()
    argv = ["--mesh-dir", str(mesh), "--checkpoint", str(checkpoint),
            "--trained-kind", "A/pyramid_stairs", "--current-cap", "9"]
    with redirect_stdout(output):
        assert main(argv) == 0
    result = json.loads(output.getvalue())
    assert result["state"] == "selection_pending"
    assert result["renderer_backend"]["supported"] is True
    assert len(result["requests"]) == 12
    from foothold_s2.eval.ex42_render_capture import capture_spec_from_evaluation
    from foothold_s2.eval.video25.record_c_layer import parse_spec
    checkpoint = tmp_path / "backend.pt"
    checkpoint.write_bytes(b"backend checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/pyramid_stairs"}, current_cap=9)
    request = next(row for row in plan["requests"] if row["terrain_key"] == "A/pyramid_stairs")
    arrays = tmp_path / "env_arrays_eval_gt_fwd1.0.npz"
    n = 64
    evaluation = tmp_path / "backend-map-modes.json"
    _write_evaluation_artifacts(plan, mesh, arrays,
        kinds=["pyramid_stairs"] * n, cols=np.zeros(n), levels=np.full(n, 9),
        alive=np.ones(n), distance=np.full(n, 4.0), evaluation=evaluation)
    repo = Path(__file__).resolve().parents[3]
    import subprocess
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    recorder = repo / "foothold_s2/eval/video25/record_c_layer.py"
    spec = capture_spec_from_evaluation(plan, request["request_id"], evaluation,
        command_name="fwd1.0", role="success", source_root=repo, source_head=head,
        recorder_sha256=hashlib.sha256(recorder.read_bytes()).hexdigest())
    parsed = parse_spec(json.dumps(spec))
    assert parsed["source_profile"] == "EX42_RENDER"
    assert parsed["terrain_set"] == "ex42_mesh"
    from foothold_s2.eval.ex42_render_capture import prepare_capture_command
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    spec_path = tmp_path / "capture.json"
    prepared = prepare_capture_command(
        plan_path, request["request_id"], evaluation, command_name="fwd1.0",
        role="success", source_root=repo, spec_path=spec_path,
        output=tmp_path / "capture.mp4", label="EX42 sample")
    assert prepared["state"] == "prepared"
    assert prepared["command"][prepared["command"].index("--policy") + 1] == "@" + str(spec_path)
    assert parse_spec("@" + str(spec_path))["request_id"] == request["request_id"]


def test_capture_assignment_replays_the_exact_evaluation_arrays(tmp_path):
    import types
    import torch
    from foothold_s2.eval.ex42_render_capture import apply_evaluation_assignment

    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/pyramid_stairs"}, current_cap=5)
    request = next(row for row in plan["requests"]
                   if row["terrain_key"] == "A/pyramid_stairs" and row["terrain_level"] == 5
                   and row["map_mode"] == "eval_gt" and row["selection_role"] == "success")
    n = 64
    kinds = np.asarray(["pyramid_stairs"] * n)
    cols = np.asarray([0] * n, dtype=np.int64)
    levels = np.asarray([5] * n, dtype=np.int64)
    arrays = tmp_path / "arrays.npz"
    evaluation = tmp_path / "map_modes.json"
    _write_evaluation_artifacts(plan, mesh, arrays, kinds=kinds, cols=cols, levels=levels,
        alive=np.ones(n), distance=np.full(n, 4.0), evaluation=evaluation)
    from foothold_s2.eval.ex42_render_capture import capture_spec_from_evaluation
    spec = capture_spec_from_evaluation(plan, request["request_id"], evaluation,
        command_name="fwd1.0", role="success", source_root=tmp_path,
        source_head="a" * 40, recorder_sha256="b" * 64)
    terrain = types.SimpleNamespace(
        terrain_origins=torch.zeros((10, 76, 3)),
        terrain_levels=torch.zeros(n, dtype=torch.long),
        terrain_types=torch.zeros(n, dtype=torch.long),
        env_origins=torch.zeros((n, 3)))
    raw = types.SimpleNamespace(num_envs=n, scene=types.SimpleNamespace(
        terrain=terrain, env_origins=torch.zeros((n, 3))))
    receipt = apply_evaluation_assignment(raw, spec)
    assert receipt["selected_env_id"] == 0
    assert receipt["assignment_sha256"]
    assert torch.equal(terrain.terrain_levels, torch.full((n,), 5, dtype=torch.long))
    assert torch.equal(terrain.terrain_types, torch.zeros(n, dtype=torch.long))


def test_full_frame_audit_detects_black_capture_and_accepts_valid_sample(tmp_path):
    import cv2
    from foothold_s2.eval.ex42_render_capture import audit_capture_video

    width, height, n = 1280, 720, 2
    yy, xx = np.mgrid[:height, :width]
    frames = [np.stack(((xx + i * 10) % 256, yy % 256, (xx // 2 + yy // 3) % 256), axis=2).astype(np.uint8)
              for i in range(n)]
    evidence = [{"root_center_px": [640.0, 360.0], "root_in_frame": True} for _ in range(n)]
    robots = [{"selected_robot_pixels": 500, "other_robot_pixels": 0} for _ in range(n)]

    def write_video(path, images):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 25, (width, height))
        assert writer.isOpened()
        for frame in images:
            writer.write(frame)
        writer.release()

    valid = tmp_path / "valid.mp4"
    write_video(valid, frames)
    assert audit_capture_video(valid, expected=n, width=width, height=height,
        screen_evidence=evidence, robot_instance_evidence=robots)["pass"] is True
    black = tmp_path / "black.mp4"
    write_video(black, [np.zeros((height, width, 3), dtype=np.uint8) for _ in range(n)])
    failed = audit_capture_video(black, expected=n, width=width, height=height,
        screen_evidence=evidence, robot_instance_evidence=robots)
    assert failed["pass"] is False
    assert any("dark_scene" in issue or "flat_scene" in issue for issue in failed["issues"])


def test_capture_spec_uses_matching_eval_cell_and_pins_frame_audit_inputs(tmp_path):
    from foothold_s2.eval.ex42_render_capture import capture_spec_from_evaluation, validate_capture_spec

    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/pyramid_stairs"}, current_cap=9)
    request = next(row for row in plan["requests"]
                   if row["terrain_key"] == "A/pyramid_stairs" and row["map_mode"] == "eval_gt")

    n = 64
    kinds = np.asarray(["pyramid_stairs"] * 32 + ["stair_up"] * 32)
    cols = np.asarray([0] * 32 + [50] * 32, dtype=np.int64)
    levels = np.asarray([9] * 32 + [0] * 32, dtype=np.int64)
    alive = np.ones(n, dtype=np.bool_)
    alive[1] = False
    distance = np.full(n, 4.0, dtype=np.float32)
    arrays = tmp_path / "env_arrays_eval_gt_fwd1.0.npz"
    evaluation = tmp_path / "map_modes.json"
    _write_evaluation_artifacts(plan, mesh, arrays, kinds=kinds, cols=cols, levels=levels,
        alive=alive, distance=distance, evaluation=evaluation)

    selected = capture_spec_from_evaluation(
        plan, request["request_id"], evaluation, command_name="fwd1.0",
        role="success", source_root=tmp_path, source_head="a" * 40,
        recorder_sha256="b" * 64,
    )
    assert selected["env_id"] == 0
    assert selected["terrain_key"] == "A/pyramid_stairs"
    assert selected["fixed_level"] == 9
    assert selected["map_mode"] == "eval_gt"
    assert selected["evaluation_arrays_sha256"]
    assert selected["frame_audit_required"] is True
    assert validate_capture_spec(selected)["state"] == "verified"

    broken = dict(json.loads(evaluation.read_text(encoding="utf-8")))
    broken["ex42_mesh"] = dict(broken["ex42_mesh"], columns=["wrong"] + broken["ex42_mesh"]["columns"][1:])
    bad_evaluation = tmp_path / "map_modes_bad_mesh_columns.json"
    bad_evaluation.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="mesh SHA, or seed"):
        capture_spec_from_evaluation(
            plan, request["request_id"], bad_evaluation, command_name="fwd1.0",
            role="success", source_root=tmp_path, source_head="a" * 40,
            recorder_sha256="b" * 64)


def test_capture_spec_rejects_wrong_checkpoint_or_empty_role(tmp_path):
    from foothold_s2.eval.ex42_render_capture import capture_spec_from_evaluation

    mesh = _mesh_fixture(tmp_path)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/pyramid_stairs"}, current_cap=9)
    request = next(row for row in plan["requests"] if row["terrain_key"] == "A/pyramid_stairs")
    arrays = tmp_path / "env_arrays_eval_gt_fwd1.0.npz"
    np.savez(arrays, kind=np.asarray(["pyramid_stairs"]), terrain_col=np.asarray([0]),
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
    plan = build_render_plan(mesh, checkpoint, trained_kinds={"A/pyramid_stairs"}, current_cap=5)
    trained_levels = {row["terrain_level"] for row in plan["requests"]
                      if row["terrain_key"] == "A/pyramid_stairs"}
    untrained_levels = {row["terrain_level"] for row in plan["requests"]
                        if row["terrain_key"] == "B/stair_up"}
    assert trained_levels == {5, 9}
    assert untrained_levels == {0}
    assert len(plan["requests"]) == 18
