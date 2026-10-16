"""Paired S2 case accounting with the pinned 1043 Tango score interval."""
from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path

from s2_eval_cases import verify as verify_cases, canonical
import s2_1043_paired_ci as PCI
from s2_eval_cpu import sha as file_sha


class PostHold(ValueError):
    pass


def aggregate(cases, episodes):
    verify_cases(cases)
    if file_sha(PCI.__file__) != cases["source_sha256"]["paired_ci.py"]:
        raise PostHold("1043_pair_interval_source_sha256")
    if (episodes.get("schema") != "s2-eval-episodes-v1" or
        episodes.get("cases_sha256") != cases["cases_sha256"] or
        episodes.get("inference") != "act_inference"):
        raise PostHold("episode_source_contract")
    rows = episodes.get("records")
    if not isinstance(rows, list):
        raise PostHold("episode_rows")
    by_key = {}
    case_by_id = {c["case_id"]: c for c in cases["cases"]}
    for row in rows:
        if (row.get("case_id") not in case_by_id or row.get("arm") not in ("A", "B") or
            row.get("family") != case_by_id[row["case_id"]]["family"] or
            row.get("eval_seed") != case_by_id[row["case_id"]]["eval_seed"]):
            raise PostHold("row_identity")
        key = (row["case_id"], row["arm"])
        if key in by_key:
            raise PostHold("duplicate_case_arm")
        by_key[key] = row
    paired = []
    layers = {f: {"planned_pairs": cases["counts"][f], "valid_pairs": 0,
                  "A_success": 0, "B_success": 0, "A_fall": 0, "B_fall": 0,
                  "A_stuck": 0, "B_stuck": 0, "missing": [], "pairs": []}
              for f in cases["counts"]}
    for case in cases["cases"]:
        cid, fam = case["case_id"], case["family"]
        a, b = by_key.get((cid, "A")), by_key.get((cid, "B"))
        why = []
        for mode, row in (("A", a), ("B", b)):
            if row is None:
                why.append(mode + ":absent")
            elif row.get("missing_reason"):
                why.append(mode + ":" + row["missing_reason"])
            elif not isinstance(row.get("score"), dict) or not isinstance(row.get("fingerprint"), dict):
                why.append(mode + ":score_or_fingerprint_absent")
        if not why and a["fingerprint"] != b["fingerprint"]:
            why.append("physical_fingerprint_diff")
        if why:
            layers[fam]["missing"].append({"case_id": cid, "reasons": why})
            paired.append({"case_id": cid, "family": fam, "paired": False, "reasons": why})
            continue
        for mode, row in (("A", a), ("B", b)):
            score = row["score"]
            if (type(score.get("success")) is not bool or type(score.get("fall")) is not bool or
                score.get("success_rule") != ("1043_unseen_crossed" if fam in
                                               ("gap", "stepping_stones") else "1043_span_q1_pass")):
                raise PostHold(mode + "_score_contract")
        sa, sb = a["score"], b["score"]
        layer = layers[fam]
        layer["valid_pairs"] += 1
        layer["A_success"] += int(sa["success"])
        layer["B_success"] += int(sb["success"])
        layer["A_fall"] += int(sa["fall"])
        layer["B_fall"] += int(sb["fall"])
        layer["A_stuck"] += int(sa.get("stuck_diagnostic") is True)
        layer["B_stuck"] += int(sb.get("stuck_diagnostic") is True)
        p = {"case_id": cid, "family": fam, "paired": True,
             "A_success": sa["success"], "B_success": sb["success"],
             "B_minus_A": int(sb["success"]) - int(sa["success"]),
             "A_fall": sa["fall"], "B_fall": sb["fall"],
             "A_stuck": sa.get("stuck_diagnostic"), "B_stuck": sb.get("stuck_diagnostic"),
             "A_crossed": sa.get("crossed"), "B_crossed": sb.get("crossed")}
        layer["pairs"].append(p)
        paired.append(p)
    for fam, layer in layers.items():
        n = layer["valid_pairs"]
        b_only = sum(p["B_success"] and not p["A_success"] for p in layer["pairs"])
        a_only = sum(p["A_success"] and not p["B_success"] for p in layer["pairs"])
        layer["numerator_denominator"] = {
            "A_success": [layer["A_success"], n], "B_success": [layer["B_success"], n],
            "B_minus_A": [b_only - a_only, n], "A_fall": [layer["A_fall"], n],
            "B_fall": [layer["B_fall"], n], "A_stuck": [layer["A_stuck"], n],
            "B_stuck": [layer["B_stuck"], n]}
        layer["discordant"] = {"B_only": b_only, "A_only": a_only}
        layer["paired_tango_95"] = list(PCI.tango(b_only, a_only, n)) if n else None
        layer["missing_pairs"] = layer["planned_pairs"] - n
    result = {"schema": "s2-eval-post-v1", "cases_sha256": cases["cases_sha256"],
              "episodes_sha256": hashlib.sha256(canonical(episodes)).hexdigest(),
              "cases_file_sha256": episodes.get("cases_file_sha256"),
              "job_file_sha256": episodes.get("job_file_sha256"),
              "input_files": episodes.get("inputs", {}),
              "update": episodes["update"], "interval_method": "1043 paired_ci.tango score 95%",
              "interval_limit": "assumes independent pairs; one training seed does not measure training-seed variability",
              "layers": layers, "paired_cases": paired,
              "planned_pairs": len(cases["cases"]),
              "valid_pairs": sum(v["valid_pairs"] for v in layers.values()),
              "missing_pairs": sum(v["missing_pairs"] for v in layers.values()),
              "comparison_ready": False, "performance_verified": False}
    return result


def aggregate_from_files(*, cases_path, cases_file_sha256, episodes_path,
                         episodes_file_sha256, output_path):
    def pinned(path, expected):
        data = Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise PostHold("input_file_sha256")
        return json.loads(data)
    cases = pinned(cases_path, cases_file_sha256)
    episodes = pinned(episodes_path, episodes_file_sha256)
    if episodes.get("cases_file_sha256") != cases_file_sha256:
        raise PostHold("episode_case_file_sha256")
    result = aggregate(cases, episodes)
    result["episodes_file_sha256"] = episodes_file_sha256
    target = Path(output_path)
    if target.exists():
        raise PostHold("output_already_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical(result) + b"\n")
    return result


def main(argv=None):
    p = argparse.ArgumentParser()
    for key in ("cases_path", "cases_file_sha256", "episodes_path",
                "episodes_file_sha256", "output_path"):
        p.add_argument("--" + key.replace("_", "-"), required=True)
    a = p.parse_args(argv)
    result = aggregate_from_files(**vars(a))
    print(json.dumps({"planned_pairs": result["planned_pairs"],
                      "valid_pairs": result["valid_pairs"],
                      "missing_pairs": result["missing_pairs"],
                      "comparison_ready": False, "performance_verified": False}))


if __name__ == "__main__":
    main()
