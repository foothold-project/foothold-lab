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
from foothold_s2.ex40_score import config, judge, require_shadow_plan, sha256
from foothold_s2.ex40_score_smoke import check as check_smoke
from foothold_s2.ex40_score_watch import process_once, _stable


def _source(tmp: Path, update: int = 500):
    checkpoint = tmp / f"model_{update}.pt"
    checkpoint.write_bytes(b"known policy checkpoint")
    plan = Plan(DEFAULT_TABLE, arm="B")
    stage_log = tmp / "stage_log.jsonl"
    stage_log.write_text(json.dumps({"event": "stage_enter", "iteration": 0,
                                      "to": "B0", "effective_schedule_sha256":
                                      plan.effective_sha256}) + "\n", encoding="utf-8")
    return checkpoint, plan


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
    old = Plan(DEFAULT_TABLE, arm="B")
    with pytest.raises(ValueError, match="seven fixed stages"):
        require_shadow_plan(old, cfg)
    seven = SimpleNamespace(stages=[SimpleNamespace(id=name) for name in cfg["stages"]],
                            promotion="fixed", shadow_gate=True)
    require_shadow_plan(seven, cfg)
    seven.shadow_gate = False
    with pytest.raises(ValueError, match="shadow_gate"):
        require_shadow_plan(seven, cfg)


def test_watch_one_at_a_time_duplicate_failure_and_skip(tmp_path):
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
    state["last_eval_seconds"] = 6001
    recent = process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                          "B", state, evaluator=evaluator, sleep=lambda _: None)
    assert recent["state"] == "PASS" and state["done"]["750"]["state"] == "skipped"
    assert calls[-1] == "model_1000.pt"
    (tmp_path / "model_1250.pt").write_bytes(b"later")
    def failure(source, out, stage, arm, cfg, table):
        return {"rc": 5, "seconds": 4, "receipt": {"state": "failed"}}
    failed = process_once(tmp_path, out_root, scores, DEFAULT_CONFIG, DEFAULT_TABLE,
                          "B", state, evaluator=failure, sleep=lambda _: None)
    assert failed["state"] == "HOLD" and state["stage_baseline"]["B0"]
    written = list(scores.glob("score_1250_*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text(encoding="utf-8"))["verdict"] == "HOLD"


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


def test_b2_axis_and_b3_relative_are_separate_gates(tmp_path, monkeypatch):
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
            "modes": {mode: {name: {"stop_complete_envs": 64,
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
    class SevenStagePlan:
        def __init__(self, path, *, arm):
            self.stages = [SimpleNamespace(id=name) for name in cfg["stages"]]
            self.effective_sha256 = "test-only-seven-stage-plan"
    monkeypatch.setattr("foothold_s2.ex40_score.Plan", SevenStagePlan)
    for stage in ("B3a", "B3b", "B3c"):
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
