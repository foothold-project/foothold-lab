"""HiPAN 수준 되돌림 스위치 (새 과제를 뽑으면 그 env 의 PGCL 수준 1 · 연속 성공 0 · 기본 꺼짐) + 수준별 env 수 통계. 실제 NavTask.reset_envs 경로."""
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


def _task(assets, on, n_after=0, n=2):
    t = nt.NavTask(assets, n, np.random.default_rng(0))
    t.new_task_after_fails = n_after
    t.level_reset_on_new_task = on
    t.reset_envs(np.arange(n))
    return t


def _fail(t, i):
    return t.reset_envs([i])["outcome"][0]          # 부목표를 못 채운 채 에피소드가 끝남 = hold


def _succeed(t, i):
    t.pgcl[i]._i = len(t.pgcl[i]._sub)              # 부목표를 다 채운 에피소드
    return t.reset_envs([i])["outcome"][0]


def _to_final(t, i, level=99):
    """env i 를 마지막 수준 (목표만) 에 둔다: 수준을 올려 두고 실패 한 번으로 그 수준의 에피소드를 시작."""
    t.pgcl[i].level = level
    assert _fail(t, i) == "hold"
    assert t.pgcl[i].is_final


def test_switch_is_off_by_default(assets):
    assert nt.NavTask(assets, 1, np.random.default_rng(0)).level_reset_on_new_task is False


@pytest.mark.parametrize("on, want", [(False, 99), (True, 1)])
def test_final_level_five_successes_new_task(assets, on, want):
    t = _task(assets, on)
    _to_final(t, 0)
    goal, new0 = t.goal[0].copy(), t.task_new
    outs = [_succeed(t, 0) for _ in range(5)]
    assert outs == ["final_success"] * 4 + ["new_task"]
    assert t.task_new == new0 + 1 and not np.allclose(t.goal[0], goal)                         # 새 과제가 뽑혔다
    assert t.pgcl[0].level == want and t.pgcl[0].streak == 0
    assert t.pgcl[1].level == 1                                                                 # 다른 env 는 그대로


@pytest.mark.parametrize("on, want", [(False, 2), (True, 1)])
def test_prescription_a_cut_new_task(assets, on, want):
    t = _task(assets, on, n_after=2)
    t.pgcl[0].level = 2
    goal, new0 = t.goal[0].copy(), t.task_new
    assert _fail(t, 0) == "hold" and t.pgcl[0].level == 2 and t.task_new == new0              # 같은 과제 재도전: 수준 그대로 (켜도)
    _fail(t, 0)                                                                                 # 두 번째 연속 실패 -> 처방 A 가 자름
    assert t.task_cut_fails == 1 and t.task_new == new0 + 1 and not np.allclose(t.goal[0], goal)
    assert t.pgcl[0].level == want and t.pgcl[0].streak == 0


@pytest.mark.parametrize("on, want", [(False, (4, 2)), (True, (1, 0))])
def test_first_task(assets, on, want):
    t = nt.NavTask(assets, 2, np.random.default_rng(0))
    t.level_reset_on_new_task = on
    t.pgcl[0].level, t.pgcl[0].streak = 4, 2                                                    # 예: --resume-levels 로 넣은 수준
    t.reset_envs(np.arange(2))                                                                  # path 가 None -> 첫 과제
    assert (t.pgcl[0].level, t.pgcl[0].streak) == want


def test_on_keeps_level_up_and_same_task_retries(assets):
    t = _task(assets, True)
    assert _succeed(t, 0) == "level_up" and t.pgcl[0].level == 2                                # 같은 과제에서 수준 올림은 그대로
    goal = t.goal[0].copy()
    for _ in range(4):
        assert _fail(t, 0) == "hold"
    assert t.pgcl[0].level == 2 and np.allclose(t.goal[0], goal)                                # 새 과제가 아니면 수준 유지


def test_level_count_stats(assets):
    t = _task(assets, False, n=4)
    t.pgcl[1].level = 2; t.pgcl[2].level = 3; t.pgcl[3].level = 7
    _fail(t, 0)
    st = t.take_stats()
    assert (st["nv_lvl_n_l1"], st["nv_lvl_n_l2"], st["nv_lvl_n_l3p"]) == (1, 1, 2)


def test_factory_switch_reads_config_then_environment():
    assert kf.task_level_reset_on_new_task({}, environ={}) is False
    assert kf.task_level_reset_on_new_task({}, environ={"HIPAN_LEVEL_RESET_ON_NEW_TASK": "1"}) is True
    assert kf.task_level_reset_on_new_task({}, environ={"HIPAN_LEVEL_RESET_ON_NEW_TASK": "0"}) is False
    assert kf.task_level_reset_on_new_task({"task_level_reset_on_new_task": True}, environ={}) is True
    assert kf.task_level_reset_on_new_task({"task_level_reset_on_new_task": 0}, environ={"HIPAN_LEVEL_RESET_ON_NEW_TASK": "1"}) is False   # 설정이 먼저
    with pytest.raises(ValueError):
        kf.task_level_reset_on_new_task({}, environ={"HIPAN_LEVEL_RESET_ON_NEW_TASK": "2"})


def test_fixed_level_eval_ignores_reset_switch(assets):
    """고정 수준 평가 (hl_eval.fix_levels) 는 학습용 되돌림 스위치가 켜진 채 넘어와도 첫 reset 에서 수준을 1 로 덮지 않는다 (reviewer PR #902)."""
    from foothold_s2.nav import hl_eval
    t = nt.NavTask(assets, 4, np.random.default_rng(0))
    t.level_reset_on_new_task = True
    hl_eval.fix_levels(t, [3, 3, 4, 4])
    t.reset_envs(np.arange(4))
    assert [p.level for p in t.pgcl] == [3, 3, 4, 4]
