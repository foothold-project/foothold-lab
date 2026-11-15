"""Launcher glue: start the supervisor and the independent watchdog, both detached from this terminal.

Records the supervisor pid and creation time immediately after start and passes exactly those
to the watchdog. This script exits right after both are started; the supervisor and the
watchdog keep running without it (and without any model session).
Usage: python s2_launch_stage0.py --status-path S --hard-deadline-epoch T --stale-after-s N
          --startup-grace-s N --poll-s N --workdir D --supervisor-log L --watchdog-log L -- <supervisor argv...>
"""
from __future__ import annotations
import argparse
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


def start_detached(argv, *, cwd: Path, log_path: Path, env=None):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(log_path, "ab")
    flags = FLAGS if sys.platform == "win32" else 0
    return subprocess.Popen(argv, cwd=str(cwd), stdout=stream, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, creationflags=flags, env=env,
                            close_fds=True)


def main(argv=None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--" not in raw:
        print("missing -- separator before supervisor argv", file=sys.stderr)
        return 4
    split = raw.index("--")
    ap = argparse.ArgumentParser()
    for name, kind in (("status-path", Path), ("hard-deadline-epoch", float), ("stale-after-s", float),
                       ("startup-grace-s", float), ("poll-s", float), ("workdir", Path),
                       ("supervisor-log", Path), ("watchdog-log", Path), ("launch-record", Path)):
        ap.add_argument("--" + name, type=kind, required=True)
    a = ap.parse_args(raw[:split])
    sup_argv = raw[split + 1:]
    if not sup_argv:
        print("empty supervisor argv", file=sys.stderr)
        return 4
    here = Path(__file__).resolve().parent
    sup = start_detached(sup_argv, cwd=a.workdir, log_path=a.supervisor_log)
    try:
        create_time = psutil.Process(sup.pid).create_time()
    except psutil.NoSuchProcess:
        print("supervisor ended before it could be identified", file=sys.stderr)
        return 5
    wd_argv = [sys.executable, "-B", str(here / "s2_hard_watchdog.py"), "--pid", str(sup.pid),
               "--create-time", repr(create_time), "--status-path", str(a.status_path),
               "--hard-deadline-epoch", repr(a.hard_deadline_epoch),
               "--stale-after-s", repr(a.stale_after_s), "--startup-grace-s", repr(a.startup_grace_s),
               "--poll-s", repr(a.poll_s), "--log", str(a.watchdog_log)]
    wd = start_detached(wd_argv, cwd=a.workdir, log_path=a.watchdog_log.with_suffix(".stdout.log"))
    a.launch_record.parent.mkdir(parents=True, exist_ok=True)
    a.launch_record.write_text(json.dumps({
        "launched_epoch": time.time(), "supervisor_pid": sup.pid, "supervisor_create_time": create_time,
        "watchdog_pid": wd.pid, "hard_deadline_epoch": a.hard_deadline_epoch,
        "stale_after_s": a.stale_after_s, "supervisor_argv": sup_argv}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps({"supervisor_pid": sup.pid, "watchdog_pid": wd.pid}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
