"""CPU-side EX-42 checkpoint stage identity for the score watcher."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import read_approved_dr_schedule


def read_transition_rows(path: str | Path | None) -> tuple[dict[str, Any], ...]:
    if path is None:
        return ()
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"EX-42 transition log line {number} is invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"EX-42 transition log line {number} is not an object")
        rows.append(row)
    return tuple(rows)


def checkpoint_stage_context(plan: EX42Plan, approvals_path: str | Path,
                             local_iteration: int, *,
                             transition_rows: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    """Resolve score attribution from the same plan and approved DR rows as transition runtime."""
    scales, decision_id = read_approved_dr_schedule(approvals_path, plan.runtime_stage_ids)
    stage_id = plan.stage_id_at(local_iteration, transitions=tuple(transition_rows))
    stage = next(row for row in plan.runtime_stages if row["id"] == stage_id)
    return {
        "state": "ready",
        "checkpoint_iteration": local_iteration,
        "stage_id": stage_id,
        "dr_scale": scales[stage_id],
        "dr_decision_id": decision_id,
        "stage_config": stage,
        "plan_sha256": plan.sha256,
        "stage_sequence": list(plan.runtime_stage_ids),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--approvals", type=Path, required=True)
    parser.add_argument("--checkpoint-iteration", type=int, required=True)
    parser.add_argument("--application-log", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = EX42Plan.load(args.table)
        result = checkpoint_stage_context(
            plan, args.approvals, args.checkpoint_iteration,
            transition_rows=read_transition_rows(args.application_log),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
