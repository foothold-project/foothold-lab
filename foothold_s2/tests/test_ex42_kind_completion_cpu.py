"""Known input checks for the E2 START arrival support window."""

import numpy as np
import pytest

from foothold_s2.eval.ex42_kind_completion import score_last_support


def _trace():
    root_x = np.zeros((20, 64), dtype=np.float64)
    root_x[5:, :] = 6.5
    alive = np.ones((20, 64), dtype=bool)
    return {"root_x_local_m": root_x, "alive": alive, "dt": np.array(0.1)}


def test_arrival_requires_half_second_alive_after_reach():
    trace = _trace()
    row = score_last_support(trace, finish_x_m=6.5, settle_s=0.5)
    assert row["success_count"] == row["survival_count"] == 64
    trace["root_x_local_m"][:, 0] = 0
    trace["root_x_local_m"][17:, 1] = 6.5
    trace["root_x_local_m"][:17, 1] = 0
    trace["alive"][8:, 2] = False
    row = score_last_support(trace, finish_x_m=6.5, settle_s=0.5)
    assert row["success_count"] == 61
    assert row["survival_count"] == 63
    assert row["per_env"][0]["reason"] == "not_reached"
    assert row["per_env"][1]["reason"] == "settle_window_short"
    assert row["per_env"][2]["reason"] == "reset_before_settle"


def test_reset_and_missing_trace_do_not_silently_pass():
    trace = _trace()
    trace["alive"][5, 0] = False
    trace["alive"][6, 0] = True
    with pytest.raises(ValueError, match="resurrect"):
        score_last_support(trace, finish_x_m=6.5, settle_s=0.5)
    trace = _trace()
    trace["root_x_local_m"][0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        score_last_support(trace, finish_x_m=6.5, settle_s=0.5)
    trace = _trace()
    del trace["root_x_local_m"]
    with pytest.raises((ValueError, KeyError)):
        score_last_support(trace, finish_x_m=6.5, settle_s=0.5)
