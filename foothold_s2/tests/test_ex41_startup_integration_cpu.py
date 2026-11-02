from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

import gymnasium as gym
import pytest
import torch

from foothold_s2.curriculum.ex41_fixed import baseline_counts
from foothold_s2.scripts.ex41_startup import (
    capture_first_observation,
    configure_ex41_train_cfg,
    first_observation_readback,
    install_initial_dr_scale,
    load_fixed_plan,
    prepare_ex41_env_cfg,
    require_production_authorization,
    set_live_initial_dr_scale,
    validate_rehearsal_request,
)


REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "foothold_s2/curriculum/ex41-fixed5000.yaml"


def test_ex41_task_registration_and_config_entrypoint_source():
    __import__("foothold_s2.sb_tasks")

    spec = gym.spec("FootholdS2-Go2-S2-SB-v0")
    module_name, class_name = spec.kwargs["env_cfg_entry_point"].split(":", 1)
    config_path = REPO.joinpath(*module_name.split(".")).with_suffix(".py")
    tree = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
    assert class_name == "FootholdS2SBEnvCfg"
    assert any(isinstance(node, ast.ClassDef) and node.name == class_name for node in tree.body)
    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    assert source.index("import foothold_s2.sb_tasks") < source.index("@hydra_task_config")


def test_real_fixed_plan_has_pinned_m6000_dr_half_and_26_maintenance_cells():
    plan = load_fixed_plan(TABLE)
    baseline = baseline_counts(plan)
    assert plan.parent_update == 6000
    assert plan.initial_dr_scale == 0.5
    assert len(baseline) == 26
    assert plan.fixed_schedule["duration_updates"] == 5000


def test_current_production_boundary_refuses_unverified_w71():
    plan = load_fixed_plan(TABLE)
    with pytest.raises(ValueError, match="W71 consumer is not verified"):
        require_production_authorization(plan)


def test_entrypoint_authorization_precedes_app_import_and_wires_consumers():
    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    assert source.index("require_production_authorization(EX41_PLAN)") < source.index(
        "from isaaclab.app import AppLauncher")
    assert "prepare_ex41_env_cfg(env_cfg, EX41_PLAN)" in source
    assert "attach_runtime(env.unwrapped, EX41_PLAN, log_dir)" in source
    assert "ex41_runtime.start(EX41_PLAN.parent_sha256)" in source
    assert "runner.load_ex41_parent()" in source
    assert "runner.ex41_w86_required" in source
    assert source.index("prepare_ex41_env_cfg(env_cfg, EX41_PLAN)") < source.index("gym.make(")
    assert "apply_ex41_pose_observation(env_cfg)" in (
        REPO / "foothold_s2/scripts/ex41_startup.py").read_text(encoding="utf-8")


