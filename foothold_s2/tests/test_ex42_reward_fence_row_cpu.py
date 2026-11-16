"""E1F / E2 reward fence inside the plan row (lead 2026-11-16 15:20, planner 15:17). CPU only.

The limits file ex42-reward-adjust-limits.yaml keeps its bytes (the source E1 row pins its sha, materialize reads the template's file against it), so
slow_progress [0, 0.6] and slow_track_sigma [0.35, 0.5] are the E1F (and E2) row's own `live_adjustment.extra_reward_limits`. Three readers must
see them: the segment adjustment (`_plan_fenced`), the live adjustment (`limits_from_plan`) and the materialization (`inherited_rewards`, the
E1F row start). The E1 row stays exactly as the file says."""
from __future__ import annotations

import copy
import hashlib
import json
import types
from pathlib import Path

import pytest
import yaml

from foothold_s2.commands import ex42_segment_adjust as adj
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.ex42_live_adjust import limits_from_plan, validate_request
from foothold_s2.tests import test_ex42_materialize_cpu as parent_tests

known = parent_tests.known
run = parent_tests.run

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
LIMITS = ROOT / "foothold_s2" / "curriculum" / "ex42-reward-adjust-limits.yaml"
LIMITS_SHA = "15dfcdcdf464fab34db1829d82ac95048d45b686f16cb54244655458314ee04e"


@pytest.fixture(scope="module")
def plan():
    return EX42Plan.load(PLAN)


def _row(plan, stage_id):
    return next(r for r in plan.document["stages"] if r["id"] == stage_id)


def _full(plan, **change):
    """A complete reward cell set (the E1 row's) with changes."""
    return {**_row(plan, "E1")["rewards"], **change}


def _doc(plan, stage_id, rewards, key="1"):
    return {"schema": adj.SCHEMA, "stage_id": stage_id, "plan_sha256": plan.sha256,
            "segments": {key: {"decided_at": "t", "reason": "r", "evidence": "e", "rewards": rewards}}}


def test_the_limits_file_keeps_its_bytes():
    assert hashlib.sha256(LIMITS.read_bytes()).hexdigest() == LIMITS_SHA
    assert _row(EX42Plan.load(PLAN), "E1")["live_adjustment"]["segment_reward_limits_sha256"] == LIMITS_SHA
    cells = adj.reward_limits()["cells"]
    assert cells["slow_progress"] == (0.0, 0.3) and cells["slow_track_sigma"] == (0.5, 0.5)


@pytest.mark.parametrize("stage_id", ["E1F", "E2"])
def test_the_segment_fence_of_the_row_is_wider_for_exactly_the_two_cells(plan, stage_id):
    fenced = adj._plan_fenced(None, plan, stage_id)["cells"]
    file_cells = adj.reward_limits()["cells"]
    assert fenced["slow_progress"] == (0.0, 0.6) and fenced["slow_track_sigma"] == (0.35, 0.5)
    assert {k: v for k, v in fenced.items() if k not in adj.PLAN_WIDENABLE} == \
        {k: v for k, v in file_cells.items() if k not in adj.PLAN_WIDENABLE}


def test_the_e1_row_keeps_the_file_fence_in_both_readers(plan):
    file_limits = adj.reward_limits()
    assert adj._plan_fenced(file_limits, plan, "E1")["cells"] == file_limits["cells"]
    assert adj._plan_fenced(None, plan, "E1") is None            # a row that widens nothing leaves None as None (the behavior before)
    live = limits_from_plan(_row(plan, "E1")["live_adjustment"])
    assert live["rewards"]["slow_progress"] == (0.0, 0.3) and live["rewards"]["slow_track_sigma"] == (0.5, 0.5)
    assert live["rewards"] == {k: v for k, v in file_limits["cells"].items()}


