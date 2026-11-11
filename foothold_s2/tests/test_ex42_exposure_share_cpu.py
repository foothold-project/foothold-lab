"""K boundary (CG terrain.exposure.<family>.<kind>.share): a partial exposure share becomes an env count.

A `share` rule is a fraction of ALL envs; the weight rules take the rest. Plan values are copied from the shipped
E1 section and only the new rule is added, so nothing here types an exposure number the plan does not hold.
"""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest
import torch

from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.terrains import ex42_exposure as ex
from foothold_s2.tests.test_ex42_exposure_cpu import PLAN, REAL, _stage_terrain

needs_mesh = pytest.mark.skipif(not (REAL / "terrain_mesh.npz").is_file(), reason="real mesh missing")


def _table():
    data = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    return cr.build_column_table([str(v) for v in data["column_family"]])


def _terrain(rule, *, weight=1.0):
    plan, terrain = _stage_terrain()
    spec = deepcopy(terrain)
    spec["exposure_at_E2"] = {"default": {"exposure": 0.0, "level_cap": 0},
                              "positive": [{"family": "A", "kinds_of": "continuous", "exposure": weight, "level_cap": 5},
                                           rule]}
    return spec


def _counts(spec, table, envs):
    exposure, caps = ex.exposure_by_column(spec, table, "E2")
    eligible, counts = ex.env_counts(envs, exposure)
    return exposure, caps, dict(zip(eligible.tolist(), counts.tolist()))


@needs_mesh
@pytest.mark.parametrize("weight", [1.0, 2.0, 0.37])
@pytest.mark.parametrize("envs", [3072, 6144])
def test_a_five_percent_share_holds_five_percent_of_the_envs_whatever_the_weight_scale(weight, envs):
    table = _table()
    rule = {"family": "A", "kind": "stepping_stones_low", "share": 0.05, "level_cap": 3}
    exposure, caps, counts = _counts(_terrain(rule, weight=weight), table, envs)
    ids = [i for i, row in enumerate(table) if row["family"] == "A" and row["kind"] == "stepping_stones_low"]
    assert ids and all(caps[i] == 3 for i in ids)
    held = sum(counts[i] for i in ids)
    assert abs(held - 0.05 * envs) <= 1                       # exact up to the rounding of one env
    assert sum(counts.values()) == envs                       # every env sits on some exposed column
    cont = [i for i, row in enumerate(table) if row["family"] == "A" and row["kind"] in
            _stage_terrain()[1]["kind_task"]["continuous"]]
    assert sum(counts[i] for i in cont) == envs - held       # the continuous columns take the rest (derived share)


@needs_mesh
def test_a_group_share_is_split_evenly_over_its_columns_and_other_columns_stay_empty():
    table = _table()
    rule = {"family": "B", "kinds_of": "B", "share": 0.10, "level_cap": 2}
    plan, terrain = _stage_terrain()
    terrain = deepcopy(terrain)
    terrain["kind_task"]["B"] = terrain["kind_task"]["B"]
    spec = _terrain({**rule, "kinds_of": "B"})
    _, caps, counts = _counts(spec, table, 3072)
    group = [i for i, row in enumerate(table) if row["family"] == "B" and row["kind"] in terrain["kind_task"]["B"]]
    assert group and max(counts[i] for i in group) - min(counts[i] for i in group) <= 1
    assert set(counts) == set(group) | {i for i, c in enumerate(caps) if c == 5}


@needs_mesh
@pytest.mark.parametrize("rule,match", [
    ({"family": "A", "kind": "stepping_stones_low", "share": 0.0, "level_cap": 3}, "0 < share < 1"),
    ({"family": "A", "kind": "stepping_stones_low", "share": 1.0, "level_cap": 3}, "0 < share < 1"),
    ({"family": "A", "kind": "stepping_stones_low", "share": True, "level_cap": 3}, "0 < share < 1"),
    ({"family": "A", "kind": "stepping_stones_low", "share": 0.05, "exposure": 0.05, "level_cap": 3}, "exactly one of exposure or share"),
    ({"family": "A", "kind": "stepping_stones_low", "level_cap": 3}, "exactly one of exposure or share"),
    ({"family": "A", "kind": "no_such_kind", "share": 0.05, "level_cap": 3}, "matches no mesh column"),
    ({"family": "A", "kind": "stepping_stones_low", "kinds_of": "continuous", "share": 0.05, "level_cap": 3}, "exactly one of kinds_of or kind"),
])
def test_a_malformed_share_rule_is_refused(rule, match):
    with pytest.raises(ValueError, match=match):
        ex.exposure_by_column(_terrain(rule), _table(), "E2")


@needs_mesh
def test_shares_that_leave_no_remainder_for_the_weight_rules_are_refused():
    table = _table()
    plan, terrain = _stage_terrain()
    spec = deepcopy(terrain)
    spec["exposure_at_E2"] = {"default": {"exposure": 0.0, "level_cap": 0}, "positive": [
        {"family": "A", "kind": "stepping_stones_low", "share": 0.6, "level_cap": 3},
        {"family": "A", "kind": "stepping_stones_high", "share": 0.5, "level_cap": 3}]}
    with pytest.raises(ValueError, match="positive remainder"):
        ex.exposure_by_column(spec, table, "E2")
    spec["exposure_at_E2"]["positive"] = spec["exposure_at_E2"]["positive"][:1]
    with pytest.raises(ValueError, match="positive remainder"):          # shares alone, no weight rule
        ex.exposure_by_column(spec, table, "E2")


