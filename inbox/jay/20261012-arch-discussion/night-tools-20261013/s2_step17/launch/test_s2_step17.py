"""CPU-only known-answer and mutation gates for the node 3/4 launchers."""
from __future__ import annotations

import argparse
import ast
import inspect
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUNDLE = ROOT / "bundle"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BUNDLE))

import s2_launch_common as C
import s2_attended_launch_eval0 as E
import s2_attended_launch_foot as F

NORMAL = []
CAUGHT = []


def ok(label, value):
    if not value:
        raise AssertionError(label)
    NORMAL.append(label)
    print("PASS", label, flush=True)


def caught(label, want, call):
    try:
        call()
    except Exception as ex:
        if want not in str(ex):
            raise AssertionError(f"{label}: wrong first failure {ex!r}") from ex
        CAUGHT.append(label)
        print("CAUGHT", label, "first=" + want, flush=True)
        return
    raise AssertionError(label + ": mutation escaped")


class Lease:
    def acquire(self):
        return self
    def release(self, **kwargs):
        assert kwargs == {"family_empty": True}


def run_dir(root, name):
    run = root / name
    (run / "in").mkdir(parents=True)
    (run / "ctl").mkdir()
    return run


def resources():
    return {"min_free_vram_bytes": 1024, "running_floor_vram_bytes": 512,
            "min_free_disk_bytes": 1024, "max_disk_bytes": 10**9}


def fake_prelaunch(m, approval, validate):
    sample = {"uuid": C.GPU_UUID, "bus": C.GPU_BUS, "index": 0,
              "free_vram_bytes": 1024 * 1024}
    return C.prelaunch(m, approval, validate, probe=lambda: sample,
        disk_probe=lambda _: 10**9, lease_factory=lambda *x: Lease(),
        lock_factory=lambda *x: Lease())


def test_contracts(root):
    ok("step16 copied source/data hash closure", C.check_bundle() == 1572)
    run = run_dir(root, "foot")
    m = F.build(run, "foot-cpu", resources(), 120, seed=7, steps_per_scene=37)
    approval = C.approval_for(m, None)
    from s2_foot_kit_scope import validate as validate_foot
    ok("foot analytic 8 scenes and 296 control steps", len(json.loads(Path(m["request_path"]).read_text())["scenes"]) == 8
       and 8 * 37 == 296 and m["max_envs"] == 2 and m["optimizer_steps"] == 0)
    ok("foot full static scope", validate_foot(m, approval, now=time.time())["steps_per_scene"] == 37)
    report = fake_prelaunch(m, approval, validate_foot)
    ok("foot fake prelaunch GO without supervisor", report["status"] == "GO" and
       not Path(m["claim_root"]).exists() and not Path(m["status_path"]).exists())
    caught("foot steps above total cap", "foot_seed_or_step_scope",
           lambda: F.build(run_dir(root, "badsteps"), "foot-bad", resources(), 120,
                           seed=7, steps_per_scene=38))
    run = run_dir(root, "eval")
    m = E.build(run, "eval-cpu", resources(), 120)
    approval = C.approval_for(m, None)
    from s2_eval_scope import validate as validate_eval
    ok("eval full static scope", validate_eval(m, approval, now=time.time())["job"]["update"] == 0)
    report = fake_prelaunch(m, approval, validate_eval)
    ok("eval fake prelaunch GO without supervisor", report["status"] == "GO" and
       not Path(m["claim_root"]).exists() and not Path(m["status_path"]).exists())
    job = json.loads(Path(m["job_path"]).read_text())
    cases = json.loads(Path(m["cases_path"]).read_text())
    receipt = json.loads((run / "in" / "checkpoint_receipt.json").read_text())
    ok("fresh pair update zero and full freeze", all(receipt[arm]["control"]["completed_updates"] == 0
       and receipt[arm]["control"]["optimizer_slot_count"] == 0
       and job["arms"][arm]["encoder_mode"] == "full_freeze" for arm in ("A", "B")))
    ok("seed four disjoint", len(cases["cases"]) == 4 and
       not set(E.EVAL_SEEDS) & set(cases["learning_seeds"]))
    return m


