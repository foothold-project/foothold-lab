"""Known-answer E1 v2 gates. No Kit or GPU is started here."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2.ex42_e1_v2 import judge_cells, measure_cells, treatment
from foothold_s2.tools.ex42_boundary_autojudge import body_forward_per_env
from foothold_s2.eval.map_mode_cells import commands
from foothold_s2.ex42_eval_once import e1_v2_commands

ROOT = Path(__file__).resolve().parents[2]
PLAN = yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text())


def _pass_cells():
    base = {"R": 1.0, "mae_mps": .01, "success": 60, "survival": 64, "envs": 64}
    yaw = {"median_abs_rad": .04, "p90_abs_rad": .08, "survival": 64, "envs": 64}
    return {"low": {f"L{level}": {mode: {case: {**base, "command_mps": .1}
                                           for case in commands("e1_v2")}
                                  for mode in ("eval_gt", "eval_pred", "probe_prop_only")}
                    for level in (0, 5)},
            "side05": {mode: {case: {**base, "command_mps": .5} for case in ("side+0.5", "side-0.5")}
                       for mode in ("eval_gt", "eval_pred", "probe_prop_only")},
            "yaw": {mode: {case: yaw.copy() for case in ("fwd0.5", "fwd1.0")}
                    for mode in ("eval_gt", "eval_pred", "probe_prop_only")}}


def test_body_forward_shared_formula_is_signed_and_alive_weighted():
    vx = np.array([[.1, -.1], [.2, 99.]], dtype=float)
    alive = np.array([[1, 1], [1, 0]], dtype=bool)
    assert np.allclose(body_forward_per_env(vx, alive, .02, .1), [1.5, -1])


def test_pass_requires_every_direction_and_mode_and_keeps_off_record_only():
    cells = _pass_cells()
    judged = judge_cells(cells, PLAN)
    assert judged["judgement"] == "PASS"
    assert judged["items"]["low/L0/probe_prop_only/fwd0.1"]["role"] == "record"
    cells["low"]["L5"]["eval_pred"]["side-0.2"]["success"] = 0
    assert judge_cells(cells, PLAN)["judgement"] == "FAIL"
    cells["low"]["L5"]["eval_pred"].pop("side-0.2")
    assert judge_cells(cells, PLAN)["items"]["low/L5/eval_pred/side-0.2"]["judgement"] == "HOLD"


def test_symmetry_cannot_mask_two_slow_directions_or_sign():
    cells = _pass_cells()
    for case in ("side+0.4", "side-0.4"):
        cells["low"]["L0"]["eval_gt"][case]["R"] = .7
    judged = judge_cells(cells, PLAN)
    assert judged["items"]["symmetry/0/eval_gt/0.4"]["S"] == 1
    assert judged["judgement"] == "FAIL"
    cells["low"]["L0"]["eval_gt"]["side+0.4"]["R"] = -.1
    assert judge_cells(cells, PLAN)["items"]["symmetry/0/eval_gt/0.4"]["judgement"] == "FAIL"


def test_yaw_tail_and_three_seed_near_boundary():
    cells = _pass_cells()
    cells["yaw"]["eval_gt"]["fwd1.0"]["p90_abs_rad"] = .19
    assert judge_cells(cells, PLAN)["items"]["yaw/eval_gt/fwd1.0"]["judgement"] == "HOLD"
    repeats = {7: copy.deepcopy(cells), 13: copy.deepcopy(cells)}
    assert judge_cells(cells, PLAN, repeats=repeats)["judgement"] == "PASS"
    repeats[13]["yaw"]["eval_gt"]["fwd1.0"]["p90_abs_rad"] = .21
    assert judge_cells(cells, PLAN, repeats=repeats)["items"]["yaw/eval_gt/fwd1.0"]["judgement"] == "HOLD"


def test_fixed_treatment_fingerprint_distinguishes_adjustment(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"checkpoint")
    for boundary in (1, 2):
        (tmp_path / f"segment_commands_b{boundary}.json").write_text(json.dumps(
            {"boundary_index": boundary, "stage_id": "E1", "commands": {"forward": .2}}))
        (tmp_path / f"segment_rewards_b{boundary}_rank0.json").write_text(json.dumps(
            {"boundary_index": boundary, "stage_id": "E1", "live": {"zero_yaw": -1}}))
        (tmp_path / f"segment_rewards_b{boundary}_rank1.json").write_text(json.dumps(
            {"boundary_index": boundary, "stage_id": "E1", "live": {"zero_yaw": -1}}))
    first = treatment(tmp_path / "model_250.pt", 250)
    second = treatment(checkpoint, 500)
    assert first["sha256"] == second["sha256"]
    (tmp_path / "segment_rewards_b2_rank0.json").write_text(json.dumps(
        {"boundary_index": 2, "stage_id": "E1", "live": {"zero_yaw": -2}}))
    with pytest.raises(ValueError, match="identity differs"):
        treatment(checkpoint, 500)
    (tmp_path / "segment_rewards_b2_rank1.json").write_text(json.dumps(
        {"boundary_index": 2, "stage_id": "E1", "live": {"zero_yaw": -2}}))
    assert treatment(checkpoint, 500)["sha256"] != first["sha256"]


def test_failed_axis_is_not_hidden_by_near_threshold_or_repeat():
    cells = _pass_cells()
    cells["low"]["L0"]["eval_gt"]["fwd0.1"].update(R=.8, success=0)
    judged = judge_cells(cells, PLAN, repeats={7: copy.deepcopy(cells), 13: copy.deepcopy(cells)})
    assert judged["items"]["low/L0/eval_gt/fwd0.1"]["judgement"] == "FAIL"


def test_small_improvement_over_prior_failure_requires_three_seeds():
    cells = _pass_cells()
    prior = copy.deepcopy(cells)
    prior["low"]["L0"]["eval_gt"]["fwd0.1"]["R"] = .798
    cells["low"]["L0"]["eval_gt"]["fwd0.1"]["R"] = .802
    row = judge_cells(cells, PLAN, previous_cells=prior)["items"]["low/L0/eval_gt/fwd0.1"]
    assert row["judgement"] == "HOLD" and row["near_threshold"]


def test_approved_threshold_mutations_change_only_the_target_cell():
    """Known-answer probes catch relaxed success, survival, symmetry and yaw guards."""
    cfg = PLAN["evaluation"]["e1_exit_v2"]
    assert {key: cfg[key] for key in ("R_min", "R_max", "mae_fraction", "success_min",
                                        "survival_min", "symmetry_min", "yaw_median_max_rad",
                                        "yaw_p90_max_rad")} == {
        "R_min": .8, "R_max": 1.2, "mae_fraction": .2, "success_min": 52,
        "survival_min": 60, "symmetry_min": .8, "yaw_median_max_rad": .1,
        "yaw_p90_max_rad": .2}
    for change in ({"success": 51}, {"survival": 59, "success": 52}, {"R": .79}, {"R": 1.21},
                   {"mae_mps": .021}):
        cells = _pass_cells()
        cells["low"]["L0"]["eval_gt"]["fwd0.1"].update(change)
        assert judge_cells(cells, PLAN)["items"]["low/L0/eval_gt/fwd0.1"]["judgement"] == "FAIL"
    cells = _pass_cells()
    cells["low"]["L0"]["eval_gt"]["side+0.4"]["R"] = .8
    cells["low"]["L0"]["eval_gt"]["side-0.4"]["R"] = 1.02
    assert judge_cells(cells, PLAN)["items"]["symmetry/0/eval_gt/0.4"]["judgement"] == "FAIL"
    cells = _pass_cells()
    cells["yaw"]["eval_gt"]["fwd1.0"].update(median_abs_rad=.11, p90_abs_rad=.15)
    assert judge_cells(cells, PLAN)["items"]["yaw/eval_gt/fwd1.0"]["judgement"] == "FAIL"


def test_p1_low_children_use_actual_eval_map_modes_parser_options(tmp_path):
    from foothold_s2.ex42_score import config
    cfg, _ = config()
    rows = e1_v2_commands(tmp_path / "model_500.pt", tmp_path, "cuda:1", cfg,
                          eval_seed=42, mesh_dir=tmp_path / "mesh",
                          evaluation_plan=ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    assert [name for name, _ in rows] == ["e1_v2_L0", "e1_v2_L5"]
    parser_source = (ROOT / "foothold_s2/eval/eval_map_modes.py").read_text()
    for name, argv in rows:
        assert argv[1:3] == ["-m", "foothold_s2.eval.eval_map_modes"]
        assert argv[argv.index("--command-suite") + 1] == "e1_v2"
        assert argv[argv.index("--fixed-level") + 1] == name[-1]
        assert argv[argv.index("--modes") + 1] == "eval_gt,eval_pred,probe_prop_only"
        for flag in ("--fixed-terrain", "--fixed-level", "--mesh-dir", "--command-suite"):
            assert f'parser.add_argument("{flag}"' in parser_source


def test_real_m2000_is_not_promoted_with_missing_low_modes():
    folder = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/"
                  "EX-42-B-E1-cmd7seg_20261112_164150/eval/scores/m2000")
    if not folder.is_dir():
        pytest.skip("read-only E1 source absent on this machine")
    score = json.loads((folder / "ex42_score.json").read_text())
    cells = measure_cells(folder, score["checkpoint_sha256"], 42)
    assert cells["low"]["L0"]["state"] == "HOLD"
    assert judge_cells(cells, PLAN)["judgement"] != "PASS"
    assert abs(cells["yaw"]["eval_gt"]["fwd1.0"]["median_abs_rad"] - .1178396) < 1e-5
