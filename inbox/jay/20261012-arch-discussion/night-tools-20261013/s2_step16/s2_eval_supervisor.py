"""One-shot evaluation-only Job Object supervisor. No launch on import."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from s2_eval_cases import canonical
from s2_eval_cpu import sha
from s2_eval_scope import ScopeHold, validate, required_argv
from s2_job_owner import JobOwner, WinKernel, OwnershipHold
from s2_resource_lease import gpu_lease, usd_conversion_lock, LeaseHold
from s2_step4a34.s2_a34_provenance import (asset_snapshot, assert_asset_unchanged,
                                           closure_sha256)
from s2_eval_usd_provenance import evidence as usd_evidence
from s2_step4a34.s2_stage0_resources_a2 import (NvmlMeter, disk_free, tree_bytes,
                                                 preflight, running, ResourceHold)


class EvalSupervisorHold(RuntimeError):
    pass


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(canonical(value) + b"\n")
    os.replace(tmp, path)


def observer_armed(m, *, process_lookup=None):
    """Read an independently started watchdog's PID, birth time and exact target."""
    if process_lookup is None:
        import psutil
        process_lookup = psutil.Process
    registration = json.loads(Path(m["observer_registration_path"]).read_text(encoding="utf-8"))
    if (registration.get("manifest_sha256") != hashlib.sha256(canonical(m)).hexdigest() or
        registration.get("status") != "ARMED" or
        registration.get("status_path") != m["status_path"] or
        registration.get("log_path") != m["observer_log_path"] or
        registration.get("hard_deadline_epoch") != m["deadline_epoch"] or
        type(registration.get("pid")) is not int or
        type(registration.get("create_time")) not in (int, float) or
        type(registration.get("supervisor_create_time")) not in (int, float)):
        raise EvalSupervisorHold("observer_registration_mismatch")
    proc = process_lookup(registration["pid"])
    target = process_lookup(os.getpid())
    if abs(target.create_time() - registration["supervisor_create_time"]) > .05:
        raise EvalSupervisorHold("supervisor_pid_reused")
    if (registration["pid"] == os.getpid() or
        abs(proc.create_time() - registration["create_time"]) > .05 or not proc.is_running()):
        raise EvalSupervisorHold("observer_pid_reused_or_dead")
    args = proc.cmdline()
    def flag(name):
        return args[args.index(name) + 1] if args.count(name) == 1 and args.index(name) + 1 < len(args) else None
    expected_watchdog = Path(__file__).resolve().parent / "s2_step4a34" / "s2_hard_watchdog.py"
    if (not any(Path(str(x)).resolve() == expected_watchdog for x in args) or
        flag("--status-path") != m["status_path"] or
        flag("--log") != m["observer_log_path"] or
        flag("--pid") != str(os.getpid()) or
        flag("--create-time") is None or
        abs(float(flag("--create-time")) - registration["supervisor_create_time"]) > .05 or
        flag("--hard-deadline-epoch") is None or
        float(flag("--hard-deadline-epoch")) != m["deadline_epoch"]):
        raise EvalSupervisorHold("observer_command_unverified")
    return registration


def _asset(m):
    return asset_snapshot(m["asset_path"],
        "C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/assets/unitree.py",
        "C:/isaac/IsaacLab/source/isaaclab/isaaclab/sim/converters/asset_converter_base.py")


