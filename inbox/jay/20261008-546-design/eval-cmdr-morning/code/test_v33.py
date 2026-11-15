"""Known-answer tests for cmdr_eval_driver_v33.py without Isaac / GPU (lead 10/13).
Loads the definitions only (source cut before the main section) into a namespace, points OUT at a temp folder."""
import csv
import json
import os
import shutil
import sys
import tempfile

EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
SRC = open(os.path.join(EV, "cmdr_eval_driver_v33.py"), encoding="utf-8").read()
for pair in json.loads(os.environ.get("V33_MUTATE", "[]")):  # break-the-guard: apply a mutation to the source copy in memory
    assert SRC.count(pair[0]) == 1, pair[0]
    SRC = SRC.replace(pair[0], pair[1])
CUT = SRC.index("deadline = DEADLINE = ")
REAL = "cq_on22000_flat_stop03_on_s1000"  # a valid v3.2 run (on22000 = branch checkpoint)
fails = []


def ns_for(gpu, extra=()):
    sys.argv = ["x", "--gpu", str(gpu)] + list(extra)
    ns = {"__file__": os.path.join(EV, "cmdr_eval_driver_v33.py"), "__name__": "v33test"}
    sys.path.insert(0, EV)
    exec(compile(SRC[:CUT], "v33", "exec"), ns)
    return ns


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:120], "want", repr(want)[:80])
    if not ok:
        fails.append(name)


