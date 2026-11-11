"""EX-41 PPO storage that excludes quarantined env steps from every batch.

The index order mirrors the installed isaac311 rsl_rl RolloutStorage.  In an
all-valid rollout it yields exactly the installed generator's batches.
"""

from __future__ import annotations

import torch

from rsl_rl.storage.rollout_storage import RolloutStorage


def safe_minibatch_advantage(advantage: torch.Tensor) -> torch.Tensor:
    """Keep singleton valid batches finite; match PPO for larger batches."""
    if advantage.numel() < 2:
        return advantage
    return (advantage - advantage.mean()) / (advantage.std() + 1e-8)


class ValidRolloutStorage(RolloutStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.valid = torch.ones(self.num_transitions_per_env, self.num_envs, dtype=torch.bool, device=self.device)
        self.yielded_batches = 0
        self.skipped_batches = 0
        self.normalize_per_batch_safely = False
        # Two-GPU mirror update: every rank must make the same number of gradient exchanges, so an
        # empty slot is handed to the caller as None instead of being dropped.
        self.yield_skipped = False

    def clear(self) -> None:
        super().clear()
        self.valid.fill_(True)

    def mini_batch_generator(self, num_mini_batches: int, num_epochs: int = 8):
        if self.training_type != "rl":
            raise ValueError("EX-41 valid batches require RL storage")
        batch_size = self.num_envs * self.num_transitions_per_env
        mini_batch_size = batch_size // num_mini_batches
        if mini_batch_size < 1:
            raise ValueError("more mini batches than rollout rows")
        indices = torch.randperm(num_mini_batches * mini_batch_size, requires_grad=False, device=self.device)
        observations = self.observations.flatten(0, 1)
        actions = self.actions.flatten(0, 1)
        values = self.values.flatten(0, 1)
        returns = self.returns.flatten(0, 1)
        old_log_prob = self.actions_log_prob.flatten(0, 1)
        advantages = self.advantages.flatten(0, 1)
        old_mu = self.mu.flatten(0, 1)
        old_sigma = self.sigma.flatten(0, 1)
        valid = self.valid.flatten()
        self.yielded_batches = 0
        self.skipped_batches = 0
        for _ in range(num_epochs):
            for index in range(num_mini_batches):
                start = index * mini_batch_size
                batch_idx = indices[start:start + mini_batch_size]
                batch_idx = batch_idx[valid[batch_idx]]
                if batch_idx.numel() == 0:
                    self.skipped_batches += 1
                    if self.yield_skipped:
                        yield None
                    continue
                self.yielded_batches += 1
                batch_advantage = advantages[batch_idx]
                if self.normalize_per_batch_safely:
                    batch_advantage = safe_minibatch_advantage(batch_advantage)
                yield (observations[batch_idx], actions[batch_idx], values[batch_idx], batch_advantage,
                       returns[batch_idx], old_log_prob[batch_idx], old_mu[batch_idx], old_sigma[batch_idx],
                       (None, None), None)
