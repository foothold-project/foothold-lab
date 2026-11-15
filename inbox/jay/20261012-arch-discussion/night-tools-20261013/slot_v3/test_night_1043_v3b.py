"""Failure-path tests for night_20261013_cmdr1043_v3.sh, v3b (lead 세션 · Claude 하위 작업 · 2026-10-13 밤 · ASTRA 17c §2.1).
Same cases as test_night_1043_v3.py (kept unchanged); only the mv failure injection differs.
v3 put an `mv` script in front of PATH. Git Bash puts /usr/bin first, so `command -v mv` was /usr/bin/mv, the real move succeeded and
N2 judged a run in which nothing failed (ASTRA 17c: 7/8 there). v3b defines `mv` as a shell function through BASH_ENV, which bash reads
before running the script, and the function writes a marker line each time it is called; N2 requires that marker.
The script is copied into a temp _eval/branch tree under the system temp dir; isaac_slot.py and validate_branch.py are stubs.
NIGHT_SCRIPT may point at a mutated copy; NIGHT_V3B_ONLY=N2,N3 runs only those checks. Exit 1 when any check fails."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("NIGHT_SCRIPT", os.path.join(HERE, "night_20261013_cmdr1043_v3.sh"))
BASHES = []
for _b in (shutil.which("bash"), "C:/Program Files/Git/bin/bash.exe", "C:/Program Files/Git/usr/bin/bash.exe"):
    if _b and os.path.exists(_b) and os.path.normcase(os.path.abspath(_b)) not in [os.path.normcase(os.path.abspath(x)) for x in BASHES]:
        BASHES.append(_b)
BASH = BASHES[0]  # the same choice as test_night_1043_v3.py; N0 / N2 / N2b also run under every other Git Bash found
ONLY = {x for x in os.environ.get("NIGHT_V3B_ONLY", "").split(",") if x}
fails = []

SLOT = r'''
import json, os, sys
log = os.environ.get("CALLS")
open(log, "a").write(json.dumps({"who": "slot", "argv": sys.argv[1:], "branch_out": os.environ.get("BRANCH_OUT")}) + "\n")
sys.exit(int(os.environ.get("SLOT_RC", "0")))
'''
VAL = r'''
import json, os, sys
log = os.environ.get("CALLS")
open(log, "a").write(json.dumps({"who": "val", "argv": sys.argv[1:], "branch_out": os.environ.get("BRANCH_OUT")}) + "\n")
if "--reuse_check" in sys.argv:
    sys.exit(int(os.environ.get("REUSE_RC", "1")))
sys.exit(int(os.environ.get("VAL_RC", "0")))
'''
MV_FAIL = 'mv() { printf "%s\\n" "$*" >> "$MV_MARK"; return 1; }\n'
MV_NOOP = 'mv() { printf "%s\\n" "$*" >> "$MV_MARK"; return 0; }\n'


def want(name):
    return not ONLY or name in ONLY


def check(name, got, exp):
    ok = got == exp
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:240], "want", repr(exp)[:160], flush=True)
    if not ok:
        fails.append(name)


def fwd(p):
    return p.replace("\\", "/")


def run(case, env_extra=None, pre=None, mv_func=None, bash=None):
    """Returns (rc, output, calls, mv marker lines or None, what is left in out_branch)."""
    tmp = tempfile.mkdtemp(prefix=f"n3b_{case}_")
    try:
        ev = os.path.join(tmp, "_eval")
        br = os.path.join(ev, "branch")
        bro = os.path.join(ev, "out_branch")
        os.makedirs(bro)
        os.makedirs(br)
        s = open(SCRIPT, encoding="utf-8").read().replace("PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe", "PY=" + fwd(sys.executable))
        open(os.path.join(br, "night.sh"), "w", encoding="utf-8", newline="\n").write(s)
        open(os.path.join(ev, "isaac_slot.py"), "w").write(SLOT)
        open(os.path.join(br, "validate_branch.py"), "w").write(VAL)
        calls = os.path.join(tmp, "calls.jsonl")
        env = dict(os.environ, CALLS=calls)
        env.pop("BASH_ENV", None)
        mark = os.path.join(tmp, "mv_called.txt")
        if mv_func:
            be = os.path.join(tmp, "bash_env.sh")
            open(be, "w", newline="\n").write(mv_func)
            env["BASH_ENV"] = fwd(be)
            env["MV_MARK"] = fwd(mark)
        env.update(env_extra or {})
        if pre:
            pre(bro)
        r = subprocess.run([bash or BASH, fwd(os.path.join(br, "night.sh")), "decision text"], capture_output=True, text=True,
                           env=env, encoding="utf-8", errors="replace", timeout=120)
        cl = [json.loads(x) for x in open(calls)] if os.path.exists(calls) else []
        marks = open(mark, encoding="utf-8").read().splitlines() if os.path.exists(mark) else None
        left = sorted(os.listdir(bro))
        return r.returncode, r.stdout + r.stderr, cl, marks, left
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def old_attempt(bro):
    os.makedirs(os.path.join(bro, "cmdr_s1043_off_u4000"))
    open(os.path.join(bro, "cmdr_s1043_off_u4000", "result.json"), "w").write("{}")
    open(os.path.join(bro, "cmdr_s1043_off_u4000.log"), "w").write("[BRANCH] done cmdr_s1043_off_u4000\n")


print("INFO bash", BASHES, flush=True)
if not ONLY:
    sb = tempfile.mkdtemp(prefix="n3b_path_")
    try:
        open(os.path.join(sb, "mv"), "w", newline="\n").write("#!/usr/bin/env bash\nexit 1\n")
        pe = dict(os.environ, PATH=fwd(sb) + os.pathsep + os.environ["PATH"])
        for b in BASHES:
            r = subprocess.run([b, "-c", "command -v mv"], capture_output=True, text=True, env=pe)
            print("INFO the v3 PATH stub under", b, "resolves mv to", r.stdout.strip(), "(stub", fwd(os.path.join(sb, "mv")) + ")", flush=True)
    finally:
        shutil.rmtree(sb, ignore_errors=True)

if want("N0"):
    tmp = tempfile.mkdtemp(prefix="n3b_n0_")
    try:
        be = os.path.join(tmp, "bash_env.sh")
        open(be, "w", newline="\n").write(MV_FAIL)
        got = [subprocess.run([b, "-c", "type -t mv"], capture_output=True, text=True,
                              env=dict(os.environ, BASH_ENV=fwd(be), MV_MARK=fwd(os.path.join(tmp, "m")))).stdout.strip() for b in BASHES]
        check("N0 precondition: under every Git Bash found a BASH_ENV function named mv takes precedence (type -t mv)", got, ["function"] * len(BASHES))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
if want("N1"):
    rc, out, cl, _, _ = run("ok")
    vals = [c for c in cl if c["who"] == "val" and "--reuse_check" not in c["argv"]]
    check("N1 both arms run and validate: PAIR DONE, exit 0, validator gets --attempt and --since",
          (rc, "PAIR 1043 DONE" in out, len(vals), all("--attempt" in c["argv"] and "--since" in c["argv"] for c in vals)), (0, True, 2, True))
if want("N2"):
    got = []
    for b in BASHES:
        rc, out, cl, marks, left = run("mvfail", pre=old_attempt, mv_func=MV_FAIL, bash=b)
        got.append((rc, marks is not None and len(marks) >= 1 and "cmdr_s1043_off_u4000" in marks[0], "옮기지 못함" in out, "PAIR 1043 DONE" in out,
                    sum(c["who"] == "slot" for c in cl), "cmdr_s1043_off_u4000" in left))
    check("N2 (17b 2.1 · 17c 2.1) moving an earlier attempt aside fails (BASH_ENV mv function, its marker seen), under every Git Bash: "
          "stop (4) at that move, before any launch, no PAIR DONE, the earlier attempt left in place",
          got, [(4, True, True, False, 0, True)] * len(BASHES))
if want("N2b"):
    got = []
    for b in BASHES:
        rc, out, cl, marks, left = run("mvnoop", pre=old_attempt, mv_func=MV_NOOP, bash=b)
        got.append((rc, marks is not None and len(marks) >= 1, "아직 원래 자리에 있음" in out, sum(c["who"] == "slot" for c in cl)))
    check("N2b mv reports success but moves nothing (marker seen), under every Git Bash: the after-move check stops (4) before any launch",
          got, [(4, True, True, 0)] * len(BASHES))
if want("N3"):
    rc, out, cl, _, _ = run("slotfail", {"SLOT_RC": "7"})
    check("N3 (17b 2.1) the slot / child fails: stop (5) without calling the validator for that arm",
          (rc, sum(c["who"] == "val" and "--reuse_check" not in c["argv"] for c in cl), sum(c["who"] == "slot" for c in cl)), (5, 0, 1))
if want("N4"):
    rc, out, cl, _, _ = run("valfail", {"VAL_RC": "1"})
    check("N4 the validator rejects the first arm: stop (6), the second arm is not launched", (rc, sum(c["who"] == "slot" for c in cl)), (6, 1))
if want("N5"):
    rc, out, cl, _, _ = run("stop", pre=lambda bro: open(os.path.join(bro, "STOP_1043"), "w").close())
    check("N5 a stop file: no launch (7)", (rc, sum(c["who"] == "slot" for c in cl)), (7, 0))
if want("N6"):
    rc, out, cl, _, _ = run("reuse", {"REUSE_RC": "0"})
    check("N6 both arms pass the reuse check: no launch, PAIR DONE", (rc, sum(c["who"] == "slot" for c in cl), "PAIR 1043 DONE" in out), (0, 0, True))
if want("N7"):
    rc, out, cl, _, _ = run("iso")
    slots = [c["argv"] for c in cl if c["who"] == "slot"]
    check("N7 every launch goes through usd_isolate_run.py with its own --usd_root and --attempt",
          all(any(x.endswith("usd_isolate_run.py") for x in a) and "--usd_root" in a and "--attempt" in a for a in slots) and len(slots) == 2, True)
if want("N8"):
    rc, out, cl, _, _ = run("root")
    check("N8 every slot and validator call gets BRANCH_OUT=../out_branch and no argument points into _eval/out",
          (len(cl) > 0, all(c.get("branch_out") == "../out_branch" for c in cl),
           any("/out/" in x.replace("\\", "/") or x.replace("\\", "/").startswith("../out/") for c in cl for x in c["argv"])), (True, True, False))
print("FAILS", fails)
sys.exit(1 if fails else 0)
