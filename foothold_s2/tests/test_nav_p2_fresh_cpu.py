"""HiPAN P2 과제 분포 스위치 (HIPAN_FRESH_TASKS · lead 11/22 01:28). 실제 방 · 실제 NavTask._new_task. CPU only."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from foothold_s2.nav import kit_factories as kf

ROOT = Path(__file__).resolve().parents[2]


def test_switch_parse_and_fail_cut(monkeypatch):
    monkeypatch.delenv("HIPAN_FRESH_TASKS", raising=False)
    assert kf.fresh_tasks() is False
    assert kf.new_task_after_fails({}, {"HIPAN_NEW_TASK_AFTER_FAILS": "5"}) == 5                       # 끔: m2000 조건 그대로
    assert kf.new_task_after_fails({}, {"HIPAN_NEW_TASK_AFTER_FAILS": "5", "HIPAN_FRESH_TASKS": "1"}) == 0   # 켬: 자르기 끔
    with pytest.raises(ValueError):
        kf.fresh_tasks({"HIPAN_FRESH_TASKS": "yes"})


def test_fresh_draws_from_the_real_rooms_keep_range_winding_and_no_repeats(tmp_path, monkeypatch):
    from foothold_s2.nav import p2_task_dist as pd
    task, env_start, _s, nf = pd.build("on", 96, tmp_path)
    assert task.table is None and nf == 0 and task.strict_winding and tuple(task.path_range_m) == kf.FRESH_PATH_RANGE_M
    rec, _t = pd.draw(task, env_start, 200)
    s = pd.summarize(rec, _t)
    assert s["repeat_pair_frac"] == 0.0 and s["path_bins_m"]["0-5"] == 0.0 and s["path_bins_m"]["30-999"] == 0.0
    assert 0.3 <= s["wind_ge_1.2"] <= 0.6


def test_off_keeps_the_m2000_table_rule():
    src = (ROOT / "foothold_s2/nav/kit_factories.py").read_text(encoding="utf-8")
    assert 'per_start = 0 if fresh else int(cfg.get("task_table_per_start", 32))' in src and "task.path_range_m, task.strict_winding = FRESH_PATH_RANGE_M, True" in src


def test_p2v2_keep_cut_and_final_successes():
    """P2 2차: HIPAN_FRESH_NO_CUT=0 이면 켬이어도 자르기 5 유지 · HIPAN_FINAL_SUCCESSES 로 마지막 수준 연속 성공 수 (실제 PGCL 이 그 수에서 새 과제 요청)."""
    on = {"HIPAN_NEW_TASK_AFTER_FAILS": "5", "HIPAN_FRESH_TASKS": "1"}
    assert kf.new_task_after_fails({}, on) == 0                                   # 1차 판 그대로 (스위치 없음)
    assert kf.new_task_after_fails({}, dict(on, HIPAN_FRESH_NO_CUT="1")) == 0
    assert kf.new_task_after_fails({}, dict(on, HIPAN_FRESH_NO_CUT="0")) == 5    # 갈래 A · B
    assert kf.new_task_after_fails({}, {"HIPAN_NEW_TASK_AFTER_FAILS": "5", "HIPAN_FRESH_NO_CUT": "0"}) == 5
    with pytest.raises(ValueError):
        kf.fresh_no_cut({"HIPAN_FRESH_NO_CUT": "2"})
    assert kf.final_successes({}) == 5 and kf.final_successes({"HIPAN_FINAL_SUCCESSES": "1"}) == 1
    for bad in ("0", "-1", "x"):
        with pytest.raises(ValueError):
            kf.final_successes({"HIPAN_FINAL_SUCCESSES": bad})
    from foothold_s2.nav import pgcl
    p = pgcl.PGCL(final_successes=5)
    p.final_successes = 1
    p.start_episode([[0.0, 0.0], [3.0, 0.0]])
    p.level = 50                                                                    # d >= 경로 길이 = 마지막 수준 (목표만)
    p._sub = [sg for sg in p._sub if sg.kind == "goal"] or p._sub
    p.update([3.0, 0.0])
    assert p.is_final and p.all_reached and p.end_episode() == "new_task" and p.needs_new_task
    q = pgcl.PGCL(final_successes=5)                                                # 기본 5: 한 번 성공으로는 새 과제 요청 안 함
    q.start_episode([[0.0, 0.0], [3.0, 0.0]]); q.level = 50; q._sub = [sg for sg in q._sub if sg.kind == "goal"] or q._sub; q.update([3.0, 0.0])
    assert q.end_episode() == "final_success" and not q.needs_new_task
