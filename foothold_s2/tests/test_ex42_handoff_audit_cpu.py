"""verifier-lx 11/14 hand-off audit (E1 -> E1F -> E2): every case is a known-answer counterexample from that audit.

H1 E1F previous window from another plan or seed, H2 valid < 64 is HOLD (E1F and E2), H3 the E2 kind env command
bundle through the real controller, H4 E2 inherits the parent's continuous cap.
"""
from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from foothold_s2.eval.ex42_flag_cells import read_evidence
from foothold_s2.ex42_e1f_judge import FlagTwoWindowJudge
from foothold_s2.tests import test_ex42_e1f_flag_cpu as ft
from foothold_s2.tests.test_ex42_filled_approval_guards_cpu import APPROVALS, TABLE, filled, pin

OTHER_PLAN = "a" * 64
PRIOR_SHA = "b" * 64


def _window(tmp_path, monkeypatch, *, prior_seed=42, prior_plan=ft.PLAN_SHA):
    """A current E1F window (m500) and the window before it (m250), both written as the Kit child writes them."""
    plan, _cal, _current, _roots = ft._full(tmp_path / "cal")
    run = tmp_path / "run"
    run.mkdir()
    cp250, cp500 = run / "model_250.pt", run / "model_500.pt"
    cp250.write_bytes(b"prior policy")
    cp500.write_bytes(b"current policy")
    ft._write_round(run / "m500" / "flag_cells", plan, 42, plan_sha=ft.PLAN_SHA, checkpoint_sha=ft._sha(cp500))
    ft._write_round(run / "m250" / "flag_cells", plan, prior_seed, plan_sha=prior_plan, checkpoint_sha=ft._sha(cp250))
    cells = {}
    for count in ("flag_one", "flag_four"):
        cells.update(read_evidence(run / "m250" / "flag_cells" / count, plan=plan, plan_sha256=prior_plan,
                                   checkpoint_sha256=ft._sha(cp250), seed=prior_seed, count=count))
    prior = {"checkpoint": str(cp250), "checkpoint_sha256": ft._sha(cp250), "flag_cells": cells,
             "maintenance_source_sha256": prior_plan, "conditions": {"eval_seed": prior_seed}}
    monkeypatch.setattr("foothold_s2.ex42_e1f_judge.judge_maintenance",
                        lambda score, baseline, measured: {**score, "judgement": "PASS"})
    monkeypatch.setattr("foothold_s2.ex42_e0_judge.load_baseline", lambda *args: {})
    monkeypatch.setattr("foothold_s2.ex42_stage_judges.previous_window", lambda ctx: prior)
    ctx = SimpleNamespace(root=ft.ROOT, cfg={"baseline": {"sha256": "a" * 64}}, plan=plan,
                          evaluation=run / "m500", checkpoint_sha=ft._sha(cp500), plan_path=tmp_path / "plan.yaml",
                          seed=42, digest=lambda path: ft.PLAN_SHA)
    score = {"maintenance_source_sha256": ft.PLAN_SHA, "conditions": {"eval_seed": 42}}
    return plan, ctx, score, prior


def test_h1_a_previous_window_of_the_same_plan_seed_and_raw_files_still_passes(tmp_path, monkeypatch):
    plan, ctx, score, _prior = _window(tmp_path, monkeypatch)
    result = FlagTwoWindowJudge().judge(ctx, score)
    assert result["judgement"] == "PASS"
    assert result["stage_exit"]["previous_identity"]["eval_seed"] == 42
    assert FlagTwoWindowJudge().verify(result, "PASS", "PASS", plan=plan)["stage_exit"] == result["stage_exit"]


@pytest.mark.parametrize("seed,plan_sha", [(999, ft.PLAN_SHA), (42, OTHER_PLAN), (999, OTHER_PLAN)])
def test_h1_a_previous_window_of_another_plan_or_seed_is_refused(tmp_path, monkeypatch, seed, plan_sha):
    """The audit's counterexample: previous seed 999 and another plan, every SHA of its own files truthful."""
    _plan, ctx, score, _prior = _window(tmp_path, monkeypatch, prior_seed=seed, prior_plan=plan_sha)
    with pytest.raises(ValueError, match="plan or seed differs"):
        FlagTwoWindowJudge().judge(ctx, score)


def test_h1_previous_cells_must_recount_from_their_own_raw_files(tmp_path, monkeypatch):
    plan, ctx, score, prior = _window(tmp_path, monkeypatch)
    prior["flag_cells"] = copy.deepcopy(prior["flag_cells"])
    prior["flag_cells"]["flag_one_eval_gt"]["success_count"] = 63       # a stored score that disagrees with its raw
    with pytest.raises(ValueError, match="differ from their raw evidence"):
        FlagTwoWindowJudge().judge(ctx, score)
    prior["flag_cells"] = {}                                             # or one that drops cells that exist on disk
    with pytest.raises(ValueError, match="differ from their raw evidence"):
        FlagTwoWindowJudge().judge(ctx, score)


