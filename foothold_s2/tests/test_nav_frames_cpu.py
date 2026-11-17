"""HiPAN 좌표 틀 점검 (G3 83 회: 부목표 끝 거리가 늘어남): teacher 관측의 부목표 칸은 몸 틀 · yaw 부호 · 방 틀 합산 · 보상에 다가가는 길잡이가 있나. CPU · Kit 없음."""
import numpy as np

from foothold_s2.nav import nav_task, rewards_hl, teacher_obs
from foothold_s2.nav.nav_task import room_frame_origin_xy


def _q(yaw):
    return np.array([[np.cos(yaw / 2), 0.0, 0.0, np.sin(yaw / 2)]])


def test_subgoal_observation_is_in_the_body_frame_with_the_left_positive_and_yaw_sign():
    pos, sub = np.array([[5.0, 5.0]]), np.array([[6.0, 5.0]])                 # the subgoal is +1 m on the room +x axis
    for yaw, want in ((0.0, (1.0, 0.0)), (np.pi / 2, (0.0, -1.0)), (-np.pi / 2, (0.0, 1.0)), (np.pi, (-1.0, 0.0))):
        got = teacher_obs.subgoal_in_body(pos, teacher_obs.yaw_from_quat_wxyz(_q(yaw)), sub)[0]
        assert np.allclose(got, want, atol=1e-12), (yaw, got)               # facing +y: a goal on the room +x is on the body right (y < 0)
    sub2 = np.array([[5.0, 6.0]])                                            # +1 m on the room +y: body left when facing +x
    assert np.allclose(teacher_obs.subgoal_in_body(pos, teacher_obs.yaw_from_quat_wxyz(_q(0.0)), sub2)[0], (0.0, 1.0))
    assert np.allclose(teacher_obs.subgoal_in_body(pos, teacher_obs.yaw_from_quat_wxyz(_q(np.pi / 2)), sub2)[0], (1.0, 0.0), atol=1e-12)


def test_room_frame_position_is_the_body_offset_from_the_env_origin_plus_the_start_point_in_the_room_frame():
    pitch = 25.0
    origins = np.array([[3.0 + 2 * pitch, 4.0]])                            # mesh coordinates: row 2, start point (3, 4)
    org = room_frame_origin_xy(origins, [2], pitch)
    assert np.allclose(org, [[3.0, 4.0]])
    pos_local = np.array([[0.5, -0.25, 0.35]])                              # the body moved (+0.5, -0.25) from its env origin
    assert np.allclose(teacher_obs.to_room_frame(pos_local, org)[0, :2], [3.5, 3.75])


def test_the_only_term_that_pays_for_getting_closer_to_the_subgoal_is_r1_inside_0_1_m():
    n = 3
    z = np.zeros
    base = dict(pos_xy=np.array([[2.0, 0.0], [1.0, 0.0], [0.05, 0.0]]), subgoal_xy=np.zeros((n, 2)), v_z=z(n), omega_xy=z((n, 2)), q=z((n, 12)), q0=z(12),
                cmd=z((n, 3)), cmd_prev=z((n, 3)), cmd_prev2=z((n, 3)), actual=z((n, 3)), v_des=np.full(n, 0.5), eta=np.ones(n), limited=z(n, bool), collision=z(n, bool))
    toward = rewards_hl.reward_terms(rewards_hl.HLState(v_xy=np.array([[-0.5, 0.0]] * n), **base))
    away = rewards_hl.reward_terms(rewards_hl.HLState(v_xy=np.array([[0.5, 0.0]] * n), **base))
    for k in toward:
        assert np.allclose(toward[k], away[k]), k                           # no term looks at the direction of motion: toward and away pay the same
    assert list(toward["r1"]) == [0.0, 0.0, 1.0]                            # 2 m and 1 m away: nothing; 0.05 m: 1


def _task(weight=0.0):
    from pathlib import Path
    from foothold_s2.nav import grade_map as gm, room_generator as rg
    table = gm.load_grade_table(str(Path(__file__).resolve().parents[1] / "nav" / "grade_table_draft.yaml"))
    room = rg.make_room(1000, rg.RoomConfig(sparse_patch_kinds=()))[1]
    t = nav_task.NavTask([nav_task.make_asset(room, table)], 2, np.random.default_rng(3))
    starts = [rg.start_points(room, 4, seed=1000)[:, :2]]
    t.build_table(starts, per_start=8, seed=0)
    t.origin_xy = np.zeros((2, 2))
    t.approach_weight = weight
    t.reset_envs([0, 1], start_xy=np.stack([starts[0][0], starts[0][1]]))
    t.take_stats()
    return t


def _st(pos, vel_b, yaw=0.0):
    from foothold_s2.tests.test_nav_task_table_cpu import _state
    s = _state(len(pos), np.asarray(pos, float))
    s.vel_b = np.asarray(vel_b, float)
    s.quat_w = np.tile(_q(yaw), (len(pos), 1))
    return s


def test_cos_vel_sub_is_plus_one_toward_minus_one_away_and_skips_standing_envs():
    t = _task()
    sub = t.subgoal.copy()
    pos = sub - np.array([[1.0, 0.0], [1.0, 0.0]])                              # both 1 m behind their subgoal on the room x axis
    t.step(_st(pos, [[0.5, 0.0, 0.0], [0.02, 0.0, 0.0]]))                         # env 0 moves toward, env 1 is standing (below 0.05)
    s = t.take_stats()
    assert s["nv_cos_n"] == 1 and abs(s["nv_cos_vel_sub"] - 1.0) < 1e-9
    t.step(_st(pos, [[-0.5, 0.0, 0.0], [0.5, 0.0, 0.0]]))                         # env 0 away, env 1 toward
    s = t.take_stats()
    assert s["nv_cos_n"] == 2 and abs(s["nv_cos_vel_sub"]) < 1e-9
    t.step(_st(pos, [[0.0, 0.5, 0.0], [0.0, 0.5, 0.0]], yaw=np.pi / 2))          # facing +y, body +y (left) = room -x: away from a subgoal that is +x of the body
    s = t.take_stats()
    assert s["nv_cos_n"] == 2 and abs(s["nv_cos_vel_sub"] + 1.0) < 1e-9


def test_approach_reward_is_off_by_default_plus_for_closing_in_and_minus_for_backing_off():
    off = _task(0.0)
    off.step(_st(off.subgoal - np.array([[2.0, 0.0]] * 2), [[0.5, 0, 0]] * 2))
    assert "r11" not in off.step(_st(off.subgoal - np.array([[1.5, 0.0]] * 2), [[0.5, 0, 0]] * 2))["terms"]
    t = _task(2.0)
    sub = t.subgoal.copy()
    p0 = t._stat() and t._pos_prev.copy()                                       # the episode start position is the first "previous" one
    unit = (sub - p0) / np.linalg.norm(sub - p0, axis=1, keepdims=True)
    first = t.step(_st(p0, [[0.5, 0, 0]] * 2))["terms"]["r11"]
    assert np.allclose(first, 0.0)                                              # still at the start: no gain
    closer = t.step(_st(p0 + 0.5 * unit, [[0.5, 0, 0]] * 2))["terms"]["r11"]
    assert np.allclose(closer, 2.0 * 0.5)                                       # 0.5 m closer x weight 2
    farther = t.step(_st(p0 - 0.5 * unit, [[-0.5, 0, 0]] * 2))["terms"]["r11"]
    assert np.allclose(farther, -2.0 * 1.0)                                     # 1.0 m farther
