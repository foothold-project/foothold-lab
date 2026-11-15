"""C-family caller contract, with only Isaac cfg containers replaced on CPU.

These tests execute real geometry and trimesh, not Kit, PhysX or Warp.
"""
import copy
from dataclasses import dataclass
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from foothold_s2.terrains import jeplo_preset as jp


@pytest.fixture
def cfg_containers(monkeypatch):
    """The minimal cfg surface; not evidence of installed Isaac compatibility."""
    @dataclass
    class SubCfg:
        function: object = None
        size: tuple = (10.0, 10.0)
        proportion: float = 1.0

    terrains = ModuleType('isaaclab.terrains')
    terrains.SubTerrainBaseCfg = SubCfg
    terrains.TerrainGeneratorCfg = SimpleNamespace
    utils = ModuleType('isaaclab.utils')
    def configclass(cls):
        # A bare dataclass ignores an unannotated override of an inherited field.
        # Isaac configclass adds annotations; model only that cfg-container surface.
        cls.__annotations__ = {'function': object, **cls.__annotations__}
        return dataclass(cls)
    utils.configclass = configclass
    monkeypatch.setitem(sys.modules, 'isaaclab', ModuleType('isaaclab'))
    monkeypatch.setitem(sys.modules, 'isaaclab.terrains', terrains)
    monkeypatch.setitem(sys.modules, 'isaaclab.utils', utils)


def test_c_family_names_are_the_seven_execution_preset_kinds():
    assert jp.KINDS == ('gap', 'flat', 'box', 'discrete_obstacles',
                        'discrete_grid', 'pyramid_stairs', 'inverted_pyramid_stairs')


@pytest.mark.parametrize('kind', jp.KINDS)
def test_measurement_factory_keeps_nine_metre_layout_and_real_geometry(kind, cfg_containers):
    pytest.importorskip('trimesh')
    generator, sub = jp.measurement_generator(kind, seed=43)
    assert generator.size == sub.size == (9.0, 9.0)
    assert (generator.num_rows, generator.num_cols) == (10, 1)
    assert generator.seed == sub.seed == 43
    assert (generator.horizontal_scale, generator.vertical_scale) == (0.08, 0.005)
    assert generator.difficulty_range == (0, 1)
    assert generator.use_cache is False
    assert generator.sub_terrains == {kind: sub}
    assert sub.proportion == 1.0
    # Same operations as ex42_manifest.measure_kind_with_kit before Kit generation.
    measured = copy.deepcopy(generator)
    measured.num_rows = measured.num_cols = 1
    measured.seed = 44
    measured.sub_terrains = {kind: copy.deepcopy(sub)}
    cfg = measured.sub_terrains[kind]
    cfg.seed = measured.seed  # TerrainGenerator._get_terrain_mesh assigns it.
    meshes, origin = cfg.function(0.91, cfg)
    tile = jp.build_heightfield(kind, 9, jp.adapter_seed(kind, 0.91, 44))
    np.testing.assert_array_equal(origin, jp.spawn_origin(tile))
    import trimesh
    vertices, faces = jp.mesh_arrays(tile)
    expected = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    np.testing.assert_array_equal(meshes[0].vertices, expected.vertices)
    np.testing.assert_array_equal(meshes[0].faces, expected.faces)
    assert generator.num_rows == 10 and sub.seed == 43


@pytest.mark.parametrize('kind', ['jeplo_gap', 'gaps', 'unknown'])
def test_measurement_factory_rejects_noncanonical_names_before_isaac_import(kind):
    with pytest.raises(ValueError, match='kind'):
        jp.measurement_generator(kind)


@pytest.mark.parametrize('seed', [None, -1, True, 2**32])
def test_measurement_factory_rejects_invalid_seed_before_isaac_import(seed):
    with pytest.raises(ValueError, match='seed'):
        jp.measurement_generator('gap', seed=seed)


@pytest.mark.parametrize('kind', jp.KINDS)
def test_actual_measurement_consumer_accepts_c_factory(kind, cfg_containers, monkeypatch):
    """Real consumer function, CPU terrain double; no Kit receipt is persisted."""
    pytest.importorskip('trimesh')
    from foothold_s2.curriculum.ex42_manifest import measure_kind_with_kit
    received = []

    class CpuTerrain:
        def __init__(self, cfg):
            received.append(cfg)
            assert (cfg.num_rows, cfg.num_cols, cfg.size) == (1, 1, (9.0, 9.0))
            sub = cfg.sub_terrains[kind]
            sub.seed = cfg.seed
            self.terrain_mesh = sub.function(0.91, sub)[0][0]

    monkeypatch.setattr(sys.modules['isaaclab.terrains'], 'TerrainGenerator', CpuTerrain, raising=False)
    generator, sub = jp.measurement_generator(kind, seed=43)
    row, elapsed = measure_kind_with_kit(
        family='C', kind=kind, preset_id='jeplo_preset_v1', generator_cfg=generator,
        subterrain_cfg=sub, original_dimensions_m={'tile_side': 9.0},
        training_dimensions_m={'tile_side': 9.0}, evaluation_dimensions_m={'tile_side': 9.0},
        evaluation_axis_directions={'tile_side': 'same'}, paper_reference='CPU test fixture only',
        physical_flag=False, source_head='a' * 40, seed=44)
    assert len(received) == 1 and received[0].seed == 44
    assert row['family'] == 'C' and row['kind'] == kind
    assert len(row['geometry_sha256']) == 64
    assert row['geometry_bounds_m'][1][:2] == [9.0, 9.0]
    assert row['measurement_provenance']['seed'] == 44
    assert elapsed >= 0
    assert generator.num_rows == 10 and sub.seed == 43
