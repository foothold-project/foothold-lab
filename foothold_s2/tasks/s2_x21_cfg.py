"""EX-21 env cfg (SONNET-X21): EX-16(EX-11 환경 + NVIDIA Go2 보상) + EX-19 의 도메인 무작위화 다섯 + EX-20 의 행동 · 종료. Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

EX-20 cfg(지연 없는 JointPositionAction scale 0.25 · 종료 time_out + base_contact 1 N)를 상속하고, EX-19 의 이벤트 다섯 대입을 그대로 더한다:
  마찰 static 0.8 · dynamic 0.6 고정 · base 질량 add [-1, 3] kg · base_com 끔 · actuator_gains 끔 · motor_strength 끔 (v2 env.yaml events 와 같음).
est_mode oracle_vel(잡음 0.1)은 agent cfg(s2_x21_ppo_cfg.py)가 정한다.
"""

from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass

from foothold_s2.tasks.s2_x20_cfg import FootholdS2X20EnvCfg


@configclass
class FootholdS2X21EnvCfg(FootholdS2X20EnvCfg):
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
