"""CPU preflight for an EX-36 completed checkpoint used by a later basic-gait segment."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

import torch


PARENT_UPDATE = {"A": 3000, "B": 1500}
REQUIRED_STATE = ("model_state_dict", "optimizer_state_dict", "ppo_learning_rate",
                  "perception_state_dict", "perception_optimizer_state_dict", "adasmpl",
                  "env_state", "rng", "map_switch")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_parent(path: str | Path, arm: str, expected_sha256: str, *, require_done: bool = True) -> dict:
    """Check bytes, manifest, completed update, and states before any Kit startup."""
    if arm not in PARENT_UPDATE or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("EX-36 arm or expected parent SHA is invalid")
    checkpoint = Path(path).resolve(strict=True)
    expected_iter = PARENT_UPDATE[arm]
    if checkpoint.name != f"model_{expected_iter}.pt":
        raise ValueError("EX-36 parent checkpoint filename or iteration differs")
    actual_sha = sha256_file(checkpoint)
    if actual_sha != expected_sha256:
        raise ValueError("EX-36 parent checkpoint SHA mismatch")
    run_dir = checkpoint.parent
    manifest_path = run_dir / "manifest.json"
    start_path = run_dir / "basic_start_receipt.json"
    status_path = run_dir / "status.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    start = json.loads(start_path.read_text(encoding="utf-8"))
    if manifest.get("checkpoints", {}).get(checkpoint.name) != actual_sha:
        raise ValueError("EX-36 checkpoint is not recorded in the source manifest")
    run = manifest.get("run") or {}
    modes = manifest.get("modes") or {}
    name = run.get("name", "")
    if not name.startswith(f"EX-36{arm}-") or not run_dir.name.startswith(name + "_"):
        raise ValueError("EX-36 arm, manifest run name, and folder disagree")
    if (start.get("stage") != "main" or start.get("run_name") != name
            or start.get("env_seed") != 42 or start.get("command_seed") != 42
            or start.get("num_envs") != 3072 or start.get("terrain_policy") != "fixed_l02"
            or sum(start.get("terrain_levels_l0_l1_l2", [])) != 3072):
        raise ValueError("EX-36 start receipt does not establish the same L0..2 and seed contract")
    command = modes.get("command_settings") or {}
    if (modes.get("task") != "FootholdS2-Go2-S2-SB-v0" or modes.get("seed") != 42
            or modes.get("num_envs") != 3072 or modes.get("num_steps_per_env") != 24
            or modes.get("map_input") != "reconstruction" or modes.get("force_gt") is not True
            or not math.isclose(float(modes.get("p_map_off", -1)), 0.1)
            or command.get("command_mode") != "basic_gait"
            or command.get("command_contract") != "basic_gait_v1"
            or not command.get("clock_scatter")
            or not math.isclose(float(command.get("basic_new_share", -1)), 0.3)):
        raise ValueError("EX-36 source manifest changes a training or map-choice condition")
    if require_done:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if (status.get("state") != "done" or status.get("iter") != expected_iter
                or (manifest.get("progress") or {}).get("completed_updates", 0) < expected_iter + 1):
            raise ValueError("EX-36 parent run is not complete")
    state = torch.load(checkpoint, weights_only=False, map_location="cpu")
    own = state.get("sol23f") or {}
    pc = state.get("perception_cfg") or {}
    switch = state.get("map_switch") or {}
    missing = [key for key in REQUIRED_STATE if key not in state]
    if missing or state.get("format") != "foothold-start/1" or state.get("iter") != expected_iter:
        raise ValueError(f"EX-36 parent format, completed update, or states differ: {missing}")
    if (own.get("variant") != "SB_map_switch" or own.get("initial_snapshot")
            or own.get("map_input") != "reconstruction" or own.get("force_gt") is not True
            or own.get("depth_delay_ticks") != 1 or state.get("env_seed") != 42
            or pc.get("contract") != "basic_gait_v1" or pc.get("map_input") != "reconstruction"
            or pc.get("force_gt") is not True or not math.isclose(float(pc.get("p_map_off", -1)), 0.1)
            or not math.isclose(float(switch.get("p_map_off", -1)), 0.1)
            or switch.get("generator_state") is None):
        raise ValueError("EX-36 checkpoint variant, command, or map-choice state differs")
    levels = (state.get("env_state") or {}).get("terrain_levels")
    types = (state.get("env_state") or {}).get("terrain_types")
    if (not isinstance(levels, torch.Tensor) or levels.shape != (3072,) or
            not isinstance(types, torch.Tensor) or types.shape != (3072,) or
            bool((levels < 0).any()) or bool((levels > 2).any())):
        raise ValueError("EX-36 checkpoint does not preserve 3072 L0..2 terrain labels")
    if (not state["model_state_dict"] or not state["optimizer_state_dict"]
            or not state["perception_state_dict"] or not state["perception_optimizer_state_dict"]
            or not math.isfinite(float(state["ppo_learning_rate"]))
            or float(state["ppo_learning_rate"]) <= 0 or not state["adasmpl"] or not state["rng"]):
        raise ValueError("EX-36 checkpoint has empty weights, optimizer, LR, or RNG state")
    return {"arm": arm, "checkpoint": str(checkpoint), "sha256": actual_sha,
            "completed_update": expected_iter, "manifest_sha256": sha256_file(manifest_path),
            "start_receipt_sha256": sha256_file(start_path), "physical_resume_identical": False,
            "restored_by_runner": ["model_state_dict", "optimizer_state_dict", "ppo_learning_rate",
                                   "perception_state_dict", "perception_optimizer_state_dict", "adasmpl",
                                   "env_state", "rng", "map_switch"]}
