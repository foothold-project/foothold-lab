"""Observation functions for terrain scans containing bottomless gaps."""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import RayCaster

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def height_scan_with_gap(
    env: ManagerBasedRLEnv,
    sensor_cfg: SceneEntityCfg,
    offset: float = 0.5,
    miss_value: float = 1.0,
) -> torch.Tensor:
    """Preserve the stock height-scan layout and map ray misses to a deep drop."""

    sensor: RayCaster = env.scene.sensors[sensor_cfg.name]
    ray_hit_z = sensor.data.ray_hits_w[..., 2]

    # This is the same relative-height equation used by IsaacLab's stock observation.
    height = sensor.data.pos_w[:, 2].unsqueeze(1) - ray_hit_z - offset
    valid_hit = torch.isfinite(ray_hit_z) & torch.isfinite(height)

    # A positive saturated value represents terrain far below the robot, not a tall wall.
    return torch.where(valid_hit, height, torch.full_like(height, miss_value))
