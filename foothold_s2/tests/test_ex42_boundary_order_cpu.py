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


def test_e3_start_block_is_the_e2_end_state_plus_the_entry_axis_only():
    rows = _rows()
    e2 = {(r.get("kind") or r.get("kinds_of")): r for r in rows["E2"]["terrain"]["exposure_at_E2"]["positive"]}
    e3 = {(r.get("kind") or r.get("kinds_of")): r for r in rows["E3"]["terrain"]["exposure_at_E3"]["positive"]}
    assert set(e3) == set(e2)                                            # no kind opens at the stage entry
    assert e3["continuous"] == e2["continuous"]                          # the continuous cap does not move (L+ is its own boundary)
    low2, low3 = e2["stepping_stones_low"], e3["stepping_stones_low"]
    assert low3["share"] == low2["share"] and low3["level_cap"] == low2["level_cap"] + 1   # D: that kind's cap +1, share unchanged
    assert rows["E3"]["terrain"]["k_ladder"]["order"][0] == {"family": "C", "kind": "flat", "level_cap": 0}


def test_command_shares_follow_the_canon_c_boundaries():
    rows = _rows()
    e1f, e3, e4 = rows["E1F"]["shares"], rows["E3"], rows["E4"]
    assert e3["shares"] == e1f and e1f["flag"] == 0.1                    # E2 changes no command share
    after = e3["command_allocation_boundary"]["shares"]
    assert abs(sum(after.values()) - 1.0) < 1e-9 and after["flag"] == 0.15
    assert (after["forward"], after["walk_left"], after["walk_right"]) == (0.14, 0.05, 0.05)
    assert {k: v for k, v in after.items() if k not in ("forward", "walk_left", "walk_right", "flag")} == \
           {k: v for k, v in e1f.items() if k not in ("forward", "walk_left", "walk_right", "flag")}
    assert e4["shares"] == after
    assert e4["command_allocation_boundary"]["targets"] == {"flag": 0.2, "forward": 0.11, "diagonal_total": 0.07}
    last = e4["command_allocation_boundary"]["shares"]
    assert abs(sum(last.values()) - 1.0) < 1e-9 and (last["flag"], last["forward"]) == (0.2, 0.11)
    diagonal = [k for k in last if k.startswith("diag_")]
    assert abs(sum(last[k] for k in diagonal) - 0.07) < 1e-9
    for k in diagonal:                                                   # the four slots keep their ratio (scaled 7/9)
        assert abs(last[k] / after[k] - 0.07 / 0.09) < 1e-6
    assert {k: v for k, v in last.items() if k not in ("forward", "flag", *diagonal)} == \
           {k: v for k, v in after.items() if k not in ("forward", "flag", *diagonal)}
    for stage in ("E5", "E6a", "E6b"):
        assert rows[stage]["shares"] == last


def test_every_stage_the_share_contract_reads_has_an_explicit_vector():
    from types import SimpleNamespace

    from foothold_s2.commands.ex42_shares import read_contract

    document = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in document["stages"]}
    assert rows["E2"]["shares"] == rows["E1F"]["shares"]                 # CG E.2 E2: no command share moves at the K boundary
    plan = SimpleNamespace(document=document)
    for stage in ("E1F", "E2", "E3", "E4", "E5", "E6a", "E6b"):
        contract = read_contract(plan, stage)
        assert contract["shares"] == rows[stage]["shares"]
    with pytest.raises(ValueError):                                      # the optional M branch has no fixed vector of its own
        read_contract(plan, "M")
