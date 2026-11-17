"""G3 첫 Pod (env 1024 · 방 6 · 시작점 64) 에서 시작 위치가 길 없는 칸이라 NavTask 가 학습을 죽였다: 이제 새 쌍으로 대신하고 센다."""
from pathlib import Path

import numpy as np

from foothold_s2.nav import grade_map as gm, nav_task, room_generator as rg

TABLE = Path(__file__).resolve().parents[1] / "nav" / "grade_table_draft.yaml"


def _task(room_seed):
    room = rg.make_room(room_seed)[1]
    return nav_task.NavTask([nav_task.make_asset(room, gm.load_grade_table(str(TABLE)))], 1, np.random.default_rng(0))


def test_a_start_with_no_path_falls_back_to_a_free_pair_and_is_counted():
    t = _task(1004)                                              # 이 방의 이 위치는 G3 첫 Pod 와 같은 시드 · 같은 막힌 시작점 (로컬 재현에서 확인)
    t._new_task(0, np.array([10.95, 17.05]))
    assert t.task_fallbacks == 1 and t.path[0] is not None and len(t.path[0]) >= 2


def test_a_good_start_does_not_fall_back_and_a_free_pair_start_still_raises_when_nothing_works():
    t = _task(1004)
    t._new_task(0)                                               # 시작도 이 층이 뽑는 옛 꼴
    assert t.task_fallbacks == 0
    t.max_task_tries = 1; t.min_task_m = 1e9                     # 어떤 쌍도 안 되게 하면 옛 꼴은 여전히 예외
    import pytest
    with pytest.raises(RuntimeError, match="no start/goal"):
        t._new_task(0)
