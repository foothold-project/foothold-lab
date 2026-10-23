"""보상 L0 (16 §8): 식의 기대값 · negative control."""

import math

import pytest
import torch

from foothold_s2.rewards import core as rc


def T(x):
    return torch.tensor(x, dtype=torch.float32)


def test_exact_tracking_is_one_at_zero_error_and_exp_minus_one_at_half_meter():
    assert float(rc.track_lin_exact(T([[0.4, 0.2]]), T([[0.4, 0.2]]))[0]) == pytest.approx(1.0, abs=1e-6)
    assert float(rc.track_lin_exact(T([[0.5, 0.0]]), T([[0.0, 0.0]]))[0]) == pytest.approx(math.exp(-1), abs=1e-6)


def test_exact_vs_min_form_for_negative_commands():
    cmd, v = T([[-0.5, 0.0]]), T([[-0.2, 0.0]])
    assert float(rc.track_lin_min_form(v, cmd)[0]) == pytest.approx(1.0, abs=1e-6)       # A: 느린 후진은 무벌
    assert float(rc.track_lin_exact(v, cmd)[0]) == pytest.approx(math.exp(-0.36), abs=1e-6)  # B: 0.698
    assert float(rc.track_lin_exact(v, cmd)[0]) == pytest.approx(0.698, abs=1e-3)
    # 더 빠른 후진(-0.8): A 는 벌, B 는 같은 오차 0.3 이라 같은 값
    v2 = T([[-0.8, 0.0]])
    assert float(rc.track_lin_exact(v2, cmd)[0]) == pytest.approx(math.exp(-0.36), abs=1e-6)


def test_exact_tracking_is_symmetric_in_sign():
    a = rc.track_lin_exact(T([[0.3, -0.1]]), T([[0.5, 0.2]]))
    b = rc.track_lin_exact(T([[-0.3, 0.1]]), T([[-0.5, -0.2]]))
    assert float(a[0]) == pytest.approx(float(b[0]), abs=1e-6)


def test_angular_tracking():
    assert float(rc.track_ang_exp(T([0.5]), T([0.5]))[0]) == pytest.approx(1.0)
    assert float(rc.track_ang_exp(T([1.5]), T([1.0]))[0]) == pytest.approx(math.exp(-1.0), abs=1e-6)


def test_stumble_hand_values():
    f = T([[[5.0, 0.0, 1.0], [0.0, 0.0, 10.0], [0.0, 0.0, 10.0], [0.0, 0.0, 10.0]],
           [[3.0, 0.0, 1.0], [0.0, 0.0, 10.0], [0.0, 0.0, 10.0], [0.0, 0.0, 10.0]]])
    assert rc.stumble(f).tolist() == [1.0, 0.0]


def test_collision_count_uses_threshold_0_1():
    forces = T([[0.05, 0.2, 5.0, 0.0], [0.0, 0.0, 0.0, 0.0]])
    assert rc.collision_count(forces).tolist() == [2.0, 0.0]


def test_smoothness_and_rate_hand_values():
    a, a1, a2 = T([[1.0, 0.0]]), T([[0.0, 0.0]]), T([[0.0, 0.0]])
    assert float(rc.action_smoothness_l2(a, a1, a2)[0]) == pytest.approx(1.0)
    assert float(rc.action_smoothness_l2(T([[2.0]]), T([[1.0]]), T([[0.0]]))[0]) == pytest.approx(0.0)  # 등속 증가는 0
    assert float(rc.action_rate_l2(a, a1)[0]) == pytest.approx(1.0)


def test_joint_terms():
    tau, qd = T([[2.0, -3.0]]), T([[-1.0, 2.0]])
    assert float(rc.joint_torques_l2(tau)[0]) == pytest.approx(13.0)
    assert float(rc.joint_power(tau, qd)[0]) == pytest.approx(2 * 1 + 3 * 2)
    assert float(rc.joint_deviation_l2(T([[1.0, 2.0]]), T([[0.5, 2.5]]))[0]) == pytest.approx(0.5)
    assert float(rc.joint_acc_l2(T([[3.0, 4.0]]))[0]) == pytest.approx(25.0)