def test_ex41_env_preparation_calls_pose_producer_and_records_contract(monkeypatch):
    called = []
    monkeypatch.setitem(sys.modules, "foothold_s2.curriculum.ex41", SimpleNamespace(
        prepare_terrain_cfg=lambda cfg, plan: {"terrain": "fixed"}))
    monkeypatch.setitem(sys.modules, "foothold_s2.curriculum.ex40_dr_runtime", SimpleNamespace(
        install_runtime_events=lambda *args, **kwargs: {"events": "installed"}))
    monkeypatch.setitem(sys.modules, "foothold_s2.rewards.w86_runtime", SimpleNamespace(
        prepare_env_cfg=lambda cfg, plan: {"weights": ["swing"]}))

    def attach_pose(cfg):
        called.append(cfg)
        cfg.observations.pose_cmd = object()

    monkeypatch.setitem(sys.modules, "foothold_s2.sensors.start_obs", SimpleNamespace(
        apply_ex41_pose_observation=attach_pose))
    terms = {name: SimpleNamespace(func=lambda env, *args, **kwargs: None)
             for name in ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")}
    cfg = SimpleNamespace(observations=SimpleNamespace(), events=SimpleNamespace(**terms))
    plan = SimpleNamespace(domain_randomization={"full_ranges": {"delay_s": [0., .015]},
                                                  "push_interval_s": [10., 15.]},
                           initial_dr_scale=.5)

    receipt = prepare_ex41_env_cfg(cfg, plan)

    assert called == [cfg]
    assert cfg.observations.pose_cmd is not None
    assert receipt["pose_observation"] == {
        "group": "pose_cmd", "shape_per_env": [2],
        "columns": ["height_delta_m", "body_roll_rad"],
        "configured_value": [0.0, 0.0],
        "producer": "foothold_s2.sensors.start_obs.zero_pose_command"}


def _first_obs(envs=3, pose=None):
    return {"policy": torch.zeros(envs, 45), "depth": torch.zeros(envs, 60, 60),
            "gt_map": torch.zeros(envs, 512), "gt_feet": torch.zeros(envs, 100),
            "base_vel": torch.zeros(envs, 3), "contacts": torch.zeros(envs, 4),
            "pose_cmd": torch.zeros(envs, 2) if pose is None else pose}


def test_first_observation_readback_validates_dimensions_and_zero_pose_columns():
    receipt = first_observation_readback(_first_obs(), expected_envs=3)
    assert receipt["groups"] == {"policy": [45], "depth": [60, 60], "gt_map": [512],
                                 "gt_feet": [100], "base_vel": [3], "contacts": [4],
                                 "pose_cmd": [2]}
    assert receipt["pose_cmd"]["zero_by_column"] == [True, True]
    assert receipt["pose_cmd"]["shape"] == [3, 2]
    bad = _first_obs(pose=torch.tensor([[0., 0.], [0., .1], [0., 0.]]))
    with pytest.raises(ValueError, match="columns are not both zero"):
        first_observation_readback(bad, expected_envs=3)


def test_first_observation_capture_does_not_read_environment_twice():
    class Env:
        num_envs = 3

        def __init__(self):
            self.calls = 0

        def get_observations(self):
            self.calls += 1
            return _first_obs()

    env = Env()
    original = env.get_observations
    with capture_first_observation(env) as receipt:
        observed = env.get_observations()
    assert env.calls == 1
    assert env.get_observations == original
    assert observed["pose_cmd"].shape == (3, 2)
    assert receipt["pose_cmd"]["zero_by_column"] == [True, True]


def test_train_cfg_requires_pose_and_w86_with_pinned_parent(tmp_path):
    plan = load_fixed_plan(TABLE)
    parent = tmp_path / "model_6000.pt"
    parent.write_bytes(b"test checkpoint placeholder")
    cfg = configure_ex41_train_cfg({}, plan, parent)
    assert cfg["ex41_pose_commands"] is True
    assert cfg["ex41_w86_required"] is True
    assert cfg["max_iterations"] == 6501
    assert cfg["ex41_parent"] == {"path": str(parent.resolve()),
                                  "sha256": plan.parent_sha256, "iteration": 6000}


def test_rehearsal_config_is_bounded_and_uses_isolated_output(tmp_path):
    plan = load_fixed_plan(TABLE)
    parent = tmp_path / "model_6000.pt"
    parent.write_bytes(b"known parent")
    configured = configure_ex41_train_cfg(
        {"ex41_w86_required": True, "save_interval": 100}, plan, parent,
        rehearsal_updates=10)
    assert configured["max_iterations"] == 10
    assert configured["save_interval"] == 1
    assert configured["ex41_rehearsal"] is True

    output = tmp_path / "s2_lab" / "ex41_rehearsal_20261102_164500"
    output.parent.mkdir()
    assert validate_rehearsal_request(10, output, "cuda:0", True) == output
    with pytest.raises(ValueError, match="exactly 10"):
        validate_rehearsal_request(11, output, "cuda:0", True)
    with pytest.raises(ValueError, match="headless cuda:0"):
        validate_rehearsal_request(10, output, "cuda:1", True)
    output.mkdir()
    (output / "unexpected.txt").write_text("must reject", encoding="utf-8")
    with pytest.raises(ValueError, match="new or empty"):
        validate_rehearsal_request(10, output, "cuda:0", True)


def test_initial_dr_is_seeded_before_each_existing_reset_event():
    calls = []
    def event(env, env_ids=None):
        calls.append((env._ex40_dr_scale, env_ids))
    cfg = SimpleNamespace(events=SimpleNamespace(**{
        name: SimpleNamespace(func=event)
        for name in ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")
    }))
    receipt = install_initial_dr_scale(cfg, 0.5)
    env = SimpleNamespace(_ex40_dr_scale=0.)
    for name in receipt["reset_terms"]:
        getattr(cfg.events, name).func(env, env_ids=[0])
    assert receipt["before_first_reset"] is True
    assert len(calls) == 3 and all(scale == 0.5 for scale, _ in calls)
    assert env._ex41_initial_dr_scale_applied == 0.5


def test_existing_dr_runtime_readback_is_set_to_half_before_rollout():
    runtime, env = SimpleNamespace(scale=0.), SimpleNamespace(_ex40_dr_scale=0.)
    assert set_live_initial_dr_scale(runtime, env, 0.5) == {
        "runtime_scale": 0.5, "env_scale": 0.5}
