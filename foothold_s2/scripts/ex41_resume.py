"""EX-41 same-run checkpoint identity and state-preservation helpers.

This module has no Isaac/Kit imports so its guards can run in CPU-only tests.
"""

from __future__ import annotations

import hashlib
import json
import math
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


def read_training_extra_row(log_dir: str | Path, iteration: int) -> dict[str, Any] | None:
    """Read the matching legacy per-update sidecar row for pre-R6 checkpoints.

    New checkpoints carry these values themselves. This is only for existing
    runs whose save predates the R6 fields; callers must report that source.
    """
    if type(iteration) is not int or iteration < 0:
        raise ValueError("EX-41 resume metrics iteration is invalid")
    path = Path(log_dir) / "train_extra.jsonl"
    if not path.is_file():
        return None
    match = None
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(row, dict) and row.get("it") == iteration:
                match = row
    return match


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
        # A saved checkpoint carries its own segment index. At runtime the
        # loader has already advanced the live curriculum before this readback.
        "segment_index": curriculum["segment_index"],
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


def compare_resume_state(expected: dict[str, Any], actual: dict[str, Any], *,
                         save_interval: int = 50) -> dict[str, Any]:
    """Require exact, auditable readback for all R6 continuation-critical groups."""
    curriculum_key = "continuous_curriculum"
    saved_curriculum = expected.get(curriculum_key)
    loaded_curriculum = actual.get(curriculum_key)
    if not isinstance(saved_curriculum, dict) or not isinstance(loaded_curriculum, dict):
        raise ValueError("EX-41 resumed W72 stage state is missing")
    saved_segment = saved_curriculum.get("segment_index")
    loaded_segment = loaded_curriculum.get("segment_index")
    if (type(saved_segment) is not int or type(loaded_segment) is not int
            or loaded_segment != saved_segment + 1):
        raise ValueError("EX-41 resume stage segment did not advance exactly once")
    use_gt_frac = expected.get("last_use_gt_frac")
    if (not isinstance(use_gt_frac, (int, float)) or not math.isfinite(float(use_gt_frac))
            or not 0.0 <= float(use_gt_frac) <= 1.0):
        raise ValueError("EX-41 resume last use_gt_frac evidence is missing or invalid")
    push_vmax = saved_curriculum.get("push_vmax_mps")
    if (not isinstance(push_vmax, (int, float)) or not math.isfinite(float(push_vmax))
            or float(push_vmax) <= 0.0):
        raise ValueError("EX-41 resume current push Vmax evidence is missing or invalid")
    # Starting a new process is a new auditable segment. The loader must
    # advance this counter; every other saved stage field remains byte-stable.
    saved_stage = {key: value for key, value in saved_curriculum.items()
                   if key != "segment_index"}
    loaded_stage = {key: value for key, value in loaded_curriculum.items()
                    if key != "segment_index"}
    saved_checkpoint = saved_stage.get("last_checkpoint")
    loaded_checkpoint = loaded_stage.get("last_checkpoint")
    checkpoint_reference = None
    if saved_checkpoint is not None or loaded_checkpoint is not None:
        iteration = expected.get("iter")
        if type(iteration) is not int or type(save_interval) is not int or save_interval <= 0:
            raise ValueError("EX-41 resume checkpoint iteration/save interval is invalid")
        previous_iteration = iteration - save_interval

        def validate_reference(reference: dict[str, Any] | None, label: str) -> dict[str, Any] | None:
            if reference is None:
                return None
            if not isinstance(reference, dict):
                raise ValueError(f"EX-41 {label} checkpoint reference is malformed")
            sha = reference.get("sha256")
            ref_iteration = reference.get("iteration")
            ref_path = reference.get("path")
            if (type(ref_iteration) is not int or ref_iteration > iteration
                    or not isinstance(ref_path, str) or not ref_path
                    or not isinstance(sha, str) or len(sha) != 64
                    or any(ch not in "0123456789abcdef" for ch in sha.lower())):
                raise ValueError(f"EX-41 {label} checkpoint reference is malformed")
            if ref_iteration != previous_iteration:
                raise ValueError(
                    f"EX-41 {label} checkpoint reference must be model_{previous_iteration}.pt or None")
            if Path(ref_path).name != f"model_{ref_iteration}.pt":
                raise ValueError(f"EX-41 {label} checkpoint path differs from its saved iteration")
            return {key: value for key, value in reference.items() if key != "sha256"}

        saved_reference = validate_reference(saved_checkpoint, "saved")
        loaded_sha = loaded_checkpoint.get("sha256") if isinstance(loaded_checkpoint, dict) else None
        loaded_base = None
        loaded_is_resume_target = False
        if loaded_checkpoint is not None:
            if not isinstance(loaded_checkpoint, dict):
                raise ValueError("EX-41 resumed checkpoint reference is missing")
            loaded_sha = loaded_checkpoint.get("sha256")
            loaded_iteration = loaded_checkpoint.get("iteration")
            loaded_path = loaded_checkpoint.get("path")
            if (not isinstance(loaded_sha, str) or len(loaded_sha) != 64
                    or any(ch not in "0123456789abcdef" for ch in loaded_sha.lower())
                    or type(loaded_iteration) is not int
                    or not isinstance(loaded_path, str) or not loaded_path):
                raise ValueError("EX-41 resumed checkpoint reference is malformed")
            loaded_base = {key: value for key, value in loaded_checkpoint.items()
                           if key != "sha256"}
            if loaded_base == saved_reference:
                # Some restore callers compare before the resume hook updates
                # last_checkpoint; this remains a valid unchanged predecessor.
                pass
            elif (loaded_iteration == iteration
                  and Path(loaded_path).name == f"model_{iteration}.pt"):
                # ContinuousFixed.on_resume_checkpoint intentionally advances
                # the reference from the save-before-current predecessor to
                # the actual model_N file that starts this resumed process.
                if (saved_reference is not None
                        and set(saved_reference) != set(loaded_base)):
                    raise ValueError("EX-41 resumed checkpoint reference metadata differs")
                if saved_reference is not None and any(
                        saved_reference[key] != loaded_base[key]
                        for key in set(saved_reference) - {"iteration", "path"}):
                    raise ValueError("EX-41 resumed checkpoint reference metadata differs")
                loaded_is_resume_target = True
            else:
                raise ValueError("EX-41 resumed checkpoint reference differs from its saved iteration")
        elif saved_reference is not None:
            raise ValueError("EX-41 resume checkpoint reference is missing after restore")

        # The serialized pointer is the prior save (or absent); on resume the
        # live pointer is replaced with model_N by on_resume_checkpoint. Validate
        # those forms above, then compare the remaining stage state exactly.
        saved_stage["last_checkpoint"] = None
        loaded_stage["last_checkpoint"] = None
        if loaded_is_resume_target:
            checkpoint_reference = {"iteration": iteration,
                                    "path": loaded_checkpoint["path"],
                                    "sha256": loaded_sha}
    def normalization_group(state):
        recorded = state.get("normalization_state")
        if isinstance(recorded, dict):
            return recorded
        # Older checkpoints did not store a named normalization receipt.
        # Keep any actual running-stat tensors comparable without inventing
        # configuration or treating LayerNorm weights as running statistics.
        running = {}
        for prefix, key in (("policy", "model_state_dict"),
                            ("perception", "perception_state_dict")):
            values = state.get(key) or {}
            if isinstance(values, dict):
                for name, value in values.items():
                    lowered = name.lower()
                    if any(token in lowered for token in (
                            "running_mean", "running_std", "running_var",
                            "_mean", "_std", "_var", "_count")):
                        running[f"{prefix}.{name}"] = value
        return {"configuration": "not_recorded_in_legacy_checkpoint",
                "running_buffers": running}

    def boundary_group(curriculum, stage_state):
        effective = curriculum.get("effective") or {}
        config = curriculum.get("config_values") or {}
        return {
            "stage_state": stage_state,
            "last_boundary": curriculum.get("last_boundary"),
            "snapshot": curriculum.get("snapshot"),
            "applied_ids": curriculum.get("applied_ids"),
            "command_share_bias": effective.get("command_share_bias",
                                                  config.get("command_share_bias")),
            "shares": effective.get("shares"),
        }

    def w86_group(state, curriculum):
        explicit = state.get("ex41_w86_reward_weights")
        effective = curriculum.get("effective") or {}
        return explicit if explicit is not None else effective.get("reward_weights")

    def optimizer_group(state):
        return {key: state.get(key) for key in (
            "optimizer_state_dict", "perception_optimizer_state_dict")}

    def learning_rate_group(state):
        policy = state.get("optimizer_state_dict") or {}
        perception = state.get("perception_optimizer_state_dict") or {}
        return {
            "ppo_learning_rate": state.get("ppo_learning_rate"),
            "ppo_param_group_lrs": [group.get("lr") for group in policy.get("param_groups", [])],
            "perception_param_group_lrs": [group.get("lr") for group in perception.get("param_groups", [])],
        }

    saved_lr = expected.get("ppo_learning_rate")
    if not isinstance(saved_lr, (int, float)) or not math.isfinite(float(saved_lr)):
        raise ValueError("EX-41 resume PPO learning rate is missing or non-finite")
    if float(saved_lr) <= 1e-5:
        raise ValueError("EX-41 resume PPO learning rate is at or below the 1e-5 floor")
    for group_lr in learning_rate_group(expected)["ppo_param_group_lrs"]:
        if not isinstance(group_lr, (int, float)) or not math.isfinite(float(group_lr)) or float(group_lr) <= 1e-5:
            raise ValueError("EX-41 resume optimizer learning rate is at or below the 1e-5 floor")

    groups = {
        "policy_critic_weights": {"model_state_dict": expected.get("model_state_dict"),
                                  "perception_state_dict": expected.get("perception_state_dict")},
        "adam_moments": optimizer_group(expected),
        "learning_rate": learning_rate_group(expected),
        "normalization_running_stats": normalization_group(expected),
        "rng": expected.get("rng"),
        "curriculum_clock": {"stage_id": (saved_curriculum.get("effective") or {}).get("stage_id"),
                             "stage_pos": saved_stage.get("stage_pos"),
                             "iteration": saved_stage.get("iteration"),
                             "fixed_clock": saved_stage.get("fixed_clock"),
                             "domain_randomization": saved_curriculum.get("domain_randomization"),
                             "push_vmax_mps": saved_curriculum.get("push_vmax_mps")},
        "w72_boundary_and_command_share": boundary_group(saved_curriculum, saved_stage),
        "w86_reward_weights": w86_group(expected, saved_curriculum),
        "map_switch_rng_and_use_gt_frac": {"map_switch": expected.get("map_switch"),
                                            "last_use_gt_frac": expected.get("last_use_gt_frac")},
    }
    loaded_groups = {
        "policy_critic_weights": {"model_state_dict": actual.get("model_state_dict"),
                                  "perception_state_dict": actual.get("perception_state_dict")},
        "adam_moments": optimizer_group(actual),
        "learning_rate": learning_rate_group(actual),
        "normalization_running_stats": normalization_group(actual),
        "rng": actual.get("rng"),
        "curriculum_clock": {"stage_id": (loaded_curriculum.get("effective") or {}).get("stage_id"),
                             "stage_pos": loaded_stage.get("stage_pos"),
                             "iteration": loaded_stage.get("iteration"),
                             "fixed_clock": loaded_stage.get("fixed_clock"),
                             "domain_randomization": loaded_curriculum.get("domain_randomization"),
                             "push_vmax_mps": loaded_curriculum.get("push_vmax_mps")},
        "w72_boundary_and_command_share": boundary_group(loaded_curriculum, loaded_stage),
        "w86_reward_weights": w86_group(actual, loaded_curriculum),
        "map_switch_rng_and_use_gt_frac": {"map_switch": actual.get("map_switch"),
                                            "last_use_gt_frac": actual.get("last_use_gt_frac")},
    }
    result = {}
    for name, saved in groups.items():
        expected_sha = state_digest(saved)
        actual_sha = state_digest(loaded_groups[name])
        if expected_sha != actual_sha:
            if name == "curriculum_clock":
                before = saved
                after = loaded_groups[name]
                differing = sorted(key for key in set(before) | set(after)
                                   if state_digest(before.get(key)) != state_digest(after.get(key)))
                raise ValueError(f"EX-41 resume readback differs for curriculum_clock fields: {differing}")
            raise ValueError(f"EX-41 resume readback differs for {name}")
        result[name] = {"state": "matched", "sha256": expected_sha}
        if name == "learning_rate":
            result[name]["ppo_value"] = float(saved_lr)
            result[name]["above_floor_1e-5"] = True
        if name == "normalization_running_stats":
            norm = groups[name]
            result[name]["running_buffer_count"] = len(norm.get("running_buffers", {}))
            result[name]["configuration"] = norm.get("configuration", "recorded")
        if name == "map_switch_rng_and_use_gt_frac":
            result[name]["use_gt_frac_recorded"] = expected.get("last_use_gt_frac") is not None
    result["segment_index"] = {
        "state": "advanced_one_segment",
        "saved": saved_segment,
        "restored": loaded_segment,
    }
    if checkpoint_reference is not None:
        result["checkpoint_reference"] = checkpoint_reference
    return result


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
