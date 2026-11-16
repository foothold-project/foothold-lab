"""The prior window's raw recount uses the MAE definition its saved cells carry (lead 2026-11-16 17:56). CPU only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from foothold_s2 import ex42_e1_v2
from foothold_s2.ex42_stage_judges import _check_prior_raw, _stored_mae_definition

PLAN = {"evaluation": {}, "graduation": {"mae_window_s": 0.5}}
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
    plan = {"evaluation": {}, "graduation": {"mae_window_s": 0.5}}
    _check_prior_raw(prior, plan)                           # no error: recounted by step
    prior_window = ex42_e1_v2.measure_cells(Path(prior["e1_v2_evaluation"]), prior["checkpoint_sha256"], prior["conditions"]["eval_seed"],
                                            mae_window_s=0.5)
    assert ex42_e1_v2.canonical_evidence(prior_window) != ex42_e1_v2.canonical_evidence(prior["e1_v2_cells"])   # the old check's failure
