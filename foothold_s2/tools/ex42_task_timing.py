"""CPU-only result-independent timing table from pinned saved meshes."""
import argparse
import json
from pathlib import Path
import yaml

from foothold_s2.eval.ex42_task_cells import sha256
from foothold_s2.eval.ex42_task_mesh import select_tile,task_anchors
from foothold_s2.eval.ex42_task_suite import completion_timing
from foothold_s2.terrains.ex42_column_reset import build_column_table
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh


def table(plan_path,combined,evaluation):
    plan=yaml.safe_load(Path(plan_path).read_text(encoding='utf-8'))
    rows=[];sources={}
    for folder in (Path(combined),Path(evaluation)):
        doc=json.loads((folder/'mesh_manifest.json').read_text(encoding='utf-8'))
        sources[str(folder)]={'manifest_sha256':sha256(folder/'mesh_manifest.json'),
                             'mesh_sha256':doc['mesh_sha256'],'file_sha256':sha256(folder/'terrain_mesh.npz')}
        if folder==Path(combined):
            data=load_combined_mesh(folder/'terrain_mesh.npz',doc['mesh_sha256'])
            columns=list(dict.fromkeys((r['family'],r['kind']) for r in build_column_table(data['column_family'])))
            cases=[(f,k,l) for f,k in columns for l in range(data['origins'].shape[0])]
        else:cases=[('V',c['kind'],0) for c in doc['columns']]
        for family,kind,level in cases:
            tile=select_tile(folder,family=family,kind=kind,level=level)
            # Reverse 10 cm paper stair has the approved 0.5 m/s reverse command.
            speed=.5 if kind=='eval_stairs_010' else 1.
            timing=completion_timing(plan,origin=tile['origin'],anchors=task_anchors(tile),speed=speed)
            rows.append({'family':family,'kind':kind,'level':level,'origin_m':tile['origin'].tolist(),
                         'source_origin_m':tile['source_origin'].tolist(),'anchors':task_anchors(tile),**timing})
    return {'format':'foothold-ex42-task-geometry-times/1','sources':sources,'rows':rows,
            'grade':'geometry measured on CPU; time margin is lead 11/11 15:20 assumption; no policy results'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','combined','evaluation','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();doc=table(a.plan,a.combined,a.evaluation)
    with a.out.open('x',encoding='utf-8') as f:json.dump(doc,f,indent=2,ensure_ascii=False,allow_nan=False)
    print(json.dumps({'rows':len(doc['rows']),'sha256':sha256(a.out),'out':str(a.out)}))


if __name__=='__main__':main()
