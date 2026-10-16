"""Independent hard-deadline watchdog for the stage-0 supervisor (separate process).

Design (lead, 2026-10-15; for ASTRA 17x review):
* The watchdog is a different process from the supervisor and survives the launching terminal.
* It identifies the supervisor ONLY by (pid, create_time) recorded by the launcher right after
  the supervisor was started. A pid whose creation time differs is another process: the
  watchdog never signals it.
* Trigger (any): absolute hard deadline passed, supervisor heartbeat older than stale_after_s,
  status file never appeared within startup_grace_s.
* Action: kill ONLY the supervisor process. The supervisor holds the Job Object handle with
  KILL_ON_JOB_CLOSE, so the OS then ends the whole owned family. The watchdog never signals
  any child, never opens the job, and never touches processes it did not identify at start.
* Exit codes: 0 supervisor ended by itself or was ended by this watchdog; 2 kill failed;
  3 identity mismatch at start (nothing signalled); 4 bad arguments.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

import psutil


def log_event(path: Path, **event) -> None:
    event["epoch"] = time.time()
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def identity_ok(proc: psutil.Process, expected_create_time: float, tolerance: float = 0.05) -> bool:
    try:
        return abs(proc.create_time() - expected_create_time) <= tolerance
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def read_heartbeat(status_path: Path):
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    hb = data.get("heartbeat_epoch")
    return (float(hb) if isinstance(hb, (int, float)) and not isinstance(hb, bool) else None), data.get("state")


def watch(*, pid: int, create_time: float, status_path: Path, hard_deadline_epoch: float,
          stale_after_s: float, startup_grace_s: float, poll_s: float, log_path: Path,
          clock=time.time, sleep=time.sleep, grace_kill_s: float = 10.0) -> int:
    for label, value in (("stale_after_s", stale_after_s), ("startup_grace_s", startup_grace_s),
                         ("poll_s", poll_s), ("grace_kill_s", grace_kill_s)):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 < value < 1e6:
            log_event(log_path, event="bad_args", field=label)
            return 4
    if not isinstance(hard_deadline_epoch, (int, float)) or hard_deadline_epoch <= clock():
        log_event(log_path, event="bad_args", field="hard_deadline_epoch")
        return 4
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        log_event(log_path, event="supervisor_not_found_at_start", pid=pid)
        return 3
    if not identity_ok(proc, create_time):
        log_event(log_path, event="identity_mismatch_at_start", pid=pid, expected=create_time)
        return 3
    started = clock()
    log_event(log_path, event="watchdog_started", pid=pid, create_time=create_time,
              hard_deadline_epoch=hard_deadline_epoch, stale_after_s=stale_after_s)
    reason = None
    while reason is None:
        try:
            alive = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            alive = False
        if not alive:
            log_event(log_path, event="supervisor_ended_by_itself")
            return 0
        now = clock()
        hb, state = read_heartbeat(status_path)
        if now >= hard_deadline_epoch:
            reason = "hard_deadline"
        elif hb is None and now - started > startup_grace_s:
            reason = "no_status_after_startup_grace"
        elif hb is not None and now - hb > stale_after_s:
            reason = "heartbeat_stale"
        else:
            sleep(poll_s)
    log_event(log_path, event="trigger", reason=reason)
    if not identity_ok(proc, create_time):
        log_event(log_path, event="identity_mismatch_before_kill_no_signal")
        return 3
    try:
        proc.kill()
    except (psutil.NoSuchProcess,):
        log_event(log_path, event="supervisor_already_gone")
        return 0
    except psutil.AccessDenied:
        log_event(log_path, event="kill_access_denied")
        return 2
    try:
        proc.wait(timeout=grace_kill_s)
    except psutil.TimeoutExpired:
        log_event(log_path, event="supervisor_still_running_after_kill")
        return 2
    except psutil.NoSuchProcess:
        pass
    log_event(log_path, event="supervisor_killed", reason=reason)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--create-time", type=float, required=True)
    ap.add_argument("--status-path", type=Path, required=True)
    ap.add_argument("--hard-deadline-epoch", type=float, required=True)
    ap.add_argument("--stale-after-s", type=float, required=True)
    ap.add_argument("--startup-grace-s", type=float, required=True)
    ap.add_argument("--poll-s", type=float, required=True)
    ap.add_argument("--log", type=Path, required=True)
    a = ap.parse_args(argv)
    a.log.parent.mkdir(parents=True, exist_ok=True)
    return watch(pid=a.pid, create_time=a.create_time, status_path=a.status_path,
                 hard_deadline_epoch=a.hard_deadline_epoch, stale_after_s=a.stale_after_s,
                 startup_grace_s=a.startup_grace_s, poll_s=a.poll_s, log_path=a.log)


if __name__ == "__main__":
    sys.exit(main())
