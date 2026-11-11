"""CPU-safe EX-41 launch and score-contract helpers.

This module does not start Isaac or a simulator. The entrypoint uses these
checks before AppLauncher and the simulator setup after authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import warnings
import io
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any

import yaml
from foothold_s2.machine_profile import machine_path

from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.curriculum import w72
from tools.wt_guard import disk_guard as wt_disk_guard


EX41_DISK_PLANNED_UPDATES = 5000 + 1500
EX41_DISK_MARGIN_BYTES = 50_000_000_000
EX41_DISK_REFERENCE_UPDATES = 8001
EX41_DISK_REFERENCE_LOG_BYTES = 13_922_236_660
EX41_DISK_REFERENCE_RAW_VIDEO_BYTES = 193_355_567
EX41_DISK_REFERENCE_FINAL_VIDEO_BYTES = 133_030_760
EX41_ISAAC_PYTHON = machine_path("conda_python")
EX41_PRODUCTION_PARENT = machine_path("s2_lab_root")
EX41_PLAYLIST_ROOT = machine_path("playlist_root")
EX41_W78_VIDEO_ROOT = machine_path("ex41_w78_video_root")
_EX41_PRODUCTION_ROOT = re.compile(r"ex41_main_[0-9]{8}_[0-9]{6}\Z")
EX41_UPDATE_SECONDS_ESTIMATE = 26.3
EX41_END_BY_BUFFER_SECONDS = 24 * 60 * 60


def assert_no_undefined_names(paths: list[str | Path]) -> None:
    """Fail before Kit starts when pyflakes finds an undefined Python name."""
    try:
        from pyflakes.api import check
        from pyflakes.reporter import Reporter
    except ImportError as exc:
        raise RuntimeError("EX-41 preflight requires pyflakes to reject undefined names") from exc
    diagnostics = io.StringIO()
    reporter = Reporter(diagnostics, diagnostics)
    for raw_path in paths:
        path = Path(raw_path).resolve(strict=True)
        source = path.read_text(encoding="utf-8")
        check(source, str(path), reporter)
    undefined = [line for line in diagnostics.getvalue().splitlines()
                 if "undefined name" in line]
    if undefined:
        raise ValueError("EX-41 preflight rejected undefined names:\n" + "\n".join(undefined))


def configure_ex41_command_slots(command_term: Any) -> dict[str, Any]:
    """Expand the pre-runtime W/T counter to EX-41's full slot contract.

    The task config initially creates a five-slot W/T command term. EX-41's
    first stages sample seven or more slots, so the cumulative counter must be
    resized when its runtime is attached, before the first rollout reset.
    Preserve counts already collected under matching names.
    """
    from foothold_s2.commands.mixed_core import EX39_SLOTS

    target = tuple(EX39_SLOTS)
    old_names = tuple(command_term.slot_names)
    old_counts = command_term.slot_counts
    if old_counts.ndim != 1 or old_counts.numel() != len(old_names):
        raise ValueError("EX-41 command slot names/counts differ before runtime attachment")
    if any(name not in target for name in old_names):
        raise ValueError("EX-41 command term has an unknown pre-runtime slot")
    counts = old_counts.new_zeros(len(target))
    for index, name in enumerate(old_names):
        counts[target.index(name)] = old_counts[index]
    command_term.slot_names = target
    command_term.slot_counts = counts
    return {"slot_names": list(target), "preserved_counts": int(old_counts.sum().item()),
            "prior_slot_names": list(old_names)}


def ex41_score_watch_argv(run_dir: str | Path, score_dir: str | Path, *,
                          table: str | Path, eval_config: str | Path,
                          python: str | Path = sys.executable) -> list[str]:
    """Build the production EX-41 watcher command without starting a child."""
    run = Path(run_dir).resolve(strict=True)
    score = Path(score_dir).resolve()
    table_path = Path(table).resolve(strict=True)
    eval_path = Path(eval_config).resolve(strict=True)
    interpreter = Path(python).resolve(strict=True)
    if os.path.normcase(str(interpreter)) != os.path.normcase(str(EX41_ISAAC_PYTHON.resolve(strict=False))):
        raise ValueError("EX-41 score watcher requires the pinned isaac311 interpreter")
    argv = [str(interpreter), "-m", "foothold_s2.ex41_score_watch",
            "--run-dir", str(run), "--out-root", str(ex41_score_watch_output_root(run)),
            "--score-dir", str(score), "--table", str(table_path),
            "--eval-config", str(eval_path), "--execute"]
    manifest_path = run / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rehearsal = manifest.get("modes", {}).get("ex41", {}).get("rehearsal", {})
        if rehearsal.get("enabled") is True:
            argv.append("--rehearsal-stop")
    return argv


def _write_score_watch_receipt(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    data = (json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    try:
        with tmp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def launch_ex41_score_watch(run_dir: str | Path, score_dir: str | Path, *,
                            table: str | Path, eval_config: str | Path,
                            python: str | Path = sys.executable,
                            trigger_update: int,
                            popen=subprocess.Popen) -> dict:
    """Start the detached numeric evaluator after the first update status."""
    if type(trigger_update) is not int or trigger_update < 1:
        raise ValueError("EX-41 watcher trigger must be a completed positive update")
    argv = ex41_score_watch_argv(run_dir, score_dir, table=table,
                                 eval_config=eval_config, python=python)
    run = Path(run_dir).resolve(strict=True)
    out = ex41_score_watch_output_root(run)
    out.mkdir(parents=True, exist_ok=True)
    lock = out / "watch.lock"
    if lock.is_file():
        try:
            owner = json.loads(lock.read_text(encoding="utf-8"))
            import psutil
            pid = owner.get("pid")
            if type(pid) is not int or pid <= 0:
                return {"state": "blocked_unknown_lock_owner", "lock": str(lock)}
            if psutil.pid_exists(pid):
                return {"state": "already_running", "pid": pid, "lock": str(lock)}
        except (OSError, ValueError, ImportError):
            return {"state": "blocked_unreadable_lock", "lock": str(lock)}
    completion_path = out / "watch_completion.json"
    if completion_path.is_file():
        try:
            completion = json.loads(completion_path.read_text(encoding="utf-8"))
            training_status = json.loads((run / "train_start_status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"state": "blocked_unreadable_completion", "completion": str(completion_path)}
        # A previous watcher can finish with HOLD when training dies. On a
        # later self-resume, allow a fresh watcher to continue the same durable
        # watch_state, but only after the trainer has positively returned to
        # running. A completed healthy run remains terminal.
        resumable = (completion.get("state") == "complete_with_hold"
                     and completion.get("training_state") in ("failed", "error", "stopped", "stopped_saved")
                     and training_status.get("state") == "running")
        if not resumable:
            return {"state": "already_complete", "completion": str(completion_path)}

    env = dict(os.environ)
    repo = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = str(repo) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("EX41_ORCHESTRATION_TO", "term_37f1d02b-35f8-435d-940e-d43a8a5be1de")
    stdout_path, stderr_path = out / "watcher.stdout.log", out / "watcher.stderr.log"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        child = popen(argv, cwd=str(repo), env=env, stdin=subprocess.DEVNULL,
                      stdout=stdout, stderr=stderr, creationflags=flags, close_fds=True)
    row = {"format": "foothold-ex41-score-watch-launch/1", "state": "running",
           "pid": int(child.pid), "started_unix": time.time(), "argv": argv,
           "cwd": str(repo), "stdout": str(stdout_path), "stderr": str(stderr_path),
           "trigger": "first_completed_update", "trigger_update": trigger_update,
           "resumed_after_incomplete_completion": completion_path.is_file()}
    receipt = out / "launches" / f"launch_{row['started_unix']:.6f}_{child.pid}.json"
    _write_score_watch_receipt(receipt, row)
    return row | {"receipt": str(receipt)}


def install_ex41_score_watch_after_first_update(runner, run_dir: str | Path,
                                                 score_dir: str | Path, *,
                                                 table: str | Path,
                                                 eval_config: str | Path,
                                                 enabled: bool = True,
                                                 launch=launch_ex41_score_watch) -> None:
    """Bind one launch to StartRunner's existing first-update status write."""
    if not enabled:
        return
    if getattr(runner, "_ex41_score_watch_hook_installed", False):
        raise ValueError("EX-41 score watcher hook already installed")
    original = runner._write_running_status
    state = {"started": False}

    def after_status(iteration, *args, **kwargs):
        result = original(iteration, *args, **kwargs)
        if type(iteration) is int and iteration >= 1 and not state["started"]:
            state["started"] = True
            try:
                receipt = launch(run_dir, score_dir, table=table,
                                 eval_config=eval_config, trigger_update=iteration)
                runner._ex41_score_watch_launch = receipt
                print("EX41_SCORE_WATCH " + json.dumps(receipt, sort_keys=True), flush=True)
            except Exception as exc:
                failure = {"state": "failed", "trigger": "first_completed_update",
                           "reason": f"{type(exc).__name__}: {exc}"}
                runner._ex41_score_watch_launch = failure
                failure_path = (Path(run_dir) / "shadow-score-watch" / "launches" /
                                f"failed_{time.time():.6f}_{uuid.uuid4().hex[:8]}.json")
                _write_score_watch_receipt(failure_path, failure)
                print("EX41_SCORE_WATCH_FAILED " + json.dumps(failure, sort_keys=True), flush=True)
        return result

    runner._write_running_status = after_status
    runner._ex41_score_watch_hook_installed = True


