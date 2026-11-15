"""Unattended launcher (revision r2, after ASTRA 17z): starts the gate and the independent watchdog,
waits until the gate has ACCEPTED the READY and the supervisor has begun writing its status, exits.

Nothing is started unless the gate, watchdog and this launcher file hashes equal the approved
manifest block and the final-deadline bound holds. The gate starts first and does no GPU work until
the watchdog publishes a matching READY; if the launcher fails or is killed between the two starts the
gate exits by itself (6) after ready_timeout_s. If this launcher decides to abort, it signals ONLY the
two processes it created, and only through the process handles it holds from Popen (no pid lookup, so
a reused pid can never be hit).

Result states: RUNNING (status.json of the supervisor seen) / FINISHED_OK (gate already wrote DONE) /
LAUNCH_ABORTED (anything else: watchdog or gate exited early, gate refused, timeout).
Exit codes: 0 RUNNING or FINISHED_OK; 4 nothing started; 5 aborted, created processes cleaned up.
READY seen is not success: only the supervisor status (or a DONE result) counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from s2_unattended_gate import expected_watchdog_argv, final_bound_ok  # noqa: E402

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
FLAGS = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
# Kit asks for the EULA on stdin otherwise ("input(): lost sys.stdin", first live attempt 10/15 14:03).
ISAAC_ENV = {"OMNI_KIT_ACCEPT_EULA": "YES", "PYTHONUNBUFFERED": "1"}


def file_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def start_detached(argv, *, cwd: Path, log_path: Path):
    stream = open(log_path, "ab")
    flags = FLAGS if sys.platform == "win32" else 0
    try:
        return subprocess.Popen([str(x) for x in argv], cwd=str(cwd), stdout=stream, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True,
                                env={**os.environ, **ISAAC_ENV})
    finally:
        stream.close()


def kill_created(proc):
    """Signal a process THIS launcher created, through its own Popen handle (never by pid lookup)."""
    if proc is None:
        return "not_started"
    try:
        if proc.poll() is not None:
            return "already_exited"
        proc.kill()
        proc.wait(timeout=10)
        return "killed"
    except Exception as ex:
        return "kill_failed:" + type(ex).__name__


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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
        if not final_bound_ok(outer, block):
            raise ValueError("final_deadline_margin")
        python_path = Path(outer["python_path"])
        watch_dir = Path(block["watch_dir"])
        if watch_dir.exists():
            raise ValueError("watch_dir_exists")
        ready_timeout = float(block["ready_timeout_s"])
        if not python_path.is_file():
            raise ValueError("python_path")
    except Exception as ex:
        print(json.dumps({"launch": "NOT_STARTED", "reason": repr(ex)}), flush=True)
        return 4
    watch_dir.mkdir(parents=True, exist_ok=False)
    gate = wd = None
    state, reason = "LAUNCH_ABORTED", "unknown"
    try:
        gate = start_detached([python_path, "-B", gate_path, "--manifest", a.manifest, "--approval", a.approval,
                               "--watch-dir", watch_dir], cwd=gate_path.parent, log_path=watch_dir / "gate.stdout.log")
        gate_ct = psutil.Process(gate.pid).create_time()
        wd_argv = expected_watchdog_argv(outer, block, gate_pid=gate.pid, gate_create_time=gate_ct)
        wd = start_detached(wd_argv, cwd=watchdog_path.parent, log_path=watch_dir / "watchdog.stdout.log")
        stop_at = time.monotonic() + ready_timeout + 30
        reason = "timeout_waiting_for_ready_and_supervisor"
        ready_seen = False
        while time.monotonic() < stop_at:
            result = read_json(watch_dir / "gate_result.json")
            if result is not None:
                if result.get("state") == "DONE":
                    state, reason = "FINISHED_OK", "gate_wrote_DONE"
                else:
                    reason = "gate_terminal:%s:%s" % (result.get("state"), result.get("reason", ""))
                break
            if gate.poll() is not None:
                reason = "gate_exited_early:%s" % gate.returncode
                break
            if wd.poll() is not None:
                reason = "watchdog_exited_early:%s" % wd.returncode
                break
            ready_seen = ready_seen or (watch_dir / "ready.json").is_file()
            if ready_seen and Path(outer["status_path"]).is_file():
                state, reason = "RUNNING", "supervisor_status_seen"
                break
            time.sleep(0.2)
    except Exception as ex:
        reason = "launcher_exception:" + repr(ex)
    record = {"state": state, "reason": reason, "launched_epoch": time.time(), "chain_id": outer.get("chain_id"),
              "gate_pid": getattr(gate, "pid", None), "gate_create_time": locals().get("gate_ct"),
              "watchdog_pid": getattr(wd, "pid", None),
              "gate_sha256": block["gate_sha256"], "watchdog_sha256": block["watchdog_sha256"],
              "launcher_sha256": block["launcher_sha256"], "manifest_sha256": file_sha256(a.manifest)}
    try:
        record["watchdog_create_time"] = psutil.Process(wd.pid).create_time() if wd is not None else None
    except Exception:
        record["watchdog_create_time"] = None
    if state == "LAUNCH_ABORTED":
        record["cleanup"] = {"gate": kill_created(gate), "watchdog": kill_created(wd)}
    try:
        (watch_dir / "launch_record.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    except OSError:
        pass
    print(json.dumps({"launch": state, "reason": reason, "gate_pid": record["gate_pid"],
                      "watchdog_pid": record["watchdog_pid"]}), flush=True)
    return 0 if state in ("RUNNING", "FINISHED_OK") else 5


if __name__ == "__main__":
    sys.exit(main())
