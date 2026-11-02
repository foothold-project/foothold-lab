import json
from types import SimpleNamespace

import foothold_s2.ex41_ops as ex41_ops
from foothold_s2.ex41_ops import (
    _alert,
    _notification_text,
    deliver_pending_alerts,
    record_boundary,
    record_deadline_alert,
    record_failure_alert,
)


class FakeRuntime:
    def __init__(self, score=None, receipt=None, *, paused=False, extension=0):
        self._history = [] if score is None else [score]
        self._receipt = receipt
        self._score_rejections = {}
        self.finished = False
        self.graduated = False
        self.clock = type("Clock", (), {"paused": paused, "extension": extension})()

    def boundary_receipt(self):
        return self._receipt

    def dr_scale(self, _update):
        return 0.5


def test_end_by_alert_uses_existing_receipts_and_deduplicated_delivery(tmp_path):
    row = record_deadline_alert(tmp_path, 250, {
        "end_by": "2026-11-06T00:00:00+00:00",
        "action": "warning_only", "training_stop_on_deadline": False,
    }, deliver=False)
    delivered = []
    first = deliver_pending_alerts(
        tmp_path,
        orchestration_sender=lambda subject, body: delivered.append(("orca", subject)) or True,
        telegram_sender=lambda body: delivered.append(("telegram", body)) or True)
    second = deliver_pending_alerts(
        tmp_path,
        orchestration_sender=lambda *_: delivered.append(("orca_duplicate",)) or True,
        telegram_sender=lambda *_: delivered.append(("telegram_duplicate",)) or True)
    assert row["kind"] == "end_by_warning"
    assert first[0]["channels"]["orchestration"]["state"] == "sent"
    assert first[0]["channels"]["telegram"]["state"] == "sent"
    assert second[0]["channels"]["orchestration"]["state"] == "sent"
    assert len(delivered) == 2


def _score(update=250):
    counts = {f"cell_{i}": {"passed": 64, "baseline_passed": 64, "total": 64}
              for i in range(39)}
    return {"iteration": update, "checkpoint_sha256": "a" * 64, "_sha256": "b" * 64,
            "metrics": {"record_counts": counts, "maintenance_counts": {},
                        "stand_min_passed": 64}}


def test_ex41_boundary_uses_exact_score_250_and_records_dr_hold(tmp_path):
    runtime = FakeRuntime(_score(), {"status": "applied", "stage_before": "S2a",
                                     "stage_after": "S2a", "decisions": []},
                          paused=True, extension=500)
    runtime._history.append(_score(500))
    report = record_boundary(runtime, tmp_path, 501)
    assert report["format"] == "foothold-ex41-progress/2"
    assert report["boundary_update"] == 500
    assert report["score_checkpoint_update"] == report["score_expected_update"] == 250
    assert report["score_checkpoint_sha256"] == "a" * 64
    assert report["score_document_sha256"] == "b" * 64
    assert report["boundary_update"] != report["score_checkpoint_update"]
    assert len(report["maintenance_counts"]) == 39
    assert report["dr_hold"] is True and report["extension_updates"] == 500
    assert json.loads((tmp_path / "ex41_reports/update_00500.json").read_text()) == report


def test_ex41_boundary_keeps_dr_when_exact_reference_score_is_missing(tmp_path):
    runtime = FakeRuntime(_score(750))
    report = record_boundary(runtime, tmp_path, 751)
    assert report["boundary_update"] == 750
    assert report["score_expected_update"] == 500
    assert report["score_checkpoint_update"] is None
    assert report["score_checkpoint_sha256"] is None
    assert report["score_document_sha256"] is None
    assert report["score_state"] == "tool_hold"
    assert report["dr_scale"] == 0.5
    assert report["finished"] is False


def test_two_consecutive_tool_holds_make_one_durable_alert_and_dedupe(tmp_path):
    delivered = {"orchestration": [], "telegram": []}
    def deliver(run):
        return deliver_pending_alerts(
            run,
            orchestration_sender=lambda subject, body: delivered["orchestration"].append((subject, body)) or True,
            telegram_sender=lambda body: delivered["telegram"].append(body) or True,
        )
    first = FakeRuntime()
    assert record_boundary(first, tmp_path, 251, deliver=deliver)["score_state"] == "tool_hold"
    second = FakeRuntime()
    report = record_boundary(second, tmp_path, 501, deliver=deliver)
    assert report["score_state"] == "tool_hold"
    alert_path = tmp_path / "ex41_reports/alerts.jsonl"
    alerts = [json.loads(line) for line in alert_path.read_text().splitlines()]
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "two_consecutive_holds"
    record_boundary(second, tmp_path, 501)
    assert len(alert_path.read_text().splitlines()) == 1
    assert len(delivered["orchestration"]) == len(delivered["telegram"]) == 1


