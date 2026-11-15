"""Fail-closed preflight for the proposed EX-42 multi-stage Kit canary.

This deliberately does not launch Kit. The current train entry has no bounded
2-3 update EX-42 rehearsal mode, and later stages do not yet have pinned
parents/entry validators. The script records every blocker in one pass so the
sequence can be enabled only after those contracts exist.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from foothold_s2.curriculum.ex42_prep import EX42Plan


SEQUENCE = ("E1F", "E2", "E3", "E4", "E5", "M", "E6a", "E6b")
TRAIN_ENTRY = Path(__file__).with_name("train_start.py")


def _declared_cli_flags(path: Path) -> set[str]:
    """Read literal argparse flags without importing the Kit-bearing entrypoint."""
    source = path.read_text(encoding="utf-8")
    return set(re.findall(r"add_argument\(\s*[\"'](--[a-zA-Z0-9_-]+)", source))


def build_report(*, plan_path: str | Path, approvals_path: str | Path,
                 updates_per_stage: int = 3, world_size: int = 2,
                 train_entry: str | Path = TRAIN_ENTRY,
                 startable_stages: set[str] | None = None,
                 approved_validators: set[str] | None = None) -> dict[str, Any]:
    if type(updates_per_stage) is not int or updates_per_stage not in (2, 3):
        raise ValueError("EX-42 Kit canary must be bounded to 2 or 3 updates per stage")
    if world_size != 2:
        raise ValueError("EX-42 Kit canary requires both training GPUs (two torchrun ranks)")

    plan = EX42Plan.load(plan_path)
    rows = {row["id"]: row for row in plan.document["stages"]}
    approvals_doc = _read_yaml(approvals_path)
    if startable_stages is None or approved_validators is None:
        from foothold_s2.scripts.ex42_training_entry import APPROVAL_VALIDATORS, E_STAGE_SPECS
        startable_stages = set(E_STAGE_SPECS)
        approved_validators = set(APPROVAL_VALIDATORS)
    flags = _declared_cli_flags(Path(train_entry))
    bounded_mode = "--ex42_stage_rehearsal_updates" in flags
    result = []
    for stage_id in SEQUENCE:
        row = rows.get(stage_id)
        approval_key = f"stage_{stage_id.lower()}_authorization"
        approval = approvals_doc.get(approval_key)
        blockers: list[str] = []
        if row is None:
            blockers.append("stage_missing_from_plan")
        elif not isinstance(row.get("parent"), dict):
            blockers.append("parent_checkpoint_not_pinned")
        if not isinstance(approval, dict) or approval.get("approved") is not True:
            blockers.append("stage_approval_missing")
        if stage_id not in approved_validators:
            blockers.append("stage_approval_validator_missing")
        if stage_id not in startable_stages:
            blockers.append("stage_training_entry_not_startable")
        if not bounded_mode:
            blockers.append("bounded_2_3_update_cli_missing")
        result.append({"stage_id": stage_id, "updates": updates_per_stage,
                       "rank_devices": ["cuda:0", "cuda:1"],
                       "state": "blocked" if blockers else "ready",
                       "blockers": blockers,
                       "command": None if blockers else "not_implemented"})

    blocked = [item["stage_id"] for item in result if item["state"] != "ready"]
    return {
        "format": "foothold-ex42-kit-sequence-rehearsal-preflight/1",
        "plan_sha256": plan.sha256,
        "stage_order": list(SEQUENCE),
        "updates_per_stage": updates_per_stage,
        "world_size": world_size,
        "devices": ["cuda:0", "cuda:1"],
        "stages": result,
        "state": "blocked" if blocked else "ready",
        "blocked_stages": blocked,
        "kit_started": False,
        "training_started": False,
        "reason": ("No bounded EX-42 stage rehearsal entrypoint exists; this report is preflight only."
                   if not bounded_mode else "Stage readiness is not launch authorization."),
    }


def _read_yaml(path: str | Path) -> dict[str, Any]:
    import yaml
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("EX-42 approvals must be a YAML mapping")
    return value


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=str(Path(__file__).parents[1] / "curriculum/ex42-prep.yaml"))
    parser.add_argument("--approvals", default=str(Path(__file__).parents[1] / "curriculum/ex42-approvals.yaml"))
    parser.add_argument("--updates-per-stage", type=int, default=3)
    parser.add_argument("--world-size", type=int, default=2)
    parser.add_argument("--execute", action="store_true",
                        help="Reserved. Refuses until an audited bounded Kit entrypoint exists.")
    args = parser.parse_args(argv)
    report = build_report(plan_path=args.plan, approvals_path=args.approvals,
                          updates_per_stage=args.updates_per_stage, world_size=args.world_size)
    if args.execute:
        report["state"] = "blocked"
        report["blocked_stages"] = list(SEQUENCE)
        report["reason"] = "execution is disabled: no approved bounded EX-42 rehearsal path"
        report["kit_started"] = False
        report["training_started"] = False
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2 if report["state"] != "ready" or args.execute else 0


if __name__ == "__main__":
    raise SystemExit(main())
