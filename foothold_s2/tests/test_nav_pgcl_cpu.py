import numpy as np
import pytest

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import pgcl


def _line(L=10.0, y=5.0, x0=1.0):
    return np.array([[x0, y], [x0 + L, y]])


def test_subgoal_count_is_ceil_of_length_over_d_and_last_is_the_goal():
    for d, expect in ((1.0, 10), (3.0, 4), (4.0, 3), (10.0, 1), (11.0, 1)):
        sg = pgcl.path_subgoals(_line(10.0), d)
        assert len(sg) == expect, d
        assert sg[-1].kind == "goal" and np.allclose(sg[-1].point, (11.0, 5.0))
    sg = pgcl.path_subgoals(_line(10.0), 3.0)
    assert [round(s.point[0], 3) for s in sg] == [4.0, 7.0, 10.0, 11.0]


def test_bent_path_uses_arc_length():
    P = np.array([[0.0, 0.0], [3.0, 0.0], [3.0, 4.0]])             # L = 7
    sg = pgcl.path_subgoals(P, 5.0)
    assert len(sg) == 2 and np.allclose(sg[0].point, (3.0, 2.0)) and np.allclose(sg[1].point, (3.0, 4.0))


def _sparse_map():
    n = 100
    grade = np.zeros((n, n), np.uint8)
    grade[40:60, :] = gm.SPARSE                                     # x 4~6 m 띠
    z = np.zeros((n, n), np.float32)
    return gm.GradeMap(grade, np.ones((n, n), np.float32), z, z, False, "x", 0.1)


def test_entry_subgoals_sit_on_the_path_axis_before_the_band():
    g = _sparse_map()
    sg = pgcl.path_subgoals(_line(8.0, y=5.0, x0=1.0), 4.0, g)
    kinds = [s.kind for s in sg]
    assert kinds.count("entry") == 1 and kinds.count("entry_before") == 1
    e = next(s for s in sg if s.kind == "entry"); b = next(s for s in sg if s.kind == "entry_before")
    assert e.point[0] == pytest.approx(4.0, abs=0.1) and b.point[0] == pytest.approx(e.point[0] - 0.5, abs=0.02)
    assert e.point[1] == pytest.approx(5.0) and b.point[1] == pytest.approx(5.0)
    assert [s.s for s in sg] == sorted(s.s for s in sg) and kinds[-1] == "goal"


def test_no_entry_subgoal_when_the_path_never_enters_a_band():
    g = _sparse_map()
    assert all(s.kind in ("path", "goal") for s in pgcl.path_subgoals(_line(2.0, y=5.0, x0=1.0), 1.0, g))


def test_level_goes_up_only_after_every_subgoal_is_reached_in_order():
    p = pgcl.PGCL()
    sub = p.start_episode(_line(10.0))
    assert len(sub) == 10 and p.level == 1 and p.d == 1.0
    for s in sub:
        assert p.target == s
        p.update(s.point)
    assert p.all_reached and p.end_episode() == "level_up" and p.level == 2 and p.d == 2.0
    assert len(p.start_episode(_line(10.0))) == 5


def test_a_missed_subgoal_keeps_the_level_and_skipping_ahead_does_not_count():
    p = pgcl.PGCL()
    sub = p.start_episode(_line(10.0))
    p.update(sub[1].point)                                          # 첫 부목표를 건너뛴 도달
    assert p.target == sub[0] and not p.all_reached
    p.update(sub[0].point); p.update(sub[1].point)
    assert p.target == sub[2]
    assert p.end_episode() == "hold" and p.level == 1


def test_reach_radius_is_a_tenth_of_a_metre():
    p = pgcl.PGCL()
    sub = p.start_episode(_line(10.0))
    p.update((sub[0].point[0] + 0.11, 5.0)); assert p.target == sub[0]
    p.update((sub[0].point[0] + 0.09, 5.0)); assert p.target == sub[1]


def test_final_level_shows_only_the_goal_and_five_successes_request_a_new_task():
    p = pgcl.PGCL()
    p.level = 11                                                    # d = 11 m >= 10 m
    sub = p.start_episode(_line(10.0))
    assert p.is_final and [s.kind for s in sub] == ["goal"]
    out = []
    for _ in range(5):                                              # 22 §4 표의 가정: 연속 5 회 (계획 v2 는 3 으로 적음, PR 본문에 충돌 기록)
        p.start_episode(_line(10.0)); p.update((11.0, 5.0)); out.append(p.end_episode())
    assert out == ["final_success"] * 4 + ["new_task"] and p.needs_new_task and p.streak == 0
    p.start_episode(_line(10.0))
    assert not p.needs_new_task


def test_a_failure_in_the_final_level_resets_the_streak():
    p = pgcl.PGCL(); p.level = 11
    for _ in range(4):
        p.start_episode(_line(10.0)); p.update((11.0, 5.0)); p.end_episode()
    assert p.streak == 4
    p.start_episode(_line(10.0))
    assert p.end_episode() == "hold" and p.streak == 0


def test_bad_inputs_are_refused():
    with pytest.raises(ValueError):
        pgcl.path_subgoals(np.array([[0.0, 0.0]]), 1.0)
    with pytest.raises(ValueError):
        pgcl.path_subgoals(_line(), 0.0)
    with pytest.raises(ValueError):
        pgcl.PGCL(final_successes=0)
