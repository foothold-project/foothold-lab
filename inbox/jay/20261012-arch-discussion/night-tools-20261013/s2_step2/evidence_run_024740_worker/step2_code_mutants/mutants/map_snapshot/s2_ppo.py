"""S2 PPO-only update. No Isaac import and no teacher or reconstruction path."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import sys

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).parent / "base_step1"))
from s2_policy import trainable_params


class S2PPOError(RuntimeError):
    pass


@dataclass(frozen=True)
class PPOConfig:
    rollout_steps: int
    num_envs: int
    epochs: int
    minibatches: int
    clip_param: float
    gamma: float
    lam: float
    value_loss_coef: float
    entropy_coef: float
    max_grad_norm: float
    desired_kl: float | None
    schedule: str
    use_clipped_value_loss: bool

    def __post_init__(self):
        for name in ("rollout_steps", "num_envs", "epochs", "minibatches"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.rollout_steps * self.num_envs < self.minibatches:
            raise ValueError("minibatches exceed rollout samples")
        for name in ("clip_param", "gamma", "lam", "value_loss_coef", "entropy_coef", "max_grad_norm"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.max_grad_norm == 0 or not (0 < self.gamma <= 1) or not (0 <= self.lam <= 1):
            raise ValueError("invalid gradient, gamma or lambda setting")
        if self.desired_kl is not None and (type(self.desired_kl) not in (int, float) or self.desired_kl <= 0):
            raise ValueError("desired_kl must be positive or None")
        if self.schedule not in ("adaptive", "fixed") or type(self.use_clipped_value_loss) is not bool:
            raise ValueError("invalid schedule or value loss rule")

    def as_dict(self):
        return asdict(self)


def adaptive_lr(lr: float, kl_mean: float, desired_kl: float | None, schedule: str) -> float:
    """Parent moe_cts.py 278-311 thresholds and clamps, applied to one base LR."""
    if desired_kl is None or schedule != "adaptive":
        return lr
    if kl_mean > desired_kl * 2.0:
        return max(1e-5, lr / 1.5)
    if 0.0 < kl_mean < desired_kl / 2.0:
        return min(1e-2, lr * 1.5)
    return lr


def _slice(batch: dict, indices: torch.Tensor) -> dict:
    return {key: ({k: v.index_select(0, indices) for k, v in value.items()}
                  if key == "obs" else value.index_select(0, indices))
            for key, value in batch.items()}


class S2PPO:
    def __init__(self, policy: nn.Module, optimizer: torch.optim.Optimizer, ctl, config: PPOConfig):
        if int(os.environ.get("WORLD_SIZE", "1")) != 1:
            raise S2PPOError("multi-process S2 PPO is not validated")
        self.policy = policy
        self.optimizer = optimizer
        self.ctl = ctl
        self.config = config
        if ctl.optimizer is not optimizer:
            raise S2PPOError("control and PPO optimizer differ")
        self.lr = ctl.base_lr

    def update(self, batch: dict, s2_update_index: int) -> dict:
        cfg = self.config
        count = cfg.rollout_steps * cfg.num_envs
        if batch["actions"].shape[0] != count or batch["obs"]["map"].shape != (count, 374):
            raise S2PPOError("rollout shape does not match fixed update plan")
        frozen = self.ctl.begin_update(s2_update_index, self.lr)
        metrics = {"surrogate": 0.0, "value": 0.0, "entropy": 0.0, "kl": 0.0}
        actual_steps = 0
        lr_path = []
        for _epoch in range(cfg.epochs):
            perm = torch.randperm(count, device=batch["actions"].device)
            for indices in torch.tensor_split(perm, cfg.minibatches):
                sample = _slice(batch, indices)
                obs = sample["obs"]
                self.policy.act(obs)
                log_prob = self.policy.get_actions_log_prob(sample["actions"])
                values = self.policy.evaluate(obs).squeeze(-1)
                mu, sigma = self.policy.action_mean, self.policy.action_std
                entropy = self.policy.entropy.mean()
                old_mu, old_sigma = sample["old_mu"], sample["old_sigma"]
                with torch.no_grad():
                    kl = torch.sum(torch.log(sigma / old_sigma + 1.0e-5)
                                   + (old_sigma.square() + (old_mu - mu).square())
                                   / (2.0 * sigma.square()) - 0.5, dim=-1).mean()
                    if not torch.isfinite(kl):
                        raise S2PPOError("nonfinite PPO KL")
                    self.lr = adaptive_lr(self.lr, float(kl), cfg.desired_kl, cfg.schedule)
                    # Parent writes its adaptive base LR to every group. Control restores
                    # the encoder ratio after backward and before each optimizer step.
                    for group in self.optimizer.param_groups:
                        group["lr"] = self.lr
                ratio = torch.exp(log_prob - sample["old_log_prob"])
                surrogate = torch.maximum(-sample["advantages"] * ratio,
                                          -sample["advantages"] * ratio.clamp(1-cfg.clip_param, 1+cfg.clip_param)).mean()
                if cfg.use_clipped_value_loss:
                    clipped = sample["old_values"] + (values - sample["old_values"]).clamp(-cfg.clip_param, cfg.clip_param)
                    value_loss = torch.maximum((values - sample["returns"]).square(),
                                               (clipped - sample["returns"]).square()).mean()
                else:
                    value_loss = (values - sample["returns"]).square().mean()
                loss = surrogate + cfg.value_loss_coef * value_loss - cfg.entropy_coef * entropy
                if not torch.isfinite(loss):
                    raise S2PPOError("nonfinite PPO loss")
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(trainable_params(self.policy), cfg.max_grad_norm,
                                         error_if_nonfinite=True)
                repaired = self.ctl.enforce_groups(self.optimizer, self.lr)
                self.optimizer.step()
                actual_steps += 1
                lr_path.append({"base": self.lr,
                                "groups": {g["name"]: g["lr"] for g in self.optimizer.param_groups},
                                "repaired": repaired})
                for name, value in (("surrogate", surrogate), ("value", value_loss), ("entropy", entropy), ("kl", kl)):
                    metrics[name] += float(value.detach())
        expected = cfg.epochs * cfg.minibatches
        if actual_steps != expected or self.ctl.steps_this_update != expected:
            raise S2PPOError(f"optimizer steps {actual_steps}/{self.ctl.steps_this_update} != {expected}")
        self.ctl.end_update(s2_update_index)
        metrics = {k: v / expected for k, v in metrics.items()}
        return {**metrics, "s2_update_index": s2_update_index, "optimizer_steps": actual_steps,
                "expected_steps": expected, "rollout_steps": cfg.rollout_steps, "num_envs": cfg.num_envs,
                "epochs": cfg.epochs, "minibatches": cfg.minibatches,
                "transitions": count, "frozen": frozen, "base_lr": self.lr, "lr_path": lr_path,
                "loss_terms": ("ppo_surrogate", "ppo_value", "entropy")}
