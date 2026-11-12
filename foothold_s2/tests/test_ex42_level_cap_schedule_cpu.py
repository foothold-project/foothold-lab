"""E1 L+ schedule: the continuous level cap of a segment follows the registered schedule (CG E.2 E1 "레벨" row, v0.17j).

Seven 250-update segments: 5, 5, 5 (command reinforcement), then 6, 7, 8, 9. Both caps follow the same number: the
per-column level caps of the exposure contract and the promotion cap the curriculum term reads
(`_ex41_terrain.level_cap`)."""
from __future__ import annotations

import copy
import pathlib
import sys
import types

import pytest
import torch
import yaml

from foothold_s2 import ex42_exposure_receipt as er
from foothold_s2.curriculum import ex41
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as te
from foothold_s2.terrains import ex42_exposure as ex

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "foothold_s2" / "curriculum" / "ex42-prep.yaml"
MESH = pathlib.Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2")
need_mesh = pytest.mark.skipif(not MESH.is_dir(), reason="real mesh not on this machine")
TERRAIN = {
    "continuous_level_cap": {"start": 6, "step_per_boundary": 1, "end": 9},
    "kind_task": {"continuous": {"pyramid_stairs": {}, "boxes": {}}},
    "exposure_at_E1": {"default": {"exposure": 0.0, "level_cap": 0},
                       "positive": [{"family": "A", "kinds_of": "continuous", "exposure": 1.0, "level_cap": 6},
                                    {"family": "A", "kind": "gaps", "share": 0.05, "level_cap": 1}]}}
TABLE = [{"family": "A", "kind": "pyramid_stairs"}, {"family": "A", "kind": "gaps"}, {"family": "A", "kind": "boxes"},
         {"family": "B", "kind": "rough"}]


@pytest.mark.parametrize("boundaries,cap", [(0, 6), (1, 7), (2, 8), (3, 9), (4, 9), (7, 9)])
def test_the_cap_rises_one_per_boundary_and_stops_at_the_end(boundaries, cap):
    before = copy.deepcopy(TERRAIN)
    terrain, got = ex.raise_continuous_cap(TERRAIN, "E1", boundaries)
    assert got == cap and TERRAIN == before                                    # the plan row itself is not touched
    _, caps = ex.exposure_by_column(terrain, TABLE, "E1")
    assert caps == [cap, 1, cap, 0]                                            # only the continuous columns move


@pytest.mark.parametrize("first,caps", [(1, [6, 7, 8, 9, 9]), (3, [6, 6, 6, 7, 8, 9, 9]), (5, [6, 6, 6, 6, 6, 7])])
def test_the_first_raise_may_wait_for_a_later_boundary(first, caps):
    terrain = copy.deepcopy(TERRAIN)
    terrain["continuous_level_cap"]["first_raise_boundary"] = first
    assert [ex.raise_continuous_cap(terrain, "E1", k)[1] for k in range(len(caps))] == caps


def test_a_stage_without_the_cell_is_unchanged():
    plain = {k: v for k, v in TERRAIN.items() if k != "continuous_level_cap"}
    terrain, cap = ex.raise_continuous_cap(plain, "E1", 3)
    assert cap is None and terrain == plain


def _with(**cell):
    terrain = copy.deepcopy(TERRAIN)
    terrain["continuous_level_cap"] = {**terrain["continuous_level_cap"], **cell}
    return terrain


@pytest.mark.parametrize("terrain,k", [
    (TERRAIN, -1), (TERRAIN, True), (TERRAIN, 1.0),
    (_with(start=6.0), 0), (_with(start=True), 0), (_with(end=5), 0), (_with(step_per_boundary=0), 0),
    (_with(first_raise_boundary=0), 0), (_with(first_raise_boundary=True), 0), (_with(first_raise_boundary=2.0), 0),
    (_with(hold_when="retention_table_hold"), 0), (_with(hold=1), 0),          # a key nothing reads is refused
    (_with(start=5), 0),                                                       # differs from the rule's own level_cap
    ({**TERRAIN, "continuous_level_cap": [6, 1, 9]}, 0),
])
def test_a_malformed_schedule_or_boundary_count_is_refused(terrain, k):
    with pytest.raises(ValueError, match="continuous"):
        ex.raise_continuous_cap(terrain, "E1", k)


