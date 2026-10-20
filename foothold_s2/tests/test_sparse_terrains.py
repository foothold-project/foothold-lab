"""듬성한 지형 생성기 L0 (15 §8.1 · §9, 16 §2). Kit 없이 돈다."""

import numpy as np
import pytest

from foothold_s2.eval import start_sheet as ss
from foothold_s2.terrains import sparse_terrains as st

SPARSE_NAMES = ["stepping_stones_low", "stepping_stones_high", "balance_beams", "stepping_beams", "gaps"]


def test_tile_is_deterministic_in_kind_and_difficulty():
    a = st.build_tile("stepping_stones_high", 0.55)
    b = st.build_tile("stepping_stones_high", 0.55)
    c = st.build_tile("stepping_stones_high", 0.95)
    assert np.array_equal(a.boxes, b.boxes) and np.array_equal(a.flags, b.flags)
    assert np.array_equal(a.inner, b.inner)
    assert a.boxes.shape != c.boxes.shape or not np.array_equal(a.boxes, c.boxes)   # 다른 난이도 = 다른 칸


def test_low_randomness_stones_are_a_regular_grid_and_high_is_not():
    low = st.build_tile("stepping_stones_low", 0.9).boxes[3:]
    high = st.build_tile("stepping_stones_high", 0.9).boxes[3:]
    xs_low = np.unique(np.round(low[:, 0], 6))
    xs_high = np.unique(np.round(high[:, 0], 6))
    assert len(xs_low) < len(xs_high)          # 저무작위는 열이 맞다


@pytest.mark.parametrize("kind", SPARSE_NAMES)
def test_flags_sit_on_a_foothold_and_inside_the_tile(kind):
    for d in (0.05, 0.45, 0.95):
        tile = st.build_tile(kind, d)
        grid = st.height_grid(tile.boxes, res=0.05)
        floor_top = tile.boxes[2, 5]           # 구덩이 바닥 윗면 = -depth
        assert tile.flags.shape == (st.FLAG_COUNT, 2)

        for x, y in tile.flags:
            assert 0.0 < x < st.TILE[0] and 0.0 < y < st.TILE[1]
            assert grid[int(x / 0.05), int(y / 0.05)] > floor_top + 0.1, (kind, d, x, y)


def test_gap_group_tag_and_flat_has_no_edges():
    assert st.build_tile("gaps", 0.5).group == "gap"
    assert st.build_tile("balance_beams", 0.5).group == "sparse"
    flat = st.build_tile("flat", 0.5)
    assert not flat.inner.any() and not flat.outer.any()


def test_edge_mask_bands_hand_example():
    # 높이 0 의 발판 칸 하나가 -0.5 바닥 위에 있는 격자: 모서리는 발판 둘레
    boxes = np.array([(0.0, 8.0, 0.0, 8.0, -1.0, -0.5), (3.0, 3.5, 3.0, 3.5, -1.0, 0.0)])
    inner, outer = st.edge_masks(st.height_grid(boxes))
    r = st.MASK_RES
    i = int(3.0 / r)
    assert inner[i - 1, int(3.2 / r)] and inner[i, int(3.2 / r)]        # 경계 양쪽 한 칸
    assert outer[i - 2, int(3.2 / r)] and not inner[i - 2, int(3.2 / r)]
    assert outer[i + 1, int(3.2 / r)] and not outer[i - 3, int(3.2 / r)]
    assert not (inner & outer).any()


def test_stairs_like_small_drops_are_not_edges():
    boxes = np.array([(0.0, 8.0, 0.0, 8.0, -1.0, 0.0), (3.0, 4.0, 0.0, 8.0, -1.0, 0.15)])
    inner, outer = st.edge_masks(st.height_grid(boxes))
    assert not inner.any() and not outer.any()


def test_real_tiles_have_edges_except_flat():
    for kind in SPARSE_NAMES:
        t = st.build_tile(kind, 0.5)
        assert t.inner.any() and t.outer.any(), kind


