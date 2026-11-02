"""CPU-only EX-40 v7 continuation checks and argument preparation.

This module never launches or terminates a process. A lead-operated monitor may
use these checks after the original process has exited, then review the emitted
argv before starting a new segment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import math
import pickle
from pathlib import Path
import re

import torch

from foothold_s2.curriculum.continuous import Plan
from foothold_s2.ex40_launch import TABLE


TOTAL_ITERATIONS = 8001
TARGET_UPDATE = TOTAL_ITERATIONS - 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_deadline(expected_finish: str, end_by: str) -> None:
    expected = datetime.fromisoformat(expected_finish)
    deadline = datetime.fromisoformat(end_by)
    if expected.tzinfo is None or deadline.tzinfo is None:
        raise ValueError("expected finish and end-by need explicit time zones")
    if deadline < expected + timedelta(hours=24):
        raise ValueError("EX-40 end-by must leave at least 24 hours after expected finish")


def _stage_at(plan: Plan, iteration: int) -> int:
    active = 0
    for index, stage in enumerate(plan.stages):
        if stage.fixed_update <= iteration:
            active = index
    return active


def check_parent(path: str | Path, expected_sha256: str, *,
                 curriculum_path: str | Path = TABLE, arm: str = "B") -> dict:
    """Verify a numbered EX-40 checkpoint's identity and resumable state on CPU."""
    checkpoint = Path(path).resolve(strict=True)
    match = re.fullmatch(r"model_(\d+)\.pt", checkpoint.name)
    if not checkpoint.is_file() or match is None or len(expected_sha256) != 64:
        raise ValueError("EX-40 continuation needs a numbered model_N.pt and full SHA256")
    iteration = int(match.group(1))
    if not 0 <= iteration < TARGET_UPDATE:
        raise ValueError("EX-40 continuation checkpoint is at or beyond the target update")
    actual_sha = sha256(checkpoint)
    if actual_sha != expected_sha256.lower():
        raise ValueError("EX-40 continuation checkpoint SHA mismatch")

    run = checkpoint.parent
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    checkpoints = manifest.get("checkpoints") or {}
    if checkpoints.get(checkpoint.name) != actual_sha:
        raise ValueError("EX-40 checkpoint SHA is not pinned in manifest.json")
    modes = manifest.get("modes") or {}
    curriculum = modes.get("continuous_curriculum") or {}
    plan = Plan(curriculum_path, arm=arm)
    if (manifest.get("schema") != "foothold-manifest/1"
            or modes.get("contract") != "basic_gait_ex40"
            or curriculum.get("sha256") != plan.sha256
            or curriculum.get("effective_schedule_sha256") != plan.effective_sha256
            or curriculum.get("arm") != arm
            or curriculum.get("terrain_curriculum") != plan.terrain_curriculum
            or modes.get("num_envs") != 3072 or modes.get("seed") != 42
            or curriculum.get("promotion") != "fixed" or curriculum.get("shadow_gate") is not True
            or modes.get("command_settings", {}).get("command_mode") != "basic_gait"):
        raise ValueError("EX-40 checkpoint manifest differs from the pinned v7 treatment")
    cli = ((manifest.get("run") or {}).get("cli_args") or {})
    if (cli.get("max_iterations") != TOTAL_ITERATIONS
            or cli.get("curriculum_arm") != arm
            or cli.get("curriculum_kit_smoke") is True
            or cli.get("curriculum") is None):
        raise ValueError("EX-40 manifest CLI is not the v7 main run")

    try:
        state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    except (pickle.UnpicklingError, EOFError, RuntimeError, ValueError) as exc:
        raise ValueError(f"EX-40 checkpoint cannot be loaded: {type(exc).__name__}: {exc}") from exc
    if not isinstance(state, dict) or state.get("iter") != iteration:
        raise ValueError("EX-40 checkpoint filename and saved iteration differ")
    required_learning = ("model_state_dict", "perception_state_dict", "optimizer_state_dict",
                         "perception_optimizer_state_dict")
    if any(not isinstance(state.get(key), dict) or not state[key] for key in required_learning):
        raise ValueError("EX-40 checkpoint is missing policy, perception, or optimizer load state")
    lr = state.get("ppo_learning_rate")
    if not isinstance(lr, (int, float)) or isinstance(lr, bool) or not math.isfinite(lr) or lr <= 0:
        raise ValueError("EX-40 checkpoint PPO learning rate is missing or invalid")
    required = ("rng", "map_switch", "env_state", "continuous_curriculum", "adasmpl", "sol23f")
    if any(key not in state for key in required):
        raise ValueError("EX-40 checkpoint is missing training, map, environment, or curriculum state")
    if (state.get("format") != "foothold-start/1"
            or state["sol23f"].get("variant") != "SB_map_switch"
            or state["sol23f"].get("map_input") != "reconstruction"):
        raise ValueError("EX-40 checkpoint runner variant or map contract differs")
    if not all(key in state["rng"] for key in ("torch", "numpy", "python")):
        raise ValueError("EX-40 checkpoint global RNG states are incomplete")
    env_state = state["env_state"]
    if (not isinstance(env_state, dict)
            or "common_step_counter" not in env_state
            or "terrain_levels" not in env_state
            or "terrain_types" not in env_state
            or "command_generator_state" not in env_state):
        raise ValueError("EX-40 checkpoint lacks restorable terrain or command RNG state")
    for key in ("terrain_levels", "terrain_types"):
        value = env_state[key]
        if not isinstance(value, torch.Tensor) or value.numel() != 3072:
            raise ValueError(f"EX-40 checkpoint {key} does not contain all 3072 environments")
    segment = (modes.get("continuous_resume") or {}).get("segment_index", 0)
    if type(segment) is not int or segment < 0:
        raise ValueError("EX-40 manifest continuation segment is malformed")
    saved_terrain = state["continuous_curriculum"].get("terrain_receipt")
    if (not isinstance(saved_terrain, dict)
            or saved_terrain.get("policy") != plan.terrain_curriculum
            or saved_terrain.get("num_envs") != 3072
            or sum(saved_terrain.get("actual_counts_by_level", [])) != 3072):
        raise ValueError("EX-40 checkpoint actual terrain distribution receipt missing")
    levels = env_state["terrain_levels"].detach().to(device="cpu", dtype=torch.long).contiguous()
    types = env_state["terrain_types"].detach().to(device="cpu", dtype=torch.long).contiguous()
    actual_counts = torch.bincount(levels, minlength=len(saved_terrain["actual_counts_by_level"])).tolist()
    labels_sha = hashlib.sha256(levels.numpy().tobytes() + types.numpy().tobytes()).hexdigest()
    if (actual_counts != saved_terrain["actual_counts_by_level"]
            or labels_sha != saved_terrain.get("terrain_labels_sha256")
            or saved_terrain.get("level_min") != int(levels.min())
            or saved_terrain.get("level_max") != int(levels.max())):
        raise ValueError("EX-40 checkpoint terrain distribution receipt disagrees with saved env state")
    if plan.terrain_curriculum == "fixed_l02":
        if (saved_terrain.get("max_init_terrain_level") != 2
                or saved_terrain.get("promotion_enabled") is not False
                or saved_terrain.get("level_max", 99) > 2
                or any(saved_terrain["actual_counts_by_level"][3:])):
            raise ValueError("EX-40 fixed_l02 checkpoint contains a promoted environment")
    map_switch = state["map_switch"]
    if (not isinstance(map_switch, dict) or map_switch.get("p_map_off") != 0.1
            or map_switch.get("generator_state") is None):
        raise ValueError("EX-40 checkpoint lacks its map-switch shadow state")
    saved = state["continuous_curriculum"]
    saved_dr = saved.get("domain_randomization") if isinstance(saved, dict) else None
    expected_dr_sha = (modes.get("domain_randomization") or {}).get("config_sha256")
    from foothold_s2.curriculum.ex40_dr import dr_scale
    if (not isinstance(saved_dr, dict)
            or saved_dr.get("format") != "ex40-dr-runtime-readback/1"
            or saved_dr.get("config_sha256") != expected_dr_sha
            or saved_dr.get("last_update") != iteration
            or saved_dr.get("schedule_update") != iteration
            or not math.isclose(float(saved_dr.get("scale", -1)), dr_scale(iteration), abs_tol=1e-12)
            or not isinstance(saved_dr.get("com_baseline"), torch.Tensor)
            or saved_dr["com_baseline"].ndim != 3
            or not torch.isfinite(saved_dr["com_baseline"]).all()
            or not isinstance(saved_dr.get("motor_baselines"), dict)
            or not saved_dr["motor_baselines"]):
        raise ValueError("EX-40 checkpoint DR runtime state missing or inconsistent with update/config")
    for name, baseline in saved_dr["motor_baselines"].items():
        if (not isinstance(name, str) or not isinstance(baseline, dict)
                or not isinstance(baseline.get("effort_limit"), torch.Tensor)
                or not isinstance(baseline.get("saturation_effort"), torch.Tensor)
                or baseline["effort_limit"].shape != baseline["saturation_effort"].shape
                or not torch.isfinite(baseline["effort_limit"]).all()
                or not torch.isfinite(baseline["saturation_effort"]).all()
                or bool((baseline["effort_limit"] <= 0).any())
                or bool((baseline["saturation_effort"] <= 0).any())):
            raise ValueError("EX-40 checkpoint DR motor baseline is malformed")
    active = _stage_at(plan, iteration)
    if (not isinstance(saved, dict) or saved.get("format") != "foothold-w55-state/1"
            or saved.get("plan_sha256") != plan.sha256
            or saved.get("effective_sha256") != plan.effective_sha256
            or saved.get("active") != active
            or saved.get("stage_entry_iteration") != plan.stages[active].fixed_update
            or (active >= 1 and saved.get("b1_entry_iteration") != plan.stages[1].fixed_update)
            or (active == 0 and saved.get("b1_entry_iteration") is not None)):
        raise ValueError("EX-40 checkpoint stage, B1 origin, or shadow state differs from v7")
    if any(key not in saved for key in ("env_stage", "pending_gate", "seen_scores",
                                        "latest_score", "passes")):
        raise ValueError("EX-40 checkpoint is missing continuous shadow or per-environment stage state")
    env_stage = saved["env_stage"]
    if (not isinstance(env_stage, torch.Tensor) or env_stage.numel() != 3072
            or bool((env_stage > active).any()) or bool((env_stage < 0).any())):
        raise ValueError("EX-40 checkpoint per-environment stage state is malformed")
    if (bool(state["sol23f"].get("force_gt")) is not plan.stages[active].force_gt
            or bool(state["adasmpl"].get("force_gt")) is not plan.stages[active].force_gt):
        raise ValueError("EX-40 checkpoint map mode differs from its saved stage")
    return {"checkpoint": str(checkpoint), "checkpoint_sha256": actual_sha,
            "completed_update": iteration, "active_stage": plan.stages[active].id,
            "segment_index": segment,
            "stage_entry_iteration": saved["stage_entry_iteration"],
            "b1_entry_iteration": saved.get("b1_entry_iteration"),
            "remaining_updates": TOTAL_ITERATIONS - iteration - 1,
            "physical_resume_identical": False}


