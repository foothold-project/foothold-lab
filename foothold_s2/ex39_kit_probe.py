"""Read the live EX-39 Kit environment during the isolated two-update smoke."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import torch

from foothold_s2.commands.mixed_core import EX39_SLOTS, make_generator


FEET = {f"{leg}_foot" for leg in ("FL", "FR", "RL", "RR")}
JOINTS = {f"{leg}_{part}_joint" for leg in ("FL", "FR", "RL", "RR")
          for part in ("thigh", "calf")}
WEIGHTS = {"ex39_thigh_calf_pos_l1": -0.01,
           "ex39_four_foot_stop": 0.1,
           "basic_hip_pos_penalty_l1": -0.05,
           "track_ang_vel": 1.0,
           "track_lin_vel": 2.0,
           "joint_acc": -1.0e-7}


def _write(log_dir, row):
    path = Path(log_dir) / "ex39_kit_probe.json"
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def slot_snapshot(term, arm, include_pair_arrays=False):
    """Measure sampled slots and heading on the actual CommandTerm, not its cfg."""
    slots = term.slot_current.detach().cpu()
    heading = term.heading.detach().cpu()
    valid = slots >= 0
    counts = {name: int((slots == i).sum()) for i, name in enumerate(EX39_SLOTS)}
    fwd = slots == 0
    spin = (slots == 3) | (slots == 4)
    out = {"sampled_envs": int(valid.sum()), "slot_counts": counts,
           "heading_envs": int(heading.sum()),
           "heading_fraction": float(heading[valid].float().mean()) if valid.any() else None,
           "heading_forward_fraction": float(heading[fwd].float().mean()) if fwd.any() else None,
           "heading_spin_fraction": float(heading[spin].float().mean()) if spin.any() else None}
    if not valid.all() or out["sampled_envs"] != len(slots):
        raise AssertionError("EX-39 command slots missing after env reset")
    if arm == "A":
        if heading.any():
            raise AssertionError("EX-39A heading enabled")
    elif (not 0.19 <= out["heading_fraction"] <= 0.23
          or not 0.42 <= out["heading_forward_fraction"] <= 0.58
          or not 0.20 <= out["heading_spin_fraction"] <= 0.40):
        raise AssertionError("EX-39B sampled heading ratios outside smoke bounds")
    if include_pair_arrays:
        out["slot_ids"] = slots.tolist()
        out["heading_ids"] = heading.tolist()
        out["commands"] = term.vel_command_b.detach().cpu().tolist()
        out["rng_state_sha256"] = hashlib.sha256(term.gen.get_state().cpu().numpy().tobytes()).hexdigest()
    return out


def capture_start(raw, cfg, arm, log_dir, contract_name):
    term = raw.command_manager.get_term("base_velocity")
    manager = raw.reward_manager
    robot = raw.scene["robot"]
    sensor = raw.scene.sensors["contact_forces"]
    row = {"stage": "env_created", "arm": arm, "checks": {}, "result": "FAIL"}
    try:
        assert cfg.commands.base_velocity.params["ex39_arm"] == term.params.ex39_arm == arm
        assert tuple(term.slot_names) == tuple(EX39_SLOTS)
        assert cfg.curriculum.terrain_levels is None and cfg.curriculum.command_range is None
        if contract_name != "basic_gait_ex39":
            raise AssertionError(f"EX-39 live runner command contract is {contract_name!r}")
        row["contract_name"] = contract_name
        row["checks"]["command_contract"] = True
        assert set(WEIGHTS).issubset(set(manager.active_terms))
        actual = {name: float(manager.get_term_cfg(name).weight) for name in WEIGHTS}
        assert all(abs(actual[name] - expected) < 1e-10 for name, expected in WEIGHTS.items())
        row["weights"] = actual
        thigh_cfg = manager.get_term_cfg("ex39_thigh_calf_pos_l1").params["asset_cfg"]
        foot_cfg = manager.get_term_cfg("ex39_four_foot_stop").params["sensor_cfg"]
        thigh_names = [robot.joint_names[i] for i in thigh_cfg.joint_ids]
        foot_names = [sensor.body_names[i] for i in foot_cfg.body_ids]
        assert set(thigh_names) == JOINTS and len(thigh_names) == 8
        assert set(foot_names) == FEET and len(foot_names) == 4
        assert tuple(sensor.data.net_forces_w[:, foot_cfg.body_ids].shape) == (raw.num_envs, 4, 3)
        row["resolved_joint_names"] = thigh_names
        row["resolved_foot_names"] = foot_names
        row["checks"]["reward_resolution"] = True
        levels = raw.scene.terrain.terrain_levels.detach().cpu()
        expected_levels = cfg.basic_ex39_level_count if hasattr(cfg, "basic_ex39_level_count") else 3
        assert len(levels) == raw.num_envs == 3072
        assert int(levels.min()) == 0 and int(levels.max()) == expected_levels - 1
        row["terrain_level_counts"] = {str(i): int((levels == i).sum()) for i in range(expected_levels)}
        row["checks"]["terrain_levels"] = True
        row["first_resample"] = slot_snapshot(term, arm)
        if arm == "B":
            fwd_heading = (term.slot_current == 0) & term.heading
            assert fwd_heading.any()
            diff = (term.psi_star[fwd_heading] - robot.data.heading_w[fwd_heading]).abs().max().item()
            assert diff < 1e-6
            row["first_forward_psi_yaw_max_abs"] = diff
            spin_heading = ((term.slot_current == 3) | (term.slot_current == 4)) & term.heading
            assert spin_heading.any()
            assert torch.count_nonzero(term.vel_command_b[spin_heading, :2]) == 0
        row["checks"]["first_heading"] = True
        row["result"] = "PASS"
    except BaseException as exc:
        row["error"] = repr(exc)
        _write(log_dir, row)
        raise
    _write(log_dir, row)
    raw._ex39_kit_foot_smoke = []
    return row


def capture_finish(raw, log_dir):
    path = Path(log_dir) / "ex39_kit_probe.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    term = raw.command_manager.get_term("base_velocity")
    arm = row["arm"]
    samples = getattr(raw, "_ex39_kit_foot_smoke", [])
    row["first_eight_reward_step_four_foot"] = samples
    try:
        z_weight = float(raw.reward_manager.get_term_cfg("lin_vel_z").weight)
        assert abs(z_weight) < 1e-10
        row["lin_vel_z_weight_after_update_3002"] = z_weight
        if arm == "B":
            detail = term.ex39_first_forward_heading_wz_detail
            row["first_forward_heading_wz_detail"] = detail
            row["first_forward_heading_wz_max"] = term.ex39_first_forward_heading_wz_max
            check_first_forward_heading(detail)
        assert len(samples) == 8 and max(x["four_foot_mean"] for x in samples) > 0.0
        # Diagnostic command-only resamples after runner.learn saved the checkpoint.
        # These are not physics steps and are excluded from the training rollout.
        ids = torch.arange(raw.num_envs, device=raw.device)
        term.gen = make_generator(42, device=raw.device)
        row["post_save_command_only_resamples"] = []
        for _ in range(2):
            term._resample_command(ids)
            row["post_save_command_only_resamples"].append(slot_snapshot(term, arm, include_pair_arrays=True))
        row["checks"]["post_save_resamples"] = True
        row["checks"]["four_foot_mean"] = True
        row["result"] = "PASS"
    except BaseException as exc:
        row["result"] = "FAIL"
        row["error"] = repr(exc)
        _write(log_dir, row)
        raise
    _write(log_dir, row)
    return row


def check_first_forward_heading(detail):
    """First physics step may rotate yaw after resample; compare that step's rule."""
    if (not isinstance(detail, dict) or detail.get("env_count", 0) < 1
            or detail.get("error_abs_max") is None or detail.get("observed_abs_max") is None
            or detail["error_abs_max"] > 1.0e-5 or detail["observed_abs_max"] > 0.1):
        raise AssertionError("EX-39 first heading wz differs from the live heading rule or exceeds 0.1")
    return detail
