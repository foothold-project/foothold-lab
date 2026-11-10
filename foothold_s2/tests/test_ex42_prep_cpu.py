from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest
import yaml

from foothold_s2.curriculum.ex42_prep import (
    EX42Plan,
    read_committed_boundary_pair,
    score_cell_roles,
    validate_boundary_transition,
    validate_stage_zero_authorization,
)
from foothold_s2.scripts.ex42_preflight import (
    build_parser,
    main,
    verify_env_registration,
    verify_import_boundary,
)
from foothold_s2.curriculum.continuous import load_plan


REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = REPO / "foothold_s2/curriculum/ex42-approvals.yaml"


def test_known_ex42_table_is_design_only_with_approved_assumptions():
    plan = EX42Plan.load(TABLE)
    assert plan.is_ex42 is True
    assert [stage["id"] for stage in plan.document["stages"]] == [
        "E0", "E1", "E1F", "E2", "E3", "E4", "E5", "M", "E6a", "E6b"
    ]
    assert plan.document["environment"]["num_envs"] == 6144
    assert plan.document["evaluation"]["judge_cells"] == 26
    assert plan.document["evaluation"]["record_only_cells"] == 13
    assert plan.document["environment"]["evaluation"]["scale_multiplier"] == {
        "gap": 1.15, "support_surface": 0.85,
    }
    blockers = plan.launch_blockers(APPROVALS, None, None)
    assert "explicit_lead_approval_missing" in blockers
    assert "e0_parent_manifest_missing" in blockers
    assert "terrain_manifest_missing" in blockers
    assert "design_assumptions_pending" not in blockers


def test_w65_stage_zero_scope_is_pinned_without_opening_the_full_plan():
    plan = EX42Plan.load(TABLE)
    receipt = validate_stage_zero_authorization(plan, APPROVALS)
    assert receipt["state"] == "stage_zero_only_authorized"
    assert receipt["scope"]["stage_id"] == "EX42_0_T0_prime"
    assert receipt["scope"]["maximum_updates"] == 1000
    assert receipt["scope"]["later_stages_authorized"] is False
    assert receipt["production_launch_allowed"] is False
    assert plan.launch_blockers(APPROVALS, None, None)


def test_w65_stage_zero_scope_rejects_stale_pin_and_any_later_stage(tmp_path):
    plan = EX42Plan.load(TABLE)
    altered = tmp_path / "approvals.yaml"
    altered.write_bytes(APPROVALS.read_bytes().replace(
        b"later_stages_authorized: false", b"later_stages_authorized: true"))
    with pytest.raises(ValueError, match="approval SHA256"):
        validate_stage_zero_authorization(plan, altered)

    import hashlib
    updated_doc = dict(plan.document)
    updated_zero = dict(updated_doc["stage_zero"])
    updated_zero["approval_sha256"] = hashlib.sha256(altered.read_bytes()).hexdigest()
    updated_doc["stage_zero"] = updated_zero
    from dataclasses import replace
    plan_with_mutation_pin = replace(plan, document=updated_doc)
    with pytest.raises(ValueError, match="scope differs"):
        validate_stage_zero_authorization(plan_with_mutation_pin, altered)


def test_continuous_factory_dispatches_ex42_and_training_runtime_fails_closed():
    plan = load_plan(TABLE)
    assert plan.is_ex42
    from foothold_s2.curriculum.continuous import make_runtime
    with pytest.raises(ValueError, match="preparation-only"):
        make_runtime(plan, 6144, "cuda:0", REPO / "outputs")


def test_terrain_manifest_measured_contract_and_larger_evaluation_requirement():
    plan = EX42Plan.load(TABLE)
    kinds = []
    for family, count in plan.document["terrain_manifest_contract"]["kind_count_by_family"].items():
        for i in range(count):
            kinds.append({"family": family, "kind": f"known_{i}", "preset_id": "known",
                          "original_dimensions_m": {"x": 1.0, "y": 1.0, "z": 0.2},
                          "training_dimensions_m": {"x": 1.0, "y": 1.0, "z": 0.2},
                          "evaluation_dimensions_m": {"x": 1.1, "y": 1.0, "z": 0.2},
                          "evaluation_axis_directions": {"x": "higher", "y": "same", "z": "same"},
                          "geometry_sha256": "a" * 64,
                          "paper_reference": "CPU fixture only",
                          "physical_flag": False})
    manifest = {"format": "foothold-ex42-terrain-manifest/1", "status": "measured",
                "training_presets": plan.document["environment"]["training_presets"],
                "measurements": {"peak_memory_gib": 3.0, "generation_seconds": 8.0,
                                 "ray_count_per_second": 1000}, "kinds": kinds}
    plan.validate_terrain_manifest(manifest)
    kinds[0]["evaluation_dimensions_m"] = dict(kinds[0]["training_dimensions_m"])
    with pytest.raises(ValueError, match="does not match direction"):
        plan.validate_terrain_manifest(manifest)

    kinds[0]["evaluation_dimensions_m"] = {"x": 1.0, "y": 0.85, "z": 0.2}
    kinds[0]["evaluation_axis_directions"] = {"x": "same", "y": "lower", "z": "same"}
    plan.validate_terrain_manifest(manifest)


