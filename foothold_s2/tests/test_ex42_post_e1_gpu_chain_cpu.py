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
    assert ids[:9] == [
        "E1-P1-m250", "E1-P1-m500", "E1-P1-m750", "E1-P1-m1000",
        "E1-exit-gate", "E1-NONPASS-notify", "W09-W08-flag-chain",
        "E1F-evidence-materialize", "W08-materialize-and-repin",
    ]
    p1 = schedule[:4]
    assert all(row["gpus"] == [0, 1] and row["devices"] == ["cuda:1", "cuda:0"] for row in p1)
    assert all(row["execution"] == "serial_checkpoint_order_split_each_checkpoint_across_two_gpus"
               for row in p1)
    assert [row["requires"][-1] if index else None for index, row in enumerate(p1)] == [
        None, "E1-P1-m250=complete", "E1-P1-m500=complete", "E1-P1-m750=complete"]
    assert schedule[0]["checkpoint"].endswith("model_250.pt")
    assert schedule[3]["requires"] == ["manifest.checkpoints.model_1000.pt",
                                        "eval/scores/m1000/p1_score.json",
                                        "E1-P1-m750=complete"]
    gate = schedule[4]
    assert gate["requires"] == [f"E1-P1-m{i}=complete" for i in (250, 500, 750, 1000)]
    assert gate["decision_source"].endswith("m1000/p1_score.json")
    assert gate["validator"].endswith("ex42_flag_baseline_chain.check_e1_gate")
    assert gate["nonpass_policy"] == "notify_and_stop_without_stage_extension"
    hold = schedule[5]
    assert hold["requires_any"] == ["E1-exit-gate=HOLD", "E1-exit-gate=FAIL"]
    assert hold["skips"] == ["W09-W08-flag-chain", "W08-materialize-and-repin", "E1F-launch"]
    assert hold["extension_requires_lead_approval"] is True
    flags = schedule[6]
    assert flags["requires"] == ["E1-exit-gate=PASS"]
    assert flags["devices"] == ["cuda:0", "cuda:1"]
    assert flags["execution"] == "two_device_groups_concurrent_each_group_serial"
    assert flags["round_devices"] == ["cuda:0", "cuda:0", "cuda:0", "cuda:1", "cuda:1", "cuda:1"]
    assert flags["parallel_groups"] == [[0, 1, 2], [3, 4, 5]]
    assert flags["round_order"] == ["W09-seed42", "W08-repeat-1", "W08-repeat-2",
                                    "W08-repeat-3", "W08-repeat-4", "W08-repeat-5"]
    assert flags["argv"][flags["argv"].index("--devices") + 1] == "cuda:0,cuda:1"
    assert flags["argv"].count("--execute") == 1
    evidence = schedule[7]
    assert evidence["id"] == "E1F-evidence-materialize"
    assert evidence["requires"] == ["W09-W08-flag-chain=complete"]
    assert evidence["evidence_out"].endswith("eval/materialize/E1F-stage-evidence.json")
    assert evidence["argv"][evidence["argv"].index("--w09-baseline") + 1].endswith(
        "eval/w09-w08/w09_baseline.json")
    expected_p1_receipt = "/tmp/ex42-e1-run/eval/e1-p1-chain-${E1_SOURCE_HEAD_12}.json"
    assert evidence["completion_receipt"] == expected_p1_receipt
    assert evidence["argv"][evidence["argv"].index("--chain-receipt") + 1] == expected_p1_receipt
    assert evidence["completion_receipt"] != flags["completion_receipt"]
    assert "--materialize-only" in evidence["argv"]
    repin = schedule[8]
    assert repin["id"] == "W08-materialize-and-repin"
    assert repin["requires"] == ["E1F-evidence-materialize=complete"]
    assert "--materialize-only" in repin["argv"]
    assert repin["argv"][repin["argv"].index("--flag-chain") + 1].endswith("chain_receipt.json")
    assert "--expected-flag-chain-sha256" in repin["argv"]
    assert repin["captures"] == "launch_env"
    launch = schedule[9]
    assert launch["requires"] == ["W08-materialize-and-repin=complete"]
    assert launch["launcher"] == "foothold_s2.scripts.ex42_stage_launcher"
    assert launch["device"] == "cuda:0"
    assert launch["ranks"] == 2 and launch["launch_env_source"] == "W08-materialize-and-repin.launch_env"
    assert schedule[10]["requires"] == ["E1F-launch=complete"]
    assert schedule[10]["id"] == "KIT-E1F"
    assert ids.index("E1F-launch") < ids.index("W14-E2-repeat-width") < ids.index("KIT-E2")
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
    assert plan["queue_mutated"] is False and plan["kit_started"] is False
    assert plan["training_started"] is False
    assert "scripter_dual_device_cli_not_merged" not in plan["schedule"][6]["blockers"]
    assert "verifier_materialize_cli_not_merged" not in plan["schedule"][8]["blockers"]
    assert plan["schedule"][7]["blockers"] == ["completed_e1_p1_receipt_and_w09_baseline_required"]
    assert plan["schedule"][9]["blockers"] == ["materialized_launch_env_required_at_runtime"]
