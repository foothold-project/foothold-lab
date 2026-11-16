"""N4 student: depth 전처리 · CNN+GRU 모양 · DAgger 가 teacher 를 따라감 · done 에서 GRU 끊김 · StudentEnv 관측 (Kit 없음)."""
import dataclasses
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.nav import hl_student as hs
from foothold_s2.nav.teacher_obs import TeacherObsLayout

CFG = dataclasses.replace(hs.StudentCfg(), num_envs=4, rollout_steps=8, seq_len=4, batch_seqs=4, epochs=3, max_rollouts=3)


def test_preprocess_depth_clips_and_maps_bad_values_to_far():
    d = torch.zeros(2, hs.DEPTH_H, hs.DEPTH_W); d[0, 0, 0] = float("inf"); d[0, 0, 1] = float("nan"); d[0, 0, 2] = 5.0; d[1] = 99.0
    x = hs.preprocess_depth(d, 10.0)
    assert x.shape == (2, 1, hs.DEPTH_H, hs.DEPTH_W) and x[0, 0, 0, 0] == 1 and x[0, 0, 0, 1] == 1 and x[0, 0, 0, 2] == 0.5 and (x[1] == 1).all()
    with pytest.raises(ValueError):
        hs.preprocess_depth(torch.zeros(1, 60, 60), 10.0)


def test_student_shapes_and_hidden_state_is_used():
    net = hs.build_student(CFG)
    depth, prop = torch.rand(3, 1, hs.DEPTH_H, hs.DEPTH_W), torch.randn(3, 47)
    a, z, xm, h = net(depth, prop, net.init_hidden(3))
    assert a.shape == (3, 3) and z.shape == (3, 32) and xm.shape == (3, 6) and h.shape == (3, CFG.gru_hidden)
    a2, *_ = net(depth, prop, h)
    assert not torch.allclose(a, a2)            # 기억이 출력에 영향을 준다


class FakeStudentEnv:
    def __init__(self, n):
        self.n, self.g = n, torch.Generator().manual_seed(0)

    def _o(self, done=None):
        return {"teacher": torch.zeros(self.n, 3), "depth": torch.rand(self.n, 1, hs.DEPTH_H, hs.DEPTH_W, generator=self.g),
                "prop": torch.randn(self.n, 47, generator=self.g), "x_m": torch.randn(self.n, 6, generator=self.g),
                "done": torch.zeros(self.n, dtype=torch.bool) if done is None else done}

    def reset(self):
        return self._o()

    def step(self, a):
        return self._o(torch.rand(self.n, generator=self.g) < 0.2)


def _teacher(obs):
    return torch.zeros(obs.shape[0], 3), torch.zeros(obs.shape[0], 32)


def test_dagger_runs_logs_and_the_loss_goes_down():
    logs = []
    def teacher(obs):
        return torch.full((obs.shape[0], 3), 0.5), torch.zeros(obs.shape[0], 32)
    student, _opt, last = hs.dagger(FakeStudentEnv(4), teacher, CFG, iterations=6, log=logs.append)
    rows = [json.loads(l) for l in logs]
    assert last == 6 and rows[0]["beta"] == 1.0 and rows[-1]["beta"] < rows[0]["beta"]
    assert rows[-1]["act"] < rows[0]["act"]


def test_aggregate_drops_the_oldest_chunk():
    agg = hs.Aggregate(2)
    for i in range(3):
        agg.add({"act": torch.full((5, 2, 3), float(i))})
    assert len(agg.chunks) == 2 and float(agg.chunks[0]["act"][0, 0, 0]) == 1.0


def test_gru_state_is_cut_at_done_in_the_rollout():
    seen = []
    net = hs.build_student(CFG)
    orig = net.forward
    net.forward = lambda d, p, h: (seen.append(h.abs().sum(1).clone()), orig(d, p, h))[1]
    env = FakeStudentEnv(4)
    env.step = lambda a: env._o(torch.tensor([True, False, False, False]))
    hs.rollout(env, env.reset(), _teacher, net, CFG, 0.0, torch.Generator().manual_seed(0))
    assert seen[1][0] == 0 and seen[1][1] > 0       # done 이었던 env 0 만 다음 틱 시작 상태가 0


def test_student_env_builds_the_observation_from_the_teacher_vector_and_goal():
    lay = TeacherObsLayout()
    n = 2
    state = SimpleNamespace(pos_local=np.zeros((n, 3)), quat_w=np.tile([1.0, 0, 0, 0], (n, 1)))
    task = SimpleNamespace(origin_xy=np.full((n, 2), 10.0), goal=np.array([[11.0, 10.0], [10.0, 12.0]]))
    flat = torch.arange(n * lay.total, dtype=torch.float32).reshape(n, lay.total)
    vec = SimpleNamespace(n=n, state=state, task=task, reset=lambda: flat, step=lambda a: (flat, None, torch.tensor([False, True]), None, {}))
    env = hs.StudentEnv(vec, lambda: np.full((n, hs.DEPTH_H, hs.DEPTH_W), 3.0), CFG)
    o = env.step(torch.zeros(n, 3))
    assert o["prop"].shape == (n, 47) and o["x_m"].shape == (n, 6) and o["done"].tolist() == [False, True]
    assert torch.allclose(o["prop"][:, 45:], torch.tensor([[1.0, 0.0], [0.0, 2.0]]))   # 방 가운데 (10, 10) 에서 본 목표의 몸 틀 위치
    assert float(o["depth"][0, 0, 0, 0]) == pytest.approx(0.3)


def test_preprocess_depth_accepts_the_ray_caster_channel_last_shape():
    import torch
    from foothold_s2.nav import hl_student as hs
    out = hs.preprocess_depth(torch.full((2, hs.DEPTH_H, hs.DEPTH_W, 1), 2.0), max_m=4.0)
    assert tuple(out.shape) == (2, 1, hs.DEPTH_H, hs.DEPTH_W) and float(out[0, 0, 0, 0]) == 0.5
