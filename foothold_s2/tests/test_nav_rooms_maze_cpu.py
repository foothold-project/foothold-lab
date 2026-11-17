"""HiPAN 길과 벽 방 (DESIGN-HIPAN-ROOMS-1117): 답을 아는 방 · 막다른 타일 · 통과 폭 · 곧게 펴기 · 목표 뽑기 · 시작점 방향 · 검사 도구. CPU · Kit 없음."""
from pathlib import Path

import numpy as np

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import gvd_astar, nav_task, room_check, room_generator as rg

TABLE = gm.load_grade_table(str(Path(__file__).resolve().parents[1] / "nav" / "grade_table_draft.yaml"))
CFG = rg.RoomConfig(sparse_patch_kinds=())


def test_grid_shortest_over_straight_matches_a_hand_computed_wall_with_one_gap():
    free = np.ones((100, 100), bool)
    free[50, :90] = False                                          # 줄 50 에 벽 · 열 90~99 (1 m) 만 틈
    graph, node = room_check.grid_graph(free)
    from scipy.sparse.csgraph import dijkstra

    d = dijkstra(graph, directed=False, indices=node[10, 10])[node[90, 10]] * 0.1
    straight = 8.0
    # 손 계산: (10,10) -> 틈 (50,90) 근처 -> (90,10). 팔방 최단 = max + (sqrt2 - 1) min 이 한 구간 약 96.6 칸 · 둘 합 약 19.3 m · 틈 모서리에서 조금 더
    assert 2.40 < d / straight < 2.46
    straight_free = np.ones((100, 100), bool)
    g2, n2 = room_check.grid_graph(straight_free)
    d2 = dijkstra(g2, directed=False, indices=n2[10, 10])[n2[90, 10]] * 0.1
    assert abs(d2 - 8.0) < 1e-6                                    # 막힌 데 없이 같은 줄이면 직선


def test_dead_end_tiles_counts_tiles_with_exactly_one_open_neighbour():
    blocked = [[i, j] for i in range(rg.NT) for j in range(rg.NT) if not (i == 0 and j < 3)]        # 자유 타일은 (0,0) (0,1) (0,2) 한 줄
    spec = {"maze": {"blocked": blocked, "edges": []}}
    assert rg.dead_end_tiles(spec) == 2                                                              # 양 끝만 (가운데는 이웃 둘)
    spec["maze"]["edges"] = [[0, 1, 0, 1, False]]                                                    # (0,1)-(0,2) 사이를 문 없는 벽으로 닫음
    assert rg.dead_end_tiles(spec) == 2                                                              # (0,0) · (0,1) 이웃 하나 · (0,2) 는 0 (고립이라 막다른 길이 아님)
    spec["maze"]["edges"] = [[0, 1, 0, 1, True]]                                                     # 문이 있으면 열린 것
    assert rg.dead_end_tiles(spec) == 2
    assert rg.dead_end_tiles({"seed": 0}) == 0                                                       # maze 명세가 없으면 0


def test_passage_width_sees_a_narrow_door():
    n = rg.N
    free = np.ones((n, n), bool)
    free[:, 100] = False
    free[95:105, 100] = True                                                                         # 문 1.0 m (10 칸)
    assert rg.passage_width_m(free) >= 0.8
    free[95:105, 100] = False
    free[98:103, 100] = True                                                                         # 문 0.5 m (5 칸)
    assert rg.passage_width_m(free) < 0.8


def test_maze_rooms_meet_the_per_room_lines_and_the_starts_are_on_flat_free_cells():
    for seed in (1000, 1001, 1002, 1003, 1004, 1005):
        spec, room = rg.make_room(seed, CFG)
        m = spec["metrics"]
        assert 0.55 <= m["free_frac"] <= 0.80 and m["connected_frac"] >= 0.98 and m["dead_end_tiles"] >= 3 and m["passage_m"] >= 0.8
        assert spec["maze"]["wall_keep"] == CFG.keep_choices[seed % 3] and spec["outer_wall_m"] == rg.MAZE_OUTER_WALL_M
        starts = rg.start_points(room, 64, seed)
        ij = np.floor(starts[:, :2] / rg.RES).astype(int)                                           # 배열은 [x 칸][y 칸]
        assert (room.cell[ij[:, 0], ij[:, 1]] == rg.CELL_FLAT).all()
        assert (np.abs(starts[:, :2] - rg.ROOM_M / 2) < rg.ROOM_M / 2 - rg.MAZE_OUTER_WALL_M).all()
        grade = gm.make_grade_map(room, TABLE)
        assert gm.largest_component_mask(gm.passable(grade))[ij[:, 0], ij[:, 1]].all()


