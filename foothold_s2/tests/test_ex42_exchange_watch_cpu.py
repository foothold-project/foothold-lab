"""Known inputs for the E2 current-versus-previous evaluation watch."""
from __future__ import annotations

import copy

from foothold_s2.ex42_exchange_watch import compare


MODES = ("eval_gt", "eval_pred", "probe_prop_only")


def _fixtures():
    baseline = {"metrics": {}}
    score = {"stage_id": "E2", "score_config_sha256": "a" * 64,
             "conditions": {"eval_seed": 42},
             "e2_kind": {"mesh_sha256": "b" * 64},
             "map64": {}, "axis_v2": {}, "stand": {},
             "d44_cells": {"turn_left_eval_gt": {"valid_count": 64,
                                                  "success_count": 60, "survival_count": 62}},
             "flag_cells": {"flag_one_eval_gt": {"valid_count": 64,
                                                  "success_count": 60, "survival_count": 62}}}
    kind = {}
    for mode in MODES:
        score["map64"][mode] = {}
        for index in range(13):
            case = f"case{index}"
            score["map64"][mode][case] = {
                "alive_at_end": 60, "vx_abs_error_median_mps": .1,
                "vy_abs_error_median_mps": .1, "wz_abs_error_median_radps": .1,
                "command_projection_median_m": 3.0}
            baseline["metrics"][f"map64/{mode}/{case}/command_projection_median_m"] = {
                "parent_median": 3.0}
        score["axis_v2"][mode] = {"case0": {"foot_drag_proxy_m_by_foot_median": [.1] * 4}}
        for foot in range(4):
            baseline["metrics"][f"axis_v2/{mode}/case0/foot_drag_proxy_m_by_foot_median/{foot}"] = {
                "rise_limit_m": .05}
        score["stand"][mode] = {"per_foot_contact_fraction_median": {
            foot: .8 for foot in ("FL", "FR", "RL", "RR")}}
        kind[mode] = {subcell: {"valid_count": 64, "success_count": 55, "survival_count": 62}
                      for subcell in ("forward", "flag_four")}
    measured = {"survival_drop_envs": 6, "error_rise_vx_vy_mps": .05125,
                "error_rise_wz_radps": .05}
    return score, kind, measured, baseline


def test_equal_previous_boundary_passes_all_judge_sources():
    previous, kind, measured, baseline = _fixtures()
    current = copy.deepcopy(previous)
    row = compare(current, previous, measured=measured, baseline=baseline,
                  kind_now=kind, kind_previous=kind)
    assert row["judgement"] == "PASS" and row["missing"] == []
    assert row["compared"] >= 26 * 5
    assert row["record_only_deltas"]


def test_survival_projection_drag_and_kind_regressions_hold_with_paths():
    previous, kind, measured, baseline = _fixtures()
    current = copy.deepcopy(previous)
    kind_now = copy.deepcopy(kind)
    current["map64"]["eval_gt"]["case0"]["alive_at_end"] = 53
    current["map64"]["eval_gt"]["case1"]["command_projection_median_m"] = 2.6
    current["axis_v2"]["eval_gt"]["case0"]["foot_drag_proxy_m_by_foot_median"][0] = .16
    kind_now["eval_pred"]["flag_four"]["success_count"] = 48
    row = compare(current, previous, measured=measured, baseline=baseline,
                  kind_now=kind_now, kind_previous=kind)
    assert row["judgement"] == "HOLD" and not row["missing"]
    paths = {item["cell"] for item in row["violations"]}
    assert paths == {"map64/eval_gt/case0/alive_at_end",
                     "map64/eval_gt/case1/command_projection_median_m",
                     "axis_v2/eval_gt/case0/foot_drag_proxy_m_by_foot_median/0",
                     "kind/eval_pred/flag_four/success_count"}


def test_missing_prior_or_different_identity_stays_hold():
    previous, kind, measured, baseline = _fixtures()
    assert compare(previous, None, measured=measured, baseline=baseline,
                   kind_now=kind, kind_previous=None)["missing"] == ["previous_boundary"]
    current = copy.deepcopy(previous)
    current["conditions"]["eval_seed"] = 43
    assert compare(current, previous, measured=measured, baseline=baseline,
                   kind_now=kind, kind_previous=kind)["missing"] == ["identity"]
    current = copy.deepcopy(previous)
    current["flag_cells"] = {}
    assert "flag_cells" in compare(current, previous, measured=measured,
                                   baseline=baseline, kind_now=kind,
                                   kind_previous=kind)["missing"]


def test_stage_specific_identity_and_kind_subcells_are_checked():
    previous, kind, measured, baseline = _fixtures()
    previous["stage_id"] = "E3"
    previous["e3_kind"] = previous.pop("e2_kind")
    current = copy.deepcopy(previous)
    row = compare(current, previous, measured=measured, baseline=baseline,
                  kind_now=kind, kind_previous=kind, stage_id="E3",
                  kind_score_key="e3_kind", kind_subcells=("forward", "flag_four"))
    assert row["judgement"] == "PASS"
    current["e3_kind"]["mesh_sha256"] = "c" * 64
    row = compare(current, previous, measured=measured, baseline=baseline,
                  kind_now=kind, kind_previous=kind, stage_id="E3",
                  kind_score_key="e3_kind", kind_subcells=("forward", "flag_four"))
    assert row["missing"] == ["identity"]
    current = copy.deepcopy(previous)
    broken = copy.deepcopy(kind)
    del broken["eval_pred"]["flag_four"]
    row = compare(current, previous, measured=measured, baseline=baseline,
                  kind_now=broken, kind_previous=kind, stage_id="E3",
                  kind_score_key="e3_kind", kind_subcells=("forward", "flag_four"))
    assert "kind/eval_pred/flag_four/success_count" in row["missing"]
