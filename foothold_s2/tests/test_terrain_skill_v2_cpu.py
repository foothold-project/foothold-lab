"""Known-input W78 v2 contract checks, without Kit or GPU."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.eval import terrain_skill_v2_run as v2


def request(tmp_path, **kwargs):
    ckpt = tmp_path / "model.pt"
    ckpt.write_bytes(b"known-input")
    cfg = dict(axis_v2=False, terrain_skill=False, fixed_terrain=True, fixed_level=None,
               terrain_set="default", envs=2, eval_seed=42, terrain_levels="2,5",
               stair_start_angles_deg="0,30,60,90", modes="eval_gt,eval_pred,probe_prop_only",
               checkpoint=str(ckpt), out=str(tmp_path / "fresh"))
    cfg.update(kwargs)
    return SimpleNamespace(**cfg)


@pytest.mark.parametrize("field,value", [
    ("terrain_levels", "2"), ("terrain_levels", "2,2"),
    ("stair_start_angles_deg", "0,30,60"), ("stair_start_angles_deg", "0,30,60,60"),
    ("modes", "eval_gt"), ("modes", "eval_gt,eval_gt,eval_pred"),
    ("fixed_level", 2), ("terrain_set", "sparse50")])
def test_request_rejects_incomplete_grid_before_kit(tmp_path, field, value):
    cfg = request(tmp_path, **{field: value})
    with pytest.raises(ValueError):
        v2.validate_request(cfg)


def test_request_accepts_exact_grid_and_rejects_nonempty_output(tmp_path):
    cfg = request(tmp_path)
    v2.validate_request(cfg)
    output = Path(cfg.out)
    output.mkdir()
    (output / "stale.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh empty"):
        v2.validate_request(cfg)


def test_exact_result_grid_requires_every_level_angle_mode_and_case():
    full = v2.expected_combinations()
    assert len(full) == 2 * 4 * 3 * len(v2.V2_CASES)
    v2.require_complete(full)
    one = next(iter(full))
    with pytest.raises(RuntimeError, match="incomplete combinations"):
        v2.require_complete(full - {one})
    with pytest.raises(RuntimeError, match="extra=1"):
        v2.require_complete(full | {(9, 0, "eval_gt", "stairs_fwd")})


class FakeRobot:
    def __init__(self, n=3):
        state = torch.zeros(n, 13)
        state[:, 3] = 1.0
        state[:, :3] = torch.arange(n * 3, dtype=torch.float32).reshape(n, 3)
        state[:, 7:] = 2.0
        self.data = SimpleNamespace(root_state_w=state, root_quat_w=state[:, 3:7].clone())

    def write_root_pose_to_sim(self, pose):
        self.data.root_state_w[:, :7] = pose
        self.data.root_quat_w = pose[:, 3:7].clone()

    def write_root_velocity_to_sim(self, velocity):
        self.data.root_state_w[:, 7:] = velocity


@pytest.mark.parametrize("degrees", [0, 30, 60, 90])
def test_start_yaw_is_world_angle_with_position_unchanged(degrees):
    robot = FakeRobot()
    before = robot.data.root_state_w[:, :3].clone()
    assert v2.set_start_yaw(robot, degrees) < 1e-6
    actual = torch.atan2(2 * robot.data.root_quat_w[:, 0] * robot.data.root_quat_w[:, 3],
                         1 - 2 * robot.data.root_quat_w[:, 3].square())
    assert torch.allclose(actual, torch.full_like(actual, np.deg2rad(degrees)), atol=1e-6)
    assert torch.equal(robot.data.root_state_w[:, :3], before)
    assert torch.count_nonzero(robot.data.root_state_w[:, 7:]) == 0


def test_movement_ratio_keeps_terminated_scheduled_time_in_denominator():
    data = {"body_vel_b": np.zeros((4, 1, 3)), "alive": np.array([[True], [True], [False], [False]])}
    data["body_vel_b"][:, 0, 0] = 1.0
    phase = [((1.0, 0.0, 0.0), 4.0)]
    row = v2.movement_ratio_for_env(data, phase, [4], 0, 1.0)[0]
    assert row == {"movement_ratio": 0.5, "distance_projected_m": 2.0,
                   "planned_distance_m": 4.0, "alive_samples": 2, "scheduled_samples": 4}
    assert v2.movement_ratio_for_env(data, [((0.0, 0.0, 0.0), 4.0)], [4], 0, 1.0)[0]["movement_ratio"] is None


def test_contact_swing_drag_and_open_swing_known_values():
    contact = np.array([[True], [False], [False], [True], [False]], dtype=bool)
    data = {"alive": np.ones((5, 1), dtype=bool),
            "contact": np.repeat(contact[:, :, None], 4, axis=2),
            "foot_pos_w": np.zeros((5, 1, 4, 3)),
            "foot_vel_xy_w": np.zeros((5, 1, 4, 2))}
    data["foot_pos_w"][:, 0, :, 2] = np.array([0.0, 0.1, 0.2, 0.0, 0.1])[:, None]
    data["foot_vel_xy_w"][3, 0, :, 0] = 0.2
    row = v2.swing_and_drag(data, 0)
    assert row["drag_num"] == 4 and row["drag_den"] == 8
    assert row["drag_ratio_of_contact"] == 0.5
    assert row["closed_swing_count"] == 4 and row["open_swing_count"] == 4
    assert row["swing_clearance_m"] == pytest.approx([0.2] * 4)


def test_stop_yaw_and_post_stop_back_lateral_known_input():
    steps = [1, 2, 2, 1]
    # Forward, two stopped samples rotate 0.1 rad, then backward drifts +y.
    yaw = np.array([0.0, 0.05, 0.1, 0.1, 0.1, 0.1])
    quat = np.zeros((6, 1, 4))
    quat[:, 0, 0], quat[:, 0, 3] = np.cos(yaw / 2), np.sin(yaw / 2)
    pos = np.zeros((6, 1, 3))
    pos[4, 0, 1] = 0.3
    data = {"alive": np.ones((6, 1), dtype=bool), "root_quat_w": quat,
            "root_pos_w": pos, "body_wz": np.array([[0], [.05], [.05], [0], [0], [0]]),
            "dt": np.asarray(1.0)}
    row = v2.stop_back_metrics(data, steps, 0)
    assert row["stop_yaw_drift_rad"] == pytest.approx(0.1)
    assert row["stop_abs_wz_integral_rad"] == pytest.approx(0.1)
    assert row["post_stop_back_lateral_m"] == pytest.approx(0.3 * np.cos(0.1))
    data["alive"][2, 0] = False
    assert v2.stop_back_metrics(data, steps, 0)["post_stop_back_lateral_m"] is None