def test_old_layout_is_still_available_and_unchanged_in_kind():
    spec = rg.generate_spec(3, rg.RoomConfig(layout="old", sparse_patch_kinds=()))
    assert "maze" not in spec and spec["primitives"] and "outer_wall_m" not in spec


def test_straightening_cuts_the_voronoi_detour_in_an_empty_room_but_never_the_wall():
    empty = rg.build_room({"seed": 0, "size_m": 20.0, "tiles": None, "primitives": []})
    g = gm.make_grade_map(empty, TABLE)
    a, b = (3.0, 3.0), (17.0, 15.0)
    raw, st = gvd_astar.find_path(g, a, b), gvd_astar.find_path(g, a, b, straighten=True)
    straight = float(np.hypot(14.0, 12.0))
    assert st.length_m <= straight * 1.03 and st.length_m <= raw.length_m + 1e-9
    assert np.allclose(st.points[0], a) and np.allclose(st.points[-1], b)
    walled = rg.build_room({"seed": 0, "size_m": 20.0, "tiles": None, "primitives": [{"type": "wall", "x0": 9.9, "y0": 0.0, "x1": 10.1, "y1": 14.0, "h": 1.2}]})
    gw = gm.make_grade_map(walled, TABLE)
    p = gvd_astar.find_path(gw, (3.0, 3.0), (17.0, 3.0), straighten=True)
    assert p.found and p.length_m > 14.0 * 1.3                                                      # 벽 위를 지나는 직선으로 깎이지 않는다 (14 m 직선이 아니라 벽 끝을 돈다)
    from scipy import ndimage

    dist = ndimage.distance_transform_edt(gw.grade != gm.BLOCKED) * gw.res
    for q0, q1 in zip(p.points[:-1], p.points[1:]):
        for k in range(21):
            xy = q0 + (q1 - q0) * k / 20
            c = (xy / gw.res).astype(int)
            assert gw.grade[c[0], c[1]] != gm.BLOCKED and dist[c[0], c[1]] >= min(gvd_astar.MIN_CLEAR_M, float(dist[int(a[0] / gw.res), int(a[1] / gw.res)])) - 0.06


def test_nav_task_draws_goals_by_path_length_and_half_from_winding_pairs():
    rooms = [rg.make_room(s, CFG)[1] for s in (1000, 1001)]
    assets = [nav_task.make_asset(r, TABLE) for r in rooms]
    n = 64
    t = nav_task.NavTask(assets, n, np.random.default_rng(0))
    starts = np.concatenate([rg.start_points(rooms[i % 2], 1, seed=i)[:, :2] for i in range(n)])
    t.reset_envs(np.arange(n), start_xy=starts)
    lens = np.array([float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) for p in t.path])
    ratios = lens / np.linalg.norm(t.goal - t.start, axis=1)
    assert t.task_new == n and int(t.ratio_hist.sum()) == n and t.task_winding == int((ratios >= 1.2).sum())
    assert t.task_fallbacks == 0
    assert ((lens >= 4.0) & (lens <= 25.0)).mean() >= 0.9                                           # 물러선 과제 (task_relaxed) 를 빼고는 경로 길이 4~25 m
    assert t.task_winding >= 0.3 * n                                                                 # 절반을 굴곡 쌍에서 뽑으려 시도 (맞는 후보가 없으면 물러서므로 하한만)


def test_room_check_judges_a_small_bundle_and_is_nonzero_when_a_line_fails(tmp_path):
    rc = room_check.main(["--count", "3", "--seed0", "1000", "--out", str(tmp_path), "--figure-seeds", "", "--planner-pairs", "4"])
    assert rc in (0, 1) and (tmp_path / "rooms_judge.md").exists() and (tmp_path / "rooms_judge.json").exists()
    res = room_check.judge([room_check.check_room(s, CFG, TABLE, np.random.default_rng(1), 3, 5, 3) for s in (1000, 1001)])
    assert len(res["lines"]) == 8
    res["lines"][0]["pass"] = False
    assert not all(l["pass"] for l in res["lines"])
