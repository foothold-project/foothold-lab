"""env_diff_compare: OPS v0.2 5.1 절 기준 (속도 차 0.015 · yaw 0.05 · 성공 수 차 3 · 넘어짐 0)."""
import copy

import pytest

from foothold_s2.nav import env_diff_compare as ec


def _case(cmd, ratio, success=32, fell=0, envs=32):
    return {"command": cmd, "envs": envs, "fell": fell, "success": success, "mean_ratio": ratio, "mean_move_m": 1.0}


def _res(**over):
    cases = {"fwd0.2": _case([0.2, 0, 0], 0.9), "yaw0.5": _case([0, 0, 0.5], 0.9)}
    cases.update(over)
    return {"cases": cases, "lower_sha256": "x"}


def test_identical_runs_pass_and_small_diffs_pass():
    a = _res()
    assert ec.compare(a, copy.deepcopy(a))["overall"] == "PASS"
    b = _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9 + 0.014 / 0.2, success=30)})        # 속도 차 0.014 · 성공 수 차 2
    assert ec.compare(a, b)["overall"] == "PASS"


def test_speed_diff_between_limits_is_warn_and_over_fail_limit_is_fail():
    a = _res()
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9 + 0.02 / 0.2)}))["overall"] == "WARN"
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9 + 0.04 / 0.2)}))["overall"] == "FAIL"


def test_fall_in_either_environment_fails_and_success_count_gap_warns():
    a = _res()
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9, fell=1)}))["overall"] == "FAIL"
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9, success=27)}))["overall"] == "WARN"


def test_yaw_uses_005_rad_per_s_and_mismatched_cases_are_refused():
    a = _res()
    assert ec.compare(a, _res(**{"yaw0.5": _case([0, 0, 0.5], 0.9 + 0.04 / 0.5)}))["overall"] == "PASS"
    assert ec.compare(a, _res(**{"yaw0.5": _case([0, 0, 0.5], 0.9 + 0.06 / 0.5)}))["overall"] == "FAIL"
    with pytest.raises(ValueError):
        ec.compare(a, {"cases": {"fwd0.2": _case([0.2, 0, 0], 0.9)}})
