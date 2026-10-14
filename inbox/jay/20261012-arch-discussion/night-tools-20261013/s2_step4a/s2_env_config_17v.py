"""One S2 environment configuration path for connection and training candidates.

No Isaac import. The caller supplies a registry-created environment cfg.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "s2_step2"))
from s2_terrain_overlay_17v import make_overlay

BASE_TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"
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
    """Copy parent cfg and apply the exact same S2 overlay in both entry points."""
    if diagnostic_kind is not None and diagnostic_kind not in DIAG_KINDS:
        raise ValueError("unknown diagnostic terrain")
    if diagnostic_kind is not None and (reset_yaw_rad is None or not math.isfinite(reset_yaw_rad)):
        raise ValueError("diagnostic reset yaw required")
    import copy
    cfg = copy.deepcopy(base_cfg)
    cfg.seed = spec.seed
    cfg.scene.num_envs = spec.num_envs
    if cfg.scene.terrain.terrain_generator is None:
        raise ValueError("parent terrain generator missing")
    terrain = make_overlay(cfg.scene.terrain.terrain_generator,
                           gap_proportion=spec.gap_proportion, stones_proportion=spec.stones_proportion)
    if diagnostic_kind == "eight_case":
        if spec.num_envs != 8 or any(name not in terrain.sub_terrains for name in DIAG_TERRAIN_ORDER):
            raise ValueError("eight-case diagnostic requires eight envs and four terrain kinds")
        # TerrainGenerator curriculum mode assigns one deterministic kind per column.
        # TerrainImporter maps env 0/1, 2/3, 4/5, 6/7 to those columns.
        chosen = {name: terrain.sub_terrains[name] for name in DIAG_TERRAIN_ORDER}
        terrain.sub_terrains = chosen
        for sub in terrain.sub_terrains.values():
            sub.proportion = .25
        step = terrain.sub_terrains["obstacles"]
        step.num_obstacles = 1
        step.obstacle_height_range = (spec.step_height_m, spec.step_height_m)
        step.obstacle_width_range = (spec.step_width_m, spec.step_width_m)
        terrain.curriculum = True
        terrain.num_rows = 1
        terrain.num_cols = 4
        cfg.scene.terrain.max_init_terrain_level = 0
        if hasattr(cfg.curriculum, "terrain_levels"):
            cfg.curriculum.terrain_levels = None
        pose = cfg.events.reset_base.params["pose_range"]
        cfg.events.reset_base.params["pose_range"] = {**pose, "x": (0.0, 0.0), "y": (0.0, 0.0),
                                                       "yaw": (0.0, 0.0)}
    cfg.scene.terrain.terrain_generator = terrain
    return cfg
