"""CPU tests for the independent hard-deadline watchdog. Only processes started by this test are
ever signalled. Known answers are written by hand: a healthy supervisor is never killed, a hung
one is killed within the stale window, an identity mismatch signals nothing, the watchdog
outlives its launcher."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import psutil

HERE = Path(__file__).resolve().parent
PY = sys.executable
FAILS = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label, flush=True)
    if not ok:
        FAILS.append(label)


FAKE_SUPERVISOR = r'''
import json, sys, time
status, mode, life = sys.argv[1], sys.argv[2], float(sys.argv[3])
t0 = time.time()
while time.time() - t0 < life:
    if mode == "healthy" or time.time() - t0 < 1.0:
        with open(status, "w", encoding="utf-8") as s:
            json.dump({"heartbeat_epoch": time.time(), "state": "RUNNING"}, s)
    time.sleep(0.2)
'''


def spawn_fake(tmp: Path, mode: str, life: float):
    script = tmp / "fake_supervisor.py"
    script.write_text(FAKE_SUPERVISOR, encoding="utf-8")
    status = tmp / ("status_" + mode + ".json")
    proc = subprocess.Popen([PY, "-B", str(script), str(status), mode, str(life)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    return proc, status, psutil.Process(proc.pid).create_time()


def run_watchdog(tmp: Path, proc, status, create_time, *, deadline_in, stale=2.0, grace=3.0, log=None):
    log = log or (tmp / ("wd_%d.log" % proc.pid))
    cmd = [PY, "-B", str(HERE / "s2_hard_watchdog.py"), "--pid", str(proc.pid),
           "--create-time", repr(create_time), "--status-path", str(status),
           "--hard-deadline-epoch", repr(time.time() + deadline_in), "--stale-after-s", repr(stale),
           "--startup-grace-s", repr(grace), "--poll-s", "0.3", "--log", str(log)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    events = [r["event"] for r in rows]
    events += ["reason:" + r["reason"] for r in rows if r.get("event") == "trigger"]
    return result.returncode, events


def main():
    tmp = Path(tempfile.mkdtemp(prefix="s2_wd_"))
    decoy = subprocess.Popen([PY, "-B", "-c", "import time; time.sleep(60)"])
    try:
        # 1 healthy supervisor that ends by itself: watchdog exits 0, kills nothing
        proc, status, ct = spawn_fake(tmp, "healthy", 2.0)
        rc, ev = run_watchdog(tmp, proc, status, ct, deadline_in=30)
        check("healthy supervisor ending by itself is left alone", rc == 0 and "supervisor_ended_by_itself" in ev and "trigger" not in ev)
        check("decoy untouched after healthy run", decoy.poll() is None)
        # 2 hung supervisor (heartbeat stops): watchdog kills only it
        proc, status, ct = spawn_fake(tmp, "hang", 60.0)
        t0 = time.time()
        rc, ev = run_watchdog(tmp, proc, status, ct, deadline_in=25, stale=2.0)
        took = time.time() - t0
        check("hung supervisor killed by heartbeat stale", rc == 0 and "supervisor_killed" in ev and "reason:heartbeat_stale" in ev and proc.poll() is not None)
        check("kill happened within stale window plus margin", took < 12.0)
        check("decoy untouched after hang kill", decoy.poll() is None)
        # 3 hard deadline with fresh heartbeat
        proc, status, ct = spawn_fake(tmp, "healthy", 20.0)
        rc, ev = run_watchdog(tmp, proc, status, ct, deadline_in=3.0, stale=30.0)
        check("hard deadline kills even with fresh heartbeat", rc == 0 and "supervisor_killed" in ev and "reason:hard_deadline" in ev and proc.poll() is not None)
        # 4 identity mismatch (pid reuse simulation): nothing signalled
        proc, status, ct = spawn_fake(tmp, "healthy", 20.0)
        rc, ev = run_watchdog(tmp, proc, status, ct + 5.0, deadline_in=30)
        check("wrong creation time: refuses and signals nothing", rc == 3 and "identity_mismatch_at_start" in ev and proc.poll() is None)
        proc.kill(); proc.wait()
        # 5 no status file ever: startup grace then kill
        proc = subprocess.Popen([PY, "-B", "-c", "import time; time.sleep(60)"])
        ct = psutil.Process(proc.pid).create_time()
        rc, ev = run_watchdog(tmp, proc, tmp / "never_written.json", ct, deadline_in=60, stale=5.0, grace=2.0)
        check("no status after startup grace: killed", rc == 0 and "supervisor_killed" in ev and proc.poll() is not None)
        # 6 bad arguments
        proc, status, ct = spawn_fake(tmp, "healthy", 10.0)
        rc, ev = run_watchdog(tmp, proc, status, ct, deadline_in=-5)
        check("past deadline is a bad argument and signals nothing", rc == 4 and proc.poll() is None)
        proc.kill(); proc.wait()
        # 7 watchdog outlives its launcher (detached start, launcher exits)
        script = tmp / "fake_supervisor.py"
        status = tmp / "status_launch.json"
        record = tmp / "launch_record.json"
        wd_log = tmp / "wd_launch.log"
        launcher = [PY, "-B", str(HERE / "s2_launch_stage0.py"), "--status-path", str(status),
                    "--hard-deadline-epoch", repr(time.time() + 60), "--stale-after-s", "2.0",
                    "--startup-grace-s", "3.0", "--poll-s", "0.3", "--workdir", str(tmp),
                    "--supervisor-log", str(tmp / "sup.log"), "--watchdog-log", str(wd_log),
                    "--launch-record", str(record), "--", PY, "-B", str(script), str(status), "hang", "60"]
        res = subprocess.run(launcher, capture_output=True, text=True, timeout=30)
        check("launcher started both and exited", res.returncode == 0 and record.exists())
        rec = json.loads(record.read_text(encoding="utf-8"))
        sup_pid, wd_pid = rec["supervisor_pid"], rec["watchdog_pid"]
        check("watchdog alive after launcher exit", psutil.pid_exists(wd_pid))
        deadline = time.time() + 20
        while time.time() < deadline and psutil.pid_exists(sup_pid):
            time.sleep(0.3)
        events = [json.loads(l)["event"] for l in wd_log.read_text(encoding="utf-8").splitlines()] if wd_log.exists() else []
        check("detached watchdog killed the hung supervisor after launcher was gone", not psutil.pid_exists(sup_pid) and "supervisor_killed" in events)
        check("decoy untouched at the end", decoy.poll() is None)
    finally:
        for p in (decoy,):
            if p.poll() is None:
                p.kill()
    print("SUMMARY", "ALL PASS" if not FAILS else "FAIL %s" % FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
