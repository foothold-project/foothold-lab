"""CPU-only EX-42 operations gate. It never imports Kit or starts training."""

from __future__ import annotations

import argparse
import ast
import importlib
import json
from pathlib import Path
import re
import subprocess
from pathlib import PureWindowsPath
from typing import Any

from foothold_s2.curriculum.ex42_prep import EX42Plan, RUNTIME_STAGE_IDS
from foothold_s2.curriculum.ex42_runtime import read_approved_dr_schedule
from foothold_s2.experiment_registry import load_experiment, source_path
from foothold_s2.machine_profile import load_machine_profile, machine_path


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
    paths = [Path(__file__).resolve(), REPO / "foothold_s2/curriculum/ex42_prep.py",
             REPO / "foothold_s2/curriculum/ex42_runtime.py",
             REPO / "foothold_s2/ex42_score_watch.py"]
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


def verify_train_entry_contract() -> dict[str, Any]:
    """Build the real train_start + installed RSL parser without running it."""
    from foothold_s2.ex41_start_preflight import train_parser_from_source

    machine = load_machine_profile()
    parser = train_parser_from_source(REPO)
    required = {"--task", "--agent", "--num_envs", "--seed", "--max_iterations", "--resume_from"}
    absent = sorted(required - set(parser._option_string_actions))
    if absent:
        raise ValueError(f"EX-42 train entry is missing parser flags: {absent}")
    argv = ["--task", "FootholdS2-Go2-S2-SB-v0", "--agent", "s2_sb",
            "--num_envs", "3072", "--seed", "42", "--max_iterations", "1",
            "--resume_from", str(machine_path("mai_tmp_root") / "runner/known-parent/model_6000.pt"),
            "--headless", "--device", "cuda:0"]
    known, unknown = parser.parse_known_args(argv)
    if (known.task != "FootholdS2-Go2-S2-SB-v0" or known.num_envs != 3072
            or known.max_iterations != 1 or known.resume_from is None
            or unknown != ["--headless", "--device", "cuda:0"]):
        raise ValueError("EX-42 candidate train argv differs from the real parser contract")
    return {"parser": "train_start declarations + installed RSL-RL cli_args.py",
            "machine_profile": machine["machine_id"],
            "machine_profile_path": machine["profile"],
            "known_argv": argv[:-3], "applauncher_passthrough": unknown,
            "training_started": False}


def verify_env_cfg_import(task_id: str = "FootholdS2-Go2-S2-SB-v0") -> dict[str, Any]:
    """Resolve the registered env class and attempt its real Python import, without Kit launch."""
    import gymnasium as gym

    importlib.import_module("foothold_s2.sb_tasks")
    spec = gym.spec(task_id)
    entry = spec.kwargs.get("env_cfg_entry_point")
    if not isinstance(entry, str) or ":" not in entry:
        raise ValueError("EX-42 registered task has no environment cfg entry point")
    module_name, class_name = entry.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except (ImportError, RuntimeError) as exc:
        return {"task_id": task_id, "entry": entry, "imported": False,
                "error_type": type(exc).__name__, "error": str(exc), "kit_started": False}
    if not hasattr(module, class_name):
        raise ValueError(f"EX-42 registered environment class is missing: {entry}")
    return {"task_id": task_id, "entry": entry, "imported": True,
            "class": class_name, "kit_started": False}


def validate_rehearsal_plan(output_root: str, stage_updates: list[int], *,
                            source_root: str | Path, expected_head: str) -> dict[str, Any]:
    """Validate an isolated, bounded rehearsal plan without creating or launching it."""
    output_win = PureWindowsPath(output_root)
    expected_win = PureWindowsPath(str(machine_path("mai_tmp_root")) + "/runner")
    expected_parent_label = expected_win.as_posix()
    if output_win.is_absolute() and expected_win.is_absolute():
        output_name, output_parent = output_win.name, output_win.parent
        output_value = str(output_win)
        parent_matches = output_parent == expected_win
        exists = Path(output_root).exists()
    else:
        output_native = Path(output_root).resolve()
        expected_parent = (machine_path("mai_tmp_root") / "runner").resolve()
        expected_parent_label = str(expected_parent)
        output_name, output_parent = output_native.name, output_native.parent
        output_value = str(output_native)
        parent_matches = output_parent == expected_parent
        exists = output_native.exists()
    if (not parent_matches
            or not re.fullmatch(r"ex42_rehearsal_[0-9]{8}_[0-9]{6}", output_name)):
        raise ValueError(f"EX-42 rehearsal output must be under {expected_parent_label}")
    if (len(stage_updates) != len(RUNTIME_STAGE_IDS)
            or any(type(value) is not int or value < 1 for value in stage_updates)):
        raise ValueError("EX-42 rehearsal requires one positive update count for each of eleven runtime stages")
    source = inspect_fixed_source(source_root, expected_head=expected_head)
    if exists:
        raise ValueError("EX-42 rehearsal output must be new")
    return {"output_root": output_value, "source": source,
            "stage_ids": list(RUNTIME_STAGE_IDS),
            "stage_updates": stage_updates, "training_started": False, "kit_started": False}


