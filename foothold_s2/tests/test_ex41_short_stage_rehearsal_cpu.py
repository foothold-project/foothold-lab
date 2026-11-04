"""Short-stage EX-41 rehearsal contract tests, CPU only."""
from __future__ import annotations

import json
import ast
from pathlib import Path

import pytest

from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.curriculum.ex41_fixed import Clock
from foothold_s2.curriculum import w72
from foothold_s2.scripts.ex41_rehearsal_schedule import (
    STAGE_IDS, boundary_updates, d181_short_tables, parse_stage_updates,
)
from foothold_s2.scripts.ex41_startup import (
    configure_stage_rehearsal_plan, validate_rehearsal_request,
    validate_stage_rehearsal_mode,
)
from foothold_s2.tests.test_ex41_fixed_cpu import fixture as fixed_runtime_fixture
from foothold_s2.tests.ex41_runtime_fixture import commit_inputs
from foothold_s2 import ex41_score_watch as watch

TABLE = Path(__file__).parents[1] / "curriculum" / "ex41-fixed5000.yaml"
DEFAULT_EVAL = Path(__file__).parents[1] / "curriculum" / "ex40_score_config.json"


def test_short_table_parser_and_d181_two_cases():
    assert parse_stage_updates("2,2,2,2,2,2") == (2, 2, 2, 2, 2, 2)
    assert boundary_updates((2, 2, 2, 2, 2, 2)) == (3, 5, 7, 9, 11)
    cases = d181_short_tables()
    assert sum(cases["no_extension"]) == 12
    assert sum(cases["extension_500_scaled"]) == 12
    assert cases["no_extension"][-1] == 2
    assert cases["extension_500_scaled"][-2:] == (3, 1)
    for bad in ("2,2,2", "0,2,2,2,2,2", "6,2,2,2,2,2", "2,2,2,2,2,2,2"):
        with pytest.raises(ValueError):
            parse_stage_updates(bad)


def test_stage_table_is_rehearsal_only_and_production_rejects_it():
    table = parse_stage_updates("2,2,2,2,2,2")
    assert validate_stage_rehearsal_mode(table, 12, production_approved=False,
                                         startup_smoke=False)
    with pytest.raises(ValueError, match="rehearsal-only"):
        validate_stage_rehearsal_mode(table, 12, production_approved=True,
                                      startup_smoke=False)
    with pytest.raises(ValueError, match="rehearsal-only"):
        validate_stage_rehearsal_mode(table, 12, production_approved=False,
                                      startup_smoke=True)
    with pytest.raises(ValueError, match="update cap"):
        validate_stage_rehearsal_mode(table, 10, production_approved=False,
                                      startup_smoke=False)
    assert validate_rehearsal_request(12, "D:/mai-tmp/s2_lab/ex41_rehearsal_20261104_230000",
                                     "cuda:0", True, stage_updates=table).name.endswith("230000")


def test_every_train_start_rehearsal_revalidation_passes_the_short_stage_table():
    source = Path(__file__).parents[1] / "scripts" / "train_start.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "validate_rehearsal_request"]
    assert len(calls) == 3
    assert all(any(keyword.arg == "stage_updates" for keyword in node.keywords)
               for node in calls)


def test_in_memory_plan_uses_short_table_without_mutating_fixed_yaml():
    rows = parse_stage_updates("2,2,2,2,2,2")
    original = TABLE.read_bytes()
    plan = load_plan(TABLE, arm="B", smoke_boundaries=boundary_updates(rows))
    receipt = configure_stage_rehearsal_plan(plan, rows)
    assert tuple(stage.id for stage in plan.stages) == STAGE_IDS
    assert tuple(plan.clock_settings["durations"]) == rows
    assert plan.clock_settings["duration_updates"] == 12
    assert plan.clock_settings["interval_updates"] == 2
    assert plan.clock_settings["pause_limit_updates"] == 0
    assert receipt["transition_next_updates"] == [3, 5, 7, 9, 11]
    assert receipt["production_table_modified"] is False
    assert TABLE.read_bytes() == original


