"""Known-input checks for the short-checkpoint full-path B13 consumer."""

from __future__ import annotations

import json
import copy
from pathlib import Path

import pytest

from foothold_s2.eval.map_mode_cells import EX40_B3_COMMANDS, commands
from foothold_s2.ex40_b13_probe import (check_checkpoint, check_evidence,
                                        check_smoke_receipt, finalize, MODES, PHASES)
from foothold_s2.ex40_eval_once import DEFAULT_CONFIG, DEFAULT_TABLE
from foothold_s2.ex40_score import sha256
from foothold_s2.tests.test_ex40_scorer_cpu import _evidence


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _inputs(tmp_path):
    run, out = tmp_path / "run", tmp_path / "output"
    run.mkdir()
    checkpoint = run / "model_17.pt"
    checkpoint.write_bytes(b"B12 complete checkpoint fixture")
    digest = sha256(checkpoint)
    _write(run / "manifest.json", {"schema": "foothold-manifest/1",
          "checkpoints": {checkpoint.name: digest}, "progress": {"completed_updates": 18}})
    config, table = tmp_path / "config.json", tmp_path / "table.yaml"
    config.write_text("config", encoding="utf-8")
    table.write_text("table", encoding="utf-8")
    _write(out / "eval_receipt.json", {
        "state": "done", "smoke": False, "checkpoint": str(checkpoint),
        "checkpoint_sha256": digest, "stage": "T0", "arm": "B", "device": "cuda:1",
        "score_config_sha256": sha256(config), "table_sha256": sha256(table),
        "steps": {name: {"rc": 0, "output_path": str(out / name)} for name in PHASES}})
    _write(out / "map64/map_modes.json", {
        "checkpoint_sha256": digest, "envs": 64,
        "modes": {mode: dict.fromkeys(commands("extended"), {}) for mode in MODES}})
    _write(out / "map64_b3/map_modes.json", {
        "checkpoint_sha256": digest, "envs": 64,
        "modes": {mode: dict.fromkeys(EX40_B3_COMMANDS, {}) for mode in MODES}})
    for mode in MODES:
        _write(out / f"stand_{mode}/stand.json", {
            "checkpoint_sha256": digest, "mode": mode, "envs": 64,
            "per_env": [{} for _ in range(64)]})
    _write(out / "axis_v2/axis_v2.json", {
        "checkpoint_sha256": digest, "envs": 64, "modes": dict.fromkeys(MODES, {})})
    return checkpoint, out, digest, config, table


def test_complete_short_checkpoint_and_full_receipt(tmp_path):
    checkpoint, out, digest, config, table = _inputs(tmp_path)
    assert check_checkpoint(checkpoint) == digest
    assert check_evidence(checkpoint, out, digest, config, table)["state"] == "done"


def test_b12_receipt_is_required_and_pins_the_short_stage(tmp_path):
    checkpoint, _, digest, _, _ = _inputs(tmp_path)
    path = tmp_path / "kit_check.json"
    row = {"state": "PASS", "run_dir": str(checkpoint.parent),
           "checkpoint": str(checkpoint), "checkpoint_sha256": digest,
           "stages": [["B0", 0], ["B1", 2], ["B2", 4], ["B3a", 6],
                      ["B3b", 8], ["B3c", 10], ["D", 12], ["T0", 14]]}
    _write(path, row)
    _write(tmp_path / "launch_receipt.json", {
        "arm": "B", "start": "scratch", "stage_boundaries": dict(row["stages"])})
    assert check_smoke_receipt(path) == checkpoint
    row["stages"][-1] = ["T0", 15]
    _write(path, row)
    with pytest.raises(ValueError, match="B13 requires"):
        check_smoke_receipt(path)


@pytest.mark.parametrize("mutation", ["incomplete", "wrong_sha"])
def test_checkpoint_mutations_caught(tmp_path, mutation):
    checkpoint, _, _, _, _ = _inputs(tmp_path)
    manifest = checkpoint.parent / "manifest.json"
    row = json.loads(manifest.read_text())
    if mutation == "incomplete":
        row["progress"]["completed_updates"] = 17
    else:
        row["checkpoints"][checkpoint.name] = "0" * 64
    _write(manifest, row)
    with pytest.raises(ValueError, match="manifest-pinned"):
        check_checkpoint(checkpoint)


