"""Known-input mesh and five-repeat calibration preflight without Kit or GPU."""
import hashlib
import json
import os

import numpy as np
import pytest

from foothold_s2.eval.ex42_mesh_eval import preflight, validate_eval_cell
from foothold_s2.eval.fixed_terrain import assignment_sha256, fixed_assignment
from foothold_s2.ex42_calibrate import SEEDS, main, summarize
from foothold_s2.ex42_eval_once import commands


def mesh_fixture(tmp_path):
    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], np.float32)
    faces = np.array([[0, 1, 2]], np.int32)
    origins = np.zeros((10, 76, 3))
    family = np.array(["A"] * 50 + ["B"] * 12 + ["C"] * 7 + ["D"] * 3 + ["E"] * 4)
    sha = hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest()
    np.savez(tmp_path / "terrain_mesh.npz", vertices=vertices, faces=faces,
             origins=origins, column_family=family)
    manifest = {"format": "foothold-ex42-combined-mesh/1", "seed": 42,
                "families_present": ["A", "B", "C", "D", "E"], "families_missing": [],
                "mesh_sha256": sha, "origins_shape": [10, 76, 3]}
    (tmp_path / "mesh_manifest.json").write_text(json.dumps(manifest))
    return manifest


def test_mesh_preflight_and_all_child_arguments(tmp_path):
    manifest = mesh_fixture(tmp_path)
    record = preflight(tmp_path)
    assert record["mesh_sha256"] == manifest["mesh_sha256"]
    assert len(record["columns"]) == 76
    assert record["eval_cols"] == 23
    assert record["eval_columns"] == record["columns"][:23]
    rows = commands("model.pt", tmp_path / "out", "cuda:1", eval_seed=44, mesh_dir=tmp_path)
    assert len(rows) == 5
    for row in (rows[0], rows[-1]):
        assert row["argv"][row["argv"].index("--mesh-dir") + 1] == str(tmp_path)
        assert row["argv"][row["argv"].index("--eval-seed") + 1] == "44"
    for row in rows[1:4]:
        assert row["argv"][row["argv"].index("--seed") + 1] == "44"
        assert "--mesh-dir" not in row["argv"]  # stance protocol is a plane
    manifest["mesh_sha256"] = "0" * 64
    (tmp_path / "mesh_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="mesh sha256"):
        preflight(tmp_path)


def test_a23_cell_rejects_the_old_76_column_reference(tmp_path):
    mesh_fixture(tmp_path)
    mesh = preflight(tmp_path)
    levels, types = fixed_assignment(64, 10, 23)
    result = {"envs": 64, "fixed_terrain": {"rows": 10, "cols": 23, "num_envs": 64,
              "fixed_level": None, "assignment_sha256": assignment_sha256(levels, types)},
              "terrain_tiles": [{"env": i, "column": int(types[i]), "level": int(levels[i]),
                                 "kind": mesh["eval_columns"][int(types[i])]} for i in range(64)]}
    validate_eval_cell(result, mesh)
    result["fixed_terrain"]["cols"] = 76
    with pytest.raises(ValueError, match="A continuous 23"):
        validate_eval_cell(result, mesh)
    result["fixed_terrain"]["cols"] = 23
    result["terrain_tiles"][42]["column"] = 50
    with pytest.raises(ValueError, match="terrain tiles"):
        validate_eval_cell(result, mesh)


def test_real_c333_mesh_matches_parent_map64_env_by_env():
    mesh_dir = os.environ.get("EX42_REAL_MESH")
    parent_path = os.environ.get("EX42_PARENT_MAP64")
    if not mesh_dir or not parent_path:
        pytest.skip("set EX42_REAL_MESH and EX42_PARENT_MAP64 for the real input comparison")
    mesh = preflight(mesh_dir)
    parent = json.loads(open(parent_path, encoding="utf-8-sig").read())
    levels, types = fixed_assignment(64, 10, mesh["eval_cols"])
    result = {"envs": 64, "fixed_terrain": {"rows": 10, "cols": 23, "num_envs": 64,
              "fixed_level": None, "assignment_sha256": assignment_sha256(levels, types)},
              "terrain_tiles": [{"env": i, "column": int(types[i]), "level": int(levels[i]),
                                 "kind": mesh["eval_columns"][int(types[i])]} for i in range(64)]}
    validate_eval_cell(result, mesh)
    assert parent["fixed_terrain"]["assignment_sha256"] == result["fixed_terrain"]["assignment_sha256"]
    assert result["fixed_terrain"]["assignment_sha256"].startswith("c3884d68")
    assert [(r["kind"], r["level"], r["column"]) for r in result["terrain_tiles"]] == [
        (r["kind"], r["level"], r["column"]) for r in parent["terrain_tiles"]]


def _scores():
    scores, receipts = [], []
    for i, seed in enumerate(SEEDS):
        value = 1 if i < 2 else i + 1
        scores.append({"checkpoint_sha256": "a" * 64, "conditions": {"eval_seed": seed},
                       "map64": {"eval_gt": {"spin+1.2": {"alive_at_end": 60 + value,
                          "vx_abs_error_median_mps": .1 * value,
                          "vy_abs_error_median_mps": .2 * value,
                          "wz_abs_error_median_radps": .3 * value,
                          "command_projection_median_m": .4 * value}}},
                       "stand": {"eval_gt": {"per_foot_contact_fraction_median": {"FL_foot": .05 * value}}},
                       "axis_v2": {"eval_gt": {"spin+1.2": {
                           "duty_by_foot_median": [.1 * value],
                           "phase_from_FL_cycle_median": [.2 * value],
                           "foot_drag_proxy_m_by_foot_median": [.3 * value],
                           "yaw_signed_accum_median_rad": .4 * value}}}})
        receipts.append({"state": "done", "eval_seed": seed, "checkpoint_sha256": "a" * 64,
                         "source_git_head": "fixed-head", "ex42_mesh": {"mesh_sha256": "b" * 64,
                                                                           "eval_cols": 23}})
    return scores, receipts


def test_five_repeat_widths_and_mismatch_guards():
    scores, receipts = _scores()
    row = summarize(scores, receipts, "b" * 64, "a" * 64)
    assert row["seeds"] == [42, 42, 43, 44, 45]
    assert row["item_widths"]["survival"]["max_same_seed_width"] == 0
    assert row["item_widths"]["survival"]["max_all_seed_width"] == 4
    assert all(row["item_widths"][key]["state"] == "measured" for key in (
        "tracking_vx_vy", "tracking_wz", "command_projection", "per_foot_contact",
        "gait_phase_and_duty", "foot_drag_m", "yaw_integral", "W57_spin_survival"))
    receipts[2]["ex42_mesh"]["mesh_sha256"] = "wrong"
    with pytest.raises(ValueError, match="repeat 2"):
        summarize(scores, receipts, "b" * 64, "a" * 64)
    receipts[2]["ex42_mesh"].update(mesh_sha256="b" * 64, eval_cols=76)
    with pytest.raises(ValueError, match="repeat 2"):
        summarize(scores, receipts, "b" * 64, "a" * 64)


def test_missing_metric_is_not_silently_averaged():
    scores, receipts = _scores()
    del scores[4]["axis_v2"]["eval_gt"]["spin+1.2"]["foot_drag_proxy_m_by_foot_median"]
    scores[2]["axis_v2"]["eval_gt"]["spin+1.2"]["phase_from_FL_cycle_median"] = None
    row = summarize(scores, receipts, "b" * 64, "a" * 64)
    assert row["missing_by_repeat"]["axis_v2/eval_gt/spin+1.2/foot_drag_proxy_m_by_foot_median/0"] == [4]
    assert row["missing_by_repeat"]["axis_v2/eval_gt/spin+1.2/phase_from_FL_cycle_median/0"] == [2]
    assert "axis_v2/eval_gt/spin+1.2/phase_from_FL_cycle_median/0" not in row["metric_widths"]
    assert row["item_widths"]["gait_phase_and_duty"]["state"] == "measured"
    assert row["item_widths"]["foot_drag_m"]["state"] == "missing_in_repeat"
    assert row["item_widths"]["foot_drag_m"]["max_all_seed_width"] is None


def test_76_column_reference_requires_explicit_scope():
    scores, receipts = _scores()
    for receipt in receipts:
        del receipt["ex42_mesh"]["eval_cols"]
    with pytest.raises(ValueError, match="repeat 0"):
        summarize(scores, receipts, "b" * 64, "a" * 64)
    row = summarize(scores, receipts, "b" * 64, "a" * 64, eval_cols=76)
    assert row["comparison_scope"] == "historical_76_reference"


def test_nonfinite_metric_still_rejected():
    scores, receipts = _scores()
    scores[2]["axis_v2"]["eval_gt"]["spin+1.2"]["phase_from_FL_cycle_median"] = float("nan")
    with pytest.raises(ValueError, match="nonfinite calibration value"):
        summarize(scores, receipts, "b" * 64, "a" * 64)


def test_summarize_only_reads_five_saved_outputs_without_launch(tmp_path, monkeypatch):
    from foothold_s2.ex42_score import digest

    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir()
    mesh = mesh_fixture(mesh_dir)
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"known checkpoint")
    checkpoint_sha = digest(checkpoint)
    scores, receipts = _scores()
    for i, (score, receipt) in enumerate(zip(scores, receipts)):
        folder = tmp_path / "saved" / f"repeat_{i:02d}"
        (folder / "map64").mkdir(parents=True)
        score["checkpoint_sha256"] = checkpoint_sha
        receipt["checkpoint_sha256"] = checkpoint_sha
        receipt["ex42_mesh"]["mesh_sha256"] = mesh["mesh_sha256"]
        (folder / "ex42_score.json").write_text(json.dumps(score))
        (folder / "eval_receipt.json").write_text(json.dumps(receipt))
        (folder / "map64" / "map_modes.json").write_text(json.dumps({"fixed_terrain": {"cols": 23}}))
    monkeypatch.setattr("foothold_s2.ex42_calibrate.subprocess.run", lambda *_a, **_kw: pytest.fail("launched child"))
    argv = ["--checkpoint", str(checkpoint), "--expected-sha256", checkpoint_sha,
            "--mesh-dir", str(mesh_dir), "--expected-mesh-sha256", mesh["mesh_sha256"],
            "--out", str(tmp_path / "saved"), "--device", "cuda:1", "--summarize-only",
            "--summary-output", str(tmp_path / "summary.json")]
    assert main(argv) == 0
    assert json.loads((tmp_path / "summary.json").read_text())["comparison_scope"] == "a23_parent_matched"
    with pytest.raises(FileExistsError):
        main(argv)
    (tmp_path / "saved" / "repeat_04" / "ex42_score.json").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        main(argv[:-1] + [str(tmp_path / "second.json")])
