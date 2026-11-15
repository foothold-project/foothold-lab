from __future__ import annotations

import hashlib
import json

import pytest

import foothold_s2.eval.ex41_push250_watch as push250_watch
from foothold_s2.eval.ex41_push_ladder import (
    PUSH250_MAGNITUDES_MPS,
    TERRAIN_CASES,
    build_push250_case_grid,
    summarize_push250,
)
from foothold_s2.eval.ex41_push250_watch import (
    _explicit_device,
    build_child_argv,
    checkpoint_for_update,
    output_path_for_global_iteration,
    score_watch_attempt_finished,
    wait_for_checkpoint_target,
    wait_for_score_watch_attempt,
)


def test_push250_grid_is_d171_minimal_profile():
    cases = build_push250_case_grid()
    assert PUSH250_MAGNITUDES_MPS == (1.0, 1.5, 2.0)
    assert len(cases) == 3 * 3 * 8
    assert {row["terrain"] for row in cases} == set(TERRAIN_CASES)
    assert {row["magnitude_mps"] for row in cases} == {1.0, 1.5, 2.0}
    assert {row["direction_deg"] for row in cases} == {0, 45, 90, 135, 180, 225, 270, 315}
    assert {(row["map_mode"], row["command"], row["envs"], row["level"])
            for row in cases} == {("eval_gt", "walk_1.0", 64, 0)}


def test_push250_criterion_uses_worst_direction_at_1_5_only():
    rows = []
    for magnitude in PUSH250_MAGNITUDES_MPS:
        for direction in (0, 45, 90, 135, 180, 225, 270, 315):
            survivors = 57 if magnitude == 1.5 and direction == 90 else 64
            rows.append({"terrain": "flat", "map_mode": "eval_gt", "command": "walk_1.0",
                         "magnitude_mps": magnitude, "direction_deg": direction,
                         "envs": 64, "survivors_after_5s": survivors,
                         "recovery_times_s": [0.5] * survivors + [None] * (64 - survivors),
                         "max_tilt_rad": 0.2})
    summary = summarize_push250(rows, terrain="flat")
    assert summary["d171_1_5_worst_direction"]["survival_fraction"] == 57 / 64
    assert summary["d171_1_5_worst_direction"]["passed"] is False
    assert set(summary["record_only_magnitudes"]) == {"1.0", "2.0"}
    assert summary["record_only_magnitudes"]["2.0"]["survival_fraction"] == 1.0


def test_push250_rejects_missing_or_duplicate_direction_cell():
    cases = build_push250_case_grid(terrain="flat")
    rows = [{"terrain": row["terrain"], "map_mode": row["map_mode"], "command": row["command"],
             "magnitude_mps": row["magnitude_mps"], "direction_deg": row["direction_deg"],
             "envs": 64, "survivors_after_5s": 64, "recovery_times_s": [0.2] * 64,
             "max_tilt_rad": 0.1} for row in cases]
    with pytest.raises(ValueError, match="unique cells"):
        summarize_push250(rows[:-1], terrain="flat")
    with pytest.raises(ValueError, match="unique cells"):
        summarize_push250(rows + [rows[0]], terrain="flat")


def test_checkpoint_requires_completed_update_manifest_score_and_sha(tmp_path):
    run_dir = tmp_path / "run"
    score_dir = tmp_path / "scores"
    run_dir.mkdir()
    score_dir.mkdir()
    checkpoint = run_dir / "model_500.pt"
    checkpoint.write_bytes(b"known checkpoint")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = {"progress": {"completed_updates": 500},
                "checkpoints": {"model_500.pt": digest}}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    score = {"evaluation_state": "complete", "checkpoint_iteration": 500,
             "checkpoint_sha256": digest}
    (score_dir / f"score_500_{digest[:12]}.json").write_text(json.dumps(score), encoding="utf-8")
    ready = checkpoint_for_update(run_dir, score_dir, 500)
    assert ready["checkpoint"] == checkpoint
    assert ready["sha256"] == digest
    assert checkpoint_for_update(run_dir, score_dir, 501) is None
    score["checkpoint_sha256"] = "0" * 64
    (score_dir / f"score_500_{digest[:12]}.json").write_text(json.dumps(score), encoding="utf-8")
    assert checkpoint_for_update(run_dir, score_dir, 500) is None
    score.update(checkpoint_sha256=digest, evaluation_state="HOLD", maintenance_pass=False)
    (score_dir / f"score_500_{digest[:12]}.json").write_text(json.dumps(score), encoding="utf-8")
    held = checkpoint_for_update(run_dir, score_dir, 500)
    assert held["measurement_state"] == "HOLD"
    assert held["judgement_state"] == "not_judged"


