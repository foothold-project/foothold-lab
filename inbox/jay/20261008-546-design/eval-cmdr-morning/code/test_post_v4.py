"""Known-answer tests for cmdr_post_v4.py (lead 10/13). Builds a fake out/ from copies of real run folders whose
pass / survival columns are rewritten to known patterns, runs v4 there, checks every verdict. Then runs v4 on the real
out/ (tables written to a temp folder) and checks the 22000 numbers equal v3's cmdr_post.json."""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

EV = "C:/isaac/ext/go2_rl_robotlab/_eval"
SRC = os.path.join(EV, "out")
PY = sys.executable
fails = []


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:140], "want", repr(want)[:100])
    if not ok:
        fails.append(name)


tmp = tempfile.mkdtemp(prefix="p4t_", dir="C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp")
base, g0 = {}, {}


def fake(tag, src, col, passes, surv_false=0, log=base):
    d = os.path.join(tmp, tag)
    shutil.copytree(os.path.join(SRC, src), d)
    p = os.path.join(d, "episodes.csv")
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    for r in rows:
        e = int(r["episode"])
        r[col] = "True" if e < passes else "False"
        r["span_survived"] = "False" if e < surv_false else "True"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log[tag] = "valid"


try:
    F3 = "cq_off24000_flat_fwd03_on_s1000"  # cell fwd03 -> span_q1_pass
    T = lambda m, fam, cell, noise, s: f"cq_{m}_{fam}_{cell}_{noise}_s{s}"  # noqa: E731
    # targets: copies of real fwd01 folders (span_q1a_pass), one per seed
    for s in range(1000, 1005):
        src = f"cq_off22000_flat_fwd01_on_s{s}"
        for cell, on in (("stop03", 70), ("fwd01", 55), ("fwd02", 40)):
            fake(T("off24000", "flat", cell, "on", s), src, "span_q1a_pass", 50)
            fake(T("on24000", "flat", cell, "on", s), src, "span_q1a_pass", on)
    # non-targets on fwd03 copies: (family, noise, seed -> (off passes, on passes)) ; seeds 1001+ go to the g0 log
    plan = {("wave", "on"): {1000: (60, 50), 1001: (60, 60), 1002: (60, 60), 1003: (60, 60), 1004: (60, 60)},
            ("stairs_up", "on"): {s: (60, 40) for s in range(1000, 1005)},
            ("slope_down", "on"): {1000: (60, 50), 1001: (60, 56), 1002: (60, 56), 1003: (60, 56), 1004: (60, 56)},
            ("obstacles", "on"): {1000: (60, 56)},
            ("rough_slope", "on"): {1000: (60, 50), 1001: (60, 60), 1002: (60, 60)},
            ("flat", "off"): {1000: (60, 55)}}
    for (fam, noise), seeds in plan.items():
        for s, (off, on) in seeds.items():
            lg = base if s == 1000 else g0
            fake(T("off24000", fam, "fwd03", noise, s), F3, "span_q1_pass", off, log=lg)
            fake(T("on24000", fam, "fwd03", noise, s), F3, "span_q1_pass", on,
                 surv_false=10 if (fam == "stairs_up" and s == 1000) else 0, log=lg)
    json.dump({"version": "3.3", "matrix": base, "pair_fail": [], "skipped": [], "runs": [1] * len(base)},
              open(os.path.join(tmp, "cmdr_eval_driver.json"), "w"))
    json.dump({"version": "3.3", "matrix": g0, "pair_fail": [], "skipped": [], "runs": [1] * len(g0)},
              open(os.path.join(tmp, "cmdr_eval_driver_g0.json"), "w"))
    env = dict(os.environ, CMDR_POST_OUT=tmp, CMDR_POST_DEST=tmp, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES="")
    r = subprocess.run([PY, os.environ.get("POST_V4", "cmdr_post_v4.py")], cwd=EV, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("0 v4 runs", r.returncode, 0)
    if r.returncode:
        print(r.stderr[-2000:])
    res = json.load(open(os.path.join(tmp, "cmdr_post.json"), encoding="utf-8"))
    tv = res["target_verdict"].get("24000", {})
    check("1 target stop03 +20", tv.get("stop03"), "개선")
    check("2 target fwd01 +5", tv.get("fwd01"), "구간 하한 0 위 · +10 %p 못 미침")
    check("3 target fwd02 -10", tv.get("fwd02"), "구간 전체가 0 아래")
    check("3b fwd02 diff", round(res["targets"]["fwd02"]["on_minus_off_24000"]["diff"], 6), -0.1)
    R = res["regression_24000"]
    check("4 fwd02 regression (n500 target)", (R["flat/fwd02/on"]["stage"], R["flat/fwd02/on"]["verdict"]), ("n500 (target)", "퇴행"))
    check("5 wave -10 then 0,0,0,0", (R["wave/fwd03/on"]["stage"], R["wave/fwd03/on"]["verdict"], round(R["wave/fwd03/on"]["diff"], 6)),
          ("n500", "비퇴행", -0.02))
    check("6 stairs_up -20 x5", (R["stairs_up/fwd03/on"]["verdict"], round(R["stairs_up/fwd03/on"]["diff"], 6)), ("퇴행", -0.2))
    check("7 slope_down -10 then -4 x4", (R["slope_down/fwd03/on"]["verdict"], round(R["slope_down/fwd03/on"]["diff"], 6)),
          ("비퇴행 미확인", -0.052))
    check("8 obstacles -4 screen", (R["obstacles/fwd03/on"]["stage"], R["obstacles/fwd03/on"]["verdict"]), ("screen", "훑기 통과"))
    check("9 rough_slope 3 of 5 seeds", (R["rough_slope/fwd03/on"]["stage"], R["rough_slope/fwd03/on"]["verdict"],
                                         R["rough_slope/fwd03/on"]["seeds_have"]), ("screen flagged", "다시 재는 중", [1000, 1001, 1002]))
    check("10 flat noise-off -5 exactly is flagged", R["flat/fwd03/off"]["verdict"], "다시 재는 중")
    check("11 no regression row for cells never measured", "wave/stand/on" in R, False)
    C = res["contract_24000"]["on24000"]
    check("12 contract surv below", C["surv_below"], ["stairs_up/fwd03/on"])
    check("13 contract pass below covers every on24000 seed-1000 cell", len(C["pass_below"]), C["n_cells"])
    check("14 contract off24000 survival all ok", res["contract_24000"]["off24000"]["surv_below"], [])
    check("15 logs read", sorted(res["driver_logs"]), ["cmdr_eval_driver", "cmdr_eval_driver_g0"])
    md = open(os.path.join(tmp, "CMDR-tables.md"), encoding="utf-8").read()
    check("16 md has the regression table and no proposal wording", ("## 24,000 퇴행" in md, "제안이며" in md), (True, False))
    # 17 the same tag in both logs must stop the script
    g0[next(iter(base))] = "valid"
    json.dump({"version": "3.3", "matrix": g0}, open(os.path.join(tmp, "cmdr_eval_driver_g0.json"), "w"))
    r = subprocess.run([PY, os.environ.get("POST_V4", "cmdr_post_v4.py")], cwd=EV, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("17 duplicate tag refused", (r.returncode != 0, "tags in two logs" in r.stderr), (True, True))

    # 18 real data: v4 22000 numbers equal v3's
    real = tempfile.mkdtemp(prefix="real_", dir=tmp)
    env2 = dict(os.environ, CMDR_POST_DEST=real, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES="")
    env3 = dict(os.environ, KMP_DUPLICATE_LIB_OK="TRUE", CUDA_VISIBLE_DEVICES="")
    for attempt in range(3):  # v3 and v4 back to back on the same matrix (the driver may add a run in between: retry)
        r3 = subprocess.run([PY, "cmdr_post.py"], cwd=EV, env=env3, capture_output=True, text=True, encoding="utf-8", errors="replace")
        r = subprocess.run([PY, os.environ.get("POST_V4", "cmdr_post_v4.py")], cwd=EV, env=env2, capture_output=True, text=True, encoding="utf-8", errors="replace")
        v4 = json.load(open(os.path.join(real, "cmdr_post.json"), encoding="utf-8"))
        v3 = json.load(open(os.path.join(SRC, "cmdr_post.json"), encoding="utf-8"))
        if v4["n_valid_runs"] == v3["n_valid_runs"]:
            break
    check("18a v3 and v4 on real out", (r3.returncode, r.returncode), (0, 0))
    same = all(json.dumps(v4["targets"][c].get("on_minus_off_22000"), sort_keys=True) == json.dumps(v3["targets"][c].get("on_minus_off_22000"), sort_keys=True)
               for c in ("stop03", "fwd01", "fwd02"))
    check("18b targets 22000 identical to v3", same, True)
    check("18c cells identical to v3", json.dumps(v4["cells"], sort_keys=True) == json.dumps(v3["cells"], sort_keys=True), True)
    check("18d n_valid equal", v4["n_valid_runs"], v3["n_valid_runs"])
    check("18e 22000 per-cell verdicts", v4["target_verdict"].get("22000"),
          {"stop03": "구간 하한 0 위 · +10 %p 못 미침", "fwd01": "구간 전체가 0 아래", "fwd02": "구간 전체가 0 아래"})
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("FAILS", fails)
