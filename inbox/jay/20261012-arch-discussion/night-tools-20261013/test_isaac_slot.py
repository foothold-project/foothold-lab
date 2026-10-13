"""Known-answer tests for isaac_slot.py v2 (lead 10/13 evening · ASTRA 17b counterexamples kept as regression cases).
Fake children write the watched log like gpu_guard + Isaac would. ISAAC_SLOT_SCRIPT may point at a mutated copy."""
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
import sys, time, json, os
log, plan, rc = sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3])
root = os.environ.get("FOOTHOLD_USD_ROOT", "NOROOT")
open(log + ".launched", "w").write(root)
f = open(log, "w", encoding="utf-8")
for d, line in plan:
    time.sleep(d)
    f.write(line.replace("{ROOT}", root) + "\n"); f.flush()
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


def slot(name, plan, rc=0, timeout=None, case=None, registry=None, lock=None, scan=True, stop_file="", deadline=0.0):
    d = os.path.join(TMP, case or name)
    os.makedirs(d, exist_ok=True)
    log = os.path.join(d, name + ".log")
    recp = os.path.join(d, name + ".slot.json")
    cmd = [sys.executable, SCRIPT, "--watch_log", log, "--record", recp, "--usd_root", os.path.join(d, "usd", name), "--attempt", "att-" + name,
           "--lock", lock or os.path.join(d, "lock"), "--registry", registry or os.path.join(d, "reg.json"), "--scan_dirs", d if scan else ""]
    if timeout:
        cmd += ["--convert_timeout_s", str(timeout)]
    if stop_file:
        cmd += ["--stop_file", stop_file]
    if deadline:
        cmd += ["--deadline", str(deadline)]
    cmd += ["--", sys.executable, child_py, log, json.dumps(plan), str(rc)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        rec = json.load(open(recp, encoding="utf-8"))
    except FileNotFoundError:
        rec = {}
    return r.returncode, rec, t0, time.time(), log


U1 = "Loading {ROOT}/IsaacLab/usd_20261013_190000_1234/go2.usd"
U2 = "Loading {ROOT}/IsaacLab/usd_20261013_190001_5678/go2.usd"
try:
    rc, rec, _, _, log = slot("t1", [[0.2, U1], [0.8, DONE], [0.5, "train"]])
    check("T1 one run: exit 0, one USD folder under its own root, released at the scene line, attempt recorded",
          (rc, rec.get("usd_final"), rec.get("state_at_release"), rec.get("usd_outside_root"), rec.get("attempt")),
          (0, ["20261013_190000_1234"], "scene_built", [], "att-t1"))

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
    second = rb if ra.get("lock_wait_s", 0) <= rb.get("lock_wait_s", 0) else ra
    check("T2 two runs at once: both exit 0 and the second waited for the first's scene line", (res["a"][0], res["b"][0], second.get("lock_wait_s", 0) >= 1.5), (0, 0, True))

    R = os.path.join(TMP, "shared_reg.json")
    rc1 = slot("r1", [[0.1, U2], [0.2, DONE]], case="t3b_a", registry=R, scan=False)[0]
    rc2 = slot("r2", [[0.1, U2], [0.2, DONE], [1.0, "rest"]], case="t3b_b", registry=R, scan=False)[0]
    check("T3b registry alone: the same folder id in another run is caught, 96", (rc1, rc2), (0, 96))
    rc1 = slot("s1", [[0.1, U1], [0.2, DONE]], case="t3c", registry=os.path.join(TMP, "reg_s1.json"))[0]
    rc2 = slot("s2", [[0.1, U1], [0.2, DONE], [1.0, "rest"]], case="t3c", registry=os.path.join(TMP, "reg_s2.json"))[0]
    check("T3c log scan alone: a log in the scanned dir naming the folder is caught, 96", (rc1, rc2), (0, 96))

    rc, rec, _, _, _ = slot("t4", [[0.3, U1], [0.3, "Traceback (most recent call last)"]], rc=1)
    check("T4 a child that dies before the scene line: its exit code, released at exit", (rc, rec.get("state_at_release")), (1, "exited"))
    check("T5 exit 0 with no USD folder in the log: 95", slot("t5", [[0.2, "no usd"], [0.2, DONE]])[0], 95)
    check("T5b exit 0 with two USD folders in the log: 95", slot("t5b", [[0.2, U1], [0.2, DONE], [0.2, U2]])[0], 95)
    rc, rec, t0, t1, _ = slot("t6", [[0.2, U1], [30, DONE]], timeout=2)
    check("T6 no scene line within the limit: child ended, 97, well before its 30 s", (rc, rec.get("state_at_release"), t1 - t0 < 20), (97, "convert_timeout", True))
    d7 = os.path.join(TMP, "t7")
    os.makedirs(d7, exist_ok=True)
    open(os.path.join(d7, "t7.log"), "w").write("Loading C:/old/IsaacLab/usd_20261013_100000_1/go2.usd\n" + DONE + "\n")
    rc, rec, _, _, _ = slot("t7", [[1.5, U1], [0.2, DONE]], case="t7")
    check("T7 an old log with a scene line is moved aside first; the slot waits for the new one",
          (rc, rec.get("hold_s", 0) >= 1.4, "moved_old_log" in rec, rec.get("usd_final")), (0, True, True, ["20261013_190000_1234"]))

    # T8 · ASTRA 17b 2.2 counterexample: the scene line comes first, the folder (already used by another run) 1.2 s later
    R8 = os.path.join(TMP, "reg8.json")
    json.dump({"20261013_190000_1234": "C:/other/run.log"}, open(R8, "w"))
    rc, rec, _, _, _ = slot("t8", [[0.2, DONE], [1.2, U1], [0.5, "rest"]], case="t8", registry=R8)
    check("T8 (17b 2.2) scene line before the folder: the lock waits for the folder, the conflict is caught, 96",
          (rc, rec.get("usd_at_release"), sorted(rec.get("conflicts", {}))), (96, ["20261013_190000_1234"], ["20261013_190000_1234"]))
    rc, rec, _, _, _ = slot("t9", [[0.2, "Loading C:/tmp/IsaacLab/usd_20261013_190002_9/go2.usd"], [0.2, DONE]])
    check("T9 a USD folder outside this run's root (isolation not applied): 94", (rc, rec.get("usd_outside_root")), (94, ["20261013_190002_9"]))
    sf = os.path.join(TMP, "STOP")
    open(sf, "w").close()
    rc, rec, _, _, log = slot("t10", [[0.1, U1], [0.1, DONE]], stop_file=sf)
    check("T10 a stop file before the lock: not launched, 98", (rc, os.path.exists(log + ".launched")), (98, False))
    os.remove(sf)
    rc, rec, _, _, log = slot("t11", [[0.1, U1], [0.1, DONE]], deadline=time.time() - 5)
    check("T11 a deadline already passed: not launched, 98", (rc, os.path.exists(log + ".launched")), (98, False))
    # T12: the lock is busy; a stop file appears while waiting
    L12 = os.path.join(TMP, "lock12")
    busy = {}

    def holder():
        busy["r"] = slot("h", [[0.1, U1], [0.1, DONE.replace("scene", "SCENE")], [4.0, "rest"]], case="t12h", lock=L12)
    th = threading.Thread(target=holder)
    th.start()
    time.sleep(1.0)
    sf12 = os.path.join(TMP, "STOP12")
    threading.Timer(1.5, lambda: open(sf12, "w").close()).start()
    rc, rec, _, _, log = slot("w", [[0.1, U2], [0.1, DONE]], case="t12w", lock=L12, stop_file=sf12)
    th.join()
    check("T12 a stop file while waiting for a busy lock: not launched, 98", (rc, os.path.exists(log + ".launched")), (98, False))
    rc, rec, _, _, log = slot("t13", [[0.2, U1], [0.2, DONE]])
    check("T13 the child gets this run's own USD root in FOOTHOLD_USD_ROOT", open(log + ".launched").read().replace("\\", "/").lower().endswith("/usd/t13"), True)
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
