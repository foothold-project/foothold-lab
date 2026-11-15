"""Known-answer family-D geometry and cfg contracts; no Kit or GPU."""
import copy
from dataclasses import dataclass
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from foothold_s2.terrains import hipan_posture as hp


def _inside(boxes, xyz):
    x, y, z = xyz
    return any(x0 < x < x1 and y0 < y < y1 and z0 < z < z1
               for x0, x1, y0, y1, z0, z1 in boxes)


@pytest.mark.parametrize('level,height', [(0, .30), (1, .45), (2, .60)])
def test_ledge_three_canonical_heights_and_entry_floor(level, height):
    t = hp.build_tile('high_ledge', level, seed=42)
    assert t.boxes.shape == (2, 6)
    assert t.dimensions['ledge_height_m'] == height
    assert t.boxes[1].tolist() == [4., 8., 0., 8., 0., height]
    assert t.origin.tolist() == [1., 4., 0.]
    assert not _inside(t.boxes, (1., 4., .01))
    assert _inside(t.boxes, (6., 4., height / 2))


@pytest.mark.parametrize('level,clearance', [(0, .30), (9, .25)])
def test_crawl_has_real_free_volume_below_the_ceiling(level, clearance):
    t = hp.build_tile('crawl', level, seed=42)
    assert t.boxes[1, 4] == clearance  # underside, not top of a filled block
    assert t.boxes[1, 5] == pytest.approx(clearance + .10)
    assert not _inside(t.boxes, (4., 4., clearance / 2))
    assert _inside(t.boxes, (4., 4., clearance + .05))
    assert not _inside(t.boxes, (1., 4., clearance + .05))
    assert t.dimensions['ceiling_clearance_m'] == clearance


def test_crawl_clearance_decreases_monotonically_between_fixed_endpoints():
    heights = [hp.build_tile('crawl', l, seed=42).dimensions['ceiling_clearance_m'] for l in range(10)]
    assert np.all(np.diff(heights) < 0)
    assert heights[0] == .30 and heights[-1] == .25


def test_wall_explicit_fixture_dimensions_and_side_bypass():
    # Test inputs, not a published HiPAN preset or approved training dimensions.
    t = hp.build_tile('wall', 0, seed=42, wall_height_m=1.20, corridor_width_m=.80)
    assert t.boxes[1].tolist() == pytest.approx([3.95, 4.05, 0., 7.20, 0., 1.20])
    assert _inside(t.boxes, (4., 4., .50))
    assert not _inside(t.boxes, (4., 7.60, .50))
    assert t.dimensions['wall_height_m'] == 1.20
    assert t.dimensions['corridor_width_m'] == .80


@pytest.mark.parametrize('kwargs', [{}, {'wall_height_m':1.2}, {'corridor_width_m':.8}])
def test_wall_has_no_invented_default_dimensions(kwargs):
    with pytest.raises(ValueError, match='wall_height_m|corridor_width_m'):
        hp.build_tile('wall', 0, seed=42, **kwargs)


@pytest.mark.parametrize('kind,level', [('unknown',0), ('high_ledge',3), ('wall',1),
                                       ('crawl',10), ('crawl',-1), ('crawl',.5), ('crawl',True)])
def test_invalid_kind_or_level_rejected(kind, level):
    with pytest.raises(ValueError):
        hp.build_tile(kind, level, seed=42, wall_height_m=1.2, corridor_width_m=.8)


@pytest.mark.parametrize('kwargs', [
    {'wall_height_m':float('nan'), 'corridor_width_m':.8},
    {'wall_height_m':1.2, 'corridor_width_m':float('inf')},
    {'wall_height_m':1.2, 'corridor_width_m':0},
    {'wall_height_m':1.2, 'corridor_width_m':4.1},
    {'wall_height_m':True, 'corridor_width_m':.8},
    {'wall_height_m':1.2, 'corridor_width_m':.8, 'wall_thickness_m':4.1},
])
def test_wall_nonfinite_or_blocked_layout_rejected(kwargs):
    with pytest.raises(ValueError):
        hp.build_tile('wall', 0, seed=42, **kwargs)


@pytest.mark.parametrize('seed', [None, True, -1, 2**32])
def test_explicit_seed_required(seed):
    with pytest.raises(ValueError, match='seed'):
        hp.build_tile('crawl', 0, seed=seed)


def test_global_random_state_is_unchanged():
    np.random.seed(17)
    before = np.random.get_state()
    hp.build_tile('crawl', 3, seed=42)
    after = np.random.get_state()
    np.testing.assert_array_equal(before[1], after[1])
    assert before[2:] == after[2:]


