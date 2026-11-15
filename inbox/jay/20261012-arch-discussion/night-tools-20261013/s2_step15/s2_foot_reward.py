"""S2-2 feet_center_any9_v1 positive cost. No Isaac dependency."""
from __future__ import annotations

from dataclasses import dataclass
import torch

HIT = 1
NO_HIT = 2
CARDINAL = (1, 3, 5, 7)
DIAGONAL = (0, 2, 6, 8)
CENTER = 4
RADIUS_M = 0.022
DROP_M = 0.20
CONTACT_N = 1.0


@dataclass(frozen=True)
class FootCost:
    cost: torch.Tensor
    per_foot: torch.Tensor
    central_discrepancy: torch.Tensor


def feet_center_any9_v1(p_f: torch.Tensor, heights: torch.Tensor,
                        status: torch.Tensor, forces: torch.Tensor) -> FootCost:
    """Return positive [N] cost; manager supplies negative weight and dt.

    HIT heights must be finite. NO_HIT is accepted only after the query layer
    certifies tile, mesh, range, and frame validity. All other states fail closed.
    """
    if p_f.ndim != 3 or p_f.shape[1:] != (4, 3):
        raise ValueError("foot_position_shape")
    n = p_f.shape[0]
    if heights.shape != (n, 4, 9) or status.shape != (n, 4, 9) or forces.shape != (n, 4, 3):
        raise ValueError("foot_query_shape")
    if any(x.device != p_f.device for x in (heights, status, forces)):
        raise ValueError("foot_device_mismatch")
    if not bool(torch.isfinite(p_f).all()) or not bool(torch.isfinite(forces).all()):
        raise ValueError("foot_nonfinite")
    valid = (status == HIT) | (status == NO_HIT)
    if not bool(valid.all()):
        raise ValueError("foot_query_invalid")
    if not bool(torch.isfinite(heights[status == HIT]).all()):
        raise ValueError("foot_hit_nonfinite")
    if not bool(torch.isposinf(heights[status == NO_HIT]).all()):
        raise ValueError("foot_no_hit_encoding")
    threshold = p_f[..., 2].unsqueeze(-1) - RADIUS_M - DROP_M
    danger = (status == NO_HIT) | ((status == HIT) & (heights < threshold))
    cardinal = danger[..., list(CARDINAL)].any(-1)
    diagonal = danger[..., list(DIAGONAL)].any(-1)
    contact = forces[..., 2] > CONTACT_N
    central = danger[..., CENTER] & contact
    per_foot = (cardinal.to(p_f.dtype) + 2 * diagonal.to(p_f.dtype)) * contact
    per_foot = torch.where(central, torch.full_like(per_foot, 3), per_foot)
    cost = per_foot.sum(-1)
    if not bool(torch.isfinite(cost).all()) or not bool(((cost >= 0) & (cost <= 12)).all()):
        raise ValueError("foot_cost_out_of_range")
    return FootCost(cost, per_foot, central.sum(-1))
