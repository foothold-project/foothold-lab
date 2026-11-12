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
    _posture(ctx.evaluation.parent / "m250", 1, 0.015)
    judge = late.E6aPostureTwoWindowJudge()
    assert _run(ctx, judge)["judgement"] == "PASS"
    stand_in["maintenance"] = "HOLD"
    assert _run(ctx, judge)["judgement"] == "HOLD"                    # maintenance never bypassed
    stand_in["maintenance"], stand_in["prior_maintenance"] = "PASS", "HOLD"
    assert _run(ctx, judge)["judgement"] == "HOLD"                    # nor the previous window's table
    stand_in["prior_maintenance"] = "PASS"
    _posture(ctx.evaluation.parent / "m250", 1, 0.5)
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


def test_e6a_absent_posture_file_never_passes(tmp_path, stand_in):
    ctx = _ctx(tmp_path, "E6a")
    _posture(ctx.evaluation.parent / "m250", 1, 0.01)                 # prior fine, current file absent
    items = _run(ctx, late.E6aPostureTwoWindowJudge())
    assert items["judgement"] == "HOLD" and items["items"]["posture_current"]["judgement"] == "HOLD"


def test_e6a_absent_previous_window_never_passes(tmp_path, stand_in):
    ctx = _ctx(tmp_path, "E6a")
    _posture(ctx.evaluation, 1, 0.01)
    judge = late.E6aPostureTwoWindowJudge()
    assert _run(ctx, judge)["judgement"] == "HOLD"                    # prior score exists, its evidence folder is empty
    stand_in["prior"] = None
    items = _run(ctx, judge)                                          # no prior score at all
    assert items["judgement"] == "HOLD" and items["items"]["maintenance_previous"]["judgement"] == "HOLD"
    assert items["items"]["posture_previous"]["judgement"] == "HOLD"           # the stage's own previous window is HOLD too


@pytest.mark.parametrize("now,prior,state", [((0, "posture_height"), (1, "posture_height"), "HOLD"),
                                              ((1, "posture_height"), (2, "posture_roll"), "HOLD"),
                                              ((2, "posture_roll"), (1, "posture_height"), "HOLD"),
                                              ((2, "posture_roll"), (2, "posture_roll"), "PASS"),
                                              ((0, "posture_height"), (0, "posture_height"), "PASS")])
def test_e6a_two_windows_must_be_the_same_boundary_and_axis(tmp_path, stand_in, now, prior, state):
    ctx = _ctx(tmp_path, "E6a")
    _posture(ctx.evaluation, now[0], 0.01, axis=now[1])
    _posture(ctx.evaluation.parent / "m250", prior[0], 0.01, axis=prior[1])
    assert _run(ctx, late.E6aPostureTwoWindowJudge())["judgement"] == state


def test_e6a_boundary_number_fixes_the_axis_and_limit(tmp_path, stand_in):
    ctx = _ctx(tmp_path, "E6a")
    for folder in (ctx.evaluation, ctx.evaluation.parent / "m250"):
        _posture(folder, 2, 0.03)                                      # roll error 0.03 is inside 0.05 but height's 0.02 would fail
    items = _run(ctx, late.E6aPostureTwoWindowJudge())["items"]
    assert items["posture_current"]["limit"] == 0.05 and items["posture_current"]["judgement"] == "PASS"
    for folder in (ctx.evaluation, ctx.evaluation.parent / "m250"):
        _posture(folder, 1, 0.03)
    items = _run(ctx, late.E6aPostureTwoWindowJudge())["items"]
    assert items["posture_current"]["limit"] == 0.02 and items["posture_current"]["judgement"] == "FAIL"
    (ctx.evaluation / "posture_cells" / "posture_cells.json").write_text(json.dumps({
        "format": late.POSTURE_FORMAT, "checkpoint_sha256": SHA, "boundary_index": 3, "axis": "posture_roll",
        "tracking_error_median": 0.0}))
    assert _run(ctx, late.E6aPostureTwoWindowJudge())["judgement"] == "HOLD"     # a fourth boundary does not exist


@pytest.fixture
def replay(tmp_path, monkeypatch, stand_in):
    """A judged M score on disk plus the config / digest / receipt the P1 verify replays from."""
    from foothold_s2 import ex42_score
    ctx = _ctx(tmp_path, "M")
    policy = tmp_path / "policy.yaml"
    policy.write_text("p")
    (ctx.evaluation / "eval_receipt.json").write_text(json.dumps({"evaluation_plan": {"path": str(policy), "sha256": "d" * 64}}))
    monkeypatch.setattr(ex42_score, "config", lambda: ({"baseline": {"sha256": "b" * 64}}, tmp_path / "cfg.json"))
    monkeypatch.setattr(ex42_score, "digest", lambda path: "d" * 64)
    monkeypatch.setattr(ex42_score, "ROOT", tmp_path)
    judge = late.MapOffTwoWindowJudge()
    base = {"checkpoint": str(ctx.checkpoint), "checkpoint_sha256": SHA, "score_config_sha256": "d" * 64,
            "conditions": {"eval_seed": 1}}

    def judged():
        return judge.judge(ctx, dict(base))
    return ctx, judge, judged


def test_verify_replays_the_raw_evidence_and_accepts_an_honest_pass(replay):
    ctx, judge, judged = replay
    _mapoff(ctx.evaluation, (0, 0, 0))
    _mapoff(ctx.evaluation.parent / "m250", (1, 1, 1))
    score = judged()
    assert score["judgement"] == "PASS"
    assert judge.verify(score, "PASS", "PASS", plan=ctx.plan)["stage_exit"] == score["stage_exit"]


def test_verify_recomputes_the_verdict_from_the_raw_evidence(replay):
    ctx, judge, judged = replay
    _mapoff(ctx.evaluation, (0, 0, 0))
    _mapoff(ctx.evaluation.parent / "m250", (1, 1, 1))
    score = judged()
    _mapoff(ctx.evaluation, (0, 0, 9))                                # the raw file changes after the score was written
    with pytest.raises(ValueError, match="replay"):
        judge.verify(score, "PASS", "PASS", plan=ctx.plan)
    (ctx.evaluation / "map_off_cells" / "map_off_cells.json").unlink()   # or disappears
    with pytest.raises(ValueError, match="replay"):
        judge.verify(score, "PASS", "PASS", plan=ctx.plan)


def test_verify_refuses_a_forged_item_even_when_the_aggregate_is_consistent(replay):
    ctx, judge, judged = replay
    _mapoff(ctx.evaluation, (0, 0, 9))
    _mapoff(ctx.evaluation.parent / "m250", (1, 1, 1))
    score = judged()
    assert score["judgement"] == "FAIL"
    score["stage_exit"]["items"]["mapoff_current"] = {"role": "judge", "judgement": "PASS"}
    score["stage_exit"]["judgement"] = score["judgement"] = "PASS"
    with pytest.raises(ValueError, match="replay"):
        judge.verify(score, "PASS", "PASS", plan=ctx.plan)


def test_verify_refuses_when_the_26_cell_aggregate_differs_from_the_maintenance_item(replay):
    ctx, judge, judged = replay
    _mapoff(ctx.evaluation, (0, 0, 0))
    _mapoff(ctx.evaluation.parent / "m250", (1, 1, 1))
    with pytest.raises(ValueError, match="aggregate differs"):
        judge.verify(judged(), "PASS", "HOLD", plan=ctx.plan)
