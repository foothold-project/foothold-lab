"""N3 학습 루프: 가짜 환경으로 한 회 돌고 · 50 회 저장 · 이어 받기 · 다른 설정 거절 (Kit 없음)."""
from types import SimpleNamespace
import json
import dataclasses
import numpy as np
import pytest
import torch

from foothold_s2.nav import hl_ppo_cfg as cfg, hl_train
from foothold_s2.nav.teacher_obs import TeacherObsLayout

D = TeacherObsLayout().total


class FakeEnv:
    def __init__(self, n):
        self.n = n; self.g = torch.Generator().manual_seed(1)

    def reset(self):
        return torch.randn(self.n, D, generator=self.g)

    def step(self, a):
        d = torch.rand(self.n, generator=self.g) < 0.2
        return torch.randn(self.n, D, generator=self.g), -a.pow(2).sum(-1), d, d & (torch.rand(self.n, generator=self.g) < 0.5), {"task_reached": 0, "fell": int(d.sum())}


def _ppo(**kw):
    return dataclasses.replace(cfg.TeacherPPO(), num_envs=8, num_steps_per_env=4, num_mini_batches=2, num_learning_epochs=1, save_interval=2, **kw)


def test_train_saves_every_interval_and_resumes(tmp_path):
    rec = {"receipt_sha256": "aa"}
    last, saved = hl_train.train(FakeEnv(8), _ppo(), out_dir=tmp_path, iterations=4, receipt=rec, log=lambda s: None)
    assert last == 4 and [p.rsplit("/", 1)[1] for p in saved] == ["model_2.pt", "model_4.pt"]
    last, saved = hl_train.train(FakeEnv(8), _ppo(), out_dir=tmp_path, iterations=2, receipt=rec, resume=str(tmp_path / "model_4.pt"), log=lambda s: None)
    assert last == 6 and saved[0].endswith("model_6.pt")


def test_resume_refuses_other_ppo_or_receipt(tmp_path):
    rec = {"receipt_sha256": "aa"}
    hl_train.train(FakeEnv(8), _ppo(), out_dir=tmp_path, iterations=2, receipt=rec, log=lambda s: None)
    ck = str(tmp_path / "model_2.pt")
    with pytest.raises(ValueError, match="PPO"):
        hl_train.train(FakeEnv(8), _ppo(gamma=0.9), out_dir=tmp_path / "b", iterations=1, receipt=rec, resume=ck, log=lambda s: None)
    with pytest.raises(ValueError, match="receipt"):
        hl_train.train(FakeEnv(8), _ppo(), out_dir=tmp_path / "c", iterations=1, receipt={"receipt_sha256": "bb"}, resume=ck, log=lambda s: None)


def test_never_overwrites_a_checkpoint(tmp_path):
    rec = {"receipt_sha256": "aa"}
    hl_train.train(FakeEnv(8), _ppo(), out_dir=tmp_path, iterations=2, receipt=rec, log=lambda s: None)
    with pytest.raises(FileExistsError):
        hl_train.train(FakeEnv(8), _ppo(), out_dir=tmp_path, iterations=2, receipt=rec, log=lambda s: None)


def test_vec_env_resets_done_envs_from_the_real_body_position():
    n = 3
    state = SimpleNamespace(done=np.array([False, True, False]), timed_out=np.array([False, False, False]),
                            pos_local=np.arange(9, dtype=float).reshape(3, 3))
    calls = {}
    nav = SimpleNamespace(n=n, step=lambda a: state, reset=lambda: state)
    task = SimpleNamespace(n=n, origin_xy=np.zeros((n, 2)),
                           reset_envs=lambda ids, start_xy=None: calls.setdefault("r", []).append((list(ids), np.asarray(start_xy))),
                           step=lambda s: {"reward": np.ones(n), "task_reached": np.zeros(n, bool)},
                           observation=lambda s: {"flat": np.zeros((n, D), np.float32)})
    env = hl_train.TeacherVecEnv(nav, task)
    env.reset()
    obs, r, d, to, info = env.step(torch.zeros(n, 3))
    ids, start = calls["r"][-1]
    assert ids == [1] and start.shape == (1, 2) and obs.shape == (n, D) and info["fell"] == 1