def checkpoint_count_for_updates(planned_updates: int, save_interval: int) -> int:
    """Count periodic model_N files plus a distinct final file for StartRunner."""
    if (type(planned_updates) is not int or planned_updates <= 0
            or type(save_interval) is not int or save_interval <= 0):
        raise ValueError("EX-41 disk plan needs positive integer updates and save_interval")
    periodic = planned_updates // save_interval
    final_is_periodic = planned_updates % save_interval == 0
    return periodic + int(not final_is_periodic)


def _require_d_drive(path: str | Path) -> Path:
    root = Path(path)
    if not root.is_absolute() or root.drive.upper() != "D:":
        raise ValueError(f"EX-41 training output must be an absolute D: path: {root}")
    return root


def ex41_output_layout_for_run(run_dir: str | Path) -> dict[str, Path] | None:
    """Resolve D164 production paths; rehearsal and legacy runs return None.

    Production run folders are <s2_lab>/ex41_main_YYYYMMDD_HHMMSS/main/<run>.
    Score/evaluation artifacts and replay lists share <root>/eval; W78 video
    output remains on the separately approved D: volume.
    """
    run = Path(run_dir).resolve()
    if run.drive.upper() != "C:" or run.parent.name != "main":
        return None
    root = run.parent.parent
    if root.parent != EX41_PRODUCTION_PARENT or not _EX41_PRODUCTION_ROOT.fullmatch(root.name):
        return None
    return {
        "root": root,
        "main_root": root / "main",
        "run_dir": run,
        "eval_root": root / "eval",
        "score_dir": root / "eval" / "scores",
        "playlist_dir": EX41_PLAYLIST_ROOT,
        "playlist_mirror_dir": root / "eval",
        "w78_video_root": EX41_W78_VIDEO_ROOT,
    }


