"""Synthetic known answers, counterexamples and frozen criteria for encounter comparison."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from s2_compare_ab import compare, freeze, wilson


def check(label, good):
    print(("PASS" if good else "FAIL") + " " + label, flush=True)
    if not good:
        raise AssertionError(label)


def event(arm, terrain, cp, j, outcome):
    return {"arm": arm, "terrain": terrain, "terrain_instance": terrain+"-scene",
            "terrain_seed": 100+j, "difficulty": 2, "env": j, "episode": cp,
            "obstacle_id": terrain+str(j), "command_bin": "forward", "update": cp, "approach": True,
            "outcome": outcome, "block": terrain+"-"+str(cp)+"-"+str(j)}


def test_all():
    with tempfile.TemporaryDirectory(prefix="s2_step4_compare_") as td:
        root = Path(td)
        cp, lp, dp = (root/n for n in ("criteria.json", "criteria.lock", "events.json"))
        criteria = {"terrains": ["gap", "stones"], "arms": ["A", "B-mlp", "B-attn"],
                    "final_checkpoint": 4, "window_updates": 2, "min_assigned": 2,
                    "min_approach": 2, "min_blocks": 2, "bootstrap_reps": 200,
                    "bootstrap_seed": 7, "z": 1.96, "min_mean_delta": .1,
                    "min_delta_lower": 0.0}
        cp.write_text(json.dumps(criteria), encoding="utf-8")
        receipt = freeze(cp, lp)
        events = []
        for checkpoint in (2, 4):
            for terrain in criteria["terrains"]:
                for j in (0, 1):
                    events.append(event("A", terrain, checkpoint, j, "fall"))
                    events.append(event("B-mlp", terrain, checkpoint, j, "pass"))
                    if j == 0:
                        events.append(event("B-attn", terrain, checkpoint, j, "pass"))
        data = {"stages": {"2": "PASS", "4": "PASS"}, "events": events}
        dp.write_text(json.dumps(data), encoding="utf-8")
        result = compare(dp, cp, lp)
        check("frozen_hash_in_report", result["criteria_sha256"] == receipt["criteria_sha256"])
        check("known_wilson_zero_two", wilson(0, 2, 1.96)[0] == 0.0)
        check("assigned_primary_and_approach_secondary", result["rows"][1]["assigned_pass_rate"] == 1 and
              result["rows"][1]["approach_pass_rate"] == 1)
        check("nonoverlap_and_cumulative", result["rows"][-2]["window"] == [3, 4] and
              result["rows"][-2]["cumulative_counts"]["assigned"] == 4)
        check("paired_delta_ci_known_answer", result["rows"][1]["delta_interval_exploratory"] == (1.0, 1.0) and
              result["final_only"]["B-mlp"] == "탐색 기준 충족")
        check("insufficient_attn_indeterminate", result["final_only"]["B-attn"] == "판정 불가")
        first = copy.deepcopy(criteria)
        first["arms"] = ["A", "B-mlp"]
        first_cp, first_lp, first_dp = (root/n for n in ("first.json", "first.lock", "first_events.json"))
        first_cp.write_text(json.dumps(first), encoding="utf-8")
        freeze(first_cp, first_lp)
        first_dp.write_text(json.dumps({"stages": data["stages"],
                                        "events": [e for e in events if e["arm"] in first["arms"]]}), encoding="utf-8")
        first_result = compare(first_dp, first_cp, first_lp)
        check("first_chain_mlp_only", first_result["design"] == "first A/B MLP" and
              set(first_result["final_only"]) == {"B-mlp"} and
              all(row["difficulty"] == 2 and row["command_bin"] == "forward"
                  for row in first_result["strata_rows"]))
        selection = copy.deepcopy(data)
        avoid = next(e for e in selection["events"] if e["arm"] == "B-mlp" and e["update"] == 4)
        avoid["approach"] = False
        avoid["outcome"] = "avoid"
        dp.write_text(json.dumps(selection), encoding="utf-8")
        selected = compare(dp, cp, lp)
        check("assigned_primary_rate", any(row["arm"] == "B-mlp" and row["checkpoint"] == 4 and
              row["assigned_pass_rate"] == .5 and row["approach_pass_rate"] == 1.0
              for row in selected["rows"]))
        check("assigned_denominator_exposes_avoidance", any(
              row["selection_changed"] and row["arm"] == "B-mlp" and
              row["window_counts"]["assigned"] == 2 and row["window_counts"]["approach"] == 1
              for row in selected["rows"]))
        dp.write_text(json.dumps(data), encoding="utf-8")
        wrong_block = copy.deepcopy(data)
        wrong_block["events"][1]["command_bin"] = "sideways"
        dp.write_text(json.dumps(wrong_block), encoding="utf-8")
        try:
            compare(dp, cp, lp)
        except ValueError as exc:
            check("block_stratum_conflict_rejected", str(exc) == "block_identity_mismatch")
        else:
            check("block_stratum_conflict_rejected", False)
        dp.write_text(json.dumps(data), encoding="utf-8")
        mutated = copy.deepcopy(data)
        mutated["events"].append(mutated["events"][0])
        dp.write_text(json.dumps(mutated), encoding="utf-8")
        try:
            compare(dp, cp, lp)
        except ValueError as exc:
            check("duplicate_event_rejected", str(exc) == "duplicate_encounter")
        else:
            check("duplicate_event_rejected", False)
        dp.write_text(json.dumps(data), encoding="utf-8")
        criteria["min_mean_delta"] = .99
        cp.write_text(json.dumps(criteria), encoding="utf-8")
        try:
            compare(dp, cp, lp)
        except ValueError as exc:
            check("post_result_threshold_change_rejected", str(exc) == "criteria_digest_mismatch")
        else:
            check("post_result_threshold_change_rejected", False)


if __name__ == "__main__":
    test_all()