def test_orientation_and_velocity_terms():
    assert float(rc.flat_orientation_l2(T([[0.3, 0.4, 0.866]]))[0]) == pytest.approx(0.25, abs=1e-6)
    assert float(rc.ang_vel_xy_l2(T([[1.0, 2.0]]))[0]) == pytest.approx(5.0)
    assert float(rc.lin_vel_z_l2(T([0.5]))[0]) == pytest.approx(0.25)


def test_foot_edge_hand_values_and_bands():
    inner = torch.zeros(4, 4, dtype=torch.bool)
    outer = torch.zeros(4, 4, dtype=torch.bool)
    inner[1, 1] = True
    outer[2, 2] = True
    feet = T([[[1.5, 1.5], [2.5, 2.5], [0.5, 0.5], [9.0, 9.0]]])    # 안쪽 띠 · 바깥 띠 · 밖 · 격자 밖
    contact = torch.tensor([[True, True, True, True]])
    val = rc.foot_edge_penalty(feet, contact, inner, outer, T([0.0, 0.0]), 1.0)
    assert float(val[0]) == pytest.approx(1.0 + 0.5)
    # 공중(접촉 아님)이면 0
    assert float(rc.foot_edge_penalty(feet, torch.zeros(1, 4, dtype=torch.bool), inner, outer,
                                      T([0.0, 0.0]), 1.0)[0]) == 0.0


def test_weights_are_the_table_values_and_s1_foot_edge_is_zero():
    w = dict(rc.WEIGHTS)
    assert w["track_lin_vel"] == 1.5 and w["track_ang_vel"] == 0.5 and w["collision"] == -10.0
    assert w["joint_torques"] == -1.0e-5 and w["joint_power"] == -2.0e-5 and w["joint_acc"] == -2.5e-7
    assert len(w) == 14
    s1 = {**w, **rc.S1_WEIGHT_OVERRIDES}
    assert s1["foot_edge"] == 0.0 and all(s1[k] == w[k] for k in w if k != "foot_edge")


def test_foot_edge_tiles_hand_values_and_cell_selection():
    h = w = 8
    inner = torch.zeros(2, 3, h, w, dtype=torch.bool)
    outer = torch.zeros_like(inner)
    inner[1, 2, 1, 1] = True            # 칸 (줄 1, 열 2) 의 안쪽 띠 한 칸
    outer[1, 2, 2, 2] = True
    inner[0, 0, 1, 1] = True            # 다른 칸의 같은 자리 (섞여 들어오면 안 됨)
    res = 0.1
    corner = torch.tensor([8.0, 16.0])  # 줄 1, 열 2 의 월드 모서리
    feet = (corner + torch.tensor([[0.15, 0.15], [0.25, 0.25], [0.45, 0.45], [-1.0, -1.0]]))[None]   # 안 · 바깥 · 밖 · 칸 밖
    contact = torch.tensor([[True, True, True, True]])
    val = rc.foot_edge_penalty_tiles(feet, contact, inner, outer, torch.tensor([1]), torch.tensor([2]),
                                     size=(8.0, 8.0), resolution=res)
    assert float(val[0]) == pytest.approx(1.0 + 0.5)
    other = rc.foot_edge_penalty_tiles(feet - corner + torch.tensor([0.0, 0.0]), contact, inner, outer,
                                       torch.tensor([0]), torch.tensor([0]), size=(8.0, 8.0), resolution=res)
    assert float(other[0]) == pytest.approx(1.0)               # (0,0) 칸은 안쪽 띠 하나만
    air = rc.foot_edge_penalty_tiles(feet, ~contact, inner, outer, torch.tensor([1]), torch.tensor([2]),
                                     size=(8.0, 8.0), resolution=res)
    assert float(air[0]) == 0.0
