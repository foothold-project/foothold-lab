"""CPU-only registration and fail-closed checks for the 1043 evaluation candidate."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNDECIDED = "UNDECIDED"
WRITE_KEYS = ("data", "reports", "work", "attempts", "registry", "convert_lock",
              "run_lease", "slot_records", "stop", "logs", "compare_report")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def inside(path, root=ROOT):
    p = Path(path).resolve(strict=False)
    r = Path(root).resolve(strict=False)
    return p == r or r in p.parents


def assert_isolated(manifest):
    paths = manifest["contract"]["paths"]
    for key in WRITE_KEYS:
        p = paths.get(key)
        if not isinstance(p, str) or not p or not inside(p):
            raise ValueError(f"write path outside codexE: {key}={p!r}")
    for key in ("data", "reports", "work", "attempts", "registry", "slot_records", "logs"):
        for forbidden in ("/out/", "/out_branch/", "/slot/"):
            if forbidden in paths[key].replace("\\", "/").lower():
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
    device = c.get("device", {})
    paths = c.get("paths", {})
    if device.get("slot") != "v3" or device.get("registry") != "v3 dedicated" or not str(paths.get("registry", "")).endswith("isaac_usd_registry_v3.json"):
        errors.append("v3 registry contract")
    if (device.get("convert_lock") != "shared with participating v3 tools" or
            device.get("run_lease") != "separate from conversion lock, held through child tree exit" or
            paths.get("convert_lock") == paths.get("run_lease")):
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


def launch_errors(m):
    errors = check_inputs(m)
    e = m.get("execution", {})
    for key in ("gpu_index", "gpu_uuid", "deadline_epoch", "approval_path", "approval_sha256",
                "risk_limit", "run_lease_participants_confirmed", "convert_lock_shared_confirmed", "candidate_hashes",
                "comparison_report_sha256"):
        if e.get(key) in (None, "", UNDECIDED, False):
            errors.append(f"execution {key} undecided")
    if e.get("contract_sha256") != m["contract_sha256"]:
        errors.append("execution contract hash mismatch")
    device = m["contract"].get("device", {})
    for key in ("gpu_index", "gpu_uuid", "CUDA_VISIBLE_DEVICES"):
        if device.get(key) in (None, "", UNDECIDED) or e.get(key) != device.get(key):
            errors.append(f"device {key} undecided or inconsistent")
    runtime = m["contract"].get("runtime", {})
    for key in ("torch", "isaac"):
        if runtime.get(key) in (None, "", UNDECIDED):
            errors.append(f"runtime {key} undecided")
    hashes = e.get("candidate_hashes")
    if isinstance(hashes, dict):
        for name in ("s1043_manifest.py", "cmdr_bundle_compare_s1043.py",
                     "cmdr_eval_driver_s1043.py", "cmdr_post_s1043.py", "frozen_exec_s1043.py"):
            p = ROOT / "cand" / name
            if hashes.get(name) != sha256(p):
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
    if approval_path not in (None, "", UNDECIDED):
        try:
            if sha256(approval_path) != e.get("approval_sha256"):
                errors.append("approval hash mismatch")
            approval = json.loads(Path(approval_path).read_text(encoding="utf-8"))
            if (not isinstance(approval, dict) or approval.get("approved") is not True or
                    approval.get("experiment") != m["contract"]["experiment"] or approval.get("train_seed") != 1043 or
                    approval.get("contract_sha256") != m["contract_sha256"] or
                    approval.get("stage") != "A" or not approval.get("by") or not approval.get("approved_at")):
                errors.append("approval contract mismatch")
        except (OSError, ValueError, TypeError):
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
