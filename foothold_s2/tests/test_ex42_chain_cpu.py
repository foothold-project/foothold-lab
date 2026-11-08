from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import EX42Runtime
from foothold_s2.eval.ex42_component_receipts import SCHEMA, sha256
from foothold_s2.eval.ex42_video_delivery import KINDS, VIDEO_RULE_VERSION, freeze_requests
from foothold_s2.ex42_status import read_status
from foothold_s2.runners.start_runner import StartRunner
from foothold_s2.tests.start_fake_env import FakeStartEnv, train_cfg


ROOT = Path(__file__).parents[2]
TABLE = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
APPROVALS = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"


def make_chain(tmp_path, *, alert_sender=None, score_argv_factory=None,
               boundary_provider=None, p1_interval=250):
    source_plan = EX42Plan.load(TABLE)
    parent_bytes = b"known EX-41 m12000 parent fixture"
    parent_sha = hashlib.sha256(parent_bytes).hexdigest()
    doc = copy.deepcopy(source_plan.document)
    doc["stage_zero"]["parent"]["sha256"] = parent_sha
    plan = EX42Plan(source_plan.path, doc, source_plan.sha256)
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "model_6000.pt").write_bytes(parent_bytes)
    (parent / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": 6000},
        "checkpoints": {"model_6000.pt": parent_sha},
    }), encoding="utf-8")
    run = tmp_path / "run"
    return EX42Runtime.training_chain(
        plan=plan, approvals_path=APPROVALS,
        parent_manifest_path=parent / "manifest.json", run_dir=run,
        repo_root=ROOT, queue_path=tmp_path / "gpu/queue.json",
        alert_sender=alert_sender, score_argv_factory=score_argv_factory,
        boundary_provider=boundary_provider, p1_interval=p1_interval,
    ), run


def _complete_map_matrix():
    from foothold_s2.eval.map_mode_cells import commands
    aliases = {"gt": "eval_gt", "pred": "eval_pred", "off": "probe_prop_only"}
    return [{"command": command, "map_mode": aliases[mode],
             "role": "record_only" if mode == "off" else "judge"}
            for mode in ("gt", "pred", "off")
            for command in commands("extended")]


def test_parent_manifest_identity_resolves_real_name_by_sha(tmp_path):
    chain, run = make_chain(tmp_path)
    start = json.loads((run / "startup_receipt.json").read_text(encoding="utf-8"))
    assert start["state"] == "chain_ready_not_launch_authorized"
    assert start["production_launch_allowed"] is False
    assert start["parent"]["manifest_checkpoint_key"] == "model_6000.pt"
    assert start["parent"]["cumulative_update"] == 12000
    assert start["parent"]["checkpoint_sha256"] == chain.parent["checkpoint_sha256"]


def test_runtime_launch_remains_fail_closed_while_plan_is_preparation_only(tmp_path):
    plan = EX42Plan.load(TABLE)
    assert plan.document["status"] == "preparation_only"
    gate_report = tmp_path / "gates-closed.md"
    rows = ["| Gate | Issue | Risk | Guard | State | Owner |", "|---|---|---|---|---|---|"]
    rows.extend(f"| G{index:02d} | x | x | x | 검증 완료 | fixture |" for index in range(1, 34))
    gate_report.write_text("\n".join(rows), encoding="utf-8")
    try:
        EX42Runtime(plan, 3072, "cuda:0", tmp_path,
                    approvals_path=APPROVALS, graduation_path=None,
                    terrain_manifest_path=None, gate_report_path=gate_report)
    except ValueError as exc:
        assert "preparation-only runtime is blocked" in str(exc)
    else:
        raise AssertionError("EX-42 preparation-only plan unexpectedly opened runtime launch")


