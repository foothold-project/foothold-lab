"""CPU-only source replay for lin_vel_z and EX40's terrain-level window deltas."""
from pathlib import Path
import hashlib
import json
import torch
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

ROOT=Path('C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240')
OUT=Path(__file__).with_name('evidence')/'EX41-parent-weight-levels.json'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    checkpoint=ROOT/'model_6000.pt'
    data=torch.load(checkpoint,map_location='cpu',weights_only=False)
    state=data['continuous_curriculum']
    events=next(ROOT.glob('events.out.tfevents*'))
    accumulator=EventAccumulator(str(events),size_guidance={'scalars':0});accumulator.Reload()
    tags=('Loss/basic_reward/lin_vel_z_weight','Episode_Reward/lin_vel_z',
          'Loss/map_switch/on_terrain_level_mean','Loss/map_switch/off_terrain_level_mean')
    rows={tag:{x.step:x.value for x in accumulator.Scalars(tag)} for tag in tags}
    starts=(1500,3000,4500,5500,6000,6500,7000,7500)
    result={'purpose':'read-only parent evidence; not a live score',
        'sources':[{'path':str(path),'sha256':sha(path)} for path in (checkpoint,events,ROOT/'params/env.yaml')],
        'checkpoint_iter':data['iter'],'curriculum_active':state['active'],
        'b1_entry_iteration':state['b1_entry_iteration'],
        'scalar_samples':{t:{str(n):r[n] for n in (1501,3000,3001,5950,6000,6001)} for t,r in rows.items()},
        'window_formula':'mean(start+300,350,400,450,500) - mean(start+50,100,150,200,250)',
        'level_deltas':{tag:{str(start):sum(values[start+i] for i in range(300,501,50))/5-
            sum(values[start+i] for i in range(50,251,50))/5 for start in starts}
            for tag,values in rows.items() if 'terrain_level' in tag},
        'limitations':'EX40 fixed_l02 has no performance level promotion. ON/OFF means vary with map selection; these are not advancement measurements.'}
    levels=data.get('env_state',{}).get('terrain_levels')
    if levels is not None:
        x=torch.as_tensor(levels).flatten().to('cpu')
        result['parent_terrain_levels']={'n':x.numel(),'mean':x.float().mean().item(),
            'counts':{str(v.item()):int((x==v).sum()) for v in x.unique()}}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(OUT),'sha256':sha(OUT),'lin_vel_z_m6000':rows[tags[0]][6000],
                      'parent_terrain_levels':result.get('parent_terrain_levels')},ensure_ascii=False))


if __name__=='__main__':main()
