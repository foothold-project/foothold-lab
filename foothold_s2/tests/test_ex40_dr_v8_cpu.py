"""Known-input CPU contract tests for the proposed EX-40 v8 DR schedule."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.curriculum.ex40_dr import (
    DR_ITEMS, DRConfig, dr_scale, interpolate_range, observation_noise_scale,
    phase_bounds, restore_scale, resumable_state, smoke_scale, validate_full_ranges,
)
from foothold_s2.ex40_launch import TABLE, main


def _synthetic_ranges():
    # Test fixture only. These values are not proposed experiment ranges.
    return {
        "base_com": {"x": [-.1, .1], "y": [-.1, .1], "z": [-.1, .1]},
        "actuator_gains": {"scale": [.9, 1.1]},
        "motor_strength": {"scale": [.9, 1.1]},
        "delay_s": [0.0, .015],
        "push_velocity": {"x": [-1.0, 1.0], "y": [-1.0, 1.0]},
        "policy_obs_noise_multiplier": 1.5,
    }


def test_schedule_boundaries_ramp_and_stage_lengths():
    assert [dr_scale(n) for n in (0, 1500, 1501, 3750, 6000, 6001)] == pytest.approx(
        [0.0, 0.0, 0.0, 0.5 * (3750 - 1501) / (6000 - 1501), 0.5, 1.0])
    assert phase_bounds(1500) == {
        "B0": (0, 1500), "B1_B3c": (1501, 6000), "D": (6001, 7500),
        "T0": (7501, 8000), "max_iterations": (0, 8001)}
    assert phase_bounds(3000)["D"] == (6001, 9000)
    assert phase_bounds(3000)["T0"] == (9001, 9500)
    assert phase_bounds(3000)["max_iterations"] == (0, 9501)
    assert [smoke_scale(stage) for stage in ("B0", "B1_B3c", "D", "T0")] == [0.0, .5, 1.0, 1.0]


def test_range_interpolation_noise_formula_and_startup_values_untouched():
    target = _synthetic_ranges()["base_com"]
    assert interpolate_range({"x": [0, 0], "y": [0, 0], "z": [0, 0]}, target, 0) == {
        "x": [0.0, 0.0], "y": [0.0, 0.0], "z": [0.0, 0.0]}
    assert interpolate_range([0.0, .015], [0.0, .015], .5) == [0.0, .015]
    assert observation_noise_scale(1.5, 0) == 1.0
    assert observation_noise_scale(1.5, .5) == 1.25
    assert observation_noise_scale(1.5, 1) == 1.5
    doc = yaml.safe_load(Path(TABLE).read_text(encoding="utf-8"))
    assert doc["domain_randomization"]["preserved_startup"] == {
        "friction_static_dynamic": [.2, 1.2], "base_mass_add_kg": [-1.0, 3.0]}
    assert DR_ITEMS == tuple(doc["domain_randomization"]["full_ranges"])


def test_empty_ranges_refuse_launch_and_filled_fixture_is_valid(tmp_path):
    doc = yaml.safe_load(Path(TABLE).read_text(encoding="utf-8"))
    cfg = doc["domain_randomization"]
    assert cfg["runtime_adapter_status"] == "not_implemented"
    with pytest.raises(ValueError, match="range is blank"):
        DRConfig.from_mapping(cfg, require_launchable=True)
    assert set(validate_full_ranges(_synthetic_ranges())) == set(DR_ITEMS)

    table = tmp_path / "ex40-v8-fixture.yaml"
    cfg["full_ranges"] = _synthetic_ranges()
    cfg["runtime_adapter_status"] = "verified"
    table.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    assert DRConfig.from_mapping(yaml.safe_load(table.read_text(encoding="utf-8"))["domain_randomization"],
                                 require_launchable=True).length_d == 1500

    with pytest.raises(SystemExit):
        main(["--arm", "B", "--device", "cuda:0", "--end-by", "2026-11-05T12:00:00+09:00",
              "--log-root", str(tmp_path / "logs"), "--score-dir", str(tmp_path / "scores"),
              "--table", str(TABLE), "--print-args"])


def test_resume_scale_round_trip_and_rejects_different_plan():
    config = DRConfig.from_mapping({"length_D": 3000, "full_ranges": _synthetic_ranges(),
                                    "runtime_adapter_status": "verified", "range_source": "fixture"})
    saved = resumable_state(6000, config)
    assert saved["scale"] == .5
    assert restore_scale(json.loads(json.dumps(saved)), 6001, config) == 1.0
    with pytest.raises(ValueError, match="resume state mismatch"):
        restore_scale(saved, 6001, DRConfig.from_mapping({
            "length_D": 1500, "full_ranges": _synthetic_ranges(),
            "runtime_adapter_status": "verified", "range_source": "fixture"}))


def test_trainer_gate_runs_before_app_launcher_construction():
    source = (Path(__file__).parents[1] / "scripts" / "train_sol23f_common.py").read_text(encoding="utf-8")
    assert source.index("require_launchable(args_cli.curriculum)") < source.index("app_launcher = AppLauncher(args_cli)")
