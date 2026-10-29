"""Opt-in EX-36 extension reward settings. Baseline weights remain unchanged by default."""

from __future__ import annotations

import math

import torch


WEIGHT_NAMES = ("track_ang_vel", "track_lin_vel", "joint_acc", "hip_pos_penalty")
BASELINE = {"track_ang_vel": 0.5, "track_lin_vel": 1.5, "joint_acc": -2.5e-7}
E1_CANDIDATE = {"track_ang_vel": 1.0, "track_lin_vel": 2.0,
                "joint_acc": -1.0e-7, "hip_pos_penalty": -0.05}


def validate_settings(weights: dict[str, float | None], lin_vel_z_schedule: bool,
                      feet_regulation_weight: float | None) -> dict:
    if set(weights) != set(WEIGHT_NAMES):
        raise ValueError("basic reward settings need four named weight slots")
    if feet_regulation_weight is not None:
        raise ValueError("feet_regulation ground adapter is unverified; weight slot cannot be enabled")
    selected = {}
    for name, value in weights.items():
        if value is None:
            continue
        v = float(value)
        if not math.isfinite(v) or (name in ("joint_acc", "hip_pos_penalty") and v > 0) or (
                name in ("track_ang_vel", "track_lin_vel") and v < 0):
            raise ValueError(f"invalid basic reward weight: {name}")
        selected[name] = v
    return {"weights": selected, "lin_vel_z_schedule": bool(lin_vel_z_schedule),
            "feet_regulation": "reserved_adapter_unverified"}


def scheduled_lin_vel_z_weight(iteration: int, end_iteration: int = 1500,
                               start_iteration: int = 0) -> float:
    """E1 schedule: -2 at this segment's first update, 0 after 1500 updates."""
    if iteration < 0 or start_iteration < 0 or end_iteration <= 0:
        raise ValueError("invalid reward schedule update")
    elapsed = max(0, iteration - start_iteration)
    return -2.0 * (1.0 - min(elapsed, end_iteration) / end_iteration)


def apply_settings(env_cfg, settings: dict) -> dict:
    """Call before gym.make; no Isaac imports unless the hip term is selected."""
    selected = settings["weights"]
    for name in ("track_ang_vel", "track_lin_vel", "joint_acc"):
        if name in selected:
            getattr(env_cfg.rewards, name).weight = selected[name]
    if "hip_pos_penalty" in selected:
        from isaaclab.managers import RewardTermCfg as RewTerm, SceneEntityCfg

        env_cfg.rewards.basic_hip_pos_penalty_l1 = RewTerm(
            func=hip_pos_penalty_l1, weight=selected["hip_pos_penalty"],
            params={"command_name": "base_velocity",
                    "asset_cfg": SceneEntityCfg("robot", joint_names=".*_hip_joint"),
                    "stand_still_scale": 1.0, "command_threshold": 0.1})
    return settings


def hip_pos_penalty_l1(env, command_name, asset_cfg, stand_still_scale, command_threshold):
    """E1 hip L1 term, copied formula from installed RobotLab Go2 mdp/rewards.py:553-573."""
    asset = env.scene[asset_cfg.name]
    command = env.command_manager.get_command(command_name)[:, [1, 2]]
    cmd_large = torch.any(torch.abs(command) > command_threshold, dim=1)
    running_reward = torch.linalg.norm(
        asset.data.joint_pos[:, asset_cfg.joint_ids]
        - asset.data.default_joint_pos[:, asset_cfg.joint_ids], dim=1, ord=1)
    return torch.where(cmd_large, running_reward, stand_still_scale * running_reward)


def thigh_calf_pos_penalty_l1(env, asset_cfg):
    """E1 joint_pos_penalty_l1 with stand_still_scale=1; RobotLab rewards.py:112-130."""
    asset = env.scene[asset_cfg.name]
    return torch.linalg.norm(asset.data.joint_pos[:, asset_cfg.joint_ids]
                             - asset.data.default_joint_pos[:, asset_cfg.joint_ids], dim=1, ord=1)


def four_foot_contact_at_stop(env, command_name, sensor_cfg, threshold=1.0):
    """D55 proposed +0.1 term: all four feet currently contact while command is zero."""
    command = env.command_manager.get_command(command_name)
    forces = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids]
    if forces.shape[1] != 4:
        raise ValueError("EX-39 stand contact requires four foot bodies")
    in_contact = torch.linalg.vector_norm(forces, dim=-1) > threshold
    return ((torch.linalg.vector_norm(command, dim=1) < 0.1) & in_contact.all(dim=1)).float()


def apply_ex39_settings(env_cfg, contact_weight: float = 0.1) -> dict:
    """Add the two D55 terms to both arms after the unchanged EX-38 reward bundle."""
    from isaaclab.managers import RewardTermCfg as RewTerm, SceneEntityCfg

    if contact_weight != 0.1:
        raise ValueError("EX-39 contact weight needs a new decision")
    env_cfg.rewards.ex39_thigh_calf_pos_l1 = RewTerm(
        func=thigh_calf_pos_penalty_l1, weight=-0.01,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=".*_(thigh|calf)_joint")})
    env_cfg.rewards.ex39_four_foot_stop = RewTerm(
        func=four_foot_contact_at_stop, weight=contact_weight,
        params={"command_name": "base_velocity", "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"),
                "threshold": 1.0})
    return {"thigh_calf_pos_l1": -0.01, "stand_four_foot_contact": contact_weight,
            "feet_regulation": "candidate_only_not_enabled"}


def set_lin_vel_z_weight(env, iteration: int, start_iteration: int = 0) -> float:
    """Call at each update boundary after RewardManager registered its nonzero base term."""
    weight = scheduled_lin_vel_z_weight(iteration, start_iteration=start_iteration)
    manager = env.unwrapped.reward_manager
    term = manager.get_term_cfg("lin_vel_z")
    term.weight = weight
    manager.set_term_cfg("lin_vel_z", term)
    return weight