def test_runtime_consumes_all_33_gate_rows_and_blocks_g11_only_counterexample(tmp_path):
    plan = EX42Plan.load(TABLE)
    gate_report = tmp_path / "analyst-register.md"
    rows = ["| Gate | Risk | Guard | Evidence | State | Owner |",
            "|---|---|---|---|---|---|"]
    rows.extend(
        f"| G{index:02d} · R{index} incident | x | x | x | "
        f"{'예행 대기' if index == 11 else '검증 완료'} | fixture |"
        for index in range(1, 34))
    gate_report.write_text("\n".join(rows), encoding="utf-8")
    from foothold_s2.ex42_gate_checks import open_gate_rows

    # The exact 33-row analyst counterexample must be consumed by EX42Runtime,
    # not only by the separate ops-check command.
    assert len(gate_report.read_text(encoding="utf-8").splitlines()) - 2 == 33
    assert open_gate_rows(gate_report) == ["G11"]
    try:
        EX42Runtime(plan, 3072, "cuda:0", tmp_path,
                    approvals_path=APPROVALS, graduation_path=None,
                    terrain_manifest_path=None, gate_report_path=gate_report)
    except ValueError as exc:
        assert "33-row gate register" in str(exc)
        assert "G11" in str(exc)
    else:
        raise AssertionError("EX-42 runtime ignored the open G11 launch gate")


def test_transition_gap_applies_approved_dr_and_registers_priority_one(tmp_path):
    delivered = []
    chain, run = make_chain(tmp_path, alert_sender=delivered.append)
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    checkpoint_bytes = b"model 1000"
    checkpoint_sha = hashlib.sha256(checkpoint_bytes).hexdigest()
    (checkpoint_dir / "model_1000.pt").write_bytes(checkpoint_bytes)
    (checkpoint_dir / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": 1000},
        "checkpoints": {"model_1000.pt": checkpoint_sha},
    }), encoding="utf-8")

    queued = chain.register_checkpoint_p1(
        iteration=1000, checkpoint_dir=checkpoint_dir,
        score_argv=["python", "-m", "known.score_command"],
    )
    queue = json.loads((tmp_path / "gpu/queue.json").read_text(encoding="utf-8"))
    assert len(queue["items"]) == 1
    assert queued["checkpoint_sha256"] == checkpoint_sha
    assert queued["stage_id"] == "EX42_0_T0_prime"
    assert queue["items"][0]["priority"] == 1 and queue["items"][0]["gpu"] == 1
    assert queue["items"][0]["argv"] == ["python", "-m", "known.score_command"]

    params = run / "params"
    params.mkdir()
    (params / "env.yaml").write_text(
        "commands: {}\nobservations:\n  policy:\n    map_mode: gt\n"
        "events: {}\nscene:\n  robot:\n    actuators: {}\n"
        "rewards: {}\ncurriculum:\n  terrain_levels: 5\n", encoding="utf-8")
    (params / "agent.yaml").write_text("algorithm: {}\n", encoding="utf-8")
    env = SimpleNamespace(_ex40_dr_scale=0.4)
    transition = chain.transition(
        env, "E0", boundary_iteration=1001, expected_score_iteration=1000,
        observed_score_iteration=None, checkpoint_sha256=checkpoint_sha,
    )
    assert transition["status"] == "measurement_gap"
    assert transition["applied_scale"] == 1.0
    assert env._ex40_dr_scale == 1.0 and env._ex42_stage_id == "E0"
    assert transition["automatic_action_receipt"] == {
        "field": "domain_randomization", "state": "approved_value_selected",
        "decision_id": chain.consumer.decision_id, "boundary": "E0",
        "value": 1.0, "approval_validated": True,
        "runtime_application": "not_implemented_preparation_only"}
    assert transition["alert_receipt"]["delivery"] == "accepted"
    assert len(delivered) == 1
    events = [json.loads(line) for line in (run / "ex42_application.jsonl").read_text().splitlines()]
    boundary = next(row for row in events if row.get("stage_after") == "E0")
    status = read_status(run / "train_start_status.json")["value"]
    alert = json.loads((run / "alerts.jsonl").read_text().splitlines()[0])
    assert all(row["checkpoint_sha256"] == checkpoint_sha for row in (boundary, status, alert))
    assert all(row["plan_sha256"] == chain.plan.sha256 for row in (boundary, status, alert))
    assert all(row["boundary_iteration"] == 1001 for row in (boundary, status, alert))

    report = chain.stage_report(stage_id="E0", boundary_iteration=1001,
                                checkpoint_sha256=checkpoint_sha)
    assert report["state"] == "incomplete"
    assert set(report["component_states"].values()) == {"MISSING_OR_MISMATCHED"}
    assert report["checkpoint_sha256"] == boundary["checkpoint_sha256"]
    assert report["plan_sha256"] == boundary["plan_sha256"]


