"""Run the four ordered E1 P1 boundary evaluations from one lead command."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable

from foothold_s2.scripts.ex42_e1_boundary_queue import build_queue_plan
from foothold_s2.scripts.ex42_e1_materialize_evidence import write_evidence
from foothold_s2.scripts.ex42_p1_queue_item import run_item


def _write_receipt(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def _write_p1_done(path: str | Path | None, row: dict[str, Any]) -> None:
    if path is None:
        return
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refusing to replace E1 P1 completion marker: {path}")
    _write_receipt(path, {"format": "foothold-ex42-e1-p1-done/1",
                          "state": "complete", "chain_receipt": str(Path(row["chain_receipt"]).resolve()),
                          "completed_iterations": [item["iteration"] for item in row["completed"]],
                          "plan_sha256": row["plan_sha256"],
                          "finished_at": datetime.now().astimezone().isoformat(timespec="seconds")})


def execute_chain(plan: dict[str, Any], *, item_runner: Callable = run_item,
                  popen: Callable = subprocess.run,
                  evidence_writer: Callable = write_evidence) -> dict[str, Any]:
    """Execute m250 -> m500 -> m750 -> m1000 serially; stop at the first bad receipt."""
    if plan.get("primary_execution") != "direct_two_gpu_sequential_chain" or plan.get("queue_mutated") is not False:
        raise ValueError("EX-42 E1 chain plan is not the direct two-GPU, no-queue plan")
    receipt_path = Path(plan["chain_receipt"])
    log_dir = Path(plan["log_dir"])
    done_path = Path(plan["p1_done_path"]) if plan.get("p1_done_path") else None
    if receipt_path.exists() or log_dir.exists() or (done_path is not None and done_path.exists()):
        raise ValueError("EX-42 E1 chain output already exists")
    log_dir.mkdir(parents=True, exist_ok=False)
    row = {"format": "foothold-ex42-e1-p1-boundary-chain-receipt/1", "state": "running",
           "source_head": plan["source_head"], "plan_sha256": plan["plan_sha256"],
           "approvals_sha256": plan["approvals_sha256"], "e1_run": plan["e1_run"],
           "devices": ["cuda:1", "cuda:0"], "completed": [], "current": None,
           "queue_mutated": False, "chain_receipt": str(receipt_path),
           "started_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    _write_receipt(receipt_path, row)
    for job in plan["jobs"]:
        iteration = job["iteration"]
        log_path = log_dir / f"m{iteration}.log"
        row["current"] = iteration
        row["last_log"] = str(log_path)
        _write_receipt(receipt_path, row)
        print(f"EX42_E1_P1_BEGIN m{iteration} device=cuda:1 split=cuda:0", flush=True)

        def logged_eval(argv, *, check=False):
            with log_path.open("wb") as stream:
                return popen(argv, check=check, cwd=plan["repo"], stdout=stream,
                             stderr=subprocess.STDOUT)

        try:
            rc = item_runner(evaluator_argv=job["eval_argv"], iteration=iteration,
                             marker=job["marker"], popen=logged_eval)
            if rc != 0:
                row.update(state="failed", reason=f"evaluator_rc_{rc}", failed_iteration=iteration)
                _write_receipt(receipt_path, row)
                print(f"EX42_E1_P1_FAILED m{iteration} rc={rc}", flush=True)
                return row
        except (OSError, ValueError, KeyError, IndexError) as exc:
            row.update(state="failed", reason=f"{type(exc).__name__}: {exc}", failed_iteration=iteration)
            _write_receipt(receipt_path, row)
            print(f"EX42_E1_P1_FAILED m{iteration} {type(exc).__name__}: {exc}", flush=True)
            return row
        row["completed"].append({"iteration": iteration, "marker": job["marker"],
                                 "output": job["output"], "log": str(log_path)})
        row["current"] = None
        _write_receipt(receipt_path, row)
        print(f"EX42_E1_P1_DONE m{iteration} marker={job['marker']}", flush=True)

    row.update(state="complete", finished_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    _write_p1_done(done_path, row)
    baseline = plan.get("w09_baseline")
    if not baseline or not Path(baseline).is_file():
        row.update(state="p1_complete_waiting_w09_baseline", evidence_state="waiting_for_w09_baseline",
                   reason="P1 complete; invoke materialize-only when the W09 artifact exists",
                   materialize_inputs={key: plan.get(key) for key in
                                       ("plan_path", "parent_manifest", "gate_receipt", "training_log",
                                        "evaluation_mesh_path", "evaluation_plan_path",
                                        "w09_baseline", "evidence_path")})
        _write_receipt(receipt_path, row)
        print(f"EX42_E1F_EVIDENCE_WAITING_FOR_W09 path={baseline or 'unspecified'}", flush=True)
        return row
    row["evidence_path"] = plan["evidence_path"]
    _write_receipt(receipt_path, row)
    try:
        evidence = evidence_writer(
            out_path=plan["evidence_path"], source_plan_path=plan["plan_path"],
            parent_manifest_path=plan["parent_manifest"], gate_receipt_path=plan["gate_receipt"],
            training_log_path=plan["training_log"],
            evaluation_mesh_path=plan["evaluation_mesh_path"],
            w09_baseline_path=plan["w09_baseline"],
            evaluation_plan_path=plan["evaluation_plan_path"])
        row.update(evidence_state="ready", applied_level_cap=evidence["applied_level_cap"],
                   evidence_sha256=hashlib.sha256(Path(plan["evidence_path"]).read_bytes()).hexdigest())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        row.update(state="p1_complete_e1f_evidence_failed",
                   reason=f"{type(exc).__name__}: {exc}")
        _write_receipt(receipt_path, row)
        print(f"EX42_E1F_EVIDENCE_FAILED {type(exc).__name__}: {exc}", flush=True)
        return row
    _write_receipt(receipt_path, row)
    print(f"EX42_E1_P1_CHAIN_COMPLETE receipt={receipt_path} e1f_evidence={plan['evidence_path']}", flush=True)
    return row


def materialize_only(*, receipt_path: str | Path, source_plan_path: str | Path,
                     parent_manifest_path: str | Path, gate_receipt_path: str | Path,
                     training_log_path: str | Path, evaluation_mesh_path: str | Path,
                     w09_baseline_path: str | Path, evidence_out: str | Path,
                     evaluation_plan_path: str | Path,
                     evidence_writer: Callable = write_evidence) -> dict[str, Any]:
    """Finish E1F evidence after the separate W09 baseline step without rerunning P1."""
    receipt_path = Path(receipt_path).resolve(strict=True)
    row = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    if (row.get("format") != "foothold-ex42-e1-p1-boundary-chain-receipt/1"
            or row.get("state") not in ("p1_complete_waiting_w09_baseline", "p1_complete_e1f_evidence_failed")
            or [item.get("iteration") for item in row.get("completed", [])] != [250, 500, 750, 1000]):
        raise ValueError("E1 P1 chain receipt is not a complete, retryable four-boundary chain")
    evidence = evidence_writer(
        out_path=evidence_out, source_plan_path=source_plan_path,
        parent_manifest_path=parent_manifest_path, gate_receipt_path=gate_receipt_path,
        training_log_path=training_log_path, evaluation_mesh_path=evaluation_mesh_path,
        w09_baseline_path=w09_baseline_path, evaluation_plan_path=evaluation_plan_path)
    row.update(state="complete", evidence_state="ready", evidence_path=str(Path(evidence_out).resolve()),
               applied_level_cap=evidence["applied_level_cap"],
               evidence_sha256=hashlib.sha256(Path(evidence_out).read_bytes()).hexdigest(),
               finished_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    _write_receipt(receipt_path, row)
    print(f"EX42_E1F_EVIDENCE_READY path={evidence_out}", flush=True)
    return row


def main(argv=None) -> int:
    repo_default = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=repo_default)
    parser.add_argument("--e1-run", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=repo_default / "foothold_s2/curriculum/ex42-prep.yaml")
    parser.add_argument("--approvals", type=Path, default=repo_default / "foothold_s2/curriculum/ex42-approvals.yaml")
    parser.add_argument("--training-log", type=Path, required=True,
                        help="explicit completed E1 rank log path")
    parser.add_argument("--evaluation-plan", type=Path, required=True,
                        help="integrated plan used for D44/maintenance measurement identity")
    parser.add_argument("--w09-baseline", type=Path,
                        help="measured W09 baseline JSON; required for E1F evidence production")
    parser.add_argument("--evidence-out", type=Path)
    parser.add_argument("--p1-done", type=Path,
                        help="write a separate completion marker after all four boundary evaluations succeed")
    parser.add_argument("--evaluation-mesh", type=Path,
                        help="exact terrain_mesh.npz used by the E1 map evaluation")
    parser.add_argument("--materialize-only", action="store_true",
                        help="write E1F materialization input from a completed chain after W09 is ready")
    parser.add_argument("--chain-receipt", type=Path,
                        help="existing E1 P1 chain receipt for --materialize-only")
    parser.add_argument("--e1-ended", action="store_true", help="required assertion: E1 training ended")
    parser.add_argument("--execute", action="store_true", help="run the four P1 evaluations serially on both GPUs")
    args = parser.parse_args(argv)
    try:
        if args.materialize_only:
            required = (args.chain_receipt, args.w09_baseline, args.evidence_out,
                        args.training_log, args.evaluation_mesh, args.evaluation_plan)
            if any(value is None for value in required):
                raise ValueError("materialize-only requires chain receipt, training log, W09 baseline, and evidence output")
            source_plan = args.plan.resolve(strict=True)
            e1_run = args.e1_run.resolve(strict=True)
            # The completed m1000 P1 and its output are fixed by the chain receipt contract.
            result = materialize_only(
                receipt_path=args.chain_receipt, source_plan_path=source_plan,
                parent_manifest_path=e1_run / "manifest.json",
                gate_receipt_path=e1_run / "eval/scores/m1000/p1_score.json",
                training_log_path=args.training_log,
                evaluation_mesh_path=args.evaluation_mesh,
                w09_baseline_path=args.w09_baseline, evidence_out=args.evidence_out,
                evaluation_plan_path=args.evaluation_plan)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
        if args.execute and args.evidence_out is None:
            raise ValueError("execution requires an explicit E1F evidence output path")
        plan = build_queue_plan(repo=args.repo, e1_run=args.e1_run, plan_path=args.plan,
                                approvals_path=args.approvals, e1_ended=args.e1_ended,
                                evaluation_plan_path=args.evaluation_plan,
                                training_log_path=args.training_log,
                                w09_baseline_path=args.w09_baseline,
                                require_clean=True, require_locked=True)
        plan["repo"] = str(Path(args.repo).resolve(strict=True))
        plan["p1_done_path"] = str(args.p1_done.resolve()) if args.p1_done else None
        if args.evidence_out:
            plan["evidence_path"] = str(args.evidence_out.resolve())
        if not args.execute:
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        row = execute_chain(plan)
        return 0 if row["state"] in ("complete", "p1_complete_waiting_w09_baseline") else 5
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"state": "blocked", "reason": f"{type(exc).__name__}: {exc}",
                          "queue_mutated": False, "kit_started": False,
                          "training_started": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
