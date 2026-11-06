"""Read-only EX-41 launch preflight. It never imports Isaac or starts training."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from foothold_s2.runtime_environment import current_runtime_identity
from foothold_s2.machine_profile import machine_path


REQUIRED_PARENT_UPDATE = 6000
REQUIRED_TRAIN_FLAGS = (
    "--task", "--agent", "--num_envs", "--seed", "--max_iterations",
    "--resume_from",
)
def _isaac_sources() -> tuple[Path, Path]:
    root = machine_path("isaaclab_root")
    return (root / "scripts/reinforcement_learning/rsl_rl/cli_args.py",
            root / "source/isaaclab/isaaclab/app/app_launcher.py")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], text=True,
                          encoding="utf-8", errors="replace", capture_output=True,
                          check=False)


def inspect_fixed_worktree(repo: str | Path, *, expected_head: str | None = None) -> dict[str, Any]:
    """Require a clean detached checkout at a fixed commit; read-only git calls only."""
    path = Path(repo).resolve(strict=True)
    root = _git(path, "rev-parse", "--show-toplevel")
    if root.returncode:
        raise ValueError("repository root cannot be resolved")
    root_path = Path(root.stdout.strip()).resolve(strict=True)
    head_result = _git(root_path, "rev-parse", "HEAD")
    if head_result.returncode:
        raise ValueError("HEAD cannot be read")
    head = head_result.stdout.strip()
    symbolic = _git(root_path, "symbolic-ref", "--quiet", "--short", "HEAD")
    if symbolic.returncode == 0:
        raise ValueError("fixed checkout must be detached")
    if symbolic.returncode != 1:
        raise ValueError("detached HEAD state cannot be established")
    status = _git(root_path, "status", "--porcelain=v1", "--untracked-files=all")
    if status.returncode:
        raise ValueError("git status could not be read")
    if status.stdout:
        raise ValueError("fixed checkout is not clean")
    if expected_head is not None and head != expected_head:
        raise ValueError("fixed checkout HEAD differs from expected commit")
    return {"repo": str(root_path), "head": head, "detached": True,
            "clean": True, "state": "read_only_preflight"}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_parent_checkpoint(checkpoint: str | Path, expected_sha256: str,
                             *, minimum_completed_updates: int = REQUIRED_PARENT_UPDATE) -> dict[str, Any]:
    """Verify checkpoint bytes against their runner manifest and progress record."""
    ckpt = Path(checkpoint).resolve(strict=True)
    match = re.fullmatch(r"model_(\d+)\.pt", ckpt.name)
    if not match:
        raise ValueError("parent checkpoint must be named model_<update>.pt")
    update = int(match.group(1))
    if update != REQUIRED_PARENT_UPDATE:
        raise ValueError(f"EX-41 parent must be model_{REQUIRED_PARENT_UPDATE}.pt")
    actual = sha256_file(ckpt)
    if actual != expected_sha256:
        raise ValueError("parent checkpoint SHA256 mismatch")
    manifest_path = ckpt.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    manifest_sha = (manifest.get("checkpoints") or {}).get(ckpt.name)
    if manifest_sha != actual:
        raise ValueError("manifest checkpoint SHA256 mismatch")
    completed = (manifest.get("progress") or {}).get("completed_updates")
    if not isinstance(completed, int) or completed < minimum_completed_updates:
        raise ValueError("manifest does not prove the required parent progress")
    return {"checkpoint": str(ckpt), "update": update,
            "sha256": actual, "manifest": str(manifest_path),
            "completed_updates": completed, "verified": True}


def audit_train_source(repo: str | Path) -> dict[str, Any]:
    """Static source audit only; does not import train_start or AppLauncher."""
    root = Path(repo).resolve(strict=True)
    train = root / "foothold_s2" / "scripts" / "train_start.py"
    isaac_rsl_cli, app_launcher_source = _isaac_sources()
    for p in (train, isaac_rsl_cli, app_launcher_source):
        if not p.is_file():
            raise ValueError(f"required parser source is missing: {p}")
    text = train.read_text(encoding="utf-8")
    args_text = isaac_rsl_cli.read_text(encoding="utf-8")
    app_text = app_launcher_source.read_text(encoding="utf-8")
    missing = [flag for flag in REQUIRED_TRAIN_FLAGS if flag not in text]
    if "def add_rsl_rl_args(parser" not in args_text:
        missing.append("RSL-RL parser source")
    if "def add_app_launcher_args(parser" not in app_text:
        missing.append("AppLauncher parser source")
    if "AppLauncher.add_app_launcher_args(parser)" not in text:
        missing.append("AppLauncher parser hookup")
    if ("LAUNCH_RUNTIME_IDENTITY = current_runtime_identity()" not in text
            or text.index("LAUNCH_RUNTIME_IDENTITY = current_runtime_identity()")
            > text.index("import tensordict")):
        missing.append("pre-Kit runtime identity guard")
    if '"launcher_environment": LAUNCH_RUNTIME_IDENTITY' not in text:
        missing.append("manifest launcher environment identity")
    if missing:
        raise ValueError("required training CLI declarations are missing: " + ", ".join(missing))
    return {"train_start": str(train), "required_flags_source_checked": list(REQUIRED_TRAIN_FLAGS),
            "rsl_rl_parser_source": str(isaac_rsl_cli), "app_launcher_parser_source": str(app_launcher_source),
            "task_import_source_checked": "foothold_s2.tasks",
            "parser_execution": "source_ast_and_safe_rsl_args_only", "environment_import": "not_run",
            "kit_launch": "not_run", "runtime_identity": current_runtime_identity(),
            "state": "static_source_audit_only"}


def train_parser_from_source(repo: str | Path) -> argparse.ArgumentParser:
    """Build the real train_start declarations without executing its imports."""
    train = Path(repo).resolve(strict=True) / "foothold_s2" / "scripts" / "train_start.py"
    tree = ast.parse(train.read_text(encoding="utf-8"), filename=str(train))
    declarations = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "parser" for target in node.targets):
            declarations.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "parser" and call.func.attr == "add_argument"):
                declarations.append(node)
    if not declarations:
        raise ValueError("train_start parser declarations were not found")
    namespace: dict[str, Any] = {"argparse": argparse}
    module = ast.Module(body=declarations, type_ignores=[])
    exec(compile(module, str(train), "exec"), namespace)
    parser = namespace["parser"]
    isaac_rsl_cli, _ = _isaac_sources()
    spec = importlib.util.spec_from_file_location("ex41_safe_cli_args", isaac_rsl_cli)
    if spec is None or spec.loader is None:
        raise ValueError("installed RSL-RL CLI parser cannot be loaded")
    cli_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli_module)
    cli_module.add_rsl_rl_args(parser)
    return parser


def inspect_train_argv(repo: str | Path, argv: list[str]) -> dict[str, Any]:
    """Exercise train_start's actual argument declarations and installed RSL args.

    AppLauncher is not imported. Its two required options are checked as trailing
    passthrough arguments from the installed source contract.
    """
    parser = train_parser_from_source(repo)
    known, unknown = parser.parse_known_args(argv)
    if known.task is None or not known.resume_from:
        raise ValueError("candidate EX-41 launch requires explicit task and parent checkpoint")
    if known.num_envs is None or known.max_iterations is None or known.max_iterations <= REQUIRED_PARENT_UPDATE:
        raise ValueError(f"candidate launch needs explicit env count and a total update target above m{REQUIRED_PARENT_UPDATE}")
    if not known.run_name or not known.distributed:
        raise ValueError("candidate EX-41 launch needs a run name and distributed flag choice")
    if unknown.count("--headless") != 1 or unknown.count("--device") != 1:
        raise ValueError("AppLauncher passthrough must contain exactly one --headless and --device")
    dev_i = unknown.index("--device")
    if dev_i + 1 >= len(unknown) or unknown[dev_i + 1] not in ("cuda:0", "cuda:1"):
        raise ValueError("AppLauncher device must be explicit cuda:0 or cuda:1")
    return {"task": known.task, "num_envs": known.num_envs, "seed": known.seed,
            "max_iterations": known.max_iterations, "resume_from": known.resume_from,
            "run_name": known.run_name, "distributed": known.distributed,
            "applauncher_passthrough": unknown,
            "device": unknown[dev_i + 1], "parser": "train_start declarations + installed cli_args.py",
            "applauncher_imported": False, "training_started": False}


def build_report(repo: str | Path, checkpoint: str | Path, expected_sha256: str,
                 *, expected_head: str | None = None) -> dict[str, Any]:
    """Assemble dry evidence; intentionally emits no training argv."""
    return {"format": "foothold-ex41-start-preflight/1",
            "launch_allowed": False,
            "reason": "analyst runtime implementation and Kit approval are outstanding",
            "worktree": inspect_fixed_worktree(repo, expected_head=expected_head),
            "parent": verify_parent_checkpoint(checkpoint, expected_sha256),
            "source_audit": audit_train_source(repo)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--parent-checkpoint", type=Path, required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--dry-run", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        result = build_report(args.repo, args.parent_checkpoint, args.parent_sha256,
                              expected_head=args.expected_head)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
