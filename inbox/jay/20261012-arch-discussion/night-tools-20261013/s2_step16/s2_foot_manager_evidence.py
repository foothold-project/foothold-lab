"""Capture actual RewardManager output and accumulation before automatic reset."""
from __future__ import annotations

import torch

from s2_foot_config import WEIGHT, manager_reward_receipt


def bind_manager_compute(env, *, sample_hook=None):
    manager = env.reward_manager
    if getattr(env, "_s2_foot_manager_hook", False):
        raise ValueError("foot_manager_hook_reused")
    receipt = manager_reward_receipt(manager, variant="feet_center_any9_v1", dt=float(env.step_dt))
    name = "feet_center_any9_v1"
    index = list(manager.active_terms).index(name)
    original = manager.compute
    env._s2_foot_manager_rows = []

    def observed_compute(dt):
        before = manager._episode_sums[name].detach().clone()
        total = original(dt)
        after = manager._episode_sums[name].detach().clone()
        rate = manager._step_reward[:, index].detach().clone()
        query = env._s2_foot_last_query
        cost = env._s2_foot_last_cost.cost.detach().clone()
        expected = cost * WEIGHT * dt
        actual = rate * dt
        if not torch.allclose(actual, expected, atol=1e-6, rtol=0):
            raise ValueError("foot_manager_rate_mismatch")
        if not torch.allclose(after-before, expected, atol=1e-6, rtol=0):
            raise ValueError("foot_manager_accumulator_mismatch")
        extra = sample_hook(query) if sample_hook is not None else {}
        env._s2_foot_manager_rows.append({"global_step": int(env.common_step_counter),
            "episode_id": query.episode_id.detach().cpu().tolist(),
            "expected_weighted": expected.detach().cpu().tolist(),
            "actual_weighted": actual.detach().cpu().tolist(),
            "episode_sum_before": before.detach().cpu().tolist(),
            "episode_sum_after": after.detach().cpu().tolist(),
            "dt_s": float(dt), "manager_terms": receipt, **extra})
        return total

    manager.compute = observed_compute
    env._s2_foot_manager_hook = True
    return receipt
