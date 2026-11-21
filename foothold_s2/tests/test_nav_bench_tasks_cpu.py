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


def test_wfc_rooms_are_made_by_the_generator_and_pass_its_acceptance():
    for kind in bt.TYPES:
        spec = bt.wfc_spec(kind, 0)
        assert spec["bench"]["type"] == kind and spec["primitives"]
    assert bt.room_path("room", "wfc", 0).name == "bench_wfc_room_s0.yaml" and bt.room_path("room").name == "bench_room.yaml"
    assert sum(p["type"] in ("table", "box") for p in bt.wfc_spec("room", 0)["primitives"]) >= bt.WFC_ROOM_CENTER[2]


def test_low_ceiling_slabs_make_posture_matter_in_room_and_complex():
    from foothold_s2.nav import grade_map as gm
    from foothold_s2.nav import room_generator as rg
    t = gm.load_grade_table(bt.NAV / "grade_table_draft.yaml")
    for kind in ("room", "complex1", "complex2"):
        r = rg.build_room(bt.wfc_spec(kind, 0))
        stand = (gm.make_grade_map(r, t, pose_active=False).grade == gm.BLOCKED).mean()
        crawl = (gm.make_grade_map(r, t, pose_active=True).grade == gm.BLOCKED).mean()
        assert stand - crawl > 0.03, kind                     # was 0.002 before the slabs (lead 19:34)