def test_rehearsal_runtime_applies_committed_w72_change_and_excludes_scores(tmp_path):
    rows = parse_stage_updates("2,2,2,2,2,2")
    boundaries = boundary_updates(rows)
    runtime, _consumer = fixed_runtime_fixture(tmp_path, smoke=boundaries)
    configure_stage_rehearsal_plan(runtime.plan, rows)
    runtime.plan.rehearsal_stage_updates = rows
    runtime.clock = Clock(runtime.plan.clock_settings)
    runtime.on_update_start(1)
    assert runtime.effective["stage_id"] == "S2a"
    snapshot = w72.read_committed_pair(runtime.plan.boundary_path,
                                       runtime.plan.approvals_path)
    rehearsal_boundary = runtime.plan.boundary_path.with_name(
        "ex41-fixed5000-rehearsal-boundary.yaml")
    runtime.plan.boundary_path = rehearsal_boundary
    snapshot["config"]["values"]["reward_weights"]["swing"] = -9.99
    commit_inputs(runtime, snapshot)
    receipt_cfg = w72.read_committed_pair(runtime.plan.boundary_path,
                                          runtime.plan.approvals_path)
    assert receipt_cfg["config"]["values"]["reward_weights"]["swing"] == -9.99
    configure_stage_rehearsal_plan(runtime.plan, rows, boundary_path=rehearsal_boundary)
    snapshot = w72.read_committed_pair(runtime.plan.boundary_path,
                                       runtime.plan.approvals_path)
    snapshot["config"]["values"]["reward_weights"]["swing"] = -9.98
    commit_inputs(runtime, snapshot)
    runtime.on_update_start(3)
    receipt = runtime.boundary_receipt()
    assert receipt["status"] == "applied"
    assert receipt["after"]["reward_weights"]["swing"] == -9.98
    assert any(row["path"] == "reward_weights.swing" for row in receipt["decisions"])
    for update in (5, 7, 9, 11, 13):
        runtime.on_update_start(update)
    assert runtime.effective["stage_id"] == "T0_prime"
    assert runtime.finished is True
    assert runtime.clock.pause_used == 0
    records = [json.loads(line) for line in
               (runtime.log_dir / "stage_log.jsonl").read_text(encoding="utf-8").splitlines()]
    excluded = [row for row in records if row.get("event") == "rehearsal_w72_evidence_excluded"]
    assert [row["iteration"] for row in excluded] == [3, 5, 7, 9, 11, 13]
    assert all(row["pause_budget_used"] == 0 for row in excluded)
    assert [row["stage"] for row in records if row.get("event") == "schedule_continue"] == [
        "S2b", "S2c", "S2d", "S2e", "T0_prime", "T0_prime"]


def test_watcher_reads_rehearsal_schedule_and_only_finds_checkpoint_slots(tmp_path):
    run = tmp_path / "run"
    report = run / "ex41_reports"
    report.mkdir(parents=True)
    cfg = report / "rehearsal_eval_config.json"
    cfg.write_bytes(DEFAULT_EVAL.read_bytes())
    schedule = {
        "format": "foothold-ex41-short-stage-rehearsal/1",
        "stage_updates": [2, 2, 2, 2, 2, 2],
        "eval_config_path": str(cfg.resolve()),
        "inject_one_measurement_failure_at": 2,
    }
    (report / "rehearsal_schedule.json").write_text(json.dumps(schedule), encoding="utf-8")
    for iteration in range(1, 13):
        (run / f"model_{iteration}.pt").write_bytes(f"m{iteration}".encode())
    rows = watch.candidates(run, watch.plan_for_run(TABLE, run))
    assert [row[0] for row in rows] == [2, 4, 6, 8, 10, 12]
    plan = watch.plan_for_run(TABLE, run)
    assert watch.due_evaluation_scopes(2, plan, run) == ("periodic", "auxiliary")
    assert watch.due_evaluation_scopes(1, plan, run) == ()
    state = watch.initial_state(run, TABLE, DEFAULT_EVAL)
    assert state["eval_config_sha256"] == watch.sha256(cfg)


