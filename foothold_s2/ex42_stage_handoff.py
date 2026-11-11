"""EX-42 hand-off after a stage's last boundary evaluation (team lead c5471d37, contract #639).

The gate PASS plus an existing, bounded approval cell for the next stage lets the next stage start by itself; any
other case only says so in the notice. This module decides and starts the lead's launcher script; every check of the
approval and of the predecessor PASS is `ex42_auto_authorization.validate_automatic_stage_launch`, and the launcher
(the same script that started the stage that just ended) still runs the normal training entry preflight.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

LAUNCH_RECORD = "next_stage_launch.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decide_next_stage(plan_path, approvals_path, stage_id, iteration, p1_path, manifest_path) -> dict[str, Any] | None:
    """None before the stage's last boundary. Otherwise {action: launch | notify, state, reason, next_stage_id, ...}."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    plan = plan_path if isinstance(plan_path, EX42Plan) else EX42Plan.load(plan_path)
    stages = plan.document["stages"]
    index = next((i for i, row in enumerate(stages) if row.get("id") == stage_id), None)
    if index is None or iteration != stages[index].get("minimum_updates"):
        return None
    following = stages[index + 1]["id"] if index + 1 < len(stages) else None
    p1 = json.loads(Path(p1_path).read_text(encoding="utf-8-sig"))
    base = {"stage_id": stage_id, "boundary_iteration": iteration, "judgment": p1.get("judgment"),
            "next_stage_id": following, "checkpoint_sha256": p1.get("checkpoint_sha256")}
    if following is None or p1.get("judgment") != "PASS":
        return {**base, "action": "notify", "state": "not_ready",
                "reason": "no following stage" if following is None else f"gate judgment is {p1.get('judgment')}"}
    try:
        proof = validate_automatic_stage_launch(
            plan, approvals_path, target_stage=following, parent_manifest_path=manifest_path,
            gate_receipt_path=p1_path, expected_gate_sha256=_sha256(p1_path))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        return {**base, "action": "notify", "state": "next_stage_ready_for_approval",
                "reason": f"not authorized to start by itself: {exc}"}
    return {**base, "action": "launch", "state": "next_stage_authorized", "authorization": proof,
            "gate_sha256": proof["gate_sha256"]}


def start_launcher(decision, launcher, output, *, parent_manifest, parent_checkpoint, gate_receipt, popen=subprocess.Popen):
    """Run the lead's launcher once for an authorized decision. The record file is created exclusively first, so a
    second evaluation of the same boundary cannot start a second training."""
    launcher = Path(launcher)
    if not launcher.is_absolute() or not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise ValueError("EX-42 next-stage launcher must be an absolute path to an executable file")
    output = Path(output)
    record = {"format": "foothold-ex42-next-stage-launch/1", "target_stage": decision["next_stage_id"],
              "launcher": str(launcher), "launcher_sha256": _sha256(launcher),
              "gate_sha256": decision["gate_sha256"], "state": "starting"}
    with open(output / LAUNCH_RECORD, "x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, sort_keys=True)
    env = {**os.environ, "EX42_AUTO_TARGET_STAGE": decision["next_stage_id"],
           "EX42_AUTO_PARENT_MANIFEST": str(parent_manifest), "EX42_AUTO_PARENT_CHECKPOINT": str(parent_checkpoint),
           "EX42_AUTO_GATE_RECEIPT": str(gate_receipt), "EX42_AUTO_GATE_SHA256": decision["gate_sha256"]}
    with open(output / "next_stage_launcher.log", "ab") as log:
        child = popen([str(launcher)], env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                      start_new_session=True)
    record.update(state="started", pid=child.pid)
    (output / LAUNCH_RECORD).write_text(json.dumps(record, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return record
