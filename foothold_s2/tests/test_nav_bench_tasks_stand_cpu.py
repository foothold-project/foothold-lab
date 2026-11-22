"""bench_tasks_stand: same tasks, paths without posture (lead 11/22 13:39). CPU only."""
from __future__ import annotations

import json

import pytest

from foothold_s2.nav import bench_tasks as bt
from foothold_s2.nav import bench_tasks_stand as bs
from foothold_s2.nav import grade_map as gm

SRC = bt.NAV / "bench_tasks_wfc_s0_body25"


def _doc(kind, n=6):
    d = json.loads((SRC / f"tasks_{kind}.json").read_text(encoding="utf-8"))
    blocked = [t for t in d["tasks"] if t["shortest_stand_m"] is None][:2]
    d["tasks"] = (blocked + [t for t in d["tasks"] if t["shortest_stand_m"] is not None])[:n]
    return d


def test_same_tasks_stand_paths():
    table = gm.load_grade_table(bt.NAV / "grade_table_draft.yaml")
    src = _doc("room")
    out, count = bs.stand_doc(src, table)
    assert out["pose_active"] is False and len(out["tasks"]) == len(src["tasks"])
    for a, b in zip(src["tasks"], out["tasks"]):
        assert (a["id"], a["start_xy"], a["goal_xy"], a["band"]) == (b["id"], b["start_xy"], b["goal_xy"], b["band"])
        assert b["shortest_pose_m"] == a["shortest_m"] and b["train_path_m"] > 0
        if a["shortest_stand_m"] is None:
            assert b["stand_blocked"] and b["shortest_m"] == b["train_path_m"]
        else:
            assert not b["stand_blocked"] and b["shortest_m"] == a["shortest_stand_m"]
    assert count["stand_blocked"] == sum(t["shortest_stand_m"] is None for t in src["tasks"]) == 2


def test_refuses_a_table_without_posture():
    table = gm.load_grade_table(bt.NAV / "grade_table_draft.yaml")
    d = _doc("corridor", 2); d["pose_active"] = False
    with pytest.raises(ValueError):
        bs.stand_doc(d, table)
