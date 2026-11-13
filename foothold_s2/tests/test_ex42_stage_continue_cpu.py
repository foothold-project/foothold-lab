"""E1 boundary decisions: not PASS (or PASS before the minimum) continues the same stage from the saved boundary
checkpoint; the bound ends it. Real plan, real approvals, a boundary save built on the real E0 m250. No training.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import time

import pytest
import yaml

from foothold_s2 import ex42_eval_once as once
from foothold_s2 import ex42_stage_handoff as handoff
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.tests.test_ex42_stage_resume_cpu import _boundary_checkpoint, needs_run

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"


def _e1_row():
    return next(r for r in yaml.safe_load(TABLE.read_text())["stages"] if r["id"] == "E1")


def _e1_maximum():
    return _e1_row()["maximum_updates"]


def _past_the_extensions():
    row = _e1_row()
    return row["maximum_updates"] + row["extension_updates"] * row["extension_max_count"] + _interval()


def _boundary(tmp_path, iteration, judgment="HOLD", maintenance="PASS"):
    path, manifest, *_ = _boundary_checkpoint(tmp_path, iteration)
    out = tmp_path / "eval"
    out.mkdir()
    measured = out / "ex42_score.json"          # the measured score the gate receipt pins; carries the maintenance table verdict
    measured.write_text(json.dumps({"maintenance_judgement": maintenance}))
    p1 = {"state": "complete", "judgment": judgment, "stage_id": "E1", "checkpoint_iteration": iteration,
          "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
          "measurement": str(measured), "measurement_sha256": hashlib.sha256(measured.read_bytes()).hexdigest()}
    (out / "p1_score.json").write_text(json.dumps(p1))
    return path, manifest, out, p1


def _decide(tmp_path, iteration, judgment="HOLD", approvals=APPROVALS, maintenance="PASS"):
    path, manifest, out, _ = _boundary(tmp_path, iteration, judgment, maintenance)
    return handoff.decide_next_stage(TABLE, approvals, "E1", iteration, out / "p1_score.json", manifest), path


def _interval():
    return yaml.safe_load(TABLE.read_text())["evaluation"]["interval_updates"]


def _inside_boundaries():
    """Every E1 boundary before the base cap, read from the plan (nothing typed): six for the seven-segment E1."""
    row, step = _e1_row(), _interval()
    inside = [(i, min(i + step, row["maximum_updates"])) for i in range(step, row["maximum_updates"], step)]
    assert len(inside) == row["maximum_updates"] // step - 1 and inside        # never an empty loop below
    return inside


@needs_run
@pytest.mark.parametrize("judgment", ["HOLD", "FAIL", None])
def test_a_boundary_inside_the_stage_continues_from_its_own_save(tmp_path, judgment):
    for number, (iteration, end) in enumerate(_inside_boundaries()):
        sub = tmp_path / f"b{number}"
        sub.mkdir()
        decision, path = _decide(sub, iteration, judgment)
        assert decision["action"] == "continue" and decision["state"] == "stage_continues"
        assert decision["target_stage"] == "E1" and decision["segment_end"] == end
        assert decision["resume_checkpoint"] == str(path)
        assert decision["authorization"]["scope"]["maximum_updates"] == _e1_maximum()


@needs_run
def test_a_pass_before_the_last_planned_segment_continues_the_stage_and_never_starts_e1f(tmp_path):
    # CG v0.17j: E1 is seven planned segments (minimum = maximum = 1750); a gate that passes earlier does not end it
    for number, (iteration, end) in enumerate(_inside_boundaries()):
        sub = tmp_path / f"p{number}"
        sub.mkdir()
        decision, path = _decide(sub, iteration, "PASS")
        assert decision["action"] == "continue" and decision["state"] == "stage_continues"
        assert decision["target_stage"] == "E1" and decision["segment_end"] == end


@needs_run
@pytest.mark.parametrize("judgment", ["HOLD", "FAIL", None])
def test_the_stage_bound_extends_only_for_the_newly_authorized_hold(tmp_path, judgment):
    decision, _ = _decide(tmp_path, _e1_maximum(), judgment)
    if judgment == "HOLD":
        assert decision["action"] == "notify" and decision["state"] == "extension_needs_lead_review"
        assert "segment_end" not in decision
    else:
        assert decision["action"] == "notify" and decision["state"] == "stage_bound_reached_not_ready"


@needs_run
def test_a_pass_at_the_bound_wants_the_next_stage_which_has_no_approval_cell(tmp_path):
    decision, _ = _decide(tmp_path, _e1_maximum(), "PASS")
    assert decision["action"] == "notify" and decision["state"] == "next_stage_ready_for_approval"


@needs_run
@pytest.mark.parametrize("iteration", [0, 100, 300, 999, "past_maximum"])
def test_updates_that_are_not_boundaries_decide_nothing(tmp_path, iteration):
    iteration = _past_the_extensions() if iteration == "past_maximum" else iteration     # read from the plan, not typed
    path, manifest, out, _ = _boundary(tmp_path, 250)
    assert handoff.decide_next_stage(TABLE, APPROVALS, "E1", iteration, out / "p1_score.json", manifest) is None


@needs_run
def test_a_save_that_is_not_the_scored_latest_one_does_not_continue(tmp_path):
    path, manifest, out, p1 = _boundary(tmp_path, 250)
    doc = json.loads(manifest.read_text())
    doc["progress"]["completed_updates"] = 300                       # training went on past the scored save
    manifest.write_text(json.dumps(doc))
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", 250, out / "p1_score.json", manifest)
    assert decision["action"] == "notify" and decision["state"] == "continue_not_authorized"
    doc["progress"]["completed_updates"] = 250
    manifest.write_text(json.dumps(doc))
    (out / "p1_score.json").write_text(json.dumps({**p1, "checkpoint_sha256": "0" * 64}))   # a different save was scored
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", 250, out / "p1_score.json", manifest)
    assert decision["state"] == "continue_not_authorized"


@needs_run
@pytest.mark.parametrize("name,edit", [
    ("policy off", lambda a: a.__setitem__("automatic_launch_allowed", False)),
    ("cell removed", lambda a: a.pop("stage_e1_authorization")),
    ("extension proof removed", lambda a: a["stage_e1_authorization"].pop("extension_contract")),
    ("scope widened", lambda a: a["stage_e1_authorization"]["scope"].__setitem__("maximum_updates", 2000)),
])
def test_an_approval_that_is_off_or_widened_does_not_continue(tmp_path, name, edit):
    approval = yaml.safe_load(APPROVALS.read_text())
    edit(approval)
    edited = tmp_path / "approvals_edited.yaml"
    edited.write_text(yaml.safe_dump(approval))
    sub = tmp_path / "run"
    sub.mkdir()
    decision, _ = _decide(sub, 250, approvals=edited)
    assert decision["action"] == "notify", name


def _launcher(tmp_path):
    path = tmp_path / "launch.sh"
    path.write_text('#!/usr/bin/env bash\nprintf "%s %s %s %s\\n" "$EX42_AUTO_ACTION" "$EX42_AUTO_TARGET_STAGE" '
                    '"$EX42_AUTO_RESUME_CHECKPOINT" "$EX42_AUTO_SEGMENT_END" > "$(dirname "$0")/ran.txt"\n')
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@needs_run
def test_the_tail_starts_the_launcher_for_the_next_segment_once(tmp_path):
    path, manifest, out, p1 = _boundary(tmp_path, 500)
    # 500 needs a checkpoint that is the manifest latest: rebuild the manifest for it
    notice = once._hand_off(TABLE, APPROVALS, "E1", 500, p1, path, out, _launcher(tmp_path))
    assert notice["state"] == "stage_continued" and notice["automatic_launch_started"] is True
    assert notice["segment_end"] == 750 and notice["notification_required"] is True
    for _ in range(100):
        if (tmp_path / "ran.txt").is_file() and (tmp_path / "ran.txt").read_text().strip().count(" ") == 3:
            break
        time.sleep(0.05)
    action, stage, checkpoint, end = (tmp_path / "ran.txt").read_text().split()
    assert (action, stage, end) == ("continue", "E1", "750") and checkpoint == str(path)
    record = json.loads((out / handoff.LAUNCH_RECORD).read_text())
    assert record["action"] == "continue" and record["segment_end"] == 750
    with pytest.raises(FileExistsError):
        handoff.start_launcher(handoff.decide_next_stage(TABLE, APPROVALS, "E1", 500, out / "p1_score.json", manifest),
                               _launcher(tmp_path), out, parent_manifest=manifest, parent_checkpoint=path,
                               gate_receipt=out / "p1_score.json")


@needs_run
def test_the_tail_without_a_launcher_or_at_the_bound_only_notifies(tmp_path):
    path, manifest, out, p1 = _boundary(tmp_path, 250)
    notice = once._hand_off(TABLE, APPROVALS, "E1", 250, p1, path, out, None)
    assert notice["state"] == "stage_continues_no_launcher" and notice["automatic_launch_started"] is False
    assert not (out / handoff.LAUNCH_RECORD).exists()
    sub = tmp_path / "bound"
    sub.mkdir()
    row = _e1_row()
    exhausted = row["maximum_updates"] + row["extension_updates"] * row["extension_max_count"]
    path, manifest, out, p1 = _boundary(sub, exhausted)
    notice = once._hand_off(TABLE, APPROVALS, "E1", exhausted, p1, path, out, _launcher(sub))
    assert notice["state"] == "stage_bound_reached_not_ready" and notice["automatic_launch_started"] is False
    assert not (sub / "ran.txt").exists()


def test_the_shipped_plan_and_cell_have_the_shape_the_decision_reads():
    plan = EX42Plan.load(TABLE)
    e1 = next(r for r in plan.document["stages"] if r["id"] == "E1")
    cell = yaml.safe_load(APPROVALS.read_text())["stage_e1_authorization"]
    assert e1["minimum_updates"] == e1["maximum_updates"] == 7 * _interval()   # seven segments, no exit before the last
    assert e1["maximum_updates"] == cell["scope"]["maximum_updates"]  # the cell approves the base cap
    assert cell["boundary_evaluation_interval_updates"] == 250 and cell["extension_authorized"] is True
    assert os.path.isfile(TABLE)


@needs_run
@pytest.mark.parametrize("maintenance", ["HOLD", "FAIL"])
@pytest.mark.parametrize("judgment", ["HOLD", "FAIL", "PASS"])
def test_a_maintenance_table_that_is_not_pass_never_starts_the_next_segment_and_says_so(tmp_path, judgment, maintenance):
    iteration, end = _inside_boundaries()[0]
    decision, _ = _decide(tmp_path, iteration, judgment, maintenance=maintenance)
    assert decision["action"] == "notify" and decision["state"] == "continue_held_by_maintenance"
    assert f"maintenance table is {maintenance}" in decision["reason"] and str(end) in decision["reason"]
    assert "resume_checkpoint" not in decision and "segment_end" not in decision


@needs_run
def test_a_hold_at_the_approved_bound_does_not_extend_while_the_maintenance_table_holds(tmp_path):
    decision, _ = _decide(tmp_path, _e1_maximum(), "HOLD", maintenance="HOLD")
    assert decision["action"] == "notify" and decision["state"] == "continue_held_by_maintenance"


@needs_run
def test_an_unpinned_or_altered_measurement_is_not_read_as_a_maintenance_pass(tmp_path):
    iteration, _ = _inside_boundaries()[0]
    path, manifest, out, p1 = _boundary(tmp_path, iteration, "HOLD", "PASS")
    (out / "ex42_score.json").write_text(json.dumps({"maintenance_judgement": "PASS", "edited": True}))   # differs from the pin
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", iteration, out / "p1_score.json", manifest)
    assert decision["state"] == "continue_held_by_maintenance" and "not readable" in decision["reason"]
    unpinned = {k: v for k, v in p1.items() if k not in ("measurement", "measurement_sha256")}
    (out / "p1_score.json").write_text(json.dumps(unpinned))
    assert handoff.decide_next_stage(TABLE, APPROVALS, "E1", iteration, out / "p1_score.json", manifest)["state"] == "continue_held_by_maintenance"


def test_later_stages_record_the_table_under_stage_exit_items(tmp_path):
    measured = tmp_path / "s.json"
    measured.write_text(json.dumps({"stage_exit": {"items": {"maintenance_current": {"judgement": "HOLD"}}}}))
    p1 = {"measurement": str(measured), "measurement_sha256": hashlib.sha256(measured.read_bytes()).hexdigest()}
    assert handoff._maintenance_verdict(p1) == "HOLD"
