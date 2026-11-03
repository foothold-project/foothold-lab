"""Publish the EX-41 GPU1 priority marker while an evaluation bundle runs."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

DEFAULT_MARKER = Path("D:/mai-tmp/gpu/PRIORITY_BUSY_GPU1")
DEFAULT_GPU0_MARKERS = (
    Path("C:/Users/AI-WS01/s2_lab/c_layer_m6000/priority/TRAINING_BUSY"),
    Path("D:/mai-tmp/gpu/TRAINING_BUSY_GPU0"),
)
DEFAULT_GPU1_TRAINING_MARKER = Path("D:/mai-tmp/gpu/TRAINING_BUSY_GPU1")
DEFAULT_GPU0_EVAL_MARKER = Path("D:/mai-tmp/gpu/PRIORITY_BUSY_GPU0")
GPU0_UUID = "c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"


def wait_for_gpu0_python_idle(*, timeout_seconds: float = 1800, poll_seconds: float = 5) -> dict:
    """Wait read-only for GPU0 Python/Kit work and active C-layer units to yield."""
    import psutil

    start = time.monotonic()
    checks = 0
    last_busy = []
    while time.monotonic() - start <= timeout_seconds:
        checks += 1
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name", "--format=csv,noheader"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"GPU0 admission query failed rc={result.returncode}")
        busy = []
        for raw in result.stdout.splitlines():
            fields = [field.strip() for field in raw.split(",", 2)]
            if len(fields) != 3 or fields[0].casefold().removeprefix("gpu-") != GPU0_UUID:
                continue
            try:
                pid = int(fields[1])
            except ValueError:
                busy.append({"pid": None, "process_name": fields[2], "state": "unknown_pid"})
                continue
            if pid == os.getpid():
                continue
            try:
                process = psutil.Process(pid)
                name = process.name()
                command = " ".join(process.cmdline())
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError) as exc:
                busy.append({"pid": pid, "process_name": fields[2],
                             "state": f"unknown:{type(exc).__name__}"})
                continue
            if "python" in name.casefold() or "kit" in name.casefold() or "isaac" in command.casefold():
                busy.append({"pid": pid, "process_name": name, "command": command[:500], "state": "busy"})
        known_pids = {row.get("pid") for row in busy}
        # Some Isaac child processes are briefly absent from nvidia-smi while
        # initializing or between Kit stages; their scheduler unit still owns GPU0.
        for process in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                info = process.info
                pid = int(info["pid"])
                command = " ".join(info.get("cmdline") or [])
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError, TypeError, ValueError):
                continue
            low = command.casefold()
            if pid == os.getpid() or pid in known_pids:
                continue
            if ("c_layer_shard.py" in low and "--gpu 0" in low) or (
                    "record_c_layer.py" in low and "--device cuda:0" in low):
                busy.append({"pid": pid, "process_name": info.get("name"),
                             "command": command[:500], "state": "c_layer_unit_active"})
        last_busy = busy
        if not busy:
            return {"state": "idle", "gpu_uuid": GPU0_UUID, "checks": checks,
                    "waited_seconds": time.monotonic() - start,
                    "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "last_busy": last_busy}
        time.sleep(poll_seconds)
    raise TimeoutError(json.dumps({"state": "HOLD", "gpu_uuid": GPU0_UUID,
                                   "checks": checks, "last_busy": last_busy}, ensure_ascii=False))


def publish_gpu0_busy_markers(*, job: str, iteration: int, run: str | None = None) -> list[dict]:
    """Claim the production/C-layer and D-drive shard GPU0 busy markers."""
    owners: list[dict] = []
    try:
        for marker in DEFAULT_GPU0_MARKERS:
            owners.append({"path": str(marker),
                           "owner": publish_marker(marker, job=job, iteration=iteration, run=run)})
    except Exception:
        clear_gpu0_busy_markers(owners)
        raise
    return owners


def clear_gpu0_busy_markers(owners: list[dict] | None) -> list[dict]:
    outcomes = []
    for item in reversed(owners or []):
        marker = Path(item["path"])
        cleared = clear_marker(marker, item["owner"])
        outcomes.append({"path": str(marker), "state": "cleared" if cleared else "HOLD"})
    return list(reversed(outcomes))


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


def gpu0_training_marker_state(markers=None) -> dict:
    """Report whether a GPU0 marker has a live owner; unreadable markers block conservatively."""
    rows = []
    for raw_path in DEFAULT_GPU0_MARKERS if markers is None else markers:
        path = Path(raw_path)
        if not path.exists():
            rows.append({"path": str(path), "state": "absent"})
            continue
        try:
            owner = _read_owner(path)
            if owner is None:
                rows.append({"path": str(path), "state": "absent"})
                continue
            live = _pid_is_live(owner)
            rows.append({"path": str(path), "state": "live" if live else "stale",
                         "pid": owner["pid"], "process_created_at": owner["process_created_at"],
                         "job": owner.get("job")})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            rows.append({"path": str(path), "state": "unknown_blocks",
                         "reason": f"{type(exc).__name__}: {exc}"})
    active = any(row["state"] in ("live", "unknown_blocks") for row in rows)
    return {"active": active, "markers": rows}


def publish_marker(path: str | Path = DEFAULT_MARKER, *, job: str,
                   iteration: int, pid: int | None = None,
                   process_created_at: float | None = None,
                   started_at: str | None = None, run: str | None = None) -> dict:
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
    if run is not None:
        row["run"] = str(run)
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


@contextmanager
def gpu0_priority(*, job: str, iteration: int, run: str | None = None):
    """Publish a P1 GPU0 receipt plus both C-layer yield markers."""
    owners = []
    try:
        eval_owner = publish_marker(DEFAULT_GPU0_EVAL_MARKER, job=job,
                                    iteration=iteration, run=run)
        owners.append({"path": str(DEFAULT_GPU0_EVAL_MARKER), "owner": eval_owner})
        owners.extend(publish_gpu0_busy_markers(job=job, iteration=iteration, run=run))
        yield owners
    finally:
        clear_gpu0_busy_markers(owners)
