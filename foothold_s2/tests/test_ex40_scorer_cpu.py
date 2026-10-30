"""Known-input EX-40 score, watcher and Kit-smoke receipt contracts, CPU only."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import copy
from types import SimpleNamespace

import pytest

from foothold_s2.curriculum.continuous import Plan, Runtime
from foothold_s2.eval.map_mode_cells import EX40_B3_COMMANDS, commands
from foothold_s2.ex40_eval_once import DEFAULT_CONFIG, DEFAULT_TABLE
from foothold_s2.ex40_score import config, judge, require_shadow_plan, sha256, stage_end_updates
from foothold_s2.ex40_score_smoke import check as check_smoke
from foothold_s2.ex40_score_watch import process_once, completion, stage_reports, _stable
from foothold_s2.ex40_stage_report import build as build_stage_report


def _source(tmp: Path, update: int = 500):
    checkpoint = tmp / f"model_{update}.pt"
    checkpoint.write_bytes(b"known policy checkpoint")
    plan = Plan(DEFAULT_TABLE, arm="B")
    stage_log = tmp / "stage_log.jsonl"
    stage_log.write_text(json.dumps({"event": "stage_enter", "iteration": 0,
                                      "to": "B0", "effective_schedule_sha256":
                                      plan.effective_sha256}) + "\n", encoding="utf-8")
    _pin(tmp, checkpoint)
    return checkpoint, plan


def _pin(run: Path, *paths: Path):
    source = run / "manifest.json"
    row = (json.loads(source.read_text(encoding="utf-8")) if source.exists() else
           {"schema": "foothold-manifest/1", "progress": {"completed_updates": 0},
            "checkpoints": {}})
    for path in paths:
        row["checkpoints"][path.name] = sha256(path)
        row["progress"]["completed_updates"] = max(
            row["progress"]["completed_updates"], int(path.stem.split("_")[-1]) + 1)
    source.write_text(json.dumps(row), encoding="utf-8")


def _evidence(out: Path, checkpoint: Path, *, missing_stand=False):
    out.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    command_rows = {}
    for mode in ("eval_gt", "probe_prop_only", "eval_pred"):
        command_rows[mode] = {}
        for name, command in commands("extended").items():
            command_rows[mode][name] = {"env_count": 64, "alive_envs_at_end": 64,
                              "command": command, "policy_steps_x_envs": 19200,
                              "gt_used": 19200 if mode == "eval_gt" else 0,
                              "per_env": [{"env": i, "samples_alive": 300,
                                           "vx_abs_error_mean_alive_mps": .05,
                                           "vy_abs_error_mean_alive_mps": .05,
                                           "wz_abs_error_mean_alive_radps": .05} for i in range(64)],
                              "body_vx_integral_median_m": command[0] * 6,
                              "yaw_follow_median": 1.0}
    sequence = {name: {"phases": [{"env_count": 64, "alive_at_end": 64}
                                     for _ in range(count)]}
                for name, count in (("spin_left_to_right", 2),
                                    ("spin_right_to_left", 2), ("stop_and_restart", 4))}
    map_row = {"checkpoint_sha256": sha256(checkpoint),
               "checkpoint_iter": int(checkpoint.stem.split("_")[-1]),
               "envs": 64, "steps": cfg["map_steps"], "eval_seed": cfg["eval_seed"],
               "command_suite": "extended",
               "commands": commands("extended"), "fixed_terrain": {"rows": 10},
               "terrain_tiles": [{"env": i} for i in range(64)],
               "modes": command_rows,
               "sequences": {mode: sequence for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
    (out / "map64").mkdir()
    (out / "map64/map_modes.json").write_text(json.dumps(map_row), encoding="utf-8")
    if not missing_stand:
        for mode in ("eval_gt", "probe_prop_only", "eval_pred"):
            folder = out / f"stand_{mode}"
            folder.mkdir()
            (folder / "stand_raw.npz").write_bytes(b"known stance raw arrays")
            stand = {"format": "foothold-ex40-stand/1",
                     "checkpoint_sha256": sha256(checkpoint), "mode": mode,
                     "envs": 64, "seconds": 3.0, "skip_seconds": 1.0,
                     "contact_force_n": 1.0, "conditions": {"ground": "plane z=0"},
                     "raw_sha256": sha256(folder / "stand_raw.npz"),
                     "per_env": [{"env": i, "alive_at_end": True,
                                  "valid_samples_after_1s": 100,
                                  "body_speed_mean_mps": .01,
                                  "abs_yaw_speed_mean_radps": .02,
                                  "feet": {name: {"contact_fraction_gt1n": .95,
                                                  "mean_fz_over_mg": .20,
                                                  "sole_gap_p95_m": .001}
                                           for name in ("FL_foot", "FR_foot", "RL_foot", "RR_foot")}}
                                 for i in range(64)]}
            (folder / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
    return map_row


def test_pass_fail_hold_and_continuous_parser(tmp_path):
    checkpoint, plan = _source(tmp_path)
    out = tmp_path / "eval"
    _evidence(out, checkpoint)
    row, baseline = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert row["verdict"] == "PASS" and len(baseline) == 10
    assert row["cells"]["eval_pred/flat_stand_record_only"]["passed_envs"] == 64
    score_dir = tmp_path / "scores"
    score_dir.mkdir()
    (score_dir / "score_500.json").write_text(json.dumps(row), encoding="utf-8")
    runtime = Runtime(plan, 2, "cpu", tmp_path / "log", score_dir)
    runtime.start()
    runtime.on_checkpoint(500, checkpoint)
    assert runtime.latest_score["verdict"] == "PASS"
    stand_path = out / "stand_eval_gt/stand.json"
    stand = json.loads(stand_path.read_text(encoding="utf-8"))
    stand["per_env"][0]["feet"]["RR_foot"]["contact_fraction_gt1n"] = .1
    for item in stand["per_env"][1:5]:
        item["feet"]["RR_foot"]["contact_fraction_gt1n"] = .1
    stand_path.write_text(json.dumps(stand), encoding="utf-8")
    fail, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert fail["verdict"] == "FAIL"
    (out / "stand_eval_gt/stand_raw.npz").unlink()
    held, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert held["verdict"] == "HOLD"


def test_first_stage_drop_is_hold_and_stand_nonfinite_is_hold(tmp_path):
    checkpoint, _ = _source(tmp_path)
    out = tmp_path / "eval"
    main = _evidence(out, checkpoint)
    main["modes"]["eval_gt"]["fwd0.5"]["alive_envs_at_end"] = 60
    (out / "map64/map_modes.json").write_text(json.dumps(main), encoding="utf-8")
    row, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B",
                   {"eval_gt/fwd0.5": 64})
    assert row["verdict"] == "HOLD"
    stand_path = out / "stand_eval_gt/stand.json"
    stand = json.loads(stand_path.read_text(encoding="utf-8"))
    stand["per_env"][0]["feet"]["RR_foot"].pop("mean_fz_over_mg")
    stand_path.write_text(json.dumps(stand), encoding="utf-8")
    held, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert held["verdict"] == "HOLD"


def test_map_command_and_gt_selection_mutations_hold(tmp_path):
    checkpoint, _ = _source(tmp_path)
    out = tmp_path / "eval"
    main = _evidence(out, checkpoint)
    path = out / "map64/map_modes.json"
    main["modes"]["eval_gt"]["fwd0.5"]["gt_used"] = 0
    path.write_text(json.dumps(main), encoding="utf-8")
    row, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert row["verdict"] == "HOLD"
    main["modes"]["eval_gt"]["fwd0.5"]["gt_used"] = 19200
    main["modes"]["eval_gt"]["fwd0.5"]["command"] = [1.0, 0.0, 0.0]
    path.write_text(json.dumps(main), encoding="utf-8")
    row, _ = judge(checkpoint, "B0", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert row["verdict"] == "HOLD"


def _state():
    return {"format": "foothold-ex40-score-watch/1",
            "config_sha256": sha256(DEFAULT_CONFIG), "table_sha256": sha256(DEFAULT_TABLE),
            "arm": "B", "done": {}, "stage_baseline": {}, "last_eval_seconds": 0}


def test_d72_rejects_old_five_stage_plan():
    cfg = config(DEFAULT_CONFIG)
    old = SimpleNamespace(stages=[SimpleNamespace(id=name) for name in
                                  ("B0", "B1", "B2", "B3", "T0")],
                          promotion="fixed", shadow_gate=True)
    with pytest.raises(ValueError, match="eight fixed stages"):
        require_shadow_plan(old, cfg)
    eight = Plan(DEFAULT_TABLE, arm="B")
    require_shadow_plan(eight, cfg)
    eight.shadow_gate = False
    with pytest.raises(ValueError, match="shadow_gate"):
        require_shadow_plan(eight, cfg)


def test_watch_one_at_a_time_duplicate_failure_and_no_skip(tmp_path):
    checkpoint, _ = _source(tmp_path)
    out_root, scores = tmp_path / "out", tmp_path / "scores"
    out_root.mkdir()
    calls = []

    def evaluator(source, out, stage, arm, cfg, table):
        calls.append(source.name)
        _evidence(out, source)
        return {"rc": 0, "seconds": 8, "receipt": {"state": "done"}}

    state = _state()
    first = process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                         "B", state, evaluator=evaluator, sleep=lambda _: None)
    assert first["state"] == "PASS" and calls == [checkpoint.name]
    assert process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                        "B", state, evaluator=evaluator, sleep=lambda _: None)["state"] == "idle"
    for update in (750, 1000):
        (tmp_path / f"model_{update}.pt").write_bytes(f"policy {update}".encode())
    _pin(tmp_path, tmp_path / "model_750.pt", tmp_path / "model_1000.pt")
    state["last_eval_seconds"] = 6001
    for expected in (750, 1000):
        recent = process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                              "B", state, evaluator=evaluator, sleep=lambda _: None)
        assert recent["state"] == "PASS" and calls[-1] == f"model_{expected}.pt"
    (tmp_path / "model_1250.pt").write_bytes(b"later")
    _pin(tmp_path, tmp_path / "model_1250.pt")
    def failure(source, out, stage, arm, cfg, table):
        return {"rc": 5, "seconds": 4, "receipt": {"state": "failed"}}
    failed = process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                          "B", state, evaluator=failure, sleep=lambda _: None)
    assert failed["state"] == "HOLD" and state["stage_baseline"]["B0"]
    written = list(scores.glob("score_1250_*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text(encoding="utf-8"))["verdict"] == "HOLD"
    ledger = [json.loads(line) for line in (out_root / "score_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["checkpoint_iteration"] for row in ledger] == [500, 750, 1000, 1250]
    assert all(row["stage_log_reference"] == str(tmp_path / "stage_log.jsonl") for row in ledger)


def test_b1_walk_half_and_sequence_are_required(tmp_path):
    checkpoint, _ = _source(tmp_path, update=1750)
    out = tmp_path / "eval"
    main = _evidence(out, checkpoint)
    held, _ = judge(checkpoint, "B1", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert held["verdict"] == "HOLD" and "map64_b3" in held["problems"][0]["reason"]
    extra = {**main, "command_suite": "ex40_b3",
             "commands": commands("ex40_b3"),
             "modes": {mode: {name: {**main["modes"][mode]["fwd0.5"],
                                      "command": command}
                              for name, command in EX40_B3_COMMANDS.items()}
                       for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
    (out / "map64_b3").mkdir()
    extra_path = out / "map64_b3/map_modes.json"
    extra_path.write_text(json.dumps(extra), encoding="utf-8")
    passed, _ = judge(checkpoint, "B1", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert passed["verdict"] == "PASS"
    assert passed["cells"]["eval_gt/walk+0.5"]["alive_envs_at_end"] == 64
    extra["modes"]["eval_gt"]["walk+0.5"]["per_env"][0]["wz_abs_error_mean_alive_radps"] = .3
    extra_path.write_text(json.dumps(extra), encoding="utf-8")
    failed, _ = judge(checkpoint, "B1", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert failed["verdict"] == "PASS"  # one bad env cannot move a median
    for row in extra["modes"]["eval_gt"]["walk+0.5"]["per_env"]:
        row["wz_abs_error_mean_alive_radps"] = .3
    extra_path.write_text(json.dumps(extra), encoding="utf-8")
    failed, _ = judge(checkpoint, "B1", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert failed["verdict"] == "FAIL"
    main["sequences"]["eval_gt"].pop("stop_and_restart")
    (out / "map64/map_modes.json").write_text(json.dumps(main), encoding="utf-8")
    held, _ = judge(checkpoint, "B1", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert held["verdict"] == "HOLD"


def test_b2_axis_and_b3_relative_are_separate_gates(tmp_path):
    checkpoint, _ = _source(tmp_path, update=3500)
    out = tmp_path / "eval"
    main = _evidence(out, checkpoint)
    extra = {**main, "command_suite": "ex40_b3", "commands": commands("ex40_b3"),
             "policy_dt_s": .02,
             "modes": {mode: {name: {**copy.deepcopy(main["modes"][mode]["fwd0.5"]),
                                      "command": command}
                              for name, command in EX40_B3_COMMANDS.items()}
                       for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
    (out / "map64_b3").mkdir()
    extra_path = out / "map64_b3/map_modes.json"
    extra_path.write_text(json.dumps(extra), encoding="utf-8")
    missing_axis, _ = judge(checkpoint, "B2", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert missing_axis["verdict"] == "HOLD"
    cfg = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    axis = {"checkpoint_sha256": sha256(checkpoint), "envs": 64,
            "modes": {mode: {name: {"alive_at_end": 64, "stop_complete_envs": 64,
                                     "stop_end_error_median_rad": .01}
                             for name in cfg["axis_goal"]["cases"]}
                      for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
    (out / "axis_v2").mkdir()
    axis_path = out / "axis_v2/axis_v2.json"
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    passed, _ = judge(checkpoint, "B2", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert passed["verdict"] == "PASS"
    axis["modes"]["eval_gt"][cfg["axis_goal"]["cases"][0]]["stop_complete_envs"] = 59
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    failed, _ = judge(checkpoint, "B2", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert failed["verdict"] == "FAIL"
    axis["modes"]["eval_gt"][cfg["axis_goal"]["cases"][0]]["stop_complete_envs"] = 64
    axis_path.write_text(json.dumps(axis), encoding="utf-8")
    for stage in ("B3a", "B3b", "B3c", "D"):
        row, _ = judge(checkpoint, stage, out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
        assert row["verdict"] == "PASS"
    extra["modes"]["eval_gt"]["spin+0.3"]["yaw_follow_median"] = .3
    extra_path.write_text(json.dumps(extra), encoding="utf-8")
    early, _ = judge(checkpoint, "B3a", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert early["verdict"] == "PASS"  # spin lower bound is not opened yet
    late, _ = judge(checkpoint, "B3b", out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert late["verdict"] == "FAIL"


def test_stable_probe_rejects_rewrite(tmp_path):
    path = tmp_path / "model_500.pt"
    path.write_bytes(b"first")
    assert _stable(path, 0, sleep=lambda _: path.write_bytes(b"second")) is None


def test_smoke_check_known_receipt(tmp_path):
    checkpoint, _ = _source(tmp_path, update=14)
    out = tmp_path / "smoke"
    _evidence(out, checkpoint)
    row = json.loads((out / "map64/map_modes.json").read_text(encoding="utf-8"))
    row["modes"] = {"eval_gt": {"fwd0.5": row["modes"]["eval_gt"]["fwd0.5"]}}
    (out / "map64/map_modes.json").write_text(json.dumps(row), encoding="utf-8")
    for mode in ("probe_prop_only", "eval_pred"):
        shutil.rmtree(out / f"stand_{mode}")
    receipt = {"state": "done", "smoke": True,
               "steps": {"map64": {"rc": 0}, "stand_eval_gt": {"rc": 0}},
               "elapsed_seconds": 40}
    (out / "eval_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    assert check_smoke(out, checkpoint)["state"] == "PASS"
    row["modes"]["eval_gt"].pop("fwd0.5")
    (out / "map64/map_modes.json").write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or mismatched"):
        check_smoke(out, checkpoint)


def _axis(out: Path, checkpoint: Path):
    cfg = config(DEFAULT_CONFIG)
    axis = {"checkpoint_sha256": sha256(checkpoint), "envs": 64,
            "modes": {mode: {name: {"alive_at_end": 64, "stop_complete_envs": 64,
                                     "stop_end_error_median_rad": .01}
                             for name in cfg["axis_goal"]["cases"]}
                      for mode in ("eval_gt", "probe_prop_only", "eval_pred")}}
    (out / "axis_v2").mkdir(exist_ok=True)
    (out / "axis_v2/axis_v2.json").write_text(json.dumps(axis), encoding="utf-8")


def test_d74_stage_ends_require_w57_and_keep_old_stage_score(tmp_path):
    checkpoint, plan = _source(tmp_path, update=1500)
    assert stage_end_updates(plan, config(DEFAULT_CONFIG)) == {
        1500: "B0", 3000: "B1", 4500: "B2", 5000: "B3a",
        5500: "B3b", 6000: "B3c", 7500: "D", 8000: "T0"}
    out_root, scores = tmp_path / "evals", tmp_path / "scores"
    source_log = tmp_path / "stage_log.jsonl"
    with source_log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": "stage_enter", "iteration": 1501,
                                 "to": "B1", "effective_schedule_sha256":
                                 plan.effective_sha256}) + "\n")
    before = source_log.read_bytes()
    def evaluator(source, out, stage, arm, cfg_path, table):
        assert stage == "B0"
        _evidence(out, source)
        missing, _ = judge(source, stage, out, cfg_path, table, arm)
        assert missing["verdict"] == "HOLD" and "axis_v2" in missing["problems"][0]["reason"]
        _axis(out, source)
        return {"rc": 0, "seconds": 2, "receipt": {"state": "done"}}
    state = _state()
    row = process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                       "B", state, evaluator=evaluator, sleep=lambda _: None)
    assert row["state"] == "PASS" and row["stage"] == "B0"
    assert source_log.read_bytes() == before
    ledger = json.loads((out_root / "score_ledger.jsonl").read_text(encoding="utf-8").strip())
    assert ledger["stage"] == "B0" and ledger["checkpoint_iteration"] == 1500
    assert json.loads(Path(ledger["score_path"]).read_text(encoding="utf-8"))["sources"]["axis_v2"]
    restarted = _state()
    def forbidden(*args):
        raise AssertionError("completed checkpoint must not run again")
    assert process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                        "B", restarted, evaluator=forbidden, sleep=lambda _: None)["recovered_from_ledger"]
    assert len(list(scores.glob("score_1500_*.json"))) == 1
    ledger_path = out_root / "score_ledger.jsonl"
    duplicate = ledger_path.read_text(encoding="utf-8")
    with ledger_path.open("a", encoding="utf-8") as stream:
        stream.write(duplicate)
    with pytest.raises(ValueError, match="duplicate checkpoint"):
        process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                     "B", restarted, evaluator=forbidden, sleep=lambda _: None)


def test_unpinned_or_rewritten_checkpoint_never_starts_eval(tmp_path):
    checkpoint, _ = _source(tmp_path)
    state = _state()
    out_root = tmp_path / "evals"
    def forbidden(*args):
        raise AssertionError("incomplete save must not be evaluated")
    (tmp_path / "manifest.json").unlink()
    assert process_once(tmp_path, out_root, tmp_path / "scores", DEFAULT_CONFIG,
                        DEFAULT_TABLE, "B", state, evaluator=forbidden,
                        sleep=lambda _: None)["reason"] == "manifest_checkpoint_not_committed"
    _pin(tmp_path, checkpoint)
    checkpoint.write_bytes(b"new bytes after manifest pin")
    assert "manifest_mismatch" in process_once(
        tmp_path, out_root, tmp_path / "scores", DEFAULT_CONFIG,
        DEFAULT_TABLE, "B", state, evaluator=forbidden, sleep=lambda _: None)["reason"]
    _pin(tmp_path, checkpoint)
    assert "not_stable" in process_once(
        tmp_path, out_root, tmp_path / "scores", DEFAULT_CONFIG,
        DEFAULT_TABLE, "B", state, evaluator=forbidden,
        sleep=lambda _: checkpoint.write_bytes(b"changed during probe"))["reason"]


def test_final_completion_requires_all_31_scores_and_training_done(tmp_path):
    plan = Plan(DEFAULT_TABLE, arm="B")
    cfg = config(DEFAULT_CONFIG)
    out_root = tmp_path / "evals"
    out_root.mkdir()
    state = _state()
    ledger_rows = []
    boundaries = stage_end_updates(plan, cfg)
    segment_roots = {}
    for n in range(500, 8001, 250):
        segment_index = (n - 500) // 2500
        source_run = segment_roots.setdefault(segment_index, tmp_path / f"segment-{segment_index}")
        source_run.mkdir(exist_ok=True)
        checkpoint = source_run / f"model_{n}.pt"
        checkpoint.write_bytes(f"completed checkpoint {n}".encode())
        manifest_path = source_run / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"schema": "foothold-manifest/1", "progress": {"completed_updates": 0},
                        "checkpoints": {}, "modes": {}}
        manifest["progress"]["completed_updates"] = n + 1
        manifest["checkpoints"][checkpoint.name] = sha256(checkpoint)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        stage = max((s for s in plan.stages if s.fixed_update <= n),
                    key=lambda s: s.fixed_update).id
        (source_run / "stage_log.jsonl").write_text("".join(
            json.dumps({"event": "stage_enter", "iteration": item.fixed_update,
                        "to": item.id, "effective_schedule_sha256": plan.effective_sha256}) + "\n"
            for item in plan.stages if item.fixed_update <= n), encoding="utf-8")
        stage_cfg = cfg["stages"][stage]
        phases = {"map64", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred"}
        if stage_cfg.get("relative_commands") or stage_cfg.get("judge_walk_half"):
            phases.add("map64_b3")
        if stage_cfg["axis_goal"] or n in boundaries:
            phases.add("axis_v2")
        evidence = out_root / f"evidence_{n}"
        evidence.mkdir()
        sources = {}
        for phase in phases:
            path = evidence / f"{phase}.json"
            path.write_text("{}", encoding="utf-8")
            sources[phase] = str(path)
        receipt_path = evidence / "eval_receipt.json"
        receipt_path.write_text(json.dumps({"state": "done", "steps": {
            phase: {"rc": 0} for phase in phases}}), encoding="utf-8")
        score_path = out_root / f"score_{n}.json"
        score_path.write_text(json.dumps({"verdict": "PASS", "sources": sources,
                                          "checkpoint_sha256": sha256(checkpoint),
                                          "evaluation_receipt": str(receipt_path)}), encoding="utf-8")
        state["done"][str(n)] = {"state": "PASS", "stage": stage,
                                 "checkpoint_sha256": sha256(checkpoint)}
        ledger_rows.append({"checkpoint_iteration": n, "checkpoint_sha256": sha256(checkpoint),
                            "run_dir": str(source_run.resolve()),
                            "checkpoint_path": str(checkpoint.resolve()),
                            "score_path": str(score_path), "score_sha256": sha256(score_path)})
    (out_root / "score_ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ledger_rows),
                                                   encoding="utf-8")
    final = segment_roots[3] / "model_8000.pt"
    status = {"state": "running", "iter": 8000, "checkpoint": str(final), "sha256": sha256(final)}
    latest_run = segment_roots[3]
    status_path = latest_run / "train_start_status.json"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    assert completion(latest_run, out_root, DEFAULT_CONFIG, DEFAULT_TABLE, "B", state)["state"] == "waiting_for_training"
    status["state"] = "done"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    assert completion(latest_run, out_root, DEFAULT_CONFIG, DEFAULT_TABLE, "B", state) == {
        "state": "done", "final_checkpoint": str(final), "final_sha256": sha256(final),
        "evaluated": 31, "stage_end_updates": list(boundaries)}
    ledger_rows[0]["checkpoint_path"] = str(tmp_path / "missing-parent-model.pt")
    (out_root / "score_ledger.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in ledger_rows), encoding="utf-8")
    assert completion(latest_run, out_root, DEFAULT_CONFIG, DEFAULT_TABLE, "B", state)["state"] == \
        "score_or_checkpoint_mismatch"
    ledger_rows[0]["checkpoint_path"] = str(segment_roots[0] / "model_500.pt")
    (out_root / "score_ledger.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in ledger_rows), encoding="utf-8")
    (out_root / "evidence_8000/axis_v2.json").unlink()
    assert completion(latest_run, out_root, DEFAULT_CONFIG, DEFAULT_TABLE, "B", state)["state"] == "stage_end_evidence_missing"
    (out_root / "evidence_8000/axis_v2.json").write_text("{}", encoding="utf-8")
    state["done"].pop("8000")
    assert completion(latest_run, out_root, DEFAULT_CONFIG, DEFAULT_TABLE, "B", state)["first_missing"] == 8000
    state["done"]["500"]["state"] = "HOLD"
    assert completion(latest_run, out_root, DEFAULT_CONFIG, DEFAULT_TABLE, "B", state)["first_missing"] == 8000
    state["done"]["500"]["state"] = "PASS"
    state["done"]["8000"] = {"state": "HOLD", "stage": "T0", "checkpoint_sha256": sha256(final)}
    assert completion(latest_run, out_root, DEFAULT_CONFIG, DEFAULT_TABLE, "B", state)["state"] == "score_hold"


def test_t0_final_score_is_exported_even_without_next_stage(tmp_path, monkeypatch):
    checkpoint, plan = _source(tmp_path, update=8000)
    with (tmp_path / "stage_log.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": "stage_enter", "iteration": 7501,
                                 "to": "T0", "effective_schedule_sha256":
                                 plan.effective_sha256}) + "\n")
    def fake_judge(source, stage, out, cfg_path, table, arm, baseline=None):
        return ({"format": "foothold-ex40-score/2", "from": "T0", "to": None,
                 "checkpoint": str(source), "checkpoint_iteration": 8000,
                 "checkpoint_sha256": sha256(source), "verdict": "PASS",
                 "problems": [], "sources": {"axis_v2": "present"}}, {})
    monkeypatch.setattr("foothold_s2.ex40_score_watch.judge", fake_judge)
    out_root, scores = tmp_path / "evals", tmp_path / "scores"
    state = _state()
    row = process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE, "B", state,
                       evaluator=lambda *args: {"rc": 0, "seconds": 2,
                                                 "receipt": {"state": "done"}},
                       sleep=lambda _: None)
    assert row["stage"] == "T0" and row["state"] == "PASS"
    assert len(list(scores.glob("score_8000_*.json"))) == 1
    assert json.loads((out_root / "score_ledger.jsonl").read_text(encoding="utf-8"))["stage"] == "T0"


def test_d74_stage_report_from_w15_w57_stand_dr_and_delivery(tmp_path):
    run, out = tmp_path / "run", tmp_path / "score_watch"
    run.mkdir()
    out.mkdir()
    ledger = []
    saved = []
    for update, stage in ((1500, "B0"), (3000, "B1")):
        checkpoint = run / f"model_{update}.pt"
        checkpoint.write_bytes(f"model {update}".encode())
        evidence = out / f"eval_{update}"
        map_row = _evidence(evidence, checkpoint)
        _axis(evidence, checkpoint)
        if update == 3000:
            map_row["modes"]["eval_gt"]["fwd0.5"]["alive_envs_at_end"] = 59
            map_row["modes"]["eval_gt"]["fwd1.0"]["alive_envs_at_end"] = 61
            (evidence / "map64/map_modes.json").write_text(json.dumps(map_row), encoding="utf-8")
        sources = {"map64": str(evidence / "map64/map_modes.json"),
                   "axis_v2": str(evidence / "axis_v2/axis_v2.json")}
        sources.update({f"stand_{mode}": str(evidence / f"stand_{mode}/stand.json")
                        for mode in ("eval_gt", "probe_prop_only", "eval_pred")})
        score = {"format": "foothold-ex40-score/2", "from": stage,
                 "checkpoint_iteration": update, "checkpoint_sha256": sha256(checkpoint),
                 "sources": sources}
        score_path = out / f"score_{update}.json"
        score_path.write_text(json.dumps(score), encoding="utf-8")
        ledger.append({"checkpoint_iteration": update, "stage": stage, "verdict": "PASS",
                       "score_path": str(score_path), "score_sha256": sha256(score_path)})
        saved.append(score)
    (out / "score_ledger.jsonl").write_text("".join(json.dumps(row) + "\n" for row in ledger), encoding="utf-8")
    (run / "train_extra.jsonl").write_text("".join(json.dumps({"it": update, "ex40_dr": {
        "update": update, "scale": scale,
        "actual_samples": {"base_com_offset_m": {"count": 2, "min": 0., "max": .01, "mean": .005}},
        "delay_readback": {"observed_min_substeps": 0, "observed_max_substeps": 1},
        "pending_values": []}}) + "\n" for update, scale in ((1500, 0.), (3000, .2))), encoding="utf-8")
    row = build_stage_report(saved[1], saved[0], run)
    assert len(row["current"]["w15"]) == 39
    assert row["dr_current"]["actual_samples"]["base_com_offset_m"]["max"] == .01
    assert any(item["cell"] == "w15/eval_gt/fwd0.5" and item["delta"] == -5 for item in row["losses"])
    assert any(item["cell"] == "w15/eval_gt/fwd1.0" and item["delta"] == -3 for item in row["unchanged"])
    sent = []
    result = stage_reports(run, out, DEFAULT_CONFIG, DEFAULT_TABLE, "B",
                           telegram_sender=tmp_path / "sender.py", lab_feed=tmp_path / "lab_feed.json",
                           sender=lambda script, message: sent.append(message.read_text(encoding="utf-8")) or True)
    assert type(result["published"]) is int
    assert result["published"] == 2 and result["first_pending"] == 4500
    assert len(sent) == 2 and (out / "stage_reports/stage_B1_m3000.md").is_file()
    assert json.loads((tmp_path / "lab_feed.json").read_text(encoding="utf-8"))["stage_reports"][1]["stage"] == "B1"
    assert "B1 m3000" in (tmp_path / "lab_feed.html").read_text(encoding="utf-8")
    # Exercise the supervisor with this real score_watch stage-report output.
    from foothold_s2.ex40_supervisor import _score_until_checkpoint
    _pin(run, run / "model_1500.pt", run / "model_3000.pt")
    (out / "watch_state.json").write_text(json.dumps({
        "format": "foothold-ex40-score-watch/1", "arm": "B",
        "done": {str(update): {"state": "PASS", "checkpoint_sha256": sha256(run / f"model_{update}.pt")}
                 for update in (1500, 3000)}}), encoding="utf-8")
    consumed = _score_until_checkpoint(run, out, tmp_path / "scores", DEFAULT_CONFIG,
        DEFAULT_TABLE, "B", 3000, sha256(run / "model_3000.pt"), max_calls=1,
        telegram_sender=tmp_path / "sender.py", lab_feed=tmp_path / "lab_feed.json",
        sender=lambda *_: pytest.fail("existing delivery receipt must suppress duplicate send"))
    assert consumed == "consumed"
    stage_reports(run, out, DEFAULT_CONFIG, DEFAULT_TABLE, "B",
                  telegram_sender=tmp_path / "sender.py", sender=lambda *_: pytest.fail("duplicate send"))
    assert len(sent) == 2
    delivery = out / "stage_reports/stage_B1_m3000.delivery.json"
    delivery.write_text(json.dumps({"state": "uncertain"}), encoding="utf-8")
    held = stage_reports(run, out, DEFAULT_CONFIG, DEFAULT_TABLE, "B",
                         telegram_sender=tmp_path / "sender.py", sender=lambda *_: pytest.fail("uncertain resend"))
    assert held["state"] == "hold" and held["first_hold"]["reason"] == "telegram_delivery_uncertain"
    (out / "eval_3000/map64/map_modes.json").write_text("{}", encoding="utf-8")
    changed = stage_reports(run, out, DEFAULT_CONFIG, DEFAULT_TABLE, "B")
    assert changed["state"] == "hold" and "source changed" in changed["first_hold"]["reason"]
    bad = copy.deepcopy(saved[1])
    bad["checkpoint_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="checkpoint"):
        build_stage_report(bad, saved[0], run)
