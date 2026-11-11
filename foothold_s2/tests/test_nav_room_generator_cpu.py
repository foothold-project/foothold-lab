import numpy as np
import pytest

from foothold_s2.nav import room_generator as rg

SEEDS = range(6)


@pytest.fixture(scope="module")
def rooms():
    return {s: rg.make_room(s) for s in SEEDS}


def _tile(room, i, j):
    return room.grade[i * rg.TILE:(i + 1) * rg.TILE, j * rg.TILE:(j + 1) * rg.TILE], \
        room.height[i * rg.TILE:(i + 1) * rg.TILE, j * rg.TILE:(j + 1) * rg.TILE]


def test_shapes_walls_and_determinism(rooms):
    r = rooms[0]
    assert r.grade.shape == (200, 200) and r.height.shape == (200, 200) and r.tiles.shape == (10, 10)
    assert (r.grade[:2] == rg.BLOCKED).all() and (r.grade[-2:] == rg.BLOCKED).all()
    assert (r.grade[:, :2] == rg.BLOCKED).all() and (r.grade[:, -2:] == rg.BLOCKED).all()
    again = rg.make_room(0)
    assert np.array_equal(again.grade, r.grade) and np.array_equal(again.height, r.height)
    assert not np.array_equal(rooms[1].tiles, r.tiles)


def test_wfc_neighbours_obey_the_patch_rules_in_every_room(rooms):
    for r in rooms.values():
        t = r.tiles
        for i in range(rg.NT):
            for j in range(rg.NT):
                for di, dj, ax in ((1, 0, 0), (0, 1, 1)):
                    if i + di < rg.NT and j + dj < rg.NT:
                        assert rg._allowed(int(t[i, j]), int(t[i + di, j + dj]), ax), (r.seed, i, j)


def test_the_rule_check_itself_refuses_a_patch_next_to_a_patch_along_x():
    assert not rg._allowed(rg.GAP, rg.STAIRS, 0)
    assert not rg._allowed(rg.BEAM, rg.OBST, 1)
    assert rg._allowed(rg.GAP, rg.FLAT, 0) and rg._allowed(rg.LOG, rg.LOG, 1)


def _paint(kind, cfg=None, seed=0):
    cfg = cfg or rg.RoomConfig()
    h = np.zeros((rg.N, rg.N)); g = np.zeros((rg.N, rg.N), np.uint8); c = np.full((rg.N, rg.N), np.inf)
    rg._paint_tile(kind, cfg, np.random.default_rng(seed), h, g, c, [], 0, 0)
    return g[:20, :20], h[:20, :20], c[:20, :20]


def test_gap_cells_are_sparse_when_crossable_and_blocked_when_too_wide():
    g, h, _ = _paint(rg.GAP, rg.RoomConfig(gap_width_m=0.5))
    gap = h < -0.5
    assert gap.sum() == 5 * 20 and (g[gap] == rg.SPARSE).all() and (g[~gap] == rg.FREE).all()
    g, h, _ = _paint(rg.GAP, rg.RoomConfig(gap_width_m=0.9))
    gap = h < -0.5
    assert gap.sum() == 9 * 20 and (g[gap] == rg.BLOCKED).all()


def test_stepping_stones_are_one_to_one_with_sparse_cells():
    g, h, _ = _paint(rg.STONES)
    on = h == 0.0
    assert on.any() and (g[on] == rg.SPARSE).all() and (g[~on] == rg.BLOCKED).all()
    assert (h[~on] == rg.FLOOR_DROP).all()


def test_beam_and_log_strip_widths_and_blocked_surroundings():
    for kind, w in ((rg.BEAM, 4), (rg.LOG, 2)):
        g, h, _ = _paint(kind)
        strip = g == rg.SPARSE
        assert strip.sum() == w * 20 and (g[~strip] == rg.BLOCKED).all()
        assert (np.nonzero(strip.any(0))[0].size) == w


def test_stairs_rise_by_the_step_height_and_return_to_flat_at_both_ends():
    g, h, _ = _paint(rg.STAIRS)
    col = h[:, 0]
    assert col[0] == 0 and col[-1] == 0 and np.isclose(col.max(), 0.30)
    assert np.allclose(np.diff(np.unique(col)), 0.15) and (g == rg.ROUGH_CONNECTED).all()


def test_overhead_below_body_height_blocks_and_above_leaves_it_passable():
    for z, expect in ((0.3, rg.BLOCKED), (0.9, rg.OVERHEAD)):
        G = np.zeros((20, 20), np.uint8); C = np.full((20, 20), np.inf)
        rg._overhead(G, C, (slice(5, 10), slice(5, 10)), z, rg.RoomConfig())
        assert (G[5:10, 5:10] == expect).all() and (C[5:10, 5:10] == z).all() and G.sum() == expect * 25


def test_every_room_has_a_large_connected_passable_area_and_free_samples_are_clear(rooms):
    for r in rooms.values():
        assert rg.largest_component(rg.passable(r.grade)) / r.grade.size >= 0.35
        pts = rg.sample_free_points(r, np.random.default_rng(1), 200)
        cells = (pts / rg.RES).astype(int)
        assert (r.grade[cells[:, 0], cells[:, 1]] != rg.BLOCKED).all()
        near = r.grade[np.clip(cells[:, 0] - 3, 0, 199), cells[:, 1]]
        assert (near != rg.BLOCKED).all()


def test_unreachable_threshold_raises():
    with pytest.raises(RuntimeError):
        rg.make_room(0, rg.RoomConfig(min_free_fraction=1.01, max_tries=2))


def test_obstacle_objects_are_recorded_with_their_grade_effect():
    cfg = rg.RoomConfig(p_wall=1.0, p_table=1.0, p_box=1.0, weights=(0, 0, 1, 0, 0, 0, 0, 0))
    h = np.zeros((rg.N, rg.N)); g = np.zeros((rg.N, rg.N), np.uint8); c = np.full((rg.N, rg.N), np.inf); objs = []
    rg._paint_tile(rg.OBST, cfg, np.random.default_rng(3), h, g, c, objs, 0, 0)
    assert [o["kind"] for o in objs] == ["wall", "table", "box"]
    wall = objs[0]
    assert (g[int(wall["x0"] / rg.RES):int(wall["x1"] / rg.RES), int(wall["y0"] / rg.RES):int(wall["y1"] / rg.RES)] == rg.BLOCKED).all()
    assert (g == rg.BLOCKED).any() and np.isfinite(c).any()
