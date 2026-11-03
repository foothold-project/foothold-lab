from __future__ import annotations

import hashlib
import json

import pytest

from foothold_s2.eval.ex41_push_ladder import (
    PUSH250_MAGNITUDES_MPS,
    TERRAIN_CASES,
    build_push250_case_grid,
    summarize_push250,
)
from foothold_s2.eval.ex41_push250_watch import (
    _explicit_device,
    build_child_argv,
    checkpoint_for_update,
    output_path_for_global_iteration,
)


def test_push250_grid_is_d171_minimal_profile():
    cases = build_push250_case_grid()
    assert PUSH250_MAGNITUDES_MPS == (1.0, 1.5, 2.0)
    assert len(cases) == 3 * 3 * 8
    assert {row["terrain"] for row in cases} == set(TERRAIN_CASES)
    assert {row["magnitude_mps"] for row in cases} == {1.0, 1.5, 2.0}
    assert {row["direction_deg"] for row in cases} == {0, 45, 90, 135, 180, 225, 270, 315}
    assert {(row["map_mode"], row["command"], row["envs"], row["level"])
            for row in cases} == {("eval_gt", "walk_1.0", 64, 0)}


def test_push250_criterion_uses_worst_direction_at_1_5_only():
    rows = []
    for magnitude in PUSH250_MAGNITUDES_MPS:
        for direction in (0, 45, 90, 135, 180, 225, 270, 315):
            survivors = 57 if magnitude == 1.5 and direction == 90 else 64
            rows.append({"terrain": "flat", "map_mode": "eval_gt", "command": "walk_1.0",
                         "magnitude_mps": magnitude, "direction_deg": direction,
                         "envs": 64, "survivors_after_5s": survivors,
                         "recovery_times_s": [0.5] * survivors + [None] * (64 - survivors),
                         "max_tilt_rad": 0.2})
    summary = summarize_push250(rows, terrain="flat")
    assert summary["d171_1_5_worst_direction"]["survival_fraction"] == 57 / 64
    assert summary["d171_1_5_worst_direction"]["passed"] is False
    assert set(summary["record_only_magnitudes"]) == {"1.0", "2.0"}
    assert summary["record_only_magnitudes"]["2.0"]["survival_fraction"] == 1.0


def test_push250_rejects_missing_or_duplicate_direction_cell():
    cases = build_push250_case_grid(terrain="flat")
    rows = [{"terrain": row["terrain"], "map_mode": row["map_mode"], "command": row["command"],
             "magnitude_mps": row["magnitude_mps"], "direction_deg": row["direction_deg"],
             "envs": 64, "survivors_after_5s": 64, "recovery_times_s": [0.2] * 64,
             "max_tilt_rad": 0.1} for row in cases]
    with pytest.raises(ValueError, match="unique cells"):
        summarize_push250(rows[:-1], terrain="flat")
    with pytest.raises(ValueError, match="unique cells"):
        summarize_push250(rows + [rows[0]], terrain="flat")


def test_checkpoint_requires_completed_update_manifest_score_and_sha(tmp_path):
    run_dir = tmp_path / "run"
    score_dir = tmp_path / "scores"
    run_dir.mkdir()
    score_dir.mkdir()
    checkpoint = run_dir / "model_500.pt"
    checkpoint.write_bytes(b"known checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {"progress": {"completed_updates": 500},
                "checkpoints": {"model_500.pt": digest}}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    score = {"evaluation_state": "complete", "checkpoint_iteration": 500,
             "checkpoint_sha256": digest}
    (score_dir / f"score_500_{digest[:12]}.json").write_text(json.dumps(score), encoding="utf-8")
    ready = checkpoint_for_update(run_dir, score_dir, 500)
    assert ready["checkpoint"] == checkpoint
    assert ready["sha256"] == digest
    assert checkpoint_for_update(run_dir, score_dir, 501) is None
    score["checkpoint_sha256"] = "0" * 64
    (score_dir / f"score_500_{digest[:12]}.json").write_text(json.dumps(score), encoding="utf-8")
    assert checkpoint_for_update(run_dir, score_dir, 500) is None


def test_output_iteration_uses_global_m6000_parent_offset(tmp_path):
    assert output_path_for_global_iteration(tmp_path, 6000).name == "6000.json"
    assert output_path_for_global_iteration(tmp_path, 6500).name == "6500.json"
    with pytest.raises(ValueError):
        output_path_for_global_iteration(tmp_path, 0)


def test_child_command_is_gpu1_and_matches_d171_request(tmp_path):
    argv = build_child_argv(checkpoint=tmp_path / "model_500.pt", out=tmp_path / "flat",
                            terrain="flat")
    assert "--push-ladder-profile" in argv
    assert argv[argv.index("--push-ladder-profile") + 1] == "push250"
    assert argv[argv.index("--push-ladder-command") + 1] == "walk_1.0"
    assert argv[argv.index("--push-ladder-map-mode") + 1] == "eval_gt"
    assert argv[argv.index("--device") + 1] == "cuda:1"
    assert argv[argv.index("--envs") + 1] == "1536"
    with pytest.raises(ValueError, match="restricted to GPU1"):
        build_child_argv(checkpoint=tmp_path / "model_500.pt", out=tmp_path / "flat",
                         terrain="flat", device="cuda:0")


def test_gpu_assignment_ignores_shared_context_on_gpu0():
    assert _explicit_device(["python.exe", "train.py", "--device=cuda:0"]) == "cuda:0"
    assert _explicit_device(["python.exe", "record_c_layer.py", "--device", "cuda:1"]) == "cuda:1"
    assert _explicit_device(["python.exe", "score_watch.py"]) is None