@pytest.mark.parametrize('kind,level', [('high_ledge',2), ('wall',0), ('crawl',9)])
def test_box_mesh_is_watertight_with_correct_volume(kind, level):
    pytest.importorskip('trimesh')
    tile = hp.build_tile(kind, level, seed=42, wall_height_m=1.2, corridor_width_m=.8)
    meshes = hp.meshes_for(tile)
    assert len(meshes) == len(tile.boxes)
    for mesh, (x0,x1,y0,y1,z0,z1) in zip(meshes, tile.boxes):
        assert mesh.is_watertight and mesh.is_winding_consistent
        assert mesh.volume == pytest.approx((x1-x0)*(y1-y0)*(z1-z0))
        np.testing.assert_allclose(mesh.bounds, [[x0,y0,z0],[x1,y1,z1]], atol=1e-12)


@pytest.fixture
def cfg_containers(monkeypatch):
    @dataclass
    class SubCfg:
        function: object = None
        size: tuple = (10., 10.)
        proportion: float = 1.
    terrains = ModuleType('isaaclab.terrains')
    terrains.SubTerrainBaseCfg = SubCfg
    terrains.TerrainGeneratorCfg = SimpleNamespace
    utils = ModuleType('isaaclab.utils')
    def configclass(cls):
        cls.__annotations__ = {'function':object, **cls.__annotations__}
        return dataclass(cls)
    utils.configclass = configclass
    monkeypatch.setitem(sys.modules,'isaaclab',ModuleType('isaaclab'))
    monkeypatch.setitem(sys.modules,'isaaclab.terrains',terrains)
    monkeypatch.setitem(sys.modules,'isaaclab.utils',utils)


@pytest.mark.parametrize('kind,rows', [('high_ledge',3), ('wall',1), ('crawl',10)])
def test_measurement_pair_preserves_cfg_and_kind_levels(kind, rows, cfg_containers):
    pytest.importorskip('trimesh')
    g, s = hp.measurement_generator(kind, seed=43, wall_height_m=1.2, corridor_width_m=.8)
    assert (g.size,g.num_rows,g.num_cols)==((8.,8.),rows,1)
    assert g.sub_terrains == {kind:s}
    assert s.function is hp.tile_function and s.seed == 43
    measured = copy.deepcopy(g)
    measured.num_rows = measured.num_cols = 1
    meshes, origin = measured.sub_terrains[kind].function(1., measured.sub_terrains[kind])
    assert len(meshes)==2 and np.isfinite(origin).all()
    assert g.num_rows==rows


@pytest.mark.parametrize('difficulty,level', [(0.,0),(.3334,1),(.6667,2),(1.,2)])
def test_ledge_adapter_maps_three_rows_to_three_levels(difficulty,level,cfg_containers):
    pytest.importorskip('trimesh')
    _,s=hp.measurement_generator('high_ledge',seed=42)
    meshes,_=s.function(difficulty,s)
    assert meshes[1].bounds[1,2]==[.30,.45,.60][level]


def test_missing_wall_values_rejected_before_isaac_import():
    with pytest.raises(ValueError,match='wall_height_m'):
        hp.measurement_generator('wall',seed=42,wall_height_m=None)


@pytest.mark.parametrize('difficulty', [float('nan'),-.1,1.1])
def test_adapter_rejects_out_of_domain_difficulty(difficulty):
    with pytest.raises(ValueError,match='difficulty'):
        hp.tile_function(difficulty,SimpleNamespace(kind='crawl'))


def _first_triangle_hit(meshes, start, direction):
    """Independent two-sided Moller-Trumbore ray, no Warp/Kit/rtree."""
    triangles = np.concatenate([m.triangles for m in meshes])
    edge1, edge2 = triangles[:,1]-triangles[:,0], triangles[:,2]-triangles[:,0]
    p = np.cross(np.broadcast_to(direction, edge2.shape), edge2)
    det = np.einsum('ij,ij->i',edge1,p)
    good = np.abs(det)>1e-10
    inv = np.zeros_like(det)
    inv[good] = 1/det[good]
    tvec = np.asarray(start)-triangles[:,0]
    u = np.einsum('ij,ij->i',tvec,p)*inv
    q = np.cross(tvec,edge1)
    v = q @ np.asarray(direction)*inv
    t = np.einsum('ij,ij->i',edge2,q)*inv
    good &= (u>=-1e-10)&(v>=-1e-10)&(u+v<=1+1e-10)&(t>1e-10)
    return float(t[good].min()) if np.any(good) else float('inf')


