"""Known-answer tests for cmdr_eval_driver_v37.py on CPU (lead 10/13, VERIFY-astra-16 9.1, 16b 2 / 3 / 5, 16f 6).
Runs the driver's real functions and loops with side effects (Isaac runs, sleeps, process lists, clocks) replaced.
Exit code 1 when any check fails."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time as _t
import types as _ty

EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
SRCF = os.environ.get("V37_SRC", os.path.join(EV, "cmdr_eval_driver_v37.py"))
SRC = open(SRCF, encoding="utf-8").read()
for pair in json.loads(os.environ.get("V37_MUTATE", "[]")):  # break-the-guard: mutate the source copy in memory
    assert SRC.count(pair[0]) == 1, pair[0]
    SRC = SRC.replace(pair[0], pair[1])
REAL = "cq_on22000_flat_stop03_on_s1000"
fails = []
TMP = tempfile.mkdtemp(prefix="v37t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")


def ns_for(argv):
    sys.argv = ["x", "--until", "2099-01-01 00:00"] + argv
    ns = {"__file__": SRCF, "__name__": "v37test"}
    sys.path.insert(0, EV)
    exec(compile(SRC, "v37", "exec"), ns)
    ns["OUT"] = TMP
    ns["LOGF"] = os.path.join(TMP, ns["args"].log + ".json")
    ns["BASEF"] = os.path.join(TMP, ns["args"].base_log + ".json")
    return ns


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:150], "want", repr(want)[:90])
    if not ok:
        fails.append(name)


class Clock:
    def __init__(self, t0=1000.0):
        self.t = t0

    def shim(self):
        return _ty.SimpleNamespace(time=lambda: self.t, strftime=_t.strftime, sleep=self.sleep, mktime=_t.mktime,
                                   strptime=_t.strptime, localtime=_t.localtime)

    def sleep(self, s):
        self.t += s


class FakeProc:
    """a launched child: poll() is None for `alive` calls, then rc."""
    def __init__(self, rc, alive=0):
        self.rc, self.alive = rc, alive

    def poll(self):
        if self.alive > 0:
            self.alive -= 1
            return None
        return self.rc

    def wait(self):
        return self.rc


def popen_from(fn):
    """POPEN stand-in from a subprocess.run-style fake (it writes the log and guard files and returns returncode)."""
    def P(cmd, **k):
        return FakeProc(fn(cmd, **k).returncode)
    return P


def probe(lockpath):
    """'held' or 'free': another process tries the conversion slot lock without waiting."""
    code = ("import msvcrt\nf = open(r'%s', 'a+b')\nf.seek(0)\ntry:\n    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)\n"
            "    print('free')\nexcept OSError:\n    print('held')\n") % lockpath
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()


def h(snap):
    return hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest() if snap is not None else None


def remeasure_ns(snaps, writers_seq, data, ready=lambda m: True, clock=None, deadline=None, att=None):
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t", "--base_log", "baset"])
    calls = {"read": 0, "writers": 0, "processed": [], "sleeps": 0}

    def read_raw():
        calls["read"] += 1
        sn = snaps[min(calls["read"], len(snaps)) - 1]
        return (sn, h(sn)) if sn is not None else (None, "JSONDecodeError")

    def writers(_):
        calls["writers"] += 1
        return writers_seq[min(calls["writers"], len(writers_seq)) - 1]

    def process(pick, reuse_only=False):
        t = n["tagof"](*pick)
        calls["processed"].append(t)
        n["LOG"]["matrix"][t] = "valid"
        return True

    def sleep(s):
        calls["sleeps"] += 1
        if clock:
            clock.sleep(s)
        if calls["sleeps"] > 80:
            raise RuntimeError("loop did not end")

    n.update(read_base_raw=read_raw, driver_writers=writers, lock_held=lambda name: False, process=process, ready=ready,
             save=lambda force=False: None, main_pass=lambda tag, cell: data[tag], set_attempt=lambda state: None,
             read_attempt=lambda name: (att if att is not None else {"attempt": "A1", "state": "ended"}), stop_requested=lambda: False)
    if clock:
        n["time"] = clock.shim()
    if deadline is not None:
        n["DEADLINE"] = deadline
    return n, calls, sleep


def pair(n, fam, cell, noise, off, on):
    T = n["tagof"]
    a, b = T("off24000", fam, cell, noise, 1000), T("on24000", fam, cell, noise, 1000)
    return {a: [e < off for e in range(100)], b: [e < on for e in range(100)]}


try:
    n0 = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t", "--base_log", "baset"])
    T = n0["tagof"]
    V = n0["VERSION"]
    EXP = n0["EXPERIMENT"]
    data = {**pair(n0, "wave", "stand", True, 60, 60), **pair(n0, "wave", "fwd03", True, 60, 50)}
    first = {T("off24000", "wave", "stand", True, 1000): "valid", T("on24000", "wave", "stand", True, 1000): "valid",
             T("off24000", "wave", "fwd03", True, 1000): "valid"}
    last = dict(first, **{T("on24000", "wave", "fwd03", True, 1000): "valid"})
    base = {"version": V, "experiment": EXP, "attempt": "A1"}
    S0 = dict(base, matrix=first)
    S1 = dict(base, matrix=last, ended="t", complete=True)
    want8 = sorted(T(m, "wave", "fwd03", True, s) for s in (1001, 1002, 1003, 1004) for m in ("off24000", "on24000"))

    # 1 S0 / S1 race: last pair arrives with ended
    n, calls, sleep = remeasure_ns([S0, S1], [[]], data)
    n["main_remeasure"](sleep=sleep)
    check("1a last pair in the final snapshot is remeasured", sorted(calls["processed"]), want8)

    # 2 old end records: an older version with nothing to screen must not end it; writer alive keeps it going
    quiet = {**pair(n0, "wave", "stand", True, 60, 60), **pair(n0, "wave", "fwd03", True, 60, 60)}
    old = dict(S1, version="3.4")
    n, calls, sleep = remeasure_ns([old, old, S1, S1], [[]], quiet)
    n["main_remeasure"](sleep=sleep)
    check("2a older-version end record (zero targets) ignored: ends on the 4th read", calls["read"], 4)
    n, calls, sleep = remeasure_ns([S1], [[777], [777], [777], []], quiet)
    n["main_remeasure"](sleep=sleep)
    check("2b writer alive on reads 1-3: a read with a writer is not a stable read -> ends on read 5", (calls["read"], calls["processed"]), (5, []))
    n, calls, sleep = remeasure_ns([S1], [[]], quiet)
    n["lock_held"] = lambda name: calls["read"] < 3
    n["main_remeasure"](sleep=sleep)
    check("2c base lock held on reads 1-2 counts as a writer: ends on read 4", calls["read"], 4)

    # 3 base log never readable: the deadline still ends it, with a record (16b 2.1)
    ck = Clock()
    n, calls, sleep = remeasure_ns([None], [[]], quiet, clock=ck, deadline=ck.t + 100)
    n["main_remeasure"](sleep=sleep)
    L = n["LOG"]
    check("3a permanent read failure: stopped at the deadline", (L.get("stopped"), "ended" in L, L["complete"], L["base_read_fail"]["why"]),
          ("deadline", True, False, "JSONDecodeError"))
    check("3b ended within a few retries", calls["sleeps"] <= 5, True)
    # temporary failure then a good final snapshot: normal end
    n, calls, sleep = remeasure_ns([None, None, S1, S1], [[]], data)
    n["main_remeasure"](sleep=sleep)
    check("3c temporary failure then final: remeasured and ended", (sorted(calls["processed"]), "stopped" in n["LOG"]), (want8, False))

    # 4 withdrawn screen cells and dequeued jobs (16b 2.3)
    allq = {}
    for fam, cell, noise in n0["screen_universe"]():
        allq.update(pair(n0, fam, cell, noise, 60, 60))
    full = {t: "valid" for t in allq}
    gone = T("on24000", "wave", "stand", True, 1000)
    Sa = dict(base, version="3.2", matrix=full)
    Sb = dict(base, matrix={t: v for t, v in full.items() if t != gone}, ended="t", complete=False)
    n, calls, sleep = remeasure_ns([Sa, Sb, Sb], [[]], allq)
    n["main_remeasure"](sleep=sleep)
    L = n["LOG"]
    check("4a cell gone from the final snapshot: withdrawn and unmeasured", ("wave/stand/on" in L["withdrawn"], L["screen_unmeasured"], L["complete"]),
          (True, ["wave/stand/on"], False))
    flagdata = dict(allq, **pair(n0, "wave", "fwd03", True, 60, 50))
    Sc = dict(base, version="3.2", matrix=full)
    Sd = dict(base, matrix={t: v for t, v in full.items() if t != T("on24000", "wave", "fwd03", True, 1000)}, ended="t", complete=False)
    seen = {"n": 0}

    def ready_late(m):
        return calls2["read"] >= 3
    n, calls2, sleep = remeasure_ns([Sc, Sd, Sd], [[]], flagdata, ready=lambda m: ready_late(m))
    n["main_remeasure"](sleep=sleep)
    L = n["LOG"]
    check("4b flagged then withdrawn before running: 8 jobs dequeued, none run", (len(L["dequeued"]), calls2["processed"], L["flagged"]), (8, [], []))

    # 5 writer detection parses argv and compares normalised paths (16b 2.2)
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "cmdr_eval_driver_g0", "--base_log", "cmdr_eval_driver"])
    D = "C:/isaac/ext/go2_rl_robotlab/_eval/cmdr_eval_driver_v35.py"

    def P(pid, *a):
        return {"pid": pid, "name": "python.exe", "cmdline": ["python.exe", D, *a]}
    procs = [P(11, "--log", "cmdr_eval_driver_g0"), P(12, "--log=cmdr_eval_driver_g0"), P(13, "--log", "CMDR_EVAL_DRIVER_G0"),
             P(14, "--log", "./cmdr_eval_driver_g0"), P(15, "--lo", "cmdr_eval_driver_g0"),
             {"pid": 16, "name": "python.exe", "cmdline": ["python.exe", "cmdr_eval_driver.py", "--until", "2026-10-13 14:00"]},
             P(17, "--log", "something_else"), {"pid": 18, "name": "python.exe", "cmdline": ["python.exe", "other.py", "--log", "cmdr_eval_driver_g0"]}]
    check("5a g0 writers in every spelling", sorted(n["driver_writers"]("cmdr_eval_driver_g0", procs)), [11, 12, 13, 14, 15])
    check("5b base writers: only the v3.2 default", n["driver_writers"]("cmdr_eval_driver", procs), [16])

    # 6 OS lock across processes
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "locktest"])
    child = subprocess.Popen([sys.executable, "-c", f"""
