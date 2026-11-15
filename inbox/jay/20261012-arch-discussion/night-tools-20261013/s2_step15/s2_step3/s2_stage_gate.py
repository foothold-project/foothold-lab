"""CPU-only S2 chain verdict. No GPU, Isaac import or subprocess launch."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from s2_connect_check import Criteria, check_path

STAGES = ("connect", "smoke", "short_ab")
STAGE_HOLD_TABLE = (
    "approval_unbound", "manifest_unfrozen", "previous_missing", "previous_hash",
    "attempt_reused", "budget", "exit_code", "traceback", "artifact_missing",
    "artifact_hash", "fingerprint", "connect_hold", "train_hold", "fault_count",
    "nonfinite", "map_time", "step_count", "encounter_missing", "device_metrics",
    "deadline", "stop_file",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_digest(manifest: dict) -> str:
    frozen = {key: manifest[key] for key in ("inputs", "stages", "criteria", "stop_file", "deadline_epoch")}
    return hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _positive_number(value):
    return type(value) in (float, int) and math.isfinite(value) and value > 0


def verdict(manifest: dict, stage: str, record: dict, *, previous: dict | None = None,
            seen_attempts=(), now_epoch: float) -> dict:
    reasons = []
    def hold(key, bad):
        if bad and key not in reasons:
            reasons.append(key)
    if stage not in STAGES:
        raise ValueError("unknown S2 stage")
    approval = manifest.get("approval", {})
    hold("approval_unbound", approval.get("status") != "APPROVED" or not approval.get("by") or
         approval.get("frozen_sha256") != frozen_digest(manifest))
    inputs, stages = manifest.get("inputs", {}), manifest.get("stages", {})
    plan = stages.get(stage, {})
    budget_keys = ("max_launches", "max_wall_s", "diag_steps") if stage == "connect" else (
        "max_launches", "max_wall_s", "updates_per_arm", "epochs", "minibatches")
    hold("manifest_unfrozen", not inputs or not plan or not all(_positive_number(plan.get(key)) for key in budget_keys) or
         not all(isinstance(inputs.get(key), str) and len(inputs[key]) == 64 for key in
                 ("parent_sha256", "code_sha256", "env_config_sha256")))
    hold("deadline", not _positive_number(manifest.get("deadline_epoch")) or now_epoch >= manifest["deadline_epoch"])
    hold("stop_file", bool(manifest.get("stop_file") and Path(manifest["stop_file"]).exists()))
    idx = STAGES.index(stage)
    if idx:
        hold("previous_missing", previous is None or previous.get("stage") != STAGES[idx-1] or
             previous.get("verdict") != "PASS")
        if previous is not None:
            hold("previous_hash", record.get("previous_sha256") != hashlib.sha256(
                json.dumps(previous, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
    hold("attempt_reused", not record.get("attempt") or record.get("attempt") in seen_attempts)
    hold("budget", not _positive_number(record.get("launches")) or not _positive_number(record.get("wall_s")) or
         (bool(plan) and (record.get("launches", math.inf) > plan.get("max_launches", 0) or
                          record.get("wall_s", math.inf) > plan.get("max_wall_s", 0))))
    hold("exit_code", record.get("exit_code") != 0)
    hold("traceback", bool(record.get("traceback")) or "Traceback (most recent call last)" in record.get("log_tail", ""))
    artifacts = record.get("artifacts") or {}
    required = ("connect_meta", "connect_npz") if stage == "connect" else ("A_result", "B_result", "A_log", "B_log")
    hold("artifact_missing", any(key not in artifacts or not Path(artifacts[key].get("path", "")).is_file()
                                 for key in required))
    if not reasons or all(key not in reasons for key in ("artifact_missing",)):
        for entry in artifacts.values():
            p = Path(entry.get("path", ""))
            hold("artifact_hash", not p.is_file() or digest(p) != entry.get("sha256"))
    hold("fingerprint", any(record.get(key) != inputs.get(key) for key in
                            ("parent_sha256", "code_sha256", "env_config_sha256")))
    if stage == "connect" and not any(x in reasons for x in ("artifact_missing", "artifact_hash")):
        root = Path(artifacts["connect_meta"]["path"]).parent
        result = check_path(root, Criteria(**manifest["criteria"]))
        hold("connect_hold", result["verdict"] != "PASS")
    elif stage != "connect" and not any(x in reasons for x in ("artifact_missing", "artifact_hash")):
        for arm in ("A", "B"):
            item = json.loads(Path(artifacts[f"{arm}_result"]["path"]).read_text(encoding="utf-8"))
            hold("train_hold", item.get("status") != "PASS" or item.get("arm") != arm)
            hold("fault_count", sum(item.get("fault_counts", {}).values()) != 0 or
                 item.get("discarded_transitions") != 0)
            hold("nonfinite", item.get("nonfinite_count") != 0)
            hold("map_time", item.get("map_time_valid") is not True)
            counts = tuple(plan.get(k) for k in ("updates_per_arm", "epochs", "minibatches"))
            expected_steps = math.prod(counts) if all(_positive_number(x) for x in counts) else None
            hold("step_count", item.get("executed_updates") != plan.get("updates_per_arm") or
                 item.get("planned_updates") != plan.get("updates_per_arm") or
                 item.get("optimizer_steps_actual") != expected_steps or
                 item.get("optimizer_steps_expected") != expected_steps)
            hold("encounter_missing", not item.get("encounters_verified"))
            hold("device_metrics", not _positive_number(item.get("device_peak_mib")) or
                 not _positive_number(item.get("device_min_free_mib")) or
                 not _positive_number(item.get("iterations_per_hour")))
    reasons = sorted(reasons)
    result = {"stage": stage, "verdict": "PASS" if not reasons else "HOLD", "reasons": reasons,
              "attempt": record.get("attempt"), "record_sha256": hashlib.sha256(
                  json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    if not reasons and idx < len(STAGES)-1:
        next_name = STAGES[idx+1]
        result["next_args"] = {"stage": next_name, "previous_sha256": hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "frozen_sha256": frozen_digest(manifest), "plan": stages[next_name]}
    return result


def claim_once(root: Path, stage: str, attempt: str) -> Path:
    if stage not in STAGES or not attempt or any(c in attempt for c in "/\\:"):
        raise ValueError("invalid stage or attempt")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{stage}-{attempt}.claim"
    path.mkdir(exist_ok=False)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--stage", choices=STAGES, required=True)
    ap.add_argument("--record", type=Path, required=True)
    ap.add_argument("--previous", type=Path)
    ap.add_argument("--now_epoch", type=float, required=True)
    a = ap.parse_args(argv)
    m = json.loads(a.manifest.read_text(encoding="utf-8"))
    r = json.loads(a.record.read_text(encoding="utf-8"))
    p = json.loads(a.previous.read_text(encoding="utf-8")) if a.previous else None
    result = verdict(m, a.stage, r, previous=p, now_epoch=a.now_epoch)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 42


if __name__ == "__main__":
    raise SystemExit(main())