def test_the_schedule_needs_exactly_one_continuous_rule():
    two = copy.deepcopy(TERRAIN)
    two["exposure_at_E1"]["positive"].append({"family": "B", "kinds_of": "continuous", "exposure": 1.0, "level_cap": 6})
    none = copy.deepcopy(TERRAIN)
    none["exposure_at_E1"]["positive"] = none["exposure_at_E1"]["positive"][1:]
    for terrain in (two, none):
        with pytest.raises(ValueError, match="exactly one kinds_of rule"):
            ex.raise_continuous_cap(terrain, "E1", 0)


def test_the_shipped_plan_gives_e1_three_segments_at_five_then_six_to_nine_and_no_other_stage_a_schedule():
    rows = {row["id"]: row for row in yaml.safe_load(PLAN.read_text(encoding="utf-8"))["stages"]}
    assert [ex.raise_continuous_cap(rows["E1"]["terrain"], "E1", k)[1] for k in range(9)] == [5, 5, 5, 6, 7, 8, 9, 9, 9]
    assert rows["E1"]["maximum_updates"] == rows["E1"]["minimum_updates"] == 7 * 250          # seven segments, no early exit
    assert [stage for stage, row in rows.items() if "continuous_level_cap" in (row.get("terrain") or {})] == ["E1"]


# ---- the promotion cap of the running segment -------------------------------------------------------------
def _runtime(stage="E1", cap=None):
    plan = types.SimpleNamespace(stages=[types.SimpleNamespace(name="s")])
    bound = te.E_STAGES[stage][0] if stage in te.E_STAGES else 1000
    runtime = te.EX42StageZeroRuntime(stage_zero_plan=plan, plan_sha256="1" * 64, approval_sha256="2" * 64,
                                      parent_sha256="3" * 64, maximum_updates=bound, push_vmax_mps=2.0, stage_id=stage)
    env = types.SimpleNamespace(num_envs=4, device="cpu")
    if cap is not None:
        env._ex42_env_contract = {"continuous_level_cap": cap}
    runtime.attach_environment(env, types.SimpleNamespace())
    return runtime, env


def test_the_promotion_cap_is_the_contract_cap_and_stays_five_without_one():
    runtime, env = _runtime(cap=7)
    assert env._ex41_terrain == {"policy": "performance", "level_cap": 7}
    assert runtime.state_dict()["terrain"] == runtime.effective["terrain"] == {"policy": "performance", "level_cap": 7}
    runtime, env = _runtime()
    assert env._ex41_terrain["level_cap"] == runtime.state_dict()["terrain"]["level_cap"] == 5
    runtime, env = _runtime(stage="EX42_0_T0_prime")
    assert env._ex41_terrain["level_cap"] == 5


@pytest.mark.parametrize("cap", [4, True, 7.0, "7"])
def test_a_contract_cap_below_the_stage_zero_cap_or_not_an_integer_is_refused(cap):
    with pytest.raises(ValueError, match="continuous level cap"):
        _runtime(cap=cap)


def test_the_curriculum_term_promotes_up_to_that_cap_only():
    levels = torch.tensor([5, 6, 7, 7, 0])
    moves = torch.tensor([1, 1, 1, -1, -1])
    assert ex41.capped_moves(levels, moves, 7).tolist() == [1, 1, 0, -1, 0]
    assert ex41.capped_moves(levels, moves, 5).tolist() == [0, 0, 0, -1, 0]      # the old literal: nothing above 5


