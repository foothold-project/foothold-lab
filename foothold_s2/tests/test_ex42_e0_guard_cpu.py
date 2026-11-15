"""Known-input guards for seven E0 judgment mutations found in PR 631 review."""
from __future__ import annotations

import copy
import json
import shutil

import pytest
import yaml

from foothold_s2.eval.map_mode_cells import commands
from foothold_s2.ex42_e0_judge import judge, load_baseline, validate_measured_q4
from foothold_s2.ex42_eval_once import p1_score_from_measure
from foothold_s2.ex42_score import ROOT, config, digest


MODES = ("eval_gt", "eval_pred", "probe_prop_only")
METRICS = ("alive_at_end", "vx_abs_error_median_mps",
           "vy_abs_error_median_mps", "wz_abs_error_median_radps")


def _baseline_and_q4():
    cfg, _ = config()
    baseline = load_baseline(ROOT, cfg, digest)
    baseline["_sha256"] = cfg["baseline"]["sha256"]
    q4 = yaml.safe_load((ROOT / cfg["maintenance_source"]).read_text())[
        "assumptions_pending_lead"]["q4_two_window_range"]["value"]
    return baseline, q4


def _parent_score(baseline):
    return {"conditions": {"envs": 64},
            "map64": {mode: {case: {metric: baseline["metrics"][
                f"map64/{mode}/{case}/{metric}"]["parent_median"] for metric in METRICS}
                             for case in commands("extended")} for mode in MODES},
            "maintenance_items": {name: {"state": "measured_unjudged", "judgement": "HOLD"}
                                  for name in baseline["items"]}}


def test_j1_survival_drop_has_adverse_positive_direction():
    baseline, q4 = _baseline_and_q4()
    score = _parent_score(baseline)
    score["map64"]["eval_gt"]["fwd0.5"]["alive_at_end"] -= 7
    result = judge(score, baseline, q4["measured"])
    check = result["cell_judgments"]["eval_gt"]["fwd0.5"]["metrics"]["alive_at_end"]
    assert check["adverse_delta"] == 7
    assert check["judgment"] == result["judgement"] == "FAIL"


def test_j4_off_mode_is_record_only_even_when_its_numbers_fail():
    baseline, q4 = _baseline_and_q4()
    score = _parent_score(baseline)
    score["map64"]["probe_prop_only"]["fwd0.5"]["alive_at_end"] -= 10
    score["map64"]["probe_prop_only"]["fwd0.5"]["vx_abs_error_median_mps"] += 1
    result = judge(score, baseline, q4["measured"])
    off = result["cell_judgments"]["probe_prop_only"]["fwd0.5"]
    assert off["role"] == "record_only"
    assert off["judgment"] == "HOLD" and off["comparison_judgment"] == "FAIL"
    assert result["judgement"] == "PASS"


def test_j5_fail_is_not_hidden_by_a_different_hold_cell():
    baseline, q4 = _baseline_and_q4()
    score = _parent_score(baseline)
    score["map64"]["eval_gt"]["fwd0.5"]["vx_abs_error_median_mps"] = None
    score["map64"]["eval_pred"]["fwd1.0"]["alive_at_end"] -= 7
    result = judge(score, baseline, q4["measured"])
    assert result["cell_judgments"]["eval_gt"]["fwd0.5"]["judgment"] == "HOLD"
    assert result["cell_judgments"]["eval_pred"]["fwd1.0"]["judgment"] == "FAIL"
    assert result["judgement"] == "FAIL"


def test_v2_foot_drag_fraction_branch_is_checked():
    baseline, q4 = _baseline_and_q4()
    paths = [path for path, row in baseline["metrics"].items()
             if "/foot_drag_proxy_m_by_foot_median/" in path and
             .25 * row["parent_median"] > 2 * row["repeat_width"]]
    assert paths, "a parent-fraction-dominated foot-drag cell is required"
    mutated = copy.deepcopy(baseline)
    mutated["metrics"][paths[0]]["rise_limit_m"] *= 2
    with pytest.raises(ValueError, match="foot drag per-cell limits differ"):
        validate_measured_q4(mutated, q4["measured"], q4["assumed"])


def test_v3_changed_baseline_bytes_are_rejected_before_judgment(tmp_path):
    cfg, _ = config()
    copied = tmp_path / cfg["baseline"]["path"]
    copied.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / cfg["baseline"]["path"], copied)
    source = json.loads(copied.read_text())
    source["source_git_head"] = "0" * 40
    copied.write_text(json.dumps(source))
    assert digest(copied) != cfg["baseline"]["sha256"]
    with pytest.raises(ValueError, match="baseline bytes differ"):
        load_baseline(tmp_path, cfg, digest)


def _p1_inputs(tmp_path):
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    output = tmp_path / "evaluation"
    output.mkdir()
    (output / "ex42_score.json").write_text("{}")
    cases = tuple(commands("extended"))
    map64 = {mode: {case: {"alive_at_end": 64} for case in cases} for mode in MODES}
    cells = {mode: {case: {"role": "record_only" if mode == "probe_prop_only" else "judge",
                           "judgment": "HOLD" if mode == "probe_prop_only" else "PASS"}
                    for case in cases} for mode in MODES}
    score = {"checkpoint_sha256": digest(checkpoint), "map64": map64,
             "cell_judgments": cells, "judgement": "PASS"}
    return checkpoint, output, score


def _p1(score, checkpoint, output, stage):
    return p1_score_from_measure(score, checkpoint=checkpoint, iteration=250,
                                 plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
                                 approvals_path=ROOT / "foothold_s2/curriculum/ex42-approvals.yaml",
                                 stage_id=stage, output=output)


def test_e1_p1_aggregate_must_match_all_26_judged_cells(tmp_path):
    checkpoint, output, score = _p1_inputs(tmp_path)
    assert _p1(score, checkpoint, output, "E0")["judgment"] == "PASS"
    score["cell_judgments"]["eval_pred"]["fwd1.0"]["judgment"] = "FAIL"
    with pytest.raises(ValueError, match="aggregate judgment differs from 26 cells"):
        _p1(score, checkpoint, output, "E0")


def test_e2_p1_e0_verdict_cannot_be_reused_for_later_stage(tmp_path):
    checkpoint, output, score = _p1_inputs(tmp_path)
    score["execution_plan_sha256"] = digest(ROOT / "foothold_s2/curriculum/ex42-prep.yaml")
    score["stage_id"] = "E0"
    with pytest.raises(ValueError, match="E2 P1 plan or stage identity missing"):
        _p1(score, checkpoint, output, "E2")
