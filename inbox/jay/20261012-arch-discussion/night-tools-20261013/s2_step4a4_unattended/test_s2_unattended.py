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
              poll=0.05, log=None, factory=psutil.Process, blind_limit=0.5, clock=time.time, kill_grace=5.0):
    watch_dir = tmp / "w"
    watch_dir.mkdir(exist_ok=True)
    try:
        rc = wd.watch(pid=victim_pid, create_time=victim_ct, chain_id=chain, status_path=tmp / "status.json",
                      watch_dir=watch_dir, hard_deadline_epoch=time.time() + hard_in, mono_budget_s=mono_budget,
                      stale_after_s=stale, startup_grace_s=grace, poll_s=poll,
                      log_path=log or (tmp / "wd.log"), own_sha256="x" * 64, kill_grace_s=kill_grace,
                      blind_limit_s=blind_limit, family_wait_s=2.0, process_factory=factory, clock=clock)
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
    approval = {"status": "APPROVED", "chain_id": outer["chain_id"], "by": "test-fixture",
                "manifest_sha256": g.sha_of(outer), "expires_epoch": outer["deadline_epoch"] + 300}
    return base, outer, approval


def write_pair(base, outer, approval=None):
    approval = approval or {"status": "APPROVED", "chain_id": outer["chain_id"], "by": "test-fixture",
                            "manifest_sha256": g.sha_of(outer), "expires_epoch": outer["deadline_epoch"] + 300}
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
    try:
        rc = g.run_gate(outer, approval, watch_dir=base / "watch", gate_file=GATE, watchdog_file=WATCHDOG,
                        prelaunch_fn=prelaunch, run_fn=run, monitor_poll_s=0.2, **extra)
    except Exception as ex:
        print("   run_gate raised", repr(ex), flush=True)
        rc = -999
    result = wait_file(base / "watch" / "gate_result.json", 0.1) or {}
    return rc, result, calls


