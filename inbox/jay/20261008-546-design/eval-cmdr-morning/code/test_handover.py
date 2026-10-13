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

    ev, out = tree("h9")
    secret = [{"pid": 7000, "ppid": 1, "name": "python.exe", "cmdline": ["C:/x/python.exe", "C:/tools/server.py", "--token=SECRETVALUE", "--key", "SECRET2"], "create_time": 1.0},
              {"pid": 7001, "ppid": 1, "name": "chrome.exe", "cmdline": ["chrome.exe", "--x"], "create_time": None}]
    late9 = secret + [{"pid": 9001, "ppid": 1, "name": "python.exe", "cmdline": ["python.exe", "q_eval_cmdr.py", "SECRETARG", "--headless"], "create_time": 5.0}]
    rc, res, man = run(ev, procs=[secret, late9])
    sc = json.load(open(os.path.join(res["dir"], "scans.json"), encoding="utf-8")) if "dir" in res else []
    raw = json.dumps(sc)
    check("H9 (16j 9.5 / 16k 6) both scans kept, every process listed, no argv value anywhere (also not in alive), end names the late Isaac",
          (rc, len(sc), [p_["pid"] for p_ in sc[0]["processes"]] if sc else None, "SECRET" in raw,
           [(a_["reason"], a_["pid"]) for a_ in sc[1]["alive"]] if len(sc) > 1 else None,
           man.get("scans_sha256") == sha(os.path.join(res["dir"], "scans.json")) if "dir" in res else None),
          (1, 2, [7000, 7001], False, [("isaac-like python", 9001)], True))

    # 16k 6: the saved record must give the verdict the rule gives; known answers written by hand
    ev, out = tree("h10")
    procs10 = [{"pid": 111, "ppid": 1, "name": "python.exe", "cmdline": None, "create_time": 1.0},  # old driver pid (argv unreadable)
               {"pid": 6000, "ppid": 111, "name": "cmd.exe", "cmdline": ["cmd.exe"], "create_time": None},  # non-python in between
               {"pid": 6001, "ppid": 6000, "name": "python.exe", "cmdline": ["python.exe", "safe.py"], "create_time": 3.0},
               {"pid": 6100, "ppid": 1, "name": "python.exe", "cmdline": ["python.exe", "cmdr_eval_driver_v37"], "create_time": 3.0},
               {"pid": 6200, "ppid": 1, "name": "python.exe", "cmdline": ["python"], "create_time": 3.0},
               {"pid": 6300, "ppid": 1, "name": "python.exe", "cmdline": ["python.exe", "safe.py", "--headless=false"], "create_time": 3.0},
               {"pid": 6400, "ppid": 1, "name": "python.exe", "cmdline": [], "create_time": 3.0},
               {"pid": 6500, "ppid": 1, "name": "kit.exe", "cmdline": ["kit.exe"], "create_time": 3.0}]
    rc, res, man = run(ev, procs=[procs10])
    sc = json.load(open(os.path.join(res["dir"], "scans.json"), encoding="utf-8")) if "dir" in res else []
    want = [("old driver", 111), ("descendant of an old driver", 6000), ("descendant of an old driver", 6001), ("isaac-like python", 6100), ("python with unreadable or empty argv", 6400), ("kit", 6500)]
    import importlib.util
    spec = importlib.util.spec_from_file_location("ho", SCRIPT)
    ho = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ho)
    again = ho.judge(sc[0]["processes"], sc[0]["old_pids"], sc[0]["scanner_pid"]) if sc else None
    check("H10 (16k 6) known answers: no-extension driver name caught, ['python'] and --headless=false not, lineage through a non-python parent kept; the saved record judges the same",
          ([(a_["reason"], a_["pid"]) for a_ in sc[0]["alive"]] if sc else None, [(a_["reason"], a_["pid"]) for a_ in again] if again is not None else None,
           sc[0]["rejudge_equal"] if sc else None),
          (want, want, True))

    def hold_tree(name, released=False):
        ev_, out_ = tree(name)
        os.makedirs(os.path.join(out_, "H0", "stamps"))
        open(os.path.join(out_, "H0", "stamps", "tX.json"), "w").write('{"attempt": "OLD-j1"}')
        e = {"stamp_sha256": sha(os.path.join(out_, "H0", "stamps", "tX.json")), "why": "w", "handover": "H0"}
        if released:
            evp = os.path.join(out_, "evidence_tX.json")
            open(evp, "w").write('{"comparison_ready": true}')
            e["released"] = {"by": "lead", "evidence": evp, "evidence_sha256": sha(evp)}
        json.dump({"tX": e}, open(os.path.join(out_, "cmdr_post_hold.json"), "w"))
        return ev_, out_

    ev, out = hold_tree("h11")
    rc, res, man = run(ev)
    hp = os.path.join(res.get("dir", ""), "cmdr_post_hold.json")
    check("H11 (16k 7.2 / 16l 5.3) the hold list and the held original's stamp are copied into the bundle with their hashes",
          (rc, os.path.exists(hp), man.get("copies_sha256", {}).get("cmdr_post_hold.json") == (sha(hp) if os.path.exists(hp) else None),
           sorted(man.get("release_deps", {}))), (0, True, True, ["held_stamps/tX.json"]))
    ev, out = hold_tree("h11b")
    rc, res, man = run(ev, touch=os.path.join(out, "cmdr_post_hold.json"))
    check("H11b the hold list changes during the freeze: exit 1, named", (rc, "cmdr_post_hold.json" in json.dumps(man.get("problems"))), (1, True))
    ev, out = tree("h12")
    rc, res, man = run(ev, touch=os.path.join(out, "cmdr_post_hold.json"))
    check("H12 (16l 5.2) a hold list that appears during the freeze: exit 1, named", (rc, "appeared" in json.dumps(man.get("problems"))), (1, True))
    ev, out = hold_tree("h13", released=True)
    rc, res, man = run(ev)
    evc = os.path.join(res.get("dir", ""), "evidence", "tX.json")
    check("H13 (16l 5.3) a release's evidence is copied into the bundle, byte for byte",
          (rc, sorted(man.get("release_deps", {})), os.path.exists(evc) and sha(evc) == sha(os.path.join(out, "evidence_tX.json"))),
          (0, ["evidence/tX.json", "held_stamps/tX.json"], True))
    ev, out = hold_tree("h13b", released=True)
    open(os.path.join(out, "evidence_tX.json"), "a").write(" ")
    rc, res, man = run(ev)
    check("H13b evidence that is not the recorded bytes: exit 1", (rc, "release evidence" in json.dumps(man.get("problems"))), (1, True))
    ev, out = hold_tree("h13c", released=True)
    rc, res, man = run(ev, touch=os.path.join(out, "evidence_tX.json"))
    check("H13c evidence that changes during the freeze: exit 1", (rc, "release dependency" in json.dumps(man.get("problems"))), (1, True))
    ev, out = tree("h13d")
    os.makedirs(os.path.join(out, "H0", "stamps"))
    open(os.path.join(out, "H0", "stamps", "tX.json"), "w").write('{"attempt": "OTHER"}')  # present, but not the held bytes
    json.dump({"tX": {"stamp_sha256": "0" * 64, "why": "w", "handover": "H0"}}, open(os.path.join(out, "cmdr_post_hold.json"), "w"))
    rc, res, man = run(ev)
    check("H13d a stamp copy that is there but not the held bytes: exit 1, named as not found by its hash", (rc, "held original stamp not found by its hash" in json.dumps(man.get("problems"))), (1, True))

    ev, out = tree("h8")
    open(os.path.join(ev, "q_metrics.py"), "a").write("# changed\n")
    rc, res, man = run(ev)
    check("H8 pins differ from the logs: exit 1", (rc, "pins differ" in json.dumps(man.get("problems"))), (1, True))
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
