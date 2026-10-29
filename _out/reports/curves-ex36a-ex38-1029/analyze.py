"""Read-only CPU analysis. Writes only this report's evidence directory."""
from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime
import numpy as np
import pandas as pd
import yaml
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

OUT = Path(__file__).resolve().parent
ROOT = Path('C:/Users/AI-WS01/s2_lab/basic_gait_runs/main')
RUNS = {
    'EX36A': 'EX-36A-basic-share30_20261029_013052_21044',
    'EX38a': 'EX-38-basic-e1rew_20261029_040521_60072',
    'EX38b': 'EX-38-basic-e1rew_20261029_123840_163180',
}
RANGES = {'EX36A': (1501, 3000), 'EX38a': (1501, 2709), 'EX38b': (2710, 3001)}
WINDOWS = {
    'early': (1601, 1700), 'middle': (2201, 2300),
    'late_base': (2501, 2600), 'pre_resume': (2680, 2709),
    'post_resume': (2710, 2739), 'tail_prev': (2801, 2900),
    'tail': (2901, 3000),
}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def ratio(r, length):
    assert np.all(np.isfinite(r)) and np.all(np.isfinite(length))
    assert np.all(length > 0)
    return r / length

def mix(a, b, na, nb):
    assert np.all(na + nb > 0)
    return (a * na + b * nb) / (na + nb)

# Known-answer checks distinguish ratio of means from mean of per-episode ratios.
assert np.isclose(ratio(np.array([9.]), np.array([5.]))[0], 1.8)
assert np.isclose(mix(np.array([0.]), np.array([2.]), np.array([10.]), np.array([30.]))[0], 1.5)
try:
    ratio(np.array([1.]), np.array([0.]))
except AssertionError:
    pass
else:
    raise AssertionError('zero episode length was not rejected')

all_data = {}
provenance = {'captured_at': datetime.now().astimezone().isoformat(), 'inputs': [], 'runs': {},
              'known_answer_checks': ['ratio_of_means=1.8', 'weighted_merge=1.5', 'zero_length_rejected']}
