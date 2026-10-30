"""Known-input CPU contract tests for the proposed EX-40 v8 DR schedule."""

from __future__ import annotations

import json
import ast
from pathlib import Path

import pytest
import yaml

from foothold_s2.curriculum.ex40_dr import (
    DR_ITEMS, DRConfig, delay_limit, dr_scale, interpolate_range,
    phase_bounds, restore_scale, resumable_state, smoke_scale, validate_full_ranges,
)
from foothold_s2.ex40_launch import TABLE, main


def _synthetic_ranges():
    # Test fixture only. These values are not proposed experiment ranges.
    return {
        "base_com": {"x": [-.1, .1], "y": [-.1, .1], "z": [-.1, .1]},
        "actuator_gains": {"stiffness_scale": [.9, 1.1], "damping_scale": [.9, 1.1]},
        "motor_strength": [.9, 1.1],
        "delay_s": [0.0, .015],
        "push_velocity": {axis: [-1.0, 1.0] for axis in ("x", "y", "z", "roll", "pitch", "yaw")},
    }


def test_schedule_boundaries_ramp_and_stage_lengths():
    assert [dr_scale(n) for n in (0, 1500, 1501, 3750, 6000, 6001)] == pytest.approx(
        [0.0, 0.0, 0.0, 0.5 * (3750 - 1501) / (6000 - 1501), 0.5, 1.0])
    assert phase_bounds(1500) == {
        "B0": (0, 1500), "B1_B3c": (1501, 6000), "D": (6001, 7500),
        "T0": (7501, 8000), "max_iterations": (0, 8001)}
    with pytest.raises(ValueError, match="fixes L_D at 1500"):
        phase_bounds(3000)
    assert [smoke_scale(stage) for stage in ("B0", "B1_B3c", "D", "T0")] == [0.0, .5, 1.0, 1.0]
    assert delay_limit(0.0) == {"max_seconds": 0.0, "rounded_substeps": 0,
                                "physics_dt_seconds": .005}
    assert delay_limit(.5)["rounded_substeps"] == 2
    assert delay_limit(1.0)["rounded_substeps"] == 3


def test_range_interpolation_fixed_noise_and_startup_values_untouched():
    target = _synthetic_ranges()["base_com"]
    assert interpolate_range({"x": [0, 0], "y": [0, 0], "z": [0, 0]}, target, 0) == {
        "x": [0.0, 0.0], "y": [0.0, 0.0], "z": [0.0, 0.0]}
    assert interpolate_range([0.0, .015], [0.0, .015], .5) == [0.0, .015]
    doc = yaml.safe_load(Path(TABLE).read_text(encoding="utf-8"))
    assert doc["domain_randomization"]["observation_noise"] == {"mode": "fixed", "multiplier": 1.0}
    bad_noise = dict(doc["domain_randomization"], observation_noise={"mode": "schedule", "multiplier": 0.5})
    with pytest.raises(ValueError, match="must stay fixed at 1x"):
        DRConfig.from_mapping(bad_noise)
    assert doc["domain_randomization"]["preserved_startup"] == {
        "friction_static_dynamic": [.2, 1.2], "base_mass_add_kg": [-1.0, 3.0]}
    assert DR_ITEMS == tuple(doc["domain_randomization"]["full_ranges"])


def test_empty_ranges_refuse_launch_and_filled_fixture_is_valid(tmp_path):
    doc = yaml.safe_load(Path(TABLE).read_text(encoding="utf-8"))
    cfg = doc["domain_randomization"]
    assert cfg["runtime_adapter_status"] == "implementation_in_progress"
    assert cfg["observation_noise"] == {"mode": "fixed", "multiplier": 1.0}
    with pytest.raises(ValueError, match="range is blank"):
        DRConfig.from_mapping(cfg, require_launchable=True)
    assert set(validate_full_ranges(_synthetic_ranges())) == set(DR_ITEMS)

    table = tmp_path / "ex40-v8-fixture.yaml"
    cfg["full_ranges"] = _synthetic_ranges()
    cfg["runtime_adapter_status"] = "verified"
    cfg["push_interval_s"] = [.5, 1.0]
    table.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    assert DRConfig.from_mapping(yaml.safe_load(table.read_text(encoding="utf-8"))["domain_randomization"],
                                 require_launchable=True).length_d == 1500

    with pytest.raises(SystemExit):
        main(["--arm", "B", "--device", "cuda:0", "--end-by", "2026-11-05T12:00:00+09:00",
              "--log-root", str(tmp_path / "logs"), "--score-dir", str(tmp_path / "scores"),
              "--table", str(TABLE), "--print-args"])


def test_resume_scale_round_trip_and_rejects_different_plan():
    config = DRConfig.from_mapping({"length_D": 1500, "full_ranges": _synthetic_ranges(),
                                    "runtime_adapter_status": "verified", "range_source": "fixture"})
    saved = resumable_state(6000, config)
    assert saved["scale"] == .5
    assert restore_scale(json.loads(json.dumps(saved)), 6001, config) == 1.0
    with pytest.raises(ValueError, match="resume state mismatch"):
        restore_scale(saved, 6001, DRConfig.from_mapping({
            "length_D": 1500, "full_ranges": _synthetic_ranges(),
            "runtime_adapter_status": "verified", "range_source": "fixture",
            "push_interval_s": [0.5, 1.0]}))


def test_trainer_gate_runs_before_app_launcher_construction():
    source = (Path(__file__).parents[1] / "scripts" / "train_sol23f_common.py").read_text(encoding="utf-8")
    assert source.index("EX40_DR_CONFIG = require_launchable(args_cli.curriculum)") < source.index("app_launcher = AppLauncher(args_cli)")