def test_checkpoint_wait_survives_failed_and_completed_training_states_until_resume(tmp_path):
    statuses = iter((
        {"state": "failed", "iter": 700},
        {"state": "complete", "iter": 700},
        {"state": "running", "iter": 701},
    ))
    state_rows = []
    probes = {"count": 0}
    ready = {"local_iteration": 750, "sha256": "a" * 64}

    def checkpoint_reader(run_dir, score_dir, local_iteration):
        probes["count"] += 1
        return ready if probes["count"] == 4 else None

    result = wait_for_checkpoint_target(
        tmp_path / "run", tmp_path / "scores", 750,
        state_path=tmp_path / "watcher_state.json",
        checkpoint_reader=checkpoint_reader,
        status_reader=lambda: next(statuses),
        state_writer=lambda path, row: state_rows.append(row),
        sleep=lambda seconds: None,
    )

    assert result == ready
    assert probes["count"] == 4
    assert [row["state"] for row in state_rows] == [
        "waiting_for_training_resume", "waiting_for_training_resume",
        "waiting_for_score_and_stable_checkpoint",
    ]
    assert state_rows[0]["trainer_state"] == "failed"
    assert state_rows[1]["trainer_state"] == "complete"


def test_push250_waits_for_score_watch_attempt_to_close_before_gpu1_claim(tmp_path):
    root = tmp_path / "eval" / "score-watch"
    score = tmp_path / "eval" / "scores" / "score_1000_aaaaaaaaaaaa.json"
    score.parent.mkdir(parents=True)
    score.write_text('{"evaluation_state":"complete"}', encoding="utf-8")
    score_sha = hashlib.sha256(score.read_bytes()).hexdigest()
    key = f"1000_{'a' * 64}"
    assert score_watch_attempt_finished(root, 1000, "a" * 64) == (
        False, "score_watch_state_missing")

    root.mkdir(parents=True)
    attempt_dir = root / "model_1000_aaaaaaaaaaaa"
    attempt_dir.mkdir()
    running = {"iteration": 1000, "checkpoint_sha256": "a" * 64, "state": "running"}
    (attempt_dir / "attempt.json").write_text(json.dumps(running), encoding="utf-8")
    (root / "watch_state.json").write_text(json.dumps({"done": {}}), encoding="utf-8")
    assert score_watch_attempt_finished(root, 1000, "a" * 64) == (
        False, "score_watch_checkpoint_not_closed")

    terminal = {"iteration": 1000, "checkpoint_sha256": "a" * 64,
                "state": "complete", "score_path": str(score), "score_sha256": score_sha}
    (attempt_dir / "attempt.json").write_text(json.dumps(terminal), encoding="utf-8")
    (root / "watch_state.json").write_text(json.dumps({"done": {key: terminal}}), encoding="utf-8")
    assert score_watch_attempt_finished(root, 1000, "a" * 64) == (
        True, "score_watch_attempt_closed")


def test_push250_does_not_treat_unclosed_or_tampered_score_watch_receipt_as_idle(tmp_path):
    root = tmp_path / "score-watch"
    score = tmp_path / "score_1250.json"
    score.write_text('{"evaluation_state":"complete"}', encoding="utf-8")
    key = f"1250_{'b' * 64}"
    attempt = {"iteration": 1250, "checkpoint_sha256": "b" * 64,
               "state": "HOLD", "score_path": str(score),
               "score_sha256": "0" * 64}
    attempt_dir = root / "model_1250_bbbbbbbbbbbb"
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "attempt.json").write_text(json.dumps(attempt), encoding="utf-8")
    (root / "watch_state.json").write_text(json.dumps({"done": {key: attempt}}), encoding="utf-8")
    assert score_watch_attempt_finished(root, 1250, "b" * 64) == (
        False, "score_watch_score_receipt_unverified")


def test_push250_wait_gate_records_wait_and_returns_only_after_score_watch_close(tmp_path, monkeypatch):
    checks = iter(((False, "score_watch_checkpoint_not_closed"),
                   (True, "score_watch_attempt_closed")))
    monkeypatch.setattr(push250_watch, "score_watch_attempt_finished",
                        lambda *_args: next(checks))
    state_path = tmp_path / "watcher_state.json"
    result = wait_for_score_watch_attempt(
        tmp_path / "score-watch", 1250, "c" * 64, state_path=state_path,
        poll_seconds=0, sleep=lambda _seconds: None)
    assert result["state"] == "score_watch_closed"
    assert result["checks"] == 2
    assert json.loads(state_path.read_text(encoding="utf-8"))["state"] == (
        "waiting_for_score_watch_evaluation")


