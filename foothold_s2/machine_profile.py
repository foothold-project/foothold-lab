"""Resolve machine-local installation and storage paths from one profile.

Select a profile with FOOTHOLD_MACHINE_PROFILE. Native Windows retains the
known workstation profile when the variable is unset; POSIX requires an
explicit profile. Unset profile variables and missing required paths fail
closed rather than falling back to another machine's drive layout.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys
from typing import Mapping, Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_ENV = "FOOTHOLD_MACHINE_PROFILE"
REQUIRED_PATHS = (
    "isaaclab_root", "isaac_sim_root", "conda_python", "rsl_rl_module",
    "s2_lab_root", "mai_tmp_root", "mai_worktree_root",
)
_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _profile_path(value: str | None, *, environ: Mapping[str, str], platform: str,
                  repo_root: str | Path = REPO_ROOT) -> Path:
    selected = value or environ.get(PROFILE_ENV)
    if not selected:
        if platform == "win32":
            selected = "machines/AI-WS01-windows.yaml"
        else:
            raise ValueError(f"{PROFILE_ENV} must select a machine profile on POSIX")
    candidate = Path(selected)
    if not candidate.is_absolute() and not PureWindowsPath(selected).is_absolute():
        candidate = Path(repo_root) / candidate
    return candidate.resolve(strict=True)


def load_machine_profile(*, profile: str | Path | None = None,
                          environ: Mapping[str, str] | None = None,
                          platform: str | None = None,
                          repo_root: str | Path = REPO_ROOT) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    selected_platform = platform or sys.platform
    path = _profile_path(str(profile) if profile is not None else None,
                         environ=env, platform=selected_platform,
                         repo_root=repo_root)
    doc = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict) or doc.get("format") != "foothold-machine-profile/1":
        raise ValueError(f"machine profile format invalid: {path}")
    if not isinstance(doc.get("machine_id"), str) or not isinstance(doc.get("paths"), dict):
        raise ValueError(f"machine profile identity or paths missing: {path}")
    paths = doc["paths"]
    resolved: dict[str, str] = {}
    for key in REQUIRED_PATHS:
        raw = paths.get(key)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"machine profile path missing: {key}")

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            result = env.get(name)
            if not result:
                raise ValueError(f"machine profile path {key} requires environment variable {name}")
            return result

        expanded = _ENV_REF.sub(replace, raw)
        if expanded.startswith("~"):
            expanded = str(Path.home()) + expanded[1:]
        is_absolute = (PureWindowsPath(expanded).is_absolute() if selected_platform == "win32"
                       else PurePosixPath(expanded).is_absolute())
        if not is_absolute:
            raise ValueError(f"machine profile path must be absolute: {key}")
        resolved[key] = expanded
    for key, raw in paths.items():
        if key in resolved or raw is None:
            continue
        if not isinstance(raw, str):
            raise ValueError(f"machine profile optional path invalid: {key}")
        def replace_optional(match: re.Match[str]) -> str:
            name = match.group(1)
            result = env.get(name)
            if not result:
                raise ValueError(f"machine profile path {key} requires environment variable {name}")
            return result
        resolved[key] = _ENV_REF.sub(replace_optional, raw)
    return {"machine_id": doc["machine_id"], "profile": str(path), "paths": resolved}


def machine_path(key: str, *, profile: str | Path | None = None,
                 environ: Mapping[str, str] | None = None,
                 platform: str | None = None) -> Path:
    paths = load_machine_profile(profile=profile, environ=environ, platform=platform)["paths"]
    value = paths.get(key)
    if not value:
        raise ValueError(f"machine profile does not define path: {key}")
    return Path(value)


def machine_reference_path(value: str | Path) -> Path:
    """Resolve a portable machine-root reference or keep a fixture path intact."""
    raw = str(value)
    if not raw.startswith("machine:"):
        return Path(raw)
    reference = raw.removeprefix("machine:")
    key, separator, relative = reference.partition("/")
    if not separator or not key or not relative:
        raise ValueError("machine path reference must be machine:<root-key>/<relative-path>")
    rel = PurePosixPath(relative)
    if rel.is_absolute() or PureWindowsPath(relative).is_absolute() or ".." in rel.parts:
        raise ValueError("machine path reference must stay under its configured root")
    return machine_path(key).joinpath(*rel.parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-path", required=True)
    args = parser.parse_args(argv)
    try:
        print(machine_path(args.print_path))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