def test_world_transform_matches_isaac_formula():
    # Isaac: 칸 중심으로 -size/2 옮기고 (row+0.5, col+0.5) * size 만큼 이동 = tile_xy + (row * 8, col * 8)
    xy = np.array([[0.5, 4.0], [7.0, 1.0]])
    w = st.tile_to_world(xy, row=3, col=5)
    assert np.allclose(w, xy + np.array([24.0, 40.0]))


def test_side_table_without_cache_and_after_save_load_give_same_world_coordinates(tmp_path):
    cells = [(0, 0, "gaps", 0.05), (2, 3, "stepping_stones_low", 0.25), (9, 4, "stepping_beams", 0.95)]
    fresh = st.SideTable()

    for r, c, kind, d in cells:
        fresh.record(kind, d, st.build_tile(kind, d))
        fresh.bind(r, c, kind, d)

    path = tmp_path / "side.npz"
    fresh.save(path)
    restored = st.SideTable.load(path)
    # 캐시 적중 상황: mesh 만 복원되고 생성기 함수가 안 불려도 (종류, 난이도) 로 다시 지으면 같다
    rebuilt = st.SideTable()

    for r, c, kind, d in cells:
        rebuilt.bind(r, c, kind, d)

    for r, c, _, _ in cells:
        for other in (restored, rebuilt):
            a, b = fresh.by_cell[(r, c)], other.by_cell[(r, c)]
            assert np.allclose(a["flags_world"], b["flags_world"], atol=1e-6)
            assert np.allclose(a["origin_world"], b["origin_world"], atol=1e-6)
            assert np.array_equal(a["inner"], b["inner"]) and np.array_equal(a["outer"], b["outer"])
            assert a["group"] == b["group"] and a["kind"] == b["kind"]


def test_flags_world_follow_the_cell_when_an_env_is_moved_to_another_cell():
    t = SIDE = st.SideTable()
    t.bind(1, 2, "balance_beams", 0.5)
    t.bind(4, 7, "balance_beams", 0.5)
    a, b = SIDE.by_cell[(1, 2)]["flags_world"], SIDE.by_cell[(4, 7)]["flags_world"]
    assert np.allclose(b - a, [24.0, 40.0])
    assert not np.allclose(a, b)


def test_start_sheet_defaults_unchanged_by_randomness_hook():
    rng1, rng2 = np.random.default_rng(3), np.random.default_rng(3)
    g1 = ss.generate("stepping_stones", 5, rng1)
    g2 = ss.generate("stepping_stones", 5, rng2, randomness=5 / 9)
    assert np.array_equal(g1.boxes, g2.boxes)


def test_high_randomness_stones_scale_with_level_and_low_is_always_zero():
    assert st.KINDS["stepping_stones_low"][1] == 0.0
    assert st.KINDS["stepping_stones_high"][1] is None                       # 레벨 비례 L/9

    for L in (0, 3, 6, 9):                       # 시험지 쪽 식: r = L / 9 -> 돌 ±0.5 x r, 열 ±0.45 x r (레벨 9 = START 최대값)
        g = ss.generate("stepping_stones", L, np.random.default_rng(1))
        assert g.params["jitter"] == pytest.approx(0.5 * L / 9.0)
        assert g.params["column_jitter"] == pytest.approx(0.45 * L / 9.0)

    for kind, randomness in (("stepping_stones_high", None), ("stepping_stones_low", 0.0)):
        for L in (0, 4, 9):
            d = (L + 0.5) / 10.0
            rng = np.random.default_rng(st.seed_of(kind, d))
            geom = ss.generate("stepping_stones", L, rng) if randomness is None                 else ss.generate("stepping_stones", L, rng, randomness=randomness)
            ref = np.array([(x0, x1, y0 + st.STRIP[0], y1 + st.STRIP[0], z0, z1)
                            for x0, x1, y0, y1, z0, z1 in geom.boxes[3:]])
            assert np.allclose(st.build_tile(kind, d).boxes[3:], ref), (kind, L)
