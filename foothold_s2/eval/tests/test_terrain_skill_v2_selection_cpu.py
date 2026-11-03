import pytest

from foothold_s2.eval import terrain_skill_v2_run as w78


def test_w78_defaults_to_complete_240_combinations():
    selected = w78.select_v2_cases("all")
    assert tuple(selected) == tuple(w78.V2_CASES)
    assert len(w78.expected_combinations(selected)) == 240


def test_w78_approved_periodic_selector_is_exactly_48_combinations():
    selected = w78.select_v2_cases("stairs_side_left,stairs_side_right")
    assert tuple(selected) == w78.PERIODIC_SIDE_CASES
    expected = w78.expected_combinations(selected)
    assert len(expected) == 48
    assert {row[3] for row in expected} == set(w78.PERIODIC_SIDE_CASES)


@pytest.mark.parametrize("value", [
    "stairs_side_left", "stairs_side_right,stairs_side_left",
    "stairs_side_left,stairs_side_left", "stairs_side_left,unknown", "",
])
def test_w78_selector_rejects_partial_ambiguous_or_invalid_coverage(value):
    if value == "":
        assert len(w78.select_v2_cases(value)) == len(w78.V2_CASES)
        return
    with pytest.raises(ValueError, match="case selector"):
        w78.select_v2_cases(value)


def test_w78_require_complete_rejects_one_missing_periodic_combination():
    cases = w78.select_v2_cases("stairs_side_left,stairs_side_right")
    complete = w78.expected_combinations(cases)
    w78.require_complete(complete, cases)
    complete.remove(next(iter(complete)))
    with pytest.raises(RuntimeError, match="47/48"):
        w78.require_complete(complete, cases)
