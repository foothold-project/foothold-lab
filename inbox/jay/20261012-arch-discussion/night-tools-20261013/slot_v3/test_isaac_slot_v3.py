"""Known-answer tests for isaac_slot_v3.py (lead 세션 · Claude 하위 작업 · 2026-10-13 밤 · ASTRA 17c §2.2 · §5 counterexamples kept).
Fake children are CPU processes that write the watched log (and <root>/assigned.jsonl, as usd_isolate_run does) like gpu_guard + Isaac.
Every lock, registry and log lives in a fresh folder under the system temp dir; the real _eval/slot is never opened.
ISAAC_SLOT_SCRIPT may point at a mutated copy. SLOT_V3_ONLY=T1,A1 runs only those checks. Exit 1 when any check fails.
Expected values are written by hand (paths through os.path only), never by calling the code under test."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import psutil

SCRIPT = os.environ.get("ISAAC_SLOT_SCRIPT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "isaac_slot_v3.py"))
ONLY = {x for x in os.environ.get("SLOT_V3_ONLY", "").split(",") if x}
TMP = tempfile.mkdtemp(prefix="slot3_")
DONE = "[INFO]: Time taken for scene creation: 1.0 s"
K1, K2 = "20261013_190000_1234", "20261013_190001_5678"
U1 = "Loading {ROOT}/IsaacLab/usd_%s/go2.usd" % K1
U2 = "Loading {ROOT}/IsaacLab/usd_%s/go2.usd" % K2
AS1 = "@ASSIGN {ROOT}/IsaacLab/usd_%s" % K1
AS2 = "@ASSIGN {ROOT}/IsaacLab/usd_%s" % K2
HINT = "2026-10-13T09:59:04Z [8,496ms] [Warning] [isaacsim.asset.importer.urdf] The path x-effect is not a valid usd path"
fails = []

CHILD = r'''
import sys, time, json, os
log, plan, rc = sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3])
root = os.environ.get("FOOTHOLD_USD_ROOT", "NOROOT")
open(log + ".launched", "w").write(root)
open(log + ".pid", "w").write(str(os.getpid()))
f = open(log, "w", encoding="utf-8")
for d, line in plan:
    time.sleep(d)
    line = line.replace("{ROOTW}", root.upper().replace("/", "\\")).replace("{ROOT}", root)
    if line.startswith("@ASSIGN "):
        os.makedirs(root, exist_ok=True)
        with open(os.path.join(root, "assigned.jsonl"), "a", encoding="utf-8") as g:
            g.write(json.dumps({"usd_dir": line[8:], "kind": "assigned"}) + "\n")
        continue
    if line.startswith("@MKDIR "):
        os.makedirs(line[7:], exist_ok=True)
        continue
    if line == "@REFUSED":  # what usd_isolate_run_v3 writes when it refuses a conversion past FOOTHOLD_EXPECT_CONVERSIONS
        os.makedirs(root, exist_ok=True)
        with open(os.path.join(root, "assigned.jsonl"), "a", encoding="utf-8") as g:
            g.write(json.dumps({"usd_dir": None, "kind": "refused_unexpected_conversion", "n": 1}) + "\n")
        continue
    f.write(line + "\n"); f.flush()
f.close()
open(log + ".finished", "w").write("1")
sys.exit(rc)
'''
child_py = os.path.join(TMP, "child.py")
open(child_py, "w").write(CHILD)
# For the end-to-end checks (17d 2.6): the real launcher, a fake isaaclab converter that copies the real __init__ order and writes
# under FAKE_TMP like Isaac's /tmp default, and a script that converts N times, prints the folder like Isaac's log, then the scene line.
ISO = os.environ.get("USD_ISOLATE_SCRIPT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "usd_isolate_run_v3.py"))
FAKE_CONV = '''
import os, random
from datetime import datetime


class AssetConverterBase:
    def __init__(self, cfg):
        cfg.validate()
        if not os.path.isfile(cfg.asset_path):
            raise ValueError(f"The asset path does not exist: {cfg.asset_path}")
        self.cfg = cfg
        if cfg.usd_dir is None:
            time_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._usd_dir = f"{os.environ['FAKE_TMP']}/IsaacLab/usd_{time_tag}_{random.randrange(10000)}"
        else:
            self._usd_dir = cfg.usd_dir
        os.makedirs(self.usd_dir, exist_ok=True)
        with open(os.path.join(self.usd_dir, "go2.usd"), "w") as f:
            f.write("usd")

    @property
    def usd_dir(self):
        return self._usd_dir
'''
INTEG = '''
import os, random, sys, time
log, n, tail = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
random.seed(7)
open(log + ".pid", "w").write(str(os.getpid()))
f = open(log, "w", encoding="utf-8")
def w(s):
    f.write(s + "\\n"); f.flush()
w("start")
from isaaclab.sim.converters.asset_converter_base import AssetConverterBase
class Cfg:
    def __init__(self):
        self.asset_path = os.environ["FAKE_ASSET"]
        self.usd_dir = None
    def validate(self):
        pass
c = Cfg()
try:
    for i in range(n):
        o = AssetConverterBase(c)
        w("Loading " + o.usd_dir + "/go2.usd")
except Exception as ex:
    w("Traceback (most recent call last):")
    w(type(ex).__name__ + ": " + str(ex))
    f.close()
    sys.exit(1)
w("[INFO]: Time taken for scene creation: 1.0 s")
time.sleep(tail)
w("done")
f.close()
open(log + ".finished", "w").write("1")
'''
_pk = os.path.join(TMP, "pkg", "isaaclab")
for _sub in ("", "sim", os.path.join("sim", "converters")):
    os.makedirs(os.path.join(_pk, _sub), exist_ok=True)
    open(os.path.join(_pk, _sub, "__init__.py"), "w").close()
open(os.path.join(_pk, "sim", "converters", "asset_converter_base.py"), "w").write(FAKE_CONV)
open(os.path.join(TMP, "go2.urdf"), "w").write("<robot/>")
integ_py = os.path.join(TMP, "integ_child.py")
open(integ_py, "w").write(INTEG)


def want(name):
    return not ONLY or name in ONLY


def check(name, got, exp):
    ok = got == exp
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:300], "want", repr(exp)[:200], flush=True)
    if not ok:
        fails.append(name)


def cpath(*parts):
    """Hand-made canonical form: absolute, case-folded, / separators."""
    return os.path.normcase(os.path.abspath(os.path.join(*parts))).replace("\\", "/")


def slot(name, plan, rc=0, timeout=None, case=None, registry=None, lock=None, scan=True, stop_file="", deadline=0.0, scan_dirs=None,
         expect=None, integ=None):
    """integ=(conversions, tail seconds): the child is the real usd_isolate_run_v3 launcher around a script that converts with a fake
    isaaclab package (as Isaac would), instead of the plan-driven fake child."""
    d = os.path.join(TMP, case or name)
    os.makedirs(d, exist_ok=True)
    log = os.path.join(d, name + ".log")
    recp = os.path.join(d, name + ".slot.json")
    sd = scan_dirs if scan_dirs is not None else (d if scan else "")
    cmd = [sys.executable, SCRIPT, "--watch_log", log, "--record", recp, "--usd_root", os.path.join(d, "usd", name), "--attempt", "att-" + name,
           "--lock", lock or os.path.join(d, "lock"), "--registry", registry or os.path.join(d, "reg.json"), "--scan_dirs", sd]
    if timeout:
        cmd += ["--convert_timeout_s", str(timeout)]
    if stop_file:
        cmd += ["--stop_file", stop_file]
    if deadline:
        cmd += ["--deadline", str(deadline)]
    if expect is not None:
        cmd += ["--expect_conversions", expect]
    env = dict(os.environ)
    if integ:
        cmd += ["--", sys.executable, "-B", ISO, integ_py, log, str(integ[0]), str(integ[1])]
        env.update(PYTHONPATH=os.path.join(TMP, "pkg"), FAKE_TMP=os.path.join(d, "faketmp"), FAKE_ASSET=os.path.join(TMP, "go2.urdf"),
                   PYTHONDONTWRITEBYTECODE="1")
    else:
        cmd += ["--", sys.executable, child_py, log, json.dumps(plan), str(rc)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    try:
        rec = json.load(open(recp, encoding="utf-8"))
    except FileNotFoundError:
        rec = {}
    return r.returncode, rec, t0, time.time(), log, d


def mine(d, name, k=K1):
    return cpath(d, "usd", name) + "/isaaclab/usd_" + k


def jload(p):
    """a registry as a dict; {} when it is missing or unreadable (a mutant must fail a check, not crash the test)."""
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_mod():
    spec = importlib.util.spec_from_file_location("slot_v3_under_test", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


LONG = [30, "rest (a long run that must not be reached)"]
try:
    if want("T1"):
        rc, rec, _, _, log, d = slot("t1", [[0.1, AS1], [0.1, U1], [0.5, DONE], [0.3, "train"]])
        reg = jload(os.path.join(d, "reg.json"))
        check("T1 one run: exit 0, its one folder (absolute) under its own root, released at the scene line, attempt, registry keyed by the absolute path",
              (rc, rec.get("usd_final"), rec.get("state_at_release"), rec.get("usd_outside_root"), rec.get("usd_unassigned"), rec.get("attempt"), sorted(reg)),
              (0, [mine(d, "t1")], "scene_built", [], [], "att-t1", [mine(d, "t1")]))

    if want("T2"):
        res = {}

        def go(k, a_, u):
            res[k] = slot(k, [[0.1, "start"], [0.1, a_], [1.4, u], [0.3, DONE], [2.0, "rest"]], case="t2")
        th = [threading.Thread(target=go, args=("a", AS1, U1)), threading.Thread(target=go, args=("b", AS2, U2))]
        for t in th:
            t.start()
            time.sleep(0.2)
        for t in th:
            t.join()
        ra, rb = res["a"][1], res["b"][1]
        second = rb if ra.get("lock_wait_s", 0) <= rb.get("lock_wait_s", 0) else ra
        check("T2 two runs at once: both exit 0 and the second waited for the first's scene line",
              (res["a"][0], res["b"][0], second.get("lock_wait_s", 0) >= 1.5), (0, 0, True))

    if want("T3a"):
        R = os.path.join(TMP, "shared_reg_3a.json")
        r1 = slot("r1", [[0.1, AS2], [0.1, U2], [0.2, DONE]], case="t3a_a", registry=R, scan=False)
        r2 = slot("r2", [[0.1, AS2], [0.1, U2], [0.2, DONE], [0.5, "rest"]], case="t3a_b", registry=R, scan=False)
        reg = jload(R)
        check("T3a (17c 5) the same basename under two different absolute roots is not a conflict: both 0, two absolute registry keys",
              (r1[0], r2[0], sorted(reg)), (0, 0, sorted([mine(r1[5], "r1", K2), mine(r2[5], "r2", K2)])))

    if want("T3b"):
        d = os.path.join(TMP, "t3b")
        os.makedirs(d)
        R = os.path.join(d, "reg_seed.json")
        json.dump({mine(d, "t3b"): "c:/other/run.log"}, open(R, "w"))
        rc, rec, *_ = slot("t3b", [[0.1, AS1], [0.1, U1], [0.2, DONE], [0.5, "rest"]], registry=R, scan=False)
        check("T3b a registry entry naming this run's exact folder for another log: 96", (rc, sorted(rec.get("conflicts", {}))), (96, [mine(d, "t3b")]))

    if want("T3c"):
        d = os.path.join(TMP, "t3c")
        os.makedirs(d)
        open(os.path.join(d, "other.log"), "w").write("Loading %s/go2.usd\n" % mine(d, "s2"))
        rc, rec, *_ = slot("s2", [[0.1, AS1], [0.1, U1], [0.2, DONE], [0.5, "rest"]], case="t3c")
        d2 = os.path.join(TMP, "t3c2")
        os.makedirs(d2)
        open(os.path.join(d2, "other.log"), "w").write("Loading C:/elsewhere/IsaacLab/usd_%s/go2.usd\n" % K1)
        rc2, rec2, *_ = slot("s3", [[0.1, AS1], [0.1, U1], [0.2, DONE]], case="t3c2")
        check("T3c log scan: another log naming this exact folder is 96; one naming the same basename under another root is not",
              (rc, sorted(rec.get("conflicts", {})), rc2, rec2.get("conflicts")), (96, [mine(d, "s2")], 0, {}))

    if want("T3d"):
        d = os.path.join(TMP, "t3d")
        os.makedirs(os.path.join(d, "attempts", "uncr_x.20261013-190000"))
        open(os.path.join(d, "attempts", "uncr_x.20261013-190000", "uncr_x.log"), "w").write("@%s/go2.usd@\n" % mine(d, "t3d"))
        rc, rec, *_ = slot("t3d", [[0.1, AS1], [0.1, U1], [0.2, DONE], [0.5, "rest"]])
        check("T3d (17c 5) a log under attempts/<tag>.<time>/ naming this exact folder: 96", (rc, sorted(rec.get("conflicts", {}))), (96, [mine(d, "t3d")]))

    if want("T3e"):
        d = os.path.join(TMP, "t3e")
        os.makedirs(os.path.join(d, "_attempts"))
        open(os.path.join(d, "_attempts", "cmdr_x.log.20261013-190000"), "w").write("@%s/go2.usd@\n" % mine(d, "t3e"))
        rc, rec, *_ = slot("t3e", [[0.1, AS1], [0.1, U1], [0.2, DONE], [0.5, "rest"]])
        check("T3e a moved log under _attempts/ (night shell layout) naming this exact folder: 96", (rc, sorted(rec.get("conflicts", {}))), (96, [mine(d, "t3e")]))

    if want("T4"):
        rc, rec, *_ = slot("t4", [[0.3, AS1], [0.0, U1], [0.3, "Traceback (most recent call last)"]], rc=1)
        check("T4 a child that dies before the scene line: its exit code, released at exit", (rc, rec.get("state_at_release")), (1, "exited"))
    if want("T5"):
        check("T5 exit 0 with no USD folder in the log: 95", slot("t5", [[0.2, "no usd"], [0.2, DONE]])[0], 95)
    if want("T5b"):
        check("T5b exit 0 with two USD folders (both assigned, both inside): 95", slot("t5b", [[0.1, AS1], [0.1, AS2], [0.1, U1], [0.2, DONE], [0.2, U2]])[0], 95)
    if want("T6"):
        rc, rec, t0, t1, *_ = slot("t6", [[0.1, AS1], [0.1, U1], [30, DONE]], timeout=2)
        check("T6 no scene line within the limit: child ended, 97, well before its 30 s", (rc, rec.get("state_at_release"), t1 - t0 < 20), (97, "convert_timeout", True))
    if want("T7"):
        d7 = os.path.join(TMP, "t7")
        os.makedirs(d7, exist_ok=True)
        open(os.path.join(d7, "t7.log"), "w").write("Loading C:/old/IsaacLab/usd_20261013_100000_1/go2.usd\n" + DONE + "\n")
        rc, rec, _, _, _, d = slot("t7", [[1.5, AS1], [0.0, U1], [0.2, DONE]], case="t7", scan=False)
        check("T7 an old log with a scene line is moved aside first; the slot waits for the new one",
              (rc, rec.get("hold_s", 0) >= 1.4, "moved_old_log" in rec, rec.get("usd_final")), (0, True, True, [mine(d, "t7")]))

    if want("T8"):
        d = os.path.join(TMP, "t8")
        os.makedirs(d)
        R8 = os.path.join(d, "reg8.json")
        json.dump({mine(d, "t8"): "c:/other/run.log"}, open(R8, "w"))
        rc, rec, *_ = slot("t8", [[0.1, AS1], [0.1, DONE], [1.2, U1], [0.5, "rest"]], registry=R8)
        check("T8 (17b 2.2) scene line before the folder: the lock waits for the folder, the conflict is caught, 96",
              (rc, rec.get("usd_at_release"), sorted(rec.get("conflicts", {}))), (96, [mine(d, "t8")], [mine(d, "t8")]))
    if want("T9"):
        rc, rec, *_ = slot("t9", [[0.2, "Loading C:/tmp/IsaacLab/usd_20261013_190002_9/go2.usd"], [0.2, DONE]])
        check("T9 a USD folder outside this run's root (isolation not applied): 94", (rc, rec.get("usd_outside_root")), (94, ["c:/tmp/isaaclab/usd_20261013_190002_9"]))
    if want("T9b"):
        rc, rec, *_ = slot("t9b", [[0.2, "(recomposing stage on stage @/tmp/IsaacLab/usd_20261013_185115_9514/go2.usd@ <00000211D>)"], [0.2, DONE]])
        check("T9b the real 18:51 form, a drive-less /tmp path: resolved on the current drive, outside, 94",
              (rc, rec.get("usd_outside_root")), (94, [cpath("/tmp/IsaacLab/usd_20261013_185115_9514")]))
    if want("T10"):
        sf = os.path.join(TMP, "STOP")
        open(sf, "w").close()
        rc, rec, _, _, log, _ = slot("t10", [[0.1, AS1], [0.1, U1], [0.1, DONE]], stop_file=sf)
        check("T10 a stop file before the lock: not launched, 98", (rc, os.path.exists(log + ".launched")), (98, False))
        os.remove(sf)
    if want("T11"):
        rc, rec, _, _, log, _ = slot("t11", [[0.1, AS1], [0.1, U1], [0.1, DONE]], deadline=time.time() - 5)
        check("T11 a deadline already passed: not launched, 98", (rc, os.path.exists(log + ".launched")), (98, False))
    if want("T12"):
        L12 = os.path.join(TMP, "lock12")
        busy = {}

        def holder():
            busy["r"] = slot("h", [[0.1, AS1], [0.1, U1], [0.1, DONE.replace("scene", "SCENE")], [4.0, "rest"]], case="t12h", lock=L12)
        th = threading.Thread(target=holder)
        th.start()
        time.sleep(1.0)
        sf12 = os.path.join(TMP, "STOP12")
        threading.Timer(1.5, lambda: open(sf12, "w").close()).start()
        rc, rec, _, _, log, _ = slot("w", [[0.1, AS2], [0.1, U2], [0.1, DONE]], case="t12w", lock=L12, stop_file=sf12)
        th.join()
        check("T12 a stop file while waiting for a busy lock: not launched, 98", (rc, os.path.exists(log + ".launched")), (98, False))
    if want("T13"):
        rc, rec, _, _, log, _ = slot("t13", [[0.1, AS1], [0.1, U1], [0.2, DONE]])
        check("T13 the child gets this run's own USD root in FOOTHOLD_USD_ROOT", open(log + ".launched").read().replace("\\", "/").lower().endswith("/usd/t13"), True)
    if want("T14"):
        rc, rec, t0, t1, log, _ = slot("t14", [[0.05, "@MKDIR {ROOT}/assigned.jsonl"], [0.1, U1], [0.3, DONE], [10, "rest"]])
        time.sleep(1.0)
        pid = int(open(log + ".pid").read())
        alive = psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
        check("T14 an internal gate error (assigned.jsonl is a folder): the child is ended, 90, slot_error recorded",
              (rc, "slot_error" in rec, alive, os.path.exists(log + ".finished")), (90, True, False, False))

    # ---- ASTRA 17c 2.2 counterexamples and the new checks ----
    if want("A1"):
        rc, rec, t0, t1, log, d = slot("a1", [[0.1, AS1], [0.1, U1], [0.1, "Loading C:/other/IsaacLab/usd_%s/go2.usd" % K1], [0.3, DONE], LONG])
        check("A1 (17c 2.2) the same basename inside and outside the root: two folders, the outside one listed, 94, stopped at the scene line",
              (rc, rec.get("usd_outside_root"), len(rec.get("usd_final", [])), rec.get("killed", {}).get("at"), t1 - t0 < 15, os.path.exists(log + ".finished")),
              (94, ["c:/other/isaaclab/usd_%s" % K1], 2, "scene_line", True, False))
    if want("A2"):
        rc, rec, t0, t1, log, _ = slot("a2", [[0.2, "Loading C:/tmp/IsaacLab/usd_20261013_190002_9/go2.usd"], [0.2, DONE], LONG])
        check("A2 (17c 2.2) outside the root at the scene line of a long run: ended there, 94, long before its 30 s",
              (rc, rec.get("killed", {}).get("at"), t1 - t0 < 15, os.path.exists(log + ".finished")), (94, "scene_line", True, False))
    if want("A3"):
        rc, rec, t0, t1, log, _ = slot("a3", [[0.1, DONE], [1.0, "Loading C:/tmp/IsaacLab/usd_20261013_190002_9/go2.usd"], LONG])
        check("A3 scene line first, the outside folder 1 s later: the lock waits for it, ended at the scene line, 94",
              (rc, rec.get("usd_at_release"), rec.get("killed", {}).get("at"), t1 - t0 < 15), (94, ["c:/tmp/isaaclab/usd_20261013_190002_9"], "scene_line", True))
    if want("A4"):
        rc, rec, t0, t1, log, d = slot("a4", [[0.1, AS1], [0.1, U1], [0.2, DONE], [3.0, "@ASSIGN C:/late/IsaacLab/usd_20261013_190009_7"],
                                              [0.0, "Loading C:/late/IsaacLab/usd_20261013_190009_7/go2.usd"], LONG])
        check("A4 inside at the scene line, an outside folder 3 s after the release: the watch ends it, 94, long before its 30 s",
              (rc, rec.get("state_at_release"), rec.get("killed", {}).get("at"), t1 - t0 < 20, os.path.exists(log + ".finished")),
              (94, "scene_built", "after_release", True, False))
    if want("A5a"):
        rc, rec, t0, t1, log, d = slot("a5a", [[0.1, U1], [0.2, DONE], LONG])
        check("A5a a folder inside the root but not in assigned.jsonl: 91, ended at the scene line",
              (rc, rec.get("usd_unassigned"), rec.get("killed", {}).get("at"), t1 - t0 < 15), (91, [mine(d, "a5a")], "scene_line", True))
    if want("A5b"):
        rc, rec, _, _, _, d = slot("a5b", [[0.1, AS2], [0.1, U1], [0.2, DONE]])
        check("A5b assigned.jsonl names another folder than the log uses: 91", (rc, rec.get("usd_unassigned")), (91, [mine(d, "a5b")]))
    if want("A5c"):
        rc, rec, *_ = slot("a5c", [[0.1, HINT], [0.2, DONE], [0.2, "rest"]])
        check("A5c an importer line (a conversion ran) with assigned.jsonl empty and no folder printed: 91", (rc, rec.get("hint_without_assigned")), (91, True))
    if want("A5d"):
        rc, rec, t0, t1, log, d = slot("a5d", [[0.1, AS1], [0.1, U1], [0.2, DONE], [3.0, U2], LONG])
        check("A5d a new inside folder after the release that is not in assigned.jsonl: the watch ends it, 91",
              (rc, rec.get("killed", {}).get("at"), rec.get("usd_unassigned"), t1 - t0 < 20), (91, "after_release", [mine(d, "a5d", K2)], True))
    if want("A6"):
        rc, rec, _, _, _, d = slot("a6", [[0.1, "@ASSIGN {ROOT}/../evil/IsaacLab/usd_%s" % K1], [0.1, "Loading {ROOT}/../evil/IsaacLab/usd_%s/go2.usd" % K1],
                                          [0.2, DONE]])
        check("A6 a path that starts with the root text but climbs out with ..: outside, 94",
              (rc, rec.get("usd_outside_root")), (94, [cpath(d, "usd", "evil") + "/isaaclab/usd_" + K1]))
    if want("A7"):
        rc, rec, _, _, _, d = slot("a7", [[0.1, AS1], [0.1, "Loading {ROOTW}\\.\\IsaacLab\\\\usd_%s\\go2.usd" % K1], [0.2, DONE]])
        check("A7 the root printed in upper case, with backslashes, a ./ segment and a doubled separator is still this run's folder: 0",
              (rc, rec.get("usd_final")), (0, [mine(d, "a7")]))
    if want("A8"):
        rc, rec, *_ = slot("a8", [[0.1, AS1], [0.0, "@ASSIGN C:/x/IsaacLab/usd_%s" % K2], [0.1, U1], [0.2, DONE]])
        check("A8 assigned.jsonl holds a folder outside the root (launcher misconfigured): 94", (rc, rec.get("assigned_outside_root")),
              (94, ["c:/x/isaaclab/usd_%s" % K2]))

    # ---- registry under its lock (17c 5) ----
    if want("R1"):
        m = load_mod()
        d = os.path.join(TMP, "r1")
        os.makedirs(d)
        R = os.path.join(d, "reg.json")
        fA, fB = "c:/fake/a/isaaclab/usd_" + K1, "c:/fake/b/isaaclab/usd_" + K1
        mark = os.path.join(d, "b_done")
        bpy = os.path.join(d, "b.py")
        open(bpy, "w").write("import importlib.util, json, sys\n"
                             "s = importlib.util.spec_from_file_location('m', sys.argv[1]); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
                             "out = m.registry_update(sys.argv[2], {sys.argv[3]: sys.argv[4]}, sys.argv[5])\n"
                             "open(sys.argv[6], 'w').write(json.dumps([out[0], out[2]]))\n")
        orig = m._load_registry
        st = {}

        def slow_load(path):
            out = orig(path)
            if "proc" not in st:  # A has read; B tries its whole update now
                st["proc"] = subprocess.Popen([sys.executable, bpy, SCRIPT, R, fB, K1, "c:/b.log", mark])
                t0 = time.time()
                while time.time() - t0 < 4 and not os.path.exists(mark):
                    time.sleep(0.05)
                st["b_during_a"] = os.path.exists(mark)
            return out
        m._load_registry = slow_load
        outA = m.registry_update(R, {fA: K1}, "c:/a.log")
        st["proc"].wait(timeout=60)
        final = jload(R)
        check("R1 (17c 5) A reads, B updates, A writes: B waits for A's lock and both entries stay (no lost update)",
              (st.get("b_during_a"), sorted(final.items()), outA[2]), (False, sorted([(fA, "c:/a.log"), (fB, "c:/b.log")]), ""))
    if want("R3"):
        m = load_mod()
        d = os.path.join(TMP, "r3")
        os.makedirs(d)
        R = os.path.join(d, "reg.json")
        os.makedirs(R + ".tmp")
        fA = "c:/fake/a/isaaclab/usd_" + K1
        out = m.registry_update(R, {fA: K1}, "c:/a.log")
        check("R3 (17c 5) another writer's <registry>.tmp is present: the update uses its own temp name, succeeds and leaves no temp file",
              (out[2], sorted(json.load(open(R, encoding="utf-8"))) if os.path.exists(R) else None, os.path.isdir(R + ".tmp"),
               sorted(x for x in os.listdir(d) if x.endswith(".tmp"))),
              ("", [fA], True, ["reg.json.tmp"]))
    if want("R4"):
        d = os.path.join(TMP, "r4")
        os.makedirs(d)
        R = os.path.join(d, "reg_bad.json")
        open(R, "w").write("{not json")
        rc, rec, t0, t1, log, _ = slot("r4", [[0.1, AS1], [0.1, U1], [0.2, DONE], LONG], registry=R)
        check("R4 a registry that is not JSON: not overwritten, 90, the child ended at the scene line",
              (rc, open(R).read(), rec.get("killed", {}).get("at"), t1 - t0 < 15), (90, "{not json", "scene_line", True))
    if want("R5"):
        d = os.path.join(TMP, "r5")
        os.makedirs(d)
        other = os.path.join(d, "v2_other.log")
        open(other, "w").write("@%s/go2.usd@\n" % mine(d, "r5"))
        R = os.path.join(d, "reg_v2.json")
        json.dump({K1: cpath(other)}, open(R, "w"))
        rc, rec, *_ = slot("r5", [[0.1, AS1], [0.1, U1], [0.2, DONE], [0.5, "rest"]], registry=R, scan=False)
        d2 = os.path.join(TMP, "r5b")
        os.makedirs(d2)
        other2 = os.path.join(d2, "v2_other.log")
        open(other2, "w").write("@C:/elsewhere/IsaacLab/usd_%s/go2.usd@\n" % K1)
        R2 = os.path.join(d2, "reg_v2.json")
        json.dump({K1: cpath(other2)}, open(R2, "w"))
        rc2, rec2, *_ = slot("r5b", [[0.1, AS1], [0.1, U1], [0.2, DONE]], registry=R2, scan=False)
        check("R5 a v2 basename registry entry is resolved through its log: that log naming this exact folder is 96, naming another root is 0",
              (rc, sorted(rec.get("conflicts", {})), rc2), (96, [mine(d, "r5")], 0))

    # ---- ASTRA 17d 2.6: an expected number of conversions (0 for runs that must not convert) ----
    if want("E1"):
        rc, rec, t0, t1, log, d = slot("e1", [[0.1, "start"], [0.2, DONE], [0.3, "rest"]], expect="0", timeout=10)
        check("E1 (17d 2.6) expect 0 and no conversion: released at the scene line without waiting for a folder, zero folders is 0 (not 95)",
              (rc, rec.get("state_at_release"), rec.get("usd_final"), rec.get("hold_s", 99) < 5, open(log + ".launched").read() != ""), (0, "scene_built", [], True, True))
    if want("E2"):
        rc, rec, t0, t1, log, d = slot("e2", [[0.1, "@REFUSED"], [0.2, DONE], LONG], expect="0")
        check("E2 (17d 2.6) expect 0 and the launcher's refusal line: 89, ended at the scene line", (rc, rec.get("killed", {}).get("at"), t1 - t0 < 15),
              (89, "scene_line", True))
    if want("E2b"):
        rc, rec, *_ = slot("e2b", [[0.1, AS1], [0.1, U1], [0.2, DONE]], expect="0")
        check("E2b (17d 2.6) expect 0 and a conversion that went through (assigned, inside the root): 89, not accepted", (rc, rec.get("expect_violation")), (89, True))
    if want("E2c"):
        rc, rec, *_ = slot("e2c", [[0.1, HINT], [0.2, DONE], [0.2, "rest"]], expect="0")
        check("E2c (17d 2.6) expect 0 and only an importer line (a conversion ran, nothing recorded): 89", (rc, rec.get("expect_violation")), (89, True))
    if want("E3"):
        rc, rec, t0, t1, log, d = slot("e3", None, expect="0", integ=(1, 30))
        r = os.path.join(d, "usd", "e3")
        check("E3 (17d 2.6) end to end, expect 0, the child converts anyway: the real launcher refuses before any write (no fake /tmp, no "
              "<root>/IsaacLab), the slot says 89",
              (rc, os.path.exists(os.path.join(d, "faketmp")), os.path.exists(os.path.join(r, "IsaacLab")), [x.get("kind") for x in [json.loads(z) for z in
               open(os.path.join(r, "assigned.jsonl"))]] if os.path.exists(os.path.join(r, "assigned.jsonl")) else None, t1 - t0 < 20),
              (89, False, False, ["refused_unexpected_conversion"], True))
    if want("E4"):
        rc, rec, t0, t1, log, d = slot("e4", None, expect="1", integ=(1, 0.5))
        check("E4 end to end, expect 1, one conversion: 0, its folder under the root (_5305)",
              (rc, [x[-5:] for x in rec.get("usd_final", [])], all(x.startswith(mine(d, "e4")[:-len(K1)]) for x in rec.get("usd_final", []))), (0, ["_5305"], True))
    if want("E5"):
        rc, rec, t0, t1, log, d = slot("e5", None, expect="1", integ=(2, 30))
        r = os.path.join(d, "usd", "e5")
        made = sorted(os.listdir(os.path.join(r, "IsaacLab"))) if os.path.isdir(os.path.join(r, "IsaacLab")) else []
        check("E5 (17d 2.6) end to end, expect 1, the same cfg converted twice: the second is refused before any write (one folder made), 89",
              (rc, [x[-5:] for x in made], os.path.exists(os.path.join(d, "faketmp")), t1 - t0 < 20), (89, ["_5305"], False, True))
    if want("E6"):
        rc, rec, t0, t1, log, d = slot("e6", [[0.1, AS1], [0.1, U1], [0.2, DONE], [3.0, "@REFUSED"], LONG])
        check("E6 (17d 2.6) a refusal written after the release, with nothing new in the log: the watch sees assigned.jsonl change, ends it, 89",
              (rc, rec.get("killed", {}).get("at"), t1 - t0 < 20), (89, "after_release", True))
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
