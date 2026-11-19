"""EX42_ACTOR_MIRROR_ZMEAN (original side of the actor symmetry loss sees the latent z at its mean, like the mirror side). CPU only, real modules
(the real StartPerception, StartActorCritic, CriticMirrorPPO and the real StartRunner._ppo_obs bound to a stand-in object)."""

from __future__ import annotations

import copy

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners import ex42_actor_mirror as am
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO
from foothold_s2.runners.start_runner import StartRunner, correct_est_vx
from foothold_s2.tests.test_ex42_actor_mirror_cpu import N, _alg, _perception, _raw, _runner_stub


def test_zmean_env_var_parsing():
    assert am.actor_mirror_zmean({}) is False and am.actor_mirror_zmean({am.ENV_ZMEAN: ""}) is False
    assert am.actor_mirror_zmean({am.ENV_ZMEAN: "0"}) is False and am.actor_mirror_zmean({am.ENV_ZMEAN: "1"}) is True
    for bad in ("2", "true", "-1"):
        with pytest.raises(ValueError):
            am.actor_mirror_zmean({am.ENV_ZMEAN: bad})


def _inputs(g):
    return (torch.randn(N, 45, generator=g), torch.rand(N, 60, 60, generator=g), torch.randn(N, 32, 16, generator=g))


def test_step_pair_is_step_plus_the_mean_in_one_advance():
    perception = _perception()
    assert perception.cfg.sample_latent_in_rollout, "the test needs the sampling rollout"
    g = torch.Generator().manual_seed(21)
    s_pair, s_step, s_det = (perception.init_state(N, "cpu") for _ in range(3))
    for _ in range(5):
        o, d, m = _inputs(g)
        torch.manual_seed(100)
        sampled, mean = perception.step_pair(s_pair, perception.ingest(s_pair, o, d), m)
        torch.manual_seed(100)
        want = perception.step(s_step, perception.ingest(s_step, o, d), m)
        want_mean = perception.step(s_det, perception.ingest(s_det, o, d), m, deterministic=True)
        assert torch.equal(sampled, want)                       # the sampled estimate (and so the PPO input and the RNG stream) is unchanged
        assert torch.equal(mean, want_mean)                     # the mean estimate is what a deterministic step gives
        assert torch.equal(s_pair.h_prop, s_step.h_prop) and torch.equal(s_pair.h_terr, s_det.h_terr)   # one advance: same hidden state either way
    assert not torch.equal(sampled[:, :16], mean[:, :16]) and torch.equal(sampled[:, 16:], mean[:, 16:])   # only the latent z differs


def test_runner_path_stores_the_mean_z_actor_input_only_when_asked():
    g = torch.Generator().manual_seed(22)
    raw = _raw(g)
    on = _runner_stub(1.0)
    o, depth, gmap, *_ = StartRunner._split(raw)
    est, est_o = torch.randn(N, 51, generator=g), torch.randn(N, 51, generator=g)
    est_m = on._mirror_stream(o, depth, gmap)
    two = on._ppo_obs(raw, est, est_m)
    assert set(two.keys()) == {ACTOR_KEY, CRITIC_KEY, am.MIRROR_KEY}          # today's set while the switch is off
    three = on._ppo_obs(raw, est, est_m, est_o)
    assert set(three.keys()) == {ACTOR_KEY, CRITIC_KEY, am.MIRROR_KEY, am.ORIG_KEY}
    assert torch.equal(three[ACTOR_KEY], two[ACTOR_KEY]) and torch.equal(three[am.MIRROR_KEY], two[am.MIRROR_KEY])
    a_o = three[am.ORIG_KEY]
    assert a_o.shape == (N, 98) and torch.equal(a_o[:, :45], o) and torch.allclose(a_o[:, 45:96], correct_est_vx(est_o))
    assert torch.equal(a_o[:, 96:], three[ACTOR_KEY][:, 96:])                 # the pose command part is the same


def _alg_z(weight, zmean, orig):
    """_alg of the actor mirror tests, plus the stored mean-z input (orig = 'same' as the actor input, 'other', or None = not stored)."""
    alg = _alg(weight, with_key=True)
    alg.actor_mirror_zmean = zmean
    return alg