def test_a_segment_entry_inside_the_row_fence_is_accepted_and_outside_it_refused(plan):
    resolved = adj.resolve(plan, "E1F", _doc(plan, "E1F", _full(plan, slow_progress=0.55, slow_track_sigma=0.4)), 1)
    assert resolved["rewards"]["slow_progress"] == 0.55 and resolved["rewards"]["slow_track_sigma"] == 0.4
    for bad in ({"slow_progress": 0.65}, {"slow_track_sigma": 0.34}, {"slow_track_sigma": 0.51}, {"slow_progress": -0.01}):
        with pytest.raises(ValueError, match="leaves the approved limits"):
            adj.resolve(plan, "E1F", _doc(plan, "E1F", _full(plan, **bad)), 1)


def test_the_back_out_values_are_inside_the_new_fence(plan):
    """Pc off, then slow_progress 0.3 and slow_track_sigma 0.5 by a boundary entry (planner 15:17)."""
    back = adj.resolve(plan, "E1F", _doc(plan, "E1F", _full(plan, slow_progress=0.3, slow_track_sigma=0.5)), 2)
    assert back["rewards"]["slow_progress"] == 0.3 and back["rewards"]["slow_track_sigma"] == 0.5


def test_the_e1_row_still_refuses_what_only_e1f_may_do(plan):
    with pytest.raises(ValueError, match="leaves the approved limits"):
        adj.resolve(plan, "E1", _doc(plan, "E1", _full(plan, slow_progress=0.4)), 1, adj.reward_limits())
    with pytest.raises(ValueError, match="leaves the approved limits"):
        adj.resolve(plan, "E1", _doc(plan, "E1", _full(plan, slow_track_sigma=0.35)), 1, adj.reward_limits())


def _with_extra(plan, stage_id, **cells):
    doc = copy.deepcopy(plan.document)
    row = next(r for r in doc["stages"] if r["id"] == stage_id)
    row["live_adjustment"]["extra_reward_limits"].update(cells)
    return types.SimpleNamespace(document=doc, sha256="x" * 64)


def _live_of(fake, stage_id):
    return next(r for r in fake.document["stages"] if r["id"] == stage_id)["live_adjustment"]


def test_a_row_cannot_narrow_the_file_fence(plan):
    for cells in ({"slow_progress": [0.0, 0.2]}, {"slow_progress": [0.1, 0.6]}, {"slow_track_sigma": [0.45, 0.49]}):
        fake = _with_extra(plan, "E1F", **cells)
        with pytest.raises(ValueError, match="does not contain the limits file"):
            adj._plan_fenced(None, fake, "E1F")
        with pytest.raises(ValueError, match="narrower"):
            limits_from_plan(_live_of(fake, "E1F"))


def test_no_other_cell_may_be_widened_by_a_row(plan):
    for cells in ({"zero_yaw": [-3.0, -0.5]}, {"slow_track": [0.0, 0.5]}):
        with pytest.raises(ValueError, match="differs from segment fence"):
            limits_from_plan(_live_of(_with_extra(plan, "E1F", **cells), "E1F"))
    # and the segment reader never looks at them: _plan_fenced widens only PLAN_WIDENABLE
    fenced = adj._plan_fenced(None, _with_extra(plan, "E1F", zero_yaw=[-3.0, -0.5]), "E1F")
    assert fenced["cells"]["zero_yaw"] == adj.reward_limits()["cells"]["zero_yaw"]


@pytest.mark.parametrize("stage_id", ["E1F", "E2"])
def test_the_live_adjustment_reads_the_same_row_fence(plan, stage_id):
    limits = limits_from_plan(_row(plan, stage_id)["live_adjustment"])
    assert limits["rewards"]["slow_progress"] == (0.0, 0.6) and limits["rewards"]["slow_track_sigma"] == (0.35, 0.5)
    entry = {"decided_by": "lead", "decided_at": "t", "evidence": "e"}
    ok = validate_request({**entry, "rewards": {"slow_progress": 0.55, "slow_track_sigma": 0.36}}, limits)
    assert ok["rewards"] == {"slow_progress": 0.55, "slow_track_sigma": 0.36}
    for bad in ({"slow_progress": 0.61}, {"slow_track_sigma": 0.34}, {"slow_track_sigma": 0.6}):
        with pytest.raises(ValueError, match="outside approved limit"):
            validate_request({**entry, "rewards": bad}, limits)
    e1 = limits_from_plan(_row(plan, "E1")["live_adjustment"])
    with pytest.raises(ValueError, match="outside approved limit"):
        validate_request({**entry, "rewards": {"slow_progress": 0.4}}, e1)


