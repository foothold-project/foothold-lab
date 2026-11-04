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
    run_nonfatal_reporting,
)


class FakeRuntime:
    def __init__(self, score=None, receipt=None, *, paused=False, extension=0):
        self._history = [] if score is None else [score]
        self._receipt = receipt
        self._score_rejections = {}
        self.finished = False
        self.graduated = False
        self.clock = type("Clock", (), {"paused": paused, "extension": extension})()
        self.plan = SimpleNamespace(automatic={'critic_both_fail_fraction': .8})

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
                        "training_knee_effort": {'left': .1, 'right': .2},
                        "stand_min_passed": 64}}


def _p3(symmetry):
    from foothold_s2.curriculum.ex41_symmetry import MAP_PAIRS, MODES, pair, combine
    map_rows = {mode: {f'map64/{name}': pair(symmetry if name == 'side' else 1., 1.)
                       for name in MAP_PAIRS} for mode in MODES}
    w78 = {f'L{level}_a{angle:03d}_{mode}_{kind}': {
        'left': symmetry if kind == 'pyramid_stairs' else 1., 'right': 1.,
        'min_lr_ratio': symmetry if kind == 'pyramid_stairs' else 1.}
        for level in (2, 5) for angle in (0, 30, 60, 90) for mode in MODES
        for kind in ('pyramid_stairs', 'pyramid_stairs_inv')}
    return combine(map_rows, w78)


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


def test_boundary_records_exact_use_gt_fraction_and_t0_prime_display_flag(tmp_path):
    runtime = FakeRuntime(_score(250))
    runtime.clock.position = lambda update: 0
    runtime.plan.stages = [SimpleNamespace(id="T0_prime")]
    (tmp_path / "train_extra.jsonl").write_text(
        json.dumps({"it": 499, "use_gt_frac": 0.99}) + "\n"
        + json.dumps({"it": 500, "use_gt_frac": 0.29}) + "\n",
        encoding="utf-8")
    report = record_boundary(runtime, tmp_path, 501)
    assert report["use_gt_frac"] == 0.29
    assert report["use_gt_frac_source"] == "train_extra.jsonl:it=500"
    assert report["stage_for_completed_update"] == "T0_prime"
    assert report["use_gt_frac_t0_prime_threshold"] == 0.3
    assert report["use_gt_frac_t0_prime_le_0p3"] is True
    alerts = [json.loads(line) for line in
              (tmp_path / "ex41_reports/alerts.jsonl").read_text().splitlines()]
    numeric = next(row for row in alerts if row["kind"] == "periodic_250_numeric_report")
    assert numeric["use_gt_frac"] == 0.29
    assert numeric["use_gt_frac_t0_prime_le_0p3"] is True


def test_boundary_does_not_fallback_to_stale_use_gt_fraction(tmp_path):
    runtime = FakeRuntime(_score(250))
    runtime.clock.position = lambda update: 0
    runtime.plan.stages = [SimpleNamespace(id="T0_prime")]
    (tmp_path / "train_extra.jsonl").write_text(
        json.dumps({"it": 499, "use_gt_frac": 0.1}) + "\n", encoding="utf-8")
    report = record_boundary(runtime, tmp_path, 501)
    assert report["use_gt_frac"] is None
    assert report["use_gt_frac_source"] is None
    assert report["use_gt_frac_t0_prime_le_0p3"] is None


def test_250_numeric_report_and_two_adjacent_low_p3_boundaries_are_durable_and_delivered(tmp_path):
    sent = {'orca': [], 'telegram': []}
    def deliver(run):
        return deliver_pending_alerts(
            run,
            orchestration_sender=lambda subject, body: sent['orca'].append((subject, body)) or True,
            telegram_sender=lambda body: sent['telegram'].append(body) or True)

    first = _score(250)
    first['metrics']['critic_mirror_symmetry'] = _p3(.7)
    # Boundary m500 observes the exact m250 score, one score lag behind.
    report1 = record_boundary(FakeRuntime(first), tmp_path, 501, deliver=deliver)
    assert report1['p3_state'] == 'complete'
    assert report1['score_checkpoint_update'] == 250
    assert len(report1['maintenance_counts']) == 39
    assert report1['p3_low_pair_ids']

    second = _score(500)
    second['metrics']['critic_mirror_symmetry'] = _p3(.75)
    report2 = record_boundary(FakeRuntime(second), tmp_path, 751, deliver=deliver)
    assert report2['p3_state'] == 'complete'
    assert report2['score_checkpoint_update'] == 500
    alerts = [json.loads(line) for line in (tmp_path/'ex41_reports/alerts.jsonl').read_text().splitlines()]
    numeric = [row for row in alerts if row['kind'] == 'periodic_250_numeric_report']
    repeated = [row for row in alerts if row['kind'] == 'two_consecutive_p3_boundaries_below_threshold']
    assert len(numeric) == 2 and all(len(row['numeric_cells']) == 39 for row in numeric)
    assert len(repeated) == 1 and repeated[0]['matching_pair_ids']
    assert repeated[0]['automatic_activation'] is False
    assert len(sent['orca']) == len(sent['telegram']) == 3
    assert '250-update numeric report' in sent['orca'][0][0]
    assert 'P3 eval_gt S' in sent['telegram'][0]
    assert '/64' in sent['telegram'][0]


