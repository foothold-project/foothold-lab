"""Fresh interpreter Gloo probe for the EX-42 actor mirror minibatch collective."""

from __future__ import annotations

import os
import tempfile
from datetime import timedelta

import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from tensordict import TensorDict

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY, OBS_GROUPS, StartActorCritic
from foothold_s2.runners.ex41_critic_mirror import CriticMirrorPPO


def worker(rank, store, out):
    dist.init_process_group("gloo", init_method=f"file://{store}", rank=rank, world_size=2,
                            timeout=timedelta(seconds=20))
    torch.manual_seed(7)
    obs = TensorDict({ACTOR_KEY: torch.randn(4, 98), CRITIC_KEY: torch.randn(4, 666)}, batch_size=[4])
    policy = StartActorCritic(obs, OBS_GROUPS, 12, actor_obs_normalization=False,
                              critic_obs_normalization=False, actor_hidden_dims=[16, 8],
                              critic_hidden_dims=[16, 8], pose_command_dim=2)
    alg = CriticMirrorPPO(policy, num_learning_epochs=1, num_mini_batches=2,
                          desired_kl=0.01, schedule="adaptive", device="cpu",
                          multi_gpu_cfg={"global_rank": rank, "local_rank": rank, "world_size": 2})
    alg.mirror_enabled = True
    alg.actor_mirror_weight = 0.1
    alg.init_storage("rl", 4, 1, obs, [12])
    alg.storage.actor_mirror_steps = torch.tensor([[True, False, True, False]])
    torch.manual_seed(100 + rank)
    rollout = TensorDict({ACTOR_KEY: torch.randn(4, 98), CRITIC_KEY: torch.randn(4, 666)}, batch_size=[4])
    alg.act(rollout)
    valid = torch.ones(4, dtype=torch.bool) if rank == 0 else torch.zeros(4, dtype=torch.bool)
    alg.process_env_step(rollout, torch.randn(4), torch.ones(4), {"ex41_ppo_valid": valid})
    alg.compute_returns(rollout)
    losses = alg.update()
    torch.save({"weights": [p.detach().clone() for p in policy.parameters()], "losses": losses},
               os.path.join(out, f"rank{rank}.pt"))
    dist.destroy_process_group()


def main():
    with tempfile.TemporaryDirectory() as out:
        mp.start_processes(worker, args=(os.path.join(out, "store"), out),
                           nprocs=2, join=True, start_method="fork")
        a, b = (torch.load(os.path.join(out, f"rank{rank}.pt"), weights_only=False) for rank in (0, 1))
    assert all(torch.equal(x, y) for x, y in zip(a["weights"], b["weights"]))
    assert a["losses"]["actor_mirror"] > 0
    assert a["losses"]["actor_mirror_mask_fraction"] == b["losses"]["actor_mirror_mask_fraction"]
    print("TWO_RANK_PASS", flush=True)


if __name__ == "__main__":
    main()
