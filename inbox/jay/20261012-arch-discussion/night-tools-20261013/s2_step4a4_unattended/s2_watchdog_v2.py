"""Independent hard-deadline watchdog v2 for the unattended gate (separate process).

Written by lead 2026-10-15 for ASTRA review against the VERIFY-astra-17x section 3 list:
  1 READY handshake: ready.json is written only after args, identity and the watch dir are
    proven; the gate does no GPU work before it sees a matching READY.
  2 identity: the watched process is (pid, create_time) from the launcher; heartbeat must carry
    the same chain_id; every poll rewrites watchdog_hb.json so the gate can check this watcher.
  3 deadlines: absolute wall clock AND a monotonic budget measured from watcher start.
  4 heartbeat input: NaN / Inf / non-number / future-dated / wrong chain are rejected and never
    count as progress. Staleness is "no new valid heartbeat value for stale_after_s monotonic".
  5 logging never blocks the kill (every write is best effort).
  6 AccessDenied is "blind", never "ended by itself". Blind too long exits 6 and says so.
  7 a kill leaves kill_receipt.json (reason, descendants seen before the kill, survivors) and
    exits 2 if any identified family member survives.
Exit codes: 0 watched process ended by itself or was ended here with an empty family;
2 kill failed or family survivors; 3 identity mismatch at start; 4 bad arguments;
6 blind (cannot read the watched process) ; 7 cannot publish READY.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import psutil

EXIT_OK, EXIT_KILL_FAILED, EXIT_IDENTITY, EXIT_BAD_ARGS, EXIT_BLIND, EXIT_NO_READY = 0, 2, 3, 4, 6, 7
FUTURE_SLACK_S = 5.0


def finite_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def safe_log(path, **event) -> bool:
    """Append one JSON line. Never raises: a broken log must not stop a kill."""
    try:
        event["epoch"] = time.time()
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return True
    except Exception:
        return False


def atomic_write(path, value) -> bool:
    """Best-effort atomic JSON write. Returns False instead of raising."""
    try:
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(value, sort_keys=True, allow_nan=False), encoding="utf-8")
        for attempt in range(50):
            try:
                os.replace(tmp, target)
                return True
            except PermissionError:
                time.sleep(0.01)
        return False
    except Exception:
        return False


def file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity_state(proc, expected_create_time: float, tolerance: float = 0.05) -> str:
    """match | mismatch | gone | denied. 'denied' is blindness, not death."""
    try:
        if abs(proc.create_time() - expected_create_time) <= tolerance:
            return "match"
        return "mismatch"
    except psutil.NoSuchProcess:
        return "gone"
    except psutil.AccessDenied:
        return "denied"


def read_status(path, chain_id, now):
    """(heartbeat_or_None, state, why_invalid). Only a finite, non-future heartbeat of this chain counts."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None, "unreadable"
    if not isinstance(data, dict):
        return None, None, "not_object"
    state = data.get("state")
    if data.get("chain_id") != chain_id:
        return None, state, "chain_mismatch"
    hb = data.get("heartbeat_epoch")
    if not finite_number(hb):
        return None, state, "hb_not_finite_number"
    if hb > now + FUTURE_SLACK_S:
        return None, state, "hb_future"
    return float(hb), state, None


def descendants_snapshot(proc):
    """[(pid, create_time)] of every descendant seen right now, or None when it cannot be read."""
    try:
        children = proc.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None
    rows = []
    for child in children:
        try:
            rows.append((child.pid, child.create_time()))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            rows.append((child.pid, None))
    return rows


def survivors(rows, process_factory):
    alive = []
    for pid, ct in rows or []:
        try:
            p = process_factory(pid)
            if ct is None or identity_state(p, ct) == "match":
                alive.append((pid, ct))
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            alive.append((pid, ct))
    return alive


def check_args(*, stale_after_s, startup_grace_s, poll_s, kill_grace_s, mono_budget_s,
               blind_limit_s, hard_deadline_epoch, clock):
    for label, value in (("stale_after_s", stale_after_s), ("startup_grace_s", startup_grace_s),
                         ("poll_s", poll_s), ("kill_grace_s", kill_grace_s),
                         ("mono_budget_s", mono_budget_s), ("blind_limit_s", blind_limit_s)):
        if not finite_number(value) or not 0 < value < 1e6:
            return label
    if not finite_number(hard_deadline_epoch) or hard_deadline_epoch <= clock():
        return "hard_deadline_epoch"
    return None


