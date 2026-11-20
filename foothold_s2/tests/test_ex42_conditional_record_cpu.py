"""Graduation plan v3: conditional_record turns FAIL side cells of the lower-bound class into record cells, all or nothing."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from foothold_s2.ex42_e1_v2 import apply_conditional_record, apply_record_cells, check_graduation

BLOCK = {"cells": [f"low/L5/{m}/side{s}0.2" for m in ("eval_gt", "eval_pred") for s in "+-"],
         "success_min": 48, "R_min": 0.85, "survival_min": 64, "companion": "L0_same_map_same_command_PASS", "decision": "e2708c0f"}
PLAN = {"evaluation": {"e1_widened": {"graduation": {"mae_window_s": 0.5, "conditional_record": BLOCK}}}}
PLAN_V2 = {"evaluation": {"e1_widened": {"graduation": {"mae_window_s": 0.5}}}}
M2000_SCORE = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261115_135412/main/EX-42-B-E1-v29c_20261115_135412/eval/scores/m2000/ex42_score.json")
PLAN_V3_FILE = Path("/home/jay/mai/tmp/sonnet-code-lx/e1-graduation-plan-v3/plan/ex42-prep.yaml")


def cell(judgement, success=50, R=0.874, survival=64, **extra):
    return {"judgement": judgement, "near_threshold": False, "R": R, "mae_mps": 0.03, "success": success, "survival": survival, **extra}


def result(**overrides):
    items = {"low/L0/eval_gt/side-0.2": cell("PASS", 60, 0.92), "low/L0/eval_pred/side-0.2": cell("PASS", 60, 0.92),
             "low/L5/eval_gt/side-0.2": cell("FAIL"), "low/L5/eval_pred/side-0.2": cell("PASS", 55, 0.9),
             "low/L5/eval_gt/fwd0.2": cell("PASS", 60, 0.98)}
    items.update(overrides)
    return {"judgement": "FAIL", "items": items}


def test_a_no_key_is_a_no_op_and_the_same_object_comes_back():
    base = result()
    before = json.dumps(base, sort_keys=True)
    assert apply_conditional_record(base, PLAN_V2) is base and apply_conditional_record(base, {"evaluation": {}}) is base
    assert json.dumps(base, sort_keys=True) == before


def test_b_all_fails_inside_cells_above_floor_with_passing_companion_become_record():
    out = apply_conditional_record(result(), PLAN)
    row = out["items"]["low/L5/eval_gt/side-0.2"]
    assert row["role"] == "record" and row["judgement_if_judged"] == "FAIL" and row["conditional_record"] == "e2708c0f"
    assert "judgement" not in row and row["success"] == 50 and row["R"] == 0.874          # value kept, not in the verdict
    assert out["judgement"] == "PASS"
    assert apply_record_cells(out, {"evaluation": {}}) is not None                       # still a normal result shape


def test_b2_exactly_on_the_floor_counts_as_above_it():
    out = apply_conditional_record(result(**{"low/L5/eval_gt/side-0.2": cell("FAIL", 48, 0.85, 64)}), PLAN)
    assert out["items"]["low/L5/eval_gt/side-0.2"]["role"] == "record"


@pytest.mark.parametrize("field,value", [("success", 47), ("R", 0.849), ("survival", 63)])
def test_c_one_cell_below_the_floor_changes_nothing(field, value):
    base = result(**{"low/L5/eval_gt/side-0.2": cell("FAIL", **{field: value})})
    assert apply_conditional_record(base, PLAN) is base


def test_d_a_fail_outside_cells_changes_nothing():
    base = result(**{"low/L5/eval_gt/fwd0.2": cell("FAIL", 60, 0.98), "low/L0/eval_gt/fwd0.2": cell("PASS", 60, 0.98)})   # stands on the floor with a PASS companion, but is not a listed cell
    assert apply_conditional_record(base, PLAN) is base
    base = result(**{"low/L0/eval_gt/side-0.2": cell("FAIL", 60, 0.92)})            # the companion is outside cells too
    assert apply_conditional_record(base, PLAN) is base


def test_e_companion_not_pass_changes_nothing():
    for companion in (cell("FAIL", 60, 0.92), cell("HOLD", 60, 0.92)):
        base = result(**{"low/L0/eval_gt/side-0.2": companion})
        assert apply_conditional_record(base, PLAN) is base
    base = result()
    del base["items"]["low/L0/eval_gt/side-0.2"]
    assert apply_conditional_record(base, PLAN) is base                                 # no companion cell at all


def test_f_hold_cells_are_not_looked_at_and_stay_hold():
    out = apply_conditional_record(result(**{"low/L5/eval_gt/fwd0.2": cell("HOLD", 60, 0.98)}), PLAN)
    assert out["items"]["low/L5/eval_gt/side-0.2"]["role"] == "record"                  # a HOLD elsewhere does not block it
    assert out["items"]["low/L5/eval_gt/fwd0.2"]["judgement"] == "HOLD" and out["judgement"] == "HOLD"
    held_cell = result(**{"low/L5/eval_gt/side-0.2": cell("HOLD")})
    assert apply_conditional_record(held_cell, PLAN) is held_cell                       # nothing failed: nothing to convert


@pytest.mark.skipif(not M2000_SCORE.is_file(), reason="m2000 official score not on this machine")
def test_g_real_m2000_cell_with_success_50_and_R_0874_turns_into_a_record_cell():
    current = json.loads(M2000_SCORE.read_text())["e1_exit_v2"]["current"]
    fails = [k for k, v in current["items"].items() if v.get("judgement") == "FAIL"]
    assert fails == ["low/L5/eval_gt/side-0.2"]
    assert current["items"][fails[0]]["success"] == 50 and round(current["items"][fails[0]]["R"], 3) == 0.874
    out = apply_conditional_record(copy.deepcopy(current), PLAN)
    assert out["items"][fails[0]]["role"] == "record" and out["judgement"] == "PASS"
    assert apply_conditional_record(current, PLAN_V2) is current


def test_the_graduation_check_accepts_the_block_and_refuses_anything_else():
    assert check_graduation({"mae_window_s": 0.5, "conditional_record": BLOCK})["conditional_record"] == BLOCK
    for bad in ({**BLOCK, "success_min": 0}, {**BLOCK, "R_min": 1.5}, {**BLOCK, "cells": ["low/L5/eval_gt/side+0.4"]},
                {**BLOCK, "companion": "none"}, {**BLOCK, "decision": "zz"}, {**BLOCK, "extra": 1}, {k: v for k, v in BLOCK.items() if k != "decision"}):
        with pytest.raises(ValueError, match="unapproved"):
            check_graduation({"conditional_record": bad})


@pytest.mark.skipif(not PLAN_V3_FILE.is_file(), reason="plan v3 not on this machine")
def test_the_locked_plan_v3_file_carries_exactly_this_block_and_its_sha_is_pinned():
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    plan = EX42Plan.load(PLAN_V3_FILE)
    assert plan.document["evaluation"]["e1_widened"]["graduation"]["conditional_record"] == BLOCK
    assert plan.sha256 == "ad05c43e462cb0f100dcbc10e08e2ce8e0a8c641682aa9963207145f9c55bdb3"