def test_output_iteration_uses_global_m6000_parent_offset(tmp_path):
    assert output_path_for_global_iteration(tmp_path, 6000).name == "6000.json"
    assert output_path_for_global_iteration(tmp_path, 6500).name == "6500.json"
    with pytest.raises(ValueError):
        output_path_for_global_iteration(tmp_path, 0)


def test_child_command_reads_device_role_and_matches_d171_request(tmp_path):
    argv = build_child_argv(checkpoint=tmp_path / "model_500.pt", out=tmp_path / "flat",
                            terrain="flat")
    assert "--push-ladder-profile" in argv
    assert argv[argv.index("--push-ladder-profile") + 1] == "push250"
    assert argv[argv.index("--push-ladder-command") + 1] == "walk_1.0"
    assert argv[argv.index("--push-ladder-map-mode") + 1] == "eval_gt"
    assert argv[argv.index("--device") + 1] == "cuda:1"
    assert argv[argv.index("--envs") + 1] == "1536"
    argv0 = build_child_argv(checkpoint=tmp_path / "model_500.pt", out=tmp_path / "flat0",
                             terrain="flat", device="cuda:0")
    assert argv0[argv0.index("--device") + 1] == "cuda:0"


def test_push250_marker_path_follows_the_configured_evaluation_role():
    assert push250_watch.priority_marker_for_device("cuda:0").name == "PRIORITY_BUSY_GPU0"
    assert push250_watch.priority_marker_for_device("cuda:1").name == "PRIORITY_BUSY_GPU1"
    with pytest.raises(ValueError, match="unsupported configured device"):
        push250_watch.priority_marker_for_device("cuda:2")


def test_push250_watcher_refuses_to_resume_with_a_changed_device_contract(tmp_path):
    from copy import deepcopy
    from foothold_s2.experiment_registry import (
        device_contract, device_contract_sha256, operational_definition,
    )

    definition = operational_definition("EX-41")
    state = {"device_contract": device_contract(definition),
             "device_contract_sha256": device_contract_sha256(definition)}
    out = tmp_path / "push250"
    out.mkdir()
    (out / "watcher_state.json").write_text(json.dumps(state), encoding="utf-8")
    changed = deepcopy(definition)
    changed["devices"]["evaluation"] = "cuda:0"
    with pytest.raises(ValueError, match="device identity differs"):
        push250_watch.watch(tmp_path / "run", tmp_path / "scores", out,
                            first_local_update=500, definition=changed)


def test_gpu_assignment_ignores_shared_context_on_gpu0():
    assert _explicit_device(["python.exe", "train.py", "--device=cuda:0"]) == "cuda:0"
    assert _explicit_device(["python.exe", "record_c_layer.py", "--device", "cuda:1"]) == "cuda:1"
    assert _explicit_device(["python.exe", "score_watch.py"]) is None


def test_push250_records_measurement_hold_and_advances_without_gpu_run(tmp_path, monkeypatch):
    run = tmp_path / 'run'; run.mkdir()
    score_dir = tmp_path / 'scores'; score_dir.mkdir()
    checkpoint = run / 'model_500.pt'; checkpoint.write_bytes(b'known failed measurement checkpoint')
    pinned = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    score_path = score_dir / f'score_500_{pinned[:12]}.json'
    score_path.write_text(json.dumps({'evaluation_state':'HOLD','maintenance_pass':False}), encoding='utf-8')
    ready = {'local_iteration':500, 'checkpoint':checkpoint, 'sha256':pinned,
             'score':score_path, 'score_sha256':hashlib.sha256(score_path.read_bytes()).hexdigest(),
             'measurement_state':'HOLD'}
    calls = []
    class StopAfterAdvance(Exception): pass
    def checkpoint_wait(_run, _scores, local_iteration, **_kwargs):
        calls.append(local_iteration)
        if local_iteration == 500:
            return ready
        raise StopAfterAdvance
    monkeypatch.setattr(push250_watch, 'wait_for_checkpoint_target', checkpoint_wait)
    monkeypatch.setattr(push250_watch, 'wait_for_score_watch_attempt',
                        lambda *_args, **_kwargs: {'state':'score_watch_closed'})
    monkeypatch.setattr(push250_watch, 'evaluate_checkpoint',
                        lambda *_args, **_kwargs: pytest.fail('measurement HOLD must skip GPU evaluation'))
    out = tmp_path / 'out'
    with pytest.raises(StopAfterAdvance):
        push250_watch.watch(run, score_dir, out, first_local_update=500, poll_seconds=0)
    receipt = json.loads((out / '6500.json').read_text(encoding='utf-8'))
    assert receipt['state'] == 'HOLD'
    assert receipt['measurement_state'] == 'failed'
    assert receipt['judgement_state'] == 'not_judged'
    assert receipt['advanced_to_local_iteration'] == 750
    assert calls == [500, 750]
