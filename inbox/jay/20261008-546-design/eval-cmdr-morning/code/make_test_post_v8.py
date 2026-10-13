"""Builds test_post_v8.py from test_post_v7.py (lead 10/13, VERIFY-astra-16g 3 / 4 / 5 / 7)."""
s = open("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/test_post_v7.py", encoding="utf-8").read()


def rep(old, new):
    global s
    n = s.count(old)
    assert n == 1, f"anchor count {n}: {old[:70]!r}"
    s = s.replace(old, new)


rep('"""Known-answer tests for cmdr_post_v7.py', '"""Known-answer tests for cmdr_post_v8.py')
rep('POST = os.environ.get("POST_V7", "cmdr_post_v7.py")', 'POST = os.environ.get("POST_V8", "cmdr_post_v8.py")')
rep('ROOT = tempfile.mkdtemp(prefix="p7t_"', 'ROOT = tempfile.mkdtemp(prefix="p8t_"')
rep('("cmdr_post v7", [], 30))', '("cmdr_post v8", [], 30))')

# the fake logs carry real run records (tag, valid, attempt, output hashes) and the new stamps carry the attempt (16g 3.1)
rep('''        self.logs = {"cmdr_eval_driver": {}, "cmdr_eval_driver_g0": {}}''',
    '''        self.logs = {"cmdr_eval_driver": {}, "cmdr_eval_driver_g0": {}}
        self.recs = {"cmdr_eval_driver": [], "cmdr_eval_driver_g0": []}''')
rep('''            json.dump({"pins": PINS, "ckpt_sha256": CKPT[m], "stamp_version": "3.5", "out_sha256": h}, open(os.path.join(d, "driver_stamp.json"), "w"))''',
    '''            json.dump({"pins": PINS, "ckpt_sha256": CKPT[m], "stamp_version": "3.5", "out_sha256": h, "attempt": tag + "-A1"},
                      open(os.path.join(d, "driver_stamp.json"), "w"))
            self.recs[log].append({"tag": tag, "valid": True, "attempt": tag + "-A1", "out_sha256": h})''')
rep('''            json.dump({"pins": PINS, "ckpt_sha256": CKPT[m], "pair_ref": tag}, open(os.path.join(d, "driver_stamp.json"), "w"))''',
    '''            json.dump({"pins": PINS, "ckpt_sha256": CKPT[m], "pair_ref": tag}, open(os.path.join(d, "driver_stamp.json"), "w"))
            self.recs[log].append({"tag": tag, "valid": True})''')
rep('''"runs": [1] * len(m),''', '''"runs": self.recs[name],''')

# R1: v8 stats every file around its read, so a CSV that changes while it is read stops the aggregate
rep('''    check("R1 CSV changed right after its read: the aggregate uses the bytes it hashed (-10 pp, not +40)",
          (code, round(rr["regression_24000"]["wave/fwd03/on"]["screen_diff"], 9)), (0, -0.1))''',
    '''    check("R1 CSV changed while it was read: exit 3, nothing written (v7 used the bytes it hashed; v8 stops)",
          (code, os.path.exists(os.path.join(RR.out, "cmdr_post.json"))), (3, False))''')
rep('''    code = run_hooked(RR.out, csvp, flip)
    rr = json.load(open(os.path.join(RR.out, "cmdr_post.json"), encoding="utf-8"))''', '''    code = run_hooked(RR.out, csvp, flip)''')

# F: v8 vs v7 on real data
rep('''    r5, r6 = (tempfile.mkdtemp(prefix=f"real{v}_", dir=ROOT) for v in (6, 7))''', '''    r5, r6 = (tempfile.mkdtemp(prefix=f"real{v}_", dir=ROOT) for v in (7, 8))''')
rep('''        for dest, script in ((r5, "cmdr_post_v6.py"), (r6, POST)):''', '''        for dest, script in ((r5, "cmdr_post_v7.py"), (r6, POST)):''')
rep('''    check("F1 real data, one snapshot: v7 = v6 on 22,000 targets, same runs, no auth failures",''', '''    check("F1 real data, one snapshot: v8 = v7 on 22,000 targets, same runs, no auth failures",''')

