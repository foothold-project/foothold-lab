"""CPU-only review requests from foothold_s2 runner manifests and status files."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

MILESTONES = (500, 1000, 1500)
POST_START_INTERVAL = 1000
POST_TIME_SECONDS = 3 * 60 * 60
UNFINISHED = {"pending", "claimed", "failed"}
STATES = {"pending", "claimed", "completed", "failed"}
_LOCAL_LOCKS: dict[str, threading.RLock] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()


@contextmanager
def state_lock(state_path: Path):
    """Serialize read-modify-write across threads and processes on this host."""
    lock_key = str(state_path.resolve())
    with _LOCAL_LOCKS_GUARD:
        local_lock = _LOCAL_LOCKS.setdefault(lock_key, threading.RLock())
    with local_lock:
        lock_path = Path(lock_key + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as stream:
            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                until = time.monotonic() + 60
                while True:
                    try:
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if time.monotonic() >= until:
                            raise TimeoutError(f"timed out locking {lock_path}")
                        time.sleep(0.025)
                try:
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 2, "requests": {}, "runs": {}}
    state = read_json(path)
    if state.get("version") != 2 or not isinstance(state.get("requests"), dict):
        raise ValueError("unsupported or malformed monitor state")
    state.setdefault("runs", {})
    return state


def parse_deadline(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("deadline must include an ISO8601 timezone")
    return parsed.timestamp()


def run_started_epoch(manifest: dict[str, Any], fallback: float) -> float:
    started = (manifest.get("run") or {}).get("started_at")
    if isinstance(started, str):
        try:
            parsed = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.astimezone()
            return parsed.timestamp()
        except ValueError:
            pass
    return fallback


def _checkpoint_iteration(name: str) -> int | None:
    match = re.search(r"(\d+)\.pt$", name)
    return int(match.group(1)) if match else None


def inspect_run(run: Path, state: dict[str, Any], deadline: float,
                now: float) -> list[dict[str, Any]]:
    manifest = read_json(run / "manifest.json")
    status = read_json(run / "train_start_status.json")
    if manifest.get("schema") != "foothold-manifest/1":
        raise ValueError(f"unsupported runner manifest: {run}")
    progress = manifest.get("progress") or {}
    checkpoints = manifest.get("checkpoints") or {}
    completed = int(progress.get("completed_updates", -1))
    status_iteration = int(status.get("iter", -1))
    latest_update = max(completed, status_iteration)
    run_data = manifest.get("run") or {}
    cli = run_data.get("cli_args") or {}
    model = str(cli.get("run_name") or run_data.get("name") or run.name)
    run_key = str(run.resolve())
    run_state = state.setdefault("runs", {}).setdefault(run_key, {
        "last_requested_iteration": 1500,
        "last_requested_epoch": run_started_epoch(manifest, now),
    })
    anchor_iteration = int(run_state.get("last_requested_iteration", 1500))
    anchor_time = float(run_state.get("last_requested_epoch", now))
    created = []
    items = []
    for name, expected_sha in checkpoints.items():
        iteration = _checkpoint_iteration(str(name))
        if iteration is None or not isinstance(expected_sha, str):
            continue
        items.append((iteration, str(name), expected_sha))

    valid = []
    # Numeric order matters: lexicographic order reorders 1000/1500 before 500.
    for iteration, name, expected_sha in sorted(items):
        checkpoint = run / name
        if iteration > completed or iteration > latest_update or not checkpoint.is_file():
            continue
        actual_sha = sha256(checkpoint)
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha) or actual_sha != expected_sha:
            continue
        request_id = hashlib.sha256(
            f"{run_key}\0{model}\0{iteration}\0{actual_sha}".encode("utf-8")
        ).hexdigest()
        valid.append((iteration, name, actual_sha, checkpoint, request_id))

    def enqueue(candidate: tuple[int, str, str, Path, str]) -> bool:
        nonlocal anchor_iteration, anchor_time
        iteration, _name, actual_sha, checkpoint, request_id = candidate
        if now >= deadline or request_id in state["requests"]:
            return False
        request = {
            "id": request_id,
            "run_dir": str(run.resolve()),
            "model": model,
            "iteration": iteration,
            "checkpoint": str(checkpoint.resolve()),
            "checkpoint_sha256": actual_sha,
            "run_state": str(status.get("state", "unknown")),
            "status_iteration": status_iteration,
            "manifest_completed_updates": completed,
            "status_time": status.get("time"),
            "requested_epoch": now,
            "state": "pending",
            "completion_evidence": None,
        }
        state["requests"][request_id] = request
        anchor_iteration = max(anchor_iteration, iteration)
        anchor_time = now
        created.append(request)
        return True

    # Keep the three initial review points even when scans resume much later.
    for candidate in valid:
        if candidate[0] in MILESTONES:
            enqueue(candidate)

    # Preserve each 1000-update cadence point if several were missed between scans.
    threshold = max(1500, anchor_iteration) + POST_START_INTERVAL
    while valid and valid[-1][0] >= threshold and now < deadline:
        candidate = next((item for item in valid if item[0] >= threshold), None)
        if candidate is None:
            break
        enqueue(candidate)
        threshold = max(threshold + POST_START_INTERVAL,
                        anchor_iteration + POST_START_INTERVAL)

    # A time-triggered review uses one newest completed, SHA-matching checkpoint.
    # Never consume the 3-hour signal on an older checkpoint when a newer one exists.
    if (now - anchor_time >= POST_TIME_SECONDS and valid
            and max(item[0] for item in valid) > 1500 and now < deadline):
        latest = max(valid, key=lambda item: item[0])
        enqueue(latest)
    run_state["last_requested_iteration"] = anchor_iteration
    run_state["last_requested_epoch"] = anchor_time
    return created


def _scan_locked(run_dirs: list[Path], state_path: Path, *, publish: bool,
                 deadline: float, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    state = load_state(state_path)
    created: list[dict[str, Any]] = []
    errors = []
    for run in run_dirs:
        try:
            created.extend(inspect_run(run, state, deadline, now))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"run_dir": str(run), "error": str(exc)})
    # This is the sole queue and status source of truth. No parallel request files.
    if publish:
        atomic_json(state_path, state)
    return {"dry_run": not publish, "created": created,
            "errors": errors,
            "unresolved": [r for r in state["requests"].values()
                           if r.get("state") in UNFINISHED],
            "state": state}


def scan(run_dirs: list[Path], state_path: Path, *, publish: bool,
         deadline: float, now: float | None = None) -> dict[str, Any]:
    with state_lock(state_path):
        return _scan_locked(run_dirs, state_path, publish=publish,
                            deadline=deadline, now=now)


def _verify_capture_receipt(request: dict[str, Any], receipt_path: Path,
                            seq_video: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(seq_video), "--verify-receipt", str(receipt_path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise ValueError("seq_video --verify-receipt rejected the receipt")
    receipt = read_json(receipt_path)
    if receipt.get("checkpoint_sha256") != request["checkpoint_sha256"]:
        raise ValueError("capture receipt checkpoint SHA does not match review request")
    files = receipt.get("files")
    if not isinstance(files, dict) or len(files) != 3:
        raise ValueError("capture receipt must contain MP4, JSON, and feet NPZ hashes")
    return {
        "receipt": str(receipt_path.resolve()),
        "receipt_sha256": sha256(receipt_path),
        "verifier": str(seq_video.resolve()),
        "verifier_sha256": sha256(seq_video),
        "verifier_returncode": result.returncode,
        "verified_output": result.stdout.strip(),
        "file_sha256": files,
    }


def _transition_locked(state_path: Path, request_id: str, new_state: str,
                        note: str | None = None, receipt_path: Path | None = None,
                        seq_video: Path | None = None) -> dict[str, Any]:
    if new_state not in STATES:
        raise ValueError(f"invalid state: {new_state}")
    state = load_state(state_path)
    request = state["requests"].get(request_id)
    if request is None:
        raise KeyError(f"unknown request: {request_id}")
    old = request["state"]
    allowed = {"pending": {"claimed", "failed"}, "claimed": {"completed", "failed"},
               "failed": {"pending"}, "completed": set()}
    if new_state not in allowed[old]:
        raise ValueError(f"invalid transition {old} -> {new_state}")
    evidence = None
    if new_state == "completed":
        if receipt_path is None or seq_video is None:
            raise ValueError("completed requires a receipt and seq_video verifier")
        evidence = _verify_capture_receipt(request, receipt_path, seq_video)
    request["state"] = new_state
    request["completion_evidence"] = evidence
    request.setdefault("history", []).append({"from": old, "to": new_state,
                                                "epoch": time.time(), "note": note})
    atomic_json(state_path, state)
    return request


def transition(state_path: Path, request_id: str, new_state: str,
               note: str | None = None, receipt_path: Path | None = None,
               seq_video: Path | None = None) -> dict[str, Any]:
    with state_lock(state_path):
        return _transition_locked(state_path, request_id, new_state, note,
                                  receipt_path, seq_video)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan_parser = sub.add_parser("scan", help="read existing runner folders only")
    scan_parser.add_argument("--run", action="append", type=Path, required=True)
    scan_parser.add_argument("--state", type=Path, required=True,
                             help="single atomic request queue and status file")
    scan_parser.add_argument("--deadline", required=True,
                             help="absolute ISO8601 deadline with timezone")
    scan_parser.add_argument("--publish", action="store_true", help="default is dry-run")
    update_parser = sub.add_parser("transition", help="record state in the canonical queue")
    update_parser.add_argument("--state", type=Path, required=True)
    update_parser.add_argument("--id", required=True)
    update_parser.add_argument("--to", choices=sorted(STATES), required=True)
    update_parser.add_argument("--note")
    update_parser.add_argument("--receipt", type=Path)
    update_parser.add_argument("--seq-video", type=Path,
                               help="seq_video.py used for --verify-receipt")
    args = parser.parse_args()
    if args.command == "scan":
        result = scan(args.run, args.state, publish=args.publish,
                      deadline=parse_deadline(args.deadline))
    else:
        result = transition(args.state, args.id, args.to, args.note,
                            args.receipt, args.seq_video)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
