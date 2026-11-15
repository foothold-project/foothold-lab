"""Fail-safe EX-42 status publication with explicit unknown/retry receipts."""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8)


def write_status(path: str | Path, payload: dict[str, Any], *,
                 replace: Callable[[str, str], None] = os.replace,
                 sleep: Callable[[float], None] = time.sleep,
                 retry_delays: tuple[float, ...] = RETRY_DELAYS) -> dict[str, Any]:
    """Atomically publish; a held reader yields unknown/retry, never a caller exception."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"state": "unknown", "attempts": 0, "retry": True,
                "warning": f"{type(exc).__name__}: {exc}", "path": str(target)}
    attempts = 0
    last_error = None
    for delay in (*retry_delays, None):
        attempts += 1
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                             prefix=f".{target.name}.{os.getpid()}.",
                                             suffix=".tmp", delete=False) as stream:
                temp_name = stream.name
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            replace(temp_name, str(target))
            return {"state": "written", "attempts": attempts, "path": str(target)}
        except PermissionError as exc:
            last_error = f"PermissionError: {exc}"
            if delay is None:
                break
            sleep(delay)
        except OSError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if delay is None:
                break
            sleep(delay)
        finally:
            if temp_name and os.path.exists(temp_name):
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
    return {"state": "unknown", "attempts": attempts, "retry": True,
            "warning": last_error, "path": str(target)}


def read_status(path: str | Path) -> dict[str, Any]:
    """Read and close promptly. Missing/invalid status stays unknown."""
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            value = json.load(stream)
        if not isinstance(value, dict):
            raise ValueError("status must be a JSON object")
        return {"state": "read", "value": value}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"state": "unknown", "warning": f"{type(exc).__name__}: {exc}"}
