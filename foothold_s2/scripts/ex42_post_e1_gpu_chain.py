"""Build a fail-closed ordered GPU plan for post-E1 checklist work.

This command is intentionally plan-only. It does not mutate the live dispatcher
queue or start Kit. Missing consumers and unpinned parents are explicit blockers;
free-text queue conditions are not treated as dependency gates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts.ex42_kit_sequence_rehearsal import SEQUENCE, build_report


BOUNDARIES = (250, 500, 750, 1000)
STAGE_PREREQUISITES = {"E2": "W14", "E3": "W19"}
FLAG_DEVICE = "cuda:1"


def build_chain(*, plan_path: str | Path, approvals_path: str | Path,
                e1_run: str | Path | None = None) -> dict[str, Any]:
    plan = EX42Plan.load(plan_path)
    run = Path(e1_run).resolve() if e1_run is not None else None
    steps: list[dict[str, Any]] = []
    for index, iteration in enumerate(BOUNDARIES):
        wave = index // 2
        requirements = [f"manifest.checkpoints.model_{iteration}.pt",
                        f"eval/scores/m{iteration}/p1_score.json"]
        if wave:
            requirements.extend(f"eval/scores/m{prior}/p1_score.json"
                                for prior in BOUNDARIES[:2])
        steps.append({"id": f"E1-P1-m{iteration}", "kind": "existing_ex42_p1",
                      "checkpoint": str(run / f"model_{iteration}.pt") if run else None,
                      "priority": 1, "gpu": index % 2, "wave": wave,
                      "requires": requirements,
                      "queue_command": None,
                      "blockers": ["recheck_must_use_manifest_checkpoint_sha",
                                   "existing_e1_p1_receipt_or_exact_argv_required"]})

    run_path = str(run) if run else "${E1_RUN}"
    gate_path = f"{run_path}/eval/scores/m1000/p1_score.json"
    checkpoint_path = f"{run_path}/model_1000.pt"
    flag_chain_path = f"{run_path}/eval/w09-w08/chain_receipt.json"
    steps.append({"id": "E1-exit-gate", "kind": "judge_e1_exit",
                  "requires": [f"E1-P1-m{i}=complete" for i in BOUNDARIES],
                  "decision_source": gate_path,
                  "validator": "foothold_s2.scripts.ex42_flag_baseline_chain.check_e1_gate",
                  "accepted_decisions": ["PASS", "HOLD", "FAIL"],
                  "nonpass_policy": "notify_and_stop_without_stage_extension",
                  "pass_next": "W09-W08-flag-chain",
                  "hold_next": "E1-NONPASS-notify", "fail_next": "E1-NONPASS-notify",
                  "hold_policy": "stop_post_e1_chain_and_wait_for_explicit_extension_approval",
                  "queue_command": None, "blockers": []})
    steps.append({"id": "E1-NONPASS-notify", "kind": "nonpass_notification",
                  "requires_any": ["E1-exit-gate=HOLD", "E1-exit-gate=FAIL"],
                  "skips": ["W09-W08-flag-chain", "W08-materialize-and-repin", "E1F-launch"],
                  "extension_requires_lead_approval": True,
                  "queue_command": None,
                  "argv": ["${ORCA_CLI_COMMAND}", "orchestration", "send", "--to",
                           "${EX42_ORCHESTRATION_TO}", "--type", "status",
                           "--subject", "EX-42 E1 gate HOLD", "--body",
                           "E1 gate HOLD; W09/W08, materialization and E1F launch skipped; awaiting lead approval."],
                  "blockers": []})

    # #688's single-device CLI runs W09 and all five W08 rounds serially. The
    # later --devices contract can replace this one device without changing the
    # dependency chain or allowing E1F to overlap the calibration work.
    flag_argv = ["${ISAAC311_PYTHON}", "-m", "foothold_s2.scripts.ex42_flag_baseline_chain",
                 "--checkpoint", checkpoint_path,
                 "--expected-checkpoint-sha256", "${E1_MODEL_1000_SHA256}",
                 "--e1-gate", gate_path,
                 "--plan", "${W09_W08_EVALUATION_PLAN}",
                 "--mesh-dir", "${E1_MESH_DIR}",
                 "--expected-mesh-sha256", "${E1_MESH_SHA256}",
                 "--device", FLAG_DEVICE, "--out", f"{run_path}/eval/w09-w08", "--execute"]
    steps.append({"id": "W09-W08-flag-chain", "kind": "flag_baseline_and_calibration",
                  "checkpoint": checkpoint_path, "priority": 2, "gpu": 1, "device": FLAG_DEVICE,
                  "execution": "single_device_serial_until_devices_cli",
                  "round_order": ["W09-seed42", *(f"W08-repeat-{i}" for i in range(1, 6))],
                  "requires": ["E1-exit-gate=PASS"], "queue_command": None,
                  "argv": flag_argv,
                  "completion_receipt": flag_chain_path,
                  "completion_state": "complete_after_all_six_rounds",
                  "blockers": []})

    materialize_argv = ["${ISAAC311_PYTHON}", "-m", "foothold_s2.ex42_stage_materialize",
                        "--plan", "${E1F_TEMPLATE_PLAN}", "--source-plan", "${E1_SOURCE_PLAN}",
                        "--approvals", "${E1F_TEMPLATE_APPROVALS}", "--target", "E1F",
                        "--parent-manifest", f"{run_path}/manifest.json",
                        "--gate-receipt", gate_path,
                        "--evidence", f"{run_path}/eval/materialize/E1F-stage-evidence.json",
                        "--budget-basis", "${E1F_BUDGET_BASIS}",
                        "--budget-limit", "${E1F_BUDGET_LIMIT}",
                        "--budget-used", "${E1F_BUDGET_USED}",
                        "--out", f"{run_path}/eval/materialize/E1F-repinned-" + "${SOURCE_HEAD}",
                        "--materialize-only", "--flag-chain", flag_chain_path,
                        "--expected-flag-chain-sha256", "${W09_W08_CHAIN_SHA256}"]
    materialize_blockers = []
    if not _supports_flag_materialize():
        materialize_blockers.append("verifier_materialize_cli_not_merged")
    steps.append({"id": "W08-materialize-and-repin", "kind": "materialize_only",
                  "priority": 2, "gpu": None,
                  "requires": ["W09-W08-flag-chain=complete"],
                  "queue_command": None, "argv": materialize_argv,
                  "captures": "launch_env", "training_started": False,
                  "blockers": materialize_blockers})

    steps.append({"id": "E1F-launch", "kind": "launch_materialized_stage",
                  "requires": ["W08-materialize-and-repin=complete"],
                  "launcher": "foothold_s2.scripts.ex42_stage_launcher",
                  "launch_env_source": "W08-materialize-and-repin.launch_env",
                  "auto_action": "next_stage", "target_stage": "E1F",
                  "device": "cuda:0", "ranks": 2, "queue_command": None,
                  "blockers": ["materialized_launch_env_required_at_runtime"]})

    rehearsal = build_report(plan_path=plan_path, approvals_path=approvals_path)
    previous_stage = "E1F-launch"
    for stage in SEQUENCE:
        prerequisite = STAGE_PREREQUISITES.get(stage)
        if stage == "E2":
            steps.append({"id": "W14-E2-repeat-width", "kind": "new_cell_repeat_width",
                          "priority": 2, "gpus": [0, 1], "requires": ["E1F=complete"],
                          "queue_command": None,
                          "blockers": ["W14_new_cell_evaluator_and_calibration_contract_missing"]})
        elif stage == "E3":
            steps.append({"id": "W19-E3-kind-repeat-width", "kind": "new_kind_repeat_width",
                          "priority": 2, "gpus": [0, 1], "requires": ["E2=complete"],
                          "queue_command": None,
                          "blockers": ["W19_kind_cell_evaluator_and_calibration_contract_missing"]})
        steps.append({"id": f"KIT-{stage}", "kind": "bounded_kit_stage_rehearsal",
                      "stage_id": stage, "updates": 3, "gpus": [0, 1],
                      "priority": 2,
                      "requires": [f"{previous_stage}=complete"]
                                  + ([f"{prerequisite}=complete"] if prerequisite else []),
                      "queue_command": None,
                      "blockers": next(row["blockers"] for row in rehearsal["stages"]
                                       if row["stage_id"] == stage)})
        previous_stage = f"KIT-{stage}"

    return {"format": "foothold-ex42-post-e1-gpu-chain/2", "plan_sha256": plan.sha256,
            "e1_run": str(run) if run else None,
            "schedule": steps,
            "state": "blocked" if any(row["blockers"] for row in steps) else "ready",
            "queue_mutated": False, "kit_started": False,
            "training_started": False,
            "gpu_idle_guarantee": False if any(row["blockers"] for row in steps) else True,
            "reason": "No live jobs are registered until every command and prerequisite receipt is concrete."}


def _supports_flag_materialize() -> bool:
    """Return whether this checkout contains verifier's flag-chain publication CLI."""
    try:
        from foothold_s2 import ex42_stage_materialize
        import inspect
        return "flag_chain" in inspect.signature(ex42_stage_materialize.materialize).parameters
    except (ImportError, AttributeError, TypeError):
        return False


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=str(Path(__file__).parents[1] / "curriculum/ex42-prep.yaml"))
    parser.add_argument("--approvals", default=str(Path(__file__).parents[1] / "curriculum/ex42-approvals.yaml"))
    parser.add_argument("--e1-run", type=Path)
    parser.add_argument("--register", action="store_true",
                        help="Reserved. Refuses until all job commands and completion gates exist.")
    args = parser.parse_args(argv)
    report = build_chain(plan_path=args.plan, approvals_path=args.approvals, e1_run=args.e1_run)
    if args.register:
        report["queue_mutated"] = False
        report["reason"] = "registration refused: sequence contains unresolved command/receipt blockers"
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2 if report["state"] != "ready" or args.register else 0


if __name__ == "__main__":
    raise SystemExit(main())