def build_ex41_output_layout(timestamp: str, run_name: str) -> dict[str, Path]:
    """Build the single approved production layout from explicit names."""
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{8}_[0-9]{6}", timestamp):
        raise ValueError("EX-41 production timestamp must be YYYYMMDD_HHMMSS")
    if (not isinstance(run_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", run_name)
            or run_name in {".", ".."}):
        raise ValueError("EX-41 run name must be one safe path component")
    root = EX41_PRODUCTION_PARENT / f"ex41_main_{timestamp}"
    run = root / "main" / run_name
    return ex41_output_layout_for_run(run) or {}


def ex41_score_watch_output_root(run_dir: str | Path) -> Path:
    """Return ROOT/eval for the fixed production layout, isolated fallback otherwise."""
    run = Path(run_dir).resolve()
    layout = ex41_output_layout_for_run(run)
    return layout["eval_root"] / "score-watch" if layout else run / "shadow-score-watch"


def _require_ex41_run_path(path: str | Path) -> Path:
    """Allow D: rehearsal paths and the two explicit C: EX-41 run layouts."""
    root = Path(path)
    if not root.is_absolute():
        raise ValueError("EX-41 output must be an absolute path")
    if root.drive.upper() == "D:":
        return root
    if (root.drive.upper() == "C:"
            and root.parent == EX41_PRODUCTION_PARENT
            and re.fullmatch(r"ex41_smoke_[0-9]{8}_[0-9]{6}", root.name)):
        return root
    layout = ex41_output_layout_for_run(root)
    if layout is None or layout["run_dir"] != root.resolve():
        raise ValueError("EX-41 output must match an approved s2_lab D: rehearsal, C: smoke, or main/<run> layout")
    return root


def validate_ex41_output_directory(path: str | Path) -> Path:
    """Reject existing non-empty run destinations before any Kit import/start."""
    root = _require_ex41_run_path(path)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("EX-41 training output directory must be new or empty")
    return root


def _free_bytes_for_path(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return int(shutil.disk_usage(probe).free)


def _planner_disk_level(path: Path, required_bytes: int, *, usage_fn=shutil.disk_usage) -> dict[str, Any]:
    """Use planner's shared threshold checker on the destination volume."""
    block_gb = required_bytes / wt_disk_guard.GB
    config = wt_disk_guard.wt_config.load(
        {"HOME": str(machine_path("runner_home"))}, user_file=None, default_file=None)
    rows = wt_disk_guard.check(
        [str(Path(path.anchor))], warn_gb=block_gb + 1e-9,
        block_gb=block_gb, config=config, usage_fn=usage_fn)
    return rows[0]


def build_ex41_disk_plan(output_root: str | Path, checkpoint_size_bytes: int,
                         save_interval: int, *, planned_updates: int = EX41_DISK_PLANNED_UPDATES,
                         free_bytes: int | None = None) -> dict[str, Any]:
    """Preflight output capacity from the pinned parent size and measured m6000 artifacts."""
    root = _require_ex41_run_path(output_root)
    if type(checkpoint_size_bytes) is not int or checkpoint_size_bytes <= 0:
        raise ValueError("EX-41 disk plan needs the measured parent checkpoint size")
    count = checkpoint_count_for_updates(planned_updates, save_interval)
    records_bytes = math.ceil(EX41_DISK_REFERENCE_LOG_BYTES * planned_updates
                              / EX41_DISK_REFERENCE_UPDATES)
    video_bytes = EX41_DISK_REFERENCE_RAW_VIDEO_BYTES + EX41_DISK_REFERENCE_FINAL_VIDEO_BYTES
    records_video_bytes = records_bytes + video_bytes
    checkpoint_bytes = count * checkpoint_size_bytes
    required_bytes = checkpoint_bytes + records_video_bytes + EX41_DISK_MARGIN_BYTES
    available = _free_bytes_for_path(root) if free_bytes is None else int(free_bytes)
    planner_check = None if free_bytes is not None else _planner_disk_level(root, required_bytes)
    receipt = {
        "format": "foothold-ex41-disk-guard/1",
        "output_root": str(root),
        "planned_updates": planned_updates,
        "update_basis": [5000, 1500],
        "save_interval": save_interval,
        "checkpoint_count": count,
        "checkpoint_size_bytes": checkpoint_size_bytes,
        "checkpoint_reserve_bytes": checkpoint_bytes,
        "record_video_reserve_bytes": records_video_bytes,
        "record_video_basis": {
            "reference_updates": EX41_DISK_REFERENCE_UPDATES,
            "run_non_checkpoint_bytes": EX41_DISK_REFERENCE_LOG_BYTES,
            "raw_video_bytes": EX41_DISK_REFERENCE_RAW_VIDEO_BYTES,
            "final_video_bytes": EX41_DISK_REFERENCE_FINAL_VIDEO_BYTES,
            "scaled_run_non_checkpoint_bytes": records_bytes,
            "video_estimate_bytes": video_bytes,
        },
        "margin_bytes": EX41_DISK_MARGIN_BYTES,
        "required_free_bytes": required_bytes,
        "available_free_bytes": available,
        "planner_disk_guard": ("injected_cpu_fixture" if planner_check is None else planner_check),
    }
    if (available < required_bytes
            or planner_check is not None and planner_check["level"] in ("block", "unknown")):
        raise ValueError("EX-41 output free space below preflight reserve: "
                         f"available={available} required={required_bytes}")
    return receipt


def write_ex41_disk_preflight(log_dir: str | Path, receipt: dict[str, Any]) -> Path:
    """Persist the exact preflight receipt in the selected run directory."""
    root = _require_ex41_run_path(log_dir)
    if Path(receipt.get("output_root", "")).resolve() != root.resolve():
        raise ValueError("EX-41 disk preflight receipt does not match run directory")
    root.mkdir(parents=True, exist_ok=True)
    target = root / "ex41_disk_preflight.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def record_ex41_disk_snapshot(log_dir: str | Path, disk_plan: dict[str, Any],
                              completed_updates: int, *, free_bytes: int | None = None) -> dict[str, Any]:
    """Append a 250-update disk observation; below-reserve space warns but does not stop training."""
    run_dir = _require_ex41_run_path(log_dir)
    if Path(disk_plan.get("output_root", "")).resolve() != run_dir.resolve():
        raise ValueError("EX-41 disk snapshot path differs from preflight run directory")
    if type(completed_updates) is not int or completed_updates < 0:
        raise ValueError("EX-41 disk snapshot update count must be a non-negative integer")
    if completed_updates == 0 or completed_updates % 250:
        raise ValueError("EX-41 disk snapshots are only valid at positive 250-update boundaries")
    interval = disk_plan["save_interval"]
    available = _free_bytes_for_path(run_dir) if free_bytes is None else int(free_bytes)
    remaining_updates = max(0, disk_plan["planned_updates"] - completed_updates)
    saved_periodic = min(disk_plan["checkpoint_count"], math.ceil(completed_updates / interval))
    remaining_checkpoints = max(0, disk_plan["checkpoint_count"] - saved_periodic)
    records_video_remaining = math.ceil(
        disk_plan["record_video_reserve_bytes"] * remaining_updates / disk_plan["planned_updates"]
    )
    required = (remaining_checkpoints * disk_plan["checkpoint_size_bytes"]
                + records_video_remaining + disk_plan["margin_bytes"])
    planner_check = _planner_disk_level(run_dir, required) if free_bytes is None else None
    row = {
        "event": ("disk_space_warning" if available < required
                  or planner_check is not None and planner_check["level"] in ("block", "unknown")
                  else "disk_space_snapshot"),
        "completed_updates": completed_updates,
        "path": str(run_dir),
        "available_free_bytes": available,
        "remaining_checkpoint_count": remaining_checkpoints,
        "checkpoint_size_bytes": disk_plan["checkpoint_size_bytes"],
        "record_video_remaining_bytes": records_video_remaining,
        "margin_bytes": disk_plan["margin_bytes"],
        "required_free_bytes": required,
        "planner_disk_guard": "injected_cpu_fixture" if planner_check is None else planner_check,
    }
    event_path = run_dir / "ex41_disk_guard.jsonl"
    with event_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")
    if available < required:
        warnings.warn("EX-41 disk reserve below threshold at update "
                      f"{completed_updates}: available={available} required={required}",
                      RuntimeWarning, stacklevel=2)
    return row


def load_fixed_plan(path: str | Path, *, smoke_boundaries=None):
    plan = load_plan(path, arm="B", smoke_boundaries=smoke_boundaries)
    if not getattr(plan, "fixed_schedule", None):
        raise ValueError("EX-41 startup requires the approved fixed5000 plan")
    if plan.parent_update != 6000 or plan.initial_dr_scale != 0.5:
        raise ValueError("EX-41 startup parent or initial DR scale differs")
    return plan


def authorization_snapshot(plan) -> dict[str, Any]:
    """Read committed W72 files. Does not alter boundary or approval state."""
    return w72.read_committed_pair(plan.boundary_path, plan.approvals_path)


def require_production_authorization(plan) -> dict[str, Any]:
    snapshot = authorization_snapshot(plan)
    values = snapshot["config"]["values"]
    if values.get("w71_ready") is not True:
        raise ValueError("EX-41 production start blocked: W71 consumer is not verified")
    return snapshot


def production_launch_status(plan, *, lead_approved: bool, snapshot=None) -> dict[str, Any]:
    """A single explicit lead CLI switch plus W71 readiness gates production."""
    if type(lead_approved) is not bool:
        raise ValueError("EX-41 lead production approval switch must be boolean")
    snapshot = authorization_snapshot(plan) if snapshot is None else snapshot
    values = snapshot.get("config", {}).get("values", {})
    w71_ready = values.get("w71_ready") is True
    return {"lead_approval_switch": lead_approved, "w71_ready": w71_ready,
            "production_launch_allowed": bool(lead_approved and w71_ready),
            "reason": ("approved" if lead_approved and w71_ready else
                       "lead_approval_switch_missing" if not lead_approved else "w71_not_ready")}


def require_production_launch(plan, *, lead_approved: bool, snapshot=None) -> dict[str, Any]:
    status = production_launch_status(plan, lead_approved=lead_approved, snapshot=snapshot)
    if not status["production_launch_allowed"]:
        raise ValueError("EX-41 production launch blocked: " + status["reason"])
    return status


def write_production_launch_receipt(log_dir: str | Path, plan, parent: dict[str, Any],
                                    status: dict[str, Any]) -> Path:
    """Persist the approved pre-Kit launch decision for the actual run."""
    root = _require_ex41_run_path(log_dir)
    if status.get("production_launch_allowed") is not True or status.get("lead_approval_switch") is not True:
        raise ValueError("EX-41 production launch receipt requires explicit lead approval")
    if status.get("w71_ready") is not True:
        raise ValueError("EX-41 production launch receipt requires W71 readiness")
    if parent.get("sha256") != plan.parent_sha256:
        raise ValueError("EX-41 production launch receipt parent differs from pinned m6000")
    root.mkdir(parents=True, exist_ok=True)
    receipt = {"format":"foothold-ex41-production-launch/1", "state":"authorized_pre_Kit",
               "production_launch_allowed":True, "kit_started":False,
               "lead_approval_switch":True, "w71_ready":True,
               "plan_sha256":plan.sha256, "effective_sha256":plan.effective_sha256,
               "parent_sha256":parent.get("sha256"),
               "created_at":datetime.now(timezone.utc).isoformat()}
    path = root / f"ex41_production_launch_{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    return path


def validate_output_with_launch_receipt(log_dir: str | Path, receipt_path: str | Path) -> Path:
    """Repeat the pre-Kit empty-root guard while allowing only its own receipt."""
    root = _require_ex41_run_path(log_dir).resolve(strict=True)
    receipt = Path(receipt_path).resolve(strict=True)
    if receipt.parent != root or not receipt.name.startswith("ex41_production_launch_"):
        raise ValueError("EX-41 launch receipt is outside the approved run root")
    children = {path.resolve() for path in root.iterdir()}
    if children != {receipt}:
        raise ValueError("EX-41 production output contains unexpected pre-Kit files")
    return root


def validate_stage_rehearsal_mode(stage_updates, rehearsal_updates, *,
                                   production_approved: bool, startup_smoke: bool) -> bool:
    """Permit a shortened six-stage table only on the isolated rehearsal path."""
    if stage_updates is None:
        return False
    if production_approved or startup_smoke:
        raise ValueError('short EX-41 stage table is rehearsal-only')
    if (not isinstance(stage_updates, tuple) or len(stage_updates) != 6
            or any(type(value) is not int or not 1 <= value <= 5 for value in stage_updates)
            or sum(stage_updates) > 30
            or type(rehearsal_updates) is not int
            or rehearsal_updates != sum(stage_updates)):
        raise ValueError('short EX-41 stage table does not match rehearsal update cap')
    return True


def validate_rehearsal_request(updates: int, output_dir: str | Path,
                               device: str, headless: bool,
                               distributed: bool = False,
                               stage_updates: tuple[int, ...] | None = None) -> Path:
    """Allow only the explicitly bounded, isolated 10-update Kit rehearsal."""
    if stage_updates is None:
        if type(updates) is not int or updates != 10:
            raise ValueError("EX-41 standard rehearsal is fixed to exactly 10 updates")
    else:
        from foothold_s2.scripts.ex41_rehearsal_schedule import boundary_updates

        if (type(updates) is not int or updates != sum(stage_updates)
                or len(boundary_updates(stage_updates)) != 5):
            raise ValueError("EX-41 stage rehearsal update count differs from its six-stage table")
    path = Path(output_dir)
    if not path.is_absolute() or path.parent.name.lower() != "s2_lab":
        raise ValueError("EX-41 rehearsal output must be an absolute s2_lab child")
    _require_d_drive(path)
    if not re.fullmatch(r"ex41_rehearsal_[0-9]{8}_[0-9]{6}", path.name):
        raise ValueError("EX-41 rehearsal output must use ex41_rehearsal_YYYYMMDD_HHMMSS")
    if device != "cuda:0" or not headless or distributed:
        raise ValueError("EX-41 rehearsal requires headless cuda:0 and one process")
    if path.exists() and any(path.iterdir()):
        raise ValueError("EX-41 rehearsal output must be new or empty")
    return path


def configure_stage_rehearsal_plan(plan, stage_updates: tuple[int, ...], *,
                                   boundary_path: str | Path | None = None) -> dict:
    """Apply a short table to an isolated rehearsal plan; YAML/production stays pinned."""
    from foothold_s2.scripts.ex41_rehearsal_schedule import boundary_updates, STAGE_IDS

    rows = tuple(stage_updates)
    boundaries = boundary_updates(rows)
    if len(plan.stages) != len(STAGE_IDS) or tuple(stage.id for stage in plan.stages) != STAGE_IDS:
        raise ValueError("EX-41 short rehearsal requires the six fixed-schedule stages")
    settings = dict(plan.clock_settings)
    settings.update(duration_updates=sum(rows), durations=rows,
                    interval_updates=min(rows), pause_limit_updates=0,
                    maximum_extensions=0, extension_updates=0)
    plan.clock_settings = settings
    plan.rehearsal_stage_updates = rows
    plan.smoke_boundaries = boundaries
    rehearsal_boundary = plan.path.with_name('ex41-fixed5000-rehearsal-boundary.yaml').resolve(strict=True)
    rehearsal_approvals = plan.path.with_name('ex41-fixed5000-rehearsal-approvals.yaml').resolve(strict=True)
    if boundary_path is not None:
        selected_boundary = Path(boundary_path).resolve(strict=True)
        if selected_boundary != rehearsal_boundary:
            raise ValueError("EX-41 rehearsal may only use its isolated rehearsal boundary file")
    production_boundary = plan.path.with_name('ex41-fixed5000-boundary.yaml').resolve()
    production_approvals = plan.path.with_name('ex41-fixed5000-approvals.yaml').resolve()
    if rehearsal_boundary == production_boundary or rehearsal_approvals == production_approvals:
        raise ValueError("EX-41 rehearsal configuration aliases production authorization")
    plan.boundary_path = rehearsal_boundary
    plan.approvals_path = rehearsal_approvals
    for stage, duration in zip(plan.stages, rows):
        plan.stage_meta[stage.id]["minimum_updates"] = duration
        plan.stage_meta[stage.id]["maximum_updates"] = duration
    return {"format": "foothold-ex41-short-stage-rehearsal/1",
            "stage_ids": list(STAGE_IDS), "stage_updates": list(rows),
            "transition_next_updates": list(boundaries),
            "completed_updates": sum(rows), "interval_updates": min(rows),
            "pause_budget_updates": 0, "production_table_modified": False,
            "boundary_config_path": str(plan.boundary_path.resolve()),
            "boundary_config_sha256": hashlib.sha256(plan.boundary_path.read_bytes()).hexdigest(),
            "approval_config_path": str(plan.approvals_path.resolve()),
            "approval_config_sha256": hashlib.sha256(plan.approvals_path.read_bytes()).hexdigest(),
            "w72_evidence_policy": "excluded_from_rehearsal"}


def validate_startup_smoke_request(updates: int, output_dir: str | Path,
                                   device: str, headless: bool,
                                   distributed: bool = False) -> Path:
    """Allow a 10-update bounded smoke through the production startup path, without authorization."""
    if type(updates) is not int or updates != 10:
        raise ValueError("EX-41 startup smoke is fixed to exactly 10 updates")
    path = Path(output_dir)
    if (not path.is_absolute() or path.drive.upper() != "C:"
            or path.parent != EX41_PRODUCTION_PARENT
            or not re.fullmatch(r"ex41_smoke_[0-9]{8}_[0-9]{6}", path.name)):
        raise ValueError(f"EX-41 startup smoke output must be under {EX41_PRODUCTION_PARENT.as_posix()}")
    if device != "cuda:0" or not headless or distributed:
        raise ValueError("EX-41 startup smoke requires headless cuda:0 and one process")
    return validate_ex41_output_directory(path)


def validate_rehearsal_resume_request(target_updates: int, output_dir: str | Path,
                                      checkpoint: str | Path, device: str,
                                      headless: bool, distributed: bool = False) -> Path:
    """Allow at most two updates from a done run or a proven dead failed attempt."""
    if type(target_updates) is not int:
        raise ValueError("EX-41 rehearsal resume target must be an integer")
    if device != "cuda:0" or not headless or distributed:
        raise ValueError("EX-41 rehearsal resume requires headless cuda:0 and one process")
    run = _require_d_drive(output_dir).resolve(strict=True)
    if run.parent.name.lower() != "s2_lab" or not re.fullmatch(
            r"ex41_rehearsal_[0-9]{8}_[0-9]{6}", run.name):
        raise ValueError("EX-41 rehearsal resume path must be a named s2_lab child")
    cp = Path(checkpoint).resolve(strict=True)
    match = re.fullmatch(r"model_([0-9]+)\.pt", cp.name)
    if cp.parent != run or match is None:
        raise ValueError("EX-41 rehearsal resume checkpoint must be numbered in the same run")
    completed = int(match[1])
    if target_updates <= completed or target_updates > completed + 2:
        raise ValueError("EX-41 rehearsal resume is limited to one or two new updates")
    manifest_path = run / "manifest.json"
    status_path = run / "train_start_status.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    status = json.loads(status_path.read_text(encoding="utf-8-sig"))
    rehearsal = manifest.get("modes", {}).get("ex41", {}).get("rehearsal", {})
    if (rehearsal.get("enabled") is not True
            or manifest.get("progress", {}).get("completed_updates") != completed):
        raise ValueError("EX-41 rehearsal resume requires the completed latest checkpoint")
    state = status.get("state")
    if state == "done":
        if status.get("iter") != completed:
            raise ValueError("EX-41 rehearsal done status differs from checkpoint update")
        return run
    if state not in ("starting", "running", "failed"):
        raise ValueError("EX-41 rehearsal retry requires a completed or failed attempt")
    status_iteration = status.get("iter")
    if status_iteration is not None and status_iteration > completed:
        raise ValueError("EX-41 failed attempt advanced beyond the latest checkpoint")
    pid = status.get("pid")
    if type(pid) is not int or _process_is_alive(pid):
        raise ValueError("EX-41 failed rehearsal process is still alive or has no PID")
    alerts_path = run / "ex41_reports" / "alerts.jsonl"
    try:
        alert_rows = [json.loads(line) for line in alerts_path.read_text(encoding="utf-8-sig").splitlines()
                      if line.strip()]
    except (OSError, ValueError) as exc:
        raise ValueError("EX-41 failed rehearsal has no readable failure receipt") from exc
    if not any(row.get("kind") in ("fatal_training_fault", "nonzero_process_exit")
               and (row.get("kind") == "fatal_training_fault" or
                    type(row.get("rc")) is int and row["rc"] != 0)
               for row in alert_rows):
        raise ValueError("EX-41 failed rehearsal has no nonzero failure alert")
    return run


def _process_is_alive(pid: int) -> bool:
    """Conservatively reject a retry while the recorded trainer PID exists."""
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.WaitForSingleObject.restype = ctypes.c_uint32
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, 0, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 0x00000102  # WAIT_TIMEOUT
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def install_end_by_warning_watch(runtime: Any, run_dir: str | Path, plan,
                                 *, now: datetime | None = None,
                                 clock_now=None,
                                 seconds_per_update: float = EX41_UPDATE_SECONDS_ESTIMATE,
                                 deliver=None) -> dict[str, Any]:
    """Record an estimated END_BY and warn at update boundaries without stopping training."""
    if not math.isfinite(seconds_per_update) or seconds_per_update <= 0:
        raise ValueError("EX-41 END_BY needs a positive measured update-time estimate")
    schedule = getattr(plan, "fixed_schedule", None)
    if not isinstance(schedule, dict):
        raise ValueError("EX-41 END_BY requires the fixed schedule")
    started = now or datetime.now(timezone.utc)
    if started.tzinfo is None:
        raise ValueError("EX-41 END_BY start time must include a timezone")
    clock = runtime.clock
    duration = int(schedule["duration_updates"])
    pause_limit = int(schedule["pause_limit_updates"])
    extension_total = int(schedule["extension_updates"]) * int(schedule["maximum_extensions"])
    elapsed = int(getattr(clock, "elapsed", 0))
    pause_used = int(getattr(clock, "pause_used", 0))
    extension_used = int(getattr(clock, "extension", 0))
    extension_decided = bool(getattr(clock, "extension_decided", False))
    expected_updates = max(0, duration - elapsed)
    max_extension_updates = max(0, pause_limit - pause_used)
    if not extension_decided:
        max_extension_updates += extension_total
    else:
        max_extension_updates += max(0, extension_used)
    expected_end = started + timedelta(seconds=expected_updates * seconds_per_update)
    end_by = expected_end + timedelta(
        seconds=max_extension_updates * seconds_per_update + EX41_END_BY_BUFFER_SECONDS)
    receipt = {
        "format": "foothold-ex41-end-by-watch/1",
        "started_at": started.isoformat(),
        "expected_end_at": expected_end.isoformat(),
        "end_by": end_by.isoformat(),
        "action": "warning_only",
        "training_stop_on_deadline": False,
        "poll_interval_updates": int(schedule["interval_updates"]),
        "expected_updates": expected_updates,
        "maximum_extension_updates": max_extension_updates,
        "seconds_per_update": seconds_per_update,
        "estimate_basis": "lead-reported 3072-env rehearsal, maximum of 10 measured updates: 26.3 s/update",
        "buffer_seconds": EX41_END_BY_BUFFER_SECONDS,
    }
    report_dir = Path(run_dir) / "ex41_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    target = report_dir / "end_by_watch.json"
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    os.replace(temp, target)

    original = runtime.on_update_start
    warned = False
    current_time = clock_now or (lambda: datetime.now(timezone.utc))

    def check_at_boundary(next_update: int):
        nonlocal warned
        result = original(next_update)
        completed = next_update - 1
        if (not warned and completed > 0
                and completed % int(schedule["interval_updates"]) == 0
                and current_time() >= end_by):
            from foothold_s2.ex41_ops import record_deadline_alert

            alert = record_deadline_alert(
                run_dir, completed,
                {"end_by": end_by.isoformat(), "action": "warning_only",
                 "training_stop_on_deadline": False}, deliver=deliver)
            runtime._write({"event": "end_by_warning", "iteration": completed,
                            "event_id": alert["event_id"], "end_by": end_by.isoformat(),
                            "action": "warning_only"})
            print("EX41_END_BY_WARNING " + json.dumps(alert, sort_keys=True), flush=True)
            warned = True
        return result

    runtime.on_update_start = check_at_boundary
    return receipt


def configure_ex41_train_cfg(train_cfg: dict[str, Any], plan, parent_path: str | Path,
                             rehearsal_updates: int | None = None,
                             disk_guard: dict[str, Any] | None = None,
                             startup_smoke_updates: int | None = None,
                             rehearsal_stage_updates: tuple[int, ...] | None = None) -> dict[str, Any]:
    """Set mandatory transfer flags and the parent reference in a fresh cfg."""
    cfg = dict(train_cfg)
    parent_agent_path = Path(parent_path).resolve(strict=True).parent / "params" / "agent.yaml"
    parent_agent = yaml.safe_load(parent_agent_path.read_text(encoding="utf-8-sig"))
    parent_perception = parent_agent.get("perception") if isinstance(parent_agent, dict) else None
    parent_p_map_off = parent_perception.get("p_map_off") if isinstance(parent_perception, dict) else None
    if (type(parent_p_map_off) not in (int, float)
            or not math.isfinite(float(parent_p_map_off))
            or not 0.0 <= float(parent_p_map_off) <= 1.0):
        raise ValueError("EX-41 parent agent.yaml has no valid perception.p_map_off")
    perception = dict(cfg.get("perception") or {})
    perception["p_map_off"] = float(parent_p_map_off)
    cfg["perception"] = perception
    cfg["ex41_pose_commands"] = True
    cfg["ex41_w86_required"] = True
    cfg["ex41_parent"] = {
        "path": str(Path(parent_path).resolve()),
        "sha256": plan.parent_sha256,
        "iteration": plan.parent_update,
    }
    if rehearsal_updates is not None and startup_smoke_updates is not None:
        raise ValueError("EX-41 rehearsal and startup smoke limits are mutually exclusive")
    if startup_smoke_updates is not None:
        if rehearsal_stage_updates is not None:
            raise ValueError("EX-41 stage table is rehearsal-only, not startup smoke")
        if type(startup_smoke_updates) is not int or startup_smoke_updates != 10:
            raise ValueError("EX-41 startup smoke is fixed to exactly 10 updates")
        cfg["max_iterations"] = startup_smoke_updates
        cfg["save_interval"] = startup_smoke_updates
        cfg["ex41_startup_smoke"] = True
    elif rehearsal_updates is None:
        if rehearsal_stage_updates is not None:
            raise ValueError("EX-41 stage table requires bounded rehearsal updates")
        # The runner uses zero-based iteration indices; one extra loop entry is
        # needed to observe the runtime's terminal completed-update boundary.
        cfg["max_iterations"] = 6501
    else:
        if rehearsal_stage_updates is None:
            if type(rehearsal_updates) is not int or rehearsal_updates != 10:
                raise ValueError("EX-41 rehearsal is fixed to exactly 10 updates")
            cfg["max_iterations"] = rehearsal_updates
        else:
            rows = tuple(rehearsal_stage_updates)
            if (len(rows) != 6 or any(type(value) is not int or not 1 <= value <= 5
                                      for value in rows)
                    or sum(rows) > 30 or type(rehearsal_updates) is not int
                    or rehearsal_updates != sum(rows)):
                raise ValueError("EX-41 rehearsal stage table differs from its bounded update count")
            cfg["max_iterations"] = sum(rows) + 1
        cfg["save_interval"] = 1
        cfg["ex41_rehearsal"] = True
    if disk_guard is not None:
        if (not isinstance(disk_guard, dict)
                or disk_guard.get("format") != "foothold-ex41-disk-guard/1"
                or disk_guard.get("output_root") is None):
            raise ValueError("EX-41 disk guard receipt is invalid")
        cfg["ex41_disk_guard"] = dict(disk_guard)
    if cfg.get("ex41_w86_required") is not True:
        raise ValueError("EX-41 requires W86")
    return cfg


def verify_m6000_parent(plan, parent_path: str | Path) -> dict[str, Any]:
    """Verify the selected parent bytes, run manifest, and pinned saved configs."""
    checkpoint = Path(parent_path).resolve(strict=True)
    if checkpoint.name != "model_6000.pt":
        raise ValueError("EX-41 parent must be model_6000.pt")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if digest != plan.parent_sha256:
        raise ValueError("EX-41 m6000 checkpoint SHA differs from fixed plan")
    manifest_path = checkpoint.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (manifest.get("checkpoints", {}).get(checkpoint.name) != digest
            or not isinstance(manifest.get("progress", {}).get("completed_updates"), int)
            or manifest["progress"]["completed_updates"] < 6000):
        raise ValueError("EX-41 m6000 checkpoint manifest does not prove saved progress")
    params = checkpoint.parent / "params"
    env_path, agent_path = params / "env.yaml", params / "agent.yaml"
    if hashlib.sha256(env_path.read_bytes()).hexdigest() != plan.baseline_env_yaml_sha256:
        raise ValueError("EX-41 parent env.yaml SHA differs from fixed plan")
    if hashlib.sha256(agent_path.read_bytes()).hexdigest() != plan.baseline_agent_yaml_sha256:
        raise ValueError("EX-41 parent agent.yaml SHA differs from fixed plan")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8-sig"))
    save_interval = agent.get("save_interval") if isinstance(agent, dict) else None
    if type(save_interval) is not int or save_interval <= 0:
        raise ValueError("EX-41 parent agent.yaml save_interval is missing or invalid")
    return {"checkpoint": str(checkpoint), "sha256": digest,
            "parent_checkpoint_update": plan.parent_update,
            "manifest_completed_updates": manifest["progress"]["completed_updates"],
            "completed_updates": manifest["progress"]["completed_updates"],
            "checkpoint_size_bytes": checkpoint.stat().st_size,
            "save_interval": save_interval,
            "env_yaml_sha256": plan.baseline_env_yaml_sha256,
            "agent_yaml_sha256": plan.baseline_agent_yaml_sha256}


def verify_ex41_start_readback(log_dir: str | Path, plan, parent_receipt: dict[str, Any],
                               manifest: dict[str, Any], env: Any,
                               dr_runtime: Any) -> dict[str, Any]:
    """Read back persisted start inputs and live DR before the first learn call."""
    root = _require_ex41_run_path(log_dir).resolve(strict=True)
    manifest_path = root / "manifest.json"
    env_path = root / "params" / "env.yaml"
    agent_path = root / "params" / "agent.yaml"
    if not all(path.is_file() for path in (manifest_path, env_path, agent_path)):
        raise ValueError("EX-41 U21 readback files are incomplete")
    saved = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    expected_modes = manifest.get("modes", {}).get("ex41", {})
    actual_modes = saved.get("modes", {}).get("ex41", {})
    # The manifest contract is JSON.  Compare its persisted representation so
    # JSON-compatible Python tuples are read back as lists without a false
    # mismatch, while every persisted value remains checked.
    expected_modes_json = json.loads(json.dumps(expected_modes, ensure_ascii=False, allow_nan=False))
    if actual_modes != expected_modes_json:
        expected_keys = set(expected_modes_json) if isinstance(expected_modes_json, dict) else set()
        actual_keys = set(actual_modes) if isinstance(actual_modes, dict) else set()
        differing = sorted(key for key in expected_keys | actual_keys
                           if expected_modes_json.get(key) != actual_modes.get(key))
        raise ValueError("EX-41 U21 manifest readback differs from in-memory manifest: "
                         + ", ".join(differing))
    if (actual_modes.get("plan_sha256") != plan.sha256
            or actual_modes.get("effective_sha256") != plan.effective_sha256):
        raise ValueError("EX-41 U21 plan SHA readback differs")
    parent = actual_modes.get("parent")
    if (not isinstance(parent, dict)
            or parent.get("sha256") != plan.parent_sha256
            or parent.get("sha256") != parent_receipt.get("sha256")
            or parent.get("checkpoint") != parent_receipt.get("checkpoint")):
        raise ValueError("EX-41 U21 parent readback differs")
    if hashlib.sha256(Path(parent["checkpoint"]).read_bytes()).hexdigest() != parent["sha256"]:
        raise ValueError("EX-41 U21 parent checkpoint SHA changed")
    from foothold_s2.runners.manifest import yaml_flat

    for key, path in (("env", env_path), ("agent", agent_path)):
        if saved.get("yaml", {}).get(key) != yaml_flat(str(path)):
            raise ValueError(f"EX-41 U21 persisted {key}.yaml differs from manifest")
    initial_contract = actual_modes.get("initial_dr_contract", {})
    if (initial_contract.get("scale") != 0.5
            or initial_contract.get("before_first_reset") is not True):
        raise ValueError("EX-41 U21 initial DR contract is not 0.5 before first reset")
    raw_env = getattr(env, "unwrapped", env)
    applied = getattr(raw_env, "_ex41_initial_dr_scale_applied", None)
    env_scale = getattr(raw_env, "_ex40_dr_scale", None)
    runtime_scale = getattr(dr_runtime, "scale", None)
    if (applied != 0.5 or env_scale != 0.5 or runtime_scale != 0.5):
        raise ValueError("EX-41 U21 first-reset DR readback is not 0.5")
    return {
        "format": "foothold-ex41-start-readback/1",
        "status": "verified",
        "plan_sha256": plan.sha256,
        "effective_sha256": plan.effective_sha256,
        "parent_checkpoint": parent["checkpoint"],
        "parent_sha256": parent["sha256"],
        "env_yaml_sha256": hashlib.sha256(env_path.read_bytes()).hexdigest(),
        "agent_yaml_sha256": hashlib.sha256(agent_path.read_bytes()).hexdigest(),
        "first_reset_dr_scale": applied,
        "runtime_dr_scale": runtime_scale,
    }


def write_ex41_start_readback(log_dir: str | Path, receipt: dict[str, Any]) -> Path:
    """Atomically persist the verified, user-readable U21 readback receipt."""
    root = _require_ex41_run_path(log_dir).resolve(strict=True)
    if receipt.get("format") != "foothold-ex41-start-readback/1" or receipt.get("status") != "verified":
        raise ValueError("EX-41 U21 readback receipt is not verified")
    target = root / "ex41_start_readback.json"
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)
    return target


