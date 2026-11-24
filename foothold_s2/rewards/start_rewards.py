"""START Table I 14 항을 Isaac Lab 보상 설정으로 (16 §7). Kit 안에서만 불린다. 식은 `core.py` 와 같다.

기존 Isaac Lab 항을 재사용하고(`track_lin_vel_xy_exp` 가 B 식과 같다), 없는 항 넷(부드러움 · 관절 일률 · 관절 오차 L2 ·
걸려 넘어짐)과 자리표시 하나(발 가장자리, S1 은 가중치 0 이고 표가 없으면 0)를 새로 쓴다.
"""

import torch

from isaaclab.managers import ManagerTermBase, RewardTermCfg as RewTerm, SceneEntityCfg
from isaaclab.utils import configclass
from isaaclab_tasks.manager_based.locomotion.velocity import mdp

from foothold_s2.rewards import core
from foothold_s2.rewards.penalty_log import record

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

    return record(env, "stumble", core.stumble(sensor.data.net_forces_w[:, sensor_cfg.body_ids]))


def foot_edge_term(env, sensor_cfg, asset_cfg):
    """발 가장자리 항 (16 §2). `env.s2_tables` 의 칸별 마스크를 발 월드 좌표로 조회한다. 표가 없으면(S1) 0."""
    tables = getattr(env, "s2_tables", None)

    if tables is None:
        mesh = getattr(env, "ex42_edge_tables", None)           # EX-42 합친 메시: 메시 윗면에서 만든 마스크 (terrains/ex42_edge_masks.py). 없으면 아래처럼 0 (옛 메시)
        if mesh is None:
            return record(env, "foot_edge", torch.zeros(env.num_envs, device=env.device))
        feet = env.scene[asset_cfg.name].data.body_pos_w[:, asset_cfg.body_ids, :2]
        force = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids]
        contact = torch.linalg.norm(force, dim=-1) > 1.0
        terrain = env.scene.terrain
        return record(env, "foot_edge", mesh.penalty(feet, contact, terrain.terrain_levels, terrain.terrain_types))

    feet = env.scene[asset_cfg.name].data.body_pos_w[:, asset_cfg.body_ids, :2]
    force = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids]
    contact = torch.linalg.norm(force, dim=-1) > 1.0
    terrain = env.scene.terrain

    return record(env, "foot_edge", core.foot_edge_penalty_tiles(feet, contact, tables.inner, tables.outer,
                                                                 terrain.terrain_levels, terrain.terrain_types))


def collision_term(env, sensor_cfg, threshold):
    """충돌 (16 §1 12 항): 설치 `undesired_contacts` 값에 켜짐 비율 기록만 더한다."""
    return record(env, "collision", mdp.undesired_contacts(env, threshold=threshold, sensor_cfg=sensor_cfg))


def track_lin_vel_min_form(env, command_name, std, asset_cfg=SceneEntityCfg("robot")):
    """선속도 추종 A 식(START 원문, 16 §3): exp(-||min(v, cmd) - cmd||^2 / std^2). `track_lin_form = "A"` 일 때만 쓴다."""
    asset = env.scene[asset_cfg.name]
    cmd = env.command_manager.get_command(command_name)[:, :2]

    return torch.exp(-torch.sum((torch.minimum(asset.data.root_lin_vel_b[:, :2], cmd) - cmd) ** 2, dim=-1) / std ** 2)


def track_lin_vel_min_on_columns(env, command_name, std, min_columns, asset_cfg=SceneEntityCfg("robot")):
    """선속도 추종 (EX-42 처방 후보 2): 지형 열이 `min_columns` 인 env 만 START 원문 식 (min(v, cmd), 과속 무벌점), 나머지는 정확 추종 (`track_lin_vel_xy_exp` 와 같은 식).
    항 이름 · std 칸은 그대로라 실시간 조정 (track_lin_vel_std) 이 그대로 먹는다. `EX42_TRACK_LIN_MIN_KINDS` 로 켠다 (ex42_gap_switches)."""
    from foothold_s2.ex42_gap_switches import column_env_mask, track_lin_mixed

    asset = env.scene[asset_cfg.name]
    terrain = env.scene.terrain
    on = column_env_mask(terrain.terrain_types, tuple(min_columns), int(terrain.terrain_origins.shape[1]))

    return track_lin_mixed(asset.data.root_lin_vel_b[:, :2], env.command_manager.get_command(command_name)[:, :2], std, on)


def track_lin_vel_std_on_columns(env, command_name, std, std_columns, std_values, min_columns=(),
                                 asset_cfg=SceneEntityCfg("robot")):
    """EX-42 optional fixed per-kind std. Other columns continue reading the live term's std."""
    from foothold_s2.ex42_gap_switches import track_lin_std_mixed, column_env_mask

    terrain = env.scene.terrain
    types = terrain.terrain_types
    n_columns = int(terrain.terrain_origins.shape[1])
    asset = env.scene[asset_cfg.name]
    value = track_lin_std_mixed(asset.data.root_lin_vel_b[:, :2],
                                env.command_manager.get_command(command_name)[:, :2], std, types, n_columns,
                                tuple(std_columns), tuple(std_values), tuple(min_columns))
    if not getattr(env, "_ex42_track_lin_std_sample_logged", False):
        on = column_env_mask(types, tuple(std_columns), n_columns)
        count = int(on.sum().item())
        if count:
            mean = float(value[on].mean().item())
            print(f"EX42_TRACK_LIN_STD_KINDS sample_envs={count} term_mean={mean:.6g}", flush=True)
            env._ex42_track_lin_std_sample_logged = True
    return value


def calf_ext_limit_band(env, asset_cfg=SceneEntityCfg("robot", joint_names=".*_calf_joint"), margin=core.CALF_BAND_MARGIN):
    """종아리 펴짐 한계 띠 (창 3 처방 후보 1축): 네 calf 의 sum max(0, q - (hard 상한 - margin)). hard 상한은 시뮬레이터(data.joint_pos_limits)에서 읽고 상수로 박지 않는다.
    부호는 가중치가 정한다(음수 가중치 = 벌점). `calf_ext_limit_band_term` 으로 붙이면 기본 가중치 0(꺼짐)이다."""
    asset = env.scene[asset_cfg.name]
    ids = asset_cfg.joint_ids

    return core.calf_extension_band(asset.data.joint_pos[:, ids], asset.data.joint_pos_limits[:, ids, 1], margin)


def calf_ext_limit_band_term(weight=core.CALF_BAND_WEIGHT_OFF, margin=core.CALF_BAND_MARGIN):
    """task cfg 에 `self.rewards.calf_ext_limit_band = calf_ext_limit_band_term(weight=-2.0)` 로 붙인다. 가중치를 안 주면 0 이라 꺼져 있다."""
    return RewTerm(func=calf_ext_limit_band, weight=weight, params={"asset_cfg": SceneEntityCfg("robot", joint_names=".*_calf_joint"), "margin": margin})


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
    collision = RewTerm(func=collision_term, weight=core.WEIGHTS["collision"],
                        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=COLLISION_BODIES),
                                "threshold": core.COLLISION_N})
    stumble = RewTerm(func=stumble_term, weight=core.WEIGHTS["stumble"],
                      params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODIES)})
    foot_edge = RewTerm(func=foot_edge_term, weight=core.S1_WEIGHT_OVERRIDES["foot_edge"],
                        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=FOOT_BODIES),
                                "asset_cfg": SceneEntityCfg("robot", body_names=FOOT_BODIES)})
