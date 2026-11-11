"""Run one queued EX-42 P1 evaluator and publish a success-only dependency marker."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def run_item(*, evaluator_argv: list[str], iteration: int, marker: str | Path,
             popen=subprocess.run) -> int:
    if not evaluator_argv or not isinstance(evaluator_argv, list) or not all(
            isinstance(value, str) for value in evaluator_argv):
        raise ValueError("EX-42 P1 evaluator argv must be a non-empty string list")
    marker = Path(marker)
    out = Path(evaluator_argv[evaluator_argv.index("--out") + 1])
    result = popen(evaluator_argv, check=False)
    if result.returncode != 0:
        return result.returncode
    receipt_path = out / "eval_receipt.json"
    score_path = out / "p1_score.json"
    measurement_path = out / "ex42_score.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    score = json.loads(score_path.read_text(encoding="utf-8-sig"))
    measurement = json.loads(measurement_path.read_text(encoding="utf-8-sig"))
    if (receipt.get("state") != "done" or score.get("state") != "complete"
            or score.get("stage_id") != "E1" or score.get("checkpoint_iteration") != iteration
            or measurement.get("stage_id") != "E1"
            # ex42_score.json carries no checkpoint_iteration (real E1 m250, 11/11 19:2x); the checkpoint SHA binds it
            or measurement.get("checkpoint_iteration", iteration) != iteration
            or score.get("checkpoint_sha256") != measurement.get("checkpoint_sha256")):
        raise ValueError(f"EX-42 E1 m{iteration} evaluator returned rc0 without matching complete evidence")
    marker.parent.mkdir(parents=True, exist_ok=True)
    tmp = marker.with_name(f"{marker.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"state": "done", "iteration": iteration,
                               "checkpoint_sha256": score["checkpoint_sha256"]},
                              sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, marker)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--eval-argv-json", required=True)
    args = parser.parse_args(argv)
    try:
        evaluator_argv = json.loads(args.eval_argv_json)
        return run_item(evaluator_argv=evaluator_argv, iteration=args.iteration,
                        marker=args.marker)
    except (OSError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        print(f"EX42_P1_QUEUE_ITEM_ERROR {exc}", file=sys.stderr, flush=True)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