def test_a_continued_segment_accepts_the_lower_cap_the_earlier_segment_saved():
    saved = _runtime(cap=6)[0].state_dict()
    later, _ = _runtime(cap=7)
    later.load_state_dict(saved)                                                # 6 then 7: the next segment
    later.load_state_dict({**saved, "terrain": {"policy": "performance", "level_cap": 7}})
    for terrain in ({"policy": "performance", "level_cap": 8},                  # saved above this segment
                    {"policy": "performance", "level_cap": 4},                  # below the stage-zero cap
                    {"policy": "fixed_l02", "level_cap": 6},
                    {"policy": "performance", "level_cap": True},
                    {"policy": "performance"}, None):
        with pytest.raises(ValueError, match="terrain differs"):
            later.load_state_dict({**saved, "terrain": terrain})


def test_stage_zero_keeps_the_exact_terrain_match():
    zero, _ = _runtime(stage="EX42_0_T0_prime")
    saved = zero.state_dict()
    zero.load_state_dict(saved)
    with pytest.raises(ValueError, match="terrain differs"):
        zero.load_state_dict({**saved, "terrain": {"policy": "performance", "level_cap": 4}})


# ---- the real plan and mesh ----------------------------------------------------------------------------------
class Term:
    def __init__(self, func=None, mode="reset", params=None):
        self.func, self.mode, self.params = func, mode, dict(params or {})


@pytest.fixture
def isaac_stubs(monkeypatch):
    managers = types.ModuleType("isaaclab.managers")
    managers.EventTermCfg = Term
    utils = types.ModuleType("isaaclab.utils")
    utils.configclass = lambda c: c
    monkeypatch.setitem(sys.modules, "isaaclab", types.ModuleType("isaaclab"))
    monkeypatch.setitem(sys.modules, "isaaclab.managers", managers)
    monkeypatch.setitem(sys.modules, "isaaclab.utils", utils)


def _contract(stage, k):
    events = types.SimpleNamespace(
        reset_base=Term(params={"pose_range": {}, "velocity_range": {"x": (0.0, 0.0)}}),
        ex40_push=Term(func=lambda *a: None, mode="interval", params={"velocity_range": {"x": (-1, 1)}}))
    cfg = types.SimpleNamespace(events=events, commands=types.SimpleNamespace(
                                    base_velocity=types.SimpleNamespace(flag_provider=None)),
                                scene=types.SimpleNamespace(terrain=types.SimpleNamespace(terrain_generator=None)))
    return te.prepare_e0_env_cfg(cfg, EX42Plan.load(PLAN), MESH, stage_id=stage, boundary_index=k)


@need_mesh
@pytest.mark.parametrize("k,cap", [(0, 5), (2, 5), (3, 6), (4, 7), (6, 9)])
def test_the_real_e1_contract_carries_the_segment_cap_on_every_continuous_column(isaac_stubs, k, cap):
    contract = _contract("E1", k)
    assert contract["continuous_level_cap"] == cap
    open_caps = {c for c, w in zip(contract["level_caps"], contract["exposure"]) if w > 0}
    assert open_caps == {cap} and sum(w > 0 for w in contract["exposure"]) == 23        # the 23 continuous columns
    assert {c for c, w in zip(contract["level_caps"], contract["exposure"]) if w == 0} == {0}


@need_mesh
def test_a_stage_without_the_schedule_keeps_its_plan_caps(isaac_stubs):
    assert _contract("E3", 0)["continuous_level_cap"] is None


@need_mesh
def test_the_receipt_replay_follows_the_same_schedule(isaac_stubs):
    body = er.build_receipt(_contract("E1", 4), stage_id="E1", plan_sha256="a" * 64, iteration=1000, kind="start")
    er.recompute_from_plan(body, EX42Plan.load(PLAN), MESH)
    wrong = er.build_receipt(_contract("E1", 2), stage_id="E1", plan_sha256="a" * 64, iteration=1000, kind="start")
    wrong["boundary_index"] = 4                                                # cap 5 written for the cap 7 segment
    with pytest.raises(ValueError):
        er.recompute_from_plan(wrong, EX42Plan.load(PLAN), MESH)
