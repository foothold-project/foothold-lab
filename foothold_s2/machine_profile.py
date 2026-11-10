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
OPTIONAL_PATHS = (
    "isaac_cache_root", "git_bash", "gpu_jobs_config", "gpu_queue",
    "playlist_root", "c_layer_lock", "a_layer_marker",
    "ex41_stage_video_source", "ex41_stage_video_output", "ex41_w78_video_root",
    "runner_home", "telegram_outbox", "telegram_script",
    "gpu0_training_marker", "gpu0_training_marker_alt", "gpu1_training_marker",
    "gpu0_eval_marker", "gpu1_eval_marker", "ex41_push250_output", "ex42_gate_report",
)
DEVICE_ROLES = ("training", "p1_evaluation", "screen")
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
    def expand_path(key: str, raw: Any, *, required: bool) -> str | None:
        if not required and (raw is None or isinstance(raw, str) and not raw.strip()):
            return None
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError(f"machine profile path missing: {key}")
        missing_optional_ref = False

        def replace(match: re.Match[str]) -> str:
            nonlocal missing_optional_ref
            name = match.group(1)
            result = env.get(name)
            if not result:
                if not required:
                    missing_optional_ref = True
                    return ""
                raise ValueError(f"machine profile path {key} requires environment variable {name}")
            return result

        expanded = _ENV_REF.sub(replace, raw)
        if missing_optional_ref:
            return None
        if expanded.startswith("~"):
            expanded = str(Path.home()) + expanded[1:]
        is_absolute = (PureWindowsPath(expanded).is_absolute() if selected_platform == "win32"
                       else PurePosixPath(expanded).is_absolute())
        if not is_absolute:
            raise ValueError(f"machine profile path must be absolute: {key}")
        return expanded

    for key in REQUIRED_PATHS:
        resolved[key] = expand_path(key, paths.get(key), required=True)
    for key in OPTIONAL_PATHS:
        value = expand_path(key, paths.get(key), required=False)
        if value is not None:
            resolved[key] = value

    raw_devices = doc.get("devices")
    if not isinstance(raw_devices, dict) or set(raw_devices) != set(DEVICE_ROLES):
        raise ValueError("machine profile devices must define training, p1_evaluation, and screen")
    devices: dict[str, dict[str, Any]] = {}
    for role in DEVICE_ROLES:
        row = raw_devices.get(role)
        if not isinstance(row, dict):
            raise ValueError(f"machine profile device role missing: {role}")
        index, uuid = row.get("cuda_index"), row.get("uuid")
        if type(index) is not int or index < 0:
            raise ValueError(f"machine profile CUDA index invalid: {role}")
        if isinstance(uuid, str):
            match = _ENV_REF.fullmatch(uuid)
            if match:
                uuid = env.get(match.group(1))
        if not isinstance(uuid, str) or not uuid.strip() or "${" in uuid:
            raise ValueError(f"machine profile GPU UUID missing: {role}")
        devices[role] = {"cuda_index": index, "device": f"cuda:{index}", "uuid": uuid.strip()}
    if devices["training"]["cuda_index"] != 0:
        raise ValueError("EX-42 training device must be cuda:0")
    return {"machine_id": doc["machine_id"], "profile": str(path),
            "paths": resolved, "devices": devices}


def validate_training_device(device: str, *, machine_profile: dict[str, Any]) -> None:
    """Reject a training CLI that disagrees with the selected machine's role map."""
    expected = machine_profile.get("devices", {}).get("training", {}).get("device")
    if device != expected or expected != "cuda:0":
        raise ValueError(f"training device must match the machine profile cuda:0 role, got {device!r}")


def machine_path(key: str, *, profile: str | Path | None = None,
                 environ: Mapping[str, str] | None = None,
                 platform: str | None = None) -> Path:
    paths = load_machine_profile(profile=profile, environ=environ, platform=platform)["paths"]
    value = paths.get(key)
    if not value:
        raise ValueError(f"machine profile does not define path: {key}")
    return Path(value)


def machine_reference_path(value: str | Path, *, profile: str | Path | None = None,
                           environ: Mapping[str, str] | None = None,
                           platform: str | None = None) -> Path:
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
    return machine_path(key, profile=profile, environ=environ, platform=platform).joinpath(*rel.parts)


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
