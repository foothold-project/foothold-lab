"""Single-use supervised request contract for the S2-2 Kit foot check."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from s2_eval_cpu import sha
from s2_eval_scope import CODE_NAMES as EVAL_CODE_NAMES
from s2_foot_scenes import SCENES


class FootScopeHold(RuntimeError):
    pass


CODE_NAMES = tuple(dict.fromkeys(EVAL_CODE_NAMES +
             ("s2_foot_kit_driver.py", "s2_foot_kit_scope.py", "s2_foot_kit_supervisor.py",
              "s2_foot_query.py", "s2_foot_reward.py", "s2_foot_config.py",
              "s2_foot_manager_evidence.py", "s2_foot_scenes.py")))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def required_argv(m):
    return [m["python_path"], "-B", m["isolate_path"], m["driver_path"],
            "--request", m["request_path"], "--request-sha256", m["request_sha256"],
            "--out", m["result_path"], "--headless", "--device", "cuda:0"]


def validate(m, approval, *, now, bundle=None, fixture=False):
    bundle = Path(__file__).resolve().parent if bundle is None else Path(bundle).resolve()
    keys = ("scope", "purpose", "chain_id", "attempt", "claim_root", "status_path",
            "stop_path", "observer_registration_path", "observer_log_path", "lease_root",
            "usd_lock_path", "usd_root", "result_path", "log_path", "python_path",
            "python_sha256", "isolate_path", "isolate_sha256", "driver_path",
            "driver_sha256", "request_path", "request_sha256", "gpu_uuid", "gpu_index",
            "deadline_epoch", "max_wall_s", "max_launches", "retry_count", "argv",
            "code_hashes", "observer_mode", "max_envs", "max_control_steps",
            "training_updates", "optimizer_steps")
    keys += ("min_free_vram_bytes", "running_floor_vram_bytes", "min_free_disk_bytes",
             "max_disk_bytes")
    if any(k not in m or m[k] in (None, "", "UNDECIDED") for k in keys):
        raise FootScopeHold("required_manifest_field")
    if (m["scope"] != "s2_foot_kit_check_once" or m["purpose"] != "one_shot_no_learning" or
        m["max_launches"] != 1 or m["retry_count"] != 0 or
        m["training_updates"] != 0 or m["optimizer_steps"] != 0 or
        m["max_envs"] > 8 or m["max_control_steps"] != 300 or
        m["observer_mode"] != "attended"):
        raise FootScopeHold("foot_scope")
    if any(re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", m[k]) is None for k in ("chain_id", "attempt")):
        raise FootScopeHold("claim_id")
    if (type(m["max_wall_s"]) is not int or not 0 < m["max_wall_s"] <= 900 or
        type(m["deadline_epoch"]) not in (int, float) or
        not now < m["deadline_epoch"] <= now+m["max_wall_s"] or
        type(m["gpu_index"]) is not int or m["gpu_index"] not in (0, 1)):
        raise FootScopeHold("deadline_or_gpu")
    if any(type(m[k]) is not int or m[k] <= 0 for k in
           ("min_free_vram_bytes", "running_floor_vram_bytes", "min_free_disk_bytes",
            "max_disk_bytes")):
        raise FootScopeHold("resource_limits")
    if (approval.get("status") != "APPROVED" or approval.get("scope") != m["scope"] or
        approval.get("manifest_sha256") != hashlib.sha256(canonical(m)).hexdigest() or
        approval.get("expires_epoch", 0) < m["deadline_epoch"] or not approval.get("by")):
        raise FootScopeHold("direct_approval_missing")
    if m["argv"] != required_argv(m):
        raise FootScopeHold("exact_argv")
    if Path(m["driver_path"]).resolve() != (bundle/"s2_foot_kit_driver.py").resolve():
        raise FootScopeHold("driver_allowlist")
    if Path(m["isolate_path"]).resolve() != (bundle/"usd_isolate_run_v3.py").resolve():
        raise FootScopeHold("isolate_allowlist")
    if (not fixture and Path(m["usd_lock_path"]).resolve() !=
        Path("C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock").resolve()):
        raise FootScopeHold("usd_lock_allowlist")
    for path, digest in (("python_path", "python_sha256"), ("driver_path", "driver_sha256"),
                         ("isolate_path", "isolate_sha256"), ("request_path", "request_sha256")):
        if not Path(m[path]).is_file() or sha(m[path]) != m[digest]:
            raise FootScopeHold("input_sha256:" + path)
    if set(m["code_hashes"]) != set(CODE_NAMES):
        raise FootScopeHold("code_closure_names")
    for name in CODE_NAMES:
        if sha(bundle/name) != m["code_hashes"][name]:
            raise FootScopeHold("code_closure_sha256:" + name)
    request = json.loads(Path(m["request_path"]).read_text(encoding="utf-8"))
    if (request.get("scope") != m["scope"] or request.get("scenes") != list(SCENES) or
        request.get("training_updates") != 0 or request.get("optimizer_steps") != 0 or
        request.get("max_wall_s") != m["max_wall_s"] or
        type(request.get("steps_per_scene")) is not int or
        not 2 <= request["steps_per_scene"] <= 37 or
        8*request["steps_per_scene"] > 300):
        raise FootScopeHold("request_scope")
    if Path(m["stop_path"]).exists():
        raise FootScopeHold("STOP")
    for key in ("claim_root", "status_path", "observer_registration_path", "observer_log_path",
                "result_path", "log_path", "usd_root"):
        target = Path(m[key]).resolve()
        if bundle.parent not in target.parents:
            raise FootScopeHold("output_outside_workspace:" + key)
    for key in ("result_path", "log_path", "usd_root"):
        if Path(m[key]).exists():
            raise FootScopeHold("output_exists:" + key)
    if not fixture and m["gpu_uuid"] in ("UNDECIDED", "synthetic-gpu-0"):
        raise FootScopeHold("gpu_identity")
    return request
