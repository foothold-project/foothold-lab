"""HiPAN 원문 시험 과제 (bench_tasks): 원문 거리 구간 [5,10] · [10,20] · [20,30] m (2604.26504.txt:727) 과 구간별 과제 수. CPU only."""
from __future__ import annotations

from foothold_s2.nav import bench_tasks as bt
from foothold_s2.nav import nav_score as ns


def test_bands_are_the_paper_ones_everywhere():
    assert bt.PAPER_BANDS_M == ((5.0, 10.0), (10.0, 20.0), (20.0, 30.0)) == ns.DISTANCE_BANDS_M
    assert bt.PER_BAND == 100 and len(bt.SEEDS) == 10 and ns.SUCCESS_M == 0.2


def test_tasks_fall_in_their_band_and_record_both_distances():
    doc = bt.make_type_tasks("corridor", task_seed=0, per_band=2)
    assert [r["band"] for r in doc["tasks"]].count(0) == 2 and len(doc["tasks"]) == 6
    for r in doc["tasks"]:
        lo, hi = bt.PAPER_BANDS_M[r["band"]]
        assert lo <= r["shortest_m"] < hi and r["euclid_m"] <= r["shortest_m"] + 0.2
    assert doc["room_spec_sha256"] and doc["distance"].startswith("shortest path")


def test_each_task_has_its_own_start():
    import numpy as np
    doc = bt.make_type_tasks("room", task_seed=0, per_band=3)
    xy = np.array([r["start_xy"] for r in doc["tasks"]])
    d = np.linalg.norm(xy[:, None] - xy[None], axis=-1) + np.eye(len(xy)) * 99
    assert d.min() >= bt.START_SEP_M
