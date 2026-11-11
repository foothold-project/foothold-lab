"""Reissue E1 P1 judgments from completed Kit evidence without touching live results.

The new output has its own identity. Each D44 trace is linked read-only from its
original Kit run and checked by SHA before scoring; map, stand and axis artifacts
are likewise consumed without launching Isaac. W09 may use the new m1000 P1
receipt only when the four-boundary gate is PASS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.eval.ex42_d44_cells import contract, read_evidence, summarize
from foothold_s2.eval.ex42_eval_tile_mesh import source_tile
from foothold_s2.ex42_eval_once import manifest_checkpoint_sha, p1_score_from_measure
from foothold_s2.ex42_score import digest, measure

BOUNDARIES = (250, 500, 750, 1000)
OTHER_EVIDENCE = ("map64", "stand_eval_gt", "stand_eval_pred", "stand_probe_prop_only", "axis_v2")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, row: dict) -> None:
    path.write_text(json.dumps(row, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def _preflight(run: Path, iteration: int, policy: EX42Plan, settings: dict) -> dict:
    checkpoint = run / f"model_{iteration}.pt"
    checkpoint_sha, actual = manifest_checkpoint_sha(checkpoint)
    if actual != iteration:
        raise ValueError(f"E1 m{iteration} checkpoint iteration differs")
    source = run / "eval" / "scores" / f"m{iteration}"
    receipt_path = source / "eval_receipt.json"
    receipt = _read(receipt_path)
    d44 = source / "d44"
    kit_path = d44 / "d44_cells.json"
    kit = _read(kit_path)
    if (receipt.get("state") != "done" or Path(receipt.get("checkpoint", "")).resolve() != checkpoint.resolve()
            or receipt.get("checkpoint_sha256") != checkpoint_sha or receipt.get("eval_seed") != 42
            or (receipt.get("evaluation_plan") or {}).get("sha256") != policy.sha256
            or (receipt.get("steps", {}).get("d44") or {}).get("state") != "done"
            or kit.get("format") != "foothold-ex42-d44-eval/1" or kit.get("state") != "done"
            or kit.get("checkpoint_sha256") != checkpoint_sha or kit.get("plan_sha256") != policy.sha256
            or kit.get("seed") != 42 or kit.get("envs") != 64
            or set(kit.get("cases", {})) != set(settings["judge_cases"] + settings["record_cases"])):
        raise ValueError(f"E1 m{iteration} original Kit or P1 identity incomplete")
    for name in OTHER_EVIDENCE:
        if not (source / name).is_dir():
            raise ValueError(f"E1 m{iteration} {name} evidence absent")
    for case_id in kit["cases"]:
        index = kit["cases"][case_id]
        case_path, trace_path = d44 / f"{case_id}.json", d44 / f"{case_id}.npz"
        row = _read(case_path)
        if (digest(case_path) != index.get("raw_sha256") or
                digest(trace_path) != index.get("trace_sha256") or
                row.get("trace_sha256") != index["trace_sha256"] or
                row.get("case_id") != case_id or
                row.get("trace_file") is None or
                Path(row["trace_file"]).resolve() != trace_path.resolve()):
            raise ValueError(f"E1 m{iteration} {case_id} original raw SHA differs")
    return {"iteration": iteration, "source": source, "receipt_path": receipt_path,
            "receipt_sha256": digest(receipt_path), "kit_path": kit_path,
            "kit_sha256": digest(kit_path), "checkpoint": checkpoint,
            "checkpoint_sha256": checkpoint_sha, "kit": kit}


def _reissue_one(item: dict, output: Path, policy: EX42Plan, plan_path: Path,
                 approvals: Path, settings: dict, anchors: dict) -> dict:
    source, kit = item["source"], item["kit"]
    output.mkdir()
    for name in OTHER_EVIDENCE:
        (output / name).symlink_to((source / name).resolve(), target_is_directory=True)
    d44 = output / "d44"
    d44.mkdir()
    cases = {}
    for case_id in (*settings["judge_cases"], *settings["record_cases"]):
        trace_source = source / "d44" / f"{case_id}.npz"
        trace = d44 / f"{case_id}.npz"
        trace.symlink_to(trace_source.resolve())
        with np.load(trace, allow_pickle=False) as arrays:
            score = summarize({key: arrays[key] for key in arrays.files},
                              spec=settings["case_specs"][case_id], anchors=anchors,
                              settings=settings, dt=float(arrays["dt"]))
        spec = settings["case_specs"][case_id]
        row = {"case_id": case_id, "task": spec["task"], "map_mode": spec["map_mode"],
               "role": spec["role"], **score,
               "trace_file": str(trace), "trace_sha256": digest(trace)}
        case_path = d44 / f"{case_id}.json"
        _write(case_path, row)
        cases[case_id] = {key: row[key] for key in
                          ("case_id", "envs", "valid_count", "success_count", "survival_count",
                           "trace_file", "trace_sha256")}
        cases[case_id].update(raw_file=str(case_path), raw_sha256=digest(case_path))
    derived = {**kit, "cases": cases,
               "cpu_reissue": {"format": "foothold-ex42-d44-cpu-reissue/1",
                               "original_kit_receipt": str(item["kit_path"]),
                               "original_kit_receipt_sha256": item["kit_sha256"]}}
    _write(d44 / "d44_cells.json", derived)
    read_evidence(d44, plan=policy.document, plan_sha256=policy.sha256,
                  checkpoint_sha256=item["checkpoint_sha256"], seed=42)
    old = _read(item["receipt_path"])
    score = measure(item["checkpoint"], output, expected_seed=42,
                    expected_mesh_sha256=old["ex42_mesh"]["mesh_sha256"],
                    stage_id="E1", evaluation_plan_path=policy.path)
    _write(output / "ex42_score.json", score)
    p1 = p1_score_from_measure(score, checkpoint=item["checkpoint"], iteration=item["iteration"],
                               plan_path=plan_path, approvals_path=approvals,
                               stage_id="E1", output=output, evaluation_plan_path=policy.path)
    _write(output / "p1_score.json", p1)
    _write(output / "eval_receipt.json", {**old, "state": "done", "score": str(output / "ex42_score.json"),
           "p1_score": str(output / "p1_score.json"), "judgement": p1["judgment"],
           "next_stage_notice": None,
           "cpu_reissue": {"format": "foothold-ex42-p1-cpu-reissue/1",
                           "original_eval_receipt": str(item["receipt_path"]),
                           "original_eval_receipt_sha256": item["receipt_sha256"],
                           "original_d44_kit_receipt_sha256": item["kit_sha256"]}})
    return {"iteration": item["iteration"], "output": str(output),
            "source_eval_receipt_sha256": item["receipt_sha256"],
            "source_d44_kit_receipt_sha256": item["kit_sha256"],
            "score_sha256": digest(output / "ex42_score.json"),
            "p1_sha256": digest(output / "p1_score.json"), "judgment": p1["judgment"]}


def reissue(run: Path, out: Path, *, p1_plan: Path, approvals: Path,
            evaluation_plan: Path, iterations: tuple[int, ...] = BOUNDARIES,
            source_chain: Path | None = None) -> dict:
    if not iterations or any(i not in BOUNDARIES for i in iterations) or tuple(sorted(set(iterations))) != iterations:
        raise ValueError("E1 reissue iterations must be ordered distinct boundaries")
    run, out = run.resolve(strict=True), out.resolve()
    if run == out or run in out.parents:
        raise ValueError("E1 CPU reissue output must be outside the live run")
    if out.exists():
        raise ValueError("E1 CPU reissue requires a fresh output root")
    p1_plan, approvals, evaluation_plan = (p.resolve(strict=True) for p in
                                           (p1_plan, approvals, evaluation_plan))
    plan, policy = EX42Plan.load(p1_plan), EX42Plan.load(evaluation_plan)
    settings = contract(policy.document)
    source_manifest, column = source_tile(Path(settings["source_mesh_dir"]))
    if source_manifest["mesh_sha256"] != settings["source_mesh_sha256"]:
        raise ValueError("E1 D44 source mesh differs from approved plan")
    if source_chain is None:
        chain_receipts = list((run / "eval").glob("e1-p1-chain-*.json"))
        if len(chain_receipts) != 1:
            raise ValueError("E1 original P1 chain receipt must be unique or given by --source-chain")
        original_chain = chain_receipts[0]
    else:
        original_chain = source_chain.resolve(strict=True)
        if original_chain.parent != run / "eval":
            raise ValueError("E1 source chain must be inside the original run eval directory")
    chain = _read(original_chain)
    chain_sha = digest(original_chain)
    if (chain.get("format") != "foothold-ex42-e1-p1-boundary-chain-receipt/1"
            or chain.get("plan_sha256") != plan.sha256
            or chain.get("approvals_sha256") != digest(approvals)):
        raise ValueError("E1 original P1 chain plan or approval identity differs")
    items = [_preflight(run, i, policy, settings) for i in iterations]
    out.mkdir(parents=True)
    completed = []
    for item in items:
        completed.append(_reissue_one(item, out / f"m{item['iteration']}", policy,
                                      p1_plan, approvals, settings, column["anchors_local_m"]))
    # Detect source mutation during the CPU pass; never bless a moving original.
    if digest(original_chain) != chain_sha or any(
            digest(item["receipt_path"]) != item["receipt_sha256"] or
            digest(item["kit_path"]) != item["kit_sha256"] for item in items):
        raise ValueError("E1 original receipt changed during CPU reissue")
    full = iterations == BOUNDARIES
    gate = completed[-1]["judgment"] if full else "HOLD"
    state = ("p1_complete_waiting_w09_baseline" if gate == "PASS" else
             "p1_complete_gate_nonpass" if full else "partial_not_gate_ready")
    chain_receipt = {"format": "foothold-ex42-e1-p1-boundary-chain-receipt/1",
                     "state": state, "cpu_reissue": True, "source_chain_receipt": str(original_chain),
                     "source_chain_receipt_sha256": chain_sha,
                     "source_head": chain["source_head"], "plan_sha256": plan.sha256,
                     "approvals_sha256": digest(approvals), "e1_run": str(run),
                     "completed": completed, "current": None, "queue_mutated": False,
                     "chain_receipt": str(out / "chain_receipt.json")}
    _write(out / "chain_receipt.json", chain_receipt)
    decision = {"format": "foothold-ex42-e1-cpu-reissue-gate/1", "state": state,
                "judgment": gate, "w09_eligible": full and gate == "PASS",
                "p1_score": str(out / "m1000" / "p1_score.json") if full else None,
                "p1_score_sha256": completed[-1]["p1_sha256"] if full else None,
                "chain_receipt": str(out / "chain_receipt.json"),
                "chain_receipt_sha256": digest(out / "chain_receipt.json")}
    _write(out / "gate_decision.json", decision)
    return decision


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--p1-plan", type=Path, required=True)
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--evaluation-plan", type=Path, required=True)
    parser.add_argument("--source-chain", type=Path,
                        help="select the original chain when the run has multiple chain receipts")
    parser.add_argument("--iterations", default="250,500,750,1000")
    args = parser.parse_args(argv)
    try:
        iterations = tuple(int(part) for part in args.iterations.split(","))
        decision = reissue(args.run, args.out, p1_plan=args.p1_plan,
                           approvals=args.approvals, evaluation_plan=args.evaluation_plan,
                           iterations=iterations, source_chain=args.source_chain)
        print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(5, f"EX42_D44_CPU_REISSUE_ERROR {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
