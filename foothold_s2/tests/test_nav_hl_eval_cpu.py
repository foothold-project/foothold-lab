"""HiPAN 고정 수준 평가 (hl_eval) CPU 예행: 진짜 NavTask (방 · 표 · PGCL) + 몸이 속도 명령대로 움직이는 가짜 NavEnv + 진짜 저장본 형식의 teacher actor. Kit 없음."""
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.nav import hl_eval, hl_ppo_cfg as cfg, hl_train, nav_task, pgcl
from foothold_s2.tests.test_nav_task_table_cpu import _setup, _state

N = 12
TICK_S = 0.5


class KinNav:
    """몸 = 방 틀 점. 행동 (vx vy) 대로 틱마다 이동. 시간 초과 (set_episode_seconds) · 과제 성공 때 request_reset 이면 시작 자리로 돌려 놓고 done 으로 돌려줌 (Isaac 처럼)."""

    def __init__(self, n, starts, room_id):
        self.n, self.hold, self.raw = n, 1, SimpleNamespace(step_dt=TICK_S)
        self.start = np.stack([starts[room_id[i]][i % len(starts[room_id[i]])] for i in range(n)]).astype(float)
        self.pos, self.age, self.limit = self.start.copy(), np.zeros(n), np.full(n, 90.0)
        self.pending = np.zeros(n, bool)

    def reset(self):
        self.pos, self.age, self.pending = self.start.copy(), np.zeros(self.n), np.zeros(self.n, bool)
        return _state(self.n, self.pos)

    def set_episode_seconds(self, ids, sec):
        self.limit[np.asarray(ids, int)] = np.asarray(sec, float)

    def request_reset(self, ids):
        self.pending[np.asarray(ids, int)] = True

    def step(self, action):
        a = np.asarray(action, float)
        self.pos = self.pos + np.clip(a[:, :2], -1.0, 1.0) * TICK_S
        self.age += TICK_S
        timed = self.age >= self.limit
        done = timed | self.pending
        state = _state(self.n, self.pos, done=done)
        state.timed_out = timed
        self.pos[done], self.age[done], self.pending[:] = self.start[done], 0.0, False        # 되돌려진 새 에피소드의 값
        return state


def _checkpoint(tmp_path, iteration, seed):
    torch.manual_seed(seed)
    ppo = cfg.TeacherPPO()
    actor, critic = cfg.build_actor_critic(ppo)
    path = tmp_path / f"model_{iteration}.pt"
    torch.save({"format": hl_train.CKPT_FORMAT, "iteration": iteration, "ppo": ppo.as_dict(), "receipt_sha256": "x", "lr": 1e-3, "actor": actor.state_dict(),
                "critic": critic.state_dict(), "log_std": torch.full((3,), float(np.log(0.2))), "optimizer": {}}, path)
    return path


@pytest.fixture()
def rig():
    _rooms, assets, starts = _setup(n_rooms=2, k=4)
    task = nav_task.NavTask(assets, N, np.random.default_rng(3))
    task.build_table(starts, per_start=16, seed=0)
    task.origin_xy = np.zeros((N, 2))
    nav = KinNav(N, starts, task.room_id)
    env = hl_train.TeacherVecEnv(nav, task)
    yield env, task


def test_levels_spread_over_rooms_and_stay_fixed_after_success(rig):
    env, task = rig
    lv = hl_eval.assign_levels(task.room_id, (3, 4, 5, 6))
    for r in set(task.room_id.tolist()):
        assert {lv[i] for i in range(N) if task.room_id[i] == r} == {3, 4, 5, 6}
    hl_eval.fix_levels(task, lv)
    p = task.pgcl[0]
    p.start_episode(task.path[0] if task.path[0] is not None else np.array([[0.0, 0.0], [5.0, 0.0], [9.0, 0.0]]))
    p._i = len(p._sub)                                              # 모든 부목표 도달
    assert p.end_episode() in ("level_up", "final_success", "new_task") and p.level == lv[0]
    assert isinstance(p, pgcl.PGCL) and (p.d0, p.step, p.reach_m) == (task.pgcl[1].d0, task.pgcl[1].step, task.pgcl[1].reach_m)


