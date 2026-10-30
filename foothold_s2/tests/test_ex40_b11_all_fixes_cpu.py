"""Known-input regressions for the six EX-40 B11 blockers."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2.curriculum.continuous import KIT_SMOKE_BOUNDARIES, Plan
from foothold_s2.curriculum.ex40_dr import KIT_SMOKE_SCHEDULE_UPDATES, dr_scale, smoke_schedule_update
from foothold_s2.curriculum.ex40_dr_runtime import validate_runtime_summary
from foothold_s2.ex40_kit_smoke import BASELINE, _check_events
from foothold_s2.ex40_launch import TABLE
from foothold_s2.ex40_supervisor import _score_until_checkpoint, transition
from foothold_s2.tests.test_ex40_v7_continue_cpu import _known_checkpoint


def _event_contract(plan: Plan) -> dict:
    ranges = plan.domain_randomization["full_ranges"]
    return {
        "ex40_base_com": {"func": "foothold_s2.curriculum.ex40_dr_runtime.reset_base_com",
            "mode": "reset", "params": {"asset_cfg": {"name": "robot", "body_names": "base"},
                "target_range": ranges["base_com"]}},
        "ex40_actuator_gains": {"func": "foothold_s2.curriculum.ex40_dr_runtime.reset_actuator_gains",
            "mode": "reset", "params": {"asset_cfg": {"name": "robot", "joint_names": ".*"},
                "target_range": ranges["actuator_gains"]}},
        "ex40_motor_strength": {"func": "foothold_s2.curriculum.ex40_dr_runtime.reset_motor_strength",
            "mode": "reset", "params": {"asset_cfg": {"name": "robot", "joint_names": ".*"},
                "target_range": ranges["motor_strength"]}},
        "ex40_push": {"func": "foothold_s2.curriculum.ex40_dr_runtime.interval_push",
            "mode": "interval", "interval_range_s": plan.domain_randomization["push_interval_s"],
            "params": {"asset_cfg": {"name": "robot"}, "target_range": ranges["push_velocity"]}},
    }


def test_event_checker_preserves_baseline_and_accepts_four_serialized_dr_terms():
    plan = Plan(TABLE, arm="B")
    baseline = yaml.load((BASELINE / "env.yaml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)["events"]
    actual = {**copy.deepcopy(baseline), **_event_contract(plan)}
    _check_events(actual, baseline, plan)
    del actual["ex40_base_com"]
    with pytest.raises(ValueError, match="event set"):
        _check_events(actual, baseline, plan)


def test_event_checker_rejects_changed_s_b10_event():
    plan = Plan(TABLE, arm="B")
    baseline = yaml.load((BASELINE / "env.yaml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)["events"]
    actual = {**copy.deepcopy(baseline), **_event_contract(plan)}
    first = next(iter(baseline))
    actual[first] = {"mutated": True}
    with pytest.raises(ValueError, match="preserved S-B10"):
        _check_events(actual, baseline, plan)


def _valid_dr_row(update: int = 6001) -> dict:
    plan = Plan(TABLE, arm="B")
    ranges = plan.domain_randomization["full_ranges"]
    scale = dr_scale(update)
    samples = {
        "base_com_offset_m": {"count": 6, "min": -0.04, "max": 0.04, "mean": 0.0, "target_envs": 2},
        "actuator_gains": {"count": 24, "min": 0.91, "max": 1.09, "mean": 1.0, "target_envs": 2},
        "motor_strength_multiplier": {"count": 4, "min": 0.92, "max": 1.08, "mean": 1.0, "target_envs": 2},
        "motor_effort_limit": {"count": 12, "min": 8.0, "max": 12.0, "mean": 10.0, "target_envs": 2},
        "motor_saturation_effort": {"count": 12, "min": 20.0, "max": 30.0, "mean": 25.0, "target_envs": 2},
        "push_velocity_delta": {"count": 12, "min": -0.8, "max": 0.9, "mean": 0.0, "target_envs": 2},
    }
    realized = {
        "base_com_offset_m": {"count": 12, "min": -0.04, "max": 0.04, "mean": 0.0},
        "delay_substeps": {"count": 4, "min": 0, "max": 3, "mean": 1.5},
        "motor.stiffness": {"count": 12, "min": 0.91, "max": 1.09, "mean": 1.0},
        "motor.damping": {"count": 12, "min": 0.91, "max": 1.09, "mean": 1.0},
        "motor.effort_limit": {"count": 12, "min": 8.0, "max": 12.0, "mean": 10.0},
        "motor.saturation_effort": {"count": 12, "min": 20.0, "max": 30.0, "mean": 25.0},
    }
    return {"it": update, "ex40_dr": {"update": update, "schedule_update": update,
        "smoke_schedule": False, "scale": scale, "config_sha256": "fixture",
        "target_ranges": {"base_com": ranges["base_com"],
            "actuator_gains": ranges["actuator_gains"], "motor_strength": ranges["motor_strength"],
            "push_velocity": ranges["push_velocity"], "delay_max_seconds": 0.015 * scale},
        "actual_samples": samples, "realized_state": realized,
        "delay_readback": {"count": 4, "reset_sample_count": 4, "observed_min_substeps": 0,
            "observed_max_substeps": 3, "max_allowed_substeps": 3,
            "current_histogram": [1, 1, 1, 1], "reset_sample_histogram": [1, 1, 1, 1],
            "max_seconds": 0.015 * scale, "configured_max_seconds": 0.015 * scale,
            "observed_max_seconds": 0.015, "physics_dt_seconds": 0.005},
        "observation_noise": {"mode": "fixed", "multiplier": 1.0}, "pending_values": []}}


def test_runtime_contract_rejects_four_known_bad_dr_readbacks():
    control = _valid_dr_row()
    validate_runtime_summary(control, 6001, require_event_samples=True)
    for mutation in ("com", "motor", "nan", "pending"):
        row = copy.deepcopy(control)["ex40_dr"]
        if mutation == "com":
            row["realized_state"]["base_com_offset_m"].update(min=-99.0, max=99.0)
        elif mutation == "motor":
            row["actual_samples"]["motor_strength_multiplier"].update(min=0.0, max=0.0)
        elif mutation == "nan":
            row["actual_samples"]["base_com_offset_m"].update(min=math.nan, max=math.nan, mean=math.nan)
        else:
            row["pending_values"] = ["push_velocity"]
        with pytest.raises(ValueError):
            validate_runtime_summary({"it": 6001, "ex40_dr": row}, 6001,
                                     require_event_samples=True)


def test_compressed_smoke_covers_all_stage_edges_and_dr_probes():
    assert KIT_SMOKE_BOUNDARIES == (2, 4, 6, 8, 10, 12, 14)
    assert len(KIT_SMOKE_BOUNDARIES) + 1 == 8
    assert [smoke_schedule_update(i) for i in (0, 11, 12, 14)] == [0, 6000, 6001, 7501]
    assert [dr_scale(smoke_schedule_update(i)) for i in (0, 11, 12, 14)] == [0.0, 0.5, 1.0, 1.0]


def test_supervisor_fake_child_waits_consumes_resumes_then_stops_after_three_failures(tmp_path):
    (tmp_path / "segment-1").mkdir()
    run, _, _, _, _ = _known_checkpoint(tmp_path / "segment-1")
    status = run / "train_start_status.json"
    status.write_text('{"state":"failed","iter":5500}', encoding="utf-8")
    wait, empty = transition(run=run, rc=1, shell_finished=False,
        process_alive=None, score_state="unknown")
    assert wait["action"] == "wait"
    assert empty["attempts"] == []

    pending, ledger = transition(run=run, rc=1, shell_finished=True,
        process_alive=False, score_state="pending")
    assert pending["action"] == "wait_for_segment_evaluation"
    first, ledger = transition(run=run, rc=1, shell_finished=True,
        process_alive=False, score_state="consumed", ledger=ledger)
    assert first["action"] == "resume_from_verified_checkpoint"
    assert first["source"]["checkpoint_sha256"]
    (tmp_path / "segment-2").mkdir()
    run, _, _, _, _ = _known_checkpoint(tmp_path / "segment-2")
    (run / "train_start_status.json").write_text(
        '{"state":"failed","iter":5500}', encoding="utf-8")
    second, ledger = transition(run=run, rc=1, shell_finished=True,
        process_alive=False, score_state="consumed", ledger=ledger)
    assert second["action"] == "resume_from_verified_checkpoint"
    (tmp_path / "segment-3").mkdir()
    run, _, _, _, _ = _known_checkpoint(tmp_path / "segment-3")
    (run / "train_start_status.json").write_text(
        '{"state":"failed","iter":5500}', encoding="utf-8")
    third, ledger = transition(run=run, rc=1, shell_finished=True,
        process_alive=False, score_state="consumed", ledger=ledger)
    assert third["action"] == "stop_after_three_failures"
    assert ledger["terminal"]["state"] == "stopped_after_three_failures"


def test_supervisor_runs_child_then_consumes_save_and_uses_official_resume_gate(tmp_path, monkeypatch):
    from foothold_s2 import ex40_supervisor as supervisor

    run, _, _, manifest, _ = _known_checkpoint(tmp_path)
    receipt = tmp_path / "launch-receipt.json"
    receipt.write_text("{}", encoding="utf-8")
    ledger = tmp_path / "ledger.json"
    calls = {"children": 0, "resume_gate": 0}

    class Child:
        def __init__(self, pid, return_code):
            self.pid = pid
            self.return_code = return_code

        def wait(self):
            return self.return_code

    def fake_popen(*_args, **_kwargs):
        calls["children"] += 1
        if calls["children"] == 1:
            (run / "train_start_status.json").write_text(
                json.dumps({"state": "failed", "iter": 5500}), encoding="utf-8")
            return Child(7001, 1)
        final = run / "model_8000.pt"
        final.write_bytes(b"known final checkpoint fixture")
        digest = hashlib.sha256(final.read_bytes()).hexdigest()
        manifest["checkpoints"][final.name] = digest
        (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run / "train_start_status.json").write_text(
            json.dumps({"state": "done", "iter": 8000}), encoding="utf-8")
        return Child(7002, 0)

    def fake_run(command, **_kwargs):
        assert command[1:3] == ["-m", "foothold_s2.ex40_launch"]
        assert "--resume-spec" in command
        calls["resume_gate"] += 1
        return SimpleNamespace(returncode=0,
            stdout=json.dumps({"argv": ["--verified-resume-args"], "training_started": False}),
            stderr="")

    monkeypatch.setattr(supervisor.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(supervisor.subprocess, "run", fake_run)
    monkeypatch.setattr(supervisor, "_run_dir_for_pid", lambda _root, _pid: run)
    monkeypatch.setattr(supervisor, "_score_until_checkpoint", lambda *_args, **_kwargs: "consumed")
    result = supervisor.supervise(initial_args=["--fake-training-args"],
        launch_receipt=receipt, log_root=tmp_path / "logs", score_out=tmp_path / "watch",
        score_dir=tmp_path / "scores", expected_finish="2026-11-01T00:00:00+09:00",
        end_by="2026-11-03T00:00:00+09:00", arm="B", device="cuda:0",
        ledger_path=ledger, max_segments=3)
    assert result["action"] == "complete"
    assert calls == {"children": 2, "resume_gate": 1}
    persisted = json.loads(ledger.read_text(encoding="utf-8"))
    assert persisted["attempts"][0]["state"] == "failed"
    assert persisted["terminal"]["state"] == "done"


@pytest.mark.parametrize("row_state,completion_state,expected", [
    ("PASS", "waiting_for_remaining_scores", "pending"),
    ("PASS", "score_hold", "pending"),
    ("PASS", "final_training_receipt_mismatch", "pending"),
    ("PASS", "done", "consumed"),
    ("HOLD", "score_hold", "pending"),
])
def test_final_checkpoint_requires_complete_score_ledger_and_non_hold_verdict(
        tmp_path, monkeypatch, row_state, completion_state, expected):
    from foothold_s2 import ex40_score_watch, ex40_supervisor

    run = tmp_path / "run"
    watch = tmp_path / "watch"
    run.mkdir()
    watch.mkdir()
    checkpoint = run / "model_8000.pt"
    checkpoint.write_bytes(b"known final model")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps({
        "checkpoints": {checkpoint.name: digest}}), encoding="utf-8")
    (watch / "watch_state.json").write_text(json.dumps({
        "done": {"8000": {"state": row_state, "checkpoint_sha256": digest}}}),
        encoding="utf-8")
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: {
        "checkpoint_first": 500, "checkpoint_stride": 250, "final_checkpoint_update": 8000})
    monkeypatch.setattr(ex40_score_watch, "completion", lambda *_args: {"state": completion_state})
    monkeypatch.setattr(ex40_supervisor.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="fixture"))

    result = _score_until_checkpoint(run, watch, tmp_path / "scores", tmp_path / "cfg.yaml",
        tmp_path / "table.yaml", "B", 8000, digest, max_calls=1)
    assert result == expected


def test_final_checkpoint_sha_mismatch_cannot_be_consumed(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor

    run = tmp_path / "run"
    watch = tmp_path / "watch"
    run.mkdir()
    watch.mkdir()
    checkpoint = run / "model_8000.pt"
    checkpoint.write_bytes(b"changed final model")
    digest = "0" * 64
    (run / "manifest.json").write_text(json.dumps({
        "checkpoints": {checkpoint.name: digest}}), encoding="utf-8")
    (watch / "watch_state.json").write_text(json.dumps({
        "done": {"8000": {"state": "PASS", "checkpoint_sha256": digest}}}),
        encoding="utf-8")
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: {
        "checkpoint_first": 500, "checkpoint_stride": 250, "final_checkpoint_update": 8000})
    monkeypatch.setattr(ex40_supervisor.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="fixture"))

    result = _score_until_checkpoint(run, watch, tmp_path / "scores", tmp_path / "cfg.yaml",
        tmp_path / "table.yaml", "B", 8000, digest, max_calls=1)
    assert result == "unknown"


def test_supervised_execution_copy_calls_watchdog_without_touching_original():
    copy_script = Path(__file__).resolve().parents[1] / "run_ex40_b11.sh"
    original = copy_script.with_name("run_ex40.sh")
    script = copy_script.read_text(encoding="utf-8")
    assert "ex40_supervisor --supervise" in script
    assert "EX40_EXPECTED_FINISH" in script
    assert original.is_file()
    assert "ex40_supervisor" not in original.read_text(encoding="utf-8")
