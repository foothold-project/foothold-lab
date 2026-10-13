"""Known-answer tests for handover_1400.py on a made-up eval folder (lead 10/13, VERIFY-astra-16h 4.1 / 4.2 / 5.2 H).
Runs the real script as a subprocess with HANDOVER_EV pointing at a temp tree. Exit 1 when any check fails."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.environ.get("HANDOVER_SCRIPT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "handover_1400.py"))
fails = []
TMP = tempfile.mkdtemp(prefix="hot_", dir=os.path.dirname(os.path.abspath(__file__)))


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:160], "want", repr(want)[:100])
    if not ok:
        fails.append(name)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


RUNF = ["meta.json", "cells.json", "episodes.csv", "traj.npz", "env_origins.npy", "driver_stamp.json"]


def tree(name):
    ev = os.path.join(TMP, name, "_eval")
    out = os.path.join(ev, "out")
    os.makedirs(os.path.join(out, "branch", "cmdr_s1042_off_u4000"))
    for f in ["q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py"]:
        open(os.path.join(ev, f), "w").write(f"# {f}\n")
    json.dump({"meta": {"code": {"files_sha256": {}}}}, open(os.path.join(out, "branch", "cmdr_s1042_off_u4000", "bundle.json"), "w"))
    ck = os.path.join(out, "ck.pt")
    open(ck, "wb").write(b"weights")
    pins = {f: sha(os.path.join(ev, f)) for f in ["q_eval_cmdr.py", "q_metrics.py", "q_post.py", "gpu_guard.py", "cmdr_bundle_compare.py"]}
    for t in ("tA", "tB", "tC"):
        os.makedirs(os.path.join(out, t))
        for f in RUNF:
            open(os.path.join(out, t, f), "w").write(f"{t} {f}\n")
        for ext in (".log", ".guard.json"):
            open(os.path.join(out, t + ext), "w").write(f"{t}{ext}\n")
    base = {"pins": pins, "ckpt": {"m": {"path": ck, "sha256": sha(ck)}}, "matrix": {"tA": "valid", "tB": "invalid"},
            "runs": [{"tag": "tA", "valid": True}, {"tag": "tB", "valid": False}]}
    g0 = {"pins": pins, "ckpt": {"m": {"path": ck, "sha256": sha(ck)}}, "matrix": {"tC": "valid"}, "runs": [{"tag": "tC", "valid": True}]}
    json.dump(base, open(os.path.join(out, "cmdr_eval_driver.json"), "w"))
    json.dump(g0, open(os.path.join(out, "cmdr_eval_driver_g0.json"), "w"))
    open(os.path.join(out, "cmdr_eval_driver_g0.stop"), "w").write("")
    return ev, out


def run(ev, procs=None, touch=None):
    pf = os.path.join(os.path.dirname(ev), "procs.json")
    json.dump(procs if procs is not None else [[]], open(pf, "w"))
    env = dict(os.environ, HANDOVER_EV=ev, HANDOVER_ROOT=os.path.dirname(ev), HANDOVER_FAKE_PROCS=pf)
    if touch:
        env["HANDOVER_TEST_TOUCH"] = touch
    r = subprocess.run([sys.executable, SCRIPT, "111", "222"], capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        res = {"stdout": r.stdout[-300:], "stderr": r.stderr[-300:]}
    man = json.load(open(os.path.join(res["dir"], "manifest.json"), encoding="utf-8")) if "dir" in res else {}
    return r.returncode, res, man


try:
    ev, out = tree("h1")
    rc, res, man = run(ev)
    check("H1 clean tree: exit 0, complete, env_origins hashed, stop request moved, invalid run kept",
          (rc, man.get("status"), man["runs"]["tA"].get("env_origins.npy") is not None, res.get("stop_requests_moved"),
           os.path.exists(os.path.join(out, "cmdr_eval_driver_g0.stop")), man["runs"]["tB"]["_valid_in_log"]),
          (0, "complete", True, ["cmdr_eval_driver_g0.stop"], False, False))

    ev, out = tree("h1b")
    open(os.path.join(out, "hud_follow.stop"), "w").write("")
    rc, res, man = run(ev)
    check("H1b (16i 4) another job's stop file stays and is listed; only the driver's own stop moves",
          (rc, os.path.exists(os.path.join(out, "hud_follow.stop")), man.get("stop_requests_other_kept"), man.get("stop_requests_moved")),
          (0, True, ["hud_follow.stop"], ["cmdr_eval_driver_g0.stop"]))

    ev, out = tree("h1c")
    os.remove(os.path.join(out, "cmdr_eval_driver_g0.stop"))
    rc, res, man = run(ev, touch=os.path.join(out, "cmdr_eval_driver_g0.stop"))
    check("H1c a driver stop that appears during the freeze is a new request: kept, not moved",
          (rc, os.path.exists(os.path.join(out, "cmdr_eval_driver_g0.stop")), man.get("stop_requests_new_kept"), man.get("stop_requests_moved")),
          (0, True, ["cmdr_eval_driver_g0.stop"], []))

    ev, out = tree("h1d")
    rc, res, man = run(ev, touch=os.path.join(out, "cmdr_eval_driver_g0.stop"))
    check("H1d a driver stop whose bytes changed during the freeze: kept, listed as changed",
          (rc, os.path.exists(os.path.join(out, "cmdr_eval_driver_g0.stop")), man.get("stop_requests_changed_kept"), man.get("stop_requests_moved")),
          (0, True, ["cmdr_eval_driver_g0.stop"], []))

    ev, out = tree("h2")
    os.remove(os.path.join(out, "tA", "episodes.csv"))
    rc, res, man = run(ev)
    check("H2 a valid run without episodes.csv: exit 1, failed, the stop request stays",
          (rc, man.get("status"), os.path.exists(os.path.join(out, "cmdr_eval_driver_g0.stop"))), (1, "failed", True))

    ev, out = tree("h3")
    os.remove(os.path.join(out, "tC.log"))
    rc, res, man = run(ev)
    check("H3 a valid run without its .log: exit 1", (rc, man.get("status")), (1, "failed"))

    ev, out = tree("h4")
    os.remove(os.path.join(out, "tB", "traj.npz"))
    os.remove(os.path.join(out, "tB.log"))
    rc, res, man = run(ev)
    check("H4 a run that is not valid may miss files: exit 0, the missing ones recorded",
          (rc, sorted(man["runs"]["tB"].get("_missing", []))), (0, [".log", "traj.npz"]))

    ev, out = tree("h5")
    rc, res, man = run(ev, touch=os.path.join(out, "tA", "episodes.csv"))
    check("H5 a run file changes after it was hashed: exit 1, named", (rc, "tA/episodes.csv" in json.dumps(man.get("problems"))), (1, True))

    ev, out = tree("h5b")
    rc, res, man = run(ev, touch=os.path.join(out, "cmdr_eval_driver.json"))
    check("H5b the original log changes after it was copied: exit 1", (rc, "cmdr_eval_driver.json" in json.dumps(man.get("problems"))), (1, True))

    ev, out = tree("h6")
    late = [{"pid": 9001, "ppid": 1, "name": "python.exe", "cmdline": ["python.exe", "q_eval_cmdr.py", "--headless"], "create_time": 5.0}]
    rc, res, man = run(ev, procs=[[], late])
    check("H6 an Isaac process appears after the first scan: exit 1 at the end scan", (rc, "alive at the end" in json.dumps(man.get("problems"))), (1, True))

    ev, out = tree("h7")
    kids = [{"pid": 111, "ppid": 1, "name": "python.exe", "cmdline": ["python.exe", "cmdr_eval_driver.py"], "create_time": 1.0},
            {"pid": 5000, "ppid": 111, "name": "python.exe", "cmdline": ["python.exe", "gpu_guard.py", "x"], "create_time": 2.0},
            {"pid": 5001, "ppid": 4999, "name": "python.exe", "cmdline": ["python.exe", "something.py"], "create_time": 3.0}]
    rc, res, man = run(ev, procs=[kids])
    a = json.dumps(man.get("problems"))
    check("H7 the old driver and its child are alive: exit 1, both named", (rc, "old driver" in a, "5000" in a), (1, True, True))

    ev, out = tree("h8")
    open(os.path.join(ev, "q_metrics.py"), "a").write("# changed\n")
    rc, res, man = run(ev)
    check("H8 pins differ from the logs: exit 1", (rc, "pins differ" in json.dumps(man.get("problems"))), (1, True))
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
