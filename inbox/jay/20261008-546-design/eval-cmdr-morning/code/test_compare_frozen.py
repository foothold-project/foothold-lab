"""Known-answer tests for compare_frozen.py on the real frozen 14:04 outputs, changed in memory copies (16j 6). Exit 1 on failure."""
import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("CF_SCRIPT", os.path.join(HERE, "compare_frozen.py"))
H = "C:/isaac/ext/go2_rl_robotlab/_eval/out/handover_20261013_140449"
A = json.load(open(f"{H}/v7/cmdr_post.json", encoding="utf-8"))
B = json.load(open(f"{H}/v8/cmdr_post.json", encoding="utf-8"))
fails = []
T = tempfile.mkdtemp(prefix="cft_", dir=HERE)


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", got, "want", want)
    if not ok:
        fails.append(name)


def rc(a, b, k):
    pa, pb = os.path.join(T, f"a{k}.json"), os.path.join(T, f"b{k}.json")
    json.dump(a, open(pa, "w", encoding="utf-8"))
    json.dump(b, open(pb, "w", encoding="utf-8"))
    return subprocess.run([sys.executable, SCRIPT, pa, pb], capture_output=True, text=True).returncode


check("C0 the real frozen pair passes", rc(A, B, 0), 0)
b1 = copy.deepcopy(B)
b1["contract_24000"]["off24000"]["cells"]["flat/stand/on"]["pass_k"] = 1
check("C1 (16j 6) the OFF arm's stand contract cell changed: fails (only the on run was held)", rc(A, b1, 1), 1)
b2 = copy.deepcopy(B)
b2["completion"]["off24000/obstacles"] = 999
check("C2 (16j 6) completion of an arm/family unrelated to the hold changed: fails", rc(A, b2, 2), 1)
b3 = copy.deepcopy(B)
e = next(x for x in b3["cells"] if x["family"] != "flat" or x["cell"] != "stand")
e["off24000"]["rate"] = 0.999
check("C3 (16j 6) a general cells entry changed: fails", rc(A, b3, 3), 1)
b4 = copy.deepcopy(B)
b4["target_verdict"]["24000"]["mean_pp"] = 999
check("C4 the target mean changed: fails", rc(A, b4, 4), 1)
b5 = copy.deepcopy(B)
b5["regression_coverage"]["done"] -= 1
check("C5 coverage lower by more than the held rows: fails", rc(A, b5, 5), 1)
b6 = copy.deepcopy(B)
b6["driver_pair_fail"] = ["x"]
check("C6 another top-level key differs: fails", rc(A, b6, 6), 1)
print("FAILS", fails)
sys.exit(1 if fails else 0)
