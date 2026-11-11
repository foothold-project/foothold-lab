from __future__ import annotations

from pathlib import Path

from foothold_s2.scripts.ex42_post_e1_gpu_chain import build_chain


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"


def test_post_e1_sequence_order_and_gpu_distribution_are_explicit() -> None:
    plan = build_chain(plan_path=PLAN, approvals_path=APPROVALS,
                       e1_run="/tmp/ex42-e1-run")
    schedule = plan["schedule"]
    ids = [row["id"] for row in schedule]
    assert ids[:10] == [
        "E1-P1-m250", "E1-P1-m500", "E1-P1-m750", "E1-P1-m1000",
        "W09-flag-baseline", "W08-flag-calibration-1", "W08-flag-calibration-2",
        "W08-flag-calibration-3", "W08-flag-calibration-4", "W08-flag-calibration-5",
    ]
    assert [row["gpu"] for row in schedule[:4]] == [0, 1, 0, 1]
    assert [row["wave"] for row in schedule[:4]] == [0, 0, 1, 1]
    assert schedule[0]["checkpoint"].endswith("model_250.pt")
    assert schedule[3]["requires"] == ["manifest.checkpoints.model_1000.pt",
                                        "eval/scores/m1000/p1_score.json",
                                        "eval/scores/m250/p1_score.json",
                                        "eval/scores/m500/p1_score.json"]
    for repeat in range(1, 6):
        row = schedule[4 + repeat]
        expected = "W09-flag-baseline" if repeat == 1 else f"W08-flag-calibration-{repeat - 1}"
        assert row["id"] == f"W08-flag-calibration-{repeat}"
        assert row["requires"] == [f"{expected}=complete"]
    repin = schedule[10]
    assert repin["id"] == "W08-materialize-and-repin"
    assert repin["requires"] == ["W08-flag-calibration-5=complete"]
    assert repin["calibration_out"] is None and repin["repinned_plan_out"] is None
    assert "materialize_only_and_plan_repin_command_missing" in repin["blockers"]
    assert "W08-materialize-and-repin=complete" in schedule[11]["requires"]
    assert schedule[11]["id"] == "KIT-E1F"
    assert ids.index("KIT-E1F") < ids.index("W14-E2-repeat-width") < ids.index("KIT-E2")
    assert ids.index("KIT-E2") < ids.index("W19-E3-kind-repeat-width") < ids.index("KIT-E3")
    assert "KIT-E1F=complete" in schedule[ids.index("KIT-E2")]["requires"]
    assert "KIT-E3=complete" in schedule[ids.index("KIT-E4")]["requires"]


def test_unresolved_commands_keep_entire_chain_out_of_live_queue() -> None:
    plan = build_chain(plan_path=PLAN, approvals_path=APPROVALS)
    assert plan["state"] == "blocked"
    assert plan["queue_mutated"] is False
    assert plan["kit_started"] is False and plan["training_started"] is False
    assert plan["gpu_idle_guarantee"] is False
    assert all(row["queue_command"] is None for row in plan["schedule"])
    assert "W09_flag_cell_evaluator_command_missing" in plan["schedule"][4]["blockers"]
    assert "five-run_calibration_receipt_contract_missing" in plan["schedule"][5]["blockers"]
    assert "materialize_only_and_plan_repin_command_missing" in plan["schedule"][10]["blockers"]