def attach_ex41_stand_runtime_data(env: Any) -> dict[str, Any]:
    """Provide the realized per-env mass consumed by the inherited EX-40 stand rewards."""
    import torch

    raw = getattr(env, "unwrapped", env)
    masses = raw.scene["robot"].root_physx_view.get_masses()
    if masses.ndim != 2 or masses.shape[0] != int(raw.num_envs) or masses.shape[1] <= 0:
        raise ValueError("EX-41 realized per-env robot mass tensor is invalid")
    total = masses.sum(dim=1).to(device=raw.device)
    if not bool(torch.isfinite(total).all()) or bool((total <= 0).any()):
        raise ValueError("EX-41 realized per-env robot masses must be finite and positive")
    raw._ex40_total_mass_kg = total
    from foothold_s2.rewards.basic_gait_bundle import StandSensorEvidence

    raw._ex40_stand_evidence = StandSensorEvidence.from_env(raw)
    return {"num_envs": int(total.numel()), "mass_min_kg": float(total.min().item()),
            "mass_max_kg": float(total.max().item()), "source": "root_physx_view.get_masses"}


def normalize_ex41_dr_baselines(env: Any, *, additional_envs=(),
                                reset_guard_log: bool = False) -> dict[str, Any]:
    """Normalize checkpoint DR baselines on both runtime and event-owned envs."""
    import torch

    raw = getattr(env, "unwrapped", env)
    scene = getattr(raw, "scene", None)
    device = getattr(raw, "device", None)
    if device is None:
        device = getattr(scene, "device", None)
    owners = [raw]
    owners.extend(owner for owner in additional_envs if owner is not None and owner is not raw)
    tracked = ("_ex40_dr_com_baseline", "_ex40_dr_motor_baselines",
               "_ex40_dr_gain_baselines", "_ex40_dr_delay_baseline",
               "_ex40_dr_delay_baselines")
    has_state = any(any(getattr(owner, name, None) is not None for name in tracked)
                    or getattr(owner, "action_manager", None) is not None
                    or getattr(owner, "scene", None) is not None for owner in owners)
    if device is None and has_state:
        raise ValueError("EX-41 resumed DR baseline target device is unavailable")
    if device is None:
        return {"device": None, "state": "no_device_bound_dr_state",
                "com_baseline": {"state": "absent"}, "motor_baselines": {},
                "other_baselines": {}, "action_delay": {"state": "absent"},
                "owners": []}
    device = torch.device(device)

    def move_tree(value: Any, path: str):
        if torch.is_tensor(value):
            source = str(value.device)
            moved = value if value.device == device else value.to(device=device).clone()
            return moved, {"state": "matched" if source == str(device) else "normalized",
                           "from_device": source, "to_device": str(moved.device),
                           "path": path}
        if isinstance(value, dict):
            moved, receipts = {}, {}
            for key, item in value.items():
                moved[key], receipts[str(key)] = move_tree(item, f"{path}.{key}")
            return moved, receipts
        if isinstance(value, list):
            moved, receipts = [], {}
            for index, item in enumerate(value):
                child, receipt = move_tree(item, f"{path}[{index}]")
                moved.append(child)
                receipts[str(index)] = receipt
            return moved, receipts
        if isinstance(value, tuple):
            moved, receipts = [], {}
            for index, item in enumerate(value):
                child, receipt = move_tree(item, f"{path}[{index}]")
                moved.append(child)
                receipts[str(index)] = receipt
            return tuple(moved), receipts
        if value is None:
            return None, {"state": "absent", "path": path}
        return value, {"state": "non_tensor", "path": path}

    owner_receipts = []
    primary_receipt: dict[str, Any] = {}
    for index, owner in enumerate(owners):
        row: dict[str, Any] = {"owner_index": index}
        if reset_guard_log:
            owner._ex41_dr_device_guard_logged = set()
        for name in tracked:
            value = getattr(owner, name, None)
            moved, receipt = move_tree(value, name)
            if value is not None:
                setattr(owner, name, moved)
            row[name] = receipt
        action_receipt = {"state": "absent"}
        manager = getattr(owner, "action_manager", None)
        get_term = getattr(manager, "get_term", None)
        if callable(get_term):
            try:
                action = get_term("joint_pos")
            except (KeyError, LookupError, ValueError):
                action = None
            delay = getattr(action, "delay", None)
            if torch.is_tensor(delay):
                moved, action_receipt = move_tree(delay, "action_manager.joint_pos.delay")
                action.delay = moved
            if action is not None and torch.is_tensor(getattr(action, "_prev", None)):
                action._prev, prev_receipt = move_tree(
                    action._prev, "action_manager.joint_pos._prev")
                action_receipt["_prev"] = prev_receipt
            if action is not None and torch.is_tensor(getattr(action, "_ex40_sample_counts", None)):
                action._ex40_sample_counts, sample_receipt = move_tree(
                    action._ex40_sample_counts, "action_manager.joint_pos._ex40_sample_counts")
                action_receipt["_ex40_sample_counts"] = sample_receipt
        physical_receipt: dict[str, Any] = {}
        scene = getattr(owner, "scene", None)
        if scene is not None:
            try:
                asset = scene["robot"]
            except (KeyError, LookupError, TypeError):
                asset = None
            if asset is not None:
                asset_data = getattr(asset, "data", None)
                for name in ("default_joint_stiffness", "default_joint_damping"):
                    value = getattr(asset_data, name, None)
                    if torch.is_tensor(value):
                        moved, physical_receipt[f"data.{name}"] = move_tree(
                            value, f"scene.robot.data.{name}")
                        setattr(asset_data, name, moved)
                for actuator_name, actuator in getattr(asset, "actuators", {}).items():
                    for name in ("stiffness", "damping", "effort_limit", "_saturation_effort"):
                        value = getattr(actuator, name, None)
                        if torch.is_tensor(value):
                            moved, physical_receipt[f"{actuator_name}.{name}"] = move_tree(
                                value, f"scene.robot.actuators.{actuator_name}.{name}")
                            setattr(actuator, name, moved)
        row["action_delay"] = action_receipt
        row["physical_dr_tensors"] = physical_receipt
        owner_receipts.append(row)
        if index == 0:
            primary_receipt = {
                "com_baseline": row["_ex40_dr_com_baseline"],
                "motor_baselines": row["_ex40_dr_motor_baselines"],
                "other_baselines": {name: row[name] for name in tracked
                                    if name not in ("_ex40_dr_com_baseline",
                                                    "_ex40_dr_motor_baselines")},
                "action_delay": action_receipt, "physical_dr_tensors": physical_receipt,
            }
    return {"device": str(device), **primary_receipt, "owners": owner_receipts}


