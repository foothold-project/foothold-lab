"""Easy ladder of stepping_stones_low (start_go2_v2.set_easy_stone_low), measured on CPU from the actual boxes.

OFF is the default and must leave every tile as it was; ON may change only kind stepping_stones_low (rows 0..9):
rows 0..4 easy (gap x table, level 0 stone size, +-2 cm), row 5 = old level 0, rows 6..9 = old levels 1..4.
"""
import importlib

import numpy as np
import pytest

from foothold_s2.terrains import sparse_terrains as legacy

GAP = {0: 0.05, 1: 0.07, 2: 0.09, 3: 0.11, 4: 0.14}
HJ = 0.02


@pytest.fixture
def go2():
    mod = importlib.import_module("foothold_s2.terrains.start_go2_v2")
    mod.set_easy_stone_low(False)
    yield mod
    mod.set_easy_stone_low(False)


def _tile_arrays(go2, kind, level):
    t = go2.build_tile(kind, level / 10)
    return [np.asarray(a) for a in (t.boxes, t.origin, t.flags, t.inner, t.outer)]


def _same(a, b):
    return all(x.shape == y.shape and x.tobytes() == y.tobytes() for x, y in zip(a, b))


def _measure(boxes):
    st = boxes[3:]
    sx, sy = float(np.median(st[:, 1] - st[:, 0])), float(np.median(st[:, 3] - st[:, 2]))
    gx = float(np.median(np.diff(np.unique(np.round(st[:, 0], 9))) - sx))
    gy = float(np.median(np.diff(np.unique(np.round(st[:, 2], 9))) - sy))
    return sx, sy, gx, gy, float(np.abs(st[:, 5] - 0.0).max())


def test_default_is_off_and_matches_the_plain_generator(go2):
    assert go2.EASY_STONE_LOW_GAP_X == GAP and go2.EASY_STONE_LOW_SHIFT == 5
    for level in range(10):
        plain = go2.generate("stepping_stones", level, np.random.default_rng(5), randomness=0.0)
        none = go2.generate("stepping_stones", level, np.random.default_rng(5), randomness=0.0, gap_x=None, height_jitter=None)
        assert plain.boxes.tobytes() == none.boxes.tobytes()
        assert "gap_x_override" not in plain.params


def test_on_changes_only_the_low_stone_column_rows(go2):
    base = {(k, lv): _tile_arrays(go2, k, lv) for k in legacy.KINDS for lv in range(10)}
    go2.set_easy_stone_low(True)
    changed = {key for key, before in base.items() if not _same(before, _tile_arrays(go2, *key))}
    assert changed == {("stepping_stones_low", lv) for lv in range(10)}      # high stones, beams, gaps, flat byte equal


def test_ladder_rows_measured_from_the_built_tiles(go2):
    old = {lv: _measure(go2.build_tile("stepping_stones_low", lv / 10).boxes) for lv in range(10)}
    go2.set_easy_stone_low(True)
    new = {lv: _measure(go2.build_tile("stepping_stones_low", lv / 10).boxes) for lv in range(10)}
    sx0, sy0, gx0, gy0, _ = old[0]
    assert (sx0, sy0) == pytest.approx((0.554, 0.4425)) and gy0 == pytest.approx(0.0885)
    for r in range(5):                                      # only gap x grows; size, gap y level 0; +-2 cm
        sx, sy, gx, gy, hmax = new[r]
        assert (sx, sy, gy) == pytest.approx((sx0, sy0, gy0)) and gx == pytest.approx(GAP[r])
        assert 0.2 * HJ < hmax <= HJ + 1e-9
    sx, sy, gx, gy, hmax = new[5]                           # the old level 0 geometry, old +-5 cm
    assert (sx, sy, gx, gy) == pytest.approx(old[0][:4]) and HJ < hmax <= go2.HEIGHT_JITTER + 1e-9
    for r in range(6, 10):                                  # old levels 1..4
        assert new[r][:4] == pytest.approx(old[r - 5][:4])
        assert HJ < new[r][4] <= go2.HEIGHT_JITTER + 1e-9
    assert [round(new[r][2], 4) for r in range(4, 6)] == [0.14, round(old[0][2], 4)]      # ladder meets the old L0 gap 0.194


def test_generator_args_are_the_ladder(go2):
    assert go2.easy_stone_low_args(3) == {"level": 0, "gap_x": 0.11, "height_jitter": HJ}
    assert go2.easy_stone_low_args(5) == {"level": 0, "gap_x": None, "height_jitter": None}
    assert go2.easy_stone_low_args(9) == {"level": 4, "gap_x": None, "height_jitter": None}


def test_switch_off_again_restores_bytes(go2):
    before = _tile_arrays(go2, "stepping_stones_low", 1)
    go2.set_easy_stone_low(True)
    assert not _same(before, _tile_arrays(go2, "stepping_stones_low", 1))
    go2.set_easy_stone_low(False)
    assert _same(before, _tile_arrays(go2, "stepping_stones_low", 1))


def test_mesh_builder_flag_exists_and_defaults_off():
    build = importlib.import_module("foothold_s2.scripts.ex42_mesh_build")
    parser = build.build_parser(None)
    assert parser.parse_args(["--out", "/tmp/x"]).easy_stone_low is False
    assert parser.parse_args(["--out", "/tmp/x", "--easy_stone_low"]).easy_stone_low is True
