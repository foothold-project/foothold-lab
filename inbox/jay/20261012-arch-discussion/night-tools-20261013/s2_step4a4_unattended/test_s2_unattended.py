"""CPU tests for the unattended watchdog v2, gate and launcher. Only processes started here are signalled.

Known answers are written by hand. A healthy chain is never killed; a hung one is killed within
the stale window and its Job Object child dies with it; a watcher problem stops the gate; nothing
starts when the contract, hashes or READY handshake do not match.
Output convention: one line per check, 'PASS label' or 'FAIL label'.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
A3_DIR = Path(os.environ.get("S2_A3_DIR", str(HERE.parent / "s2_step4a3")))
os.environ["S2_A3_DIR"] = str(A3_DIR)
sys.path.insert(0, str(HERE))
import s2_unattended_gate as g  # noqa: E402
import s2_watchdog_v2 as wd  # noqa: E402

PY = sys.executable
GATE = HERE / "gate_harness.py"
WATCHDOG = HERE / "s2_watchdog_v2.py"
LAUNCHER = HERE / "s2_unattended_launch.py"
G3 = "G3 READY with wrong %s is refused (%s), no work"
FAILS = []
SPAWNED = []


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label, flush=True)
    if not ok:
        FAILS.append(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spawn(argv, **kw):
    proc = subprocess.Popen([str(x) for x in argv], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
    SPAWNED.append(proc)
    time.sleep(0.4)
    return proc, psutil.Process(proc.pid).create_time()


def gone(pid, ct=None, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            p = psutil.Process(pid)
            if ct is not None and abs(p.create_time() - ct) > 0.05:
                return True
            if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.2)
    return False


def wait_file(path, timeout=30.0):
    end = time.time() + timeout
    while time.time() < end:
        if Path(path).is_file():
            try:
                return json.loads(Path(path).read_text(encoding="utf-8"))
            except ValueError:
                pass
        time.sleep(0.2)
    return None


class Beater(threading.Thread):
    """Writes the status file the way the supervisor does, until told to stop or until `life` passes."""

    def __init__(self, path, chain_id, life=None, value=None, chain_override=None):
        super().__init__(daemon=True)
        self.path, self.chain_id, self.life, self.value, self.chain_override = path, chain_id, life, value, chain_override
        self.halt = threading.Event()

    def run(self):
        t0 = time.time()
        while not self.halt.is_set() and (self.life is None or time.time() - t0 < self.life):
            hb = time.time() if self.value is None else self.value
            body = {"chain_id": self.chain_override or self.chain_id, "state": "RUNNING", "heartbeat_epoch": hb}
            text = json.dumps(body) if not (isinstance(hb, float) and hb != hb) else \
                '{"chain_id": "%s", "state": "RUNNING", "heartbeat_epoch": NaN}' % (self.chain_override or self.chain_id)
            if isinstance(hb, str):
                text = json.dumps(body)
            Path(self.path).write_text(text, encoding="utf-8")
            time.sleep(0.1)


def run_watch(tmp, victim_pid, victim_ct, *, chain="c1", hard_in=30.0, mono_budget=30.0, stale=0.8, grace=1.0,
              poll=0.05, log=None, factory=psutil.Process, blind_limit=0.5, clock=time.time, kill_grace=5.0, family_wait=2.0):
    watch_dir = tmp / "w"
    watch_dir.mkdir(exist_ok=True)
    try:
        rc = wd.watch(pid=victim_pid, create_time=victim_ct, chain_id=chain, status_path=tmp / "status.json",
                      watch_dir=watch_dir, hard_deadline_epoch=time.time() + hard_in, mono_budget_s=mono_budget,
                      stale_after_s=stale, startup_grace_s=grace, poll_s=poll,
                      log_path=log or (tmp / "wd.log"), own_sha256="x" * 64, kill_grace_s=kill_grace,
                      blind_limit_s=blind_limit, family_wait_s=family_wait, process_factory=factory, clock=clock)
    except Exception as ex:
        print("   watch() raised", repr(ex), flush=True)
        rc = -999
    receipt = wait_file(watch_dir / "kill_receipt.json", 0.1)
    hb = wait_file(watch_dir / "watchdog_hb.json", 0.1)
    ready = wait_file(watch_dir / "ready.json", 0.1)
    events = []
    logp = log or (tmp / "wd.log")
    if Path(logp).is_file():
        events = [json.loads(x)["event"] for x in Path(logp).read_text(encoding="utf-8").splitlines()]
    return rc, receipt, hb, ready, events


VICTIM_CHILD = (
    "import subprocess,sys,time\n"
    "c=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(120)'])\n"
    "open(sys.argv[1],'w').write(str(c.pid))\n"
    "time.sleep(120)\n")


def unit_watchdog():
    tmp = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    sleeper = ["-B", "-c", "import time; time.sleep(120)"]
    decoy, _ = spawn([PY, *sleeper])
    # W1 healthy victim ending by itself
    victim, ct = spawn([PY, "-B", "-c", "import time; time.sleep(2.0)"])
    b = Beater(tmp / "status.json", "c1")
    b.start()
    rc, receipt, hb, ready, ev = run_watch(tmp, victim.pid, ct, stale=1.5)
    b.halt.set()
    check("W1 healthy victim ending by itself is left alone", rc == 0 and receipt is None and "watched_ended_by_itself" in ev)
    check("W1 READY file carries chain, watchdog hash and gate identity",
          bool(ready) and ready["state"] == "READY" and ready["chain_id"] == "c1" and ready["gate_pid"] == victim.pid
          and ready["watchdog_sha256"] == "x" * 64)
    check("W1 decoy untouched", decoy.poll() is None)
    # W2 hung (heartbeat stops)
    tmp2 = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    victim, ct = spawn([PY, *sleeper])
    b = Beater(tmp2 / "status.json", "c1", life=0.6)
    b.start()
    t0 = time.time()
    rc, receipt, hb, ready, ev = run_watch(tmp2, victim.pid, ct, stale=0.8)
    check("W2 hung victim killed by stale heartbeat", rc == 0 and bool(receipt) and receipt["reason"] == "heartbeat_stale"
          and receipt["gate_killed"] is True and victim.poll() is not None)
    check("W2 kill within stale window plus margin", time.time() - t0 < 6.0)
    check("W2 final heartbeat says KILLED", bool(hb) and hb["state"] == "KILLED")
    # W3 absolute hard deadline with fresh heartbeats
    tmp3 = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    victim, ct = spawn([PY, *sleeper])
    b = Beater(tmp3 / "status.json", "c1")
    b.start()
    rc, receipt, hb, ready, ev = run_watch(tmp3, victim.pid, ct, hard_in=1.0, stale=5.0)
    b.halt.set()
    check("W3 hard deadline kills with fresh heartbeat (wall or its monotonic mirror)",
          rc == 0 and bool(receipt) and receipt["reason"] in ("hard_deadline", "mono_deadline"))
    # W3b the wall clock jumps forward past the absolute deadline while the monotonic budget is still long
    t3b = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    victim, ct = spawn([PY, *sleeper])
    t_zero = time.time()
    b = Beater(t3b / "status.json", "c1", life=5.0)
    b.start()
    rc, receipt, hb, ready, ev = run_watch(t3b, victim.pid, ct, hard_in=600.0, mono_budget=600.0, stale=50.0,
                                           clock=lambda: t_zero + (100000.0 if time.time() - t_zero > 1.0 else 0.0) + (time.time() - t_zero))
    b.halt.set()
    check("W3b a forward wall-clock jump past the absolute deadline triggers hard_deadline",
          rc == 0 and bool(receipt) and receipt["reason"] == "hard_deadline")
    # W4 monotonic budget with a frozen wall clock
    tmp4 = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    victim, ct = spawn([PY, *sleeper])
    frozen = time.time()
    b = Beater(tmp4 / "status.json", "c1", life=3.0)
    b.start()
    rc, receipt, hb, ready, ev = run_watch(tmp4, victim.pid, ct, hard_in=100.0, mono_budget=0.8, stale=5.0,
                                           clock=lambda: frozen)
    b.halt.set()
    check("W4 monotonic budget kills when the wall clock never advances", rc == 0 and bool(receipt) and receipt["reason"] == "mono_deadline")
    # W5 future heartbeat / W6 NaN / W7 wrong chain / W8 string and bool heartbeats never count as progress
    for label, kw in (("W5 future-dated", dict(value=time.time() + 3600)),
                      ("W6 NaN", dict(value=float("nan"))),
                      ("W7 other chain", dict(chain_override="other")),
                      ("W8 string", dict(value="123456")),
                      ("W8b bool", dict(value=True))):
        t = Path(tempfile.mkdtemp(prefix="s2u_w_"))
        victim, ct = spawn([PY, *sleeper])
        b = Beater(t / "status.json", "c1", **kw)
        b.start()
        rc, receipt, hb, ready, ev = run_watch(t, victim.pid, ct, stale=5.0, grace=1.0)
        b.halt.set()
        check(label + " heartbeat is rejected and the victim is killed after the startup grace",
              rc == 0 and bool(receipt) and receipt["reason"] == "no_valid_status_after_startup_grace" and victim.poll() is not None)
    # W9 log failure must not stop the kill
    t = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    victim, ct = spawn([PY, *sleeper])
    b = Beater(t / "status.json", "c1")
    b.start()
    bad_log = t / "logdir"
    bad_log.mkdir()
    rc, receipt, hb, ready, ev = run_watch(t, victim.pid, ct, hard_in=1.0, stale=5.0, log=bad_log)
    b.halt.set()
    check("W9 unwritable log does not block the kill", rc == 0 and victim.poll() is not None and bool(receipt))
    # W10 AccessDenied at start is blind, not 'ended by itself'
    class Denied:
        def __init__(self, *a, **k):
            pass

        def create_time(self):
            raise psutil.AccessDenied(pid=1)

        def is_running(self):
            raise psutil.AccessDenied(pid=1)

    t = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    rc, receipt, hb, ready, ev = run_watch(t, os.getpid(), psutil.Process().create_time(), factory=Denied)
    check("W10 AccessDenied at start is BLIND exit 6", rc == 6 and bool(hb) and hb["state"] == "BLIND"
          and "watched_ended_by_itself" not in ev)
    # W11 AccessDenied after a normal start: blind too long -> 6
    t = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    victim, ct = spawn([PY, *sleeper])
    real = psutil.Process(victim.pid)
    state = {"n": 0}

    class FlipsToDenied:
        def __init__(self, pid):
            self.pid = pid

        def create_time(self):
            state["n"] += 1
            if state["n"] > 2:
                raise psutil.AccessDenied(pid=self.pid)
            return real.create_time()

        def is_running(self):
            return True

        def status(self):
            return psutil.STATUS_RUNNING

        def children(self, recursive=True):
            return []

    b = Beater(t / "status.json", "c1")
    b.start()
    rc, receipt, hb, ready, ev = run_watch(t, victim.pid, ct, factory=FlipsToDenied, blind_limit=0.5, stale=5.0)
    b.halt.set()
    check("W11 AccessDenied after start becomes blind exit 6 (never reported as ended by itself)",
          rc == 6 and "watched_ended_by_itself" not in ev and "blind_too_long" in ev and victim.poll() is None)
    # W12 kill AccessDenied -> exit 2 with a receipt note
    t = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    victim, ct = spawn([PY, *sleeper])
    real = psutil.Process(victim.pid)

    class KillDenied:
        def __init__(self, pid):
            self.pid = pid

        def create_time(self):
            return real.create_time()

        def is_running(self):
            return True

        def status(self):
            return psutil.STATUS_RUNNING

        def children(self, recursive=True):
            return []

        def kill(self):
            raise psutil.AccessDenied(pid=self.pid)

    rc, receipt, hb, ready, ev = run_watch(t, victim.pid, ct, factory=KillDenied, hard_in=1.0, stale=5.0)
    check("W12 kill AccessDenied exits 2 and records it", rc == 2 and bool(receipt) and receipt.get("note") == "kill_access_denied"
          and "kill_access_denied" in ev and victim.poll() is None)
    # W13 identity mismatch at start: nothing signalled
    t = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    victim, ct = spawn([PY, *sleeper])
    rc, receipt, hb, ready, ev = run_watch(t, victim.pid, ct + 5.0)
    check("W13 wrong creation time signals nothing", rc == 3 and victim.poll() is None and "identity_mismatch_at_start" in ev)
    # W14 bad arguments incl. the NaN cases the A3 watchdog kept polling on
    for label, kw in (("W14a NaN stale", dict(stale=float("nan"))), ("W14b past deadline", dict(hard_in=-5.0)),
                      ("W14c NaN poll", dict(poll=float("nan")))):
        t = Path(tempfile.mkdtemp(prefix="s2u_w_"))
        victim, ct = spawn([PY, *sleeper])
        rc, receipt, hb, ready, ev = run_watch(t, victim.pid, ct, **kw)
        check(label + " is a bad argument and signals nothing", rc == 4 and victim.poll() is None)
    # W15 family: a child that is NOT in a Job object is still cleaned up and reported
    t = Path(tempfile.mkdtemp(prefix="s2u_w_"))
    script = t / "victim_with_child.py"
    script.write_text(VICTIM_CHILD, encoding="utf-8")
    child_file = t / "child_pid.txt"
    victim, ct = spawn([PY, "-B", script, child_file])
    time.sleep(1.0)
    child_pid = int(child_file.read_text())
    b = Beater(t / "status.json", "c1", life=0.5)
    b.start()
    rc, receipt, hb, ready, ev = run_watch(t, victim.pid, ct, stale=0.8)
    check("W15 descendant seen before the kill is reported and force-killed when it survives",
          rc == 0 and bool(receipt) and any(row[0] == child_pid for row in receipt["descendants_before_kill"])
          and receipt["family_empty"] is True and gone(child_pid, timeout=5))
    check("W15 decoy untouched at the end", decoy.poll() is None)


class FakeProc:
    """A stand-in process for identity / family tests. Records kills; becomes NoSuchProcess once killed."""

    def __init__(self, pid, ct, *, children=None, ct_exc=None, children_exc=None, kill_log=None, killable=True):
        self.pid, self._ct, self._children = pid, ct, children or []
        self._ct_exc, self._children_exc, self.kill_log, self.killable = ct_exc, children_exc, kill_log, killable
        self.dead = False

    def create_time(self):
        if self.dead:
            raise psutil.NoSuchProcess(self.pid)
        if self._ct_exc is not None:
            raise self._ct_exc(pid=self.pid)
        return self._ct

    def is_running(self):
        return not self.dead

    def status(self):
        return psutil.STATUS_RUNNING

    def children(self, recursive=True):
        if self._children_exc is not None:
            raise self._children_exc(pid=self.pid)
        return list(self._children)

    def kill(self):
        if self.kill_log is not None:
            self.kill_log.append(self.pid)
        if self.killable:
            self.dead = True

    def wait(self, timeout=None):
        return 0


def unit_watchdog_family():
    """17z P1: identity is never guessed; unverified family members are never signalled and never 'empty'."""
    def run_fake(gate, factory, hard_in=0.6):
        tmp = Path(tempfile.mkdtemp(prefix="s2u_f_"))
        rc, receipt, hb, ready, ev = run_watch(tmp, gate.pid, gate._ct, factory=factory, hard_in=hard_in,
                                               stale=5.0, grace=30.0, poll=0.05, kill_grace=1.0)
        return rc, receipt

    # W18 descendant creation time unreadable at the snapshot; the same pid later answers with another process
    log = []
    child = FakeProc(777, 2.0, ct_exc=psutil.AccessDenied)
    gate = FakeProc(100, 1.0, children=[child], kill_log=log)
    later = FakeProc(777, 999.0, kill_log=log)
    rc, receipt = run_fake(gate, lambda pid: gate if pid == 100 else later)
    check("W18 descendant with unreadable creation time is never signalled, family is UNVERIFIED, exit 2",
          rc == 2 and 777 not in log and bool(receipt) and receipt["family_status"] == "unverified"
          and receipt["family_empty"] is False and receipt["descendant_snapshot_complete"] is False)
    # W19 snapshot read the creation time, but the identity check afterwards is AccessDenied
    log = []
    child = FakeProc(777, 2.0)
    gate = FakeProc(100, 1.0, children=[child], kill_log=log)
    denied = FakeProc(777, 2.0, ct_exc=psutil.AccessDenied, kill_log=log)
    rc, receipt = run_fake(gate, lambda pid: gate if pid == 100 else denied)
    check("W19 identity AccessDenied after the snapshot: no signal, never 'family_empty', exit 2",
          rc == 2 and 777 not in log and bool(receipt) and receipt["family_status"] == "unverified"
          and receipt["family_empty"] is False)
    # W20 the descendant listing itself is AccessDenied
    log = []
    gate = FakeProc(100, 1.0, children_exc=psutil.AccessDenied, kill_log=log)
    rc, receipt = run_fake(gate, lambda pid: gate)
    check("W20 unreadable descendant listing is UNVERIFIED (not empty), exit 2",
          rc == 2 and bool(receipt) and receipt["family_status"] == "unverified" and receipt["family_empty"] is False)
    # W21 positive control: a verified descendant that survives is killed after re-verification and the family is empty
    log = []
    child = FakeProc(777, 2.0, kill_log=log)
    gate = FakeProc(100, 1.0, children=[child], kill_log=log)
    rc, receipt = run_fake(gate, lambda pid: gate if pid == 100 else child)
    check("W21 verified surviving descendant is killed and the family is proven empty, exit 0",
          rc == 0 and 777 in log and bool(receipt) and receipt["family_status"] == "empty"
          and receipt["descendants_force_killed"] == [777])
    # W22 reused pid (different creation time) is another process: not signalled, family empty
    log = []
    child = FakeProc(777, 2.0)
    gate = FakeProc(100, 1.0, children=[child], kill_log=log)
    reused = FakeProc(777, 999.0, kill_log=log)
    rc, receipt = run_fake(gate, lambda pid: gate if pid == 100 else reused)
    check("W22 reused pid is not signalled and counts as gone",
          rc == 0 and 777 not in log and bool(receipt) and receipt["family_status"] == "empty")
    # W25 race: matched at the snapshot and the first classification, but another process owns the pid by the
    # time the signal would be sent (identity must be re-verified immediately before the signal)
    log = []
    counter = {"n": 0}
    child = FakeProc(777, 2.0)
    gate = FakeProc(100, 1.0, children=[child], kill_log=log)

    def race_factory(pid):
        if pid == 100:
            return gate
        counter["n"] += 1
        return FakeProc(777, 2.0 if counter["n"] == 1 else 999.0, kill_log=log)

    tmp = Path(tempfile.mkdtemp(prefix="s2u_f_"))
    rc, receipt, hb, ready, ev = run_watch(tmp, 100, 1.0, factory=race_factory, hard_in=0.6, stale=5.0, grace=30.0,
                                           poll=0.05, kill_grace=1.0, family_wait=0.0)
    check("W25 pid taken over between classification and signal: identity re-verified, nothing signalled",
          rc == 0 and 777 not in log and bool(receipt) and receipt["family_status"] == "empty")
    # W23 a hung status read cannot delay the kill: the worker thread blocks, the deciding thread still kills
    tmp = Path(tempfile.mkdtemp(prefix="s2u_f_"))
    victim, ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)"])
    original = wd.read_status

    def hanging_read(*a, **k):
        time.sleep(60)

    wd.read_status = hanging_read
    try:
        t0 = time.time()
        rc, receipt, hb, ready, ev = run_watch(tmp, victim.pid, ct, stale=0.8, grace=1.5)
    finally:
        wd.read_status = original
    check("W23 hung status read: victim still killed within seconds (io_stalled or startup grace)",
          rc == 0 and bool(receipt) and receipt["reason"] in ("io_stalled", "no_valid_status_after_startup_grace")
          and victim.poll() is not None and time.time() - t0 < 8.0)
    # W24 a hung heartbeat write cannot delay the kill either
    tmp = Path(tempfile.mkdtemp(prefix="s2u_f_"))
    victim, ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)"])
    original_write = wd.atomic_write
    b = Beater(tmp / "status.json", "c1")
    b.start()

    def hanging_write(path, value):
        if "watchdog_hb" in str(path):
            time.sleep(60)
        return original_write(path, value)

    wd.atomic_write = hanging_write
    try:
        t0 = time.time()
        rc, receipt, hb, ready, ev = run_watch(tmp, victim.pid, ct, stale=0.8, hard_in=30.0)
    finally:
        wd.atomic_write = original_write
        b.halt.set()
    check("W24 hung heartbeat write: victim still killed (io_stalled), receipt written",
          rc == 0 and bool(receipt) and receipt["reason"] == "io_stalled" and victim.poll() is not None
          and time.time() - t0 < 8.0)


class ArgvProxy:
    """Delegates to a real psutil.Process but reports the watchdog command line the gate expects."""

    def __init__(self, real, argv):
        self._real, self._argv = real, argv

    def cmdline(self):
        return self._argv

    def __getattr__(self, name):
        return getattr(self._real, name)


def proxy_factory(helper_pid, argv):
    def factory(pid):
        real = psutil.Process(pid)
        return ArgvProxy(real, argv) if pid == helper_pid else real
    return factory


def make_env(root: Path, name: str, *, mode="healthy", life=2.0, job_child=False, prelaunch="GO", ready_timeout=3,
             stale=3, grace=10, poll=0.3, monitor_stale=3, stop_grace=5, extra=10, max_wall=60, deadline_in=200,
             gate_path=GATE, watchdog_path=WATCHDOG, launcher_path=LAUNCHER):
    base = root / name
    (base / "ctl").mkdir(parents=True)
    (base / "marker").mkdir()
    bundle = base / "bundle"
    bundle.mkdir()
    (bundle / "one.py").write_text("print(1)\n", encoding="utf-8")
    (bundle / "two.py").write_text("print(2)\n", encoding="utf-8")
    (bundle / "SHA256SUMS.txt").write_text("".join("%s *%s\n" % (sha(bundle / n), n) for n in ("one.py", "two.py")),
                                           encoding="utf-8")
    now = time.time()
    outer = {"contract_version": "a4u", "observer_mode": "unattended", "chain_id": "chain-" + name,
             "attempt": "one", "purpose": "stage0_information_only", "python_path": PY,
             "status_path": str(base / "ctl" / "status.json"), "stop_path": str(base / "ctl" / "STOP"),
             "deadline_epoch": now + deadline_in, "max_wall_s": max_wall,
             "fake": {"mode": mode, "life_s": life, "job_child": job_child, "prelaunch": prelaunch,
                      "marker_dir": str(base / "marker")},
             "unattended": {"gate_path": str(gate_path), "gate_sha256": sha(gate_path),
                            "watchdog_path": str(watchdog_path), "watchdog_sha256": sha(watchdog_path),
                            "launcher_path": str(launcher_path), "launcher_sha256": sha(launcher_path),
                            "bundle_dir": str(bundle), "bundle_list_sha256": sha(bundle / "SHA256SUMS.txt"),
                            "watch_dir": str(base / "watch"), "ready_timeout_s": ready_timeout,
                            "stale_after_s": stale, "startup_grace_s": grace, "poll_s": poll,
                            "mono_budget_s": max_wall + 60, "hard_deadline_extra_s": extra,
                            "monitor_stale_s": monitor_stale, "stop_grace_s": stop_grace}}
    return base, outer, good_approval(outer)


def good_approval(outer):
    return {"status": "APPROVED", "chain_id": outer["chain_id"], "by": "test-fixture", "scope": g.APPROVAL_SCOPE,
            "decision_basis": {"verdict_file": "TEST-VERDICT.md", "verdict_sha256": "a" * 64,
                               "verdict_line": "UNATTENDED_GO test fixture"},
            "manifest_sha256": g.sha_of(outer), "expires_epoch": outer["deadline_epoch"] + 300}


def write_pair(base, outer, approval=None):
    approval = approval or good_approval(outer)
    m, a = base / "manifest.json", base / "approval.json"
    m.write_text(json.dumps(outer), encoding="utf-8")
    a.write_text(json.dumps(approval), encoding="utf-8")
    return m, a


def fakes(base, prelaunch_status="GO", verdict="PASS", stop_aware=True, life=0.0):
    calls = {"prelaunch": 0, "run": 0}

    def prelaunch(m, a):
        calls["prelaunch"] += 1
        calls["inner_manifest"], calls["inner_approval"] = m, a
        return {"status": prelaunch_status}

    def run(m, a):
        calls["run"] += 1
        t0 = time.time()
        while time.time() - t0 < life:
            if stop_aware and Path(m["stop_path"]).exists():
                return {"verdict": "HOLD"}
            time.sleep(0.1)
        return {"verdict": verdict}

    return prelaunch, run, calls


def gate_inproc(base, outer, approval, **kw):
    prelaunch, run, calls = fakes(base, **{k: v for k, v in kw.items() if k in ("prelaunch_status", "verdict", "stop_aware", "life")})
    (base / "watch").mkdir(exist_ok=True)
    extra = {k: v for k, v in kw.items() if k in ("die", "process_factory")}
    extra.setdefault("die", lambda code: calls.setdefault("hard_exit_codes", []).append(code))
    watch_dir = kw.get("watch_dir", base / "watch")
    try:
        rc = g.run_gate(outer, approval, watch_dir=watch_dir, gate_file=GATE, watchdog_file=WATCHDOG,
                        prelaunch_fn=prelaunch, run_fn=run, monitor_poll_s=0.2, **extra)
    except Exception as ex:
        print("   run_gate raised", repr(ex), flush=True)
        rc = -999
    result = wait_file(Path(watch_dir) / "gate_result.json", 0.1) or {}
    return rc, result, calls


def ready_for(b, o, helper, hct, **over):
    """Write a hand-made ready.json for a helper process; return a process factory that reports the exact
    watchdog command line the gate expects for it."""
    block = o["unattended"]
    me = psutil.Process().create_time()
    ready = {"chain_id": o["chain_id"], "state": "READY", "epoch": time.time(), "seq": 1,
             "gate_pid": os.getpid(), "gate_create_time": me, "watchdog_pid": helper.pid,
             "watchdog_create_time": hct, "watchdog_sha256": block["watchdog_sha256"],
             "hard_deadline_epoch": o["deadline_epoch"] + block["hard_deadline_extra_s"],
             "mono_budget_s": block["mono_budget_s"], "stale_after_s": block["stale_after_s"],
             "startup_grace_s": block["startup_grace_s"]}
    ready.update(over)
    (b / "watch").mkdir(exist_ok=True)
    (b / "watch" / "ready.json").write_text(json.dumps(ready), encoding="utf-8")
    argv = g.expected_watchdog_argv(o, block, gate_pid=os.getpid(), gate_create_time=me)
    return proxy_factory(helper.pid, argv), argv


def write_hb(b, o, helper, hct, **over):
    hb = {"chain_id": o["chain_id"], "watchdog_pid": helper.pid, "watchdog_create_time": hct,
          "gate_pid": os.getpid(), "state": "WATCHING", "seq": 2, "epoch": time.time()}
    hb.update(over)
    (b / "watch" / "watchdog_hb.json").write_text(json.dumps(hb), encoding="utf-8")


def unit_gate_contract(root):
    helper, hct = spawn([PY, "-B", "-c", "import time; time.sleep(120)"])
    # no READY file: not ready, and no GPU work function is ever called
    base_nr, outer_nr, appr_nr = make_env(root, "notready", ready_timeout=1)
    t0 = time.time()
    rc, result, calls = gate_inproc(base_nr, outer_nr, appr_nr)
    check("G1 no READY file: gate exits 6 NOT_READY quickly", rc == 6 and (result or {}).get("state") == "NOT_READY" and time.time() - t0 < 6)
    check("G1 no GPU work function called before READY", calls["prelaunch"] == 0 and calls["run"] == 0)
    final = g.FINAL_DEADLINE_EPOCH
    rows = [
        ("observer attended", lambda o, a: o.__setitem__("observer_mode", "attended"), "observer_mode_not_unattended"),
        ("contract version", lambda o, a: o.__setitem__("contract_version", "a2"), "contract_version"),
        ("approval digest", lambda o, a: a.__setitem__("manifest_sha256", "0" * 64), "approval_digest"),
        ("approval expired", lambda o, a: a.__setitem__("expires_epoch", time.time() - 5), "approval_expired"),
        ("approval missing by", lambda o, a: a.__setitem__("by", ""), "approval_missing"),
        ("approval wrong chain", lambda o, a: a.__setitem__("chain_id", "other"), "approval_missing"),
        ("approval wrong scope", lambda o, a: a.__setitem__("scope", "attended_anything"), "approval_scope_or_basis"),
        ("approval basis missing", lambda o, a: a.pop("decision_basis"), "approval_scope_or_basis"),
        ("approval basis short hash", lambda o, a: a["decision_basis"].__setitem__("verdict_sha256", "abc"), "approval_scope_or_basis"),
        ("deadline too near", lambda o, a: o.__setitem__("deadline_epoch", time.time() + 40), "deadline_or_wall_budget"),
        ("final deadline margin", lambda o, a: (o.__setitem__("deadline_epoch", final - 20), a.__setitem__("expires_epoch", final + 300)), "final_deadline_margin"),
        ("ready_timeout out of range", lambda o, a: o["unattended"].__setitem__("ready_timeout_s", 0), "block_value_ready_timeout_s"),
        ("mono budget too small", lambda o, a: o["unattended"].__setitem__("mono_budget_s", 10), "block_value_mono_budget_s"),
        ("string stale", lambda o, a: o["unattended"].__setitem__("stale_after_s", "3"), "block_value_stale_after_s"),
        ("NaN stale cannot be signed", lambda o, a: o["unattended"].__setitem__("stale_after_s", float("nan")), "exception:ValueError"),
        ("gate hash", lambda o, a: o["unattended"].__setitem__("gate_sha256", "0" * 64), "gate_file_hash"),
        ("watchdog hash", lambda o, a: o["unattended"].__setitem__("watchdog_sha256", "0" * 64), "watchdog_file_hash"),
        ("launcher hash", lambda o, a: o["unattended"].__setitem__("launcher_sha256", "0" * 64), "launcher_file_hash"),
        ("bundle list hash", lambda o, a: o["unattended"].__setitem__("bundle_list_sha256", "0" * 64), "bundle_list_hash"),
        ("block key missing", lambda o, a: o["unattended"].pop("watch_dir"), "unattended_block_missing"),
    ]
    for i, (label, change, want) in enumerate(rows):
        b, o, a = make_env(root, "row%d" % i, ready_timeout=1)
        change(o, a)
        if not label.startswith("approval") and "NaN" not in label:
            a["manifest_sha256"] = g.sha_of(o)
        rc, result, calls = gate_inproc(b, o, a)
        check("G2 contract row '%s' -> HOLD_CONTRACT %s, no work" % (label, want),
              rc == 5 and (result or {}).get("state") == "HOLD_CONTRACT" and want in (result or {}).get("reason", "") and calls["prelaunch"] == 0)
    # a CLI --watch-dir that differs from the approved one (17z): refused before anything runs
    b, o, a = make_env(root, "watchdiff", ready_timeout=1)
    other = b / "unsigned_watch"
    other.mkdir()
    rc, result, calls = gate_inproc(b, o, a, watch_dir=other)
    check("G2 CLI watch dir differs from the approved watch dir -> HOLD_CONTRACT, no work",
          rc == 5 and "watch_dir_differs_from_approved" in (result or {}).get("reason", "") and calls["prelaunch"] == 0)
    # bundle file modified after the list was frozen
    b, o, a = make_env(root, "bundlefile", ready_timeout=1)
    (Path(o["unattended"]["bundle_dir"]) / "one.py").write_text("print('tampered')\n", encoding="utf-8")
    rc, result, calls = gate_inproc(b, o, a)
    check("G2 bundle file changed after freeze -> HOLD_CONTRACT", rc == 5 and "bundle_file_hash_one.py" in (result or {}).get("reason", ""))
    # READY validation rows (the 'watchdog' is a helper process whose command line the proxy factory reports)
    rows = [("gate pid", dict(gate_pid=1), "ready_gate_identity"),
            ("gate creation time", dict(gate_create_time=1.0), "ready_gate_identity"),
            ("watchdog hash", dict(watchdog_sha256="0" * 64), "ready_watchdog_hash"),
            ("hard deadline", dict(hard_deadline_epoch=1.0), "ready_param_hard_deadline_epoch"),
            ("mono budget", dict(mono_budget_s=1.0), "ready_param_mono_budget_s"),
            ("stale", dict(stale_after_s=99.0), "ready_param_stale_after_s"),
            ("chain", dict(chain_id="other"), "ready_chain_or_state"),
            ("state", dict(state="STARTING"), "ready_chain_or_state"),
            ("old file", dict(epoch=time.time() - 3600), "ready_not_fresh"),
            ("watchdog pid dead", dict(watchdog_pid=2 ** 22 + 12345), "ready_watchdog_not_alive"),
            ("watchdog ct wrong", dict(watchdog_create_time=hct + 50), "ready_watchdog_not_alive")]
    for label, over, want in rows:
        b, o, a = make_env(root, "rdy_" + label.replace(" ", "_"), ready_timeout=1)
        factory, _argv = ready_for(b, o, helper, hct, **over)
        rc, result, calls = gate_inproc(b, o, a, process_factory=factory)
        check(G3 % (label, want), rc == 6 and want in (result or {}).get("reason", "") and calls["prelaunch"] == 0)
    # exact watchdog command line: any single differing argument is refused
    flags = ("--pid", "--create-time", "--chain-id", "--status-path", "--watch-dir", "--hard-deadline-epoch",
             "--mono-budget-s", "--stale-after-s", "--startup-grace-s", "--poll-s", "--log")
    b0, o0, a0 = make_env(root, "argvbase", ready_timeout=1)
    _f, expected = ready_for(b0, o0, helper, hct)
    variants = [("program", 2)] + [(f, expected.index(f) + 1) for f in flags]
    for name, idx in variants:
        b, o, a = make_env(root, "argv_" + name.strip("-").replace("-", "_"), ready_timeout=1)
        factory, argv = ready_for(b, o, helper, hct)
        tampered = list(argv)
        tampered[idx] = "tampered-value"
        rc, result, calls = gate_inproc(b, o, a, process_factory=proxy_factory(helper.pid, tampered))
        check("G3 watchdog command line with a different %s is refused (ready_watchdog_argv_mismatch), no work" % name,
              rc == 6 and "ready_watchdog_argv_mismatch" in (result or {}).get("reason", "") and calls["prelaunch"] == 0)
    b, o, a = make_env(root, "argv_extra", ready_timeout=1)
    factory, argv = ready_for(b, o, helper, hct)
    rc, result, calls = gate_inproc(b, o, a, process_factory=proxy_factory(helper.pid, argv + ["--extra", "1"]))
    check("G3 watchdog command line with an extra argument is refused", rc == 6 and "ready_watchdog_argv_mismatch" in (result or {}).get("reason", ""))
    # valid READY: derived inner pair, prelaunch then run, exit code from the verdict
    b, o, a = make_env(root, "good")
    factory, _ = ready_for(b, o, helper, hct)
    rc, result, calls = gate_inproc(b, o, a, process_factory=factory)
    inner, inner_a = calls.get("inner_manifest", {}), calls.get("inner_approval", {})
    check("G4 valid READY: prelaunch then run, DONE rc 0", rc == 0 and (result or {}).get("state") == "DONE" and calls["prelaunch"] == 1 and calls["run"] == 1)
    check("G4 inner manifest is attended-shaped and bound to the outer digest",
          inner.get("observer_mode") == "attended" and inner.get("unattended_origin_sha256") == g.sha_of(o)
          and inner_a.get("manifest_sha256") == g.sha_of(inner) and inner_a.get("origin_approval_sha256") == g.sha_of(a)
          and inner_a["expires_epoch"] == a["expires_epoch"])
    b, o, a = make_env(root, "nogo")
    factory, _ = ready_for(b, o, helper, hct)
    rc, result, calls = gate_inproc(b, o, a, prelaunch_status="NO_GO", process_factory=factory)
    check("G5 prelaunch NO_GO stops before run, rc 42", rc == 42 and (result or {}).get("state") == "NO_GO" and calls["run"] == 0)
    b, o, a = make_env(root, "notpass")
    factory, _ = ready_for(b, o, helper, hct)
    rc, result, calls = gate_inproc(b, o, a, verdict="HOLD", process_factory=factory)
    check("G5 non-PASS verdict is rc 42", rc == 42 and (result or {}).get("state") == "DONE")


class HbWriter(threading.Thread):
    """Keeps rewriting watchdog_hb.json with a changing seq, like a live watcher would."""

    def __init__(self, b, o, helper, hct, *, start_seq=2, step=1, cycle=None, period=0.2, **over):
        super().__init__(daemon=True)
        self.args = (b, o, helper, hct)
        self.start_seq, self.step, self.cycle, self.period, self.over = start_seq, step, cycle, period, over
        self.halt = threading.Event()

    def run(self):
        i = 0
        while not self.halt.is_set():
            seq = self.cycle[i % len(self.cycle)] if self.cycle else self.start_seq + self.step * i
            write_hb(*self.args, seq=seq, **self.over)
            i += 1
            time.sleep(self.period)


def unit_gate_monitor(root):
    # watcher process dies while the supervisor runs: STOP file, supervisor stops, rc 71
    b, o, a = make_env(root, "lost", monitor_stale=3)
    helper2, h2ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)"])
    factory, _ = ready_for(b, o, helper2, h2ct)
    write_hb(b, o, helper2, h2ct, seq=2)
    threading.Timer(1.0, helper2.kill).start()
    rc, result, calls = gate_inproc(b, o, a, life=30, process_factory=factory)
    check("G6 watcher death during the run -> STOP file, supervisor stopped, rc 71 WATCHER_LOST",
          rc == 71 and result.get("state") == "WATCHER_LOST" and result.get("watcher_problem") in ("watcher_gone", "watcher_mismatch")
          and Path(o["stop_path"]).exists())
    # a healthy-looking but frozen heartbeat (same valid seq forever) -> stale -> STOP
    # (label, writer kwargs or None for one static file, static kwargs, wanted problem). Invalid inputs are written
    # with a CHANGING value on purpose: they must still never count as progress.
    cases = [
        ("G7 watcher alive but heartbeat frozen", None, dict(seq=2), "watcher_heartbeat_stale"),
        ("G8 watcher reporting BLIND", None, dict(state="BLIND", seq=2), "watcher_state_BLIND"),
        ("G9 heartbeat with a NaN seq is never progress", dict(cycle=[float("nan")]), {}, "watcher_heartbeat_stale"),
        ("G10 heartbeat of another chain is never progress", dict(start_seq=5, chain_id="other-chain"), {}, "watcher_heartbeat_stale"),
        ("G11 heartbeat from another watcher pid is never progress", dict(start_seq=5, watchdog_pid=1), {}, "watcher_heartbeat_stale"),
        ("G12 heartbeat for another gate pid is never progress", dict(start_seq=5, gate_pid=1), {}, "watcher_heartbeat_stale"),
        ("G13 non-monotonic seq (2,3,2,3,...) stops being progress", dict(cycle=[2, 3]), {}, "watcher_heartbeat_stale"),
        ("G14 non-integer seq is never progress", dict(start_seq=2.5), {}, "watcher_heartbeat_stale"),
        ("G15 foreign watcher creation time is never progress", dict(start_seq=5, watchdog_create_time=1.0), {}, "watcher_heartbeat_stale"),
    ]
    for i, (label, writer_kw, static, want) in enumerate(cases):
        b, o, a = make_env(root, "hbcase%d" % i, monitor_stale=3)
        helper3, h3ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)"])
        factory, _ = ready_for(b, o, helper3, h3ct)
        writer = None
        if writer_kw is None:
            write_hb(b, o, helper3, h3ct, **static)
        else:
            writer = HbWriter(b, o, helper3, h3ct, **writer_kw)
            writer.start()
        try:
            rc, result, calls = gate_inproc(b, o, a, life=30, process_factory=factory)
        finally:
            if writer is not None:
                writer.halt.set()
        check("%s -> STOP, rc 71 with %s" % (label, want),
              rc == 71 and result.get("watcher_problem") == want and Path(o["stop_path"]).exists())
    # supervisor ignoring STOP -> hard exit hook after the grace
    b, o, a = make_env(root, "lost2", monitor_stale=3, stop_grace=5)
    helper4, h4ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)"])
    factory, _ = ready_for(b, o, helper4, h4ct)
    write_hb(b, o, helper4, h4ct, seq=2)
    threading.Timer(0.5, helper4.kill).start()
    died = []
    t0 = time.time()
    done = threading.Event()

    def runner():
        gate_inproc(b, o, a, life=9, stop_aware=False, die=lambda code: died.append(code), process_factory=factory)
        done.set()

    th = threading.Thread(target=runner, daemon=True)
    th.start()
    done.wait(30)
    check("G6 supervisor ignoring STOP -> hard exit hook called with 70 after the grace", died == [70] and time.time() - t0 >= 5)


def process_level(root):
    ok_states = ("RUNNING", "FINISHED_OK")
    # P1 healthy chain through the real launcher, gate harness and watchdog
    base, outer, appr = make_env(root, "p1", mode="healthy", life=3.0)
    m, a = write_pair(base, outer, appr)
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)],
                         capture_output=True, text=True, timeout=90)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    check("P1 launcher exit 0 only after the supervisor status was seen", res.returncode == 0 and bool(rec) and rec["state"] in ok_states)
    result = wait_file(base / "watch" / "gate_result.json", 40)
    check("P1 healthy chain finishes DONE rc 0 with fake PASS", bool(result) and result["state"] == "DONE" and result["exit_code"] == 0)
    check("P1 prelaunch and run each called once", (base / "marker" / "prelaunch_called").exists() and (base / "marker" / "run_called").exists())
    time.sleep(2.5)
    log = [json.loads(x)["event"] for x in (base / "watch" / "watchdog.log").read_text(encoding="utf-8").splitlines()]
    check("P1 watchdog saw the gate end by itself and killed nothing", "watched_ended_by_itself" in log and not (base / "watch" / "kill_receipt.json").exists())
    # P2 hung supervisor with a Job Object child: watchdog kills the gate, the Job closes, the child dies
    base, outer, appr = make_env(root, "p2", mode="hang", job_child=True, stale=3, life=60)
    m, a = write_pair(base, outer, appr)
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)],
                         capture_output=True, text=True, timeout=90)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    check("P2 launcher exits before the hang is detected (watchdog outlives its launcher)", res.returncode == 0 and bool(rec))
    receipt = wait_file(base / "watch" / "kill_receipt.json", 40)
    check("P2 hung gate killed by the watchdog with a receipt", bool(receipt) and receipt["reason"] == "heartbeat_stale" and receipt["gate_killed"] is True)
    child = int((base / "marker" / "child_pid").read_text())
    check("P2 Job Object child died with the gate", gone(child, timeout=10))
    check("P2 gate process gone and no PASS result written", gone(rec["gate_pid"], rec["gate_create_time"], 10)
          and not (base / "watch" / "gate_result.json").exists())
    # P3 watcher killed while the gate runs: monitor writes STOP, the supervisor stops, rc 71
    base, outer, appr = make_env(root, "p3", mode="respect_stop", life=120, monitor_stale=3)
    m, a = write_pair(base, outer, appr)
    subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=90)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    time.sleep(2.5)
    psutil.Process(rec["watchdog_pid"]).kill()
    result = wait_file(base / "watch" / "gate_result.json", 30)
    check("P3 watchdog killed -> gate stops its own work with WATCHER_LOST rc 71", bool(result) and result.get("state") == "WATCHER_LOST" and (result or {}).get("exit_code") == 71)
    # P4 watcher killed and supervisor ignores STOP, with a Job child: hard exit takes the child too
    base, outer, appr = make_env(root, "p4", mode="ignore_stop", job_child=True, life=300, monitor_stale=3, stop_grace=5)
    m, a = write_pair(base, outer, appr)
    subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=90)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    time.sleep(2.5)
    child = int((base / "marker" / "child_pid").read_text())
    psutil.Process(rec["watchdog_pid"]).kill()
    check("P4 gate hard-exits after the stop grace when the supervisor ignores STOP", gone(rec["gate_pid"], rec["gate_create_time"], 40))
    check("P4 its Job Object child dies with it", gone(child, timeout=10))
    # P5 watchdog that dies at once: launcher aborts and cleans up only the two processes it created
    dead = root / "dead_watchdog.py"
    dead.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    base, outer, appr = make_env(root, "p5", watchdog_path=dead, ready_timeout=60)
    m, a = write_pair(base, outer, appr)
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=90)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    check("P5 launcher aborts with exit 5 when the watchdog is not ready", res.returncode == 5 and bool(rec) and rec["state"] == "LAUNCH_ABORTED")
    check("P5 the gate it created is gone and no GPU-side marker exists", gone(rec["gate_pid"], rec["gate_create_time"], 10)
          and not (base / "marker" / "run_called").exists())
    # P6 tampered watchdog file after approval: nothing started
    base, outer, appr = make_env(root, "p6")
    m, a = write_pair(base, outer, appr)
    victim = root / "tampered_watchdog.py"
    victim.write_text(WATCHDOG.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    outer["unattended"]["watchdog_path"] = str(victim)
    m.write_text(json.dumps(outer), encoding="utf-8")
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=90)
    check("P6 hash mismatch against the manifest: exit 4, nothing started, no watch dir",
          res.returncode == 4 and not (base / "watch").exists())
    # P7 existing watch dir is refused (a previous run must never be reused)
    base, outer, appr = make_env(root, "p7")
    (base / "watch").mkdir()
    m, a = write_pair(base, outer, appr)
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=90)
    check("P7 existing watch dir: exit 4, nothing started", res.returncode == 4 and not (base / "marker" / "prelaunch_called").exists())
    # P8 the gate alone, no watchdog ever: NOT_READY, no work (the launcher died between the two starts)
    base, outer, appr = make_env(root, "p8", ready_timeout=2)
    m, a = write_pair(base, outer, appr)
    (base / "watch").mkdir()
    res = subprocess.run([PY, "-B", str(GATE), "--manifest", str(m), "--approval", str(a), "--watch-dir", str(base / "watch")],
                         capture_output=True, text=True, timeout=90)
    result = wait_file(base / "watch" / "gate_result.json", 3)
    check("P8 gate without any watchdog: exit 6 NOT_READY and no work", res.returncode == 6 and (result or {}).get("state") == "NOT_READY"
          and not (base / "marker" / "prelaunch_called").exists())
    # P9 the watchdog is READY but the gate refuses the approval: READY alone is not success, launcher aborts (rc 5)
    base, outer, appr = make_env(root, "p9", ready_timeout=5)
    appr["manifest_sha256"] = "0" * 64
    m, a = write_pair(base, outer, appr)
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=90)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    check("P9 READY file but the gate refused the approval: launcher exit 5, LAUNCH_ABORTED, no work",
          res.returncode == 5 and bool(rec) and rec["state"] == "LAUNCH_ABORTED" and "HOLD_CONTRACT" in rec["reason"]
          and not (base / "marker" / "prelaunch_called").exists())
    check("P9 watchdog it started is gone after the abort", gone(rec["watchdog_pid"], rec["watchdog_create_time"], 15))
    # P11 the gate refuses AFTER the READY file exists (prelaunch NO_GO after a delay): READY alone is not success
    base, outer, appr = make_env(root, "p11", ready_timeout=10, prelaunch="NO_GO")
    outer["fake"]["prelaunch_delay_s"] = 1.5
    m, a = write_pair(base, outer, good_approval(outer))
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=90)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    check("P11 gate refuses after READY (NO_GO): launcher waits for it, exit 5, LAUNCH_ABORTED",
          res.returncode == 5 and bool(rec) and rec["state"] == "LAUNCH_ABORTED" and "NO_GO" in rec["reason"]
          and not (base / "marker" / "run_called").exists())
    # P12 the detached children carry the Kit EULA variable (first live attempt died on it)
    import s2_unattended_launch as L2
    out_file = root / "env_probe.txt"
    probe = L2.start_detached([PY, "-B", "-c", "import os; open(%r,'w').write(os.environ.get('OMNI_KIT_ACCEPT_EULA','MISSING')+'|'+os.environ.get('PYTHONUNBUFFERED','MISSING'))" % str(out_file)],
                              cwd=root, log_path=root / "env_probe.log")
    probe.wait(30)
    check("P12 detached start passes OMNI_KIT_ACCEPT_EULA=YES and PYTHONUNBUFFERED=1 to the child",
          out_file.exists() and out_file.read_text() == "YES|1")
    # P10 launcher cleanup signals only through held handles: a decoy with the 'same pid' is untouched
    import s2_unattended_launch as L
    decoy, _ = spawn([PY, "-B", "-c", "import time; time.sleep(120)"])

    class HeldHandle:
        pid = decoy.pid  # a stale/reused pid number must be irrelevant
        killed = False

        def poll(self):
            return None

        def kill(self):
            HeldHandle.killed = True

        def wait(self, timeout=None):
            return 0

    real_process = L.psutil.Process
    L.psutil.Process = lambda *a, **k: (_ for _ in ()).throw(AssertionError("launcher must not look processes up by pid"))
    try:
        outcome = L.kill_created(HeldHandle())
    finally:
        L.psutil.Process = real_process
    check("P10 cleanup kills through the held handle only, never by pid lookup; decoy with that pid untouched",
          outcome == "killed" and HeldHandle.killed and decoy.poll() is None)


def main():
    group = sys.argv[sys.argv.index("--group") + 1] if "--group" in sys.argv else "all"
    root = Path(tempfile.mkdtemp(prefix="s2u_run_"))
    try:
        if group in ("all", "watchdog"):
            unit_watchdog()
            unit_watchdog_family()
        if group in ("all", "gate"):
            unit_gate_contract(root)
            unit_gate_monitor(root)
        if group in ("all", "process"):
            process_level(root)
    finally:
        for p in SPAWNED:
            try:
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass
    print("SUMMARY", "ALL PASS" if not FAILS else "FAIL %s" % FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
