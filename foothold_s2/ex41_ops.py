"""Local EX-41 boundary reports and durable alert receipts.

This module never sends notifications.  It writes reviewable artifacts beside
the training run so an approved consumer can deliver them later.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _score_snapshot(runtime, completed_update: int) -> tuple[dict | None, str]:
    rows = [row for row in getattr(runtime, "_history", [])
            if type(row.get("iteration")) is int
            and completed_update - 250 < row["iteration"] <= completed_update]
    if not rows:
        return None, "tool_hold"
    score = max(rows, key=lambda row: row["iteration"])
    metrics = score.get("metrics")
    counts = metrics.get("record_counts") if isinstance(metrics, dict) else None
    if not isinstance(counts, dict) or len(counts) != 39:
        return score, "tool_hold"
    for value in counts.values():
        if (not isinstance(value, dict) or type(value.get("passed")) is not int
                or type(value.get("baseline_passed")) is not int or value.get("total") != 64):
            return score, "tool_hold"
    failed = []
    maint = metrics.get("maintenance_counts")
    baseline = getattr(runtime, "baseline", None)
    if isinstance(maint, dict) and isinstance(baseline, dict):
        for key, base in baseline.items():
            row = maint.get(key)
            if not isinstance(row, dict) or type(row.get("passed")) is not int:
                return score, "tool_hold"
            if row["passed"] < base - 3:
                failed.append(key)
    return score, "performance_hold" if failed else "clear"


def _alert(path: Path, event_id: str, kind: str, update: int, details: dict) -> None:
    rows = _jsonl(path)
    if any(row.get("event_id") == event_id for row in rows):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"format": "foothold-ex41-alert/1", "event_id": event_id,
                                 "kind": kind, "iteration": update, **details},
                                ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()


def record_boundary(runtime, run_dir: str | Path, next_update: int) -> dict | None:
    """Write a 250-update or stage-end report after the runtime boundary hook.

    ``next_update`` is the local one-based rollout about to start, so the last
    completed checkpoint is ``next_update - 1``.
    """
    if type(next_update) is not int or next_update < 1:
        raise ValueError("EX-41 next update must be a positive integer")
    completed = next_update - 1
    receipt = runtime.boundary_receipt()
    current_receipt = (isinstance(receipt, dict)
                       and receipt.get("iteration") == next_update)
    changed_stage = (current_receipt
                     and receipt.get("stage_before") != receipt.get("stage_after"))
    at_250 = completed > 0 and completed % 250 == 0
    rejected = current_receipt and receipt.get("status") == "rejected"
    if not (at_250 or changed_stage or rejected or getattr(runtime, "finished", False)):
        return None

    run = Path(run_dir)
    report_path = run / "ex41_reports" / f"update_{completed:05d}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    prior = _jsonl(run / "ex41_reports" / "progress.jsonl")
    event_id = hashlib.sha256(f"ex41-boundary:{completed}".encode()).hexdigest()
    for row in prior:
        if row.get("event_id") == event_id:
            return row

    score, hold_kind = _score_snapshot(runtime, completed)
    metrics = score.get("metrics", {}) if isinstance(score, dict) else {}
    counts = metrics.get("record_counts") if isinstance(metrics, dict) else None
    receipt = receipt if current_receipt else {}
    rejected_scores = [
        {"iteration": value.get("iteration"), "reason": value.get("reason")}
        for value in getattr(runtime, "_score_rejections", {}).values()
        if isinstance(value, dict) and completed - 250 < value.get("iteration", -1) <= completed
    ]
    clock = getattr(runtime, "clock", None)
    report = {
        "format": "foothold-ex41-progress/1", "event_id": event_id,
        "checkpoint_iteration": completed,
        "checkpoint_sha256": (score or {}).get("checkpoint_sha256"),
        "score_iteration": (score or {}).get("iteration"),
        "score_sha256": (score or {}).get("_sha256"),
        "score_state": hold_kind,
        "score_rejections": rejected_scores,
        "maintenance_counts": counts if isinstance(counts, dict) and len(counts) == 39 else None,
        "stage_before": receipt.get("stage_before"), "stage_after": receipt.get("stage_after"),
        "boundary_status": receipt.get("status", "no_boundary_receipt"),
        "boundary_iteration": receipt.get("iteration"),
        "boundary_reason": receipt.get("reason"),
        "decisions": receipt.get("decisions", []),
        "dr_scale": (runtime.dr_scale(next_update) if callable(getattr(runtime, "dr_scale", None)) else None),
        "dr_hold": bool(getattr(clock, "paused", False)),
        "extension_updates": getattr(clock, "extension", None),
        "stand_min_passed": metrics.get("stand_min_passed") if isinstance(metrics, dict) else None,
        "finished": bool(getattr(runtime, "finished", False)),
        "graduated": bool(getattr(runtime, "graduated", False)),
        "requires_review": bool(getattr(runtime, "finished", False)),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                      indent=2, allow_nan=False) + "\n", encoding="utf-8")
    progress = run / "ex41_reports" / "progress.jsonl"
    with progress.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                allow_nan=False) + "\n")
        stream.flush()

    alert_path = run / "ex41_reports" / "alerts.jsonl"
    if rejected:
        reason = str(receipt.get("reason", "boundary rejected"))
        _alert(alert_path, f"boundary-rejected:{completed}:{event_id}",
               "boundary_or_approval_rejected", completed,
               {"reason": reason, "boundary_event_id": receipt.get("event_id")})
    auto = [row for row in report["decisions"] if isinstance(row, dict) and row.get("automatic")]
    if auto:
        _alert(alert_path, f"automatic-adjustment:{completed}:{event_id}",
               "automatic_adjustment", completed, {"decisions": auto})
    if completed >= 250 and hold_kind in ("tool_hold", "performance_hold"):
        consecutive = 1
        previous_kind = None
        for row in reversed(prior):
            if row.get("checkpoint_iteration", 0) != completed - 250 * consecutive:
                break
            if row.get("score_state") not in ("tool_hold", "performance_hold"):
                break
            previous_kind = row["score_state"]
            consecutive += 1
        if consecutive >= 2:
            _alert(alert_path, f"consecutive-hold:{completed}:{event_id}",
                   "two_consecutive_holds", completed,
                   {"hold_kinds": [previous_kind, hold_kind],
                    "first_hold_kind": previous_kind,
                    "latest_hold_kind": hold_kind,
                    "operator_review_required": True})
    return report

