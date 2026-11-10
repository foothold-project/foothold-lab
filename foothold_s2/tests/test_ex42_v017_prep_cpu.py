"""Known-input checks for the EX-42 v0.17 preparation declarations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from foothold_s2.curriculum.ex42_prep import EX42Plan, validate_command_shares
from foothold_s2.terrains.ex42_column_reset import build_column_table, push_gate_mask
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


def test_merged_runtime_does_not_authorize_full_plan_launch():
    plan = EX42Plan.load(PLAN)
    blockers = plan.launch_blockers(APPROVALS, None, None)
    assert "runtime_integration_pending" not in blockers
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


def test_ex42_plan_push_declarations_feed_the_single_column_gate():
    tasks = EX42Plan.load(PLAN).document["stages"][0]["terrain"]["kind_task"]
    families = ["A"] * 50 + ["B"] * 12 + ["C"] * 7 + ["D"] * 3 + ["E"] * 4
    table = build_column_table(families)
    off = {family: {name for name, entry in kinds.items() if entry["push"] is False}
           for family, kinds in tasks.items() if family in set(families)}
    mask = push_gate_mask(table, off)
    assert mask[table.index(next(row for row in table if row["family"] == "A" and row["kind"] == "flat"))] is False
    assert mask[59] is True  # B/beam is narrow; #600 gate owns the event wrapper.
    assert len(mask) == len(families)
