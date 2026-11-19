"""HiPAN 과제 유지 처방 A (연속 실패 N 번 뒤 새 과제 · 기본 꺼짐) + 로그 둘 (새 과제의 첫 시도 성공률 · 같은 과제 연속 실패 3 회 이상 env 수). 실제 NavTask.reset_envs 경로."""
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import kit_factories as kf
from foothold_s2.nav import nav_task as nt
from foothold_s2.nav import room_generator as rg

NAV = Path(__file__).resolve().parents[1] / "nav"
TABLE = gm.load_grade_table(NAV / "grade_table_draft.yaml")


@pytest.fixture(scope="module")
def assets():
    return [nt.make_asset(rg.make_room(s, rg.FIRST_ROUND_CFG, TABLE)[1], TABLE) for s in (3, 4)]


def _task(assets, n_after=0, n=2):
    t = nt.NavTask(assets, n, np.random.default_rng(0))
    t.new_task_after_fails = n_after
    t.reset_envs(np.arange(n))
    return t


def _fail(t, i):
    return t.reset_envs([i])["outcome"][0]          # 부목표를 못 채운 채 에피소드가 끝남 = hold


def test_switch_is_off_by_default_and_the_task_is_kept(assets):
    t = _task(assets)
    assert t.new_task_after_fails == 0
    goal, new0 = t.goal[0].copy(), t.task_new
    for _ in range(12):
        assert _fail(t, 0) == "hold"
    assert np.allclose(t.goal[0], goal) and t.task_new == new0 and t.task_cut_fails == 0       # 옛 동작: 같은 과제 유지
    assert t._fail_run[0] == 12                                                                  # 통계는 센다


def test_after_n_failures_a_new_task_is_drawn_and_the_level_stays(assets):
    t = _task(assets, n_after=3)
    t.pgcl[0].level = 2                                                                          # 수준은 그대로 두는지
    goal, new0 = t.goal[0].copy(), t.task_new
    _fail(t, 0); _fail(t, 0)
    assert np.allclose(t.goal[0], goal) and t.task_new == new0 and t._fail_run[0] == 2
    _fail(t, 0)                                                                                  # 세 번째 연속 실패 -> 새 과제
    assert t.task_new == new0 + 1 and t.task_cut_fails == 1 and t._fail_run[0] == 0
    assert not np.allclose(t.goal[0], goal)
    assert t.pgcl[0].level == 2
    assert t._fail_run[1] == 0 and t.task_cut_fails == 1                                         # 다른 env 는 그대로


def test_a_success_resets_the_failure_run(assets):
    t = _task(assets, n_after=3)
    _fail(t, 0); _fail(t, 0)
    t.pgcl[0]._i = len(t.pgcl[0]._sub)                                                           # 부목표를 다 채운 에피소드
    assert t.reset_envs([0])["outcome"] == ["level_up"] and t._fail_run[0] == 0
    _fail(t, 0); _fail(t, 0)
    assert t.task_cut_fails == 0                                                                 # 성공 뒤 다시 세어 N 에 못 미침


def test_first_try_success_by_level_counts_only_new_tasks(assets):
    t = _task(assets, n_after=2)
    _fail(t, 0)                                                                                  # env 0: 새 과제의 첫 시도 실패 (수준 1)
    t.pgcl[1]._i = len(t.pgcl[1]._sub)                                                           # env 1: 첫 시도 성공
    t.reset_envs([1])
    _fail(t, 0)                                                                                  # env 0 의 두 번째 시도 (첫 시도 아님) -> 연속 2 실패 -> 새 과제
    _fail(t, 0)                                                                                  # 새 과제의 첫 시도 실패
    st = t.take_stats()
    assert st["nv_ft_eps_l1"] == 3 and st["nv_ft_succ_l1"] == pytest.approx(1 / 3)               # 첫 시도: env0 둘 (실패) + env1 하나 (성공)
    assert st["nv_task_cut"] == 1
    assert st["nv_ft_eps_l2"] == 0 and st["nv_ft_succ_l2"] == -1.0


def test_stuck_env_count_reads_three_or_more_consecutive_failures(assets):
    t = _task(assets)                                                                            # 끔 상태에서도 센다
    for _ in range(3):
        _fail(t, 0)
    _fail(t, 1)
    st = t.take_stats()
    assert st["nv_stuck3"] == 1 and st["nv_stuck3_l1"] == 1 and st["nv_stuck3_l2"] == 0 and st["nv_task_cut"] == 0


def test_factory_switch_reads_config_then_environment():
    assert kf.new_task_after_fails({}, environ={}) == 0
    assert kf.new_task_after_fails({"task_new_after_fails": 5}, environ={}) == 5
    assert kf.new_task_after_fails({}, environ={"HIPAN_NEW_TASK_AFTER_FAILS": "5"}) == 5
    with pytest.raises(ValueError):
        kf.new_task_after_fails({"task_new_after_fails": -1}, environ={})


def test_task_rows_and_cut_log_record_the_task_with_clearance_and_grades(assets):
    t = _task(assets, n_after=2)
    rows = t.task_rows()
    assert len(rows) == 2 and {"env", "room", "level", "streak", "fail_run", "cut_n", "start", "goal", "path_len_m", "min_clear_m", "grades"} <= set(rows[0])
    assert rows[0]["path_len_m"] > 0 and rows[0]["min_clear_m"] >= 0 and sum(rows[0]["grades"].values()) == pytest.approx(1.0, abs=1e-3)
    goal = [round(float(x), 3) for x in t.goal[0]]
    _fail(t, 0); _fail(t, 0)                                                                     # 두 번 연속 실패 -> 자름
    cuts = t.take_cut_log()
    assert len(cuts) == 1 and cuts[0]["env"] == 0 and cuts[0]["goal"] == goal and cuts[0]["fail_run"] == 2 and cuts[0]["cut_n"] == 1   # 자르기 전 과제의 기록
    assert cuts[0]["min_clear_m"] is not None and t.take_cut_log() == []
    assert t.task_rows()[0]["cut_n"] == 1 and t.task_rows()[0]["goal"] != goal


def test_dump_tasks_writes_jsonl_per_save_and_can_be_switched_off(assets, tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from foothold_s2.nav import hl_train
    t = _task(assets, n_after=2)
    _fail(t, 0); _fail(t, 0)
    env = SimpleNamespace(task=t)
    hl_train.dump_tasks(env, tmp_path, 50)
    rows = [json.loads(x) for x in (tmp_path / "tasks_50.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 and rows[0]["iteration"] == 50 and rows[0]["cut_n"] == 1
    cuts = [json.loads(x) for x in (tmp_path / "task_cuts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(cuts) == 1 and cuts[0]["iteration"] == 50 and cuts[0]["env"] == 0
    monkeypatch.setenv("HIPAN_TASK_DUMP", "0")
    hl_train.dump_tasks(env, tmp_path, 100)
    assert not (tmp_path / "tasks_100.jsonl").exists()                                           # 끔