def test_installed_isaac_event_signatures_are_the_called_contracts():
    isaac = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/events.py")
    tree = ast.parse(isaac.read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    assert [arg.arg for arg in functions["randomize_rigid_body_com"].args.args] == [
        "env", "env_ids", "com_range", "asset_cfg"]
    assert [arg.arg for arg in functions["push_by_setting_velocity"].args.args] == [
        "env", "env_ids", "velocity_range", "asset_cfg"]
    gain_call = next(node for node in functions["randomize_actuator_gains"].body
                     if isinstance(node, ast.FunctionDef) and node.name == "__call__")
    assert [arg.arg for arg in gain_call.args.args] == ["self", "env", "env_ids", "asset_cfg",
                                                         "stiffness_distribution_params",
                                                         "damping_distribution_params", "operation", "distribution"]
    adapter = (Path(__file__).parents[1] / "curriculum" / "ex40_dr_runtime.py").read_text(encoding="utf-8")
    for call in ("events.randomize_rigid_body_com(", "events.randomize_actuator_gains(",
                 "events.push_by_setting_velocity("):
        assert call in adapter
    action_source = (Path(__file__).parents[1] / "tasks" / "delayed_action.py").read_text(encoding="utf-8")
    assert "dr_scale_from_env" in action_source and "_ex40_dr_scale" in action_source
    assert "round(float(scale) * self.cfg.max_delay_s / self._env.physics_dt)" in action_source
    assert 'mode="reset"' in adapter and 'mode="interval"' in adapter


def test_runtime_readback_accepts_measured_values_and_rejects_forged_schedule():
    from foothold_s2.curriculum.ex40_dr_runtime import validate_runtime_summary

    sample_summary = {name: {"count": 1, "min": 0.0, "max": 0.0, "mean": 0.0}
        for name in ("base_com_offset_m", "actuator_gains", "motor_strength_multiplier",
                     "motor_effort_limit", "motor_saturation_effort", "push_velocity_delta")}
    row = {"it": 6001, "ex40_dr": {"update": 6001, "scale": 1.0,
        "actual_samples": sample_summary, "realized_state": {
            "base_com_offset_m": {"count": 12, "min": -.02, "max": .02, "mean": 0.0},
            "delay_substeps": {"count": 4, "min": 0, "max": 2, "mean": 1.0},
            "motor.stiffness": {"count": 12, "min": .9, "max": 1.1, "mean": 1.0},
            "motor.damping": {"count": 12, "min": .9, "max": 1.1, "mean": 1.0},
            "motor.effort_limit": {"count": 12, "min": 8.0, "max": 12.0, "mean": 10.0},
            "motor.saturation_effort": {"count": 12, "min": 20.0, "max": 30.0, "mean": 25.0}},
        "delay_readback": {"count": 4, "reset_sample_count": 4, "observed_min_substeps": 0,
            "observed_max_substeps": 2, "max_allowed_substeps": 3,
            "current_histogram": [1, 2, 1, 0], "reset_sample_histogram": [1, 1, 2, 0],
            "max_seconds": .015, "physics_dt_seconds": .005},
        "observation_noise": {"mode": "fixed", "multiplier": 1.0},
        "pending_values": ["push_velocity"]}}
    validate_runtime_summary(row, 6001)
    validate_runtime_summary(row, 6001, require_event_samples=True)
    row["ex40_dr"]["observation_noise"] = {"mode": "scheduled", "multiplier": 0.5}
    with pytest.raises(ValueError, match="fixed at 1x"):
        validate_runtime_summary(row, 6001)
    row["ex40_dr"]["observation_noise"] = {"mode": "fixed", "multiplier": 1.0}
    row["ex40_dr"]["scale"] = .5
    with pytest.raises(ValueError, match="scale differs"):
        validate_runtime_summary(row, 6001)


def test_runtime_sample_counters_distinguish_zero_events_from_smoke_coverage():
    from foothold_s2.curriculum.ex40_dr_runtime import validate_runtime_summary

    names = ("base_com_offset_m", "actuator_gains", "motor_strength_multiplier",
             "motor_effort_limit", "motor_saturation_effort", "push_velocity_delta")
    row = {"ex40_dr": {"update": 0, "scale": 0.0,
        "observation_noise": {"mode": "fixed", "multiplier": 1.0},
        "actual_samples": {name: {"count": 0, "min": None, "max": None, "mean": None}
                           for name in names},
        "delay_readback": {"count": 1, "reset_sample_count": 1, "observed_min_substeps": 0,
            "observed_max_substeps": 0, "max_allowed_substeps": 0,
            "current_histogram": [1], "reset_sample_histogram": [1],
            "max_seconds": 0.0, "physics_dt_seconds": .005},
        "realized_state": {"base_com_offset_m": {"count": 1}, "delay_substeps": {"count": 1},
            "motor.stiffness": {"count": 1}, "motor.damping": {"count": 1},
            "motor.effort_limit": {"count": 1}, "motor.saturation_effort": {"count": 1}},
        "pending_values": ["push_velocity"]}}
    validate_runtime_summary(row, 0)
    with pytest.raises(ValueError, match="did not produce actual samples"):
        validate_runtime_summary(row, 0, require_event_samples=True)


def test_push_range_remains_blank_noise_is_fixed_and_launch_blocked():
    doc = yaml.safe_load(Path(TABLE).read_text(encoding="utf-8"))
    cfg = doc["domain_randomization"]
    assert cfg["full_ranges"]["push_velocity"] is None
    assert cfg["observation_noise"] == {"mode": "fixed", "multiplier": 1.0}
    assert cfg["push_interval_s"] is None
    with pytest.raises(ValueError, match="range is blank"):
        DRConfig.from_mapping(cfg, require_launchable=True)
