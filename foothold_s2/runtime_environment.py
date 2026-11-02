"""EX-41 launcher environment pin for Python and the installed RSL-RL API."""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
from pathlib import Path
import sys
from typing import Any


EXPECTED_PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
EXPECTED_RSL_RL_INIT = Path(
    "C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/__init__.py"
)
EXPECTED_RSL_RL_VERSION = "3.1.2"


def validate_runtime_identity(*, python_executable: str | Path,
                              rsl_rl_module: str | Path,
                              rsl_rl_version: str,
                              ppo_source: str | Path,
                              expected_python: str | Path = EXPECTED_PYTHON,
                              expected_module: str | Path = EXPECTED_RSL_RL_INIT,
                              expected_version: str = EXPECTED_RSL_RL_VERSION) -> dict[str, Any]:
    python_path = Path(python_executable).resolve()
    module_path = Path(rsl_rl_module).resolve()
    expected_python_path = Path(expected_python).resolve()
    expected_module_path = Path(expected_module).resolve()
    source = Path(ppo_source).resolve(strict=True)
    if python_path != expected_python_path:
        raise ValueError(f"Python interpreter mismatch: {python_path}")
    if module_path != expected_module_path:
        raise ValueError(f"rsl_rl module path mismatch: {module_path}")
    if rsl_rl_version != expected_version:
        raise ValueError(f"rsl-rl-lib version mismatch: {rsl_rl_version}")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    ppo = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PPO"), None)
    if ppo is None:
        raise ValueError("installed rsl_rl PPO class not found")
    init = next((node for node in ppo.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == "__init__"), None)
    names = {arg.arg for arg in init.args.args} if init else set()
    has_init_storage = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and node.name == "init_storage" for node in ppo.body)
    if "storage" in names or not has_init_storage:
        raise ValueError("installed PPO API differs: expected no constructor storage and init_storage()")
    return {"python_executable": str(python_path),
            "rsl_rl_module": str(module_path),
            "rsl_rl_version": rsl_rl_version,
            "ppo_source": str(source),
            "ppo_constructor_storage": False,
            "ppo_init_storage": True}


def current_runtime_identity() -> dict[str, Any]:
    spec = importlib.util.find_spec("rsl_rl")
    if spec is None or spec.origin is None:
        raise ValueError("rsl_rl package cannot be resolved")
    package_root = Path(spec.origin).resolve().parent
    ppo_source = package_root / "algorithms" / "ppo.py"
    version = importlib.metadata.version("rsl-rl-lib")
    return validate_runtime_identity(python_executable=sys.executable,
                                    rsl_rl_module=spec.origin,
                                    rsl_rl_version=version,
                                    ppo_source=ppo_source)
