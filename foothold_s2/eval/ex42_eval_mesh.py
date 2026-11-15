"""Separate fixed evaluation mesh adapter, never accepted by training preflight."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from foothold_s2.terrains.ex42_eval_terrains import FORMAT, KINDS
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh


def preflight(folder):
    folder=Path(folder).resolve(strict=True)
    doc=json.loads((folder/'mesh_manifest.json').read_text(encoding='utf-8'))
    if doc.get('format')!=FORMAT or doc.get('training_allowed') is not False:
        raise ValueError('requires evaluation-only manifest')
    npz=folder/'terrain_mesh.npz'
    if hashlib.sha256(npz.read_bytes()).hexdigest()!=doc.get('mesh_file_sha256'):
        raise ValueError('evaluation mesh file SHA mismatch')
    data=load_combined_mesh(npz,doc['mesh_sha256'])
    cols=doc.get('columns',[])
    names=[c.get('kind') for c in cols]
    if not cols or len(set(names))!=len(names) or any(k not in KINDS for k in names):
        raise ValueError('invalid evaluation column identity')
    if data['origins'].shape!=(1,len(cols),3) or doc.get('origins_shape')!=[1,len(cols),3]:
        raise ValueError('evaluation origin shape mismatch')
    if data['column_family']!=['V']*len(cols):
        raise ValueError('evaluation family mismatch')
    for i,c in enumerate(cols):
        if c.get('column')!=i or c.get('tile_size_m')!=[8.,8.]:
            raise ValueError('evaluation column order or carrier mismatch')
        if not np.array_equal(c.get('origin_world_m'),data['origins'][0,i]):
            raise ValueError('evaluation manifest origin mismatch')
        if c.get('reset_ranges')!={a:[0.,0.] for a in ('x','y','yaw')}:
            raise ValueError('evaluation reset must keep the declared support patch')
    return {**data,'columns':cols,'column_names':names,'manifest':doc,'mesh_npz':str(npz)}


def reset_table(record):
    return [{'family':'V','kind':c['kind'],'ranges':c['reset_ranges'],'from_declaration':True}
            for c in record['columns']]


def generator_cfg(folder):
    """Kit-only; one fixed row. Does not infer row pitch from two origins."""
    from isaaclab.utils import configclass
    record=preflight(folder)

    class EvalMeshGenerator:
        def __init__(self,cfg,device='cpu'):
            import trimesh
            data=preflight(Path(cfg.mesh_npz).parent)
            self.terrain_mesh=trimesh.Trimesh(vertices=data['vertices'].astype(float),
                faces=data['faces'].astype(np.int64),process=False)
            self.terrain_origins=data['origins']
            self.flat_patches={}

    @configclass
    class EvalMeshCfg:
        class_type: type = EvalMeshGenerator
        mesh_npz: str = record['mesh_npz']
        mesh_sha256: str = record['mesh_sha256']
        num_rows: int = 1
        num_cols: int = len(record['columns'])
        size: tuple = (8.,8.)
        tile_x_by_column: tuple = (8.,)*len(record['columns'])
        column_family: tuple = ('V',)*len(record['columns'])
        seed: int = record['manifest']['seed']
        curriculum: bool = False
        use_cache: bool = False

    return EvalMeshCfg()


def attach(env_cfg,folder):
    """Before gym.make. Evaluation script must explicitly choose this adapter."""
    from foothold_s2.terrains.ex42_column_reset import apply_column_reset
    record=preflight(folder)
    env_cfg.scene.terrain.terrain_type='generator'
    env_cfg.scene.terrain.terrain_generator=generator_cfg(folder)
    env_cfg.scene.terrain.max_init_terrain_level=0
    # Fixed evaluation geometry must never advance/replace its only row.
    for name in ('terrain_levels','terrain_levels_mixed'):
        if getattr(env_cfg.curriculum,name,None) is not None:
            setattr(env_cfg.curriculum,name,None)
    apply_column_reset(env_cfg,reset_table(record))
    return record
