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


def _task(weight=0.0, **kw):
    from pathlib import Path
    from foothold_s2.nav import grade_map as gm, room_generator as rg
    table = gm.load_grade_table(str(Path(__file__).resolve().parents[1] / "nav" / "grade_table_draft.yaml"))
    room = rg.make_room(1000, rg.RoomConfig(sparse_patch_kinds=()))[1]
    t = nav_task.NavTask([nav_task.make_asset(room, table)], 2, np.random.default_rng(3), **kw)
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


def test_shape_decay_off_keeps_the_scale_at_one():
    t = _task(0.0)
    t.shape_w = 5.0; t.shape_decay = False
    t.step(_st(t._pos_prev.copy(), [[0.5, 0, 0]] * 2))
    t.pgcl[1].level = 2
    for _ in range(150):
        t.step(_st(np.stack([_along(t, 0, 0.1), _along(t, 1, 0.1)]), [[0.5, 0, 0]] * 2)); s = t.take_stats()
    assert t.shape_scale == 1.0 and s["nv_shape_scale"] == 1.0


def _level2_shape(all_levels):
    t = _task(0.0)
    t.shape_w = 5.0; t.shape_all_levels = all_levels
    t.step(_st(t._pos_prev.copy(), [[0.5, 0, 0]] * 2))
    t.pgcl[1].level = 2
    out = t.step(_st(np.stack([_along(t, 0, 0.1), _along(t, 1, 0.1)]), [[0.5, 0, 0]] * 2))
    return out["terms"]["r_shape"]


def test_shape_levels_all_gives_level2_envs_the_approach_reward_and_default_does_not():
    off = _level2_shape(False)
    on = _level2_shape(True)
    assert off[1] == 0.0 and off[0] > 0.0                       # default 1: level 2 env reads 0, level 1 env pays
    assert on[1] > 0.0 and np.isclose(on[0], off[0])            # all: level 2 pays too, level 1 unchanged


def _near_first_subgoal(t, d):
    """각 env 의 지금 부목표에서 +x 로 d m 떨어진 위치."""
    return np.stack([np.asarray(t.pgcl[i].target.point, float) + [d, 0.0] for i in range(2)])


def test_reach_radius_default_is_the_paper_0_1_and_0_3_counts_a_0_25_m_distance_as_reached():
    from foothold_s2.nav import pgcl
    t = _task()
    assert t.reach_m == pgcl.REACH_M == rewards_hl.ARRIVE_M == 0.1 and all(p.reach_m == 0.1 for p in t.pgcl)
    out = t.step(_st(_near_first_subgoal(t, 0.25), [[0.5, 0, 0]] * 2))
    assert t.take_stats()["nv_sub_reached"] == 0 and (out["terms"]["r1"] == 0).all()          # 0.25 m is not a reach at the default 0.1
    w = _task(reach_m=0.3)
    assert w.reach_m == 0.3 and all(p.reach_m == 0.3 for p in w.pgcl)
    out = w.step(_st(_near_first_subgoal(w, 0.25), [[0.5, 0, 0]] * 2))
    stats = w.take_stats()
    assert stats["nv_sub_reached"] == 2 and (out["terms"]["r1"] > 0).all()                      # 0.25 m < 0.3 m: reached (both PGCL and r1)
    far = _task(reach_m=0.3)
    far.step(_st(_near_first_subgoal(far, 0.35), [[0.5, 0, 0]] * 2))
    assert far.take_stats()["nv_sub_reached"] == 0                                              # 0.35 m is still outside 0.3 m


def test_reward_terms_arrive_radius_follows_the_argument_and_defaults_to_the_paper_value():
    n = 1
    z = np.zeros
    base = dict(pos_xy=np.array([[0.25, 0.0]]), subgoal_xy=np.zeros((n, 2)), v_xy=z((n, 2)), v_z=z(n), omega_xy=z((n, 2)), q=z((n, 12)), q0=z(12),
                cmd=z((n, 3)), cmd_prev=z((n, 3)), cmd_prev2=z((n, 3)), actual=z((n, 3)), v_des=np.full(n, 0.5), eta=np.ones(n), limited=z(n, bool), collision=z(n, bool))
    s = rewards_hl.HLState(**base)
    assert rewards_hl.reward_terms(s)["r1"][0] == 0.0 and rewards_hl.reward_terms(s, arrive_m=0.3)["r1"][0] == 1.0


