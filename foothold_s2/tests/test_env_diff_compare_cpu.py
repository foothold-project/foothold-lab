"""env_diff_compare: OPS v0.2 5.1 절 기준 (속도 차 0.015 · yaw 0.05 · 성공 수 차 3 · 넘어짐 0)."""
import copy

import pytest

from foothold_s2.nav import env_diff_compare as ec


def _case(cmd, ratio, success=32, fell=0, envs=32):
    return {"command": cmd, "envs": envs, "fell": fell, "success": success, "mean_ratio": ratio, "mean_move_m": 1.0}


def _res(**over):
    cases = {"fwd0.2": _case([0.2, 0, 0], 0.9), "yaw0.5": _case([0, 0, 0.5], 0.9)}
    cases.update(over)
    return {"cases": cases, "lower_sha256": "x", "seed": 0, "room_seed": 0}


def test_identical_runs_pass_and_small_diffs_pass():
    a = _res()
    assert ec.compare(a, copy.deepcopy(a))["overall"] == "PASS"
    b = _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9 + 0.014 / 0.2, success=30)})        # 속도 차 0.014 · 성공 수 차 2
    assert ec.compare(a, b)["overall"] == "PASS"


def test_speed_diff_between_limits_is_warn_and_over_fail_limit_is_fail():
    a = _res()
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9 + 0.02 / 0.2)}))["overall"] == "WARN"
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9 + 0.04 / 0.2)}))["overall"] == "FAIL"


def test_fall_count_gap_of_one_passes_two_fails_and_equal_falls_pass():
    a = _res()
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9, fell=1)}))["overall"] == "PASS"          # 차 1
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9, fell=2)}))["overall"] == "FAIL"          # 차 2
    loc = _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9, fell=1)})
    assert ec.compare(loc, copy.deepcopy(loc))["overall"] == "PASS"                                          # 로컬 기준값에 1 이 있어도 같으면 통과


def test_success_count_gap_warns_and_different_seeds_are_refused():
    a = _res()
    assert ec.compare(a, _res(**{"fwd0.2": _case([0.2, 0, 0], 0.9, success=27)}))["overall"] == "WARN"


def test_yaw_uses_005_rad_per_s_and_mismatched_cases_are_refused():
    a = _res()
    assert ec.compare(a, _res(**{"yaw0.5": _case([0, 0, 0.5], 0.9 + 0.04 / 0.5)}))["overall"] == "PASS"
    assert ec.compare(a, _res(**{"yaw0.5": _case([0, 0, 0.5], 0.9 + 0.06 / 0.5)}))["overall"] == "FAIL"
    with pytest.raises(ValueError):
        ec.compare(a, {"cases": {"fwd0.2": _case([0.2, 0, 0], 0.9)}})


def test_different_or_missing_seed_is_refused_unless_assumed():
    a, b = _res(), _res()
    b["seed"] = 1
    with pytest.raises(ValueError, match="seed"):
        ec.compare(a, b)
    old = _res(); del old["seed"]
    with pytest.raises(ValueError, match="assume"):
        ec.compare(old, _res())
    assert ec.compare(old, _res(), assume_seed=(0, 0))["seeds_assumed"]
