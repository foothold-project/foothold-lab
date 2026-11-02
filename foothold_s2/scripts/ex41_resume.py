"""EX-41 same-run checkpoint identity and state-preservation helpers.

This module has no Isaac/Kit imports so its guards can run in CPU-only tests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import torch


RESUME_FORMAT = "foothold-ex41-resume/1"
CHECKPOINT_FORMAT = "foothold-start/1"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_resume_manifest(checkpoint: str | Path, manifest_path: str | Path, *,
                             plan_sha256: str, effective_sha256: str,
                             parent_sha256: str, log_dir: str | Path | None = None,
                             score_dir: str | Path | None = None) -> dict[str, Any]:
    """Check run/checkpoint identity before any checkpoint state is restored."""
    path = Path(checkpoint).resolve(strict=True)
    manifest_file = Path(manifest_path).resolve(strict=True)
    if manifest_file != path.parent / "manifest.json":
        raise ValueError("EX-41 resume manifest must belong to the checkpoint run directory")
    if log_dir is not None and Path(log_dir).resolve() != path.parent:
        raise ValueError("EX-41 resume checkpoint is outside the requested existing run directory")
    match = re.fullmatch(r"model_(\d+)\.pt", path.name)
    if not match:
        raise ValueError("EX-41 self-resume requires a numbered model_<iter>.pt checkpoint")
    iteration = int(match.group(1))
    actual_sha = sha256_file(path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    if manifest.get("checkpoints", {}).get(path.name) != actual_sha:
        raise ValueError("EX-41 resume checkpoint SHA differs from the run manifest")
    # EX41 maps StartRunner's zero-based loop index to a one-based update
    # number before saving, so model_N.pt contains completed update N.
    progress = manifest.get("progress", {}).get("completed_updates")
    if type(progress) is not int or progress != iteration:
        raise ValueError("EX-41 resume checkpoint is not the manifest's latest saved progress")
    modes = manifest.get("modes", {}).get("ex41")
    if not isinstance(modes, dict):
        raise ValueError("EX-41 resume manifest identity is missing")
    if (modes.get("plan_sha256") != plan_sha256
            or modes.get("effective_sha256") != effective_sha256):
        raise ValueError("EX-41 resume plan/effective SHA differs from the run manifest")
    parent = modes.get("parent")
    if not isinstance(parent, dict) or parent.get("sha256") != parent_sha256:
        raise ValueError("EX-41 resume parent SHA differs from the run manifest")
    transfer = modes.get("transfer")
    if isinstance(transfer, dict) and transfer.get("parent_sha256") != parent_sha256:
        raise ValueError("EX-41 resume transfer parent SHA differs from the run manifest")
    resume_records = manifest.get("ex41_resume_checkpoints")
    record = resume_records.get(path.name) if isinstance(resume_records, dict) else None
    if not isinstance(record, dict):
        raise ValueError("EX-41 resume checkpoint has no runner continuation receipt")
    if (record.get("checkpoint_sha256") != actual_sha
            or record.get("iteration") != iteration
            or record.get("completed_updates") != iteration
            or record.get("plan_sha256") != plan_sha256
            or record.get("effective_sha256") != effective_sha256
            or record.get("parent_sha256") != parent_sha256
            or type(record.get("segment_index")) is not int):
        raise ValueError("EX-41 resume continuation receipt differs from checkpoint/plan/parent")
    # Read the actual payload on CPU during the pre-Kit preflight. Manifest
    # metadata alone must not authorize restoring a checkpoint with another
    # plan, parent, or incomplete W72/optimizer/RNG state.
    payload = torch.load(path, map_location="cpu", weights_only=False)
    saved = validate_resume_state(
        payload, plan_sha256=plan_sha256,
        effective_sha256=effective_sha256, parent_sha256=parent_sha256)
    if (saved["iteration"] != iteration
            or saved["last_valid_boundary"] != record.get("last_valid_boundary")
            or saved["dr_scale"] != record.get("dr_scale")
            or saved["fixed_clock"] != record.get("fixed_clock")):
        raise ValueError("EX-41 resume receipt differs from serialized checkpoint state")
    recorded_score_dir = modes.get("score_dir")
    if score_dir is not None and recorded_score_dir is not None:
        if Path(score_dir).resolve() != Path(recorded_score_dir).resolve():
            raise ValueError("EX-41 resume score directory differs from the existing run")
    return {
        "checkpoint": str(path),
        "checkpoint_sha256": actual_sha,
        "iteration": iteration,
        "completed_updates": iteration,
        "next_update": iteration + 1,
        "last_valid_boundary": saved["last_valid_boundary"],
        "dr_scale": saved["dr_scale"],
        "fixed_clock": saved["fixed_clock"],
        "manifest_progress_updates": progress,
        "segment_index": record["segment_index"] + 1,
        "plan_sha256": plan_sha256,
        "effective_sha256": effective_sha256,
        "parent_sha256": parent_sha256,
        "run_dir": str(path.parent),
        "score_dir": recorded_score_dir,
    }


def add_resume_envelope(state: dict[str, Any], *, plan_sha256: str,
                        effective_sha256: str, parent_sha256: str) -> dict[str, Any]:
    """Add an explicit identity envelope to a normal StartRunner checkpoint."""
    if state.get("format") != CHECKPOINT_FORMAT:
        raise ValueError("EX-41 resume can only wrap a StartRunner checkpoint")
    curriculum = state.get("continuous_curriculum")
    if not isinstance(curriculum, dict):
        raise ValueError("EX-41 checkpoint is missing continuous curriculum state")
    transfer = state.get("ex41_parent_transfer")
    if not isinstance(transfer, dict) or transfer.get("parent_sha256") != parent_sha256:
        raise ValueError("EX-41 checkpoint parent transfer SHA differs from the fixed plan")
    if curriculum.get("plan_sha256") != plan_sha256 or curriculum.get("effective_sha256") != effective_sha256:
        raise ValueError("EX-41 checkpoint plan/effective SHA differs from the fixed plan")
    state["ex41_resume"] = {
        "format": RESUME_FORMAT,
        "plan_sha256": plan_sha256,
        "effective_sha256": effective_sha256,
        "parent_sha256": parent_sha256,
        "iteration": int(state["iter"]),
        "completed_updates": int(state["iter"]),
        "next_update": int(state["iter"]) + 1,
        "w72_last_valid_boundary": curriculum.get("last_boundary"),
        "w72_snapshot": curriculum.get("snapshot"),
        "fixed_clock": curriculum.get("fixed_clock"),
    }
    return state


def validate_resume_state(state: dict[str, Any], *, plan_sha256: str,
                          effective_sha256: str, parent_sha256: str) -> dict[str, Any]:
    """Validate all serialized state needed to continue before learning begins."""
    if state.get("format") != CHECKPOINT_FORMAT:
        raise ValueError("EX-41 self-resume checkpoint format differs")
    iteration = state.get("iter")
    if type(iteration) is not int or iteration < 1:
        raise ValueError("EX-41 self-resume checkpoint iteration is invalid")
    if (not isinstance(state.get("optimizer_state_dict"), dict)
            or not isinstance(state["optimizer_state_dict"].get("param_groups"), list)):
        raise ValueError("EX-41 self-resume optimizer state is missing")
    if (not isinstance(state.get("perception_optimizer_state_dict"), dict)
            or not isinstance(state["perception_optimizer_state_dict"].get("param_groups"), list)):
        raise ValueError("EX-41 self-resume perception optimizer state is missing")
    if not isinstance(state.get("model_state_dict"), dict) or not isinstance(state.get("perception_state_dict"), dict):
        raise ValueError("EX-41 self-resume policy/perception weights are missing")
    if not isinstance(state.get("ppo_learning_rate"), (int, float)):
        raise ValueError("EX-41 self-resume PPO learning rate is missing")
    if (not isinstance(state.get("adasmpl"), dict)
            or not {"p", "count", "sum", "sumsq", "force_gt"}.issubset(state["adasmpl"])):
        raise ValueError("EX-41 self-resume AdaSmpl state is missing")
    rng = state.get("rng")
    if not isinstance(rng, dict) or not {"torch", "numpy", "python"}.issubset(rng):
        raise ValueError("EX-41 self-resume RNG state is incomplete")
    env_state = state.get("env_state")
    if (not isinstance(env_state, dict)
            or not {"terrain_levels", "terrain_types", "range_curriculum",
                    "command_generator_state"}.issubset(env_state)):
        raise ValueError("EX-41 self-resume terrain, command curriculum, or command RNG state is missing")
    if not isinstance(state.get("map_switch"), dict):
        raise ValueError("EX-41 self-resume map sampling RNG state is missing")

    curriculum = state.get("continuous_curriculum")
    required_curriculum = {
        "stages", "stage_pos", "effective", "config_values", "snapshot", "last_boundary",
        "iteration", "extensions", "pair_bias", "halved", "auto_disabled", "mirror_pending",
        "auto_seen", "history", "level_history", "s2c_pass", "ramp", "stage_baseline_sha",
        "receipt", "applied_ids", "finished", "stop_requested", "graduated", "score_rejections",
        "active", "env_stage", "terrain_receipt", "segment_index", "domain_randomization",
        "stage_entry_iteration", "pending_gate", "seen_scores", "passes",
        "maintenance_baseline_sha256", "missing_maintenance_boundaries",
    }
    if (not isinstance(curriculum, dict) or curriculum.get("format") != "foothold-ex41-state/1"
            or not required_curriculum.issubset(curriculum)):
        raise ValueError("EX-41 self-resume W72/curriculum state is missing")
    if (curriculum.get("plan_sha256") != plan_sha256
            or curriculum.get("effective_sha256") != effective_sha256):
        raise ValueError("EX-41 self-resume checkpoint plan/effective SHA differs")
    boundary = curriculum.get("last_boundary")
    if type(boundary) is not int or boundary < -1 or not isinstance(curriculum.get("snapshot"), dict):
        raise ValueError("EX-41 self-resume last valid W72 boundary/snapshot is missing")
    if type(curriculum.get("segment_index")) is not int or type(curriculum.get("env_stage")) is not torch.Tensor:
        raise ValueError("EX-41 self-resume curriculum segment/env state is incomplete")
    if curriculum.get("iteration") != iteration:
        raise ValueError("EX-41 saved curriculum update differs from checkpoint iteration")
    terrain_receipt = curriculum.get("terrain_receipt")
    if not isinstance(terrain_receipt, dict) or not terrain_receipt.get("terrain_labels_sha256"):
        raise ValueError("EX-41 self-resume terrain receipt is missing")
    dr = curriculum.get("domain_randomization")
    if not isinstance(dr, dict) or not isinstance(dr.get("scale"), (int, float)):
        raise ValueError("EX-41 self-resume DR scale/state is missing")
    clock = curriculum.get("fixed_clock")
    required_clock = {"anchor", "elapsed", "pause_used", "recovered", "extension",
                      "extension_decided", "paused"}
    if not isinstance(clock, dict) or not required_clock.issubset(clock):
        raise ValueError("EX-41 self-resume fixed schedule clock is incomplete")
    transfer = state.get("ex41_parent_transfer")
    if not isinstance(transfer, dict) or transfer.get("parent_sha256") != parent_sha256:
        raise ValueError("EX-41 self-resume checkpoint parent SHA differs")
    envelope = state.get("ex41_resume")
    if not isinstance(envelope, dict) or envelope.get("format") != RESUME_FORMAT:
        raise ValueError("EX-41 self-resume identity envelope is missing")
    expected_envelope = {
        "plan_sha256": plan_sha256,
        "effective_sha256": effective_sha256,
        "parent_sha256": parent_sha256,
        "iteration": iteration,
        "completed_updates": iteration,
        "next_update": iteration + 1,
        "w72_last_valid_boundary": boundary,
        "w72_snapshot": curriculum["snapshot"],
        "fixed_clock": clock,
    }
    for key, value in expected_envelope.items():
        if envelope.get(key) != value:
            raise ValueError(f"EX-41 self-resume envelope differs at {key}")
    return {
        "iteration": iteration,
        "completed_updates": iteration,
        "next_update": iteration + 1,
        "segment_index": curriculum["segment_index"] + 1,
        "last_valid_boundary": boundary,
        "dr_scale": float(dr["scale"]),
        "fixed_clock": dict(clock),
    }


def state_digest(value: Any) -> str:
    """Stable recursive CPU digest used to compare parent/child restore results."""
    digest = hashlib.sha256()

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key in sorted(item, key=str):
                visit(item[key], f"{path}/{key}")
        elif isinstance(item, (list, tuple)):
            digest.update(f"{path}:{type(item).__name__}:{len(item)}".encode())
            for index, child in enumerate(item):
                visit(child, f"{path}/{index}")
        elif isinstance(item, torch.Tensor):
            tensor = item.detach().cpu().contiguous()
            digest.update(path.encode())
            digest.update(str(tensor.dtype).encode())
            digest.update(repr(tuple(tensor.shape)).encode())
            if tensor.numel():
                digest.update(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
        elif isinstance(item, np.ndarray):
            array = np.ascontiguousarray(item)
            digest.update(path.encode())
            digest.update(str(array.dtype).encode())
            digest.update(repr(array.shape).encode())
            digest.update(array.tobytes())
        else:
            digest.update(path.encode())
            digest.update(repr(item).encode("utf-8", "backslashreplace"))

    visit(value, "root")
    return digest.hexdigest()


def install_resume_checkpoint_hooks(runner, manifest: dict[str, Any], log_dir: str | Path, *,
                                    plan_sha256: str, effective_sha256: str,
                                    parent_sha256: str, write_manifest) -> None:
    """Attach the EX-41 envelope and manifest continuation receipt to numbered saves."""
    original_state_dict = runner.state_dict
    original_manifest_checkpoint = runner._manifest_checkpoint

    def state_dict_with_identity(infos=None):
        state = original_state_dict(infos)
        return add_resume_envelope(state, plan_sha256=plan_sha256,
                                   effective_sha256=effective_sha256,
                                   parent_sha256=parent_sha256)

    def manifest_checkpoint_with_resume(iteration, name, num_envs):
        original_manifest_checkpoint(iteration, name, num_envs)
        state = state_dict_with_identity()
        if int(state["iter"]) != int(iteration):
            raise ValueError("EX-41 continuation receipt iteration differs from saved checkpoint")
        curriculum = state["continuous_curriculum"]
        envelope = state["ex41_resume"]
        checkpoint_path = Path(log_dir) / name
        record = {
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "iteration": int(iteration),
        "completed_updates": int(iteration),
            "plan_sha256": plan_sha256,
            "effective_sha256": effective_sha256,
            "parent_sha256": parent_sha256,
            "segment_index": int(curriculum["segment_index"]),
            "last_valid_boundary": envelope["w72_last_valid_boundary"],
            "dr_scale": float(curriculum["domain_randomization"]["scale"]),
            "fixed_clock": dict(curriculum["fixed_clock"]),
        }
        manifest.setdefault("ex41_resume_checkpoints", {})[name] = record
        # The generic StartRunner manifest uses zero-based iter semantics and
        # writes it + 1. EX41's saved iter is already the one-based update n.
        manifest.setdefault("progress", {})["completed_updates"] = int(iteration)
        write_manifest(str(log_dir), manifest)

    runner.state_dict = state_dict_with_identity
    runner._manifest_checkpoint = manifest_checkpoint_with_resume


def append_resume_segment(manifest: dict[str, Any], resume: dict[str, Any], *,
                          process_id: int, started_at: str) -> dict[str, Any]:
    """Append one auditable continuation segment without rebuilding run identity."""
    row = {
        "segment_index": resume["segment_index"],
        "checkpoint": resume["checkpoint"],
        "checkpoint_sha256": resume["checkpoint_sha256"],
        "completed_updates_at_start": resume["completed_updates"],
        "next_update": resume["next_update"],
        "plan_sha256": resume["plan_sha256"],
        "effective_sha256": resume["effective_sha256"],
        "parent_sha256": resume["parent_sha256"],
        "process_id": int(process_id),
        "started_at": started_at,
        "restored": True,
    }
    rows = manifest.setdefault("resume_segments", [])
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise ValueError("EX-41 resume segment manifest is malformed")
    row["resume_attempt"] = len(rows) + 1
    rows.append(row)
    return row