def test_dsub_min_is_the_median_over_unfinished_episodes_of_the_closest_approach_to_the_current_subgoal():
    t = _task()
    for d in (0.8, 0.6, 0.5, 0.7):                                                              # env 0 gets as close as 0.5 m, env 1 as close as 0.7 m
        pos = np.stack([np.asarray(t.pgcl[0].target.point, float) + [d, 0.0], np.asarray(t.pgcl[1].target.point, float) + [d + 0.2 if d == 0.5 else 0.9, 0.0]])
        t.step(_st(pos, [[0.5, 0, 0]] * 2))
    t.reset_envs([0, 1], start_xy=np.stack([t.start[0], t.start[1]]))                         # both episodes end without reaching
    stats = t.take_stats()
    assert abs(stats["nv_dsub_min"] - np.median([0.5, 0.7])) < 1e-9 and stats["nv_episodes"] == 2
    assert t.take_stats() == {}                                                                 # nothing since: no key, no stale value
    r = _task()
    r.step(_st(_near_first_subgoal(r, 0.05), [[0.5, 0, 0]] * 2))                              # both reached the first subgoal and then are measured against the next one
    r.reset_envs([0, 1], start_xy=np.stack([r.start[0], r.start[1]]))
    assert r.take_stats()["nv_dsub_min"] > 0.1


def test_per_level_columns_average_each_pgcl_level_separately_and_sum_back_to_the_mixed_totals():
    t = _task()
    t.pgcl[1].level = 3                                                           # env 0 at level 1, env 1 at level 3 (level 2 stays empty)
    sub = t.subgoal.copy()
    behind = sub - np.array([[1.0, 0.0], [1.0, 0.0]])
    t.step(_st(behind, [[-0.5, 0.0, 0.0], [0.5, 0.0, 0.0]]))                    # env 0 moves away (cos -1), env 1 toward (cos +1)
    t.step(_st(np.stack([np.asarray(t.pgcl[0].target.point, float) + [0.05, 0.0], behind[1]]), [[0.5, 0, 0]] * 2))   # env 0 reaches its first subgoal
    n0 = len(t.pgcl[0]._sub)
    prog0 = t.pgcl[0]._i / n0
    d1 = float(np.linalg.norm(behind[1] - np.asarray(t.pgcl[1]._sub[0].point)))
    t.reset_envs([0, 1], start_xy=np.stack([t.start[0], t.start[1]]))
    s = t.take_stats()
    assert (s["nv_eps_l1"], s["nv_eps_l2"], s["nv_eps_l3p"]) == (1, 0, 1)
    assert s["nv_sub_reached_l1"] == 1 and s["nv_sub_reached_l3p"] == 0 and s["nv_sub_reached_l1"] + s["nv_sub_reached_l2"] + s["nv_sub_reached_l3p"] == s["nv_sub_reached"]
    assert s["nv_cos_n_l1"] == 2 and s["nv_cos_n_l3p"] == 2 and s["nv_cos_n_l1"] + s["nv_cos_n_l2"] + s["nv_cos_n_l3p"] == s["nv_cos_n"] == 4
    assert abs(s["nv_cos_l3p"] - 1.0) < 1e-9 and s["nv_cos_l2"] == -1.0 and s["nv_prog_l2"] == s["nv_dend_l2"] == s["nv_succ_l2"] == -1.0   # empty level reads -1
    assert abs(s["nv_prog_l1"] - prog0) < 1e-12 and s["nv_prog_l3p"] == 0.0 and abs((s["nv_prog_l1"] + s["nv_prog_l3p"]) / 2 - s["nv_progress_end"]) < 1e-12
    assert abs(s["nv_dend_l3p"] - d1) < 1e-9 and abs((s["nv_dend_l1"] + s["nv_dend_l3p"]) / 2 - s["nv_dsub_end"]) < 1e-9
    assert s["nv_succ_l1"] == 0.0 and s["nv_succ_l3p"] == 0.0


