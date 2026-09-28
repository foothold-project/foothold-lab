"""Unitree Go2 environment for fine-tuning a rough-terrain policy on gaps."""

from __future__ import annotations

import copy

from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils import configclass

from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import TerminationsCfg

from ..rough_env_cfg import UnitreeGo2RoughEnvCfg
from . import gap_observations, gap_terminations
from .gap_terrain import ForwardGapTerrainCfg


@configclass
class GapTerminationsCfg(TerminationsCfg):
    """Stock contact/timeout terms plus bottomless-gap fall detection."""

    fell_below_terrain = DoneTerm(
        func=gap_terminations.root_too_far_below_origin,
        params={"minimum_relative_height": -3.0, "asset_cfg": SceneEntityCfg("robot")},
    )


@configclass
class UnitreeGo2GapEnvCfg(UnitreeGo2RoughEnvCfg):
    """Conservative mixed-terrain task compatible with NVIDIA's pretrained policy."""

    terminations: GapTerminationsCfg = GapTerminationsCfg()

    def __post_init__(self):
        super().__post_init__()

        # Replace only the height-scan function; term order, ray count, and tensor shape remain unchanged.
        self.observations.policy.height_scan.func = gap_observations.height_scan_with_gap
        self.observations.policy.height_scan.params = {
            "sensor_cfg": SceneEntityCfg("height_scanner"),
            "offset": 0.5,
            "miss_value": 1.0,
        }
        self.observations.policy.height_scan.clip = (-1.0, 1.0)

        # Copy after Go2-specific terrain scaling so the stock global configuration is never mutated.
        terrain_generator = copy.deepcopy(self.scene.terrain.terrain_generator)
        proportions = {
            "pyramid_stairs": 0.18,
            "pyramid_stairs_inv": 0.18,
            "boxes": 0.18,
            "random_rough": 0.18,
            "hf_pyramid_slope": 0.09,
            "hf_pyramid_slope_inv": 0.09,
        }
        for name, proportion in proportions.items():
            terrain_generator.sub_terrains[name].proportion = proportion

        terrain_generator.sub_terrains["forward_gap"] = ForwardGapTerrainCfg(
            proportion=0.10,
            gap_width_range=(0.05, 0.20),
            gap_center_ratio=0.50,
            approach_distance=1.50,
        )
        terrain_generator.num_rows = 10
        terrain_generator.num_cols = 20
        terrain_generator.difficulty_range = (0.0, 1.0)
        terrain_generator.use_cache = False
        self.scene.terrain.terrain_generator = terrain_generator
        self.scene.terrain.max_init_terrain_level = 2

        # Training samples forward speeds while keeping lateral and yaw commands at zero.
        command = self.commands.base_velocity
        command.heading_command = False
        command.rel_heading_envs = 0.0
        command.rel_standing_envs = 0.0
        command.ranges.lin_vel_x = (0.5, 1.5)
        command.ranges.lin_vel_y = (0.0, 0.0)
        command.ranges.ang_vel_z = (0.0, 0.0)

        # The custom gap is located in +x, so resets use a small heading perturbation only.
        self.events.reset_base.params["pose_range"] = {
            "x": (-0.10, 0.10),
            "y": (-0.20, 0.20),
            "yaw": (-0.05, 0.05),
        }

        # All reward functions and weights remain identical to the NVIDIA rough task.


@configclass
class UnitreeGo2GapEnvCfg_PLAY(UnitreeGo2GapEnvCfg):
    """Noise-free 3x3 gap-only environment evaluated at 1.0 m/s."""

    def __post_init__(self):
        super().__post_init__()

        self.scene.num_envs = 9
        self.scene.env_spacing = 2.5
        self.scene.terrain.max_init_terrain_level = None

        terrain_generator = self.scene.terrain.terrain_generator
        terrain_generator.num_rows = 3
        terrain_generator.num_cols = 3
        terrain_generator.curriculum = False
        terrain_generator.difficulty_range = (0.65, 0.65)
        for terrain_cfg in terrain_generator.sub_terrains.values():
            terrain_cfg.proportion = 0.0
        terrain_generator.sub_terrains["forward_gap"].proportion = 1.0

        self.curriculum.terrain_levels = None
        self.observations.policy.enable_corruption = False
        self.events.base_external_force_torque = None
        self.events.push_robot = None

        command = self.commands.base_velocity
        command.resampling_time_range = (3600.0, 3600.0)
        command.ranges.lin_vel_x = (1.0, 1.0)
        command.ranges.lin_vel_y = (0.0, 0.0)
        command.ranges.ang_vel_z = (0.0, 0.0)
