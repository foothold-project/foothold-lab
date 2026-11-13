"""Target-facing start yaw and JEPLO initial foot-overlap contracts."""
import math

import numpy as np
import pytest
import torch

from foothold_s2.robots.go2_kinematics import (
    DEFAULT_ROOT_HEIGHT_M,
    FOOT_RADIUS_M,
    foot_centers,
)
from foothold_s2.terrains import ex42_column_reset as reset
from foothold_s2.terrains import jeplo_preset as jeplo
from foothold_s2.terrains import jump_preset


TARGET_KINDS = {
    "B": {"climb_up", "climb_down", "gap"},
    "C": {"flat", "discrete_grid", "pyramid_stairs", "inverted_pyramid_stairs"},
    "D": {"high_ledge", "wall", "crawl"},
    "E": {"slope_steep", "slope_steep_inv", "stairs_high", "stairs_high_inv"},
    "F": set(jump_preset.KINDS),
}


def test_targeted_families_declare_only_forward_heading_for_target_kinds():
    column_families = [family for family in "BCDEF" for _ in range({"B": 12, "C": 7, "D": 3, "E": 4, "F": 4}[family])]
    rows = reset.build_column_table(column_families)
    for row in rows:
        if row["kind"] in TARGET_KINDS[row["family"]]:
            assert row["ranges"]["yaw"] == (0.0, 0.0), (row["family"], row["kind"])


def test_real_reset_consumer_emits_target_yaw_zero_for_every_selected_kind():
    families = [family for family in "BCDEF" for _ in range({"B": 12, "C": 7, "D": 3, "E": 4, "F": 4}[family])]
    table = reset.build_column_table(families)
    lo, hi = reset.table_tensors(table)

    class Asset:
        device = "cpu"

        def __init__(self, n):
            state = torch.zeros(n, 13)
            state[:, 2] = DEFAULT_ROOT_HEIGHT_M
            state[:, 3] = 1.0
            self.data = type("Data", (), {"default_root_state": state})

        def write_root_pose_to_sim(self, pose, env_ids):
            self.pose = pose

        def write_root_velocity_to_sim(self, velocity, env_ids):
            pass

    asset = Asset(len(table))

    class Scene:
        terrain = type("Terrain", (), {"terrain_types": torch.arange(len(table))})
        env_origins = torch.zeros(len(table), 3)

        def __getitem__(self, name):
            assert name == "robot"
            return asset

    reset.reset_root_state_by_column(type("Env", (), {"scene": Scene()})(),
                                     torch.arange(len(table)), lo, hi, {})
    quaternion = asset.pose[:, 3:7]
    yaw = 2 * torch.atan2(quaternion[:, 3], quaternion[:, 0])
    for index, row in enumerate(table):
        if row["kind"] in TARGET_KINDS[row["family"]]:
            error = math.atan2(math.sin(float(yaw[index])), math.cos(float(yaw[index])))
            assert abs(error) < 1e-7, (row["family"], row["kind"], error)


def _ray_heights(vertices, faces, points):
    triangles = np.asarray(vertices, dtype=np.float64)[faces]
    a = triangles[:, 0]
    u = triangles[:, 1, :2] - a[:, :2]
    v = triangles[:, 2, :2] - a[:, :2]
    det = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
    valid = np.abs(det) > 1e-12
    a, u, v, det, triangles = a[valid], u[valid], v[valid], det[valid], triangles[valid]
    lower = triangles[:, :, :2].min(axis=1)
    upper = triangles[:, :, :2].max(axis=1)
    heights = []
    for point in np.asarray(points, dtype=np.float64):
        near = np.all((lower <= point + 1e-8) & (upper >= point - 1e-8), axis=1)
        aa, uu, vv, dd, tt = a[near], u[near], v[near], det[near], triangles[near]
        q = point - aa[:, :2]
        s = (q[:, 0] * vv[:, 1] - q[:, 1] * vv[:, 0]) / dd
        t = (uu[:, 0] * q[:, 1] - uu[:, 1] * q[:, 0]) / dd
        hit = (s >= -1e-7) & (t >= -1e-7) & (s + t <= 1 + 1e-7)
        assert hit.any(), f"terrain has no triangle under {point}"
        z = aa[:, 2] + s * (tt[:, 1, 2] - aa[:, 2]) + t * (tt[:, 2, 2] - aa[:, 2])
        heights.append(z[hit].max())
    return np.asarray(heights)


