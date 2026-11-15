"""Rejudge saved EX-42 E1 boundary evaluations under a graduation evaluation plan (CPU, read-only on the sources).

Why: the graduation plan (evaluation.e1_widened.graduation: 0.5 s window MAE, near_threshold R_0p1 0.06, L3 fwd1.0
judged with the heading-forward 3.5 m rule) is a separate evaluation plan with its own sha. The run keeps its training
plan and its running evaluation plan untouched. This tool walks the boundaries in order (each window needs the previous
window rejudged under the same plan), writes the new scores into a fresh tree whose raw folders are symlinks to the
saved evaluation, and prints the old and new judgment cell by cell.

The source evaluation is never written. The output root must be a fresh folder."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _read(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write(path: Path, doc: dict) -> None:
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _cells(score: dict) -> dict:
    """Flatten the judged items of an E1 v2 score: name -> (judgement, key numbers)."""
    out = {}
    exit_v2 = score.get("e1_exit_v2") or {}
    for name, row in ((exit_v2.get("current") or {}).get("items") or {}).items():
        out[f"v2/{name}"] = row
    for name, row in ((exit_v2.get("wide_current") or {}).get("items") or {}).items():
        out[f"wide/{name}"] = row
    return out


def _brief(row: dict) -> dict:
    keep = ("role", "judgement", "R", "mae_mps", "success", "survival", "valid", "near_threshold",
            "mae_window_s", "mae_step_mps", "success_rule")
    return {k: row[k] for k in keep if k in row}


def rejudge_chain(src_scores: Path, dst_root: Path, *, plan_path: Path, training_plan: Path, approvals: Path,
                  iterations: list[int]) -> dict:
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_eval_once import p1_score_from_measure
    from foothold_s2.ex42_score import digest, measure

    src_scores, dst_root = Path(src_scores).resolve(strict=True), Path(dst_root).absolute()
    if dst_root.exists():
        raise ValueError("rejudge output root must be fresh")
    grad_plan = EX42Plan.load(plan_path)
    execution = EX42Plan.load(training_plan)
    dst_root.mkdir(parents=True)
    rows = {}
    for number in sorted(iterations):
        src, dst = src_scores / f"m{number}", dst_root / f"m{number}"
        old_score = _read(src / "ex42_score.json")
        # A boundary scored again from raw may have no P1 receipt of its own; the stage and iteration then come from
        # the saved score and the folder name.
        old_p1 = (_read(src / "p1_score.json") if (src / "p1_score.json").is_file()
                  else {"stage_id": old_score.get("stage_id"), "checkpoint_iteration": number})
        receipt = _read(src / "eval_receipt.json")
        if old_p1.get("stage_id") != "E1" or old_score.get("execution_plan_sha256") != execution.sha256:
            raise ValueError(f"m{number}: saved score is not the E1 run of this training plan")
        dst.mkdir()
        for entry in src.iterdir():
            if entry.name in ("ex42_score.json", "p1_score.json", "next_stage_notice.json"):  # rewritten here
                continue
            os.symlink(entry, dst / entry.name)
        checkpoint = Path(old_score["checkpoint"])
        score = measure(checkpoint, dst, expected_seed=receipt["eval_seed"],
                        expected_mesh_sha256=receipt["ex42_mesh"]["mesh_sha256"], stage_id="E1",
                        evaluation_plan_path=grad_plan.path, execution_plan_path=execution.path)
        _write(dst / "ex42_score.json", score)
        p1 = p1_score_from_measure(score, checkpoint=checkpoint, iteration=old_p1["checkpoint_iteration"],
                                   plan_path=execution.path, approvals_path=approvals, stage_id="E1",
                                   output=dst, evaluation_plan_path=grad_plan.path)
        _write(dst / "p1_score.json", p1)
        old_cells, new_cells = _cells(old_score), _cells(score)
        diff = {}
        for name in sorted(set(old_cells) | set(new_cells)):
            old_row, new_row = _brief(old_cells.get(name, {})), _brief(new_cells.get(name, {}))
            diff[name] = {"old": old_row, "new": new_row, "changed": old_row != new_row}
        rows[f"m{number}"] = {
            "checkpoint_sha256": score["checkpoint_sha256"],
            "old_p1_receipt": (src / "p1_score.json").is_file(),
            "old_judgement": old_score.get("judgement"), "new_judgement": score.get("judgement"),
            "old_maintenance_source_sha256": old_score.get("maintenance_source_sha256"),
            "new_maintenance_source_sha256": score.get("maintenance_source_sha256"),
            "plan_sha256": p1["plan_sha256"], "p1_judgment": p1["judgment"],
            "new_score": str(dst / "ex42_score.json"), "new_p1": str(dst / "p1_score.json"),
            "new_score_sha256": digest(dst / "ex42_score.json"),
            "cells": diff,
            "reason": score.get("reason"),
            "provenance_error": (score.get("e1_exit_v2") or {}).get("provenance_error")}
    report = {"format": "foothold-ex42-e1-graduation-rejudge/1", "evaluation_plan": str(grad_plan.path),
              "evaluation_plan_sha256": grad_plan.sha256, "training_plan_sha256": execution.sha256,
              "source_scores": str(src_scores), "boundaries": rows}
    _write(dst_root / "rejudge_report.json", report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src-scores", type=Path, required=True, help="OUT/eval/scores (read only)")
    parser.add_argument("--out", type=Path, required=True, help="fresh folder")
    parser.add_argument("--plan", type=Path, required=True, help="graduation evaluation plan")
    parser.add_argument("--training-plan", type=Path, required=True)
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--iterations", type=int, nargs="+", required=True)
    args = parser.parse_args(argv)
    report = rejudge_chain(args.src_scores, args.out, plan_path=args.plan, training_plan=args.training_plan,
                           approvals=args.approvals, iterations=args.iterations)
    for name, row in report["boundaries"].items():
        changed = sorted(k for k, v in row["cells"].items() if v["changed"])
        print(json.dumps({"boundary": name, "old": row["old_judgement"], "new": row["new_judgement"],
                          "p1": row["p1_judgment"], "changed_cells": changed,
                          "provenance_error": row["provenance_error"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
