"""CPU known-input checks for EX-41 W86 to PPO validity accounting."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
import torch
from tensordict import TensorDict

from rsl_rl.algorithms import PPO
from rsl_rl.storage.rollout_storage import RolloutStorage

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO
from foothold_s2.runners.ex41_valid_storage import ValidRolloutStorage
from foothold_s2.runners.start_runner import StartRunner


def _obs(n=4):
    return TensorDict({ACTOR_KEY: torch.arange(n * 98, dtype=torch.float32).reshape(n, 98) / 1000,
                       CRITIC_KEY: torch.arange(n * 666, dtype=torch.float32).reshape(n, 666) / 1000},
                      batch_size=[n])


def _alg(n=4, mirror=False):
    obs = _obs(n)
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False,
                              critic_obs_normalization=False, actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8],
                              pose_command_dim=2)
    alg = CriticMirrorPPO(policy, num_learning_epochs=1, num_mini_batches=2,
                          desired_kl=0.01, schedule="adaptive", device="cpu")
    alg.mirror_enabled = mirror
    alg.init_storage("rl", n, 1, obs, [12])
    return alg, obs


def _fill(alg, obs, valid):
    torch.manual_seed(5)
    alg.act(obs)
    alg.process_env_step(obs, torch.tensor([0.2] * len(valid)), torch.ones(len(valid)),
                             {"ex41_ppo_valid": torch.tensor(valid)})
    assert alg.storage.step == 1


def test_missing_mask_and_wrong_shape_fail():
    alg, obs = _alg()
    alg.act(obs)
    with pytest.raises(ValueError, match="validity mask missing"):
        alg.process_env_step(obs, torch.zeros(4), torch.zeros(4), {})
    with pytest.raises(ValueError, match="shape differs"):
        alg.process_env_step(obs, torch.zeros(4), torch.zeros(4), {"ex41_ppo_valid": [True]})


def test_all_valid_batch_matches_installed_storage_exactly():
    obs = _obs()
    base = RolloutStorage("rl", 4, 1, obs, [12], "cpu")
    masked = ValidRolloutStorage("rl", 4, 1, obs, [12], "cpu")
    for storage in (base, masked):
        storage.observations[0].copy_(obs)
        storage.actions[0].fill_(0.5)
        storage.values[0].fill_(0.2)
        storage.returns[0].fill_(0.4)
        storage.advantages[0].fill_(0.6)
        storage.actions_log_prob[0].fill_(-0.1)
        storage.mu[0].fill_(0.3)
        storage.sigma[0].fill_(1.0)
    torch.manual_seed(73)
    original = list(base.mini_batch_generator(2, 2))
    torch.manual_seed(73)
    replacement = list(masked.mini_batch_generator(2, 2))
    assert len(original) == len(replacement) == 4
    for left, right in zip(original, replacement, strict=True):
        for a, b in zip(left[:8], right[:8], strict=True):
            if isinstance(a, TensorDict):
                assert all(torch.equal(a[k], b[k]) for k in a.keys())
            else:
                assert torch.equal(a, b)


def test_all_valid_ppo_update_matches_installed_ppo_exactly():
    torch.manual_seed(27)
    guarded, obs = _alg()
    plain_policy = copy.deepcopy(guarded.policy)
    plain = PPO(plain_policy, num_learning_epochs=1, num_mini_batches=2,
                desired_kl=0.01, schedule="adaptive", device="cpu")
    plain.init_storage("rl", 4, 1, obs, [12])
    _fill(guarded, obs, [True] * 4)
    for name in ("rewards", "dones", "actions", "values", "actions_log_prob", "mu", "sigma"):
        getattr(plain.storage, name).copy_(getattr(guarded.storage, name))
    plain.storage.observations.copy_(guarded.storage.observations)
    guarded.compute_returns(obs)
    plain.compute_returns(obs)
    assert torch.equal(guarded.storage.advantages, plain.storage.advantages)
    torch.manual_seed(91)
    guarded_losses = guarded.update()
    torch.manual_seed(91)
    plain_losses = plain.update()
    assert guarded_losses.pop("ppo_skipped_batches") == 0
    assert guarded_losses == plain_losses
    for a, b in zip(guarded.policy.parameters(), plain.policy.parameters(), strict=True):
        assert torch.equal(a, b)


def test_invalid_step_is_terminal_for_previous_gae():
    alg, obs = _alg(n=2)
    alg.normalize_advantage_per_mini_batch = True
    alg.init_storage("rl", 2, 2, obs, [12])
    alg.act(obs)
    alg.process_env_step(obs, torch.ones(2), torch.zeros(2), {"ex41_ppo_valid": [True, True]})
    alg.act(obs)
    alg.process_env_step(obs, torch.tensor([1e6, 1.0]), torch.zeros(2),
                             {"ex41_ppo_valid": [False, True]})
    assert alg.storage.rewards[1, 0] == 0
    assert alg.storage.values[1, 0] == 0
    assert alg.storage.dones[1, 0] == 1
    alg.compute_returns(obs)
    assert alg.storage.returns[1, 0] == 0
    assert alg.storage.returns[0, 0] == 1


def test_ppo_diagnostic_kl_probe_excludes_invalid_rows():
    alg, obs = _alg()
    _fill(alg, obs, [True, False, True, True])
    runner = object.__new__(StartRunner)
    runner.alg = alg
    runner.env = SimpleNamespace(num_envs=4)
    runner.device = "cpu"
    runner.ex41_pose_commands = True
    runner.pcfg = {"kl_probe_envs": 4}
    snap = runner._kl_ppo_before(0)
    assert snap["obs"].batch_size[0] == 3
    alg.storage.valid.fill_(False)
    assert runner._kl_ppo_before(0) is None


@pytest.mark.parametrize("mirror", [False, True])
def test_invalid_row_cannot_change_loss_kl_or_optimizer(mirror):
    torch.manual_seed(11)
    reference, obs = _alg(mirror=mirror)
    changed, _ = _alg(mirror=mirror)
    changed.policy.load_state_dict(copy.deepcopy(reference.policy.state_dict()))
    changed.optimizer.load_state_dict(copy.deepcopy(reference.optimizer.state_dict()))
    _fill(reference, obs, [True, False, True, True])
    _fill(changed, obs, [True, False, True, True])
    # Equal valid rows and extreme invalid saved policy, return, and advantage.
    changed.storage.mu[0, 1].fill_(1e5)
    changed.storage.sigma[0, 1].fill_(0.01)
    changed.storage.returns[0, 1].fill_(1e6)
    changed.storage.advantages[0, 1].fill_(1e6)
    changed.storage.observations[0][ACTOR_KEY][1].fill_(1e4)
    changed.storage.observations[0][CRITIC_KEY][1].fill_(1e4)
    reference.compute_returns(obs)
    changed.compute_returns(obs)
    assert torch.equal(reference.storage.advantages, changed.storage.advantages)
    assert reference.storage.advantages[0, 1, 0] == 0
    torch.manual_seed(91)
    ref_loss = reference.update()
    torch.manual_seed(91)
    changed_loss = changed.update()
    assert ref_loss == changed_loss
    assert reference.learning_rate == changed.learning_rate
    for a, b in zip(reference.policy.parameters(), changed.policy.parameters(), strict=True):
        assert torch.equal(a, b)


@pytest.mark.parametrize("mirror", [False, True])
def test_all_invalid_minibatches_skip_optimizer_and_return_finite(mirror):
    torch.manual_seed(13)
    alg, obs = _alg(mirror=mirror)
    before = [p.detach().clone() for p in alg.policy.parameters()]
    _fill(alg, obs, [False] * 4)
    alg.compute_returns(obs)
    assert torch.equal(alg.storage.advantages, torch.zeros_like(alg.storage.advantages))
    losses = alg.update()
    assert losses["ppo_skipped_batches"] == 2
    assert all(torch.isfinite(torch.tensor(value)) for value in losses.values())
    assert all(torch.equal(a, b) for a, b in zip(before, alg.policy.parameters(), strict=True))
    assert len(alg.optimizer.state) == 0