def test_success_is_a_reset_request_once_and_the_level_goes_up_when_isaac_hands_the_env_back_done():
    import torch
    from foothold_s2.nav import nav_task, room_generator as rg, grade_map as gm
    from foothold_s2.tests.test_nav_task_table_cpu import _setup, _state

    _rooms, assets, starts = _setup(n_rooms=1, k=4)
    n = 2
    task = nav_task.NavTask(assets, n, np.random.default_rng(3))
    task.build_table(starts, per_start=16, seed=0)
    task.origin_xy = np.zeros((n, 2))                                      # pos_local is the room frame here
    st0 = np.stack([starts[0][0], starts[0][1]])
    asked, limits, cur = [], [], {}
    nav = SimpleNamespace(n=n, reset=lambda: cur["s"], step=lambda a: cur["s"], request_reset=lambda ids: asked.append(list(ids)),
                          set_episode_seconds=lambda ids, sec: limits.append((list(ids), list(sec))))
    env = hl_train.TeacherVecEnv(nav, task)
    cur["s"] = _state(n, st0)
    env.reset()
    assert limits and all(s > 10 for s in limits[0][1])
    task.pgcl[0]._i = len(task.pgcl[0]._sub) - 1
    pos = st0.copy(); pos[0] = task.pgcl[0]._sub[-1].point
    cur["s"] = _state(n, pos)
    obs, r, d, to, info = env.step(torch.zeros(n, 3))
    assert info["task_reached"] == 1 and asked == [[0]] and task.pgcl[0].level == 1       # asked Isaac, nothing ended yet
    cur["s"] = _state(n, st0, done=np.array([True, False]))                 # next window: Isaac hands env 0 back at its start
    obs, r, d, to, info = env.step(torch.zeros(n, 3))
    assert info["task_reached"] == 0 and asked == [[0]] and task.pgcl[0].level == 2 and info["fell"] == 1


def test_adaptive_lr_stops_at_lr_max_and_kl_warn_line_and_kl_max_are_logged(tmp_path):
    lines = []
    hl_train.train(FakeEnv(8), _ppo(desired_kl=1e6, lr_max=4.0e-4, kl_warn=0.0), out_dir=tmp_path, iterations=6, receipt={"receipt_sha256": "aa"}, log=lines.append)
    rows = [json.loads(s) for s in lines if s.startswith("{")]
    assert max(r["lr"] for r in rows) == 4.0e-4 and rows[-1]["lr"] == 4.0e-4 and all("kl_max" in r and r["kl_max"] >= r["kl"] for r in rows)
    assert sum(s.startswith("KL_WARN") for s in lines) == len(rows) and "lr=4.00e-04" in [s for s in lines if s.startswith("KL_WARN")][-1]
    assert cfg.TeacherPPO().lr_max == 1.0e-3 and cfg.TeacherPPO().lr_min == 1.0e-5 and "lr_max" in cfg.ASSUMED
    quiet = []
    hl_train.train(FakeEnv(8), _ppo(kl_warn=1e9), out_dir=tmp_path / "q", iterations=2, receipt={"receipt_sha256": "aa"}, log=quiet.append)
    assert not any(s.startswith("KL_WARN") for s in quiet)


def test_noise_std_floor_is_off_by_default_and_holds_the_policy_std_when_on(tmp_path):
    """탐색 잡음 하한: 기본 꺼짐 (줄 없음). 켜면 lr 이 커도 std 가 하한 아래로 안 내려가고 첫 줄에 NOISE_STD_MIN 이 찍힌다. 범위 밖 값은 거절."""
    off = []
    hl_train.train(FakeEnv(8), _ppo(), out_dir=tmp_path / "off", iterations=1, receipt={"receipt_sha256": "aa"}, log=off.append)
    assert not any("NOISE_STD_MIN" in str(x) for x in off)
    on = []
    hl_train.train(FakeEnv(8), _ppo(learning_rate=0.5, lr_max=1.0), out_dir=tmp_path / "on", iterations=2, receipt={"receipt_sha256": "aa"},
                   log=on.append, noise_std_min=0.45)
    assert any("NOISE_STD_MIN 0.45" in str(x) for x in on)
    rows = [json.loads(x) for x in on if str(x).startswith('{"iteration"')]
    assert rows and all(r["noise_std"] >= 0.45 - 1e-6 for r in rows)
    with pytest.raises(ValueError, match="noise_std_min"):
        hl_train.train(FakeEnv(8), _ppo(), out_dir=tmp_path / "bad", iterations=1, receipt={"receipt_sha256": "aa"}, log=lambda s: None, noise_std_min=0.9)