def test_real_cpu_prelaunch(root):
    """Use the real disk meter and both real byte locks, with GPU sample injected."""
    from s2_step4a34.s2_stage0_resources_a2 import disk_free
    from s2_resource_lease import gpu_lease, usd_conversion_lock
    from s2_foot_kit_scope import validate as validate_foot
    from s2_eval_scope import validate as validate_eval

    legacy = root / "legacy-without-logs"
    (legacy / "in").mkdir(parents=True)
    (legacy / "ctl").mkdir()
    caught("legacy run disk probe", "disk_probe_failed",
           lambda: disk_free(legacy / "logs"))

    lock_before = C.sha(C.USD_LOCK)
    sample = {"uuid": C.GPU_UUID, "bus": C.GPU_BUS, "index": 0,
              "free_vram_bytes": 1024 * 1024}
    with patch.object(C, "ROOT", root):
        for node, build, validate in (
            ("foot", lambda run, chain: F.build(run, chain, resources(), 120,
                                                seed=7, steps_per_scene=2), validate_foot),
            ("eval0", lambda run, chain: E.build(run, chain, resources(), 120), validate_eval),
        ):
            run, chain = C.new_run(node)
            ok(node + " new_run creates disk target only", (run / "in").is_dir()
               and (run / "ctl").is_dir() and (run / "logs").is_dir()
               and not (run / "out").exists() and not (run / "ctl" / "claims").exists())
            free = disk_free(run / "logs")
            ok(node + " real disk_free on new run", type(free) is int and free >= 1024)
            m = build(run, chain)
            approval = C.approval_for(m, None)
            report = C.prelaunch(m, approval, validate, probe=lambda: sample)
            ok(node + " real CPU prelaunch GO", report["status"] == "GO"
               and report["lease_released"] and report["usd_lock_released"]
               and report["gpu"] == sample)
            ok(node + " no output or claim created", not Path(m["claim_root"]).exists()
               and not Path(m["result_path" if node == "foot" else "episodes_path"]).parent.exists()
               and not Path(m["log_path"]).exists())
            gpu_lease(Path(m["lease_root"]), m["gpu_uuid"]).acquire().release(family_empty=True)
            usd_conversion_lock(Path(m["usd_lock_path"])).acquire().release(family_empty=True)
            ok(node + " both real locks reacquire after prelaunch", True)
        def args():
            return SimpleNamespace(live=False, rehearse=True, attendee="", confirm="",
                consent_file=None, max_wall_s=120, seed=7, steps_per_scene=2,
                **resources())
        for node, mod in (("foot", F), ("eval0", E)):
            def gpu_only_injected(m, approval, validator):
                return C.prelaunch(m, approval, validator, probe=lambda: sample)
            with patch("s2_step4a34.s2_stage0_resources_a2.NvmlMeter",
                       side_effect=AssertionError("GPU probe in CPU rehearsal")):
                rc = mod.execute(args(), prelaunch_fn=gpu_only_injected,
                    live_fn=lambda *a, **k: (_ for _ in ()).throw(AssertionError("supervisor started")),
                    observer=lambda *a, **k: (_ for _ in ()).throw(AssertionError("observer started")))
            candidates = sorted((root / "runs").glob(
                ("foot" if node == "foot" else "eval0") + "-rehearse-*"))
            run = candidates[-1]
            summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
            ok(node + " real CPU wrapper rehearsal GO", rc == 0
               and summary["prelaunch"]["status"] == "GO"
               and summary["supervisor_started"] is False
               and not (run / "out").exists() and not (run / "ctl" / "claims").exists())
    ok("existing USD lock bytes unchanged", C.sha(C.USD_LOCK) == lock_before)


def test_guards(root, eval_manifest):
    scope = E.SCOPE
    direct = {"scope": scope, "by": "lead", "quote": "direct yes",
              "eula_accepted": "yes", "attending_until_end": "yes",
              "go_for_this_one_run": "yes"}
    path = root / "consent.json"
    C.write_json(path, direct)
    ok("direct consent accepted", C.consent_from(path, scope) == direct)
    wrong = dict(direct, scope=F.SCOPE)
    C.write_json(path, wrong)
    caught("consent scope mismatch", "consent_scope_or_direct_words", lambda: C.consent_from(path, scope))
    caught("missing consent", "consent_file_missing", lambda: C.consent_from(None, scope))
    caught("stale GO", "prelaunch_go_older_than_45s",
           lambda: C.go_fresh({"status": "GO", "checked_epoch": 100.}, clock=lambda: 146.))
    spawned = []
    caught("stale GO blocks live supervisor", "prelaunch_go_older_than_45s",
           lambda: C.live_once(root, eval_manifest, {}, "s2_eval_supervisor.py",
               {"status": "GO", "checked_epoch": 100.}, clock=lambda: 146.,
               popen=lambda *a, **k: spawned.append(a)))
    ok("stale GO starts no process", spawned == [])
    ok("fresh GO", C.go_fresh({"status": "GO", "checked_epoch": 100.}, clock=lambda: 145.) == 45.)
    code = ast.parse(inspect.getsource(C.live_once))
    launches = [n for n in ast.walk(code) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "supervisor" for t in n.targets)
                and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "popen"]
    ok("single supervisor launch site, no retry loop", len(launches) == 1 and
       not any(isinstance(n, (ast.For, ast.While)) and launches[0] in ast.walk(n)
               for n in ast.walk(code)))
    caught("observer baseline failure", "family_observer_record_failed",
           lambda: C.observer_call(root, "record", call=lambda *a, **k: SimpleNamespace(returncode=3, stdout="baseline failed", stderr="")))
    caught("observer post failure", "family_observer_verify_failed",
           lambda: C.observer_call(root, "verify", call=lambda *a, **k: SimpleNamespace(returncode=3, stdout="residual", stderr="")))
    caught("attempt output reuse", "output_exists:episodes_path",
           lambda: (Path(eval_manifest["episodes_path"]).parent.mkdir(parents=True, exist_ok=True),
                    Path(eval_manifest["episodes_path"]).write_text("old"),
                    __import__("s2_eval_scope").validate(eval_manifest,
                        C.approval_for(eval_manifest, None), now=time.time())))


