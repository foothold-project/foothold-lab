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
    calls = {"children": 0, "resume_gate": 0, "active_score_polls": [], "active_child": None}

    class Child:
        def __init__(self, pid, return_code):
            self.pid = pid
            self.return_code = return_code
            self.poll_count = 0

        def poll(self):
            self.poll_count += 1
            return None if self.poll_count == 1 else self.return_code

        def wait(self):
            return self.return_code

    def fake_popen(*_args, **_kwargs):
        calls["children"] += 1
        if calls["children"] == 1:
            (run / "train_start_status.json").write_text(
                json.dumps({"state": "failed", "iter": 5500}), encoding="utf-8")
            calls["active_child"] = Child(7001, 1)
            return calls["active_child"]
        final = run / "model_8000.pt"
        final.write_bytes(b"known final checkpoint fixture")
        digest = hashlib.sha256(final.read_bytes()).hexdigest()
        manifest["checkpoints"][final.name] = digest
        (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run / "train_start_status.json").write_text(
            json.dumps({"state": "done", "iter": 8000}), encoding="utf-8")
        calls["active_child"] = Child(7002, 0)
        return calls["active_child"]

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
    checkpoint_sha = hashlib.sha256((run / "model_5500.pt").read_bytes()).hexdigest()
    monkeypatch.setattr(supervisor, "_latest_score_checkpoint",
                        lambda *_args: (5500, checkpoint_sha))
    def fake_score(*_args, **_kwargs):
        active_child = calls["active_child"]
        calls["active_score_polls"].append((active_child.pid, active_child.poll_count))
        return "consumed"
    monkeypatch.setattr(supervisor, "_score_until_checkpoint", fake_score)
    result = supervisor.supervise(initial_args=["--fake-training-args"],
        launch_receipt=receipt, log_root=tmp_path / "logs", score_out=tmp_path / "watch",
        score_dir=tmp_path / "scores", expected_finish="2026-11-01T00:00:00+09:00",
        end_by="2026-11-03T00:00:00+09:00", arm="B", device="cuda:0",
        ledger_path=ledger, max_segments=3, poll_seconds=0, sleep=lambda _seconds: None)
    assert result["action"] == "complete"
    assert calls["children"] == 2 and calls["resume_gate"] == 1
    assert any(polls == 1 for _pid, polls in calls["active_score_polls"])
    persisted = json.loads(ledger.read_text(encoding="utf-8"))
    assert persisted["attempts"][0]["state"] == "failed"
    assert persisted["terminal"]["state"] == "done"
    events = [json.loads(line) for line in (tmp_path / "watch" / "supervisor_score_events.jsonl")
              .read_text(encoding="utf-8").splitlines()]
    assert events and events[0]["pid"] == 7001
    assert events[0]["score_state"] == "consumed"


