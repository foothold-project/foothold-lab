"""Known-answer tests for validate_branch.py on copies of the finished 1042 'on' arm (lead 10/13 evening).
VALIDATE_SCRIPT may point at a mutated copy. Exit 1 when any check fails."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("VALIDATE_SCRIPT", os.path.join(HERE, "validate_branch.py"))
SRC = os.path.join(HERE, "..", "out", "branch")
TAG0 = "cmdr_s1042_on_u4000"
PARENT = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/model_20000.pt"
TMP = tempfile.mkdtemp(prefix="vb_", dir=HERE)
fails = []


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:160], "want", repr(want)[:80])
    if not ok:
        fails.append(name)


def make(case):
    root = os.path.join(TMP, case)
    d = os.path.join(root, TAG0)
    os.makedirs(d)
    for f in ("result.json", "saves.json"):
        shutil.copy2(os.path.join(SRC, TAG0, f), os.path.join(d, f))
    for f in ("model_22000.pt", "model_24000.pt"):
        open(os.path.join(d, f), "wb").write(b"weights " + f.encode())
    shutil.copy2(os.path.join(SRC, TAG0 + ".log"), os.path.join(root, TAG0 + ".log"))
    shutil.copy2(os.path.join(SRC, TAG0 + ".guard.json"), os.path.join(root, TAG0 + ".guard.json"))
    json.dump({"slot_rc": 0, "conflicts": {}, "usd_final": ["20261013_190000_1"]}, open(os.path.join(root, TAG0 + ".slot.json"), "w"))
    return root, d


def run(root, *extra, seed=1042):
    r = subprocess.run([sys.executable, SCRIPT, "--tag", TAG0, "--parent", PARENT, "--seed", str(seed), "--num_envs", "8192", "--updates", "4000",
                        "--cmdr", "on", *extra], capture_output=True, text=True, env=dict(os.environ, BRANCH_OUT=root))
    return r.returncode, (r.stdout.strip() or r.stderr.strip()[-200:])


def edit_json(p, fn):
    o = json.load(open(p, encoding="utf-8"))
    fn(o)
    json.dump(o, open(p, "w", encoding="utf-8"))


try:
    root, d = make("v1")
    rc, out = run(root)
    check("V1 the finished 1042 arm with a clean slot record: valid", rc, 0)
    root, d = make("v2")
    s = open(os.path.join(root, TAG0 + ".log"), encoding="utf-8", errors="replace").read().replace(f"[BRANCH] done {TAG0}", "")
    open(os.path.join(root, TAG0 + ".log"), "w", encoding="utf-8").write(s)
    check("V2 no [BRANCH] done line: invalid", run(root)[0], 1)
    root, d = make("v3")
    open(os.path.join(root, TAG0 + ".log"), "a", encoding="utf-8").write("\nTraceback (most recent call last):\n")
    check("V3 a Traceback in the log: invalid", run(root)[0], 1)
    root, d = make("v4")
    check("V4 the run's seed is not the requested one (1043 asked): invalid", run(root, seed=1043)[0], 1)
    root, d = make("v5")
    os.remove(os.path.join(d, "model_24000.pt"))
    check("V5 the last checkpoint missing: invalid", run(root)[0], 1)
    root, d = make("v5b")
    open(os.path.join(d, "model_24000.pt"), "wb").close()
    rc, out = run(root)
    check("V5b a zero-byte last checkpoint: invalid, named", (rc, "missing model_24000.pt" in out), (1, True))
    root, d = make("v6")
    edit_json(os.path.join(root, TAG0 + ".guard.json"), lambda o: o.update(exit_code=1))
    check("V6 guard exit 1: invalid", run(root)[0], 1)
    root, d = make("v7")
    edit_json(os.path.join(root, TAG0 + ".slot.json"), lambda o: o.update(conflicts={"x": ["other.log"]}))
    check("V7 the slot record names a USD conflict: invalid", run(root)[0], 1)
    root, d = make("v8")
    a0 = run(root, "--reuse_check")[0]
    a1 = run(root, "--stamp", "--attempt", "t")[0]
    a2 = run(root, "--reuse_check")[0]
    open(os.path.join(d, "model_24000.pt"), "ab").write(b"x")
    a3 = run(root, "--reuse_check")[0]
    check("V8 reuse: no stamp 1 · stamp written 0 · stamp matches 0 · checkpoint changed after the stamp 1", (a0, a1, a2, a3), (1, 0, 0, 1))
    root, d = make("v9")
    edit_json(os.path.join(d, "result.json"), lambda o: o["final_state"].update(iter_from_counter=23001))
    check("V9 the run stopped short (iter_from_counter 23001): invalid", run(root)[0], 1)
    root, d = make("v10")
    edit_json(os.path.join(d, "result.json"), lambda o: o["meta"].update(parent_sha256="0" * 64))
    check("V10 the recorded parent sha256 is not the parent file now: invalid", run(root)[0], 1)
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
