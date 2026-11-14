"""Small-noise envs candidate (off by default): the scaled std is part of the policy of those envs, so the stored log-prob,
sigma, the re-evaluated log-prob and the KL all use the same per-sample std and PPO stays on-policy. CPU only."""

from __future__ import annotations

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.ex42_live_metrics import SLOT_INDEX, LiveMetrics
from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners import ex41_critic_mirror as mirror
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO, small_noise_mask, small_noise_scale

N = 64
SCALE = 0.2


@pytest.fixture(autouse=True)
def _restore_rng():
    state = torch.get_rng_state()
    yield
    torch.set_rng_state(state)


def _obs(n=N):
    g = torch.Generator().manual_seed(5)
    return TensorDict({ACTOR_KEY: torch.randn(n, 98, generator=g) * .1,
                       CRITIC_KEY: torch.randn(n, 666, generator=g) * .1}, [n])


def _alg(scale_env, n=N, steps=2):
    torch.manual_seed(89)
    obs = _obs(n)
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
                             actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)
    alg = CriticMirrorPPO(policy, num_learning_epochs=1, num_mini_batches=1, desired_kl=0.01,
                         schedule="adaptive", device="cpu")
    alg.mirror_enabled = True
    alg.init_storage("rl", n, steps, obs, [12])
    if scale_env is not None:
        alg.storage.noise_scale_env = scale_env
        policy.noise_scale = scale_env
    return alg, obs


def _rollout(alg, obs, steps=2, seed=7):
    torch.manual_seed(seed)
    n = obs.batch_size[0]
    for _ in range(steps):
        with torch.inference_mode():
            alg.act(obs)
            alg.process_env_step(obs, torch.zeros(n), torch.zeros(n), {"ex41_ppo_valid": torch.ones(n, dtype=torch.bool)})
    alg.compute_returns(obs)


def test_mask_is_exact_even_and_reproducible_and_on_by_default_share_zero_is_off():
    assert mirror.SMALL_NOISE_ENV_SHARE == 0.25 and mirror.SMALL_NOISE_SIGMA_SCALE == 0.2      # on by default (lead 19:28)
    assert small_noise_scale(N, 0.0, SCALE) is None and StartActorCritic.noise_scale is None   # share 0: nothing set
    mask = small_noise_mask(N, 0.25)
    assert int(mask.sum()) == 16 and mask.tolist() == small_noise_mask(N, 0.25).tolist()
    assert all(int(mask[i:i + 4].sum()) == 1 for i in range(0, N, 4))            # spread over the index, one in four
    assert int(small_noise_mask(1024, 0.25).sum()) == 256 and int(small_noise_mask(10, 0.3).sum()) == 3
    scale = small_noise_scale(N, 0.25, SCALE)
    assert scale.shape == (N, 1) and sorted(set(scale.flatten().tolist())) == [pytest.approx(SCALE), 1.0]
    for bad in (-0.1, 1.0):
        with pytest.raises(ValueError):
            small_noise_mask(N, bad)
    for bad in (0.0, 1.0):
        with pytest.raises(ValueError):
            small_noise_scale(N, 0.25, bad)


def test_scale_one_path_is_transparent_to_the_unscaled_update():
    base, obs = _alg(None)
    _rollout(base, obs)
    base.update()
    ones, obs = _alg(torch.ones(N, 1))
    _rollout(ones, obs)
    ones.update()
    for a, b in zip(base.policy.state_dict().values(), ones.policy.state_dict().values()):
        assert torch.equal(a, b)


def test_only_marked_envs_sample_with_the_scaled_std_same_noise_draw():
    scale = small_noise_scale(N, 0.25, SCALE)
    noisy = small_noise_mask(N, 0.25)
    plain, obs = _alg(None)
    _rollout(plain, obs, steps=1)
    scaled, obs = _alg(scale)
    _rollout(scaled, obs, steps=1)
    mu = plain.storage.mu[0]
    dev_plain = plain.storage.actions[0] - mu
    dev_scaled = scaled.storage.actions[0] - scaled.storage.mu[0]
    assert torch.allclose(dev_scaled[~noisy], dev_plain[~noisy], atol=1e-6)
    assert torch.allclose(dev_scaled[noisy], dev_plain[noisy] * SCALE, atol=1e-6)
    std = plain.policy.std
    assert torch.allclose(scaled.storage.sigma[0][noisy], (std * SCALE).expand(int(noisy.sum()), 12))
    assert torch.allclose(scaled.storage.sigma[0][~noisy], std.expand(int((~noisy).sum()), 12))