def test_stage_report_uses_checkpoint_source_segment_and_prior_segment(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch

    first_run, second_run = tmp_path / "segment-0", tmp_path / "segment-1"
    first_run.mkdir()
    second_run.mkdir()
    out_root = tmp_path / "watch"
    out_root.mkdir()
    calls = []
    ledger_rows = []
    for update, stage, run in ((500, "B0", first_run), (750, "B1", second_run)):
        score_path = out_root / f"score_{update}.json"
        score_path.write_text(json.dumps({"checkpoint_iteration": update, "from": stage,
                                          "checkpoint_sha256": str(update)}), encoding="utf-8")
        ledger_rows.append({"checkpoint_iteration": update, "stage": stage, "verdict": "PASS",
            "run_dir": str(run), "score_path": str(score_path),
            "score_sha256": hashlib.sha256(score_path.read_bytes()).hexdigest()})
    (out_root / "score_ledger.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in ledger_rows), encoding="utf-8")
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: {})
    monkeypatch.setattr(ex40_score_watch, "stage_end_updates",
                        lambda *_args: {500: "B0", 750: "B1"})

    def fake_build(current, previous, run, *, previous_run=None):
        calls.append((current["checkpoint_iteration"], run, previous_run))
        return {"checkpoint_sha256": current["checkpoint_sha256"],
                "previous_checkpoint_iteration": previous["checkpoint_iteration"] if previous else None,
                "gains": [], "losses": [], "unchanged": []}

    monkeypatch.setattr(ex40_score_watch, "build_stage_report", fake_build)
    monkeypatch.setattr(ex40_score_watch, "stage_markdown", lambda _row: "local fixture report\n")
    result = ex40_score_watch.stage_reports(second_run, out_root, tmp_path / "cfg.yaml",
                                              TABLE, "B")
    assert result["state"] == "done"
    assert calls == [(500, first_run, first_run), (750, second_run, first_run)]


def test_supervisor_consumes_actual_stage_report_count_and_fake_delivery(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor
    from foothold_s2.ex40_supervisor import _score_until_checkpoint

    run, watch, scores = tmp_path / "run", tmp_path / "watch", tmp_path / "scores"
    run.mkdir()
    watch.mkdir()
    scores.mkdir()
    checkpoint = run / "model_500.pt"
    checkpoint.write_bytes(b"actual CPU checkpoint input")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps({
        "schema": "foothold-manifest/1", "progress": {"completed_updates": 501},
        "checkpoints": {checkpoint.name: digest}}), encoding="utf-8")
    (watch / "watch_state.json").write_text(json.dumps({
        "format": "foothold-ex40-score-watch/1", "arm": "B",
        "done": {"500": {"state": "PASS", "checkpoint_sha256": digest}}}), encoding="utf-8")
    _add_valid_supervisor_slot(run, watch, 500, digest, "B0")
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: {
        "checkpoint_first": 500, "checkpoint_stride": 250,
        "final_checkpoint_update": 1000})
    monkeypatch.setattr(ex40_supervisor, "_verified_score_slot", lambda *_args: "verified")
    monkeypatch.setattr(ex40_score_watch, "stage_end_updates", lambda *_args: {500: "B0"})
    monkeypatch.setattr(ex40_score_watch, "build_stage_report", lambda current, previous, _run,
        **_kwargs: {"checkpoint_iteration": current["checkpoint_iteration"],
                    "checkpoint_sha256": current["checkpoint_sha256"],
                    "previous_checkpoint_iteration": None, "gains": [], "losses": [],
                    "unchanged": [], "current": {"source_sha256": {}}})
    monkeypatch.setattr(ex40_score_watch, "stage_markdown", lambda _row: "CPU receipt\n")
    sent = []
    sender_path = tmp_path / "fake_sender.py"
    lab_feed = tmp_path / "lab" / "ex40_stage_reports.json"
    state = _score_until_checkpoint(run, watch, scores, tmp_path / "cfg.yaml", TABLE,
        "B", 500, digest, max_calls=1, telegram_sender=sender_path, lab_feed=lab_feed,
        sender=lambda script, message: sent.append((script, message.read_text(encoding="utf-8"))) or True)

    assert state == "consumed"
    stage_root = watch / "stage_reports"
    report = stage_root / "stage_B0_m500.json"
    delivery = json.loads((stage_root / "stage_B0_m500.delivery.json").read_text(encoding="utf-8"))
    assert json.loads(report.read_text(encoding="utf-8"))["checkpoint_sha256"] == digest
    assert delivery["state"] == "sent"
    assert len(sent) == 1 and "상황판:" in sent[0][1]
    feed = json.loads(lab_feed.read_text(encoding="utf-8"))
    assert feed["stage_reports"][0]["update"] == 500
    assert lab_feed.with_suffix(".html").is_file()


def test_supervisor_handles_actual_zero_published_count_as_pending(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor
    from foothold_s2.ex40_supervisor import _score_until_checkpoint

    run, watch, scores = tmp_path / "run", tmp_path / "watch", tmp_path / "scores"
    run.mkdir()
    watch.mkdir()
    scores.mkdir()
    checkpoint = run / "model_500.pt"
    checkpoint.write_bytes(b"zero published count checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps({
        "schema": "foothold-manifest/1", "progress": {"completed_updates": 501},
        "checkpoints": {checkpoint.name: digest}}), encoding="utf-8")
    (watch / "watch_state.json").write_text(json.dumps({
        "format": "foothold-ex40-score-watch/1", "arm": "B",
        "done": {"500": {"state": "PASS", "checkpoint_sha256": digest}}}), encoding="utf-8")
    _add_valid_supervisor_slot(run, watch, 500, digest, "B0")
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: {
        "checkpoint_first": 500, "checkpoint_stride": 250,
        "final_checkpoint_update": 1000})
    monkeypatch.setattr(ex40_supervisor, "_verified_score_slot", lambda *_args: "verified")
    monkeypatch.setattr(ex40_score_watch, "stage_end_updates", lambda *_args: {500: "B0"})
    real_stage_reports = ex40_score_watch.stage_reports
    observed = []

    def observe(*args, **kwargs):
        result = real_stage_reports(*args, **kwargs)
        observed.append((result["published"], type(result["published"])))
        return result

    monkeypatch.setattr(ex40_score_watch, "stage_reports", observe)
    result = _score_until_checkpoint(run, watch, scores, tmp_path / "cfg.yaml", TABLE,
        "B", 500, digest, max_calls=1)
    assert observed == [(0, int)]
    assert result == "pending"
    with pytest.raises(TypeError, match="'int' object is not iterable"):
        set(observed[0][0])


