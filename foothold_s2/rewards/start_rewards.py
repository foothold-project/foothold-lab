"""START Table I 14 항을 Isaac Lab 보상 설정으로 (16 §7). Kit 안에서만 불린다. 식은 `core.py` 와 같다.

기존 Isaac Lab 항을 재사용하고(`track_lin_vel_xy_exp` 가 B 식과 같다), 없는 항 넷(부드러움 · 관절 일률 · 관절 오차 L2 ·
걸려 넘어짐)과 자리표시 하나(발 가장자리, S1 은 가중치 0)를 새로 쓴다.
"""

import torch

from isaaclab.managers import ManagerTermBase, RewardTermCfg as RewTerm, SceneEntityCfg
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity import mdp

from foothold_s2.rewards import core

# 충돌 판정 링크 (16 §1 가정: base · 허벅지 · 머리, 17 문서와 맞춤)
COLLISION_BODIES = ["base", ".*_thigh", "Head_.*"]
FOOT_BODIES = ".*_foot"


class action_smoothness_l2(ManagerTermBase):
    """sum (a_t - 2 a_{t-1} + a_{t-2})^2. 행동 이력 둘을 이 항이 직접 들고 있다 (reset 때 0 으로)."""

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        dim = env.action_manager.total_action_dim
        self._a1 = torch.zeros(env.num_envs, dim, device=env.device)
        self._a2 = torch.zeros_like(self._a1)

    def reset(self, env_ids=None):
        if env_ids is None:
            env_ids = slice(None)

        self._a1[env_ids] = 0.0
        self._a2[env_ids] = 0.0

    def __call__(self, env):
        a = env.action_manager.action
        out = core.action_smoothness_l2(a, self._a1, self._a2)
        self._a2 = self._a1.clone()
        self._a1 = a.clone()

        return out


def joint_power_abs(env, asset_cfg=SceneEntityCfg("robot")):
    asset = env.scene[asset_cfg.name]

    return core.joint_power(asset.data.applied_torque[:, asset_cfg.joint_ids],
                            asset.data.joint_vel[:, asset_cfg.joint_ids])


def joint_deviation_sq(env, asset_cfg=SceneEntityCfg("robot")):
    asset = env.scene[asset_cfg.name]

    return core.joint_deviation_l2(asset.data.joint_pos[:, asset_cfg.joint_ids],
                                   asset.data.default_joint_pos[:, asset_cfg.joint_ids])


def stumble_term(env, sensor_cfg):
    """걸려 넘어짐: 발 접촉력이 수직력의 4 배 넘게 수평 (16 §1 13 항)."""
    sensor = env.scene.sensors[sensor_cfg.name]

    return core.stumble(sensor.data.net_forces_w[:, sensor_cfg.body_ids])


def foot_edge_placeholder(env):
    """발 가장자리 항 자리표시. S1 은 마스크가 없고 가중치가 0 이다 (16 §5). S2 가 마스크 조회로 바꾼다."""
    return torch.zeros(env.num_envs, device=env.device)


@configclass
class StartRewardsCfg:
    """16 §1 의 14 항. 가중치는 `core.WEIGHTS` (S1 은 발 가장자리 0)."""

    track_lin_vel = RewTerm(func=mdp.track_lin_vel_xy_exp, weight=core.WEIGHTS["track_lin_vel"],
                            params={"command_name": "base_velocity", "std": core.STD2 ** 0.5})
    track_ang_vel = RewTerm(func=mdp.track_ang_vel_z_exp, weight=core.WEIGHTS["track_ang_vel"],
                            params={"command_name": "base_velocity", "std": core.STD2 ** 0.5})
    lin_vel_z = RewTerm(func=mdp.lin_vel_z_l2, weight=core.WEIGHTS["lin_vel_z"])
    ang_vel_xy = RewTerm(func=mdp.ang_vel_xy_l2, weight=core.WEIGHTS["ang_vel_xy"])
    flat_orientation = RewTerm(func=mdp.flat_orientation_l2, weight=core.WEIGHTS["flat_orientation"])
    joint_torques = RewTerm(func=mdp.joint_torques_l2, weight=core.WEIGHTS["joint_torques"])
    action_rate = RewTerm(func=mdp.action_rate_l2, weight=core.WEIGHTS["action_rate"])
    action_smoothness = RewTerm(func=action_smoothness_l2, weight=core.WEIGHTS["action_smoothness"])
    joint_power = RewTerm(func=joint_power_abs, weight=core.WEIGHTS["joint_power"])
    joint_acc = RewTerm(func=mdp.joint_acc_l2, weight=core.WEIGHTS["joint_acc"])
    joint_deviation = RewTerm(func=joint_deviation_sq, weight=core.WEIGHTS["joint_deviation"])
    collision = RewTerm(func=mdp.undesired_contacts, weight=core.WEIGHTS["collision"],
                        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=COLLISION_BODIES),
                                "threshold": core.COLLISION_N})
    stumble = RewTerm(func=stumble_term, weight=core.WEIGHTS["stumble"],
                      params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODIES)})
    foot_edge = RewTerm(func=foot_edge_placeholder, weight=core.S1_WEIGHT_OVERRIDES["foot_edge"])
