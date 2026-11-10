"""CPU preflight for EX-42. Production launch is deliberately fail-closed."""

from __future__ import annotations

import argparse
import ast
import importlib
import json
from pathlib import Path
import sys

from foothold_s2.curriculum.ex42_prep import EX42Plan


REPO = Path(__file__).resolve().parents[2]
DEFAULT_TABLE = REPO / "foothold_s2/curriculum/ex42-prep.yaml"
DEFAULT_APPROVALS = REPO / "foothold_s2/curriculum/ex42-approvals.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EX-42 design and launch-gate preflight")
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--approvals", type=Path, default=DEFAULT_APPROVALS)
    parser.add_argument("--e0-parent-manifest", "--graduation", dest="graduation", type=Path)
    parser.add_argument("--terrain-manifest", type=Path)
    parser.add_argument("--check-env-registration", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--production-launch-approved", action="store_true")
    return parser


def verify_env_registration(task_id: str) -> dict[str, str]:
    """Import the project's actual Gym registration without importing Kit."""
    import gymnasium as gym

    importlib.import_module("foothold_s2.sb_tasks")
    spec = gym.spec(task_id)
    entry = spec.kwargs.get("env_cfg_entry_point")
    if not isinstance(entry, str) or ":" not in entry:
        raise ValueError("registered task has no env_cfg_entry_point")
    module_name, class_name = entry.split(":", 1)
    module_path = REPO.joinpath(*module_name.split(".")).with_suffix(".py")
    if not module_path.is_file():
        raise ValueError(f"registered env config class is missing: {class_name}")
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    if class_name not in classes:
        raise ValueError(f"registered env config class is missing: {class_name}")
    return {"task_id": spec.id, "env_cfg_module": module_name,
            "env_cfg_class": class_name, "env_cfg_import": "AST-checked; Isaac/pxr import not attempted"}


def verify_import_boundary() -> dict[str, int]:
    """AST-parse startup modules and reject Kit bootstrap at import time."""
    paths = [REPO / "foothold_s2/curriculum/ex42_prep.py", Path(__file__)]
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    forbidden = {"isaacsim", "isaaclab.app", "omni.kit"}
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names if alias.name in forbidden)
        elif isinstance(node, ast.ImportFrom) and node.module in forbidden:
            found.add(node.module)
    if found:
        raise ValueError(f"EX-42 preflight must not bootstrap Kit: {sorted(found)}")
    return {"ast_files": len(paths), "kit_imports_at_module_scope": 0}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = EX42Plan.load(args.table)
    blockers = plan.launch_blockers(args.approvals, args.graduation, args.terrain_manifest)
    if args.production_launch_approved:
        blockers.append("EX-42 runtime and Kit approval are not part of this preparation task")
    env = None
    if args.check_env_registration:
        env = verify_env_registration(plan.document["environment"]["task_id"])
    ast_result = verify_import_boundary()
    output = {"state": "preparation_validated" if not blockers else "blocked",
              "table_sha256": plan.sha256,
              "stage_ids": [row["id"] for row in plan.document["stages"]],
              "score_cells": plan.document["evaluation"]["total_cells"],
              "blockers": blockers, "env_registration": env,
              "import_boundary": ast_result}
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if args.dry_run else 2


if __name__ == "__main__":
    raise SystemExit(main())