def test_h1_p1_verify_rechecks_the_previous_window_identity(tmp_path, monkeypatch):
    plan, ctx, score, _prior = _window(tmp_path, monkeypatch)
    result = FlagTwoWindowJudge().judge(ctx, score)
    forged = copy.deepcopy(result)
    forged["stage_exit"]["previous_identity"]["eval_seed"] = 999
    with pytest.raises(ValueError, match="plan or seed differs"):
        FlagTwoWindowJudge().verify(forged, "PASS", "PASS", plan=plan)
    dropped = copy.deepcopy(result)
    dropped["stage_exit"]["previous_identity"] = None
    with pytest.raises(ValueError, match="identity absent"):
        FlagTwoWindowJudge().verify(dropped, "PASS", "PASS", plan=plan)
    wrong_folder = copy.deepcopy(result)
    wrong_folder["stage_exit"]["previous_identity"]["evaluation"] = str(tmp_path / "run" / "m500" / "flag_cells")
    with pytest.raises(ValueError, match="receipt identity|not from the checked previous window"):
        FlagTwoWindowJudge().verify(wrong_folder, "PASS", "PASS", plan=plan)


def test_h2_the_plan_and_both_consumers_use_the_whole_64_window(tmp_path):
    plan = yaml.safe_load(TABLE.read_text(encoding="utf-8-sig"))
    assert plan["evaluation"]["flag_cells"]["valid_min"] == 64
    assert plan["evaluation"]["e2_kind_cells"]["valid_min_each"] == 64
    from foothold_s2.ex42_e1f_judge import _flag_window
    from foothold_s2.ex42_e2_judge import _spec
    weaker = copy.deepcopy(plan)
    weaker["evaluation"]["e2_kind_cells"]["valid_min_each"] = 48
    with pytest.raises(ValueError, match="E2 named-kind exit contract"):
        _spec(weaker)
    flag_plan, _cal, current, _roots = ft._full(tmp_path)
    flag_plan["evaluation"]["flag_cells"]["valid_min"] = 48
    with pytest.raises(ValueError, match="must equal the whole window"):
        _flag_window(current["flag_one_eval_gt"], flag_plan, "flag_one_eval_gt")


def test_h2_48_valid_with_39_success_and_45_survival_is_hold_in_e1f_and_e2(tmp_path):
    """The audit's counterexample: 48 valid, 39 success, 45 survival passed both stages before."""
    plan, _cal, current, _roots = ft._full(tmp_path)
    changed = ft._rewrite_cell(tmp_path, current, "flag_one_eval_gt", valid_count=48, success_count=39,
                               survival_count=45)
    from foothold_s2.ex42_e1f_judge import _flag_window
    assert _flag_window(changed["flag_one_eval_gt"], plan, "flag_one_eval_gt")["judgement"] == "HOLD"
    from foothold_s2.ex42_e2_judge import score_mode
    forward = {"valid_count": 48, "success_count": 39, "survival_count": 45}
    flag = {"valid_count": 64, "success_count": 64, "survival_count": 64}
    row = score_mode(forward, flag, valid_min_each=64, success_min=52, survival_min=60, weak_fraction=.5)
    assert row["judgement"] == "HOLD"


# ---- H3: the E2 kind env command bundle, through the real controller ------------------------------------------------
def test_h3_e2_stepping_stone_envs_get_the_flag_and_forward_one_and_nothing_else():
    import torch

    from foothold_s2.commands import ex42_shares as cs, mixed_core as mc
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.scripts import ex42_training_entry as te

    plan = EX42Plan.load(TABLE)
    doc = copy.deepcopy(plan.document)
    row = next(r for r in doc["stages"] if r["id"] == "E2")
    row["terrain"]["exposure_at_E2"]["positive"][0]["level_cap"] = 5          # what materialize fills from E1F
    plan = replace(plan, document=doc)
    source, old = te.load_ex42_stage_zero_source(plan)
    view = te.make_ex42_stage_zero_plan_view(source, old, {"parent_sha256": "0" * 64}, ex42_plan=plan, stage_id="E2")
    n = 10000
    term = SimpleNamespace(gen=mc.make_generator(42), is_flag_env=torch.ones(n, dtype=torch.bool),
                           slot_current=torch.full((n,), -1), cfg=SimpleNamespace(dynamic_flags=True, force_flag_provider=None))
    table = [{"family": "A", "kind": "pyramid_stairs"}, {"family": "A", "kind": "stepping_stones_low"}]
    raw = SimpleNamespace(num_envs=n, device="cpu", _ex42_column_table=table,
                          scene=SimpleNamespace(terrain=SimpleNamespace(terrain_types=torch.arange(n) % 2)))
    runtime = SimpleNamespace(plan=view, env_stage=torch.zeros(n, dtype=torch.long))
    shares = cs.CommandShares(view.command_contract, view.stages[0])
    shares.attach(raw, term, runtime)
    ids = torch.arange(n)
    shares.reset(ids)
    stones = ids[~shares.continuous()]
    flags = int(term.is_flag_env[stones].sum())
    assert len(stones) == 5000 and 0.30 < flags / len(stones) < 0.44         # planner weight 0.37, was 0 envs
    free = stones[~term.is_flag_env[stones]]
    names = Counter()
    for stage_index in runtime.env_stage[free].unique().tolist():
        members = free[runtime.env_stage[free] == stage_index]
        sample = mc.resample_stage(term.gen, len(members), runtime.plan.stages[stage_index], torch.zeros(len(members)))
        names.update(mc.EX39_SLOTS[int(i)] for i in sample["slot"])
    assert set(names) == {"forward"}                                        # no reverse / side / spin / stand
    assert float(sample["cmd"][:, 0].min()) == pytest.approx(1.0) and float(sample["cmd"][:, 0].max()) == pytest.approx(1.0)


