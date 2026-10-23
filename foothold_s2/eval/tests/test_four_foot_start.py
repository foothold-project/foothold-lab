"""N1c CPU 계약: FK 네 발 지지, 연속 위치 탐색, yaw, 리셋 일치."""
import numpy as np
import pytest

from foothold_s2.eval import sparse_starts as ss
from foothold_s2.robots import go2_kinematics as fk


def grid(width=.2, gap=.25):
    return np.array([[x, x+width, y, y+width, -1., 0.]
                     for x in np.arange(1., 7.-width, width+gap)
                     for y in np.arange(2., 6.-width, width+gap)])


def test_fk_zero_angles_known_lengths_and_collision_offset():
    feet = fk.foot_centers(np.zeros((4, 3)))
    assert feet == pytest.approx(np.array([[.1914, .142, -.426], [.1914, -.142, -.426],
                                 [-.1954, .142, -.426], [-.1954, -.142, -.426]]))


def test_regular_grid_finds_feasible_four_foot_pose():
    # A square stance fits four different 0.2 m stones, even though root is over a hole.
    feet = np.array([[-.225, -.225, -.3], [-.225, .225, -.3],
                     [.225, -.225, -.3], [.225, .225, -.3]])
    result = ss.select_start(grid(), (-.3, 0., 0.), feet=feet)
    assert result['status'] == 'ready'
    assert ss.valid_start(result['origin'], grid(), (-.3, 0., 0.),
                          feet=feet, yaw=result['yaw_rad'])
    assert len(result['feet_world']) == 4


def test_regular_grid_proves_impossible_stance():
    # 0.225 spacing cannot share a 0.056 m safe interior or bridge 0.394 m between interiors.
    feet = np.array([[0., 0., -.3], [.225, 0., -.3],
                     [0., .225, -.3], [.225, .225, -.3]])
    result = ss.select_start(grid(), (0., .2, 0.), feet=feet)
    assert result['status'] == 'no_start'
    assert result['origin'] is None and result['previous_origin'] is not None
    assert result['reason'] == 'no_four_foot_support'


def test_go2_default_pose_on_point_two_stones_point_two_five_gaps(monkeypatch):
    result = ss.select_start(grid(), (-.3, 0., 0.))
    assert result['status'] == 'no_start' and result['previous_origin'] is not None
    # Independent necessary condition: no sampled yaw fits all pair displacements
    # into the periodic safe squares (width .056, pitch .45), even on an infinite grid.
    for angle in range(0, 360, 15):
        xy = ss.rotate_xy(fk.foot_centers()[:, :2], np.deg2rad(angle))
        delta = xy[:, None, :] - xy[None, :, :]
        residual = np.abs(delta - .45*np.round(delta/.45))
        assert np.any(residual > .056 + 1e-8)
    # The old 2 cm rule did admit this geometry. Preserve that contrast explicitly.
    monkeypatch.setattr(ss, 'FOOT_EDGE_MARGIN_M', .02)
    assert ss.select_start(grid(), (-.3, 0., 0.))['status'] == 'ready'


def test_yaw_search_and_continuous_translation():
    feet = fk.foot_centers()
    yaw = np.deg2rad(15.)
    xy = np.array([4.023456, 4.012345])
    rotated = ss.rotate_xy(feet[:, :2], yaw) + xy
    # Only 2 micrometres of safe interior: a coarse translation grid cannot find it.
    half = fk.FOOT_RADIUS_M + ss.FOOT_EDGE_MARGIN_M + 1e-6
    boxes = [[x-half, x+half, y-half, y+half, -1., .02] for x, y in rotated]
    result = ss.select_start(boxes, (0., .2, 0.))
    assert result['status'] == 'ready'
    assert result['yaw_rad'] == pytest.approx(yaw)
    assert result['origin'][:2] == pytest.approx(xy, abs=2e-6)


def test_mesh_seams_are_not_edges_but_holes_are():
    boxes = [[x, x+.1, y, y+.1, 0., .1]
             for x in np.arange(3., 5., .1) for y in np.arange(3., 5., .1)]
    merged = ss.merge_support_boxes(boxes)
    assert len(merged) == 1
    assert ss.valid_start([4., 4., .1], merged, (0., .2, 0.))
    holed = [b for b in boxes if not (3.8 < b[0] < 4.11 and 3.8 < b[2] < 4.11)]
    assert sum((b[1]-b[0])*(b[3]-b[2]) for b in ss.merge_support_boxes(holed)) == pytest.approx(
        sum((b[1]-b[0])*(b[3]-b[2]) for b in holed))


