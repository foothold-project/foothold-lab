"""Termination conditions for bottomless-gap training."""

from __future__ import annotations

from typing import TYPE_CHECKING

from isaaclab.managers import SceneEntityCfg

if TYPE_CHECKING:
    from isaaclab.envs import ManagerBasedRLEnv


def root_too_far_below_origin(
    env: ManagerBasedRLEnv,
    minimum_relative_height: float = -3.0,
    asset_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Terminate a robot that has fallen far below its terrain-tile origin."""

    robot = env.scene[asset_cfg.name]
    relative_height = robot.data.root_pos_w[:, 2] - env.scene.env_origins[:, 2]
    return relative_height < minimum_relative_height
