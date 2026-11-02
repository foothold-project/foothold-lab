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
    term = env.command_manager.get_term(command_name)
    if getattr(term, "stage_runtime", None) is not None:
        stop = term.stand
    else:
        stop = torch.linalg.vector_norm(command, dim=1) < 0.1
    reward = (stop & in_contact.all(dim=1)).float()
    samples = getattr(env, "_ex39_kit_foot_smoke", None)
    if samples is not None and len(samples) < 8:
        from foothold_s2.commands.mixed_core import EX39_SLOTS

        term = env.command_manager.get_term(command_name)
        stand = term.slot_current == EX39_SLOTS.index("stand")
        samples.append({"stand_envs": int(stand.sum().item()),
                        "four_foot_mean": float(reward[stand].mean().item()) if stand.any() else 0.0})
    return reward


def stand_penalty_values(gap_m, vertical_force_n, mass_kg, stop, elapsed_s,
                         *, gap_weight=-0.2, load_weight=-0.1,
                         load_fraction=0.05, ramp_s=0.5):
    """D70 terms before RewardManager dt; height is collision sole above its ray hit."""
    if (gap_m.shape != vertical_force_n.shape or gap_m.ndim != 2 or gap_m.shape[1] != 4
            or mass_kg.shape != gap_m.shape[:1] or stop.shape != mass_kg.shape
            or elapsed_s.shape != mass_kg.shape
            or not torch.isfinite(mass_kg[stop]).all() or (mass_kg[stop] <= 0).any()):
        raise ValueError("EX-40 stand sensor geometry or mass invalid")
    safe_mass = torch.where(stop, mass_kg, torch.ones_like(mass_kg))
    support = (load_fraction * safe_mass * 9.81)[:, None]
    gap_valid = stop[:, None] & torch.isfinite(gap_m)
    load_valid = stop[:, None] & torch.isfinite(vertical_force_n)
    safe_gap = torch.where(gap_valid, gap_m, torch.full_like(gap_m, 0.005))
    safe_force = torch.where(load_valid, vertical_force_n, support.expand_as(vertical_force_n))
    ramp = torch.where(stop, (elapsed_s / ramp_s).clamp(0.0, 1.0),
                       torch.zeros_like(elapsed_s))
    gap = gap_weight * ((safe_gap - 0.005).clamp_min(0.0) / 0.05).sum(dim=1) * ramp
    load = load_weight * ((support - safe_force.clamp_min(0.0)).clamp_min(0.0)
                          / support).sum(dim=1) * ramp
    return gap, load


class StandSensorEvidence:
    """One CPU transfer per tensor at update end; only recorded EX-40 stand samples."""

    def __init__(self, flat_columns: tuple[int, ...]):
        self.flat_columns = flat_columns
        self._rows = []

    @classmethod
    def from_env(cls, env):
        from foothold_s2.terrains.columns import column_types

        generator = env.scene.terrain.cfg.terrain_generator
        proportions = {name: cfg.proportion for name, cfg in generator.sub_terrains.items()}
        names = column_types(proportions, generator.num_cols)
        return cls(tuple(index for index, name in enumerate(names) if name == "flat"))

    def add(self, gap_m, hit_z, force_z, stop, terrain_types, origin_z):
        self._rows.append(tuple(value.detach().clone() for value in
                                (gap_m, hit_z, force_z, stop, terrain_types, origin_z)))

    def summary(self) -> dict:
        if not self._rows:
            raise ValueError("EX-40 stand sensor evidence missing from update")
        columns = [torch.cat([row[i] for row in self._rows]).cpu() for i in range(6)]
        self._rows.clear()
        gap, hit, force, stop, terrain_types, origin_z = columns
        stand = stop.bool()[:, None].expand_as(hit)
        hit_valid = torch.isfinite(hit)
        force_valid = torch.isfinite(force)
        gap_valid = torch.isfinite(gap)
        valid = stand & hit_valid & gap_valid
        flat = torch.zeros_like(stop, dtype=torch.bool)
        for index in self.flat_columns:
            flat |= terrain_types == index
        flat_valid = valid & flat[:, None]

        def quantiles(foot):
            values = gap[:, foot][valid[:, foot]] * 1000.0
            return ([float(v) for v in torch.quantile(values, torch.tensor([.05, .5, .95]))]
                    if values.numel() else None)

        sample_ids = torch.nonzero(stand & hit_valid, as_tuple=False)[:4]
        samples = [{"row": int(row), "foot": int(foot), "hit_z_m": float(hit[row, foot]),
                    "terrain_origin_z_m": float(origin_z[row]),
                    "hit_minus_origin_z_m": float(hit[row, foot] - origin_z[row])}
                   for row, foot in sample_ids]
        total = int(stand.sum())
        good = int((stand & hit_valid).sum())
        return {"stand_foot_total": total, "hit_valid_count": good,
                "hit_valid_ratio": good / total if total else None,
                "hit_valid_count_by_foot": [int(v) for v in (stand & hit_valid).sum(dim=0)],
                "gap_valid_count_by_foot": [int(v) for v in valid.sum(dim=0)],
                "hit_invalid_by_foot": [int(v) for v in (stand & ~hit_valid).sum(dim=0)],
                "force_nonfinite_by_foot": [int(v) for v in (stand & ~force_valid).sum(dim=0)],
                "gap_nonfinite_by_foot": [int(v) for v in (stand & ~gap_valid).sum(dim=0)],
                "gap_p5_p50_p95_mm_by_foot": [quantiles(i) for i in range(4)],
                "flat_stand_valid_foot_count": int(flat_valid.sum()),
                "flat_gap_p50_mm": (float(torch.median(gap[flat_valid] * 1000.0))
                                    if flat_valid.any() else None),
                "hit_origin_samples": samples, "flat_columns": list(self.flat_columns)}


