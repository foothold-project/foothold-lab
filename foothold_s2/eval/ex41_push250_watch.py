"""Checkpoint-gated D171 push checks on GPU1, outside the live trainer/score-watch."""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from foothold_s2.eval.ex41_gpu_priority import (
    DEFAULT_MARKER,
    _pid_is_live,
    _read_owner,
    gpu1_priority,
)
from foothold_s2.experiment_registry import operational_definition, paths_for_run
from foothold_s2.eval.ex41_push_ladder import TERRAIN_CASES

GPU1_UUID = "315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f"
DEFAULT_PYTHON = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
DEFAULT_OUTPUT = Path("D:/mai-tmp/runner/ex41_push250")
TASK = "FootholdS2-Go2-S2-SB-v0"
DESKTOP_PROCESS_NAMES = {
    "dwm.exe", "explorer.exe", "shellhost.exe", "searchhost.exe",
    "startmenuexperiencehost.exe", "shellexperiencehost.exe", "textinputhost.exe",
    "crossdeviceresume.exe", "applicationframehost.exe", "systemsettings.exe",
    "chrome.exe", "msedge.exe", "msedgewebview2.exe", "photos.exe", "snippingtool.exe",
    "chatgpt.exe", "discord.exe", "potplayer64.exe", "windowsTerminal.exe".casefold(),
    "logioptionsplus_agent.exe", "logioverlay.exe", "orca.exe", "code.exe",
}


def _explicit_device(cmdline: list[str]) -> str | None:
    for index, arg in enumerate(cmdline):
        low = arg.casefold()
        if low in ("--device", "--physics_device", "--active_gpu"):
            return cmdline[index + 1] if index + 1 < len(cmdline) else None
        for prefix in ("--device=", "--physics_device=", "--active_gpu="):
            if low.startswith(prefix):
                return arg.split("=", 1)[1]
    return None


