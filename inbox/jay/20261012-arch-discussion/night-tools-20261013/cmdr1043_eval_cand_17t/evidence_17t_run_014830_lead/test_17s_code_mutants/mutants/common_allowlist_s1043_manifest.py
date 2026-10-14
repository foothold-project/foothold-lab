"""CPU-only registration and fail-closed checks for the 1043 evaluation candidate."""
from __future__ import annotations

import hashlib
import ast
import json
import math
import os
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[1]
UNDECIDED = "UNDECIDED"
WRITE_KEYS = ("data", "reports", "work", "attempts", "registry", "convert_lock",
              "run_lease", "slot_records", "stop", "logs", "compare_report")
COMMON_WRITE_KEYS = {"registry", "convert_lock", "run_lease"}
SUPPORTED_COMPARISON_RULES = frozenset({"semantic_and_json_bytes_and_traj_bytes"})
SUPPORTED_RESTART_SCOPES = frozenset({"single_start_no_reuse"})
SUPPORTED_PARTIAL_RESULTS = frozenset({"held"})
RESERVED_NAMES = frozenset({"undecided", "none", "null", "true", "false", "unknown", "nan"})
CANDIDATE_FILES = ("s1043_manifest.py", "cmdr_bundle_compare_s1043.py",
                   "cmdr_eval_driver_s1043.py", "cmdr_post_s1043.py", "frozen_exec_s1043.py")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
RESET_EXPECTED = {"origin_xy_m": [-0.5, 0.5], "origin_z_m": [0, 0.2],
                  "joints": "default pose scale 1.0", "body_velocity": [0, 0, 0, 0, 0, 0],
                  "yaw": "fixed per command; linear commands point toward world +x",
                  "spawn_offset": "", "spawn_offset_meaning": "no separate forward offset",
                  "rng": "u.reset(seed=eval_seed); original q_eval_cmdr.py controls consumption",
                  "physics_randomization": "push events off; other changes pinned by q evaluator and Go2EnvCfg"}


def candidate_dir(m):
    return Path(m["contract"]["deployment"]["candidate_dir"]).resolve(strict=False)


def check_reset(m):
    """Compare declared reset with literal q implementation and its registered source bytes."""
    c = m["contract"]
    if c.get("evaluation", {}).get("reset") != RESET_EXPECTED:
        return ["reset contract differs from pinned q"]
    try:
        rec = c["inputs"]["source_q_eval_cmdr.py"]
        source = Path(rec["path"]).read_text(encoding="utf-8")
        if sha256(rec["path"]) != rec["sha256"]:
            return ["reset source hash changed"]
        tree = ast.parse(source)
        pose = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "EventTerm":
                if any(k.arg == "func" and isinstance(k.value, ast.Name) and k.value.id == "reset_root_q" for k in node.keywords):
                    pose = next(ast.literal_eval(k.value)["pose_range"] for k in node.keywords if k.arg == "params")
                    break
        if pose != {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "z": (0.0, 0.2)}:
            return ["reset source pose range"]
        anchors = ('position_range"] = (1.0, 1.0)', 'write_root_velocity_to_sim(torch.zeros(len(env_ids), 6',
                   'u._q_yaw = yaw0', 'yaw0[lin_mask] = -torch.atan2', 'if args.spawn_offset:',
                   'obs_buf, _ = u.reset(seed=args.eval_seed)')
        if any(x not in source for x in anchors):
            return ["reset source behavior marker"]
    except (OSError, ValueError, KeyError, SyntaxError, StopIteration, TypeError):
        return ["reset source unreadable"]
    return []


def same_file_path(a, b):
    """Compare Windows aliases even before a lock file has been created."""
    pa, pb = Path(a), Path(b)
    try:
        if pa.exists() and pb.exists() and os.path.samefile(pa, pb):
            return True
    except OSError:
        pass
    return os.path.normcase(os.path.realpath(pa)).casefold() == os.path.normcase(os.path.realpath(pb)).casefold()


