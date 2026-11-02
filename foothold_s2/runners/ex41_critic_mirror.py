"""D101 value-only Go2 mirror for the 666-wide EX-41 critic.

The first 52 entries are o45, body linear velocity3, contacts4.  Both
legacy and clean52 assemble those groups in this order.  Ground map is
32x16; foot maps are FL, FR, RL, RR, each 5x5 (start_obs.py).
"""

from __future__ import annotations

import torch
from torch import nn

from rsl_rl.algorithms import PPO

from foothold_s2.models.start_policy import CRITIC_KEY
from foothold_s2.runners.ex41_valid_storage import ValidRolloutStorage, safe_minibatch_advantage


LEG_SWAP = (1, 0, 3, 2)
JOINT_IDS = tuple(4 * joint + LEG_SWAP[leg] for joint in range(3) for leg in range(4))
JOINT_SIGNS = (-1,) * 4 + (1,) * 8
EXPECTED_JOINT_NAMES = tuple(
    f"{leg}_{joint}_joint"
    for joint in ("hip", "thigh", "calf")
    for leg in ("FL", "FR", "RL", "RR")
)


def assert_joint_order(joint_names) -> None:
    """Reject an env whose policy joint order differs from EX-40 evidence."""
    if tuple(joint_names) != EXPECTED_JOINT_NAMES:
        raise ValueError("EX-41 critic mirror joint_names differ from EX-40 coordinate metadata")


def mirror_critic(x: torch.Tensor) -> torch.Tensor:
    if x.shape[-1] != 666:
        raise ValueError("EX-41 mirror needs 666 critic entries")
    y = x.clone()
    # Angular velocity is an axial vector under left-right reflection.
    y[..., 0:3] = x[..., 0:3] * x.new_tensor((-1, 1, -1))
    y[..., 3:6] = x[..., 3:6] * x.new_tensor((1, -1, 1))
    y[..., 6:9] = x[..., 6:9] * x.new_tensor((1, -1, -1))
    joint_signs = x.new_tensor(JOINT_SIGNS)
    for lo in (9, 21, 33):
        y[..., lo:lo + 12] = x[..., lo:lo + 12][..., JOINT_IDS] * joint_signs
    y[..., 45:48] = x[..., 45:48] * x.new_tensor((1, -1, 1))
    y[..., 48:52] = x[..., 48:52][..., list(LEG_SWAP)]
    y[..., 52:564] = x[..., 52:564].reshape(*x.shape[:-1], 32, 16).flip(-1).flatten(-2)
    y[..., 564:664] = x[..., 564:664].reshape(*x.shape[:-1], 4, 5, 5)[..., list(LEG_SWAP), :, :].flip(-1).flatten(-3)
    y[..., 664] = x[..., 664]   # body height delta
    y[..., 665] = -x[..., 665]  # body roll
    return y


def value_loss(value: torch.Tensor, old_value: torch.Tensor, returns: torch.Tensor,
               clip_param: float, clipped: bool) -> torch.Tensor:
    if clipped:
        limited = old_value + (value - old_value).clamp(-clip_param, clip_param)
        return torch.maximum((value - returns).square(), (limited - returns).square()).mean()
    return (value - returns).square().mean()