def _stand_penalties(env, asset_cfg, sensor_cfg, command_name, config, *, record=False):
    robot = env.scene[asset_cfg.name]
    term = env.command_manager.get_term(command_name)
    hit_z = torch.stack([env.scene.sensors[f"ex40_support_{i}"].data.ray_hits_w[:, 0, 2]
                         for i in range(4)], dim=1)
    # Go2 URDF foot collision sphere: local center (-0.002, 0, 0), r=0.022.
    # Transform the center with the full foot orientation, including roll and pitch.
    from isaaclab.utils.math import quat_apply

    center_offset = robot.data.body_pos_w.new_tensor((-0.002, 0.0, 0.0))
    foot_quat = robot.data.body_quat_w[:, asset_cfg.body_ids]
    center_w = robot.data.body_pos_w[:, asset_cfg.body_ids] + quat_apply(
        foot_quat.reshape(-1, 4), center_offset.expand(foot_quat.shape[0] * 4, 3)
    ).reshape(foot_quat.shape[0], 4, 3)
    sole_z = center_w[..., 2] - 0.022
    force_z = env.scene.sensors[sensor_cfg.name].data.net_forces_w[:, sensor_cfg.body_ids, 2]
    mass = env._ex40_total_mass_kg
    gap_m = sole_z - hit_z
    if record and hasattr(env, "_ex40_stand_evidence"):
        evidence = env._ex40_stand_evidence
        evidence.add(gap_m, hit_z, force_z, term.stand,
                     env.scene.terrain.terrain_types, env.scene.terrain.env_origins[:, 2])
    return stand_penalty_values(gap_m, force_z, mass, term.stand,
                                term.stop_elapsed_s, **config)


def ex40_stand_gap(env, asset_cfg, sensor_cfg, command_name, config):
    return _stand_penalties(env, asset_cfg, sensor_cfg, command_name, config,
                            record=True)[0] / config["gap_weight"]


def ex40_stand_load(env, asset_cfg, sensor_cfg, command_name, config):
    return _stand_penalties(env, asset_cfg, sensor_cfg, command_name, config)[1] / config["load_weight"]


def apply_ex40_stand_settings(env_cfg, config):
    from isaaclab.managers import RewardTermCfg as RewTerm, SceneEntityCfg
    from isaaclab.sensors import RayCasterCfg, patterns

    feet = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
    for i, name in enumerate(feet):
        setattr(env_cfg.scene, f"ex40_support_{i}", RayCasterCfg(
            prim_path=f"{{ENV_REGEX_NS}}/Robot/{name}",
            offset=RayCasterCfg.OffsetCfg(pos=(-0.002, 0.0, 20.0)),
            ray_alignment="yaw",
            pattern_cfg=patterns.GridPatternCfg(resolution=0.05, size=[0.0, 0.0], ordering="yx"),
            mesh_prim_paths=["/World/ground"], update_period=0.0))
    args = {"asset_cfg": SceneEntityCfg("robot", body_names=list(feet)),
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=list(feet)),
            "command_name": "base_velocity", "config": dict(config)}
    env_cfg.rewards.ex40_stand_gap = RewTerm(func=ex40_stand_gap,
                                             weight=config["gap_weight"], params=args)
    env_cfg.rewards.ex40_stand_load = RewTerm(func=ex40_stand_load,
                                              weight=config["load_weight"], params=args)


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
