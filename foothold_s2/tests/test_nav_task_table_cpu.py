"""시작 · 목표 · 경로 표 (G3 Pod: 새 과제 뽑기가 CPU 병목): 표에서 뽑은 과제가 직접 뽑은 과제와 같은 분포인지 · 표 밖 시작은 옛 꼴 · 길 계산 캐시가 옛 계산과 같은 길을 내는지. CPU · Kit 없음."""
from pathlib import Path

import numpy as np

from foothold_s2.nav import grade_map as gm, gvd_astar, nav_task, room_generator as rg

TABLE = gm.load_grade_table(str(Path(__file__).resolve().parents[1] / "nav" / "grade_table_draft.yaml"))
CFG = rg.RoomConfig(sparse_patch_kinds=())


def _setup(n_rooms=2, k=8):
    rooms = [rg.make_room(1000 + i, CFG)[1] for i in range(n_rooms)]
    assets = [nav_task.make_asset(r, TABLE) for r in rooms]
    starts = [rg.start_points(r, k, seed=1000 + i)[:, :2] for i, r in enumerate(rooms)]
    return rooms, assets, starts


def _draw(task, starts, n):
    ids = np.arange(n)
    s = np.stack([starts[task.room_id[i]][i % len(starts[task.room_id[i]])] for i in ids])
    task.reset_envs(ids, start_xy=s)
    lens = np.array([task._length(p) for p in task.path])
    ratio = lens / np.linalg.norm(task.goal - task.start, axis=1)
    return s, lens, ratio


def test_table_draws_match_live_draws_in_length_and_winding_and_keep_the_start():
    _rooms, assets, starts = _setup()
    n = 64
    live = nav_task.NavTask(assets, n, np.random.default_rng(1))
    tab = nav_task.NavTask(assets, n, np.random.default_rng(1))
    sha = tab.build_table(starts, per_start=24, seed=3)
    assert len(sha) == 64 and tab.build_table(starts, per_start=24, seed=3) == sha          # 같은 시드 = 같은 표
    s0, l0, r0 = _draw(live, starts, n)
    s1, l1, r1 = _draw(tab, starts, n)
    assert tab.task_table_hits == n and tab.task_table_miss == 0 and live.task_table_hits == 0
    assert np.allclose(s1, tab.start) and all(np.allclose(p[0], tab.start[i]) and np.allclose(p[-1], tab.goal[i]) for i, p in enumerate(tab.path))
    assert ((l1 >= 4.0) & (l1 <= 25.0)).mean() >= 0.95
    assert abs(np.median(l1) - np.median(l0)) <= 0.2 * np.median(l0)
    assert abs((r1 >= 1.2).mean() - tab.winding_frac) <= 0.2                                  # 표에서는 굴곡 쌍 비율이 winding_frac (0.5) 근처
    assert tab.task_winding == int((r1 >= 1.2).sum()) and tab.task_new == n


def test_start_off_the_table_falls_back_to_live_planning():
    _rooms, assets, starts = _setup(n_rooms=1, k=4)
    t = nav_task.NavTask(assets, 1, np.random.default_rng(2))
    t.build_table(starts, per_start=16, seed=0, tol_m=0.1)
    near = starts[0][0] + np.array([0.05, 0.0])
    far = starts[0][1] + np.array([0.0, 0.0])
    t.reset_envs([0], start_xy=near[None])
    assert t.task_table_hits == 1
    t.pgcl[0].needs_new_task = True
    # 표의 시작점에서 0.1 m 보다 먼 자리 (같은 방의 다른 평지 칸)
    g = assets[0].grade
    cand = gm.sample_free_points(g, np.random.default_rng(5), 50)
    off = [c for c in cand if np.linalg.norm(starts[0] - c, axis=1).min() > 1.0][0]
    t.reset_envs([0], start_xy=off[None])
    assert t.task_table_miss == 1 and np.allclose(t.start[0], off) and t.path[0] is not None


