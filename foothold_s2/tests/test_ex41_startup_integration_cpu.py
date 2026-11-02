from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import gymnasium as gym
import pytest

from foothold_s2.curriculum.ex41_fixed import baseline_counts
from foothold_s2.scripts.ex41_startup import (
    configure_ex41_train_cfg,
    install_initial_dr_scale,
    load_fixed_plan,
    require_production_authorization,
    set_live_initial_dr_scale,
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
