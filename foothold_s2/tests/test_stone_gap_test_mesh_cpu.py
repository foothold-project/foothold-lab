"""Known answers for the easy-stone test mesh script (no mesh file needed)."""
import numpy as np
import pytest

from foothold_s2.scripts import ex42_stone_gap_test_mesh as tm
from foothold_s2.terrains import start_go2_v2 as v2


def test_changed_rows_are_the_generators_easy_rows():
    assert list(tm.ROWS_CHANGED) == sorted(v2.EASY_STONE_LOW_GAP_X)


def test_measure_tile_reads_gap_size_and_height_from_stone_boxes():
    z = v2.PLATFORM_Z
    # (label, x0, x1, y0, y1, z0, z1) in world coordinates, tile corner (10, 20); stone 0.5 x 0.4, gaps 0.1 (x) 0.2 (y)
    stones = [(i, 10 + x, 10 + x + .5, 20 + y, 20 + y + .4, -1.0, z + h)
              for i, (x, y, h) in enumerate([(0, 0, .01), (.6, 0, -.02), (0, .6, .0), (.6, .6, .02)])]
    m = tm.measure_tile(stones, 10.0, 20.0)
    assert m["stone_x_m"] == pytest.approx(.5) and m["stone_y_m"] == pytest.approx(.4)
    assert m["gap_x_m"] == pytest.approx(.1) and m["gap_y_m"] == pytest.approx(.2)
    assert m["height_jitter_max_abs_m"] == pytest.approx(.02) and m["stones"] == 4


@pytest.mark.parametrize("row", [0, 1, 2, 3, 4])
def test_new_tile_off_is_the_old_generator_and_on_is_the_easy_one(row):
    depth = 0.4
    off = tm.new_tile_boxes(row, False, depth, "k")[3:]
    on = tm.new_tile_boxes(row, True, depth, "k")[3:]
    sx = off[0, 1] - off[0, 0]
    gap = lambda b: np.median(np.diff(np.unique(np.round(b[:, 0], 9))) - sx)
    assert gap(on) == pytest.approx(v2.EASY_STONE_LOW_GAP_X[row])
    assert gap(off) == pytest.approx(v2._lerp(v2.STONE_GAP_X, row))
    assert np.abs(on[:, 5] - v2.PLATFORM_Z).max() <= v2.EASY_STONE_LOW_HEIGHT_JITTER + 1e-9
    assert v2.build_tile("stepping_stones_low", row / 10).boxes.shape[0] > 3
    assert v2._EASY["stone_low"] is False           # building a test tile never leaves the switch on
