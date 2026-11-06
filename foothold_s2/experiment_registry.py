"""Load experiment-specific values from experiments/<id>.yaml.

Operating code uses this registry rather than embedding experiment identifiers.
Paths in a definition are repository-relative unless explicitly marked as an
external absolute reference.
"""
from __future__ import annotations

import re
import hashlib
import json
from pathlib import Path, PureWindowsPath
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_ROOT = REPO_ROOT / "experiments"
FORMAT = "foothold-experiment-definition/1"
_ID = re.compile(r"^[A-Z][A-Z0-9-]{1,31}$")
_DEVICE_ROLES = ("training", "evaluation", "video", "w78")
_GPU_UUIDS = {
    "cuda:0": "c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b",
    "cuda:1": "315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f",
}


def load_experiment(experiment_id: str, *, registry_root: str | Path = REGISTRY_ROOT) -> dict[str, Any]:
    if not isinstance(experiment_id, str) or not _ID.fullmatch(experiment_id):
        raise ValueError("invalid experiment identifier")
    path = Path(registry_root) / f"{experiment_id}.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ValueError(f"experiment definition format invalid: {path}")
    if doc.get("experiment_id") != experiment_id:
        raise ValueError("experiment definition ID does not match requested ID")
    if not isinstance(doc.get("paths"), dict) or not isinstance(doc.get("files"), dict):
        raise ValueError("experiment definition must contain paths and files")
    return doc


def source_path(definition: dict[str, Any], key: str, *, repo_root: str | Path = REPO_ROOT) -> Path:
    files = definition["files"]
    value = files.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"experiment source path missing: {key}")
    win = PureWindowsPath(value)
    if win.is_absolute() or value.startswith(("/", "\\")):
        return Path(value)
    resolved = (Path(repo_root) / Path(value)).resolve()
    root = Path(repo_root).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"experiment path escapes repository: {key}")
    return resolved


def output_paths(definition: dict[str, Any], stamp: str, *, s2_lab: str | Path,
                 run_name: str | None = None) -> dict[str, Path]:
    if not re.fullmatch(r"[0-9]{8}_[0-9]{6}", stamp):
        raise ValueError("experiment output stamp must be YYYYMMDD_HHMMSS")
    path_spec = definition["paths"]
    template = path_spec.get("root_template")
    slug = path_spec.get("slug")
    if not isinstance(template, str) or not isinstance(slug, str):
        raise ValueError("experiment root template or slug missing")
    relative = template.format(slug=slug, stamp=stamp)
    if PureWindowsPath(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("experiment root template must stay below s2_lab")
    root = Path(s2_lab) / relative
    dirs = path_spec.get("directories")
    if not isinstance(dirs, dict) or not dirs:
        raise ValueError("experiment output directories missing")
    result = {"root": root}
    for key, rel in dirs.items():
        if not isinstance(rel, str) or PureWindowsPath(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError(f"unsafe experiment output directory: {key}")
        if "{run}" in rel and not run_name:
            continue
        result[key] = root / rel.format(exp=definition["experiment_id"], run=run_name or "")
    return result


def required_cli_path(definition: dict[str, Any], key: str, override: str | Path | None = None) -> Path:
    if override is not None:
        return Path(override)
    return source_path(definition, key)


def paths_for_run(definition: dict[str, Any], run_dir: str | Path) -> dict[str, Path]:
    run = Path(run_dir).resolve(strict=True)
    root = run.parent.parent
    slug = definition["paths"].get("slug")
    if (run.parent.name != "main" or not isinstance(slug, str)
            or not root.name.startswith(f"{slug}_")):
        raise ValueError("run directory is not under the selected experiment root/main")
    if not (root / "main").is_dir():
        raise ValueError("experiment output root has no main directory")
    return {
        "root": root,
        "main": run,
        "scores": root / definition["paths"]["directories"]["scores"],
        "push250": root / definition["paths"]["directories"]["push250"],
        "score_watch": root / definition["paths"]["directories"]["score_watch"],
        "stage_end": root / definition["paths"]["directories"]["stage_end"],
        "stage_video": root / definition["paths"]["directories"]["stage_video"],
    }


def operational_definition(experiment_id: str, *, registry_root: str | Path = REGISTRY_ROOT) -> dict[str, Any]:
    """Load an operational experiment, rejecting preparation-only entries."""
    definition = load_experiment(experiment_id, registry_root=registry_root)
    if definition.get("status") != "operating" or definition.get("operations", {}).get("enabled") is not True:
        raise ValueError(f"experiment operations are not enabled: {experiment_id}")
    return definition


def device_contract(definition: dict[str, Any]) -> dict[str, str]:
    """Return the four pinned device roles from one experiment definition."""
    devices = definition.get("devices")
    if not isinstance(devices, dict) or set(devices) != set(_DEVICE_ROLES):
        raise ValueError("experiment definition must pin training, evaluation, video, and w78 devices")
    result: dict[str, str] = {}
    for role in _DEVICE_ROLES:
        device = devices.get(role)
        if not isinstance(device, str) or device not in _GPU_UUIDS:
            raise ValueError(f"experiment {role} device must be an explicit registered CUDA device")
        result[role] = device
    return result


def device_contract_sha256(definition: dict[str, Any]) -> str:
    payload = json.dumps(device_contract(definition), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def queue_gpu_identity(device: str) -> tuple[int, str]:
    """Translate a registered CUDA device to dispatcher index and UUID."""
    if device not in _GPU_UUIDS:
        raise ValueError(f"unsupported experiment queue device: {device}")
    return int(device.rsplit(":", 1)[1]), _GPU_UUIDS[device]
