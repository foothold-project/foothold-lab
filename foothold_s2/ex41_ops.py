"""EX-41 boundary reports and durable local plus delivered alert receipts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
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
    expected_iteration = completed_update - 250
    rows = [row for row in getattr(runtime, "_history", [])
            if type(row.get("iteration")) is int
            and row["iteration"] == expected_iteration]
    if expected_iteration < 1 or not rows:
        return None, "tool_hold"
    score = rows[-1]
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


def _alert(path: Path, event_id: str, kind: str, update: int, details: dict) -> dict | None:
    rows = _jsonl(path)
    if any(row.get("event_id") == event_id for row in rows):
        return None
    row = {"format": "foothold-ex41-alert/1", "event_id": event_id,
           "kind": kind, "iteration": update, **details}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row,
                                ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
    return row


def _notification_text(row: dict[str, Any]) -> tuple[str, str]:
    kind = str(row.get("kind", "EX-41 alert"))
    iteration = row.get("iteration", "unknown")
    event_id = str(row.get("event_id", "unknown"))
    if kind == "notification_test":
        return ("EX-41 notification path test",
                f"Test only, no training incident. Event {event_id}.")
    if kind == "stage_end_auxiliary_report":
        p3_state = row.get("p3_state", "unknown")
        metrics = row.get("p3_metrics")
        metrics_state = "recorded" if isinstance(metrics, dict) else "missing"
        return (f"EX-41 stage-end report {row.get('stage_id', 'unknown')} m{iteration}",
                f"Stage-end W57/W78 report has P3 state {p3_state}; P3 metrics {metrics_state}. "
                f"Checkpoint SHA: {row.get('checkpoint_sha256', 'unknown')}. "
                f"Report: {row.get('report_path', 'see run ex41_reports')}. Event {event_id}.")
    if kind == "periodic_250_numeric_report":
        cells = row.get('numeric_cells')
        if isinstance(cells, list):
            cell_text = "; ".join(
                f"{item.get('cell')}={item.get('passed')}/{item.get('baseline_passed')}"
                f"({item.get('delta')})/{item.get('total')}"
                for item in cells)
        else:
            cell_text = "39-cell table unavailable"
        pairs = row.get('p3_s_eval_gt')
        if isinstance(pairs, dict):
            p3_text = "; ".join(f"{key}={value}" for key, value in pairs.items())
        else:
            p3_text = "P3 S unavailable"
        return (f"EX-41 250-update numeric report m{iteration}",
                f"state={row.get('report_state')}; cells: {cell_text}; P3 eval_gt S: {p3_text}; "
                f"DR={row.get('dr_scale')}; training={json.dumps(row.get('training_metrics'), ensure_ascii=False, separators=(',', ':'))}; "
                f"checkpoint={row.get('score_checkpoint_update')} SHA={row.get('score_checkpoint_sha256')}; "
                f"report={row.get('report_path')}; event={event_id}")
    if kind == "two_consecutive_p3_boundaries_below_threshold":
        return (f"EX-41 P3 repeated low boundary m{iteration}",
                f"P3 pairs below threshold at two adjacent scored checkpoints: {row.get('matching_pair_ids')}. "
                f"No automatic activation; stage-end review/approval only. Event {event_id}.")
    subject = f"EX-41 alert {kind} m{iteration}"
    body = (f"EX-41 {kind} at update {iteration}. Review required. "
            f"Event {event_id}. Details are in the run's ex41_reports/alerts.jsonl.")
    return subject, body


def _send_orchestration(subject: str, body: str) -> bool:
    command = ["orca", "orchestration", "send", "--type", "status",
               "--subject", subject, "--body", body, "--json"]
    target = os.environ.get("EX41_ORCHESTRATION_TO")
    run_id = os.environ.get("EX41_ORCHESTRATION_RUN_ID")
    if target:
        command.extend(("--to", target))
        if target.startswith("run:") and not run_id:
            run_id = target.split(":", 1)[1]
    elif run_id:
        command.extend(("--run", run_id, "--to", f"run:{run_id}"))
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, encoding="utf-8", errors="replace",
                                timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    try:
        response = json.loads(result.stdout)
    except (TypeError, ValueError):
        return False
    return response.get("ok") is True


def _send_telegram(body: str) -> bool:
    try:
        from foothold_s2.chain.runner import default_tg_sender
        config = {
            "outbox": os.environ.get("EX41_TELEGRAM_OUTBOX", "C:/ssd-cleanup-logs/tg-outbox.txt"),
            "script": os.environ.get("EX41_TELEGRAM_SCRIPT", "C:/ssd-cleanup-logs/tg-send.ps1"),
        }
        return bool(default_tg_sender(config, body))
    except (OSError, subprocess.SubprocessError, ImportError):
        return False


def _write_delivery_receipt(path: Path, receipt: dict[str, Any]) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def deliver_pending_alerts(run_dir: str | Path, *, orchestration_sender=None,
                           telegram_sender=None) -> list[dict[str, Any]]:
    """Deliver durable alert rows through the existing Orca and Telegram paths.

    Senders are injectable for CPU tests. A successful channel is never resent;
    a failed channel remains pending for the next boundary poll.
    """
    report_dir = Path(run_dir) / "ex41_reports"
    alert_path = report_dir / "alerts.jsonl"
    if not alert_path.is_file():
        return []
    receipts_dir = report_dir / "alert_deliveries"
    results = []
    for row in _jsonl(alert_path):
        event_id = str(row.get("event_id", ""))
        if not event_id:
            continue
        receipt_path = receipts_dir / f"{hashlib.sha256(event_id.encode()).hexdigest()}.json"
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            receipt = {"format": "foothold-ex41-alert-delivery/1", "event_id": event_id,
                       "channels": {}}
        subject, body = _notification_text(row)
        for channel, sender, payload in (
            ("orchestration", orchestration_sender or _send_orchestration, (subject, body)),
            ("telegram", telegram_sender or _send_telegram, (body,)),
        ):
            if receipt["channels"].get(channel, {}).get("state") == "sent":
                continue
            try:
                accepted = bool(sender(*payload))
            except Exception as exc:  # noqa: BLE001
                receipt["channels"][channel] = {"state": "pending", "error": type(exc).__name__}
            else:
                receipt["channels"][channel] = {"state": "sent" if accepted else "pending"}
            receipts_dir.mkdir(parents=True, exist_ok=True)
            _write_delivery_receipt(receipt_path, receipt)
        results.append(receipt)
    return results


def record_failure_alert(run_dir: str | Path, kind: str, update: int,
                         details: dict[str, Any], *, deliver: bool = True) -> dict[str, Any]:
    """Record a fatal or nonzero child result without masking the local receipt."""
    if kind not in ("fatal_training_fault", "nonzero_process_exit"):
        raise ValueError("unsupported EX-41 failure alert kind")
    event_id = hashlib.sha256(json.dumps(
        [kind, update, details], sort_keys=True, allow_nan=False).encode()).hexdigest()
    row = _alert(Path(run_dir) / "ex41_reports" / "alerts.jsonl", event_id, kind, update, details)
    if deliver:
        deliver_pending_alerts(run_dir)
    return row or next((r for r in _jsonl(Path(run_dir) / "ex41_reports" / "alerts.jsonl")
                        if r.get("event_id") == event_id), {"event_id": event_id})


def record_deadline_alert(run_dir: str | Path, update: int,
                          details: dict[str, Any], *, deliver: bool = True) -> dict[str, Any]:
    """Publish one durable warning when the estimated END_BY is exceeded."""
    if type(update) is not int or update < 0:
        raise ValueError("END_BY warning update must be a nonnegative integer")
    if details.get("action") != "warning_only" or details.get("training_stop_on_deadline") is not False:
        raise ValueError("END_BY warning must explicitly preserve healthy training")
    event_id = hashlib.sha256(json.dumps(
        ["end_by_warning", update, details], sort_keys=True, allow_nan=False).encode()).hexdigest()
    row = _alert(Path(run_dir) / "ex41_reports" / "alerts.jsonl", event_id,
                 "end_by_warning", update, details)
    if deliver:
        deliver_pending_alerts(run_dir)
    return row or next((r for r in _jsonl(Path(run_dir) / "ex41_reports" / "alerts.jsonl")
                        if r.get("event_id") == event_id), {"event_id": event_id})


def record_boundary(runtime, run_dir: str | Path, next_update: int, *, deliver=None) -> dict | None:
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
        "format": "foothold-ex41-progress/2", "event_id": event_id,
        "boundary_update": completed,
        "boundary_receipt_update": receipt.get("iteration"),
        "score_checkpoint_update": (score or {}).get("iteration"),
        "score_checkpoint_sha256": (score or {}).get("checkpoint_sha256"),
        "score_document_sha256": (score or {}).get("_sha256"),
        "score_expected_update": completed - 250,
        "score_state": hold_kind,
        "score_rejections": rejected_scores,
        "maintenance_counts": counts if isinstance(counts, dict) and len(counts) == 39 else None,
        "p3_symmetry": metrics.get("critic_mirror_symmetry") if isinstance(metrics, dict) else None,
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
    p3_pairs = None
    p3_state = 'missing'
    if at_250:
        p3 = report['p3_symmetry']
        try:
            from foothold_s2.curriculum.ex41_symmetry import validate
            validate(p3)
            p3_pairs = {key: row['symmetry'] for key, row in p3['modes']['eval_gt'].items()}
            p3_state = 'complete' if all(type(value) in (int, float) for value in p3_pairs.values()) else 'partial'
        except (ImportError, ValueError, TypeError, KeyError):
            pass
        threshold = getattr(getattr(runtime, 'plan', None), 'automatic', {}).get(
            'critic_both_fail_fraction', .8)
        report['p3_state'] = p3_state
        report['p3_low_pair_ids'] = (sorted(key for key, value in p3_pairs.items()
                                             if type(value) in (int, float) and value < threshold)
                                     if p3_state == 'complete' else None)
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                      indent=2, allow_nan=False) + "\n", encoding="utf-8")
    progress = run / "ex41_reports" / "progress.jsonl"
    with progress.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                allow_nan=False) + "\n")
        stream.flush()

    alert_path = run / "ex41_reports" / "alerts.jsonl"
    if at_250:
        threshold = getattr(getattr(runtime, 'plan', None), 'automatic', {}).get(
            'critic_both_fail_fraction', .8)
        table = report['maintenance_counts']
        numeric_cells = ([{'cell':key, 'passed':value['passed'],
                           'baseline_passed':value['baseline_passed'],
                           'delta':value['passed'] - value['baseline_passed'],
                           'total':value['total']}
                          for key, value in sorted(table.items())]
                         if isinstance(table, dict) and len(table) == 39 else None)
        training_metrics = metrics.get('training_knee_effort') if isinstance(metrics, dict) else None
        has_dr_scale = type(report['dr_scale']) in (int, float)
        report_state = ('complete' if numeric_cells is not None and p3_state == 'complete'
                        and has_dr_scale and isinstance(training_metrics, dict) else 'incomplete')
        report_event = hashlib.sha256(json.dumps(
            ['periodic-250-numeric-report', completed, report['score_checkpoint_sha256'], report_state],
            sort_keys=True, allow_nan=False).encode()).hexdigest()
        _alert(alert_path, report_event, 'periodic_250_numeric_report', completed, {
            'report_state': report_state, 'numeric_cells': numeric_cells,
            'p3_state': p3_state, 'p3_s_eval_gt': p3_pairs,
            'dr_scale': report['dr_scale'],
            'training_metrics': training_metrics,
            'score_checkpoint_update': report['score_checkpoint_update'],
            'score_checkpoint_sha256': report['score_checkpoint_sha256'],
            'report_path': str(report_path), 'automatic_activation': False,
            'approval_at_stage_end_only': True})
        if report_state == 'complete' and p3_pairs is not None:
            low = sorted(key for key, value in p3_pairs.items()
                         if type(value) in (int, float) and value < threshold)
            previous_row = next((item for item in reversed(prior)
                                 if item.get('boundary_update') == completed - 250), None)
            previous_low = set(previous_row.get('p3_low_pair_ids', [])) if previous_row else set()
            consecutive = bool(previous_row and previous_row.get('p3_state') == 'complete'
                               and previous_row.get('score_checkpoint_update') == report['score_expected_update'] - 250)
            matched = sorted(previous_low.intersection(low)) if consecutive else []
            if matched:
                event_id = hashlib.sha256(json.dumps(
                    ['two-consecutive-p3-boundaries', completed, matched,
                     previous_row.get('score_checkpoint_sha256'), report['score_checkpoint_sha256']],
                    sort_keys=True, allow_nan=False).encode()).hexdigest()
                _alert(alert_path, event_id, 'two_consecutive_p3_boundaries_below_threshold', completed, {
                    'matching_pair_ids': matched, 'threshold': threshold,
                    'previous_boundary_update': previous_row['boundary_update'],
                    'previous_checkpoint_update': previous_row['score_checkpoint_update'],
                    'previous_checkpoint_sha256': previous_row['score_checkpoint_sha256'],
                    'checkpoint_update': report['score_checkpoint_update'],
                    'checkpoint_sha256': report['score_checkpoint_sha256'],
                    'automatic_activation': False, 'approval_at_stage_end_only': True})
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
            if row.get("boundary_update", 0) != completed - 250 * consecutive:
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
    if deliver is not None:
        deliver(run)
    return report

