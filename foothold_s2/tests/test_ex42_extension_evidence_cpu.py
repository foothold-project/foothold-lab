"""The old HOLD-only extension probe and a pinned, numeric two-boundary counterexample."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from foothold_s2 import ex42_stage_handoff as handoff
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.tests.test_ex42_stage_continue_cpu import APPROVALS, TABLE, _boundary, _e1_maximum, _interval, needs_run


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipts(tmp_path, gaps=(0.3, 0.2, 0.1)):
    plan = EX42Plan.load(TABLE)
    cap, interval = _e1_maximum(), _interval()
    _, manifest, old_out, p1 = _boundary(tmp_path, cap)
    root = tmp_path / "eval" / "scores"
    limit = plan.document["evaluation"]["e1_exit_v2"]["yaw_median_max_rad"]
    for iteration, gap in zip((cap - 2 * interval, cap - interval, cap), gaps):
        folder = root / f"m{iteration}"
        folder.mkdir(parents=True)
        score = {"stage_id": "E1", "checkpoint_sha256": p1["checkpoint_sha256"], "score_config_sha256": "a" * 64,
                 "execution_plan_sha256": plan.sha256, "maintenance_judgement": "PASS",
                 "e1_exit_v2": {"current": {"items": {"yaw/eval_gt/fwd0.5": {
                     "judgement": "FAIL" if gap > 0 else "PASS", "median_abs_rad": limit + gap, "p90_abs_rad": 0,
                     "survival": 64}}}}}
        measured = folder / "ex42_score.json"
        measured.write_text(json.dumps(score))
        receipt = {**p1, "state": "complete", "stage_id": "E1", "checkpoint_iteration": iteration,
                   "plan_sha256": plan.sha256, "evaluation_plan": {"path": str(TABLE), "sha256": _sha(TABLE)},
                   "measurement": str(measured), "measurement_sha256": _sha(measured)}
        (folder / "p1_score.json").write_text(json.dumps(receipt))
    return root / f"m{cap}" / "p1_score.json", manifest


@needs_run
def test_verifier_h1_missing_improvement_is_a_notice(tmp_path):
    _, manifest, out, _ = _boundary(tmp_path, _e1_maximum())
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", _e1_maximum(), out / "p1_score.json", manifest)
    assert decision["action"] == "notify" and decision["state"] == "extension_needs_lead_review"
    assert decision["judgment"] == "HOLD" and "segment_end" not in decision


@needs_run
def test_verified_two_step_improvement_extends_and_carries_numbers(tmp_path):
    gate, manifest = _receipts(tmp_path)
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", _e1_maximum(), gate, manifest)
    assert decision["action"] == "continue" and decision["segment_end"] == _e1_maximum() + _interval()
    proof = decision["extension_evidence"]
    assert proof["state"] == "PASS" and len(proof["boundaries"]) == 3
    row = proof["metrics"][0]
    assert row["older_gap"] > row["previous_gap"] > row["current_gap"] > 0
    assert all(item["gate_sha256"] and item["score_sha256"] for item in proof["boundaries"])


@needs_run
@pytest.mark.parametrize("gaps", [(0.3, 0.3, 0.1), (0.3, 0.2, 0.2), (0.1, 0.2, 0.3)])
def test_no_two_step_improvement_cannot_extend(tmp_path, gaps):
    gate, manifest = _receipts(tmp_path, gaps)
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", _e1_maximum(), gate, manifest)
    assert decision["state"] == "extension_needs_lead_review" and decision["action"] == "notify"


@needs_run
def test_a_deficient_cell_that_reaches_its_threshold_can_still_prove_progress(tmp_path):
    gate, manifest = _receipts(tmp_path, (0.3, 0.2, 0.0))
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", _e1_maximum(), gate, manifest)
    assert decision["action"] == "continue"
    assert decision["extension_evidence"]["metrics"][0]["current_gap"] == 0.0


@needs_run
def test_another_deficient_cell_worsening_blocks_the_extension(tmp_path):
    gate, manifest = _receipts(tmp_path)
    limit = EX42Plan.load(TABLE).document["evaluation"]["e1_exit_v2"]["yaw_median_max_rad"]
    for iteration, gap in zip((_e1_maximum() - 2 * _interval(), _e1_maximum() - _interval(), _e1_maximum()),
                              (0.1, 0.2, 0.3)):
        folder = gate.parent.parent / f"m{iteration}"
        score_path, receipt_path = folder / "ex42_score.json", folder / "p1_score.json"
        score = json.loads(score_path.read_text())
        score["e1_exit_v2"]["current"]["items"]["yaw/eval_pred/fwd0.5"] = {
            "judgement": "FAIL", "median_abs_rad": limit + gap, "p90_abs_rad": 0, "survival": 64}
        score_path.write_text(json.dumps(score))
        receipt = json.loads(receipt_path.read_text()); receipt["measurement_sha256"] = _sha(score_path)
        receipt_path.write_text(json.dumps(receipt))
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", _e1_maximum(), gate, manifest)
    assert decision["action"] == "notify" and "away from" in decision["reason"]


@needs_run
@pytest.mark.parametrize("mutation", ["score", "gate_plan", "missing", "nan", "policy", "v2_missing"])
def test_missing_or_changed_boundary_evidence_cannot_extend(tmp_path, mutation):
    gate, manifest = _receipts(tmp_path)
    prior = gate.parent.parent / f"m{_e1_maximum() - _interval()}"
    if mutation == "score":
        (prior / "ex42_score.json").write_text("{}")
    elif mutation == "gate_plan":
        path = prior / "p1_score.json"
        row = json.loads(path.read_text()); row["plan_sha256"] = "0" * 64; path.write_text(json.dumps(row))
    elif mutation == "missing":
        (prior / "p1_score.json").unlink()
    elif mutation == "nan":
        path = prior / "ex42_score.json"
        row = json.loads(path.read_text()); row["e1_exit_v2"]["current"]["items"]["yaw/eval_gt/fwd0.5"]["median_abs_rad"] = float("nan")
        path.write_text(json.dumps(row))
        receipt = prior / "p1_score.json"; pin = json.loads(receipt.read_text()); pin["measurement_sha256"] = _sha(path); receipt.write_text(json.dumps(pin))
    elif mutation == "v2_missing":
        path = prior / "ex42_score.json"
        row = json.loads(path.read_text()); row.pop("e1_exit_v2")
        path.write_text(json.dumps(row))
        receipt = prior / "p1_score.json"; pin = json.loads(receipt.read_text()); pin["measurement_sha256"] = _sha(path); receipt.write_text(json.dumps(pin))
    else:
        receipt = prior / "p1_score.json"; row = json.loads(receipt.read_text()); row["evaluation_plan"]["sha256"] = "0" * 64; receipt.write_text(json.dumps(row))
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", _e1_maximum(), gate, manifest)
    assert decision["state"] == "extension_needs_lead_review" and decision["action"] == "notify"
