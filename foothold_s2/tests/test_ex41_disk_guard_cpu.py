from __future__ import annotations

import json

import pytest
from pathlib import Path
from types import SimpleNamespace

from foothold_s2.scripts.ex41_startup import (
    _planner_disk_level,
    build_ex41_disk_plan,
    checkpoint_count_for_updates,
    record_ex41_disk_snapshot,
    validate_ex41_output_directory,
    write_ex41_disk_preflight,
)
from tools.wt_guard.disk_guard import GB


M6000_CHECKPOINT_BYTES = 26_895_071


def test_plan_uses_measured_m6000_size_interval_and_6500_update_window(tmp_path):
    output = tmp_path / "EX-41-B"
    plan = build_ex41_disk_plan(output, M6000_CHECKPOINT_BYTES, 50, free_bytes=10**12)

    assert plan["planned_updates"] == 6500
    assert plan["update_basis"] == [5000, 1500]
    assert plan["save_interval"] == 50
    assert checkpoint_count_for_updates(6500, 50) == 130
    assert plan["checkpoint_reserve_bytes"] == 130 * M6000_CHECKPOINT_BYTES
    assert plan["record_video_basis"]["run_non_checkpoint_bytes"] == 13_922_236_660
    assert plan["record_video_basis"]["raw_video_bytes"] == 193_355_567
    assert plan["record_video_basis"]["final_video_bytes"] == 133_030_760
    assert plan["record_video_basis"]["reference_updates"] == 8001
    assert plan["margin_bytes"] == 50_000_000_000


def test_start_gate_requires_d_drive_and_rejects_low_free_space(tmp_path):
    output = tmp_path / "EX-41-B"
    with pytest.raises(ValueError, match="absolute D:"):
        validate_ex41_output_directory("C:/runs/ex41")

    plan = build_ex41_disk_plan(output, M6000_CHECKPOINT_BYTES, 50, free_bytes=10**12)
    with pytest.raises(ValueError, match="below preflight reserve"):
        build_ex41_disk_plan(output, M6000_CHECKPOINT_BYTES, 50,
                             planned_updates=6500,
                             free_bytes=plan["required_free_bytes"] - 1)


def test_planner_disk_guard_function_accepts_and_blocks_known_free_space():
    def usage_with_free(free_bytes):
        return lambda _path: SimpleNamespace(free=free_bytes, total=2_000 * GB, used=0)

    path = Path("D:/runs/EX-41")
    threshold = 65 * GB
    assert _planner_disk_level(path, threshold,
                               usage_fn=usage_with_free(threshold + 1))["level"] == "ok"
    assert _planner_disk_level(path, threshold,
                               usage_fn=usage_with_free(threshold - 1))["level"] == "block"


def test_output_root_must_be_empty_before_launch(tmp_path):
    output = tmp_path / "EX-41-B"
    output.mkdir()
    (output / "old-run.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="new or empty"):
        validate_ex41_output_directory(output)


def test_preflight_receipt_is_persisted_in_the_selected_run_folder(tmp_path):
    output = tmp_path / "EX-41-B"
    plan = build_ex41_disk_plan(output, M6000_CHECKPOINT_BYTES, 50, free_bytes=10**12)
    receipt_path = write_ex41_disk_preflight(output, plan)
    assert receipt_path.name == "ex41_disk_preflight.json"
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == plan


def test_entrypoint_checks_capacity_before_applauncher_and_uses_exact_run_folder():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "scripts/train_start.py").read_text(
        encoding="utf-8")
    assert source.index("validate_ex41_output_directory(_pre_args.ex41_log_root)") < source.index(
        "app_launcher = AppLauncher(args_cli)")
    assert 'log_dir = os.path.abspath(args_cli.ex41_log_root)' in source
    assert "build_ex41_disk_plan(" in source
    assert "disk_guard=EX41_DISK_RECEIPT" in source
    assert "write_ex41_disk_preflight(log_dir, EX41_DISK_RECEIPT)" in source


def test_250_update_snapshot_appends_receipt_and_warns_without_stopping(tmp_path):
    output = tmp_path / "EX-41-B"
    output.mkdir()
    plan = build_ex41_disk_plan(output, M6000_CHECKPOINT_BYTES, 50, free_bytes=10**12)

    row = record_ex41_disk_snapshot(output, plan, 250, free_bytes=10**12)
    assert row["event"] == "disk_space_snapshot"
    assert row["completed_updates"] == 250
    assert row["remaining_checkpoint_count"] < plan["checkpoint_count"]
    event_file = output / "ex41_disk_guard.jsonl"
    assert json.loads(event_file.read_text(encoding="utf-8").splitlines()[0]) == row

    with pytest.warns(RuntimeWarning, match="below threshold"):
        warning = record_ex41_disk_snapshot(output, plan, 500, free_bytes=0)
    assert warning["event"] == "disk_space_warning"
    rows = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines()]
    assert [item["completed_updates"] for item in rows] == [250, 500]


def test_snapshot_rejects_non_250_update_boundary(tmp_path):
    output = tmp_path / "EX-41-B"
    plan = build_ex41_disk_plan(output, M6000_CHECKPOINT_BYTES, 50, free_bytes=10**12)
    with pytest.raises(ValueError, match="250-update boundaries"):
        record_ex41_disk_snapshot(output, plan, 251, free_bytes=10**12)


def test_runner_invokes_guard_after_each_250th_ex41_update():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "runners/start_runner.py").read_text(
        encoding="utf-8")
    assert 'disk_guard = self.cfg.get("ex41_disk_guard")' in source
    assert "disk_guard is not None and it % 250 == 0" in source
    assert "record_ex41_disk_snapshot(self.log_dir, disk_guard, it)" in source
