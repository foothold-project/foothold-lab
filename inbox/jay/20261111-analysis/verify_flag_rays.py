"""Independent CPU ray check of every finite saved flag, against its support Z."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import trimesh

from foothold_s2.terrains import ame2_preset, jeplo_preset, hipan_posture, sparse_terrains
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh


def verify(folder):
    folder=Path(folder)
    doc=json.loads((folder/'mesh_manifest.json').read_text(encoding='utf-8'))
    data=load_combined_mesh(folder/'terrain_mesh.npz',doc['mesh_sha256'])
    with np.load(folder/'terrain_mesh.npz') as saved:
        flags=saved['flags']
    v,f=data['vertices'],data['faces'];cent=v[f][:,:,:2].mean(1)
    meta=doc['flag_provenance']['cells'];results=[];started=time.perf_counter()
    widths={'A':sparse_terrains.TILE[1],'B':ame2_preset.SIZE,
            'C':jeplo_preset.SIZE,'D':hipan_posture.TILE_SIZE[1],'E':sparse_terrains.TILE[1]}
    for family in doc['families_present']:
        width=doc['columns_by_family'][family]*widths[family]
        shift=doc['offsets_m'][family]
        mask=(cent[:,1]>=shift-width/2)&(cent[:,1]<shift+width/2)
        mesh=trimesh.Trimesh(v,f[mask],process=False)
        relevant=[m for m in meta if m['family']==family and 'support_z_m' in m]
        if not relevant:
            results.append({'family':family,'points':0,'bad':0,'max_error_m':None})
            continue
        pts=np.concatenate([flags[m['row'],m['column']] for m in relevant])
        expected=np.concatenate([m['support_z_m'] for m in relevant])
        origins=np.column_stack((pts,np.full(len(pts),v[:,2].max()+10)))
        for i,m in enumerate(relevant):
            # Inside the tunnel, not above its roof. D floor-to-roof >= .25 m.
            if m['kind']=='crawl':origins[i*4:(i+1)*4,2]=expected[i*4:(i+1)*4]+.1
        loc,idx,_=mesh.ray.intersects_location(origins,np.tile([0.,0.,-1.],(len(pts),1)),multiple_hits=True)
        got=np.full(len(pts),np.nan)
        for i in np.unique(idx):got[i]=loc[idx==i,2].max()
        err=np.abs(got-expected);bad=np.flatnonzero(~np.isfinite(got)|(err>1e-4))
        results.append({'family':family,'points':len(pts),'bad':len(bad),
            'max_error_m':float(np.nanmax(err)) if np.isfinite(err).any() else None,
            'first_bad_indices':bad[:10].tolist()})
    return {'geometry_sha256':doc['mesh_sha256'],'flags_sha256':doc['flag_provenance']['sha256'],
            'height_tolerance_m':1e-4,'method':'trimesh ray triangle intersection',
            'results':results,'seconds':time.perf_counter()-started,
            'passed':sum(r['bad'] for r in results)==0 and sum(r['points'] for r in results)>0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder');p.add_argument('--out',required=True)
    args=p.parse_args();result=verify(args.folder)
    Path(args.out).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result))
    raise SystemExit(0 if result['passed'] else 2)
