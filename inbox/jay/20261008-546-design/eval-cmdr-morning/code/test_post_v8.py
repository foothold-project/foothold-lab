"""Known-answer tests for cmdr_post_v8.py and the page layer facts5_cmdr.py (lead 10/13, VERIFY-astra-16c 2 / 5).
Fake out/ folders are built from copies of real run folders OF THE SAME CELL; the main pass column gets the pattern and the
other pass columns the opposite (reading the wrong column fails a check). Every fixture run carries the real stamp schema
(pins, checkpoint, stamp_version, four output hashes) unless a case breaks it on purpose. Never writes to the real out/.
Exit code 1 when any check fails."""
import csv
import builtins
import io
import runpy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
SRC = os.path.join(EV, "out")
PY = sys.executable
POST = os.environ.get("POST_V8", "cmdr_post_v8.py")
COLS = ("span_q2_pass", "span_q1a_pass", "span_q1_pass")
MAIN = {"stop03": "span_q2_pass", "fwd01": "span_q1a_pass", "fwd02": "span_q1a_pass", "fwd03": "span_q1_pass", "stand": "span_q1_pass",
        "back03": "span_q1_pass", "left03": "span_q1_pass", "right03": "span_q1_pass"}
PINS = {k: "h_" + k for k in ("q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py")}
CKPT = {"off24000": "ck_off", "on24000": "ck_on", "off22000": "ck_off22", "on22000": "ck_on22", "p20000": "ck_p"}
OUT4 = ("meta.json", "cells.json", "episodes.csv", "traj.npz")
OK_LABEL, BAD_LABEL = "퇴행 방지 조건 충족 (통과율 · MAE)", "퇴행 방지 조건 미충족"
fails = []
ROOT = tempfile.mkdtemp(prefix="p8t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:150], "want", repr(want)[:100])
    if not ok:
        fails.append(name)


def T(m, fam, cell, noise, s):
    return f"cq_{m}_{fam}_{cell}_{noise}_s{s}"


class Fake:
    def __init__(self, name):
        self.out = os.path.join(ROOT, name)
        os.makedirs(self.out)
        self.logs = {"cmdr_eval_driver": {}, "cmdr_eval_driver_g0": {}}
        self.recs = {"cmdr_eval_driver": [], "cmdr_eval_driver_g0": []}

    def run(self, tag, passes, surv_false=0, mae=None, mae_list=None, log="cmdr_eval_driver", stamp="new"):
        cell = tag.split("_")[-3]
        src = f"cq_off22000_flat_{cell}_on_s{tag.rsplit('_s', 1)[1]}"
        if not os.path.exists(os.path.join(SRC, src)):
            src = f"cq_off22000_flat_{cell}_on_s1000"
        d = os.path.join(self.out, tag)
        shutil.copytree(os.path.join(SRC, src), d)
        p = os.path.join(d, "episodes.csv")
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        assert all(r["cell"] == cell for r in rows), "fixture cell"
        for r in rows:
            e = int(r["episode"])
            for col in COLS:
                hit = e < passes
                r[col] = str(hit if col == MAIN[cell] else not hit)
            r["span_survived"] = "False" if e < surv_false else "True"
            if mae is not None:
                r["mae_vx"] = str(mae)
            if mae_list is not None:
                r["mae_vx"] = str(mae_list[e])
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        os.remove(os.path.join(d, "driver_stamp.json"))
        m = tag.split("_")[1]
        if stamp == "new":
            h = {f: hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest() for f in OUT4}
            json.dump({"pins": PINS, "ckpt_sha256": CKPT[m], "stamp_version": "3.5", "out_sha256": h, "attempt": tag + "-A1"},
                      open(os.path.join(d, "driver_stamp.json"), "w"))
            self.recs[log].append({"tag": tag, "valid": True, "attempt": tag + "-A1", "out_sha256": h})
        elif stamp == "legacy":
            json.dump({"pins": PINS, "ckpt_sha256": CKPT[m], "pair_ref": tag}, open(os.path.join(d, "driver_stamp.json"), "w"))
            self.recs[log].append({"tag": tag, "valid": True})
        self.logs[log][tag] = "valid"

    def go(self, extra_logs=None):
        for name, m in self.logs.items():
            body = {"version": "3.5", "experiment": "cmdr_s1042_pair_eval", "matrix": m, "pair_fail": [], "skipped": [], "runs": self.recs[name],
                    "pins": dict(PINS), "ckpt": {k: {"sha256": v} for k, v in CKPT.items()}}
            body.update((extra_logs or {}).get(name, {}))
            json.dump(body, open(os.path.join(self.out, f"{name}.json"), "w"))
        env = dict(os.environ, CMDR_POST_OUT=self.out, CMDR_POST_DEST=self.out, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES="")
        r = subprocess.run([PY, POST], cwd=EV, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.rc, self.err = r.returncode, r.stderr
        if r.returncode == 0:
            self.res = json.load(open(os.path.join(self.out, "cmdr_post.json"), encoding="utf-8"))
        return self


try:
    # A: targets complete, +5 / +10 / +15 -> mean exactly +10, all low ends > 0 -> 개선
    A = Fake("A")
    for s in range(1000, 1005):
        for cell, on in (("stop03", 55), ("fwd01", 60), ("fwd02", 65)):
            A.run(T("off24000", "flat", cell, "on", s), 50)
            A.run(T("on24000", "flat", cell, "on", s), on)
    A.go()
    check("A0 runs", A.rc, 0)
    tv = A.res["target_verdict"]["24000"]
    check("A1 complete, 500 pairs each", (tv["complete"], tv["n_pairs"]), (True, {"stop03": 500, "fwd01": 500, "fwd02": 500}))
    check("A2 +5 +10 +15 -> 개선", (tv["all_low_above_0"], round(tv["mean_pp"], 9), tv["verdict"]), (True, 10.0, "개선"))
    check("A3 stop03 read from span_q2", round(A.res["targets"]["stop03"]["on_minus_off_24000"]["diff"], 9), 0.05)
    check("A4 schema, no auth failures, manifest of every used run", (A.res["schema"], A.res["auth_fail"], len(A.res["inputs_manifest"])), ("cmdr_post v8", [], 30))

    # B: 100 pairs and 400 pairs -> 보류
    B = Fake("B")
    for cell in ("stop03", "fwd01", "fwd02"):
        B.run(T("off24000", "flat", cell, "on", 1000), 40)
        B.run(T("on24000", "flat", cell, "on", 1000), 80)
    B.go()
    tv = B.res["target_verdict"]["24000"]
    check("B1 100 pairs: 보류", (tv["complete"], tv["verdict"], tv["seeds_missing"]["stop03"], "mean_pp" in tv), (False, "수집 중 · 결합 판정 보류", [1001, 1002, 1003, 1004], False))
    B2 = Fake("B2")
    for s in range(1000, 1004):
        for cell in ("stop03", "fwd01", "fwd02"):
            B2.run(T("off24000", "flat", cell, "on", s), 40)
            B2.run(T("on24000", "flat", cell, "on", s), 80)
    B2.go()
    check("B2 400 pairs: 보류", B2.res["target_verdict"]["24000"]["verdict"], "수집 중 · 결합 판정 보류")

    # C: regression rows
    C = Fake("C")
    C.run(T("off24000", "wave", "stand", "on", 1000), 97, mae=0.1)
    C.run(T("on24000", "wave", "stand", "on", 1000), 97, mae=0.5)
    C.run(T("off24000", "slope_up", "stand", "on", 1000), 97, mae=0.1)
    C.run(T("on24000", "slope_up", "stand", "on", 1000), 97, mae="nan")
    C.run(T("off24000", "obstacles", "fwd03", "on", 1000), 60)
    C.run(T("on24000", "obstacles", "fwd03", "on", 1000), 56)
    C.run(T("off24000", "rough_slope", "fwd03", "on", 1000), 60)
    C.run(T("on24000", "rough_slope", "fwd03", "on", 1000), 50)
    for s in range(1001, 1005):
        C.run(T("off24000", "rough_slope", "fwd03", "on", s), 60, log="cmdr_eval_driver_g0")
        C.run(T("on24000", "rough_slope", "fwd03", "on", s), 60, log="cmdr_eval_driver_g0")
    C.run(T("off24000", "stairs_up", "fwd03", "on", 1000), 60)
    C.run(T("on24000", "stairs_up", "fwd03", "on", 1000), 40)
    for s in (1001, 1002):
        C.run(T("off24000", "stairs_up", "fwd03", "on", s), 60, log="cmdr_eval_driver_g0")
        C.run(T("on24000", "stairs_up", "fwd03", "on", s), 40, log="cmdr_eval_driver_g0")
    C.run(T("off24000", "wave", "fwd03", "on", 1000), 50)
    C.run(T("on24000", "wave", "fwd03", "on", 1000), 50)
    C.run(T("off24000", "slope_down", "stand", "on", 1000), 97, mae=0.1)  # C9 1 of 100 finite
    C.run(T("on24000", "slope_down", "stand", "on", 1000), 97, mae_list=[0.1] + ["nan"] * 99)
    C.run(T("off24000", "stairs_down", "stand", "on", 1000), 97, mae=0.1)  # C10 99 of 100 finite
    C.run(T("on24000", "stairs_down", "stand", "on", 1000), 97, mae_list=[0.1] * 99 + ["nan"])
    C.run(T("off24000", "wave", "back03", "on", 1000), 97, mae=0.30)  # C11 exactly +10 %
    C.run(T("on24000", "wave", "back03", "on", 1000), 97, mae=0.33)
    C.run(T("off24000", "wave", "left03", "on", 1000), 97, mae=0.30)  # C12 +10.03 %
    C.run(T("on24000", "wave", "left03", "on", 1000), 97, mae=0.3301)
    C.run(T("off24000", "slope_down", "fwd03", "on", 1000), 60)  # C14 flagged, on seed 1003 vx 1 finite
    C.run(T("on24000", "slope_down", "fwd03", "on", 1000), 50)
    for s_ in range(1001, 1005):
        C.run(T("off24000", "slope_down", "fwd03", "on", s_), 60, log="cmdr_eval_driver_g0")
        C.run(T("on24000", "slope_down", "fwd03", "on", s_), 60, log="cmdr_eval_driver_g0", mae_list=([0.1] + ["nan"] * 99) if s_ == 1003 else None)
    C.run(T("off24000", "wave", "right03", "on", 1000), 97, mae=0.0)  # C15 control 0 -> absolute line 0.015
    C.run(T("on24000", "wave", "right03", "on", 1000), 97, mae=0.0150001)
    C.go()
    check("C0 runs", C.rc, 0)
    R = C.res["regression_24000"]
    r1 = R["wave/stand/on"]
    check("C1 MAE-only worsening", (r1["pass_status"], r1["mae"]["over"], r1["overall"]), ("비퇴행", ["vx"], BAD_LABEL))
    check("C2 all-NaN MAE: 결측, 미확인", (R["slope_up/stand/on"]["mae"]["missing"], R["slope_up/stand/on"]["overall"]), (["vx"], "미확인"))
    r3 = R["obstacles/fwd03/on"]
    check("C3 -4 pp not flagged: 비퇴행 미확인", (r3["stage"], r3["pass_status"]), ("선별 비해당 · 추가 측정 없음", "비퇴행 미확인"))
    r4 = R["rough_slope/fwd03/on"]
    check("C4 flagged -> 500: -2 pp 비퇴행, new 400 alone 0", (r4["stage"], round(r4["diff"], 9), r4["pass_status"], round(r4["new400"]["diff"], 9)),
          ("선별 → 500 판", -0.02, "비퇴행", 0.0))
    check("C5 2 of 4 new seeds: 다시 재는 중", (R["stairs_up/fwd03/on"]["pass_status"], R["stairs_up/fwd03/on"]["seeds_have"]), ("다시 재는 중", [1000, 1001, 1002]))
    check("C6 identical arrays: Tango width, 충족 label", (R["wave/fwd03/on"]["screen_lo"] < 0 < R["wave/fwd03/on"]["screen_hi"], R["wave/fwd03/on"]["overall"]), (True, OK_LABEL))
    r9, r10 = R["slope_down/stand/on"], R["stairs_down/stand/on"]
    check("C9 1 of 100 finite: 결측 + short list, 미확인", (r9["mae"]["missing"], r9["overall"]), (["vx"], "미확인"))
    check("C10 99 of 100 finite: still 결측", (r10["mae"]["missing"], r10["overall"]), (["vx"], "미확인"))
    check("C11 exactly +10 %: allowed", (R["wave/back03/on"]["mae"]["over"], R["wave/back03/on"]["overall"]), ([], OK_LABEL))
    check("C12 +10.03 %: over", R["wave/left03/on"]["mae"]["over"], ["vx"])
    r14 = R["slope_down/fwd03/on"]
    check("C14 500-row shortfall kept: arm, seed, finite n", (r14["stage"], r14["mae"]["short"].get("vx"), r14["overall"]),
          ("선별 → 500 판", [{"arm": "on24000", "seed": 1003, "finite": 1}], "미확인"))
    r15 = R["wave/right03/on"]
    check("C15 absolute MAE line (control 0)", (r15["mae"]["over"], r15["mae"]["lines"]["vx"]["line"], round(r15["mae"]["lines"]["vx"]["limit"], 6)), (["vx"], "abs", 0.015))
    check("C16 coverage: done counts rows needing no more samples", (C.res["regression_coverage"]["measured"], C.res["regression_coverage"]["done"]), (12, 11))
    tv = C.res["target_verdict"]["24000"]
    check("C13 no target measured: three targets listed with 0 pairs, 보류", (tv["n_pairs"], tv["verdict"]), ({"stop03": 0, "fwd01": 0, "fwd02": 0}, "수집 중 · 결합 판정 보류"))
    cov = C.res["regression_coverage"]
    check("C7 coverage: planned 99, measured 12", (cov["planned"], cov["measured"]), (99, 12))
    k = C.res["contract_24000"]["on24000"]["cells"]["wave/stand/on"]
    check("C8 contract k/n and Wilson (independent calc 0.915481)", (k["pass_k"], k["n"], k["pass_ok"], round(k["pass_ci"][0], 4)), (97, 100, True, 0.9155))

    # D: authentication of every run (16c 2.2)
    def auth_case(name, setup, want):
        X = Fake("D_" + name.replace(" ", "_"))
        X.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
        X.run(T("on24000", "wave", "fwd03", "on", 1000), 50)
        t = T("on24000", "wave", "fwd03", "on", 1000)
        setup(os.path.join(X.out, t))
        X.go()
        got = [a["why"] for a in X.res["auth_fail"] if a["tag"] == t]
        check(f"D {name}", (got, "wave/fwd03/on" in X.res["regression_24000"]), ([want], False))

    def sp(d):
        return os.path.join(d, "driver_stamp.json")

    def edit(d, **kw):
        st = json.load(open(sp(d)))
        st.update(kw)
        json.dump(st, open(sp(d), "w"))
    auth_case("changed cells.json", lambda d: open(os.path.join(d, "cells.json"), "a").write(" "), "outputs changed after validation")
    auth_case("no stamp", lambda d: os.remove(sp(d)), "no stamp")
    auth_case("cut stamp", lambda d: open(sp(d), "w").write("{"), "stamp unreadable")
    auth_case("empty hashes", lambda d: edit(d, out_sha256={}), "new stamp without the four output hashes")
    auth_case("checkpoint differs", lambda d: edit(d, ckpt_sha256="other"), "stamp checkpoint differs from its log")
    auth_case("pins differ", lambda d: edit(d, pins={"x": 1}), "stamp pins differ from its log")
    L = Fake("D_legacy")
    L.run(T("off24000", "wave", "fwd03", "on", 1000), 60, stamp="legacy")
    L.run(T("on24000", "wave", "fwd03", "on", 1000), 50, stamp="legacy")
    L.go({"cmdr_eval_driver": {"version": "3.2"}})
    check("D legacy stamps in a v3.2 log: accepted and listed", (L.res["auth_fail"], L.res["legacy_stamps"], len(L.res["legacy_tags"])), ([], 2, 2))
    L2 = Fake("D_legacy_in_new_log")
    L2.run(T("off24000", "wave", "fwd03", "on", 1000), 60, stamp="legacy")
    L2.run(T("on24000", "wave", "fwd03", "on", 1000), 50, stamp="legacy")
    L2.go()
    check("D legacy stamp in a v3.5 log: rejected", sorted(a["why"] for a in L2.res["auth_fail"]), ["legacy stamp in a v3.3+ log"] * 2)
    auth_case("version key removed, old hashes kept", lambda d: (lambda st: (st.pop("stamp_version"), json.dump(st, open(sp(d), "w"))))(json.load(open(sp(d)))),
              "ambiguous stamp (new-format fields without stamp_version)")

    # E: log-level identity
    E = Fake("E")
    E.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
    E.run(T("on24000", "wave", "fwd03", "on", 1000), 50, log="cmdr_eval_driver_g0")
    E.go({"cmdr_eval_driver_g0": {"pins": dict(PINS, **{"q_post.py": "other"})}})
    check("E1 pins differ between logs -> stop", (E.rc != 0, "differs between the two logs" in E.err), (True, True))
    E2 = Fake("E2")
    E2.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
    E2.go({"cmdr_eval_driver": {"pins": {k: v for k, v in PINS.items() if k != "gpu_guard.py"}}})
    check("E2 a pinned file missing -> stop", (E2.rc != 0, "pins missing" in E2.err), (True, True))
    E3 = Fake("E3")
    E3.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
    E3.go({"cmdr_eval_driver": {"experiment": "something_else"}})
    check("E3 other experiment -> stop", (E3.rc != 0, "experiment" in E3.err), (True, True))

    # R: the bytes hashed are the bytes parsed; a log that changes during the aggregate stops it (16e 3.2)
    def run_hooked(out, target, mutate, post=POST):
        real_open = builtins.open
        state = {"done": False}

        def hooked(file, mode="r", *a, **k):
            f = real_open(file, mode, *a, **k)
            if not state["done"] and "b" in mode and "r" in mode and os.path.normcase(os.path.abspath(str(file))) == os.path.normcase(os.path.abspath(target)):
                data = f.read()
                f.close()
                state["done"] = True
                mutate()  # the file on disk changes right after the first binary read
                return io.BytesIO(data)
            return f
        old_env = {k: os.environ.get(k) for k in ("CMDR_POST_OUT", "CMDR_POST_DEST")}
        os.environ["CMDR_POST_OUT"], os.environ["CMDR_POST_DEST"] = out, out
        sys.path.insert(0, EV)
        builtins.open = hooked
        code = 0
        try:
            runpy.run_path(os.path.join(EV, post), run_name="__main__")
        except SystemExit as e:
            code = e.code
        finally:
            builtins.open = real_open
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return code
    RR = Fake("R")
    RR.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
    RR.run(T("on24000", "wave", "fwd03", "on", 1000), 50)
    RR.go()
    t_on = T("on24000", "wave", "fwd03", "on", 1000)
    csvp = os.path.join(RR.out, t_on, "episodes.csv")

    def flip():
        rows = list(csv.DictReader(open(csvp, encoding="utf-8")))
        for r in rows:
            r["span_q1_pass"] = "True"
        with open(csvp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    os.remove(os.path.join(RR.out, "cmdr_post.json"))
    code = run_hooked(RR.out, csvp, flip)
    check("R1 CSV changed while it was read: exit 3, nothing written (v7 used the bytes it hashed; v8 stops)",
          (code, os.path.exists(os.path.join(RR.out, "cmdr_post.json"))), (3, False))
    RL = Fake("RL")
    RL.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
    RL.run(T("on24000", "wave", "fwd03", "on", 1000), 50)
    RL.go()
    os.remove(os.path.join(RL.out, "cmdr_post.json"))
    logp = os.path.join(RL.out, "cmdr_eval_driver.json")
    code = run_hooked(RL.out, logp, lambda: open(logp, "a").write(" "))
    check("R2 a log changed during the aggregate: exit 3, nothing written", (code, os.path.exists(os.path.join(RL.out, "cmdr_post.json"))), (3, False))

    # L1 (16g 3.1) the log still publishes the older run; a newer, normal stamp over new bytes must not be used
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

    # L5 (16h 4.3) a held run stays out of every table with its reason; measured again (new stamp) it is used again
    LD = Fake("L5")
    LD.run(t_off, 60)
    LD.run(t_on, 50)
    hs = hashlib.sha256(open(os.path.join(LD.out, t_on, "driver_stamp.json"), "rb").read()).hexdigest()
    json.dump({t_on: {"stamp_sha256": hs, "why": "USD 임시 폴더 공유 의심 (11:38) · 다시 재는 중"}}, open(os.path.join(LD.out, "cmdr_post_hold.json"), "w"))
    LD.go()
    check("L5 held run: out of the tables, listed with its reason, not an auth failure",
          (LD.rc, [h["tag"] for h in LD.res["held"]], "wave/fwd03/on" in LD.res["regression_24000"], LD.res["auth_fail"]), (0, [t_on], False, []))
    held_post = os.path.join(LD.out, "cmdr_post.json")
    import shutil as _sh
    _sh.copy(held_post, os.path.join(LD.out, "cmdr_post_held.json"))
    sp_ = os.path.join(LD.out, t_on, "driver_stamp.json")
    st_ = json.load(open(sp_))
    st_["revalidated_at"] = "later"
    json.dump(st_, open(sp_, "w"))
    LD.go()
    check("L5b the stamp is no longer the held one: used again, release recorded",
          (LD.rc, LD.res["held"], [r["tag"] for r in LD.res["hold_released"]], "wave/fwd03/on" in LD.res["regression_24000"]), (0, [], [t_on], True))

    # F: real out/, read only, one snapshot of both logs: v6 equals v5 on the 22,000 targets
    r5, r6 = (tempfile.mkdtemp(prefix=f"real{v}_", dir=ROOT) for v in (7, 8))

    def snap():
        return tuple(hashlib.sha256(open(os.path.join(SRC, f), "rb").read()).hexdigest() if os.path.exists(os.path.join(SRC, f)) else ""
                     for f in ("cmdr_eval_driver.json", "cmdr_eval_driver_g0.json"))
    same_snapshot = False
    for _ in range(4):
        before = snap()
        rcs = []
        for dest, script in ((r5, "cmdr_post_v7.py"), (r6, POST)):  # v7 exits 3 when a live log changes mid-aggregate: try again
            rcs.append(subprocess.run([PY, script], cwd=EV, env=dict(os.environ, CMDR_POST_DEST=dest, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES=""),
                                      capture_output=True, text=True).returncode)
        assert all(rc in (0, 3) for rc in rcs), rcs
        if 3 in rcs:
            continue
        if before == snap():
            same_snapshot = True
            break
    v5 = json.load(open(os.path.join(r5, "cmdr_post.json"), encoding="utf-8"))
    v6 = json.load(open(os.path.join(r6, "cmdr_post.json"), encoding="utf-8"))
    same = all(v6["targets"][c]["on_minus_off_22000"][k] == v5["targets"][c]["on_minus_off_22000"][k] for c in ("stop03", "fwd01", "fwd02")
               for k in ("diff", "lo", "hi", "n", "newcombe"))
    check("F1 real data, one snapshot: v8 = v7 on 22,000 targets, same runs, no auth failures",
          (same_snapshot, same, v5["n_valid_runs"] == v6["n_valid_runs"], v6["auth_fail"]), (True, True, True, []))

    # G: the page layer
    sys.path.insert(0, "C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/e12page")
    import facts5_cmdr as FC
    summ = os.path.join(SRC, "branch", "cmdr_summary.json")
    g = FC.build(post_path=os.path.join(B.out, "cmdr_post.json"), summary_path=summ)
    check("G1 100-pair targets: 보류, values labelled (100 쌍, none labelled (500 쌍", ("결합 판정 보류" in g["cmdr_status"], "(100 쌍" in g["cmdr_status"], "(500 쌍" in g["cmdr_status"]), (True, True, False))
    check("G2 their regression rows carry n and 수집 중", ("100 판" in g["cmdr_reg_rows"], "수집 중" in g["cmdr_reg_rows"]), (True, True))
    g2 = FC.build(post_path=os.path.join(r5, "cmdr_post.json"), summary_path=summ)
    check("G3 an older aggregate is refused, not read as 'no comparison'", ("집계 판 불일치" in g2["cmdr_status"], "아직 비교 없음" in g2["cmdr_status"]), (True, False))
    g3 = FC.build(post_path=os.path.join(r6, "cmdr_post.json"), summary_path=summ)
    check("G4 off-arm sentence reads n from the aggregate", ("판)" in g3["cmdr_offarm"], "체크포인트마다 500 판" in g3["cmdr_offarm"]), (True, False))
    det = g3["cmdr_contract_detail"].split("<details>")[1:]
    want_n = [v6["contract_24000"][m]["n_cells"] for m in ("off24000", "on24000") if v6["contract_24000"].get(m, {}).get("n_cells")]
    check("G5 contract detail: one table per arm, one row per measured cell", [d.count("<tr><td>") for d in det], want_n)
    check("G7 summary separates 'has a comparison' from 'samples complete'", ("다 재진" in g["cmdr_reg_summary"], "필요한 판 수를 다 채운 칸" in g["cmdr_reg_summary"]), (False, True))
    Dn = Fake("Dn")
    Dn.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
    Dn.run(T("on24000", "wave", "fwd03", "on", 1000), 50)
    open(os.path.join(Dn.out, T("on24000", "wave", "fwd03", "on", 1000), "driver_stamp.json"), "w").write("{")
    Dn.go()
    gd = FC.build(post_path=os.path.join(Dn.out, "cmdr_post.json"), summary_path=summ)
    check("G8 no valid comparison: says so without guessing why", ("평가 전" in gd["cmdr_reg_summary"], "현재 유효한 on · off 24,000 비교 없음" in gd["cmdr_reg_summary"]), (False, True))
    g4 = FC.build(post_path=os.path.join(C.out, "cmdr_post.json"), summary_path=summ)
    check("G9 absolute MAE line in words on the regression row", "절대 한도 0.015" in g4["cmdr_reg_rows"], True)
    H = open("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/e12page/v5_cmdr.html", encoding="utf-8").read()
    check("G10 fragment: no old label, training status from a token", ("전체 조건" in H, "%%cmdr_train_status%%" in H, "진행 중 · 끝 ≈" in H), (False, True, False))
    check("G11 seed ids in the per-seed list", "1000 +" in g3["cmdr_status"] or "1000 -" in g3["cmdr_status"], True)
    ev_real = FC.EV
    FC.EV = os.path.join(ROOT, "no_branch_here")
    g12 = FC.build(post_path=os.path.join(C.out, "cmdr_post.json"), summary_path=summ)
    FC.EV = ev_real
    check("G12 (16g 5.1) no result file: says only what is seen", ("현재 상태 미확인" in g12["cmdr_train_status"], "학습 중" in g12["cmdr_train_status"]), (True, False))
    g13 = FC.build(post_path=os.path.join(LO.out, "cmdr_post.json"), summary_path=summ)
    g14 = FC.build(post_path=os.path.join(LD.out, "cmdr_post_held.json"), summary_path=summ)
    check("G14 (16h 4.3) the status line names the held run and its reason", ("공개 보류 1 개" in g14["cmdr_status"] or "공개 보류 1 개" in " ".join(str(v) for v in g14.values()),
          "USD 임시 폴더 공유 의심" in " ".join(str(v) for v in g14.values())), (True, True))
    check("G13 (16g 4) the status line shows the origins", ("구형 출처 · 재검사 때 해시 1" in g13["cmdr_status"] or "구형 출처 · 재검사 때 해시 1" in " ".join(str(v) for v in g13.values())), True)
    check("G6 rows with partial MAE are shown, not hidden", ("물결 · 서 있기" in g4["cmdr_reg_rows"] and "내리막 · 서 있기" in g4["cmdr_reg_rows"]), True)
finally:
    shutil.rmtree(ROOT, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
