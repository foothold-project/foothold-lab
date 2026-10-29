"""CPU preflight for train_sb launch arguments before Isaac or GPU startup."""

from __future__ import annotations

import argparse
import ast
import importlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "foothold_s2/scripts/train_sol23f_common.py"
MODULES = (
    "foothold_s2.basic_gait_launch",
    "foothold_s2.basic_gait_extend_launch",
    "foothold_s2.basic_gait_ex38_continue",
    "foothold_s2.basic_gait_ex39",
    "foothold_s2.basic_gait_run",
    "foothold_s2.commands.mixed_core",
    "foothold_s2.commands.basic_levels",
    "foothold_s2.rewards.basic_gait_bundle",
    "foothold_s2.sol23f_contract",
)


def actual_parser() -> argparse.ArgumentParser:
    tree = ast.parse(TRAIN.read_text(encoding="utf-8"), filename=str(TRAIN))
    declarations = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "parser" for t in node.targets):
            declarations.append(node)
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and isinstance(node.value.func, ast.Attribute)
              and isinstance(node.value.func.value, ast.Name)
              and node.value.func.value.id == "parser" and node.value.func.attr == "add_argument"):
            declarations.append(node)
    namespace = {"argparse": argparse}
    exec(compile(ast.Module(body=declarations, type_ignores=[]), str(TRAIN), "exec"), namespace)
    return namespace["parser"]


def inspect_args(args: list[str]) -> dict:
    parser = actual_parser()
    parsed, unknown = parser.parse_known_args(["--task", "FootholdS2-Go2-S2-SB-v0", "--variant", "SB", *args])
    if parsed.variant != "SB" or parsed.task != "FootholdS2-Go2-S2-SB-v0":
        raise ValueError("train_sb wrapper task or variant mismatch")
    # cli_args and AppLauncher register these after the declarations extracted above.
    expected = ["--headless", "--device", args[args.index("--device") + 1],
                "--run_name", args[args.index("--run_name") + 1]]
    if unknown[:5] != expected or len(unknown) not in (5, 6) or (
            len(unknown) == 6 and not unknown[5].startswith("--kit_args=")):
        raise ValueError(f"unexpected AppLauncher arguments: {unknown}")
    if parsed.basic_ex39_arm:
        from foothold_s2.sol23f_contract import validate_launch

        parsed.agent = "rsl_rl_cfg_entry_point"
        parsed.distributed = False
        parsed.map_input = None
        parsed.resume = False
        validate_launch(parsed, verify_parent=True)
    return {"run_name": args[args.index("--run_name") + 1], "max_iterations": parsed.max_iterations,
            "basic_ex38": parsed.basic_ex38, "basic_ex38_continue_parent_sha": parsed.basic_ex38_continue_parent_sha,
            "basic_ex39_arm": parsed.basic_ex39_arm,
            "unknown_applauncher_args": unknown}


def check(args_path: Path, *, git_check: bool = True) -> dict:
    if not args_path.is_file():
        raise FileNotFoundError(args_path)
    args = args_path.read_text(encoding="utf-8-sig").splitlines()
    if not args or any(not a or "\r" in a for a in args):
        raise ValueError("empty or malformed training launch arguments")
    imports = {name: str(importlib.import_module(name).__file__) for name in MODULES}
    row = inspect_args(args)
    if git_check:
        status = subprocess.run(["git", "status", "--porcelain", "--", "foothold_s2"],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        if status.stdout.strip():
            raise ValueError("training source tree is not git clean: " + status.stdout.strip())
        subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True,
                       text=True, capture_output=True)
    return {"state": "prestart_pass", "python_imports": imports,
            "actual_train_parser": str(TRAIN), "source_git_clean": git_check, **row}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--args-file", type=Path, required=True)
    a = parser.parse_args(argv)
    print(json.dumps(check(a.args_file), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
