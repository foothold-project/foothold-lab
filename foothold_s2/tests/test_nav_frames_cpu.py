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


def _along(t, i, d):
    """env i 의 시작에서 경로를 따라 d m 간 위치 (방 틀)."""
    pts = np.asarray(t.path[i], float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    k = min(int(np.searchsorted(cum, d, side="right")) - 1, len(seg) - 1)
    return pts[k] + (pts[k + 1] - pts[k]) * (d - cum[k]) / max(seg[k], 1e-12)


def test_shaping_is_off_by_default_and_pays_plus_for_closing_in_and_minus_for_backing_off():
    off = _task(0.0)
    off.step(_st(off._pos_prev.copy(), [[0.5, 0, 0]] * 2))
    assert "r_shape" not in off.step(_st(off._pos_prev.copy(), [[0.5, 0, 0]] * 2))["terms"]
    t = _task(0.0)
    t.shape_w = 2.0
    t.step(_st(t._pos_prev.copy(), [[0.5, 0, 0]] * 2))                         # first tick: still at the start, no gain
    p0 = t._pos_prev.copy()
    a = t.step(_st(np.stack([_along(t, 0, 0.2), _along(t, 1, 0.2)]), [[0.5, 0, 0]] * 2))["terms"]["r_shape"]
    assert np.allclose(a, 2.0 * 0.2, atol=0.02)                                 # 0.2 m closer along the path x w
    b = t.step(_st(p0, [[-0.5, 0, 0]] * 2))["terms"]["r_shape"]
    assert (b < -0.3).all()                                                     # back to the start: minus


def test_shaping_value_does_not_jump_when_a_subgoal_is_passed_and_is_clipped_per_tick():
    t = _task(0.0)
    t.shape_w = 5.0
    t.step(_st(t._pos_prev.copy(), [[0.5, 0, 0]] * 2))
    first_sub = np.asarray(t.pgcl[0]._sub[0].point, float)
    d_sub = float(np.linalg.norm(first_sub - t.start[0]))                       # about where the first subgoal is (path is almost straight until it)
    vals, passed = [], []
    for k in range(1, 12):
        d = 0.1 * k * max(d_sub, 1.0)
        out = t.step(_st(np.stack([_along(t, 0, d), _along(t, 1, 0.01)]), [[0.5, 0, 0]] * 2))
        vals.append(out["terms"]["r_shape"][0]); passed.append(t.pgcl[0]._i)
    assert max(passed) >= 1                                                     # the walk went past the first subgoal
    assert all(0.0 < v <= 0.5 + 1e-12 for v in vals)                            # always forward, clipped to 0.5 per tick
    step_gain = np.diff([0.0] + [0.1 * k * max(d_sub, 1.0) for k in range(1, 12)])
    ok = [abs(v - min(5.0 * g, 0.5)) < 0.06 for v, g in zip(vals, step_gain)]
    assert all(ok), (vals, step_gain, passed)                                   # equals the clipped w x walked length also on the tick the subgoal was passed


def test_shaping_is_zero_for_level_2_envs_and_decays_over_100_iterations_after_10_percent_are_at_level_2():
    t = _task(0.0)
    t.shape_w = 5.0
    t.step(_st(t._pos_prev.copy(), [[0.5, 0, 0]] * 2))
    t.pgcl[1].level = 2
    out = t.step(_st(np.stack([_along(t, 0, 0.1), _along(t, 1, 0.1)]), [[0.5, 0, 0]] * 2))["terms"]["r_shape"]
    assert out[0] > 0 and out[1] == 0.0
    s = t.take_stats()
    assert s["nv_shape_scale"] == 1.0 and t.shape_scale < 1.0 and abs(t.shape_scale - 0.99) < 1e-12      # half the envs are at level 2: decay starts
    for _ in range(98):
        t.step(_st(t._pos_prev.copy(), [[0.5, 0, 0]] * 2)); t.take_stats()
    assert abs(t.shape_scale - 0.01) < 1e-9
    t.step(_st(t._pos_prev.copy(), [[0.5, 0, 0]] * 2)); t.take_stats()
    assert t.shape_scale == 0.0
    t2 = _task(0.0)
    t2.shape_w = 5.0
    t2.step(_st(t2._pos_prev.copy(), [[0.5, 0, 0]] * 2)); t2.take_stats()
    assert t2.shape_scale == 1.0                                                # nobody at level 2: no decay