def _w35_fixtures(tmp_path, checkpoint_sha):
    plan_sha = EX42Plan.load(TABLE).sha256
    number_source = tmp_path / "score.json"
    number_source.write_text('{"metric":1}', encoding="utf-8")
    number = {"receipt": {"schema": SCHEMA, "state": "PASS",
        "checkpoint_sha256": checkpoint_sha, "stage_name": "EX42_0_T0_prime",
        "plan_sha256": plan_sha,
        "result_path": str(number_source),
        "result_sha256": sha256(number_source)}}

    tile = {"env": 0, "kind": "flat", "level": 0, "col": 0}
    terrain_meta = {"selected_environment": {"env_id": 0, "kind": "flat", "level": 0, "col": 0},
        "task_selection": {"selected_tile": tile,
            "fixed_assignment": {"assignment_sha256": "a" * 64}},
        "segments": [["walk", [0.5, 0, 0], 1.0]]}
    review = tmp_path / "review.json"
    review.write_text(json.dumps(terrain_meta), encoding="utf-8")
    raw = tmp_path / "review_feet.npz"
    np.savez(raw, t=np.array([0.0]), seg=np.array([0]),
        terrain_kind=np.array(["flat"]), terrain_level=np.array([0]),
        terrain_env=np.array([0]), terrain_col=np.array([0]),
        terrain_assignment_sha256=np.array(["a" * 64]))
    terrain = {"review_json": str(review), "raw_npz": str(raw),
               "identity": {"checkpoint_sha256": checkpoint_sha,
                   "plan_sha256": plan_sha, "stage_name": "EX42_0_T0_prime"},
               "selection": {"state": "selected", "tile": tile}}

    w78_row = {"distance": 1.0, "case": "stairs_side_left",
        "requested_kinds": ["stairs"], "terrain_assignment_sha256": "d" * 64,
        "terrain_tiles": [{"env": 0, "kind": "stairs", "level": 0, "column": 0}],
        "phase_steps": [50]}
    w78_receipt = {"state": "done", "run_identity": {"code_head": "c" * 40},
        "source_sha256": {"terrain_skill_v2_run.py": "d" * 64},
        "checkpoint_sha256": checkpoint_sha, "checkpoint_iter": 1000,
        "plan_sha256": plan_sha, "stage_name": "EX42_0_T0_prime",
        "eval_seed": 42, "envs": 64, "levels": [0], "start_angles_deg": [0],
        "dt_s": 0.02, "dr_off": True, "curriculum_off": True,
        "mode_selection": ["eval_gt"], "case_selection": ["stairs_side_left"],
        "modes": {"eval_gt": {"L0_a000_stairs_side_left": w78_row}}}
    w78 = {"full": w78_receipt, "units": [copy.deepcopy(w78_receipt)],
        "queue": {"items": [{"id": 1, "gpu": 1, "priority": 3,
                               "kind": "eval", "state": "대기"}]}, "unit_id": 1}

    loader_sha, composer_sha = "e" * 64, "f" * 64
    plan = freeze_requests(checkpoint_sha256=checkpoint_sha, plan_sha256=plan_sha,
        stage_name="EX42_0_T0_prime", requests=[{
            "kind": kind, "map_mode": "eval_gt",
            "terrain_kind": "flat" if kind == "A" else "stairs",
            "terrain_level": 0, "segment": "fwd1.0"} for kind in sorted(KINDS)])
    receipts = []
    first_video, first_digest, first_request = None, None, None
    for row in plan["requests"]:
        video = tmp_path / f"{row['id']}.mp4"
        video.write_bytes(row["id"].encode())
        digest = sha256(video)
        audit_path = tmp_path / f"{row['id']}.audit.json"
        audit_path.write_text(json.dumps({"pass": True, "issue_count": 0,
            "frames": 10, "video_sha256": digest, "loader_sha256": loader_sha,
            "composer_sha256": composer_sha, "video_rule_version": VIDEO_RULE_VERSION}),
            encoding="utf-8")
        receipt = {**row, "request_id": row["id"], "state": "PASS", "rc": 0,
            "video_path": str(video), "video_sha256": digest,
            "audit_path": str(audit_path), "expected_frames": 10,
            "video_rule_version": VIDEO_RULE_VERSION,
            "loader_sha256": loader_sha, "composer_sha256": composer_sha}
        receipts.append(receipt)
        if first_video is None:
            first_video, first_digest, first_request = video, digest, receipt["request_id"]
    playlist = tmp_path / "all.m3u8"
    playlist.write_text("#EXTM3U\n" + "\n".join(r["video_path"] for r in receipts),
                        encoding="utf-8")
    sample = {"plan": plan, "receipt": {"request_id": first_request, "state": "PASS",
        "rc": 0, "video_rule_version": VIDEO_RULE_VERSION,
        "video_path": str(first_video), "video_sha256": first_digest,
        "audit_path": receipts[0]["audit_path"], "expected_frames": 10,
        "loader_sha256": loader_sha, "composer_sha256": composer_sha},
        "approval": {"state": "APPROVED", "request_id": first_request,
                     "video_sha256": first_digest},
        "loader_sha256": loader_sha, "composer_sha256": composer_sha}
    delivery = {"plan": plan, "receipts": receipts, "playlist": str(playlist),
        "loader_sha256": loader_sha, "composer_sha256": composer_sha,
        "sample_approval": sample["approval"]}
    return number, terrain, w78, sample, delivery