class CriticMirrorPPO(PPO):
    """Ordinary PPO while off; when enabled only the value loss gets mirrors.

    Mirrored old values were never stored.  Therefore the mirror branch uses
    an unclipped squared return loss.  The original branch retains PPO's
    configured clipping.  The two value losses are averaged to keep scale.
    The actor uses the original all-parameter PPO gradient clip before mirror
    critic gradients are substituted and clipped separately.  Actor data are
    neither mirrored nor repeated.  Multi-GPU, symmetry, RND and recurrence
    are rejected for this specialized update.
    """

    mirror_enabled = False

    def init_storage(self, training_type, num_envs, num_transitions_per_env, obs, actions_shape):
        self.storage = ValidRolloutStorage(training_type, num_envs, num_transitions_per_env,
                                           obs, actions_shape, self.device)

    def process_env_step(self, obs, rewards, dones, extras):
        valid = extras.get("ex41_ppo_valid")
        if valid is None:
            raise ValueError("EX-41 PPO validity mask missing from quarantine step")
        valid = torch.as_tensor(valid, device=self.storage.valid.device, dtype=torch.bool).flatten()
        if valid.shape != (self.storage.num_envs,):
            raise ValueError("EX-41 PPO validity mask shape differs from env count")
        step = self.storage.step
        self.storage.valid[step].copy_(valid)
        super().process_env_step(obs, rewards, dones, extras)
        if not bool(valid.all()):
            # A quarantined transition is a terminal boundary.  This also
            # prevents its next-state value from entering the previous GAE.
            bad = ~valid
            self.storage.rewards[step, bad] = 0
            self.storage.values[step, bad] = 0
            self.storage.dones[step, bad] = 1
            self.storage.actions_log_prob[step, bad] = 0
            self.storage.mu[step, bad] = 0
            self.storage.sigma[step, bad] = 1

    def compute_returns(self, obs):
        last_valid = self.storage.valid[-1]
        if bool(last_valid.all()):
            last_values = self.policy.evaluate(obs).detach()
        else:
            # Never evaluate a quarantined final observation.  An extreme but
            # finite critic input can overflow to Inf, and PPO's 0 * Inf in
            # the terminal bootstrap would then poison earlier valid GAE.
            last_values = torch.zeros_like(self.storage.values[-1])
            if bool(last_valid.any()):
                last_values[last_valid] = self.policy.evaluate(obs[last_valid]).detach()
        self.storage.compute_returns(last_values, self.gamma, self.lam, normalize_advantage=False)
        valid = self.storage.valid.unsqueeze(-1)
        if not self.normalize_advantage_per_mini_batch:
            # Preserve the installed normalization path when all rows are valid.
            if bool(valid.all()):
                advantage = self.storage.advantages
                self.storage.advantages = (advantage - advantage.mean()) / (advantage.std() + 1e-8)
            elif bool(valid.any()):
                advantage = self.storage.advantages[valid]
                mean = advantage.mean()
                std = advantage.std() if advantage.numel() > 1 else advantage.new_zeros(())
                self.storage.advantages = torch.where(valid, (self.storage.advantages - mean) / (std + 1e-8), 0)
            else:
                self.storage.advantages.zero_()

    def update(self) -> dict[str, float]:
        parameters = tuple(self.policy.parameters())
        if not bool(torch.stack([torch.isfinite(param).all() for param in parameters]).all()):
            skipped = float(self.num_learning_epochs * self.num_mini_batches)
            self.storage.clear()
            result = {"value_function": 0.0, "surrogate": 0.0, "entropy": 0.0,
                      "ppo_skipped_batches": skipped, "ppo_nonfinite_parameters": 1.0}
            if self.mirror_enabled:
                result.update(value_mirror=0.0, value_combined=0.0)
            return result
        if not self.mirror_enabled:
            safe_norm = self.normalize_advantage_per_mini_batch
            if safe_norm:
                # Installed PPO normalizes after sampling.  Move the same
                # operation into the valid-row generator so a singleton can
                # bypass its undefined unbiased standard deviation.
                self.storage.normalize_per_batch_safely = True
                self.normalize_advantage_per_mini_batch = False
            try:
                result = super().update()
            finally:
                self.storage.normalize_per_batch_safely = False
                self.normalize_advantage_per_mini_batch = safe_norm
            actual = self.storage.yielded_batches
            expected = self.num_learning_epochs * self.num_mini_batches
            if actual:
                result = {key: value * expected / actual for key, value in result.items()}
            result["ppo_skipped_batches"] = float(self.storage.skipped_batches)
            return result
        if self.symmetry or self.rnd or self.policy.is_recurrent or self.is_multi_gpu:
            raise ValueError("EX-41 critic mirror supports single-GPU feed-forward PPO without symmetry or RND")
        total_v = total_m = total_combined = total_s = total_e = 0.0
        batches = self.storage.mini_batch_generator(self.num_mini_batches, self.num_learning_epochs)
        for (obs, actions, old_value, advantage, returns, old_logp, old_mu, old_sigma,
             hidden, masks) in batches:
            if self.normalize_advantage_per_mini_batch:
                with torch.no_grad():
                    advantage = safe_minibatch_advantage(advantage)
            self.policy.act(obs, masks=masks, hidden_state=hidden[0])
            logp = self.policy.get_actions_log_prob(actions)
            value = self.policy.evaluate(obs, masks=masks, hidden_state=hidden[1])
            mu, sigma, entropy = self.policy.action_mean, self.policy.action_std, self.policy.entropy
            if self.desired_kl is not None and self.schedule == "adaptive":
                with torch.inference_mode():
                    kl = torch.sum(torch.log(sigma / old_sigma + 1.0e-5)
                                   + (old_sigma.square() + (old_mu - mu).square()) / (2.0 * sigma.square())
                                   - 0.5, dim=-1).mean()
                    if self.is_multi_gpu:
                        torch.distributed.all_reduce(kl, op=torch.distributed.ReduceOp.SUM)
                        kl /= self.gpu_world_size
                    if self.gpu_global_rank == 0:
                        if kl > self.desired_kl * 2.0:
                            self.learning_rate = max(1e-5, self.learning_rate / 1.5)
                        elif 0 < kl < self.desired_kl / 2.0:
                            self.learning_rate = min(1e-2, self.learning_rate * 1.5)
                    if self.is_multi_gpu:
                        lr_tensor = torch.tensor(self.learning_rate, device=self.device)
                        torch.distributed.broadcast(lr_tensor, src=0)
                        self.learning_rate = lr_tensor.item()
                    for group in self.optimizer.param_groups:
                        group["lr"] = self.learning_rate
            ratio = torch.exp(logp - old_logp.squeeze())
            surrogate = torch.maximum(-advantage.squeeze() * ratio,
                                      -advantage.squeeze() * ratio.clamp(1.0 - self.clip_param, 1.0 + self.clip_param)).mean()
            original_value = value_loss(value, old_value, returns, self.clip_param, self.use_clipped_value_loss)
            mirrored = obs.clone()
            mirrored[CRITIC_KEY] = mirror_critic(obs[CRITIC_KEY])
            mirror_value = self.policy.evaluate(mirrored, masks=masks, hidden_state=hidden[1])
            mirror_loss = (mirror_value - returns).square().mean()
            combined_value = 0.5 * (original_value + mirror_loss)
            base_loss = surrogate + self.value_loss_coef * original_value - self.entropy_coef * entropy.mean()
            self.optimizer.zero_grad()
            base_loss.backward(retain_graph=True)
            # Preserve the exact unaugmented PPO clip for actor and std.
            nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
            critic_params = tuple(self.policy.critic.parameters())
            critic_grads = torch.autograd.grad(self.value_loss_coef * combined_value, critic_params)
            for param, grad in zip(critic_params, critic_grads, strict=True):
                param.grad = grad
            nn.utils.clip_grad_norm_(critic_params, self.max_grad_norm)
            self.optimizer.step()
            total_v += float(original_value.detach())
            total_m += float(mirror_loss.detach())
            total_combined += float(combined_value.detach())
            total_s += float(surrogate.detach())
            total_e += float(entropy.mean().detach())
        count = self.storage.yielded_batches
        skipped = self.storage.skipped_batches
        self.storage.clear()
        count = max(count, 1)
        return {"value_function": total_v / count, "value_mirror": total_m / count,
                "value_combined": total_combined / count,
                "surrogate": total_s / count, "entropy": total_e / count,
                "ppo_skipped_batches": float(skipped)}