def test_cached_find_path_matches_uncached_and_is_not_stale_after_the_grid_changes():
    rooms, assets, _ = _setup(n_rooms=1)
    g = assets[0].grade
    rng = np.random.default_rng(4)
    gvd_astar._CACHE = False
    try:
        pts = [gm.sample_free_points(g, rng, 2) for _ in range(4)]
        ref = [gvd_astar.find_path(g, a, b, straighten=True) for a, b in pts]
    finally:
        gvd_astar._CACHE = True
    for (a, b), r in zip(pts, ref):
        c = gvd_astar.find_path(g, a, b, straighten=True)
        assert c.found == r.found and (not r.found or (np.allclose(c.points, r.points, atol=1e-6) and abs(c.length_m - r.length_m) < 1e-4))
    st1 = gvd_astar._static(g, gvd_astar.RAMP_M, None)
    assert gvd_astar._static(g, gvd_astar.RAMP_M, None) is st1                                # 같은 방 = 같은 정적 값 (한 번만 계산)
    g.grade[90:110, :] = gm.BLOCKED; g.cost[90:110, :] = np.inf                                # 격자가 바뀌면 지문이 달라 캐시를 다시 만든다 (낡은 길을 안 낸다)
    st2 = gvd_astar._static(g, gvd_astar.RAMP_M, None)
    assert st2 is not st1 and st2["fp"] != st1["fp"]


def test_continuing_task_reset_uses_the_table_and_vectorized_subgoal_samples_match():
    from foothold_s2.nav import pgcl
    _rooms, assets, starts = _setup(n_rooms=1, k=4)
    t = nav_task.NavTask(assets, 1, np.random.default_rng(5))
    t.build_table(starts, per_start=16, seed=0)
    t.redraw_on_fall = True                                             # the 02:2x behaviour (cfg task_redraw_on_fall)
    t.reset_envs([0], start_xy=starts[0][0][None])
    live_before = t.task_table_hits
    t.pgcl[0].needs_new_task = False                                  # 넘어짐: 과제는 이어 쓰는 경우
    t.reset_envs([0], start_xy=starts[0][1][None])
    assert t.task_redraw_on_reset == 1 and t.task_table_hits == live_before + 1 and t.task_table_miss == 0
    P = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 2.0], [3.0, 2.0]])      # 길이 0 구간 포함
    arc = pgcl._arc(P); ss = np.linspace(-0.5, arc[-1] + 0.5, 57)
    assert np.allclose(pgcl._at_many(P, arc, ss), np.array([pgcl._at(P, arc, s) for s in ss]), atol=1e-12)


def test_default_table_radius_covers_the_isaac_reset_jitter_square():
    _rooms, assets, starts = _setup(n_rooms=1, k=4)
    t = nav_task.NavTask(assets, 1, np.random.default_rng(3))
    t.build_table(starts, per_start=16, seed=0)
    assert t.table_tol_m >= 0.71                                       # reset_base x y U(-0.5, 0.5): the corner is 0.707 m from the origin (a table start)


def _state(n, pos, applied_vx=0.5, vel=0.0, done=None):
    from foothold_s2.nav.nav_env import NavState
    z = lambda *s: np.zeros(s)
    return NavState(pos_w=np.c_[pos, np.full(n, 0.35)], quat_w=np.tile([1.0, 0, 0, 0], (n, 1)), pos_local=np.c_[pos, np.full(n, 0.35)], vel_b=np.c_[np.full(n, vel), z(n, 2)],
                    yaw_rate=z(n), applied=np.tile([applied_vx, 0, 0, 0, 0], (n, 1)), stand=np.zeros(n, bool), modified=np.zeros(n, bool), track_err=z(5, n, 3),
                    done=np.zeros(n, bool) if done is None else done, done_step=np.full(n, -1), timed_out=np.zeros(n, bool), ang_vel_b=z(n, 3), q=z(n, 12), q0=z(12),
                    proprio=z(n, 45), collision=np.zeros(n, bool))


