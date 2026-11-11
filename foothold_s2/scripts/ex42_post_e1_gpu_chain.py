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
FLAG_DEVICES = ("cuda:0", "cuda:1")


def build_chain(*, plan_path: str | Path, approvals_path: str | Path,
                e1_run: str | Path | None = None) -> dict[str, Any]:
    plan = EX42Plan.load(plan_path)
    run = Path(e1_run).resolve() if e1_run is not None else None
    run_path = str(run) if run else "${E1_RUN}"
    manifest_path = run / "manifest.json" if run else None
    source_head = None
    if manifest_path is not None and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        source_head = ((manifest.get("git") or {}).get("head"))
    source_head_prefix = source_head[:12] if isinstance(source_head, str) and len(source_head) >= 12 else "${E1_SOURCE_HEAD_12}"
    p1_chain_receipt = f"{run_path}/eval/e1-p1-chain-{source_head_prefix}.json"
    steps: list[dict[str, Any]] = []
    previous_p1 = None
    for iteration in BOUNDARIES:
        requirements = [f"manifest.checkpoints.model_{iteration}.pt",
                        f"eval/scores/m{iteration}/p1_score.json"]
        if previous_p1 is not None:
            requirements.append(f"{previous_p1}=complete")
        steps.append({"id": f"E1-P1-m{iteration}", "kind": "serial_two_gpu_checkpoint_eval",
                      "checkpoint": str(run / f"model_{iteration}.pt") if run else None,
                      "priority": 1, "gpus": [0, 1], "devices": ["cuda:1", "cuda:0"],
                      "execution": "serial_checkpoint_order_split_each_checkpoint_across_two_gpus",
                      "requires": requirements,
                      "queue_command": None, "checkpoint_sha_source": "manifest.json",
                      "blockers": ["E1_must_end_and_publish_checkpoint_and_exact_p1_receipt"]})
        previous_p1 = f"E1-P1-m{iteration}"

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

    # #691 assigns W09 and two W08 rounds to GPU0, then three W08 rounds to
    # GPU1. Each group is sequential; the materialize and E1F stages wait for
    # the complete six-round receipt.
    flag_argv = ["${ISAAC311_PYTHON}", "-m", "foothold_s2.scripts.ex42_flag_baseline_chain",
                 "--checkpoint", checkpoint_path,
                 "--expected-checkpoint-sha256", "${E1_MODEL_1000_SHA256}",
                 "--e1-gate", gate_path,
                 "--plan", "${W09_W08_EVALUATION_PLAN}",
                 "--mesh-dir", "${E1_MESH_DIR}",
                 "--expected-mesh-sha256", "${E1_MESH_SHA256}",
                 "--devices", ",".join(FLAG_DEVICES),
                 "--out", f"{run_path}/eval/w09-w08", "--execute"]
    flag_blockers = []
    if not _supports_flag_devices():
        flag_blockers.append("scripter_dual_device_cli_not_merged")
    steps.append({"id": "W09-W08-flag-chain", "kind": "flag_baseline_and_calibration",
                  "checkpoint": checkpoint_path, "priority": 2, "gpus": list(range(2)),
                  "devices": list(FLAG_DEVICES),
                  "execution": "two_device_groups_concurrent_each_group_serial",
                  "round_order": ["W09-seed42", *(f"W08-repeat-{i}" for i in range(1, 6))],
                  "round_devices": ["cuda:0", "cuda:0", "cuda:0", "cuda:1", "cuda:1", "cuda:1"],
                  "parallel_groups": [[0, 1, 2], [3, 4, 5]],
                  "requires": ["E1-exit-gate=PASS"], "queue_command": None,
                  "argv": flag_argv,
                  "completion_receipt": flag_chain_path,
                  "completion_state": "complete_after_all_six_rounds",
                  "blockers": flag_blockers})

    evidence_path = f"{run_path}/eval/materialize/E1F-stage-evidence.json"
    evidence_argv = ["${ISAAC311_PYTHON}", "-m", "foothold_s2.scripts.ex42_e1_boundary_chain",
                     "--repo", "${FIXED_REPO}", "--e1-run", run_path,
                     "--plan", "${E1_SOURCE_PLAN}", "--training-log", "${E1_TRAINING_LOG}",
                     "--evaluation-plan", "${EVALUATION_PLAN}", "--materialize-only",
                     "--chain-receipt", p1_chain_receipt,
                     "--w09-baseline", f"{run_path}/eval/w09-w08/w09_baseline.json",
                     "--evidence-out", evidence_path,
                     "--evaluation-mesh", "${E1_EVALUATION_MESH_NPZ}"]
    steps.append({"id": "E1F-evidence-materialize", "kind": "materialize_e1f_stage_evidence",
                  "requires": ["W09-W08-flag-chain=complete"],
                  "argv": evidence_argv, "evidence_out": evidence_path, "queue_command": None,
                  "completion_receipt": p1_chain_receipt,
                  "other_required_receipt": flag_chain_path,
                  "blockers": ["completed_e1_p1_receipt_and_w09_baseline_required"]})

    materialize_argv = ["${ISAAC311_PYTHON}", "-m", "foothold_s2.ex42_stage_materialize",
                        "--plan", "${E1F_TEMPLATE_PLAN}", "--source-plan", "${E1_SOURCE_PLAN}",
                        "--approvals", "${E1F_TEMPLATE_APPROVALS}", "--target", "E1F",
                        "--parent-manifest", f"{run_path}/manifest.json",
                        "--gate-receipt", gate_path,
                        "--evidence", evidence_path,
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
                  "requires": ["E1F-evidence-materialize=complete"],
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


def _supports_flag_devices() -> bool:
    """Return whether the merged flag producer accepts its dual-device contract."""
    try:
        from foothold_s2.scripts import ex42_flag_baseline_chain
        import inspect
        return "devices" in inspect.signature(ex42_flag_baseline_chain.run_chain).parameters
    except (ImportError, AttributeError, TypeError):
        return False


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", "--repo", dest="source_repo", type=Path,
                        default=Path(__file__).resolve().parents[2],
                        help="fixed source checkout used by the E1 run")
    parser.add_argument("--plan", default=str(Path(__file__).parents[1] / "curriculum/ex42-prep.yaml"))
    parser.add_argument("--approvals", default=str(Path(__file__).parents[1] / "curriculum/ex42-approvals.yaml"))
    parser.add_argument("--e1-run", type=Path)
    parser.add_argument("--training-log", type=Path,
                        help="actual E1 training log for a read-only dependency preflight")
    parser.add_argument("--preflight", action="store_true",
                        help="validate plan plus actual E1 inputs without claiming they are complete")
    parser.add_argument("--register", action="store_true",
                        help="Reserved. Refuses until all job commands and completion gates exist.")
    args = parser.parse_args(argv)
    report = build_chain(plan_path=args.plan, approvals_path=args.approvals, e1_run=args.e1_run)
    if args.preflight:
        inputs = {"e1_run": args.e1_run, "training_log": args.training_log,
                  "source_repo": args.source_repo}
        missing = [name for name, value in inputs.items() if value is None or not Path(value).exists()]
        if missing:
            report["preflight_state"] = "blocked"
            report["preflight_missing"] = missing
        else:
            report["preflight_state"] = "inputs_present_plan_valid"
            report["preflight_inputs"] = {name: str(Path(value).resolve()) for name, value in inputs.items()}
            report["preflight_source_head"] = __import__("subprocess").check_output(
                ["git", "rev-parse", "HEAD"], cwd=args.source_repo, text=True).strip()
            report["preflight_log_bytes"] = Path(args.training_log).stat().st_size
            manifest_path = Path(args.e1_run) / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            startup = json.loads((Path(args.e1_run) / "startup_receipt.json").read_text(encoding="utf-8-sig"))
            source_plan = EX42Plan.load(args.plan)
            progress = manifest.get("progress") or {}
            report["preflight_manifest_progress"] = progress.get("completed_updates")
            report["preflight_manifest_source_head"] = (manifest.get("git") or {}).get("head")
            report["preflight_manifest_plan_sha256"] = startup.get("plan_sha256")
            report["preflight_plan_sha256"] = source_plan.sha256
            report["preflight_checkpoints"] = {
                str(i): {"manifest_sha": (manifest.get("checkpoints") or {}).get(f"model_{i}.pt"),
                         "file_exists": (Path(args.e1_run) / f"model_{i}.pt").is_file(),
                         "score_exists": (Path(args.e1_run) / "eval/scores" / f"m{i}" / "p1_score.json").is_file()}
                for i in BOUNDARIES
            }
            report["preflight_w09_baseline_exists"] = (
                Path(args.e1_run) / "eval/w09-w08/w09_baseline.json").is_file()
            report["preflight_chain_receipts"] = sorted(
                path.name for path in (Path(args.e1_run) / "eval").glob("e1-p1-chain-*.json"))
            report["preflight_materialize_only_argv"] = next(
                row["argv"] for row in report["schedule"] if row["id"] == "E1F-evidence-materialize")
            mismatches = []
            if report["preflight_source_head"] != report["preflight_manifest_source_head"]:
                mismatches.append("source_HEAD_differs_from_E1_manifest")
            if report["preflight_plan_sha256"] != report["preflight_manifest_plan_sha256"]:
                mismatches.append("source_plan_differs_from_E1_startup_receipt")
            report["preflight_identity_mismatches"] = mismatches
    if args.register:
        report["queue_mutated"] = False
        report["reason"] = "registration refused: sequence contains unresolved command/receipt blockers"
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    preflight_failed = args.preflight and (
        report.get("preflight_state") != "inputs_present_plan_valid"
        or report.get("preflight_identity_mismatches"))
    return 2 if (report["state"] != "ready" and not args.preflight) or args.register or preflight_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