def ops_check(table: str | Path = DEFAULT_TABLE,
              approvals: str | Path = DEFAULT_APPROVALS, *,
              graduation: str | Path | None = None,
              terrain_manifest: str | Path | None = None,
              source_root: str | Path | None = None,
              expected_head: str | None = None) -> dict[str, Any]:
    plan = EX42Plan.load(table)
    blockers = plan.launch_blockers(approvals, graduation, terrain_manifest)
    blockers.append("runtime_integration_pending")
    definition = load_experiment("EX-42")
    values = definition.get("operational_values", {})
    parent = values.get("parent", {})
    training = values.get("training", {})
    if (parent != plan.document["stage_zero"]["parent"]
            or training.get("initial_stage") != plan.document["stage_zero"]["id"]
            or training.get("initial_stage_updates") != plan.document["stage_zero"]["maximum_updates"]):
        blockers.append("stage_zero_definition_mismatch")
    try:
        stage_ids = plan.runtime_stage_ids
        read_approved_dr_schedule(approvals, stage_ids)
    except (OSError, KeyError, TypeError, ValueError):
        blockers.append("stage_dr_schedule_unapproved")
    source = None
    if source_root is not None:
        source = inspect_fixed_source(source_root, expected_head=expected_head)
    elif expected_head is not None:
        blockers.append("source_root_missing")
    import_check = verify_import_boundary()
    train_entry = verify_train_entry_contract()
    env_import = verify_env_cfg_import(plan.document["environment"]["task_id"])
    if not env_import["imported"]:
        blockers.append("environment_import_unavailable")
    return {
        "state": "blocked" if blockers else "ready",
        "plan_sha256": plan.sha256,
        "source": source,
        "blockers": list(dict.fromkeys(blockers)),
        "production_launch_allowed": False,
        "kit_started": False,
        "training_started": False,
        "import_check": import_check,
        "train_entry": train_entry,
        "environment_import": env_import,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EX-42 CPU operations/readiness gate")
    parser.add_argument("--exp", required=True, help="experiment definition ID in experiments/<ID>.yaml")
    parser.add_argument("--table", type=Path)
    parser.add_argument("--approvals", type=Path)
    parser.add_argument("--graduation", type=Path)
    parser.add_argument("--terrain-manifest", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--expected-head")
    parser.add_argument("--rehearsal-output")
    parser.add_argument("--rehearsal-stage-updates", type=int, nargs=len(RUNTIME_STAGE_IDS))
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--ops-check", action="store_true")
    modes.add_argument("--rehearsal", action="store_true")
    modes.add_argument("--production", action="store_true")
    parser.add_argument("--production-launch-approved", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        definition = load_experiment(args.exp)
        table = args.table or source_path(definition, "curriculum")
        approvals = args.approvals or source_path(definition, "approvals")
        result = ops_check(table, approvals, graduation=args.graduation,
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
        try:
            if args.rehearsal_output is None or args.rehearsal_stage_updates is None:
                raise ValueError("EX-42 rehearsal needs an isolated output root and ten stage lengths")
            if args.source_root is None or args.expected_head is None:
                raise ValueError("EX-42 rehearsal needs a fixed source root and expected HEAD")
            result["rehearsal_plan"] = validate_rehearsal_plan(
                args.rehearsal_output, args.rehearsal_stage_updates,
                source_root=args.source_root, expected_head=args.expected_head)
        except (OSError, ValueError) as exc:
            result["blockers"].append(str(exc))
    if args.production:
        result["blockers"].append("production_launch_not_implemented")
        if args.source_root is None or args.expected_head is None:
            result["blockers"].append("fixed_source_identity_required")
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
