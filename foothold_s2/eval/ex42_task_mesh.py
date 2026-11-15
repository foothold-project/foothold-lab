"""Select saved triangles by family/kind/level and give each trial its own tile.

No regeneration, training-mesh mutation, or arbitrary per-env column indexing.
The explicit flat reference substitutes only geometry and ground z; it records
that substitution. Distances remain robot-command projections in world space.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from functools import lru_cache
import numpy as np

from foothold_s2.eval.ex42_task_cells import sha256
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh

FORMAT='foothold-ex42-task-replicas/1'


@lru_cache(maxsize=2)
def _load_source(folder,manifest_sha,npz_sha):
    """Cache immutable decoded bytes within one CPU preparation process."""
    folder=Path(folder);doc=json.loads((folder/'mesh_manifest.json').read_text(encoding='utf-8'))
    data=load_combined_mesh(folder/'terrain_mesh.npz',doc['mesh_sha256'])
    triangles=np.asarray(data['vertices'])[np.asarray(data['faces'])]
    return doc,data,triangles,triangles.mean(1)


def _sizes():
    from foothold_s2.terrains import ame2_preset,jeplo_preset,hipan_posture,sparse_terrains
    return {'A':tuple(sparse_terrains.TILE),'B':(ame2_preset.SIZE,)*2,
        'C':(jeplo_preset.SIZE,)*2,'D':tuple(hipan_posture.TILE_SIZE),'E':tuple(sparse_terrains.TILE)}


def select_tile(folder, *, family,kind,level):
    folder=Path(folder).resolve();mp=folder/'mesh_manifest.json'
    manifest_sha=sha256(mp);npz_sha=sha256(folder/'terrain_mesh.npz')
    doc,data,triangles,centers=_load_source(str(folder),manifest_sha,npz_sha)
    if type(level) is not int: raise ValueError('integer level required')
    if doc.get('format')=='foothold-ex42-evaluation-mesh/1':
        from foothold_s2.eval.ex42_eval_mesh import preflight as source_preflight
        data=source_preflight(folder)
        columns=data['columns']
        found=[i for i,c in enumerate(columns) if c['kind']==kind]
        if family!='V' or level!=0 or len(found)!=1: raise ValueError('fixed evaluation kind/level missing')
        col=found[0];meta=columns[col]
        low=np.asarray(meta['tile_offset_m'],float);size=meta['tile_size_m']
        anchors=meta['anchors_local_m'];dims=meta['dimensions']
    elif doc.get('format')=='foothold-ex42-combined-mesh/1':
        from foothold_s2.terrains.ex42_column_reset import build_column_table
        table=build_column_table(data['column_family'])
        found=[i for i,c in enumerate(table) if c['family']==family and c['kind']==kind]
        if not found or not 0<=level<data['origins'].shape[0]: raise ValueError('combined kind/level missing')
        # Repeated kind columns: a request explicitly records which representative
        # column is selected; never silently remaps by environment number.
        col=found[0];size=_sizes()[family]
        family_cols=[i for i,f in enumerate(data['column_family']) if f==family]
        index=family_cols.index(col);rows=data['origins'].shape[0]
        low=np.array([(level-rows/2)*size[0],(index-len(family_cols)/2)*size[1]+doc['offsets_m'][family],0.])
        anchors={};dims={}
    else: raise ValueError('unknown terrain source format')
    selected=np.all((centers[:,:2]>low[:2]+1e-7)&(centers[:,:2]<low[:2]+size-1e-7),axis=1)
    # Outer vertical faces can lie exactly on the tile boundary.
    selected |= np.all((triangles[:,:,:2]>=low[None,None,:2]-1e-6)&
                       (triangles[:,:,:2]<=low[None,None,:2]+size+1e-6),axis=(1,2))
    tri=triangles[selected]-low
    if not len(tri) or np.any(tri[:,:,:2]<-1e-4) or np.any(tri[:,:,:2]>np.asarray(size)+1e-4):
        raise ValueError('selected tile is empty or crosses its carrier boundary')
    vertices=np.asarray(tri.reshape(-1,3),np.float32)
    faces=np.arange(len(vertices),dtype=np.int32).reshape(-1,3)
    original_origin=np.asarray(data['origins'][level,col])-low
    origin=original_origin.copy()
    if family=='E':
        from foothold_s2.terrains.ex42_mesh_mount import local_mesh_heights
        xy=np.array([[.5,size[1]/2]])
        z=local_mesh_heights(vertices,faces,xy)[0]
        if not np.isfinite(z):raise ValueError('E entry has no support')
        origin=np.array([xy[0,0],xy[0,1],z])
    return dict(vertices=vertices,faces=faces,origin=origin,source_origin=original_origin,size=list(size),anchors=anchors,dimensions=dims,
        source_manifest=str(mp),source_manifest_sha256=manifest_sha,source_mesh_sha256=doc['mesh_sha256'],
        source_file_sha256=npz_sha,family=family,kind=kind,level=level,column=col,
        tile_triangle_sha256=hashlib.sha256(vertices.tobytes()+faces.tobytes()).hexdigest())


def task_anchors(tile):
    """Geometry-derived bounds. Tolerances and completion timing belong to request.

    JEPLO's roughness remains on the top. Select the near-top horizontal
    triangles within the central highest plateau, not a floor bypass.
    """
    size=tile['size'];a=tile['anchors'];v=tile['vertices'];tri=v[tile['faces']]
    result={'exit_x':size[0]-.5,'tile_end_x':size[0],'exit_bounds_y':[0.,size[1]]}
    if 'landing_bounds_xy' in a:
        x0,x1,y0,y1=a['landing_bounds_xy']
        result.update(exit_x=x0+.2,tile_end_x=x1,exit_bounds_y=[y0,y1],
                      support_floor_m=a['landing_center'][2])
    elif 'top' in a:
        x,y,z=a['top'];result.update(exit_x=x-.8,tile_end_x=x+.8,exit_bounds_y=[0.,size[1]],support_floor_m=z)
    elif 'landing_center' in a:
        result.update(exit_x=a['landing_center'][0],support_floor_m=a['landing_center'][2])
    if tile['family']=='C' and tile['kind']=='box':
        top=float(v[:,2].max())
        upper=tri[(tri[:,:,2].min(1)>=top-.08)&(np.ptp(tri[:,:,2],axis=1)<.08)]
        if not len(upper):raise ValueError('JEPLO central top surface missing')
        points=upper.reshape(-1,3);lo=points[:,:2].min(0);hi=points[:,:2].max(0)
        result.update(center_bounds_xy=[float(lo[0]),float(hi[0]),float(lo[1]),float(hi[1])],
                      center_top_m=float(np.median(upper[:,:,2])))
    return result


def build_replicas(source,output,*,family,kind,level,flat=False):
    import trimesh
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    tile=select_tile(source,family=family,kind=kind,level=level)
    sx,sy=tile['size'];base=trimesh.Trimesh(tile['vertices'],tile['faces'],process=False)
    origin=tile['origin'].copy()
    if flat:
        base=trimesh.creation.box([sx,sy,.2]);base.apply_translation([sx/2,sy/2,-.1]);origin[2]=0
    pieces=[];origins=np.empty((8,8,3))
    for r in range(8):
        for c in range(8):
            offset=np.array([r*sx,c*sy,0]);mesh=base.copy();mesh.apply_translation(offset)
            pieces.append(mesh);origins[r,c]=origin+offset
    # Exterior only: never add a ground plane underneath gap/crawl tiles.
    for x0,x1,y0,y1 in ((-20.,0.,-20.,8*sy+20),(8*sx,8*sx+20,-20,8*sy+20),
                        (0,8*sx,-20,0),(0,8*sx,8*sy,8*sy+20)):
        mesh=trimesh.creation.box([x1-x0,y1-y0,.2]);mesh.apply_translation([(x0+x1)/2,(y0+y1)/2,-.1]);pieces.append(mesh)
    joined=trimesh.util.concatenate(pieces)
    vertices=np.asarray(joined.vertices,np.float32);faces=np.asarray(joined.faces,np.int32)
    output.mkdir(parents=True,exist_ok=False)
    npz=output/'terrain_mesh.npz';np.savez_compressed(npz,vertices=vertices,faces=faces,origins=origins,column_family=np.array(['V']*8))
    doc={k:tile[k] for k in ('source_manifest','source_manifest_sha256','source_mesh_sha256',
          'source_file_sha256','family','kind','level','column','tile_triangle_sha256')}
    doc.update(format=FORMAT,training_allowed=False,flat_reference=bool(flat),tile_size_m=tile['size'],
        local_origin_m=origin.tolist(),source_origin_m=tile['source_origin'].tolist(),task_anchors=task_anchors(tile),
        origin_rule='E entry x0.5,y mid, measured support z; lead 11/11 15:20' if family=='E' else 'source origin unchanged',
        dimensions=tile['dimensions'],mesh_file_sha256=sha256(npz),
        mesh_sha256=hashlib.sha256(vertices.tobytes()+faces.tobytes()).hexdigest(),envs=64)
    (output/'replica_receipt.json').write_text(json.dumps(doc,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    return doc


def preflight(folder):
    folder=Path(folder);doc=json.loads((folder/'replica_receipt.json').read_text(encoding='utf-8'))
    if doc.get('format')!=FORMAT or doc.get('training_allowed') is not False or doc.get('envs')!=64:
        raise ValueError('invalid task replica receipt')
    source=Path(doc['source_manifest'])
    if sha256(source)!=doc['source_manifest_sha256']:raise ValueError('source manifest changed')
    original=json.loads(source.read_text(encoding='utf-8'))
    if original.get('mesh_sha256')!=doc['source_mesh_sha256'] or sha256(source.parent/'terrain_mesh.npz')!=doc['source_file_sha256']:
        raise ValueError('source mesh changed')
    npz=folder/'terrain_mesh.npz'
    if sha256(npz)!=doc['mesh_file_sha256']:raise ValueError('replica file SHA changed')
    data=load_combined_mesh(npz,doc['mesh_sha256'])
    if data['origins'].shape!=(8,8,3):raise ValueError('invalid replica origins')
    expected=np.broadcast_to(np.asarray(doc['local_origin_m']),(8,8,3)).copy()
    expected[:,:,0]+=np.arange(8)[:,None]*doc['tile_size_m'][0]
    expected[:,:,1]+=np.arange(8)[None,:]*doc['tile_size_m'][1]
    if not np.allclose(data['origins'],expected,atol=1e-6,rtol=0):raise ValueError('replica origins changed')
    return {**data,'receipt':doc}
