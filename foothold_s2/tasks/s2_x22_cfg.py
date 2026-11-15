"""EX-22 env cfg (SONNET-X21): EX-21 + 명령 분포를 v2 와 같게. Kit 안에서만 불린다. 기존 파일은 고치지 않는다.

v2 실행 기록(C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml)의 commands.base_velocity 를 그대로:
UniformVelocityCommand, resampling (10, 10) s, heading_command True · heading_control_stiffness 0.5, rel_standing_envs 0.1, rel_heading_envs 1.0,
ranges: lin_vel_x (0.4, 1.5) · lin_vel_y (0, 0) · ang_vel_z (-1, 1) · heading (-pi, pi).  달라진 것 하나: debug_vis 는 v2 가 True 지만 학습은 headless 라 False(화살표 마커 USD 를 내려받지 않게, 값에는 영향 없음).

충돌 두 개를 끈다 (S1 의 명령 term(MixedVelocityCommand)에 묶여 있어서 UniformVelocityCommand 에서는 AttributeError 가 난다):
  - curriculum.terrain_levels: S1 의 terrain_levels_mixed(is_flag_env · cmd_sum_xy · max_dist 등을 읽음) -> v2 의 mdp.terrain_levels_vel (v2 env.yaml curriculum.terrain_levels)
  - curriculum.command_range: S1 의 command_range_curriculum(is_flag_env · range_curriculum 을 읽음) -> 없음
penalty_on 커리큘럼은 명령 term 을 안 읽어 그대로 둔다. START 명령 계약 검사(contract)는 agent cfg 에서 끈다.
"""

import math

from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity import mdp

from foothold_s2.tasks.s2_x21_cfg import FootholdS2X21EnvCfg


@configclass
class FootholdS2X22EnvCfg(FootholdS2X21EnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.commands.base_velocity = mdp.UniformVelocityCommandCfg(
            asset_name="robot", resampling_time_range=(10.0, 10.0), rel_standing_envs=0.1, rel_heading_envs=1.0, heading_command=True,
            heading_control_stiffness=0.5, debug_vis=False,
            ranges=mdp.UniformVelocityCommandCfg.Ranges(lin_vel_x=(0.4, 1.5), lin_vel_y=(0.0, 0.0), ang_vel_z=(-1.0, 1.0), heading=(-math.pi, math.pi)))
        self.curriculum.terrain_levels = CurrTerm(func=mdp.terrain_levels_vel)
        self.curriculum.command_range = None
