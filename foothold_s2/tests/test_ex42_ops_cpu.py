from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from foothold_s2.scripts.ex42_ops import (
    inspect_fixed_source,
    main,
    ops_check,
    verify_env_cfg_import,
    verify_train_entry_contract,
    validate_rehearsal_plan,
)
from foothold_s2.machine_profile import load_machine_profile

REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = REPO / "foothold_s2/curriculum/ex42-approvals.yaml"


def test_ops_check_reports_all_known_blockers_and_never_allows_launch(capsys):
    result = ops_check(TABLE, APPROVALS)
    assert result["state"] == "blocked"
    assert result["production_launch_allowed"] is False
    assert "runtime_integration_pending" in result["blockers"]
    assert "explicit_lead_approval_missing" in result["blockers"]
    assert "terrain_manifest_missing" in result["blockers"]
    assert "environment_import_unavailable" in result["blockers"]
    assert len(result["blockers"]) == 6
    assert result["train_entry"]["training_started"] is False
    assert main(["--ops-check", "--exp", "EX-42", "--table", str(TABLE), "--approvals", str(APPROVALS)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["production_launch_allowed"] is False


def test_production_mode_is_rejected_even_if_a_flag_is_given(capsys):
    assert main(["--production", "--exp", "EX-42", "--production-launch-approved", "--table", str(TABLE),
                 "--approvals", str(APPROVALS)]) == 2
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


def test_rehearsal_plan_requires_new_d_output_ten_stages_and_fixed_source(tmp_path):
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
    good = validate_rehearsal_plan("D:/mai-tmp/runner/ex42_rehearsal_20261105_235959",
                                   [1] * 11, **kwargs)
    assert good["stage_updates"] == [1] * 11
    assert good["stage_ids"][0] == "EX42_0_T0_prime"
    assert good["training_started"] is False and good["kit_started"] is False
    with pytest.raises(ValueError, match="D:/mai-tmp/runner"):
        validate_rehearsal_plan("C:/temp/ex42_rehearsal_20261105_235959", [1] * 11, **kwargs)
    with pytest.raises(ValueError, match="eleven runtime stages"):
        validate_rehearsal_plan("D:/mai-tmp/runner/ex42_rehearsal_20261105_235959",
                                [1] * 10, **kwargs)


def test_start_wrapper_exposes_only_gated_modes_and_does_not_call_training():
    script = (REPO / "foothold_s2/run_ex42.ps1").read_text(encoding="utf-8")
    assert "ops-check" in script and "rehearsal" in script and "production" in script
    assert "foothold_s2.scripts.ex42_ops" in script
    assert "train_start.py" not in script
    assert "RehearsalStageUpdates" in script


def test_real_train_parser_and_environment_import_attempt_are_reported_without_kit():
    parser = verify_train_entry_contract()
    assert parser["parser"].startswith("train_start declarations")
    machine = load_machine_profile()
    assert parser["machine_profile"] == machine["machine_id"]
    assert parser["machine_profile_path"] == machine["profile"]
    assert parser["applauncher_passthrough"] == ["--headless", "--device", "cuda:0"]
    env = verify_env_cfg_import()
    assert env["kit_started"] is False
    assert env["imported"] is False
    assert env["error_type"] == "ModuleNotFoundError"