def newest_verified_checkpoint(run: str | Path, *, curriculum_path: str | Path = TABLE,
                               arm: str = "B") -> dict:
    root = Path(run).resolve(strict=True)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    entries = []
    for name, digest in (manifest.get("checkpoints") or {}).items():
        match = re.fullmatch(r"model_(\d+)\.pt", name)
        if match and int(match.group(1)) < TARGET_UPDATE and isinstance(digest, str):
            entries.append((int(match.group(1)), name, digest))
    rejected = []
    for iteration, name, digest in sorted(entries, reverse=True):
        path = root / name
        try:
            result = check_parent(path, digest, curriculum_path=curriculum_path, arm=arm)
            result["rejected_candidates"] = rejected
            return result
        except (OSError, ValueError, RuntimeError, EOFError, pickle.UnpicklingError,
                KeyError, TypeError, IndexError) as exc:
            rejected.append({"checkpoint": name, "reason": f"{type(exc).__name__}: {exc}"})
            continue
    detail = json.dumps(rejected, ensure_ascii=False, sort_keys=True)
    raise ValueError(f"no intact, manifest-pinned EX-40 checkpoint is resumable; rejected={detail}")


def source_decision(*, run: str | Path, shell_finished: bool, process_alive: bool | None,
                    curriculum_path: str | Path = TABLE, arm: str = "B") -> dict:
    """Return a safe wait/complete/resume decision without launching anything."""
    root = Path(run).resolve(strict=True)
    status = json.loads((root / "train_start_status.json").read_text(encoding="utf-8-sig"))
    if process_alive is True:
        return {"state": "waiting_for_original_exit", "status": status.get("state"),
                "iteration": status.get("iter")}
    if process_alive is None and not shell_finished and status.get("state") in ("running", "failed", "stopped_saved"):
        return {"state": "waiting_for_process_state", "status": status.get("state"),
                "iteration": status.get("iter")}
    if process_alive is None and status.get("state") not in ("done",):
        return {"state": "waiting_for_process_state", "status": status.get("state"),
                "iteration": status.get("iter")}
    if not shell_finished and status.get("state") == "running":
        return {"state": "waiting_for_terminal_receipt", "status": "running",
                "iteration": status.get("iter")}
    if status.get("state") == "done" and status.get("iter") == TARGET_UPDATE:
        return {"state": "already_complete", "completed_update": TARGET_UPDATE}
    try:
        checkpoint = newest_verified_checkpoint(root, curriculum_path=curriculum_path, arm=arm)
    except (OSError, ValueError) as exc:
        return {"state": "hold_no_verified_checkpoint", "reason": str(exc)}
    return {"state": "ready_to_continue", "source_status": status.get("state"),
            "source_iteration": status.get("iter"), **checkpoint}