# ---- H4: E2 inherits the continuous cap the parent ended with --------------------------------------------------------
def test_h4_e2_registers_the_same_cap_inheritance_as_e1f():
    plan = yaml.safe_load(TABLE.read_text(encoding="utf-8-sig"))
    rows = {row["id"]: row for row in plan["stages"]}
    e1f = rows["E1F"]["authorization_contract"]["inherited_stage_templates"][0]
    e2 = rows["E2"]["authorization_contract"]["inherited_stage_templates"][0]
    assert e2["approval_path"] == e1f["approval_path"] and e2["allowed_values"] == e1f["allowed_values"]
    assert e2["stage_path"] == "terrain.exposure_at_E2" and e2["value_path"] == "positive.0.level_cap"
    assert rows["E2"]["terrain"]["exposure_at_E2"]["positive"][0]["level_cap"] is None    # no assumed 5


@pytest.mark.parametrize("parent_cap", [5, 6, 7, 8, 9])
def test_h4_e2_row_must_carry_exactly_the_measured_parent_cap(tmp_path, parent_cap):
    plan, path, data, validate = filled(tmp_path, "E2")
    cell = data["stage_e2_authorization"]
    cell["prerequisites"]["predecessor_exit"]["continuous_level_cap"] = parent_cap
    doc = copy.deepcopy(plan.document)
    positive = next(r for r in doc["stages"] if r["id"] == "E2")["terrain"]["exposure_at_E2"]["positive"]
    positive[0]["level_cap"] = parent_cap
    assert validate(pin(replace(plan, document=doc), path, data), path, "b" * 64)["scope"]["stage_id"] == "E2"
    if parent_cap != 5:                         # the audit's counterexample: the row falls back to 5 under a cap-6..9 parent
        positive[0]["level_cap"] = 5
        with pytest.raises(ValueError, match="measured predecessor cap"):
            validate(pin(replace(plan, document=doc), path, data), path, "b" * 64)


def test_h4_an_unfilled_or_out_of_range_parent_cap_is_refused(tmp_path):
    for bad in (None, 4, 10, True):
        plan, path, data, validate = filled(tmp_path, "E2")
        data["stage_e2_authorization"]["prerequisites"]["predecessor_exit"]["continuous_level_cap"] = bad
        with pytest.raises(ValueError, match="inherited stage integer"):
            validate(pin(plan, path, data), path, "b" * 64)


@pytest.mark.parametrize("cap", [5, 6, 7, 8, 9])
def test_h4_materialize_continues_with_the_cap_the_e1f_row_carries(cap):
    """The audit's E2 materialize counterexample: a cap-6..9 parent made E2 fall back to the template's 5."""
    from foothold_s2.ex42_stage_materialize import inherited_cap
    doc = yaml.safe_load(TABLE.read_text(encoding="utf-8-sig"))
    rows = {row["id"]: row for row in doc["stages"]}
    rows["E1F"]["terrain"]["exposure_at_E1F"]["positive"][0]["level_cap"] = cap
    source = SimpleNamespace(document=doc)
    got, ref = inherited_cap(rows["E2"]["authorization_contract"], None, target="E2", source=source, stage="E1F",
                             base=Path("."), parent_manifest=Path("."))
    assert (got, ref) == (cap, None)


def test_h4_an_unfilled_source_cap_is_refused_not_replaced_by_the_assumed_five():
    from foothold_s2.ex42_stage_materialize import inherited_cap
    doc = yaml.safe_load(TABLE.read_text(encoding="utf-8-sig"))
    rows = {row["id"]: row for row in doc["stages"]}
    assert rows["E1F"]["terrain"]["exposure_at_E1F"]["positive"][0]["level_cap"] is None   # the template: not measured
    with pytest.raises(ValueError, match="unfilled in the source plan"):
        inherited_cap(rows["E2"]["authorization_contract"], None, target="E2", source=SimpleNamespace(document=doc),
                      stage="E1F", base=Path("."), parent_manifest=Path("."))
