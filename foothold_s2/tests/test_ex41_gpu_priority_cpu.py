"""CPU tests for EX-41 priority marker ownership and gpu_jobs stale-PID handling."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import psutil
import pytest

from foothold_s2.eval.ex41_gpu_priority import (
    DEFAULT_MARKER, clear_marker, gpu0_priority,
    gpu1_priority, publish_marker,
)
from foothold_s2 import ex41_eval_once


def test_default_marker_uses_d138_gpu_path():
    assert DEFAULT_MARKER == Path("D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1")


def test_gpu0_training_markers_claim_both_c_layer_and_gpu_jobs_paths(tmp_path, monkeypatch):
    from foothold_s2.eval import ex41_gpu_priority as priority

    markers = (tmp_path / "c-layer" / "TRAINING_BUSY",
               tmp_path / "gpu" / "TRAINING_BUSY_GPU0")
    monkeypatch.setattr(priority, "DEFAULT_GPU0_MARKERS", markers)
    eval_marker = tmp_path / "gpu" / "PRIORITY_BUSY_GPU0"
    monkeypatch.setattr(priority, "DEFAULT_GPU0_EVAL_MARKER", eval_marker)
    monkeypatch.setattr(priority, "_process_created_at", lambda pid: 123.0)
    with gpu0_priority(job="EX-41-training", iteration=6000, run="C:/known/run") as owners:
        assert [Path(item["path"]) for item in owners] == [eval_marker, *markers]
        for marker in (eval_marker, *markers):
            row = json.loads(marker.read_text(encoding="utf-8"))
            assert row["job"] == "EX-41-training"
            assert row["pid"] > 0
            assert row["process_created_at"] == 123.0
            assert row["iteration"] == 6000
            assert row["run"] == "C:/known/run"
    assert all(not marker.exists() for marker in (eval_marker, *markers))


def test_gpu0_marker_partial_claim_rolls_back_our_first_marker(tmp_path, monkeypatch):
    from foothold_s2.eval import ex41_gpu_priority as priority

    first = tmp_path / "first" / "TRAINING_BUSY"
    occupied = tmp_path / "occupied" / "TRAINING_BUSY"
    occupied.parent.mkdir(parents=True)
    foreign = publish_marker(occupied, job="foreign", iteration=1,
                             pid=psutil.Process().pid,
                             process_created_at=psutil.Process().create_time())
    monkeypatch.setattr(priority, "DEFAULT_GPU0_MARKERS", (first, occupied))
    monkeypatch.setattr(priority, "_process_created_at", lambda _pid: psutil.Process().create_time())
    with pytest.raises(RuntimeError, match="already owned"):
        priority.publish_gpu0_busy_markers(job="EX-41-training:test-run", iteration=0)
    assert not first.exists()
    assert json.loads(occupied.read_text(encoding="utf-8")) == foreign


def test_gpu0_priority_clears_owned_markers_after_exception(tmp_path, monkeypatch):
    from foothold_s2.eval import ex41_gpu_priority as priority

    markers = (tmp_path / "c-layer" / "TRAINING_BUSY",
               tmp_path / "gpu" / "TRAINING_BUSY_GPU0")
    eval_marker = tmp_path / "gpu" / "PRIORITY_BUSY_GPU0"
    monkeypatch.setattr(priority, "DEFAULT_GPU0_MARKERS", markers)
    monkeypatch.setattr(priority, "DEFAULT_GPU0_EVAL_MARKER", eval_marker)
    monkeypatch.setattr(priority, "_process_created_at", lambda _pid: 456.0)
    with pytest.raises(RuntimeError, match="known failure"):
        with gpu0_priority(job="push-ladder", iteration=6000):
            assert all(path.is_file() for path in (eval_marker, *markers))
            raise RuntimeError("known failure")
    assert all(not path.exists() for path in (eval_marker, *markers))


def test_marker_writes_exact_contract_and_clears_only_owner(tmp_path):
    marker = tmp_path / "PRIORITY_BUSY_GPU1"
    pid = psutil.Process().pid
    created = psutil.Process(pid).create_time()
    row = publish_marker(marker, job="ex41_w78", iteration=6250,
                         pid=pid, process_created_at=created,
                         started_at="2026-11-02T12:00:00+09:00")
    assert set(row) == {"job", "pid", "process_created_at", "started_at", "iteration"}
    assert json.loads(marker.read_text(encoding="utf-8")) == row
    replacement = dict(row, job="other")
    assert not clear_marker(marker, replacement)
    assert marker.exists()
    assert clear_marker(marker, row)
    assert not marker.exists()


def test_marker_context_clears_after_failure(tmp_path):
    marker = tmp_path / "PRIORITY_BUSY_GPU1"
    with pytest.raises(RuntimeError, match="known failure"):
        with gpu1_priority(marker, job="ex41_shadow_eval", iteration=500):
            assert json.loads(marker.read_text(encoding="utf-8"))["iteration"] == 500
            raise RuntimeError("known failure")
    assert not marker.exists()


def test_gpu_jobs_treats_dead_marker_pid_as_stale(tmp_path):
    source = Path("C:/mai/wt/foothold-lab/lead_tmp-20261023/_out/tools/gpu_jobs/gpu_jobs.py")
    if not source.is_file():
        pytest.skip("local gpu_jobs checkout is unavailable")
    spec = importlib.util.spec_from_file_location("ex41_test_gpu_jobs", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    marker = tmp_path / "PRIORITY_BUSY_GPU1"
    marker.write_text(json.dumps({"job": "ex41_w78", "pid": 2_147_483_647,
                                  "process_created_at": 1.0,
                                  "started_at": "2026-11-02T12:00:00+09:00",
                                  "iteration": 6250}), encoding="utf-8")
    result = module.marker_state(marker)
    assert result == {"present": False, "reason": "stale_pids", "pids": [2_147_483_647]}


@pytest.mark.parametrize("child_rc, expected_state", [(0, "done"), (7, "failed")])
def test_evaluation_bundle_publishes_marker_for_child_and_clears_it(
        tmp_path, monkeypatch, child_rc, expected_state):
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"checkpoint")
    cfg_path = tmp_path / "eval.json"
    cfg_path.write_text("{}", encoding="utf-8")
    out = tmp_path / "bundle"
    marker = tmp_path / "gpu" / "PRIORITY_BUSY_GPU1"

    class Plan:
        fixed_schedule = True
        parent_sha256 = "p" * 64
        effective_sha256 = "s" * 64

    observed = []

    monkeypatch.setattr(ex41_eval_once, "load_plan", lambda *_args, **_kwargs: Plan())
    monkeypatch.setattr(ex41_eval_once, "config", lambda *_args: {"envs": 64, "eval_seed": 42,
                                                                    "map_steps": 2, "stand_seconds": 1,
                                                                    "stand_skip_seconds": 0,
                                                                    "stand": {"contact_force_n": 1}})
    monkeypatch.setattr(ex41_eval_once.subprocess, "check_output",
                        lambda *_args, **_kwargs: "" if "--short" in _args[0] else "head")
    def known_commands(_checkpoint, root, _cfg, *, scope="all"):
        assert scope == "core"
        return [{"name": name, "argv": ["known-child", "--out", str(root / name)]}
                for name in ex41_eval_once.CORE_PHASES]

    monkeypatch.setattr(ex41_eval_once, "commands", known_commands)

    def fake_child(argv, *_args, **_kwargs):
        argv = list(argv)
        output = Path(argv[argv.index("--out") + 1])
        assert output.is_dir()
        row = json.loads(marker.read_text(encoding="utf-8"))
        observed.append(row)
        return {"rc": child_rc, "state": "done" if child_rc == 0 else "failed"}

    monkeypatch.setattr(ex41_eval_once, "hidden_child", fake_child)
    assert Plan.fixed_schedule is True
    assert not out.exists()
    row = ex41_eval_once.evaluate(checkpoint, out, eval_config=cfg_path,
                                  priority_marker=marker, scope="core")
    assert observed and observed[0]["job"] == "ex41_evaluation_bundle"
    assert observed[0]["iteration"] == 500
    assert row["state"] == expected_state
    assert row["gpu1_priority_marker"]["state"] == "cleared"
    assert not marker.exists()
