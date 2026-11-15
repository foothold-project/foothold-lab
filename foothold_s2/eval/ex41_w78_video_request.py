"""Create immutable W78 stair-video requests for exact EX-41 checkpoints.

The runner owns request creation. The recorder owns video capture and its
receipt. This module never starts a recorder or an evaluation process.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from foothold_s2.eval.ex41_map_modes import REQUIRED_MODES

SCHEMA = "foothold-ex41-w78-video-request/1"
ANGLES_DEG = (0, 30, 60, 90)
LEVEL = 5
CASE = "stairs_fwd"
REQUEST_DIR = "w78_video_requests"
_STAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*\Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_combinations() -> list[str]:
    """Canonical W78 v2 combination IDs for the twelve requested videos."""
    return [f"L{LEVEL}_a{angle:03d}_{mode}_{CASE}"
            for angle in ANGLES_DEG for mode in REQUIRED_MODES]


def _manifest_checkpoint_sha(run_root: Path, checkpoint: Path) -> str:
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    value = manifest.get("checkpoints", {}).get(checkpoint.name)
    if isinstance(value, dict):
        value = value.get("sha256")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("checkpoint SHA missing from run manifest")
    if value != _sha256_file(checkpoint):
        raise ValueError("checkpoint SHA differs from run manifest")
    return value


def build_request(run_root: str | Path, checkpoint_path: str | Path,
                  local_iteration: int, stage_name: str) -> dict:
    """Build a request only from a manifest-published checkpoint in this run."""
    root = Path(run_root).resolve(strict=True)
    checkpoint = Path(checkpoint_path).resolve(strict=True)
    if not checkpoint.is_file():
        raise ValueError("checkpoint path is not a file")
    try:
        checkpoint.relative_to(root)
    except ValueError as exc:
        raise ValueError("checkpoint must be inside the EX-41 run") from exc
    if type(local_iteration) is not int or local_iteration < 1:
        raise ValueError("local_iteration must be a positive integer")
    match = re.fullmatch(r"model_(\d+)\.pt", checkpoint.name)
    if not match or int(match.group(1)) != local_iteration:
        raise ValueError("local_iteration differs from checkpoint filename")
    if not isinstance(stage_name, str) or not _STAGE.fullmatch(stage_name):
        raise ValueError("stage_name must be a nonempty EX-41 stage identifier")
    checkpoint_sha = _manifest_checkpoint_sha(root, checkpoint)
    return {
        "schema": SCHEMA,
        "request_id": "",  # Filled from the canonical payload below.
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha,
        "local_iteration": local_iteration,
        "stage_name": stage_name,
        "combinations": expected_combinations(),
    }


def request_bytes(request: dict) -> bytes:
    """Return canonical UTF-8 JSON with request_id derived from its payload."""
    if not isinstance(request, dict) or request.get("schema") != SCHEMA:
        raise ValueError("unsupported W78 video request schema")
    payload = {key: value for key, value in request.items() if key != "request_id"}
    if payload.get("combinations") != expected_combinations():
        raise ValueError("W78 video request combinations differ from canonical set")
    request_id = _sha256_bytes(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8"))
    final = dict(payload, request_id=request_id)
    return (json.dumps(final, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       indent=2) + "\n").encode("utf-8")


def write_request(run_root: str | Path, checkpoint_path: str | Path,
                  local_iteration: int, stage_name: str) -> Path:
    """Publish one immutable request under run_root/w78_video_requests."""
    root = Path(run_root).resolve(strict=True)
    request = build_request(root, checkpoint_path, local_iteration, stage_name)
    data = request_bytes(request)
    request_id = json.loads(data)["request_id"]
    folder = root / REQUEST_DIR
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"request_m{local_iteration:05d}_{request_id[:12]}.json"
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError("existing W78 video request differs")
        return target
    temp = target.with_name(target.name + f".pending.{os.getpid()}")
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.rename(temp, target)
        except FileExistsError:
            if target.read_bytes() != data:
                raise ValueError("concurrent W78 video request conflicts")
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return target


def publish_stage_end_request(run_root: str | Path, runtime, *,
                              stage_name: str, next_stage: str | None,
                              boundary_iteration: int) -> dict:
    """Publish only when the exact completed stage checkpoint is available.

    At a transition entering update ``n``, the stage-end checkpoint must be
    the completed update ``n-1``. For a final checkpoint, pass
    ``next_stage=None`` and ``boundary_iteration`` equal to its iteration.
    Missing or mismatched evidence is an explicit hold, never a fabricated
    request or a training stop.
    """
    if not isinstance(stage_name, str) or not _STAGE.fullmatch(stage_name):
        raise ValueError("stage_name must be a nonempty EX-41 stage identifier")
    if next_stage is not None and (not isinstance(next_stage, str)
                                   or not _STAGE.fullmatch(next_stage)):
        raise ValueError("next_stage must be a stage identifier or None")
    if type(boundary_iteration) is not int or boundary_iteration < 1:
        raise ValueError("boundary_iteration must be a positive integer")
    expected = boundary_iteration if next_stage is None else boundary_iteration - 1
    checkpoint = getattr(runtime, "last_checkpoint", None)
    if not isinstance(checkpoint, dict) or checkpoint.get("iteration") != expected:
        return {"state": "held", "reason": "exact_stage_end_checkpoint_missing",
                "stage_name": stage_name, "next_stage": next_stage,
                "expected_iteration": expected,
                "observed_iteration": checkpoint.get("iteration") if isinstance(checkpoint, dict) else None}
    try:
        path = write_request(run_root, checkpoint["path"], expected, stage_name)
    except (OSError, ValueError, KeyError) as exc:
        return {"state": "held", "reason": f"{type(exc).__name__}: {exc}",
                "stage_name": stage_name, "next_stage": next_stage,
                "expected_iteration": expected}
    return {"state": "published", "path": str(path),
            "stage_name": stage_name, "next_stage": next_stage,
            "iteration": expected}
