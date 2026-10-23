"""Observe SOL-23f runs and consume one verified review clip at a time.

This process never starts training or kills a process. Capture is disabled unless
the operator explicitly passes --capture after checking spare GPU capacity.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any

import psutil


DEADLINE = "2026-10-24T22:30:00+09:00"
SOURCE_FILES = (
    "inbox/jay/20261023-experiments/monitor_23d.py",
    "foothold_s2/eval/seq_video.py",
    "foothold_s2/eval/record_sol23f.py",
)
INTERVALS = (100, 200, 500)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(200):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 199:
                    raise
                time.sleep(0.01)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


@contextmanager
def exclusive_owner(path: Path):
    """An OS lock, not a stale PID file, owns the entire scan/capture lifetime."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("consumer_already_running") from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("consumer_already_running") from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_config(config: dict[str, Any]) -> tuple[Path, float]:
    if config.get("schema") != "sol24a-consumer/1" or config.get("deadline") != DEADLINE:
        raise ValueError("consumer schema/deadline mismatch")
    deadline = datetime.fromisoformat(DEADLINE).timestamp()
    root = Path(config["fixed_root"]).resolve(strict=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if head != config.get("expected_head"):
        raise ValueError("fixed source HEAD differs from the registered hash")
    if not isinstance(config.get("runs"), list) or not config["runs"]:
        raise ValueError("at least one run binding is required")
    names = set()
    for run in config["runs"]:
        if run.get("name") not in ("B", "TD") or run["name"] in names:
            raise ValueError("run names must be unique B/TD")
        names.add(run["name"])
        if run.get("device") != {"B": "cuda:0", "TD": "cuda:1"}[run["name"]]:
            raise ValueError("capture GPU ordinal must match the registered run")
        if run.get("scene") not in ("flat", "rough"):
            raise ValueError("capture scene must be flat or rough")
        if not isinstance(run.get("policy"), dict) or run["policy"].get("experiment") != run["name"]:
            raise ValueError("capture policy experiment must match run")
        if not isinstance(run.get("process_file"), str) or not isinstance(run.get("run_dir"), str):
            raise ValueError("run and process file paths are required")
        if not isinstance(run.get("launch_config"), str) or not Path(run["launch_config"]).is_file():
            raise ValueError("original launch environment file is required")
        launch = read_json(Path(run["launch_config"]))
        if (Path(launch.get("cwd", "")).resolve() != root
                or not isinstance(launch.get("env"), dict)
                or not isinstance(launch.get("unset_env"), list)):
            raise ValueError("original launch environment contract is invalid")
        if (launch["env"].get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID"
                or "CUDA_VISIBLE_DEVICES" not in launch["unset_env"]
                or "CUDA_VISIBLE_DEVICES" in launch["env"]):
            raise ValueError("capture GPU ordinal binding differs from the root launch")
    for key in ("state", "status", "capture_root", "metrics_root"):
        target = Path(config[key]).resolve()
        if target.is_relative_to(root):
            raise ValueError(f"{key} must not write inside the frozen source")
    if not Path(config["python"]).is_file():
        raise ValueError("capture Python executable missing")
    if config.get("metrics_every") not in INTERVALS:
        raise ValueError("metrics_every must be 100, 200, or 500")
    if float(config.get("poll_s", 0)) < 1 or float(config.get("min_capture_window_s", 0)) < 0:
        raise ValueError("invalid poll/capture window")
    return root, deadline


def source_hashes(root: Path) -> dict[str, str]:
    return {name: sha256(root / name) for name in SOURCE_FILES}


def pid_identity(pid: int | None) -> dict[str, Any]:
    if type(pid) is not int or pid <= 0:
        return {"pid": pid, "alive": False, "create_time": None}
    try:
        process = psutil.Process(pid)
        return {"pid": pid, "alive": process.is_running() and process.status() != psutil.STATUS_ZOMBIE,
                "create_time": process.create_time()}
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"pid": pid, "alive": False, "create_time": None}


