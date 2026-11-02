from __future__ import annotations

import copy
import hashlib
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import gymnasium as gym
import pytest

from foothold_s2.curriculum.ex41_fixed import CELLS, CASES, baseline_counts, maintenance
from foothold_s2.scripts.ex41_startup import (
    add_maintenance_counts,
    configure_ex41_train_cfg,
    install_initial_dr_scale,
    load_fixed_plan,
    maintenance_counts_from_map_modes,
    require_production_authorization,
    set_live_initial_dr_scale,
)


REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "foothold_s2/curriculum/ex41-fixed5000.yaml"


def test_ex41_task_registration_and_config_entrypoint_source():
    import foothold_s2.sb_tasks  # noqa: F401

    spec = gym.spec("FootholdS2-Go2-S2-SB-v0")
    module_name, class_name = spec.kwargs["env_cfg_entry_point"].split(":", 1)
    config_path = REPO.joinpath(*module_name.split(".")).with_suffix(".py")
    tree = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
    assert class_name == "FootholdS2SBEnvCfg"
    assert any(isinstance(node, ast.ClassDef) and node.name == class_name for node in tree.body)
    source = (REPO / "foothold_s2/scripts/train_start.py").read_text(encoding="utf-8")
    assert source.index("import foothold_s2.sb_tasks") < source.index("@hydra_task_config")


def _map_modes(iteration: int, checkpoint_sha: str, alive: int = 64):
    return {
        "format": "foothold-map-modes/1",
        "checkpoint_iter": iteration,
        "checkpoint_sha256": checkpoint_sha,
        "envs": 64,
        "modes": {
            mode: {
                case: {"env_count": 64, "per_env": [{"alive_at_end": i < alive} for i in range(64)],
                       "alive_envs_at_end": alive}
                for case in CASES
            }
            for mode in ("eval_gt", "probe_prop_only", "eval_pred")
        },
    }


def test_real_fixed_plan_has_pinned_m6000_dr_half_and_39_baseline_cells():
    plan = load_fixed_plan(TABLE)
    baseline = baseline_counts(plan)
    assert plan.parent_update == 6000
    assert plan.initial_dr_scale == 0.5
    assert len(baseline) == len(CELLS) == 39
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


def test_numeric_39_cell_score_counts_and_exact_mode_case_mapping():
    plan = load_fixed_plan(TABLE)
    baseline = baseline_counts(plan)
    counts = maintenance_counts_from_map_modes(_map_modes(250, "a" * 64, 61), baseline)
    assert set(counts) == set(CELLS)
    assert len(counts) == 39
    assert all(type(row["passed"]) is int and type(row["baseline_passed"]) is int
               and row["total"] == 64 for row in counts.values())
    assert maintenance(counts, baseline) == []


def test_missing_cell_or_non64_env_evidence_is_rejected():
    plan = load_fixed_plan(TABLE)
    baseline = baseline_counts(plan)
    doc = _map_modes(250, "b" * 64)
    del doc["modes"]["probe_prop_only"][CASES[0]]
    with pytest.raises(ValueError, match="cases incomplete"):
        maintenance_counts_from_map_modes(doc, baseline)
    doc = _map_modes(250, "b" * 64)
    doc["modes"]["eval_gt"][CASES[0]]["env_count"] = 63
    with pytest.raises(ValueError, match="invalid 64-env count"):
        maintenance_counts_from_map_modes(doc, baseline)


def test_score_enrichment_requires_same_checkpoint_and_preserves_other_verdicts(tmp_path):
    plan = load_fixed_plan(TABLE)
    baseline = baseline_counts(plan)
    cp = tmp_path / "model_250.pt"
    cp.write_bytes(b"known checkpoint")
    checkpoint_sha = hashlib.sha256(cp.read_bytes()).hexdigest()
    modes_path = tmp_path / "map_modes.json"
    modes_path.write_text(json.dumps(_map_modes(250, checkpoint_sha)), encoding="utf-8")
    score = {"format": "foothold-ex41-score/1", "iteration": 250,
             "checkpoint_path": str(cp), "checkpoint_sha256": checkpoint_sha,
             "maintenance_pass": False, "stage_pass": True, "safety_stop": False,
             "metrics": {"sentinel": 17}, "evidence": [],
             "created_at": "2026-11-02T00:00:00+00:00",
             "stage_id": "S2a", "schedule_sha256": plan.effective_sha256,
             "parent_sha256": plan.parent_sha256,
             "baseline_checkpoint_sha256": plan.parent_sha256}
    result = add_maintenance_counts(score, _map_modes(250, checkpoint_sha), baseline, modes_path)
    assert len(result["metrics"]["maintenance_counts"]) == 39
    assert result["maintenance_pass"] is True
    assert result["stage_pass"] is True and result["metrics"]["sentinel"] == 17
    assert result["evidence"] == [{"path": str(modes_path.resolve()),
                                    "sha256": hashlib.sha256(modes_path.read_bytes()).hexdigest()}]
    broken = copy.deepcopy(score)
    with pytest.raises(ValueError, match="does not match"):
        add_maintenance_counts(broken, _map_modes(250, "0" * 64), baseline, modes_path)
