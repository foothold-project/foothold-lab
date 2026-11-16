from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import hl_rewards_term as hrt
from foothold_s2.nav import nav_task as nt
from foothold_s2.nav import room_generator as rg
from foothold_s2.nav import teacher_obs as to

NAV = Path(__file__).resolve().parents[1] / "nav"
TABLE = gm.load_grade_table(NAV / "grade_table_draft.yaml")


def _state(pos_local, *, applied=None, modified=None, collision=None, vel=(0.5, 0.0, 0.0)):
    pos_local = np.asarray(pos_local, float)
    n = len(pos_local)
    return SimpleNamespace(
        pos_local=pos_local, quat_w=np.tile([1.0, 0, 0, 0], (n, 1)), vel_b=np.tile(vel, (n, 1)), yaw_rate=np.zeros(n), ang_vel_b=np.zeros((n, 3)),
        applied=np.zeros((n, 5)) if applied is None else applied, modified=np.zeros(n, bool) if modified is None else modified,
        collision=np.zeros(n, bool) if collision is None else collision, q=np.zeros((n, 12)), q0=np.zeros(12), proprio=np.zeros((n, 45)))


@pytest.fixture(scope="module")
def assets():
    return [nt.make_asset(rg.make_room(s, rg.FIRST_ROUND_CFG, TABLE)[1], TABLE) for s in (3, 4)]


def test_hl_state_takes_the_applied_command_and_the_flags():
    n = 3
    ap = np.zeros((n, 5)); ap[:, 0] = 0.4
    st = _state(np.zeros((n, 3)), applied=ap, modified=np.array([True, False, False]), collision=np.array([False, True, False]))
    h = hrt.to_hl_state(st, pos_room_xy=np.zeros((n, 2)), subgoal_xy=np.ones((n, 2)), eta=np.ones(n), v_des=np.full(n, 0.5),
                        cmd_prev=np.zeros((n, 3)), cmd_prev2=np.zeros((n, 3)))
    assert np.allclose(h.cmd[:, 0], 0.4) and list(h.limited) == [True, False, False] and list(h.collision) == [False, True, False]
    assert h.actual.shape == (n, 3) and h.actual[0, 0] == pytest.approx(0.5)
    total, terms = hrt.reward(st, pos_room_xy=np.zeros((n, 2)), subgoal_xy=np.ones((n, 2)), eta=np.ones(n), v_des=np.full(n, 0.5),
                              cmd_prev=np.zeros((n, 3)), cmd_prev2=np.zeros((n, 3)))
    assert total.shape == (n,) and np.isfinite(total).all() and total[1] < total[2]          # 충돌한 env 는 같은 조건의 다른 env 보다 낮다


def test_reset_gives_starts_in_free_cells_and_rooms_round_robin(assets):
    t = nt.NavTask(assets, 4, np.random.default_rng(0))
    assert list(t.room_id) == [0, 1, 0, 1]
    out = t.reset_envs(np.arange(4))
    assert out["start_xy"].shape == (4, 2) and out["yaw"].shape == (4,) and out["outcome"] == ["fresh"] * 4
    for i in range(4):
        assert np.linalg.norm(t.start[i] - t.goal[i]) >= 2.0 and t.path[i] is not None
        assert np.allclose(t.subgoal[i], t.pgcl[i].target.point)
    again = t.reset_envs([1])                                   # 같은 과제를 이어 쓴다 (새 과제 요청이 없으면 시작 · 목표 그대로)
    assert np.allclose(again["start_xy"][0], t.start[1]) and again["outcome"] == ["hold"]


def test_task_is_reproducible_from_the_rng_seed(assets):
    a, b = (nt.NavTask(assets, 2, np.random.default_rng(7)) for _ in range(2))
    a.reset_envs([0, 1]); b.reset_envs([0, 1])
    assert np.allclose(a.start, b.start) and np.allclose(a.goal, b.goal)


def test_step_advances_the_subgoal_when_the_robot_stands_on_it_and_pays_reward(assets):
    t = nt.NavTask(assets, 2, np.random.default_rng(1))
    t.reset_envs([0, 1])
    first = t.subgoal.copy()
    pos_room = np.c_[first, np.full(2, 0.34)]                  # 부목표 위에 서 있다
    st = _state(pos_room - [10.0, 10.0, 0.0])                  # 국소 = 방 틀 - 방 가운데
    out = t.step(st)
    assert out["reward"].shape == (2,) and np.isfinite(out["reward"]).all() and out["terms"]
    assert not np.allclose(out["subgoal"], first) or bool(out["task_reached"].all())      # 다음 부목표로 갔다 (또는 이게 마지막이라 다 닿음)
    obs = t.observation(st)
    assert obs["flat"].shape == (2, to.TeacherObsLayout().total)


def test_origin_xy_shifts_the_room_position(assets):
    t = nt.NavTask(assets, 1, np.random.default_rng(2), origin_xy=np.array([[3.0, 4.0]]))
    t.reset_envs([0])
    st = _state(np.array([t.subgoal[0] - [3.0, 4.0]]) @ np.eye(2))
    st.pos_local = np.c_[st.pos_local, [0.34]]
    t.step(st)
    assert t.pgcl[0]._i >= 1                                    # origin 을 쓰면 국소 위치가 부목표 위