def test_w35_five_consumers_execute_through_one_path_and_failure_isolated(tmp_path):
    chain, _run = make_chain(tmp_path)
    checkpoint_sha = "a" * 64
    args = _w35_fixtures(tmp_path, checkpoint_sha)
    results = chain.run_w35_components(
        stage_id="EX42_0_T0_prime", checkpoint_sha256=checkpoint_sha,
        local_iteration=1000,
        number=args[0], terrain=args[1], w78=args[2], sample=args[3], delivery=args[4])
    assert {key: row["state"] for key, row in results.items()} == {
        "number": "PASS", "terrain": "PASS", "w78": "PASS",
        "video_sample": "PASS", "video_delivery": "PASS"}
    assert len(list((_run / "components").glob("*.json"))) == 5
    report = chain.stage_report(stage_id="EX42_0_T0_prime", boundary_iteration=1000,
                                checkpoint_sha256=checkpoint_sha)
    assert report["state"] == "complete"

    bad_number = {"receipt": {**args[0]["receipt"], "result_sha256": "0" * 64}}
    retry = chain.run_w35_components(
        stage_id="EX42_0_T0_prime", checkpoint_sha256=checkpoint_sha,
        local_iteration=1000,
        number=bad_number, terrain=args[1], w78=args[2], sample=args[3], delivery=args[4])
    assert retry["number"]["state"] == "unknown"
    assert all(retry[key]["state"] == "PASS" for key in
               ("terrain", "w78", "video_sample", "video_delivery"))

    wrong_identity_terrain = {**args[1], "identity": {
        **args[1]["identity"], "checkpoint_sha256": "9" * 64}}
    mismatch = chain.run_w35_components(
        stage_id="EX42_0_T0_prime", checkpoint_sha256=checkpoint_sha,
        local_iteration=1000,
        number={"receipt": {**args[0]["receipt"], "result_sha256": "0" * 64}},
        terrain=wrong_identity_terrain, w78=args[2], sample=args[3], delivery=args[4])
    assert mismatch["terrain"]["state"] == "unknown"
    assert mismatch["terrain"]["reason"].startswith("ValueError: terrain identity mismatch")
    assert mismatch["w78"]["state"] == "PASS"


def test_p1_rejects_missing_or_wrong_checkpoint_manifest_sha(tmp_path):
    chain, _run = make_chain(tmp_path)
    checkpoint_dir = tmp_path / "bad-checkpoints"
    checkpoint_dir.mkdir()
    data = b"checkpoint N"
    (checkpoint_dir / "model_250.pt").write_bytes(data)
    (checkpoint_dir / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": 250},
        "checkpoints": {"model_250.pt": "0" * 64},
    }), encoding="utf-8")
    try:
        chain.register_checkpoint_p1(iteration=250, checkpoint_dir=checkpoint_dir,
                                     score_argv=["python", "score.py"])
    except ValueError as exc:
        assert "manifest-published" in str(exc)
    else:
        raise AssertionError("P1 accepted a checkpoint with an incorrect manifest SHA")


