"""Known-input P1 marker and P4 gate tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[2] / "_out/tools/gpu_jobs/gpu_jobs.py"
SPEC = importlib.util.spec_from_file_location("ex41_gpu_jobs", SOURCE)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def marker(path: Path, *, created=100.0):
    path.write_text(json.dumps({"job": "ex41-eval", "pid": 42,
                                "process_create_time": created,
                                "started_at": "2026-11-02T21:00:00+09:00",
                                "iteration": 1500}), encoding="utf-8")


def config(path: Path):
    return {"sources": {"ex41_p1_marker": str(path)},
            "jobs": [{"id": "c-layer", "priority": 4, "gpu": 1},
                     {"id": "w78-video", "priority": 4, "gpu": 1}]}


def test_active_marker_yields_both_render_jobs(tmp_path, monkeypatch):
    path = tmp_path / "busy.json"
    marker(path)
    monkeypatch.setattr(GATE, "psutil", SimpleNamespace(
        Process=lambda _pid: SimpleNamespace(create_time=lambda: 100.0, is_running=lambda: True),
        NoSuchProcess=LookupError, AccessDenied=PermissionError))
    for job in ("c-layer", "w78-video"):
        result = GATE.admission(config(path), job)
        assert result["admit_next_unit"] is False
        assert result["marker"]["state"] == "active"


def test_dead_or_reused_pid_does_not_block(tmp_path, monkeypatch):
    path = tmp_path / "busy.json"
    marker(path)
    fake = SimpleNamespace(Process=lambda _pid: SimpleNamespace(
        create_time=lambda: 200.0, is_running=lambda: True),
        NoSuchProcess=LookupError, AccessDenied=PermissionError)
    monkeypatch.setattr(GATE, "psutil", fake)
    assert GATE.admission(config(path), "c-layer")["marker"]["state"] == "stale"
    assert GATE.admission(config(path), "c-layer")["admit_next_unit"] is True
    fake.Process = lambda _pid: (_ for _ in ()).throw(LookupError())
    assert GATE.admission(config(path), "w78-video")["admit_next_unit"] is True


def test_unknown_marker_fails_closed(tmp_path):
    path = tmp_path / "busy.json"
    path.write_text("{}", encoding="utf-8")
    assert GATE.admission(config(path), "c-layer")["marker"]["state"] == "unknown"
    assert GATE.admission(config(path), "c-layer")["admit_next_unit"] is False


def test_c_layer_queue_calls_gate_before_attempt(tmp_path, monkeypatch):
    from foothold_s2.eval import c_layer_queue as queue
    from foothold_s2.tests.test_c_layer_queue import fixture

    plan, _ = fixture(tmp_path)
    monkeypatch.setattr(queue, "_gpu_gate", lambda _plan, _job: {
        "job": "c-layer", "admit_next_unit": False, "reason": "ex41_p1_active"})
    result = queue.run_one(plan, out=tmp_path / "out", high_priority_markers=[])
    assert result["state"] == "yielded_to_higher_priority"
    assert not (tmp_path / "out").exists()
