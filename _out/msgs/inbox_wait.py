"""Wait for new orchestration messages after the coordinator moved to the mailbox shell (lead, 10/28 04:1x).

The lead pane is no longer the run consumer (check --run is fenced), so read the inbox without acking:
poll `orca orchestration inbox --json` every 20 s and exit, printing the new rows, once a sequence number
above the last seen one appears. The last seen sequence lives in _out/msgs/.inbox_seq.
Usage: python _out/msgs/inbox_wait.py [timeout_s]
"""
import json
import os
import pathlib
import shlex
import socket
import subprocess
import sys
import time

WINDOWS = sys.platform == "win32"


def orca_cli(env=os.environ, platform=sys.platform):
    """The Orca CLI command, resolved the way Orca itself does (resolveOrchestrationCliExecutable).

    On Linux a bare `orca` is usually GNOME's screen reader, which prints no JSON, so the old call read an empty
    inbox forever and only said "timeout". Order: ORCA_CLI_COMMAND, then orca-dev when ORCA_DEV_REPO_ROOT is set,
    then orca-ide on Linux and orca elsewhere. Windows keeps the bare `orca` it always used.
    """
    configured = (env.get("ORCA_CLI_COMMAND") or "").strip()
    if configured:
        return shlex.split(configured)
    if env.get("ORCA_DEV_REPO_ROOT"):
        return ["orca-dev"]
    return ["orca-ide"] if platform.startswith("linux") else ["orca"]


def state_path(env=os.environ, platform=sys.platform, host=None):
    """Windows: _out/msgs/.inbox_seq as before. Elsewhere the host name is part of the file name, so a sequence file
    copied from another machine (its mailbox numbers mean nothing here) is not read and new messages are not skipped."""
    name = env.get("INBOX_STATE", ".inbox_seq")
    if platform != "win32":
        name += "." + (host or socket.gethostname())
    return pathlib.Path(__file__).with_name(name)


def rows(cmd=None, run=subprocess.run, platform=sys.platform):
    cmd = cmd or orca_cli(platform=platform)
    try:
        done = run(cmd + ["orchestration", "inbox", "--limit", "30", "--json"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
    except OSError as e:
        if platform == "win32":
            raise
        raise SystemExit("inbox_wait: cannot run Orca CLI %r (%s). Set ORCA_CLI_COMMAND." % (cmd[0], e))
    t = done.stdout or ""
    try:
        d = json.loads(t[t.find("{"):])
    except ValueError:
        if platform != "win32":     # a wrong program answers without JSON: say so instead of waiting an hour
            raise SystemExit("inbox_wait: %r gave no JSON (rc %s). Is it the Orca CLI? Set ORCA_CLI_COMMAND."
                             % (cmd[0], done.returncode))
        return []
    return (d.get("result") or {}).get("messages") or []


def main():
    state = state_path()
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 3600.0
    seen = int(state.read_text()) if state.exists() else max((int(m["sequence"]) for m in rows()), default=0)
    state.write_text(str(seen))
    end = time.time() + timeout
    while time.time() < end:
        new = sorted((m for m in rows() if int(m["sequence"]) > seen), key=lambda m: int(m["sequence"]))
        if new:
            for m in new:
                print(m["type"], m["from_handle"][5:13], m.get("subject", ""), "|",
                      (m.get("body") or "")[:1200].replace("\n", " / "))
            state.write_text(str(max(int(m["sequence"]) for m in new)))
            sys.exit(0)
        time.sleep(20)
    print("timeout, no new message after sequence", seen)


if __name__ == "__main__":
    main()