def _eta_after_two_episodes(mode, new_task_between):
    t = _task()
    t.visit_reset = mode
    t.step(_st(_near_first_subgoal(t, 0.4), [[0.5, 0, 0]] * 2))
    n_before = int(t.visit.counts[0].sum())
    if new_task_between:
        t.pgcl[0].needs_new_task = True
    t.reset_envs([0, 1], start_xy=np.stack([t.start[0], t.start[1]]))                 # episode 1 ends, same start
    return n_before, int(t.visit.counts[0].sum()), int(t.visit.counts[1].sum())


def test_visit_reset_task_keeps_eta_across_episodes_of_the_same_task_and_clears_it_on_a_new_task():
    b, kept0, kept1 = _eta_after_two_episodes("task", False)
    assert b > 0 and kept0 == b and kept1 == b                                         # same task: both envs keep the grid
    b, c0, c1 = _eta_after_two_episodes("task", True)
    assert c0 == 0 and c1 == b                                                         # env 0 got a new task: cleared; env 1 kept
    b, e0, e1 = _eta_after_two_episodes("episode", False)
    assert e0 == 0 and e1 == 0                                                         # default: cleared every episode (as before)
    assert _task().visit_reset == "episode"


def test_r1_r2_sums_are_in_the_iteration_row():
    t = _task()
    t.step(_st(_near_first_subgoal(t, 0.4), [[0.5, 0, 0]] * 2))
    t.step(_st(_near_first_subgoal(t, 0.4), [[0.5, 0, 0]] * 2))
    s = t.take_stats()
    assert abs(s["nv_r2_sum"] - s["nv_r2"] * 2) < 1e-12 and abs(s["nv_r1_sum"] - s["nv_r1"] * 2) < 1e-12 and s["nv_r2_sum"] > 0


def test_cos_disp_is_plus_one_toward_minus_one_away_and_yaw_error_is_small_only_for_the_right_yaw():
    t = _task()
    start = t._pos_prev.copy()
    d = t.subgoal - start
    u = d / np.linalg.norm(d, axis=1, keepdims=True)
    yaw = np.pi / 2                                                        # body +x points world +y: a body velocity (0.5, 0) moves the body along +y
    t.step(_st(start + 0.05 * u, [[0.5, 0, 0]] * 2, yaw=0.0))                # displacement toward the subgoal, state yaw 0
    s = t.take_stats()
    assert s["nv_cos_disp_n"] == 2 and abs(s["nv_cos_disp"] - 1.0) < 1e-9
    t2 = _task(); p = t2._pos_prev.copy(); u2 = (t2.subgoal - p) / np.linalg.norm(t2.subgoal - p, axis=1, keepdims=True)
    t2.step(_st(p - 0.05 * u2, [[0.5, 0, 0]] * 2, yaw=0.0))
    assert abs(t2.take_stats()["nv_cos_disp"] + 1.0) < 1e-9
    # yaw check: world displacement along +y with body velocity (0.5, 0) means the true yaw is 90 deg
    ok, bad = _task(), _task()
    for tk, y in ((ok, np.pi / 2), (bad, 0.0)):
        p0 = tk._pos_prev.copy()
        tk.step(_st(p0 + np.array([[0.0, 0.05]] * 2), [[0.5, 0, 0]] * 2, yaw=y))
    a, b = ok.take_stats(), bad.take_stats()
    assert a["nv_yaw_n"] == 2 and a["nv_yaw_err_deg"] < 1e-6 and a["nv_yaw_ok_frac"] == 1.0
    assert abs(b["nv_yaw_err_deg"] - 90.0) < 1e-6 and b["nv_yaw_ok_frac"] == 0.0
    assert _task().take_stats() == {}                                         # nothing since: no key