def test_stored_log_prob_is_the_sampling_distribution_and_the_update_reevaluates_with_the_same_scale():
    scale = small_noise_scale(N, 0.25, SCALE)
    noisy = small_noise_mask(N, 0.25)
    alg, obs = _alg(scale)
    _rollout(alg, obs)
    st = alg.storage
    for step in range(2):
        expected = torch.distributions.Normal(st.mu[step], st.sigma[step]).log_prob(st.actions[step]).sum(-1)
        assert torch.allclose(st.actions_log_prob[step].flatten(), expected, atol=1e-4)
        alg.policy.noise_scale = scale                              # the update's per-row scale: ratio 1, KL 0
        alg.policy.act(obs)
        again = alg.policy.get_actions_log_prob(st.actions[step])
        assert torch.allclose(again, st.actions_log_prob[step].flatten(), atol=1e-4)
        kl = torch.sum(torch.log(alg.policy.action_std / st.sigma[step] + 1e-5)
                       + (st.sigma[step].square() + (st.mu[step] - alg.policy.action_mean).square())
                       / (2.0 * alg.policy.action_std.square()) - 0.5, dim=-1)
        assert kl.abs().max() < 1e-3
        alg.policy.noise_scale = None                               # a wrong (unscaled) assumption breaks exactly those rows
        alg.policy.act(obs)
        wrong = alg.policy.get_actions_log_prob(st.actions[step])
        assert torch.allclose(wrong[~noisy], st.actions_log_prob[step].flatten()[~noisy], atol=1e-4)
        assert (wrong[noisy] - st.actions_log_prob[step].flatten()[noisy]).abs().min() > 1.0
    alg.policy.noise_scale = scale


def test_update_ratio_starts_at_one_for_every_row_and_records_the_share():
    scale = small_noise_scale(N, 0.25, SCALE)
    alg, obs = _alg(scale)
    _rollout(alg, obs)
    advantage = alg.storage.advantages.flatten(0, 1).flatten().clone()
    alg.normalize_advantage_per_mini_batch = False
    losses = alg.update()
    assert losses["surrogate"] == pytest.approx(-float(advantage.mean()), abs=1e-5)       # ratio exactly 1 on all rows
    assert losses["small_noise_env_share"] == pytest.approx(0.25)
    assert losses["small_noise_sigma_scale"] == pytest.approx(SCALE)
    assert alg.policy.noise_scale is alg.storage.noise_scale_env                          # rollout scale back after update
    off, obs = _alg(None)
    _rollout(off, obs)
    assert "small_noise_env_share" not in off.update()


def test_runner_wiring_refuses_the_installed_update_and_sets_both_sides(monkeypatch):
    import inspect

    from foothold_s2.runners import start_runner
    src = inspect.getsource(start_runner.StartRunner._construct_algorithm)
    assert "small_noise_scale" in src and "noise_scale_env" in src and "policy.noise_scale" in src
    assert "if not self.ex41_critic_mirror:" in src and "installed PPO.update" in src


def test_live_metrics_tracks_noisy_envs_apart_and_keeps_the_row_unchanged_when_off(tmp_path):
    noisy = torch.tensor([True, False, False, False, False])
    cmd = torch.tensor([[.2, 0, 0]] * 5)
    vel = torch.tensor([[.2, 0, 0], [.1, 0, 0], [.1, 0, 0], [.1, 0, 0], [.1, 0, 0]])
    slot = torch.full((5,), SLOT_INDEX["forward"])
    args = (cmd, vel, slot, torch.zeros(5, dtype=torch.bool), torch.zeros(5, dtype=torch.bool),
            torch.ones(5, dtype=torch.long), torch.zeros(5, dtype=torch.long), torch.zeros(5, dtype=torch.bool))
    on = LiveMetrics(tmp_path / "on", noise_envs=noisy, noise_sigma_scale=SCALE)
    on.begin(1, device="cpu")
    on.add(*args)
    row = on.end()
    assert row["small_noise"]["env_share"] == pytest.approx(0.2) and row["small_noise"]["sigma_scale"] == SCALE
    groups = row["small_noise"]["slow_forward"]
    assert groups["noisy"] == {"samples": 1, "tracking_ratio": 1.0, "stall_fraction": 0.0}
    assert groups["rest"]["samples"] == 4 and groups["rest"]["tracking_ratio"] == pytest.approx(0.5)
    off = LiveMetrics(tmp_path / "off")
    off.begin(1, device="cpu")
    off.add(*args)
    assert "small_noise" not in off.end()
    wrong = LiveMetrics(tmp_path / "wrong", noise_envs=noisy[:3])
    wrong.begin(1, device="cpu")
    with pytest.raises(ValueError, match="mask differs"):
        wrong.add(*args)


