"""Known-answer tests for cmdr_eval_driver_v35.py on CPU (lead 10/13, VERIFY-astra-16 9.1 and 16b 2 / 3 / 5).
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
SRCF = os.environ.get("V35_SRC", os.path.join(EV, "cmdr_eval_driver_v35.py"))
SRC = open(SRCF, encoding="utf-8").read()
for pair in json.loads(os.environ.get("V35_MUTATE", "[]")):  # break-the-guard: mutate the source copy in memory
    assert SRC.count(pair[0]) == 1, pair[0]
    SRC = SRC.replace(pair[0], pair[1])
REAL = "cq_on22000_flat_stop03_on_s1000"
fails = []
TMP = tempfile.mkdtemp(prefix="v35t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")


def ns_for(argv):
    sys.argv = ["x", "--until", "2099-01-01 00:00"] + argv
    ns = {"__file__": SRCF, "__name__": "v35test"}
    sys.path.insert(0, EV)
    exec(compile(SRC, "v35", "exec"), ns)
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


def h(snap):
    return hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest() if snap is not None else None


def remeasure_ns(snaps, writers_seq, data, ready=lambda m: True, clock=None, deadline=None):
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
             save=lambda force=False: None, main_pass=lambda tag, cell: data[tag])
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
    base = {"version": V, "experiment": EXP}
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
    check("2b writer alive on reads 1-3: ends on read 4 (writer gone, same bytes as read 3)", (calls["read"], calls["processed"]), (4, []))
    n, calls, sleep = remeasure_ns([S1], [[]], quiet)
    n["lock_held"] = lambda name: calls["read"] < 3
    n["main_remeasure"](sleep=sleep)
    check("2c base lock held on reads 1-2 counts as a writer: ends on read 3", calls["read"], 3)

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

    # 7 one exit record for every way out (16b 3)
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "exitt"])
    json.dump({"matrix": {"old": "valid"}}, open(n["LOGF"], "w"))

    def boom():
        raise SystemExit(4)
    n["start"] = boom
    try:
        n["main"]()
    except SystemExit:
        pass
    old = json.load(open(n["LOGF"]))
    st = json.load(open(os.path.join(TMP, "exitt.stopped.json")))
    check("7a exit during re-validation: old table kept, stop record beside it", (old, st["exit_code"], st["stopped"]), ({"matrix": {"old": "valid"}}, 4, "exit 4"))
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "exitr", "--base_log", "baset"])
    n["start"] = lambda: None
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
    check("7b exception: exit record in the log with not_run", (L["exit_code"], L["stopped"], L["not_run"]), (1, "ValueError: x", ["cq_on24000_wave_fwd03_on_s1001"]))

    # 8 guard retries keep their own evidence (16b 3)
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "gtt"])
    n["P0"] = {"x": 1}
    rcs = [99, 0]

    def fake_run(cmd, **k):
        name = cmd[cmd.index("--log") + 1].split("/")[-1][:-4]
        open(os.path.join(TMP, name + ".log"), "w").write(f"try rc {rcs[0]}\n")
        open(os.path.join(TMP, name + ".guard.json"), "w").write("{}")
        return _ty.SimpleNamespace(returncode=rcs.pop(0))
    n["subprocess"] = _ty.SimpleNamespace(run=fake_run)
    n.update(pins=lambda: {"x": 1})
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

    # 11 earlier checks kept: real run validate, negative / NaN max_abs, gpu uuid, stamps, refusal of same log
    n = ns_for(["--gpu", "1"])
    d = os.path.join(TMP, REAL)
    shutil.copytree(os.path.join(EV, "out", REAL), d)
    for ext in (".log", ".guard.json"):
        shutil.copy(os.path.join(EV, "out", REAL + ext), os.path.join(TMP, REAL + ext))
    drv = json.load(open(os.path.join(EV, "out", "cmdr_eval_driver.json"), encoding="utf-8"))
    va = (REAL, drv["ckpt"]["on22000"]["sha256"], 22000, "flat", ["stop03"], 100, True, 1000, True)
    check("11a real run validates on GPU 1", n["validate"](*va), "")
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
