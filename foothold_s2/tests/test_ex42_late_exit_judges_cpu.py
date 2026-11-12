"""E6a / E6b / M exit judges and the M return decision. Synthetic raw evidence in the stated formats; no Kit, no GPU."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2 import ex42_late_exit_judges as late
from foothold_s2 import ex42_e0_judge, ex42_stage_judges

SHA = "a" * 64


def _posture(folder, index, error, axis=None, sha=SHA):
    path = Path(folder) / "posture_cells"
    path.mkdir(parents=True, exist_ok=True)
    (path / "posture_cells.json").write_text(json.dumps({
        "format": late.POSTURE_FORMAT, "checkpoint_sha256": sha, "boundary_index": index,
        "axis": axis or late.E6A_AXES[index], "tracking_error_median": error}))


def _mapoff(folder, gaps, sha=SHA, envs=64):
    path = Path(folder) / "map_off_cells"
    path.mkdir(parents=True, exist_ok=True)
    levels = {name: {"eval_gt_alive": 60, "map_off_alive": 60 - gap} for name, gap in zip(late.MAPOFF_LEVELS, gaps)}
    (path / "map_off_cells.json").write_text(json.dumps({
        "format": late.MAPOFF_FORMAT, "checkpoint_sha256": sha, "envs": envs, "levels": levels}))


@pytest.mark.parametrize("index,error,expected", [
    (0, 0.02, "PASS"), (0, 0.0201, "FAIL"), (1, 0.019, "PASS"), (1, 0.03, "FAIL"),
    (2, 0.05, "PASS"), (2, 0.0501, "FAIL"), (2, 0.02, "PASS")])
def test_posture_limits_are_per_axis_and_inclusive(tmp_path, index, error, expected):
    _posture(tmp_path, index, error)
    row = late.posture_window(json.loads((tmp_path / "posture_cells/posture_cells.json").read_text()), index)
    assert row["judgement"] == expected and row["limit"] == late.POSTURE_LIMITS[late.E6A_AXES[index]]


def test_posture_axis_or_boundary_outside_the_fixed_order_is_refused(tmp_path):
    _posture(tmp_path, 2, 0.01, axis="posture_height")             # boundary 3 must be roll
    with pytest.raises(ValueError):
        late.posture_window(json.loads((tmp_path / "posture_cells/posture_cells.json").read_text()), 2)


def test_posture_nan_error_is_refused():
    with pytest.raises(ValueError):
        late.posture_window({"boundary_index": 0, "axis": "posture_height", "tracking_error_median": float("nan")}, 0)


@pytest.mark.parametrize("gaps,expected", [((6, 6, 6), "PASS"), ((0, 0, 7), "FAIL"), ((7, 0, 0), "FAIL"), ((-3, 2, 5), "PASS")])
def test_mapoff_needs_all_three_levels_within_six_envs(tmp_path, gaps, expected):
    _mapoff(tmp_path, gaps)
    row = json.loads((tmp_path / "map_off_cells/map_off_cells.json").read_text())
    assert late.mapoff_window(row)["judgement"] == expected


def test_mapoff_missing_level_or_wrong_env_count_is_refused(tmp_path):
    _mapoff(tmp_path, (0, 0, 0))
    row = json.loads((tmp_path / "map_off_cells/map_off_cells.json").read_text())
    del row["levels"]["L9"]
    with pytest.raises(ValueError):
        late.mapoff_window(row)
    row["envs"] = 32
    with pytest.raises(ValueError):
        late.mapoff_window(row)
    assert late.mapoff_window(None)["judgement"] == "HOLD"


def _ctx(tmp_path, stage):
    run = tmp_path / "run"
    cur = run / "m500"
    cur.mkdir(parents=True)
    return SimpleNamespace(stage_id=stage, checkpoint=run / "model_500.pt", evaluation=cur, checkpoint_sha=SHA,
                           root=tmp_path, cfg={"baseline": {"sha256": "b" * 64}}, digest=None,
                           plan={"evaluation": {"interval_updates": 250},
                                 "assumptions_pending_lead": {"q4_two_window_range": {"value": {"measured": {}}}}})


@pytest.fixture
def stand_in(monkeypatch):
    state = {"maintenance": "PASS", "prior_maintenance": "PASS", "prior": {"checkpoint_sha256": SHA, "is_prior": True}}
    monkeypatch.setattr(ex42_e0_judge, "load_baseline", lambda *a, **k: {})
    monkeypatch.setattr(ex42_e0_judge, "judge", lambda score, *a: {
        **score, "judgement": state["prior_maintenance"] if score.get("is_prior") else state["maintenance"]})
    monkeypatch.setattr(late, "previous_window", lambda ctx: state["prior"])
    return state


def _run(ctx, judge):
    return judge.judge(ctx, {"checkpoint_sha256": SHA})["stage_exit"]


def test_e6a_passes_only_with_both_windows_and_the_maintenance_table(tmp_path, stand_in):
    ctx = _ctx(tmp_path, "E6a")
    _posture(ctx.evaluation, 1, 0.01)
    _posture(ctx.evaluation.parent / "m250", 0, 0.015)
    judge = late.E6aPostureTwoWindowJudge()
    assert _run(ctx, judge)["judgement"] == "PASS"
    stand_in["maintenance"] = "HOLD"
    assert _run(ctx, judge)["judgement"] == "HOLD"                    # maintenance never bypassed
    stand_in["maintenance"], stand_in["prior_maintenance"] = "PASS", "HOLD"
    assert _run(ctx, judge)["judgement"] == "HOLD"                    # nor the previous window's table
    stand_in["prior_maintenance"] = "PASS"
    _posture(ctx.evaluation.parent / "m250", 0, 0.5)
    assert _run(ctx, judge)["judgement"] == "FAIL"                    # a failed prior window fails the exit


def test_a_missing_prior_window_or_evidence_is_hold_never_pass(tmp_path, stand_in):
    ctx = _ctx(tmp_path, "M")
    _mapoff(ctx.evaluation, (0, 0, 0))
    judge = late.MapOffTwoWindowJudge()
    stand_in["prior"] = None
    assert _run(ctx, judge)["judgement"] == "HOLD"
    stand_in["prior"] = {"checkpoint_sha256": SHA}
    assert _run(ctx, judge)["judgement"] == "HOLD"                    # prior folder has no evidence
    _mapoff(ctx.evaluation.parent / "m250", (1, 1, 1))
    assert _run(ctx, judge)["judgement"] == "PASS"


def test_evidence_of_another_checkpoint_is_not_consumed(tmp_path, stand_in):
    ctx = _ctx(tmp_path, "M")
    _mapoff(ctx.evaluation, (0, 0, 0), sha="c" * 64)
    _mapoff(ctx.evaluation.parent / "m250", (0, 0, 0))
    items = _run(ctx, late.MapOffTwoWindowJudge())["items"]
    assert items["mapoff_current"]["judgement"] == "HOLD" and "identity" in items["mapoff_current"]["reason"]


def test_stage_identity_mismatch_is_refused(tmp_path, stand_in):
    with pytest.raises(ValueError):
        late.MapOffTwoWindowJudge().judge(_ctx(tmp_path, "E6a"), {})


def test_e6b_has_no_pass_without_the_common_kind_consumer(tmp_path, stand_in):
    assert _run(_ctx(tmp_path, "E6b"), late.E6bKindTwoWindowJudge())["judgement"] == "HOLD"


def test_the_three_adapters_are_registered_under_the_plan_names():
    for name in ("posture_two_window_e6a", "kind_two_window_e6b", "mapoff_two_window_m"):
        assert ex42_stage_judges.ADAPTERS[name].name == name


@pytest.mark.parametrize("updates,judgement,ext,action", [
    (250, "PASS", False, "return"), (250, "HOLD", False, "continue"), (500, "HOLD", False, "extend"),
    (500, "HOLD", True, "continue"), (1000, "HOLD", True, "notify_and_return"), (1000, "FAIL", False, "notify_and_return"),
    (1000, "PASS", True, "return")])
def test_m_return_decision(updates, judgement, ext, action):
    row = late.m_return_decision(source_stage="E4", m_updates=updates, m_judgement=judgement, extension_used=ext)
    assert row["action"] == action and row["return_to"] == "E4" and row["p_map_off"] == 0.3
    assert row["counts_toward_source_maximum"] is False and row["counts_toward_ex42_budget"] is True


@pytest.mark.parametrize("kwargs", [dict(source_stage="", m_updates=0, m_judgement="PASS", extension_used=False),
                                    dict(source_stage="E3", m_updates=-1, m_judgement="PASS", extension_used=False),
                                    dict(source_stage="E3", m_updates=1, m_judgement="WIN", extension_used=False)])
def test_m_return_refuses_bad_inputs(kwargs):
    with pytest.raises(ValueError):
        late.m_return_decision(**kwargs)


def _exit_score(stage, adapter, judgements, verdict):
    items = {f"x{i}": {"role": "judge", "judgement": j} for i, j in enumerate(judgements)}
    items["maintenance_current"] = {"role": "judge", "judgement": "PASS"}
    return {"stage_id": stage, "stage_exit": {"adapter": adapter, "windows": 2, "judgement": verdict, "items": items}}


def test_verify_refuses_a_pass_claimed_over_a_hold_item():
    judge = late.MapOffTwoWindowJudge()
    forged = _exit_score("M", judge.name, ["PASS", "HOLD"], "PASS")
    with pytest.raises(ValueError, match="aggregate differs"):
        judge.verify(forged, "PASS", "PASS", plan={})


def test_verify_refuses_another_stages_score_or_adapter():
    judge = late.E6aPostureTwoWindowJudge()
    with pytest.raises(ValueError):
        judge.verify(_exit_score("M", judge.name, ["PASS"], "PASS"), "PASS", "PASS", plan={})
    with pytest.raises(ValueError, match="aggregate differs"):
        judge.verify(_exit_score("E6a", "kind_two_window_e3", ["PASS"], "PASS"), "PASS", "PASS", plan={})