def test_heading_judge_passes_for_the_true_yaw_and_stops_for_a_wrong_quaternion_order_or_no_motion():
    from foothold_s2.nav import heading_check as hc
    n = 6
    for yaw0 in (0.0, np.pi / 2, np.pi, -np.pi / 2, 0.7):
        yaw = np.full((10, n), yaw0); vb = np.tile([0.4, 0.0], (10, n, 1)); p0 = np.zeros((n, 2)); p1 = 0.35 * np.stack([np.cos(yaw0) * np.ones(n), np.sin(yaw0) * np.ones(n)], 1)
        r = hc.judge(yaw, vb, p0, p1, np.zeros(n, bool))
        assert r["ok"] and r["err_vs_yaw_median_deg"] < 1e-6, (yaw0, r)
        wrong = hc.judge(yaw + np.pi / 2, vb, p0, p1, np.zeros(n, bool))          # a yaw read 90 deg off
        assert not wrong["ok"] and "interpreted yaw" in wrong["reason"]
    still = hc.judge(np.zeros((10, n)), np.tile([0.4, 0.0], (10, n, 1)), np.zeros((n, 2)), np.zeros((n, 2)) + 0.01, np.zeros(n, bool))
    assert not still["ok"] and "inconclusive" in still["reason"]
    fell = hc.judge(np.zeros((10, n)), np.tile([0.4, 0.0], (10, n, 1)), np.zeros((n, 2)), np.tile([0.35, 0.0], (n, 1)), np.ones(n, bool))
    assert not fell["ok"] and "inconclusive" in fell["reason"]                      # envs that ended inside the window do not count


class _FakeNav:
    """몸 +x 로 가라는 명령에 진짜 yaw 방향으로 움직이는 가짜 NavEnv. quat_order: 'wxyz' (맞음) 또는 'xyzw' (순서를 잘못 읽은 값을 줌)."""
    class _Raw: step_dt = 0.02
    def __init__(self, quat_order, n=8, yaw0=0.9):
        from foothold_s2.nav.command_space import CommandSpace
        self.n, self.hold, self.raw, self.quat_order, self.yaw0 = n, 5, self._Raw(), quat_order, yaw0
        self.space = type("S", (), {"mode": "clip"})()
        self.pos = np.zeros((n, 2))
    def _state(self):
        w, z = np.cos(self.yaw0 / 2), np.sin(self.yaw0 / 2)
        q = [w, 0, 0, z] if self.quat_order == "wxyz" else [0, 0, z, w]
        s = _st(self.pos.copy(), [[0.4, 0.0, 0.0]] * self.n)
        s.quat_w = np.tile(q, (self.n, 1)); s.pos_local = np.c_[self.pos, np.full(self.n, 0.35)]; s.done = np.zeros(self.n, bool)
        return s
    def reset(self):
        self.pos[:] = 0.0; return self._state()
    def step(self, action):
        assert np.allclose(np.asarray(action)[:, 0], 0.5) and np.allclose(np.asarray(action)[:, 1:], 0.0)
        self.pos += 0.4 * 0.1 * np.array([np.cos(self.yaw0), np.sin(self.yaw0)]); return self._state()


def test_heading_selfcheck_run_passes_with_the_right_quaternion_order_and_raises_with_the_wrong_one():
    from foothold_s2.nav import heading_check as hc
    assert hc.run(_FakeNav("wxyz"))["ok"]
    try:
        hc.run(_FakeNav("xyzw"))
    except RuntimeError as e:
        assert "HEADING_SELFCHECK FAILED" in str(e)
    else:
        raise AssertionError("a wrongly read quaternion must stop training")
    assert hc.run(object()) is None                                                    # fake env without the attributes: skipped


