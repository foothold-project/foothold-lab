"""Observer tests on a scratch run directory: a clean attempt passes (or is UNKNOWN only because of WDDM limits), a leftover
process that carries the run directory in its argv is a HOLD, a held GPU lease is a HOLD, a second observation is refused.
Runs real OS processes and the real file locks, no GPU work."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s2_family_observer as ob

UUID = "GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"
FAILS = []


def check(name, good):
    print(("PASS" if good else "FAIL") + " " + name, flush=True)
    if not good:
        FAILS.append(name)


def fresh_run():
    run = Path(tempfile.mkdtemp(prefix="s2_obs_run_"))
    (run / "ctl").mkdir()
    (run / "out").mkdir()
    (run / "summary.json").write_text(json.dumps({"supervisor_rc": 42}), encoding="utf-8")
    (run / "out" / "completion.json").write_text(json.dumps({"verdict": "HOLD_INFORMATION_ONLY", "family_active_count": 0}), encoding="utf-8")
    return run


def verdict(run):
    return json.loads((run / "family_observation.json").read_text(encoding="utf-8"))


def main():
    ob.GAP_S = 1.0
    run = fresh_run()
    check("record writes a baseline", ob.main(["record", "--run", str(run), "--gpu-uuid", UUID]) == 0 and (run / "family_baseline.json").is_file())
    rc = ob.main(["verify", "--run", str(run), "--gpu-uuid", UUID])
    v = verdict(run)
    # another session's CPU tests may start processes that carry the same tool names while this test runs (sol did): the
    # observer reports them as os_residual for a human to read, so the clean case is judged on everything except those
    check("clean attempt: no lock, receipt or GPU reason, both locks acquirable",
          not [r for r in v["reasons"] if not r.startswith("os_residual")] and
          v["first"]["locks"]["gpu_lease"] == "acquired_and_released" and v["first"]["locks"]["usd_lock"] == "acquired_and_released")
    check("clean attempt is PASS, or HOLD with a named reason, never a silent PASS",
          v["verdict"] == "PASS" or bool(v["reasons"] or v["unknown"]))
    check("a second observation for the same attempt is refused", ob.main(["verify", "--run", str(run), "--gpu-uuid", UUID]) == 2)
    check("observation records its receipts with hashes", "summary.json" in v["receipts"] and len(v["receipts"]["summary.json"]["sha256"]) == 64)

    run2 = fresh_run()
    ob.main(["record", "--run", str(run2), "--gpu-uuid", UUID])
    left = subprocess.Popen([sys.executable, "-c", "import time,sys; time.sleep(60)", str(run2)])
    time.sleep(1.0)
    ob.main(["verify", "--run", str(run2), "--gpu-uuid", UUID])
    v2 = verdict(run2)
    left.kill(); left.wait()
    check("a leftover process with the run directory in its argv -> HOLD os_residual", v2["verdict"] == "HOLD" and
          any(r.startswith("os_residual") for r in v2["reasons"]))

    run3 = fresh_run()
    ob.main(["record", "--run", str(run3), "--gpu-uuid", UUID])
    sys.path.insert(0, str(ob.BUNDLE))
    from s2_resource_lease import gpu_lease
    held = gpu_lease(run3 / "ctl" / "lease", UUID).acquire()
    try:
        ob.main(["verify", "--run", str(run3), "--gpu-uuid", UUID])
    finally:
        held.release(family_empty=True)
    v3 = verdict(run3)
    check("a held GPU lease -> HOLD lock_gpu_lease", v3["verdict"] == "HOLD" and any("lock_gpu_lease" in r for r in v3["reasons"]))

    run4 = fresh_run()
    ob.main(["record", "--run", str(run4), "--gpu-uuid", UUID])
    (run4 / "out" / "completion.json").write_text(json.dumps({"family_active_count": 2}), encoding="utf-8")
    ob.main(["verify", "--run", str(run4), "--gpu-uuid", UUID])
    check("a receipt that reports a non-empty family -> HOLD", any(r.startswith("receipt_family_not_zero") for r in verdict(run4)["reasons"]))

    run5 = fresh_run()
    ob.main(["record", "--run", str(run5), "--gpu-uuid", UUID])
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    time.sleep(0.5)
    import psutil
    ct = psutil.Process(proc.pid).create_time()
    ob.main(["verify", "--run", str(run5), "--gpu-uuid", UUID, "--known-pids", "%d:%f" % (proc.pid, ct)])
    v5 = verdict(run5)
    proc.kill(); proc.wait()
    check("an attempt pid still alive with the same creation time -> HOLD, even if its command line looks unrelated",
          v5["verdict"] == "HOLD" and any(r.startswith("known_attempt_process_still_alive") for r in v5["reasons"]))
    run6 = fresh_run()
    ob.main(["record", "--run", str(run6), "--gpu-uuid", UUID])
    ob.main(["verify", "--run", str(run6), "--gpu-uuid", UUID, "--known-pids", "%d:%f" % (proc.pid, ct + 100.0)])
    check("the same pid with another creation time (pid reuse) is not taken for the attempt's process",
          not any(r.startswith("known_attempt_process_still_alive") for r in verdict(run6)["reasons"]))
    print("SUMMARY", "ALL PASS" if not FAILS else "FAIL %s" % FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
