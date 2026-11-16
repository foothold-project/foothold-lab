"""Real two-rank PPO on gloo: observer parity and scheduler evidence, no GPU."""

import copy
import json
from pathlib import Path

import pytest
import torch
import torch.distributed as dist
import torch.multiprocessing as mp

from foothold_s2.runners.ppo_kl_audit import install_runner_kl_audit, join_rank_records
from foothold_s2.tests.test_ppo_kl_audit_cpu import _alg, _obs, _same_state, _shared_installer_inputs


def _worker(rank, store, directory, mirror, empty_second_rank):
    torch.set_num_threads(1)
    dist.init_process_group("gloo", init_method=f"file://{store}", rank=rank, world_size=2)
    original_reduce, original_broadcast = dist.all_reduce, dist.broadcast
    results = []
    try:
        for enabled in (False, True):
            means, collectives = [], []

            def reduce(tensor, *args, **kwargs):
                collectives.append(("reduce", tuple(tensor.shape)))
                value = original_reduce(tensor, *args, **kwargs)
                if tensor.ndim == 0:
                    means.append(float(tensor) / 2)
                return value

            def broadcast(tensor, *args, **kwargs):
                collectives.append(("broadcast", tuple(tensor.shape)))
                return original_broadcast(tensor, *args, **kwargs)

            dist.all_reduce, dist.broadcast = reduce, broadcast
            alg, _ = _alg(mirror, multi={"global_rank": rank, "local_rank": rank, "world_size": 2})
            runner, runtime = _shared_installer_inputs(alg, directory, rank)
            audit = install_runner_kl_audit(runner, runtime=runtime) if enabled else None
            torch.manual_seed(31 + rank)
            obs = _obs()
            obs["actor_in"] += rank * .3
            obs["critic_in"] += rank * .1
            for _ in range(2):
                with torch.inference_mode():
                    alg.act(obs)
                    valid = torch.ones(4, dtype=torch.bool)
                    if empty_second_rank and rank == 1:
                        valid.zero_()
                    alg.process_env_step(obs, torch.randn(4), torch.ones(4), {"ex41_ppo_valid": valid})
            alg.compute_returns(obs)
            torch.manual_seed(17 + rank)
            loss = alg.update()
            results.append({"policy": copy.deepcopy(alg.policy.state_dict()),
                            "optimizer": copy.deepcopy(alg.optimizer.state_dict()),
                            "rng": torch.get_rng_state(), "lr": alg.learning_rate, "loss": loss,
                            "scheduler_means": means, "collectives": collectives})
            if audit: audit.close()
        _same_state(results[0], results[1])
        torch.save(results[1], Path(directory) / f"rank{rank}.pt")
    finally:
        dist.all_reduce, dist.broadcast = original_reduce, original_broadcast
        dist.destroy_process_group()


@pytest.mark.parametrize("mirror,empty_second_rank", [(False, False), (True, False), (True, True)])
def test_two_rank_observer_matches_actual_collective_kl_and_leaves_training_identical(tmp_path, mirror, empty_second_rank):
    mp.spawn(_worker, args=(str(tmp_path / "gloo-store"), str(tmp_path), mirror, empty_second_rank),
             nprocs=2, join=True)
    results = [torch.load(tmp_path / f"rank{rank}.pt", weights_only=False) for rank in range(2)]
    _same_state(results[0]["policy"], results[1]["policy"])
    rows = [json.loads(line) for rank in range(2)
            for line in (tmp_path / "run" / "ppo_kl_audit" / f"ppo_kl_rank{rank}.jsonl").read_text().splitlines()]
    assert len({json.dumps(r["identity"], sort_keys=True) for r in rows}) == 1
    assert rows[0]["identity"]["plan_sha256"] == "a" * 64
    assert not list(tmp_path.glob("rank*-private"))
    joined = join_rank_records(rows)
    assert len(joined) == 4
    for row, actual_global in zip(joined, results[0]["scheduler_means"], strict=True):
        assert row["status"] == "complete" and row["lr_consistent"]
        assert row["scheduler_kl_rank_mean"] == pytest.approx(actual_global, rel=1e-7, abs=1e-12)
    assert all(r["status"] == "complete" for r in rows if r["event"] == "update_complete")
    if empty_second_rank:
        batches = [r for r in rows if r["event"] == "minibatch" and r["rank"] == 1]
        assert all(r["valid_count"] == 0 and r["scheduler_kl_local_mean"] == 0 for r in batches)
