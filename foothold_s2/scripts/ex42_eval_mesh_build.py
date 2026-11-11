"""Build immutable evaluation mesh on CPU. Does not launch Kit or training."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from foothold_s2.terrains.ex42_eval_terrains import KINDS, LANDING, PAPER, START, SURFACE_SPIN, write_mesh
from foothold_s2.eval.ex42_eval_mesh import preflight
from foothold_s2.scripts.ex42_mesh_mount_check import part_a

GROUPS = {'landing': (LANDING,), 'paper': PAPER, 'start': START,
          'surface': (SURFACE_SPIN,), 'all': KINDS}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--group',choices=list(GROUPS),default='all')
    p.add_argument('--seed',type=int,default=42)
    a=p.parse_args(argv)
    kinds=GROUPS[a.group]
    doc=write_mesh(a.out,kinds=kinds,seed=a.seed)
    record=preflight(a.out)
    cpu=part_a(record)
    (a.out/'cpu_origin_check.json').write_text(json.dumps(cpu,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'mesh_sha256':doc['mesh_sha256'],'mesh_file_sha256':doc['mesh_file_sha256'],
        'columns':len(kinds),'cpu_origins':cpu,'kit_mount':'pending','training_started':False}),flush=True)
    return 0 if cpu['passed'] else 2


if __name__=='__main__':
    raise SystemExit(main())