def prepare_ex41_env_cfg(env_cfg: Any, plan, *,
                         stage_zero_approval: dict[str, Any] | None = None) -> dict[str, Any]:
    """Install EX-41-only pose observations, terrain, DR consumers, and W86 before gym.make."""
    from foothold_s2.rewards.basic_gait_bundle import (
        apply_ex39_settings, apply_ex40_stand_settings, apply_settings, validate_settings,
    )
    from foothold_s2.curriculum.ex41 import prepare_terrain_cfg
    from foothold_s2.curriculum.ex40_dr_runtime import install_runtime_events
    from foothold_s2.rewards.w86_runtime import prepare_env_cfg
    from foothold_s2.eval.ex41_eval_loader import prepare_ex41_env_cfg as prepare_pose_env_cfg

    dr = plan.domain_randomization
    ranges = dr["full_ranges"]
    first_rewards = dict(plan.stages[0].rewards)
    reward_settings = validate_settings(
        {key: first_rewards[key] for key in ("track_ang_vel", "track_lin_vel", "joint_acc", "hip_pos_penalty")},
        lin_vel_z_schedule=False, feet_regulation_weight=None)
    apply_settings(env_cfg, reward_settings)
    ex39_reward_receipt = apply_ex39_settings(env_cfg)
    apply_ex40_stand_settings(env_cfg, plan.stand_cfg)
    pose_receipt = prepare_pose_env_cfg(env_cfg)
    event_receipt = install_runtime_events(
        env_cfg, ranges, tuple(dr["push_interval_s"]),
        delay_max_s=float(ranges["delay_s"][1]))
    dr_receipt = install_initial_dr_scale(
        env_cfg, plan.initial_dr_scale, scoped_approval=stage_zero_approval)
    terrain_receipt = prepare_terrain_cfg(
        env_cfg, plan,
        initial_policy="performance" if stage_zero_approval is not None else None,
        initial_level_cap=5 if stage_zero_approval is not None else None)
    w86_receipt = prepare_env_cfg(env_cfg, plan)
    return {"events": event_receipt, "initial_dr": dr_receipt,
            "terrain": terrain_receipt, "w86": w86_receipt,
            "pose_observation": pose_receipt,
            "reward_contract": {"source": "EX-41 first stage plus EX-39/EX-40 helpers",
                                "first_stage_weights": first_rewards,
                                "ex39": ex39_reward_receipt,
                                "stand": dict(plan.stand_cfg)}}


