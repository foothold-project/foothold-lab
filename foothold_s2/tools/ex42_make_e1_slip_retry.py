"""Write the E1 foot_slip retry cell: the shipped EX-42 plan and approvals with ONE change in what E1 trains.

The finished run EX-42-B-E1_20261111_114505 (foot_slip weight 0.0) stays the control. The retry has the same parent
(E0 m250, sha 680c820b...), the same stage rows and the same evaluation; the E1 row only gains
`reward_overrides: {foot_slip: -0.25}` and `retry_of` (which names the control). The retry has its own approvals file,
and its E1 cell is closed (`approved: false`) until the team lead fills it. Nothing here starts anything.

    python -m foothold_s2.tools.ex42_make_e1_slip_retry [--check]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import sys
from pathlib import Path

import yaml

CURRICULUM = Path(__file__).resolve().parents[1] / "curriculum"
BASE_PLAN, BASE_APPROVALS = "ex42-prep.yaml", "ex42-approvals.yaml"
RETRY_PLAN, RETRY_APPROVALS = "ex42-e1-slip-prep.yaml", "ex42-e1-slip-approvals.yaml"
FOOT_SLIP_WEIGHT = -0.25                       # assumption (planner REVIEW-EX42-D44-SLIP-AND-OPTIONS-1111 s4.1), a 50-update Kit check confirms it
CONTROL = {"control_run": "EX-42-B-E1_20261111_114505",
           "control_plan_sha256": "e542961d9c65a588ae893b81a8d07d39cd66ca068f2f118410c3e2d1d7a2d982",
           "control_parent_sha256": "680c820b73646d9c11f62f184fd35e6cc096ffd04681951d542b2b4b472d779e",
           "control_foot_slip_weight": 0.0,
           "changes": "foot_slip weight 0.0 -> -0.25, nothing else"}


def _dump(document) -> str:
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=10 ** 6)


def build(curriculum: Path = CURRICULUM) -> tuple[str, str]:
    """(plan text, approvals text) of the retry cell, derived from the shipped pair."""
    plan = yaml.safe_load((curriculum / BASE_PLAN).read_text(encoding="utf-8-sig"))
    approvals = yaml.safe_load((curriculum / BASE_APPROVALS).read_text(encoding="utf-8-sig"))
    cell = approvals["stage_e1_authorization"]
    approvals["stage_e1_authorization"] = {
        **{k: v for k, v in cell.items() if k not in ("approved", "decision_id", "approved_at", "approver", "decision_source")},
        "approved": False, "decision_id": None, "approved_at": None, "approver": None, "decision_source": None,
        "retry_of": dict(CONTROL)}
    approvals_text = _dump(approvals)
    row = next(r for r in plan["stages"] if r["id"] == "E1")
    if row["parent"]["sha256"] != CONTROL["control_parent_sha256"]:
        raise ValueError("the shipped E1 parent is no longer the control run's parent")
    row["reward_overrides"] = {"foot_slip": FOOT_SLIP_WEIGHT}
    row["retry_of"] = copy.deepcopy(CONTROL)
    plan["approval_file"] = RETRY_APPROVALS
    plan["stage_zero"]["approval_sha256"] = hashlib.sha256(approvals_text.encode("utf-8")).hexdigest()
    return _dump(plan), approvals_text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="only compare the committed files with a fresh build")
    args = parser.parse_args(argv)
    plan_text, approvals_text = build()
    files = {CURRICULUM / RETRY_PLAN: plan_text, CURRICULUM / RETRY_APPROVALS: approvals_text}
    if args.check:
        stale = [p.name for p, text in files.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]
        print("stale: " + ", ".join(stale) if stale else "retry files are current")
        return 1 if stale else 0
    for path, text in files.items():
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
