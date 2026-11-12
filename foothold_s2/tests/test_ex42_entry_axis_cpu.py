"""Stage entry axis comes from the plan's registered order, not from evidence (CPU, real plan rows)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from foothold_s2.ex42_stage_materialize import registered_entry_axis

PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


def _row(stage):
    return next(r for r in yaml.safe_load(PLAN.read_text())["stages"] if r["id"] == stage)


def test_multi_axis_stage_takes_the_registered_entry_axis():
    row = _row("E3")
    assert registered_entry_axis(row, {}) == row["boundary"]["axis_order"][0] == "terrain_kind_level_cap"


def test_an_unmet_axis_is_skipped_in_registered_order():
    row = _row("E3")
    order = row["boundary"]["axis_order"]
    assert registered_entry_axis(row, {"axis_eligible": {order[0]: False}}) == order[1]
    assert registered_entry_axis(row, {"axis_eligible": {order[0]: False, order[1]: False}}) == order[2]


def test_with_no_axis_met_there_is_nothing_to_materialize():
    row = _row("E3")
    with pytest.raises(ValueError, match="changes no axis"):
        registered_entry_axis(row, {"axis_eligible": {a: False for a in row["boundary_axes"]}})


def test_evidence_cannot_pick_another_axis_but_may_repeat_the_registered_one():
    row = _row("E3")
    assert registered_entry_axis(row, {"boundary_axis": "terrain_kind_level_cap"}) == "terrain_kind_level_cap"
    with pytest.raises(ValueError, match="other than the registered"):
        registered_entry_axis(row, {"boundary_axis": "command_allocation"})


def test_missing_or_inconsistent_order_is_refused():
    row = _row("E3")
    for change in (lambda r: r.pop("boundary"), lambda r: r["boundary"].update(entry_axis="command_allocation"),
                   lambda r: r["boundary"].update(axis_order=r["boundary"]["axis_order"][:2])):
        broken = yaml.safe_load(yaml.safe_dump(row))
        change(broken)
        with pytest.raises(ValueError, match="registered axis order"):
            registered_entry_axis(broken, {})


def test_bad_eligibility_is_refused():
    row = _row("E3")
    for bad in ({"nope": True}, {"terrain_exposure": "yes"}, ["x"]):
        with pytest.raises(ValueError, match="axis_eligible"):
            registered_entry_axis(row, {"axis_eligible": bad})


def test_single_axis_stage_is_its_one_axis():
    row = next(r for r in yaml.safe_load(PLAN.read_text())["stages"] if len(r.get("boundary_axes") or []) == 1)
    assert registered_entry_axis(row, {}) == row["boundary_axes"][0]


def test_prepare_takes_the_axis_from_the_registered_order_only():
    """Wiring guard (source level: the full materialize fixture has no multi-axis target)."""
    import inspect
    from foothold_s2 import ex42_stage_materialize as m
    src = inspect.getsource(m._prepare)
    assert "registered_entry_axis(row,ev)" in src and "ev.get('boundary_axis')" not in src
