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


def test_an_unmet_entry_axis_holds_and_never_moves_to_the_next_axis():
    row = _row("E3")
    order = row["boundary"]["axis_order"]
    with pytest.raises(ValueError, match="HOLD"):
        registered_entry_axis(row, {"axis_eligible": {order[0]: False}})
    assert registered_entry_axis(row, {"axis_eligible": {order[0]: True, order[1]: False}}) == order[0]


def test_a_repeated_axis_in_the_order_is_legal_and_the_entry_axis_is_order_zero():
    row = _row("E6a")
    assert row["boundary"]["axis_order"] == ["posture_height", "posture_height", "posture_roll"]
    assert registered_entry_axis(row, {}) == "posture_height"


def test_every_registered_stage_row_gives_its_order_zero():
    """Real plan: every non-jump stage (E0..E6b, M). J2 to J4 have no registered order and are not read here."""
    rows = [r for r in yaml.safe_load(PLAN.read_text())["stages"] if not r["id"].startswith("J")]
    assert {r["id"] for r in rows} >= {"E1F", "E2", "E3", "E4", "E5", "E6a", "E6b", "M"}
    for r in rows:
        axes = r["boundary_axes"]
        expected = axes[0] if len(axes) == 1 else r["boundary"]["axis_order"][0]
        assert registered_entry_axis(r, {}) == expected, r["id"]


def test_evidence_cannot_pick_another_axis_but_may_repeat_the_registered_one():
    row = _row("E3")
    assert registered_entry_axis(row, {"boundary_axis": "terrain_kind_level_cap"}) == "terrain_kind_level_cap"
    with pytest.raises(ValueError, match="other than the registered"):
        registered_entry_axis(row, {"boundary_axis": "command_allocation"})


def test_missing_or_inconsistent_order_is_refused():
    row = _row("E3")
    for change in (lambda r: r.pop("boundary"), lambda r: r["boundary"].update(entry_axis="command_allocation"),
                   lambda r: r["boundary"].update(axis_order=r["boundary"]["axis_order"][:2]),
                   lambda r: r["boundary"].update(axis_order=["x"] + r["boundary"]["axis_order"][1:])):
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
