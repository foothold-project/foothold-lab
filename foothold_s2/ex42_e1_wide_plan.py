"""Derive a separate C1 evaluation policy without changing the pinned training plan."""
from __future__ import annotations

import argparse
import copy
import json
import shutil
from pathlib import Path

import yaml

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.eval.map_mode_cells import E1_WIDE_ENDPOINT_COMMANDS, E1_WIDE_FIXED_COMMANDS
from foothold_s2.eval.map_mode_cells import commands as command_suite


def widened_contract(source: dict) -> dict:
    evaluation = source["evaluation"]
    levels = evaluation["fixed_levels"]
    if levels != [3, 6, 9] or evaluation["promotion"]["window_episodes"] != 64:
        raise ValueError("C1 source fixed levels or denominator differs")
    return {
        "format": "foothold-ex42-e1-widened/2", "active": True,
        "fixed_forward_levels": levels,
        "fixed_commands": list(E1_WIDE_FIXED_COMMANDS),
        "endpoint_commands": list(E1_WIDE_ENDPOINT_COMMANDS),
        "judge_modes": ["eval_gt", "eval_pred"], "record_modes": ["probe_prop_only"],
        "fixed_forward_roles": {3: "judge_if_exposed", 6: "judge_if_exposed",
                                9: "record_only_pending_decision"},
        "endpoint_roles": {case: "judge" if case in ("side+0.8", "side-0.8")
                           else "record_only" for case in E1_WIDE_ENDPOINT_COMMANDS},
        "fixed_other_role": "record_only", "fixed_off_role": "record_only",
        "reached_level_success_min": evaluation["promotion"]["success_min"],
        "off_survival": {
            "role": "two_window_watch", "map64_commands": list(command_suite("extended")),
            "low_forward_levels": [0, 5], "low_forward_commands": ["fwd0.1", "fwd0.2"],
            "survival_min": evaluation["promotion"]["survival_min"],
            "valid_min": evaluation["promotion"]["window_episodes"],
        },
    }


def write_evaluation_plan(source_path: Path, destination: Path, expected_source_sha256: str) -> EX42Plan:
    source = EX42Plan.load(source_path)
    if source.sha256 != expected_source_sha256 or "e1_widened" in source.document["evaluation"]:
        raise ValueError("C1 source training plan SHA or evaluation scope differs")
    destination = Path(destination).absolute()
    root = source.path.parents[2]
    if destination.is_relative_to(root) or destination.exists() or destination.parent.exists():
        raise ValueError("C1 evaluation plan needs a fresh output outside the source checkout")
    cfg = widened_contract(source.document)
    # A single insertion preserves every training byte and lets the parsed
    # before/after check reject any field outside evaluation.e1_widened.
    marker = "  directions:\n"
    text = source.path.read_text(encoding="utf-8")
    if text.count(marker) != 1:
        raise ValueError("C1 source evaluation insertion point differs")
    block = yaml.safe_dump({"e1_widened": cfg}, sort_keys=False, allow_unicode=True)
    block = "".join("  " + line for line in block.splitlines(keepends=True))
    text = text.replace(marker, block + marker)
    destination.parent.mkdir(parents=True)
    for path in source.path.parent.rglob("*"):
        if path.is_file() and path.suffix in (".yaml", ".yml", ".json"):
            if path.is_symlink() or not path.resolve().is_relative_to(source.path.parent):
                raise ValueError("C1 curriculum dependency escapes its source directory")
            target = destination.parent / path.relative_to(source.path.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    destination.write_text(text, encoding="utf-8")
    policy = EX42Plan.load(destination)
    validate_evaluation_scope(source.path, policy.path)
    from foothold_s2.ex42_e1_wide import contract
    contract(policy.document)
    if EX42Plan.load(source.path).sha256 != source.sha256:
        raise ValueError("C1 source training plan changed during derivation")
    return policy


def validate_evaluation_scope(source_path: Path, evaluation_path: Path) -> None:
    source, policy = EX42Plan.load(source_path), EX42Plan.load(evaluation_path)
    before, after = copy.deepcopy(source.document), copy.deepcopy(policy.document)
    if "e1_widened" in before["evaluation"]:
        raise ValueError("C1 training plan already contains an evaluation override")
    cfg = widened_contract(before)
    if after["evaluation"].pop("e1_widened", None) != cfg or before != after:
        raise ValueError("C1 evaluation plan differs outside approved evaluation fields")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    plan = write_evaluation_plan(args.source, args.out, args.expected_source_sha256)
    print(json.dumps({"state": "complete", "evaluation_plan": str(plan.path),
                      "evaluation_plan_sha256": plan.sha256,
                      "source_sha256": args.expected_source_sha256}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