# L: the 16g counterexamples, the hold, origins; G12: no result file is not "training"
i = s.index("    # F: real out/, read only")
s = s[:i] + r'''    # L1 (16g 3.1) the log still publishes the older run; a newer, normal stamp over new bytes must not be used
    t_off, t_on = T("off24000", "wave", "fwd03", "on", 1000), T("on24000", "wave", "fwd03", "on", 1000)
    LK = Fake("L1")
    LK.run(t_off, 60)
    LK.run(t_on, 50)
    d_on = os.path.join(LK.out, t_on)
    rows = list(csv.DictReader(open(os.path.join(d_on, "episodes.csv"), encoding="utf-8")))
    for r in rows:
        r["span_q1_pass"] = "True"
    with open(os.path.join(d_on, "episodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    h2 = {f_: hashlib.sha256(open(os.path.join(d_on, f_), "rb").read()).hexdigest() for f_ in OUT4}
    json.dump({"pins": PINS, "ckpt_sha256": CKPT["on24000"], "stamp_version": "3.7", "out_sha256": h2, "attempt": "NEW-j1"},
              open(os.path.join(d_on, "driver_stamp.json"), "w"))
    LK.go()
    check("L1 newer normal stamp over a log that published the older run: excluded, no +40 comparison",
          (LK.rc, [(a["tag"], a["why"]) for a in LK.res["auth_fail"]], "wave/fwd03/on" in LK.res["regression_24000"]),
          (0, [(t_on, "stamp hashes differ from its log's run record")], False))
    LK2 = Fake("L1b")
    LK2.run(t_off, 60)
    LK2.run(t_on, 50)
    sp_ = os.path.join(LK2.out, t_on, "driver_stamp.json")
    st_ = json.load(open(sp_))
    st_["attempt"] = "NEW-j1"
    json.dump(st_, open(sp_, "w"))
    LK2.go()
    check("L1b same bytes, other attempt than the record: excluded", [(a["tag"], a["why"]) for a in LK2.res["auth_fail"]],
          [(t_on, "stamp attempt differs from its log's run record")])

    # L2 (16g 3.2) a legacy run: a file read earlier is replaced while a later one is read -> the end check stops it
    LS = Fake("L2")
    LS.run(t_off, 60, stamp="legacy")
    LS.run(t_on, 50, stamp="legacy")
    LS.go({"cmdr_eval_driver": {"version": "3.2"}})
    check("L2 control: legacy pair in a v3.2 log runs", (LS.rc, LS.res["legacy_stamps"]), (0, 2))
    os.remove(os.path.join(LS.out, "cmdr_post.json"))
    mp_ = os.path.join(LS.out, t_on, "meta.json")
    code = run_hooked(LS.out, os.path.join(LS.out, t_on, "episodes.csv"), lambda: open(mp_, "a").write(" "))
    check("L2 meta.json replaced after it was read (while the CSV is read): exit 3, nothing written",
          (code, os.path.exists(os.path.join(LS.out, "cmdr_post.json"))), (3, False))

    # L3 a restarted owner is re-validating: held, nothing written; a matching running attempt is read
    LH = Fake("L3")
    LH.run(t_off, 60)
    LH.run(t_on, 50)
    json.dump({"attempt": "NEW", "state": "revalidating"}, open(os.path.join(LH.out, "cmdr_eval_driver.attempt.json"), "w"))
    LH.go({"cmdr_eval_driver": {"attempt": "OLD"}})
    check("L3 owner re-validating: exit 5, nothing written", (LH.rc, os.path.exists(os.path.join(LH.out, "cmdr_post.json"))), (5, False))
    json.dump({"attempt": "OLD", "state": "running"}, open(os.path.join(LH.out, "cmdr_eval_driver.attempt.json"), "w"))
    LH.go({"cmdr_eval_driver": {"attempt": "OLD"}})
    check("L3b attempt file running, same attempt as the log: read", LH.rc, 0)
    json.dump({"attempt": "OTHER", "state": "running"}, open(os.path.join(LH.out, "cmdr_eval_driver.attempt.json"), "w"))
    os.remove(os.path.join(LH.out, "cmdr_post.json"))
    LH.go({"cmdr_eval_driver": {"attempt": "OLD"}})
    check("L3c attempt file names another attempt than the log: held", LH.rc, 5)

    # L4 (16g 4) origins are kept per run and counted
    LO = Fake("L4")
    LO.run(t_off, 60)
    LO.run(t_on, 50)
    sp_ = os.path.join(LO.out, t_on, "driver_stamp.json")
    st_ = json.load(open(sp_))
    st_["origin"] = "legacy-origin revalidated"
    json.dump(st_, open(sp_, "w"))
    LO.go()
    me = LO.res["inputs_manifest"][t_on]
    check("L4 origin per run and counted; record and stamp attempts and the stamp hash kept",
          (LO.res["origin_counts"], me["record_attempt"] == me["stamp_attempt"] == t_on + "-A1", len(me["stamp_sha256"]), me["owner"]),
          ({"hashed (stamp has no origin field)": 1, "legacy-origin revalidated": 1}, True, 64, "cmdr_eval_driver"))

''' + s[i:]

rep('''    check("G11 seed ids in the per-seed list", "1000 +" in g3["cmdr_status"] or "1000 -" in g3["cmdr_status"], True)''',
    '''    check("G11 seed ids in the per-seed list", "1000 +" in g3["cmdr_status"] or "1000 -" in g3["cmdr_status"], True)
    ev_real = FC.EV
    FC.EV = os.path.join(ROOT, "no_branch_here")
    g12 = FC.build(post_path=os.path.join(C.out, "cmdr_post.json"), summary_path=summ)
    FC.EV = ev_real
    check("G12 (16g 5.1) no result file: says only what is seen", ("현재 상태 미확인" in g12["cmdr_train_status"], "학습 중" in g12["cmdr_train_status"]), (True, False))
    g13 = FC.build(post_path=os.path.join(LO.out, "cmdr_post.json"), summary_path=summ)
    check("G13 (16g 4) the status line shows the origins", ("구형 출처 · 재검사 때 해시 1" in g13["cmdr_status"] or "구형 출처 · 재검사 때 해시 1" in " ".join(str(v) for v in g13.values())), True)''')
open("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/test_post_v8.py", "w", encoding="utf-8").write(s)
print("ok")