def test_a_cell_reports_every_fixed_level_with_the_same_first_tasks_for_any_checkpoint(rig, tmp_path):
    env, task = rig
    a1, std1, it1 = hl_eval.load_actor(_checkpoint(tmp_path, 300, 1))
    a2, std2, it2 = hl_eval.load_actor(_checkpoint(tmp_path, 1000, 2))
    assert (it1, it2) == (300, 1000) and std1 == pytest.approx(0.2, rel=1e-5)
    ticks = hl_eval.horizon_ticks(task)
    assert ticks > 10
    goals = []
    rows = []
    for actor in (a1, a2):
        out = hl_eval.run_cell(env, task, actor, levels=(3, 4, 5, 6), ticks=ticks, mode="mean", seed=7)
        goals.append(task.goal.copy() if False else None)
        rows.append(out)
        assert set(out) == {3, 4, 5, 6}
        for lv, v in out.items():
            assert v["eps"] >= 0 and v["first_eps"] >= 0
            assert all(np.isfinite(v[k]) for k in ("succ", "prog", "cos", "dend", "first_succ", "first_prog"))
        assert sum(v["first_eps"] for v in out.values()) > 0
        assert all(p.level == p.fixed for p in task.pgcl)            # 수준은 끝까지 고정
    # 같은 시드 -> 첫 과제가 저장본과 무관하게 같다: env 마다 첫 에피소드의 (수준, 경로 길이) 를 두 칸에서 비교
    firsts = []
    for actor in (a1, a2):
        task.rng = np.random.default_rng(7)
        task.path = [None] * N
        hl_eval.fix_levels(task, hl_eval.assign_levels(task.room_id, (3, 4, 5, 6)))
        env.reset()
        firsts.append(np.array([task._length(p) for p in task.path]))
    assert np.allclose(firsts[0], firsts[1])
    task.rng = np.random.default_rng(8)
    task.path = [None] * N
    env.reset()
    assert not np.allclose(firsts[0], np.array([task._length(p) for p in task.path]))      # 다른 시드는 다른 과제


def test_a_zero_policy_never_reaches_and_a_cell_is_refused_for_a_bad_mode(rig):
    env, task = rig

    class Zero(torch.nn.Module):
        def forward(self, x):
            return torch.zeros(x.shape[0], 3)

    out = hl_eval.run_cell(env, task, Zero(), levels=(3, 4), ticks=hl_eval.horizon_ticks(task), mode="mean", seed=1)
    assert all(v["succ"] in (0.0, -1.0) for v in out.values()) and all(v["first_succ"] in (0.0, -1.0) for v in out.values())
    with pytest.raises(ValueError, match="mode"):
        hl_eval.run_cell(env, task, Zero(), levels=(3,), ticks=3, mode="loud", seed=1)


def test_a_policy_that_walks_to_the_subgoal_scores_above_zero(rig):
    """정책이 부목표 방향으로 가면 (정답 사전 지식 없이 task.subgoal 을 읽는 오라클) 성공이 0 보다 커야 한다: 평가 틀이 성공을 셀 수 있다는 확인."""
    env, task = rig

    class Oracle(torch.nn.Module):
        def forward(self, x):
            pos = env.nav.pos
            d = task.subgoal - pos
            n = np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
            v = np.clip(d / n, -1, 1) * np.minimum(n, 1.0)
            return torch.as_tensor(np.c_[v, np.zeros(len(v))], dtype=torch.float32)

    out = hl_eval.run_cell(env, task, Oracle(), levels=(3, 4), ticks=hl_eval.horizon_ticks(task) * 2, mode="mean", seed=1)
    assert any(v["succ"] > 0 for v in out.values()), out


def test_table_and_json_shape():
    rows = [{"iteration": 300, "mode": "mean", "level": 3, "eps": 4, "succ": 0.5, "prog": 0.7, "cos": 0.2},
            {"iteration": 300, "mode": "mean", "level": 4, "eps": 0, "succ": -1.0, "prog": -1.0, "cos": -1.0}]
    t = hl_eval.table(rows)
    assert "model_300" in t and "0.500 (4)" in t and "| - |" in t


def test_fine_level_columns_are_added_next_to_the_old_ones_and_agree_with_them(rig):
    """수준 3 이상 한 칸 (l3p) 은 그대로, 세분 칸 (l3 · l4 · l5 · l6p) 이 더해진다: 세분 칸의 에피소드 수 합 = l3p, 도달 부목표 합 = l3p."""
    env, task = rig
    out = hl_eval.run_cell(env, task, torch.nn.Identity(), levels=(1,), ticks=1, mode="mean", seed=1) if False else None
    hl_eval.fix_levels(task, hl_eval.assign_levels(task.room_id, (1, 2, 3, 4, 5, 6)))
    task._st = None
    env.reset()
    zero = torch.zeros(N, 3)
    for _ in range(hl_eval.horizon_ticks(task)):
        env.step(zero + 0.8)
    stats = env.take_nav_stats()
    assert {"nv_eps_l1", "nv_eps_l2", "nv_eps_l3p", "nv_eps_l3", "nv_eps_l4", "nv_eps_l5", "nv_eps_l6p"} <= set(stats)
    assert stats["nv_eps_l3p"] == sum(stats[f"nv_eps_{k}"] for k in ("l3", "l4", "l5", "l6p")) and stats["nv_eps_l3p"] > 0
    assert stats["nv_sub_reached_l3p"] == sum(stats[f"nv_sub_reached_{k}"] for k in ("l3", "l4", "l5", "l6p"))
    assert stats["nv_cos_n_l3p"] == sum(stats[f"nv_cos_n_{k}"] for k in ("l3", "l4", "l5", "l6p"))
    assert [hl_eval.stat_key(k) for k in (1, 2, 3, 4, 5, 6, 9)] == ["l1", "l2", "l3", "l4", "l5", "l6p", "l6p"]
