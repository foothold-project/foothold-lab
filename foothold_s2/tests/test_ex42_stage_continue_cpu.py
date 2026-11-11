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


def _boundary(tmp_path, iteration, judgment="HOLD"):
    path, manifest, *_ = _boundary_checkpoint(tmp_path, iteration)
    p1 = {"state": "complete", "judgment": judgment, "stage_id": "E1", "checkpoint_iteration": iteration,
          "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    out = tmp_path / "eval"
    out.mkdir()
    (out / "p1_score.json").write_text(json.dumps(p1))
    return path, manifest, out, p1


def _decide(tmp_path, iteration, judgment="HOLD", approvals=APPROVALS):
    path, manifest, out, _ = _boundary(tmp_path, iteration, judgment)
    return handoff.decide_next_stage(TABLE, approvals, "E1", iteration, out / "p1_score.json", manifest), path


def _interval():
    return yaml.safe_load(TABLE.read_text())["evaluation"]["interval_updates"]


def _inside_boundaries():
    """The E1 boundaries after the first check and before the base cap, read from the plan (nothing typed)."""
    row, step = _e1_row(), _interval()
    return [(i, min(i + step, row["maximum_updates"])) for i in range(row["minimum_updates"], row["maximum_updates"], step)]


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
def test_a_pass_at_any_boundary_from_the_first_check_goes_to_the_next_stage_not_on(tmp_path):
    following = "E1F"
    for number, (iteration, _) in enumerate(_inside_boundaries()):
        sub = tmp_path / f"p{number}"
        sub.mkdir()
        decision, _ = _decide(sub, iteration, "PASS")
        assert decision["state"] != "stage_continues" and decision["next_stage_id"] == following
        assert decision["action"] in ("launch", "notify")           # no E1F approval cell yet: a notice, never "continue"


@needs_run
@pytest.mark.parametrize("judgment", ["HOLD", "FAIL", None])
def test_the_stage_bound_without_a_pass_ends_the_stage_with_a_notice(tmp_path, judgment):
    decision, _ = _decide(tmp_path, _e1_maximum(), judgment)
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
    ("extension opened", lambda a: a["stage_e1_authorization"].__setitem__("extension_authorized", True)),
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
    path, manifest, out, p1 = _boundary(sub, _e1_maximum())
    notice = once._hand_off(TABLE, APPROVALS, "E1", _e1_maximum(), p1, path, out, _launcher(sub))
    assert notice["state"] == "stage_bound_reached_not_ready" and notice["automatic_launch_started"] is False
    assert not (sub / "ran.txt").exists()


def test_the_shipped_plan_and_cell_have_the_shape_the_decision_reads():
    plan = EX42Plan.load(TABLE)
    e1 = next(r for r in plan.document["stages"] if r["id"] == "E1")
    cell = yaml.safe_load(APPROVALS.read_text())["stage_e1_authorization"]
    assert e1["minimum_updates"] == _interval()                       # the first check is the first boundary
    assert e1["maximum_updates"] == cell["scope"]["maximum_updates"]  # the cell approves the base cap
    assert cell["boundary_evaluation_interval_updates"] == 250 and cell["extension_authorized"] is False
    assert os.path.isfile(TABLE)
