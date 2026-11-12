"""The plan rows of M, E6a and E6b name their exit judges, and Q12 no longer gates the E6b approval cell.

Ledger: decisions.tsv 2026-11-11 01:1x (the ceiling is handled by the depth camera and the upper policy's crouch
command; Q12 is not a blocker). The judges themselves are tested in test_ex42_late_exit_judges_cpu.py."""
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_stage_judges as judges
from foothold_s2.curriculum.ex42_prep import EX42Plan

PLAN = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
Q12 = "prerequisites.q12_sensor_decision"
CELLS = {"M": "mapoff_two_window_m", "E6a": "posture_two_window_e6a", "E6b": "kind_two_window_e6b"}


@pytest.fixture(scope="module")
def document():
    return yaml.safe_load(PLAN.read_text(encoding="utf-8"))


def row(document, stage_id):
    return next(r for r in document["stages"] if r["id"] == stage_id)


@pytest.mark.parametrize("stage_id,name", sorted(CELLS.items()))
def test_the_row_names_the_judge_registered_for_that_stage(document, stage_id, name):
    assert row(document, stage_id)["exit_judge"] == name
    adapter = judges.adapter_for(document, stage_id)
    assert adapter is judges.ADAPTERS[name] and adapter.stage_id == stage_id


def test_a_judge_of_another_stage_is_not_what_the_row_names(document):
    named = {stage_id: judges.adapter_name(document, stage_id) for stage_id in CELLS}
    assert len(set(named.values())) == 3          # three rows, three different judges


def test_q12_is_not_a_required_cell_of_the_e6b_approval(document):
    contract = row(document, "E6b")["authorization_contract"]
    assert contract["required_string_paths"] == []
    assert Q12 not in [*contract["required_sha256_paths"], *contract["required_boolean_paths"], *contract["required_values"]]


def test_the_jump_rows_are_left_as_they_were(document):
    # out of this change (the jump study is decided separately): they still list the Q12 cell
    for stage_id in ("J0", "J1", "J2", "J3", "J4"):
        assert Q12 in row(document, stage_id)["authorization_contract"]["required_string_paths"]


def test_the_plan_still_loads_with_the_new_cells():
    plan = EX42Plan.load(PLAN)
    assert {"M", "E6a", "E6b"} <= set(plan.runtime_stage_ids)
