"""CPU checks for the optional EX-42 actor mirror loss on the real START policy path."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import torch

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY
from foothold_s2.models.start_perception import PerceptionCfg, StartPerception
from foothold_s2.runners.ex41_critic_mirror import EXPECTED_JOINT_NAMES, mirror_critic
from foothold_s2.runners import ex41_critic_mirror as critic_mirror_module
from foothold_s2.runners import ex42_actor_mirror as mirror_module
from foothold_s2.runners.ex42_actor_mirror import (
    actor_mirror_loss, flat_map_mask, mirror_action, mirror_actor_observation, weight_from_env,
)
from foothold_s2.tests.ex41_authorization_fixture import real_authorization
from foothold_s2.tests.test_ex41_b345 import PoseEnv
from foothold_s2.tests.start_fake_env import train_cfg
from foothold_s2.runners.start_runner import StartRunner


def test_gate_and_real_runner_observation_path(monkeypatch, tmp_path, capsys):
    for raw in ("-0.1", "nan", "inf", "invalid"):
        monkeypatch.setenv("EX42_ACTOR_MIRROR_W", raw)
        with pytest.raises(ValueError, match="EX42_ACTOR_MIRROR_W"):
            weight_from_env()
    monkeypatch.delenv("EX42_ACTOR_MIRROR_W", raising=False)
    assert weight_from_env() == 0.0
    monkeypatch.setenv("EX42_ACTOR_MIRROR_W", "0.1")
    cfg = train_cfg(2, {"microbatch_envs": 2})
    cfg["ex41_pose_commands"] = True
    cfg["ex41_critic_mirror"] = True
    cfg["ex41_mirror_approval"] = real_authorization(tmp_path / "w72")
    runner = StartRunner(PoseEnv(num_envs=4), cfg, log_dir=None, device="cpu")
    assert runner.alg.actor_mirror_weight == 0.1
    assert not runner.alg.policy.is_recurrent  # history/GRU live in perception, outside frozen PPO actor rows
    assert "EX42_ACTOR_MIRROR where=start w=0.1" in capsys.readouterr().out
    raw = runner.env.get_observations()
    obs = runner._ppo_obs(raw, torch.randn(4, 51))
    assert obs[ACTOR_KEY].shape == (4, 98) and obs[CRITIC_KEY].shape == (4, 666)
    assert torch.equal(obs[ACTOR_KEY][:, 6:9], raw["policy"][:, 6:9])  # vx, vy, wz
    assert torch.equal(mirror_actor_observation(obs[ACTOR_KEY])[:, 6:9],
                       raw["policy"][:, 6:9] * torch.tensor([1, -1, -1]))
    # The raw 32x16 map belongs to critic input. The actor contains learned
    # z16, v3, zf16, zb16; it contains neither map pixels nor GRU state.
    assert torch.equal(mirror_critic(obs[CRITIC_KEY])[:, 52:564],
                       raw["gt_map"].reshape(4, 32, 16).flip(-1).flatten(1))
    flat = torch.zeros(4, 32, 16)
    flat[1, 0, 0] = 0.019
    flat[2, 0, 0] = 0.020
    flat[3, 0, 0] = float("nan")
    assert flat_map_mask(flat).tolist() == [True, True, False, False]


def test_real_runner_rollout_stores_the_flat_mask_and_reports_loss(monkeypatch, tmp_path, capsys):
    class FlatPoseEnv(PoseEnv):
        def _make(self):
            raw = super()._make()
            raw["gt_map"].zero_()
            return raw

    monkeypatch.setenv("EX42_ACTOR_MIRROR_W", "0.1")
    cfg = train_cfg(2, {"microbatch_envs": 2})
    cfg["ex41_pose_commands"] = True
    cfg["ex41_critic_mirror"] = True
    cfg["ex41_mirror_approval"] = real_authorization(tmp_path / "w72_run")
    runner = StartRunner(FlatPoseEnv(num_envs=4), cfg, log_dir=None, device="cpu")
    runner.learn(1)
    out = capsys.readouterr().out
    assert "Mean actor_mirror loss" in out and "mask_fraction=1" in out
    assert "EX42_ACTOR_MIRROR warning" not in out


def test_ex42_parent_load_path_can_enable_critic_mirror_after_runner_init(monkeypatch, tmp_path):
    monkeypatch.setenv("EX42_ACTOR_MIRROR_W", "0.1")
    cfg = train_cfg(2, {"microbatch_envs": 2})
    cfg["ex41_pose_commands"] = True
    cfg["ex41_critic_mirror"] = False
    runner = StartRunner(PoseEnv(num_envs=4), cfg, log_dir=None, device="cpu")
    assert runner.alg.actor_mirror_weight == 0.1 and not runner.alg.mirror_enabled
    runner.set_ex41_critic_mirror(True, real_authorization(tmp_path / "w72_after_parent"))
    assert runner.alg.mirror_enabled
    off, obs = _algorithm()
    off.mirror_enabled = False
    off.actor_mirror_weight = 0.1
    with pytest.raises(ValueError, match="needs the critic-mirror update loop"):
        _update(off, obs)


def test_known_joint_order_mirror_and_involution_catches_hip_sign_mutation(monkeypatch):
    names = list(EXPECTED_JOINT_NAMES)
    a = torch.arange(1, 13, dtype=torch.float32).unsqueeze(0)
    mirrored = mirror_action(a)
    assert torch.equal(mirror_action(mirrored), a)
    for dest, name in enumerate(names):
        leg, joint, suffix = name.split("_")
        other = {"FL": "FR", "FR": "FL", "RL": "RR", "RR": "RL"}[leg]
        src = names.index(f"{other}_{joint}_{suffix}")
        expected = -a[0, src] if joint == "hip" else a[0, src]
        assert mirrored[0, dest] == expected
    # A swapped-hip-only mutant is involutive too, so the known-answer check
    # above is essential; this negative control must fail that check.
    monkeypatch.setattr(mirror_module, "JOINT_SIGNS", (1,) * 12)
    with pytest.raises(AssertionError):
        assert torch.equal(mirror_action(a)[:, :4], mirrored[:, :4])
    monkeypatch.undo()
    obs = torch.arange(98, dtype=torch.float32).unsqueeze(0)
    reflected = mirror_actor_observation(obs)
    assert torch.equal(mirror_actor_observation(reflected), obs)
    assert reflected[0, 9] == -obs[0, 10] and reflected[0, 13] == obs[0, 14]
    assert reflected[0, 62] == -obs[0, 62] and reflected[0, 97] == -obs[0, 97]
    assert torch.equal(reflected[:, 45:61], obs[:, 45:61])
    assert torch.equal(reflected[:, 64:96], obs[:, 64:96])
    monkeypatch.setattr(critic_mirror_module, "JOINT_SIGNS", (1,) * 12)
    with pytest.raises(AssertionError):
        assert mirror_actor_observation(obs)[0, 9] == -obs[0, 10]
    monkeypatch.undo()


def test_real_encoder_flat_height_flip_records_the_latent_limitation(capsys):
    torch.manual_seed(17)
    model = StartPerception(PerceptionCfg()).eval()
    checkpoint = os.environ.get("EX42_ACTOR_MIRROR_TEST_CKPT")
    if checkpoint:
        state = torch.load(checkpoint, map_location="cpu", weights_only=False)
        model.load_state_dict(state["perception_state_dict"], strict=True)
    hprop = torch.zeros(4, 128)
    # Both maps satisfy the actual <2 cm mask. One smooth masked map can
    # appear invariant while irregular masked maps still alter learned zf/zb.
    height = torch.linspace(0, 0.019, 512).reshape(1, 32, 16).repeat(4, 1, 1)
    with torch.inference_mode():
        first = model.ie.estimate(hprop, height)
        other = model.ie.estimate(hprop, height.flip(-1))
    max_gap = max(float((first[key] - other[key]).abs().max()) for key in ("mu", "v", "zf", "zb"))
    assert max_gap < 1e-3, max_gap
    generator = torch.Generator().manual_seed(23)
    irregular_hprop = torch.randn(32, 128, generator=generator) * 0.1
    irregular_map = torch.rand(32, 32, 16, generator=generator) * 0.019
    assert bool(flat_map_mask(irregular_map).all())
    with torch.inference_mode():
        first = model.ie.estimate(irregular_hprop, irregular_map)
        other = model.ie.estimate(irregular_hprop, irregular_map.flip(-1))
    irregular_gap = max(float((first[key] - other[key]).abs().max()) for key in ("mu", "v", "zf", "zb"))
    assert irregular_gap >= 0 and irregular_gap < float("inf")
    print(f"EX42_ACTOR_MIRROR encoder_probe irregular_masked_max_gap={irregular_gap:.6g}")
    if checkpoint:
        assert irregular_gap > 0.01, "the measured m250 encoder gap must be reported rather than described as invariant"
        for key in ("v", "zf", "zb"):
            ratio = float((first[key] - other[key]).abs().max() / first[key].square().mean().sqrt())
            assert ratio < 0.1, (key, ratio)


def _algorithm(seed=1):
    from foothold_s2.tests.test_ex42_bc_prior_cpu import _alg, _obs
    obs = _obs()
    alg = _alg(obs)
    return alg, obs


def _update(alg, obs):
    from foothold_s2.tests.test_ex42_bc_prior_cpu import _update as run_update
    return run_update(alg, obs)


def test_on_loss_actor_only_and_critic_unchanged(capsys):
    off, obs = _algorithm()
    on, _ = _algorithm()
    on.actor_mirror_weight = 0.1
    on.storage.actor_mirror_steps = torch.tensor([[True, True, False, False, True, True, False, False]])
    # Deliberately asymmetric real START actor. Its reflected output differs.
    loss = actor_mirror_loss(on.policy, obs, on.policy.act_inference(obs))
    assert loss.item() > 0
    on.optimizer.zero_grad()
    loss.backward()
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in on.policy.actor.parameters())
    assert all(p.grad is None for p in on.policy.critic.parameters())
    off_result = _update(off, obs)
    on_result = _update(on, obs)
    assert on_result["actor_mirror"] > 0
    assert on_result["actor_mirror_mask_fraction"] == 0.5
    assert on_result["value_function"] == off_result["value_function"]
    assert all(torch.equal(a, b) for a, b in zip(off.policy.critic.parameters(), on.policy.critic.parameters()))
    assert any(not torch.equal(a, b) for a, b in zip(off.policy.actor.parameters(), on.policy.actor.parameters()))
    assert "Mean actor_mirror loss" in capsys.readouterr().out


def test_unset_and_zero_are_byte_identical(monkeypatch):
    monkeypatch.delenv("EX42_ACTOR_MIRROR_W", raising=False)
    off, obs = _algorithm()
    zero, _ = _algorithm()
    assert weight_from_env() == 0.0
    monkeypatch.setenv("EX42_ACTOR_MIRROR_W", "0")
    zero.actor_mirror_weight = weight_from_env()
    rng = torch.get_rng_state().clone()
    off_result = _update(off, obs)
    off_rng = torch.get_rng_state().clone()
    torch.set_rng_state(rng)
    zero_result = _update(zero, obs)
    assert off_result == zero_result
    assert all(torch.equal(a, b) for a, b in zip(off.policy.parameters(), zero.policy.parameters()))
    assert torch.equal(torch.get_rng_state(), off_rng)


def test_two_rank_gate_with_one_empty_rank_keeps_collectives_aligned():
    # Forking after earlier torch tests can hang in pre-existing thread pools.
    # Probe in a fresh interpreter and retain a bounded failure mode.
    done = subprocess.run([sys.executable, "-m", "foothold_s2.tests.ex42_actor_mirror_two_rank_probe"],
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "TWO_RANK_PASS" in done.stdout
