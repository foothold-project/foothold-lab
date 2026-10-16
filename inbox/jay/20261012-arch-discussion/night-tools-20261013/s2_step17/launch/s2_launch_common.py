"""CPU sealing and attended, single-use supervisor orchestration for S2 nodes 3/4.

Import has no GPU or Isaac side effects. The real prelaunch probes resources but
never starts a supervisor. Only an explicit live command may start one.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time


PY = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
BUNDLE = Path(__file__).resolve().parent.parent / "bundle"
ROOT = BUNDLE.parent
GPU_UUID = "GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"
GPU_BUS = "41:00.0"
USD_LOCK = Path("C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock")
ASSET = Path("C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf")
HOOK = Path("C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/ray_caster.py")
STEP16_LIST_SHA256 = "b3fb34d066a6f916d5a4aec93d2dd6b844b3a7ea55f637a8cf5f12f5f2ef6312"


class LaunchHold(RuntimeError):
    pass


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_json(path, value):
    Path(path).write_bytes(canonical(value) + b"\n")


def consent_from(path, scope):
    if path is None or not Path(path).is_file():
        raise LaunchHold("consent_file_missing")
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if (value.get("scope") != scope or
        any(not isinstance(value.get(k), str) or not value[k].strip()
            for k in ("by", "quote")) or
        any(value.get(k) != "yes" for k in
            ("eula_accepted", "attending_until_end", "go_for_this_one_run"))):
        raise LaunchHold("consent_scope_or_direct_words")
    return value


def approval_for(manifest, consent, attendee=None):
    # For rehearsal this remains in memory. A live approval is written only
    # after the operator has supplied the direct consent file.
    return {"status": "APPROVED", "scope": manifest["scope"],
            "by": consent["by"] if consent else "rehearsal_only",
            "quote": consent["quote"] if consent else "rehearsal_only",
            "attendee": attendee if consent else None,
            "direct_consent": consent,
            "manifest_sha256": hashlib.sha256(canonical(manifest)).hexdigest(),
            "expires_epoch": manifest["deadline_epoch"]}


def check_bundle():
    listing = BUNDLE / "S2-STEP16-SHA256SUMS.txt"
    if not listing.is_file():
        raise LaunchHold("step16_hash_list_missing")
    if sha(listing) != STEP16_LIST_SHA256:
        raise LaunchHold("step16_hash_list_changed")
    rows = [line for line in listing.read_text(encoding="utf-8").splitlines() if line.strip()]
    checked = 0
    for line in rows:
        digest, rel = line.split(None, 1)
        rel = rel.strip().lstrip("*")
        parts = PurePosixPath(rel.replace("\\", "/")).parts
        if "__pycache__" in parts or rel.lower().endswith(".pyc"):
            continue  # The pinned list is intact, but bytecode is not code closure.
        here = BUNDLE / rel
        if not here.is_file() or sha(here) != digest:
            raise LaunchHold("step16_bundle_changed:" + rel)
        checked += 1
    return checked


def new_run(node, clock=time.time):
    import uuid
    name = f"{node}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run = ROOT / "runs" / name
    for sub in ("in", "ctl", "logs"):
        (run / sub).mkdir(parents=True, exist_ok=False)
    return run, name


def base_manifest(run, chain, scope, driver_name, *, max_wall_s, resources, clock=time.time):
    if (type(max_wall_s) is not int or not 0 < max_wall_s <= 900 or
        any(type(resources[k]) is not int or resources[k] <= 0 for k in
            ("min_free_vram_bytes", "running_floor_vram_bytes", "min_free_disk_bytes", "max_disk_bytes"))):
        raise LaunchHold("resource_decision_missing")
    deadline = clock() + max_wall_s
    m = {"scope": scope, "chain_id": chain, "attempt": "first",
         "claim_root": str(run / "ctl" / "claims"),
         "status_path": str(run / "ctl" / "status.json"),
         "stop_path": str(run / "ctl" / "STOP"),
         "observer_registration_path": str(run / "ctl" / "watchdog_registration.json"),
         "observer_log_path": str(run / "ctl" / "watchdog.jsonl"),
         "lease_root": str(run / "ctl" / "lease"),
         "usd_lock_path": str(USD_LOCK), "usd_root": str(run / "usd"),
         "log_path": str(run / "logs" / "child.log"),
         "python_path": str(PY), "python_sha256": sha(PY),
         "isolate_path": str(BUNDLE / "usd_isolate_run_v3.py"),
         "isolate_sha256": sha(BUNDLE / "usd_isolate_run_v3.py"),
         "driver_path": str(BUNDLE / driver_name),
         "driver_sha256": sha(BUNDLE / driver_name),
         "gpu_uuid": GPU_UUID, "gpu_index": 0, "gpu_bus_id": GPU_BUS,
         "deadline_epoch": deadline, "max_wall_s": max_wall_s,
         "max_launches": 1, "retry_count": 0,
         "observer_mode": "attended", **resources}
    return m


def prelaunch(m, approval, validator, *, probe=None, lease_factory=None, lock_factory=None,
              disk_probe=None, clock=time.time, fixture=False):
    """Validate, sample real identity/resources and briefly test both locks."""
    validator(m, approval, now=clock(), fixture=fixture)
    if probe is None:
        from s2_step4a34.s2_stage0_resources_a2 import NvmlMeter
        meter = NvmlMeter()
        try:
            sample = meter.probe(0)
        finally:
            meter.close()
    else:
        sample = probe()
    from s2_step4a34.s2_stage0_resources_a2 import preflight, disk_free
    preflight(sample, (disk_probe or disk_free)(Path(m["log_path"]).parent), m)
    if lease_factory is None or lock_factory is None:
        from s2_resource_lease import gpu_lease, usd_conversion_lock
        lease_factory = lease_factory or gpu_lease
        lock_factory = lock_factory or usd_conversion_lock
    lease = lease_factory(Path(m["lease_root"]), m["gpu_uuid"]).acquire()
    try:
        lock = lock_factory(Path(m["usd_lock_path"])).acquire()
        try:
            pass
        finally:
            lock.release(family_empty=True)
    finally:
        lease.release(family_empty=True)
    return {"status": "GO", "checked_epoch": clock(), "gpu": sample,
            "manifest_sha256": hashlib.sha256(canonical(m)).hexdigest(),
            "lease_released": True, "usd_lock_released": True}


def go_fresh(report, *, clock=time.time):
    if report.get("status") != "GO" or type(report.get("checked_epoch")) not in (float, int):
        raise LaunchHold("prelaunch_not_go")
    age = clock() - report["checked_epoch"]
    if age < 0 or age > 45:
        raise LaunchHold("prelaunch_go_older_than_45s")
    return age


def single_launch_guard(prior_launches):
    if prior_launches != 0:
        raise LaunchHold("automatic_retry_forbidden")


def observer_call(run, mode, *, known="", call=subprocess.run):
    args = [str(PY), "-B", str(Path(__file__).parent / "s2_family_observer.py"),
            mode, "--run", str(run), "--gpu-uuid", GPU_UUID]
    if known:
        args += ["--known-pids", known]
    proc = call(args, cwd=str(BUNDLE), capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise LaunchHold("family_observer_" + mode + "_failed:" + (proc.stdout or proc.stderr)[-200:])
    if mode == "verify":
        row = json.loads((run / "family_observation.json").read_text(encoding="utf-8"))
        if row.get("verdict") != "PASS":
            raise LaunchHold("family_observer_not_pass")
    return proc


def live_once(run, m, approval, supervisor_name, prelaunch_report, *,
              observer=observer_call, popen=subprocess.Popen, clock=time.time,
              sleep=time.sleep):
    go_fresh(prelaunch_report, clock=clock)
    single_launch_guard(0)
    import psutil
    supervisor = popen([str(PY), "-B", str(BUNDLE / supervisor_name),
                        "--manifest", str(run / "in" / "manifest.json"),
                        "--approval", str(run / "in" / "approval.json")],
                       cwd=str(BUNDLE), env={**os.environ, "OMNI_KIT_ACCEPT_EULA": "YES",
                                             "PYTHONUNBUFFERED": "1"})
    sup_ct = psutil.Process(supervisor.pid).create_time()
    watchdog = None
    operational_hold = None
    known = {supervisor.pid: sup_ct}
    try:
        watchdog = popen([str(PY), "-B", str(BUNDLE / "s2_step4a34" / "s2_hard_watchdog.py"),
                          "--pid", str(supervisor.pid), "--create-time", str(sup_ct),
                          "--status-path", m["status_path"],
                          "--hard-deadline-epoch", str(m["deadline_epoch"]),
                          "--stale-after-s", "20", "--startup-grace-s", "20",
                          "--poll-s", "1", "--log", m["observer_log_path"]],
                         cwd=str(BUNDLE), env={**os.environ, "PYTHONUNBUFFERED": "1"})
        watch_ct = psutil.Process(watchdog.pid).create_time()
        write_json(m["observer_registration_path"], {
            "manifest_sha256": hashlib.sha256(canonical(m)).hexdigest(),
            "status": "ARMED", "status_path": m["status_path"],
            "log_path": m["observer_log_path"],
            "hard_deadline_epoch": m["deadline_epoch"],
            "pid": watchdog.pid, "create_time": watch_ct,
            "supervisor_create_time": sup_ct})
        last = clock()
        while supervisor.poll() is None:
            if watchdog.poll() is not None:
                Path(m["stop_path"]).write_text("watchdog lost\n", encoding="utf-8")
                operational_hold = "watchdog_lost"
                break
            if clock() - last >= 10:
                try:
                    st = json.loads(Path(m["status_path"]).read_text(encoding="utf-8"))
                    if type(st.get("child_pid")) is int:
                        known.setdefault(st["child_pid"], psutil.Process(st["child_pid"]).create_time())
                    if type(st.get("pid")) is int:
                        known.setdefault(st["pid"], psutil.Process(st["pid"]).create_time())
                except (OSError, ValueError, psutil.Error):
                    st = {}
                print("state=%s remaining_s=%s" % (st.get("state"), st.get("remaining_s")), flush=True)
                last = clock()
            sleep(1)
    except KeyboardInterrupt:
        Path(m["stop_path"]).write_text("attendee STOP\n", encoding="utf-8")
        print("STOP written. Waiting for owned family cleanup.", flush=True)
    finally:
        try:
            supervisor.wait(timeout=90)
        except subprocess.TimeoutExpired:
            raise LaunchHold("supervisor_cleanup_unverified")
    if watchdog is None:
        raise LaunchHold("watchdog_not_started")
    try:
        watchdog.wait(timeout=20)
    except subprocess.TimeoutExpired:
        raise LaunchHold("watchdog_cleanup_unverified")
    try:
        st = json.loads(Path(m["status_path"]).read_text(encoding="utf-8"))
        for key in ("child_pid", "pid"):
            if type(st.get(key)) is int and st[key] not in known:
                try:
                    known[st[key]] = psutil.Process(st[key]).create_time()
                except psutil.Error:
                    pass
    except (OSError, ValueError):
        pass
    try:
        observer(run, "verify", known=",".join(f"{pid}:{ct:.6f}" for pid, ct in known.items()))
    except LaunchHold as ex:
        operational_hold = str(ex)
    return {"supervisor_rc": supervisor.returncode,
            "watchdog_rc": watchdog.returncode,
            "known_pid_count": len(known),
            "family_observation": "PASS" if operational_hold is None else "HOLD",
            "operational_hold": operational_hold}
