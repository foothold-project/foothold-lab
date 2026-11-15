"""N1d: 지지면 높이 관문과 root 높이의 답을 아는 CPU 입력."""
import numpy as np
import pytest

from foothold_s2.eval import sparse_starts as ss

FEET = np.array([[-.3, -.2, -.3], [-.3, .2, -.3], [.3, -.2, -.3], [.3, .2, -.3]])


def patches(heights, center=(4., 4.)):
    return [[center[0]+x-.09, center[0]+x+.09, center[1]+y-.09, center[1]+y+.09, -1., h]
            for (x, y, _), h in zip(FEET, heights)]


@pytest.mark.parametrize('spread,ready', [(.02, True), (.03, True), (.0301, False), (.085, False)])
def test_height_spread_gate(spread, ready):
    result = ss.select_start(patches([0., 0., 0., spread]), (0., .2, 0.), feet=FEET)
    assert (result['status'] == 'ready') is ready
    if not ready:
        assert result['origin'] is None and result['eligible'] is False
        assert result['reason'] == 'support_height_spread_exceeded'
        assert result['xy_only_candidate']['support_height_spread_m'] == pytest.approx(spread)


def test_search_continues_past_nearest_bad_height_pose():
    boxes = patches([0., 0., 0., .085]) + patches([.01, .01, .02, .03], center=(5.5, 4.))
    result = ss.select_start(boxes, (0., .2, 0.), feet=FEET)
    assert result['status'] == 'ready'
    assert result['origin'][0] > 5.
    assert result['support_height_spread_m'] <= .03 + 1e-8
    assert result['xy_only_candidate']['origin'][0] == pytest.approx(4.)


def test_root_height_known_input_equal_feet():
    # .02 support - (-.3 foot center) + .022 radius + .01 clearance = .352.
    assert ss.root_height_for_supports([0., .01, .02, .02], FEET[:, 2]) == pytest.approx(.352)
    result = ss.select_start(patches([0., .01, .02, .02]), (0., .2, 0.), feet=FEET)
    assert result['spawn_root_z_m'] == pytest.approx(.352)
    assert result['origin'][2] + result['root_height_m'] + result['root_z_offset_m'] == pytest.approx(.352)
    assert min(result['sole_air_gaps_m']) == pytest.approx(.01)
    assert sorted(result['sole_air_gaps_m']) == pytest.approx([.01, .01, .02, .03])


def test_root_height_unequal_fk_feet_prevents_penetration():
    # The highest support has the shorter leg. A different foot controls root height.
    z = np.array([-.31, -.30, -.30, -.30])
    heights = np.array([0., .005, 0., 0.])
    root_z = ss.root_height_for_supports(heights, z)
    assert root_z == pytest.approx(.342)
    gaps = root_z + z - .022 - heights
    assert min(gaps) == pytest.approx(.01)
    assert gaps[1] == pytest.approx(.015)


def test_reset_offset_compensates_default_root_height_without_moving_terrain_origin():
    boxes = patches([0., .01, .02, .02])
    a = ss.select_start(boxes, (0., .2, 0.), feet=FEET, root_height_m=.4)
    b = ss.select_start(boxes, (0., .2, 0.), feet=FEET, root_height_m=.42)
    assert a['spawn_root_z_m'] == pytest.approx(b['spawn_root_z_m'])
    assert b['origin'][2] == a['origin'][2]
    assert b['root_z_offset_m'] - a['root_z_offset_m'] == pytest.approx(-.02)
    assert np.array(a['feet_world']) == pytest.approx(np.array(b['feet_world']))
