"""Easy first rows of stepping_stones_low (start_go2_v2.set_easy_stone_low), measured on CPU from the actual boxes.

OFF is the default and must leave every tile as it was; ON may change only kind stepping_stones_low at levels 0 to 4.
"""
import importlib

import numpy as np
import pytest

from foothold_s2.terrains import sparse_terrains as legacy

TABLE = {0: 0.05, 1: 0.07, 2: 0.09, 3: 0.11, 4: 0.14}
HJ = 0.02


@pytest.fixture
def go2():
    mod = importlib.import_module("foothold_s2.terrains.start_go2_v2")
    mod.set_easy_stone_low(False)
    yield mod
    mod.set_easy_stone_low(False)


def _tile_arrays(go2, kind, level):
    t = go2.build_tile(kind, (level + 0.5) / 10)
    return [np.asarray(a) for a in (t.boxes, t.origin, t.flags, t.inner, t.outer)]


def _same(a, b):
    return all(x.shape == y.shape and x.tobytes() == y.tobytes() for x, y in zip(a, b))


def test_default_is_off_and_matches_the_plain_generator(go2):
    assert go2.EASY_STONE_LOW_GAP_X == TABLE
    for level in range(10):
        plain = go2.generate("stepping_stones", level, np.random.default_rng(5), randomness=0.0)
        none = go2.generate("stepping_stones", level, np.random.default_rng(5), randomness=0.0, gap_x=None)
        assert plain.boxes.tobytes() == none.boxes.tobytes()
        assert "gap_x_override" not in plain.params
        off = go2.build_tile("stepping_stones_low", (level + 0.5) / 10)
        assert off.boxes.shape[0] > 3        # a real tile, gap table not consulted while off


def test_on_changes_only_low_stones_rows_0_to_4(go2):
    base = {(k, lv): _tile_arrays(go2, k, lv) for k in legacy.KINDS for lv in range(10)}
    go2.set_easy_stone_low(True)
    changed = set()
    for (kind, level), before in base.items():
        if not _same(before, _tile_arrays(go2, kind, level)):
            changed.add((kind, level))
    assert changed == {("stepping_stones_low", lv) for lv in TABLE}      # high stones, beams, gaps, flat, rows 3+ byte equal


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_on_sets_gap_x_and_keeps_stone_size_and_gap_y(go2, level):
    off = go2.generate("stepping_stones", level, np.random.default_rng(7), randomness=0.0)
    on = go2.generate("stepping_stones", level, np.random.default_rng(7), randomness=0.0, gap_x=TABLE[level],
                      height_jitter=HJ)
    for geom in (off, on):
        b = geom.boxes[3:]
        assert b[:, 1] - b[:, 0] == pytest.approx(geom.params["stone_x"])
    assert on.params["stone_x"] == off.params["stone_x"] and on.params["stone_y"] == off.params["stone_y"]
    assert on.params["gap_y"] == off.params["gap_y"]
    b = on.boxes[3:]
    gaps = np.diff(np.unique(np.round(b[:, 0], 9))) - on.params["stone_x"]
    assert gaps == pytest.approx(TABLE[level])
    assert on.params["gap_x_override"] == TABLE[level]
    tops = on.boxes[3:, 5] - go2.PLATFORM_Z
    assert np.abs(tops).max() <= HJ + 1e-9 and np.abs(tops).max() > 0.2 * HJ            # +-2 cm, still shaken
    assert np.abs(off.boxes[3:, 5] - go2.PLATFORM_Z).max() > HJ                        # the old +-5 cm is wider
    assert np.diff(np.unique(np.round(b[:, 2], 9))) - on.params["stone_y"] == pytest.approx(on.params["gap_y"])


def test_built_tiles_carry_the_easy_values_only_on_easy_rows(go2):
    go2.set_easy_stone_low(True)
    for level in range(10):
        p = go2.generate("stepping_stones", level, np.random.default_rng(1), randomness=0.0).params
        assert "gap_x_override" not in p and "height_jitter_override" not in p
        t = go2.build_tile("stepping_stones_low", level / 10)
        tops = t.boxes[3:, 5] - go2.PLATFORM_Z
        assert (np.abs(tops).max() <= HJ + 1e-9) == (level in TABLE)
        if level in TABLE:
            xs = np.unique(np.round(t.boxes[3:, 0], 9))
            stone_x = t.boxes[3, 1] - t.boxes[3, 0]
            assert np.diff(xs) - stone_x == pytest.approx(TABLE[level])


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