def first_observation_readback(raw: Any, expected_envs: int) -> dict[str, Any]:
    """Validate and summarize the actual first TensorDict consumed by StartRunner."""
    required = {"policy": [45], "depth": [60, 60], "gt_map": [512],
                "gt_feet": [100], "base_vel": [3], "contacts": [4],
                "pose_cmd": [2]}
    groups = {}
    for name, expected_shape in required.items():
        if name not in raw.keys():
            raise ValueError(f"EX-41 first observation missing group {name}")
        value = raw[name]
        got = list(value.shape[1:])
        if name == "depth" and value[0].numel() == 3600:
            got = [60, 60]
        if got != expected_shape or int(value.shape[0]) != int(expected_envs):
            raise ValueError(f"EX-41 first observation shape differs for {name}: {list(value.shape)}")
        groups[name] = list(value.shape[1:])
    pose = raw["pose_cmd"]
    if not bool(pose.isfinite().all().item()):
        raise ValueError("EX-41 first pose_cmd is not finite")
    nonzero_by_column = pose.detach().ne(0).any(dim=0).cpu().tolist()
    if nonzero_by_column != [False, False]:
        raise ValueError("EX-41 first pose_cmd columns are not both zero")
    return {"groups": groups,
            "pose_cmd": {"columns": ["height_delta_m", "body_roll_rad"],
                         "zero_by_column": [True, True],
                         "shape": list(pose.shape)}}


