"""EX-42 E1 turns the D174 critic mirror on while training on two GPUs: the mirror update must exchange gradients.

Two gloo processes on CPU stand in for the two ranks. They get different rollouts and must end every update with
identical weights; a rank with no valid row in a slot must not leave the other rank waiting.
"""

from __future__ import annotations

import os
import tempfile

import pytest
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from tensordict import TensorDict

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO


def _worker(rank, store, out, valid_by_rank, schedule, epochs):
    dist.init_process_group("gloo", init_method=f"file://{store}", rank=rank, world_size=2)
    torch.manual_seed(7)   # same weights on both ranks
    n = 4
    obs = TensorDict({ACTOR_KEY: torch.randn(n, 98), CRITIC_KEY: torch.randn(n, 666)}, batch_size=[n])
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
                              actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)
    alg = CriticMirrorPPO(policy, num_learning_epochs=epochs, num_mini_batches=2, desired_kl=0.01, schedule=schedule,
                          device="cpu", multi_gpu_cfg={"global_rank": rank, "local_rank": rank, "world_size": 2})
    alg.mirror_enabled = True
    alg.init_storage("rl", n, 1, obs, [12])
    before = [p.detach().clone() for p in policy.parameters()]
    torch.manual_seed(100 + rank)   # different rollouts per rank
    rollout = TensorDict({ACTOR_KEY: torch.randn(n, 98), CRITIC_KEY: torch.randn(n, 666)}, batch_size=[n])
    alg.act(rollout)
    alg.process_env_step(rollout, torch.randn(n), torch.ones(n), {"ex41_ppo_valid": torch.tensor(valid_by_rank[rank])})
    alg.compute_returns(rollout)
    losses = alg.update()
    torch.save({"before": before, "after": [p.detach().clone() for p in policy.parameters()], "losses": losses,
                "lr": alg.learning_rate}, os.path.join(out, f"r{rank}.pt"))
    dist.destroy_process_group()


def _run(valid_by_rank, schedule="adaptive", epochs=1):
    with tempfile.TemporaryDirectory() as tmp:
        store = os.path.join(tmp, "store")
        mp.spawn(_worker, args=(store, tmp, valid_by_rank, schedule, epochs), nprocs=2, join=True)
        return [torch.load(os.path.join(tmp, f"r{r}.pt")) for r in (0, 1)]


def _same(a, b):
    return all(torch.equal(x, y) for x, y in zip(a, b, strict=True))


@pytest.mark.parametrize("schedule", ["adaptive", "fixed"])
def test_ranks_with_different_rollouts_end_with_identical_weights(schedule):
    r0, r1 = _run([[True] * 4, [True] * 4], schedule)
    assert _same(r0["before"], r1["before"])
    assert not _same(r0["before"], r0["after"])        # the update really moved the weights
    assert _same(r0["after"], r1["after"])             # and moved them the same way on both ranks
    assert r0["lr"] == r1["lr"]


@pytest.mark.parametrize("schedule", ["adaptive", "fixed"])
def test_rank_without_valid_rows_does_not_hang_or_diverge(schedule):
    r0, r1 = _run([[True] * 4, [False] * 4], schedule, epochs=2)
    assert r1["losses"]["ppo_skipped_batches"] == 4 and r0["losses"]["ppo_skipped_batches"] == 0
    assert not _same(r0["before"], r0["after"])
    assert _same(r0["after"], r1["after"])
    assert r0["lr"] == r1["lr"]


def test_rank_with_one_partly_invalid_slot_stays_in_step():
    r0, r1 = _run([[True] * 4, [True, False, False, True]])
    assert _same(r0["after"], r1["after"])


def test_single_gpu_still_rejects_nothing_but_symmetry_rnd_recurrence():
    from foothold_s2.runners import ex41_critic_mirror as module
    source = open(module.__file__, encoding="utf-8").read()
    assert "self.is_multi_gpu:\n            raise" not in source


# ---- one GPU on all rows == two GPUs on half the rows each ----------------------------------------
FIELDS = ("actions", "values", "actions_log_prob", "mu", "sigma", "returns", "advantages")


def _policy_and_alg(n, multi=None, schedule="fixed"):
    obs = TensorDict({ACTOR_KEY: torch.zeros(n, 98), CRITIC_KEY: torch.zeros(n, 666)}, batch_size=[n])
    torch.manual_seed(7)   # weights must not depend on how many rows this process holds
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False, critic_obs_normalization=False,
                              actor_hidden_dims=[16, 8], critic_hidden_dims=[16, 8], pose_command_dim=2)
    obs = TensorDict({ACTOR_KEY: torch.randn(n, 98), CRITIC_KEY: torch.randn(n, 666)}, batch_size=[n])
    alg = CriticMirrorPPO(policy, num_learning_epochs=1, num_mini_batches=1, desired_kl=0.01, schedule=schedule,
                          device="cpu", multi_gpu_cfg=multi)
    alg.mirror_enabled = True
    # plain SGD: the weight change is then linear in the gradient (Adam turns near-zero gradients into full steps)
    alg.optimizer = torch.optim.SGD(policy.parameters(), lr=1e-2)
    alg.max_grad_norm = 1e9   # a clip would hide a gradient that is off by a constant factor
    alg.init_storage("rl", n, 1, obs, [12])
    return alg, obs


def _equivalence_worker(rank, store, out, reference):
    dist.init_process_group("gloo", init_method=f"file://{store}", rank=rank, world_size=2)
    alg, _ = _policy_and_alg(4, {"global_rank": rank, "local_rank": rank, "world_size": 2})
    rows = slice(4 * rank, 4 * rank + 4)
    alg.storage.observations[0] = reference["obs"][rows]
    for name in FIELDS:
        getattr(alg.storage, name)[0] = reference[name][rows]
    alg.storage.step = 1
    alg.update()
    torch.save([p.detach().clone() for p in alg.policy.parameters()], os.path.join(out, f"e{rank}.pt"))
    dist.destroy_process_group()


def test_two_gpus_on_half_the_rows_each_equal_one_gpu_on_all_rows():
    single, obs = _policy_and_alg(8)
    torch.manual_seed(3)
    single.act(obs)
    single.process_env_step(obs, torch.randn(8), torch.ones(8), {"ex41_ppo_valid": torch.ones(8, dtype=torch.bool)})
    # the same advantages and returns for each row whichever process holds it (no per-rank statistics)
    single.storage.returns[0] = torch.randn(8, 1)
    single.storage.advantages[0] = torch.randn(8, 1)
    reference = {"obs": single.storage.observations[0].clone(),
                 **{name: getattr(single.storage, name)[0].clone() for name in FIELDS}}
    before = [p.detach().clone() for p in single.policy.parameters()]
    single.update()
    one_gpu = [p.detach().clone() for p in single.policy.parameters()]
    assert not _same(before, one_gpu)
    with tempfile.TemporaryDirectory() as tmp:
        mp.spawn(_equivalence_worker, args=(os.path.join(tmp, "store"), tmp, reference), nprocs=2, join=True)
        two = [torch.load(os.path.join(tmp, f"e{r}.pt")) for r in (0, 1)]
    assert _same(two[0], two[1])
    for a, b in zip(one_gpu, two[0], strict=True):
        assert torch.allclose(a, b, atol=1e-6, rtol=1e-5), float((a - b).abs().max())
