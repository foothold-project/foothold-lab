"""Known-answer tests for cmdr_eval_driver_v34.py on CPU (lead 10/13, VERIFY-astra-16 9.1).
Runs the driver's real functions and real main loops (main_remeasure, main_base, start, process) with the side
effects (Isaac runs, file writes, process lists, sleeps) replaced by stubs. Exit code 1 when any check fails."""
import json
import os
import shutil
import sys
import tempfile

EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
SRCF = os.environ.get("V34_SRC", os.path.join(EV, "cmdr_eval_driver_v34.py"))
SRC = open(SRCF, encoding="utf-8").read()
for pair in json.loads(os.environ.get("V34_MUTATE", "[]")):  # break-the-guard: mutate the source copy in memory
    assert SRC.count(pair[0]) == 1, pair[0]
    SRC = SRC.replace(pair[0], pair[1])
REAL = "cq_on22000_flat_stop03_on_s1000"
fails = []
TMP = tempfile.mkdtemp(prefix="v34t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")


def ns_for(argv):
    sys.argv = ["x", "--until", "2099-01-01 00:00"] + argv
    ns = {"__file__": SRCF, "__name__": "v34test"}
    sys.path.insert(0, EV)
    exec(compile(SRC, "v34", "exec"), ns)
    ns["OUT"] = TMP
    ns["LOGF"] = os.path.join(TMP, ns["args"].log + ".json")
    ns["BASEF"] = os.path.join(TMP, ns["args"].base_log + ".json")
    return ns


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:150], "want", repr(want)[:90])
    if not ok:
        fails.append(name)


def remeasure_ns(snaps, writers_seq, data):
    """a remeasure namespace whose base log reads come from `snaps` (one per loop pass, last one repeats),
    whose base writer list comes from `writers_seq`, and whose seed-1000 pass lists come from `data`."""
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t", "--base_log", "baset"])
    calls = {"read": 0, "writers": 0, "processed": [], "sleeps": 0}

    def read_base():
        calls["read"] += 1
        return snaps[min(calls["read"], len(snaps)) - 1]

    def writers(_):
        calls["writers"] += 1
        return writers_seq[min(calls["writers"], len(writers_seq)) - 1]

    def process(pick, reuse_only=False):
        t = n["tagof"](*pick)
        calls["processed"].append(t)
        n["LOG"]["matrix"][t] = "valid"
        return True

    def sleep(_):
        calls["sleeps"] += 1
        if calls["sleeps"] > 50:
            raise RuntimeError("loop did not end")

    n.update(read_base=read_base, driver_writers=writers, process=process, ready=lambda m: True, save=lambda force=False: None,
             main_pass=lambda tag, cell: data[tag])
    return n, calls, sleep


def pair(n, fam, cell, noise, off, on):
    T = n["tagof"]
    a, b = T("off24000", fam, cell, noise, 1000), T("on24000", fam, cell, noise, 1000)
    return {a: [e < off for e in range(100)], b: [e < on for e in range(100)]}


