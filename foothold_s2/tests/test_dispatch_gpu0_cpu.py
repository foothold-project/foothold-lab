"""GPU0 adapter contract using a fake queue, never starting a child."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest


ENTRY = Path(__file__).resolve().parents[2] / "_out/tools/gpu_jobs/dispatch_gpu0.py"


def entry():
    spec = importlib.util.spec_from_file_location("dispatch_gpu0_test", ENTRY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_same_queue_lock_separate_state_and_gpu0_only(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    module = entry().configure()
    assert module.DISPATCH["gpu"] == 0
    assert module.LIVE["queue"] == "D:/mai-tmp/gpu/queue.json"
    assert module.DISPATCH["results"] == "D:/mai-tmp/gpu/results"
    assert module.DISPATCH["state"] != "D:/mai-tmp/gpu/dispatch_state.json"
    queue = tmp_path / "queue.json"
    with module.queue_lock(str(queue)):
        module.write_queue(str(queue), {"format": module.QUEUE_FORMAT, "items": []})
        assert module.read_queue(str(queue))["items"] == []
        assert Path(str(queue) + ".lock").exists()
    assert not Path(str(queue) + ".lock").exists()
    item = {"state": "대기", "kind": "render", "argv": ["python", "capture.py"],
            "gpu": 0, "priority": 3}
    assert module.item_ready(item, 100)[0]
    item["gpu"] = 1
    assert module.item_ready(item, 100) == (False, "other_gpu")


def test_live_training_marker_blocks_even_without_gpu_jobs(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    module = entry().configure()
    marker = tmp_path / "TRAINING_BUSY_GPU0"
    marker.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    assert module.marker_state(marker)["present"]
    assert "marker:" in module.p1_busy([], set(), [str(marker)])
    marker.write_text(json.dumps({"pid": 99999999}), encoding="utf-8")
    assert not module.marker_state(marker)["present"]
    assert module.p1_busy([], set(), [str(marker)]) is None


def test_unpinned_dispatch_or_remapped_ordinals_rejected(monkeypatch):
    module = entry()
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "1")
    with pytest.raises(RuntimeError, match="must be unset"):
        module.configure()
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES")
    monkeypatch.setattr(module, "SOURCE_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="SHA changed"):
        module.configure()
