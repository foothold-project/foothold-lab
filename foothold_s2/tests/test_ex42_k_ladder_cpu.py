"""K boundary ladder: shares of a stage after k boundaries, from the plan's `terrain.k_ladder` (CPU only)."""
from __future__ import annotations

import pathlib

import numpy as np
import pytest
import yaml

from foothold_s2.terrains import ex42_column_reset as cr
from foothold_s2.terrains import ex42_exposure as ex
from foothold_s2.terrains.ex42_k_ladder import ladder_terrain
from foothold_s2.tests.test_ex42_exposure_cpu import PLAN, REAL

needs_mesh = pytest.mark.skipif(not (REAL / "terrain_mesh.npz").is_file(), reason="real mesh missing")
TRAIN_START = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "train_start.py"


def _terrain(order, start=None, grades=None, floor=None):
    ladder = {"grades": grades or {"new": 0.05, "current": 0.10, "easy": 0.03},
              "order": [{"family": f, "kind": k, "level_cap": 0} for f, k in order]}
    if floor:
        ladder["kind_floor"] = floor
    positive = [{"family": "A", "kinds_of": "continuous", "exposure": 1.0, "level_cap": 5}]
    positive += start if start is not None else [{"family": "A", "kind": "stepping_stones_low", "share": 0.05, "level_cap": 0}]
    return {"exposure_at_S": {"default": {"exposure": 0.0, "level_cap": 0}, "positive": positive}, "k_ladder": ladder}


def _shares(terrain):
    return {f"{r['family']}/{r['kind']}": r["share"] for r in terrain["exposure_at_S"]["positive"] if "share" in r}


def _pass(*kinds, reached=()):
    return {k: {"first_window_pass": True, "target_level_reached": k in reached} for k in kinds}


def test_a_grade_moves_only_on_evidence_and_one_kind_changes_per_boundary():
    terrain = _terrain([("C", "flat"), ("B", "rough"), ("C", "gap")])
    start = "A/stepping_stones_low"
    assert ladder_terrain(terrain, "S", 0)[0] == terrain
    # no evidence: the start kind is still new, so nothing opens and nothing is promoted (a missing result is a hold)
    assert _shares(ladder_terrain(terrain, "S", 4)[0]) == pytest.approx({start: 0.05})
    outcomes = [_pass(start), {}, _pass("C/flat"), _pass("C/flat", reached=("C/flat",)), {}]
    got = [_shares(ladder_terrain(terrain, "S", k, outcomes)[0]) for k in range(1, 6)]
    assert got[0] == pytest.approx({start: 0.10})                                    # first window passed -> current
    assert got[1] == pytest.approx({start: 0.10, "C/flat": 0.05})                    # nothing new left: the next kind opens
    assert got[2] == pytest.approx({start: 0.10, "C/flat": 0.10})                    # its first window passed -> current
    assert got[3] == pytest.approx({start: 0.10, "C/flat": 0.03})                    # target level reached -> easy
    assert got[4] == pytest.approx({start: 0.10, "C/flat": 0.03, "B/rough": 0.05})   # then the next opens
    receipts = ladder_terrain(terrain, "S", 5, outcomes)[1]
    assert [(r["boundary"], r["kind"], r["grade"], r["because"]) for r in receipts][:2] == [
        (1, start, "current", "first_window_pass"), (2, "C/flat", "new", "previous_kind_passed")]
    assert len({r["boundary"] for r in receipts}) == len(receipts)                    # one change per boundary
    weights = [r for r in ladder_terrain(terrain, "S", 3, outcomes)[0]["exposure_at_S"]["positive"] if "exposure" in r]
    assert weights == [terrain["exposure_at_S"]["positive"][0]]                       # the continuous weight rule is untouched


def test_a_next_kind_does_not_open_while_the_previous_one_has_not_passed_and_easy_needs_the_target_level():
    terrain = _terrain([("C", "flat"), ("B", "rough")])
    start = "A/stepping_stones_low"
    shares = _shares(ladder_terrain(terrain, "S", 3, [_pass(start), {}, {}])[0])      # C/flat opened, never passes
    assert shares == pytest.approx({start: 0.10, "C/flat": 0.05})
    shares = _shares(ladder_terrain(terrain, "S", 2, [{start: {"first_window_pass": True}}, {start: {"target_level_reached": True}}])[0])
    assert shares[start] == pytest.approx(0.03)                                       # current -> easy only on the target level
    shares = _shares(ladder_terrain(terrain, "S", 2, [{start: {"first_window_pass": True}}, {start: {"first_window_pass": True}}])[0])
    assert shares[start] == pytest.approx(0.10)                                       # a second pass is not the target level


