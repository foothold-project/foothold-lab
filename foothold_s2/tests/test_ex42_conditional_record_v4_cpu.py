"""Graduation plan v4: conditional_record.from_iteration keeps the rule off windows before that update (m2000 is not counted)."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from foothold_s2.ex42_e1_v2 import _window_iteration, apply_conditional_record, apply_conditional_record_prior, check_graduation
from foothold_s2.tests.test_ex42_conditional_record_cpu import BLOCK, cell, result

B4 = {**BLOCK, "from_iteration": 2250}
PLAN4 = {"evaluation": {"e1_widened": {"graduation": {"mae_window_s": 0.5, "conditional_record": B4}}}}
PLAN3 = {"evaluation": {"e1_widened": {"graduation": {"mae_window_s": 0.5, "conditional_record": BLOCK}}}}
PLAN_V4_FILE = Path("/home/jay/mai/tmp/sonnet-code-lx/e1-graduation-plan-v4/plan/ex42-prep.yaml")


def test_m2000_window_is_not_covered_fail_cell_stays_fail():
    base = result()
    out = apply_conditional_record(base, PLAN4, 2000)
    assert out is base and out["items"]["low/L5/eval_gt/side-0.2"]["judgement"] == "FAIL"


def test_m2250_window_is_covered_same_values_pass():
    out = apply_conditional_record(result(), PLAN4, 2250)
    assert out["judgement"] == "PASS" and out["items"]["low/L5/eval_gt/side-0.2"]["role"] == "record"


def test_boundary_is_inclusive_and_later_windows_covered():
    assert apply_conditional_record(result(), PLAN4, 2500)["judgement"] == "PASS"
    base = result()
    assert apply_conditional_record(base, PLAN4, 2249) is base      # a >= turned into > would fail the 2250 test above; < 2250 stays off


def test_previous_window_2000_is_not_covered_when_judging_m2250():
    prior = {"judgement": "FAIL", "items": result()["items"]}
    assert apply_conditional_record(prior, PLAN4, _window_iteration("/x/model_2000.pt")) is prior
    assert apply_conditional_record(prior, PLAN4, _window_iteration("/x/model_2250.pt"))["judgement"] == "PASS"


@pytest.mark.parametrize("value", [None, "2250", "model", 2250.0])
def test_unreadable_iteration_applies_nothing_and_says_so(value):
    base = result()
    out = apply_conditional_record(base, PLAN4, value)
    assert out["items"] == base["items"] and out["judgement"] == "FAIL" and "unreadable" in out["conditional_record_skipped"]


def test_window_iteration_reads_the_checkpoint_name_only():
    assert _window_iteration("/a/b/model_2250.pt") == 2250 and _window_iteration(Path("model_250.pt")) == 250
    for bad in (None, 5, "model_x.pt", "/a/ckpt_2250.pt", "model_2250.pt.bak"):
        assert _window_iteration(bad) is None


def test_plan_without_from_iteration_behaves_as_v3_at_any_window():
    for it in (None, 1750, 2000, 2250):
        assert apply_conditional_record(result(), PLAN3, it)["judgement"] == "PASS"


@pytest.mark.parametrize("bad", [0, -250, 2251, 2250.0, "2250", True])
def test_check_graduation_refuses_a_bad_from_iteration(bad):
    with pytest.raises(ValueError):
        check_graduation({"mae_window_s": 0.5, "conditional_record": {**BLOCK, "from_iteration": bad}})


def test_check_graduation_accepts_v4_and_still_refuses_an_unknown_key():
    check_graduation({"mae_window_s": 0.5, "conditional_record": B4})
    with pytest.raises(ValueError):
        check_graduation({"mae_window_s": 0.5, "conditional_record": {**B4, "extra": 1}})


@pytest.mark.skipif(not PLAN_V4_FILE.is_file(), reason="plan v4 file not on this machine")
def test_plan_v4_file_differs_from_v3_by_the_one_line():
    v3 = Path(str(PLAN_V4_FILE).replace("plan-v4", "plan-v3")).read_text().splitlines()
    v4 = PLAN_V4_FILE.read_text().splitlines()
    assert len(v4) == len(v3) + 1 and [x for x in v4 if x not in v3] == ["        from_iteration: 2250"]


def test_prior_window_is_judged_at_its_own_update_number_not_the_current_one():
    prior = {"judgement": "FAIL", "items": result()["items"]}
    assert apply_conditional_record_prior(prior, PLAN4, {"checkpoint": "/x/model_2000.pt"}) is prior                    # m2250 judging, previous m2000
    assert apply_conditional_record_prior(prior, PLAN4, {"checkpoint": "/x/model_2250.pt"})["judgement"] == "PASS"      # m2500 judging, previous m2250
    out = apply_conditional_record_prior(prior, PLAN4, {})                                                              # unreadable previous
    assert out["judgement"] == "FAIL" and "unreadable" in out["conditional_record_skipped"]


def test_judge_wires_current_window_by_its_checkpoint_and_previous_by_its_own_score():
    import inspect
    from foothold_s2 import ex42_e1_v2
    src = inspect.getsource(ex42_e1_v2._judge_e1_v2)
    assert "plan, _window_iteration(checkpoint))" in src                         # current window: the checkpoint being judged
    assert "apply_conditional_record_prior(prior_v2, plan, previous)" in src      # previous window: its own score, never the current checkpoint
    assert "apply_conditional_record(prior_v2" not in src
