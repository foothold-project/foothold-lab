from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from foothold_s2.ex40_score_watch import _manifest_digest
from foothold_s2.eval import ex41_push250_watch as push250
from foothold_s2.scripts.ex41_startup import (
    assert_no_undefined_names,
    configure_stage_rehearsal_plan,
)
from foothold_s2.curriculum.continuous import load_plan


TABLE = Path("foothold_s2/curriculum/ex41-fixed5000.yaml").resolve()


def test_i09_manifest_model_name_and_sha_is_ready_without_n_plus_one(tmp_path):
    digest = "a" * 64
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema": "foothold-manifest/1",
        "progress": {"completed_updates": 250},
        "checkpoints": {"model_250.pt": digest},
    }), encoding="utf-8")
    assert _manifest_digest(tmp_path, 250) == digest


def test_i11_push_watcher_waits_outside_marker_then_claims_idle_gpu(tmp_path):
    calls = []
    snapshots = iter([
        {"state": "busy", "marker_state": "absent", "busy": [{"pid": 8}]},
        {"state": "idle", "marker_state": "absent", "busy": []},
        {"state": "busy", "marker_state": "live", "busy": [{"pid": 44}]},
    ])

    class Marker:
        def __enter__(self):
            calls.append("claim")
            return {"pid": 44}

        def __exit__(self, *_args):
            calls.append("release")

    def priority(*_args, **_kwargs):
        calls.append("priority_factory")
        return Marker()

    with push250.gpu1_idle_priority(
        tmp_path / "marker", job="test", iteration=6500,
        timeout_seconds=5, poll_seconds=0,
        snapshot=lambda _marker: next(snapshots), priority=priority,
        sleep=lambda _seconds: None,
    ) as (owner, snapshot):
        assert owner["pid"] == 44
        assert snapshot["state"] == "busy"
        assert calls == ["priority_factory", "claim"]
    assert calls[-1] == "release"


def test_i11_busy_gpu_timeout_never_claims_marker(tmp_path):
    claims = []

    @contextmanager
    def forbidden_claim(*_args, **_kwargs):
        claims.append(True)
        yield {"pid": 1}

    with pytest.raises(TimeoutError, match="bounded push250 wait"):
        with push250.gpu1_idle_priority(
            tmp_path / "marker", job="test", iteration=6500,
            timeout_seconds=-1, poll_seconds=0,
            snapshot=lambda _marker: {"state": "busy", "busy": [{"pid": 99}]},
            priority=forbidden_claim, sleep=lambda _seconds: None,
        ):
            pytest.fail("busy GPU must never be claimed")
    assert claims == []


def test_i13_restart_skips_matching_terminal_result_and_advances(tmp_path, monkeypatch):
    run, scores, out = tmp_path / "run", tmp_path / "scores", tmp_path / "push"
    run.mkdir(); scores.mkdir(); out.mkdir()
    destination = push250.output_path_for_global_iteration(out, 6500)
    destination.write_text(json.dumps({
        "state": "done", "local_iteration": 500, "global_iteration": 6500,
        "checkpoint_sha256": "b" * 64,
    }), encoding="utf-8")
    waits = []

    def checkpoint_wait(_run, _scores, iteration, **kwargs):
        waits.append(iteration)
        if iteration == 500:
            return {"sha256": "b" * 64}
        raise RuntimeError("test stopped after the watcher advanced")

    monkeypatch.setattr(push250, "wait_for_checkpoint_target", checkpoint_wait)
    monkeypatch.setattr(push250, "wait_for_score_watch_attempt",
                        lambda *_args, **_kwargs: pytest.fail("finished iteration was re-evaluated"))
    with pytest.raises(RuntimeError, match="advanced"):
        push250.watch(run, scores, out, first_local_update=500, interval=250,
                      parent_iteration=6000, poll_seconds=0, worktree=tmp_path)
    state = json.loads((out / "watcher_state.json").read_text(encoding="utf-8"))
    assert waits == [500, 750]
    assert state["state"] == "already_completed_skipped"
    assert state["next_local_iteration"] == 750
    assert push250.matching_terminal_result(destination, local_iteration=500,
                                             global_iteration=6500,
                                             checkpoint_sha256="b" * 64)


def test_i13_wrong_result_identity_is_not_silently_skipped(tmp_path):
    result = tmp_path / "6500.json"
    result.write_text(json.dumps({"state": "done", "local_iteration": 500,
                                 "global_iteration": 6500,
                                 "checkpoint_sha256": "c" * 64}), encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        push250.matching_terminal_result(result, local_iteration=500,
                                         global_iteration=6500,
                                         checkpoint_sha256="b" * 64)


def test_i17_pyflakes_guard_rejects_undefined_name_and_accepts_launch_sources(tmp_path):
    bad = tmp_path / "old_launch.py"
    bad.write_text("def launch():\n    return undefined_copy\n", encoding="utf-8")
    with pytest.raises(ValueError, match="undefined name 'undefined_copy'"):
        assert_no_undefined_names([bad])
    assert_no_undefined_names([
        Path("foothold_s2/scripts/train_start.py"),
        Path("foothold_s2/scripts/ex41_startup.py"),
        Path("foothold_s2/scripts/ex41_resume.py"),
        Path("foothold_s2/runners/start_runner.py"),
        Path("foothold_s2/ex40_score_watch.py"),
        Path("foothold_s2/ex41_score_watch.py"),
        Path("foothold_s2/eval/ex41_push250_watch.py"),
    ])


def test_i20_rehearsal_plan_uses_separate_committed_boundary_and_approval_files():
    plan = load_plan(TABLE, arm="B")
    production_boundary = plan.boundary_path.read_bytes()
    production_approvals = plan.approvals_path.read_bytes()
    receipt = configure_stage_rehearsal_plan(plan, (2, 2, 2, 2, 2, 2))
    assert plan.boundary_path.name == "ex41-fixed5000-rehearsal-boundary.yaml"
    assert plan.approvals_path.name == "ex41-fixed5000-rehearsal-approvals.yaml"
    assert plan.boundary_path != TABLE.with_name("ex41-fixed5000-boundary.yaml")
    assert plan.approvals_path != TABLE.with_name("ex41-fixed5000-approvals.yaml")
    assert receipt["boundary_config_path"] == str(plan.boundary_path.resolve())
    assert receipt["approval_config_path"] == str(plan.approvals_path.resolve())
    assert TABLE.with_name("ex41-fixed5000-boundary.yaml").read_bytes() == production_boundary
    assert TABLE.with_name("ex41-fixed5000-approvals.yaml").read_bytes() == production_approvals


def test_i20_explicit_production_boundary_is_rejected_for_rehearsal():
    plan = load_plan(TABLE, arm="B")
    with pytest.raises(ValueError, match="isolated rehearsal boundary"):
        configure_stage_rehearsal_plan(
            plan, (2, 2, 2, 2, 2, 2),
            boundary_path=TABLE.with_name("ex41-fixed5000-boundary.yaml"))
