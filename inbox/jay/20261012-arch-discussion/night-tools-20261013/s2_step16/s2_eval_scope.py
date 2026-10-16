"""Sealed, single-use evaluation-only launch contract. Import never launches Kit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from s2_eval_cases import verify as verify_cases, canonical, COMMANDS
from s2_eval_cpu import sha
from s2_eval_driver import validate_job, PARENT_E1_SHA256, AGENT_YAML_SHA256
from s2_step4a34.s2_a34_provenance import asset_snapshot, closure_sha256


class ScopeHold(RuntimeError):
    pass


CODE_NAMES = ("s2_eval_driver.py", "s2_eval_cases.py", "s2_eval_cpu.py",
              "s2_eval_pre_reset.py", "s2_eval_case_fingerprint.py",
              "s2_eval_kit_adapter.py", "s2_eval_usd_provenance.py",
              "s2_env_adapter_17v.py", "s2_packet_17v.py",
              "s2_sensor_tracker_17v.py", "s2_map_obs.py", "s2_policy.py",
              "s2_1043_q_metrics.py", "s2_job_owner.py", "s2_resource_lease.py",
              "s2_eval_scope.py", "s2_eval_supervisor.py", "usd_isolate_run_v3.py",
              "s2_step4a34/s2_a34_provenance.py", "s2_step4a34/s2_hard_watchdog.py",
              "s2_step4a34/s2_stage0_resources_a2.py", "s2_step4a34/s2_device_binding_a2.py")
FULL_COUNTS = {"gap": 20, "stepping_stones": 20, "flat": 10, "stairs_up": 10}
SMOKE_COUNTS = {"gap": 2, "stepping_stones": 2, "flat": 0, "stairs_up": 0}
USD_LOCK = Path("C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock")
ASSET = Path("C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf")


def required_argv(m):
    return [m["python_path"], "-B", m["isolate_path"], m["driver_path"],
            "--job", m["job_path"], "--job-sha256", m["job_sha256"],
            "--cases", m["cases_path"], "--cases-file-sha256", m["cases_file_sha256"],
            "--out", m["episodes_path"], "--asset-path", m["asset_path"],
            "--hook-source-path", m["hook_source_path"],
            "--hook-source-sha256", m["hook_source_sha256"],
            "--headless", "--device", "cuda:0"]


def _under(path, root):
    p, r = Path(path).resolve(), Path(root).resolve()
    return r in p.parents


def validate_lead_case_plan(cases):
    verify_cases(cases)
    phase = cases["phase"]
    if (phase == "smoke" and cases["counts"] != SMOKE_COUNTS or
        phase == "full" and cases["counts"] != FULL_COUNTS or
        phase not in ("smoke", "full")):
        raise ScopeHold("lead_pair_counts")
    names = {c["command"]["name"] for c in cases["cases"]}
    if len(names) != 1 or (phase == "smoke" and names != {"fwd10"}) or not names <= {"fwd10", "fwd03"}:
        raise ScopeHold("lead_command_plan")
    if any(c["command"] != COMMANDS[c["command"]["name"]] or c["difficulty"] != .5 or
           c["friction"] != 1. or c["policy_dt"] != .02 or c["physics_dt"] != .005 or
           c["terrain_set"] != ("unseen10" if c["family"] in ("gap", "stepping_stones") else "train")
           for c in cases["cases"]):
        raise ScopeHold("lead_terrain_command_physics")
    return True


def validate(m, approval, *, now, bundle=None, fixture=False):
    if bundle is None:
        bundle = Path(__file__).resolve().parent
    required = ("scope", "purpose", "chain_id", "attempt", "claim_root", "status_path",
                "stop_path", "deadline_epoch", "max_wall_s", "observer_mode", "observer_registration_path", "observer_log_path",
                "max_launches", "retry_count", "training_updates", "python_path", "python_sha256",
                "isolate_path", "isolate_sha256", "driver_path", "driver_sha256",
                "job_path", "job_sha256", "cases_path", "cases_file_sha256",
                "episodes_path", "log_path", "usd_root", "usd_lock_path", "lease_root",
                "gpu_uuid", "gpu_index", "gpu_bus_id", "asset_path", "asset_closure_sha256",
                "hook_source_path", "hook_source_sha256", "code_hashes", "argv", "phase",
                "min_free_vram_bytes", "running_floor_vram_bytes", "min_free_disk_bytes",
                "max_disk_bytes", "expect_conversions", "usd_conversion_cap")
    if any(k not in m or m[k] in (None, "", "UNDECIDED") for k in required):
        raise ScopeHold("required_manifest_field")
    if (m["scope"] != "s2_eval_kit_smoke_once" or m["purpose"] != "evaluation_information_only" or
        m["phase"] != "smoke" or m["max_launches"] != 1 or m["retry_count"] != 0 or
        m["training_updates"] != 0 or m["observer_mode"] != "attended"):
        raise ScopeHold("evaluation_only_scope")
    if any(re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", m[k]) is None for k in ("chain_id", "attempt")):
        raise ScopeHold("claim_id")
    if any(type(m[k]) is not int or m[k] <= 0 for k in
           ("min_free_vram_bytes", "running_floor_vram_bytes", "min_free_disk_bytes", "max_disk_bytes")):
        raise ScopeHold("resource_limits")
    if m["expect_conversions"] != "any" or m["usd_conversion_cap"] != 8:
        raise ScopeHold("evaluation_conversion_scope")
    if (type(m["gpu_index"]) is not int or m["gpu_index"] not in (0, 1) or
        type(m["max_wall_s"]) is not int or not 0 < m["max_wall_s"] <= 900 or
        type(m["deadline_epoch"]) not in (int, float) or
        not now < m["deadline_epoch"] <= now + m["max_wall_s"]):
        raise ScopeHold("resource_or_deadline")
    if m["gpu_uuid"] in ("synthetic-gpu-0", "synthetic-gpu-1", "UNDECIDED"):
        raise ScopeHold("real_gpu_uuid_required")
    if approval.get("status") != "APPROVED" or approval.get("scope") != m["scope"] or not approval.get("by"):
        raise ScopeHold("scope_approval_missing")
    if (approval.get("manifest_sha256") != hashlib.sha256(canonical(m)).hexdigest() or
        approval.get("expires_epoch", 0) < m["deadline_epoch"]):
        raise ScopeHold("approval_digest_or_expiry")
    if m["argv"] != required_argv(m):
        raise ScopeHold("exact_argv")
    # Case file field has a different explicit name.
    for path_key, hash_key in (("python_path", "python_sha256"),
                               ("isolate_path", "isolate_sha256"),
                               ("driver_path", "driver_sha256"),
                               ("job_path", "job_sha256"),
                               ("cases_path", "cases_file_sha256"),
                               ("hook_source_path", "hook_source_sha256")):
        p = Path(m[path_key])
        if not p.is_file() or sha(p) != m[hash_key]:
            raise ScopeHold("input_sha256:" + path_key)
    if Path(m["driver_path"]).resolve() != (bundle / "s2_eval_driver.py").resolve():
        raise ScopeHold("driver_allowlist")
    if not fixture:
        if (Path(m["asset_path"]).resolve() != ASSET.resolve() or
            Path(m["isolate_path"]).resolve() != (bundle / "usd_isolate_run_v3.py").resolve() or
            Path(m["usd_lock_path"]).resolve() != USD_LOCK.resolve() or
            not USD_LOCK.is_file()):
            raise ScopeHold("asset_isolate_lock_allowlist")
    if set(m["code_hashes"]) != set(CODE_NAMES):
        raise ScopeHold("code_closure_names")
    for name in CODE_NAMES:
        p = bundle / name
        if not p.is_file() or sha(p) != m["code_hashes"][name]:
            raise ScopeHold("code_closure_sha256:" + name)
    if m["driver_sha256"] != m["code_hashes"]["s2_eval_driver.py"]:
        raise ScopeHold("driver_hash_disagrees_with_closure")
    if not fixture:
        expected = closure_sha256(asset_snapshot(m["asset_path"],
                     "C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/assets/unitree.py",
                     "C:/isaac/IsaacLab/source/isaaclab/isaaclab/sim/converters/asset_converter_base.py"))
        if m["asset_closure_sha256"] != expected:
            raise ScopeHold("asset_dependency_hash")
    for key in ("claim_root", "status_path", "episodes_path", "log_path", "usd_root", "observer_log_path", "observer_registration_path"):
        if not _under(m[key], bundle.parent):
            raise ScopeHold("write_outside_codexE:" + key)
    for key in ("episodes_path", "log_path", "usd_root"):
        if Path(m[key]).exists():
            raise ScopeHold("output_exists:" + key)
    if Path(m["episodes_path"]).name != "episodes.json" or Path(m["log_path"]).name != "child.log":
        raise ScopeHold("output_name_allowlist")
    roots = [Path(m[k]).parent.resolve() for k in ("episodes_path", "log_path", "observer_log_path")]
    roots.append(Path(m["usd_root"]).resolve())
    if len(set(roots)) != len(roots) or any(a in b.parents or b in a.parents for a in roots for b in roots if a != b):
        raise ScopeHold("output_roots_overlap")
    if Path(m["stop_path"]).exists():
        raise ScopeHold("STOP")
    job = json.loads(Path(m["job_path"]).read_text(encoding="utf-8"))
    cases = json.loads(Path(m["cases_path"]).read_text(encoding="utf-8"))
    validate_lead_case_plan(cases)
    if (cases["phase"] != "smoke" or
        job.get("phase") != "smoke" or job.get("update") != 0 or
        job.get("inference") != "act_inference" or job.get("cases_sha256") != cases["cases_sha256"]):
        raise ScopeHold("lead_frozen_case_or_job")
    if set(cases["learning_seeds"]) & {c["eval_seed"] for c in cases["cases"]}:
        raise ScopeHold("learning_eval_seed_overlap")
    validate_job(job, cases, require_identity=not fixture)
    for name, pinned in (("parent", PARENT_E1_SHA256), ("agent_yaml", AGENT_YAML_SHA256)):
        ref = job.get(name, {})
        if not ref.get("path") or ref.get("sha256") != pinned or sha(ref["path"]) != pinned:
            raise ScopeHold(name + "_input_sha256")
    for arm in ("A", "B"):
        ref = job["arms"][arm]
        if sha(ref["checkpoint"]) != ref["checkpoint_sha256"]:
            raise ScopeHold(arm + "_checkpoint_sha256")
    return {"job": job, "cases": cases}
