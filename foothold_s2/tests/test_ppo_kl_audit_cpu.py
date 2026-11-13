"""Known-input KL, row identity, and unchanged-PPO tests. CPU only."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
import torch
from tensordict import TensorDict

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO
from foothold_s2.runners.ppo_kl_audit import (
    PpoKLAudit, install_runner_kl_audit, join_rank_records, scheduler_kl,
)


@pytest.fixture(autouse=True)
def _restore_rng():
    state = torch.get_rng_state()
    yield
    torch.set_rng_state(state)


def _obs(n=4):
    return TensorDict({ACTOR_KEY: torch.arange(n * 98).float().reshape(n, 98) / 1000,
                       CRITIC_KEY: torch.arange(n * 666).float().reshape(n, 666) / 1000}, [n])


def _alg(mirror=False, n=4, steps=2, multi=None):
    torch.manual_seed(89)
    obs = _obs(n)
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False,
                             critic_obs_normalization=False, actor_hidden_dims=[16, 8],
                             critic_hidden_dims=[16, 8], pose_command_dim=2)
    alg = CriticMirrorPPO(policy, num_learning_epochs=2, num_mini_batches=2,
                         desired_kl=0.01, schedule="adaptive", device="cpu", multi_gpu_cfg=multi)
    alg.mirror_enabled = mirror
    alg.init_storage("rl", n, steps, obs, [12])
    return alg, obs


def _metadata(alg, iteration=250):
    n = alg.storage.num_envs
    step = alg.storage.step
    ids = torch.arange(n)
    return {"iteration": iteration, "command": torch.stack((ids + step * 10, ids * 0, ids * 0), -1).float(),
            "command_slot": ids, "terrain_column": ids, "terrain_level": ids + step,
            "heading": ids == 1, "flag": ids == 2, "map_mode": ids % 3,
            "episode_length": ids + step}


def _rows(audit):
    return [json.loads(line) for line in audit.path.read_text().splitlines()]


def _same_state(a, b):
    if isinstance(a, torch.Tensor):
        assert torch.equal(a, b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a: _same_state(a[k], b[k])
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b)
        for x, y in zip(a, b, strict=True): _same_state(x, y)
    else:
        assert a == b


def test_scheduler_kl_known_shift_and_std_not_approximate_probe():
    mu0, sigma0 = torch.zeros(2, 3, dtype=torch.float64), torch.ones(2, 3, dtype=torch.float64)
    mu1, sigma1 = mu0.clone(), sigma0.clone()
    mu1[1, 0] = 2
    expected = torch.tensor([3 * torch.log(torch.tensor(1.00001, dtype=torch.float64)),
                            2 + 3 * torch.log(torch.tensor(1.00001, dtype=torch.float64))])
    torch.testing.assert_close(scheduler_kl(mu0, sigma0, mu1, sigma1), expected, rtol=1e-12, atol=1e-12)
    # KL(old || new), with exactly the epsilon used by the installed scheduler.
    sigma1.fill_(2)
    expected = (torch.log(sigma1 / sigma0 + 1e-5)
                + (sigma0.square() + (mu0 - mu1).square()) / (2 * sigma1.square()) - .5).sum(-1)
    assert torch.equal(scheduler_kl(mu0, sigma0, mu1, sigma1), expected)


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("quarantine", [False, True])
def test_audit_preserves_weights_optimizer_rng_lr_losses_and_aligns_actual_rows(tmp_path, mirror, quarantine):
    results = []
    for enabled in (False, True):
        alg, obs = _alg(mirror)
        audit = PpoKLAudit(alg, lambda: _metadata(alg), tmp_path, identity={"run": "known"},
                           top_k=8) if enabled else None
        torch.manual_seed(731)
        snapshots = []
        for step in range(2):
            snapshots.append(_metadata(alg))
            with torch.inference_mode():
                alg.act(obs)
                valid = torch.tensor([True, not quarantine, True, True])
                alg.process_env_step(obs, torch.tensor([1., -.2, .4, .8]), torch.tensor([0., 1., 0., 0.]),
                                     {"ex41_ppo_valid": valid})
        alg.compute_returns(obs)
        torch.manual_seed(477)
        losses = alg.update()
        results.append((copy.deepcopy(alg.policy.state_dict()), copy.deepcopy(alg.optimizer.state_dict()),
                        torch.get_rng_state(), alg.learning_rate, losses))
        if audit:
            rows = _rows(audit)
            batches = [r for r in rows if r["event"] == "minibatch"]
            assert len(batches) == 4
            assert rows[-1]["event"] == "update_complete" and rows[-1]["status"] == "complete"
            for b in batches:
                assert b["iteration"] == 250 and b["rank"] == 0 and b["epoch"] in (0, 1)
                assert b["lr_after"] > 0 and b["metadata_status"] == "complete"
                assert b["scheduler_kl_local_mean"] >= 0
                for sample in b["top_kl_samples"]:
                    env, step = sample["env_id"], sample["rollout_step"]
                    assert sample["command"][0] == env + step * 10
                    assert sample["terrain_level"] == env + step
                    assert sample["map_mode"] == ("GT", "PRED", "OFF")[env % 3]
                    assert sample["after_reset"] == (step == 0 or env == 1)
                    if quarantine: assert env != 1
            audit.close()
    _same_state(results[0], results[1])


def test_hook_reads_std_before_optimizer_changes_it(tmp_path):
    alg, obs = _alg(steps=1)
    audit = PpoKLAudit(alg, lambda: _metadata(alg), tmp_path, identity={"run": "known"})
    alg.act(obs)
    alg.process_env_step(obs, torch.ones(4), torch.zeros(4), {"ex41_ppo_valid": torch.ones(4, dtype=torch.bool)})
    batch_idx = torch.arange(4)
    old_mu, old_sigma = alg.storage.mu[0], alg.storage.sigma[0]
    audit.observe("begin_update")
    audit.observe("begin_minibatch", 0, 0, batch_idx, old_mu, old_sigma)
    alg.policy.act(obs)
    expected = scheduler_kl(old_mu, old_sigma, alg.policy.action_mean, alg.policy.action_std).mean().item()
    alg.policy.std.grad = torch.ones_like(alg.policy.std)
    alg.optimizer.step()
    row = [r for r in _rows(audit) if r["event"] == "minibatch"][0]
    assert row["scheduler_kl_local_mean"] == expected
    after = scheduler_kl(old_mu, old_sigma, alg.policy.action_mean, alg.policy.action_std).mean().item()
    assert after != expected
    audit.close()


def test_missing_metadata_is_incomplete_not_silent_success(tmp_path):
    alg, obs = _alg()
    audit = PpoKLAudit(alg, lambda: {}, tmp_path, identity={"run": "known"})
    for _ in range(2):
        alg.act(obs)
        alg.process_env_step(obs, torch.ones(4), torch.zeros(4), {"ex41_ppo_valid": torch.ones(4, dtype=torch.bool)})
    alg.compute_returns(obs)
    alg.update()  # observational failure must not change or terminate the optimizer
    rows = _rows(audit)
    assert any(r["event"] == "audit_error" for r in rows)
    assert rows[-1]["status"] == "incomplete"
    assert all(r["metadata_status"] == "incomplete" for r in rows if r["event"] == "minibatch")
    audit.close()


def test_rank_join_requires_all_ranks_and_uses_mean_of_rank_means():
    base = {"event": "minibatch", "iteration": 1, "epoch": 0, "minibatch": 0, "world_size": 2,
            "identity": {"run": "r"}, "status": "optimizer_step", "metadata_status": "complete",
            "lr_before": .001, "lr_after": .001 / 1.5, "schedule": "adaptive", "desired_kl": .01}
    rows = [{**base, "rank": 0, "valid_count": 4, "scheduler_kl_local_mean": .01},
            {**base, "rank": 1, "valid_count": 2, "scheduler_kl_local_mean": .05}]
    result = join_rank_records(rows)[0]
    assert result["status"] == "complete" and result["scheduler_kl_rank_mean"] == pytest.approx(.03)
    assert result["scheduler_decision"] == "decrease" and result["lr_consistent"]
    assert join_rank_records(rows[:1])[0]["status"] == "incomplete"
    assert join_rank_records(rows + rows[:1])[0]["status"] == "incomplete"
    bad = copy.deepcopy(rows); bad[1]["lr_after"] = .002
    assert not join_rank_records(bad)[0]["lr_consistent"]


def test_installer_reads_actual_pre_action_map_flags_and_env(tmp_path):
    alg, obs = _alg(steps=1)
    term = SimpleNamespace(command=torch.zeros(4, 3), slot_current=torch.arange(4),
                           heading=torch.tensor([False, True, False, False]), is_flag_env=torch.zeros(4, dtype=torch.bool))
    terrain = SimpleNamespace(terrain_types=torch.tensor([0, 1, 0, 1]), terrain_levels=torch.arange(4))
    env = SimpleNamespace(command_manager=SimpleNamespace(get_term=lambda _: term),
                          scene=SimpleNamespace(terrain=terrain), episode_length_buf=torch.arange(4),
                          _ex42_column_table=[{"family": "A", "kind": "flat"}, {"family": "A", "kind": "stairs"}])
    runtime = SimpleNamespace(iteration=751, stage_id="E1", plan=SimpleNamespace(sha256="a" * 64))
    runner = SimpleNamespace(alg=alg, env=SimpleNamespace(unwrapped=env), log_dir=str(tmp_path),
                             pstate=SimpleNamespace(use_gt=torch.tensor([True, False, True, False]),
                                                   map_off=torch.tensor([False, False, True, True])))
    audit = install_runner_kl_audit(runner, runtime=runtime)
    assert install_runner_kl_audit(runner, runtime=runtime) is audit  # no duplicate observer
    alg.act(obs)
    runner.pstate.map_off.fill_(False)  # post-step map changes must not overwrite the captured rows
    alg.process_env_step(obs, torch.ones(4), torch.zeros(4), {"ex41_ppo_valid": torch.ones(4, dtype=torch.bool)})
    alg.compute_returns(obs)
    alg.update()
    samples = [s for r in _rows(audit) if r["event"] == "minibatch" for s in r["top_kl_samples"]]
    by_env = {s["env_id"]: s for s in samples}
    assert [by_env[i]["map_mode"] for i in range(4)] == ["GT", "PRED", "OFF", "OFF"]
    assert by_env[1]["terrain_kind"] == "stairs" and by_env[1]["heading"] is True
    audit.close()