def test_the_real_e1f_materialization_starts_the_two_cells_where_the_row_says(known):
    """Real chain: E1's last readback, then E1F's reward_start overlay; the first segment's record and the stage start both print 0.4 / 0.35."""
    result = run(known)
    plan = EX42Plan.load(result["plan"])
    row = _row(plan, "E1F")
    assert row["rewards"]["slow_progress"] == 0.4 and row["rewards"]["slow_track_sigma"] == 0.35
    assert adj.stage_rewards(plan, "E1F") == row["rewards"]
    first = adj.read(None, plan, "E1F", 0, adj.reward_limits())                           # the record every segment start writes; segment 0 has no file
    assert first["rewards"]["values"]["slow_progress"] == 0.4 and first["rewards"]["values"]["slow_track_sigma"] == 0.35
    assert first["rewards"]["limits_sha256"] == LIMITS_SHA
    # the back-out entry is accepted on the materialized plan, and so is the original E1 value (0.3 / 0.5)
    back = adj.resolve(plan, "E1F", _doc(plan, "E1F", {**row["rewards"], "slow_progress": 0.3, "slow_track_sigma": 0.5}), 1)
    assert back["rewards"]["slow_progress"] == 0.3 and back["rewards"]["slow_track_sigma"] == 0.5
    transition = json.loads(Path(result["transition"]).read_text())
    assert transition["inherited_rewards"]["start_override"] == {"slow_progress": 0.4, "slow_track_sigma": 0.35}
    from foothold_s2.ex42_stage_materialize import validate_materialized_transition
    validate_materialized_transition(plan, target_stage="E1F", gate_receipt_path=known["gate_receipt"],
                                     expected_gate_sha256=parent_tests.sha(known["gate_receipt"]))


def _template_with(known, mutate):
    document = yaml.safe_load(Path(known["plan"]).read_text())
    mutate(next(r for r in document["stages"] if r["id"] == "E1F"))
    out = Path(known["plan"]).parent / "mutated-template.yaml"        # beside the plan: the loader reads its sibling files
    out.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True))
    return out


@pytest.mark.parametrize("start, why", [({"slow_progress": 0.7}, "leaves the approved limits"),
                                        ({"slow_track_sigma": 0.3}, "leaves the approved limits"),
                                        ({"slow_track": 0.2}, "may name only"),
                                        ({"zero_yaw": -1.5}, "may name only"),
                                        ({}, "may name only")])
def test_a_reward_start_outside_the_fence_or_off_the_two_cells_is_refused(known, start, why):
    known["plan"] = _template_with(known, lambda row: row.update(reward_start=start))
    with pytest.raises(ValueError, match=why):
        run(known)
    assert not Path(known["out"]).exists()


def test_a_reward_start_needs_the_inherited_cells(known):
    def own(row):
        row["rewards"] = dict(_row(EX42Plan.load(PLAN), "E1")["rewards"])
    known["plan"] = _template_with(known, own)
    with pytest.raises(ValueError, match="needs the reward cells inherited"):
        run(known)


def test_e2_inherits_the_started_values_inside_its_own_fence(known):
    """E2's materialization reads E1F's last values (0.4 / 0.35 when nothing moved them) against E2's row fence, not the file's."""
    from foothold_s2.ex42_stage_materialize import inherited_rewards
    result = run(known)
    e1f_plan = EX42Plan.load(result["plan"])
    template = EX42Plan.load(PLAN)
    got, _ = inherited_rewards(e1f_plan, "E1F", known["parent_manifest"], 100, LIMITS, target_plan=template, target_stage="E2")
    assert got["values"]["slow_progress"] == 0.4 and got["values"]["slow_track_sigma"] == 0.35
    with pytest.raises(ValueError, match="leaves the approved limits"):          # without the row fence the file refuses the same values
        inherited_rewards(e1f_plan, "E1F", known["parent_manifest"], 100, LIMITS)
