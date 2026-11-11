"""EX-42 multi-axis stages register their entry axis and the order of the next axis before any result (CG v0.17c)."""
from pathlib import Path

import pytest
import yaml

PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
EXPECTED = {
    "E3": ("terrain_kind_level_cap", ["terrain_kind_level_cap", "terrain_exposure", "terrain_level_cap", "command_allocation"],
           "rotate_in_order_one_axis_per_boundary"),
    "E4": ("terrain_exposure", ["terrain_exposure", "terrain_kind_level_cap", "command_allocation"],
           "rotate_in_order_one_axis_per_boundary"),
    "E5": ("terrain_exposure", ["terrain_exposure", "command_allocation"], "rotate_in_order_one_axis_per_boundary"),
    "E6a": ("posture_height", ["posture_height", "posture_height", "posture_roll"], "fixed_sequence"),
    "E6b": ("terrain_exposure", ["terrain_exposure", "terrain_kind_level_cap"], "rotate_in_order_one_axis_per_boundary"),
}


def _rows():
    return {row["id"]: row for row in yaml.safe_load(PLAN.read_text(encoding="utf-8"))["stages"]}


def check_boundary(row):
    """The rule the table has to keep: one registered entry axis, an order made only of the allowed axes."""
    axes, block = row["boundary_axes"], row.get("boundary")
    if not isinstance(block, dict):
        raise ValueError(f"EX-42 {row['id']} has several boundary axes and no fixed order")
    order = block.get("axis_order")
    if not isinstance(order, list) or not order or set(order) != set(axes):
        raise ValueError(f"EX-42 {row['id']} axis order must use exactly the allowed axes")
    if block.get("entry_axis") != order[0]:
        raise ValueError(f"EX-42 {row['id']} entry axis must be the first axis of the order")
    if block.get("rule") == "rotate_in_order_one_axis_per_boundary":
        if order != axes or block.get("not_eligible") != "skip" or block.get("none_eligible") != "no_axis_change":
            raise ValueError(f"EX-42 {row['id']} rotation must follow the table order and skip unmet axes")
    elif block.get("rule") != "fixed_sequence":
        raise ValueError(f"EX-42 {row['id']} boundary rule is not registered")


def test_registered_orders_match_the_canon_rows():
    rows = _rows()
    for stage, (entry, order, rule) in EXPECTED.items():
        block = rows[stage]["boundary"]
        assert (block["entry_axis"], block["axis_order"], block["rule"]) == (entry, order, rule)
        check_boundary(rows[stage])


def test_every_enabled_multi_axis_stage_has_a_fixed_order():
    for stage, row in _rows().items():
        if stage.startswith("J") or len(row["boundary_axes"]) < 2:
            continue
        check_boundary(row)


@pytest.mark.parametrize("mutate", [
    lambda block: block.update(entry_axis="command_allocation"),
    lambda block: block.update(axis_order=["terrain_kind_level_cap", "terrain_exposure"]),
    lambda block: block.update(axis_order=block["axis_order"][::-1], entry_axis=block["axis_order"][-1]),
    lambda block: block.update(not_eligible="hold"),
    lambda block: block.update(rule="first_ready"),
])
def test_a_broken_order_is_refused(mutate):
    row = _rows()["E3"]
    mutate(row["boundary"])
    with pytest.raises(ValueError):
        check_boundary(row)


def test_a_multi_axis_stage_without_the_block_is_refused():
    row = _rows()["E4"]
    del row["boundary"]
    with pytest.raises(ValueError):
        check_boundary(row)
