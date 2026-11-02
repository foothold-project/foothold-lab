import json

from foothold_s2.ex41_ops import record_boundary


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


def _score(update=250):
    counts = {f"cell_{i}": {"passed": 64, "baseline_passed": 64, "total": 64}
              for i in range(39)}
    return {"iteration": update, "checkpoint_sha256": "a" * 64, "_sha256": "b" * 64,
            "metrics": {"record_counts": counts, "maintenance_counts": {},
                        "stand_min_passed": 64}}


def test_ex41_250_report_includes_39_cells_dr_hold_and_extension(tmp_path):
    runtime = FakeRuntime(_score(), {"status": "applied", "stage_before": "S2a",
                                     "stage_after": "S2a", "decisions": []},
                          paused=True, extension=500)
    report = record_boundary(runtime, tmp_path, 251)
    assert report["checkpoint_iteration"] == 250
    assert len(report["maintenance_counts"]) == 39
    assert report["dr_hold"] is True and report["extension_updates"] == 500
    assert json.loads((tmp_path / "ex41_reports/update_00250.json").read_text()) == report


def test_two_consecutive_tool_holds_make_one_durable_alert_and_dedupe(tmp_path):
    first = FakeRuntime()
    assert record_boundary(first, tmp_path, 251)["score_state"] == "tool_hold"
    second = FakeRuntime()
    report = record_boundary(second, tmp_path, 501)
    assert report["score_state"] == "tool_hold"
    alert_path = tmp_path / "ex41_reports/alerts.jsonl"
    alerts = [json.loads(line) for line in alert_path.read_text().splitlines()]
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "two_consecutive_holds"
    record_boundary(second, tmp_path, 501)
    assert len(alert_path.read_text().splitlines()) == 1


def test_rejected_boundary_and_automatic_change_have_local_alert_receipts(tmp_path):
    runtime = FakeRuntime(_score(), {"status": "rejected", "iteration": 252, "event_id": "reject-1",
                                    "stage_before": "S2a", "stage_after": "S2a",
                                    "reason": "approval mismatch",
                                    "decisions": [{"automatic": True, "path": "reward_weights.swing"}]})
    record_boundary(runtime, tmp_path, 252)
    alerts = [json.loads(line) for line in
              (tmp_path / "ex41_reports/alerts.jsonl").read_text().splitlines()]
    assert {row["kind"] for row in alerts} == {"boundary_or_approval_rejected", "automatic_adjustment"}


def test_non_boundary_update_is_not_reported(tmp_path):
    runtime = FakeRuntime()
    assert record_boundary(runtime, tmp_path, 252) is None
    assert not (tmp_path / "ex41_reports").exists()


def test_stale_rejected_boundary_does_not_emit_repeated_reports(tmp_path):
    runtime = FakeRuntime(receipt={"status": "rejected", "iteration": 251,
                                   "stage_before": "S2a", "stage_after": "S2a"})
    assert record_boundary(runtime, tmp_path, 252) is None
    assert not (tmp_path / "ex41_reports").exists()