def test_supervisor_watch_command_routes_sender_and_shared_lab_feed(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor

    run, watch, scores = tmp_path / "run", tmp_path / "watch", tmp_path / "scores"
    run.mkdir()
    watch.mkdir()
    scores.mkdir()
    checkpoint = run / "model_500.pt"
    checkpoint.write_bytes(b"routing probe checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps({
        "schema": "foothold-manifest/1", "progress": {"completed_updates": 501},
        "checkpoints": {checkpoint.name: digest}}), encoding="utf-8")
    cfg = {"checkpoint_first": 500, "checkpoint_stride": 250,
           "final_checkpoint_update": 1000, "check_interval_seconds": 1}
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: cfg)
    monkeypatch.setattr(ex40_supervisor, "_verified_score_slot", lambda *_args: "verified")
    monkeypatch.setattr(ex40_score_watch, "stage_end_updates", lambda *_args: {750: "B1"})
    command_rows = []
    monkeypatch.setattr(ex40_supervisor.subprocess, "run", lambda command, **_kwargs: (
        command_rows.append(command) or SimpleNamespace(returncode=0,
            stdout=json.dumps({"evaluation": {"state": "PASS"}}), stderr="")))
    sender_path = tmp_path / "sender.py"
    lab_feed = tmp_path / "shared" / "stage_reports.json"
    assert _score_until_checkpoint(run, watch, scores, tmp_path / "cfg.yaml", TABLE,
        "B", 501, digest, max_calls=1, telegram_sender=sender_path,
        lab_feed=lab_feed) == "pending"
    command = command_rows[0]
    assert "--telegram-sender" in command
    assert command[command.index("--telegram-sender") + 1] == str(sender_path)
    assert "--no-telegram" not in command
    assert command[command.index("--lab-feed") + 1] == str(lab_feed)


