"""CPU-only record of old E1 windows under a later C1 evaluation policy."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.ex42_e1_wide_plan import validate_evaluation_scope
from foothold_s2.ex42_eval_once import manifest_checkpoint_sha
from foothold_s2.ex42_score import measure


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recount(run: Path, output: Path, *, execution_plan: Path, evaluation_plan: Path,
            iterations: tuple[int, ...], mesh_sha256: str) -> dict:
    run = Path(run).resolve(strict=True)
    output = Path(output).absolute()
    if output.is_relative_to(run) or output.exists() or not iterations or len(set(iterations)) != len(iterations):
        raise ValueError("C1 old-window record needs distinct boundaries and a fresh external output")
    source = EX42Plan.load(execution_plan)
    policy = EX42Plan.load(evaluation_plan)
    validate_evaluation_scope(source.path, policy.path)
    refs = []
    for iteration in iterations:
        if type(iteration) is not int or iteration <= 0 or iteration % source.document["evaluation"]["interval_updates"]:
            raise ValueError("C1 old-window iteration is not a boundary")
        checkpoint = run / f"model_{iteration}.pt"
        checkpoint_sha, actual = manifest_checkpoint_sha(checkpoint)
        if actual != iteration:
            raise ValueError("C1 old-window checkpoint iteration differs")
        original = run / "eval" / "scores" / f"m{iteration}"
        kit, original_score = original / "eval_receipt.json", original / "ex42_score.json"
        receipt = json.loads(kit.read_text(encoding="utf-8-sig"))
        if (receipt.get("state") != "done" or receipt.get("checkpoint_sha256") != checkpoint_sha
                or (receipt.get("evaluation_plan") or {}).get("sha256") != source.sha256
                or not original_score.is_file()):
            raise ValueError("C1 old-window original receipt differs")
        refs.append((iteration, checkpoint, original, kit, original_score,
                     _sha(kit), _sha(original_score), checkpoint_sha))
    output.mkdir(parents=True)
    rows = []
    for iteration, checkpoint, original, kit, original_score, kit_sha, score_sha, checkpoint_sha in refs:
        score = measure(checkpoint, original, expected_seed=42, expected_mesh_sha256=mesh_sha256,
                        stage_id="E1", evaluation_plan_path=policy.path,
                        execution_plan_path=source.path)
        if _sha(kit) != kit_sha or _sha(original_score) != score_sha:
            raise ValueError("C1 old-window source changed during CPU recount")
        target = output / f"m{iteration}"
        target.mkdir()
        (target / "ex42_score.json").write_text(json.dumps(score, ensure_ascii=False,
                                                allow_nan=False, indent=2) + "\n", encoding="utf-8")
        wide = score.get("e1_exit_v2", {}).get("wide_current", {})
        rows.append({"iteration": iteration, "checkpoint_sha256": checkpoint_sha,
                     "source_receipt": str(kit), "source_receipt_sha256": kit_sha,
                     "source_score": str(original_score), "source_score_sha256": score_sha,
                     "record_score": str(target / "ex42_score.json"),
                     "record_score_sha256": _sha(target / "ex42_score.json"),
                     "judgement_record_only": score["judgement"],
                     "wide_state": wide.get("judgement", "HOLD"),
                     "wide_missing": not bool(score.get("e1_wide_cells", {}).get("sources"))})
    receipt = {"format": "foothold-ex42-e1-c1-old-window-recount/1", "state": "record_only",
               "official_gate": False, "source_plan_sha256": source.sha256,
               "evaluation_plan_sha256": policy.sha256, "mesh_sha256": mesh_sha256,
               "windows": rows}
    (output / "recount_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False,
                                               allow_nan=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execution-plan", type=Path, required=True)
    parser.add_argument("--evaluation-plan", type=Path, required=True)
    parser.add_argument("--iterations", required=True, help="comma-separated local boundary iterations")
    parser.add_argument("--mesh-sha256", required=True)
    args = parser.parse_args(argv)
    row = recount(args.run, args.out, execution_plan=args.execution_plan,
                  evaluation_plan=args.evaluation_plan,
                  iterations=tuple(int(x) for x in args.iterations.split(",")),
                  mesh_sha256=args.mesh_sha256)
    print(json.dumps({"state": row["state"], "windows": [x["iteration"] for x in row["windows"]],
                      "receipt": str(args.out / "recount_receipt.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
