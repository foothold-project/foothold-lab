"""v28p: a share of the envs acts with the mean action (noise exactly 0). Their rows are not PPO samples (no surrogate, value,
entropy, bounds, scheduler KL, advantage statistics) but the perception replay still holds them. Share 0 changes nothing. CPU only."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_policy import ACTOR_KEY
from foothold_s2.runners import ex41_critic_mirror as mirror
from foothold_s2.runners.ex41_critic_mirror import mean_action_mask, small_noise_mask
from foothold_s2.runners.perception_replay import PerceptionReplay
from foothold_s2.tests.test_ex42_small_noise_cpu import N, _alg, _obs

STEPS = 3


def _alg_mean(share, steps=STEPS):
    alg, obs = _alg(None, steps=steps)
    alg.mean_action_mask = mean_action_mask(N, share)
    alg.normalize_advantage_per_mini_batch = False
    return alg, obs


def _rollout(alg, obs, rewards_for_mean=0.0, seed=11, steps=STEPS):
    torch.manual_seed(seed)
    mask = alg.mean_action_mask
    for _ in range(steps):
        reward = torch.linspace(-1, 1, N)
        if mask is not None:
            reward = torch.where(mask, torch.full_like(reward, rewards_for_mean), reward)
        with torch.inference_mode():
            alg.act(obs)
            alg.process_env_step(obs, reward, torch.zeros(N), {"ex41_ppo_valid": torch.ones(N, dtype=torch.bool)})
    alg.compute_returns(obs)


def test_constants_and_the_helper():
    assert mirror.MEAN_ACTION_PERCEPTION_SHARE == 0.12
    assert mirror.SMALL_NOISE_LOWSPEED_CMD == 0.0 and mirror.SMALL_NOISE_ENV_SHARE == 0.25 and mirror.SMALL_NOISE_SIGMA_SCALE == 0.2   # v28f-like
    assert mirror.small_noise_static_share() == 0.25
    assert mean_action_mask(N, 0.0) is None
    mask = mean_action_mask(1024, 0.12)
    assert mask.dtype == torch.bool and int(mask.sum()) == 122 and torch.equal(mask, small_noise_mask(1024, 0.12))


def test_the_mean_envs_act_with_exactly_the_mean_and_the_others_are_sampled():
    alg, obs = _alg_mean(0.25)
    torch.manual_seed(3)
    with torch.inference_mode():
        actions = alg.act(obs).clone()
    mask = alg.mean_action_mask
    mean = alg.transition.action_mean
    assert int(mask.sum()) == N // 4
    assert torch.equal(actions[mask], mean[mask])                       # noise exactly 0
    assert (actions[~mask] != mean[~mask]).all()                        # the other envs still sample
    assert torch.equal(alg.transition.actions, actions)                 # the stored action is the one the env gets


def test_mean_rows_are_invalid_for_ppo_and_a_quarantine_flag_still_counts():
    alg, obs = _alg_mean(0.25)
    quarantined = torch.zeros(N, dtype=torch.bool)
    quarantined[1] = True                                               # env 1 is not a mean env (mean envs are 3, 7, ...)
    with torch.inference_mode():
        alg.act(obs)
        alg.process_env_step(obs, torch.zeros(N), torch.zeros(N), {"ex41_ppo_valid": ~quarantined})
    valid = alg.storage.valid[0]
    assert torch.equal(valid, ~(alg.mean_action_mask | quarantined))


def test_ppo_never_sees_the_mean_rows_and_the_scheduler_kl_and_advantage_statistics_exclude_them():
    base, obs = _alg_mean(0.25)
    _rollout(base, obs, rewards_for_mean=0.0)
    other = copy.deepcopy(base)                                         # same weights, same stored rollout
    mask = base.mean_action_mask
    flat = lambda x: x.flatten(0, 1)                                    # noqa: E731
    row = flat(mask[None, :].expand(STEPS, N))                          # [step * env] rows of the mean envs
    for tensor in (other.storage.actions, other.storage.values, other.storage.returns, other.storage.advantages,
                   other.storage.mu, other.storage.sigma, other.storage.actions_log_prob):
        view = tensor.flatten(0, 1)
        view[row] = view[row] * 7.0 + 123.0                              # scribble over the mean rows only
    other.storage.observations[ACTOR_KEY][:, mask] += 9.0
    # the scribbled copy has to produce exactly the same update: those rows are never yielded
    torch.manual_seed(5)
    a = base.update()
    torch.manual_seed(5)
    b = other.update()
    assert a["surrogate"] == b["surrogate"] and a["value_function"] == b["value_function"] and a["entropy"] == b["entropy"]
    assert base.learning_rate == other.learning_rate                    # the adaptive-lr KL did not see them
    for p, q in zip(base.policy.parameters(), other.policy.parameters(), strict=True):
        assert torch.equal(p, q)


def test_advantage_normalisation_uses_the_valid_rows_only():
    a, obs_a = _alg_mean(0.25)
    _rollout(a, obs_a, rewards_for_mean=0.0)
    b, obs_b = _alg_mean(0.25)
    _rollout(b, obs_b, rewards_for_mean=1000.0)                         # huge rewards on the mean envs
    valid = a.storage.valid
    assert torch.equal(valid, b.storage.valid) and not bool(valid.all())
    assert torch.equal(a.storage.advantages[valid], b.storage.advantages[valid])        # their statistics did not move
    x = a.storage.advantages[valid]
    assert float(x.mean()) == pytest.approx(0.0, abs=1e-5) and float(x.std()) == pytest.approx(1.0, abs=1e-3)


def test_share_zero_is_the_old_path_bit_for_bit():
    off, obs = _alg_mean(0.0)
    assert off.mean_action_mask is None
    ref, obs2 = _alg(None, steps=STEPS)
    ref.normalize_advantage_per_mini_batch = False
    _rollout(off, obs)
    _rollout(ref, obs2)
    assert off.storage.valid.all() and torch.equal(off.storage.actions, ref.storage.actions)
    torch.manual_seed(2)
    a = off.update()
    torch.manual_seed(2)
    b = ref.update()
    assert a == b
    for p, q in zip(off.policy.parameters(), ref.policy.parameters(), strict=True):
        assert torch.equal(p, q)


def test_checkpoint_keys_do_not_change():
    alg, _ = _alg_mean(0.25)
    ref, _ = _alg(None)
    assert list(alg.policy.state_dict().keys()) == list(ref.policy.state_dict().keys())
    assert list(alg.optimizer.state_dict()["param_groups"][0].keys()) == list(ref.optimizer.state_dict()["param_groups"][0].keys())
    assert not any("mean_action" in k for k in alg.policy.state_dict())


def test_the_perception_replay_holds_every_env_whatever_ppo_marks_valid():
    replay = PerceptionReplay(num_envs=N, num_steps=2, device="cpu")
    mask = mean_action_mask(N, 0.25)
    seen = torch.cat([idx for idx in replay.env_batches(num_minibatches=4, num_epochs=1)])
    assert sorted(seen.tolist()) == list(range(N)) and bool(torch.isin(torch.nonzero(mask).flatten(), seen).all())
    assert replay.gather(torch.nonzero(mask).flatten())["obs"].shape[1] == int(mask.sum())


def _runner(alg, mirror_on=True):
    from foothold_s2.runners import start_runner
    runner = object.__new__(start_runner.StartRunner)
    runner.ex41_pose_commands, runner.ex41_critic_mirror, runner.ex41_mirror_approval = True, mirror_on, None
    runner.alg, runner.device, runner.env = alg, "cpu", SimpleNamespace(num_envs=N)
    runner.disable_logs, runner.is_distributed = True, False
    runner.pcfg = {"est_mode": "learned"}
    return runner


def test_runner_hands_the_mask_to_the_algorithm_and_off_switches_remove_it(monkeypatch):
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner._apply_small_noise()
    assert torch.equal(alg.mean_action_mask, mean_action_mask(N, 0.12)) and runner._mean_action is alg.mean_action_mask
    monkeypatch.setattr(mirror, "MEAN_ACTION_PERCEPTION_SHARE", 0.0)
    runner._apply_small_noise()
    assert alg.mean_action_mask is None and runner._mean_action is None
    monkeypatch.undo()
    off = _runner(alg, mirror_on=False)
    off._apply_small_noise()
    assert alg.mean_action_mask is None


def test_bias_of_the_mean_envs_is_recorded_apart_from_all_envs():
    from foothold_s2.models import start_perception as sp
    alg, _ = _alg(None)
    runner = _runner(alg)
    runner._apply_small_noise()
    runner._vbias_samples, runner._vbias_mean_samples = [], []
    mean = runner._mean_action
    o = torch.zeros(N, 12)
    o[:, 6] = 0.1                                                       # every command is in the 0.05 to 0.15 band
    vel = torch.zeros(N, 3)
    k = o.shape[-1] + sp.Z_DIM
    est = torch.zeros(N, k + sp.V_DIM)
    est[:, k] = torch.where(mean, torch.tensor(0.5), torch.tensor(0.1))   # the mean envs read 0.5 too high, the others 0.1
    ppo_obs = {ACTOR_KEY: est}
    for _ in range(3):
        runner._vbias_collect(o, ppo_obs, vel)
    runner._vbias_finish(4)
    assert runner.last_perception_v_bias["n"] == 3 * N and runner.last_perception_v_bias_mean_action["n"] == 3 * int(mean.sum())
    assert runner.last_perception_v_bias_mean_action["mean"] == pytest.approx(0.5)
    assert runner.last_perception_v_bias["mean"] == pytest.approx(0.5 * float(mean.float().mean()) + 0.1 * (1 - float(mean.float().mean())))
    assert runner._v_bias_record()["mean_action_lowband"]["n"] == 3 * int(mean.sum()) and runner._vbias_mean_samples == []