def test_p1_collection_failure_is_retryable_but_completed_judgment_hold_is_not(tmp_path):
    chain, run = make_chain(tmp_path)
    checkpoint_bytes = b"valid model 250 bytes"
    checkpoint_sha = hashlib.sha256(checkpoint_bytes).hexdigest()
    (run / "model_250.pt").write_bytes(checkpoint_bytes)
    (run / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": 250},
        "checkpoints": {"model_250.pt": checkpoint_sha},
    }), encoding="utf-8")
    failed = chain.record_p1_outcome(
        iteration=250, stage_id="EX42_0_T0_prime",
        checkpoint_sha256=checkpoint_sha, attempt=1,
        collection_state="failed", failure_reason="dispatcher child rc=1")
    assert failed["state"] == "collection_failed_retryable"
    assert failed["retry_required"] is True

    score_path = tmp_path / "score.json"
    score_path.write_text(json.dumps({
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_iteration": 250,
        "plan_sha256": chain.plan.sha256,
        "stage_id": "EX42_0_T0_prime",
        "judgment": "HOLD",
        "map_matrix": _complete_map_matrix(),
        "judge_count": 26,
        "record_only_count": 13,
    }), encoding="utf-8")
    held = chain.record_p1_outcome(
        iteration=250, stage_id="EX42_0_T0_prime",
        checkpoint_sha256=checkpoint_sha, attempt=2,
        collection_state="complete", score_path=score_path,
        score_sha256=hashlib.sha256(score_path.read_bytes()).hexdigest())
    assert held["state"] == "judgment_hold"
    assert held["retry_required"] is False
    assert failed["receipt"]["path"] != held["receipt"]["path"]


def test_g13_completed_score_cannot_pass_when_manifest_names_a_different_model_sha(tmp_path):
    chain, run = make_chain(tmp_path)
    expected_sha = "a" * 64
    (run / "model_250.pt").write_bytes(b"actual model bytes differ")
    (run / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": 250},
        "checkpoints": {"model_250.pt": "b" * 64},
    }), encoding="utf-8")
    score_path = tmp_path / "score.json"
    score_path.write_text(json.dumps({
        "checkpoint_sha256": expected_sha,
        "checkpoint_iteration": 250,
        "plan_sha256": chain.plan.sha256,
        "stage_id": "EX42_0_T0_prime",
        "judgment": "PASS",
    }), encoding="utf-8")
    try:
        chain.record_p1_outcome(
            iteration=250, stage_id="EX42_0_T0_prime", checkpoint_sha256=expected_sha,
            attempt=1, collection_state="complete", score_path=score_path,
            score_sha256=hashlib.sha256(score_path.read_bytes()).hexdigest())
    except ValueError as exc:
        assert "model_N" in str(exc) or "score SHA" in str(exc)
    else:
        raise AssertionError("G13 accepted score SHA without a matching model_250 manifest entry")


def test_g15_completed_p1_score_cannot_pass_when_map_mode_cell_is_missing(tmp_path):
    chain, run = make_chain(tmp_path)
    checkpoint_bytes = b"valid model 250 for map matrix"
    checkpoint_sha = hashlib.sha256(checkpoint_bytes).hexdigest()
    (run / "model_250.pt").write_bytes(checkpoint_bytes)
    (run / "manifest.json").write_text(json.dumps({
        "progress": {"completed_updates": 250},
        "checkpoints": {"model_250.pt": checkpoint_sha},
    }), encoding="utf-8")
    score_path = tmp_path / "score.json"
    score_path.write_text(json.dumps({
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_iteration": 250,
        "plan_sha256": chain.plan.sha256,
        "stage_id": "EX42_0_T0_prime",
        "judgment": "PASS",
        "map_matrix": _complete_map_matrix()[:-1],
        "judge_count": 26,
        "record_only_count": 13,
    }), encoding="utf-8")
    try:
        chain.record_p1_outcome(
            iteration=250, stage_id="EX42_0_T0_prime", checkpoint_sha256=checkpoint_sha,
            attempt=1, collection_state="complete", score_path=score_path,
            score_sha256=hashlib.sha256(score_path.read_bytes()).hexdigest())
    except ValueError as exc:
        assert "map-mode" in str(exc) or "missing, duplicate" in str(exc)
    else:
        raise AssertionError("G15 accepted a score with one missing command × map-mode cell")