tmp = tempfile.mkdtemp(prefix="v33t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")
try:
    src_out = os.path.join(EV, "out")
    shutil.copytree(os.path.join(src_out, REAL), os.path.join(tmp, REAL))
    for ext in (".log", ".guard.json"):
        shutil.copy(os.path.join(src_out, REAL + ext), os.path.join(tmp, REAL + ext))
    drv = json.load(open(os.path.join(src_out, "cmdr_eval_driver.json"), encoding="utf-8"))
    sha_on22 = drv["ckpt"]["on22000"]["sha256"]

    n1 = ns_for(1)
    n1["OUT"] = tmp
    args = (REAL, sha_on22, 22000, "flat", ["stop03"], 100, True, 1000, True)
    check("1 validate real run on GPU 1", n1["validate"](*args), "")
    n0 = ns_for(0)
    n0["OUT"] = tmp
    check("2 same run under --gpu 0 -> gpu uuid", n0["validate"](*args), "gpu uuid")

    # 3 negative max_abs must fail (v3.2 passed it)
    mp = os.path.join(tmp, REAL, "meta.json")
    meta = json.load(open(mp, encoding="utf-8"))
    keep = meta["checks_run"]["obs_single_cmd_vs_target_max_abs"]
    meta["checks_run"]["obs_single_cmd_vs_target_max_abs"] = -1.0
    json.dump(meta, open(mp, "w", encoding="utf-8"))
    check("3 negative max_abs rejected", n1["validate"](*args).startswith("checks_run"), True)
    meta["checks_run"]["obs_single_cmd_vs_target_max_abs"] = float("nan")
    json.dump(meta, open(mp, "w", encoding="utf-8"))
    check("3b NaN max_abs rejected", n1["validate"](*args).startswith("checks_run"), True)
    shutil.copy(os.path.join(src_out, REAL, "meta.json"), mp)  # back to the real file
    check("3c restored meta passes", n1["validate"](*args), "")
    check("3d restored value is the real one", json.load(open(mp, encoding="utf-8"))["checks_run"]["obs_single_cmd_vs_target_max_abs"], keep)

    # 4 stamps: v3.2 stamp (no hashes) with the right pins -> ok; v3.3 stamp with hashes -> ok; changed output -> not ok
    P = json.load(open(os.path.join(tmp, REAL, "driver_stamp.json"), encoding="utf-8"))["pins"]
    check("4a v3.2 stamp accepted", n1["stamp_ok"](REAL, P), True)
    check("4b wrong pins refused", n1["stamp_ok"](REAL, {**P, "q_eval_cmdr.py": "0"}), False)
    n1["write_stamp"](REAL, P, {"out_sha256": n1["outhash"](REAL), "attempt": "t"})
    check("4c v3.3 stamp accepted", n1["stamp_ok"](REAL, P), True)
    with open(os.path.join(tmp, REAL, "cells.json"), "a", encoding="utf-8") as f:
        f.write(" ")
    check("4d changed cells.json refused", n1["stamp_ok"](REAL, P), False)
    os.remove(os.path.join(tmp, REAL, "traj.npz"))
    check("4e missing traj refused", n1["stamp_ok"](REAL, P), False)

    # 5 order24: same multiset, 24000 jobs first, relative order kept inside both blocks
    J = n1["jobs"]()
    O = n1["order24"](J)
    check("5a same jobs", sorted(O) == sorted(J) and len(O) == len(J) == 555, True)
    k = sum(j[0] in ("off24000", "on24000") for j in J)
    check("5b 24000 block first", all(j[0] in ("off24000", "on24000") for j in O[:k]) and not any(j[0] in ("off24000", "on24000") for j in O[k:]), True)
    check("5c order kept", [j for j in J if j[0] in ("off24000", "on24000")] == O[:k] and [j for j in J if j[0] not in ("off24000", "on24000")] == O[k:], True)
    check("5d first job", O[0], ("off24000", "flat", "stop03", True, 1000))

    # 6 screen: synthetic episodes.csv; boundary -5 pp flags, -4 pp does not; flat noise-on targets skipped
    scr = tempfile.mkdtemp(prefix="scr_", dir=tmp)
    n2 = ns_for(0, ["--plan", "remeasure", "--log", "g0test", "--base_log", "basetest"])
    n2["OUT"] = scr

    def fake(tag, cell, passes):
        os.makedirs(os.path.join(scr, tag))
        col = "span_q2_pass" if cell == "stop03" else ("span_q1a_pass" if cell in ("fwd01", "fwd02") else "span_q1_pass")
        with open(os.path.join(scr, tag, "episodes.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["episode", "span_q2_pass", "span_q1a_pass", "span_q1_pass"])
            w.writeheader()
            for e in reversed(range(100)):  # written out of order on purpose: main_pass must sort by episode
                r = {"episode": e, "span_q2_pass": "False", "span_q1a_pass": "False", "span_q1_pass": "False"}
                r[col] = "True" if e < passes else "False"
                w.writerow(r)

    T = n2["tagof"]
    cases = [("wave", "fwd03", True, 50, 45), ("wave", "back03", True, 50, 46), ("flat", "fwd01", True, 50, 10),
             ("flat", "fwd01", False, 60, 55), ("stairs_up", "stand", True, 100, 94)]
    valid = {}
    for fam, cell, noise, off, on in cases:
        a, b = T("off24000", fam, cell, noise, 1000), T("on24000", fam, cell, noise, 1000)
        fake(a, cell, off)
        fake(b, cell, on)
        valid[a] = valid[b] = "valid"
    valid[T("on24000", "stairs_up", "stand", True, 1000)] = "pair_fail"  # a pair_fail run must not enter the screen
    json.dump({"matrix": {k: v for k, v in valid.items() if "wave" in k}}, open(os.path.join(scr, "basetest.json"), "w"))
    json.dump({"matrix": {k: v for k, v in valid.items() if "wave" not in k}}, open(os.path.join(scr, "g0test.json"), "w"))
    sc = n2["screen"]()
    check("6a keys", sorted(sc), sorted([("wave", "fwd03", True), ("wave", "back03", True), ("flat", "fwd01", False)]))
    check("6b -5 pp exact", sc[("wave", "fwd03", True)], (-5, 100))
    check("6c -4 pp", sc[("wave", "back03", True)], (-4, 100))
    check("6d flag rule (driver's flagged())", [n2["flagged"](*sc[k]) for k in (("wave", "fwd03", True), ("wave", "back03", True), ("flat", "fwd01", False))], [True, False, True])
    check("6e flagged(-6, 100) / (0, 100) / (-25, 500) / (-24, 500)", [n2["flagged"](-6, 100), n2["flagged"](0, 100), n2["flagged"](-25, 500), n2["flagged"](-24, 500)], [True, False, True, False])

    # 7 base_finished needs a v3.3 log that ended or stopped
    json.dump({"matrix": {}, "ended": "x"}, open(os.path.join(scr, "basetest.json"), "w"))
    check("7a v3.2-style log never counts as finished", n2["base_finished"](), False)
    json.dump({"matrix": {}, "version": "3.3"}, open(os.path.join(scr, "basetest.json"), "w"))
    check("7b running v3.3", n2["base_finished"](), False)
    json.dump({"matrix": {}, "version": "3.3", "stopped": "deadline"}, open(os.path.join(scr, "basetest.json"), "w"))
    check("7c stopped v3.3", n2["base_finished"](), True)

    # 8 atomic save writes valid JSON at LOGF, no tmp left
    n2["LOGF"] = os.path.join(scr, "savetest.json")
    n2["LOG"]["x"] = 1
    n2["save"]()
    check("8 save", json.load(open(n2["LOGF"], encoding="utf-8"))["x"] == 1 and not os.path.exists(n2["LOGF"] + ".tmp"), True)
    check("9 attempt id form", n2["ATTEMPT"].startswith("g0-"), True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("FAILS", fails)
