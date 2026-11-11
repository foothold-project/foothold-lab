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

    steps.append({"id": "W09-flag-baseline", "kind": "flag_baseline_once",
                  "checkpoint": str(run / "model_1000.pt") if run else None,
                  "priority": 2, "gpu": 0,
                  "requires": ["E1_P1_m1000=PASS", "E1_graduation_receipt"],
                  "queue_command": None,
                  "blockers": ["W09_flag_cell_evaluator_command_missing",
                               "E1_graduation_checkpoint_SHA_not_yet_available"]})
    prior_w08 = "W09-flag-baseline"
    for repeat in range(1, 6):
        steps.append({"id": f"W08-flag-calibration-{repeat}",
                      "kind": "flag_calibration_repeat", "repeat": repeat,
                      "checkpoint": str(run / "model_1000.pt") if run else None,
                      "priority": 2, "gpu": (repeat - 1) % 2,
                      "requires": [f"{prior_w08}=complete"],
                      "queue_command": None,
                      "blockers": ["flag_cell_calibration_producer_missing",
                                   "five-run_calibration_receipt_contract_missing"]})
        prior_w08 = f"W08-flag-calibration-{repeat}"

    steps.append({"id": "W08-materialize-and-repin", "kind": "materialize_only",
                  "priority": 2, "gpu": 0,
                  "requires": ["W08-flag-calibration-5=complete"],
                  "queue_command": None,
                  "calibration_out": None, "repinned_plan_out": None,
                  "blockers": ["W08_calibration_artifact_schema_missing",
                               "materialize_only_and_plan_repin_command_missing"]})

    rehearsal = build_report(plan_path=plan_path, approvals_path=approvals_path)
    previous_stage = "W08-materialize-and-repin"
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

    return {"format": "foothold-ex42-post-e1-gpu-chain/1", "plan_sha256": plan.sha256,
            "e1_run": str(run) if run else None,
            "schedule": steps,
            "state": "blocked" if any(row["blockers"] for row in steps) else "ready",
            "queue_mutated": False, "kit_started": False,
            "training_started": False,
            "gpu_idle_guarantee": False if any(row["blockers"] for row in steps) else True,
            "reason": "No live jobs are registered until every command and prerequisite receipt is concrete."}


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
