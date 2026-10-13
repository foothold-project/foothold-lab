"""Known-answer tests for isaac_slot.py (lead 10/13 evening). Fake children write the watched log like gpu_guard + Isaac would.
Each case runs the real script (ISAAC_SLOT_SCRIPT may point at a mutated copy). Exit 1 when any check fails."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

SCRIPT = os.environ.get("ISAAC_SLOT_SCRIPT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "isaac_slot.py"))
TMP = tempfile.mkdtemp(prefix="slot_", dir=os.path.dirname(os.path.abspath(__file__)))
DONE = "[INFO]: Time taken for scene creation: 1.0 s"
fails = []

CHILD = r'''
import sys, time, json
log, plan, rc = sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3])
f = open(log, "w", encoding="utf-8")
for d, line in plan:
    time.sleep(d)
    f.write(line + "\n"); f.flush()
f.close()
sys.exit(rc)
'''
child_py = os.path.join(TMP, "child.py")
open(child_py, "w").write(CHILD)


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:200], "want", repr(want)[:120])
    if not ok:
        fails.append(name)


def slot(name, plan, rc=0, timeout=None, extra=None, case=None, registry=None, lock=None, scan=True):
    d = os.path.join(TMP, case or name)
    os.makedirs(d, exist_ok=True)
    log = os.path.join(d, name + ".log")
    recp = os.path.join(d, name + ".slot.json")
    cmd = [sys.executable, SCRIPT, "--watch_log", log, "--record", recp, "--lock", lock or os.path.join(d, "lock"),
           "--registry", registry or os.path.join(d, "reg.json"), "--scan_dirs", d if scan else ""]
    if timeout:
        cmd += ["--convert_timeout_s", str(timeout)]
    cmd += (extra or []) + ["--", sys.executable, child_py, log, json.dumps(plan), str(rc)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        rec = json.load(open(recp, encoding="utf-8"))
    except FileNotFoundError:
        rec = {}
    return r.returncode, rec, t0, time.time()


U1 = "Loading IsaacLab.usd_20261013_190000_1234/go2.usd"
U2 = "Loading IsaacLab.usd_20261013_190001_5678/go2.usd"
try:
    rc, rec, _, _ = slot("t1", [[0.2, U1], [0.8, DONE], [0.5, "train"]])
    check("T1 one run: exit 0, one USD folder, released at the scene line", (rc, rec.get("usd_final"), rec.get("state_at_release")),
          (0, ["20261013_190000_1234"], "scene_built"))

    # T2: two runs at once must not overlap their conversion (start .. scene line)
    res = {}

    def go(k, u):
        res[k] = slot(k, [[0.1, "start"], [1.5, u], [0.3, DONE], [2.0, "rest"]], case="t2")
    th = [threading.Thread(target=go, args=("a", U1)), threading.Thread(target=go, args=("b", U2))]
    for t in th:
        t.start()
        time.sleep(0.2)
    for t in th:
        t.join()
    ra, rb = res["a"][1], res["b"][1]
    first, second = (ra, rb) if ra.get("lock_wait_s", 0) <= rb.get("lock_wait_s", 0) else (rb, ra)
    check("T2 two runs at once: both exit 0 and the second waited for the first's scene line (wait >= ~1.8 s)",
          (res["a"][0], res["b"][0], second.get("lock_wait_s", 0) >= 1.5), (0, 0, True))

    rc1, _, _, _ = slot("c1", [[0.1, U1], [0.2, DONE]], case="t3")
    rc2, rec2, _, _ = slot("c2", [[0.1, U1], [0.2, DONE], [1.0, "rest"]], case="t3")
    check("T3 a second run naming the same USD folder: 96, conflict named", (rc1, rc2, sorted(rec2.get("conflicts", {}))),
          (0, 96, ["20261013_190000_1234"]))

    # T3b / T3c: the two guards one at a time (each alone must catch it)
    R = os.path.join(TMP, "shared_reg.json")
    rc1, _, _, _ = slot("r1", [[0.1, U2], [0.2, DONE]], case="t3b_a", registry=R, scan=False)
    rc2, rec2, _, _ = slot("r2", [[0.1, U2], [0.2, DONE], [1.0, "rest"]], case="t3b_b", registry=R, scan=False)
    check("T3b registry alone (no log scan): the same folder in another log dir is caught, 96", (rc1, rc2), (0, 96))
    rc1, _, _, _ = slot("s1", [[0.1, U1], [0.2, DONE]], case="t3c", registry=os.path.join(TMP, "reg_s1.json"))
    rc2, rec2, _, _ = slot("s2", [[0.1, U1], [0.2, DONE], [1.0, "rest"]], case="t3c", registry=os.path.join(TMP, "reg_s2.json"))
    check("T3c log scan alone (separate registries): a log in the scanned dir naming the folder is caught, 96", (rc1, rc2), (0, 96))

    rc, rec, t0, t1 = slot("t4", [[0.3, U1], [0.3, "Traceback (most recent call last)"]], rc=1)
    check("T4 a child that dies before the scene line: its exit code, lock released at exit", (rc, rec.get("state_at_release")), (1, "exited"))

    rc, rec, _, _ = slot("t5", [[0.2, "no usd line"], [0.2, DONE]])
    check("T5 exit 0 with no USD folder in the log: 95", rc, 95)

    rc, rec, _, _ = slot("t5b", [[0.2, U1], [0.2, DONE], [0.2, U2]])
    check("T5b exit 0 with two USD folders in the log: 95", rc, 95)

    rc, rec, t0, t1 = slot("t6", [[0.2, U1], [30, DONE]], timeout=2)
    check("T6 no scene line within the limit: child ended, 97, well before its 30 s", (rc, rec.get("state_at_release"), t1 - t0 < 20), (97, "convert_timeout", True))

    d7 = os.path.join(TMP, "t7")
    os.makedirs(d7, exist_ok=True)
    open(os.path.join(d7, "t7.log"), "w").write(U2 + "\n" + DONE + "\n")  # an older attempt's log
    rc, rec, t0, t1 = slot("t7", [[1.5, U1], [0.2, DONE]], case="t7")
    check("T7 an old log with a scene line is moved aside first; the slot waits for the new one",
          (rc, rec.get("hold_s", 0) >= 1.4, "moved_old_log" in rec, rec.get("usd_final")), (0, True, True, ["20261013_190000_1234"]))
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
