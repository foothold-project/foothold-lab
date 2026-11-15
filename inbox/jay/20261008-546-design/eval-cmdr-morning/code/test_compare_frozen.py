"""Known-answer tests for compare_frozen.py (exact form, VERIFY-astra-16k 3) on the real frozen 14:05 v8 output, changed
in memory copies. Exit 1 on failure. The real aggregate is used for its size and shape; each case states what it changes."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("CF_SCRIPT", os.path.join(HERE, "compare_frozen.py"))
H = "C:/isaac/ext/go2_rl_robotlab/_eval/out/handover_20261013_140449"
V7 = json.load(open(f"{H}/v7/cmdr_post.json", encoding="utf-8"))
V8 = json.load(open(f"{H}/v8/cmdr_post.json", encoding="utf-8"))
fails = []
T = tempfile.mkdtemp(prefix="cft_", dir=HERE)


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", got, "want", want)
    if not ok:
        fails.append(name)


def rc(a, b, k, ref=None):
    ps = []
    for i, x in enumerate((a, b, ref)):
        if x is None:
            continue
        p = os.path.join(T, f"{k}_{i}.json")
        json.dump(x, open(p, "w", encoding="utf-8"))
        ps.append(p)
    return subprocess.run([sys.executable, SCRIPT] + ps, capture_output=True, text=True, encoding="utf-8", errors="replace").returncode


# a newer output with no held run and its v7 twin: the v8 tables, bookkeeping as v7 would write it
NEW = copy.deepcopy(V8)
NEW["held"] = []
NEW["hold_released"] = []
REF = copy.deepcopy(V8)
for k in ("held", "hold_released", "hold_candidates", "inputs_manifest", "origin_counts"):
    REF.pop(k, None)
REF["schema"] = "cmdr_post v7"
for d in REF.get("driver_logs", {}).values():
    d.pop("attempt", None)
check("C0 same tables, only bookkeeping differs: pass", rc(REF, NEW, 0), 0)


def mutated(fn):
    b = copy.deepcopy(NEW)
    fn(b)
    return b


arm_off = NEW["contract_24000"]["off24000"]
cases = [
    ("C1 (16j) off stand contract cell changed", lambda b: b["contract_24000"]["off24000"]["cells"]["flat/stand/on"].__setitem__("pass_k", 1)),
    ("C2 (16j) an unrelated completion changed", lambda b: b["completion"].__setitem__("off24000/obstacles", 999)),
    ("C3 (16j) a general cells entry changed", lambda b: next(x for x in b["cells"] if x["family"] != "flat" or x["cell"] != "stand")["off24000"].__setitem__("rate", 0.999)),
    ("C4 the target mean changed", lambda b: b["target_verdict"]["24000"].__setitem__("mean_pp", 999)),
    ("C5 coverage changed", lambda b: b["regression_coverage"].__setitem__("done", b["regression_coverage"]["done"] - 1)),
    ("C6 another top-level key differs", lambda b: b.__setitem__("driver_pair_fail", ["x"])),
    ("C7 (16k 3) off contract n_cells changed", lambda b: b["contract_24000"]["off24000"].__setitem__("n_cells", 999)),
    ("C8 (16k 3) off contract pass_below emptied", lambda b: b["contract_24000"]["off24000"].__setitem__("pass_below", [])),
    ("C9 (16k 3) a cell dropped from on unmeasured", lambda b: b["contract_24000"]["on24000"].__setitem__("unmeasured", b["contract_24000"]["on24000"].get("unmeasured", [])[1:] if b["contract_24000"]["on24000"].get("unmeasured") else ["x"])),
    ("C10 (16k 3) a whole cells row deleted", lambda b: b.__setitem__("cells", [x for x in b["cells"] if not (x["family"] == "flat" and x["cell"] == "fwd03")])),
    ("C11 (16k 3) a completion count changed by one", lambda b: b["completion"].__setitem__("on24000/flat", b["completion"]["on24000/flat"] + 1)),
    ("C12 (16k 3) a regression row added", lambda b: b["regression_24000"].__setitem__("flat/stand/on", {"x": 1})),
    ("C13 a top-level key with a slash in its name", lambda b: b.__setitem__("a/b", 1)),
]
for i, (name, fn) in enumerate(cases, 1):
    check(name + ": fails", rc(REF, mutated(fn), 100 + i), 1)

# held runs: without a filtered reference nothing passes; with one, exact equality is required
check("C20 the real 14:05 pair (one held run) without a filtered v7: not comparable (exit 2)", rc(V7, V8, 20), 2)
HB = copy.deepcopy(NEW)
HB["held"] = [{"tag": "cq_on24000_flat_stand_on_s1000"}]
HB["inputs_manifest"] = {k: v for k, v in HB.get("inputs_manifest", {}).items() if k != "cq_on24000_flat_stand_on_s1000"}
A7 = dict(REF, n_valid_runs=REF["n_valid_runs"] + 1)
check("C21 a held run and a filtered v7 equal to it with the right count: pass", rc(A7, HB, 21, REF), 0)
check("C22 the plain v7 count is not the filtered count plus the held runs (filtered = newer): fails", rc(dict(REF, n_valid_runs=REF["n_valid_runs"] + 3), HB, 22, REF), 1)
HB2 = copy.deepcopy(HB)
HB2["inputs_manifest"]["cq_on24000_flat_stand_on_s1000"] = {}
check("C23 a held run that is still used: fails", rc(A7, HB2, 23, REF), 1)
RB = copy.deepcopy(NEW)
RB["hold_released"] = [{"tag": "cq_on24000_flat_stand_on_s1000_NOT_USED"}]
check("C24 a released run that is not used: fails", rc(REF, RB, 24), 1)
shutil.rmtree(T, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
