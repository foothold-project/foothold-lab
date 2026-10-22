"""EX-19 env cfg (SONNET-X19): EX-16(EX-11 환경 + NVIDIA Go2 보상) + 도메인 무작위화를 v2 와 같게 (DIFF-s1a-vs-nvidia-v2 D01~D05). Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

v2 실행 기록(C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml)의 events 와 같게:
  D01 마찰: static 0.8 · dynamic 0.6 고정(범위 아님), restitution 0, 버킷 64, 로봇 전 몸체, startup   (S1: 0.2~1.2 무작위 · make_consistent)
  D02 base COM 무작위 끔 (v2 events.base_com = None)
  D03 PD 이득 무작위 끔 (v2 에는 actuator_gains 이벤트가 없다)
  D04 모터 세기 무작위 끔 (v2 에는 motor_strength 이벤트가 없다)
  D05 base 질량 추가 [-1, 3] kg (add, base 몸체, startup)   (S1: [-1, 2])
reset_base · reset_robot_joints · 행동 · 종료는 EX-16 그대로(v2 와 다른 부분은 EX-20 에서 따로 본다).
"""

from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass

from foothold_s2.tasks.s2_x16n_cfg import FootholdS2X16nEnvCfg


@configclass
class FootholdS2X19EnvCfg(FootholdS2X16nEnvCfg):
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
