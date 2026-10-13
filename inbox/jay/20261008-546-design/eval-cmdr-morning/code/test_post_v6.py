"""Known-answer tests for cmdr_post_v6.py and the page layer facts5_cmdr.py (lead 10/13, VERIFY-astra-16c 2 / 5).
Fake out/ folders are built from copies of real run folders OF THE SAME CELL; the main pass column gets the pattern and the
other pass columns the opposite (reading the wrong column fails a check). Every fixture run carries the real stamp schema
(pins, checkpoint, stamp_version, four output hashes) unless a case breaks it on purpose. Never writes to the real out/.
Exit code 1 when any check fails."""
import csv
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
POST = os.environ.get("POST_V6", "cmdr_post_v6.py")
COLS = ("span_q2_pass", "span_q1a_pass", "span_q1_pass")
MAIN = {"stop03": "span_q2_pass", "fwd01": "span_q1a_pass", "fwd02": "span_q1a_pass", "fwd03": "span_q1_pass", "stand": "span_q1_pass",
        "back03": "span_q1_pass", "left03": "span_q1_pass"}
PINS = {k: "h_" + k for k in ("q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py")}
CKPT = {"off24000": "ck_off", "on24000": "ck_on", "off22000": "ck_off22", "on22000": "ck_on22", "p20000": "ck_p"}
OUT4 = ("meta.json", "cells.json", "episodes.csv", "traj.npz")
OK_LABEL, BAD_LABEL = "퇴행 방지 조건 충족 (통과율 · MAE)", "퇴행 방지 조건 미충족"
fails = []
ROOT = tempfile.mkdtemp(prefix="p6t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")


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
            json.dump({"pins": PINS, "ckpt_sha256": CKPT[m], "stamp_version": "3.5", "out_sha256": h}, open(os.path.join(d, "driver_stamp.json"), "w"))
        elif stamp == "legacy":
            json.dump({"pins": PINS, "ckpt_sha256": CKPT[m], "pair_ref": tag}, open(os.path.join(d, "driver_stamp.json"), "w"))
        self.logs[log][tag] = "valid"

    def go(self, extra_logs=None):
        for name, m in self.logs.items():
            body = {"version": "3.5", "experiment": "cmdr_s1042_pair_eval", "matrix": m, "pair_fail": [], "skipped": [], "runs": [1] * len(m),
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
    check("A4 schema and no auth failures", (A.res["schema"], A.res["auth_fail"]), ("cmdr_post v6", []))

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
    tv = C.res["target_verdict"]["24000"]
    check("C13 no target measured: three targets listed with 0 pairs, 보류", (tv["n_pairs"], tv["verdict"]), ({"stop03": 0, "fwd01": 0, "fwd02": 0}, "수집 중 · 결합 판정 보류"))
    cov = C.res["regression_coverage"]
    check("C7 coverage: planned 99, measured 10", (cov["planned"], cov["measured"]), (99, 10))
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
    L.go()
    check("D legacy v3.2 stamps accepted and counted", (L.res["auth_fail"], L.res["legacy_stamps"], "wave/fwd03/on" in L.res["regression_24000"]), ([], 2, True))

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

    # F: real out/, read only, one snapshot of both logs: v6 equals v5 on the 22,000 targets
    r5, r6 = (tempfile.mkdtemp(prefix=f"real{v}_", dir=ROOT) for v in (5, 6))

    def snap():
        return tuple(hashlib.sha256(open(os.path.join(SRC, f), "rb").read()).hexdigest() if os.path.exists(os.path.join(SRC, f)) else ""
                     for f in ("cmdr_eval_driver.json", "cmdr_eval_driver_g0.json"))
    same_snapshot = False
    for _ in range(4):
        before = snap()
        for dest, script in ((r5, "cmdr_post_v5.py"), (r6, POST)):
            subprocess.run([PY, script], cwd=EV, env=dict(os.environ, CMDR_POST_DEST=dest, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES=""),
                           capture_output=True, text=True, check=True)
        if before == snap():
            same_snapshot = True
            break
    v5 = json.load(open(os.path.join(r5, "cmdr_post.json"), encoding="utf-8"))
    v6 = json.load(open(os.path.join(r6, "cmdr_post.json"), encoding="utf-8"))
    same = all(v6["targets"][c]["on_minus_off_22000"][k] == v5["targets"][c]["on_minus_off_22000"][k] for c in ("stop03", "fwd01", "fwd02")
               for k in ("diff", "lo", "hi", "n", "newcombe"))
    check("F1 real data, one snapshot: v6 = v5 on 22,000 targets, same runs, no auth failures",
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
    check("G5 contract detail lists every measured cell", g3["cmdr_contract_detail"].count("<tr><td>") >= v6["contract_24000"]["off24000"]["n_cells"], True)
    g4 = FC.build(post_path=os.path.join(C.out, "cmdr_post.json"), summary_path=summ)
    check("G6 rows with partial MAE are shown, not hidden", ("물결 · 서 있기" in g4["cmdr_reg_rows"] and "내리막 · 서 있기" in g4["cmdr_reg_rows"]), True)
finally:
    shutil.rmtree(ROOT, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
