"""Optional actor equivariance loss on the stored PPO input.

The PPO actor input contains o45, learned perception features 51 and pose2.
Only o45, the estimated velocity3 and pose2 have known reflection coordinates.
The other 48 learned features are held fixed as conditioning variables: they
are not a reflected height map or recurrent state. This is a conditional
regularizer, not a full mirror of the perception pipeline.
"""

from __future__ import annotations

import math
import os

import torch

from foothold_s2.runners.ex41_critic_mirror import JOINT_IDS, JOINT_SIGNS, mirror_policy45


ENV = "EX42_ACTOR_MIRROR_W"


def weight_from_env() -> float:
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return 0.0
    try:
        weight = float(raw)
    except ValueError as exc:
        raise ValueError(f"{ENV} must be a finite nonnegative number") from exc
    if not math.isfinite(weight) or weight < 0:
        raise ValueError(f"{ENV} must be a finite nonnegative number")
    return weight


def flat_map_mask(gt_map: torch.Tensor) -> torch.Tensor:
    """Select rollout rows whose true 32x16 height range is below 2 cm."""
    if gt_map.shape[-2:] != (32, 16):
        raise ValueError("EX-42 actor mirror needs a 32x16 ground-truth height map")
    flat = gt_map.flatten(-2)
    return torch.isfinite(flat).all(dim=-1) & ((flat.max(dim=-1).values - flat.min(dim=-1).values) < 0.02)


def mirror_actor_observation(x: torch.Tensor) -> torch.Tensor:
    """Reflect explicit coordinates, preserving latent perception conditioning.

    The 32x16 map and GRU hidden state are absent from the frozen PPO actor
    input. The critic's map reflection is mirror_critic(...). Raw o45 shares
    exactly the first 45 coordinates with that critic contract.
    """
    if x.shape[-1] != 98:
        raise ValueError("EX-42 actor mirror needs 98 actor entries")
    y = x.clone()
    y[..., :45] = mirror_policy45(x[..., :45])
    # estimate() returns [z16, v3, zf16, zb16] at actor offset 45.
    # z/zf/zb have no geometric index contract; v is a body polar vector.
    y[..., 61:64] = x[..., 61:64] * x.new_tensor((1, -1, 1))
    y[..., 96] = x[..., 96]   # body height command
    y[..., 97] = -x[..., 97]  # body roll command
    return y


def mirror_action(action: torch.Tensor) -> torch.Tensor:
    if action.shape[-1] != 12:
        raise ValueError("EX-42 actor mirror needs 12 Go2 actions")
    return action[..., JOINT_IDS] * action.new_tensor(JOINT_SIGNS)


def actor_mirror_loss(policy, observations, original_mean: torch.Tensor,
                      selected: torch.Tensor | None = None) -> torch.Tensor:
    if selected is not None:
        if selected.shape != (original_mean.shape[0],):
            raise ValueError("EX-42 actor mirror mask does not match the minibatch")
        if not bool(selected.any()):
            return original_mean.sum() * 0.0
        observations = observations[selected]
        original_mean = original_mean[selected]
    mirrored = observations.clone()
    mirrored["actor_in"] = mirror_actor_observation(observations["actor_in"])
    reflected_mean = policy.act_inference(mirrored)
    return (reflected_mean - mirror_action(original_mean)).square().sum(dim=-1).mean()
