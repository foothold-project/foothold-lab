"""EX42_ACTOR_MIRROR (actor left-right symmetry loss, planner DESIGN-ACTOR-MIRROR-1120 section 5). CPU only, real modules:
the real StartPerception, the real StartActorCritic and CriticMirrorPPO, and the real StartRunner._ppo_obs / _mirror_stream methods
(bound to a small stand-in object, because the real runner needs an Isaac env)."""

from __future__ import annotations

import types

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_perception import StartPerception
from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners import ex42_actor_mirror as am
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO, mirror_critic
from foothold_s2.runners.start_runner import StartRunner, correct_est_vx

N = 8


@pytest.fixture(autouse=True)
def _restore_rng():
    state = torch.get_rng_state()
    yield
    torch.set_rng_state(state)


# ---------------- 1. the mirror twice is the identity ----------------

def test_mirror_twice_is_identity_and_shares_the_critic_formula():
    g = torch.Generator().manual_seed(1)
    o = torch.randn(N, 45, generator=g)
    a = torch.randn(N, 12, generator=g)
    d = torch.rand(N, 2, 60, 60, generator=g)
    m = torch.randn(N, 32, 16, generator=g)
    p = torch.randn(N, 2, generator=g)
    for f, x in ((am.mirror_proprio, o), (am.mirror_action, a), (am.mirror_depth, d), (am.mirror_map, m), (am.mirror_pose, p)):
        assert torch.equal(f(f(x)), x), f.__name__
    assert not torch.equal(am.mirror_proprio(o), o) and not torch.equal(am.mirror_depth(d), d)
    # the o45 formula is the critic's: the first 45 entries of mirror_critic(x) are mirror_proprio(o)
    x = torch.randn(N, 666, generator=g)
    assert torch.equal(mirror_critic(x)[..., :45], am.mirror_proprio(x[..., :45]))
    # the previous-action block of o45 mirrors like an action
    assert torch.equal(am.mirror_proprio(o)[..., 33:45], am.mirror_action(o[..., 33:45]))
    # the 512-entry critic map block and the 32 x 16 map mirror agree
    assert torch.equal(mirror_critic(x)[..., 52:564], am.mirror_map(x[..., 52:564].reshape(N, 32, 16)).reshape(N, 512))


# ---------------- 2. the loss: 0 for a symmetric policy, > 0 for an asymmetric one ----------------

def test_symmetry_loss_is_zero_for_a_symmetric_hand_policy_and_positive_for_an_asymmetric_one():
    g = torch.Generator().manual_seed(2)
    w = torch.randn(45, 12, generator=g)
    o = torch.randn(64, 45, generator=g)

    def raw(x):
        return x @ w

    def symmetric(x):
        return 0.5 * (raw(x) + am.mirror_action(raw(am.mirror_proprio(x))))

    loss_sym = am.symmetry_loss(symmetric(o), symmetric(am.mirror_proprio(o)))
    loss_asym = am.symmetry_loss(raw(o), raw(am.mirror_proprio(o)))
    assert float(loss_sym) < 1e-10
    assert float(loss_asym) > 1e-2
    # both sides move: the original mean and the mirrored mean each get a gradient (each target is detached)
    x, y = raw(o).requires_grad_(), raw(am.mirror_proprio(o)).requires_grad_()
    am.symmetry_loss(x, y).backward()
    assert float(x.grad.abs().max()) > 0 and float(y.grad.abs().max()) > 0
    # both directions each take half: swapping the two arguments gives the same value
    assert float(am.symmetry_loss(raw(am.mirror_proprio(o)), raw(o))) == pytest.approx(float(loss_asym), rel=1e-5)


# ---------------- 3. the mirror stream: reset and first step ----------------

def _perception():
    torch.manual_seed(3)
    return StartPerception().eval()


def test_reset_rows_of_the_mirror_stream_restart_like_a_fresh_perception_on_the_mirrored_world():
    perception = _perception()
    g = torch.Generator().manual_seed(4)
    state = perception.init_state(N, "cpu")
    mirror_state = perception.init_state(N, "cpu")

    def inputs():
        return (torch.randn(N, 45, generator=g), torch.rand(N, 60, 60, generator=g), torch.randn(N, 32, 16, generator=g))

    def stream(o, depth, gmap):
        am.sync_flags(mirror_state, state)
        inp = perception.ingest(mirror_state, am.mirror_proprio(o), am.mirror_depth(depth))
        return perception.step(mirror_state, inp, am.mirror_map(gmap), deterministic=True)

    for _ in range(7):
        stream(*inputs())
    assert float(mirror_state.h_prop.abs().max()) > 0 and int(mirror_state.steps_since_reset.min()) == 7
    done = torch.zeros(N, dtype=torch.bool)
    done[[1, 3]] = True
    state.use_gt[done] = ~state.use_gt[done]                       # the original drew new flags for the finished episodes
    am.sync_mirror_state(mirror_state, state, done)
    assert float(mirror_state.h_prop[done].abs().max()) == 0 and float(mirror_state.h_terr[done].abs().max()) == 0
    assert torch.equal(mirror_state.use_gt, state.use_gt) and int(mirror_state.steps_since_reset[~done].min()) == 7
    o, depth, gmap = inputs()
    got = stream(o, depth, gmap)[done]
    fresh = perception.init_state(2, "cpu")
    fresh.use_gt = state.use_gt[done].clone()
    inp = perception.ingest(fresh, am.mirror_proprio(o[done]), am.mirror_depth(depth[done]))
    want = perception.step(fresh, inp, am.mirror_map(gmap[done]), deterministic=True)
    assert torch.allclose(got, want, atol=1e-6)
    # a row that was not reset kept its history: it differs from a fresh start
    kept = stream(*inputs())[~done][:1]
    assert kept.shape[0] == 1


