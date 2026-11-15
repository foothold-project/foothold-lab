"""Bounded one-shot Job Object owner for S2-2 Kit foot evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from s2_eval_cpu import sha
from s2_eval_supervisor import atomic_json, observer_armed
from s2_foot_kit_scope import validate, required_argv, canonical
from s2_job_owner import JobOwner, WinKernel, OwnershipHold
from s2_resource_lease import gpu_lease, usd_conversion_lock, LeaseHold
from s2_step4a34.s2_stage0_resources_a2 import (NvmlMeter, disk_free, tree_bytes,
                                                 preflight, running, ResourceHold)


class FootSupervisorHold(RuntimeError):
    pass


def _oracle(row):
    z = row["analytic_rays"]["expected_hit_z_m"]
    boundary = row["analytic_rays"]["boundary_mask"]
    if any(any(any(foot) for foot in env) for env in boundary):
        # Boundary samples are recorded, and cannot silently count as a pass.
        return None
    costs = []
    for env_idx, feet in enumerate(z):
        total = 0
        for foot_idx, heights in enumerate(feet):
            center_z = row["foot_centers_w_m"][env_idx][foot_idx][2]
            force_z = row["contact_forces_w_n"][env_idx][foot_idx][2]
            danger = [h < center_z-.022-.20 for h in heights]
            if force_z > 1.0:
                total += 3 if danger[4] else (int(any(danger[i] for i in (1,3,5,7))) +
                                              2*int(any(danger[i] for i in (0,2,6,8))))
        costs.append(total)
    return costs


def verdict(result, *, rc, family_empty, reason, observer_log=None):
    errors = []
    if rc != 0 or not family_empty or reason:
        errors.append("operational:" + (reason or "child_or_family"))
    if observer_log is None or not Path(observer_log).is_file():
        errors.append("operational:independent_observer_log")
    else:
        try:
            events = [json.loads(x) for x in Path(observer_log).read_text(encoding="utf-8").splitlines() if x]
            if not any(x.get("event") == "watchdog_started" and x.get("pid") == os.getpid()
                       for x in events) or any(x.get("event") in ("trigger", "supervisor_killed")
                                             for x in events):
                errors.append("operational:independent_observer_receipt")
        except (OSError, ValueError):
            errors.append("operational:independent_observer_receipt")
    try:
        if (result.get("schema") != "s2-foot-kit-check-v1" or
            result.get("training_updates") != 0 or result.get("optimizer_steps") != 0 or
            result.get("control_steps", 301) > 300 or result.get("max_envs", 9) > 8 or
            [x["scene"] for x in result["scenes"]] !=
            list(__import__("s2_foot_scenes").SCENES)):
            errors.append("data:result_scope")
        support = swing = False
        for scene in result["scenes"]:
            if not scene["rows"] or scene["manager_terms"]["count"] != 16:
                errors.append("data:scene_or_reward_terms_missing")
            for row in scene["rows"]:
                if row.get("manager_evidence") is None or row.get("analytic_rays") is None or \
                   len(row.get("usd_collision_spheres", [])) != 4*len(row.get("foot_centers_w_m", [])) or \
                   len(row.get("contact_ids") or []) != 4:
                    errors.append("data:step_evidence_missing")
                    continue
                expected = _oracle(row)
                if expected is not None and any(abs(a-b) > 1e-6 for a,b in zip(expected, row["raw_cost"])):
                    errors.append("data:analytic_cost_mismatch")
                if expected is None:
                    errors.append("data:boundary_only_oracle")
                for env in row["contact_forces_w_n"]:
                    for f in env:
                        support |= f[2] > 1.05
                        swing |= f[2] < .95
        if not support or not swing:
            errors.append("data:support_or_swing_unobserved")
        if result["scenes"][-1].get("partial_reset") is None:
            errors.append("data:partial_reset_unobserved")
    except (KeyError, TypeError, ValueError, IndexError):
        errors.append("data:result_unreadable")
    return {"verdict": "HOLD" if errors else "INFORMATION_ONLY", "reasons": sorted(set(errors)),
            "comparison_ready": False, "performance_verified": False,
            "training_updates": 0, "optimizer_steps": 0}


def run_foot(m, approval, *, clock=time.time, mono=time.monotonic, sleep=time.sleep,
             owner_factory=None, lease_factory=None, lock_factory=None,
             meter_factory=NvmlMeter, observer_check=observer_armed,
             fixture=False, validator=validate):
    validator(m, approval, now=clock(), fixture=fixture)
    claim = Path(m["claim_root"]) / (m["chain_id"] + "-" + m["attempt"] + ".claim")
    claim.parent.mkdir(parents=True, exist_ok=True)
    try:
        claim.mkdir(exist_ok=False)
    except FileExistsError as ex:
        raise FootSupervisorHold("claim_reused") from ex
    absolute_deadline = mono() + min(m["max_wall_s"], m["deadline_epoch"]-clock())
    phases = {k: None for k in ("claim", "observer", "lease", "usd_lock", "kit_launch",
                                 "child_exit", "family_empty", "lease_release", "usd_lock_release")}
    phases["claim"] = clock()
    owner = lease = lock = meter = None
    rc = reason = None
    family_empty = False

    def status(state, **extra):
        atomic_json(Path(m["status_path"]), {"state": state, "claim": claim.name,
              "epoch": clock(), "remaining_s": max(0., min(m["deadline_epoch"]-clock(),
                                                          absolute_deadline-mono())), **extra})

    status("STARTING")
    try:
        observer = None
        while observer is None and mono() < absolute_deadline:
            try:
                observer = observer_check(m)
            except Exception:
                if clock()-phases["claim"] > 20:
                    raise FootSupervisorHold("observer_not_armed")
                status("WAIT_OBSERVER")
                sleep(.2)
        if observer is None:
            raise FootSupervisorHold("observer_deadline")
        phases["observer"] = clock()
        lease = (lease_factory or gpu_lease)(Path(m["lease_root"]), m["gpu_uuid"]).acquire()
        phases["lease"] = clock()
        lock = (lock_factory or usd_conversion_lock)(Path(m["usd_lock_path"])).acquire()
        phases["usd_lock"] = clock()
        if not fixture:
            meter = meter_factory()
            preflight(meter.probe(m["gpu_index"]), disk_free(Path(m["result_path"]).parent), m)
        Path(m["usd_root"]).mkdir(parents=True, exist_ok=False)
        owner = (owner_factory or (lambda: JobOwner(WinKernel())))()
        env = os.environ.copy()
        env.update({"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": str(m["gpu_index"]),
                    "FOOTHOLD_USD_ROOT": m["usd_root"], "FOOTHOLD_EXPECT_CONVERSIONS": "any",
                    "FOOTHOLD_CONVERSION_CAP": "8", "FOOTHOLD_S2_FOOT_PURPOSE": "one_shot_no_learning"})
        phases["kit_launch"] = clock()
        Path(m["log_path"]).parent.mkdir(parents=True, exist_ok=True)
        owner.launch(required_argv(m), Path(m["driver_path"]).parent, env,
                     log_path=Path(m["log_path"]))
        while owner.active_count():
            if Path(m["stop_path"]).exists():
                reason = "STOP"; break
            if clock() >= m["deadline_epoch"] or mono() >= absolute_deadline:
                reason = "deadline"; break
            try:
                observer_check(m)
            except Exception:
                reason = "observer_lost"; break
            if not fixture:
                running(meter.probe(m["gpu_index"]), disk_free(Path(m["log_path"]).parent),
                        tree_bytes(Path(m["log_path"]).parent)+tree_bytes(Path(m["usd_root"])), m)
            status("RUNNING", pid=owner.pid)
            sleep(min(1., max(.01, absolute_deadline-mono())))
        if reason:
            owner.stop_owned(wait_seconds=10.)
        rc = owner.exit_code()
        phases["child_exit"] = clock()
    except (OSError, ValueError, KeyError, FootSupervisorHold, OwnershipHold, LeaseHold, ResourceHold) as ex:
        reason = str(ex)
    finally:
        if owner is not None:
            try:
                if owner.active_count():
                    owner.stop_owned(wait_seconds=10.)
                family_empty = owner.active_count() == 0
                owner.close()
            except OwnershipHold:
                family_empty = False
        if family_empty:
            phases["family_empty"] = clock()
        if lease is not None:
            try:
                lease.release(family_empty=family_empty)
                phases["lease_release"] = clock()
            except LeaseHold:
                reason = "lease_release"
        if lock is not None:
            try:
                lock.release(family_empty=family_empty)
                phases["usd_lock_release"] = clock()
            except LeaseHold:
                reason = "usd_lock_release"
        if meter is not None:
            try:
                meter.close()
            except Exception:
                reason = "meter_release"
    try:
        result = json.loads(Path(m["result_path"]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        result = {}
    answer = verdict(result, rc=rc, family_empty=family_empty, reason=reason,
                     observer_log=m["observer_log_path"])
    receipt = {"scope": m["scope"], "claim": claim.name,
               "manifest_sha256": hashlib.sha256(canonical(m)).hexdigest(),
               "approval_sha256": hashlib.sha256(canonical(approval)).hexdigest(),
               "argv": required_argv(m), "phases": phases, "child_rc": rc,
               "family_empty": family_empty, "result_sha256": sha(m["result_path"])
               if Path(m["result_path"]).is_file() else None, "verdict": answer}
    atomic_json(claim/"foot.receipt.json", receipt)
    status(answer["verdict"], reasons=answer["reasons"],
           receipt_sha256=sha(claim/"foot.receipt.json"))
    return answer


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--approval", required=True)
    a = p.parse_args(argv)
    m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    approval = json.loads(Path(a.approval).read_text(encoding="utf-8"))
    result = run_foot(m, approval)
    print(json.dumps(result), flush=True)
    return 0 if result["verdict"] == "INFORMATION_ONLY" else 42


if __name__ == "__main__":
    raise SystemExit(main())
