"""지형 열 배정 · p_advance · 승급 규칙 L0 (15 §9 · 14 §9)."""

import numpy as np
import pytest

from foothold_s2.curriculum import rules
from foothold_s2.terrains import columns, progression


def test_fifty_columns_give_integer_counts_per_terrain():
    counts = columns.column_assignment(columns.FULL, columns.FULL_COLS)
    assert counts == {"pyramid_stairs": 5, "pyramid_stairs_inv": 5, "boxes": 4, "random_rough": 4,
                      "hf_pyramid_slope": 2, "hf_pyramid_slope_inv": 2, "stage_stairs": 1,
                      "stepping_stones_low": 7, "stepping_stones_high": 5, "balance_beams": 5,
                      "stepping_beams": 5, "gaps": 3, "flat": 2}
    assert sum(counts.values()) == 50
    exp = columns.expected_counts(columns.FULL, 50)
    assert all(abs(exp[n] - counts[n]) < 1e-9 for n in counts)


def test_negative_control_twenty_columns_break_the_proportions():
    counts = columns.column_assignment(columns.FULL, 20)
    assert counts["hf_pyramid_slope"] == 0 and counts["flat"] == 0
    exp = columns.expected_counts(columns.FULL, 20)
    assert abs(exp["hf_pyramid_slope"] - counts["hf_pyramid_slope"]) > 0.5


def test_s1a_continuous_only_uses_23_columns_exactly():
    counts = columns.column_assignment(columns.CONTINUOUS, columns.CONTINUOUS_COLS)
    assert counts == {"pyramid_stairs": 5, "pyramid_stairs_inv": 5, "boxes": 4, "random_rough": 4,
                      "hf_pyramid_slope": 2, "hf_pyramid_slope_inv": 2, "stage_stairs": 1}
    assert sum(counts.values()) == 23
    exp = columns.expected_counts(columns.CONTINUOUS, 23)
    assert all(abs(exp[n] - round(exp[n])) < 1e-9 for n in exp)
    exp50 = columns.expected_counts(columns.CONTINUOUS, 50)
    assert any(abs(exp50[n] - round(exp50[n])) > 0.1 for n in exp50)


def test_column_types_are_contiguous_blocks_in_declared_order():
    types = columns.column_types(columns.CONTINUOUS, 23)
    assert types[:5] == ["pyramid_stairs"] * 5 and types[5:10] == ["pyramid_stairs_inv"] * 5
    assert types[-1] == "stage_stairs"


def test_p_advance_values():
    f = progression.p_advance
    assert f(0) == 0 and f(1000) == 0
    assert f(2250) == pytest.approx(0.1607, abs=1e-3)
    assert f(4500) == pytest.approx(0.45, abs=1e-3)
    assert f(8000) == pytest.approx(0.9) and f(9000) == pytest.approx(0.9)


def test_p_advance_old_500_4000_values_are_gone():
    assert progression.p_advance(2250, T_start=500, T_end=4000) == pytest.approx(0.45, abs=1e-3)
    assert progression.p_advance(2250) != pytest.approx(0.45, abs=1e-3)


def test_reassign_columns_resamples_everyone_and_skips_gap_envs():
    rng = np.random.default_rng(0)
    groups = np.array(["sparse"] * 1000 + ["gap"] * 100 + ["continuous"] * 100)
    easy, hard = [0, 1, 2], [10, 11, 12]
    out = progression.reassign_columns(rng, groups, easy, hard, T=8000)
    assert abs(np.mean(np.isin(out[:1000], hard)) - 0.9) < 0.03
    assert np.all(out[1000:] == -1)
    out0 = progression.reassign_columns(rng, groups, easy, hard, T=1000)
    assert np.all(np.isin(out0[:1000], easy))
    again = progression.reassign_columns(rng, groups, easy, hard, T=8000)
    assert abs(np.mean(np.isin(again[:1000], easy)) - 0.1) < 0.03


def test_free_velocity_promotion_and_demotion_hand_values():
    # 명령 합 (0.8, 0) -> 0.5 x 0.8 x 4 x 0.9 = 1.44 m, 이동 1.0 -> 강등, 4.5 m -> 승급
    out = rules.judge_free([1.0, 4.5, 2.0], [[0.8, 0.0]] * 3)
    assert out.tolist() == [-1, 1, 0]


def test_free_velocity_boundaries():
    # 1.44 m 는 부동소수 경계(0.5 x 0.8 x 4 x 0.9 = 1.4400000000000002)라 양쪽으로 비켜서 잰다
    out = rules.judge_free([4.0, 4.0001, 1.45, 1.43], [[0.8, 0.0]] * 4)
    assert out.tolist() == [0, 1, 0, -1]


def test_episodes_without_any_move_command_are_excluded():
    out = rules.judge_free([0.0, 9.0], [[0.0, 0.0], [0.0, 0.0]])
    assert out.tolist() == [0, 0]


def test_flag_rule():
    out = rules.judge_flag([4, 1, 2, 0, 3], [4, 4, 4, 4, 4])
    assert out.tolist() == [1, -1, 0, -1, 0]


def test_combined_judge_uses_flag_rule_for_flag_envs():
    out = rules.judge([True, False], [0.0, 4.5], [[0, 0], [0.8, 0]], [4, 0], [4, 4])
    assert out.tolist() == [1, 1]
