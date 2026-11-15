"""D158/CG v0.16 geometry contract, measured on CPU without Kit.

Sources in fable-25a 368d03e2:
  DESIGN-EX42-TERRAIN-draft.md:114,174-186: x*1.108, y*0.885, z unchanged.
  CURRICULUM-GATES.md:277,595: beam 0.531 -> 0.09, linear L/9.
  CURRICULUM-GATES.md:294: E slope 0.40 -> 0.70, stairs 0.23 -> 0.30.
Numbers below are independently written from those lines, not imported constants.
"""
import hashlib
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from foothold_s2.eval import start_sheet as legacy
from foothold_s2.terrains import sparse_terrains as old_tiles
from foothold_s2.terrains.ex42 import PAPER_EXT_SPECS


@pytest.fixture
def go2():
    return importlib.import_module("foothold_s2.terrains.start_go2_v2")


@pytest.mark.parametrize("level,sx,sy,gx,gy", [
    (0, 0.554, 0.4425, 0.1939, 0.0885),
    (9, 0.2216, 0.177, 0.277, 0.154875),
])
def test_stone_dimensions_and_gaps_from_actual_boxes(go2, level, sx, sy, gx, gy):
    geom = go2.generate("stepping_stones", level, np.random.default_rng(42), randomness=0)
    boxes = geom.boxes[3:]
    assert boxes[:, 1] - boxes[:, 0] == pytest.approx(sx)
    assert boxes[:, 3] - boxes[:, 2] == pytest.approx(sy)
    assert np.diff(np.unique(boxes[:, 0])) - sx == pytest.approx(gx)
    assert np.diff(np.unique(boxes[:, 2])) - sy == pytest.approx(gy)


@pytest.mark.parametrize("level,width,beam,gap,gap_width", [
    (0, 0.531, 0.554, 0.1108, 0.1108),
    (5, 0.286, 0.33855555555555555, 0.21852222222222223, 0.48013333333333336),
    (9, 0.09, 0.1662, 0.3047, 0.7756),
])
def test_beams_and_gaps_from_actual_support_faces(go2, level, width, beam, gap, gap_width):
    balance = go2.generate("balance_beams", level, np.random.default_rng(42)).boxes[3:]
    assert balance.shape == (1, 6)
    assert balance[0, 3] - balance[0, 2] == pytest.approx(width)
    assert balance[0, :2] == pytest.approx([1, 7])  # tile/frame not stretched
    bars = go2.generate("stepping_beams", level, np.random.default_rng(42)).boxes[3:]
    assert bars[:, 1] - bars[:, 0] == pytest.approx(beam)
    assert bars[1:, 0] - bars[:-1, 1] == pytest.approx(gap)
    assert bars[:, 3] - bars[:, 2] == pytest.approx(4)
    platforms = go2.generate("gaps", level, np.random.default_rng(42)).boxes[3:]
    assert len(platforms) == 4
    assert platforms[1:, 0] - platforms[:-1, 1] == pytest.approx(gap_width)


@pytest.mark.parametrize("kind", legacy.KINDS)
def test_unscaled_frame_depth_and_height_jitter(go2, kind):
    for level in (0, 5, 9):
        geom = go2.generate(kind, level, np.random.default_rng(42))
        old = legacy.generate(kind, level, np.random.default_rng(42))
        assert np.array_equal(geom.boxes[:3], old.boxes[:3])
        assert geom.depth == old.depth
        assert np.all(np.abs(geom.boxes[3:, 5]) <= 0.05)
        assert np.all(geom.boxes[3:, 0] >= 1)
        assert np.all(geom.boxes[3:, 1] <= 7 + 1e-12)
        assert np.all(geom.boxes[3:, 2] >= 0)
        assert np.all(geom.boxes[3:, 3] <= 4)


@pytest.mark.parametrize("kind", list(old_tiles.KINDS))
def test_tile_mesh_callback_and_isolated_cache(go2, kind):
    difficulty = 0.95
    tile = go2.build_tile(kind, difficulty)
    again = go2.build_tile(kind, difficulty)
    assert np.array_equal(tile.boxes, again.boxes)
    assert np.array_equal(tile.flags, again.flags)
    old_keys = dict(old_tiles.SIDE_TABLE.by_key)
    meshes, origin = go2._tile_function(difficulty, SimpleNamespace(kind=kind))
    assert np.array_equal(origin, tile.origin)
    assert len(meshes) == len(tile.boxes)
    for box, mesh in zip(tile.boxes, meshes):
        assert mesh.bounds == pytest.approx(np.array([[box[0], box[2], box[4]],
                                                     [box[1], box[3], box[5]]]))
    assert old_tiles.SIDE_TABLE.by_key == old_keys
    # Cache hit must reconstruct the Go2 preset, not silently use the absolute one.
    table = go2.SideTable()
    table.bind(9, 2, kind, difficulty)
    assert np.array_equal(table.by_cell[9, 2]["inner"], tile.inner)
    assert np.array_equal(table.by_cell[9, 2]["outer"], tile.outer)
    assert table.by_cell[9, 2]["flags_world"] == pytest.approx(tile.flags + [72, 16])


