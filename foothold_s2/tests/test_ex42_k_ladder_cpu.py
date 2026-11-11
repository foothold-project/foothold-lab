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


def test_a_kind_is_new_then_current_then_easy_and_one_more_opens_each_boundary():
    terrain = _terrain([("C", "flat"), ("B", "rough"), ("C", "gap")])
    assert ladder_terrain(terrain, "S", 0)[0] == terrain
    got = [_shares(ladder_terrain(terrain, "S", k)[0]) for k in (1, 2, 3)]
    assert got[0] == pytest.approx({"A/stepping_stones_low": 0.10, "C/flat": 0.05})
    assert got[1] == pytest.approx({"A/stepping_stones_low": 0.03, "C/flat": 0.10, "B/rough": 0.05})
    assert got[2] == pytest.approx({"A/stepping_stones_low": 0.03, "C/flat": 0.03, "B/rough": 0.10, "C/gap": 0.05})
    weights = [r for r in ladder_terrain(terrain, "S", 3)[0]["exposure_at_S"]["positive"] if "exposure" in r]
    assert weights == [terrain["exposure_at_S"]["positive"][0]]                 # the continuous weight rule is untouched


def test_the_donor_vector_comes_from_the_continuous_share_and_a_broken_floor_refuses():
    terrain = _terrain([("C", "flat")] * 1)
    receipts = ladder_terrain(terrain, "S", 1)[1]
    assert any(r["kind"] == "C/flat" and "continuous" in r["donor_vector"] for r in receipts)
    many = [("C", f"k{i}") for i in range(30)]
    with pytest.raises(ValueError, match="floor|easy-grade"):                              # 30 opened kinds cannot all fit above the floors
        ladder_terrain(_terrain(many), "S", 30)
    with pytest.raises(ValueError, match="twice"):
        ladder_terrain(_terrain([("C", "flat"), ("C", "flat")]), "S", 2)


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
    for k in range(boundaries + 1):
        terrain, _ = ladder_terrain(base, stage, k)
        exposure, _caps = ex.exposure_by_column(terrain, table, stage)
        sparse = sum(s for s in ex.column_shares(terrain, table, stage) if s)
        assert 0.0 < sparse <= 0.571 + 1e-9 and 1.0 - sparse >= 0.429 - 1e-9, (stage, k, sparse)
        assert sum(ex.env_counts(6144, exposure)[1].tolist()) == 6144


def test_train_start_reads_the_ladder_from_the_plan_it_was_started_with_at_the_resume_boundary():
    src = TRAIN_START.read_text(encoding="utf-8")
    assert "EX42Plan.load(_pre_args.ex42_plan or Path(__file__)" in src
    assert 'boundary_index=(EX42_STAGE_ZERO_RESUME_PROOF["local_update_origin"] // _interval' in src