def test_g17_start_and_stage_boundary_write_saved_and_runtime_config_evidence(tmp_path):
    stage_holder = {}

    def boundary_provider(iteration, _runner):
        if iteration != 1001:
            return None
        return {"next_stage_id": stage_holder["chain"].plan.runtime_stage_ids[1],
                "expected_score_iteration": 1000,
                "observed_score_iteration": None,
                "checkpoint_sha256": "a" * 64}

    chain, run = make_chain(tmp_path, boundary_provider=boundary_provider)
    stage_holder["chain"] = chain
    params = run / "params"
    params.mkdir()
    (params / "env.yaml").write_text(
        "commands:\n  base_velocity:\n    ranges: {lin_vel_x: [0.1, 0.2]}\n"
        "observations:\n  policy:\n    map_mode: gt\n"
        "events:\n  push: enabled\n"
        "scene:\n  robot:\n    actuators: motorA\n"
        "rewards:\n  feet: 0.5\n"
        "curriculum:\n  terrain_levels: 2\n", encoding="utf-8")
    (params / "agent.yaml").write_text(
        "algorithm:\n  lr: 0.0003\n", encoding="utf-8")
    runtime = SimpleNamespace()
    runner = SimpleNamespace(env=SimpleNamespace(unwrapped=runtime, num_envs=3072),
                             log_dir=str(run), pcfg={"force_gt": True,
                                                     "p_map_off": 0.1,
                                                     "map_input": "reconstruction"})
    assert chain.on_runner_update_start(runner, 0) is None
    transition = chain.on_runner_update_start(runner, 1001)
    assert transition["status"] == "measurement_gap"
    path = run / "ex42_config_snapshots.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["iteration"] for row in rows] == [0, 1001]
    assert rows[0]["stage_id"] == chain.plan.runtime_stage_ids[0]
    assert rows[0]["saved_active_config"]["commands"]["observed"] is True
    assert rows[0]["saved_active_config"]["map_selection"]["observed"] is True
    assert rows[0]["saved_active_config"]["domain_randomization"]["observed"] is True
    assert rows[0]["saved_active_config"]["rewards"]["observed"] is True
    assert rows[0]["saved_active_config"]["level_cap"]["observed"] is True
    assert rows[1]["stage_id"] == chain.plan.runtime_stage_ids[1]
    assert rows[1]["runtime_readback"]["stage_id"] == chain.plan.runtime_stage_ids[1]
    assert rows[1]["runtime_readback"]["dr_scale"] == 1.0
    assert rows[1]["complete"] is False
    assert rows[1]["requested_realized_comparison"] == "not_verified"


def test_g17_missing_saved_config_values_remain_unknown_not_defaults(tmp_path):
    chain, run = make_chain(tmp_path)
    params = run / "params"
    params.mkdir()
    (params / "env.yaml").write_text("scene: {}\n", encoding="utf-8")
    (params / "agent.yaml").write_text("algorithm: {}\n", encoding="utf-8")
    runner = SimpleNamespace(env=SimpleNamespace(unwrapped=SimpleNamespace()),
                             log_dir=str(run), pcfg={})

    assert chain.on_runner_update_start(runner, 0) is None
    row = json.loads((run / "ex42_config_snapshots.jsonl").read_text(encoding="utf-8"))
    assert row["state"] == "partial"
    assert row["complete"] is False
    assert row["requested_realized_comparison"] == "not_verified"
    assert {"commands", "map_selection", "domain_randomization", "actuators",
            "rewards", "level_cap"}.issubset(row["missing_saved_fields"])
    assert row["saved_active_config"]["commands"] == {
        "value": None, "source": str(params / "env.yaml"), "observed": False}


