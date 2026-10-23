"""S1 runner 무인 학습 점검 (rl 의 test_unattended 와 같은 항목): 상태 파일 · latest.pt · 재개 때 env 상태 복원 · 남은 회차만.

가짜 env 로 배선만 본다. rsl-rl-lib 3.1.2 가 있는 환경(isaac311)에서 돈다.
"""

import json
import os

import pytest
import torch

pytest.importorskip("rsl_rl")
tensordict = pytest.importorskip("tensordict")

from foothold_s2.runners.status import NAME, read_status  # noqa: E402
from foothold_s2.s1_runner import S1Runner  # noqa: E402


class _RC:
    def __init__(self):
        self.vmax_x, self.vmax_y, self.flag_vmax, self.history = 1.0, 1.0, 1.0, []


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


class FakeS1Env:
    """OnPolicyRunner 가 요구하는 VecEnv 모양 + 재개 때 사라질 수 있는 상태 셋."""

    def __init__(self, num_envs=8, seed=0, crash_at_step=None):
        self.num_envs = num_envs
        self.num_actions = 12
        self.device = "cpu"
        self.max_episode_length = 13
        self.episode_length_buf = torch.zeros(num_envs, dtype=torch.long)
        self.g = torch.Generator().manual_seed(seed)
        self.cfg = type("Cfg", (), {"seed": seed})()
        self.common_step_counter = 0
        self.scene = _Scene(num_envs)
        self.command_manager = _CM(_Term())
        self.unwrapped = self
        self.crash_at_step = crash_at_step
        self._obs = self._make()

    def _make(self):
        n = self.num_envs

        return tensordict.TensorDict({"policy": torch.randn(n, 45, generator=self.g),
                                      "critic": torch.randn(n, 52, generator=self.g)}, batch_size=[n])

    def get_observations(self):
        return self._obs

    def step(self, actions):
        if self.crash_at_step is not None and self.common_step_counter >= self.crash_at_step:
            raise RuntimeError("env 가 죽었다")

        self.common_step_counter += 1
        self.episode_length_buf += 1
        dones = (self.episode_length_buf + torch.arange(self.num_envs)) % self.max_episode_length == 0
        self.episode_length_buf[dones] = 0
        rewards = 1.0 - 0.01 * actions.pow(2).sum(-1) + 0.1 * torch.arange(self.num_envs).float()
        self._obs = self._make()

        return self._obs, rewards, dones.long(), {"time_outs": torch.zeros(self.num_envs, dtype=torch.bool)}


def cfg(**s1):
    return {
        "num_steps_per_env": 24, "save_interval": 1000, "obs_groups": {"policy": ["policy"], "critic": ["critic"]},
        "policy": {"class_name": "ActorCritic", "init_noise_std": 1.0, "actor_obs_normalization": False,
                   "critic_obs_normalization": False, "actor_hidden_dims": [16], "critic_hidden_dims": [16],
                   "activation": "elu"},
        "algorithm": {"class_name": "PPO", "num_learning_epochs": 2, "num_mini_batches": 2, "clip_param": 0.2,
                      "gamma": 0.99, "lam": 0.95, "value_loss_coef": 1.0, "entropy_coef": 0.01,
                      "learning_rate": 1e-3, "max_grad_norm": 1.0, "schedule": "adaptive", "desired_kl": 0.01,
                      "use_clipped_value_loss": True},
        "s1_state": {"latest_interval": 2, "status_interval": 1, **s1},
    }


def make(tmp_path, n=8, **kw):
    env = FakeS1Env(num_envs=n, seed=1, **kw)

    return S1Runner(env, cfg(), log_dir=str(tmp_path), device="cpu"), env


def test_status_first_evidence_and_atomic(tmp_path):
    r, _ = make(tmp_path)
    r.learn(1)
    s = read_status(str(tmp_path))
    assert s["state"] == "done" and s["iter"] == 0 and s["tot_iter"] == 1
    r2, _ = make(tmp_path / "b")
    assert read_status(str(tmp_path / "b")) is None                    # 학습 전에는 없다
    r2.learn(2)
    assert not [f for f in os.listdir(tmp_path / "b") if f.startswith(NAME) and f != NAME]