def test_missing_p3_then_complete_p3_boundary_is_a_hold_not_a_type_error(tmp_path):
    first = _score(250)
    first['metrics']['critic_mirror_symmetry'] = None
    report1 = record_boundary(FakeRuntime(first), tmp_path, 501)
    assert report1['p3_state'] == 'missing'
    assert report1['p3_low_pair_ids'] is None

    second = _score(500)
    second['metrics']['critic_mirror_symmetry'] = _p3(.7)
    report2 = record_boundary(FakeRuntime(second), tmp_path, 751)
    assert report2['p3_state'] == 'complete'
    assert report2['p3_low_pair_ids']
    alerts = [json.loads(line) for line in
              (tmp_path / 'ex41_reports/alerts.jsonl').read_text().splitlines()]
    repeated = [row for row in alerts
                if row['kind'] == 'two_consecutive_p3_boundaries_below_threshold']
    assert repeated == []


def test_reporting_failure_is_alerted_but_guard_removed_counterexample_raises(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ex41_ops, 'deliver_pending_alerts', lambda *_args, **_kwargs: [])
    runtime = FakeRuntime(_score(), {"status": "applied", "iteration": 251,
                                     "stage_before": "S2a", "stage_after": "S2a"})
    monkeypatch.setattr(ex41_ops, '_score_snapshot',
                        lambda *_args: (_ for _ in ()).throw(RuntimeError('report writer failed')))
    def broken_report():
        return record_boundary(runtime, tmp_path, 251)

    # Mutation counterexample: without the loop's reporting guard the same
    # observational failure escapes into the training loop.
    import pytest
    with pytest.raises(RuntimeError, match='report writer failed'):
        broken_report()

    assert run_nonfatal_reporting(tmp_path, 500, 'record_boundary', broken_report) is None
    out = json.loads(capsys.readouterr().out)
    assert out['event'] == 'EX41_NONFATAL_REPORTING_FAILURE'
    assert out['phase'] == 'record_boundary'
    assert out['error_type'] == 'RuntimeError'
    alerts = [json.loads(line) for line in
              (tmp_path / 'ex41_reports/alerts.jsonl').read_text().splitlines()]
    assert alerts[-1]['kind'] == 'nonfatal_reporting_failure'
    assert alerts[-1]['training_continues'] is True


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
    assert len([row for row in alerts if row['kind'] == 'two_consecutive_holds']) == 1
    assert len([row for row in alerts if row['kind'] == 'periodic_250_numeric_report']) == 2
    record_boundary(second, tmp_path, 501)
    assert len(alert_path.read_text().splitlines()) == 3
    assert len(delivered["orchestration"]) == len(delivered["telegram"]) == 3


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


def test_rehearsal_process_failure_is_local_only_even_if_delivery_is_retried(tmp_path):
    run = tmp_path / "rehearsal"
    row = record_failure_alert(run, "nonzero_process_exit", 0, {"rc": 1},
                               deliver=True, local_only=True)
    sent = []
    receipts = deliver_pending_alerts(
        run,
        orchestration_sender=lambda *args: sent.append(("orca", args)) or True,
        telegram_sender=lambda *args: sent.append(("telegram", args)) or True,
    )
    assert row["delivery_policy"] == "local_only"
    assert receipts == []
    assert sent == []


def test_failure_event_id_is_scoped_to_run_directory(tmp_path):
    first = record_failure_alert(tmp_path / "run-1", "nonzero_process_exit", 0, {"rc": 1},
                                 deliver=False, local_only=True)
    second = record_failure_alert(tmp_path / "run-2", "nonzero_process_exit", 0, {"rc": 1},
                                  deliver=False, local_only=True)
    assert first["event_id"] != second["event_id"]


def test_external_sender_defaults_fail_closed(monkeypatch):
    called = []
    monkeypatch.delenv("EX41_ALLOW_EXTERNAL_ALERT_DELIVERY", raising=False)
    monkeypatch.setenv("EX41_ORCHESTRATION_TO", "term_fixture-only")
    monkeypatch.setattr(ex41_ops.subprocess, "run", lambda *args, **kwargs: called.append(args))
    assert ex41_ops._send_orchestration("subject", "body") is False
    assert ex41_ops._send_telegram("body") is False
    assert called == []


def test_delivery_layer_suppresses_default_senders_without_opt_in(tmp_path, monkeypatch):
    run = tmp_path / "run"
    record_failure_alert(run, "nonzero_process_exit", 0, {"rc": 1}, deliver=False)
    monkeypatch.setenv("EX41_ALLOW_EXTERNAL_ALERT_DELIVERY", "0")
    receipts = deliver_pending_alerts(run)
    assert len(receipts) == 1
    assert receipts[0]["channels"] == {
        "orchestration": {"state": "suppressed", "reason": "external_delivery_not_enabled"},
        "telegram": {"state": "suppressed", "reason": "external_delivery_not_enabled"},
    }


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
    monkeypatch.setenv("EX41_ALLOW_EXTERNAL_ALERT_DELIVERY", "1")
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
