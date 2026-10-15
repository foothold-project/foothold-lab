"""Unattended launcher: starts the gate and the independent watchdog, waits for READY, exits.

Written by lead 2026-10-15 for ASTRA review. Nothing is started unless the gate, watchdog and
this launcher file hashes equal the approved manifest block. The gate starts first and does no
GPU work until the watchdog publishes a matching READY; if the launcher itself fails, is killed
between the two starts, or the watchdog never becomes ready, the gate exits by itself (6) and
this launcher also kills only the two processes it just created (identity checked).

Exit codes: 0 gate + watchdog running and READY seen; 4 nothing started (contract / hash /
existing watch dir / bad input); 5 started but not ready, both created processes cleaned up.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
FLAGS = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW


def file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def start_detached(argv, *, cwd: Path, log_path: Path):
    stream = open(log_path, "ab")
    flags = FLAGS if sys.platform == "win32" else 0
    try:
        return subprocess.Popen([str(x) for x in argv], cwd=str(cwd), stdout=stream, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    finally:
        stream.close()


def kill_if_same(proc: subprocess.Popen, create_time):
    """Kill only the process this launcher created (pid + creation time must still match)."""
    if proc is None:
        return "not_started"
    try:
        p = psutil.Process(proc.pid)
        if create_time is not None and abs(p.create_time() - create_time) > 0.05:
            return "identity_changed_no_signal"
        p.kill()
        p.wait(timeout=10)
        return "killed"
    except psutil.NoSuchProcess:
        return "already_gone"
    except (psutil.AccessDenied, psutil.TimeoutExpired) as ex:
        return "kill_failed:" + type(ex).__name__


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--approval", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        outer = json.loads(a.manifest.read_text(encoding="utf-8"))
        block = outer["unattended"]
        gate_path, watchdog_path = Path(block["gate_path"]), Path(block["watchdog_path"])
        if Path(__file__).resolve() != Path(block["launcher_path"]).resolve() or \
                file_sha256(__file__) != block["launcher_sha256"]:
            raise ValueError("launcher_hash")
        if file_sha256(gate_path) != block["gate_sha256"]:
            raise ValueError("gate_hash")
        if file_sha256(watchdog_path) != block["watchdog_sha256"]:
            raise ValueError("watchdog_hash")
        if outer.get("observer_mode") != "unattended" or outer.get("contract_version") != "a4u":
            raise ValueError("contract_mode")
        python_path = Path(outer["python_path"])
        watch_dir = Path(block["watch_dir"])
        if watch_dir.exists():
            raise ValueError("watch_dir_exists")
        timings = [float(block[k]) for k in ("ready_timeout_s", "stale_after_s", "startup_grace_s", "poll_s",
                                             "mono_budget_s", "hard_deadline_extra_s")]
        ready_timeout, stale, grace, poll, mono_budget, extra = timings
        hard_deadline = float(outer["deadline_epoch"]) + extra
        if not python_path.is_file():
            raise ValueError("python_path")
    except Exception as ex:
        print(json.dumps({"launch": "NOT_STARTED", "reason": repr(ex)}), flush=True)
        return 4
    watch_dir.mkdir(parents=True, exist_ok=False)
    gate = wd = None
    gate_ct = wd_ct = None
    state = "LAUNCH_ABORTED"
    reason = "unknown"
    try:
        gate = start_detached([python_path, "-B", gate_path, "--manifest", a.manifest, "--approval", a.approval,
                               "--watch-dir", watch_dir], cwd=gate_path.parent, log_path=watch_dir / "gate.stdout.log")
        gate_ct = psutil.Process(gate.pid).create_time()
        wd = start_detached([python_path, "-B", watchdog_path, "--pid", gate.pid, "--create-time", repr(gate_ct),
                             "--chain-id", outer["chain_id"], "--status-path", outer["status_path"],
                             "--watch-dir", watch_dir, "--hard-deadline-epoch", repr(hard_deadline),
                             "--mono-budget-s", repr(mono_budget), "--stale-after-s", repr(stale),
                             "--startup-grace-s", repr(grace), "--poll-s", repr(poll),
                             "--log", watch_dir / "watchdog.log"],
                            cwd=watchdog_path.parent, log_path=watch_dir / "watchdog.stdout.log")
        wd_ct = psutil.Process(wd.pid).create_time()
        stop_at = time.monotonic() + ready_timeout + 10
        reason = "ready_timeout"
        while time.monotonic() < stop_at:
            if gate.poll() is not None:
                reason = "gate_exited_early:%s" % gate.returncode
                break
            if wd.poll() is not None:
                reason = "watchdog_exited_early:%s" % wd.returncode
                break
            if (watch_dir / "ready.json").is_file():
                state, reason = "LAUNCHED", "ready_seen"
                break
            time.sleep(0.2)
    except Exception as ex:
        reason = "launcher_exception:" + repr(ex)
    record = {"state": state, "reason": reason, "launched_epoch": time.time(), "chain_id": outer.get("chain_id"),
              "gate_pid": getattr(gate, "pid", None), "gate_create_time": gate_ct,
              "watchdog_pid": getattr(wd, "pid", None), "watchdog_create_time": wd_ct,
              "gate_sha256": block["gate_sha256"], "watchdog_sha256": block["watchdog_sha256"],
              "launcher_sha256": block["launcher_sha256"], "manifest_sha256": file_sha256(a.manifest)}
    if state != "LAUNCHED":
        record["cleanup"] = {"gate": kill_if_same(gate, gate_ct), "watchdog": kill_if_same(wd, wd_ct)}
    try:
        (watch_dir / "launch_record.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    except OSError:
        pass
    print(json.dumps({"launch": state, "reason": reason, "gate_pid": record["gate_pid"],
                      "watchdog_pid": record["watchdog_pid"]}), flush=True)
    return 0 if state == "LAUNCHED" else 5


if __name__ == "__main__":
    sys.exit(main())
