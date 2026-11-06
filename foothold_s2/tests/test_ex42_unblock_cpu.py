from __future__ import annotations

import hashlib
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import EX42Runtime
from foothold_s2.eval.ex41_push250_watch import score_watch_attempt_finished
from foothold_s2.ex40_score_watch import _manifest_digest
from foothold_s2.ex41_score_watch import (
    phase_output_from_receipt,
    phase_receipt_path,
)


ROOT = Path(__file__).resolve().parents[2]


def _load_dispatch():
    path = ROOT / "_out/tools/gpu_jobs/dispatch.py"
    spec = importlib.util.spec_from_file_location("ex42_unblock_dispatch", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_stage_transition_consumes_only_complete_approved_dr_schedule(tmp_path):
    plan = EX42Plan.load(ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    approvals = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-approvals.yaml")
                               .read_text(encoding="utf-8"))
    path = tmp_path / "approvals.yaml"
    path.write_text(yaml.safe_dump(approvals), encoding="utf-8")
    with pytest.raises(ValueError, match="approved DR schedule missing"):
        EX42Runtime.transition_consumer(plan, path)

    # Explicit fixture values exercise consumption only; they are not committed
    # as an EX-42 schedule or offered as defaults.
    approvals["domain_randomization"] = {
        "approved": True,
        "decision_id": "fixture-decision",
        "stage_scales": {stage["id"]: 0.37 for stage in plan.document["stages"]},
    }
    path.write_text(yaml.safe_dump(approvals), encoding="utf-8")
    consumer = EX42Runtime.transition_consumer(plan, path, current_stage_id="E0")
    env = SimpleNamespace(_ex42_stage_id="E0", _ex40_dr_scale=0.1)
    row = consumer.transition(env, "E1", boundary_iteration=251,
                              expected_score_iteration=250,
                              observed_score_iteration=None)
    assert row["stage_before"] == "E0" and row["stage_after"] == "E1"
    assert row["decision_id"] == "fixture-decision"
    assert row["status"] == "measurement_gap"
    assert row["applied_scale"] == row["planned_scale"] == 0.37
    assert row["learning_continues"] is True
    assert row["maintenance_action"] == "not_decided_here"
    assert env._ex42_stage_id == "E1" and env._ex40_dr_scale == 0.37
    with pytest.raises(ValueError, match="exactly one planned stage"):
        consumer.transition(env, "E3", boundary_iteration=501,
                            expected_score_iteration=500,
                            observed_score_iteration=500)


def test_dispatch_queue_updates_serialize_and_temp_names_are_private(tmp_path, monkeypatch):
    dispatch = _load_dispatch()
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"format": dispatch.QUEUE_FORMAT, "items": []}),
                     encoding="utf-8")
    cfg = {**dispatch.LIVE, "queue": str(queue)}

    class Args:
        qaction = "add"
        priority = 4
        gpu = 1
        owner = "cpu-test"
        cond = ""
        start = end = None
        needs_approval = False
        kind = cwd = argv_json = None
        wait_absent = wait_pid = done_file = []

        def __init__(self, title):
            self.title = title

    # A concurrent command blocks behind a lock held by another queue writer.
    entered = threading.Event()

    def add_one():
        entered.set()
        return dispatch.queue_cmd(Args("locked"), cfg)

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        with dispatch.queue_lock(str(queue)):
            future = pool.submit(add_one)
            assert entered.wait(1)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.05)
        assert future.result(timeout=2) == "added 1"
    finally:
        pool.shutdown(wait=True)

    # Intercept replacements to prove each write uses its own temp path.
    names = []
    original_replace = Path.replace

    def recording_replace(source, target):
        names.append(source.name)
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", recording_replace)
    base = {"format": dispatch.QUEUE_FORMAT, "items": []}
    dispatch.write_queue(str(queue), base)
    dispatch.write_queue(str(queue), base)
    assert len(names) == 2 and names[0] != names[1]
    assert not list(tmp_path.glob("*.tmp"))

    # Parallel add operations retain every item, exercising the shared RMW lock.
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: dispatch.queue_cmd(Args(f"parallel-{i}"), cfg), range(32)))
    items = json.loads(queue.read_text(encoding="utf-8"))["items"]
    assert len(items) == 32
    assert len({row["id"] for row in items}) == 32
    assert not (tmp_path / "queue.json.lock").exists()


def test_push250_matches_attempt_identity_not_incidental_done_fields(tmp_path):
    root = tmp_path / "score-watch"
    attempt_dir = root / "model_1000_aaaaaaaaaaaa"
    attempt_dir.mkdir(parents=True)
    score = tmp_path / "score.json"
    score.write_text('{"state":"complete"}', encoding="utf-8")
    score_sha = hashlib.sha256(score.read_bytes()).hexdigest()
    attempt = {"iteration": 1000, "checkpoint_sha256": "a" * 64,
               "state": "complete", "score_path": str(score), "score_sha256": score_sha}
    done = {**attempt, "mode": "recovered", "reason": "watcher restarted"}
    (attempt_dir / "attempt.json").write_text(json.dumps(attempt), encoding="utf-8")
    (root / "watch_state.json").write_text(
        json.dumps({"done": {f"1000_{'a' * 64}": done}}), encoding="utf-8")
    assert score_watch_attempt_finished(root, 1000, "a" * 64) == (
        True, "score_watch_attempt_closed")


def test_score_watch_accepts_pinned_model_n_before_lagging_progress_n_plus_one(tmp_path):
    digest = "c" * 64
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema": "foothold-manifest/1",
        "progress": {"completed_updates": 500},
        "checkpoints": {"model_500.pt": digest},
    }), encoding="utf-8")
    assert _manifest_digest(tmp_path, 500) == digest


def test_stage_end_video_phase_filename_and_child_output_are_fenced(tmp_path):
    phase = "W57:fwd0.5:eval_gt"
    assert phase_receipt_path(tmp_path, phase).name == "W57__fwd0.5__eval_gt.json"
    phase_root = tmp_path / "axis_v2"
    phase_root.mkdir()
    child_out = phase_root / "axis_v2"
    receipt = {"steps": {"axis_v2": {"argv": ["eval", "--out", str(child_out)]}}}
    (phase_root / "eval_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    assert phase_output_from_receipt(phase_root, "axis_v2") == child_out.resolve()
    receipt["steps"]["axis_v2"]["argv"] = ["eval", "--out", str(tmp_path / "stale")]
    (phase_root / "eval_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from its phase root"):
        phase_output_from_receipt(phase_root, "axis_v2")
