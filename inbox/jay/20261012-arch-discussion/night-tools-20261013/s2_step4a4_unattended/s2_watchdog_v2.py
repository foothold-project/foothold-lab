"""Independent hard-deadline watchdog v2 (revision r2, after ASTRA 17z) for the unattended gate.

Separate process from the gate it watches. Requirements (VERIFY-astra-17x section 3) and the 17z fixes:
  1 READY handshake: ready.json is written only after args, identity and the watch dir are proven.
  2 identity: the watched process is (pid, create_time) from the launcher; the status heartbeat must
    carry the same chain_id; every poll rewrites watchdog_hb.json so the gate can check this watcher.
  3 deadlines: absolute wall clock AND a monotonic budget measured from watcher start.
  4 heartbeat input: NaN / Inf / non-number / future-dated / wrong chain are never progress.
    Staleness = no new valid heartbeat value for stale_after_s (monotonic).
  5 file I/O (status read, heartbeat write, log) runs in a worker thread. The deciding thread never
    waits on a disk call, so a hung or failing disk can delay a log but not a kill; if the worker
    stops finishing cycles for stale_after_s the watchdog treats the run as unobservable and kills.
  6 AccessDenied is "blind", never "ended by itself". Blind too long exits 6.
  7 identity is never guessed (17z P1): a process whose creation time was not read, or cannot be read
    now, is UNVERIFIED. It is never signalled and it makes family_empty false. Only the gate
    process (verified before the signal) and descendants whose (pid, create_time) matched at the
    snapshot and still match right before the signal are ever killed here.
  8 kill_receipt.json records reason, descendants seen before the kill, survivors, unverified ones and
    family_status = empty | survivors | unverified. Exit 2 unless the family is proven empty.
Exit codes: 0 watched process ended by itself, or was ended here and its family proven empty;
2 kill failed / family survivors / family unverified; 3 identity mismatch at start; 4 bad arguments;
6 blind (cannot read the watched process); 7 cannot publish READY.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import threading
import time
from pathlib import Path

import psutil

EXIT_OK, EXIT_KILL_FAILED, EXIT_IDENTITY, EXIT_BAD_ARGS, EXIT_BLIND, EXIT_NO_READY = 0, 2, 3, 4, 6, 7
FUTURE_SLACK_S = 5.0


def finite_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def safe_log(path, **event) -> bool:
    """Append one JSON line. Never raises."""
    try:
        event["epoch"] = time.time()
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return True
    except Exception:
        return False


def atomic_write(path, value) -> bool:
    """Best-effort atomic JSON write. Returns False instead of raising."""
    try:
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(value, sort_keys=True, allow_nan=False), encoding="utf-8")
        for _ in range(50):
            try:
                os.replace(tmp, target)
                return True
            except PermissionError:
                time.sleep(0.01)
        return False
    except Exception:
        return False


def bounded_call(fn, timeout: float = 10.0) -> bool:
    """Run a disk call in a daemon thread; give up after `timeout`. True when it finished."""
    box = {}

    def runner():
        try:
            box["ok"] = fn()
        except Exception:
            box["ok"] = False

    th = threading.Thread(target=runner, daemon=True)
    th.start()
    th.join(timeout)
    return not th.is_alive() and bool(box.get("ok", True))


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
    """([(pid, create_time_or_None)], complete). complete is False when the listing or any creation
    time could not be read: those descendants are UNVERIFIED and must never be signalled."""
    try:
        children = proc.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None, False
    rows, complete = [], True
    for child in children:
        try:
            rows.append((child.pid, child.create_time()))
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            rows.append((child.pid, None))
            complete = False
    return rows, complete


def classify(rows, process_factory):
    """-> (verified_alive, unverified_pids). A pid whose creation time was never read, or cannot be
    read now, is unverified; a reused pid (different creation time) counts as gone."""
    alive, unverified = [], []
    for pid, ct in rows or []:
        if ct is None:
            unverified.append(pid)
            continue
        try:
            state = identity_state(process_factory(pid), ct)
        except psutil.NoSuchProcess:
            state = "gone"
        except psutil.AccessDenied:
            state = "denied"
        if state == "match":
            alive.append((pid, ct))
        elif state == "denied":
            unverified.append(pid)
    return alive, unverified


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


class IoWorker(threading.Thread):
    """All routine file I/O. The deciding thread only reads `snapshot` and `cycle_mono` under the lock."""

    def __init__(self, *, status_path, chain_id, hb_path, log_path, poll_s, clock, mono):
        super().__init__(daemon=True)
        self.status_path, self.chain_id, self.hb_path, self.log_path = status_path, chain_id, hb_path, log_path
        self.poll_s, self.clock, self.mono = poll_s, clock, mono
        self.lock = threading.Lock()
        self.snapshot = (None, None, "not_read_yet", mono())
        self.cycle_mono = mono()
        self.pending_beat, self.pending_logs = None, []
        self.halt = threading.Event()

    def post_beat(self, payload):
        with self.lock:
            self.pending_beat = payload

    def post_log(self, **event):
        with self.lock:
            self.pending_logs.append(event)

    def read(self):
        with self.lock:
            return self.snapshot, self.cycle_mono

    def run(self):
        while not self.halt.is_set():
            try:
                hb, state, why = read_status(self.status_path, self.chain_id, self.clock())
            except Exception:
                hb, state, why = None, None, "read_exception"
            with self.lock:
                self.snapshot = (hb, state, why, self.mono())
                beat, logs = self.pending_beat, self.pending_logs
                self.pending_beat, self.pending_logs = None, []
            if beat is not None:
                atomic_write(self.hb_path, beat)
            for event in logs:
                safe_log(self.log_path, **event)
            with self.lock:
                self.cycle_mono = self.mono()
            self.halt.wait(self.poll_s)


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
    worker = None

    def beat(state, **extra):
        nonlocal seq
        seq += 1
        payload = {**me, **extra, "state": state, "seq": seq, "epoch": clock()}
        if worker is not None:
            worker.post_beat(payload)
        else:
            bounded_call(lambda: atomic_write(hb_path, payload), 5.0)

    def log(**event):
        if worker is not None:
            worker.post_log(**event)
        else:
            bounded_call(lambda: safe_log(log_path, **event), 5.0)

    if bad:
        bounded_call(lambda: safe_log(log_path, event="bad_args", field=bad), 5.0)
        beat("BAD_ARGS", field=bad)
        return EXIT_BAD_ARGS
    try:
        proc = process_factory(pid)
    except psutil.NoSuchProcess:
        bounded_call(lambda: safe_log(log_path, event="watched_not_found_at_start", pid=pid), 5.0)
        return EXIT_IDENTITY
    except psutil.AccessDenied:
        bounded_call(lambda: safe_log(log_path, event="watched_blind_at_start", pid=pid), 5.0)
        beat("BLIND", why="access_denied_at_start")
        return EXIT_BLIND
    start_state = identity_state(proc, create_time)
    if start_state == "denied":
        bounded_call(lambda: safe_log(log_path, event="watched_blind_at_start", pid=pid), 5.0)
        beat("BLIND", why="access_denied_at_start")
        return EXIT_BLIND
    if start_state != "match":
        bounded_call(lambda: safe_log(log_path, event="identity_mismatch_at_start", pid=pid,
                                      expected=create_time, state=start_state), 5.0)
        return EXIT_IDENTITY
    t0_wall, t0_mono = clock(), mono()
    deadline_mono = t0_mono + min(mono_budget_s, hard_deadline_epoch - t0_wall)
    seq += 1
    ready = {**me, "state": "READY", "seq": seq, "epoch": clock(), "watchdog_sha256": own_sha256,
             "hard_deadline_epoch": hard_deadline_epoch, "mono_budget_s": mono_budget_s,
             "stale_after_s": stale_after_s, "startup_grace_s": startup_grace_s}
    if not bounded_call(lambda: atomic_write(ready_path, ready), 10.0):
        bounded_call(lambda: safe_log(log_path, event="cannot_publish_ready"), 5.0)
        return EXIT_NO_READY
    worker = IoWorker(status_path=status_path, chain_id=chain_id, hb_path=hb_path, log_path=log_path,
                      poll_s=poll_s, clock=clock, mono=mono)
    worker.start()
    log(event="watchdog_started", pid=pid, create_time=create_time, chain_id=chain_id,
        hard_deadline_epoch=hard_deadline_epoch, mono_budget_s=mono_budget_s, stale_after_s=stale_after_s)
    last_hb, last_progress_mono, ever_valid = None, t0_mono, False
    blind_since = None
    reason = None

    def finish(code):
        worker.halt.set()
        worker.join(2.0)
        return code

    while reason is None:
        now, m = clock(), mono()
        state = identity_state(proc, create_time)
        if state == "gone":
            log(event="watched_ended_by_itself")
            beat("ENDED")
            sleep(poll_s * 2)
            return finish(EXIT_OK)
        if state == "mismatch":
            log(event="watched_identity_changed_no_signal")
            beat("ENDED", why="identity_changed")
            sleep(poll_s * 2)
            return finish(EXIT_OK)
        if state == "denied":
            blind_since = m if blind_since is None else blind_since
            beat("BLIND", why="access_denied", blind_s=m - blind_since)
            if m - blind_since > blind_limit_s:
                log(event="blind_too_long")
                sleep(poll_s * 2)
                return finish(EXIT_BLIND)
        else:
            blind_since = None
            try:
                running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                running = False
            except psutil.AccessDenied:
                running = True
            if not running:
                log(event="watched_ended_by_itself")
                beat("ENDED")
                sleep(poll_s * 2)
                return finish(EXIT_OK)
        (hb, _hb_state, why, obs_mono), cycle_mono = worker.read()
        if hb is not None and hb != last_hb:
            last_hb, last_progress_mono, ever_valid = hb, obs_mono, True
        if now >= hard_deadline_epoch:
            reason = "hard_deadline"
        elif m >= deadline_mono:
            reason = "mono_deadline"
        elif m - cycle_mono > stale_after_s:
            reason = "io_stalled"
        elif not ever_valid and m - t0_mono > startup_grace_s:
            reason = "no_valid_status_after_startup_grace"
        elif ever_valid and m - last_progress_mono > stale_after_s:
            reason = "heartbeat_stale"
        else:
            if state != "denied":
                beat("WATCHING", hb_valid=hb is not None, hb_invalid_reason=why)
            sleep(poll_s)
    # ---- trigger: decide and kill first, write afterwards (no disk call precedes the kill) ----
    family, complete = descendants_snapshot(proc)
    receipt = {"chain_id": chain_id, "reason": reason, "gate_pid": pid, "gate_create_time": create_time,
               "trigger_epoch": clock(), "descendants_before_kill": family,
               "descendant_snapshot_complete": complete, "gate_killed": False}
    pre = identity_state(proc, create_time)
    if pre == "mismatch":
        receipt["note"] = "identity_mismatch_before_kill_no_signal"
        bounded_call(lambda: atomic_write(receipt_path, receipt), 10.0)
        log(event="identity_mismatch_before_kill_no_signal")
        return finish(EXIT_IDENTITY)
    try:
        proc.kill()
    except psutil.NoSuchProcess:
        receipt["note"] = "gate_already_gone_before_kill"
    except psutil.AccessDenied:
        receipt["note"] = "kill_access_denied"
        bounded_call(lambda: atomic_write(receipt_path, receipt), 10.0)
        log(event="kill_access_denied", reason=reason)
        beat("KILL_DENIED", reason=reason)
        sleep(poll_s * 2)
        return finish(EXIT_KILL_FAILED)
    try:
        proc.wait(timeout=kill_grace_s)
    except psutil.TimeoutExpired:
        receipt["note"] = "watched_still_running_after_kill"
        bounded_call(lambda: atomic_write(receipt_path, receipt), 10.0)
        log(event="watched_still_running_after_kill", reason=reason)
        return finish(EXIT_KILL_FAILED)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    receipt["gate_killed"] = receipt.get("note") != "gate_already_gone_before_kill"
    end = mono() + family_wait_s
    alive, unverified = classify(family, process_factory)
    while alive and mono() < end:
        sleep(0.1)
        alive, unverified = classify(family, process_factory)
    forced = []
    for cpid, cct in alive:
        try:
            cp = process_factory(cpid)
            if identity_state(cp, cct) == "match":  # re-verified immediately before the signal
                cp.kill()
                forced.append(cpid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    end2 = mono() + family_wait_s
    remaining_alive, remaining_unverified = classify(family, process_factory)
    while remaining_alive and forced and mono() < end2:
        sleep(0.1)
        remaining_alive, remaining_unverified = classify(family, process_factory)
    if remaining_alive:
        status = "survivors"
    elif remaining_unverified or not complete or family is None:
        status = "unverified"
    else:
        status = "empty"
    receipt.update(descendants_force_killed=forced, descendants_alive_after=remaining_alive,
                   descendants_unverified=remaining_unverified, family_status=status,
                   family_empty=status == "empty", receipt_epoch=clock())
    bounded_call(lambda: atomic_write(receipt_path, receipt), 10.0)
    log(event="gate_killed", reason=reason, family_status=status)
    beat("KILLED", reason=reason, family_status=status)
    sleep(poll_s * 2)
    return finish(EXIT_OK if status == "empty" else EXIT_KILL_FAILED)


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
