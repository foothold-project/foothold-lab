from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2.nav import room_generator as rg
from foothold_s2.nav import teacher_maps as tm
from foothold_s2.nav import teacher_obs as to


def _state(pos_local, yaw, n=None, proprio=None):
    pos_local = np.asarray(pos_local, float)
    n = len(pos_local)
    q = np.stack([np.cos(np.asarray(yaw) / 2), np.zeros(n), np.zeros(n), np.sin(np.asarray(yaw) / 2)], 1)
    return SimpleNamespace(pos_local=pos_local, quat_w=q, vel_b=np.tile([0.5, 0.0, 0.0], (n, 1)), ang_vel_b=np.tile([0.0, 0.0, 0.2], (n, 1)),
                           proprio=np.zeros((n, 45)) if proprio is None else proprio)


@pytest.fixture(scope="module")
def vox():
    _spec, room = rg.make_room(3, rg.FIRST_ROUND_CFG, None)
    _spec2, room2 = rg.make_room(4, rg.FIRST_ROUND_CFG, None)
    return {0: tm.RoomVoxels.from_room(room), 1: tm.RoomVoxels.from_room(room2)}


def test_layout_widths_and_offsets_add_up():
    lay = to.TeacherObsLayout()
    assert lay.sizes == {"o_p": 45, "c_prev": 3, "x_m": 6, "subgoal": 2, "occ": 1694, "elev": 651} and lay.total == 2401
    off = lay.offsets
    assert off["o_p"] == (0, 45) and off["elev"][1] == lay.total and off["occ"] == (56, 1750)


def test_yaw_and_subgoal_rotate_into_the_body_frame():
    q = np.array([[np.cos(np.pi / 4), 0, 0, np.sin(np.pi / 4)]])                    # yaw +90 도
    assert to.yaw_from_quat_wxyz(q)[0] == pytest.approx(np.pi / 2)
    rel = to.subgoal_in_body(np.array([[5.0, 5.0]]), np.array([np.pi / 2]), np.array([[5.0, 8.0]]))   # 방 틀 +y 3 m = 몸 앞쪽
    assert rel[0] == pytest.approx([3.0, 0.0], abs=1e-9)
    rel = to.subgoal_in_body(np.array([[5.0, 5.0]]), np.array([0.0]), np.array([[5.0, 8.0]]))           # yaw 0: 왼쪽 3 m
    assert rel[0] == pytest.approx([0.0, 3.0], abs=1e-9)


def test_build_gives_flat_and_parts_and_envs_in_different_rooms_read_their_own_voxels(vox):
    n = 4
    state = _state([[0, 0, 0.34], [1, 1, 0.34], [0, 0, 0.34], [1, 1, 0.34]], [0.0, 0.3, 0.0, 0.3], proprio=np.arange(n * 45).reshape(n, 45) / 100)
    out = to.build(vox, [0, 0, 1, 1], state, np.zeros((n, 3)), np.array([[12.0, 10.0]] * n))
    lay = to.TeacherObsLayout()
    assert out["flat"].shape == (n, lay.total) and out["flat"].dtype == np.float32
    a, b = lay.offsets["occ"]
    assert np.array_equal(out["flat"][:, a:b].reshape(n, 14, 11, 11) > 0, out["parts"]["occ"])
    direct0 = tm.crop_occupancy(vox[0], to.to_room_frame(state.pos_local)[:1], np.array([0.0]))
    direct1 = tm.crop_occupancy(vox[1], to.to_room_frame(state.pos_local)[2:3], np.array([0.0]))
    assert np.array_equal(out["parts"]["occ"][0], direct0[0]) and np.array_equal(out["parts"]["occ"][2], direct1[0])
    assert out["parts"]["subgoal"][0] == pytest.approx([2.0, 0.0], abs=1e-6)       # 방 틀 (10, 10) -> (12, 10), yaw 0
    assert np.allclose(out["parts"]["x_m"][0], [0.5, 0, 0, 0, 0, 0.2]) and np.allclose(out["parts"]["o_p"][1], np.arange(45, 90) / 100)


def test_bad_shapes_unknown_rooms_and_nonfinite_values_are_refused(vox):
    state = _state([[0, 0, 0.34]], [0.0])
    with pytest.raises(ValueError, match="required"):
        to.build(vox, [0], state, np.zeros((1, 2)), np.zeros((1, 2)))
    with pytest.raises(ValueError, match="without voxels"):
        to.build(vox, [7], state, np.zeros((1, 3)), np.zeros((1, 2)))
    state.proprio[0, 0] = np.nan
    with pytest.raises(RuntimeError, match="non-finite"):
        to.build(vox, [0], state, np.zeros((1, 3)), np.zeros((1, 2)))