def watch(*, pid: int, create_time: float, chain_id: str, status_path: Path, watch_dir: Path,
          hard_deadline_epoch: float, mono_budget_s: float, stale_after_s: float,
          startup_grace_s: float, poll_s: float, log_path: Path, own_sha256: str = "",
          kill_grace_s: float = 10.0, blind_limit_s: float = 20.0, family_wait_s: float = 5.0,
          clock=time.time, mono=time.monotonic, sleep=time.sleep,
          process_factory=psutil.Process) -> int:
    watch_dir = Path(watch_dir)
    hb_path, ready_path, receipt_path = (watch_dir / "watchdog_hb.json", watch_dir / "ready.json",
                                         watch_dir / "kill_receipt.json")
    bad = check_args(stale_after_s=stale_after_s, startup_grace_s=startup_grace_s, poll_s=poll_s,
                     kill_grace_s=kill_grace_s, mono_budget_s=mono_budget_s,
                     blind_limit_s=blind_limit_s, hard_deadline_epoch=hard_deadline_epoch, clock=clock)
    me = {"chain_id": chain_id, "watchdog_pid": os.getpid(), "gate_pid": pid, "gate_create_time": create_time}
    try:
        me["watchdog_create_time"] = psutil.Process().create_time()
    except Exception:
        me["watchdog_create_time"] = None
    seq = 0

    def beat(state, **extra):
        nonlocal seq
        seq += 1
        atomic_write(hb_path, {**me, **extra, "state": state, "seq": seq, "epoch": clock()})

    if bad:
        safe_log(log_path, event="bad_args", field=bad)
        beat("BAD_ARGS", field=bad)
        return EXIT_BAD_ARGS
    try:
        proc = process_factory(pid)
    except psutil.NoSuchProcess:
        safe_log(log_path, event="watched_not_found_at_start", pid=pid)
        return EXIT_IDENTITY
    except psutil.AccessDenied:
        safe_log(log_path, event="watched_blind_at_start", pid=pid)
        beat("BLIND", why="access_denied_at_start")
        return EXIT_BLIND
    start_state = identity_state(proc, create_time)
    if start_state == "denied":
        safe_log(log_path, event="watched_blind_at_start", pid=pid)
        beat("BLIND", why="access_denied_at_start")
        return EXIT_BLIND
    if start_state != "match":
        safe_log(log_path, event="identity_mismatch_at_start", pid=pid, expected=create_time, state=start_state)
        return EXIT_IDENTITY
    t0_wall, t0_mono = clock(), mono()
    deadline_mono = t0_mono + min(mono_budget_s, hard_deadline_epoch - t0_wall)
    seq += 1
    ready = {**me, "state": "READY", "seq": seq, "epoch": clock(), "watchdog_sha256": own_sha256,
             "hard_deadline_epoch": hard_deadline_epoch, "mono_budget_s": mono_budget_s,
             "stale_after_s": stale_after_s, "startup_grace_s": startup_grace_s}
    if not atomic_write(ready_path, ready):
        safe_log(log_path, event="cannot_publish_ready")
        return EXIT_NO_READY
    safe_log(log_path, event="watchdog_started", pid=pid, create_time=create_time, chain_id=chain_id,
             hard_deadline_epoch=hard_deadline_epoch, mono_budget_s=mono_budget_s, stale_after_s=stale_after_s)
    last_hb, last_progress_mono, ever_valid = None, t0_mono, False
    blind_since = None
    reason = None
    while reason is None:
        now, m = clock(), mono()
        state = identity_state(proc, create_time)
        if state == "gone":
            safe_log(log_path, event="watched_ended_by_itself")
            beat("ENDED")
            return EXIT_OK
        if state == "mismatch":
            safe_log(log_path, event="watched_identity_changed_no_signal")
            beat("ENDED", why="identity_changed")
            return EXIT_OK
        if state == "denied":
            blind_since = m if blind_since is None else blind_since
            beat("BLIND", why="access_denied", blind_s=m - blind_since)
            if m - blind_since > blind_limit_s:
                safe_log(log_path, event="blind_too_long")
                return EXIT_BLIND
        else:
            blind_since = None
            try:
                running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                running = False
            except psutil.AccessDenied:
                running = True
            if not running:
                safe_log(log_path, event="watched_ended_by_itself")
                beat("ENDED")
                return EXIT_OK
        hb, _hb_state, why = read_status(status_path, chain_id, now)
        if hb is not None and hb != last_hb:
            last_hb, last_progress_mono, ever_valid = hb, m, True
        if now >= hard_deadline_epoch:
            reason = "hard_deadline"
        elif m >= deadline_mono:
            reason = "mono_deadline"
        elif not ever_valid and m - t0_mono > startup_grace_s:
            reason = "no_valid_status_after_startup_grace"
        elif ever_valid and m - last_progress_mono > stale_after_s:
            reason = "heartbeat_stale"
        else:
            if state != "denied":
                beat("WATCHING", hb_valid=hb is not None, hb_invalid_reason=why)
            sleep(poll_s)
    safe_log(log_path, event="trigger", reason=reason)
    beat("TRIGGERED", reason=reason)
    family = descendants_snapshot(proc)
    receipt = {"chain_id": chain_id, "reason": reason, "gate_pid": pid, "gate_create_time": create_time,
               "trigger_epoch": clock(), "descendants_before_kill": family, "gate_killed": False}
    if identity_state(proc, create_time) == "mismatch":
        safe_log(log_path, event="identity_mismatch_before_kill_no_signal")
        receipt["note"] = "identity_mismatch_before_kill_no_signal"
        atomic_write(receipt_path, receipt)
        return EXIT_IDENTITY
    try:
        proc.kill()
    except psutil.NoSuchProcess:
        safe_log(log_path, event="watched_already_gone")
    except psutil.AccessDenied:
        safe_log(log_path, event="kill_access_denied")
        beat("KILL_DENIED", reason=reason)
        receipt["note"] = "kill_access_denied"
        atomic_write(receipt_path, receipt)
        return EXIT_KILL_FAILED
    try:
        proc.wait(timeout=kill_grace_s)
    except psutil.TimeoutExpired:
        safe_log(log_path, event="watched_still_running_after_kill")
        receipt["note"] = "watched_still_running_after_kill"
        atomic_write(receipt_path, receipt)
        return EXIT_KILL_FAILED
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    receipt["gate_killed"] = True
    end = mono() + family_wait_s
    left = survivors(family, process_factory)
    while left and mono() < end:
        sleep(0.1)
        left = survivors(family, process_factory)
    forced = []
    for cpid, cct in left:
        try:
            cp = process_factory(cpid)
            if cct is None or identity_state(cp, cct) == "match":
                cp.kill()
                forced.append(cpid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    remaining = left
    if forced:
        end2 = mono() + family_wait_s
        remaining = survivors(left, process_factory)
        while remaining and mono() < end2:
            sleep(0.1)
            remaining = survivors(left, process_factory)
    receipt.update(descendants_left_after_wait=left, descendants_force_killed=forced,
                   descendants_remaining=remaining, receipt_epoch=clock(),
                   family_empty=not remaining and family is not None)
    atomic_write(receipt_path, receipt)
    safe_log(log_path, event="gate_killed", reason=reason, family_empty=receipt["family_empty"])
    beat("KILLED", reason=reason, family_empty=receipt["family_empty"])
    return EXIT_OK if receipt["family_empty"] else EXIT_KILL_FAILED


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--create-time", type=float, required=True)
    ap.add_argument("--chain-id", required=True)
    ap.add_argument("--status-path", type=Path, required=True)
    ap.add_argument("--watch-dir", type=Path, required=True)
    ap.add_argument("--hard-deadline-epoch", type=float, required=True)
    ap.add_argument("--mono-budget-s", type=float, required=True)
    ap.add_argument("--stale-after-s", type=float, required=True)
    ap.add_argument("--startup-grace-s", type=float, required=True)
    ap.add_argument("--poll-s", type=float, required=True)
    ap.add_argument("--kill-grace-s", type=float, default=10.0)
    ap.add_argument("--blind-limit-s", type=float, default=20.0)
    ap.add_argument("--log", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        a.log.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return watch(pid=a.pid, create_time=a.create_time, chain_id=a.chain_id, status_path=a.status_path,
                 watch_dir=a.watch_dir, hard_deadline_epoch=a.hard_deadline_epoch,
                 mono_budget_s=a.mono_budget_s, stale_after_s=a.stale_after_s,
                 startup_grace_s=a.startup_grace_s, poll_s=a.poll_s, log_path=a.log,
                 own_sha256=file_sha256(__file__), kill_grace_s=a.kill_grace_s,
                 blind_limit_s=a.blind_limit_s)


if __name__ == "__main__":
    sys.exit(main())
