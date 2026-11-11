"""CG boundary rules as code: E3 share donation, E5 10/70/20 regrade + commands, E6a posture, E6b family share."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest
import torch

from foothold_s2.terrains import ex42_boundary_rules as br
from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.terrains import ex42_exposure as ex
from foothold_s2.tests.test_ex42_exposure_cpu import REAL, _stage_terrain

needs_mesh = pytest.mark.skipif(not (REAL / "terrain_mesh.npz").is_file(), reason="real mesh missing")


# ---- E3: three grades with a donor vector ----------------------------------------------------------------------
def test_opening_a_kind_takes_the_share_from_the_continuous_side_while_it_stays_above_the_floor():
    r = br.donate_for_k_boundary({"a": 0.05}, "b", 0.05, easy_kinds=["a"])
    assert r["shares"] == {"a": 0.05, "b": 0.05} and r["donor_vector"] == {"continuous": pytest.approx(-0.05)}
    assert r["continuous_share"] == pytest.approx(0.90)


def test_when_the_continuous_share_hits_its_floor_the_rest_comes_equally_from_the_easy_kinds():
    shares = {"cur": 0.30, "e1": 0.14, "e2": 0.14}            # continuous 0.42 is below the 0.429 floor already
    r = br.donate_for_k_boundary(shares, "new", 0.05, easy_kinds=["e1", "e2"])
    assert r["donor_vector"] == {"e1": pytest.approx(-0.025), "e2": pytest.approx(-0.025)}
    assert r["shares"]["e1"] == pytest.approx(0.115) and r["shares"]["new"] == 0.05
    assert r["allowed_diff_paths"][0] == "terrain.exposure.new.share"


def test_a_donation_that_breaks_a_floor_is_refused_not_renormalized():
    with pytest.raises(ValueError, match="floor"):
        br.donate_for_k_boundary({"cur": 0.40, "e1": 0.14, "e2": 0.025}, "new", 0.05, easy_kinds=["e1", "e2"])
    with pytest.raises(ValueError, match="easy-grade"):
        br.donate_for_k_boundary({"cur": 0.30, "x": 0.27}, "new", 0.05, easy_kinds=[])
    with pytest.raises(ValueError, match="also a donor"):
        br.donate_for_k_boundary({"a": 0.1}, "a", 0.15, easy_kinds=["a"])


def test_dropping_a_kind_to_the_easy_grade_gives_the_share_back_to_the_continuous_side():
    r = br.donate_for_k_boundary({"a": 0.10, "b": 0.05}, "a", 0.03, easy_kinds=["b"])
    assert r["donor_vector"] == {"continuous": pytest.approx(0.07)} and r["continuous_share"] == pytest.approx(0.92)


# ---- E5 regrade --------------------------------------------------------------------------------------------------
def test_regrade_splits_the_sparse_total_ten_seventy_twenty_equally_inside_a_grade():
    r = br.regrade_shares({"new": ["n"], "current": ["c1", "c2"], "easy": ["e"]}, 0.20)
    assert r["shares"] == {"n": pytest.approx(0.02), "c1": pytest.approx(0.07), "c2": pytest.approx(0.07), "e": pytest.approx(0.04)}
    assert sum(r["shares"].values()) == pytest.approx(0.20)


@pytest.mark.parametrize("grades,total,match", [
    ({"new": [], "current": ["c"], "easy": ["e"]}, 0.2, "every grade"),
    ({"new": ["a"], "current": ["a"], "easy": ["e"]}, 0.2, "two grades"),
    ({"new": ["n"], "current": ["c"], "easy": ["e"]}, 0.20, "floor"),       # 10 % of 0.20 = 0.02 ok, easy 0.04 ok -> see below
    ({"new": ["n"], "current": ["c"], "easy": ["e"]}, 0.60, "continuous floor"),
])
def test_regrade_refuses_empty_grades_double_grades_floor_and_oversize(grades, total, match):
    if match == "floor":                                       # a total small enough that new < 2 %
        total = 0.10
    with pytest.raises(ValueError, match=match):
        br.regrade_shares(grades, total)


@needs_mesh
def test_regraded_shares_become_env_counts_inside_one_env_of_the_share():
    data = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    table = cr.build_column_table([str(v) for v in data["column_family"]])
    kinds = ["stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams"]
    r = br.regrade_shares({"new": [kinds[0]], "current": kinds[1:3], "easy": [kinds[3]]}, 0.20)
    plan, terrain = _stage_terrain()
    spec = deepcopy(terrain)
    spec["exposure_at_E5"] = {"default": {"exposure": 0.0, "level_cap": 0}, "positive": [
        {"family": "A", "kinds_of": "continuous", "exposure": 1.0, "level_cap": 5},
        *br.positive_rules(r["shares"], {k: "A" for k in kinds}, {k: 3 for k in kinds})]}
    exposure, _ = ex.exposure_by_column(spec, table, "E5")
    eligible, counts = ex.env_counts(3072, exposure)
    held = dict(zip(eligible.tolist(), counts.tolist()))
    for kind, share in r["shares"].items():
        ids = [i for i, row in enumerate(table) if row["family"] == "A" and row["kind"] == kind]
        assert abs(sum(held.get(i, 0) for i in ids) - share * 3072) <= len(ids)


# ---- E5 commands -----------------------------------------------------------------------------------------------
def test_reverse_and_sideways_join_the_command_set_with_weights_decided_in_the_same_step():
    entry = {"command_set": ["forward_1.0", "flag"], "command_weights": {"forward_1.0": 0.63, "flag": 0.37}}
    r = br.extend_kind_commands(entry, ["reverse"], {"forward_1.0": 0.53, "flag": 0.37, "reverse": 0.10})
    assert r["command_set"] == ["forward_1.0", "flag", "reverse"]
    assert set(r["allowed_diff_paths"]) == {"command_set", "command_weights.forward_1.0", "command_weights.flag",
                                            "command_weights.reverse"}
    assert br.command_counts(100, r["command_set"], r["command_weights"]) == {"forward_1.0": 53, "flag": 37, "reverse": 10}


@pytest.mark.parametrize("add,weights,match", [
    (["spin_left"], {"forward_1.0": 0.5, "flag": 0.4, "spin_left": 0.1}, "can be added"),
    (["reverse"], {"forward_1.0": 0.5, "flag": 0.5}, "keys"),
    (["reverse"], {"forward_1.0": 0.5, "flag": 0.5, "reverse": 0.1}, "sum to 1"),
    (["reverse"], {"forward_1.0": 1.1, "flag": -0.2, "reverse": 0.1}, "non-negative"),
    (["flag"], {"forward_1.0": 0.5, "flag": 0.5}, "can be added"),
])
def test_command_extension_refuses_bad_additions_and_weights(add, weights, match):
    entry = {"command_set": ["forward_1.0", "flag"], "command_weights": {"forward_1.0": 0.63, "flag": 0.37}}
    with pytest.raises(ValueError, match=match):
        br.extend_kind_commands(entry, add, weights)


def test_command_counts_always_sum_to_the_env_count():
    for n in (1, 7, 154, 307):
        counts = br.command_counts(n, ["a", "b", "c"], {"a": 0.5, "b": 0.3, "c": 0.2})
        assert sum(counts.values()) == n


# ---- E6a posture ------------------------------------------------------------------------------------------------
def test_one_posture_axis_widens_with_its_reward_weight_and_the_other_stays():
    r = br.widen_posture({"delta_h": (0.0, 0.0), "roll": (0.0, 0.0)}, {"height": 0.0, "roll": 0.0}, "delta_h",
                         step=0.02, limit=0.06, reward_weight=1.0)
    assert r["ranges"] == {"delta_h": (-0.02, 0.02), "roll": (0.0, 0.0)} and r["reward_weights"] == {"height": 1.0, "roll": 0.0}
    assert r["allowed_diff_paths"] == ["ranges.delta_h", "rewards.height.weight"]
    at_limit = br.widen_posture(r["ranges"], r["reward_weights"], "delta_h", step=0.05, limit=0.06, reward_weight=1.0)
    assert at_limit["ranges"]["delta_h"] == (-0.06, 0.06)
    with pytest.raises(ValueError, match="limit"):
        br.widen_posture(at_limit["ranges"], at_limit["reward_weights"], "delta_h", step=0.05, limit=0.06, reward_weight=1.0)
    with pytest.raises(ValueError, match="axis"):
        br.widen_posture(r["ranges"], r["reward_weights"], "pitch", step=0.02, limit=0.06, reward_weight=1.0)


def test_posture_samples_stay_inside_the_current_ranges_and_a_closed_axis_is_exactly_zero():
    gen = torch.Generator().manual_seed(3)
    out = br.sample_posture(4096, {"delta_h": (-0.05, 0.03), "roll": (0.0, 0.0)}, gen)
    assert out.shape == (4096, 2) and float(out[:, 0].min()) >= -0.05 and float(out[:, 0].max()) <= 0.03
    assert float(out[:, 0].min()) < -0.04 and float(out[:, 0].max()) > 0.02 and bool((out[:, 1] == 0).all())


# ---- E6b family share --------------------------------------------------------------------------------------------
@needs_mesh
def test_family_d_goes_from_exposure_zero_to_five_percent_of_the_envs():
    data = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    table = cr.build_column_table([str(v) for v in data["column_family"]])
    d_kinds = sorted({row["kind"] for row in table if row["family"] == "D"})
    assert d_kinds
    plan, terrain = _stage_terrain()
    section = {"default": {"exposure": 0.0, "level_cap": 0}, "positive": [
        {"family": "A", "kinds_of": "continuous", "exposure": 1.0, "level_cap": 5}]}
    spec = deepcopy(terrain)
    spec["exposure_at_E6b"] = br.open_family_share(section, "D", d_kinds, 0.05)
    exposure, caps = ex.exposure_by_column(spec, table, "E6b")
    d_cols = [i for i, row in enumerate(table) if row["family"] == "D"]
    assert all(exposure[i] > 0 and caps[i] == 0 for i in d_cols)
    eligible, counts = ex.env_counts(3072, exposure)
    held = dict(zip(eligible.tolist(), counts.tolist()))
    assert abs(sum(held.get(i, 0) for i in d_cols) - 0.05 * 3072) <= len(d_kinds)
    with pytest.raises(ValueError, match="already"):
        br.open_family_share(spec["exposure_at_E6b"], "D", d_kinds, 0.05)
