"""Watch only the recorder child spawned by the current C-layer attempt."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import time


PREFIX = b"C76_PROGRESS "


def progress_frames(data: bytes, previous: int) -> int:
    """Accept complete, strictly advancing progress lines only."""
    latest = previous
    for line in data.splitlines():
        if not line.startswith(PREFIX):
            continue
        try:
            row = json.loads(line[len(PREFIX):])
        except (UnicodeDecodeError, ValueError):
            continue
        frame = row.get("frame") if isinstance(row, dict) else None
        if type(frame) is int and frame > latest:
            latest = frame
    return latest


def run_recorder(argv: list[str], log_path: Path, env: dict[str, str], *,
                 no_progress_s: float = 600.0, poll_s: float = 2.0) -> int:
    """End our child as a technical failure if its frame counter stops advancing.

    The timer starts at process launch, so Kit startup without any frame is covered.
    No unrelated process is inspected or terminated. The caller records failure and
    must not publish a success receipt after this raises.
    """
    if (not math.isfinite(no_progress_s) or not math.isfinite(poll_s)
            or no_progress_s <= 0 or poll_s <= 0):
        raise ValueError("progress intervals must be positive")
    last_frame = 0
    last_progress = time.monotonic()
    read_offset = 0
    pending = b""
    with log_path.open("wb") as log:
        child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            while True:
                with log_path.open("rb") as stream:
                    stream.seek(read_offset)
                    fresh = stream.read()
                    read_offset = stream.tell()
                pending += fresh
                if b"\n" in pending:
                    complete, pending = pending.rsplit(b"\n", 1)
                    advanced = progress_frames(complete, last_frame)
                    if advanced > last_frame:
                        last_frame = advanced
                        last_progress = time.monotonic()
                code = child.poll()
                if code is not None:
                    return code
                if time.monotonic() - last_progress >= no_progress_s:
                    child.terminate()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=10)
                    raise ValueError(f"recorder_no_progress_timeout after {no_progress_s:g}s; last_frame={last_frame}")
                time.sleep(poll_s)
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
