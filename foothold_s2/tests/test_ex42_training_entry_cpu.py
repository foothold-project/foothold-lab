from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from foothold_s2.scripts import ex42_training_entry as entry
from foothold_s2.tests.test_ex42_chain_cpu import APPROVALS, ROOT, make_chain
from foothold_s2.runners.start_runner import StartRunner


def test_train_start_caller_builds_parent_verified_chain_and_attaches(tmp_path, monkeypatch):
    fixture_chain, run = make_chain(tmp_path)
    parent_manifest = Path(fixture_chain.parent["manifest_path"])
    monkeypatch.setattr(entry.EX42Plan, "load", lambda _path: fixture_chain.plan)
    runner = StartRunner.__new__(StartRunner)
    runner.log_dir = str(run)

    chain = entry.build_and_attach_ex42_training_chain(
        runner,
        plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
        approvals_path=APPROVALS,
        parent_manifest_path=parent_manifest,
        run_dir=run,
        repo_root=ROOT,
        queue_path=tmp_path / "queue.json",
        score_argv_json='["python", "-m", "known.p1", "--iteration", "{iteration}"]',
        p1_interval=250,
    )

    assert runner.ex42_training_chain is chain
    assert chain.plan.document["status"] == "preparation_only"
    assert chain.parent["checkpoint_sha256"] == fixture_chain.parent["checkpoint_sha256"]
    assert chain.score_argv_factory(250) == [
        "python", "-m", "known.p1", "--iteration", "250"]
    receipt = json.loads((run / "startup_receipt.json").read_text(encoding="utf-8"))
    assert receipt["state"] == "chain_ready_not_launch_authorized"
    assert receipt["production_launch_allowed"] is False


def test_p1_argv_requires_exactly_one_iteration_placeholder():
    with pytest.raises(ValueError, match="exactly once"):
        entry.make_score_argv_factory('["python", "-m", "known.p1"]')
    with pytest.raises(ValueError, match="exactly once"):
        entry.make_score_argv_factory(
            '["{iteration}", "{iteration}"]')


def test_train_start_preparation_gate_precedes_kit_and_keeps_attachment_call():
    source = ROOT / "foothold_s2/scripts/train_start.py"
    text = source.read_text(encoding="utf-8")
    assert text.index("EX-42 preparation_only:") < text.index("from isaaclab.app import AppLauncher")
    assert text.index("EX42_SOURCE_LOCK_RECEIPT = audit_ex42_launch_source") < text.index(
        "from isaaclab.app import AppLauncher")
    assert "attach_ex42_training_chain(runner, EX42_TRAINING_CHAIN)" in text
    ast.parse(text)