def test_bad_outcomes_refuse_and_easy_defaults_to_the_one_floor_cell():
    terrain = _terrain([("C", "flat")])
    for bad in ([{"A/stepping_stones_low": {"first_window_pass": 1}}], [{"A/stepping_stones_low": {"pass": True}}],
                [{"A/stepping_stones_low": True}]):
        with pytest.raises(ValueError, match="outcomes"):
            ladder_terrain(terrain, "S", 1, bad)
    one = _terrain([("C", "flat")], grades={"new": 0.05, "current": 0.10}, floor=0.025)
    shares = _shares(ladder_terrain(one, "S", 3, [_pass("A/stepping_stones_low", reached=("A/stepping_stones_low",))] * 3)[0])
    assert shares["A/stepping_stones_low"] == pytest.approx(0.025)


def test_the_donor_vector_comes_from_the_continuous_share_and_a_broken_floor_refuses():
    terrain = _terrain([("C", "flat")] * 1, start=[])
    receipts = ladder_terrain(terrain, "S", 1)[1]                                      # no start kind left new: the first opens
    assert any(r["kind"] == "C/flat" and "continuous" in r["donor_vector"] for r in receipts)
    many = [("C", f"k{i}") for i in range(30)]
    with pytest.raises(ValueError, match="floor|easy-grade"):                              # 30 opened kinds cannot all fit above the floors
        ladder_terrain(_terrain(many, start=[]), "S", 120,
                       [{f"C/k{i}": {"first_window_pass": True, "target_level_reached": True} for i in range(30)}] * 120)
    with pytest.raises(ValueError, match="twice"):
        ladder_terrain(_terrain([("C", "flat"), ("C", "flat")], start=[]), "S", 6, [_pass("C/flat", reached=("C/flat",))] * 6)


def test_bad_grades_or_counts_refuse_and_no_ladder_is_unchanged():
    with pytest.raises(ValueError, match="grades"):
        ladder_terrain(_terrain([], grades={"new": 0.05, "current": 0.10, "easy": 0.07}), "S", 1)
    with pytest.raises(ValueError, match="nonnegative"):
        ladder_terrain(_terrain([]), "S", -1)
    plain = {"exposure_at_S": {"default": {}, "positive": []}}
    assert ladder_terrain(plain, "S", 5)[0] == plain


@needs_mesh
@pytest.mark.parametrize("stage,boundaries", [("E3", 13), ("E4", 16), ("E6b", 3)])
def test_the_plans_ladders_resolve_on_the_real_mesh_inside_the_floors_at_every_boundary(stage, boundaries):
    rows = {row["id"]: row for row in yaml.safe_load(PLAN.read_text(encoding="utf-8-sig"))["stages"]}
    data = np.load(REAL / "terrain_mesh.npz", allow_pickle=False)
    table = cr.build_column_table([str(v) for v in data["column_family"]])
    base = {**rows[stage]["terrain"], "kind_task": rows["E0"]["terrain"]["kind_task"]}
    kinds = [f"{r['family']}/{r['kind']}" for r in base[f"exposure_at_{stage}"]["positive"] if "share" in r]
    kinds += [f"{e['family']}/{e['kind']}" for e in base["k_ladder"]["order"]]
    everything = {kind: {"first_window_pass": True, "target_level_reached": True} for kind in kinds}
    for k in range(boundaries + 1):
        terrain, _ = ladder_terrain(base, stage, k, [everything] * k)
        exposure, _caps = ex.exposure_by_column(terrain, table, stage)
        sparse = sum(s for s in ex.column_shares(terrain, table, stage) if s)
        assert 0.0 < sparse <= 0.571 + 1e-9 and 1.0 - sparse >= 0.429 - 1e-9, (stage, k, sparse)
        assert sum(ex.env_counts(6144, exposure)[1].tolist()) == 6144


def test_train_start_reads_the_ladder_from_the_plan_it_was_started_with_at_the_resume_boundary():
    src = TRAIN_START.read_text(encoding="utf-8")
    assert "EX42Plan.load(_pre_args.ex42_plan or Path(__file__)" in src
    assert 'boundary_index=(EX42_STAGE_ZERO_RESUME_PROOF["local_update_origin"] // _interval' in src
    assert 'os.environ["EX42_LADDER_OUTCOMES"]' in src                                 # the window evidence, when a file is given
