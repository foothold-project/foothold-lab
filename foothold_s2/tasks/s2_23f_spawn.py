"""TopDown 출발 발판 위 네 발을 보장하는 reset 후 root 보정.

관절은 Isaac Lab의 reset_joints_by_scale이 먼저 표집·기록한 값을 그대로 쓴다.
Root의 기존 yaw와 출발 발판 안 조건을 유지하면서 XY만 지지 가능한 구간으로 옮긴다.
"""

from __future__ import annotations

import numpy as np
import torch

from foothold_s2.robots import go2_kinematics as fk
from foothold_s2.eval import start_sheet


EDGE_MARGIN_M = fk.FOOT_RADIUS_M + 0.01
DEPARTURE = (0.0, start_sheet.ZONE_X[0], 0.0, start_sheet.SIZE[1])


def supported_departure_xy(joints: np.ndarray, proposed_xy: np.ndarray, yaw: float) -> np.ndarray:
    """Same sampled joints/yaw; clamp root XY into the four-foot support intersection."""
    feet = fk.foot_centers(joints)[:, :2]
    c, s = np.cos(yaw), np.sin(yaw)
    rotated = feet @ np.array([[c, s], [-s, c]])
    x0, x1, y0, y1 = DEPARTURE
    low = np.array([x0 + EDGE_MARGIN_M, y0 + EDGE_MARGIN_M]) - rotated.min(axis=0)
    high = np.array([x1 - EDGE_MARGIN_M, y1 - EDGE_MARGIN_M]) - rotated.max(axis=0)
    # The inherited x/y reset proposal is ±0.5 around the tile origin (0.5, 2).
    low = np.maximum(low, [0.0, 1.5])
    high = np.minimum(high, [1.0, 2.5])
    if np.any(low > high):
        raise ValueError("TopDown sampled joints/yaw have no four-foot departure support")
    xy = np.clip(np.asarray(proposed_xy, dtype=float), low, high)
    points = rotated + xy
    if not np.all((points >= np.array([x0, y0]) + EDGE_MARGIN_M - 1e-7)
                  & (points <= np.array([x1, y1]) - EDGE_MARGIN_M + 1e-7)):
        raise AssertionError("TopDown four-foot departure support check failed")
    return xy


def correct_topdown_spawn(env, env_ids) -> None:
    """Reset event ordered after reset_robot_joints, before any physics step."""
    if len(env_ids) == 0:
        return
    robot = env.scene["robot"]
    joints = [robot.joint_names.index(name) for name in fk.JOINT_NAMES]
    fk.validate_default_pose(robot.joint_names,
                             robot.data.default_joint_pos[env_ids][0].detach().cpu().numpy())
    q = robot.data.joint_pos[env_ids][:, joints].detach().cpu().numpy().reshape(-1, 4, 3)
    pose = robot.data.root_link_pose_w[env_ids].clone()
    origin = env.scene.terrain.env_origins[env_ids, :2]
    local = (pose[:, :2] - origin).detach().cpu().numpy() + np.array(start_sheet.SPAWN_XY)
    quat = pose[:, 3:7]
    yaw = torch.atan2(2 * (quat[:, 0] * quat[:, 3] + quat[:, 1] * quat[:, 2]),
                      1 - 2 * (quat[:, 2].square() + quat[:, 3].square())).detach().cpu().numpy()
    corrected = np.stack([supported_departure_xy(q[i], local[i], float(yaw[i])) for i in range(len(q))])
    pose[:, :2] = origin + torch.as_tensor(corrected - np.array(start_sheet.SPAWN_XY),
                                          device=pose.device, dtype=pose.dtype)
    robot.write_root_pose_to_sim(pose, env_ids=env_ids)
