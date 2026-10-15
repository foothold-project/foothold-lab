"""The gate and the watchdog must survive the tree kill of the process that ran their launcher.

Shape that matters: a grandparent G (stands for the session shell) runs the launcher as a child and
stays alive; the launcher exits after READY; then `taskkill /F /T` ends G. The detached gate and
watchdog must still be alive and the chain must still finish (DONE) by itself.
Known opposite (measured 10/15): if the PARENT is still alive during the tree kill, a detached child dies.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
os.environ.setdefault("S2_A3_DIR", str(HERE.parent / "s2_step4a3"))
sys.path.insert(0, str(HERE))
import test_s2_unattended as T  # noqa: E402

FAILS = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label, flush=True)
    if not ok:
        FAILS.append(label)


def alive(pid, ct):
    try:
        p = psutil.Process(pid)
        return abs(p.create_time() - ct) <= 0.05 and p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def main():
    root = Path(tempfile.mkdtemp(prefix="s2u_si_"))
    base, outer, appr = T.make_env(root, "p9", mode="healthy", life=8.0)
    m, a = T.write_pair(base, outer, appr)
    marker = root / "launched.txt"
    code = ("import subprocess,sys,time\n"
            "subprocess.run([sys.executable,'-B',%r,'--manifest',%r,'--approval',%r],check=True)\n"
            "open(%r,'w').write('launched')\n"
            "time.sleep(120)\n" % (str(T.LAUNCHER), str(m), str(a), str(marker)))
    g = subprocess.Popen([sys.executable, "-B", "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + 30
    while time.time() < end and not marker.exists():
        time.sleep(0.2)
    rec = T.wait_file(base / "watch" / "launch_record.json", 5)
    check("S1 launcher finished and wrote LAUNCHED", marker.exists() and bool(rec) and rec["state"] == "LAUNCHED")
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(g.pid)], capture_output=True)
    time.sleep(1.0)
    check("S2 the grandparent (session shell stand-in) is gone after the tree kill", g.poll() is not None)
    check("S3 gate and watchdog are still alive after the tree kill",
          alive(rec["gate_pid"], rec["gate_create_time"]) or (base / "watch" / "gate_result.json").exists())
    result = T.wait_file(base / "watch" / "gate_result.json", 40)
    check("S4 the chain still finishes DONE by itself", bool(result) and result["state"] == "DONE" and result["exit_code"] == 0)
    time.sleep(2)
    log = [json.loads(x)["event"] for x in (base / "watch" / "watchdog.log").read_text(encoding="utf-8").splitlines()]
    check("S5 the watchdog saw the gate end by itself and killed nothing",
          "watched_ended_by_itself" in log and not (base / "watch" / "kill_receipt.json").exists())
    print("SUMMARY", "ALL PASS" if not FAILS else "FAIL %s" % FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