import msvcrt, time
f = open(r"{os.path.join(TMP, 'locktest.lock')}", "a+b")
msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
print("locked", flush=True)
time.sleep(6)
"""], stdout=subprocess.PIPE, text=True)
    child.stdout.readline()
    check("6a lock held by another process: take_lock refused, lock_held true", (n["take_lock"](), n["lock_held"]("locktest")), (False, True))
    child.wait()
    check("6b after it exits: free", (n["lock_held"]("locktest"), n["take_lock"]()), (False, True))
    n["LOCK"][0].close()

    # 7 exit records (16b 3, 16d 2.1 / 2.5): owner during re-validation keeps the old table; an exception after start is recorded
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "exitt"])
    json.dump({"matrix": {"old": "valid"}}, open(n["LOGF"], "w"))

    def boom_owned():
        n["OWNED"][0] = True
        raise SystemExit(4)
    n["start"] = boom_owned
    try:
        n["main"]()
    except SystemExit:
        pass
    old = json.load(open(n["LOGF"]))
    st = json.load(open(os.path.join(TMP, "exitt.stopped.json")))
    att = json.load(open(os.path.join(TMP, "exitt.attempt.json")))
    check("7a owner exits during re-validation: old table kept, stop record beside it, attempt stopped",
          (old, st["exit_code"], st["stopped"], st["end_kind"], att["state"]), ({"matrix": {"old": "valid"}}, 4, "exit 4", "error", "stopped"))
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "exitr", "--base_log", "baset"])

    def owned_start():
        n["OWNED"][0] = True
        n["PUBLISH"][0] = True
    n["start"] = owned_start
    n["run_tests"] = lambda: None
    n["PENDING"][0].append(("on24000", "wave", "fwd03", True, 1001))

    def crash(**k):
        raise ValueError("x")
    n["main_remeasure"] = crash
    try:
        n["main"]()
    except ValueError:
        pass
    L = json.load(open(n["LOGF"]))
    check("7b exception: exit record in the log with not_run, end_kind error", (L["exit_code"], L["stopped"], L["not_run"], L["end_kind"]),
          (1, "ValueError: x", ["cq_on24000_wave_fwd03_on_s1001"], "error"))

    # 8 guard retries keep their own evidence (16b 3)
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "gtt"])
    n["P0"] = {"x": 1}
    rcs = [99, 0]

    def fake_run(cmd, **k):
        name = cmd[cmd.index("--log") + 1].split("/")[-1][:-4]
        open(os.path.join(TMP, name + ".log"), "w").write(f"try rc {rcs[0]}\n")
        open(os.path.join(TMP, name + ".guard.json"), "w").write("{}")
        return _ty.SimpleNamespace(returncode=rcs.pop(0))
    n["POPEN"] = popen_from(fake_run)
    n.update(pins=lambda: {"x": 1}, foreign_isaac=lambda procs=None: [])
    n["time"] = Clock().shim()
    rc, k = n["guarded"]("gtag", ["x"], wait_s=1)
    tr = n["TRIES"]["gtag"]
    moved = sorted(os.listdir(os.path.join(TMP, "attempts")))
    check("8a rc99 then 0: two tries recorded, first try's files moved aside", (rc, k, [x["rc"] for x in tr], len(tr[1]["earlier_moved"]), len(moved)), (0, 2, [99, 0], 2, 2))
    check("8b moved log is the first try's", open(os.path.join(TMP, "attempts", [m for m in moved if ".log." in m][0])).read(), "try rc 99\n")

    # 9 write_stamp retries a sharing violation
    n = ns_for(["--gpu", "1"])
    os.makedirs(os.path.join(TMP, "stamptag"), exist_ok=True)
    real_replace = os.replace
    cnt = {"n": 0}

    def flaky(a, b):
        cnt["n"] += 1
        if cnt["n"] <= 2:
            raise PermissionError("shared")
        return real_replace(a, b)
    n["os"] = _ty.SimpleNamespace(**{k: getattr(os, k) for k in dir(os) if not k.startswith("__")})
    n["os"].replace = flaky
    n["time"] = Clock().shim()
    n["write_stamp"]("stamptag", {"x": 1}, {"out_sha256": {}})
    check("9 two sharing violations then written", (cnt["n"], os.path.exists(os.path.join(TMP, "stamptag", "driver_stamp.json"))), (3, True))

    # 10 GPU 0 hand-over reads the contents
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t"])
    bdir = os.path.join(TMP, "branch")
    on = os.path.join(bdir, "cmdr_s1042_on_u4000")
    os.makedirs(on)
    n["B"] = bdir
    n["NIGHT_OUT"] = os.path.join(bdir, "night.out")
    ckp = os.path.join(on, "model_24000.pt")
    n["MODELS"] = dict(n["MODELS"], on24000=(ckp, 24000))
    n["training_running"] = lambda: False
    n["gpu_used_mib"] = lambda g: 900
    good = {"meta": {"args": {"tag": "cmdr_s1042_on_u4000", "cmdr": "on"}}, "final_state": {"where": "end", "label_next": 24000}}

    def res(d):
        json.dump(d, open(os.path.join(on, "result.json"), "w"))
    check("10a no result.json", n["training_done"](), "on arm has no result.json")
    res(dict(good, meta={"args": {"tag": "cmdr_s1042_off_u4000", "cmdr": "off"}}))
    check("10b the off arm's result is refused", n["training_done"]().startswith("on arm result.json is not the finished on arm"), True)
    res(dict(good, final_state={"where": "rollout", "label_next": 23500}))
    check("10c unfinished result refused", n["training_done"]().startswith("on arm result.json is not the finished on arm"), True)
    res(good)
    open(ckp, "wb").write(b"x")
    check("10d wrong checkpoint size", n["training_done"](), "model_24000.pt size 1")
    with open(ckp, "wb") as f:
        f.truncate(n["CKPT_BYTES"])
    open(n["NIGHT_OUT"], "w").write("cmdr_s1042_off_u4000 EXIT 0\nNIGHT DONE (old)\ncmdr_s1042_on_u4000 START\n")
    check("10e NIGHT DONE only before the on arm's exit", n["training_done"](), "night log has no NIGHT DONE after the on arm's EXIT 0")
    open(n["NIGHT_OUT"], "a").write("cmdr_s1042_on_u4000 EXIT 0 22000s\nNIGHT DONE 2026-10-13 11:30\n")
    check("10f all signs", n["training_done"](), "")
    n["gpu_used_mib"] = lambda g: 3000
    check("10g 3000 MiB refused (< 3000 needed)", n["training_done"](), "GPU 0 memory used 3000 MiB")
    n["gpu_used_mib"] = lambda g: 2999
    check("10h 2999 MiB ok", n["training_done"](), "")

    # 12 16d 2.1: refused starts leave the existing log bytes untouched (real main -> start -> exit_record)
    def refused(case):
        args = ["--gpu", "0", "--plan", "remeasure", "--log", "own", "--base_log", "own" if case == "same" else "baset"]
        n = ns_for(args)
        open(n["LOGF"], "w").write('{"attempt": "OTHER_LIVE_WRITER", "matrix": {"keep": "valid"}}')
        before = open(n["LOGF"], "rb").read()
        n["driver_writers"] = (lambda name: [999]) if case == "writer" else (lambda name: [])
        n["take_lock"] = (lambda: False) if case == "lock" else n["take_lock"]
        try:
            n["main"]()
            code = "no exit"
        except SystemExit as e:
            code = e.code
        after = open(n["LOGF"], "rb").read()
        ref = [f for f in os.listdir(os.path.join(TMP, "attempts")) if f.startswith("own.") and f.endswith(".refused.json")] \
            if os.path.isdir(os.path.join(TMP, "attempts")) else []
        side = [f for f in ("own.stopped.json", "own.attempt.json") if os.path.exists(os.path.join(TMP, f))]
        for f in ref:
            os.remove(os.path.join(TMP, "attempts", f))
        os.remove(n["LOGF"])
        if n["LOCK"][0]:
            n["LOCK"][0].close()
        return code, before == after, len(ref), side
    for case in ("writer", "lock", "same"):
        check(f"12 refused start ({case}): exit 6, log bytes kept, one refused record, no shared side files", refused(case), (6, True, 1, []))

    # 13 16d 2.2: an old finished log under a NEW attempt that stopped while re-validating never ends the remeasure
    old_fin = dict(base, attempt="OLD", matrix=last, ended="t", complete=True)
    ck = Clock()
    n, calls, sleep = remeasure_ns([old_fin], [[]], quiet, clock=ck, deadline=ck.t + 400, att={"attempt": "NEW", "state": "stopped"})
    n["main_remeasure"](sleep=sleep)
    check("13a new attempt stopped, log still the old finished one: no final, ends only at the deadline",
          (n["LOG"].get("stopped"), n["LOG"]["complete"], n["LOG"]["base_seen"]["final"]), ("deadline", False, False))
    n, calls, sleep = remeasure_ns([old_fin], [[]], quiet, att={"attempt": "NEW", "state": "revalidating"}, clock=Clock(), deadline=1000 + 300)
    n["main_remeasure"](sleep=sleep)
    check("13b new attempt re-validating: no final", n["LOG"]["base_seen"]["final"], False)
    n, calls, sleep = remeasure_ns([old_fin, None, old_fin, old_fin], [[]], quiet, att={"attempt": "OLD", "state": "ended"})
    n["main_remeasure"](sleep=sleep)
    check("13c matching attempt ended: a failed read resets the stable count -> ends on read 4", calls["read"], 4)

    # 14 16d 2.3: a job whose stamp cannot be written stays in the exit record with its tries
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "actv"])
    job = ("on24000", "wave", "fwd03", True, 1001)
    tagj = n["tagof"](*job)

    def owned_start2():
        n["OWNED"][0] = True
    n["start"] = owned_start2
    n["jobs"] = lambda: [job]
    n["P0"] = {"x": 1}
    n["LOG"]["ckpt"] = {m: {"sha256": "c"} for m in n["MODELS"]}

    def g(name, cmd, tries=4, wait_s=300, ck=None):
        n["TRIES"].setdefault(name, []).append({"try": 1, "rc": 0, "s": 80, "earlier_moved": []})
        return 0, 1

    def bad_stamp(*a, **k):
        raise RuntimeError("could not replace stamp")
    n.update(ready=lambda m: True, run_tests=lambda: None, pins=lambda: {"x": 1}, sha=lambda p: "c", stamp_ok=lambda t, P: False,
             old_stamp=lambda t: {}, guarded=g, validate=lambda *a, **k: "", outhash=lambda t: {"h": 1}, diag_warns=lambda t: [],
             fingerprint=lambda t: {"f": 1}, write_stamp=bad_stamp)
    try:
        n["main"]()
    except RuntimeError:
        pass
    L = json.load(open(n["LOGF"]))
    check("14 stamp failure mid-job: active tag and its tries in the exit record, error, not complete",
          ((L["active"] or {}).get("tag"), len(L["active_tries"]), L["end_kind"], L["complete"]), (tagj, 1, "error", False))

    # 15 16d 2.5: normal ends write end_kind and exit_code (complete and deadline)
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "endk"])
    n["OWNED"][0] = True
    js = n["jobs"]()[:2]
    n["jobs"] = lambda: js

    def proc_ok(pick, reuse_only=False):
        n["LOG"]["matrix"][n["tagof"](*pick)] = "valid"
        return True
    n.update(ready=lambda m: True, run_tests=lambda: None, process=proc_ok)
    n["main_base"]()
    L = json.load(open(n["LOGF"]))
    check("15a all valid: end_kind complete, exit_code 0", (L["end_kind"], L["exit_code"], L["complete"]), ("complete", 0, True))
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "endd"])
    n["OWNED"][0] = True
    n["jobs"] = lambda: js
    n.update(ready=lambda m: True, run_tests=lambda: setattr(sys, "_x", 0) or n.__setitem__("DEADLINE", 0),
             process=lambda pick, reuse_only=False: False)
    n["main_base"]()
    L = json.load(open(n["LOGF"]))
    check("15b deadline with jobs left: incomplete, stopped deadline, not_run listed", (L["end_kind"], L["stopped"], len(L["not_run"])), ("incomplete", "deadline", 2))

    # 16 16d 2.4: unreadable argv is an unknown writer
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t"])
    check("16 python with unreadable argv -> unknown writer", n["driver_writers"]("g0t", [{"pid": 5, "name": "python.exe", "cmdline": None}]), ["unknown:5"])

    # 17 (s) stop file ends the remeasure at the next boundary
    n, calls, sleep = remeasure_ns([S1], [[]], data)
    n["stop_requested"] = lambda: True
    n["main_remeasure"](sleep=sleep)
    check("17 stop file: stopped, incomplete, no job run", (n["LOG"]["stopped"], n["LOG"]["end_kind"], calls["processed"]), ("stop file", "incomplete", []))

    # 18 (w) stop / deadline / pins / checkpoint while waiting for the slot, and with the slot held: no launch (16f 3.2)
    def slot_ns(log, foreign, deadline=None, pins_fn=None, sha_fn=None):
        n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", log])
        ck = Clock(1000.0)
        n["time"] = ck.shim()
        n["P0"] = {"x": 1}
        n["pins"] = pins_fn(ck) if pins_fn else (lambda: {"x": 1})
        if sha_fn:
            n["sha"] = sha_fn(ck)
        n["LOG"]["ckpt"] = {m: {"sha256": "c"} for m in n["MODELS"]}
        n["DEADLINE"] = deadline if deadline is not None else 4e9
        n["foreign_isaac"] = lambda procs=None: foreign(ck)
        orig = n["convert_slot"]
        n["convert_slot"] = lambda where, ck_=None, sleep=None: orig(where, ck_, sleep=ck.sleep)
        launches = []
        n["POPEN"] = lambda cmd, **k: (launches.append(cmd), FakeProc(0))[1]
        return n, ck, launches

    def run_g(n, name, ck_m=None):
        try:
            return n["guarded"](name, ["x"], ck=ck_m)
        except SystemExit as e:
            return ("exit", e.code)
    n, ck, launches = slot_ns("s18a", lambda c: [4242] if c.t < 1020 else [], deadline=1010.0)
    got = run_g(n, "dl")
    check("18a slot busy past the deadline: exit 2 during the wait, before any launch", (got, launches, n["LOG"].get("stopped"), ck.t < 1020), (("exit", 2), [], "deadline before dl try 1", True))

    def stop_at(c):
        if c.t >= 1002:
            open(os.path.join(TMP, "s18b.stop"), "w").write("")
        return [4242] if c.t < 1020 else []
    n, ck, launches = slot_ns("s18b", stop_at)
    got = run_g(n, "st")
    check("18b stop file while waiting: exit 7 during the wait, no launch", (got, launches, n["LOG"].get("stopped"), ck.t < 1020), (("exit", 7), [], "stop file before st try 1", True))
    os.remove(os.path.join(TMP, "s18b.stop"))
    n, ck, launches = slot_ns("s18c", lambda c: [4242] if c.t < 1020 else [], pins_fn=lambda c: (lambda: {"x": 1} if c.t < 1002 else {"x": 2}))
    got = run_g(n, "pn")
    check("18c pins change while waiting: exit 4 during the wait, no launch", (got, launches, ck.t < 1020), (("exit", 4), [], True))
    n, ck, launches = slot_ns("s18d", lambda c: [4242] if c.t < 1020 else [], sha_fn=lambda c: (lambda p: "c" if c.t < 1002 else "d"))
    got = run_g(n, "ckp", ck_m="on24000")
    check("18d the job's checkpoint changes while waiting: exit 5 during the wait, no launch", (got, launches, ck.t < 1020), (("exit", 5), [], True))

    def stop_when_free(c):
        open(os.path.join(TMP, "s18e.stop"), "w").write("")
        return []
    n, ck, launches = slot_ns("s18e", stop_when_free)
    got = run_g(n, "sh")
    check("18e stop file appears as the slot is taken: the check with the slot held stops it, no launch",
          (got, launches, n["LOG"].get("stopped")), (("exit", 7), [], "stop file before sh try 1 launch"))
    os.remove(os.path.join(TMP, "s18e.stop"))
    n, ck, launches = slot_ns("s18f", lambda c: [4242] if c.t < 1020 else [])
    got = run_g(n, "ok")
    check("18f control: slot free at 1020, nothing fired: one launch after the wait, (0, 1)", (got, len(launches), ck.t >= 1020), ((0, 1), 1, True))

    # 19 (x) robot root reference failure: retried whatever the exit code; tries used up = infrastructure failure (16f 3.3)
    def rr_ns(log, seq):
        n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", log])
        n["P0"] = {"x": 1}
        n.update(pins=lambda: {"x": 1}, foreign_isaac=lambda procs=None: [])
        n["time"] = Clock().shim()

        def run2(cmd, **k):
            what, rc = seq.pop(0)
            name = cmd[cmd.index("--log") + 1].split("/")[-1][:-4]
            txt = (n["ROOT_REF"] + " prim path @/tmp/IsaacLab/usd_x@\n[Q-EVAL] done\n") if what == "root" else "[Q-EVAL] done\n"
            open(os.path.join(TMP, name + ".log"), "w").write(txt)
            open(os.path.join(TMP, name + ".guard.json"), "w").write("{}")
            return _ty.SimpleNamespace(returncode=rc)
        n["POPEN"] = popen_from(run2)
        return n
    n = rr_ns("r19a", [("root", 0), ("ok", 0)])
    rc, k = n["guarded"]("rtag_a", ["x"])
    check("19a root reference failure with exit 0 and no Traceback: retried, then clean (0, 2)",
          (rc, k, n["TRIES"]["rtag_a"][0].get("root_ref_unresolved"), n["LOG"].get("infra_fail")), (0, 2, True, None))
    n = rr_ns("r19b", [("root", 0)] * 4)
    rc, k = n["guarded"]("rtag_b", ["x"])
    tr = n["TRIES"]["rtag_b"]
    kept_b = [f for f in os.listdir(os.path.join(TMP, "attempts")) if f.startswith("rtag_b.")]
    check("19b four root reference failures: (1, 4), infrastructure failure on the last try, earlier tries' six files kept",
          (rc, k, tr[-1].get("infra_fail"), n["LOG"].get("infra_fail"), len(kept_b)), (1, 4, True, ["rtag_b"], 6))

    # 20 (v) the slot is held from before the launch until the scene-creation line, then released while the child runs
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "hold"])
    n["P0"] = {"x": 1}
    n.update(pins=lambda: {"x": 1}, foreign_isaac=lambda procs=None: [])
    lockp = os.path.join(TMP, "isaac_convert.lock")
    seen = []

    class HP(FakeProc):
        def poll(self):
            seen.append(probe(lockp))
            if len(seen) == 2:
                open(os.path.join(TMP, "htag.log"), "a").write(n["CONVERT_DONE"] + " : 4.6 seconds\n")
            return None

    def hp_popen(cmd, **k):
        open(os.path.join(TMP, "htag.log"), "w").write("[Warning] [isaacsim.asset.importer.urdf] RL_foot_joint\n"
                                                       "Unresolved reference prim path @/tmp/IsaacLab/usd_20261013_120000_7028/go2.usd@\n")
        open(os.path.join(TMP, "htag.guard.json"), "w").write("{}")
        return HP(0)
    n["POPEN"] = hp_popen
    rc, k = n["guarded"]("htag", ["x"])
    after = probe(lockp)
    t0 = n["TRIES"]["htag"][0]
    check("20a slot held while the child converts, released at the scene-creation line",
          (seen, after, t0["slot"]["released_by"], t0["usd_dir"], (rc, k)), (["held", "held"], "free", "marker", ["20261013_120000_7028"], (0, 1)))
    check("20b a child that exits before the line releases the slot too", n["hold_until_converted"]("nolog", FakeProc(1))[0], "exit")
    f = n["convert_slot"]("direct")
    held = probe(lockp)
    n["release_slot"](f)
    check("20c convert_slot holds the OS lock until release_slot", (held, probe(lockp)), ("held", "free"))

    # 21 (v) who takes part in the slot (process lists made up; pids 1000+ are not real here)
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t"])
    me = os.getpid()

    def PR(pid, ppid, ct, *argv, name="python.exe", cwd=None, empty=False):
        return {"pid": pid, "ppid": ppid, "create_time": ct, "name": name, "cwd": cwd,
                "cmdline": [] if empty else (list(argv) if argv else None)}
    plist = [PR(me, 1, 50, "python.exe", "cmdr_eval_driver_v37.py", "--gpu", "0"),
             PR(1001, 1, 60, "python.exe", "cmdr_eval_driver.py", "--until", "2026-10-13 14:00"),
             PR(1002, 1, 61, "python.exe", "cmdr_eval_driver_v36.py", "--gpu", "0"),
             PR(1030, 1, 100, "python.exe", SRCF.replace("/", "\\"), "--gpu", "1"),
             PR(1050, 1, 100, "python.exe", "D:/other/_eval/cmdr_eval_driver_v37.py", "--gpu", "1"),
             PR(1051, 1050, 110, "python.exe", "gpu_guard.py", "--", "python.exe", "q_eval_cmdr.py", "--headless"),
             PR(1060, 1, 100, "python.exe", "cmdr_eval_driver_v37.py", "--gpu", "0", cwd=os.path.dirname(SRCF)),
             PR(1061, 1060, 110, "python.exe", "gpu_guard.py", "--", "python.exe", "q_eval_cmdr.py", "--headless"),
             PR(1062, 1, 100, "python.exe", "cmdr_eval_driver_v37.py", "--gpu", "0"),
             PR(1063, 1062, 110, "python.exe", "gpu_guard.py", "--", "python.exe", "q_eval_cmdr.py", "--headless"),
             PR(1070, 1, 70, empty=True),
             PR(1031, 1030, 110, "python.exe", "gpu_guard.py", "--gpu", "1", "--", "python.exe", "q_eval_cmdr.py", "--headless"),
             PR(1032, 1031, 111, "python.exe", "q_eval_cmdr.py", "--headless", "--tag", "t"),
             PR(1033, 1030, 90, "python.exe", "q_eval_cmdr.py", "--headless", "--tag", "u"),
             PR(1040, 1, 70),
             PR(1041, 1, 71, "python.exe", "-m", "awslabs.aws_api_mcp_server.server"),
             PR(1042, 1, 72, "kit.exe", name="kit.exe"),
             PR(1043, 1, 73, "python.exe", "unseen_driver.py"),
             PR(1044, 1, 74, "python.exe", "branch_run.py", "--tag", "x"),
             PR(1045, 1, 75, "python.exe", "something.py", "--headless"),
             PR(1046, 1001, 80, "python.exe", "gpu_guard.py", "--", "python.exe", "q_eval_cmdr.py", "--headless")]
    check("21 foreign: older drivers, their children, unseen / training launchers, kit, unreadable or empty argv, a reused parent pid, "
          "a same-named v3.7 in another folder and its child, a relative path whose cwd is unknown and its child; "
          "not: this file (absolute or relative to its cwd), its children, unrelated python",
          sorted(map(str, n["foreign_isaac"](plist))),
          sorted(map(str, [1001, 1002, 1033, "unknown:1040", 1042, 1043, 1044, 1045, 1046, 1050, 1051, 1062, 1063, "unknown:1070"])))

    # 26 (v) the real process list on this machine: fast, our own parent and create time right, live old drivers foreign
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t"])
    t_ = _t.time()
    pl = n["_procs_tree"]()
    dt = _t.time() - t_
    mine = next(p for p in pl if p["pid"] == os.getpid())
    t_ = _t.time()
    fo = n["foreign_isaac"]()
    dt2 = _t.time() - t_
    old_live = sorted(p["pid"] for p in pl if (p.get("name") or "").lower().startswith("python") and p.get("cmdline")
                      and any(os.path.basename(x).lower() in ("cmdr_eval_driver.py", "cmdr_eval_driver_v36.py") for x in p["cmdline"]))
    check(f"26 real process list in {dt:.2f} s and foreign check in {dt2:.2f} s (< 5 s each); own ppid and create time; live older drivers foreign {old_live}",
          (dt < 5, dt2 < 5, mine["ppid"] == os.getppid(), mine["create_time"] is not None, all(x in fo for x in old_live)), (True, True, True, True, True))

    # 27 (o2) a re-validated v3.2 run keeps its origin; a later re-validation does not upgrade it; a new run is hashed-at-collection
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "org"])
    job = ("on24000", "wave", "fwd03", True, 1003)
    tg = n["tagof"](*job)
    os.makedirs(os.path.join(TMP, tg))
    open(os.path.join(TMP, tg, "driver_stamp.json"), "w").write('{"pins": {"x": 1}, "t": "old"}')
    want_prev = hashlib.sha256(open(os.path.join(TMP, tg, "driver_stamp.json"), "rb").read()).hexdigest()
    n["P0"] = {"x": 1}
    n["LOG"]["ckpt"] = {mm: {"sha256": "c"} for mm in n["MODELS"]}
    got_st = {}
    real_sha = n["sha"]
    n.update(pins=lambda: {"x": 1}, sha=lambda p: real_sha(p) if p.endswith("driver_stamp.json") else "c", stamp_ok=lambda t, P: True,
             validate=lambda *a, **k: "", outhash=lambda t: {"h": 1}, diag_warns=lambda t: [], fingerprint=lambda t: {"f": 1},
             write_stamp=lambda t, P, extra: got_st.update(extra))
    n["process"](job)
    rec = n["LOG"]["runs"][-1]
    check("27a re-validated v3.2 run: origin legacy-origin revalidated, the old stamp's hash and this attempt kept",
          (rec["reused"], rec["origin"], got_st.get("origin"), got_st.get("prev_stamp_sha256") == want_prev,
           got_st.get("revalidated_by") == n["ATTEMPT"], got_st.get("attempt")),
          (True, "legacy-origin revalidated", "legacy-origin revalidated", True, True, "v3.2 or earlier"))
    open(os.path.join(TMP, tg, "driver_stamp.json"), "w").write(json.dumps({"pins": {"x": 1}, "stamp_version": "3.7",
                                                                            "origin": "origin unknown", "attempt": "g1-1-1013140000-j1"}))
    got_st.clear()
    n["process"](job)
    check("27b a later re-validation keeps an explicit origin (origin unknown + a real job id is not upgraded to hashed-at-collection)",
          got_st.get("origin"), "origin unknown")
    n["stamp_ok"] = lambda t, P: False
    n["guarded"] = lambda name, cmd, tries=4, wait_s=300, ck=None: (0, 1)
    got_st.clear()
    n["process"](job)
    check("27c a new run: hashed-at-collection, no previous stamp fields", (n["LOG"]["runs"][-1]["origin"], got_st.get("origin"), "prev_stamp_sha256" in got_st),
          ("hashed-at-collection", "hashed-at-collection", False))
    n["stamp_ok"] = lambda t, P: True
    got_o = []
    for att in ("v3.2 or earlier", "g0-85080-1013114359-j1", "weird"):
        os.makedirs(os.path.join(TMP, tg), exist_ok=True)
        open(os.path.join(TMP, tg, "driver_stamp.json"), "w").write(json.dumps({"pins": {"x": 1}, "stamp_version": "3.6", "attempt": att}))
        got_st.clear()
        n["process"](job)
        got_o.append(got_st.get("origin"))
    check("27d (16h 3.2) a v3.6 stamp without origin: re-validated v3.2 run / real job id / anything else",
          got_o, ["legacy-origin revalidated", "hashed-at-collection", "origin unknown"])

    # 22 (y) usd_check on copies of real logs (out/ is only read)
    n = ns_for(["--gpu", "1"])
    U = os.path.join(TMP, "u")
    os.makedirs(U)
    n["OUT"] = U
    ST, KT = "cq_on24000_flat_stand_on_s1000", "cq_test_8d384fcb_g0t113506p59116_ka_copy_default_buffers"
    shutil.copy(os.path.join(EV, "out", ST + ".log"), os.path.join(U, ST + ".log"))
    check("22a the 11:38 stand run's log alone: passes", n["usd_check"](ST), "")
    shutil.copy(os.path.join(EV, "out", KT + ".log"), os.path.join(U, KT + ".log"))
    check("22b with the 11:38 start test log beside it: shared folder", n["usd_check"](ST),
          f"USD temp folder usd_20261013_113828_7028 shared with ['{KT}.log']")
    check("22c the failed start test's own log: root reference failure", n["usd_check"](KT).startswith("robot root reference unresolved"), True)
    os.remove(os.path.join(U, KT + ".log"))
    os.makedirs(os.path.join(U, "attempts"))
    shutil.copy(os.path.join(EV, "out", KT + ".log"), os.path.join(U, "attempts", KT + ".log.1013113828.1"))
    check("22d a copy under attempts/ also counts", n["usd_check"](ST).startswith("USD temp folder usd_20261013_113828_7028 shared with ['attempts/"), True)
    shutil.rmtree(os.path.join(U, "attempts"))
    os.remove(os.path.join(U, ST + ".log"))
    txt = open(os.path.join(EV, "out", REAL + ".log"), encoding="utf-8", errors="replace").read()

    def wl(name, t):
        open(os.path.join(U, name + ".log"), "w", encoding="utf-8").write(t)
    wl("r_nomk", txt.replace(n["CONVERT_DONE"], "[INFO]: something else"))
    wl("r_after", txt + "\n2026-10-13T00:00:00Z [Warning] [isaacsim.asset.importer.urdf] late line\n")
    wl("r_two", txt + "\nUnresolved reference prim path @/tmp/IsaacLab/usd_20991231_000000_1/go2.usd@\n")
    check("22e no scene-creation line / importer line after it / two USD folders",
          (n["usd_check"]("r_nomk"), n["usd_check"]("r_after"), n["usd_check"]("r_two")),
          ("no scene-creation line", "USD conversion output after the scene-creation line", "USD folders named in the log: 2"))

    # 23 (y) real data, read only: every valid run in both live logs passes except the 11:38 stand run
    n = ns_for(["--gpu", "1"])
    n["OUT"] = os.path.join(EV, "out")
    tags = sorted({r["tag"] for nm in ("cmdr_eval_driver", "cmdr_eval_driver_g0")
                   for r in json.load(open(os.path.join(EV, "out", nm + ".json"), encoding="utf-8"))["runs"] if r["valid"]})
    bad = {t: w for t, w in ((t, n["usd_check"](t)) for t in tags) if w}
    check(f"23 real data: of {len(tags)} valid runs only the stand run fails, for the shared folder",
          (sorted(bad), (bad.get(ST) or "").startswith("USD temp folder usd_20261013_113828_7028 shared with [")), ([ST], True))

    # 24 (z) a run measured again keeps its earlier result folder
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "prs"])
    os.makedirs(os.path.join(TMP, "ptag"))
    open(os.path.join(TMP, "ptag", "meta.json"), "w").write("old")
    m = n["preserve_result"]("ptag")
    check("24a folder moved under attempts/, second call finds none",
          (m.startswith("attempts/ptag.dir."), open(os.path.join(TMP, m, "meta.json")).read(), n["preserve_result"]("ptag")), (True, "old", None))
    job = ("on24000", "wave", "fwd03", True, 1002)
    tg = n["tagof"](*job)
    os.makedirs(os.path.join(TMP, tg))
    open(os.path.join(TMP, tg, "meta.json"), "w").write("old")
    n["P0"] = {"x": 1}
    n["LOG"]["ckpt"] = {mm: {"sha256": "c"} for mm in n["MODELS"]}

    def g2(name, cmd, tries=4, wait_s=300, ck=None):
        os.makedirs(os.path.join(TMP, name), exist_ok=True)
        open(os.path.join(TMP, name, "meta.json"), "w").write("new")
        return 0, 1
    n.update(pins=lambda: {"x": 1}, sha=lambda p: "c", stamp_ok=lambda t, P: False, old_stamp=lambda t: {}, guarded=g2,
             validate=lambda *a, **k: "", outhash=lambda t: {"h": 1}, diag_warns=lambda t: [], fingerprint=lambda t: {"f": 1},
             write_stamp=lambda *a, **k: None)
    n["process"](job)
    mv = n["LOG"]["runs"][-1].get("earlier_result_moved")
    check("24b process(): the run record names the moved folder; old bytes there, new bytes in place",
          (bool(mv), open(os.path.join(TMP, mv, "meta.json")).read() if mv else None, open(os.path.join(TMP, tg, "meta.json")).read()), (True, "old", "new"))

    # 25 (w) exit record of a stop or a deadline before a launch: incomplete, attempt stopped, active job kept
    def stop_main(log, make):
        n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", log, "--base_log", "baset"])

        def st():
            n["OWNED"][0] = True
            n["PUBLISH"][0] = True
        n["start"] = st
        n["run_tests"] = lambda: None
        make(n)

        def mr(**k):
            n["ACTIVE"][0] = {"tag": "t1", "stage": "run"}
            n["gate"]("t1 try 1")
        n["main_remeasure"] = mr
        try:
            n["main"]()
            code = "no exit"
        except SystemExit as e:
            code = e.code
        L = json.load(open(n["LOGF"], encoding="utf-8"))
        att = json.load(open(os.path.join(TMP, log + ".attempt.json"), encoding="utf-8"))
        return code, L["exit_code"], L["end_kind"], L["stopped"], (L["active"] or {}).get("tag"), att["state"]
    check("25a stop file before a launch", stop_main("e25a", lambda n: open(os.path.join(TMP, "e25a.stop"), "w").write("")),
          (7, 7, "incomplete", "stop file before t1 try 1", "t1", "stopped"))
    check("25b deadline before a launch", stop_main("e25b", lambda n: n.__setitem__("DEADLINE", 0)),
          (2, 2, "incomplete", "deadline before t1 try 1", "t1", "stopped"))

    # 11 earlier checks kept: real run validate, negative / NaN max_abs, gpu uuid, stamps, refusal of same log
    n = ns_for(["--gpu", "1"])
    d = os.path.join(TMP, REAL)
    shutil.copytree(os.path.join(EV, "out", REAL), d)
    for ext in (".log", ".guard.json"):
        shutil.copy(os.path.join(EV, "out", REAL + ext), os.path.join(TMP, REAL + ext))
    drv = json.load(open(os.path.join(EV, "out", "cmdr_eval_driver.json"), encoding="utf-8"))
    va = (REAL, drv["ckpt"]["on22000"]["sha256"], 22000, "flat", ["stop03"], 100, True, 1000, True)
    check("11a real run validates on GPU 1", n["validate"](*va), "")
    lp = os.path.join(TMP, REAL + ".log")
    open(lp, "a", encoding="utf-8").write("\n" + n["ROOT_REF"] + " prim path @/tmp/IsaacLab/x@\n")
    check("11g the same real run with the robot root reference failure added: invalid (16f 3.3)", n["validate"](*va).startswith("robot root reference unresolved"), True)
    shutil.copy(os.path.join(EV, "out", REAL + ".log"), lp)
    check("11b under --gpu 0 -> gpu uuid", ns_for(["--gpu", "0", "--log", "g0t"])["validate"](*va), "gpu uuid")
    mp = os.path.join(d, "meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    meta["checks_run"]["obs_single_cmd_vs_target_max_abs"] = -1.0
    json.dump(meta, open(mp, "w", encoding="utf-8"))
    check("11c negative max_abs rejected", n["validate"](*va).startswith("checks_run"), True)
    shutil.copy(os.path.join(EV, "out", REAL, "meta.json"), mp)
    P0 = json.load(open(os.path.join(d, "driver_stamp.json"), encoding="utf-8"))["pins"]
    open(os.path.join(d, "driver_stamp.json"), "w").write("{")
    check("11d cut stamp -> not reusable", n["stamp_ok"](REAL, P0), False)
    n = ns_for(["--gpu", "0", "--plan", "remeasure"])
    try:
        n["start"]()
        got = "no exit"
    except SystemExit as e:
        got = e.code
    check("11e --log == --base_log refused", got, 6)
    check("11f universe 96, flag boundary", (len(n0["screen_universe"]()), n0["flagged"](-5, 100), n0["flagged"](-4, 100)), (96, True, False))
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
