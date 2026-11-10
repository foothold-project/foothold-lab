"""Known-input checks for the EX-42 v0.17 preparation declarations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from foothold_s2.curriculum.ex42_prep import EX42Plan, validate_command_shares
from foothold_s2.curriculum.ex40_dr_runtime import _ex42_push_rows
from foothold_s2.experiment_registry import load_experiment
from foothold_s2.scripts.ex42_ops import verify_train_entry_contract


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"


def test_full_plan_6144_and_stage_zero_3072_are_distinct():
    plan = EX42Plan.load(PLAN)
    exp = load_experiment("EX-42")
    assert plan.document["environment"]["num_envs"] == 6144
    assert plan.document["command_allocation"]["total_denominator"] == 6144
    assert exp["operational_values"]["training"]["environments"] == 6144
    assert exp["operational_values"]["training"]["per_gpu_envs"] == 3072
    assert verify_train_entry_contract()["full_plan_num_envs"] == 6144
    assert plan.document["stage_zero"]["maximum_updates"] == 1000
    assert plan.document["stage_zero"]["parent"]["manifest_local_update"] == 6000
    validate_command_shares(0.4, {"forward": 0.58, "reverse": 0.14,
                                  "side_left": 0.14, "side_right": 0.14})
    with pytest.raises(ValueError, match="6144"):
        validate_command_shares(0.4, {"forward": 0.58, "reverse": 0.14,
                                      "side_left": 0.14, "side_right": 0.14}, total_envs=3072)


def test_e0_parent_manifest_key_and_bytes_must_match(tmp_path):
    plan = EX42Plan.load(PLAN)
    document = deepcopy(plan.document)
    parent = document["stages"][0]["parent"]
    checkpoint = tmp_path / "model_1000.pt"
    checkpoint.write_bytes(b"known E0 parent")
    parent["sha256"] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    plan = replace(plan, document=document)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"progress": {"completed_updates": 1000},
                                    "checkpoints": {checkpoint.name: parent["sha256"]}}))
    assert plan.verify_parent_manifest(manifest, stage_id="E0")["cumulative_update"] == 13000
    manifest.write_text(json.dumps({"progress": {"completed_updates": 999},
                                    "checkpoints": {checkpoint.name: parent["sha256"]}}))
    with pytest.raises(ValueError, match="completed"):
        plan.verify_parent_manifest(manifest, stage_id="E0")
    manifest.write_text(json.dumps({"progress": {"completed_updates": 1000},
                                    "checkpoints": {"wrong_name.pt": parent["sha256"]}}))
    with pytest.raises(ValueError, match="key"):
        plan.verify_parent_manifest(manifest, stage_id="E0")


def test_runtime_integration_approval_is_not_a_merge_or_launch_approval():
    plan = EX42Plan.load(PLAN)
    blockers = plan.launch_blockers(APPROVALS, None, None)
    assert "runtime_integration_pending" in blockers
    assert "explicit_lead_approval_missing" in blockers
    assert "e0_parent_manifest_missing" in blockers
    assert "design_assumptions_pending" not in blockers
    assert all(row["approved"] is True for row in plan.document["assumptions_pending_lead"].values())


def test_push_mask_and_measurement_declarations_are_exact():
    doc = EX42Plan.load(PLAN).document
    tasks = doc["stages"][0]["terrain"]["kind_task"]
    assert tasks["A"]["gaps"]["push"] is False
    assert tasks["A"]["flat"]["push"] is True
    assert tasks["B"]["beam"]["push"] is False
    assert tasks["B"]["rough"]["push"] is True
    assert doc["evaluation"]["push_cells"] == {
        "role": "record", "mask": "same_as_training", "off_kinds_value": "n/a"}
    assert doc["environment"]["preparation_measurements"]["values"]["kind"] == "proxy_downward_grid_rays"
    assert doc["environment"]["terrain_presets"]["B"]["rough"] == {
        "undulation_slope_deg": 20, "roughness_m": 0.16}
    assert "beam_width_m" not in doc["evaluation"]["paper_cells"]["physical_flag_record_only"]
    assert "stairs_m" not in doc["evaluation"]["paper_cells"]["physical_flag_record_only"]


def test_ex42_push_excludes_narrow_support_before_physics_and_ex40_is_unchanged():
    tasks = EX42Plan.load(PLAN).document["stages"][0]["terrain"]["kind_task"]
    gen = SimpleNamespace(num_cols=2, sub_terrains={
        "flat": SimpleNamespace(proportion=0.5),
        "gaps": SimpleNamespace(proportion=0.5)})
    terrain = SimpleNamespace(cfg=SimpleNamespace(terrain_generator=gen),
                              terrain_types=torch.tensor([0, 1, 0, 1]))
    env = SimpleNamespace(scene=SimpleNamespace(terrain=terrain),
                          _ex42_stage_id="E0", _ex42_push_kind_task=tasks)
    rows = torch.arange(4)
    assert _ex42_push_rows(env, rows).tolist() == [0, 2]
    assert env._ex40_dr_samples["push_kind_excluded_count"]["sum"] == 2
    assert _ex42_push_rows(SimpleNamespace(scene=env.scene, _ex42_stage_id=None), rows).tolist() == rows.tolist()
    del env._ex42_push_kind_task
    with pytest.raises(ValueError, match="registered kind table"):
        _ex42_push_rows(env, rows)
