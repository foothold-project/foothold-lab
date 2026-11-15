"""E1 graduation evaluation plan: the decisions live in evaluation.e1_widened.graduation and the plan sha pins them."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from foothold_s2 import ex42_e1_v2
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.ex42_e1_v2 import check_graduation, graduation, judge_cells, plan_mae_window_s
from foothold_s2.ex42_e1_wide import judge_cells as judge_wide
from foothold_s2.ex42_e1_wide_plan import validate_evaluation_scope, widened_contract, write_evaluation_plan

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
PARENT = "cfa5bf53e67258cbc98f91c1a6c5d2215411f879408657daa628698aae4060dc"
APPROVED = {"mae_window_s": 0.5, "near_R_0p1": 0.06, "l3_fwd10_role": "judge_if_exposed",
            "fixed_fwd10_rule": "heading_forward", "parent_evaluation_plan_sha256": PARENT}


def test_only_approved_keys_and_values_pass_the_graduation_check():
    assert check_graduation(None) == {}
    assert check_graduation(dict(APPROVED)) == APPROVED
    for bad in ({"mae_window_s": 0}, {"mae_window_s": 30}, {"mae_window_s": float("nan")},
                {"near_R_0p1": 0.9}, {"l3_fwd10_role": "judge"}, {"fixed_fwd10_rule": "projection"},
                {"parent_evaluation_plan_sha256": "abc"}, {"survival_min": 1}):
        with pytest.raises(ValueError, match="unapproved"):
            check_graduation(bad)


def test_derived_plan_without_graduation_is_the_running_plan_byte_for_byte(tmp_path):
    source_sha = EX42Plan.load(SOURCE).sha256
    policy = write_evaluation_plan(SOURCE, tmp_path / "a" / SOURCE.name, source_sha)
    assert "graduation" not in policy.document["evaluation"]["e1_widened"]
    assert policy.document["evaluation"]["e1_widened"]["fixed_forward_roles"][3] == "judge_if_exposed"
    if source_sha == "1f4ff70d8820e2e754ed1120b821fafb22a04e40d7f84f1ff0a9a9cfedff8a92":
        assert policy.sha256 == PARENT       # the evaluation plan the v29c run uses today


def test_graduation_block_is_the_only_extra_and_the_scope_check_still_refuses_everything_else(tmp_path):
    source_sha = EX42Plan.load(SOURCE).sha256
    plain = write_evaluation_plan(SOURCE, tmp_path / "a" / SOURCE.name, source_sha)
    policy = write_evaluation_plan(SOURCE, tmp_path / "b" / SOURCE.name, source_sha, graduation=dict(APPROVED))
    assert policy.sha256 != plain.sha256
    assert graduation(policy.document) == APPROVED and plan_mae_window_s(policy.document) == 0.5
    # the two plans differ by the graduation block only
    stripped = copy.deepcopy(policy.document)
    stripped["evaluation"]["e1_widened"].pop("graduation")
    assert stripped == plain.document
    validate_evaluation_scope(SOURCE, policy.path)
    text = policy.path.read_text()
    for old, new in (("window_episodes: 64", "window_episodes: 63"),      # outside evaluation.e1_widened
                     ("near_R_0p1: 0.06", "near_R_0p1: 0.9"),             # value not approved
                     ("mae_window_s: 0.5", "mae_window_s: 0.5\n      unknown_key: 1")):
        policy.path.write_text(text.replace(old, new, 1))
        with pytest.raises(ValueError):
            validate_evaluation_scope(SOURCE, policy.path)
    start = text.index("e1_widened:")                         # a change inside the block, next to the approved one
    inside = text[:start] + text[start:].replace("survival_min: 60", "survival_min: 50", 1)
    assert inside != text
    policy.path.write_text(inside)
    with pytest.raises(ValueError):
        validate_evaluation_scope(SOURCE, policy.path)
    policy.path.write_text(text)
    with pytest.raises(ValueError, match="unapproved"):
        write_evaluation_plan(SOURCE, tmp_path / "c" / SOURCE.name, source_sha, graduation={"mae_window_s": 99})


def test_l3_role_field_really_drives_the_wide_judgement():
    plan = yaml.safe_load(SOURCE.read_text())
    on = widened_contract(plan, {"l3_fwd10_role": "judge_if_exposed"})
    off = widened_contract(plan, {"l3_fwd10_role": "record_only"})
    assert on["fixed_forward_roles"][3] == "judge_if_exposed" and off["fixed_forward_roles"][3] == "record_only"
    assert widened_contract(plan) == on                      # no block = judged, as before
    cells = {"fixed": {"L3": {m: {"fwd1.0": {"valid_count": 64, "success_count": 64, "survival_count": 64}}
                              for m in ("eval_gt", "eval_pred", "probe_prop_only")}}, "endpoints": {}}
    for contract, role in ((on, "judge"), (off, "record_only")):
        doc = copy.deepcopy(plan)
        doc["evaluation"]["e1_widened"] = contract
        try:
            items = judge_wide(cells, doc, cap=3)["items"]
        except (KeyError, ValueError):                       # sparse cells: only the L3 item is asserted below
            pytest.skip("wide judge needs the full cell set on this plan")
        assert items["wide_L3_fwd1.0/eval_gt"]["role"] == role


def test_near_threshold_comes_from_the_graduation_block():
    base = {"R": 0.83, "survival": 64, "envs": 64, "command_mps": 0.1, "mae_mps": 0.0, "success": 64,
            "per_env_R": [0.83] * 64, "per_env_mae_mps": [0.0] * 64, "per_env_alive_end": [True] * 64}
    modes = ("eval_gt", "eval_pred", "probe_prop_only")
    yaw = {"median_abs_rad": .04, "p90_abs_rad": .08, "survival": 64, "envs": 64}

    def cells():
        low = {}
        for level in ("L0", "L5"):
            low[level] = {m: {c: {**base, "command_mps": (.1 if c == "fwd0.1" else .2 if c == "fwd0.2" else float(c[4:]))}
                              for c in ex42_e1_v2.LOW_CASES} for m in modes}
        return {"low": low,
                "side05": {m: {c: {**base, "command_mps": .5} for c in ("side+0.5", "side-0.5")} for m in modes},
                "yaw": {m: {c: yaw.copy() for c in ("fwd0.5", "fwd1.0")} for m in modes}}

    plan = yaml.safe_load(SOURCE.read_text())
    r_min = plan["evaluation"]["e1_exit_v2"]["R_min"]
    row = lambda doc: judge_cells(cells(), doc)["items"]["low/L0/eval_gt/fwd0.1"]
    low_edge = r_min + 0.03                  # 0.03 above the lower bound: outside the plan's width, inside 0.06
    base.update({"R": low_edge, "per_env_R": [low_edge] * 64})
    assert row(plan)["near_threshold"] is False
    graduated = copy.deepcopy(plan)
    graduated["evaluation"].setdefault("e1_widened", {})["graduation"] = {"near_R_0p1": 0.06}
    assert row(graduated)["near_threshold"] is True
