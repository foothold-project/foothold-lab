"""N3 학습 루프: 가짜 환경으로 한 회 돌고 · 50 회 저장 · 이어 받기 · 다른 설정 거절 (Kit 없음)."""
from types import SimpleNamespace
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