def _runtime(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("runtime")
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def _output_verdict(m, *, rc, family_empty, reason, asset_before, observer,
                    expected_pid=None, require_device=False):
    errors = []
    episodes_path = Path(m["episodes_path"])
    records = []
    case_receipts = []
    if not episodes_path.is_file():
        errors.append("episodes_missing")
    else:
        try:
            data = json.loads(episodes_path.read_text(encoding="utf-8"))
            records = data["records"]
            cases = json.loads(Path(m["cases_path"]).read_text(encoding="utf-8"))
            expected_ids = {c["case_id"] for c in cases["cases"]}
            expected = 2 * len(expected_ids)
            if (len(records) != expected or data.get("schema") != "s2-eval-episodes-v1" or
                data.get("cases_sha256") != cases["cases_sha256"] or
                data.get("cases_file_sha256") != m["cases_file_sha256"] or
                data.get("job_file_sha256") != m["job_sha256"] or
                data.get("comparison_ready") is not False or data.get("performance_verified") is not False):
                errors.append("episode_schema_or_count")
            if expected_pid is not None and data.get("runtime", {}).get("pid") != expected_pid:
                errors.append("child_runtime_pid_mismatch")
            if require_device and any(not isinstance(data.get("checkpoint_receipts", {}).get(mode), dict)
                                      for mode in ("A", "B")):
                errors.append("checkpoint_identity_receipt_missing")
            if any(row.get("missing_reason") for row in records):
                errors.append("episode_missing_rows")
            case_receipts = [{"case_id": row.get("case_id"), "arm": row.get("arm"),
                              "fingerprint": row.get("fingerprint"),
                              "missing_reason": row.get("missing_reason")}
                             for row in records]
            by_case = {}
            for row in records:
                arms = by_case.setdefault(row.get("case_id"), {})
                if row.get("arm") in arms:
                    errors.append("duplicate_case_arm")
                arms[row.get("arm")] = row
            if set(by_case) != expected_ids:
                errors.append("case_ids_diff")
            if any(set(arms) != {"A", "B"} or arms["A"].get("fingerprint") != arms["B"].get("fingerprint")
                   for arms in by_case.values()):
                errors.append("paired_physical_fingerprint_diff")
        except Exception:
            errors.append("episodes_unreadable")
    if rc != 0:
        errors.append("child_exit_code")
    if not family_empty:
        errors.append("owned_family_active")
    if reason:
        errors.append(reason)
    asset_after_sha = None
    if asset_before is not None:
        try:
            after = _asset(m)
            asset_after_sha = closure_sha256(after)
            assert_asset_unchanged(asset_before, after, asset_before["urdf"]["sha256"])
        except Exception:
            errors.append("asset_dependency_changed")
    usd_record = None
    if not errors:
        try:
            refs = sorted({ref for row in records for ref in row["usd_robot_references"]})
            usd_record = usd_evidence(m["usd_root"], m["asset_path"], refs,
                                      max_entries=m["usd_conversion_cap"], case_rows=records)
        except Exception:
            errors.append("usd_isolation_or_robot_reference")
    observer_path = Path(m["observer_log_path"])
    observer_sha = sha(observer_path) if observer_path.is_file() else None
    if observer_sha is None:
        errors.append("independent_observer_log_missing")
    elif require_device:
        try:
            events = [json.loads(line) for line in observer_path.read_text(encoding="utf-8").splitlines() if line]
            if (not any(e.get("event") == "watchdog_started" and
                    e.get("pid") == os.getpid() for e in events) or
                any(e.get("event") in ("trigger", "supervisor_killed") for e in events)):
                errors.append("independent_observer_receipt")
        except (OSError, ValueError):
            errors.append("independent_observer_receipt")
    if require_device:
        path = Path(m["usd_root"]) / "device_binding.json"
        try:
            binding = json.loads(path.read_text(encoding="utf-8"))
            runtime = _runtime(episodes_path)
            if (not binding or runtime is None or
                runtime.get("device_binding", {}).get("torch_uuid_normalized") is None):
                errors.append("child_device_binding_missing")
        except (OSError, ValueError, AttributeError, TypeError):
            errors.append("child_device_binding_missing")
    classes = {"operational": [], "data": [], "performance": []}
    for error in sorted(set(errors)):
        classes["data" if error in ("paired_physical_fingerprint_diff", "case_ids_diff")
                else "operational"].append(error)
    for row in records:
        if row.get("missing_reason"):
            classes[row.get("failure_class", "operational") if row.get("failure_class") in classes
                    else "operational"].append(row["case_id"] + ":" + row["arm"] + ":" + row["missing_reason"])
    return {"verdict": "HOLD" if errors else "INFORMATION_ONLY",
            "reasons": sorted(set(errors)), "comparison_ready": False,
            "hold_classes": classes,
            "performance_verified": False, "information_only": True,
            "interpretation": "학습 0의 4짝 연결 시험에서 검사한 경로만 확인, 미시험 분기 별도",
            "training_updates": 0, "episode_count": len(records),
            "planned_case_arms": 8, "executed_case_arms": sum(r.get("executed", True) for r in records),
            "valid_case_arms": sum(not r.get("missing_reason") for r in records),
            "unrun_case_arms": max(0, 8 - sum(r.get("executed", True) for r in records)),
            "natural_termination_tested": any(r.get("natural_termination_tested") for r in records),
            "untested_branches": [] if any(r.get("natural_termination_tested") for r in records)
                                  else ["natural_termination"],
            "case_receipts": case_receipts,
            "episodes_sha256": sha(episodes_path) if episodes_path.is_file() else None,
            "asset_after_closure_sha256": asset_after_sha,
            "usd_evidence": usd_record, "observer_registration": observer,
            "observer_log_sha256": observer_sha}


def run_eval(m, approval, *, clock=time.time, mono=time.monotonic, sleep=time.sleep,
             owner_factory=None, lease_factory=None, lock_factory=None,
             meter_factory=NvmlMeter, observer_check=observer_armed,
             fixture=False, validator=validate):
    validator(m, approval, now=clock(), fixture=fixture)
    claim = Path(m["claim_root"]) / (m["chain_id"] + "-" + m["attempt"] + ".claim")
    claim.parent.mkdir(parents=True, exist_ok=True)
    try:
        claim.mkdir(exist_ok=False)
    except FileExistsError as ex:
        raise EvalSupervisorHold("claim_reused") from ex
    status_path = Path(m["status_path"])
    deadline_mono = mono() + min(m["max_wall_s"], m["deadline_epoch"] - clock())
    phases = {"claim_epoch": clock(), "observer_armed_epoch": None,
              "lease_acquired_epoch": None, "usd_lock_acquired_epoch": None,
              "kit_launch_epoch": None, "child_exit_epoch": None,
              "family_empty_epoch": None, "lease_released_epoch": None,
              "usd_lock_released_epoch": None}
    owner = lease = usd_lock = meter = None
    observer = None
    rc = None
    reason = None
    family_empty = False
    before = None
    atomic_json(claim / "attempt_start.json", {"manifest_sha256": hashlib.sha256(canonical(m)).hexdigest(),
             "approval_sha256": hashlib.sha256(canonical(approval)).hexdigest(),
             "argv": required_argv(m), "claim_id": claim.name, "epoch": clock()})
    def status(state, **extra):
        atomic_json(status_path, {"scope": m["scope"], "claim_id": claim.name,
            "state": state, "heartbeat_epoch": clock(),
            "remaining_s": max(0., min(m["deadline_epoch"]-clock(), deadline_mono-mono())), **extra})
    status("STARTING")
    try:
        # An external launcher starts s2_hard_watchdog.py, writes registration, then this owner proceeds.
        while observer is None and mono() < deadline_mono:
            try:
                observer = observer_check(m)
            except (OSError, ValueError, KeyError, EvalSupervisorHold):
                if clock() - phases["claim_epoch"] > 20.:
                    raise EvalSupervisorHold("observer_not_armed_within_20s")
                status("WAIT_OBSERVER")
                sleep(.2)
        if observer is None:
            raise EvalSupervisorHold("observer_deadline")
        phases["observer_armed_epoch"] = clock()
        lease = (lease_factory or gpu_lease)(Path(m["lease_root"]), m["gpu_uuid"]).acquire()
        phases["lease_acquired_epoch"] = clock()
        usd_lock = (lock_factory or usd_conversion_lock)(Path(m["usd_lock_path"])).acquire()
        phases["usd_lock_acquired_epoch"] = clock()
        if not fixture:
            meter = meter_factory()
            preflight(meter.probe(m["gpu_index"]), disk_free(Path(m["episodes_path"]).parent), m)
            before = _asset(m)
            if closure_sha256(before) != m["asset_closure_sha256"]:
                raise EvalSupervisorHold("asset_dependency_hash")
        Path(m["usd_root"]).mkdir(parents=True, exist_ok=False)
        owner = (owner_factory or (lambda: JobOwner(WinKernel())))()
        env = os.environ.copy()
        env.update({"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "CUDA_VISIBLE_DEVICES": str(m["gpu_index"]),
                    "FOOTHOLD_USD_ROOT": m["usd_root"],
                    "FOOTHOLD_EXPECT_CONVERSIONS": m["expect_conversions"],
                    "FOOTHOLD_CONVERSION_CAP": str(m["usd_conversion_cap"]),
                    "FOOTHOLD_S2_EVAL_PURPOSE": "evaluation_information_only",
                    "FOOTHOLD_S2_EVAL_GPU_UUID": m["gpu_uuid"]})
        log = Path(m["log_path"])
        log.parent.mkdir(parents=True, exist_ok=True)
        phases["kit_launch_epoch"] = clock()
        owner.launch(required_argv(m), Path(m["driver_path"]).parent, env, log_path=log)
        status("RUNNING", child_pid=owner.pid)
        initial_free = disk_free(log.parent) if not fixture else None
        while owner.active_count():
            if Path(m["stop_path"]).exists():
                reason = "STOP"; break
            if clock() >= m["deadline_epoch"] or mono() >= deadline_mono:
                reason = "deadline"; break
            try:
                observer_check(m)
            except (OSError, ValueError, KeyError, EvalSupervisorHold):
                reason = "independent_observer_lost"; break
            if not fixture:
                state_path = Path(m["usd_root"]) / "isolate_state.json"
                if state_path.is_file():
                    usd_state = json.loads(state_path.read_text(encoding="utf-8"))
                    if usd_state.get("conversions", 0) > m["usd_conversion_cap"]:
                        reason = "usd_conversion_cap_exceeded"; break
                running(meter.probe(m["gpu_index"]), disk_free(log.parent),
                        max(initial_free-disk_free(log.parent),
                            tree_bytes(log.parent)+tree_bytes(Path(m["episodes_path"]).parent)+
                            tree_bytes(Path(m["usd_root"]))), m)
            status("RUNNING", child_pid=owner.pid)
            sleep(min(1., max(.01, deadline_mono-mono())))
        if reason:
            owner.stop_owned(wait_seconds=10.)
        rc = owner.exit_code()
        phases["child_exit_epoch"] = clock()
        family_empty = owner.active_count() == 0
        if family_empty:
            phases["family_empty_epoch"] = clock()
        try:
            observer_check(m)
        except (OSError, ValueError, KeyError, EvalSupervisorHold):
            reason = "independent_observer_lost_after_child"
    except (OSError, ValueError, KeyError, OwnershipHold, LeaseHold, ResourceHold, EvalSupervisorHold) as ex:
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
        if lease is not None:
            try:
                lease.release(family_empty=family_empty)
                phases["lease_released_epoch"] = clock()
            except LeaseHold:
                reason = "lease_release_unverified"
        if usd_lock is not None:
            try:
                usd_lock.release(family_empty=family_empty)
                phases["usd_lock_released_epoch"] = clock()
            except LeaseHold:
                reason = "usd_lock_release_unverified"
        if meter is not None:
            try:
                meter.close()
            except Exception:
                reason = "meter_release_unverified"
    verdict = _output_verdict(m, rc=rc, family_empty=family_empty, reason=reason,
                              asset_before=before, observer=observer,
                              expected_pid=getattr(owner, "pid", None),
                              require_device=not fixture)
    artifacts = {name: sha(path) for name, path in (("episodes.json", Path(m["episodes_path"])),
                ("child.log", Path(m["log_path"])), ("observer.log", Path(m["observer_log_path"])),
                ("device_binding.json", Path(m["usd_root"]) / "device_binding.json"),
                ("isolate_state.json", Path(m["usd_root"]) / "isolate_state.json"),
                ("assigned.jsonl", Path(m["usd_root"]) / "assigned.jsonl"))
                if path.is_file()}
    receipt = {"claim_id": claim.name, "scope": m["scope"], "purpose": m["purpose"],
               "manifest_sha256": hashlib.sha256(canonical(m)).hexdigest(),
               "approval_sha256": hashlib.sha256(canonical(approval)).hexdigest(),
               "job_sha256": m["job_sha256"], "cases_file_sha256": m["cases_file_sha256"],
               "driver_sha256": m["driver_sha256"], "code_hashes": m["code_hashes"],
               "asset_closure_sha256": m["asset_closure_sha256"],
               "gpu_uuid": m["gpu_uuid"], "gpu_index": m["gpu_index"],
               "child_pid": getattr(owner, "pid", None), "child_exit_code": rc,
               "child_runtime": _runtime(m["episodes_path"]),
               "family_empty": family_empty, "phases": phases, "artifacts": artifacts,
               "verdict": verdict, "deadline_epoch": m["deadline_epoch"],
               "completed_epoch": clock()}
    atomic_json(claim / "eval.receipt.json", receipt)
    status("HOLD" if verdict["verdict"] == "HOLD" else "INFORMATION_ONLY",
           reasons=verdict["reasons"], receipt_sha256=sha(claim / "eval.receipt.json"))
    return verdict


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--approval", type=Path, required=True)
    a = p.parse_args(argv)
    verdict = run_eval(json.loads(a.manifest.read_text(encoding="utf-8")),
                       json.loads(a.approval.read_text(encoding="utf-8")))
    print(json.dumps(verdict, sort_keys=True), flush=True)
    return 0 if verdict["verdict"] == "INFORMATION_ONLY" else 42


if __name__ == "__main__":
    raise SystemExit(main())
