"""SOL-23f START-TopDown: sparse 8x4, 원문 명령, 발 가장자리, PIE DR/지연."""

import copy
import torch

from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass

from foothold_s2.curriculum import terrain_levels_mixed as tlm
from foothold_s2.rewards import core
from foothold_s2.tasks.s2_env_cfg import FootholdS2DiagG0StartEnvCfg
from foothold_s2.tasks.s2_23f_camera import randomize_topdown_camera
from foothold_s2.tasks.s2_23f_motor import TopDownDCMotor, randomize_topdown_motor_strength
from foothold_s2.tasks.s2_23f_spawn import correct_topdown_spawn
from foothold_s2.tasks.s2_23f_termination import foot_below_support_plane
from foothold_s2.terrains import sol23f_topdown


def topdown_foot_edge(env, sensor_cfg, asset_cfg):
    """8x4 m 칸의 발 중심 접촉점을 2.5/5 cm 모서리 띠와 대조한다."""
    if not hasattr(env, "s2_tables"):
        raise RuntimeError("TopDown foot edge needs bound terrain side table")
    feet = env.scene[asset_cfg.name].data.body_pos_w[:, asset_cfg.body_ids, :2]
    forces = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids]
    contact = torch.linalg.vector_norm(forces, dim=-1) > 1.0
    terrain = env.scene.terrain
    return core.foot_edge_penalty_tiles(
        feet + torch.as_tensor(sol23f_topdown.WORLD_CENTER_SHIFT, device=feet.device, dtype=feet.dtype),
        contact, env.s2_tables.inner, env.s2_tables.outer,
        terrain.terrain_levels, terrain.terrain_types, size=sol23f_topdown.SIZE,
        resolution=sol23f_topdown.RESOLUTION,
    )


@configclass
class FootholdS223FTopDownEnvCfg(FootholdS2DiagG0StartEnvCfg):
    """S1 PIE 이벤트와 지연 action을 보존한다. G0의 50열을 8x4 sparse 전용으로 교체한다."""

    track_lin_form: str = "A"  # START 원문 min 식, EX23/B의 정확 추종식과 분리

    def use_full_terrain(self):
        self.scene.terrain.terrain_generator = sol23f_topdown.generator_cfg()

    def __post_init__(self):
        super().__post_init__()
        self.rewards.foot_edge.weight = core.WEIGHTS["foot_edge"]
        self.rewards.foot_edge.func = topdown_foot_edge
        self.rewards.foot_edge.params = {
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"),
            "asset_cfg": SceneEntityCfg("robot", body_names=".*_foot"),
        }
        self.curriculum.terrain_levels = CurrTerm(
            func=tlm.terrain_levels_s2, params={"t_start": 1000, "t_end": 8000, "p_max": 0.9})
        # START 명령은 고정 U(0,1.5) 전진 또는 제자리 회전. 우리 범위 커리큘럼을 제거한다.
        self.curriculum.command_range = None
        self.commands.base_velocity.dynamic_flags = False
        self.commands.base_velocity.flag_stride = 0
        self.commands.base_velocity.params = {"start_mode": True}
        # PIE 표 II: 카메라 위치 각 축 ±10 mm, pitch ±1°, 원영상 HFOV 86..88°.
        self.events.topdown_camera = EventTerm(func=randomize_topdown_camera, mode="reset")
        # PIE 표 II의 초기 관절 위치 배율. EX23 및 S1의 1.0 고정은 이 판에 상속하지 않는다.
        self.events.reset_robot_joints.params["position_range"] = (0.5, 1.5)
        # Team choice, not specified by START: face forward at the narrow departure.
        # B keeps the inherited randomized yaw range.
        self.events.reset_base = copy.deepcopy(self.events.reset_base)
        self.events.reset_base.params = {
            **self.events.reset_base.params,
            "pose_range": {**self.events.reset_base.params["pose_range"], "yaw": (0.0, 0.0)},
        }
        # reset_base and reset_robot_joints run first. Correct their root XY
        # after the actual randomized joints are in ArticulationData.
        self.events.supported_spawn = EventTerm(func=correct_topdown_spawn, mode="reset")
        # PIE motor-strength is applied to PD output before the unchanged DC clip.
        for actuator_cfg in self.scene.robot.actuators.values():
            actuator_cfg.class_type = TopDownDCMotor
        self.events.motor_strength.func = randomize_topdown_motor_strength
        self.terminations.foot_below_ground.func = foot_below_support_plane
        self.terminations.foot_below_ground.params.pop("scanner_cfg")
