"""Rejudge a completed EX-42 evaluation from immutable CPU artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from foothold_s2.ex42_eval_once import p1_score_from_measure
from foothold_s2.ex42_score import digest, measure


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rejudge(evaluation: Path, output: Path, *, plan_path: Path, approvals_path: Path) -> dict:
    evaluation, output = evaluation.resolve(strict=True), output.resolve()
    if output.exists():
        raise ValueError("EX-42 rejudgment requires a fresh output directory")
    old_score_path = evaluation / "ex42_score.json"
    old_p1_path = evaluation / "p1_score.json"
    receipt = _read(evaluation / "eval_receipt.json")
    old_score, old_p1 = _read(old_score_path), _read(old_p1_path)
    if (receipt.get("state") != "done" or old_p1.get("state") != "complete" or
            Path(receipt.get("score", "")).name != old_score_path.name or
            old_p1.get("measurement_sha256") != digest(old_score_path) or
            Path(receipt.get("p1_score", "")).name != old_p1_path.name):
        raise ValueError("EX-42 saved evaluation receipts differ")
    checkpoint = Path(old_score["checkpoint"])
    if digest(checkpoint) != old_score["checkpoint_sha256"] or old_p1["checkpoint_sha256"] != old_score["checkpoint_sha256"]:
        raise ValueError("EX-42 saved checkpoint SHA differs")
    score = measure(checkpoint, evaluation, expected_seed=receipt["eval_seed"],
                    expected_mesh_sha256=receipt["ex42_mesh"]["mesh_sha256"],
                    stage_id=old_p1["stage_id"])
    for key in ("map64", "stand", "axis_v2", "conditions"):
        if score[key] != old_score[key]:
            raise ValueError(f"EX-42 remeasurement differs from saved evidence: {key}")
    output.mkdir(parents=True)
    score_path = output / "ex42_score.json"
    score_path.write_text(json.dumps(score, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    p1 = p1_score_from_measure(score, checkpoint=checkpoint,
                               iteration=old_p1["checkpoint_iteration"],
                               plan_path=plan_path, approvals_path=approvals_path,
                               stage_id=old_p1["stage_id"], output=output)
    (output / "p1_score.json").write_text(json.dumps(p1, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    provenance = {"format": "foothold-ex42-e0-rejudge/1", "source_evaluation": str(evaluation),
                  "source_score_sha256": digest(old_score_path), "source_p1_sha256": digest(old_p1_path),
                  "new_score_sha256": digest(score_path), "new_p1_sha256": digest(output / "p1_score.json"),
                  "checkpoint_sha256": score["checkpoint_sha256"], "judgment": p1["judgment"]}
    (output / "rejudge_receipt.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--approvals", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rejudge(args.evaluation, args.output, plan_path=args.plan,
                             approvals_path=args.approvals), ensure_ascii=False))


if __name__ == "__main__":
    main()
