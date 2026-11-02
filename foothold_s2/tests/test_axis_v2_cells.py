"""Known-input CPU checks for W57 axis v2 measurements."""

import math

import numpy as np
import pytest

from foothold_s2.eval import axis_v2_cells as A


def test_yaw_accumulation_unwraps_and_ignores_post_reset_jump():
    d = math.pi / 180
    yaw = np.array([[179, 20], [-179, 30], [90, 140]], float) * d
    alive = np.array([[1, 1], [1, 0], [0, 0]], bool)
    out = A.yaw_accumulation(np.array([178, 10]) * d, yaw, alive)
    assert out["signed_rad"][0] / d == pytest.approx(3)
    assert out["absolute_rad"][0] / d == pytest.approx(3)
    assert out["final_minus_start_wrapped_rad"][0] / d == pytest.approx(3)
    assert out["signed_rad"][1] / d == pytest.approx(10)
    with pytest.raises(ValueError, match="alive"):
        A.yaw_accumulation(np.array([0]), np.zeros((3, 1)), np.array([[1], [0], [1]]))


def test_contact_symmetry_is_four_foot_occupancy_not_reset_contact():
    c = np.array([[[1, 0, 1, 0]], [[0, 1, 0, 1]], [[1, 0, 1, 0]]], bool)
    out = A.contact_symmetry(c, np.array([[1], [1], [0]], bool))
    assert out["fraction_by_foot"].tolist() == [[.5, .5, .5, .5]]
    assert out["left_right_gap"].tolist() == [0]
    left = A.contact_symmetry(np.array([[[1, 0, 1, 0]]], bool), np.array([[1]], bool))
    assert left["left_right_gap"].tolist() == [1]
    assert left["diagonal_gap"].tolist() == [0]


def test_goal_stop_error_hold_duration_and_fall_are_separate():
    d = math.pi / 180
    yaw = np.array([[45, 45], [90, 60], [91, 50], [92, 180]], float) * d
    alive = np.array([[1, 1], [1, 1], [1, 0], [1, 0]], bool)
    out = A.goal_stop(np.zeros(2), np.full(2, 90 * d), yaw, alive, 2, .02)
    assert out["stop_end_error_rad"][0] / d == pytest.approx(2)
    assert np.isnan(out["stop_end_error_rad"][1])
    assert out["stop_alive_duration_s"].tolist() == pytest.approx([.04, 0])
    assert out["fall_in_turn"].tolist() == [False, False]
    assert out["fall_in_stop"].tolist() == [False, True]
    assert out["stop_yaw_drift_rad"][0] / d == pytest.approx(2)


def test_goal_stop_stationary_time_requires_low_linear_and_yaw_motion():
    yaw = np.zeros((4, 1))
    alive = np.ones((4, 1), bool)
    vx = np.array([[0], [0], [.2], [0]])
    vy = np.zeros_like(vx)
    wz = np.array([[.5], [.5], [0], [.2]])
    out = A.goal_stop(np.zeros(1), np.zeros(1), yaw, alive, 2, .02, vx=vx, vy=vy, wz=wz)
    assert out["stop_alive_duration_s"][0] == pytest.approx(.04)
    assert out["stop_stationary_duration_s"][0] == 0


def test_case_specs_have_reset_yaw_and_signed_goal_offsets():
    specs = A.case_specs()
    assert len(specs) == 10
    assert {s["goal_delta_deg"] for s in specs if s["kind"] == "goal_turn_stop"} == {
        -90, -60, -30, 0, 30, 60, 90}
    assert {s["kind"] for s in specs} == {"forward", "goal_turn_stop"}
    assert len({s["name"] for s in specs}) == 10
    assert all(s["command"][2] in (-1.0, 1.0) for s in specs if s["kind"] == "goal_turn_stop")


def test_dynamic_goal_stop_requires_complete_fixed_length_window():
    yaw = np.array([[0, 0], [1, .2], [1.02, .3], [1.04, .4]])
    alive = np.array([[1, 1], [1, 1], [1, 1], [1, 1]], bool)
    out = A.goal_stop_dynamic(np.zeros(2), np.array([1.0, 1.0]), yaw, alive,
                              np.array([2, 3]), 2, .02, vx=np.zeros_like(yaw),
                              vy=np.zeros_like(yaw), wz=np.zeros_like(yaw))
    assert out["stop_complete"].tolist() == [True, False]
    assert out["stop_end_error_rad"][0] == pytest.approx(.04)
    assert np.isnan(out["stop_end_error_rad"][1])
    assert out["stop_yaw_drift_rad"][0] == pytest.approx(.04)
    assert out["stop_alive_duration_s"].tolist() == pytest.approx([.04, .02])
    assert out["stop_wz_mean_signed_radps"][0] == pytest.approx(0.0)
    assert out["stop_wz_mean_abs_radps"][0] == pytest.approx(0.0)
    assert out["stop_wz_max_abs_radps"][0] == pytest.approx(0.0)
    assert out["stop_heading_flow_signed_rad"][0] == pytest.approx(.04)
    assert out["stop_heading_flow_absolute_rad"][0] == pytest.approx(.04)


def test_dynamic_stop_records_angular_velocity_and_cumulative_heading_flow():
    yaw = np.array([[0.0], [0.1], [0.2], [0.35]])
    alive = np.ones_like(yaw, dtype=bool)
    wz = np.array([[0.1], [0.2], [-0.3], [0.4]])
    out = A.goal_stop_dynamic(np.zeros(1), np.ones(1), yaw, alive,
                              np.array([1]), 2, .02, vx=np.zeros_like(yaw),
                              vy=np.zeros_like(yaw), wz=wz)
    assert out["stop_wz_mean_signed_radps"][0] == pytest.approx(-.05)
    assert out["stop_wz_mean_abs_radps"][0] == pytest.approx(.25)
    assert out["stop_wz_max_abs_radps"][0] == pytest.approx(.3)
    assert out["stop_heading_flow_signed_rad"][0] == pytest.approx(.2)
    assert out["stop_heading_flow_absolute_rad"][0] == pytest.approx(.2)


def test_reverse_stop_lateral_deviation_uses_stop_entry_heading_and_keeps_incomplete_null():
    xy = np.array([[[0.0, 0.0]], [[1.0, 0.0]], [[1.2, 0.0]], [[1.4, 0.0]]])
    alive = np.array([[1], [1], [1], [1]], bool)
    out = A.reverse_stop_lateral_deviation(
        np.array([[1.0, 0.0]]), np.array([np.pi / 2]), xy, alive,
        np.array([2]), 2)
    assert out["complete"].tolist() == [True]
    assert out["signed_lateral_deviation_m"][0] == pytest.approx(-.4)
    assert out["max_abs_lateral_deviation_m"][0] == pytest.approx(.4)
    incomplete = A.reverse_stop_lateral_deviation(
        np.array([[1.0, 0.0]]), np.array([np.pi / 2]), xy,
        np.array([[1], [1], [1], [0]], bool), np.array([2]), 2)
    assert incomplete["complete"].tolist() == [False]
    assert np.isnan(incomplete["signed_lateral_deviation_m"][0])


def test_early_completed_stop_is_alive_at_its_window_end_not_last_global_step():
    valid = np.array([[1, 1], [1, 1], [1, 0], [0, 0], [0, 0]], bool)
    assert A.alive_at_window_end(valid, np.array([True, False])).tolist() == [True, False]
    assert A.alive_at_window_end(valid).tolist() == [False, False]