def _run_runner_to_checkpoint(tmp_path, *, score_argv_factory):
    calls = []

    def boundary(iteration, _runner):
        calls.append(("boundary_provider", iteration))
        if iteration == 1:
            return {"next_stage_id": "E0", "expected_score_iteration": 0,
                    "observed_score_iteration": None, "checkpoint_sha256": "a" * 64}
        return None

    chain, run = make_chain(
        tmp_path, score_argv_factory=score_argv_factory,
        boundary_provider=boundary, p1_interval=1)
    runner = StartRunner(FakeStartEnv(num_envs=8, seed=71),
                         train_cfg(24, {"microbatch_envs": 4}),
                         log_dir=str(run), device="cpu")
    runner.current_learning_iteration = 1
    runner.cfg["save_interval"] = 1
    runner.save_interval = 1
    runner.pcfg["latest_interval"] = 999999
    runner._check_code = lambda _iteration: None

    def publish_manifest(iteration, name, _num_envs):
        path = run / name
        (run / "manifest.json").write_text(json.dumps({
            "progress": {"completed_updates": iteration},
            "checkpoints": {name: hashlib.sha256(path.read_bytes()).hexdigest()},
        }), encoding="utf-8")
        calls.append(("manifest", iteration))

    runner._manifest_checkpoint = publish_manifest
    runner.attach_ex42_training_chain(chain)
    assert chain.plan.document["status"] == "preparation_only"
    original_boundary = chain.on_runner_update_start

    def observe_boundary(*args):
        value = original_boundary(*args)
        if value is not None:
            calls.append(("transition_applied", value["boundary_iteration"]))
        return value

    chain.on_runner_update_start = observe_boundary
    original_p1 = chain.on_checkpoint_saved

    def observe_p1(*args):
        value = original_p1(*args)
        calls.append(("p1_result", value["state"]))
        return value

    chain.on_checkpoint_saved = observe_p1
    original_step = runner.env.step

    def observe_step(actions):
        calls.append(("env_step", 1))
        return original_step(actions)

    runner.env.step = observe_step
    calls.append(("attached", 1))
    runner.learn(1)
    calls.append(("learn_returned", runner.current_learning_iteration))
    return chain, runner, run, calls


def test_start_runner_calls_boundary_then_saves_manifest_then_registers_p1(tmp_path):
    chain, runner, run, calls = _run_runner_to_checkpoint(
        tmp_path, score_argv_factory=lambda iteration: [
            "python", "-m", "known.score_command", "--checkpoint-iteration", str(iteration)])
    assert calls.index(("boundary_provider", 1)) < calls.index(("manifest", 1))
    assert calls.index(("transition_applied", 1)) < calls.index(("env_step", 1))
    assert calls.index(("manifest", 1)) < calls.index(("p1_result", "queued"))
    queue = json.loads((tmp_path / "gpu/queue.json").read_text(encoding="utf-8"))
    assert queue["items"][0]["argv"][-1] == "1"
    assert queue["items"][0]["priority"] == 1
    events = [json.loads(line) for line in (run / "ex42_application.jsonl").read_text().splitlines()]
    assert next(row for row in events if row.get("event") == "stage_transition")["stage_after"] == "E0"
    assert next(row for row in events if row.get("event") == "p1_queued")["checkpoint_iteration"] == 1
    assert runner.current_learning_iteration == 1
    assert calls[-1] == ("learn_returned", 1)


def test_start_runner_p1_enqueue_failure_is_recorded_without_stopping_learning(tmp_path):
    chain, runner, run, calls = _run_runner_to_checkpoint(
        tmp_path, score_argv_factory=lambda _iteration: [])
    events = [json.loads(line) for line in (run / "ex42_application.jsonl").read_text().splitlines()]
    failure = next(row for row in events if row.get("event") == "p1_enqueue_failed")
    assert failure["state"] == "collection_failed_retryable"
    assert calls.index(("manifest", 1)) < calls.index(("p1_result", "collection_failed_retryable"))
    assert runner.current_learning_iteration == 1
    assert calls[-1] == ("learn_returned", 1)
    status = read_status(run / "train_start_status.json")
    assert status["state"] == "read"