try:
    # ---- 1 the S0 / S1 race (VERIFY-astra-16 6.1): the last pair arrives together with "ended"
    n0 = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t", "--base_log", "baset"])
    data = {**pair(n0, "wave", "stand", True, 60, 60), **pair(n0, "wave", "fwd03", True, 60, 50)}
    T = n0["tagof"]
    first = {T("off24000", "wave", "stand", True, 1000): "valid", T("on24000", "wave", "stand", True, 1000): "valid",
             T("off24000", "wave", "fwd03", True, 1000): "valid"}
    last = dict(first, **{T("on24000", "wave", "fwd03", True, 1000): "valid"})
    base = {"version": "3.4", "experiment": n0["EXPERIMENT"]}
    S0 = dict(base, matrix=first)
    S1 = dict(base, matrix=last, ended="t", complete=True)
    n, calls, sleep = remeasure_ns([S0, S1], [[]], data)
    n["main_remeasure"](sleep=sleep)
    want = sorted(T(m, "wave", "fwd03", True, s) for s in (1001, 1002, 1003, 1004) for m in ("off24000", "on24000"))
    check("1a last pair in the final snapshot is flagged and remeasured", sorted(calls["processed"]), want)
    check("1b flagged list", n["LOG"]["flagged"], ["wave/fwd03/on"])
    check("1c not complete: most planned screen cells never measured", (n["LOG"]["complete"], len(n["LOG"]["screen_unmeasured"])),
          (False, len(n["screen_universe"]()) - 2))

    # ---- 2 an "ended" base log while a base writer is alive (a restart re-validating) must not end the remeasure
    n, calls, sleep = remeasure_ns([S1], [[777], [777], [777], []], data)
    n["main_remeasure"](sleep=sleep)
    check("2a waited for the writer to go before ending", calls["writers"] >= 4 and n["LOG"]["base_seen"]["final"], True)
    check("2b remeasure still done", sorted(calls["processed"]), want)
    # with nothing flagged, the loop must still wait for the writer: 3 passes with a writer, end on the 4th read
    quiet = {**pair(n0, "wave", "stand", True, 60, 60), **pair(n0, "wave", "fwd03", True, 60, 60)}
    n, calls, sleep = remeasure_ns([S1], [[777], [777], [777], []], quiet)
    n["main_remeasure"](sleep=sleep)
    check("2a2 nothing flagged: ended only after the writer was gone", (calls["read"], calls["processed"]), (4, []))
    # an older version's end record never counts
    n, calls, sleep = remeasure_ns([dict(S1, version="3.3"), S1], [[]], data)
    n["main_remeasure"](sleep=sleep)
    check("2c v3.3 end record ignored (needed a second read)", calls["read"] >= 2, True)

    # ---- 3 base stopped by the deadline, incomplete: remeasure ends, complete False, lists say why
    S2 = dict(base, matrix=last, stopped="deadline", complete=None)
    n, calls, sleep = remeasure_ns([S2], [[]], data)
    n["main_remeasure"](sleep=sleep)
    check("3 stopped base -> not complete", (n["LOG"]["complete"], bool(n["LOG"]["screen_unmeasured"])), (False, True))
    # a remeasure group with one invalid run is listed
    n, calls, sleep = remeasure_ns([S1], [[]], data)
    orig = n["process"]

    def process_bad(pick, reuse_only=False):
        orig(pick)
        if pick[0] == "on24000" and pick[4] == 1003:
            n["LOG"]["matrix"][n["tagof"](*pick)] = "invalid"
        return True
    n["process"] = process_bad
    n["main_remeasure"](sleep=sleep)
    check("3b invalid remeasure run listed as missing", n["LOG"]["remeasure_missing"], [T("on24000", "wave", "fwd03", True, 1003)])

    # ---- 4 start(): same log refused, a second writer refused (process scans, pins, waits and sleeps stubbed so only
    #      the check under test can stop start(); the live v3.2 driver must not decide the result)
    import time as _t
    import types as _ty

    def quiet_start(n):
        n.update(driver_writers=lambda name: [], pins=lambda: {"q_eval_cmdr.py": "x" * 16}, unseen_running=lambda: False,
                 live_runs=lambda tags: [], training_done=lambda: "", ready=lambda m: True, save=lambda force=False: None,
                 time=_ty.SimpleNamespace(time=_t.time, strftime=_t.strftime, sleep=lambda x: None, mktime=_t.mktime,
                                          strptime=_t.strptime, localtime=_t.localtime))
        return n
    n = quiet_start(ns_for(["--gpu", "0", "--plan", "remeasure"]))
    try:
        n["start"]()
        got = "no exit"
    except SystemExit as e:
        got = e.code
    check("4a --log == --base_log refused", got, 6)
    n = quiet_start(ns_for(["--gpu", "1", "--plan", "base", "--log", "baset"]))
    n["driver_writers"] = lambda name: [4242] if name == "baset" else []
    try:
        n["start"]()
        got = "no exit"
    except SystemExit as e:
        got = e.code
    check("4b second writer of the same log refused", got, 6)
    n = quiet_start(ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t", "--base_log", "baset"]))
    try:
        n["start"]()
        got = "no exit"
    except SystemExit as e:
        got = e.code
    check("4c different logs, no writer, GPU handed over -> start returns", (got, "gpu0_from" in n["LOG"]), ("no exit", True))
    seq = ["", "branch_run.py still running", "", "", ""]
    looks = []

    def td():
        looks.append(1)
        return seq[len(looks) - 1]
    n = quiet_start(ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t", "--base_log", "baset"]))
    n["training_done"] = td
    n["start"]()
    check("4d GPU 0 needs two clean looks in a row (ok, not ok, ok, ok -> 4 looks)", len(looks), 4)

    # ---- 5 stamps
    n = ns_for(["--gpu", "1"])
    d = os.path.join(TMP, REAL)
    shutil.copytree(os.path.join(EV, "out", REAL), d)
    P = json.load(open(os.path.join(d, "driver_stamp.json"), encoding="utf-8"))["pins"]
    check("5a v3.2 stamp (pins only) accepted", n["stamp_ok"](REAL, P), True)
    open(os.path.join(d, "driver_stamp.json"), "w").write("{")
    check("5b cut stamp -> not reusable, no crash", (n["old_stamp"](REAL), n["stamp_ok"](REAL, P)), ({}, False))
    json.dump({"pins": P, "stamp_version": "3.4"}, open(os.path.join(d, "driver_stamp.json"), "w"))
    check("5c new stamp without hashes refused", n["stamp_ok"](REAL, P), False)
    n["write_stamp"](REAL, P, {"out_sha256": n["outhash"](REAL)})
    check("5d written stamp ok, no tmp left", (n["stamp_ok"](REAL, P), [f for f in os.listdir(d) if f.endswith(".tmp")]), (True, []))

    # ---- 6 earlier checks on the real run (validate, negative / NaN max_abs, GPU UUID)
    for ext in (".log", ".guard.json"):
        shutil.copy(os.path.join(EV, "out", REAL + ext), os.path.join(TMP, REAL + ext))
    shutil.copy(os.path.join(EV, "out", REAL, "driver_stamp.json"), os.path.join(d, "driver_stamp.json"))
    drv = json.load(open(os.path.join(EV, "out", "cmdr_eval_driver.json"), encoding="utf-8"))
    va = (REAL, drv["ckpt"]["on22000"]["sha256"], 22000, "flat", ["stop03"], 100, True, 1000, True)
    check("6a real run validates on GPU 1", n["validate"](*va), "")
    check("6b same run under --gpu 0 -> gpu uuid", ns_for(["--gpu", "0", "--log", "g0t"])["validate"](*va), "gpu uuid")
    mp = os.path.join(d, "meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    for v, name in ((-1.0, "6c negative"), (float("nan"), "6d NaN")):
        meta["checks_run"]["obs_single_cmd_vs_target_max_abs"] = v
        json.dump(meta, open(mp, "w", encoding="utf-8"))
        check(f"{name} max_abs rejected", n["validate"](*va).startswith("checks_run"), True)
    shutil.copy(os.path.join(EV, "out", REAL, "meta.json"), mp)

    # ---- 7 GPU 0 hand-over needs every sign
    n = ns_for(["--gpu", "0", "--plan", "remeasure", "--log", "g0t"])
    bdir = os.path.join(TMP, "branch")
    on = os.path.join(bdir, "cmdr_s1042_on_u4000")
    os.makedirs(on)
    n["B"] = bdir
    n["NIGHT_OUT"] = os.path.join(bdir, "night.out")
    n["MODELS"] = dict(n["MODELS"], on24000=(os.path.join(on, "model_24000.pt"), 24000))
    n["training_running"] = lambda: False
    n["gpu_used_mib"] = lambda g: 900
    check("7a no result.json", n["training_done"](), "on arm has no result.json")
    open(os.path.join(on, "result.json"), "w").write("{}")
    check("7b no checkpoint", n["training_done"](), "no model_24000.pt")
    open(os.path.join(on, "model_24000.pt"), "w").write("x")
    check("7c no night log", n["training_done"](), "no night log")
    open(n["NIGHT_OUT"], "w").write("cmdr_s1042_on_u4000 EXIT 0\n")
    check("7d night log without NIGHT DONE", n["training_done"](), "night log has no NIGHT DONE")
    open(n["NIGHT_OUT"], "a").write("NIGHT DONE 2026-10-13 11:30:00\n")
    check("7e all signs -> handed over", n["training_done"](), "")
    n["training_running"] = lambda: True
    check("7f branch_run alive", n["training_done"](), "branch_run.py still running")
    n["training_running"] = lambda: False
    n["gpu_used_mib"] = lambda g: 13954
    check("7g GPU memory still held", n["training_done"](), "GPU 0 memory used 13954 MiB")

    # ---- 8 main_base: nothing written before the re-validation pass, then the whole table at once; end lists
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "baset"])
    js = n["jobs"]()[:5]
    n["jobs"] = lambda: js
    n["ready"] = lambda m: True
    seen = {"exists_during_reuse": [], "matrix_at_tests": None}

    def process(pick, reuse_only=False):
        t = n["tagof"](*pick)
        if reuse_only:
            seen["exists_during_reuse"].append(os.path.exists(n["LOGF"]))
            if pick in js[:3]:
                n["LOG"]["matrix"][t] = "valid"
                n["LOG"]["runs"].append({"tag": t})
                n["save"]()
                return True
            return False
        n["LOG"]["matrix"][t] = "invalid" if pick == js[4] else "valid"
        n["save"]()
        return True

    def run_tests():
        seen["matrix_at_tests"] = len(json.load(open(n["LOGF"], encoding="utf-8"))["matrix"])
    n.update(process=process, run_tests=run_tests)
    n["main_base"]()
    check("8a no base log written during the re-validation pass", seen["exists_during_reuse"], [False] * 5)
    check("8b whole re-validated table written before the start tests", seen["matrix_at_tests"], 3)
    L = json.load(open(n["LOGF"], encoding="utf-8"))
    check("8c end record: one invalid -> not complete and listed", (L["complete"], L["not_valid"], L["not_run"]), (False, [n["tagof"](*js[4])], []))

    # ---- 9 process(): every new run has its own attempt id, carried into the stamp
    n = ns_for(["--gpu", "1", "--plan", "base", "--log", "baset"])
    n["P0"] = {"x": 1}
    stamps = []
    n.update(pins=lambda: {"x": 1}, sha=lambda p: "c", stamp_ok=lambda t, P: False, guarded=lambda name, cmd: (0, 1),
             validate=lambda *a, **k: "", outhash=lambda t: {"h": t}, diag_warns=lambda t: [], fingerprint=lambda t: {"f": 1},
             write_stamp=lambda t, P, extra: stamps.append(extra["attempt"]), save=lambda force=False: None, old_stamp=lambda t: {})
    n["LOG"]["ckpt"] = {m: {"sha256": "c"} for m in n["MODELS"]}
    n["process"](n["jobs"]()[0])
    n["process"](n["jobs"]()[1])
    check("9 two runs, two attempt ids", (len(set(stamps)), stamps[0].endswith("-j1"), stamps[1].endswith("-j2")), (2, True, True))

    # ---- 10 screen boundary on the real function: -5 pp flags, -4 pp does not; targets never screened
    n0["main_pass"] = lambda tag, cell: data2[tag]
    data2 = {**pair(n0, "wave", "fwd03", True, 50, 45), **pair(n0, "wave", "back03", True, 50, 46), **pair(n0, "flat", "fwd01", True, 50, 10)}
    sc = n0["screen"](set(data2))
    check("10a keys (flat noise-on target skipped)", sorted(sc), [("wave", "back03", True), ("wave", "fwd03", True)])
    check("10b flags", [n0["flagged"](*sc[("wave", "fwd03", True)]), n0["flagged"](*sc[("wave", "back03", True)])], [True, False])
    check("10c universe size (8 families x 11 + flat noise off 11, minus 3 targets)", len(n0["screen_universe"]()), 96)
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