@contextmanager
def capture_first_observation(env: Any):
    """Record StartRunner's existing first read without computing observations twice."""
    original = env.get_observations
    receipt: dict[str, Any] = {}

    def capture(*args, **kwargs):
        raw = original(*args, **kwargs)
        if not receipt:
            receipt.update(first_observation_readback(raw, env.num_envs))
        return raw

    env.get_observations = capture
    try:
        yield receipt
    finally:
        env.get_observations = original


def _authorized_initial_dr_scale(scale: float, scoped_approval: dict[str, Any] | None) -> bool:
    if type(scale) not in (int, float) or not math.isfinite(float(scale)):
        return False
    if float(scale) == 0.5:
        return scoped_approval is None
    if float(scale) != 1.0 or not isinstance(scoped_approval, dict):
        return False
    scope = scoped_approval.get("scope")
    common = (scoped_approval.get("production_launch_allowed") is False
              and scoped_approval.get("later_stages_authorized") is False
              and isinstance(scope, dict)
              and scope.get("start_update") == 0
              and scope.get("later_stages_authorized") is False
              and re.fullmatch(r"[0-9a-f]{64}", str(scope.get("parent_sha256", "")))
              and re.fullmatch(r"[0-9a-f]{64}", str(scoped_approval.get("approvals_sha256", ""))))
    if not common:
        return False
    if scoped_approval.get("state") == "stage_e0_only_authorized":
        # Bounded E0 cell (validate_stage_e0_authorization): m13000 -> 250 updates, nothing later.
        return scope.get("stage_id") == "E0" and scope.get("maximum_updates") == 250
    if scoped_approval.get("state") == "stage_e1_only_authorized":
        # Bounded E1 first segment (validate_stage_e1_authorization): E0 m250 -> the cell's own maximum, no extension
        # and no later stage. The bound is read from the approved cell, not written here.
        bound, interval = scope.get("maximum_updates"), scoped_approval.get("boundary_evaluation_interval_updates")
        return (scope.get("stage_id") == "E1" and type(bound) is int and bound > 0
                and scoped_approval.get("extension_authorized") is False
                and type(interval) is int and 0 < interval <= bound and bound % interval == 0)
    return (scoped_approval.get("state") == "stage_zero_only_authorized"
            and scope.get("stage_id") == "EX42_0_T0_prime"
            and scope.get("source_stage_id") == "T0_prime"
            and scope.get("maximum_updates") == 1000)


def install_initial_dr_scale(env_cfg: Any, scale: float, *,
                             scoped_approval: dict[str, Any] | None = None) -> dict[str, Any]:
    """Seed the existing EX40 reset terms before the environment's first reset.

    Isaac's reset manager calls these configured functions with the environment
    and env_ids. Wrapping the actual registered functions makes the initial
    scale visible to the existing DR consumers without replacing their logic.
    """
    if not _authorized_initial_dr_scale(scale, scoped_approval):
        raise ValueError("Initial DR scale requires EX-41 0.5 or a bounded EX-42 stage-zero approval")
    scale = float(scale)
    stage_zero = scoped_approval is not None
    events = getattr(env_cfg, "events", None)
    names = ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")
    rows = {}
    for name in names:
        term = getattr(events, name, None)
        func = getattr(term, "func", None)
        if not callable(func):
            raise ValueError(f"EX-41 reset DR consumer missing: {name}")

        @wraps(func)
        def seeded(env, *args, _func=func, _name=name, **kwargs):
            # Seed only at the first reset. Stage progression owns subsequent
            # scale changes, and later environment resets must preserve them.
            marker = ("_ex42_stage_zero_initial_dr_scale_applied" if stage_zero
                      else "_ex41_initial_dr_scale_applied")
            if getattr(env, marker, None) is None:
                env._ex40_dr_scale = scale
                setattr(env, marker, scale)
            device_receipt = normalize_ex41_dr_baselines(env)
            device_receipt["reset_term"] = _name
            env._ex41_dr_device_guard = device_receipt
            logged_terms = set(getattr(env, "_ex41_dr_device_guard_logged", ()))
            if _name not in logged_terms:
                print("EX41_RESET_DR_DEVICE_GUARD "
                      + json.dumps(device_receipt, sort_keys=True), flush=True)
                logged_terms.add(_name)
                env._ex41_dr_device_guard_logged = logged_terms
            return _func(env, *args, **kwargs)

        term.func = seeded
        rows[name] = "wrapped-existing-reset-consumer"
    return {"scale": scale, "scope": "ex42_stage_zero_only" if stage_zero else "ex41_initial",
            "before_first_reset": True, "reset_terms": rows}


def set_live_initial_dr_scale(dr_runtime: Any, env: Any, scale: float, *,
                              scoped_approval: dict[str, Any] | None = None) -> dict[str, Any]:
    """Align the existing runtime readback and env before the first rollout."""
    if not _authorized_initial_dr_scale(scale, scoped_approval):
        raise ValueError("Initial DR scale requires EX-41 0.5 or a bounded EX-42 stage-zero approval")
    scale = float(scale)
    dr_runtime.scale = scale
    env._ex40_dr_scale = scale
    if getattr(env, "_ex40_dr_scale", None) != scale or dr_runtime.scale != scale:
        raise ValueError("Initial DR readback did not apply")
    return {"runtime_scale": dr_runtime.scale, "env_scale": env._ex40_dr_scale}


