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


def _continue_decision(plan, approvals_path, stage_id, iteration, base, manifest_path, p1):
    """Same stage, from this boundary's saved checkpoint: allowed only inside the bounds of the stage's own approval
    cell (E1: scope maximum, cell interval) under the scoped automatic policy. No PASS is needed to go on."""
    from foothold_s2.curriculum.ex42_prep import _read_yaml, scoped_automatic_policy, validate_stage_e1_authorization
    if stage_id != "E1":
        return {**base, "action": "notify", "state": "not_ready", "reason": f"{stage_id} has no boundary to continue from"}
    try:
        if not scoped_automatic_policy(_read_yaml(Path(approvals_path)).get("automatic_launch_allowed")):
            raise ValueError("scoped automatic policy is not enabled")
        pin = next(row for row in plan.document["stages"] if row["id"] == stage_id)["parent"]["sha256"]
        proof = validate_stage_e1_authorization(plan, approvals_path, pin)
        bound, interval = proof["scope"]["maximum_updates"], proof["boundary_evaluation_interval_updates"]
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
        name = f"model_{iteration}.pt"
        checkpoint = Path(manifest_path).parent / name
        if (manifest.get("checkpoints", {}).get(name) != p1.get("checkpoint_sha256")
                or _sha256(checkpoint) != p1.get("checkpoint_sha256")
                or manifest.get("progress", {}).get("completed_updates") != iteration):
            raise ValueError("the boundary checkpoint is not the manifest's latest save that was scored")
        if iteration >= bound:
            return {**base, "action": "notify", "state": "stage_bound_reached_not_ready",
                    "reason": f"update {iteration} is the approved bound {bound} and the gate did not pass"}
    except (ValueError, OSError, KeyError, StopIteration, json.JSONDecodeError) as exc:
        return {**base, "action": "notify", "state": "continue_not_authorized",
                "reason": f"not authorized to continue by itself: {exc}"}
    return {**base, "action": "continue", "state": "stage_continues", "target_stage": stage_id,
            "resume_checkpoint": str(checkpoint), "segment_end": min(iteration + interval, bound),
            "authorization": proof}


def decide_next_stage(plan_path, approvals_path, stage_id, iteration, p1_path, manifest_path) -> dict[str, Any] | None:
    """None when this update is not a boundary of the stage. Otherwise a decision for the boundary:
    launch (the gate passed at or after the stage minimum and the next stage has its approved cell), continue (the
    same stage goes on from this save), or notify (anything else, with the reason)."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    plan = plan_path if isinstance(plan_path, EX42Plan) else EX42Plan.load(plan_path)
    stages = plan.document["stages"]
    index = next((i for i, row in enumerate(stages) if row.get("id") == stage_id), None)
    if index is None:
        return None
    minimum = stages[index].get("minimum_updates")
    boundary = iteration == minimum
    if stage_id == "E1" and not boundary:          # the plan's evaluation interval, so a removed cell still gets a notice
        interval = plan.document.get("evaluation", {}).get("interval_updates")
        boundary = type(interval) is int and interval > 0 and 0 < iteration < minimum and iteration % interval == 0
    if not boundary:
        return None
    following = stages[index + 1]["id"] if index + 1 < len(stages) else None
    p1 = json.loads(Path(p1_path).read_text(encoding="utf-8-sig"))
    base = {"stage_id": stage_id, "boundary_iteration": iteration, "judgment": p1.get("judgment"),
            "next_stage_id": following, "checkpoint_sha256": p1.get("checkpoint_sha256"),
            "gate_sha256": _sha256(p1_path)}
    if not (p1.get("judgment") == "PASS" and iteration >= minimum and following is not None):
        if stage_id == "E1":      # not ready (or only a PASS before the stage minimum): the stage goes on from this save
            return _continue_decision(plan, approvals_path, stage_id, iteration, base, manifest_path, p1)
        return {**base, "action": "notify", "state": "not_ready",
                "reason": "no following stage" if following is None else f"gate judgment is {p1.get('judgment')}"}
    try:
        proof = validate_automatic_stage_launch(
            plan, approvals_path, target_stage=following, parent_manifest_path=manifest_path,
            gate_receipt_path=p1_path, expected_gate_sha256=_sha256(p1_path))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        return {**base, "action": "notify", "state": "next_stage_ready_for_approval",
                "reason": f"not authorized to start by itself: {exc}"}
    return {**base, "action": "launch", "state": "next_stage_authorized", "target_stage": following,
            "authorization": proof, "gate_sha256": proof["gate_sha256"]}


def start_launcher(decision, launcher, output, *, parent_manifest, parent_checkpoint, gate_receipt, popen=subprocess.Popen):
    """Run the lead's launcher once for an authorized decision. The record file is created exclusively first, so a
    second evaluation of the same boundary cannot start a second training."""
    launcher = Path(launcher)
    if not launcher.is_absolute() or not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise ValueError("EX-42 next-stage launcher must be an absolute path to an executable file")
    output = Path(output)
    kind = "continue" if decision["action"] == "continue" else "next_stage"
    record = {"format": "foothold-ex42-next-stage-launch/1", "action": kind, "target_stage": decision["target_stage"],
              "launcher": str(launcher), "launcher_sha256": _sha256(launcher),
              "gate_sha256": decision["gate_sha256"], "state": "starting",
              **({"resume_checkpoint": decision["resume_checkpoint"], "segment_end": decision["segment_end"]}
                 if kind == "continue" else {})}
    with open(output / LAUNCH_RECORD, "x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, sort_keys=True)
    env = {**os.environ, "EX42_AUTO_ACTION": kind, "EX42_AUTO_TARGET_STAGE": decision["target_stage"],
           "EX42_AUTO_PARENT_MANIFEST": str(parent_manifest), "EX42_AUTO_PARENT_CHECKPOINT": str(parent_checkpoint),
           "EX42_AUTO_GATE_RECEIPT": str(gate_receipt), "EX42_AUTO_GATE_SHA256": decision["gate_sha256"]}
    if kind == "continue":      # the same stage goes on in the same run directory: resume from this boundary save
        env.update(EX42_AUTO_RESUME_CHECKPOINT=decision["resume_checkpoint"],
                   EX42_AUTO_SEGMENT_END=str(decision["segment_end"]))
    with open(output / "next_stage_launcher.log", "ab") as log:
        child = popen([str(launcher)], env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                      start_new_session=True)
    record.update(state="started", pid=child.pid)
    (output / LAUNCH_RECORD).write_text(json.dumps(record, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return record
