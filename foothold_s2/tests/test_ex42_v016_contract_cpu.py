from __future__ import annotations

from pathlib import Path

import pytest

from foothold_s2.curriculum.ex42_prep import EX42Plan


REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "foothold_s2/curriculum/ex42-prep.yaml"


def test_plan_matches_canonical_v016_and_d182_values():
    plan = EX42Plan.load(TABLE)
    doc = plan.document

    assert doc["design"]["canonical_commit"] == "69e5ac6bb5a5e16f8b5c419e8674237f3f597dd8"
    assert doc["design"]["canonical_version"] == "v0.16"
    assert doc["design"]["d182_decisions"] == {
        "expert_advice_decisions": ["D176-4", "D176-8", "D176-6", "D176-7"],
        "consecutive_hold": "exposure_only_training_continues",
        "foot_drag": {"baseline_fraction": 0.25, "spread_multiplier": 2,
                      "judge_from_stage": "E2", "class": "assumption"},
        "physical_flag_cells": "evaluation_record_only",
        "extension_e": {"slope_deg": 35.0, "stairs_height_m": 0.30},
        "pallets_l9": {"gap_m": 0.35, "height_delta_m": 0.30,
                       "one_axis_per_boundary": True},
    }
    assert doc["environment"]["training_presets"]["A"] == "start_go2_v2"
    assert doc["environment"]["training_presets"]["E"] == "paper_ext_v1"
    assert doc["terrain_manifest_contract"]["kind_count_by_family"]["E"] == 4
    assert doc["terrain_manifest_contract"]["evaluation_axis_rule"] == "harder_per_axis"
    assert doc["environment"]["evaluation"]["start_variants"] == [
        "start_go2_v2", "start_go2_eval_gap115", "start_go2_eval_sup085",
        "start_go2_eval_both",
    ]
    assert doc["evaluation"]["paper_cells"]["stairs_landing"]["height_m"] == 0.16
    assert doc["evaluation"]["paper_cells"]["stairs_landing"]["landing_depth_m"] == 1.2
    assert doc["evaluation"]["judge_cells"] == 26
    assert doc["evaluation"]["record_only_cells"] == 13
    assert doc["evaluation"]["map_modes"] == ["gt", "pred", "off"]
    assert doc["environment"]["training_presets"]["B"] == "ame2_go2_mix_v1"
    assert doc["environment"]["terrain_presets"]["B"]["climb_up_l9_m"] == 0.53
    assert doc["terrain_manifest_contract"]["kind_count_by_family"] == {
        "A": 13, "B": 12, "C": 7, "D": 3, "E": 4, "continuous": 7,
    }
    assert doc["command_allocation"]["continuous_share_min"] == 0.43
    assert doc["command_allocation"]["global_command_floor"] == {
        "reverse": 0.05, "side_left": 0.03, "side_right": 0.03,
    }


def test_v016_makes_known_values_decisions_but_keeps_unmeasured_values_open():
    doc = EX42Plan.load(TABLE).document
    assert doc["launch"]["automatic"] is False
    assert doc["launch"]["require_explicit_lead_approval"] is True
    assert doc["assumptions_pending_lead"]["evaluation_friction"]["value"] is None
    assert doc["assumptions_pending_lead"]["q4_two_window_range"]["value"] is None
    assert doc["assumptions_pending_lead"]["next_jump_study_start"]["value"] is None
    assert doc["stages"][3]["id"] == "E2"
    assert doc["maintenance"]["judge_from_stage"]["foot_drag"] == "E2"
    assert doc["stages"][3]["hold_policy"] == "hold_exposure_continue_training"


def test_conditional_command_shares_respect_absolute_3072_environment_floors():
    from foothold_s2.curriculum.ex42_prep import validate_command_shares

    assert validate_command_shares(0.40, {"forward": 0.58, "reverse": 0.14,
                                          "side_left": 0.14, "side_right": 0.14}) == {
        "reverse": pytest.approx(0.056), "side_left": pytest.approx(0.056),
        "side_right": pytest.approx(0.056),
    }
    with pytest.raises(ValueError, match="global floor"):
        validate_command_shares(0.35, {"forward": 0.58, "reverse": 0.14,
                                       "side_left": 0.14, "side_right": 0.14})


def test_global_command_floors_are_present_on_every_stage_and_fail_closed():
    plan = EX42Plan.load(TABLE)
    expected = {"reverse": 0.05, "side_left": 0.03, "side_right": 0.03}
    assert all(stage["terrain"]["floors"]["global_command_floor"] == expected
               for stage in plan.document["stages"])
    assert plan.validate_stage_command_shares(
        "E1", 0.40, {"forward": 0.58, "reverse": 0.14,
                     "side_left": 0.14, "side_right": 0.14})["reverse"] == pytest.approx(0.056)
    with pytest.raises(ValueError, match="global floor"):
        plan.validate_stage_command_shares(
            "E1", 0.35, {"forward": 0.58, "reverse": 0.14,
                         "side_left": 0.14, "side_right": 0.14})

    document = plan.document.copy()
    document["stages"] = [dict(stage) for stage in plan.document["stages"]]
    document["stages"][0]["terrain"] = {"floors": {"global_command_floor": {"reverse": 0.04}}}
    import yaml
    broken = TABLE.with_name(".ex42-missing-stage-floor.yaml")
    try:
        broken.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        with pytest.raises(ValueError, match="stage global command floors"):
            EX42Plan.load(broken)
    finally:
        broken.unlink(missing_ok=True)
