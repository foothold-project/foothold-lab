"""E1 exit uses the pinned maintenance floor and two D44 windows."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from foothold_s2.ex42_e1_judge import judge_e1, previous_e1_score
from foothold_s2.ex42_score import ROOT, config, digest, measure
from foothold_s2.ex42_eval_once import p1_score_from_measure


SAVED_E0 = Path("/home/jay/mai/tmp/scripter/ex42-e0-rejudge-m250-v3/ex42_score.json")


def _inputs():
    cfg, _ = config()
    from foothold_s2.ex42_e0_judge import load_baseline

    baseline = load_baseline(ROOT, cfg, digest)
    baseline["_sha256"] = cfg["baseline"]["sha256"]
    plan = yaml.safe_load((ROOT / cfg["maintenance_source"]).read_text(encoding="utf-8-sig"))
    measured = plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
    score = json.loads(SAVED_E0.read_text(encoding="utf-8"))
    return score, baseline, measured, plan


def _landing(plan, tmp_path, *, success=None, survival=None):
    promotion = plan["evaluation"]["promotion"]
    value = {"case_id": plan["evaluation"]["paper_cells"]["stairs_landing"]["id"],
            "envs": promotion["window_episodes"],
            "success_count": promotion["success_min"] if success is None else success,
            "survival_count": promotion["survival_min"] if survival is None else survival}
    path = tmp_path / f"landing_{value['success_count']}_{value['survival_count']}.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return {**value, "raw_file": str(path), "raw_sha256": digest(path)}


def test_saved_e0_m250_as_e1_is_hold_for_missing_d44_column():
    score, baseline, measured, plan = _inputs()
    result = judge_e1(score, baseline, measured, plan, previous=None)
    assert result["maintenance_judgement"] == "PASS"
    assert result["judgement"] == "HOLD"
    assert result["e1_exit"]["d44"]["current"]["reason"] == "평가 열 없음"
    assert result["e1_exit"]["d44"]["previous"]["reason"] == "직전 창 없음"
    assert result["e1_exit"]["windows_required"] == plan["evaluation"]["promotion"]["windows"]


def test_e1_two_windows_require_both_thresholds_and_maintenance(tmp_path):
    score, baseline, measured, plan = _inputs()
    score["d44_landing"] = _landing(plan, tmp_path)
    previous = copy.deepcopy(score)
    passed = judge_e1(score, baseline, measured, plan, previous=previous)
    assert passed["judgement"] == "PASS"
    assert passed["e1_exit"]["d44"]["current"]["judgement"] == "PASS"
    assert passed["e1_exit"]["d44"]["previous"]["judgement"] == "PASS"
    previous["d44_landing"] = _landing(plan, tmp_path, success=plan["evaluation"]["promotion"]["success_min"] - 1)
    failed = judge_e1(score, baseline, measured, plan, previous=previous)
    assert failed["judgement"] == "FAIL"
    score["d44_landing"] = _landing(plan, tmp_path, survival=plan["evaluation"]["promotion"]["survival_min"] - 1)
    assert judge_e1(score, baseline, measured, plan, previous=previous)["judgement"] == "FAIL"


def test_e1_d44_missing_and_survival_floor_are_visible_with_passing_prior(tmp_path):
    score, baseline, measured, plan = _inputs()
    previous = copy.deepcopy(score)
    previous["d44_landing"] = _landing(plan, tmp_path)
    missing = judge_e1(score, baseline, measured, plan, previous=previous)
    assert missing["maintenance_judgement"] == "PASS"
    assert missing["e1_exit"]["d44"]["previous"]["judgement"] == "PASS"
    assert missing["e1_exit"]["d44"]["current"] == {"judgement": "HOLD", "reason": "평가 열 없음"}
    assert missing["judgement"] == "HOLD"

    score["d44_landing"] = _landing(
        plan, tmp_path, survival=plan["evaluation"]["promotion"]["survival_min"] - 1)
    below = judge_e1(score, baseline, measured, plan, previous=previous)
    assert below["e1_exit"]["d44"]["current"]["judgement"] == "FAIL"
    assert below["judgement"] == "FAIL"


def test_e1_thresholds_are_read_from_plan_and_missing_prior_is_hold(tmp_path):
    score, baseline, measured, plan = _inputs()
    score["d44_landing"] = _landing(plan, tmp_path)
    assert judge_e1(score, baseline, measured, plan, previous=None)["judgement"] == "HOLD"
    changed = copy.deepcopy(plan)
    changed["evaluation"]["promotion"]["success_min"] -= 1
    changed["evaluation"]["promotion"]["survival_min"] -= 1
    current = copy.deepcopy(score)
    current["d44_landing"] = _landing(
        plan, tmp_path, success=plan["evaluation"]["promotion"]["success_min"] - 1,
        survival=plan["evaluation"]["promotion"]["survival_min"] - 1)
    assert judge_e1(current, baseline, measured, changed, previous=current)["judgement"] == "PASS"


def test_known_maintenance_failure_is_not_hidden_by_missing_d44():
    score, baseline, measured, plan = _inputs()
    score["map64"]["eval_gt"]["fwd0.5"]["alive_at_end"] = 0
    result = judge_e1(score, baseline, measured, plan, previous=None)
    assert result["maintenance_judgement"] == "FAIL"
    assert result["e1_exit"]["d44"]["current"]["reason"] == "평가 열 없음"
    assert result["judgement"] == "FAIL"


def test_e1_rejects_bad_landing_evidence(tmp_path):
    score, baseline, measured, plan = _inputs()
    score["d44_landing"] = _landing(plan, tmp_path)
    for update in ({"envs": 63}, {"success_count": 65}, {"raw_sha256": ""},
                   {"case_id": "another_case"}):
        bad = copy.deepcopy(score)
        bad["d44_landing"].update(update)
        with pytest.raises(ValueError, match="D44"):
            judge_e1(bad, baseline, measured, plan, previous=score)
    Path(score["d44_landing"]["raw_file"]).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="D44"):
        judge_e1(score, baseline, measured, plan, previous=score)


def test_e1_rejects_changed_raw_bytes_with_same_counts(tmp_path):
    score, baseline, measured, plan = _inputs()
    score["d44_landing"] = _landing(plan, tmp_path)
    source = Path(score["d44_landing"]["raw_file"])
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="D44 landing raw evidence differs"):
        judge_e1(score, baseline, measured, plan, previous=score)


def test_real_m250_measure_as_e1_keeps_maintenance_pass_and_d44_hold():
    if not SAVED_E0.is_file():
        pytest.skip("local m250 source is unavailable")
    saved = json.loads(SAVED_E0.read_text(encoding="utf-8"))
    original = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218/eval/scores/m250")
    if not original.is_dir():
        pytest.skip("local m250 raw evaluation is unavailable")
    score = measure(Path(saved["checkpoint"]), original, stage_id="E1")
    assert score["maintenance_judgement"] == "PASS"
    assert score["judgement"] == "HOLD"
    assert score["e1_exit"]["d44"]["current"]["reason"] == "평가 열 없음"


def test_p1_bridge_accepts_e1_two_window_evidence(tmp_path):
    score, baseline, measured, plan = _inputs()
    score["d44_landing"] = _landing(plan, tmp_path)
    judged = judge_e1(score, baseline, measured, plan, previous=copy.deepcopy(score))
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"known checkpoint")
    judged["checkpoint_sha256"] = digest(checkpoint)
    output = tmp_path / "m500"
    output.mkdir()
    (output / "ex42_score.json").write_text(json.dumps(judged), encoding="utf-8")
    result = p1_score_from_measure(judged, checkpoint=checkpoint, iteration=500,
                                   plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
                                   approvals_path=ROOT / "foothold_s2/curriculum/ex42-approvals.yaml",
                                   stage_id="E1", output=output)
    assert result["judgment"] == "PASS" and result["stage_id"] == "E1"
    assert result["e1_exit"]["d44"]["current"]["success_count"] == plan["evaluation"]["promotion"]["success_min"]


def test_p1_bridge_rejects_inconsistent_e1_aggregate(tmp_path):
    score, baseline, measured, plan = _inputs()
    score["d44_landing"] = _landing(plan, tmp_path)
    judged = judge_e1(score, baseline, measured, plan, previous=copy.deepcopy(score))
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"known checkpoint")
    judged["checkpoint_sha256"] = digest(checkpoint)
    judged["e1_exit"]["d44"]["current"]["judgement"] = "FAIL"
    output = tmp_path / "m500"
    output.mkdir()
    (output / "ex42_score.json").write_text(json.dumps(judged), encoding="utf-8")
    with pytest.raises(ValueError, match="E1 two-window exit evidence differs"):
        p1_score_from_measure(judged, checkpoint=checkpoint, iteration=500,
                              plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
                              approvals_path=ROOT / "foothold_s2/curriculum/ex42-approvals.yaml",
                              stage_id="E1", output=output)


def test_p1_bridge_records_known_e1_failure_even_with_missing_d44(tmp_path):
    score, baseline, measured, plan = _inputs()
    score["map64"]["eval_gt"]["fwd0.5"]["alive_at_end"] = 0
    judged = judge_e1(score, baseline, measured, plan, previous=None)
    checkpoint = tmp_path / "model_250.pt"
    checkpoint.write_bytes(b"known checkpoint")
    judged["checkpoint_sha256"] = digest(checkpoint)
    output = tmp_path / "m250"
    output.mkdir()
    (output / "ex42_score.json").write_text(json.dumps(judged), encoding="utf-8")
    result = p1_score_from_measure(judged, checkpoint=checkpoint, iteration=250,
                                   plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
                                   approvals_path=ROOT / "foothold_s2/curriculum/ex42-approvals.yaml",
                                   stage_id="E1", output=output)
    assert result["judgment"] == "FAIL"
    assert result["e1_exit"]["d44"]["current"]["reason"] == "평가 열 없음"


def test_prior_window_requires_published_p1_and_checkpoint_bytes(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"new")
    prior_checkpoint = tmp_path / "model_250.pt"
    prior_checkpoint.write_bytes(b"prior")
    folder = tmp_path / "eval" / "scores"
    prior_dir = folder / "m250"
    prior_dir.mkdir(parents=True)
    score = {"stage_id": "E1", "checkpoint": str(prior_checkpoint),
             "checkpoint_sha256": digest(prior_checkpoint), "score_config_sha256": "b" * 64}
    score_path = prior_dir / "ex42_score.json"
    score_path.write_text(json.dumps(score), encoding="utf-8")
    assert previous_e1_score(checkpoint, folder / "m500", 250, "b" * 64) is None
    (prior_dir / "p1_score.json").write_text(json.dumps({"state": "complete", "stage_id": "E1", "checkpoint_iteration": 250,
        "checkpoint_sha256": digest(prior_checkpoint), "measurement_sha256": digest(score_path)}), encoding="utf-8")
    assert previous_e1_score(checkpoint, folder / "m500", 250, "b" * 64)["stage_id"] == "E1"
    prior_checkpoint.write_bytes(b"changed")
    with pytest.raises(ValueError, match="prior window"):
        previous_e1_score(checkpoint, folder / "m500", 250, "b" * 64)


def test_prior_window_uses_iteration_even_when_current_finishes_first(tmp_path):
    checkpoint = tmp_path / "model_500.pt"
    checkpoint.write_bytes(b"current completed first")
    score_dir = tmp_path / "eval" / "scores"
    current_dir = score_dir / "m500"
    current_dir.mkdir(parents=True)
    (current_dir / "p1_score.json").write_text('{"state":"complete"}', encoding="utf-8")
    assert previous_e1_score(checkpoint, current_dir, 250, "b" * 64) is None

    prior_checkpoint = tmp_path / "model_250.pt"
    prior_checkpoint.write_bytes(b"prior completed later")
    prior_dir = score_dir / "m250"
    prior_dir.mkdir()
    score = {"stage_id": "E1", "checkpoint": str(prior_checkpoint),
             "checkpoint_sha256": digest(prior_checkpoint), "score_config_sha256": "b" * 64}
    score_path = prior_dir / "ex42_score.json"
    score_path.write_text(json.dumps(score), encoding="utf-8")
    (prior_dir / "p1_score.json").write_text(json.dumps({"state": "complete", "stage_id": "E1",
        "checkpoint_iteration": 250, "checkpoint_sha256": digest(prior_checkpoint),
        "measurement_sha256": digest(score_path)}), encoding="utf-8")
    assert previous_e1_score(checkpoint, current_dir, 250, "b" * 64) == score


def test_the_two_reviewed_adapters_are_registered_and_a_stage_without_one_judges_nothing():
    from foothold_s2 import ex42_stage_judges as sj
    doc = {"stages": [{"id": "E0"}, {"id": "E1"}, {"id": "E1F"}, {"id": "E2", "exit_judge": "nope"},
                      {"id": "E3", "exit_judge": "map39_e0"}]}
    assert sj.adapter_for(doc, "E0").name == "map39_e0" and sj.adapter_for(doc, "E1").name == "map39_e1_two_window"
    assert sj.adapter_for(doc, "E1F") is None
    assert sj.adapter_for(doc, "E3") is sj.ADAPTERS["map39_e0"]            # the plan can name an adapter for any stage
    with pytest.raises(ValueError, match="unknown judge adapter"):
        sj.adapter_for(doc, "E2")
    with pytest.raises(ValueError, match="not in the plan"):
        sj.adapter_for(doc, "Z9")
    assert sj.aggregate(["PASS", "HOLD"]) == "HOLD" and sj.aggregate(["PASS", "FAIL", "HOLD"]) == "FAIL"
    assert sj.aggregate([]) == "HOLD" and sj.aggregate(["PASS"]) == "PASS"
