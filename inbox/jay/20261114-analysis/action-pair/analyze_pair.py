"""CPU readback of completed mean/sample files. Never writes to the input folder."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from prepare import sha, read


def analyze(root):
    execution=read(root/'execution_plan.json')
    cp=Path(execution['checkpoint'])
    if sha(cp)!=execution['checkpoint_sha256']:
        raise ValueError('checkpoint changed')
    state=torch.load(cp,map_location='cpu',weights_only=False)
    std=state['model_state_dict']['std'].numpy()
    recorded=read(root/'pair_readback.json')
    if len(recorded['cells'])!=4:
        raise ValueError('four paired cells required')
    rows=[]
    for row in recorded['cells']:
        for action in ('mean','sample'):
            doc=read(root/action/'action_probe_map_modes.json')
            key=row['mode']+'/'+row['case']
            if not np.array_equal(np.array(doc['action_std_by_cell'][key]),std.astype(float)):
                raise ValueError('std receipt differs from checkpoint')
            raw=Path(row[action]['raw'])
            if sha(raw)!=row[action]['sha256']:
                raise ValueError('raw NPZ changed')
            with np.load(raw,allow_pickle=False) as z:
                identity=json.loads(str(z['run_identity'].item()))
                if (identity['checkpoint_sha256']!=execution['checkpoint_sha256']
                        or identity['code_head']!=execution['code_head']
                        or identity['eval_seed']!=42
                        or identity['action_sampling_probe']['action_mode']!=action):
                    raise ValueError('raw identity differs')
                vx=z['vx'].astype(float); alive=z['alive'].astype(bool); dt=float(z['dt'])
                if vx.shape!=(300,64) or alive.shape!=vx.shape or not np.isfinite(vx).all() or dt!=.02:
                    raise ValueError('raw trace dimensions or values differ')
                dist=(vx*alive).sum(0)*dt
                ratio=dist/(float(row['case'][3:])*len(vx)*dt)
                if abs(float(np.median(ratio))-row[action]['R_median'])>=1e-12:
                    raise ValueError('R readback differs')
                first=(vx[:50]*alive[:50]).mean(0)
                last=(vx[-50:]*alive[-50:]).mean(0)
                middle=(vx[100:200]*alive[100:200]).mean(0)
                rows.append(dict(map=row['mode'],command=row['case'],action=action,
                    R=float(np.median(ratio)),distance_m=float(np.median(dist)),
                    survived=int(alive[-1].sum()),stalled_2to4=int((middle<.05).sum()),
                    stalled_last1=int((last<.05).sum()),first_second_vx=float(np.median(first)),
                    last_second_vx=float(np.median(last)),raw=str(raw),sha256=sha(raw),
                    contact_available=any('contact' in k or 'force' in k for k in z.files)))
    return {'execution':execution,'std':std.tolist(),'cells':rows}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.resolve().is_relative_to(a.input.resolve()):
        raise ValueError('analysis output must be outside original result folder')
    result=analyze(a.input)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(f'CPU readback complete: {len(result["cells"])} cells')