def unit_gate_contract(root):
    base, outer, appr = make_env(root, "ok")
    (base / "watch").mkdir()
    helper, hct = spawn([PY, "-B", "-c", "import time; time.sleep(120)", str(WATCHDOG)])
    # no READY file: not ready, and no GPU work function is ever called
    base_nr, outer_nr, appr_nr = make_env(root, "notready", ready_timeout=1)
    t0 = time.time()
    rc, result, calls = gate_inproc(base_nr, outer_nr, appr_nr)
    check("G1 no READY file: gate exits 6 NOT_READY quickly", rc == 6 and (result or {}).get("state") == "NOT_READY" and time.time() - t0 < 6)
    check("G1 no GPU work function called before READY", calls["prelaunch"] == 0 and calls["run"] == 0)
    # contract tamper table: every row must stop before READY and before any call
    def mutate_block(key, value):
        def f(o, a):
            o["unattended"][key] = value
        return f

    rows = [
        ("observer attended", lambda o, a: o.__setitem__("observer_mode", "attended"), "observer_mode_not_unattended"),
        ("contract version", lambda o, a: o.__setitem__("contract_version", "a2"), "contract_version"),
        ("approval digest", lambda o, a: a.__setitem__("manifest_sha256", "0" * 64), "approval_digest"),
        ("approval expired", lambda o, a: a.__setitem__("expires_epoch", time.time() - 5), "approval_expired"),
        ("approval missing by", lambda o, a: a.__setitem__("by", ""), "approval_missing"),
        ("approval wrong chain", lambda o, a: a.__setitem__("chain_id", "other"), "approval_missing"),
        ("deadline too near", lambda o, a: o.__setitem__("deadline_epoch", time.time() + 40), "deadline_or_wall_budget"),
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
        if label not in ("approval digest",) and not label.startswith("approval") and "NaN" not in label:
            a["manifest_sha256"] = g.sha_of(o)
        rc, result, calls = gate_inproc(b, o, a)
        check("G2 contract row '%s' -> HOLD_CONTRACT %s, no work" % (label, want),
              rc == 5 and (result or {}).get("state") == "HOLD_CONTRACT" and want in (result or {}).get("reason", "") and calls["prelaunch"] == 0)
    # bundle file modified after the list was frozen
    b, o, a = make_env(root, "bundlefile", ready_timeout=1)
    (Path(o["unattended"]["bundle_dir"]) / "one.py").write_text("print('tampered')\n", encoding="utf-8")
    rc, result, calls = gate_inproc(b, o, a)
    check("G2 bundle file changed after freeze -> HOLD_CONTRACT", rc == 5 and "bundle_file_hash_one.py" in (result or {}).get("reason", ""))
    # READY validation rows: hand-made ready.json using a helper process as the 'watchdog'
    def ready_for(b, o, **over):
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
        ready_for(b, o, **over)
        prelaunch, run, calls = fakes(b)
        rc = g.run_gate(o, a, watch_dir=b / "watch", gate_file=GATE, watchdog_file=WATCHDOG, prelaunch_fn=prelaunch,
                        run_fn=run, monitor_poll_s=0.2)
        result = wait_file(b / "watch" / "gate_result.json", 0.1)
        check("G3 READY with wrong %s is refused (%s), no work" % (label, want),
              rc == 6 and want in (result or {}).get("reason", "") and calls["prelaunch"] == 0)
    wrong, wct = spawn([PY, "-B", "-c", "import time; time.sleep(120)"])
    b, o, a = make_env(root, "rdy_prog", ready_timeout=1)
    ready_for(b, o, watchdog_pid=wrong.pid, watchdog_create_time=wct)
    prelaunch, run, calls = fakes(b)
    rc = g.run_gate(o, a, watch_dir=b / "watch", gate_file=GATE, watchdog_file=WATCHDOG, prelaunch_fn=prelaunch,
                    run_fn=run, monitor_poll_s=0.2)
    result = wait_file(b / "watch" / "gate_result.json", 0.1)
    check("G3 READY from a process that is not running the watchdog program is refused",
          rc == 6 and "ready_watchdog_wrong_program" in (result or {}).get("reason", "") and calls["prelaunch"] == 0)
    # valid READY: derived inner pair, prelaunch then run, exit code from the verdict
    b, o, a = make_env(root, "good")
    ready_for(b, o)
    rc, result, calls = gate_inproc(b, o, a)
    inner, inner_a = calls.get("inner_manifest", {}), calls.get("inner_approval", {})
    check("G4 valid READY: prelaunch then run, DONE rc 0", rc == 0 and (result or {}).get("state") == "DONE" and calls["prelaunch"] == 1 and calls["run"] == 1)
    check("G4 inner manifest is attended-shaped and bound to the outer digest",
          inner.get("observer_mode") == "attended" and inner.get("unattended_origin_sha256") == g.sha_of(o)
          and inner_a.get("manifest_sha256") == g.sha_of(inner) and inner_a.get("origin_approval_sha256") == g.sha_of(a)
          and inner_a["expires_epoch"] == a["expires_epoch"])
    b, o, a = make_env(root, "nogo")
    ready_for(b, o)
    rc, result, calls = gate_inproc(b, o, a, prelaunch_status="NO_GO")
    check("G5 prelaunch NO_GO stops before run, rc 42", rc == 42 and (result or {}).get("state") == "NO_GO" and calls["run"] == 0)
    b, o, a = make_env(root, "notpass")
    ready_for(b, o)
    rc, result, calls = gate_inproc(b, o, a, verdict="HOLD")
    check("G5 non-PASS verdict is rc 42", rc == 42 and (result or {}).get("state") == "DONE")
    # watcher lost while the supervisor runs: STOP written, supervisor stops, rc 71
    b, o, a = make_env(root, "lost", monitor_stale=3)
    helper2, h2ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)", str(WATCHDOG)])
    block = o["unattended"]
    ready_for(b, o, watchdog_pid=helper2.pid, watchdog_create_time=h2ct)
    threading.Timer(1.0, helper2.kill).start()
    rc, result, calls = gate_inproc(b, o, a, life=30)
    check("G6 watcher death during the run -> STOP file, supervisor stopped, rc 71 WATCHER_LOST",
          rc == 71 and result.get("state") == "WATCHER_LOST" and result.get("watcher_problem") in ("watcher_gone", "watcher_mismatch")
          and Path(o["stop_path"]).exists())
    # watcher alive but its heartbeat file never changes -> stale -> STOP
    b, o, a = make_env(root, "frozen", monitor_stale=3)
    helper4, h4ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)", str(WATCHDOG)])
    ready_for(b, o, watchdog_pid=helper4.pid, watchdog_create_time=h4ct)
    (b / "watch" / "watchdog_hb.json").write_text(json.dumps({"state": "WATCHING", "seq": 1}), encoding="utf-8")
    rc, result, calls = gate_inproc(b, o, a, life=30)
    check("G7 watcher alive but heartbeat frozen -> STOP, rc 71 with watcher_heartbeat_stale",
          rc == 71 and result.get("watcher_problem") == "watcher_heartbeat_stale" and Path(o["stop_path"]).exists())
    # watcher reports BLIND -> STOP
    b, o, a = make_env(root, "blind", monitor_stale=3)
    helper5, h5ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)", str(WATCHDOG)])
    ready_for(b, o, watchdog_pid=helper5.pid, watchdog_create_time=h5ct)
    (b / "watch" / "watchdog_hb.json").write_text(json.dumps({"state": "BLIND", "seq": 1}), encoding="utf-8")
    rc, result, calls = gate_inproc(b, o, a, life=30)
    check("G8 watcher reporting BLIND -> STOP, rc 71 with watcher_state_BLIND",
          rc == 71 and result.get("watcher_problem") == "watcher_state_BLIND" and Path(o["stop_path"]).exists())
    # watcher gone and the supervisor ignores STOP -> hard exit hook
    b, o, a = make_env(root, "lost2", monitor_stale=3, stop_grace=5)
    helper3, h3ct = spawn([PY, "-B", "-c", "import time; time.sleep(120)", str(WATCHDOG)])
    ready_for(b, o, watchdog_pid=helper3.pid, watchdog_create_time=h3ct)
    threading.Timer(0.5, helper3.kill).start()
    died = []
    t0 = time.time()
    done = threading.Event()

    def runner():
        gate_inproc(b, o, a, life=9, stop_aware=False, die=lambda code: died.append(code))
        done.set()

    th = threading.Thread(target=runner, daemon=True)
    th.start()
    done.wait(30)
    check("G6 supervisor ignoring STOP -> hard exit hook called with 70 after the grace", died == [70] and time.time() - t0 >= 5)