def test_rollout_returns_to_the_per_env_scale_even_after_an_interrupted_update():
    scale = small_noise_scale(N, 0.25, SCALE)
    alg, obs = _alg(scale)
    alg.policy.noise_scale = torch.full((5, 1), 0.5)            # what an update interrupted mid-minibatch would leave
    _rollout(alg, obs, steps=1)
    assert alg.policy.noise_scale is alg.storage.noise_scale_env
    noisy = small_noise_mask(N, 0.25)
    assert torch.allclose(alg.storage.sigma[0][noisy], (alg.policy.std * SCALE).expand(int(noisy.sum()), 12))


def test_training_entry_hands_the_shared_mask_to_the_live_metrics_only_when_on(monkeypatch):
    from types import SimpleNamespace

    from foothold_s2.scripts.ex42_training_entry import EX42StageZeroRuntime
    fake = SimpleNamespace(env=SimpleNamespace(num_envs=N))
    monkeypatch.setattr(mirror, "SMALL_NOISE_ENV_SHARE", 0.0)
    assert EX42StageZeroRuntime._small_noise_record(fake) == {}                   # share 0: the row stays as it was
    monkeypatch.setattr(mirror, "SMALL_NOISE_ENV_SHARE", 0.25)
    monkeypatch.setattr(mirror, "SMALL_NOISE_SIGMA_SCALE", SCALE)
    record = EX42StageZeroRuntime._small_noise_record(fake)
    assert record["noise_sigma_scale"] == SCALE and record["noise_envs"].tolist() == small_noise_mask(N, 0.25).tolist()


def test_resume_first_update_keeps_the_same_env_split_and_sigma_handling(tmp_path):
    """A checkpoint holds weights and optimizer only; the split is a pure function of the env index, so a resumed run rebuilds
    the same scale and its first update (ratio 1 for every row) behaves like any other update."""
    scale = small_noise_scale(N, mirror.SMALL_NOISE_ENV_SHARE, mirror.SMALL_NOISE_SIGMA_SCALE)
    first, obs = _alg(scale)
    _rollout(first, obs)
    first.update()
    state = {"model": first.policy.state_dict(), "optimizer": first.optimizer.state_dict()}
    assert "noise_scale" not in "".join(state["model"].keys())
    torch.save(state, tmp_path / "model_250.pt")
    resumed, obs = _alg(small_noise_scale(N, mirror.SMALL_NOISE_ENV_SHARE, mirror.SMALL_NOISE_SIGMA_SCALE))
    loaded = torch.load(tmp_path / "model_250.pt")
    resumed.policy.load_state_dict(loaded["model"])
    resumed.optimizer.load_state_dict(loaded["optimizer"])
    assert torch.equal(resumed.storage.noise_scale_env, first.storage.noise_scale_env)
    assert resumed.policy.noise_scale is resumed.storage.noise_scale_env
    _rollout(resumed, obs, seed=11)
    noisy = small_noise_mask(N, mirror.SMALL_NOISE_ENV_SHARE)
    assert torch.allclose(resumed.storage.sigma[0][noisy],
                          (resumed.policy.std * mirror.SMALL_NOISE_SIGMA_SCALE).expand(int(noisy.sum()), 12))
    advantage = resumed.storage.advantages.flatten(0, 1).flatten().clone()
    resumed.normalize_advantage_per_mini_batch = False
    losses = resumed.update()
    assert losses["surrogate"] == pytest.approx(-float(advantage.mean()), abs=1e-5)       # ratio 1 on all rows after the load
    assert losses["small_noise_env_share"] == pytest.approx(0.25)
