"""D44 required case count comes from the plan, never a compiled constant."""
import copy
import json
from pathlib import Path

from foothold_s2.ex42_e1_judge import judge_e1
from foothold_s2.ex42_score import ROOT, config, digest
from foothold_s2.ex42_e0_judge import load_baseline
import yaml


SOURCE = Path("/home/jay/mai/tmp/scripter/ex42-e0-rejudge-m250-v3/ex42_score.json")
CASES = ("turn_left_eval_gt", "turn_left_eval_pred", "turn_right_eval_gt",
         "turn_right_eval_pred", "stop_restart_eval_gt", "stop_restart_eval_pred")


def _known_score_and_plan(tmp_path):
    cfg, _ = config()
    baseline = load_baseline(ROOT, cfg, digest)
    baseline["_sha256"] = cfg["baseline"]["sha256"]
    plan = yaml.safe_load((ROOT / cfg["maintenance_source"]).read_text(encoding="utf-8-sig"))
    measured = plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
    score = json.loads(SOURCE.read_text(encoding="utf-8"))
    promotion = plan["evaluation"]["promotion"]
    cells = {}
    for case_id in CASES:
        spec = plan["evaluation"]["paper_cells"]["stairs_landing"]["case_specs"][case_id]
        trace = tmp_path / f"{case_id}.npz"
        trace.write_bytes(b"known trace")
        raw = {"case_id": case_id, "envs": promotion["window_episodes"],
               "valid_count": promotion["window_episodes"],
               "success_count": promotion["success_min"],
               "survival_count": promotion["survival_min"], **spec,
               "trace_file": str(trace), "trace_sha256": digest(trace)}
        path = tmp_path / f"{case_id}.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        cells[case_id] = {**raw, "raw_file": str(path), "raw_sha256": digest(path)}
    score["d44_cells"] = cells
    return score, baseline, measured, plan


def test_d44_cells_require_all_planned_cases_in_both_windows(tmp_path):
    score, baseline, measured, plan = _known_score_and_plan(tmp_path)
    previous = copy.deepcopy(score)
    assert judge_e1(score, baseline, measured, plan, previous=previous)["judgement"] == "PASS"

    missing = copy.deepcopy(score)
    del missing["d44_cells"][CASES[-1]]
    held = judge_e1(missing, baseline, measured, plan, previous=previous)
    assert held["judgement"] == "HOLD"
    assert held["e1_exit"]["d44"]["cases"][CASES[-1]]["current"]["reason"] == "평가 열 없음"

    below = copy.deepcopy(score)
    bad = below["d44_cells"][CASES[-1]]
    bad["success_count"] = plan["evaluation"]["promotion"]["success_min"] - 1
    raw = json.loads(Path(bad["raw_file"]).read_text(encoding="utf-8"))
    raw["success_count"] = bad["success_count"]
    path = tmp_path / "fourth_low.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    bad["raw_file"] = str(path)
    bad["raw_sha256"] = digest(path)
    failed = judge_e1(below, baseline, measured, plan, previous=previous)
    assert failed["judgement"] == "FAIL"
    assert failed["e1_exit"]["d44"]["cases"][CASES[-1]]["current"]["judgement"] == "FAIL"


def test_d44_three_case_plan_also_uses_only_its_approved_cases(tmp_path):
    score, baseline, measured, plan = _known_score_and_plan(tmp_path)
    plan["evaluation"]["paper_cells"]["stairs_landing"]["judge_cases"] = list(CASES[:3])
    score["d44_cells"] = {key: score["d44_cells"][key] for key in CASES[:3]}
    assert judge_e1(score, baseline, measured, plan, previous=copy.deepcopy(score))["judgement"] == "PASS"


def test_approach_timeouts_scale_denominator_until_valid_floor(tmp_path):
    score, baseline, measured, plan = _known_score_and_plan(tmp_path)
    previous = copy.deepcopy(score)
    cell = score["d44_cells"][CASES[-1]]
    cell["valid_count"] = cell["envs"] - 1
    cell["success_count"] = min(cell["success_count"], cell["valid_count"])
    raw = json.loads(Path(cell["raw_file"]).read_text(encoding="utf-8"))
    raw.update(valid_count=cell["valid_count"], success_count=cell["success_count"])
    path = tmp_path / "one_timeout.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    cell.update(raw_file=str(path), raw_sha256=digest(path))
    judged = judge_e1(score, baseline, measured, plan, previous=previous)
    assert judged["judgement"] == "PASS"
    assert judged["e1_exit"]["d44"]["cases"][CASES[-1]]["current"]["success_min"] == 52
