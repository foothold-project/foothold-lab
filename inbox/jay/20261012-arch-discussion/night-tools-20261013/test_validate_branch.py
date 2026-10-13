"""Known-answer tests for validate_branch.py v2 on copies of the finished 1042 'on' arm, with real checkpoints (lead 10/13 evening).
ASTRA 17b counterexamples are kept as cases. VALIDATE_SCRIPT may point at a mutated copy. Exit 1 when any check fails."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("VALIDATE_SCRIPT", os.path.join(HERE, "validate_branch.py"))
SRC = os.path.join(HERE, "..", "out", "branch")
TAG0 = "cmdr_s1042_on_u4000"
PARENT = "C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/model_20000.pt"
TMP = tempfile.mkdtemp(prefix="vb_", dir=HERE)
fails = []
T_START = time.mktime(time.strptime(json.load(open(os.path.join(SRC, TAG0, "result.json"), encoding="utf-8"))["meta"]["t_start"], "%Y-%m-%d %H:%M:%S"))


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:180], "want", repr(want)[:80])
    if not ok:
        fails.append(name)


def make(case):
    root = os.path.join(TMP, case)
    d = os.path.join(root, TAG0)
    os.makedirs(d)
    for f in ("result.json", "saves.json", "model_22000.pt", "model_24000.pt", "bundle.json", "bundle.npz"):
        shutil.copy2(os.path.join(SRC, TAG0, f), os.path.join(d, f))
    shutil.copy2(os.path.join(SRC, TAG0 + ".log"), os.path.join(root, TAG0 + ".log"))
    shutil.copy2(os.path.join(SRC, TAG0 + ".guard.json"), os.path.join(root, TAG0 + ".guard.json"))
    json.dump({"attempt": "A1", "slot_rc": 0, "child_rc": 0, "state_at_release": "scene_built", "usd_final": ["20261013_190000_1"],
               "usd_outside_root": [], "conflicts": {}, "t_request_epoch": T_START - 60,
               "cmd": ["py", "gpu_guard.py", "--", "py", "../usd_isolate_run.py", "branch_run.py", "--headless", "--tag", TAG0]},
              open(os.path.join(root, TAG0 + ".slot.json"), "w"))
    return root, d


def run(root, *extra, seed=1042, attempt="A1", since=None):
    args = [sys.executable, SCRIPT, "--tag", TAG0, "--parent", PARENT, "--seed", str(seed), "--num_envs", "8192", "--updates", "4000", "--cmdr", "on"]
    if attempt is not None:
        args += ["--attempt", attempt]
    args += ["--since", str(T_START - 120 if since is None else since)]
    r = subprocess.run(args + list(extra), capture_output=True, text=True, env=dict(os.environ, BRANCH_OUT=root), encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout.strip() or r.stderr.strip()[-300:])


def edit_json(p, fn):
    o = json.load(open(p, encoding="utf-8"))
    fn(o)
    json.dump(o, open(p, "w", encoding="utf-8"))


try:
    root, d = make("v1")
    rc, out = run(root)
    check("V1 the finished 1042 arm (real checkpoints) with a matching slot record: valid", (rc, out[:5]), (0, "VALID"))
    root, d = make("v2")
    s = open(os.path.join(root, TAG0 + ".log"), encoding="utf-8", errors="replace").read().replace(f"[BRANCH] done {TAG0}", "")
    open(os.path.join(root, TAG0 + ".log"), "w", encoding="utf-8").write(s)
    check("V2 no [BRANCH] done line: invalid", run(root)[0], 1)
    root, d = make("v3")
    open(os.path.join(root, TAG0 + ".log"), "a", encoding="utf-8").write("\nTraceback (most recent call last):\n")
    check("V3 a Traceback in the log: invalid", run(root)[0], 1)
    root, d = make("v3b")
    open(os.path.join(root, TAG0 + ".log"), "a", encoding="utf-8").write("\n[Error] </World/envs/env_0/Robot>: Unresolved reference prim path\n")
    check("V3b (17b 2.3) a robot root reference failure after the done line: invalid", run(root)[0], 1)
    root, d = make("v4")
    check("V4 the run's seed is not the requested one (1043 asked): invalid", run(root, seed=1043)[0], 1)
    root, d = make("v5")
    os.remove(os.path.join(d, "model_24000.pt"))
    check("V5 the last checkpoint missing: invalid", run(root)[0], 1)
    root, d = make("v5b")
    open(os.path.join(d, "model_24000.pt"), "wb").write(b"not a checkpoint")
    rc, out = run(root)
    check("V5b (17b 2.3) a .pt that is not a checkpoint: invalid", (rc, "not loadable" in out or "model_state_dict" in out), (1, True))
    root, d = make("v5c")
    shutil.copy2(os.path.join(SRC, TAG0, "model_22000.pt"), os.path.join(d, "model_24000.pt"))
    check("V5c (17b 2.3) model_24000.pt holds the 22000 checkpoint: invalid", run(root)[0], 1)
    root, d = make("v6")
    edit_json(os.path.join(root, TAG0 + ".guard.json"), lambda o: o.update(exit_code=1))
    check("V6 guard exit 1: invalid", run(root)[0], 1)
    root, d = make("v7")
    edit_json(os.path.join(root, TAG0 + ".slot.json"), lambda o: o.update(conflicts={"x": ["other.log"]}))
    check("V7 the slot record names a USD conflict: invalid", run(root)[0], 1)
    root, d = make("v7b")
    edit_json(os.path.join(root, TAG0 + ".slot.json"), lambda o: o.update(child_rc=1, state_at_release="exited"))
    check("V7b (17b 2.3) slot_rc 0 but child_rc 1 and released at exit: invalid", run(root)[0], 1)
    root, d = make("v7c")
    edit_json(os.path.join(root, TAG0 + ".slot.json"), lambda o: o.update(cmd=["py", "branch_run.py", "--tag", TAG0]))
    check("V7c the slot command did not use the USD isolation launcher: invalid", run(root)[0], 1)
    root, d = make("v7d")
    check("V7d (17b 2.1) the slot record is another attempt's: invalid", run(root, attempt="A2")[0], 1)
    root, d = make("v7e")
    check("V7e (17b 2.1) results older than this attempt (since after t_start): invalid", run(root, since=T_START + 3600)[0], 1)
    root, d = make("v8")
    a0 = run(root, "--reuse_check")[0]
    a1 = run(root, "--stamp")[0]
    rc2, out2 = run(root, "--reuse_check", attempt=None)
    open(os.path.join(d, "result.json"), "a").write(" ")
    a3 = run(root, "--reuse_check", attempt=None)[0]
    check("V8 reuse: no stamp 1 · stamp 0 · reuse keeps the original attempt 0 · a file changed after the stamp 1",
          (a0, a1, rc2, "attempt A1" in out2, a3), (1, 0, 0, True, 1))
    root, d = make("v9")
    edit_json(os.path.join(d, "result.json"), lambda o: o["final_state"].update(iter_from_counter=23001))
    check("V9 the run stopped short (iter_from_counter 23001): invalid", run(root)[0], 1)
    root, d = make("v10")
    edit_json(os.path.join(d, "result.json"), lambda o: o["meta"].update(parent_sha256="0" * 64))
    check("V10 the recorded parent sha256 is not the parent file now: invalid", run(root)[0], 1)
    root, d = make("v11")
    edit_json(os.path.join(d, "saves.json"), lambda o: o[-1].update(file="model_20000.pt"))
    check("V11 (17b 2.3) the last save record names another file: invalid", run(root)[0], 1)
    root, d = make("v12")
    os.remove(os.path.join(d, "bundle.npz"))
    check("V12 bundle.npz missing: invalid", run(root)[0], 1)
    root, d = make("v13")
    check("V13 no --attempt: invalid", run(root, attempt=None)[0], 1)
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