def process_level(root):
    # P1 healthy chain through the real launcher, gate harness and watchdog
    base, outer, appr = make_env(root, "p1", mode="healthy", life=3.0)
    m, a = write_pair(base, outer, appr)
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)],
                         capture_output=True, text=True, timeout=60)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    check("P1 launcher exit 0 and READY seen", res.returncode == 0 and bool(rec) and rec["state"] == "LAUNCHED")
    result = wait_file(base / "watch" / "gate_result.json", 40)
    check("P1 healthy chain finishes DONE rc 0 with fake PASS", bool(result) and (result or {}).get("state") == "DONE" and (result or {}).get("exit_code") == 0)
    check("P1 prelaunch and run each called once", (base / "marker" / "prelaunch_called").exists() and (base / "marker" / "run_called").exists())
    time.sleep(2.0)
    log = [json.loads(x)["event"] for x in (base / "watch" / "watchdog.log").read_text(encoding="utf-8").splitlines()]
    check("P1 watchdog saw the gate end by itself and killed nothing", "watched_ended_by_itself" in log and not (base / "watch" / "kill_receipt.json").exists())
    # P2 hung supervisor with a Job Object child: watchdog kills the gate, the Job closes, the child dies
    base, outer, appr = make_env(root, "p2", mode="hang", job_child=True, stale=3, life=60)
    m, a = write_pair(base, outer, appr)
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)],
                         capture_output=True, text=True, timeout=60)
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
    subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=60)
    rec = wait_file(base / "watch" / "launch_record.json", 5)
    time.sleep(2.5)
    psutil.Process(rec["watchdog_pid"]).kill()
    result = wait_file(base / "watch" / "gate_result.json", 30)
    check("P3 watchdog killed -> gate stops its own work with WATCHER_LOST rc 71", bool(result) and result.get("state") == "WATCHER_LOST" and (result or {}).get("exit_code") == 71)
    # P4 watcher killed and supervisor ignores STOP, with a Job child: hard exit takes the child too
    base, outer, appr = make_env(root, "p4", mode="ignore_stop", job_child=True, life=300, monitor_stale=3, stop_grace=5)
    m, a = write_pair(base, outer, appr)
    subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=60)
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
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=60)
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
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=60)
    check("P6 hash mismatch against the manifest: exit 4, nothing started, no watch dir",
          res.returncode == 4 and not (base / "watch").exists())
    # P7 existing watch dir is refused (a previous run must never be reused)
    base, outer, appr = make_env(root, "p7")
    (base / "watch").mkdir()
    m, a = write_pair(base, outer, appr)
    res = subprocess.run([PY, "-B", str(LAUNCHER), "--manifest", str(m), "--approval", str(a)], capture_output=True, text=True, timeout=60)
    check("P7 existing watch dir: exit 4, nothing started", res.returncode == 4 and not (base / "marker" / "prelaunch_called").exists())
    # P8 the gate alone, no watchdog ever: NOT_READY, no work (the launcher died between the two starts)
    base, outer, appr = make_env(root, "p8", ready_timeout=2)
    m, a = write_pair(base, outer, appr)
    (base / "watch").mkdir()
    res = subprocess.run([PY, "-B", str(GATE), "--manifest", str(m), "--approval", str(a), "--watch-dir", str(base / "watch")],
                         capture_output=True, text=True, timeout=60)
    result = wait_file(base / "watch" / "gate_result.json", 3)
    check("P8 gate without any watchdog: exit 6 NOT_READY and no work", res.returncode == 6 and (result or {}).get("state") == "NOT_READY"
          and not (base / "marker" / "prelaunch_called").exists())


def main():
    group = sys.argv[sys.argv.index("--group") + 1] if "--group" in sys.argv else "all"
    root = Path(tempfile.mkdtemp(prefix="s2u_run_"))
    try:
        if group in ("all", "watchdog"):
            unit_watchdog()
        if group in ("all", "gate"):
            unit_gate_contract(root)
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
