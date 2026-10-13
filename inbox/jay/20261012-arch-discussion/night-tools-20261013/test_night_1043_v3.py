"""Failure-path tests for night_20261013_cmdr1043_v3.sh with stubs (lead 10/13 evening · ASTRA 17b 2.1 counterexample kept).
The script is copied into a temp _eval/branch tree; isaac_slot.py, validate_branch.py and mv are stubs controlled by env vars.
NIGHT_SCRIPT may point at a mutated copy. Exit 1 when any check fails."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("NIGHT_SCRIPT", os.path.join(HERE, "night_20261013_cmdr1043_v3.sh"))
BASH = shutil.which("bash") or "C:/Program Files/Git/bin/bash.exe"
fails = []

SLOT = r'''
import json, os, sys
log = os.environ.get("CALLS")
open(log, "a").write(json.dumps({"who": "slot", "argv": sys.argv[1:]}) + "\n")
sys.exit(int(os.environ.get("SLOT_RC", "0")))
'''
VAL = r'''
import json, os, sys
log = os.environ.get("CALLS")
open(log, "a").write(json.dumps({"who": "val", "argv": sys.argv[1:]}) + "\n")
if "--reuse_check" in sys.argv:
    sys.exit(int(os.environ.get("REUSE_RC", "1")))
sys.exit(int(os.environ.get("VAL_RC", "0")))
'''


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:200], "want", repr(want)[:120])
    if not ok:
        fails.append(name)


def run(case, env_extra=None, pre=None, mv_fail=False):
    tmp = tempfile.mkdtemp(prefix=f"n3_{case}_", dir=HERE)
    try:
        ev = os.path.join(tmp, "_eval")
        br = os.path.join(ev, "branch")
        os.makedirs(os.path.join(ev, "out", "branch"))
        os.makedirs(br)
        s = open(SCRIPT, encoding="utf-8").read().replace("PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe",
                                                          "PY=" + sys.executable.replace("\\", "/"))
        open(os.path.join(br, "night.sh"), "w", encoding="utf-8", newline="\n").write(s)
        open(os.path.join(ev, "isaac_slot.py"), "w").write(SLOT)
        open(os.path.join(br, "validate_branch.py"), "w").write(VAL)
        calls = os.path.join(tmp, "calls.jsonl")
        env = dict(os.environ, CALLS=calls)
        if mv_fail:
            sb = os.path.join(tmp, "stubbin")
            os.makedirs(sb)
            open(os.path.join(sb, "mv"), "w", newline="\n").write("#!/usr/bin/env bash\nexit 1\n")
            env["PATH"] = sb.replace("\\", "/") + os.pathsep + env["PATH"]
        env.update(env_extra or {})
        if pre:
            pre(os.path.join(ev, "out", "branch"))
        r = subprocess.run([BASH, os.path.join(br, "night.sh").replace("\\", "/"), "decision text"], capture_output=True, text=True,
                           env=env, encoding="utf-8", errors="replace", timeout=120)
        cl = [json.loads(x) for x in open(calls)] if os.path.exists(calls) else []
        return r.returncode, r.stdout + r.stderr, cl
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def old_attempt(bro):
    os.makedirs(os.path.join(bro, "cmdr_s1043_off_u4000"))
    open(os.path.join(bro, "cmdr_s1043_off_u4000", "result.json"), "w").write("{}")
    open(os.path.join(bro, "cmdr_s1043_off_u4000.log"), "w").write("[BRANCH] done cmdr_s1043_off_u4000\n")


rc, out, cl = run("ok")
vals = [c for c in cl if c["who"] == "val" and "--reuse_check" not in c["argv"]]
check("N1 both arms run and validate: PAIR DONE, exit 0, validator gets --attempt and --since",
      (rc, "PAIR 1043 DONE" in out, len(vals), all("--attempt" in c["argv"] and "--since" in c["argv"] for c in vals)), (0, True, 2, True))
rc, out, cl = run("mvfail", pre=old_attempt, mv_fail=True)
check("N2 (17b 2.1) moving an earlier attempt aside fails: stop (4) before any launch, no PAIR DONE",
      (rc, "PAIR 1043 DONE" in out, sum(c["who"] == "slot" for c in cl)), (4, False, 0))
rc, out, cl = run("slotfail", {"SLOT_RC": "7"})
check("N3 (17b 2.1) the slot / child fails: stop (5) without calling the validator for that arm",
      (rc, sum(c["who"] == "val" and "--reuse_check" not in c["argv"] for c in cl), sum(c["who"] == "slot" for c in cl)), (5, 0, 1))
rc, out, cl = run("valfail", {"VAL_RC": "1"})
check("N4 the validator rejects the first arm: stop (6), the second arm is not launched", (rc, sum(c["who"] == "slot" for c in cl)), (6, 1))
rc, out, cl = run("stop", pre=lambda bro: open(os.path.join(bro, "STOP_1043"), "w").close())
check("N5 a stop file: no launch (7)", (rc, sum(c["who"] == "slot" for c in cl)), (7, 0))
rc, out, cl = run("reuse", {"REUSE_RC": "0"})
check("N6 both arms pass the reuse check: no launch, PAIR DONE", (rc, sum(c["who"] == "slot" for c in cl), "PAIR 1043 DONE" in out), (0, 0, True))
rc, out, cl = run("iso")
slots = [c["argv"] for c in cl if c["who"] == "slot"]
check("N7 every launch goes through usd_isolate_run.py with its own --usd_root and --attempt",
      all(any(x.endswith("usd_isolate_run.py") for x in a) and "--usd_root" in a and "--attempt" in a for a in slots) and len(slots) == 2, True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
