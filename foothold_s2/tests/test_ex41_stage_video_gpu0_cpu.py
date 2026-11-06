"""Known-input GPU0 training guard and CLI tests; no Kit or GPU."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from foothold_s2.eval import ex41_stage_video as video


class Live:
    def __init__(self, pid):
        self.pid = pid

    def create_time(self):
        return 123.0


def absent(pid):
    raise psutil.NoSuchProcess(pid)


def test_live_training_marker_rejects_gpu0_but_not_gpu1(tmp_path: Path):
    marker = tmp_path / "TRAINING_BUSY_GPU0"
    marker.write_text(json.dumps({"pid": 94296, "process_created_at": 123.0}), encoding="utf-8")
    with pytest.raises(ValueError, match="GPU0 training is active: pid 94296"):
        video.assert_gpu0_training_idle("cuda:0", marker, Live)
    video.assert_gpu0_training_idle("cuda:1", marker, Live)


def test_stale_marker_and_pid_reuse_do_not_claim_live_training(tmp_path: Path):
    marker = tmp_path / "TRAINING_BUSY_GPU0"
    marker.write_text(json.dumps({"pid": 94296, "process_created_at": 123.0}), encoding="utf-8")
    video.assert_gpu0_training_idle("cuda:0", marker, absent)
    marker.write_text(json.dumps({"pid": 94296, "process_created_at": 120.0}), encoding="utf-8")
    video.assert_gpu0_training_idle("cuda:0", marker, Live)


@pytest.mark.parametrize("contents", ["{", "{}", '{"pid":94296}'])
def test_unreadable_or_incomplete_marker_fails_closed(tmp_path: Path, contents: str):
    marker = tmp_path / "TRAINING_BUSY_GPU0"
    marker.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="GPU0 training marker"):
        video.assert_gpu0_training_idle("cuda:0", marker, Live)


def test_run_checks_gpu0_before_checkpoint_or_capture(monkeypatch):
    def blocked(device):
        assert device == "cuda:0"
        raise ValueError("GPU0 training is active")

    monkeypatch.setattr(video, "assert_gpu0_training_idle", blocked)
    with pytest.raises(ValueError, match="GPU0 training is active"):
        video.run(SimpleNamespace(device="cuda:0"))


def test_parser_accepts_both_devices_and_passes_recorder_device(monkeypatch, tmp_path: Path):
    seen = []

    def fake_run(args):
        seen.append(args.device)
        return {"state": "planned"}

    monkeypatch.setattr(video, "run", fake_run)
    required = ["--checkpoint", "c.pt", "--source-root", "src", "--recorder", "r.py",
                "--composer", "c.py", "--python", "python.exe", "--gpu-jobs-config", "jobs.json",
                "--out", "out", "--playlist-root", "playlist", "--iteration", "750",
                "--stage-name", "S2d", "--suite", "W80", "--case", "stairs_fwd",
                "--mode", "eval_gt", "--plan-only"]
    for device in ("cuda:0", "cuda:1"):
        assert video.main(required + ["--device", device]) == 0
    assert seen == ["cuda:0", "cuda:1"]
    args = SimpleNamespace(suite="W80", case="stairs_fwd", mode="eval_gt", iteration=750,
                           python=Path("python.exe"), recorder=Path("r.py"),
                           checkpoint=Path("c.pt"), device="cuda:0")
    cmd, _ = video.recorder_argv(args, {"command": [0.5, 0, 0]}, tmp_path)
    assert cmd[cmd.index("--device") + 1] == "cuda:0"
