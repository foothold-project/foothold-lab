"""Publish the EX-41 GPU1 priority marker while an evaluation bundle runs."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

DEFAULT_MARKER = Path("D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1")


def _process_created_at(pid: int) -> float:
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("psutil is required to identify the marker owner process") from exc
    return float(psutil.Process(pid).create_time())


def _read_owner(path: Path) -> dict | None:
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(row, dict):
        raise ValueError("GPU1 priority marker must contain a JSON object")
    pid = row.get("pid")
    created = row.get("process_created_at")
    if type(pid) is not int or pid <= 0 or type(created) not in (int, float):
        raise ValueError("GPU1 priority marker owner identity is invalid")
    return row


def _pid_is_live(row: dict) -> bool:
    try:
        actual = _process_created_at(row["pid"])
    except Exception as exc:
        # NoSuchProcess proves stale. Access errors and missing psutil do not.
        try:
            import psutil
        except ImportError:
            raise RuntimeError("cannot establish existing GPU1 marker liveness") from exc
        if isinstance(exc, psutil.NoSuchProcess):
            return False
        if isinstance(exc, psutil.ZombieProcess):
            return False
        raise RuntimeError("cannot establish existing GPU1 marker liveness") from exc
    return abs(actual - float(row["process_created_at"])) <= 0.1


def publish_marker(path: str | Path = DEFAULT_MARKER, *, job: str,
                   iteration: int, pid: int | None = None,
                   process_created_at: float | None = None,
                   started_at: str | None = None) -> dict:
    """Atomically claim the marker, refusing a live or unreadable owner."""
    if not isinstance(job, str) or not job.strip():
        raise ValueError("GPU1 marker job is required")
    if type(iteration) is not int or iteration < 0:
        raise ValueError("GPU1 marker iteration must be a nonnegative integer")
    marker = Path(path)
    owner_pid = os.getpid() if pid is None else pid
    if type(owner_pid) is not int or owner_pid <= 0:
        raise ValueError("GPU1 marker PID must be positive")
    created = _process_created_at(owner_pid) if process_created_at is None else float(process_created_at)
    if marker.exists():
        previous = _read_owner(marker)
        if previous is not None and _pid_is_live(previous):
            raise RuntimeError(f"GPU1 priority marker already owned by PID {previous['pid']}")
    row = {
        "job": job,
        "pid": owner_pid,
        "process_created_at": created,
        "started_at": started_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "iteration": iteration,
    }
    marker.parent.mkdir(parents=True, exist_ok=True)
    temp = marker.with_name(marker.name + ".pending." + uuid.uuid4().hex)
    data = (json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, marker)
    finally:
        temp.unlink(missing_ok=True)
    return row


def clear_marker(path: str | Path, owner: dict) -> bool:
    """Clear only the marker still owned by this exact PID creation time."""
    marker = Path(path)
    try:
        current = _read_owner(marker)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    if current is None:
        return True
    if current != owner:
        return False
    try:
        marker.unlink()
        return True
    except OSError:
        return False


@contextmanager
def gpu1_priority(path: str | Path = DEFAULT_MARKER, *, job: str, iteration: int):
    owner = publish_marker(path, job=job, iteration=iteration)
    try:
        yield owner
    finally:
        clear_marker(path, owner)
