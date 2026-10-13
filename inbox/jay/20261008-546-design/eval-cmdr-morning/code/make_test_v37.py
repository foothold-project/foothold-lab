"""Builds test_v37.py from test_v36.py (lead 10/13, VERIFY-astra-16f 3.1 / 3.2 / 3.3 / 4 and 6 (1)(2)(3))."""
s = open("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/test_v36.py", encoding="utf-8").read()


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"anchor count {n}: {old[:70]!r}"
    s = s.replace(old, new)


rep('"""Known-answer tests for cmdr_eval_driver_v36.py on CPU (lead 10/13, VERIFY-astra-16 9.1 and 16b 2 / 3 / 5).',
    '"""Known-answer tests for cmdr_eval_driver_v37.py on CPU (lead 10/13, VERIFY-astra-16 9.1, 16b 2 / 3 / 5, 16f 6).')
rep('SRCF = os.environ.get("V36_SRC", os.path.join(EV, "cmdr_eval_driver_v36.py"))', 'SRCF = os.environ.get("V37_SRC", os.path.join(EV, "cmdr_eval_driver_v37.py"))')
rep('for pair in json.loads(os.environ.get("V36_MUTATE", "[]")):', 'for pair in json.loads(os.environ.get("V37_MUTATE", "[]")):')
rep('TMP = tempfile.mkdtemp(prefix="v36t_"', 'TMP = tempfile.mkdtemp(prefix="v37t_"')
rep('    ns = {"__file__": SRCF, "__name__": "v36test"}', '    ns = {"__file__": SRCF, "__name__": "v37test"}')
rep('    exec(compile(SRC, "v36", "exec"), ns)', '    exec(compile(SRC, "v37", "exec"), ns)')

rep('''def h(snap):''', '''class FakeProc:
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
    code = ("import msvcrt\\nf = open(r'%s', 'a+b')\\nf.seek(0)\\ntry:\\n    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)\\n"
            "    print('free')\\nexcept OSError:\\n    print('held')\\n") % lockpath
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()


def h(snap):''')

# 8: the launch is POPEN now and goes through the real conversion slot (no foreign process)
rep('''    n["subprocess"] = _ty.SimpleNamespace(run=fake_run)
    n.update(pins=lambda: {"x": 1}, wait_start_slot=lambda sleep=None: None)''',
    '''    n["POPEN"] = popen_from(fake_run)
    n.update(pins=lambda: {"x": 1}, foreign_isaac=lambda procs=None: [])''')
# 14: guarded takes the job's checkpoint now
rep('''    def g(name, cmd, tries=4, wait_s=300):''', '''    def g(name, cmd, tries=4, wait_s=300, ck=None):''')
# 11: ASTRA 16f 3.3 counterexample 2 (validate of a real run with the root reference failure appended)
rep('''    check("11a real run validates on GPU 1", n["validate"](*va), "")''',
    '''    check("11a real run validates on GPU 1", n["validate"](*va), "")
    lp = os.path.join(TMP, REAL + ".log")
    open(lp, "a", encoding="utf-8").write("\\n" + n["ROOT_REF"] + " prim path @/tmp/IsaacLab/x@\\n")
    check("11g the same real run with the robot root reference failure added: invalid (16f 3.3)", n["validate"](*va).startswith("robot root reference unresolved"), True)
    shutil.copy(os.path.join(EV, "out", REAL + ".log"), lp)''')

i = s.index("    # 18 (t) start spacing")
j = s.index("    # 11 earlier checks kept")
NEW = r'''    # 18 (w) stop / deadline / pins / checkpoint while waiting for the slot, and with the slot held: no launch (16f 3.2)
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

    def PR(pid, ppid, ct, *argv, name="python.exe"):
        return {"pid": pid, "ppid": ppid, "create_time": ct, "name": name, "cmdline": list(argv) if argv else None}
    plist = [PR(me, 1, 50, "python.exe", "cmdr_eval_driver_v37.py", "--gpu", "0"),
             PR(1001, 1, 60, "python.exe", "cmdr_eval_driver.py", "--until", "2026-10-13 14:00"),
             PR(1002, 1, 61, "python.exe", "cmdr_eval_driver_v36.py", "--gpu", "0"),
             PR(1030, 1, 100, "python.exe", "C:/x/_eval/cmdr_eval_driver_v37.py", "--gpu", "1"),
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
    check("21 foreign: older drivers, their children, unseen / training launchers, kit, unreadable argv, a reused parent pid; "
          "not: a v3.7 driver, its children, unrelated python",
          sorted(map(str, n["foreign_isaac"](plist))), sorted(map(str, [1001, 1002, 1033, "unknown:1040", 1042, 1043, 1044, 1045, 1046])))

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
                                                                            "origin": "legacy-origin revalidated", "attempt": "v3.2 or earlier"}))
    got_st.clear()
    n["process"](job)
    check("27b a later re-validation does not upgrade the origin", got_st.get("origin"), "legacy-origin revalidated")
    n["stamp_ok"] = lambda t, P: False
    n["guarded"] = lambda name, cmd, tries=4, wait_s=300, ck=None: (0, 1)
    got_st.clear()
    n["process"](job)
    check("27c a new run: hashed-at-collection, no previous stamp fields", (n["LOG"]["runs"][-1]["origin"], got_st.get("origin"), "prev_stamp_sha256" in got_st),
          ("hashed-at-collection", "hashed-at-collection", False))

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

'''
s = s[:i] + NEW + s[j:]
open("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/test_v37.py", "w", encoding="utf-8").write(s)
print("ok")
