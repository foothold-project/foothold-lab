"""Pinned, numeric evidence for an automatic E1 HOLD extension.

The score receipts from the two preceding boundaries must be present in the
same run.  A missing or incomparable cell is a request for lead review, not a
reason to train another segment.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("extension metric is missing or nonfinite")
    return float(value)


def _read_boundary(path: Path, stage: str, iteration: int, current: dict):
    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    if (receipt.get("state") != "complete" or receipt.get("stage_id") != stage
            or receipt.get("checkpoint_iteration") != iteration
            or receipt.get("plan_sha256") != current.get("plan_sha256")
            or receipt.get("evaluation_plan") != current.get("evaluation_plan")):
        raise ValueError(f"extension boundary identity differs: {path}")
    score_path = path.parent / "ex42_score.json"
    if (Path(receipt.get("measurement", "")).resolve() != score_path.resolve()
            or _sha(score_path) != receipt.get("measurement_sha256")):
        raise ValueError(f"extension score pin differs: {path}")
    score = json.loads(score_path.read_text(encoding="utf-8-sig"))
    if score.get("checkpoint_sha256") != receipt.get("checkpoint_sha256") or score.get("stage_id") != stage:
        raise ValueError(f"extension checkpoint pin differs: {path}")
    return score, {"iteration": iteration, "gate_path": str(path), "gate_sha256": _sha(path),
                   "score_path": str(score_path), "score_sha256": receipt["measurement_sha256"]}


def _gaps(score: dict, plan: dict) -> dict[str, dict]:
    result = {}
    v2 = score.get("e1_exit_v2")
    if isinstance(v2, dict):
        cfg = plan["evaluation"]["e1_exit_v2"]
        for key, row in (v2.get("current") or {}).get("items", {}).items():
            if not isinstance(row, dict) or row.get("role") == "record":
                continue
            if row.get("judgement") not in ("PASS", "FAIL", "HOLD"):
                raise ValueError(f"extension E1 v2 judgment missing: {key}")
            if row.get("judgement") == "HOLD" and "R" not in row and "S" not in row and "median_abs_rad" not in row:
                raise ValueError(f"extension E1 v2 cell has no numeric evidence: {key}")
            if key.startswith(("low/", "side05/")):
                speed = _number(row["command_mps"])
                limits = {"R": (cfg["R_min"], cfg["R_max"]),
                          "mae_mps": (0, cfg["mae_fraction"] * speed),
                          "success": (cfg["success_min"], math.inf),
                          "survival": (cfg["survival_min"], math.inf)}
            elif key.startswith("yaw/"):
                limits = {"median_abs_rad": (0, cfg["yaw_median_max_rad"]),
                          "p90_abs_rad": (0, cfg["yaw_p90_max_rad"]),
                          "survival": (cfg["survival_min"], math.inf)}
            elif key.startswith("symmetry/"):
                limits = {"S": (cfg["symmetry_min"], math.inf)}
            else:
                raise ValueError(f"extension E1 v2 cell unknown: {key}")
            for metric, (low, high) in limits.items():
                value = _number(row[metric])
                result[f"e1_v2/{key}/{metric}"] = {
                    "measured": value, "lower": low if math.isfinite(low) else None,
                    "upper": high if math.isfinite(high) else None,
                    "gap": max(low - value, value - high, 0.0)}
    d44 = (score.get("e1_exit") or {}).get("d44") or {}
    for case in d44.get("required_cases", []):
        if v2 is not None and case.startswith("stop_restart_"):
            continue  # E1 v2 makes stop/restart record only.
        row = (d44.get("cases", {}).get(case) or {}).get("current")
        if not isinstance(row, dict) or row.get("case_id") != case:
            raise ValueError(f"extension D44 cell missing: {case}")
        for metric, threshold in (("success_count", "success_min"), ("survival_count", "survival_min")):
            floor, value = _number(row[threshold]), _number(row[metric])
            result[f"d44/{case}/{metric}"] = {"measured": value, "lower": floor,
                                                "upper": None, "gap": max(floor - value, 0.0)}
    return result


def improvement_evidence(plan, stage: str, iteration: int, interval: int, p1_path: Path) -> dict:
    """Allow only a pinned two-step move toward the existing exit threshold.

    At least one currently failing numeric metric must improve at both steps;
    none of the currently failing metrics may worsen in the last step.  These
    comparisons add no new performance threshold to the approved plan.
    """
    try:
        if stage != "E1":
            raise ValueError(f"extension numeric evidence for {stage} is not implemented")
        p1_path = Path(p1_path)
        if p1_path.parent.name != f"m{iteration}" or iteration - 2 * interval <= 0:
            raise ValueError("two preceding boundary receipts are unavailable")
        root = p1_path.parent.parent
        current_receipt = json.loads(p1_path.read_text(encoding="utf-8-sig"))
        if current_receipt.get("plan_sha256") != plan.sha256:
            raise ValueError("extension execution plan pin differs")
        policy_ref = current_receipt.get("evaluation_plan") or {}
        policy_path = Path(policy_ref.get("path", ""))
        if not policy_path.is_absolute() or _sha(policy_path) != policy_ref.get("sha256"):
            raise ValueError("extension evaluation plan pin differs")
        import yaml
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8-sig"))
        scores, pins = [], []
        for number in (iteration - 2 * interval, iteration - interval, iteration):
            score, pin = _read_boundary(root / f"m{number}" / "p1_score.json", stage, number, current_receipt)
            scores.append(score)
            pins.append(pin)
        fingerprints = [s.get("score_config_sha256") for s in scores]
        if not all(isinstance(v, str) and len(v) == 64 for v in fingerprints) or len(set(fingerprints)) != 1:
            raise ValueError("extension score configuration changed between boundaries")
        if any(s.get("execution_plan_sha256", plan.sha256) != plan.sha256 for s in scores):
            raise ValueError("extension score execution plan differs")
        stage_row = next(row for row in plan.document["stages"] if row["id"] == stage)
        if stage_row.get("exit_judge") == "map39_e1_v2_two_window" and any(
                not isinstance(s.get("e1_exit_v2"), dict) for s in scores):
            raise ValueError("extension E1 v2 evidence missing")
        gaps = [_gaps(score, policy) for score in scores]
        if not gaps[2] or set(gaps[0]) != set(gaps[1]) or set(gaps[1]) != set(gaps[2]):
            raise ValueError("extension metric coverage differs between boundaries")
        deficient = {key: gaps[2][key] for key in gaps[2]
                     if any(gap[key]["gap"] > 0 for gap in gaps)}
        if not deficient:
            raise ValueError("no numeric deficient metric moves toward its threshold")
        rows = []
        for key, value in sorted(deficient.items()):
            if any((gap[key]["lower"], gap[key]["upper"]) !=
                   (value["lower"], value["upper"]) for gap in gaps[:2]):
                raise ValueError(f"extension threshold differs: {key}")
            rows.append({"metric": key, "lower": value["lower"], "upper": value["upper"],
                         "older_measured": gaps[0][key]["measured"],
                         "previous_measured": gaps[1][key]["measured"],
                         "current_measured": value["measured"],
                         "older_gap": gaps[0][key]["gap"],
                         "previous_gap": gaps[1][key]["gap"], "current_gap": value["gap"]})
        if not any(r["older_gap"] > r["previous_gap"] > r["current_gap"] for r in rows):
            raise ValueError("no deficient metric improved across both preceding boundaries")
        if any(r["current_gap"] > r["previous_gap"] for r in rows):
            raise ValueError("a deficient metric moved away from its threshold")
        return {"state": "PASS", "evaluation_plan": policy_ref, "boundaries": pins, "metrics": rows,
                "rule": "one failing gap decreases twice, no failing gap worsens at the latest boundary"}
    except (KeyError, TypeError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {"state": "HOLD", "reason": str(exc)}