def test_root_projection_alone_is_not_support():
    assert not ss.valid_start([4., 4., 0.], [[3.9, 4.1, 3.9, 4.1, -1., 0.]], (-.3, 0., 0.))


def test_height_is_recorded_and_previous_height_preserved():
    feet = fk.foot_centers()
    boxes = [[4+x-.09, 4+x+.09, 4+y-.09, 4+y+.09, -1., z]
             for (x, y, _), z in zip(feet, [0., .01, .02, .03])]
    result = ss.select_start(boxes, (0., .2, 0.))
    assert result['status'] == 'ready'
    assert result['origin'][2] == result['previous_origin'][2]
    assert result['support_height_spread_m'] == pytest.approx(.03)
    assert result['foot_air_gaps_m'] == pytest.approx(
        np.array(result['feet_world'])[:, 2] - np.array(result['support_heights_m']))


def test_changed_default_joints_stop_instead_of_using_old_fk():
    fk.validate_default_pose(fk.JOINT_NAMES, np.array(fk.DEFAULT_JOINT_POS).reshape(12))
    with pytest.raises(ValueError, match='default_joint_pos'):
        fk.validate_default_pose(fk.JOINT_NAMES, np.array(fk.DEFAULT_JOINT_POS).reshape(12)*1.05)


def test_actual_cfg_height_is_read_but_spawn_height_is_support_based():
    from types import SimpleNamespace as NS
    cfg = NS(init_state=NS(pos=(0., 0., .42), rot=(1., 0., 0., 0.), joint_pos={
        '.*L_hip_joint': .1, '.*R_hip_joint': -.1, 'F.*_thigh_joint': .8,
        'R.*_thigh_joint': 1., '.*_calf_joint': -1.5}))
    height = fk.root_height_from_cfg(cfg)
    a = ss.select_start([[2., 6., 2., 6., -1., 0.]], (-.3, 0., 0.))
    b = ss.select_start([[2., 6., 2., 6., -1., 0.]], (-.3, 0., 0.), root_height_m=height)
    assert height == .42
    assert np.array(b['foot_air_gaps_m']) == pytest.approx(a['foot_air_gaps_m'])
    assert b['root_z_offset_m'] - a['root_z_offset_m'] == pytest.approx(-.02)


@pytest.mark.parametrize('path', [
    'C:/Users/AI-WS01/s2_lab/_research_repos/MGDP/legged_gym/resources/robots/all_dog/go2/urdf/go2.urdf',
    'C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf'])
def test_fk_matches_installed_urdf_chain(path):
    """독립적인 동차행렬 FK로 세 관절과 충돌 중심까지 대조한다."""
    from pathlib import Path
    import xml.etree.ElementTree as ET
    from scipy.spatial.transform import Rotation
    if not Path(path).exists():
        pytest.skip('로컬 Go2 URDF 없음')
    root = ET.parse(path).getroot()
    joints = {j.get('name'): j for j in root.findall('joint')}
    for q in (np.zeros((4, 3)), np.array(fk.DEFAULT_JOINT_POS),
              np.array([[.2, .5, -1.8], [-.3, .9, -1.3], [.4, 1.1, -2.], [-.1, .7, -1.6]])):
        expected = []
        for i, leg in enumerate(fk.LEGS):
            transform = np.eye(4)
            for part, angle in zip(('hip', 'thigh', 'calf', 'foot'), [*q[i], 0.]):
                joint = joints[f'{leg}_{part}_joint']
                origin = joint.find('origin')
                xyz = np.fromstring(origin.get('xyz'), sep=' ')
                rpy = np.fromstring(origin.get('rpy', '0 0 0'), sep=' ')
                local = np.eye(4)
                local[:3, 3] = xyz
                local[:3, :3] = Rotation.from_euler('xyz', rpy).as_matrix()
                if angle:
                    axis = np.fromstring(joint.find('axis').get('xyz'), sep=' ')
                    local[:3, :3] = local[:3, :3] @ Rotation.from_rotvec(axis*angle).as_matrix()
                transform = transform @ local
            collision = root.find(f"link[@name='{leg}_foot']/collision")
            offset = np.fromstring(collision.find('origin').get('xyz'), sep=' ')
            assert float(collision.find('geometry/sphere').get('radius')) == fk.FOOT_RADIUS_M
            expected.append((transform @ np.r_[offset, 1.])[:3])
        assert fk.foot_centers(q) == pytest.approx(np.array(expected), abs=1e-10)
