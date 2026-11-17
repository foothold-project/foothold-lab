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
