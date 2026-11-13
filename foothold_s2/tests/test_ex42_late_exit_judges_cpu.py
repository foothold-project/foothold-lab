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


# ---- E6b: the D kinds through the common named-kind reader (real plan, stood-in raw readers) -----------------------
PASS_CELL = {"eval_gt": {"judgement": "PASS"}, "eval_pred": {"judgement": "PASS"}}
FAIL_CELL = {"eval_gt": {"judgement": "FAIL"}, "eval_pred": {"judgement": "PASS"}}
D_CELLS = ("D/crawl/L0", "D/high_ledge/L0")


def _real_plan():
    import yaml
    from foothold_s2.ex42_score import ROOT
    return yaml.safe_load((ROOT / "foothold_s2/curriculum/ex42-prep.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def e6b(tmp_path, monkeypatch, stand_in):
    """Both windows on disk with a pinned mesh; per-window cells / exposure are set through the returned state."""
    import foothold_s2.ex42_e3_judge as e3
    import foothold_s2.ex42_learned_cells_evidence as evidence
    from foothold_s2.eval import ex42_late_stage_kinds as kinds
    ctx = _ctx(tmp_path, "E6b")
    ctx.plan = _real_plan()
    ctx.checkpoint = tmp_path / "run" / "model_500.pt"
    state = {"m500": {"cells": {k: PASS_CELL for k in D_CELLS}, "opened": {"D/high_ledge": 0, "D/crawl": 0}, "mesh": "b" * 64},
             "m250": {"cells": {k: PASS_CELL for k in D_CELLS}, "opened": {"D/high_ledge": 0, "D/crawl": 0}, "mesh": "b" * 64},
             "seen": []}
    for name in ("m500", "m250"):
        (tmp_path / "run" / name).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(e3, "_mesh", lambda score, folder: {"mesh_sha256": state[Path(folder).name]["mesh"],
                                                           "column_family": ["D", "D"], "columns": ["high_ledge", "crawl"]})

    def exposure(checkpoint, **k):
        row = state["m" + Path(checkpoint).stem.split("_")[1]]
        return None if row["opened"] is None else {"opened_kinds": dict(row["opened"], **{"A/gaps": 5, "B/stair_up": 3}),
                                                    "mesh_sha256": row["mesh"], "receipts": []}
    monkeypatch.setattr(evidence, "read_stage_exposure", exposure)

    def reader(folder, **k):
        state["seen"].append((Path(folder), k["stage_id"], sorted(c["family"] for c in k["inventory"]["opened_cells"])))
        return dict(state[Path(folder).parent.name]["cells"])
    monkeypatch.setattr(kinds, "read_e3_window", reader)
    stand_in["prior"] = {"stage_id": "E6b", "checkpoint_sha256": SHA, "checkpoint": str(tmp_path / "run" / "model_250.pt"),
                         "execution_plan_sha256": "c" * 64, "maintenance_source_sha256": "d" * 64,
                         "conditions": {"eval_seed": 7}, "is_prior": True}
    score = {"stage_id": "E6b", "checkpoint_sha256": SHA, "checkpoint": str(ctx.checkpoint),
             "execution_plan_sha256": "c" * 64, "maintenance_source_sha256": "d" * 64, "conditions": {"eval_seed": 7}}
    return ctx, score, state, stand_in


def _e6b(fixture):
    ctx, score, _, _ = fixture
    return late.E6bKindTwoWindowJudge().judge(ctx, dict(score))["stage_exit"]


def test_e6b_targets_are_the_plan_d_kinds_only_and_need_no_plan_entry():
    from foothold_s2.eval import ex42_late_stage_kinds as kinds
    plan = _real_plan()
    assert "E6b" not in plan["evaluation"]["late_kind_exit"]           # the plan file (and its SHA) is untouched
    assert kinds.level_targets(plan, "E6b") == {("D", "high_ledge"): 0, ("D", "crawl"): 0}
    assert kinds.folder_name("E6b") == "kind_cells_e6b"


def test_e6b_passes_when_both_windows_pass_every_d_cell(e6b):
    exit_row = _e6b(e6b)
    assert exit_row["judgement"] == "PASS" and exit_row["items"]["kind_current"]["cells"].keys() == set(D_CELLS)
    stage_ids = {seen[1] for seen in e6b[2]["seen"]}
    families = {f for seen in e6b[2]["seen"] for f in seen[2]}
    assert stage_ids == {"E6b"} and families == {"D"}                     # earlier families are not asked for


def test_e6b_a_failing_cell_in_either_window_fails_and_maintenance_is_not_bypassed(e6b):
    state = e6b[2]
    state["m500"]["cells"] = {"D/crawl/L0": PASS_CELL, "D/high_ledge/L0": FAIL_CELL}
    assert _e6b(e6b)["judgement"] == "FAIL"
    state["m500"]["cells"] = {k: PASS_CELL for k in D_CELLS}
    state["m250"]["cells"] = {"D/crawl/L0": FAIL_CELL, "D/high_ledge/L0": PASS_CELL}
    assert _e6b(e6b)["judgement"] == "FAIL"
    state["m250"]["cells"] = {k: PASS_CELL for k in D_CELLS}
    e6b[3]["maintenance"] = "HOLD"
    assert _e6b(e6b)["judgement"] == "HOLD"


def test_e6b_no_exposure_receipt_or_unopened_target_holds(e6b):
    state = e6b[2]
    state["m500"]["opened"] = {"D/high_ledge": 0}                         # crawl never opened
    row = _e6b(e6b)
    assert row["judgement"] == "HOLD" and row["items"]["kind_current"]["missing_targets"][0]["kind"] == "crawl"
    state["m500"]["opened"] = None
    row = _e6b(e6b)
    assert row["judgement"] == "HOLD" and row["items"]["kind_current"]["exposure_found"] is False


def test_e6b_a_missing_previous_window_or_changed_cells_or_mesh_is_hold(e6b):
    ctx, score, state, stand_in = e6b
    state["m250"]["cells"] = {"D/crawl/L0": PASS_CELL}
    assert _e6b(e6b)["items"]["same_cells"]["judgement"] == "HOLD" and _e6b(e6b)["judgement"] == "HOLD"
    state["m250"]["cells"] = {k: PASS_CELL for k in D_CELLS}
    state["m250"]["mesh"] = "e" * 64
    assert _e6b(e6b)["judgement"] == "HOLD"
    state["m250"]["mesh"] = "b" * 64
    stand_in["prior"] = None
    row = _e6b(e6b)
    assert row["judgement"] == "HOLD" and row["items"]["kind_previous"]["reason"] == "직전 창 없음"


def test_e6b_a_broken_raw_window_is_hold_with_the_reason_never_pass(e6b, monkeypatch):
    from foothold_s2.eval import ex42_late_stage_kinds as kinds
    monkeypatch.setattr(kinds, "read_e3_window", lambda *a, **k: (_ for _ in ()).throw(ValueError("trace sha differs")))
    row = _e6b(e6b)
    assert row["judgement"] == "HOLD" and "trace sha differs" in row["items"]["kind_current"]["reason"]


def test_e6b_a_score_of_another_stage_is_refused(e6b):
    from foothold_s2.eval import ex42_late_stage_kinds as kinds
    ctx, score, _, _ = e6b
    with pytest.raises(ValueError):
        kinds.recount(dict(score, stage_id="E5"), plan=ctx.plan, evaluation=ctx.evaluation, mesh={"mesh_sha256": "b" * 64},
                      stage_id="E6b")


def test_the_common_reader_now_sees_the_d_family_folder(tmp_path, monkeypatch):
    from foothold_s2.eval import ex42_stage_kind_bundle as bundle
    inventory = {"opened_cells": [{"family": "D", "kind": "crawl", "level": 0, "flag_source": bundle.KIND_FLAGS}]}
    folder = tmp_path / "kind_cells_e6b"
    folder.mkdir()
    args = dict(inventory=inventory, plan={}, plan_sha256="x", mesh={}, checkpoint_sha256="y", seed=1, stage_id="E6b")
    with pytest.raises(ValueError, match="coverage differs"):
        bundle.read_e3_window(folder, **args)
    (folder / "D" / "crawl" / "L0").mkdir(parents=True)
    monkeypatch.setattr(bundle, "read_stage_kind_bundle", lambda *a, **k: {"seen": k["family"]})
    assert bundle.read_e3_window(folder, **args) == {"D/crawl/L0": {"seen": "D"}}
    (folder / "D" / "high_ledge" / "L0").mkdir(parents=True)              # a cell nobody asked for is still a mismatch
    with pytest.raises(ValueError, match="coverage differs"):
        bundle.read_e3_window(folder, **args)


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