def build_resume_args(launch_receipt: dict, parent: dict, *, end_by: str,
                      expected_finish: str, arm: str = "B") -> list[str]:
    """Prepare, but never execute, the same-treatment EX-40 continuation argv."""
    validate_deadline(expected_finish, end_by)
    if (launch_receipt.get("state") != "CPU_PREPARED_NOT_LAUNCHED"
            or launch_receipt.get("training_started") is not False):
        raise ValueError("resume source must be the original CPU-only launch receipt")
    verified_parent = check_parent(parent["checkpoint"], parent["checkpoint_sha256"], arm=arm)
    if verified_parent["completed_update"] != parent.get("completed_update", verified_parent["completed_update"]):
        raise ValueError("resume parent update number differs from its checkpoint")
    args = list(launch_receipt.get("argv") or [])
    required = ("--resume_from", "--basic-ex40-parent-sha")
    if any(flag in args for flag in required):
        raise ValueError("source EX-40 launch receipt must be the original scratch argv")
    if "--curriculum-kit-smoke" in args:
        raise ValueError("EX-40 smoke receipt cannot be used for continuation")
    for flag, value in (("--max_iterations", str(TOTAL_ITERATIONS)),
                        ("--curriculum-arm", arm)):
        if args.count(flag) != 1 or args[args.index(flag) + 1] != value:
            raise ValueError(f"source EX-40 receipt differs at {flag}")
    if args.count("--end-by") != 1:
        raise ValueError("source EX-40 receipt has no unique deadline")
    if args.count("--curriculum") != 1 or args[args.index("--command_mode") + 1] != "basic_gait":
        raise ValueError("source EX-40 receipt does not preserve the curriculum and command contract")
    table = Path(args[args.index("--curriculum") + 1]).resolve(strict=True)
    if Plan(table, arm=arm).sha256 != Plan(TABLE, arm=arm).sha256:
        raise ValueError("source EX-40 receipt curriculum differs from the v7 table")
    args[args.index("--end-by") + 1] = end_by
    args.extend(["--resume_from", parent["checkpoint"],
                 "--basic-ex40-parent-sha", parent["checkpoint_sha256"],
                 "--basic-ex40-segment-index", str(verified_parent["segment_index"] + 1)])
    return args


def consecutive_failure_action(history: list[dict], new_failure: bool) -> str:
    count = 0
    for row in reversed(history):
        if row.get("state") != "failed":
            break
        count += 1
    count = count + 1 if new_failure else 0
    return "stop_after_three_failures" if count >= 3 else "record_and_review"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    process = parser.add_mutually_exclusive_group()
    process.add_argument("--process-alive", dest="process_alive", action="store_true")
    process.add_argument("--process-dead", dest="process_alive", action="store_false")
    parser.set_defaults(process_alive=None)
    parser.add_argument("--shell-finished", action="store_true")
    parser.add_argument("--arm", choices=("A", "B"), default="B")
    args = parser.parse_args(argv)
    print(json.dumps(source_decision(run=args.run, shell_finished=args.shell_finished,
                                     process_alive=args.process_alive, arm=args.arm),
                     ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