def test_randomness_contract(go2):
    for level in (0, 5, 9):
        high = go2.generate("stepping_stones", level, np.random.default_rng(42))
        low = go2.generate("stepping_stones", level, np.random.default_rng(42), randomness=0)
        assert high.params["jitter"] == pytest.approx(0.5 * level / 9)
        assert high.params["column_jitter"] == pytest.approx(0.45 * level / 9)
        assert low.params["jitter"] == low.params["column_jitter"] == 0


def test_flags_remain_on_supports(go2):
    for kind in old_tiles.KINDS:
        for difficulty in (0.05, 0.55, 0.95):
            tile = go2.build_tile(kind, difficulty)
            floor = tile.boxes[2, 5] if kind != "flat" else -1
            for x, y in tile.flags:
                supported = ((tile.boxes[:, 0] <= x) & (x <= tile.boxes[:, 1]) &
                             (tile.boxes[:, 2] <= y) & (y <= tile.boxes[:, 3]) &
                             (tile.boxes[:, 5] > floor + 0.1))
                assert supported.any(), (kind, difficulty, x, y)


def test_lazy_cfg_selects_go2_mesh_function_and_keeps_legacy_cfg(go2, monkeypatch):
    # Isaac imports are replaced only at the configuration shell. Geometry and
    # trimesh callback are real CPU functions, tested above and here.
    class BaseCfg:
        def __init__(self, **kwargs):
            self.function = type(self).function
            self.__dict__.update(kwargs)

    package, terrain, utils = (ModuleType(name) for name in
                               ("isaaclab", "isaaclab.terrains", "isaaclab.utils"))
    terrain.SubTerrainBaseCfg = BaseCfg
    utils.configclass = lambda cls: cls
    package.terrains, package.utils = terrain, utils
    for module in (package, terrain, utils):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    configs = go2.sparse_subterrains()
    assert set(configs) == set(old_tiles.KINDS)
    cfg = configs["balance_beams"]
    old_cfg = old_tiles.sparse_subterrains()["balance_beams"]
    assert cfg.preset_id == "start_go2_v2"
    assert cfg.function is go2._tile_function
    assert old_cfg.function is old_tiles._tile_function
    meshes, _ = cfg.function(0.95, cfg)
    old_meshes, _ = old_cfg.function(0.95, old_cfg)
    assert meshes[3].extents[1] == pytest.approx(0.09)
    assert old_meshes[3].extents[1] == pytest.approx(0.175)
    from foothold_s2.terrains.ex42 import paper_ext_subterrains
    for spec in PAPER_EXT_SPECS:
        setattr(terrain, spec.cfg_type, SimpleNamespace)
    e_cfg = paper_ext_subterrains({spec.kind: 1.0 for spec in PAPER_EXT_SPECS})
    assert e_cfg["slope_steep"].slope_range == (0.40, 0.70)
    assert e_cfg["stairs_high_inv"].step_height_range == (0.23, 0.30)


@pytest.mark.parametrize("proportions", [{}, {"not_a_kind": 1.0}])
def test_unknown_preset_kind_rejected_before_isaac(go2, proportions):
    with pytest.raises(ValueError, match="known sparse"):
        go2.sparse_subterrains(proportions)


def test_legacy_source_bytes_are_preserved():
    root = Path(__file__).parents[1]
    # Base 75293ad5 git blobs, not a new expected geometry generated by the fix.
    for name, digest in {
        "eval/start_sheet.py": "15e830bda3fc5ed7f106074d415b30e6ca5334887a9f1b011d980ffce018d9ec",
        "terrains/sparse_terrains.py": "5f296cf750609b83d99c46d6f730716d2f58532f436fae0dc3b776be7737b522",
    }.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_e_l0_and_l9_canonical_ranges():
    assert [s.range_value for s in PAPER_EXT_SPECS] == [
        (0.40, 0.70), (0.40, 0.70), (0.23, 0.30), (0.23, 0.30)]


@pytest.mark.parametrize("kind,level", [("unknown", 0), ("gaps", -1), ("gaps", 10), ("gaps", 0.5)])
def test_invalid_geometry_request_is_rejected(go2, kind, level):
    with pytest.raises(ValueError):
        go2.generate(kind, level, np.random.default_rng(42))