@pytest.mark.parametrize("mutation", ["smoke", "wrong_arm", "missing_phase", "phase_failed",
                                      "missing_command", "missing_mode", "missing_stand_env",
                                      "missing_axis_mode", "wrong_config_sha"])
def test_full_path_mutations_caught(tmp_path, mutation):
    checkpoint, out, digest, config, table = _inputs(tmp_path)
    if mutation in {"smoke", "wrong_arm", "missing_phase", "phase_failed", "wrong_config_sha"}:
        path = out / "eval_receipt.json"
        row = json.loads(path.read_text())
        if mutation == "smoke":
            row["smoke"] = True
        elif mutation == "wrong_arm":
            row["arm"] = "A"
        elif mutation == "missing_phase":
            del row["steps"]["axis_v2"]
        elif mutation == "phase_failed":
            row["steps"]["map64_b3"]["rc"] = 2
        else:
            row["score_config_sha256"] = "0" * 64
    elif mutation == "missing_command":
        path = out / "map64/map_modes.json"
        row = json.loads(path.read_text())
        del row["modes"]["eval_pred"]["back1.0"]
    elif mutation == "missing_mode":
        path = out / "map64_b3/map_modes.json"
        row = json.loads(path.read_text())
        del row["modes"]["eval_pred"]
    elif mutation == "missing_stand_env":
        path = out / "stand_eval_gt/stand.json"
        row = json.loads(path.read_text())
        row["per_env"].pop()
    else:
        path = out / "axis_v2/axis_v2.json"
        row = json.loads(path.read_text())
        del row["modes"]["eval_pred"]
    _write(path, row)
    with pytest.raises(ValueError, match="B13"):
        check_evidence(checkpoint, out, digest, config, table)


def test_full_cpu_score_report_and_five_pngs_without_publication(tmp_path):
    run, out = tmp_path / "run", tmp_path / "full"
    run.mkdir()
    checkpoint = run / "model_17.pt"
    checkpoint.write_bytes(b"known short Kit policy")
    digest = sha256(checkpoint)
    _write(run / "manifest.json", {"schema": "foothold-manifest/1",
          "checkpoints": {checkpoint.name: digest}, "progress": {"completed_updates": 18}})
    main = _evidence(out, checkpoint)
    extra = {**main, "command_suite": "ex40_b3", "commands": commands("ex40_b3"),
             "policy_dt_s": .02,
             "modes": {mode: {name: {**copy.deepcopy(main["modes"][mode]["fwd0.5"]),
                                      "command": command, "yaw_follow_median": 1.0}
                              for name, command in EX40_B3_COMMANDS.items()}
                       for mode in MODES}}
    _write(out / "map64_b3/map_modes.json", extra)
    cfg = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    axis = {"checkpoint_sha256": digest, "envs": 64,
            "modes": {mode: {name: {"alive_at_end": 64, "stop_complete_envs": 64,
                                     "stop_end_error_median_rad": .01,
                                     "contact_left_right_gap_median": .02}
                             for name in cfg["axis_goal"]["cases"]} for mode in MODES}}
    _write(out / "axis_v2/axis_v2.json", axis)
    _write(out / "eval_receipt.json", {
        "state": "done", "smoke": False, "checkpoint": str(checkpoint),
        "checkpoint_sha256": digest, "stage": "T0", "arm": "B", "device": "cuda:1",
        "source_git_head": "a" * 40, "elapsed_seconds": 123.0,
        "score_config_sha256": sha256(DEFAULT_CONFIG), "table_sha256": sha256(DEFAULT_TABLE),
        "steps": {name: {"rc": 0, "output_path": str(out / name)} for name in PHASES}})
    result = finalize(checkpoint, out, DEFAULT_CONFIG, DEFAULT_TABLE)
    assert result["state"] == "PASS" and result["functional_only"]
    assert not result["gate_eligible"] and not result["published"]
    assert result["score_verdict_diagnostic_only"] == "PASS"
    assert len(result["charts"]) == 5
    assert all(Path(item["path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
               for item in result["charts"])
    document = (out / "stage_reports/FUNCTIONAL-EX40-B13-m17.md").read_text(encoding="utf-8")
    assert "기능시험" in document and "m8000 판정" in document
    assert not list(out.rglob("*.publish.json"))
