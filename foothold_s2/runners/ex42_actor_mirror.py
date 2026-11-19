"""EX42_ACTOR_MIRROR: a left-right symmetry loss on the actor mean action (candidate H3-b, planner DESIGN-ACTOR-MIRROR-1120 v0.1).

The critic already has a mirror (ex41_critic_mirror.mirror_critic); the actor has none. Half of the actor input is the latent output of the
perception module, which cannot be mirrored by a formula. So the rollout runs the perception a second time on a mirrored world (mirrored o45
history, depth flipped left-right, ground map flipped) with its own hidden state, and stores that second actor input next to the first one.
The update then punishes the distance between the actor mean on the mirrored input and the mirror of the actor mean on the original input
(and the same the other way round, each side taking half). Perception is outside the optimizer of the actor (PPO sees detached inputs), so only the
actor MLP moves.

Optional EX42_ACTOR_MIRROR_ZMEAN=1 (needs the weight on): the original side of the loss uses the latent at its mean too (key actor_in_o, one more actor input stored),
so the loss compares like with like; the sampled input still feeds the PPO surrogate.

Off by default: weight 0 (env var EX42_ACTOR_MIRROR_W unset or 0) builds no second stream, stores no second input and changes no number.

Mirror definitions (all shared with, or checked against, the critic mirror):
  o45        mirror_o45_into (ex41_critic_mirror): angular velocity (-1, 1, -1), gravity (1, -1, 1), command (1, -1, -1), the three joint
             blocks with the left-right leg swap and the hip sign
  action 12  the same JOINT_IDS and JOINT_SIGNS (an involution)
  depth      60 x 60 flipped along the last axis. Exact: the camera sits on the body mid line (y = 0, only a pitch), the principal point is the image
             centre and Isaac Lab adds 0.5 to every pixel (patterns.py), so column i pairs with column 59 - i. Which tensor axis is the width is
             NOT proven on CPU (the image is square): the Kit symmetry scene check (design section 5) is the gate.
  map 32x16  last axis flipped (as in mirror_critic)
  pose_cmd 2 (height delta m, body roll rad): (+1, -1). The runner keeps both at 0 in this stage, so the mirror stays 0.
"""

from __future__ import annotations

import math
import os

import torch

from foothold_s2.runners.ex41_critic_mirror import JOINT_IDS, JOINT_SIGNS, mirror_o45_into

ENV_WEIGHT = "EX42_ACTOR_MIRROR_W"
ENV_ZMEAN = "EX42_ACTOR_MIRROR_ZMEAN"
ORIG_KEY = "actor_in_o"         # the original-world actor input with the perception latent z at its mean, stored only while ZMEAN is on
MIRROR_KEY = "actor_in_m"       # the second actor input, stored next to ACTOR_KEY only while the loss is on
MAP_SHAPE = (32, 16)


def actor_mirror_weight(environ=None) -> float:
    """Weight of the symmetry loss. 0 (unset, empty or 0) = off, which is exactly today's training. Negative or non-finite raises."""
    environ = os.environ if environ is None else environ
    raw = str(environ.get(ENV_WEIGHT, "")).strip()
    if raw == "":
        return 0.0
    w = float(raw)
    if not math.isfinite(w) or w < 0.0:
        raise ValueError(f"{ENV_WEIGHT} must be finite and >= 0, got {raw!r}")
    return w


def actor_mirror_zmean(environ=None) -> bool:
    """EX42_ACTOR_MIRROR_ZMEAN=1: the original side of the symmetry loss also sees the latent z at its mean (as the mirror side always does), so both
    sides of the loss are in the same condition. The PPO surrogate input stays the sampled one. Unset, empty or 0 = off (today's loss). Anything else raises."""
    environ = os.environ if environ is None else environ
    raw = str(environ.get(ENV_ZMEAN, "")).strip()
    if raw in ("", "0"):
        return False
    if raw == "1":
        return True
    raise ValueError(f"{ENV_ZMEAN} must be unset, 0 or 1, got {raw!r}")


def mirror_proprio(o: torch.Tensor) -> torch.Tensor:
    """Mirror of o45 (last dim 45)."""
    if o.shape[-1] != 45:
        raise ValueError("actor mirror needs 45 proprio entries")
    y = o.clone()
    mirror_o45_into(y, o)
    return y


def mirror_action(a: torch.Tensor) -> torch.Tensor:
    """Mirror of a 12-wide action or action mean (an involution)."""
    if a.shape[-1] != 12:
        raise ValueError("actor mirror needs 12 action entries")
    return a[..., list(JOINT_IDS)] * a.new_tensor(JOINT_SIGNS)


def mirror_depth(d: torch.Tensor) -> torch.Tensor:
    """(..., 60, 60) normalized depth, flipped along the width axis (the last one)."""
    if d.shape[-2:] != (60, 60):
        raise ValueError("actor mirror needs a 60 x 60 depth image")
    return d.flip(-1)


def mirror_map(g: torch.Tensor) -> torch.Tensor:
    """(..., 32, 16) ground map, flipped along the last axis (as mirror_critic does for the 512 entries)."""
    if g.shape[-2:] != MAP_SHAPE:
        raise ValueError("actor mirror needs a 32 x 16 ground map")
    return g.flip(-1)


def mirror_pose(p: torch.Tensor) -> torch.Tensor:
    """pose_cmd (height delta, roll): the roll changes sign under a left-right reflection."""
    if p.shape[-1] != 2:
        raise ValueError("actor mirror needs 2 pose command entries")
    return p * p.new_tensor((1.0, -1.0))


def symmetry_loss(mu: torch.Tensor, mu_m: torch.Tensor) -> torch.Tensor:
    """Mean over samples of the squared distance summed over the 12 action dims; both directions, each taking half:
    0.5 * |mu_m - M(mu).detach()|^2 + 0.5 * |mu - M(mu_m).detach()|^2.  Zero for a left-right symmetric policy."""
    to_m = (mu_m - mirror_action(mu).detach()).square().sum(-1)
    to_o = (mu - mirror_action(mu_m).detach()).square().sum(-1)
    return 0.5 * (to_m.mean() + to_o.mean())


def sync_flags(mirror_state, state) -> None:
    """The mirror stream runs with the very same AdaSmpl and map-off flags as the original (copied in place for all envs)."""
    mirror_state.use_gt.copy_(state.use_gt)
    if state.map_off is not None:
        mirror_state.map_off.copy_(state.map_off)


def sync_mirror_state(mirror_state, state, reset_mask: torch.Tensor) -> None:
    """After the env reset: the mirror stream starts the finished episodes the same way the original does (both hidden states 0, the history and the
    frames refilled by the next ingest) and takes the map flags the original just drew."""
    m = reset_mask.bool()
    mirror_state.h_prop[m] = 0
    mirror_state.h_terr[m] = 0
    mirror_state.steps_since_reset[m] = 0
    sync_flags(mirror_state, state)
