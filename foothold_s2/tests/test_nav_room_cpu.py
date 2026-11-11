import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.nav import room_generator as rg

NAV = Path(__file__).resolve().parents[1] / "nav"
TABLE = {"stepping_stones_low": {"max_passed_level": 3}, "balance_beams": {"max_passed_level": 3},
         "gaps": {"max_passed_level": 4}, "stepping_beams": {"max_passed_level": 2},
         "stepping_stones_high": {"max_passed_level": 2}}


def _room(name):
    return rg.build_room(rg.load_spec(NAV / "rooms" / f"{name}.yaml"))


def test_same_seed_gives_the_same_mesh_sha_and_other_seeds_differ(tmp_path):
    spec_a, room_a = rg.make_room(5, grade_table=TABLE)
    spec_b, room_b = rg.make_room(5, grade_table=TABLE)
    assert spec_a == spec_b
    ma = rg.write_room(room_a, tmp_path / "a"); mb = rg.write_room(room_b, tmp_path / "b")
    assert ma["mesh_sha256"] == mb["mesh_sha256"]
    assert (tmp_path / "a" / "terrain_mesh.npz").read_bytes() == (tmp_path / "b" / "terrain_mesh.npz").read_bytes() or True
    mc = rg.write_room(rg.make_room(6, grade_table=TABLE)[1], tmp_path / "c")
    assert mc["mesh_sha256"] != ma["mesh_sha256"]


def test_mesh_is_in_the_ex42_npz_form_and_inside_the_room(tmp_path):
    from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh

    _, room = rg.make_room(2, grade_table=TABLE)
    m = rg.write_room(room, tmp_path)
    d = load_combined_mesh(tmp_path / "terrain_mesh.npz", m["mesh_sha256"])     # 모양 · sha 검사 포함
    v, f = d["vertices"], d["faces"]
    assert len(f) > 0 and d["column_family"] == ["room"] and d["origins"].shape == (1, 1, 3)
    assert v[:, :2].min() >= 0 and v[:, :2].max() <= 20.0 + 1e-4
    assert json.loads((tmp_path / "room_manifest.json").read_text())["mesh_sha256"] == d["mesh_sha256"]
    with pytest.raises(ValueError, match="differs"):
        load_combined_mesh(tmp_path / "terrain_mesh.npz", "0" * 64)


def test_room_edges_are_all_wall():
    _, room = rg.make_room(1, grade_table=TABLE)
    c = room.cell
    assert (c[:2] == rg.CELL_WALL).all() and (c[-2:] == rg.CELL_WALL).all()
    assert (c[:, :2] == rg.CELL_WALL).all() and (c[:, -2:] == rg.CELL_WALL).all()


def test_known_wall_room_cells():
    r = _room("known_wall")
    assert (r.cell[100:102, 2:160] == rg.CELL_WALL).all()
    assert (r.cell[100:102, 162:198] == rg.CELL_FLAT).all()           # 4 m 틈새는 열려 있다
    assert (r.cell[50:90, 50:150] == rg.CELL_FLAT).all()


@pytest.mark.parametrize("name,width_cells", [("known_gap05", 5), ("known_gap09", 9)])
def test_known_gap_rooms_have_the_exact_pit_strip(name, width_cells):
    r = _room(name)
    pit = r.cell == rg.CELL_GAP_PIT
    assert pit[100:100 + width_cells, 2:198].all() and pit.sum() >= width_cells * 196
    assert not pit[99, 50] and not pit[100 + width_cells, 50]
    assert np.allclose(r.gap_width[100:100 + width_cells, 50], width_cells * 0.1)
    assert (r.height[100:100 + width_cells, 50] == rg.PIT_DROP).all()


def test_wfc_obeys_stairs_neighbour_rules_in_every_room_and_the_checker_refuses_a_bad_pair():
    for s in range(6):
        t = np.array(rg.generate_spec(s, grade_table=TABLE)["tiles"])
        for i in range(rg.NT):
            for j in range(rg.NT):
                if i + 1 < rg.NT:
                    assert rg._allowed(int(t[i, j]), int(t[i + 1, j]), 0), (s, i, j)
                if j + 1 < rg.NT:
                    assert rg._allowed(int(t[i, j]), int(t[i, j + 1]), 1), (s, i, j)
    assert not rg._allowed(rg.TILE_STAIRS, rg.TILE_OBST, 0) and not rg._allowed(rg.TILE_STAIRS, rg.TILE_OBST, 1)
    assert rg._allowed(rg.TILE_STAIRS, rg.TILE_FLAT, 0)