@pytest.mark.parametrize("kind", ["discrete_grid", "discrete_obstacles"])
@pytest.mark.parametrize("level", range(10))
@pytest.mark.parametrize("seed", [0, 42, 2026])
def test_jep_lo_target_start_has_no_default_go2_foot_sphere_overlap(kind, level, seed):
    tile = jeplo.build_heightfield(kind, level, seed)
    vertices, faces = jeplo.mesh_arrays(tile)
    origin = jeplo.spawn_origin(tile, vertices=vertices, faces=faces)
    ranges = jeplo.reset_ranges_by_column({0: kind})[0]
    assert ranges == {"x": (0.0, 0.0), "y": (0.0, 0.0), "yaw": (0.0, 0.0)}

    feet = foot_centers()
    world_xy = origin[:2] + feet[:, :2]
    terrain_z = _ray_heights(vertices, faces, world_xy)
    foot_bottom = origin[2] + DEFAULT_ROOT_HEIGHT_M + feet[:, 2] - FOOT_RADIUS_M
    assert np.all(foot_bottom >= terrain_z - 1e-7), {
        "kind": kind,
        "level": level,
        "seed": seed,
        "origin": origin.tolist(),
        "foot_clearance_m": (foot_bottom - terrain_z).tolist(),
    }


def test_old_discrete_obstacle_l9_anchor_is_known_to_overlap():
    tile = jeplo.build_heightfield("discrete_obstacles", 9, 2026)
    vertices, faces = jeplo.mesh_arrays(tile)
    old_xy = np.array([0.96, 4.48])
    old_z = _ray_heights(vertices, faces, [old_xy])[0]
    origin = np.r_[old_xy, old_z]
    terrain_z = _ray_heights(vertices, faces, origin[:2] + foot_centers()[:, :2])
    foot_bottom = origin[2] + DEFAULT_ROOT_HEIGHT_M + foot_centers()[:, 2] - FOOT_RADIUS_M
    assert float(np.min(foot_bottom - terrain_z)) < 0.0


def test_triangle_distance_and_foot_collision_guard_answer_known_inputs():
    from foothold_s2.terrains.jeplo_preset import _default_go2_feet_clear, _point_triangle_distance

    triangle = np.array([[[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]])
    np.testing.assert_allclose(
        _point_triangle_distance(np.array([.2, .2, .1]), triangle), [.1], atol=1e-12)
    np.testing.assert_allclose(
        _point_triangle_distance(np.array([1.2, 0., 0.]), triangle), [.2], atol=1e-12)

    ground = np.array([
        [[-2., -2., 0.], [2., -2., 0.], [2., 2., 0.]],
        [[-2., -2., 0.], [2., 2., 0.], [-2., 2., 0.]],
    ])
    bump = ground.copy()
    bump[:, :, 2] = .20
    assert _default_go2_feet_clear(ground, np.zeros(2), 0.0)
    assert not _default_go2_feet_clear(bump, np.zeros(2), 0.0)


def test_foot_sphere_overlap_guard_rejects_half_radius_threshold_mutant():
    """A triangle 0.75 radii from a foot overlaps the full sphere, not half."""
    from foothold_s2.terrains.jeplo_preset import (
        _default_go2_feet_clear,
        _point_triangle_distance,
    )

    ground = np.array([
        [[-2., -2., 0.], [2., -2., 0.], [2., 2., 0.]],
        [[-2., -2., 0.], [2., 2., 0.], [-2., 2., 0.]],
    ])
    center = np.r_[foot_centers()[0, :2],
                   DEFAULT_ROOT_HEIGHT_M + foot_centers()[0, 2]]
    # A vertical obstacle whose closest point is 0.75 * radius from the first
    # foot center. It intersects that foot's collision sphere, but lies outside
    # a shrunken 0.5 * radius guard.
    x = center[0] + 0.75 * FOOT_RADIUS_M
    obstacle = np.array([[
        [x, center[1] - .1, center[2] - .1],
        [x, center[1] + .1, center[2] - .1],
        [x, center[1], center[2] + .1],
    ]])
    distance = float(_point_triangle_distance(center, obstacle)[0])
    assert distance == pytest.approx(.75 * FOOT_RADIUS_M)
    assert FOOT_RADIUS_M / 2 < distance < FOOT_RADIUS_M
    assert _default_go2_feet_clear(ground, np.zeros(2), 0.0)
    assert not _default_go2_feet_clear(
        np.concatenate((ground, obstacle)), np.zeros(2), 0.0)
