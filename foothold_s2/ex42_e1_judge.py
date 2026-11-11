"""CPU E1 exit: pinned maintenance floors and two D44 landing windows."""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path

from foothold_s2.ex42_e0_judge import judge as judge_maintenance


def _landing_window(value: dict | None, plan: dict, case_id: str) -> dict:
    if value is None:
        return {"judgement": "HOLD", "reason": "평가 열 없음"}
    promotion = plan["evaluation"]["promotion"]
    envs = promotion["window_episodes"]
    if (not isinstance(value, dict) or value.get("case_id") != case_id or
            type(value.get("envs")) is not int or value["envs"] != envs or
            any(type(value.get(key)) is not int or not 0 <= value[key] <= envs
                for key in ("valid_count", "success_count", "survival_count")) or
            value["success_count"] > value["valid_count"] or
            not isinstance(value.get("raw_file"), str) or
            not isinstance(value.get("raw_sha256"), str) or
            re.fullmatch(r"[0-9a-f]{64}", value["raw_sha256"]) is None):
        raise ValueError("EX-42 E1 D44 landing evidence invalid")
    path = Path(value["raw_file"])
    try:
        raw = path.read_bytes()
        source = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise ValueError("EX-42 E1 D44 landing raw evidence unavailable") from exc
    if (hashlib.sha256(raw).hexdigest() != value["raw_sha256"] or
            any(source.get(key) != value[key] for key in
                ("case_id", "envs", "valid_count", "success_count", "survival_count"))):
        raise ValueError("EX-42 E1 D44 landing raw evidence differs")
    passed = value["success_count"] >= promotion["success_min"] and value["survival_count"] >= promotion["survival_min"]
    judgement = "HOLD" if value["valid_count"] != envs else "PASS" if passed else "FAIL"
    return {"judgement": judgement, "case_id": case_id,
            "envs": envs, "valid_count": value["valid_count"], "success_count": value["success_count"],
            "survival_count": value["survival_count"],
            **({"reason": "D44 무판정 env 있음"} if judgement == "HOLD" else {}),
            "success_min": promotion["success_min"], "survival_min": promotion["survival_min"],
            "raw_file": str(path), "raw_sha256": value["raw_sha256"]}


def judge_e1(score: dict, baseline: dict, measured: dict, plan: dict,
             *, previous: dict | None) -> dict:
    """Judge one E1 checkpoint with its preceding, explicitly evidenced window."""
    current = judge_maintenance(score, baseline, measured)
    earlier = judge_maintenance(previous, baseline, measured) if previous is not None else None
    windows = plan["evaluation"]["promotion"]["windows"]
    if windows != 2:
        raise ValueError("EX-42 E1 exit requires the approved two-window plan")
    case_ids = plan["evaluation"]["paper_cells"]["stairs_landing"].get("judge_cases")
    if case_ids is None:
        case_ids = []
    if not isinstance(case_ids, list) or any(
            not isinstance(case_id, str) or not case_id for case_id in case_ids) or len(set(case_ids)) != len(case_ids):
        raise ValueError("EX-42 E1 D44 judge case contract invalid")
    current_cells = score.get("d44_cells", {})
    previous_cells = previous.get("d44_cells", {}) if previous is not None else {}
    if not isinstance(current_cells, dict) or not isinstance(previous_cells, dict):
        raise ValueError("EX-42 E1 D44 cells must be objects")
    if set(current_cells) - set(case_ids) or set(previous_cells) - set(case_ids):
        raise ValueError("EX-42 E1 D44 cell outside the approved case list")
    cases = {}
    for case_id in case_ids:
        cases[case_id] = {"current": _landing_window(current_cells.get(case_id), plan, case_id),
                          "previous": (_landing_window(previous_cells.get(case_id), plan, case_id)
                                       if previous is not None else {"judgement": "HOLD", "reason": "직전 창 없음"})}
    if not case_ids:
        current_landing = {"judgement": "HOLD", "reason": "D44 판정 칸 계약 없음"}
        previous_landing = {"judgement": "HOLD", "reason": "D44 판정 칸 계약 없음"}
    else:
        def group(which):
            verdicts = [cases[case_id][which]["judgement"] for case_id in case_ids]
            return {"judgement": "FAIL" if "FAIL" in verdicts else "HOLD" if "HOLD" in verdicts else "PASS"}
        current_landing, previous_landing = group("current"), group("previous")
    maintenance = {"current": current["judgement"],
                   "previous": earlier["judgement"] if earlier else "HOLD"}
    all_verdicts = [*maintenance.values(), current_landing["judgement"], previous_landing["judgement"]]
    overall = "FAIL" if "FAIL" in all_verdicts else "HOLD" if "HOLD" in all_verdicts else "PASS"
    result = dict(current)
    result["stage_id"] = "E1"
    result["maintenance_judgement"] = current["judgement"]
    result["judgement"] = overall
    result["reason"] = "E1 exit: maintenance floor and D44 landing in two windows"
    result["e1_exit"] = {"windows_required": windows, "maintenance": maintenance,
                         "d44": {"required_cases": case_ids, "cases": cases,
                                 "current": current_landing, "previous": previous_landing},
                         "judgement": overall}
    return result


def previous_e1_score(checkpoint: Path, evaluation: Path, interval: int,
                      score_config_sha256: str) -> dict | None:
    """Read only the immediate prior E1 P1 result in this run and source config."""
    match = re.fullmatch(r"model_(\d+)\.pt", checkpoint.name)
    if match is None or interval <= 0:
        raise ValueError("EX-42 E1 window checkpoint or interval invalid")
    previous_iteration = int(match.group(1)) - interval
    if previous_iteration <= 0:
        return None
    path = evaluation.parent / f"m{previous_iteration}" / "ex42_score.json"
    if not path.is_file():
        return None
    receipt_path = path.with_name("p1_score.json")
    if not receipt_path.is_file():
        return None
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    prior = json.loads(path.read_text(encoding="utf-8-sig"))
    expected_checkpoint = checkpoint.parent / f"model_{previous_iteration}.pt"
    if (receipt.get("state") != "complete" or receipt.get("stage_id") != "E1" or
            receipt.get("checkpoint_iteration") != previous_iteration or
            receipt.get("measurement_sha256") != hashlib.sha256(path.read_bytes()).hexdigest() or
            receipt.get("checkpoint_sha256") != prior.get("checkpoint_sha256") or
            prior.get("stage_id") != "E1" or prior.get("checkpoint") != str(expected_checkpoint) or
            prior.get("score_config_sha256") != score_config_sha256 or
            not isinstance(prior.get("checkpoint_sha256"), str) or
            re.fullmatch(r"[0-9a-f]{64}", prior["checkpoint_sha256"]) is None or
            not expected_checkpoint.is_file() or
            hashlib.sha256(expected_checkpoint.read_bytes()).hexdigest() != prior["checkpoint_sha256"]):
        raise ValueError("EX-42 E1 prior window identity differs")
    return prior