def test_same_goal_retry_after_a_fall_keeps_the_goal_and_uses_the_table_path(monkeypatch):
    _rooms, assets, starts = _setup(n_rooms=1, k=4)
    t = nav_task.NavTask(assets, 1, np.random.default_rng(5))
    t.build_table(starts, per_start=16, seed=0)
    t.redraw_on_fall = False
    t.reset_envs([0], start_xy=starts[0][0][None])
    goal = t.goal[0].copy()
    monkeypatch.setattr(t, "_plan", lambda *a, **k: (_ for _ in ()).throw(AssertionError("A* must not run")))
    t.reset_envs([0], start_xy=(starts[0][0] + np.array([0.3, -0.2]))[None])        # a fall: the same task, a jittered start
    assert np.allclose(t.goal[0], goal) and t.task_redraw_on_reset == 0 and np.allclose(t.path[0][-1], goal)


def test_iteration_stats_count_subgoals_levels_outcomes_rewards_speeds_and_episode_ends():
    _rooms, assets, starts = _setup(n_rooms=1, k=4)
    n = 4
    t = nav_task.NavTask(assets, n, np.random.default_rng(9))
    t.build_table(starts, per_start=16, seed=0)
    t.tick_s = 0.5
    st0 = np.stack([starts[0][i % 4] for i in range(n)])
    t.reset_envs(np.arange(n), start_xy=st0)
    pos = st0.copy()
    for k in range(3):
        t.step(_state(n, pos, vel=0.0))
    done = np.array([True, False, False, False])
    t.step(_state(n, pos, done=done))
    t.reset_envs([0], start_xy=st0[:1])
    s = t.take_stats()
    assert s["nv_episodes"] == 1 and s["nv_out_hold"] == 1 and s["nv_stand_frac"] == 1.0 and s["nv_v_body"] == 0.0
    assert abs(s["nv_v_cmd"] - 0.5) < 1e-9 and abs(s["nv_lvl1"] - 1.0) < 1e-9 and s["nv_progress_end"] == 0.0
    assert s["nv_ep_ticks"] == 4 and s["nv_ep_s"] == 2.0 and s["nv_dsub_start"] > 0 and s["nv_path_len"] >= 4.0 and "nv_r1" in s
    assert t.take_stats() == {}                                                       # read and cleared


def test_default_keeps_the_same_task_and_path_across_a_fall_and_the_level_follows_pgcl():
    _rooms, assets, starts = _setup(n_rooms=1, k=4)
    t = nav_task.NavTask(assets, 1, np.random.default_rng(5))
    t.build_table(starts, per_start=16, seed=0)
    assert t.redraw_on_fall is False
    t.reset_envs([0], start_xy=starts[0][0][None])
    goal, path = t.goal[0].copy(), t.path[0].copy()
    new0 = t.task_new
    out = t.reset_envs([0], start_xy=starts[0][0][None])                       # fall: the body is back on the task start
    assert out["outcome"] == ["hold"] and t.task_new == new0 and np.allclose(t.goal[0], goal) and np.allclose(t.path[0], path)
    t.pgcl[0]._i = len(t.pgcl[0]._sub)                                          # every subgoal reached
    out = t.reset_envs([0], start_xy=starts[0][0][None])
    assert out["outcome"] == ["level_up"] and t.pgcl[0].level == 2 and np.allclose(t.goal[0], goal) and t.task_new == new0


def test_episode_seconds_is_path_length_over_0_3_plus_10():
    _rooms, assets, starts = _setup(n_rooms=1, k=4)
    t = nav_task.NavTask(assets, 2, np.random.default_rng(6))
    t.build_table(starts, per_start=16, seed=0)
    assert np.allclose(t.episode_seconds([0, 1]), 90.0)                         # no task yet: fixed 90 s
    t.reset_envs([0, 1], start_xy=np.stack([starts[0][0], starts[0][1]]))
    sec = t.episode_seconds([0, 1])
    for k in range(2):
        L = float(np.linalg.norm(np.diff(t.path[k], axis=0), axis=1).sum())
        assert abs(sec[k] - (L / 0.3 + 10.0)) < 1e-9 and 10 + 4 / 0.3 - 1e-9 <= sec[k] <= 10 + 25 / 0.3 + 1e-9