def test_rejected_boundary_and_automatic_change_have_local_alert_receipts(tmp_path):
    runtime = FakeRuntime(_score(), {"status": "rejected", "iteration": 252, "event_id": "reject-1",
                                    "stage_before": "S2a", "stage_after": "S2a",
                                    "reason": "approval mismatch",
                                    "decisions": [{"automatic": True, "path": "reward_weights.swing"}]})
    record_boundary(runtime, tmp_path, 252)
    alerts = [json.loads(line) for line in
              (tmp_path / "ex41_reports/alerts.jsonl").read_text().splitlines()]
    assert {row["kind"] for row in alerts} == {"boundary_or_approval_rejected", "automatic_adjustment"}


def test_alerts_reach_both_channels_once_and_retry_only_failed_channel(tmp_path):
    run = tmp_path / "run"
    sent = {"orchestration": [], "telegram": []}
    def orca(subject, body):
        sent["orchestration"].append((subject, body))
        return True
    def telegram(body):
        sent["telegram"].append(body)
        return len(sent["telegram"]) > 1

    record_failure_alert(run, "nonzero_process_exit", 500, {"rc": 7}, deliver=False)
    first = deliver_pending_alerts(run, orchestration_sender=orca, telegram_sender=telegram)
    assert first[0]["channels"]["orchestration"]["state"] == "sent"
    assert first[0]["channels"]["telegram"]["state"] == "pending"
    second = deliver_pending_alerts(run, orchestration_sender=orca, telegram_sender=telegram)
    assert second[0]["channels"]["orchestration"]["state"] == "sent"
    assert second[0]["channels"]["telegram"]["state"] == "sent"
    assert len(sent["orchestration"]) == 1 and len(sent["telegram"]) == 2


def test_fatal_alert_has_durable_receipt_without_printing_sender_data(tmp_path):
    run = tmp_path / "run"
    row = record_failure_alert(run, "fatal_training_fault", 750, {"fault": "bad update"},
                               deliver=False)
    assert row["kind"] == "fatal_training_fault"
    sent = deliver_pending_alerts(run, orchestration_sender=lambda *_: True,
                                  telegram_sender=lambda *_: True)
    assert sent[0]["channels"] == {"orchestration": {"state": "sent"},
                                    "telegram": {"state": "sent"}}


def test_answer_known_notification_test_is_not_worded_as_incident(tmp_path):
    row = _alert(tmp_path / "ex41_reports/alerts.jsonl", "delivery-test", "notification_test", 0, {})
    assert _notification_text(row) == (
        "EX-41 notification path test", "Test only, no training incident. Event delivery-test.")


def test_orchestration_sender_requires_json_acceptance(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"ok": false}', stderr="")
    monkeypatch.setattr(ex41_ops.subprocess, "run", run)
    monkeypatch.setenv("EX41_ORCHESTRATION_RUN_ID", "run_known-test")
    monkeypatch.setenv("EX41_ORCHESTRATION_TO", "term_known-recipient")
    assert ex41_ops._send_orchestration("subject", "body") is False
    command, kwargs = calls[-1]
    assert "--json" in command
    assert "--to" in command and "term_known-recipient" in command
    assert kwargs["stdin"] is ex41_ops.subprocess.DEVNULL

    def accepted(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")
    monkeypatch.setattr(ex41_ops.subprocess, "run", accepted)
    assert ex41_ops._send_orchestration("subject", "body") is True


def test_non_boundary_update_is_not_reported(tmp_path):
    runtime = FakeRuntime()
    assert record_boundary(runtime, tmp_path, 252) is None
    assert not (tmp_path / "ex41_reports").exists()


def test_stale_rejected_boundary_does_not_emit_repeated_reports(tmp_path):
    runtime = FakeRuntime(receipt={"status": "rejected", "iteration": 251,
                                   "stage_before": "S2a", "stage_after": "S2a"})
    assert record_boundary(runtime, tmp_path, 252) is None
    assert not (tmp_path / "ex41_reports").exists()
