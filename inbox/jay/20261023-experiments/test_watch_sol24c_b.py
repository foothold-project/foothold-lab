"""Known-input CPU tests for the temporary SOL24c B watcher."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).with_name("watch_sol24c_b.py")
spec = importlib.util.spec_from_file_location("watch_sol24c_b_test", MODULE_PATH)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
NOW = watch.epoch("2026-10-24T08:00:00+09:00")


def iso(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def case(tmp_path):
    config = {
        "schema": watch.SCHEMA, "deadline": watch.DEADLINE,
        "run_name": "ex28-b-main", "target_updates": 1501,
        "process_file": str(tmp_path / "source_process/process.json"),
        "manifest_file": str(tmp_path / "source_manifest/manifest.json"),
        "state_file": str(tmp_path / "runtime/state.json"),
        "target": "term_d0d6549f-2da1-433c-9d05-58ce534224d7",
        "sender_python": sys.executable, "sender_cwd": str(tmp_path),
        "poll_s": 30, "max_heartbeat_age_s": 120,
    }
    assert watch.validate_config(config) == watch.epoch(watch.DEADLINE)
    set_process(config, now=NOW)
    set_manifest(config, completed=0)
    return config, watch.load_state(config)


def set_process(config, *, now=NOW, mode="running", rc=None):
    value = {"started_at": iso(NOW - 100), "supervisor_pid": 11,
             "state": mode, "heartbeat_at": iso(now), "child_pid": 22}
    if mode == "exited":
        value.update(returncode=rc, ended_at=iso(now))
    if mode == "supervisor_error":
        value.update(error="CPU fixture", ended_at=iso(now))
    write(Path(config["process_file"]), value)


def set_manifest(config, *, completed):
    write(Path(config["manifest_file"]), {
        "schema": "foothold-manifest/1", "run": {"name": "ex28-b-main"},
        "progress": {"completed_updates": completed},
    })


def test_five_boundaries_exact_and_durable_no_duplicate(case):
    config, state = case
    sent = []
    set_manifest(config, completed=99)
    watch.tick(config, state, NOW, lambda text: sent.append(text) or 0)
    assert sent == []
    for boundary in watch.BOUNDARIES:
        set_manifest(config, completed=boundary)
        set_process(config, now=NOW + boundary)
        watch.tick(config, state, NOW + boundary, lambda text: sent.append(text) or 0)
        assert len(sent) == watch.BOUNDARIES.index(boundary) + 1
        reloaded = watch.load_state(config)
        watch.tick(config, reloaded, NOW + boundary,
                   lambda text: sent.append(text) or 0)
        assert len(sent) == watch.BOUNDARIES.index(boundary) + 1
        state = reloaded
    assert [state["events"][f"update_{n}"]["status"] for n in watch.BOUNDARIES] == ["sent"] * 5
    assert all("중간 분석 요청" in line for line in sent)


def test_stale_heartbeat_holds_manifest_boundary(case):
    config, state = case
    set_manifest(config, completed=100)
    set_process(config, now=NOW - 500)
    sent = []
    watch.tick(config, state, NOW, lambda text: sent.append(text) or 0)
    assert sent == [] and "supervisor_heartbeat_stale_or_future" in state["mismatch"]
    assert state["last_seen_completed"] == 0
    set_process(config, now=NOW + 1)
    watch.tick(config, state, NOW + 1, lambda text: sent.append(text) or 0)
    assert len(sent) == 1 and state["events"]["update_100"]["status"] == "sent"


def test_progress_regression_holds_queued_deferred_boundary(case):
    config, state = case
    set_manifest(config, completed=200)
    watch.tick(config, state, NOW, lambda _text: 4)
    assert state["events"]["update_100"]["status"] == "deferred"
    assert state["events"]["update_200"]["status"] == "pending"
    set_manifest(config, completed=100)
    set_process(config, now=NOW + 1)
    sent = []
    watch.tick(config, state, NOW + 1, lambda text: sent.append(text) or 0)
    assert sent == [] and "manifest_progress_regressed" in state["mismatch"]
    assert state["events"]["update_100"]["status"] == "deferred"
    assert state["events"]["update_200"]["status"] == "pending"


def test_changed_process_identity_blocks_manifest_boundary(case):
    config, state = case
    watch.tick(config, state, NOW, lambda _text: 0)
    set_manifest(config, completed=100)
    process = watch.read_json(Path(config["process_file"]))
    process["started_at"] = iso(NOW + 1)
    process["heartbeat_at"] = iso(NOW + 1)
    write(Path(config["process_file"]), process)
    sent = []
    watch.tick(config, state, NOW + 1, lambda text: sent.append(text) or 0)
    assert sent == [] and "process_identity_changed" in state["mismatch"]
    assert "update_100" not in state["events"]


def test_exit_four_retries_but_exit_two_is_uncertain(case):
    config, state = case
    set_manifest(config, completed=100)
    watch.tick(config, state, NOW, lambda _text: 4)
    event = state["events"]["update_100"]
    assert event["status"] == "deferred" and event["attempts"] == 1
    sent = []
    watch.tick(config, state, NOW + 1, lambda text: sent.append(text) or 0)
    assert len(sent) == 1 and event["status"] == "sent" and event["attempts"] == 2
    set_manifest(config, completed=200)
    set_process(config, now=NOW + 2)
    watch.tick(config, state, NOW + 2, lambda _text: 2)
    uncertain = state["events"]["update_200"]
    assert uncertain["status"] == "uncertain" and uncertain["last_exit_code"] == 2
    watch.tick(config, watch.load_state(config), NOW + 3,
               lambda text: sent.append(text) or 0)
    assert len(sent) == 1 and watch.load_state(config)["events"]["update_200"]["status"] == "uncertain"


def test_busy_target_defers_later_ready_boundary_in_same_tick(case):
    config, state = case
    set_manifest(config, completed=200)
    calls = []
    watch.tick(config, state, NOW, lambda text: calls.append(text) or 4)
    assert len(calls) == 1
    assert state["events"]["update_100"]["status"] == "deferred"
    assert state["events"]["update_200"]["status"] == "pending"
    watch.tick(config, state, NOW + 1, lambda text: calls.append(text) or 0)
    assert len(calls) == 3
    assert state["events"]["update_100"]["status"] == "sent"
    assert state["events"]["update_200"]["status"] == "sent"


def test_interrupted_send_intent_is_not_resubmitted(case):
    config, state = case
    state["events"]["update_100"] = {"status": "sending", "text": "CPU fixture",
                                       "created_epoch": NOW, "attempts": 1}
    watch.save_state(config, state)
    reloaded = watch.load_state(config)
    sent = []
    watch.tick(config, reloaded, NOW + 1, lambda text: sent.append(text) or 0)
    assert not sent
    assert reloaded["events"]["update_100"]["status"] == "uncertain"
    assert reloaded["events"]["update_100"]["reason"] == "restart_after_send_intent"


def test_sender_exception_is_not_recorded_as_success(case):
    config, state = case
    set_manifest(config, completed=100)
    def broken(_text):
        raise TimeoutError("CPU fixture")
    watch.tick(config, state, NOW, broken)
    event = state["events"]["update_100"]
    assert event["status"] == "uncertain"
    assert event["reason"] == "sender_exception:TimeoutError"


@pytest.mark.parametrize("rc,kind", [(0, "terminal_end"), (7, "terminal_failure")])
def test_natural_exit_and_failure_each_alert_once(case, rc, kind):
    config, state = case
    set_manifest(config, completed=99)
    set_process(config, mode="exited", rc=rc)
    sent = []
    watch.tick(config, state, NOW, lambda text: sent.append(text) or 0)
    assert len(sent) == 1 and kind in state["events"]
    assert state["events"][kind]["status"] == "sent"
    watch.tick(config, watch.load_state(config), NOW + 1,
               lambda text: sent.append(text) or 0)
    assert len(sent) == 1
    assert str(rc) in sent[0]


def test_supervisor_failure_reports_unknown_child_without_boundary(case):
    config, state = case
    set_manifest(config, completed=100)
    set_process(config, mode="supervisor_error")
    sent = []
    watch.tick(config, state, NOW, lambda text: sent.append(text) or 0)
    assert len(sent) == 1 and "child 상태 미확인" in sent[0]
    assert "supervisor_error_child_state_unverified" in state["mismatch"]
    assert "update_100" not in state["events"]


def test_deferred_terminal_waits_when_process_evidence_disappears(case):
    config, state = case
    set_process(config, mode="exited", rc=7)
    watch.tick(config, state, NOW, lambda _text: 4)
    assert state["events"]["terminal_failure"]["status"] == "deferred"
    Path(config["process_file"]).unlink()
    sent = []
    watch.tick(config, state, NOW + 1, lambda text: sent.append(text) or 0)
    assert sent == [] and "process_unreadable" in state["mismatch"]
    assert state["events"]["terminal_failure"]["status"] == "deferred"


def test_expiry_stops_new_sends_and_owner_lock(case):
    config, state = case
    set_manifest(config, completed=500)
    sent = []
    watch.tick(config, state, watch.epoch(watch.DEADLINE),
               lambda text: sent.append(text) or 0)
    assert state["expired"] is True and not sent and not state["events"]
    lock = Path(config["state_file"]).with_suffix(".json.owner.lock")
    with watch.exclusive_owner(lock):
        with pytest.raises(RuntimeError, match="watcher_already_running"):
            with watch.exclusive_owner(lock):
                pass


def test_cli_sender_uses_exact_mai_resume_command(case, monkeypatch):
    config, _state = case
    seen = []

    class Result:
        returncode = 4

    def fake_run(argv, **kwargs):
        seen.append((argv, kwargs))
        return Result()

    monkeypatch.setattr(watch.subprocess, "run", fake_run)
    assert watch.cli_sender(config, "CPU test") == 4
    argv, kwargs = seen[0]
    assert argv == [sys.executable, "-m", "mai_resume", "send", "--to", config["target"],
                    "--text", "CPU test", "--wait", "15"]
    assert kwargs["cwd"] == config["sender_cwd"] and kwargs["timeout"] == 45