def test_running_status_carries_first_iteration_evidence(tmp_path):
    r, _ = make(tmp_path)
    seen = []
    real = r.log

    def spy(locs, width=80, pad=35):
        real(locs, width, pad)
        seen.append(dict(read_status(str(tmp_path))))

    r.log = spy
    r.learn(2)
    assert seen[0]["state"] == "running" and seen[0]["iter"] == 0 and {"iter_s", "steps_per_s", "pid", "time"} <= set(seen[0])


def test_latest_pt_written_and_atomic(tmp_path):
    r, _ = make(tmp_path)
    r.learn(3)                                                          # it 0 1 2, latest_interval 2 -> it 0, 2 와 끝
    assert os.path.exists(tmp_path / "latest.pt") and not os.path.exists(tmp_path / "latest.pt.tmp")
    assert torch.load(tmp_path / "latest.pt", weights_only=False)["iter"] == 2


def test_resume_restores_the_four_silent_states_and_continues_after_the_finished_iteration(tmp_path):
    r, env = make(tmp_path / "a")
    rc = env.command_manager.t.range_curriculum
    rc.vmax_x, rc.flag_vmax = 1.75, 1.25
    rc.history.append({"iteration": 3})
    env.scene.terrain.terrain_levels[:] = torch.arange(8)
    r.alg.learning_rate = 3.3e-4                                       # adaptive 로 내려간 값
    r.learn(2)
    ck = str(tmp_path / "a" / "latest.pt")
    steps_after = env.common_step_counter
    assert steps_after == 48

    r2, env2 = make(tmp_path / "b")
    rc2 = env2.command_manager.t.range_curriculum
    assert env2.common_step_counter == 0 and rc2.vmax_x == 1.0 and rc2.flag_vmax == 1.0       # 새 env 는 처음 값
    r2.load(ck)
    assert env2.common_step_counter == steps_after
    assert rc2.vmax_x == 1.75 and rc2.flag_vmax == 1.25 and rc2.history == [{"iteration": 3}]
    assert torch.equal(env2.scene.terrain.terrain_levels, torch.arange(8))
    saved_lr = torch.load(ck, weights_only=False)["ppo_learning_rate"]
    assert r2.alg.learning_rate == saved_lr and saved_lr != 1e-3          # 새 runner 의 기본값(1e-3)이 아니라 저장된 값
    assert r2.current_learning_iteration == 1
    r2.learn(2)                                                          # 끝난 회차 1 다음인 2, 3 을 돈다
    assert r2.current_learning_iteration == 3
    assert torch.load(tmp_path / "b" / "latest.pt", weights_only=False)["iter"] == 3
    assert env2.common_step_counter == steps_after + 48


def test_negative_without_restore_state_is_lost(tmp_path):
    r, env = make(tmp_path / "a")
    env.command_manager.t.range_curriculum.flag_vmax = 1.5
    r.learn(1)
    _, env2 = make(tmp_path / "b")
    assert env2.command_manager.t.range_curriculum.flag_vmax == 1.0 and env2.common_step_counter == 0


def test_stock_checkpoint_is_refused(tmp_path):
    r, _ = make(tmp_path)
    torch.save({"model_state_dict": r.alg.policy.state_dict(), "optimizer_state_dict": r.alg.optimizer.state_dict(),
                "iter": 5, "infos": None}, tmp_path / "model_5.pt")
    with pytest.raises(ValueError):
        r.load(str(tmp_path / "model_5.pt"))


def test_state_file_json_serializable(tmp_path):
    r, _ = make(tmp_path)
    r.learn(1)
    json.load(open(tmp_path / NAME, encoding="utf-8"))


def test_latest_pt_exists_when_training_dies_midway(tmp_path):
    r, _ = make(tmp_path, crash_at_step=24 * 3 + 5)
    with pytest.raises(RuntimeError):
        r.learn(10)
    assert torch.load(tmp_path / "latest.pt", weights_only=False)["iter"] == 2
    assert read_status(str(tmp_path))["iter"] == 2                       # 마지막으로 쓴 상태도 그 회차


def test_latest_pt_survives_a_half_written_save(tmp_path, monkeypatch):
    r, _ = make(tmp_path)
    r.learn(1)
    before = torch.load(tmp_path / "latest.pt", weights_only=False)["iter"]
    real = torch.save

    def half(obj, path, *a, **k):
        with open(path, "wb") as f:
            f.write(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(torch, "save", half)
    with pytest.raises(OSError):
        r.save_latest()
    monkeypatch.setattr(torch, "save", real)
    assert torch.load(tmp_path / "latest.pt", weights_only=False)["iter"] == before