def _tasklist_process_name(pid: int) -> str | None:
    result = subprocess.run(["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=10, check=False)
    if result.returncode != 0:
        return None
    try:
        row = next(csv.reader([line for line in result.stdout.splitlines() if line.strip()]))
    except (StopIteration, csv.Error):
        return None
    return row[0] if len(row) >= 2 and row[1].strip() == str(pid) else None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checkpoint_for_update(run_dir: Path, score_dir: Path, local_iteration: int) -> dict[str, Any] | None:
    """Return a checkpoint only after manifest progress, manifest SHA and score SHA agree."""
    if type(local_iteration) is not int or local_iteration <= 0:
        raise ValueError("local_iteration must be a positive integer")
    run_dir, score_dir = Path(run_dir), Path(score_dir)
    manifest = _read_json(run_dir / "manifest.json")
    if not manifest:
        return None
    progress = manifest.get("progress") or {}
    checkpoints = manifest.get("checkpoints") or {}
    if type(progress.get("completed_updates")) is not int or progress["completed_updates"] < local_iteration:
        return None
    checkpoint = run_dir / f"model_{local_iteration}.pt"
    if not checkpoint.is_file():
        return None
    expected_sha = checkpoints.get(checkpoint.name)
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        return None
    actual_sha = _sha256(checkpoint)
    if actual_sha != expected_sha:
        return None
    score_candidates = sorted(score_dir.glob(f"score_{local_iteration}_*.json"))
    for score_path in score_candidates:
        score = _read_json(score_path)
        if not score or score.get("evaluation_state") not in ("complete", "HOLD"):
            continue
        if score.get("checkpoint_sha256") != actual_sha:
            continue
        recorded_path = score.get("checkpoint_path")
        if recorded_path and Path(recorded_path).resolve() != checkpoint.resolve():
            continue
        return {"local_iteration": local_iteration, "checkpoint": checkpoint,
                "sha256": actual_sha, "manifest_progress": progress["completed_updates"],
                "score": score_path, "score_sha256": _sha256(score_path),
                "measurement_state": score.get("evaluation_state"),
                "judgement_state": ("hold" if score.get("maintenance_pass") is False else "pass")
                if score.get("evaluation_state") == "complete" else "not_judged"}
    return None


def output_path_for_global_iteration(out_dir: Path, global_iteration: int) -> Path:
    if type(global_iteration) is not int or global_iteration <= 0:
        raise ValueError("global_iteration must be a positive integer")
    return Path(out_dir) / f"{global_iteration}.json"


def build_child_argv(*, checkpoint: Path, out: Path, terrain: str, device: str = "cuda:1",
                     python: Path = DEFAULT_PYTHON, task: str = TASK, seed: int = 42) -> list[str]:
    if terrain not in TERRAIN_CASES:
        raise ValueError(f"unsupported D171 terrain: {terrain}")
    if device != "cuda:1":
        raise ValueError("push250 watcher is restricted to GPU1")
    return [str(python), "-m", "foothold_s2.eval.eval_map_modes",
            "--task", task, "--checkpoint", str(checkpoint), "--out", str(out),
            "--envs", "1536", "--steps", "350", "--modes", "eval_gt",
            "--command-suite", "core", "--commands", "all", "--fixed-terrain", "--fixed-level", "0",
            "--eval-seed", str(seed), "--push-ladder", "--push-ladder-profile", "push250",
            "--push-ladder-terrain", terrain, "--push-ladder-map-mode", "eval_gt",
            "--push-ladder-command", "walk_1.0", "--push-ladder-directions", "full",
            "--headless", "--device", device,
            "--kit_args=--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache"]


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True,
                               allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def gpu1_busy_snapshot(marker: Path = DEFAULT_MARKER) -> dict[str, Any]:
    """Read-only GPU1 gate; desktop GUI compute clients are intentionally ignored."""
    import psutil

    query = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name", "--format=csv,noheader"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=20, check=False)
    if query.returncode != 0:
        raise RuntimeError(f"GPU1 admission query failed rc={query.returncode}")
    busy = []
    for line in query.stdout.splitlines():
        fields = [part.strip() for part in line.split(",", 2)]
        if len(fields) != 3 or fields[0].casefold().removeprefix("gpu-") != GPU1_UUID:
            continue
        try:
            pid = int(fields[1])
            proc = psutil.Process(pid)
            name = proc.name()
            cmdline = proc.cmdline()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except (psutil.AccessDenied, OSError, ValueError) as exc:
            pid = int(fields[1]) if fields[1].isdigit() else -1
            name = _tasklist_process_name(pid) if pid > 0 else None
            if name and name.casefold() in DESKTOP_PROCESS_NAMES:
                continue
            busy.append({"pid": pid if pid > 0 else fields[1], "state": "unknown_blocks",
                         "reason": type(exc).__name__})
            continue
        if name.casefold() in DESKTOP_PROCESS_NAMES:
            continue
        command = " ".join(cmdline)
        low = (name + " " + command).casefold()
        if "python" in name.casefold() or "kit" in low or "isaac" in low:
            assigned = _explicit_device(cmdline)
            if assigned and assigned.casefold() != "cuda:1":
                continue
            busy.append({"pid": pid, "name": name, "state": "experiment_process",
                         "device": assigned or "unknown"})
    owner_state = "absent"
    if marker.exists():
        try:
            owner = _read_owner(marker)
            owner_state = "live" if owner and _pid_is_live(owner) else "stale"
            if owner_state == "live":
                busy.append({"pid": owner["pid"], "state": "priority_marker"})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError):
            owner_state = "unknown_blocks"
            busy.append({"pid": None, "state": "priority_marker_unknown"})
    return {"gpu_uuid": GPU1_UUID, "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "busy": busy, "marker_state": owner_state, "state": "busy" if busy else "idle"}


@contextmanager
def gpu1_idle_priority(marker: Path, *, job: str, iteration: int,
                       timeout_seconds: float = 300, poll_seconds: float = 10,
                       snapshot=gpu1_busy_snapshot, priority=gpu1_priority,
                       sleep=time.sleep):
    """Wait without owning P1, then claim and recheck; release on admission races."""
    started = time.monotonic()
    checks = 0
    while True:
        if time.monotonic() - started > timeout_seconds:
            raise TimeoutError("GPU1 did not become idle within the bounded push250 wait")
        checks += 1
        before = snapshot(marker)
        if before.get("state") != "idle":
            sleep(poll_seconds)
            continue
        candidate = priority(marker, job=job, iteration=iteration)
        try:
            owner = candidate.__enter__()
        except RuntimeError:
            sleep(poll_seconds)
            continue
        after = snapshot(marker)
        others = [row for row in after.get("busy", []) if row.get("pid") != owner.get("pid")]
        if after.get("marker_state") == "unknown_blocks" or others:
            candidate.__exit__(None, None, None)
            sleep(poll_seconds)
            continue
        after.update(checks_before_claim=checks,
                     waited_s_before_claim=time.monotonic() - started)
        try:
            yield owner, after
        finally:
            candidate.__exit__(None, None, None)
        return


def matching_terminal_result(path: Path, *, local_iteration: int,
                             global_iteration: int, checkpoint_sha256: str) -> bool:
    """True only for an already-published terminal result for this exact checkpoint."""
    row = _read_json(Path(path))
    if not isinstance(row, dict):
        raise ValueError("existing push250 result is unreadable")
    if (row.get("local_iteration") != local_iteration
            or row.get("global_iteration") != global_iteration
            or row.get("checkpoint_sha256") != checkpoint_sha256
            or row.get("state") not in ("done", "HOLD")):
        raise ValueError("existing push250 result identity is not the completed checkpoint")
    return True


def _compare_to_baseline(result: dict[str, Any], baseline_path: Path) -> dict[str, Any] | None:
    baseline = _read_json(baseline_path)
    if not baseline or baseline.get("state") != "done":
        return None
    comparison = {}
    current_by_terrain = {row.get("terrain"): row for row in result.get("terrains", [])}
    base_by_terrain = {row.get("terrain"): row for row in baseline.get("terrains", [])}
    for terrain in TERRAIN_CASES:
        current = current_by_terrain.get(terrain, {}).get("summary", {})
        base = base_by_terrain.get(terrain, {}).get("summary", {})
        if not current or not base:
            return None
        current_15 = current["d171_1_5_worst_direction"]["survival_fraction"]
        base_15 = base["d171_1_5_worst_direction"]["survival_fraction"]
        comparison[terrain] = {
            "d171_1_5_worst_direction": {"m6000": base_15, "current": current_15,
                                          "difference": current_15 - base_15},
            "record_only": {
                magnitude: {
                    "m6000": base["record_only_magnitudes"][magnitude]["survival_fraction"],
                    "current": current["record_only_magnitudes"][magnitude]["survival_fraction"],
                    "difference": current["record_only_magnitudes"][magnitude]["survival_fraction"]
                                 - base["record_only_magnitudes"][magnitude]["survival_fraction"],
                } for magnitude in ("1.0", "2.0")
            },
        }
    return comparison


def evaluate_checkpoint(checkpoint: Path, *, global_iteration: int, out_dir: Path,
                        worktree: Path, device: str = "cuda:1", python: Path = DEFAULT_PYTHON,
                        task: str = TASK, seed: int = 42, marker: Path = DEFAULT_MARKER,
                        timeout_seconds: int = 1800, local_iteration: int | None = None) -> dict[str, Any]:
    checkpoint = Path(checkpoint).resolve(strict=True)
    out_dir = Path(out_dir)
    destination = output_path_for_global_iteration(out_dir, global_iteration)
    if destination.exists():
        raise FileExistsError(f"refusing duplicate push250 result: {destination}")
    checkpoint_sha = _sha256(checkpoint)
    local_iteration = global_iteration - 6000 if local_iteration is None else int(local_iteration)
    admission = gpu1_busy_snapshot(marker)
    result: dict[str, Any] = {
        "schema": "foothold-ex41-push250-check/1", "state": "running",
        "global_iteration": global_iteration, "local_iteration": local_iteration,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha, "device": device, "seed": seed,
        "profile": {"decision": "D171", "map_mode": "eval_gt", "command": "walk_1.0",
                    "magnitudes_mps": [1.0, 1.5, 2.0], "directions_deg": [0,45,90,135,180,225,270,315],
                    "envs_per_magnitude_direction": 64, "envs_per_terrain": 1536,
                    "terrain_cases": list(TERRAIN_CASES), "level": 0,
                    "push_at_s": 2.0, "follow_s": 5.0},
        "gpu1_admission": admission, "children": [], "started_at": datetime.now(timezone.utc).isoformat(),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_work" / f"{global_iteration}_{checkpoint_sha[:12]}"
    work.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.pop("CUDA_VISIBLE_DEVICES", None)
    env.update(PYTHONUTF8="1", PYTHONUNBUFFERED="1", PYTHONPATH=str(worktree.resolve()),
               CUDA_DEVICE_ORDER="PCI_BUS_ID", KMP_DUPLICATE_LIB_OK="TRUE", OMNI_KIT_ACCEPT_EULA="YES")
    start = time.monotonic()
    try:
        with gpu1_idle_priority(marker, job="EX-41-push250-D171", iteration=global_iteration,
                                timeout_seconds=300) as (owner, claimed_snapshot):
            result["priority_marker"] = owner
            result["gpu1_after_claim"] = claimed_snapshot
            for terrain in TERRAIN_CASES:
                child_out = work / terrain
                child_out.mkdir(parents=True, exist_ok=False)
                argv = build_child_argv(checkpoint=checkpoint, out=child_out, terrain=terrain,
                                        device=device, python=python, task=task, seed=seed)
                log = child_out.with_suffix(".log")
                child_start = time.monotonic()
                with log.open("w", encoding="utf-8", newline="\n") as stream:
                    completed = subprocess.run(argv, cwd=worktree, env=env, stdin=subprocess.DEVNULL,
                                               stdout=stream, stderr=subprocess.STDOUT,
                                               timeout=timeout_seconds,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                               check=False)
                result_path = child_out / "push_ladder.json"
                child: dict[str, Any] = {"terrain": terrain, "argv": argv, "log": str(log),
                                         "rc": completed.returncode, "seconds": time.monotonic() - child_start,
                                         "state": "HOLD"}
                if completed.returncode == 0 and result_path.is_file():
                    cell_result = _read_json(result_path)
                    if (cell_result and cell_result.get("checkpoint_sha256") == checkpoint_sha
                            and cell_result.get("profile") == "push250"
                            and cell_result.get("summary", {}).get("profile") == "D171_push250"):
                        child.update(state="done", summary=cell_result["summary"],
                                     result_path=str(result_path),
                                     result_sha256=_sha256(result_path),
                                     arrays=cell_result.get("arrays"))
                    else:
                        child["reason"] = "child receipt missing or identity/profile mismatch"
                else:
                    child["reason"] = "child rc nonzero or push_ladder.json missing"
                result["children"].append(child)
                if child["state"] != "done":
                    break
    except Exception:
        result["elapsed_s"] = time.monotonic() - start
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        raise
    result["elapsed_s"] = time.monotonic() - start
    result["completed_at"] = datetime.now(timezone.utc).isoformat()
    result["state"] = ("done" if len(result["children"]) == len(TERRAIN_CASES)
                       and all(child["state"] == "done" for child in result["children"])
                       else "HOLD")
    if result["state"] == "done":
        result["terrains"] = [{"terrain": child["terrain"], "summary": child["summary"],
                               "result_path": child["result_path"],
                               "result_sha256": child["result_sha256"]}
                              for child in result["children"]]
        result["d171_all_terrains_passed"] = all(
            child["summary"]["d171_1_5_worst_direction"]["passed"] for child in result["children"])
        if global_iteration != 6000:
            baseline = out_dir / "6000.json"
            result["m6000_comparison"] = _compare_to_baseline(result, baseline) if baseline.exists() else None
    _atomic_json(destination, result)
    return result


def wait_until_gpu1_idle(*, marker: Path = DEFAULT_MARKER, poll_seconds: float = 10.0,
                         timeout_seconds: float = 6 * 60 * 60) -> dict[str, Any]:
    start = time.monotonic()
    checks = 0
    while time.monotonic() - start <= timeout_seconds:
        checks += 1
        snapshot = gpu1_busy_snapshot(marker)
        if snapshot["state"] == "idle":
            snapshot.update(checks=checks, waited_s=time.monotonic() - start)
            return snapshot
        time.sleep(poll_seconds)
    raise TimeoutError("GPU1 did not become idle before the push250 admission timeout")


def wait_for_checkpoint_target(run_dir: Path, score_dir: Path, local_iteration: int, *,
                               state_path: Path, poll_seconds: float = 10.0,
                               checkpoint_reader=checkpoint_for_update,
                               status_reader=None, state_writer=_atomic_json, sleep=time.sleep) -> dict[str, Any]:
    """Wait across trainer failures and resumes; only stable checkpoint+score releases the target."""
    run_dir, score_dir = Path(run_dir), Path(score_dir)
    status_reader = status_reader or (lambda: _read_json(run_dir / "train_start_status.json") or {})
    state_path = Path(state_path)
    while True:
        ready = checkpoint_reader(run_dir, score_dir, local_iteration)
        if ready:
            return ready
        status = status_reader()
        trainer_state = status.get("state", "unknown")
        waiting_state = ("waiting_for_training_resume"
                         if trainer_state in ("failed", "error", "stopped", "complete", "done")
                         else "waiting_for_score_and_stable_checkpoint")
        state_writer(state_path, {
            "state": waiting_state,
            "next_local_iteration": local_iteration,
            "trainer_state": trainer_state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        sleep(poll_seconds)


def score_watch_attempt_finished(score_watch_root: Path, local_iteration: int,
                                 checkpoint_sha256: str) -> tuple[bool, str]:
    """Require score-watch to close this checkpoint before push250 claims GPU1.

    The periodic score can be published before the watcher finishes its
    checkpoint work. In particular, score-watch writes its done state only
    after its evaluation child and any stage-end auxiliary child have returned.
    A missing/in-progress/ambiguous receipt therefore leaves GPU1 to score-watch.
    """
    root = Path(score_watch_root)
    state = _read_json(root / "watch_state.json")
    if not isinstance(state, dict):
        return False, "score_watch_state_missing"
    key = f"{local_iteration}_{checkpoint_sha256}"
    done = (state.get("done") or {}).get(key)
    if not isinstance(done, dict):
        return False, "score_watch_checkpoint_not_closed"
    attempt_path = root / f"model_{local_iteration}_{checkpoint_sha256[:12]}" / "attempt.json"
    attempt = _read_json(attempt_path)
    if not isinstance(attempt, dict):
        return False, "score_watch_attempt_receipt_missing"
    if (attempt.get("iteration") != local_iteration
            or attempt.get("checkpoint_sha256") != checkpoint_sha256
            or attempt.get("state") not in ("complete", "HOLD")
            # A restarted score watcher may add explanatory mode/reason fields to done.
            # Match the evidence identity, not unrelated presentation fields.
            or any(done.get(key) != attempt.get(key) for key in
                   ("iteration", "checkpoint_sha256", "state", "score_path", "score_sha256"))):
        return False, "score_watch_attempt_not_terminal_or_receipts_differ"
    score_path = attempt.get("score_path")
    score_sha = attempt.get("score_sha256")
    if not score_path or not score_sha:
        return False, "score_watch_score_receipt_missing"
    score_file = Path(score_path)
    if not score_file.is_file() or _sha256(score_file) != score_sha:
        return False, "score_watch_score_receipt_unverified"
    return True, "score_watch_attempt_closed"


def wait_for_score_watch_attempt(score_watch_root: Path, local_iteration: int,
                                 checkpoint_sha256: str, *, state_path: Path,
                                 poll_seconds: float = 10.0,
                                 timeout_seconds: float = 6 * 60 * 60,
                                 sleep=time.sleep) -> dict[str, Any]:
    """Wait for the matching score-watch receipt before attempting P1."""
    started = time.monotonic()
    checks = 0
    while True:
        checks += 1
        closed, reason = score_watch_attempt_finished(
            score_watch_root, local_iteration, checkpoint_sha256)
        if closed:
            return {"state": "score_watch_closed", "reason": reason,
                    "checks": checks, "waited_s": time.monotonic() - started}
        _atomic_json(Path(state_path), {
            "state": "waiting_for_score_watch_evaluation",
            "local_iteration": local_iteration,
            "checkpoint_sha256": checkpoint_sha256,
            "reason": reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        if time.monotonic() - started > timeout_seconds:
            raise TimeoutError("score-watch did not close this checkpoint within six hours")
        sleep(poll_seconds)


def watch(run_dir: Path, score_dir: Path, out_dir: Path, *, first_local_update: int = 500,
         interval: int = 250, parent_iteration: int = 6000, poll_seconds: float = 10,
         marker: Path = DEFAULT_MARKER, python: Path = DEFAULT_PYTHON,
         worktree: Path | None = None, score_watch_dir: Path | None = None,
         task: str = TASK, seed: int = 42) -> int:
    os.environ.setdefault('EX41_ORCHESTRATION_TO',
                          'term_37f1d02b-35f8-435d-940e-d43a8a5be1de')
    if first_local_update < interval or first_local_update % interval or interval <= 0:
        raise ValueError("push250 starts at a positive interval-aligned local update")
    run_dir, score_dir, out_dir = Path(run_dir), Path(score_dir), Path(out_dir)
    worktree = Path(worktree or Path(__file__).resolve().parents[2])
    state_path = out_dir / "watcher_state.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    score_watch_root = Path(score_watch_dir) if score_watch_dir is not None else score_dir.parent / "score-watch"
    local_iteration = first_local_update
    while True:
        ready = wait_for_checkpoint_target(
            run_dir, score_dir, local_iteration, state_path=state_path,
            poll_seconds=poll_seconds, state_writer=_atomic_json)
        global_iteration = parent_iteration + local_iteration
        destination = output_path_for_global_iteration(out_dir, global_iteration)
        if destination.exists():
            matching_terminal_result(destination, local_iteration=local_iteration,
                                     global_iteration=global_iteration,
                                     checkpoint_sha256=ready["sha256"])
            local_iteration += interval
            _atomic_json(state_path, {"state": "already_completed_skipped",
                                      "completed_local_iteration": local_iteration - interval,
                                      "next_local_iteration": local_iteration,
                                      "existing_result": str(destination),
                                      "updated_at": datetime.now(timezone.utc).isoformat()})
            continue
        wait_for_score_watch_attempt(
            score_watch_root, local_iteration, ready["sha256"],
            state_path=state_path, poll_seconds=poll_seconds)
        if ready.get("measurement_state") == "HOLD":
            # A collection failure is visible but does not permanently stop
            # future D171 boundaries. No GPU marker or evaluator is started.
            receipt = {
                "schema": "foothold-ex41-push250-check/1", "state": "HOLD",
                "reason": "score_watch_measurement_failed; boundary recorded without D171 run",
                "global_iteration": global_iteration, "local_iteration": local_iteration,
                "checkpoint": str(ready["checkpoint"]), "checkpoint_sha256": ready["sha256"],
                "score_path": str(ready["score"]), "score_sha256": ready["score_sha256"],
                "measurement_state": "failed", "judgement_state": "not_judged",
                "advanced_to_local_iteration": local_iteration + interval,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_json(destination, receipt)
            local_iteration += interval
            _atomic_json(state_path, {"state": "measurement_hold_advanced",
                                      "local_iteration": local_iteration,
                                      "prior_result_path": str(destination),
                                      "updated_at": datetime.now(timezone.utc).isoformat()})
            continue
        admission = gpu1_busy_snapshot(marker)
        _atomic_json(state_path, {"state": "starting", "local_iteration": local_iteration,
                                  "global_iteration": global_iteration, "checkpoint_sha256": ready["sha256"],
                                  "score_path": str(ready["score"]), "gpu1_admission": admission,
                                  "updated_at": datetime.now(timezone.utc).isoformat()})
        try:
            result = evaluate_checkpoint(ready["checkpoint"], global_iteration=global_iteration,
                                         out_dir=out_dir, worktree=worktree, device="cuda:1",
                                          python=python, marker=marker, task=task, seed=seed,
                                          local_iteration=local_iteration)
        except Exception as exc:
            result = {"schema": "foothold-ex41-push250-check/1", "state": "HOLD",
                      "global_iteration": global_iteration, "local_iteration": local_iteration,
                      "checkpoint": str(ready["checkpoint"]), "checkpoint_sha256": ready["sha256"],
                      "error": f"{type(exc).__name__}: {exc}",
                      "updated_at": datetime.now(timezone.utc).isoformat()}
            _atomic_json(destination, result)
        result.setdefault("local_iteration", local_iteration)
        _atomic_json(state_path, {"state": result["state"], "local_iteration": local_iteration,
                                  "global_iteration": global_iteration,
                                  "result_path": str(destination), "elapsed_s": result["elapsed_s"],
                                  "updated_at": datetime.now(timezone.utc).isoformat()})
        if result["state"] != "done":
            return 6
        local_iteration += interval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exp", required=True, help="experiment definition ID in experiments/<ID>.yaml")
    parser.add_argument("--run-dir", type=Path, required=True, help="live training run folder with manifest.json")
    parser.add_argument("--score-dir", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--first-local-update", type=int)
    parser.add_argument("--interval", type=int)
    parser.add_argument("--parent-iteration", type=int)
    parser.add_argument("--poll-seconds", type=float, default=10)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--worktree", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--once-checkpoint", type=Path)
    parser.add_argument("--once-global-iteration", type=int)
    args = parser.parse_args(argv)
    try:
        definition = operational_definition(args.exp)
        paths = paths_for_run(definition, args.run_dir)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    training = definition["operational_values"]["training"]
    evaluation = definition["operational_values"]["evaluation"]
    args.score_dir = args.score_dir or paths["scores"]
    args.out_dir = args.out_dir or paths["push250"]
    args.first_local_update = (definition["operational_values"]["evaluation"]["checkpoint_first"]
                               if args.first_local_update is None else args.first_local_update)
    args.interval = training["interval_updates"] if args.interval is None else args.interval
    args.parent_iteration = args.parent_iteration if args.parent_iteration is not None else definition["operational_values"]["parent"]["update"]
    args.task = evaluation.get("task_id", TASK)
    args.seed = int(evaluation["seed"])
    if args.once_checkpoint:
        if args.once_global_iteration is None:
            parser.error("--once-global-iteration is required with --once-checkpoint")
        try:
            result = evaluate_checkpoint(args.once_checkpoint, global_iteration=args.once_global_iteration,
                                         out_dir=args.out_dir, worktree=args.worktree, python=args.python,
                                         task=args.task, seed=args.seed)
        except Exception as exc:
            result = {"schema": "foothold-ex41-push250-check/1", "state": "HOLD",
                      "global_iteration": args.once_global_iteration,
                      "error": f"{type(exc).__name__}: {exc}",
                      "updated_at": datetime.now(timezone.utc).isoformat()}
            _atomic_json(output_path_for_global_iteration(args.out_dir, args.once_global_iteration), result)
        print(json.dumps({"state": result["state"], "iteration": result["global_iteration"],
                          "elapsed_s": result["elapsed_s"], "path": str(output_path_for_global_iteration(args.out_dir, args.once_global_iteration))},
                         ensure_ascii=False, sort_keys=True), flush=True)
        return 0 if result["state"] == "done" else 5
    return watch(args.run_dir, args.score_dir, args.out_dir,
                 first_local_update=args.first_local_update, interval=args.interval,
                 parent_iteration=args.parent_iteration, poll_seconds=args.poll_seconds,
                 python=args.python, worktree=args.worktree, score_watch_dir=paths["score_watch"],
                 task=args.task, seed=args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
