"""EX-42 actor left-right mirror loss (lead 2026-11-22 04:34, ledger 7dd4ffc75: an E3 first-window prescription candidate for the
forward yaw drift). Off by default.

    L = L_PPO + w * mean_s || mu_theta(o_s) - M_a mu_theta(M_o o_s) ||^2        (w = EX42_ACTOR_MIRROR_WEIGHT, default 0 = off)

Outside START (the source paper has no symmetry term). It sits next to the heading-hold 2.0 alternative because the two answer
different questions: heading hold rewards the outcome (no yaw drift while walking straight) and leaves the cause in the actor,
while the drift measured on 11/22 sits in the policy itself (app MuJoCo mirror test: the yaw sign flips exactly with a mirrored
model; same checkpoint E1F m250 drifts left in Isaac too, +9.3 deg mean at 6 s, vx 1.0). The mirror loss asks the actor for the
mirrored action on the mirrored state, which is the property whose absence makes a straight command drift.

M_o (lead 04:35, path B): the actor input is o45 + perception estimate 51 (z 16, v 3, zf 16, zb 16) + pose command 2. z, zf, zb are
learned latents with no left-right table, so the mirrored input is NOT built by permuting the stored actor input. The perception
replay of the rollout (hist 10 x 45, depth 2 x 60 x 60, ground-truth map 32 x 16, foot maps, base velocity) is mirrored with the
physical tables of the critic mirror (o45 rows, map y flip, foot order swap and y flip, velocity y sign) and the depth image is
flipped left-right; the frozen-for-this-step perception module re-estimates the 51 entries from it (est_sequence, no gradient,
z = mean). M_o o = [mirror(o45), est(mirrored replay) through the same actor-input path (_est_in: vx correction), mirror(pose)].

Caveats written down for the reader (lead 04:35):
  * the depth camera is on the body centre line (depth_cam_cfg.OFFSET_POS y = 0, pitch only) and its image width is the last
    axis, so a left-right flip of the image is the mirrored camera; position jitter is symmetric in distribution only;
  * the mirrored sequence starts from the rollout's own GRU states (h_prop0, h_terr0: the context before this rollout was not
    mirrored), so the first steps after a rollout start are an approximation until the GRUs forget that context;
  * z is the posterior mean on the mirrored side while the stored input may carry a sampled z (sample_latent_in_rollout).

M_a: action rows are the joint order of EXPECTED_JOINT_NAMES; mirror = JOINT_IDS permutation with JOINT_SIGNS (hip abduction
flips), the same table the critic mirror applies to joint positions, velocities and last actions.

No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

from foothold_s2.runners.ex41_critic_mirror import JOINT_IDS, JOINT_SIGNS, LEG_SWAP

WEIGHT_ENV = "EX42_ACTOR_MIRROR_WEIGHT"
KEY = "actor_in_mirror"          # the mirrored actor input rides in the rollout storage observations next to actor_in
LOG = "EX42_ACTOR_MIRROR"
OBS_DIM = 45
EST_DIM = 51
V_SLICE = slice(OBS_DIM + 16, OBS_DIM + 19)   # est = z 16, v 3, zf 16, zb 16 (start_perception.EST_DIM order)


def weight() -> float:
    """0.0 = off (unset, empty or 0). A bad value is refused, not ignored."""
    raw = os.environ.get(WEIGHT_ENV, "")
    if raw == "":
        return 0.0
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{WEIGHT_ENV} must be a number (got {raw!r})") from None
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{WEIGHT_ENV} must be finite and >= 0 (got {raw!r})")
    return value


def mirror_o45(x: torch.Tensor) -> torch.Tensor:
    """o45 = ang vel 3, projected gravity 3, command (vx vy wz) 3, joint pos 12, joint vel 12, last action 12 (critic mirror rows 0:45)."""
    if x.shape[-1] != OBS_DIM:
        raise ValueError(f"o45 mirror needs {OBS_DIM} entries, got {x.shape[-1]}")
    y = x.clone()
    y[..., 0:3] = x[..., 0:3] * x.new_tensor((-1, 1, -1))
    y[..., 3:6] = x[..., 3:6] * x.new_tensor((1, -1, 1))
    y[..., 6:9] = x[..., 6:9] * x.new_tensor((1, -1, -1))
    signs = x.new_tensor(JOINT_SIGNS)
    for lo in (9, 21, 33):
        y[..., lo:lo + 12] = x[..., lo:lo + 12][..., list(JOINT_IDS)] * signs
    return y


def mirror_action(a: torch.Tensor) -> torch.Tensor:
    return a[..., list(JOINT_IDS)] * a.new_tensor(JOINT_SIGNS)


def mirror_pose(p: torch.Tensor) -> torch.Tensor:
    """D93 pose command [body height delta, body roll]: roll flips."""
    return p * p.new_tensor((1, -1))


def mirror_replay(batch: dict) -> dict:
    """The perception replay of a rollout, mirrored left-right. Keys not listed (done, tick, first, use_gt, map_off, h_prop0, h_terr0)
    are symmetric and are kept (the GRU start states are the caveat above)."""
    out = dict(batch)
    out["obs"] = mirror_o45(batch["obs"])
    out["next_obs"] = mirror_o45(batch["next_obs"])
    out["hist"] = mirror_o45(batch["hist"])
    out["depth2"] = batch["depth2"].flip(-1)
    out["gt_map"] = batch["gt_map"].flip(-1)
    feet = batch["gt_feet"]
    out["gt_feet"] = feet.reshape(*feet.shape[:-1], 4, 5, 5)[..., list(LEG_SWAP), :, :].flip(-1).reshape(feet.shape)
    out["base_vel"] = batch["base_vel"] * batch["base_vel"].new_tensor((1, -1, 1))
    return out


def mirrored_actor_inputs(perception, replay, est_in, pose: torch.Tensor | None, chunk: int) -> torch.Tensor:
    """(T, N, actor dim) mirrored actor inputs for the whole rollout. est_in(est, vel) is the runner's _est_in (the one actor-input
    path). pose is the (T, N, 2) pose command or None. chunk = envs per perception pass (memory)."""
    T, N = replay.T, replay.N
    parts = []
    for lo in range(0, N, chunk):
        idx = torch.arange(lo, min(lo + chunk, N), device=replay.device)
        m = mirror_replay(replay.gather(idx))
        eps = torch.zeros(T, idx.numel(), 16, device=replay.device)
        est = perception.est_sequence(m, eps)
        parts.append(torch.cat([m["obs"], est_in(est, m["base_vel"])], -1))
    actor = torch.cat(parts, 1)
    if pose is not None:
        actor = torch.cat([actor, mirror_pose(pose)], -1)
    return actor


def mirror_loss(mu: torch.Tensor, mu_of_mirror: torch.Tensor) -> torch.Tensor:
    """mean over samples of the squared distance between the action and the mirrored action of the mirrored state (both branches
    carry gradient: the term is symmetric in the two)."""
    return (mu - mirror_action(mu_of_mirror)).square().sum(-1).mean()
