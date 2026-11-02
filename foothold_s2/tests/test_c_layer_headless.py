"""CPU checks for the C-layer camera launcher and pinned capture plan."""
from __future__ import annotations

import argparse
from pathlib import Path

from foothold_s2.eval import plan_c_layer
from foothold_s2.eval.video25 import record_c_layer


def test_capture_launcher_forces_offscreen_camera_even_with_gui_inputs():
    args = argparse.Namespace(headless=False, enable_cameras=False, livestream=2)
    actual = record_c_layer.configure_capture_launcher(args)
    assert actual is args
    assert (actual.headless, actual.enable_cameras, actual.livestream) == (True, True, 0)


def test_all_c_layer_rows_pin_headless_camera_args(tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    source_recorder = source / "foothold_s2/eval/record_sol23f.py"
    source_recorder.parent.mkdir(parents=True)
    source_recorder.write_text("# recorder\n", encoding="utf-8")
    checkpoint = tmp_path / "model_6000.pt"
    recorder = tmp_path / "record_c_layer.py"
    composer = tmp_path / "compose.py"
    python = tmp_path / "python.exe"
    for path in (checkpoint, recorder, composer, python):
        path.write_bytes(b"fixture")

    monkeypatch.setattr(plan_c_layer, "_head", lambda _source: "a" * 40)
    monkeypatch.setattr(plan_c_layer.queue, "sha256", lambda path: (
        "d5e9ec40" + "0" * 56 if Path(path) == checkpoint else "b" * 64))
    monkeypatch.setattr(plan_c_layer.queue, "validate_plan", lambda _plan: {"ready": 216})
    layout = {kind: (index, index) for index, kind in enumerate(
        plan_c_layer.KINDS["continuous"] + plan_c_layer.KINDS["sparse"])}
    monkeypatch.setattr(plan_c_layer, "assignments", lambda: layout)

    plan = plan_c_layer.build_plan(
        checkpoint=checkpoint, source_root=source, recorder=recorder,
        composer=composer, python=python, playlist_dir=tmp_path / "playlists",
        priority_markers={"training": tmp_path / "training.busy"}, device="cuda:1")
    assert len(plan["jobs"]) == 216
    for row in plan["jobs"]:
        argv = row["recorder_argv"]
        assert argv[-4:] == ["--headless", "--enable_cameras", "--livestream", "0"]
        assert argv[argv.index("--device") + 1] == "cuda:1"
