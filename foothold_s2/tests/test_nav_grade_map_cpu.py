from pathlib import Path

import numpy as np
import pytest
import yaml

from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import room_generator as rg

NAV = Path(__file__).resolve().parents[1] / "nav"
TABLE = gm.load_grade_table(NAV / "grade_table_draft.yaml")


def _map(name, pose=False, table=TABLE):
    return gm.make_grade_map(rg.build_room(rg.load_spec(NAV / "rooms" / f"{name}.yaml")), table, pose)


def test_gap_grades_follow_the_crossable_width_one_to_one():
    a, b = _map("known_gap05"), _map("known_gap09")
    assert (a.grade[100:105, 2:198] == gm.SPARSE).all() and np.isinf(a.cost[0, 0])
    assert (a.cost[100:105, 50] == 3.0).all()
    assert (b.grade[100:109, 2:198] == gm.BLOCKED).all() and np.isinf(b.cost[100:109, 50]).all()
    assert (a.grade[50, 50] == gm.FREE) and a.cost[50, 50] == 1.0


def test_gap_threshold_comes_from_the_table_not_the_code():
    t = dict(TABLE, max_gap_cross_m=1.0)
    assert (_map("known_gap09", table=t).grade[100:109, 50] == gm.SPARSE).all()


def test_stepping_stone_cells_are_sparse_and_gaps_between_are_blocked():
    spec = {"seed": 0, "size_m": 20.0, "primitives": [{"type": "patch", "kind": "stepping_stones_low", "level": 3, "x": 6.0, "y": 4.0}]}
    room = rg.build_room(spec)
    g = gm.make_grade_map(room, TABLE)
    on = room.cell == rg.CELL_FOOTHOLD
    assert on.any() and (g.grade[on] == gm.SPARSE).all()
    pit = room.cell == rg.CELL_PIT
    assert (g.grade[pit] == gm.BLOCKED).all()


def test_patch_above_the_passed_level_is_blocked_inside_the_strip():
    spec = {"seed": 0, "size_m": 20.0, "primitives": [{"type": "patch", "kind": "balance_beams", "level": 9, "x": 6.0, "y": 4.0}]}
    room = rg.build_room(spec)
    g = gm.make_grade_map(room, TABLE)
    foot = room.cell == rg.CELL_FOOTHOLD
    assert foot.any() and (g.grade[foot] == gm.BLOCKED).all()
    ok = rg.build_room({**spec, "primitives": [{**spec["primitives"][0], "level": 2}]})
    assert (gm.make_grade_map(ok, TABLE).grade[ok.cell == rg.CELL_FOOTHOLD] == gm.SPARSE).all()


def test_overhead_rules_follow_the_pose_switch_and_clearances():
    spec = {"seed": 0, "size_m": 20.0, "primitives": [
        {"type": "table", "x": 4.0, "y": 4.0, "w": 0.8, "top": 0.7},              # 여유 0.65 >= 0.5 : 서서 통과
        {"type": "box", "x": 10.0, "y": 10.0, "w": 0.6, "z0": 0.3, "h": 0.5},     # 0.3 : 숙여서만
        {"type": "box", "x": 14.0, "y": 14.0, "w": 0.6, "z0": 0.2, "h": 0.5}]}    # 0.2 < 0.3 : 항상 막음
    room = rg.build_room(spec)
    off, on = gm.make_grade_map(room, TABLE, False), gm.make_grade_map(room, TABLE, True)
    for m in (off, on):
        assert m.grade[44, 44] == gm.OVERHEAD and m.cost[44, 44] == 1.0
        assert m.grade[40, 40] == gm.BLOCKED                                       # 탁자 다리
        assert m.grade[143, 143] == gm.BLOCKED
    assert off.grade[103, 103] == gm.BLOCKED
    assert on.grade[103, 103] == gm.OVERHEAD and on.cost[103, 103] == 2.0


def test_stairs_are_connected_and_rough_is_free():
    room = rg.build_room({"seed": 0, "size_m": 20.0, "primitives": [
        {"type": "stairs", "x": 4.0, "y": 4.0, "step_m": 0.15}, {"type": "rough", "x0": 10.0, "y0": 10.0, "x1": 12.0, "y1": 12.0, "seed": 1}]})
    g = gm.make_grade_map(room, TABLE)
    assert (g.grade[40:60, 40:60] == gm.CONNECTED_ROUGH).all() and g.cost[50, 50] == 1.5
    assert (g.grade[100:120, 100:120] == gm.FREE).all()


def test_save_and_load_round_trip_and_table_sha_is_recorded(tmp_path):
    g = _map("known_gap05", pose=True)
    gm.save_grade_map(g, tmp_path / "grade_map.npz")
    h = gm.load_grade_map(tmp_path / "grade_map.npz")
    assert np.array_equal(h.grade, g.grade) and np.array_equal(h.cost, g.cost) and h.pose_active
    assert h.table_sha256 == TABLE["sha256"] and len(h.table_sha256) == 64


def test_table_validation(tmp_path):
    d = yaml.safe_load((NAV / "grade_table_draft.yaml").read_text(encoding="utf-8"))
    d["crawl_clearance_m"] = 0.9
    p = tmp_path / "t.yaml"; p.write_text(yaml.safe_dump(d))
    with pytest.raises(ValueError, match="crawl"):
        gm.load_grade_table(p)
    del d["costs"]; p.write_text(yaml.safe_dump(d))
    with pytest.raises(ValueError, match="costs"):
        gm.load_grade_table(p)


def test_free_samples_are_clear_of_blocked_cells_and_in_the_main_component():
    g = _map("known_wall")
    pts = gm.sample_free_points(g, np.random.default_rng(0), 300)
    cells = (pts / g.res).astype(int)
    assert (g.grade[cells[:, 0], cells[:, 1]] == gm.FREE).all()
    from scipy import ndimage
    dist = ndimage.distance_transform_edt(g.grade != gm.BLOCKED) * g.res
    assert (dist[cells[:, 0], cells[:, 1]] > 0.3).all()
    g2 = _map("known_gap09")                                   # 방이 둘로 갈림: 표본은 한쪽에만
    c2 = (gm.sample_free_points(g2, np.random.default_rng(0), 200) / g2.res).astype(int)
    assert (c2[:, 0] < 100).all() or (c2[:, 0] > 109).all()