def _walk(yaw_read_offset, n=64, T=200, dt=0.1, seed=0):
    """진짜 yaw 로 걷는 가짜 로봇 (걸음 흔들림: 몸 속도 · 위치에 잡음). yaw_read_offset 만큼 틀리게 읽은 yaw 를 준다 (0 = 맞게 읽음)."""
    from foothold_s2.nav.heading_check import WindowYawCheck
    rng = np.random.default_rng(seed)
    yaw = rng.uniform(-np.pi, np.pi, n); pos = np.zeros((n, 2)); w = WindowYawCheck((1, 5, 10))
    for _ in range(T):
        yaw = yaw + rng.normal(0, 0.05, n)                                   # 몸이 천천히 돈다
        vb = np.stack([0.4 + rng.normal(0, 0.08, n), rng.normal(0, 0.08, n)], 1)
        c, s = np.cos(yaw), np.sin(yaw)
        step = np.stack([c * vb[:, 0] - s * vb[:, 1], s * vb[:, 0] + c * vb[:, 1]], 1) * dt + rng.normal(0, 0.012, (n, 2))   # 위치 흔들림
        pos = pos + step
        w.push(pos, vb, yaw + yaw_read_offset, np.zeros(n, bool))
    return w.table()


def test_window_yaw_check_gets_better_with_longer_windows_and_catches_a_wrong_yaw():
    ok = _walk(0.0)
    assert ok[10]["median_deg"] < ok[1]["median_deg"] and ok[10]["median_deg"] < 10.0 and ok[10]["within_30"] > 0.95
    bad = _walk(np.pi / 2)                                                    # 쿼터니언 순서를 틀리게 읽은 꼴 (90 도 어긋남)
    assert all(r["median_deg"] > 60.0 for r in bad.values())


def test_window_yaw_check_skips_samples_that_cross_a_reset_and_is_off_by_default():
    from foothold_s2.nav.heading_check import WindowYawCheck
    w = WindowYawCheck((5,))
    for t in range(12):
        w.push(np.full((1, 2), float(t)), np.ones((1, 2)), np.zeros(1), np.array([t == 8]))
    assert w.table()[5]["samples"] == 2                                      # t=6,7 만 (리셋 t=8 뒤에는 6 틱이 지나야 다시 쓰임; 12 틱 안에는 없음)
    assert nav_task.NavTask.QUAT_WINDOWS == ()


# ---- 방문 격자 선택 칸 `shared` (HIPAN-NEXT-RUN-1119): 방마다 하나를 모든 env 가 함께 쌓고 비우지 않는다. 꺼짐 (기본) = 지금과 같음 ----
def test_shared_visit_is_off_by_default_and_the_default_grid_is_unchanged():
    t = _task()
    assert t.visit_reset == "episode" and t.visit.shared is False and t.visit.counts.shape == (2, 40, 40)
    ref = np.zeros((2, 40, 40), np.int32)                                         # the old per-env grid, rebuilt by hand
    g = rewards_hl.VisitGrid(2)
    rng = np.random.default_rng(0)
    for _ in range(20):
        p = rng.uniform(0.0, 20.0, (2, 2))
        on = rng.random(2) > 0.2
        cell = np.clip(np.floor(p / 0.5).astype(int), 0, 39)
        for i in range(2):
            if on[i]:
                ref[i, cell[i, 0], cell[i, 1]] += 1
        want = np.array([ref[i, cell[i, 0], cell[i, 1]] if on[i] else 1 for i in range(2)], float)
        assert (g.visit(p, active=on) == want).all()
    assert (g.counts == ref).all()