def validate_rehearsal_dr_samples(row: dict[str, Any], ranges: dict[str, Any],
                                  scale: float = 0.8) -> dict[str, Any]:
    """Check actual EX-40 event/action readback against one EX-41 rehearsal scale."""
    from foothold_s2.curriculum.ex40_dr import interpolate_range

    if type(scale) not in (int, float) or not math.isclose(float(scale), 0.8, abs_tol=1e-12):
        raise ValueError("EX-41 DR proof is fixed to scale 0.8")
    actual = row.get("actual_samples") if isinstance(row, dict) else None
    required = ("base_com_offset_m", "actuator_gains", "motor_strength_multiplier",
                "motor_effort_limit", "motor_saturation_effort", "push_velocity_delta")
    if not isinstance(actual, dict):
        raise ValueError("EX-41 DR proof actual reset/event samples are missing")
    for name in required:
        stats = actual.get(name)
        if (not isinstance(stats, dict) or type(stats.get("count")) is not int
                or stats["count"] <= 0):
            raise ValueError(f"EX-41 DR proof sample is missing: {name}")
        for field in ("min", "max", "mean"):
            if (type(stats.get(field)) not in (int, float)
                    or not math.isfinite(float(stats[field]))):
                raise ValueError(f"EX-41 DR proof sample is nonfinite: {name}.{field}")

    def bounds(target, neutral):
        return interpolate_range((neutral, neutral), tuple(target), float(scale))

    expected = {
        "base_com_offset_m": (
            min(bounds(ranges["base_com"][axis], 0.0)[0] for axis in ("x", "y", "z")),
            max(bounds(ranges["base_com"][axis], 0.0)[1] for axis in ("x", "y", "z"))),
        "actuator_gains": (
            min(bounds(ranges["actuator_gains"][key], 1.0)[0]
                for key in ("stiffness_scale", "damping_scale")),
            max(bounds(ranges["actuator_gains"][key], 1.0)[1]
                for key in ("stiffness_scale", "damping_scale"))),
        "motor_strength_multiplier": bounds(ranges["motor_strength"], 1.0),
        "push_velocity_delta": (
            min(bounds(pair, 0.0)[0] for pair in ranges["push_velocity"].values()),
            max(bounds(pair, 0.0)[1] for pair in ranges["push_velocity"].values())),
    }
    for name, (low, high) in expected.items():
        got = actual[name]
        if got["min"] < low - 1e-6 or got["max"] > high + 1e-6:
            raise ValueError(f"EX-41 DR proof sample outside scale 0.8 range: {name}")
    delay = row.get("delay_readback")
    if (not isinstance(delay, dict) or type(delay.get("reset_sample_count")) is not int
            or delay["reset_sample_count"] <= 0
            or not math.isclose(float(delay.get("configured_max_seconds", -1)),
                                float(ranges["delay_s"][1]) * float(scale), abs_tol=1e-12)
            or (delay.get("observed_max_substeps") or 0) > delay.get("max_allowed_substeps", -1)):
        raise ValueError("EX-41 DR proof delayed-action readback outside scale 0.8 range")
    if not math.isclose(float(row.get("scale", -1)), float(scale), abs_tol=1e-12):
        raise ValueError("EX-41 DR proof runtime scale readback differs")
    return {"scale": float(scale), "sample_bounds": expected,
            "sample_counts": {name: actual[name]["count"] for name in required},
            "delay_readback": delay}


def run_rehearsal_dr_proof(env: Any, dr_runtime: Any, ranges: dict[str, Any],
                           output_dir: str | Path, plan_sha256: str,
                           delay_max_s: float) -> dict[str, Any]:
    """Use real reset and interval event consumers at 0.8, then restore 0.5."""
    if not math.isclose(float(delay_max_s), float(ranges["delay_s"][1]), abs_tol=1e-12):
        raise ValueError("EX-41 rehearsal delay cap differs from the pinned DR range")
    raw = getattr(env, "unwrapped", env)
    target = Path(output_dir) / "ex41_dr_scale_08_readback.json"
    if target.exists():
        try:
            prior = json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise ValueError("EX-41 existing DR proof receipt is unreadable") from exc
        if (prior.get("format") != "foothold-ex41-dr-scale-proof/1"
                or prior.get("state") != "verified"
                or prior.get("plan_sha256") != plan_sha256
                or prior.get("scale") != 0.8
                or prior.get("reset_forced") is not True
                or prior.get("restored_scale") != 0.5
                or prior.get("interval_elapsed_s") != 15.0):
            raise ValueError("EX-41 existing DR proof receipt is not a reusable verified 0.8 proof")
        checked = validate_rehearsal_dr_samples(prior.get("runtime_readback"), ranges, 0.8)
        if prior.get("range_check") != json.loads(json.dumps(checked, allow_nan=False)):
            raise ValueError("EX-41 existing DR proof range receipt differs from its readback")
        return prior
    if getattr(raw, "_ex41_initial_dr_scale_applied", None) is None:
        raw._ex40_dr_scale = 0.5
        env.reset()
    if getattr(raw, "_ex41_initial_dr_scale_applied", None) != 0.5:
        raise ValueError("EX-41 rehearsal first-reset scale is not 0.5")

    dr_runtime.scale = 0.8
    raw._ex40_dr_scale = 0.8
    raw._ex40_dr_samples = {}
    try:
        env.reset()
        # The installed manager consumes interval events only after dt passes.
        # Advancing one configured maximum interval forces the real push term.
        raw.event_manager.apply("interval", dt=15.0)
        row = dr_runtime.summary()
        checked = validate_rehearsal_dr_samples(row, ranges, 0.8)
        receipt = {"format": "foothold-ex41-dr-scale-proof/1", "state": "verified",
                   "plan_sha256": plan_sha256, "scale": 0.8,
                   "reset_forced": True, "interval_elapsed_s": 15.0,
                   "runtime_readback": row, "range_check": checked,
                   "restored_scale": 0.5}
    except Exception as exc:
        receipt = {"format": "foothold-ex41-dr-scale-proof/1", "state": "failed",
                   "plan_sha256": plan_sha256, "scale": 0.8,
                   "reset_forced": True, "interval_elapsed_s": 15.0,
                   "error": f"{type(exc).__name__}: {exc}"}
        raise
    finally:
        dr_runtime.scale = 0.5
        raw._ex40_dr_scale = 0.5
        raw._ex40_dr_samples = {}
        env.reset()
        if dr_runtime.scale != 0.5 or raw._ex40_dr_scale != 0.5:
            raise RuntimeError("EX-41 rehearsal failed to restore initial DR scale 0.5")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + ".tmp")
            temp.write_text(json.dumps(receipt, sort_keys=True, indent=2,
                                       allow_nan=False) + "\n", encoding="utf-8")
            os.replace(temp, target)
    return receipt


def enrich_score_file(score_path: str | Path, map_modes_path: str | Path,
                      stand_paths: dict[str, str | Path],
                      table_path: str | Path, out_path: str | Path,
                      w86_metrics_path: str | Path) -> Path:
    """Enrich the score from evaluation and same-iteration W86 evidence."""
    from foothold_s2.curriculum.ex41_scoring import (
        enrich_score_metrics, enrich_training_metrics,
    )

    plan = load_fixed_plan(table_path)
    score = json.loads(Path(score_path).read_text(encoding="utf-8-sig"))
    result = enrich_score_metrics(score, map_modes_path, stand_paths, plan)
    result = enrich_training_metrics(
        result,
        w86_metrics_path,
        snapshot_dir=Path(out_path).parent / "w86_evidence",
    )
    modes = json.loads(Path(map_modes_path).read_text(encoding="utf-8-sig"))
    eval_pred = modes.get("modes", {}).get("eval_pred")
    commands = modes.get("commands")
    if not isinstance(eval_pred, dict) or not isinstance(commands, dict) or set(eval_pred) != set(commands):
        raise ValueError("EX-41 eval_pred tracking source has incomplete command cells")
    tracking_cells = {}
    axes = ((0, "vx_abs_error_mean_alive_mps"),
            (1, "vy_abs_error_mean_alive_mps"),
            (2, "wz_abs_error_mean_alive_radps"))
    for case, row in eval_pred.items():
        command = commands[case]
        per_env = row.get("per_env") if isinstance(row, dict) else None
        if (not isinstance(command, list) or len(command) != 3
                or not isinstance(per_env, list) or len(per_env) != 64
                or type(row.get("gt_used")) is not int or row["gt_used"] != 0
                or type(row.get("alive_envs_at_end")) is not int):
            raise ValueError(f"EX-41 eval_pred tracking evidence is invalid: {case}")
        medians = {}
        measured = {}
        for axis, field in axes:
            values = []
            for env_row in per_env:
                if (not isinstance(env_row, dict) or type(env_row.get("samples_alive")) is not int
                        or env_row["samples_alive"] <= 0):
                    continue
                value = env_row.get(field)
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    values.append(float(value))
            if len(values) < 60:
                raise ValueError(f"EX-41 eval_pred tracking has fewer than 60 measured envs: {case}/{field}")
            ordered = sorted(values)
            middle = len(ordered) // 2
            medians[field] = (ordered[middle] if len(ordered) % 2
                              else (ordered[middle - 1] + ordered[middle]) / 2.0)
            measured[field] = len(values)
        tracking_cells[case] = {
            "gt_used": 0,
            "alive_envs_at_end": row["alive_envs_at_end"],
            "tracking_medians": medians,
            "measured_envs": measured,
        }
    result.setdefault("metrics", {})["eval_pred_tracking_errors"] = tracking_cells
    target = Path(out_path)
    if target.resolve() == Path(score_path).resolve():
        raise ValueError("EX-41 enriched score must not overwrite its draft")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(target)
    return target