def test_actual_cli_parser_and_dry_run_report_hold(capsys):
    args = build_parser().parse_args(["--table", str(TABLE), "--approvals", str(APPROVALS), "--dry-run"])
    assert args.dry_run is True
    assert args.production_launch_approved is False
    assert main(["--table", str(TABLE), "--approvals", str(APPROVALS), "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "blocked"
    assert "explicit_lead_approval_missing" in result["blockers"]


def test_actual_gym_task_registration_and_config_class_ast():
    result = verify_env_registration("FootholdS2-Go2-S2-SB-v0")
    assert result["task_id"] == "FootholdS2-Go2-S2-SB-v0"
    assert result["env_cfg_class"] == "FootholdS2SBEnvCfg"
    assert "not attempted" in result["env_cfg_import"]


def test_startup_ast_does_not_import_or_initialize_kit():
    assert verify_import_boundary() == {"ast_files": 2, "kit_imports_at_module_scope": 0}


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_w72_boundary_reads_only_same_clean_committed_pair_and_approved_single_axis(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "cpu-test@example.invalid")
    _git(root, "config", "user.name", "EX42 CPU test")
    boundary_path = root / "boundary.yaml"
    approval_path = root / "approvals.yaml"
    old = {"format": "foothold-ex42-boundary/1", "revision": 1,
           "axis_id": "terrain_exposure", "allowed_diff_paths": ["terrain.exposure.A.test.share"],
           "values": {"terrain.exposure.A.test.share": 0.0}}
    approvals = {"format": "foothold-ex42-approvals/1", "status": "approved",
                 "production_launch_allowed": False, "automatic_launch_allowed": False,
                 "fields": {"terrain.exposure.A.test.share": {"decision_id": "D-test", "bounds": [0.0, 0.05]}}}
    boundary_path.write_text(yaml.safe_dump(old, sort_keys=False), encoding="utf-8")
    approval_path.write_text(yaml.safe_dump(approvals, sort_keys=False), encoding="utf-8")
    _git(root, "add", "boundary.yaml", "approvals.yaml")
    _git(root, "commit", "-qm", "initial")
    first = read_committed_boundary_pair(boundary_path, approval_path)

    new = dict(old)
    new["revision"] = 2
    new["values"] = {"terrain.exposure.A.test.share": 0.05}
    boundary_path.write_text(yaml.safe_dump(new, sort_keys=False), encoding="utf-8")
    _git(root, "add", "boundary.yaml")
    _git(root, "commit", "-qm", "approved boundary change")
    second = read_committed_boundary_pair(boundary_path, approval_path)
    changes = validate_boundary_transition(
        first["boundary"], second["boundary"], second["approvals"],
        registered_axes={"terrain_exposure": {"terrain.exposure.A.test.share"}})
    assert changes == [{"path": "terrain.exposure.A.test.share", "before": 0.0,
                        "after": 0.05, "decision_id": "D-test", "axis_id": "terrain_exposure"}]

    new["revision"] = 3
    new["values"]["unapproved.value"] = 1
    boundary_path.write_text(yaml.safe_dump(new, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="dirty or untracked"):
        read_committed_boundary_pair(boundary_path, approval_path)


def test_score_contract_preserves_26_judge_and_13_record_only_values():
    judge = {f"j{i:02d}": float(i) for i in range(26)}
    record = {f"r{i:02d}": float(i) for i in range(13)}
    result = score_cell_roles(judge, record)
    assert (result["judge_count"], result["record_only_count"], result["total_cells"]) == (26, 13, 39)
    assert result["judge_cells"] == judge and result["record_only_cells"] == record
    with pytest.raises(ValueError, match="exactly 26 judge"):
        score_cell_roles({}, record)


def test_ex42_missing_or_late_boundary_score_uses_planned_dr_and_records_gap():
    from foothold_s2.curriculum.ex42_runtime import resolve_missing_score_dr_boundary

    missing = resolve_missing_score_dr_boundary(
        planned_scale=0.65, boundary_iteration=1001,
        expected_score_iteration=1000, observed_score_iteration=None,
    )
    assert missing["status"] == "measurement_gap"
    assert missing["reason"] == "score_missing"
    assert missing["dr_action"] == "follow_schedule_record_gap"
    assert missing["applied_scale"] == missing["planned_scale"] == 0.65
    assert missing["learning_continues"] is True

    late = resolve_missing_score_dr_boundary(
        planned_scale=0.8, boundary_iteration=1501,
        expected_score_iteration=1500, observed_score_iteration=1250,
    )
    assert late["status"] == "measurement_gap"
    assert late["reason"] == "score_late_or_wrong_iteration"
    assert late["applied_scale"] == late["planned_scale"] == 0.8
    assert late["maintenance_action"] == "not_decided_here"


def test_parent_checkpoint_is_resolved_by_manifest_sha_not_nominal_filename(tmp_path):
    import hashlib
    import json

    from foothold_s2.curriculum.ex42_prep import EX42Plan

    root = Path(__file__).parents[1]
    plan = EX42Plan.load(root / "curriculum/ex42-prep.yaml")
    payload = b"fixed parent checkpoint bytes"
    digest = hashlib.sha256(payload).hexdigest()
    checkpoint = tmp_path / "model_6000.pt"
    checkpoint.write_bytes(payload)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "progress": {"completed_updates": 6000},
        "checkpoints": {"model_6000.pt": digest},
    }), encoding="utf-8")

    # The production plan is pinned to the reviewed live-run SHA, while this
    # compact fixture proves lookup follows the manifest key rather than a
    # fabricated model_12000.pt filename.
    plan.document["stage_zero"]["parent"]["sha256"] = digest
    parent = plan.verify_parent_manifest(manifest)
    assert parent["manifest_checkpoint_key"] == "model_6000.pt"
    assert parent["checkpoint_path"] == str(checkpoint.resolve())
    assert parent["cumulative_update"] == 12000
    assert parent["checkpoint_sha256"] == digest

    manifest.write_text(json.dumps({
        "progress": {"completed_updates": 6000},
        "checkpoints": {"model_6000.pt": "0" * 64},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one checkpoint"):
        plan.verify_parent_manifest(manifest)