def approval_binding(m):
    """Exact execution decision that an externally digested approval must review."""
    c, e = m["contract"], m["execution"]
    return {"experiment": c["experiment"], "train_seed": 1043,
            "contract_sha256": m["contract_sha256"], "stage": e["stage"],
            "approval_id": e["approval_id"], "attempt": e["attempt"],
            "log_name": e["log_name"], "restart_scope": e["restart_scope"],
            "termination_policy": e["termination_policy"],
            "comparison_pass_rule": e["comparison_pass_rule"],
            "candidate_hashes": e["candidate_hashes"],
            "comparison_report_sha256": e["comparison_report_sha256"],
            "gpu_index": e["gpu_index"], "gpu_uuid": e["gpu_uuid"],
            "CUDA_VISIBLE_DEVICES": e["CUDA_VISIBLE_DEVICES"],
            "diagnostic_repeat_original": e["diagnostic_repeat_original"],
            "deadline_epoch": e["deadline_epoch"], "risk_limit": e["risk_limit"],
            "convert_lock": str(Path(c["paths"]["convert_lock"]).resolve(strict=False)),
            "run_lease": str(Path(c["paths"]["run_lease"]).resolve(strict=False)),
            "registry": str(Path(c["paths"]["registry"]).resolve(strict=False)),
            "python": c["runtime"]["python"]}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def inside(path, root=None):
    p = Path(path).resolve(strict=False)
    r = Path(root if root is not None else ROOT).resolve(strict=False)
    return p == r or r in p.parents


def assert_isolated(manifest):
    paths = manifest["contract"]["paths"]
    deployment = manifest["contract"].get("deployment", {})
    root = deployment.get("write_root")
    source = deployment.get("source_eval")
    if not isinstance(root, str) or not Path(root).is_absolute() or not isinstance(source, str):
        raise ValueError("deployment write root or source root missing")
    allow = deployment.get("common_write_allowlist", UNDECIDED)
    if allow == UNDECIDED:
        allow = []
    if not isinstance(allow, list):
        raise ValueError("common write allowlist invalid")
    entries = set()
    for entry in allow:
        if (not isinstance(entry, dict) or set(entry) != {"key", "path"} or
                entry["key"] not in COMMON_WRITE_KEYS or not isinstance(entry["path"], str) or
                not Path(entry["path"]).is_absolute() or
                any(ch in entry["path"] for ch in "*?[]") or Path(entry["path"]).is_dir() or
                Path(entry["path"]).suffix != (".json" if entry["key"] == "registry" else ".lock") or
                not inside(entry["path"], source) or
                not entry["path"].startswith(source.rstrip("\\/") + os.sep)):
            raise ValueError("common write allowlist invalid")
        entries.add((entry["key"], entry["path"]))
    for key in WRITE_KEYS:
        p = paths.get(key)
        private = isinstance(p, str) and inside(p, root) and not inside(p, source)
        common = isinstance(p, str) and inside(p, source)
        if not isinstance(p, str) or not p or not (private or common):
            raise ValueError(f"write path outside codexE: {key}={p!r}")
    for key in ("data", "reports", "work", "attempts", "registry", "slot_records", "logs"):
        for forbidden in ("/out/", "/out_branch/", "/slot/"):
            if forbidden in paths[key].replace("\\", "/").lower() and (key, paths[key]) not in entries:
                raise ValueError(f"forbidden output path: {key}")
    return {key: str(Path(paths[key]).resolve(strict=False)) for key in WRITE_KEYS}


def load(path):
    raw = Path(path).read_bytes()
    m = json.loads(raw.decode("utf-8"))
    if not isinstance(m, dict) or not isinstance(m.get("contract"), dict):
        raise ValueError("manifest missing contract")
    if m.get("contract_sha256") != canonical_hash(m["contract"]):
        raise ValueError("contract hash mismatch")
    assert_isolated(m)
    global ROOT
    ROOT = Path(m["contract"]["deployment"]["write_root"]).resolve(strict=False)
    return m