def test_wrapper_modes(root):
    def args(mode, *, live=False, consent=None):
        return SimpleNamespace(live=live, rehearse=not live,
            attendee="lead" if live else "", confirm="LAUNCH-ATTENDED" if live else "",
            consent_file=consent, max_wall_s=120, seed=7, steps_per_scene=20, **resources())
    for mod, name in ((F, "foot-wrapper"), (E, "eval-wrapper")):
        run = run_dir(root, name)
        launched = []
        with patch.object(mod, "new_run", return_value=(run, name)), \
             patch.object(mod, "check_bundle", return_value=1572):
            rc = mod.execute(args(name), prelaunch_fn=fake_prelaunch,
                live_fn=lambda *a, **k: launched.append(True),
                observer=lambda *a, **k: (_ for _ in ()).throw(AssertionError("rehearsal_observer")))
        summary = json.loads((run / "summary.json").read_text())
        ok(name + " rehearse never starts supervisor", rc == 0 and not launched
           and summary["supervisor_started"] is False and
           not (run / "in" / "approval.json").exists())
    caught("live without consent before build", "consent_file_missing",
           lambda: F.execute(args("foot", live=True)))
    path = root / "scope-bad.json"
    C.write_json(path, {"scope": E.SCOPE, "by": "lead", "quote": "go",
        "eula_accepted": "yes", "attending_until_end": "yes",
        "go_for_this_one_run": "yes"})
    caught("live wrong scope before build", "consent_scope_or_direct_words",
           lambda: F.execute(args("foot", live=True, consent=path)))
    C.write_json(path, {"scope": F.SCOPE, "by": "lead", "quote": "go",
        "eula_accepted": "yes", "attending_until_end": "yes",
        "go_for_this_one_run": "yes"})
    run = run_dir(root, "observer-fail")
    started = []
    with patch.object(F, "new_run", return_value=(run, "observer-fail")), \
         patch.object(F, "check_bundle", return_value=1572):
        caught("live observer baseline blocks supervisor", "baseline_failed",
            lambda: F.execute(args("foot", live=True, consent=path),
                prelaunch_fn=lambda *a: started.append("prelaunch"),
                observer=lambda *a: (_ for _ in ()).throw(C.LaunchHold("baseline_failed")),
                live_fn=lambda *a, **k: started.append("supervisor")))
    ok("baseline failed before prelaunch or supervisor", started == [])


def test_fake_supervisor(root):
    run = run_dir(root, "fake-supervisor")
    m = F.build(run, "foot-fake", resources(), 120, seed=7, steps_per_scene=2)
    approval = C.approval_for(m, {"by": "lead", "quote": "direct go"})
    C.write_json(run / "in" / "approval.json", approval)
    class Proc:
        def __init__(self, pid):
            self.pid = pid
            self.returncode = None
            self.polls = 0
        def poll(self):
            self.polls += 1
            if self.pid == 101 and self.polls > 1:
                self.returncode = 0
                return 0
            return None
        def wait(self, timeout):
            self.returncode = 0
            return 0
    calls = []
    procs = [Proc(101), Proc(102)]
    def popen(argv, **kwargs):
        calls.append(argv)
        return procs[len(calls)-1]
    observer = []
    with patch("psutil.Process", side_effect=lambda pid: SimpleNamespace(create_time=lambda: float(pid))):
        result = C.live_once(run, m, approval, "s2_foot_kit_supervisor.py",
            {"status": "GO", "checked_epoch": time.time()},
            popen=popen, sleep=lambda _: None,
            observer=lambda *a, **k: observer.append((a, k)))
    registration = json.loads(Path(m["observer_registration_path"]).read_text())
    ok("fake supervisor and watchdog each start once", len(calls) == 2 and
       "s2_foot_kit_supervisor.py" in calls[0][2] and
       "s2_hard_watchdog.py" in calls[1][2] and
       result["supervisor_rc"] == 0 and result["watchdog_rc"] == 0)
    ok("watchdog registration binds distinct PID and manifest", registration["pid"] == 102 and
       registration["supervisor_create_time"] == 101. and
       registration["manifest_sha256"] == C.approval_for(m, None)["manifest_sha256"])
    ok("independent post observer called", len(observer) == 1 and observer[0][0][1] == "verify")


def main():
    with tempfile.TemporaryDirectory(dir=ROOT, prefix="step17-cpu-") as td:
        root = Path(td)
        manifest = test_contracts(root)
        test_real_cpu_prelaunch(root)
        test_guards(root, manifest)
        test_wrapper_modes(root)
        test_fake_supervisor(root)
    print(json.dumps({"normal": len(NORMAL), "caught": len(CAUGHT),
                      "normal_labels": NORMAL, "caught_labels": CAUGHT}, sort_keys=True))


if __name__ == "__main__":
    main()
