"""EX-23 env cfg (SONNET-X23): START 구조 G1(본선) = EX-11 환경(S1 7 종 지형 · START 명령 · START 보상표 foot_edge 0 · START 종료) + v2 처럼 약한 DR + 행동 지연 끔.
Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

EX-11 환경(FootholdS2X11EnvCfg)을 상속하고 두 묶음만 바꾼다:
  - DR 다섯 (EX-19 와 같은 식): 마찰 0.8/0.6 고정 · 질량 add [-1, 3] · base_com 끔 · actuator_gains 끔 · motor_strength 끔 (v2 env.yaml events 와 같음)
  - 행동 (EX-20 과 같은 식): 지연 없는 JointPositionAction (scale 0.25 · use_default_offset)
종료는 START 그대로(time_out · bad_orientation · foot_below_ground), 보상은 START 표 그대로(관절 한계 벌점 없음), 명령 START.
지도 입력(map_input reconstruction · est_mode learned · critic clean52)은 agent cfg(s2_x23_ppo_cfg.py)가 정한다.
"""

from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity import mdp

from foothold_s2.tasks.s2_env_cfg import FootholdS2X11EnvCfg


@configclass
class FootholdS2X23EnvCfg(FootholdS2X11EnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.events.physics_material.params = {
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"), "static_friction_range": (0.8, 0.8), "dynamic_friction_range": (0.6, 0.6),
            "restitution_range": (0.0, 0.0), "num_buckets": 64}
        self.events.add_base_mass.params = {
            "asset_cfg": SceneEntityCfg("robot", body_names="base"), "mass_distribution_params": (-1.0, 3.0), "operation": "add"}
        self.events.base_com = None
        self.events.actuator_gains = None
        self.events.motor_strength = None
        self.actions.joint_pos = mdp.JointPositionActionCfg(asset_name="robot", joint_names=[".*"], scale=0.25, use_default_offset=True)
