"""HiPAN P3 몸 폭 여유 스위치 (HIPAN_PATH_CLEAR_M · lead 11/22 02:42 · 기본 꺼짐). 실제 방 · 실제 NavTask. CPU only."""
from __future__ import annotations

import numpy as np
import pytest

from foothold_s2.nav import grade_map as gm, kit_factories as kf, room_generator as rg


def test_switch_parse():
    assert kf.path_clear_m({}) == 0.0 and kf.path_clear_m({"HIPAN_PATH_CLEAR_M": "0"}) == 0.0
    assert kf.path_clear_m({"HIPAN_PATH_CLEAR_M": "0.25"}) == 0.25
    for bad in ("-0.1", "0.7", "x"):
        with pytest.raises(ValueError):
            kf.path_clear_m({"HIPAN_PATH_CLEAR_M": bad})


def test_body_grade_shuts_near_walls_not_pits():
    room = rg.make_room(1001)[1]
    g = gm.make_grade_map(room, gm.load_grade_table(kf.__file__.replace("kit_factories.py", "grade_table_draft.yaml")))
    b = gm.body_clear_grade(g, room, 0.25)
    from scipy import ndimage
    src = (g.grade == gm.BLOCKED) & ~np.isin(room.cell, gm.BODY_SOURCE_PITS)
    d = ndimage.distance_transform_edt(~src) * g.res
    newly = (b.grade == gm.BLOCKED) & (g.grade != gm.BLOCKED)
    assert newly.any() and (d[newly] < 0.25).all()                       # 막힌 칸은 벽 · 막힌 칸 둘레만
    assert ((b.grade == gm.BLOCKED) | (d < 0.25) | (g.grade == b.grade)).all()
    assert np.isinf(b.cost[newly]).all() and (g.grade[g.grade == gm.BLOCKED] == gm.BLOCKED).all()
    assert b is not g and g.grade is not b.grade                           # 원래 등급 지도는 그대로


def test_fresh_tasks_paths_keep_body_clearance(tmp_path, monkeypatch):
    from foothold_s2.nav import p2_task_dist as pd
    monkeypatch.setenv("HIPAN_PATH_CLEAR_M", "0.25")
    task, env_start, _s, _nf = pd.build("on", 96, tmp_path)
    kf.apply_path_clear(task, task.assets, kf.path_clear_m())
    rng = np.random.default_rng(0); mins = []
    for _ in range(40):
        i = int(rng.integers(len(env_start)))
        task._new_task(i, env_start[i])
        mins.append(task._path_facts(i)["min_clear_m"])
    assert min(mins) >= 0.2 and task.task_fallbacks == 0                   # 끔이면 0.10 이하가 절반 (p3_clear_dist 실측)
