from pathlib import Path

import numpy as np
import pytest

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import nav_score as ns
from foothold_s2.nav import room_generator as rg

NAV = Path(__file__).resolve().parents[1] / "nav"
TABLE = gm.load_grade_table(NAV / "grade_table_draft.yaml")


def _named(name, pose=False):
    return gm.make_grade_map(rg.build_room(rg.load_spec(NAV / "rooms" / f"{name}.yaml")), TABLE, pose)


def _empty():
    return gm.make_grade_map(rg.build_room({"seed": 0, "size_m": 20.0, "primitives": []}), TABLE)


def test_shortest_length_hand_values_on_an_empty_room():
    g = _empty()
    assert ns.shortest_length(g, (5.05, 10.05), (15.05, 10.05)) == pytest.approx(10.0)             # 직선 10 m
    assert ns.shortest_length(g, (5.05, 5.05), (15.05, 15.05)) == pytest.approx(10.0 * np.sqrt(2))  # 대각 14.14 m


def test_shortest_length_follows_walls_gaps_and_stone_jumps():
    wall = ns.shortest_length(_named("known_wall"), (5.05, 5.05), (15.05, 5.05))
    assert wall > 14.0                                                                              # 벽을 돌아감
    assert np.isinf(ns.shortest_length(_named("known_gap09"), (5.05, 10.05), (15.05, 10.05)))       # 0.9 m 틈은 못 건넘
    assert ns.shortest_length(_named("known_gap05"), (5.05, 10.05), (15.05, 10.05)) == pytest.approx(10.0, abs=0.2)
    stones = ns.shortest_length(_named("known_cross_stepping_stones_low"), (5.05, 10.05), (15.05, 10.05))
    assert 10.0 - 1e-9 <= stones < 12.0                                                                    # 건너뛰기 간선으로 건넘
    assert np.isinf(ns.shortest_length(_named("known_cross_stepping_stones_low"), (5.05, 10.05), (15.05, 10.05), stride_m=0.1))


def test_blocked_start_is_refused():
    with pytest.raises(ValueError):
        ns.geodesic_map(_named("known_wall"), (10.0, 5.0))                                          # 벽 위


def test_score_episode_hand_values():
    ok = ns.score_episode([[0, 0], [5, 0], [10, 0], [12.5, 0], [12.5, 0.1]], (12.5, 0.15), shortest_m=10.0, collisions=2)
    assert ok["success"] and ok["length_m"] == pytest.approx(12.6) and ok["spl"] == pytest.approx(10.0 / 12.6) and ok["collisions"] == 2
    miss = ns.score_episode([[0, 0], [10, 0]], (10.0, 0.5), 10.0)
    assert not miss["success"] and miss["spl"] == 0.0
    edge_in = ns.score_episode([[0, 0], [10, 0]], (10.19, 0.0), 10.0)
    edge_out = ns.score_episode([[0, 0], [10, 0]], (10.21, 0.0), 10.0)
    assert edge_in["success"] and not edge_out["success"]                                           # 0.2 m 문턱
    shorter = ns.score_episode([[0, 0], [9.9, 0]], (9.9, 0.0), 10.0)
    assert shorter["spl"] == 1.0                                                                    # 최단보다 짧게 나와도 1 로 자름
    with pytest.raises(ValueError):
        ns.score_episode([[0, 0]], (0, 0), 0.0)
    with pytest.raises(ValueError):
        ns.score_episode([], (0, 0), 1.0)


def test_aggregate_sr_spl_collisions_bands_and_sparse_beyond():
    tasks = [ns.Task((0, 0), (1, 1), 5.0, 0, False), ns.Task((0, 0), (1, 1), 5.0, 0, True),
             ns.Task((0, 0), (1, 1), 10.0, 1, False), ns.Task((0, 0), (1, 1), 20.0, 2, True)]
    eps = [{"success": True, "spl": 0.8, "collisions": 0}, {"success": False, "spl": 0.0, "collisions": 4},
           {"success": True, "spl": 0.6, "collisions": 2}, {"success": True, "spl": 1.0, "collisions": 2}]
    a = ns.aggregate(eps, tasks)
    assert a["sr"] == 0.75 and a["spl"] == pytest.approx(0.6) and a["collisions"] == 2.0
    assert a["sr_by_band"] == {0: 0.5, 1: 1.0, 2: 1.0}
    assert a["sr_sparse_beyond"] == 0.5 and a["n_sparse_beyond"] == 2
    with pytest.raises(ValueError):
        ns.aggregate([])
    with pytest.raises(ValueError):
        ns.aggregate(eps, tasks[:2])


def test_tasks_are_reproducible_in_their_bands_and_reachable():
    g = gm.make_grade_map(rg.build_room(rg.load_spec(NAV / "rooms" / "bench_room.yaml")), TABLE)
    a = ns.make_tasks(g, np.random.default_rng(1), per_band=4)
    b = ns.make_tasks(g, np.random.default_rng(1), per_band=4)
    assert [(t.start, t.goal) for t in a] == [(t.start, t.goal) for t in b] and len(a) == 12
    for band, (lo, hi) in enumerate(ns.DISTANCE_BANDS_M):
        mine = [t for t in a if t.band == band]
        assert len(mine) == 4
        for t in mine:
            assert lo <= t.shortest_m < hi and np.isclose(ns.shortest_length(g, t.start, t.goal), t.shortest_m, atol=0.15)
            assert g.grade[tuple((np.array(t.start) / g.res).astype(int))] != gm.BLOCKED
    assert [(t.start, t.goal) for t in a] != [(t.start, t.goal) for t in ns.make_tasks(g, np.random.default_rng(2), per_band=4)]


def test_the_full_benchmark_is_three_bands_of_one_hundred():
    g = gm.make_grade_map(rg.build_room(rg.load_spec(NAV / "rooms" / "bench_room.yaml")), TABLE)
    tasks = ns.make_tasks(g, np.random.default_rng(0))
    assert len(tasks) == 300 and [sum(t.band == b for t in tasks) for b in range(3)] == [100, 100, 100]


def test_a_goal_that_needs_a_sparse_crossing_is_flagged():
    g = _named("known_cross_stepping_stones_low")
    tasks = ns.make_tasks(g, np.random.default_rng(0), per_band=2, bands=((3.0, 40.0),))
    for t in tasks:
        across = (t.start[0] < 7.0) != (t.goal[0] < 7.0) or (t.start[0] > 13.0) != (t.goal[0] > 13.0)
        assert t.needs_sparse == across


def test_too_small_a_room_is_refused_instead_of_returning_fewer_tasks():
    g = _named("known_wall")
    with pytest.raises(RuntimeError):
        ns.make_tasks(g, np.random.default_rng(0), per_band=2, bands=((60.0, 80.0),))


def test_pgcl_gate_and_modified_fraction():
    assert ns.pgcl_gate(0.984, 0.769) and not ns.pgcl_gate(0.95, 0.94)
    assert ns.modified_fraction([True, False, False, True]) == 0.5 and ns.modified_fraction([]) == 0.0
