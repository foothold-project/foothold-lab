from __future__ import annotations

import json
import subprocess
import builtins
from pathlib import Path

import pytest

from foothold_s2.scripts.ex42_ops import (
    inspect_fixed_source,
    main,
    ops_check,
    validate_rehearsal_plan,
)

REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = REPO / "foothold_s2/curriculum/ex42-approvals.yaml"
GATE_FIXTURE = Path(__file__).with_name("fixtures") / "ex42-gate-g11-open.md"


def test_ops_check_reports_all_known_blockers_and_never_allows_launch(capsys):
    result = ops_check(TABLE, APPROVALS, gate_report=GATE_FIXTURE)
    assert result["state"] == "blocked"
    assert result["production_launch_allowed"] is False
    assert "runtime_integration_pending" in result["blockers"]
    assert "explicit_lead_approval_missing" in result["blockers"]
    assert "terrain_manifest_missing" in result["blockers"]
    assert "environment_import_unavailable" in result["blockers"]
    assert "gate_open:G11" in result["blockers"]
    assert result["train_entry"]["training_started"] is False
    assert main(["--ops-check", "--exp", "EX-42", "--table", str(TABLE), "--approvals", str(APPROVALS),
                 "--gate-report", str(GATE_FIXTURE)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["production_launch_allowed"] is False
    if payload["train_entry"].get("final_argv_sha256"):
        assert len(payload["train_entry"]["final_argv_sha256"]) == 64
    else:
        assert payload["train_entry"]["verified"] is False
        assert "train_entry_contract_unavailable" in payload["blockers"]


def test_ops_check_surfaces_analyst_g11_counterexample(capsys):
    fixture = Path(__file__).with_name("fixtures") / "ex42-gate-g11-open.md"
    result = ops_check(TABLE, APPROVALS, gate_report=fixture)
    assert result["state"] == "blocked"
    assert "gate_open:G11" in result["blockers"]
    assert result["production_launch_allowed"] is False


def test_ops_check_collects_environment_blockers_when_train_import_is_missing(monkeypatch, capsys):
    from foothold_s2.scripts import ex42_ops

    called = {"env": False}

    def missing_train_entry():
        raise ModuleNotFoundError("rsl_rl is unavailable")

    def missing_environment(task_id):
        called["env"] = True
        return {"task_id": task_id, "imported": False, "error_type": "ModuleNotFoundError",
                "error": "gymnasium is unavailable", "kit_started": False}

    monkeypatch.setattr(ex42_ops, "verify_train_entry_contract", missing_train_entry)
    monkeypatch.setattr(ex42_ops, "verify_env_cfg_import", missing_environment)
    assert ex42_ops.main(["--ops-check", "--exp", "EX-42", "--table", str(TABLE),
        "--approvals", str(APPROVALS), "--gate-report", str(GATE_FIXTURE)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert called["env"] is True
    assert payload["state"] == "blocked"
    assert payload["production_launch_allowed"] is False
    assert "runtime_integration_pending" in payload["blockers"]
    assert "environment_import_unavailable" in payload["blockers"]
    assert "train_entry_contract_unavailable" in payload["blockers"]
    assert payload["train_entry"]["verified"] is False
    assert "final_argv_sha256" not in payload["train_entry"]


def test_production_mode_is_rejected_even_if_a_flag_is_given(capsys):
    assert main(["--production", "--exp", "EX-42", "--production-launch-approved", "--table", str(TABLE),
                 "--approvals", str(APPROVALS), "--gate-report", str(GATE_FIXTURE)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "blocked"
    assert "runtime_integration_pending" in result["blockers"]
    assert "fixed_source_identity_required" in result["blockers"]


def test_fixed_source_requires_detached_clean_matching_head(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    (repo / "source.txt").write_text("known", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "source.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-m", "fixture"], check=True, capture_output=True)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, text=True,
                          capture_output=True).stdout.strip()
    subprocess.run(["git", "-C", str(repo), "checkout", "--detach", head], check=True,
                   capture_output=True)
    assert inspect_fixed_source(repo, expected_head=head)["clean"] is True
    with pytest.raises(ValueError, match="HEAD differs"):
        inspect_fixed_source(repo, expected_head="0" * 40)
    (repo / "source.txt").write_text("dirty", encoding="utf-8")
    with pytest.raises(ValueError, match="not clean"):
        inspect_fixed_source(repo)


def test_rehearsal_plan_uses_machine_tmp_root_and_requires_new_output(tmp_path, monkeypatch):
    from foothold_s2.scripts import ex42_ops
    from foothold_s2.machine_profile import machine_path as resolve_machine_path
    import yaml

    configured_tmp_root = tmp_path / "machine-local-tmp"
    profile = tmp_path / "machine-profile.yaml"
    profile.write_text(yaml.safe_dump({
        "format": "foothold-machine-profile/1", "machine_id": "test-machine",
        "paths": {
            "isaaclab_root": str(tmp_path / "isaaclab"),
            "isaac_sim_root": str(tmp_path / "isaacsim"),
            "conda_python": str(tmp_path / "python"),
            "rsl_rl_module": str(tmp_path / "rsl_rl" / "__init__.py"),
            "s2_lab_root": str(tmp_path / "s2_lab"),
            "mai_tmp_root": str(configured_tmp_root),
            "mai_worktree_root": str(tmp_path / "worktrees"),
        },
        "devices": {
            "training": {"cuda_index": 0, "uuid": "GPU-test-0"},
            "p1_evaluation": {"cuda_index": 0, "uuid": "GPU-test-0"},
            "screen": {"cuda_index": 1, "uuid": "GPU-test-1"},
        },
    }), encoding="utf-8")
    monkeypatch.setattr(ex42_ops, "machine_path",
                        lambda key: resolve_machine_path(key, profile=profile))
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    (repo / "source.txt").write_text("known", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "source.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-m", "fixture"], check=True, capture_output=True)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, text=True,
                          capture_output=True).stdout.strip()
    subprocess.run(["git", "-C", str(repo), "checkout", "--detach", head], check=True,
                   capture_output=True)
    kwargs = {"source_root": repo, "expected_head": head}
    output_root = configured_tmp_root / "runner" / "ex42_rehearsal_20261105_235959"
    good = validate_rehearsal_plan(str(output_root), [1] * 11, **kwargs)
    assert good["stage_updates"] == [1] * 11
    assert good["stage_ids"][0] == "EX42_0_T0_prime"
    assert good["training_started"] is False and good["kit_started"] is False
    with pytest.raises(ValueError, match="machine-local-tmp"):
        validate_rehearsal_plan(str(tmp_path / "wrong" / "ex42_rehearsal_20261105_235959"),
                                [1] * 11, **kwargs)
    with pytest.raises(ValueError, match="eleven runtime stages"):
        validate_rehearsal_plan(str(output_root), [1] * 10, **kwargs)


def test_start_wrapper_exposes_only_gated_modes_and_does_not_call_training():
    script = (REPO / "foothold_s2/run_ex42.ps1").read_text(encoding="utf-8")
    assert "ops-check" in script and "rehearsal" in script and "production" in script
    assert "foothold_s2.scripts.ex42_ops" in script
    assert "train_start.py" not in script
    assert "RehearsalStageUpdates" in script


def test_missing_gymnasium_still_emits_blocker_json_and_rc2(monkeypatch, capsys):
    original_import = builtins.__import__
    def import_without_gym(name, *args, **kwargs):
        if name == "gymnasium":
            raise ImportError("simulated missing gymnasium")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", import_without_gym)
    assert main(["--ops-check", "--exp", "EX-42", "--table", str(TABLE),
                 "--approvals", str(APPROVALS), "--gate-report", str(GATE_FIXTURE)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "blocked"
    assert result["kit_started"] is False and result["training_started"] is False
    assert "environment_import_unavailable" in result["blockers"]
