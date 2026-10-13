"""Known-answer tests for cmdr_post_v5.py (lead 10/13, VERIFY-astra-16 6.3 / 9.2). Builds fake out/ folders from copies of
real run folders OF THE SAME CELL, rewrites the pass / survival / MAE columns to known patterns (the other pass columns get
the opposite pattern, so reading the wrong column fails a check), runs v5 there. Never writes to the real out/.
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
POST = os.environ.get("POST_V5", "cmdr_post_v5.py")
COLS = ("span_q2_pass", "span_q1a_pass", "span_q1_pass")
MAIN = {"stop03": "span_q2_pass", "fwd01": "span_q1a_pass", "fwd02": "span_q1a_pass", "fwd03": "span_q1_pass", "stand": "span_q1_pass"}
fails = []
ROOT = tempfile.mkdtemp(prefix="p5t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")


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

    def run(self, tag, passes, surv_false=0, mae=None, log="cmdr_eval_driver"):
        cell = tag.split("_")[-3]
        src = f"cq_off22000_flat_{cell}_on_s{tag.rsplit('_s', 1)[1]}"  # a real folder of the same cell (and seed when there is one)
        if not os.path.exists(os.path.join(SRC, src)):
            src = f"cq_off22000_flat_{cell}_on_s1000"
        d = os.path.join(self.out, tag)
        shutil.copytree(os.path.join(SRC, src), d)
        p = os.path.join(d, "episodes.csv")
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        assert all(r["cell"] == cell for r in rows), "fixture cell"
        for r in rows:
            e = int(r["episode"])
            for col in COLS:  # main column gets the pattern, the others the opposite (a wrong column fails the checks)
                hit = e < passes
                r[col] = str(hit if col == MAIN[cell] else not hit)
            r["span_survived"] = "False" if e < surv_false else "True"
            if mae is not None:
                r["mae_vx"] = str(mae)
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        os.remove(os.path.join(d, "driver_stamp.json"))
        self.logs[log][tag] = "valid"

    def go(self, extra_logs=None):
        for name, m in self.logs.items():
            body = {"version": "3.4", "matrix": m, "pair_fail": [], "skipped": [], "runs": [1] * len(m), "pins": {"x": "1"}}
            body.update((extra_logs or {}).get(name, {}))
            json.dump(body, open(os.path.join(self.out, f"{name}.json"), "w"))
        env = dict(os.environ, CMDR_POST_OUT=self.out, CMDR_POST_DEST=self.out, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES="")
        r = subprocess.run([PY, POST], cwd=EV, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.rc, self.err = r.returncode, r.stderr
        if r.returncode == 0:
            self.res = json.load(open(os.path.join(self.out, "cmdr_post.json"), encoding="utf-8"))
        return self


try:
    # A: targets complete (5 seeds), +5 / +10 / +15 -> mean exactly +10, all low ends > 0 -> 개선; per-cell columns differ by cell
    A = Fake("A")
    for s in range(1000, 1005):
        for cell, on in (("stop03", 55), ("fwd01", 60), ("fwd02", 65)):
            A.run(T("off24000", "flat", cell, "on", s), 50)
            A.run(T("on24000", "flat", cell, "on", s), on)
    A.go()
    check("A0 runs", A.rc, 0)
    tv = A.res["target_verdict"]["24000"]
    check("A1 complete, 500 pairs each", (tv["complete"], tv["n_pairs"]), (True, {"stop03": 500, "fwd01": 500, "fwd02": 500}))
    check("A2 +5 +10 +15: mean exactly +10 and all low ends > 0 -> 개선", (tv["all_low_above_0"], round(tv["mean_pp"], 9), tv["verdict"]), (True, 10.0, "개선"))
    check("A3 stop03 read from span_q2 (+5 pp; the q1a column says -5)", round(A.res["targets"]["stop03"]["on_minus_off_24000"]["diff"], 9), 0.05)
    check("A4 interval method is Tango, Newcombe kept", (A.res["targets"]["fwd01"]["on_minus_off_24000"]["method"],
                                                         len(A.res["targets"]["fwd01"]["on_minus_off_24000"]["newcombe"])), ("tango", 2))

    # B: targets with seed 1000 only (100 pairs) -> no joint verdict even with huge differences (ASTRA 16 1)
    B = Fake("B")
    for cell in ("stop03", "fwd01", "fwd02"):
        B.run(T("off24000", "flat", cell, "on", 1000), 40)
        B.run(T("on24000", "flat", cell, "on", 1000), 80)
    B.go()
    tv = B.res["target_verdict"]["24000"]
    check("B1 100 pairs: 수집 중 · 결합 판정 보류", (tv["complete"], tv["verdict"], tv["seeds_missing"]["stop03"]), (False, "수집 중 · 결합 판정 보류", [1001, 1002, 1003, 1004]))
    check("B2 no joint fields before completion", "mean_pp" in tv, False)
    # B': 4 seeds (400 pairs) -> still 보류
    B2 = Fake("B2")
    for s in range(1000, 1004):
        for cell in ("stop03", "fwd01", "fwd02"):
            B2.run(T("off24000", "flat", cell, "on", s), 40)
            B2.run(T("on24000", "flat", cell, "on", s), 80)
    B2.go()
    check("B3 400 pairs: 보류", B2.res["target_verdict"]["24000"]["verdict"], "수집 중 · 결합 판정 보류")

    # C: regression rows
    C = Fake("C")
    # C1 MAE-only worsening: identical passes, vx MAE 0.1 -> 0.5
    C.run(T("off24000", "wave", "stand", "on", 1000), 97, mae=0.1)
    C.run(T("on24000", "wave", "stand", "on", 1000), 97, mae=0.5)
    # C2 NaN MAE in one arm
    C.run(T("off24000", "slope_up", "stand", "on", 1000), 97, mae=0.1)
    C.run(T("on24000", "slope_up", "stand", "on", 1000), 97, mae="nan")
    # C3 -4 pp, not flagged, wide interval (off 0..59 pass, on 0..55)
    C.run(T("off24000", "obstacles", "fwd03", "on", 1000), 60)
    C.run(T("on24000", "obstacles", "fwd03", "on", 1000), 56)
    # C4 flagged -10 then four new seeds identical -> 500: -2 pp; new 400 alone: 0
    C.run(T("off24000", "rough_slope", "fwd03", "on", 1000), 60)
    C.run(T("on24000", "rough_slope", "fwd03", "on", 1000), 50)
    for s in range(1001, 1005):
        C.run(T("off24000", "rough_slope", "fwd03", "on", s), 60, log="cmdr_eval_driver_g0")
        C.run(T("on24000", "rough_slope", "fwd03", "on", s), 60, log="cmdr_eval_driver_g0")
    # C5 flagged, only 2 new seeds -> 다시 재는 중
    C.run(T("off24000", "stairs_up", "fwd03", "on", 1000), 60)
    C.run(T("on24000", "stairs_up", "fwd03", "on", 1000), 40)
    for s in (1001, 1002):
        C.run(T("off24000", "stairs_up", "fwd03", "on", s), 60, log="cmdr_eval_driver_g0")
        C.run(T("on24000", "stairs_up", "fwd03", "on", s), 40, log="cmdr_eval_driver_g0")
    # C6 identical arrays: Tango interval is not zero-width
    C.run(T("off24000", "wave", "fwd03", "on", 1000), 50)
    C.run(T("on24000", "wave", "fwd03", "on", 1000), 50)
    C.go()
    check("C0 runs", C.rc, 0)
    R = C.res["regression_24000"]
    r1 = R["wave/stand/on"]
    check("C1 MAE-only: pass 비퇴행, vx over, overall 미충족", (r1["pass_status"], r1["mae"]["over"], r1["overall"]), ("비퇴행", ["vx"], "전체 조건 미충족"))
    r2 = R["slope_up/stand/on"]
    check("C2 NaN MAE: 결측, overall 미확인", (r2["mae"]["missing"], r2["overall"]), (["vx"], "미확인"))
    r3 = R["obstacles/fwd03/on"]
    check("C3 -4 pp not flagged: 비퇴행 미확인 (interval crosses -5)", (r3["stage"], r3["pass_status"], r3["screen_lo"] < -0.05), ("선별 비해당 · 추가 측정 없음", "비퇴행 미확인", True))
    r4 = R["rough_slope/fwd03/on"]
    check("C4 flagged -> 500: -2 pp, 비퇴행; new 400 alone 0 with interval", (r4["stage"], round(r4["diff"], 9), r4["pass_status"], round(r4["new400"]["diff"], 9), r4["new400"]["lo"] < 0 < r4["new400"]["hi"]),
          ("선별 → 500 판", -0.02, "비퇴행", 0.0, True))
    check("C4b per-seed differences", sorted((k, round(v, 9)) for k, v in r4["per_seed"].items()), [("1000", -0.1), ("1001", 0.0), ("1002", 0.0), ("1003", 0.0), ("1004", 0.0)])
    r5 = R["stairs_up/fwd03/on"]
    check("C5 flagged, 2 of 4 new seeds: 다시 재는 중", (r5["pass_status"], r5["seeds_have"]), ("다시 재는 중", [1000, 1001, 1002]))
    r6 = R["wave/fwd03/on"]
    check("C6 identical arrays: interval has width (Tango)", (r6["screen_lo"] < 0 < r6["screen_hi"], r6["pass_status"]), (True, "비퇴행"))
    cov = C.res["regression_coverage"]
    check("C7 coverage: planned 99, measured 6", (cov["planned"], cov["measured"], len(cov["unmeasured"])), (99, 6, 93))
    k = C.res["contract_24000"]["on24000"]["cells"]["wave/stand/on"]
    check("C8 contract k/n and Wilson", (k["pass_k"], k["n"], k["pass_ok"], round(k["pass_ci"][0], 4)), (97, 100, True, 0.9155))  # independent Wilson calc 0.915481

    # D: a run whose stamp hashes no longer match is not used and is listed
    D = Fake("D")
    D.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
    D.run(T("on24000", "wave", "fwd03", "on", 1000), 50)
    t = T("on24000", "wave", "fwd03", "on", 1000)
    h = {f: hashlib.sha256(open(os.path.join(D.out, t, f), "rb").read()).hexdigest() for f in ("meta.json", "cells.json", "episodes.csv", "traj.npz")}
    json.dump({"out_sha256": h}, open(os.path.join(D.out, t, "driver_stamp.json"), "w"))
    with open(os.path.join(D.out, t, "cells.json"), "a") as f:
        f.write(" ")
    D.go()
    check("D1 changed after validation: excluded and listed", (D.res["changed_after_validation"], "wave/fwd03/on" in D.res["regression_24000"]), ([t], False))

    # E: the two logs disagree on pins -> the script stops
    E = Fake("E")
    E.run(T("off24000", "wave", "fwd03", "on", 1000), 60)
    E.run(T("on24000", "wave", "fwd03", "on", 1000), 50, log="cmdr_eval_driver_g0")
    E.go({"cmdr_eval_driver_g0": {"pins": {"x": "2"}}})
    check("E1 pins differ between logs -> stop", (E.rc != 0, "differs between the two logs" in E.err), (True, True))

    # F: real out/, read only: v5's Newcombe column and differences equal v4's interval and differences (same matrix)
    real4, real5 = (tempfile.mkdtemp(prefix=f"real{v}_", dir=ROOT) for v in (4, 5))
    for _ in range(3):
        before = hashlib.sha256(open(os.path.join(SRC, "cmdr_eval_driver.json"), "rb").read()).hexdigest()
        for dest, script in ((real4, "cmdr_post_v4.py"), (real5, POST)):
            subprocess.run([PY, script], cwd=EV, env=dict(os.environ, CMDR_POST_DEST=dest, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES=""),
                           capture_output=True, text=True, check=True)
        after = hashlib.sha256(open(os.path.join(SRC, "cmdr_eval_driver.json"), "rb").read()).hexdigest()
        if before == after:
            break
    v4 = json.load(open(os.path.join(real4, "cmdr_post.json"), encoding="utf-8"))
    v5 = json.load(open(os.path.join(real5, "cmdr_post.json"), encoding="utf-8"))
    same = all(abs(v5["targets"][c]["on_minus_off_22000"]["newcombe"][i] - v4["targets"][c]["on_minus_off_22000"][k]) < 1e-12
               and abs(v5["targets"][c]["on_minus_off_22000"]["diff"] - v4["targets"][c]["on_minus_off_22000"]["diff"]) < 1e-12
               for c in ("stop03", "fwd01", "fwd02") for i, k in ((0, "lo"), (1, "hi")))
    check("F1 real data: v5 Newcombe column = v4 interval, same differences", (same, v4["n_valid_runs"] == v5["n_valid_runs"]), (True, True))
finally:
    shutil.rmtree(ROOT, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