def test_shared_visit_two_envs_count_the_same_cell_and_it_is_never_cleared():
    t = _task()
    t.use_shared_visit()
    assert t.visit_reset == "shared" and t.visit.shared and t.visit.counts.shape == (1, 40, 40)        # one grid for the one room
    pos = np.array([[5.2, 5.2], [5.3, 5.4]])                                       # both in the same 0.5 m cell of room 0
    eta = t.visit.visit(pos, group=t.room_id)
    assert t.visit.counts[0, 10, 10] == 2 and (eta == 2.0).all()                  # both envs are counted before either reads
    out = t.step(_st(_near_first_subgoal(t, 0.4), [[0.5, 0, 0]] * 2))             # a real step adds to the same grid (room frame origin 0)
    total = int(t.visit.counts.sum())
    assert total == 4 and out["eta"].shape == (2,)
    t.reset_envs([0, 1], start_xy=np.stack([t.start[0], t.start[1]]))             # episode ends: the shared grid is not cleared
    assert int(t.visit.counts.sum()) == total
    t.pgcl[0].needs_new_task = True
    t.reset_envs([0, 1], start_xy=np.stack([t.start[0], t.start[1]]))             # nor on a new task
    assert int(t.visit.counts.sum()) == total
    again = t.visit.visit(pos, group=t.room_id, active=np.array([True, False]))   # a finished env does not count and reads eta = 1
    assert t.visit.counts[0, 10, 10] == 3 and again[0] == 3.0 and again[1] == 1.0
    try:
        t.visit.visit(pos)
        raise AssertionError("shared grid without rooms must refuse")
    except ValueError:
        pass


def test_the_shared_grid_is_one_per_room_so_two_rooms_do_not_mix():
    g = rewards_hl.VisitGrid(3, num_groups=2)
    p = np.array([[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]])
    eta = g.visit(p, group=np.array([0, 0, 1]))
    assert list(eta) == [2.0, 2.0, 1.0] and g.counts[0, 2, 2] == 2 and g.counts[1, 2, 2] == 1
    g.reset(None); g.reset([0])
    assert int(g.counts.sum()) == 3


def test_r2_falls_faster_with_the_shared_grid_than_with_the_per_env_grid():
    def r2_total(shared):
        t = _task()
        if shared:
            t.use_shared_visit()
        for _ in range(6):                                                         # two envs stand in the same cell every tick
            t.step(_st(np.array([[5.2, 5.2], [5.3, 5.4]]), [[0.0, 0, 0]] * 2))
        return t.take_stats()["nv_r2_sum"]
    assert r2_total(True) < r2_total(False)


def test_cos_of_the_first_three_ticks_of_an_episode_is_recorded_by_age():
    t = _task()
    sub = t.subgoal.copy()
    p0 = t._pos_prev.copy()                                                        # episode start positions (reset sets them)
    toward = (sub - p0) / np.linalg.norm(sub - p0, axis=1, keepdims=True)
    for k in range(4):                                                             # env 0 steps straight to its subgoal, env 1 straight away from it
        pos = p0 + np.stack([0.01 * (k + 1) * toward[0], -0.01 * (k + 1) * toward[1]])
        t.step(_st(pos, [[0.5, 0, 0]] * 2))
        if k == 0:
            pos1 = pos
    s = t.take_stats()
    assert s["nv_cos_age13_n"] == 6 and abs(s["nv_cos_age13"]) < 1e-6              # three ticks x two envs, +1 and -1 cancel
    assert all(abs(s[f"nv_cos_age{a}"]) < 1e-6 for a in (1, 2, 3))
    assert t.take_stats() == {}                                                    # drained
    t2 = _task()
    assert t2.take_stats() == {}
    t2.step(_st(t2._pos_prev, [[0.0, 0, 0]] * 2))                                  # no movement: no direction, nothing counted
    assert t2.take_stats()["nv_cos_age13"] == -1.0


def test_cos_age_is_plus_one_when_every_young_env_walks_to_its_subgoal():
    t = _task()
    sub = t.subgoal.copy(); p0 = t._pos_prev.copy()
    step = 0.01 * (sub - p0) / np.linalg.norm(sub - p0, axis=1, keepdims=True)
    t.step(_st(p0 + step, [[0.5, 0, 0]] * 2))
    s = t.take_stats()
    assert s["nv_cos_age1"] > 0.999 and s["nv_cos_age13_n"] == 2 and s["nv_cos_age2"] == -1.0 and s["nv_cos_age3"] == -1.0
