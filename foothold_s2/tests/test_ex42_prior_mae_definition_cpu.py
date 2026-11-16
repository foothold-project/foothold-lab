"""The prior window's raw recount uses the MAE definition its saved cells carry (lead 2026-11-16 17:56). CPU only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from foothold_s2 import ex42_e1_v2
from foothold_s2.ex42_e1_v2 import stored_mae_definition as _stored_mae_definition
from foothold_s2.ex42_stage_judges import _check_prior_raw

PLAN = {"evaluation": {"e1_widened": {"graduation": {"mae_window_s": 0.5}}}}      # the real shape (plan ac5c66b5)
STEP, WINDOW, RECORD = {"mae_mps": 0.0234}, {"mae_mps": 0.0171, "mae_basis": "window", "mae_window_s": 0.5}, \
    {"mae_mps": 0.0234, "mae_basis": "step", "mae_window_s": 0.5}


def _cells(cell):
    return {"low": {"L0": {"eval_gt": {"fwd0.1": dict(cell)}}}, "side05": {"eval_gt": {"side+0.5": dict(cell)}}}


@pytest.mark.parametrize("cell,expect", [(STEP, (None, None)), (WINDOW, (0.5, None)), (RECORD, (None, 0.5))])
def test_the_saved_cells_name_their_definition(cell, expect):
    assert _stored_mae_definition(_cells(cell), 0.5) == expect


def test_disagreeing_or_empty_cells_keep_the_plan_definition():
    mixed = _cells(STEP); mixed["side05"]["eval_gt"]["side+0.5"] = dict(WINDOW)
    assert _stored_mae_definition(mixed, 0.5) == (0.5, None)
    assert _stored_mae_definition({"low": {"L0": {"state": "HOLD"}}}, 0.5) == (0.5, None)


@pytest.fixture
def fake_raw(monkeypatch):
    """Raw truth of one prior evaluation: a per-step MAE and a window MAE; measure_cells answers by the definition asked for."""
    calls = []

    def measure(evaluation, sha, seed, *, mae_window_s=None, record_window_s=None, **kw):
        calls.append((mae_window_s, record_window_s))
        if mae_window_s is not None:
            return _cells({**WINDOW, "mae_window_s": mae_window_s})
        return _cells(RECORD if record_window_s is not None else STEP)
    monkeypatch.setattr(ex42_e1_v2, "measure_cells", measure)
    return calls


def _prior(cell):
    return {"e1_v2_evaluation": "/nowhere", "checkpoint_sha256": "a" * 64, "conditions": {"eval_seed": 42}, "e1_v2_cells": _cells(cell)}


def test_same_definition_passes_and_a_step_prior_is_recounted_by_step(fake_raw):
    _check_prior_raw(_prior(WINDOW), PLAN)
    assert fake_raw[-1] == (0.5, None)
    _check_prior_raw(_prior(STEP), PLAN)
    assert fake_raw[-1] == (None, None)                      # not the plan's 0.5 window
    _check_prior_raw(_prior(RECORD), PLAN)
    assert fake_raw[-1] == (None, 0.5)


@pytest.mark.parametrize("cell", [STEP, WINDOW, RECORD])
def test_a_really_different_value_is_still_refused(fake_raw, cell):
    prior = _prior(cell)
    prior["e1_v2_cells"]["low"]["L0"]["eval_gt"]["fwd0.1"]["mae_mps"] += 0.001
    with pytest.raises(ValueError, match="prior E1 v2 raw cell evidence differs"):
        _check_prior_raw(prior, PLAN)


M1750 = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261115_135412/main/EX-42-B-E1-v29c_20261115_135412/eval/scores/m1750/ex42_score.json")


@pytest.mark.skipif(not M1750.is_file(), reason="old OUT absent")
def test_real_m1750_step_cells_recount_by_their_own_definition_and_not_by_the_plan_window():
    prior = json.loads(M1750.read_text())
    plan = PLAN
    _check_prior_raw(prior, plan)                           # no error: recounted by step
    prior_window = ex42_e1_v2.measure_cells(Path(prior["e1_v2_evaluation"]), prior["checkpoint_sha256"], prior["conditions"]["eval_seed"],
                                            mae_window_s=0.5)
    assert ex42_e1_v2.canonical_evidence(prior_window) != ex42_e1_v2.canonical_evidence(prior["e1_v2_cells"])   # the old check's failure


# ---- repeat_seed_judgments keys: ints from the judge, strings after a JSON round trip (lead 2026-11-16 18:01) ----
from foothold_s2.ex42_stage_judges import _int_seed_keys


def _exit(keys, last="PASS"):
    return {"current": {"items": {"yaw/eval_gt/fwd1.0": {"repeat_seed_judgments": dict(zip(keys, ("PASS", "PASS", last)))}}}}


def test_string_and_int_seed_keys_are_the_same_evidence():
    assert _int_seed_keys(_exit((42, 7, 13))) == _int_seed_keys(_exit(("42", "7", "13"))) == _exit((42, 7, 13))
    assert _int_seed_keys(json.loads(json.dumps(_exit((42, 7, 13))))) == _exit((42, 7, 13))


def test_a_really_different_seed_value_still_differs():
    assert _int_seed_keys(_exit((42, 7, 13), "PASS")) != _int_seed_keys(_exit(("42", "7", "13"), "FAIL"))


def test_only_the_seed_dict_keys_are_touched():
    other = {"x": {"7": 1}, "repeat_seed_judgments": {"a": 2}}
    assert _int_seed_keys(other) == other                    # other digit keys and non-digit seed keys stay as they are


OLD = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261115_135412/main/EX-42-B-E1-v29c_20261115_135412")


@pytest.mark.skipif(not (OLD / "eval/scores/m2000/ex42_score.json").is_file(), reason="old OUT absent")
def test_real_m2000_p1_is_built_from_the_saved_json_and_a_changed_value_is_refused(tmp_path):
    """The saved m2000 score is read from JSON as is (string seed keys, step prior window); only the repaired code builds its p1."""
    import shutil
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_eval_once import p1_score_from_measure
    scores = OLD / "eval/scores"
    plan = EX42Plan.load(json.loads((scores / "m2250/p1_score.json").read_text())["evaluation_plan"]["path"])
    approvals = Path(plan.path).parent / "ex42-approvals.yaml"
    saved = json.loads((scores / "m2000/ex42_score.json").read_text())
    shutil.copyfile(scores / "m2000/ex42_score.json", tmp_path / "ex42_score.json")
    p1 = p1_score_from_measure(saved, checkpoint=OLD / "model_2000.pt", iteration=2000, plan_path=plan.path, approvals_path=approvals,
                               stage_id="E1", output=tmp_path, evaluation_plan_path=plan.path)
    assert p1["judgment"] == saved["judgement"] == "FAIL" and p1["e1_exit_v2"] == saved["e1_exit_v2"]
    saved["e1_exit_v2"]["current"]["items"]["low/L5/eval_gt/side-0.2"]["success"] = 52          # a real value changed
    with pytest.raises(ValueError, match="two-window judgment differs"):
        p1_score_from_measure(saved, checkpoint=OLD / "model_2000.pt", iteration=2000, plan_path=plan.path, approvals_path=approvals,
                              stage_id="E1", output=tmp_path, evaluation_plan_path=plan.path)


# ---- the judge's own recount of the previous window (ex42_e1_v2._verified_cells, lead 2026-11-16 18:05) ----
def test_the_test_plan_really_asks_for_the_half_second_window():
    assert ex42_e1_v2.plan_mae_window_s(PLAN) == 0.5


def test_verified_cells_counts_a_saved_step_window_by_its_saved_definition(fake_raw):
    prior = _prior(STEP)
    ex42_e1_v2._verified_cells(prior, Path("/nowhere"), 42, 0.5, saved_definition=True)
    assert fake_raw[-1] == (None, None)
    with pytest.raises(ValueError, match="cached cells differ"):                  # without the saved definition: the old refusal
        ex42_e1_v2._verified_cells(prior, Path("/nowhere"), 42, 0.5)
    assert fake_raw[-1] == (0.5, None)
    ex42_e1_v2._verified_cells(_prior(WINDOW), Path("/nowhere"), 42, 0.5, saved_definition=True)
    assert fake_raw[-1] == (0.5, None)


@pytest.mark.parametrize("cell", [STEP, WINDOW, RECORD])
def test_verified_cells_still_refuses_a_really_different_raw_value(fake_raw, cell):
    prior = _prior(cell)
    prior["e1_v2_cells"]["low"]["L0"]["eval_gt"]["fwd0.1"]["mae_mps"] += 0.001
    with pytest.raises(ValueError, match="cached cells differ"):
        ex42_e1_v2._verified_cells(prior, Path("/nowhere"), 42, 0.5, saved_definition=True)


GRAD_PLAN = Path("/home/jay/mai/tmp/sonnet-code-lx/e1-graduation-plan-v2/plan/ex42-prep.yaml")


@pytest.mark.skipif(not (M1750.is_file() and GRAD_PLAN.is_file()), reason="old OUT or graduation plan absent")
def test_real_m1750_with_the_graduation_plan_is_not_refused_by_the_judge_when_it_is_the_previous_window(monkeypatch):
    """The judge's real path for m2000 drops m1750 (another evaluation policy sha), which hides the recount; force it to be kept."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_e0_judge import load_baseline
    from foothold_s2.ex42_score import ROOT, config, digest
    plan = EX42Plan.load(GRAD_PLAN)
    assert plan.sha256.startswith("ac5c66b5") and ex42_e1_v2.plan_mae_window_s(plan.document) == 0.5
    scores = M1750.parent.parent
    score = json.loads((scores / "m2000/ex42_score.json").read_text())
    previous = json.loads(M1750.read_text())
    monkeypatch.setattr(ex42_e1_v2, "c1_previous_window", lambda s, p, prev: (prev, False))
    cfg, _ = config()
    baseline = load_baseline(ROOT, cfg, digest); baseline["_sha256"] = cfg["baseline"]["sha256"]
    measured = plan.document["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
    result = ex42_e1_v2.judge_e1_v2(score, baseline, measured, plan.document, previous=previous, checkpoint=Path(score["checkpoint"]),
                                    evaluation=Path(score["e1_v2_evaluation"]), seed=score["conditions"]["eval_seed"])
    assert "provenance_error" not in json.dumps(result.get("e1_exit_v2", {})), result.get("reason")
    assert "cached cells differ" not in str(result.get("reason"))
