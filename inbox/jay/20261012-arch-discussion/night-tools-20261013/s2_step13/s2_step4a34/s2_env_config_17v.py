"""One S2 environment configuration path for connection and training candidates.

No Isaac import. The caller supplies a registry-created environment cfg.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
from s2_known_scene_a2 import answer, answer_sha256, build_generator

BASE_TASK = "RobotLab-Go2-v0"
DIAG_KINDS = ("eight_case",)
DIAG_TERRAIN_ORDER = ("flat", "obstacles", "gap", "stepping_stones")


@dataclass(frozen=True)
class EnvironmentSpec:
    seed: int
    num_envs: int
    gap_proportion: float
    stones_proportion: float
    step_height_m: float
    step_width_m: float
    geometry_tolerance_m: float

    def __post_init__(self):
        if type(self.seed) is not int or type(self.num_envs) is not int or self.num_envs < 1:
            raise ValueError("seed and positive num_envs required")
        for key in ("gap_proportion", "stones_proportion", "step_height_m", "step_width_m", "geometry_tolerance_m"):
            value = getattr(self, key)
            if type(value) not in (float, int) or not math.isfinite(value):
                raise ValueError(f"finite {key} required")
        if self.step_height_m <= 0 or self.step_width_m <= 0 or self.geometry_tolerance_m <= 0:
            raise ValueError("positive step geometry and tolerance required")

    def sha256(self, diagnostic_kind=None):
        return hashlib.sha256(json.dumps({**asdict(self), "diagnostic_kind": diagnostic_kind},
                                          sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def configure_env(base_cfg, spec: EnvironmentSpec, *, diagnostic_kind: str | None,
                  reset_yaw_rad: float | None):
    """Use the registered RobotLab Go2 task with the same known-answer mesh scene."""
    if diagnostic_kind is not None and diagnostic_kind not in DIAG_KINDS:
        raise ValueError("unknown diagnostic terrain")
    if diagnostic_kind is not None and (reset_yaw_rad is None or not math.isfinite(reset_yaw_rad)):
        raise ValueError("diagnostic reset yaw required")
    import copy
    cfg = copy.deepcopy(base_cfg)
    cfg.seed = spec.seed
    cfg.scene.num_envs = spec.num_envs
    if diagnostic_kind == "eight_case":
        if not hasattr(cfg.sim, "enable_scene_query_support"):
            raise ValueError("scene_query_support_setting_missing")
        cfg.sim.enable_scene_query_support = True
    if cfg.scene.terrain.terrain_generator is None:
        raise ValueError("registered Go2 rough terrain generator missing")
    if diagnostic_kind != "eight_case":
        raise ValueError("diagnostic scene choice required")
    terrain = build_generator(spec.seed)
    if diagnostic_kind == "eight_case":
        if spec.num_envs != 8 or tuple(terrain.sub_terrains) != DIAG_TERRAIN_ORDER:
            raise ValueError("eight-case diagnostic requires eight envs and four terrain kinds")
        # TerrainGenerator curriculum columns and TerrainImporter env mapping
        # are grounded in terrain_generator.py:238-266 / terrain_importer.py:335-353.
        if abs(spec.step_height_m-answer()["step"]["top_z_m"])>1e-9 or abs(
            spec.step_width_m-(answer()["step"]["x_range"][1]-answer()["step"]["x_range"][0]))>1e-9:
            raise ValueError("approved step geometry differs from answer scene")
        cfg.scene.terrain.max_init_terrain_level = 0
        cfg.scene.terrain.terrain_type = "generator"
        if hasattr(cfg.curriculum, "terrain_levels"):
            cfg.curriculum.terrain_levels = None
        pose = cfg.events.reset_base.params["pose_range"]
        cfg.events.reset_base.params["pose_range"] = {**pose, "x": (0.0, 0.0), "y": (0.0, 0.0),
                                                       "yaw": (0.0, 0.0)}
        cfg.events.reset_base.params["velocity_range"] = {key:(0.0,0.0) for key in
                                                             ("x","y","z","roll","pitch","yaw")}
        cfg.observations.policy.enable_corruption = False
        for name in ("randomize_push_robot","randomize_rigid_body_mass_base",
                     "randomize_rigid_body_mass_others","randomize_com_positions",
                     "randomize_rigid_body_material","randomize_actuator_gains",
                     "randomize_motor_zero_offset"):
            if hasattr(cfg.events,name):setattr(cfg.events,name,None)
        cmd=cfg.commands.base_velocity
        cmd.resampling_time_range=(1e9,1e9)
        cmd.resampling_time=1e9
        cmd.dynamic_resample_commands=False
        cmd.command_range_curriculum=[]
        cmd.limit_vel_prob=0.0
        cmd.zero_command_curriculum=None
        cmd.ranges.lin_vel_x=(0.0,0.0)
        cmd.ranges.lin_vel_y=(0.0,0.0)
        cmd.ranges.ang_vel_yaw=(0.0,0.0)
        cfg.episode_length_s=max(20.0,256*cfg.decimation*cfg.sim.dt+5.0)
        # A3.2 (attempt 3, 10/15): with gravity and contact termination the robot sagged from z 0.4 to 0.17
        # in 16 steps, was auto-reset five times (envs 4, 5, 6) and the gap_90 robot fell through the hole to
        # z -66 m, which put the ray starts (robot z + 20 m) below the ground. This diagnostic only checks the
        # sensor-to-map chain, so the robot is held in place: no gravity, no contact termination. This applies to
        # the eight_case diagnostic branch only.
        rigid=getattr(getattr(cfg.scene.robot,"spawn",None),"rigid_props",None)
        if rigid is None or not hasattr(rigid,"disable_gravity"):
            raise ValueError("robot rigid_props.disable_gravity missing")
        rigid.disable_gravity=True
        if not hasattr(cfg.terminations,"illegal_contact"):
            raise ValueError("illegal_contact termination missing")
        cfg.terminations.illegal_contact=None
    cfg.scene.terrain.terrain_generator = terrain
    cfg.scene.terrain.terrain_generator.border_width=0.0
    cfg.scene.terrain.terrain_generator.use_cache=False
    return cfg