def _alg_with_orig(weight, zmean, orig_mode, steps=2):
    torch.manual_seed(11)
    g = torch.Generator().manual_seed(6)
    n = 32
    actor = torch.randn(n, 98, generator=g) * .1
    critic = torch.randn(n, 666, generator=g) * .1
    mirror = torch.randn(n, 98, generator=g) * .1
    fields = {ACTOR_KEY: actor, CRITIC_KEY: critic, am.MIRROR_KEY: mirror}
    if orig_mode == "same":
        fields[am.ORIG_KEY] = actor.clone()
    elif orig_mode == "other":
        fields[am.ORIG_KEY] = torch.randn(n, 98, generator=g) * .1
    obs = TensorDict(fields, [n])
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
                             actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)
    alg = CriticMirrorPPO(policy, num_learning_epochs=1, num_mini_batches=1, desired_kl=0.01, schedule="adaptive", device="cpu")
    alg.mirror_enabled = True
    alg.actor_mirror_weight = weight
    alg.actor_mirror_zmean = zmean
    alg.init_storage("rl", n, steps, obs, [12])
    torch.manual_seed(7)
    for _ in range(steps):
        with torch.inference_mode():
            alg.act(obs)
            alg.process_env_step(obs, torch.randn(n), torch.zeros(n), {"ex41_ppo_valid": torch.ones(n, dtype=torch.bool)})
    alg.compute_returns(obs)
    return alg


def test_update_zmean_equals_today_when_the_mean_input_is_the_actor_input_and_differs_otherwise():
    base = _alg_with_orig(5.0, False, "same")
    r0 = base.update()
    same = _alg_with_orig(5.0, True, "same")                           # mean-z input == the sampled input: the same loss and the same step (the original side is a second forward, so only summation order may differ)
    r1 = same.update()
    assert r1["actor_mirror"] == pytest.approx(r0["actor_mirror"], rel=1e-6)
    for a, b in zip(base.policy.state_dict().values(), same.policy.state_dict().values()):
        assert torch.allclose(a, b, atol=1e-6, rtol=1e-5)
    other = _alg_with_orig(5.0, True, "other")
    r2 = other.update()
    assert abs(r2["actor_mirror"] - r0["actor_mirror"]) > 1e-4 and r2["actor_mirror"] > 0
    sd0, sd2 = base.policy.state_dict(), other.policy.state_dict()
    assert any(not torch.equal(sd0[k], sd2[k]) for k in sd0 if k.startswith("actor."))
    assert all(torch.equal(sd0[k], sd2[k]) for k in sd0 if k.startswith("critic."))


def test_update_zmean_stops_without_the_stored_input_and_does_nothing_while_the_weight_is_zero():
    with pytest.raises(ValueError, match="stored no mean-z actor input"):
        _alg_with_orig(1.0, True, None).update()
    off = _alg_with_orig(0.0, False, None)
    off.update()
    z0 = _alg_with_orig(0.0, True, "other")                            # weight 0: the switch changes nothing
    z0.update()
    for a, b in zip(off.policy.state_dict().values(), z0.policy.state_dict().values()):
        assert torch.equal(a, b)


def test_mean_z_on_both_sides_gives_zero_loss_for_a_symmetric_policy_but_the_sampled_original_side_does_not():
    g = torch.Generator().manual_seed(23)
    n = 64
    w = torch.randn(45 + 51, 12, generator=g)

    def m_in(x):                                                       # the input mirror of this test: o45 mirrored, est reversed in sign (a stand-in for the latent mirror)
        return torch.cat([am.mirror_proprio(x[..., :45]), -x[..., 45:]], -1)

    def raw(x):
        return x @ w

    def symmetric(x):                                                  # exactly symmetric under (m_in, mirror_action)
        return 0.5 * (raw(x) + am.mirror_action(raw(m_in(x))))

    o = torch.randn(n, 45, generator=g)
    est_mean = torch.randn(n, 51, generator=g)
    est_sampled = est_mean + 0.3 * torch.randn(n, 51, generator=g)     # the rollout's sampled latent
    x_mean, x_sampled = torch.cat([o, est_mean], -1), torch.cat([o, est_sampled], -1)
    mirror_in = m_in(x_mean)                                           # the mirror stream always carries the mean latent
    like_with_like = am.symmetry_loss(symmetric(x_mean), symmetric(mirror_in))
    sampled_vs_mean = am.symmetry_loss(symmetric(x_sampled), symmetric(mirror_in))
    assert float(like_with_like) < 1e-10
    assert float(sampled_vs_mean) > 1e-3
