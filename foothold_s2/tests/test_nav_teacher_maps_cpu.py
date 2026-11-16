import numpy as np
import pytest

from foothold_s2.nav import room_generator as rg
from foothold_s2.nav import teacher_maps as tm

BASE_Z = 0.35


def _vox(*prims):
    return tm.RoomVoxels.from_room(rg.build_room({"seed": 0, "size_m": 20.0, "primitives": list(prims)}))


def _box(x, y, w, z0, h):
    return {"type": "box", "x": x, "y": y, "w": w, "z0": z0, "h": h}


def test_shapes_and_flat_floor_is_outside_the_3d_window_and_zero_relative_in_the_2_5d_map():
    v = _vox()
    pose = [[10.0, 10.0, BASE_Z]]
    occ = tm.crop_occupancy(v, pose, [0.0])
    el = tm.crop_elevation(v, pose, [0.0])
    assert occ.shape == (1, 14, 11, 11) and occ.dtype == bool and not occ.any()      # 서 있으면 발 밑 바닥은 창 아래
    assert el.shape == (1, 31, 21) and np.allclose(el, -BASE_Z, atol=1e-6)            # 바닥 윗면 0 - 몸 높이


def test_box_volume_is_counted_in_cells_of_a_tenth_of_a_metre():
    v = _vox(_box(9.3, 10.0, 0.4, 0.2, 0.3))                # 0.4 x 0.4 x 0.3 m = 48 셀. 몸 (9.05, 10.25) 앞 0.3~0.7 m
    occ = tm.crop_occupancy(v, [[9.05, 10.25, BASE_Z]], [0.0])
    want = 0.4 * 0.4 * 0.3 / 0.001
    assert abs(int(occ.sum()) - want) <= 0.1 * want


@pytest.mark.parametrize("yaw", [0.0, np.pi / 2, np.pi, -np.pi / 2])
def test_the_window_turns_with_the_body(yaw):
    """같은 상자를 몸 앞 0.5 m 에 두면 어느 방향을 보든 같은 셀 수 · 같은 몸 틀 위치."""
    c, s = round(float(np.cos(yaw))), round(float(np.sin(yaw)))
    cx, cy = 10.05, 10.05
    bx, by = cx + 0.5 * c, cy + 0.5 * s                      # 몸 앞 0.5 m 중심
    v = _vox(_box(round(bx - 0.25, 2), round(by - 0.25, 2), 0.5, 0.2, 0.3))     # 0.5 x 0.5 x 0.3 = 75 셀
    occ = tm.crop_occupancy(v, [[cx, cy, BASE_Z]], [yaw])[0]
    assert int(occ.sum()) == 75
    xs = np.nonzero(occ.any(axis=(1, 2)))[0]
    assert xs.min() == 3 + 3 and xs.max() == 3 + 7           # 몸 앞 0.3~0.7 m = x 셀 번호 6~10 (몸 셀 3)
    ys = np.nonzero(occ.any(axis=(0, 2)))[0]
    assert ys.min() == 3 and ys.max() == 7                   # 좌우 가운데 (몸 셀 5)


@pytest.mark.parametrize("yaw", [0.0, np.pi / 2, np.pi, -np.pi / 2])
def test_left_and_right_are_not_swapped(yaw):
    c, s = round(float(np.cos(yaw))), round(float(np.sin(yaw)))
    cx, cy = 10.05, 10.05
    lx, ly = cx + 0.25 * c - 0.25 * s, cy + 0.25 * s + 0.25 * c          # 몸 앞 0.25 m · 왼쪽 0.25 m (왼쪽 = 몸 +y)
    v = _vox(_box(round(lx - 0.1, 2), round(ly - 0.1, 2), 0.2, 0.2, 0.3))
    occ = tm.crop_occupancy(v, [[cx, cy, BASE_Z]], [yaw])[0]
    ys = np.nonzero(occ.any(axis=(0, 2)))[0]
    assert len(ys) and (ys > 5).all()                        # y 셀 번호가 5 (몸) 보다 큼 = 왼쪽


def test_the_3d_window_covers_z_minus_0_3_to_plus_0_7_of_the_body():
    cx, cy = 10.05, 10.05
    low = _vox(_box(10.3, 10.0, 0.2, 0.0, 0.1))              # 바닥 위 0~0.1 (몸 -0.35~-0.25): 창의 맨 아래 층
    assert tm.crop_occupancy(low, [[cx, cy, BASE_Z]], [0.0])[0][..., 0].sum() == 4
    top_in = _vox(_box(10.3, 10.0, 0.2, 1.0, 0.1))           # 1.0~1.1 = 창의 맨 위 층 (몸 +0.65~+0.75)
    assert tm.crop_occupancy(top_in, [[cx, cy, BASE_Z]], [0.0])[0][..., 10].sum() == 4
    above = _vox(_box(10.3, 10.0, 0.2, 1.1, 0.1))            # 창 위
    assert not tm.crop_occupancy(above, [[cx, cy, BASE_Z]], [0.0]).any()


def test_outside_the_room_is_occupied_and_the_outer_wall_is_read_as_wall():
    v = _vox()
    pose, yaw = [[0.35, 10.05, BASE_Z]], [np.pi]             # 서쪽 벽 (x < 0.2) 가까이에서 서쪽을 봄
    occ = tm.crop_occupancy(v, pose, yaw)[0]
    assert occ[5:].all() and not occ[:5].any()               # 앞 0.15 m 부터 벽 · 방 밖 전부 점유
    el = tm.crop_elevation(v, pose, yaw)[0]
    assert (el[13:] > 0.6).all() and np.allclose(el[:10], -BASE_Z, atol=1e-6)


def test_elevation_reads_step_height_and_ignores_overhead_above_the_cap():
    v = _vox({"type": "stairs", "x": 10.0, "y": 8.0, "step_m": 0.15}, _box(8.1, 8.85, 0.4, 1.2, 0.3))
    el = tm.crop_elevation(v, [[9.05, 9.05, BASE_Z]], [0.0])[0]
    row = el[:, 10]                                          # 몸 앞뒤 한 줄
    assert np.isclose(row[20], -BASE_Z) and np.isclose(row[28], 0.30 - BASE_Z)    # 계단 첫 칸은 바닥 · 둘째 단은 0.3 m
    assert np.allclose(el[0:4, 8:13], -BASE_Z)               # 몸 뒤 (x 8.1~8.5) 매달린 상자 (z 1.2~) 는 z_cap 위라 바닥으로 읽힘


def test_bad_inputs_are_refused():
    v = _vox()
    with pytest.raises(ValueError):
        tm.crop_occupancy(v, [[1.0, 1.0]], [0.0])
    with pytest.raises(ValueError):
        tm.RoomVoxels(np.zeros((3, 3, 3), bool))


def test_batch_matches_single_poses():
    v = _vox(_box(9.3, 10.0, 0.4, 0.2, 0.3), {"type": "stairs", "x": 12.0, "y": 8.0})
    poses = np.array([[9.0, 10.2, BASE_Z], [11.5, 9.0, BASE_Z], [3.0, 3.0, BASE_Z + 0.1]])
    yaws = np.array([0.0, 0.3, -2.0])
    occ, el = tm.crop_occupancy(v, poses, yaws), tm.crop_elevation(v, poses, yaws)
    for i in range(3):
        assert (occ[i] == tm.crop_occupancy(v, poses[i:i + 1], yaws[i:i + 1])[0]).all()
        assert np.allclose(el[i], tm.crop_elevation(v, poses[i:i + 1], yaws[i:i + 1])[0])
