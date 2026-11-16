import numpy as np
import pytest

from foothold_s2.nav import n1_check as n1


def _err(scale, T=40, hold=5, n=16, seed=0):
    return np.random.default_rng(seed).normal(0, scale, (T, hold, n, 3))


def test_p95_matches_a_hand_computed_value():
    e = np.zeros((1, 5, 1, 3)); e[0, :, 0, 0] = [0.0, 0.1, 0.2, 0.3, 0.4]
    got = n1.p95(e, np.full((1, 1), -1))
    assert got["samples"] == 5 and got["vx"] == pytest.approx(np.quantile([0, 0.1, 0.2, 0.3, 0.4], 0.95)) and got["vy"] == 0.0


def test_steps_after_the_first_done_are_left_out_but_the_done_step_stays():
    e = np.zeros((1, 5, 2, 3)); e[0, :, 1, 0] = 9.0           # env 1 은 끝난 뒤 값이 크다
    done = np.array([[-1, 2]])
    m = n1.valid_mask(done, 5)
    assert m[0, :, 0].all() and list(m[0, :, 1]) == [True, True, True, False, False]
    got = n1.p95(e, done)
    assert got["samples"] == 8 and got["vx"] == pytest.approx(9.0)    # 끝난 스텝 (k=2) 까지의 세 값은 남는다
    e[0, 3:, 1, 0] = 1000.0
    assert n1.p95(e, done)["vx"] == pytest.approx(9.0)


def test_decision_switches_at_twenty_percent_in_both_directions():
    gt = n1.p95(_err(0.10), np.full((40, 16), -1))
    same = n1.compare_maps(gt, n1.p95(_err(0.10, seed=1), np.full((40, 16), -1)))
    worse = n1.compare_maps(gt, n1.p95(_err(0.14, seed=2), np.full((40, 16), -1)))
    better = n1.compare_maps(gt, n1.p95(_err(0.07, seed=3), np.full((40, 16), -1)))
    assert same["teacher_map"] == "gt" and worse["teacher_map"] == "recon" and better["teacher_map"] == "recon"
    assert same["relative_difference"]["l2"] < 0.2 < worse["relative_difference"]["l2"] and set(same["relative_difference"]) == {"l2", "vx", "vy", "wz"}


def test_bad_inputs_are_refused():
    with pytest.raises(ValueError, match="finite"):
        n1.p95(np.full((1, 5, 1, 3), np.nan), np.full((1, 1), -1))
    with pytest.raises(ValueError, match="done_step"):
        n1.p95(np.zeros((2, 5, 3, 3)), np.full((2, 4), -1))