def _add_valid_supervisor_slot(run: Path, watch: Path, update: int, digest: str, stage: str):
    from foothold_s2.ex40_score_watch import DEFAULT_CONFIG, config as score_config

    cfg = score_config(DEFAULT_CONFIG)
    plan = Plan(TABLE, arm="B")
    (run / "stage_log.jsonl").write_text(json.dumps({"event": "stage_enter",
        "iteration": 0, "to": stage, "effective_schedule_sha256": plan.effective_sha256}) + "\n",
        encoding="utf-8")
    stage_cfg = cfg["stages"][stage]
    phases = {"map64", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred"}
    if stage_cfg.get("relative_commands") or stage_cfg.get("judge_walk_half"):
        phases.add("map64_b3")
    phases.add("axis_v2")
    evidence = watch / f"evidence_{update}"
    evidence.mkdir(exist_ok=True)
    sources = {}
    for phase in phases:
        source = evidence / f"{phase}.json"
        source.write_text("{}", encoding="utf-8")
        sources[phase] = str(source)
    receipt = evidence / "eval_receipt.json"
    receipt.write_text(json.dumps({"state": "done", "steps": {
        phase: {"rc": 0} for phase in phases}}), encoding="utf-8")
    score_path = watch / f"score_{update}.json"
    score_path.write_text(json.dumps({"checkpoint_iteration": update,
        "checkpoint_sha256": digest, "from": stage, "verdict": "PASS",
        "sources": sources, "evaluation_receipt": str(receipt)}), encoding="utf-8")
    state_path = watch / "watch_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["done"][str(update)].update({"stage": stage, "score_path": str(score_path)})
    state_path.write_text(json.dumps(state), encoding="utf-8")
    row = {"checkpoint_iteration": update, "checkpoint_sha256": digest,
        "stage": stage, "verdict": "PASS", "run_dir": str(run),
        "checkpoint_path": str(run / f"model_{update}.pt"),
        "score_path": str(score_path),
        "score_sha256": hashlib.sha256(score_path.read_bytes()).hexdigest()}
    (watch / "score_ledger.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def _supervisor_slot_history(root: Path, *, include_prior_5250: bool, target_update: int = 5500):
    from foothold_s2.ex40_score_watch import DEFAULT_CONFIG, config as score_config, stage_end_updates
    from foothold_s2.eval.map_mode_cells import commands as map_commands

    cfg = score_config(DEFAULT_CONFIG)
    plan = Plan(TABLE, arm="B")
    boundaries = stage_end_updates(plan, cfg)
    current_run = root / "segment-current"
    old_run = root / "segment-prior"
    current_run.mkdir(parents=True)
    old_run.mkdir(parents=True)
    out_root = root / "watch"
    out_root.mkdir()
    manifests = {current_run: {"schema": "foothold-manifest/1",
                               "progress": {"completed_updates": 0}, "checkpoints": {}},
                 old_run: {"schema": "foothold-manifest/1",
                           "progress": {"completed_updates": 0}, "checkpoints": {}}}
    stages_by_run = {current_run: set(), old_run: set()}
    done, ledger = {}, []
    score_dir = root / "scores"
    score_dir.mkdir()
    for update in range(cfg["checkpoint_first"], target_update + 1, cfg["checkpoint_stride"]):
        if update == 5250 and not include_prior_5250:
            continue
        source_run = old_run if update == 5250 else current_run
        checkpoint = source_run / f"model_{update}.pt"
        checkpoint.write_bytes(f"verified checkpoint {update}".encode())
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        manifest = manifests[source_run]
        manifest["checkpoints"][checkpoint.name] = digest
        manifest["progress"]["completed_updates"] = max(
            manifest["progress"]["completed_updates"], update + 1)
        stage = max((item for item in plan.stages if item.fixed_update <= update),
                    key=lambda item: item.fixed_update).id
        stages_by_run[source_run].update((item.fixed_update, item.id)
                                         for item in plan.stages if item.fixed_update <= update)
        stage_cfg = cfg["stages"][stage]
        phases = {"map64", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred"}
        if stage_cfg.get("relative_commands") or stage_cfg.get("judge_walk_half"):
            phases.add("map64_b3")
        if stage_cfg["axis_goal"] or update in boundaries:
            phases.add("axis_v2")
        evidence = out_root / f"evidence_{update}"
        evidence.mkdir()
        sources = {}
        for phase in phases:
            path = evidence / f"{phase}.json"
            if phase == "map64":
                per_env = [{"samples_alive": 1,
                    "vx_abs_error_mean_alive_mps": 0.1,
                    "vy_abs_error_mean_alive_mps": 0.1,
                    "wz_abs_error_mean_alive_radps": 0.1} for _ in range(64)]
                payload = {"checkpoint_sha256": digest, "envs": 64, "modes": {
                    mode: {name: {"alive_envs_at_end": 64, "per_env": per_env}
                           for name in map_commands("extended")}
                    for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
            elif phase == "axis_v2":
                payload = {"checkpoint_sha256": digest, "envs": 64, "modes": {
                    mode: {"forward": {"alive_at_end": 64,
                        "stop_end_error_median_rad": 0.1,
                        "yaw_final_minus_start_median_rad": 0.1,
                        "contact_left_right_gap_median": 0.1}}
                    for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
            elif phase.startswith("stand_"):
                per_env = [{"feet": {foot: {"contact_fraction_gt1n": 0.5,
                    "mean_fz_over_mg": 1.0, "sole_gap_p95_m": 0.01}
                    for foot in ("FL_foot", "FR_foot", "RL_foot", "RR_foot")}}
                    for _ in range(64)]
                payload = {"checkpoint_sha256": digest, "envs": 64, "per_env": per_env}
            else:
                payload = {}
            path.write_text(json.dumps(payload), encoding="utf-8")
            sources[phase] = str(path)
        receipt_path = evidence / "eval_receipt.json"
        receipt_path.write_text(json.dumps({"state": "done", "steps": {
            phase: {"rc": 0} for phase in phases}}), encoding="utf-8")
        score_path = score_dir / f"score_{update}.json"
        score_path.write_text(json.dumps({"checkpoint_iteration": update,
            "checkpoint_sha256": digest, "from": stage, "verdict": "PASS",
            "sources": sources, "evaluation_receipt": str(receipt_path)}), encoding="utf-8")
        done[str(update)] = {"state": "PASS", "stage": stage,
                             "checkpoint_sha256": digest, "score_path": str(score_path)}
        ledger.append({"checkpoint_iteration": update, "checkpoint_sha256": digest,
            "stage": stage, "verdict": "PASS", "run_dir": str(source_run),
            "checkpoint_path": str(checkpoint), "score_path": str(score_path),
            "score_sha256": hashlib.sha256(score_path.read_bytes()).hexdigest()})
    for source_run, manifest in manifests.items():
        (source_run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        rows = sorted(stages_by_run[source_run])
        (source_run / "stage_log.jsonl").write_text("".join(json.dumps({
            "event": "stage_enter", "iteration": iteration, "to": stage_id,
            "effective_schedule_sha256": plan.effective_sha256}) + "\n"
            for iteration, stage_id in rows),
            encoding="utf-8")
    (out_root / "watch_state.json").write_text(json.dumps({
        "format": "foothold-ex40-score-watch/1", "arm": "B", "done": done}),
        encoding="utf-8")
    (out_root / "score_ledger.jsonl").write_text("".join(json.dumps(row) + "\n" for row in ledger),
        encoding="utf-8")
    return current_run, out_root, score_dir, manifests[current_run]["checkpoints"][f"model_{target_update}.pt"]


def _relocate_supervisor_history(root: Path, *, first_current: int,
                                 non_stride_update: int | None = None):
    """Create a real ledger-backed split run, keeping score/eval evidence intact."""
    from foothold_s2.ex40_score_watch import DEFAULT_CONFIG, DEFAULT_TABLE, config as score_config

    final_update = 1500 if non_stride_update is not None else 8000
    current, watch, scores, _ = _supervisor_slot_history(
        root, include_prior_5250=True, target_update=final_update)
    prior = root / "segment-prior-all"
    prior.mkdir()
    ledger_path = watch / "score_ledger.jsonl"
    ledger = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    for row in ledger:
        update = row["checkpoint_iteration"]
        destination = prior if update < first_current else current
        checkpoint = Path(row["checkpoint_path"])
        target = destination / checkpoint.name
        if checkpoint.resolve() != target.resolve():
            if target.exists():
                target.unlink()
            checkpoint.replace(target)
        row["run_dir"] = str(destination)
        row["checkpoint_path"] = str(target)

    if non_stride_update is not None:
        checkpoint = current / f"model_{non_stride_update}.pt"
        checkpoint.write_bytes(f"non-stride segment save {non_stride_update}".encode())
        non_stride_digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    else:
        non_stride_digest = None

    plan = Plan(DEFAULT_TABLE, arm="B")
    for source in (prior, current):
        source_rows = sorted((row for row in ledger if Path(row["run_dir"]) == source),
                             key=lambda row: row["checkpoint_iteration"])
        checkpoints = {Path(row["checkpoint_path"]).name: row["checkpoint_sha256"]
                       for row in source_rows}
        progress = max((row["checkpoint_iteration"] + 1 for row in source_rows), default=0)
        if source == current and non_stride_update is not None:
            checkpoints[f"model_{non_stride_update}.pt"] = non_stride_digest
            progress = max(progress, non_stride_update + 1)
        manifest = {"schema": "foothold-manifest/1",
                    "progress": {"completed_updates": progress}, "checkpoints": checkpoints}
        (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        stage_rows = []
        seen = set()
        for row in source_rows:
            stage = row["stage"]
            if stage not in seen:
                stage_rows.append({"event": "stage_enter", "iteration": row["checkpoint_iteration"],
                                   "to": stage,
                                   "effective_schedule_sha256": plan.effective_sha256})
                seen.add(stage)
        (source / "stage_log.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in stage_rows), encoding="utf-8")
    ledger_path.write_text("".join(json.dumps(row) + "\n" for row in ledger), encoding="utf-8")
    if final_update == 8000:
        final = current / "model_8000.pt"
        final_sha = hashlib.sha256(final.read_bytes()).hexdigest()
        (current / "train_start_status.json").write_text(json.dumps({
            "state": "done", "iter": 8000, "checkpoint": str(final),
            "sha256": final_sha}), encoding="utf-8")
    return current, prior, watch, scores, non_stride_digest


@pytest.mark.parametrize("signal_update", [1550, 1600])
def test_resume_target_uses_verified_prior_segment_and_stage_report_sha(
        tmp_path, monkeypatch, signal_update):
    from foothold_s2 import ex40_score_watch, ex40_supervisor
    from foothold_s2.ex40_score_watch import DEFAULT_CONFIG, DEFAULT_TABLE

    run, prior, watch, scores, signal_sha = _relocate_supervisor_history(
        tmp_path, first_current=1551, non_stride_update=signal_update)
    assert signal_sha is not None
    feed = watch / "lab_feed.json"
    sender_path = tmp_path / "fake_sender.py"
    sends = []
    initial_reports = ex40_score_watch.stage_reports(
        run, watch, DEFAULT_CONFIG, DEFAULT_TABLE, "B", telegram_sender=sender_path,
        lab_feed=feed, sender=lambda script, message: sends.append(message.read_text(encoding="utf-8")) or True)
    assert initial_reports["published"] > 0 and initial_reports["first_hold"] is None
    before_sends = len(sends)
    monkeypatch.setattr(ex40_supervisor.subprocess, "run",
        lambda *_args, **_kwargs: pytest.fail("verified prior scores must not be re-evaluated"))

    result = _score_until_checkpoint(run, watch, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
        "B", signal_update, signal_sha, max_calls=1, telegram_sender=sender_path,
        lab_feed=feed, sender=lambda *_: sends.append("unexpected resend") or True)
    again = _score_until_checkpoint(run, watch, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
        "B", signal_update, signal_sha, max_calls=1, telegram_sender=sender_path,
        lab_feed=feed, sender=lambda *_: sends.append("unexpected resend") or True)

    assert result == "consumed" and again == "consumed"
    assert len(sends) == before_sends
    assert ex40_score_watch._manifest_digest(prior, 1500) is not None


def test_resume_full_31_slot_split_completes_prior_stage_reports_once(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor
    from foothold_s2.ex40_score_watch import DEFAULT_CONFIG, DEFAULT_TABLE

    run, prior, watch, scores, _ = _relocate_supervisor_history(
        tmp_path, first_current=3250)
    ledger = ex40_score_watch._ledger_rows(watch)
    assert len(ledger) == 31
    assert sum(Path(row["run_dir"]) == prior for row in ledger) == 11
    feed = watch / "lab_feed.json"
    sender_path = tmp_path / "fake_sender.py"
    sends = []
    initial = ex40_score_watch.stage_reports(
        run, watch, DEFAULT_CONFIG, DEFAULT_TABLE, "B", telegram_sender=sender_path,
        lab_feed=feed, sender=lambda script, message: sends.append(message.read_text(encoding="utf-8")) or True)
    assert initial["state"] == "done" and initial["published"] == 8
    before_sends = len(sends)
    final_sha = ex40_score_watch._manifest_digest(run, 8000)
    monkeypatch.setattr(ex40_supervisor.subprocess, "run",
        lambda *_args, **_kwargs: pytest.fail("all 31 verified slots must not be re-evaluated"))

    result = _score_until_checkpoint(run, watch, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
        "B", 8000, final_sha, max_calls=1, telegram_sender=sender_path,
        lab_feed=feed, sender=lambda *_: sends.append("unexpected resend") or True)
    again = _score_until_checkpoint(run, watch, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
        "B", 8000, final_sha, max_calls=1, telegram_sender=sender_path,
        lab_feed=feed, sender=lambda *_: sends.append("unexpected resend") or True)

    assert result == "consumed" and again == "consumed"
    assert len(sends) == before_sends == 8
    assert ex40_score_watch.completion(run, watch, DEFAULT_CONFIG, DEFAULT_TABLE,
        "B", json.loads((watch / "watch_state.json").read_text(encoding="utf-8")))["state"] == "done"


def test_resume_target_missing_or_conflicting_prior_source_stays_blocked(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor
    from foothold_s2.ex40_score_watch import DEFAULT_CONFIG, DEFAULT_TABLE

    missing_root = tmp_path / "missing"
    run, prior, watch, scores, signal_sha = _relocate_supervisor_history(
        missing_root, first_current=1551, non_stride_update=1550)
    ledger_path = watch / "score_ledger.jsonl"
    ledger = ex40_score_watch._ledger_rows(watch)
    target = next(row for row in ledger if row["checkpoint_iteration"] == 1500)
    Path(target["checkpoint_path"]).unlink()
    manifest_path = prior / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"].pop("model_1500.pt")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (watch / "watch_state.json").write_text(json.dumps({
        "format": "foothold-ex40-score-watch/1", "arm": "B",
        "done": {str(key): value for key, value in
                 json.loads((watch / "watch_state.json").read_text(encoding="utf-8"))["done"].items()
                 if key != "1500"}}), encoding="utf-8")
    ledger_path.write_text("".join(json.dumps(row) + "\n" for row in ledger
                                   if row["checkpoint_iteration"] != 1500), encoding="utf-8")
    assert _score_until_checkpoint(run, watch, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
        "B", 1550, signal_sha, max_calls=1) == "pending"

    conflict_root = tmp_path / "conflict"
    run, prior, watch, scores, signal_sha = _relocate_supervisor_history(
        conflict_root, first_current=1551, non_stride_update=1550)
    duplicate = run / "model_1500.pt"
    duplicate.write_bytes(b"same update, different resumed segment bytes")
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["checkpoints"][duplicate.name] = hashlib.sha256(duplicate.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert _score_until_checkpoint(run, watch, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
        "B", 1550, signal_sha, max_calls=1) == "unknown"


def test_stride_slot_gap_blocks_consumption_but_verified_prior_segment_is_kept(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor
    from foothold_s2.ex40_score_watch import DEFAULT_CONFIG, DEFAULT_TABLE

    reports_called = []
    child_calls = []
    monkeypatch.setattr(ex40_score_watch, "stage_reports", lambda *_args, **_kwargs: (
        reports_called.append(True) or {"state": "pending", "published": 99,
            "first_pending": None, "first_hold": None}))
    monkeypatch.setattr(ex40_supervisor, "_stage_report_delivery_ok", lambda *_args: True)
    monkeypatch.setattr(ex40_supervisor.subprocess, "run", lambda *args, **kwargs:
        child_calls.append((args, kwargs)) or SimpleNamespace(returncode=1, stdout="", stderr="unexpected"))

    missing_run, missing_watch, missing_scores, missing_sha = _supervisor_slot_history(
        tmp_path / "gap", include_prior_5250=False)
    assert _score_until_checkpoint(missing_run, missing_watch, missing_scores, DEFAULT_CONFIG,
        DEFAULT_TABLE, "B", 5550, missing_sha, max_calls=1) == "pending"
    assert reports_called == []

    prior_run, prior_watch, prior_scores, prior_sha = _supervisor_slot_history(
        tmp_path / "prior", include_prior_5250=True)
    prior_state_path = prior_watch / "watch_state.json"
    prior_state = json.loads(prior_state_path.read_text(encoding="utf-8"))
    prior_state["done"].pop("5250")
    prior_state_path.write_text(json.dumps(prior_state), encoding="utf-8")
    assert _score_until_checkpoint(prior_run, prior_watch, prior_scores, DEFAULT_CONFIG,
        DEFAULT_TABLE, "B", 5550, prior_sha, max_calls=1) == "consumed"
    assert reports_called == [True]
    assert child_calls == []

    conflict_run, conflict_watch, conflict_scores, conflict_sha = _supervisor_slot_history(
        tmp_path / "conflict", include_prior_5250=True)
    prior_checkpoint = conflict_run.parent / "segment-prior" / "model_5250.pt"
    prior_checkpoint.write_bytes(b"changed after score receipt")
    assert _score_until_checkpoint(conflict_run, conflict_watch, conflict_scores, DEFAULT_CONFIG,
        DEFAULT_TABLE, "B", 5550, conflict_sha, max_calls=1) == "unknown"


def test_non_stride_save_drains_pending_stride_scores_and_requires_local_stage_receipt(
        tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor

    run, _, _, _, _ = _known_checkpoint(tmp_path)
    watch = tmp_path / "watch"
    scores = tmp_path / "scores"
    watch.mkdir()
    scores.mkdir()
    checkpoints = {}
    for update in (500, 750):
        path = run / f"model_{update}.pt"
        path.write_bytes(f"fixture checkpoint {update}".encode())
        checkpoints[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    non_stride = run / "model_751.pt"
    non_stride.write_bytes(b"non-stride save after 750")
    checkpoints[non_stride.name] = hashlib.sha256(non_stride.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps({
        "schema": "foothold-manifest/1", "progress": {"completed_updates": 752},
        "checkpoints": checkpoints}), encoding="utf-8")
    (watch / "watch_state.json").write_text(json.dumps({
        "format": "foothold-ex40-score-watch/1", "arm": "B", "done": {}}),
        encoding="utf-8")
    cfg = {"checkpoint_first": 500, "checkpoint_stride": 250,
           "final_checkpoint_update": 1000, "check_interval_seconds": 1}
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: cfg)
    monkeypatch.setattr(ex40_supervisor, "_verified_score_slot", lambda *_args: "verified")
    monkeypatch.setattr(ex40_score_watch, "stage_end_updates",
                        lambda _plan, _cfg: {750: "S1", 1000: "S2"})
    sender_path = tmp_path / "sender.py"
    lab_feed = tmp_path / "shared" / "stage_reports.json"

    def fake_stage_reports(_run, out_root, *_args, **kwargs):
        stage_root = out_root / "stage_reports"
        stage_root.mkdir(exist_ok=True)
        report_path = stage_root / "stage_S1_m750.json"
        report_path.write_text(json.dumps({"checkpoint_iteration": 750,
            "checkpoint_sha256": checkpoints["model_750.pt"]}), encoding="utf-8")
        (stage_root / "stage_S1_m750.md").write_text("fake report\n", encoding="utf-8")
        summary = stage_root / "stage_S1_m750.telegram.txt"
        summary.write_text("fake summary\n", encoding="utf-8")
        (stage_root / "stage_S1_m750.delivery.json").write_text(json.dumps({
            "state": "sent", "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest()}),
            encoding="utf-8")
        feed = kwargs["lab_feed"]
        feed.parent.mkdir(parents=True, exist_ok=True)
        feed.write_text(json.dumps({"stage_reports": [{"stage": "S1", "update": 750,
            "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest()}]}), encoding="utf-8")
        feed.with_suffix(".html").write_text("<html></html>\n", encoding="utf-8")
        return {"state": "pending", "published": 1, "first_pending": 1000, "first_hold": None}

    monkeypatch.setattr(ex40_score_watch, "stage_reports", fake_stage_reports)
    calls = []

    def fake_watch(command, **_kwargs):
        calls.append(command)
        state_path = watch / "watch_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        done = state.setdefault("done", {})
        pending = next(update for update in (500, 750) if str(update) not in done)
        pinned = checkpoints[f"model_{pending}.pt"]
        done[str(pending)] = {"state": "PASS", "checkpoint_sha256": pinned}
        state.update({"format": "foothold-ex40-score-watch/1", "arm": "B"})
        state_path.write_text(json.dumps(state), encoding="utf-8")
        ledger_path = watch / "score_ledger.jsonl"
        with ledger_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"checkpoint_iteration": pending,
                "checkpoint_sha256": pinned, "run_dir": str(run),
                "checkpoint_path": str(run / f"model_{pending}.pt")}) + "\n")
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "evaluation": {"state": "PASS", "update": pending},
            "reports": {"state": "pending"}, "completion": {"state": "waiting_for_training"}}),
            stderr="")

    monkeypatch.setattr(ex40_supervisor.subprocess, "run", fake_watch)
    result = _score_until_checkpoint(run, watch, scores, tmp_path / "cfg.yaml",
        TABLE, "B", 751, checkpoints["model_751.pt"], max_calls=4,
        telegram_sender=sender_path, lab_feed=lab_feed)
    assert result == "consumed"
    assert len(calls) == 2
    assert "--telegram-sender" in calls[0] and "--no-telegram" not in calls[0]
    assert calls[0][calls[0].index("--telegram-sender") + 1] == str(sender_path)
    assert calls[0][calls[0].index("--lab-feed") + 1] == str(lab_feed)
    saved = json.loads((watch / "watch_state.json").read_text(encoding="utf-8"))
    assert sorted(saved["done"]) == ["500", "750"]


def test_segment_duplicate_sha_and_missing_score_remain_unconsumed(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor

    run = tmp_path / "segment-2"
    watch = tmp_path / "watch"
    run.mkdir()
    watch.mkdir()
    checkpoint = run / "model_5500.pt"
    checkpoint.write_bytes(b"new segment checkpoint")
    actual = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps({
        "schema": "foothold-manifest/1", "progress": {"completed_updates": 5501},
        "checkpoints": {checkpoint.name: actual}}), encoding="utf-8")
    (watch / "watch_state.json").write_text(json.dumps({
        "format": "foothold-ex40-score-watch/1", "arm": "B",
        "done": {"5500": {"state": "PASS", "checkpoint_sha256": "a" * 64}}}),
        encoding="utf-8")
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: {
        "checkpoint_first": 500, "checkpoint_stride": 250, "final_checkpoint_update": 8000})
    monkeypatch.setattr(ex40_score_watch, "stage_end_updates", lambda *_args: {})
    monkeypatch.setattr(ex40_score_watch, "stage_reports", lambda *_args, **_kwargs: {
        "state": "done", "published": 0, "first_pending": None, "first_hold": None})
    monkeypatch.setattr(ex40_supervisor.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0,
            stdout=json.dumps({"evaluation": {"state": "idle"}}), stderr=""))
    # The same update number from a resumed segment cannot inherit an older segment's SHA receipt.
    assert _score_until_checkpoint(run, watch, tmp_path / "scores", tmp_path / "cfg.yaml",
        TABLE, "B", 5500, actual, max_calls=1) == "pending"
    # If a stride row is absent and the consumer has no stable candidate, it stays pending.
    state = json.loads((watch / "watch_state.json").read_text(encoding="utf-8"))
    state["done"].clear()
    (watch / "watch_state.json").write_text(json.dumps(state), encoding="utf-8")
    assert _score_until_checkpoint(run, watch, tmp_path / "scores", tmp_path / "cfg.yaml",
        TABLE, "B", 5500, actual, max_calls=1) == "pending"


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
        "schema": "foothold-manifest/1", "progress": {"completed_updates": 8001},
        "checkpoints": {checkpoint.name: digest}}), encoding="utf-8")
    (watch / "watch_state.json").write_text(json.dumps({
        "format": "foothold-ex40-score-watch/1", "arm": "B",
        "done": {"8000": {"state": row_state, "checkpoint_sha256": digest}}}),
        encoding="utf-8")
    (watch / "score_ledger.jsonl").write_text(json.dumps({
        "checkpoint_iteration": 8000, "checkpoint_sha256": digest,
        "run_dir": str(run), "checkpoint_path": str(checkpoint)}) + "\n", encoding="utf-8")
    monkeypatch.setattr(ex40_score_watch, "config", lambda _path: {
        "checkpoint_first": 8000, "checkpoint_stride": 250, "final_checkpoint_update": 8000})
    monkeypatch.setattr(ex40_supervisor, "_verified_score_slot", lambda *_args: "verified")
    monkeypatch.setattr(ex40_score_watch, "completion", lambda *_args: {"state": completion_state})
    monkeypatch.setattr(ex40_score_watch, "stage_end_updates", lambda *_args: {8000: "S2"})
    monkeypatch.setattr(ex40_score_watch, "stage_reports", lambda *_args, **_kwargs: {
        "state": "done", "published": 1, "first_pending": None,
        "first_hold": None})
    monkeypatch.setattr(ex40_supervisor, "_stage_report_delivery_ok", lambda *_args: True)
    monkeypatch.setattr(ex40_supervisor.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="fixture"))

    result = _score_until_checkpoint(run, watch, tmp_path / "scores", tmp_path / "cfg.yaml",
        TABLE, "B", 8000, digest, max_calls=1)
    assert result == expected


def test_final_checkpoint_sha_mismatch_cannot_be_consumed(tmp_path, monkeypatch):
    from foothold_s2 import ex40_score_watch, ex40_supervisor

    run, watch, scores, digest = _supervisor_slot_history(
        tmp_path, include_prior_5250=True, target_update=8000)
    (run / "model_8000.pt").write_bytes(b"changed final model")
    monkeypatch.setattr(ex40_score_watch, "stage_reports", lambda *_args, **_kwargs: {
        "state": "done", "published": 99, "first_pending": None,
        "first_hold": None})
    monkeypatch.setattr(ex40_supervisor, "_stage_report_delivery_ok", lambda *_args: True)

    result = _score_until_checkpoint(run, watch, scores, ex40_score_watch.DEFAULT_CONFIG,
        ex40_score_watch.DEFAULT_TABLE, "B", 8000, digest, max_calls=1)
    assert result == "unknown"


def test_supervised_execution_copy_calls_watchdog_without_touching_original():
    copy_script = Path(__file__).resolve().parents[1] / "run_ex40_b11.sh"
    original = copy_script.with_name("run_ex40.sh")
    script = copy_script.read_text(encoding="utf-8")
    assert "ex40_supervisor --supervise" in script
    assert "EX40_EXPECTED_FINISH" in script
    assert "EX40_TELEGRAM_SENDER:-C:/Users/AI-WS01/s2_lab/tools_lead/tg_send.py" in script
    assert "EX40_LAB_FEED:-C:/Users/AI-WS01/s2_lab/lab_status/ex40_stage_reports.json" in script
    assert "--telegram-sender \"$EX40_TELEGRAM_SENDER\" --lab-feed \"$EX40_LAB_FEED\"" in script
    assert original.is_file()
    assert "ex40_supervisor" not in original.read_text(encoding="utf-8")