def check_inputs(m, *, require_files=True):
    c = m["contract"]
    errors = []
    if c.get("experiment") != "cmdr_s1043_pair_eval" or c.get("train_seed") != 1043:
        errors.append("experiment or seed")
    if c.get("evaluation", {}).get("seeds") != [1000, 1001, 1002, 1003, 1004]:
        errors.append("evaluation seeds")
    if len(c.get("plan", {}).get("base", [])) != 555 or len(c.get("plan", {}).get("A", [])) != 45:
        errors.append("plan count")
    errors.extend(check_reset(m))
    deployment = c.get("deployment", {})
    if (deployment.get("layout") != "single-directory" or not isinstance(deployment.get("candidate_dir"), str)
            or not Path(deployment["candidate_dir"]).is_absolute() or
            not same_file_path(deployment.get("candidate_dir", ""), Path(__file__).parent) or
            deployment.get("write_root") != str(ROOT) or
            not same_file_path(deployment.get("source_eval", ""), Path(c.get("inputs", {}).get("source_q_eval.py", {}).get("path", "")).parent)):
        errors.append("deployment layout or source root")
    device = c.get("device", {})
    paths = c.get("paths", {})
    if device.get("slot") != "v3" or device.get("registry") != "v3 dedicated" or not str(paths.get("registry", "")).endswith("isaac_usd_registry_v3.json"):
        errors.append("v3 registry contract")
    if (device.get("convert_lock") != "shared with participating v3 tools" or
            device.get("run_lease") != "separate from conversion lock, held through child tree exit" or
            same_file_path(paths.get("convert_lock", ""), paths.get("run_lease", ""))):
        errors.append("conversion lock or run lease contract")
    for name, rec in c.get("inputs", {}).items():
        if not isinstance(rec, dict) or not rec.get("path") or not rec.get("sha256"):
            errors.append(f"input record {name}")
            continue
        if require_files:
            try:
                if sha256(rec["path"]) != rec["sha256"]:
                    errors.append(f"input hash {name}")
            except OSError:
                errors.append(f"input missing {name}")
    for arm in ("off", "on"):
        d = c.get("branches", {}).get(arm, {})
        for field in ("result", "bundle_json", "bundle_npz", "stamp", "model_22000", "model_24000",
                      "run_log", "guard", "slot"):
            if field not in d or d[field] not in c.get("inputs", {}):
                errors.append(f"branch {arm} {field}")
        if require_files and "result" in d and d["result"] in c.get("inputs", {}):
            try:
                result = json.loads(Path(c["inputs"][d["result"]]["path"]).read_text(encoding="utf-8"))
                args = result["meta"]["args"]
                final = result["final_state"]
                if (args.get("cmdr"), args.get("seed"), args.get("parent"), args.get("updates"),
                        args.get("num_envs"), args.get("gate"), final.get("where"), final.get("label_next")) != (
                        arm, 1043, c["parent"]["path"], 4000, 8192, False, "end", 24000):
                    errors.append(f"branch {arm} not complete")
            except (OSError, ValueError, KeyError, TypeError):
                errors.append(f"branch {arm} result unreadable")
        if require_files and "stamp" in d and d["stamp"] in c.get("inputs", {}):
            try:
                stamp_path = Path(c["inputs"][d["stamp"]]["path"])
                stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
                listed = stamp["sha256"]
                if len(listed) != 9:
                    errors.append(f"branch {arm} stamp count")
                branch_root = stamp_path.parent.parent
                for rel, expected in listed.items():
                    target = (branch_root / rel).resolve(strict=False)
                    if branch_root.resolve() not in target.parents or sha256(target) != expected:
                        errors.append(f"branch {arm} stamp mismatch {rel}")
            except (OSError, ValueError, KeyError, TypeError):
                errors.append(f"branch {arm} stamp unreadable")
        if require_files and all(k in d for k in ("run_log", "guard", "slot")):
            try:
                log = Path(c["inputs"][d["run_log"]]["path"]).read_text(encoding="utf-8", errors="replace")
                guard = json.loads(Path(c["inputs"][d["guard"]]["path"]).read_text(encoding="utf-8"))
                slot = json.loads(Path(c["inputs"][d["slot"]]["path"]).read_text(encoding="utf-8"))
                if f"[BRANCH] done cmdr_s1043_{arm}_u4000" not in log:
                    errors.append(f"branch {arm} completion line")
                if guard.get("exit_code") != 0 or guard.get("stopped_by_guard"):
                    errors.append(f"branch {arm} guard exit")
                if slot.get("slot_rc") != 0:
                    errors.append(f"branch {arm} slot exit")
            except (OSError, ValueError, KeyError, TypeError):
                errors.append(f"branch {arm} end evidence unreadable")
    return errors