def test_triangle_ray_sees_crawl_air_floor_underside_and_top_separately():
    pytest.importorskip('trimesh')
    meshes = hp.meshes_for(hp.build_tile('crawl',9,seed=42))
    # The upper scan hits the roof TOP. This documents Q12, not a new gate.
    assert _first_triangle_hit(meshes,[4,4,20],[0,0,-1]) == pytest.approx(19.65)
    assert _first_triangle_hit(meshes,[4,4,.1],[0,0,1]) == pytest.approx(.15)
    assert _first_triangle_hit(meshes,[4,4,.1],[0,0,-1]) == pytest.approx(.1)
    assert np.isinf(_first_triangle_hit(meshes,[1,4,.2],[1,0,0]))
    assert _first_triangle_hit(meshes,[1,4,.3],[1,0,0]) == pytest.approx(1.)


def test_full_family_ten_storage_rows_do_not_add_ledge_heights(cfg_containers):
    pytest.importorskip('trimesh')
    g = hp.build_family_generator(seed=42,wall_height_m=1.2,corridor_width_m=.8)
    assert (g.num_rows,g.num_cols,g.border_width)==(10,3,0.)
    assert list(g.sub_terrains)==list(hp.KINDS)
    assert sum(s.proportion for s in g.sub_terrains.values())==pytest.approx(1.)
    for row in range(10):
        for jitter in (.001,.999):
            d=(row+jitter)/10
            ledge,_=g.sub_terrains['high_ledge'].function(d,g.sub_terrains['high_ledge'])
            wall,_=g.sub_terrains['wall'].function(d,g.sub_terrains['wall'])
            crawl,_=g.sub_terrains['crawl'].function(d,g.sub_terrains['crawl'])
            assert ledge[1].bounds[1,2]==[.30,.45,.60][min(row,2)]
            assert wall[1].bounds[1,2]==1.2
            assert crawl[1].bounds[0,2]==pytest.approx(.30-.05*row/9)


def test_family_has_no_invented_wall_preset():
    with pytest.raises(ValueError,match='wall_height_m'):
        hp.build_family_generator(seed=42,wall_height_m=None)


def test_go2_inferred_preset_is_explicitly_distinct_from_paper_values(cfg_containers):
    assert hp.PRESET_ID == 'posture_go2_v1'
    assert hp.PRESET_SOURCE == 'project_inference_20261111'
    assert hp.WALL_HEIGHT_M == 1.2 and hp.CORRIDOR_WIDTH_M == .8
    g,sub = hp.measurement_generator('wall',seed=42)
    assert (sub.wall_height_m,sub.corridor_width_m)==(1.2,.8)
    family = hp.build_family_generator(seed=42)
    assert (family.num_rows,family.num_cols)==(10,3)


@pytest.mark.parametrize('kind', hp.KINDS)
def test_actual_measurement_consumer_accepts_d_factory(kind,cfg_containers,monkeypatch):
    trimesh = pytest.importorskip('trimesh')
    from foothold_s2.curriculum.ex42_manifest import measure_kind_with_kit
    received = []

    class CpuTerrain:
        def __init__(self,cfg):
            received.append(cfg)
            assert (cfg.num_rows,cfg.num_cols,cfg.size)==(1,1,(8.,8.))
            sub = cfg.sub_terrains[kind]
            sub.seed = cfg.seed
            self.terrain_mesh = trimesh.util.concatenate(sub.function(.91,sub)[0])

    monkeypatch.setattr(sys.modules['isaaclab.terrains'],'TerrainGenerator',CpuTerrain,raising=False)
    g,s = hp.measurement_generator(kind,seed=43)
    row,elapsed = measure_kind_with_kit(
        family='D',kind=kind,preset_id=hp.PRESET_ID,generator_cfg=g,subterrain_cfg=s,
        original_dimensions_m={'tile_side':8.},training_dimensions_m={'tile_side':8.},
        evaluation_dimensions_m={'tile_side':8.},evaluation_axis_directions={'tile_side':'same'},
        paper_reference='CPU contract fixture only, not a paper dimension',physical_flag=False,
        source_head='a'*40,seed=44)
    assert row['family']=='D' and row['kind']==kind
    assert len(row['geometry_sha256'])==64
    assert row['geometry_bounds_m'][1][:2]==[8.,8.]
    assert received[0].seed==44 and elapsed>=0
    assert s.seed==43  # caller copy was private
