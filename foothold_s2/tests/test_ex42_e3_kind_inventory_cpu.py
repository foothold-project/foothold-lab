"""Known-input checks for the CG E3 five START kinds and opened level cells."""
from pathlib import Path

import pytest
import yaml

from foothold_s2.eval.ex42_stage_kind_bundle import e3_target_inventory


PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"


def test_e3_inventory_has_five_start_kinds_and_only_opened_representative_levels():
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    result = e3_target_inventory(plan, {"A/stepping_stones_low": 6, "B/rough": 3})
    assert len(result["targets"]) == 20
    assert {row["kind"] for row in result["targets"] if row["family"] == "A"
            and row["level"] == 5} == {
                "stepping_stones_low", "stepping_stones_high", "balance_beams",
                "stepping_beams", "gaps"}
    assert result["opened_cells"] == [
        {"family": "A", "kind": "stepping_stones_low", "level": n} for n in (0, 5, 6)
    ] + [{"family": "B", "kind": "rough", "level": n} for n in (0, 3)]
    assert len(result["missing_targets"]) == 18


def test_e3_inventory_rejects_an_unapproved_kind_and_a_missing_start_kind():
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="outside approved"):
        e3_target_inventory(plan, {"B/beam": 0})
    plan["evaluation"]["e3_kind_exit"]["start_kinds"].remove("gaps")
    with pytest.raises(ValueError, match="target list"):
        e3_target_inventory(plan, {})