def launch_errors(m, *, approved_digest=None, require_files=True):
    errors = check_inputs(m, require_files=require_files)
    e = m.get("execution", {})
    if e.get("stage") not in ("diagnostic", "A"):
        errors.append("execution stage undecided")
    if type(e.get("diagnostic_repeat_original")) is not bool or (e.get("stage") == "A" and e.get("diagnostic_repeat_original") is not False):
        errors.append("execution diagnostic repeat decision invalid")
    if type(e.get("gpu_index")) is not int or e["gpu_index"] not in (0, 1):
        errors.append("execution gpu_index invalid")
    if not isinstance(e.get("gpu_uuid"), str) or e["gpu_uuid"] in ("", UNDECIDED):
        errors.append("execution gpu_uuid undecided")
    if type(e.get("deadline_epoch")) not in (int, float) or not math.isfinite(e["deadline_epoch"]) or e["deadline_epoch"] <= time.time():
        errors.append("execution deadline_epoch invalid")
    if not isinstance(e.get("approval_path"), str) or e["approval_path"] in ("", UNDECIDED) or not Path(e["approval_path"]).is_absolute():
        errors.append("execution approval_path undecided")
    for key in ("approval_sha256", "comparison_report_sha256"):
        if not isinstance(e.get(key), str) or not SHA_RE.fullmatch(e[key]):
            errors.append(f"execution {key} invalid")
    risk = e.get("risk_limit")
    if (not isinstance(risk, dict) or set(risk) != {"max_child_launches", "max_retries_per_run", "max_wall_s"} or
            any(type(risk[k]) is not int or risk[k] < (0 if k == "max_retries_per_run" else 1) for k in risk)):
        errors.append("execution risk_limit invalid")
    for key in ("run_lease_participants_confirmed", "convert_lock_shared_confirmed"):
        if e.get(key) is not True:
            errors.append(f"execution {key} not confirmed")
    if not isinstance(e.get("CUDA_VISIBLE_DEVICES"), str) or e["CUDA_VISIBLE_DEVICES"] not in ("0", "1"):
        errors.append("execution CUDA_VISIBLE_DEVICES invalid")
    for key in ("approval_id", "attempt", "log_name"):
        value = e.get(key)
        limit = 50 if key == "log_name" else 64
        if (not isinstance(value, str) or not re.fullmatch(rf"[A-Za-z0-9_-]{{1,{limit}}}", value) or
                value.casefold() in RESERVED_NAMES):
            errors.append(f"execution {key} invalid")
    scope = e.get("restart_scope")
    if not isinstance(scope, str) or scope not in SUPPORTED_RESTART_SCOPES:
        errors.append("execution restart_scope unsupported")
    comparison_rule = e.get("comparison_pass_rule")
    if not isinstance(comparison_rule, str) or comparison_rule not in SUPPORTED_COMPARISON_RULES:
        errors.append("execution comparison_pass_rule unsupported")
    policy = e.get("termination_policy")
    if (not isinstance(policy, dict) or set(policy) != {"terminate_grace_s", "partial_result"} or
            type(policy["terminate_grace_s"]) not in (int, float) or
            not math.isfinite(policy["terminate_grace_s"]) or policy["terminate_grace_s"] <= 0 or
            not isinstance(policy["partial_result"], str) or
            policy["partial_result"] not in SUPPORTED_PARTIAL_RESULTS):
        errors.append("execution termination_policy invalid")
    if e.get("contract_sha256") != m["contract_sha256"]:
        errors.append("execution contract hash mismatch")
    device = m["contract"].get("device", {})
    for key in ("gpu_index", "gpu_uuid", "CUDA_VISIBLE_DEVICES"):
        if (key == "gpu_index" and (type(device.get(key)) is not int or device[key] not in (0, 1))) or (
                key != "gpu_index" and (not isinstance(device.get(key), str) or device[key] in ("", UNDECIDED))) or e.get(key) != device.get(key):
            errors.append(f"device {key} undecided or inconsistent")
    if type(device.get("gpu_index")) is int and device.get("CUDA_VISIBLE_DEVICES") != str(device["gpu_index"]):
        errors.append("device CUDA_VISIBLE_DEVICES inconsistent")
    if device.get("child_logical_cuda") != 0 or type(device.get("child_logical_cuda")) is not int:
        errors.append("device child logical CUDA invalid")
    runtime = m["contract"].get("runtime", {})
    for key in ("torch", "isaac"):
        if runtime.get(key) in (None, "", UNDECIDED):
            errors.append(f"runtime {key} undecided")
    hashes = e.get("candidate_hashes")
    if not isinstance(hashes, dict) or set(hashes) != set(CANDIDATE_FILES) or any(
            not isinstance(v, str) or not SHA_RE.fullmatch(v) for v in hashes.values()):
        errors.append("execution candidate_hashes invalid")
    else:
        try:
            directory = candidate_dir(m)
        except (KeyError, TypeError, ValueError):
            directory = None
            errors.append("candidate deployment missing")
        for name in CANDIDATE_FILES:
            p = directory / name if directory is not None else None
            try:
                matched = hashes[name] == sha256(p)
            except (OSError, TypeError):
                matched = False
            if not matched:
                errors.append(f"candidate hash {name}")
    report_path = m["contract"]["paths"]["compare_report"]
    if isinstance(e.get("comparison_report_sha256"), str) and e["comparison_report_sha256"] != UNDECIDED:
        try:
            report = json.loads(Path(report_path).read_text(encoding="utf-8"))
            if (sha256(report_path) != e["comparison_report_sha256"] or
                    report.get("verdict") != "SAME" or report.get("contract_sha256") != m["contract_sha256"]):
                errors.append("comparison report mismatch")
        except (OSError, ValueError):
            errors.append("comparison report unreadable")
    approval_path = e.get("approval_path")
    if isinstance(approval_path, str) and approval_path not in ("", UNDECIDED):
        try:
            actual_digest = sha256(approval_path)
            if (not isinstance(approved_digest, str) or not SHA_RE.fullmatch(approved_digest) or
                    approved_digest != actual_digest or actual_digest != e.get("approval_sha256")):
                errors.append("approval hash mismatch")
            approval = json.loads(Path(approval_path).read_text(encoding="utf-8"))
            if (not isinstance(approval, dict) or approval.get("approved") is not True or
                    not approval.get("by") or not approval.get("approved_at") or
                    approval.get("reviewed") != approval_binding(m)):
                errors.append("approval contract mismatch")
        except (OSError, ValueError, TypeError, KeyError):
            errors.append("approval unreadable")
    return errors


def assert_environment(expected_self, expected_sha):
    import sys
    actual_self = str(Path(__file__).resolve())
    actual_sha = sha256(__file__)
    print("sys.executable", sys.executable)
    print("candidate.__file__", actual_self)
    print("candidate.sha256", actual_sha)
    if str(Path(expected_self).resolve()) != actual_self or expected_sha != actual_sha:
        raise RuntimeError("환경 불일치")
