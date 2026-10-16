"""Opt-in S2-2 reward wiring and constructed-manager evidence."""
from __future__ import annotations

from s2_foot_query import FootQueryTracker, live_raycast
from s2_foot_reward import feet_center_any9_v1

VARIANTS = ("none", "feet_center_any9_v1")
WEIGHT = -0.01
BASELINE_WEIGHTS = {
    "track_lin_vel_xy_exp": 2.0,
    "track_ang_vel_z_exp": 1.0,
    "lin_vel_z_l2": -2.0,
    "ang_vel_xy_l2": -0.05,
    "joint_acc_l2": -1e-7,
    "joint_power": -2e-5,
    "joint_torques_l2": -1e-4,
    "base_height_l2": -1.0,
    "action_rate_l2": -0.01,
    "action_smoothness_l2": -0.01,
    "undesired_contacts": -1.0,
    "joint_pos_limits": -2.0,
    "feet_regulation": -0.05,
    "hip_pos_penalty_l1": -0.05,
    "joint_pos_penalty_l1": -0.01,
}


def validate_variant(variant: str, spacing_m):
    if variant not in VARIANTS:
        raise ValueError("reward_variant_unknown")
    if variant == "none":
        if spacing_m is not None:
            raise ValueError("none_forbids_foot_spacing")
        return
    if type(spacing_m) not in (float, int) or float(spacing_m) != 0.05:
        raise ValueError("feet_center_any9_v1_requires_explicit_0.05_m_spacing")


def foot_reward_term(env, spacing_m: float):
    tracker = getattr(env, "_s2_foot_tracker", None)
    if tracker is None:
        tracker = FootQueryTracker(env.num_envs, spacing_m, device=env.device)
        env._s2_foot_tracker = tracker
    query = live_raycast(env, tracker, spacing_m=spacing_m)
    result = feet_center_any9_v1(query.centers, query.heights, query.status, query.forces)
    env._s2_foot_last_query = query
    env._s2_foot_last_cost = result
    env._s2_foot_central_discrepancy_total = (
        getattr(env, "_s2_foot_central_discrepancy_total", 0) + int(result.central_discrepancy.sum())
    )
    return result.cost


def add_foot_reward(cfg, *, variant="none", spacing_m=None, term_factory=None):
    """Mutate only the opted-in cfg. None is a byte-preserving no-op."""
    validate_variant(variant, spacing_m)
    if variant == "none":
        return cfg
    if hasattr(cfg.rewards, "feet_center_any9_v1"):
        raise ValueError("foot_reward_already_configured")
    if term_factory is None:
        from isaaclab.managers import RewardTermCfg as term_factory
    cfg.rewards.feet_center_any9_v1 = term_factory(
        func=foot_reward_term, weight=WEIGHT, params={"spacing_m": float(spacing_m)}
    )
    return cfg


def manager_reward_receipt(manager, *, variant="none"):
    """Read post-inheritance, post-override RewardManager term names and weights."""
    names = tuple(manager.active_terms)
    weights = {name: float(manager.get_term_cfg(name).weight) for name in names}
    expected = dict(BASELINE_WEIGHTS)
    if variant == "feet_center_any9_v1":
        expected[variant] = WEIGHT
    if len(names) != len(expected) or weights != expected:
        raise ValueError("constructed_reward_manager_mismatch")
    return {"variant": variant, "terms": [{"name": n, "weight": weights[n]} for n in names],
            "count": len(names)}