def test_injected_p1_failure_retries_same_checkpoint_then_registers_p2_p3(tmp_path, monkeypatch):
    rows = parse_stage_updates("2,2,2,2,2,2")
    runtime, _consumer = fixed_runtime_fixture(tmp_path, smoke=boundary_updates(rows))
    plan = runtime.plan
    configure_stage_rehearsal_plan(plan, rows)
    plan.rehearsal_stage_updates = rows
    runtime.clock = Clock(plan.clock_settings)
    runtime.on_update_start(1)
    runtime.on_update_start(3)
    run = runtime.log_dir
    table = plan.path
    checkpoint = run / "model_2.pt"
    checkpoint.write_bytes(b"answer-known checkpoint m2")
    effective_sha256 = plan.effective_sha256
    report = run / "ex41_reports"
    report.mkdir(parents=True, exist_ok=True)
    eval_config = report / "rehearsal_eval_config.json"
    eval_config.write_bytes(DEFAULT_EVAL.read_bytes())
    (report / "rehearsal_schedule.json").write_text(json.dumps({
        "format": "foothold-ex41-short-stage-rehearsal/1",
        "stage_updates": list(rows), "eval_config_path": str(eval_config.resolve()),
        "inject_one_measurement_failure_at": 2,
    }), encoding="utf-8")
    (run / "manifest.json").write_text(json.dumps({
        "schema": "foothold-manifest/1", "progress": {"completed_updates": 3},
        "checkpoints": {checkpoint.name: watch.sha256(checkpoint)},
        "modes": {"ex41": {"effective_sha256": effective_sha256,
                              "plan_sha256": plan.sha256,
                              "parent": {"sha256": plan.parent_sha256}}},
    }), encoding="utf-8")
    state = watch.initial_state(run, table, DEFAULT_EVAL)
    monkeypatch.setattr(watch, "_stable", lambda path, *_args: watch.sha256(path))
    launched = []
    def child(argv, folder, **_kwargs):
        argv = list(argv)
        assert argv[argv.index("--scope") + 1] == "core"
        launched.append(argv[argv.index("--checkpoint") + 1])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "child.json").write_text(json.dumps({"state": "done", "rc": 0}), encoding="utf-8")
        return {"state": "done", "rc": 0, "pid": 4242}
    monkeypatch.setattr(watch, "hidden_child", child)
    monkeypatch.setattr(watch, "collect", lambda cp, stage, _source, active_plan, *_a, **_k: {
        "format": "foothold-ex41-score/1", "iteration": 2, "stage_id": stage,
        "checkpoint_path": str(cp), "checkpoint_sha256": watch.sha256(cp),
        "parent_sha256": active_plan.parent_sha256,
        "baseline_checkpoint_sha256": active_plan.parent_sha256,
        "schedule_sha256": active_plan.effective_sha256,
        "maintenance_pass": True, "stage_pass": False, "safety_stop": False,
        "metrics": {"maintenance_counts": {}, "stand_min_passed": 64},
        "evidence": [], "components": {}, "graduation_status": "not_judged",
        "evaluation_state": "complete", "evaluation_scope": "core_26_cells_rehearsal_only",
        "auxiliary_missing": [],
    })
    specs = [
        {"id": "axis", "phase": "axis_v2", "kind": "eval", "priority": 2, "owner": "cpu-test",
         "authorization_ref": "axis-condition", "needs_approval": False},
        {"id": "render", "phase": "video", "kind": "render", "priority": 3, "owner": "cpu-test",
         "authorization_ref": "render-condition", "needs_approval": False},
    ]
    monkeypatch.setattr(watch, "stage_end_queue_specs", lambda *_a, **_k: [dict(row) for row in specs])
    monkeypatch.setattr(watch, "register_stage_end_queue_jobs",
                        lambda _path, selected: [{**row, "condition": row["authorization_ref"],
                                                  "state": "대기"} for row in selected])
    first = watch.process_once(run, tmp_path / "out", tmp_path / "scores", table, state,
                               eval_config=DEFAULT_EVAL, execute=True,
                               sleep=lambda _seconds: None)
    assert first["state"] == "measurement_retry_pending"
    assert first["measurement_state"] == "failed_retryable"
    assert first["judgement_state"] == "not_judged"
    assert not launched
    second = watch.process_once(run, tmp_path / "out", tmp_path / "scores", table, state,
                                eval_config=DEFAULT_EVAL, execute=True,
                                sleep=lambda _seconds: None)
    assert second["state"] == "complete" and second["iteration"] == 2
    assert second["attempt_count"] == 2 and second["judgement_state"] == "pass"
    assert launched == [str(checkpoint)]
    receipt = json.loads((tmp_path / "out" / f"model_2_{watch.sha256(checkpoint)[:12]}_retry02" /
                          "rehearsal_queue_registration.json").read_text(encoding="utf-8"))
    assert receipt["rehearsal"] is True
    assert [(row["priority"], row["kind"], row["needs_approval"])
            for row in receipt["jobs"]] == [(2, "eval", True), (3, "render", True)]


