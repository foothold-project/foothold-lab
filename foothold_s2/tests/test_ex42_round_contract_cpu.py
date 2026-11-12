"""Round contract consumers: the stage table's execution cap is `maximum_updates` (not the first check), and a HOLD
at the cap goes on through the HOLD-only extensions (`extension_updates` x `extension_max_count`) only. Real plan,
real approvals, a boundary save built on the real E0 m250; only the extension flag is stood in for. No training.
"""
from __future__ import annotations

import pytest
import yaml

from foothold_s2 import ex42_stage_handoff as handoff
from foothold_s2.scripts.ex42_training_entry import E_STAGE_SPECS, e_stage_table
from foothold_s2.tests.test_ex42_stage_continue_cpu import APPROVALS, TABLE, _boundary, _e1_row
from foothold_s2.tests.test_ex42_stage_resume_cpu import needs_run


def _stages():
    return yaml.safe_load(TABLE.read_text())["stages"]


def test_the_execution_cap_of_the_table_is_the_plan_maximum_not_the_first_check():
    table = e_stage_table(_stages())
    rows = {r["id"]: r for r in _stages()}
    for stage, spec in table.items():
        assert spec["updates"] == rows[stage]["maximum_updates"]
        assert spec["extension_updates"] == (rows[stage].get("extension_updates") or 0)
        assert spec["extension_max_count"] == (rows[stage].get("extension_max_count") or 0)
    assert E_STAGE_SPECS["E1"]["updates"] == _e1_row()["maximum_updates"]


@pytest.mark.parametrize("iteration,expected", [
    (999, None), (1000, 1500), (1250, 1500), (1500, 2000), (1750, 2000), (2000, None), (2500, None)])
def test_extension_ceiling_steps_by_the_increment_and_stops_after_the_count(iteration, expected):
    assert handoff.extension_ceiling(iteration, 1000, 500, 2) == expected


@pytest.mark.parametrize("step,count", [(0, 2), (500, 0), (None, 2), (500, None), (-500, 2)])
def test_no_extension_without_a_step_and_a_count(step, count):
    assert handoff.extension_ceiling(1000, 1000, step, count) is None


def _with_extension(monkeypatch, plan_row_changes, authorized=True):
    """The shipped plan row plus extension fields, and the extension flag of the approval cell stood in."""
    real = handoff.EX42Plan if hasattr(handoff, "EX42Plan") else None
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    original = EX42Plan.load

    def load(path, *a, **k):
        plan = original(path, *a, **k)
        row = next(r for r in plan.document["stages"] if r["id"] == "E1")
        row.update(plan_row_changes)
        return plan
    monkeypatch.setattr(EX42Plan, "load", staticmethod(load))
    monkeypatch.setattr(handoff, "_extension_authorized", lambda approvals, stage: authorized)
    return real


@needs_run
@pytest.mark.parametrize("judgment,authorized,state", [
    ("HOLD", True, "stage_continues"), ("FAIL", True, "stage_bound_reached_not_ready"),
    (None, True, "stage_bound_reached_not_ready"), ("HOLD", False, "stage_bound_reached_not_ready")])
def test_a_hold_at_the_approved_bound_goes_on_only_when_the_extension_is_open(tmp_path, monkeypatch, judgment, authorized, state):
    _with_extension(monkeypatch, {"extension_updates": 500, "extension_max_count": 2}, authorized)
    path, manifest, out, _ = _boundary(tmp_path, 1750, judgment)
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", 1750, out / "p1_score.json", manifest)
    assert decision["state"] == state
    if state == "stage_continues":
        assert decision["segment_end"] == 2000 and decision["resume_checkpoint"] == str(path)     # one interval into the extension
        assert decision["plan"] == str(TABLE) and decision["approvals"]


@needs_run
def test_when_every_extension_is_used_the_stage_ends_with_a_notice(tmp_path, monkeypatch):
    _with_extension(monkeypatch, {"extension_updates": 500, "extension_max_count": 2})
    path, manifest, out, _ = _boundary(tmp_path, 2750, "HOLD")
    decision = handoff.decide_next_stage(TABLE, APPROVALS, "E1", 2750, out / "p1_score.json", manifest)
    assert decision["action"] == "notify" and decision["state"] == "stage_bound_reached_not_ready"