def process_record(run: dict[str, Any], prior: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(run["process_file"])
    if not path.is_file():
        return {"state": "process_file_missing", "path": str(path)}
    record = read_json(path)
    identity = pid_identity(record.get("child_pid"))
    if prior and prior.get("pid") == identity["pid"] and prior.get("create_time") is not None:
        identity["reused_or_replaced"] = identity["create_time"] != prior["create_time"]
    return {**identity, "state": record.get("state"), "returncode": record.get("returncode"),
            "heartbeat_at": record.get("heartbeat_at"), "path": str(path)}


def _row_at(path: Path, iteration: int) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    found = None
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # the writer may still be appending its last line
            if isinstance(row, dict) and row.get("it") == iteration:
                found = row
    return found


def _tb_at(run_dir: Path, iteration: int) -> dict[str, float]:
    if not any(run_dir.glob("events.out.tfevents.*")):
        return {}
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    try:
        events = EventAccumulator(str(run_dir), size_guidance={"scalars": 0})
        events.Reload()
        wanted = ("Loss/perception/l_tr", "Loss/perception/l_ie",
                  "Loss/adasmpl/gt_fraction", "Loss/adasmpl/p_smpl")
        tags = set(events.Tags().get("scalars", ()))
        return {name: next((float(row.value) for row in events.Scalars(name) if row.step == iteration), None)
                for name in wanted if name in tags}
    except (OSError, ValueError, KeyError):
        # A concurrently appended event file can be unreadable for one poll.
        return {}


def metric_snapshot(run_dir: Path, completed_updates: int) -> dict[str, Any]:
    """Use exact completed update and iteration, never a nearby or future row."""
    iteration = completed_updates - 1
    mapping = _row_at(run_dir / "map_stats.jsonl", iteration)
    evidence = _row_at(run_dir / "step_evidence.jsonl", iteration)
    tb = _tb_at(run_dir, iteration)
    missing = []
    if mapping is None:
        missing.append("map_stats_exact_iteration")
    if evidence is None:
        missing.append("foot_xy_and_termination_exact_iteration")
    if tb.get("Loss/perception/l_tr") is None:
        missing.append("tr_net_loss_exact_iteration")
    if tb.get("Loss/adasmpl/gt_fraction") is None:
        missing.append("gt_fraction_exact_iteration")
    # The current runner records camera geometry, not depth-pixel distribution.
    missing.append("depth_pixel_distribution_not_recorded")
    return {"completed_updates": completed_updates, "iteration": iteration,
            "map_stats": mapping, "step_evidence": evidence, "tensorboard": tb,
            "depth_distribution": None, "missing": missing,
            "sources": [str(run_dir / name) for name in
                        ("map_stats.jsonl", "step_evidence.jsonl", "events.out.tfevents.*")]}


def publish_metrics(config: dict[str, Any], run: dict[str, Any]) -> list[str]:
    run_dir = Path(run["run_dir"])
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    completed = int((read_json(manifest_path).get("progress") or {}).get("completed_updates", 0))
    interval = int(config["metrics_every"])
    root = Path(config["metrics_root"]) / run["name"]
    published = []
    for boundary in range(interval, completed + 1, interval):
        target = root / f"completed_{boundary}.json"
        if target.exists():
            old = read_json(target)
            transient = set(old.get("missing", ())) - {"depth_pixel_distribution_not_recorded"}
            if not transient:
                continue
        row = metric_snapshot(run_dir, boundary)
        row["run_dir"] = str(run_dir.resolve())
        atomic_json(target, row)
        published.append(str(target))
    return published


def _receipt_path(config: dict[str, Any], request: dict[str, Any]) -> Path:
    return Path(config["capture_root"]) / request["id"] / "review.done"


def _run_for_request(config: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    matches = [row for row in config["runs"] if Path(row["run_dir"]).resolve() == Path(request["run_dir"]).resolve()]
    if len(matches) != 1:
        raise ValueError("request run is not bound to exactly one capture profile")
    return matches[0]


def recover_claims(config: dict[str, Any], monitor: Any, previous: dict[str, Any]) -> bool:
    """Resume verified receipts; unknown child ownership blocks further capture."""
    state = monitor.load_state(Path(config["state"]))
    active = previous.get("active_capture") or {}
    live = pid_identity(active.get("pid"))
    active_live = (live["alive"] and live["create_time"] == active.get("create_time"))
    blocked = active_live
    for request in state["requests"].values():
        if request.get("state") != "claimed":
            continue
        receipt = _receipt_path(config, request)
        if receipt.is_file():
            try:
                monitor.transition(Path(config["state"]), request["id"], "completed",
                                   "verified receipt after restart", receipt,
                                   Path(config["fixed_root"]) / SOURCE_FILES[1])
            except (OSError, ValueError) as exc:
                monitor.transition(Path(config["state"]), request["id"], "failed",
                                   f"receipt invalid after restart: {type(exc).__name__}: {exc}")
        elif active_live and request["id"] == active.get("request_id"):
            continue
        elif active.get("request_id") == request["id"] and active.get("create_time") is not None:
            # This known child has exited without publishing a receipt.
            monitor.transition(Path(config["state"]), request["id"], "failed",
                               "known capture child exited without a verified receipt")
        else:
            # A crash between Popen and status publication can leave a live
            # untracked child. Do not fail the claim and start the next clip.
            blocked = True
    return blocked


def capture_command(config: dict[str, Any], run: dict[str, Any], request: dict[str, Any]) -> list[str]:
    return [config["python"], str(Path(config["fixed_root"]) / SOURCE_FILES[1]),
            str(_receipt_path(config, request).parent), "review",
            json.dumps(run["policy"], separators=(",", ":")), request["checkpoint"],
            run["label"], run["scene"], run["device"], "--python", config["python"],
            "--recorder", str(Path(config["fixed_root"]) / SOURCE_FILES[2]),
            "--max-attempts", str(int(config.get("max_attempts", 4)))]


def capture_environment(run: dict[str, Any]) -> dict[str, str]:
    """Reuse the root trainer's recorded Kit environment without exposing its values."""
    launch = read_json(Path(run["launch_config"]))
    env = os.environ.copy()
    for name in launch["unset_env"]:
        if not isinstance(name, str):
            raise ValueError("launch unset_env key must be a string")
        env.pop(name, None)
    for name, value in launch["env"].items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("launch environment keys and values must be strings")
        env[name] = value
    return env


def consume_one(config: dict[str, Any], monitor: Any, request: dict[str, Any],
                status: dict[str, Any], launch=None) -> dict[str, Any]:
    state = Path(config["state"])
    checkpoint = Path(request["checkpoint"])
    if not checkpoint.is_file() or sha256(checkpoint) != request["checkpoint_sha256"]:
        return monitor.transition(state, request["id"], "failed", "checkpoint changed before capture")
    run = _run_for_request(config, request)
    monitor.transition(state, request["id"], "claimed", "one-at-a-time capture started")
    command = capture_command(config, run, request)
    receipt = _receipt_path(config, request)
    receipt.parent.parent.mkdir(parents=True, exist_ok=True)
    log_path = receipt.parent.parent / (request["id"] + ".child.log")
    if launch is None:
        def launch(argv, log):
            env = capture_environment(run)
            with log.open("wb") as stream:
                child = subprocess.Popen(argv, cwd=config["fixed_root"], env=env,
                                         stdout=stream, stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                identity = pid_identity(child.pid)
                status["active_capture"] = {"request_id": request["id"], **identity}
                atomic_json(Path(config["status"]), status)
                return child.wait()
    try:
        rc = launch(command, log_path)
        if rc == 0 and receipt.is_file():
            result = monitor.transition(state, request["id"], "completed", "seq_video receipt verified",
                                        receipt, Path(config["fixed_root"]) / SOURCE_FILES[1])
        else:
            result = monitor.transition(state, request["id"], "failed", f"seq_video exit {rc}, receipt={receipt.is_file()}")
    except Exception as exc:
        result = monitor.transition(state, request["id"], "failed", f"capture or receipt error: {type(exc).__name__}: {exc}")
    finally:
        status["active_capture"] = None
        atomic_json(Path(config["status"]), status)
    return result


def cycle(config: dict[str, Any], monitor: Any, status: dict[str, Any], deadline: float,
          *, capture: bool, now: float | None = None, launch=None) -> dict[str, Any]:
    now = time.time() if now is None else now
    root = Path(config["fixed_root"])
    if source_hashes(root) != status["source_sha256"]:
        raise RuntimeError("frozen capture/monitor source changed")
    previous_runs = status.get("runs", {})
    status["runs"] = {run["name"]: process_record(run, previous_runs.get(run["name"]))
                      for run in config["runs"]}
    paths = [Path(run["run_dir"]) for run in config["runs"] if Path(run["run_dir"]).is_dir()]
    result = monitor.scan(paths, Path(config["state"]), publish=True, deadline=deadline, now=now)
    status["scan_errors"] = result["errors"]
    status["metrics_published"] = [path for run in config["runs"] for path in publish_metrics(config, run)]
    status["last_scan_epoch"] = now
    status["request_counts"] = {name: sum(row.get("state") == name for row in result["state"]["requests"].values())
                                for name in ("pending", "claimed", "completed", "failed")}
    status["state"] = "deadline" if now >= deadline else "observing"
    atomic_json(Path(config["status"]), status)
    if not capture or now + float(config["min_capture_window_s"]) >= deadline:
        return status
    requests = sorted((row for row in result["state"]["requests"].values() if row.get("state") == "pending"),
                      key=lambda row: (row["requested_epoch"], row["id"]))
    if requests:
        status["state"] = "capturing"
        atomic_json(Path(config["status"]), status)
        status["last_capture"] = consume_one(config, monitor, requests[0], status, launch=launch)
        status["state"] = "observing"
        atomic_json(Path(config["status"]), status)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--capture", action="store_true", help="explicitly allow one sequential GPU clip")
    parser.add_argument("--once", action="store_true", help="one scan cycle for CPU inspection")
    args = parser.parse_args(argv)
    config = read_json(args.config)
    root, deadline = validate_config(config)
    monitor = load_module(root / SOURCE_FILES[0], "sol24a_fixed_monitor")
    recorder = load_module(root / SOURCE_FILES[2], "sol24a_fixed_recorder")
    for run in config["runs"]:
        recorder.parse_spec(json.dumps(run["policy"]))
    status_path = Path(config["status"])
    with exclusive_owner(status_path.with_suffix(status_path.suffix + ".owner.lock")):
        prior = read_json(status_path) if status_path.is_file() else {}
        capture_blocked = recover_claims(config, monitor, prior)
        status = {"schema": "sol24a-consumer-status/1", "owner_pid": os.getpid(),
                  "owner_create_time": psutil.Process().create_time(),
                  "started_epoch": time.time(), "deadline": DEADLINE,
                  "fixed_head": config["expected_head"], "source_sha256": source_hashes(root),
                  "active_capture": prior.get("active_capture") if capture_blocked else None,
                  "capture_recovery_hold": capture_blocked,
                  "runs": prior.get("runs", {}), "state": "starting"}
        atomic_json(status_path, status)
        while True:
            now = time.time()
            if capture_blocked:
                capture_blocked = recover_claims(config, monitor, status)
                status["capture_recovery_hold"] = capture_blocked
                if not capture_blocked:
                    status["active_capture"] = None
            cycle(config, monitor, status, deadline, capture=args.capture and not capture_blocked, now=now)
            if args.once or now >= deadline:
                return 0
            time.sleep(float(config["poll_s"]))


if __name__ == "__main__":
    raise SystemExit(main())
