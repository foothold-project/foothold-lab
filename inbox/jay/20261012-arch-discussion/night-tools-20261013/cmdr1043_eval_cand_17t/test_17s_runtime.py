"""CPU-only approval, retry and owned child-tree probes for 17s."""
import copy
import importlib.util
import json
import msvcrt
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from s1043_manifest import approval_binding, launch_errors, sha256
from test_17r_b import make

if os.environ.get("S1043_MANIFEST_OVERRIDE"):
    spec = importlib.util.spec_from_file_location("s1043_manifest_mutant", os.environ["S1043_MANIFEST_OVERRIDE"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__file__ = str(HERE / "s1043_manifest.py")
    module.ROOT = ROOT
    launch_errors = module.launch_errors


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def driver_globals():
    driver = Path(os.environ.get("S1043_DRIVER_OVERRIDE", HERE / "cmdr_eval_driver_s1043.py"))
    old = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(HERE / "manifest_s1043.json"),
                    "--expect_self_sha", sha256(driver), "--cpu_plan"]
        return runpy.run_path(str(driver), run_name="runtime_cpu_probe")["guarded"].__globals__
    finally:
        sys.argv = old


def refresh_approval(m):
    e = m["execution"]
    path = Path(e["approval_path"])
    path.write_text(json.dumps({"approved": True, "by": "CPU_FIXTURE_ONLY", "approved_at": "fixture",
                                "reviewed": approval_binding(m)}, sort_keys=True), encoding="utf-8")
    e["approval_sha256"] = sha256(path)
    return e["approval_sha256"]


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    m, digest = make(0)
    check("normal approval binding", launch_errors(m, approved_digest=digest, require_files=False) == [])
    altered = copy.deepcopy(m)
    altered["execution"]["attempt"] = "another-attempt"
    check("attempt-only mutation rejected", "approval contract mismatch" in
          launch_errors(altered, approved_digest=digest, require_files=False))
    altered = copy.deepcopy(m)
    altered["execution"]["risk_limit"]["max_retries_per_run"] = 0
    zero_digest = refresh_approval(altered)
    check("retry zero approved", launch_errors(altered, approved_digest=zero_digest, require_files=False) == [])
    for bad in (-1, "0", False):
        trial = copy.deepcopy(altered)
        trial["execution"]["risk_limit"]["max_retries_per_run"] = bad
        check(f"retry {bad!r} rejected", "execution risk_limit invalid" in
              launch_errors(trial, approved_digest=zero_digest, require_files=False))

    g = driver_globals()
    fixture = ROOT / "fixture_17s_runtime" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    fixture.mkdir(parents=True, exist_ok=False)
    c = copy.deepcopy(m["contract"])
    c["deployment"]["write_root"] = str(fixture)
    c["paths"].update(data=str(fixture / "data"), work=str(fixture / "work"),
                      registry=str(fixture / "registry/slot.json"), stop=str(fixture / "STOP"),
                      run_lease=str(fixture / "lease.lock"))
    g["CONTRACT"] = c
    g["OUT"] = c["paths"]["data"]
    Path(g["OUT"]).mkdir(parents=True)
    g["MANIFEST"] = copy.deepcopy(altered)
    g["MANIFEST"]["contract"] = c
    g["ATTEMPT"] = "cpu-17s-runtime"
    g["ATTEMPT_START"] = time.time()
    g["LOGF"] = str(fixture / "data/runtime.json")
    g["args"].log = "runtime"
    g["gate"] = lambda *a, **kw: None
    g["gpu_preflight"] = lambda: {"gpu_index": "0", "free_mib": 8192}
    g["usd_dirs_of"] = lambda name: []
    g["root_ref_failed"] = lambda name: False
    g["py_traceback"] = lambda name: False
    def lease(*a, **kw):
        f = open(c["paths"]["run_lease"], "a+b")
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        return f
    g["run_lease"] = lease
    g["TREE_ABORT"][0] = None
    calls = []
    child_code = ["import time; time.sleep(0.15)"]
    def popen(*a, **kw):
        calls.append(time.monotonic())
        return subprocess.Popen([sys.executable, "-B", "-c", child_code[0]],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g["POPEN"] = popen
    g["MANIFEST"]["execution"]["risk_limit"].update(max_retries_per_run=0, max_child_launches=10, max_wall_s=5)
    # A guard-style rc 99 would normally request another try. Zero retry
    # must still cap the actual launch loop at one.
    real_watcher = g["wait_child_tree"]
    g["wait_child_tree"] = lambda p, **kw: (p.wait(), 99)[1]
    rc, tries = g["guarded"]("retry_zero", [sys.executable], wait_s=0, ck="p20000")
    check("retry zero makes exactly one launch", rc == 99 and tries == 1 and len(calls) == 1)
    g["wait_child_tree"] = real_watcher
    child_code[0] = "import time; time.sleep(4)"
    g["ATTEMPT_START"] = time.time()
    g["MANIFEST"]["execution"]["risk_limit"]["max_wall_s"] = 2
    rc, tries = g["guarded"]("wall_guarded", [sys.executable], wait_s=0, ck="p20000")
    check("guarded wall returns nonzero held result", rc == 124 and tries == 1 and
          g["TRIES"]["wall_guarded"][0]["abort_reason"] == "wall_limit" and
          g["TRIES"]["wall_guarded"][0]["partial_result"] == "held")

    # The reservation is under a fixture write_root. A second start cannot
    # reuse even an approval whose first process already exited.
    e = g["MANIFEST"]["execution"]
    e.update(approval_id="17s-one", attempt="17s-one-attempt", log_name="runtime",
             approval_sha256="1" * 64, restart_scope="single_start_no_reuse")
    g["ATTEMPT"] = e["attempt"]
    first = g["claim_approval"]()
    claim = json.loads(first.read_text(encoding="utf-8"))
    check("claim binds id digest attempt log", all(claim[k] == v for k, v in
          {"approval_id": e["approval_id"], "approval_sha256": e["approval_sha256"],
           "attempt": e["attempt"], "log_name": "runtime"}.items()))
    try:
        g["claim_approval"]()
    except RuntimeError as ex:
        check("second start refused", str(ex) == "approval already used")
    else:
        check("second start refused", False)
    e["attempt"] = "mutated-attempt"
    g["ATTEMPT"] = e["attempt"]
    try:
        g["claim_approval"]()
    except RuntimeError as ex:
        check("attempt-only reuse refused", str(ex) == "approval already used")
    else:
        check("attempt-only reuse refused", False)
    e["approval_id"] = "17s-race"
    barrier = threading.Barrier(2)
    outcomes = []
    def contender():
        barrier.wait()
        try:
            g["claim_approval"]()
            outcomes.append("claimed")
        except RuntimeError as ex:
            outcomes.append(str(ex))
    threads = [threading.Thread(target=contender) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    check("concurrent start one claim", sorted(outcomes) == ["approval already used", "claimed"])

    # Return to the real tree watcher; all processes here are launched by
    # this test. No legacy process is signalled.
    watcher = g["wait_child_tree"]
    def owned_run(label, code, limit, stop_after=None):
        stop_file = fixture / "STOP"
        if stop_file.exists():
            stop_file.unlink()
        child = subprocess.Popen([sys.executable, "-B", "-c", code],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        timer = None
        if stop_after is not None:
            timer = threading.Timer(stop_after, lambda: stop_file.write_text("stop", encoding="utf-8"))
            timer.start()
        lease_file = lease()
        begun = time.monotonic()
        try:
            result = watcher(child, wall_deadline=time.time() + limit,
                             stop_check=stop_file.exists, terminate_grace_s=0.2)
            elapsed = time.monotonic() - begun
            probe = open(c["paths"]["run_lease"], "a+b")
            try:
                probe.seek(0)
                try:
                    msvcrt.locking(probe.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    still_held = True
                else:
                    still_held = False
                    msvcrt.locking(probe.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                probe.close()
            check(label + " lease held through tree exit", still_held)
        finally:
            g["release_run_lease"](lease_file)
            if timer:
                timer.join()
        check(label + " lease released", not os.path.exists(stop_file) or child.poll() is not None)
        return result, elapsed
    rc, elapsed = owned_run("normal", "import time; time.sleep(.25)", 2)
    check("normal child unaffected", rc == 0 and elapsed < 2)
    rc, elapsed = owned_run("wall", "import time; time.sleep(4)", 2)
    check("wall kills owned child near limit", rc == 124 and 1.7 <= elapsed < 3.5)
    grandchild = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(4)']); time.sleep(4)"
    rc, elapsed = owned_run("grandchild", grandchild, 2)
    check("wall kills observed grandchild", rc == 124 and 1.7 <= elapsed < 3.5)
    rc, elapsed = owned_run("stop", "import time; time.sleep(4)", 5, stop_after=.4)
    check("STOP kills owned child", rc == 125 and elapsed < 2)


if __name__ == "__main__":
    main()
