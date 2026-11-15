"""Explicit CPU check against installed Isaac cfg classes and three mesh methods.

No Kit / PhysX / Warp / generator constructor. Only class_type metadata is a
placeholder. The three method bodies are compiled unchanged from the installed
source, so this checks callback, seed overwrite, centring and row placement.
Wall dimensions here are test fixtures, never an approved preset.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import types

import numpy as np
import trimesh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isaaclab-source', type=Path, required=True,
                        help='folder containing isaaclab/utils and isaaclab/terrains')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = args.isaaclab_source.resolve()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    for name, sub in [('isaaclab',''), ('isaaclab.utils','utils'), ('isaaclab.terrains','terrains')]:
        mod = types.ModuleType(name)
        mod.__path__ = [str(root/sub)]
        sys.modules[name] = mod
    from isaaclab.utils.configclass import configclass
    from isaaclab.utils.dict import dict_to_md5_hash
    sys.modules['isaaclab.utils'].configclass = configclass
    from isaaclab.terrains.sub_terrain_cfg import SubTerrainBaseCfg
    mod = types.ModuleType('isaaclab.terrains.terrain_generator')
    mod.TerrainGenerator = type('UninstantiatedTerrainGenerator',(),{})
    sys.modules[mod.__name__] = mod
    from isaaclab.terrains.terrain_generator_cfg import TerrainGeneratorCfg
    sys.modules['isaaclab.terrains'].SubTerrainBaseCfg = SubTerrainBaseCfg
    sys.modules['isaaclab.terrains'].TerrainGeneratorCfg = TerrainGeneratorCfg
    from foothold_s2.terrains import hipan_posture as hp

    source = root/'terrains/terrain_generator.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TerrainGenerator')
    names = {'_get_terrain_mesh','_add_sub_terrain','_generate_curriculum_terrains'}
    methods = [n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(methods)==3
    extracted = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')],level=0),*methods],type_ignores=[])
    namespace = {'np':np,'trimesh':trimesh,'os':os,'dict_to_md5_hash':dict_to_md5_hash}
    exec(compile(ast.fix_missing_locations(extracted),str(source),'exec'),namespace)
    CpuGrid = type('CpuGrid',(),{name:namespace[name] for name in names})
    fixtures = dict(wall_height_m=1.2,corridor_width_m=.8)
    per_kind = []
    for kind in hp.KINDS:
        g,s = hp.measurement_generator(kind,seed=43,**fixtures)
        g.validate()
        assert g.copy().sub_terrains[kind].to_dict()['kind']==kind
        meshes,origin = s.function(.91,s)
        per_kind.append(dict(kind=kind,rows=g.num_rows,origin=origin.tolist(),mesh_count=len(meshes)))

    g = hp.build_family_generator(seed=42,**fixtures)
    g.validate()
    obj = CpuGrid()
    obj.cfg, obj.np_rng = g,np.random.default_rng(g.seed)
    obj.terrain_meshes = []
    obj.terrain_origins = np.zeros((10,3,3))
    obj._generate_curriculum_terrains()
    assert len(obj.terrain_meshes)==30
    # Installed _add_sub_terrain leaves an uncentred whole grid. __init__ global
    # centring is not executed; these expectations are in that pre-centred frame.
    expected = np.array([[(8*r+1,8*c+4,0) for c in range(3)] for r in range(10)])
    np.testing.assert_allclose(obj.terrain_origins,expected,atol=1e-12)
    for row in range(10):
        assert obj.terrain_meshes[row].bounds[1,2]==[.3,.45,.6][min(row,2)]
        assert obj.terrain_meshes[10+row].bounds[1,2]==1.2
        assert np.any(np.isclose(obj.terrain_meshes[20+row].vertices[:,2],.3-.05*row/9))
    paths = [source,root/'utils/configclass.py',root/'terrains/sub_terrain_cfg.py',root/'terrains/terrain_generator_cfg.py']
    result = dict(cpu_only=True,kit_started=False,class_type_placeholder=True,
                  constructor_executed=False,methods=sorted(names),
                  source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                  fixture_wall_dimensions_m=fixtures,per_kind=per_kind,grid_tiles=30,
                  origins_shape=list(obj.terrain_origins.shape),origins=obj.terrain_origins.tolist())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS: actual cfg classes; 3 installed mesh methods; 30 tiles; no Kit/GPU')


if __name__=='__main__':
    main()
