"""CPU-safe EX-42 train_start caller helpers.

This module wires approved plan/parent inputs to the existing StartRunner hook.
It does not grant launch authorization; the current EX-42 plan remains
preparation_only and train_start rejects it before AppLauncher is created.
"""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import EX42Runtime
from foothold_s2.curriculum.ex42_prep import validate_stage_zero_authorization


STAGE_ZERO_TASK_ID = "FootholdS2-Go2-S2-SB-v0"
STAGE_ZERO_UPDATES = 1000
STAGE_ZERO_NUM_ENVS = 3072
STAGE_ZERO_DEVICE = "cuda:1"


def validate_ex42_stage_zero_cli(*, plan_path: str | Path, approvals_path: str | Path,
                                 parent_manifest_path: str | Path, log_dir: str | Path,
                                 task: str, device: str, headless: bool, distributed: bool,
                                 max_iterations: int | None, num_envs: int | None,
                                 map_input: str | None, force_gt: bool,
                                 approved_switch: bool, resume_from: str | Path | None = None,
                                 self_resume: bool = False, resume_smoke: bool = False,
                                 resume_updates: int | None = None
                                 ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Validate the explicitly approved stage-zero CLI without importing Kit."""
    if approved_switch is not True:
        raise ValueError("EX-42 stage zero requires its explicit scoped approval switch")
    if resume_from and not self_resume:
        raise ValueError("EX-42 stage zero is not self-resume without its dedicated resume route")
    if self_resume and not resume_from:
        raise ValueError("EX-42 self-resume requires a manifest-pinned checkpoint")
    if resume_smoke and not self_resume:
        raise ValueError("EX-42 bounded resume smoke requires self-resume")
    if task != STAGE_ZERO_TASK_ID:
        raise ValueError("EX-42 stage-zero task differs from the approved task")
    valid_device = (device == STAGE_ZERO_DEVICE
                    or (resume_smoke and device == "cuda:0"))
    if not valid_device or headless is not True or distributed is not False:
        raise ValueError("EX-42 stage zero requires headless single-process cuda:1; only bounded resume smoke may use cuda:0")
    if max_iterations != STAGE_ZERO_UPDATES or num_envs != STAGE_ZERO_NUM_ENVS:
        raise ValueError("EX-42 stage zero is bounded to exactly 1000 updates and 3072 environments")
    if map_input not in (None, "reconstruction") or force_gt is not False:
        raise ValueError("EX-42 stage zero must consume reconstructed maps without forced GT")
    if resume_smoke:
        if type(resume_updates) is not int or not 1 <= resume_updates <= 5:
            raise ValueError("EX-42 resume smoke is bounded to one through five updates")
    elif resume_updates is not None:
        raise ValueError("EX-42 resume update override is only valid for bounded smoke")
    output = Path(log_dir).resolve()
    if output.exists():
        same_run_resume = (self_resume and not resume_smoke and resume_from is not None
                           and output.resolve() == Path(resume_from).resolve().parent)
        if not same_run_resume or not (output / "manifest.json").is_file():
            raise ValueError("EX-42 stage-zero output must be new, except same-run manifest-pinned resume")
    elif self_resume and not resume_smoke:
        raise ValueError("EX-42 full self-resume must continue in its source run directory")
    plan = EX42Plan.load(plan_path)
    checkpoint, parent_receipt = inspect_ex42_stage_zero_parent(
        plan=plan, approvals_path=approvals_path,
        parent_manifest_path=parent_manifest_path,
        expected_sha256=plan.document["stage_zero"]["parent"]["sha256"])
    if (parent_receipt["approval"]["state"] != "stage_zero_only_authorized"
            or parent_receipt["approval"]["later_stages_authorized"] is not False):
        raise ValueError("EX-42 stage-zero approval is not bounded to stage zero")
    return plan, checkpoint, parent_receipt, {
        "state": "stage_zero_preflight_passed",
        "task": task, "device": device, "num_envs": num_envs,
        "max_iterations": max_iterations, "map_input": "reconstruction",
        "force_gt": False, "output_dir": str(output),
        "production_launch_allowed": False,
        "later_stages_authorized": False,
        "self_resume": bool(self_resume),
        "resume_smoke": bool(resume_smoke),
        "resume_updates": resume_updates,
    }


def validate_ex42_stage_zero_resume(*, checkpoint_path: str | Path,
                                   manifest_path: str | Path,
                                   plan_sha256: str, approval_sha256: str,
                                   parent_receipt: dict[str, Any],
                                   maximum_updates: int = STAGE_ZERO_UPDATES,
                                   resume_smoke_updates: int | None = None,
                                   require_latest: bool = True) -> dict[str, Any]:
    """Validate a self-resume checkpoint against its manifest and W65 pins.

    The checkpoint is read on CPU. The caller must validate a fresh target run
    directory separately before creating it or starting Kit.
    """
    import torch

    path = Path(checkpoint_path).resolve(strict=True)
    manifest_file = Path(manifest_path).resolve(strict=True)
    match = re.fullmatch(r"model_(\d+)\.pt", path.name)
    if not path.is_file() or match is None:
        raise ValueError("EX-42 self-resume requires a numbered model_N.pt checkpoint")
    local_iteration = int(match.group(1))
    if not 0 < local_iteration < maximum_updates:
        raise ValueError("EX-42 self-resume checkpoint must be inside the approved stage-zero range")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("EX-42 self-resume source manifest is invalid")
    run = manifest.get("run")
    manifest_run_dir = run.get("log_dir") if isinstance(run, dict) else None
    if (not isinstance(manifest_run_dir, str)
            or Path(manifest_run_dir).resolve() != path.parent.resolve()
            or manifest_file.parent.resolve() != path.parent.resolve()):
        raise ValueError("EX-42 self-resume checkpoint and manifest must belong to the same run directory")
    checkpoints = manifest.get("checkpoints")
    expected_sha = checkpoints.get(path.name) if isinstance(checkpoints, dict) else None
    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if not isinstance(expected_sha, str) or expected_sha != actual_sha:
        raise ValueError("EX-42 self-resume checkpoint SHA is absent or differs from its source manifest")
    progress = manifest.get("progress")
    if (not isinstance(progress, dict)
            or type(progress.get("completed_updates")) is not int
            or progress["completed_updates"] < local_iteration):
        raise ValueError("EX-42 self-resume source manifest does not publish this checkpoint iteration")
    if require_latest and progress["completed_updates"] != local_iteration:
        raise ValueError("EX-42 same-run self-resume checkpoint is not the manifest's latest completed update")
    saved = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(saved, dict) or saved.get("format") != "foothold-start/1":
        raise ValueError("EX-42 self-resume file is not a START checkpoint")
    if saved.get("iter") != local_iteration:
        raise ValueError("EX-42 self-resume filename and checkpoint iteration differ")
    required = ("model_state_dict", "optimizer_state_dict", "ppo_learning_rate",
                "perception_state_dict", "perception_optimizer_state_dict", "adasmpl",
                "normalization_state", "rng", "map_switch", "env_state",
                "continuous_curriculum", "ex42_parent_transfer")
    missing = [key for key in required if saved.get(key) is None]
    if missing:
        raise ValueError("EX-42 self-resume lacks required state: " + ", ".join(missing))
    curriculum = saved["continuous_curriculum"]
    transfer = saved["ex42_parent_transfer"]
    expected_parent = parent_receipt.get("parent_sha256")
    if (not isinstance(curriculum, dict)
            or curriculum.get("format") != "foothold-ex42-stage-zero-state/1"
            or curriculum.get("iteration") != local_iteration
            or curriculum.get("maximum_updates") != maximum_updates
            or curriculum.get("plan_sha256") != plan_sha256
            or curriculum.get("approval_sha256") != approval_sha256
            or curriculum.get("parent_sha256") != expected_parent
            or curriculum.get("stage_id") != "EX42_0_T0_prime"
            or curriculum.get("dr_scale") != 1.0
            or curriculum.get("finished") is not False):
        raise ValueError("EX-42 self-resume curriculum pins or stage identity differ")
    if (not isinstance(transfer, dict)
            or transfer.get("parent_sha256") != expected_parent
            or transfer.get("parent_cumulative_update") != 12000
            or transfer.get("map_input") != "reconstruction"
            or transfer.get("force_gt") is not False):
        raise ValueError("EX-42 self-resume pinned EX-41 parent transfer differs")
    if (not isinstance(saved["map_switch"], dict)
            or saved["map_switch"].get("generator_state") is None
            or not isinstance(saved["rng"], dict)
            or any(key not in saved["rng"] for key in ("torch", "numpy", "python"))):
        raise ValueError("EX-42 self-resume RNG or map-switch state is incomplete")
    remaining = maximum_updates - local_iteration
    if resume_smoke_updates is not None:
        if (type(resume_smoke_updates) is not int
                or not 1 <= resume_smoke_updates <= min(5, remaining)):
            raise ValueError("EX-42 bounded resume updates exceed the five-update or stage limit")
        updates = resume_smoke_updates
    else:
        updates = remaining
    return {
        "state": "manifest_checkpoint_self_resume_verified",
        "checkpoint_path": str(path), "checkpoint_sha256": actual_sha,
        "source_manifest_path": str(manifest_file),
        "source_manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
        "source_manifest_completed_updates": progress["completed_updates"],
        "source_manifest_total_env_steps": int(progress.get("total_env_steps", 0)),
        "local_update_origin": local_iteration,
        "first_resumed_local_update": local_iteration + 1,
        "cumulative_update_origin": 12000 + local_iteration,
        "first_resumed_cumulative_update": 12001 + local_iteration,
        "maximum_updates": maximum_updates, "requested_updates": updates,
        "remaining_after_resume": maximum_updates - local_iteration - updates,
        "plan_sha256": plan_sha256, "approval_sha256": approval_sha256,
        "parent_sha256": expected_parent,
        "restored_groups": ["policy_and_critic", "ppo_optimizer", "learning_rate",
                            "perception", "perception_optimizer", "adasmpl",
                            "normalization", "rng", "curriculum", "map_switch",
                            "environment_terrain_and_command_rng"],
    }


def validate_ex42_stage_zero_chain_output(log_dir: str | Path, *,
                                          plan_sha256: str,
                                          parent_sha256: str,
                                          allow_existing_run: bool = False) -> dict[str, Any]:
    """Accept only the startup receipt just written by this validated chain.

    The initial CLI preflight requires a nonexistent output directory. Chain
    construction then creates that directory and writes this single receipt
    before Kit starts, so the post-chain guard must validate that exact file
    rather than treating the expected directory as stale output.
    """
    source = Path(log_dir)
    if source.is_symlink():
        raise ValueError("EX-42 stage-zero chain output is not a real directory")
    output = source.resolve(strict=True)
    if not output.is_dir():
        raise ValueError("EX-42 stage-zero chain output is not a real directory")
    entries = list(output.iterdir())
    if (not allow_existing_run and
            (len(entries) != 1 or entries[0].name != "startup_receipt.json"
             or not entries[0].is_file() or entries[0].is_symlink())):
        raise ValueError("EX-42 stage-zero chain output has unexpected contents")
    if (allow_existing_run and not (output / "startup_receipt.json").is_file()):
        raise ValueError("EX-42 stage-zero chain output has unexpected contents")
    if (output / "startup_receipt.json").is_symlink():
        raise ValueError("EX-42 stage-zero startup receipt must not be a symlink")
    try:
        receipt = json.loads((output / "startup_receipt.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("EX-42 stage-zero chain startup receipt is unreadable") from exc
    if not isinstance(receipt, dict):
        raise ValueError("EX-42 stage-zero chain startup receipt is not an object")
    parent = receipt.get("parent")
    if (receipt.get("state") != "chain_ready_not_launch_authorized"
            or receipt.get("experiment") != "EX-42"
            or receipt.get("production_launch_allowed") is not False
            or receipt.get("plan_sha256") != plan_sha256
            or not isinstance(parent, dict)
            or parent.get("checkpoint_sha256") != parent_sha256):
        raise ValueError("EX-42 stage-zero startup receipt identity differs")
    return {"state": "chain_startup_receipt_verified",
            "path": str(output / "startup_receipt.json"), "plan_sha256": plan_sha256,
            "parent_sha256": parent_sha256}


def build_stage_zero_chain_with_receipt_checks(log_dir: str | Path, *,
                                               plan_sha256: str,
                                               parent_sha256: str,
                                               allow_existing_run: bool,
                                               builder: Any) -> tuple[Any, dict[str, Any]]:
    """Validate an existing receipt before chain construction and its output after.

    Same-run self-resume reuses a directory whose receipt predates this process.
    Validate that receipt before the chain constructor can atomically replace it,
    then validate the resulting receipt again before AppLauncher is imported.
    """
    receipt_path = Path(log_dir).resolve() / "startup_receipt.json"
    previous = None
    previous_sha256 = None
    if allow_existing_run:
        previous = validate_ex42_stage_zero_chain_output(
            log_dir, plan_sha256=plan_sha256, parent_sha256=parent_sha256,
            allow_existing_run=True)
        previous_sha256 = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    chain = builder()
    current = validate_ex42_stage_zero_chain_output(
        log_dir, plan_sha256=plan_sha256, parent_sha256=parent_sha256,
        allow_existing_run=allow_existing_run)
    current_sha256 = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    return chain, {
        "state": "startup_receipt_checked_before_and_after_chain_construction",
        "previous": previous,
        "previous_sha256": previous_sha256,
        "current": current,
        "current_sha256": current_sha256,
        "receipt_changed": previous_sha256 is not None and previous_sha256 != current_sha256,
    }


def restore_stage_zero_resume_terrain_before_reset(env: Any,
                                                   checkpoint: dict[str, Any]) -> dict[str, Any]:
    """Install checkpoint terrain selection before the env's real reset event.

    Isaac Lab's reset_root_state_uniform reads scene.env_origins while placing
    the robot. Restoring levels/origins only later in StartRunner.load leaves
    every root pose at the first-reset origin, so the saved terrain and pose
    disagree. This pre-reset restore makes the existing reset event authoritative.
    """
    import torch

    raw = getattr(env, "unwrapped", env)
    scene = getattr(raw, "scene", None)
    terrain = getattr(scene, "terrain", None)
    saved = checkpoint.get("env_state") if isinstance(checkpoint, dict) else None
    if terrain is None or not isinstance(saved, dict):
        raise ValueError("EX-42 resume cannot restore terrain before reset")
    levels_dst = getattr(terrain, "terrain_levels", None)
    types_dst = getattr(terrain, "terrain_types", None)
    origins_grid = getattr(terrain, "terrain_origins", None)
    active_origins = getattr(terrain, "env_origins", None)
    if any(value is None for value in (levels_dst, types_dst, origins_grid, active_origins)):
        raise ValueError("EX-42 resume terrain selection tensors are unavailable")
    levels_src = saved.get("terrain_levels")
    types_src = saved.get("terrain_types")
    if levels_src is None or types_src is None:
        raise ValueError("EX-42 resume checkpoint lacks saved terrain levels/types")
    levels_src = torch.as_tensor(levels_src)
    types_src = torch.as_tensor(types_src)
    if levels_src.ndim != 1 or types_src.ndim != 1 or levels_src.shape != types_src.shape:
        raise ValueError("EX-42 resume checkpoint terrain levels/types have invalid shapes")
    count = int(levels_dst.numel())
    if levels_src.numel() != count:
        raise ValueError("EX-42 resume terrain selection env count differs")
    levels = levels_src.to(device=levels_dst.device, dtype=levels_dst.dtype)
    terrain_types = types_src.to(device=types_dst.device, dtype=types_dst.dtype)
    if (bool((levels < 0).any()) or bool((levels >= origins_grid.shape[0]).any())
            or bool((terrain_types < 0).any())
            or bool((terrain_types >= origins_grid.shape[1]).any())):
        raise ValueError("EX-42 resume checkpoint terrain selection is out of bounds")
    levels_dst.copy_(levels)
    types_dst.copy_(terrain_types)
    restored_origins = origins_grid[levels, terrain_types].to(
        device=active_origins.device, dtype=active_origins.dtype)
    active_origins.copy_(restored_origins)
    scene_origins = getattr(scene, "env_origins", None)
    if scene_origins is None:
        raise ValueError("EX-42 resume scene origins are unavailable before reset")
    if not torch.equal(scene_origins, restored_origins):
        try:
            scene_origins.copy_(restored_origins)
        except (AttributeError, RuntimeError) as exc:
            raise ValueError("EX-42 resume scene origins cannot be aligned before reset") from exc
    if not torch.equal(scene_origins, restored_origins):
        raise ValueError("EX-42 resume scene origins differ before reset")
    levels_cpu = levels.detach().to("cpu", dtype=torch.int64)
    types_cpu = terrain_types.detach().to("cpu", dtype=torch.int64)
    level_values, level_counts = torch.unique(levels_cpu, return_counts=True)
    type_values, type_counts = torch.unique(types_cpu, return_counts=True)
    return {
        "state": "checkpoint_terrain_selection_applied_before_reset",
        "restored_before_reset": True,
        "env_count": count,
        "level_counts": {str(int(k)): int(v) for k, v in zip(level_values.tolist(), level_counts.tolist())},
        "type_counts": {str(int(k)): int(v) for k, v in zip(type_values.tolist(), type_counts.tolist())},
    }


def build_stage_zero_resume_root_xy_readback(env: Any, *,
                                             pose_range: dict[str, tuple[float, float]]) -> dict[str, Any]:
    """Measure all resumed roots against their selected tile origins before rollout."""
    import torch

    raw = getattr(env, "unwrapped", env)
    scene = getattr(raw, "scene", None)
    robot = None
    try:
        robot = scene["robot"]
    except (TypeError, KeyError, AttributeError):
        robot = getattr(scene, "robot", None)
    origins = getattr(scene, "env_origins", None)
    root = getattr(getattr(robot, "data", None), "root_pos_w", None)
    if origins is None or root is None or root.ndim != 2 or root.shape[1] < 2:
        raise ValueError("EX-42 resume root/origin readback is unavailable")
    if origins.ndim != 2 or origins.shape[1] < 2 or origins.shape[0] != root.shape[0]:
        raise ValueError("EX-42 resume root/origin readback shapes differ")
    if not {"x", "y"}.issubset(pose_range):
        raise ValueError("EX-42 reset pose ranges must include x and y")
    delta = (root[:, :2] - origins[:, :2]).detach()
    distance = torch.linalg.vector_norm(delta, dim=1)
    if not bool(torch.isfinite(distance).all()):
        raise ValueError("EX-42 resume root/origin distances are not finite")
    x_bounds = tuple(float(value) for value in pose_range["x"])
    y_bounds = tuple(float(value) for value in pose_range["y"])
    if len(x_bounds) != 2 or len(y_bounds) != 2:
        raise ValueError("EX-42 reset pose ranges must be two-value bounds")
    tolerance = 1e-4
    outside = ((delta[:, 0] < x_bounds[0] - tolerance)
               | (delta[:, 0] > x_bounds[1] + tolerance)
               | (delta[:, 1] < y_bounds[0] - tolerance)
               | (delta[:, 1] > y_bounds[1] + tolerance))
    sorted_distances = distance.sort().values
    p95_index = max(0, int(0.95 * (sorted_distances.numel() - 1)))
    root_ids = torch.nonzero(outside, as_tuple=False).flatten().detach().to("cpu").tolist()
    return {
        "state": "root_xy_checked_against_restored_env_origins",
        "env_count": int(root.shape[0]),
        "distance_xy_m": {
            "min": float(sorted_distances[0].item()),
            "mean": float(distance.mean().item()),
            "p95": float(sorted_distances[p95_index].item()),
            "max": float(sorted_distances[-1].item()),
        },
        "reset_pose_bounds_xy_m": {"x": list(x_bounds), "y": list(y_bounds)},
        "outside_reset_bounds_count": len(root_ids),
        "outside_reset_bounds_env_ids_first_16": root_ids[:16],
    }


def load_ex42_stage_zero_source(plan: EX42Plan, *, arm: str = "B"):
    """Read the pinned EX-41 T0-prime stage as the stage-zero config source."""
    from foothold_s2.curriculum.continuous import load_plan

    source_path = plan.path.parent / plan.document["stage_zero"]["source"]["path"]
    source = load_plan(source_path, arm=arm)
    if not getattr(source, "is_ex41", False):
        raise ValueError("EX-42 stage-zero source did not load as an EX-41 plan")
    stage = next((row for row in source.stages if row.id == "T0_prime"), None)
    if stage is None:
        raise ValueError("EX-42 T0-prime source stage is absent")
    zero = plan.document["stage_zero"]
    comparisons = {
        "shares": (stage.shares, zero["shares"]),
        "ranges": ({key: tuple(value) for key, value in stage.ranges.items()},
                   {key: tuple(value) for key, value in zero["ranges"].items()}),
        "force_gt": (stage.force_gt, zero["force_gt"]),
    }
    for name, (actual, expected) in comparisons.items():
        if actual != expected:
            raise ValueError(f"EX-42 stage-zero source {name} changed after plan validation")
    return source, stage


def make_ex42_stage_zero_plan_view(source_plan: Any, stage: Any,
                                   parent_receipt: dict[str, Any]):
    """Provide EX-41's existing config adapters the approved single T0-prime stage."""
    return SimpleNamespace(
        is_ex41=True, stages=[stage], domain_randomization=source_plan.domain_randomization,
        initial_dr_scale=1.0, stand_cfg=source_plan.stand_cfg,
        heading_cfg=source_plan.heading_cfg, terrain_curriculum="performance",
        fixed_schedule=source_plan.fixed_schedule,
        parent_sha256=parent_receipt["parent_sha256"], parent_update=12000,
        ex42_stage_zero=True, parent_receipt=dict(parent_receipt),
    )


class EX42StageZeroRuntime:
    """Single bounded T0-prime runtime, with explicit saved continuation identity."""

    uses_one_based_updates = True
    is_ex42_stage_zero = True

    def __init__(self, *, stage_zero_plan: Any, plan_sha256: str,
                 approval_sha256: str, parent_sha256: str, maximum_updates: int = 1000,
                 push_vmax_mps: float):
        if maximum_updates != STAGE_ZERO_UPDATES:
            raise ValueError("EX-42 stage-zero runtime must remain bounded to 1000 updates")
        self.plan = SimpleNamespace(is_ex41=False, stages=stage_zero_plan.stages)
        self.plan_sha256 = plan_sha256
        self.approval_sha256 = approval_sha256
        self.parent_sha256 = parent_sha256
        self.maximum_updates = maximum_updates
        if (not isinstance(push_vmax_mps, (int, float))
                or not math.isfinite(float(push_vmax_mps)) or float(push_vmax_mps) <= 0):
            raise ValueError("EX-42 stage-zero parent push Vmax is invalid")
        self.push_vmax_mps = float(push_vmax_mps)
        self.stage_id = "EX42_0_T0_prime"
        self.stage_config = stage_zero_plan.stages[0]
        self.effective = {"stage_id": self.stage_id, "dr_scale": 1.0,
                          "terrain": {"policy": "performance", "level_cap": 5}}
        self.iteration = 0
        self._last_boundary = None
        self.finished = False
        self.command_samples = 0
        self.map_reset_counts: dict[str, int] = {"gt": 0, "pred": 0, "off": 0}
        self.runner = None
        self.env = None
        self.pre_step_count = 0
        self.post_step_count = 0
        self._step_pending = False

    def attach_environment(self, env: Any, command_term: Any) -> None:
        import torch

        raw = getattr(env, "unwrapped", env)
        self.env = raw
        self.env_stage = torch.zeros(raw.num_envs, dtype=torch.long, device=raw.device)
        command_term.stage_runtime = self
        raw._ex42_stage_id = self.stage_id
        raw._ex42_stage_config = {"id": self.stage_id, "source": "T0_prime"}
        raw._ex41_terrain = {"policy": "performance", "level_cap": 5}
        raw._ex40_dr_scale = 1.0
        raw._ex41_push_vmax_mps = self.push_vmax_mps

    def attach_runner(self, runner: Any) -> None:
        if runner.log_dir is None or self.env is None:
            raise ValueError("EX-42 stage-zero runtime requires its environment and run directory")
        self.runner = runner
        runner.continuous_curriculum = self

    def on_reset(self, env_ids: Any) -> None:
        return None

    def record_command_sample(self, env_ids: Any, commands: Any, slots: Any,
                              heading: Any) -> None:
        self.command_samples += int(len(env_ids))

    def on_update_start(self, update: int) -> None:
        if type(update) is not int or not 1 <= update <= self.maximum_updates:
            raise ValueError("EX-42 stage-zero update is outside its approved 1..1000 range")
        self.iteration = update
        if self.env is not None:
            raw = self.env
            raw._ex42_stage_id = self.stage_id
            raw._ex40_dr_scale = 1.0
            raw._ex41_push_vmax_mps = self.push_vmax_mps

    def record_pre_step(self) -> None:
        if self.env is None or self.runner is None:
            raise RuntimeError("EX-42 stage-zero step recorder is not attached")
        if self._step_pending:
            raise RuntimeError("EX-42 stage-zero pre-step was recorded twice")
        self._step_pending = True
        self.pre_step_count += 1

    def record_post_step(self, done: Any) -> None:
        if not self._step_pending:
            raise RuntimeError("EX-42 stage-zero post-step has no matching pre-step")
        shape = getattr(done, "shape", None)
        if shape is None or len(shape) != 1 or int(shape[0]) != int(self.env.num_envs):
            raise ValueError("EX-42 stage-zero done vector must match the environment batch")
        self._step_pending = False
        self.post_step_count += 1

    def flush_consumption(self, update: int) -> None:
        if update != self.iteration:
            raise ValueError("EX-42 stage-zero command consumption iteration differs")

    def record_map_reset(self, env_ids: Any, use_gt: Any, map_off: Any = None) -> None:
        import torch

        values = torch.as_tensor(use_gt).detach().to(device="cpu", dtype=torch.bool).flatten()
        off = (torch.zeros_like(values) if map_off is None else
               torch.as_tensor(map_off).detach().to(device="cpu", dtype=torch.bool).flatten())
        if off.shape != values.shape:
            raise ValueError("EX-42 stage-zero map source vectors differ")
        self.map_reset_counts["off"] += int(off.sum())
        self.map_reset_counts["gt"] += int((values & ~off).sum())
        self.map_reset_counts["pred"] += int((~values & ~off).sum())

    def state_dict(self) -> dict[str, Any]:
        return {"format": "foothold-ex42-stage-zero-state/1",
                "stage_id": self.stage_id, "iteration": self.iteration,
                "maximum_updates": self.maximum_updates, "dr_scale": 1.0,
                "plan_sha256": self.plan_sha256,
                "approval_sha256": self.approval_sha256,
                "parent_sha256": self.parent_sha256,
                "terrain": {"policy": "performance", "level_cap": 5},
                "command_samples": self.command_samples,
                "push_vmax_mps": self.push_vmax_mps,
                "pre_step_count": self.pre_step_count,
                "post_step_count": self.post_step_count,
                "map_reset_counts": dict(self.map_reset_counts),
                "finished": False}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        expected = self.state_dict()
        for key in ("format", "stage_id", "maximum_updates", "plan_sha256",
                    "approval_sha256", "parent_sha256", "dr_scale", "terrain",
                    "push_vmax_mps"):
            if state.get(key) != expected[key]:
                raise ValueError(f"EX-42 stage-zero continuation {key} differs")
        iteration = state.get("iteration")
        if type(iteration) is not int or not 0 <= iteration <= self.maximum_updates:
            raise ValueError("EX-42 stage-zero continuation iteration is invalid")
        self.iteration = iteration
        self.command_samples = int(state.get("command_samples", 0))
        self.pre_step_count = int(state.get("pre_step_count", 0))
        self.post_step_count = int(state.get("post_step_count", 0))
        if self.pre_step_count != self.post_step_count:
            raise ValueError("EX-42 stage-zero continuation has an incomplete environment step")
        counts = state.get("map_reset_counts")
        if not isinstance(counts, dict) or set(counts) != {"gt", "pred", "off"}:
            raise ValueError("EX-42 stage-zero map reset counts are invalid")
        self.map_reset_counts = {key: int(counts[key]) for key in ("gt", "pred", "off")}

    def on_resume_checkpoint(self, path: str | Path, iteration: int) -> None:
        if iteration != self.iteration:
            raise ValueError("EX-42 stage-zero checkpoint iteration differs from saved curriculum")

    def on_checkpoint(self, iteration: int, checkpoint: str | Path) -> None:
        if iteration != self.iteration:
            raise ValueError("EX-42 stage-zero checkpoint did not consume the latest update")
        self.last_checkpoint = {"path": str(Path(checkpoint).resolve()), "iteration": iteration}


def build_stage_zero_reset_readback(env: Any, dr_runtime: Any,
                                   env_contract: dict[str, Any]) -> dict[str, Any]:
    """Build JSON-safe first-reset evidence from the live env and config contract.

    ``attach_runtime`` returns a W86Runtime adapter, which is intentionally not
    serialized. Its JSON-safe registration contract comes from
    ``prepare_ex41_env_cfg``; the live attachment is reported separately.
    """
    raw = getattr(env, "unwrapped", env)
    w86_contract = env_contract.get("w86")
    if not isinstance(w86_contract, dict):
        raise ValueError("EX-42 stage-zero W86 registration contract is missing")
    if getattr(raw, "_ex41_w86", None) is None:
        raise ValueError("EX-42 stage-zero W86 runtime is not attached")
    return {
        "stage_id": raw._ex42_stage_id,
        "dr_scale": raw._ex40_dr_scale,
        "runtime_dr_scale": float(dr_runtime.scale),
        "initial_scale_wrapper": env_contract["initial_dr"],
        "terrain": env_contract["terrain"],
        "w86": w86_contract,
        "w86_attached": True,
        "pose_cmd_configured": True,
        "map_input": "reconstruction",
        "force_gt": False,
        "reset_event_samples": getattr(raw, "_ex40_dr_samples", {}),
        "push_vmax_mps": getattr(raw, "_ex41_push_vmax_mps", None),
        "lin_vel_z_weight": _runtime_reward_weight(raw, "lin_vel_z"),
    }


def _runtime_reward_weight(env: Any, name: str) -> float:
    manager = getattr(env, "reward_manager", None)
    if manager is None:
        raise ValueError("EX-42 stage-zero reward manager is unavailable")
    return float(manager.get_term_cfg(name).weight)


def apply_stage_zero_parent_reward_contract(env_cfg: Any, *,
                                           parent_sha256: str,
                                           parent_update: int) -> dict[str, Any]:
    """Keep the approved EX-41 m6000 parent reward term unchanged for stage zero."""
    if parent_sha256 != "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613" or parent_update != 6000:
        raise ValueError("EX-42 stage-zero reward transfer requires the pinned EX-41 m6000 parent")
    term = getattr(getattr(env_cfg, "rewards", None), "lin_vel_z", None)
    if term is None or not hasattr(term, "weight"):
        raise ValueError("EX-42 stage-zero config lacks the parent lin_vel_z reward term")
    term.weight = 0.0
    return {"term": "lin_vel_z", "weight": 0.0,
            "source": "EX-41 m6000 runtime readback", "parent_sha256": parent_sha256}


def apply_stage_zero_parent_reward_manager(env: Any, *,
                                           parent_sha256: str,
                                           parent_update: int) -> dict[str, Any]:
    """Apply the same parent reward term to the live manager before first reset."""
    if parent_sha256 != "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613" or parent_update != 6000:
        raise ValueError("EX-42 stage-zero reward transfer requires the pinned EX-41 m6000 parent")
    raw = getattr(env, "unwrapped", env)
    manager = getattr(raw, "reward_manager", None)
    if manager is None:
        raise ValueError("EX-42 stage-zero live reward manager is unavailable")
    cfg = manager.get_term_cfg("lin_vel_z")
    cfg.weight = 0.0
    manager.set_term_cfg("lin_vel_z", cfg)
    actual = float(manager.get_term_cfg("lin_vel_z").weight)
    if actual != 0.0:
        raise ValueError("EX-42 stage-zero live lin_vel_z reward did not match parent")
    return {"term": "lin_vel_z", "weight": actual,
            "source": "EX-41 m6000 runtime readback", "parent_sha256": parent_sha256}


class EX42StageZeroDRReadback:
    """EX-40 event readback fixed at the approved EX-42 stage-zero DR scale."""

    def __init__(self, base: Any, push_vmax_mps: float):
        if (not isinstance(push_vmax_mps, (int, float))
                or not math.isfinite(float(push_vmax_mps)) or float(push_vmax_mps) <= 0):
            raise ValueError("EX-42 stage-zero push Vmax is invalid")
        self.base = base
        self.env = base.env
        self.ranges = base.ranges
        self.push_vmax_mps = float(push_vmax_mps)
        self.scale = 1.0
        self.env._ex40_dr_scale = 1.0
        self.env._ex41_push_vmax_mps = self.push_vmax_mps

    def update_start(self, update: int) -> None:
        if type(update) is not int or update < 1:
            raise ValueError("EX-42 stage-zero DR update must be a positive integer")
        self.base.update_start(update)
        self.base.scale = 1.0
        self.scale = 1.0
        self.env._ex40_dr_scale = 1.0
        self.env._ex41_push_vmax_mps = self.push_vmax_mps

    def summary(self) -> dict[str, Any]:
        result = self.base.summary()
        result["scale"] = 1.0
        result["target_ranges"]["push_velocity"] = {
            "mode": "radial_magnitude_and_heading", "vmax_mps": self.push_vmax_mps,
            "legacy_axis_ranges_ignored": True}
        result["target_ranges"]["push_vmax_mps"] = self.push_vmax_mps
        result["push_schedule"] = {"stage_id": "T0_prime", "vmax_mps": self.push_vmax_mps,
                                    "independent_of_dr_scale": True,
                                    "source": "pinned EX-41 m6000 checkpoint"}
        return result


def configure_ex42_stage_zero_train_cfg(train_cfg: dict[str, Any],
                                         checkpoint: dict[str, Any], *,
                                         parent_path: str | Path,
                                         parent_sha256: str) -> dict[str, Any]:
    """Match the saved learner/perception contract while bounding stage zero."""
    saved_cfg = checkpoint.get("perception_cfg")
    if not isinstance(saved_cfg, dict):
        raise ValueError("EX-42 stage-zero parent perception config is missing")
    if saved_cfg.get("map_input") != "reconstruction" or saved_cfg.get("force_gt") is not False:
        raise ValueError("EX-42 stage zero requires the saved reconstruction/PRED mode")
    cfg = dict(train_cfg)
    cfg["perception"] = dict(saved_cfg)
    cfg["ex41_pose_commands"] = True
    cfg["ex41_w86_required"] = True
    cfg["ex41_critic_mirror"] = False
    cfg["ex42_stage_zero_parent"] = {"path": str(Path(parent_path).resolve()),
                                    "sha256": parent_sha256,
                                    "local_update": 6000,
                                    "cumulative_update": 12000}
    cfg["max_iterations"] = STAGE_ZERO_UPDATES
    cfg["save_interval"] = 50
    parent_sha = cfg["ex42_stage_zero_parent"]["sha256"]
    if parent_sha is not None and not re.fullmatch(r"[0-9a-f]{64}", parent_sha):
        raise ValueError("EX-42 stage-zero parent transfer SHA is malformed")
    if not math.isfinite(float(checkpoint.get("ppo_learning_rate", float("nan")))):
        raise ValueError("EX-42 stage-zero parent learning rate is invalid")
    curriculum_state = checkpoint.get("continuous_curriculum")
    push_vmax = curriculum_state.get("push_vmax_mps") if isinstance(curriculum_state, dict) else None
    if (not isinstance(push_vmax, (int, float)) or not math.isfinite(float(push_vmax))
            or float(push_vmax) <= 0):
        raise ValueError("EX-42 stage-zero parent push Vmax is missing or invalid")
    cfg["ex42_stage_zero_push_vmax_mps"] = float(push_vmax)
    return cfg


def make_score_argv_factory(serialized: str):
    """Parse a JSON argv vector with one explicit {iteration} placeholder."""
    try:
        template = json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise ValueError("EX-42 P1 score command must be a JSON argv array") from exc
    if (not isinstance(template, list) or not template
            or any(not isinstance(part, str) or not part for part in template)):
        raise ValueError("EX-42 P1 score command must be a non-empty string argv array")
    occurrences = sum(part.count("{iteration}") for part in template)
    if occurrences != 1:
        raise ValueError("EX-42 P1 score argv must contain {iteration} exactly once")

    def build(iteration: int) -> list[str]:
        if type(iteration) is not int or iteration < 0:
            raise ValueError("EX-42 P1 checkpoint iteration must be non-negative")
        return [part.replace("{iteration}", str(iteration)) for part in template]

    return build


def inspect_ex42_stage_zero_parent(*, plan: EX42Plan, approvals_path: str | Path,
                                   parent_manifest_path: str | Path,
                                   expected_sha256: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate the exact EX-41 pose_cmd parent for EX-42 stage zero.

    The EX-41 physical environment and curriculum clock are intentionally not
    restored. Policy, optimizers, LR, perception, AdaSmpl, map switch, RNG and
    normalization state are retained for the new EX-42 environment.
    """
    import torch

    approval = validate_stage_zero_authorization(plan, approvals_path)
    parent = plan.verify_parent_manifest(parent_manifest_path)
    path = Path(parent["checkpoint_path"]).resolve(strict=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    pinned = plan.document["stage_zero"]["parent"]["sha256"]
    if digest != pinned or (expected_sha256 is not None and expected_sha256 != pinned):
        raise ValueError("EX-42 stage-zero parent checkpoint SHA differs from the pinned approval")
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if (not isinstance(checkpoint, dict)
            or checkpoint.get("format") != "foothold-start/1"
            or checkpoint.get("iter") != 6000
            or checkpoint.get("ex41_pose_commands") is not True
            or checkpoint.get("ex41_critic_mirror") is not False):
        raise ValueError("EX-42 stage-zero parent is not the reviewed EX-41 pose_cmd m6000 checkpoint")
    cfg = checkpoint.get("perception_cfg") or {}
    if cfg.get("map_input") != "reconstruction" or cfg.get("force_gt") is not False:
        raise ValueError("EX-42 stage-zero parent must consume reconstructed maps without GT forcing")
    required = ("model_state_dict", "optimizer_state_dict", "ppo_learning_rate",
                "perception_state_dict", "perception_optimizer_state_dict", "adasmpl",
                "normalization_state", "rng", "map_switch", "continuous_curriculum")
    missing = [key for key in required if key not in checkpoint or checkpoint[key] is None]
    if missing:
        raise ValueError("EX-42 stage-zero parent lacks continuation state: " + ", ".join(missing))
    model = checkpoint["model_state_dict"]
    actor = model.get("actor.0.weight")
    critic = model.get("critic.0.weight")
    if (actor is None or tuple(actor.shape) != (512, 98)
            or critic is None or tuple(critic.shape) != (512, 666)):
        raise ValueError("EX-42 stage-zero parent actor/critic dimensions must be 98/666")
    receipt = {
        "state": "parent_verified_for_stage_zero",
        "parent_path": str(path), "manifest_path": str(Path(parent_manifest_path).resolve()),
        "parent_sha256": digest, "parent_local_update": 6000,
        "parent_cumulative_update": 12000,
        "actor_input_dim": 98, "critic_input_dim": 666,
        "pose_cmd": {"present": True, "width": 2, "zero_on_first_stage": True},
        "map_input": cfg["map_input"], "force_gt": cfg["force_gt"],
        "parent_p_map_off": checkpoint["map_switch"].get("p_map_off"),
        "continuation_state_fields": list(required),
        "ex41_environment_state_restored": False,
        "ex41_curriculum_state_restored": False,
        "approval": approval,
    }
    return checkpoint, receipt


def build_ex42_training_chain(*, plan_path: str | Path,
                              approvals_path: str | Path,
                              parent_manifest_path: str | Path,
                              run_dir: str | Path,
                              repo_root: str | Path,
                              queue_path: str | Path,
                              score_argv_json: str,
                              dispatch_path: str | Path | None = None,
                              boundary_provider: Any = None,
                              p1_interval: int = 250):
    """Load the pinned EX-42 plan and approved parent, then construct its chain."""
    plan = EX42Plan.load(plan_path)
    if plan.document.get("status") != "preparation_only":
        raise ValueError("EX-42 plan must remain preparation_only until launch approval")
    return EX42Runtime.training_chain(
        plan=plan,
        approvals_path=approvals_path,
        parent_manifest_path=parent_manifest_path,
        run_dir=run_dir,
        repo_root=repo_root,
        queue_path=queue_path,
        dispatch_path=dispatch_path,
        score_argv_factory=make_score_argv_factory(score_argv_json),
        boundary_provider=boundary_provider,
        p1_interval=p1_interval,
    )


def attach_ex42_training_chain(runner: Any, chain: Any) -> None:
    """Pass the constructed chain through the supported StartRunner API."""
    attach = getattr(runner, "attach_ex42_training_chain", None)
    if not callable(attach):
        raise TypeError("EX-42 training caller requires StartRunner.attach_ex42_training_chain")
    attach(chain)


def build_and_attach_ex42_training_chain(runner: Any, **inputs: Any):
    """Shared train_start path, also callable in CPU-only integration tests."""
    chain = build_ex42_training_chain(**inputs)
    attach_ex42_training_chain(runner, chain)
    return chain