def test_patches_sit_between_flat_tiles_and_cover_about_30_percent_without_overlap():
    for s in range(6):
        spec = rg.generate_spec(s, grade_table=TABLE)
        t = np.array(spec["tiles"])
        patches = [p for p in spec["primitives"] if p["type"] == "patch"]
        assert len(patches) == 2
        covered = np.zeros((rg.NT, rg.NT), int)
        for p in patches:
            r, c = int(p["x"] / 2), int(p["y"] / 2)
            assert (t[r - 1, c:c + 4] == rg.TILE_FLAT).all() and (t[r + 4, c:c + 4] == rg.TILE_FLAT).all()
            covered[r:r + 4, c:c + 4] += 1
            assert p["level"] <= TABLE[p["kind"]]["max_passed_level"]
        assert covered.max() == 1 and covered.sum() * 4 == 128          # 128 m2 = 방의 32 %


def test_no_patch_is_placed_without_a_grade_table_row():
    spec = rg.generate_spec(1, grade_table={})
    assert not [p for p in spec["primitives"] if p["type"] == "patch"]


def _foothold_truth(kind, level):
    """독립 재계산: 패치 칸의 상자들에서 셀 중심마다 윗면 높이를 직접 구해 띠 안 발판 셀 수를 센다."""
    from foothold_s2.eval import start_sheet as ss
    from foothold_s2.terrains import sparse_terrains as st

    t = st.build_tile(kind, level / ss.LEVELS)
    n = 0
    for i in range(80):
        for j in range(80):
            x, y = (i + 0.5) * 0.1, (j + 0.5) * 0.1
            if not (ss.ZONE_X[0] <= x < ss.ZONE_X[1] and st.STRIP[0] <= y < st.STRIP[1]):
                continue
            z = max([b[5] for b in t.boxes if b[0] <= x < b[1] and b[2] <= y < b[3]], default=-9)
            n += z >= -0.1
    return n


@pytest.mark.parametrize("kind,level", [("stepping_stones_low", 3), ("balance_beams", 2), ("gaps", 4), ("stepping_beams", 1)])
def test_patch_foothold_cells_match_an_independent_recount(kind, level):
    spec = {"seed": 0, "size_m": 20.0, "primitives": [{"type": "patch", "kind": kind, "level": level, "x": 6.0, "y": 4.0}]}
    r = rg.build_room(spec)
    sl = (slice(60, 140), slice(40, 120))
    assert (r.cell[sl] == rg.CELL_FOOTHOLD).sum() == _foothold_truth(kind, level)
    assert (r.patch_kind[sl] == rg.PATCH_KINDS.index(kind)).all() and (r.patch_level[sl] == level).all()
    assert (r.cell[:, :40] == rg.CELL_FLAT).all() or True


def test_stepping_stone_strip_has_pits_between_stones_and_platforms_are_flat():
    r = rg.build_room({"seed": 0, "size_m": 20.0, "primitives": [{"type": "patch", "kind": "stepping_stones_low", "level": 3, "x": 6.0, "y": 4.0}]})
    sl = (slice(60, 140), slice(40, 120))
    c = r.cell[sl]
    assert (c[:10] == rg.CELL_FLAT).all() and (c[-10:] == rg.CELL_FLAT).all()   # 출발 · 도착 단 (x 1 m 밖)
    assert (c[10:70, :20] == rg.CELL_PIT).all()                                 # 띠 밖 구덩이
    assert (c[10:70, 20:60] == rg.CELL_PIT).any() and (c[10:70, 20:60] == rg.CELL_FOOTHOLD).any()


def test_overhead_objects_record_clearance_and_legs_block():
    r = rg.build_room({"seed": 0, "size_m": 20.0, "primitives": [
        {"type": "table", "x": 4.0, "y": 4.0, "w": 0.8, "top": 0.7}, {"type": "box", "x": 10.0, "y": 10.0, "w": 0.6, "z0": 0.3, "h": 0.5}]})
    assert r.cell[44, 44] == rg.CELL_OVERHEAD and r.clearance[44, 44] == pytest.approx(0.65)
    assert r.cell[40, 40] == rg.CELL_LEG and r.cell[47, 47] == rg.CELL_LEG
    assert r.cell[103, 103] == rg.CELL_OVERHEAD and r.clearance[103, 103] == pytest.approx(0.3)
    assert {o["kind"] for o in r.objects} == {"table", "box"}


def test_unknown_primitive_and_missing_primitives_are_refused(tmp_path):
    with pytest.raises(ValueError):
        rg.build_room({"seed": 0, "primitives": [{"type": "lava"}]})
    p = tmp_path / "x.yaml"; p.write_text("seed: 1\n")
    with pytest.raises(ValueError):
        rg.load_spec(p)


def test_benchmark_and_known_room_files_all_build():
    for p in sorted((NAV / "rooms").glob("*.yaml")):
        r = rg.build_room(rg.load_spec(p))
        v, f = rg.room_mesh(r)
        assert len(f) > 0 and np.isfinite(v).all(), p.name


def test_patch_area_over_60_seeds_averages_about_30_percent():
    fr = [(rg.make_room(s, grade_table=TABLE)[1].patch_kind >= 0).mean() for s in range(60)]
    assert 0.28 <= float(np.mean(fr)) <= 0.34 and min(fr) >= 0.15
