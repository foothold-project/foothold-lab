"""EX-42 BC prior loss on slow-command samples (ex42_bc_prior, lead 2026-11-21 17:21 / 17:24): off by default, the same
bytes when off, and only in the critic-mirror update loop. CPU only."""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners import ex42_bc_prior as bcp
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO
from foothold_s2.runners.start_runner import StartRunner

N = 8


def _obs():
    torch.manual_seed(0)
    actor = torch.randn(N, 98) * 0.1
    actor[:, 6:9] = torch.tensor([[0.2, 0.0, 0.0], [0.0, 0.15, 0.0], [0.5, 0.0, 0.0], [0.3, 0.0, 0.0],
                                  [0.05, 0.0, 0.0], [0.1, 0.0, 0.0], [1.0, 0.0, 0.3], [0.29, 0.0, 0.0]])
    return TensorDict({ACTOR_KEY: actor, CRITIC_KEY: torch.randn(N, 666) * 0.1}, batch_size=[N])


SLOW = [True, True, False, False, False, True, False, True]


def _policy(obs, seed):
    torch.manual_seed(seed)
    return StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
                            actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)


def _alg(obs, mirror=True, prior=None, beta=0.0):
    alg = CriticMirrorPPO(_policy(obs, 1), num_learning_epochs=2, num_mini_batches=2, desired_kl=0.01,
                          schedule="adaptive", device="cpu")
    alg.mirror_enabled = mirror
    alg.bc_prior, alg.bc_beta = prior, beta
    alg.init_storage("rl", N, 1, obs, [12])
    return alg


def _update(alg, obs):
    torch.manual_seed(5)
    alg.act(obs)
    alg.process_env_step(obs, torch.full((N,), 0.2), torch.ones(N), {"ex41_ppo_valid": torch.ones(N, dtype=torch.bool)})
    alg.compute_returns(obs)
    torch.manual_seed(9)
    return alg.update()


def _params(alg):
    return [p.detach().clone() for p in alg.policy.parameters()]


def test_slow_mask_reads_the_command_slot_of_the_actor_input():
    assert bcp.slow_mask(_obs()[ACTOR_KEY]).tolist() == SLOW          # 0.1 <= |c_xy| < 0.3, side commands too


def test_off_and_beta_0_are_the_same_bytes_and_beta_pulls_toward_the_prior(capsys):
    obs = _obs()
    prior = _policy(obs, 2).eval()
    for p in prior.parameters():
        p.requires_grad_(False)
    off = _alg(obs); r_off = _update(off, obs)
    zero = _alg(obs, prior=copy.deepcopy(prior), beta=0.0); r_zero = _update(zero, obs)
    assert all(torch.equal(a, b) for a, b in zip(_params(off), _params(zero), strict=True))
    assert "bc_prior_loss" not in r_off and r_zero["bc_prior_samples"] == 2 * sum(SLOW)     # two epochs over every row
    assert r_zero["bc_prior_loss"] > 0
    on = _alg(obs, prior=copy.deepcopy(prior), beta=50.0); _update(on, obs)
    assert not all(torch.equal(a, b) for a, b in zip(_params(off), _params(on), strict=True))
    slow = torch.tensor(SLOW)
    gap = lambda alg: float((alg.policy.act_inference(obs)[slow] - prior.act_inference(obs)[slow]).square().sum(-1).mean())  # noqa: E731
    assert gap(on) < gap(off)
    assert "EX42_BC_PRIOR beta=50.0 loss=" in capsys.readouterr().out


def test_the_installed_ppo_path_refuses_the_prior():
    obs = _obs()
    alg = _alg(obs, mirror=False, prior=_policy(obs, 2), beta=1.0)
    with pytest.raises(ValueError, match="needs the critic-mirror update loop"):
        _update(alg, obs)


def test_settings_need_both_values_and_a_file(monkeypatch, tmp_path):
    monkeypatch.delenv(bcp.CKPT_ENV, raising=False); monkeypatch.delenv(bcp.BETA_ENV, raising=False)
    assert bcp.settings() is None
    monkeypatch.setenv(bcp.BETA_ENV, "1.0")
    with pytest.raises(ValueError, match="go together"):
        bcp.settings()
    monkeypatch.setenv(bcp.CKPT_ENV, str(tmp_path / "nothing.pt"))
    with pytest.raises(ValueError, match="is not a file"):
        bcp.settings()
    ck = tmp_path / "m.pt"; ck.write_bytes(b"x")
    monkeypatch.setenv(bcp.CKPT_ENV, str(ck))
    assert bcp.settings() == {"ckpt": str(ck), "beta": 1.0}
    for bad in ("-1", "nan", "x"):
        monkeypatch.setenv(bcp.BETA_ENV, bad)
        with pytest.raises(ValueError, match=bcp.BETA_ENV):
            bcp.settings()


def test_the_prior_is_a_frozen_strict_copy_and_the_runner_attaches_it_only_on_the_mirror_loop(monkeypatch, tmp_path, capsys):
    obs = _obs()
    parent = _policy(obs, 3)
    ck = tmp_path / "parent.pt"; torch.save({"model_state_dict": parent.state_dict()}, ck)
    policy = _policy(obs, 1)
    prior = bcp.load_prior(policy, str(ck), "cpu")
    assert prior is not policy and not any(p.requires_grad for p in prior.parameters()) and not prior.training
    assert torch.equal(prior.act_inference(obs), parent.act_inference(obs))
    other = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
                             actor_hidden_dims=[32, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)
    with pytest.raises(RuntimeError):
        bcp.load_prior(other, str(ck), "cpu")                                 # another architecture: refused
    runner = SimpleNamespace(device="cpu")
    monkeypatch.delenv(bcp.CKPT_ENV, raising=False); monkeypatch.delenv(bcp.BETA_ENV, raising=False)
    alg = _alg(obs); StartRunner._attach_bc_prior(runner, alg, alg.policy)
    assert alg.bc_prior is None
    monkeypatch.setenv(bcp.CKPT_ENV, str(ck)); monkeypatch.setenv(bcp.BETA_ENV, "0.5")
    StartRunner._attach_bc_prior(runner, alg, alg.policy)
    assert alg.bc_beta == 0.5 and torch.equal(alg.bc_prior.act_inference(obs), parent.act_inference(obs))
    assert "EX42_BC_PRIOR where=start beta=0.5 " in capsys.readouterr().out
    late = _alg(obs, mirror=False)                    # the real E2 order: the mirror is granted after the runner is built
    StartRunner._attach_bc_prior(runner, late, late.policy)
    assert late.bc_prior is not None
    from rsl_rl.algorithms import PPO
    plain = PPO(_policy(obs, 1), num_learning_epochs=1, num_mini_batches=1, device="cpu")
    with pytest.raises(ValueError, match="CriticMirrorPPO"):
        StartRunner._attach_bc_prior(runner, plain, plain.policy)
