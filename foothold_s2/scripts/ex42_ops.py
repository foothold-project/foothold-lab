"""CPU-only EX-42 operations gate. It never imports Kit or starts training."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from foothold_s2.curriculum.ex42_prep import EX42Plan


REPO = Path(__file__).resolve().parents[2]
DEFAULT_TABLE = REPO / "foothold_s2/curriculum/ex42-prep.yaml"
DEFAULT_APPROVALS = REPO / "foothold_s2/curriculum/ex42-approvals.yaml"


def inspect_fixed_source(repo: str | Path, *, expected_head: str | None = None) -> dict[str, Any]:
    """Require a detached, clean worktree and optionally its exact expected HEAD."""
    root = Path(repo).resolve(strict=True)

    def git(*args: str) -> str:
        proc = subprocess.run(["git", "-C", str(root), *args], check=False,
                              text=True, encoding="utf-8", errors="replace",
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode:
            raise ValueError(f"EX-42 source check failed: {proc.stderr.strip()}")
        return proc.stdout.strip()

    top = Path(git("rev-parse", "--show-toplevel")).resolve(strict=True)
    head = subprocess.run(["git", "-C", str(top), "rev-parse", "HEAD"], check=False,
                          text=True, encoding="utf-8", errors="replace",
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if head.returncode:
        raise ValueError("EX-42 source HEAD cannot be read")
    actual_head = head.stdout.strip()
    symbolic = subprocess.run(["git", "-C", str(top), "symbolic-ref", "--quiet", "--short", "HEAD"],
                              check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if symbolic.returncode == 0:
        raise ValueError("EX-42 source worktree must be detached")
    if symbolic.returncode != 1:
        raise ValueError("EX-42 source detached state cannot be established")
    if git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("EX-42 source worktree is not clean")
    if expected_head is not None and actual_head != expected_head:
        raise ValueError("EX-42 source HEAD differs from expected commit")
    return {"root": str(top), "head": actual_head, "detached": True, "clean": True}


def verify_import_boundary() -> dict[str, int]:
    """AST-check gate modules and reject import-time simulator bootstrap."""
    paths = [Path(__file__).resolve(), REPO / "foothold_s2/curriculum/ex42_prep.py"]
    forbidden = ("isaacsim", "isaaclab.app", "omni.kit")
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            if any(name == bad or name.startswith(bad + ".") for bad in forbidden for name in names):
                raise ValueError(f"EX-42 gate must not import Kit at module scope: {path}")
            if module and any(module == bad or module.startswith(bad + ".") for bad in forbidden):
                raise ValueError(f"EX-42 gate must not import Kit at module scope: {path}")
    return {"ast_files": len(paths), "kit_imports": 0}


def ops_check(table: str | Path = DEFAULT_TABLE,
              approvals: str | Path = DEFAULT_APPROVALS, *,
              graduation: str | Path | None = None,
              terrain_manifest: str | Path | None = None,
              source_root: str | Path | None = None,
              expected_head: str | None = None) -> dict[str, Any]:
    plan = EX42Plan.load(table)
    blockers = plan.launch_blockers(approvals, graduation, terrain_manifest)
    blockers.append("runtime_integration_pending")
    source = None
    if source_root is not None:
        source = inspect_fixed_source(source_root, expected_head=expected_head)
    elif expected_head is not None:
        blockers.append("source_root_missing")
    import_check = verify_import_boundary()
    return {
        "state": "blocked" if blockers else "ready",
        "plan_sha256": plan.sha256,
        "source": source,
        "blockers": list(dict.fromkeys(blockers)),
        "production_launch_allowed": False,
        "kit_started": False,
        "training_started": False,
        "import_check": import_check,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EX-42 CPU operations/readiness gate")
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--approvals", type=Path, default=DEFAULT_APPROVALS)
    parser.add_argument("--graduation", type=Path)
    parser.add_argument("--terrain-manifest", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--expected-head")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--ops-check", action="store_true")
    modes.add_argument("--rehearsal", action="store_true")
    modes.add_argument("--production", action="store_true")
    parser.add_argument("--production-launch-approved", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = ops_check(args.table, args.approvals, graduation=args.graduation,
                           terrain_manifest=args.terrain_manifest,
                           source_root=args.source_root, expected_head=args.expected_head)
    except (OSError, ValueError) as exc:
        result = {"state": "blocked", "blockers": [str(exc)],
                  "production_launch_allowed": False, "kit_started": False,
                  "training_started": False}
    if args.rehearsal:
        result["blockers"].append("rehearsal_runtime_not_integrated")
        result["state"] = "blocked"
        result["mode"] = "rehearsal_plan_only"
    if args.production:
        result["blockers"].append("production_launch_not_implemented")
        if not args.production_launch_approved:
            result["blockers"].append("explicit_lead_approval_missing")
        result["state"] = "blocked"
        result["mode"] = "production_rejected"
    if args.ops_check:
        result["mode"] = "ops_check"
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
