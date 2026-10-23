"""무인 학습 점검 (10/20 lead 지시 3): 상태 파일 · latest.pt · 재개 때 env 상태 복원 · 남은 회차만 · 첫 증거.

가짜 env 로 runner 배선만 본다. 실제 Isaac 의 「띄움 · 첫 증거 · 끝」 은 학습 승인 뒤 첫 실행에서.
"""

import json
import os

import torch

from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.runners.status import NAME, read_status, write_status
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


class _RC:
    def __init__(self):
        self.vmax_x, self.vmax_y, self.history = 1.0, 1.0, []


class _Term:
    def __init__(self):
        self.range_curriculum = _RC()


class _CM:
    def __init__(self, t):
        self.t = t

    def get_term(self, name):
        return self.t


class _Terrain:
    def __init__(self, n):
        self.terrain_levels = torch.zeros(n, dtype=torch.long)
        self.terrain_types = torch.zeros(n, dtype=torch.long)


class _Scene:
    def __init__(self, n):
        self.terrain = _Terrain(n)


class StatefulEnv(FakeStartEnv):
    """가짜 env 에 재개 때 사라질 수 있는 상태 셋(step counter · 지형 칸 · 명령 상한)을 붙인 것."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.common_step_counter = 0
        self.scene = _Scene(self.num_envs)
        self.command_manager = _CM(_Term())
        self.unwrapped = self

    def step(self, a):
        self.common_step_counter += 1
        return super().step(a)


def _runner(tmp_path, n=8, **pc):
    p = {"microbatch_envs": 4, "latest_interval": 2, "status_interval": 1}
    p.update(pc)
    env = StatefulEnv(num_envs=n, seed=1)
    return StartRunner(env, train_cfg(24, p), log_dir=str(tmp_path), device="cpu"), env


def test_status_first_evidence_and_atomic(tmp_path):
    r, _ = _runner(tmp_path)
    assert read_status(str(tmp_path)) is None  # 학습 전에는 없다
    r.learn(1)
    s = read_status(str(tmp_path))
    assert s["state"] == "running" and s["iter"] == 0 and s["tot_iter"] == 1  # 첫 iteration 이 끝나자마자 나온다
    assert s["mean_reward"] is not None or s["mean_reward"] is None  # 키가 있다
    assert {"iter_s", "steps_per_s", "p_smpl", "perception", "pid", "time"} <= set(s)
    assert not [f for f in os.listdir(tmp_path) if f.startswith(NAME) and f != NAME]  # 임시 파일이 남지 않는다


def test_write_status_failed_keeps_old_file(tmp_path, monkeypatch):
    write_status(str(tmp_path), {"state": "running", "iter": 5})
    real = os.replace

    def boom(a, b):
        raise OSError("disk")

    monkeypatch.setattr(os, "replace", boom)
    try:
        write_status(str(tmp_path), {"state": "running", "iter": 6})
    except OSError:
        pass
    monkeypatch.setattr(os, "replace", real)
    assert read_status(str(tmp_path))["iter"] == 5  # 반쯤 쓰인 파일이 아니라 이전 온전한 파일


def test_latest_pt_written_and_atomic(tmp_path):
    r, _ = _runner(tmp_path)
    r.learn(3)  # it 0,1,2 · latest_interval 2 -> it0, it2 와 끝
    assert os.path.exists(tmp_path / "latest.pt") and not os.path.exists(tmp_path / "latest.pt.tmp")
    assert torch.load(tmp_path / "latest.pt", weights_only=False)["iter"] == 2


def test_resume_restores_env_state_and_continues_after_finished_iteration(tmp_path):
    r, env = _runner(tmp_path / "a")
    env.command_manager.t.range_curriculum.vmax_x = 1.75  # 학습 중 올라간 값
    env.command_manager.t.range_curriculum.history.append({"iteration": 3})
    env.scene.terrain.terrain_levels[:] = torch.arange(8)
    r.learn(2)
    ck = str(tmp_path / "a" / "latest.pt")
    steps_after = env.common_step_counter
    assert steps_after == 48

    r2, env2 = _runner(tmp_path / "b")
    assert env2.common_step_counter == 0 and env2.command_manager.t.range_curriculum.vmax_x == 1.0  # 새 env 는 처음 값
    r2.load(ck)
    assert env2.common_step_counter == steps_after
    assert env2.command_manager.t.range_curriculum.vmax_x == 1.75
    assert env2.command_manager.t.range_curriculum.history == [{"iteration": 3}]
    assert torch.equal(env2.scene.terrain.terrain_levels, torch.arange(8))
    assert r2.current_learning_iteration == 1
    r2.learn(2)  # 끝난 회차 1 다음인 2, 3 을 돈다
    assert r2.current_learning_iteration == 3
    assert torch.load(tmp_path / "b" / "latest.pt", weights_only=False)["iter"] == 3
    assert env2.common_step_counter == steps_after + 48


def test_negative_without_restore_state_is_lost(tmp_path):
    """negative control: load 를 안 거치면 같은 상태가 처음 값이다(저장 · 복원이 실제로 일을 한다는 근거)."""
    r, env = _runner(tmp_path / "a")
    env.command_manager.t.range_curriculum.vmax_x = 1.75
    r.learn(1)
    _, env2 = _runner(tmp_path / "b")
    assert env2.command_manager.t.range_curriculum.vmax_x == 1.0 and env2.common_step_counter == 0


def test_state_file_json_serializable(tmp_path):
    r, _ = _runner(tmp_path)
    r.learn(1)
    json.load(open(tmp_path / NAME, encoding="utf-8"))


class _CrashEnv(StatefulEnv):
    def __init__(self, crash_at_step, **kw):
        super().__init__(**kw)
        self.crash_at_step = crash_at_step

    def step(self, a):
        if self.common_step_counter >= self.crash_at_step:
            raise RuntimeError("env 가 죽었다")
        return super().step(a)


def test_latest_pt_exists_when_training_dies_midway(tmp_path):
    """끝에서 저장하는 코드가 가리지 않게, 학습 도중(it 3) 죽는 경우: latest.pt 는 it 2 까지 와 있어야 한다."""
    env = _CrashEnv(crash_at_step=24 * 3 + 5, num_envs=8, seed=1)
    r = StartRunner(env, train_cfg(24, {"microbatch_envs": 4, "latest_interval": 2, "status_interval": 1}),
                    log_dir=str(tmp_path), device="cpu")
    try:
        r.learn(10)
        raise AssertionError("죽었어야 한다")
    except RuntimeError:
        pass
    assert torch.load(tmp_path / "latest.pt", weights_only=False)["iter"] == 2
    assert read_status(str(tmp_path))["iter"] == 2  # 마지막으로 쓴 상태도 그 회차


def test_latest_pt_survives_a_half_written_save(tmp_path, monkeypatch):
    r, _ = _runner(tmp_path)
    r.learn(1)
    before = torch.load(tmp_path / "latest.pt", weights_only=False)["iter"]
    real = torch.save

    def half(obj, path, *a, **k):
        with open(path, "wb") as f:
            f.write(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(torch, "save", half)
    try:
        r.save_latest()
    except OSError:
        pass
    monkeypatch.setattr(torch, "save", real)
    assert torch.load(tmp_path / "latest.pt", weights_only=False)["iter"] == before  # 이전 온전한 파일
