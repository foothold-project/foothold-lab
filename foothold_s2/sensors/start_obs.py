"""START runner 가 요구하는 센서 · 관측 묶음을 env cfg 에 붙인다 (Kit 안에서만 import). s2_env_cfg(lead) 와 관문이 같이 쓴다.

runner 계약(runners/start_runner.py 머리말): policy 45 는 env 가 내고, 이 함수가 아래 다섯 묶음과 센서를 더한다.
    depth (N, 3600)   D435i 60x60 정규화 · 증강 (11 §2)
    gt_map (N, 512)   정답 H^b, h = z_hit - z_base, clip ±1 (12 §3 가정) · 32 x 16 · 중력 정렬 yaw 틀
    gt_feet (N, 100)  정답 H^f, 발 4 개 x 5 x 5 · 5 cm (12 §4 가정) · 같은 높이 기준
    base_vel (N, 3)   몸 틀 선속도 (특권)
    contacts (N, 4)   발 접촉 0/1 (특권, 1 N 문턱 · 가정(rl))
"""

from __future__ import annotations

import torch

from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import RayCasterCfg, patterns
from isaaclab.utils import configclass

import isaaclab.envs.mdp as mdp

from foothold_s2.sensors.depth_aug import DepthAugCfg, augment
from foothold_s2.sensors.depth_cam_cfg import make_depth_camera_cfg

FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
AUG = DepthAugCfg()


def depth_obs(env, sensor_cfg: SceneEntityCfg):
    d = env.scene.sensors[sensor_cfg.name].data.output["distance_to_image_plane"]  # (N, 60, 60, 1) m
    return augment(d[..., 0], AUG).flatten(1)


def height_rel_base(env, sensor_cfg: SceneEntityCfg):
    """h = z_hit - z_base, clip ±1 m. 못 맞힌 광선은 -1."""
    z = env.scene.sensors[sensor_cfg.name].data.ray_hits_w[..., 2]
    base_z = env.scene["robot"].data.root_pos_w[:, 2:3]
    return torch.nan_to_num(z - base_z, nan=-1.0, posinf=-1.0, neginf=-1.0).clamp(-1.0, 1.0)


def feet_height(env):
    return torch.cat([height_rel_base(env, SceneEntityCfg(f"foot_scan_{i}")) for i in range(4)], -1)


def feet_contact(env, sensor_cfg: SceneEntityCfg):
    f = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids]
    return (f.norm(dim=-1) > 1.0).float()


@configclass
class DepthGroup(ObsGroup):
    depth = ObsTerm(func=depth_obs, params={"sensor_cfg": SceneEntityCfg("depth_cam")})


@configclass
class GtMapGroup(ObsGroup):
    gt_map = ObsTerm(func=height_rel_base, params={"sensor_cfg": SceneEntityCfg("gt_map_scan")})


@configclass
class GtFeetGroup(ObsGroup):
    gt_feet = ObsTerm(func=feet_height)


@configclass
class BaseVelGroup(ObsGroup):
    base_vel = ObsTerm(func=mdp.base_lin_vel)


@configclass
class ContactsGroup(ObsGroup):
    contacts = ObsTerm(func=feet_contact, params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=list(FEET))})


def apply_start_perception(env_cfg, robot_base: str = "{ENV_REGEX_NS}/Robot/base") -> None:
    """env cfg 에 D435i · 정답 지도 · 발 지도 센서와 runner 관측 묶음 다섯을 더한다. policy 묶음(45)은 건드리지 않는다.

    scene 에 contact_forces(ContactSensor, 발 몸체 포함) 가 있어야 한다. 지면은 `/World/ground` 단일 결합 Mesh.
    """
    s = env_cfg.scene
    s.depth_cam = make_depth_camera_cfg(robot_base)
    # 32 x 16 칸 중심 x -0.475..1.075 · y -0.375..0.375 -> 크기 1.55 x 0.75 · 가운데 x 0.3 (12 §3 가정)
    s.gt_map_scan = RayCasterCfg(
        prim_path=robot_base,
        offset=RayCasterCfg.OffsetCfg(pos=(0.3, 0.0, 20.0)),
        ray_alignment="yaw",
        pattern_cfg=patterns.GridPatternCfg(resolution=0.05, size=[1.55, 0.75], ordering="yx"),
        mesh_prim_paths=["/World/ground"],
    )
    root = robot_base.rsplit("/", 1)[0]
    for i, foot in enumerate(FEET):
        setattr(s, f"foot_scan_{i}", RayCasterCfg(
            prim_path=f"{root}/{foot}",
            offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
            ray_alignment="yaw",
            pattern_cfg=patterns.GridPatternCfg(resolution=0.05, size=[0.2, 0.2], ordering="yx"),
            mesh_prim_paths=["/World/ground"],
        ))
    o = env_cfg.observations
    o.depth = DepthGroup()
    o.gt_map = GtMapGroup()
    o.gt_feet = GtFeetGroup()
    o.base_vel = BaseVelGroup()
    o.contacts = ContactsGroup()