@needs_mesh
def test_the_shipped_plan_sections_are_unchanged_weights_only():
    table = _table()
    plan, e0 = _stage_terrain()
    terrain = {**next(r for r in plan.document["stages"] if r["id"] == "E1")["terrain"], "kind_task": e0["kind_task"]}
    exposure, caps = ex.exposure_by_column(terrain, table, "E1")
    assert sum(w > 0 for w in exposure) == 23 and set(w for w in exposure if w > 0) == {1.0}


def test_env_counts_are_the_assignment():
    exposure = [0.0, 1.0, 0.0, 3.0]
    eligible, counts = ex.env_counts(10, exposure)
    types = ex.assign_exposed_columns(10, exposure, torch.Generator().manual_seed(0))
    assert eligible.tolist() == [1, 3] and counts.tolist() == [3, 7] or counts.tolist() == [2, 8]
    assert torch.bincount(types, minlength=4).tolist()[1::2] == counts.tolist()


# ---- inherited placement at a K boundary (planner: parent env_state left the new kind with 0 envs) ------------
def _parent_state(table, envs, spec_terrain):
    cont = [i for i, row in enumerate(table) if row["family"] == "A" and row["kind"] in spec_terrain["kind_task"]["continuous"]]
    gen = torch.Generator().manual_seed(1)
    types = torch.as_tensor(cont)[torch.randint(len(cont), (envs,), generator=gen)]
    levels = torch.randint(0, 6, (envs,), generator=gen)
    return types, levels, cont


@needs_mesh
@pytest.mark.parametrize("envs", [3072, 6144])
def test_a_k_boundary_fills_the_new_kind_from_the_parent_placement_and_keeps_the_rest(envs):
    table = _table()
    rule = {"family": "A", "kind": "stepping_stones_low", "share": 0.05, "level_cap": 3}
    spec = _terrain(rule)
    exposure, caps = ex.exposure_by_column(spec, table, "E2")
    shares = ex.column_shares(spec, table, "E2")
    types, levels, cont = _parent_state(table, envs, _stage_terrain()[1])
    new_types, new_levels, receipt = ex.rebalance_to_shares(types, levels, exposure, shares, torch.Generator().manual_seed(2))
    ids = [i for i, s in enumerate(shares) if s]
    held = int(torch.isin(new_types, torch.as_tensor(ids)).sum())
    assert abs(held - 0.05 * envs) <= 1 and receipt["moved_to_share_columns"] == held
    changed = new_types != types
    assert int(changed.sum()) == held                                       # nothing else moved
    assert bool((new_levels[changed] == 0).all()) and torch.equal(new_levels[~changed], levels[~changed])
    assert bool(torch.as_tensor([w > 0 for w in exposure])[new_types].all())


@needs_mesh
def test_envs_on_exposure_zero_columns_and_a_surplus_on_the_share_column_move_to_weight_columns():
    table = _table()
    spec = _terrain({"family": "A", "kind": "stepping_stones_low", "share": 0.05, "level_cap": 3})
    exposure, _ = ex.exposure_by_column(spec, table, "E2")
    shares = ex.column_shares(spec, table, "E2")
    types, levels, cont = _parent_state(table, 3072, _stage_terrain()[1])
    dead = [i for i, w in enumerate(exposure) if w == 0][0]
    share_col = [i for i, s in enumerate(shares) if s][0]
    types[:100] = dead                       # parent envs on a column that now has exposure 0
    types[100:600] = share_col               # far more than 5 % on the share column
    new_types, _, receipt = ex.rebalance_to_shares(types, levels, exposure, shares, torch.Generator().manual_seed(3))
    assert not bool((new_types == dead).any())
    assert abs(int((new_types == share_col).sum()) - 0.05 * 3072 / sum(1 for s in shares if s)) <= 1
    assert receipt["moved_to_weight_columns"] >= 100


@needs_mesh
def test_apply_exposure_with_shares_accepts_the_parent_and_without_shares_still_refuses_exposure_zero_envs():
    table = _table()
    spec = _terrain({"family": "A", "kind": "stepping_stones_low", "share": 0.05, "level_cap": 3})
    exposure, caps = ex.exposure_by_column(spec, table, "E2")
    shares = ex.column_shares(spec, table, "E2")
    types, levels, _ = _parent_state(table, 3072, _stage_terrain()[1])
    mesh = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)

    def terrain():
        return __import__("types").SimpleNamespace(
            terrain_levels=torch.zeros(3072, dtype=torch.long), terrain_types=torch.zeros(3072, dtype=torch.long),
            terrain_origins=torch.zeros(10, len(table), 3), env_origins=torch.zeros(3072, 3),
            update_env_origins=lambda *a: None)

    state = {"terrain_types": types, "terrain_levels": levels}
    t = terrain()
    receipt = ex.apply_exposure(t, exposure, caps, parent_env_state=state, table=table, parent_same_mesh=True, shares=shares)
    assert receipt["rebalance"]["moved_to_share_columns"] > 0
    assert int(torch.isin(t.terrain_types, torch.as_tensor([i for i, s in enumerate(shares) if s])).sum()) > 0
    with pytest.raises(ValueError, match="exposure 0"):
        ex.apply_exposure(terrain(), exposure, caps, parent_env_state={"terrain_types": torch.full((3072,), [i for i, w in enumerate(exposure) if w == 0][0]),
                                                                       "terrain_levels": levels},
                          table=table, parent_same_mesh=True)
