"""NVIDIA Go2 rough 보상 세트 통째 (EX-16, SONNET-X16b). Kit 안에서만 불린다.

출처(설치본 Isaac Lab, 줄 번호는 이 기기의 C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/):
  velocity_env_cfg.py:231~263 RewardsCfg (기본값)  +  config/go2/rough_env_cfg.py:52~58 (Go2 에서 바꾸는 값: feet_air_time 센서 `.*_foot` · 가중치 0.01, undesired_contacts = None,
  dof_torques_l2 -2e-4, track_lin_vel_xy_exp 1.5, track_ang_vel_z_exp 0.75, dof_acc_l2 -2.5e-7).
실행 기록 대조: C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_rough/2026-08-05_17-42-05/params/env.yaml:821~ 와 unitree_go2_gap_nvidia/2026-09-10_20-47-27_..._nvidia_gap_repro_seed42_iter1500/params/env.yaml 의 rewards (시험이 읽어 맞춘다).

항 이름은 START 의 이름을 쓴다(설치본 이름 -> 여기 이름): track_lin_vel_xy_exp -> track_lin_vel · track_ang_vel_z_exp -> track_ang_vel · lin_vel_z_l2 -> lin_vel_z · ang_vel_xy_l2 -> ang_vel_xy ·
dof_torques_l2 -> joint_torques · dof_acc_l2 -> joint_acc · action_rate_l2 -> action_rate · feet_air_time -> feet_air_time · flat_orientation_l2 -> flat_orientation · dof_pos_limits -> dof_pos_limits.
이유: S1 의 command_range 커리큘럼이 보상 항 이름 `track_lin_vel` · `track_ang_vel` 로 값을 읽는다(START 명령 가지는 그 상한을 안 읽지만 term 은 돈다). 함수 · 가중치 · 인자는 설치본 그대로다.
START 고유 항(action_smoothness · joint_power · joint_deviation · collision · stumble · foot_edge)은 없다. 설치본의 undesired_contacts 는 Go2 cfg 가 None 으로 끈다(실행 기록 env.yaml 도 null).
"""

import math

from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity import mdp


@configclass
class NvidiaGo2RewardsCfg:
    # -- task
    track_lin_vel = RewTerm(func=mdp.track_lin_vel_xy_exp, weight=1.5, params={"command_name": "base_velocity", "std": math.sqrt(0.25)})
    track_ang_vel = RewTerm(func=mdp.track_ang_vel_z_exp, weight=0.75, params={"command_name": "base_velocity", "std": math.sqrt(0.25)})
    # -- penalties
    lin_vel_z = RewTerm(func=mdp.lin_vel_z_l2, weight=-2.0)
    ang_vel_xy = RewTerm(func=mdp.ang_vel_xy_l2, weight=-0.05)
    joint_torques = RewTerm(func=mdp.joint_torques_l2, weight=-0.0002)
    joint_acc = RewTerm(func=mdp.joint_acc_l2, weight=-2.5e-7)
    action_rate = RewTerm(func=mdp.action_rate_l2, weight=-0.01)
    feet_air_time = RewTerm(
        func=mdp.feet_air_time, weight=0.01,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"), "command_name": "base_velocity", "threshold": 0.5})
    # -- optional penalties (설치본은 가중치 0)
    flat_orientation = RewTerm(func=mdp.flat_orientation_l2, weight=0.0)
    dof_pos_limits = RewTerm(func=mdp.joint_pos_limits, weight=0.0)