cfgs = {}
for name, dirname in RUNS.items():
    root = ROOT / dirname
    dst = OUT / 'inputs' / name
    dst.mkdir(parents=True, exist_ok=True)
    files = sorted(root.glob('*tfevents*'))
    assert len(files) == 1, (name, files)
    for p in files + [root / x for x in ['manifest.json', 'resume_parent.json', 'basic_start_receipt.json',
                                          'train_start_status.json', 'params/env.yaml', 'params/agent.yaml']]:
        before = sha(p)
        target = dst / p.name
        shutil.copyfile(p, target)
        assert sha(target) == before == sha(p), ('source changed during copy', p)
        provenance['inputs'].append({'run': name, 'path': str(p), 'snapshot': str(target),
                                     'sha256': before, 'bytes': p.stat().st_size})
    ea = EventAccumulator(str(dst / files[0].name), size_guidance={'scalars': 0, 'tensors': 0},
                          purge_orphaned_data=False).Reload()
    assert ea.Tags()['tensors'] == []
    cols = {}
    for tag in ea.Tags()['scalars']:
        if tag.endswith('/time'):
            continue  # These have wall-clock seconds as step, not iteration.
        events = ea.Scalars(tag)
        steps = [e.step for e in events]
        assert len(steps) == len(set(steps)), ('duplicate tag/step', name, tag)
        cols[tag] = pd.Series({e.step: e.value for e in events})
    df = pd.DataFrame(cols).sort_index()
    df.index.name = 'iteration'
    lo, hi = RANGES[name]
    assert df.index.tolist() == list(range(lo, hi + 1)), ('missing iteration', name)
    required = ['Train/mean_reward', 'Train/mean_episode_length', 'Loss/kl_probe/ppo_mean',
                'Policy/mean_noise_std', 'Loss/value_function', 'Loss/learning_rate']
    assert np.isfinite(df[required].values).all()
    df['reward_per_step'] = ratio(df['Train/mean_reward'], df['Train/mean_episode_length'])
    na, nb = df['Loss/map_switch/on_env_steps'], df['Loss/map_switch/off_env_steps']
    assert np.all(na + nb == 3072 * 24)
    df['terrain_mean'] = mix(df['Loss/map_switch/on_terrain_level_mean'], df['Loss/map_switch/off_terrain_level_mean'], na, nb)
    assert np.max(np.abs(df['terrain_mean'] - (841 + 2 * 1058) / 3072)) < 1e-6
    for term, weight in [('lin', 1.5 if name == 'EX36A' else 2.0), ('ang', .5 if name == 'EX36A' else 1.0)]:
        a = df[f'Loss/map_switch/on_track_{term}_vel_per_s']
        b = df[f'Loss/map_switch/off_track_{term}_vel_per_s']
        df[f'track_{term}_unit_weight'] = mix(a, b, na, nb) / weight
        assert df[f'track_{term}_unit_weight'].between(0, 1.000001).all()
    cfgs[name] = yaml.load((dst / 'env.yaml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    df.to_csv(OUT / f'{name}_raw.csv', float_format='%.17g')
    all_data[name] = df
    provenance['runs'][name] = {'rows': len(df), 'first': lo, 'last': hi, 'scalar_tags': len(cols),
                               'missing_by_tag': {k:int(v) for k,v in df.isna().sum().items() if v},
                               'git': json.loads((dst/'manifest.json').read_text(encoding='utf-8'))['git']}

ex38 = pd.concat([all_data['EX38a'], all_data['EX38b']]).sort_index()
assert not ex38.index.duplicated().any()
assert ex38.index.tolist() == list(range(1501, 3002))
all_data['EX38'] = ex38
ex38.to_csv(OUT / 'EX38_raw.csv', float_format='%.17g')

def stats(frame, lo, hi, tag):
    x = frame.loc[lo:hi, tag].dropna()
    if x.empty:
        return None
    return {'n':len(x), 'mean':float(x.mean()), 'min':float(x.min()), 'max':float(x.max()),
            'sd_iterations':float(x.std(ddof=1)),
            'slope_per100':float(np.polyfit(x.index.to_numpy(dtype=float)-float(x.index[0]), x, 1)[0]*100)}

summary = {}
for name in ['EX36A', 'EX38']:
    df = all_data[name]
    summary[name] = {tag:{w:stats(df,*window,tag) for w,window in WINDOWS.items()} for tag in df}
    blocks = []
    for lo in range(1501, 3001, 100):
        blocks.append({'lo':lo,'hi':lo+99, **{tag:float(df.loc[lo:lo+99,tag].mean()) for tag in df}})
    pd.DataFrame(blocks).to_csv(OUT / f'{name}_blocks100.csv',index=False,float_format='%.17g')

def flatten(obj, p=''):
    if isinstance(obj,dict):
        return {k2:v2 for k,v in obj.items() for k2,v2 in flatten(v,p+'/'+k).items()}
    if isinstance(obj,list):
        return {k2:v2 for k,v in enumerate(obj) for k2,v2 in flatten(v,p+'/'+str(k)).items()}
    return {p:obj}

flat={k:flatten(v) for k,v in cfgs.items()}
provenance['env_diffs']={}
for a,b in [('EX36A','EX38a'),('EX38a','EX38b')]:
    provenance['env_diffs'][a+' -> '+b] = {k:[flat[a].get(k),flat[b].get(k)] for k in sorted(flat[a].keys()|flat[b].keys()) if flat[a].get(k)!=flat[b].get(k)}

for p in [Path('C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/runners/on_policy_runner.py'),
          Path('C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/algorithms/ppo.py'),
          Path('C:/isaac/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py')]:
    dst=OUT/'sources/installed'/p.name
    dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,dst)
    provenance['inputs'].append({'path':str(p),'snapshot':str(dst),'sha256':sha(dst),'note':'installed read-only source; historical library bytes not sealed by run manifest'})
(OUT/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

print('COUNTS',provenance['runs'])
print('ENV_DIFFS',provenance['env_diffs'])
for name in ['EX36A','EX38']:
    print('\n',name)
    for tag in ['reward_per_step','Train/mean_episode_length','track_lin_unit_weight','track_ang_unit_weight',
                'Loss/kl_probe/ppo_mean','Loss/kl_probe/phi_mean','Policy/mean_noise_std','Loss/value_function',
                'Loss/learning_rate','Loss/entropy','terrain_mean']:
        print(tag, {w:round(v['mean'],8) for w,v in summary[name][tag].items()})
    lr=all_data[name]['Loss/learning_rate']
    print('LR min/max/floor_count',float(lr.min()),float(lr.max()),int((lr<=1.00001e-5).sum()))
print('All inputs copied read-only, 3 known-answer checks, contiguous/dedup/nonfinite/terrain/count checks passed.')
