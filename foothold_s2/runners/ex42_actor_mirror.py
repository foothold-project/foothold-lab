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
import torch.distributed as dist

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


def capture_encoder_probe_rows(perception, state, gt_map: torch.Tensor,
                               selected: torch.Tensor, limit: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None:
    """Keep the exact map source the rollout encoder consumed for up to limit selected rows."""
    ids = selected.nonzero().flatten()[:limit]
    if ids.numel() == 0:
        return None
    if perception.trnet is not None:
        _, refined = perception.trnet.decode(state.h_terr[ids])
        used_map = torch.where(state.use_gt[ids, None, None], gt_map[ids], refined)
    elif perception.cfg.fast_gt_only:
        used_map = gt_map[ids]
    else:
        raise ValueError("EX-42 actor mirror encoder probe needs a map-consuming perception model")
    return state.h_prop[ids].clone(), used_map.clone(), state.map_off[ids].clone()


def encoder_flip_statistics(ie, hprop: torch.Tensor, used_map: torch.Tensor,
                            map_off: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Per component: max |flip-original|, original squared sum, value count."""
    original = ie.estimate(hprop, used_map, map_off)
    reflected = ie.estimate(hprop, used_map.flip(-1), map_off)
    maxima, energy, counts = [], [], []
    for key in ("v", "zf", "zb"):
        a, b = original[key], reflected[key]
        difference = (a - b).abs()
        maxima.append(difference.max())
        energy.append(a.square().sum())
        counts.append(a.new_tensor(a.numel()))
    return torch.stack(maxima), torch.stack(energy), torch.stack(counts)


def encoder_probe_line(update: int, samples: int, ratios: tuple[float, float, float]) -> str:
    alert = samples == 0 or any(not math.isfinite(value) or value > 0.1 for value in ratios)
    shown = " ".join(f"{key}={value:.6g}" for key, value in zip(("v", "zf", "zb"), ratios, strict=True))
    return f"EX42_ACTOR_MIRROR_ENCODER it={update} samples={samples} {shown}" + (" ALERT" if alert else "")


def report_encoder_probe(update: int, rows: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
                         perception, *, multi_gpu: bool, rank: int, device) -> str:
    """Reduce the real masked rollout sample across ranks; no policy, reward or RNG mutation."""
    maxima = torch.zeros(3, device=device)
    energy = torch.zeros(3, device=device)
    counts = torch.zeros(3, device=device)
    samples = torch.zeros((), device=device)
    if rows:
        hprop = torch.cat([row[0] for row in rows])
        used_map = torch.cat([row[1] for row in rows])
        map_off = torch.cat([row[2] for row in rows])
        with torch.inference_mode():
            maxima, energy, counts = encoder_flip_statistics(perception.ie, hprop, used_map, map_off)
        samples.fill_(hprop.shape[0])
    if multi_gpu:
        dist.all_reduce(maxima, op=dist.ReduceOp.MAX)
        dist.all_reduce(energy, op=dist.ReduceOp.SUM)
        dist.all_reduce(counts, op=dist.ReduceOp.SUM)
        dist.all_reduce(samples, op=dist.ReduceOp.SUM)
    ratios = tuple(float(maxima[i] / (energy[i] / counts[i]).sqrt()) if counts[i] > 0 and energy[i] > 0
                   else (0.0 if counts[i] > 0 and maxima[i] == 0 else float("inf")) for i in range(3))
    line = encoder_probe_line(update, int(samples), ratios)
    if rank == 0:
        print(line, flush=True)
    return line