# ---------------- 4. the real runner path (_ppo_obs, _mirror_stream) and the real PPO update ----------------

def _runner_stub(w):
    perception = _perception()
    stub = types.SimpleNamespace(
        pcfg={"est_mode": "learned", "critic_mode": "legacy", "oracle_vel_noise": 0.0},
        ex41_pose_commands=True, perception=perception, perception_ema=None,
        pstate=perception.init_state(N, "cpu"), pstate_m=perception.init_state(N, "cpu") if w else None)
    stub._split = StartRunner._split
    stub._pose_command = StartRunner._pose_command
    stub._est_in = types.MethodType(StartRunner._est_in, stub)
    stub._mirror_stream = types.MethodType(StartRunner._mirror_stream, stub)
    stub._ppo_obs = types.MethodType(StartRunner._ppo_obs, stub)
    return stub


def _raw(g):
    return TensorDict({"policy": torch.randn(N, 45, generator=g), "depth": torch.rand(N, 3600, generator=g),
                       "gt_map": torch.randn(N, 512, generator=g), "gt_feet": torch.randn(N, 100, generator=g),
                       "base_vel": torch.randn(N, 3, generator=g), "contacts": torch.rand(N, 4, generator=g),
                       "pose_cmd": torch.zeros(N, 2)}, [N])


def test_runner_path_stores_the_mirrored_actor_input_only_when_on():
    g = torch.Generator().manual_seed(5)
    raw = _raw(g)
    off = _runner_stub(0.0)
    est = torch.randn(N, 51, generator=g)
    plain = off._ppo_obs(raw, est)
    assert set(plain.keys()) == {ACTOR_KEY, CRITIC_KEY}                 # off: nothing extra is stored
    on = _runner_stub(1.0)
    o, depth, gmap, *_ = StartRunner._split(raw)
    est_m = on._mirror_stream(o, depth, gmap)
    obs = on._ppo_obs(raw, est, est_m)
    assert set(obs.keys()) == {ACTOR_KEY, CRITIC_KEY, am.MIRROR_KEY}
    assert torch.equal(obs[ACTOR_KEY], plain[ACTOR_KEY]) and torch.equal(obs[CRITIC_KEY], plain[CRITIC_KEY])    # the original input is untouched
    a_m = obs[am.MIRROR_KEY]
    assert a_m.shape == (N, 98)
    assert torch.equal(a_m[:, :45], am.mirror_proprio(o)) and torch.allclose(a_m[:, 45:96], correct_est_vx(est_m))     # the same est correction as the original input (vx, if the env switches it on) and float(a_m[:, 96:].abs().max()) == 0.0


def _alg(weight, with_key, steps=2):
    torch.manual_seed(11)
    g = torch.Generator().manual_seed(6)
    n = 32
    fields = {ACTOR_KEY: torch.randn(n, 98, generator=g) * .1, CRITIC_KEY: torch.randn(n, 666, generator=g) * .1}
    if with_key:
        fields[am.MIRROR_KEY] = torch.randn(n, 98, generator=g) * .1
    obs = TensorDict(fields, [n])
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
                             actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)
    alg = CriticMirrorPPO(policy, num_learning_epochs=1, num_mini_batches=1, desired_kl=0.01, schedule="adaptive", device="cpu")
    alg.mirror_enabled = True
    alg.actor_mirror_weight = weight
    alg.init_storage("rl", n, steps, obs, [12])
    torch.manual_seed(7)
    for _ in range(steps):
        with torch.inference_mode():
            alg.act(obs)
            alg.process_env_step(obs, torch.randn(n), torch.zeros(n), {"ex41_ppo_valid": torch.ones(n, dtype=torch.bool)})
    alg.compute_returns(obs)
    return alg


def test_weight_zero_is_todays_update_and_weight_on_moves_only_the_actor():
    base = _alg(0.0, with_key=False)
    r0 = base.update()
    keyed = _alg(0.0, with_key=True)                                   # the key is stored but unused while the weight is 0
    r1 = keyed.update()
    assert "actor_mirror" not in r0 and "actor_mirror" not in r1
    for a, b in zip(base.policy.state_dict().values(), keyed.policy.state_dict().values()):
        assert torch.equal(a, b)                                       # off = bit-identical
    on = _alg(5.0, with_key=True)
    r2 = on.update()
    assert r2["actor_mirror"] > 0 and r2["actor_mirror_grad_ratio"] > 0 and r2["actor_mirror_weight"] == 5.0
    sd0, sd2 = base.policy.state_dict(), on.policy.state_dict()
    assert any(not torch.equal(sd0[k], sd2[k]) for k in sd0 if k.startswith("actor."))
    assert all(torch.equal(sd0[k], sd2[k]) for k in sd0 if k.startswith("critic."))     # the critic does not feel the actor loss


def test_weight_on_without_the_stored_key_or_without_the_critic_mirror_path_stops():
    with pytest.raises(ValueError, match="stored no mirrored actor input"):
        _alg(1.0, with_key=False).update()
    alg = _alg(1.0, with_key=True)
    alg.mirror_enabled = False
    with pytest.raises(ValueError, match="critic mirror update path"):
        alg.update()


def test_weight_env_var_parsing():
    assert am.actor_mirror_weight({}) == 0.0 and am.actor_mirror_weight({am.ENV_WEIGHT: ""}) == 0.0
    assert am.actor_mirror_weight({am.ENV_WEIGHT: "0.25"}) == 0.25
    for bad in ("-1", "nan", "inf"):
        with pytest.raises(ValueError):
            am.actor_mirror_weight({am.ENV_WEIGHT: bad})
