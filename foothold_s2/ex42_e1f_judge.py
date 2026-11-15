"""E1F flag exit. The stage plan supplies cells, thresholds and pinned repeats.

The Kit child measures flag cells. This module only reads SHA-bound evidence and
combines it with the already reviewed EX-42 maintenance comparison.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from foothold_s2.eval.ex42_flag_cells import contract, read_evidence, summarize_repeats
from foothold_s2.ex42_e0_judge import judge as judge_maintenance


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _calibration(plan: dict) -> dict:
    cells = contract(plan)
    pin = cells.get("calibration")
    if not isinstance(pin, dict) or not pin.get("path") or not pin.get("sha256"):
        return {"judgement": "HOLD", "reason": "깃발 칸 다섯 반복 폭 미등록"}
    path = Path(pin["path"])
    if re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]) is None or not path.is_file() or _sha(path) != pin["sha256"]:
        raise ValueError("E1F flag calibration path or SHA differs")
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    wanted = set(cells["judge_cases"])
    widths = row.get("repeat_width", {})
    if (row.get("format") != "foothold-ex42-flag-calibration/1"
            or row.get("seeds") != cells["repeat_seeds"]
            or len(row.get("repeat_receipts", [])) != 5
            or set(widths) != wanted
            or any(set(widths[name]) != {"success_count", "survival_count"}
                   or any(type(v) is not int or v < 0 or v > 64 for v in widths[name].values())
                   for name in wanted)):
        raise ValueError("E1F flag five-repeat calibration coverage differs")
    parent = next((stage.get("parent") for stage in plan.get("stages", []) if stage.get("id") == "E1F"), None)
    if not isinstance(parent, dict) or row.get("checkpoint_sha256") != parent.get("sha256"):
        raise ValueError("E1F flag calibration parent checkpoint differs")
    repeat_roots = []
    for sample, seed in zip(row["repeat_receipts"], cells["repeat_seeds"]):
        if not isinstance(sample, dict) or sample.get("seed") != seed or set(sample.get("receipts", {})) != {"flag_one", "flag_four"}:
            raise ValueError("E1F flag calibration repeat identity differs")
        names = sample["receipts"]
        roots = []
        for count in ("flag_one", "flag_four"):
            item = names[count]
            if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                    or Path(item["path"]).name != "flag_cells.json"
                    or Path(item["path"]).parent.name != count
                    or not Path(item["path"]).is_file()
                    or _sha(Path(item["path"])) != item.get("sha256")):
                raise ValueError("E1F flag calibration repeat receipt SHA differs")
            roots.append(Path(item["path"]).parent.parent)
        if roots[0] != roots[1]:
            raise ValueError("E1F flag calibration count roots differ")
        repeat_roots.append(roots[0])
    source_plan_sha = row.get("source_plan_sha256")
    if not isinstance(source_plan_sha, str) or re.fullmatch(r"[0-9a-f]{64}", source_plan_sha) is None:
        raise ValueError("E1F flag calibration source plan SHA missing")
    recomputed = summarize_repeats(repeat_roots, plan=plan, plan_sha256=source_plan_sha,
                                   checkpoint_sha256=row["checkpoint_sha256"])
    if recomputed != row:
        raise ValueError("E1F flag calibration differs from five raw repeats")
    return {"judgement": "PASS", "evidence": {"path": str(path), "sha256": pin["sha256"]},
            "repeat_width": widths}


def _flag_window(value: dict | None, plan: dict, case_id: str) -> dict:
    if value is None:
        return {"judgement": "HOLD", "reason": "깃발 평가 열 없음", "check_id": case_id}
    cells = contract(plan)
    spec = cells["case_specs"][case_id]
    n = plan["evaluation"]["promotion"]["window_episodes"]
    if (not isinstance(value, dict) or value.get("case_id") != case_id
            or type(value.get("envs")) is not int or value["envs"] != n
            or any(type(value.get(key)) is not int or not 0 <= value[key] <= n
                   for key in ("valid_count", "success_count", "survival_count"))
            or value["success_count"] > value["valid_count"]
            or value["survival_count"] > value["valid_count"]
            or not isinstance(value.get("raw_file"), str)
            or not isinstance(value.get("raw_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", value["raw_sha256"]) is None):
        raise ValueError("E1F flag cell count or identity invalid")
    path = Path(value["raw_file"])
    if not path.is_file() or _sha(path) != value["raw_sha256"]:
        raise ValueError("E1F flag raw SHA differs")
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if (any(raw.get(key) != value[key] for key in ("case_id", "envs", "valid_count",
                                                  "success_count", "survival_count"))
            or any(raw.get(key) != expected for key, expected in spec.items())):
        raise ValueError("E1F flag raw counts or case identity differ")
    trace_file, trace_sha = raw.get("trace_file"), raw.get("trace_sha256")
    if (not isinstance(trace_file, str) or not isinstance(trace_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", trace_sha) is None
            or not Path(trace_file).is_file() or _sha(Path(trace_file)) != trace_sha):
        raise ValueError("E1F flag trace SHA differs")
    valid_min = cells["valid_min"]
    if type(valid_min) is not int or not 0 < valid_min <= n:
        raise ValueError("E1F flag valid denominator floor invalid")
    valid = value["valid_count"]
    promotion = plan["evaluation"]["promotion"]
    success_min = math.ceil(promotion["success_min"] * valid / n)
    survival_min = math.ceil(promotion["survival_min"] * valid / n)
    state = ("HOLD" if valid < valid_min else "PASS" if
             value["success_count"] >= success_min and value["survival_count"] >= survival_min else "FAIL")
    return {"judgement": state, "check_id": case_id, "role": "judge",
            "valid_count": valid, "success_count": value["success_count"],
            "survival_count": value["survival_count"], "success_min": success_min,
            "survival_min": survival_min,
            "evidence": {"path": str(path), "sha256": value["raw_sha256"]},
            **({"reason": "깃발 유효 env 하한 미달"} if state == "HOLD" else {})}


def _aggregate(states) -> str:
    states = list(states)
    return "FAIL" if "FAIL" in states else "HOLD" if not states or "HOLD" in states else "PASS"


def judge_e1f(score: dict, baseline: dict, measured: dict, plan: dict,
              *, previous: dict | None) -> dict:
    """Two sequential 64-env windows, four judge cells, pinned five-repeat width."""
    cells = contract(plan)
    if plan["evaluation"]["promotion"]["windows"] != 2 or plan["evaluation"]["promotion"]["window_episodes"] != 64:
        raise ValueError("E1F flag two-window promotion contract differs")
    current = judge_maintenance(score, baseline, measured)
    prior = judge_maintenance(previous, baseline, measured) if previous is not None else None
    current_cells = score.get("flag_cells", {})
    previous_cells = previous.get("flag_cells", {}) if previous is not None else {}
    if not isinstance(current_cells, dict) or not isinstance(previous_cells, dict) or set(current_cells) - set(cells["judge_cases"]) or set(previous_cells) - set(cells["judge_cases"]):
        raise ValueError("E1F flag score has a cell outside the approved judge list")
    cases = {case_id: {
        "current": _flag_window(current_cells.get(case_id), plan, case_id),
        "previous": (_flag_window(previous_cells.get(case_id), plan, case_id) if previous is not None
                     else {"judgement": "HOLD", "reason": "직전 창 없음", "check_id": case_id}),
    } for case_id in cells["judge_cases"]}
    calibration = _calibration(plan)
    maintenance = {"current": current["judgement"],
                   "previous": prior["judgement"] if prior else "HOLD"}
    items = {"maintenance_current": {"role": "judge", "judgement": maintenance["current"]},
             "maintenance_previous": {"role": "judge", "judgement": maintenance["previous"]},
             "flag_calibration": {"role": "judge", **calibration}}
    for case_id, windows in cases.items():
        for which, value in windows.items():
            items[f"{case_id}_{which}"] = {"role": "judge", **value}
    overall = _aggregate(item["judgement"] for item in items.values())
    result = dict(current)
    result.update(stage_id="E1F", judgement=overall,
                  reason="E1F flag two-window maintenance, flag cells and pinned five-repeat width",
                  stage_exit={"adapter": "flag_two_window", "judgement": overall, "windows": 2,
                              "items": items})
    return result


class FlagTwoWindowJudge:
    """Structural StageJudge contract from #672, without importing its pending branch."""
    name = "flag_two_window"

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import load_baseline
        from foothold_s2.ex42_stage_judges import previous_window

        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        folder = ctx.evaluation / "flag_cells"
        marker = folder / "child_failures.json"
        failures = {}
        if marker.is_file():
            state = json.loads(marker.read_text(encoding="utf-8-sig"))
            failures = state.get("failures")
            if (state.get("format") != "foothold-ex42-e1f-child-failures/1" or
                    state.get("checkpoint_sha256") != ctx.checkpoint_sha or
                    not isinstance(failures, dict) or not failures or
                    set(failures) - {"flag_one", "flag_four"} or
                    any(not isinstance(reason, str) or not reason for reason in failures.values())):
                raise ValueError("E1F flag child failure marker invalid")
            score["flag_child_failures"] = {"path": str(marker), "sha256": _sha(marker),
                                             "failures": failures}
        for count in ("flag_one", "flag_four"):
            if count in failures:
                continue
            subdir = folder / count
            if (subdir / "flag_cells.json").is_file():
                score.setdefault("flag_cells", {}).update(read_evidence(
                    subdir, plan=ctx.plan, plan_sha256=ctx.digest(ctx.plan_path),
                    checkpoint_sha256=ctx.checkpoint_sha,
                    seed=ctx.seed, count=count))
        return judge_e1f(score, baseline, measured, ctx.plan, previous=previous_window(ctx))

    def verify(self, score, judgment, expected, plan=None):
        exit_row = score.get("stage_exit") or {}
        items = exit_row.get("items") or {}
        if plan is None:
            raise ValueError("EX-42 P1 E1F plan is required")
        cells = contract(plan)
        expected_items = {"maintenance_current", "maintenance_previous", "flag_calibration"} | {
            f"{case}_{window}" for case in cells["judge_cases"]
            for window in ("current", "previous")}
        if (score.get("stage_id") != "E1F" or exit_row.get("adapter") != self.name
                or exit_row.get("windows") != 2 or exit_row.get("judgement") != judgment
                or items.get("maintenance_current", {}).get("judgement") != expected
                or set(items) != expected_items
                or any(item.get("role") != "judge" for item in items.values())
                or any(item.get("judgement") not in ("PASS", "HOLD", "FAIL") for item in items.values())
                or _aggregate(item["judgement"] for item in items.values()) != judgment):
            raise ValueError("EX-42 P1 E1F stage exit evidence differs")
        for case_id in cells["judge_cases"]:
            for which in ("current", "previous"):
                item = items[f"{case_id}_{which}"]
                if item["judgement"] == "HOLD" and item.get("reason") in ("깃발 평가 열 없음", "직전 창 없음"):
                    continue
                evidence = item.get("evidence") or {}
                checked = _flag_window({"case_id": case_id, "envs": 64,
                                        "valid_count": item.get("valid_count"),
                                        "success_count": item.get("success_count"),
                                        "survival_count": item.get("survival_count"),
                                        "raw_file": evidence.get("path"),
                                        "raw_sha256": evidence.get("sha256")}, plan, case_id)
                if checked != item:
                    raise ValueError("EX-42 P1 E1F flag cell verdict differs from raw")
        calibration = _calibration(plan)
        if items["flag_calibration"] != {"role": "judge", **calibration}:
            raise ValueError("EX-42 P1 E1F flag calibration differs")
        for key, item in items.items():
            evidence = item.get("evidence")
            if evidence is None:
                if item["judgement"] == "PASS" and key not in ("maintenance_current", "maintenance_previous"):
                    raise ValueError("EX-42 P1 E1F PASS has no raw evidence")
                continue
            if (not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str)
                    or not isinstance(evidence.get("sha256"), str)
                    or not Path(evidence["path"]).is_file()
                    or _sha(Path(evidence["path"])) != evidence["sha256"]):
                raise ValueError("EX-42 P1 E1F evidence path or SHA differs")
        return {"stage_exit": exit_row}


# #672 imports this module after its own E0/E1 registrations. Keeping the
# registration here makes the stage-specific module own its adapter identity.
try:
    from foothold_s2.ex42_stage_judges import register
except ModuleNotFoundError as exc:
    if exc.name != "foothold_s2.ex42_stage_judges":
        raise
else:
    register(FlagTwoWindowJudge())