def test_c3_expected_head_mismatch_is_a_real_preflight_rejection(tmp_path):
    import subprocess
    import tempfile
    from foothold_s2.ex41_start_preflight import inspect_fixed_worktree

    root = Path(tempfile.mkdtemp(dir=tmp_path)) / "repo"
    root.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args],
                                       stderr=subprocess.PIPE).decode().strip()
    git("init", "-q")
    git("config", "user.name", "CPU test")
    git("config", "user.email", "cpu@example.invalid")
    (root / "seed.txt").write_text("fixture\n", encoding="utf-8")
    git("add", "seed.txt")
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    git("checkout", "--detach", "HEAD")
    actual = git("rev-parse", "HEAD")
    with pytest.raises(ValueError, match="expected commit"):
        inspect_fixed_worktree(root, expected_head="0" * 40)
    refusal = {"state": "rejected", "expected_head": "0" * 40,
               "actual_head": actual, "reason": "fixed HEAD mismatch"}
    path = tmp_path / "C3-head-mismatch.json"
    path.write_text(json.dumps(refusal, sort_keys=True), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["state"] == "rejected"


def test_m10_readback_warning_is_durable_and_uses_alert_delivery_receipt(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from foothold_s2 import ex41_ops

    sent = []
    monkeypatch.setattr(ex41_ops, "_send_orchestration",
                        lambda subject, body: sent.append((subject, body)) or True)
    monkeypatch.setattr(ex41_ops, "_send_telegram", lambda _body: True)
    runtime = SimpleNamespace(dr_scale=lambda _update: .5, effective={"stage_id": "S2a"})
    env = SimpleNamespace(_ex40_dr_scale=.51, _ex41_stage_id="S2a")
    row = ex41_ops.record_boundary_runtime_readback(
        runtime, SimpleNamespace(scale=.51), env, tmp_path, 3, inject_delta=.01)
    assert row["state"] == "warning" and row["absolute_dr_delta"] >= .01
    assert row["actual_dr_scale"] == .51 and row["observed_dr_scale"] == .52
    assert row["orchestration_received"] is True
    assert len(sent) == 1
    persisted = json.loads((tmp_path / "ex41_reports" /
                            "boundary_runtime_readback.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert persisted["delivery_receipt"] == row["delivery_receipt"]
    delivery = json.loads(Path(row["delivery_receipt"]).read_text(encoding="utf-8"))
    assert delivery["channels"]["orchestration"]["state"] == "sent"


def test_rehearsal_p2_p3_jobs_register_in_real_dispatch_queue_as_approval_gated(tmp_path):
    rows = [
        {"id": "REHEARSAL-axis-2", "phase": "axis_v2", "authorization_ref": "R:axis:2",
         "priority": 2, "kind": "eval", "gpu": 1, "owner": "cpu-test",
         "output_path": str(tmp_path / "axis"), "done_files": [str(tmp_path / "axis" / "done.json")],
         "cwd": str(Path.cwd()), "argv": ["python", "-c", "pass"], "needs_approval": True},
        {"id": "REHEARSAL-render-2", "phase": "render", "authorization_ref": "R:render:2",
         "priority": 3, "kind": "render", "gpu": 1, "owner": "cpu-test",
         "output_path": str(tmp_path / "render"), "done_files": [str(tmp_path / "render" / "done.json")],
         "cwd": str(Path.cwd()), "argv": ["python", "-c", "pass"], "needs_approval": True},
    ]
    queue_path = tmp_path / "queue.json"
    registered = watch.register_stage_end_queue_jobs(queue_path, rows)
    assert [row["priority"] for row in registered] == [2, 3]
    assert [row["kind"] for row in registered] == ["eval", "render"]
    assert all(row["needs_approval"] is True for row in registered)
    queue = json.loads(queue_path.read_text(encoding="utf-8-sig"))
    assert [row["title"] for row in queue["items"]] == [row["id"] for row in rows]
    assert all(row["state"] == "대기" for row in queue["items"])
