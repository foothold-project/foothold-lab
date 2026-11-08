"""Independently recalculate selected EX29 claims. CPU only, immutable inputs."""
from __future__ import annotations
import csv
import hashlib
import json
import re
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
RAW = Path('C:/Users/AI-WS01/s2_lab/run_20261024')
RUN = Path('C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_topdown/2026-10-24_08-20-33_ex29-td-main')
SOL = Path('C:/mai/wt/foothold-lab/sol-23a/inbox/jay/20261023-experiments')
OUT = HERE / 'figs/history-audit-1024'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def roll(q):
    w, x, y, z = np.moveaxis(q, -1, 0)
    return np.arctan2(2*(w*x+y*z), 1-2*(x*x+y*y))

def read_csv(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return {int(row['update']): row for row in csv.DictReader(f)}

def main():
    # Known input before production, no simulator import.
    assert np.isclose(roll(np.array([np.sqrt(.5), np.sqrt(.5), 0, 0])), np.pi/2)
    assert roll(np.array([1., 0, 0, 0])) == 0
    data = {'scope': 'CPU saved records; selected transitions, not a causal intervention', 'sources': {}}
    path = RUN/'step_evidence.jsonl'
    steps = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert [v['it'] for v in steps] == list(range(229)), 'missing or repeated update'
    data['sources'][path.as_posix()] = sha(path)
    data['orientation_counts'] = {}
    for a,b in [(0,0),(1,1),(0,9),(0,24),(100,124),(175,199)]:
        data['orientation_counts'][f'{a}:{b}'] = sum(v['termination_counts']['bad_orientation'] for v in steps if a<=v['it']<=b)
    assert list(data['orientation_counts'].values()) == [0,18,739,1196,60676,105201]
    log = RAW/'td_main_segment1/run.log'
    text = re.sub(r'\x1b\[[0-9;]*m', '', log.read_text(encoding='utf-8-sig'))
    blocks = re.split(r'Learning iteration\s+(\d+)/\d+', text)
    fields = {'episode_length_steps':'Mean episode length', 'mean_reward':'Mean reward',
              'terrain_level':'Curriculum/terrain_levels', 'bad_orientation_ratio':'Episode_Termination/bad_orientation',
              'gt_fraction':'Mean adasmpl/gt_fraction loss'}
    parsed = {}
    for j in range(1,len(blocks),2):
        row = {}
        for key, label in fields.items():
            m = re.search(r'^\s*'+re.escape(label)+r':\s*([-+0-9.eE]+)', blocks[j+1],re.M)
            if m: row[key] = float(m.group(1))
        parsed[int(blocks[j])] = row
    sol = read_csv(SOL/'EVIDENCE-sol-24e-ex29-runlog.csv')
    for i,row in parsed.items():
        for k,v in row.items():
            assert np.isclose(v,float(sol[i][k]),rtol=0,atol=1e-7), (i,k,v,sol[i][k])
    assert len(parsed)==229
    data['log_rows'] = parsed
    data['sources'][log.as_posix()] = sha(log)
    trace_sol = read_csv(SOL/'EVIDENCE-sol-24e-ex29-trace8.csv')
    meta = json.loads((RUN/'training_trace/coordinate_metadata.json').read_text())
    names = meta['joint_names']
    indexes = {side:[names.index(side+'_'+joint+'_joint') for joint in ('hip','calf')] for side in ('FL','FR','RL','RR')}
    rows = []
    for path in sorted((RUN/'training_trace').glob('update_*.npz')):
        i = int(path.stem.split('_')[1])
        with np.load(path,allow_pickle=False) as z:
            a = z['actor_action']
            row = {'update':i, 'roll_mean':float(roll(z['root_quat_w']).mean())}
            for j,joint in enumerate(('hip','calf')):
                row[joint+'_right_minus_left'] = float((a[:,:,[indexes['FR'][j],indexes['RR'][j]]].mean(-1)-a[:,:,[indexes['FL'][j],indexes['RL'][j]]].mean(-1)).mean())
            if i==0:
                assert np.allclose(z['root_pos_w'][0,:,2],.4)
                assert np.allclose(roll(z['root_quat_w'][0]),0)
            for ours,theirs in [('roll_mean','prestep_roll_mean_rad'),('hip_right_minus_left','preclip_right_hip_minus_left_mean'),('calf_right_minus_left','preclip_right_calf_minus_left_mean')]:
                assert np.isclose(row[ours],float(trace_sol[i][theirs]),atol=2e-6), (i,ours)
            rows.append(row)
    assert len(rows)==75
    data['trace_groups']={}
    for a,b in [(0,24),(100,124),(200,224)]:
        sel=[r for r in rows if a<=r['update']<=b]
        data['trace_groups'][f'{a}:{b}']={k:float(np.mean([r[k] for r in sel])) for k in ['roll_mean','hip_right_minus_left','calf_right_minus_left']}
    data['evals']=[]
    for terrain in ['flat','stepping_stones_low']:
        for mode in ['gt','pred']:
            p=RAW/f'ex29_model200_{terrain}_{mode}/review_feet.npz'
            with np.load(p,allow_pickle=False) as z:
                done=np.flatnonzero(z['done'])
                row={'terrain':terrain,'map':mode,'ticks':len(z['t']), 'done_count':len(done), 'first_done':int(done[0]),
                     'all_reasons':np.unique(z['termination_reason'][done]).tolist(),
                     'all_terms':np.unique(z['termination_terms'][done]).tolist(),
                     'mean_abs_roll_at_pretermination':float(np.abs(z['roll'][done]).mean()),
                     'mean_abs_pitch_at_pretermination':float(np.abs(z['pitch'][done]).mean()),
                     'actual_gt_fraction':float(z['map_use_gt'].mean()),'sha256':sha(p)}
                assert len(done)==34 and done[0]==16 and len(z['t'])==600
                assert row['all_reasons']==['termination_terms']
                assert row['all_terms']==['bad_orientation']
                assert row['actual_gt_fraction']==(1 if mode=='gt' else 0)
            data['evals'].append(row)
    data['checks'] = {'known_input_quaternion':2, 'log_rows_crosschecked':len(parsed), 'trace_rows_crosschecked':len(rows), 'evaluations':4}
    OUT.mkdir(parents=True,exist_ok=True)
    output=OUT/'ex29_independent_check.json'
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'output':output.as_posix(),'sha256':sha(output),'checks':data['checks'],'orientation_counts':data['orientation_counts'],'trace_groups':data['trace_groups']},ensure_ascii=False))

if __name__=='__main__':main()
