"""Known-input A23 pin and E0 judgment counterexamples."""
import copy
from pathlib import Path

import pytest
import yaml

from foothold_s2.ex42_baseline import build
from foothold_s2.ex42_e0_judge import judge, load_baseline, validate_measured_q4
from foothold_s2.ex42_score import ROOT, config, digest
from foothold_s2.eval.map_mode_cells import commands


def test_five_repeat_parent_median_and_foot_drag_limit():
    row = {"format": "foothold-ex42-calibration/1", "state": "measured_unjudged",
           "comparison_scope": "a23_parent_matched", "eval_cols": 23,
           "seeds": [42, 42, 43, 44, 45], "checkpoint_sha256": "a" * 64,
           "mesh_sha256": "b" * 64, "source_git_head": "c" * 40,
           "metric_widths": {"axis_v2/eval_gt/fwd0.5/foot_drag_proxy_m_by_foot_median/0": {
               "values": [.1, .1, .2, .1, .1], "all_seed_width": .1}},
           "item_widths": {"foot_drag_m": {"state": "measured", "metric_count": 1,
                                           "metric_paths": ["axis_v2/eval_gt/fwd0.5/foot_drag_proxy_m_by_foot_median/0"]}},
           "missing_by_repeat": {"axis_v2/eval_gt/fwd0.5/phase/0": [0, 1, 2, 3, 4]}}
    result = build(row, "d" * 64)
    metric = result["metrics"]["axis_v2/eval_gt/fwd0.5/foot_drag_proxy_m_by_foot_median/0"]
    assert metric == {"parent_median": .1, "repeat_width": .1, "rise_limit_m": .2}
    assert result["all_null_metrics"] == row["missing_by_repeat"]
    row["metric_widths"]["axis_v2/eval_gt/fwd0.5/foot_drag_proxy_m_by_foot_median/0"]["all_seed_width"] = .01
    with pytest.raises(ValueError, match="width differs"):
        build(row, "d" * 64)
    row["metric_widths"]["axis_v2/eval_gt/fwd0.5/foot_drag_proxy_m_by_foot_median/0"]["all_seed_width"] = .1
    row["metric_widths"]["axis_v2/eval_gt/fwd0.5/foot_drag_proxy_m_by_foot_median/0"]["values"][2] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        build(row, "d" * 64)


def _score_for_parent(base):
    cases = tuple(commands("extended"))
    modes = ("eval_gt", "eval_pred", "probe_prop_only")
    map64 = {}
    for mode in modes:
        map64[mode] = {}
        for case in cases:
            map64[mode][case] = {metric: base["metrics"][f"map64/{mode}/{case}/{metric}"]["parent_median"]
                                 for metric in ("alive_at_end", "vx_abs_error_median_mps",
                                                "vy_abs_error_median_mps", "wz_abs_error_median_radps")}
    return {"conditions": {"envs": 64}, "map64": map64,
            "maintenance_items": {name: {"state": "measured_unjudged", "judgement": "HOLD"}
                                  for name in base["items"]}}


def test_pinned_26_cells_pass_fail_hold_and_record_only():
    cfg, _ = config()
    base = load_baseline(ROOT, cfg, digest)
    base["_sha256"] = cfg["baseline"]["sha256"]
    q4 = yaml.safe_load((ROOT / cfg["maintenance_source"]).read_text())[
        "assumptions_pending_lead"]["q4_two_window_range"]["value"]
    measured = q4["measured"]
    validate_measured_q4(base, measured, q4["assumed"])
    score = _score_for_parent(base)
    assert judge(score, base, measured)["judgement"] == "PASS"
    assert judge(score, base, measured)["maintenance_items"]["foot_drag_m"]["state"] == "baseline_pinned_record_only"
    score["map64"]["probe_prop_only"]["fwd0.5"]["vx_abs_error_median_mps"] += 5
    assert judge(score, base, measured)["judgement"] == "PASS"
    score["map64"]["eval_gt"]["fwd0.5"]["vx_abs_error_median_mps"] += measured["error_rise_vx_vy_mps"] + .001
    failed = judge(score, base, measured)
    assert failed["judgement"] == "FAIL"
    assert failed["cell_judgments"]["eval_gt"]["fwd0.5"]["judgment"] == "FAIL"
    score["map64"]["eval_gt"]["fwd0.5"]["vx_abs_error_median_mps"] = None
    assert judge(score, base, measured)["judgement"] == "HOLD"
    changed = copy.deepcopy(measured)
    changed["calibration_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="pin differ"):
        judge(score, base, changed)
    changed = copy.deepcopy(measured)
    changed["survival_drop_envs"] = 60
    with pytest.raises(ValueError, match="approved max rule"):
        validate_measured_q4(base, changed, q4["assumed"])


def test_baseline_bytes_and_approval_file_pin():
    cfg, _ = config()
    assert digest(ROOT / cfg["baseline"]["path"]) == cfg["baseline"]["sha256"]
    plan = yaml.safe_load((ROOT / cfg["maintenance_source"]).read_text())
    assert digest(ROOT / "foothold_s2/curriculum/ex42-approvals.yaml") == plan["stage_zero"]["approval_sha256"]
