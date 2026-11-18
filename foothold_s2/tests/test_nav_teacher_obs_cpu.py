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


# 답을 아는 입력: 부목표 관측 2 칸 (몸 틀, x 앞 · y 왼쪽, 미터 그대로 · 논문 2604.26504 라인 491 「relative sub-goal position」)
@pytest.mark.parametrize("yaw,sub_world_offset,expected", [
    (0.0, (1.0, 0.0), (1.0, 0.0)),                  # 몸 앞 1 m
    (0.0, (0.0, 1.0), (0.0, 1.0)),                  # 왼쪽 1 m
    (0.0, (-1.0, 0.0), (-1.0, 0.0)),                # 뒤 1 m
    (0.0, (0.0, -1.0), (0.0, -1.0)),                # 오른쪽 1 m
    (np.pi / 2, (1.0, 0.0), (0.0, -1.0)),           # 몸이 90 도 돌아 +y 를 봄: 방 +x 는 몸 오른쪽
    (np.pi / 2, (0.0, 1.0), (1.0, 0.0)),            # 방 +y 는 몸 앞
    (-np.pi / 2, (1.0, 0.0), (0.0, 1.0)),
    (np.pi, (1.0, 0.0), (-1.0, 0.0)),
])
def test_subgoal_obs_columns_match_known_body_frame_values_through_build(vox, yaw, sub_world_offset, expected):
    state = _state([[0.0, 0.0, 0.34]], [yaw])
    c = to.ROOM_ORIGIN_XY
    out = to.build(vox, [0], state, np.zeros((1, 3)), np.array([[c[0] + sub_world_offset[0], c[1] + sub_world_offset[1]]]))
    assert out["parts"]["subgoal"][0] == pytest.approx(expected, abs=1e-6)
    a, b = to.TeacherObsLayout().offsets["subgoal"]
    assert out["flat"][0, a:b] == pytest.approx(expected, abs=1e-6)          # 평탄 벡터의 같은 두 칸도 같은 값 (미터 그대로, 나눗셈 · 한계 없음)


def test_subgoal_obs_transform_is_identity_by_default_and_divides_then_clips_when_asked(vox, monkeypatch):
    assert to.SUBGOAL_OBS_SCALE == 1.0 and to.SUBGOAL_OBS_CLIP == 0.0
    x = np.array([[7.0, -12.0]])
    assert np.array_equal(to.subgoal_obs_transform(x), x)
    monkeypatch.setattr(to, "SUBGOAL_OBS_SCALE", 5.0)
    assert to.subgoal_obs_transform(x)[0] == pytest.approx([1.4, -2.4])
    monkeypatch.setattr(to, "SUBGOAL_OBS_CLIP", 2.0)
    assert to.subgoal_obs_transform(x)[0] == pytest.approx([1.4, -2.0])
    c = to.ROOM_ORIGIN_XY                                                      # build 에도 반영
    out = to.build(vox, [0], _state([[0.0, 0.0, 0.34]], [0.0]), np.zeros((1, 3)), np.array([[c[0] + 7.0, c[1] - 12.0]]))
    assert out["parts"]["subgoal"][0] == pytest.approx([1.4, -2.0], abs=1e-6)
