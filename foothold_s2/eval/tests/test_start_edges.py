"""N1e: 발 구 가장자리에서 5 cm 여유의 경계와 기록."""
import numpy as np
import pytest

from foothold_s2.eval import sparse_starts as ss

FEET = np.array([[-.3, -.2, -.3], [-.3, .2, -.3], [.3, -.2, -.3], [.3, .2, -.3]])


@pytest.mark.parametrize('half,ready', [(.0719, False), (.072, True), (.0721, True)])
def test_five_cm_boundary_and_per_foot_records(half, ready):
    boxes = [[4+x-half, 4+x+half, 4+y-half, 4+y+half, -1., 0.] for x, y, _ in FEET]
    result = ss.select_start(boxes, (-.3, 0., 0.), feet=FEET)
    assert (result['status'] == 'ready') is ready
    assert result['foot_edge_margin_m'] == .05
    assert result['foot_order'] == ['FL', 'FR', 'RL', 'RR']
    if not ready:
        assert result['origin'] is None and result['previous_origin'] is not None
        assert result['reason'] == 'no_four_foot_support'
        return
    assert result['foot_center_edge_distances_m'] == pytest.approx([half]*4)
    assert result['foot_edge_clearances_m'] == pytest.approx([half-.022]*4)
    assert min(result['sole_air_gaps_m']) == pytest.approx(.01)
    assert result['xy_only_candidate']['foot_edge_clearances_m'] == pytest.approx([half-.022]*4)


def test_edge_distances_preserve_each_foot_order():
    half = [.08, .09, .10, .11]
    boxes = [[4+x-h, 4+x+h, 4+y-h, 4+y+h, -1., 0.] for (x, y, _), h in zip(FEET, half)]
    result = ss.select_start(boxes, (0., .2, 0.), feet=FEET)
    assert result['yaw_rad'] == 0.
    assert result['foot_center_edge_distances_m'] == pytest.approx(half)
    assert result['foot_edge_clearances_m'] == pytest.approx(np.array(half)-.022)


def test_edge_distance_uses_merged_surface_not_triangle_seam():
    boxes = [[x, x+.1, y, y+.1, -1., 0.]
             for x in np.arange(3., 5., .1) for y in np.arange(3., 5., .1)]
    result = ss.select_start(boxes, (0., .2, 0.), feet=FEET)
    assert result['foot_center_edge_distances_m'] == pytest.approx([.7]*4)
    assert result['foot_edge_clearances_m'] == pytest.approx([.678]*4)


def test_gaps_previous_two_cm_pose_is_rejected_and_new_pose_moves_inward():
    from foothold_s2.terrains.sparse_terrains import build_tile
    boxes = build_tile('gaps', .5).boxes[3:]
    old = [3.568602674194979, 4., 0.]
    assert not ss.valid_start(old, boxes, (-.3, 0., 0.), yaw=np.pi/2)
    result = ss.select_start(boxes, (-.3, 0., 0.))
    assert result['status'] == 'ready'
    assert result['yaw_rad'] == pytest.approx(np.pi/2)
    assert result['origin'][0] == pytest.approx(old[0]-.03)
    assert min(result['foot_edge_clearances_m']) == pytest.approx(.05)
