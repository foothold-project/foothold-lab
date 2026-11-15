from __future__ import annotations

import json
from pathlib import Path

import pytest

from foothold_s2.scripts.ex42_kit_sequence_rehearsal import (
    SEQUENCE, build_report, main,
)


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"


def test_sequence_preflight_lists_all_later_stages_and_refuses_kit() -> None:
    report = build_report(plan_path=PLAN, approvals_path=APPROVALS)
    assert report["stage_order"] == ["E1F", "E2", "E3", "E4", "E5", "M", "E6a", "E6b"]
    assert tuple(row["stage_id"] for row in report["stages"]) == SEQUENCE
    assert report["updates_per_stage"] == 3
    assert report["devices"] == ["cuda:0", "cuda:1"]
    assert report["state"] == "blocked"
    assert report["kit_started"] is False and report["training_started"] is False
    assert "bounded_2_3_update_cli_missing" in report["stages"][0]["blockers"]
    assert "parent_checkpoint_not_pinned" in report["stages"][0]["blockers"]
    assert "stage_training_entry_not_startable" in report["stages"][0]["blockers"]


@pytest.mark.parametrize("updates", [0, 1, 4, 20])
def test_rehearsal_update_bound_is_strict(updates: int) -> None:
    with pytest.raises(ValueError, match="2 or 3 updates"):
        build_report(plan_path=PLAN, approvals_path=APPROVALS, updates_per_stage=updates)


def test_execute_fails_closed_without_starting_kit(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--plan", str(PLAN), "--approvals", str(APPROVALS), "--execute"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["state"] == "blocked"
    assert report["kit_started"] is False
    assert report["training_started"] is False
    assert report["reason"] == "execution is disabled: no approved bounded EX-42 rehearsal path"
